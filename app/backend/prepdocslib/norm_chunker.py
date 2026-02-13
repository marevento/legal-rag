"""Chunk norms for Azure AI Search indexing.

Strategy: 1 paragraph = 1 chunk. Each Mietrecht paragraph is a self-contained
legal unit, so no splitting is needed for our ~45 documents.
"""

from __future__ import annotations

from models.norm import Norm


def chunk_norms(norms: list[Norm]) -> list[dict]:
    """Convert Norm objects into search index documents.

    Each document contains the full paragraph text plus metadata
    for filtering, display, and citation.

    Args:
        norms: Parsed Norm objects from BMJ XML.

    Returns:
        List of dicts ready for Azure AI Search upload.
    """
    documents = []
    for norm in norms:
        doc = {
            "id": norm.norm_id,
            "norm_id": norm.norm_id,
            "gesetz": norm.gesetz,
            "paragraph": norm.paragraph,
            "titel": norm.titel,
            "text": norm.text,
            "url": norm.url,
            # Combined field for embedding: title + text for richer semantic representation
            "content": _build_content_field(norm),
        }
        documents.append(doc)
    return documents


def _build_content_field(norm: Norm) -> str:
    """Build the content field used for embedding and full-text search."""
    parts = [f"§{norm.paragraph} BGB"]
    if norm.titel:
        parts.append(norm.titel)
    parts.append(norm.text)
    return "\n".join(parts)
