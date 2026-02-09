"""
ARIA ESI Universe Commands

Cached universe queries for fast local lookups.
Graph management commands for MCP server.
No authentication required.
"""

import argparse
import time
from pathlib import Path

from ..cache import (
    find_border_systems_in_region,
    find_nearest_border_systems,
    get_cache_info,
    get_system_by_name,
    get_system_full_info,
    is_cache_available,
)
from ..core import get_utc_timestamp
from ..mcp.context_policy import UNIVERSE

# Constants for loop command - imported from service to avoid duplication
from ..services.loop_planning import VALID_SECURITY_FILTERS
from ..universe.builder import (
    DEFAULT_CACHE_PATH,
    DEFAULT_GRAPH_PATH,
    build_universe_graph,
    load_universe_graph,
)

LOOP_MIN_TARGET_JUMPS = UNIVERSE.LOOP_MIN_TARGET_JUMPS
LOOP_MAX_TARGET_JUMPS = UNIVERSE.LOOP_MAX_TARGET_JUMPS
LOOP_MIN_BORDERS = UNIVERSE.LOOP_MIN_BORDERS
LOOP_MAX_BORDERS = UNIVERSE.LOOP_MAX_BORDERS


def cmd_borders(args: argparse.Namespace) -> dict:
    """
    Find high-sec systems bordering low-sec.

    Can search by region or find nearest to a system.
    """
    query_ts = get_utc_timestamp()

    if not is_cache_available():
        return {
            "error": "cache_not_found",
            "message": "Universe cache not available",
            "hint": "Run 'python -m aria_esi.cache.builder' to generate it",
            "query_timestamp": query_ts,
        }

    region = getattr(args, "region", None)
    system = getattr(args, "system", None)
    limit = getattr(args, "limit", 10)

    if region:
        # Search by region
        borders = find_border_systems_in_region(region)
        if not borders:
            return {
                "error": "no_results",
                "message": f"No border systems found in region '{region}'",
                "hint": "Check region name spelling or try a different region",
                "query_timestamp": query_ts,
            }

        return {
            "query_timestamp": query_ts,
            "volatility": "stable",
            "search_type": "region",
            "region": region,
            "border_systems": borders,
            "count": len(borders),
        }

    elif system:
        # Search by proximity to system
        borders = find_nearest_border_systems(system, limit=limit)
        if not borders:
            # Check if system exists
            sys_match = get_system_by_name(system)
            if not sys_match:
                return {
                    "error": "system_not_found",
                    "message": f"System '{system}' not found",
                    "query_timestamp": query_ts,
                }
            return {
                "error": "no_results",
                "message": f"No border systems found near '{system}'",
                "query_timestamp": query_ts,
            }

        # Get origin system info
        origin_info = get_system_full_info(get_system_by_name(system)[0])

        return {
            "query_timestamp": query_ts,
            "volatility": "stable",
            "search_type": "proximity",
            "origin": origin_info,
            "border_systems": borders,
            "count": len(borders),
            "note": "Jump counts are approximate (BFS). Use 'route' command for exact distances.",
        }

    else:
        return {
            "error": "missing_argument",
            "message": "Specify --region or --system",
            "query_timestamp": query_ts,
        }


def cmd_loop(args: argparse.Namespace) -> dict:
    """
    Plan a circular mining route through border systems.

    Finds high-sec systems bordering low-sec and plans an optimized
    circular route to visit them, minimizing backtracking.
    """
    query_ts = get_utc_timestamp()

    # Validate parameters
    origin = args.origin
    target_jumps = getattr(args, "target_jumps", 20)
    min_borders = getattr(args, "min_borders", 3)
    max_borders = getattr(args, "max_borders", 6)
    security_filter = getattr(args, "security_filter", "highsec")
    avoid_systems = getattr(args, "avoid", None)

    if target_jumps < LOOP_MIN_TARGET_JUMPS or target_jumps > LOOP_MAX_TARGET_JUMPS:
        return {
            "error": "invalid_parameter",
            "message": f"target_jumps must be between {LOOP_MIN_TARGET_JUMPS} and {LOOP_MAX_TARGET_JUMPS}",
            "query_timestamp": query_ts,
        }

    if min_borders < LOOP_MIN_BORDERS or min_borders > LOOP_MAX_BORDERS:
        return {
            "error": "invalid_parameter",
            "message": f"min_borders must be between {LOOP_MIN_BORDERS} and {LOOP_MAX_BORDERS}",
            "query_timestamp": query_ts,
        }

    if max_borders < min_borders or max_borders > LOOP_MAX_BORDERS:
        return {
            "error": "invalid_parameter",
            "message": f"max_borders must be between {min_borders} and {LOOP_MAX_BORDERS}",
            "query_timestamp": query_ts,
        }

    if security_filter not in VALID_SECURITY_FILTERS:
        return {
            "error": "invalid_parameter",
            "message": f"security_filter must be one of: {', '.join(VALID_SECURITY_FILTERS)}",
            "query_timestamp": query_ts,
        }

    # Check if graph is available
    if not DEFAULT_GRAPH_PATH.exists():
        return {
            "error": "graph_not_found",
            "message": "Universe graph not available",
            "hint": "Run 'aria-esi graph-build' to generate it",
            "query_timestamp": query_ts,
        }

    # Load graph and call loop planner
    try:
        universe = load_universe_graph(DEFAULT_GRAPH_PATH)
    except Exception as e:
        return {
            "error": "graph_load_failed",
            "message": f"Could not load universe graph: {e}",
            "query_timestamp": query_ts,
        }

    # Resolve origin system
    origin_idx = universe.resolve_name(origin)
    if origin_idx is None:
        return {
            "error": "system_not_found",
            "message": f"System '{origin}' not found",
            "query_timestamp": query_ts,
        }

    # Use the loop planning service
    try:
        from ..services.loop_planning import InsufficientBordersError, LoopPlanningService

        service = LoopPlanningService(universe)

        # Resolve avoid systems
        avoid_indices: set[int] = set()
        unresolved_avoids: list[str] = []
        if avoid_systems:
            avoid_indices, unresolved_avoids = service.resolve_avoid_systems(avoid_systems)

        summary = service.plan_loop(
            origin_idx=origin_idx,
            target_jumps=target_jumps,
            min_borders=min_borders,
            max_borders=max_borders,
            security_filter=security_filter,  # type: ignore[arg-type]
            avoid_systems=avoid_indices if avoid_indices else None,
        )

        # Build CLI-friendly result from service summary
        from ..mcp.models import BorderSystem
        from ..mcp.utils import build_system_info

        systems = [build_system_info(universe, idx).model_dump() for idx in summary.full_route]

        border_systems = [
            BorderSystem(
                name=universe.idx_to_name[idx],
                system_id=int(universe.system_ids[idx]),
                security=float(universe.security[idx]),
                jumps_from_origin=dist,
                adjacent_lowsec=universe.get_adjacent_lowsec(idx),
                region=universe.get_region_name(idx),
            ).model_dump()
            for idx, dist in summary.borders_visited
        ]

        # Build warnings list
        warnings: list[str] = []
        if unresolved_avoids:
            warnings.append(f"Unknown systems in avoid list: {', '.join(unresolved_avoids)}")

        return {
            "query_timestamp": query_ts,
            "volatility": "stable",
            "origin_requested": origin,
            "systems": systems,
            "total_jumps": summary.total_jumps,
            "unique_systems": summary.unique_systems,
            "border_systems_visited": border_systems,
            "backtrack_jumps": summary.backtrack_jumps,
            "efficiency": summary.efficiency,
            "warnings": warnings,
            "corrections": {},
        }

    except ImportError as e:
        return {
            "error": "loop_planner_unavailable",
            "message": f"Loop planner not available: {e}",
            "hint": "Ensure 'universe' optional dependencies are installed: uv sync --extra universe",
            "query_timestamp": query_ts,
        }
    except InsufficientBordersError as e:
        return {
            "error": "insufficient_borders",
            "message": str(e),
            "suggestion": e.suggestion,
            "query_timestamp": query_ts,
        }
    except Exception as e:
        return {
            "error": "loop_planning_failed",
            "message": f"Loop planning failed: {e}",
            "query_timestamp": query_ts,
        }


