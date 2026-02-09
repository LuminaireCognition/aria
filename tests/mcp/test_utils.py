"""
Tests for MCP Utils Module.

Covers DistanceMatrix, weight computation, and shared utility functions.
"""

from __future__ import annotations

import pytest

from aria_esi.mcp.errors import InvalidParameterError
from aria_esi.mcp.utils import (
    HIGHSEC_THRESHOLD,
    LOWSEC_THRESHOLD,
    WEIGHT_AVOID,
    WEIGHT_LOWSEC_PENALTY,
    WEIGHT_NORMAL,
    WEIGHT_NULLSEC_PENALTY,
    DistanceMatrix,
    build_system_info,
    compute_filtered_weights,
    compute_safe_weights,
    get_security_threshold,
)
from aria_esi.universe import UniverseGraph

from .conftest import create_mock_universe

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def route_universe() -> UniverseGraph:
    """
    Universe for testing routing weights.

    Graph structure:
        Jita (high 0.95) -- Perimeter (high 0.90) -- Urlen (high 0.85)
             |                    |
        Maurasi (high 0.65) ------+
             |
        Sivala (low 0.35)
             |
        Ala (null -0.2)
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
        {"name": "Ala", "id": 30000161, "sec": -0.2, "const": 20000022, "region": 10000003,
         "const_name": "Somewhere", "region_name": "Outer Region"},
    ]
    edges = [
        (0, 1),  # Jita -- Perimeter
        (0, 2),  # Jita -- Maurasi
        (1, 3),  # Perimeter -- Urlen
        (1, 2),  # Perimeter -- Maurasi
        (2, 4),  # Maurasi -- Sivala
        (4, 5),  # Sivala -- Ala
    ]
    return create_mock_universe(systems, edges)


@pytest.fixture
def disconnected_universe() -> UniverseGraph:
    """Universe with two disconnected components for testing unreachable paths."""
    systems = [
        {"name": "Island1", "id": 30000001, "sec": 0.9, "const": 20000001, "region": 10000001,
         "const_name": "North", "region_name": "North Region"},
        {"name": "Island2", "id": 30000002, "sec": 0.9, "const": 20000001, "region": 10000001,
         "const_name": "North", "region_name": "North Region"},
        {"name": "Island3", "id": 30000003, "sec": 0.9, "const": 20000002, "region": 10000002,
         "const_name": "South", "region_name": "South Region"},
        {"name": "Island4", "id": 30000004, "sec": 0.9, "const": 20000002, "region": 10000002,
         "const_name": "South", "region_name": "South Region"},
    ]
    edges = [
        (0, 1),  # North cluster
        (2, 3),  # South cluster (disconnected from North)
    ]
    return create_mock_universe(systems, edges)


# =============================================================================
# DistanceMatrix Tests
# =============================================================================


class TestDistanceMatrix:
    """Tests for DistanceMatrix class."""

    def test_compute_basic(self, route_universe: UniverseGraph):
        """Basic distance matrix computation."""
        waypoints = [0, 1, 2, 3]  # Jita, Perimeter, Maurasi, Urlen
        matrix = DistanceMatrix.compute(route_universe, waypoints)

        assert len(matrix) == 4
        assert matrix.waypoints == waypoints

    def test_distance_lookup(self, route_universe: UniverseGraph):
        """Distance lookups return correct values."""
        waypoints = [0, 1, 2, 3]  # Jita, Perimeter, Maurasi, Urlen
        matrix = DistanceMatrix.compute(route_universe, waypoints)

        # Direct connections
        assert matrix.distance(0, 1) == 1  # Jita -> Perimeter
        assert matrix.distance(0, 2) == 1  # Jita -> Maurasi

        # Same system
        assert matrix.distance(0, 0) == 0

        # Multi-hop
        assert matrix.distance(0, 3) == 2  # Jita -> Perimeter -> Urlen

    def test_path_lookup(self, route_universe: UniverseGraph):
        """Path lookups return correct vertex lists."""
        waypoints = [0, 1, 2, 3]  # Jita, Perimeter, Maurasi, Urlen
        matrix = DistanceMatrix.compute(route_universe, waypoints)

        # Direct path
        path = matrix.path(0, 1)
        assert path == [0, 1]

        # Multi-hop path
        path = matrix.path(0, 3)
        assert len(path) == 3
        assert path[0] == 0
        assert path[-1] == 3

    def test_disconnected_returns_infinity(self, disconnected_universe: UniverseGraph):
        """Unreachable systems have infinite distance."""
        waypoints = [0, 1, 2, 3]  # All four islands
        matrix = DistanceMatrix.compute(disconnected_universe, waypoints)

        # Same cluster - reachable
        assert matrix.distance(0, 1) == 1
        assert matrix.distance(2, 3) == 1

        # Different clusters - unreachable
        assert matrix.distance(0, 2) == float("inf")
        assert matrix.distance(1, 3) == float("inf")

    def test_disconnected_returns_empty_path(self, disconnected_universe: UniverseGraph):
        """Unreachable systems have empty path."""
        waypoints = [0, 2]  # From different clusters
        matrix = DistanceMatrix.compute(disconnected_universe, waypoints)

        path = matrix.path(0, 2)
        assert path == []

    def test_invalid_waypoint_raises(self, route_universe: UniverseGraph):
        """Invalid waypoint indices raise error."""
        with pytest.raises(InvalidParameterError) as exc_info:
            DistanceMatrix.compute(route_universe, [0, 1, 100])  # 100 is out of range

        assert exc_info.value.param == "waypoints"

    def test_security_filter_highsec(self, route_universe: UniverseGraph):
        """Highsec security filter penalizes low/null systems."""
        # Include systems that span high/low/null
        waypoints = [0, 2, 4, 5]  # Jita, Maurasi, Sivala, Ala
        matrix = DistanceMatrix.compute(
            route_universe, waypoints, security_filter="highsec"
        )

        # Path through high-sec should be preferred
        # But with penalties, the graph should still be connected
        dist = matrix.distance(0, 4)  # Jita -> Sivala via Maurasi
        assert dist >= 2  # At least 2 jumps

    def test_security_filter_lowsec(self, route_universe: UniverseGraph):
        """Lowsec security filter allows low-sec systems."""
        waypoints = [0, 2, 4, 5]  # Jita, Maurasi, Sivala, Ala
        matrix = DistanceMatrix.compute(
            route_universe, waypoints, security_filter="lowsec"
        )

        # Should allow low-sec without heavy penalty
        dist = matrix.distance(0, 4)
        assert dist == 2  # Jita -> Maurasi -> Sivala

    def test_security_filter_any(self, route_universe: UniverseGraph):
        """Any security filter has no restrictions."""
        waypoints = [0, 2, 4, 5]
        matrix = DistanceMatrix.compute(
            route_universe, waypoints, security_filter="any"
        )

        # No security penalty
        dist = matrix.distance(0, 5)  # Jita -> Maurasi -> Sivala -> Ala
        assert dist == 3

    def test_avoid_systems(self, route_universe: UniverseGraph):
        """Avoided systems are not traversed."""
        waypoints = [0, 1, 3]  # Jita, Perimeter, Urlen
        # Avoid Perimeter - forces longer route
        matrix = DistanceMatrix.compute(
            route_universe, waypoints, avoid_systems={1}
        )

        # Jita -> Urlen now must go through Maurasi
        dist = matrix.distance(0, 3)
        # With Perimeter blocked, route is Jita -> Maurasi -> Urlen (2 jumps)
        # Or through other paths if available
        assert dist >= 2

    def test_len_returns_waypoint_count(self, route_universe: UniverseGraph):
        """__len__ returns number of waypoints."""
        waypoints = [0, 1, 2]
        matrix = DistanceMatrix.compute(route_universe, waypoints)
        assert len(matrix) == 3


# =============================================================================
# Weight Computation Tests
# =============================================================================


class TestComputeSafeWeights:
    """Tests for compute_safe_weights function."""

    def test_returns_weight_list(self, route_universe: UniverseGraph):
        """Returns a list of weights for all edges."""
        weights = compute_safe_weights(route_universe)

        # Should have one weight per edge
        assert len(weights) == route_universe.graph.ecount()

    def test_highsec_destinations_normal_weight(self, route_universe: UniverseGraph):
        """Edges to high-sec systems have normal weight."""
        weights = compute_safe_weights(route_universe)

        # Find edge to Jita (idx 0, sec 0.95)
        for edge in route_universe.graph.es:
            if route_universe.security[edge.target] >= HIGHSEC_THRESHOLD:
                assert weights[edge.index] == WEIGHT_NORMAL

    def test_lowsec_destinations_penalty_weight(self, route_universe: UniverseGraph):
        """Edges to low-sec systems have penalty weight."""
        weights = compute_safe_weights(route_universe)

        # Find edge to Sivala (idx 4, sec 0.35)
        for edge in route_universe.graph.es:
            target_sec = route_universe.security[edge.target]
            if LOWSEC_THRESHOLD <= target_sec < HIGHSEC_THRESHOLD:
                assert weights[edge.index] == WEIGHT_LOWSEC_PENALTY

    def test_nullsec_destinations_heavy_penalty(self, route_universe: UniverseGraph):
        """Edges to null-sec systems have heavy penalty."""
        weights = compute_safe_weights(route_universe)

        # Find edge to Ala (idx 5, sec -0.2)
        for edge in route_universe.graph.es:
            if route_universe.security[edge.target] < LOWSEC_THRESHOLD:
                assert weights[edge.index] == WEIGHT_NULLSEC_PENALTY


class TestComputeFilteredWeights:
    """Tests for compute_filtered_weights function."""

    def test_any_filter_no_avoid_returns_none(self, route_universe: UniverseGraph):
        """Any filter with no avoidance returns None for unweighted routing."""
        weights = compute_filtered_weights(route_universe, security_filter="any")
        assert weights is None

    def test_any_filter_with_avoid_returns_weights(self, route_universe: UniverseGraph):
        """Any filter with avoidance returns weight list."""
        weights = compute_filtered_weights(
            route_universe, security_filter="any", avoid_systems={1}
        )
        assert weights is not None
        assert len(weights) == route_universe.graph.ecount()

    def test_avoid_systems_infinite_weight(self, route_universe: UniverseGraph):
        """Avoided systems get infinite weight on incoming edges."""
        avoid = {1}  # Perimeter
        weights = compute_filtered_weights(
            route_universe, security_filter="any", avoid_systems=avoid
        )

        for edge in route_universe.graph.es:
            if edge.target in avoid:
                assert weights[edge.index] == WEIGHT_AVOID

    def test_highsec_filter_weights(self, route_universe: UniverseGraph):
        """Highsec filter applies correct weights."""
        weights = compute_filtered_weights(route_universe, security_filter="highsec")

        for edge in route_universe.graph.es:
            dst_sec = route_universe.security[edge.target]
            if dst_sec >= HIGHSEC_THRESHOLD:
                assert weights[edge.index] == WEIGHT_NORMAL
            elif dst_sec >= LOWSEC_THRESHOLD:
                assert weights[edge.index] == WEIGHT_LOWSEC_PENALTY
            else:
                assert weights[edge.index] == WEIGHT_NULLSEC_PENALTY

    def test_lowsec_filter_weights(self, route_universe: UniverseGraph):
        """Lowsec filter applies correct weights."""
        weights = compute_filtered_weights(route_universe, security_filter="lowsec")

        for edge in route_universe.graph.es:
            dst_sec = route_universe.security[edge.target]
            if dst_sec >= LOWSEC_THRESHOLD:
                assert weights[edge.index] == WEIGHT_NORMAL
            else:
                assert weights[edge.index] == WEIGHT_NULLSEC_PENALTY


class TestGetSecurityThreshold:
    """Tests for get_security_threshold function."""

    def test_highsec_threshold(self):
        """Highsec filter returns highsec threshold."""
        assert get_security_threshold("highsec") == HIGHSEC_THRESHOLD

    def test_lowsec_threshold(self):
        """Lowsec filter returns lowsec threshold."""
        assert get_security_threshold("lowsec") == LOWSEC_THRESHOLD

    def test_any_threshold(self):
        """Any filter returns -1.0 (allow all)."""
        assert get_security_threshold("any") == -1.0


# =============================================================================
# Build System Info Tests
# =============================================================================


class TestBuildSystemInfo:
    """Tests for build_system_info function."""

    def test_builds_complete_info(self, route_universe: UniverseGraph):
        """Builds complete SystemInfo with all fields."""
        info = build_system_info(route_universe, 0)  # Jita

        assert info.name == "Jita"
        assert info.system_id == 30000142
        assert info.security == pytest.approx(0.95, abs=0.01)
        assert info.security_class == "HIGH"
        assert info.region == "The Forge"
        assert info.constellation == "Kimotoro"

    def test_includes_neighbors(self, route_universe: UniverseGraph):
        """Includes neighbor information."""
        info = build_system_info(route_universe, 0)  # Jita

        assert len(info.neighbors) > 0
        neighbor_names = [n.name for n in info.neighbors]
        assert "Perimeter" in neighbor_names
        assert "Maurasi" in neighbor_names

    def test_neighbor_info_complete(self, route_universe: UniverseGraph):
        """Neighbor info includes security data."""
        info = build_system_info(route_universe, 0)  # Jita

        for neighbor in info.neighbors:
            assert neighbor.name is not None
            assert neighbor.security is not None
            assert neighbor.security_class in ("HIGH", "LOW", "NULL")

    def test_border_flag_set_correctly(self, route_universe: UniverseGraph):
        """Border flag correctly identifies border systems."""
        # Maurasi (idx 2) is a border system (high-sec adjacent to Sivala)
        info = build_system_info(route_universe, 2)
        assert info.is_border is True

        # Jita (idx 0) is not a border system
        info = build_system_info(route_universe, 0)
        assert info.is_border is False

    def test_adjacent_lowsec_populated(self, route_universe: UniverseGraph):
        """Adjacent low-sec systems are listed for border systems."""
        # Maurasi (idx 2) borders Sivala (low-sec)
        info = build_system_info(route_universe, 2)

        # Should have adjacent_lowsec info
        assert info.adjacent_lowsec is not None
        lowsec_names = [s for s in info.adjacent_lowsec]
        assert "Sivala" in lowsec_names


# =============================================================================
# Constants Tests
# =============================================================================


class TestConstants:
    """Tests for weight constants."""

    def test_weight_ordering(self):
        """Weight constants are in correct order."""
        assert WEIGHT_NORMAL < WEIGHT_LOWSEC_PENALTY
        assert WEIGHT_LOWSEC_PENALTY < WEIGHT_NULLSEC_PENALTY
        assert WEIGHT_NULLSEC_PENALTY < WEIGHT_AVOID

    def test_avoid_is_infinity(self):
        """WEIGHT_AVOID is effectively infinite."""
        assert WEIGHT_AVOID == float("inf")

    def test_threshold_values(self):
        """Security thresholds have expected values."""
        assert HIGHSEC_THRESHOLD == 0.45
        assert LOWSEC_THRESHOLD == 0.0
