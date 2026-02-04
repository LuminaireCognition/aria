"""
SDE Dispatcher for MCP Server.

Consolidates 8 SDE tools into a single dispatcher:
- item_info: Detailed item information
- blueprint_info: Blueprint manufacturing data
- search: Search items by name/category
- skill_requirements: Skill prerequisites for items
- corporation_info: NPC corporation info
- agent_search: Find NPC mission agents
- agent_divisions: List agent divisions
- cache_status: SDE database status
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from ..context import log_context, wrap_output
from ..context_policy import SDE
from ..errors import InvalidParameterError
from ..policy import check_capability
from ..validation import add_validation_warnings, validate_action_params

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from aria_esi.universe.graph import UniverseGraph


SDEAction = Literal[
    "item_info",
    "blueprint_info",
    "search",
    "skill_requirements",
    "corporation_info",
    "agent_search",
    "agent_divisions",
    "cache_status",
    "meta_variants",
]

VALID_ACTIONS: set[str] = {
    "item_info",
    "blueprint_info",
    "search",
    "skill_requirements",
    "corporation_info",
    "agent_search",
    "agent_divisions",
    "cache_status",
    "meta_variants",
}


def register_sde_dispatcher(server: FastMCP, universe: UniverseGraph) -> None:
    """
    Register the unified SDE dispatcher with MCP server.

    Args:
        server: MCP Server instance
        universe: UniverseGraph (not used by SDE tools, kept for consistency)
    """

    @server.tool()
    @log_context("sde")
    async def sde(
        action: str,
        # Common params
        item: str | None = None,
        # search params
        query: str | None = None,
        category: str | None = None,
        limit: int = 10,
        # skill_requirements params
        include_prerequisites: bool = True,
        # corporation_info params
        corporation_id: int | None = None,
        corporation_name: str | None = None,
        # agent_search params
        corporation: str | None = None,
        level: int | None = None,
        division: str | None = None,
        system: str | None = None,
        highsec_only: bool = False,
    ) -> dict:
        """
        Unified SDE (Static Data Export) interface.

        Actions:
        - item_info: Get detailed item information
        - blueprint_info: Get blueprint manufacturing data
        - search: Search items by name with optional category filter
        - skill_requirements: Get skill prerequisites for items
        - corporation_info: Get NPC corporation details
        - agent_search: Find NPC mission agents
        - agent_divisions: List available agent divisions
        - cache_status: Get SDE database status
        - meta_variants: Get T2/Faction/Officer variants of an item

        Args:
            action: The operation to perform

            Item info params (action="item_info"):
                item: Item name (case-insensitive, fuzzy matched)

            Blueprint params (action="blueprint_info"):
                item: Product name or blueprint name

            Search params (action="search"):
                query: Search term (partial name)
                category: Optional category filter (Ship, Module, Blueprint, etc.)
                limit: Max results (default 10, max 50)

            Skill requirements params (action="skill_requirements"):
                item: Item name (ship, module, or skill)
                include_prerequisites: Include full prerequisite chain (default True)

            Corporation info params (action="corporation_info"):
                corporation_id: Corporation ID, OR
                corporation_name: Corporation name (fuzzy matched)

            Agent search params (action="agent_search"):
                corporation: Corporation name
                corporation_id: Corporation ID (alternative)
                level: Agent level (1-5)
                division: Division name (Security, Distribution, Mining, Research)
                system: Filter to specific system
                highsec_only: Only return highsec agents
                limit: Max results (default 20, max 100)

            Agent divisions params (action="agent_divisions"):
                (no params)

            Cache status params (action="cache_status"):
                (no params)

            Meta variants params (action="meta_variants"):
                item: Item name (any variant or base item)

        Returns:
            Action-specific result dictionary

        Examples:
            sde(action="item_info", item="Pioneer")
            sde(action="blueprint_info", item="Venture Blueprint")
            sde(action="search", query="mining", category="Ship")
            sde(action="skill_requirements", item="Vexor Navy Issue")
            sde(action="corporation_info", corporation_name="Sisters of EVE")
            sde(action="agent_search", corporation="Caldari Navy", level=4)
            sde(action="meta_variants", item="Medium Armor Repairer II")
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
            "sde",
            action,
            context={
                "item": item,
                "query": query,
                "corporation": corporation or corporation_name,
            },
        )

        # Validate parameters for this action
        # Warns when irrelevant parameters are passed
        validation_warnings = validate_action_params(
            "sde",
            action,
            {
                "item": item,
                "query": query,
                "category": category,
                "limit": limit,
                "include_prerequisites": include_prerequisites,
                "corporation_id": corporation_id,
                "corporation_name": corporation_name,
                "corporation": corporation,
                "level": level,
                "division": division,
                "system": system,
                "highsec_only": highsec_only,
            },
        )

        # Execute action
        match action:
            case "item_info":
                result = await _item_info(item)
            case "blueprint_info":
                result = await _blueprint_info(item)
            case "search":
                result = await _search(query, category, limit)
            case "skill_requirements":
                result = await _skill_requirements(item, include_prerequisites)
            case "corporation_info":
                result = await _corporation_info(corporation_id, corporation_name)
            case "agent_search":
                result = await _agent_search(
                    corporation, corporation_id, level, division, system, highsec_only, limit
                )
            case "agent_divisions":
                result = await _agent_divisions()
            case "cache_status":
                result = await _cache_status()
            case "meta_variants":
                result = await _meta_variants(item)
            case _:
                raise InvalidParameterError("action", action, f"Unknown action: {action}")

        # Add validation warnings to result if any
        return add_validation_warnings(result, validation_warnings)


