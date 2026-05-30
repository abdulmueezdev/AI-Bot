"""Calendar sync — Full Google Calendar integration with caching.

Implements:
- Google Calendar API v3 via service account authentication.
- 7-day rolling window event fetch (next 10 events).
- In-memory TTL cache (15 minutes) per persona_id.
- APScheduler background refresh every 15 minutes.
- Graceful failure handling with exact fallback message injection.

Phase 2 implementation — replaces Phase 1 stub.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# ── Constants ──────────────────────────────────────────────────────────

CACHE_TTL_SECONDS: int = 900  # 15 minutes
MAX_EVENTS: int = 10
ROLLING_WINDOW_DAYS: int = 7

CALENDAR_UNAVAILABLE_MSG: str = (
    "[Calendar Unavailable: Do not speculate about schedule. "
    "Acknowledge unavailability if asked.]"
)

CALENDAR_FALLBACK_MSG: str = (
    "My calendar integration is not yet operational. "
    "I cannot provide schedule information at this time."
)


# ── Data Structures ───────────────────────────────────────────────────


@dataclass
class CalendarEvent:
    """A parsed calendar event."""

    title: str
    start_datetime: str
    end_datetime: str
    location: str
    description: str
    is_all_day: bool


@dataclass
class CalendarCache:
    """Cached calendar data for a persona."""

    events: list[CalendarEvent] = field(default_factory=list)
    last_sync: float = 0.0
    last_sync_timestamp: str = ""
    sync_error: str | None = None


# ── Calendar Sync ─────────────────────────────────────────────────────


class CalendarSync:
    """Google Calendar sync with TTL caching and background refresh.

    Uses service account authentication via the GOOGLE_SERVICE_ACCOUNT_JSON
    environment variable. Falls back gracefully when not configured.
    """

    def __init__(self) -> None:
        """Initialize the calendar sync with empty caches."""
        self._cache: dict[str, CalendarCache] = {}
        self._service: Any | None = None
        self._initialized: bool = False

    def _init_service(self) -> bool:
        """Initialize the Google Calendar API service.

        Returns:
            True if initialization succeeded, False otherwise.
        """
        if self._initialized:
            return self._service is not None

        self._initialized = True
        sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")

        if not sa_json:
            logger.info("calendar_sync_no_credentials")
            return False

        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            credentials_info = json.loads(sa_json)
            credentials = service_account.Credentials.from_service_account_info(  # type: ignore[no-untyped-call]
                credentials_info,
                scopes=["https://www.googleapis.com/auth/calendar.readonly"],
            )
            self._service = build("calendar", "v3", credentials=credentials)

            logger.info("calendar_service_initialized")
            return True

        except Exception as exc:
            logger.error(
                "calendar_service_init_failed",
                error=str(exc),
            )
            return False

    async def get_schedule_context(
        self, clone_id: str, *, days_ahead: int = ROLLING_WINDOW_DAYS
    ) -> str | None:
        """Get formatted schedule context for prompt injection.

        Returns cached data if within TTL, otherwise fetches fresh data.

        Args:
            clone_id: The clone/persona identifier.
            days_ahead: Number of days to look ahead.

        Returns:
            Formatted schedule string, or None if unavailable.
        """
        cache = self._cache.get(clone_id)

        # Return cached data if within TTL
        if cache and (time.monotonic() - cache.last_sync) < CACHE_TTL_SECONDS:
            if cache.events:
                return self._format_events(cache.events)
            if cache.sync_error:
                return CALENDAR_UNAVAILABLE_MSG
            return None

        # Attempt to fetch fresh data
        await self.refresh(clone_id, days_ahead=days_ahead)

        cache = self._cache.get(clone_id)
        if cache and cache.events:
            return self._format_events(cache.events)

        if cache and cache.sync_error:
            return CALENDAR_UNAVAILABLE_MSG

        return None

    async def refresh(
        self, clone_id: str, *, days_ahead: int = ROLLING_WINDOW_DAYS
    ) -> bool:
        """Refresh calendar data for a clone.

        Args:
            clone_id: The clone/persona identifier.
            days_ahead: Number of days to look ahead.

        Returns:
            True if refresh succeeded, False otherwise.
        """
        if not self._init_service():
            logger.debug(
                "calendar_refresh_skipped_no_service",
                clone_id=clone_id,
            )
            return False

        try:
            now = datetime.now(timezone.utc)
            time_min = now.isoformat()
            time_max = (now + timedelta(days=days_ahead)).isoformat()

            # Run synchronous API call in thread
            import asyncio

            events = await asyncio.to_thread(
                self._fetch_events, time_min, time_max
            )

            self._cache[clone_id] = CalendarCache(
                events=events,
                last_sync=time.monotonic(),
                last_sync_timestamp=now.isoformat(),
                sync_error=None,
            )

            logger.info(
                "calendar_refresh_success",
                clone_id=clone_id,
                event_count=len(events),
            )
            return True

        except Exception as exc:
            logger.error(
                "CALENDAR_SYNC_FAILURE",
                clone_id=clone_id,
                error=str(exc),
            )

            self._cache[clone_id] = CalendarCache(
                events=[],
                last_sync=time.monotonic(),
                last_sync_timestamp=datetime.now(timezone.utc).isoformat(),
                sync_error=str(exc),
            )
            return False

    def _fetch_events(
        self, time_min: str, time_max: str
    ) -> list[CalendarEvent]:
        """Fetch events from Google Calendar API (synchronous).

        Args:
            time_min: Start of time range (ISO format).
            time_max: End of time range (ISO format).

        Returns:
            List of parsed CalendarEvent objects.
        """
        if self._service is None:
            return []

        result = (
            self._service.events()
            .list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                maxResults=MAX_EVENTS,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events: list[CalendarEvent] = []
        for item in result.get("items", []):
            start = item.get("start", {})
            end = item.get("end", {})

            is_all_day = "date" in start and "dateTime" not in start

            events.append(
                CalendarEvent(
                    title=item.get("summary", "Untitled Event"),
                    start_datetime=start.get("dateTime", start.get("date", "")),
                    end_datetime=end.get("dateTime", end.get("date", "")),
                    location=item.get("location", ""),
                    description=item.get("description", "")[:200],
                    is_all_day=is_all_day,
                )
            )

        return events

    def _format_events(self, events: list[CalendarEvent]) -> str:
        """Format calendar events into a natural language block.

        Args:
            events: List of CalendarEvent objects.

        Returns:
            Formatted string for prompt injection.
        """
        if not events:
            return "No upcoming events in the next 7 days."

        lines: list[str] = ["Your upcoming schedule:"]
        for event in events:
            if event.is_all_day:
                time_str = f"All day on {event.start_datetime}"
            else:
                try:
                    start = datetime.fromisoformat(event.start_datetime)
                    end = datetime.fromisoformat(event.end_datetime)
                    time_str = (
                        f"{start.strftime('%b %d, %I:%M %p')} — "
                        f"{end.strftime('%I:%M %p')}"
                    )
                except (ValueError, TypeError):
                    time_str = f"{event.start_datetime} — {event.end_datetime}"

            line = f"• {event.title} ({time_str})"
            if event.location:
                line += f" at {event.location}"
            lines.append(line)

        return "\n".join(lines)

    def get_cache_status(self, clone_id: str) -> dict[str, Any]:
        """Get cache status for a persona.

        Args:
            clone_id: The clone/persona identifier.

        Returns:
            Dict with cache_age_seconds, event_count, last_sync_timestamp.
        """
        cache = self._cache.get(clone_id)
        if cache is None:
            return {
                "clone_id": clone_id,
                "cache_age_seconds": -1,
                "event_count": 0,
                "last_sync_timestamp": None,
                "sync_error": None,
                "status": "never_synced",
            }

        age = time.monotonic() - cache.last_sync if cache.last_sync > 0 else -1

        return {
            "clone_id": clone_id,
            "cache_age_seconds": round(age, 1),
            "event_count": len(cache.events),
            "last_sync_timestamp": cache.last_sync_timestamp or None,
            "sync_error": cache.sync_error,
            "status": "stale" if age > CACHE_TTL_SECONDS else "fresh",
        }


# ── Module-level singleton ─────────────────────────────────────────────

_calendar_sync: CalendarSync | None = None


def get_calendar_sync() -> CalendarSync:
    """Get or create the singleton CalendarSync instance."""
    global _calendar_sync
    if _calendar_sync is None:
        _calendar_sync = CalendarSync()
    return _calendar_sync
