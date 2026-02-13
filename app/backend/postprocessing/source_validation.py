"""Validate and filter source references from LLM output.

Ensures that only sources actually retrieved by the search step
appear in the final response. Drops any hallucinated source indices.
"""

from __future__ import annotations

import logging

from models.norm import NormReference

logger = logging.getLogger(__name__)


def validate_cited_sources(
    cited_indices: list[int],
    retrieved_sources: list[NormReference],
) -> list[int]:
    """Filter cited_sources to only include valid indices.

    Args:
        cited_indices: 1-based source indices from LLM structured output.
        retrieved_sources: Sources actually returned by search.

    Returns:
        Filtered list of valid 1-based indices.
    """
    valid = []
    for idx in cited_indices:
        if 1 <= idx <= len(retrieved_sources):
            valid.append(idx)
        else:
            logger.warning(
                "Dropping invalid cited source [%d] (only %d sources retrieved)",
                idx,
                len(retrieved_sources),
            )
    return valid


def filter_sources_to_cited(
    sources: list[NormReference],
    cited_indices: list[int],
) -> list[NormReference]:
    """Return only the sources that were actually cited in the answer.

    Preserves original ordering and indices for citation consistency.
    """
    cited_set = set(cited_indices)
    return [s for i, s in enumerate(sources, 1) if i in cited_set]
