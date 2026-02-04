"""
Tests for aria_esi.core.formatters

These are pure functions with no external dependencies, making them
ideal for comprehensive unit testing.
"""

from datetime import datetime, timezone


class TestFormatISK:
    """Tests for format_isk function."""

    def test_billions(self):
        from aria_esi.core import format_isk
        assert format_isk(1_500_000_000) == "1.50B"
        assert format_isk(1_000_000_000) == "1.00B"
        assert format_isk(999_999_999_999) == "1000.00B"

    def test_millions(self):
        from aria_esi.core import format_isk
        assert format_isk(250_000_000) == "250.00M"
        assert format_isk(1_000_000) == "1.00M"
        assert format_isk(999_999_999) == "1000.00M"

    def test_thousands(self):
        from aria_esi.core import format_isk
        assert format_isk(15_000) == "15.00K"
        assert format_isk(1_000) == "1.00K"
        assert format_isk(999_999) == "1000.00K"

    def test_small_values(self):
        from aria_esi.core import format_isk
        assert format_isk(100) == "100.00"
        assert format_isk(1) == "1.00"
        assert format_isk(999) == "999.00"

    def test_sub_one_values(self):
        from aria_esi.core import format_isk
        assert format_isk(0.5) == "0.5000"
        assert format_isk(0.01) == "0.0100"

    def test_zero(self):
        from aria_esi.core import format_isk
        assert format_isk(0) == "0.0000"

    def test_custom_precision(self):
        from aria_esi.core import format_isk
        assert format_isk(1_500_000_000, precision=0) == "2B"
        assert format_isk(1_500_000_000, precision=3) == "1.500B"
        assert format_isk(250_000_000, precision=1) == "250.0M"


class TestFormatISKFull:
    """Tests for format_isk_full function."""

    def test_with_commas(self):
        from aria_esi.core import format_isk_full
        assert format_isk_full(1_500_000_000) == "1,500,000,000.00 ISK"
        assert format_isk_full(1_234_567.89) == "1,234,567.89 ISK"
        assert format_isk_full(100) == "100.00 ISK"


class TestFormatDuration:
    """Tests for format_duration function."""

    def test_days_hours_minutes(self):
        from aria_esi.core import format_duration
        # 1 day + 1 hour + 30 minutes
        assert format_duration(86400 + 3600 + 1800) == "1d 1h 30m"

    def test_hours_minutes(self):
        from aria_esi.core import format_duration
        # Implementation omits zero minutes when hours present
        assert format_duration(7200) == "2h"
        assert format_duration(3661) == "1h 1m"

    def test_hours_with_minutes(self):
        from aria_esi.core import format_duration
        assert format_duration(7500) == "2h 5m"  # 2 hours 5 minutes

    def test_minutes_only(self):
        from aria_esi.core import format_duration
        assert format_duration(300) == "5m"
        assert format_duration(60) == "1m"

    def test_zero_and_negative(self):
        from aria_esi.core import format_duration
        assert format_duration(0) == "Complete"
        assert format_duration(-100) == "Complete"

    def test_large_duration(self):
        from aria_esi.core import format_duration
        # 5 days + 12 hours + 30 minutes
        assert format_duration(5 * 86400 + 12 * 3600 + 30 * 60) == "5d 12h 30m"


class TestFormatDurationLong:
    """Tests for format_duration_long function."""

    def test_singular_plural(self):
        from aria_esi.core import format_duration_long
        assert format_duration_long(86400) == "1 day"
        assert format_duration_long(86400 * 2) == "2 days"
        assert format_duration_long(3600) == "1 hour"
        assert format_duration_long(3600 * 2) == "2 hours"
        assert format_duration_long(60) == "1 minute"
        assert format_duration_long(120) == "2 minutes"

    def test_complete(self):
        from aria_esi.core import format_duration_long
        assert format_duration_long(0) == "Complete"
        assert format_duration_long(-1) == "Complete"

    def test_less_than_minute(self):
        from aria_esi.core import format_duration_long
        assert format_duration_long(30) == "Less than a minute"


class TestToRoman:
    """Tests for to_roman function."""

    def test_valid_levels(self):
        from aria_esi.core import to_roman
        assert to_roman(0) == "0"
        assert to_roman(1) == "I"
        assert to_roman(2) == "II"
        assert to_roman(3) == "III"
        assert to_roman(4) == "IV"
        assert to_roman(5) == "V"

    def test_out_of_range(self):
        from aria_esi.core import to_roman
        assert to_roman(6) == "6"
        assert to_roman(-1) == "-1"
        assert to_roman(100) == "100"


