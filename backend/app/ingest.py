"""Document ingestion — loads, chunks, embeds, and stores clone knowledge.

Supports rate limiting, state resumption, and tiktoken-based chunking.
"""

from __future__ import annotations

import asyncio
import datetime
import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog
import tiktoken

from app.config import get_settings
from app.embedder import embed_texts
from app.vector_store import add_documents, delete_collection, delete_file_chunks

logger = structlog.get_logger(__name__)


class DailyLimitReached(Exception):
    """Raised when the daily Gemini API limit is reached."""

    pass


@dataclass
class IngestStats:
    """Statistics from an ingestion run."""

    clone_id: str
    files_processed: int = 0
    chunks_created: int = 0
    errors: list[str] = field(default_factory=list)
    elapsed_ms: float = 0.0


@dataclass
class Chunk:
    """A single text chunk with metadata."""

    text: str
    metadata: dict[str, Any]
    chunk_id: str


def load_state(state_file: Path) -> dict[str, Any]:
    today = datetime.date.today().isoformat()
    if state_file.exists():
        try:
            from typing import cast

            with open(state_file, "r") as f:
                state = cast(dict[str, Any], json.load(f))
            if state.get("date") != today:
                state["date"] = today
                state["daily_api_calls"] = 0
            return state
        except Exception as e:
            logger.error("corrupt_state_file", error=str(e))

    return {
        "files_done": [],
        "chunks_ingested": 0,
        "last_file": None,
        "last_chunk_index": 0,
        "date": today,
        "daily_api_calls": 0,
    }


def save_state(state_file: Path, state: dict[str, Any]) -> None:
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)


def parse_metadata_header(file_path: Path) -> dict[str, Any] | None:
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        return None

    start_idx = content.find("=== METADATA ===")
    if start_idx == -1:
        return None

    end_idx = content.find("=== END METADATA ===", start_idx)
    if end_idx == -1:
        return None

    meta_block = content[start_idx + len("=== METADATA ===") : end_idx].strip()
    metadata = {}
    for line in meta_block.split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            metadata[k.strip()] = v.strip()
    return metadata


def _chunk_text_tiktoken(
    content: str, filename: str, clone_id: str, base_meta: dict[str, Any]
) -> list[Chunk]:
    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(content)

    chunks: list[Chunk] = []
    chunk_size = 512
    overlap = 64
    step = chunk_size - overlap

    if not tokens:
        return chunks

    for i in range(0, len(tokens), step):
        chunk_tokens = tokens[i : i + chunk_size]
        text = enc.decode(chunk_tokens)

        meta = base_meta.copy()
        meta["clone_id"] = clone_id
        meta["source_file"] = filename
        meta["chunk_index"] = len(chunks)

        chunk_id_raw = f"{filename}:{len(chunks)}:{text[:50]}"
        chunk_id = hashlib.sha256(chunk_id_raw.encode("utf-8")).hexdigest()[:16]

        chunks.append(Chunk(text=text.strip(), metadata=meta, chunk_id=chunk_id))

    return chunks


def _load_and_chunk_file(file_path: Path, clone_id: str) -> list[Chunk]:
    """Load a file, parse metadata, and split it into chunks."""

    base_meta = parse_metadata_header(file_path) or {}

    try:
        content = file_path.read_text(encoding="utf-8")
        start_idx = content.find("=== METADATA ===")
        if start_idx != -1:
            end_idx = content.find("=== END METADATA ===", start_idx)
            if end_idx != -1:
                content = content[:start_idx] + content[end_idx + len("=== END METADATA ===") :]
                content = content.strip()
    except Exception as e:
        logger.error("file_read_error", file=file_path.name, error=str(e))
        return []

    return _chunk_text_tiktoken(content, file_path.name, clone_id, base_meta)


