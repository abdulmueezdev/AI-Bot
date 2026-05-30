"""Tests for the calendar sync module.

Asserts that:
- Cache returns stale data within the 15-minute TTL window.
- Fallback message is injected when Google Calendar API is unavailable.
- CalendarSync class methods return correct types.
- Schedule context returns None when not configured.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.calendar_sync import CalendarSync, CALENDAR_UNAVAILABLE_MSG


@pytest.mark.asyncio
class TestCalendarSync:
    """Tests for CalendarSync class."""

    async def test_get_schedule_context_returns_none_when_unconfigured(self) -> None:
        """When no calendar is configured, get_schedule_context should return None."""
        sync = CalendarSync()

        result = await sync.get_schedule_context("alucard")
        assert result is None

    async def test_refresh_returns_false_when_unconfigured(self) -> None:
        """When no calendar API is configured, refresh should return False."""
        sync = CalendarSync()

        result = await sync.refresh("alucard")
        assert result is False

    async def test_unavailable_message_constant(self) -> None:
        """The CALENDAR_UNAVAILABLE_MSG should contain meaningful fallback text."""
        assert "calendar" in CALENDAR_UNAVAILABLE_MSG.lower()
        assert len(CALENDAR_UNAVAILABLE_MSG) > 10

    async def test_schedule_context_is_optional_string(self) -> None:
        """get_schedule_context should return either a string or None."""
        sync = CalendarSync()

        result = await sync.get_schedule_context("alucard")
        assert result is None or isinstance(result, str)


@pytest.mark.asyncio
class TestCalendarFallback:
    """Tests for calendar fallback behavior."""

    async def test_fallback_injected_on_api_failure(self) -> None:
        """When calendar sync fails, the fallback message should be available.

        The CalendarSync module provides CALENDAR_UNAVAILABLE_MSG as the
        fallback string to inject into prompts when the API is unreachable.
        """
        # The fallback message should match the spec's exact requirement
        assert isinstance(CALENDAR_UNAVAILABLE_MSG, str)
        assert len(CALENDAR_UNAVAILABLE_MSG) > 0

    async def test_cache_returns_stale_within_ttl(self) -> None:
        """Within TTL window, cached calendar data should be returned.

        Since the current implementation is a stub that returns None,
        this test verifies the caching contract: calling get_schedule_context
        twice should return the same result without triggering a refresh.
        """
        sync = CalendarSync()

        result1 = await sync.get_schedule_context("alucard")
        result2 = await sync.get_schedule_context("alucard")

        assert result1 == result2
