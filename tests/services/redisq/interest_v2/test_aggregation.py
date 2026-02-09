"""Tests for Interest Engine v2 Aggregation functions.

CRITICAL TEST AREA: RMS vs Linear aggregation, signal dilution prevention.
"""

import math

import pytest

from aria_esi.services.redisq.interest_v2.aggregation import (
    aggregate_linear,
    aggregate_max,
    aggregate_rms,
    aggregate_scores,
    calculate_prefetch_bounds,
    compare_aggregation_modes,
)
from aria_esi.services.redisq.interest_v2.models import (
    AggregationMode,
    CategoryScore,
    SignalScore,
)


class TestAggregateRMS:
    """Tests for RMS (Root Mean Square) aggregation."""

    def test_single_category_full_score(self):
        """Single category at 1.0 returns 1.0."""
        scores = [
            CategoryScore(category="location", score=1.0, weight=1.0, match=True)
        ]
        result = aggregate_rms(scores)
        assert result == 1.0

    def test_single_category_zero_score(self):
        """Single category at 0.0 returns 0.0."""
        scores = [
            CategoryScore(category="location", score=0.0, weight=1.0, match=False)
        ]
        result = aggregate_rms(scores)
        assert result == 0.0

    def test_two_categories_equal_weights(self):
        """Two categories: sqrt((1*1^2 + 1*0^2) / 2) = 0.707..."""
        scores = [
            CategoryScore(category="location", score=1.0, weight=1.0, match=True),
            CategoryScore(category="politics", score=0.0, weight=1.0, match=False),
        ]
        result = aggregate_rms(scores)
        expected = math.sqrt(0.5)  # ~0.707
        assert abs(result - expected) < 0.001

    def test_rms_prevents_signal_dilution(self):
        """
        CRITICAL: RMS prevents strong signals from being diluted by neutral ones.

        With linear avg: (1.0 + 0.0) / 2 = 0.5
        With RMS: sqrt((1.0^2 + 0.0^2) / 2) = 0.707

        The strong location signal is preserved better with RMS.
        """
        scores = [
            CategoryScore(category="location", score=1.0, weight=1.0, match=True),
            CategoryScore(category="politics", score=0.0, weight=1.0, match=False),
        ]

        rms_result = aggregate_rms(scores)
        linear_result = aggregate_linear(scores)

        # RMS should be higher than linear (0.707 vs 0.5)
        assert rms_result > linear_result
        assert rms_result > 0.6  # RMS preserves strong signal
        assert linear_result == 0.5  # Linear dilutes to 0.5

    def test_weighted_rms(self):
        """RMS with different weights."""
        scores = [
            CategoryScore(category="location", score=1.0, weight=2.0, match=True),
            CategoryScore(category="politics", score=0.0, weight=1.0, match=False),
        ]
        # sqrt((2*1^2 + 1*0^2) / (2+1)) = sqrt(2/3) ≈ 0.816
        result = aggregate_rms(scores)
        expected = math.sqrt(2 / 3)
        assert abs(result - expected) < 0.001

    def test_all_high_scores(self):
        """All high scores should aggregate close to 1.0."""
        scores = [
            CategoryScore(category="location", score=0.9, weight=1.0, match=True),
            CategoryScore(category="value", score=0.8, weight=1.0, match=True),
            CategoryScore(category="politics", score=0.85, weight=1.0, match=True),
        ]
        result = aggregate_rms(scores)
        # sqrt((0.9^2 + 0.8^2 + 0.85^2) / 3) ≈ 0.85
        assert result > 0.8
        assert result < 0.95

    def test_empty_scores_returns_zero(self):
        """Empty input returns 0.0."""
        result = aggregate_rms([])
        assert result == 0.0

    def test_zero_total_weight_returns_zero(self):
        """Zero total weight returns 0.0."""
        scores = [
            CategoryScore(category="location", score=1.0, weight=0.0, match=True),
        ]
        result = aggregate_rms(scores)
        assert result == 0.0

    def test_penalty_factor_applied(self):
        """Penalty factor is applied in penalized_score."""
        scores = [
            CategoryScore(category="location", score=1.0, weight=1.0, match=True, penalty_factor=0.5),
        ]
        result = aggregate_rms(scores)
        # 0.5 penalized score
        assert result == 0.5

    def test_result_clamped_to_one(self):
        """Result is clamped to [0, 1]."""
        # This shouldn't happen naturally but test the clamp
        scores = [
            CategoryScore(category="location", score=1.0, weight=1.0, match=True),
        ]
        result = aggregate_rms(scores)
        assert 0.0 <= result <= 1.0


