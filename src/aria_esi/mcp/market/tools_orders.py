"""
Market Orders MCP Tools.

Provides market_orders tool for detailed order book queries.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aria_esi.core.logging import get_logger
from aria_esi.mcp.market.database import get_market_database
from aria_esi.models.market import (
    TRADE_HUBS,
    MarketOrder,
    MarketOrdersResult,
    RegionConfig,
    resolve_trade_hub,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = get_logger("aria_market.tools_orders")


def register_order_tools(server: FastMCP) -> None:
    """Register market order tools with MCP server."""

    @server.tool()
    async def market_orders(
        item: str,
        region: str = "jita",
        region_id: int | None = None,
        order_type: str = "all",
        limit: int = 10,
    ) -> dict:
        """
        Get detailed market orders from ESI.

        Returns individual buy and sell orders sorted by price.
        More detailed than market_prices but slower (direct ESI query).

        Args:
            item: Item name to look up (case-insensitive)
            region: Trade hub name (jita, amarr, dodixie, rens, hek)
            region_id: Direct region ID (bypasses trade hub resolution, use for NPC regions)
            order_type: Filter by order type ("buy", "sell", "all")
            limit: Maximum orders to return per side (default 10, max 50)

        Returns:
            MarketOrdersResult with detailed order book

        Examples:
            market_orders("PLEX")
            market_orders("Tritanium", region="amarr", limit=5)
            market_orders("Veldspar", order_type="sell")
            market_orders("Pioneer Blueprint", region_id=10000057)
        """
        # If region_id provided directly, use it (for NPC regions)
        hub: RegionConfig
        if region_id is not None:
            hub = RegionConfig(
                region_id=region_id,
                region_name=f"Region {region_id}",  # Generic name for non-trade-hub regions
                station_id=None,
                station_name=None,
                system_id=None,
            )
        else:
            # Resolve trade hub
            trade_hub = resolve_trade_hub(region)
            if not trade_hub:
                trade_hub = TRADE_HUBS["jita"]
            hub = RegionConfig(
                region_id=trade_hub["region_id"],
                region_name=trade_hub["region_name"],
                station_id=trade_hub["station_id"],
                station_name=trade_hub["station_name"],
                system_id=trade_hub["system_id"],
            )

        # Clamp limit
        limit = max(1, min(50, limit))

        # Resolve item name
        db = get_market_database()
        type_info = db.resolve_type_name(item)

        if not type_info:
            # Try to find suggestions
            suggestions = db.find_type_suggestions(item)
            return {
                "error": {
                    "code": "TYPE_NOT_FOUND",
                    "message": f"Unknown item: {item}",
                    "data": {"suggestions": suggestions},
                }
            }

        type_id = type_info.type_id
        type_name = type_info.type_name
        resolved_region_id: int = hub["region_id"]

        # Fetch orders from ESI
        from aria_esi.mcp.esi_client import get_async_esi_client

        buy_orders: list[dict] = []
        sell_orders: list[dict] = []
        warnings: list[str] = []

        try:
            client = await get_async_esi_client()

            # Fetch orders based on order_type
            if order_type in ("all", "buy"):
                try:
                    data = await client.get(
                        f"/markets/{resolved_region_id}/orders/",
                        params={"type_id": str(type_id), "order_type": "buy"},
                    )
                    if isinstance(data, list):
                        buy_orders = data
                except Exception as e:
                    logger.warning("Failed to fetch buy orders: %s", e)
                    warnings.append(f"Buy orders unavailable: {e}")

            if order_type in ("all", "sell"):
                try:
                    data = await client.get(
                        f"/markets/{resolved_region_id}/orders/",
                        params={"type_id": str(type_id), "order_type": "sell"},
                    )
                    if isinstance(data, list):
                        sell_orders = data
                except Exception as e:
                    logger.warning("Failed to fetch sell orders: %s", e)
                    warnings.append(f"Sell orders unavailable: {e}")

        except Exception as e:
            return {
                "error": {
                    "code": "ESI_UNAVAILABLE",
                    "message": f"ESI client error: {e}",
                }
            }

        # Sort orders
        buy_orders.sort(key=lambda x: x.get("price", 0), reverse=True)  # Highest first
        sell_orders.sort(key=lambda x: x.get("price", float("inf")))  # Lowest first

        # Convert to model objects
        def convert_order(order: dict) -> MarketOrder:
            return MarketOrder(
                order_id=order.get("order_id", 0),
                type_id=order.get("type_id", type_id),
                is_buy_order=order.get("is_buy_order", False),
                price=order.get("price", 0),
                volume_remain=order.get("volume_remain", 0),
                volume_total=order.get("volume_total", 0),
                location_id=order.get("location_id", 0),
                location_name=None,  # Would need additional ESI call
                system_id=order.get("system_id", 0),
                system_name=None,  # Would need additional ESI call
                range=order.get("range", "station"),
                min_volume=order.get("min_volume", 1),
                duration=order.get("duration", 0),
                issued=order.get("issued", ""),
            )

        buy_models = [convert_order(o) for o in buy_orders[:limit]]
        sell_models = [convert_order(o) for o in sell_orders[:limit]]

        # Calculate best prices and spread
        best_buy = buy_orders[0]["price"] if buy_orders else None
        best_sell = sell_orders[0]["price"] if sell_orders else None

        spread = None
        spread_percent = None
        if best_buy is not None and best_sell is not None:
            spread = round(best_sell - best_buy, 2)
            if best_sell > 0:
                spread_percent = round((spread / best_sell) * 100, 2)

        result = MarketOrdersResult(
            type_id=type_id,
            type_name=type_name,
            region=hub["region_name"],
            region_id=resolved_region_id,
            buy_orders=buy_models,
            sell_orders=sell_models,
            total_buy_orders=len(buy_orders),
            total_sell_orders=len(sell_orders),
            best_buy=round(best_buy, 2) if best_buy else None,
            best_sell=round(best_sell, 2) if best_sell else None,
            spread=spread,
            spread_percent=spread_percent,
            freshness="fresh",  # Direct ESI query
            warnings=warnings,
        )

        return result.model_dump()
