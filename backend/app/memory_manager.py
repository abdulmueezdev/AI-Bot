"""Memory manager — Phase 2 stub.

This module will implement the 3-tier memory system:
- Working memory (current session context)
- Episodic memory (summarized past conversations)
- Semantic memory (RAG knowledge base — already in vector_store)

Phase 1: No-op implementation. All methods return empty/default values.
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)


class MemoryManager:
    """Stub memory manager for Phase 1.

    Phase 2 will add:
    - Session history tracking
    - Conversation summarization
    - Semantic retrieval of past sessions
    """

    async def get_session_context(
        self, clone_id: str, session_id: str
    ) -> list[dict[str, str]]:
        """Get conversation history for the current session.

        Phase 1: Returns empty list (no session memory).
        """
        return []

    async def store_interaction(
        self,
        clone_id: str,
        session_id: str,
        user_message: str,
        assistant_response: str,
    ) -> None:
        """Store an interaction for future retrieval.

        Phase 1: No-op.
        """
        logger.debug(
            "memory_store_skipped_phase1",
            clone_id=clone_id,
            session_id=session_id,
        )

    async def get_episodic_context(
        self, clone_id: str, query: str
    ) -> list[str]:
        """Retrieve relevant past conversation summaries.

        Phase 1: Returns empty list.
        """
        return []
