"""
Market Dispatcher for MCP Server.

Consolidates 18 market tools into a single dispatcher:
- prices: Aggregated market prices
- orders: Detailed order book
- valuation: Inventory valuation
- spread: Cross-region price comparison
- history: Price history and trends
- find_nearby: Proximity-based market search
- npc_sources: Find NPC-seeded items
- arbitrage_scan: Cross-region arbitrage opportunities
- arbitrage_detail: Detailed opportunity analysis
- route_value: Hauling value and risk analysis
- watchlist_create/add_item/list/get/delete: Watchlist management
- scope_create/list/delete/refresh: Market scope management
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from ..context import log_context, wrap_output, wrap_output_multi
from ..context_policy import MARKET
from ..errors import InvalidParameterError
from ..policy import check_capability
from ..validation import add_validation_warnings, validate_action_params

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from aria_esi.universe.graph import UniverseGraph


MarketAction = Literal[
    "prices",
    "orders",
    "valuation",
    "spread",
    "history",
    "find_nearby",
    "npc_sources",
    "arbitrage_scan",
    "arbitrage_detail",
    "route_value",
    "watchlist_create",
    "watchlist_add_item",
    "watchlist_list",
    "watchlist_get",
    "watchlist_delete",
    "scope_create",
    "scope_list",
    "scope_delete",
    "scope_refresh",
]

VALID_ACTIONS: set[str] = {
    "prices",
    "orders",
    "valuation",
    "spread",
    "history",
    "find_nearby",
    "npc_sources",
    "arbitrage_scan",
    "arbitrage_detail",
    "route_value",
    "watchlist_create",
    "watchlist_add_item",
    "watchlist_list",
    "watchlist_get",
    "watchlist_delete",
    "scope_create",
    "scope_list",
    "scope_delete",
    "scope_refresh",
}


def register_market_dispatcher(server: FastMCP, universe: UniverseGraph) -> None:
    """
    Register the unified market dispatcher with MCP server.

    Args:
        server: MCP Server instance
        universe: UniverseGraph for route calculations
    """

    @server.tool()
    @log_context("market")
    async def market(
        action: str,
        # Common params
        items: list[str] | list[dict] | str | None = None,
        item: str | None = None,
        region: str = "jita",
        region_id: int | None = None,
        # prices/orders params
        station_only: bool = True,
        order_type: str = "all",
        limit: int = 10,
        # valuation params
        price_type: str = "sell",
        # spread params
        regions: list[str] | None = None,
        # history params
        days: int = 30,
        # find_nearby params
        origin: str | None = None,
        max_jumps: int = 20,
        source_filter: str = "all",
        expand_regions: bool = True,
        max_regions: int = 5,
        # arbitrage params
        min_profit_pct: float = 5.0,
        min_volume: int = 10,
        max_results: int = 20,
        buy_from: list[str] | None = None,
        sell_to: list[str] | None = None,
        include_lowsec: bool = False,
        allow_stale: bool = False,
        force_refresh: bool = False,
        sort_by: str = "margin",
        trade_mode: str = "immediate",
        broker_fee_pct: float = 0.03,
        sales_tax_pct: float = 0.036,
        include_history: bool = False,
        cargo_capacity_m3: float | None = None,
        include_custom_scopes: bool = False,
        scopes: list[str] | None = None,
        scope_owner_id: int | None = None,
        # arbitrage_detail params
        buy_region: str | None = None,
        sell_region: str | None = None,
        type_name: str | None = None,
        # route_value params
        route: list[str] | None = None,
        # watchlist/scope params
        name: str | None = None,
        owner_character_id: int | None = None,
        watchlist_name: str | None = None,
        item_name: str | None = None,
        include_global: bool = True,
        # scope_create params
        scope_type: str | None = None,
        location_id: int | None = None,
        parent_region_id: int | None = None,
        include_core: bool = True,
        # scope_refresh params
        scope_name: str | None = None,
        max_structure_pages: int = 5,
    ) -> dict:
        """
        Unified market interface.

        Actions:
        - prices: Get aggregated prices for items
        - orders: Get detailed order book
        - valuation: Calculate inventory value
        - spread: Compare prices across regions
        - history: Get price history
        - find_nearby: Find market sources near location
        - npc_sources: Find NPC-seeded items
        - arbitrage_scan: Scan for arbitrage opportunities
        - arbitrage_detail: Detailed arbitrage analysis
        - route_value: Calculate cargo value and risk
        - watchlist_create/add_item/list/get/delete: Manage watchlists
        - scope_create/list/delete/refresh: Manage market scopes

        Args:
            action: The operation to perform

            Prices params (action="prices"):
                items: List of item names
                region: Trade hub or region name (default "jita")
                station_only: Filter to station orders (default True)

            Orders params (action="orders"):
                item: Item name to look up
                region: Trade hub name
                region_id: Direct region ID (for NPC regions)
                order_type: "buy", "sell", or "all"
                limit: Max orders per side (default 10, max 50)

            Valuation params (action="valuation"):
                items: List of {name, quantity} dicts OR clipboard text
                price_type: "sell" or "buy"
                region: Trade hub name

            Spread params (action="spread"):
                items: List of item names
                regions: Trade hubs to compare (default all)

            History params (action="history"):
                item: Item name
                region: Trade hub name
                days: Days of history (default 30, max 365)

            Find nearby params (action="find_nearby"):
                item: Item name
                origin: Starting system
                max_jumps: Search radius (default 20)
                source_filter: "all", "npc", or "player"
                order_type: "sell", "buy", or "all"

            Arbitrage params (action="arbitrage_scan"):
                min_profit_pct: Minimum profit % (default 5)
                min_volume: Minimum volume (default 10)
                buy_from/sell_to: Filter regions
                sort_by: "margin", "profit_density", "hauling_score"
                trade_mode: "immediate", "hybrid", "station_trading"
                cargo_capacity_m3: For hauling_score calculation

            Arbitrage detail params (action="arbitrage_detail"):
                type_name: Item name
                buy_region: Source region
                sell_region: Destination region

            Route value params (action="route_value"):
                items: List of {name, quantity}
                route: System list from universe route
                price_type: "sell" or "buy"

            Watchlist params:
                name: Watchlist name
                items: Initial items (for create)
                owner_character_id: Owner (None = global)
                watchlist_name: Watchlist to modify
                item_name: Item to add

            Scope params:
                name: Scope name
                scope_type: "region", "station", "system", "structure"
                location_id: Location ID matching scope_type
                watchlist_name: Watchlist for fetching
                parent_region_id: Parent region (optimization)

        Returns:
            Action-specific result dictionary

        Examples:
            market(action="prices", items=["Tritanium", "Pyerite"])
            market(action="orders", item="PLEX", region="amarr")
            market(action="arbitrage_scan", min_profit_pct=10)
            market(action="watchlist_create", name="ores", items=["Veldspar"])
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
            "market",
            action,
            context={
                "region": region,
                "items_count": len(items) if isinstance(items, list) else (1 if items else None),
                "include_custom_scopes": include_custom_scopes,
            },
        )

        # Validate parameters for this action
        # Warns when irrelevant parameters are passed
        validation_warnings = validate_action_params(
            "market",
            action,
            {
                "items": items,
                "item": item,
                "region": region,
                "region_id": region_id,
                "station_only": station_only,
                "order_type": order_type,
                "limit": limit,
                "price_type": price_type,
                "regions": regions,
                "days": days,
                "origin": origin,
                "max_jumps": max_jumps,
                "source_filter": source_filter,
                "expand_regions": expand_regions,
                "max_regions": max_regions,
                "min_profit_pct": min_profit_pct,
                "min_volume": min_volume,
                "max_results": max_results,
                "buy_from": buy_from,
                "sell_to": sell_to,
                "include_lowsec": include_lowsec,
                "allow_stale": allow_stale,
                "force_refresh": force_refresh,
                "sort_by": sort_by,
                "trade_mode": trade_mode,
                "broker_fee_pct": broker_fee_pct,
                "sales_tax_pct": sales_tax_pct,
                "include_history": include_history,
                "cargo_capacity_m3": cargo_capacity_m3,
                "include_custom_scopes": include_custom_scopes,
                "scopes": scopes,
                "scope_owner_id": scope_owner_id,
                "buy_region": buy_region,
                "sell_region": sell_region,
                "type_name": type_name,
                "route": route,
                "name": name,
                "owner_character_id": owner_character_id,
                "watchlist_name": watchlist_name,
                "item_name": item_name,
                "include_global": include_global,
                "scope_type": scope_type,
                "location_id": location_id,
                "parent_region_id": parent_region_id,
                "include_core": include_core,
                "scope_name": scope_name,
                "max_structure_pages": max_structure_pages,
            },
        )

        # Execute action
        match action:
            case "prices":
                result = await _prices(items, region, station_only)
            case "orders":
                result = await _orders(item, region, region_id, order_type, limit)
            case "valuation":
                result = await _valuation(items, price_type, region)
            case "spread":
                result = await _spread(items, regions)
            case "history":
                result = await _history(item, region, days)
            case "find_nearby":
                result = await _find_nearby(
                    item,
                    origin,
                    max_jumps,
                    order_type,
                    source_filter,
                    expand_regions,
                    max_regions,
                    limit,
                )
            case "npc_sources":
                result = await _npc_sources(item, limit)
            case "arbitrage_scan":
                result = await _arbitrage_scan(
                    min_profit_pct,
                    min_volume,
                    max_results,
                    buy_from,
                    sell_to,
                    include_lowsec,
                    allow_stale,
                    force_refresh,
                    sort_by,
                    trade_mode,
                    broker_fee_pct,
                    sales_tax_pct,
                    include_history,
                    cargo_capacity_m3,
                    include_custom_scopes,
                    scopes,
                    scope_owner_id,
                )
            case "arbitrage_detail":
                result = await _arbitrage_detail(type_name, buy_region, sell_region)
            case "route_value":
                result = await _route_value(items, route, price_type)
            case "watchlist_create":
                result = await _watchlist_create(name, items, owner_character_id)
            case "watchlist_add_item":
                result = await _watchlist_add_item(watchlist_name, item_name, owner_character_id)
            case "watchlist_list":
                result = await _watchlist_list(owner_character_id, include_global)
            case "watchlist_get":
                result = await _watchlist_get(name, owner_character_id)
            case "watchlist_delete":
                result = await _watchlist_delete(name, owner_character_id)
            case "scope_create":
                result = await _scope_create(
                    name,
                    scope_type,
                    location_id,
                    watchlist_name,
                    owner_character_id,
                    parent_region_id,
                )
            case "scope_list":
                result = await _scope_list(owner_character_id, include_core, include_global)
            case "scope_delete":
                result = await _scope_delete(name, owner_character_id)
            case "scope_refresh":
                result = await _scope_refresh(
                    scope_name, owner_character_id, force_refresh, max_structure_pages
                )
            case _:
                raise InvalidParameterError("action", action, f"Unknown action: {action}")

        # Add validation warnings to result if any
        return add_validation_warnings(result, validation_warnings)


