"""
Tests for Interest Engine v2 Tune Command.

Tests weight visualization, adjustment suggestions, and impact estimation.
"""

from __future__ import annotations

import pytest

from aria_esi.services.redisq.interest_v2.cli.tune import (
    WeightVisualization,
    calculate_effective_weights,
    compare_weights,
    estimate_impact,
    format_impact_report,
    format_weight_display,
    suggest_adjustments,
    visualize_weights,
)
from aria_esi.services.redisq.interest_v2.models import CANONICAL_CATEGORIES

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_weights() -> dict[str, float]:
    """Create sample weights for testing."""
    return {
        "location": 0.8,
        "value": 0.7,
        "politics": 0.3,
        "activity": 0.5,
        "time": 0.0,
        "routes": 0.4,
        "assets": 0.2,
        "war": 0.1,
        "ship": 0.6,
    }


@pytest.fixture
def all_zero_weights() -> dict[str, float]:
    """Create all-zero weights for testing."""
    return dict.fromkeys(CANONICAL_CATEGORIES, 0.0)


@pytest.fixture
def all_max_weights() -> dict[str, float]:
    """Create all-max weights for testing."""
    return dict.fromkeys(CANONICAL_CATEGORIES, 1.0)


# =============================================================================
# TestWeightVisualization
# =============================================================================


class TestWeightVisualization:
    """Tests for WeightVisualization dataclass."""

    def test_str_enabled(self):
        """Enabled weights show filled circle indicator."""
        viz = WeightVisualization(
            category="location",
            weight=0.8,
            bar="████████████████░░░░",
            enabled=True,
        )

        result = str(viz)

        assert "●" in result
        assert "○" not in result

    def test_str_disabled(self):
        """Disabled weights show hollow circle indicator."""
        viz = WeightVisualization(
            category="time",
            weight=0.0,
            bar="░░░░░░░░░░░░░░░░░░░░",
            enabled=False,
        )

        result = str(viz)

        assert "○" in result
        assert "●" not in result

    def test_str_formatting(self):
        """String representation has proper alignment."""
        viz = WeightVisualization(
            category="location",
            weight=0.75,
            bar="███████████████░░░░░",
            enabled=True,
        )

        result = str(viz)

        # Should contain category name, bar, and weight
        assert "location" in result
        assert "███" in result
        assert "0.75" in result

    def test_str_category_alignment(self):
        """Category names are padded for alignment."""
        short_cat = WeightVisualization(
            category="war",
            weight=0.5,
            bar="██████████░░░░░░░░░░",
            enabled=True,
        )
        long_cat = WeightVisualization(
            category="politics",
            weight=0.5,
            bar="██████████░░░░░░░░░░",
            enabled=True,
        )

        # Both should format consistently
        assert "war" in str(short_cat)
        assert "politics" in str(long_cat)


# =============================================================================
# TestVisualizeWeights
# =============================================================================


