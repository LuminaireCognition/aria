"""Tests for HullValueSignal provider."""

from __future__ import annotations

import pytest

from aria_esi.services.redisq.interest_v2.signals.hull_value import HullValueSignal

from ..factories import make_processed_kill


class TestHullValueSignalScore:
    """Tests for HullValueSignal.score() method."""

    @pytest.fixture
    def signal(self) -> HullValueSignal:
        """Create a HullValueSignal instance."""
        return HullValueSignal()

    def test_score_none_kill(self, signal: HullValueSignal) -> None:
        """Test scoring with None kill returns 0."""
        result = signal.score(None, 30000142, {})
        assert result.score == 0.0
        assert result.signal == "hull_value"
        assert result.prefetch_capable is True
        assert "No kill data" in result.reason

    def test_score_none_hull_value(self, signal: HullValueSignal) -> None:
        """Test scoring with None hull_value returns 0."""
        kill = make_processed_kill(hull_value=None)
        result = signal.score(kill, 30000142, {})
        assert result.score == 0.0
        assert "No hull price data" in result.reason

    def test_score_below_minimum(self, signal: HullValueSignal) -> None:
        """Test hull value below minimum threshold scores 0."""
        kill = make_processed_kill(hull_value=50_000_000.0)  # 50M hull
        config = {"min": 500_000_000}  # 500M minimum

        result = signal.score(kill, 30000142, config)
        assert result.score == 0.0
        assert "below minimum" in result.reason.lower()
        assert result.raw_value == 50_000_000.0

    def test_score_sigmoid_default(self, signal: HullValueSignal) -> None:
        """Test sigmoid scaling with default config at pivot."""
        # 2B is default pivot for hull_value
        kill = make_processed_kill(hull_value=2_000_000_000.0)  # 2B
        config = {"scale": "sigmoid"}

        result = signal.score(kill, 30000142, config)
        # At pivot, score should be around 0.5
        assert 0.4 <= result.score <= 0.6, f"Expected ~0.5, got {result.score}"
        assert result.prefetch_capable is True

    def test_score_sigmoid_high_value(self, signal: HullValueSignal) -> None:
        """Test sigmoid scaling with expensive hull."""
        kill = make_processed_kill(hull_value=5_000_000_000.0)  # 5B hull (e.g. capital)
        config = {"scale": "sigmoid"}

        result = signal.score(kill, 30000142, config)
        assert result.score > 0.8

    def test_score_linear(self, signal: HullValueSignal) -> None:
        """Test linear scaling."""
        kill = make_processed_kill(hull_value=1_000_000_000.0)  # 1B
        config = {
            "scale": "linear",
            "min": 0,
            "max": 2_000_000_000,  # 2B
        }

        result = signal.score(kill, 30000142, config)
        # 1B / 2B = 0.5
        assert 0.45 <= result.score <= 0.55

    def test_score_reason_formatting(self, signal: HullValueSignal) -> None:
        """Test ISK value formatting in reason."""
        kill = make_processed_kill(hull_value=1_500_000_000.0)  # 1.5B
        result = signal.score(kill, 30000142, {})
        assert "B" in result.reason
        assert "Hull value:" in result.reason

    def test_score_zero_hull_value(self, signal: HullValueSignal) -> None:
        """Test hull with zero value scores 0 (below any meaningful threshold)."""
        kill = make_processed_kill(hull_value=0.0)
        result = signal.score(kill, 30000142, {})
        assert result.score == 0.0

    def test_score_at_minimum(self, signal: HullValueSignal) -> None:
        """Test hull value at exactly minimum threshold."""
        kill = make_processed_kill(hull_value=500_000_000.0)  # 500M
        config = {"min": 500_000_000}  # 500M minimum

        result = signal.score(kill, 30000142, config)
        assert result.score >= 0.0
        assert result.raw_value == 500_000_000.0

    def test_score_log(self, signal: HullValueSignal) -> None:
        """Test logarithmic scaling."""
        kill = make_processed_kill(hull_value=500_000_000.0)  # 500M
        config = {
            "scale": "log",
            "min": 0,
            "max": 10_000_000_000,  # 10B
        }

        result = signal.score(kill, 30000142, config)
        assert 0.0 < result.score < 1.0

    def test_score_step(self, signal: HullValueSignal) -> None:
        """Test step function scaling."""
        config = {
            "scale": "step",
            "thresholds": [
                {"below": 500_000_000, "score": 0.3},  # < 500M
                {"below": 2_000_000_000, "score": 0.7},  # < 2B
                {"default": 1.0},  # >= 2B
            ],
        }

        low_kill = make_processed_kill(hull_value=200_000_000.0)  # 200M
        result = signal.score(low_kill, 30000142, config)
        assert result.score == 0.3

        mid_kill = make_processed_kill(hull_value=1_000_000_000.0)  # 1B
        result = signal.score(mid_kill, 30000142, config)
        assert result.score == 0.7

        high_kill = make_processed_kill(hull_value=3_000_000_000.0)  # 3B
        result = signal.score(high_kill, 30000142, config)
        assert result.score == 1.0

    def test_score_custom_pivot(self, signal: HullValueSignal) -> None:
        """Test sigmoid with custom pivot point."""
        kill = make_processed_kill(hull_value=1_000_000_000.0)  # 1B
        config = {
            "scale": "sigmoid",
            "pivot": 1_000_000_000,  # 1B pivot
        }

        result = signal.score(kill, 30000142, config)
        assert 0.4 <= result.score <= 0.6

    def test_score_custom_steepness(self, signal: HullValueSignal) -> None:
        """Test sigmoid with custom steepness."""
        kill = make_processed_kill(hull_value=2_500_000_000.0)  # 2.5B
        config_gentle = {
            "scale": "sigmoid",
            "pivot": 2_000_000_000,
            "steepness": 2.0,
        }
        config_steep = {
            "scale": "sigmoid",
            "pivot": 2_000_000_000,
            "steepness": 12.0,
        }

        result_gentle = signal.score(kill, 30000142, config_gentle)
        result_steep = signal.score(kill, 30000142, config_steep)

        assert result_steep.score > result_gentle.score

    def test_score_raw_value_set(self, signal: HullValueSignal) -> None:
        """Test raw_value is set in result."""
        kill = make_processed_kill(hull_value=1_500_000_000.0)
        result = signal.score(kill, 30000142, {})
        assert result.raw_value == 1_500_000_000.0


