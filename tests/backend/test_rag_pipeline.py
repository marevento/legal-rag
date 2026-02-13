"""Tests for the core RAG pipeline: search → LLM → postprocess → response.

Mocks only the external services (OpenAI, Azure Search) and verifies the full
pipeline including query transform, citation renumbering, source validation, and
citation injection.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.chat import ChatRequest, ChatMessage, StructuredLLMOutput
from models.norm import Norm, NormReference
from postprocessing.citation_injection import NormCache
import postprocessing.citation_injection as _ci_module


# --- Fixtures ---


@pytest.fixture(autouse=True)
def _patch_norm_cache():
    """Inject a test NormCache with two norms for all tests in this module."""
    cache = NormCache()
    cache._norms = {
        "bgb-535": Norm(
            norm_id="bgb-535",
            paragraph="535",
            titel="Inhalt und Hauptpflichten des Mietvertrags",
            text="(1) Durch den Mietvertrag wird der Vermieter verpflichtet...",
            gesetz="BGB",
            url="https://www.gesetze-im-internet.de/bgb/__535.html",
        ),
        "bgb-536": Norm(
            norm_id="bgb-536",
            paragraph="536",
            titel="Mietminderung bei Sach- und Rechtsmängeln",
            text="(1) Hat die Mietsache zur Zeit der Überlassung einen Mangel...",
            gesetz="BGB",
            url="https://www.gesetze-im-internet.de/bgb/__536.html",
        ),
    }
    original = _ci_module.norm_cache
    _ci_module.norm_cache = cache
    yield
    _ci_module.norm_cache = original


@pytest.fixture
def search_results() -> list[NormReference]:
    """Simulated search results as NormReference objects."""
    return [
        NormReference(
            norm_id="bgb-535",
            paragraph="535",
            titel="Inhalt und Hauptpflichten des Mietvertrags",
            text="(1) Durch den Mietvertrag wird der Vermieter verpflichtet...",
            url="https://www.gesetze-im-internet.de/bgb/__535.html",
            relevance_score=0.95,
        ),
        NormReference(
            norm_id="bgb-536",
            paragraph="536",
            titel="Mietminderung bei Sach- und Rechtsmängeln",
            text="(1) Hat die Mietsache zur Zeit der Überlassung einen Mangel...",
            url="https://www.gesetze-im-internet.de/bgb/__536.html",
            relevance_score=0.80,
        ),
    ]


def _make_chat_request(
    question: str = "Was sind die Hauptpflichten?",
    query_transform: str = "none",
    decompose: bool = False,
) -> ChatRequest:
    return ChatRequest(
        messages=[ChatMessage(role="user", content=question)],
        search_strategy="hybrid",
        query_transform=query_transform,
        decompose=decompose,
        top_k=5,
        approach="custom",
    )


# --- Postprocessing tests ---


class TestPostprocessing:
    """Test the _postprocess method on the Approach base class."""

    def test_renumber_and_inject(self):
        """Citations are renumbered and injected with verbatim text."""
        from approaches.approach import Approach

        sources = [
            NormReference(norm_id="bgb-535", paragraph="535", titel="Inhalt", text="...", url=""),
            NormReference(norm_id="bgb-536", paragraph="536", titel="Minderung", text="...", url=""),
        ]

        # LLM cites source 2 only (skipping 1) — should be renumbered to [1]
        answer, cited = Approach._postprocess(
            "Bei Mängeln gilt [2].", [2], sources
        )

        assert len(cited) == 1
        assert cited[0].norm_id == "bgb-536"
        assert "[1:" in answer  # renumbered from [2] to [1]
        assert "§536" in answer

    def test_invalid_citation_dropped(self):
        """Invalid citation indices are silently dropped."""
        from approaches.approach import Approach

        sources = [
            NormReference(norm_id="bgb-535", paragraph="535", titel="Inhalt", text="...", url=""),
        ]

        # LLM cites source 1 (valid) and 5 (invalid)
        answer, cited = Approach._postprocess(
            "Die Pflichten [1] und weitere [5].", [1, 5], sources
        )

        assert len(cited) == 1
        assert cited[0].norm_id == "bgb-535"
        assert "[1:" in answer
        assert "[5]" in answer  # invalid marker left as-is (no matching source)

    def test_no_citations(self):
        """Answer with no citations passes through unchanged."""
        from approaches.approach import Approach

        sources = [
            NormReference(norm_id="bgb-535", paragraph="535", titel="Inhalt", text="...", url=""),
        ]

        answer, cited = Approach._postprocess(
            "Keine spezifische Norm gefunden.", [], sources
        )

        assert len(cited) == 0
        assert answer == "Keine spezifische Norm gefunden."

    def test_multiple_citations_renumbered(self):
        """Multiple citations are renumbered sequentially."""
        from approaches.approach import Approach

        sources = [
            NormReference(norm_id="bgb-535", paragraph="535", titel="Inhalt", text="...", url=""),
            NormReference(norm_id="bgb-536", paragraph="536", titel="Minderung", text="...", url=""),
        ]

        # LLM cites both sources
        answer, cited = Approach._postprocess(
            "Pflichten [1] und Mängel [2].", [1, 2], sources
        )

        assert len(cited) == 2
        assert "[1:" in answer
        assert "[2:" in answer


# --- Full pipeline tests ---


class TestChatRAGPipeline:
    """Test the full ChatRAGApproach.run() with mocked OpenAI and Search."""

    @pytest.mark.asyncio
    async def test_full_pipeline(self, search_results):
        """Complete pipeline: search → generate → postprocess (no query transform)."""
        mock_openai = AsyncMock()

        # Single LLM call: structured generation (query_transform=none, no rewrite)
        gen_response = MagicMock()
        gen_response.choices = [MagicMock()]
        llm_output = StructuredLLMOutput(
            explanation="Der Vermieter muss die Mietsache überlassen [1]. Bei Mängeln kann gemindert werden [2].",
            cited_sources=[1, 2],
            confidence="high",
        )
        gen_response.choices[0].message.content = llm_output.model_dump_json()

        mock_openai.chat.completions.create = AsyncMock(return_value=gen_response)

        with (
            patch("config.AZURE_OPENAI_ENDPOINT", "https://fake.openai.azure.com"),
            patch("config.AZURE_OPENAI_API_KEY", "fake-key"),
            patch("config.AZURE_OPENAI_API_VERSION", "2024-10-21"),
            patch("config.AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large"),
            patch("config.AZURE_OPENAI_EMBEDDING_DIMENSIONS", 3072),
            patch("approaches.approach.Approach._search_async", new_callable=AsyncMock, return_value=search_results),
        ):
            from approaches.chat_rag import ChatRAGApproach

            approach = ChatRAGApproach(
                openai_client=mock_openai,
                search_client=MagicMock(),
            )

            request = _make_chat_request()
            response = await approach.run(request)

        assert response.confidence == "high"
        assert len(response.sources) == 2
        assert response.sources[0].norm_id == "bgb-535"
        assert response.sources[1].norm_id == "bgb-536"
        assert "[1:" in response.answer
        assert "[2:" in response.answer
        assert "§535" in response.answer
        assert "§536" in response.answer

    @pytest.mark.asyncio
    async def test_pipeline_with_rewrite(self, search_results):
        """Pipeline with query_transform=rewrite: rewrite → search → generate."""
        mock_openai = AsyncMock()

        # First call: query rewrite
        rewrite_response = MagicMock()
        rewrite_response.choices = [MagicMock()]
        rewrite_response.choices[0].message.content = "Hauptpflichten Vermieter Mieter BGB 535"

        # Second call: structured generation
        gen_response = MagicMock()
        gen_response.choices = [MagicMock()]
        llm_output = StructuredLLMOutput(
            explanation="Der Vermieter muss die Mietsache überlassen [1].",
            cited_sources=[1],
            confidence="high",
        )
        gen_response.choices[0].message.content = llm_output.model_dump_json()

        mock_openai.chat.completions.create = AsyncMock(
            side_effect=[rewrite_response, gen_response]
        )

        with (
            patch("config.AZURE_OPENAI_ENDPOINT", "https://fake.openai.azure.com"),
            patch("config.AZURE_OPENAI_API_KEY", "fake-key"),
            patch("config.AZURE_OPENAI_API_VERSION", "2024-10-21"),
            patch("config.AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large"),
            patch("config.AZURE_OPENAI_EMBEDDING_DIMENSIONS", 3072),
            patch("approaches.approach.Approach._search_async", new_callable=AsyncMock, return_value=search_results),
        ):
            from approaches.chat_rag import ChatRAGApproach

            approach = ChatRAGApproach(
                openai_client=mock_openai,
                search_client=MagicMock(),
            )

            request = _make_chat_request(query_transform="rewrite")
            response = await approach.run(request)

        assert response.confidence == "high"
        assert len(response.sources) == 1
        # Verify rewrite was called (2 LLM calls total)
        assert mock_openai.chat.completions.create.call_count == 2

    @pytest.mark.asyncio
    async def test_pipeline_drops_hallucinated_source(self, search_results):
        """Pipeline drops citation indices that don't exist in search results."""
        mock_openai = AsyncMock()

        gen_response = MagicMock()
        gen_response.choices = [MagicMock()]
        llm_output = StructuredLLMOutput(
            explanation="Pflichten [1] und noch etwas [3].",  # [3] doesn't exist
            cited_sources=[1, 3],
            confidence="medium",
        )
        gen_response.choices[0].message.content = llm_output.model_dump_json()

        mock_openai.chat.completions.create = AsyncMock(return_value=gen_response)

        with (
            patch("config.AZURE_OPENAI_ENDPOINT", "https://fake.openai.azure.com"),
            patch("config.AZURE_OPENAI_API_KEY", "fake-key"),
            patch("config.AZURE_OPENAI_API_VERSION", "2024-10-21"),
            patch("config.AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large"),
            patch("config.AZURE_OPENAI_EMBEDDING_DIMENSIONS", 3072),
            patch("approaches.approach.Approach._search_async", new_callable=AsyncMock, return_value=search_results),
        ):
            from approaches.chat_rag import ChatRAGApproach

            approach = ChatRAGApproach(
                openai_client=mock_openai,
                search_client=MagicMock(),
            )

            request = _make_chat_request()
            response = await approach.run(request)

        # Only source 1 should survive — source 3 was hallucinated
        assert len(response.sources) == 1
        assert response.sources[0].norm_id == "bgb-535"
        assert response.confidence == "medium"

    @pytest.mark.asyncio
    async def test_query_rewrite_fallback(self, search_results):
        """If query rewrite fails, pipeline uses original query."""
        mock_openai = AsyncMock()

        # First call: query rewrite FAILS
        # Second call: structured generation succeeds
        gen_response = MagicMock()
        gen_response.choices = [MagicMock()]
        llm_output = StructuredLLMOutput(
            explanation="Antwort [1].",
            cited_sources=[1],
            confidence="high",
        )
        gen_response.choices[0].message.content = llm_output.model_dump_json()

        mock_openai.chat.completions.create = AsyncMock(
            side_effect=[Exception("API error"), gen_response]
        )

        with (
            patch("config.AZURE_OPENAI_ENDPOINT", "https://fake.openai.azure.com"),
            patch("config.AZURE_OPENAI_API_KEY", "fake-key"),
            patch("config.AZURE_OPENAI_API_VERSION", "2024-10-21"),
            patch("config.AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large"),
            patch("config.AZURE_OPENAI_EMBEDDING_DIMENSIONS", 3072),
            patch("approaches.approach.Approach._search_async", new_callable=AsyncMock, return_value=search_results),
        ):
            from approaches.chat_rag import ChatRAGApproach

            approach = ChatRAGApproach(
                openai_client=mock_openai,
                search_client=MagicMock(),
            )

            request = _make_chat_request("Kann mein Vermieter kündigen?", query_transform="rewrite")
            response = await approach.run(request)

        # Should still succeed with original query
        assert response.confidence == "high"
        assert len(response.sources) == 1