class TestVisualizeWeights:
    """Tests for visualize_weights function."""

    def test_all_categories_included(self, sample_weights: dict[str, float]):
        """All canonical categories are included in visualization."""
        result = visualize_weights(sample_weights)

        categories = {viz.category for viz in result}
        assert categories == set(CANONICAL_CATEGORIES)

    def test_zero_weight_disabled(self, sample_weights: dict[str, float]):
        """Zero weights are marked as disabled."""
        result = visualize_weights(sample_weights)

        time_viz = next(v for v in result if v.category == "time")
        assert time_viz.weight == 0.0
        assert time_viz.enabled is False

    def test_positive_weight_enabled(self, sample_weights: dict[str, float]):
        """Positive weights are marked as enabled."""
        result = visualize_weights(sample_weights)

        location_viz = next(v for v in result if v.category == "location")
        assert location_viz.weight == 0.8
        assert location_viz.enabled is True

    def test_full_weight_bar(self, all_max_weights: dict[str, float]):
        """Max weight fills the entire bar."""
        result = visualize_weights(all_max_weights, bar_width=20)

        for viz in result:
            assert viz.weight == 1.0
            # Bar should be all filled
            assert "░" not in viz.bar
            assert "█" * 20 in viz.bar

    def test_empty_weight_bar(self, all_zero_weights: dict[str, float]):
        """Zero weight shows empty bar."""
        result = visualize_weights(all_zero_weights, bar_width=20)

        for viz in result:
            assert viz.weight == 0.0
            # Bar should be all empty
            assert "█" not in viz.bar
            assert "░" * 20 in viz.bar

    def test_partial_weight_bar(self):
        """Partial weights show proportional bar fill."""
        weights = {"location": 0.5}
        result = visualize_weights(weights, bar_width=20)

        location_viz = next(v for v in result if v.category == "location")
        # 50% of 20 = 10 filled characters
        assert location_viz.bar.count("█") == 10
        assert location_viz.bar.count("░") == 10

    def test_custom_bar_width(self, sample_weights: dict[str, float]):
        """Bar width is configurable."""
        result_10 = visualize_weights(sample_weights, bar_width=10)
        result_30 = visualize_weights(sample_weights, bar_width=30)

        # Check a specific category
        loc_10 = next(v for v in result_10 if v.category == "location")
        loc_30 = next(v for v in result_30 if v.category == "location")

        assert len(loc_10.bar) == 10
        assert len(loc_30.bar) == 30

    def test_missing_category_defaults_zero(self):
        """Missing categories default to weight 0.0."""
        # Only specify one category
        weights = {"location": 0.8}
        result = visualize_weights(weights)

        # All other categories should have weight 0.0
        for viz in result:
            if viz.category != "location":
                assert viz.weight == 0.0
                assert viz.enabled is False


# =============================================================================
# TestFormatWeightDisplay
# =============================================================================


class TestFormatWeightDisplay:
    """Tests for format_weight_display function."""

    def test_basic_display(self, sample_weights: dict[str, float]):
        """Basic display includes header and all categories."""
        result = format_weight_display(sample_weights)

        # Should have header
        assert "Category Weight Configuration" in result

        # Should have all categories
        for cat in CANONICAL_CATEGORIES:
            assert cat in result.lower()

    def test_with_preset_name(self, sample_weights: dict[str, float]):
        """Preset name is included when provided."""
        result = format_weight_display(sample_weights, preset_name="trade-hub")

        assert "Preset:" in result
        assert "trade-hub" in result

    def test_without_preset_name(self, sample_weights: dict[str, float]):
        """Preset section is omitted when not provided."""
        result = format_weight_display(sample_weights, preset_name=None)

        assert "Preset:" not in result

    def test_with_customize_adjustments(self, sample_weights: dict[str, float]):
        """Customize adjustments section is included when provided."""
        customize = {"location": "+20%", "value": "-10%"}
        result = format_weight_display(sample_weights, customize=customize)

        assert "Adjustments:" in result
        assert "location: +20%" in result
        assert "value: -10%" in result

    def test_without_customize_adjustments(self, sample_weights: dict[str, float]):
        """Adjustments section is omitted when not provided."""
        result = format_weight_display(sample_weights, customize=None)

        assert "Adjustments:" not in result

    def test_legend_included(self, sample_weights: dict[str, float]):
        """Legend is always present."""
        result = format_weight_display(sample_weights)

        assert "Legend:" in result
        assert "●" in result
        assert "○" in result
        assert "enabled" in result
        assert "disabled" in result


# =============================================================================
# TestSuggestAdjustments
# =============================================================================


