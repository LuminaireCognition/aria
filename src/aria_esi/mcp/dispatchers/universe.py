"""
Universe Dispatcher for MCP Server.

Consolidates 14 universe navigation tools into a single dispatcher:
- route: Point-to-point navigation
- systems: Batch system lookups
- borders: Find high-sec/low-sec border systems
- search: Filter systems by criteria
- loop: Circular mining/patrol routes
- analyze: Route security analysis
- nearest: Find nearest systems matching predicates
- optimize_waypoints: TSP waypoint optimization
- activity: Live system activity data
- hotspots: Find high-activity systems
- gatecamp_risk: Route risk analysis
- fw_frontlines: Faction Warfare contested systems
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal

from ..context import log_context, summarize_route, wrap_output, wrap_output_multi
from ..context_policy import UNIVERSE
from ..errors import InvalidParameterError
from ..policy import check_capability
from ..validation import add_validation_warnings, validate_action_params

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from aria_esi.universe.graph import UniverseGraph

    from ..models import BorderType, EscapeRoute, ThreatLevel


UniverseAction = Literal[
    "route",
    "systems",
    "borders",
    "search",
    "loop",
    "analyze",
    "nearest",
    "optimize_waypoints",
    "activity",
    "hotspots",
    "gatecamp_risk",
    "fw_frontlines",
    "local_area",
]

VALID_ACTIONS: set[str] = {
    "route",
    "systems",
    "borders",
    "search",
    "loop",
    "analyze",
    "nearest",
    "optimize_waypoints",
    "activity",
    "hotspots",
    "gatecamp_risk",
    "fw_frontlines",
    "local_area",
}


def register_universe_dispatcher(server: FastMCP, graph: UniverseGraph) -> None:
    """
    Register the unified universe dispatcher with MCP server.

    Args:
        server: MCP Server instance
        graph: UniverseGraph for navigation operations
    """
    # Note: graph parameter kept for interface consistency but action implementations
    # use get_universe() from tools module for the actual graph instance
    _ = graph  # Silence unused parameter warning

    @server.tool()
    @log_context("universe")
    async def universe(
        action: str,
        # route params
        origin: str | None = None,
        destination: str | None = None,
        mode: str = "shortest",
        avoid_systems: list[str] | None = None,
        # systems params
        systems: list[str] | None = None,
        # borders/search/nearest params
        limit: int = 20,
        max_jumps: int | None = None,
        # search/nearest params
        security_min: float | None = None,
        security_max: float | None = None,
        region: str | None = None,
        is_border: bool | None = None,
        # nearest params
        min_adjacent_lowsec: int | None = None,
        # loop params
        target_jumps: int = 20,
        min_borders: int = 4,
        max_borders: int | None = None,
        optimize: str = "density",
        security_filter: str = "highsec",
        # waypoints params
        waypoints: list[str] | None = None,
        return_to_origin: bool = True,
        # hotspots params
        activity_type: str = "kills",
        # gatecamp_risk params
        route: list[str] | None = None,
        # fw_frontlines params
        faction: str | None = None,
        # activity params - realtime
        include_realtime: bool = False,
        # local_area params
        hotspot_threshold: int = 5,
        quiet_threshold: int = 0,
        ratting_threshold: int = 100,
    ) -> dict:
        """
        Unified universe navigation interface.

        Actions:
        - route: Calculate optimal route between two systems
        - systems: Get detailed info for multiple systems
        - borders: Find high-sec systems bordering low-sec
        - search: Search systems by criteria (security, region, etc.)
        - loop: Plan circular routes visiting border systems
        - analyze: Analyze security profile of a route
        - nearest: Find nearest systems matching predicates
        - optimize_waypoints: Optimize visit order for waypoints (TSP)
        - activity: Get recent activity data for systems
        - hotspots: Find high-activity systems near origin
        - gatecamp_risk: Analyze gatecamp risk along route
        - fw_frontlines: Get Faction Warfare contested systems
        - local_area: Consolidated local intel for orientation in unknown space

        Args:
            action: The operation to perform (see Actions above)

            Route params (action="route"):
                origin: Starting system
                destination: Target system
                mode: "shortest", "safe", or "unsafe"
                avoid_systems: Systems to avoid

            Systems params (action="systems"):
                systems: List of system names to look up

            Borders params (action="borders"):
                origin: Starting system for distance
                limit: Max systems to return (default 10, max 50)
                max_jumps: Search radius (default 15, max 30)

            Search params (action="search"):
                origin: Center point for distance filter
                max_jumps: Max distance from origin
                security_min/security_max: Security range filter
                region: Region name filter
                is_border: Filter to border systems
                limit: Max results (default 20, max 100)

            Loop params (action="loop"):
                origin: Start/end system
                target_jumps: Desired loop length (default 20)
                min_borders: Min border systems (default 4)
                max_borders: Max border systems
                optimize: "density" or "coverage"
                security_filter: "highsec", "lowsec", or "any"
                avoid_systems: Systems to avoid

            Analyze params (action="analyze"):
                systems: Ordered route to analyze

            Nearest params (action="nearest"):
                origin: Starting system
                is_border: Filter to border systems
                min_adjacent_lowsec: Min adjacent low-sec gates
                security_min/security_max: Security range
                region: Region filter
                limit: Max results (default 5, max 50)
                max_jumps: Search radius (default 30, max 50)

            Optimize waypoints params (action="optimize_waypoints"):
                waypoints: Systems to visit (2-50)
                origin: Optional fixed start
                return_to_origin: Return to start (default True)
                security_filter: "any", "highsec", "lowsec"
                avoid_systems: Systems to avoid

            Activity params (action="activity"):
                systems: Systems to query
                include_realtime: Include real-time kill data if poller is healthy

            Hotspots params (action="hotspots"):
                origin: Search center
                max_jumps: Search radius (default 15)
                activity_type: "kills", "jumps", or "ratting"
                security_min/security_max: Security filter
                limit: Max results (default 10)

            Gatecamp risk params (action="gatecamp_risk"):
                route: Explicit route, OR
                origin/destination: Calculate route
                mode: Routing mode (default "safe")

            FW frontlines params (action="fw_frontlines"):
                faction: Filter to specific faction

            Local area params (action="local_area"):
                origin: Current system for orientation
                max_jumps: Search radius (default 10, max 30)
                include_realtime: Include real-time gatecamp detection
                hotspot_threshold: Min kills to classify as hotspot (default 5)
                quiet_threshold: Max kills for quiet zone (default 0)
                ratting_threshold: Min NPC kills for ratting bank (default 100)

        Returns:
            Action-specific result dictionary

        Examples:
            universe(action="route", origin="Jita", destination="Amarr", mode="safe")
            universe(action="systems", systems=["Jita", "Perimeter"])
            universe(action="borders", origin="Dodixie", limit=5)
            universe(action="loop", origin="Masalle", target_jumps=25)
            universe(action="activity", systems=["Tama", "Amamake"])
            universe(action="hotspots", origin="Hek", activity_type="kills")
            universe(action="local_area", origin="ZZ-TOP", max_jumps=10, include_realtime=True)
        """
        if action not in VALID_ACTIONS:
            raise InvalidParameterError(
                "action",
                action,
                f"Must be one of: {', '.join(sorted(VALID_ACTIONS))}",
            )

        # Policy check - verify action is allowed
        # Pass context for policy extensibility and audit logging
        check_capability(
            "universe",
            action,
            context={
                "origin": origin,
                "destination": destination,
                "mode": mode,
                "systems_count": len(systems) if systems else None,
            },
        )

        # Validate parameters for this action
        # Warns when irrelevant parameters are passed (e.g., security_min for route action)
        validation_warnings = validate_action_params(
            "universe",
            action,
            {
                "origin": origin,
                "destination": destination,
                "mode": mode,
                "avoid_systems": avoid_systems,
                "systems": systems,
                "limit": limit,
                "max_jumps": max_jumps,
                "security_min": security_min,
                "security_max": security_max,
                "region": region,
                "is_border": is_border,
                "min_adjacent_lowsec": min_adjacent_lowsec,
                "target_jumps": target_jumps,
                "min_borders": min_borders,
                "max_borders": max_borders,
                "optimize": optimize,
                "security_filter": security_filter,
                "waypoints": waypoints,
                "return_to_origin": return_to_origin,
                "activity_type": activity_type,
                "route": route,
                "faction": faction,
                "include_realtime": include_realtime,
                "hotspot_threshold": hotspot_threshold,
                "quiet_threshold": quiet_threshold,
                "ratting_threshold": ratting_threshold,
            },
        )

        # Execute action and add any validation warnings to result
        match action:
            case "route":
                result = await _route(origin, destination, mode, avoid_systems)

            case "systems":
                result = await _systems(systems)

            case "borders":
                result = await _borders(origin, limit, max_jumps)

            case "search":
                result = await _search(
                    origin, max_jumps, security_min, security_max, region, is_border, limit
                )

            case "loop":
                result = await _loop(
                    origin,
                    target_jumps,
                    min_borders,
                    max_borders,
                    optimize,
                    security_filter,
                    avoid_systems,
                )

            case "analyze":
                result = await _analyze(systems)

            case "nearest":
                result = await _nearest(
                    origin,
                    is_border,
                    min_adjacent_lowsec,
                    security_min,
                    security_max,
                    region,
                    limit,
                    max_jumps,
                )

            case "optimize_waypoints":
                result = await _optimize_waypoints(
                    waypoints, origin, return_to_origin, security_filter, avoid_systems
                )

            case "activity":
                result = await _activity(systems, include_realtime)

            case "hotspots":
                result = await _hotspots(
                    origin, max_jumps, activity_type, security_min, security_max, limit
                )

            case "gatecamp_risk":
                result = await _gatecamp_risk(route, origin, destination, mode)

            case "fw_frontlines":
                result = await _fw_frontlines(faction)

            case "local_area":
                result = await _local_area(
                    origin,
                    max_jumps,
                    include_realtime,
                    hotspot_threshold,
                    quiet_threshold,
                    ratting_threshold,
                )

            case _:
                raise InvalidParameterError(
                    "action",
                    action,
                    f"Unknown action. Must be one of: {', '.join(sorted(VALID_ACTIONS))}",
                )

        # Add validation warnings to result if any
        return add_validation_warnings(result, validation_warnings)


# =============================================================================
# Action Implementations - Delegate to existing tool modules
# =============================================================================


async def _route(
    origin: str | None,
    destination: str | None,
    mode: str,
    avoid_systems: list[str] | None,
) -> dict:
    """Route action - delegate to tools_route."""
    if not origin:
        raise InvalidParameterError("origin", origin, "Required for action='route'")
    if not destination:
        raise InvalidParameterError("destination", destination, "Required for action='route'")

    from ..models import RouteResult
    from ..tools import collect_corrections, get_universe, resolve_system_name
    from ..tools_route import VALID_MODES, _build_route_result, _calculate_route

    universe = get_universe()

    if mode not in VALID_MODES:
        raise InvalidParameterError(
            "mode", mode, f"Must be one of: {', '.join(sorted(VALID_MODES))}"
        )

    origin_resolved = resolve_system_name(origin)
    dest_resolved = resolve_system_name(destination)
    corrections = collect_corrections(origin_resolved, dest_resolved)

    avoid_indices: set[int] | None = None
    unresolved_avoids: list[str] = []
    if avoid_systems:
        avoid_indices = set()
        for name in avoid_systems:
            idx = universe.resolve_name(name)
            if idx is not None:
                avoid_indices.add(idx)
            else:
                unresolved_avoids.append(name)

    path = _calculate_route(universe, origin_resolved.idx, dest_resolved.idx, mode, avoid_indices)

    if not path:
        from ..errors import RouteNotFoundError

        raise RouteNotFoundError(origin_resolved.canonical_name, dest_resolved.canonical_name)

    result = _build_route_result(
        universe,
        path,
        origin_resolved.canonical_name,
        dest_resolved.canonical_name,
        mode,
        corrections,
    )

    if unresolved_avoids:
        result = RouteResult(
            **{
                **result.model_dump(),
                "warnings": result.warnings
                + [f"Unknown systems in avoid_systems: {', '.join(unresolved_avoids)}"],
            }
        )

    return summarize_route(
        result.model_dump(),
        systems_key="systems",
        threshold=UNIVERSE.ROUTE_SUMMARIZE_THRESHOLD,
        head=UNIVERSE.ROUTE_SHOW_HEAD,
        tail=UNIVERSE.ROUTE_SHOW_TAIL,
    )


async def _systems(systems: list[str] | None) -> dict:
    """Systems action - delegate to tools_systems."""
    if not systems:
        raise InvalidParameterError("systems", systems, "Required for action='systems'")

    from ..models import SystemInfo
    from ..tools import ResolvedSystem, get_universe, resolve_system_name
    from ..utils import build_system_info

    universe = get_universe()
    results: list[SystemInfo | None] = []
    corrections: dict[str, str] = {}

    for name in systems:
        try:
            resolved: ResolvedSystem = resolve_system_name(name)
            results.append(build_system_info(universe, resolved.idx))
            if resolved.was_corrected and resolved.corrected_from:
                corrections[resolved.corrected_from] = resolved.canonical_name
        except Exception:
            results.append(None)

    return wrap_output(
        {
            "systems": [s.model_dump() if s else None for s in results],
            "found": sum(1 for s in results if s is not None),
            "not_found": sum(1 for s in results if s is None),
            "corrections": corrections,
        },
        "systems",
        max_items=UNIVERSE.OUTPUT_MAX_SYSTEMS,
    )


async def _borders(
    origin: str | None,
    limit: int,
    max_jumps: int | None,
) -> dict:
    """Borders action - delegate to tools_borders."""
    if not origin:
        raise InvalidParameterError("origin", origin, "Required for action='borders'")

    from ..tools import collect_corrections, get_universe, resolve_system_name
    from ..tools_borders import MAX_JUMPS, MAX_LIMIT, _find_border_systems

    effective_limit = min(limit, MAX_LIMIT) if limit else 10
    effective_max_jumps = min(max_jumps or 15, MAX_JUMPS)

    if effective_limit < 1:
        raise InvalidParameterError("limit", limit, f"Must be between 1 and {MAX_LIMIT}")
    if effective_max_jumps < 1:
        raise InvalidParameterError("max_jumps", max_jumps, f"Must be between 1 and {MAX_JUMPS}")

    universe = get_universe()
    origin_resolved = resolve_system_name(origin)
    corrections = collect_corrections(origin_resolved)

    borders = _find_border_systems(
        universe, origin_resolved.idx, effective_limit, effective_max_jumps
    )

    return wrap_output(
        {
            "origin": origin_resolved.canonical_name,
            "borders": [b.model_dump() for b in borders],
            "total_found": len(borders),
            "search_radius": effective_max_jumps,
            "corrections": corrections,
        },
        "borders",
        max_items=UNIVERSE.OUTPUT_MAX_SYSTEMS,
    )


async def _search(
    origin: str | None,
    max_jumps: int | None,
    security_min: float | None,
    security_max: float | None,
    region: str | None,
    is_border: bool | None,
    limit: int,
) -> dict:
    """Search action - delegate to tools_search."""
    from ..tools import collect_corrections, get_universe, resolve_system_name
    from ..tools_search import (
        MAX_JUMPS,
        MAX_LIMIT,
        _resolve_region,
        _search_systems,
        _summarize_filters,
    )

    universe = get_universe()

    if limit < 1 or limit > MAX_LIMIT:
        raise InvalidParameterError("limit", limit, f"Must be between 1 and {MAX_LIMIT}")

    if max_jumps is not None and origin is None:
        raise InvalidParameterError(
            "origin", None, "origin is required when max_jumps is specified"
        )

    if max_jumps is not None and (max_jumps < 1 or max_jumps > MAX_JUMPS):
        raise InvalidParameterError("max_jumps", max_jumps, f"Must be between 1 and {MAX_JUMPS}")

    origin_idx: int | None = None
    origin_canonical: str | None = None
    corrections: dict[str, str] = {}
    if origin:
        origin_resolved = resolve_system_name(origin)
        origin_idx = origin_resolved.idx
        origin_canonical = origin_resolved.canonical_name
        corrections = collect_corrections(origin_resolved)

    region_id = None
    region_not_found = False
    if region:
        region_id = _resolve_region(universe, region)
        if region_id is None:
            region_not_found = True

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

    return wrap_output(
        {
            "systems": [r.model_dump() for r in results],
            "total_found": len(results),
            "filters_applied": _summarize_filters(
                origin_canonical or origin, max_jumps, security_min, security_max, region, is_border
            ),
            "corrections": corrections,
        },
        "systems",
        max_items=UNIVERSE.OUTPUT_MAX_SYSTEMS,
    )


async def _loop(
    origin: str | None,
    target_jumps: int,
    min_borders: int,
    max_borders: int | None,
    optimize: str,
    security_filter: str,
    avoid_systems: list[str] | None,
) -> dict:
    """Loop action - delegate to tools_loop."""
    if not origin:
        raise InvalidParameterError("origin", origin, "Required for action='loop'")

    from ..models import VALID_OPTIMIZE_MODES, VALID_SECURITY_FILTERS
    from ..tools import collect_corrections, get_universe, resolve_system_name
    from ..tools_loop import (
        MAX_BORDERS_CAP,
        MAX_BORDERS_LIMIT,
        MAX_TARGET_JUMPS,
        MIN_BORDERS_LIMIT,
        MIN_TARGET_JUMPS,
        _plan_loop,
    )

    universe = get_universe()

    if target_jumps < MIN_TARGET_JUMPS or target_jumps > MAX_TARGET_JUMPS:
        raise InvalidParameterError(
            "target_jumps",
            target_jumps,
            f"Must be between {MIN_TARGET_JUMPS} and {MAX_TARGET_JUMPS}",
        )
    if min_borders < MIN_BORDERS_LIMIT or min_borders > MAX_BORDERS_LIMIT:
        raise InvalidParameterError(
            "min_borders",
            min_borders,
            f"Must be between {MIN_BORDERS_LIMIT} and {MAX_BORDERS_LIMIT}",
        )
    if max_borders is not None and (max_borders < min_borders or max_borders > MAX_BORDERS_CAP):
        raise InvalidParameterError(
            "max_borders",
            max_borders,
            f"Must be between {min_borders} and {MAX_BORDERS_CAP}",
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
    """Analyze action - delegate to tools_analyze."""
    if not systems or len(systems) < 2:
        raise InvalidParameterError(
            "systems", systems, "At least 2 systems required for action='analyze'"
        )

    from ..tools import get_universe
    from ..tools_analyze import _analyze_route, _validate_connectivity

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


async def _nearest(
    origin: str | None,
    is_border: bool | None,
    min_adjacent_lowsec: int | None,
    security_min: float | None,
    security_max: float | None,
    region: str | None,
    limit: int,
    max_jumps: int | None,
) -> dict:
    """Nearest action - delegate to tools_nearest."""
    if not origin:
        raise InvalidParameterError("origin", origin, "Required for action='nearest'")

    from ..tools import collect_corrections, get_universe, resolve_system_name
    from ..tools_nearest import (
        MAX_JUMPS,
        MAX_LIMIT,
        _build_predicate,
        _find_nearest,
        _summarize_predicates,
    )

    universe = get_universe()

    effective_limit = min(limit, MAX_LIMIT) if limit else 5
    effective_max_jumps = min(max_jumps or 30, MAX_JUMPS)

    if effective_limit < 1:
        raise InvalidParameterError("limit", limit, f"Must be between 1 and {MAX_LIMIT}")
    if effective_max_jumps < 1:
        raise InvalidParameterError("max_jumps", max_jumps, f"Must be between 1 and {MAX_JUMPS}")
    if security_min is not None and (security_min < -1.0 or security_min > 1.0):
        raise InvalidParameterError("security_min", security_min, "Must be between -1.0 and 1.0")
    if security_max is not None and (security_max < -1.0 or security_max > 1.0):
        raise InvalidParameterError("security_max", security_max, "Must be between -1.0 and 1.0")
    if min_adjacent_lowsec is not None and min_adjacent_lowsec < 1:
        raise InvalidParameterError(
            "min_adjacent_lowsec", min_adjacent_lowsec, "Must be at least 1"
        )

    origin_resolved = resolve_system_name(origin)
    corrections = collect_corrections(origin_resolved)

    region_id = None
    if region:
        region_id = universe.resolve_region(region)
        if region_id is None:
            return {
                "origin": origin_resolved.canonical_name,
                "systems": [],
                "total_found": 0,
                "search_radius": effective_max_jumps,
                "predicates": _summarize_predicates(
                    is_border, min_adjacent_lowsec, security_min, security_max, region
                ),
                "warning": f"Unknown region: '{region}'",
                "corrections": corrections,
            }

    predicate = _build_predicate(
        universe=universe,
        is_border=is_border,
        min_adjacent_lowsec=min_adjacent_lowsec,
        security_min=security_min,
        security_max=security_max,
        region_id=region_id,
    )

    results = _find_nearest(
        universe=universe,
        origin_idx=origin_resolved.idx,
        predicate=predicate,
        limit=effective_limit,
        max_jumps=effective_max_jumps,
    )

    return wrap_output(
        {
            "origin": origin_resolved.canonical_name,
            "systems": [r.model_dump() for r in results],
            "total_found": len(results),
            "search_radius": effective_max_jumps,
            "predicates": _summarize_predicates(
                is_border, min_adjacent_lowsec, security_min, security_max, region
            ),
            "corrections": corrections,
        },
        "systems",
        max_items=UNIVERSE.OUTPUT_MAX_SYSTEMS,
    )


async def _optimize_waypoints(
    waypoints: list[str] | None,
    origin: str | None,
    return_to_origin: bool,
    security_filter: str,
    avoid_systems: list[str] | None,
) -> dict:
    """Optimize waypoints action - delegate to tools_waypoints."""
    from ..models import VALID_SECURITY_FILTERS
    from ..tools import collect_corrections, get_universe, resolve_system_name
    from ..tools_waypoints import (
        MAX_WAYPOINTS,
        MIN_WAYPOINTS,
    )
    from ..tools_waypoints import (
        _optimize_waypoints as do_optimize,
    )

    if not waypoints:
        raise InvalidParameterError(
            "waypoints", waypoints, "Required for action='optimize_waypoints'"
        )

    universe = get_universe()

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

    if len(waypoint_indices) < MIN_WAYPOINTS:
        raise InvalidParameterError(
            "waypoints",
            waypoint_indices,
            f"Only {len(waypoint_indices)} valid waypoints after resolution, need at least {MIN_WAYPOINTS}",
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

    result = do_optimize(
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
    )

    return wrap_output(result, "route", max_items=UNIVERSE.OUTPUT_MAX_ROUTE)


async def _activity(systems: list[str] | None, include_realtime: bool = False) -> dict:
    """Activity action - delegate to tools_activity with optional realtime data."""
    if not systems:
        raise InvalidParameterError(
            "systems", systems, "At least one system required for action='activity'"
        )

    from ..activity import classify_activity, get_activity_cache
    from ..models import ActivityResult, SystemActivity
    from ..tools import get_universe

    universe = get_universe()
    cache = get_activity_cache()

    # Check if realtime data is available
    realtime_cache = None
    realtime_healthy = False
    if include_realtime:
        try:
            from aria_esi.services.redisq.threat_cache import get_threat_cache

            realtime_cache = get_threat_cache()
            realtime_healthy = realtime_cache.is_healthy()
        except Exception:
            # Silently fall back to hourly-only
            pass

    result_systems: list[SystemActivity] = []
    warnings: list[str] = []

    for name in systems:
        idx = universe.resolve_name(name)
        if idx is None:
            warnings.append(f"Unknown system: {name}")
            continue

        system_id = int(universe.system_ids[idx])
        activity = await cache.get_activity(system_id)

        total_kills = activity.ship_kills + activity.pod_kills
        activity_level = classify_activity(total_kills, "kills")

        system_activity = SystemActivity(
            name=universe.idx_to_name[idx],
            system_id=system_id,
            security=float(universe.security[idx]),
            security_class=universe.security_class(idx),
            ship_kills=activity.ship_kills,
            pod_kills=activity.pod_kills,
            npc_kills=activity.npc_kills,
            ship_jumps=activity.ship_jumps,
            activity_level=activity_level,
        )

        result_systems.append(system_activity)

    # Build base result
    result_dict = ActivityResult(
        systems=result_systems,
        cache_age_seconds=cache.get_kills_cache_age(),
        data_period="last_hour",
        warnings=warnings,
    ).model_dump()

    # Merge realtime data if available
    if include_realtime and realtime_healthy and realtime_cache:
        system_ids = [s.system_id for s in result_systems]
        system_names = {s.system_id: s.name for s in result_systems}

        try:
            realtime_data = realtime_cache.get_activity_for_systems(system_ids, system_names)

            # Add realtime overlay to each system
            for system_dict in result_dict["systems"]:
                system_id = system_dict["system_id"]
                if system_id in realtime_data:
                    system_dict["realtime"] = realtime_data[system_id].to_dict()

            result_dict["realtime_healthy"] = True

        except Exception as e:
            # Non-fatal - just don't include realtime
            logger.debug("Failed to fetch realtime data: %s", e)
            result_dict["realtime_healthy"] = False

    elif include_realtime:
        # Realtime was requested but not available
        result_dict["realtime_healthy"] = False

    return wrap_output(result_dict, "systems", max_items=UNIVERSE.OUTPUT_MAX_SYSTEMS)


async def _hotspots(
    origin: str | None,
    max_jumps: int | None,
    activity_type: str,
    security_min: float | None,
    security_max: float | None,
    limit: int,
) -> dict:
    """Hotspots action - delegate to tools_activity."""
    if not origin:
        raise InvalidParameterError("origin", origin, "Required for action='hotspots'")

    from ..activity import classify_activity, get_activity_cache
    from ..models import HotspotsResult, HotspotSystem
    from ..tools import collect_corrections, get_universe, resolve_system_name

    universe = get_universe()
    cache = get_activity_cache()

    if activity_type not in ("kills", "jumps", "ratting"):
        raise InvalidParameterError(
            "activity_type", activity_type, "Must be one of: kills, jumps, ratting"
        )

    effective_max_jumps = max_jumps or 15
    if effective_max_jumps < 1 or effective_max_jumps > 30:
        raise InvalidParameterError("max_jumps", max_jumps, "Must be between 1 and 30")

    if limit < 1 or limit > 50:
        raise InvalidParameterError("limit", limit, "Must be between 1 and 50")

    origin_resolved = resolve_system_name(origin)
    corrections = collect_corrections(origin_resolved)

    # BFS to find systems within range
    g = universe.graph
    visited = {origin_resolved.idx: 0}
    frontier = [origin_resolved.idx]
    systems_in_range: list[tuple[int, int]] = []

    for distance in range(1, effective_max_jumps + 1):
        next_frontier = []
        for current in frontier:
            for neighbor in g.neighbors(current):
                if neighbor not in visited:
                    visited[neighbor] = distance
                    next_frontier.append(neighbor)
                    systems_in_range.append((neighbor, distance))
        frontier = next_frontier
        if not frontier:
            break

    # Get activity data and filter
    hotspots: list[HotspotSystem] = []
    systems_scanned = 0

    for idx, distance in systems_in_range:
        sec = float(universe.security[idx])

        if security_min is not None and sec < security_min:
            continue
        if security_max is not None and sec > security_max:
            continue

        systems_scanned += 1
        system_id = int(universe.system_ids[idx])
        activity = await cache.get_activity(system_id)

        if activity_type == "kills":
            activity_value = activity.ship_kills + activity.pod_kills
        elif activity_type == "jumps":
            activity_value = activity.ship_jumps
        else:
            activity_value = activity.npc_kills

        if activity_value == 0:
            continue

        activity_level = classify_activity(activity_value, activity_type)

        hotspots.append(
            HotspotSystem(
                name=universe.idx_to_name[idx],
                system_id=system_id,
                security=sec,
                security_class=universe.security_class(idx),
                region=universe.get_region_name(idx),
                jumps_from_origin=distance,
                activity_value=activity_value,
                activity_level=activity_level,
            )
        )

    hotspots.sort(key=lambda h: h.activity_value, reverse=True)
    hotspots = hotspots[:limit]

    result = HotspotsResult(
        origin=origin_resolved.canonical_name,
        activity_type=activity_type,
        hotspots=hotspots,
        search_radius=effective_max_jumps,
        systems_scanned=systems_scanned,
        cache_age_seconds=cache.get_kills_cache_age(),
        corrections=corrections,
    )

    return wrap_output(result.model_dump(), "hotspots", max_items=UNIVERSE.OUTPUT_MAX_HOTSPOTS)


async def _gatecamp_risk(
    route: list[str] | None,
    origin: str | None,
    destination: str | None,
    mode: str,
) -> dict:
    """Gatecamp risk action - delegate to tools_activity with real-time enhancement."""
    from ..activity import get_activity_cache
    from ..errors import RouteNotFoundError, SystemNotFoundError
    from ..models import ChokepointType, GatecampRisk, GatecampRiskResult, RiskLevel
    from ..tools import collect_corrections, get_universe, resolve_system_name
    from ..tools_route import _calculate_route

    universe = get_universe()
    cache = get_activity_cache()

    # Try to get real-time threat cache for enhanced detection
    threat_cache = None
    try:
        from aria_esi.services.redisq.threat_cache import get_threat_cache

        threat_cache = get_threat_cache()
        if not threat_cache.is_healthy():
            threat_cache = None
    except Exception:
        pass  # Silently fall back to hourly-only

    corrections: dict[str, str] = {}
    if route:
        indices: list[int] = []
        for name in route:
            idx = universe.resolve_name(name)
            if idx is None:
                raise SystemNotFoundError(name, [])
            indices.append(idx)
    elif origin and destination:
        origin_resolved = resolve_system_name(origin)
        dest_resolved = resolve_system_name(destination)
        corrections = collect_corrections(origin_resolved, dest_resolved)

        indices = _calculate_route(universe, origin_resolved.idx, dest_resolved.idx, mode)
        if not indices:
            raise RouteNotFoundError(origin_resolved.canonical_name, dest_resolved.canonical_name)
    else:
        raise InvalidParameterError(
            "route",
            None,
            "Must provide either 'route' or both 'origin' and 'destination'",
        )

    if len(indices) < 2:
        raise InvalidParameterError("route", route, "Route must have at least 2 systems")

    # Find chokepoints and analyze risk
    chokepoints: list[GatecampRisk] = []
    high_risk_systems: list[str] = []
    realtime_camps_detected = 0

    for i in range(1, len(indices)):
        prev_idx = indices[i - 1]
        curr_idx = indices[i]

        prev_class = universe.security_class(prev_idx)
        curr_class = universe.security_class(curr_idx)

        chokepoint_type: ChokepointType | None = None

        if prev_class == "HIGH" and curr_class in ("LOW", "NULL"):
            chokepoint_type = "lowsec_entry"
            chokepoint_idx = curr_idx
        elif prev_class in ("LOW", "NULL") and curr_class == "HIGH":
            chokepoint_type = "lowsec_exit"
            chokepoint_idx = prev_idx
        else:
            if curr_class in ("LOW", "NULL"):
                neighbors = list(universe.graph.neighbors(curr_idx))
                if len(neighbors) <= 2:
                    chokepoint_type = "pipe"
                    chokepoint_idx = curr_idx
                elif len(neighbors) >= 4:
                    chokepoint_type = "hub"
                    chokepoint_idx = curr_idx

        if chokepoint_type:
            system_id = int(universe.system_ids[chokepoint_idx])
            system_name = universe.idx_to_name[chokepoint_idx]
            activity = await cache.get_activity(system_id)
            ship_kills = activity.ship_kills
            pod_kills = activity.pod_kills
            total_kills = ship_kills + pod_kills

            # Check real-time gatecamp detection if available
            realtime_camp = None
            if threat_cache:
                try:
                    realtime_camp = threat_cache.get_gatecamp_status(system_id, system_name)
                except Exception:
                    pass

            # Determine risk level - real-time detection takes precedence
            risk_level: RiskLevel
            if realtime_camp and realtime_camp.confidence in ("high", "medium"):
                # Real-time camp detected - escalate risk
                realtime_camps_detected += 1
                if realtime_camp.confidence == "high":
                    risk_level = "extreme"
                    warning = f"ACTIVE CAMP ({realtime_camp.kill_count} kills/{realtime_camp.window_minutes}min)"
                else:
                    risk_level = "high"
                    warning = f"Likely active camp ({realtime_camp.kill_count} kills/{realtime_camp.window_minutes}min)"
            elif total_kills >= 20:
                risk_level = "extreme"
                warning = "Active gatecamp highly likely"
            elif total_kills >= 10:
                risk_level = "high"
                warning = "Active gatecamp likely"
            elif total_kills >= 5:
                risk_level = "medium"
                warning = "Some PvP activity detected"
            else:
                risk_level = "low"
                warning = None

            chokepoints.append(
                GatecampRisk(
                    system=system_name,
                    system_id=system_id,
                    security=float(universe.security[chokepoint_idx]),
                    chokepoint_type=chokepoint_type,
                    recent_kills=ship_kills,
                    recent_pods=pod_kills,
                    risk_level=risk_level,
                    warning=warning,
                )
            )

            if risk_level in ("high", "extreme"):
                high_risk_systems.append(system_name)

    # Determine overall risk
    overall_risk: RiskLevel
    if any(c.risk_level == "extreme" for c in chokepoints):
        overall_risk = "extreme"
    elif any(c.risk_level == "high" for c in chokepoints):
        overall_risk = "high"
    elif any(c.risk_level == "medium" for c in chokepoints):
        overall_risk = "medium"
    else:
        overall_risk = "low"

    # Generate recommendation
    if overall_risk == "extreme":
        recommendation = (
            f"Route has {len(high_risk_systems)} extreme-risk chokepoints. "
            "Consider alternate route, scouting, or waiting for activity to die down."
        )
    elif overall_risk == "high":
        recommendation = (
            f"Route has {len(high_risk_systems)} high-risk chokepoints. "
            "Scout ahead or use alternate route. Pass high_risk_systems to universe_route avoid_systems."
        )
    elif overall_risk == "medium":
        recommendation = "Moderate risk. Stay alert at chokepoints and consider using a scout."
    else:
        recommendation = "Route appears relatively safe. Standard travel precautions apply."

    origin_name = universe.idx_to_name[indices[0]]
    dest_name = universe.idx_to_name[indices[-1]]

    result = GatecampRiskResult(
        origin=origin_name,
        destination=dest_name,
        total_jumps=len(indices) - 1,
        overall_risk=overall_risk,
        chokepoints=chokepoints,
        high_risk_systems=high_risk_systems,
        recommendation=recommendation,
        cache_age_seconds=cache.get_kills_cache_age(),
        corrections=corrections,
    )

    result_dict = result.model_dump()

    # Add real-time metadata
    if threat_cache:
        result_dict["realtime_healthy"] = True
        result_dict["realtime_camps_detected"] = realtime_camps_detected
    else:
        result_dict["realtime_healthy"] = False

    return wrap_output(result_dict, "chokepoints", max_items=UNIVERSE.OUTPUT_MAX_CHOKEPOINTS)


async def _fw_frontlines(faction: str | None) -> dict:
    """FW frontlines action - delegate to tools_activity."""
    from ..activity import get_activity_cache, get_faction_id, get_faction_name
    from ..models import FWFrontlinesResult, FWSystem
    from ..tools import get_universe

    universe = get_universe()
    cache = get_activity_cache()

    fw_data = await cache.get_all_fw()

    filter_faction_id: int | None = None
    if faction:
        filter_faction_id = get_faction_id(faction)
        if filter_faction_id is None:
            raise InvalidParameterError(
                "faction", faction, "Must be one of: caldari, gallente, amarr, minmatar"
            )

    contested: list[FWSystem] = []
    vulnerable: list[FWSystem] = []
    stable: list[FWSystem] = []

    for system_id, fw_system in fw_data.items():
        if filter_faction_id:
            if (
                fw_system.owner_faction_id != filter_faction_id
                and fw_system.occupier_faction_id != filter_faction_id
            ):
                continue

        idx = universe.id_to_idx.get(system_id)
        if idx is None:
            continue

        if fw_system.victory_points_threshold > 0:
            contested_pct = fw_system.victory_points / fw_system.victory_points_threshold * 100
        else:
            contested_pct = 0.0

        activity = await cache.get_activity(system_id)
        recent_kills = activity.ship_kills + activity.pod_kills

        fw_result = FWSystem(
            name=universe.idx_to_name[idx],
            system_id=system_id,
            security=float(universe.security[idx]),
            region=universe.get_region_name(idx),
            owner_faction=get_faction_name(fw_system.owner_faction_id),
            occupier_faction=get_faction_name(fw_system.occupier_faction_id),
            contested=fw_system.contested,
            contested_percentage=min(contested_pct, 100.0),
            victory_points=fw_system.victory_points,
            victory_points_threshold=fw_system.victory_points_threshold,
            recent_kills=recent_kills if recent_kills > 0 else None,
        )

        if fw_system.contested == "vulnerable":
            vulnerable.append(fw_result)
        elif fw_system.contested == "contested":
            contested.append(fw_result)
        else:
            stable.append(fw_result)

    contested.sort(key=lambda s: s.contested_percentage, reverse=True)
    vulnerable.sort(key=lambda s: s.contested_percentage, reverse=True)

    result = FWFrontlinesResult(
        faction_filter=faction,
        contested=contested,
        vulnerable=vulnerable,
        stable=stable,
        summary={
            "total_systems": len(contested) + len(vulnerable) + len(stable),
            "contested_count": len(contested),
            "vulnerable_count": len(vulnerable),
            "stable_count": len(stable),
        },
        cache_age_seconds=cache.get_kills_cache_age(),
    )

    return wrap_output_multi(
        result.model_dump(),
        [
            ("contested", UNIVERSE.OUTPUT_MAX_FW_SYSTEMS),
            ("vulnerable", UNIVERSE.OUTPUT_MAX_FW_SYSTEMS),
            ("stable", UNIVERSE.OUTPUT_MAX_FW_SYSTEMS),
        ],
    )


async def _local_area(
    origin: str | None,
    max_jumps: int | None,
    include_realtime: bool,
    hotspot_threshold: int,
    quiet_threshold: int,
    ratting_threshold: int,
) -> dict:
    """
    Local area action - consolidated intel for orientation in unknown space.

    Provides:
    - Threat summary (total kills, active camps)
    - Hotspots (high PvP activity systems)
    - Quiet zones (low/zero activity for stealth ops)
    - Ratting banks (high NPC kills indicating targets)
    - Escape routes (nearest low-sec, high-sec, NPC stations)
    - Security borders (transition points)
    """
    if not origin:
        raise InvalidParameterError("origin", origin, "Required for action='local_area'")

    from collections import deque

    from ..activity import classify_activity, get_activity_cache
    from ..models import (
        LocalAreaResult,
        LocalSystemActivity,
        SecurityBorder,
        ThreatSummary,
    )
    from ..tools import collect_corrections, get_universe, resolve_system_name

    universe = get_universe()
    cache = get_activity_cache()

    # Validate parameters
    effective_max_jumps = max_jumps or 10
    if effective_max_jumps < 1 or effective_max_jumps > 30:
        raise InvalidParameterError("max_jumps", max_jumps, "Must be between 1 and 30")

    origin_resolved = resolve_system_name(origin)
    corrections = collect_corrections(origin_resolved)

    # Get origin info
    origin_idx = origin_resolved.idx
    origin_sec = float(universe.security[origin_idx])
    origin_sec_class = universe.security_class(origin_idx)
    origin_region = universe.get_region_name(origin_idx)
    origin_constellation = universe.get_constellation_name(origin_idx)

    # BFS to find all systems within range and track distances
    g = universe.graph
    visited: dict[int, int] = {origin_idx: 0}
    queue: deque[tuple[int, int]] = deque([(origin_idx, 0)])
    systems_in_range: list[tuple[int, int]] = []  # (idx, distance)

    while queue:
        current_idx, distance = queue.popleft()
        if distance > 0:
            systems_in_range.append((current_idx, distance))

        if distance < effective_max_jumps:
            for neighbor in g.neighbors(current_idx):
                if neighbor not in visited:
                    visited[neighbor] = distance + 1
                    queue.append((neighbor, distance + 1))

    # Get all activity data
    all_activity = await cache.get_all_activity()

    # Try to get real-time threat cache for gatecamp detection
    realtime_healthy = False
    active_camps: list[str] = []
    if include_realtime:
        try:
            from ...services.redisq.threat_cache import get_threat_cache

            threat_cache = get_threat_cache()
            if threat_cache and threat_cache.is_healthy():
                realtime_healthy = True
                # Get gatecamp data for systems in range
                system_ids_in_range = [int(universe.system_ids[idx]) for idx, _ in systems_in_range]
                system_names = {
                    int(universe.system_ids[idx]): universe.idx_to_name[idx]
                    for idx, _ in systems_in_range
                }
                realtime_data = threat_cache.get_activity_for_systems(
                    system_ids_in_range, system_names
                )
                for system_id, activity_summary in realtime_data.items():
                    if activity_summary.gatecamp:
                        camp = activity_summary.gatecamp
                        active_camps.append(camp.system_name or str(system_id))
        except Exception:
            # Real-time not available, continue without it
            pass

    # Classify systems
    hotspots: list[LocalSystemActivity] = []
    quiet_zones: list[LocalSystemActivity] = []
    ratting_banks: list[LocalSystemActivity] = []
    borders: list[SecurityBorder] = []

    total_kills = 0
    total_pods = 0
    hotspot_count = 0

    for idx, distance in systems_in_range:
        system_id = int(universe.system_ids[idx])
        sec = float(universe.security[idx])
        sec_class = universe.security_class(idx)
        region = universe.get_region_name(idx)

        activity = all_activity.get(system_id)
        ship_kills = activity.ship_kills if activity else 0
        pod_kills = activity.pod_kills if activity else 0
        npc_kills = activity.npc_kills if activity else 0
        ship_jumps = activity.ship_jumps if activity else 0

        pvp_kills = ship_kills + pod_kills
        total_kills += ship_kills
        total_pods += pod_kills

        activity_level = classify_activity(pvp_kills, "kills")

        # Determine reason/classification
        reason = None
        system_name = universe.idx_to_name[idx]

        if system_name in active_camps:
            reason = "gatecamp"
            # Note: don't increment hotspot_count here - it's tracked via active_camps
            # and will be counted when added to hotspots list below if kills meet threshold

        # Build system activity record
        system_activity = LocalSystemActivity(
            system=system_name,
            system_id=system_id,
            security=sec,
            security_class=sec_class,
            region=region,
            jumps=distance,
            ship_kills=ship_kills,
            pod_kills=pod_kills,
            npc_kills=npc_kills,
            ship_jumps=ship_jumps,
            activity_level=activity_level,
            reason=reason,
        )

        # Classify into categories
        if pvp_kills >= hotspot_threshold:
            if reason is None:
                system_activity = LocalSystemActivity(
                    **{**system_activity.model_dump(), "reason": "high activity"}
                )
            hotspots.append(system_activity)
            hotspot_count += 1

        if pvp_kills <= quiet_threshold:
            quiet_zones.append(system_activity)

        if npc_kills >= ratting_threshold:
            ratting_activity = LocalSystemActivity(
                **{**system_activity.model_dump(), "reason": "ratting bank"}
            )
            ratting_banks.append(ratting_activity)

        # Check for security borders
        for neighbor_idx in g.neighbors(idx):
            if neighbor_idx in visited:
                neighbor_sec = float(universe.security[neighbor_idx])
                border_type = _classify_border(sec, neighbor_sec)
                if border_type:
                    borders.append(
                        SecurityBorder(
                            system=system_name,
                            system_id=system_id,
                            security=sec,
                            jumps=distance,
                            border_type=border_type,
                            adjacent_system=universe.idx_to_name[neighbor_idx],
                            adjacent_security=neighbor_sec,
                        )
                    )

    # Sort results
    hotspots.sort(key=lambda s: (s.ship_kills + s.pod_kills), reverse=True)
    quiet_zones.sort(key=lambda s: s.jumps)  # Nearest first
    ratting_banks.sort(key=lambda s: s.npc_kills, reverse=True)
    borders.sort(key=lambda s: s.jumps)

    # Limit results
    hotspots = hotspots[:10]
    quiet_zones = quiet_zones[:10]
    ratting_banks = ratting_banks[:10]
    borders = borders[:10]

    # Calculate escape routes
    escape_routes = await _find_escape_routes(
        universe, origin_idx, origin_sec, visited, effective_max_jumps
    )

    # Determine threat level
    threat_level = _classify_threat_level(total_kills, hotspot_count, len(active_camps))

    threat_summary = ThreatSummary(
        level=threat_level,
        total_kills=total_kills,
        total_pods=total_pods,
        active_camps=active_camps,
        hotspot_count=hotspot_count,
    )

    result = LocalAreaResult(
        origin=origin_resolved.canonical_name,
        origin_id=int(universe.system_ids[origin_idx]),
        security=origin_sec,
        security_class=origin_sec_class,
        region=origin_region,
        constellation=origin_constellation,
        threat_summary=threat_summary,
        hotspots=hotspots,
        quiet_zones=quiet_zones,
        ratting_banks=ratting_banks,
        escape_routes=escape_routes,
        borders=borders,
        systems_scanned=len(systems_in_range),
        search_radius=effective_max_jumps,
        cache_age_seconds=cache.get_kills_cache_age(),
        realtime_healthy=realtime_healthy,
        corrections=corrections,
    )

    return wrap_output_multi(
        result.model_dump(),
        [
            ("hotspots", 10),
            ("quiet_zones", 10),
            ("ratting_banks", 10),
            ("escape_routes", 5),
            ("borders", 10),
        ],
    )


def _classify_border(sec: float, neighbor_sec: float) -> BorderType | None:
    """Classify the type of security border between two systems."""

    # Determine security classes
    def sec_class(s: float) -> str:
        if s >= 0.45:
            return "high"
        elif s > 0.0:
            return "low"
        else:
            return "null"

    from_class = sec_class(sec)
    to_class = sec_class(neighbor_sec)

    if from_class == to_class:
        return None

    border_map: dict[tuple[str, str], BorderType] = {
        ("null", "low"): "null_to_low",
        ("low", "high"): "low_to_high",
        ("high", "low"): "high_to_low",
        ("low", "null"): "low_to_null",
    }

    return border_map.get((from_class, to_class))


def _classify_threat_level(total_kills: int, hotspot_count: int, camp_count: int) -> ThreatLevel:
    """Classify overall threat level for the local area."""
    # Active camps are high priority
    if camp_count >= 3:
        return "EXTREME"
    if camp_count >= 1:
        return "HIGH"

    # High activity
    if total_kills >= 50 or hotspot_count >= 5:
        return "HIGH"
    if total_kills >= 20 or hotspot_count >= 2:
        return "MEDIUM"

    return "LOW"


async def _find_escape_routes(
    universe: UniverseGraph,
    origin_idx: int,
    origin_sec: float,
    visited: dict[int, int],
    max_jumps: int,
) -> list[EscapeRoute]:
    """Find escape routes to safer space."""
    from ..models import EscapeRoute

    escape_routes: list[EscapeRoute] = []

    # Determine what we're looking for based on origin security
    origin_class = "null" if origin_sec <= 0.0 else ("low" if origin_sec < 0.45 else "high")

    # Find nearest low-sec (if in null)
    if origin_class == "null":
        for idx, distance in sorted(visited.items(), key=lambda x: x[1]):
            if idx == origin_idx:
                continue
            sec = float(universe.security[idx])
            if 0.0 < sec < 0.45:
                escape_routes.append(
                    EscapeRoute(
                        destination=universe.idx_to_name[idx],
                        destination_type="lowsec",
                        jumps=distance,
                        via_system=None,  # Could trace path if needed
                        route_security="lowsec",
                    )
                )
                break

    # Find nearest high-sec (if in low or null)
    if origin_class in ("null", "low"):
        for idx, distance in sorted(visited.items(), key=lambda x: x[1]):
            if idx == origin_idx:
                continue
            sec = float(universe.security[idx])
            if sec >= 0.45:
                escape_routes.append(
                    EscapeRoute(
                        destination=universe.idx_to_name[idx],
                        destination_type="highsec",
                        jumps=distance,
                        via_system=None,
                        route_security="mixed" if origin_class == "null" else "lowsec",
                    )
                )
                break

    # Note: NPC station lookup would require SDE enhancement
    # For now, we identify security transitions which often have stations

    return escape_routes
