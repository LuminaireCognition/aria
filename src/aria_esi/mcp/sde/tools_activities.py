"""
Activity Skill Planning MCP Tools.

Provides skill requirement lookups for common EVE Online activities
like mining, exploration, missions, and industry.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from aria_esi.core.logging import get_logger

from .tools_skills import (
    DEFAULT_ATTRIBUTES,
    calculate_sp_for_level,
    calculate_sp_per_minute,
    format_training_time,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = get_logger("aria_sde.tools_activities")

# =============================================================================
# Constants
# =============================================================================

# Path to activity definitions (relative to project root)
ACTIVITIES_FILE = Path("reference/activities/skill_plans.yaml")

# Cache structure: (data, mtime) tuple for automatic invalidation on file change
_activities_cache: tuple[dict[str, Any], float] | None = None


def reset_activities_cache() -> None:
    """
    Reset the activities cache.

    Use for testing or to force reload of the activities YAML file.
    """
    global _activities_cache
    _activities_cache = None


def _is_activities_cache_stale() -> bool:
    """
    Check if the activities cache is stale based on file modification time.

    Returns:
        True if cache is None or file has been modified since caching
    """
    if _activities_cache is None:
        return True

    project_root = _get_project_root()
    activities_path = project_root / ACTIVITIES_FILE

    if not activities_path.exists():
        return True

    cached_mtime = _activities_cache[1]
    current_mtime = activities_path.stat().st_mtime
    return current_mtime > cached_mtime


# =============================================================================
# Activity Loading
# =============================================================================


def _get_project_root() -> Path:
    """Find project root by looking for pyproject.toml."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return Path.cwd()


def load_activities() -> dict[str, Any]:
    """
    Load activity definitions from YAML file.

    Automatically reloads if the file has been modified since caching.

    Returns:
        Dictionary of activity_id -> activity definition
    """
    global _activities_cache

    if not _is_activities_cache_stale():
        return _activities_cache[0]

    project_root = _get_project_root()
    activities_path = project_root / ACTIVITIES_FILE

    if not activities_path.exists():
        logger.warning(f"Activities file not found: {activities_path}")
        return {}

    with open(activities_path) as f:
        data = yaml.safe_load(f) or {}

    _activities_cache = (data, activities_path.stat().st_mtime)
    return data


def get_activity(activity_id: str) -> dict[str, Any] | None:
    """
    Get a specific activity by ID.

    Args:
        activity_id: Activity identifier (e.g., "gas_huffing")

    Returns:
        Activity definition or None if not found
    """
    activities = load_activities()
    return activities.get(activity_id)


def search_activities(query: str) -> list[dict[str, Any]]:
    """
    Search activities by name, category, or description.

    Args:
        query: Search term (case-insensitive)

    Returns:
        List of matching activities with their IDs
    """
    activities = load_activities()
    query_lower = query.lower()
    results = []

    for activity_id, activity in activities.items():
        # Search in display_name, category, and description
        display_name = activity.get("display_name", "").lower()
        category = activity.get("category", "").lower()
        description = activity.get("description", "").lower()

        if (
            query_lower in activity_id.lower()
            or query_lower in display_name
            or query_lower in category
            or query_lower in description
        ):
            results.append(
                {
                    "activity_id": activity_id,
                    **activity,
                }
            )

    return results


def resolve_parameters(
    skills: list[dict[str, Any]],
    parameters: dict[str, str],
) -> list[dict[str, Any]]:
    """
    Resolve parameterized skill references.

    Replaces ${param} placeholders with actual values.

    Args:
        skills: List of skill definitions
        parameters: Parameter values {"field": "Mechanical Engineering"}

    Returns:
        Skills with parameters resolved
    """
    resolved = []
    for skill in skills:
        skill_copy = skill.copy()
        skill_name = skill_copy.get("skill", "")

        # Check for parameter placeholder
        match = re.match(r"\$\{(\w+)\}", skill_name)
        if match:
            param_name = match.group(1)
            if param_name in parameters:
                skill_copy["skill"] = parameters[param_name]
            else:
                # Parameter not provided, skip or mark as required
                skill_copy["skill"] = f"[{param_name} - parameter required]"
                skill_copy["parameter_required"] = param_name

        resolved.append(skill_copy)

    return resolved