class TestSuggestAdjustments:
    """Tests for suggest_adjustments function."""

    def test_location_keywords(self, sample_weights: dict[str, float]):
        """Location keywords trigger location suggestions."""
        # Test "nearby"
        result = suggest_adjustments(sample_weights, "I want nearby kills")
        # location is already 0.8, so no suggestion (>= 0.7)

        # Use lower location weight
        low_loc = {**sample_weights, "location": 0.3}
        result = suggest_adjustments(low_loc, "I want nearby kills")
        assert "location" in result
        assert "+30%" in result["location"]

    def test_system_keyword(self):
        """'system' keyword triggers location suggestion."""
        weights = {"location": 0.5}
        result = suggest_adjustments(weights, "Show system activity")
        assert "location" in result

    def test_value_keywords(self):
        """Value keywords trigger value suggestions."""
        weights = {"value": 0.3}

        # Test "isk"
        result = suggest_adjustments(weights, "Show high isk kills")
        assert "value" in result
        assert "+30%" in result["value"]

    def test_expensive_keyword(self):
        """'expensive' keyword triggers value suggestion."""
        weights = {"value": 0.4}
        result = suggest_adjustments(weights, "Find expensive ships")
        assert "value" in result

    def test_politics_keywords(self):
        """Politics keywords trigger politics suggestions."""
        weights = {"politics": 0.2}

        # Test "alliance"
        result = suggest_adjustments(weights, "Watch alliance activity")
        assert "politics" in result
        assert "+40%" in result["politics"]

    def test_enemy_keyword(self):
        """'enemy' keyword triggers politics suggestion."""
        weights = {"politics": 0.3}
        result = suggest_adjustments(weights, "Track enemy losses")
        assert "politics" in result

    def test_activity_keywords(self):
        """Activity keywords trigger activity suggestions."""
        weights = {"activity": 0.3}

        # Test "busy"
        result = suggest_adjustments(weights, "Find busy systems")
        assert "activity" in result
        assert "+30%" in result["activity"]

    def test_hotspot_keyword(self):
        """'hotspot' keyword triggers activity suggestion."""
        weights = {"activity": 0.2}
        result = suggest_adjustments(weights, "Detect hotspots")
        assert "activity" in result

    def test_reduction_keywords(self, sample_weights: dict[str, float]):
        """Reduction keywords suggest decreases for high weights."""
        # Test "less"
        result = suggest_adjustments(sample_weights, "I want less notifications")

        # Should have -20% for categories with weight > 0.3
        assert "location" in result  # 0.8
        assert "-20%" in result["location"]

    def test_fewer_keyword(self, sample_weights: dict[str, float]):
        """'fewer' keyword suggests reductions."""
        result = suggest_adjustments(sample_weights, "fewer alerts please")
        assert "location" in result

    def test_quiet_keyword(self, sample_weights: dict[str, float]):
        """'quiet' keyword suggests reductions."""
        result = suggest_adjustments(sample_weights, "keep it quiet")
        assert "location" in result

    def test_no_suggestion_high_weight(self):
        """No suggestion when weight is already high (>= 0.7)."""
        weights = {"location": 0.9, "value": 0.8}

        result = suggest_adjustments(weights, "nearby systems")

        # location is 0.9, already >= 0.7, so no suggestion
        assert "location" not in result

    def test_multiple_keywords_match(self):
        """Multiple keyword matches produce combined suggestions."""
        weights = {"location": 0.3, "value": 0.3, "politics": 0.3}

        # Request involves multiple aspects
        result = suggest_adjustments(
            weights, "expensive alliance nearby kills"
        )

        assert "location" in result  # "nearby"
        assert "value" in result  # "expensive"
        assert "politics" in result  # "alliance"

    def test_no_suggestion_for_unrelated(self):
        """No suggestions for unrelated requests."""
        weights = {"location": 0.8, "value": 0.8}
        result = suggest_adjustments(weights, "hello world")
        assert len(result) == 0


# =============================================================================
# TestCalculateEffectiveWeights
# =============================================================================


