"""Planning action implementations: loop, analyze, optimize_waypoints."""

from __future__ import annotations

from ...context import wrap_output
from ...context_policy import UNIVERSE
from ...errors import InvalidParameterError
from ...models import VALID_OPTIMIZE_MODES, VALID_SECURITY_FILTERS
from ...tools import collect_corrections, get_universe, resolve_system_name
from ._helpers_analyze import _analyze_route, _validate_connectivity
from ._helpers_loop import _plan_loop
from ._helpers_waypoints import _do_optimize_waypoints


async def _loop(
    origin: str | None,
    target_jumps: int,
    min_borders: int,
    max_borders: int | None,
    optimize: str,
    security_filter: str,
    avoid_systems: list[str] | None,
) -> dict:
    """Loop action."""
    if not origin:
        raise InvalidParameterError("origin", origin, "Required for action='loop'")

    universe = get_universe()

    if (
        target_jumps < UNIVERSE.LOOP_MIN_TARGET_JUMPS
        or target_jumps > UNIVERSE.LOOP_MAX_TARGET_JUMPS
    ):
        raise InvalidParameterError(
            "target_jumps",
            target_jumps,
            f"Must be between {UNIVERSE.LOOP_MIN_TARGET_JUMPS} and {UNIVERSE.LOOP_MAX_TARGET_JUMPS}",
        )
    if min_borders < UNIVERSE.LOOP_MIN_BORDERS or min_borders > UNIVERSE.LOOP_MAX_BORDERS:
        raise InvalidParameterError(
            "min_borders",
            min_borders,
            f"Must be between {UNIVERSE.LOOP_MIN_BORDERS} and {UNIVERSE.LOOP_MAX_BORDERS}",
        )
    if max_borders is not None and (
        max_borders < min_borders or max_borders > UNIVERSE.LOOP_MAX_BORDERS_CAP
    ):
        raise InvalidParameterError(
            "max_borders",
            max_borders,
            f"Must be between {min_borders} and {UNIVERSE.LOOP_MAX_BORDERS_CAP}",
        )
    if optimize not in VALID_OPTIMIZE_MODES:
        raise InvalidParameterError(
            "optimize",
            optimize,
            f"Must be one of: {', '.join(sorted(VALID_OPTIMIZE_MODES))}",
        )
    if security_filter not in VALID_SECURITY_FILTERS:
        raise InvalidParameterError(
            "security_filter",
            security_filter,
            f"Must be one of: {', '.join(sorted(VALID_SECURITY_FILTERS))}",
        )

    origin_resolved = resolve_system_name(origin)
    corrections = collect_corrections(origin_resolved)

    avoid_indices: set[int] = set()
    unresolved_avoids: list[str] = []
    if avoid_systems:
        for name in avoid_systems:
            idx = universe.resolve_name(name)
            if idx is not None:
                avoid_indices.add(idx)
            else:
                unresolved_avoids.append(name)

    result = _plan_loop(
        universe=universe,
        origin_idx=origin_resolved.idx,
        target_jumps=target_jumps,
        min_borders=min_borders,
        max_borders=max_borders,
        optimize=optimize,
        security_filter=security_filter,
        avoid_systems=avoid_indices,
        unresolved_avoids=unresolved_avoids,
        corrections=corrections,
    )

    return wrap_output(result, "systems", max_items=UNIVERSE.OUTPUT_MAX_SYSTEMS)


async def _analyze(systems: list[str] | None) -> dict:
    """Analyze action."""
    if not systems or len(systems) < 2:
        raise InvalidParameterError(
            "systems", systems, "At least 2 systems required for action='analyze'"
        )

    universe = get_universe()

    indices: list[int] = []
    for name in systems:
        idx = universe.resolve_name(name)
        if idx is None:
            raise InvalidParameterError("systems", name, f"Unknown system: {name}")
        indices.append(idx)

    _validate_connectivity(universe, indices, systems)
    result = _analyze_route(universe, indices)

    return wrap_output(result.model_dump(), "systems", max_items=UNIVERSE.OUTPUT_MAX_SYSTEMS)


async def _optimize_waypoints(
    waypoints: list[str] | None,
    origin: str | None,
    return_to_origin: bool,
    security_filter: str,
    avoid_systems: list[str] | None,
    linear: bool = False,
) -> dict:
    """Optimize waypoints action."""
    if not waypoints:
        raise InvalidParameterError(
            "waypoints", waypoints, "Required for action='optimize_waypoints'"
        )

    universe = get_universe()

    if len(waypoints) < UNIVERSE.WAYPOINTS_MIN_COUNT:
        raise InvalidParameterError(
            "waypoints",
            len(waypoints),
            f"At least {UNIVERSE.WAYPOINTS_MIN_COUNT} waypoints required for optimization",
        )
    if len(waypoints) > UNIVERSE.WAYPOINTS_MAX_COUNT:
        raise InvalidParameterError(
            "waypoints",
            len(waypoints),
            f"Maximum {UNIVERSE.WAYPOINTS_MAX_COUNT} waypoints allowed",
        )
    if security_filter not in VALID_SECURITY_FILTERS:
        raise InvalidParameterError(
            "security_filter",
            security_filter,
            f"Must be one of: {', '.join(sorted(VALID_SECURITY_FILTERS))}",
        )

    origin_idx: int | None = None
    origin_name: str | None = None
    corrections: dict[str, str] = {}
    if origin:
        origin_resolved = resolve_system_name(origin)
        origin_idx = origin_resolved.idx
        origin_name = origin_resolved.canonical_name
        corrections = collect_corrections(origin_resolved)

    waypoint_indices: list[int] = []
    unresolved: list[str] = []
    for name in waypoints:
        idx = universe.resolve_name(name)
        if idx is not None:
            if idx not in waypoint_indices:
                waypoint_indices.append(idx)
        else:
            unresolved.append(name)

    if len(waypoint_indices) < UNIVERSE.WAYPOINTS_MIN_COUNT:
        raise InvalidParameterError(
            "waypoints",
            waypoint_indices,
            f"Only {len(waypoint_indices)} valid waypoints after resolution, need at least {UNIVERSE.WAYPOINTS_MIN_COUNT}",
        )

    avoid_indices: set[int] = set()
    unresolved_avoids: list[str] = []
    if avoid_systems:
        for name in avoid_systems:
            idx = universe.resolve_name(name)
            if idx is not None:
                avoid_indices.add(idx)
            else:
                unresolved_avoids.append(name)

    result = _do_optimize_waypoints(
        universe=universe,
        waypoint_indices=waypoint_indices,
        origin_idx=origin_idx,
        origin_name=origin_name,
        return_to_origin=return_to_origin,
        security_filter=security_filter,
        avoid_systems=avoid_indices,
        unresolved_waypoints=unresolved,
        unresolved_avoids=unresolved_avoids,
        corrections=corrections,
        linear=linear,
    )

    return wrap_output(result, "route", max_items=UNIVERSE.OUTPUT_MAX_ROUTE)
