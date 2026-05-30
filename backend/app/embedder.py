"""Gemini embedding client — gemini-embedding-001.

All embedding operations go through this module. Supports batch embedding
with 3-retry exponential backoff. No other embedding model is permitted.
Uses the new `google-genai` SDK.
"""

from __future__ import annotations

import asyncio
import time

from google import genai
from google.genai import types
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)

# Module-level client (initialized on first use)
_client: genai.Client | None = None


def _get_client() -> genai.Client:
    """Get or create the Gemini client."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = genai.Client(api_key=settings.gemini_api_key)
        logger.info("gemini_client_initialized")
    return _client


async def embed_texts(
    texts: list[str],
    *,
    clone_id: str = "system",
    task_type: str = "RETRIEVAL_DOCUMENT",
) -> list[list[float]]:
    """Embed a batch of texts using Gemini gemini-embedding-001.

    Args:
        texts: List of text strings to embed.
        clone_id: Clone context for logging.
        task_type: RETRIEVAL_DOCUMENT for indexing, RETRIEVAL_QUERY for queries.

    Returns:
        List of embedding vectors (list of floats).

    Raises:
        RuntimeError: If all retry attempts are exhausted.
    """
    if not texts:
        return []

    # Process in batches of 20 to avoid API limits
    batch_size = 20
    all_embeddings: list[list[float]] = []

    for batch_start in range(0, len(texts), batch_size):
        batch = texts[batch_start : batch_start + batch_size]
        batch_embeddings = await _embed_batch_with_retry(
            batch,
            task_type=task_type,
            clone_id=clone_id,
            batch_index=batch_start // batch_size,
        )
        all_embeddings.extend(batch_embeddings)
        
        # Rate limit protection for free tier
        await asyncio.sleep(2.0)

    logger.info(
        "embedding_complete",
        clone_id=clone_id,
        total_texts=len(texts),
        total_embeddings=len(all_embeddings),
        dimensions=len(all_embeddings[0]) if all_embeddings else 0,
    )

    return all_embeddings


async def embed_query(
    query: str,
    *,
    clone_id: str = "system",
) -> list[float]:
    """Embed a single query string for retrieval.

    Args:
        query: The search query to embed.
        clone_id: Clone context for logging.

    Returns:
        Embedding vector as a list of floats.
    """
    results = await embed_texts(
        [query],
        clone_id=clone_id,
        task_type="RETRIEVAL_QUERY",
    )
    return results[0]


async def _embed_batch_with_retry(
    texts: list[str],
    *,
    task_type: str,
    clone_id: str,
    batch_index: int,
) -> list[list[float]]:
    """Embed a single batch with 3-retry exponential backoff.

    Returns:
        List of embedding vectors.

    Raises:
        RuntimeError: If all retries are exhausted.
    """
    settings = get_settings()
    last_error: Exception | None = None

    for attempt in range(settings.max_retries):
        try:
            start_time = time.monotonic()

            # Run the synchronous Gemini SDK call in a thread pool
            result = await asyncio.to_thread(
                _do_embed,
                texts,
                task_type=task_type,
            )

            elapsed_ms = (time.monotonic() - start_time) * 1000

            logger.info(
                "embedding_batch_success",
                clone_id=clone_id,
                batch_index=batch_index,
                batch_size=len(texts),
                latency_ms=round(elapsed_ms, 1),
                attempt=attempt + 1,
            )

            return result

        except Exception as exc:
            last_error = exc
            if attempt < settings.max_retries - 1:
                delay = settings.retry_delays[attempt]
                logger.warning(
                    "embedding_batch_retry",
                    clone_id=clone_id,
                    batch_index=batch_index,
                    attempt=attempt + 1,
                    delay_seconds=delay,
                    error=str(exc),
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "embedding_batch_failed",
                    clone_id=clone_id,
                    batch_index=batch_index,
                    attempts=settings.max_retries,
                    error=str(exc),
                )

    raise RuntimeError(
        f"Embedding failed after {settings.max_retries} attempts: {last_error}"
    )


def _do_embed(texts: list[str], *, task_type: str) -> list[list[float]]:
    """Synchronous embedding call for use in thread pool."""
    settings = get_settings()
    client = _get_client()

    result = client.models.embed_content(
        model=settings.embedding_model,
        contents=texts,  # type: ignore[arg-type]
        config=types.EmbedContentConfig(
            task_type=task_type,
            output_dimensionality=settings.embedding_dimensions,
        ),
    )

    if not result.embeddings:
        return []
    
    from typing import cast
    return [cast(list[float], emb.values) for emb in result.embeddings]