def cmd_cache_info(args: argparse.Namespace) -> dict:
    """Show universe cache status."""
    query_ts = get_utc_timestamp()
    info = get_cache_info()

    return {
        "query_timestamp": query_ts,
        **info,
    }


def cmd_system_info(args: argparse.Namespace) -> dict:
    """Look up system information from cache."""
    query_ts = get_utc_timestamp()

    if not is_cache_available():
        return {
            "error": "cache_not_found",
            "message": "Universe cache not available",
            "hint": "Run 'python -m aria_esi.cache.builder' to generate it",
            "query_timestamp": query_ts,
        }

    system_name = args.system

    sys_match = get_system_by_name(system_name)
    if not sys_match:
        return {
            "error": "system_not_found",
            "message": f"System '{system_name}' not found",
            "query_timestamp": query_ts,
        }

    sys_id, _ = sys_match
    info = get_system_full_info(sys_id)

    # Add neighbor info
    from ..cache import get_system_neighbors

    neighbors = []
    for _neighbor_id, neighbor in get_system_neighbors(sys_id):
        sec = neighbor.get("security", 0)
        sec_class = "HIGH" if sec >= 0.45 else "LOW" if sec > 0 else "NULL"
        neighbors.append(
            {
                "name": neighbor["name"],
                "security": round(sec, 2),
                "class": sec_class,
            }
        )

    return {
        "query_timestamp": query_ts,
        "volatility": "stable",
        "system": info,
        "neighbors": neighbors,
    }


# =============================================================================
# Graph Commands (STP-011)
# =============================================================================


def cmd_graph_build(args: argparse.Namespace) -> dict:
    """
    Build universe graph from JSON cache.

    Creates optimized .universe file for fast navigation queries.
    """
    query_ts = get_utc_timestamp()

    cache_path = Path(args.cache) if args.cache else DEFAULT_CACHE_PATH
    output_path = Path(args.output) if args.output else DEFAULT_GRAPH_PATH

    # Check if output exists and force flag
    if output_path.exists() and not args.force:
        return {
            "error": "output_exists",
            "message": f"Output file exists: {output_path}",
            "hint": "Use --force to overwrite",
            "query_timestamp": query_ts,
        }

    # Check if cache exists
    if not cache_path.exists():
        return {
            "error": "cache_not_found",
            "message": f"Cache file not found: {cache_path}",
            "hint": "Run cache builder first to generate universe_cache.json",
            "query_timestamp": query_ts,
        }

    # Build the graph
    start = time.perf_counter()
    try:
        universe = build_universe_graph(cache_path, output_path)
        elapsed = time.perf_counter() - start

        result = {
            "query_timestamp": query_ts,
            "status": "success",
            "message": f"Built universe graph in {elapsed:.2f}s",
            "graph": {
                "systems": universe.system_count,
                "stargates": universe.stargate_count,
                "border_systems": len(universe.border_systems),
                "highsec_systems": len(universe.highsec_systems),
                "lowsec_systems": len(universe.lowsec_systems),
                "nullsec_systems": len(universe.nullsec_systems),
                "regions": len(universe.region_names),
                "constellations": len(universe.constellation_names),
            },
            "output": {
                "path": str(output_path),
                "size_kb": round(output_path.stat().st_size / 1024, 1),
            },
            "build_time_seconds": round(elapsed, 2),
        }

        # Update checksum if requested
        if getattr(args, "update_checksum", False):
            try:
                from ..core.data_integrity import update_universe_graph_checksum

                checksum = update_universe_graph_checksum(output_path)
                result["checksum"] = {
                    "sha256": checksum,
                    "updated": True,
                }
            except Exception as e:
                result["checksum"] = {
                    "error": str(e),
                    "updated": False,
                }

        return result

    except Exception as e:
        return {
            "error": "build_failed",
            "message": f"Build failed: {e}",
            "query_timestamp": query_ts,
        }


def cmd_graph_verify(args: argparse.Namespace) -> dict:
    """
    Verify universe graph integrity.

    Checks that the graph loads correctly and passes all validation checks.
    """
    query_ts = get_utc_timestamp()

    graph_path = Path(args.graph) if args.graph else DEFAULT_GRAPH_PATH

    if not graph_path.exists():
        return {
            "error": "graph_not_found",
            "message": f"Graph file not found: {graph_path}",
            "hint": "Run 'graph-build' first to create the graph",
            "query_timestamp": query_ts,
        }

    errors = []
    checks = []

    # Try to load the graph
    try:
        start = time.perf_counter()
        universe = load_universe_graph(graph_path)
        load_time = time.perf_counter() - start
        checks.append(
            {
                "check": "load",
                "status": "pass",
                "load_time_ms": round(load_time * 1000, 1),
            }
        )
    except Exception as e:
        return {
            "error": "load_failed",
            "message": f"Could not load graph: {e}",
            "query_timestamp": query_ts,
        }

    # Check basic properties
    if universe.system_count == 0:
        errors.append("No systems in graph")
        checks.append({"check": "system_count", "status": "fail", "message": "No systems"})
    else:
        checks.append({"check": "system_count", "status": "pass", "count": universe.system_count})

    # Check index consistency
    if len(universe.name_to_idx) != universe.system_count:
        errors.append(
            f"name_to_idx size mismatch: {len(universe.name_to_idx)} != {universe.system_count}"
        )
        checks.append({"check": "name_to_idx", "status": "fail"})
    else:
        checks.append({"check": "name_to_idx", "status": "pass"})

    if len(universe.id_to_idx) != universe.system_count:
        errors.append(
            f"id_to_idx size mismatch: {len(universe.id_to_idx)} != {universe.system_count}"
        )
        checks.append({"check": "id_to_idx", "status": "fail"})
    else:
        checks.append({"check": "id_to_idx", "status": "pass"})

    # Check security sets partition all systems
    security_total = (
        len(universe.highsec_systems) + len(universe.lowsec_systems) + len(universe.nullsec_systems)
    )
    if security_total != universe.system_count:
        errors.append(f"Security sets don't partition: {security_total} != {universe.system_count}")
        checks.append({"check": "security_partition", "status": "fail"})
    else:
        checks.append({"check": "security_partition", "status": "pass"})

    # Check border systems are valid high-sec systems
    border_valid = True
    for idx in universe.border_systems:
        if idx >= universe.system_count:
            errors.append(f"Invalid border system index: {idx}")
            border_valid = False
            break
        if universe.security[idx] < 0.45:
            name = universe.idx_to_name[idx]
            errors.append(f"Border system {name} is not high-sec")
            border_valid = False
            break
    checks.append({"check": "border_systems", "status": "pass" if border_valid else "fail"})

    # Check known systems exist
    known_systems = ["Jita", "Amarr", "Dodixie", "Rens", "Hek"]
    known_found = []
    known_missing = []
    for name in known_systems:
        known_idx = universe.resolve_name(name)
        if known_idx is None:
            errors.append(f"Known system not found: {name}")
            known_missing.append(name)
        else:
            known_found.append(name)
    checks.append(
        {
            "check": "known_systems",
            "status": "pass" if not known_missing else "fail",
            "found": known_found,
            "missing": known_missing,
        }
    )

    # Check graph connectivity (Jita to Amarr path)
    jita_idx = universe.resolve_name("Jita")
    amarr_idx = universe.resolve_name("Amarr")
    if jita_idx is not None and amarr_idx is not None:
        paths = universe.graph.get_shortest_paths(jita_idx, amarr_idx)
        if not paths or not paths[0]:
            errors.append("No path between Jita and Amarr")
            checks.append({"check": "connectivity", "status": "fail"})
        else:
            checks.append(
                {
                    "check": "connectivity",
                    "status": "pass",
                    "sample_path": "Jita -> Amarr",
                    "jumps": len(paths[0]) - 1,
                }
            )
    else:
        checks.append({"check": "connectivity", "status": "skip", "reason": "Trade hubs not found"})

    # Build result
    status = "FAILED" if errors else "PASSED"
    result = {
        "query_timestamp": query_ts,
        "status": status,
        "graph_path": str(graph_path),
        "checks": checks,
    }

    if errors:
        result["errors"] = errors

    return result


