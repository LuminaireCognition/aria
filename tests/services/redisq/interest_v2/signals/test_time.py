"""Tests for TimeSignal provider."""

from __future__ import annotations

from datetime import datetime, timezone
from datetime import time as dt_time

import pytest

from aria_esi.services.redisq.interest_v2.signals.time import (
    TimeSignal,
    _parse_time,
    _time_in_window,
)

from .conftest import MockProcessedKill


class TestTimeSignalScore:
    """Tests for TimeSignal.score() method."""

    @pytest.fixture
    def signal(self) -> TimeSignal:
        """Create a TimeSignal instance."""
        return TimeSignal()

    def test_score_no_windows(self, signal: TimeSignal) -> None:
        """Test scoring with no windows configured returns 1.0."""
        kill = MockProcessedKill()
        result = signal.score(kill, 30000142, {})
        assert result.score == 1.0
        assert "No time windows configured" in result.reason

    def test_score_empty_windows(self, signal: TimeSignal) -> None:
        """Test scoring with empty windows list returns 1.0."""
        kill = MockProcessedKill()
        result = signal.score(kill, 30000142, {"windows": []})
        assert result.score == 1.0

    def test_score_none_kill_uses_current_time(self, signal: TimeSignal) -> None:
        """Test scoring with None kill uses current time."""
        config = {
            "windows": [
                {"start": "00:00", "end": "23:59", "score": 0.8, "label": "All day"},
            ]
        }
        result = signal.score(None, 30000142, config)
        assert result.score == 0.8  # Should match the all-day window

    def test_score_in_window(
        self, signal: TimeSignal, mock_kill_primetime: MockProcessedKill
    ) -> None:
        """Test scoring when kill is within a configured window."""
        config = {
            "windows": [
                {"start": "18:00", "end": "23:00", "score": 1.0, "label": "Prime time"},
            ]
        }
        result = signal.score(mock_kill_primetime, 30000142, config)
        assert result.score == 1.0
        assert "Prime time" in result.reason

    def test_score_outside_window(
        self, signal: TimeSignal, mock_kill_offhours: MockProcessedKill
    ) -> None:
        """Test scoring when kill is outside all windows."""
        config = {
            "windows": [
                {"start": "18:00", "end": "23:00", "score": 1.0, "label": "Prime time"},
            ],
            "default_score": 0.3,
        }
        result = signal.score(mock_kill_offhours, 30000142, config)
        assert result.score == 0.3
        assert "Outside configured time windows" in result.reason

    def test_score_default_outside_window(self, signal: TimeSignal) -> None:
        """Test default score (0.5) when outside windows."""
        kill = MockProcessedKill(
            kill_time=datetime(2024, 1, 15, 4, 0, 0, tzinfo=timezone.utc)  # 04:00
        )
        config = {
            "windows": [
                {"start": "10:00", "end": "12:00", "score": 1.0},
            ]
        }
        result = signal.score(kill, 30000142, config)
        assert result.score == 0.5  # DEFAULT_SCORE

    def test_score_overnight_window_before_midnight(self, signal: TimeSignal) -> None:
        """Test overnight window with kill before midnight."""
        kill = MockProcessedKill(
            kill_time=datetime(2024, 1, 15, 23, 30, 0, tzinfo=timezone.utc)  # 23:30
        )
        config = {
            "windows": [
                {"start": "22:00", "end": "06:00", "score": 0.9, "label": "Late night"},
            ]
        }
        result = signal.score(kill, 30000142, config)
        assert result.score == 0.9
        assert "Late night" in result.reason

    def test_score_overnight_window_after_midnight(
        self, signal: TimeSignal, mock_kill_midnight: MockProcessedKill
    ) -> None:
        """Test overnight window with kill after midnight."""
        config = {
            "windows": [
                {"start": "22:00", "end": "06:00", "score": 0.9, "label": "Late night"},
            ]
        }
        # 00:00 should be in the overnight window
        result = signal.score(mock_kill_midnight, 30000142, config)
        assert result.score == 0.9

    def test_score_multiple_windows_first_match(self, signal: TimeSignal) -> None:
        """Test first matching window is used."""
        kill = MockProcessedKill(
            kill_time=datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)  # 14:00
        )
        config = {
            "windows": [
                {"start": "10:00", "end": "16:00", "score": 0.6, "label": "Work hours"},
                {"start": "12:00", "end": "18:00", "score": 0.8, "label": "Afternoon"},
            ]
        }
        result = signal.score(kill, 30000142, config)
        assert result.score == 0.6  # First window matches
        assert "Work hours" in result.reason

    def test_score_timezone_conversion(self, signal: TimeSignal) -> None:
        """Test timezone conversion."""
        # Kill at 15:00 UTC = 10:00 US/Eastern (assuming standard time)
        kill = MockProcessedKill(
            kill_time=datetime(2024, 1, 15, 15, 0, 0, tzinfo=timezone.utc)  # 15:00 UTC
        )
        config = {
            "timezone": "America/New_York",
            "windows": [
                {"start": "09:00", "end": "11:00", "score": 1.0, "label": "EST morning"},
            ],
        }
        result = signal.score(kill, 30000142, config)
        assert result.score == 1.0  # Should match the EST window

    def test_score_invalid_timezone_fallback(self, signal: TimeSignal) -> None:
        """Test invalid timezone falls back to UTC."""
        kill = MockProcessedKill(
            kill_time=datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        )
        config = {
            "timezone": "Invalid/Timezone",
            "windows": [
                {"start": "11:00", "end": "13:00", "score": 1.0},
            ],
        }
        # Should still work with UTC fallback
        result = signal.score(kill, 30000142, config)
        assert result.score == 1.0

    def test_score_raw_value_includes_time(self, signal: TimeSignal) -> None:
        """Test raw_value includes the evaluated time."""
        kill = MockProcessedKill(
            kill_time=datetime(2024, 1, 15, 12, 30, 0, tzinfo=timezone.utc)
        )
        config = {
            "windows": [
                {"start": "12:00", "end": "13:00", "score": 1.0, "label": "Noon"},
            ]
        }
        result = signal.score(kill, 30000142, config)
        assert result.raw_value is not None
        assert "time" in result.raw_value

    def test_score_window_boundary_start(self, signal: TimeSignal) -> None:
        """Test kill exactly at window start is included."""
        kill = MockProcessedKill(
            kill_time=datetime(2024, 1, 15, 18, 0, 0, tzinfo=timezone.utc)
        )
        config = {
            "windows": [
                {"start": "18:00", "end": "20:00", "score": 1.0},
            ]
        }
        result = signal.score(kill, 30000142, config)
        assert result.score == 1.0

    def test_score_window_boundary_end(self, signal: TimeSignal) -> None:
        """Test kill exactly at window end is included."""
        kill = MockProcessedKill(
            kill_time=datetime(2024, 1, 15, 20, 0, 0, tzinfo=timezone.utc)
        )
        config = {
            "windows": [
                {"start": "18:00", "end": "20:00", "score": 1.0},
            ]
        }
        result = signal.score(kill, 30000142, config)
        assert result.score == 1.0


