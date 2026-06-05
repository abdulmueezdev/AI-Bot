"""Supabase pgvector store — clone-isolated document storage.

Every query and upsert is scoped to a specific clone_id.
Cross-collection access is structurally impossible because
every RPC call filters on clone_id.

Migration note: Replaced ChromaDB (ephemeral local storage) with
Supabase pgvector (persistent cloud storage) in Phase 4A.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import structlog
from supabase import Client, create_client

from app.config import get_settings

logger = structlog.get_logger(__name__)

# Module-level client (initialized on first use)
_client: Client | None = None


@dataclass(frozen=True)
class RetrievalResult:
    """A single retrieved chunk with its metadata and similarity score."""

    text: str
    metadata: dict[str, Any]
    similarity: float


def _get_client() -> Client:
    """Get or create the Supabase client."""
    global _client
    if _client is None:
        settings = get_settings()
        if not settings.supabase_url or not settings.supabase_key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_KEY must be set in environment variables."
            )
        _client = create_client(settings.supabase_url, settings.supabase_key)
        logger.info(
            "supabase_initialized",
            url=settings.supabase_url[:30] + "...",
        )
    return _client


async def add_documents(
    clone_id: str,
    *,
    chunks: list[str],
    embeddings: list[list[float]],
    metadatas: list[dict[str, Any]],
    ids: list[str],
) -> int:
    """Add documents to a clone's vector collection in Supabase.

    Args:
        clone_id: The clone identifier (must be validated before calling).
        chunks: List of text chunks.
        embeddings: Corresponding embedding vectors.
        metadatas: Metadata dicts for each chunk.
        ids: Unique IDs for each chunk (used in metadata, not as PK).

    Returns:
        Number of documents added.
    """
    client = _get_client()

    # Ensure clone_id is tagged in every metadata entry
    for meta in metadatas:
        meta["clone_id"] = clone_id

    rows = []
    for chunk, embedding, meta, doc_id in zip(chunks, embeddings, metadatas, ids):
        meta_with_id = {**meta, "doc_id": doc_id}
        rows.append(
            {
                "clone_id": clone_id,
                "content": chunk,
                "embedding": json.dumps(embedding),
                "metadata": meta_with_id,
            }
        )

    # Batch insert
    client.table("documents").insert(rows).execute()

    logger.info(
        "documents_added",
        clone_id=clone_id,
        count=len(rows),
    )
    return len(rows)


async def query(
    clone_id: str,
    query_embedding: list[float],
    *,
    top_k: int | None = None,
) -> list[RetrievalResult]:
    """Query a clone's documents for similar chunks via Supabase RPC.

    Args:
        clone_id: The clone identifier — queries are strictly isolated.
        query_embedding: The query's embedding vector.
        top_k: Number of results to retrieve (defaults to config).

    Returns:
        List of RetrievalResult sorted by descending similarity.
        Empty list if no matching documents exist.
    """
    settings = get_settings()
    if top_k is None:
        top_k = settings.top_k_results

    client = _get_client()

    try:
        response = client.rpc(
            "match_documents",
            {
                "query_embedding": json.dumps(query_embedding),
                "match_count": top_k,
                "filter_clone_id": clone_id,
            },
        ).execute()
    except Exception as exc:
        logger.warning(
            "vector_query_failed",
            clone_id=clone_id,
            error=str(exc),
        )
        return []

    results: list[RetrievalResult] = []
    if response.data:
        for row in response.data:
            results.append(
                RetrievalResult(
                    text=row["content"],
                    metadata=row.get("metadata") or {},
                    similarity=round(float(row["similarity"]), 4),
                )
            )

    # Sort by descending similarity (RPC already does this, but be safe)
    results.sort(key=lambda r: r.similarity, reverse=True)

    logger.info(
        "vector_query_complete",
        clone_id=clone_id,
        results_count=len(results),
        top_similarity=results[0].similarity if results else 0.0,
    )

    return results


async def get_collection_count(clone_id: str) -> int:
    """Get the number of documents for a clone.

    Args:
        clone_id: The clone identifier.

    Returns:
        Document count, or 0 if no documents exist.
    """
    client = _get_client()
    try:
        response = (
            client.table("documents")
            .select("id", count="exact")  # type: ignore[arg-type]
            .eq("clone_id", clone_id)
            .execute()
        )
        return response.count or 0
    except Exception:
        return 0


async def get_file_chunk_count(clone_id: str, file_name: str) -> int:
    """Get the number of documents for a specific file in a clone's collection.

    Args:
        clone_id: The clone identifier.
        file_name: The source file name to check.

    Returns:
        Document count for the file, or 0 if no documents exist.
    """
    client = _get_client()
    try:
        response = (
            client.table("documents")
            .select("id", count="exact")  # type: ignore[arg-type]
            .eq("clone_id", clone_id)
            .eq("metadata->>source_file", file_name)
            .execute()
        )
        return response.count or 0
    except Exception:
        return 0


async def delete_collection(clone_id: str) -> bool:
    """Delete all documents for a clone (for re-ingestion).

    Args:
        clone_id: The clone identifier.

    Returns:
        True if any rows were deleted, False otherwise.
    """
    client = _get_client()
    try:
        response = (
            client.table("documents")
            .delete()
            .eq("clone_id", clone_id)
            .execute()
        )
        deleted = len(response.data) > 0 if response.data else False
        if deleted:
            logger.info("collection_deleted", clone_id=clone_id)
        return deleted
    except Exception:
        return False