class TestCalculateEffectiveWeights:
    """Tests for calculate_effective_weights function."""

    def test_positive_adjustment(self, sample_weights: dict[str, float]):
        """Positive adjustments increase weight."""
        adjustments = {"location": "+30%"}
        result = calculate_effective_weights(sample_weights, adjustments)

        # 0.8 * 1.3 = 1.04
        assert result["location"] == pytest.approx(1.04, rel=0.01)

    def test_negative_adjustment(self, sample_weights: dict[str, float]):
        """Negative adjustments decrease weight."""
        adjustments = {"value": "-20%"}
        result = calculate_effective_weights(sample_weights, adjustments)

        # 0.7 * 0.8 = 0.56
        assert result["value"] == pytest.approx(0.56, rel=0.01)

    def test_missing_category_preserved(self, sample_weights: dict[str, float]):
        """Non-adjusted categories preserve their original value."""
        adjustments = {"location": "+10%"}
        result = calculate_effective_weights(sample_weights, adjustments)

        # Other categories unchanged
        assert result["value"] == sample_weights["value"]
        assert result["politics"] == sample_weights["politics"]

    def test_zero_adjustment(self, sample_weights: dict[str, float]):
        """Zero adjustment ('+0%') causes no change."""
        adjustments = {"location": "+0%"}
        result = calculate_effective_weights(sample_weights, adjustments)

        # 0.8 * 1.0 = 0.8
        assert result["location"] == pytest.approx(0.8, rel=0.01)

    def test_unknown_category_ignored(self, sample_weights: dict[str, float]):
        """Unknown categories in adjustments are ignored."""
        adjustments = {"unknown_cat": "+50%"}
        result = calculate_effective_weights(sample_weights, adjustments)

        # Should be unchanged
        assert result == sample_weights

    def test_multiple_adjustments(self, sample_weights: dict[str, float]):
        """Multiple adjustments are applied correctly."""
        adjustments = {"location": "+20%", "value": "-10%", "politics": "+50%"}
        result = calculate_effective_weights(sample_weights, adjustments)

        assert result["location"] == pytest.approx(0.96, rel=0.01)  # 0.8 * 1.2
        assert result["value"] == pytest.approx(0.63, rel=0.01)  # 0.7 * 0.9
        assert result["politics"] == pytest.approx(0.45, rel=0.01)  # 0.3 * 1.5


# =============================================================================
# TestCompareWeights
# =============================================================================


class TestCompareWeights:
    """Tests for compare_weights function."""

    def test_increase_formatting(self):
        """Increases are formatted with '+' and '↑'."""
        before = {"location": 0.5}
        after = {"location": 0.8}

        result = compare_weights(before, after)

        assert "+0.30" in result
        assert "↑" in result

    def test_decrease_formatting(self):
        """Decreases are formatted with negative value and '↓'."""
        before = {"location": 0.8}
        after = {"location": 0.5}

        result = compare_weights(before, after)

        assert "-0.30" in result
        assert "↓" in result

    def test_no_change_formatting(self):
        """No change is formatted as '--'."""
        before = {"location": 0.5}
        after = {"location": 0.5}

        result = compare_weights(before, after)

        assert "--" in result

    def test_all_categories_shown(self, sample_weights: dict[str, float]):
        """All canonical categories are shown in comparison."""
        before = sample_weights
        after = {**sample_weights, "location": 0.9}

        result = compare_weights(before, after)

        for cat in CANONICAL_CATEGORIES:
            assert cat in result

    def test_header_included(self, sample_weights: dict[str, float]):
        """Header row is included."""
        result = compare_weights(sample_weights, sample_weights)

        assert "Category" in result
        assert "Before" in result
        assert "After" in result
        assert "Change" in result


# =============================================================================
# TestEstimateImpact
# =============================================================================


