"""Replace [1][2] citation markers with verbatim norm text from cache.

Core anti-hallucination mechanism: The LLM only outputs markers like [1], [2].
This module replaces them with the actual norm text from a pre-parsed database,
ensuring citations are always deterministic and correct.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from models.norm import Norm, NormReference

logger = logging.getLogger(__name__)

# Matches [1], [2], etc. in text
CITATION_MARKER_RE = re.compile(r"\[(\d+)\]")


class NormCache:
    """In-memory cache of norms loaded from norm_cache.json."""

    def __init__(self) -> None:
        self._norms: dict[str, Norm] = {}

    def load(self, path: Path) -> None:
        """Load norms from a JSON file."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self._norms = {k: Norm.model_validate(v) for k, v in data.items()}
        logger.info("Loaded %d norms into cache from %s", len(self._norms), path)

    def get(self, norm_id: str) -> Norm | None:
        return self._norms.get(norm_id)

    def get_by_index(self, sources: list[NormReference], index: int) -> Norm | None:
        """Get norm by 1-based citation index from the source list."""
        if 1 <= index <= len(sources):
            return self._norms.get(sources[index - 1].norm_id)
        return None

    @property
    def norms(self) -> dict[str, Norm]:
        return self._norms


# Global cache instance
norm_cache = NormCache()


def inject_citations(
    text: str,
    sources: list[NormReference],
) -> str:
    """Replace [N] markers in text with verbatim norm citations.

    Args:
        text: LLM output containing [1], [2], etc. markers.
        sources: Ordered list of NormReferences matching the source indices.

    Returns:
        Text with markers replaced by formatted citations including norm text.
    """

    def _replace_marker(match: re.Match) -> str:
        idx = int(match.group(1))
        if idx < 1 or idx > len(sources):
            logger.warning("Citation marker [%d] out of range (have %d sources)", idx, len(sources))
            return match.group(0)  # Leave invalid markers unchanged

        source = sources[idx - 1]
        norm = norm_cache.get(source.norm_id)

        if norm is None:
            logger.warning("Norm %s not found in cache for marker [%d]", source.norm_id, idx)
            return f"[{idx}: {source.paragraph}]"

        # Format: [1: § 535 BGB — Inhalt und Hauptpflichten des Mietvertrags]
        titel_part = f" — {norm.titel}" if norm.titel else ""
        return f"[{idx}: §{norm.paragraph} BGB{titel_part}]"

    return CITATION_MARKER_RE.sub(_replace_marker, text)


