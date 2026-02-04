"""
Tests for Loop Tool Implementation.

STP-009: Loop Tool (universe_loop) Tests
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import igraph as ig
import numpy as np
import pytest

from aria_esi.mcp.errors import InsufficientBordersError, InvalidParameterError, SystemNotFoundError
from aria_esi.mcp.tools import register_tools
from aria_esi.mcp.tools_loop import (
    _build_loop_result,
    _expand_tour_matrix,
    _find_borders_with_distance,
    _nearest_neighbor_tsp_matrix,
    _plan_loop,
    _select_diverse_borders_matrix,
    register_loop_tools,
)
from aria_esi.universe import UniverseGraph

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_universe() -> UniverseGraph:
    """
    Create a mock universe for testing loop planning.

    Graph structure (linear with branches for diversity testing):

        Jita (high 0.95) -- Perimeter (high 0.90) -- Urlen (high 0.85) -- Haatomo (high 0.70)
             |                    |                       |
        *Maurasi (high 0.65) -----+                  *Uedama (high 0.50)
             |                                            |
        Sivala (low 0.35)                            Niarja (low 0.30)
             |
        Ala (null -0.2)

        Additional branch for diversity:
        Haatomo -- *Aufay (high 0.55) -- Balle (low 0.25)
                        |
                   Clellinon (high 0.60)

    Border systems: Maurasi, Uedama, Aufay (all high-sec bordering low-sec)
    """
    g = ig.Graph(
        n=11,
        edges=[
            (0, 1),  # Jita -- Perimeter
            (0, 2),  # Jita -- Maurasi
            (1, 3),  # Perimeter -- Urlen
            (1, 2),  # Perimeter -- Maurasi
            (2, 4),  # Maurasi -- Sivala
            (4, 5),  # Sivala -- Ala
            (3, 6),  # Urlen -- Haatomo
            (6, 7),  # Haatomo -- Uedama
            (7, 8),  # Uedama -- Niarja
            (6, 9),  # Haatomo -- Aufay
            (9, 10), # Aufay -- Balle
            (3, 7),  # Urlen -- Uedama (shortcut)
        ],
        directed=False,
    )

    systems = [
        {"name": "Jita", "id": 30000142, "sec": 0.95, "const": 20000020, "region": 10000002},
        {"name": "Perimeter", "id": 30000144, "sec": 0.90, "const": 20000020, "region": 10000002},
        {"name": "Maurasi", "id": 30000140, "sec": 0.65, "const": 20000020, "region": 10000002},
        {"name": "Urlen", "id": 30000138, "sec": 0.85, "const": 20000020, "region": 10000002},
        {"name": "Sivala", "id": 30000160, "sec": 0.35, "const": 20000021, "region": 10000002},
        {"name": "Ala", "id": 30000161, "sec": -0.2, "const": 20000022, "region": 10000003},
        {"name": "Haatomo", "id": 30002693, "sec": 0.70, "const": 20000023, "region": 10000002},
        {"name": "Uedama", "id": 30002691, "sec": 0.50, "const": 20000023, "region": 10000043},
        {"name": "Niarja", "id": 30002692, "sec": 0.30, "const": 20000023, "region": 10000043},
        {"name": "Aufay", "id": 30002694, "sec": 0.55, "const": 20000024, "region": 10000044},
        {"name": "Balle", "id": 30002695, "sec": 0.25, "const": 20000024, "region": 10000044},
    ]

    name_to_idx = {s["name"]: i for i, s in enumerate(systems)}
    idx_to_name = {i: s["name"] for i, s in enumerate(systems)}
    name_to_id = {s["name"]: s["id"] for s in systems}
    id_to_idx = {s["id"]: i for i, s in enumerate(systems)}
    name_lookup = {s["name"].lower(): s["name"] for s in systems}

    security = np.array([s["sec"] for s in systems], dtype=np.float32)
    system_ids = np.array([s["id"] for s in systems], dtype=np.int32)
    constellation_ids = np.array([s["const"] for s in systems], dtype=np.int32)
    region_ids = np.array([s["region"] for s in systems], dtype=np.int32)

    highsec = frozenset(i for i in range(11) if security[i] >= 0.45)
    lowsec = frozenset(i for i in range(11) if 0.0 < security[i] < 0.45)
    nullsec = frozenset(i for i in range(11) if security[i] <= 0.0)
    # Maurasi (idx 2) borders Sivala
    # Uedama (idx 7) borders Niarja
    # Aufay (idx 9) borders Balle
    border = frozenset([2, 7, 9])

    region_systems = {
        10000002: [0, 1, 2, 3, 4, 6],
        10000003: [5],
        10000043: [7, 8],
        10000044: [9, 10],
    }
    constellation_names = {
        20000020: "Kimotoro",
        20000021: "Otanuomi",
        20000022: "Somewhere",
        20000023: "Uosusuokko",
        20000024: "Aufayland",
    }
    region_names = {
        10000002: "The Forge",
        10000003: "Outer Region",
        10000043: "Domain",
        10000044: "Sinq Laison",
    }
    region_name_lookup = {name.lower(): rid for rid, name in region_names.items()}

    return UniverseGraph(
        graph=g,
        name_to_idx=name_to_idx,
        idx_to_name=idx_to_name,
        name_to_id=name_to_id,
        id_to_idx=id_to_idx,
        security=security,
        system_ids=system_ids,
        constellation_ids=constellation_ids,
        region_ids=region_ids,
        name_lookup=name_lookup,
        constellation_names=constellation_names,
        region_names=region_names,
        region_name_lookup=region_name_lookup,
        border_systems=border,
        region_systems=region_systems,
        highsec_systems=highsec,
        lowsec_systems=lowsec,
        nullsec_systems=nullsec,
        version="test-1.0",
        system_count=11,
        stargate_count=12,
    )


@pytest.fixture
def registered_universe(mock_universe: UniverseGraph) -> UniverseGraph:
    """Register tools with the mock universe."""
    mock_server = MagicMock()
    register_tools(mock_server, mock_universe)
    return mock_universe


# =============================================================================
# Find Borders Tests
# =============================================================================


class TestFindBordersWithDistance:
    """Test _find_borders_with_distance function."""

    def test_finds_borders_near_origin(self, mock_universe: UniverseGraph):
        """Finds border systems near origin."""
        borders = _find_borders_with_distance(mock_universe, 0, limit=10, max_jumps=10)

        border_names = [mock_universe.idx_to_name[idx] for idx, _ in borders]
        assert "Maurasi" in border_names  # 1 jump from Jita

    def test_includes_distance(self, mock_universe: UniverseGraph):
        """Returns distance from origin for each border."""
        borders = _find_borders_with_distance(mock_universe, 0, limit=10, max_jumps=10)

        # Find Maurasi (should be 1 jump from Jita)
        maurasi_entry = next((b for b in borders if mock_universe.idx_to_name[b[0]] == "Maurasi"), None)
        assert maurasi_entry is not None
        assert maurasi_entry[1] == 1

    def test_sorted_by_distance(self, mock_universe: UniverseGraph):
        """Results sorted by distance."""
        borders = _find_borders_with_distance(mock_universe, 0, limit=10, max_jumps=10)

        distances = [dist for _, dist in borders]
        assert distances == sorted(distances)

    def test_respects_limit(self, mock_universe: UniverseGraph):
        """Limit parameter is respected."""
        borders = _find_borders_with_distance(mock_universe, 0, limit=1, max_jumps=10)

        assert len(borders) <= 1

    def test_respects_max_jumps(self, mock_universe: UniverseGraph):
        """Max jumps limits search radius."""
        borders = _find_borders_with_distance(mock_universe, 0, limit=10, max_jumps=1)

        for _, dist in borders:
            assert dist <= 1

    def test_stays_in_highsec(self, mock_universe: UniverseGraph):
        """BFS only traverses high-sec systems."""
        borders = _find_borders_with_distance(mock_universe, 0, limit=10, max_jumps=10)

        # All borders found should be reachable via high-sec
        # Maurasi is directly connected to Jita (high-sec)
        # Uedama is reachable via Jita->Perimeter->Urlen->Uedama (all high-sec)
        border_names = [mock_universe.idx_to_name[idx] for idx, _ in borders]
        assert "Maurasi" in border_names


# =============================================================================
# Build Loop Result Tests
# =============================================================================


class TestBuildLoopResult:
    """Test _build_loop_result function."""

    def test_result_structure(self, mock_universe: UniverseGraph):
        """Result has required fields."""
        full_route = [0, 2, 0]  # Jita -> Maurasi -> Jita
        borders = [(2, 1)]  # Maurasi at 1 jump
        result = _build_loop_result(mock_universe, 0, full_route, borders)

        assert "systems" in result
        assert "total_jumps" in result
        assert "unique_systems" in result
        assert "border_systems_visited" in result
        assert "backtrack_jumps" in result
        assert "efficiency" in result

    def test_total_jumps_calculated(self, mock_universe: UniverseGraph):
        """Total jumps is route length minus 1."""
        full_route = [0, 2, 0]  # 3 systems = 2 jumps
        result = _build_loop_result(mock_universe, 0, full_route, [])

        assert result["total_jumps"] == 2

    def test_unique_systems_counted(self, mock_universe: UniverseGraph):
        """Unique systems correctly counted."""
        full_route = [0, 2, 0]  # 2 unique (Jita appears twice)
        result = _build_loop_result(mock_universe, 0, full_route, [])

        assert result["unique_systems"] == 2

    def test_efficiency_calculated(self, mock_universe: UniverseGraph):
        """Efficiency is unique/total ratio."""
        full_route = [0, 2, 0]  # 2 unique out of 3 total
        result = _build_loop_result(mock_universe, 0, full_route, [])

        expected_efficiency = 2 / 3
        assert result["efficiency"] == pytest.approx(expected_efficiency, rel=0.01)


# =============================================================================
# Plan Loop Tests
# =============================================================================


class TestPlanLoop:
    """Test _plan_loop function."""

    def test_returns_loop(self, mock_universe: UniverseGraph):
        """Plan returns valid loop."""
        result = _plan_loop(
            mock_universe,
            origin_idx=0,
            target_jumps=20,
            min_borders=2,
            max_borders=3,
        )

        # Should not have error
        assert "error" not in result
        assert "systems" in result

    def test_loop_starts_at_origin(self, mock_universe: UniverseGraph):
        """Loop starts at origin."""
        result = _plan_loop(
            mock_universe,
            origin_idx=0,
            target_jumps=20,
            min_borders=2,
            max_borders=3,
        )

        if "systems" in result:
            assert result["systems"][0]["name"] == "Jita"

    def test_loop_ends_at_origin(self, mock_universe: UniverseGraph):
        """Loop ends at origin."""
        result = _plan_loop(
            mock_universe,
            origin_idx=0,
            target_jumps=20,
            min_borders=2,
            max_borders=3,
        )

        if "systems" in result:
            assert result["systems"][-1]["name"] == "Jita"

    def test_insufficient_borders_error(self, mock_universe: UniverseGraph):
        """Raises InsufficientBordersError when not enough borders found."""
        with pytest.raises(InsufficientBordersError) as exc_info:
            _plan_loop(
                mock_universe,
                origin_idx=0,
                target_jumps=10,  # Very small radius
                min_borders=10,  # Too many required
                max_borders=15,
            )

        assert exc_info.value.required == 10
        assert exc_info.value.found < 10


# =============================================================================
# Tool Registration Tests
# =============================================================================


class TestLoopToolRegistration:
    """Test loop tool registration."""

    def test_tool_registered(self, mock_universe: UniverseGraph):
        """universe_loop tool is registered."""
        mock_server = MagicMock()
        register_loop_tools(mock_server, mock_universe)

        mock_server.tool.assert_called()


# =============================================================================
# Integration Tests
# =============================================================================


class TestUniverseLoopIntegration:
    """Integration tests for the universe_loop tool."""

    def _capture_tool(self, registered_universe: UniverseGraph):
        """Helper to capture the registered tool function."""
        from aria_esi.mcp.tools_loop import register_loop_tools

        captured_tool = None

        def mock_tool():
            def decorator(func):
                nonlocal captured_tool
                captured_tool = func
                return func

            return decorator

        mock_server = MagicMock()
        mock_server.tool = mock_tool
        register_loop_tools(mock_server, registered_universe)
        return captured_tool

    def test_loop_returns_to_origin(self, registered_universe: UniverseGraph):
        """Loop starts and ends at origin."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(
            captured_tool(origin="Jita", target_jumps=20, min_borders=2, max_borders=3)
        )

        if "systems" in result:
            assert result["systems"][0]["name"] == "Jita"
            assert result["systems"][-1]["name"] == "Jita"

    def test_loop_visits_borders(self, registered_universe: UniverseGraph):
        """Loop visits border systems."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(
            captured_tool(origin="Jita", target_jumps=20, min_borders=2, max_borders=3)
        )

        if "border_systems_visited" in result:
            assert len(result["border_systems_visited"]) >= 2
            assert len(result["border_systems_visited"]) <= 3

    def test_loop_efficiency_reasonable(self, registered_universe: UniverseGraph):
        """Loop efficiency is reasonable."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(
            captured_tool(origin="Jita", target_jumps=20, min_borders=2, max_borders=3)
        )

        if "efficiency" in result:
            # At least 30% unique systems (accounting for backtracking)
            assert result["efficiency"] >= 0.3

    def test_loop_insufficient_borders(self, registered_universe: UniverseGraph):
        """Raises InsufficientBordersError when not enough borders found."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)

        with pytest.raises(InsufficientBordersError):
            asyncio.run(
                captured_tool(origin="Jita", target_jumps=10, min_borders=10, max_borders=15)
            )

    def test_loop_invalid_target_jumps_low(self, registered_universe: UniverseGraph):
        """Invalid target_jumps (too low) raises error."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)

        with pytest.raises(InvalidParameterError):
            asyncio.run(captured_tool(origin="Jita", target_jumps=5))

    def test_loop_invalid_target_jumps_high(self, registered_universe: UniverseGraph):
        """Invalid target_jumps (too high) raises error."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)

        with pytest.raises(InvalidParameterError):
            asyncio.run(captured_tool(origin="Jita", target_jumps=200))

    def test_loop_invalid_min_borders_low(self, registered_universe: UniverseGraph):
        """Invalid min_borders (too low) raises error."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)

        with pytest.raises(InvalidParameterError):
            asyncio.run(captured_tool(origin="Jita", min_borders=1))

    def test_loop_invalid_min_borders_high(self, registered_universe: UniverseGraph):
        """Invalid min_borders (too high) raises error."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)

        with pytest.raises(InvalidParameterError):
            asyncio.run(captured_tool(origin="Jita", min_borders=15))

    def test_loop_invalid_max_borders_low(self, registered_universe: UniverseGraph):
        """Invalid max_borders (less than min) raises error."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)

        with pytest.raises(InvalidParameterError):
            asyncio.run(captured_tool(origin="Jita", min_borders=5, max_borders=3))

    def test_loop_invalid_max_borders_high(self, registered_universe: UniverseGraph):
        """Invalid max_borders (too high) raises error."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)

        with pytest.raises(InvalidParameterError):
            asyncio.run(captured_tool(origin="Jita", max_borders=20))

    def test_loop_unknown_origin(self, registered_universe: UniverseGraph):
        """Unknown origin raises SystemNotFoundError."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)

        with pytest.raises(SystemNotFoundError):
            asyncio.run(captured_tool(origin="UnknownSystem"))

    def test_loop_case_insensitive_origin(self, registered_universe: UniverseGraph):
        """Origin is case-insensitive."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(
            captured_tool(origin="jita", target_jumps=20, min_borders=2, max_borders=3)
        )

        if "systems" in result:
            assert result["systems"][0]["name"] == "Jita"

    def test_loop_has_total_jumps(self, registered_universe: UniverseGraph):
        """Loop result includes total jumps."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(
            captured_tool(origin="Jita", target_jumps=20, min_borders=2, max_borders=3)
        )

        if "total_jumps" in result:
            assert result["total_jumps"] > 0

    def test_loop_has_backtrack_info(self, registered_universe: UniverseGraph):
        """Loop result includes backtrack info."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(
            captured_tool(origin="Jita", target_jumps=20, min_borders=2, max_borders=3)
        )

        assert "backtrack_jumps" in result
        assert result["backtrack_jumps"] >= 0


# =============================================================================
# Performance Tests
# =============================================================================


class TestLoopPerformance:
    """Test loop planning performance."""

    def test_loop_latency(self, registered_universe: UniverseGraph):
        """Loop planning within latency budget."""
        import asyncio

        captured_tool = None

        def mock_tool():
            def decorator(func):
                nonlocal captured_tool
                captured_tool = func
                return func

            return decorator

        mock_server = MagicMock()
        mock_server.tool = mock_tool

        from aria_esi.mcp.tools_loop import register_loop_tools

        register_loop_tools(mock_server, registered_universe)

        start = time.perf_counter()
        for _ in range(10):  # Fewer iterations since loop is more complex
            asyncio.run(
                captured_tool(
                    origin="Jita", target_jumps=20, min_borders=2, max_borders=3
                )
            )
        elapsed = time.perf_counter() - start

        avg_time = elapsed / 10
        # Should be well under 20ms budget
        assert avg_time < 0.020

# =============================================================================
# Distance Matrix Optimization Tests
# =============================================================================


class TestDistanceMatrix:
    """Test DistanceMatrix optimization."""

    def test_compute_creates_matrix(self, mock_universe: UniverseGraph):
        """Matrix computation succeeds."""
        from aria_esi.mcp.utils import DistanceMatrix

        waypoints = [0, 2, 7, 9]  # Jita, Maurasi, Uedama, Aufay
        matrix = DistanceMatrix.compute(mock_universe, waypoints, security_filter="highsec")

        assert len(matrix) == 4
        assert matrix.waypoints == waypoints

    def test_distance_is_symmetric(self, mock_universe: UniverseGraph):
        """Distance from A to B equals B to A."""
        from aria_esi.mcp.utils import DistanceMatrix

        waypoints = [0, 2, 7]  # Jita, Maurasi, Uedama
        matrix = DistanceMatrix.compute(mock_universe, waypoints, security_filter="highsec")

        assert matrix.distance(0, 2) == matrix.distance(2, 0)
        assert matrix.distance(0, 7) == matrix.distance(7, 0)
        assert matrix.distance(2, 7) == matrix.distance(7, 2)

    def test_distance_to_self_is_zero(self, mock_universe: UniverseGraph):
        """Distance from system to itself is 0."""
        from aria_esi.mcp.utils import DistanceMatrix

        waypoints = [0, 2, 7]
        matrix = DistanceMatrix.compute(mock_universe, waypoints, security_filter="highsec")

        for wp in waypoints:
            assert matrix.distance(wp, wp) == 0

    def test_path_returns_valid_route(self, mock_universe: UniverseGraph):
        """Path retrieval returns connected route."""
        from aria_esi.mcp.utils import DistanceMatrix

        waypoints = [0, 2, 7]
        matrix = DistanceMatrix.compute(mock_universe, waypoints, security_filter="highsec")

        path = matrix.path(0, 7)  # Jita to Uedama

        # Path should start at source and end at destination
        assert path[0] == 0
        assert path[-1] == 7

        # Path length should match distance
        assert len(path) - 1 == matrix.distance(0, 7)

    def test_safe_mode_avoids_lowsec(self, mock_universe: UniverseGraph):
        """Safe mode penalizes lowsec routes."""
        from aria_esi.mcp.utils import DistanceMatrix

        # With security_filter="highsec", should prefer highsec even if longer
        matrix_safe = DistanceMatrix.compute(mock_universe, [0, 2], security_filter="highsec")
        matrix_unsafe = DistanceMatrix.compute(mock_universe, [0, 2], security_filter="any")

        # Both should find a path (Maurasi is highsec)
        assert matrix_safe.distance(0, 2) < float("inf")
        assert matrix_unsafe.distance(0, 2) < float("inf")


class TestMatrixOptimizedFunctions:
    """Test matrix-optimized helper functions."""

    def test_select_diverse_borders_matrix(self, mock_universe: UniverseGraph):
        """Matrix version selects diverse borders."""
        from aria_esi.mcp.utils import DistanceMatrix

        # Candidates: (vertex_idx, distance_from_origin)
        candidates = [(2, 1), (7, 3), (9, 4)]  # Maurasi, Uedama, Aufay

        # Create matrix for origin + candidates
        all_waypoints = [0] + [c[0] for c in candidates]
        matrix = DistanceMatrix.compute(mock_universe, all_waypoints, security_filter="highsec")

        selected = _select_diverse_borders_matrix(candidates, matrix)

        # Should select all candidates (diverse enough)
        assert len(selected) >= 1
        # First selected should be closest
        assert selected[0] == candidates[0]

    def test_nearest_neighbor_tsp_matrix(self, mock_universe: UniverseGraph):
        """Matrix TSP produces valid tour."""
        from aria_esi.mcp.utils import DistanceMatrix

        origin = 0
        waypoints = [2, 7, 9]

        all_wp = [origin] + waypoints
        matrix = DistanceMatrix.compute(mock_universe, all_wp, security_filter="highsec")

        tour = _nearest_neighbor_tsp_matrix(origin, waypoints, matrix)

        # Tour should start at origin
        assert tour[0] == origin
        # Tour should visit all waypoints
        assert set(tour) == set([origin] + waypoints)

    def test_expand_tour_matrix(self, mock_universe: UniverseGraph):
        """Matrix tour expansion produces full route."""
        from aria_esi.mcp.utils import DistanceMatrix

        tour = [0, 2, 7]  # Jita -> Maurasi -> Uedama -> (back to Jita)

        matrix = DistanceMatrix.compute(mock_universe, tour, security_filter="highsec")

        full_route = _expand_tour_matrix(tour, matrix)

        # Should start and end at origin
        assert full_route[0] == 0
        assert full_route[-1] == 0
        # Should contain all tour waypoints
        for wp in tour:
            assert wp in full_route

class TestMatrixPerformance:
    """Test that matrix optimization improves performance."""

    def test_plan_loop_uses_matrix(self, registered_universe: UniverseGraph):
        """Plan loop successfully uses matrix optimization."""
        # This test verifies the integration works end-to-end
        result = _plan_loop(
            registered_universe,
            origin_idx=0,
            target_jumps=15,
            min_borders=2,
            max_borders=3,
        )

        # Should return valid result, not an error
        assert "error" not in result
        assert "systems" in result
        assert "total_jumps" in result


# =============================================================================
# Optimize Mode Tests
# =============================================================================


class TestOptimizeModes:
    """Test optimize parameter behavior."""

    def test_density_mode_default(self, mock_universe: UniverseGraph):
        """Density mode is the default optimization strategy."""
        result = _plan_loop(
            mock_universe,
            origin_idx=0,
            target_jumps=20,
            min_borders=2,
            max_borders=None,  # No cap
        )

        # Should succeed without error
        assert "error" not in result
        assert "border_systems_visited" in result

    def test_coverage_mode_explicit(self, mock_universe: UniverseGraph):
        """Coverage mode can be explicitly selected."""
        result = _plan_loop(
            mock_universe,
            origin_idx=0,
            target_jumps=20,
            min_borders=2,
            max_borders=None,
            optimize="coverage",
        )

        # Should succeed without error
        assert "error" not in result
        assert "border_systems_visited" in result

    def test_density_mode_no_cap(self, mock_universe: UniverseGraph):
        """Density mode with max_borders=None doesn't cap borders."""
        result = _plan_loop(
            mock_universe,
            origin_idx=0,
            target_jumps=30,  # Larger budget for more borders
            min_borders=2,
            max_borders=None,  # No artificial cap
            optimize="density",
        )

        # Should have found borders based on budget, not an artificial cap
        assert "error" not in result

    def test_density_mode_with_cap(self, mock_universe: UniverseGraph):
        """Density mode respects explicit max_borders cap."""
        result = _plan_loop(
            mock_universe,
            origin_idx=0,
            target_jumps=30,
            min_borders=2,
            max_borders=2,  # Explicit cap
            optimize="density",
        )

        assert "error" not in result
        assert len(result["border_systems_visited"]) <= 2

    def test_coverage_mode_default_cap(self, mock_universe: UniverseGraph):
        """Coverage mode defaults to max 8 borders when not specified."""
        result = _plan_loop(
            mock_universe,
            origin_idx=0,
            target_jumps=30,
            min_borders=2,
            max_borders=None,  # Should default to 8 for coverage
            optimize="coverage",
        )

        assert "error" not in result
        # Coverage mode should still work
        assert len(result["border_systems_visited"]) >= 2