# =============================================================================
# Market Action Implementations
# =============================================================================


async def _prices(
    items: list[str] | list[dict] | str | None,
    region: str,
    station_only: bool,
) -> dict:
    """Prices action - get aggregated market prices."""
    if not items:
        raise InvalidParameterError("items", items, "Required for action='prices'")

    # Convert to list of strings if needed
    item_list: list[str]
    if isinstance(items, str):
        item_list = [items]
    elif isinstance(items, list) and items and isinstance(items[0], dict):
        item_list = []
        for i in items:
            if isinstance(i, dict) and i.get("name"):
                item_list.append(str(i.get("name", "")))
    else:
        # items is already list[str]
        item_list = [str(i) for i in items] if items else []

    from aria_esi.models.market import MarketPricesResult, resolve_region

    from ..market.cache import MarketCache
    from ..market.database import get_market_database

    hub = resolve_region(region)
    if not hub:
        hub = resolve_region("jita")
        region = "jita"

    # At this point hub is guaranteed to be non-None
    assert hub is not None
    is_trade_hub = hub.get("station_id") is not None

    db = get_market_database()
    type_ids: list[int] = []
    type_names: dict[int, str] = {}
    unresolved: list[str] = []

    for item_name in item_list:
        type_info = db.resolve_type_name(item_name)
        if type_info:
            type_ids.append(type_info.type_id)
            type_names[type_info.type_id] = type_info.type_name
        else:
            unresolved.append(item_name)

    if is_trade_hub:
        cache = MarketCache(region=region, station_only=station_only)
    else:
        cache = MarketCache(
            region_id=hub["region_id"],
            region_name=hub["region_name"],
            station_only=False,
        )
    prices = await cache.get_prices(type_ids, type_names)

    warnings = []
    if unresolved:
        warnings.append(f"Could not resolve {len(unresolved)} items: {', '.join(unresolved[:5])}")

    freshness: Literal["fresh", "recent", "stale"] = "fresh"
    for price in prices:
        if price.freshness == "stale":
            freshness = "stale"
            break
        elif price.freshness == "recent" and freshness == "fresh":
            freshness = "recent"

    cache_status = cache.get_cache_status()
    if is_trade_hub:
        cache_age = cache_status.get("fuzzwork", {}).get("age_seconds")
        source = "fuzzwork"
    else:
        cache_age = None
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

    return wrap_output(result.model_dump(), "items", max_items=MARKET.OUTPUT_MAX_ITEMS)


