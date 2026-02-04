"""
Waypoint Optimization Tool Implementation for MCP Universe Server.

Provides the universe_optimize_waypoints tool for solving the Traveling
Salesman Problem (TSP) on arbitrary waypoints. Useful for PI collection,
asset consolidation, and multi-stop trade routes.

STP-012: Waypoint Optimization Tool (universe_optimize_waypoints)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .context_policy import UNIVERSE
from .errors import InvalidParameterError
from .models import VALID_SECURITY_FILTERS, OptimizedWaypointResult, WaypointInfo
from .tools import collect_corrections, get_universe, resolve_system_name
from .utils import DistanceMatrix, build_system_info

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from ..universe.graph import UniverseGraph


# =============================================================================
# Waypoint Optimization Constants - imported from context_policy
# =============================================================================

MIN_WAYPOINTS = UNIVERSE.WAYPOINTS_MIN_COUNT
MAX_WAYPOINTS = UNIVERSE.WAYPOINTS_MAX_COUNT


def register_waypoints_tools(server: FastMCP, universe: UniverseGraph) -> None:
    """
    Register waypoint optimization tools with MCP server.

    Args:
        server: MCP Server instance
        universe: UniverseGraph for route calculations
    """

    @server.tool()
    async def universe_optimize_waypoints(
        waypoints: list[str],
        origin: str | None = None,
        return_to_origin: bool = True,
        security_filter: str = "any",
        avoid_systems: list[str] | None = None,
    ) -> dict:
        """
        Optimize visit order for multiple waypoints (TSP approximation).

        PREFER THIS TOOL over writing custom TSP scripts. Handles:
        - Distance matrix precomputation for O(1) lookups
        - Nearest-neighbor TSP heuristic for fast approximation
        - Security-constrained routing
        - System avoidance for known danger zones
        - Optional origin/return handling

        Useful for: PI collection routes, asset consolidation, trade runs,
        multi-stop hauling, and any scenario requiring efficient multi-point
        navigation.

        Args:
            waypoints: List of system names to visit (2-50 systems)
            origin: Optional starting system. If not specified, optimization
                    finds the best starting point among waypoints.
            return_to_origin: If True and origin specified, route returns to
                              origin after visiting all waypoints (default: True)
            security_filter: Security constraint for route traversal:
                - "any": No security restrictions (default, shortest paths)
                - "highsec": Only traverse high-sec (>= 0.45)
                - "lowsec": Allow low-sec, avoid null-sec
            avoid_systems: List of system names to avoid in routing

        Returns:
            OptimizedWaypointResult with:
            - waypoints: Waypoints in optimized visit order
            - total_jumps: Total route length
            - route_systems: Full route with all intermediate systems
            - is_loop: Whether route returns to origin
            - unresolved_waypoints: Names that couldn't be found

        Examples:
            # Simple waypoint optimization (finds best order)
            universe_optimize_waypoints(["Jita", "Amarr", "Dodixie", "Rens"])

            # With fixed starting point, returning home
            universe_optimize_waypoints(
                waypoints=["Station1", "Station2", "Station3"],
                origin="HomeBase",
                return_to_origin=True
            )

            # One-way route from origin (no return)
            universe_optimize_waypoints(
                waypoints=["Dest1", "Dest2", "Dest3"],
                origin="StartPoint",
                return_to_origin=False
            )

            # Safe route avoiding dangerous systems
            universe_optimize_waypoints(
                waypoints=["Jita", "Dodixie", "Hek"],
                security_filter="highsec",
                avoid_systems=["Uedama", "Niarja"]
            )
        """
        universe = get_universe()

        # Validate parameters
        if len(waypoints) < MIN_WAYPOINTS:
            raise InvalidParameterError(
                "waypoints",
                len(waypoints),
                f"At least {MIN_WAYPOINTS} waypoints required for optimization",
            )
        if len(waypoints) > MAX_WAYPOINTS:
            raise InvalidParameterError(
                "waypoints",
                len(waypoints),
                f"Maximum {MAX_WAYPOINTS} waypoints allowed",
            )
        if security_filter not in VALID_SECURITY_FILTERS:
            raise InvalidParameterError(
                "security_filter",
                security_filter,
                f"Must be one of: {', '.join(sorted(VALID_SECURITY_FILTERS))}",
            )

        # Resolve origin if specified (with auto-correction)
        origin_idx: int | None = None
        origin_name: str | None = None
        corrections: dict[str, str] = {}
        if origin:
            origin_resolved = resolve_system_name(origin)
            origin_idx = origin_resolved.idx
            origin_name = origin_resolved.canonical_name
            corrections = collect_corrections(origin_resolved)

        # Resolve waypoints
        waypoint_indices: list[int] = []
        unresolved: list[str] = []
        for name in waypoints:
            idx = universe.resolve_name(name)
            if idx is not None:
                if idx not in waypoint_indices:  # Avoid duplicates
                    waypoint_indices.append(idx)
            else:
                unresolved.append(name)

        # Check we still have enough waypoints after resolution
        if len(waypoint_indices) < MIN_WAYPOINTS:
            raise InvalidParameterError(
                "waypoints",
                waypoint_indices,
                f"Only {len(waypoint_indices)} valid waypoints after resolution, "
                f"need at least {MIN_WAYPOINTS}",
            )

        # Resolve avoid_systems
        avoid_indices: set[int] = set()
        unresolved_avoids: list[str] = []
        if avoid_systems:
            for name in avoid_systems:
                idx = universe.resolve_name(name)
                if idx is not None:
                    avoid_indices.add(idx)
                else:
                    unresolved_avoids.append(name)

        result = _optimize_waypoints(
            universe=universe,
            waypoint_indices=waypoint_indices,
            origin_idx=origin_idx,
            origin_name=origin_name,
            return_to_origin=return_to_origin,
            security_filter=security_filter,  # type: ignore[arg-type]
            avoid_systems=avoid_indices,
            unresolved_waypoints=unresolved,
            unresolved_avoids=unresolved_avoids,
            corrections=corrections,
        )

        return result


def _optimize_waypoints(
    universe: UniverseGraph,
    waypoint_indices: list[int],
    origin_idx: int | None,
    origin_name: str | None,
    return_to_origin: bool,
    security_filter: str = "any",
    avoid_systems: set[int] | None = None,
    unresolved_waypoints: list[str] | None = None,
    unresolved_avoids: list[str] | None = None,
    corrections: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Optimize waypoint visit order using TSP approximation.

    Algorithm:
    1. Build distance matrix for all waypoints (+ origin if specified)
    2. If no origin: find optimal starting point (minimum total tour cost)
    3. Apply nearest-neighbor TSP heuristic
    4. Optionally add return leg to origin
    5. Expand tour to full route with intermediate systems
    6. Build result

    Args:
        universe: UniverseGraph for pathfinding
        waypoint_indices: Vertex indices of waypoints to visit
        origin_idx: Optional fixed starting vertex index
        return_to_origin: Whether to return to origin after visiting all waypoints
        security_filter: Security constraint for routing
        avoid_systems: Set of vertex indices to avoid
        unresolved_waypoints: Waypoint names that couldn't be resolved
        unresolved_avoids: Avoid system names that couldn't be resolved

    Returns:
        OptimizedWaypointResult as dict
    """
    # Step 1: Build list of all vertices for distance matrix
    if origin_idx is not None and origin_idx not in waypoint_indices:
        all_vertices = [origin_idx] + waypoint_indices
    else:
        all_vertices = waypoint_indices
        # If origin is in waypoints, just track it
        if origin_idx is not None:
            # Make sure origin is first for consistent handling
            all_vertices = [origin_idx] + [v for v in waypoint_indices if v != origin_idx]

    # Step 2: Compute distance matrix
    matrix = DistanceMatrix.compute(
        universe,
        all_vertices,
        security_filter=security_filter,  # type: ignore[arg-type]
        avoid_systems=avoid_systems,
    )

    # Step 3: Determine starting point
    if origin_idx is not None:
        start_idx = origin_idx
    else:
        # Find best starting point: one that minimizes total tour cost
        # Use the vertex with minimum average distance to others
        start_idx = _find_best_start(waypoint_indices, matrix)

    # Step 4: Apply nearest-neighbor TSP
    # Tour visits all waypoints (excluding origin if separate)
    if origin_idx is not None and origin_idx not in waypoint_indices:
        to_visit = waypoint_indices
    else:
        to_visit = [v for v in waypoint_indices if v != start_idx]

    tour = _nearest_neighbor_tsp(start_idx, to_visit, matrix)

    # Step 5: Build full route
    full_route: list[int] = []

    # Expand tour segments
    for i in range(len(tour) - 1):
        src = tour[i]
        dst = tour[i + 1]
        segment = matrix.path(src, dst)
        if segment:
            # Add all but last (will be added as next segment's start)
            full_route.extend(segment[:-1])

    # Add the last waypoint
    if tour:
        full_route.append(tour[-1])

    # Step 6: Handle return to origin
    is_loop = False
    if return_to_origin and origin_idx is not None:
        # Add return leg
        return_segment = matrix.path(tour[-1], origin_idx)
        if return_segment and len(return_segment) > 1:
            full_route.extend(return_segment[1:])  # Skip first (already at last waypoint)
        is_loop = True

    # Step 7: Build result
    return _build_optimization_result(
        universe=universe,
        tour=tour,
        full_route=full_route,
        origin_idx=origin_idx,
        origin_name=origin_name,
        is_loop=is_loop,
        unresolved_waypoints=unresolved_waypoints,
        unresolved_avoids=unresolved_avoids,
        corrections=corrections,
    )


