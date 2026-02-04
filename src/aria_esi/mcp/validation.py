"""
Parameter validation for MCP dispatchers.

Validates that only relevant parameters are passed for each action,
preventing LLM parameter hallucination and cross-action bleeding.

Issue: Gemini 3 Pro MCP Integration Review - Dispatcher Argument Complexity
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# Universe Dispatcher Parameter Schema
# =============================================================================

UNIVERSE_ACTION_PARAMS: dict[str, set[str]] = {
    "route": {"origin", "destination", "mode", "avoid_systems"},
    "systems": {"systems"},
    "borders": {"origin", "limit", "max_jumps"},
    "search": {
        "origin",
        "max_jumps",
        "security_min",
        "security_max",
        "region",
        "is_border",
        "limit",
    },
    "loop": {
        "origin",
        "target_jumps",
        "min_borders",
        "max_borders",
        "optimize",
        "security_filter",
        "avoid_systems",
    },
    "analyze": {"systems"},
    "nearest": {
        "origin",
        "is_border",
        "min_adjacent_lowsec",
        "security_min",
        "security_max",
        "region",
        "limit",
        "max_jumps",
    },
    "optimize_waypoints": {
        "waypoints",
        "origin",
        "return_to_origin",
        "security_filter",
        "avoid_systems",
    },
    "activity": {"systems", "include_realtime"},
    "hotspots": {
        "origin",
        "max_jumps",
        "activity_type",
        "security_min",
        "security_max",
        "limit",
    },
    "gatecamp_risk": {"route", "origin", "destination", "mode"},
    "fw_frontlines": {"faction"},
    "local_area": {
        "origin",
        "max_jumps",
        "include_realtime",
        "hotspot_threshold",
        "quiet_threshold",
        "ratting_threshold",
    },
}


# =============================================================================
# Market Dispatcher Parameter Schema
# =============================================================================

MARKET_ACTION_PARAMS: dict[str, set[str]] = {
    "prices": {"items", "region", "station_only"},
    "orders": {"item", "region", "region_id", "order_type", "limit"},
    "valuation": {"items", "price_type", "region"},
    "spread": {"items", "regions"},
    "history": {"item", "region", "days"},
    "find_nearby": {
        "item",
        "origin",
        "max_jumps",
        "order_type",
        "source_filter",
        "expand_regions",
        "max_regions",
        "limit",
    },
    "npc_sources": {"item", "limit"},
    "arbitrage_scan": {
        "min_profit_pct",
        "min_volume",
        "max_results",
        "buy_from",
        "sell_to",
        "include_lowsec",
        "allow_stale",
        "force_refresh",
        "sort_by",
        "trade_mode",
        "broker_fee_pct",
        "sales_tax_pct",
        "include_history",
        "cargo_capacity_m3",
        "include_custom_scopes",
        "scopes",
        "scope_owner_id",
    },
    "arbitrage_detail": {"type_name", "buy_region", "sell_region"},
    "route_value": {"items", "route", "price_type"},
    "watchlist_create": {"name", "items", "owner_character_id"},
    "watchlist_add_item": {"watchlist_name", "item_name", "owner_character_id"},
    "watchlist_list": {"owner_character_id", "include_global"},
    "watchlist_get": {"name", "owner_character_id"},
    "watchlist_delete": {"name", "owner_character_id"},
    "scope_create": {
        "name",
        "scope_type",
        "location_id",
        "watchlist_name",
        "owner_character_id",
        "parent_region_id",
    },
    "scope_list": {"owner_character_id", "include_core", "include_global"},
    "scope_delete": {"name", "owner_character_id"},
    "scope_refresh": {
        "scope_name",
        "owner_character_id",
        "force_refresh",
        "max_structure_pages",
    },
}


# =============================================================================
# SDE Dispatcher Parameter Schema
# =============================================================================

SDE_ACTION_PARAMS: dict[str, set[str]] = {
    "item_info": {"item"},
    "blueprint_info": {"item"},
    "search": {"query", "category", "limit"},
    "skill_requirements": {"item", "include_prerequisites"},
    "corporation_info": {"corporation_id", "corporation_name"},
    "agent_search": {
        "corporation",
        "corporation_id",
        "level",
        "division",
        "system",
        "highsec_only",
        "limit",
    },
    "agent_divisions": set(),
    "cache_status": set(),
}


# =============================================================================
# Skills Dispatcher Parameter Schema
# =============================================================================

SKILLS_ACTION_PARAMS: dict[str, set[str]] = {
    "training_time": {"skill_list", "attributes"},
    "easy_80_plan": {"item", "current_skills", "attributes"},
    "get_multipliers": {"role"},
    "get_breakpoints": {"role", "category_filter"},
    "t2_requirements": {"item"},
    "activity_plan": {"activity", "tier", "parameters", "current_skills"},
    "activity_list": {"category_filter"},
    "activity_search": {"query"},
    "activity_compare": {"activity", "parameters", "current_skills"},
}


# =============================================================================
# Fitting Dispatcher Parameter Schema
# =============================================================================

FITTING_ACTION_PARAMS: dict[str, set[str]] = {
    "calculate_stats": {"eft", "damage_profile", "use_pilot_skills"},
    "check_requirements": {"eft", "pilot_skills"},
    "extract_requirements": {"eft"},
}


# =============================================================================
# Validation Functions
# =============================================================================


def get_default_values(dispatcher: str) -> dict[str, Any]:
    """Get default parameter values for a dispatcher to compare against."""
    if dispatcher == "universe":
        return {
            "mode": "shortest",
            "limit": 20,
            "target_jumps": 20,
            "min_borders": 4,
            "optimize": "density",
            "security_filter": "highsec",
            "return_to_origin": True,
            "activity_type": "kills",
            "include_realtime": False,
            "hotspot_threshold": 5,
            "quiet_threshold": 0,
            "ratting_threshold": 100,
        }
    elif dispatcher == "market":
        return {
            "region": "jita",
            "station_only": True,
            "order_type": "all",
            "limit": 10,
            "price_type": "sell",
            "days": 30,
            "max_jumps": 20,
            "source_filter": "all",
            "expand_regions": True,
            "max_regions": 5,
            "min_profit_pct": 5.0,
            "min_volume": 10,
            "max_results": 20,
            "include_lowsec": False,
            "allow_stale": False,
            "force_refresh": False,
            "sort_by": "margin",
            "trade_mode": "immediate",
            "broker_fee_pct": 0.03,
            "sales_tax_pct": 0.036,
            "include_history": False,
            "include_custom_scopes": False,
            "include_global": True,
            "include_core": True,
            "max_structure_pages": 5,
        }
    elif dispatcher == "sde":
        return {
            "limit": 10,
            "include_prerequisites": True,
            "highsec_only": False,
        }
    elif dispatcher == "skills":
        return {
            "tier": "easy_80",
        }
    elif dispatcher == "fitting":
        return {
            "use_pilot_skills": False,
        }
    return {}


def validate_action_params(
    dispatcher: str,
    action: str,
    provided_params: dict[str, Any],
    *,
    strict: bool = False,
) -> list[str]:
    """
    Validate that only relevant parameters are passed for an action.

    Args:
        dispatcher: Name of the dispatcher (universe, market, sde, skills, fitting)
        action: The action being invoked
        provided_params: Dict of all parameters provided by the caller
        strict: If True, raise an error. If False, return warnings (default).

    Returns:
        List of warning messages for irrelevant parameters.

    Raises:
        ValueError: If strict=True and irrelevant parameters are found.
    """
    # Get schema for this dispatcher
    schema_map = {
        "universe": UNIVERSE_ACTION_PARAMS,
        "market": MARKET_ACTION_PARAMS,
        "sde": SDE_ACTION_PARAMS,
        "skills": SKILLS_ACTION_PARAMS,
        "fitting": FITTING_ACTION_PARAMS,
    }

    schema = schema_map.get(dispatcher)
    if schema is None:
        logger.warning("Unknown dispatcher for validation: %s", dispatcher)
        return []

    valid_params = schema.get(action)
    if valid_params is None:
        # Unknown action - let the dispatcher handle the error
        return []

    # Get default values to filter out
    defaults = get_default_values(dispatcher)

    # Find parameters that were explicitly set (non-None and non-default)
    irrelevant: list[str] = []
    for param, value in provided_params.items():
        # Skip if param is valid for this action
        if param in valid_params:
            continue

        # Skip if value is None (not provided)
        if value is None:
            continue

        # Skip if value equals the default (not explicitly changed)
        if param in defaults and value == defaults[param]:
            continue

        # This is an irrelevant parameter that was explicitly set
        irrelevant.append(param)

    if not irrelevant:
        return []

    # Build warning message
    warnings = []
    for param in irrelevant:
        msg = (
            f"Parameter '{param}' is not used by action '{action}'. "
            f"Valid parameters for '{action}': {', '.join(sorted(valid_params)) or '(none)'}"
        )
        warnings.append(msg)
        logger.warning("[%s.%s] %s", dispatcher, action, msg)

    if strict and irrelevant:
        from .errors import InvalidParameterError

        raise InvalidParameterError(
            "parameters",
            irrelevant,
            f"Parameters not applicable to action '{action}': {', '.join(irrelevant)}",
        )

    return warnings


def add_validation_warnings(result: dict, warnings: list[str]) -> dict:
    """
    Add validation warnings to a result dict.

    Args:
        result: The result dictionary from an action
        warnings: List of validation warning messages

    Returns:
        Modified result dict with warnings added
    """
    if not warnings:
        return result

    existing_warnings = result.get("warnings", [])
    if isinstance(existing_warnings, list):
        result["warnings"] = existing_warnings + warnings
    else:
        result["warnings"] = warnings

    return result
