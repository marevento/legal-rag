"""Abstract base class for RAG approaches."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from abc import ABC, abstractmethod
from contextlib import contextmanager
from pathlib import Path
from typing import AsyncGenerator, Iterator

from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from jinja2 import Environment, FileSystemLoader
from openai import AsyncAzureOpenAI, AzureOpenAI

import config
from models.chat import ChatMessage, ChatRequest, ChatResponse, ChatResponseDelta
from models.norm import NormReference
from postprocessing.citation_injection import inject_citations
from postprocessing.source_validation import validate_cited_sources

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_jinja_env = Environment(loader=FileSystemLoader(str(_PROMPTS_DIR)), autoescape=True)


class Approach(ABC):
    """Base class for RAG approaches (custom, langchain, etc.)."""

    search_client: SearchClient

    def __init__(self) -> None:
        self._embedding_client = AzureOpenAI(
            azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
            api_key=config.AZURE_OPENAI_API_KEY,
            api_version=config.AZURE_OPENAI_API_VERSION,
        )

    @abstractmethod
    async def run(self, request: ChatRequest) -> ChatResponse:
        """Execute the full RAG pipeline and return a complete response."""
        ...

    def _embed_query(self, text: str) -> list[float]:
        """Embed a query string using Azure OpenAI."""
        response = self._embedding_client.embeddings.create(
            model=config.AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
            input=text,
            dimensions=config.AZURE_OPENAI_EMBEDDING_DIMENSIONS,
        )
        return response.data[0].embedding

    def _search(
        self,
        query: str,
        strategy: str = "hybrid",
        top_k: int = 5,
    ) -> list[NormReference]:
        """Search Azure AI Search for relevant norms (sync — call via asyncio.to_thread)."""
        search_kwargs: dict = {"top": top_k}

        if strategy in ("vector", "hybrid"):
            embedding = self._embed_query(query)
            search_kwargs["vector_queries"] = [
                VectorizedQuery(
                    vector=embedding,
                    k_nearest_neighbors=top_k,
                    fields="content_vector",
                )
            ]

        if strategy in ("bm25", "hybrid"):
            search_kwargs["search_text"] = query
        else:
            search_kwargs["search_text"] = None

        results = self.search_client.search(**search_kwargs)

        sources = []
        for result in results:
            sources.append(
                NormReference(
                    norm_id=result["norm_id"],
                    paragraph=result["paragraph"],
                    titel=result.get("titel", ""),
                    text=result.get("text", ""),
                    url=result.get("url", ""),
                    relevance_score=result.get("@search.score", 0.0),
                )
            )

        logger.info("Retrieved %d sources via %s search", len(sources), strategy)
        return sources

    async def _search_async(
        self,
        query: str,
        strategy: str = "hybrid",
        top_k: int = 5,
    ) -> list[NormReference]:
        """Async wrapper around _search — runs in a thread to avoid blocking the event loop."""
        return await asyncio.to_thread(
            self._search,
            query=query,
            strategy=strategy,
            top_k=top_k,
        )

    def _search_with_embedding(
        self,
        query: str,
        embedding: list[float],
        strategy: str = "hybrid",
        top_k: int = 5,
    ) -> list[NormReference]:
        """Search using a pre-computed embedding (for HyDE)."""
        search_kwargs: dict = {"top": top_k}

        if strategy in ("vector", "hybrid"):
            search_kwargs["vector_queries"] = [
                VectorizedQuery(
                    vector=embedding,
                    k_nearest_neighbors=top_k,
                    fields="content_vector",
                )
            ]

        if strategy in ("bm25", "hybrid"):
            search_kwargs["search_text"] = query
        else:
            search_kwargs["search_text"] = None

        results = self.search_client.search(**search_kwargs)

        sources = []
        for result in results:
            sources.append(
                NormReference(
                    norm_id=result["norm_id"],
                    paragraph=result["paragraph"],
                    titel=result.get("titel", ""),
                    text=result.get("text", ""),
                    url=result.get("url", ""),
                    relevance_score=result.get("@search.score", 0.0),
                )
            )

        logger.info("Retrieved %d sources via %s search (HyDE embedding)", len(sources), strategy)
        return sources

    # --- Retrieval orchestration ---

    async def _retrieve(
        self,
        query: str,
        request: ChatRequest,
        openai_client: AsyncAzureOpenAI,
        past_messages: list[ChatMessage] | None = None,
    ) -> list[NormReference]:
        """Orchestrate retrieval: apply query transform and optional decomposition."""
        if request.decompose:
            return await self._retrieve_decompose(query, request, openai_client, past_messages)
        return await self._retrieve_single(query, request, openai_client, past_messages)

    async def _retrieve_single(
        self,
        query: str,
        request: ChatRequest,
        openai_client: AsyncAzureOpenAI,
        past_messages: list[ChatMessage] | None = None,
    ) -> list[NormReference]:
        """Apply query transform then search."""
        transformed = await self._apply_transform(query, request.query_transform, openai_client, past_messages)

        if request.query_transform == "hyde":
            # For HyDE, embed the hypothetical doc and use that for vector search
            embedding = await asyncio.to_thread(self._embed_query, transformed)
            return await asyncio.to_thread(
                self._search_with_embedding, query, embedding, request.search_strategy, request.top_k,
            )

        return await self._search_async(transformed, request.search_strategy, request.top_k)

    async def _apply_transform(
        self,
        query: str,
        transform: str,
        openai_client: AsyncAzureOpenAI,
        past_messages: list[ChatMessage] | None = None,
    ) -> str:
        """Apply a query transform: none, rewrite, or hyde."""
        if transform == "none":
            return query

        if transform == "rewrite":
            template = _jinja_env.get_template("query_rewrite.jinja2")
            prompt = template.render(query=query, past_messages=past_messages or [])
        elif transform == "hyde":
            template = _jinja_env.get_template("hyde.jinja2")
            prompt = template.render(query=query)
        else:
            return query

        try:
            response = await openai_client.chat.completions.create(
                model=config.AZURE_OPENAI_CHAT_MINI_DEPLOYMENT,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=300,
            )
            result = (response.choices[0].message.content or "").strip()
            logger.info("Query transform (%s): '%s' -> '%s'", transform, query, result[:100])
            return result or query
        except Exception:
            logger.warning("Query transform (%s) failed, using original query", transform, exc_info=True)
            return query

    async def _retrieve_decompose(
        self,
        query: str,
        request: ChatRequest,
        openai_client: AsyncAzureOpenAI,
        past_messages: list[ChatMessage] | None = None,
    ) -> list[NormReference]:
        """Decompose query into sub-queries, retrieve each, merge results."""
        template = _jinja_env.get_template("query_decompose.jinja2")
        prompt = template.render(query=query)

        try:
            response = await openai_client.chat.completions.create(
                model=config.AZURE_OPENAI_CHAT_MINI_DEPLOYMENT,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=300,
            )
            content = response.choices[0].message.content or "[]"
            sub_queries = json.loads(content)
            if not isinstance(sub_queries, list) or not sub_queries:
                sub_queries = [query]
            sub_queries = sub_queries[:4]  # cap at 4
            logger.info("Query decomposition: '%s' -> %s", query, sub_queries)
        except Exception:
            logger.warning("Query decomposition failed, using original query", exc_info=True)
            sub_queries = [query]

        # Retrieve each sub-query in parallel, applying the selected transform
        tasks = [
            self._retrieve_single(sq, request, openai_client, past_messages)
            for sq in sub_queries
        ]
        results = await asyncio.gather(*tasks)

        # Merge and deduplicate by norm_id, keeping highest relevance_score
        seen: dict[str, NormReference] = {}
        for source_list in results:
            for source in source_list:
                if source.norm_id not in seen or source.relevance_score > seen[source.norm_id].relevance_score:
                    seen[source.norm_id] = source

        merged = sorted(seen.values(), key=lambda s: s.relevance_score, reverse=True)
        logger.info("Decomposition merged %d unique sources from %d sub-queries", len(merged), len(sub_queries))
        return merged[:request.top_k]

    @staticmethod
    def _postprocess(
        explanation: str,
        cited_indices: list[int],
        sources: list[NormReference],
    ) -> tuple[str, list[NormReference]]:
        """Validate, renumber, and inject citations. Returns (answer, cited_sources)."""
        valid_indices = validate_cited_sources(cited_indices, sources)
        sorted_valid = sorted(set(valid_indices))
        renumber_map = {old: new for new, old in enumerate(sorted_valid, 1)}

        def _renumber(match: re.Match) -> str:
            idx = int(match.group(1))
            return f"[{renumber_map[idx]}]" if idx in renumber_map else match.group(0)

        renumbered = re.sub(r"\[(\d+)\]", _renumber, explanation)
        cited_sources = [sources[i - 1] for i in sorted_valid]
        answer = inject_citations(renumbered, cited_sources)
        return answer, cited_sources

    async def run_stream(self, request: ChatRequest) -> AsyncGenerator[ChatResponseDelta, None]:
        """Streaming variant — compute-then-stream (not token-level streaming).

        Design decision: structured JSON output must be complete before citation
        injection can replace [1][2] markers with verbatim norm text. Token-level
        streaming would require either moving injection to the frontend (duplicating
        logic) or streaming raw markers and sending a correction delta (causing
        flicker). Compute-then-stream keeps the anti-hallucination pipeline intact
        at the cost of higher TTFB (~2.5s).
        """
        response = await self.run(request)

        chunk_size = 20
        words = response.answer.split(" ")
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i : i + chunk_size])
            if i > 0:
                chunk = " " + chunk
            yield ChatResponseDelta(delta=chunk)

        yield ChatResponseDelta(
            delta="",
            sources=response.sources,
            confidence=response.confidence,
            done=True,
        )

    @staticmethod
    def _timer() -> "_Timer":
        return _Timer()


class _Timer:
    """Timer for pipeline stages, usable as a context manager."""

    def __init__(self) -> None:
        self.stages: dict[str, float] = {}
        self._start: float = 0.0
        self._current_stage: str = ""

    def start(self, stage: str) -> _Timer:
        self._current_stage = stage
        self._start = time.perf_counter()
        return self

    def stop(self) -> float:
        elapsed = (time.perf_counter() - self._start) * 1000  # ms
        self.stages[self._current_stage] = elapsed
        return elapsed

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        """Context manager: ``with timer.stage("retrieval"):``"""
        self.start(name)
        try:
            yield
        finally:
            self.stop()

    @property
    def total_ms(self) -> float:
        return sum(self.stages.values())
