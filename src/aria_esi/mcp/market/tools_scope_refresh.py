"""
MCP Tool Registration for Market Scope Refresh.

Registers the market_scope_refresh tool with the MCP server.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aria_esi.mcp.market.database_async import get_async_market_database
from aria_esi.mcp.market.scope_refresh import MarketScopeFetcher
from aria_esi.models.market import ManagementError

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register_scope_refresh_tools(server: FastMCP) -> None:
    """
    Register scope refresh tools with MCP server.

    Args:
        server: FastMCP server instance
    """

    @server.tool()
    async def market_scope_refresh(
        scope_name: str,
        owner_character_id: int | None = None,
        force_refresh: bool = False,
        max_structure_pages: int = 5,
    ) -> dict:
        """
        Refresh market data for an ad-hoc scope.

        Fetches orders from ESI for all items in the scope's watchlist
        and stores aggregated prices in the database.

        IMPORTANT: This tool only works for ad-hoc scopes (region, station,
        system, structure). Core hub scopes use Fuzzwork aggregates and
        cannot be refreshed via this tool.

        Args:
            scope_name: Name of the scope to refresh
            owner_character_id: Character ID for scope lookup (None = global)
            force_refresh: Force refresh even if cached data is fresh
            max_structure_pages: Max pages to fetch for structure scopes (default 5)

        Returns:
            ScopeRefreshResult with refresh details:
            - items_refreshed: Number of watchlist items processed
            - items_with_orders: Items that had orders
            - items_without_orders: Items with zero orders
            - scan_status: 'complete', 'truncated', or 'error'
            - prices: Per-item price information
            - warnings/errors: Any issues encountered

        Scope Types:
            - region: Fetches orders per type_id from watchlist
            - station: Fetches region orders, filters by station location_id
            - system: Fetches region orders, filters by system_id
            - structure: Fetches ALL structure orders (paginated), filters by watchlist

        Structure Scopes:
            Structure scopes cannot filter ESI requests by type_id. All orders
            are fetched (up to max_structure_pages) then filtered locally.
            This is bandwidth-intensive. Large structures may have 50+ pages.

        Examples:
            # Refresh a region scope
            market_scope_refresh("everyshore_minerals")

            # Refresh with force refresh
            market_scope_refresh("my_station", force_refresh=True)

            # Refresh a structure with more pages
            market_scope_refresh("fortizar_market", max_structure_pages=10)
        """
        # Get database
        db = await get_async_market_database()

        # Look up scope
        scope = await db.get_scope(scope_name, owner_character_id)
        if scope is None:
            return ManagementError(
                code="SCOPE_NOT_FOUND",
                message=f"Scope '{scope_name}' not found",
                suggestions=[
                    "Use market_scope_list to see available scopes",
                    "Check scope name spelling",
                    "Verify owner_character_id if scope is character-owned",
                ],
            ).model_dump()

        # Create fetcher and refresh
        fetcher = MarketScopeFetcher(db)
        result = await fetcher.refresh_scope(
            scope,
            force_refresh=force_refresh,
            max_structure_pages=max_structure_pages,
        )

        return result.model_dump()
