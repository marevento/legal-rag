"""Abstract base class for RAG approaches."""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import AsyncGenerator, Iterator

from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizableTextQuery

import config
from models.chat import ChatRequest, ChatResponse, ChatResponseDelta
from models.norm import NormReference

logger = logging.getLogger(__name__)


class Approach(ABC):
    """Base class for RAG approaches (custom, langchain, etc.)."""

    search_client: SearchClient

    @abstractmethod
    async def run(self, request: ChatRequest) -> ChatResponse:
        """Execute the full RAG pipeline and return a complete response."""
        ...

    def _search(
        self,
        query: str,
        strategy: str = "hybrid",
        top_k: int = 5,
        use_semantic_ranker: bool = False,
    ) -> list[NormReference]:
        """Search Azure AI Search for relevant norms (sync — call via asyncio.to_thread)."""
        search_kwargs: dict = {"top": top_k}

        if strategy in ("vector", "hybrid"):
            search_kwargs["vector_queries"] = [
                VectorizableTextQuery(
                    text=query,
                    k_nearest_neighbors=top_k,
                    fields="content_vector",
                )
            ]

        if strategy in ("bm25", "hybrid"):
            search_kwargs["search_text"] = query
        else:
            search_kwargs["search_text"] = None

        if use_semantic_ranker:
            search_kwargs["query_type"] = "semantic"
            search_kwargs["semantic_configuration_name"] = config.AZURE_SEARCH_SEMANTIC_CONFIG

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
        use_semantic_ranker: bool = False,
    ) -> list[NormReference]:
        """Async wrapper around _search — runs in a thread to avoid blocking the event loop."""
        return await asyncio.to_thread(
            self._search,
            query=query,
            strategy=strategy,
            top_k=top_k,
            use_semantic_ranker=use_semantic_ranker,
        )

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
