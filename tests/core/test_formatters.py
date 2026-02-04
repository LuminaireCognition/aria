"""
Tests for ARIA ESI Formatters.

Tests utility functions for formatting ESI data for display.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest


# =============================================================================
# ISK Formatting Tests
# =============================================================================


class TestFormatIsk:
    """Test format_isk function."""

    def test_billions(self):
        """Formats billions correctly."""
        from aria_esi.core.formatters import format_isk

        result = format_isk(1500000000)
        assert result == "1.50B"

    def test_millions(self):
        """Formats millions correctly."""
        from aria_esi.core.formatters import format_isk

        result = format_isk(250000000)
        assert result == "250.00M"

    def test_thousands(self):
        """Formats thousands correctly."""
        from aria_esi.core.formatters import format_isk

        result = format_isk(15000)
        assert result == "15.00K"

    def test_units(self):
        """Formats small amounts correctly."""
        from aria_esi.core.formatters import format_isk

        result = format_isk(100)
        assert result == "100.00"

    def test_sub_unit(self):
        """Formats sub-1 ISK amounts correctly."""
        from aria_esi.core.formatters import format_isk

        result = format_isk(0.5)
        assert result == "0.5000"

    def test_custom_precision(self):
        """Respects custom precision parameter."""
        from aria_esi.core.formatters import format_isk

        result = format_isk(1500000000, precision=0)
        assert result == "2B"

    def test_exact_billion_boundary(self):
        """Handles exact billion boundary."""
        from aria_esi.core.formatters import format_isk

        result = format_isk(1_000_000_000)
        assert result == "1.00B"

    def test_exact_million_boundary(self):
        """Handles exact million boundary."""
        from aria_esi.core.formatters import format_isk

        result = format_isk(1_000_000)
        assert result == "1.00M"

    def test_exact_thousand_boundary(self):
        """Handles exact thousand boundary."""
        from aria_esi.core.formatters import format_isk

        result = format_isk(1_000)
        assert result == "1.00K"


class TestFormatIskFull:
    """Test format_isk_full function."""

    def test_formats_with_commas(self):
        """Formats with thousand separators."""
        from aria_esi.core.formatters import format_isk_full

        result = format_isk_full(1500000000)
        assert result == "1,500,000,000.00 ISK"

    def test_small_amount(self):
        """Formats small amounts correctly."""
        from aria_esi.core.formatters import format_isk_full

        result = format_isk_full(100.50)
        assert result == "100.50 ISK"


# =============================================================================
# Duration Formatting Tests
# =============================================================================


class TestFormatDuration:
    """Test format_duration function."""

    def test_days_hours_minutes(self):
        """Formats full duration."""
        from aria_esi.core.formatters import format_duration

        result = format_duration(86400 + 3600 + 1800)
        assert result == "1d 1h 30m"

    def test_hours_only(self):
        """Formats hours duration."""
        from aria_esi.core.formatters import format_duration

        result = format_duration(7200)
        # When there are hours but no minutes, only hours are shown
        assert result == "2h"

    def test_minutes_only(self):
        """Formats minutes duration."""
        from aria_esi.core.formatters import format_duration

        result = format_duration(300)
        assert result == "5m"

    def test_zero_complete(self):
        """Zero seconds shows Complete."""
        from aria_esi.core.formatters import format_duration

        result = format_duration(0)
        assert result == "Complete"

    def test_negative_complete(self):
        """Negative seconds shows Complete."""
        from aria_esi.core.formatters import format_duration

        result = format_duration(-100)
        assert result == "Complete"

    def test_days_only(self):
        """Formats days with no hours/minutes."""
        from aria_esi.core.formatters import format_duration

        result = format_duration(86400)
        assert "1d" in result


class TestFormatDurationLong:
    """Test format_duration_long function."""

    def test_full_format(self):
        """Formats verbose duration."""
        from aria_esi.core.formatters import format_duration_long

        result = format_duration_long(86400 + 7200 + 1800)
        assert "1 day" in result
        assert "2 hours" in result
        assert "30 minutes" in result

    def test_singular_forms(self):
        """Uses singular forms correctly."""
        from aria_esi.core.formatters import format_duration_long

        result = format_duration_long(86400 + 3600 + 60)
        assert "1 day" in result
        assert "1 hour" in result
        assert "1 minute" in result

    def test_zero(self):
        """Zero shows Complete."""
        from aria_esi.core.formatters import format_duration_long

        result = format_duration_long(0)
        assert result == "Complete"

    def test_under_minute(self):
        """Under a minute shows appropriate message."""
        from aria_esi.core.formatters import format_duration_long

        result = format_duration_long(30)
        assert result == "Less than a minute"


# =============================================================================
# Skill Level Formatting Tests
# =============================================================================


class TestToRoman:
    """Test to_roman function."""

    def test_level_1(self):
        """Converts 1 to I."""
        from aria_esi.core.formatters import to_roman

        assert to_roman(1) == "I"

    def test_level_5(self):
        """Converts 5 to V."""
        from aria_esi.core.formatters import to_roman

        assert to_roman(5) == "V"

    def test_level_0(self):
        """Converts 0 to 0."""
        from aria_esi.core.formatters import to_roman

        assert to_roman(0) == "0"

    def test_all_levels(self):
        """Converts all valid levels."""
        from aria_esi.core.formatters import to_roman

        expected = ["0", "I", "II", "III", "IV", "V"]
        for i, exp in enumerate(expected):
            assert to_roman(i) == exp

    def test_invalid_level(self):
        """Returns string for invalid levels."""
        from aria_esi.core.formatters import to_roman

        assert to_roman(10) == "10"


class TestFormatSkillLevel:
    """Test format_skill_level function."""

    def test_basic_format(self):
        """Formats skill with level."""
        from aria_esi.core.formatters import format_skill_level

        result = format_skill_level("Drones", 5)
        assert result == "Drones V"

    def test_level_1(self):
        """Formats level 1 skill."""
        from aria_esi.core.formatters import format_skill_level

        result = format_skill_level("Mining", 1)
        assert result == "Mining I"


# =============================================================================
# DateTime Tests
# =============================================================================


class TestParseDatetime:
    """Test parse_datetime function."""

    def test_basic_format(self):
        """Parses standard ESI format."""
        from aria_esi.core.formatters import parse_datetime

        result = parse_datetime("2026-01-15T12:30:00Z")
        assert result is not None
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 12
        assert result.minute == 30
        assert result.tzinfo == timezone.utc

    def test_microseconds_format(self):
        """Parses format with microseconds."""
        from aria_esi.core.formatters import parse_datetime

        result = parse_datetime("2026-01-15T12:30:00.123456Z")
        assert result is not None
        assert result.year == 2026

    def test_empty_string(self):
        """Returns None for empty string."""
        from aria_esi.core.formatters import parse_datetime

        result = parse_datetime("")
        assert result is None

    def test_invalid_format(self):
        """Returns None for invalid format."""
        from aria_esi.core.formatters import parse_datetime

        result = parse_datetime("not a date")
        assert result is None


class TestFormatDatetime:
    """Test format_datetime function."""

    def test_formats_correctly(self):
        """Formats datetime to ISO string."""
        from aria_esi.core.formatters import format_datetime

        dt = datetime(2026, 1, 15, 12, 30, 0, tzinfo=timezone.utc)
        result = format_datetime(dt)
        assert result == "2026-01-15T12:30:00Z"


class TestGetUtcNow:
    """Test get_utc_now function."""

    def test_returns_datetime(self):
        """Returns datetime object."""
        from aria_esi.core.formatters import get_utc_now

        result = get_utc_now()
        assert isinstance(result, datetime)
        assert result.tzinfo == timezone.utc


class TestGetUtcTimestamp:
    """Test get_utc_timestamp function."""

    def test_returns_string(self):
        """Returns ISO format string."""
        from aria_esi.core.formatters import get_utc_timestamp

        result = get_utc_timestamp()
        assert isinstance(result, str)
        assert "T" in result
        assert "Z" in result


class TestTimeUntil:
    """Test time_until function."""

    def test_future_time(self):
        """Returns positive for future."""
        from aria_esi.core.formatters import get_utc_now, time_until

        future = get_utc_now().replace(year=2030)
        result = time_until(future)
        assert result > 0

    def test_past_time(self):
        """Returns negative for past."""
        from aria_esi.core.formatters import get_utc_now, time_until

        past = get_utc_now().replace(year=2020)
        result = time_until(past)
        assert result < 0


class TestTimeSince:
    """Test time_since function."""

    def test_past_time(self):
        """Returns positive for past."""
        from aria_esi.core.formatters import get_utc_now, time_since

        past = get_utc_now().replace(year=2020)
        result = time_since(past)
        assert result > 0


# =============================================================================
# Security Status Tests
# =============================================================================


class TestFormatSecurity:
    """Test format_security function."""

    def test_positive(self):
        """Formats positive security."""
        from aria_esi.core.formatters import format_security

        result = format_security(0.5)
        assert result == "0.5"

    def test_negative(self):
        """Formats negative security."""
        from aria_esi.core.formatters import format_security

        result = format_security(-0.3)
        assert result == "-0.3"

    def test_high_sec(self):
        """Formats high-sec status."""
        from aria_esi.core.formatters import format_security

        result = format_security(1.0)
        assert result == "1.0"


class TestGetSecurityClass:
    """Test get_security_class function."""

    def test_high_sec(self):
        """Classifies high-sec correctly."""
        from aria_esi.core.formatters import get_security_class

        assert get_security_class(0.95) == "high_sec"
        assert get_security_class(0.5) == "high_sec"
        assert get_security_class(0.45) == "high_sec"

    def test_low_sec(self):
        """Classifies low-sec correctly."""
        from aria_esi.core.formatters import get_security_class

        assert get_security_class(0.4) == "low_sec"
        assert get_security_class(0.1) == "low_sec"

    def test_null_sec(self):
        """Classifies null-sec correctly."""
        from aria_esi.core.formatters import get_security_class

        assert get_security_class(0.0) == "null_sec"
        assert get_security_class(-0.5) == "null_sec"


class TestGetSecurityDescription:
    """Test get_security_description function."""

    def test_paragon(self):
        """Classifies paragon status."""
        from aria_esi.core.formatters import get_security_description

        assert get_security_description(5.0) == "Paragon"
        assert get_security_description(6.0) == "Paragon"

    def test_upstanding(self):
        """Classifies upstanding status."""
        from aria_esi.core.formatters import get_security_description

        assert get_security_description(3.0) == "Upstanding"

    def test_neutral(self):
        """Classifies neutral status."""
        from aria_esi.core.formatters import get_security_description

        assert get_security_description(0.0) == "Neutral"
        assert get_security_description(1.0) == "Neutral"

    def test_suspect(self):
        """Classifies suspect status."""
        from aria_esi.core.formatters import get_security_description

        assert get_security_description(-1.0) == "Suspect"

    def test_criminal(self):
        """Classifies criminal status."""
        from aria_esi.core.formatters import get_security_description

        assert get_security_description(-3.0) == "Criminal"

    def test_outlaw(self):
        """Classifies outlaw status."""
        from aria_esi.core.formatters import get_security_description

        assert get_security_description(-6.0) == "Outlaw"


# =============================================================================
# Progress Formatting Tests
# =============================================================================


class TestFormatProgress:
    """Test format_progress function."""

    def test_basic(self):
        """Formats basic percentage."""
        from aria_esi.core.formatters import format_progress

        result = format_progress(75, 100)
        assert result == "75.0%"

    def test_zero_total(self):
        """Handles zero total."""
        from aria_esi.core.formatters import format_progress

        result = format_progress(50, 0)
        assert result == "0.0%"

    def test_over_100(self):
        """Caps at 100%."""
        from aria_esi.core.formatters import format_progress

        result = format_progress(150, 100)
        assert result == "100.0%"


class TestCalculateProgress:
    """Test calculate_progress function."""

    def test_in_progress(self):
        """Calculates progress between times."""
        from datetime import timedelta

        from aria_esi.core.formatters import calculate_progress, get_utc_now

        now = get_utc_now()
        start = now - timedelta(hours=1)
        end = now + timedelta(hours=1)

        result = calculate_progress(start, end)
        assert 40 < result < 60  # Should be around 50%

    def test_complete(self):
        """Returns 100% when past end."""
        from datetime import timedelta

        from aria_esi.core.formatters import calculate_progress, get_utc_now

        now = get_utc_now()
        start = now - timedelta(hours=2)
        end = now - timedelta(hours=1)

        result = calculate_progress(start, end)
        assert result == 100.0

    def test_zero_duration(self):
        """Returns 100% for zero duration."""
        from aria_esi.core.formatters import calculate_progress, get_utc_now

        now = get_utc_now()
        result = calculate_progress(now, now)
        assert result == 100.0


# =============================================================================
# EFT Format Tests
# =============================================================================


class TestFormatEftHeader:
    """Test format_eft_header function."""

    def test_basic_header(self):
        """Formats basic header."""
        from aria_esi.core.formatters import format_eft_header

        result = format_eft_header("Vexor")
        assert result == "[Vexor, ARIA Export]"

    def test_custom_name(self):
        """Uses custom fit name."""
        from aria_esi.core.formatters import format_eft_header

        result = format_eft_header("Vexor", "My Fit")
        assert result == "[Vexor, My Fit]"


class TestFormatEftDrone:
    """Test format_eft_drone function."""

    def test_drone_line(self):
        """Formats drone line correctly."""
        from aria_esi.core.formatters import format_eft_drone

        result = format_eft_drone("Hammerhead II", 5)
        assert result == "Hammerhead II x5"


class TestFormatEftCargo:
    """Test format_eft_cargo function."""

    def test_cargo_line(self):
        """Formats cargo line correctly."""
        from aria_esi.core.formatters import format_eft_cargo

        result = format_eft_cargo("Antimatter Charge M", 1000)
        assert result == "Antimatter Charge M x1000"


# =============================================================================
# Ref Type Formatting Tests
# =============================================================================


class TestFormatRefType:
    """Test format_ref_type function."""

    def test_known_type(self):
        """Formats known ref type."""
        from aria_esi.core.formatters import format_ref_type

        result = format_ref_type("bounty_prizes")
        assert result == "Bounties"

    def test_unknown_type(self):
        """Formats unknown ref type as title case."""
        from aria_esi.core.formatters import format_ref_type

        result = format_ref_type("some_unknown_type")
        assert result == "Some Unknown Type"
