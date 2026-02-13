"""Custom RAG approach: retrieve -> structured output -> post-process.

This is the primary RAG pipeline using Azure SDK directly.
Key feature: anti-hallucination via structured output + citation injection.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from azure.search.documents import SearchClient
from jinja2 import Environment, FileSystemLoader
from openai import AsyncAzureOpenAI

import config
from approaches.approach import Approach
from models.chat import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    StructuredLLMOutput,
)
from models.norm import NormReference
from postprocessing.citation_injection import inject_citations
from postprocessing.source_validation import validate_cited_sources

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"
jinja_env = Environment(loader=FileSystemLoader(str(PROMPTS_DIR)), autoescape=True)


class ChatRAGApproach(Approach):
    """Custom RAG with structured output and deterministic citation injection."""

    def __init__(
        self,
        openai_client: AsyncAzureOpenAI,
        search_client: SearchClient,
    ) -> None:
        self.openai_client = openai_client
        self.search_client = search_client

    async def run(self, request: ChatRequest) -> ChatResponse:
        timer = self._timer()

        user_query = request.messages[-1].content
        past_messages = request.messages[:-1]

        # Stage 1: Query rewrite (with conversation history for follow-up questions)
        timer.start("query_rewrite")
        rewritten_query = await self._rewrite_query(user_query, past_messages)
        timer.stop()

        # Stage 2: Retrieve from Azure AI Search
        timer.start("retrieval")
        sources = await self._search_async(
            query=rewritten_query,
            strategy=request.search_strategy,
            top_k=request.top_k,
            use_semantic_ranker=request.use_semantic_ranker,
        )
        timer.stop()

        if not sources:
            return ChatResponse(
                answer="Zu dieser Frage wurden keine relevanten Mietrecht-Normen gefunden.",
                sources=[],
                confidence="low",
                search_strategy=request.search_strategy,
            )

        # Stage 3: Generate structured LLM response (with conversation history)
        timer.start("generation")
        llm_output = await self._generate(user_query, sources, request.temperature, past_messages)
        timer.stop()

        # Stage 4: Post-processing
        timer.start("postprocessing")

        # Validate cited sources
        valid_indices = validate_cited_sources(llm_output.cited_sources, sources)

        # Inject verbatim citations from norm cache
        answer = inject_citations(llm_output.explanation, sources)

        timer.stop()

        logger.info(
            "RAG pipeline completed in %.0fms (rewrite=%.0f, retrieval=%.0f, generation=%.0f, postprocess=%.0f)",
            timer.total_ms,
            timer.stages.get("query_rewrite", 0),
            timer.stages.get("retrieval", 0),
            timer.stages.get("generation", 0),
            timer.stages.get("postprocessing", 0),
        )

        # Filter sources to only those actually cited
        cited_sources = [s for i, s in enumerate(sources, 1) if i in valid_indices]

        return ChatResponse(
            answer=answer,
            sources=cited_sources,
            confidence=llm_output.confidence,
            search_strategy=request.search_strategy,
            approach="custom",
        )

    async def _rewrite_query(self, query: str, past_messages: list[ChatMessage] | None = None) -> str:
        """Rewrite user query for better retrieval using GPT-4o-mini."""
        template = jinja_env.get_template("query_rewrite.jinja2")
        prompt = template.render(query=query, past_messages=past_messages or [])

        try:
            response = await self.openai_client.chat.completions.create(
                model=config.AZURE_OPENAI_CHAT_MINI_DEPLOYMENT,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=200,
            )
            content = response.choices[0].message.content or ""
            rewritten = content.strip()
            logger.info("Query rewrite: '%s' -> '%s'", query, rewritten)
            return rewritten
        except Exception:
            logger.warning("Query rewrite failed, using original query", exc_info=True)
            return query

    # _search and _search_async inherited from Approach base class

    async def _generate(
        self,
        query: str,
        sources: list[NormReference],
        temperature: float = 0.0,
        past_messages: list[ChatMessage] | None = None,
    ) -> StructuredLLMOutput:
        """Generate structured LLM response with citation markers."""
        template = jinja_env.get_template("chat_system.jinja2")
        system_prompt = template.render(sources=sources)

        # Build messages: system + conversation history + current question with sources
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        for msg in past_messages or []:
            messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": query})

        response = await self.openai_client.chat.completions.create(
            model=config.AZURE_OPENAI_CHAT_DEPLOYMENT,
            messages=messages,
            temperature=temperature,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "legal_rag_response",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "explanation": {
                                "type": "string",
                                "description": "Answer with [1][2] citation markers. Do NOT include norm text.",
                            },
                            "cited_sources": {
                                "type": "array",
                                "items": {"type": "integer"},
                                "description": "List of source numbers cited.",
                            },
                            "confidence": {
                                "type": "string",
                                "enum": ["high", "medium", "low"],
                                "description": "Confidence level.",
                            },
                        },
                        "required": ["explanation", "cited_sources", "confidence"],
                        "additionalProperties": False,
                    },
                },
            },
        )

        content = response.choices[0].message.content
        if content is None:
            raise ValueError("LLM returned empty content — possible content filter refusal")
        parsed = json.loads(content)
        return StructuredLLMOutput.model_validate(parsed)
