"""
Tests for Interest Engine v2 scaling functions.
"""

import pytest

from aria_esi.services.redisq.interest_v2.scaling.builtin import (
    InverseScaling,
    LinearScaling,
    LogScaling,
    SigmoidScaling,
    StepScaling,
    scale_value,
)


class TestSigmoidScaling:
    """Tests for sigmoid scaling function."""

    def test_basic_scaling(self):
        scaler = SigmoidScaling()
        config = {"min": 0, "max": 1_000_000_000, "pivot": 500_000_000}

        # At pivot, score should be ~0.5
        score = scaler.scale(500_000_000, config)
        assert 0.45 <= score <= 0.55

        # Below min
        score = scaler.scale(-1, config)
        assert score == 0.0

        # Above max
        score = scaler.scale(2_000_000_000, config)
        assert score == 1.0

    def test_steepness_effect(self):
        scaler = SigmoidScaling()
        config = {"min": 0, "max": 1000, "pivot": 500, "steepness": 10}

        # Higher steepness = sharper transition
        low_score = scaler.scale(400, config)
        high_score = scaler.scale(600, config)

        # With high steepness, difference should be significant (> 0.4)
        assert high_score - low_score > 0.4

    def test_validation(self):
        scaler = SigmoidScaling()

        # Valid config
        errors = scaler.validate({"min": 0, "max": 1000, "pivot": 500})
        assert errors == []

        # Invalid: min >= max
        errors = scaler.validate({"min": 1000, "max": 100})
        assert len(errors) == 1

        # Invalid: pivot outside range
        errors = scaler.validate({"min": 0, "max": 1000, "pivot": 2000})
        assert len(errors) == 1

        # Invalid: negative steepness
        errors = scaler.validate({"min": 0, "max": 1000, "steepness": -1})
        assert len(errors) == 1


class TestLinearScaling:
    """Tests for linear scaling function."""

    def test_basic_scaling(self):
        scaler = LinearScaling()
        config = {"min": 0, "max": 100}

        assert scaler.scale(0, config) == 0.0
        assert scaler.scale(50, config) == 0.5
        assert scaler.scale(100, config) == 1.0

    def test_clamping(self):
        scaler = LinearScaling()
        config = {"min": 0, "max": 100}

        assert scaler.scale(-10, config) == 0.0
        assert scaler.scale(200, config) == 1.0

    def test_invert(self):
        scaler = LinearScaling()
        config = {"min": 0, "max": 100, "invert": True}

        assert scaler.scale(0, config) == 1.0
        assert scaler.scale(100, config) == 0.0
        assert scaler.scale(50, config) == 0.5

    def test_validation(self):
        scaler = LinearScaling()

        errors = scaler.validate({"min": 0, "max": 100})
        assert errors == []

        errors = scaler.validate({"min": 100, "max": 50})
        assert len(errors) == 1


class TestLogScaling:
    """Tests for logarithmic scaling function."""

    def test_basic_scaling(self):
        scaler = LogScaling()
        config = {"min": 1, "max": 1000}

        # At min, score should be 0
        score = scaler.scale(1, config)
        assert score == pytest.approx(0.0, abs=0.01)

        # At max, score should be 1
        score = scaler.scale(1000, config)
        assert score == pytest.approx(1.0, abs=0.01)

        # Log grows slowly - middle value should be less than 0.5
        score = scaler.scale(100, config)
        assert 0.3 < score < 0.8

    def test_wide_range(self):
        """Log scaling should handle wide value ranges well."""
        scaler = LogScaling()
        config = {"min": 1, "max": 1_000_000_000}  # 1 to 1B

        # 1M should give meaningful score even in huge range
        score = scaler.scale(1_000_000, config)
        assert 0.3 < score < 0.8

    def test_validation(self):
        scaler = LogScaling()

        errors = scaler.validate({"min": 1, "max": 1000, "base": 10})
        assert errors == []

        errors = scaler.validate({"min": 100, "max": 50})
        assert len(errors) == 1

        errors = scaler.validate({"base": 0.5})
        assert len(errors) == 1


