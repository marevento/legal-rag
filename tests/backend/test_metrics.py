"""Tests for evaluation metrics."""

from evaluation.metrics import compute_citation_accuracy, compute_retrieval_metrics


def test_perfect_recall():
    result = compute_retrieval_metrics(
        retrieved_norm_ids=["bgb-535", "bgb-556", "bgb-573"],
        expected_norm_ids=["bgb-535", "bgb-556"],
        k=5,
    )
    assert result.recall_at_k == 1.0


def test_partial_recall():
    result = compute_retrieval_metrics(
        retrieved_norm_ids=["bgb-535", "bgb-540"],
        expected_norm_ids=["bgb-535", "bgb-556"],
        k=5,
    )
    assert result.recall_at_k == 0.5


def test_zero_recall():
    result = compute_retrieval_metrics(
        retrieved_norm_ids=["bgb-540", "bgb-541"],
        expected_norm_ids=["bgb-535", "bgb-556"],
        k=5,
    )
    assert result.recall_at_k == 0.0


def test_precision():
    result = compute_retrieval_metrics(
        retrieved_norm_ids=["bgb-535", "bgb-540", "bgb-556", "bgb-541", "bgb-542"],
        expected_norm_ids=["bgb-535", "bgb-556"],
        k=5,
    )
    assert result.precision_at_k == 0.4


def test_citation_accuracy_all_correct():
    acc = compute_citation_accuracy(["bgb-535", "bgb-556"], ["bgb-535", "bgb-556", "bgb-573"])
    assert acc == 1.0


def test_citation_accuracy_partial():
    acc = compute_citation_accuracy(["bgb-535", "bgb-999"], ["bgb-535", "bgb-556"])
    assert acc == 0.5


def test_citation_accuracy_empty():
    acc = compute_citation_accuracy([], ["bgb-535"])
    assert acc == 0.0
