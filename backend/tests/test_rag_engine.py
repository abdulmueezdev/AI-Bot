"""Tests for the RAG engine — vector store query and retrieval.

Asserts that:
- ChromaDB query returns correct chunks above similarity threshold.
- Empty-result path returns an empty list.
- Clone isolation is enforced via clone_id metadata filter.
- Similarity scores are correctly computed from cosine distances.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.vector_store import RetrievalResult, query, get_collection_count, add_documents


@pytest.mark.asyncio
class TestVectorQuery:
    """Tests for vector_store.query()."""

    async def test_returns_results_sorted_by_similarity(
        self, mock_chromadb_collection: MagicMock
    ) -> None:
        """Query should return results sorted by descending similarity."""
        with patch("app.vector_store._get_client") as mock_client_fn:
            client = MagicMock()
            client.get_collection.return_value = mock_chromadb_collection
            mock_client_fn.return_value = client

            results = await query("alucard", [0.1] * 768)

            assert len(results) == 2
            assert results[0].similarity >= results[1].similarity

    async def test_similarity_computed_from_distance(
        self, mock_chromadb_collection: MagicMock
    ) -> None:
        """Similarity should be 1.0 - cosine_distance."""
        with patch("app.vector_store._get_client") as mock_client_fn:
            client = MagicMock()
            client.get_collection.return_value = mock_chromadb_collection
            mock_client_fn.return_value = client

            results = await query("alucard", [0.1] * 768)

            # Distance 0.08 → similarity 0.92
            assert results[0].similarity == pytest.approx(0.92, abs=0.01)
            # Distance 0.15 → similarity 0.85
            assert results[1].similarity == pytest.approx(0.85, abs=0.01)

    async def test_empty_collection_returns_empty_list(self) -> None:
        """Query on a non-existent collection should return an empty list."""
        with patch("app.vector_store._get_client") as mock_client_fn:
            client = MagicMock()
            client.get_collection.side_effect = Exception("Collection not found")
            mock_client_fn.return_value = client

            results = await query("nonexistent", [0.1] * 768)

            assert results == []

    async def test_empty_results_from_collection(self) -> None:
        """Query returning no documents should return an empty list."""
        empty_collection = MagicMock()
        empty_collection.query.return_value = {
            "ids": [[]],
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }

        with patch("app.vector_store._get_client") as mock_client_fn:
            client = MagicMock()
            client.get_collection.return_value = empty_collection
            mock_client_fn.return_value = client

            results = await query("alucard", [0.1] * 768)

            assert results == []

    async def test_clone_isolation_enforced(
        self, mock_chromadb_collection: MagicMock
    ) -> None:
        """Query should include clone_id filter in the where clause."""
        with patch("app.vector_store._get_client") as mock_client_fn:
            client = MagicMock()
            client.get_collection.return_value = mock_chromadb_collection
            mock_client_fn.return_value = client

            await query("alucard", [0.1] * 768)

            # Verify the where filter was passed
            call_kwargs = mock_chromadb_collection.query.call_args
            assert call_kwargs.kwargs.get("where") == {"clone_id": "alucard"}

    async def test_respects_top_k_parameter(
        self, mock_chromadb_collection: MagicMock
    ) -> None:
        """Query should pass top_k as n_results to ChromaDB."""
        with patch("app.vector_store._get_client") as mock_client_fn:
            client = MagicMock()
            client.get_collection.return_value = mock_chromadb_collection
            mock_client_fn.return_value = client

            await query("alucard", [0.1] * 768, top_k=3)

            call_kwargs = mock_chromadb_collection.query.call_args
            assert call_kwargs.kwargs.get("n_results") == 3


@pytest.mark.asyncio
class TestGetCollectionCount:
    """Tests for vector_store.get_collection_count()."""

    async def test_returns_count_for_existing_collection(self) -> None:
        """Should return the document count for an existing collection."""
        collection = MagicMock()
        collection.count.return_value = 42

        with patch("app.vector_store._get_client") as mock_client_fn:
            client = MagicMock()
            client.get_collection.return_value = collection
            mock_client_fn.return_value = client

            count = await get_collection_count("alucard")

            assert count == 42

    async def test_returns_zero_for_missing_collection(self) -> None:
        """Should return 0 if the collection does not exist."""
        with patch("app.vector_store._get_client") as mock_client_fn:
            client = MagicMock()
            client.get_collection.side_effect = Exception("Not found")
            mock_client_fn.return_value = client

            count = await get_collection_count("missing")

            assert count == 0


@pytest.mark.asyncio
class TestAddDocuments:
    """Tests for vector_store.add_documents()."""

    async def test_tags_metadata_with_clone_id(self) -> None:
        """Every metadata entry should be tagged with clone_id."""
        collection = MagicMock()

        with patch("app.vector_store._get_client") as mock_client_fn:
            client = MagicMock()
            client.get_or_create_collection.return_value = collection
            mock_client_fn.return_value = client

            metadatas: list[dict[str, Any]] = [{"source_file": "test.md"}]
            await add_documents(
                "alucard",
                chunks=["test chunk"],
                embeddings=[[0.1] * 768],
                metadatas=metadatas,
                ids=["id1"],
            )

            assert metadatas[0]["clone_id"] == "alucard"

    async def test_returns_count_of_added_documents(self) -> None:
        """Should return the number of documents added."""
        collection = MagicMock()

        with patch("app.vector_store._get_client") as mock_client_fn:
            client = MagicMock()
            client.get_or_create_collection.return_value = collection
            mock_client_fn.return_value = client

            count = await add_documents(
                "alucard",
                chunks=["chunk1", "chunk2", "chunk3"],
                embeddings=[[0.1] * 768] * 3,
                metadatas=[{"source_file": "test.md"}] * 3,
                ids=["id1", "id2", "id3"],
            )

            assert count == 3