class TestStepScaling:
    """Tests for step (threshold) scaling function."""

    def test_basic_thresholds(self):
        scaler = StepScaling()
        config = {
            "thresholds": [
                {"below": 100_000_000, "score": 0.3},  # < 100M
                {"below": 1_000_000_000, "score": 0.8},  # < 1B
                {"default": 1.0},  # >= 1B
            ]
        }

        assert scaler.scale(50_000_000, config) == 0.3
        assert scaler.scale(500_000_000, config) == 0.8
        assert scaler.scale(5_000_000_000, config) == 1.0

    def test_edge_cases(self):
        scaler = StepScaling()
        config = {
            "thresholds": [
                {"below": 100, "score": 0.0},
                {"default": 1.0},
            ]
        }

        # Exactly at threshold should be caught by next rule
        assert scaler.scale(100, config) == 1.0
        assert scaler.scale(99, config) == 0.0

    def test_above_threshold(self):
        scaler = StepScaling()
        config = {
            "thresholds": [
                {"above": 1_000_000_000, "score": 1.0},  # > 1B
                {"default": 0.3},
            ]
        }

        assert scaler.scale(2_000_000_000, config) == 1.0
        assert scaler.scale(500_000_000, config) == 0.3

    def test_validation(self):
        scaler = StepScaling()

        # Valid config
        errors = scaler.validate(
            {
                "thresholds": [
                    {"below": 100, "score": 0.3},
                    {"default": 1.0},
                ]
            }
        )
        assert errors == []

        # Missing thresholds
        errors = scaler.validate({})
        assert len(errors) == 1

        # Invalid threshold (no below/above/default)
        errors = scaler.validate({"thresholds": [{"score": 0.5}]})
        assert len(errors) >= 1

        # Non-ascending below values
        errors = scaler.validate(
            {
                "thresholds": [
                    {"below": 200, "score": 0.3},
                    {"below": 100, "score": 0.5},
                ]
            }
        )
        assert len(errors) >= 1


class TestInverseScaling:
    """Tests for inverse (1/x) scaling function."""

    def test_basic_scaling(self):
        scaler = InverseScaling()
        config = {"base": 5}

        # At value=0, score=1
        assert scaler.scale(0, config) == 1.0

        # At value=base, score=0.5
        assert scaler.scale(5, config) == 0.5

        # As value increases, score approaches 0
        assert scaler.scale(100, config) < 0.1

    def test_min_score(self):
        scaler = InverseScaling()
        config = {"base": 5, "min_score": 0.2}

        # Score should never go below min_score
        score = scaler.scale(1000, config)
        assert score >= 0.2

    def test_validation(self):
        scaler = InverseScaling()

        errors = scaler.validate({"base": 5})
        assert errors == []

        errors = scaler.validate({"base": -1})
        assert len(errors) == 1

        errors = scaler.validate({"min_score": 1.5})
        assert len(errors) == 1


class TestScaleValueFunction:
    """Tests for the scale_value convenience function."""

    def test_string_type(self):
        # Basic usage with string type
        score = scale_value(500, "linear", {"min": 0, "max": 1000})
        assert score == 0.5

    def test_dict_type(self):
        # Dict with provider key
        score = scale_value(
            500,
            {"provider": "linear", "min": 0, "max": 1000},
        )
        assert score == 0.5

    def test_unknown_provider(self):
        # Unknown provider should fallback to linear
        score = scale_value(50, "unknown_provider", {"min": 0, "max": 100})
        assert score == 0.5

    def test_merged_config(self):
        # Config from both scale_type dict and config param
        score = scale_value(
            500,
            {"provider": "linear", "min": 0},
            {"max": 1000},
        )
        assert score == 0.5
