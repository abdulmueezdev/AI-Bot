"""Prompt builder — assembles persona, context, and query into a token-budgeted prompt.

The assembled prompt follows this structure:
  1. System prompt — persona identity + guardrails
  2. Retrieved context — top-k chunks from vector store
  3. User query
  4. Response instruction

Total prompt is hard-capped at max_prompt_tokens (3584).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import structlog
import tiktoken

from app.config import get_settings
from app.vector_store import RetrievalResult

logger = structlog.get_logger(__name__)

# Use cl100k_base as a conservative token estimator for Llama 3.1
_encoding: tiktoken.Encoding | None = None


def _get_encoding() -> tiktoken.Encoding:
    """Lazy-init the tiktoken encoding."""
    global _encoding
    if _encoding is None:
        _encoding = tiktoken.get_encoding("cl100k_base")
    return _encoding


def count_tokens(text: str) -> int:
    """Count tokens in a text string using cl100k_base encoding.

    This is a conservative estimate for Llama 3.1 tokenization.
    The 512-token output buffer absorbs any discrepancy.
    """
    return len(_get_encoding().encode(text))


@dataclass(frozen=True)
class PromptResult:
    """The assembled prompt ready for LLM submission."""

    system_prompt: str
    user_prompt: str
    total_tokens: int
    context_chunks_used: int
    used_fallback: bool = False


# ── Persona loading ────────────────────────────────────────────────────

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

    Trims to essential sections to stay within ~800 token budget.
    """
    settings = get_settings()
    persona_path = settings.get_clone_persona_path(clone_id)

    if not persona_path.exists():
        logger.warning("persona_file_missing", clone_id=clone_id, path=str(persona_path))
        return f"You are {clone_id}. Respond thoughtfully and in character."

    full_text = persona_path.read_text(encoding="utf-8")

    # Extract the most critical sections for the system prompt
    # Keep: Core Profile, Personality, Speaking Style, Vocabulary, Catchphrases, Guardrails
    # These are the identity-defining sections
    lines = full_text.splitlines()
    essential_lines: list[str] = []
    current_section_relevant = True

    for line in lines:
        # Always include these sections
        if any(keyword in line.lower() for keyword in [
            "core profile", "personality", "speaking style", "tone",
            "vocabulary", "catchphrase", "guardrail", "sample dialogue",
            "archetype", "directive", "linguistic",
        ]):
            current_section_relevant = True
        elif line.startswith("6. Background") or line.startswith("7. Sample"):
            # Background goes to RAG, sample dialogues are useful but optional
            current_section_relevant = True

        if current_section_relevant:
            essential_lines.append(line)

    trimmed = "\n".join(essential_lines).strip()

    # If trimming was too aggressive, use the full text
    if count_tokens(trimmed) < 100:
        trimmed = full_text

    # Final safety check — hard truncate if over 1000 tokens
    tokens = count_tokens(trimmed)
    if tokens > 1000:
        enc = _get_encoding()
        token_ids = enc.encode(trimmed)[:1000]
        trimmed = enc.decode(token_ids)

    logger.info(
        "persona_loaded",
        clone_id=clone_id,
        tokens=count_tokens(trimmed),
    )

    return trimmed


def _get_clone_display_name(clone_id: str) -> str:
    """Get a display-friendly name for the clone."""
    name_map: dict[str, str] = {
        "alucard": "Alucard",
        "bob": "Bob",
        "carol": "Carol",
    }
    return name_map.get(clone_id, clone_id.capitalize())


def build_prompt(
    clone_id: str,
    query: str,
    retrieval_results: list[RetrievalResult],
    *,
    below_threshold: bool = False,
) -> PromptResult:
    """Assemble the full prompt with token budgeting.

    Args:
        clone_id: The clone identifier.
        query: The user's message.
        retrieval_results: Chunks retrieved from vector store.
        below_threshold: If True, all retrieved chunks were below similarity threshold.

    Returns:
        PromptResult with system and user prompts, token count, and metadata.
    """
    settings = get_settings()

    # 1. Build system prompt (persona)
    persona_text = _load_persona(clone_id)
    clone_name = _get_clone_display_name(clone_id)
    system_prompt = PERSONA_SYSTEM_TEMPLATE.format(
        clone_name=clone_name,
        persona_text=persona_text,
    )

    system_tokens = count_tokens(system_prompt)

    # 2. Build query section
    query_section = QUERY_TEMPLATE.format(query=query)
    query_tokens = count_tokens(query_section)

    # 3. Calculate context budget
    # Total budget = max_prompt_tokens - system_tokens - query_tokens - safety_margin
    safety_margin = 50  # Buffer for template overhead
    context_budget = settings.max_prompt_tokens - system_tokens - query_tokens - safety_margin

    # 4. Build context section
    if below_threshold or not retrieval_results:
        # Use fallback — no relevant context found
        context_section = CONTEXT_TEMPLATE.format(context=FALLBACK_NO_CONTEXT)
        context_chunks_used = 0
        used_fallback = True
    else:
        # Pack chunks until budget is exhausted (highest similarity first)
        context_parts: list[str] = []
        context_tokens_used = 0
        context_chunks_used = 0

        for result in retrieval_results:
            chunk_text = f"[Source: {result.metadata.get('source_file', 'unknown')}]\n{result.text}"
            chunk_tokens = count_tokens(chunk_text)

            if context_tokens_used + chunk_tokens > context_budget:
                # Budget exhausted — skip remaining chunks
                logger.info(
                    "context_budget_reached",
                    clone_id=clone_id,
                    chunks_used=context_chunks_used,
                    chunks_available=len(retrieval_results),
                    tokens_used=context_tokens_used,
                    budget=context_budget,
                )
                break

            context_parts.append(chunk_text)
            context_tokens_used += chunk_tokens
            context_chunks_used += 1

        if context_parts:
            context_section = CONTEXT_TEMPLATE.format(
                context="\n\n".join(context_parts)
            )
        else:
            context_section = CONTEXT_TEMPLATE.format(context=FALLBACK_NO_CONTEXT)
            context_chunks_used = 0

        used_fallback = context_chunks_used == 0

    # 5. Assemble user prompt (context + query)
    user_prompt = f"{context_section}\n\n{query_section}"

    # 6. Final token count
    total_tokens = count_tokens(system_prompt) + count_tokens(user_prompt)

    logger.info(
        "prompt_assembled",
        clone_id=clone_id,
        system_tokens=system_tokens,
        user_tokens=count_tokens(user_prompt),
        total_tokens=total_tokens,
        context_chunks_used=context_chunks_used,
        used_fallback=used_fallback,
        budget=settings.max_prompt_tokens,
    )

    return PromptResult(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        total_tokens=total_tokens,
        context_chunks_used=context_chunks_used,
        used_fallback=used_fallback,
    )
