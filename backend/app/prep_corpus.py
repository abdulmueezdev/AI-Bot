"""Prepares the corpus by injecting metadata and converting formats."""

from __future__ import annotations

import re

import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)

KAFKA_READS_MAPPING = {
    "kafka-reads-aristotle.md": {
        "philosopher": "aristotle",
        "school": "classical",
        "era": "ancient",
        "source_type": "notebookllm_synthetic",
        "original_work": "Various Works",
    },
    "kafka-reads-confucius.md": {
        "philosopher": "confucius",
        "school": "eastern",
        "era": "ancient",
        "source_type": "notebookllm_synthetic",
        "original_work": "Analects",
    },
    "kafka-reads-dostoevsky.md": {
        "philosopher": "fyodor_dostoevsky",
        "school": "existentialism",
        "era": "modern",
        "source_type": "notebookllm_synthetic",
        "original_work": "Notes from Underground",
    },
    "kafka-reads-marcus-aurelius.md": {
        "philosopher": "marcus_aurelius",
        "school": "stoicism",
        "era": "ancient",
        "source_type": "notebookllm_synthetic",
        "original_work": "Meditations",
    },
    "kafka-reads-nietzsche.md": {
        "philosopher": "friedrich_nietzsche",
        "school": "existentialism",
        "era": "modern",
        "source_type": "notebookllm_synthetic",
        "original_work": "Thus Spoke Zarathustra",
    },
    "kafka-reads-plato.md": {
        "philosopher": "plato",
        "school": "classical",
        "era": "ancient",
        "source_type": "notebookllm_synthetic",
        "original_work": "Republic",
    },
    "kafka-reads-socrates.md": {
        "philosopher": "socrates",
        "school": "classical",
        "era": "ancient",
        "source_type": "notebookllm_synthetic",
        "original_work": "Dialogues",
    },
}


def strip_markdown(text: str) -> str:
    """Strip basic markdown syntax (#, *, _, etc)."""
    # Remove bold/italic
    text = re.sub(r"(\*\*|\*|__|_)(.*?)\1", r"\2", text)
    # Remove headers
    text = re.sub(r"^#+\s+", "", text, flags=re.MULTILINE)
    # Remove links [text](url) -> text
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    return text


def format_metadata_block(metadata: dict[str, str]) -> str:
    lines = ["=== METADATA ==="]
    for k, v in metadata.items():
        lines.append(f"{k}: {v}")
    lines.append("=== END METADATA ===")
    return "\n".join(lines) + "\n\n"


def prep_corpus(clone_id: str = "alucard") -> None:
    settings = get_settings()
    data_dir = settings.get_clone_data_path(clone_id)
    output_dir = data_dir / "notebookllm"
    output_dir.mkdir(parents=True, exist_ok=True)

    files_converted = 0
    files_skipped = 0
    total_size = 0

    for item in data_dir.iterdir():
        if not item.is_file():
            continue

        filename = item.name

        if filename.endswith(".pdf"):
            logger.info("skip_pdf", clone_id=clone_id, file=filename)
            files_skipped += 1
            continue

        if filename.endswith(".txt") and item.stat().st_size == 0:
            logger.warning("skip_empty_file", clone_id=clone_id, file=filename)
            files_skipped += 1
            continue

        try:
            content = item.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(
                "file_read_error", clone_id=clone_id, file=filename, error=str(e)
            )
            files_skipped += 1
            continue

        # Check if already has metadata
        if "=== METADATA ===" in content:
            logger.info("skip_already_has_metadata", clone_id=clone_id, file=filename)
            files_skipped += 1
            continue

        out_content = ""
        out_filename = filename

        if filename in KAFKA_READS_MAPPING:
            meta = KAFKA_READS_MAPPING[filename]
            out_content = format_metadata_block(meta)
            out_content += strip_markdown(content)
            out_filename = filename.replace(".md", ".txt")
        elif filename.endswith(".txt"):
            meta = {
                "source_type": "text_corpus",
                "original_work": filename,
            }
            out_content = format_metadata_block(meta)
            out_content += content
        elif filename.endswith(".md"):
            meta = {
                "source_type": "markdown_corpus",
                "original_work": filename,
            }
            out_content = format_metadata_block(meta)
            out_content += strip_markdown(content)
            out_filename = filename.replace(".md", ".txt")
        elif filename.endswith(".json"):
            logger.info("skip_json", clone_id=clone_id, file=filename)
            files_skipped += 1
            continue
        else:
            logger.info("skip_unknown_type", clone_id=clone_id, file=filename)
            files_skipped += 1
            continue

        out_path = output_dir / out_filename
        out_path.write_text(out_content, encoding="utf-8")
        size = out_path.stat().st_size

        files_converted += 1
        total_size += size
        logger.info(
            "converted_file",
            clone_id=clone_id,
            original=filename,
            output=out_filename,
            size=size,
        )

    logger.info(
        "prep_complete",
        clone_id=clone_id,
        converted=files_converted,
        skipped=files_skipped,
        total_size_mb=round(total_size / (1024 * 1024), 2),
    )


if __name__ == "__main__":
    prep_corpus()
