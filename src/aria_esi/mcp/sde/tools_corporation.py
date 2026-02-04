"""
SDE Corporation Info MCP Tool.

Provides NPC corporation information including station regions
and seeding statistics.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from aria_esi.core.logging import get_logger
from aria_esi.mcp.market.database import get_market_database
from aria_esi.mcp.sde.queries import SDENotSeededError, get_sde_query_service

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = get_logger("aria_sde.tools_corporation")


# =============================================================================
# Models
# =============================================================================


class CorporationModel(BaseModel):
    """Base model for corporation data."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class CorporationRegion(CorporationModel):
    """Region where corporation has stations."""

    region_id: int = Field(ge=1, description="Region ID")
    region_name: str = Field(description="Region name")
    station_count: int = Field(ge=0, description="Number of stations in this region")
    is_primary: bool = Field(description="True if this is the region with most stations")


class CorporationInfoResult(CorporationModel):
    """Result from sde_corporation_info tool."""

    success: bool = Field(description="Whether the lookup succeeded")
    corporation_id: int | None = Field(default=None, ge=1, description="Corporation ID")
    corporation_name: str | None = Field(default=None, description="Corporation name")
    faction_id: int | None = Field(default=None, description="Faction ID if affiliated")
    station_count: int = Field(default=0, ge=0, description="Total stations")
    regions: list[CorporationRegion] = Field(
        default_factory=list, description="Regions with stations"
    )
    seeds_items: bool = Field(default=False, description="True if corporation seeds items")
    seeded_item_count: int = Field(default=0, ge=0, description="Number of items seeded")
    error_code: str | None = Field(default=None, description="Error code if failed")
    message: str | None = Field(default=None, description="Error or status message")
    suggestions: list[str] = Field(default_factory=list, description="Name suggestions")


# =============================================================================
# Tool Registration
# =============================================================================


# =============================================================================
# Standalone Implementation Functions (for dispatcher imports)
# =============================================================================


async def _corporation_info_impl(
    corporation_id: int | None = None,
    corporation_name: str | None = None,
) -> dict:
    """
    Get NPC corporation information including station regions.

    Standalone implementation callable by both MCP tool and dispatcher.

    Args:
        corporation_id: Corporation ID to look up
        corporation_name: Corporation name (fuzzy matched)

    Returns:
        CorporationInfoResult with corporation details
    """
    # Validate input
    if corporation_id is None and corporation_name is None:
        return CorporationInfoResult(
            success=False,
            error_code="missing_parameter",
            message="Either corporation_id or corporation_name must be provided",
        ).model_dump()

    db = get_market_database()
    conn = db._get_connection()

    # Check if SDE tables exist
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='npc_corporations'"
    )
    if not cursor.fetchone():
        return CorporationInfoResult(
            success=False,
            error_code="sde_not_seeded",
            message="SDE data not seeded. Run 'uv run aria-esi sde-seed' first.",
        ).model_dump()

    # Resolve corporation ID if name provided
    resolved_id = corporation_id
    if corporation_name is not None and corporation_id is None:
        resolved_id = _resolve_corporation_name(conn, corporation_name)
        if resolved_id is None:
            # Try to find suggestions
            suggestions = _find_corporation_suggestions(conn, corporation_name)
            return CorporationInfoResult(
                success=False,
                error_code="corporation_not_found",
                message=f"No corporation matching '{corporation_name}'",
                suggestions=suggestions,
            ).model_dump()

    # Guard for type narrowing - we should have a resolved_id by now
    if resolved_id is None:
        return CorporationInfoResult(
            success=False,
            error_code="missing_parameter",
            message="Corporation ID could not be resolved",
        ).model_dump()

    # Get corporation info from query service
    try:
        service = get_sde_query_service()
        corp_info = service.get_corporation_info(resolved_id)
    except SDENotSeededError as e:
        return CorporationInfoResult(
            success=False,
            error_code="sde_not_seeded",
            message=str(e),
        ).model_dump()

    if corp_info is None:
        return CorporationInfoResult(
            success=False,
            error_code="corporation_not_found",
            message=f"Corporation ID {resolved_id} not found",
        ).model_dump()

    # Build regions list
    regions = []
    for i, (region_id, region_name, station_count) in enumerate(corp_info.regions):
        regions.append(
            CorporationRegion(
                region_id=region_id,
                region_name=region_name,
                station_count=station_count,
                is_primary=(i == 0),
            )
        )

    return CorporationInfoResult(
        success=True,
        corporation_id=corp_info.corporation_id,
        corporation_name=corp_info.corporation_name,
        faction_id=corp_info.faction_id,
        station_count=corp_info.station_count,
        regions=regions,
        seeds_items=corp_info.seeds_items,
        seeded_item_count=corp_info.seeded_item_count,
    ).model_dump()


# =============================================================================
# MCP Tool Registration
# =============================================================================


def register_corporation_tools(server: FastMCP) -> None:
    """Register SDE corporation lookup tools with MCP server."""

    @server.tool()
    async def sde_corporation_info(
        corporation_id: int | None = None,
        corporation_name: str | None = None,
    ) -> dict:
        """
        Get NPC corporation information including station regions.

        Provides detailed information about an NPC corporation including:
        - All regions where they have stations
        - Whether they seed items (sell blueprints/modules)
        - How many items they seed

        Args:
            corporation_id: Corporation ID to look up
            corporation_name: Corporation name (fuzzy matched)

        Returns:
            CorporationInfoResult with corporation details

        Examples:
            sde_corporation_info(corporation_id=1000129)  # ORE
            sde_corporation_info(corporation_name="Sisters of EVE")
            sde_corporation_info(corporation_name="outer ring")  # Fuzzy match
        """
        return await _corporation_info_impl(corporation_id, corporation_name)


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


def _find_corporation_suggestions(conn, name: str, limit: int = 5) -> list[str]:
    """Find corporation name suggestions."""
    name_lower = name.lower().strip()

    cursor = conn.execute(
        """
        SELECT corporation_name FROM npc_corporations
        WHERE corporation_name_lower LIKE ?
        ORDER BY length(corporation_name)
        LIMIT ?
        """,
        (f"%{name_lower}%", limit),
    )

    return [row[0] for row in cursor.fetchall()]