async def ingest_clone_data(
    clone_id: str, *, force: bool = False, file_name: str | None = None
) -> IngestStats:
    settings = get_settings()
    start_time = time.monotonic()
    stats = IngestStats(clone_id=clone_id)

    data_dir = settings.get_clone_data_path(clone_id)
    if not data_dir.exists():
        stats.errors.append(f"Data directory not found: {data_dir}")
        logger.error("ingest_data_dir_missing", clone_id=clone_id, path=str(data_dir))
        return stats

    state_file = data_dir.parent / "ingestion_state.json"
    state = load_state(state_file)

    today = datetime.date.today().isoformat()
    if state.get("date") != today:
        state["date"] = today
        state["daily_api_calls"] = 0
        state["daily_tokens"] = 0
        save_state(state_file, state)

    if force:
        state["files_done"] = []
        state["last_file"] = None
        state["last_chunk_index"] = 0
        state["chunks_ingested"] = 0
        save_state(state_file, state)
        if file_name:
            await delete_file_chunks(clone_id, file_name)
        else:
            await delete_collection(clone_id)

    data_files: list[Path] = []
    for f in data_dir.iterdir():
        if f.is_file():
            data_files.append(f)
    notebookllm_dir = data_dir / "notebookllm"
    if notebookllm_dir.exists():
        for f in notebookllm_dir.iterdir():
            if f.is_file():
                data_files.append(f)

    persona_path = settings.get_clone_persona_path(clone_id)
    if persona_path.exists() and persona_path not in data_files:
        data_files.append(persona_path)

    if file_name:
        data_files = [f for f in data_files if f.name == file_name]

    # Pre-filtering step: Only process philosophy files
    philosophy_keywords = [
        "aristotle", "confucius", "dostoevsky", "marcus", "nietzsche", 
        "plato", "socrates", "philosophy", "stoic", "existential"
    ]
    data_files = [
        f for f in data_files 
        if any(keyword in f.name.lower() for keyword in philosophy_keywords)
        and f.suffix.lower() in ['.txt', '.md']
    ]

    # Sort files to ensure deterministic resumption
    data_files.sort(key=lambda p: p.name)


    all_chunks: list[Chunk] = []

    for file_path in data_files:
        if file_path.name in state["files_done"]:
            continue

        try:
            chunks = _load_and_chunk_file(file_path, clone_id)

            if state["last_file"] == file_path.name:
                chunks = chunks[state["last_chunk_index"] :]

            if chunks:
                all_chunks.extend(chunks)
                stats.files_processed += 1
                logger.info(
                    "file_chunked",
                    clone_id=clone_id,
                    file=file_path.name,
                    chunks=len(chunks),
                )
            else:
                if state["last_file"] != file_path.name:
                    state["files_done"].append(file_path.name)
        except Exception as exc:
            error_msg = f"Failed to process {file_path.name}: {exc}"
            stats.errors.append(error_msg)
            logger.error(
                "file_chunk_error",
                clone_id=clone_id,
                file=file_path.name,
                error=str(exc),
            )

    if not all_chunks:
        save_state(state_file, state)
        return stats

    chunk_texts = [c.text for c in all_chunks]
    logger.info("embedding_start", clone_id=clone_id, total_chunks=len(chunk_texts))

    batch_size = 15
    total_batches = (len(all_chunks) + batch_size - 1) // batch_size
    eta_hours = total_batches // 60
    eta_mins = total_batches % 60
    logger.info(
        "eta_estimate",
        message=f"Estimated completion: {eta_hours} hours {eta_mins} minutes from now",
    )

    try:
        batch_counter = 0
        for batch_start in range(0, len(all_chunks), batch_size):
            batch_counter += 1
            batch_chunks = all_chunks[batch_start : batch_start + batch_size]
            
            # Check the 930 API calls (chunks) limit BEFORE processing the batch
            if state.get("daily_api_calls", 0) + len(batch_chunks) > 930:
                save_state(state_file, state)
                logger.info(
                    "ingestion_paused_daily_limit",
                    clone_id=clone_id,
                    message="Daily target of 930 chunks reached. Pausing to preserve testing quota."
                )
                print("⏸️ INGESTION PAUSED — Daily target of 930 chunks reached. Pausing to preserve testing quota.")
                return stats
                
            state["daily_api_calls"] = state.get("daily_api_calls", 0) + len(batch_chunks)
            batch_texts = [c.text for c in batch_chunks]

            async for batch_embeddings, tokens_consumed in embed_texts(
                batch_texts, clone_id=clone_id
            ):
                state["daily_tokens"] = state.get("daily_tokens", 0) + tokens_consumed

                remaining_batches = (
                    len(all_chunks) - batch_start + batch_size - 1
                ) // batch_size
                current_total = state.get("chunks_ingested", 0) + len(batch_embeddings)

                logger.info(
                    "batch_metrics",
                    clone_id=clone_id,
                    message=f"Batch {batch_counter}: {len(batch_chunks)} chunks embedded ({current_total} total). RPM: {len(batch_chunks)}/100. ETA: {remaining_batches} minutes remaining.",
                )
                await add_documents(
                    clone_id,
                    chunks=batch_texts,
                    embeddings=batch_embeddings,
                    metadatas=[c.metadata for c in batch_chunks],
                    ids=[c.chunk_id for c in batch_chunks],
                )

                stats.chunks_created += len(batch_embeddings)

                last_chunk = batch_chunks[-1]
                state["chunks_ingested"] += len(batch_embeddings)
                state["last_file"] = last_chunk.metadata["source_file"]
                state["last_chunk_index"] = last_chunk.metadata["chunk_index"] + 1

                files_in_batch = set([c.metadata["source_file"] for c in batch_chunks])
                for fname in files_in_batch:
                    file_chunks = [
                        c for c in all_chunks if c.metadata["source_file"] == fname
                    ]
                    if file_chunks and file_chunks[-1] in batch_chunks:
                        if fname not in state["files_done"]:
                            state["files_done"].append(fname)

                save_state(state_file, state)

                # If there are more chunks, wait 60s
                if batch_start + batch_size < len(all_chunks):
                    logger.info(
                        "waiting_for_rate_limit",
                        message="Waiting 60s before next batch...",
                    )
                    await asyncio.sleep(60)

    except DailyLimitReached:
        raise
    except RuntimeError as exc:
        if "Quota depleted" in str(exc):
            save_state(state_file, state)
            logger.info("ingestion_paused_daily_limit", clone_id=clone_id)
            print("⏸️ INGESTION PAUSED — Resume tomorrow.")
            return stats
        else:
            stats.errors.append(f"Embedding failed at chunk {batch_start}: {exc}")
            logger.error("embedding_failed", clone_id=clone_id, error=str(exc))

    stats.elapsed_ms = (time.monotonic() - start_time) * 1000

    logger.info(
        "ingest_complete",
        clone_id=clone_id,
        files_processed=stats.files_processed,
        chunks_created=stats.chunks_created,
        errors=len(stats.errors),
        elapsed_ms=round(stats.elapsed_ms, 1),
    )

    print(
        f"INGESTION_COMPLETE — {state.get('chunks_ingested', 0)} total chunks, {state.get('daily_tokens', 0)} total tokens, {state.get('daily_api_calls', 0)} API calls over N days."
    )

    return stats
