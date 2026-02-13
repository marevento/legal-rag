"""Retrieval and generation metrics for evaluation."""

from __future__ import annotations

import logging

from models.evaluation import GenerationMetrics, RetrievalMetrics

logger = logging.getLogger(__name__)


def compute_retrieval_metrics(
    retrieved_norm_ids: list[str],
    expected_norm_ids: list[str],
    k: int = 5,
) -> RetrievalMetrics:
    """Compute Recall@K and Precision@K for a single query.

    Args:
        retrieved_norm_ids: Norm IDs returned by search (ordered by relevance).
        expected_norm_ids: Ground-truth norm IDs from golden dataset.
        k: Number of top results to consider.
    """
    top_k = set(retrieved_norm_ids[:k])
    expected = set(expected_norm_ids)

    if not expected:
        return RetrievalMetrics(
            recall_at_k=1.0,
            precision_at_k=1.0 if not top_k else 0.0,
            k=k,
            retrieved_norm_ids=retrieved_norm_ids[:k],
            expected_norm_ids=expected_norm_ids,
        )

    hits = top_k & expected
    recall = len(hits) / len(expected) if expected else 0.0
    precision = len(hits) / len(top_k) if top_k else 0.0

    return RetrievalMetrics(
        recall_at_k=recall,
        precision_at_k=precision,
        k=k,
        retrieved_norm_ids=retrieved_norm_ids[:k],
        expected_norm_ids=expected_norm_ids,
    )


def compute_citation_accuracy(
    cited_norm_ids: list[str],
    expected_norm_ids: list[str],
) -> float:
    """Fraction of cited norms that are in the expected set."""
    if not cited_norm_ids:
        return 0.0
    expected = set(expected_norm_ids)
    correct = sum(1 for nid in cited_norm_ids if nid in expected)
    return correct / len(cited_norm_ids)


async def compute_groundedness(
    answer: str,
    sources_text: list[str],
    openai_client,
    deployment: str,
) -> float:
    """LLM-as-judge groundedness scoring.

    Asks GPT-4o-mini to score how well the answer is grounded in the sources.
    Returns a score between 0.0 and 1.0.
    """
    sources_combined = "\n\n---\n\n".join(sources_text)

    prompt = f"""Bewerte, wie gut die folgende Antwort durch die bereitgestellten Quellen belegt ist.

Quellen:
{sources_combined}

Antwort:
{answer}

Bewerte auf einer Skala von 0 bis 10:
- 10: Jede Aussage ist vollständig durch die Quellen belegt
- 5: Einige Aussagen sind belegt, andere nicht
- 0: Die Antwort hat keinen Bezug zu den Quellen

Antworte NUR mit einer Zahl zwischen 0 und 10."""

    try:
        response = await openai_client.chat.completions.create(
            model=deployment,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=10,
        )
        score_text = response.choices[0].message.content.strip()
        score = float(score_text) / 10.0
        return max(0.0, min(1.0, score))
    except Exception:
        logger.warning("Groundedness scoring failed", exc_info=True)
        return 0.0
