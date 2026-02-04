"""
Skills Dispatcher for MCP Server.

Consolidates 9 skill-related tools into a single dispatcher:
- training_time: Calculate skill training time
- easy_80_plan: Generate Easy 80% skill plan
- get_multipliers: Get high-impact multiplier skills
- get_breakpoints: Get breakpoint skills for activities
- t2_requirements: Check T2 item skill requirements
- activity_plan: Get skill plan for an activity
- activity_list: List available activities
- activity_search: Search activities by keyword
- activity_compare: Compare activity skill tiers
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from ..context import log_context, wrap_output
from ..context_policy import SKILLS
from ..errors import InvalidParameterError
from ..policy import check_capability
from ..validation import add_validation_warnings, validate_action_params

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from aria_esi.universe.graph import UniverseGraph


SkillsAction = Literal[
    "training_time",
    "easy_80_plan",
    "get_multipliers",
    "get_breakpoints",
    "t2_requirements",
    "activity_plan",
    "activity_list",
    "activity_search",
    "activity_compare",
]

VALID_ACTIONS: set[str] = {
    "training_time",
    "easy_80_plan",
    "get_multipliers",
    "get_breakpoints",
    "t2_requirements",
    "activity_plan",
    "activity_list",
    "activity_search",
    "activity_compare",
}


def register_skills_dispatcher(server: FastMCP, universe: UniverseGraph) -> None:
    """
    Register the unified skills dispatcher with MCP server.

    Args:
        server: MCP Server instance
        universe: UniverseGraph (not used by skills tools, kept for consistency)
    """

    @server.tool()
    @log_context("skills")
    async def skills(
        action: str,
        # Common params
        item: str | None = None,
        # training_time params
        skill_list: list[dict] | None = None,
        attributes: dict | None = None,
        # easy_80_plan params
        current_skills: dict | None = None,
        # get_multipliers/get_breakpoints params
        role: str | None = None,
        category_filter: str | None = None,
        # activity params
        activity: str | None = None,
        tier: str = "easy_80",
        parameters: dict | None = None,
        # search params
        query: str | None = None,
    ) -> dict:
        """
        Unified skill planning interface.

        Actions:
        - training_time: Calculate training time for skills
        - easy_80_plan: Generate Easy 80% skill plan for item
        - get_multipliers: Get high-impact multiplier skills
        - get_breakpoints: Get breakpoint skills
        - t2_requirements: Check T2 skill requirements
        - activity_plan: Get skill plan for an activity
        - activity_list: List available activities
        - activity_search: Search activities
        - activity_compare: Compare activity skill tiers

        Args:
            action: The operation to perform

            Training time params (action="training_time"):
                skill_list: List of {"skill_name": str, "from_level": int, "to_level": int}
                attributes: Optional character attributes {"intelligence": 27, ...}

            Easy 80 params (action="easy_80_plan"):
                item: Item name (ship, module, or skill)
                current_skills: Optional dict of current skill levels
                attributes: Optional attributes for time calculation

            Multipliers params (action="get_multipliers"):
                role: Optional role filter (drone_boat, turret_boat, etc.)

            Breakpoints params (action="get_breakpoints"):
                role: Optional role filter
                category_filter: Optional category filter (combat, tank, etc.)

            T2 requirements params (action="t2_requirements"):
                item: T2 item name

            Activity plan params (action="activity_plan"):
                activity: Activity name or ID
                tier: "minimum", "easy_80", "full", or "all"
                parameters: For parameterized activities
                current_skills: Current skill levels

            Activity list params (action="activity_list"):
                category_filter: Optional category filter

            Activity search params (action="activity_search"):
                query: Search term

            Activity compare params (action="activity_compare"):
                activity: Activity name or ID
                parameters: For parameterized activities
                current_skills: Current skill levels

        Returns:
            Action-specific result dictionary

        Examples:
            skills(action="training_time", skill_list=[{"skill_name": "Mechanics", "from_level": 3, "to_level": 5}])
            skills(action="easy_80_plan", item="Vexor Navy Issue")
            skills(action="get_multipliers", role="drone_boat")
            skills(action="activity_plan", activity="gas huffing")
        """
        if action not in VALID_ACTIONS:
            raise InvalidParameterError(
                "action",
                action,
                f"Must be one of: {', '.join(sorted(VALID_ACTIONS))}",
            )

        # Policy check - verify action is allowed
        # Pass context for policy extensibility and audit logging
        check_capability(
            "skills",
            action,
            context={
                "item": item,
                "activity": activity,
                "skill_count": len(skill_list) if skill_list else None,
            },
        )

        # Validate parameters for this action
        # Warns when irrelevant parameters are passed
        validation_warnings = validate_action_params(
            "skills",
            action,
            {
                "item": item,
                "skill_list": skill_list,
                "attributes": attributes,
                "current_skills": current_skills,
                "role": role,
                "category_filter": category_filter,
                "activity": activity,
                "tier": tier,
                "parameters": parameters,
                "query": query,
            },
        )

        # Execute action
        match action:
            case "training_time":
                result = await _training_time(skill_list, attributes)
            case "easy_80_plan":
                result = await _easy_80_plan(item, current_skills, attributes)
            case "get_multipliers":
                result = await _get_multipliers(role)
            case "get_breakpoints":
                result = await _get_breakpoints(role, category_filter)
            case "t2_requirements":
                result = await _t2_requirements(item)
            case "activity_plan":
                result = await _activity_plan(activity, tier, parameters, current_skills)
            case "activity_list":
                result = await _activity_list(category_filter)
            case "activity_search":
                result = await _activity_search(query)
            case "activity_compare":
                result = await _activity_compare(activity, parameters, current_skills)
            case _:
                raise InvalidParameterError("action", action, f"Unknown action: {action}")

        # Add validation warnings to result if any
        return add_validation_warnings(result, validation_warnings)


# =============================================================================
# Skills Action Implementations
# =============================================================================


async def _training_time(skill_list: list[dict] | None, attributes: dict | None) -> dict:
    """Training time action - calculate skill training time."""
    if not skill_list:
        raise InvalidParameterError("skill_list", skill_list, "Required for action='training_time'")

    import math

    from aria_esi.models.sde import TrainingTimeResult

    from ..market.database import get_market_database
    from ..sde.queries import get_sde_query_service

    # Training time constants
    SP_PER_LEVEL = {1: 250, 2: 1415, 3: 8000, 4: 45255, 5: 256000}
    DEFAULT_ATTRIBUTES = {
        "intelligence": 20,
        "memory": 20,
        "perception": 20,
        "willpower": 20,
        "charisma": 19,
    }

    db = get_market_database()
    conn = db._get_connection()
    query_service = get_sde_query_service()

    attrs = attributes or DEFAULT_ATTRIBUTES.copy()
    warnings: list[str] = []
    skill_results: list[dict] = []
    total_sp = 0
    total_seconds = 0

    for skill_spec in skill_list:
        skill_name = skill_spec.get("skill_name", "")
        from_level = skill_spec.get("from_level", 0)
        to_level = skill_spec.get("to_level", 1)

        if from_level < 0 or from_level > 4:
            warnings.append(f"{skill_name}: Invalid from_level {from_level}")
            continue
        if to_level < 1 or to_level > 5:
            warnings.append(f"{skill_name}: Invalid to_level {to_level}")
            continue
        if from_level >= to_level:
            warnings.append(f"{skill_name}: from_level >= to_level, skipping")
            continue

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
            warnings.append(f"Skill '{skill_name}' not found")
            continue

        skill_id = row[0]
        skill_attrs = query_service.get_skill_attributes(skill_id)

        if not skill_attrs:
            warnings.append(f"No training data for '{skill_name}'")
            continue

        # Calculate SP needed
        sp_at_from = SP_PER_LEVEL.get(from_level, 0) * skill_attrs.rank if from_level > 0 else 0
        sp_at_to = SP_PER_LEVEL.get(to_level, 0) * skill_attrs.rank
        sp_needed = sp_at_to - sp_at_from

        # Calculate training time
        primary_val = attrs.get(skill_attrs.primary_attribute or "intelligence", 20)
        secondary_val = attrs.get(skill_attrs.secondary_attribute or "memory", 20)
        sp_per_min = primary_val + (secondary_val / 2)
        training_minutes = sp_needed / sp_per_min
        training_seconds = int(math.ceil(training_minutes * 60))

        total_sp += sp_needed
        total_seconds += training_seconds

        skill_results.append(
            {
                "skill_name": skill_attrs.type_name,
                "skill_id": skill_attrs.type_id,
                "rank": skill_attrs.rank,
                "from_level": from_level,
                "to_level": to_level,
                "sp_needed": sp_needed,
                "training_seconds": training_seconds,
                "training_formatted": _format_training_time(training_seconds),
                "primary_attribute": skill_attrs.primary_attribute,
                "secondary_attribute": skill_attrs.secondary_attribute,
            }
        )

    return wrap_output(
        TrainingTimeResult(
            skills=skill_results,
            total_skillpoints=total_sp,
            total_training_seconds=total_seconds,
            total_training_formatted=_format_training_time(total_seconds),
            attributes_used=attrs,
            warnings=warnings,
        ).model_dump(),
        "skills",
        max_items=SKILLS.OUTPUT_MAX_SKILLS,
    )


def _format_training_time(seconds: int) -> str:
    """Format training time in human-readable format."""
    if seconds < 60:
        return f"{seconds}s"

    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"

    hours = minutes // 60
    remaining_minutes = minutes % 60
    if hours < 24:
        if remaining_minutes:
            return f"{hours}h {remaining_minutes}m"
        return f"{hours}h"

    days = hours // 24
    remaining_hours = hours % 24
    if remaining_hours:
        return f"{days}d {remaining_hours}h"
    return f"{days}d"


async def _easy_80_plan(
    item: str | None, current_skills: dict | None, attributes: dict | None
) -> dict:
    """Easy 80 plan action - generate Easy 80% skill plan."""
    if not item:
        raise InvalidParameterError("item", item, "Required for action='easy_80_plan'")

    from ..sde.tools_easy80 import _easy_80_plan_impl

    result = await _easy_80_plan_impl(item, current_skills, attributes)
    return wrap_output(result, "skill_plan", max_items=SKILLS.OUTPUT_MAX_SKILLS)


async def _get_multipliers(role: str | None) -> dict:
    """Get multipliers action - get high-impact multiplier skills."""
    from ..sde.tools_easy80 import _get_multipliers_impl

    return await _get_multipliers_impl(role)


async def _get_breakpoints(role: str | None, category_filter: str | None) -> dict:
    """Get breakpoints action - get breakpoint skills."""
    from ..sde.tools_easy80 import _get_breakpoints_impl

    return await _get_breakpoints_impl(role, category_filter)


async def _t2_requirements(item: str | None) -> dict:
    """T2 requirements action - check T2 skill requirements."""
    if not item:
        raise InvalidParameterError("item", item, "Required for action='t2_requirements'")

    from ..sde.tools_easy80 import _t2_requirements_impl

    return await _t2_requirements_impl(item)


async def _activity_plan(
    activity: str | None,
    tier: str,
    parameters: dict | None,
    current_skills: dict | None,
) -> dict:
    """Activity plan action - get skill plan for an activity."""
    if not activity:
        raise InvalidParameterError("activity", activity, "Required for action='activity_plan'")

    from ..sde.tools_activities import _activity_skill_plan_impl

    result = await _activity_skill_plan_impl(activity, tier, parameters, current_skills)
    return wrap_output(result, "skills", max_items=SKILLS.OUTPUT_MAX_SKILLS)


async def _activity_list(category_filter: str | None) -> dict:
    """Activity list action - list available activities."""
    from ..sde.tools_activities import _activity_list_impl

    result = await _activity_list_impl(category_filter)
    return wrap_output(result, "activities", max_items=SKILLS.OUTPUT_MAX_ACTIVITIES)


async def _activity_search(query: str | None) -> dict:
    """Activity search action - search activities."""
    if not query:
        raise InvalidParameterError("query", query, "Required for action='activity_search'")

    from ..sde.tools_activities import _activity_search_impl

    return await _activity_search_impl(query)


async def _activity_compare(
    activity: str | None,
    parameters: dict | None,
    current_skills: dict | None,
) -> dict:
    """Activity compare action - compare activity skill tiers."""
    if not activity:
        raise InvalidParameterError("activity", activity, "Required for action='activity_compare'")

    from ..sde.tools_activities import _activity_compare_tiers_impl

    return await _activity_compare_tiers_impl(activity, parameters, current_skills)
