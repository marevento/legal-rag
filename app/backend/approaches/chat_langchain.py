"""LangChain LCEL alternative RAG implementation.

Demonstrates the same pipeline using LangChain abstractions.
Switchable via RAG_APPROACH=langchain env var.
"""

from __future__ import annotations

import logging
from pathlib import Path

from azure.search.documents import SearchClient
from jinja2 import Environment, FileSystemLoader
from langchain_core.prompts import ChatPromptTemplate
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
        super().__init__()
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

        self.output_parser = PydanticOutputParser(pydantic_object=StructuredLLMOutput)

    async def run(self, request: ChatRequest) -> ChatResponse:
        timer = self._timer()
        user_query = request.messages[-1].content
        past_messages = request.messages[:-1]

        # Stage 1+2: Query transform + retrieval (shared with custom approach)
        timer.start("retrieval")
        sources = await self._retrieve(user_query, request, self.openai_client, past_messages)
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
        # Escape curly braces so LangChain doesn't treat them as template variables
        system_content = system_content.replace("{", "{{").replace("}", "}}")

        # Build messages: system + past conversation + current question
        prompt_messages: list[tuple[str, str]] = [("system", system_content)]
        for msg in past_messages:
            prompt_messages.append((msg.role, msg.content.replace("{", "{{").replace("}", "}}")))
        prompt_messages.append(("human", "{question}"))

        chat_prompt = ChatPromptTemplate.from_messages(prompt_messages)

        # Use LCEL chain: prompt -> LLM -> parse
        chain = chat_prompt | self.llm | self.output_parser
        llm_output: StructuredLLMOutput = await chain.ainvoke({"question": user_query})
        timer.stop()

        # Stage 4: Same post-processing as custom approach
        timer.start("postprocessing")
        answer, cited_sources = self._postprocess(
            llm_output.explanation, llm_output.cited_sources, sources
        )
        timer.stop()

        logger.info(
            "RAG pipeline completed",
            extra={
                "custom_dimensions": {
                    "approach": "langchain",
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
            approach="langchain",
        )

    # run_stream inherited from Approach base class

    # _search inherited from ChatRAGApproach — both approaches share the same search_client
