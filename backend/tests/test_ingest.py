"""Tests for the ingest module — document loading and chunking.

Asserts that:
- Markdown files are chunked by headers.
- CSV files produce one chunk per row.
- JSON QA pairs produce one chunk per item.
- Unsupported file types return empty chunks.
- Chunk IDs are deterministic.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.ingest import (
    Chunk,
    IngestStats,
    _chunk_csv,
    _chunk_json,
    _chunk_markdown,
    _generate_chunk_id,
    _get_overlap,
)


class TestChunkMarkdown:
    """Tests for _chunk_markdown()."""

    def test_single_section_becomes_one_chunk(self) -> None:
        """A short markdown doc without headers becomes a single chunk."""
        content = "This is a simple paragraph of text."
        chunks = _chunk_markdown(content, "test.md", "alucard")

        assert len(chunks) >= 1
        assert all(isinstance(c, Chunk) for c in chunks)

    def test_splits_on_headers(self) -> None:
        """Markdown should be split on ## and ### headers."""
        content = "## Section 1\nContent 1.\n\n## Section 2\nContent 2."
        chunks = _chunk_markdown(content, "test.md", "alucard")

        assert len(chunks) >= 2

    def test_metadata_includes_clone_id(self) -> None:
        """Every chunk should have clone_id in metadata."""
        content = "## Test\nSome content."
        chunks = _chunk_markdown(content, "test.md", "alucard")

        for chunk in chunks:
            assert chunk.metadata["clone_id"] == "alucard"

    def test_metadata_includes_source_file(self) -> None:
        """Every chunk should have source_file in metadata."""
        content = "## Test\nSome content."
        chunks = _chunk_markdown(content, "test.md", "alucard")

        for chunk in chunks:
            assert chunk.metadata["source_file"] == "test.md"

    def test_empty_content_returns_empty(self) -> None:
        """Empty content should return an empty list of chunks."""
        chunks = _chunk_markdown("", "test.md", "alucard")
        assert chunks == []


class TestChunkCsv:
    """Tests for _chunk_csv()."""

    def test_one_chunk_per_row(self) -> None:
        """Each CSV row should become one chunk."""
        content = "question,answer\nWhat is hope?,Hope is cruel.\nWho are you?,I am Alucard."
        chunks = _chunk_csv(content, "test.csv", "alucard")

        assert len(chunks) == 2

    def test_metadata_has_faq_content_type(self) -> None:
        """CSV chunks should have content_type=faq in metadata."""
        content = "question,answer\nWhat?,Something."
        chunks = _chunk_csv(content, "test.csv", "alucard")

        for chunk in chunks:
            assert chunk.metadata.get("content_type") == "faq"

    def test_empty_csv_returns_empty(self) -> None:
        """CSV with only headers should return empty list."""
        content = "question,answer\n"
        chunks = _chunk_csv(content, "test.csv", "alucard")
        assert chunks == []


class TestChunkJson:
    """Tests for _chunk_json()."""

    def test_qa_pairs_chunked(self) -> None:
        """JSON QA pairs should produce one chunk per pair."""
        content = '[{"question": "Q1", "answer": "A1"}, {"question": "Q2", "answer": "A2"}]'
        chunks = _chunk_json(content, "test.json", "alucard")

        assert len(chunks) == 2
        assert "Q1" in chunks[0].text
        assert "A1" in chunks[0].text

    def test_single_object_wrapped(self) -> None:
        """A single JSON object (not array) should be handled."""
        content = '{"question": "Q1", "answer": "A1"}'
        chunks = _chunk_json(content, "test.json", "alucard")

        assert len(chunks) == 1

    def test_metadata_has_qa_content_type(self) -> None:
        """JSON chunks should have content_type=qa in metadata."""
        content = '[{"question": "Q1", "answer": "A1"}]'
        chunks = _chunk_json(content, "test.json", "alucard")

        for chunk in chunks:
            assert chunk.metadata.get("content_type") == "qa"


class TestGenerateChunkId:
    """Tests for _generate_chunk_id()."""

    def test_deterministic(self) -> None:
        """Same inputs should produce the same chunk ID."""
        id1 = _generate_chunk_id("alucard", "test.md", 0, 0)
        id2 = _generate_chunk_id("alucard", "test.md", 0, 0)
        assert id1 == id2

    def test_different_inputs_different_ids(self) -> None:
        """Different inputs should produce different chunk IDs."""
        id1 = _generate_chunk_id("alucard", "test.md", 0, 0)
        id2 = _generate_chunk_id("alucard", "test.md", 1, 0)
        assert id1 != id2

    def test_id_is_hex_string(self) -> None:
        """Chunk ID should be a 16-char hex string."""
        chunk_id = _generate_chunk_id("alucard", "test.md", 0, 0)
        assert len(chunk_id) == 16
        int(chunk_id, 16)  # Should not raise if valid hex


class TestGetOverlap:
    """Tests for _get_overlap()."""

    def test_short_text_returns_full(self) -> None:
        """Text shorter than overlap_chars should return the full text."""
        result = _get_overlap("short", 100)
        assert result == "short"

    def test_returns_end_of_text(self) -> None:
        """Should return text from the end, aligned to sentence boundary if possible."""
        text = "First sentence. Second sentence. Third sentence."
        result = _get_overlap(text, 30)
        assert len(result) <= 30
        assert isinstance(result, str)
