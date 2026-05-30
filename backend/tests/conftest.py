"""Shared test fixtures for the Digital Clone AI Chatbot test suite.

Provides mocked settings, retrieval results, prompt results, and
environment patches so no real API calls are ever made during testing.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

# Patch environment variables BEFORE any app imports
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("OPENROUTER_API_KEY", "test-openrouter-key")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("LOG_LEVEL", "DEBUG")
os.environ.setdefault("CHROMA_PERSIST_DIR", "/tmp/test_chroma")
os.environ.setdefault("CLONE_DATA_DIR", "/tmp/test_clones")


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Generator[None, None, None]:
    """Clear the lru_cache on get_settings before every test."""
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def mock_settings() -> Any:
    """Return a Settings instance with test-safe defaults."""
    from app.config import Settings

    return Settings(
        groq_api_key="test-groq-key",
        openrouter_api_key="test-openrouter-key",
        gemini_api_key="test-gemini-key",
        environment="testing",
        log_level="DEBUG",
        chroma_persist_dir="/tmp/test_chroma",
        clone_data_dir="/tmp/test_clones",
        valid_clone_ids=frozenset({"alucard", "testclone"}),
    )


@pytest.fixture()
def mock_retrieval_results() -> list[Any]:
    """Return a list of mock RetrievalResult objects for prompt building tests."""
    from app.vector_store import RetrievalResult

    return [
        RetrievalResult(
            text="Alucard believes that hope is the cruelest instrument.",
            metadata={"source_file": "diaries.md", "clone_id": "alucard"},
            similarity=0.92,
        ),
        RetrievalResult(
            text="The burden of knowledge is to act on what you know.",
            metadata={"source_file": "parables.md", "clone_id": "alucard"},
            similarity=0.85,
        ),
        RetrievalResult(
            text="Alucard studied at multiple institutions across continents.",
            metadata={"source_file": "biography.md", "clone_id": "alucard"},
            similarity=0.78,
        ),
    ]


@pytest.fixture()
def mock_low_similarity_results() -> list[Any]:
    """Return retrieval results all below the default similarity threshold."""
    from app.vector_store import RetrievalResult

    return [
        RetrievalResult(
            text="Unrelated text about weather patterns.",
            metadata={"source_file": "random.md", "clone_id": "alucard"},
            similarity=0.30,
        ),
    ]


@pytest.fixture()
def mock_prompt_result() -> Any:
    """Return a mock PromptResult for LLM client tests."""
    from app.prompt_builder import PromptResult

    return PromptResult(
        system_prompt="You are Alucard, a digital clone AI.",
        user_prompt="The person speaking to you says: 'Hello'\nRespond fully in character.",
        total_tokens=150,
        context_chunks_used=2,
        used_fallback=False,
    )


@pytest.fixture()
def mock_chromadb_collection() -> MagicMock:
    """Return a mock ChromaDB collection with query support."""
    collection = MagicMock()
    collection.count.return_value = 42
    collection.query.return_value = {
        "ids": [["id1", "id2"]],
        "documents": [
            [
                "Alucard believes hope is the cruelest instrument.",
                "The burden of knowledge is to act.",
            ]
        ],
        "metadatas": [
            [
                {"clone_id": "alucard", "source_file": "diaries.md"},
                {"clone_id": "alucard", "source_file": "parables.md"},
            ]
        ],
        "distances": [[0.08, 0.15]],
    }
    return collection


@pytest.fixture()
def tmp_persona_file(tmp_path: Path) -> Path:
    """Create a temporary persona file for testing."""
    persona_dir = tmp_path / "clones" / "alucard"
    persona_dir.mkdir(parents=True)
    persona_file = persona_dir / "persona_v1.txt"
    persona_file.write_text(
        "## Core Profile\n"
        "Name: Alucard\n"
        "Archetype: The Dark Philosopher\n\n"
        "## Personality\n"
        "Brooding, intellectual, sardonic.\n\n"
        "## Speaking Style\n"
        "Formal, archaic vocabulary.\n\n"
        "## Guardrails\n"
        "Never break character.\n",
        encoding="utf-8",
    )
    return persona_file