class TestFormatSkillLevel:
    """Tests for format_skill_level function."""

    def test_format(self):
        from aria_esi.core import format_skill_level
        assert format_skill_level("Drones", 5) == "Drones V"
        assert format_skill_level("Mining", 1) == "Mining I"
        assert format_skill_level("Spaceship Command", 4) == "Spaceship Command IV"


class TestParseDatetime:
    """Tests for parse_datetime function."""

    def test_standard_format(self):
        from aria_esi.core import parse_datetime
        result = parse_datetime("2026-01-15T12:30:00Z")
        assert result is not None
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 12
        assert result.minute == 30
        assert result.tzinfo == timezone.utc

    def test_with_microseconds(self):
        from aria_esi.core import parse_datetime
        result = parse_datetime("2026-01-15T12:30:00.123456Z")
        assert result is not None
        assert result.year == 2026

    def test_invalid_format(self):
        from aria_esi.core import parse_datetime
        assert parse_datetime("invalid") is None
        assert parse_datetime("2026/01/15") is None

    def test_empty_and_none(self):
        from aria_esi.core import parse_datetime
        assert parse_datetime("") is None
        assert parse_datetime(None) is None


class TestFormatDatetime:
    """Tests for format_datetime function."""

    def test_format(self):
        from aria_esi.core import format_datetime
        dt = datetime(2026, 1, 15, 12, 30, 0, tzinfo=timezone.utc)
        assert format_datetime(dt) == "2026-01-15T12:30:00Z"


class TestGetUtcTimestamp:
    """Tests for get_utc_timestamp function."""

    def test_format(self):
        from aria_esi.core import get_utc_timestamp
        result = get_utc_timestamp()
        # Should be ISO format ending in Z
        assert result.endswith("Z")
        assert "T" in result
        # Should be parseable
        from aria_esi.core import parse_datetime
        parsed = parse_datetime(result)
        assert parsed is not None


class TestTimeUntilAndSince:
    """Tests for time_until and time_since functions."""

    def test_time_until_future(self, fixed_datetime):
        from unittest.mock import patch

        from aria_esi.core import formatters, time_until

        # fixed_datetime is 18:30:00, future is 19:30:00 (1 hour ahead)
        future = fixed_datetime.replace(hour=19)

        with patch.object(formatters, 'get_utc_now', return_value=fixed_datetime):
            result = time_until(future)

        assert result == 3600  # 1 hour in seconds

    def test_time_until_past(self, fixed_datetime):
        from unittest.mock import patch

        from aria_esi.core import formatters, time_until

        # fixed_datetime is 18:30:00, past is 17:30:00 (1 hour ago)
        past = fixed_datetime.replace(hour=17)

        with patch.object(formatters, 'get_utc_now', return_value=fixed_datetime):
            result = time_until(past)

        assert result == -3600  # negative (past)

    def test_time_since(self, fixed_datetime):
        from unittest.mock import patch

        from aria_esi.core import formatters, time_since

        # fixed_datetime is 18:30:00, past is 17:30:00 (1 hour ago)
        past = fixed_datetime.replace(hour=17)

        with patch.object(formatters, 'get_utc_now', return_value=fixed_datetime):
            result = time_since(past)

        assert result == 3600  # positive (past)


class TestFormatSecurity:
    """Tests for format_security function."""

    def test_format(self):
        from aria_esi.core import format_security
        assert format_security(0.945) == "0.9"
        assert format_security(0.5) == "0.5"
        assert format_security(-0.3) == "-0.3"
        assert format_security(1.0) == "1.0"


class TestGetSecurityClass:
    """Tests for get_security_class function."""

    def test_high_sec(self):
        from aria_esi.core import get_security_class
        assert get_security_class(1.0) == "high_sec"
        assert get_security_class(0.5) == "high_sec"
        assert get_security_class(0.45) == "high_sec"

    def test_low_sec(self):
        from aria_esi.core import get_security_class
        assert get_security_class(0.4) == "low_sec"
        assert get_security_class(0.1) == "low_sec"
        assert get_security_class(0.05) == "low_sec"

    def test_null_sec(self):
        from aria_esi.core import get_security_class
        assert get_security_class(0.0) == "null_sec"
        assert get_security_class(-0.5) == "null_sec"
        assert get_security_class(-1.0) == "null_sec"


class TestGetSecurityDescription:
    """Tests for get_security_description function."""

    def test_descriptions(self):
        from aria_esi.core import get_security_description
        assert get_security_description(5.0) == "Paragon"
        assert get_security_description(2.0) == "Upstanding"
        assert get_security_description(0.0) == "Neutral"
        assert get_security_description(-2.0) == "Suspect"
        assert get_security_description(-5.0) == "Criminal"
        assert get_security_description(-6.0) == "Outlaw"