def cmd_activity_systems(args: argparse.Namespace) -> dict:
    """
    Get activity data for one or more systems.

    Queries ESI for recent kills, jumps, and NPC activity.
    With --realtime flag, includes real-time kill data and gatecamp detection.
    """
    import asyncio

    query_ts = get_utc_timestamp()

    systems = args.systems
    include_realtime = getattr(args, "realtime", False)

    if not systems:
        return {
            "error": "missing_argument",
            "message": "At least one system name required",
            "query_timestamp": query_ts,
        }

    # Load graph for system resolution
    if not DEFAULT_GRAPH_PATH.exists():
        return {
            "error": "graph_not_found",
            "message": "Universe graph not available",
            "hint": "Run 'aria-esi graph-build' to generate it",
            "query_timestamp": query_ts,
        }

    try:
        universe = load_universe_graph(DEFAULT_GRAPH_PATH)
    except Exception as e:
        return {
            "error": "graph_load_failed",
            "message": f"Could not load universe graph: {e}",
            "query_timestamp": query_ts,
        }

    # Try to get realtime cache if requested
    realtime_cache = None
    realtime_healthy = False
    if include_realtime:
        try:
            from ..services.redisq.threat_cache import get_threat_cache

            realtime_cache = get_threat_cache()
            realtime_healthy = realtime_cache.is_healthy()
        except Exception:
            pass  # Silently fall back to hourly-only

    try:
        from ..mcp.activity import classify_activity, get_activity_cache

        cache = get_activity_cache()

        async def fetch_activity():
            result_systems = []
            warnings = []

            for name in systems:
                idx = universe.resolve_name(name)
                if idx is None:
                    warnings.append(f"Unknown system: {name}")
                    continue

                system_id = int(universe.system_ids[idx])
                system_name = universe.idx_to_name[idx]
                activity = await cache.get_activity(system_id)

                total_kills = activity.ship_kills + activity.pod_kills
                activity_level = classify_activity(total_kills, "kills")

                system_data = {
                    "name": system_name,
                    "system_id": system_id,
                    "security": round(float(universe.security[idx]), 2),
                    "security_class": universe.security_class(idx),
                    "ship_kills": activity.ship_kills,
                    "pod_kills": activity.pod_kills,
                    "npc_kills": activity.npc_kills,
                    "ship_jumps": activity.ship_jumps,
                    "activity_level": activity_level,
                }

                # Add realtime data if available
                if realtime_healthy and realtime_cache:
                    try:
                        rt_summary = realtime_cache.get_activity_summary(system_id, system_name)
                        system_data["realtime"] = rt_summary.to_dict()
                    except Exception:
                        pass  # Non-fatal

                result_systems.append(system_data)

            return result_systems, warnings, cache.get_kills_cache_age()

        result_systems, warnings, cache_age = asyncio.run(fetch_activity())

        result = {
            "query_timestamp": query_ts,
            "volatility": "volatile",
            "data_period": "last_hour",
            "systems": result_systems,
            "cache_age_seconds": cache_age,
        }

        if include_realtime:
            result["realtime_healthy"] = realtime_healthy

        if warnings:
            result["warnings"] = warnings

        return result

    except ImportError as e:
        return {
            "error": "activity_unavailable",
            "message": f"Activity module not available: {e}",
            "query_timestamp": query_ts,
        }
    except Exception as e:
        return {
            "error": "activity_failed",
            "message": f"Activity query failed: {e}",
            "query_timestamp": query_ts,
        }


def cmd_hotspots(args: argparse.Namespace) -> dict:
    """
    Find high-activity systems near an origin.

    Uses ESI activity data to find systems with high kills, jumps, or ratting.
    """
    import asyncio

    query_ts = get_utc_timestamp()

    origin = args.origin
    max_jumps = getattr(args, "max_jumps", 15)
    activity_type = getattr(args, "activity_type", "kills")
    min_security = getattr(args, "min_security", None)
    max_security = getattr(args, "max_security", None)
    limit = getattr(args, "limit", 10)

    # Validate activity type
    if activity_type not in ("kills", "jumps", "ratting"):
        return {
            "error": "invalid_parameter",
            "message": "activity_type must be one of: kills, jumps, ratting",
            "query_timestamp": query_ts,
        }

    # Load graph
    if not DEFAULT_GRAPH_PATH.exists():
        return {
            "error": "graph_not_found",
            "message": "Universe graph not available",
            "hint": "Run 'aria-esi graph-build' to generate it",
            "query_timestamp": query_ts,
        }

    try:
        universe = load_universe_graph(DEFAULT_GRAPH_PATH)
    except Exception as e:
        return {
            "error": "graph_load_failed",
            "message": f"Could not load universe graph: {e}",
            "query_timestamp": query_ts,
        }

    # Resolve origin
    origin_idx = universe.resolve_name(origin)
    if origin_idx is None:
        return {
            "error": "system_not_found",
            "message": f"System '{origin}' not found",
            "query_timestamp": query_ts,
        }

    # Use the MCP hotspots implementation
    try:
        from ..mcp.activity import classify_activity, get_activity_cache

        cache = get_activity_cache()

        # BFS to find systems within range
        g = universe.graph
        visited = {origin_idx: 0}
        frontier = [origin_idx]
        systems_in_range = []

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

        # Get activity data
        async def fetch_hotspots():
            hotspots = []
            systems_scanned = 0

            for idx, distance in systems_in_range:
                sec = float(universe.security[idx])

                if min_security is not None and sec < min_security:
                    continue
                if max_security is not None and sec > max_security:
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
                    {
                        "name": universe.idx_to_name[idx],
                        "system_id": system_id,
                        "security": round(sec, 2),
                        "region": universe.get_region_name(idx),
                        "jumps_from_origin": distance,
                        "activity_value": activity_value,
                        "activity_level": activity_level,
                    }
                )

            hotspots.sort(key=lambda h: h["activity_value"], reverse=True)
            return hotspots[:limit], systems_scanned, cache.get_kills_cache_age()

        hotspots, systems_scanned, cache_age = asyncio.run(fetch_hotspots())

        return {
            "query_timestamp": query_ts,
            "volatility": "volatile",
            "data_period": "last_hour",
            "origin": universe.idx_to_name[origin_idx],
            "activity_type": activity_type,
            "hotspots": hotspots,
            "search_radius": max_jumps,
            "systems_scanned": systems_scanned,
            "cache_age_seconds": cache_age,
        }

    except ImportError as e:
        return {
            "error": "activity_unavailable",
            "message": f"Activity module not available: {e}",
            "query_timestamp": query_ts,
        }
    except Exception as e:
        return {
            "error": "hotspots_failed",
            "message": f"Hotspots search failed: {e}",
            "query_timestamp": query_ts,
        }


