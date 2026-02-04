"""
Tests for quiet hours checker.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from aria_esi.services.redisq.notifications.config import QuietHoursConfig
from aria_esi.services.redisq.notifications.quiet_hours import QuietHoursChecker


class TestQuietHoursChecker:
    """Tests for QuietHoursChecker."""

    def test_disabled_quiet_hours(self):
        """Disabled quiet hours never triggers."""
        config = QuietHoursConfig(enabled=False, start="02:00", end="08:00")
        checker = QuietHoursChecker(config=config)

        # Test various times
        assert checker.is_quiet_time() is False

        midnight = datetime(2024, 1, 15, 0, 0, tzinfo=ZoneInfo("America/New_York"))
        assert checker.is_quiet_time(midnight) is False

        three_am = datetime(2024, 1, 15, 3, 0, tzinfo=ZoneInfo("America/New_York"))
        assert checker.is_quiet_time(three_am) is False

    def test_within_quiet_hours(self):
        """Test time within quiet hours."""
        config = QuietHoursConfig(
            enabled=True,
            start="02:00",
            end="08:00",
            timezone="America/New_York",
        )
        checker = QuietHoursChecker(config=config)

        # 3 AM should be quiet
        three_am = datetime(2024, 1, 15, 3, 0, tzinfo=ZoneInfo("America/New_York"))
        assert checker.is_quiet_time(three_am) is True

        # 7:59 AM should be quiet
        almost_8 = datetime(2024, 1, 15, 7, 59, tzinfo=ZoneInfo("America/New_York"))
        assert checker.is_quiet_time(almost_8) is True

    def test_outside_quiet_hours(self):
        """Test time outside quiet hours."""
        config = QuietHoursConfig(
            enabled=True,
            start="02:00",
            end="08:00",
            timezone="America/New_York",
        )
        checker = QuietHoursChecker(config=config)

        # 8:01 AM should not be quiet
        after_8 = datetime(2024, 1, 15, 8, 1, tzinfo=ZoneInfo("America/New_York"))
        assert checker.is_quiet_time(after_8) is False

        # 1:59 AM should not be quiet
        before_2 = datetime(2024, 1, 15, 1, 59, tzinfo=ZoneInfo("America/New_York"))
        assert checker.is_quiet_time(before_2) is False

        # 2 PM should not be quiet
        two_pm = datetime(2024, 1, 15, 14, 0, tzinfo=ZoneInfo("America/New_York"))
        assert checker.is_quiet_time(two_pm) is False

    def test_quiet_hours_spanning_midnight(self):
        """Test quiet hours that span midnight (e.g., 22:00 to 06:00)."""
        config = QuietHoursConfig(
            enabled=True,
            start="22:00",  # 10 PM
            end="06:00",  # 6 AM
            timezone="America/New_York",
        )
        checker = QuietHoursChecker(config=config)

        # 11 PM should be quiet
        eleven_pm = datetime(2024, 1, 15, 23, 0, tzinfo=ZoneInfo("America/New_York"))
        assert checker.is_quiet_time(eleven_pm) is True

        # 2 AM should be quiet
        two_am = datetime(2024, 1, 16, 2, 0, tzinfo=ZoneInfo("America/New_York"))
        assert checker.is_quiet_time(two_am) is True

        # 12 PM should not be quiet
        noon = datetime(2024, 1, 15, 12, 0, tzinfo=ZoneInfo("America/New_York"))
        assert checker.is_quiet_time(noon) is False

    def test_timezone_conversion(self):
        """Test timezone conversion from UTC."""
        config = QuietHoursConfig(
            enabled=True,
            start="02:00",
            end="08:00",
            timezone="America/New_York",
        )
        checker = QuietHoursChecker(config=config)

        # 8:00 UTC = 3:00 AM EST (during winter, EST = UTC-5)
        utc_time = datetime(2024, 1, 15, 8, 0, tzinfo=ZoneInfo("UTC"))
        assert checker.is_quiet_time(utc_time) is True

    def test_next_active_time(self):
        """Test calculation of next active time."""
        config = QuietHoursConfig(
            enabled=True,
            start="02:00",
            end="08:00",
            timezone="America/New_York",
        )
        checker = QuietHoursChecker(config=config)

        # At 3 AM, next active should be 8 AM same day
        three_am = datetime(2024, 1, 15, 3, 0, tzinfo=ZoneInfo("America/New_York"))
        next_active = checker.next_active_time(three_am)

        assert next_active is not None
        assert next_active.hour == 8
        assert next_active.minute == 0
        assert next_active.day == 15

    def test_next_active_time_not_quiet(self):
        """Returns None when not in quiet period."""
        config = QuietHoursConfig(
            enabled=True,
            start="02:00",
            end="08:00",
            timezone="America/New_York",
        )
        checker = QuietHoursChecker(config=config)

        # 2 PM is not quiet
        two_pm = datetime(2024, 1, 15, 14, 0, tzinfo=ZoneInfo("America/New_York"))
        assert checker.next_active_time(two_pm) is None

    def test_fallback_timezone(self):
        """Test fallback to UTC for invalid timezone."""
        config = QuietHoursConfig(
            enabled=True,
            start="02:00",
            end="08:00",
            timezone="Invalid/Timezone",
        )
        checker = QuietHoursChecker(config=config)

        # Should use UTC as fallback
        assert checker._timezone == ZoneInfo("UTC")


class TestQuietHoursEdgeCases:
    """Edge case tests for QuietHoursChecker."""

    def test_exact_start_time(self):
        """Test exactly at start time is quiet."""
        config = QuietHoursConfig(
            enabled=True,
            start="02:00",
            end="08:00",
            timezone="America/New_York",
        )
        checker = QuietHoursChecker(config=config)

        exact_start = datetime(2024, 1, 15, 2, 0, tzinfo=ZoneInfo("America/New_York"))
        assert checker.is_quiet_time(exact_start) is True

    def test_exact_end_time(self):
        """Test exactly at end time is quiet (inclusive)."""
        config = QuietHoursConfig(
            enabled=True,
            start="02:00",
            end="08:00",
            timezone="America/New_York",
        )
        checker = QuietHoursChecker(config=config)

        exact_end = datetime(2024, 1, 15, 8, 0, tzinfo=ZoneInfo("America/New_York"))
        assert checker.is_quiet_time(exact_end) is True

    def test_naive_datetime_handling(self):
        """Test handling of naive datetime (no timezone)."""
        config = QuietHoursConfig(
            enabled=True,
            start="02:00",
            end="08:00",
            timezone="America/New_York",
        )
        checker = QuietHoursChecker(config=config)

        # Naive datetime should be treated as configured timezone
        naive_3am = datetime(2024, 1, 15, 3, 0)
        # Should work without error
        result = checker.is_quiet_time(naive_3am)
        assert isinstance(result, bool)
