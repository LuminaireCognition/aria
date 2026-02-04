"""Tests for ActivitySignal provider."""

from __future__ import annotations

from typing import Any

import pytest

from aria_esi.services.redisq.interest_v2.signals.activity import ActivitySignal

from .conftest import MockGatecampStatus, MockProcessedKill


class TestActivitySignalScore:
    """Tests for ActivitySignal.score() method."""

    @pytest.fixture
    def signal(self) -> ActivitySignal:
        """Create an ActivitySignal instance."""
        return ActivitySignal()

    def test_score_no_activity_data(self, signal: ActivitySignal) -> None:
        """Test scoring with no activity data returns 0."""
        kill = MockProcessedKill()
        result = signal.score(kill, 30000142, {})
        assert result.score == 0.0
        assert "No activity data available" in result.reason
        assert result.prefetch_capable is False

    def test_score_gatecamp_high_confidence(
        self, signal: ActivitySignal, mock_gatecamp_high: MockGatecampStatus
    ) -> None:
        """Test scoring with high confidence gatecamp."""
        config = {
            "gatecamp_status": mock_gatecamp_high,
            "gatecamp": {"enabled": True, "score": 0.9},
        }
        result = signal.score(None, 30000142, config)
        assert result.score == 0.9
        assert "Gatecamp" in result.reason
        assert "high" in result.reason.lower()

    def test_score_gatecamp_low_confidence_below_threshold(
        self, signal: ActivitySignal, mock_gatecamp_low: MockGatecampStatus
    ) -> None:
        """Test low confidence gatecamp below medium threshold."""
        config = {
            "gatecamp_status": mock_gatecamp_low,
            "gatecamp": {"enabled": True, "score": 0.9, "min_confidence": "medium"},
        }
        result = signal.score(None, 30000142, config)
        assert result.score == 0.0  # Low < medium threshold

    def test_score_gatecamp_low_confidence_at_threshold(
        self, signal: ActivitySignal, mock_gatecamp_low: MockGatecampStatus
    ) -> None:
        """Test low confidence gatecamp at low threshold."""
        config = {
            "gatecamp_status": mock_gatecamp_low,
            "gatecamp": {"enabled": True, "score": 0.9, "min_confidence": "low"},
        }
        result = signal.score(None, 30000142, config)
        assert result.score == 0.9  # Low >= low threshold

    def test_score_gatecamp_disabled(
        self, signal: ActivitySignal, mock_gatecamp_high: MockGatecampStatus
    ) -> None:
        """Test gatecamp detection when disabled."""
        config = {
            "gatecamp_status": mock_gatecamp_high,
            "gatecamp": {"enabled": False},
        }
        result = signal.score(None, 30000142, config)
        assert result.score == 0.0  # Disabled

    def test_score_activity_spike(
        self, signal: ActivitySignal, mock_activity_spike: dict[str, Any]
    ) -> None:
        """Test scoring with activity spike detected."""
        config = {
            "activity_data": mock_activity_spike,
            "spike": {"enabled": True, "score": 0.7},
        }
        result = signal.score(None, 30000142, config)
        assert result.score == 0.7
        assert "Activity spike" in result.reason

    def test_score_spike_disabled(
        self, signal: ActivitySignal, mock_activity_spike: dict[str, Any]
    ) -> None:
        """Test spike detection when disabled."""
        config = {
            "activity_data": mock_activity_spike,
            "spike": {"enabled": False},
        }
        result = signal.score(None, 30000142, config)
        assert result.score == 0.0

    def test_score_sustained_activity(
        self, signal: ActivitySignal, mock_activity_sustained: dict[str, Any]
    ) -> None:
        """Test scoring with sustained activity."""
        config = {
            "activity_data": mock_activity_sustained,
            "sustained": {"enabled": True, "score": 0.5, "threshold": 5},
        }
        result = signal.score(None, 30000142, config)
        assert result.score == 0.5
        assert "Sustained activity" in result.reason
        assert "10 kills" in result.reason

    def test_score_sustained_below_threshold(
        self, signal: ActivitySignal, mock_activity_quiet: dict[str, Any]
    ) -> None:
        """Test sustained activity below threshold."""
        config = {
            "activity_data": mock_activity_quiet,
            "sustained": {"enabled": True, "score": 0.5, "threshold": 5},
        }
        result = signal.score(None, 30000142, config)
        assert result.score == 0.0  # 1 kill < 5 threshold

    def test_score_sustained_default_threshold(
        self, signal: ActivitySignal, mock_activity_sustained: dict[str, Any]
    ) -> None:
        """Test sustained activity with default threshold (5)."""
        config = {
            "activity_data": mock_activity_sustained,
            "sustained": {"enabled": True, "score": 0.5},
        }
        result = signal.score(None, 30000142, config)
        assert result.score == 0.5  # 10 >= 5

    def test_score_multiple_patterns_max(
        self, signal: ActivitySignal,
        mock_gatecamp_high: MockGatecampStatus,
        mock_activity_spike: dict[str, Any],
    ) -> None:
        """Test maximum score when multiple patterns detected."""
        config = {
            "gatecamp_status": mock_gatecamp_high,
            "activity_data": {**mock_activity_spike, "sustained_kills": 10},
            "gatecamp": {"enabled": True, "score": 0.9},
            "spike": {"enabled": True, "score": 0.7},
            "sustained": {"enabled": True, "score": 0.5, "threshold": 5},
        }
        result = signal.score(None, 30000142, config)
        assert result.score == 0.9  # Max of 0.9, 0.7, 0.5
        # All patterns should be in reason
        assert "Gatecamp" in result.reason
        assert "Activity spike" in result.reason
        assert "Sustained" in result.reason

    def test_score_default_gatecamp_score(self, signal: ActivitySignal) -> None:
        """Test default gatecamp score is 0.9."""
        config = {
            "gatecamp_status": MockGatecampStatus(confidence="high"),
            "gatecamp": {"enabled": True},  # No score specified
        }
        result = signal.score(None, 30000142, config)
        assert result.score == 0.9  # DEFAULT_GATECAMP_SCORE

    def test_score_default_spike_score(self, signal: ActivitySignal) -> None:
        """Test default spike score is 0.7."""
        config = {
            "activity_data": {"spike_detected": True, "sustained_kills": 0},
            "spike": {"enabled": True},  # No score specified
        }
        result = signal.score(None, 30000142, config)
        assert result.score == 0.7  # DEFAULT_SPIKE_SCORE

    def test_score_default_sustained_score(self, signal: ActivitySignal) -> None:
        """Test default sustained score is 0.5."""
        config = {
            "activity_data": {"spike_detected": False, "sustained_kills": 10},
            "sustained": {"enabled": True},  # No score specified
        }
        result = signal.score(None, 30000142, config)
        assert result.score == 0.5  # DEFAULT_SUSTAINED_SCORE

    def test_score_raw_value_includes_patterns(
        self, signal: ActivitySignal, mock_gatecamp_high: MockGatecampStatus
    ) -> None:
        """Test raw_value includes detected patterns."""
        config = {
            "gatecamp_status": mock_gatecamp_high,
            "activity_data": {"spike_detected": True, "sustained_kills": 10},
            "gatecamp": {"enabled": True},
            "spike": {"enabled": True},
            "sustained": {"enabled": True, "threshold": 5},
        }
        result = signal.score(None, 30000142, config)
        assert result.raw_value is not None
        assert "patterns" in result.raw_value
        assert len(result.raw_value["patterns"]) == 3

    def test_score_no_patterns_detected(
        self, signal: ActivitySignal, mock_activity_quiet: dict[str, Any]
    ) -> None:
        """Test scoring when no patterns are detected."""
        config = {
            "activity_data": mock_activity_quiet,
            "spike": {"enabled": True},
            "sustained": {"enabled": True, "threshold": 5},
        }
        result = signal.score(None, 30000142, config)
        assert result.score == 0.0
        assert "No notable activity patterns" in result.reason

    def test_score_gatecamp_medium_confidence(self, signal: ActivitySignal) -> None:
        """Test medium confidence gatecamp meets medium threshold."""
        config = {
            "gatecamp_status": MockGatecampStatus(confidence="medium"),
            "gatecamp": {"enabled": True, "score": 0.8, "min_confidence": "medium"},
        }
        result = signal.score(None, 30000142, config)
        assert result.score == 0.8