def cmd_gatecamp_risk(args: argparse.Namespace) -> dict:
    """
    Analyze gatecamp risk along a route.

    Combines static chokepoint analysis with live kill data.
    With --realtime flag, uses real-time kill data for active gatecamp detection.
    """
    import asyncio

    query_ts = get_utc_timestamp()

    origin = args.origin
    destination = args.destination
    mode = getattr(args, "mode", "safe")
    include_realtime = getattr(args, "realtime", False)

    # Load graph
    if not DEFAULT_GRAPH_PATH.exists():
        return {
            "error": "graph_not_found",
            "message": "Universe graph not available",
            "hint": "Run 'aria-esi graph-build' to generate it",
            "query_timestamp": query_ts,
        }

    try:
        universe = load_universe_graph(DEFAULT_GRAPH_PATH)
    except Exception as e:
        return {
            "error": "graph_load_failed",
            "message": f"Could not load universe graph: {e}",
            "query_timestamp": query_ts,
        }

    # Resolve systems
    origin_idx = universe.resolve_name(origin)
    if origin_idx is None:
        return {
            "error": "system_not_found",
            "message": f"System '{origin}' not found",
            "query_timestamp": query_ts,
        }

    dest_idx = universe.resolve_name(destination)
    if dest_idx is None:
        return {
            "error": "system_not_found",
            "message": f"System '{destination}' not found",
            "query_timestamp": query_ts,
        }

    # Calculate route
    try:
        from ..mcp.tools_route import _calculate_route

        indices = _calculate_route(universe, origin_idx, dest_idx, mode)
        if not indices:
            return {
                "error": "no_route",
                "message": f"No route found from {origin} to {destination}",
                "query_timestamp": query_ts,
            }
    except Exception as e:
        return {
            "error": "route_failed",
            "message": f"Route calculation failed: {e}",
            "query_timestamp": query_ts,
        }

    # Try to get realtime cache if requested
    realtime_cache = None
    realtime_healthy = False
    realtime_camps_detected = 0
    if include_realtime:
        try:
            from ..services.redisq.threat_cache import get_threat_cache

            realtime_cache = get_threat_cache()
            realtime_healthy = realtime_cache.is_healthy()
        except Exception:
            pass  # Silently fall back to hourly-only

    # Analyze gatecamp risk
    try:
        from ..mcp.activity import get_activity_cache

        cache = get_activity_cache()

        async def analyze_risk():
            nonlocal realtime_camps_detected
            chokepoints = []
            high_risk_systems = []

            for i in range(1, len(indices)):
                prev_idx = indices[i - 1]
                curr_idx = indices[i]

                prev_class = universe.security_class(prev_idx)
                curr_class = universe.security_class(curr_idx)

                chokepoint_type = None
                if prev_class == "HIGH" and curr_class in ("LOW", "NULL"):
                    chokepoint_type = "lowsec_entry"
                    chokepoint_idx = curr_idx
                elif prev_class in ("LOW", "NULL") and curr_class == "HIGH":
                    chokepoint_type = "lowsec_exit"
                    chokepoint_idx = prev_idx
                elif curr_class in ("LOW", "NULL"):
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
                    system_name = universe.idx_to_name[chokepoint_idx]
                    activity = await cache.get_activity(system_id)
                    ship_kills = activity.ship_kills
                    pod_kills = activity.pod_kills
                    total_kills = ship_kills + pod_kills

                    # Check realtime gatecamp detection if available
                    realtime_camp = None
                    if realtime_healthy and realtime_cache:
                        try:
                            realtime_camp = realtime_cache.get_gatecamp_status(
                                system_id, system_name
                            )
                        except Exception:
                            pass

                    # Determine risk level - realtime detection takes precedence
                    if realtime_camp and realtime_camp.confidence in ("high", "medium"):
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

                    chokepoint_data = {
                        "system": system_name,
                        "system_id": system_id,
                        "security": round(float(universe.security[chokepoint_idx]), 2),
                        "chokepoint_type": chokepoint_type,
                        "recent_kills": ship_kills,
                        "recent_pods": pod_kills,
                        "risk_level": risk_level,
                        "warning": warning,
                    }

                    # Add realtime details if camp detected
                    if realtime_camp:
                        chokepoint_data["realtime_camp"] = {
                            "confidence": realtime_camp.confidence,
                            "kills": realtime_camp.kill_count,
                            "force_asymmetry": realtime_camp.force_asymmetry,
                            "is_smartbomb": realtime_camp.is_smartbomb_camp,
                        }

                    chokepoints.append(chokepoint_data)

                    if risk_level in ("high", "extreme"):
                        high_risk_systems.append(system_name)

            # Determine overall risk
            if any(c["risk_level"] == "extreme" for c in chokepoints):
                overall_risk = "extreme"
            elif any(c["risk_level"] == "high" for c in chokepoints):
                overall_risk = "high"
            elif any(c["risk_level"] == "medium" for c in chokepoints):
                overall_risk = "medium"
            else:
                overall_risk = "low"

            return chokepoints, high_risk_systems, overall_risk, cache.get_kills_cache_age()

        chokepoints, high_risk, overall, cache_age = asyncio.run(analyze_risk())

        # Generate recommendation
        if overall == "extreme":
            recommendation = (
                f"Route has {len(high_risk)} extreme-risk chokepoints. "
                "Consider alternate route, scouting, or waiting."
            )
        elif overall == "high":
            recommendation = (
                f"Route has {len(high_risk)} high-risk chokepoints. "
                "Scout ahead or avoid: " + ", ".join(high_risk)
            )
        elif overall == "medium":
            recommendation = "Moderate risk. Stay alert at chokepoints."
        else:
            recommendation = "Route appears relatively safe."

        result = {
            "query_timestamp": query_ts,
            "volatility": "volatile",
            "data_period": "last_hour",
            "route_summary": {
                "origin": universe.idx_to_name[origin_idx],
                "destination": universe.idx_to_name[dest_idx],
                "total_jumps": len(indices) - 1,
                "overall_risk": overall,
            },
            "chokepoints": chokepoints,
            "high_risk_systems": high_risk,
            "recommendation": recommendation,
            "cache_age_seconds": cache_age,
        }

        # Add realtime metadata if requested
        if include_realtime:
            result["realtime_healthy"] = realtime_healthy
            result["realtime_camps_detected"] = realtime_camps_detected

        return result

    except ImportError as e:
        return {
            "error": "activity_unavailable",
            "message": f"Activity module not available: {e}",
            "query_timestamp": query_ts,
        }
    except Exception as e:
        return {
            "error": "risk_analysis_failed",
            "message": f"Risk analysis failed: {e}",
            "query_timestamp": query_ts,
        }


