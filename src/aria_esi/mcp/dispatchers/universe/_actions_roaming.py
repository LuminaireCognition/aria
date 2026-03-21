"""Roaming route action implementation."""

from __future__ import annotations

from aria_esi.store.activity import ActivityData

from ...errors import InvalidParameterError
from ...models import NeighborInfo, RoamRouteResult, RoamRouteSystem
from ...tools import collect_corrections, get_universe, resolve_system_name
from ._helpers_local_area import _find_escape_routes
from ._helpers_roam import (
    classify_systems,
    collect_bfs_data,
    fetch_activity_for_systems,
    greedy_forward_walk,
    sweep_retrace,
)


async def _roam_route(
    origin: str | None,
    target_jumps: int = 20,
    activity_type: str = "ratting",
    mode: str = "linear",
    avoid_systems: list[str] | None = None,
    avoid_hotspots: bool = True,
    hotspot_threshold: int = 5,
    direction: str | None = None,
) -> dict:
    """
    Build a linear hunting/roaming route through active systems.

    Constructs a route that threads through ratting or PVP-active space,
    avoiding PVP hotspots and respecting topology constraints.
    """
    if not origin:
        raise InvalidParameterError("origin", origin, "Required for action='roam_route'")

    if activity_type not in ("ratting", "kills"):
        raise InvalidParameterError("activity_type", activity_type, "Must be 'ratting' or 'kills'")

    if mode not in ("linear", "sweep"):
        raise InvalidParameterError("mode", mode, "Must be 'linear' or 'sweep'")

    if target_jumps < 10 or target_jumps > 40:
        raise InvalidParameterError("target_jumps", target_jumps, "Must be between 10 and 40")

    universe = get_universe()

    # Resolve origin
    origin_resolved = resolve_system_name(origin)
    corrections = collect_corrections(origin_resolved)

    # Resolve direction target
    direction_idx: int | None = None
    if direction:
        try:
            direction_resolved = resolve_system_name(direction)
            direction_idx = direction_resolved.idx
            corrections.update(collect_corrections(direction_resolved))
        except Exception:  # noqa: BLE001 -- MCP handler
            pass  # Non-fatal: direction is optional bias

    # Resolve avoid systems
    avoid_indices: set[int] = set()
    warnings: list[str] = []
    if avoid_systems:
        for name in avoid_systems:
            idx = universe.resolve_name(name)
            if idx is not None:
                avoid_indices.add(idx)
            else:
                warnings.append(f"Unknown system in avoid_systems: {name}")

    # Step 1: BFS data collection
    bfs_radius = target_jumps * 2
    visited_bfs = await collect_bfs_data(universe, origin_resolved.idx, bfs_radius, avoid_indices)

    # Fetch activity for all systems in range
    system_ids = [int(universe.system_ids[idx]) for idx in visited_bfs]
    activity_data = await fetch_activity_for_systems(system_ids)

    # Step 2: Classify systems
    classification, hunt_metrics, hunt_threshold = classify_systems(
        universe, visited_bfs, activity_data, activity_type, hotspot_threshold
    )

    # Step 3: Greedy forward walk
    route_indices = greedy_forward_walk(
        universe=universe,
        origin_idx=origin_resolved.idx,
        target_jumps=target_jumps,
        classification=classification,
        hunt_metrics=hunt_metrics,
        avoid_hotspots=avoid_hotspots,
        direction_idx=direction_idx,
        visited_bfs=visited_bfs,
        avoid_indices=avoid_indices,
    )

    # Step 4: Sweep-mode retrace (if applicable)
    retrace_indices: list[int] = []
    if mode == "sweep" and len(route_indices) - 1 < target_jumps:
        route_indices, retrace_indices = sweep_retrace(
            universe=universe,
            route=route_indices,
            target_jumps=target_jumps,
            classification=classification,
            hunt_metrics=hunt_metrics,
            avoid_hotspots=avoid_hotspots,
            avoid_indices=avoid_indices,
        )

    # Step 5: Annotate and build response
    retrace_set = set(retrace_indices)
    retrace_names = [universe.idx_to_name[idx] for idx in retrace_indices]

    systems: list[RoamRouteSystem] = []
    total_npc = 0
    total_pvp = 0
    hunting_count = 0

    for jump_num, idx in enumerate(route_indices, start=1):
        system_id = int(universe.system_ids[idx])
        act = activity_data.get(system_id, ActivityData(system_id=system_id))

        # Determine phase
        if idx in retrace_set and jump_num > route_indices.index(idx):
            phase = "retrace"
        elif classification.get(idx) == "hunt":
            phase = "hunt"
            hunting_count += 1
        else:
            phase = "transit"

        total_npc += act.npc_kills
        total_pvp += act.ship_kills + act.pod_kills

        neighbors = [
            NeighborInfo(
                name=universe.idx_to_name[n],
                security=float(universe.security[n]),
                security_class=universe.security_class(n),
            )
            for n in universe.graph.neighbors(idx)
        ]

        systems.append(
            RoamRouteSystem(
                name=universe.idx_to_name[idx],
                system_id=system_id,
                security=float(universe.security[idx]),
                region=universe.get_region_name(idx),
                jump_number=jump_num,
                phase=phase,
                npc_kills=act.npc_kills,
                ship_kills=act.ship_kills,
                pod_kills=act.pod_kills,
                ship_jumps=act.ship_jumps,
                neighbors=neighbors,
            )
        )

    # Calculate escape routes from endpoint
    endpoint_idx = route_indices[-1] if route_indices else origin_resolved.idx
    endpoint_sec = float(universe.security[endpoint_idx])
    escape_routes = await _find_escape_routes(
        universe, endpoint_idx, endpoint_sec, visited_bfs, bfs_radius
    )

    result = RoamRouteResult(
        origin=origin_resolved.canonical_name,
        systems=systems,
        total_jumps=max(0, len(route_indices) - 1),
        hunting_systems=hunting_count,
        total_npc_kills=total_npc,
        total_pvp_kills=total_pvp,
        retrace_systems=retrace_names,
        escape_routes=escape_routes,
        warnings=warnings,
        corrections=corrections,
    )

    return result.model_dump()
