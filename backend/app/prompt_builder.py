"""Prompt builder — hardened 8-block token-budgeted prompt assembly.

Assembles persona, calendar, entity, memory, knowledge, history,
few-shot examples, and query into a strict token-budgeted prompt.

Token budget allocation (4,000 total hard cap):
  [SYSTEM IDENTITY BLOCK]  — max 300 tokens  — NEVER truncate
  [FEW_SHOT BLOCK]          — max 400 tokens  — from persona YAML
  [CALENDAR BLOCK]          — max 300 tokens  — conditional on calendar keywords
  [ENTITY BLOCK]            — max 200 tokens  — always if entities exist
  [MEMORY BLOCK]            — max 400 tokens  — top-2 episodic summaries
  [KNOWLEDGE BLOCK]         — max 1,200 tokens — top-5 RAG chunks
  [HISTORY BLOCK]           — max 600 tokens  — truncate oldest turns first
  [USER QUERY]              — max 500 tokens  — truncate if over limit
  Remaining buffer          ~100 tokens        — reserved for LLM response prefill

Uses tiktoken (cl100k_base encoding) for precise token counting.
"""

from __future__ import annotations

import yaml
from dataclasses import dataclass
from functools import lru_cache

import structlog
import tiktoken

from app.config import get_settings
from app.vector_store import RetrievalResult

logger = structlog.get_logger(__name__)

# ── Token Budget Constants ─────────────────────────────────────────────

TOTAL_BUDGET: int = 3600
IDENTITY_BUDGET: int = 1500
FEW_SHOT_BUDGET: int = 800
CALENDAR_BUDGET: int = 300
ENTITY_BUDGET: int = 200
MEMORY_BUDGET: int = 400
KNOWLEDGE_BUDGET: int = 1200
HISTORY_BUDGET: int = 600
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
    """Count tokens in a text string using cl100k_base encoding."""
    if not text:
        return 0
    return len(_get_encoding().encode(text))


def _truncate_to_budget(text: str, max_tokens: int) -> str:
    """Truncate text from the END to fit within a token budget."""
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
    few_shot: int = 0
    calendar: int = 0
    entity: int = 0
    memory: int = 0
    knowledge: int = 0
    history: int = 0
    query: int = 0
    total: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "identity": self.identity,
            "few_shot": self.few_shot,
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

