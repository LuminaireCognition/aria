"""
ARIA ESI Assets Commands

Asset management: inventory, ship fittings, blueprints.
All commands require authentication.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import requests  # type: ignore[import-untyped]

from ..core import (
    SHIP_GROUP_IDS,
    SLOT_ORDER,
    CredentialsError,
    ESIClient,
    ESIError,
    get_authenticated_client,
    get_utc_timestamp,
)
from ..services.asset_snapshots import get_snapshot_service
from ..services.asset_insights import (
    find_duplicate_ships,
    generate_insights_summary,
    get_trade_hub_station_ids,
    identify_forgotten_assets,
    suggest_consolidations,
)

# =============================================================================
# Assets Command
# =============================================================================


def cmd_assets(args: argparse.Namespace) -> dict:
    """
    Fetch character asset inventory.

    Supports filters: --ships (assembled ships only), --type <name>, --location <name>
    Optional: --value to include market valuations
    Optional: --snapshot to save current state
    Optional: --trends to show value changes over time
    Optional: --history to list available snapshots
    """
    query_ts = get_utc_timestamp()
    filter_type = getattr(args, "filter_type", None)
    filter_value = None
    include_value = getattr(args, "value", False)
    save_snapshot = getattr(args, "snapshot", False)
    show_trends = getattr(args, "trends", False)
    show_history = getattr(args, "history", False)
    show_insights = getattr(args, "insights", False)

    # Check for type or location filters
    type_filter = getattr(args, "type_filter", None)
    location_filter = getattr(args, "location_filter", None)

    if type_filter:
        filter_type = "type"
        filter_value = type_filter
    elif location_filter:
        filter_type = "location"
        filter_value = location_filter

    try:
        client, creds = get_authenticated_client()
    except CredentialsError as e:
        return e.to_dict() | {"query_timestamp": query_ts}

    char_id = creds.character_id
    public_client = ESIClient()

    # Handle history listing (doesn't need to fetch assets)
    if show_history:
        return _handle_snapshot_history(creds, query_ts)

    # Handle trends display (doesn't need to fetch assets)
    if show_trends and not save_snapshot:
        return _handle_snapshot_trends(creds, query_ts)

    # Handle insights (needs full asset processing with valuation)
    if show_insights:
        return _handle_asset_insights(creds, query_ts, save_snapshot=save_snapshot)

    # Fetch assets
    try:
        assets = client.get(f"/characters/{char_id}/assets/", auth=True)
    except ESIError as e:
        return {
            "error": "esi_error",
            "message": f"Could not fetch assets: {e.message}",
            "hint": "Ensure esi-assets.read_assets.v1 scope is authorized",
            "query_timestamp": query_ts,
        }

    if not isinstance(assets, list):
        assets = []

    if not assets:
        return {
            "query_timestamp": query_ts,
            "volatility": "semi_stable",
            "total_assets": 0,
            "filtered_count": 0,
            "assets": [],
            "message": "No assets found",
        }

    # Collect unique type_ids and location_ids for resolution
    type_ids = set(a["type_id"] for a in assets)
    location_ids = set(a["location_id"] for a in assets if a.get("location_type") == "station")

    # Resolve type names and group IDs
    type_info = {}
    for tid in type_ids:
        info = public_client.get_dict_safe(f"/universe/types/{tid}/")
        if info and "name" in info:
            type_info[tid] = {"name": info["name"], "group_id": info.get("group_id", 0)}

    # Resolve station names
    station_names = {}
    for lid in location_ids:
        info = public_client.get_dict_safe(f"/universe/stations/{lid}/")
        if info and "name" in info:
            station_names[lid] = info["name"]

    # Filter and process assets
    result_assets = []
    ships_found = []

    for a in assets:
        tid = a["type_id"]
        tinfo = type_info.get(tid, {"name": f"Unknown-{tid}", "group_id": 0})
        name = tinfo["name"]
        group_id = tinfo["group_id"]

        # Determine location name
        loc_id = a["location_id"]
        if a.get("location_type") == "station":
            location = station_names.get(loc_id, f"Station-{loc_id}")
        elif a.get("location_type") == "item":
            location = f"In container/ship ({loc_id})"
        else:
            location = f"Location-{loc_id}"

        # Apply filters
        if filter_type == "ships":
            # Only show assembled ships in hangars
            if group_id not in SHIP_GROUP_IDS:
                continue
            if not a.get("is_singleton", False):
                continue  # Packaged ships don't count
            if a.get("location_flag") != "Hangar":
                continue

            ships_found.append(
                {
                    "item_id": a["item_id"],
                    "type_id": tid,
                    "name": name,
                    "location": location,
                    "location_id": loc_id,
                }
            )
            continue

        elif filter_type == "type" and filter_value:
            if filter_value.lower() not in name.lower():
                continue

        elif filter_type == "location" and filter_value:
            if filter_value.lower() not in location.lower():
                continue

        result_assets.append(
            {
                "item_id": a["item_id"],
                "type_id": tid,
                "name": name,
                "quantity": a.get("quantity", 1),
                "location": location,
                "location_flag": a.get("location_flag", ""),
                "is_singleton": a.get("is_singleton", False),
            }
        )

    # Output based on filter type
    if filter_type == "ships":
        ships_found.sort(key=lambda x: x["name"])
        result: dict[str, Any] = {
            "query_timestamp": query_ts,
            "volatility": "semi_stable",
            "ship_count": len(ships_found),
            "ships": ships_found,
        }
        # Add valuation for ships if requested
        if include_value and ships_found:
            valuation = _calculate_asset_valuation(ships_found, type_info, public_client)
            result["valuation"] = valuation
            # Save snapshot if requested
            if save_snapshot:
                snapshot_result = _save_asset_snapshot(creds, valuation)
                result["snapshot"] = snapshot_result
        return result
    else:
        # Sort by name
        result_assets.sort(key=lambda x: x["name"])
        truncated = len(result_assets) > 100
        result = {
            "query_timestamp": query_ts,
            "volatility": "semi_stable",
            "total_assets": len(assets),
            "filtered_count": len(result_assets),
            "filter": {"type": filter_type, "value": filter_value} if filter_type else None,
            "assets": result_assets[:100] if truncated else result_assets,
            "truncated": truncated,
        }
        # Add valuation if requested (or if saving snapshot)
        if (include_value or save_snapshot) and result_assets:
            valuation = _calculate_asset_valuation(result_assets, type_info, public_client)
            result["valuation"] = valuation
            # Save snapshot if requested
            if save_snapshot:
                snapshot_result = _save_asset_snapshot(creds, valuation)
                result["snapshot"] = snapshot_result
        elif save_snapshot:
            result["snapshot"] = {
                "error": "no_assets",
                "message": "No assets to snapshot",
            }
        return result


# =============================================================================
# Snapshot Helpers
# =============================================================================


def _get_pilot_dir(creds: Any) -> Path:
    """Get the pilot's userdata directory."""
    # Build path from credentials
    from pathlib import Path

    # Try to find the pilot directory
    userdata = Path("userdata/pilots")
    if not userdata.exists():
        userdata.mkdir(parents=True, exist_ok=True)

    # Look for directory matching character ID
    char_id = str(creds.character_id)
    for d in userdata.iterdir():
        if d.is_dir() and d.name.startswith(char_id):
            return d

    # Create default directory if not found
    default_dir = userdata / f"{char_id}_pilot"
    default_dir.mkdir(exist_ok=True)
    return default_dir