class TestActivitySignalValidate:
    """Tests for ActivitySignal.validate() method."""

    @pytest.fixture
    def signal(self) -> ActivitySignal:
        """Create an ActivitySignal instance."""
        return ActivitySignal()

    def test_validate_empty_config(self, signal: ActivitySignal) -> None:
        """Test validation passes for empty config."""
        errors = signal.validate({})
        assert errors == []

    def test_validate_valid_config(self, signal: ActivitySignal) -> None:
        """Test validation passes for valid config."""
        config = {
            "gatecamp": {"enabled": True, "score": 0.9, "min_confidence": "medium"},
            "spike": {"enabled": True, "score": 0.7},
            "sustained": {"enabled": True, "score": 0.5},
        }
        errors = signal.validate(config)
        assert errors == []

    def test_validate_pattern_not_dict(self, signal: ActivitySignal) -> None:
        """Test validation fails when pattern config is not a dict."""
        config = {"gatecamp": "enabled"}
        errors = signal.validate(config)
        assert len(errors) == 1
        assert "must be a dictionary" in errors[0]

    def test_validate_score_out_of_range(self, signal: ActivitySignal) -> None:
        """Test validation fails for score outside [0, 1]."""
        config = {"gatecamp": {"score": 1.5}}
        errors = signal.validate(config)
        assert len(errors) == 1
        assert "between 0 and 1" in errors[0]

    def test_validate_score_negative(self, signal: ActivitySignal) -> None:
        """Test validation fails for negative score."""
        config = {"spike": {"score": -0.1}}
        errors = signal.validate(config)
        assert len(errors) == 1
        assert "between 0 and 1" in errors[0]

    def test_validate_invalid_confidence(self, signal: ActivitySignal) -> None:
        """Test validation fails for invalid confidence level."""
        config = {"gatecamp": {"min_confidence": "very_high"}}
        errors = signal.validate(config)
        assert len(errors) == 1
        assert "low/medium/high" in errors[0]

    def test_validate_valid_confidence_levels(self, signal: ActivitySignal) -> None:
        """Test validation passes for all valid confidence levels."""
        for confidence in ("low", "medium", "high"):
            config = {"gatecamp": {"min_confidence": confidence}}
            errors = signal.validate(config)
            assert errors == [], f"Unexpected errors for confidence '{confidence}'"

    def test_validate_multiple_patterns(self, signal: ActivitySignal) -> None:
        """Test validation checks all pattern configs."""
        config = {
            "gatecamp": {"score": 0.9},
            "spike": {"score": 0.7},
            "sustained": {"score": 0.5},
        }
        errors = signal.validate(config)
        assert errors == []


class TestActivitySignalProperties:
    """Tests for ActivitySignal class properties."""

    def test_signal_name(self) -> None:
        """Test signal name is correct."""
        signal = ActivitySignal()
        assert signal._name == "activity"

    def test_signal_category(self) -> None:
        """Test signal category is correct."""
        signal = ActivitySignal()
        assert signal._category == "activity"

    def test_prefetch_capable(self) -> None:
        """Test signal is NOT prefetch capable."""
        signal = ActivitySignal()
        assert signal._prefetch_capable is False

    def test_default_scores(self) -> None:
        """Test default score constants."""
        signal = ActivitySignal()
        assert signal.DEFAULT_GATECAMP_SCORE == 0.9
        assert signal.DEFAULT_SPIKE_SCORE == 0.7
        assert signal.DEFAULT_SUSTAINED_SCORE == 0.5