Respond fully in character. KEEP IT BRIEF. Never more than one short paragraph. Do not ramble."""


@dataclass
class PersonaConfig:
    system_prompt: str
    examples: str

@lru_cache(maxsize=8)
def _load_persona(clone_id: str) -> PersonaConfig:
    """Load and cache the persona text from config.yaml for a clone."""
    settings = get_settings()
    config_path = settings.get_clone_config_path(clone_id)

    if not config_path.exists():
        logger.warning("config_file_missing", clone_id=clone_id, path=str(config_path))
        return PersonaConfig(
            system_prompt=f"You are {clone_id}. Respond thoughtfully and in character.",
            examples=""
        )

    try:
        config_data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error("config_yaml_parse_error", clone_id=clone_id, error=str(e))
        return PersonaConfig(
            system_prompt=f"You are {clone_id}. Respond thoughtfully and in character.",
            examples=""
        )

    system_prompt = config_data.get("system_prompt", f"You are {clone_id}.")
    
    # Process conversation examples
    examples_list = config_data.get("conversation_examples", [])
    examples_text = ""
    if examples_list:
        example_lines = ["[CONVERSATION EXAMPLES]"]
        for ex in examples_list:
            if "user" in ex and "assistant" in ex:
                example_lines.append(f"User: {ex['user']}")
                example_lines.append(f"Assistant: {ex['assistant']}\n")
        examples_text = "\n".join(example_lines)
    
    # Hard truncate to budget
    template_overhead = count_tokens(PERSONA_SYSTEM_TEMPLATE.format(clone_name="X", persona_text=""))
    persona_budget = IDENTITY_BUDGET - template_overhead
    if persona_budget < 50:
        persona_budget = 200

    trimmed_system = _truncate_to_budget(system_prompt.strip(), persona_budget)
    
    if count_tokens(examples_text) > FEW_SHOT_BUDGET:
        examples_text = _truncate_to_budget(examples_text, FEW_SHOT_BUDGET)

    logger.info(
        "persona_loaded",
        clone_id=clone_id,
        identity_tokens=count_tokens(trimmed_system),
        few_shot_tokens=count_tokens(examples_text),
    )

    return PersonaConfig(system_prompt=trimmed_system, examples=examples_text)


def _get_clone_display_name(clone_id: str) -> str:
    """Get a display-friendly name for the clone."""
    name_map: dict[str, str] = {
        "alucard": "Franz Kafka",
        "bob": "Bob",
        "carol": "Carol",
    }
    return name_map.get(clone_id, clone_id.capitalize())


def detect_calendar_query(message: str) -> bool:
    """Detect if a message is asking about schedule/calendar."""
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
    """Assemble the full prompt with strict token budgeting."""
    breakdown = TokenBreakdown()

    # ── Block 1 & 2: System Identity & Few Shot ────────────────────────
    persona_config = _load_persona(clone_id)
    clone_name = _get_clone_display_name(clone_id)
    system_prompt = PERSONA_SYSTEM_TEMPLATE.format(
        clone_name=clone_name,
        persona_text=persona_config.system_prompt,
    )
    breakdown.identity = count_tokens(system_prompt)
    
    few_shot_block = persona_config.examples
    if few_shot_block:
        few_shot_block += "\n"
    breakdown.few_shot = count_tokens(few_shot_block)

    if few_shot_block:
        system_prompt += '\n\n' + few_shot_block

    # ── Block 8: User Query ───────────────────────────────────────────
    query_section = QUERY_TEMPLATE.format(query=query)
    if count_tokens(query_section) > QUERY_BUDGET:
        truncated_query = _truncate_to_budget(query, QUERY_BUDGET - 20)
        query_section = QUERY_TEMPLATE.format(query=truncated_query)
    breakdown.query = count_tokens(query_section)

    # ── Block 3: Calendar ──────────────────────────────────────────────
    calendar_block = ""
    if inject_calendar is None:
        inject_calendar = detect_calendar_query(query)

    if inject_calendar and calendar_context:
        calendar_block = f"\n[SCHEDULE]\n{calendar_context}\n"
        if count_tokens(calendar_block) > CALENDAR_BUDGET:
            calendar_block = _truncate_to_budget(calendar_block, CALENDAR_BUDGET)
    breakdown.calendar = count_tokens(calendar_block)

    # ── Block 4: Entity ────────────────────────────────────────────────
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

    # ── Block 5: Memory ────────────────────────────────────────────────
    memory_block = ""
    if episodic_summaries:
        memory_lines = ["[PAST CONVERSATION MEMORIES]"]
        for summary in episodic_summaries[:2]:
            memory_lines.append(f"• {summary}")
        memory_block = "\n".join(memory_lines) + "\n"
        if count_tokens(memory_block) > MEMORY_BUDGET:
            memory_block = _truncate_to_budget(memory_block, MEMORY_BUDGET)
    breakdown.memory = count_tokens(memory_block)

    # ── Block 6: Knowledge ─────────────────────────────────────────────
    if below_threshold or not retrieval_results:
        knowledge_section = CONTEXT_TEMPLATE.format(context=FALLBACK_NO_CONTEXT)
        context_chunks_used = 0
        used_fallback = True
    else:
        context_parts: list[str] = []
        context_tokens_used = 0
        context_chunks_used = 0

        for result in retrieval_results:
            if result.similarity < get_settings().similarity_threshold:
                continue

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
                continue

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

    # ── Block 7: History ───────────────────────────────────────────────
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
