"""
Tests for Waypoint Optimization Tool Implementation.

STP-012: Waypoint Optimization Tool (universe_optimize_waypoints) Tests
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from aria_esi.mcp.errors import InvalidParameterError, SystemNotFoundError
from aria_esi.mcp.tools import register_tools
from aria_esi.mcp.tools_waypoints import (
    _find_best_start,
    _nearest_neighbor_tsp,
    _optimize_waypoints,
    register_waypoints_tools,
)
from aria_esi.mcp.utils import DistanceMatrix
from aria_esi.universe import UniverseGraph

from .conftest import create_mock_universe

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def waypoint_universe() -> UniverseGraph:
    """
    Create a universe optimized for waypoint testing.

    Graph structure (fully connected high-sec for easy testing):

        Jita (0.95) -- Perimeter (0.90) -- Urlen (0.85) -- Haatomo (0.70)
             |               |                 |
        Maurasi (0.65) ------+            Uedama (0.50)
             |
        Sivala (0.35) -- low-sec

    Additional region for multi-region testing:
        Haatomo -- Aufay (0.55) -- Balle (0.25)

    This creates a mix of short and long paths for TSP testing.
    """
    systems = [
        {"name": "Jita", "id": 30000142, "sec": 0.95, "const": 20000020, "region": 10000002,
         "const_name": "Kimotoro", "region_name": "The Forge"},
        {"name": "Perimeter", "id": 30000144, "sec": 0.90, "const": 20000020, "region": 10000002,
         "const_name": "Kimotoro", "region_name": "The Forge"},
        {"name": "Maurasi", "id": 30000140, "sec": 0.65, "const": 20000020, "region": 10000002,
         "const_name": "Kimotoro", "region_name": "The Forge"},
        {"name": "Urlen", "id": 30000138, "sec": 0.85, "const": 20000020, "region": 10000002,
         "const_name": "Kimotoro", "region_name": "The Forge"},
        {"name": "Sivala", "id": 30000160, "sec": 0.35, "const": 20000021, "region": 10000002,
         "const_name": "Otanuomi", "region_name": "The Forge"},
        {"name": "Haatomo", "id": 30002693, "sec": 0.70, "const": 20000023, "region": 10000002,
         "const_name": "Uosusuokko", "region_name": "The Forge"},
        {"name": "Uedama", "id": 30002691, "sec": 0.50, "const": 20000023, "region": 10000043,
         "const_name": "Uosusuokko", "region_name": "Domain"},
        {"name": "Aufay", "id": 30002694, "sec": 0.55, "const": 20000024, "region": 10000044,
         "const_name": "Aufayland", "region_name": "Sinq Laison"},
        {"name": "Balle", "id": 30002695, "sec": 0.25, "const": 20000024, "region": 10000044,
         "const_name": "Aufayland", "region_name": "Sinq Laison"},
    ]

    edges = [
        (0, 1),  # Jita -- Perimeter
        (0, 2),  # Jita -- Maurasi
        (1, 2),  # Perimeter -- Maurasi
        (1, 3),  # Perimeter -- Urlen
        (2, 4),  # Maurasi -- Sivala
        (3, 5),  # Urlen -- Haatomo
        (3, 6),  # Urlen -- Uedama
        (5, 6),  # Haatomo -- Uedama
        (5, 7),  # Haatomo -- Aufay
        (7, 8),  # Aufay -- Balle
    ]

    return create_mock_universe(systems, edges)


@pytest.fixture
def registered_waypoint_universe(waypoint_universe: UniverseGraph) -> UniverseGraph:
    """Register tools with waypoint universe."""
    mock_server = MagicMock()
    register_tools(mock_server, waypoint_universe)
    return waypoint_universe


# =============================================================================
# Helper Functions
# =============================================================================


def _capture_tool(universe: UniverseGraph):
    """Helper to capture the registered tool function."""
    captured_tool = None

    def mock_tool():
        def decorator(func):
            nonlocal captured_tool
            captured_tool = func
            return func
        return decorator

    mock_server = MagicMock()
    mock_server.tool = mock_tool
    register_waypoints_tools(mock_server, universe)
    return captured_tool


# =============================================================================
# Unit Tests: _find_best_start
# =============================================================================


class TestFindBestStart:
    """Test _find_best_start function."""

    def test_finds_central_waypoint(self, waypoint_universe: UniverseGraph):
        """Finds waypoint with minimum total distance to others."""
        # Build matrix for Jita (0), Perimeter (1), Urlen (3)
        waypoints = [0, 1, 3]
        matrix = DistanceMatrix.compute(waypoint_universe, waypoints, security_filter="any")

        best = _find_best_start(waypoints, matrix)

        # Perimeter (1) is central - 1 hop to both Jita and Urlen
        # Jita: 1 to Perimeter, 2 to Urlen = 3
        # Perimeter: 1 to Jita, 1 to Urlen = 2
        # Urlen: 2 to Jita, 1 to Perimeter = 3
        assert best == 1  # Perimeter is optimal

    def test_handles_single_waypoint(self, waypoint_universe: UniverseGraph):
        """Returns single waypoint when only one given."""
        waypoints = [0]
        matrix = DistanceMatrix.compute(waypoint_universe, waypoints, security_filter="any")

        best = _find_best_start(waypoints, matrix)
        assert best == 0


# =============================================================================
# Unit Tests: _nearest_neighbor_tsp
# =============================================================================


class TestNearestNeighborTsp:
    """Test _nearest_neighbor_tsp function."""

    def test_visits_all_waypoints(self, waypoint_universe: UniverseGraph):
        """Tour visits all waypoints exactly once."""
        start = 0  # Jita
        waypoints = [1, 3, 5]  # Perimeter, Urlen, Haatomo
        all_wp = [start] + waypoints
        matrix = DistanceMatrix.compute(waypoint_universe, all_wp, security_filter="any")

        tour = _nearest_neighbor_tsp(start, waypoints, matrix)

        assert len(tour) == 4  # start + 3 waypoints
        assert set(tour) == {0, 1, 3, 5}

    def test_starts_at_given_start(self, waypoint_universe: UniverseGraph):
        """Tour starts at specified start vertex."""
        start = 3  # Urlen
        waypoints = [0, 1, 5]
        all_wp = [start] + waypoints
        matrix = DistanceMatrix.compute(waypoint_universe, all_wp, security_filter="any")

        tour = _nearest_neighbor_tsp(start, waypoints, matrix)

        assert tour[0] == 3

    def test_greedy_nearest_neighbor(self, waypoint_universe: UniverseGraph):
        """Tour follows nearest-neighbor greedy heuristic."""
        start = 0  # Jita
        waypoints = [1, 3]  # Perimeter, Urlen
        all_wp = [start] + waypoints
        matrix = DistanceMatrix.compute(waypoint_universe, all_wp, security_filter="any")

        tour = _nearest_neighbor_tsp(start, waypoints, matrix)

        # From Jita: Perimeter is 1 hop, Urlen is 2 hops
        # Should visit Perimeter first
        assert tour[0] == 0  # Jita
        assert tour[1] == 1  # Perimeter (nearest)
        assert tour[2] == 3  # Urlen


# =============================================================================
# Unit Tests: _optimize_waypoints
# =============================================================================


class TestOptimizeWaypoints:
    """Test _optimize_waypoints function."""

    def test_returns_valid_result(self, waypoint_universe: UniverseGraph):
        """Returns complete optimization result."""
        result = _optimize_waypoints(
            waypoint_universe,
            waypoint_indices=[0, 1, 3],
            origin_idx=None,
            origin_name=None,
            return_to_origin=False,
        )

        assert "waypoints" in result
        assert "total_jumps" in result
        assert "route_systems" in result
        assert "is_loop" in result

    def test_with_origin(self, waypoint_universe: UniverseGraph):
        """Origin is respected in tour."""
        result = _optimize_waypoints(
            waypoint_universe,
            waypoint_indices=[1, 3, 5],  # Perimeter, Urlen, Haatomo
            origin_idx=0,  # Jita
            origin_name="Jita",
            return_to_origin=True,
        )

        # First waypoint in tour should be origin
        assert result["waypoints"][0]["name"] == "Jita"
        assert result["is_loop"] is True
        # Route should start and end at Jita
        assert result["route_systems"][0]["name"] == "Jita"
        assert result["route_systems"][-1]["name"] == "Jita"

    def test_without_return_to_origin(self, waypoint_universe: UniverseGraph):
        """Route doesn't return when return_to_origin=False."""
        result = _optimize_waypoints(
            waypoint_universe,
            waypoint_indices=[1, 3, 5],
            origin_idx=0,
            origin_name="Jita",
            return_to_origin=False,
        )

        assert result["is_loop"] is False
        # Route should start at Jita but not necessarily end there
        assert result["route_systems"][0]["name"] == "Jita"

    def test_visits_all_waypoints(self, waypoint_universe: UniverseGraph):
        """All waypoints appear in result."""
        waypoints = [0, 1, 3, 5]  # Jita, Perimeter, Urlen, Haatomo
        result = _optimize_waypoints(
            waypoint_universe,
            waypoint_indices=waypoints,
            origin_idx=None,
            origin_name=None,
            return_to_origin=False,
        )

        visited_names = {wp["name"] for wp in result["waypoints"]}
        expected_names = {"Jita", "Perimeter", "Urlen", "Haatomo"}
        assert visited_names == expected_names

    def test_security_filter_highsec(self, waypoint_universe: UniverseGraph):
        """Highsec filter avoids lowsec systems."""
        result = _optimize_waypoints(
            waypoint_universe,
            waypoint_indices=[0, 2],  # Jita, Maurasi
            origin_idx=None,
            origin_name=None,
            return_to_origin=False,
            security_filter="highsec",
        )

        # Route should not include Sivala (lowsec)
        route_names = {s["name"] for s in result["route_systems"]}
        assert "Sivala" not in route_names


