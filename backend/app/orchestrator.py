"""Orchestrator — the full RAG pipeline from query to response.

Pipeline: validate_clone → embed_query → vector_search → check_similarity
         → build_prompt → call_llm → return_response
"""

from __future__ import annotations

import time
import uuid

import structlog

from app.config import get_settings
from app.embedder import embed_query
from app.llm_client import LLMResponse, LLMUnavailableError, generate
from app.prompt_builder import build_prompt
from app.safety import sanitize_input, validate_clone_id
from app.vector_store import query as vector_query

logger = structlog.get_logger(__name__)


class ChatResult:
    """Result of a chat interaction."""

    def __init__(
        self,
        *,
        response: str,
        clone_id: str,
        session_id: str,
        model_used: str,
        provider: str,
        context_chunks_used: int,
        latency_ms: float,
        used_fallback_context: bool,
    ) -> None:
        self.response = response
        self.clone_id = clone_id
        self.session_id = session_id
        self.model_used = model_used
        self.provider = provider
        self.context_chunks_used = context_chunks_used
        self.latency_ms = latency_ms
        self.used_fallback_context = used_fallback_context


async def handle_chat(
    clone_id: str,
    message: str,
    session_id: str | None = None,
) -> ChatResult:
    """Execute the full RAG pipeline for a chat message.

    Args:
        clone_id: The clone to interact with.
        message: The user's message.
        session_id: Optional session ID (generated if not provided).

    Returns:
        ChatResult with the response and metadata.

    Raises:
        HTTPException: If clone_id is invalid (via safety module).
        LLMUnavailableError: If all LLM providers fail.
    """
    settings = get_settings()
    start_time = time.monotonic()

    # Generate session ID if not provided
    if not session_id:
        session_id = uuid.uuid4().hex[:12]

    log = logger.bind(clone_id=clone_id, session_id=session_id)

    # Step 1: Validate clone ID
    validate_clone_id(clone_id)

    # Step 2: Sanitize input
    cleaned_message = sanitize_input(message)
    if not cleaned_message:
        return ChatResult(
            response="It seems you have sent an empty message. Even silence has weight, but I require words to proceed.",
            clone_id=clone_id,
            session_id=session_id,
            model_used="none",
            provider="none",
            context_chunks_used=0,
            latency_ms=0.0,
            used_fallback_context=False,
        )

    log.info("chat_pipeline_start", message_length=len(cleaned_message))

    # Step 3: Embed the query
    query_embedding = await embed_query(cleaned_message, clone_id=clone_id)

    # Step 4: Vector search
    retrieval_results = await vector_query(clone_id, query_embedding)

    # Step 5: Check similarity threshold
    below_threshold = True
    if retrieval_results:
        max_similarity = max(r.similarity for r in retrieval_results)
        below_threshold = max_similarity < settings.similarity_threshold
        if below_threshold:
            log.warning(
                "similarity_below_threshold",
                max_similarity=max_similarity,
                threshold=settings.similarity_threshold,
            )

    # Step 6: Build prompt
    prompt = build_prompt(
        clone_id,
        cleaned_message,
        retrieval_results,
        below_threshold=below_threshold,
    )

    # Step 7: Call LLM
    llm_response: LLMResponse = await generate(
        prompt,
        clone_id=clone_id,
        session_id=session_id,
    )

    # Step 8: Assemble result
    total_latency = (time.monotonic() - start_time) * 1000

    log.info(
        "chat_pipeline_complete",
        total_latency_ms=round(total_latency, 1),
        model_used=llm_response.model_used,
        provider=llm_response.provider,
        context_chunks=prompt.context_chunks_used,
        used_fallback=prompt.used_fallback,
        response_length=len(llm_response.text),
    )

    return ChatResult(
        response=llm_response.text,
        clone_id=clone_id,
        session_id=session_id,
        model_used=llm_response.model_used,
        provider=llm_response.provider,
        context_chunks_used=prompt.context_chunks_used,
        latency_ms=round(total_latency, 1),
        used_fallback_context=prompt.used_fallback,
    )