# =============================================================================
# SDE Action Implementations
# =============================================================================


async def _item_info(item: str | None) -> dict:
    """Item info action - get detailed item information."""
    if not item:
        raise InvalidParameterError("item", item, "Required for action='item_info'")

    from aria_esi.models.sde import CATEGORY_BLUEPRINT, ItemInfo, ItemInfoResult

    from ..market.database import get_market_database
    from ..sde.queries import get_sde_query_service

    db = get_market_database()
    conn = db._get_connection()

    query = item.strip()
    query_lower = query.lower()

    # Check if SDE tables exist
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='categories'")
    if not cursor.fetchone():
        return ItemInfoResult(
            item=None,
            found=False,
            query=query,
            suggestions=[],
            warnings=["SDE data not seeded. Run 'aria-esi sde-seed' first."],
        ).model_dump()

    # Try exact match first
    item_data = _lookup_item(conn, query_lower, exact=True)

    if not item_data:
        # Try fuzzy match
        item_data = _lookup_item(conn, query_lower, exact=False)

    if item_data:
        is_blueprint = item_data.get("category_id") == CATEGORY_BLUEPRINT or item_data.get(
            "type_name", ""
        ).lower().endswith(" blueprint")

        skill_rank = None
        skill_primary = None
        skill_secondary = None
        skill_prereqs = None

        if item_data.get("category_id") == 16:  # CATEGORY_SKILL
            skill_table_cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='skill_attributes'"
            )
            if skill_table_cursor.fetchone():
                skill_cursor = conn.execute(
                    """
                    SELECT rank, primary_attribute, secondary_attribute
                    FROM skill_attributes
                    WHERE type_id = ?
                    """,
                    (item_data["type_id"],),
                )
                skill_row = skill_cursor.fetchone()
                if skill_row:
                    skill_rank = skill_row[0]
                    skill_primary = skill_row[1]
                    skill_secondary = skill_row[2]

                query_service = get_sde_query_service()
                prereqs = query_service.get_skill_prerequisites(item_data["type_id"])
                if prereqs:
                    skill_prereqs = [
                        {
                            "skill_id": p.skill_id,
                            "skill_name": p.skill_name,
                            "level": p.required_level,
                        }
                        for p in prereqs
                    ]

        result_item = ItemInfo(
            type_id=item_data["type_id"],
            type_name=item_data["type_name"],
            description=item_data.get("description"),
            group_id=item_data.get("group_id"),
            group_name=item_data.get("group_name"),
            category_id=item_data.get("category_id"),
            category_name=item_data.get("category_name"),
            market_group_id=item_data.get("market_group_id"),
            volume=item_data.get("volume"),
            packaged_volume=item_data.get("packaged_volume"),
            is_published=bool(item_data.get("published", 1)),
            is_blueprint=is_blueprint,
            skill_rank=skill_rank,
            skill_primary_attribute=skill_primary,
            skill_secondary_attribute=skill_secondary,
            skill_prerequisites=skill_prereqs,
        )

        return ItemInfoResult(
            item=result_item,
            found=True,
            query=query,
            suggestions=[],
            warnings=[],
        ).model_dump()

    # Not found - get suggestions
    suggestions = _find_suggestions(conn, query_lower)

    return ItemInfoResult(
        item=None,
        found=False,
        query=query,
        suggestions=suggestions,
        warnings=[f"Item '{query}' not found in SDE."],
    ).model_dump()