# =============================================================================
# Integration Tests: universe_optimize_waypoints tool
# =============================================================================


class TestUniverseOptimizeWaypointsIntegration:
    """Integration tests for the universe_optimize_waypoints tool."""

    def test_basic_optimization(self, registered_waypoint_universe: UniverseGraph):
        """Basic waypoint optimization works."""
        tool = _capture_tool(registered_waypoint_universe)
        result = asyncio.run(tool(waypoints=["Jita", "Perimeter", "Urlen"]))

        assert "waypoints" in result
        assert len(result["waypoints"]) == 3
        assert result["total_jumps"] > 0

    def test_with_origin_and_return(self, registered_waypoint_universe: UniverseGraph):
        """Origin with return creates loop."""
        tool = _capture_tool(registered_waypoint_universe)
        result = asyncio.run(tool(
            waypoints=["Perimeter", "Urlen", "Haatomo"],
            origin="Jita",
            return_to_origin=True,
        ))

        assert result["origin"] == "Jita"
        assert result["is_loop"] is True
        assert result["route_systems"][0]["name"] == "Jita"
        assert result["route_systems"][-1]["name"] == "Jita"

    def test_one_way_route(self, registered_waypoint_universe: UniverseGraph):
        """One-way route without return."""
        tool = _capture_tool(registered_waypoint_universe)
        result = asyncio.run(tool(
            waypoints=["Perimeter", "Urlen", "Haatomo"],
            origin="Jita",
            return_to_origin=False,
        ))

        assert result["is_loop"] is False
        assert result["route_systems"][0]["name"] == "Jita"

    def test_case_insensitive_names(self, registered_waypoint_universe: UniverseGraph):
        """System names are case-insensitive."""
        tool = _capture_tool(registered_waypoint_universe)
        result = asyncio.run(tool(waypoints=["jita", "PERIMETER", "Urlen"]))

        visited_names = {wp["name"] for wp in result["waypoints"]}
        assert "Jita" in visited_names
        assert "Perimeter" in visited_names

    def test_duplicate_waypoints_deduplicated(self, registered_waypoint_universe: UniverseGraph):
        """Duplicate waypoints are removed."""
        tool = _capture_tool(registered_waypoint_universe)
        result = asyncio.run(tool(waypoints=["Jita", "Perimeter", "Jita", "Urlen"]))

        # Should only have 3 unique waypoints
        assert len(result["waypoints"]) == 3

    def test_unresolved_waypoints_reported(self, registered_waypoint_universe: UniverseGraph):
        """Unknown waypoints are reported in result."""
        tool = _capture_tool(registered_waypoint_universe)
        result = asyncio.run(tool(
            waypoints=["Jita", "UnknownSystem", "Perimeter", "AnotherFake"]
        ))

        assert len(result["unresolved_waypoints"]) == 2
        assert "UnknownSystem" in result["unresolved_waypoints"]
        assert "AnotherFake" in result["unresolved_waypoints"]

    def test_avoid_systems(self, registered_waypoint_universe: UniverseGraph):
        """Avoid systems are excluded from route."""
        tool = _capture_tool(registered_waypoint_universe)

        # Without avoidance, Perimeter is on direct path
        result_normal = asyncio.run(tool(
            waypoints=["Jita", "Urlen"],
            security_filter="any",
        ))

        # With avoidance
        result_avoid = asyncio.run(tool(
            waypoints=["Jita", "Urlen"],
            avoid_systems=["Perimeter"],
            security_filter="any",
        ))

        # Both should still complete, but paths may differ
        assert "route_systems" in result_normal
        assert "route_systems" in result_avoid

    def test_visit_order_in_result(self, registered_waypoint_universe: UniverseGraph):
        """Waypoints include visit_order field."""
        tool = _capture_tool(registered_waypoint_universe)
        result = asyncio.run(tool(waypoints=["Jita", "Perimeter", "Urlen"]))

        for i, wp in enumerate(result["waypoints"]):
            assert wp["visit_order"] == i


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestWaypointErrors:
    """Test error handling in waypoint optimization."""

    def test_too_few_waypoints(self, registered_waypoint_universe: UniverseGraph):
        """Raises error for less than 2 waypoints."""
        tool = _capture_tool(registered_waypoint_universe)

        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(tool(waypoints=["Jita"]))

        assert "waypoints" in str(exc.value)
        assert "2" in str(exc.value)

    def test_too_many_waypoints(self, registered_waypoint_universe: UniverseGraph):
        """Raises error for more than 50 waypoints."""
        tool = _capture_tool(registered_waypoint_universe)

        # Create 51 waypoint names (will fail validation before resolution)
        many_waypoints = [f"System{i}" for i in range(51)]

        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(tool(waypoints=many_waypoints))

        assert "waypoints" in str(exc.value)
        assert "50" in str(exc.value)

    def test_invalid_security_filter(self, registered_waypoint_universe: UniverseGraph):
        """Raises error for invalid security_filter."""
        tool = _capture_tool(registered_waypoint_universe)

        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(tool(
                waypoints=["Jita", "Perimeter"],
                security_filter="invalid"
            ))

        assert "security_filter" in str(exc.value)

    def test_unknown_origin(self, registered_waypoint_universe: UniverseGraph):
        """Raises error for unknown origin system."""
        tool = _capture_tool(registered_waypoint_universe)

        with pytest.raises(SystemNotFoundError):
            asyncio.run(tool(
                waypoints=["Jita", "Perimeter"],
                origin="UnknownSystem"
            ))

    def test_insufficient_valid_waypoints(self, registered_waypoint_universe: UniverseGraph):
        """Raises error if too few waypoints resolve."""
        tool = _capture_tool(registered_waypoint_universe)

        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(tool(waypoints=["Unknown1", "Unknown2", "Jita"]))

        assert "waypoints" in str(exc.value)


