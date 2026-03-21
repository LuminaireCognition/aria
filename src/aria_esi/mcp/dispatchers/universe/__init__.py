"""
Universe Dispatcher for MCP Server.

Consolidates 14 universe navigation tools into a single dispatcher:
- route: Point-to-point navigation
- systems: Batch system lookups
- borders: Find high-sec/low-sec border systems
- search: Filter systems by criteria
- loop: Circular mining/patrol routes
- analyze: Route security analysis
- nearest: Find nearest systems matching predicates
- optimize_waypoints: TSP waypoint optimization
- activity: Live system activity data
- hotspots: Find high-activity systems
- gatecamp_risk: Route risk analysis
- fw_frontlines: Faction Warfare contested systems
- local_area: Consolidated local intel for orientation
- territory_analysis: Sovereignty territory analysis for coalitions/alliances
"""

from __future__ import annotations

# Re-exports for backward compatibility — all symbols that tests import from this package.
# Navigation service re-exports (used by test_tools_route.py)
from ....services.navigation import compute_safe_weights as _compute_safe_weights  # noqa: F401
from ....services.navigation import compute_unsafe_weights as _compute_unsafe_weights  # noqa: F401

# Action implementations
from ._actions_intel import (
    _activity,  # noqa: F401
    _fw_frontlines,  # noqa: F401
    _gatecamp_risk,  # noqa: F401
    _hotspots,  # noqa: F401
    _local_area,  # noqa: F401
    _territory_analysis,  # noqa: F401
)
from ._actions_navigation import (
    _borders,  # noqa: F401
    _nearest,  # noqa: F401
    _route,  # noqa: F401
    _search,  # noqa: F401
    _systems,  # noqa: F401
)
from ._actions_planning import (
    _analyze,  # noqa: F401
    _loop,  # noqa: F401
    _optimize_waypoints,  # noqa: F401
)
from ._actions_roaming import _roam_route  # noqa: F401

# Dispatcher
from ._dispatcher import (
    VALID_ACTIONS,  # noqa: F401
    UniverseAction,  # noqa: F401
    register_universe_dispatcher,  # noqa: F401
)

# Helper re-exports (used by tests)
from ._helpers_analyze import (
    _analyze_route,  # noqa: F401
    _find_chokepoints,  # noqa: F401
    _find_danger_zones,  # noqa: F401
    _validate_connectivity,  # noqa: F401
)
from ._helpers_local_area import (
    _classify_border,  # noqa: F401
    _classify_threat_level,  # noqa: F401
    _find_escape_routes,  # noqa: F401
)
from ._helpers_loop import (
    SEARCH_RADIUS_DIVISOR,  # noqa: F401
    _build_loop_result,  # noqa: F401
    _expand_tour_matrix,  # noqa: F401
    _find_borders_with_distance,  # noqa: F401
    _nearest_neighbor_tsp_matrix,  # noqa: F401
    _plan_loop,  # noqa: F401
    _select_diverse_borders_matrix,  # noqa: F401
)
from ._helpers_roam import (
    classify_systems,  # noqa: F401
    collect_bfs_data,  # noqa: F401
    fetch_activity_for_systems,  # noqa: F401
    greedy_forward_walk,  # noqa: F401
    sweep_retrace,  # noqa: F401
)
from ._helpers_route import (
    _build_route_result,  # noqa: F401
    _calculate_route,  # noqa: F401
    _generate_fw_route_warnings,  # noqa: F401
    _route_compute_security_summary,  # noqa: F401
    _route_generate_warnings,  # noqa: F401
)
from ._helpers_search import (
    _bfs_within_range,  # noqa: F401
    _build_border_system,  # noqa: F401
    _build_nearest_result,  # noqa: F401
    _build_predicate,  # noqa: F401
    _build_search_result,  # noqa: F401
    _find_border_systems,  # noqa: F401
    _find_nearest,  # noqa: F401
    _resolve_region,  # noqa: F401
    _search_systems,  # noqa: F401
    _summarize_filters,  # noqa: F401
    _summarize_predicates,  # noqa: F401
)
from ._helpers_waypoints import (
    _build_optimization_result,  # noqa: F401
    _do_optimize_waypoints,  # noqa: F401
    _find_best_start,  # noqa: F401
    _linear_path,  # noqa: F401
    _nearest_neighbor_tsp,  # noqa: F401
)
