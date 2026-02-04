"""
Context-Aware Topology Configuration.

Provides configuration loading and validation for the multi-layer
interest calculation system.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ....core.logging import get_logger
from .models import (
    DIGEST_THRESHOLD,
    FETCH_THRESHOLD,
    LOG_THRESHOLD,
    PRIORITY_THRESHOLD,
)

if TYPE_CHECKING:
    from ....universe.graph import UniverseGraph
    from .calculator import InterestCalculator
    from .layers.base import InterestLayer

logger = get_logger(__name__)


# =============================================================================
# Configuration Classes
# =============================================================================


@dataclass
class ContextAwareTopologyConfig:
    """
    Configuration for context-aware multi-layer topology filtering.

    This config replaces the simple operational_systems + hop expansion
    with a multi-layer system where interest = max(layer_scores) * escalation.

    Layers:
    - Geographic: System proximity with classifications (home/hunting/transit)
    - Entity: Corp/alliance involvement (corp member loss = 1.0 always)
    - Route: Named travel corridors with ship filtering
    - Asset: Corp structures and offices
    - Pattern: Activity escalation (gatecamps, spikes)

    Config lives in userdata/config.json under redisq.context_topology.
    """

    enabled: bool = False

    # Optional archetype preset (hunter, industrial, sovereignty, wormhole)
    archetype: str | None = None

    # Layer configurations (each is a dict passed to layer.from_config())
    geographic: dict[str, Any] = field(default_factory=dict)
    entity: dict[str, Any] = field(default_factory=dict)
    routes: list[dict[str, Any]] = field(default_factory=list)
    assets: dict[str, Any] = field(default_factory=dict)
    patterns: dict[str, Any] = field(default_factory=dict)

    # Interest thresholds
    fetch_threshold: float = FETCH_THRESHOLD
    log_threshold: float = LOG_THRESHOLD
    digest_threshold: float = DIGEST_THRESHOLD
    priority_threshold: float = PRIORITY_THRESHOLD

    # Track which keys were explicitly set by user (for preset merging)
    # This allows distinguishing "user set to default" from "user didn't set"
    _explicit_keys: set[str] = field(default_factory=set, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ContextAwareTopologyConfig:
        """Create from configuration dict."""
        if not data:
            return cls()

        # Track which keys were explicitly provided by the user
        # This allows "user set to default" to override preset values
        explicit_keys = set(data.keys())

        return cls(
            enabled=data.get("enabled", False),
            archetype=data.get("archetype"),
            geographic=data.get("geographic", {}),
            entity=data.get("entity", {}),
            routes=data.get("routes", []),
            assets=data.get("assets", {}),
            patterns=data.get("patterns", {}),
            fetch_threshold=data.get("fetch_threshold", FETCH_THRESHOLD),
            log_threshold=data.get("log_threshold", LOG_THRESHOLD),
            digest_threshold=data.get("digest_threshold", DIGEST_THRESHOLD),
            priority_threshold=data.get("priority_threshold", PRIORITY_THRESHOLD),
            _explicit_keys=explicit_keys,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to configuration dict."""
        result: dict[str, Any] = {
            "enabled": self.enabled,
        }

        if self.archetype:
            result["archetype"] = self.archetype

        if self.geographic:
            result["geographic"] = self.geographic
        if self.entity:
            result["entity"] = self.entity
        if self.routes:
            result["routes"] = self.routes
        if self.assets:
            result["assets"] = self.assets
        if self.patterns:
            result["patterns"] = self.patterns

        # Only include thresholds if non-default
        if self.fetch_threshold != FETCH_THRESHOLD:
            result["fetch_threshold"] = self.fetch_threshold
        if self.log_threshold != LOG_THRESHOLD:
            result["log_threshold"] = self.log_threshold
        if self.digest_threshold != DIGEST_THRESHOLD:
            result["digest_threshold"] = self.digest_threshold
        if self.priority_threshold != PRIORITY_THRESHOLD:
            result["priority_threshold"] = self.priority_threshold

        return result

    def validate(self) -> list[str]:
        """
        Validate configuration.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Threshold validation
        if not (0.0 <= self.fetch_threshold <= 1.0):
            errors.append("fetch_threshold must be between 0.0 and 1.0")
        if not (0.0 <= self.log_threshold <= 1.0):
            errors.append("log_threshold must be between 0.0 and 1.0")
        if not (0.0 <= self.digest_threshold <= 1.0):
            errors.append("digest_threshold must be between 0.0 and 1.0")
        if not (0.0 <= self.priority_threshold <= 1.0):
            errors.append("priority_threshold must be between 0.0 and 1.0")

        # Threshold ordering
        if self.log_threshold < self.fetch_threshold:
            errors.append("log_threshold must be >= fetch_threshold")
        if self.digest_threshold < self.log_threshold:
            errors.append("digest_threshold must be >= log_threshold")
        if self.priority_threshold < self.digest_threshold:
            errors.append("priority_threshold must be >= digest_threshold")

        # Geographic layer validation
        if self.geographic:
            systems = self.geographic.get("systems", [])
            valid_classifications = {"home", "hunting", "transit"}
            for i, sys_config in enumerate(systems):
                if not isinstance(sys_config, dict):
                    errors.append(f"geographic.systems[{i}] must be a dict")
                    continue
                if "name" not in sys_config:
                    errors.append(f"geographic.systems[{i}] missing 'name'")
                classification = sys_config.get("classification", "home")
                if classification not in valid_classifications:
                    errors.append(
                        f"geographic.systems[{i}] invalid classification: {classification}"
                    )

        # Route validation
        for i, route in enumerate(self.routes):
            if not isinstance(route, dict):
                errors.append(f"routes[{i}] must be a dict")
                continue
            waypoints = route.get("waypoints", [])
            if len(waypoints) < 2:
                errors.append(f"routes[{i}] must have at least 2 waypoints")

        return errors

    @property
    def has_geographic(self) -> bool:
        """Check if geographic layer is configured."""
        return bool(self.geographic.get("systems"))

    @property
    def has_entity(self) -> bool:
        """Check if entity layer is configured."""
        return bool(
            self.entity.get("corp_id")
            or self.entity.get("alliance_id")
            or self.entity.get("watched_corps")
            or self.entity.get("watched_alliances")
        )

    @property
    def has_routes(self) -> bool:
        """Check if route layer is configured."""
        return bool(self.routes)

    @property
    def has_assets(self) -> bool:
        """Check if asset layer is configured."""
        return self.assets.get("structures", False) or self.assets.get("offices", False)

    @property
    def has_patterns(self) -> bool:
        """Check if pattern layer is configured."""
        return self.patterns.get("gatecamp_detection", False) or self.patterns.get(
            "spike_detection", False
        )

    def _to_mergeable_dict(self) -> dict[str, Any]:
        """
        Convert config to dict format suitable for preset merging.

        Includes all values that were explicitly set by the user, even if
        they match defaults. This ensures user intent is preserved when
        merging with archetype presets.
        """
        result: dict[str, Any] = {}

        # Layer configs: include if non-empty OR explicitly set by user
        # The explicit check allows user to clear a preset's value with empty
        if self.geographic or "geographic" in self._explicit_keys:
            result["geographic"] = self.geographic
        if self.entity or "entity" in self._explicit_keys:
            result["entity"] = self.entity
        if self.routes or "routes" in self._explicit_keys:
            result["routes"] = self.routes
        if self.assets or "assets" in self._explicit_keys:
            result["assets"] = self.assets
        if self.patterns or "patterns" in self._explicit_keys:
            result["patterns"] = self.patterns

        # Thresholds: include if non-default OR explicitly set by user
        # This allows user to explicitly set default value to override preset
        if self.fetch_threshold != FETCH_THRESHOLD or "fetch_threshold" in self._explicit_keys:
            result["fetch_threshold"] = self.fetch_threshold
        if self.log_threshold != LOG_THRESHOLD or "log_threshold" in self._explicit_keys:
            result["log_threshold"] = self.log_threshold
        if self.digest_threshold != DIGEST_THRESHOLD or "digest_threshold" in self._explicit_keys:
            result["digest_threshold"] = self.digest_threshold
        if (
            self.priority_threshold != PRIORITY_THRESHOLD
            or "priority_threshold" in self._explicit_keys
        ):
            result["priority_threshold"] = self.priority_threshold
        return result

    @classmethod
    def _from_merged(
        cls, merged: dict[str, Any], enabled: bool, archetype: str | None
    ) -> ContextAwareTopologyConfig:
        """Create new config from merged preset dict."""
        return cls(
            enabled=enabled,
            archetype=archetype,
            geographic=merged.get("geographic", {}),
            entity=merged.get("entity", {}),
            routes=merged.get("routes", []),
            assets=merged.get("assets", {}),
            patterns=merged.get("patterns", {}),
            fetch_threshold=merged.get("fetch_threshold", FETCH_THRESHOLD),
            log_threshold=merged.get("log_threshold", LOG_THRESHOLD),
            digest_threshold=merged.get("digest_threshold", DIGEST_THRESHOLD),
            priority_threshold=merged.get("priority_threshold", PRIORITY_THRESHOLD),
        )

    def build_calculator(
        self,
        graph: UniverseGraph | None = None,
    ) -> InterestCalculator:
        """
        Build an InterestCalculator from this configuration.

        Args:
            graph: UniverseGraph for geographic/route layers (loaded if None)

        Returns:
            Configured InterestCalculator
        """
        from .calculator import InterestCalculator
        from .layers import (
            AssetConfig,
            AssetLayer,
            EntityConfig,
            EntityLayer,
            GeographicConfig,
            GeographicLayer,
            PatternConfig,
            PatternLayer,
            RouteConfig,
            RouteDefinition,
            RouteLayer,
        )
        from .presets import apply_preset, get_preset

        # Apply archetype preset if configured
        effective_config = self
        if self.archetype:
            if get_preset(self.archetype):
                merged = apply_preset(self._to_mergeable_dict(), self.archetype)
                effective_config = self._from_merged(merged, self.enabled, self.archetype)
                logger.info("Applied archetype preset: %s", self.archetype)
            else:
                logger.warning("Unknown archetype '%s', ignoring", self.archetype)

        layers: list[InterestLayer] = []

        # Load graph if needed for geographic or route layers
        if graph is None and (effective_config.has_geographic or effective_config.has_routes):
            from ....universe import load_universe_graph

            graph = load_universe_graph()

        # Geographic layer
        if effective_config.has_geographic and graph is not None:
            geo_config = GeographicConfig.from_dict(effective_config.geographic)
            geo_layer = GeographicLayer.from_config(geo_config, graph)
            layers.append(geo_layer)
            logger.debug("Geographic layer: %d systems tracked", geo_layer.total_systems)

        # Entity layer
        if effective_config.has_entity:
            entity_config = EntityConfig.from_dict(effective_config.entity)
            entity_layer = EntityLayer.from_config(entity_config)
            layers.append(entity_layer)
            logger.debug("Entity layer configured")

        # Route layer
        if effective_config.has_routes and graph is not None:
            route_defs = [RouteDefinition.from_dict(r) for r in effective_config.routes]
            route_config = RouteConfig(routes=route_defs)
            route_layer = RouteLayer.from_config(route_config, graph)
            layers.append(route_layer)
            logger.debug(
                "Route layer: %d systems on %d routes",
                route_layer.total_systems,
                len(effective_config.routes),
            )

        # Asset layer
        if effective_config.has_assets:
            asset_config = AssetConfig.from_dict(effective_config.assets)
            asset_layer = AssetLayer.from_config(asset_config)
            layers.append(asset_layer)
            logger.debug("Asset layer configured")

        # Create calculator
        calculator = InterestCalculator(
            layers=layers,
            fetch_threshold=effective_config.fetch_threshold,
        )

        # Pattern layer (added separately as escalation)
        if effective_config.has_patterns:
            pattern_config = PatternConfig.from_dict(effective_config.patterns)
            pattern_layer = PatternLayer.from_config(pattern_config)
            calculator.set_pattern_layer(pattern_layer)
            logger.debug("Pattern layer configured")

        return calculator

    @classmethod
    def load(cls, config_path: Path | None = None) -> ContextAwareTopologyConfig:
        """
        Load context-aware topology configuration from userdata/config.json.

        Args:
            config_path: Optional path override (defaults to userdata/config.json)

        Returns:
            ContextAwareTopologyConfig instance (disabled if not configured)
        """
        if config_path is None:
            config_path = Path("userdata/config.json")

        if not config_path.exists():
            return cls()

        try:
            with open(config_path) as f:
                config = json.load(f)
            context_topology = config.get("redisq", {}).get("context_topology", {})
            return cls.from_dict(context_topology)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load context_topology config: %s", e)
            return cls()


# =============================================================================
# Migration Helpers
# =============================================================================


def migrate_legacy_config(
    legacy_topology: dict[str, Any],
) -> ContextAwareTopologyConfig:
    """
    Migrate legacy topology config to context-aware format.

    Legacy format:
    {
        "enabled": true,
        "operational_systems": ["Tama", "Sujarento"],
        "interest_weights": {"operational": 1.0, "hop_1": 1.0, "hop_2": 0.7}
    }

    New format:
    {
        "enabled": true,
        "geographic": {
            "systems": [
                {"name": "Tama", "classification": "home"},
                {"name": "Sujarento", "classification": "home"}
            ],
            "home_weights": {0: 1.0, 1: 1.0, 2: 0.7}
        }
    }

    Args:
        legacy_topology: Legacy topology configuration dict

    Returns:
        ContextAwareTopologyConfig with migrated settings
    """
    if not legacy_topology:
        return ContextAwareTopologyConfig()

    enabled = legacy_topology.get("enabled", False)
    operational_systems = legacy_topology.get("operational_systems", [])
    interest_weights = legacy_topology.get("interest_weights", {})

    # Convert operational systems to geographic config
    systems = [{"name": name, "classification": "home"} for name in operational_systems]

    # Convert interest weights to home weights
    home_weights = {
        0: interest_weights.get("operational", 1.0),
        1: interest_weights.get("hop_1", 1.0),
        2: interest_weights.get("hop_2", 0.7),
    }

    geographic = {
        "systems": systems,
        "home_weights": home_weights,
    }

    return ContextAwareTopologyConfig(
        enabled=enabled,
        geographic=geographic,
    )
