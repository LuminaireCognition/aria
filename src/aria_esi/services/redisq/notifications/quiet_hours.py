"""
Quiet Hours Manager.

Timezone-aware quiet hours checking using zoneinfo for DST handling.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

if TYPE_CHECKING:
    from .config import QuietHoursConfig


@dataclass
class QuietHoursChecker:
    """
    Checks if current time falls within quiet hours.

    Uses zoneinfo for proper DST handling:
    - Spring forward: Folds nonexistent time to next valid
    - Fall back: Uses first occurrence (fold=0)
    """

    config: QuietHoursConfig

    def __post_init__(self) -> None:
        """Parse time strings to time objects."""
        self._start_time = self._parse_time(self.config.start)
        self._end_time = self._parse_time(self.config.end)
        self._timezone: ZoneInfo | None = None

        try:
            self._timezone = ZoneInfo(self.config.timezone)
        except ZoneInfoNotFoundError:
            # Fall back to UTC if timezone not found
            self._timezone = ZoneInfo("UTC")

    @staticmethod
    def _parse_time(time_str: str) -> time:
        """
        Parse HH:MM string to time object.

        Args:
            time_str: Time in HH:MM format

        Returns:
            time object
        """
        parts = time_str.split(":")
        hour = int(parts[0]) if len(parts) > 0 else 0
        minute = int(parts[1]) if len(parts) > 1 else 0
        return time(hour=hour, minute=minute)

    def is_quiet_time(self, now: datetime | None = None) -> bool:
        """
        Check if the given time is within quiet hours.

        Args:
            now: Time to check (defaults to current time)

        Returns:
            True if within quiet hours, False otherwise
        """
        if not self.config.enabled:
            return False

        if now is None:
            now = datetime.now(tz=self._timezone)
        elif now.tzinfo is None:
            # Naive datetime - convert to configured timezone
            now = now.replace(tzinfo=self._timezone)
        else:
            # Convert to configured timezone
            now = now.astimezone(self._timezone)

        current_time = now.time()

        # Handle quiet hours that span midnight
        if self._start_time <= self._end_time:
            # Simple case: start and end are same day (e.g., 09:00 to 17:00)
            return self._start_time <= current_time <= self._end_time
        else:
            # Spans midnight: start > end (e.g., 22:00 to 06:00)
            return current_time >= self._start_time or current_time <= self._end_time

    def next_active_time(self, now: datetime | None = None) -> datetime | None:
        """
        Get the next time when notifications will be active.

        Args:
            now: Reference time (defaults to current time)

        Returns:
            Datetime when quiet hours end, or None if not in quiet period
        """
        if not self.is_quiet_time(now):
            return None

        if now is None:
            now = datetime.now(tz=self._timezone)
        elif now.tzinfo is None:
            now = now.replace(tzinfo=self._timezone)
        else:
            now = now.astimezone(self._timezone)

        # Calculate when quiet hours end
        end_dt = now.replace(
            hour=self._end_time.hour,
            minute=self._end_time.minute,
            second=0,
            microsecond=0,
        )

        # If end time is before current time, it's tomorrow
        if end_dt <= now:
            from datetime import timedelta

            end_dt = end_dt + timedelta(days=1)

        return end_dt
