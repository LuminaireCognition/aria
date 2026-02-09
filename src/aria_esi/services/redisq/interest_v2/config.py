"""
Interest Engine v2 Configuration.

Handles parsing and validation of profile interest configuration,
with support for three-tier progressive complexity:
- Simple: preset + customize sliders
- Intermediate: preset + explicit weights + rules
- Advanced: full signals + rules + prefetch control
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import (
    CANONICAL_CATEGORIES,
    DEFAULT_THRESHOLDS,
    AggregationMode,
    ConfigTier,
)


@dataclass
class ThresholdsConfig:
    """Notification tier thresholds."""

    priority: float = DEFAULT_THRESHOLDS["priority"]
    notify: float = DEFAULT_THRESHOLDS["notify"]
    digest: float = DEFAULT_THRESHOLDS["digest"]

    def __post_init__(self) -> None:
        """Validate threshold ordering."""
        # Will be checked in validate(), but ensure non-negative
        self.priority = max(0.0, min(1.0, self.priority))
        self.notify = max(0.0, min(1.0, self.notify))
        self.digest = max(0.0, min(1.0, self.digest))

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ThresholdsConfig:
        """Create from dictionary."""
        if not data:
            return cls()
        return cls(
            priority=data.get("priority", DEFAULT_THRESHOLDS["priority"]),
            notify=data.get("notify", DEFAULT_THRESHOLDS["notify"]),
            digest=data.get("digest", DEFAULT_THRESHOLDS["digest"]),
        )

    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary."""
        return {
            "priority": self.priority,
            "notify": self.notify,
            "digest": self.digest,
        }

    def validate(self) -> list[str]:
        """Validate threshold configuration."""
        errors = []
        # Ordering: digest <= notify <= priority
        if self.digest > self.notify:
            errors.append(
                f"Threshold ordering violated: digest ({self.digest}) > notify ({self.notify})"
            )
        if self.notify > self.priority:
            errors.append(
                f"Threshold ordering violated: notify ({self.notify}) > priority ({self.priority})"
            )
        return errors


