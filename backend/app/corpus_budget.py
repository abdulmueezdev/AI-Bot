"""Estimates the token budget for the entire corpus before ingestion."""

from __future__ import annotations

import json
import math
from typing import Any

import structlog
import tiktoken

from app.config import get_settings
from app.ingest import parse_metadata_header

logger = structlog.get_logger(__name__)


def estimate_corpus_budget(clone_id: str = "alucard") -> dict[str, Any]:
    settings = get_settings()
    data_dir = settings.get_clone_data_path(clone_id)

    files_to_scan = []

    for f in data_dir.iterdir():
        if f.is_file() and f.suffix == ".txt":
            files_to_scan.append(f)

    notebookllm_dir = data_dir / "notebookllm"
    if notebookllm_dir.exists():
        for f in notebookllm_dir.iterdir():
            if f.is_file() and f.suffix == ".txt":
                files_to_scan.append(f)

    enc = tiktoken.get_encoding("cl100k_base")
    chunk_size = 512
    overlap = 64
    step = chunk_size - overlap

    total_files = 0
    estimated_chunks = 0
    total_bytes = 0

    by_philosopher: dict[str, int] = {}
    by_school: dict[str, int] = {}
    by_source_type: dict[str, int] = {}

    for f in files_to_scan:
        total_files += 1
        total_bytes += f.stat().st_size

        meta = parse_metadata_header(f) or {}
        philosopher = meta.get("philosopher", "unknown")
        school = meta.get("school", "unknown")
        source_type = meta.get("source_type", "unknown")

        by_philosopher[philosopher] = by_philosopher.get(philosopher, 0) + 1
        by_school[school] = by_school.get(school, 0) + 1
        by_source_type[source_type] = by_source_type.get(source_type, 0) + 1

        try:
            content = f.read_text(encoding="utf-8")
            if content.startswith("=== METADATA ==="):
                end_idx = content.find("=== END METADATA ===")
                if end_idx != -1:
                    content = content[end_idx + len("=== END METADATA ===") :].strip()

            tokens = enc.encode(content)
            if tokens:
                # Approximate number of chunks
                file_chunks = math.ceil(len(tokens) / step)
                estimated_chunks += file_chunks
        except Exception:
            pass

    estimated_mb = total_bytes / (1024 * 1024)

    report = {
        "total_files": total_files,
        "estimated_chunks": estimated_chunks,
        "estimated_mb": round(estimated_mb, 2),
        "by_philosopher": by_philosopher,
        "by_school": by_school,
        "by_source_type": by_source_type,
    }

    print("\n--- CORPUS BUDGET REPORT ---")
    print(json.dumps(report, indent=2))
    print("----------------------------\n")

    if estimated_chunks > 75000:
        raise RuntimeError(
            f"HARD STOP: Estimated chunks ({estimated_chunks}) exceeds safe limit of 75,000."
        )
    if estimated_mb > 400:
        raise RuntimeError(
            f"HARD STOP: Estimated MB ({estimated_mb}MB) exceeds safe limit of 400MB."
        )

    return report


if __name__ == "__main__":
    estimate_corpus_budget()
