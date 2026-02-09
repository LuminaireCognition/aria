"""
Market Valuation MCP Tools.

Provides market_valuation tool for inventory valuation with EVE clipboard support.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aria_esi.core.logging import get_logger
from aria_esi.mcp.market.cache import MarketCache
from aria_esi.mcp.market.clipboard import parse_clipboard_to_dict
from aria_esi.mcp.market.database import get_market_database
from aria_esi.models.market import (
    TRADE_HUBS,
    FreshnessLevel,
    PriceType,
    ValuationItem,
    ValuationResult,
    resolve_trade_hub,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = get_logger("aria_market.tools_valuation")


def register_valuation_tools(server: FastMCP) -> None:
    """Register market valuation tools with MCP server."""

    @server.tool()
    async def market_valuation(
        items: list[dict] | str,
        price_type: str = "sell",
        region: str = "jita",
    ) -> dict:
        """
        Calculate total value of item list with per-item breakdown.

        Accepts either:
        - List of {"name": str, "quantity": int} dicts
        - Raw EVE clipboard text (auto-parsed)

        Args:
            items: List of item dicts OR raw clipboard text
            price_type: "sell" (instant buy price) or "buy" (instant sell price)
            region: Trade hub name (jita, amarr, dodixie, rens, hek)

        Returns:
            ValuationResult with itemized breakdown and total value

        Examples:
            # With structured input
            market_valuation([
                {"name": "Tritanium", "quantity": 1000000},
                {"name": "Pyerite", "quantity": 500000}
            ])

            # With raw clipboard
            market_valuation("Tritanium\\t1000000\\nPyerite\\t500000")

            # Using buy prices (instant sell)
            market_valuation([{"name": "PLEX", "quantity": 1}], price_type="buy")
        """
        # Validate and narrow price_type
        validated_price_type: PriceType = "sell" if price_type != "buy" else "buy"

        # Resolve trade hub
        hub = resolve_trade_hub(region)
        if not hub:
            hub = TRADE_HUBS["jita"]

        # Parse clipboard if string input
        if isinstance(items, str):
            items = parse_clipboard_to_dict(items)

        if not items:
            return {
                "error": {
                    "code": "NO_ITEMS",
                    "message": "No items provided or parsed",
                }
            }

        # Validate price_type
        if price_type not in ("buy", "sell"):
            price_type = "sell"

        # Resolve item names and get prices
        db = get_market_database()
        cache = MarketCache(region=region, station_only=True)

        # Collect type IDs
        type_ids: list[int] = []
        type_names: dict[int, str] = {}
        quantities: dict[int, int] = {}
        unresolved_items: list[dict] = []

        for item in items:
            name = item.get("name", "")
            qty = item.get("quantity", 1)

            type_info = db.resolve_type_name(name)
            if type_info:
                type_id = type_info.type_id
                type_ids.append(type_id)
                type_names[type_id] = type_info.type_name
                # Accumulate quantity if same item appears multiple times
                quantities[type_id] = quantities.get(type_id, 0) + qty
            else:
                unresolved_items.append(item)

        # Fetch prices
        prices = await cache.get_prices(type_ids, type_names)
        price_map = {p.type_id: p for p in prices}

        # Build valuation results
        valuation_items: list[ValuationItem] = []
        total_value = 0.0
        total_quantity = 0
        resolved_count = 0

        for type_id, qty in quantities.items():
            price_data = price_map.get(type_id)
            name = type_names.get(type_id, f"Type {type_id}")

            if price_data:
                # Get price based on validated_price_type
                if validated_price_type == "sell":
                    unit_price = price_data.sell.min_price
                else:
                    unit_price = price_data.buy.max_price

                if unit_price:
                    item_total = unit_price * qty
                    total_value += item_total
                    total_quantity += qty
                    resolved_count += 1

                    valuation_items.append(
                        ValuationItem(
                            type_id=type_id,
                            type_name=name,
                            quantity=qty,
                            unit_price=round(unit_price, 2),
                            total_value=round(item_total, 2),
                            resolved=True,
                        )
                    )
                else:
                    # No price available
                    total_quantity += qty
                    valuation_items.append(
                        ValuationItem(
                            type_id=type_id,
                            type_name=name,
                            quantity=qty,
                            unit_price=None,
                            total_value=None,
                            resolved=True,
                            warning="No market data available",
                        )
                    )
            else:
                total_quantity += qty
                valuation_items.append(
                    ValuationItem(
                        type_id=type_id,
                        type_name=name,
                        quantity=qty,
                        unit_price=None,
                        total_value=None,
                        resolved=True,
                        warning="Price lookup failed",
                    )
                )

        # Add unresolved items
        for item in unresolved_items:
            name = item.get("name", "Unknown")
            qty = item.get("quantity", 1)
            total_quantity += qty

            valuation_items.append(
                ValuationItem(
                    type_id=None,
                    type_name=name,
                    quantity=qty,
                    unit_price=None,
                    total_value=None,
                    resolved=False,
                    warning="Could not resolve item name",
                )
            )

        # Build warnings
        warnings: list[str] = []
        if unresolved_items:
            warnings.append(f"{len(unresolved_items)} items could not be resolved")

        no_price_count = sum(1 for v in valuation_items if v.resolved and v.unit_price is None)
        if no_price_count:
            warnings.append(f"{no_price_count} items have no market data")

        # Get freshness
        freshness: FreshnessLevel = "fresh"
        cache_status = cache.get_cache_status()
        age = cache_status.get("fuzzwork", {}).get("age_seconds")
        if age:
            if age > 1800:
                freshness = "stale"
            elif age > 300:
                freshness = "recent"

        result = ValuationResult(
            items=valuation_items,
            total_value=round(total_value, 2),
            total_quantity=total_quantity,
            resolved_count=resolved_count,
            unresolved_count=len(unresolved_items),
            price_type=validated_price_type,
            region=hub["region_name"],
            region_id=hub["region_id"],
            freshness=freshness,
            warnings=warnings,
        )

        return result.model_dump()
