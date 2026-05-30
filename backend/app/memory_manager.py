"""Memory manager — 3-tier memory system for digital clones.

Tier 1: Short-term buffer — in-memory deque, max 10 turns per session.
Tier 2: Episodic memory — summarized past sessions in ChromaDB.
Tier 3: Entity memory — structured entities in Supabase (with in-memory fallback).

Session lifecycle:
- Each interaction is stored in the short-term buffer.
- On session end (explicit call or 30-min timeout), a summary is generated
  and stored as an episodic memory embedding.
- Entities are extracted from the summary and upserted to persistent storage.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

import structlog

logger = structlog.get_logger(__name__)

# ── Constants ──────────────────────────────────────────────────────────

MAX_TURNS_PER_SESSION: int = 10
SESSION_TIMEOUT_SECONDS: int = 1800  # 30 minutes
EPISODIC_SUMMARY_WORD_TARGET: int = 100
EPISODIC_TOP_K: int = 2
ENTITY_TOP_K: int = 5

SUMMARY_INSTRUCTION: str = (
    "Summarize this conversation in exactly 100 words. "
    "Focus on decisions made, topics discussed, and any commitments "
    "or preferences expressed by the user. Write in third person."
)

ENTITY_EXTRACTION_INSTRUCTION: str = (
    "Extract named entities from this conversation summary. "
    "Return a JSON array of objects with keys: "
    '"entity_type" (one of: person, project, date, preference, commitment), '
    '"entity_name" (the entity), '
    '"context" (brief context of how it was mentioned). '
    "Return ONLY the JSON array, no other text."
)


# ── Data Structures ───────────────────────────────────────────────────


@dataclass
class SessionMessage:
    """A single message in the session buffer."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: str

    def to_dict(self) -> dict[str, str]:
        """Convert to a JSON-safe dictionary."""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
        }


@dataclass
class SessionState:
    """State for an active session including buffer and metadata."""

    turns: deque[tuple[SessionMessage, SessionMessage]] = field(
        default_factory=lambda: deque(maxlen=MAX_TURNS_PER_SESSION)
    )
    last_activity: float = field(default_factory=time.monotonic)
    turn_count: int = 0


@dataclass
class EntityRecord:
    """A structured entity extracted from conversation."""

    entity_type: str
    entity_name: str
    context: str
    last_updated: str


# ── Memory Manager ────────────────────────────────────────────────────