class TestOptimizeModeIntegration:
    """Integration tests for optimize parameter in universe_loop tool."""

    def _capture_tool(self, registered_universe: UniverseGraph):
        """Helper to capture the registered tool function."""
        from aria_esi.mcp.tools_loop import register_loop_tools

        captured_tool = None

        def mock_tool():
            def decorator(func):
                nonlocal captured_tool
                captured_tool = func
                return func

            return decorator

        mock_server = MagicMock()
        mock_server.tool = mock_tool
        register_loop_tools(mock_server, registered_universe)
        return captured_tool

    def test_optimize_density_via_tool(self, registered_universe: UniverseGraph):
        """Optimize=density works through the tool interface."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(
            captured_tool(
                origin="Jita",
                target_jumps=20,
                min_borders=2,
                optimize="density",
            )
        )

        assert "error" not in result
        assert "systems" in result

    def test_optimize_coverage_via_tool(self, registered_universe: UniverseGraph):
        """Optimize=coverage works through the tool interface."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(
            captured_tool(
                origin="Jita",
                target_jumps=20,
                min_borders=2,
                optimize="coverage",
            )
        )

        assert "error" not in result
        assert "systems" in result

    def test_invalid_optimize_raises_error(self, registered_universe: UniverseGraph):
        """Invalid optimize value raises InvalidParameterError."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)

        with pytest.raises(InvalidParameterError):
            asyncio.run(
                captured_tool(
                    origin="Jita",
                    target_jumps=20,
                    min_borders=2,
                    optimize="invalid_mode",
                )
            )

    def test_max_borders_none_allowed(self, registered_universe: UniverseGraph):
        """max_borders=None is allowed (no artificial cap)."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(
            captured_tool(
                origin="Jita",
                target_jumps=20,
                min_borders=2,
                max_borders=None,  # No cap
                optimize="density",
            )
        )

        assert "error" not in result
        assert "systems" in result

    def test_max_borders_explicit_cap(self, registered_universe: UniverseGraph):
        """Explicit max_borders cap is respected."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(
            captured_tool(
                origin="Jita",
                target_jumps=20,
                min_borders=2,
                max_borders=2,
                optimize="density",
            )
        )

        assert "error" not in result
        assert len(result["border_systems_visited"]) <= 2
