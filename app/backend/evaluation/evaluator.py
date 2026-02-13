"""Run evaluation suite against the golden dataset."""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass
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
class EvalProgress:
    """Progress update during evaluation."""
    completed: int
    total: int
    strategy: str
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


async def run_evaluation(
    approach: Approach,
    openai_client: AsyncAzureOpenAI,
    examples: list[GoldenExample],
    strategies: list[str] | None = None,
    top_k: int = 5,
) -> MetricsReport:
    """Run full evaluation suite.

    Args:
        approach: RAG approach to evaluate.
        openai_client: For groundedness scoring.
        examples: Golden dataset examples.
        strategies: Search strategies to compare (default: all three).
        top_k: Number of results for retrieval metrics.

    Returns:
        Complete metrics report.
    """
    if strategies is None:
        strategies = ["bm25", "vector", "hybrid"]

    all_results: list[EvalResult] = []

    for strategy in strategies:
        logger.info("Evaluating strategy: %s", strategy)
        for example in examples:
            result = await _evaluate_single(
                approach=approach,
                openai_client=openai_client,
                example=example,
                strategy=strategy,
                top_k=top_k,
            )
            all_results.append(result)

    # Compute aggregated metrics
    strategy_comparisons = _compute_strategy_comparisons(all_results, strategies)
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
    top_k: int = 5,
) -> AsyncGenerator[EvalProgress | MetricsReport, None]:
    """Streaming variant that yields progress updates."""
    if strategies is None:
        strategies = ["bm25", "vector", "hybrid"]

    total = len(strategies) * len(examples)
    completed = 0
    all_results: list[EvalResult] = []

    for strategy in strategies:
        logger.info("Evaluating strategy: %s", strategy)
        for example in examples:
            yield EvalProgress(
                completed=completed,
                total=total,
                strategy=strategy,
                question=example.question,
            )

            start = time.perf_counter()
            result = await _evaluate_single(
                approach=approach,
                openai_client=openai_client,
                example=example,
                strategy=strategy,
                top_k=top_k,
            )
            elapsed = time.perf_counter() - start

            all_results.append(result)
            completed += 1

            # Detect throttling: if a single eval took >10s, it likely hit rate limits
            if elapsed > 10:
                yield EvalProgress(
                    completed=completed,
                    total=total,
                    strategy=strategy,
                    question=example.question,
                    status="throttled",
                )

    # Compute aggregated metrics
    strategy_comparisons = _compute_strategy_comparisons(all_results, strategies)
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
    strategy: str,
    top_k: int,
) -> EvalResult:
    """Evaluate a single example."""
    request = ChatRequest(
        messages=[ChatMessage(role="user", content=example.question)],
        search_strategy=strategy,
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
        search_strategy=strategy,
        latency_ms=total_ms,
    )


def _compute_strategy_comparisons(
    results: list[EvalResult],
    strategies: list[str],
) -> list[StrategyComparison]:
    """Aggregate metrics per strategy."""
    comparisons = []
    for strategy in strategies:
        strategy_results = [r for r in results if r.search_strategy == strategy]
        if not strategy_results:
            continue

        n = len(strategy_results)
        comparisons.append(
            StrategyComparison(
                strategy=strategy,
                avg_recall_at_5=sum(r.retrieval.recall_at_k for r in strategy_results) / n,
                avg_precision_at_5=sum(r.retrieval.precision_at_k for r in strategy_results) / n,
                avg_groundedness=sum(r.generation.groundedness_score for r in strategy_results) / n,
                avg_citation_accuracy=sum(r.generation.citation_accuracy for r in strategy_results) / n,
                avg_latency_ms=sum(r.latency_ms for r in strategy_results) / n,
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

    # 1. Query rewrite: check colloquial recall
    colloquial = by_category.get("colloquial", [])
    if colloquial:
        hybrid_colloquial = [r for r in colloquial if r.search_strategy == "hybrid"]
        if hybrid_colloquial:
            avg_recall = sum(r.retrieval.recall_at_k for r in hybrid_colloquial) / len(hybrid_colloquial)
            recommendations.append(
                PatternRecommendation(
                    pattern="Query Rewrite",
                    signal="Low Recall@5 on colloquial queries",
                    metric_name="avg_recall_at_5_colloquial",
                    current_value=round(avg_recall, 3),
                    threshold=0.7,
                    recommended=avg_recall < 0.7,
                    explanation=(
                        f"Colloquial query recall is {avg_recall:.1%}. "
                        + ("Below 70% threshold — query rewrite recommended." if avg_recall < 0.7 else "Above threshold — not yet needed.")
                    ),
                )
            )

    # 2. HyDE: check vector vs BM25 gap on colloquial
    if colloquial:
        vector_coll = [r for r in colloquial if r.search_strategy == "vector"]
        bm25_coll = [r for r in colloquial if r.search_strategy == "bm25"]
        if vector_coll and bm25_coll:
            vec_recall = sum(r.retrieval.recall_at_k for r in vector_coll) / len(vector_coll)
            bm25_recall = sum(r.retrieval.recall_at_k for r in bm25_coll) / len(bm25_coll)
            gap = bm25_recall - vec_recall
            recommendations.append(
                PatternRecommendation(
                    pattern="HyDE (Hypothetical Document Embeddings)",
                    signal="Vector search underperforms BM25 on colloquial queries",
                    metric_name="bm25_vector_recall_gap_colloquial",
                    current_value=round(gap, 3),
                    threshold=0.15,
                    recommended=gap > 0.15,
                    explanation=(
                        f"BM25-vector recall gap is {gap:.1%}. "
                        + ("Above 15% — HyDE recommended." if gap > 0.15 else "Below threshold — not yet needed.")
                    ),
                )
            )

    # 3. Query decomposition: check multi_part recall
    multi_part = by_category.get("multi_part", [])
    if multi_part:
        hybrid_mp = [r for r in multi_part if r.search_strategy == "hybrid"]
        if hybrid_mp:
            avg_recall = sum(r.retrieval.recall_at_k for r in hybrid_mp) / len(hybrid_mp)
            recommendations.append(
                PatternRecommendation(
                    pattern="Query Decomposition",
                    signal="Low Recall@5 on multi-part queries",
                    metric_name="avg_recall_at_5_multi_part",
                    current_value=round(avg_recall, 3),
                    threshold=0.6,
                    recommended=avg_recall < 0.6,
                    explanation=(
                        f"Multi-part query recall is {avg_recall:.1%}. "
                        + ("Below 60% — decomposition recommended." if avg_recall < 0.6 else "Above threshold — not yet needed.")
                    ),
                )
            )

    # 4. Semantic ranker: check precision vs recall gap
    hybrid_results = [r for r in all_results if r.search_strategy == "hybrid"]
    if hybrid_results:
        avg_recall = sum(r.retrieval.recall_at_k for r in hybrid_results) / len(hybrid_results)
        avg_precision = sum(r.retrieval.precision_at_k for r in hybrid_results) / len(hybrid_results)
        gap = avg_recall - avg_precision
        recommendations.append(
            PatternRecommendation(
                pattern="Semantic Ranker",
                signal="Good recall but poor precision (recall-precision gap)",
                metric_name="recall_precision_gap_hybrid",
                current_value=round(gap, 3),
                threshold=0.2,
                recommended=gap > 0.2,
                explanation=(
                    f"Recall-precision gap is {gap:.1%}. "
                    + ("Above 20% — semantic ranker recommended." if gap > 0.2 else "Below threshold — not yet needed.")
                ),
            )
        )

    return recommendations