def _save_asset_snapshot(
    creds: Any,
    valuation: dict,
    location_values: dict[int, float] | None = None,
    insights_summary: dict | None = None,
) -> dict:
    """
    Save an asset snapshot from valuation data.

    Args:
        creds: Character credentials
        valuation: Valuation data with total_value and item_values
        location_values: Optional dict mapping location_id to total value at that location
        insights_summary: Optional insights summary from generate_insights_summary()

    Returns:
        Dict with saved status, filename, and total_value
    """
    pilot_dir = _get_pilot_dir(creds)
    service = get_snapshot_service(pilot_dir)

    # Extract data from valuation
    total_value = valuation.get("total_value", 0)
    item_values = valuation.get("item_values", [])

    # Build by_category (simplified - could be enhanced with group lookups)
    by_category: dict[str, float] = {}
    for item in item_values:
        # Simple categorization by name patterns
        name = item.get("name", "").lower()
        if "blueprint" in name:
            cat = "blueprints"
        elif any(x in name for x in ["drone", "fighter"]):
            cat = "drones"
        elif any(x in name for x in ["tritanium", "pyerite", "mexallon", "isogen", "nocxium", "zydrine", "megacyte"]):
            cat = "minerals"
        else:
            cat = "other"
        by_category[cat] = by_category.get(cat, 0) + item.get("total_value", 0)

    # Build top_items
    top_items = [
        {
            "type_id": item.get("type_id"),
            "name": item.get("name"),
            "value": item.get("total_value"),
        }
        for item in item_values[:20]
    ]

    # Use provided location values or empty dict
    by_location = location_values or {}

    try:
        filepath = service.save_snapshot(
            total_value=total_value,
            by_category=by_category,
            by_location=by_location,
            top_items=top_items,
            insights=insights_summary,
        )
        return {
            "saved": True,
            "file": str(filepath.name),
            "total_value": total_value,
            "has_insights": insights_summary is not None,
        }
    except Exception as e:
        return {
            "saved": False,
            "error": str(e),
        }