def cmd_gatecamp(args: argparse.Namespace) -> dict:
    """
    Check for active gatecamp in a single system.

    Uses real-time kill data from RedisQ for active camp detection.
    Falls back to hourly activity data if real-time unavailable.
    """
    import asyncio

    query_ts = get_utc_timestamp()

    system = args.system

    # Load graph for system resolution
    if not DEFAULT_GRAPH_PATH.exists():
        return {
            "error": "graph_not_found",
            "message": "Universe graph not available",
            "hint": "Run 'aria-esi graph-build' to generate it",
            "query_timestamp": query_ts,
        }

    try:
        universe = load_universe_graph(DEFAULT_GRAPH_PATH)
    except Exception as e:
        return {
            "error": "graph_load_failed",
            "message": f"Could not load universe graph: {e}",
            "query_timestamp": query_ts,
        }

    # Resolve system
    idx = universe.resolve_name(system)
    if idx is None:
        return {
            "error": "system_not_found",
            "message": f"System '{system}' not found",
            "query_timestamp": query_ts,
        }

    system_id = int(universe.system_ids[idx])
    system_name = universe.idx_to_name[idx]
    security = round(float(universe.security[idx]), 2)

    # Try to get realtime cache
    realtime_cache = None
    realtime_healthy = False
    try:
        from ..services.redisq.threat_cache import get_threat_cache

        realtime_cache = get_threat_cache()
        realtime_healthy = realtime_cache.is_healthy()
    except Exception:
        pass  # Fall back to hourly-only

    try:
        from ..mcp.activity import get_activity_cache

        cache = get_activity_cache()

        async def check_gatecamp():
            activity = await cache.get_activity(system_id)
            return activity

        activity = asyncio.run(check_gatecamp())

        result = {
            "query_timestamp": query_ts,
            "volatility": "volatile",
            "system": {
                "name": system_name,
                "system_id": system_id,
                "security": security,
                "security_class": universe.security_class(idx),
            },
            "hourly_activity": {
                "ship_kills": activity.ship_kills,
                "pod_kills": activity.pod_kills,
                "ship_jumps": activity.ship_jumps,
            },
            "realtime_healthy": realtime_healthy,
            "cache_age_seconds": cache.get_kills_cache_age(),
        }

        # Check for active gatecamp if realtime data available
        if realtime_healthy and realtime_cache:
            try:
                rt_summary = realtime_cache.get_activity_summary(system_id, system_name)
                gatecamp = rt_summary.gatecamp

                result["realtime"] = {
                    "kills_10m": rt_summary.kills_10m,
                    "kills_1h": rt_summary.kills_1h,
                    "pod_kills_10m": rt_summary.pod_kills_10m,
                    "recent_kills": rt_summary.recent_kills[:5],  # Last 5
                }

                if gatecamp:
                    result["gatecamp_detected"] = True
                    result["gatecamp"] = {
                        "confidence": gatecamp.confidence,
                        "kill_count": gatecamp.kill_count,
                        "window_minutes": gatecamp.window_minutes,
                        "force_asymmetry": gatecamp.force_asymmetry,
                        "is_smartbomb": gatecamp.is_smartbomb_camp,
                        "attacker_corps": gatecamp.attacker_corps,
                        "attacker_ships": gatecamp.attacker_ships,
                    }
                    if gatecamp.last_kill_time:
                        result["gatecamp"]["last_kill"] = gatecamp.last_kill_time.isoformat()
                else:
                    result["gatecamp_detected"] = False

            except Exception as e:
                result["realtime_error"] = str(e)
                result["gatecamp_detected"] = None  # Unknown
        else:
            # No realtime data - provide assessment based on hourly
            total_kills = activity.ship_kills + activity.pod_kills
            result["gatecamp_detected"] = None  # Cannot determine
            if total_kills >= 20:
                result["hourly_assessment"] = "High activity - possible gatecamp"
            elif total_kills >= 10:
                result["hourly_assessment"] = "Elevated activity - stay alert"
            elif total_kills >= 5:
                result["hourly_assessment"] = "Some PvP activity"
            else:
                result["hourly_assessment"] = "Low activity"

        return result

    except ImportError as e:
        return {
            "error": "activity_unavailable",
            "message": f"Activity module not available: {e}",
            "query_timestamp": query_ts,
        }
    except Exception as e:
        return {
            "error": "gatecamp_check_failed",
            "message": f"Gatecamp check failed: {e}",
            "query_timestamp": query_ts,
        }


