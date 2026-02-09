"""
Migration Tool for Interest Engine v2.

Converts v1 notification profile configurations to v2 format.

Migration strategies:
- preserve-triggers: Maintain v1 trigger behavior using always_notify rules
- weighted-only: Convert to weighted scoring without trigger preservation
- hybrid: Combine weighted scoring with trigger preservation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MigrationStrategy(str, Enum):
    """Migration strategy for v1 to v2 conversion."""

    PRESERVE_TRIGGERS = "preserve-triggers"
    WEIGHTED_ONLY = "weighted-only"
    HYBRID = "hybrid"


@dataclass
class MigrationResult:
    """Result of profile migration."""

    success: bool
    profile_name: str
    strategy: MigrationStrategy
    interest_config: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    changes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "profile_name": self.profile_name,
            "strategy": self.strategy.value,
            "interest": self.interest_config,
            "warnings": self.warnings,
            "changes": self.changes,
        }


def migrate_profile(
    profile: dict[str, Any],
    strategy: MigrationStrategy = MigrationStrategy.HYBRID,
    preset: str | None = None,
) -> MigrationResult:
    """
    Migrate a v1 profile to v2 interest configuration.

    Args:
        profile: Full profile dictionary (from YAML)
        strategy: Migration strategy to use
        preset: Override preset (default: auto-detect from topology)

    Returns:
        MigrationResult with new interest config
    """
    profile_name = profile.get("name", "unknown")
    warnings: list[str] = []
    changes: list[str] = []

    # Extract v1 components
    topology = profile.get("topology", {})
    triggers = profile.get("triggers", {})

    # Auto-detect preset from topology if not specified
    if preset is None:
        preset = _detect_preset(topology, triggers)
        if preset:
            changes.append(f"Auto-detected preset: {preset}")

    # Build base interest config
    interest_config: dict[str, Any] = {
        "engine": "v2",
    }

    if preset:
        interest_config["preset"] = preset

    # Apply strategy-specific migration
    if strategy == MigrationStrategy.PRESERVE_TRIGGERS:
        _migrate_preserve_triggers(interest_config, triggers, changes, warnings)
    elif strategy == MigrationStrategy.WEIGHTED_ONLY:
        _migrate_weighted_only(interest_config, topology, changes, warnings)
    elif strategy == MigrationStrategy.HYBRID:
        _migrate_hybrid(interest_config, topology, triggers, changes, warnings)

    # Migrate topology to signals.location if present
    if topology:
        _migrate_topology_to_signals(interest_config, topology, changes)

    return MigrationResult(
        success=True,
        profile_name=profile_name,
        strategy=strategy,
        interest_config=interest_config,
        warnings=warnings,
        changes=changes,
    )


def _detect_preset(topology: dict[str, Any], triggers: dict[str, Any]) -> str | None:
    """
    Auto-detect appropriate preset from v1 configuration.

    Returns:
        Preset name or None
    """
    # Check for trade hub indicators
    geographic = topology.get("geographic", {})
    systems = geographic.get("systems", [])

    trade_hub_systems = {"Jita", "Amarr", "Dodixie", "Rens", "Hek"}
    if any(s.get("name") in trade_hub_systems for s in systems):
        return "trade-hub"

    # Check for political indicators
    entity = topology.get("entity", {})
    if entity.get("alliances") or entity.get("corporations"):
        return "political"

    # Check trigger patterns
    if triggers.get("high_value_threshold", {}).get("enabled"):
        return "trade-hub"

    if triggers.get("watchlist_activity", {}).get("enabled"):
        return "political"

    # Check for routes
    routes = topology.get("routes", {})
    if routes.get("systems"):
        return "hunter"

    # Default to balanced
    return "balanced"


def _migrate_preserve_triggers(
    config: dict[str, Any],
    triggers: dict[str, Any],
    changes: list[str],
    warnings: list[str],
) -> None:
    """
    Migrate triggers to v2 rules with full preservation.

    Maps v1 triggers to v2 always_notify/always_ignore rules.
    """
    always_notify: list[str] = []
    always_ignore: list[str] = []
    signals: dict[str, Any] = {}

    # Watchlist activity -> watchlist_match rule
    if triggers.get("watchlist_activity", {}).get("enabled"):
        always_notify.append("watchlist_match")
        changes.append("watchlist_activity -> rules.always_notify: [watchlist_match]")

    # High value threshold -> high_value rule + signals.value.min
    high_value = triggers.get("high_value_threshold", {})
    if high_value.get("enabled"):
        always_notify.append("high_value")
        min_value = high_value.get("min_value", 1_000_000_000)
        signals["value"] = {"min": min_value}
        changes.append(f"high_value_threshold -> signals.value.min: {min_value}")

    # Gatecamp detected -> gatecamp_detected rule
    if triggers.get("gatecamp_detected", {}).get("enabled"):
        always_notify.append("gatecamp_detected")
        changes.append("gatecamp_detected -> rules.always_notify: [gatecamp_detected]")

    # NPC faction kill -> npc_only ignore rule (inverted logic)
    npc_kill = triggers.get("npc_faction_kill", {})
    if npc_kill.get("enabled"):
        # v1 NPC faction kill was a positive trigger
        # In v2, we use politics signal instead
        warnings.append("npc_faction_kill trigger migrated to politics signal; behavior may differ")

    # Pod kills - if not enabled, add to ignore
    pod_trigger = triggers.get("pod_kill", {})
    if not pod_trigger.get("enabled", True):
        always_ignore.append("pod_only")
        changes.append("pod_kill disabled -> rules.always_ignore: [pod_only]")

    # Build rules config
    if always_notify or always_ignore:
        config["rules"] = {}
        if always_notify:
            config["rules"]["always_notify"] = always_notify
        if always_ignore:
            config["rules"]["always_ignore"] = always_ignore

    if signals:
        config["signals"] = signals


def _migrate_weighted_only(
    config: dict[str, Any],
    topology: dict[str, Any],
    changes: list[str],
    warnings: list[str],
) -> None:
    """
    Migrate to pure weighted scoring without trigger preservation.

    Derives weights from topology configuration.
    """
    weights: dict[str, float] = {}

    # Geographic configuration -> location weight
    if topology.get("geographic"):
        weights["location"] = 0.8
        changes.append("geographic config -> weights.location: 0.8")

    # Routes configuration -> routes weight
    if topology.get("routes"):
        weights["routes"] = 0.6
        changes.append("routes config -> weights.routes: 0.6")

    # Entity configuration -> politics weight
    if topology.get("entity"):
        weights["politics"] = 0.7
        changes.append("entity config -> weights.politics: 0.7")

    # Default weights for unconfigured categories
    if "location" not in weights:
        weights["location"] = 0.5
    if "value" not in weights:
        weights["value"] = 0.5

    if weights:
        config["weights"] = weights

    warnings.append(
        "Weighted-only migration does not preserve trigger behavior; "
        "kills that previously triggered may now be filtered"
    )


def _migrate_hybrid(
    config: dict[str, Any],
    topology: dict[str, Any],
    triggers: dict[str, Any],
    changes: list[str],
    warnings: list[str],
) -> None:
    """
    Hybrid migration: weighted scoring with trigger preservation.

    Best of both worlds - weighted scoring for nuanced filtering,
    but critical triggers preserved as always_notify.
    """
    # First, apply weighted migration
    _migrate_weighted_only(config, topology, changes, warnings)

    # Remove the warning about not preserving triggers
    if warnings and "Weighted-only migration" in warnings[-1]:
        warnings.pop()

    # Then preserve critical triggers
    always_notify: list[str] = []

    # Preserve high-value as must-notify
    high_value = triggers.get("high_value_threshold", {})
    if high_value.get("enabled"):
        always_notify.append("high_value")
        min_value = high_value.get("min_value", 1_000_000_000)
        if "signals" not in config:
            config["signals"] = {}
        config["signals"]["value"] = {"min": min_value}
        changes.append(f"Preserved high_value trigger with min: {min_value}")

    # Preserve watchlist as must-notify
    if triggers.get("watchlist_activity", {}).get("enabled"):
        always_notify.append("watchlist_match")
        changes.append("Preserved watchlist_activity as always_notify")

    # Preserve gatecamp detection
    if triggers.get("gatecamp_detected", {}).get("enabled"):
        always_notify.append("gatecamp_detected")
        changes.append("Preserved gatecamp_detected as always_notify")

    if always_notify:
        if "rules" not in config:
            config["rules"] = {}
        config["rules"]["always_notify"] = always_notify


def _migrate_topology_to_signals(
    config: dict[str, Any],
    topology: dict[str, Any],
    changes: list[str],
) -> None:
    """
    Migrate topology geographic config to signals.location.
    """
    geographic = topology.get("geographic", {})
    if not geographic:
        return

    systems = geographic.get("systems", [])
    if not systems:
        return

    if "signals" not in config:
        config["signals"] = {}

    if "location" not in config["signals"]:
        config["signals"]["location"] = {}

    # Convert systems to geographic signal format
    location_config = config["signals"]["location"]
    if "geographic" not in location_config:
        location_config["geographic"] = {}

    geo_signal = location_config["geographic"]

    # Convert system list
    migrated_systems = []
    for sys in systems:
        if isinstance(sys, dict):
            migrated_sys: dict[str, Any] = {"name": sys.get("name", "")}
            if sys.get("range"):
                migrated_sys["range"] = sys["range"]
            if sys.get("classification"):
                migrated_sys["classification"] = sys["classification"]
            migrated_systems.append(migrated_sys)

    if migrated_systems:
        geo_signal["systems"] = migrated_systems
        changes.append(f"Migrated {len(migrated_systems)} systems to signals.location.geographic")


def format_migration_diff(
    original: dict[str, Any],
    result: MigrationResult,
) -> str:
    """
    Format migration as human-readable diff.

    Args:
        original: Original profile dict
        result: Migration result

    Returns:
        Formatted diff string
    """
    lines = []

    lines.append(f"╔═══ Migration: {result.profile_name} ═══╗")
    lines.append(f"║ Strategy: {result.strategy.value}")
    lines.append("╚" + "═" * 40 + "╝")
    lines.append("")

    # Changes
    if result.changes:
        lines.append("📝 Changes:")
        for change in result.changes:
            lines.append(f"  • {change}")
        lines.append("")

    # Warnings
    if result.warnings:
        lines.append("⚠️  Warnings:")
        for warning in result.warnings:
            lines.append(f"  • {warning}")
        lines.append("")

    # New interest config
    lines.append("📋 New interest configuration:")
    lines.append("─" * 40)

    import json

    config_str = json.dumps(result.interest_config, indent=2)
    for line in config_str.split("\n"):
        lines.append(f"  {line}")

    return "\n".join(lines)


def validate_migration(result: MigrationResult) -> list[str]:
    """
    Validate migrated configuration.

    Args:
        result: Migration result to validate

    Returns:
        List of validation errors (empty if valid)
    """
    from ..validation import validate_interest_config

    validation = validate_interest_config(result.interest_config)
    return validation.error_messages