def _lookup_item(conn, query_lower: str, exact: bool = True) -> dict | None:
    """Look up item by name."""
    if exact:
        cursor = conn.execute(
            """
            SELECT
                t.type_id, t.type_name, t.description, t.group_id, t.category_id,
                t.market_group_id, t.volume, t.packaged_volume, t.published,
                g.group_name, c.category_name
            FROM types t
            LEFT JOIN groups g ON t.group_id = g.group_id
            LEFT JOIN categories c ON t.category_id = c.category_id
            WHERE t.type_name_lower = ?
            LIMIT 1
            """,
            (query_lower,),
        )
    else:
        cursor = conn.execute(
            """
            SELECT
                t.type_id, t.type_name, t.description, t.group_id, t.category_id,
                t.market_group_id, t.volume, t.packaged_volume, t.published,
                g.group_name, c.category_name
            FROM types t
            LEFT JOIN groups g ON t.group_id = g.group_id
            LEFT JOIN categories c ON t.category_id = c.category_id
            WHERE t.type_name_lower LIKE ?
            AND t.published = 1
            ORDER BY length(t.type_name)
            LIMIT 1
            """,
            (f"{query_lower}%",),
        )

    row = cursor.fetchone()

    if not row and not exact:
        cursor = conn.execute(
            """
            SELECT
                t.type_id, t.type_name, t.description, t.group_id, t.category_id,
                t.market_group_id, t.volume, t.packaged_volume, t.published,
                g.group_name, c.category_name
            FROM types t
            LEFT JOIN groups g ON t.group_id = g.group_id
            LEFT JOIN categories c ON t.category_id = c.category_id
            WHERE t.type_name_lower LIKE ?
            AND t.published = 1
            ORDER BY length(t.type_name)
            LIMIT 1
            """,
            (f"%{query_lower}%",),
        )
        row = cursor.fetchone()

    if row:
        return {
            "type_id": row[0],
            "type_name": row[1],
            "description": row[2],
            "group_id": row[3],
            "category_id": row[4],
            "market_group_id": row[5],
            "volume": row[6],
            "packaged_volume": row[7],
            "published": row[8],
            "group_name": row[9],
            "category_name": row[10],
        }

    return None


def _find_suggestions(conn, query_lower: str, limit: int = 5) -> list[str]:
    """Find similar item names for suggestions."""
    suggestions = []

    cursor = conn.execute(
        """
        SELECT type_name FROM types
        WHERE type_name_lower LIKE ?
        AND published = 1
        ORDER BY length(type_name)
        LIMIT ?
        """,
        (f"{query_lower}%", limit),
    )
    suggestions.extend(row[0] for row in cursor.fetchall())

    if len(suggestions) < limit:
        remaining = limit - len(suggestions)
        cursor = conn.execute(
            """
            SELECT type_name FROM types
            WHERE type_name_lower LIKE ?
            AND type_name_lower NOT LIKE ?
            AND published = 1
            ORDER BY length(type_name)
            LIMIT ?
            """,
            (f"%{query_lower}%", f"{query_lower}%", remaining),
        )
        suggestions.extend(row[0] for row in cursor.fetchall())

    return suggestions


async def _blueprint_info(item: str | None) -> dict:
    """Blueprint info action - get blueprint manufacturing data."""
    if not item:
        raise InvalidParameterError("item", item, "Required for action='blueprint_info'")

    from ..sde.tools_blueprint import _blueprint_info_impl

    return await _blueprint_info_impl(item)


async def _search(query: str | None, category: str | None, limit: int) -> dict:
    """Search action - search items by name."""
    if not query:
        raise InvalidParameterError("query", query, "Required for action='search'")

    from ..sde.tools_search import _search_impl

    result = await _search_impl(query, category, limit)
    return wrap_output(result, "items", max_items=SDE.OUTPUT_MAX_SEARCH_ITEMS)


