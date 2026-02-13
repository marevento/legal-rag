"""Tests for source validation."""

from models.norm import NormReference
from postprocessing.source_validation import filter_sources_to_cited, validate_cited_sources


def test_validate_all_valid(sample_norm_references):
    result = validate_cited_sources([1, 2, 3], sample_norm_references)
    assert result == [1, 2, 3]


def test_validate_drops_invalid(sample_norm_references):
    result = validate_cited_sources([1, 5, 2, 99], sample_norm_references)
    assert result == [1, 2]


def test_validate_empty():
    result = validate_cited_sources([], [])
    assert result == []


def test_filter_sources_to_cited(sample_norm_references):
    cited = filter_sources_to_cited(sample_norm_references, [1, 3])
    assert len(cited) == 2
    assert cited[0].norm_id == "bgb-535"
    assert cited[1].norm_id == "bgb-573"


def test_filter_sources_none_cited(sample_norm_references):
    cited = filter_sources_to_cited(sample_norm_references, [])
    assert len(cited) == 0