def cmd_fw_frontlines(args: argparse.Namespace) -> dict:
    """
    Get current Faction Warfare frontline systems.

    Returns contested and vulnerable systems where fighting is active.
    """
    import asyncio

    query_ts = get_utc_timestamp()
    faction = getattr(args, "faction", None)

    # Load graph for system name resolution
    if not DEFAULT_GRAPH_PATH.exists():
        return {
            "error": "graph_not_found",
            "message": "Universe graph not available",
            "hint": "Run 'aria-esi graph-build' to generate it",
            "query_timestamp": query_ts,
        }

    try:
        universe = load_universe_graph(DEFAULT_GRAPH_PATH)
    except Exception as e:
        return {
            "error": "graph_load_failed",
            "message": f"Could not load universe graph: {e}",
            "query_timestamp": query_ts,
        }

    try:
        from ..mcp.activity import get_activity_cache, get_faction_id, get_faction_name

        cache = get_activity_cache()

        # Validate faction
        filter_faction_id = None
        if faction:
            filter_faction_id = get_faction_id(faction)
            if filter_faction_id is None:
                return {
                    "error": "invalid_faction",
                    "message": f"Unknown faction: {faction}",
                    "hint": "Valid factions: caldari, gallente, amarr, minmatar",
                    "query_timestamp": query_ts,
                }

        async def fetch_frontlines():
            fw_data = await cache.get_all_fw()

            contested = []
            vulnerable = []
            stable = []

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
                    contested_pct = (
                        fw_system.victory_points / fw_system.victory_points_threshold * 100
                    )
                else:
                    contested_pct = 0.0

                activity = await cache.get_activity(system_id)
                recent_kills = activity.ship_kills + activity.pod_kills

                fw_result = {
                    "name": universe.idx_to_name[idx],
                    "system_id": system_id,
                    "security": round(float(universe.security[idx]), 2),
                    "region": universe.get_region_name(idx),
                    "owner_faction": get_faction_name(fw_system.owner_faction_id),
                    "occupier_faction": get_faction_name(fw_system.occupier_faction_id),
                    "contested": fw_system.contested,
                    "contested_percentage": round(min(contested_pct, 100.0), 1),
                    "recent_kills": recent_kills if recent_kills > 0 else None,
                }

                if fw_system.contested == "vulnerable":
                    vulnerable.append(fw_result)
                elif fw_system.contested == "contested":
                    contested.append(fw_result)
                else:
                    stable.append(fw_result)

            contested.sort(key=lambda s: s["contested_percentage"], reverse=True)
            vulnerable.sort(key=lambda s: s["contested_percentage"], reverse=True)

            return contested, vulnerable, stable, cache.get_kills_cache_age()

        contested, vulnerable, stable, cache_age = asyncio.run(fetch_frontlines())

        return {
            "query_timestamp": query_ts,
            "volatility": "volatile",
            "faction_filter": faction,
            "frontlines": {
                "contested": contested,
                "vulnerable": vulnerable,
            },
            "summary": {
                "total_systems": len(contested) + len(vulnerable) + len(stable),
                "contested_count": len(contested),
                "vulnerable_count": len(vulnerable),
                "stable_count": len(stable),
            },
            "cache_age_seconds": cache_age,
        }

    except ImportError as e:
        return {
            "error": "activity_unavailable",
            "message": f"Activity module not available: {e}",
            "query_timestamp": query_ts,
        }
    except Exception as e:
        return {
            "error": "fw_frontlines_failed",
            "message": f"FW frontlines query failed: {e}",
            "query_timestamp": query_ts,
        }


def cmd_activity_cache_status(args: argparse.Namespace) -> dict:
    """
    Show activity cache status for diagnostics.
    """
    query_ts = get_utc_timestamp()

    try:
        from ..mcp.activity import get_activity_cache

        cache = get_activity_cache()
        status = cache.get_cache_status()

        return {
            "query_timestamp": query_ts,
            "cache_status": status,
        }

    except ImportError as e:
        return {
            "error": "activity_unavailable",
            "message": f"Activity module not available: {e}",
            "query_timestamp": query_ts,
        }
    except Exception as e:
        return {
            "error": "cache_status_failed",
            "message": f"Failed to get cache status: {e}",
            "query_timestamp": query_ts,
        }


def cmd_graph_stats(args: argparse.Namespace) -> dict:
    """
    Display universe graph statistics.

    Shows comprehensive statistics about the loaded graph.
    """
    query_ts = get_utc_timestamp()

    graph_path = Path(args.graph) if args.graph else DEFAULT_GRAPH_PATH

    if not graph_path.exists():
        return {
            "error": "graph_not_found",
            "message": f"Graph file not found: {graph_path}",
            "hint": "Run 'graph-build' first to create the graph",
            "query_timestamp": query_ts,
        }

    try:
        universe = load_universe_graph(graph_path)
    except Exception as e:
        return {
            "error": "load_failed",
            "message": f"Could not load graph: {e}",
            "query_timestamp": query_ts,
        }

    result = {
        "query_timestamp": query_ts,
        "version": universe.version,
        "graph_path": str(graph_path),
        "systems": {
            "total": universe.system_count,
            "highsec": len(universe.highsec_systems),
            "lowsec": len(universe.lowsec_systems),
            "nullsec": len(universe.nullsec_systems),
            "highsec_pct": round(100 * len(universe.highsec_systems) / universe.system_count, 1),
            "lowsec_pct": round(100 * len(universe.lowsec_systems) / universe.system_count, 1),
            "nullsec_pct": round(100 * len(universe.nullsec_systems) / universe.system_count, 1),
        },
        "stargates": universe.stargate_count,
        "border_systems": len(universe.border_systems),
        "regions": len(universe.region_names),
        "constellations": len(universe.constellation_names),
        "graph": {
            "vertices": universe.graph.vcount(),
            "edges": universe.graph.ecount(),
            "average_degree": round(2 * universe.graph.ecount() / universe.graph.vcount(), 2),
        },
    }

    # Add detailed stats if requested
    if args.detailed:
        # Top regions by system count
        region_counts = {}
        for rid, systems in universe.region_systems.items():
            name = universe.region_names.get(rid, f"Unknown ({rid})")
            region_counts[name] = len(systems)

        top_regions = sorted(region_counts.items(), key=lambda x: -x[1])[:10]
        result["top_regions"] = [{"name": name, "systems": count} for name, count in top_regions]

        # Sample path lengths
        import random

        samples = random.sample(range(universe.system_count), min(100, universe.system_count))
        if len(samples) >= 2:
            sample_paths = []
            for i in range(min(50, len(samples) - 1)):
                paths = universe.graph.get_shortest_paths(samples[i], samples[i + 1])
                if paths and paths[0]:
                    sample_paths.append(len(paths[0]) - 1)
            if sample_paths:
                result["sample_stats"] = {
                    "average_path_length": round(sum(sample_paths) / len(sample_paths), 1),
                    "min_path_length": min(sample_paths),
                    "max_path_length": max(sample_paths),
                    "sample_size": len(sample_paths),
                }

    return result


# =============================================================================
# Orient / Local Area Command
# =============================================================================


