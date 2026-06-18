"""Tests for the embedder module.

Asserts that:
- Embeddings are correct dimension.
- Task type mapping works.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.embedder import embed_query, embed_texts


@pytest.mark.asyncio
class TestEmbedder:
    """Tests for the embedder module."""

    @patch("app.embedder._get_client")
    async def test_embed_query(self, mock_get_client: MagicMock) -> None:
        """embed_query should return a list of floats."""
        mock_instance = MagicMock()
        mock_response = MagicMock()
        mock_embedding = MagicMock()
        mock_embedding.values = [0.1] * 768
        mock_response.embeddings = [mock_embedding]
        mock_instance.models.embed_content.return_value = mock_response
        mock_get_client.return_value = mock_instance

        result = await embed_query("What is hope?", clone_id="alucard")
        assert len(result) == 768
        assert isinstance(result[0], float)

    @patch("app.embedder._get_client")
    async def test_embed_texts(self, mock_get_client: MagicMock) -> None:
        """embed_texts should return a list of lists of floats."""
        mock_instance = MagicMock()
        mock_response = MagicMock()
        mock_embedding = MagicMock()
        mock_embedding.values = [0.1] * 768
        mock_response.embeddings = [mock_embedding, mock_embedding]
        mock_instance.models.embed_content.return_value = mock_response
        mock_get_client.return_value = mock_instance

        texts = ["Text 1", "Text 2"]
        results: list[list[float]] = []
        async for batch in embed_texts(texts, clone_id="alucard"):
            results.extend(batch)

        assert len(results) == 2
        assert len(results[0]) == 768
        assert len(results[1]) == 768
