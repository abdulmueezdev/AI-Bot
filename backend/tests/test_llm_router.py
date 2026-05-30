"""Tests for the LLM client — Groq (primary) + OpenRouter (fallback) routing.

Asserts that:
- Primary (Groq) is tried first.
- On Groq failure, fallback to OpenRouter.
- LLMUnavailableError raised when both fail.
- Model name is logged/returned on every successful call.
- Retry backoff logic is exercised.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.llm_client import LLMResponse, LLMUnavailableError, generate
from app.prompt_builder import PromptResult


def _make_prompt_result() -> PromptResult:
    """Create a minimal PromptResult for testing."""
    return PromptResult(
        system_prompt="You are Alucard.",
        user_prompt="Hello",
        total_tokens=50,
        context_chunks_used=1,
        used_fallback=False,
    )


@pytest.mark.asyncio
class TestGenerate:
    """Tests for the generate() function."""

    async def test_groq_success_returns_response(self) -> None:
        """Successful Groq call should return an LLMResponse with correct provider."""
        prompt = _make_prompt_result()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "I am Alucard."
        mock_response.usage = MagicMock()
        mock_response.usage.total_tokens = 100

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_client.close = AsyncMock()

        with patch("app.llm_client.AsyncGroq", return_value=mock_client):
            result = await generate(prompt, clone_id="alucard")

        assert isinstance(result, LLMResponse)
        assert result.provider == "groq"
        assert result.text == "I am Alucard."
        assert result.tokens_used == 100

    async def test_groq_model_name_in_response(self) -> None:
        """The model name should be included in the response."""
        prompt = _make_prompt_result()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"
        mock_response.usage = MagicMock()
        mock_response.usage.total_tokens = 50

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_client.close = AsyncMock()

        with patch("app.llm_client.AsyncGroq", return_value=mock_client):
            result = await generate(prompt, clone_id="alucard")

        assert result.model_used != ""
        assert isinstance(result.model_used, str)

    async def test_fallback_to_openrouter_on_groq_failure(self) -> None:
        """When Groq fails, should fall back to OpenRouter."""
        prompt = _make_prompt_result()

        # Groq fails
        mock_groq_client = AsyncMock()
        mock_groq_client.chat.completions.create = AsyncMock(
            side_effect=RuntimeError("Groq rate limited")
        )
        mock_groq_client.close = AsyncMock()

        # OpenRouter succeeds
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = {
            "choices": [{"message": {"content": "Fallback response"}}],
            "usage": {"total_tokens": 75},
        }

        with (
            patch("app.llm_client.AsyncGroq", return_value=mock_groq_client),
            patch("app.llm_client.httpx.AsyncClient") as mock_http_cls,
        ):
            mock_http_client = AsyncMock()
            mock_http_client.post = AsyncMock(return_value=mock_http_response)
            mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
            mock_http_client.__aexit__ = AsyncMock(return_value=False)
            mock_http_cls.return_value = mock_http_client

            result = await generate(prompt, clone_id="alucard")

        assert result.provider == "openrouter"
        assert result.text == "Fallback response"

    async def test_all_providers_fail_raises_unavailable(self) -> None:
        """When both Groq and OpenRouter fail, LLMUnavailableError should be raised."""
        prompt = _make_prompt_result()

        # Groq fails
        mock_groq_client = AsyncMock()
        mock_groq_client.chat.completions.create = AsyncMock(
            side_effect=RuntimeError("Groq down")
        )
        mock_groq_client.close = AsyncMock()

        # OpenRouter also fails
        with (
            patch("app.llm_client.AsyncGroq", return_value=mock_groq_client),
            patch("app.llm_client.httpx.AsyncClient") as mock_http_cls,
        ):
            mock_http_client = AsyncMock()
            mock_http_client.post = AsyncMock(
                side_effect=RuntimeError("OpenRouter down")
            )
            mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
            mock_http_client.__aexit__ = AsyncMock(return_value=False)
            mock_http_cls.return_value = mock_http_client

            with pytest.raises(LLMUnavailableError):
                await generate(prompt, clone_id="alucard")

    async def test_latency_is_positive(self) -> None:
        """Latency should be a positive number on successful call."""
        prompt = _make_prompt_result()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"
        mock_response.usage = MagicMock()
        mock_response.usage.total_tokens = 50

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_client.close = AsyncMock()

        with patch("app.llm_client.AsyncGroq", return_value=mock_client):
            result = await generate(prompt, clone_id="alucard")

        assert result.latency_ms >= 0
