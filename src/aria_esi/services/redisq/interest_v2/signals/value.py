"""
Value Signal for Interest Engine v2.

Scores kills based on ISK value with configurable scaling.

Prefetch capable: YES (zkb.totalValue available in RedisQ)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..models import SignalScore
from ..providers.base import BaseSignalProvider
from ..scaling import scale_value

if TYPE_CHECKING:
    from ...models import ProcessedKill


class ValueSignal(BaseSignalProvider):
    """
    ISK value-based scoring signal.

    Uses scaling functions to convert raw ISK to [0, 1] score.

    Config:
        min: Minimum value threshold (score = 0 below this)
        max: Maximum value for scaling (score approaches 1)
        scale: Scaling function ("sigmoid", "linear", "log", "step")
        pivot: For sigmoid scaling, value where score = 0.5
        thresholds: For step scaling, list of threshold configs

    Prefetch capable: YES (zkb.totalValue in RedisQ)
    """

    _name = "value"
    _category = "value"
    _prefetch_capable = True

    # Default configuration
    DEFAULT_MIN = 0
    DEFAULT_MAX = 10_000_000_000  # 10B ISK
    DEFAULT_PIVOT = 500_000_000  # 500M ISK
    DEFAULT_SCALE = "sigmoid"

    def score(
        self,
        kill: ProcessedKill | None,
        system_id: int,
        config: dict[str, Any],
    ) -> SignalScore:
        """Score based on kill value."""
        if kill is None:
            return SignalScore(
                signal=self._name,
                score=0.0,
                reason="No kill data",
                prefetch_capable=True,
            )

        value = kill.total_value
        min_val = config.get("min", self.DEFAULT_MIN)

        # Check minimum threshold
        if value < min_val:
            return SignalScore(
                signal=self._name,
                score=0.0,
                reason=f"Value {_format_isk(value)} below minimum {_format_isk(min_val)}",
                prefetch_capable=True,
                raw_value=value,
            )

        # Build scaling config
        scale_type = config.get("scale", self.DEFAULT_SCALE)
        scale_config = {
            "min": min_val,
            "max": config.get("max", self.DEFAULT_MAX),
        }

        # Add pivot for sigmoid
        if scale_type == "sigmoid":
            scale_config["pivot"] = config.get("pivot", self.DEFAULT_PIVOT)
            scale_config["steepness"] = config.get("steepness", 6.0)

        # Handle step thresholds
        if scale_type == "step" and "thresholds" in config:
            scale_config["thresholds"] = config["thresholds"]

        # Calculate score
        score = scale_value(value, scale_type, scale_config)

        return SignalScore(
            signal=self._name,
            score=score,
            reason=f"Value: {_format_isk(value)}",
            prefetch_capable=True,
            raw_value=value,
        )

    def validate(self, config: dict[str, Any]) -> list[str]:
        """Validate value signal config."""
        errors = []

        min_val = config.get("min", 0)
        max_val = config.get("max", self.DEFAULT_MAX)

        if min_val < 0:
            errors.append("min must be non-negative")

        if max_val <= min_val:
            errors.append(f"max ({max_val}) must be greater than min ({min_val})")

        if "pivot" in config:
            pivot = config["pivot"]
            if pivot < min_val or pivot > max_val:
                errors.append(f"pivot ({pivot}) must be between min and max")

        scale = config.get("scale", "sigmoid")
        valid_scales = {"sigmoid", "linear", "log", "step"}
        if scale not in valid_scales:
            errors.append(f"Unknown scale type: '{scale}'. Valid: {valid_scales}")

        if scale == "step" and "thresholds" not in config:
            errors.append("step scaling requires 'thresholds' configuration")

        return errors


def _format_isk(value: float) -> str:
    """Format ISK value for display."""
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{value:.0f}"
