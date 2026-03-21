"""
Tests for route activity enrichment (Change 6) and linear waypoint mode (Change 3).
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from aria_esi.mcp.dispatchers.universe import (
    _build_route_result,
    _do_optimize_waypoints,
    _linear_path,
    _optimize_waypoints as _action_optimize_waypoints,
    _route,
)
from aria_esi.mcp.tools import register_tools
from aria_esi.mcp.utils import DistanceMatrix
from aria_esi.store.activity import ActivityData
from aria_esi.universe import UniverseGraph

from .conftest import create_mock_universe


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def route_universe() -> UniverseGraph:
    """Universe for route activity enrichment tests."""
    systems = [
        {"name": "Jita", "id": 30000142, "sec": 0.95, "const": 20000020, "region": 10000002,
         "const_name": "Kimotoro", "region_name": "The Forge"},
        {"name": "Perimeter", "id": 30000144, "sec": 0.90, "const": 20000020, "region": 10000002,
         "const_name": "Kimotoro", "region_name": "The Forge"},
        {"name": "Urlen", "id": 30000138, "sec": 0.85, "const": 20000020, "region": 10000002,
         "const_name": "Kimotoro", "region_name": "The Forge"},
    ]
    edges = [(0, 1), (1, 2)]
    return create_mock_universe(systems, edges)


@pytest.fixture
def registered_route_universe(route_universe: UniverseGraph) -> UniverseGraph:
    mock_server = MagicMock()
    register_tools(mock_server, route_universe)
    return route_universe


MOCK_ACTIVITY = {
    30000142: ActivityData(system_id=30000142, npc_kills=10, ship_kills=2, pod_kills=1, ship_jumps=500),
    30000144: ActivityData(system_id=30000144, npc_kills=5, ship_kills=0, pod_kills=0, ship_jumps=300),
    30000138: ActivityData(system_id=30000138, npc_kills=0, ship_kills=0, pod_kills=0, ship_jumps=50),
}


def _mock_cache():
    mock_cache = MagicMock()

    async def mock_get_activity(system_id):
        return MOCK_ACTIVITY.get(system_id, ActivityData(system_id=system_id))

    async def mock_get_all_fw():
        return {}

    mock_cache.get_activity = mock_get_activity
    mock_cache.get_all_fw = mock_get_all_fw
    mock_cache.get_kills_cache_age.return_value = 60
    return mock_cache


# =============================================================================
# Tests: Route Activity Enrichment (Change 6)
# =============================================================================


class TestRouteActivityEnrichment:
    """Test include_activity on route responses."""

    def test_without_activity(self, route_universe: UniverseGraph):
        """Default route has no activity fields populated."""
        path = [0, 1, 2]
        result = asyncio.run(_build_route_result(
            route_universe, path, "Jita", "Urlen", "shortest"
        ))
        system = result.systems[0]
        assert system.npc_kills is None
        assert system.ship_jumps is None

    def test_with_activity(self, route_universe: UniverseGraph):
        """include_activity=True populates kill/jump data."""
        with patch("aria_esi.mcp.dispatchers.universe._helpers_route.get_activity_cache", return_value=_mock_cache()):
            path = [0, 1, 2]
            result = asyncio.run(_build_route_result(
                route_universe, path, "Jita", "Urlen", "shortest",
                include_activity=True,
            ))
        system = result.systems[0]
        assert system.npc_kills == 10
        assert system.ship_kills == 2
        assert system.pod_kills == 1
        assert system.ship_jumps == 500
        assert system.activity_level is not None

    def test_cache_miss_zeros(self, route_universe: UniverseGraph):
        """Systems with no hourly data get zero-filled activity."""
        with patch("aria_esi.mcp.dispatchers.universe._helpers_route.get_activity_cache", return_value=_mock_cache()):
            path = [0, 1, 2]
            result = asyncio.run(_build_route_result(
                route_universe, path, "Jita", "Urlen", "shortest",
                include_activity=True,
            ))
        # Urlen has zero activity in mock
        urlen = result.systems[2]
        assert isinstance(urlen.npc_kills, int)
        assert isinstance(urlen.ship_jumps, int)
        assert urlen.activity_level is not None

    def test_route_action_passes_include_activity(self, registered_route_universe: UniverseGraph):
        """_route action passes include_activity through to builder."""
        mock = _mock_cache()
        with (
            patch("aria_esi.mcp.dispatchers.universe._helpers_route.get_activity_cache", return_value=mock),
            patch("aria_esi.store.activity.get_activity_cache", return_value=mock),
        ):
            result = asyncio.run(_route(
                "Jita", "Urlen", "shortest", None,
                include_activity=True,
            ))
        # Should have activity data on the first system
        first = result["systems"][0]
        assert first.get("npc_kills") is not None or first.get("npc_kills") == 10


# =============================================================================
# Tests: Linear Waypoint Mode (Change 3)
# =============================================================================


@pytest.fixture
def linear_universe() -> UniverseGraph:
    """
    Universe for linear path testing.

    Topology:
        A (0) -- B (1) -- C (2) -- D (3) -- E (4)
                  |
                 F (5) -- G (6)

    A linear path from A through [C, D, G] must skip some waypoints
    if it can't reach them without backtracking.
    """
    systems = [
        {"name": "A", "id": 30200001, "sec": -0.1, "const": 20200001, "region": 10200001,
         "const_name": "TestConst", "region_name": "Test Region"},
        {"name": "B", "id": 30200002, "sec": -0.2, "const": 20200001, "region": 10200001,
         "const_name": "TestConst", "region_name": "Test Region"},
        {"name": "C", "id": 30200003, "sec": -0.3, "const": 20200001, "region": 10200001,
         "const_name": "TestConst", "region_name": "Test Region"},
        {"name": "D", "id": 30200004, "sec": -0.4, "const": 20200001, "region": 10200001,
         "const_name": "TestConst", "region_name": "Test Region"},
        {"name": "E", "id": 30200005, "sec": -0.5, "const": 20200001, "region": 10200001,
         "const_name": "TestConst", "region_name": "Test Region"},
        {"name": "F", "id": 30200006, "sec": -0.3, "const": 20200001, "region": 10200001,
         "const_name": "TestConst", "region_name": "Test Region"},
        {"name": "G", "id": 30200007, "sec": -0.4, "const": 20200001, "region": 10200001,
         "const_name": "TestConst", "region_name": "Test Region"},
    ]
    edges = [
        (0, 1),  # A -- B
        (1, 2),  # B -- C
        (2, 3),  # C -- D
        (3, 4),  # D -- E
        (1, 5),  # B -- F
        (5, 6),  # F -- G
    ]
    return create_mock_universe(systems, edges)


@pytest.fixture
def registered_linear_universe(linear_universe: UniverseGraph) -> UniverseGraph:
    mock_server = MagicMock()
    register_tools(mock_server, linear_universe)
    return linear_universe


class TestLinearPath:
    """Test _linear_path function."""

    def test_no_repeat(self, linear_universe: UniverseGraph):
        """Linear path must not revisit systems."""
        waypoints = [2, 3, 6]  # C, D, G
        all_vertices = [0] + waypoints
        matrix = DistanceMatrix.compute(linear_universe, all_vertices, security_filter="any")
        tour, skipped = _linear_path(0, waypoints, matrix)
        assert len(tour) == len(set(tour)), "Linear path contains duplicates"

    def test_skips_unreachable(self, linear_universe: UniverseGraph):
        """Waypoints in dead-end pockets force skipping."""
        # From A, visiting both E (far end) and G (branch) linearly
        # requires backtracking through B — one must be skipped
        waypoints = [4, 6]  # E, G
        all_vertices = [0] + waypoints
        matrix = DistanceMatrix.compute(linear_universe, all_vertices, security_filter="any")
        tour, skipped = _linear_path(0, waypoints, matrix)
        # Should visit at least one and skip the other
        assert len(tour) >= 2  # At least start + 1 waypoint
        # Total visited + skipped = total waypoints
        assert len(tour) - 1 + len(skipped) == len(waypoints)


class TestOptimizeWaypointsLinear:
    """Test linear mode in _do_optimize_waypoints."""

    def test_linear_no_repeat(self, linear_universe: UniverseGraph):
        """Linear mode result has no duplicate systems."""
        result = _do_optimize_waypoints(
            linear_universe,
            waypoint_indices=[2, 3, 4],
            origin_idx=0,
            origin_name="A",
            return_to_origin=False,
            security_filter="any",
            linear=True,
        )
        route_names = [s["name"] for s in result["route_systems"]]
        assert len(route_names) == len(set(route_names)), "Linear route has duplicates"
        assert result["mode"] == "linear"

    def test_linear_overrides_return_to_origin(self, linear_universe: UniverseGraph):
        """linear=True + return_to_origin=True: linear wins with warning."""
        result = _do_optimize_waypoints(
            linear_universe,
            waypoint_indices=[2, 3],
            origin_idx=0,
            origin_name="A",
            return_to_origin=True,
            security_filter="any",
            linear=True,
        )
        assert result["mode"] == "linear"
        assert any("overrides return_to_origin" in w for w in result.get("warnings", []))
        # Route should NOT loop back to origin
        route_names = [s["name"] for s in result["route_systems"]]
        assert len(route_names) == len(set(route_names))

    def test_tsp_mode_default(self, linear_universe: UniverseGraph):
        """Default mode is TSP."""
        result = _do_optimize_waypoints(
            linear_universe,
            waypoint_indices=[2, 3],
            origin_idx=0,
            origin_name="A",
            return_to_origin=False,
            security_filter="any",
        )
        assert result["mode"] == "tsp"

    def test_action_passes_linear(self, registered_linear_universe: UniverseGraph):
        """Action layer passes linear parameter correctly."""
        result = asyncio.run(_action_optimize_waypoints(
            waypoints=["C", "D"],
            origin="A",
            return_to_origin=False,
            security_filter="any",
            avoid_systems=None,
            linear=True,
        ))
        assert result["mode"] == "linear"
