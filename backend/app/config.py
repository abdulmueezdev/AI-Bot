"""Application configuration — all settings from environment variables.

Uses pydantic-settings to load, validate, and type-check every config value.
No secrets are ever hardcoded. No defaults for API keys.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import FrozenSet

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration loaded exclusively from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM Providers ──────────────────────────────────────────────────
    groq_api_key: str = Field(..., description="Groq API key for Llama 3.1")
    openrouter_api_key: str = Field(..., description="OpenRouter fallback API key")

    # ── Embedding Provider ─────────────────────────────────────────────
    gemini_api_key: str = Field(..., description="Google Gemini API key")

    # ── Model Selection ────────────────────────────────────────────────
    groq_model: str = Field(
        default="llama-3.3-70b-versatile",
        description="Primary Groq model identifier",
    )
    openrouter_model: str = Field(
        default="meta-llama/llama-4-scout-17b-16e-instruct",
        description="Fallback OpenRouter model identifier",
    )
    embedding_model: str = Field(
        default="models/gemini-embedding-001",
        description="Gemini embedding model identifier",
    )
    embedding_dimensions: int = Field(
        default=768,
        description="Output dimensionality for embeddings",
    )

    # ── Token Budget ───────────────────────────────────────────────────
    max_total_tokens: int = Field(default=4096, description="Hard ceiling for prompt + output")
    max_output_tokens: int = Field(default=512, description="Max tokens for LLM response")
    max_prompt_tokens: int = Field(default=3584, description="Max tokens for assembled prompt")

    # ── RAG Settings ───────────────────────────────────────────────────
    similarity_threshold: float = Field(
        default=0.55,
        description="Minimum cosine similarity for retrieval",
    )
    top_k_results: int = Field(default=5, description="Number of chunks to retrieve")
    chunk_size: int = Field(default=1024, description="Target chunk size in characters")
    chunk_overlap: int = Field(default=64, description="Overlap between chunks in characters")

    # ── LLM Generation ─────────────────────────────────────────────────
    llm_temperature: float = Field(default=0.7, description="LLM sampling temperature")

    # ── Retry Settings ─────────────────────────────────────────────────
    max_retries: int = Field(default=3, description="Max retry attempts for external APIs")
    retry_delays: list[float] = Field(
        default=[15.0, 30.0, 60.0],
        description="Exponential backoff delays in seconds",
    )

    # ── Storage ────────────────────────────────────────────────────────
    chroma_persist_dir: str = Field(
        default="./chroma_data",
        description="ChromaDB persistent storage directory (legacy, unused after Supabase migration)",
    )
    clone_data_dir: str = Field(
        default="./clones",
        description="Root directory for clone data",
    )

    # ── Supabase ───────────────────────────────────────────────────────
    supabase_url: str = Field(
        default="",
        description="Supabase project URL",
    )
    supabase_key: str = Field(
        default="",
        description="Supabase anon/public API key",
    )

    # ── Application ────────────────────────────────────────────────────
    environment: str = Field(default="development", description="Runtime environment")
    log_level: str = Field(default="INFO", description="Logging level")
    app_version: str = Field(default="0.1.0", description="Application version")
    max_input_length: int = Field(default=2000, description="Max user message length in chars")

    # ── Clone Whitelist ────────────────────────────────────────────────
    valid_clone_ids: FrozenSet[str] = Field(
        default=frozenset({"alucard"}),
        description="Hard whitelist of valid clone identifiers",
    )

    @property
    def chroma_path(self) -> Path:
        """Resolved ChromaDB storage path."""
        return Path(self.chroma_persist_dir).resolve()

    @property
    def clones_path(self) -> Path:
        """Resolved clones data root path."""
        return Path(self.clone_data_dir).resolve()

    def get_clone_data_path(self, clone_id: str) -> Path:
        """Get the data directory for a specific clone."""
        return self.clones_path / clone_id / "data"

    def get_clone_persona_path(self, clone_id: str) -> Path:
        """Get the persona file path for a specific clone."""
        return self.clones_path / clone_id / "persona_v1.txt"

    def get_clone_config_path(self, clone_id: str) -> Path:
        """Get the config.yaml path for a specific clone."""
        return self.clones_path / clone_id / "config.yaml"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton settings instance — cached after first call."""
    # Resolve .env path relative to the backend directory
    backend_dir = Path(__file__).resolve().parent.parent
    env_path = backend_dir / ".env"
    if env_path.exists():
        os.environ.setdefault("ENV_FILE", str(env_path))
    return Settings(_env_file=str(env_path) if env_path.exists() else None)  # type: ignore[call-arg]
