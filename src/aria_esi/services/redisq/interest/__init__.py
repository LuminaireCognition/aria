"""
Context-Aware Topology Interest Calculation.

Multi-layer interest scoring for kill filtering and notification prioritization.

The interest calculator coordinates multiple layers:
- Geographic: Distance from operational systems (home/hunting/transit)
- Entity: Corp/alliance involvement (corp losses always notify)
- Route: Named travel routes with ship filtering
- Asset: Corp structure and office locations
- Pattern: Activity spike and gatecamp escalation

Interest is calculated as: min(max(layer_scores) * escalation_multiplier, 1.0)

Usage:
    from aria_esi.services.redisq.interest import (
        InterestCalculator,
        InterestScore,
        LayerScore,
    )

    # Create calculator with layers
    calculator = InterestCalculator(layers=[geo_layer, entity_layer])

    # Pre-fetch check
    if calculator.should_fetch(system_id):
        kill = fetch_from_esi(kill_id)

        # Post-fetch scoring
        score = calculator.calculate_kill_interest(system_id, kill)
        if score.should_notify:
            send_notification(kill, score)
"""

from .calculator import InterestCalculator
from .config import ContextAwareTopologyConfig, migrate_legacy_config
from .models import (
    DIGEST_THRESHOLD,
    FETCH_THRESHOLD,
    LOG_THRESHOLD,
    PRIORITY_THRESHOLD,
    TIER_DIGEST,
    TIER_FILTER,
    TIER_LOG_ONLY,
    TIER_PRIORITY,
    InterestScore,
    LayerScore,
    PatternEscalation,
    get_tier,
)
from .presets import (
    ARCHETYPE_PRESETS,
    apply_preset,
    get_preset,
    list_presets,
)

__all__ = [
    # Calculator
    "InterestCalculator",
    # Config
    "ContextAwareTopologyConfig",
    "migrate_legacy_config",
    # Presets
    "ARCHETYPE_PRESETS",
    "get_preset",
    "list_presets",
    "apply_preset",
    # Models
    "InterestScore",
    "LayerScore",
    "PatternEscalation",
    # Tier constants
    "TIER_FILTER",
    "TIER_LOG_ONLY",
    "TIER_DIGEST",
    "TIER_PRIORITY",
    "get_tier",
    # Threshold constants
    "FETCH_THRESHOLD",
    "LOG_THRESHOLD",
    "DIGEST_THRESHOLD",
    "PRIORITY_THRESHOLD",
]
