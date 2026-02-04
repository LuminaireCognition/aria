"""
Route Tool Implementation for MCP Universe Server.

Provides the universe_route tool for calculating optimal routes between
EVE Online systems with support for shortest, safe, and unsafe routing modes.

STP-005: Route Tool (universe_route)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..services.navigation import (
    VALID_MODES,
    NavigationService,
    compute_security_summary,
    generate_warnings,
)
from .errors import InvalidParameterError, RouteNotFoundError
from .models import RouteResult, SecuritySummary
from .tools import collect_corrections, get_universe, resolve_system_name
from .utils import build_system_info

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from ..universe.graph import UniverseGraph


def register_route_tools(server: FastMCP, universe: UniverseGraph) -> None:
    """
    Register route-related MCP tools.

    Args:
        server: MCP Server instance
        universe: UniverseGraph for route calculations
    """

    @server.tool()
    async def universe_route(
        origin: str,
        destination: str,
        mode: str = "shortest",
        avoid_systems: list[str] | None = None,
    ) -> dict:
        """
        Calculate optimal route between two systems.

        PREFER THIS TOOL over writing custom pathfinding scripts. Handles
        graph loading, edge weighting, and security analysis automatically.

        Args:
            origin: Starting system name (case-insensitive)
            destination: Target system name (case-insensitive)
            mode: Routing preference
                - "shortest": Minimum jumps (default)
                - "safe": Avoid low/null-sec where possible
                - "unsafe": Prefer low/null-sec (for hunting)
            avoid_systems: List of system names to avoid (e.g., known gatecamp systems)

        Returns:
            RouteResult with full system details and security analysis

        System Avoidance:
            Use avoid_systems to route around dangerous or undesirable systems.
            Common use cases:
            - Known gatecamp systems (Uedama, Sivala, Niarja)
            - Wardec staging systems
            - Triglavian minor victory systems
            - Systems with active hostile activity

        Examples:
            universe_route("Jita", "Amarr", mode="safe")

            # Avoid known gatecamp systems
            universe_route("Jita", "Dodixie", avoid_systems=["Uedama", "Sivala"])

            # Combine safe mode with specific avoidance
            universe_route("Jita", "Hek", mode="safe", avoid_systems=["Niarja", "Aufay"])
        """
        universe_graph = get_universe()

        # Validate mode
        if mode not in VALID_MODES:
            raise InvalidParameterError(
                "mode", mode, f"Must be one of: {', '.join(sorted(VALID_MODES))}"
            )

        # Resolve system names (with auto-correction)
        origin_resolved = resolve_system_name(origin)
        dest_resolved = resolve_system_name(destination)
        corrections = collect_corrections(origin_resolved, dest_resolved)

        # Resolve avoid_systems to vertex indices
        avoid_indices: set[int] | None = None
        unresolved_avoids: list[str] = []
        if avoid_systems:
            avoid_indices = set()
            for name in avoid_systems:
                idx = universe_graph.resolve_name(name)
                if idx is not None:
                    avoid_indices.add(idx)
                else:
                    unresolved_avoids.append(name)

        # Calculate route
        path = _calculate_route(
            universe, origin_resolved.idx, dest_resolved.idx, mode, avoid_indices
        )

        if not path:
            raise RouteNotFoundError(origin_resolved.canonical_name, dest_resolved.canonical_name)

        # Build result with corrections
        result = _build_route_result(
            universe,
            path,
            origin_resolved.canonical_name,
            dest_resolved.canonical_name,
            mode,
            corrections,
        )

        # Add warning for unresolved avoid_systems
        if unresolved_avoids:
            result = RouteResult(
                **{
                    **result.model_dump(),
                    "warnings": result.warnings
                    + [f"Unknown systems in avoid_systems: {', '.join(unresolved_avoids)}"],
                }
            )

        return result.model_dump()


# =============================================================================
# Routing Algorithms (delegated to NavigationService)
# =============================================================================


def _calculate_route(
    universe: UniverseGraph,
    origin_idx: int,
    dest_idx: int,
    mode: str,
    avoid_systems: set[int] | None = None,
) -> list[int]:
    """
    Calculate route using NavigationService.

    This function exists for backwards compatibility with tests.
    New code should use NavigationService directly.

    Args:
        universe: UniverseGraph for pathfinding
        origin_idx: Starting vertex index
        dest_idx: Destination vertex index
        mode: Routing mode (shortest, safe, unsafe)
        avoid_systems: Set of vertex indices to avoid

    Returns:
        List of vertex indices from origin to destination
    """
    service = NavigationService(universe)
    return service.calculate_route(origin_idx, dest_idx, mode, avoid_systems)  # type: ignore[arg-type]


# Re-export weight functions for test compatibility
# fmt: off
# ruff: noqa: E402, F401, I001
from ..services.navigation import compute_safe_weights as _compute_safe_weights
from ..services.navigation import compute_unsafe_weights as _compute_unsafe_weights
# fmt: on

# =============================================================================
# Result Construction (delegated to navigation service)
# =============================================================================


def _build_route_result(
    universe: UniverseGraph,
    path: list[int],
    origin: str,
    destination: str,
    mode: str,
    corrections: dict[str, str] | None = None,
) -> RouteResult:
    """Build complete RouteResult from path."""
    systems = [build_system_info(universe, idx) for idx in path]
    summary = compute_security_summary(universe, path)
    warnings = generate_warnings(universe, path, mode)

    return RouteResult(
        origin=origin,
        destination=destination,
        mode=mode,  # type: ignore[arg-type]
        jumps=len(path) - 1,
        systems=systems,
        security_summary=SecuritySummary(
            total_jumps=summary.total_jumps,
            highsec_jumps=summary.highsec_jumps,
            lowsec_jumps=summary.lowsec_jumps,
            nullsec_jumps=summary.nullsec_jumps,
            lowest_security=summary.lowest_security,
            lowest_security_system=summary.lowest_security_system,
        ),
        warnings=warnings,
        corrections=corrections or {},
    )


# Re-export for test compatibility
def _compute_security_summary(
    universe: UniverseGraph,
    path: list[int],
) -> SecuritySummary:
    """Compute security breakdown for route (wrapper for tests)."""
    summary = compute_security_summary(universe, path)
    return SecuritySummary(
        total_jumps=summary.total_jumps,
        highsec_jumps=summary.highsec_jumps,
        lowsec_jumps=summary.lowsec_jumps,
        nullsec_jumps=summary.nullsec_jumps,
        lowest_security=summary.lowest_security,
        lowest_security_system=summary.lowest_security_system,
    )


def _generate_warnings(
    universe: UniverseGraph,
    path: list[int],
    mode: str,
) -> list[str]:
    """Generate route warnings (wrapper for tests)."""
    return generate_warnings(universe, path, mode)
