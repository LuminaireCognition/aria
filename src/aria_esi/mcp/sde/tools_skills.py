"""
SDE Skill Requirements MCP Tools.

Provides skill prerequisite lookups and training time calculations
for ships, modules, and other items in EVE Online.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from aria_esi.core.logging import get_logger
from aria_esi.mcp.market.database import get_market_database
from aria_esi.models.sde import (
    CATEGORY_SKILL,
    SkillRequirementNode,
    SkillRequirementsResult,
    TrainingTimeResult,
    TypeSkillRequirement,
)

from .queries import get_sde_query_service

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = get_logger("aria_sde.tools_skills")

# =============================================================================
# Training Time Constants
# =============================================================================

# Skillpoint thresholds per level (cumulative SP needed to reach level N)
# These are multiplied by the skill rank to get actual SP
SP_PER_LEVEL = {
    1: 250,
    2: 1415,
    3: 8000,
    4: 45255,
    5: 256000,
}

# Default character attributes (no implants, balanced remap)
DEFAULT_ATTRIBUTES = {
    "intelligence": 20,
    "memory": 20,
    "perception": 20,
    "willpower": 20,
    "charisma": 19,
}


# =============================================================================
# Utility Functions
# =============================================================================


def calculate_sp_for_level(rank: int, level: int) -> int:
    """
    Calculate total SP needed to reach a skill level.

    Args:
        rank: Skill rank (training time multiplier)
        level: Target level (1-5)

    Returns:
        Total skillpoints needed
    """
    if level < 1 or level > 5:
        return 0
    return SP_PER_LEVEL[level] * rank


def calculate_sp_per_minute(
    primary_attr: str | None,
    secondary_attr: str | None,
    attributes: dict[str, int] | None = None,
) -> float:
    """
    Calculate SP gained per minute based on attributes.

    EVE formula: SP/min = primary + secondary/2

    Args:
        primary_attr: Primary training attribute name
        secondary_attr: Secondary training attribute name
        attributes: Character attributes dict (defaults to DEFAULT_ATTRIBUTES)

    Returns:
        Skillpoints gained per minute
    """
    attrs = attributes or DEFAULT_ATTRIBUTES

    primary_val = attrs.get(primary_attr or "intelligence", 20)
    secondary_val = attrs.get(secondary_attr or "memory", 20)

    return primary_val + (secondary_val / 2)


def format_training_time(seconds: int) -> str:
    """
    Format training time in human-readable format.

    Args:
        seconds: Training time in seconds

    Returns:
        Formatted string like "2d 5h 30m" or "45m"
    """
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


# =============================================================================
# Tool Registration
# =============================================================================


def register_skill_tools(server: FastMCP) -> None:
    """Register skill-related MCP tools with the server."""

    @server.tool()
    async def sde_skill_requirements(
        item: str,
        include_prerequisites: bool = True,
    ) -> dict:
        """
        Get skill requirements for an item (ship, module, skill).

        Returns both direct requirements and the full prerequisite tree
        needed to use an item in EVE Online.

        Args:
            item: Item name (ship, module, or skill) - case-insensitive
            include_prerequisites: Include full prerequisite chain (default: True)

        Returns:
            SkillRequirementsResult with complete skill tree

        Examples:
            sde_skill_requirements("Vexor Navy Issue")
            sde_skill_requirements("Medium Armor Repairer II")
            sde_skill_requirements("Mechanical Engineering")
        """
        db = get_market_database()
        conn = db._get_connection()
        query_service = get_sde_query_service()

        # Normalize query
        query = item.strip()
        query_lower = query.lower()

        # Check if SDE tables exist
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='type_skill_requirements'"
        )
        if not cursor.fetchone():
            return SkillRequirementsResult(
                item=query,
                item_type_id=0,
                item_category=None,
                found=False,
                warnings=["Skill data not imported. Run 'aria-esi sde-seed' to update SDE."],
            ).model_dump()

        # Look up item
        cursor = conn.execute(
            """
            SELECT t.type_id, t.type_name, c.category_name, t.category_id
            FROM types t
            LEFT JOIN categories c ON t.category_id = c.category_id
            WHERE t.type_name_lower = ?
            LIMIT 1
            """,
            (query_lower,),
        )
        row = cursor.fetchone()

        if not row:
            # Try fuzzy match
            cursor = conn.execute(
                """
                SELECT t.type_id, t.type_name, c.category_name, t.category_id
                FROM types t
                LEFT JOIN categories c ON t.category_id = c.category_id
                WHERE t.type_name_lower LIKE ?
                AND t.published = 1
                ORDER BY length(t.type_name)
                LIMIT 1
                """,
                (f"{query_lower}%",),
            )
            row = cursor.fetchone()

        if not row:
            return SkillRequirementsResult(
                item=query,
                item_type_id=0,
                item_category=None,
                found=False,
                warnings=[f"Item '{query}' not found in SDE."],
            ).model_dump()

        type_id, type_name, category_name, category_id = row

        # Get direct requirements
        direct_reqs = query_service.get_type_skill_requirements(type_id)

        # For skills, get their prerequisites too
        if category_id == CATEGORY_SKILL:
            skill_prereqs = query_service.get_skill_prerequisites(type_id)
            direct_req_list = [
                TypeSkillRequirement(
                    skill_id=p.skill_id,
                    skill_name=p.skill_name,
                    required_level=p.required_level,
                )
                for p in skill_prereqs
            ]
        else:
            direct_req_list = [
                TypeSkillRequirement(
                    skill_id=r.skill_id,
                    skill_name=r.skill_name,
                    required_level=r.required_level,
                )
                for r in direct_reqs
            ]

        # Get full prerequisite tree if requested
        full_tree: list[SkillRequirementNode] = []
        if include_prerequisites:
            tree_data = query_service.get_full_skill_tree(type_id)
            for skill_id, skill_name, level, rank in tree_data:
                attrs = query_service.get_skill_attributes(skill_id)
                full_tree.append(
                    SkillRequirementNode(
                        skill_id=skill_id,
                        skill_name=skill_name,
                        required_level=level,
                        rank=rank,
                        primary_attribute=attrs.primary_attribute if attrs else None,
                        secondary_attribute=attrs.secondary_attribute if attrs else None,
                    )
                )

        return SkillRequirementsResult(
            item=type_name,
            item_type_id=type_id,
            item_category=category_name,
            found=True,
            direct_requirements=direct_req_list,
            full_prerequisite_tree=full_tree,
            total_skills=len(full_tree),
            warnings=[],
        ).model_dump()

    @server.tool()
    async def skill_training_time(
        skills: list[dict],
        attributes: dict | None = None,
    ) -> dict:
        """
        Calculate training time for a skill plan.

        Uses the EVE Online skill training formula to calculate time needed
        to train skills from their current level to target levels.

        Args:
            skills: List of {"skill_name": str, "from_level": int, "to_level": int}
            attributes: Optional character attributes {"intelligence": 27, ...}
                       Defaults to balanced 20/20/20/20/19 if not provided.

                       To include implant bonuses, add them directly to the
                       relevant attribute values. For example, with a +4
                       Intelligence implant: {"intelligence": 24, ...}

                       Attribute names: intelligence, memory, perception,
                       willpower, charisma

        Returns:
            TrainingTimeResult with per-skill breakdown and totals

        Examples:
            skill_training_time([
                {"skill_name": "Mechanics", "from_level": 3, "to_level": 5},
                {"skill_name": "Hull Upgrades", "from_level": 0, "to_level": 4}
            ])

            # With +4 perception implant
            skill_training_time(
                [{"skill_name": "Spaceship Command", "from_level": 4, "to_level": 5}],
                attributes={"perception": 24, "willpower": 20}
            )
        """
        db = get_market_database()
        conn = db._get_connection()
        query_service = get_sde_query_service()

        attrs = attributes or DEFAULT_ATTRIBUTES.copy()
        warnings: list[str] = []
        skill_results: list[dict] = []
        total_sp = 0
        total_seconds = 0

        for skill_spec in skills:
            skill_name = skill_spec.get("skill_name", "")
            from_level = skill_spec.get("from_level", 0)
            to_level = skill_spec.get("to_level", 1)

            # Validate levels
            if from_level < 0 or from_level > 4:
                warnings.append(f"{skill_name}: Invalid from_level {from_level}")
                continue
            if to_level < 1 or to_level > 5:
                warnings.append(f"{skill_name}: Invalid to_level {to_level}")
                continue
            if from_level >= to_level:
                warnings.append(f"{skill_name}: from_level >= to_level, skipping")
                continue

            # Look up skill
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
            sp_at_from = (
                calculate_sp_for_level(skill_attrs.rank, from_level) if from_level > 0 else 0
            )
            sp_at_to = calculate_sp_for_level(skill_attrs.rank, to_level)
            sp_needed = sp_at_to - sp_at_from

            # Calculate training time
            sp_per_min = calculate_sp_per_minute(
                skill_attrs.primary_attribute,
                skill_attrs.secondary_attribute,
                attrs,
            )
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
                    "training_formatted": format_training_time(training_seconds),
                    "primary_attribute": skill_attrs.primary_attribute,
                    "secondary_attribute": skill_attrs.secondary_attribute,
                }
            )

        return TrainingTimeResult(
            skills=skill_results,
            total_skillpoints=total_sp,
            total_training_seconds=total_seconds,
            total_training_formatted=format_training_time(total_seconds),
            attributes_used=attrs,
            warnings=warnings,
        ).model_dump()
