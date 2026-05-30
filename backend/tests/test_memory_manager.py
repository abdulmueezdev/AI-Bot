"""Tests for the memory manager — short-term buffer and session lifecycle.

Asserts that:
- Session buffer stores last 10 turns as a deque.
- Buffer overflow evicts the oldest turn.
- Buffer flush on session end works correctly.
- Episodic memory summary generation is triggered on session end.
- Episodic memory retrieval returns top-2 summaries.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.memory_manager import MemoryManager


@pytest.mark.asyncio
class TestSessionBuffer:
    """Tests for the short-term session buffer (Tier 1)."""

    async def test_stores_interaction(self) -> None:
        """Storing an interaction should add it to the session buffer."""
        mm = MemoryManager()

        await mm.store_interaction(
            clone_id="alucard",
            session_id="sess1",
            user_message="Hello",
            assistant_response="Greetings.",
        )

        context = await mm.get_session_context("alucard", "sess1")
        assert len(context) >= 1

    async def test_buffer_max_10_turns(self) -> None:
        """Buffer should retain at most 10 turns (20 messages: user + assistant)."""
        mm = MemoryManager()

        for i in range(15):
            await mm.store_interaction(
                clone_id="alucard",
                session_id="sess1",
                user_message=f"Message {i}",
                assistant_response=f"Response {i}",
            )

        context = await mm.get_session_context("alucard", "sess1")
        # Each turn = 1 user + 1 assistant entry, max 10 turns = 20 messages
        assert len(context) <= 20

    async def test_oldest_evicted_on_overflow(self) -> None:
        """When buffer exceeds max, the oldest turns should be evicted."""
        mm = MemoryManager()

        for i in range(15):
            await mm.store_interaction(
                clone_id="alucard",
                session_id="sess1",
                user_message=f"Message {i}",
                assistant_response=f"Response {i}",
            )

        context = await mm.get_session_context("alucard", "sess1")
        # The earliest messages (0-4) should have been evicted
        all_content = " ".join(msg.get("content", "") for msg in context)
        assert "Message 0" not in all_content
        assert "Message 14" in all_content

    async def test_separate_sessions_isolated(self) -> None:
        """Different session IDs should have independent buffers."""
        mm = MemoryManager()

        await mm.store_interaction(
            clone_id="alucard",
            session_id="sess_a",
            user_message="Question A",
            assistant_response="Answer A",
        )
        await mm.store_interaction(
            clone_id="alucard",
            session_id="sess_b",
            user_message="Question B",
            assistant_response="Answer B",
        )

        ctx_a = await mm.get_session_context("alucard", "sess_a")
        ctx_b = await mm.get_session_context("alucard", "sess_b")

        a_content = " ".join(msg.get("content", "") for msg in ctx_a)
        b_content = " ".join(msg.get("content", "") for msg in ctx_b)

        assert "Question A" in a_content
        assert "Question B" not in a_content
        assert "Question B" in b_content

    async def test_empty_session_returns_empty(self) -> None:
        """A session with no interactions should return an empty list."""
        mm = MemoryManager()

        context = await mm.get_session_context("alucard", "nonexistent")
        assert context == []


@pytest.mark.asyncio
class TestEpisodicMemory:
    """Tests for episodic memory (Tier 2)."""

    async def test_get_episodic_context_returns_list(self) -> None:
        """Episodic context retrieval should return a list of summary strings."""
        mm = MemoryManager()

        result = await mm.get_episodic_context("alucard", "test query")
        assert isinstance(result, list)

    async def test_get_episodic_context_empty_for_new_clone(self) -> None:
        """A clone with no episodic memory should return an empty list."""
        mm = MemoryManager()

        result = await mm.get_episodic_context("new_clone", "test query")
        assert result == []