@dataclass
class PrefetchConfig:
    """Prefetch scoring configuration."""

    mode: str = "auto"  # auto, conservative, strict, bypass
    min_threshold: float | None = None  # Override threshold for prefetch gate
    unknown_assumption: float = 1.0  # Score for unknown categories (safety)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> PrefetchConfig:
        """Create from dictionary."""
        if not data:
            return cls()
        return cls(
            mode=data.get("mode", "auto"),
            min_threshold=data.get("min_threshold"),
            unknown_assumption=data.get("unknown_assumption", 1.0),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result: dict[str, Any] = {"mode": self.mode}
        if self.min_threshold is not None:
            result["min_threshold"] = self.min_threshold
        if self.unknown_assumption != 1.0:
            result["unknown_assumption"] = self.unknown_assumption
        return result

    def validate(self) -> list[str]:
        """Validate prefetch configuration."""
        errors = []
        valid_modes = ("auto", "conservative", "strict", "bypass")
        if self.mode not in valid_modes:
            errors.append(f"Invalid prefetch mode: {self.mode}. Must be one of {valid_modes}")
        if self.min_threshold is not None and not (0.0 <= self.min_threshold <= 1.0):
            errors.append(f"min_threshold must be between 0.0 and 1.0, got {self.min_threshold}")
        if not (0.0 <= self.unknown_assumption <= 1.0):
            errors.append(
                f"unknown_assumption must be between 0.0 and 1.0, got {self.unknown_assumption}"
            )
        return errors


@dataclass
class RulesConfig:
    """Hard rules configuration."""

    always_notify: list[str] = field(default_factory=list)  # Rule IDs
    always_ignore: list[str] = field(default_factory=list)  # Rule IDs
    require_all: list[str] = field(default_factory=list)  # Category names
    require_any: list[str] = field(default_factory=list)  # Category names
    custom: dict[str, Any] = field(default_factory=dict)  # Custom rule definitions

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> RulesConfig:
        """Create from dictionary."""
        if not data:
            return cls()
        return cls(
            always_notify=data.get("always_notify", []),
            always_ignore=data.get("always_ignore", []),
            require_all=data.get("require_all", []),
            require_any=data.get("require_any", []),
            custom=data.get("custom", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result: dict[str, Any] = {}
        if self.always_notify:
            result["always_notify"] = self.always_notify
        if self.always_ignore:
            result["always_ignore"] = self.always_ignore
        if self.require_all:
            result["require_all"] = self.require_all
        if self.require_any:
            result["require_any"] = self.require_any
        if self.custom:
            result["custom"] = self.custom
        return result

    def has_gates(self) -> bool:
        """Check if any gates are configured."""
        return bool(self.require_all or self.require_any)

    def has_custom_rules(self) -> bool:
        """Check if custom rules are defined."""
        return bool(self.custom)


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""

    max_per_hour: int = 60
    burst: int = 5
    bypass_for_always_notify: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> RateLimitConfig:
        """Create from dictionary."""
        if not data:
            return cls()
        return cls(
            max_per_hour=data.get("max_per_hour", 60),
            burst=data.get("burst", 5),
            bypass_for_always_notify=data.get("bypass_for_always_notify", False),
        )


@dataclass
class InterestConfigV2:
    """
    Interest Engine v2 configuration.

    Supports three tiers of configuration complexity:
    - Simple: preset + customize sliders + basic rules
    - Intermediate: preset + explicit weights + rules
    - Advanced: full signals + rules + prefetch control

    The tier is auto-detected based on which fields are present.
    """

    # Engine selection
    engine: str = "v1"  # "v1" or "v2"

    # Aggregation mode
    mode: AggregationMode = AggregationMode.WEIGHTED

    # Simple tier: preset + customize
    preset: str | None = None  # Built-in or user-defined preset name
    customize: dict[str, str] | None = None  # Category adjustments ("+20%", "-10%")

    # Intermediate tier: explicit weights
    weights: dict[str, float] | None = None  # Category weights 0.0-1.0

    # Advanced tier: full signal configuration
    signals: dict[str, Any] | None = None  # Per-category signal config

    # Rules (all tiers, but simple tier is limited)
    rules: RulesConfig = field(default_factory=RulesConfig)

    # Thresholds
    thresholds: ThresholdsConfig = field(default_factory=ThresholdsConfig)

    # Prefetch (advanced only)
    prefetch: PrefetchConfig = field(default_factory=PrefetchConfig)

    # Rate limiting
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)

    @property
    def tier(self) -> ConfigTier:
        """
        Detect configuration tier based on present fields.

        Tier detection rules:
        - Has `signals` block → Advanced
        - Has `weights` but no `signals` → Intermediate
        - Has `preset`, optional customize/thresholds/rules.always_* → Simple
        """
        if self.signals is not None:
            return ConfigTier.ADVANCED
        if self.weights is not None:
            return ConfigTier.INTERMEDIATE
        return ConfigTier.SIMPLE

    @property
    def is_v2(self) -> bool:
        """Check if this configuration uses v2 engine."""
        return self.engine == "v2"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> InterestConfigV2:
        """
        Create from dictionary.

        Args:
            data: interest section from profile YAML

        Returns:
            InterestConfigV2 instance
        """
        if not data:
            return cls()

        # Parse mode
        mode_str = data.get("mode", "weighted")
        try:
            mode = AggregationMode(mode_str)
        except ValueError:
            mode = AggregationMode.WEIGHTED

        # Parse sub-configs
        rules = RulesConfig.from_dict(data.get("rules"))
        thresholds = ThresholdsConfig.from_dict(data.get("thresholds"))
        prefetch = PrefetchConfig.from_dict(data.get("prefetch"))
        rate_limit = RateLimitConfig.from_dict(data.get("rate_limit"))

        return cls(
            engine=data.get("engine", "v1"),
            mode=mode,
            preset=data.get("preset"),
            customize=data.get("customize"),
            weights=data.get("weights"),
            signals=data.get("signals"),
            rules=rules,
            thresholds=thresholds,
            prefetch=prefetch,
            rate_limit=rate_limit,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        result: dict[str, Any] = {"engine": self.engine}

        if self.mode != AggregationMode.WEIGHTED:
            result["mode"] = self.mode.value

        if self.preset:
            result["preset"] = self.preset
        if self.customize:
            result["customize"] = self.customize
        if self.weights:
            result["weights"] = self.weights
        if self.signals:
            result["signals"] = self.signals

        rules_dict = self.rules.to_dict()
        if rules_dict:
            result["rules"] = rules_dict

        # Only include thresholds if non-default
        thresh_dict = self.thresholds.to_dict()
        if thresh_dict != DEFAULT_THRESHOLDS:
            result["thresholds"] = thresh_dict

        # Only include prefetch if non-default
        if self.prefetch.mode != "auto" or self.prefetch.min_threshold is not None:
            result["prefetch"] = self.prefetch.to_dict()

        return result

    def validate(self) -> list[str]:
        """
        Validate the configuration.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        tier = self.tier

        # Engine validation
        if self.engine not in ("v1", "v2"):
            errors.append(f"Invalid engine: {self.engine}. Must be 'v1' or 'v2'")

        # Mode validation for prefetch
        if self.mode == AggregationMode.MAX and self.prefetch.mode != "bypass":
            errors.append(
                "mode: max requires prefetch.mode: bypass (prefetch scoring not supported)"
            )

        # Tier-specific validation
        if tier == ConfigTier.SIMPLE:
            errors.extend(self._validate_simple_tier())
        elif tier == ConfigTier.INTERMEDIATE:
            errors.extend(self._validate_intermediate_tier())
        else:
            errors.extend(self._validate_advanced_tier())

        # Weight validation (for intermediate/advanced)
        if self.weights:
            errors.extend(self._validate_weights())

        # Rules validation
        errors.extend(self._validate_rules())

        # Threshold validation
        errors.extend(self.thresholds.validate())

        # Prefetch validation
        errors.extend(self.prefetch.validate())

        return errors

    def _validate_simple_tier(self) -> list[str]:
        """Validate simple tier constraints."""
        errors = []

        # Simple tier requires preset
        if not self.preset:
            errors.append("Simple tier requires a preset. Specify 'preset: <name>'.")

        # Simple tier doesn't allow weights
        if self.weights:
            errors.append(
                "Simple tier does not allow 'weights'. Use 'customize' with percentages, "
                "or upgrade to Intermediate tier by adding 'weights'."
            )

        # Simple tier doesn't allow signals
        if self.signals:
            errors.append(
                "Simple tier does not allow 'signals'. Use preset defaults, "
                "or upgrade to Advanced tier by adding 'signals'."
            )

        # Simple tier only allows built-in rules in always_notify/always_ignore
        if self.rules.has_custom_rules():
            errors.append(
                "Simple tier does not allow custom rules. Use built-in rule IDs, "
                "or upgrade to Advanced tier."
            )

        # Simple tier doesn't allow require_any/require_all
        if self.rules.has_gates():
            errors.append(
                "Simple tier does not allow require_any/require_all gates. "
                "Upgrade to Intermediate tier or higher."
            )

        return errors

    def _validate_intermediate_tier(self) -> list[str]:
        """Validate intermediate tier constraints."""
        errors = []

        # Intermediate tier requires preset for signal defaults
        if not self.preset:
            errors.append(
                "Intermediate tier with explicit weights requires a preset for signal defaults. "
                "Add 'preset: <name>' or upgrade to Advanced tier with explicit 'signals'."
            )

        # Intermediate tier doesn't allow signals
        if self.signals:
            errors.append(
                "Intermediate tier does not use 'signals' block. Remove it or "
                "upgrade to Advanced tier (signals present implies Advanced)."
            )

        return errors

    def _validate_advanced_tier(self) -> list[str]:
        """Validate advanced tier constraints."""
        errors = []

        # Advanced tier needs either preset or weights
        if not self.preset and not self.weights:
            errors.append(
                "Advanced tier requires either 'preset' or explicit 'weights'. "
                "Provide at least one for weight baseline."
            )

        return errors

    def _validate_weights(self) -> list[str]:
        """Validate weight configuration."""
        errors = []

        if not self.weights:
            return errors

        all_zero = True
        for category, weight in self.weights.items():
            # Category name validation
            if category not in CANONICAL_CATEGORIES:
                errors.append(
                    f"Unknown category '{category}'. "
                    f"Valid categories: {', '.join(CANONICAL_CATEGORIES)}"
                )
                continue

            # Weight range validation
            if not isinstance(weight, (int, float)):
                errors.append(
                    f"Weight for '{category}' must be a number, got {type(weight).__name__}"
                )
                continue

            if weight < 0:
                errors.append(f"Weight must be non-negative: {category} = {weight}")
            elif weight > 0:
                all_zero = False

            # Check for non-finite values
            import math

            if math.isnan(weight) or math.isinf(weight):
                errors.append(f"Weight must be finite: {category} = {weight}")

        if all_zero and self.weights:
            errors.append(
                "All category weights are zero; no notifications will match. "
                "Set at least one weight > 0."
            )

        return errors

    def _validate_rules(self) -> list[str]:
        """Validate rules configuration."""
        errors = []

        # Check require_all/require_any reference valid categories
        for gate_name, categories in [
            ("require_all", self.rules.require_all),
            ("require_any", self.rules.require_any),
        ]:
            for cat in categories:
                if cat not in CANONICAL_CATEGORIES:
                    errors.append(
                        f"rules.{gate_name} references unknown category '{cat}'. "
                        f"Valid: {', '.join(CANONICAL_CATEGORIES)}"
                    )

        # Check for disabled categories in gates
        if self.weights:
            for cat in self.rules.require_all:
                if cat in self.weights and self.weights[cat] == 0:
                    errors.append(
                        f"Category '{cat}' in require_all has weight 0 (disabled). "
                        "Cannot require a disabled category."
                    )

            # Check require_any doesn't contain only disabled categories
            if self.rules.require_any:
                all_disabled = all(
                    cat in self.weights and self.weights[cat] == 0
                    for cat in self.rules.require_any
                    if cat in CANONICAL_CATEGORIES
                )
                if all_disabled:
                    errors.append(
                        "All categories in require_any are disabled (weight 0). "
                        "At least one must be enabled."
                    )

        return errors

    def get_effective_weights(self) -> dict[str, float]:
        """
        Get effective weights, applying customize sliders to preset baseline.

        Returns:
            Dictionary of category -> weight (0.0 to 1.0+)
        """
        # This will be implemented fully when presets are loaded
        # For now, return explicit weights or empty dict
        if self.weights:
            return dict(self.weights)
        return {}


def parse_customize_adjustment(adjustment: str) -> float:
    """
    Parse a customize slider adjustment string.

    Args:
        adjustment: String like "+20%", "-10%", "0%"

    Returns:
        Multiplier (e.g., 1.2 for +20%, 0.9 for -10%)
    """
    if not adjustment:
        return 1.0

    adjustment = adjustment.strip()
    if adjustment.endswith("%"):
        try:
            pct = float(adjustment[:-1])
            # +20% -> 1.2, -10% -> 0.9
            return max(0.0, 1.0 + pct / 100.0)
        except ValueError:
            pass

    return 1.0
