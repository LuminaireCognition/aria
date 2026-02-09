"""
Navigation Service Router.

Core routing algorithms shared between MCP tools and CLI commands.
Provides a unified interface for route calculation with support for
different routing modes and system avoidance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from .weights import (
    compute_avoid_weights,
    compute_safe_weights,
    compute_unsafe_weights,
)

if TYPE_CHECKING:
    from ...universe.graph import UniverseGraph


RouteMode = Literal["shortest", "safe", "unsafe"]
VALID_MODES: frozenset[str] = frozenset({"shortest", "safe", "unsafe"})


@dataclass
class NavigationService:
    """
    Unified navigation service for route calculations.

    Provides a single source of truth for route algorithms used by
    both MCP tools and CLI commands. Supports shortest, safe, and
    unsafe routing modes with optional system avoidance.

    Example:
        service = NavigationService(universe)
        path = service.calculate_route(origin_idx, dest_idx, "safe", avoid_indices)
    """

    universe: UniverseGraph

    def calculate_route(
        self,
        origin_idx: int,
        dest_idx: int,
        mode: RouteMode = "shortest",
        avoid_systems: set[int] | None = None,
    ) -> list[int]:
        """
        Calculate route between two systems using the specified mode.

        Args:
            origin_idx: Starting vertex index
            dest_idx: Destination vertex index
            mode: Routing mode
                - "shortest": Minimum jumps (ignores security)
                - "safe": Prefer high-sec, penalize low/null-sec
                - "unsafe": Prefer low/null-sec (for hunting)
            avoid_systems: Set of vertex indices to avoid (treated as blocked)

        Returns:
            List of vertex indices from origin to destination.
            Empty list if no route exists.

        Note:
            The returned path includes both origin and destination.
            A direct jump returns [origin_idx, dest_idx] (2 elements, 1 jump).
        """
        g = self.universe.graph

        if mode == "shortest":
            if avoid_systems:
                weights = compute_avoid_weights(self.universe, avoid_systems)
                paths = g.get_shortest_paths(origin_idx, dest_idx, weights=weights)
            else:
                # Unweighted BFS - O(V + E)
                paths = g.get_shortest_paths(origin_idx, dest_idx)
            return paths[0] if paths and paths[0] else []

        elif mode == "safe":
            weights = compute_safe_weights(self.universe, avoid_systems)
            paths = g.get_shortest_paths(origin_idx, dest_idx, weights=weights)
            return paths[0] if paths and paths[0] else []

        elif mode == "unsafe":
            weights = compute_unsafe_weights(self.universe, avoid_systems)
            paths = g.get_shortest_paths(origin_idx, dest_idx, weights=weights)
            return paths[0] if paths and paths[0] else []

        return []

    def resolve_avoid_systems(
        self,
        system_names: list[str],
    ) -> tuple[set[int], list[str]]:
        """
        Resolve system names to vertex indices for avoidance.

        Args:
            system_names: List of system names to avoid

        Returns:
            Tuple of (resolved_indices, unresolved_names)
            - resolved_indices: Set of valid vertex indices
            - unresolved_names: List of names that couldn't be resolved
        """
        avoid_indices: set[int] = set()
        unresolved: list[str] = []

        for name in system_names:
            idx = self.universe.resolve_name(name)
            if idx is not None:
                avoid_indices.add(idx)
            else:
                unresolved.append(name)

        return avoid_indices, unresolved
