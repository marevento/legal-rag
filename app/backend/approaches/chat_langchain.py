"""LangChain LCEL alternative RAG implementation.

Demonstrates the same pipeline using LangChain abstractions.
Switchable via RAG_APPROACH=langchain env var.
"""

from __future__ import annotations

import logging
from pathlib import Path

from azure.search.documents import SearchClient
from jinja2 import Environment, FileSystemLoader
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_openai import AzureChatOpenAI
from openai import AsyncAzureOpenAI

import config
from approaches.approach import Approach
from models.chat import (
    ChatRequest,
    ChatResponse,
    StructuredLLMOutput,
)
from postprocessing.citation_injection import inject_citations
from postprocessing.source_validation import validate_cited_sources

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"
jinja_env = Environment(loader=FileSystemLoader(str(PROMPTS_DIR)), autoescape=True)


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
        past_messages = request.messages[:-1]

        # Stage 1: Query rewrite via LCEL (with conversation history)
        timer.start("query_rewrite")
        rewrite_template = jinja_env.get_template("query_rewrite.jinja2").render(
            query=user_query, past_messages=past_messages,
        )
        rewrite_prompt = ChatPromptTemplate.from_messages([("human", rewrite_template)])
        rewrite_chain = rewrite_prompt | self.llm_mini
        rewrite_result = await rewrite_chain.ainvoke({})
        rewritten_query = (rewrite_result.content or "").strip() or user_query
        timer.stop()

        # Stage 2: Retrieve (using shared _search_async from base class)
        timer.start("retrieval")
        sources = await self._search_async(rewritten_query, request.search_strategy, request.top_k)
        timer.stop()

        if not sources:
            return ChatResponse(
                answer="Zu dieser Frage wurden keine relevanten Mietrecht-Normen gefunden.",
                sources=[],
                confidence="low",
                search_strategy=request.search_strategy,
                approach="langchain",
            )

        # Stage 3: Generate via LCEL chain with structured output (with conversation history)
        timer.start("generation")
        system_template = jinja_env.get_template("chat_system.jinja2")
        system_content = system_template.render(sources=sources)

        # Build messages: system + past conversation + current question
        prompt_messages: list[tuple[str, str]] = [("system", system_content)]
        for msg in past_messages:
            prompt_messages.append((msg.role, msg.content))
        prompt_messages.append(("human", "{question}"))

        chat_prompt = ChatPromptTemplate.from_messages(prompt_messages)

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

        logger.info(
            "RAG pipeline completed",
            extra={
                "custom_dimensions": {
                    "approach": "langchain",
                    "total_ms": round(timer.total_ms),
                    "query_rewrite_ms": round(timer.stages.get("query_rewrite", 0)),
                    "retrieval_ms": round(timer.stages.get("retrieval", 0)),
                    "generation_ms": round(timer.stages.get("generation", 0)),
                    "postprocessing_ms": round(timer.stages.get("postprocessing", 0)),
                    "search_strategy": request.search_strategy,
                    "sources_retrieved": len(sources),
                    "sources_cited": len(valid_indices),
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
            approach="langchain",
        )

    # run_stream inherited from Approach base class

    # _search inherited from ChatRAGApproach — both approaches share the same search_client
