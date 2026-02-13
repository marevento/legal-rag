"""Evaluation models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class GoldenExample(BaseModel):
    """A single evaluation example from the golden dataset."""

    question: str
    category: str = Field(description="simple_technical, colloquial, multi_part, definition, complex")
    expected_norm_ids: list[str] = Field(description="e.g. ['bgb-535', 'bgb-536']")
    expected_answer_contains: list[str] = Field(default_factory=list, description="Key phrases expected in answer")


class RetrievalMetrics(BaseModel):
    recall_at_k: float = 0.0
    precision_at_k: float = 0.0
    k: int = 5
    retrieved_norm_ids: list[str] = Field(default_factory=list)
    expected_norm_ids: list[str] = Field(default_factory=list)


class GenerationMetrics(BaseModel):
    groundedness_score: float = Field(default=0.0, description="0-1 score from LLM-as-judge")
    citation_accuracy: float = Field(default=0.0, description="Fraction of citations that are valid")
    confidence: str = "medium"


class EvalResult(BaseModel):
    """Result for a single evaluation example."""

    question: str
    category: str
    retrieval: RetrievalMetrics
    generation: GenerationMetrics
    search_strategy: str
    latency_ms: float = 0.0
    latency_breakdown: dict[str, float] = Field(default_factory=dict)


class StrategyComparison(BaseModel):
    strategy: str
    avg_recall_at_5: float = 0.0
    avg_precision_at_5: float = 0.0
    avg_groundedness: float = 0.0
    avg_citation_accuracy: float = 0.0
    avg_latency_ms: float = 0.0


class PatternRecommendation(BaseModel):
    """Whether a RAG pattern is recommended based on eval metrics."""

    pattern: str
    signal: str
    metric_name: str
    current_value: float
    threshold: float
    recommended: bool
    explanation: str


class MetricsReport(BaseModel):
    """Full evaluation report."""

    results: list[EvalResult] = Field(default_factory=list)
    strategy_comparisons: list[StrategyComparison] = Field(default_factory=list)
    pattern_recommendations: list[PatternRecommendation] = Field(default_factory=list)
    results_by_category: dict[str, list[EvalResult]] = Field(default_factory=dict)
