"""
ARIA ESI Navigation Commands

Route planning and system activity intelligence.
All commands are public (no authentication required).

REFACTORED: Route command now uses local UniverseGraph for O(1) pathfinding
instead of ESI /route/ endpoint. This eliminates network latency and provides
consistent routing with MCP tools.

REFACTORED: Activity command now uses cached data with O(1) lookups instead
of fetching entire global datasets for each query. Cache TTL is 10 minutes.

UNIFIED: Route calculation now uses shared NavigationService for consistency
with MCP tools. CLI gains --avoid parameter support.
"""

import argparse
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from ..core import (
    ESIClient,
    get_utc_timestamp,
)
from ..services.navigation import (
    NavigationService,
    compute_security_summary,
    generate_warnings,
    get_threat_level,
)
from ..universe import UniverseBuildError, load_universe_graph

# =============================================================================
# Activity Data Cache (avoids fetching entire global dataset per query)
# =============================================================================

# Cache TTL in seconds (10 minutes, matching MCP activity cache)
ACTIVITY_CACHE_TTL = 600


@dataclass
class CachedActivityData:
    """Cached activity data for a single system."""

    ship_kills: int = 0
    pod_kills: int = 0
    npc_kills: int = 0
    ship_jumps: int = 0


@dataclass
class ActivityCache:
    """
    Module-level cache for ESI activity data.

    Fetches galaxy-wide kills/jumps data once, caches for TTL period.
    Subsequent lookups are O(1) dict access instead of O(n) list iteration.
    """

    kills_data: dict[int, CachedActivityData] = field(default_factory=dict)
    jumps_data: dict[int, int] = field(default_factory=dict)
    kills_timestamp: float = 0
    jumps_timestamp: float = 0

    def is_kills_stale(self) -> bool:
        """Check if kills cache needs refresh."""
        return time.time() - self.kills_timestamp > ACTIVITY_CACHE_TTL

    def is_jumps_stale(self) -> bool:
        """Check if jumps cache needs refresh."""
        return time.time() - self.jumps_timestamp > ACTIVITY_CACHE_TTL

    def refresh_kills(self, client: ESIClient) -> None:
        """Fetch and cache global kills data."""
        data = client.get_safe("/universe/system_kills/", default=[])
        if isinstance(data, list):
            self.kills_data = {
                entry["system_id"]: CachedActivityData(
                    ship_kills=entry.get("ship_kills", 0),
                    pod_kills=entry.get("pod_kills", 0),
                    npc_kills=entry.get("npc_kills", 0),
                )
                for entry in data
            }
            self.kills_timestamp = time.time()

    def refresh_jumps(self, client: ESIClient) -> None:
        """Fetch and cache global jumps data."""
        data = client.get_safe("/universe/system_jumps/", default=[])
        if isinstance(data, list):
            self.jumps_data = {entry["system_id"]: entry.get("ship_jumps", 0) for entry in data}
            self.jumps_timestamp = time.time()

    def get_activity(self, system_id: int, client: ESIClient) -> CachedActivityData:
        """
        Get activity data for a system, refreshing cache if stale.

        Args:
            system_id: EVE system ID
            client: ESI client for refresh calls

        Returns:
            CachedActivityData with kills and jumps (zeros if no activity)
        """
        # Refresh stale caches
        if self.is_kills_stale():
            self.refresh_kills(client)
        if self.is_jumps_stale():
            self.refresh_jumps(client)

        # O(1) lookup from cached dict
        kills = self.kills_data.get(system_id, CachedActivityData())
        jumps = self.jumps_data.get(system_id, 0)

        return CachedActivityData(
            ship_kills=kills.ship_kills,
            pod_kills=kills.pod_kills,
            npc_kills=kills.npc_kills,
            ship_jumps=jumps,
        )


# Module-level singleton cache
_activity_cache: Optional[ActivityCache] = None


def get_activity_cache() -> ActivityCache:
    """Get or create the activity cache singleton."""
    global _activity_cache
    if _activity_cache is None:
        _activity_cache = ActivityCache()
    return _activity_cache


def reset_navigation_activity_cache() -> None:
    """Reset the navigation activity cache singleton (for testing)."""
    global _activity_cache
    _activity_cache = None


# =============================================================================
# Route Command
# =============================================================================


