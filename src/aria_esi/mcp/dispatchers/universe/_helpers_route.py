"""Route computation and building helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from aria_esi.store.activity import get_activity_cache

from ....services.navigation import (
    compute_security_summary as _svc_compute_security_summary,
)
from ....services.navigation import (
    generate_warnings as _svc_generate_warnings,
)
from ...models import RouteResult, SecuritySummary
from ...utils import build_system_info

if TYPE_CHECKING:
    from aria_esi.universe.graph import UniverseGraph

    from ....services.navigation import RouteMode


def _calculate_route(
    universe: UniverseGraph,
    origin_idx: int,
    dest_idx: int,
    mode: str,
    avoid_systems: set[int] | None = None,
    preferred_systems: set[int] | None = None,
) -> list[int]:
    """
    Calculate route using NavigationService.

    Args:
        universe: UniverseGraph for pathfinding
        origin_idx: Starting vertex index
        dest_idx: Destination vertex index
        mode: Routing mode (shortest, safe, unsafe)
        avoid_systems: Set of vertex indices to avoid
        preferred_systems: Set of vertex indices to prefer (territory routing)

    Returns:
        List of vertex indices from origin to destination
    """
    from ....services.navigation import NavigationService

    service = NavigationService(universe)
    return service.calculate_route(
        origin_idx, dest_idx, cast("RouteMode", mode), avoid_systems, preferred_systems
    )


async def _generate_fw_route_warnings(universe: UniverseGraph, path: list[int]) -> list[str]:
    """Generate warnings for FW warzone systems on route."""
    cache = get_activity_cache()
    fw_data = await cache.get_all_fw()
    if not fw_data:
        return []

    fw_on_route = 0
    contested_systems: list[str] = []
    vulnerable_systems: list[str] = []

    for idx in path:
        system_id = int(universe.system_ids[idx])
        fw_entry = fw_data.get(system_id)
        if fw_entry is None:
            continue
        fw_on_route += 1
        name = universe.idx_to_name[idx]
        if fw_entry.contested == "vulnerable":
            vulnerable_systems.append(name)
        elif fw_entry.contested == "contested":
            contested_systems.append(name)

    warnings: list[str] = []
    if fw_on_route > 0:
        warnings.append(
            f"Route passes through {fw_on_route} Faction Warfare warzone system(s) - expect militia activity"
        )
    if vulnerable_systems:
        warnings.append(
            f"Vulnerable FW system(s): {', '.join(vulnerable_systems)} - high militia activity likely"
        )
    if contested_systems:
        warnings.append(f"Contested FW system(s): {', '.join(contested_systems)}")

    return warnings


async def _build_route_result(
    universe: UniverseGraph,
    path: list[int],
    origin: str,
    destination: str,
    mode: str,
    corrections: dict[str, str] | None = None,
    include_activity: bool = False,
) -> RouteResult:
    """Build complete RouteResult from path."""
    from aria_esi.store.activity import classify_activity

    systems = [build_system_info(universe, idx) for idx in path]
    summary = _svc_compute_security_summary(universe, path)
    warnings = _svc_generate_warnings(universe, path, mode)

    if include_activity:
        cache = get_activity_cache()
        enriched = []
        for system_info in systems:
            activity = await cache.get_activity(system_info.system_id)
            enriched.append(
                system_info.model_copy(
                    update={
                        "npc_kills": activity.npc_kills,
                        "ship_kills": activity.ship_kills,
                        "pod_kills": activity.pod_kills,
                        "ship_jumps": activity.ship_jumps,
                        "activity_level": classify_activity(
                            activity.ship_kills + activity.pod_kills, "kills"
                        ),
                    }
                )
            )
        systems = enriched

    return RouteResult(
        origin=origin,
        destination=destination,
        mode=cast("RouteMode", mode),
        jumps=len(path) - 1,
        systems=systems,
        security_summary=SecuritySummary(
            total_jumps=summary.total_jumps,
            highsec_jumps=summary.highsec_jumps,
            lowsec_jumps=summary.lowsec_jumps,
            nullsec_jumps=summary.nullsec_jumps,
            lowest_security=summary.lowest_security,
            lowest_security_system=summary.lowest_security_system,
        ),
        warnings=warnings,
        corrections=corrections or {},
    )


# Re-export for test compatibility
def _route_compute_security_summary(
    universe: UniverseGraph,
    path: list[int],
) -> SecuritySummary:
    """Compute security breakdown for route (wrapper for tests)."""
    summary = _svc_compute_security_summary(universe, path)
    return SecuritySummary(
        total_jumps=summary.total_jumps,
        highsec_jumps=summary.highsec_jumps,
        lowsec_jumps=summary.lowsec_jumps,
        nullsec_jumps=summary.nullsec_jumps,
        lowest_security=summary.lowest_security,
        lowest_security_system=summary.lowest_security_system,
    )


def _route_generate_warnings(
    universe: UniverseGraph,
    path: list[int],
    mode: str,
) -> list[str]:
    """Generate route warnings (wrapper for tests)."""
    return _svc_generate_warnings(universe, path, mode)
