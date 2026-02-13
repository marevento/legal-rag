"""Strategy comparison utilities for the evaluation dashboard."""

from __future__ import annotations

from models.evaluation import EvalResult, StrategyComparison


def compare_strategies(results: list[EvalResult]) -> dict[str, StrategyComparison]:
    """Build a strategy-keyed comparison from evaluation results."""
    by_strategy: dict[str, list[EvalResult]] = {}
    for r in results:
        by_strategy.setdefault(r.search_strategy, []).append(r)

    comparisons = {}
    for strategy, strategy_results in by_strategy.items():
        n = len(strategy_results)
        comparisons[strategy] = StrategyComparison(
            strategy=strategy,
            avg_recall_at_5=sum(r.retrieval.recall_at_k for r in strategy_results) / n,
            avg_precision_at_5=sum(r.retrieval.precision_at_k for r in strategy_results) / n,
            avg_groundedness=sum(r.generation.groundedness_score for r in strategy_results) / n,
            avg_citation_accuracy=sum(r.generation.citation_accuracy for r in strategy_results) / n,
            avg_latency_ms=sum(r.latency_ms for r in strategy_results) / n,
        )
    return comparisons


def format_comparison_table(comparisons: dict[str, StrategyComparison]) -> str:
    """Format strategy comparisons as a markdown table."""
    header = "| Strategy | Recall@5 | Precision@5 | Groundedness | Citation Acc. | Latency (ms) |"
    sep = "|----------|----------|-------------|--------------|---------------|--------------|"
    rows = [header, sep]
    for comp in comparisons.values():
        rows.append(
            f"| {comp.strategy:<8} | {comp.avg_recall_at_5:.3f}    | {comp.avg_precision_at_5:.3f}       "
            f"| {comp.avg_groundedness:.3f}        | {comp.avg_citation_accuracy:.3f}         | {comp.avg_latency_ms:.0f}          |"
        )
    return "\n".join(rows)