class TestAggregateLinear:
    """Tests for linear weighted average aggregation."""

    def test_single_category(self):
        """Single category returns its score."""
        scores = [
            CategoryScore(category="location", score=0.8, weight=1.0, match=True),
        ]
        result = aggregate_linear(scores)
        assert result == 0.8

    def test_equal_weights(self):
        """Equal weights produce simple average."""
        scores = [
            CategoryScore(category="location", score=1.0, weight=1.0, match=True),
            CategoryScore(category="politics", score=0.0, weight=1.0, match=False),
        ]
        result = aggregate_linear(scores)
        assert result == 0.5

    def test_weighted_average(self):
        """Weighted average calculation."""
        scores = [
            CategoryScore(category="location", score=1.0, weight=3.0, match=True),
            CategoryScore(category="politics", score=0.0, weight=1.0, match=False),
        ]
        # (3*1.0 + 1*0.0) / (3+1) = 0.75
        result = aggregate_linear(scores)
        assert result == 0.75

    def test_empty_scores_returns_zero(self):
        """Empty input returns 0.0."""
        result = aggregate_linear([])
        assert result == 0.0


class TestAggregateMax:
    """Tests for max aggregation (legacy mode)."""

    def test_returns_max_score(self):
        """Returns the maximum score."""
        scores = [
            CategoryScore(category="location", score=0.8, weight=1.0, match=True),
            CategoryScore(category="value", score=0.6, weight=1.0, match=True),
            CategoryScore(category="politics", score=0.9, weight=1.0, match=True),
        ]
        result = aggregate_max(scores)
        assert result == 0.9

    def test_ignores_weights(self):
        """Max ignores weights."""
        scores = [
            CategoryScore(category="location", score=0.5, weight=10.0, match=True),
            CategoryScore(category="value", score=0.9, weight=0.1, match=True),
        ]
        result = aggregate_max(scores)
        assert result == 0.9

    def test_empty_scores_returns_zero(self):
        """Empty input returns 0.0."""
        result = aggregate_max([])
        assert result == 0.0

    def test_applies_penalty(self):
        """Penalty factor is applied."""
        scores = [
            CategoryScore(category="location", score=1.0, weight=1.0, match=True, penalty_factor=0.5),
            CategoryScore(category="value", score=0.4, weight=1.0, match=True),
        ]
        result = aggregate_max(scores)
        # penalized_score of location is 0.5, value is 0.4
        assert result == 0.5


def _make_configured_category(category: str, score: float, weight: float, match: bool) -> CategoryScore:
    """Helper to create a properly configured CategoryScore with signals."""
    cat = CategoryScore(category=category, score=score, weight=weight, match=match)
    # Add a dummy signal so is_configured returns True
    cat.signals = {"test": SignalScore(signal="test", score=score, prefetch_capable=True)}
    return cat