def _handle_snapshot_history(creds: Any, query_ts: str) -> dict:
    """List available snapshots."""
    pilot_dir = _get_pilot_dir(creds)
    service = get_snapshot_service(pilot_dir)

    dates = service.list_snapshots()

    if not dates:
        return {
            "query_timestamp": query_ts,
            "snapshot_count": 0,
            "snapshots": [],
            "message": "No snapshots available. Use --snapshot to create one.",
        }

    # Load summary info for each snapshot
    snapshots = []
    for date in dates[:30]:  # Limit to most recent 30
        snapshot = service.load_snapshot(date)
        if snapshot:
            snapshots.append({
                "date": date,
                "total_value": snapshot.get("total_value", 0),
            })

    return {
        "query_timestamp": query_ts,
        "snapshot_count": len(dates),
        "snapshots": snapshots,
    }


def _handle_snapshot_trends(creds: Any, query_ts: str, days: int = 7) -> dict:
    """Show asset value trends."""
    pilot_dir = _get_pilot_dir(creds)
    service = get_snapshot_service(pilot_dir)

    trends = service.calculate_trends(days=days)

    if "error" in trends:
        return {
            "query_timestamp": query_ts,
            **trends,
            "hint": "Use --snapshot to save current asset values.",
        }

    # Get high water mark
    hwm = service.get_high_water_mark()
    if hwm:
        trends["all_time_high"] = hwm.get("total_value", 0)

    return {
        "query_timestamp": query_ts,
        "volatility": "semi_stable",
        **trends,
    }


