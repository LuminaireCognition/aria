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
    "resolve_names",
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
    "resolve_names",
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
        # resolve_names params
        names: list[str] | None = None,
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
        - resolve_names: Resolve entity names to IDs via ESI

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
                division: Division name (Security, Distribution, Mining, R&D). Also accepts "Research" as alias for R&D.
                system: Filter to specific system
                highsec_only: Only return highsec agents
                limit: Max results (default 20, max 100)

            Agent divisions params (action="agent_divisions"):
                (no params)

            Cache status params (action="cache_status"):
                (no params)

            Meta variants params (action="meta_variants"):
                item: Item name (any variant or base item)

            Resolve names params (action="resolve_names"):
                names: List of entity names to resolve (characters, corps, alliances)

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
            sde(action="resolve_names", names=["Pandemic Horde", "Jita"])
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
                "names": names,
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
            case "resolve_names":
                result = await _resolve_names(names)
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

    from ..sde.tools_item import _item_info_impl

    return await _item_info_impl(item)


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

    from ..sde.tools_skills import _skill_requirements_impl

    result = await _skill_requirements_impl(item, include_prerequisites)
    return wrap_output(result, "full_prerequisite_tree", max_items=SDE.OUTPUT_MAX_SKILL_TREE)


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
    from ..sde.tools_search import _cache_status_impl

    return await _cache_status_impl()


async def _meta_variants(item: str | None) -> dict:
    """Meta variants action - get all variants of an item."""
    if not item:
        raise InvalidParameterError("item", item, "Required for action='meta_variants'")

    from ..sde.tools_item import _meta_variants_impl

    return await _meta_variants_impl(item)


async def _resolve_names(names: list[str] | None) -> dict:
    """Resolve entity names to IDs via ESI POST /universe/ids/ endpoint."""
    if not names:
        raise InvalidParameterError("names", names, "Required for action='resolve_names'")

    # Deduplicate and limit
    unique_names = list(dict.fromkeys(n.strip() for n in names if n.strip()))[:100]
    if not unique_names:
        raise InvalidParameterError("names", names, "At least one non-empty name required")

    from aria_esi.store.esi_client import get_async_esi_client

    client = await get_async_esi_client()
    result = await client.post("/universe/ids/", data=unique_names)

    if not isinstance(result, dict):
        return {
            "query": unique_names,
            "characters": [],
            "corporations": [],
            "alliances": [],
            "systems": [],
            "warnings": ["ESI returned unexpected response format"],
        }

    return {
        "query": unique_names,
        "characters": result.get("characters", []),
        "corporations": result.get("corporations", []),
        "alliances": result.get("alliances", []),
        "systems": result.get("systems", []),
        "total_resolved": sum(
            len(result.get(k, [])) for k in ("characters", "corporations", "alliances", "systems")
        ),
    }
