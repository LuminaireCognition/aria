"""
Border System Search.

Provides BFS-based border system discovery for loop planning.
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from ...universe.graph import UniverseGraph


SecurityFilter = Literal["highsec", "lowsec", "any"]

# Security thresholds for classification
HIGHSEC_THRESHOLD = 0.45
LOWSEC_THRESHOLD = 0.0


def get_security_threshold(security_filter: SecurityFilter) -> float:
    """
    Get the minimum security threshold for a security filter.

    Args:
        security_filter: The security filter type

    Returns:
        Minimum security value for traversable systems
    """
    if security_filter == "highsec":
        return HIGHSEC_THRESHOLD
    elif security_filter == "lowsec":
        return LOWSEC_THRESHOLD
    else:  # "any"
        return -1.0  # Allow everything


def find_borders_with_distance(
    universe: UniverseGraph,
    origin_idx: int,
    limit: int,
    max_jumps: int,
    security_filter: SecurityFilter = "highsec",
    avoid_systems: set[int] | None = None,
) -> list[tuple[int, int]]:
    """
    Find border systems with their distances from origin using BFS.

    Traversal is constrained by security_filter and avoid_systems.

    Args:
        universe: UniverseGraph for lookups
        origin_idx: Starting vertex index
        limit: Maximum borders to find
        max_jumps: Maximum search radius
        security_filter: Security constraint ("highsec", "lowsec", "any")
        avoid_systems: Set of vertex indices to avoid

    Returns:
        List of (vertex_idx, distance) tuples sorted by distance
    """
    g = universe.graph
    borders: list[tuple[int, int]] = []
    visited: dict[int, int] = {origin_idx: 0}
    queue: deque[tuple[int, int]] = deque([(origin_idx, 0)])
    avoid = avoid_systems or set()

    # Get security threshold based on filter
    sec_threshold = get_security_threshold(security_filter)

    while queue:
        vertex, dist = queue.popleft()
        if dist > max_jumps:
            continue

        if vertex in universe.border_systems:
            borders.append((vertex, dist))

        # Traverse through systems meeting security threshold
        for neighbor in g.neighbors(vertex):
            if neighbor not in visited and neighbor not in avoid:
                if universe.security[neighbor] >= sec_threshold:
                    visited[neighbor] = dist + 1
                    queue.append((neighbor, dist + 1))

    borders.sort(key=lambda x: x[1])
    return borders[:limit]