class MemoryManager:
    """3-tier memory system for digital clones.

    Tier 1: Short-term session buffer (in-memory deque).
    Tier 2: Episodic memory (ChromaDB collection per clone).
    Tier 3: Entity memory (Supabase with in-memory fallback).
    """

    def __init__(self) -> None:
        """Initialize the memory manager with empty session buffers."""
        # Tier 1: {(clone_id, session_id): SessionState}
        self._sessions: dict[tuple[str, str], SessionState] = {}

        # Tier 3 fallback: in-memory entity store
        # {clone_id: {entity_name: EntityRecord}}
        self._entity_store: dict[str, dict[str, EntityRecord]] = defaultdict(dict)

    # ── Tier 1: Short-Term Buffer ──────────────────────────────────────

    async def store_interaction(
        self,
        clone_id: str,
        session_id: str,
        user_message: str,
        assistant_response: str,
    ) -> None:
        """Store an interaction in the short-term session buffer.

        Args:
            clone_id: The clone identifier.
            session_id: The session identifier.
            user_message: The user's message.
            assistant_response: The assistant's response.
        """
        key = (clone_id, session_id)
        now = datetime.now(timezone.utc).isoformat()

        if key not in self._sessions:
            self._sessions[key] = SessionState()

        state = self._sessions[key]

        user_msg = SessionMessage(role="user", content=user_message, timestamp=now)
        asst_msg = SessionMessage(
            role="assistant", content=assistant_response, timestamp=now
        )

        state.turns.append((user_msg, asst_msg))
        state.last_activity = time.monotonic()
        state.turn_count += 1

        logger.debug(
            "interaction_stored",
            clone_id=clone_id,
            session_id=session_id,
            turn_count=state.turn_count,
            buffer_size=len(state.turns),
        )

    async def get_session_context(
        self, clone_id: str, session_id: str
    ) -> list[dict[str, str]]:
        """Get conversation history for the current session.

        Args:
            clone_id: The clone identifier.
            session_id: The session identifier.

        Returns:
            List of message dicts with 'role' and 'content' keys,
            ordered chronologically. Returns empty list if no session exists.
        """
        key = (clone_id, session_id)
        state = self._sessions.get(key)

        if state is None:
            return []

        messages: list[dict[str, str]] = []
        for user_msg, asst_msg in state.turns:
            messages.append(user_msg.to_dict())
            messages.append(asst_msg.to_dict())

        return messages

    def _check_session_timeout(
        self, clone_id: str, session_id: str
    ) -> bool:
        """Check if a session has timed out (>30 minutes since last activity).

        Args:
            clone_id: The clone identifier.
            session_id: The session identifier.

        Returns:
            True if the session has timed out, False otherwise.
        """
        key = (clone_id, session_id)
        state = self._sessions.get(key)

        if state is None:
            return False

        elapsed = time.monotonic() - state.last_activity
        return elapsed > SESSION_TIMEOUT_SECONDS

    async def flush_session(
        self,
        clone_id: str,
        session_id: str,
    ) -> str | None:
        """Flush a session: generate summary, store episodic memory, extract entities.

        This is called when a session ends (explicit call or timeout detected).

        Args:
            clone_id: The clone identifier.
            session_id: The session identifier.

        Returns:
            The generated summary string, or None if session was empty.
        """
        key = (clone_id, session_id)
        state = self._sessions.get(key)

        if state is None or len(state.turns) == 0:
            logger.info(
                "session_flush_skipped_empty",
                clone_id=clone_id,
                session_id=session_id,
            )
            return None

        # Build transcript from buffer
        transcript = self._build_transcript(state)

        logger.info(
            "session_flush_started",
            clone_id=clone_id,
            session_id=session_id,
            turn_count=state.turn_count,
            transcript_length=len(transcript),
        )

        # Generate summary via LLM (lazy import to avoid circular deps)
        summary = await self._generate_summary(clone_id, transcript)

        if summary:
            # Store episodic memory embedding
            await self._store_episodic_memory(
                clone_id=clone_id,
                session_id=session_id,
                summary=summary,
                turn_count=state.turn_count,
            )

            # Extract and store entities
            await self._extract_and_store_entities(clone_id, summary)

        # Clear the session buffer
        del self._sessions[key]

        logger.info(
            "session_flushed",
            clone_id=clone_id,
            session_id=session_id,
            summary_length=len(summary) if summary else 0,
        )

        return summary

    def _build_transcript(self, state: SessionState) -> str:
        """Build a text transcript from the session buffer.

        Args:
            state: The session state containing turns.

        Returns:
            Formatted transcript string.
        """
        lines: list[str] = []
        for user_msg, asst_msg in state.turns:
            lines.append(f"User: {user_msg.content}")
            lines.append(f"Assistant: {asst_msg.content}")
        return "\n".join(lines)

    async def _generate_summary(
        self, clone_id: str, transcript: str
    ) -> str | None:
        """Generate a 100-word summary of the conversation using the LLM.

        Args:
            clone_id: The clone identifier for logging.
            transcript: The full conversation transcript.

        Returns:
            Summary string, or None if generation failed.
        """
        try:
            from app.llm_client import generate
            from app.prompt_builder import PromptResult

            prompt = PromptResult(
                system_prompt=SUMMARY_INSTRUCTION,
                user_prompt=transcript,
                total_tokens=0,
                context_chunks_used=0,
                used_fallback=False,
            )

            response = await generate(
                prompt,
                clone_id=clone_id,
                session_id="memory_summary",
            )

            logger.info(
                "episodic_summary_generated",
                clone_id=clone_id,
                summary_words=len(response.text.split()),
            )

            return response.text

        except Exception as exc:
            logger.error(
                "episodic_summary_failed",
                clone_id=clone_id,
                error=str(exc),
            )
            return None

    async def _store_episodic_memory(
        self,
        clone_id: str,
        session_id: str,
        summary: str,
        turn_count: int,
    ) -> None:
        """Store a session summary as an episodic memory embedding.

        Args:
            clone_id: The clone identifier.
            session_id: The session identifier.
            summary: The generated summary text.
            turn_count: Number of turns in the session.
        """
        try:
            from app.embedder import embed_texts
            from app.vector_store import add_documents

            # Embed the summary
            embeddings = await embed_texts(
                [summary], clone_id=clone_id, task_type="RETRIEVAL_DOCUMENT"
            )

            now = datetime.now(timezone.utc).isoformat()
            word_count = len(summary.split())

            # Store in episodic memory collection
            # Note: We use a separate collection naming pattern
            await add_documents(
                f"episodic_{clone_id}",
                chunks=[summary],
                embeddings=embeddings,
                metadatas=[
                    {
                        "clone_id": clone_id,
                        "session_id": session_id,
                        "timestamp": now,
                        "turn_count": turn_count,
                        "summary_word_count": word_count,
                        "memory_type": "episodic",
                    }
                ],
                ids=[f"episodic_{clone_id}_{session_id}"],
            )

            logger.info(
                "episodic_memory_stored",
                clone_id=clone_id,
                session_id=session_id,
                word_count=word_count,
            )

        except Exception as exc:
            logger.error(
                "episodic_memory_store_failed",
                clone_id=clone_id,
                session_id=session_id,
                error=str(exc),
            )

    # ── Tier 2: Episodic Memory Retrieval ──────────────────────────────

    async def get_episodic_context(
        self, clone_id: str, query: str
    ) -> list[str]:
        """Retrieve relevant past conversation summaries.

        Embeds the query and searches the episodic memory collection
        for the top-2 most relevant summaries.

        Args:
            clone_id: The clone identifier.
            query: The user's current query to match against.

        Returns:
            List of summary strings (max 2), empty if none found.
        """
        try:
            from app.embedder import embed_query
            from app.vector_store import query as vector_query

            query_embedding = await embed_query(query, clone_id=clone_id)
            results = await vector_query(
                f"episodic_{clone_id}",
                query_embedding,
                top_k=EPISODIC_TOP_K,
            )

            summaries = [r.text for r in results if r.similarity > 0.5]

            logger.info(
                "episodic_context_retrieved",
                clone_id=clone_id,
                results_count=len(summaries),
            )

            return summaries

        except Exception as exc:
            logger.debug(
                "episodic_context_retrieval_skipped",
                clone_id=clone_id,
                error=str(exc),
            )
            return []

    # ── Tier 3: Entity Memory ──────────────────────────────────────────

    async def _extract_and_store_entities(
        self, clone_id: str, summary: str
    ) -> None:
        """Extract entities from a summary and store them.

        Uses the LLM to extract named entities, then upserts them
        to the entity store (Supabase or in-memory fallback).

        Args:
            clone_id: The clone identifier.
            summary: The session summary to extract entities from.
        """
        try:
            from app.llm_client import generate
            from app.prompt_builder import PromptResult

            prompt = PromptResult(
                system_prompt=ENTITY_EXTRACTION_INSTRUCTION,
                user_prompt=summary,
                total_tokens=0,
                context_chunks_used=0,
                used_fallback=False,
            )

            response = await generate(
                prompt,
                clone_id=clone_id,
                session_id="entity_extraction",
            )

            # Parse JSON response
            entities = self._parse_entity_response(response.text)

            now = datetime.now(timezone.utc).isoformat()
            for entity in entities:
                record = EntityRecord(
                    entity_type=entity.get("entity_type", "unknown"),
                    entity_name=entity.get("entity_name", ""),
                    context=entity.get("context", ""),
                    last_updated=now,
                )
                if record.entity_name:
                    self._entity_store[clone_id][record.entity_name] = record

            logger.info(
                "entities_extracted",
                clone_id=clone_id,
                entity_count=len(entities),
            )

        except Exception as exc:
            logger.error(
                "entity_extraction_failed",
                clone_id=clone_id,
                error=str(exc),
            )

    def _parse_entity_response(self, text: str) -> list[dict[str, str]]:
        """Parse the LLM's entity extraction response.

        Args:
            text: Raw LLM response (expected JSON array).

        Returns:
            List of entity dicts, empty list on parse failure.
        """
        try:
            # Try to find JSON array in the response
            text = text.strip()
            if text.startswith("```"):
                # Strip markdown code blocks
                lines = text.split("\n")
                text = "\n".join(
                    line
                    for line in lines
                    if not line.strip().startswith("```")
                )

            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed
            return []
        except (json.JSONDecodeError, ValueError):
            logger.warning("entity_parse_failed", raw_text=text[:200])
            return []

    async def get_entity_context(
        self, clone_id: str, query: str
    ) -> list[dict[str, str]]:
        """Retrieve relevant entities for a query.

        Returns the top-5 most recently updated entities for the clone.

        Args:
            clone_id: The clone identifier.
            query: The user's query (used for future relevance scoring).

        Returns:
            List of entity dicts with type, name, and context.
        """
        entities = self._entity_store.get(clone_id, {})
        if not entities:
            return []

        # Return top-5 most recently updated
        sorted_entities = sorted(
            entities.values(),
            key=lambda e: e.last_updated,
            reverse=True,
        )[:ENTITY_TOP_K]

        return [
            {
                "entity_type": e.entity_type,
                "entity_name": e.entity_name,
                "context": e.context,
            }
            for e in sorted_entities
        ]


# ── Module-level singleton ─────────────────────────────────────────────

_memory_manager: MemoryManager | None = None


def get_memory_manager() -> MemoryManager:
    """Get or create the singleton MemoryManager instance."""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager
