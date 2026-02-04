"""Tests for ValueSignal provider."""

from __future__ import annotations

import pytest

from aria_esi.services.redisq.interest_v2.signals.value import ValueSignal

from .conftest import MockProcessedKill


class TestValueSignalScore:
    """Tests for ValueSignal.score() method."""

    @pytest.fixture
    def signal(self) -> ValueSignal:
        """Create a ValueSignal instance."""
        return ValueSignal()

    def test_score_none_kill(self, signal: ValueSignal) -> None:
        """Test scoring with None kill returns 0."""
        result = signal.score(None, 30000142, {})
        assert result.score == 0.0
        assert result.signal == "value"
        assert result.prefetch_capable is True
        assert "No kill data" in result.reason

    def test_score_below_minimum(self, signal: ValueSignal) -> None:
        """Test kill below minimum threshold scores 0."""
        kill = MockProcessedKill(total_value=10_000_000.0)  # 10M
        config = {"min": 50_000_000}  # 50M minimum

        result = signal.score(kill, 30000142, config)
        assert result.score == 0.0
        assert "below minimum" in result.reason.lower()
        assert result.raw_value == 10_000_000.0

    def test_score_at_minimum(self, signal: ValueSignal) -> None:
        """Test kill at exactly minimum threshold."""
        kill = MockProcessedKill(total_value=50_000_000.0)  # 50M
        config = {"min": 50_000_000}  # 50M minimum

        result = signal.score(kill, 30000142, config)
        # At minimum, should get a score (depends on scaling)
        assert result.score >= 0.0
        assert result.raw_value == 50_000_000.0

    def test_score_sigmoid_default(self, signal: ValueSignal) -> None:
        """Test sigmoid scaling with default config."""
        # 500M is default pivot point
        kill = MockProcessedKill(total_value=500_000_000.0)  # 500M
        config = {"scale": "sigmoid"}

        result = signal.score(kill, 30000142, config)
        # At pivot, score should be around 0.5
        assert 0.4 <= result.score <= 0.6, f"Expected ~0.5, got {result.score}"
        assert result.prefetch_capable is True

    def test_score_sigmoid_high_value(
        self, signal: ValueSignal, mock_kill_high_value: MockProcessedKill
    ) -> None:
        """Test sigmoid scaling with high value kill."""
        config = {"scale": "sigmoid"}

        result = signal.score(mock_kill_high_value, 30000142, config)
        # 3.5B should score high
        assert result.score > 0.8

    def test_score_linear(self, signal: ValueSignal) -> None:
        """Test linear scaling."""
        kill = MockProcessedKill(total_value=500_000_000.0)  # 500M
        config = {
            "scale": "linear",
            "min": 0,
            "max": 1_000_000_000,  # 1B
        }

        result = signal.score(kill, 30000142, config)
        # 500M / 1B = 0.5
        assert 0.45 <= result.score <= 0.55

    def test_score_linear_at_max(self, signal: ValueSignal) -> None:
        """Test linear scaling at maximum."""
        kill = MockProcessedKill(total_value=2_000_000_000.0)  # 2B
        config = {
            "scale": "linear",
            "min": 0,
            "max": 1_000_000_000,  # 1B
        }

        result = signal.score(kill, 30000142, config)
        # Above max should clamp to 1.0
        assert result.score == 1.0

    def test_score_log(self, signal: ValueSignal) -> None:
        """Test logarithmic scaling."""
        kill = MockProcessedKill(total_value=100_000_000.0)  # 100M
        config = {
            "scale": "log",
            "min": 0,
            "max": 10_000_000_000,  # 10B
        }

        result = signal.score(kill, 30000142, config)
        # Log scaling compresses high values
        assert 0.0 < result.score < 1.0

    def test_score_step(self, signal: ValueSignal) -> None:
        """Test step function scaling."""
        config = {
            "scale": "step",
            "thresholds": [
                {"below": 100_000_000, "score": 0.3},  # < 100M
                {"below": 1_000_000_000, "score": 0.7},  # < 1B
                {"default": 1.0},  # >= 1B
            ],
        }

        # Test each tier
        low_kill = MockProcessedKill(total_value=50_000_000.0)  # 50M
        result = signal.score(low_kill, 30000142, config)
        assert result.score == 0.3

        mid_kill = MockProcessedKill(total_value=500_000_000.0)  # 500M
        result = signal.score(mid_kill, 30000142, config)
        assert result.score == 0.7

        high_kill = MockProcessedKill(total_value=2_000_000_000.0)  # 2B
        result = signal.score(high_kill, 30000142, config)
        assert result.score == 1.0

    def test_score_custom_pivot(self, signal: ValueSignal) -> None:
        """Test sigmoid with custom pivot point."""
        kill = MockProcessedKill(total_value=1_000_000_000.0)  # 1B
        config = {
            "scale": "sigmoid",
            "pivot": 1_000_000_000,  # 1B pivot
        }

        result = signal.score(kill, 30000142, config)
        # At pivot, score should be around 0.5
        assert 0.4 <= result.score <= 0.6

    def test_score_custom_steepness(self, signal: ValueSignal) -> None:
        """Test sigmoid with custom steepness."""
        kill = MockProcessedKill(total_value=600_000_000.0)  # 600M
        config_gentle = {
            "scale": "sigmoid",
            "pivot": 500_000_000,
            "steepness": 2.0,  # Gentle curve
        }
        config_steep = {
            "scale": "sigmoid",
            "pivot": 500_000_000,
            "steepness": 12.0,  # Steep curve
        }

        result_gentle = signal.score(kill, 30000142, config_gentle)
        result_steep = signal.score(kill, 30000142, config_steep)

        # Steep curve should be closer to 1.0 above pivot
        assert result_steep.score > result_gentle.score

    def test_score_reason_formatting(self, signal: ValueSignal) -> None:
        """Test ISK value formatting in reason."""
        configs = [
            (1_000_000_000.0, "B"),  # 1B
            (500_000_000.0, "M"),  # 500M
            (50_000.0, "K"),  # 50K
        ]

        for value, expected_suffix in configs:
            kill = MockProcessedKill(total_value=value)
            result = signal.score(kill, 30000142, {})
            assert expected_suffix in result.reason, f"Expected '{expected_suffix}' for {value}"

    def test_score_zero_value(self, signal: ValueSignal) -> None:
        """Test kill with zero value."""
        kill = MockProcessedKill(total_value=0.0)
        result = signal.score(kill, 30000142, {})
        assert result.score == 0.0


