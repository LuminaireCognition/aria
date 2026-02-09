"""
Interest Engine v2 Data Models.

Core data structures for the weighted signal-based interest scoring system.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AggregationMode(str, Enum):
    """Score aggregation mode across categories."""

    WEIGHTED = "weighted"  # RMS weighted blend (default)
    LINEAR = "linear"  # Traditional weighted average
    MAX = "max"  # Legacy max-of-layers


class ConfigTier(str, Enum):
    """Configuration complexity tier."""

    SIMPLE = "simple"  # preset + customize sliders
    INTERMEDIATE = "intermediate"  # preset + weights + rules
    ADVANCED = "advanced"  # full signals + rules + prefetch


class NotificationTier(str, Enum):
    """Notification delivery tier."""

    FILTER = "filter"  # Don't fetch from ESI
    LOG_ONLY = "log_only"  # Log but don't notify
    DIGEST = "digest"  # Batch into digests
    NOTIFY = "notify"  # Standard notification
    PRIORITY = "priority"  # Priority notification


# Default thresholds for notification tiers
DEFAULT_THRESHOLDS = {
    "digest": 0.40,
    "notify": 0.60,
    "priority": 0.85,
}

# RMS safety factor floor for strict prefetch mode
RMS_SAFETY_FLOOR = 0.45  # 1/sqrt(5)


def rms_safety_factor(n_categories: int) -> float:
    """
    Calculate RMS safety factor for prefetch threshold adjustment.

    The factor accounts for linear/RMS divergence in strict prefetch mode.
    With more categories, the worst-case divergence increases.

    Args:
        n_categories: Number of configured (non-zero weight) categories

    Returns:
        Safety factor in range [0.45, 1.0]
    """
    if n_categories <= 0:
        return 1.0
    if n_categories == 1:
        return 1.0
    # 1/sqrt(n), floored at 0.45 (1/sqrt(5))
    return max(1.0 / math.sqrt(n_categories), RMS_SAFETY_FLOOR)


@dataclass
class SignalScore:
    """
    Score from a single signal within a category.

    Signals produce normalized scores [0, 1] with optional match semantics
    for rule gates.
    """

    signal: str  # Signal name (e.g., "geographic", "security")
    score: float  # Normalized score 0.0 to 1.0
    reason: str | None = None  # Human-readable explanation
    weight: float = 1.0  # Signal weight within category
    match: bool | None = None  # Explicit match for gates (derived if None)
    prefetch_capable: bool = True  # Can score with RedisQ data only
    raw_value: Any = None  # Original value before scaling (for debugging)

    def __post_init__(self) -> None:
        """Clamp score to valid range."""
        self.score = max(0.0, min(1.0, self.score))

    @property
    def matches(self) -> bool:
        """
        Check if signal matches for gate evaluation.

        If match is explicitly set, use that. Otherwise derive from score.
        Default match threshold is 0.3.
        """
        if self.match is not None:
            return self.match
        return self.score >= 0.3

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        result = {
            "signal": self.signal,
            "score": round(self.score, 3),
            "weight": self.weight,
            "match": self.matches,
        }
        if self.reason:
            result["reason"] = self.reason
        if self.raw_value is not None:
            result["raw_value"] = self.raw_value
        return result


@dataclass
class CategoryScore:
    """
    Aggregated score for a signal category.

    Categories group related signals (e.g., location category contains
    geographic and security signals). Category scores are weighted and
    blended to produce the final interest score.
    """

    category: str  # Category name (e.g., "location", "value", "politics")
    score: float  # Aggregated score 0.0 to 1.0
    weight: float  # Category weight in final blend
    signals: dict[str, SignalScore] = field(default_factory=dict)
    match: bool = False  # Category match for gates
    reason: str | None = None  # Summary reason
    penalty_factor: float = 1.0  # Multiplicative penalty (0.0 to 1.0)

    @property
    def penalized_score(self) -> float:
        """Score after penalty application."""
        return self.score * self.penalty_factor

    @property
    def weighted_score(self) -> float:
        """Score weighted for final aggregation."""
        return self.penalized_score * self.weight

    @property
    def is_configured(self) -> bool:
        """Check if category has any configured signals."""
        return len(self.signals) > 0

    @property
    def is_enabled(self) -> bool:
        """Check if category is enabled (weight > 0)."""
        return self.weight > 0

    @property
    def prefetch_capable(self) -> bool:
        """
        Check if all signals in category are prefetch-capable.

        A category is only prefetch-capable if ALL its configured signals
        can score with RedisQ data alone.
        """
        if not self.signals:
            return True
        return all(s.prefetch_capable for s in self.signals.values())

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "category": self.category,
            "score": round(self.score, 3),
            "penalized_score": round(self.penalized_score, 3),
            "weight": self.weight,
            "match": self.match,
            "penalty_factor": self.penalty_factor,
            "signals": {name: sig.to_dict() for name, sig in self.signals.items()},
            "reason": self.reason,
        }


@dataclass
class RuleMatch:
    """Result of a rule evaluation."""

    rule_id: str  # Rule identifier
    matched: bool  # Whether rule matched
    reason: str | None = None  # Why it matched/didn't match
    prefetch_capable: bool = True  # Could evaluate at prefetch stage

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "rule_id": self.rule_id,
            "matched": self.matched,
            "reason": self.reason,
            "prefetch_capable": self.prefetch_capable,
        }


@dataclass
class InterestResultV2:
    """
    Complete interest calculation result from v2 engine.

    Contains the final interest score, category breakdown, rule matches,
    and metadata for explainability and debugging.
    """

    # Context
    system_id: int
    kill_id: int | None = None

    # Final score
    interest: float = 0.0  # Final blended score [0, 1]
    tier: NotificationTier = NotificationTier.FILTER

    # Aggregation details
    mode: AggregationMode = AggregationMode.WEIGHTED
    category_scores: dict[str, CategoryScore] = field(default_factory=dict)

    # Rule evaluation
    always_notify_matched: list[RuleMatch] = field(default_factory=list)
    always_ignore_matched: list[RuleMatch] = field(default_factory=list)
    require_all_passed: bool = True
    require_any_passed: bool = True
    gate_failure_reason: str | None = None

    # Prefetch metadata
    is_prefetch: bool = False  # True if scored with prefetch data only
    prefetch_mode: str = "auto"  # conservative, strict, bypass
    prefetch_score: float | None = None  # Prefetch-only score
    prefetch_upper_bound: float | None = None  # For conservative mode

    # Thresholds used
    thresholds: dict[str, float] = field(default_factory=dict)

    # Engine metadata
    engine_version: str = "v2"
    config_tier: ConfigTier = ConfigTier.SIMPLE
    preset: str | None = None

    @property
    def should_fetch(self) -> bool:
        """Check if kill should be fetched from ESI."""
        return self.tier != NotificationTier.FILTER

    @property
    def should_notify(self) -> bool:
        """Check if kill should generate a notification."""
        return self.tier in (NotificationTier.NOTIFY, NotificationTier.PRIORITY)

    @property
    def is_priority(self) -> bool:
        """Check if this is a priority notification."""
        return self.tier == NotificationTier.PRIORITY

    @property
    def is_digest(self) -> bool:
        """Check if this should be batched into digest."""
        return self.tier == NotificationTier.DIGEST

    @property
    def bypassed_scoring(self) -> bool:
        """Check if scoring was bypassed by always_notify rule."""
        return len(self.always_notify_matched) > 0 and any(
            m.matched for m in self.always_notify_matched
        )

    @property
    def was_ignored(self) -> bool:
        """Check if ignored by always_ignore rule."""
        return len(self.always_ignore_matched) > 0 and any(
            m.matched for m in self.always_ignore_matched
        )

    @property
    def dominant_category(self) -> str | None:
        """Get the highest-scoring category."""
        if not self.category_scores:
            return None
        enabled = [c for c in self.category_scores.values() if c.is_enabled]
        if not enabled:
            return None
        return max(enabled, key=lambda c: c.penalized_score).category

    def get_category_breakdown(self) -> list[tuple[str, float, float, bool]]:
        """
        Get sorted breakdown of category scores.

        Returns:
            List of (category, score, weight, match) tuples, sorted by weighted score
        """
        return sorted(
            [
                (c.category, c.penalized_score, c.weight, c.match)
                for c in self.category_scores.values()
                if c.is_enabled
            ],
            key=lambda x: x[1] * x[2],  # Sort by weighted contribution
            reverse=True,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        result: dict[str, Any] = {
            "system_id": self.system_id,
            "interest": round(self.interest, 3),
            "tier": self.tier.value,
            "mode": self.mode.value,
            "engine_version": self.engine_version,
            "config_tier": self.config_tier.value,
        }

        if self.kill_id:
            result["kill_id"] = self.kill_id
        if self.preset:
            result["preset"] = self.preset

        # Category breakdown
        result["categories"] = {name: cat.to_dict() for name, cat in self.category_scores.items()}

        # Dominant category
        if self.dominant_category:
            result["dominant_category"] = self.dominant_category

        # Rule matches
        if self.always_notify_matched:
            result["always_notify"] = [m.to_dict() for m in self.always_notify_matched]
        if self.always_ignore_matched:
            result["always_ignore"] = [m.to_dict() for m in self.always_ignore_matched]

        # Gate status
        if not self.require_all_passed or not self.require_any_passed:
            result["gates"] = {
                "require_all_passed": self.require_all_passed,
                "require_any_passed": self.require_any_passed,
            }
            if self.gate_failure_reason:
                result["gates"]["failure_reason"] = self.gate_failure_reason

        # Prefetch metadata
        if self.is_prefetch:
            result["prefetch"] = {
                "mode": self.prefetch_mode,
                "score": round(self.prefetch_score, 3) if self.prefetch_score else None,
                "upper_bound": (
                    round(self.prefetch_upper_bound, 3) if self.prefetch_upper_bound else None
                ),
            }

        # Thresholds
        if self.thresholds:
            result["thresholds"] = self.thresholds

        return result

    def explain(self) -> str:
        """
        Generate human-readable explanation of the score.

        Returns:
            Multi-line explanation string
        """
        lines = []

        # Header
        system_str = f"System {self.system_id}"
        if self.kill_id:
            system_str = f"Kill {self.kill_id} in {system_str}"
        lines.append(f"{system_str}")
        lines.append("─" * 40)

        # Rule bypass/ignore
        if self.was_ignored:
            matched = [m for m in self.always_ignore_matched if m.matched]
            lines.append(f"❌ IGNORED by: {', '.join(m.rule_id for m in matched)}")
            return "\n".join(lines)

        if self.bypassed_scoring:
            matched = [m for m in self.always_notify_matched if m.matched]
            lines.append(f"⚡ ALWAYS NOTIFY: {', '.join(m.rule_id for m in matched)}")
            lines.append(f"   Tier: {self.tier.value}")
            return "\n".join(lines)

        # Category breakdown
        for cat, score, weight, match in self.get_category_breakdown():
            cat_obj = self.category_scores[cat]
            match_char = "✓" if match else "○"
            weight_pct = f"{weight * 100:.0f}%"
            lines.append(f"{cat.capitalize():12} {match_char} {score:.2f} (weight {weight_pct})")

            # Signal details
            for sig_name, sig in cat_obj.signals.items():
                sig_match = "✓" if sig.matches else "○"
                reason_str = f" [{sig.reason}]" if sig.reason else ""
                lines.append(f"  └─ {sig_name}: {sig_match} {sig.score:.2f}{reason_str}")

        lines.append("─" * 40)

        # Gate status
        if not self.require_all_passed:
            lines.append(f"⚠ require_all FAILED: {self.gate_failure_reason}")
        if not self.require_any_passed:
            lines.append(f"⚠ require_any FAILED: {self.gate_failure_reason}")

        # Final score
        lines.append(f"Interest:   {self.interest:.2f} ({self.mode.value})")
        lines.append(f"Threshold:  {self.thresholds.get('notify', 0.6):.2f} (notify)")
        lines.append(
            f"Result:     {'✓ ' + self.tier.value.upper() if self.should_notify else '✗ ' + self.tier.value}"
        )

        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"InterestResultV2(system={self.system_id}, "
            f"interest={self.interest:.2f}, "
            f"tier={self.tier.value!r}, "
            f"mode={self.mode.value!r})"
        )


# =============================================================================
# Canonical Categories
# =============================================================================

# The 9 canonical signal categories
CANONICAL_CATEGORIES = (
    "location",
    "value",
    "politics",
    "activity",
    "time",
    "routes",
    "assets",
    "war",
    "ship",
)


def validate_category(category: str) -> bool:
    """Check if category name is valid."""
    return category in CANONICAL_CATEGORIES
