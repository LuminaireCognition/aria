"""
Nearest Tool Implementation for MCP Universe Server.

Provides the universe_nearest tool for finding the closest systems matching
flexible predicate criteria. Uses BFS for efficient distance-ordered search.

STP-011: Nearest Tool (universe_nearest)
STP-014: Activity-aware predicates for local intel
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from typing import TYPE_CHECKING

from .activity import ActivityData, classify_activity, get_activity_cache
from .context_policy import UNIVERSE
from .errors import InvalidParameterError
from .models import SystemSearchResult
from .tools import collect_corrections, get_universe, resolve_system_name

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from ..universe.graph import UniverseGraph


# Parameter limits - imported from context_policy for centralized management
MAX_LIMIT = UNIVERSE.NEAREST_MAX_LIMIT
MAX_JUMPS = UNIVERSE.NEAREST_MAX_JUMPS


def register_nearest_tools(server: FastMCP, universe: UniverseGraph) -> None:
    """
    Register nearest system tools with MCP server.

    Args:
        server: MCP Server instance
        universe: UniverseGraph for nearest lookups
    """

    @server.tool()
    async def universe_nearest(
        origin: str,
        is_border: bool | None = None,
        min_adjacent_lowsec: int | None = None,
        security_min: float | None = None,
        security_max: float | None = None,
        region: str | None = None,
        max_kills: int | None = None,
        min_npc_kills: int | None = None,
        activity_level: str | None = None,
        limit: int = 5,
        max_jumps: int = 30,
    ) -> dict:
        """
        Find nearest systems matching predicate criteria.

        PREFER THIS TOOL over writing custom BFS scripts to find nearby systems
        matching specific criteria. Uses distance-ordered search for efficiency.

        Args:
            origin: Starting system for distance calculation (case-insensitive)
            is_border: If True, only match border systems (high-sec adjacent to low-sec)
            min_adjacent_lowsec: Minimum number of adjacent low-sec systems required
            security_min: Minimum security status (inclusive)
            security_max: Maximum security status (inclusive)
            region: Filter to specific region (case-insensitive)
            max_kills: Maximum PvP kills (ship + pod) in last hour - for finding quiet systems
            min_npc_kills: Minimum NPC kills in last hour - for finding ratting activity
            activity_level: Filter by activity level: "none", "low", "medium", "high", "extreme"
            limit: Maximum systems to return (default: 5, max: 50)
            max_jumps: Maximum search radius (default: 30, max: 50)

        Returns:
            Dictionary containing:
            - origin: The origin system name
            - systems: List of matching systems sorted by distance
            - total_found: Number of systems found
            - search_radius: The max_jumps value used
            - predicates: Summary of predicates applied

        Predicate Examples:
            # Find nearest border systems with at least 2 low-sec gates
            universe_nearest("Jita", is_border=True, min_adjacent_lowsec=2)

            # Find nearest low-sec systems
            universe_nearest("Dodixie", security_min=0.1, security_max=0.4)

            # Find nearest systems in a specific region
            universe_nearest("Amarr", region="Domain", limit=10)

            # Find nearest border systems in Genesis
            universe_nearest("Yulai", is_border=True, region="Genesis")

            # Find nearest quiet systems (0 PvP kills) for stealth ops
            universe_nearest("ZZ-TOP", max_kills=0, security_max=0.0)

            # Find nearest ratting pockets (high NPC kills)
            universe_nearest("ZZ-TOP", min_npc_kills=100, security_max=0.0)

            # Find nearest high-activity systems
            universe_nearest("Tama", activity_level="high", security_max=0.4)
        """
        # Validate parameters
        if limit < 1 or limit > MAX_LIMIT:
            raise InvalidParameterError("limit", limit, f"Must be between 1 and {MAX_LIMIT}")
        if max_jumps < 1 or max_jumps > MAX_JUMPS:
            raise InvalidParameterError(
                "max_jumps", max_jumps, f"Must be between 1 and {MAX_JUMPS}"
            )
        if security_min is not None and (security_min < -1.0 or security_min > 1.0):
            raise InvalidParameterError(
                "security_min", security_min, "Must be between -1.0 and 1.0"
            )
        if security_max is not None and (security_max < -1.0 or security_max > 1.0):
            raise InvalidParameterError(
                "security_max", security_max, "Must be between -1.0 and 1.0"
            )
        if min_adjacent_lowsec is not None and min_adjacent_lowsec < 1:
            raise InvalidParameterError(
                "min_adjacent_lowsec", min_adjacent_lowsec, "Must be at least 1"
            )
        if max_kills is not None and max_kills < 0:
            raise InvalidParameterError("max_kills", max_kills, "Must be >= 0")
        if min_npc_kills is not None and min_npc_kills < 0:
            raise InvalidParameterError("min_npc_kills", min_npc_kills, "Must be >= 0")
        valid_activity_levels = {"none", "low", "medium", "high", "extreme"}
        if activity_level is not None and activity_level not in valid_activity_levels:
            raise InvalidParameterError(
                "activity_level",
                activity_level,
                f"Must be one of: {', '.join(sorted(valid_activity_levels))}",
            )

        # Determine if we need activity data (only fetch if activity predicates are used)
        needs_activity = (
            max_kills is not None or min_npc_kills is not None or activity_level is not None
        )
        activity_data: dict[int, ActivityData] | None = None
        cache_age: int | None = None

        if needs_activity:
            cache = get_activity_cache()
            activity_data = await cache.get_all_activity()
            cache_age = cache.get_kills_cache_age()

        universe = get_universe()
        origin_resolved = resolve_system_name(origin)
        corrections = collect_corrections(origin_resolved)

        # Resolve region if provided
        region_id = None
        if region:
            region_id = universe.resolve_region(region)
            if region_id is None:
                # Unknown region - return empty results with warning
                return {
                    "origin": origin_resolved.canonical_name,
                    "systems": [],
                    "total_found": 0,
                    "search_radius": max_jumps,
                    "predicates": _summarize_predicates(
                        is_border, min_adjacent_lowsec, security_min, security_max, region
                    ),
                    "warning": f"Unknown region: '{region}'",
                    "corrections": corrections,
                }

        # Build predicate function
        predicate = _build_predicate(
            universe=universe,
            is_border=is_border,
            min_adjacent_lowsec=min_adjacent_lowsec,
            security_min=security_min,
            security_max=security_max,
            region_id=region_id,
            max_kills=max_kills,
            min_npc_kills=min_npc_kills,
            activity_level=activity_level,
            activity_data=activity_data,
        )

        # Find nearest matching systems
        results = _find_nearest(
            universe=universe,
            origin_idx=origin_resolved.idx,
            predicate=predicate,
            limit=limit,
            max_jumps=max_jumps,
        )

        response = {
            "origin": origin_resolved.canonical_name,
            "systems": [r.model_dump() for r in results],
            "total_found": len(results),
            "search_radius": max_jumps,
            "predicates": _summarize_predicates(
                is_border=is_border,
                min_adjacent_lowsec=min_adjacent_lowsec,
                security_min=security_min,
                security_max=security_max,
                region=region,
                max_kills=max_kills,
                min_npc_kills=min_npc_kills,
                activity_level=activity_level,
            ),
            "corrections": corrections,
        }

        # Include cache age if activity data was used
        if cache_age is not None:
            response["activity_cache_age_seconds"] = cache_age

        return response


def _build_predicate(
    universe: UniverseGraph,
    is_border: bool | None,
    min_adjacent_lowsec: int | None,
    security_min: float | None,
    security_max: float | None,
    region_id: int | None,
    max_kills: int | None = None,
    min_npc_kills: int | None = None,
    activity_level: str | None = None,
    activity_data: dict[int, ActivityData] | None = None,
) -> Callable[[int], bool]:
    """
    Build a predicate function from filter parameters.

    Returns a function that takes a vertex index and returns True if it matches.

    Args:
        universe: UniverseGraph for system lookups
        is_border: Filter to border systems only
        min_adjacent_lowsec: Minimum adjacent low-sec gates
        security_min: Minimum security status
        security_max: Maximum security status
        region_id: Filter to specific region
        max_kills: Maximum PvP kills (ship + pod) - for finding quiet systems
        min_npc_kills: Minimum NPC kills - for finding ratting activity
        activity_level: Required activity level (none/low/medium/high/extreme)
        activity_data: Pre-fetched activity data (required if activity filters used)
    """

    def predicate(idx: int) -> bool:
        # Border filter
        if is_border is True and idx not in universe.border_systems:
            return False
        if is_border is False and idx in universe.border_systems:
            return False

        # Adjacent low-sec count filter
        if min_adjacent_lowsec is not None:
            lowsec_neighbors = sum(
                1 for n in universe.graph.neighbors(idx) if universe.security[n] < 0.45
            )
            if lowsec_neighbors < min_adjacent_lowsec:
                return False

        # Security range filter
        sec = universe.security[idx]
        if security_min is not None and sec < security_min:
            return False
        if security_max is not None and sec > security_max:
            return False

        # Region filter
        if region_id is not None and int(universe.region_ids[idx]) != region_id:
            return False

        # Activity filters (require activity_data to be pre-fetched)
        if max_kills is not None or min_npc_kills is not None or activity_level is not None:
            system_id = int(universe.system_ids[idx])
            activity = activity_data.get(system_id) if activity_data else None

            # Get kill counts (default to 0 if no data)
            pvp_kills = 0
            npc_kills = 0
            if activity:
                pvp_kills = activity.ship_kills + activity.pod_kills
                npc_kills = activity.npc_kills

            # Max kills filter (for finding quiet systems)
            if max_kills is not None and pvp_kills > max_kills:
                return False

            # Min NPC kills filter (for finding ratting pockets)
            if min_npc_kills is not None and npc_kills < min_npc_kills:
                return False

            # Activity level filter
            if activity_level is not None:
                current_level = classify_activity(pvp_kills, "kills")
                if current_level != activity_level:
                    return False

        return True

    return predicate


def _find_nearest(
    universe: UniverseGraph,
    origin_idx: int,
    predicate: Callable[[int], bool],
    limit: int,
    max_jumps: int,
) -> list[SystemSearchResult]:
    """
    Find nearest systems matching predicate using BFS.

    BFS guarantees distance-ordered results, so we can stop as soon
    as we have enough matches.

    Args:
        universe: UniverseGraph for traversal
        origin_idx: Starting vertex index
        predicate: Function that returns True for matching systems
        limit: Maximum results to return
        max_jumps: Maximum search radius

    Returns:
        List of SystemSearchResult sorted by distance
    """
    g = universe.graph
    results: list[SystemSearchResult] = []

    # BFS with distance tracking
    visited: set[int] = {origin_idx}
    queue: deque[tuple[int, int]] = deque([(origin_idx, 0)])

    while queue and len(results) < limit:
        vertex, dist = queue.popleft()

        # Stop if beyond max_jumps
        if dist > max_jumps:
            continue

        # Check if this system matches predicate (skip origin)
        if dist > 0 and predicate(vertex):
            results.append(_build_result(universe, vertex, dist))
            if len(results) >= limit:
                break

        # Expand to neighbors
        for neighbor in g.neighbors(vertex):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, dist + 1))

    return results


def _build_result(
    universe: UniverseGraph,
    idx: int,
    jumps_from_origin: int,
) -> SystemSearchResult:
    """Build search result for a vertex."""
    return SystemSearchResult(
        name=universe.idx_to_name[idx],
        system_id=int(universe.system_ids[idx]),
        security=float(universe.security[idx]),
        security_class=universe.security_class(idx),
        region=universe.get_region_name(idx),
        jumps_from_origin=jumps_from_origin,
    )


def _summarize_predicates(
    is_border: bool | None,
    min_adjacent_lowsec: int | None,
    security_min: float | None,
    security_max: float | None,
    region: str | None,
    max_kills: int | None = None,
    min_npc_kills: int | None = None,
    activity_level: str | None = None,
) -> dict[str, bool | int | float | str]:
    """Summarize applied predicates for response."""
    predicates: dict[str, bool | int | float | str] = {}
    if is_border is not None:
        predicates["is_border"] = is_border
    if min_adjacent_lowsec is not None:
        predicates["min_adjacent_lowsec"] = min_adjacent_lowsec
    if security_min is not None:
        predicates["security_min"] = security_min
    if security_max is not None:
        predicates["security_max"] = security_max
    if region is not None:
        predicates["region"] = region
    if max_kills is not None:
        predicates["max_kills"] = max_kills
    if min_npc_kills is not None:
        predicates["min_npc_kills"] = min_npc_kills
    if activity_level is not None:
        predicates["activity_level"] = activity_level
    return predicates
