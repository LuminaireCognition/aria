"""
Tests for Loop Planning Service.

Integration tests for the LoopPlanningService class.
"""

from __future__ import annotations

import igraph as ig
import numpy as np
import pytest

from aria_esi.services.loop_planning import (
    InsufficientBordersError,
    LoopPlanningService,
    LoopSummary,
)
from aria_esi.universe import UniverseGraph


@pytest.fixture
def mock_universe() -> UniverseGraph:
    """Create a mock universe for testing loop planning service."""
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


class TestLoopPlanningService:
    """Test LoopPlanningService class."""

    def test_plan_loop_returns_summary(self, mock_universe: UniverseGraph):
        """plan_loop returns a LoopSummary."""
        service = LoopPlanningService(mock_universe)
        summary = service.plan_loop(
            origin_idx=0,
            target_jumps=20,
            min_borders=2,
            max_borders=3,
        )

        assert isinstance(summary, LoopSummary)
        assert summary.total_jumps > 0
        assert summary.unique_systems > 0
        assert len(summary.borders_visited) >= 2
        assert len(summary.borders_visited) <= 3

    def test_plan_loop_starts_and_ends_at_origin(self, mock_universe: UniverseGraph):
        """Loop starts and ends at origin."""
        service = LoopPlanningService(mock_universe)
        summary = service.plan_loop(
            origin_idx=0,
            target_jumps=20,
            min_borders=2,
        )

        assert summary.full_route[0] == 0
        assert summary.full_route[-1] == 0

    def test_plan_loop_density_mode(self, mock_universe: UniverseGraph):
        """Density mode works correctly."""
        service = LoopPlanningService(mock_universe)
        summary = service.plan_loop(
            origin_idx=0,
            target_jumps=20,
            min_borders=2,
            optimize="density",
        )

        assert len(summary.borders_visited) >= 2

    def test_plan_loop_coverage_mode(self, mock_universe: UniverseGraph):
        """Coverage mode works correctly."""
        service = LoopPlanningService(mock_universe)
        summary = service.plan_loop(
            origin_idx=0,
            target_jumps=20,
            min_borders=2,
            optimize="coverage",
        )

        assert len(summary.borders_visited) >= 2

    def test_plan_loop_insufficient_borders_raises(self, mock_universe: UniverseGraph):
        """Raises InsufficientBordersError when not enough borders."""
        service = LoopPlanningService(mock_universe)

        with pytest.raises(InsufficientBordersError) as exc_info:
            service.plan_loop(
                origin_idx=0,
                target_jumps=10,  # Small radius
                min_borders=10,  # Too many required
            )

        assert exc_info.value.required == 10
        assert exc_info.value.found < 10

    def test_plan_loop_with_avoid_systems(self, mock_universe: UniverseGraph):
        """Respects avoid_systems parameter."""
        service = LoopPlanningService(mock_universe)

        # Avoid Maurasi (idx 2)
        summary = service.plan_loop(
            origin_idx=0,
            target_jumps=20,
            min_borders=2,
            avoid_systems={2},
        )

        # Maurasi should not be in the route
        assert 2 not in summary.full_route

    def test_find_borders(self, mock_universe: UniverseGraph):
        """find_borders returns border systems."""
        service = LoopPlanningService(mock_universe)
        borders = service.find_borders(
            origin_idx=0,
            limit=10,
            max_jumps=10,
        )

        assert len(borders) > 0
        # All returned should be border systems
        for idx, _ in borders:
            assert idx in mock_universe.border_systems

    def test_resolve_avoid_systems(self, mock_universe: UniverseGraph):
        """resolve_avoid_systems resolves names to indices."""
        service = LoopPlanningService(mock_universe)
        indices, unresolved = service.resolve_avoid_systems(["Jita", "Unknown"])

        assert 0 in indices  # Jita resolved to idx 0
        assert "Unknown" in unresolved


class TestLoopSummary:
    """Test LoopSummary dataclass."""

    def test_summary_attributes(self, mock_universe: UniverseGraph):
        """Summary has correct attributes."""
        from aria_esi.services.loop_planning import compute_loop_summary

        full_route = [0, 2, 0]  # Jita -> Maurasi -> Jita
        borders_visited = [(2, 1)]  # Maurasi at 1 jump

        summary = compute_loop_summary(full_route, borders_visited)

        assert summary.full_route == full_route
        assert summary.borders_visited == borders_visited
        assert summary.total_jumps == 2  # 3 systems = 2 jumps
        assert summary.unique_systems == 2  # Jita appears twice
        assert summary.backtrack_jumps >= 0
        assert 0.0 <= summary.efficiency <= 1.0

    def test_summary_efficiency_calculation(self, mock_universe: UniverseGraph):
        """Efficiency is calculated correctly."""
        from aria_esi.services.loop_planning import compute_loop_summary

        # 2 unique out of 3 total
        full_route = [0, 2, 0]
        summary = compute_loop_summary(full_route, [])

        expected_efficiency = 2 / 3
        assert abs(summary.efficiency - expected_efficiency) < 0.01


class TestLoopPlanningServicePerformance:
    """Performance tests for loop planning service."""

    def test_plan_loop_latency(self, mock_universe: UniverseGraph):
        """Loop planning completes within latency budget."""
        import time

        service = LoopPlanningService(mock_universe)

        start = time.perf_counter()
        for _ in range(10):
            service.plan_loop(
                origin_idx=0,
                target_jumps=20,
                min_borders=2,
                max_borders=3,
            )
        elapsed = time.perf_counter() - start

        avg_time = elapsed / 10
        # Should be well under 20ms budget
        assert avg_time < 0.020


