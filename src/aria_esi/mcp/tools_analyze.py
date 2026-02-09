"""
Analyze Tool Implementation for MCP Universe Server.

Provides the universe_analyze tool for detailed security analysis of a route
or system sequence. Identifies chokepoints, danger zones, and provides
tactical intelligence for route planning.

STP-010: Analyze Tool (universe_analyze)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .errors import InvalidParameterError, RouteNotFoundError
from .models import DangerZone, RouteAnalysis, SecuritySummary, SystemInfo
from .tools import get_universe
from .utils import build_system_info

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from ..universe.graph import UniverseGraph


def register_analyze_tools(server: FastMCP, universe: UniverseGraph) -> None:
    """
    Register route analysis tools with MCP server.

    Args:
        server: MCP Server instance
        universe: UniverseGraph for route analysis
    """

    @server.tool()
    async def universe_analyze(systems: list[str]) -> dict:
        """
        Analyze security profile of a route or system list.

        PREFER THIS TOOL over writing custom security analysis scripts.
        Automatically identifies tactical concerns like chokepoints and
        danger zones that require special attention.

        Args:
            systems: Ordered list of system names representing a route

        Returns:
            RouteAnalysis with:
            - security_summary: Counts of high/low/null systems, lowest security point
            - chokepoints: Systems where security transitions occur (gatecamp risk)
            - danger_zones: Contiguous low/null segments with jump counts

        Example:
            universe_analyze(["Jita", "Perimeter", "Urlen", "Sirppala"])
        """
        universe = get_universe()

        if len(systems) < 2:
            raise InvalidParameterError(
                "systems",
                systems,
                "At least 2 systems required for analysis",
            )

        # Resolve all system names
        indices: list[int] = []
        for name in systems:
            idx = universe.resolve_name(name)
            if idx is None:
                raise InvalidParameterError(
                    "systems",
                    name,
                    f"Unknown system: {name}",
                )
            indices.append(idx)

        # Validate route connectivity
        _validate_connectivity(universe, indices, systems)

        # Build analysis
        result = _analyze_route(universe, indices)

        return result.model_dump()


def _validate_connectivity(
    universe: UniverseGraph,
    indices: list[int],
    names: list[str],
) -> None:
    """
    Validate that consecutive systems are connected by stargate.

    Args:
        universe: UniverseGraph for neighbor lookups
        indices: List of vertex indices
        names: Original system names for error messages

    Raises:
        RouteNotFoundError: If systems aren't connected by stargate
    """
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
    """
    Build complete route analysis.

    Args:
        universe: UniverseGraph for system lookups
        indices: List of vertex indices representing the route

    Returns:
        RouteAnalysis with all computed fields
    """
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
    """
    Compute security breakdown for route.

    Counts systems by security class and identifies the lowest security
    system in the route.

    Args:
        universe: UniverseGraph for security lookups
        indices: List of vertex indices

    Returns:
        SecuritySummary with counts and lowest security info
    """
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
    """
    Find chokepoints: points where route transitions security class.

    A chokepoint is a system where:
    - Previous system is high-sec AND current is low/null (entry point)
    - Previous system is low/null AND current is high-sec (exit point)

    These are typically where gatecamps occur.

    Args:
        universe: UniverseGraph for security lookups
        indices: List of vertex indices

    Returns:
        List of SystemInfo for chokepoint systems
    """
    chokepoints: list[SystemInfo] = []

    for i in range(1, len(indices)):
        prev_idx = indices[i - 1]
        curr_idx = indices[i]

        prev_class = universe.security_class(prev_idx)
        curr_class = universe.security_class(curr_idx)

        # Entry to dangerous space (the dangerous system is the chokepoint)
        if prev_class == "HIGH" and curr_class in ("LOW", "NULL"):
            chokepoints.append(build_system_info(universe, curr_idx))

        # Exit from dangerous space (the last dangerous system is the chokepoint)
        elif prev_class in ("LOW", "NULL") and curr_class == "HIGH":
            chokepoints.append(build_system_info(universe, prev_idx))

    return chokepoints


def _find_danger_zones(
    universe: UniverseGraph,
    indices: list[int],
) -> list[DangerZone]:
    """
    Find danger zones: consecutive segments in low/null-sec.

    A danger zone is a contiguous sequence of systems with security < 0.45.
    These zones help capsuleers plan defensive measures like scouts or
    webbing alts.

    Args:
        universe: UniverseGraph for security lookups
        indices: List of vertex indices

    Returns:
        List of DangerZone objects with start/end systems and stats
    """
    danger_zones: list[DangerZone] = []
    in_danger = False
    zone_start: int | None = None
    zone_min_sec = 1.0

    for i, idx in enumerate(indices):
        sec = float(universe.security[idx])
        is_dangerous = sec < 0.45

        if is_dangerous and not in_danger:
            # Entering danger zone
            in_danger = True
            zone_start = i
            zone_min_sec = sec

        elif is_dangerous and in_danger:
            # Continuing in danger zone
            zone_min_sec = min(zone_min_sec, sec)

        elif not is_dangerous and in_danger:
            # Exiting danger zone
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

    # Handle case where route ends in danger zone
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