class TestAggregateScores:
    """Tests for the main aggregate_scores dispatch function."""

    def test_default_mode_is_weighted(self):
        """Default mode uses RMS (weighted) aggregation."""
        scores = {
            "location": _make_configured_category("location", 1.0, 1.0, True),
            "politics": _make_configured_category("politics", 0.0, 1.0, False),
        }
        result = aggregate_scores(scores)
        # RMS result
        assert abs(result - math.sqrt(0.5)) < 0.001

    def test_linear_mode(self):
        """Linear mode uses linear aggregation."""
        scores = {
            "location": _make_configured_category("location", 1.0, 1.0, True),
            "politics": _make_configured_category("politics", 0.0, 1.0, False),
        }
        result = aggregate_scores(scores, mode=AggregationMode.LINEAR)
        assert result == 0.5

    def test_max_mode(self):
        """Max mode uses max aggregation."""
        scores = {
            "location": _make_configured_category("location", 0.8, 1.0, True),
            "politics": _make_configured_category("politics", 0.6, 1.0, True),
        }
        result = aggregate_scores(scores, mode=AggregationMode.MAX)
        assert result == 0.8

    def test_filters_unconfigured_categories(self):
        """Only aggregates configured (has signals) and enabled (weight > 0) categories."""
        loc = _make_configured_category("location", 0.8, 1.0, True)
        # unconfigured has no signals
        unconfigured = CategoryScore(category="unconfigured", score=0.0, weight=0.0, match=False)
        scores = {
            "location": loc,
            "unconfigured": unconfigured,
        }
        # Only location is enabled (weight > 0) and configured (has signals)
        result = aggregate_scores(scores)
        assert result == 0.8


class TestCalculatePrefetchBounds:
    """Tests for prefetch bounds calculation."""

    def test_all_prefetch_capable(self):
        """All prefetch-capable categories use actual scores."""
        # Create category with prefetch-capable signal
        cat = CategoryScore(category="location", score=0.8, weight=1.0, match=True)
        cat.signals = {"geographic": SignalScore(signal="geographic", score=0.8, prefetch_capable=True)}

        category_scores = {"location": cat}
        weights = {"location": 1.0}

        prefetch_score, lower, upper = calculate_prefetch_bounds(category_scores, weights)
        assert prefetch_score == 0.8
        assert lower == 0.8
        assert upper == 0.8

    def test_mixed_prefetch_capability(self):
        """Mix of prefetch and post-fetch categories."""
        # Prefetch-capable category
        loc = CategoryScore(category="location", score=0.8, weight=1.0, match=True)
        loc.signals = {"geographic": SignalScore(signal="geographic", score=0.8, prefetch_capable=True)}

        # Post-fetch category (no signals marked as prefetch-capable)
        act = CategoryScore(category="activity", score=0.0, weight=1.0, match=False)
        # No signals configured

        category_scores = {"location": loc, "activity": act}
        weights = {"location": 1.0, "activity": 1.0}

        prefetch_score, lower, upper = calculate_prefetch_bounds(category_scores, weights)

        # Prefetch score only from known categories
        assert prefetch_score == 0.8
        # Lower bound: known / total = 0.8 / 2 = 0.4
        assert lower == 0.4
        # Upper bound: (known + unknown*1.0) / total = (0.8 + 1.0) / 2 = 0.9
        assert upper == 0.9

    def test_custom_unknown_assumption(self):
        """Custom unknown_assumption value."""
        loc = CategoryScore(category="location", score=0.6, weight=1.0, match=True)
        loc.signals = {"geographic": SignalScore(signal="geographic", score=0.6, prefetch_capable=True)}

        category_scores = {"location": loc}
        weights = {"location": 1.0, "activity": 1.0}  # activity not in scores

        prefetch_score, lower, upper = calculate_prefetch_bounds(
            category_scores, weights, unknown_assumption=0.5
        )

        # Upper bound uses 0.5 for unknown
        # (0.6 + 0.5) / 2 = 0.55
        assert upper == 0.55

    def test_no_prefetch_capable(self):
        """No prefetch-capable categories returns None for prefetch_score."""
        weights = {"activity": 1.0}  # Activity requires post-fetch
        category_scores = {}

        prefetch_score, lower, upper = calculate_prefetch_bounds(category_scores, weights)
        assert prefetch_score is None
        assert lower == 0.0
        assert upper == 1.0

    def test_disabled_categories_ignored(self):
        """Categories with weight <= 0 are ignored."""
        loc = CategoryScore(category="location", score=0.8, weight=1.0, match=True)
        loc.signals = {"geographic": SignalScore(signal="geographic", score=0.8, prefetch_capable=True)}

        category_scores = {"location": loc}
        weights = {"location": 1.0, "disabled": 0.0}  # disabled has weight 0

        prefetch_score, lower, upper = calculate_prefetch_bounds(category_scores, weights)
        # Only location counts
        assert prefetch_score == 0.8
        assert lower == 0.8
        assert upper == 0.8