def cmd_route(args: argparse.Namespace) -> dict[str, Any]:
    """
    Calculate route between two solar systems using local graph.

    Uses pre-built UniverseGraph and NavigationService for O(1) pathfinding
    instead of ESI API calls. This provides microsecond response times vs
    seconds for network calls.

    Args:
        args: Parsed arguments with origin, destination, route_flag, avoid

    Returns:
        Route data dict with systems, security summary, threat assessment
    """
    origin = args.origin
    destination = args.destination
    route_flag = getattr(args, "route_flag", "shortest")
    avoid_systems = getattr(args, "avoid", None) or []
    query_ts = get_utc_timestamp()

    # Load universe graph
    try:
        universe = load_universe_graph()
    except UniverseBuildError as e:
        return {
            "error": "graph_not_available",
            "message": str(e),
            "hint": "Run 'uv run aria-esi universe --build' to generate the graph.",
            "query_timestamp": query_ts,
        }

    # Create navigation service
    nav_service = NavigationService(universe)

    # Resolve origin system
    origin_idx = universe.resolve_name(origin)
    if origin_idx is None:
        return {
            "error": "system_not_found",
            "message": f"Could not find system: {origin}",
            "hint": "Check spelling. System names are case-insensitive.",
            "query_timestamp": query_ts,
        }

    # Resolve destination system
    dest_idx = universe.resolve_name(destination)
    if dest_idx is None:
        return {
            "error": "system_not_found",
            "message": f"Could not find system: {destination}",
            "hint": "Check spelling. System names are case-insensitive.",
            "query_timestamp": query_ts,
        }

    # Check for same system
    if origin_idx == dest_idx:
        origin_info = _get_system_info_from_graph(universe, origin_idx)
        return {
            "error": "same_system",
            "message": "Origin and destination are the same system",
            "system": origin_info,
            "query_timestamp": query_ts,
        }

    # Resolve avoid_systems to indices
    avoid_indices: set[int] | None = None
    unresolved_avoids: list[str] = []
    warnings: list[str] = []

    if avoid_systems:
        avoid_indices, unresolved_avoids = nav_service.resolve_avoid_systems(avoid_systems)
        if unresolved_avoids:
            warnings.append(f"Unknown systems in --avoid: {', '.join(unresolved_avoids)}")

    # Map CLI route flags to graph routing modes
    # CLI uses: shortest, secure, insecure
    # Graph uses: shortest, safe, unsafe
    mode_map = {
        "shortest": "shortest",
        "secure": "safe",
        "insecure": "unsafe",
    }
    graph_mode = mode_map.get(route_flag, "shortest")

    # Calculate route using NavigationService
    path = nav_service.calculate_route(origin_idx, dest_idx, graph_mode, avoid_indices)  # type: ignore[arg-type]

    if not path:
        # Check if origin or destination is in wormhole space (J-space)
        origin_name = universe.idx_to_name[origin_idx]
        dest_name = universe.idx_to_name[dest_idx]
        hint = None
        if origin_name.startswith("J") and origin_name[1:].isdigit():
            hint = "Wormhole (J-space) systems have no permanent stargate connections"
        elif dest_name.startswith("J") and dest_name[1:].isdigit():
            hint = "Wormhole (J-space) systems have no permanent stargate connections"
        elif avoid_indices:
            hint = "Route may be blocked by avoided systems. Try removing some from --avoid."

        result: dict[str, Any] = {
            "error": "no_route",
            "message": f"No route available from {origin} to {destination}",
            "query_timestamp": query_ts,
        }
        if hint:
            result["hint"] = hint
        if warnings:
            result["warnings"] = warnings
        return result

    # Build system info for each vertex in path
    systems = [_get_system_info_from_graph(universe, idx) for idx in path]

    # Use shared utilities for security summary and warnings
    summary = compute_security_summary(universe, path)
    route_warnings = generate_warnings(universe, path, graph_mode)
    warnings.extend(route_warnings)

    # Determine threat level using shared function
    threat_level = get_threat_level(
        summary.highsec_jumps, summary.lowsec_jumps, summary.nullsec_jumps, summary.lowest_security
    )

    # Route mode display names
    mode_names = {
        "shortest": "Shortest",
        "secure": "Secure (high-sec priority)",
        "insecure": "Risky (low-sec/null preferred)",
    }

    result = {
        "query_timestamp": query_ts,
        "volatility": "stable",
        "origin": systems[0] if systems else None,
        "destination": systems[-1] if systems else None,
        "route_mode": route_flag,
        "route_mode_display": mode_names.get(route_flag, route_flag),
        "total_jumps": summary.total_jumps,
        "systems": systems,
        "security_summary": {
            "high_sec": summary.highsec_jumps,
            "low_sec": summary.lowsec_jumps,
            "null_sec": summary.nullsec_jumps,
            "lowest_security": round(summary.lowest_security, 2),
            "lowest_security_system": summary.lowest_security_system,
            "threat_level": threat_level,
        },
    }

    if warnings:
        result["warnings"] = warnings
    if avoid_systems:
        result["avoided_systems"] = [s for s in avoid_systems if s not in unresolved_avoids]

    return result