def _handle_asset_insights(creds: Any, query_ts: str, save_snapshot: bool = False) -> dict:
    """
    Generate smart insights about asset inventory.

    Includes:
    - Forgotten assets (low value at non-hub locations)
    - Consolidation suggestions
    - Duplicate ship detection

    Args:
        creds: Character credentials
        query_ts: Query timestamp string
        save_snapshot: If True, save insights with snapshot
    """
    from collections import defaultdict

    char_id = creds.character_id
    client, _ = get_authenticated_client()
    public_client = ESIClient()

    # Fetch assets
    try:
        assets = client.get(f"/characters/{char_id}/assets/", auth=True)
    except ESIError as e:
        return {
            "error": "esi_error",
            "message": f"Could not fetch assets: {e.message}",
            "query_timestamp": query_ts,
        }

    if not isinstance(assets, list) or not assets:
        return {
            "query_timestamp": query_ts,
            "insights": {
                "summary": {
                    "has_insights": False,
                    "message": "No assets found",
                },
            },
        }

    # Collect unique type_ids and location_ids for resolution
    type_ids = set(a["type_id"] for a in assets)
    location_ids = set(a["location_id"] for a in assets if a.get("location_type") == "station")

    # Resolve type names and group IDs
    type_info = {}
    for tid in type_ids:
        info = public_client.get_dict_safe(f"/universe/types/{tid}/")
        if info and "name" in info:
            type_info[tid] = {"name": info["name"], "group_id": info.get("group_id", 0)}

    # Resolve station names
    station_names: dict[int, str] = {}
    for lid in location_ids:
        info = public_client.get_dict_safe(f"/universe/stations/{lid}/")
        if info and "name" in info:
            station_names[lid] = info["name"]

    # Group assets by location and prepare for insights
    assets_by_location: dict[int, list[dict]] = defaultdict(list)
    processed_assets = []

    for a in assets:
        tid = a["type_id"]
        tinfo = type_info.get(tid, {"name": f"Unknown-{tid}", "group_id": 0})
        name = tinfo["name"]

        # Determine location name
        loc_id = a["location_id"]
        if a.get("location_type") == "station":
            location = station_names.get(loc_id, f"Station-{loc_id}")
        elif a.get("location_type") == "item":
            location = f"In container/ship ({loc_id})"
        else:
            location = f"Location-{loc_id}"

        asset_entry = {
            "item_id": a["item_id"],
            "type_id": tid,
            "name": name,
            "quantity": a.get("quantity", 1),
            "location": location,
            "location_id": loc_id,
            "is_singleton": a.get("is_singleton", False),
        }

        # Only group station assets for location analysis
        if a.get("location_type") == "station":
            assets_by_location[loc_id].append(asset_entry)

        processed_assets.append(asset_entry)

    # Get prices for valuation
    type_ids_str = ",".join(str(tid) for tid in type_ids)
    price_data = {}
    try:
        resp = requests.get(
            f"https://market.fuzzwork.co.uk/aggregates/?station=60003760&types={type_ids_str}",
            timeout=15,
        )
        resp.raise_for_status()
        price_data = resp.json()
    except (requests.RequestException, ValueError):
        pass  # Continue without prices

    # Calculate values per location
    location_values: dict[int, float] = defaultdict(float)
    for loc_id, loc_assets in assets_by_location.items():
        for asset in loc_assets:
            tid_str = str(asset["type_id"])
            if tid_str in price_data:
                unit_price = float(price_data[tid_str].get("sell", {}).get("min", 0))
                location_values[loc_id] += unit_price * asset.get("quantity", 1)

    # Run insight analysis
    forgotten = identify_forgotten_assets(
        assets_by_location,
        station_names,
        dict(location_values),
    )

    # Load home systems from config for consolidation suggestions
    home_systems = _load_home_systems()

    # Create a simple route calculator if possible (just returns None for now)
    # Full integration would use universe MCP dispatcher
    consolidations = suggest_consolidations(
        forgotten,
        home_systems,
        route_calculator=None,  # Would need MCP integration
    )

    # Find duplicate ships
    duplicates = find_duplicate_ships(
        processed_assets,
        type_info,
        SHIP_GROUP_IDS,
    )

    # Generate summary
    summary = generate_insights_summary(forgotten, consolidations, duplicates)

    result: dict[str, Any] = {
        "query_timestamp": query_ts,
        "volatility": "semi_stable",
        "insights": {
            "summary": summary,
            "forgotten_assets": forgotten[:20],  # Top 20 lowest value
            "consolidation_suggestions": consolidations[:20],
            "duplicate_ships": duplicates[:10],  # Top 10 by count
        },
    }

    # Save snapshot with insights if requested
    if save_snapshot:
        # Calculate total value for snapshot
        total_value = sum(location_values.values())

        # Build valuation dict for _save_asset_snapshot
        valuation = {
            "total_value": total_value,
            "item_values": [],  # Would need full item valuation; insights focuses on locations
        }

        snapshot_result = _save_asset_snapshot(
            creds,
            valuation,
            location_values=dict(location_values),
            insights_summary=summary,
        )
        result["snapshot"] = snapshot_result

    return result