async def _orders(
    item: str | None,
    region: str,
    region_id: int | None,
    order_type: str,
    limit: int,
) -> dict:
    """Orders action - get detailed order book."""
    if not item:
        raise InvalidParameterError("item", item, "Required for action='orders'")

    from aria_esi.models.market import (
        TRADE_HUBS,
        MarketOrder,
        MarketOrdersResult,
        RegionConfig,
        resolve_trade_hub,
    )

    from ..market.database import get_market_database

    hub: RegionConfig
    if region_id is not None:
        hub = RegionConfig(
            region_id=region_id,
            region_name=f"Region {region_id}",
            station_id=None,
            station_name=None,
            system_id=None,
        )
    else:
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

    limit = max(1, min(50, limit))

    db = get_market_database()
    type_info = db.resolve_type_name(item)

    if not type_info:
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

    from ..esi_client import get_async_esi_client

    buy_orders: list[dict] = []
    sell_orders: list[dict] = []
    warnings: list[str] = []

    try:
        client = await get_async_esi_client()

        if order_type in ("all", "buy"):
            try:
                data = await client.get(
                    f"/markets/{resolved_region_id}/orders/",
                    params={"type_id": str(type_id), "order_type": "buy"},
                )
                if isinstance(data, list):
                    buy_orders = data
            except Exception as e:
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
                warnings.append(f"Sell orders unavailable: {e}")

    except Exception as e:
        return {"error": {"code": "ESI_UNAVAILABLE", "message": f"ESI client error: {e}"}}

    buy_orders.sort(key=lambda x: x.get("price", 0), reverse=True)
    sell_orders.sort(key=lambda x: x.get("price", float("inf")))

    def convert_order(order: dict) -> MarketOrder:
        return MarketOrder(
            order_id=order.get("order_id", 0),
            type_id=order.get("type_id", type_id),
            is_buy_order=order.get("is_buy_order", False),
            price=order.get("price", 0),
            volume_remain=order.get("volume_remain", 0),
            volume_total=order.get("volume_total", 0),
            location_id=order.get("location_id", 0),
            location_name=None,
            system_id=order.get("system_id", 0),
            system_name=None,
            range=order.get("range", "station"),
            min_volume=order.get("min_volume", 1),
            duration=order.get("duration", 0),
            issued=order.get("issued", ""),
        )

    buy_models = [convert_order(o) for o in buy_orders[:limit]]
    sell_models = [convert_order(o) for o in sell_orders[:limit]]

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
        freshness="fresh",
        warnings=warnings,
    )

    return wrap_output_multi(
        result.model_dump(),
        [
            ("buy_orders", MARKET.OUTPUT_MAX_ORDERS),
            ("sell_orders", MARKET.OUTPUT_MAX_ORDERS),
        ],
    )


