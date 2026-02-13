"""Run evaluation suite against the golden dataset."""

from __future__ import annotations

import itertools
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncGenerator

from openai import AsyncAzureOpenAI

import config
from approaches.approach import Approach
from evaluation.metrics import (
    compute_citation_accuracy,
    compute_groundedness,
    compute_retrieval_metrics,
)
from models.chat import ChatMessage, ChatRequest
from models.evaluation import (
    EvalResult,
    GenerationMetrics,
    GoldenExample,
    MetricsReport,
    PatternRecommendation,
    StrategyComparison,
)

logger = logging.getLogger(__name__)


@dataclass
class EvalConfig:
    """A single evaluation configuration to test."""
    search_strategy: str
    query_transform: str = "none"
    decompose: bool = False

    @property
    def label(self) -> str:
        parts = [self.search_strategy]
        if self.query_transform != "none":
            parts.append(self.query_transform)
        if self.decompose:
            parts.append("decompose")
        return "+".join(parts)


@dataclass
class EvalProgress:
    """Progress update during evaluation."""
    completed: int
    total: int
    config_label: str
    question: str
    status: str = "running"  # "running", "throttled", "complete"


def load_golden_dataset(path: Path) -> list[GoldenExample]:
    """Load golden dataset from JSONL file."""
    examples = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                examples.append(GoldenExample.model_validate_json(line))
    logger.info("Loaded %d golden examples from %s", len(examples), path)
    return examples


def _build_configs(
    strategies: list[str],
    query_transforms: list[str],
    decompose_options: list[bool],
) -> list[EvalConfig]:
    """Build all evaluation config combinations."""
    return [
        EvalConfig(search_strategy=s, query_transform=qt, decompose=d)
        for s, qt, d in itertools.product(strategies, query_transforms, decompose_options)
    ]


async def run_evaluation(
    approach: Approach,
    openai_client: AsyncAzureOpenAI,
    examples: list[GoldenExample],
    strategies: list[str] | None = None,
    query_transforms: list[str] | None = None,
    decompose_options: list[bool] | None = None,
    top_k: int = 5,
) -> MetricsReport:
    """Run full evaluation suite across all config combinations."""
    configs = _build_configs(
        strategies or ["bm25", "vector", "hybrid"],
        query_transforms or ["none"],
        decompose_options or [False],
    )

    all_results: list[EvalResult] = []

    for cfg in configs:
        logger.info("Evaluating config: %s", cfg.label)
        for example in examples:
            result = await _evaluate_single(
                approach=approach,
                openai_client=openai_client,
                example=example,
                cfg=cfg,
                top_k=top_k,
            )
            all_results.append(result)

    config_labels = [c.label for c in configs]
    strategy_comparisons = _compute_strategy_comparisons(all_results, config_labels)
    results_by_category = _group_by_category(all_results)
    pattern_recommendations = _compute_pattern_recommendations(all_results, results_by_category)

    return MetricsReport(
        results=all_results,
        strategy_comparisons=strategy_comparisons,
        pattern_recommendations=pattern_recommendations,
        results_by_category={k: v for k, v in results_by_category.items()},
    )


