"""
Universe Cache Module

Provides fast local queries against cached ESI universe data.
"""

import json
from pathlib import Path
from typing import Any, Optional

# Default cache location
CACHE_PATH = Path(__file__).parent.parent / "data" / "universe_cache.json"

# Module-level cache storage (loaded once)
_cache: Optional[dict[str, Any]] = None


def load_cache(path: Optional[Path] = None) -> dict[str, Any]:
    """
    Load universe cache from disk.

    Caches in memory after first load for fast repeated access.

    Args:
        path: Path to cache file (default: data/universe_cache.json)

    Returns:
        Cache dict with regions, constellations, systems, stargates

    Raises:
        FileNotFoundError: If cache doesn't exist (run builder first)
    """
    global _cache

    if _cache is not None:
        return _cache

    cache_path = path or CACHE_PATH
    if not cache_path.exists():
        raise FileNotFoundError(
            f"Universe cache not found at {cache_path}. "
            "Run 'python -m aria_esi.cache.builder' to generate it."
        )

    with open(cache_path) as f:
        _cache = json.load(f)

    return _cache


def is_cache_available(path: Optional[Path] = None) -> bool:
    """Check if cache file exists."""
    cache_path = path or CACHE_PATH
    return cache_path.exists()


def get_cache_info(path: Optional[Path] = None) -> dict[str, Any]:
    """Get cache metadata without loading full cache."""
    cache_path = path or CACHE_PATH
    if not cache_path.exists():
        return {"available": False, "path": str(cache_path)}

    # Load just to get metadata
    cache = load_cache(cache_path)
    return {
        "available": True,
        "path": str(cache_path),
        "generated": cache.get("generated"),
        "counts": {
            "regions": len(cache.get("regions", {})),
            "constellations": len(cache.get("constellations", {})),
            "systems": len(cache.get("systems", {})),
            "stargates": len(cache.get("stargates", {})),
        },
    }


def clear_cache() -> None:
    """Clear in-memory cache (forces reload on next access)."""
    global _cache
    _cache = None


# =============================================================================
# Query Functions
# =============================================================================


def get_system(system_id: int) -> Optional[dict[str, Any]]:
    """
    Get system data by ID.

    Returns:
        Dict with name, security, constellation_id, stargates
    """
    cache = load_cache()
    return cache["systems"].get(str(system_id))


def get_system_by_name(name: str) -> Optional[tuple[int, dict[str, Any]]]:
    """
    Find system by name (case-insensitive).

    Returns:
        Tuple of (system_id, system_data) or None
    """
    cache = load_cache()
    name_lower = name.lower()
    for sys_id, data in cache["systems"].items():
        if data["name"].lower() == name_lower:
            return int(sys_id), data
    return None


def get_constellation(const_id: int) -> Optional[dict[str, Any]]:
    """Get constellation data by ID."""
    cache = load_cache()
    return cache["constellations"].get(str(const_id))


def get_region(region_id: int) -> Optional[dict[str, Any]]:
    """Get region data by ID."""
    cache = load_cache()
    return cache["regions"].get(str(region_id))


def get_region_by_name(name: str) -> Optional[tuple[int, dict[str, Any]]]:
    """
    Find region by name (case-insensitive).

    Returns:
        Tuple of (region_id, region_data) or None
    """
    cache = load_cache()
    name_lower = name.lower()
    for region_id, data in cache["regions"].items():
        if data["name"].lower() == name_lower:
            return int(region_id), data
    return None


def get_stargate_destination(gate_id: int) -> Optional[int]:
    """Get destination system ID for a stargate."""
    cache = load_cache()
    gate = cache["stargates"].get(str(gate_id))
    return gate["destination_system_id"] if gate else None


def get_system_neighbors(system_id: int) -> list[tuple[int, dict[str, Any]]]:
    """
    Get all systems connected to a system via stargates.

    Returns:
        List of (system_id, system_data) tuples
    """
    cache = load_cache()
    system = cache["systems"].get(str(system_id))
    if not system:
        return []

    neighbors = []
    for gate_id in system.get("stargates", []):
        dest_id = get_stargate_destination(gate_id)
        if dest_id:
            dest_data = get_system(dest_id)
            if dest_data:
                neighbors.append((dest_id, dest_data))

    return neighbors


