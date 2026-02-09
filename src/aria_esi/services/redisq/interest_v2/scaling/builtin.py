"""
Built-in Scaling Functions.

These scaling functions are always available (no feature flag required).
They convert raw values to normalized scores [0, 1].
"""

from __future__ import annotations

import math
from typing import Any

from ..providers.base import BaseScalingProvider


class SigmoidScaling(BaseScalingProvider):
    """
    S-curve scaling with configurable pivot point.

    Best for: Value (ISK) where you want to differentiate 100M vs 10B
    while handling extreme outliers gracefully.

    Config:
        min: Minimum value (score = 0 below this)
        max: Maximum value (score approaches 1 above this)
        pivot: Value where score = 0.5 (default: midpoint)
        steepness: How sharp the transition is (default: 6)

    Formula:
        normalized = (value - min) / (max - min)
        centered = (normalized - pivot_normalized) * steepness
        score = 1 / (1 + exp(-centered))
    """

    _name = "sigmoid"

    def scale(self, value: float, config: dict[str, Any]) -> float:
        """Apply sigmoid scaling."""
        min_val = config.get("min", 0.0)
        max_val = config.get("max", 1_000_000_000.0)  # 1B ISK default
        pivot = config.get("pivot", (min_val + max_val) / 2)
        steepness = config.get("steepness", 6.0)

        # Handle edge cases
        if max_val <= min_val:
            return 0.5
        if value <= min_val:
            return 0.0
        if value >= max_val:
            return 1.0

        # Normalize to [0, 1]
        normalized = (value - min_val) / (max_val - min_val)
        pivot_normalized = (pivot - min_val) / (max_val - min_val)

        # Apply sigmoid centered on pivot
        centered = (normalized - pivot_normalized) * steepness
        try:
            score = 1.0 / (1.0 + math.exp(-centered))
        except OverflowError:
            score = 0.0 if centered < 0 else 1.0

        return max(0.0, min(1.0, score))

    def validate(self, config: dict[str, Any]) -> list[str]:
        """Validate sigmoid config."""
        errors = []
        min_val = config.get("min", 0.0)
        max_val = config.get("max", 1_000_000_000.0)

        if min_val >= max_val:
            errors.append(f"min ({min_val}) must be less than max ({max_val})")

        if "pivot" in config:
            pivot = config["pivot"]
            if pivot < min_val or pivot > max_val:
                errors.append(f"pivot ({pivot}) must be between min and max")

        if "steepness" in config:
            if config["steepness"] <= 0:
                errors.append("steepness must be positive")

        return errors


class LinearScaling(BaseScalingProvider):
    """
    Direct proportion scaling.

    Best for: Distance decay, simple range mapping.

    Config:
        min: Minimum value (score = 0)
        max: Maximum value (score = 1)
        invert: If True, score = 1 at min and 0 at max (default: False)

    Formula:
        score = (value - min) / (max - min)
        if invert: score = 1 - score
    """

    _name = "linear"

    def scale(self, value: float, config: dict[str, Any]) -> float:
        """Apply linear scaling."""
        min_val = config.get("min", 0.0)
        max_val = config.get("max", 1.0)
        invert = config.get("invert", False)

        if max_val <= min_val:
            return 0.5

        if value <= min_val:
            score = 0.0
        elif value >= max_val:
            score = 1.0
        else:
            score = (value - min_val) / (max_val - min_val)

        if invert:
            score = 1.0 - score

        return max(0.0, min(1.0, score))

    def validate(self, config: dict[str, Any]) -> list[str]:
        """Validate linear config."""
        errors = []
        min_val = config.get("min", 0.0)
        max_val = config.get("max", 1.0)

        if min_val >= max_val:
            errors.append(f"min ({min_val}) must be less than max ({max_val})")

        return errors


class LogScaling(BaseScalingProvider):
    """
    Logarithmic scaling for wide-range values.

    Best for: Values spanning multiple orders of magnitude.

    Config:
        min: Minimum value (score = 0)
        max: Maximum value (score = 1)
        base: Log base (default: 10)

    Formula:
        score = log(1 + value - min) / log(1 + max - min)
    """

    _name = "log"

    def scale(self, value: float, config: dict[str, Any]) -> float:
        """Apply logarithmic scaling."""
        min_val = config.get("min", 0.0)
        max_val = config.get("max", 1_000_000_000.0)
        base = config.get("base", 10.0)

        if max_val <= min_val:
            return 0.5

        if value <= min_val:
            return 0.0
        if value >= max_val:
            return 1.0

        # Use log1p for numerical stability near 0
        # log_b(x) = ln(x) / ln(b)
        try:
            log_value = math.log1p(value - min_val) / math.log(base)
            log_max = math.log1p(max_val - min_val) / math.log(base)
            score = log_value / log_max if log_max > 0 else 0.5
        except (ValueError, ZeroDivisionError):
            score = 0.5

        return max(0.0, min(1.0, score))

    def validate(self, config: dict[str, Any]) -> list[str]:
        """Validate log config."""
        errors = []
        min_val = config.get("min", 0.0)
        max_val = config.get("max", 1_000_000_000.0)
        base = config.get("base", 10.0)

        if min_val >= max_val:
            errors.append(f"min ({min_val}) must be less than max ({max_val})")
        if base <= 1:
            errors.append(f"base ({base}) must be greater than 1")

        return errors