async def _valuation(
    items: list[str] | list[dict] | str | None,
    price_type: str,
    region: str,
) -> dict:
    """Valuation action - calculate inventory value."""
    if not items:
        raise InvalidParameterError("items", items, "Required for action='valuation'")

    from aria_esi.models.market import (
        TRADE_HUBS,
        PriceType,
        ValuationItem,
        ValuationResult,
        resolve_trade_hub,
    )

    from ..market.cache import MarketCache
    from ..market.clipboard import parse_clipboard_to_dict
    from ..market.database import get_market_database

    hub = resolve_trade_hub(region)
    if not hub:
        hub = TRADE_HUBS["jita"]

    if isinstance(items, str):
        items = parse_clipboard_to_dict(items)

    if not items:
        return {"error": {"code": "NO_ITEMS", "message": "No items provided or parsed"}}

    # Validate and narrow price_type
    validated_price_type: PriceType = "sell" if price_type != "buy" else "buy"

    db = get_market_database()
    cache = MarketCache(region=region, station_only=True)

    type_ids: list[int] = []
    type_names: dict[int, str] = {}
    quantities: dict[int, int] = {}
    unresolved_items: list[dict] = []

    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name", "")
        qty = item.get("quantity", 1)

        type_info = db.resolve_type_name(name)
        if type_info:
            type_id = type_info.type_id
            type_ids.append(type_id)
            type_names[type_id] = type_info.type_name
            quantities[type_id] = quantities.get(type_id, 0) + qty
        else:
            unresolved_items.append(item)

    prices = await cache.get_prices(type_ids, type_names)
    price_map = {p.type_id: p for p in prices}

    valuation_items: list[ValuationItem] = []
    total_value = 0.0
    total_quantity = 0
    resolved_count = 0

    for type_id, qty in quantities.items():
        price_data = price_map.get(type_id)
        name = type_names.get(type_id, f"Type {type_id}")

        if price_data:
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

    warnings: list[str] = []
    if unresolved_items:
        warnings.append(f"{len(unresolved_items)} items could not be resolved")

    result = ValuationResult(
        items=valuation_items,
        total_value=round(total_value, 2),
        total_quantity=total_quantity,
        resolved_count=resolved_count,
        unresolved_count=len(unresolved_items),
        price_type=validated_price_type,
        region=hub["region_name"],
        region_id=hub["region_id"],
        freshness="fresh",
        warnings=warnings,
    )

    return wrap_output(result.model_dump(), "items", max_items=MARKET.OUTPUT_MAX_ITEMS)