def _load_home_systems() -> list[str]:
    """Load home systems from config.json."""
    import json
    from pathlib import Path

    config_path = Path("userdata/config.json")
    if not config_path.exists():
        return []

    try:
        with open(config_path) as f:
            config = json.load(f)

        # Extract home systems from context_topology
        topology = config.get("redisq", {}).get("context_topology", {})
        geographic = topology.get("geographic", {})
        systems = geographic.get("systems", [])

        return [
            s["name"]
            for s in systems
            if s.get("classification") == "home"
        ]
    except (json.JSONDecodeError, KeyError):
        return []


# =============================================================================
# Asset Valuation Helper
# =============================================================================


def _calculate_asset_valuation(
    assets: list[dict], type_info: dict, public_client: ESIClient
) -> dict:
    """
    Calculate market valuation for a list of assets.

    Uses Fuzzwork market API for bulk price lookups.
    Returns valuation summary with total and per-item breakdown.
    """
    # Group assets by type_id and sum quantities
    type_quantities: dict[int, int] = {}
    type_names: dict[int, str] = {}

    for asset in assets:
        tid = asset.get("type_id")
        if not tid:
            continue
        qty = asset.get("quantity", 1)
        type_quantities[tid] = type_quantities.get(tid, 0) + qty
        if tid not in type_names:
            info = type_info.get(tid, {})
            type_names[tid] = info.get("name", asset.get("name", f"Unknown-{tid}"))

    if not type_quantities:
        return {"total_value": 0, "item_values": [], "price_source": "none"}

    # Fetch prices from Fuzzwork API (Jita prices)
    type_ids_str = ",".join(str(tid) for tid in type_quantities.keys())
    try:
        # Fuzzwork aggregates endpoint
        resp = requests.get(
            f"https://market.fuzzwork.co.uk/aggregates/?station=60003760&types={type_ids_str}",
            timeout=10,
        )
        resp.raise_for_status()
        price_data = resp.json()
    except (requests.RequestException, ValueError):
        # Fallback: return without prices
        return {
            "total_value": 0,
            "item_values": [],
            "price_source": "unavailable",
            "error": "Could not fetch market prices",
        }

    # Calculate values
    item_values = []
    total_value: float = 0.0

    for tid, qty in type_quantities.items():
        tid_str = str(tid)
        if tid_str in price_data:
            # Use sell price (what you'd pay to buy, conservative for valuation)
            sell_data = price_data[tid_str].get("sell", {})
            unit_price = float(sell_data.get("min", 0))
        else:
            unit_price = 0

        item_total = unit_price * qty
        total_value += item_total

        item_values.append(
            {
                "type_id": tid,
                "name": type_names.get(tid, f"Unknown-{tid}"),
                "quantity": qty,
                "unit_price": unit_price,
                "total_value": item_total,
            }
        )

    # Sort by total value descending
    item_values.sort(key=lambda x: x["total_value"], reverse=True)  # type: ignore[arg-type,return-value]

    return {
        "total_value": total_value,
        "item_count": len(item_values),
        "item_values": item_values[:50],  # Top 50 by value
        "truncated": len(item_values) > 50,
        "price_source": "fuzzwork_jita",
    }


# =============================================================================
# Fitting Command
# =============================================================================


