"""
Loop Planning Result Builder.

Provides transport-agnostic result construction for loop planning.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LoopSummary:
    """
    Transport-agnostic loop planning metrics.

    Contains the core metrics computed by the loop planning algorithm.
    Transport layers (MCP, CLI) use these to build their specific responses.
    """

    full_route: list[int]
    """Complete route as vertex indices."""

    borders_visited: list[tuple[int, int]]
    """Border systems visited with distances: (vertex_idx, distance_from_origin)."""

    total_jumps: int
    """Total number of jumps in the route."""

    unique_systems: int
    """Number of unique systems in the route."""

    backtrack_jumps: int
    """Number of jumps that revisit previously visited systems."""

    efficiency: float
    """Ratio of unique systems to total route length (0.0 to 1.0)."""


def compute_loop_summary(
    full_route: list[int],
    borders_visited: list[tuple[int, int]],
) -> LoopSummary:
    """
    Compute transport-agnostic loop summary from route data.

    Args:
        full_route: Complete route as vertex indices
        borders_visited: Border systems visited with distances

    Returns:
        LoopSummary with computed metrics
    """
    unique_count = len(set(full_route))
    total_jumps = len(full_route) - 1 if full_route else 0
    backtrack = total_jumps - (unique_count - 1) if unique_count > 0 else 0
    efficiency = unique_count / len(full_route) if full_route else 0.0

    return LoopSummary(
        full_route=full_route,
        borders_visited=borders_visited,
        total_jumps=total_jumps,
        unique_systems=unique_count,
        backtrack_jumps=max(0, backtrack),
        efficiency=min(1.0, efficiency),
    )
