"""Session management endpoint — /session/end/{clone_id}/{session_id}.

Triggers episodic memory flush: generates summary, stores embedding,
and extracts entities when a session explicitly ends.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.memory_manager import get_memory_manager
from app.safety import validate_clone_id

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/session", tags=["session"])


class EndSessionResponse(BaseModel):
    """Response body for the end session endpoint."""

    clone_id: str = Field(description="The clone identifier.")
    session_id: str = Field(description="The session identifier.")
    summary: str | None = Field(
        description="Generated episodic summary, or None if session was empty."
    )
    status: str = Field(description="Status: flushed or empty.")


@router.post(
    "/end/{clone_id}/{session_id}",
    response_model=EndSessionResponse,
    summary="End a chat session",
    description=(
        "Explicitly end a session, triggering episodic memory flush: "
        "generates a 100-word summary, stores it as an embedding, "
        "and extracts entities."
    ),
)
async def end_session(clone_id: str, session_id: str) -> EndSessionResponse:
    """End a session and flush memory."""
    validate_clone_id(clone_id)

    log = logger.bind(clone_id=clone_id, session_id=session_id)
    log.info("session_end_requested")

    mm = get_memory_manager()
    summary = await mm.flush_session(clone_id, session_id)

    status = "flushed" if summary else "empty"
    log.info("session_end_complete", status=status)

    return EndSessionResponse(
        clone_id=clone_id,
        session_id=session_id,
        summary=summary,
        status=status,
    )