class TestCompareAggregationModes:
    """Tests for mode comparison utility."""

    def test_compares_all_modes(self):
        """Returns scores for all aggregation modes."""
        scores = {
            "location": _make_configured_category("location", 1.0, 1.0, True),
            "politics": _make_configured_category("politics", 0.0, 1.0, False),
        }

        comparison = compare_aggregation_modes(scores)

        assert "rms" in comparison
        assert "linear" in comparison
        assert "max" in comparison

        # RMS should be highest for this case
        assert comparison["rms"] > comparison["linear"]
        assert abs(comparison["rms"] - math.sqrt(0.5)) < 0.001
        assert comparison["linear"] == 0.5
        assert comparison["max"] == 1.0


class TestSignalDilutionScenarios:
    """
    CRITICAL: Scenarios demonstrating RMS prevents signal dilution.

    These tests verify the core design goal of v2: strong signals
    should not be drowned out by neutral signals.
    """

    def test_single_strong_signal_not_diluted(self):
        """
        One strong location signal shouldn't be diluted by multiple zeros.

        Linear: 1.0 / 5 = 0.2 (heavily diluted)
        RMS: sqrt(1.0 / 5) = 0.447 (preserved better)
        """
        scores = [
            CategoryScore(category="location", score=1.0, weight=1.0, match=True),
            CategoryScore(category="value", score=0.0, weight=1.0, match=False),
            CategoryScore(category="politics", score=0.0, weight=1.0, match=False),
            CategoryScore(category="activity", score=0.0, weight=1.0, match=False),
            CategoryScore(category="routes", score=0.0, weight=1.0, match=False),
        ]

        rms = aggregate_rms(scores)
        linear = aggregate_linear(scores)

        assert rms > linear
        assert rms == pytest.approx(math.sqrt(0.2), abs=0.001)  # ~0.447
        assert linear == 0.2

    def test_two_strong_signals_preserve_strength(self):
        """Two strong signals should maintain high score."""
        scores = [
            CategoryScore(category="location", score=0.9, weight=1.0, match=True),
            CategoryScore(category="value", score=0.8, weight=1.0, match=True),
            CategoryScore(category="politics", score=0.0, weight=1.0, match=False),
        ]

        rms = aggregate_rms(scores)
        linear = aggregate_linear(scores)

        # RMS: sqrt((0.81 + 0.64 + 0) / 3) = sqrt(0.483) ≈ 0.695
        # Linear: (0.9 + 0.8 + 0) / 3 = 0.567

        assert rms > linear
        assert rms > 0.65  # Strong signals preserved
        assert linear < 0.60  # Linear dilutes more

    def test_weight_amplifies_strong_signal(self):
        """Higher weight on strong signal should increase RMS."""
        low_weight = [
            CategoryScore(category="location", score=1.0, weight=1.0, match=True),
            CategoryScore(category="politics", score=0.0, weight=1.0, match=False),
        ]

        high_weight = [
            CategoryScore(category="location", score=1.0, weight=3.0, match=True),
            CategoryScore(category="politics", score=0.0, weight=1.0, match=False),
        ]

        rms_low = aggregate_rms(low_weight)
        rms_high = aggregate_rms(high_weight)

        # Higher weight on strong signal should increase RMS
        assert rms_high > rms_low
        # sqrt(3*1 / 4) = 0.866 vs sqrt(1/2) = 0.707
        assert abs(rms_high - math.sqrt(0.75)) < 0.001
        assert abs(rms_low - math.sqrt(0.5)) < 0.001