def _get_full_system_info(client: ESIClient, system_id: int) -> Optional[dict]:
    """Get system info including constellation and region via ESI (used by activity command)."""
    system = client.get_dict_safe(f"/universe/systems/{system_id}/")
    if not system:
        return None

    # Get constellation for region
    constellation_id = system.get("constellation_id")
    constellation = (
        client.get_dict_safe(f"/universe/constellations/{constellation_id}/")
        if constellation_id
        else None
    )

    region_id = constellation.get("region_id") if constellation else None
    region = client.get_dict_safe(f"/universe/regions/{region_id}/") if region_id else None

    return {
        "system_id": system_id,
        "name": system.get("name", "Unknown"),
        "security": round(system.get("security_status", 0), 2),
        "constellation": constellation.get("name", "Unknown") if constellation else "Unknown",
        "region": region.get("name", "Unknown") if region else "Unknown",
    }


# =============================================================================
# Local Graph Helpers (O(1) lookups, no network calls)
# =============================================================================


def _get_system_info_from_graph(universe, idx: int) -> dict:
    """
    Get system info from UniverseGraph (O(1) lookup, no network call).

    Args:
        universe: UniverseGraph instance
        idx: Vertex index in the graph

    Returns:
        System info dict matching ESI output format
    """
    return {
        "system_id": universe.get_system_id(idx),
        "name": universe.idx_to_name[idx],
        "security": round(float(universe.security[idx]), 2),
        "constellation": universe.get_constellation_name(idx),
        "region": universe.get_region_name(idx),
    }


# =============================================================================
# Activity Command
# =============================================================================


def cmd_activity(args: argparse.Namespace) -> dict[str, Any]:
    """
    Get live system activity intel (kills, jumps).

    Uses cached activity data with 10-minute TTL for O(1) lookups instead of
    fetching entire global datasets for each query.

    Args:
        args: Parsed arguments with system name

    Returns:
        Activity data dict with kills, jumps, threat assessment
    """
    system_name = args.system
    client = ESIClient()
    query_ts = get_utc_timestamp()

    # Resolve system name to ID
    result = client.resolve_names([system_name])
    systems = result.get("systems", [])

    if not systems:
        return {
            "error": "system_not_found",
            "message": f"Could not find system: {system_name}",
            "hint": "Check spelling. System names are case-insensitive.",
            "query_timestamp": query_ts,
        }

    system_id = systems[0]["id"]
    resolved_name = systems[0]["name"]

    # Get system info
    system_info = client.get_dict_safe(f"/universe/systems/{system_id}/")
    security = round(system_info.get("security_status", 0), 2) if system_info else 0

    # Get activity from cache (O(1) lookup, auto-refreshes if stale)
    cache = get_activity_cache()
    activity = cache.get_activity(system_id, client)

    # Calculate threat indicators
    pvp_kills = activity.ship_kills + activity.pod_kills

    # Threat level and factors
    threat_level, threat_factors = _calculate_threat(
        security, pvp_kills, activity.npc_kills, activity.ship_jumps
    )

    # Activity assessment
    activity_assessment = _get_activity_assessment(
        security, pvp_kills, activity.npc_kills, activity.ship_jumps
    )

    return {
        "query_timestamp": query_ts,
        "volatility": "volatile",
        "data_period": "last_hour",
        "system": {"id": system_id, "name": resolved_name, "security_status": security},
        "activity": {
            "ship_kills": activity.ship_kills,
            "pod_kills": activity.pod_kills,
            "npc_kills": activity.npc_kills,
            "total_pvp_kills": pvp_kills,
            "jumps": activity.ship_jumps,
        },
        "threat_assessment": {
            "level": threat_level,
            "factors": threat_factors,
            "assessment": activity_assessment,
        },
    }


