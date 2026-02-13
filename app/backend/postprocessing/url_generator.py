"""Generate deterministic URLs for gesetze-im-internet.de."""

from __future__ import annotations

import re

# Mapping of law abbreviations to gesetze-im-internet.de path segments
_LAW_PATHS: dict[str, str] = {
    "bgb": "bgb",
    "BGB": "bgb",
}


def generate_norm_url(gesetz: str, paragraph: str) -> str:
    """Generate a gesetze-im-internet.de URL for a given norm.

    Args:
        gesetz: Law abbreviation (e.g. 'bgb', 'BGB').
        paragraph: Paragraph number, possibly with suffix (e.g. '535', '573a').

    Returns:
        Full URL like 'https://www.gesetze-im-internet.de/bgb/__535.html'
    """
    law_path = _LAW_PATHS.get(gesetz, gesetz.lower())

    # Normalize paragraph: '573a' -> '573a', '535' -> '535'
    clean_para = re.sub(r"[§\s]", "", paragraph)

    return f"https://www.gesetze-im-internet.de/{law_path}/__{clean_para}.html"
