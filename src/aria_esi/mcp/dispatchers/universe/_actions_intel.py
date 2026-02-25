"""Intel action implementations: activity, hotspots, gatecamp_risk, fw_frontlines, local_area, territory_analysis."""

from __future__ import annotations

import logging
from collections import deque

from ...activity import classify_activity, get_activity_cache, get_faction_id, get_faction_name
from ...context import wrap_output, wrap_output_multi
from ...context_policy import UNIVERSE
from ...errors import InvalidParameterError, RouteNotFoundError, SystemNotFoundError
from ...models import (
    ActivityResult,
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
from ...tools import collect_corrections, get_universe, resolve_system_name
from ._helpers_local_area import _classify_border, _classify_threat_level, _find_escape_routes
from ._helpers_route import _calculate_route

logger = logging.getLogger(__name__)


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
        except (ImportError, RuntimeError):
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

        except Exception as e:  # noqa: BLE001 -- MCP handler
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
    except (ImportError, RuntimeError):
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
                except Exception:  # noqa: BLE001 -- MCP handler
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

    from ...models import (
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
            from ....services.redisq.threat_cache import get_threat_cache

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
        except (ImportError, RuntimeError):
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
