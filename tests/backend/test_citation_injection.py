"""Tests for citation injection (anti-hallucination core)."""

import json
import tempfile
from pathlib import Path

from models.norm import Norm, NormReference
from postprocessing.citation_injection import NormCache, inject_citations


def test_inject_single_citation(sample_norms, sample_norm_references):
    cache = NormCache()
    cache._norms = {n.norm_id: n for n in sample_norms}

    # Monkey-patch the global cache for this test
    import postprocessing.citation_injection as module

    original = module.norm_cache
    module.norm_cache = cache

    try:
        text = "Der Vermieter hat Pflichten gemäß [1]."
        result = inject_citations(text, sample_norm_references)
        assert "[1: §535 BGB" in result
        assert "Inhalt und Hauptpflichten" in result
    finally:
        module.norm_cache = original


def test_inject_multiple_citations(sample_norms, sample_norm_references):
    cache = NormCache()
    cache._norms = {n.norm_id: n for n in sample_norms}

    import postprocessing.citation_injection as module

    original = module.norm_cache
    module.norm_cache = cache

    try:
        text = "Siehe [1] und [2] sowie [3]."
        result = inject_citations(text, sample_norm_references)
        assert "[1: §535 BGB" in result
        assert "[2: §556 BGB" in result
        assert "[3: §573 BGB" in result
    finally:
        module.norm_cache = original


def test_invalid_marker_unchanged(sample_norms, sample_norm_references):
    cache = NormCache()
    cache._norms = {n.norm_id: n for n in sample_norms}

    import postprocessing.citation_injection as module

    original = module.norm_cache
    module.norm_cache = cache

    try:
        text = "Invalid reference [99]."
        result = inject_citations(text, sample_norm_references)
        assert "[99]" in result  # Unchanged
    finally:
        module.norm_cache = original


def test_no_markers():
    text = "This text has no citation markers."
    result = inject_citations(text, [])
    assert result == text


def test_norm_cache_load(sample_norms):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        data = {n.norm_id: n.model_dump() for n in sample_norms}
        json.dump(data, f, ensure_ascii=False)
        f.flush()

        cache = NormCache()
        cache.load(Path(f.name))
        assert len(cache.norms) == 3
        assert cache.get("bgb-535") is not None
        assert cache.get("bgb-535").paragraph == "535"