def cmd_fitting(args: argparse.Namespace) -> dict:
    """
    Extract ship fitting in EFT format.

    Finds ship by name or item_id and returns fitting with exportable EFT format.
    """
    query_ts = get_utc_timestamp()
    ship_query = getattr(args, "ship", None)

    if not ship_query:
        return {
            "error": "missing_argument",
            "message": "Ship name or item_id required",
            "hint": "Use 'assets --ships' to list available ships",
            "query_timestamp": query_ts,
        }

    try:
        client, creds = get_authenticated_client()
    except CredentialsError as e:
        return e.to_dict() | {"query_timestamp": query_ts}

    char_id = creds.character_id
    public_client = ESIClient()

    # Fetch all assets
    try:
        assets = client.get(f"/characters/{char_id}/assets/", auth=True)
    except ESIError as e:
        return {
            "error": "esi_error",
            "message": f"Could not fetch assets: {e.message}",
            "query_timestamp": query_ts,
        }

    if not isinstance(assets, list):
        assets = []

    # Resolve type names for all assets
    type_ids = set(a["type_id"] for a in assets)
    type_info = {}

    for tid in type_ids:
        info = public_client.get_dict_safe(f"/universe/types/{tid}/")
        if info and "name" in info:
            type_info[tid] = {"name": info["name"], "group_id": info.get("group_id", 0)}

    # Find matching ship
    target_ship = None
    is_item_id_query = ship_query.isdigit()

    for a in assets:
        tid = a["type_id"]
        tinfo = type_info.get(tid, {"name": "", "group_id": 0})

        # Must be a ship
        if tinfo["group_id"] not in SHIP_GROUP_IDS:
            continue

        # Must be assembled and in hangar
        if not a.get("is_singleton", False):
            continue
        if a.get("location_flag") != "Hangar":
            continue

        # Match by item_id or name
        if is_item_id_query:
            if str(a["item_id"]) == ship_query:
                target_ship = a
                break
        else:
            if ship_query.lower() in tinfo["name"].lower():
                target_ship = a
                break

    if not target_ship:
        return {
            "error": "ship_not_found",
            "message": f"No assembled ship matching '{ship_query}' found in hangars",
            "hint": "Use 'assets --ships' to list available ships",
            "query_timestamp": query_ts,
        }

    ship_item_id = target_ship["item_id"]
    ship_type_id = target_ship["type_id"]
    ship_type_name = type_info.get(ship_type_id, {}).get("name", "Unknown")

    # Get station name
    loc_id = target_ship["location_id"]
    station_info = public_client.get_dict_safe(f"/universe/stations/{loc_id}/")
    station_name = (
        station_info.get("name", f"Station-{loc_id}") if station_info else f"Station-{loc_id}"
    )

    # Find all items fitted to this ship
    fitted_items = [a for a in assets if a.get("location_id") == ship_item_id]

    # Categorize by slot
    slots = {
        "high": [],
        "med": [],
        "low": [],
        "rig": [],
        "drone_bay": [],
        "cargo": [],
        "fighter_bay": [],
        "subsystem": [],
    }

    for item in fitted_items:
        flag = item.get("location_flag", "")
        tid = item["type_id"]
        tinfo = type_info.get(tid, {"name": f"Unknown-{tid}"})
        name = tinfo["name"]
        qty = item.get("quantity", 1)

        entry = {"name": name, "type_id": tid, "quantity": qty}

        if flag.startswith("HiSlot"):
            entry["slot"] = SLOT_ORDER.get(flag, 99)
            slots["high"].append(entry)
        elif flag.startswith("MedSlot"):
            entry["slot"] = SLOT_ORDER.get(flag, 99)
            slots["med"].append(entry)
        elif flag.startswith("LoSlot"):
            entry["slot"] = SLOT_ORDER.get(flag, 99)
            slots["low"].append(entry)
        elif flag.startswith("RigSlot"):
            entry["slot"] = SLOT_ORDER.get(flag, 99)
            slots["rig"].append(entry)
        elif flag == "DroneBay":
            slots["drone_bay"].append(entry)
        elif flag == "FighterBay":
            slots["fighter_bay"].append(entry)
        elif flag.startswith("SubSystem"):
            slots["subsystem"].append(entry)
        elif flag in ("Cargo", "FleetHangar", "Unlocked", "SpecializedAmmoHold"):
            slots["cargo"].append(entry)

    # Sort slots by slot number
    for slot_type in ["high", "med", "low", "rig"]:
        slots[slot_type].sort(key=lambda x: x.get("slot", 99))

    # Sort drone/cargo by name
    for slot_type in ["drone_bay", "cargo", "fighter_bay", "subsystem"]:
        slots[slot_type].sort(key=lambda x: x["name"])

    # Generate EFT format
    eft_lines = [f"[{ship_type_name}, ARIA Export]", ""]

    # Low slots
    for item in slots["low"]:
        eft_lines.append(item["name"])
    if not slots["low"]:
        eft_lines.append("[Empty Low slot]")
    eft_lines.append("")

    # Med slots
    for item in slots["med"]:
        eft_lines.append(item["name"])
    if not slots["med"]:
        eft_lines.append("[Empty Med slot]")
    eft_lines.append("")

    # High slots
    for item in slots["high"]:
        eft_lines.append(item["name"])
    if not slots["high"]:
        eft_lines.append("[Empty High slot]")
    eft_lines.append("")

    # Rigs
    for item in slots["rig"]:
        eft_lines.append(item["name"])
    if not slots["rig"]:
        eft_lines.append("[Empty Rig slot]")

    # Subsystems (T3 only)
    if slots["subsystem"]:
        eft_lines.append("")
        for item in slots["subsystem"]:
            eft_lines.append(item["name"])

    # Drones (two blank lines before)
    if slots["drone_bay"]:
        eft_lines.append("")
        eft_lines.append("")
        # Aggregate drones by name
        drone_counts = {}
        for d in slots["drone_bay"]:
            name = d["name"]
            drone_counts[name] = drone_counts.get(name, 0) + d["quantity"]
        for name, count in sorted(drone_counts.items()):
            eft_lines.append(f"{name} x{count}")

    # Cargo (two blank lines before)
    if slots["cargo"]:
        eft_lines.append("")
        eft_lines.append("")
        # Aggregate cargo by name
        cargo_counts = {}
        for c in slots["cargo"]:
            name = c["name"]
            cargo_counts[name] = cargo_counts.get(name, 0) + c["quantity"]
        for name, count in sorted(cargo_counts.items()):
            eft_lines.append(f"{name} x{count}")

    eft_format = "\n".join(eft_lines)

    return {
        "query_timestamp": query_ts,
        "volatility": "semi_stable",
        "ship": {
            "item_id": ship_item_id,
            "type_id": ship_type_id,
            "type_name": ship_type_name,
            "location": station_name,
        },
        "fitting": {
            "high_slots": [{"name": x["name"], "type_id": x["type_id"]} for x in slots["high"]],
            "med_slots": [{"name": x["name"], "type_id": x["type_id"]} for x in slots["med"]],
            "low_slots": [{"name": x["name"], "type_id": x["type_id"]} for x in slots["low"]],
            "rig_slots": [{"name": x["name"], "type_id": x["type_id"]} for x in slots["rig"]],
            "subsystems": [
                {"name": x["name"], "type_id": x["type_id"]} for x in slots["subsystem"]
            ],
            "drone_bay": slots["drone_bay"],
            "cargo": slots["cargo"],
        },
        "eft_format": eft_format,
    }


