"""TSP waypoint optimization helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...models import OptimizedWaypointResult, WaypointInfo
from ...utils import DistanceMatrix, build_system_info

if TYPE_CHECKING:
    from aria_esi.universe.graph import UniverseGraph


def _do_optimize_waypoints(
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
    """Optimize waypoint visit order using TSP approximation."""
    if origin_idx is not None and origin_idx not in waypoint_indices:
        all_vertices = [origin_idx] + waypoint_indices
    else:
        all_vertices = waypoint_indices
        if origin_idx is not None:
            all_vertices = [origin_idx] + [v for v in waypoint_indices if v != origin_idx]

    matrix = DistanceMatrix.compute(
        universe,
        all_vertices,
        security_filter=security_filter,  # type: ignore[arg-type]
        avoid_systems=avoid_systems,
    )

    if origin_idx is not None:
        start_idx = origin_idx
    else:
        start_idx = _find_best_start(waypoint_indices, matrix)

    if origin_idx is not None and origin_idx not in waypoint_indices:
        to_visit = waypoint_indices
    else:
        to_visit = [v for v in waypoint_indices if v != start_idx]

    tour = _nearest_neighbor_tsp(start_idx, to_visit, matrix)

    full_route: list[int] = []
    for i in range(len(tour) - 1):
        src = tour[i]
        dst = tour[i + 1]
        segment = matrix.path(src, dst)
        if segment:
            full_route.extend(segment[:-1])

    if tour:
        full_route.append(tour[-1])

    is_loop = False
    if return_to_origin and origin_idx is not None:
        return_segment = matrix.path(tour[-1], origin_idx)
        if return_segment and len(return_segment) > 1:
            full_route.extend(return_segment[1:])
        is_loop = True

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
    """Find the best starting waypoint for TSP."""
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
    """Nearest-neighbor TSP heuristic."""
    tour = [start]
    unvisited = set(waypoints)

    current = start
    while unvisited:
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
    """Build OptimizedWaypointResult from computed tour."""
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

    route_systems = [build_system_info(universe, idx) for idx in full_route]
    total_jumps = len(full_route) - 1 if full_route else 0

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