class TestTimeSignalValidate:
    """Tests for TimeSignal.validate() method."""

    @pytest.fixture
    def signal(self) -> TimeSignal:
        """Create a TimeSignal instance."""
        return TimeSignal()

    def test_validate_empty_config(self, signal: TimeSignal) -> None:
        """Test validation passes for empty config."""
        errors = signal.validate({})
        assert errors == []

    def test_validate_valid_windows(self, signal: TimeSignal) -> None:
        """Test validation passes for valid windows."""
        config = {
            "windows": [
                {"start": "09:00", "end": "17:00", "score": 0.8, "label": "Work"},
                {"start": "18:00", "end": "23:00", "score": 1.0, "label": "Prime"},
            ]
        }
        errors = signal.validate(config)
        assert errors == []

    def test_validate_missing_start(self, signal: TimeSignal) -> None:
        """Test validation fails when start is missing."""
        config = {"windows": [{"end": "17:00", "score": 0.8}]}
        errors = signal.validate(config)
        assert len(errors) == 1
        assert "start" in errors[0]

    def test_validate_missing_end(self, signal: TimeSignal) -> None:
        """Test validation fails when end is missing."""
        config = {"windows": [{"start": "09:00", "score": 0.8}]}
        errors = signal.validate(config)
        assert len(errors) == 1
        assert "end" in errors[0]

    def test_validate_invalid_time_format(self, signal: TimeSignal) -> None:
        """Test validation fails for invalid time format."""
        config = {"windows": [{"start": "9am", "end": "5pm", "score": 0.8}]}
        errors = signal.validate(config)
        assert len(errors) == 2  # Both start and end invalid
        assert "HH:MM" in errors[0]

    def test_validate_score_out_of_range(self, signal: TimeSignal) -> None:
        """Test validation fails for scores outside [0, 1]."""
        config = {"windows": [{"start": "09:00", "end": "17:00", "score": 1.5}]}
        errors = signal.validate(config)
        assert len(errors) == 1
        assert "between 0 and 1" in errors[0]

    def test_validate_window_not_dict(self, signal: TimeSignal) -> None:
        """Test validation fails when window is not a dict."""
        config = {"windows": ["09:00-17:00"]}
        errors = signal.validate(config)
        assert len(errors) == 1
        assert "must be a dictionary" in errors[0]

    def test_validate_invalid_timezone(self, signal: TimeSignal) -> None:
        """Test validation fails for invalid timezone."""
        config = {"timezone": "Invalid/Timezone"}
        errors = signal.validate(config)
        assert len(errors) == 1
        assert "Invalid timezone" in errors[0]

    def test_validate_valid_timezone(self, signal: TimeSignal) -> None:
        """Test validation passes for valid timezone."""
        config = {"timezone": "America/New_York"}
        errors = signal.validate(config)
        assert errors == []

    def test_validate_utc_timezone(self, signal: TimeSignal) -> None:
        """Test validation passes for UTC timezone."""
        config = {"timezone": "UTC"}
        errors = signal.validate(config)
        assert errors == []


