"""
Tests for Loop Planning Algorithms.

Unit tests for TSP and border selection algorithms.
"""

from __future__ import annotations

import igraph as ig
import numpy as np
import pytest

from aria_esi.services.loop_planning.algorithms import (
    expand_tour,
    nearest_neighbor_tsp,
    select_borders_coverage,
    select_borders_density,
)
from aria_esi.universe import UniverseGraph


@pytest.fixture
def mock_universe() -> UniverseGraph:
    """
    Create a mock universe for testing loop planning algorithms.

    Graph structure (linear with branches):

        Jita (high 0.95) -- Perimeter (high 0.90) -- Urlen (high 0.85) -- Haatomo (high 0.70)
             |                    |                       |
        *Maurasi (high 0.65) -----+                  *Uedama (high 0.50)
             |                                            |
        Sivala (low 0.35)                            Niarja (low 0.30)

        Additional branch:
        Haatomo -- *Aufay (high 0.55) -- Balle (low 0.25)

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
            (9, 10),  # Aufay -- Balle
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
    border = frozenset([2, 7, 9])  # Maurasi, Uedama, Aufay

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


class TestSelectBordersDensity:
    """Test select_borders_density function."""

    def test_selects_borders_within_budget(self, mock_universe: UniverseGraph):
        """Selects borders within jump budget."""
        from aria_esi.mcp.utils import DistanceMatrix

        # Candidates: (vertex_idx, distance_from_origin)
        candidates = [(2, 1), (7, 3), (9, 4)]  # Maurasi, Uedama, Aufay
        origin = 0

        all_waypoints = [origin] + [c[0] for c in candidates]
        matrix = DistanceMatrix.compute(mock_universe, all_waypoints, security_filter="highsec")

        selected = select_borders_density(origin, candidates, matrix, target_jumps=20, min_borders=2)

        assert len(selected) >= 2
        # Should select at least the closest ones
        assert (2, 1) in selected  # Maurasi is closest

    def test_respects_minimum_borders(self, mock_universe: UniverseGraph):
        """Respects minimum borders even if over budget."""
        from aria_esi.mcp.utils import DistanceMatrix

        candidates = [(2, 1), (7, 3), (9, 4)]
        origin = 0

        all_waypoints = [origin] + [c[0] for c in candidates]
        matrix = DistanceMatrix.compute(mock_universe, all_waypoints, security_filter="highsec")

        # Very small budget but min_borders=2
        selected = select_borders_density(origin, candidates, matrix, target_jumps=5, min_borders=2)

        assert len(selected) >= 2

    def test_empty_candidates_returns_empty(self, mock_universe: UniverseGraph):
        """Empty candidates returns empty list."""
        from aria_esi.mcp.utils import DistanceMatrix

        matrix = DistanceMatrix.compute(mock_universe, [0], security_filter="highsec")
        selected = select_borders_density(0, [], matrix, target_jumps=20, min_borders=2)

        assert selected == []


class TestSelectBordersCoverage:
    """Test select_borders_coverage function."""

    def test_selects_diverse_borders(self, mock_universe: UniverseGraph):
        """Selects spatially diverse borders."""
        from aria_esi.mcp.utils import DistanceMatrix

        candidates = [(2, 1), (7, 3), (9, 4)]  # Maurasi, Uedama, Aufay
        origin = 0

        all_waypoints = [origin] + [c[0] for c in candidates]
        matrix = DistanceMatrix.compute(mock_universe, all_waypoints, security_filter="highsec")

        selected = select_borders_coverage(candidates, matrix)

        # Should select all since they're diverse enough
        assert len(selected) >= 1
        # First selected should be closest to origin
        assert selected[0] == candidates[0]

    def test_empty_candidates_returns_empty(self, mock_universe: UniverseGraph):
        """Empty candidates returns empty list."""
        from aria_esi.mcp.utils import DistanceMatrix

        matrix = DistanceMatrix.compute(mock_universe, [0], security_filter="highsec")
        selected = select_borders_coverage([], matrix)

        assert selected == []


class TestNearestNeighborTsp:
    """Test nearest_neighbor_tsp function."""

    def test_produces_valid_tour(self, mock_universe: UniverseGraph):
        """Produces tour visiting all waypoints."""
        from aria_esi.mcp.utils import DistanceMatrix

        origin = 0
        waypoints = [2, 7, 9]

        all_wp = [origin] + waypoints
        matrix = DistanceMatrix.compute(mock_universe, all_wp, security_filter="highsec")

        tour = nearest_neighbor_tsp(origin, waypoints, matrix)

        # Tour should start at origin
        assert tour[0] == origin
        # Tour should visit all waypoints exactly once
        assert set(tour) == set([origin] + waypoints)
        assert len(tour) == len(waypoints) + 1

    def test_empty_waypoints_returns_start_only(self, mock_universe: UniverseGraph):
        """Empty waypoints returns tour with just start."""
        from aria_esi.mcp.utils import DistanceMatrix

        matrix = DistanceMatrix.compute(mock_universe, [0], security_filter="highsec")
        tour = nearest_neighbor_tsp(0, [], matrix)

        assert tour == [0]


class TestExpandTour:
    """Test expand_tour function."""

    def test_expands_tour_to_full_route(self, mock_universe: UniverseGraph):
        """Expands tour to full route with intermediate systems."""
        from aria_esi.mcp.utils import DistanceMatrix

        tour = [0, 2, 7]  # Jita -> Maurasi -> Uedama -> (back to Jita)

        matrix = DistanceMatrix.compute(mock_universe, tour, security_filter="highsec")

        full_route = expand_tour(tour, matrix)

        # Should start and end at origin
        assert full_route[0] == 0
        assert full_route[-1] == 0
        # Should contain all tour waypoints
        for wp in tour:
            assert wp in full_route

    def test_short_tour_returns_valid_loop(self, mock_universe: UniverseGraph):
        """Short tour (single waypoint) returns valid loop."""
        from aria_esi.mcp.utils import DistanceMatrix

        tour = [0]  # Just origin
        matrix = DistanceMatrix.compute(mock_universe, tour, security_filter="highsec")

        full_route = expand_tour(tour, matrix)

        # Should return origin -> origin for short tours
        assert full_route[0] == 0
        assert full_route[-1] == 0
