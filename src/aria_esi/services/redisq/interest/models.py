"""
Interest Calculation Models.

Data classes for multi-layer interest scoring in the context-aware topology system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

# =============================================================================
# Interest Tiers
# =============================================================================

# Interest score thresholds for notification tiers
TIER_FILTER = 0.0  # Below this: don't fetch from ESI
TIER_LOG_ONLY = 0.3  # Below this: log only, no notification
TIER_DIGEST = 0.6  # Below this: batch into digests
TIER_PRIORITY = 0.8  # Above this: priority notification

# Threshold constants (aliases for config use)
FETCH_THRESHOLD = TIER_FILTER  # 0.0
LOG_THRESHOLD = TIER_LOG_ONLY  # 0.3
DIGEST_THRESHOLD = TIER_DIGEST  # 0.6
PRIORITY_THRESHOLD = TIER_PRIORITY  # 0.8


def get_tier(interest: float) -> str:
    """
    Map interest score to notification tier.

    Args:
        interest: Interest score (0.0 to 1.0+)

    Returns:
        Tier name: "filter", "log_only", "digest", "standard", or "priority"
    """
    if interest <= TIER_FILTER:
        return "filter"
    elif interest < TIER_LOG_ONLY:
        return "log_only"
    elif interest < TIER_DIGEST:
        return "digest"
    elif interest < TIER_PRIORITY:
        return "standard"
    else:
        return "priority"


# =============================================================================
# Layer Score
# =============================================================================


@dataclass
class LayerScore:
    """
    Interest score from a single layer.

    Each layer calculates its own score independently.
    The final interest is max(layer_scores).
    """

    layer: str  # "geographic", "entity", "route", "asset"
    score: float  # 0.0 to 1.0
    reason: str | None = None  # Human-readable explanation

    def __repr__(self) -> str:
        if self.reason:
            return f"LayerScore({self.layer}={self.score:.2f}, {self.reason!r})"
        return f"LayerScore({self.layer}={self.score:.2f})"


# =============================================================================
# Pattern Escalation
# =============================================================================


@dataclass
class PatternEscalation:
    """
    Activity pattern-based interest multiplier.

    Applied after base interest calculation to boost interest
    when dangerous patterns are detected (gatecamps, activity spikes).
    """

    multiplier: float = 1.0  # Multiplier applied to base interest
    reason: str | None = None  # Human-readable explanation
    expires_at: float | None = None  # Unix timestamp when escalation expires

    def is_expired(self, now: float | None = None) -> bool:
        """Check if escalation has expired."""
        if self.expires_at is None:
            return False
        if now is None:
            import time

            now = time.time()
        return now > self.expires_at

    def __repr__(self) -> str:
        if self.reason:
            return f"PatternEscalation({self.multiplier}x, {self.reason!r})"
        return f"PatternEscalation({self.multiplier}x)"


# =============================================================================
# Interest Score
# =============================================================================


@dataclass
class InterestScore:
    """
    Complete interest calculation result.

    Contains the final interest score along with detailed breakdown
    of how each layer contributed.
    """

    system_id: int
    interest: float  # Final score (after escalation, capped at 1.0)
    base_interest: float  # Pre-escalation score (max of layer scores)
    dominant_layer: str  # Which layer provided the winning score
    layer_scores: dict[str, LayerScore] = field(default_factory=dict)
    escalation: PatternEscalation | None = None

    @property
    def tier(self) -> str:
        """
        Get notification tier based on interest score.

        Returns:
            Tier name: "filter", "log_only", "digest", "standard", or "priority"
        """
        return get_tier(self.interest)

    @property
    def should_fetch(self) -> bool:
        """Check if kill should be fetched from ESI."""
        return self.tier != "filter"

    @property
    def should_notify(self) -> bool:
        """Check if kill should generate a notification."""
        return self.tier in ("standard", "priority")

    @property
    def is_priority(self) -> bool:
        """Check if this is a priority notification."""
        return self.tier == "priority"

    @property
    def is_digest(self) -> bool:
        """Check if this should be batched into digest."""
        return self.tier == "digest"

    @property
    def dominant_reason(self) -> str | None:
        """Get the reason from the dominant layer."""
        if self.dominant_layer in self.layer_scores:
            return self.layer_scores[self.dominant_layer].reason
        return None

    def get_layer_breakdown(self) -> list[tuple[str, float, str | None]]:
        """
        Get sorted breakdown of layer scores.

        Returns:
            List of (layer_name, score, reason) tuples, sorted by score descending
        """
        return sorted(
            [(ls.layer, ls.score, ls.reason) for ls in self.layer_scores.values()],
            key=lambda x: x[1],
            reverse=True,
        )

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        result = {
            "system_id": self.system_id,
            "interest": round(self.interest, 3),
            "base_interest": round(self.base_interest, 3),
            "dominant_layer": self.dominant_layer,
            "tier": self.tier,
            "layer_scores": {
                name: {"score": round(ls.score, 3), "reason": ls.reason}
                for name, ls in self.layer_scores.items()
            },
        }
        if self.escalation and self.escalation.multiplier != 1.0:
            result["escalation"] = {
                "multiplier": self.escalation.multiplier,
                "reason": self.escalation.reason,
            }
        return result

    def __repr__(self) -> str:
        return (
            f"InterestScore(system={self.system_id}, "
            f"interest={self.interest:.2f}, "
            f"tier={self.tier!r}, "
            f"dominant={self.dominant_layer!r})"
        )
