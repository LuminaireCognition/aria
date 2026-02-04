"""
Built-in Presets for Interest Engine v2.

Provides 6 presets with complete weight baselines optimized for
different playstyles. Each preset configures all 9 canonical categories.

Presets:
- trade-hub: Trade hub activity monitoring
- political: Alliance/coalition warfare intel
- industrial: Industrial operations protection
- hunter: Roaming PvP hunting grounds
- sovereignty: Sov warfare and structure operations
- wormhole: Wormhole space operations
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PresetDefinition:
    """Complete preset definition."""

    name: str
    description: str
    weights: dict[str, float]
    signals: dict[str, Any] = field(default_factory=dict)
    rules: dict[str, Any] = field(default_factory=dict)
    thresholds: dict[str, float] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for config merging."""
        result: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "weights": dict(self.weights),
        }
        if self.signals:
            result["signals"] = self.signals
        if self.rules:
            result["rules"] = self.rules
        if self.thresholds:
            result["thresholds"] = self.thresholds
        return result


# =============================================================================
# Built-in Preset Definitions
# =============================================================================

TRADE_HUB = PresetDefinition(
    name="trade-hub",
    description="Trade hub activity monitoring - high-value targets near market hubs",
    weights={
        "location": 0.8,
        "value": 0.7,
        "politics": 0.1,
        "activity": 0.2,
        "time": 0.0,
        "routes": 0.3,
        "assets": 0.1,
        "war": 0.0,
        "ship": 0.3,
    },
    signals={
        "location": {
            "geographic": {
                "home_weight": 0.8,
                "trade_hub_weight": 1.0,
            },
        },
        "ship": {
            "prefer": ["freighter", "jump_freighter", "dst", "blockade_runner"],
        },
    },
    rules={
        "always_notify": ["high_value"],
    },
)

POLITICAL = PresetDefinition(
    name="political",
    description="Alliance/coalition warfare intel - enemy/friendly activity",
    weights={
        "location": 0.1,
        "value": 0.1,
        "politics": 1.0,
        "activity": 0.1,
        "time": 0.0,
        "routes": 0.0,
        "assets": 0.0,
        "war": 0.3,
        "ship": 0.0,
    },
    signals={
        "politics": {
            "require_any": ["enemies", "friendlies"],
        },
    },
    rules={
        "always_notify": ["war_target_activity"],
    },
)

INDUSTRIAL = PresetDefinition(
    name="industrial",
    description="Industrial operations protection - mining and hauling safety",
    weights={
        "location": 0.5,
        "value": 0.6,
        "politics": 0.1,
        "activity": 0.3,
        "time": 0.0,
        "routes": 0.4,
        "assets": 0.3,
        "war": 0.0,
        "ship": 0.8,
    },
    signals={
        "ship": {
            "prefer": [
                "freighter",
                "orca",
                "rorqual",
                "mining_barge",
                "exhumer",
                "industrial",
            ],
            "exclude": ["capsule"],
        },
        "activity": {
            "prefer_quiet": True,
        },
    },
    rules={
        "always_ignore": ["pod_only", "npc_only"],
    },
)

HUNTER = PresetDefinition(
    name="hunter",
    description="Roaming PvP hunting grounds - find active areas and targets",
    weights={
        "location": 0.6,
        "value": 0.2,
        "politics": 0.1,
        "activity": 0.8,
        "time": 0.3,
        "routes": 0.5,
        "assets": 0.0,
        "war": 0.0,
        "ship": 0.2,
    },
    signals={
        "activity": {
            "min_kills_hour": 3,
            "prefer_active": True,
        },
    },
    rules={
        "always_ignore": ["npc_only"],
    },
)

SOVEREIGNTY = PresetDefinition(
    name="sovereignty",
    description="Sov warfare and structure operations - entosis and structure kills",
    weights={
        "location": 0.4,
        "value": 0.3,
        "politics": 0.7,
        "activity": 0.4,
        "time": 0.0,
        "routes": 0.2,
        "assets": 0.6,
        "war": 0.9,
        "ship": 0.3,
    },
    signals={
        "ship": {
            "prefer": ["carrier", "supercarrier", "dreadnought", "titan", "fax"],
        },
    },
    rules={
        "always_notify": ["structure_kill", "war_target_activity"],
    },
)

WORMHOLE = PresetDefinition(
    name="wormhole",
    description="Wormhole space operations - chain mapping and local threats",
    weights={
        "location": 1.0,
        "value": 0.2,
        "politics": 0.2,
        "activity": 0.6,
        "time": 0.0,
        "routes": 0.0,  # No routes in wormhole space
        "assets": 0.3,
        "war": 0.0,
        "ship": 0.3,
    },
    signals={
        "location": {
            "security": {
                "prefer_wormhole": True,
            },
        },
        "activity": {
            "prefer_active": True,
        },
    },
    rules={
        "always_ignore": ["npc_only"],
    },
)

BALANCED = PresetDefinition(
    name="balanced",
    description="Balanced preset - moderate weights across all categories",
    weights={
        "location": 0.5,
        "value": 0.5,
        "politics": 0.5,
        "activity": 0.5,
        "time": 0.0,
        "routes": 0.3,
        "assets": 0.3,
        "war": 0.3,
        "ship": 0.3,
    },
)

# =============================================================================
# Preset Registry
# =============================================================================

BUILTIN_PRESETS: dict[str, PresetDefinition] = {
    "trade-hub": TRADE_HUB,
    "political": POLITICAL,
    "industrial": INDUSTRIAL,
    "hunter": HUNTER,
    "sovereignty": SOVEREIGNTY,
    "wormhole": WORMHOLE,
    "balanced": BALANCED,
}


def get_builtin_preset(name: str) -> PresetDefinition | None:
    """
    Get a built-in preset by name.

    Args:
        name: Preset name (case-insensitive)

    Returns:
        PresetDefinition or None if not found
    """
    return BUILTIN_PRESETS.get(name.lower())


def list_builtin_presets() -> list[str]:
    """List all built-in preset names."""
    return list(BUILTIN_PRESETS.keys())