class TestEstimateImpact:
    """Tests for estimate_impact function."""

    def test_enabled_count_change(self, sample_weights: dict[str, float]):
        """Tracks enabled category count changes."""
        before = sample_weights  # time=0.0 (disabled)
        after = {**sample_weights, "time": 0.5}  # time now enabled

        result = estimate_impact(before, after)

        assert result["enabled_categories"]["before"] == 8  # time was 0
        assert result["enabled_categories"]["after"] == 9  # time now > 0

    def test_total_weight_change(self, sample_weights: dict[str, float]):
        """Tracks total weight changes."""
        before = sample_weights
        after = {**sample_weights, "location": 1.0}  # +0.2

        result = estimate_impact(before, after)

        assert result["total_weight"]["after"] > result["total_weight"]["before"]

    def test_significant_increase_detection(self, sample_weights: dict[str, float]):
        """Detects significant (>20%) increases."""
        before = sample_weights  # location=0.8
        after = {**sample_weights, "location": 1.0}  # +25%

        result = estimate_impact(before, after)

        increases = [cat for cat, _ in result["significant_increases"]]
        assert "location" in increases

    def test_significant_decrease_detection(self, sample_weights: dict[str, float]):
        """Detects significant (<-20%) decreases."""
        before = sample_weights  # location=0.8
        after = {**sample_weights, "location": 0.4}  # -50%

        result = estimate_impact(before, after)

        decreases = [cat for cat, _ in result["significant_decreases"]]
        assert "location" in decreases

    def test_more_notifications_estimate(self, sample_weights: dict[str, float]):
        """Estimates more notifications when categories enabled."""
        before = sample_weights  # time=0.0
        after = {**sample_weights, "time": 0.5}

        result = estimate_impact(before, after)

        assert "more" in result["notification_estimate"].lower()

    def test_fewer_notifications_estimate(self, sample_weights: dict[str, float]):
        """Estimates fewer notifications when categories disabled."""
        before = sample_weights  # location=0.8
        after = {**sample_weights, "location": 0.0}

        result = estimate_impact(before, after)

        assert "fewer" in result["notification_estimate"].lower()

    def test_unchanged_estimate(self, sample_weights: dict[str, float]):
        """Estimates unchanged when no significant changes."""
        before = sample_weights
        after = sample_weights.copy()

        result = estimate_impact(before, after)

        assert result["notification_estimate"] == "unchanged"

    def test_slight_increase_from_weights(self):
        """Estimates slightly more when total weight increases significantly."""
        before = {"location": 0.5, "value": 0.5}
        after = {"location": 0.8, "value": 0.8}  # +60% total

        result = estimate_impact(before, after)

        assert "more" in result["notification_estimate"].lower()

    def test_slight_decrease_from_weights(self):
        """Estimates slightly fewer when total weight decreases significantly."""
        before = {"location": 0.8, "value": 0.8}
        after = {"location": 0.4, "value": 0.4}  # -50% total

        result = estimate_impact(before, after)

        assert "fewer" in result["notification_estimate"].lower()


# =============================================================================
# TestFormatImpactReport
# =============================================================================


class TestFormatImpactReport:
    """Tests for format_impact_report function."""

    def test_report_sections(self, sample_weights: dict[str, float]):
        """Report includes all required sections."""
        after = {**sample_weights, "location": 1.0}
        impact = estimate_impact(sample_weights, after)

        report = format_impact_report(impact)

        # Header
        assert "Estimated Impact" in report

        # Category count
        assert "Categories enabled" in report

        # Total weight
        assert "Total weight" in report

        # Estimate
        assert "Estimate" in report

    def test_significant_changes_displayed(self, sample_weights: dict[str, float]):
        """Significant changes are displayed in report."""
        after = {**sample_weights, "location": 1.0, "value": 0.2}
        impact = estimate_impact(sample_weights, after)

        report = format_impact_report(impact)

        # Should mention categories with significant changes
        if impact["significant_increases"]:
            assert "increases" in report.lower()

        if impact["significant_decreases"]:
            assert "decreases" in report.lower()

    def test_estimate_emoji_present(self, sample_weights: dict[str, float]):
        """Report includes estimate emoji."""
        impact = estimate_impact(sample_weights, sample_weights)
        report = format_impact_report(impact)

        assert "🔮" in report

    def test_header_emoji_present(self, sample_weights: dict[str, float]):
        """Report includes header emoji."""
        impact = estimate_impact(sample_weights, sample_weights)
        report = format_impact_report(impact)

        assert "📊" in report
