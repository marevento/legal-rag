"""Integration tests for async routes and RAG pipeline with mocked clients."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
import pytest_asyncio

from app import create_app
from models.norm import Norm

TEST_JWT_SECRET = "test-secret-key-for-testing-only"
TEST_ADMIN_EMAIL = "admin@test.com"
TEST_VIEWER_EMAIL = "viewer@test.com"


def _make_token(email: str, role: str = "viewer") -> str:
    """Create a test JWT token."""
    from datetime import datetime, timedelta, timezone

    payload = {
        "sub": email,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


def _auth_headers(email: str = TEST_ADMIN_EMAIL, role: str = "admin") -> dict[str, str]:
    """Return Bearer auth headers for test user."""
    token = _make_token(email, role)
    return {"Authorization": f"Bearer {token}"}


# --- Fixtures ---


@pytest_asyncio.fixture
async def app_with_client(tmp_path: Path):
    """Create a Quart app and test client with mocked Azure clients."""
    cache_data = {
        "535": {
            "norm_id": "bgb-535",
            "paragraph": "535",
            "titel": "Inhalt und Hauptpflichten des Mietvertrags",
            "text": "Durch den Mietvertrag wird der Vermieter verpflichtet...",
            "gesetz": "BGB",
            "url": "https://www.gesetze-im-internet.de/bgb/__535.html",
        }
    }
    cache_path = tmp_path / "norm_cache.json"
    cache_path.write_text(json.dumps(cache_data), encoding="utf-8")

    with (
        patch("config.NORM_CACHE_PATH", str(cache_path)),
        patch("config.AZURE_OPENAI_ENDPOINT", "https://fake.openai.azure.com"),
        patch("config.AZURE_OPENAI_API_KEY", "fake-key"),
        patch("config.AZURE_SEARCH_ENDPOINT", "https://fake.search.windows.net"),
        patch("config.AZURE_SEARCH_API_KEY", "fake-key"),
        patch("config.JWT_SECRET", TEST_JWT_SECRET),
        patch("config.ADMIN_EMAILS", [TEST_ADMIN_EMAIL]),
    ):
        app = create_app()
        async with app.test_app() as test_app:
            client = test_app.test_client()
            yield app, client


@pytest_asyncio.fixture
async def app_client(app_with_client):
    """Convenience fixture returning just the client."""
    _, client = app_with_client
    return client


# --- Health endpoint ---


@pytest.mark.asyncio
async def test_health(app_client):
    response = await app_client.get("/health")
    assert response.status_code == 200
    data = await response.get_json()
    assert data["status"] == "ok"


# --- Auth enforcement ---


@pytest.mark.asyncio
async def test_chat_requires_auth(app_client):
    response = await app_client.post(
        "/chat",
        json={"messages": [{"role": "user", "content": "test"}]},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_config_requires_auth(app_client):
    response = await app_client.get("/config")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_config_with_auth(app_client):
    response = await app_client.get("/config", headers=_auth_headers())
    assert response.status_code == 200
    data = await response.get_json()
    assert "search_strategy" in data


# --- Chat endpoint with mocked RAG ---


@pytest.mark.asyncio
async def test_chat_returns_response(app_with_client):
    """Test /chat endpoint with mocked approach."""
    from models.chat import ChatResponse

    app, client = app_with_client

    mock_response = ChatResponse(
        answer="Die Hauptpflichten ergeben sich aus [1: §535 BGB — Inhalt und Hauptpflichten des Mietvertrags].",
        sources=[],
        confidence="high",
        search_strategy="hybrid",
        approach="custom",
    )

    with patch.object(
        app.config["chat_rag"],
        "run",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        response = await client.post(
            "/chat",
            json={"messages": [{"role": "user", "content": "Was sind die Hauptpflichten?"}]},
            headers=_auth_headers(),
        )
        assert response.status_code == 200
        data = await response.get_json()
        assert "answer" in data
        assert data["confidence"] == "high"


# --- Evaluate endpoint ---


@pytest.mark.asyncio
async def test_evaluate_404_without_golden_dataset(app_client):
    """Test /evaluate returns 404 when golden dataset is missing."""
    with patch("config.DATA_DIR", "/nonexistent"):
        response = await app_client.post(
            "/evaluate",
            json={"strategies": ["hybrid"]},
            headers=_auth_headers(),
        )
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_evaluate_forbidden_for_viewer(app_client):
    """Test /evaluate returns 403 for viewer role."""
    response = await app_client.post(
        "/evaluate",
        json={"strategies": ["hybrid"]},
        headers=_auth_headers(TEST_VIEWER_EMAIL, "viewer"),
    )
    assert response.status_code == 403


# --- Norms endpoint ---


@pytest.mark.asyncio
async def test_norms_returns_cached_norms(app_client):
    response = await app_client.get("/norms", headers=_auth_headers())
    assert response.status_code == 200
    data = await response.get_json()
    assert len(data) == 1
    assert data[0]["paragraph"] == "535"
