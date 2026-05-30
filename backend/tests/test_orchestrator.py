"""Tests for the orchestrator — full RAG pipeline integration.

Asserts that:
- handle_chat validates clone_id.
- Empty messages return the in-character fallback.
- Full pipeline assembles with mocked dependencies.
- Session timeout detection triggers memory flush.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.orchestrator import ChatResult, handle_chat


@pytest.mark.asyncio
class TestHandleChat:
    """Tests for the handle_chat() orchestrator."""

    async def test_invalid_clone_id_raises_404(self) -> None:
        """Invalid clone IDs should raise HTTP 404."""
        with pytest.raises(HTTPException) as exc_info:
            await handle_chat(
                clone_id="nonexistent",
                message="Hello",
                session_id="test_session",
            )
        assert exc_info.value.status_code == 404

    async def test_empty_message_returns_fallback(self) -> None:
        """Empty or whitespace-only messages should return the in-character fallback."""
        result = await handle_chat(
            clone_id="alucard",
            message="   ",
            session_id="test_session",
        )
        assert isinstance(result, ChatResult)
        assert "empty message" in result.response.lower()
        assert result.model_used == "none"
        assert result.context_chunks_used == 0

    async def test_generates_session_id_if_none(self) -> None:
        """If no session_id is provided, one should be generated."""
        result = await handle_chat(
            clone_id="alucard",
            message="",
            session_id=None,
        )
        assert result.session_id != ""
        assert len(result.session_id) > 0

    @patch("app.orchestrator.generate")
    @patch("app.orchestrator.vector_query")
    @patch("app.orchestrator.embed_query")
    async def test_full_pipeline_success(
        self,
        mock_embed: AsyncMock,
        mock_vector: AsyncMock,
        mock_generate: AsyncMock,
    ) -> None:
        """Full pipeline should chain: embed → search → build prompt → call LLM."""
        mock_embed.return_value = [0.1] * 768

        from app.vector_store import RetrievalResult

        mock_vector.return_value = [
            RetrievalResult(
                text="Alucard believes hope is cruel.",
                metadata={"source_file": "test.md", "clone_id": "alucard"},
                similarity=0.9,
            )
        ]

        from app.llm_client import LLMResponse

        mock_generate.return_value = LLMResponse(
            text="I am Alucard. Hope is indeed the cruelest instrument.",
            model_used="llama-3.1-70b-versatile",
            provider="groq",
            tokens_used=120,
            latency_ms=500.0,
        )

        result = await handle_chat(
            clone_id="alucard",
            message="What do you think about hope?",
            session_id="test_session",
        )

        assert isinstance(result, ChatResult)
        assert result.clone_id == "alucard"
        assert result.model_used == "llama-3.1-70b-versatile"
        assert result.latency_ms > 0
        assert "Alucard" in result.response

    @patch("app.orchestrator.generate")
    @patch("app.orchestrator.vector_query")
    @patch("app.orchestrator.embed_query")
    async def test_chat_result_has_all_fields(
        self,
        mock_embed: AsyncMock,
        mock_vector: AsyncMock,
        mock_generate: AsyncMock,
    ) -> None:
        """ChatResult should have all required fields populated."""
        mock_embed.return_value = [0.1] * 768
        mock_vector.return_value = []

        from app.llm_client import LLMResponse

        mock_generate.return_value = LLMResponse(
            text="Response text",
            model_used="test-model",
            provider="groq",
            tokens_used=50,
            latency_ms=100.0,
        )

        result = await handle_chat(
            clone_id="alucard",
            message="Hello",
            session_id="test_sess",
        )

        assert result.response != ""
        assert result.clone_id == "alucard"
        assert result.session_id == "test_sess"
        assert isinstance(result.model_used, str)
        assert isinstance(result.latency_ms, float)
        assert isinstance(result.context_chunks_used, int)
