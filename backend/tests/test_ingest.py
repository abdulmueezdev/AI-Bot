"""Tests for the ingest module — document loading and chunking."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from app.ingest import Chunk, _chunk_text_tiktoken, _load_and_chunk_file, parse_metadata_header

class TestChunkTextTiktoken:
    """Tests for _chunk_text_tiktoken()."""

    def test_single_section_becomes_one_chunk(self) -> None:
        """A short doc becomes a single chunk."""
        content = "This is a simple paragraph of text."
        chunks = _chunk_text_tiktoken(content, "test.md", "alucard", {})

        assert len(chunks) >= 1
        assert all(isinstance(c, Chunk) for c in chunks)
        assert chunks[0].text == "This is a simple paragraph of text."

    def test_metadata_includes_clone_id(self) -> None:
        """Every chunk should have clone_id in metadata."""
        content = "Some content."
        chunks = _chunk_text_tiktoken(content, "test.md", "alucard", {})

        for chunk in chunks:
            assert chunk.metadata["clone_id"] == "alucard"
            assert chunk.metadata["source_file"] == "test.md"
            assert "chunk_index" in chunk.metadata

    def test_empty_content_returns_empty(self) -> None:
        """Empty content should return an empty list of chunks."""
        chunks = _chunk_text_tiktoken("", "test.md", "alucard", {})
        assert chunks == []

class TestLoadAndChunkFile:
    """Tests for _load_and_chunk_file()."""

    def test_load_file_with_metadata(self, tmp_path: Path) -> None:
        file_path = tmp_path / "test.md"
        content = "=== METADATA ===\ntype: faq\n=== END METADATA ===\nSome text."
        file_path.write_text(content, encoding="utf-8")
        
        chunks = _load_and_chunk_file(file_path, "alucard")
        assert len(chunks) == 1
        assert chunks[0].text == "Some text."
        assert chunks[0].metadata.get("type") == "faq"

    def test_load_file_no_metadata(self, tmp_path: Path) -> None:
        file_path = tmp_path / "test.md"
        content = "Some text."
        file_path.write_text(content, encoding="utf-8")
        
        chunks = _load_and_chunk_file(file_path, "alucard")
        assert len(chunks) == 1
        assert chunks[0].text == "Some text."
        assert "type" not in chunks[0].metadata