class StepScaling(BaseScalingProvider):
    """
    Discrete threshold-based scoring.

    Best for: Tier-based classification (cheap/medium/expensive).

    Config:
        thresholds: List of {"below": value, "score": score} or {"default": score}
                   Thresholds are evaluated in order; first match wins.

    Example:
        thresholds:
          - { below: 100_000_000, score: 0.3 }   # < 100M ISK
          - { below: 1_000_000_000, score: 0.8 } # < 1B ISK
          - { default: 1.0 }                      # >= 1B ISK
    """

    _name = "step"

    def scale(self, value: float, config: dict[str, Any]) -> float:
        """Apply step function scaling."""
        thresholds = config.get("thresholds", [])

        if not thresholds:
            return 0.5

        for threshold in thresholds:
            if "below" in threshold:
                if value < threshold["below"]:
                    return max(0.0, min(1.0, threshold.get("score", 0.0)))
            elif "above" in threshold:
                if value > threshold["above"]:
                    return max(0.0, min(1.0, threshold.get("score", 0.0)))
            elif "default" in threshold:
                return max(0.0, min(1.0, threshold["default"]))

        # No match, return 0.5
        return 0.5

    def validate(self, config: dict[str, Any]) -> list[str]:
        """Validate step config."""
        errors = []
        thresholds = config.get("thresholds", [])

        if not thresholds:
            errors.append("thresholds list is required for step scaling")
            return errors

        has_default = False
        prev_below = None

        for i, threshold in enumerate(thresholds):
            if not isinstance(threshold, dict):
                errors.append(f"threshold[{i}] must be a dictionary")
                continue

            if "default" in threshold:
                if has_default:
                    errors.append(f"threshold[{i}]: multiple defaults not allowed")
                has_default = True
                score = threshold["default"]
            elif "below" in threshold:
                below = threshold["below"]
                score = threshold.get("score")
                if score is None:
                    errors.append(f"threshold[{i}]: 'score' required with 'below'")
                if prev_below is not None and below <= prev_below:
                    errors.append(
                        f"threshold[{i}]: 'below' values must be ascending "
                        f"({below} <= {prev_below})"
                    )
                prev_below = below
            elif "above" in threshold:
                score = threshold.get("score")
                if score is None:
                    errors.append(f"threshold[{i}]: 'score' required with 'above'")
            else:
                errors.append(f"threshold[{i}]: must have 'below', 'above', or 'default'")
                continue

            # Validate score range
            if score is not None and not (0.0 <= score <= 1.0):
                errors.append(f"threshold[{i}]: score ({score}) must be between 0.0 and 1.0")

        return errors


class InverseScaling(BaseScalingProvider):
    """
    Inverse (1/x) decay scaling.

    Best for: Proximity scoring where closer = higher score.

    Config:
        base: Base value where score = 0.5 (default: 1.0)
        min_score: Minimum score at infinity (default: 0.0)

    Formula:
        score = base / (base + value)
    """

    _name = "inverse"

    def scale(self, value: float, config: dict[str, Any]) -> float:
        """Apply inverse scaling."""
        base = config.get("base", 1.0)
        min_score = config.get("min_score", 0.0)

        if base <= 0:
            return 0.5

        if value < 0:
            value = 0

        # At value=0, score=1; at value=base, score=0.5; at infinity, score->0
        score = base / (base + value)

        # Apply minimum score floor
        score = max(min_score, score)

        return max(0.0, min(1.0, score))

    def validate(self, config: dict[str, Any]) -> list[str]:
        """Validate inverse config."""
        errors = []

        if "base" in config and config["base"] <= 0:
            errors.append(f"base ({config['base']}) must be positive")

        if "min_score" in config:
            min_score = config["min_score"]
            if not (0.0 <= min_score <= 1.0):
                errors.append(f"min_score ({min_score}) must be between 0.0 and 1.0")

        return errors


# =============================================================================
# Utility Function
# =============================================================================


def scale_value(
    value: float,
    scale_type: str | dict[str, Any],
    config: dict[str, Any] | None = None,
) -> float:
    """
    Scale a value using the specified scaling function.

    Args:
        value: Raw value to scale
        scale_type: Scaling function name or dict with "provider" key
        config: Scaling parameters (merged with scale_type if dict)

    Returns:
        Normalized score in [0, 1]
    """
    # Handle dict-style config
    if isinstance(scale_type, dict):
        provider_name = scale_type.get("provider", "linear")
        merged_config = {**scale_type, **(config or {})}
    else:
        provider_name = scale_type
        merged_config = config or {}

    # Get provider from registry
    from ..providers.registry import get_provider_registry

    registry = get_provider_registry()
    provider = registry.get_scaling(provider_name)

    if provider is None:
        # Default to linear if unknown
        provider = LinearScaling()

    return provider.scale(value, merged_config)
