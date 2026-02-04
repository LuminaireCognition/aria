"""
ARIA ESI Market Commands

Market price lookups and trade hub data.
All commands are public (no authentication required).

Includes:
- price: Look up market prices for individual items (ESI-backed)
- market-seed: Download bulk market data from Fuzzwork
- market-status: Show market database status
- price-batch: Batch price lookup from file (Fuzzwork-backed)
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

from ..core import (
    STATION_NAMES,
    ESIClient,
    ESIError,
    get_utc_timestamp,
)

# =============================================================================
# Price Command
# =============================================================================


def cmd_price(args: argparse.Namespace) -> dict:
    """
    Look up market prices for an item.

    Args:
        args: Parsed arguments with item_name and optional region

    Returns:
        Price data dict with global prices and regional orders
    """
    item_name = args.item_name
    region_id = getattr(args, "region_id", None)
    region_name = getattr(args, "region_name", None)
    hub_name = getattr(args, "hub_name", None)

    client = ESIClient()
    query_ts = get_utc_timestamp()

    # Resolve item name to type_id
    type_id, resolved_name = client.resolve_item(item_name)

    if not type_id:
        return {
            "error": "item_not_found",
            "message": f"Could not find item: {item_name}",
            "hint": "Check spelling. Item names are case-insensitive.",
            "query_timestamp": query_ts,
        }

    # Get item name if we only had an ID
    if not resolved_name:
        resolved_name = client.get_type_name(type_id)
        if not resolved_name:
            resolved_name = f"Type {type_id}"

    # Get global market prices
    try:
        global_prices = client.get("/markets/prices/")
    except ESIError as e:
        return {
            "error": "market_data_unavailable",
            "message": "Could not fetch global market prices",
            "detail": str(e),
            "query_timestamp": query_ts,
        }

    # Find this item's global price
    item_global = None
    if isinstance(global_prices, list):
        for price_data in global_prices:
            if price_data.get("type_id") == type_id:
                item_global = price_data
                break

    # Build output
    output = {
        "query_timestamp": query_ts,
        "volatility": "semi_stable",
        "item": {"type_id": type_id, "name": resolved_name},
    }

    # Add global prices
    if item_global:
        output["global_prices"] = {
            "average_price": round(item_global.get("average_price", 0), 2),
            "adjusted_price": round(item_global.get("adjusted_price", 0), 2),
        }
    else:
        output["global_prices"] = {
            "average_price": None,
            "adjusted_price": None,
            "note": "No global price data (item may be untradeable)",
        }

    # Get regional orders if region specified
    if region_id:
        # Ensure region_name is a string
        resolved_region_name = (
            region_name if isinstance(region_name, str) else f"Region {region_id}"
        )
        regional_data = _get_regional_orders(
            client, type_id, region_id, resolved_region_name, hub_name
        )
        output["regional_data"] = regional_data

    return output


def _get_regional_orders(
    client: ESIClient, type_id: int, region_id: str, region_name: str, hub_name: Optional[str]
) -> dict:
    """Fetch and process regional market orders."""

    # Get sell orders
    try:
        sell_orders = client.get(
            f"/markets/{region_id}/orders/", params={"type_id": str(type_id), "order_type": "sell"}
        )
    except ESIError:
        sell_orders = []

    # Get buy orders
    try:
        buy_orders = client.get(
            f"/markets/{region_id}/orders/", params={"type_id": str(type_id), "order_type": "buy"}
        )
    except ESIError:
        buy_orders = []

    # Ensure we have lists
    if not isinstance(sell_orders, list):
        sell_orders = []
    if not isinstance(buy_orders, list):
        buy_orders = []

    # Sort orders
    sell_orders.sort(key=lambda x: x.get("price", float("inf")))
    buy_orders.sort(key=lambda x: x.get("price", 0), reverse=True)

    # Format top orders with station names
    formatted_sell = _format_orders(client, sell_orders[:5])
    formatted_buy = _format_orders(client, buy_orders[:5])

    # Calculate spread
    best_sell = sell_orders[0]["price"] if sell_orders else None
    best_buy = buy_orders[0]["price"] if buy_orders else None

    spread = None
    spread_percent = None
    if best_sell and best_buy:
        spread = round(best_sell - best_buy, 2)
        spread_percent = round((spread / best_sell) * 100, 2) if best_sell > 0 else 0

    return {
        "region_id": int(region_id),
        "region_name": region_name,
        "hub_name": hub_name,
        "sell_orders": formatted_sell,
        "buy_orders": formatted_buy,
        "sell_order_count": len(sell_orders),
        "buy_order_count": len(buy_orders),
        "best_sell": round(best_sell, 2) if best_sell else None,
        "best_buy": round(best_buy, 2) if best_buy else None,
        "spread": spread,
        "spread_percent": spread_percent,
    }


def _format_orders(client: ESIClient, orders: list) -> list:
    """Format market orders with station names."""
    formatted = []
    for order in orders:
        location_id = order.get("location_id")

        # Get station name (check cache first)
        station_name = STATION_NAMES.get(location_id)
        if not station_name:
            station_name = client.get_station_name(location_id) or f"Station {location_id}"

        formatted.append(
            {
                "price": round(order.get("price", 0), 2),
                "volume": order.get("volume_remain", 0),
                "location": station_name,
                "location_id": location_id,
            }
        )

    return formatted


# =============================================================================
# Market Seed Command
# =============================================================================


def cmd_market_seed(args: argparse.Namespace) -> dict:
    """
    Download and import bulk market data from Fuzzwork.

    Downloads the complete Jita 4-4 price dataset and imports it
    into the local market database, then resolves type names via ESI.

    Args:
        args: Parsed arguments (currently no options)

    Returns:
        Import status with row counts
    """
    query_ts = get_utc_timestamp()

    try:
        from ..mcp.market.clients import FuzzworkClient
        from ..mcp.market.database import MarketDatabase
    except ImportError as e:
        return {
            "error": "import_error",
            "message": f"Failed to import market modules: {e}",
            "hint": "Ensure httpx is installed: uv pip install httpx",
            "query_timestamp": query_ts,
        }

    print("Downloading bulk market data from Fuzzwork...", file=sys.stderr)

    try:
        client = FuzzworkClient()
        csv_data = client.download_bulk_csv_sync()
        print(f"Downloaded {len(csv_data) / 1024 / 1024:.1f} MB", file=sys.stderr)
    except Exception as e:
        return {
            "error": "download_error",
            "message": f"Failed to download bulk data: {e}",
            "query_timestamp": query_ts,
        }

    print("Importing into database...", file=sys.stderr)

    try:
        db = MarketDatabase()
        types_count, aggregates_count = db.import_fuzzwork_csv(csv_data)
    except Exception as e:
        return {
            "error": "import_error",
            "message": f"Failed to import data: {e}",
            "query_timestamp": query_ts,
        }

    # Resolve type names via ESI
    print("Resolving type names via ESI...", file=sys.stderr)
    names_resolved = 0

    try:
        placeholder_ids = db.get_placeholder_type_ids()
        if placeholder_ids:
            esi_client = ESIClient()
            # ESI /universe/names/ accepts up to 1000 IDs per request
            batch_size = 1000
            all_names: dict[int, str] = {}

            for i in range(0, len(placeholder_ids), batch_size):
                batch = placeholder_ids[i : i + batch_size]
                try:
                    # POST to /universe/names/ with list of IDs
                    response = esi_client.post("/universe/names/", data=batch)
                    if isinstance(response, list):
                        for item in response:
                            if item.get("category") == "inventory_type":
                                all_names[item["id"]] = item["name"]
                    print(
                        f"  Resolved {len(all_names)}/{len(placeholder_ids)} names...",
                        file=sys.stderr,
                    )
                except ESIError as e:
                    print(f"  Warning: ESI batch failed: {e}", file=sys.stderr)

            if all_names:
                names_resolved = db.update_type_names(all_names)

    except Exception as e:
        print(f"Warning: Failed to resolve type names: {e}", file=sys.stderr)

    db.close()

    return {
        "status": "success",
        "types_imported": types_count,
        "aggregates_imported": aggregates_count,
        "names_resolved": names_resolved,
        "source": "fuzzwork_bulk_csv",
        "query_timestamp": query_ts,
    }


# =============================================================================
# Market Status Command
# =============================================================================


def cmd_market_status(args: argparse.Namespace) -> dict:
    """
    Show market database status and statistics.

    Args:
        args: Parsed arguments (currently no options)

    Returns:
        Database statistics
    """
    query_ts = get_utc_timestamp()

    try:
        from ..mcp.market.database import MarketDatabase
    except ImportError as e:
        return {
            "error": "import_error",
            "message": f"Failed to import market modules: {e}",
            "query_timestamp": query_ts,
        }

    try:
        db = MarketDatabase()
        stats = db.get_stats()
        db.close()
    except Exception as e:
        return {
            "error": "database_error",
            "message": f"Failed to read database: {e}",
            "query_timestamp": query_ts,
        }

    # Determine freshness
    if stats.get("newest_update") is not None:
        if stats["newest_update"] < 300:  # 5 min
            freshness = "fresh"
        elif stats["newest_update"] < 1800:  # 30 min
            freshness = "recent"
        else:
            freshness = "stale"
    else:
        freshness = "empty"

    return {
        "status": "ok",
        "type_count": stats.get("type_count", 0),
        "aggregate_count": stats.get("aggregate_count", 0),
        "freshness": freshness,
        "oldest_data_age_seconds": stats.get("oldest_update"),
        "newest_data_age_seconds": stats.get("newest_update"),
        "database_path": stats.get("database_path"),
        "database_size_mb": round(stats.get("database_size_mb", 0), 2),
        "query_timestamp": query_ts,
    }


# =============================================================================
# Price Batch Command
# =============================================================================


def cmd_price_batch(args: argparse.Namespace) -> dict:
    """
    Batch price lookup from file.

    Reads item names from a file (one per line) and returns
    aggregated prices from Fuzzwork or local cache.

    Args:
        args: Parsed arguments with file path and region

    Returns:
        Batch price data
    """
    query_ts = get_utc_timestamp()
    file_path = Path(args.file_path)

    if not file_path.exists():
        return {
            "error": "file_not_found",
            "message": f"File not found: {file_path}",
            "query_timestamp": query_ts,
        }

    # Read item names from file
    try:
        with open(file_path) as f:
            item_names = [line.strip() for line in f if line.strip()]
    except Exception as e:
        return {
            "error": "file_error",
            "message": f"Failed to read file: {e}",
            "query_timestamp": query_ts,
        }

    if not item_names:
        return {
            "error": "empty_file",
            "message": "No item names found in file",
            "query_timestamp": query_ts,
        }

    try:
        from ..mcp.market.clients import create_client
        from ..mcp.market.database import MarketDatabase
        from ..models.market import TRADE_HUBS, resolve_trade_hub
    except ImportError as e:
        return {
            "error": "import_error",
            "message": f"Failed to import market modules: {e}",
            "query_timestamp": query_ts,
        }

    # Resolve trade hub
    hub_name = getattr(args, "hub", "jita")
    hub = resolve_trade_hub(hub_name)
    if not hub:
        hub = TRADE_HUBS["jita"]
        hub_name = "jita"

    # Resolve item names to type IDs
    db = MarketDatabase()
    resolved = db.batch_resolve_names(item_names)

    type_ids = []
    unresolved = []
    name_map = {}  # type_id -> name

    for name, type_info in resolved.items():
        if type_info:
            type_ids.append(type_info.type_id)
            name_map[type_info.type_id] = type_info.type_name
        else:
            unresolved.append(name)

    if not type_ids:
        db.close()
        return {
            "error": "no_items_resolved",
            "message": "Could not resolve any item names",
            "unresolved": unresolved,
            "hint": "Run 'aria-esi market-seed' to populate the type database",
            "query_timestamp": query_ts,
        }

    # Fetch prices from Fuzzwork
    client = create_client(hub_name, station_only=True)
    try:
        aggregates = client.get_aggregates_sync(type_ids)
    except Exception as e:
        db.close()
        return {
            "error": "fuzzwork_error",
            "message": f"Failed to fetch prices: {e}",
            "query_timestamp": query_ts,
        }

    # Build results
    items = []
    for type_id, agg in aggregates.items():
        item_name = name_map.get(type_id, f"Type {type_id}")

        # Calculate spread
        spread = None
        spread_percent = None
        if agg.sell_min and agg.buy_max:
            spread = round(agg.sell_min - agg.buy_max, 2)
            if agg.sell_min > 0:
                spread_percent = round((spread / agg.sell_min) * 100, 2)

        items.append(
            {
                "type_id": type_id,
                "name": item_name,
                "buy": {
                    "max": round(agg.buy_max, 2) if agg.buy_max else None,
                    "min": round(agg.buy_min, 2) if agg.buy_min else None,
                    "weighted_avg": round(agg.buy_weighted_average, 2)
                    if agg.buy_weighted_average
                    else None,
                    "volume": agg.buy_volume,
                    "order_count": agg.buy_order_count,
                },
                "sell": {
                    "max": round(agg.sell_max, 2) if agg.sell_max else None,
                    "min": round(agg.sell_min, 2) if agg.sell_min else None,
                    "weighted_avg": round(agg.sell_weighted_average, 2)
                    if agg.sell_weighted_average
                    else None,
                    "volume": agg.sell_volume,
                    "order_count": agg.sell_order_count,
                },
                "spread": spread,
                "spread_percent": spread_percent,
            }
        )

    db.close()

    return {
        "region": hub["region_name"],
        "station": hub["station_name"],
        "items_requested": len(item_names),
        "items_resolved": len(items),
        "items": items,
        "unresolved": unresolved if unresolved else None,
        "source": "fuzzwork",
        "query_timestamp": query_ts,
    }


# =============================================================================
# Argument Parser Registration
# =============================================================================


def register_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Register market command parsers."""

    price_parser = subparsers.add_parser("price", help="Look up market prices for an item")
    price_parser.add_argument("item_name", nargs="+", help="Item name to look up")

    # Trade hub region flags
    price_parser.add_argument(
        "--jita",
        action="store_const",
        const=("10000002", "The Forge", "Jita"),
        dest="region_info",
        help="Show Jita (The Forge) prices",
    )
    price_parser.add_argument(
        "--amarr",
        action="store_const",
        const=("10000043", "Domain", "Amarr"),
        dest="region_info",
        help="Show Amarr (Domain) prices",
    )
    price_parser.add_argument(
        "--dodixie",
        action="store_const",
        const=("10000032", "Sinq Laison", "Dodixie"),
        dest="region_info",
        help="Show Dodixie (Sinq Laison) prices",
    )
    price_parser.add_argument(
        "--rens",
        action="store_const",
        const=("10000030", "Heimatar", "Rens"),
        dest="region_info",
        help="Show Rens (Heimatar) prices",
    )
    price_parser.add_argument(
        "--hek",
        action="store_const",
        const=("10000042", "Metropolis", "Hek"),
        dest="region_info",
        help="Show Hek (Metropolis) prices",
    )
    price_parser.add_argument("--region", type=str, metavar="REGION_ID", help="Custom region ID")
    price_parser.add_argument(
        "--global-only",
        action="store_true",
        dest="global_only",
        help="Show only global prices (no regional data)",
    )

    # Default to Jita - most common use case
    price_parser.set_defaults(
        func=_cmd_price_wrapper,
        region_info=("10000002", "The Forge", "Jita"),
    )

    # Market seed command
    seed_parser = subparsers.add_parser(
        "market-seed",
        help="Download bulk market data from Fuzzwork",
    )
    seed_parser.set_defaults(func=cmd_market_seed)

    # Market status command
    status_parser = subparsers.add_parser(
        "market-status",
        help="Show market database status",
    )
    status_parser.set_defaults(func=cmd_market_status)

    # Price batch command
    batch_parser = subparsers.add_parser(
        "price-batch",
        help="Batch price lookup from file",
    )
    batch_parser.add_argument(
        "file_path",
        help="Path to file with item names (one per line)",
    )
    batch_parser.add_argument(
        "--jita",
        action="store_const",
        const="jita",
        dest="hub",
        default="jita",
        help="Use Jita prices (default)",
    )
    batch_parser.add_argument(
        "--amarr",
        action="store_const",
        const="amarr",
        dest="hub",
        help="Use Amarr prices",
    )
    batch_parser.add_argument(
        "--dodixie",
        action="store_const",
        const="dodixie",
        dest="hub",
        help="Use Dodixie prices",
    )
    batch_parser.add_argument(
        "--rens",
        action="store_const",
        const="rens",
        dest="hub",
        help="Use Rens prices",
    )
    batch_parser.add_argument(
        "--hek",
        action="store_const",
        const="hek",
        dest="hub",
        help="Use Hek prices",
    )
    batch_parser.set_defaults(func=cmd_price_batch)


def _cmd_price_wrapper(args: argparse.Namespace) -> dict:
    """Wrapper to process price command arguments."""
    # Join item name parts if passed as multiple args
    if isinstance(args.item_name, list):
        args.item_name = " ".join(args.item_name)

    # Handle --global-only flag (skip regional data)
    if getattr(args, "global_only", False):
        args.region_id = None
        args.region_name = None
        args.hub_name = None
    # Extract region info from flags (defaults to Jita)
    elif hasattr(args, "region") and args.region:
        args.region_id = args.region
        args.region_name = "Custom Region"
        args.hub_name = None
    elif hasattr(args, "region_info") and args.region_info:
        args.region_id, args.region_name, args.hub_name = args.region_info
    else:
        args.region_id = None
        args.region_name = None
        args.hub_name = None

    return cmd_price(args)