class TestHullValueSignalValidate:
    """Tests for HullValueSignal.validate() method."""

    @pytest.fixture
    def signal(self) -> HullValueSignal:
        """Create a HullValueSignal instance."""
        return HullValueSignal()

    def test_validate_empty_config(self, signal: HullValueSignal) -> None:
        """Test validation passes for empty config (uses defaults)."""
        errors = signal.validate({})
        assert errors == []

    def test_validate_valid_config(self, signal: HullValueSignal) -> None:
        """Test validation passes for valid config."""
        config = {
            "min": 100_000_000,
            "max": 10_000_000_000,
            "pivot": 2_000_000_000,
            "scale": "sigmoid",
        }
        errors = signal.validate(config)
        assert errors == []

    def test_validate_negative_min(self, signal: HullValueSignal) -> None:
        """Test validation fails for negative min."""
        errors = signal.validate({"min": -100})
        assert len(errors) == 1
        assert "non-negative" in errors[0].lower()

    def test_validate_max_less_than_min(self, signal: HullValueSignal) -> None:
        """Test validation fails when max <= min."""
        errors = signal.validate({"min": 1_000_000_000, "max": 100_000_000})
        assert len(errors) == 1
        assert "greater than min" in errors[0]

    def test_validate_pivot_out_of_range(self, signal: HullValueSignal) -> None:
        """Test validation fails for pivot outside min/max."""
        config = {
            "min": 0,
            "max": 1_000_000_000,
            "pivot": 2_000_000_000,
        }
        errors = signal.validate(config)
        assert len(errors) == 1
        assert "pivot" in errors[0].lower()

    def test_validate_invalid_scale(self, signal: HullValueSignal) -> None:
        """Test validation fails for unknown scale type."""
        errors = signal.validate({"scale": "unknown"})
        assert len(errors) == 1
        assert "Unknown scale type" in errors[0]

    def test_validate_step_without_thresholds(self, signal: HullValueSignal) -> None:
        """Test validation fails for step scale without thresholds."""
        errors = signal.validate({"scale": "step"})
        assert len(errors) == 1
        assert "thresholds" in errors[0].lower()

    def test_validate_step_with_thresholds(self, signal: HullValueSignal) -> None:
        """Test validation passes for step scale with thresholds."""
        config = {
            "scale": "step",
            "thresholds": [
                {"below": 1_000_000_000, "score": 0.5},
                {"default": 1.0},
            ],
        }
        errors = signal.validate(config)
        assert errors == []

    def test_validate_all_scale_types(self, signal: HullValueSignal) -> None:
        """Test validation passes for all valid scale types."""
        for scale in ("sigmoid", "linear", "log"):
            errors = signal.validate({"scale": scale})
            assert errors == [], f"Unexpected errors for scale '{scale}': {errors}"


class TestHullValueSignalProperties:
    """Tests for HullValueSignal class properties."""

    def test_signal_name(self) -> None:
        """Test signal name is correct."""
        signal = HullValueSignal()
        assert signal._name == "hull_value"

    def test_signal_category(self) -> None:
        """Test signal category is correct."""
        signal = HullValueSignal()
        assert signal._category == "value"

    def test_prefetch_capable(self) -> None:
        """Test signal is prefetch capable."""
        signal = HullValueSignal()
        assert signal._prefetch_capable is True
