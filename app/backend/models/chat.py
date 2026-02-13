"""Chat request/response models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from models.norm import NormReference


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    search_strategy: str = Field(default="hybrid", description="bm25, vector, or hybrid")
    temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    top_k: int = Field(default=5, ge=1, le=20)
    use_semantic_ranker: bool = False
    approach: str = Field(default="custom", description="custom or langchain")


class StructuredLLMOutput(BaseModel):
    """JSON schema enforced on GPT-4o via structured output.

    The LLM must use [1][2] markers and never reproduce norm text.
    """

    explanation: str = Field(description="Answer with [1][2] citation markers. Do NOT include norm text.")
    cited_sources: list[int] = Field(description="List of source numbers actually cited, e.g. [1, 2]")
    confidence: Literal["high", "medium", "low"] = Field(description="Confidence in the answer")


class ChatResponse(BaseModel):
    """Final response after post-processing."""

    answer: str = Field(description="Answer with injected verbatim norm text")
    sources: list[NormReference] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"
    search_strategy: str = "hybrid"
    approach: str = "custom"


class ChatResponseDelta(BaseModel):
    """Streaming delta for SSE."""

    delta: str = ""
    sources: list[NormReference] | None = None
    confidence: Literal["high", "medium", "low"] | None = None
    done: bool = False