async def run_evaluation_stream(
    approach: Approach,
    openai_client: AsyncAzureOpenAI,
    examples: list[GoldenExample],
    strategies: list[str] | None = None,
    query_transforms: list[str] | None = None,
    decompose_options: list[bool] | None = None,
    top_k: int = 5,
) -> AsyncGenerator[EvalProgress | MetricsReport, None]:
    """Streaming variant that yields progress updates."""
    configs = _build_configs(
        strategies or ["bm25", "vector", "hybrid"],
        query_transforms or ["none"],
        decompose_options or [False],
    )

    total = len(configs) * len(examples)
    completed = 0
    all_results: list[EvalResult] = []

    for cfg in configs:
        logger.info("Evaluating config: %s", cfg.label)
        for example in examples:
            yield EvalProgress(
                completed=completed,
                total=total,
                config_label=cfg.label,
                question=example.question,
            )

            start = time.perf_counter()
            result = await _evaluate_single(
                approach=approach,
                openai_client=openai_client,
                example=example,
                cfg=cfg,
                top_k=top_k,
            )
            elapsed = time.perf_counter() - start

            all_results.append(result)
            completed += 1

            if elapsed > 10:
                yield EvalProgress(
                    completed=completed,
                    total=total,
                    config_label=cfg.label,
                    question=example.question,
                    status="throttled",
                )

    config_labels = [c.label for c in configs]
    strategy_comparisons = _compute_strategy_comparisons(all_results, config_labels)
    results_by_category = _group_by_category(all_results)
    pattern_recommendations = _compute_pattern_recommendations(all_results, results_by_category)

    yield MetricsReport(
        results=all_results,
        strategy_comparisons=strategy_comparisons,
        pattern_recommendations=pattern_recommendations,
        results_by_category={k: v for k, v in results_by_category.items()},
    )


async def _evaluate_single(
    approach: Approach,
    openai_client: AsyncAzureOpenAI,
    example: GoldenExample,
    cfg: EvalConfig,
    top_k: int,
) -> EvalResult:
    """Evaluate a single example with a given config."""
    request = ChatRequest(
        messages=[ChatMessage(role="user", content=example.question)],
        search_strategy=cfg.search_strategy,
        query_transform=cfg.query_transform,
        decompose=cfg.decompose,
        top_k=top_k,
        temperature=0,
    )

    start = time.perf_counter()
    response = await approach.run(request)
    total_ms = (time.perf_counter() - start) * 1000

    # Compute retrieval metrics
    retrieved_ids = [s.norm_id for s in response.sources]
    retrieval = compute_retrieval_metrics(retrieved_ids, example.expected_norm_ids, k=top_k)

    # Compute citation accuracy
    cited_ids = [s.norm_id for s in response.sources]
    citation_acc = compute_citation_accuracy(cited_ids, example.expected_norm_ids)

    # Compute groundedness
    sources_text = [s.text for s in response.sources]
    groundedness = await compute_groundedness(
        response.answer,
        sources_text,
        openai_client,
        config.AZURE_OPENAI_CHAT_MINI_DEPLOYMENT,
    )

    generation = GenerationMetrics(
        groundedness_score=groundedness,
        citation_accuracy=citation_acc,
        confidence=response.confidence,
    )

    return EvalResult(
        question=example.question,
        category=example.category,
        retrieval=retrieval,
        generation=generation,
        search_strategy=cfg.search_strategy,
        query_transform=cfg.query_transform,
        decompose=cfg.decompose,
        latency_ms=total_ms,
    )


def _compute_strategy_comparisons(
    results: list[EvalResult],
    config_labels: list[str],
) -> list[StrategyComparison]:
    """Aggregate metrics per config combination."""
    comparisons = []
    for label in config_labels:
        matching = [r for r in results if r.config_label == label]
        if not matching:
            continue

        n = len(matching)
        comparisons.append(
            StrategyComparison(
                strategy=label,
                avg_recall_at_5=sum(r.retrieval.recall_at_k for r in matching) / n,
                avg_precision_at_5=sum(r.retrieval.precision_at_k for r in matching) / n,
                avg_groundedness=sum(r.generation.groundedness_score for r in matching) / n,
                avg_citation_accuracy=sum(r.generation.citation_accuracy for r in matching) / n,
                avg_latency_ms=sum(r.latency_ms for r in matching) / n,
            )
        )
    return comparisons


def _group_by_category(results: list[EvalResult]) -> dict[str, list[EvalResult]]:
    """Group results by query category."""
    groups: dict[str, list[EvalResult]] = defaultdict(list)
    for r in results:
        groups[r.category].append(r)
    return dict(groups)


