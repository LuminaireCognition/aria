"""
Market Analysis MCP Tools.

Provides market_spread tool for cross-region price comparison.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aria_esi.core.logging import get_logger
from aria_esi.models.market import (
    GLOBAL_MARKET_TYPE_IDS,
    GLOBAL_PLEX_MARKET_REGION_ID,
    TRADE_HUBS,
    FreshnessLevel,
    ItemSpread,
    MarketSpreadResult,
    RegionPrice,
)
from aria_esi.store.market.cache import MarketCache
from aria_esi.store.market.database import get_market_database

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = get_logger("aria_market.tools_analysis")


def register_analysis_tools(server: FastMCP) -> None:
    """Register market analysis tools with MCP server."""

    @server.tool()
    async def market_spread(
        items: list[str],
        regions: list[str] | None = None,
    ) -> dict:
        """
        Compare prices across regions for arbitrage analysis.

        Queries all major trade hubs to find the best buy and sell
        locations for each item.

        Args:
            items: List of item names to compare
            regions: Optional list of regions (defaults to all trade hubs)

        Returns:
            MarketSpreadResult with per-item cross-region comparison

        Examples:
            market_spread(["Tritanium", "Pyerite"])
            market_spread(["PLEX"], regions=["jita", "amarr"])
        """
        # Default to all trade hubs
        if not regions:
            regions = ["jita", "amarr", "dodixie", "rens", "hek"]

        # Validate regions
        valid_regions = [r for r in regions if r.lower() in TRADE_HUBS]
        if not valid_regions:
            valid_regions = list(TRADE_HUBS.keys())

        # Resolve item names
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

        if not type_ids:
            return {
                "error": {
                    "code": "NO_ITEMS_RESOLVED",
                    "message": "Could not resolve any item names",
                    "data": {"unresolved": unresolved},
                }
            }

        # Fetch prices from each region (skip global market items — handled separately)
        regional_type_ids = [tid for tid in type_ids if tid not in GLOBAL_MARKET_TYPE_IDS]
        region_prices: dict[str, dict[int, dict]] = {}  # region -> type_id -> prices

        for region in valid_regions:
            hub = TRADE_HUBS[region.lower()]
            cache = MarketCache(region=region, station_only=True)

            try:
                prices = await cache.get_prices(regional_type_ids, type_names)
                region_prices[region] = {
                    p.type_id: {
                        "buy_max": p.buy.max_price,
                        "sell_min": p.sell.min_price,
                        "buy_volume": p.buy.volume,
                        "sell_volume": p.sell.volume,
                    }
                    for p in prices
                }
            except Exception as e:  # noqa: BLE001 -- MCP handler
                logger.warning("Failed to fetch prices from %s: %s", region, e)
                region_prices[region] = {}

        # Fetch prices for global market items (e.g. PLEX) via ESI region 19000001
        global_prices: dict[int, dict] = {}
        for type_id in type_ids:
            if type_id in GLOBAL_MARKET_TYPE_IDS:
                try:
                    from aria_esi.store.esi_client import get_async_esi_client

                    client = await get_async_esi_client()
                    buy_orders = await client.get(
                        f"/markets/{GLOBAL_PLEX_MARKET_REGION_ID}/orders/",
                        params={"type_id": str(type_id), "order_type": "buy"},
                    )
                    sell_orders = await client.get(
                        f"/markets/{GLOBAL_PLEX_MARKET_REGION_ID}/orders/",
                        params={"type_id": str(type_id), "order_type": "sell"},
                    )
                    buy_orders = sorted(
                        (buy_orders or []) if isinstance(buy_orders, list) else [],
                        key=lambda x: x.get("price", 0),
                        reverse=True,
                    )
                    sell_orders = sorted(
                        (sell_orders or []) if isinstance(sell_orders, list) else [],
                        key=lambda x: x.get("price", float("inf")),
                    )
                    global_prices[type_id] = {
                        "buy_max": buy_orders[0]["price"] if buy_orders else None,
                        "sell_min": sell_orders[0]["price"] if sell_orders else None,
                        "buy_volume": sum(o.get("volume_remain", 0) for o in buy_orders),
                        "sell_volume": sum(o.get("volume_remain", 0) for o in sell_orders),
                    }
                except Exception as e:  # noqa: BLE001 -- MCP handler
                    logger.warning("Failed to fetch global market prices for %d: %s", type_id, e)
                    global_prices[type_id] = {}

        # Build spread analysis for each item
        item_spreads: list[ItemSpread] = []
        warnings: list[str] = []

        for type_id in type_ids:
            name = type_names.get(type_id, f"Type {type_id}")

            # Global market items get a single universal entry instead of 5 null hub entries
            if type_id in GLOBAL_MARKET_TYPE_IDS:
                price_data = global_prices.get(type_id, {})
                buy_price = price_data.get("buy_max")
                sell_price = price_data.get("sell_min")
                region_data = [
                    RegionPrice(
                        region="Global PLEX Market",
                        region_id=GLOBAL_PLEX_MARKET_REGION_ID,
                        buy_price=round(buy_price, 2) if buy_price else None,
                        sell_price=round(sell_price, 2) if sell_price else None,
                        buy_volume=price_data.get("buy_volume", 0),
                        sell_volume=price_data.get("sell_volume", 0),
                    )
                ]
                item_spreads.append(
                    ItemSpread(
                        type_id=type_id,
                        type_name=name,
                        regions=region_data,
                        best_buy_region="Global PLEX Market" if buy_price else None,
                        best_sell_region="Global PLEX Market" if sell_price else None,
                        arbitrage_profit=None,
                        arbitrage_percent=None,
                    )
                )
                warnings.append(
                    f"{name} trades on the Global PLEX Market (single universal market — no regional arbitrage)"
                )
                continue

            region_data = []
            best_buy_region = None
            best_buy_price = 0.0
            best_sell_region = None
            best_sell_price = float("inf")

            for region in valid_regions:
                hub = TRADE_HUBS[region.lower()]
                price_data = region_prices.get(region, {}).get(type_id, {})

                buy_price = price_data.get("buy_max")
                sell_price = price_data.get("sell_min")
                buy_volume = price_data.get("buy_volume", 0)
                sell_volume = price_data.get("sell_volume", 0)

                region_data.append(
                    RegionPrice(
                        region=hub["region_name"],
                        region_id=hub["region_id"],
                        buy_price=round(buy_price, 2) if buy_price else None,
                        sell_price=round(sell_price, 2) if sell_price else None,
                        buy_volume=buy_volume,
                        sell_volume=sell_volume,
                    )
                )

                # Track best buy (highest)
                if buy_price and buy_price > best_buy_price:
                    best_buy_price = buy_price
                    best_buy_region = hub["region_name"]

                # Track best sell (lowest)
                if sell_price and sell_price < best_sell_price:
                    best_sell_price = sell_price
                    best_sell_region = hub["region_name"]

            # Calculate arbitrage potential
            arbitrage_profit = None
            arbitrage_percent = None
            if best_buy_price > 0 and best_sell_price < float("inf"):
                arbitrage_profit = round(best_buy_price - best_sell_price, 2)
                if best_sell_price > 0:
                    arbitrage_percent = round((arbitrage_profit / best_sell_price) * 100, 2)

            item_spreads.append(
                ItemSpread(
                    type_id=type_id,
                    type_name=name,
                    regions=region_data,
                    best_buy_region=best_buy_region,
                    best_sell_region=best_sell_region,
                    arbitrage_profit=arbitrage_profit
                    if arbitrage_profit and arbitrage_profit > 0
                    else None,
                    arbitrage_percent=arbitrage_percent
                    if arbitrage_percent and arbitrage_percent > 0
                    else None,
                )
            )

        if unresolved:
            warnings.append(
                f"Could not resolve {len(unresolved)} items: {', '.join(unresolved[:3])}"
            )

        # Check overall freshness
        freshness: FreshnessLevel = "fresh"  # Multiple caches, assume fresh for now

        result = MarketSpreadResult(
            items=item_spreads,
            regions_queried=[TRADE_HUBS[r.lower()]["region_name"] for r in valid_regions],
            freshness=freshness,
            warnings=warnings,
        )

        return result.model_dump()
