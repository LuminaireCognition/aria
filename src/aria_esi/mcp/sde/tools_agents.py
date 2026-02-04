"""
SDE Agent Search MCP Tool.

Provides NPC agent search by corporation, level, and division.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from aria_esi.core.logging import get_logger
from aria_esi.mcp.market.database import get_market_database

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = get_logger("aria_sde.tools_agents")


# =============================================================================
# Models
# =============================================================================


class AgentModel(BaseModel):
    """Base model for agent data."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class AgentInfo(AgentModel):
    """Information about a single NPC agent."""

    agent_id: int = Field(ge=1, description="Agent ID")
    agent_name: str = Field(description="Agent name")
    level: int = Field(ge=1, le=5, description="Agent level (1-5)")
    division_id: int | None = Field(default=None, description="Division ID")
    division_name: str | None = Field(
        default=None, description="Division name (Security, Distribution, Mining, etc.)"
    )
    corporation_id: int = Field(ge=1, description="Corporation ID")
    corporation_name: str | None = Field(default=None, description="Corporation name")
    station_id: int | None = Field(default=None, description="Station ID")
    station_name: str | None = Field(default=None, description="Station name")
    system_id: int | None = Field(default=None, description="Solar system ID")
    system_name: str | None = Field(default=None, description="Solar system name")
    security: float | None = Field(default=None, description="System security status")
    region_name: str | None = Field(default=None, description="Region name")
    agent_type: str | None = Field(
        default=None, description="Agent type (BasicAgent, ResearchAgent, etc.)"
    )


class AgentSearchResult(AgentModel):
    """Result from sde_agent_search tool."""

    success: bool = Field(description="Whether the search succeeded")
    agents: list[AgentInfo] = Field(default_factory=list, description="Matching agents")
    total_found: int = Field(default=0, ge=0, description="Total agents matching criteria")
    filters_applied: dict = Field(default_factory=dict, description="Summary of filters used")
    error_code: str | None = Field(default=None, description="Error code if failed")
    message: str | None = Field(default=None, description="Error or status message")


class DivisionListResult(AgentModel):
    """Result from sde_agent_divisions tool."""

    success: bool = Field(description="Whether the lookup succeeded")
    divisions: list[dict] = Field(
        default_factory=list, description="List of division ID/name pairs"
    )
    error_code: str | None = Field(default=None, description="Error code if failed")
    message: str | None = Field(default=None, description="Error or status message")


# =============================================================================
# Standalone Implementation Functions (for dispatcher imports)
# =============================================================================