def _compute_pattern_recommendations(
    all_results: list[EvalResult],
    by_category: dict[str, list[EvalResult]],
) -> list[PatternRecommendation]:
    """Compute pattern recommendations based on evaluation metrics."""
    recommendations = []

    # 1. Query rewrite: compare hybrid vs hybrid+rewrite on colloquial queries
    colloquial = by_category.get("colloquial", [])
    if colloquial:
        baseline = [r for r in colloquial if r.config_label == "hybrid"]
        rewrite = [r for r in colloquial if r.config_label == "hybrid+rewrite"]
        if baseline:
            base_recall = sum(r.retrieval.recall_at_k for r in baseline) / len(baseline)
            rewrite_recall = sum(r.retrieval.recall_at_k for r in rewrite) / len(rewrite) if rewrite else None
            explanation = f"Baseline colloquial recall is {base_recall:.1%}."
            if rewrite_recall is not None:
                delta = rewrite_recall - base_recall
                explanation += f" With rewrite: {rewrite_recall:.1%} ({delta:+.1%})."
                explanation += " Rewrite improves recall." if delta > 0 else " Rewrite does not improve recall."
            else:
                explanation += " Enable 'rewrite' in eval to compare."
            recommendations.append(
                PatternRecommendation(
                    pattern="Query Rewrite",
                    signal="Colloquial query recall improvement with rewrite",
                    metric_name="avg_recall_at_5_colloquial",
                    current_value=round(rewrite_recall or base_recall, 3),
                    threshold=0.7,
                    recommended=base_recall < 0.7,
                    explanation=explanation,
                )
            )

    # 2. HyDE: compare hybrid vs hybrid+hyde on colloquial queries
    if colloquial:
        baseline = [r for r in colloquial if r.config_label == "hybrid"]
        hyde = [r for r in colloquial if r.config_label == "hybrid+hyde"]
        if baseline:
            base_recall = sum(r.retrieval.recall_at_k for r in baseline) / len(baseline)
            hyde_recall = sum(r.retrieval.recall_at_k for r in hyde) / len(hyde) if hyde else None
            explanation = f"Baseline colloquial recall is {base_recall:.1%}."
            if hyde_recall is not None:
                delta = hyde_recall - base_recall
                explanation += f" With HyDE: {hyde_recall:.1%} ({delta:+.1%})."
                explanation += " HyDE improves recall." if delta > 0 else " HyDE does not improve recall."
            else:
                explanation += " Enable 'hyde' in eval to compare."
            recommendations.append(
                PatternRecommendation(
                    pattern="HyDE (Hypothetical Document Embeddings)",
                    signal="Colloquial query recall improvement with HyDE",
                    metric_name="avg_recall_at_5_colloquial_hyde",
                    current_value=round(hyde_recall or base_recall, 3),
                    threshold=0.7,
                    recommended=base_recall < 0.7,
                    explanation=explanation,
                )
            )

    # 3. Query decomposition: compare with and without on multi-part queries
    multi_part = by_category.get("multi_part", [])
    if multi_part:
        baseline = [r for r in multi_part if r.config_label == "hybrid"]
        decomposed = [r for r in multi_part if r.config_label == "hybrid+decompose"]
        if baseline:
            base_recall = sum(r.retrieval.recall_at_k for r in baseline) / len(baseline)
            decomp_recall = sum(r.retrieval.recall_at_k for r in decomposed) / len(decomposed) if decomposed else None
            explanation = f"Baseline multi-part recall is {base_recall:.1%}."
            if decomp_recall is not None:
                delta = decomp_recall - base_recall
                explanation += f" With decomposition: {decomp_recall:.1%} ({delta:+.1%})."
                explanation += " Decomposition improves recall." if delta > 0 else " Decomposition does not improve recall."
            else:
                explanation += " Enable 'decompose' in eval to compare."
            recommendations.append(
                PatternRecommendation(
                    pattern="Query Decomposition",
                    signal="Multi-part query recall improvement with decomposition",
                    metric_name="avg_recall_at_5_multi_part",
                    current_value=round(decomp_recall or base_recall, 3),
                    threshold=0.6,
                    recommended=base_recall < 0.6,
                    explanation=explanation,
                )
            )

    return recommendations
