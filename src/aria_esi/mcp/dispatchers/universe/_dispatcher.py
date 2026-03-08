"""Universe dispatcher registration and action routing."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from ...context import log_context
from ...errors import InvalidParameterError
from ...policy import check_capability
from ...validation import add_validation_warnings, validate_action_params
from ._actions_intel import (
    _activity,
    _fw_frontlines,
    _gatecamp_risk,
    _hotspots,
    _local_area,
    _territory_analysis,
)
from ._actions_navigation import _borders, _nearest, _route, _search, _systems
from ._actions_planning import _analyze, _loop, _optimize_waypoints

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from aria_esi.universe.graph import UniverseGraph


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
        # territory routing params
        prefer_territory: str | None = None,
        avoid_territory: str | None = None,
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
                prefer_territory: Coalition alias to prefer (e.g., "imperium")
                avoid_territory: Coalition alias to avoid (e.g., "panfam")

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
                mode: Routing mode (default "shortest")

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
                "prefer_territory": prefer_territory,
                "avoid_territory": avoid_territory,
            },
        )

        # Execute action and add any validation warnings to result
        match action:
            case "route":
                result = await _route(
                    origin,
                    destination,
                    mode,
                    avoid_systems,
                    prefer_territory,
                    avoid_territory,
                )

            case "systems":
                result = await _systems(systems)

            case "borders":
                result = await _borders(origin, limit, max_jumps)

            case "search":
                result = await _search(
                    origin,
                    max_jumps,
                    security_min,
                    security_max,
                    region,
                    is_border,
                    limit,
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
