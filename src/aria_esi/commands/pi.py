"""
ARIA ESI PI Commands

Planetary Interaction location planning and planet cache management.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

from ..core import ESIClient, get_utc_timestamp
from ..services.planet_cache import (
    fetch_system_planets_sync,
    find_planets_for_product,
    get_planet_cache_service,
    get_resources_for_planet_type,
)

logger = logging.getLogger(__name__)


def cmd_cache_planets(args: argparse.Namespace) -> dict:
    """
    Build or refresh planet type cache for systems.

    Fetches planet data from ESI for specified systems or regions.
    """
    query_ts = get_utc_timestamp()
    systems = getattr(args, "systems", None) or []
    region = getattr(args, "region", None)
    around = getattr(args, "around", None)
    jumps = getattr(args, "jumps", 10)
    clear = getattr(args, "clear", False)

    service = get_planet_cache_service()

    # Handle clear
    if clear:
        service.clear_cache()
        return {
            "query_timestamp": query_ts,
            "action": "cleared",
            "message": "Planet cache cleared",
        }

    # Get ESI client
    esi = ESIClient()

    # Collect systems to cache
    systems_to_fetch: list[dict[str, Any]] = []

    if systems:
        # Explicit system names provided
        for system_name in systems:
            system_id = _resolve_system_id(system_name, esi)
            if system_id:
                systems_to_fetch.append({
                    "name": system_name,
                    "id": system_id,
                })
            else:
                return {
                    "query_timestamp": query_ts,
                    "error": "system_not_found",
                    "message": f"Could not resolve system: {system_name}",
                }

    elif around:
        # Fetch systems around a central system
        center_id = _resolve_system_id(around, esi)
        if not center_id:
            return {
                "query_timestamp": query_ts,
                "error": "system_not_found",
                "message": f"Could not resolve system: {around}",
            }

        # Use universe graph to find nearby systems
        # This would ideally use the MCP dispatcher but falls back to ESI
        nearby = _get_systems_within_jumps(center_id, jumps, esi)
        systems_to_fetch = nearby

    elif region:
        # Fetch all systems in a region
        region_id = _resolve_region_id(region, esi)
        if not region_id:
            return {
                "query_timestamp": query_ts,
                "error": "region_not_found",
                "message": f"Could not resolve region: {region}",
            }

        systems_to_fetch = _get_systems_in_region(region_id, esi)

    else:
        # No systems specified - show cache stats
        stats = service.get_cache_stats()
        cache = service.load_cache()

        return {
            "query_timestamp": query_ts,
            "action": "stats",
            "cache_stats": stats,
            "systems_cached": len(cache.get("systems", {})),
            "hint": "Use --systems, --region, or --around to add systems to cache",
        }

    # Fetch planet data for each system
    cached = 0
    skipped = 0
    errors = []

    for system in systems_to_fetch:
        system_name = system["name"]
        system_id = system["id"]

        # Skip if already cached (unless force refresh)
        if service.is_system_cached(system_name) and not getattr(args, "force", False):
            skipped += 1
            continue

        try:
            planets = fetch_system_planets_sync(system_id, esi)
            service.add_system(system_name, system_id, planets)
            cached += 1
        except Exception as e:
            errors.append({"system": system_name, "error": str(e)})

    # Save cache
    service.save_cache()

    return {
        "query_timestamp": query_ts,
        "action": "cached",
        "systems_cached": cached,
        "systems_skipped": skipped,
        "errors": errors if errors else None,
        "cache_stats": service.get_cache_stats(),
    }


def cmd_pi_near(args: argparse.Namespace) -> dict:
    """
    Find planets near home systems for PI production.

    Searches cached systems for planets that can produce the specified product.
    Now with distance-aware filtering and sorting.
    """
    query_ts = get_utc_timestamp()
    product = getattr(args, "product", None)
    max_jumps = getattr(args, "jumps", 10)

    if not product:
        return {
            "query_timestamp": query_ts,
            "error": "missing_argument",
            "message": "Product name required",
            "hint": "Usage: pi-near <product> [--jumps N]",
        }

    # Find what planets are needed for this product
    product_info = find_planets_for_product(product)

    if "error" in product_info:
        return {
            "query_timestamp": query_ts,
            "error": "product_not_found",
            "message": product_info["error"],
        }

    # Load home systems from config
    home_systems = _load_home_systems()
    if not home_systems:
        return {
            "query_timestamp": query_ts,
            "error": "no_home_systems",
            "message": "No home systems configured",
            "hint": "Add home systems to userdata/config.json under redisq.context_topology.geographic.systems",
        }

    # Get planet cache
    service = get_planet_cache_service()
    cache = service.load_cache()
    systems_data = cache.get("systems", {})

    if not systems_data:
        return {
            "query_timestamp": query_ts,
            "error": "cache_empty",
            "message": "Planet cache is empty",
            "hint": "Run 'uv run aria-esi cache-planets --around <home_system>' to populate cache",
        }

    # Find systems with required planet types
    required_p0 = product_info.get("required_p0", [])
    single_planet_options = product_info.get("single_planet_options", [])

    # Search cached systems
    matches = []

    for system_name, system_data in systems_data.items():
        planets = system_data.get("planets", [])
        planet_types_in_system = {p.get("type_name") for p in planets}

        # Check if this system has useful planets
        useful_types = planet_types_in_system & set(single_planet_options) if single_planet_options else set()

        # Also check for any planet types that have required P0
        planet_types_info = product_info.get("planet_types", {})
        partial_types = set()
        for _p0, types in planet_types_info.items():
            partial_types.update(set(types) & planet_types_in_system)

        if useful_types or partial_types:
            matches.append({
                "system_name": system_name,
                "system_id": system_data.get("system_id"),
                "single_planet_types": list(useful_types),
                "partial_types": list(partial_types),
                "planet_count": len(planets),
            })

    # Calculate distances from home systems
    target_systems = [m["system_name"] for m in matches]
    distances = _calculate_distances_from_home(target_systems, home_systems)

    # Add distances to matches and filter by max_jumps
    filtered_matches = []
    for match in matches:
        system_name = match["system_name"]
        distance = distances.get(system_name, -1)
        match["distance_jumps"] = distance

        # Mark home systems with 0 distance
        if system_name in home_systems:
            match["distance_jumps"] = 0
            match["is_home"] = True
        else:
            match["is_home"] = False

        # Filter by max_jumps (include unreachable systems with warning)
        if distance >= 0 and distance <= max_jumps:
            filtered_matches.append(match)
        elif distance == -1:
            # System not in universe graph (could be wormhole, unreachable, or graph issue)
            match["distance_jumps"] = None
            match["distance_note"] = "distance unknown"
            # Include if we have no distance data (fallback to old behavior)
            if not distances:
                filtered_matches.append(match)

    # Sort by: home systems first, then by distance, then by single-planet coverage
    filtered_matches.sort(
        key=lambda x: (
            not x.get("is_home", False),  # Home systems first
            x.get("distance_jumps") if x.get("distance_jumps") is not None else 9999,  # Then by distance
            -len(x.get("single_planet_types", [])),  # Then by single-planet coverage
            -len(x.get("partial_types", [])),  # Then by partial coverage
        )
    )

    return {
        "query_timestamp": query_ts,
        "product": product,
        "product_tier": product_info.get("product_tier"),
        "required_p0": required_p0,
        "single_planet_options": single_planet_options,
        "home_systems": home_systems,
        "max_jumps": max_jumps,
        "matches": filtered_matches[:20],  # Top 20 matches
        "total_matches": len(filtered_matches),
        "total_before_filter": len(matches),
        "systems_searched": len(systems_data),
    }


def cmd_pi_planets(args: argparse.Namespace) -> dict:
    """
    Show planet types in a specific system.
    """
    query_ts = get_utc_timestamp()
    system = getattr(args, "system", None)

    if not system:
        return {
            "query_timestamp": query_ts,
            "error": "missing_argument",
            "message": "System name required",
        }

    service = get_planet_cache_service()
    planets = service.get_system_planets(system)

    if planets is None:
        # Try to fetch from ESI
        esi = ESIClient()
        system_id = _resolve_system_id(system, esi)

        if not system_id:
            return {
                "query_timestamp": query_ts,
                "error": "system_not_found",
                "message": f"Could not resolve system: {system}",
            }

        planets = fetch_system_planets_sync(system_id, esi)
        if planets:
            service.add_system(system, system_id, planets)
            service.save_cache()

    if not planets:
        return {
            "query_timestamp": query_ts,
            "system": system,
            "planets": [],
            "message": "No planets found or system not accessible",
        }

    # Enrich with resource info
    enriched = []
    for planet in planets:
        planet_type = planet.get("type_name", "Unknown")
        resources = get_resources_for_planet_type(planet_type)

        enriched.append({
            "planet_id": planet.get("planet_id"),
            "type": planet_type,
            "p0_resources": resources,
        })

    return {
        "query_timestamp": query_ts,
        "system": system,
        "planet_count": len(enriched),
        "planets": enriched,
    }


# =============================================================================
# Helper Functions
# =============================================================================


def _calculate_distances_from_home(
    target_systems: list[str],
    home_systems: list[str],
) -> dict[str, int]:
    """
    Calculate shortest jump distance from home systems to target systems.

    Uses the universe graph for efficient O(1) routing lookups.

    Args:
        target_systems: Systems to calculate distance to
        home_systems: Home systems to measure from

    Returns:
        Dict mapping system name to minimum jumps from any home system.
        Systems that can't be reached have value -1.
    """
    try:
        from ..services.navigation.router import NavigationService
        from ..universe import load_universe_graph

        universe = load_universe_graph()
        nav = NavigationService(universe)
    except Exception as e:
        logger.warning(f"Could not load universe graph: {e}")
        return {}

    distances: dict[str, int] = {}

    # Resolve home system indices
    home_indices: list[int] = []
    for home in home_systems:
        idx = universe.resolve_name(home)
        if idx is not None:
            home_indices.append(idx)

    if not home_indices:
        logger.warning("No home systems could be resolved in universe graph")
        return {}

    # Calculate distance for each target
    for target in target_systems:
        target_idx = universe.resolve_name(target)
        if target_idx is None:
            distances[target] = -1
            continue

        # Find minimum distance from any home system
        min_distance = float("inf")
        for home_idx in home_indices:
            path = nav.calculate_route(home_idx, target_idx, mode="shortest")
            if path:
                # Path includes origin and destination, so jumps = len - 1
                jumps = len(path) - 1
                min_distance = min(min_distance, jumps)

        distances[target] = int(min_distance) if min_distance != float("inf") else -1

    return distances


def _resolve_system_id(system_name: str, esi: ESIClient) -> int | None:
    """Resolve system name to ID using ESI search."""
    # Try ESI search
    result = esi.get(f"/search/?categories=solar_system&search={system_name}&strict=true")
    if result and "solar_system" in result:
        system_ids = result["solar_system"]
        if system_ids:
            return system_ids[0]
    return None


def _resolve_region_id(region_name: str, esi: ESIClient) -> int | None:
    """Resolve region name to ID using ESI search."""
    result = esi.get(f"/search/?categories=region&search={region_name}&strict=true")
    if result and "region" in result:
        region_ids = result["region"]
        if region_ids:
            return region_ids[0]
    return None


def _get_systems_in_region(region_id: int, esi: ESIClient) -> list[dict[str, Any]]:
    """Get all systems in a region."""
    region_info = esi.get(f"/universe/regions/{region_id}/")
    if not region_info:
        return []

    constellation_ids = region_info.get("constellations", [])
    systems = []

    for const_id in constellation_ids:
        const_info = esi.get(f"/universe/constellations/{const_id}/")
        if not const_info:
            continue

        for system_id in const_info.get("systems", []):
            system_info = esi.get(f"/universe/systems/{system_id}/")
            if system_info and "name" in system_info:
                systems.append({
                    "name": system_info["name"],
                    "id": system_id,
                })

    return systems


def _get_systems_within_jumps(
    center_id: int,
    max_jumps: int,
    esi: ESIClient,
) -> list[dict[str, Any]]:
    """
    Get systems within N jumps of center.

    Simple BFS implementation.
    """
    visited = {center_id}
    current_layer = [center_id]
    systems = []

    # Get center system name
    center_info = esi.get(f"/universe/systems/{center_id}/")
    if center_info and "name" in center_info:
        systems.append({"name": center_info["name"], "id": center_id})

    for _ in range(max_jumps):
        next_layer = []

        for system_id in current_layer:
            system_info = esi.get(f"/universe/systems/{system_id}/")
            if not system_info:
                continue

            # Get stargates and follow them
            stargates = system_info.get("stargates", [])
            for gate_id in stargates:
                gate_info = esi.get(f"/universe/stargates/{gate_id}/")
                if not gate_info:
                    continue

                dest_id = gate_info.get("destination", {}).get("system_id")
                if dest_id and dest_id not in visited:
                    visited.add(dest_id)
                    next_layer.append(dest_id)

                    # Get destination system name
                    dest_info = esi.get(f"/universe/systems/{dest_id}/")
                    if dest_info and "name" in dest_info:
                        systems.append({"name": dest_info["name"], "id": dest_id})

        current_layer = next_layer

        if not current_layer:
            break

    return systems


def _load_home_systems() -> list[str]:
    """Load home systems from config.json."""
    config_path = Path("userdata/config.json")
    if not config_path.exists():
        return []

    try:
        with open(config_path) as f:
            config = json.load(f)

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
# Argument Parser Registration
# =============================================================================


def register_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Register PI command parsers."""

    # cache-planets command
    cache_parser = subparsers.add_parser(
        "cache-planets",
        help="Build/refresh planet type cache for PI planning",
    )
    cache_parser.add_argument(
        "--systems",
        nargs="+",
        metavar="SYSTEM",
        help="Specific system names to cache",
    )
    cache_parser.add_argument(
        "--region",
        metavar="NAME",
        help="Cache all systems in a region",
    )
    cache_parser.add_argument(
        "--around",
        metavar="SYSTEM",
        help="Cache systems within N jumps of a system",
    )
    cache_parser.add_argument(
        "--jumps",
        type=int,
        default=10,
        help="Number of jumps for --around (default: 10)",
    )
    cache_parser.add_argument(
        "--force",
        action="store_true",
        help="Re-fetch already cached systems",
    )
    cache_parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear all cached data",
    )
    cache_parser.set_defaults(func=cmd_cache_planets)

    # pi-near command
    near_parser = subparsers.add_parser(
        "pi-near",
        help="Find planets near home systems for PI production",
    )
    near_parser.add_argument(
        "product",
        help="PI product name (P1, P2, P3, or P4)",
    )
    near_parser.add_argument(
        "--jumps",
        type=int,
        default=10,
        help="Maximum jumps from home (default: 10)",
    )
    near_parser.set_defaults(func=cmd_pi_near)

    # pi-planets command
    planets_parser = subparsers.add_parser(
        "pi-planets",
        help="Show planet types in a system",
    )
    planets_parser.add_argument(
        "system",
        help="System name to check",
    )
    planets_parser.set_defaults(func=cmd_pi_planets)
