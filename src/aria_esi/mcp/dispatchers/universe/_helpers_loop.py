"""Loop planning delegation helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...context_policy import UNIVERSE
from ...errors import InsufficientBordersError
from ...models import BorderSystem, LoopResult
from ...utils import DistanceMatrix, build_system_info

if TYPE_CHECKING:
    from aria_esi.universe.graph import UniverseGraph


# Search radius calculation constant
SEARCH_RADIUS_DIVISOR = UNIVERSE.LOOP_SEARCH_RADIUS_DIVISOR


def _plan_loop(
    universe: UniverseGraph,
    origin_idx: int,
    target_jumps: int,
    min_borders: int,
    max_borders: int | None,
    optimize: str = "density",
    security_filter: str = "highsec",
    avoid_systems: set[int] | None = None,
    unresolved_avoids: list[str] | None = None,
    corrections: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Plan circular route through border systems."""
    from ....services.loop_planning import LoopPlanningService
    from ....services.loop_planning.errors import (
        InsufficientBordersError as ServiceInsufficientBordersError,
    )

    service = LoopPlanningService(universe)
    try:
        summary = service.plan_loop(
            origin_idx=origin_idx,
            target_jumps=target_jumps,
            min_borders=min_borders,
            max_borders=max_borders,
            optimize=optimize,  # type: ignore[arg-type]
            security_filter=security_filter,  # type: ignore[arg-type]
            avoid_systems=avoid_systems,
            search_radius_divisor=SEARCH_RADIUS_DIVISOR,
            max_borders_cap=UNIVERSE.LOOP_MAX_BORDERS_CAP,
        )
    except ServiceInsufficientBordersError as e:
        raise InsufficientBordersError(
            found=e.found,
            required=e.required,
            search_radius=e.search_radius,
            suggestion=e.suggestion,
        ) from e

    return _build_loop_result(
        universe,
        origin_idx,
        summary.full_route,
        summary.borders_visited,
        unresolved_avoids,
        corrections,
    )


# Backwards-compatible aliases for tests
def _find_borders_with_distance(
    universe: UniverseGraph,
    origin_idx: int,
    limit: int,
    max_jumps: int,
    security_filter: str = "highsec",
    avoid_systems: set[int] | None = None,
) -> list[tuple[int, int]]:
    """Backwards-compatible alias. See services.loop_planning.find_borders_with_distance."""
    from ....services.loop_planning import find_borders_with_distance

    return find_borders_with_distance(
        universe,
        origin_idx,
        limit,
        max_jumps,
        security_filter,  # type: ignore[arg-type]
        avoid_systems,
    )


def _select_diverse_borders_matrix(
    candidates: list[tuple[int, int]],
    matrix: DistanceMatrix,
) -> list[tuple[int, int]]:
    """Backwards-compatible alias. See services.loop_planning.select_borders_coverage."""
    from ....services.loop_planning import select_borders_coverage

    return select_borders_coverage(candidates, matrix)


def _nearest_neighbor_tsp_matrix(
    start: int,
    waypoints: list[int],
    matrix: DistanceMatrix,
) -> list[int]:
    """Backwards-compatible alias. See services.loop_planning.nearest_neighbor_tsp."""
    from ....services.loop_planning import nearest_neighbor_tsp

    return nearest_neighbor_tsp(start, waypoints, matrix)


def _expand_tour_matrix(tour: list[int], matrix: DistanceMatrix) -> list[int]:
    """Backwards-compatible alias. See services.loop_planning.expand_tour."""
    from ....services.loop_planning import expand_tour

    return expand_tour(tour, matrix)


def _build_loop_result(
    universe: UniverseGraph,
    origin_idx: int,
    full_route: list[int],
    borders_visited: list[tuple[int, int]],
    unresolved_avoids: list[str] | None = None,
    corrections: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build LoopResult from computed route."""
    systems = [build_system_info(universe, idx) for idx in full_route]

    border_systems = [
        BorderSystem(
            name=universe.idx_to_name[idx],
            system_id=int(universe.system_ids[idx]),
            security=float(universe.security[idx]),
            jumps_from_origin=dist,
            adjacent_lowsec=universe.get_adjacent_lowsec(idx),
            region=universe.get_region_name(idx),
        )
        for idx, dist in borders_visited
    ]

    unique_count = len(set(full_route))
    total_jumps = len(full_route) - 1 if full_route else 0
    backtrack = total_jumps - (unique_count - 1) if unique_count > 0 else 0
    efficiency = unique_count / len(full_route) if full_route else 0.0

    warnings: list[str] = []
    if unresolved_avoids:
        warnings.append(f"Unknown systems in avoid_systems: {', '.join(unresolved_avoids)}")

    return LoopResult(
        systems=systems,
        total_jumps=total_jumps,
        unique_systems=unique_count,
        border_systems_visited=border_systems,
        backtrack_jumps=max(0, backtrack),
        efficiency=min(1.0, efficiency),
        warnings=warnings,
        corrections=corrections or {},
    ).model_dump()
