"""
Tuning Tool for Interest Engine v2.

Provides visualization and adjustment of category weights
for interactive profile tuning.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..models import CANONICAL_CATEGORIES


@dataclass
class WeightVisualization:
    """Visual representation of category weights."""

    category: str
    weight: float
    bar: str
    enabled: bool

    def __str__(self) -> str:
        status = "●" if self.enabled else "○"
        return f"{status} {self.category:12} {self.bar} {self.weight:.2f}"


def visualize_weights(
    weights: dict[str, float],
    bar_width: int = 20,
) -> list[WeightVisualization]:
    """
    Create visual representation of weights.

    Args:
        weights: Dict of category -> weight
        bar_width: Width of visual bar

    Returns:
        List of WeightVisualization for each category
    """
    result = []

    for category in CANONICAL_CATEGORIES:
        weight = weights.get(category, 0.0)
        enabled = weight > 0

        # Create bar
        filled = int(weight * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)

        result.append(
            WeightVisualization(
                category=category,
                weight=weight,
                bar=bar,
                enabled=enabled,
            )
        )

    return result


def format_weight_display(
    weights: dict[str, float],
    preset_name: str | None = None,
    customize: dict[str, str] | None = None,
) -> str:
    """
    Format weights for terminal display.

    Args:
        weights: Current effective weights
        preset_name: Optional preset being used
        customize: Optional customize adjustments

    Returns:
        Formatted string for display
    """
    lines = []

    # Header
    lines.append("╔═══════════════════════════════════════════════╗")
    lines.append("║           Category Weight Configuration        ║")
    lines.append("╚═══════════════════════════════════════════════╝")
    lines.append("")

    if preset_name:
        lines.append(f"  Preset: {preset_name}")
        lines.append("")

    # Weight bars
    lines.append("  Category      Weight                    Value")
    lines.append("  ─────────────────────────────────────────────")

    visualizations = visualize_weights(weights)
    for viz in visualizations:
        lines.append(f"  {viz}")

    lines.append("")

    # Customize adjustments if present
    if customize:
        lines.append("  Adjustments:")
        for cat, adj in customize.items():
            lines.append(f"    {cat}: {adj}")
        lines.append("")

    # Legend
    lines.append("  Legend:")
    lines.append("    ● = enabled (weight > 0)")
    lines.append("    ○ = disabled (weight = 0)")
    lines.append("")

    return "\n".join(lines)


def suggest_adjustments(
    current_weights: dict[str, float],
    target_behavior: str,
) -> dict[str, str]:
    """
    Suggest weight adjustments for a target behavior.

    Args:
        current_weights: Current weight configuration
        target_behavior: Desired behavior description

    Returns:
        Dict of category -> adjustment (e.g., "+20%", "-10%")
    """
    suggestions: dict[str, str] = {}

    target_lower = target_behavior.lower()

    # More location focus
    if "location" in target_lower or "system" in target_lower or "nearby" in target_lower:
        if current_weights.get("location", 0) < 0.7:
            suggestions["location"] = "+30%"

    # More value focus
    if "value" in target_lower or "isk" in target_lower or "expensive" in target_lower:
        if current_weights.get("value", 0) < 0.7:
            suggestions["value"] = "+30%"

    # More politics focus
    if "politic" in target_lower or "alliance" in target_lower or "enemy" in target_lower:
        if current_weights.get("politics", 0) < 0.7:
            suggestions["politics"] = "+40%"

    # More activity focus
    if "active" in target_lower or "busy" in target_lower or "hotspot" in target_lower:
        if current_weights.get("activity", 0) < 0.6:
            suggestions["activity"] = "+30%"

    # Less noise
    if "less" in target_lower or "fewer" in target_lower or "quiet" in target_lower:
        for cat in CANONICAL_CATEGORIES:
            if current_weights.get(cat, 0) > 0.3:
                suggestions[cat] = "-20%"

    return suggestions


def calculate_effective_weights(
    base_weights: dict[str, float],
    adjustments: dict[str, str],
) -> dict[str, float]:
    """
    Apply adjustments to base weights.

    Args:
        base_weights: Starting weights
        adjustments: Dict of category -> adjustment string

    Returns:
        New effective weights
    """
    from ..config import parse_customize_adjustment

    result = dict(base_weights)

    for category, adjustment in adjustments.items():
        if category in result:
            multiplier = parse_customize_adjustment(adjustment)
            result[category] = result[category] * multiplier

    return result


def compare_weights(
    before: dict[str, float],
    after: dict[str, float],
) -> str:
    """
    Format comparison of two weight configurations.

    Args:
        before: Original weights
        after: New weights

    Returns:
        Formatted comparison string
    """
    lines = []

    lines.append("  Category      Before    After     Change")
    lines.append("  ─────────────────────────────────────────")

    for category in CANONICAL_CATEGORIES:
        w_before = before.get(category, 0.0)
        w_after = after.get(category, 0.0)
        change = w_after - w_before

        if change > 0:
            change_str = f"+{change:.2f} ↑"
        elif change < 0:
            change_str = f"{change:.2f} ↓"
        else:
            change_str = "  --"

        lines.append(f"  {category:12} {w_before:6.2f}    {w_after:6.2f}    {change_str}")

    return "\n".join(lines)


def estimate_impact(
    before_weights: dict[str, float],
    after_weights: dict[str, float],
) -> dict[str, Any]:
    """
    Estimate impact of weight changes on notifications.

    Args:
        before_weights: Original weights
        after_weights: New weights

    Returns:
        Dict with estimated impact metrics
    """
    # Calculate total weight change
    total_before = sum(before_weights.values())
    total_after = sum(after_weights.values())

    # Categories enabled/disabled
    enabled_before = sum(1 for w in before_weights.values() if w > 0)
    enabled_after = sum(1 for w in after_weights.values() if w > 0)

    # Identify significant changes
    significant_increases = []
    significant_decreases = []

    for cat in CANONICAL_CATEGORIES:
        w_before = before_weights.get(cat, 0.0)
        w_after = after_weights.get(cat, 0.0)

        if w_before > 0:
            pct_change = (w_after - w_before) / w_before * 100
        elif w_after > 0:
            pct_change = 100
        else:
            pct_change = 0

        if pct_change > 20:
            significant_increases.append((cat, pct_change))
        elif pct_change < -20:
            significant_decreases.append((cat, pct_change))

    # Estimate notification change
    # More categories enabled = potentially more notifications
    # Higher weights = more sensitive to that category
    notification_estimate = "unchanged"
    if enabled_after > enabled_before:
        notification_estimate = "likely more notifications"
    elif enabled_after < enabled_before:
        notification_estimate = "likely fewer notifications"
    elif total_after > total_before * 1.2:
        notification_estimate = "slightly more notifications"
    elif total_after < total_before * 0.8:
        notification_estimate = "slightly fewer notifications"

    return {
        "enabled_categories": {
            "before": enabled_before,
            "after": enabled_after,
        },
        "total_weight": {
            "before": round(total_before, 2),
            "after": round(total_after, 2),
        },
        "significant_increases": significant_increases,
        "significant_decreases": significant_decreases,
        "notification_estimate": notification_estimate,
    }


def format_impact_report(impact: dict[str, Any]) -> str:
    """
    Format impact estimate as readable report.

    Args:
        impact: Impact estimate from estimate_impact()

    Returns:
        Formatted report string
    """
    lines = []

    lines.append("📊 Estimated Impact")
    lines.append("─" * 40)

    # Category count
    enabled = impact["enabled_categories"]
    lines.append(f"  Categories enabled: {enabled['before']} → {enabled['after']}")

    # Total weight
    total = impact["total_weight"]
    lines.append(f"  Total weight: {total['before']} → {total['after']}")
    lines.append("")

    # Significant changes
    if impact["significant_increases"]:
        lines.append("  Significant increases:")
        for cat, pct in impact["significant_increases"]:
            lines.append(f"    {cat}: +{pct:.0f}%")

    if impact["significant_decreases"]:
        lines.append("  Significant decreases:")
        for cat, pct in impact["significant_decreases"]:
            lines.append(f"    {cat}: {pct:.0f}%")

    lines.append("")
    lines.append(f"  🔮 Estimate: {impact['notification_estimate']}")

    return "\n".join(lines)