class TestFormatProgress:
    """Tests for format_progress function."""

    def test_normal(self):
        from aria_esi.core import format_progress
        assert format_progress(75, 100) == "75.0%"
        assert format_progress(1, 3) == "33.3%"

    def test_complete(self):
        from aria_esi.core import format_progress
        assert format_progress(100, 100) == "100.0%"

    def test_over_complete(self):
        from aria_esi.core import format_progress
        assert format_progress(150, 100) == "100.0%"  # Capped

    def test_zero_total(self):
        from aria_esi.core import format_progress
        assert format_progress(50, 0) == "0.0%"


class TestEFTFormatters:
    """Tests for EFT (EVE Fitting Tool) format functions."""

    def test_eft_header(self):
        from aria_esi.core import format_eft_header
        assert format_eft_header("Vexor", "My Fit") == "[Vexor, My Fit]"
        assert format_eft_header("Catalyst", "ARIA Export") == "[Catalyst, ARIA Export]"

    def test_eft_drone(self):
        from aria_esi.core import format_eft_drone
        assert format_eft_drone("Hammerhead II", 5) == "Hammerhead II x5"
        assert format_eft_drone("Hobgoblin I", 3) == "Hobgoblin I x3"

    def test_eft_cargo(self):
        from aria_esi.core import format_eft_cargo
        assert format_eft_cargo("Antimatter Charge M", 1000) == "Antimatter Charge M x1000"


class TestFormatRefType:
    """Tests for format_ref_type function."""

    def test_known_types(self):
        from aria_esi.core import format_ref_type
        assert format_ref_type("bounty_prizes") == "Bounties"
        assert format_ref_type("market_transaction") == "Market Trading"
        assert format_ref_type("agent_mission_reward") == "Mission Rewards"

    def test_unknown_type_fallback(self):
        from aria_esi.core import format_ref_type
        # Should convert snake_case to Title Case
        assert format_ref_type("some_unknown_type") == "Some Unknown Type"
        assert format_ref_type("weird_custom_thing") == "Weird Custom Thing"


class TestCalculateProgress:
    """Tests for calculate_progress function."""

    def test_progress_in_middle(self, fixed_datetime):
        from unittest.mock import patch

        from aria_esi.core import formatters
        from aria_esi.core.formatters import calculate_progress

        # fixed_datetime is 18:30:00
        start = fixed_datetime.replace(hour=17, minute=30)  # 1 hour ago
        end = fixed_datetime.replace(hour=19, minute=30)    # 1 hour from now

        with patch.object(formatters, 'get_utc_now', return_value=fixed_datetime):
            result = calculate_progress(start, end)

        # We're at 50% (1 hour elapsed out of 2 hours total)
        assert abs(result - 50.0) < 0.1

    def test_progress_complete(self, fixed_datetime):
        from unittest.mock import patch

        from aria_esi.core import formatters
        from aria_esi.core.formatters import calculate_progress

        # fixed_datetime is 18:30:00
        start = fixed_datetime.replace(hour=16, minute=30)  # 2 hours ago
        end = fixed_datetime.replace(hour=17, minute=30)    # 1 hour ago (completed)

        with patch.object(formatters, 'get_utc_now', return_value=fixed_datetime):
            result = calculate_progress(start, end)

        # Progress should be 100% (capped)
        assert result == 100.0

    def test_progress_not_started(self, fixed_datetime):
        from datetime import timedelta
        from unittest.mock import patch

        from aria_esi.core import formatters
        from aria_esi.core.formatters import calculate_progress

        # fixed_datetime is 18:30:00
        start = fixed_datetime + timedelta(hours=1)  # starts in 1 hour
        end = fixed_datetime + timedelta(hours=2)    # ends in 2 hours

        with patch.object(formatters, 'get_utc_now', return_value=fixed_datetime):
            result = calculate_progress(start, end)

        # Progress should be 0% (capped, can't be negative)
        assert result == 0.0

    def test_progress_zero_duration(self, fixed_datetime):
        from unittest.mock import patch

        from aria_esi.core import formatters
        from aria_esi.core.formatters import calculate_progress

        # start and end are the same
        start = fixed_datetime
        end = fixed_datetime

        with patch.object(formatters, 'get_utc_now', return_value=fixed_datetime):
            result = calculate_progress(start, end)

        # Zero duration should return 100%
        assert result == 100.0
