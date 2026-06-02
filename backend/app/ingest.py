"""Document ingestion — loads, chunks, embeds, and stores clone knowledge.

Supports: .md (semantic by headers), .csv (row-per-chunk), .json (QA pairs),
.txt (recursive splitting). All chunks are tagged with clone_id metadata.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

from app.config import get_settings
from app.embedder import embed_texts
from app.vector_store import add_documents, delete_collection

logger = structlog.get_logger(__name__)


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


async def ingest_clone_data(clone_id: str, *, force: bool = False, file_name: str | None = None) -> IngestStats:
    """Ingest all documents from a clone's data directory.

    Args:
        clone_id: The clone identifier.
        force: If True, delete existing collection before re-ingesting.

    Returns:
        IngestStats with counts and any errors.
    """
    settings = get_settings()
    start_time = time.monotonic()
    stats = IngestStats(clone_id=clone_id)

    data_dir = settings.get_clone_data_path(clone_id)
    if not data_dir.exists():
        stats.errors.append(f"Data directory not found: {data_dir}")
        logger.error("ingest_data_dir_missing", clone_id=clone_id, path=str(data_dir))
        return stats

    # Also ingest the persona file as knowledge
    persona_path = settings.get_clone_persona_path(clone_id)
    data_files: list[Path] = list(data_dir.iterdir())
    if persona_path.exists():
        data_files.append(persona_path)

    if file_name:
        data_files = [f for f in data_files if f.name == file_name]

    if force:
        await delete_collection(clone_id)
        logger.info("collection_cleared_for_reingest", clone_id=clone_id)

    # Process each file
    all_chunks: list[Chunk] = []

    for file_path in data_files:
        if file_path.is_dir():
            continue

        try:
            chunks = _load_and_chunk_file(file_path, clone_id)
            all_chunks.extend(chunks)
            stats.files_processed += 1
            logger.info(
                "file_chunked",
                clone_id=clone_id,
                file=file_path.name,
                chunks=len(chunks),
            )
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
        stats.errors.append("No chunks generated from any file")
        return stats

    # Embed all chunks in batch
    chunk_texts = [c.text for c in all_chunks]
    logger.info("embedding_start", clone_id=clone_id, total_chunks=len(chunk_texts))

    try:
        embeddings = await embed_texts(chunk_texts, clone_id=clone_id)
    except RuntimeError as exc:
        stats.errors.append(f"Embedding failed: {exc}")
        logger.error("embedding_failed", clone_id=clone_id, error=str(exc))
        return stats

    # Store in vector DB
    await add_documents(
        clone_id,
        chunks=chunk_texts,
        embeddings=embeddings,
        metadatas=[c.metadata for c in all_chunks],
        ids=[c.chunk_id for c in all_chunks],
    )

    stats.chunks_created = len(all_chunks)
    stats.elapsed_ms = (time.monotonic() - start_time) * 1000

    logger.info(
        "ingest_complete",
        clone_id=clone_id,
        files_processed=stats.files_processed,
        chunks_created=stats.chunks_created,
        errors=len(stats.errors),
        elapsed_ms=round(stats.elapsed_ms, 1),
    )

    return stats


def _load_and_chunk_file(file_path: Path, clone_id: str) -> list[Chunk]:
    """Load a file and split it into chunks based on file type.

    Args:
        file_path: Path to the source file.
        clone_id: Clone identifier for metadata tagging.

    Returns:
        List of Chunk objects.
    """
    suffix = file_path.suffix.lower()
    
    if suffix == ".pdf":
        return _chunk_pdf(file_path, clone_id)

    content = file_path.read_text(encoding="utf-8")

    if suffix == ".md" or suffix == ".txt":
        return _chunk_markdown(content, file_path.name, clone_id)
    elif suffix == ".csv":
        return _chunk_csv(content, file_path.name, clone_id)
    elif suffix == ".json":
        return _chunk_json(content, file_path.name, clone_id)
    else:
        logger.warning(
            "unsupported_file_type",
            clone_id=clone_id,
            file=file_path.name,
            suffix=suffix,
        )
        return []

def _chunk_pdf(file_path: Path, clone_id: str) -> list[Chunk]:
    """Chunk PDF — extract text and chunk it."""
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.error("pypdf_missing", clone_id=clone_id)
        return []
        
    try:
        reader = PdfReader(str(file_path))
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n\n"
        
        if not text.strip():
            logger.warning("pdf_no_text_extracted", file=file_path.name)
            
        return _chunk_markdown(text, file_path.name, clone_id)
    except Exception as e:
        logger.error("pdf_extraction_error", file=file_path.name, error=str(e))
        return []


def _chunk_markdown(content: str, filename: str, clone_id: str) -> list[Chunk]:
    """Chunk markdown by headers, preserving semantic boundaries.

    Splits on ## and ### headers. If a section exceeds chunk_size,
    it is further split on paragraph boundaries with overlap.
    """
    settings = get_settings()
    chunks: list[Chunk] = []

    # Split on headers (## or ###)
    sections = re.split(r"(?=^#{1,3}\s+)", content, flags=re.MULTILINE)

    for section_idx, section in enumerate(sections):
        section = section.strip()
        if not section:
            continue

        # If section is small enough, use it as-is
        if len(section) <= settings.chunk_size:
            chunk_id = _generate_chunk_id(clone_id, filename, section_idx, 0)
            chunks.append(Chunk(
                text=section,
                metadata={
                    "clone_id": clone_id,
                    "source_file": filename,
                    "chunk_index": len(chunks),
                    "section_index": section_idx,
                },
                chunk_id=chunk_id,
            ))
        else:
            # Split large sections on paragraph boundaries
            paragraphs = section.split("\n\n")
            current_chunk = ""

            for para_idx, para in enumerate(paragraphs):
                para = para.strip()
                if not para:
                    continue

                if len(current_chunk) + len(para) + 2 > settings.chunk_size and current_chunk:
                    chunk_id = _generate_chunk_id(clone_id, filename, section_idx, len(chunks))
                    chunks.append(Chunk(
                        text=current_chunk.strip(),
                        metadata={
                            "clone_id": clone_id,
                            "source_file": filename,
                            "chunk_index": len(chunks),
                            "section_index": section_idx,
                        },
                        chunk_id=chunk_id,
                    ))
                    # Overlap: keep last few sentences
                    overlap_text = _get_overlap(current_chunk, settings.chunk_overlap)
                    current_chunk = overlap_text + "\n\n" + para if overlap_text else para
                else:
                    current_chunk = current_chunk + "\n\n" + para if current_chunk else para

            # Flush remaining
            if current_chunk.strip():
                chunk_id = _generate_chunk_id(clone_id, filename, section_idx, len(chunks))
                chunks.append(Chunk(
                    text=current_chunk.strip(),
                    metadata={
                        "clone_id": clone_id,
                        "source_file": filename,
                        "chunk_index": len(chunks),
                        "section_index": section_idx,
                    },
                    chunk_id=chunk_id,
                ))

    return chunks


def _chunk_csv(content: str, filename: str, clone_id: str) -> list[Chunk]:
    """Chunk CSV — each row becomes a standalone chunk.

    For FAQ-style CSVs, pairs query and response together.
    """
    import io

    chunks: list[Chunk] = []
    reader = csv.DictReader(io.StringIO(content))

    for row_idx, row in enumerate(reader):
        # Combine all fields into a single text
        parts: list[str] = []
        for key, value in row.items():
            if value is not None:
                str_value = str(value).strip()
                if str_value:
                    parts.append(f"{key}: {str_value}")
        if not parts:
            continue

        text = "\n".join(parts)
        chunk_id = _generate_chunk_id(clone_id, filename, row_idx, 0)

        chunks.append(Chunk(
            text=text,
            metadata={
                "clone_id": clone_id,
                "source_file": filename,
                "chunk_index": row_idx,
                "content_type": "faq",
            },
            chunk_id=chunk_id,
        ))

    return chunks


def _chunk_json(content: str, filename: str, clone_id: str) -> list[Chunk]:
    """Chunk JSON — each QA pair or object becomes a chunk."""
    chunks: list[Chunk] = []
    data = json.loads(content)

    if not isinstance(data, list):
        data = [data]

    for item_idx, item in enumerate(data):
        if isinstance(item, dict):
            # Handle QA pair format
            if "question" in item and "answer" in item:
                text = f"Q: {item['question']}\nA: {item['answer']}"
            else:
                # Generic dict — dump all fields
                parts = [f"{k}: {v}" for k, v in item.items() if v]
                text = "\n".join(parts)
        else:
            text = str(item)

        if not text.strip():
            continue

        chunk_id = _generate_chunk_id(clone_id, filename, item_idx, 0)
        chunks.append(Chunk(
            text=text.strip(),
            metadata={
                "clone_id": clone_id,
                "source_file": filename,
                "chunk_index": item_idx,
                "content_type": "qa",
            },
            chunk_id=chunk_id,
        ))

    return chunks


def _generate_chunk_id(clone_id: str, filename: str, section: int, chunk: int) -> str:
    """Generate a deterministic, unique chunk ID."""
    raw = f"{clone_id}:{filename}:{section}:{chunk}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _get_overlap(text: str, overlap_chars: int) -> str:
    """Get the last `overlap_chars` characters of text, aligned to sentence boundary."""
    if len(text) <= overlap_chars:
        return text

    overlap_region = text[-overlap_chars:]
    # Try to align to the start of a sentence
    sentence_start = overlap_region.find(". ")
    if sentence_start != -1:
        return overlap_region[sentence_start + 2 :]

    return overlap_region
