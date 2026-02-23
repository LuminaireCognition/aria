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
- local_area: Consolidated local intel for orientation
- territory_analysis: Sovereignty territory analysis for coalitions/alliances
"""

from __future__ import annotations

import logging
from collections import deque
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal

from ...services.navigation import (
    VALID_MODES,
)

# Re-exports for test compatibility
from ...services.navigation import compute_safe_weights as _compute_safe_weights  # noqa: F401
from ...services.navigation import (
    compute_security_summary as _svc_compute_security_summary,
)
from ...services.navigation import compute_unsafe_weights as _compute_unsafe_weights  # noqa: F401
from ...services.navigation import (
    generate_warnings as _svc_generate_warnings,
)
from ..activity import classify_activity, get_activity_cache, get_faction_id, get_faction_name
from ..context import log_context, summarize_route, wrap_output, wrap_output_multi
from ..context_policy import UNIVERSE
from ..errors import (
    InsufficientBordersError,
    InvalidParameterError,
    RouteNotFoundError,
    SystemNotFoundError,
)
from ..models import (
    VALID_OPTIMIZE_MODES,
    VALID_SECURITY_FILTERS,
    ActivityResult,
    BorderSystem,
    CacheLayerStatus,
    CacheStatusResult,
    ChokepointType,
    DangerZone,
    FWFrontlinesResult,
    FWSystem,
    GatecampRisk,
    GatecampRiskResult,
    HotspotsResult,
    HotspotSystem,
    LoopResult,
    OptimizedWaypointResult,
    RiskLevel,
    RouteAnalysis,
    RouteResult,
    SecuritySummary,
    SystemActivity,
    SystemInfo,
    SystemSearchResult,
    WaypointInfo,
)
from ..policy import check_capability
from ..tools import ResolvedSystem, collect_corrections, get_universe, resolve_system_name
from ..utils import DistanceMatrix, build_system_info
from ..validation import add_validation_warnings, validate_action_params

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from aria_esi.universe.graph import UniverseGraph

    from ..activity import ActivityData
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
    "territory_analysis",
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
    "territory_analysis",
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
        # territory_analysis params
        coalition: str | None = None,
        alliance_id: int | None = None,
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
        - territory_analysis: Analyze sovereignty territory for coalition/alliance

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

            Territory analysis params (action="territory_analysis"):
                coalition: Coalition ID or alias (e.g., "imperium", "goons")
                alliance_id: Alliance ID to analyze

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
            universe(action="territory_analysis", coalition="imperium")
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
                "coalition": coalition,
                "alliance_id": alliance_id,
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
                    origin, max_jumps, security_min, security_max, region, is_border, limit,
                    coalition,
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

            case "territory_analysis":
                result = await _territory_analysis(coalition, alliance_id)

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
    """Route action."""
    if not origin:
        raise InvalidParameterError("origin", origin, "Required for action='route'")
    if not destination:
        raise InvalidParameterError("destination", destination, "Required for action='route'")

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

    # Add FW warzone warnings
    fw_warnings = await _generate_fw_route_warnings(universe, path)
    if fw_warnings:
        result = RouteResult(
            **{
                **result.model_dump(),
                "warnings": result.warnings + fw_warnings,
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
    """Systems action."""
    if not systems:
        raise InvalidParameterError("systems", systems, "Required for action='systems'")

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
    """Borders action."""
    if not origin:
        raise InvalidParameterError("origin", origin, "Required for action='borders'")

    effective_limit = min(limit, UNIVERSE.BORDERS_MAX_LIMIT) if limit else 10
    effective_max_jumps = min(max_jumps or 15, UNIVERSE.BORDERS_MAX_JUMPS)

    if effective_limit < 1:
        raise InvalidParameterError(
            "limit", limit, f"Must be between 1 and {UNIVERSE.BORDERS_MAX_LIMIT}"
        )
    if effective_max_jumps < 1:
        raise InvalidParameterError(
            "max_jumps", max_jumps, f"Must be between 1 and {UNIVERSE.BORDERS_MAX_JUMPS}"
        )

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
    coalition: str | None = None,
) -> dict:
    """Search action."""
    universe = get_universe()

    if limit < 1 or limit > UNIVERSE.SEARCH_MAX_LIMIT:
        raise InvalidParameterError(
            "limit", limit, f"Must be between 1 and {UNIVERSE.SEARCH_MAX_LIMIT}"
        )

    if max_jumps is not None and origin is None:
        raise InvalidParameterError(
            "origin", None, "origin is required when max_jumps is specified"
        )

    if max_jumps is not None and (max_jumps < 1 or max_jumps > UNIVERSE.SEARCH_MAX_JUMPS):
        raise InvalidParameterError(
            "max_jumps", max_jumps, f"Must be between 1 and {UNIVERSE.SEARCH_MAX_JUMPS}"
        )

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
                coalition,
            ),
            "warning": f"Unknown region: '{region}'",
            "corrections": corrections,
        }

    # Resolve coalition filter to system IDs
    coalition_system_ids: set[int] | None = None
    coalition_warning: str | None = None
    if coalition:
        from aria_esi.services.sovereignty import get_systems_by_coalition

        coalition_systems = get_systems_by_coalition(coalition)
        if coalition_systems:
            coalition_system_ids = set(coalition_systems)
        else:
            coalition_warning = f"Unknown or empty coalition: '{coalition}'"

    if coalition_warning and coalition_system_ids is None:
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
                coalition,
            ),
            "warning": coalition_warning,
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
        coalition_system_ids=coalition_system_ids,
    )

    return wrap_output(
        {
            "systems": [r.model_dump() for r in results],
            "total_found": len(results),
            "filters_applied": _summarize_filters(
                origin_canonical or origin,
                max_jumps,
                security_min,
                security_max,
                region,
                is_border,
                coalition,
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
    """Nearest action."""
    if not origin:
        raise InvalidParameterError("origin", origin, "Required for action='nearest'")

    universe = get_universe()

    effective_limit = min(limit, UNIVERSE.NEAREST_MAX_LIMIT) if limit else 5
    effective_max_jumps = min(max_jumps or 30, UNIVERSE.NEAREST_MAX_JUMPS)

    if effective_limit < 1:
        raise InvalidParameterError(
            "limit", limit, f"Must be between 1 and {UNIVERSE.NEAREST_MAX_LIMIT}"
        )
    if effective_max_jumps < 1:
        raise InvalidParameterError(
            "max_jumps", max_jumps, f"Must be between 1 and {UNIVERSE.NEAREST_MAX_JUMPS}"
        )
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
    )

    return wrap_output(result, "route", max_items=UNIVERSE.OUTPUT_MAX_ROUTE)


async def _activity(systems: list[str] | None, include_realtime: bool = False) -> dict:
    """Activity action with optional realtime data."""
    if not systems:
        raise InvalidParameterError(
            "systems", systems, "At least one system required for action='activity'"
        )

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
    """Hotspots action."""
    if not origin:
        raise InvalidParameterError("origin", origin, "Required for action='hotspots'")

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
    """Gatecamp risk action with real-time enhancement."""
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
    """FW frontlines action."""
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

    from ..models import (
        FWLocalStatus,
        LocalAreaResult,
        LocalSystemActivity,
        SecurityBorder,
        ThreatSummary,
    )

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

    # Collect FW system data
    fw_systems_list: list[FWLocalStatus] = []
    fw_data = await cache.get_all_fw()
    if fw_data:
        all_local_ids = [(origin_idx, 0)] + systems_in_range
        for idx, distance in all_local_ids:
            system_id = int(universe.system_ids[idx])
            fw_entry = fw_data.get(system_id)
            if fw_entry is None:
                continue
            if fw_entry.victory_points_threshold > 0:
                contested_pct = fw_entry.victory_points / fw_entry.victory_points_threshold * 100
            else:
                contested_pct = 0.0
            fw_systems_list.append(
                FWLocalStatus(
                    system=universe.idx_to_name[idx],
                    system_id=system_id,
                    security=float(universe.security[idx]),
                    jumps=distance,
                    owner_faction=get_faction_name(fw_entry.owner_faction_id),
                    occupier_faction=get_faction_name(fw_entry.occupier_faction_id),
                    contested=fw_entry.contested,
                    contested_percentage=min(contested_pct, 100.0),
                )
            )
        # Sort: vulnerable first, then contested, then uncontested; within each by distance
        status_order = {"vulnerable": 0, "contested": 1, "uncontested": 2}
        fw_systems_list.sort(key=lambda s: (status_order.get(s.contested, 3), s.jumps))
        fw_systems_list = fw_systems_list[:10]

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
        fw_systems=fw_systems_list,
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
            ("fw_systems", 10),
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


async def _territory_analysis(
    coalition: str | None,
    alliance_id: int | None,
) -> dict:
    """
    Territory analysis action - analyze sovereignty for a coalition or alliance.

    Returns territory statistics including:
    - System count
    - Region breakdown
    - Constellation count
    """
    if not coalition and not alliance_id:
        raise InvalidParameterError(
            "coalition",
            None,
            "Must specify either 'coalition' or 'alliance_id' for action='territory_analysis'",
        )

    from aria_esi.services.sovereignty import analyze_territory

    result = analyze_territory(
        coalition_id=coalition,
        alliance_id=alliance_id,
    )

    return result


# =============================================================================
# Route Implementation Functions (from tools_route.py)
# =============================================================================


def _calculate_route(
    universe: UniverseGraph,
    origin_idx: int,
    dest_idx: int,
    mode: str,
    avoid_systems: set[int] | None = None,
) -> list[int]:
    """
    Calculate route using NavigationService.

    Args:
        universe: UniverseGraph for pathfinding
        origin_idx: Starting vertex index
        dest_idx: Destination vertex index
        mode: Routing mode (shortest, safe, unsafe)
        avoid_systems: Set of vertex indices to avoid

    Returns:
        List of vertex indices from origin to destination
    """
    from ...services.navigation import NavigationService

    service = NavigationService(universe)
    return service.calculate_route(origin_idx, dest_idx, mode, avoid_systems)  # type: ignore[arg-type]


async def _generate_fw_route_warnings(
    universe: UniverseGraph, path: list[int]
) -> list[str]:
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
        warnings.append(
            f"Contested FW system(s): {', '.join(contested_systems)}"
        )

    return warnings


def _build_route_result(
    universe: UniverseGraph,
    path: list[int],
    origin: str,
    destination: str,
    mode: str,
    corrections: dict[str, str] | None = None,
) -> RouteResult:
    """Build complete RouteResult from path."""
    systems = [build_system_info(universe, idx) for idx in path]
    summary = _svc_compute_security_summary(universe, path)
    warnings = _svc_generate_warnings(universe, path, mode)

    return RouteResult(
        origin=origin,
        destination=destination,
        mode=mode,  # type: ignore[arg-type]
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


# =============================================================================
# Borders Implementation Functions (from tools_borders.py)
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
# Search Implementation Functions (from tools_search.py)
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
        candidates = {universe.id_to_idx[sid] for sid in coalition_system_ids if sid in universe.id_to_idx}
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
# Loop Implementation Functions (from tools_loop.py)
# =============================================================================

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
    from ...services.loop_planning import LoopPlanningService
    from ...services.loop_planning.errors import (
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
    from ...services.loop_planning import find_borders_with_distance

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
    from ...services.loop_planning import select_borders_coverage

    return select_borders_coverage(candidates, matrix)


def _nearest_neighbor_tsp_matrix(
    start: int,
    waypoints: list[int],
    matrix: DistanceMatrix,
) -> list[int]:
    """Backwards-compatible alias. See services.loop_planning.nearest_neighbor_tsp."""
    from ...services.loop_planning import nearest_neighbor_tsp

    return nearest_neighbor_tsp(start, waypoints, matrix)


def _expand_tour_matrix(tour: list[int], matrix: DistanceMatrix) -> list[int]:
    """Backwards-compatible alias. See services.loop_planning.expand_tour."""
    from ...services.loop_planning import expand_tour

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


# =============================================================================
# Analyze Implementation Functions (from tools_analyze.py)
# =============================================================================


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
    security_summary = _compute_security_summary(universe, indices)
    chokepoints = _find_chokepoints(universe, indices)
    danger_zones = _find_danger_zones(universe, indices)

    return RouteAnalysis(
        systems=systems,
        security_summary=security_summary,
        chokepoints=chokepoints,
        danger_zones=danger_zones,
    )


def _compute_security_summary(
    universe: UniverseGraph,
    indices: list[int],
) -> SecuritySummary:
    """Compute security breakdown for route (analyze version)."""
    highsec = 0
    lowsec = 0
    nullsec = 0
    lowest_sec = 1.0
    lowest_system = ""

    for idx in indices:
        sec = float(universe.security[idx])
        sec_class = universe.security_class(idx)

        if sec_class == "HIGH":
            highsec += 1
        elif sec_class == "LOW":
            lowsec += 1
        else:
            nullsec += 1

        if sec < lowest_sec:
            lowest_sec = sec
            lowest_system = universe.idx_to_name[idx]

    return SecuritySummary(
        total_jumps=len(indices) - 1,
        highsec_jumps=highsec,
        lowsec_jumps=lowsec,
        nullsec_jumps=nullsec,
        lowest_security=lowest_sec,
        lowest_security_system=lowest_system,
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

        if prev_class == "HIGH" and curr_class in ("LOW", "NULL"):
            chokepoints.append(build_system_info(universe, curr_idx))
        elif prev_class in ("LOW", "NULL") and curr_class == "HIGH":
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


# =============================================================================
# Nearest Implementation Functions (from tools_nearest.py)
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


# =============================================================================
# Waypoints Implementation Functions (from tools_waypoints.py)
# =============================================================================


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


# =============================================================================
# Register Functions (for test compatibility)
# =============================================================================


def register_route_tools(server: FastMCP, universe: UniverseGraph) -> None:
    """Register route tools with MCP server (for test compatibility)."""

    @server.tool()
    async def universe_route(
        origin: str,
        destination: str,
        mode: str = "shortest",
        avoid_systems: list[str] | None = None,
    ) -> dict:
        """Calculate optimal route between two systems."""
        universe_graph = get_universe()

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
                idx = universe_graph.resolve_name(name)
                if idx is not None:
                    avoid_indices.add(idx)
                else:
                    unresolved_avoids.append(name)

        path = _calculate_route(
            universe, origin_resolved.idx, dest_resolved.idx, mode, avoid_indices
        )

        if not path:
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

        return result.model_dump()


def register_systems_tools(server: FastMCP, universe: UniverseGraph) -> None:
    """Register system lookup tools with MCP server (for test compatibility)."""

    @server.tool()
    async def universe_systems(systems: list[str]) -> dict:
        """Get detailed information for one or more systems."""
        universe_graph = get_universe()
        results: list[SystemInfo | None] = []
        corrections: dict[str, str] = {}

        for name in systems:
            try:
                resolved: ResolvedSystem = resolve_system_name(name)
                results.append(build_system_info(universe_graph, resolved.idx))
                if resolved.was_corrected and resolved.corrected_from:
                    corrections[resolved.corrected_from] = resolved.canonical_name
            except Exception:
                results.append(None)

        return {
            "systems": [s.model_dump() if s else None for s in results],
            "found": sum(1 for s in results if s is not None),
            "not_found": sum(1 for s in results if s is None),
            "corrections": corrections,
        }


def register_borders_tools(server: FastMCP, universe: UniverseGraph) -> None:
    """Register border discovery tools with MCP server (for test compatibility)."""

    @server.tool()
    async def universe_borders(
        origin: str,
        limit: int = 10,
        max_jumps: int = 15,
    ) -> dict:
        """Find high-sec systems that border low-sec space."""
        if limit < 1 or limit > UNIVERSE.BORDERS_MAX_LIMIT:
            raise InvalidParameterError(
                "limit", limit, f"Must be between 1 and {UNIVERSE.BORDERS_MAX_LIMIT}"
            )
        if max_jumps < 1 or max_jumps > UNIVERSE.BORDERS_MAX_JUMPS:
            raise InvalidParameterError(
                "max_jumps", max_jumps, f"Must be between 1 and {UNIVERSE.BORDERS_MAX_JUMPS}"
            )

        universe_graph = get_universe()
        origin_resolved = resolve_system_name(origin)
        corrections = collect_corrections(origin_resolved)

        borders = _find_border_systems(universe_graph, origin_resolved.idx, limit, max_jumps)

        return {
            "origin": origin_resolved.canonical_name,
            "borders": [b.model_dump() for b in borders],
            "total_found": len(borders),
            "search_radius": max_jumps,
            "corrections": corrections,
        }


def register_search_tools(server: FastMCP, universe: UniverseGraph) -> None:
    """Register system search tools with MCP server (for test compatibility)."""

    @server.tool()
    async def universe_search(
        origin: str | None = None,
        max_jumps: int | None = None,
        security_min: float | None = None,
        security_max: float | None = None,
        region: str | None = None,
        is_border: bool | None = None,
        limit: int = 20,
    ) -> dict:
        """Search for systems matching criteria."""
        universe_graph = get_universe()

        if limit < 1 or limit > UNIVERSE.SEARCH_MAX_LIMIT:
            raise InvalidParameterError(
                "limit", limit, f"Must be between 1 and {UNIVERSE.SEARCH_MAX_LIMIT}"
            )
        if max_jumps is not None and origin is None:
            raise InvalidParameterError(
                "origin", None, "origin is required when max_jumps is specified"
            )
        if max_jumps is not None and (max_jumps < 1 or max_jumps > UNIVERSE.SEARCH_MAX_JUMPS):
            raise InvalidParameterError(
                "max_jumps", max_jumps, f"Must be between 1 and {UNIVERSE.SEARCH_MAX_JUMPS}"
            )
        if security_min is not None and (security_min < -1.0 or security_min > 1.0):
            raise InvalidParameterError(
                "security_min", security_min, "Must be between -1.0 and 1.0"
            )
        if security_max is not None and (security_max < -1.0 or security_max > 1.0):
            raise InvalidParameterError(
                "security_max", security_max, "Must be between -1.0 and 1.0"
            )

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
            region_id = _resolve_region(universe_graph, region)
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
            universe=universe_graph,
            origin_idx=origin_idx,
            max_jumps=max_jumps,
            security_min=security_min,
            security_max=security_max,
            region_id=region_id,
            is_border=is_border,
            limit=limit,
        )

        return {
            "systems": [r.model_dump() for r in results],
            "total_found": len(results),
            "filters_applied": _summarize_filters(
                origin_canonical or origin, max_jumps, security_min, security_max, region, is_border
            ),
            "corrections": corrections,
        }


def register_loop_tools(server: FastMCP, universe: UniverseGraph) -> None:
    """Register loop planning tools with MCP server (for test compatibility)."""

    @server.tool()
    async def universe_loop(
        origin: str,
        target_jumps: int = 20,
        min_borders: int = 4,
        max_borders: int | None = None,
        optimize: str = "density",
        security_filter: str = "highsec",
        avoid_systems: list[str] | None = None,
    ) -> dict:
        """Plan a circular route visiting multiple border systems."""
        universe_graph = get_universe()

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
                idx = universe_graph.resolve_name(name)
                if idx is not None:
                    avoid_indices.add(idx)
                else:
                    unresolved_avoids.append(name)

        result = _plan_loop(
            universe=universe_graph,
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

        return result


def register_analyze_tools(server: FastMCP, universe: UniverseGraph) -> None:
    """Register route analysis tools with MCP server (for test compatibility)."""

    @server.tool()
    async def universe_analyze(systems: list[str]) -> dict:
        """Analyze security profile of a route or system list."""
        universe_graph = get_universe()

        if len(systems) < 2:
            raise InvalidParameterError(
                "systems",
                systems,
                "At least 2 systems required for analysis",
            )

        indices: list[int] = []
        for name in systems:
            idx = universe_graph.resolve_name(name)
            if idx is None:
                raise InvalidParameterError(
                    "systems",
                    name,
                    f"Unknown system: {name}",
                )
            indices.append(idx)

        _validate_connectivity(universe_graph, indices, systems)
        result = _analyze_route(universe_graph, indices)

        return result.model_dump()


def register_nearest_tools(server: FastMCP, universe: UniverseGraph) -> None:
    """Register nearest system tools with MCP server (for test compatibility)."""

    @server.tool()
    async def universe_nearest(
        origin: str,
        is_border: bool | None = None,
        min_adjacent_lowsec: int | None = None,
        security_min: float | None = None,
        security_max: float | None = None,
        region: str | None = None,
        max_kills: int | None = None,
        min_npc_kills: int | None = None,
        activity_level: str | None = None,
        limit: int = 5,
        max_jumps: int = 30,
    ) -> dict:
        """Find nearest systems matching predicate criteria."""
        if limit < 1 or limit > UNIVERSE.NEAREST_MAX_LIMIT:
            raise InvalidParameterError(
                "limit", limit, f"Must be between 1 and {UNIVERSE.NEAREST_MAX_LIMIT}"
            )
        if max_jumps < 1 or max_jumps > UNIVERSE.NEAREST_MAX_JUMPS:
            raise InvalidParameterError(
                "max_jumps", max_jumps, f"Must be between 1 and {UNIVERSE.NEAREST_MAX_JUMPS}"
            )
        if security_min is not None and (security_min < -1.0 or security_min > 1.0):
            raise InvalidParameterError(
                "security_min", security_min, "Must be between -1.0 and 1.0"
            )
        if security_max is not None and (security_max < -1.0 or security_max > 1.0):
            raise InvalidParameterError(
                "security_max", security_max, "Must be between -1.0 and 1.0"
            )
        if min_adjacent_lowsec is not None and min_adjacent_lowsec < 1:
            raise InvalidParameterError(
                "min_adjacent_lowsec", min_adjacent_lowsec, "Must be at least 1"
            )
        if max_kills is not None and max_kills < 0:
            raise InvalidParameterError("max_kills", max_kills, "Must be >= 0")
        if min_npc_kills is not None and min_npc_kills < 0:
            raise InvalidParameterError("min_npc_kills", min_npc_kills, "Must be >= 0")
        valid_activity_levels = {"none", "low", "medium", "high", "extreme"}
        if activity_level is not None and activity_level not in valid_activity_levels:
            raise InvalidParameterError(
                "activity_level",
                activity_level,
                f"Must be one of: {', '.join(sorted(valid_activity_levels))}",
            )

        needs_activity = (
            max_kills is not None or min_npc_kills is not None or activity_level is not None
        )
        activity_data = None
        cache_age = None

        if needs_activity:
            cache = get_activity_cache()
            activity_data = await cache.get_all_activity()
            cache_age = cache.get_kills_cache_age()

        universe_graph = get_universe()
        origin_resolved = resolve_system_name(origin)
        corrections = collect_corrections(origin_resolved)

        region_id = None
        if region:
            region_id = universe_graph.resolve_region(region)
            if region_id is None:
                return {
                    "origin": origin_resolved.canonical_name,
                    "systems": [],
                    "total_found": 0,
                    "search_radius": max_jumps,
                    "predicates": _summarize_predicates(
                        is_border, min_adjacent_lowsec, security_min, security_max, region
                    ),
                    "warning": f"Unknown region: '{region}'",
                    "corrections": corrections,
                }

        predicate = _build_predicate(
            universe=universe_graph,
            is_border=is_border,
            min_adjacent_lowsec=min_adjacent_lowsec,
            security_min=security_min,
            security_max=security_max,
            region_id=region_id,
            max_kills=max_kills,
            min_npc_kills=min_npc_kills,
            activity_level=activity_level,
            activity_data=activity_data,
        )

        results = _find_nearest(
            universe=universe_graph,
            origin_idx=origin_resolved.idx,
            predicate=predicate,
            limit=limit,
            max_jumps=max_jumps,
        )

        response = {
            "origin": origin_resolved.canonical_name,
            "systems": [r.model_dump() for r in results],
            "total_found": len(results),
            "search_radius": max_jumps,
            "predicates": _summarize_predicates(
                is_border=is_border,
                min_adjacent_lowsec=min_adjacent_lowsec,
                security_min=security_min,
                security_max=security_max,
                region=region,
                max_kills=max_kills,
                min_npc_kills=min_npc_kills,
                activity_level=activity_level,
            ),
            "corrections": corrections,
        }

        if cache_age is not None:
            response["activity_cache_age_seconds"] = cache_age

        return response


def register_waypoints_tools(server: FastMCP, universe: UniverseGraph) -> None:
    """Register waypoint optimization tools with MCP server (for test compatibility)."""

    @server.tool()
    async def universe_optimize_waypoints(
        waypoints: list[str],
        origin: str | None = None,
        return_to_origin: bool = True,
        security_filter: str = "any",
        avoid_systems: list[str] | None = None,
    ) -> dict:
        """Optimize visit order for multiple waypoints."""
        universe_graph = get_universe()

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
            idx = universe_graph.resolve_name(name)
            if idx is not None:
                if idx not in waypoint_indices:
                    waypoint_indices.append(idx)
            else:
                unresolved.append(name)

        if len(waypoint_indices) < UNIVERSE.WAYPOINTS_MIN_COUNT:
            raise InvalidParameterError(
                "waypoints",
                waypoint_indices,
                f"Only {len(waypoint_indices)} valid waypoints after resolution, "
                f"need at least {UNIVERSE.WAYPOINTS_MIN_COUNT}",
            )

        avoid_indices: set[int] = set()
        unresolved_avoids: list[str] = []
        if avoid_systems:
            for name in avoid_systems:
                idx = universe_graph.resolve_name(name)
                if idx is not None:
                    avoid_indices.add(idx)
                else:
                    unresolved_avoids.append(name)

        result = _do_optimize_waypoints(
            universe=universe_graph,
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

        return result


def register_activity_tools(server: FastMCP, universe: UniverseGraph) -> None:
    """Register activity overlay tools with MCP server (for test compatibility)."""

    @server.tool()
    async def universe_activity(systems: list[str]) -> dict:
        """Get recent activity data for specified systems."""
        universe_graph = get_universe()
        cache = get_activity_cache()

        if not systems:
            raise InvalidParameterError("systems", systems, "At least one system required")

        result_systems: list[SystemActivity] = []
        warnings: list[str] = []

        for name in systems:
            idx = universe_graph.resolve_name(name)
            if idx is None:
                warnings.append(f"Unknown system: {name}")
                continue

            system_id = int(universe_graph.system_ids[idx])
            activity = await cache.get_activity(system_id)

            total_kills = activity.ship_kills + activity.pod_kills
            activity_level = classify_activity(total_kills, "kills")

            result_systems.append(
                SystemActivity(
                    name=universe_graph.idx_to_name[idx],
                    system_id=system_id,
                    security=float(universe_graph.security[idx]),
                    security_class=universe_graph.security_class(idx),
                    ship_kills=activity.ship_kills,
                    pod_kills=activity.pod_kills,
                    npc_kills=activity.npc_kills,
                    ship_jumps=activity.ship_jumps,
                    activity_level=activity_level,
                )
            )

        result = ActivityResult(
            systems=result_systems,
            cache_age_seconds=cache.get_kills_cache_age(),
            data_period="last_hour",
            warnings=warnings,
        )

        return result.model_dump()

    @server.tool()
    async def universe_hotspots(
        origin: str,
        max_jumps: int = 15,
        activity_type: str = "kills",
        min_security: float | None = None,
        max_security: float | None = None,
        limit: int = 10,
    ) -> dict:
        """Find high-activity systems near origin."""
        universe_graph = get_universe()
        cache = get_activity_cache()

        if activity_type not in ("kills", "jumps", "ratting"):
            raise InvalidParameterError(
                "activity_type",
                activity_type,
                "Must be one of: kills, jumps, ratting",
            )

        if max_jumps < 1 or max_jumps > 30:
            raise InvalidParameterError(
                "max_jumps",
                max_jumps,
                "Must be between 1 and 30",
            )

        if limit < 1 or limit > 50:
            raise InvalidParameterError("limit", limit, "Must be between 1 and 50")

        origin_resolved = resolve_system_name(origin)
        corrections = collect_corrections(origin_resolved)

        g = universe_graph.graph
        visited = {origin_resolved.idx: 0}
        frontier = [origin_resolved.idx]
        systems_in_range: list[tuple[int, int]] = []

        for distance in range(1, max_jumps + 1):
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

        hotspots: list[HotspotSystem] = []
        systems_scanned = 0

        for idx, distance in systems_in_range:
            sec = float(universe_graph.security[idx])

            if min_security is not None and sec < min_security:
                continue
            if max_security is not None and sec > max_security:
                continue

            systems_scanned += 1
            system_id = int(universe_graph.system_ids[idx])
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
                    name=universe_graph.idx_to_name[idx],
                    system_id=system_id,
                    security=sec,
                    security_class=universe_graph.security_class(idx),
                    region=universe_graph.get_region_name(idx),
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
            search_radius=max_jumps,
            systems_scanned=systems_scanned,
            cache_age_seconds=cache.get_kills_cache_age(),
            corrections=corrections,
        )

        return result.model_dump()

    @server.tool()
    async def universe_gatecamp_risk(
        route: list[str] | None = None,
        origin: str | None = None,
        destination: str | None = None,
        mode: str = "safe",
    ) -> dict:
        """Analyze gatecamp risk along a route."""
        universe_graph = get_universe()
        cache = get_activity_cache()

        corrections: dict[str, str] = {}
        if route:
            indices: list[int] = []
            for name in route:
                idx = universe_graph.resolve_name(name)
                if idx is None:
                    raise SystemNotFoundError(name, [])
                indices.append(idx)
        elif origin and destination:
            origin_resolved = resolve_system_name(origin)
            dest_resolved = resolve_system_name(destination)
            corrections = collect_corrections(origin_resolved, dest_resolved)

            indices = _calculate_route(universe_graph, origin_resolved.idx, dest_resolved.idx, mode)
            if not indices:
                raise RouteNotFoundError(
                    origin_resolved.canonical_name, dest_resolved.canonical_name
                )
        else:
            raise InvalidParameterError(
                "route",
                None,
                "Must provide either 'route' or both 'origin' and 'destination'",
            )

        if len(indices) < 2:
            raise InvalidParameterError("route", route, "Route must have at least 2 systems")

        chokepoints: list[GatecampRisk] = []
        high_risk_systems: list[str] = []

        for i in range(1, len(indices)):
            prev_idx = indices[i - 1]
            curr_idx = indices[i]

            prev_class = universe_graph.security_class(prev_idx)
            curr_class = universe_graph.security_class(curr_idx)

            chokepoint_type: ChokepointType | None = None

            if prev_class == "HIGH" and curr_class in ("LOW", "NULL"):
                chokepoint_type = "lowsec_entry"
                chokepoint_idx = curr_idx
            elif prev_class in ("LOW", "NULL") and curr_class == "HIGH":
                chokepoint_type = "lowsec_exit"
                chokepoint_idx = prev_idx
            else:
                if curr_class in ("LOW", "NULL"):
                    neighbors = list(universe_graph.graph.neighbors(curr_idx))
                    if len(neighbors) <= 2:
                        chokepoint_type = "pipe"
                        chokepoint_idx = curr_idx
                    elif len(neighbors) >= 4:
                        chokepoint_type = "hub"
                        chokepoint_idx = curr_idx

            if chokepoint_type:
                system_id = int(universe_graph.system_ids[chokepoint_idx])
                activity = await cache.get_activity(system_id)
                ship_kills = activity.ship_kills
                pod_kills = activity.pod_kills
                total_kills = ship_kills + pod_kills

                risk_level: RiskLevel
                if total_kills >= 20:
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

                system_name = universe_graph.idx_to_name[chokepoint_idx]

                chokepoints.append(
                    GatecampRisk(
                        system=system_name,
                        system_id=system_id,
                        security=float(universe_graph.security[chokepoint_idx]),
                        chokepoint_type=chokepoint_type,
                        recent_kills=ship_kills,
                        recent_pods=pod_kills,
                        risk_level=risk_level,
                        warning=warning,
                    )
                )

                if risk_level in ("high", "extreme"):
                    high_risk_systems.append(system_name)

        overall_risk: RiskLevel
        if any(c.risk_level == "extreme" for c in chokepoints):
            overall_risk = "extreme"
        elif any(c.risk_level == "high" for c in chokepoints):
            overall_risk = "high"
        elif any(c.risk_level == "medium" for c in chokepoints):
            overall_risk = "medium"
        else:
            overall_risk = "low"

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

        origin_name = universe_graph.idx_to_name[indices[0]]
        dest_name = universe_graph.idx_to_name[indices[-1]]

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

        return result.model_dump()

    @server.tool()
    async def fw_frontlines(faction: str | None = None) -> dict:
        """Get current Faction Warfare frontline systems."""
        universe_graph = get_universe()
        cache = get_activity_cache()

        fw_data = await cache.get_all_fw()

        filter_faction_id: int | None = None
        if faction:
            filter_faction_id = get_faction_id(faction)
            if filter_faction_id is None:
                raise InvalidParameterError(
                    "faction",
                    faction,
                    "Must be one of: caldari, gallente, amarr, minmatar",
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

            idx = universe_graph.id_to_idx.get(system_id)
            if idx is None:
                continue

            if fw_system.victory_points_threshold > 0:
                contested_pct = fw_system.victory_points / fw_system.victory_points_threshold * 100
            else:
                contested_pct = 0.0

            activity = await cache.get_activity(system_id)
            recent_kills = activity.ship_kills + activity.pod_kills

            fw_result = FWSystem(
                name=universe_graph.idx_to_name[idx],
                system_id=system_id,
                security=float(universe_graph.security[idx]),
                region=universe_graph.get_region_name(idx),
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

        return result.model_dump()

    @server.tool()
    async def activity_cache_status() -> dict:
        """Return diagnostic information about the activity cache."""
        cache = get_activity_cache()
        status = cache.get_cache_status()

        result = CacheStatusResult(
            kills=CacheLayerStatus(
                cached_systems=status["kills"]["cached_systems"],
                age_seconds=status["kills"]["age_seconds"],
                ttl_seconds=status["kills"]["ttl_seconds"],
                stale=status["kills"]["stale"],
            ),
            jumps=CacheLayerStatus(
                cached_systems=status["jumps"]["cached_systems"],
                age_seconds=status["jumps"]["age_seconds"],
                ttl_seconds=status["jumps"]["ttl_seconds"],
                stale=status["jumps"]["stale"],
            ),
            fw=CacheLayerStatus(
                cached_systems=status["fw"]["cached_systems"],
                age_seconds=status["fw"]["age_seconds"],
                ttl_seconds=status["fw"]["ttl_seconds"],
                stale=status["fw"]["stale"],
            ),
        )

        return result.model_dump()
