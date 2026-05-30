"""Tests for the RAG engine — vector store query and retrieval.

Asserts that:
- Supabase RPC query returns correct chunks sorted by similarity.
- Empty-result path returns an empty list.
- Clone isolation is enforced via filter_clone_id parameter.
- Similarity scores are correctly extracted from RPC response.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.vector_store import query, get_collection_count, add_documents


@pytest.mark.asyncio
class TestVectorQuery:
    """Tests for vector_store.query()."""

    async def test_returns_results_sorted_by_similarity(
        self, mock_supabase_client: MagicMock
    ) -> None:
        """Query should return results sorted by descending similarity."""
        rpc_response = MagicMock()
        rpc_response.data = [
            {
                "id": "id1",
                "clone_id": "alucard",
                "content": "Alucard believes hope is the cruelest instrument.",
                "metadata": {"source_file": "diaries.md", "clone_id": "alucard"},
                "similarity": 0.92,
            },
            {
                "id": "id2",
                "clone_id": "alucard",
                "content": "The burden of knowledge is to act.",
                "metadata": {"source_file": "parables.md", "clone_id": "alucard"},
                "similarity": 0.85,
            },
        ]
        mock_supabase_client.rpc.return_value.execute.return_value = rpc_response

        with patch("app.vector_store._get_client", return_value=mock_supabase_client):
            results = await query("alucard", [0.1] * 768)

        assert len(results) == 2
        assert results[0].similarity >= results[1].similarity

    async def test_similarity_extracted_from_rpc_response(
        self, mock_supabase_client: MagicMock
    ) -> None:
        """Similarity should be extracted from the RPC response."""
        rpc_response = MagicMock()
        rpc_response.data = [
            {
                "id": "id1",
                "clone_id": "alucard",
                "content": "Hope is the cruelest instrument.",
                "metadata": {"clone_id": "alucard"},
                "similarity": 0.92,
            },
            {
                "id": "id2",
                "clone_id": "alucard",
                "content": "Knowledge is a burden.",
                "metadata": {"clone_id": "alucard"},
                "similarity": 0.85,
            },
        ]
        mock_supabase_client.rpc.return_value.execute.return_value = rpc_response

        with patch("app.vector_store._get_client", return_value=mock_supabase_client):
            results = await query("alucard", [0.1] * 768)

        assert results[0].similarity == pytest.approx(0.92, abs=0.01)
        assert results[1].similarity == pytest.approx(0.85, abs=0.01)

    async def test_empty_results_returns_empty_list(
        self, mock_supabase_client: MagicMock
    ) -> None:
        """Query returning no documents should return an empty list."""
        rpc_response = MagicMock()
        rpc_response.data = []
        mock_supabase_client.rpc.return_value.execute.return_value = rpc_response

        with patch("app.vector_store._get_client", return_value=mock_supabase_client):
            results = await query("alucard", [0.1] * 768)

        assert results == []

    async def test_rpc_exception_returns_empty_list(
        self, mock_supabase_client: MagicMock
    ) -> None:
        """Query on a failed RPC call should return an empty list."""
        mock_supabase_client.rpc.side_effect = Exception("Connection refused")

        with patch("app.vector_store._get_client", return_value=mock_supabase_client):
            results = await query("nonexistent", [0.1] * 768)

        assert results == []

    async def test_clone_isolation_enforced(
        self, mock_supabase_client: MagicMock
    ) -> None:
        """Query should pass clone_id as filter_clone_id to the RPC call."""
        rpc_response = MagicMock()
        rpc_response.data = []
        mock_supabase_client.rpc.return_value.execute.return_value = rpc_response

        with patch("app.vector_store._get_client", return_value=mock_supabase_client):
            await query("alucard", [0.1] * 768)

        # Verify clone_id was passed as filter
        call_args = mock_supabase_client.rpc.call_args
        assert call_args[0][0] == "match_documents"
        assert call_args[0][1]["filter_clone_id"] == "alucard"

    async def test_respects_top_k_parameter(
        self, mock_supabase_client: MagicMock
    ) -> None:
        """Query should pass top_k as match_count to the RPC call."""
        rpc_response = MagicMock()
        rpc_response.data = []
        mock_supabase_client.rpc.return_value.execute.return_value = rpc_response

        with patch("app.vector_store._get_client", return_value=mock_supabase_client):
            await query("alucard", [0.1] * 768, top_k=3)

        call_args = mock_supabase_client.rpc.call_args
        assert call_args[0][1]["match_count"] == 3


@pytest.mark.asyncio
class TestGetCollectionCount:
    """Tests for vector_store.get_collection_count()."""

    async def test_returns_count_for_existing_documents(
        self, mock_supabase_client: MagicMock
    ) -> None:
        """Should return the document count for a clone."""
        count_response = MagicMock()
        count_response.count = 42

        table_mock = MagicMock()
        table_mock.select.return_value = table_mock
        table_mock.eq.return_value = table_mock
        table_mock.execute.return_value = count_response
        mock_supabase_client.table.return_value = table_mock

        with patch("app.vector_store._get_client", return_value=mock_supabase_client):
            count = await get_collection_count("alucard")

        assert count == 42

    async def test_returns_zero_on_error(
        self, mock_supabase_client: MagicMock
    ) -> None:
        """Should return 0 if the query fails."""
        mock_supabase_client.table.side_effect = Exception("Connection error")

        with patch("app.vector_store._get_client", return_value=mock_supabase_client):
            count = await get_collection_count("missing")

        assert count == 0


@pytest.mark.asyncio
class TestAddDocuments:
    """Tests for vector_store.add_documents()."""

    async def test_tags_metadata_with_clone_id(
        self, mock_supabase_client: MagicMock
    ) -> None:
        """Every metadata entry should be tagged with clone_id."""
        insert_response = MagicMock()
        insert_response.data = [{}]

        table_mock = MagicMock()
        table_mock.insert.return_value = table_mock
        table_mock.execute.return_value = insert_response
        mock_supabase_client.table.return_value = table_mock

        metadatas: list[dict[str, Any]] = [{"source_file": "test.md"}]

        with patch("app.vector_store._get_client", return_value=mock_supabase_client):
            await add_documents(
                "alucard",
                chunks=["test chunk"],
                embeddings=[[0.1] * 768],
                metadatas=metadatas,
                ids=["id1"],
            )

        assert metadatas[0]["clone_id"] == "alucard"

    async def test_returns_count_of_added_documents(
        self, mock_supabase_client: MagicMock
    ) -> None:
        """Should return the number of documents added."""
        insert_response = MagicMock()
        insert_response.data = [{}, {}, {}]

        table_mock = MagicMock()
        table_mock.insert.return_value = table_mock
        table_mock.execute.return_value = insert_response
        mock_supabase_client.table.return_value = table_mock

        with patch("app.vector_store._get_client", return_value=mock_supabase_client):
            count = await add_documents(
                "alucard",
                chunks=["chunk1", "chunk2", "chunk3"],
                embeddings=[[0.1] * 768] * 3,
                metadatas=[{"source_file": "test.md"}] * 3,
                ids=["id1", "id2", "id3"],
            )

        assert count == 3