def get_system_full_info(system_id: int) -> Optional[dict[str, Any]]:
    """
    Get system with constellation and region names resolved.

    Returns:
        Dict with name, security, constellation, region
    """
    system = get_system(system_id)
    if not system:
        return None

    const = get_constellation(system["constellation_id"])
    region = get_region(const["region_id"]) if const else None

    return {
        "system_id": system_id,
        "name": system["name"],
        "security": round(system["security"], 2),
        "constellation": const["name"] if const else "Unknown",
        "region": region["name"] if region else "Unknown",
    }


# =============================================================================
# Border System Queries
# =============================================================================


def find_border_systems_in_region(region_name: str) -> list[dict[str, Any]]:
    """
    Find all high-sec systems bordering low-sec in a region.

    Args:
        region_name: Region name (case-insensitive)

    Returns:
        List of dicts with system info and bordering low-sec systems
    """
    cache = load_cache()

    # Find region
    region_match = get_region_by_name(region_name)
    if not region_match:
        return []
    region_id = region_match[0]

    # Get all constellations in region
    region_const_ids = set()
    for const_id, const in cache["constellations"].items():
        if const.get("region_id") == region_id:
            region_const_ids.add(int(const_id))

    # Find high-sec systems bordering low-sec
    border_systems = []

    for sys_id, system in cache["systems"].items():
        sys_id_int = int(sys_id)
        const_id = system.get("constellation_id")

        # Skip if not in target region
        if const_id not in region_const_ids:
            continue

        sec = system.get("security", 0)
        # Skip if not high-sec (>= 0.45 rounds to 0.5)
        if sec < 0.45:
            continue

        # Check neighbors for low-sec
        lowsec_neighbors = []
        for neighbor_id, neighbor in get_system_neighbors(sys_id_int):
            neighbor_sec = neighbor.get("security", 0)
            if 0 < neighbor_sec < 0.45:
                lowsec_neighbors.append(
                    {
                        "system_id": neighbor_id,
                        "name": neighbor["name"],
                        "security": round(neighbor_sec, 2),
                    }
                )

        if lowsec_neighbors:
            border_systems.append(
                {
                    "system_id": sys_id_int,
                    "name": system["name"],
                    "security": round(sec, 2),
                    "borders_lowsec": lowsec_neighbors,
                }
            )

    return sorted(border_systems, key=lambda x: x["name"])


def find_nearest_border_systems(origin_name: str, limit: int = 10) -> list[dict[str, Any]]:
    """
    Find border systems nearest to origin, across all regions.

    Note: Uses BFS for approximate distance (jump count).
    For exact routing, use ESI route endpoint.

    Args:
        origin_name: Starting system name
        limit: Max results to return

    Returns:
        List of border systems with approximate jump distance
    """
    origin_match = get_system_by_name(origin_name)
    if not origin_match:
        return []

    origin_id = origin_match[0]
    cache = load_cache()

    # BFS to find distances
    visited: dict[int, int] = {origin_id: 0}
    queue = [origin_id]
    border_systems = []

    while queue and len(border_systems) < limit * 2:
        current_id = queue.pop(0)
        current_dist = visited[current_id]

        system = cache["systems"].get(str(current_id))
        if not system:
            continue

        sec = system.get("security", 0)

        # Check if this is a border system
        if sec >= 0.45:
            lowsec_neighbors = []
            for _neighbor_id, neighbor in get_system_neighbors(current_id):
                neighbor_sec = neighbor.get("security", 0)
                if 0 < neighbor_sec < 0.45:
                    lowsec_neighbors.append(neighbor["name"])

            if lowsec_neighbors:
                border_systems.append(
                    {
                        "system_id": current_id,
                        "name": system["name"],
                        "security": round(sec, 2),
                        "approx_jumps": current_dist,
                        "borders": lowsec_neighbors[:3],
                    }
                )

        # Add neighbors to queue
        for neighbor_id, _ in get_system_neighbors(current_id):
            if neighbor_id not in visited:
                visited[neighbor_id] = current_dist + 1
                queue.append(neighbor_id)

    # Sort by distance and return top results
    border_systems.sort(key=lambda x: x["approx_jumps"])
    return border_systems[:limit]


__all__ = [
    "CACHE_PATH",
    "load_cache",
    "is_cache_available",
    "get_cache_info",
    "clear_cache",
    "get_system",
    "get_system_by_name",
    "get_constellation",
    "get_region",
    "get_region_by_name",
    "get_stargate_destination",
    "get_system_neighbors",
    "get_system_full_info",
    "find_border_systems_in_region",
    "find_nearest_border_systems",
]
