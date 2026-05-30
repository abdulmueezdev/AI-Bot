"""ChromaDB vector store — clone-isolated collections.

Every query and upsert is scoped to a specific clone_id.
Cross-collection access is structurally impossible.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import chromadb
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)

# Module-level client (initialized on first use)
_client: chromadb.ClientAPI | None = None

# TODO(post-v1.0.0): Migrate from ChromaDB to Supabase pgvector.
# Render free tier uses an ephemeral filesystem, meaning the ChromaDB local
# store is wiped on every redeploy. For the MVP, we accept this and use a
# manual re-ingest script. For production, we must migrate to pgvector.


@dataclass(frozen=True)
class RetrievalResult:
    """A single retrieved chunk with its metadata and similarity score."""

    text: str
    metadata: dict[str, Any]
    similarity: float


def _get_client() -> chromadb.ClientAPI:
    """Get or create the ChromaDB persistent client."""
    global _client
    if _client is None:
        settings = get_settings()
        settings.chroma_path.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(settings.chroma_path))
        logger.info(
            "chromadb_initialized",
            persist_dir=str(settings.chroma_path),
        )
    return _client


def _collection_name(clone_id: str) -> str:
    """Generate the collection name for a clone.

    Each clone gets its own isolated collection.
    """
    return f"clone_{clone_id}_knowledge"


async def add_documents(
    clone_id: str,
    *,
    chunks: list[str],
    embeddings: list[list[float]],
    metadatas: list[dict[str, Any]],
    ids: list[str],
) -> int:
    """Add documents to a clone's vector collection.

    Args:
        clone_id: The clone identifier (must be validated before calling).
        chunks: List of text chunks.
        embeddings: Corresponding embedding vectors.
        metadatas: Metadata dicts for each chunk.
        ids: Unique IDs for each chunk.

    Returns:
        Number of documents added.
    """
    # Ensure clone_id is tagged in every metadata entry
    for meta in metadatas:
        meta["clone_id"] = clone_id

    def _upsert() -> int:
        client = _get_client()
        collection = client.get_or_create_collection(
            name=_collection_name(clone_id),
            metadata={"hnsw:space": "cosine"},
        )
        collection.upsert(
            ids=ids,
            documents=chunks,
            embeddings=embeddings,  # type: ignore[arg-type]
            metadatas=metadatas,  # type: ignore[arg-type]
        )
        return len(chunks)

    count = await asyncio.to_thread(_upsert)

    logger.info(
        "documents_added",
        clone_id=clone_id,
        collection=_collection_name(clone_id),
        count=count,
    )
    return count


async def query(
    clone_id: str,
    query_embedding: list[float],
    *,
    top_k: int | None = None,
) -> list[RetrievalResult]:
    """Query a clone's vector collection for similar chunks.

    Args:
        clone_id: The clone identifier — queries are strictly isolated.
        query_embedding: The query's embedding vector.
        top_k: Number of results to retrieve (defaults to config).

    Returns:
        List of RetrievalResult sorted by descending similarity.
        Empty list if the collection doesn't exist yet.
    """
    settings = get_settings()
    if top_k is None:
        top_k = settings.top_k_results

    def _query() -> list[RetrievalResult]:
        client = _get_client()
        col_name = _collection_name(clone_id)

        try:
            collection = client.get_collection(name=col_name)
        except Exception:
            logger.warning(
                "collection_not_found",
                clone_id=clone_id,
                collection=col_name,
            )
            return []

        results = collection.query(
            query_embeddings=[query_embedding],  # type: ignore[arg-type]
            n_results=top_k,
            where={"clone_id": clone_id},  # Enforce clone isolation at query level
            include=["documents", "metadatas", "distances"],
        )

        retrieval_results: list[RetrievalResult] = []

        if results["documents"] and results["documents"][0]:
            documents = results["documents"][0]
            metadatas_list = results["metadatas"][0] if results["metadatas"] else [{}] * len(documents)
            distances = results["distances"][0] if results["distances"] else [1.0] * len(documents)

            for doc, meta, distance in zip(documents, metadatas_list, distances):
                # ChromaDB cosine distance = 1 - cosine_similarity
                similarity = 1.0 - distance
                retrieval_results.append(
                    RetrievalResult(
                        text=doc,
                        metadata=meta or {},  # type: ignore[arg-type]
                        similarity=round(similarity, 4),
                    )
                )

        # Sort by descending similarity
        retrieval_results.sort(key=lambda r: r.similarity, reverse=True)

        return retrieval_results

    results = await asyncio.to_thread(_query)

    logger.info(
        "vector_query_complete",
        clone_id=clone_id,
        results_count=len(results),
        top_similarity=results[0].similarity if results else 0.0,
    )

    return results


async def get_collection_count(clone_id: str) -> int:
    """Get the number of documents in a clone's collection.

    Args:
        clone_id: The clone identifier.

    Returns:
        Document count, or 0 if collection doesn't exist.
    """
    def _count() -> int:
        client = _get_client()
        try:
            collection = client.get_collection(name=_collection_name(clone_id))
            return collection.count()
        except Exception:
            return 0

    return await asyncio.to_thread(_count)


async def delete_collection(clone_id: str) -> bool:
    """Delete a clone's entire collection (for re-ingestion).

    Args:
        clone_id: The clone identifier.

    Returns:
        True if deleted, False if collection didn't exist.
    """
    def _delete() -> bool:
        client = _get_client()
        try:
            client.delete_collection(name=_collection_name(clone_id))
            logger.info("collection_deleted", clone_id=clone_id)
            return True
        except Exception:
            return False

    return await asyncio.to_thread(_delete)
