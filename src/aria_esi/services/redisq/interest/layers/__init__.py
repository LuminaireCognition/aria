"""
Interest Calculation Layers.

Each layer provides interest scores based on a specific criterion:
- Geographic: Distance from operational systems
- Entity: Corp/alliance involvement
- Route: Named travel routes
- Asset: Corp structure/office locations
- Pattern: Activity patterns and escalation

Layers follow the InterestLayer protocol, implementing:
- score_system(system_id): Quick check with system ID only
- score_kill(system_id, kill): Full check with kill context
"""

from .asset import (
    OFFICE_INTEREST,
    STRUCTURE_INTEREST,
    AssetConfig,
    AssetLayer,
)
from .base import BaseLayer, InterestLayer
from .entity import (
    ALLIANCE_MEMBER_ATTACKER_INTEREST,
    ALLIANCE_MEMBER_VICTIM_INTEREST,
    CORP_MEMBER_ATTACKER_INTEREST,
    CORP_MEMBER_VICTIM_INTEREST,
    WAR_TARGET_INTEREST,
    WATCHLIST_ENTITY_INTEREST,
    EntityConfig,
    EntityLayer,
)
from .geographic import (
    DEFAULT_HOME_WEIGHTS,
    DEFAULT_HUNTING_WEIGHTS,
    DEFAULT_TRANSIT_WEIGHTS,
    GeographicConfig,
    GeographicLayer,
    GeographicSystem,
    SystemClassification,
)
from .pattern import (
    ESCALATION_TTL_SECONDS,
    GATECAMP_MULTIPLIER,
    SPIKE_MULTIPLIER,
    SUSTAINED_MULTIPLIER,
    PatternConfig,
    PatternLayer,
)
from .route import (
    LOGISTICS_SHIP_TYPES,
    RouteConfig,
    RouteDefinition,
    RouteLayer,
)

__all__ = [
    # Protocol
    "InterestLayer",
    "BaseLayer",
    # Geographic layer
    "GeographicLayer",
    "GeographicConfig",
    "GeographicSystem",
    "SystemClassification",
    "DEFAULT_HOME_WEIGHTS",
    "DEFAULT_HUNTING_WEIGHTS",
    "DEFAULT_TRANSIT_WEIGHTS",
    # Entity layer
    "EntityLayer",
    "EntityConfig",
    "CORP_MEMBER_VICTIM_INTEREST",
    "CORP_MEMBER_ATTACKER_INTEREST",
    "ALLIANCE_MEMBER_VICTIM_INTEREST",
    "ALLIANCE_MEMBER_ATTACKER_INTEREST",
    "WAR_TARGET_INTEREST",
    "WATCHLIST_ENTITY_INTEREST",
    # Route layer
    "RouteLayer",
    "RouteConfig",
    "RouteDefinition",
    "LOGISTICS_SHIP_TYPES",
    # Asset layer
    "AssetLayer",
    "AssetConfig",
    "STRUCTURE_INTEREST",
    "OFFICE_INTEREST",
    # Pattern layer
    "PatternLayer",
    "PatternConfig",
    "GATECAMP_MULTIPLIER",
    "SPIKE_MULTIPLIER",
    "SUSTAINED_MULTIPLIER",
    "ESCALATION_TTL_SECONDS",
]
