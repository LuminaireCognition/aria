"""
Activity Overlay Tools for MCP Universe Server.

Provides ESI-backed activity tools for live intel on system activity:
- universe_activity: Raw activity data for systems
- universe_hotspots: Find high-activity systems near origin
- universe_gatecamp_risk: Overlay kill data on route chokepoints
- fw_frontlines: Faction Warfare contested systems
- activity_cache_status: Cache diagnostics

STP-013: Activity Overlay Tools
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .activity import (
    classify_activity,
    get_activity_cache,
    get_faction_id,
    get_faction_name,
)
from .errors import InvalidParameterError, RouteNotFoundError, SystemNotFoundError
from .models import (
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
    SystemActivity,
)
from .tools import collect_corrections, get_universe, resolve_system_name

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from ..universe.graph import UniverseGraph


def register_activity_tools(server: FastMCP, universe: UniverseGraph) -> None:
    """
    Register activity overlay tools with MCP server.

    Args:
        server: MCP Server instance
        universe: UniverseGraph for system lookups
    """

    @server.tool()
    async def universe_activity(systems: list[str]) -> dict:
        """
        Get recent activity data for specified systems.

        Returns kills, jumps, and NPC activity from the last hour.
        Data is cached with ~10 minute refresh.

        Args:
            systems: List of system names to query

        Returns:
            ActivityResult with per-system activity breakdown

        Example:
            universe_activity(["Tama", "Amamake", "Rancer"])
        """
        universe = get_universe()
        cache = get_activity_cache()

        if not systems:
            raise InvalidParameterError("systems", systems, "At least one system required")

        result_systems: list[SystemActivity] = []
        warnings: list[str] = []

        for name in systems:
            idx = universe.resolve_name(name)
            if idx is None:
                warnings.append(f"Unknown system: {name}")
                continue

            system_id = int(universe.system_ids[idx])
            activity = await cache.get_activity(system_id)

            # Compute activity level based on total PvP kills
            total_kills = activity.ship_kills + activity.pod_kills
            activity_level = classify_activity(total_kills, "kills")

            result_systems.append(
                SystemActivity(
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
        """
        Find high-activity systems near origin.

        Useful for hunting roams (find targets) or avoidance (find danger).

        Args:
            origin: Starting system for search
            max_jumps: Maximum distance to search (default: 15)
            activity_type: What to measure
                - "kills": PvP kills (ship + pod)
                - "jumps": Traffic volume
                - "ratting": NPC kills (potential targets)
            min_security: Minimum security status filter
            max_security: Maximum security status filter
            limit: Maximum systems to return (default: 10)

        Returns:
            List of high-activity systems sorted by activity level

        Example:
            universe_hotspots("Hek", activity_type="jumps",
                            min_security=0.1, max_security=0.4)
        """
        universe = get_universe()
        cache = get_activity_cache()

        # Validate parameters
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

        # Resolve origin (with auto-correction)
        origin_resolved = resolve_system_name(origin)
        corrections = collect_corrections(origin_resolved)

        # BFS to find systems within range
        g = universe.graph
        visited = {origin_resolved.idx: 0}
        frontier = [origin_resolved.idx]
        systems_in_range: list[tuple[int, int]] = []  # (idx, distance)

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

        # Get activity data and filter
        hotspots: list[HotspotSystem] = []
        systems_scanned = 0

        for idx, distance in systems_in_range:
            sec = float(universe.security[idx])

            # Apply security filters
            if min_security is not None and sec < min_security:
                continue
            if max_security is not None and sec > max_security:
                continue

            systems_scanned += 1
            system_id = int(universe.system_ids[idx])
            activity = await cache.get_activity(system_id)

            # Get activity value based on type
            if activity_type == "kills":
                activity_value = activity.ship_kills + activity.pod_kills
            elif activity_type == "jumps":
                activity_value = activity.ship_jumps
            else:  # ratting
                activity_value = activity.npc_kills

            # Skip systems with no activity
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

        # Sort by activity value descending and limit
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
        """
        Analyze gatecamp risk along a route.

        Combines static chokepoint analysis with live kill data to identify
        likely gatecamps.

        Args:
            route: Explicit route as system list, OR
            origin/destination: Calculate route first
            mode: Routing mode if calculating (shortest, safe, unsafe)

        Returns:
            Route with risk assessment for each chokepoint

        Gatecamp Heuristic:
            A system is flagged as likely gatecamp if:
            - It's a chokepoint (security transition or pipe)
            - Recent kills > 5 in last hour

        Example:
            universe_gatecamp_risk(origin="Jita", destination="Tama")
        """
        universe = get_universe()
        cache = get_activity_cache()

        # Determine route - either explicit or calculated
        corrections: dict[str, str] = {}
        if route:
            # Use explicit route
            indices: list[int] = []
            for name in route:
                idx = universe.resolve_name(name)
                if idx is None:
                    raise SystemNotFoundError(name, [])
                indices.append(idx)
        elif origin and destination:
            # Calculate route using same algorithm as universe_route
            from .tools_route import _calculate_route

            origin_resolved = resolve_system_name(origin)
            dest_resolved = resolve_system_name(destination)
            corrections = collect_corrections(origin_resolved, dest_resolved)

            indices = _calculate_route(universe, origin_resolved.idx, dest_resolved.idx, mode)
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

        # Find chokepoints and analyze risk
        chokepoints: list[GatecampRisk] = []
        high_risk_systems: list[str] = []

        for i in range(1, len(indices)):
            prev_idx = indices[i - 1]
            curr_idx = indices[i]

            prev_class = universe.security_class(prev_idx)
            curr_class = universe.security_class(curr_idx)

            # Detect chokepoint type
            chokepoint_type: ChokepointType | None = None

            if prev_class == "HIGH" and curr_class in ("LOW", "NULL"):
                chokepoint_type = "lowsec_entry"
                chokepoint_idx = curr_idx
            elif prev_class in ("LOW", "NULL") and curr_class == "HIGH":
                chokepoint_type = "lowsec_exit"
                chokepoint_idx = prev_idx
            else:
                # Check for pipe or hub systems in dangerous space
                if curr_class in ("LOW", "NULL"):
                    neighbors = list(universe.graph.neighbors(curr_idx))
                    if len(neighbors) <= 2:
                        # Pipe: bottleneck with few exits
                        chokepoint_type = "pipe"
                        chokepoint_idx = curr_idx
                    elif len(neighbors) >= 4:
                        # Hub: major junction, often camped
                        chokepoint_type = "hub"
                        chokepoint_idx = curr_idx

            if chokepoint_type:
                system_id = int(universe.system_ids[chokepoint_idx])
                activity = await cache.get_activity(system_id)
                ship_kills = activity.ship_kills
                pod_kills = activity.pod_kills
                total_kills = ship_kills + pod_kills

                # Determine risk level
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

                system_name = universe.idx_to_name[chokepoint_idx]

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

        # Get origin/destination names
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

        return result.model_dump()

    @server.tool()
    async def fw_frontlines(faction: str | None = None) -> dict:
        """
        Get current Faction Warfare frontline systems.

        Returns contested and vulnerable systems where fighting is active.

        Args:
            faction: Filter to specific faction (optional)
                - "caldari", "gallente", "amarr", "minmatar"
                - None for all factions

        Returns:
            FW systems grouped by contested status

        Example:
            fw_frontlines("gallente")
        """
        universe = get_universe()
        cache = get_activity_cache()

        # Get all FW data
        fw_data = await cache.get_all_fw()

        # Optional faction filter
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
            # Apply faction filter
            if filter_faction_id:
                if (
                    fw_system.owner_faction_id != filter_faction_id
                    and fw_system.occupier_faction_id != filter_faction_id
                ):
                    continue

            # Resolve system name from ID
            idx = universe.id_to_idx.get(system_id)
            if idx is None:
                continue

            # Calculate contested percentage
            if fw_system.victory_points_threshold > 0:
                contested_pct = fw_system.victory_points / fw_system.victory_points_threshold * 100
            else:
                contested_pct = 0.0

            # Get kill activity for this system
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

        # Sort by contested percentage (most contested first)
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
        """
        Return diagnostic information about the activity cache.

        Useful for debugging cache behavior, checking data freshness,
        and verifying ESI connectivity.

        Returns:
            Cache status for kills, jumps, and FW data layers

        Example:
            activity_cache_status()
        """
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