# =============================================================================
# Blueprints Command
# =============================================================================


def cmd_blueprints(args: argparse.Namespace) -> dict:
    """
    Fetch character blueprint library (BPOs and BPCs).

    Returns list of blueprints with ME/TE research levels.
    """
    query_ts = get_utc_timestamp()

    try:
        client, creds = get_authenticated_client()
    except CredentialsError as e:
        return e.to_dict() | {"query_timestamp": query_ts}

    char_id = creds.character_id
    public_client = ESIClient()

    # Fetch blueprints
    try:
        blueprints = client.get(f"/characters/{char_id}/blueprints/", auth=True)
    except ESIError as e:
        return {
            "error": "esi_error",
            "message": f"Could not fetch blueprints: {e.message}",
            "hint": "Ensure esi-characters.read_blueprints.v1 scope is authorized",
            "query_timestamp": query_ts,
        }

    if not isinstance(blueprints, list):
        blueprints = []

    if not blueprints:
        return {
            "query_timestamp": query_ts,
            "volatility": "semi_stable",
            "bpo_count": 0,
            "bpc_count": 0,
            "bpos": [],
            "bpcs": [],
            "message": "No blueprints found",
        }

    # Collect unique type_ids and location_ids for resolution
    type_ids = set(bp["type_id"] for bp in blueprints)
    location_ids = set(bp["location_id"] for bp in blueprints)

    # Resolve type names
    type_names = {}
    for tid in type_ids:
        info = public_client.get_dict_safe(f"/universe/types/{tid}/")
        if info and "name" in info:
            type_names[tid] = info["name"]

    # Resolve location names (stations)
    location_names = {}
    for lid in location_ids:
        # Try station first
        info = public_client.get_dict_safe(f"/universe/stations/{lid}/")
        if info and "name" in info:
            location_names[lid] = info["name"]
        else:
            # Could be a structure - would need auth, skip for now
            location_names[lid] = f"Structure ({lid})"

    # Process blueprints
    bpos = []
    bpcs = []

    for bp in blueprints:
        tid = bp["type_id"]
        entry = {
            "type_id": tid,
            "name": type_names.get(tid, f"Unknown ({tid})"),
            "location": location_names.get(bp["location_id"], f"Unknown ({bp['location_id']})"),
            "material_efficiency": bp["material_efficiency"],
            "time_efficiency": bp["time_efficiency"],
        }

        if bp["quantity"] == -1:
            # BPO (infinite runs)
            entry["type"] = "BPO"
            bpos.append(entry)
        elif bp["quantity"] == -2 or bp.get("runs", 0) > 0:
            # BPC
            entry["type"] = "BPC"
            entry["runs"] = bp.get("runs", 0)
            bpcs.append(entry)

    # Sort by name
    bpos.sort(key=lambda x: x["name"])
    bpcs.sort(key=lambda x: x["name"])

    return {
        "query_timestamp": query_ts,
        "volatility": "semi_stable",
        "bpo_count": len(bpos),
        "bpc_count": len(bpcs),
        "bpos": bpos,
        "bpcs": bpcs,
    }


