"""Tests for norm chunking."""

from prepdocslib.norm_chunker import chunk_norms


def test_chunk_norms(sample_norms):
    docs = chunk_norms(sample_norms)
    assert len(docs) == 3

    doc = docs[0]
    assert doc["id"] == "bgb-535"
    assert doc["norm_id"] == "bgb-535"
    assert doc["gesetz"] == "BGB"
    assert doc["paragraph"] == "535"
    assert doc["titel"] == "Inhalt und Hauptpflichten des Mietvertrags"
    assert "Mietvertrag" in doc["text"]
    assert doc["url"].startswith("https://")


def test_chunk_content_field(sample_norms):
    docs = chunk_norms(sample_norms)
    content = docs[0]["content"]
    assert "§535 BGB" in content
    assert "Inhalt und Hauptpflichten" in content
    assert "Mietvertrag" in content


def test_chunk_empty():
    docs = chunk_norms([])
    assert docs == []