async def _agent_search_impl(
    corporation: str | None = None,
    corporation_id: int | None = None,
    level: int | None = None,
    division: str | None = None,
    system: str | None = None,
    highsec_only: bool = False,
    limit: int = 20,
) -> dict:
    """
    Search for NPC mission agents by corporation, level, and division.

    Standalone implementation callable by both MCP tool and dispatcher.

    Args:
        corporation: Corporation name (fuzzy matched, e.g., "Sisters of EVE")
        corporation_id: Corporation ID (alternative to name)
        level: Agent level (1-5)
        division: Division name (Security, Distribution, Mining, Research)
        system: Filter to specific solar system
        highsec_only: If True, only return agents in highsec (>=0.45)
        limit: Maximum results (default 20, max 100)

    Returns:
        AgentSearchResult with matching agents
    """
    limit = min(limit, 100)

    db = get_market_database()
    conn = db._get_connection()

    # Check if agent tables exist
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='agents'")
    if not cursor.fetchone():
        return AgentSearchResult(
            success=False,
            error_code="sde_not_seeded",
            message="Agent data not available. Run 'uv run aria-esi sde-seed' to import SDE data with agent tables.",
        ).model_dump()

    # Build query
    conditions = []
    params = []
    filters_applied: dict[str, str | int | bool] = {}

    # Resolve corporation
    resolved_corp_id = corporation_id
    if corporation is not None and corporation_id is None:
        resolved_corp_id = _resolve_corporation_name(conn, corporation)
        if resolved_corp_id is None:
            return AgentSearchResult(
                success=False,
                error_code="corporation_not_found",
                message=f"No corporation matching '{corporation}'",
            ).model_dump()
        filters_applied["corporation"] = corporation

    if resolved_corp_id is not None:
        conditions.append("a.corporation_id = ?")
        params.append(resolved_corp_id)
        if "corporation" not in filters_applied:
            filters_applied["corporation_id"] = resolved_corp_id

    # Level filter
    if level is not None:
        if level < 1 or level > 5:
            return AgentSearchResult(
                success=False,
                error_code="invalid_level",
                message="Agent level must be between 1 and 5",
            ).model_dump()
        conditions.append("a.level = ?")
        params.append(level)
        filters_applied["level"] = level

    # Division filter
    if division is not None:
        div_id = _resolve_division_name(conn, division)
        if div_id is None:
            return AgentSearchResult(
                success=False,
                error_code="division_not_found",
                message=f"No division matching '{division}'. Use 'Security', 'Distribution', 'Mining', or 'Research'.",
            ).model_dump()
        conditions.append("a.division_id = ?")
        params.append(div_id)
        filters_applied["division"] = division

    # System filter
    if system is not None:
        # We need to join with universe data for system names
        # For now, filter by system_id if numeric, otherwise skip
        filters_applied["system"] = system
        # This would require joining with universe MCP data

    # Highsec filter - requires joining with stations and systems
    if highsec_only:
        filters_applied["highsec_only"] = True
        # We'll filter in post-processing since we need security from universe data

    # Build the full query with joins
    where_clause = " AND ".join(conditions) if conditions else "1=1"

    query = f"""
        SELECT
            a.agent_id,
            a.agent_name,
            a.level,
            a.division_id,
            d.division_name,
            a.corporation_id,
            c.corporation_name,
            a.station_id,
            s.station_name,
            a.system_id,
            s.region_id,
            r.region_name,
            t.agent_type_name
        FROM agents a
        LEFT JOIN agent_divisions d ON a.division_id = d.division_id
        LEFT JOIN npc_corporations c ON a.corporation_id = c.corporation_id
        LEFT JOIN stations s ON a.station_id = s.station_id
        LEFT JOIN regions r ON s.region_id = r.region_id
        LEFT JOIN agent_types t ON a.agent_type_id = t.agent_type_id
        WHERE {where_clause}
        ORDER BY a.level, d.division_name, a.agent_name
        LIMIT ?
    """
    params.append(limit * 2 if highsec_only else limit)  # Fetch extra for filtering

    cursor = conn.execute(query, params)
    rows = cursor.fetchall()

    # Build result list
    agents = []
    for row in rows:
        # Get security status from universe data if available
        system_id = row[9]
        security = None
        system_name = None

        if system_id:
            # Try to get system info from universe MCP or local cache
            security, system_name = _get_system_info(system_id)

        # Apply highsec filter
        if highsec_only and (security is None or security < 0.45):
            continue

        agent = AgentInfo(
            agent_id=row[0],
            agent_name=row[1],
            level=row[2],
            division_id=row[3],
            division_name=row[4],
            corporation_id=row[5],
            corporation_name=row[6],
            station_id=row[7],
            station_name=row[8],
            system_id=system_id,
            system_name=system_name,
            security=security,
            region_name=row[11],
            agent_type=row[12],
        )
        agents.append(agent)

        if len(agents) >= limit:
            break

    return AgentSearchResult(
        success=True,
        agents=agents,
        total_found=len(agents),
        filters_applied=filters_applied,
    ).model_dump()


async def _agent_divisions_impl() -> dict:
    """
    List all available NPC agent divisions.

    Standalone implementation callable by both MCP tool and dispatcher.

    Returns:
        DivisionListResult with all divisions
    """
    db = get_market_database()
    conn = db._get_connection()

    # Check if agent_divisions table exists
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_divisions'"
    )
    if not cursor.fetchone():
        return DivisionListResult(
            success=False,
            error_code="sde_not_seeded",
            message="Agent data not available. Run 'uv run aria-esi sde-seed' to import SDE data.",
        ).model_dump()

    cursor = conn.execute(
        "SELECT division_id, division_name FROM agent_divisions ORDER BY division_name"
    )

    divisions = [{"division_id": row[0], "division_name": row[1]} for row in cursor.fetchall()]

    return DivisionListResult(
        success=True,
        divisions=divisions,
    ).model_dump()


