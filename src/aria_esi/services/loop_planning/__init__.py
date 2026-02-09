"""
Loop Planning Service.

Unified loop planning service shared between MCP tools and CLI commands.
Provides a single source of truth for loop planning algorithms, border
selection strategies, and result construction utilities.

Usage:
    from aria_esi.services.loop_planning import LoopPlanningService

    service = LoopPlanningService(universe)
    summary = service.plan_loop(origin_idx, target_jumps=20, min_borders=4)
"""

from __future__ import annotations

__all__ = [
    # Core service
    "LoopPlanningService",
    "OptimizeMode",
    "VALID_OPTIMIZE_MODES",
    "VALID_SECURITY_FILTERS",
    # Errors
    "LoopPlanningError",
    "InsufficientBordersError",
    # Algorithms
    "select_borders_density",
    "select_borders_coverage",
    "nearest_neighbor_tsp",
    "expand_tour",
    # Border search
    "find_borders_with_distance",
    "SecurityFilter",
    # Result utilities
    "LoopSummary",
    "compute_loop_summary",
]


def __getattr__(name: str):
    """Lazy import to avoid circular dependencies."""
    # Planner service
    if name == "LoopPlanningService":
        from .planner import LoopPlanningService

        return LoopPlanningService
    if name in ("OptimizeMode", "VALID_OPTIMIZE_MODES", "VALID_SECURITY_FILTERS"):
        from . import planner

        return getattr(planner, name)

    # Errors
    if name in ("LoopPlanningError", "InsufficientBordersError"):
        from . import errors

        return getattr(errors, name)

    # Algorithms
    if name in (
        "select_borders_density",
        "select_borders_coverage",
        "nearest_neighbor_tsp",
        "expand_tour",
    ):
        from . import algorithms

        return getattr(algorithms, name)

    # Border search
    if name in ("find_borders_with_distance", "SecurityFilter"):
        from . import border_search

        return getattr(border_search, name)

    # Result utilities
    if name in ("LoopSummary", "compute_loop_summary"):
        from . import result_builder

        return getattr(result_builder, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