# =============================================================================
# Tool Registration Tests
# =============================================================================


class TestWaypointToolRegistration:
    """Test waypoint tool registration."""

    def test_tool_registered(self, waypoint_universe: UniverseGraph):
        """universe_optimize_waypoints tool is registered."""
        mock_server = MagicMock()
        register_waypoints_tools(mock_server, waypoint_universe)

        mock_server.tool.assert_called()


# =============================================================================
# Model Tests
# =============================================================================


class TestOptimizedWaypointResultModel:
    """Test OptimizedWaypointResult model."""

    def test_model_serialization(self, registered_waypoint_universe: UniverseGraph):
        """Result serializes to valid dict."""
        tool = _capture_tool(registered_waypoint_universe)
        result = asyncio.run(tool(waypoints=["Jita", "Perimeter", "Urlen"]))

        # Should be a dict (model_dump output)
        assert isinstance(result, dict)
        assert isinstance(result["waypoints"], list)
        assert isinstance(result["route_systems"], list)

    def test_waypoint_info_fields(self, registered_waypoint_universe: UniverseGraph):
        """WaypointInfo has all required fields."""
        tool = _capture_tool(registered_waypoint_universe)
        result = asyncio.run(tool(waypoints=["Jita", "Perimeter"]))

        wp = result["waypoints"][0]
        assert "name" in wp
        assert "system_id" in wp
        assert "security" in wp
        assert "security_class" in wp
        assert "region" in wp
        assert "visit_order" in wp
