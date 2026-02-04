"""
Interest Engine v2 - Weighted Signal-Based Notification Filtering.

This module implements a modular, weighted interest scoring system that replaces
the v1 max-of-layers approach with RMS-weighted blending across 9 signal categories.

Key Components:
- SignalProvider: Protocol for scoring signals (location, value, politics, etc.)
- RuleProvider: Hard rules for must-notify/must-ignore conditions
- InterestEngineV2: Main orchestrator that blends signals and applies rules
- PresetLoader: Manages built-in and user-defined presets
- PrefetchScorer: Two-stage scoring with safety margins

Configuration Tiers:
- Simple: preset + customize sliders
- Intermediate: preset + explicit weights + rules
- Advanced: full signals + rules + prefetch control

Feature Flags:
- rule_dsl: Enable expression DSL for custom rules
- custom_signals: Enable user-defined signal plugins
- custom_presets: Enable user-defined preset files (default: true)
- custom_scaling: Enable user-defined scaling functions
- delivery_webhook: Enable generic webhook delivery (default: true)
- delivery_slack: Enable Slack delivery

See dev/proposals/NOTIFICATION_FILTER_REARCHITECTURE_PROPOSAL.md for design.
"""

from .config import InterestConfigV2, PrefetchConfig, RulesConfig, ThresholdsConfig
from .engine import InterestEngineV2, create_engine
from .features import FeatureFlags
from .models import (
    AggregationMode,
    CategoryScore,
    ConfigTier,
    InterestResultV2,
    NotificationTier,
    RuleMatch,
    SignalScore,
)
from .prefetch import PrefetchDecision, PrefetchScorer, create_prefetch_scorer
from .validation import ValidationError, ValidationResult, validate_interest_config

__all__ = [
    # Models
    "AggregationMode",
    "CategoryScore",
    "ConfigTier",
    "InterestResultV2",
    "NotificationTier",
    "RuleMatch",
    "SignalScore",
    # Config
    "FeatureFlags",
    "InterestConfigV2",
    "PrefetchConfig",
    "RulesConfig",
    "ThresholdsConfig",
    # Engine
    "InterestEngineV2",
    "create_engine",
    # Prefetch
    "PrefetchDecision",
    "PrefetchScorer",
    "create_prefetch_scorer",
    # Validation
    "ValidationError",
    "ValidationResult",
    "validate_interest_config",
]
