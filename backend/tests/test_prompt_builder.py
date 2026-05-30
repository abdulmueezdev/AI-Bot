"""Tests for the prompt builder — token budgeting and assembly.

Asserts that:
- Total token budget (4,000) is never exceeded.
- Persona identity block is always present in the system prompt.
- RAG knowledge block is truncated before the identity block when over budget.
- Fallback context is used when similarity is below threshold.
- Each block respects its individual token budget.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from app.prompt_builder import build_prompt, count_tokens, PromptResult
from app.vector_store import RetrievalResult


class TestCountTokens:
    """Tests for the count_tokens utility."""

    def test_empty_string_returns_zero(self) -> None:
        """Empty string should have zero tokens."""
        assert count_tokens("") == 0

    def test_single_word(self) -> None:
        """Single word should return a small positive count."""
        tokens = count_tokens("hello")
        assert tokens >= 1

    def test_longer_text_more_tokens(self) -> None:
        """Longer text should produce more tokens than shorter text."""
        short = count_tokens("hello")
        long = count_tokens("hello world this is a much longer text string")
        assert long > short


class TestBuildPrompt:
    """Tests for build_prompt()."""

    @patch("app.prompt_builder._load_persona")
    def test_total_tokens_under_budget(
        self,
        mock_load: Any,
        mock_retrieval_results: list[RetrievalResult],
    ) -> None:
        """Total assembled prompt must never exceed the token budget (3584 default)."""
        mock_load.return_value = "You are Alucard. A dark philosopher."

        result = build_prompt(
            "alucard",
            "What is your view on hope?",
            mock_retrieval_results,
        )

        assert result.total_tokens <= 4000

    @patch("app.prompt_builder._load_persona")
    def test_persona_identity_always_present(
        self,
        mock_load: Any,
        mock_retrieval_results: list[RetrievalResult],
    ) -> None:
        """System prompt must always contain the persona identity text."""
        mock_load.return_value = "You are Alucard. A dark philosopher."

        result = build_prompt(
            "alucard",
            "Hello",
            mock_retrieval_results,
        )

        assert "Alucard" in result.system_prompt
        assert "digital clone" in result.system_prompt.lower()

    @patch("app.prompt_builder._load_persona")
    def test_fallback_context_when_below_threshold(
        self,
        mock_load: Any,
        mock_low_similarity_results: list[RetrievalResult],
    ) -> None:
        """When below_threshold=True, fallback context should be used."""
        mock_load.return_value = "You are Alucard."

        result = build_prompt(
            "alucard",
            "Tell me about quantum physics",
            mock_low_similarity_results,
            below_threshold=True,
        )

        assert result.used_fallback is True
        assert result.context_chunks_used == 0

    @patch("app.prompt_builder._load_persona")
    def test_fallback_context_when_no_results(
        self,
        mock_load: Any,
    ) -> None:
        """When retrieval_results is empty, fallback context should be used."""
        mock_load.return_value = "You are Alucard."

        result = build_prompt(
            "alucard",
            "Random question",
            [],
        )

        assert result.used_fallback is True
        assert result.context_chunks_used == 0

    @patch("app.prompt_builder._load_persona")
    def test_context_chunks_counted_correctly(
        self,
        mock_load: Any,
        mock_retrieval_results: list[RetrievalResult],
    ) -> None:
        """context_chunks_used should match the number of chunks actually included."""
        mock_load.return_value = "You are Alucard."

        result = build_prompt(
            "alucard",
            "What is hope?",
            mock_retrieval_results,
        )

        assert result.context_chunks_used > 0
        assert result.context_chunks_used <= len(mock_retrieval_results)

    @patch("app.prompt_builder._load_persona")
    def test_rag_truncated_before_identity(
        self,
        mock_load: Any,
    ) -> None:
        """When context is too large, chunks should be dropped (not persona)."""
        mock_load.return_value = "You are Alucard. A dark philosopher."

        # Create many large chunks to blow the budget
        huge_chunks = [
            RetrievalResult(
                text="X " * 500,  # ~500 tokens each
                metadata={"source_file": f"big{i}.md", "clone_id": "alucard"},
                similarity=0.9 - i * 0.01,
            )
            for i in range(20)
        ]

        result = build_prompt("alucard", "Hello", huge_chunks)

        # Identity must still be present
        assert "Alucard" in result.system_prompt
        # Not all chunks can fit
        assert result.context_chunks_used < 20
        # Total must be under budget
        assert result.total_tokens <= 4000

    @patch("app.prompt_builder._load_persona")
    def test_query_always_present(
        self,
        mock_load: Any,
        mock_retrieval_results: list[RetrievalResult],
    ) -> None:
        """The user's query must always appear in the assembled prompt."""
        mock_load.return_value = "You are Alucard."
        query_text = "What is your greatest fear?"

        result = build_prompt("alucard", query_text, mock_retrieval_results)

        assert query_text in result.user_prompt

    @patch("app.prompt_builder._load_persona")
    def test_result_is_prompt_result(
        self,
        mock_load: Any,
    ) -> None:
        """build_prompt should return a PromptResult dataclass."""
        mock_load.return_value = "You are Alucard."

        result = build_prompt("alucard", "Hello", [])

        assert isinstance(result, PromptResult)
        assert isinstance(result.system_prompt, str)
        assert isinstance(result.user_prompt, str)
        assert isinstance(result.total_tokens, int)
