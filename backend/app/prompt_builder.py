"""Prompt builder — hardened 7-block token-budgeted prompt assembly.

Assembles persona, calendar, entity, memory, knowledge, history,
and query into a strict token-budgeted prompt.

Token budget allocation (4,000 total hard cap):
  [SYSTEM IDENTITY BLOCK]  — max 300 tokens  — NEVER truncate
  [CALENDAR BLOCK]          — max 300 tokens  — conditional on calendar keywords
  [ENTITY BLOCK]            — max 200 tokens  — always if entities exist
  [MEMORY BLOCK]            — max 400 tokens  — top-2 episodic summaries
  [KNOWLEDGE BLOCK]         — max 1,200 tokens — top-5 RAG chunks
  [HISTORY BLOCK]           — max 800 tokens  — truncate oldest turns first
  [USER QUERY]              — max 500 tokens  — truncate if over limit
  Remaining buffer          ~300 tokens        — reserved for LLM response prefill

Uses tiktoken (cl100k_base encoding) for precise token counting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import structlog
import tiktoken

from app.config import get_settings
from app.vector_store import RetrievalResult

logger = structlog.get_logger(__name__)

# ── Token Budget Constants ─────────────────────────────────────────────

TOTAL_BUDGET: int = 4000
IDENTITY_BUDGET: int = 300
CALENDAR_BUDGET: int = 300
ENTITY_BUDGET: int = 200
MEMORY_BUDGET: int = 400
KNOWLEDGE_BUDGET: int = 1200
HISTORY_BUDGET: int = 800
QUERY_BUDGET: int = 500

# Calendar query detection keywords
CALENDAR_KEYWORDS: frozenset[str] = frozenset({
    "when", "schedule", "meeting", "available", "appointment",
    "today", "tomorrow", "this week", "free", "busy", "calendar",
})

# ── Encoding ───────────────────────────────────────────────────────────

_encoding: tiktoken.Encoding | None = None


def _get_encoding() -> tiktoken.Encoding:
    """Lazy-init the tiktoken encoding."""
    global _encoding
    if _encoding is None:
        _encoding = tiktoken.get_encoding("cl100k_base")
    return _encoding


def count_tokens(text: str) -> int:
    """Count tokens in a text string using cl100k_base encoding.

    Args:
        text: The text to count tokens for.

    Returns:
        Number of tokens.
    """
    if not text:
        return 0
    return len(_get_encoding().encode(text))


def _truncate_to_budget(text: str, max_tokens: int) -> str:
    """Truncate text from the END to fit within a token budget.

    Args:
        text: The text to truncate.
        max_tokens: Maximum allowed tokens.

    Returns:
        Truncated text.
    """
    enc = _get_encoding()
    token_ids = enc.encode(text)
    if len(token_ids) <= max_tokens:
        return text
    return enc.decode(token_ids[:max_tokens])


# ── Result Dataclass ───────────────────────────────────────────────────


@dataclass(frozen=True)
class PromptResult:
    """The assembled prompt ready for LLM submission."""

    system_prompt: str
    user_prompt: str
    total_tokens: int
    context_chunks_used: int
    used_fallback: bool = False


@dataclass
class TokenBreakdown:
    """Token count breakdown for logging."""

    identity: int = 0
    calendar: int = 0
    entity: int = 0
    memory: int = 0
    knowledge: int = 0
    history: int = 0
    query: int = 0
    total: int = 0

    def to_dict(self) -> dict[str, int]:
        """Convert to a logging-safe dict."""
        return {
            "identity": self.identity,
            "calendar": self.calendar,
            "entity": self.entity,
            "memory": self.memory,
            "knowledge": self.knowledge,
            "history": self.history,
            "query": self.query,
            "total": self.total,
        }


# ── Persona Loading ───────────────────────────────────────────────────

PERSONA_SYSTEM_TEMPLATE = """You are {clone_name}, a digital clone AI. You must ALWAYS stay in character.

{persona_text}