@pytest.fixture
def mock_universe_many_borders() -> UniverseGraph:
    """Create a mock universe with 10 border systems for edge case testing."""
    # Hub-and-spoke topology: origin (0) connected to 10 highsec borders (1-10),
    # each border connected to a lowsec system (11-20)
    edges = []
    # Connect origin to all borders
    for i in range(1, 11):
        edges.append((0, i))
    # Connect each border to its lowsec neighbor
    for i in range(1, 11):
        edges.append((i, i + 10))
    # Add some inter-border connections for routing variety
    for i in range(1, 10):
        edges.append((i, i + 1))

    g = ig.Graph(n=21, edges=edges, directed=False)

    systems = [{"name": "Origin", "id": 30000000, "sec": 0.95, "const": 20000001, "region": 10000001}]
    # 10 border systems (highsec adjacent to lowsec)
    for i in range(1, 11):
        systems.append({
            "name": f"Border{i}",
            "id": 30000000 + i,
            "sec": 0.50,
            "const": 20000001,
            "region": 10000001,
        })
    # 10 lowsec systems
    for i in range(11, 21):
        systems.append({
            "name": f"Lowsec{i - 10}",
            "id": 30000000 + i,
            "sec": 0.30,
            "const": 20000002,
            "region": 10000001,
        })

    name_to_idx = {s["name"]: i for i, s in enumerate(systems)}
    idx_to_name = {i: s["name"] for i, s in enumerate(systems)}
    name_to_id = {s["name"]: s["id"] for s in systems}
    id_to_idx = {s["id"]: i for i, s in enumerate(systems)}
    name_lookup = {s["name"].lower(): s["name"] for s in systems}

    security = np.array([s["sec"] for s in systems], dtype=np.float32)
    system_ids = np.array([s["id"] for s in systems], dtype=np.int32)
    constellation_ids = np.array([s["const"] for s in systems], dtype=np.int32)
    region_ids = np.array([s["region"] for s in systems], dtype=np.int32)

    highsec = frozenset(i for i in range(21) if security[i] >= 0.45)
    lowsec = frozenset(i for i in range(21) if 0.0 < security[i] < 0.45)
    nullsec = frozenset()
    border = frozenset(range(1, 11))  # All 10 border systems

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
        constellation_names={20000001: "TestConst", 20000002: "LowConst"},
        region_names={10000001: "TestRegion"},
        region_name_lookup={"testregion": 10000001},
        border_systems=border,
        region_systems={10000001: list(range(21))},
        highsec_systems=highsec,
        lowsec_systems=lowsec,
        nullsec_systems=nullsec,
        version="test-1.0",
        system_count=21,
        stargate_count=len(edges),
    )


class TestLoopPlanningEdgeCases:
    """Edge case tests for loop planning service."""

    def test_coverage_mode_respects_min_borders_above_default_cap(
        self, mock_universe_many_borders: UniverseGraph
    ):
        """Coverage mode returns at least min_borders even when > DEFAULT_COVERAGE_CAP."""
        from aria_esi.services.loop_planning.planner import DEFAULT_COVERAGE_CAP

        service = LoopPlanningService(mock_universe_many_borders)

        # Request more borders than the default cap
        min_borders = DEFAULT_COVERAGE_CAP + 1  # 9 borders
        summary = service.plan_loop(
            origin_idx=0,
            target_jumps=50,
            min_borders=min_borders,
            max_borders=None,  # No explicit cap
            optimize="coverage",
        )

        # Should return at least min_borders, not capped at DEFAULT_COVERAGE_CAP
        assert len(summary.borders_visited) >= min_borders

    def test_density_mode_uncapped_when_max_borders_none(
        self, mock_universe_many_borders: UniverseGraph
    ):
        """Density mode is uncapped when max_borders=None."""
        service = LoopPlanningService(mock_universe_many_borders)

        summary = service.plan_loop(
            origin_idx=0,
            target_jumps=100,  # Large budget to allow many borders
            min_borders=2,
            max_borders=None,  # Uncapped
            optimize="density",
        )

        # With a large budget and uncapped max, density mode should find many borders
        # The mock has 10 borders, all reachable
        assert len(summary.borders_visited) >= 5  # Should find multiple borders

    def test_density_mode_capped_when_max_borders_set(
        self, mock_universe_many_borders: UniverseGraph
    ):
        """Density mode respects explicit max_borders cap."""
        service = LoopPlanningService(mock_universe_many_borders)

        summary = service.plan_loop(
            origin_idx=0,
            target_jumps=100,
            min_borders=2,
            max_borders=3,  # Explicit cap
            optimize="density",
        )

        # Should be capped at max_borders
        assert len(summary.borders_visited) <= 3

    def test_coverage_mode_respects_explicit_max_borders(
        self, mock_universe_many_borders: UniverseGraph
    ):
        """Coverage mode respects explicit max_borders even if min_borders is lower."""
        service = LoopPlanningService(mock_universe_many_borders)

        summary = service.plan_loop(
            origin_idx=0,
            target_jumps=50,
            min_borders=2,
            max_borders=4,  # Explicit cap below DEFAULT_COVERAGE_CAP
            optimize="coverage",
        )

        # Should respect explicit max_borders
        assert len(summary.borders_visited) <= 4
        assert len(summary.borders_visited) >= 2
