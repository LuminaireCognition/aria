"""
Archetype Presets for Context-Aware Topology.

Provides pre-configured layer settings for common EVE Online playstyles.
"""

from __future__ import annotations

from typing import Any

# =============================================================================
# Archetype Presets
# =============================================================================

ARCHETYPE_PRESETS: dict[str, dict[str, Any]] = {
    "hunter": {
        "description": "FW/piracy focused - prioritizes kill activity and gatecamps",
        "geographic": {
            "systems": [],  # User must configure
            "home_weights": {0: 1.0, 1: 0.95, 2: 0.8, 3: 0.5},
            "hunting_weights": {0: 1.0, 1: 0.85, 2: 0.5},
            "transit_weights": {0: 0.7, 1: 0.3},
        },
        "entity": {
            "corp_member_victim": 1.0,
            "corp_member_attacker": 0.9,
            "alliance_member_victim": 0.8,
            "alliance_member_attacker": 0.7,
            "war_target": 0.95,
            "watchlist_entity": 0.9,
        },
        "patterns": {
            "gatecamp_detection": True,
            "spike_detection": True,
            "gatecamp_multiplier": 1.5,
            "spike_multiplier": 1.3,
        },
        "fetch_threshold": 0.0,
        "log_threshold": 0.3,
        "digest_threshold": 0.5,
        "priority_threshold": 0.8,
    },
    "industrial": {
        "description": "Trade/industry focused - prioritizes logistics routes and asset protection",
        "geographic": {
            "systems": [],  # User must configure
            "home_weights": {0: 1.0, 1: 0.9, 2: 0.7},
            "hunting_weights": {0: 0.8, 1: 0.6},
            "transit_weights": {0: 0.6, 1: 0.3},
        },
        "entity": {
            "corp_member_victim": 1.0,
            "corp_member_attacker": 0.7,
            "alliance_member_victim": 0.8,
            "alliance_member_attacker": 0.5,
            "war_target": 0.9,
            "watchlist_entity": 0.8,
        },
        "routes": [],  # User configures logistics routes
        "assets": {
            "structures": True,
            "offices": True,
            "structure_interest": 1.0,
            "office_interest": 0.8,
        },
        "patterns": {
            "gatecamp_detection": True,
            "spike_detection": False,  # Less interested in activity spikes
            "gatecamp_multiplier": 1.5,
        },
        "fetch_threshold": 0.0,
        "log_threshold": 0.4,
        "digest_threshold": 0.6,
        "priority_threshold": 0.85,
    },
    "sovereignty": {
        "description": "Null-sec focused - prioritizes territory and strategic assets",
        "geographic": {
            "systems": [],  # User must configure
            "home_weights": {0: 1.0, 1: 1.0, 2: 0.9, 3: 0.7},
            "hunting_weights": {0: 1.0, 1: 0.9, 2: 0.7},
            "transit_weights": {0: 0.8, 1: 0.5},
        },
        "entity": {
            "corp_member_victim": 1.0,
            "corp_member_attacker": 0.9,
            "alliance_member_victim": 0.95,
            "alliance_member_attacker": 0.85,
            "war_target": 0.95,
            "watchlist_entity": 0.9,
        },
        "assets": {
            "structures": True,
            "offices": True,
            "structure_interest": 1.0,
            "office_interest": 0.9,
        },
        "patterns": {
            "gatecamp_detection": True,
            "spike_detection": True,
            "gatecamp_multiplier": 1.4,
            "spike_multiplier": 1.5,  # Spikes more significant in null
        },
        "fetch_threshold": 0.0,
        "log_threshold": 0.3,
        "digest_threshold": 0.5,
        "priority_threshold": 0.75,  # Lower threshold - more things matter
    },
    "wormhole": {
        "description": "W-space focused - entity-centric, no fixed geography",
        "geographic": {
            "systems": [],  # W-space is dynamic
            "home_weights": {0: 1.0},  # Only direct connections matter
            "hunting_weights": {0: 0.9},
            "transit_weights": {0: 0.7},
        },
        "entity": {
            "corp_member_victim": 1.0,
            "corp_member_attacker": 1.0,  # Everyone matters in small corps
            "alliance_member_victim": 0.9,
            "alliance_member_attacker": 0.85,
            "war_target": 0.95,
            "watchlist_entity": 0.95,  # Watchlist very important
        },
        "patterns": {
            "gatecamp_detection": False,  # No gates in wormholes
            "spike_detection": True,
            "spike_multiplier": 1.4,
        },
        "fetch_threshold": 0.0,
        "log_threshold": 0.2,  # Lower threshold - less noise in w-space
        "digest_threshold": 0.5,
        "priority_threshold": 0.8,
    },
    "mission_runner": {
        "description": "PvE mission focused - minimal interest in PvP activity",
        "geographic": {
            "systems": [],  # User must configure mission hubs
            "home_weights": {0: 1.0, 1: 0.7},
            "hunting_weights": {0: 0.6},
            "transit_weights": {0: 0.4},
        },
        "entity": {
            "corp_member_victim": 1.0,
            "corp_member_attacker": 0.5,  # Less interested in corp kills
            "alliance_member_victim": 0.7,
            "alliance_member_attacker": 0.4,
            "war_target": 0.9,
            "watchlist_entity": 0.7,
        },
        "patterns": {
            "gatecamp_detection": True,  # Safety matters
            "spike_detection": False,
            "gatecamp_multiplier": 1.5,
        },
        "fetch_threshold": 0.3,  # Filter more aggressively
        "log_threshold": 0.5,
        "digest_threshold": 0.7,
        "priority_threshold": 0.9,  # Only alert for serious things
    },
}


def get_preset(archetype: str) -> dict[str, Any] | None:
    """
    Get configuration preset for an archetype.

    Args:
        archetype: Archetype name (hunter, industrial, sovereignty, wormhole, mission_runner)

    Returns:
        Preset configuration dict or None if not found
    """
    return ARCHETYPE_PRESETS.get(archetype.lower())


def list_presets() -> list[tuple[str, str]]:
    """
    List available presets with descriptions.

    Returns:
        List of (name, description) tuples
    """
    return [(name, preset["description"]) for name, preset in ARCHETYPE_PRESETS.items()]


def apply_preset(
    base_config: dict[str, Any],
    archetype: str,
) -> dict[str, Any]:
    """
    Apply an archetype preset to a base configuration.

    The preset provides defaults, but user config takes precedence.
    User-provided values always win, including:
    - Empty lists (to clear preset's list values)
    - Empty dicts (to clear preset's dict values)
    - Values matching defaults (user explicitly chose that value)

    Args:
        base_config: User's configuration (only includes explicitly-set fields)
        archetype: Archetype to apply

    Returns:
        Merged configuration
    """
    preset = get_preset(archetype)
    if not preset:
        return base_config

    result: dict = {}

    # Start with preset values
    for key, value in preset.items():
        if key == "description":
            continue
        if isinstance(value, dict):
            result[key] = value.copy()
        elif isinstance(value, list):
            result[key] = list(value)
        else:
            result[key] = value

    # Override with user config - user values always take precedence
    for key, value in base_config.items():
        if key == "archetype":
            continue
        if isinstance(value, dict) and key in result and isinstance(result[key], dict):
            # For dicts: if user provides empty dict, clear the preset's dict
            # Otherwise merge user values into preset
            if not value:
                result[key] = {}
            else:
                result[key].update(value)
        elif isinstance(value, list):
            # For lists: user's list always wins (including empty lists)
            # This allows user to explicitly clear a preset's list
            result[key] = list(value)
        elif value is not None:
            result[key] = value

    return result