def cmd_orient(args: argparse.Namespace) -> dict:
    """
    Get local area intel for orientation in unknown space.

    Provides consolidated tactical intelligence including:
    - Threat summary (total kills, active camps)
    - Hotspots (high PvP activity systems to avoid)
    - Quiet zones (low activity for stealth ops)
    - Ratting banks (high NPC kills indicating targets)
    - Escape routes (nearest safer space)
    - Security borders (transition points)
    """
    import asyncio
    from collections import deque

    from ..core import get_utc_timestamp
    from ..universe import load_universe_graph

    system = args.system
    max_jumps = getattr(args, "max_jumps", 10)
    include_realtime = getattr(args, "realtime", False)
    query_ts = get_utc_timestamp()

    # Load universe graph
    try:
        universe = load_universe_graph()
    except Exception as e:
        return {
            "error": "graph_not_available",
            "message": str(e),
            "hint": "Run 'uv run aria-esi graph-build' to generate the graph.",
            "query_timestamp": query_ts,
        }

    # Resolve system name
    origin_idx = universe.resolve_name(system)
    if origin_idx is None:
        return {
            "error": "system_not_found",
            "message": f"Could not find system: {system}",
            "query_timestamp": query_ts,
        }

    async def fetch_local_area():
        from ..mcp.activity import classify_activity, get_activity_cache

        cache = get_activity_cache()
        all_activity = await cache.get_all_activity()

        # Get origin info
        origin_sec = float(universe.security[origin_idx])
        origin_sec_class = universe.security_class(origin_idx)
        origin_region = universe.get_region_name(origin_idx)
        origin_constellation = universe.get_constellation_name(origin_idx)

        # BFS to find all systems within range
        g = universe.graph
        visited: dict[int, int] = {origin_idx: 0}
        queue: deque[tuple[int, int]] = deque([(origin_idx, 0)])
        systems_in_range: list[tuple[int, int]] = []

        while queue:
            current_idx, distance = queue.popleft()
            if distance > 0:
                systems_in_range.append((current_idx, distance))

            if distance < max_jumps:
                for neighbor in g.neighbors(current_idx):
                    if neighbor not in visited:
                        visited[neighbor] = distance + 1
                        queue.append((neighbor, distance + 1))

        # Try to get real-time gatecamp data
        active_camps = []
        realtime_healthy = False
        if include_realtime:
            try:
                from ..services.redisq.threat_cache import get_threat_cache

                threat_cache = get_threat_cache()
                if threat_cache and threat_cache.is_healthy():
                    realtime_healthy = True
                    system_ids = [int(universe.system_ids[idx]) for idx, _ in systems_in_range]
                    system_names = {
                        int(universe.system_ids[idx]): universe.idx_to_name[idx]
                        for idx, _ in systems_in_range
                    }
                    realtime_data = threat_cache.get_activity_for_systems(system_ids, system_names)
                    for system_id, summary in realtime_data.items():
                        if summary.gatecamp:
                            active_camps.append(summary.gatecamp.system_name or str(system_id))
            except Exception:
                pass

        # Classify systems
        hotspots = []
        quiet_zones = []
        ratting_banks = []
        borders = []
        total_kills = 0
        total_pods = 0
        hotspot_count = 0

        for idx, distance in systems_in_range:
            system_id = int(universe.system_ids[idx])
            sec = float(universe.security[idx])
            sec_class = universe.security_class(idx)
            region = universe.get_region_name(idx)
            name = universe.idx_to_name[idx]

            activity = all_activity.get(system_id)
            ship_kills = activity.ship_kills if activity else 0
            pod_kills = activity.pod_kills if activity else 0
            npc_kills = activity.npc_kills if activity else 0
            ship_jumps = activity.ship_jumps if activity else 0
            pvp_kills = ship_kills + pod_kills

            total_kills += ship_kills
            total_pods += pod_kills

            activity_level = classify_activity(pvp_kills, "kills")

            system_info = {
                "system": name,
                "system_id": system_id,
                "security": sec,
                "security_class": sec_class,
                "region": region,
                "jumps": distance,
                "ship_kills": ship_kills,
                "pod_kills": pod_kills,
                "npc_kills": npc_kills,
                "ship_jumps": ship_jumps,
                "activity_level": activity_level,
            }

            # Classify
            if pvp_kills >= 5:
                reason = "gatecamp" if name in active_camps else "high activity"
                hotspots.append({**system_info, "reason": reason})
                hotspot_count += 1

            if pvp_kills == 0:
                quiet_zones.append(system_info)

            if npc_kills >= 100:
                ratting_banks.append({**system_info, "reason": "ratting bank"})

            # Check for security borders
            for neighbor_idx in g.neighbors(idx):
                if neighbor_idx in visited:
                    neighbor_sec = float(universe.security[neighbor_idx])
                    border_type = _classify_security_border(sec, neighbor_sec)
                    if border_type:
                        borders.append(
                            {
                                "system": name,
                                "system_id": system_id,
                                "security": sec,
                                "jumps": distance,
                                "border_type": border_type,
                                "adjacent_system": universe.idx_to_name[neighbor_idx],
                                "adjacent_security": neighbor_sec,
                            }
                        )

        # Sort results
        hotspots.sort(key=lambda s: s["ship_kills"] + s["pod_kills"], reverse=True)
        quiet_zones.sort(key=lambda s: s["jumps"])
        ratting_banks.sort(key=lambda s: s["npc_kills"], reverse=True)
        borders.sort(key=lambda s: s["jumps"])

        # Find escape routes
        escape_routes = []
        origin_class = "null" if origin_sec <= 0.0 else ("low" if origin_sec < 0.45 else "high")

        if origin_class == "null":
            for idx, distance in sorted(visited.items(), key=lambda x: x[1]):
                if idx == origin_idx:
                    continue
                sec = float(universe.security[idx])
                if 0.0 < sec < 0.45:
                    escape_routes.append(
                        {
                            "destination": universe.idx_to_name[idx],
                            "destination_type": "lowsec",
                            "jumps": distance,
                        }
                    )
                    break

        if origin_class in ("null", "low"):
            for idx, distance in sorted(visited.items(), key=lambda x: x[1]):
                if idx == origin_idx:
                    continue
                sec = float(universe.security[idx])
                if sec >= 0.45:
                    escape_routes.append(
                        {
                            "destination": universe.idx_to_name[idx],
                            "destination_type": "highsec",
                            "jumps": distance,
                        }
                    )
                    break

        # Determine threat level
        if len(active_camps) >= 3:
            threat_level = "EXTREME"
        elif len(active_camps) >= 1:
            threat_level = "HIGH"
        elif total_kills >= 50 or hotspot_count >= 5:
            threat_level = "HIGH"
        elif total_kills >= 20 or hotspot_count >= 2:
            threat_level = "MEDIUM"
        else:
            threat_level = "LOW"

        return {
            "origin": universe.idx_to_name[origin_idx],
            "origin_id": int(universe.system_ids[origin_idx]),
            "security": origin_sec,
            "security_class": origin_sec_class,
            "region": origin_region,
            "constellation": origin_constellation,
            "threat_summary": {
                "level": threat_level,
                "total_kills": total_kills,
                "total_pods": total_pods,
                "active_camps": active_camps,
                "hotspot_count": hotspot_count,
            },
            "hotspots": hotspots[:10],
            "quiet_zones": quiet_zones[:10],
            "ratting_banks": ratting_banks[:10],
            "escape_routes": escape_routes,
            "borders": borders[:10],
            "systems_scanned": len(systems_in_range),
            "search_radius": max_jumps,
            "cache_age_seconds": cache.get_kills_cache_age(),
            "realtime_healthy": realtime_healthy,
        }

    try:
        result = asyncio.run(fetch_local_area())
        return {
            "query_timestamp": query_ts,
            "volatility": "volatile",
            "data_period": "last_hour",
            **result,
        }
    except Exception as e:
        return {
            "error": "orient_failed",
            "message": f"Local area analysis failed: {e}",
            "query_timestamp": query_ts,
        }


def _classify_security_border(sec: float, neighbor_sec: float) -> str | None:
    """Classify the type of security border between two systems."""

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

    border_map = {
        ("null", "low"): "null_to_low",
        ("low", "high"): "low_to_high",
        ("high", "low"): "high_to_low",
        ("low", "null"): "low_to_null",
    }

    return border_map.get((from_class, to_class))


# =============================================================================
# Argument Parser Registration
# =============================================================================


