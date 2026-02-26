"""Legacy register_*_tools functions for test compatibility."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aria_esi.store.activity import (
    classify_activity,
    get_activity_cache,
    get_faction_id,
    get_faction_name,
)

from ....services.navigation import VALID_MODES
from ...context_policy import UNIVERSE
from ...errors import InvalidParameterError, RouteNotFoundError, SystemNotFoundError
from ...models import (
    VALID_OPTIMIZE_MODES,
    VALID_SECURITY_FILTERS,
    ActivityResult,
    CacheLayerStatus,
    CacheStatusResult,
    ChokepointType,
    FWFrontlinesResult,
    FWSystem,
    GatecampRisk,
    GatecampRiskResult,
    HotspotsResult,
    HotspotSystem,
    RiskLevel,
    RouteResult,
    SystemActivity,
    SystemInfo,
)
from ...tools import ResolvedSystem, collect_corrections, get_universe, resolve_system_name
from ...utils import build_system_info
from ._helpers_analyze import _analyze_route, _validate_connectivity
from ._helpers_loop import _plan_loop
from ._helpers_route import _build_route_result, _calculate_route
from ._helpers_search import (
    _build_predicate,
    _find_border_systems,
    _find_nearest,
    _resolve_region,
    _search_systems,
    _summarize_filters,
    _summarize_predicates,
)
from ._helpers_waypoints import _do_optimize_waypoints

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from aria_esi.universe.graph import UniverseGraph


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
            except Exception:  # noqa: BLE001 -- MCP handler
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