def calculate_activity_training_time(
    skills: list[dict[str, Any]],
    current_skills: dict[str, int] | None = None,
    attributes: dict[str, int] | None = None,
) -> dict[str, Any]:
    """
    Calculate training time for an activity's skill list.

    Args:
        skills: List of skill requirements
        current_skills: Current skill levels (default: all 0)
        attributes: Character attributes (default: balanced)

    Returns:
        Training time breakdown
    """
    from aria_esi.mcp.market.database import get_market_database

    from .queries import get_sde_query_service

    current = current_skills or {}
    attrs = attributes or DEFAULT_ATTRIBUTES

    db = get_market_database()
    conn = db._get_connection()
    query_service = get_sde_query_service()

    total_sp = 0
    total_seconds = 0
    skill_times = []
    warnings = []

    for skill_entry in skills:
        skill_name = skill_entry.get("skill", "")
        target_level = skill_entry.get("level", 1)

        # Skip parameterized skills that weren't resolved
        if skill_name.startswith("[") or skill_entry.get("parameter_required"):
            warnings.append(f"Parameter required for: {skill_entry.get('parameter_required')}")
            continue

        from_level = current.get(skill_name, 0)
        if from_level >= target_level:
            skill_times.append(
                {
                    "skill_name": skill_name,
                    "target_level": target_level,
                    "current_level": from_level,
                    "training_needed": False,
                    "training_formatted": "Already trained",
                }
            )
            continue

        # Look up skill in SDE
        cursor = conn.execute(
            """
            SELECT type_id FROM types
            WHERE type_name_lower = ?
            AND category_id = 16
            LIMIT 1
            """,
            (skill_name.lower(),),
        )
        row = cursor.fetchone()
        if not row:
            warnings.append(f"Skill not found: {skill_name}")
            continue

        skill_id = row[0]
        skill_attrs = query_service.get_skill_attributes(skill_id)
        if not skill_attrs:
            warnings.append(f"No training data for: {skill_name}")
            continue

        rank = skill_attrs.rank

        # Calculate SP needed
        sp_at_from = calculate_sp_for_level(rank, from_level) if from_level > 0 else 0
        sp_at_to = calculate_sp_for_level(rank, target_level)
        sp_needed = sp_at_to - sp_at_from

        # Calculate training time
        sp_per_min = calculate_sp_per_minute(
            skill_attrs.primary_attribute,
            skill_attrs.secondary_attribute,
            attrs,
        )
        training_seconds = int(math.ceil((sp_needed / sp_per_min) * 60))

        total_sp += sp_needed
        total_seconds += training_seconds

        skill_times.append(
            {
                "skill_name": skill_name,
                "target_level": target_level,
                "current_level": from_level,
                "training_needed": True,
                "sp_needed": sp_needed,
                "training_seconds": training_seconds,
                "training_formatted": format_training_time(training_seconds),
                "note": skill_entry.get("note"),
            }
        )

    return {
        "skills": skill_times,
        "total_sp": total_sp,
        "total_seconds": total_seconds,
        "total_formatted": format_training_time(total_seconds),
        "warnings": warnings,
    }


# =============================================================================
# Standalone Implementation Functions (for dispatcher imports)
# =============================================================================