def register_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Register universe command parsers."""

    # Border systems command
    borders_parser = subparsers.add_parser(
        "borders",
        help="Find high-sec systems bordering low-sec (cached)",
    )
    borders_parser.add_argument(
        "--region",
        "-r",
        help="Search within a specific region",
    )
    borders_parser.add_argument(
        "--system",
        "-s",
        help="Find nearest border systems to this system",
    )
    borders_parser.add_argument(
        "--limit",
        "-n",
        type=int,
        default=10,
        help="Max results for proximity search (default: 10)",
    )
    borders_parser.set_defaults(func=cmd_borders)

    # Loop planning command
    loop_parser = subparsers.add_parser(
        "loop",
        help="Plan circular mining route through border systems",
    )
    loop_parser.add_argument(
        "origin",
        help="Starting/ending system for the loop",
    )
    loop_parser.add_argument(
        "--target-jumps",
        "-j",
        type=int,
        default=20,
        help="Target loop length in jumps (default: 20)",
    )
    loop_parser.add_argument(
        "--min-borders",
        type=int,
        default=3,
        help="Minimum border systems to visit (default: 3)",
    )
    loop_parser.add_argument(
        "--max-borders",
        type=int,
        default=6,
        help="Maximum border systems to visit (default: 6)",
    )
    loop_parser.add_argument(
        "--security",
        dest="security_filter",
        choices=["highsec", "lowsec", "any"],
        default="highsec",
        help="Security constraint for route (default: highsec)",
    )
    loop_parser.add_argument(
        "--avoid",
        nargs="+",
        help="Systems to avoid (e.g., --avoid Uedama Niarja)",
    )
    loop_parser.set_defaults(func=cmd_loop)

    # Cache info command
    cache_parser = subparsers.add_parser(
        "cache-info",
        help="Show universe cache status",
    )
    cache_parser.set_defaults(func=cmd_cache_info)

    # System info command (cached)
    sysinfo_parser = subparsers.add_parser(
        "sysinfo",
        help="Look up system info from cache",
    )
    sysinfo_parser.add_argument(
        "system",
        help="System name to look up",
    )
    sysinfo_parser.set_defaults(func=cmd_system_info)

    # Graph build command (STP-011)
    graph_build_parser = subparsers.add_parser(
        "graph-build",
        help="Build universe graph from JSON cache",
    )
    graph_build_parser.add_argument(
        "--cache",
        "-c",
        help=f"Path to universe_cache.json (default: {DEFAULT_CACHE_PATH})",
    )
    graph_build_parser.add_argument(
        "--output",
        "-o",
        help=f"Output path for universe graph (.universe) (default: {DEFAULT_GRAPH_PATH})",
    )
    graph_build_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Overwrite existing output file",
    )
    graph_build_parser.add_argument(
        "--update-checksum",
        action="store_true",
        help="Update checksum in data-sources.json after build (recommended)",
    )
    graph_build_parser.set_defaults(func=cmd_graph_build)

    # Graph verify command (STP-011)
    graph_verify_parser = subparsers.add_parser(
        "graph-verify",
        help="Verify universe graph integrity",
    )
    graph_verify_parser.add_argument(
        "--graph",
        "-g",
        help=f"Path to universe graph (.universe) (default: {DEFAULT_GRAPH_PATH})",
    )
    graph_verify_parser.set_defaults(func=cmd_graph_verify)

    # Graph stats command (STP-011)
    graph_stats_parser = subparsers.add_parser(
        "graph-stats",
        help="Display universe graph statistics",
    )
    graph_stats_parser.add_argument(
        "--graph",
        "-g",
        help=f"Path to universe graph (.universe) (default: {DEFAULT_GRAPH_PATH})",
    )
    graph_stats_parser.add_argument(
        "--detailed",
        "-d",
        action="store_true",
        help="Show detailed statistics (regions, path lengths)",
    )
    graph_stats_parser.set_defaults(func=cmd_graph_stats)

    # Activity overlay commands (STP-013)
    activity_parser = subparsers.add_parser(
        "activity-systems",
        help="Get activity data for specified systems",
    )
    activity_parser.add_argument(
        "systems",
        nargs="+",
        help="System names to query (e.g., Tama Amamake Rancer)",
    )
    activity_parser.add_argument(
        "--realtime",
        "-r",
        action="store_true",
        help="Include real-time kill data and gatecamp detection (requires RedisQ poller)",
    )
    activity_parser.set_defaults(func=cmd_activity_systems)

    hotspots_parser = subparsers.add_parser(
        "hotspots",
        help="Find high-activity systems near an origin",
    )
    hotspots_parser.add_argument(
        "origin",
        help="Origin system for search",
    )
    hotspots_parser.add_argument(
        "--max-jumps",
        "-j",
        type=int,
        default=15,
        help="Maximum distance to search (default: 15)",
    )
    hotspots_parser.add_argument(
        "--type",
        dest="activity_type",
        choices=["kills", "jumps", "ratting"],
        default="kills",
        help="Activity type to measure (default: kills)",
    )
    hotspots_parser.add_argument(
        "--min-security",
        type=float,
        help="Minimum security status filter",
    )
    hotspots_parser.add_argument(
        "--max-security",
        type=float,
        help="Maximum security status filter",
    )
    hotspots_parser.add_argument(
        "--limit",
        "-n",
        type=int,
        default=10,
        help="Maximum systems to return (default: 10)",
    )
    hotspots_parser.set_defaults(func=cmd_hotspots)

    gatecamp_parser = subparsers.add_parser(
        "gatecamp-risk",
        help="Analyze gatecamp risk along a route",
    )
    gatecamp_parser.add_argument(
        "origin",
        help="Origin system",
    )
    gatecamp_parser.add_argument(
        "destination",
        help="Destination system",
    )
    gatecamp_parser.add_argument(
        "--mode",
        choices=["shortest", "safe", "unsafe"],
        default="safe",
        help="Route calculation mode (default: safe)",
    )
    gatecamp_parser.add_argument(
        "--realtime",
        "-r",
        action="store_true",
        help="Use real-time kill data for active gatecamp detection (requires RedisQ poller)",
    )
    gatecamp_parser.set_defaults(func=cmd_gatecamp_risk)

    # Single-system gatecamp check
    gatecamp_single_parser = subparsers.add_parser(
        "gatecamp",
        help="Check for active gatecamp in a single system",
    )
    gatecamp_single_parser.add_argument(
        "system",
        help="System name to check (e.g., Niarja)",
    )
    gatecamp_single_parser.set_defaults(func=cmd_gatecamp)

    fw_parser = subparsers.add_parser(
        "fw-frontlines",
        help="Get Faction Warfare contested systems",
    )
    fw_parser.add_argument(
        "--faction",
        "-f",
        choices=["caldari", "gallente", "amarr", "minmatar"],
        help="Filter to specific faction",
    )
    fw_parser.set_defaults(func=cmd_fw_frontlines)

    cache_status_parser = subparsers.add_parser(
        "activity-cache-status",
        help="Show activity cache status",
    )
    cache_status_parser.set_defaults(func=cmd_activity_cache_status)

    # Orient / Local Area command
    orient_parser = subparsers.add_parser(
        "orient",
        help="Get local area intel for orientation in unknown space",
    )
    orient_parser.add_argument(
        "system",
        help="Current system for orientation (e.g., after wormhole/filament)",
    )
    orient_parser.add_argument(
        "--max-jumps",
        "-j",
        type=int,
        default=10,
        help="Search radius in jumps (default: 10)",
    )
    orient_parser.add_argument(
        "--realtime",
        "-r",
        action="store_true",
        help="Include real-time gatecamp detection (requires RedisQ poller)",
    )
    orient_parser.set_defaults(func=cmd_orient)