class TestValueSignalValidate:
    """Tests for ValueSignal.validate() method."""

    @pytest.fixture
    def signal(self) -> ValueSignal:
        """Create a ValueSignal instance."""
        return ValueSignal()

    def test_validate_empty_config(self, signal: ValueSignal) -> None:
        """Test validation passes for empty config (uses defaults)."""
        errors = signal.validate({})
        assert errors == []

    def test_validate_valid_config(self, signal: ValueSignal) -> None:
        """Test validation passes for valid config."""
        config = {
            "min": 10_000_000,
            "max": 10_000_000_000,
            "pivot": 500_000_000,
            "scale": "sigmoid",
        }
        errors = signal.validate(config)
        assert errors == []

    def test_validate_negative_min(self, signal: ValueSignal) -> None:
        """Test validation fails for negative min."""
        errors = signal.validate({"min": -100})
        assert len(errors) == 1
        assert "non-negative" in errors[0].lower()

    def test_validate_max_less_than_min(self, signal: ValueSignal) -> None:
        """Test validation fails when max <= min."""
        errors = signal.validate({"min": 1_000_000_000, "max": 100_000_000})
        assert len(errors) == 1
        assert "greater than min" in errors[0]

    def test_validate_pivot_out_of_range(self, signal: ValueSignal) -> None:
        """Test validation fails for pivot outside min/max."""
        config = {
            "min": 0,
            "max": 1_000_000_000,
            "pivot": 2_000_000_000,  # Above max
        }
        errors = signal.validate(config)
        assert len(errors) == 1
        assert "pivot" in errors[0].lower()

    def test_validate_invalid_scale(self, signal: ValueSignal) -> None:
        """Test validation fails for unknown scale type."""
        errors = signal.validate({"scale": "unknown"})
        assert len(errors) == 1
        assert "Unknown scale type" in errors[0]

    def test_validate_step_without_thresholds(self, signal: ValueSignal) -> None:
        """Test validation fails for step scale without thresholds."""
        errors = signal.validate({"scale": "step"})
        assert len(errors) == 1
        assert "thresholds" in errors[0].lower()

    def test_validate_step_with_thresholds(self, signal: ValueSignal) -> None:
        """Test validation passes for step scale with thresholds."""
        config = {
            "scale": "step",
            "thresholds": [
                {"below": 100_000_000, "score": 0.3},
                {"default": 1.0},
            ],
        }
        errors = signal.validate(config)
        assert errors == []

    def test_validate_all_scale_types(self, signal: ValueSignal) -> None:
        """Test validation passes for all valid scale types."""
        for scale in ("sigmoid", "linear", "log"):
            errors = signal.validate({"scale": scale})
            assert errors == [], f"Unexpected errors for scale '{scale}': {errors}"


class TestValueSignalProperties:
    """Tests for ValueSignal class properties."""

    def test_signal_name(self) -> None:
        """Test signal name is correct."""
        signal = ValueSignal()
        assert signal._name == "value"

    def test_signal_category(self) -> None:
        """Test signal category is correct."""
        signal = ValueSignal()
        assert signal._category == "value"

    def test_prefetch_capable(self) -> None:
        """Test signal is prefetch capable."""
        signal = ValueSignal()
        assert signal._prefetch_capable is True