def _find_best_start(waypoints: list[int], matrix: DistanceMatrix) -> int:
    """
    Find the best starting waypoint for TSP.

    Heuristic: Choose the waypoint with minimum total distance to all others.
    This tends to produce better tours as it avoids starting at an extreme.

    Args:
        waypoints: List of waypoint vertex indices
        matrix: Precomputed distance matrix

    Returns:
        Best starting vertex index
    """
    best_start = waypoints[0]
    best_total = float("inf")

    for wp in waypoints:
        total = sum(matrix.distance(wp, other) for other in waypoints if other != wp)
        if total < best_total:
            best_total = total
            best_start = wp

    return best_start


def _nearest_neighbor_tsp(
    start: int,
    waypoints: list[int],
    matrix: DistanceMatrix,
) -> list[int]:
    """
    Nearest-neighbor TSP heuristic.

    Greedy algorithm that always visits the nearest unvisited waypoint.
    Produces tours typically within 25% of optimal.

    Args:
        start: Starting vertex index
        waypoints: List of waypoint vertex indices to visit
        matrix: Precomputed distance matrix for O(1) lookups

    Returns:
        Ordered list of vertex indices forming the tour
    """
    tour = [start]
    unvisited = set(waypoints)

    current = start
    while unvisited:
        # Find nearest unvisited
        nearest = min(
            unvisited,
            key=lambda w: matrix.distance(current, w),
        )
        tour.append(nearest)
        unvisited.remove(nearest)
        current = nearest

    return tour


