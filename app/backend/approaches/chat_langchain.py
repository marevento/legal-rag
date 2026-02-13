"""LangChain LCEL alternative RAG implementation.

Demonstrates the same pipeline using LangChain abstractions.
Switchable via RAG_APPROACH=langchain env var.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import AsyncGenerator

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from jinja2 import Environment, FileSystemLoader
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import AzureChatOpenAI
from openai import AsyncAzureOpenAI

import config
from approaches.approach import Approach
from models.chat import (
    ChatRequest,
    ChatResponse,
    ChatResponseDelta,
    StructuredLLMOutput,
)
from models.norm import NormReference
from postprocessing.citation_injection import inject_citations, norm_cache
from postprocessing.source_validation import validate_cited_sources

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"
jinja_env = Environment(loader=FileSystemLoader(str(PROMPTS_DIR)), autoescape=False)


class ChatLangChainApproach(Approach):
    """LangChain LCEL implementation of the RAG pipeline."""

    def __init__(
        self,
        openai_client: AsyncAzureOpenAI,
        search_client: SearchClient,
    ) -> None:
        self.openai_client = openai_client
        self.search_client = search_client

        # LangChain LLM for generation
        self.llm = AzureChatOpenAI(
            azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
            api_key=config.AZURE_OPENAI_API_KEY,
            api_version=config.AZURE_OPENAI_API_VERSION,
            azure_deployment=config.AZURE_OPENAI_CHAT_DEPLOYMENT,
            temperature=0,
        )

        # LangChain LLM for query rewrite (mini model)
        self.llm_mini = AzureChatOpenAI(
            azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
            api_key=config.AZURE_OPENAI_API_KEY,
            api_version=config.AZURE_OPENAI_API_VERSION,
            azure_deployment=config.AZURE_OPENAI_CHAT_MINI_DEPLOYMENT,
            temperature=0,
        )

        self.output_parser = PydanticOutputParser(pydantic_object=StructuredLLMOutput)

    async def run(self, request: ChatRequest) -> ChatResponse:
        timer = self._timer()
        user_query = request.messages[-1].content

        # Stage 1: Query rewrite via LCEL
        timer.start("query_rewrite")
        rewrite_prompt = ChatPromptTemplate.from_template(
            jinja_env.get_template("query_rewrite.jinja2").render(query="{query}")
        )
        rewrite_chain = rewrite_prompt | self.llm_mini
        rewrite_result = await rewrite_chain.ainvoke({"query": user_query})
        rewritten_query = rewrite_result.content.strip()
        timer.stop()

        # Stage 2: Retrieve (using Azure SDK directly — LangChain retriever is a wrapper)
        timer.start("retrieval")
        sources = self._search(rewritten_query, request.search_strategy, request.top_k)
        timer.stop()

        if not sources:
            return ChatResponse(
                answer="Zu dieser Frage wurden keine relevanten Mietrecht-Normen gefunden.",
                sources=[],
                confidence="low",
                search_strategy=request.search_strategy,
                approach="langchain",
            )

        # Stage 3: Generate via LCEL chain with structured output
        timer.start("generation")
        system_template = jinja_env.get_template("chat_system.jinja2")
        system_content = system_template.render(sources=sources)

        chat_prompt = ChatPromptTemplate.from_messages([
            ("system", system_content),
            ("human", "{question}"),
        ])

        # Use LCEL chain: prompt -> LLM -> parse
        chain = chat_prompt | self.llm | self.output_parser
        llm_output: StructuredLLMOutput = await chain.ainvoke({"question": user_query})
        timer.stop()

        # Stage 4: Same post-processing as custom approach
        timer.start("postprocessing")
        valid_indices = validate_cited_sources(llm_output.cited_sources, sources)
        answer = inject_citations(llm_output.explanation, sources)
        cited_sources = [s for i, s in enumerate(sources, 1) if i in valid_indices]
        timer.stop()

        logger.info("LangChain pipeline completed in %.0fms", timer.total_ms)

        return ChatResponse(
            answer=answer,
            sources=cited_sources,
            confidence=llm_output.confidence,
            search_strategy=request.search_strategy,
            approach="langchain",
        )

    async def run_stream(self, request: ChatRequest) -> AsyncGenerator[ChatResponseDelta, None]:
        """Streaming — same as custom approach, full then stream."""
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

    def _search(
        self,
        query: str,
        strategy: str = "hybrid",
        top_k: int = 5,
    ) -> list[NormReference]:
        """Search using Azure SDK (same as custom approach)."""
        from azure.search.documents.models import VectorizableTextQuery

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
        return sources