async def _activity_skill_plan_impl(
    activity: str,
    tier: str = "easy_80",
    parameters: dict | None = None,
    current_skills: dict | None = None,
) -> dict:
    """
    Get skill requirements for an EVE Online activity.

    Standalone implementation callable by both MCP tool and dispatcher.

    Args:
        activity: Activity name or ID (e.g., "gas huffing", "l3 missions")
        tier: Which tier to return ("minimum", "easy_80", "full", or "all")
        parameters: For parameterized activities
        current_skills: Current skill levels for time calculation

    Returns:
        Activity skill plan with training times
    """
    # Load activities
    activities = load_activities()

    # Normalize query
    query = activity.strip().lower()

    # Try exact match first
    activity_data = None
    activity_id = None

    for aid, data in activities.items():
        if aid.lower() == query or aid.lower().replace("_", " ") == query:
            activity_data = data
            activity_id = aid
            break

    # Try fuzzy search
    if not activity_data:
        matches = search_activities(query)
        if len(matches) == 1:
            activity_data = matches[0]
            activity_id = matches[0]["activity_id"]
        elif len(matches) > 1:
            return {
                "found": False,
                "error": f"Multiple activities match '{activity}'. Please be more specific.",
                "suggestions": [
                    {"id": m["activity_id"], "name": m.get("display_name")} for m in matches[:5]
                ],
            }

    if not activity_data:
        # Try word-based search
        words = query.split()
        for aid, data in activities.items():
            display_name = data.get("display_name", "").lower()
            if all(word in display_name or word in aid.lower() for word in words):
                activity_data = data
                activity_id = aid
                break

    if not activity_data:
        return {
            "found": False,
            "error": f"Activity '{activity}' not found.",
            "available_categories": list(
                set(a.get("category", "other") for a in activities.values())
            ),
        }

    # Check for required parameters
    param_defs = activity_data.get("parameters", [])
    params = parameters or {}

    missing_params = []
    for param_def in param_defs:
        param_name = param_def.get("name")
        if param_name and param_name not in params:
            # Use default if available
            if "default" in param_def:
                params[param_name] = param_def["default"]
            else:
                missing_params.append(
                    {
                        "name": param_name,
                        "type": param_def.get("type"),
                        "options": param_def.get("options"),
                    }
                )

    if missing_params:
        return {
            "found": True,
            "activity_id": activity_id,
            "display_name": activity_data.get("display_name"),
            "requires_parameters": True,
            "missing_parameters": missing_params,
            "hint": "Call again with parameters dict",
        }

    # Build response
    result = {
        "found": True,
        "activity_id": activity_id,
        "display_name": activity_data.get("display_name"),
        "category": activity_data.get("category"),
        "description": activity_data.get("description"),
        "ships": activity_data.get("ships"),
        "notes": activity_data.get("notes"),
    }

    # Get requested tiers
    tiers_to_include = ["minimum", "easy_80", "full"] if tier == "all" else [tier]

    for tier_name in tiers_to_include:
        skills = activity_data.get(tier_name, [])
        if skills:
            # Resolve parameters
            resolved_skills = resolve_parameters(skills, params)

            # Calculate training time
            time_data = calculate_activity_training_time(
                resolved_skills,
                current_skills,
            )

            result[tier_name] = {
                "skills": resolved_skills,
                "training_time": time_data,
            }

    return result


async def _activity_list_impl(category: str | None = None) -> dict:
    """
    List available activity skill plans.

    Standalone implementation callable by both MCP tool and dispatcher.

    Args:
        category: Optional filter by category

    Returns:
        List of activities with IDs and descriptions
    """
    activities = load_activities()

    result = []
    categories = set()

    for activity_id, data in activities.items():
        act_category = data.get("category", "other")
        categories.add(act_category)

        if category and act_category.lower() != category.lower():
            continue

        result.append(
            {
                "activity_id": activity_id,
                "display_name": data.get("display_name"),
                "category": act_category,
                "description": data.get("description"),
                "has_parameters": bool(data.get("parameters")),
            }
        )

    return {
        "activities": result,
        "total": len(result),
        "categories": sorted(categories),
        "filter_applied": category,
    }


async def _activity_search_impl(query: str) -> dict:
    """
    Search for activities by keyword.

    Standalone implementation callable by both MCP tool and dispatcher.

    Args:
        query: Search term

    Returns:
        Matching activities
    """
    matches = search_activities(query)

    return {
        "query": query,
        "matches": [
            {
                "activity_id": m["activity_id"],
                "display_name": m.get("display_name"),
                "category": m.get("category"),
                "description": m.get("description"),
            }
            for m in matches
        ],
        "total": len(matches),
    }


