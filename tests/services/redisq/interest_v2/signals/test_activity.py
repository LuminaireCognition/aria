"""Tests for ActivitySignal provider."""

from __future__ import annotations

from typing import Any

import pytest

from aria_esi.services.redisq.interest_v2.signals.activity import ActivitySignal

from ..factories import make_processed_kill
from .conftest import MockGatecampStatus


class TestActivitySignalScore:
    """Tests for ActivitySignal.score() method."""

    @pytest.fixture
    def signal(self) -> ActivitySignal:
        """Create an ActivitySignal instance."""
        return ActivitySignal()

    def test_score_no_activity_data(self, signal: ActivitySignal) -> None:
        """Test scoring with no activity data returns 0."""
        kill = make_processed_kill()
        # All signals disabled = no self-sufficient querying, no pre-injected data
        config = {
            "spike": {"enabled": False},
            "sustained": {"enabled": False},
            "gatecamp": {"enabled": False},
        }
        result = signal.score(kill, 30000142, config)
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
            "spike": {"enabled": False},
            "sustained": {"enabled": False},
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
            "spike": {"enabled": False},
            "sustained": {"enabled": False},
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


class TestActivitySignalEdgeCases:
    """Tests for edge cases in ActivitySignal scoring."""

    @pytest.fixture
    def signal(self) -> ActivitySignal:
        """Create an ActivitySignal instance."""
        return ActivitySignal()

    def test_sustained_at_exact_threshold_triggers(self, signal: ActivitySignal) -> None:
        """Sustained kills exactly at threshold should trigger (>= comparison)."""
        config = {
            "activity_data": {"spike_detected": False, "sustained_kills": 5},
            "sustained": {"enabled": True, "score": 0.5, "threshold": 5},
        }
        result = signal.score(None, 30000142, config)
        assert result.score == 0.5
        assert "Sustained activity (5 kills)" in result.reason

    def test_sustained_one_below_threshold_does_not_trigger(self, signal: ActivitySignal) -> None:
        """Sustained kills one below threshold should not trigger."""
        config = {
            "activity_data": {"spike_detected": False, "sustained_kills": 4},
            "sustained": {"enabled": True, "score": 0.5, "threshold": 5},
        }
        result = signal.score(None, 30000142, config)
        assert result.score == 0.0

    def test_gatecamp_unknown_confidence_value(self, signal: ActivitySignal) -> None:
        """Unknown confidence in gatecamp_status should not trigger scoring."""
        config = {
            "gatecamp_status": MockGatecampStatus(confidence="extreme"),
            "gatecamp": {"enabled": True, "score": 0.9, "min_confidence": "low"},
            "spike": {"enabled": False},
            "sustained": {"enabled": False},
        }
        result = signal.score(None, 30000142, config)
        # "extreme" maps to 0 in confidence_levels.get(confidence, 0)
        assert result.score == 0.0

    def test_gatecamp_none_confidence_does_not_trigger(self, signal: ActivitySignal) -> None:
        """None confidence in gatecamp_status should not trigger."""
        config = {
            "gatecamp_status": MockGatecampStatus(confidence=None),
            "gatecamp": {"enabled": True, "score": 0.9, "min_confidence": "low"},
            "spike": {"enabled": False},
            "sustained": {"enabled": False},
        }
        result = signal.score(None, 30000142, config)
        assert result.score == 0.0

    def test_all_patterns_equal_score_returns_that_score(self, signal: ActivitySignal) -> None:
        """When multiple patterns have identical scores, max() returns that score."""
        config = {
            "gatecamp_status": MockGatecampStatus(confidence="high"),
            "activity_data": {"spike_detected": True, "sustained_kills": 10},
            "gatecamp": {"enabled": True, "score": 0.5},
            "spike": {"enabled": True, "score": 0.5},
            "sustained": {"enabled": True, "score": 0.5, "threshold": 5},
        }
        result = signal.score(None, 30000142, config)
        assert result.score == 0.5
        assert len(result.raw_value["patterns"]) == 3

    def test_spike_not_detected_returns_zero(self, signal: ActivitySignal) -> None:
        """When spike_detected is False, spike pattern should not contribute."""
        config = {
            "activity_data": {"spike_detected": False, "sustained_kills": 0},
            "spike": {"enabled": True, "score": 0.7},
            "sustained": {"enabled": False},
        }
        result = signal.score(None, 30000142, config)
        assert result.score == 0.0

    def test_spike_enabled_with_empty_spike_config(self, signal: ActivitySignal) -> None:
        """Spike with no config keys should use defaults (enabled: True)."""
        config = {
            "activity_data": {"spike_detected": True, "sustained_kills": 0},
            # spike config not present at all — defaults to {"enabled": True}
        }
        result = signal.score(None, 30000142, config)
        assert result.score == 0.7  # DEFAULT_SPIKE_SCORE


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

    def test_validate_score_at_boundaries(self, signal: ActivitySignal) -> None:
        """Test validation passes for scores at exact boundaries (0.0 and 1.0)."""
        config = {
            "gatecamp": {"score": 0.0},
            "spike": {"score": 1.0},
        }
        errors = signal.validate(config)
        assert errors == []

    def test_validate_multiple_errors_reported(self, signal: ActivitySignal) -> None:
        """Test that all validation errors are collected, not just the first."""
        config = {
            "gatecamp": {"score": 2.0},
            "spike": {"score": -1.0},
            "sustained": "not_a_dict",
        }
        errors = signal.validate(config)
        assert len(errors) == 3


