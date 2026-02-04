"""
Borders Tool Implementation for MCP Universe Server.

Provides the universe_borders tool for finding high-sec systems that border
low-sec space. Essential for mining expedition planning and border patrol
operations.

STP-007: Borders Tool (universe_borders)
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

from .context_policy import UNIVERSE
from .errors import InvalidParameterError
from .models import BorderSystem
from .tools import collect_corrections, get_universe, resolve_system_name

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from ..universe.graph import UniverseGraph


# Parameter limits - imported from context_policy for centralized management
MAX_LIMIT = UNIVERSE.BORDERS_MAX_LIMIT
MAX_JUMPS = UNIVERSE.BORDERS_MAX_JUMPS


def register_borders_tools(server: FastMCP, universe: UniverseGraph) -> None:
    """
    Register border discovery tools with MCP server.

    Args:
        server: MCP Server instance
        universe: UniverseGraph for border lookups
    """

    @server.tool()
    async def universe_borders(
        origin: str,
        limit: int = 10,
        max_jumps: int = 15,
    ) -> dict:
        """
        Find high-sec systems that border low-sec space.

        PREFER THIS TOOL over writing custom BFS scripts to find border systems.
        Uses pre-indexed border data for fast lookups. Essential for planning
        mining expeditions to empire border ore sites.

        Args:
            origin: Starting system for distance calculation
            limit: Maximum systems to return (default: 10, max: 50)
            max_jumps: Maximum search radius (default: 15, max: 30)

        Returns:
            Dictionary containing:
            - origin: The origin system name
            - borders: List of BorderSystem objects sorted by distance
              (includes adjacent_lowsec showing which low-sec systems are accessible)
            - total_found: Number of border systems found
            - search_radius: The max_jumps value used

        Example:
            universe_borders("Dodixie", limit=5)
        """
        # Validate parameters
        if limit < 1 or limit > MAX_LIMIT:
            raise InvalidParameterError("limit", limit, f"Must be between 1 and {MAX_LIMIT}")
        if max_jumps < 1 or max_jumps > MAX_JUMPS:
            raise InvalidParameterError(
                "max_jumps", max_jumps, f"Must be between 1 and {MAX_JUMPS}"
            )

        universe = get_universe()
        origin_resolved = resolve_system_name(origin)
        corrections = collect_corrections(origin_resolved)

        # Find borders using BFS
        borders = _find_border_systems(universe, origin_resolved.idx, limit, max_jumps)

        return {
            "origin": origin_resolved.canonical_name,
            "borders": [b.model_dump() for b in borders],
            "total_found": len(borders),
            "search_radius": max_jumps,
            "corrections": corrections,
        }


def _find_border_systems(
    universe: UniverseGraph,
    origin_idx: int,
    limit: int,
    max_jumps: int,
) -> list[BorderSystem]:
    """
    Find border systems using BFS with distance tracking.

    This version only traverses high-sec systems, which is faster
    and more relevant for mining/PI operations.

    Algorithm:
    1. BFS from origin, tracking distance
    2. Only expand through high-sec neighbors
    3. Check each visited system for border status
    4. Collect borders until limit reached or max_jumps exceeded
    5. Sort by distance and return top N

    Args:
        universe: UniverseGraph for lookups
        origin_idx: Starting vertex index
        limit: Maximum border systems to return
        max_jumps: Maximum search radius

    Returns:
        List of BorderSystem objects sorted by distance.
    """
    g = universe.graph
    border_results: list[tuple[int, int]] = []

    # BFS with distance tracking
    visited: dict[int, int] = {origin_idx: 0}
    queue: deque[tuple[int, int]] = deque([(origin_idx, 0)])

    # Gather extra for better sorting (may find closer ones later in BFS)
    gather_limit = limit * 3

    while queue:
        vertex, dist = queue.popleft()

        # Stop expanding beyond max_jumps
        if dist > max_jumps:
            continue

        # Check if this is a border system
        if vertex in universe.border_systems:
            border_results.append((vertex, dist))
            # Early exit if we have enough
            if len(border_results) >= gather_limit:
                break

        # Only expand through high-sec neighbors
        for neighbor in g.neighbors(vertex):
            if neighbor not in visited:
                # Only queue high-sec systems for traversal
                if universe.security[neighbor] >= 0.45:
                    visited[neighbor] = dist + 1
                    queue.append((neighbor, dist + 1))

    # Sort by distance, take top N
    border_results.sort(key=lambda x: x[1])
    border_results = border_results[:limit]

    # Build BorderSystem objects
    return [_build_border_system(universe, idx, dist) for idx, dist in border_results]


def _build_border_system(
    universe: UniverseGraph,
    idx: int,
    jumps_from_origin: int,
) -> BorderSystem:
    """
    Build BorderSystem object for a vertex.

    Args:
        universe: UniverseGraph for lookups
        idx: Vertex index
        jumps_from_origin: Distance from the origin system

    Returns:
        BorderSystem with all fields populated
    """
    # Get adjacent low-sec systems
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
