"""
Score Aggregation for Interest Engine v2.

Implements RMS, linear, and max aggregation modes for blending category scores.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from .models import AggregationMode, CategoryScore

if TYPE_CHECKING:
    pass


def aggregate_scores(
    category_scores: dict[str, CategoryScore],
    mode: AggregationMode = AggregationMode.WEIGHTED,
) -> float:
    """
    Aggregate category scores into a final interest score.

    Args:
        category_scores: Dict of category name -> CategoryScore
        mode: Aggregation mode (weighted/RMS, linear, max)

    Returns:
        Final interest score in [0, 1]
    """
    # Filter to configured and enabled categories
    active_scores = [c for c in category_scores.values() if c.is_configured and c.is_enabled]

    if not active_scores:
        return 0.0

    if mode == AggregationMode.MAX:
        return aggregate_max(active_scores)
    elif mode == AggregationMode.LINEAR:
        return aggregate_linear(active_scores)
    else:  # WEIGHTED (RMS)
        return aggregate_rms(active_scores)


def aggregate_rms(category_scores: list[CategoryScore]) -> float:
    """
    RMS (Root Mean Square) weighted aggregation.

    Formula: sqrt(sum(w * s^2) / sum(w))

    This prevents strong signals from being diluted by neutral signals.
    A 1.0 location + 0.0 politics yields ~0.71 (not 0.5 as with linear).

    Args:
        category_scores: List of active CategoryScore objects

    Returns:
        RMS-weighted interest score in [0, 1]
    """
    if not category_scores:
        return 0.0

    numerator = 0.0
    denominator = 0.0

    for cat in category_scores:
        score = cat.penalized_score
        weight = cat.weight

        numerator += weight * (score**2)
        denominator += weight

    if denominator <= 0:
        return 0.0

    result = math.sqrt(numerator / denominator)
    return max(0.0, min(1.0, result))


def aggregate_linear(category_scores: list[CategoryScore]) -> float:
    """
    Linear weighted average aggregation.

    Formula: sum(w * s) / sum(w)

    Traditional weighted average. Can cause signal dilution when
    some categories score 0.

    Args:
        category_scores: List of active CategoryScore objects

    Returns:
        Linearly-weighted interest score in [0, 1]
    """
    if not category_scores:
        return 0.0

    numerator = 0.0
    denominator = 0.0

    for cat in category_scores:
        score = cat.penalized_score
        weight = cat.weight

        numerator += weight * score
        denominator += weight

    if denominator <= 0:
        return 0.0

    result = numerator / denominator
    return max(0.0, min(1.0, result))


def aggregate_max(category_scores: list[CategoryScore]) -> float:
    """
    Max aggregation (legacy mode).

    Takes the maximum score across all categories (ignoring weights).

    Args:
        category_scores: List of active CategoryScore objects

    Returns:
        Maximum interest score in [0, 1]
    """
    if not category_scores:
        return 0.0

    return max(cat.penalized_score for cat in category_scores)


def calculate_prefetch_bounds(
    category_scores: dict[str, CategoryScore],
    weights: dict[str, float],
    unknown_assumption: float = 1.0,
) -> tuple[float | None, float, float]:
    """
    Calculate prefetch score and bounds for conservative mode.

    For categories that can be scored at prefetch (prefetch_capable=True),
    calculates the actual score. For unknown categories, uses unknown_assumption
    to compute bounds.

    Args:
        category_scores: Dict of category -> CategoryScore (may be partial)
        weights: Dict of category -> weight
        unknown_assumption: Score to assume for unknown categories (default 1.0)

    Returns:
        Tuple of (prefetch_score, lower_bound, upper_bound)
        prefetch_score is None if no categories are prefetch-capable
    """
    known_sum = 0.0
    known_weight_sum = 0.0
    unknown_weight_sum = 0.0

    for category, weight in weights.items():
        if weight <= 0:
            continue

        cat_score = category_scores.get(category)

        if cat_score is not None and cat_score.prefetch_capable and cat_score.is_configured:
            # Known category - use actual score
            known_sum += weight * cat_score.penalized_score
            known_weight_sum += weight
        else:
            # Unknown category
            unknown_weight_sum += weight

    total_weight = known_weight_sum + unknown_weight_sum

    if total_weight <= 0:
        return None, 0.0, 0.0

    # Prefetch score (known only)
    if known_weight_sum > 0:
        prefetch_score = known_sum / known_weight_sum
    else:
        prefetch_score = None

    # Lower bound (unknowns assumed 0)
    lower_bound = known_sum / total_weight

    # Upper bound (unknowns assumed unknown_assumption)
    upper_bound = (known_sum + unknown_weight_sum * unknown_assumption) / total_weight

    return prefetch_score, lower_bound, upper_bound


def compare_aggregation_modes(
    category_scores: dict[str, CategoryScore],
) -> dict[str, float]:
    """
    Calculate scores under all aggregation modes for comparison.

    Useful for debugging and the explain command.

    Args:
        category_scores: Dict of category -> CategoryScore

    Returns:
        Dict of mode name -> score
    """
    active = [c for c in category_scores.values() if c.is_configured and c.is_enabled]

    return {
        "rms": aggregate_rms(active),
        "linear": aggregate_linear(active),
        "max": aggregate_max(active),
    }
