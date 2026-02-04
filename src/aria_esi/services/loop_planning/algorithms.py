"""
Loop Planning Algorithms.

Provides TSP approximation and border selection algorithms for loop planning.
These are pure algorithms that operate on precomputed distance matrices.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...mcp.utils import DistanceMatrix


def select_borders_density(
    origin_idx: int,
    candidates: list[tuple[int, int]],
    matrix: DistanceMatrix,
    target_jumps: int,
    min_borders: int,
) -> list[tuple[int, int]]:
    """
    Select border systems that fit within jump budget.

    Algorithm: Greedy chain-building that tracks cumulative route cost.
    Adds borders in order of proximity to current position, stopping when
    the route (including return to origin) would exceed the target.

    Args:
        origin_idx: Starting vertex index
        candidates: List of (vertex_idx, distance_from_origin) tuples, sorted by distance
        matrix: Precomputed DistanceMatrix for O(1) lookups
        target_jumps: Target maximum route length
        min_borders: Minimum borders to include (even if over budget)

    Returns:
        List of selected (vertex_idx, distance_from_origin) tuples
    """
    if not candidates:
        return []

    selected: list[tuple[int, int]] = []
    remaining = list(candidates)
    current = origin_idx
    cumulative_distance: float = 0.0

    while remaining:
        # Find nearest unvisited border to current position
        best_idx = -1
        best_distance = float("inf")

        for i, (vertex, _) in enumerate(remaining):
            dist = matrix.distance(current, vertex)
            if dist < best_distance:
                best_distance = dist
                best_idx = i

        if best_idx < 0:
            break

        border_idx, dist_from_origin = remaining[best_idx]

        # Calculate cost: leg to this border + return to origin
        leg_cost = matrix.distance(current, border_idx)
        return_cost = matrix.distance(border_idx, origin_idx)
        projected_total = cumulative_distance + leg_cost + return_cost

        # Add if: under budget OR we haven't met minimum yet
        if projected_total <= target_jumps or len(selected) < min_borders:
            selected.append((border_idx, dist_from_origin))
            cumulative_distance += leg_cost
            current = border_idx
            remaining.pop(best_idx)
        else:
            # Over budget and have enough borders - stop
            break

        # Early exit if we've used most of our budget
        if cumulative_distance + return_cost >= target_jumps and len(selected) >= min_borders:
            break

    return selected


def select_borders_coverage(
    candidates: list[tuple[int, int]],
    matrix: DistanceMatrix,
) -> list[tuple[int, int]]:
    """
    Select spatially diverse border systems using precomputed distances.

    Algorithm: Greedy selection maximizing minimum distance to selected set.
    Start with closest to origin, then iteratively add the candidate most
    distant from the currently selected set.

    Args:
        candidates: List of (vertex_idx, distance_from_origin) tuples
        matrix: Precomputed DistanceMatrix for O(1) lookups

    Returns:
        List of selected (vertex_idx, distance_from_origin) tuples
    """
    if not candidates:
        return []

    selected: list[tuple[int, int]] = [candidates[0]]
    remaining = list(candidates[1:])

    while remaining:
        # Find candidate maximizing minimum distance to selected set
        best_idx = -1
        best_min_dist = -1.0

        for i, (vertex, _) in enumerate(remaining):
            # O(1) lookup instead of pathfinding
            min_dist = min(matrix.distance(vertex, s[0]) for s in selected)
            if min_dist > best_min_dist:
                best_min_dist = min_dist
                best_idx = i

        if best_idx >= 0:
            selected.append(remaining.pop(best_idx))
        else:
            break

    return selected


def nearest_neighbor_tsp(
    start: int,
    waypoints: list[int],
    matrix: DistanceMatrix,
) -> list[int]:
    """
    Nearest-neighbor TSP heuristic using precomputed distances.

    Produces a tour visiting all waypoints starting from start.
    Does not include return to start (expansion handles that).

    Args:
        start: Starting vertex index
        waypoints: List of waypoint vertex indices to visit
        matrix: Precomputed DistanceMatrix for O(1) lookups

    Returns:
        Ordered list of vertices forming the tour
    """
    tour = [start]
    unvisited = set(waypoints)

    current = start
    while unvisited:
        # O(1) lookup instead of pathfinding
        nearest = min(
            unvisited,
            key=lambda w: matrix.distance(current, w),
        )
        tour.append(nearest)
        unvisited.remove(nearest)
        current = nearest

    return tour


def expand_tour(tour: list[int], matrix: DistanceMatrix) -> list[int]:
    """
    Expand tour waypoints to full route using precomputed paths.

    Connects each consecutive pair with shortest path, including
    the return leg back to origin.

    Args:
        tour: List of waypoint vertex indices
        matrix: Precomputed DistanceMatrix with cached paths

    Returns:
        Full route with all intermediate systems
    """
    if len(tour) < 2:
        return tour + tour  # Just origin -> origin

    full_route: list[int] = []

    for i in range(len(tour)):
        src = tour[i]
        dst = tour[(i + 1) % len(tour)]  # Wrap to origin

        # O(1) lookup instead of pathfinding
        segment = matrix.path(src, dst)
        if segment:
            # Add all but last (will be added as next segment's start)
            # except for the final segment which closes the loop
            if i < len(tour) - 1:
                full_route.extend(segment[:-1])
            else:
                # Last segment returns to origin, include all
                full_route.extend(segment)

    return full_route
