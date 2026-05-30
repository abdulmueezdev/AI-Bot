"""Calendar status endpoint — /calendar/status/{persona_id}.

Returns cache age, event count, and last sync timestamp
for a given persona's calendar integration.
"""

from __future__ import annotations


import structlog
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.calendar_sync import get_calendar_sync

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/calendar", tags=["calendar"])


class CalendarStatusResponse(BaseModel):
    """Response body for the calendar status endpoint."""

    clone_id: str = Field(description="The clone/persona identifier.")
    cache_age_seconds: float = Field(
        description="Seconds since last cache refresh. -1 if never synced."
    )
    event_count: int = Field(description="Number of cached events.")
    last_sync_timestamp: str | None = Field(
        description="ISO timestamp of last sync."
    )
    sync_error: str | None = Field(
        description="Last sync error message, if any."
    )
    status: str = Field(description="Cache status: fresh, stale, or never_synced.")


@router.get(
    "/status/{persona_id}",
    response_model=CalendarStatusResponse,
    summary="Get calendar sync status",
    description="Returns cache age, event count, and last sync timestamp.",
)
async def calendar_status(persona_id: str) -> CalendarStatusResponse:
    """Get the calendar sync status for a persona."""
    sync = get_calendar_sync()
    status = sync.get_cache_status(persona_id)

    logger.info(
        "calendar_status_requested",
        persona_id=persona_id,
        status=status.get("status"),
    )

    return CalendarStatusResponse(**status)