class TestActivitySignalSelfSufficient:
    """Tests for ActivitySignal querying ThreatCache directly."""

    @pytest.fixture
    def signal(self) -> ActivitySignal:
        """Create an ActivitySignal instance."""
        return ActivitySignal()

    def test_spike_queries_threat_cache_when_no_activity_data(
        self, signal: ActivitySignal, monkeypatch
    ) -> None:
        """When no activity_data in config, signal queries ThreatCache."""
        from unittest.mock import MagicMock

        mock_tc = MagicMock()
        mock_tc.detect_activity_spike.return_value = (True, 8.0, 2.0)

        # Monkeypatch the method directly to avoid import-path issues
        monkeypatch.setattr(signal, "_query_spike_data", lambda sys_id, cfg: {
            "spike_detected": True,
            "sustained_kills": 8,
        })

        config = {
            "spike": {"enabled": True, "score": 0.7, "pod_only": True, "threshold": 3.0, "min_current": 5},
        }
        result = signal.score(None, 30000142, config)

        assert result.score == 0.7
        assert "Activity spike" in result.reason

    def test_query_spike_data_calls_threat_cache(self, signal: ActivitySignal, monkeypatch) -> None:
        """_query_spike_data calls ThreatCache.detect_activity_spike with correct params."""
        from unittest.mock import MagicMock

        import aria_esi.services.redisq.threat_cache as tc_mod

        mock_tc = MagicMock()
        mock_tc.detect_activity_spike.return_value = (True, 8.0, 2.0)
        monkeypatch.setattr(tc_mod, "get_threat_cache", lambda: mock_tc)

        spike_config = {"pod_only": True, "threshold": 3.0, "min_current": 5}
        result = signal._query_spike_data(30000142, spike_config)

        assert result is not None
        assert result["spike_detected"] is True
        assert result["sustained_kills"] == 8
        mock_tc.detect_activity_spike.assert_called_once_with(
            30000142,
            spike_threshold=3.0,
            pod_only=True,
            min_current=5,
        )

    def test_spike_does_not_query_when_activity_data_present(
        self, signal: ActivitySignal, monkeypatch
    ) -> None:
        """When activity_data exists, signal should NOT query ThreatCache."""
        called = False
        original = signal._query_spike_data

        def tracking_query(*args, **kwargs):
            nonlocal called
            called = True
            return original(*args, **kwargs)

        monkeypatch.setattr(signal, "_query_spike_data", tracking_query)

        config = {
            "activity_data": {"spike_detected": True, "sustained_kills": 2},
            "spike": {"enabled": True, "score": 0.7},
        }
        result = signal.score(None, 30000142, config)

        assert not called
        assert result.score == 0.7

    def test_spike_graceful_on_threat_cache_failure(
        self, signal: ActivitySignal, monkeypatch
    ) -> None:
        """Signal returns 0 when ThreatCache query fails."""
        monkeypatch.setattr(signal, "_query_spike_data", lambda sys_id, cfg: None)

        config = {
            "spike": {"enabled": True, "score": 0.7},
            "sustained": {"enabled": False},
        }
        result = signal.score(None, 30000142, config)

        assert result.score == 0.0

    def test_sustained_queries_threat_cache_when_no_activity_data(
        self, signal: ActivitySignal, monkeypatch
    ) -> None:
        """When no activity_data, sustained check queries ThreatCache."""
        monkeypatch.setattr(signal, "_query_sustained_data", lambda sys_id, cfg: {
            "spike_detected": False,
            "sustained_kills": 10,
        })

        config = {
            "spike": {"enabled": False},
            "sustained": {"enabled": True, "score": 0.5, "threshold": 5},
        }
        result = signal.score(None, 30000142, config)

        assert result.score == 0.5
        assert "Sustained activity" in result.reason

    def test_query_sustained_data_calls_db(self, signal: ActivitySignal, monkeypatch) -> None:
        """_query_sustained_data calls count_recent_kills."""
        from unittest.mock import MagicMock

        import aria_esi.services.redisq.threat_cache as tc_mod

        mock_tc = MagicMock()
        mock_db = MagicMock()
        mock_db.count_recent_kills.return_value = 10
        mock_tc._get_db.return_value = mock_db
        monkeypatch.setattr(tc_mod, "get_threat_cache", lambda: mock_tc)

        result = signal._query_sustained_data(30000142, {"window_minutes": 120})

        assert result is not None
        assert result["sustained_kills"] == 10
        mock_db.count_recent_kills.assert_called_once_with(system_id=30000142, since_minutes=120)

    def test_query_spike_data_returns_none_on_exception(
        self, signal: ActivitySignal, monkeypatch
    ) -> None:
        """_query_spike_data returns None when get_threat_cache raises."""
        import aria_esi.services.redisq.threat_cache as tc_mod

        def _raise():
            raise RuntimeError("no cache")

        monkeypatch.setattr(tc_mod, "get_threat_cache", _raise)

        result = signal._query_spike_data(30000142, {"threshold": 2.0})
        assert result is None

    def test_query_sustained_data_returns_none_on_exception(
        self, signal: ActivitySignal, monkeypatch
    ) -> None:
        """_query_sustained_data returns None when get_threat_cache raises."""
        import aria_esi.services.redisq.threat_cache as tc_mod

        def _raise():
            raise RuntimeError("no cache")

        monkeypatch.setattr(tc_mod, "get_threat_cache", _raise)

        result = signal._query_sustained_data(30000142, {"window_minutes": 60})
        assert result is None


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