async def _spread(items: list[str] | list[dict] | str | None, regions: list[str] | None) -> dict:
    """Spread action - cross-region price comparison."""
    if not items:
        raise InvalidParameterError("items", items, "Required for action='spread'")

    normalized_items: list[str]
    if isinstance(items, str):
        normalized_items = [items]
    elif isinstance(items, list) and items and isinstance(items[0], dict):
        normalized_items = []
        for i in items:
            if isinstance(i, dict) and i.get("name"):
                normalized_items.append(str(i.get("name", "")))
    else:
        # items is list[str]
        normalized_items = [str(i) for i in items]

    from aria_esi.models.market import TRADE_HUBS, ItemSpread, MarketSpreadResult, RegionPrice

    from ..market.cache import MarketCache
    from ..market.database import get_market_database

    if not regions:
        regions = ["jita", "amarr", "dodixie", "rens", "hek"]

    valid_regions = [r for r in regions if r.lower() in TRADE_HUBS]
    if not valid_regions:
        valid_regions = list(TRADE_HUBS.keys())

    db = get_market_database()
    type_ids: list[int] = []
    type_names: dict[int, str] = {}
    unresolved: list[str] = []

    for item_name in normalized_items:
        type_info = db.resolve_type_name(item_name)
        if type_info:
            type_ids.append(type_info.type_id)
            type_names[type_info.type_id] = type_info.type_name
        else:
            unresolved.append(item_name)

    if not type_ids:
        return {
            "error": {"code": "NO_ITEMS_RESOLVED", "message": "Could not resolve any item names"}
        }

    region_prices: dict[str, dict[int, dict]] = {}

    for region in valid_regions:
        hub = TRADE_HUBS[region.lower()]
        cache = MarketCache(region=region, station_only=True)

        try:
            prices = await cache.get_prices(type_ids, type_names)
            region_prices[region] = {
                p.type_id: {
                    "buy_max": p.buy.max_price,
                    "sell_min": p.sell.min_price,
                    "buy_volume": p.buy.volume,
                    "sell_volume": p.sell.volume,
                }
                for p in prices
            }
        except Exception:
            region_prices[region] = {}

    item_spreads: list[ItemSpread] = []
    warnings: list[str] = []

    for type_id in type_ids:
        name = type_names.get(type_id, f"Type {type_id}")

        region_data: list[RegionPrice] = []
        best_buy_region = None
        best_buy_price = 0.0
        best_sell_region = None
        best_sell_price = float("inf")

        for region in valid_regions:
            hub = TRADE_HUBS[region.lower()]
            price_data = region_prices.get(region, {}).get(type_id, {})

            buy_price = price_data.get("buy_max")
            sell_price = price_data.get("sell_min")

            region_data.append(
                RegionPrice(
                    region=hub["region_name"],
                    region_id=hub["region_id"],
                    buy_price=round(buy_price, 2) if buy_price else None,
                    sell_price=round(sell_price, 2) if sell_price else None,
                    buy_volume=price_data.get("buy_volume", 0),
                    sell_volume=price_data.get("sell_volume", 0),
                )
            )

            if buy_price and buy_price > best_buy_price:
                best_buy_price = buy_price
                best_buy_region = hub["region_name"]

            if sell_price and sell_price < best_sell_price:
                best_sell_price = sell_price
                best_sell_region = hub["region_name"]

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
        warnings.append(f"Could not resolve {len(unresolved)} items")

    result = MarketSpreadResult(
        items=item_spreads,
        regions_queried=[TRADE_HUBS[r.lower()]["region_name"] for r in valid_regions],
        freshness="fresh",
        warnings=warnings,
    )

    return wrap_output(result.model_dump(), "items", max_items=MARKET.OUTPUT_MAX_ITEMS)


