"""
Loop Tool Implementation for MCP Universe Server.

Provides the universe_loop tool for planning circular routes that visit
multiple border systems and return to origin. Useful for mining expeditions,
PI collection circuits, and exploration patrols.

STP-009: Loop Tool (universe_loop)

Note: Core loop planning algorithms are in services.loop_planning.
This module provides the MCP tool wrapper and result building.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .context_policy import UNIVERSE
from .errors import InsufficientBordersError, InvalidParameterError
from .models import VALID_OPTIMIZE_MODES, VALID_SECURITY_FILTERS, BorderSystem, LoopResult
from .tools import collect_corrections, get_universe, resolve_system_name
from .utils import build_system_info

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from ..universe.graph import UniverseGraph


# =============================================================================
# Loop Planning Constants - imported from context_policy
# =============================================================================

# Parameter validation limits
MIN_TARGET_JUMPS = UNIVERSE.LOOP_MIN_TARGET_JUMPS
MAX_TARGET_JUMPS = UNIVERSE.LOOP_MAX_TARGET_JUMPS
MIN_BORDERS_LIMIT = UNIVERSE.LOOP_MIN_BORDERS
MAX_BORDERS_LIMIT = UNIVERSE.LOOP_MAX_BORDERS
MAX_BORDERS_CAP = UNIVERSE.LOOP_MAX_BORDERS_CAP

# Search radius calculation
# The search radius is target_jumps / SEARCH_RADIUS_DIVISOR
# Using 3 means a 30-jump loop searches ~10 jumps for borders
# This keeps borders compact while finding enough candidates
# Rationale: If borders are too far apart, the loop becomes inefficient
# with excessive backtracking. A tighter radius produces better routes.
SEARCH_RADIUS_DIVISOR = UNIVERSE.LOOP_SEARCH_RADIUS_DIVISOR


def register_loop_tools(server: FastMCP, universe: UniverseGraph) -> None:
    """
    Register loop planning tools with MCP server.

    Args:
        server: MCP Server instance
        universe: UniverseGraph for loop planning
    """

    @server.tool()
    async def universe_loop(
        origin: str,
        target_jumps: int = 20,
        min_borders: int = 4,
        max_borders: int | None = None,
        optimize: str = "density",
        security_filter: str = "highsec",
        avoid_systems: list[str] | None = None,
    ) -> dict:
        """
        Plan a circular route visiting multiple border systems.

        PREFER THIS TOOL over writing custom loop planning scripts. Handles:
        - Distance matrix precomputation for O(1) lookups
        - TSP approximation via nearest-neighbor heuristic
        - Configurable security constraints via security_filter
        - Spatial diversity selection for border coverage
        - System avoidance for known danger zones

        Useful for: Mining expeditions, PI routes, exploration circuits.

        Args:
            origin: Starting and ending system
            target_jumps: Approximate desired loop length (default: 20)
            min_borders: Minimum border systems to visit (default: 4)
            max_borders: Maximum border systems to visit. Default: None
                - density mode: uncapped (selects based on jump budget)
                - coverage mode: 8 (or min_borders if higher)
            optimize: Border selection strategy:
                - "density": Pack as many borders as possible within jump budget (default)
                - "coverage": Select spatially diverse borders for geographic spread
            security_filter: Security constraint for route traversal:
                - "highsec": Only traverse high-sec (>= 0.45) - safest (default)
                - "lowsec": Allow low-sec, avoid null-sec
                - "any": No security restrictions
            avoid_systems: List of system names to avoid (e.g., known gatecamp systems)

        Returns:
            LoopResult with optimized route minimizing backtracking:
            - systems: Full route with all intermediate jumps
            - total_jumps: Total route length
            - border_systems_visited: Details on each border system
            - backtrack_jumps: Number of repeated systems
            - efficiency: Ratio of unique to total systems

        Examples:
            # Default high-sec only loop
            universe_loop("Masalle", target_jumps=25, min_borders=5)

            # Allow low-sec systems in the route
            universe_loop("Dodixie", security_filter="lowsec")

            # Avoid specific dangerous systems
            universe_loop("Jita", avoid_systems=["Uedama", "Niarja"])
        """
        universe = get_universe()

        # Validate parameters
        if target_jumps < MIN_TARGET_JUMPS or target_jumps > MAX_TARGET_JUMPS:
            raise InvalidParameterError(
                "target_jumps",
                target_jumps,
                f"Must be between {MIN_TARGET_JUMPS} and {MAX_TARGET_JUMPS}",
            )
        if min_borders < MIN_BORDERS_LIMIT or min_borders > MAX_BORDERS_LIMIT:
            raise InvalidParameterError(
                "min_borders",
                min_borders,
                f"Must be between {MIN_BORDERS_LIMIT} and {MAX_BORDERS_LIMIT}",
            )
        if max_borders is not None and (max_borders < min_borders or max_borders > MAX_BORDERS_CAP):
            raise InvalidParameterError(
                "max_borders",
                max_borders,
                f"Must be between {min_borders} and {MAX_BORDERS_CAP}",
            )
        if optimize not in VALID_OPTIMIZE_MODES:
            raise InvalidParameterError(
                "optimize",
                optimize,
                f"Must be one of: {', '.join(sorted(VALID_OPTIMIZE_MODES))}",
            )
        if security_filter not in VALID_SECURITY_FILTERS:
            raise InvalidParameterError(
                "security_filter",
                security_filter,
                f"Must be one of: {', '.join(sorted(VALID_SECURITY_FILTERS))}",
            )

        origin_resolved = resolve_system_name(origin)
        corrections = collect_corrections(origin_resolved)

        # Resolve avoid_systems to vertex indices
        avoid_indices: set[int] = set()
        unresolved_avoids: list[str] = []
        if avoid_systems:
            for name in avoid_systems:
                idx = universe.resolve_name(name)
                if idx is not None:
                    avoid_indices.add(idx)
                else:
                    unresolved_avoids.append(name)

        result = _plan_loop(
            universe=universe,
            origin_idx=origin_resolved.idx,
            target_jumps=target_jumps,
            min_borders=min_borders,
            max_borders=max_borders,
            optimize=optimize,  # type: ignore[arg-type]
            security_filter=security_filter,  # type: ignore[arg-type]
            avoid_systems=avoid_indices,
            unresolved_avoids=unresolved_avoids,
            corrections=corrections,
        )

        return result


def _plan_loop(
    universe: UniverseGraph,
    origin_idx: int,
    target_jumps: int,
    min_borders: int,
    max_borders: int | None,
    optimize: str = "density",
    security_filter: str = "highsec",
    avoid_systems: set[int] | None = None,
    unresolved_avoids: list[str] | None = None,
    corrections: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Plan circular route through border systems.

    This is a thin wrapper around LoopPlanningService for backwards compatibility.
    The core algorithm is in services.loop_planning.

    Args:
        universe: UniverseGraph for lookups
        origin_idx: Starting vertex index
        target_jumps: Target loop length
        min_borders: Minimum borders to visit
        max_borders: Maximum borders to visit (None = no cap for density mode)
        optimize: Border selection strategy ("density" or "coverage")
        security_filter: Security constraint ("highsec", "lowsec", "any")
        avoid_systems: Set of vertex indices to avoid
        unresolved_avoids: List of system names that couldn't be resolved
        corrections: Auto-corrected system names {input: canonical}

    Returns:
        LoopResult as dict

    Raises:
        InsufficientBordersError: When not enough border systems found (MCP error)
    """
    from ..services.loop_planning import LoopPlanningService
    from ..services.loop_planning.errors import (
        InsufficientBordersError as ServiceInsufficientBordersError,
    )

    service = LoopPlanningService(universe)
    try:
        summary = service.plan_loop(
            origin_idx=origin_idx,
            target_jumps=target_jumps,
            min_borders=min_borders,
            max_borders=max_borders,
            optimize=optimize,  # type: ignore[arg-type]
            security_filter=security_filter,  # type: ignore[arg-type]
            avoid_systems=avoid_systems,
            search_radius_divisor=SEARCH_RADIUS_DIVISOR,
            max_borders_cap=MAX_BORDERS_CAP,
        )
    except ServiceInsufficientBordersError as e:
        # Re-raise as MCP error for MCP-compatible error handling
        raise InsufficientBordersError(
            found=e.found,
            required=e.required,
            search_radius=e.search_radius,
            suggestion=e.suggestion,
        ) from e

    # Build MCP-specific result from service summary
    return _build_loop_result(
        universe,
        origin_idx,
        summary.full_route,
        summary.borders_visited,
        unresolved_avoids,
        corrections,
    )