CRITICAL RULES:
- Never break character. Never say you are an AI, a language model, or a chatbot.
- Respond using the speaking style, vocabulary, and tone described above.
- If you don't know something, respond in character — never give a generic AI response.
- Keep responses concise but rich in character. Aim for 2-4 paragraphs.
"""

CONTEXT_TEMPLATE = """The following are relevant excerpts from your knowledge base. Use them to inform your response, but do not quote them verbatim. Synthesize naturally in your voice.

---
{context}
---"""

FALLBACK_NO_CONTEXT = (
    "I do not have sufficient knowledge to address this particular matter "
    "with the precision it deserves. The corridors of my memory, it seems, "
    "do not extend to this territory."
)

QUERY_TEMPLATE = """The person speaking to you says:
"{query}"

Respond fully in character."""


@lru_cache(maxsize=8)
def _load_persona(clone_id: str) -> str:
    """Load and cache the persona text for a clone.

    Trims to essential sections to stay within the identity token budget.

    Args:
        clone_id: The clone identifier.

    Returns:
        Persona text string.
    """
    settings = get_settings()
    persona_path = settings.get_clone_persona_path(clone_id)

    if not persona_path.exists():
        logger.warning("persona_file_missing", clone_id=clone_id, path=str(persona_path))
        return f"You are {clone_id}. Respond thoughtfully and in character."

    full_text = persona_path.read_text(encoding="utf-8")

    # Extract the most critical sections for the system prompt
    lines = full_text.splitlines()
    essential_lines: list[str] = []
    current_section_relevant = True

    for line in lines:
        if any(keyword in line.lower() for keyword in [
            "core profile", "personality", "speaking style", "tone",
            "vocabulary", "catchphrase", "guardrail", "sample dialogue",
            "archetype", "directive", "linguistic",
        ]):
            current_section_relevant = True
        elif line.startswith("6. Background") or line.startswith("7. Sample"):
            current_section_relevant = True

        if current_section_relevant:
            essential_lines.append(line)

    trimmed = "\n".join(essential_lines).strip()

    # If trimming was too aggressive, use the full text
    if count_tokens(trimmed) < 100:
        trimmed = full_text

    # Hard truncate to identity budget (leaving room for template)
    template_overhead = count_tokens(
        PERSONA_SYSTEM_TEMPLATE.format(clone_name="X", persona_text="")
    )
    persona_budget = IDENTITY_BUDGET - template_overhead
    if persona_budget < 50:
        persona_budget = 200  # Safety floor

    trimmed = _truncate_to_budget(trimmed, persona_budget)

    logger.info(
        "persona_loaded",
        clone_id=clone_id,
        tokens=count_tokens(trimmed),
    )

    return trimmed


def _get_clone_display_name(clone_id: str) -> str:
    """Get a display-friendly name for the clone.

    Args:
        clone_id: The clone identifier.

    Returns:
        Display name string.
    """
    name_map: dict[str, str] = {
        "alucard": "Alucard",
        "bob": "Bob",
        "carol": "Carol",
    }
    return name_map.get(clone_id, clone_id.capitalize())


def detect_calendar_query(message: str) -> bool:
    """Detect if a message is asking about schedule/calendar.

    Checks if any calendar keywords appear in the lowercased message.

    Args:
        message: The user's message.

    Returns:
        True if calendar-related keywords are detected.
    """
    lower = message.lower()
    return any(keyword in lower for keyword in CALENDAR_KEYWORDS)


# ── Main Build Function ───────────────────────────────────────────────


def build_prompt(
    clone_id: str,
    query: str,
    retrieval_results: list[RetrievalResult],
    *,
    below_threshold: bool = False,
    history: list[dict[str, str]] | None = None,
    calendar_context: str | None = None,
    episodic_summaries: list[str] | None = None,
    entity_context: list[dict[str, str]] | None = None,
    inject_calendar: bool | None = None,
) -> PromptResult:
    """Assemble the full prompt with strict 7-block token budgeting.

    Args:
        clone_id: The clone identifier.
        query: The user's message.
        retrieval_results: Chunks retrieved from vector store.
        below_threshold: If True, all retrieved chunks were below similarity threshold.
        history: Conversation history messages (role + content dicts).
        calendar_context: Formatted calendar schedule string.
        episodic_summaries: Past session summaries from episodic memory.
        entity_context: Structured entities from entity memory.
        inject_calendar: Override for calendar injection. Auto-detected if None.

    Returns:
        PromptResult with system and user prompts, token count, and metadata.
    """
    breakdown = TokenBreakdown()

    # ── Block 1: System Identity (NEVER truncate) ──────────────────────
    persona_text = _load_persona(clone_id)
    clone_name = _get_clone_display_name(clone_id)
    system_prompt = PERSONA_SYSTEM_TEMPLATE.format(
        clone_name=clone_name,
        persona_text=persona_text,
    )
    # Note: we do NOT truncate identity — it was pre-fitted in _load_persona
    breakdown.identity = count_tokens(system_prompt)

    # ── Block 7: User Query (truncate if over 500 tokens) ─────────────
    query_section = QUERY_TEMPLATE.format(query=query)
    if count_tokens(query_section) > QUERY_BUDGET:
        truncated_query = _truncate_to_budget(query, QUERY_BUDGET - 20)
        query_section = QUERY_TEMPLATE.format(query=truncated_query)
    breakdown.query = count_tokens(query_section)

    # ── Block 2: Calendar (conditional) ────────────────────────────────
    calendar_block = ""
    if inject_calendar is None:
        inject_calendar = detect_calendar_query(query)

    if inject_calendar and calendar_context:
        calendar_block = f"\n[SCHEDULE]\n{calendar_context}\n"
        if count_tokens(calendar_block) > CALENDAR_BUDGET:
            calendar_block = _truncate_to_budget(calendar_block, CALENDAR_BUDGET)
    breakdown.calendar = count_tokens(calendar_block)

    # ── Block 3: Entity (always if entities exist) ─────────────────────
    entity_block = ""
    if entity_context:
        entity_lines = ["[KNOWN ENTITIES]"]
        for ent in entity_context:
            entity_lines.append(
                f"• {ent.get('entity_type', 'unknown')}: "
                f"{ent.get('entity_name', '')} — {ent.get('context', '')}"
            )
        entity_block = "\n".join(entity_lines) + "\n"
        if count_tokens(entity_block) > ENTITY_BUDGET:
            entity_block = _truncate_to_budget(entity_block, ENTITY_BUDGET)
    breakdown.entity = count_tokens(entity_block)

    # ── Block 4: Memory (top-2 episodic summaries) ─────────────────────
    memory_block = ""
    if episodic_summaries:
        memory_lines = ["[PAST CONVERSATION MEMORIES]"]
        for summary in episodic_summaries[:2]:
            memory_lines.append(f"• {summary}")
        memory_block = "\n".join(memory_lines) + "\n"
        if count_tokens(memory_block) > MEMORY_BUDGET:
            memory_block = _truncate_to_budget(memory_block, MEMORY_BUDGET)
    breakdown.memory = count_tokens(memory_block)

    # ── Block 5: Knowledge (top-5 RAG chunks) ──────────────────────────
    if below_threshold or not retrieval_results:
        knowledge_section = CONTEXT_TEMPLATE.format(context=FALLBACK_NO_CONTEXT)
        context_chunks_used = 0
        used_fallback = True
    else:
        context_parts: list[str] = []
        context_tokens_used = 0
        context_chunks_used = 0

        for result in retrieval_results:
            chunk_text = f"[Source: {result.metadata.get('source_file', 'unknown')}]\n{result.text}"
            chunk_tokens = count_tokens(chunk_text)

            if context_tokens_used + chunk_tokens > KNOWLEDGE_BUDGET:
                logger.info(
                    "knowledge_budget_reached",
                    clone_id=clone_id,
                    chunks_used=context_chunks_used,
                    chunks_available=len(retrieval_results),
                    tokens_used=context_tokens_used,
                    budget=KNOWLEDGE_BUDGET,
                )
                break

            context_parts.append(chunk_text)
            context_tokens_used += chunk_tokens
            context_chunks_used += 1

        if context_parts:
            knowledge_section = CONTEXT_TEMPLATE.format(
                context="\n\n".join(context_parts)
            )
        else:
            knowledge_section = CONTEXT_TEMPLATE.format(context=FALLBACK_NO_CONTEXT)
            context_chunks_used = 0

        used_fallback = context_chunks_used == 0

    breakdown.knowledge = count_tokens(knowledge_section)

    # ── Block 6: History (truncate oldest turns first) ─────────────────
    history_block = ""
    if history:
        history_lines = ["[CONVERSATION HISTORY]"]
        # Build from newest to oldest, then reverse
        history_messages = list(history)  # copy

        # Build full history first
        for msg in history_messages:
            role = msg.get("role", "user").capitalize()
            content = msg.get("content", "")
            history_lines.append(f"{role}: {content}")

        full_history = "\n".join(history_lines) + "\n"

        if count_tokens(full_history) > HISTORY_BUDGET:
            # Truncate oldest turns first
            while (
                count_tokens("\n".join(history_lines) + "\n") > HISTORY_BUDGET
                and len(history_lines) > 2  # Keep header + at least 1 message
            ):
                history_lines.pop(1)  # Remove oldest (index 1, after header)

            history_block = "\n".join(history_lines) + "\n"
        else:
            history_block = full_history

    breakdown.history = count_tokens(history_block)

    # ── Assemble user prompt ───────────────────────────────────────────
    user_prompt_parts: list[str] = []
    if calendar_block:
        user_prompt_parts.append(calendar_block)
    if entity_block:
        user_prompt_parts.append(entity_block)
    if memory_block:
        user_prompt_parts.append(memory_block)
    user_prompt_parts.append(knowledge_section)
    if history_block:
        user_prompt_parts.append(history_block)
    user_prompt_parts.append(query_section)

    user_prompt = "\n".join(user_prompt_parts)

    # ── Final budget enforcement ───────────────────────────────────────
    total = count_tokens(system_prompt) + count_tokens(user_prompt)

    if total > TOTAL_BUDGET:
        # Last resort: reduce KNOWLEDGE BLOCK
        overshoot = total - TOTAL_BUDGET
        current_knowledge_tokens = count_tokens(knowledge_section)
        reduced_budget = max(100, current_knowledge_tokens - overshoot)
        knowledge_section = _truncate_to_budget(knowledge_section, reduced_budget)
        breakdown.knowledge = count_tokens(knowledge_section)

        # Rebuild user prompt
        user_prompt_parts_rebuild: list[str] = []
        if calendar_block:
            user_prompt_parts_rebuild.append(calendar_block)
        if entity_block:
            user_prompt_parts_rebuild.append(entity_block)
        if memory_block:
            user_prompt_parts_rebuild.append(memory_block)
        user_prompt_parts_rebuild.append(knowledge_section)
        if history_block:
            user_prompt_parts_rebuild.append(history_block)
        user_prompt_parts_rebuild.append(query_section)
        user_prompt = "\n".join(user_prompt_parts_rebuild)

    total = count_tokens(system_prompt) + count_tokens(user_prompt)
    breakdown.total = total

    # ── Log token breakdown ────────────────────────────────────────────
    logger.info(
        "prompt_assembled",
        clone_id=clone_id,
        token_breakdown=breakdown.to_dict(),
        context_chunks_used=context_chunks_used,
        used_fallback=used_fallback,
        calendar_injected=bool(calendar_block),
        entities_injected=bool(entity_block),
        memory_injected=bool(memory_block),
        history_injected=bool(history_block),
    )

    return PromptResult(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        total_tokens=total,
        context_chunks_used=context_chunks_used,
        used_fallback=used_fallback,
    )