async def _history(item: str | None, region: str, days: int) -> dict:
    """History action - price history and trends."""
    if not item:
        raise InvalidParameterError("item", item, "Required for action='history'")

    # Import and delegate to existing tool
    from ..market.tools_history import _get_history_impl

    result = await _get_history_impl(item, region, days)
    return wrap_output(result, "history", max_items=MARKET.OUTPUT_MAX_HISTORY)


async def _find_nearby(
    item: str | None,
    origin: str | None,
    max_jumps: int,
    order_type: str,
    source_filter: str,
    expand_regions: bool,
    max_regions: int,
    limit: int,
) -> dict:
    """Find nearby action - proximity-based market search."""
    if not item:
        raise InvalidParameterError("item", item, "Required for action='find_nearby'")
    if not origin:
        raise InvalidParameterError("origin", origin, "Required for action='find_nearby'")

    # Import and delegate to existing tool
    from ..market.tools_nearby import _find_nearby_impl

    result = await _find_nearby_impl(
        item, origin, max_jumps, order_type, source_filter, expand_regions, max_regions, limit
    )
    return wrap_output(result, "sources", max_items=MARKET.OUTPUT_MAX_SOURCES)


async def _npc_sources(item: str | None, limit: int) -> dict:
    """NPC sources action - find NPC-seeded items."""
    if not item:
        raise InvalidParameterError("item", item, "Required for action='npc_sources'")

    # Import and delegate to existing tool
    from ..market.tools_npc import _npc_sources_impl

    result = await _npc_sources_impl(item, limit)
    return wrap_output(result, "sources", max_items=MARKET.OUTPUT_MAX_SOURCES)