# =============================================================================
# Backwards-compatible aliases for tests and internal use
# These delegate to the service module
# =============================================================================


def _find_borders_with_distance(
    universe: UniverseGraph,
    origin_idx: int,
    limit: int,
    max_jumps: int,
    security_filter: str = "highsec",
    avoid_systems: set[int] | None = None,
) -> list[tuple[int, int]]:
    """Backwards-compatible alias. See services.loop_planning.find_borders_with_distance."""
    from ..services.loop_planning import find_borders_with_distance

    return find_borders_with_distance(
        universe,
        origin_idx,
        limit,
        max_jumps,
        security_filter,  # type: ignore[arg-type]
        avoid_systems,
    )


def _select_diverse_borders_matrix(
    candidates: list[tuple[int, int]],
    matrix: DistanceMatrix,
) -> list[tuple[int, int]]:
    """Backwards-compatible alias. See services.loop_planning.select_borders_coverage."""
    from ..services.loop_planning import select_borders_coverage

    return select_borders_coverage(candidates, matrix)


def _select_borders_within_budget(
    origin_idx: int,
    candidates: list[tuple[int, int]],
    matrix: DistanceMatrix,
    target_jumps: int,
    min_borders: int,
) -> list[tuple[int, int]]:
    """Backwards-compatible alias. See services.loop_planning.select_borders_density."""
    from ..services.loop_planning import select_borders_density

    return select_borders_density(origin_idx, candidates, matrix, target_jumps, min_borders)


