"""
ARIA ESI Market Orders Commands

View active and historical market orders.
All commands require authentication.
"""

import argparse
from datetime import datetime, timezone

from ..core import (
    CredentialsError,
    ESIClient,
    ESIError,
    get_authenticated_client,
    get_utc_timestamp,
    parse_datetime,
)

# Order range display mapping
ORDER_RANGES = {
    "station": "Station",
    "solarsystem": "Solar System",
    "region": "Region",
}


def _format_range(range_val) -> str:
    """Format order range for display."""
    if range_val in ORDER_RANGES:
        return ORDER_RANGES[range_val]
    # Numeric range (jumps)
    try:
        jumps = int(range_val)
        return f"{jumps} jumps"
    except (ValueError, TypeError):
        return str(range_val)


# =============================================================================
# Market Orders Command
# =============================================================================


def cmd_orders(args: argparse.Namespace) -> dict:
    """
    Fetch market orders.

    Shows active buy/sell orders and optionally order history.
    """
    query_ts = get_utc_timestamp()
    buy_only = getattr(args, "buy", False)
    sell_only = getattr(args, "sell", False)
    include_history = getattr(args, "history", False)
    limit = getattr(args, "limit", 50)

    try:
        client, creds = get_authenticated_client()
    except CredentialsError as e:
        return e.to_dict() | {"query_timestamp": query_ts}

    char_id = creds.character_id

    # Check scope
    if not creds.has_scope("esi-markets.read_character_orders.v1"):
        return {
            "error": "scope_not_authorized",
            "message": "Missing required scope: esi-markets.read_character_orders.v1",
            "action": "Re-run OAuth setup to authorize market orders access",
            "command": "python3 .claude/scripts/aria-oauth-setup.py",
            "query_timestamp": query_ts,
        }

    public_client = ESIClient()

    # Fetch active orders
    try:
        active_orders = client.get(f"/characters/{char_id}/orders/", auth=True)
    except ESIError as e:
        return {
            "error": "esi_error",
            "message": f"Could not fetch market orders: {e.message}",
            "hint": "Ensure esi-markets.read_character_orders.v1 scope is authorized",
            "query_timestamp": query_ts,
        }

    all_orders: list = list(active_orders) if isinstance(active_orders, list) else []

    # Fetch order history if requested
    if include_history:
        try:
            # Paginate history
            page = 1
            while True:
                history = client.get(
                    f"/characters/{char_id}/orders/history/", auth=True, params={"page": page}
                )
                if not isinstance(history, list) or not history:
                    break
                all_orders.extend(history)
                page += 1
                if page > 10:  # Safety limit
                    break
        except ESIError:
            pass  # History is optional, continue with active orders

    # Empty check
    if not all_orders:
        return {
            "query_timestamp": query_ts,
            "volatility": "semi_stable",
            "character_id": char_id,
            "summary": {
                "active_orders": 0,
                "buy_orders": 0,
                "sell_orders": 0,
                "total_escrow": 0,
                "total_sell_value": 0,
            },
            "orders": [],
            "message": "No market orders found",
        }

    # Collect IDs for resolution
    type_ids = set()
    location_ids = set()
    region_ids = set()

    for order in all_orders:
        type_ids.add(order.get("type_id", 0))
        location_ids.add(order.get("location_id", 0))
        region_ids.add(order.get("region_id", 0))

    # Resolve type names
    type_names = {}
    for tid in type_ids:
        if tid:
            info = public_client.get_safe(f"/universe/types/{tid}/")
            if info and "name" in info:
                type_names[tid] = info["name"]
            else:
                type_names[tid] = f"Unknown-{tid}"

    # Resolve station names
    location_names = {}
    for lid in location_ids:
        if lid:
            # Try station first
            station = public_client.get_safe(f"/universe/stations/{lid}/")
            if station and "name" in station:
                location_names[lid] = station["name"]
            else:
                location_names[lid] = f"Structure-{lid}"

    # Resolve region names
    region_names = {}
    for rid in region_ids:
        if rid:
            region = public_client.get_safe(f"/universe/regions/{rid}/")
            if region and "name" in region:
                region_names[rid] = region["name"]
            else:
                region_names[rid] = f"Region-{rid}"

    now = datetime.now(timezone.utc)
    processed_orders = []
    summary = {
        "active_orders": 0,
        "buy_orders": 0,
        "sell_orders": 0,
        "total_escrow": 0.0,
        "total_sell_value": 0.0,
    }

    for order in all_orders:
        is_buy = order.get("is_buy_order", False)

        # Apply buy/sell filter
        if buy_only and not is_buy:
            continue
        if sell_only and is_buy:
            continue

        type_id = order.get("type_id", 0)
        location_id = order.get("location_id", 0)
        region_id = order.get("region_id", 0)

        price = order.get("price", 0.0)
        volume_total = order.get("volume_total", 0)
        volume_remain = order.get("volume_remain", 0)
        escrow = order.get("escrow", 0.0) if is_buy else None

        # Calculate fill percentage
        fill_percent = 0.0
        if volume_total > 0:
            fill_percent = ((volume_total - volume_remain) / volume_total) * 100

        # Parse dates
        issued_dt = parse_datetime(order.get("issued"))
        duration = order.get("duration", 0)

        # Calculate expiration
        expires_dt = None
        days_remaining = 0
        if issued_dt and duration:
            from datetime import timedelta

            expires_dt = issued_dt + timedelta(days=duration)
            remaining = expires_dt - now
            days_remaining = max(0, remaining.days)

        # Determine state
        state = order.get("state", "active")
        if state == "active" and days_remaining == 0 and expires_dt and now > expires_dt:
            state = "expired"

        # Update summary
        if state == "active":
            summary["active_orders"] += 1
            if is_buy:
                summary["buy_orders"] += 1
                if escrow:
                    summary["total_escrow"] += escrow
            else:
                summary["sell_orders"] += 1
                summary["total_sell_value"] += price * volume_remain

        processed_order = {
            "order_id": order.get("order_id"),
            "type_id": type_id,
            "type_name": type_names.get(type_id, f"Unknown-{type_id}"),
            "is_buy_order": is_buy,
            "location_id": location_id,
            "location_name": location_names.get(location_id, f"Structure-{location_id}"),
            "region_id": region_id,
            "region_name": region_names.get(region_id, f"Region-{region_id}"),
            "price": price,
            "volume_total": volume_total,
            "volume_remain": volume_remain,
            "fill_percent": round(fill_percent, 1),
            "issued": order.get("issued"),
            "duration": duration,
            "expires": expires_dt.isoformat() if expires_dt else None,
            "days_remaining": days_remaining,
            "state": state,
            "min_volume": order.get("min_volume", 1),
            "range": _format_range(order.get("range", "station")),
            "escrow": escrow,
        }

        processed_orders.append(processed_order)

    # Sort: active first, then by days remaining (ascending)
    def sort_key(o):
        state_order = {"active": 0, "expired": 1, "cancelled": 2}
        order_type = 0 if not o["is_buy_order"] else 1  # Sell before buy
        return (state_order.get(o["state"], 3), order_type, o["days_remaining"], o["type_name"])

    processed_orders.sort(key=sort_key)
    processed_orders = processed_orders[:limit]

    return {
        "query_timestamp": query_ts,
        "volatility": "semi_stable",
        "character_id": char_id,
        "summary": {
            "active_orders": summary["active_orders"],
            "buy_orders": summary["buy_orders"],
            "sell_orders": summary["sell_orders"],
            "total_escrow": round(summary["total_escrow"], 2),
            "total_sell_value": round(summary["total_sell_value"], 2),
        },
        "orders": processed_orders,
        "filters": {
            "buy_only": buy_only,
            "sell_only": sell_only,
            "include_history": include_history,
            "limit": limit,
        },
    }


# =============================================================================
# Argument Parser Registration
# =============================================================================


def register_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Register market orders command parsers."""

    parser = subparsers.add_parser("orders", help="Show market orders (buy/sell)")
    parser.add_argument("--buy", action="store_true", help="Show only buy orders")
    parser.add_argument("--sell", action="store_true", help="Show only sell orders")
    parser.add_argument("--history", action="store_true", help="Include expired/cancelled orders")
    parser.add_argument(
        "--limit", "-n", type=int, default=50, help="Limit number of results (default: 50)"
    )
    parser.set_defaults(func=cmd_orders)