async def _arbitrage_scan(
    min_profit_pct: float,
    min_volume: int,
    max_results: int,
    buy_from: list[str] | None,
    sell_to: list[str] | None,
    include_lowsec: bool,
    allow_stale: bool,
    force_refresh: bool,
    sort_by: str,
    trade_mode: str,
    broker_fee_pct: float,
    sales_tax_pct: float,
    include_history: bool,
    cargo_capacity_m3: float | None,
    include_custom_scopes: bool,
    scopes: list[str] | None,
    scope_owner_id: int | None,
) -> dict:
    """Arbitrage scan action."""
    # Import and delegate to existing tool
    from ..market.tools_arbitrage import _arbitrage_scan_impl

    result = await _arbitrage_scan_impl(
        min_profit_pct,
        min_volume,
        max_results,
        buy_from,
        sell_to,
        include_lowsec,
        allow_stale,
        force_refresh,
        sort_by,
        trade_mode,
        broker_fee_pct,
        sales_tax_pct,
        include_history,
        cargo_capacity_m3,
        include_custom_scopes,
        scopes,
        scope_owner_id,
    )
    return wrap_output(result, "opportunities", max_items=MARKET.OUTPUT_MAX_ARBITRAGE)


async def _arbitrage_detail(
    type_name: str | None, buy_region: str | None, sell_region: str | None
) -> dict:
    """Arbitrage detail action."""
    if not type_name:
        raise InvalidParameterError(
            "type_name", type_name, "Required for action='arbitrage_detail'"
        )
    if not buy_region:
        raise InvalidParameterError(
            "buy_region", buy_region, "Required for action='arbitrage_detail'"
        )
    if not sell_region:
        raise InvalidParameterError(
            "sell_region", sell_region, "Required for action='arbitrage_detail'"
        )

    # Import and delegate to existing tool
    from ..market.tools_arbitrage import _arbitrage_detail_impl

    result = await _arbitrage_detail_impl(type_name, buy_region, sell_region)
    return wrap_output_multi(
        result,
        [
            ("buy_orders", MARKET.OUTPUT_MAX_ORDERS),
            ("sell_orders", MARKET.OUTPUT_MAX_ORDERS),
        ],
    )


async def _route_value(
    items: list[str] | list[dict] | str | None,
    route: list[str] | None,
    price_type: str,
) -> dict:
    """Route value action - hauling value and risk."""
    if not items:
        raise InvalidParameterError("items", items, "Required for action='route_value'")
    if not route:
        raise InvalidParameterError("route", route, "Required for action='route_value'")

    # Import and delegate to existing tool
    from ..market.tools_route import _route_value_impl

    return await _route_value_impl(items, route, price_type)