# =============================================================================
# Argument Parser Registration
# =============================================================================


def register_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Register assets command parsers."""

    # Assets command
    assets_parser = subparsers.add_parser("assets", help="Fetch character asset inventory")
    assets_group = assets_parser.add_mutually_exclusive_group()
    assets_group.add_argument(
        "--ships",
        action="store_const",
        const="ships",
        dest="filter_type",
        help="Show only assembled ships",
    )
    assets_parser.add_argument(
        "--type", dest="type_filter", metavar="NAME", help="Filter by item type name"
    )
    assets_parser.add_argument(
        "--location", dest="location_filter", metavar="NAME", help="Filter by location name"
    )
    assets_parser.add_argument(
        "--value",
        action="store_true",
        help="Include market valuations (uses Jita prices)",
    )
    assets_parser.add_argument(
        "--snapshot",
        action="store_true",
        help="Save current asset state for trend tracking",
    )
    assets_parser.add_argument(
        "--trends",
        action="store_true",
        help="Show asset value changes over time (7-day default)",
    )
    assets_parser.add_argument(
        "--history",
        action="store_true",
        help="List all available snapshots",
    )
    assets_parser.add_argument(
        "--insights",
        action="store_true",
        help="Show smart insights: forgotten assets, duplicates, consolidation suggestions",
    )
    assets_parser.set_defaults(
        func=cmd_assets,
        filter_type=None,
        filter_value=None,
        value=False,
        snapshot=False,
        trends=False,
        history=False,
        insights=False,
    )

    # Fitting command
    fitting_parser = subparsers.add_parser("fitting", help="Extract ship fitting in EFT format")
    fitting_parser.add_argument("ship", help="Ship name or item_id to extract fitting from")
    fitting_parser.set_defaults(func=cmd_fitting)

    # Blueprints command
    blueprints_parser = subparsers.add_parser(
        "blueprints", help="Fetch blueprint library (BPOs/BPCs)"
    )
    blueprints_parser.set_defaults(func=cmd_blueprints)
