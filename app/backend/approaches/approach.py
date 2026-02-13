"""Abstract base class for RAG approaches."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import AsyncGenerator

from models.chat import ChatRequest, ChatResponse, ChatResponseDelta


class Approach(ABC):
    """Base class for RAG approaches (custom, langchain, etc.)."""

    @abstractmethod
    async def run(self, request: ChatRequest) -> ChatResponse:
        """Execute the full RAG pipeline and return a complete response."""
        ...

    @abstractmethod
    async def run_stream(self, request: ChatRequest) -> AsyncGenerator[ChatResponseDelta, None]:
        """Execute the RAG pipeline with streaming output."""
        ...
        # Make this a generator
        yield  # type: ignore[misc]  # pragma: no cover

    @staticmethod
    def _timer() -> "_Timer":
        return _Timer()


class _Timer:
    """Simple context manager for timing pipeline stages."""

    def __init__(self) -> None:
        self.stages: dict[str, float] = {}
        self._start: float = 0.0
        self._current_stage: str = ""

    def start(self, stage: str) -> "_Timer":
        self._current_stage = stage
        self._start = time.perf_counter()
        return self

    def stop(self) -> float:
        elapsed = (time.perf_counter() - self._start) * 1000  # ms
        self.stages[self._current_stage] = elapsed
        return elapsed

    @property
    def total_ms(self) -> float:
        return sum(self.stages.values())
