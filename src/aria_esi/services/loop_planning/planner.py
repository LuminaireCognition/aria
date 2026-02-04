"""
Loop Planning Service.

Core loop planning service shared between MCP tools and CLI commands.
Provides a unified interface for loop planning with support for
different optimization modes and security constraints.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from .algorithms import (
    expand_tour,
    nearest_neighbor_tsp,
    select_borders_coverage,
    select_borders_density,
)
from .border_search import SecurityFilter, find_borders_with_distance
from .errors import InsufficientBordersError
from .result_builder import LoopSummary, compute_loop_summary

if TYPE_CHECKING:
    from ...universe.graph import UniverseGraph


OptimizeMode = Literal["density", "coverage"]
VALID_OPTIMIZE_MODES: frozenset[str] = frozenset({"density", "coverage"})
VALID_SECURITY_FILTERS: frozenset[str] = frozenset({"highsec", "lowsec", "any"})


# Default cap for coverage mode when max_borders not specified
DEFAULT_COVERAGE_CAP = 8


@dataclass
class LoopPlanningService:
    """
    Unified loop planning service.

    Provides a single source of truth for loop planning algorithms used by
    both MCP tools and CLI commands. Supports density and coverage
    optimization modes with configurable security constraints.

    Example:
        service = LoopPlanningService(universe)
        summary = service.plan_loop(
            origin_idx=0,
            target_jumps=20,
            min_borders=4,
            max_borders=None,
            optimize="density",
            security_filter="highsec",
        )
    """

    universe: UniverseGraph

    def plan_loop(
        self,
        origin_idx: int,
        target_jumps: int,
        min_borders: int,
        max_borders: int | None = None,
        optimize: OptimizeMode = "density",
        security_filter: SecurityFilter = "highsec",
        avoid_systems: set[int] | None = None,
        search_radius_divisor: int = 3,
        max_borders_cap: int = 15,
    ) -> LoopSummary:
        """
        Plan a circular route through border systems.

        Algorithm:
        1. BFS to find border systems within range
        2. Precompute distance matrix for all candidates (OPTIMIZATION)
        3. Select borders based on optimize mode (density or coverage)
        4. Solve TSP approximation using matrix
        5. Expand tour to full route using matrix paths
        6. Build summary

        Args:
            origin_idx: Starting vertex index
            target_jumps: Target loop length
            min_borders: Minimum borders to visit
            max_borders: Maximum borders to visit (None = no cap for density mode)
            optimize: Border selection strategy ("density" or "coverage")
            security_filter: Security constraint ("highsec", "lowsec", "any")
            avoid_systems: Set of vertex indices to avoid
            search_radius_divisor: Divisor for calculating search radius from target_jumps
            max_borders_cap: Absolute maximum borders for internal calculations

        Returns:
            LoopSummary with computed route metrics

        Raises:
            InsufficientBordersError: When not enough border systems found
        """
        # Import here to avoid circular dependency
        from ...mcp.utils import DistanceMatrix

        # Step 1: Find candidate borders within reasonable range
        # Use tighter radius to keep borders closer, producing more compact routes
        search_radius = target_jumps // search_radius_divisor
        # For candidate search, use effective_max to avoid searching too few candidates
        effective_max_for_search = max_borders if max_borders is not None else max_borders_cap
        candidates = find_borders_with_distance(
            self.universe,
            origin_idx,
            limit=effective_max_for_search * 3,
            max_jumps=search_radius,
            security_filter=security_filter,
            avoid_systems=avoid_systems,
        )

        if len(candidates) < min_borders:
            raise InsufficientBordersError(
                found=len(candidates),
                required=min_borders,
                search_radius=search_radius,
            )

        # Step 2: Precompute distance matrix for origin + all candidates
        # This single operation replaces many individual pathfinding calls
        candidate_indices = [c[0] for c in candidates]
        all_waypoints = [origin_idx] + candidate_indices
        matrix = DistanceMatrix.compute(
            self.universe,
            all_waypoints,
            security_filter=security_filter,
            avoid_systems=avoid_systems,
        )

        # Step 3: Select borders based on optimize mode
        if optimize == "density":
            # Budget-aware selection: pack as many borders as possible within jump budget
            selected = select_borders_density(
                origin_idx, candidates, matrix, target_jumps, min_borders
            )
            # Only cap if explicitly requested
            if max_borders is not None:
                selected = selected[:max_borders]
        else:  # coverage
            # Spatially diverse selection with default cap
            # Ensure we honor min_borders even if it exceeds the default cap
            selected = select_borders_coverage(candidates, matrix)
            effective_max = (
                max_borders if max_borders is not None else max(DEFAULT_COVERAGE_CAP, min_borders)
            )
            selected = selected[:effective_max]

        # Step 4: Solve TSP approximation using matrix
        tour = nearest_neighbor_tsp(origin_idx, [s[0] for s in selected], matrix)

        # Step 5: Expand tour to full route using matrix paths
        full_route = expand_tour(tour, matrix)

        # Step 6: Build summary
        return compute_loop_summary(full_route, selected)

    def find_borders(
        self,
        origin_idx: int,
        limit: int,
        max_jumps: int,
        security_filter: SecurityFilter = "highsec",
        avoid_systems: set[int] | None = None,
    ) -> list[tuple[int, int]]:
        """
        Find border systems within range of origin.

        Wrapper around find_borders_with_distance for service API consistency.

        Args:
            origin_idx: Starting vertex index
            limit: Maximum borders to find
            max_jumps: Maximum search radius
            security_filter: Security constraint
            avoid_systems: Set of vertex indices to avoid

        Returns:
            List of (vertex_idx, distance) tuples sorted by distance
        """
        return find_borders_with_distance(
            self.universe,
            origin_idx,
            limit=limit,
            max_jumps=max_jumps,
            security_filter=security_filter,
            avoid_systems=avoid_systems,
        )

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
