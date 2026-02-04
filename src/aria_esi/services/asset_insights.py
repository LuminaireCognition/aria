"""
ARIA Asset Insights Service.

Provides smart analysis of asset inventory including:
- Forgotten asset detection
- Consolidation suggestions
- Duplicate ship detection
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

# Trade hub reference data
_trade_hub_data: Optional[dict[str, Any]] = None


def _load_trade_hub_data() -> dict[str, Any]:
    """Load trade hub reference data."""
    global _trade_hub_data
    if _trade_hub_data is not None:
        return _trade_hub_data

    ref_path = (
        Path(__file__).parent.parent.parent.parent
        / "reference"
        / "constants"
        / "trade_hubs.json"
    )

    # Fallback path for installed package
    if not ref_path.exists():
        ref_path = Path("reference/constants/trade_hubs.json")

    if ref_path.exists():
        with open(ref_path) as f:
            _trade_hub_data = json.load(f)
    else:
        # Default data if file not found
        _trade_hub_data = {
            "station_ids": [60003760, 60008494, 60011866, 60004588, 60005686],
            "system_names": ["Jita", "Amarr", "Dodixie", "Rens", "Hek"],
            "thresholds": {"forgotten_asset_value": 5000000},
        }

    return _trade_hub_data


def get_trade_hub_station_ids() -> list[int]:
    """Get list of major trade hub station IDs."""
    data = _load_trade_hub_data()
    return data.get("station_ids", [])


def get_trade_hub_system_names() -> list[str]:
    """Get list of major trade hub system names."""
    data = _load_trade_hub_data()
    return data.get("system_names", [])


def get_forgotten_asset_threshold() -> float:
    """Get the ISK threshold for forgotten assets."""
    data = _load_trade_hub_data()
    return data.get("thresholds", {}).get("forgotten_asset_value", 5_000_000)


def identify_forgotten_assets(
    assets_by_location: dict[int, list[dict[str, Any]]],
    location_names: dict[int, str],
    location_values: dict[int, float],
    threshold: Optional[float] = None,
) -> list[dict[str, Any]]:
    """
    Identify locations with low-value assets not in trade hubs.

    These are "forgotten" assets that may be worth consolidating.

    Args:
        assets_by_location: Dict mapping location_id to list of assets
        location_names: Dict mapping location_id to station/structure name
        location_values: Dict mapping location_id to total value at that location
        threshold: ISK threshold for "forgotten" (default 5M)

    Returns:
        List of forgotten locations sorted by value (lowest first):
        [
            {
                "location_id": int,
                "location_name": str,
                "total_value": float,
                "item_count": int,
                "system_name": str (if extractable from station name)
            }
        ]
    """
    if threshold is None:
        threshold = get_forgotten_asset_threshold()

    trade_hub_ids = set(get_trade_hub_station_ids())
    forgotten = []

    for location_id, items in assets_by_location.items():
        # Skip trade hubs
        if location_id in trade_hub_ids:
            continue

        total_value = location_values.get(location_id, 0)

        # Only include locations under threshold
        if total_value >= threshold:
            continue

        location_name = location_names.get(location_id, f"Location-{location_id}")

        # Try to extract system name from station name
        # Format: "System Name - Structure Name" or "System Planet - Moon N - Station"
        system_name = _extract_system_name(location_name)

        forgotten.append(
            {
                "location_id": location_id,
                "location_name": location_name,
                "total_value": total_value,
                "item_count": len(items),
                "system_name": system_name,
            }
        )

    # Sort by value (lowest first - easiest to abandon/consolidate)
    return sorted(forgotten, key=lambda x: x["total_value"])


def _extract_system_name(station_name: str) -> Optional[str]:
    """
    Extract system name from station name.

    Station name formats:
    - "Jita IV - Moon 4 - Caldari Navy Assembly Plant" -> "Jita"
    - "Dodixie IX - Moon 20 - Federation Navy Assembly Plant" -> "Dodixie"
    - "Structure (12345)" -> None
    """
    if station_name.startswith("Structure"):
        return None
    if station_name.startswith("Location-"):
        return None

    # Split on " - " and take first part, then strip planet designator
    parts = station_name.split(" - ")
    if not parts:
        return None

    first_part = parts[0].strip()

    # Remove roman numeral planet designators (e.g., "Jita IV" -> "Jita")
    # Common patterns: "System Name I", "System Name II", ..., "System Name XII"
    words = first_part.split()
    roman_numerals = {"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"}

    if len(words) > 1 and words[-1] in roman_numerals:
        return " ".join(words[:-1])

    return first_part


def suggest_consolidations(
    forgotten_assets: list[dict[str, Any]],
    home_systems: list[str],
    route_calculator: Optional[Any] = None,
) -> list[dict[str, Any]]:
    """
    Suggest consolidation destinations for forgotten assets.

    Args:
        forgotten_assets: List from identify_forgotten_assets
        home_systems: List of pilot's home system names
        route_calculator: Optional callable(origin, destination) -> jumps
                         If None, distances won't be calculated

    Returns:
        List of consolidation suggestions:
        [
            {
                "source_location": str,
                "source_value": float,
                "item_count": int,
                "to_home": {"system": str, "jumps": int} or None,
                "to_nearest_hub": {"system": str, "jumps": int} or None,
                "recommendation": str
            }
        ]
    """
    trade_hubs = get_trade_hub_system_names()
    suggestions = []

    for asset in forgotten_assets:
        source_system = asset.get("system_name")
        suggestion = {
            "source_location": asset["location_name"],
            "source_value": asset["total_value"],
            "item_count": asset["item_count"],
            "source_system": source_system,
            "to_home": None,
            "to_nearest_hub": None,
            "recommendation": "unknown",
        }

        # Can't calculate routes without source system
        if not source_system or not route_calculator:
            suggestion["recommendation"] = "manual_check"
            suggestions.append(suggestion)
            continue

        # Calculate distance to home systems
        best_home = None
        best_home_jumps = float("inf")
        for home in home_systems:
            try:
                jumps = route_calculator(source_system, home)
                if jumps is not None and jumps < best_home_jumps:
                    best_home_jumps = jumps
                    best_home = home
            except Exception:
                pass

        if best_home:
            suggestion["to_home"] = {"system": best_home, "jumps": int(best_home_jumps)}

        # Calculate distance to nearest trade hub
        best_hub = None
        best_hub_jumps = float("inf")
        for hub in trade_hubs:
            try:
                jumps = route_calculator(source_system, hub)
                if jumps is not None and jumps < best_hub_jumps:
                    best_hub_jumps = jumps
                    best_hub = hub
            except Exception:
                pass

        if best_hub:
            suggestion["to_nearest_hub"] = {"system": best_hub, "jumps": int(best_hub_jumps)}

        # Recommendation logic
        if best_home and best_hub:
            if best_home_jumps <= best_hub_jumps:
                suggestion["recommendation"] = f"consolidate_home"
            else:
                suggestion["recommendation"] = f"consolidate_hub"
        elif best_home:
            suggestion["recommendation"] = "consolidate_home"
        elif best_hub:
            suggestion["recommendation"] = "consolidate_hub"
        else:
            suggestion["recommendation"] = "manual_check"

        suggestions.append(suggestion)

    return suggestions


def find_duplicate_ships(
    assets: list[dict[str, Any]],
    type_info: dict[int, dict[str, Any]],
    ship_group_ids: set[int],
) -> list[dict[str, Any]]:
    """
    Find duplicate ships (same type at same or different locations).

    Args:
        assets: List of asset dicts with type_id, location_id, is_singleton
        type_info: Dict mapping type_id to {"name": str, "group_id": int}
        ship_group_ids: Set of group IDs that represent ships

    Returns:
        List of duplicate findings:
        [
            {
                "type_name": str,
                "type_id": int,
                "instances": [{"location": str, "count": int}],
                "total_count": int,
                "note": "same_location" | "multiple_locations"
            }
        ]
    """
    # Group assembled ships by type
    ships_by_type: dict[int, list[dict]] = defaultdict(list)

    for asset in assets:
        type_id = asset.get("type_id")
        if not type_id:
            continue

        info = type_info.get(type_id, {})
        group_id = info.get("group_id", 0)

        # Must be a ship
        if group_id not in ship_group_ids:
            continue

        # Must be assembled (is_singleton = True)
        if not asset.get("is_singleton", False):
            continue

        ships_by_type[type_id].append(asset)

    duplicates = []

    for type_id, instances in ships_by_type.items():
        if len(instances) < 2:
            continue

        type_name = type_info.get(type_id, {}).get("name", f"Unknown-{type_id}")

        # Group by location
        by_location: dict[int, int] = defaultdict(int)
        location_names: dict[int, str] = {}

        for ship in instances:
            loc_id = ship.get("location_id", 0)
            by_location[loc_id] += 1
            if loc_id not in location_names:
                location_names[loc_id] = ship.get("location", f"Location-{loc_id}")

        # Check for duplicates at same location
        same_location_dupes = [
            {"location": location_names[loc_id], "count": count}
            for loc_id, count in by_location.items()
            if count > 1
        ]

        if same_location_dupes:
            duplicates.append(
                {
                    "type_name": type_name,
                    "type_id": type_id,
                    "instances": same_location_dupes,
                    "total_count": sum(d["count"] for d in same_location_dupes),
                    "note": "same_location",
                }
            )

        # Also note if same ship type exists at multiple locations
        if len(by_location) > 1:
            all_locations = [
                {"location": location_names[loc_id], "count": count}
                for loc_id, count in by_location.items()
            ]
            duplicates.append(
                {
                    "type_name": type_name,
                    "type_id": type_id,
                    "instances": all_locations,
                    "total_count": len(instances),
                    "note": "multiple_locations",
                }
            )

    # Sort by total count (most duplicates first)
    return sorted(duplicates, key=lambda x: x["total_count"], reverse=True)


def generate_insights_summary(
    forgotten: list[dict[str, Any]],
    consolidations: list[dict[str, Any]],
    duplicates: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Generate a summary of all asset insights.

    Args:
        forgotten: Results from identify_forgotten_assets
        consolidations: Results from suggest_consolidations
        duplicates: Results from find_duplicate_ships

    Returns:
        Summary dict with counts and highlights
    """
    total_forgotten_value = sum(f["total_value"] for f in forgotten)
    total_forgotten_items = sum(f["item_count"] for f in forgotten)

    # Count consolidation recommendations
    home_recs = sum(1 for c in consolidations if c["recommendation"] == "consolidate_home")
    hub_recs = sum(1 for c in consolidations if c["recommendation"] == "consolidate_hub")

    # Count duplicate types
    same_loc_dupes = [d for d in duplicates if d["note"] == "same_location"]
    multi_loc_dupes = [d for d in duplicates if d["note"] == "multiple_locations"]

    return {
        "forgotten_assets": {
            "location_count": len(forgotten),
            "total_value": total_forgotten_value,
            "total_items": total_forgotten_items,
            "threshold": get_forgotten_asset_threshold(),
        },
        "consolidation_suggestions": {
            "total": len(consolidations),
            "recommend_home": home_recs,
            "recommend_hub": hub_recs,
        },
        "duplicate_ships": {
            "same_location_types": len(same_loc_dupes),
            "multi_location_types": len(multi_loc_dupes),
        },
        "has_insights": bool(forgotten or duplicates),
    }