async def _skill_requirements(item: str | None, include_prerequisites: bool) -> dict:
    """Skill requirements action - get skill prerequisites."""
    if not item:
        raise InvalidParameterError("item", item, "Required for action='skill_requirements'")

    from aria_esi.models.sde import (
        CATEGORY_SKILL,
        SkillRequirementNode,
        SkillRequirementsResult,
        TypeSkillRequirement,
    )

    from ..market.database import get_market_database
    from ..sde.queries import get_sde_query_service

    db = get_market_database()
    conn = db._get_connection()
    query_service = get_sde_query_service()

    query = item.strip()
    query_lower = query.lower()

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

    direct_reqs = query_service.get_type_skill_requirements(type_id)

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

    return wrap_output(
        SkillRequirementsResult(
            item=type_name,
            item_type_id=type_id,
            item_category=category_name,
            found=True,
            direct_requirements=direct_req_list,
            full_prerequisite_tree=full_tree,
            total_skills=len(full_tree),
            warnings=[],
        ).model_dump(),
        "full_prerequisite_tree",
        max_items=SDE.OUTPUT_MAX_SKILL_TREE,
    )


async def _corporation_info(corporation_id: int | None, corporation_name: str | None) -> dict:
    """Corporation info action - get NPC corporation details."""
    if not corporation_id and not corporation_name:
        raise InvalidParameterError(
            "corporation_id/corporation_name",
            None,
            "Either corporation_id or corporation_name required for action='corporation_info'",
        )

    from ..sde.tools_corporation import _corporation_info_impl

    return await _corporation_info_impl(corporation_id, corporation_name)


async def _agent_search(
    corporation: str | None,
    corporation_id: int | None,
    level: int | None,
    division: str | None,
    system: str | None,
    highsec_only: bool,
    limit: int,
) -> dict:
    """Agent search action - find NPC mission agents."""
    from ..sde.tools_agents import _agent_search_impl

    result = await _agent_search_impl(
        corporation, corporation_id, level, division, system, highsec_only, limit
    )
    return wrap_output(result, "agents", max_items=SDE.OUTPUT_MAX_AGENTS)


async def _agent_divisions() -> dict:
    """Agent divisions action - list available divisions."""
    from ..sde.tools_agents import _agent_divisions_impl

    return await _agent_divisions_impl()


async def _cache_status() -> dict:
    """Cache status action - get SDE database status."""
    from ..market.database import get_market_database

    db = get_market_database()
    stats = db.get_stats()

    return {
        "database_path": stats.get("database_path"),
        "database_size_mb": round(stats.get("database_size_mb", 0), 2),
        "type_count": stats.get("type_count", 0),
        "is_available": stats.get("type_count", 0) > 0,
    }


async def _meta_variants(item: str | None) -> dict:
    """Meta variants action - get all variants of an item."""
    if not item:
        raise InvalidParameterError("item", item, "Required for action='meta_variants'")

    from aria_esi.models.sde import MetaVariantInfo, MetaVariantsResult

    from ..market.database import get_market_database
    from ..sde.queries import get_sde_query_service

    db = get_market_database()
    conn = db._get_connection()
    query_service = get_sde_query_service()

    query = item.strip()
    query_lower = query.lower()

    # Check if meta_types table exists
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='meta_types'"
    )
    if not cursor.fetchone():
        return MetaVariantsResult(
            query=query,
            query_type_id=0,
            found=False,
            warnings=["Meta type data not imported. Run 'aria-esi sde-seed' to update SDE."],
        ).model_dump()

    # Look up the queried item
    item_data = _lookup_item(conn, query_lower, exact=True)
    if not item_data:
        item_data = _lookup_item(conn, query_lower, exact=False)

    if not item_data:
        return MetaVariantsResult(
            query=query,
            query_type_id=0,
            found=False,
            warnings=[f"Item '{query}' not found in SDE."],
        ).model_dump()

    type_id = item_data["type_id"]

    # Get variants
    variants = query_service.get_meta_variants(type_id)

    # Determine parent
    parent_id = query_service._get_parent_type_id(type_id)
    parent_name = None

    if parent_id:
        # Queried item is a variant, look up parent name
        cursor = conn.execute("SELECT type_name FROM types WHERE type_id = ?", (parent_id,))
        row = cursor.fetchone()
        parent_name = row[0] if row else None
    elif variants:
        # Queried item is the parent
        parent_id = type_id
        parent_name = item_data["type_name"]

    variant_list = [
        MetaVariantInfo(
            type_id=v.type_id,
            type_name=v.type_name,
            meta_group_id=v.meta_group_id,
            meta_group_name=v.meta_group_name,
        )
        for v in variants
    ]

    return MetaVariantsResult(
        query=query,
        query_type_id=type_id,
        parent_type_id=parent_id,
        parent_type_name=parent_name,
        found=True,
        variants=variant_list,
        total_variants=len(variant_list),
        warnings=[] if variants else ["No meta variants found for this item."],
    ).model_dump()