class TestTimeSignalProperties:
    """Tests for TimeSignal class properties."""

    def test_signal_name(self) -> None:
        """Test signal name is correct."""
        signal = TimeSignal()
        assert signal._name == "time"

    def test_signal_category(self) -> None:
        """Test signal category is correct."""
        signal = TimeSignal()
        assert signal._category == "time"

    def test_prefetch_capable(self) -> None:
        """Test signal is prefetch capable."""
        signal = TimeSignal()
        assert signal._prefetch_capable is True


class TestParseTime:
    """Tests for _parse_time helper function."""

    def test_parse_valid_time(self) -> None:
        """Test parsing valid time strings."""
        assert _parse_time("09:30") == dt_time(hour=9, minute=30)
        assert _parse_time("23:59") == dt_time(hour=23, minute=59)
        assert _parse_time("00:00") == dt_time(hour=0, minute=0)

    def test_parse_invalid_format(self) -> None:
        """Test parsing invalid time format raises ValueError."""
        with pytest.raises(ValueError):
            _parse_time("9am")
        with pytest.raises(ValueError):
            _parse_time("")
        with pytest.raises(ValueError):
            _parse_time("09")


class TestTimeInWindow:
    """Tests for _time_in_window helper function."""

    def test_normal_window_inside(self) -> None:
        """Test time inside normal window."""
        start = dt_time(hour=9, minute=0)
        end = dt_time(hour=17, minute=0)
        check = dt_time(hour=12, minute=0)
        assert _time_in_window(check, start, end) is True

    def test_normal_window_outside(self) -> None:
        """Test time outside normal window."""
        start = dt_time(hour=9, minute=0)
        end = dt_time(hour=17, minute=0)
        check = dt_time(hour=20, minute=0)
        assert _time_in_window(check, start, end) is False

    def test_normal_window_at_start(self) -> None:
        """Test time exactly at window start."""
        start = dt_time(hour=9, minute=0)
        end = dt_time(hour=17, minute=0)
        check = dt_time(hour=9, minute=0)
        assert _time_in_window(check, start, end) is True

    def test_normal_window_at_end(self) -> None:
        """Test time exactly at window end."""
        start = dt_time(hour=9, minute=0)
        end = dt_time(hour=17, minute=0)
        check = dt_time(hour=17, minute=0)
        assert _time_in_window(check, start, end) is True

    def test_overnight_window_before_midnight(self) -> None:
        """Test overnight window - time before midnight."""
        start = dt_time(hour=22, minute=0)
        end = dt_time(hour=6, minute=0)
        check = dt_time(hour=23, minute=0)
        assert _time_in_window(check, start, end) is True

    def test_overnight_window_after_midnight(self) -> None:
        """Test overnight window - time after midnight."""
        start = dt_time(hour=22, minute=0)
        end = dt_time(hour=6, minute=0)
        check = dt_time(hour=3, minute=0)
        assert _time_in_window(check, start, end) is True

    def test_overnight_window_outside(self) -> None:
        """Test overnight window - time outside."""
        start = dt_time(hour=22, minute=0)
        end = dt_time(hour=6, minute=0)
        check = dt_time(hour=12, minute=0)
        assert _time_in_window(check, start, end) is False

    def test_overnight_window_at_midnight(self) -> None:
        """Test overnight window - exactly at midnight."""
        start = dt_time(hour=22, minute=0)
        end = dt_time(hour=6, minute=0)
        check = dt_time(hour=0, minute=0)
        assert _time_in_window(check, start, end) is True