def _calculate_threat(
    security: float, pvp_kills: int, npc_kills: int, jumps: int
) -> tuple[str, list]:
    """Calculate threat level and factors based on system data."""
    threat_level = "MINIMAL"
    threat_factors = []

    # Security-based threat
    if security <= 0:
        threat_level = "CRITICAL"
        threat_factors.append("Null-sec or wormhole space - no CONCORD")
    elif security < 0.5:
        threat_level = "HIGH"
        threat_factors.append("Low-sec - no CONCORD protection")
    elif security == 0.5:
        threat_level = "ELEVATED"
        threat_factors.append("Sec 0.5 - suicide ganking viable")

    # Activity-based threat escalation
    if pvp_kills >= 50:
        if threat_level in ["MINIMAL", "ELEVATED"]:
            threat_level = "HIGH"
        threat_factors.append(f"Very high PvP activity: {pvp_kills} ship/pod kills in last hour")
    elif pvp_kills >= 20:
        if threat_level == "MINIMAL":
            threat_level = "ELEVATED"
        threat_factors.append(f"Elevated PvP activity: {pvp_kills} ship/pod kills in last hour")
    elif pvp_kills >= 5:
        threat_factors.append(f"Moderate PvP activity: {pvp_kills} ship/pod kills in last hour")
    elif pvp_kills > 0:
        threat_factors.append(f"Some PvP activity: {pvp_kills} kills in last hour")

    # Jump traffic analysis
    if jumps >= 1000:
        threat_factors.append(f"Very high traffic: {jumps} jumps/hour (major trade hub)")
    elif jumps >= 500:
        threat_factors.append(f"High traffic: {jumps} jumps/hour")
    elif jumps >= 100:
        threat_factors.append(f"Moderate traffic: {jumps} jumps/hour")
    elif jumps > 0:
        threat_factors.append(f"Low traffic: {jumps} jumps/hour")
    else:
        threat_factors.append("Minimal traffic - system appears quiet")

    return threat_level, threat_factors


def _get_activity_assessment(security: float, pvp_kills: int, npc_kills: int, jumps: int) -> str:
    """Generate human-readable activity assessment."""
    if pvp_kills >= 20 and security < 0.5:
        return "Active PvP zone - gate camps likely"
    elif pvp_kills >= 10:
        return "PvP hotspot - exercise caution"
    elif pvp_kills >= 5 and security <= 0.5:
        return "Some combat activity - stay alert"
    elif npc_kills >= 100:
        return "Active ratting/mission running area"
    elif jumps >= 500:
        return "High-traffic system - busy but typically safe"
    elif jumps < 10 and pvp_kills == 0:
        return "Quiet system - minimal activity"
    else:
        return "Normal activity levels"


# =============================================================================
# Argument Parser Registration
# =============================================================================


def register_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Register navigation command parsers."""

    # Route command
    route_parser = subparsers.add_parser("route", help="Calculate route between systems")
    route_parser.add_argument("origin", help="Origin system name")
    route_parser.add_argument("destination", help="Destination system name")
    route_parser.add_argument(
        "--safe",
        "--secure",
        action="store_const",
        const="secure",
        dest="route_flag",
        help="Prefer high-sec route",
    )
    route_parser.add_argument(
        "--shortest",
        action="store_const",
        const="shortest",
        dest="route_flag",
        help="Shortest route (default)",
    )
    route_parser.add_argument(
        "--risky",
        "--insecure",
        "--unsafe",
        action="store_const",
        const="insecure",
        dest="route_flag",
        help="Prefer low-sec/null route",
    )
    route_parser.add_argument(
        "--avoid",
        nargs="+",
        metavar="SYSTEM",
        help="Systems to avoid (e.g., --avoid Uedama Niarja)",
    )
    route_parser.set_defaults(route_flag="shortest", func=cmd_route)

    # Activity command
    activity_parser = subparsers.add_parser("activity", help="Get live system activity intel")
    activity_parser.add_argument("system", help="System name to check")
    activity_parser.set_defaults(func=cmd_activity)