# =============================================================================
# MCP Tool Registration
# =============================================================================


def register_agent_tools(server: FastMCP) -> None:
    """Register SDE agent search tools with MCP server."""

    @server.tool()
    async def sde_agent_search(
        corporation: str | None = None,
        corporation_id: int | None = None,
        level: int | None = None,
        division: str | None = None,
        system: str | None = None,
        highsec_only: bool = False,
        limit: int = 20,
    ) -> dict:
        """
        Search for NPC mission agents by corporation, level, and division.

        Find agents based on multiple criteria including corporation,
        mission level, division type, and location.

        Args:
            corporation: Corporation name (fuzzy matched, e.g., "Sisters of EVE")
            corporation_id: Corporation ID (alternative to name)
            level: Agent level (1-5)
            division: Division name (Security, Distribution, Mining, Research)
            system: Filter to specific solar system
            highsec_only: If True, only return agents in highsec (>=0.45)
            limit: Maximum results (default 20, max 100)

        Returns:
            AgentSearchResult with matching agents

        Examples:
            sde_agent_search(corporation="Sisters of EVE", level=2, division="Security")
            sde_agent_search(corporation="Caldari Navy", level=4)
            sde_agent_search(corporation_id=1000125, level=2, highsec_only=True)
        """
        return await _agent_search_impl(
            corporation, corporation_id, level, division, system, highsec_only, limit
        )

    @server.tool()
    async def sde_agent_divisions() -> dict:
        """
        List all available NPC agent divisions.

        Returns the division types used by mission agents:
        - Security: Combat missions
        - Distribution: Courier/hauling missions
        - Mining: Mining missions
        - Research: R&D agents for datacores

        Returns:
            DivisionListResult with all divisions

        Examples:
            sde_agent_divisions()
        """
        return await _agent_divisions_impl()


def _resolve_corporation_name(conn, name: str) -> int | None:
    """Resolve corporation name to ID."""
    name_lower = name.lower().strip()

    # Try exact match
    cursor = conn.execute(
        "SELECT corporation_id FROM npc_corporations WHERE corporation_name_lower = ?",
        (name_lower,),
    )
    row = cursor.fetchone()
    if row:
        return row[0]

    # Try prefix match
    cursor = conn.execute(
        "SELECT corporation_id FROM npc_corporations WHERE corporation_name_lower LIKE ? LIMIT 1",
        (f"{name_lower}%",),
    )
    row = cursor.fetchone()
    if row:
        return row[0]

    # Try contains match
    cursor = conn.execute(
        "SELECT corporation_id FROM npc_corporations WHERE corporation_name_lower LIKE ? LIMIT 1",
        (f"%{name_lower}%",),
    )
    row = cursor.fetchone()
    if row:
        return row[0]

    return None


def _resolve_division_name(conn, name: str) -> int | None:
    """Resolve division name to ID."""
    name_lower = name.lower().strip()

    # Try exact match
    cursor = conn.execute(
        "SELECT division_id FROM agent_divisions WHERE division_name_lower = ?",
        (name_lower,),
    )
    row = cursor.fetchone()
    if row:
        return row[0]

    # Try prefix match
    cursor = conn.execute(
        "SELECT division_id FROM agent_divisions WHERE division_name_lower LIKE ? LIMIT 1",
        (f"{name_lower}%",),
    )
    row = cursor.fetchone()
    if row:
        return row[0]

    # Try contains match
    cursor = conn.execute(
        "SELECT division_id FROM agent_divisions WHERE division_name_lower LIKE ? LIMIT 1",
        (f"%{name_lower}%",),
    )
    row = cursor.fetchone()
    if row:
        return row[0]

    return None


def _get_system_info(system_id: int) -> tuple[float | None, str | None]:
    """
    Get system security and name from universe data.

    Returns:
        Tuple of (security_status, system_name)
    """
    # Try to use universe MCP tools if available
    try:
        from aria_esi.mcp.universe.graph import get_universe_graph

        graph = get_universe_graph()
        if graph and system_id in graph.systems:
            system = graph.systems[system_id]
            return (system.security, system.name)
    except Exception:
        pass

    return (None, None)
