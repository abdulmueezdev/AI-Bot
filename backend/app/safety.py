"""Safety module — clone ID validation and input sanitization.

Every API boundary must call validate_clone_id() before processing.
Clone IDs are validated against a hard whitelist from config.
"""

from __future__ import annotations

import re

import structlog
from fastapi import HTTPException, status

from app.config import get_settings

logger = structlog.get_logger(__name__)


def validate_clone_id(clone_id: str) -> None:
    """Validate clone_id against the hard whitelist.

    Args:
        clone_id: The clone identifier to validate.

    Raises:
        HTTPException: 404 if clone_id is not in the whitelist.
    """
    settings = get_settings()
    normalized = clone_id.strip().lower()

    if normalized not in settings.valid_clone_ids:
        logger.warning(
            "clone_id_rejected",
            clone_id=clone_id,
            valid_ids=list(settings.valid_clone_ids),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Clone '{clone_id}' not found. Valid clones: {sorted(settings.valid_clone_ids)}",
        )


def sanitize_input(text: str) -> str:
    """Sanitize user input text.

    - Strips leading/trailing whitespace
    - Removes control characters (except newlines)
    - Truncates to max_input_length from config

    Args:
        text: Raw user input.

    Returns:
        Cleaned and truncated text.
    """
    settings = get_settings()

    # Strip whitespace
    cleaned = text.strip()

    # Remove control characters except newlines and tabs
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", cleaned)

    # Truncate to max length
    if len(cleaned) > settings.max_input_length:
        logger.warning(
            "input_truncated",
            original_length=len(cleaned),
            max_length=settings.max_input_length,
        )
        cleaned = cleaned[: settings.max_input_length]

    return cleaned
