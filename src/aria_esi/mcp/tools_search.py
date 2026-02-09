"""
Search Tool Implementation for MCP Universe Server.

Provides the universe_search tool for filtering systems by various criteria
including security range, region, border status, and distance from a reference point.

STP-008: Search Tool (universe_search)
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, Any

from .context_policy import UNIVERSE
from .errors import InvalidParameterError
from .models import SystemSearchResult
from .tools import collect_corrections, get_universe, resolve_system_name

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from ..universe.graph import UniverseGraph


# Parameter limits - imported from context_policy for centralized management
MAX_LIMIT = UNIVERSE.SEARCH_MAX_LIMIT
MAX_JUMPS = UNIVERSE.SEARCH_MAX_JUMPS


def register_search_tools(server: FastMCP, universe: UniverseGraph) -> None:
    """
    Register system search tools with MCP server.

    Args:
        server: MCP Server instance
        universe: UniverseGraph for search operations
    """

    @server.tool()
    async def universe_search(
        origin: str | None = None,
        max_jumps: int | None = None,
        security_min: float | None = None,
        security_max: float | None = None,
        region: str | None = None,
        is_border: bool | None = None,
        limit: int = 20,
    ) -> dict:
        """
        Search for systems matching criteria.

        PREFER THIS TOOL over writing custom filtering scripts. Combines
        multiple filter criteria efficiently using pre-built indices for
        regions, borders, and distance calculations.

        Args:
            origin: Center point for distance filter (required if max_jumps set)
            max_jumps: Maximum distance from origin
            security_min: Minimum security status (inclusive)
            security_max: Maximum security status (inclusive)
            region: Filter to specific region name (case-insensitive)
            is_border: Filter to border systems only
            limit: Maximum results (default: 20, max: 100)

        Returns:
            Dictionary containing:
            - systems: List of matching SystemSearchResult objects
            - total_found: Number of systems found
            - filters_applied: Summary of filters used

        Examples:
            # Find low-sec systems within 10 jumps of Dodixie
            universe_search(
                origin="Dodixie",
                max_jumps=10,
                security_min=0.1,
                security_max=0.4
            )

            # Find all border systems in The Forge
            universe_search(region="The Forge", is_border=True)
        """
        universe = get_universe()

        # Validate parameters
        if limit < 1 or limit > MAX_LIMIT:
            raise InvalidParameterError("limit", limit, f"Must be between 1 and {MAX_LIMIT}")

        if max_jumps is not None and origin is None:
            raise InvalidParameterError(
                "origin", None, "origin is required when max_jumps is specified"
            )

        if max_jumps is not None and (max_jumps < 1 or max_jumps > MAX_JUMPS):
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

        # Resolve origin if provided (with auto-correction)
        origin_idx: int | None = None
        origin_canonical: str | None = None
        corrections: dict[str, str] = {}
        if origin:
            origin_resolved = resolve_system_name(origin)
            origin_idx = origin_resolved.idx
            origin_canonical = origin_resolved.canonical_name
            corrections = collect_corrections(origin_resolved)

        # Resolve region if provided
        # Track whether region was requested vs not found
        region_id = None
        region_not_found = False
        if region:
            region_id = _resolve_region(universe, region)
            if region_id is None:
                region_not_found = True

        # If region was explicitly requested but not found, return empty results with warning
        if region_not_found:
            return {
                "systems": [],
                "total_found": 0,
                "filters_applied": _summarize_filters(
                    origin_canonical or origin,
                    max_jumps,
                    security_min,
                    security_max,
                    region,
                    is_border,
                ),
                "warning": f"Unknown region: '{region}'",
                "corrections": corrections,
            }

        # Execute search
        results = _search_systems(
            universe=universe,
            origin_idx=origin_idx,
            max_jumps=max_jumps,
            security_min=security_min,
            security_max=security_max,
            region_id=region_id,
            is_border=is_border,
            limit=limit,
        )

        return {
            "systems": [r.model_dump() for r in results],
            "total_found": len(results),
            "filters_applied": _summarize_filters(
                origin_canonical or origin, max_jumps, security_min, security_max, region, is_border
            ),
            "corrections": corrections,
        }


def _resolve_region(universe: UniverseGraph, region_name: str) -> int | None:
    """
    Resolve region name to ID (case-insensitive, O(1)).

    Args:
        universe: UniverseGraph for region lookups
        region_name: Region name to resolve

    Returns:
        Region ID if found, None otherwise (returns empty results)
    """
    return universe.resolve_region(region_name)


def _search_systems(
    universe: UniverseGraph,
    origin_idx: int | None,
    max_jumps: int | None,
    security_min: float | None,
    security_max: float | None,
    region_id: int | None,
    is_border: bool | None,
    limit: int,
) -> list[SystemSearchResult]:
    """
    Execute system search with filters.

    Strategy:
    - If origin + max_jumps: BFS within range, then filter
    - If region: Iterate region systems, then filter
    - If is_border: Use border index
    - Otherwise: Full scan with filters (less efficient)

    Args:
        universe: UniverseGraph for lookups
        origin_idx: Starting vertex index for distance filter
        max_jumps: Maximum distance from origin
        security_min: Minimum security status (inclusive)
        security_max: Maximum security status (inclusive)
        region_id: Region ID to filter by
        is_border: Filter to border systems only
        limit: Maximum results

    Returns:
        List of SystemSearchResult objects
    """
    results: list[SystemSearchResult] = []
    distances: dict[int, int] = {}

    # Determine candidate set based on most restrictive filter
    if origin_idx is not None and max_jumps is not None:
        # BFS to find systems within range
        candidates, distances = _bfs_within_range(universe, origin_idx, max_jumps)
    elif region_id is not None:
        # Use region index
        candidates = set(universe.region_systems.get(region_id, []))
    elif is_border is True:
        # Use border index
        candidates = set(universe.border_systems)
    else:
        # Full scan
        candidates = set(range(universe.system_count))

    # Apply filters to candidates
    for idx in candidates:
        if len(results) >= limit:
            break

        # Security filter
        sec = universe.security[idx]
        if security_min is not None and sec < security_min:
            continue
        if security_max is not None and sec > security_max:
            continue

        # Region filter (if not already applied as candidate set)
        if region_id is not None and origin_idx is not None:
            if int(universe.region_ids[idx]) != region_id:
                continue

        # Border filter (if not already applied as candidate set)
        if is_border is True and idx not in universe.border_systems:
            continue
        if is_border is False and idx in universe.border_systems:
            continue

        results.append(_build_search_result(universe, idx, distances.get(idx)))

    return results


def _bfs_within_range(
    universe: UniverseGraph,
    origin_idx: int,
    max_jumps: int,
) -> tuple[set[int], dict[int, int]]:
    """
    BFS to find all systems within max_jumps.

    Args:
        universe: UniverseGraph for traversal
        origin_idx: Starting vertex index
        max_jumps: Maximum distance from origin

    Returns:
        Tuple of (set of vertex indices, dict of distances)
    """
    g = universe.graph
    visited: dict[int, int] = {origin_idx: 0}
    queue: deque[tuple[int, int]] = deque([(origin_idx, 0)])

    while queue:
        vertex, dist = queue.popleft()
        if dist >= max_jumps:
            continue

        for neighbor in g.neighbors(vertex):
            if neighbor not in visited:
                visited[neighbor] = dist + 1
                queue.append((neighbor, dist + 1))

    return set(visited.keys()), visited


def _build_search_result(
    universe: UniverseGraph,
    idx: int,
    jumps_from_origin: int | None,
) -> SystemSearchResult:
    """
    Build search result for a vertex.

    Args:
        universe: UniverseGraph for lookups
        idx: Vertex index
        jumps_from_origin: Distance from origin (if applicable)

    Returns:
        SystemSearchResult with all fields populated
    """
    return SystemSearchResult(
        name=universe.idx_to_name[idx],
        system_id=int(universe.system_ids[idx]),
        security=float(universe.security[idx]),
        security_class=universe.security_class(idx),
        region=universe.get_region_name(idx),
        jumps_from_origin=jumps_from_origin,
    )


def _summarize_filters(
    origin: str | None,
    max_jumps: int | None,
    security_min: float | None,
    security_max: float | None,
    region: str | None,
    is_border: bool | None,
) -> dict[str, Any]:
    """
    Summarize applied filters for response.

    Args:
        origin: Origin system name
        max_jumps: Maximum jumps from origin
        security_min: Minimum security status
        security_max: Maximum security status
        region: Region name filter
        is_border: Border filter

    Returns:
        Dictionary of applied filters
    """
    filters: dict[str, Any] = {}
    if origin:
        filters["origin"] = origin
    if max_jumps is not None:
        filters["max_jumps"] = max_jumps
    if security_min is not None:
        filters["security_min"] = security_min
    if security_max is not None:
        filters["security_max"] = security_max
    if region:
        filters["region"] = region
    if is_border is not None:
        filters["is_border"] = is_border
    return filters
