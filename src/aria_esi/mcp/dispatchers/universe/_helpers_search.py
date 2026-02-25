"""Border, search, and nearest-system helpers."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from ...activity import classify_activity
from ...models import BorderSystem, SystemSearchResult

if TYPE_CHECKING:
    from aria_esi.universe.graph import UniverseGraph

    from ...activity import ActivityData


# =============================================================================
# Borders
# =============================================================================


def _find_border_systems(
    universe: UniverseGraph,
    origin_idx: int,
    limit: int,
    max_jumps: int,
) -> list[BorderSystem]:
    """
    Find border systems using BFS with distance tracking.

    Only traverses high-sec systems for mining/PI relevance.
    """
    g = universe.graph
    border_results: list[tuple[int, int]] = []

    visited: dict[int, int] = {origin_idx: 0}
    queue: deque[tuple[int, int]] = deque([(origin_idx, 0)])
    gather_limit = limit * 3

    while queue:
        vertex, dist = queue.popleft()
        if dist > max_jumps:
            continue

        if vertex in universe.border_systems:
            border_results.append((vertex, dist))
            if len(border_results) >= gather_limit:
                break

        for neighbor in g.neighbors(vertex):
            if neighbor not in visited:
                if universe.security[neighbor] >= 0.45:
                    visited[neighbor] = dist + 1
                    queue.append((neighbor, dist + 1))

    border_results.sort(key=lambda x: x[1])
    border_results = border_results[:limit]

    return [_build_border_system(universe, idx, dist) for idx, dist in border_results]


def _build_border_system(
    universe: UniverseGraph,
    idx: int,
    jumps_from_origin: int,
) -> BorderSystem:
    """Build BorderSystem object for a vertex."""
    adjacent_lowsec = [
        universe.idx_to_name[n]
        for n in universe.graph.neighbors(idx)
        if universe.security[n] < 0.45
    ]

    return BorderSystem(
        name=universe.idx_to_name[idx],
        system_id=int(universe.system_ids[idx]),
        security=float(universe.security[idx]),
        jumps_from_origin=jumps_from_origin,
        adjacent_lowsec=adjacent_lowsec,
        region=universe.get_region_name(idx),
    )


# =============================================================================
# Search
# =============================================================================


def _resolve_region(universe: UniverseGraph, region_name: str) -> int | None:
    """Resolve region name to ID (case-insensitive, O(1))."""
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
    coalition_system_ids: set[int] | None = None,
) -> list[SystemSearchResult]:
    """Execute system search with filters."""
    results: list[SystemSearchResult] = []
    distances: dict[int, int] = {}

    if coalition_system_ids is not None:
        # Start with coalition systems as candidates
        candidates = {
            universe.id_to_idx[sid] for sid in coalition_system_ids if sid in universe.id_to_idx
        }
        # If also filtering by BFS range, intersect
        if origin_idx is not None and max_jumps is not None:
            bfs_candidates, distances = _bfs_within_range(universe, origin_idx, max_jumps)
            candidates = candidates & bfs_candidates
    elif origin_idx is not None and max_jumps is not None:
        candidates, distances = _bfs_within_range(universe, origin_idx, max_jumps)
    elif region_id is not None:
        candidates = set(universe.region_systems.get(region_id, []))
    elif is_border is True:
        candidates = set(universe.border_systems)
    else:
        candidates = set(range(universe.system_count))

    for idx in candidates:
        if len(results) >= limit:
            break

        sec = universe.security[idx]
        if security_min is not None and sec < security_min:
            continue
        if security_max is not None and sec > security_max:
            continue

        if region_id is not None and origin_idx is not None:
            if int(universe.region_ids[idx]) != region_id:
                continue

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
    """BFS to find all systems within max_jumps."""
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
    """Build search result for a vertex."""
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
    coalition: str | None = None,
) -> dict[str, Any]:
    """Summarize applied filters for response."""
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
    if coalition:
        filters["coalition"] = coalition
    return filters


# =============================================================================
# Nearest
# =============================================================================


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
    """Build a predicate function from filter parameters."""

    def predicate(idx: int) -> bool:
        if is_border is True and idx not in universe.border_systems:
            return False
        if is_border is False and idx in universe.border_systems:
            return False

        if min_adjacent_lowsec is not None:
            lowsec_neighbors = sum(
                1 for n in universe.graph.neighbors(idx) if universe.security[n] < 0.45
            )
            if lowsec_neighbors < min_adjacent_lowsec:
                return False

        sec = universe.security[idx]
        if security_min is not None and sec < security_min:
            return False
        if security_max is not None and sec > security_max:
            return False

        if region_id is not None and int(universe.region_ids[idx]) != region_id:
            return False

        if max_kills is not None or min_npc_kills is not None or activity_level is not None:
            system_id = int(universe.system_ids[idx])
            activity = activity_data.get(system_id) if activity_data else None

            pvp_kills = 0
            npc_kills = 0
            if activity:
                pvp_kills = activity.ship_kills + activity.pod_kills
                npc_kills = activity.npc_kills

            if max_kills is not None and pvp_kills > max_kills:
                return False
            if min_npc_kills is not None and npc_kills < min_npc_kills:
                return False
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
    """Find nearest systems matching predicate using BFS."""
    g = universe.graph
    results: list[SystemSearchResult] = []

    visited: set[int] = {origin_idx}
    queue: deque[tuple[int, int]] = deque([(origin_idx, 0)])

    while queue and len(results) < limit:
        vertex, dist = queue.popleft()

        if dist > max_jumps:
            continue

        if dist > 0 and predicate(vertex):
            results.append(_build_nearest_result(universe, vertex, dist))
            if len(results) >= limit:
                break

        for neighbor in g.neighbors(vertex):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, dist + 1))

    return results


def _build_nearest_result(
    universe: UniverseGraph,
    idx: int,
    jumps_from_origin: int,
) -> SystemSearchResult:
    """Build search result for a nearest-match vertex."""
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
