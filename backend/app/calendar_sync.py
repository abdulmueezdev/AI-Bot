"""Calendar sync — Phase 2 stub.

This module will implement:
- Google Calendar API v3 integration (OAuth flow)
- .ics feed parsing (icalendar library)
- APScheduler background refresh jobs
- Schedule context injection into prompts

Phase 1: No-op implementation. Returns static unavailable message.
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)

CALENDAR_UNAVAILABLE_MSG = (
    "My calendar integration is not yet operational. "
    "I cannot provide schedule information at this time."
)


class CalendarSync:
    """Stub calendar sync for Phase 1.

    Phase 2 will add:
    - Google Calendar API v3 with OAuth
    - .ics feed parsing
    - APScheduler background refresh
    - Schedule context for prompt injection
    """

    async def get_schedule_context(
        self, clone_id: str, *, days_ahead: int = 7
    ) -> str | None:
        """Get schedule context for a clone.

        Phase 1: Returns None (no calendar data).
        """
        logger.debug(
            "calendar_sync_skipped_phase1",
            clone_id=clone_id,
        )
        return None

    async def refresh(self, clone_id: str) -> bool:
        """Refresh calendar data for a clone.

        Phase 1: No-op, returns False.
        """
        return False