def _build_optimization_result(
    universe: UniverseGraph,
    tour: list[int],
    full_route: list[int],
    origin_idx: int | None,
    origin_name: str | None,
    is_loop: bool,
    unresolved_waypoints: list[str] | None = None,
    unresolved_avoids: list[str] | None = None,
    corrections: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Build OptimizedWaypointResult from computed tour.

    Args:
        universe: UniverseGraph for system lookups
        tour: Ordered list of waypoint vertex indices
        full_route: Complete route including intermediate systems
        origin_idx: Origin vertex index (if specified)
        origin_name: Canonical origin name (if specified)
        is_loop: Whether route returns to origin
        unresolved_waypoints: Waypoint names that couldn't be resolved
        unresolved_avoids: Avoid system names that couldn't be resolved
        corrections: Auto-corrected system names {input: canonical}

    Returns:
        OptimizedWaypointResult as dictionary
    """
    # Build waypoint info with visit order
    waypoints = [
        WaypointInfo(
            name=universe.idx_to_name[idx],
            system_id=int(universe.system_ids[idx]),
            security=float(universe.security[idx]),
            security_class=universe.security_class(idx),
            region=universe.get_region_name(idx),
            visit_order=i,
        )
        for i, idx in enumerate(tour)
    ]

    # Build full route system info
    route_systems = [build_system_info(universe, idx) for idx in full_route]

    # Calculate total jumps
    total_jumps = len(full_route) - 1 if full_route else 0

    # Build warnings
    warnings: list[str] = []
    if unresolved_waypoints:
        warnings.append(f"Unknown waypoints: {', '.join(unresolved_waypoints)}")
    if unresolved_avoids:
        warnings.append(f"Unknown systems in avoid_systems: {', '.join(unresolved_avoids)}")

    return OptimizedWaypointResult(
        origin=origin_name,
        waypoints=waypoints,
        total_jumps=total_jumps,
        route_systems=route_systems,
        is_loop=is_loop,
        unresolved_waypoints=unresolved_waypoints or [],
        warnings=warnings,
        corrections=corrections or {},
    ).model_dump()