async def _activity_compare_tiers_impl(
    activity: str,
    parameters: dict | None = None,
    current_skills: dict | None = None,
) -> dict:
    """
    Compare training times across all tiers for an activity.

    Standalone implementation callable by both MCP tool and dispatcher.

    Args:
        activity: Activity name or ID
        parameters: For parameterized activities
        current_skills: Current skill levels

    Returns:
        Comparison of minimum, easy_80, and full tiers
    """
    # Get full activity data
    plan_result = await _activity_skill_plan_impl(
        activity=activity,
        tier="all",
        parameters=parameters,
        current_skills=current_skills,
    )

    if not plan_result.get("found"):
        return plan_result

    comparison = {
        "activity_id": plan_result.get("activity_id"),
        "display_name": plan_result.get("display_name"),
        "tiers": {},
    }

    for tier_name in ["minimum", "easy_80", "full"]:
        tier_data = plan_result.get(tier_name)
        if tier_data:
            training = tier_data.get("training_time", {})
            comparison["tiers"][tier_name] = {
                "skill_count": len(tier_data.get("skills", [])),
                "total_training": training.get("total_formatted", "N/A"),
                "total_seconds": training.get("total_seconds", 0),
            }

    # Calculate savings
    if "minimum" in comparison["tiers"] and "full" in comparison["tiers"]:
        min_time = comparison["tiers"]["minimum"]["total_seconds"]
        full_time = comparison["tiers"]["full"]["total_seconds"]
        if full_time > 0:
            comparison["minimum_saves"] = {
                "seconds": full_time - min_time,
                "formatted": format_training_time(full_time - min_time),
                "percentage": round((1 - min_time / full_time) * 100, 1),
            }

    if "easy_80" in comparison["tiers"] and "full" in comparison["tiers"]:
        easy_time = comparison["tiers"]["easy_80"]["total_seconds"]
        full_time = comparison["tiers"]["full"]["total_seconds"]
        if full_time > 0:
            comparison["easy_80_saves"] = {
                "seconds": full_time - easy_time,
                "formatted": format_training_time(full_time - easy_time),
                "percentage": round((1 - easy_time / full_time) * 100, 1),
            }

    return comparison


# =============================================================================
# MCP Tool Registration
# =============================================================================


def register_activity_tools(server: FastMCP) -> None:
    """Register activity-related MCP tools with the server."""

    @server.tool()
    async def activity_skill_plan(
        activity: str,
        tier: str = "easy_80",
        parameters: dict | None = None,
        current_skills: dict | None = None,
    ) -> dict:
        """
        Get skill requirements for an EVE Online activity.

        Returns skill lists for different tiers:
        - minimum: Bare minimum to participate
        - easy_80: ~80% effectiveness with reasonable training
        - full: Maximum effectiveness

        Args:
            activity: Activity name or ID (e.g., "gas huffing", "l3 missions")
            tier: Which tier to return ("minimum", "easy_80", "full", or "all")
            parameters: For parameterized activities (e.g., {"field": "Laser Physics"})
            current_skills: Current skill levels for time calculation

        Returns:
            Activity skill plan with training times

        Examples:
            activity_skill_plan("gas huffing")
            activity_skill_plan("research agents", parameters={"field": "Mechanical Engineering"})
            activity_skill_plan("mining barge", tier="all")
        """
        return await _activity_skill_plan_impl(activity, tier, parameters, current_skills)

    @server.tool()
    async def activity_list(
        category: str | None = None,
    ) -> dict:
        """
        List available activity skill plans.

        Args:
            category: Optional filter by category
                     (mining, exploration, combat, industry, trade, research)

        Returns:
            List of activities with IDs and descriptions

        Examples:
            activity_list()  # All activities
            activity_list("mining")  # Mining activities only
        """
        return await _activity_list_impl(category)

    @server.tool()
    async def activity_search(
        query: str,
    ) -> dict:
        """
        Search for activities by keyword.

        Searches activity names, descriptions, and categories.

        Args:
            query: Search term

        Returns:
            Matching activities

        Examples:
            activity_search("mining")
            activity_search("level 3")
            activity_search("gas")
        """
        return await _activity_search_impl(query)

    @server.tool()
    async def activity_compare_tiers(
        activity: str,
        parameters: dict | None = None,
        current_skills: dict | None = None,
    ) -> dict:
        """
        Compare training times across all tiers for an activity.

        Shows the time investment vs effectiveness tradeoff.

        Args:
            activity: Activity name or ID
            parameters: For parameterized activities
            current_skills: Current skill levels

        Returns:
            Comparison of minimum, easy_80, and full tiers

        Examples:
            activity_compare_tiers("gas huffing")
            activity_compare_tiers("mining barge")
        """
        return await _activity_compare_tiers_impl(activity, parameters, current_skills)
