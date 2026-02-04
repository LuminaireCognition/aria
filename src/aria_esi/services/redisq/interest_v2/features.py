"""
Feature Flags for Interest Engine v2.

Controls opt-in features like expression DSL, custom signals, and delivery providers.
Feature flags are loaded from userdata/config.json under notifications.features.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class FeatureFlags:
    """
    Feature flags for opt-in v2 functionality.

    Most features default to False (conservative). Notable exceptions:
    - custom_presets: Low risk, high value - enabled by default
    - delivery_webhook: Generic webhooks are common - enabled by default

    Flags are loaded from userdata/config.json:
    {
        "notifications": {
            "features": {
                "rule_dsl": false,
                ...
            }
        }
    }
    """

    # Rule system
    rule_dsl: bool = False  # Enable expression DSL for custom rules

    # Extensibility
    custom_signals: bool = False  # Enable user-defined signal plugins
    custom_presets: bool = True  # Enable user-defined preset files
    custom_scaling: bool = False  # Enable user-defined scaling functions

    # Delivery providers
    delivery_webhook: bool = True  # Generic HTTP POST webhook
    delivery_slack: bool = False  # Slack webhook with Block Kit
    delivery_email: bool = False  # Email digest (batched)
    delivery_pushover: bool = False  # Mobile push
    delivery_matrix: bool = False  # Matrix protocol

    # Engine selection (for rollout)
    default_engine: str = "v1"  # "v1" or "v2" - default engine for new profiles

    @classmethod
    def from_config(cls, config: dict[str, Any] | None) -> FeatureFlags:
        """
        Load feature flags from config dictionary.

        Args:
            config: notifications.features section from config.json

        Returns:
            FeatureFlags with values from config or defaults
        """
        if not config:
            return cls()

        # Handle both flat dict and nested structure
        features = config.get("features", config)
        if not isinstance(features, dict):
            return cls()

        return cls(
            rule_dsl=features.get("rule_dsl", False),
            custom_signals=features.get("custom_signals", False),
            custom_presets=features.get("custom_presets", True),
            custom_scaling=features.get("custom_scaling", False),
            delivery_webhook=features.get("delivery_webhook", True),
            delivery_slack=features.get("delivery_slack", False),
            delivery_email=features.get("delivery_email", False),
            delivery_pushover=features.get("delivery_pushover", False),
            delivery_matrix=features.get("delivery_matrix", False),
            default_engine=features.get("default_engine", "v1"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for config serialization."""
        return {
            "rule_dsl": self.rule_dsl,
            "custom_signals": self.custom_signals,
            "custom_presets": self.custom_presets,
            "custom_scaling": self.custom_scaling,
            "delivery_webhook": self.delivery_webhook,
            "delivery_slack": self.delivery_slack,
            "delivery_email": self.delivery_email,
            "delivery_pushover": self.delivery_pushover,
            "delivery_matrix": self.delivery_matrix,
            "default_engine": self.default_engine,
        }

    def is_delivery_enabled(self, provider: str) -> bool:
        """
        Check if a delivery provider is enabled.

        Args:
            provider: Provider name (discord, webhook, slack, etc.)

        Returns:
            True if provider is enabled
        """
        # Discord and log are always available
        if provider in ("discord", "log"):
            return True

        flag_name = f"delivery_{provider}"
        return getattr(self, flag_name, False)

    def validate_rule_dsl(self) -> tuple[bool, str | None]:
        """
        Check if expression DSL is available.

        Returns:
            (is_available, error_message_if_not)
        """
        if self.rule_dsl:
            return True, None
        return False, (
            "Expression DSL requires 'features.rule_dsl: true' in config. "
            "Use template-based rules instead, or enable the feature flag."
        )

    def validate_custom_signals(self) -> tuple[bool, str | None]:
        """Check if custom signals are available."""
        if self.custom_signals:
            return True, None
        return False, (
            "Custom signals require 'features.custom_signals: true' in config. "
            "Use built-in signals instead, or enable the feature flag."
        )

    def validate_custom_scaling(self) -> tuple[bool, str | None]:
        """Check if custom scaling functions are available."""
        if self.custom_scaling:
            return True, None
        return False, (
            "Custom scaling functions require 'features.custom_scaling: true'. "
            "Use built-in scaling (sigmoid, linear, log, step, inverse) instead."
        )


# Global feature flags instance (set during initialization)
_global_features: FeatureFlags | None = None


def get_feature_flags() -> FeatureFlags:
    """
    Get the global feature flags instance.

    Returns:
        FeatureFlags instance (defaults if not initialized)
    """
    global _global_features
    if _global_features is None:
        return FeatureFlags()
    return _global_features


def set_feature_flags(flags: FeatureFlags) -> None:
    """
    Set the global feature flags instance.

    Called during application initialization with loaded config.

    Args:
        flags: FeatureFlags instance to use globally
    """
    global _global_features
    _global_features = flags


def init_feature_flags(config: dict[str, Any] | None) -> FeatureFlags:
    """
    Initialize feature flags from config and set globally.

    Args:
        config: notifications section from config.json

    Returns:
        Initialized FeatureFlags
    """
    flags = FeatureFlags.from_config(config)
    set_feature_flags(flags)
    return flags