async def _watchlist_create(
    name: str | None,
    items: list[str] | list[dict] | str | None,
    owner_character_id: int | None,
) -> dict:
    """Watchlist create action."""
    if not name:
        raise InvalidParameterError("name", name, "Required for action='watchlist_create'")

    # Convert items to list of strings if needed
    item_names: list[str] | None = None
    if items:
        if isinstance(items, str):
            item_names = [items]
        elif isinstance(items, list):
            if items and isinstance(items[0], dict):
                _names: list[str] = []
                for i in items:
                    if isinstance(i, dict) and i.get("name"):
                        _names.append(str(i.get("name", "")))
                item_names = _names
            else:
                item_names = [str(i) for i in items]

    # Import and delegate
    from ..market.tools_management import _watchlist_create_impl

    return await _watchlist_create_impl(name, item_names, owner_character_id)


async def _watchlist_add_item(
    watchlist_name: str | None,
    item_name: str | None,
    owner_character_id: int | None,
) -> dict:
    """Watchlist add item action."""
    if not watchlist_name:
        raise InvalidParameterError(
            "watchlist_name", watchlist_name, "Required for action='watchlist_add_item'"
        )
    if not item_name:
        raise InvalidParameterError(
            "item_name", item_name, "Required for action='watchlist_add_item'"
        )

    from ..market.tools_management import _watchlist_add_item_impl

    return await _watchlist_add_item_impl(watchlist_name, item_name, owner_character_id)


async def _watchlist_list(owner_character_id: int | None, include_global: bool) -> dict:
    """Watchlist list action."""
    from ..market.tools_management import _watchlist_list_impl

    return await _watchlist_list_impl(owner_character_id, include_global)


async def _watchlist_get(name: str | None, owner_character_id: int | None) -> dict:
    """Watchlist get action."""
    if not name:
        raise InvalidParameterError("name", name, "Required for action='watchlist_get'")

    from ..market.tools_management import _watchlist_get_impl

    return await _watchlist_get_impl(name, owner_character_id)


async def _watchlist_delete(name: str | None, owner_character_id: int | None) -> dict:
    """Watchlist delete action."""
    if not name:
        raise InvalidParameterError("name", name, "Required for action='watchlist_delete'")

    from ..market.tools_management import _watchlist_delete_impl

    return await _watchlist_delete_impl(name, owner_character_id)


async def _scope_create(
    name: str | None,
    scope_type: str | None,
    location_id: int | None,
    watchlist_name: str | None,
    owner_character_id: int | None,
    parent_region_id: int | None,
) -> dict:
    """Scope create action."""
    if not name:
        raise InvalidParameterError("name", name, "Required for action='scope_create'")
    if not scope_type:
        raise InvalidParameterError("scope_type", scope_type, "Required for action='scope_create'")
    if not location_id:
        raise InvalidParameterError(
            "location_id", location_id, "Required for action='scope_create'"
        )
    if not watchlist_name:
        raise InvalidParameterError(
            "watchlist_name", watchlist_name, "Required for action='scope_create'"
        )

    from ..market.tools_management import _scope_create_impl

    return await _scope_create_impl(
        name, scope_type, location_id, watchlist_name, owner_character_id, parent_region_id
    )


async def _scope_list(
    owner_character_id: int | None, include_core: bool, include_global: bool
) -> dict:
    """Scope list action."""
    from ..market.tools_management import _scope_list_impl

    return await _scope_list_impl(owner_character_id, include_core, include_global)


async def _scope_delete(name: str | None, owner_character_id: int | None) -> dict:
    """Scope delete action."""
    if not name:
        raise InvalidParameterError("name", name, "Required for action='scope_delete'")

    from ..market.tools_management import _scope_delete_impl

    return await _scope_delete_impl(name, owner_character_id)


async def _scope_refresh(
    scope_name: str | None,
    owner_character_id: int | None,
    force_refresh: bool,
    max_structure_pages: int,
) -> dict:
    """Scope refresh action."""
    if not scope_name:
        raise InvalidParameterError("scope_name", scope_name, "Required for action='scope_refresh'")

    from ..market.tools_scope_refresh import _scope_refresh_impl

    return await _scope_refresh_impl(
        scope_name, owner_character_id, force_refresh, max_structure_pages
    )