def _nearest_neighbor_tsp_matrix(
    start: int,
    waypoints: list[int],
    matrix: DistanceMatrix,
) -> list[int]:
    """Backwards-compatible alias. See services.loop_planning.nearest_neighbor_tsp."""
    from ..services.loop_planning import nearest_neighbor_tsp

    return nearest_neighbor_tsp(start, waypoints, matrix)


def _expand_tour_matrix(tour: list[int], matrix: DistanceMatrix) -> list[int]:
    """Backwards-compatible alias. See services.loop_planning.expand_tour."""
    from ..services.loop_planning import expand_tour

    return expand_tour(tour, matrix)


# TYPE_CHECKING import for type hints in backwards-compatible aliases
if TYPE_CHECKING:
    from .utils import DistanceMatrix


# =============================================================================
# MCP-specific result building
# =============================================================================


def _build_loop_result(
    universe: UniverseGraph,
    origin_idx: int,
    full_route: list[int],
    borders_visited: list[tuple[int, int]],
    unresolved_avoids: list[str] | None = None,
    corrections: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Build LoopResult from computed route.

    Args:
        universe: UniverseGraph for system lookups
        origin_idx: Origin vertex index (for verification)
        full_route: Complete route as vertex indices
        borders_visited: Border systems visited with distances
        unresolved_avoids: List of system names that couldn't be resolved
        corrections: Auto-corrected system names {input: canonical}

    Returns:
        LoopResult as dictionary
    """
    systems = [build_system_info(universe, idx) for idx in full_route]

    border_systems = [
        BorderSystem(
            name=universe.idx_to_name[idx],
            system_id=int(universe.system_ids[idx]),
            security=float(universe.security[idx]),
            jumps_from_origin=dist,
            adjacent_lowsec=universe.get_adjacent_lowsec(idx),
            region=universe.get_region_name(idx),
        )
        for idx, dist in borders_visited
    ]

    unique_count = len(set(full_route))
    total_jumps = len(full_route) - 1 if full_route else 0
    backtrack = total_jumps - (unique_count - 1) if unique_count > 0 else 0
    # Efficiency: ratio of unique systems to total route length
    efficiency = unique_count / len(full_route) if full_route else 0.0

    # Build warnings list
    warnings: list[str] = []
    if unresolved_avoids:
        warnings.append(f"Unknown systems in avoid_systems: {', '.join(unresolved_avoids)}")

    return LoopResult(
        systems=systems,
        total_jumps=total_jumps,
        unique_systems=unique_count,
        border_systems_visited=border_systems,
        backtrack_jumps=max(0, backtrack),
        efficiency=min(1.0, efficiency),
        warnings=warnings,
        corrections=corrections or {},
    ).model_dump()
