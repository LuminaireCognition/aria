"""
Market Price MCP Tools.

Provides market_prices and market_cache_status tools for price queries.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aria_esi.core.logging import get_logger
from aria_esi.mcp.market.cache import MarketCache, get_market_cache
from aria_esi.mcp.market.database import get_market_database
from aria_esi.models.market import (
    FreshnessLevel,
    MarketCacheLayerStatus,
    MarketCacheStatusResult,
    MarketPricesResult,
    resolve_region,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = get_logger("aria_market.tools_prices")


def register_price_tools(server: FastMCP) -> None:
    """Register market price tools with MCP server."""

    @server.tool()
    async def market_prices(
        items: list[str],
        region: str = "jita",
        station_only: bool = True,
    ) -> dict:
        """
        Get aggregated prices for multiple items.

        PREFER THIS TOOL over manual ESI market queries. Provides:
        - Fuzzwork aggregated prices (buy/sell min/max/avg)
        - Spread calculation
        - Station-filtered data (Jita 4-4 by default)
        - Automatic type name resolution

        Args:
            items: List of item names to look up (case-insensitive)
            region: Region name - supports trade hubs (jita, amarr, dodixie, rens, hek)
                   and any EVE region name (e.g., "Everyshore", "Outer Ring")
            station_only: If True, filter to trade hub station orders (trade hubs only)

        Returns:
            MarketPricesResult with per-item price data

        Examples:
            market_prices(["Tritanium", "Pyerite", "Mexallon"])
            market_prices(["PLEX"], region="amarr")
            market_prices(["Veldspar"], station_only=False)
            market_prices(["Tritanium"], region="Everyshore")
        """
        # Resolve region (supports trade hubs, region names, and numeric IDs)
        hub = resolve_region(region)
        if not hub:
            hub = resolve_region("jita")
            region = "jita"

        # Determine if this is a trade hub (has Fuzzwork data) or arbitrary region
        is_trade_hub = hub.get("station_id") is not None

        # Resolve item names to type IDs
        db = get_market_database()
        type_ids: list[int] = []
        type_names: dict[int, str] = {}
        unresolved: list[str] = []

        for item_name in items:
            type_info = db.resolve_type_name(item_name)
            if type_info:
                type_ids.append(type_info.type_id)
                type_names[type_info.type_id] = type_info.type_name
            else:
                unresolved.append(item_name)

        # Get prices from cache
        # For non-trade-hub regions, pass region_id directly to use ESI
        if is_trade_hub:
            cache = MarketCache(region=region, station_only=station_only)
        else:
            cache = MarketCache(
                region_id=hub["region_id"],
                region_name=hub["region_name"],
                station_only=False,  # No station filtering for non-trade-hub regions
            )
        prices = await cache.get_prices(type_ids, type_names)

        # Build warnings
        warnings = []
        if unresolved:
            warnings.append(
                f"Could not resolve {len(unresolved)} items: {', '.join(unresolved[:5])}"
            )
            if len(unresolved) > 5:
                warnings.append(f"...and {len(unresolved) - 5} more unresolved items")

        # Determine overall freshness
        freshness: FreshnessLevel = "fresh"
        for price in prices:
            if price.freshness == "stale":
                freshness = "stale"
                break
            elif price.freshness == "recent" and freshness == "fresh":
                freshness = "recent"

        # Get cache age and determine source
        cache_status = cache.get_cache_status()
        if is_trade_hub:
            cache_age = cache_status.get("fuzzwork", {}).get("age_seconds")
            source = "fuzzwork"
        else:
            cache_age = None  # ESI data is fetched fresh
            source = "esi"

        result = MarketPricesResult(
            items=prices,
            region=hub["region_name"],
            region_id=hub["region_id"],
            station=hub.get("station_name") if station_only and is_trade_hub else None,
            station_id=hub.get("station_id") if station_only and is_trade_hub else None,
            source=source,
            freshness=freshness,
            cache_age_seconds=cache_age,
            unresolved_items=unresolved,
            warnings=warnings,
        )

        return result.model_dump()

    @server.tool()
    async def market_cache_status() -> dict:
        """
        Get diagnostic information about market cache layers.

        Returns status for:
        - Fuzzwork cache (aggregated prices)
        - ESI orders cache (detailed orders)
        - Database (persistent cache)

        Useful for debugging cache behavior and data freshness.

        Returns:
            MarketCacheStatusResult with layer-by-layer status
        """
        cache = get_market_cache()
        status = cache.get_cache_status()

        # Get database stats
        db = get_market_database()
        db_stats = db.get_stats()

        result = MarketCacheStatusResult(
            fuzzwork=MarketCacheLayerStatus(
                name="fuzzwork",
                cached_types=status.get("fuzzwork", {}).get("cached_types", 0),
                age_seconds=status.get("fuzzwork", {}).get("age_seconds"),
                ttl_seconds=status.get("fuzzwork", {}).get("ttl_seconds", 900),
                stale=status.get("fuzzwork", {}).get("stale", True),
                last_error=status.get("fuzzwork", {}).get("last_error"),
            ),
            esi_orders=MarketCacheLayerStatus(
                name="esi_orders",
                cached_types=status.get("esi_orders", {}).get("cached_types", 0),
                age_seconds=status.get("esi_orders", {}).get("age_seconds"),
                ttl_seconds=status.get("esi_orders", {}).get("ttl_seconds", 300),
                stale=status.get("esi_orders", {}).get("stale", True),
                last_error=status.get("esi_orders", {}).get("last_error"),
            ),
            esi_history=MarketCacheLayerStatus(
                name="esi_history",
                cached_types=0,  # Not implemented yet
                age_seconds=None,
                ttl_seconds=3600,
                stale=True,
                last_error=None,
            ),
            database_path=db_stats.get("database_path"),
            database_size_mb=round(db_stats.get("database_size_mb", 0), 2),
            type_count=db_stats.get("type_count", 0),
            common_items_cached=0,  # Not implemented yet
        )

        return result.model_dump()
