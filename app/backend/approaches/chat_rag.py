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
    ChatRequest,
    ChatResponse,
    StructuredLLMOutput,
)
from models.norm import NormReference

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
        super().__init__()
        self.openai_client = openai_client
        self.search_client = search_client

    async def run(self, request: ChatRequest) -> ChatResponse:
        timer = self._timer()

        user_query = request.messages[-1].content
        past_messages = request.messages[:-1]

        # Stage 1+2: Query transform + retrieval
        timer.start("retrieval")
        sources = await self._retrieve(user_query, request, self.openai_client, past_messages)
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

        answer, cited_sources = self._postprocess(
            llm_output.explanation, llm_output.cited_sources, sources
        )

        timer.stop()

        logger.info(
            "RAG pipeline completed",
            extra={
                "custom_dimensions": {
                    "approach": "custom",
                    "total_ms": round(timer.total_ms),
                    "retrieval_ms": round(timer.stages.get("retrieval", 0)),
                    "generation_ms": round(timer.stages.get("generation", 0)),
                    "postprocessing_ms": round(timer.stages.get("postprocessing", 0)),
                    "search_strategy": request.search_strategy,
                    "query_transform": request.query_transform,
                    "decompose": request.decompose,
                    "sources_retrieved": len(sources),
                    "sources_cited": len(cited_sources),
                    "confidence": llm_output.confidence,
                    "history_turns": len(past_messages),
                },
            },
        )

        return ChatResponse(
            answer=answer,
            sources=cited_sources,
            confidence=llm_output.confidence,
            search_strategy=request.search_strategy,
            approach="custom",
        )

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
