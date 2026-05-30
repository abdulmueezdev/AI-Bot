"""Tests for the FastAPI router — API endpoint integration tests.

Asserts that:
- /health endpoint returns the expected shape.
- /chat/{clone_id} returns correct response model.
- Invalid clone IDs return 404.
- /ingest/{clone_id} validates clone_id.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client() -> TestClient:
    """Create a test client for the FastAPI app."""
    return TestClient(app, raise_server_exceptions=False)


class TestHealthEndpoint:
    """Tests for GET /health."""

    def test_health_returns_200(self, client: TestClient) -> None:
        """Health endpoint should return HTTP 200."""
        with patch("app.router.get_collection_count", new_callable=AsyncMock) as mock_count:
            mock_count.return_value = 42
            response = client.get("/health")

        assert response.status_code == 200

    def test_health_returns_status_field(self, client: TestClient) -> None:
        """Health response should contain a status field."""
        with patch("app.router.get_collection_count", new_callable=AsyncMock) as mock_count:
            mock_count.return_value = 42
            response = client.get("/health")

        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"

    def test_health_returns_version(self, client: TestClient) -> None:
        """Health response should contain a version field."""
        with patch("app.router.get_collection_count", new_callable=AsyncMock) as mock_count:
            mock_count.return_value = 0
            response = client.get("/health")

        data = response.json()
        assert "version" in data

    def test_health_returns_clones_dict(self, client: TestClient) -> None:
        """Health response should contain a clones dict with counts."""
        with patch("app.router.get_collection_count", new_callable=AsyncMock) as mock_count:
            mock_count.return_value = 10
            response = client.get("/health")

        data = response.json()
        assert "clones" in data
        assert isinstance(data["clones"], dict)


class TestChatEndpoint:
    """Tests for POST /chat/{clone_id}."""

    def test_invalid_clone_returns_404(self, client: TestClient) -> None:
        """Invalid clone IDs should return HTTP 404."""
        response = client.post(
            "/chat/nonexistent_clone",
            json={"message": "Hello"},
        )
        assert response.status_code == 404

    def test_empty_message_rejected(self, client: TestClient) -> None:
        """Empty message should be rejected by validation."""
        response = client.post(
            "/chat/alucard",
            json={"message": ""},
        )
        # Pydantic validation should reject min_length=1
        assert response.status_code == 422

    @patch("app.router.handle_chat", new_callable=AsyncMock)
    def test_valid_chat_returns_200(
        self, mock_chat: AsyncMock, client: TestClient
    ) -> None:
        """Valid chat request should return HTTP 200 with response model."""
        from app.orchestrator import ChatResult

        mock_chat.return_value = ChatResult(
            response="I am Alucard.",
            clone_id="alucard",
            session_id="test_session",
            model_used="llama-3.1-70b-versatile",
            provider="groq",
            context_chunks_used=2,
            latency_ms=500.0,
            used_fallback_context=False,
        )

        response = client.post(
            "/chat/alucard",
            json={"message": "Who are you?"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["response"] == "I am Alucard."
        assert data["clone_id"] == "alucard"
        assert "session_id" in data
        assert "model_used" in data


class TestIngestEndpoint:
    """Tests for POST /ingest/{clone_id}."""

    def test_invalid_clone_returns_404(self, client: TestClient) -> None:
        """Invalid clone IDs should return HTTP 404."""
        response = client.post("/ingest/nonexistent_clone")
        assert response.status_code == 404


class TestCalendarStatusEndpoint:
    """Tests for GET /calendar/status/{persona_id}."""

    def test_calendar_status_returns_200(self, client: TestClient) -> None:
        """Calendar status endpoint should return HTTP 200."""
        response = client.get("/calendar/status/alucard")
        assert response.status_code == 200

    def test_calendar_status_has_expected_fields(self, client: TestClient) -> None:
        """Calendar status should include cache_age, event_count, status fields."""
        response = client.get("/calendar/status/alucard")
        data = response.json()
        assert "clone_id" in data
        assert "cache_age_seconds" in data
        assert "event_count" in data
        assert "status" in data


class TestSessionEndpoint:
    """Tests for POST /session/end/{clone_id}/{session_id}."""

    def test_invalid_clone_returns_404(self, client: TestClient) -> None:
        """Invalid clone ID should return HTTP 404."""
        response = client.post("/session/end/nonexistent/sess1")
        assert response.status_code == 404

    def test_valid_end_session_returns_200(self, client: TestClient) -> None:
        """Valid end session request should return HTTP 200."""
        response = client.post("/session/end/alucard/test_session")
        assert response.status_code == 200
        data = response.json()
        assert data["clone_id"] == "alucard"
        assert data["session_id"] == "test_session"
        assert data["status"] in ("flushed", "empty")
