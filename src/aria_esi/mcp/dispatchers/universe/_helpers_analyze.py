"""Route analysis helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...errors import RouteNotFoundError
from ...models import DangerZone, RouteAnalysis, SystemInfo
from ...utils import build_system_info
from ._helpers_route import _route_compute_security_summary

if TYPE_CHECKING:
    from aria_esi.universe.graph import UniverseGraph


def _validate_connectivity(
    universe: UniverseGraph,
    indices: list[int],
    names: list[str],
) -> None:
    """Validate that consecutive systems are connected by stargate."""
    g = universe.graph
    for i in range(len(indices) - 1):
        src = indices[i]
        dst = indices[i + 1]
        if dst not in g.neighbors(src):
            raise RouteNotFoundError(
                names[i],
                names[i + 1],
                reason="Systems not connected by stargate",
            )


def _analyze_route(
    universe: UniverseGraph,
    indices: list[int],
) -> RouteAnalysis:
    """Build complete route analysis."""
    systems = [build_system_info(universe, idx) for idx in indices]
    security_summary = _route_compute_security_summary(universe, indices)
    chokepoints = _find_chokepoints(universe, indices)
    danger_zones = _find_danger_zones(universe, indices)

    return RouteAnalysis(
        systems=systems,
        security_summary=security_summary,
        chokepoints=chokepoints,
        danger_zones=danger_zones,
    )


def _find_chokepoints(
    universe: UniverseGraph,
    indices: list[int],
) -> list[SystemInfo]:
    """Find chokepoints: points where route transitions security class."""
    chokepoints: list[SystemInfo] = []

    for i in range(1, len(indices)):
        prev_idx = indices[i - 1]
        curr_idx = indices[i]

        prev_class = universe.security_class(prev_idx)
        curr_class = universe.security_class(curr_idx)

        if prev_class == "HIGH" and curr_class in ("LOW", "NULL", "POCHVEN"):
            chokepoints.append(build_system_info(universe, curr_idx))
        elif prev_class in ("LOW", "NULL", "POCHVEN") and curr_class == "HIGH":
            chokepoints.append(build_system_info(universe, prev_idx))

    return chokepoints


def _find_danger_zones(
    universe: UniverseGraph,
    indices: list[int],
) -> list[DangerZone]:
    """Find danger zones: consecutive segments in low/null-sec."""
    danger_zones: list[DangerZone] = []
    in_danger = False
    zone_start: int | None = None
    zone_min_sec = 1.0

    for i, idx in enumerate(indices):
        sec = float(universe.security[idx])
        is_dangerous = sec < 0.45

        if is_dangerous and not in_danger:
            in_danger = True
            zone_start = i
            zone_min_sec = sec
        elif is_dangerous and in_danger:
            zone_min_sec = min(zone_min_sec, sec)
        elif not is_dangerous and in_danger:
            in_danger = False
            if zone_start is not None:
                danger_zones.append(
                    DangerZone(
                        start_system=universe.idx_to_name[indices[zone_start]],
                        end_system=universe.idx_to_name[indices[i - 1]],
                        jump_count=i - zone_start,
                        min_security=zone_min_sec,
                    )
                )
            zone_start = None

    if in_danger and zone_start is not None:
        danger_zones.append(
            DangerZone(
                start_system=universe.idx_to_name[indices[zone_start]],
                end_system=universe.idx_to_name[indices[-1]],
                jump_count=len(indices) - zone_start,
                min_security=zone_min_sec,
            )
        )

    return danger_zones
