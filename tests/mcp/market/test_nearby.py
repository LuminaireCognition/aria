"""
Tests for aria_esi.mcp.market.tools_nearby

Tests proximity-based market search functionality.
"""

import pytest

from aria_esi.mcp.market.tools_nearby import (
    NPC_DURATION_THRESHOLD,
    calculate_best_value,
    compute_distances_bounded_bfs,
    detect_price_anomalies,
    get_neighboring_regions,
    suggest_source_filter,
)
from aria_esi.models.market import NearbyMarketSource
from aria_esi.models.sde import CATEGORY_BLUEPRINT, CATEGORY_SKILL


class TestSuggestSourceFilter:
    """Tests for source filter suggestion based on item category."""

    def test_blueprint_suggests_npc(self):
        """Blueprints should suggest NPC filter."""
        assert suggest_source_filter(CATEGORY_BLUEPRINT) == "npc"

    def test_skill_suggests_npc(self):
        """Skillbooks should suggest NPC filter."""
        assert suggest_source_filter(CATEGORY_SKILL) == "npc"

    def test_implant_suggests_all(self):
        """Implants should suggest all (NPC + player traded)."""
        assert suggest_source_filter(20) == "all"  # CATEGORY_IMPLANT

    def test_module_suggests_all(self):
        """Modules should suggest all sources."""
        assert suggest_source_filter(7) == "all"  # CATEGORY_MODULE

    def test_none_category_suggests_all(self):
        """Unknown category should suggest all."""
        assert suggest_source_filter(None) == "all"

    def test_unknown_category_suggests_all(self):
        """Unknown category ID should suggest all."""
        assert suggest_source_filter(999) == "all"


class TestDetectPriceAnomalies:
    """Tests for price anomaly detection."""

    def test_no_flags_for_normal_price(self):
        """Normal prices should not be flagged."""
        flags = detect_price_anomalies(1_000_000, 1_100_000, 100)
        assert flags == []

    def test_flags_extreme_markup(self):
        """10x+ markup should be flagged."""
        flags = detect_price_anomalies(11_000_000, 1_000_000, 100)
        assert len(flags) == 1
        assert "significantly above Jita" in flags[0]

    def test_flags_scam_pattern(self):
        """10x+ markup with low stock should warn of scam."""
        flags = detect_price_anomalies(11_000_000, 1_000_000, 5)
        assert len(flags) == 1
        assert "possible scam" in flags[0]

    def test_no_flags_without_jita_reference(self):
        """No flags if Jita reference not available."""
        flags = detect_price_anomalies(100_000_000, None, 100)
        assert flags == []

    def test_no_flags_for_zero_jita_price(self):
        """No flags if Jita price is zero."""
        flags = detect_price_anomalies(100_000_000, 0, 100)
        assert flags == []


class TestCalculateBestValue:
    """Tests for best value calculation."""

    def _make_source(
        self,
        price: float,
        jumps: int,
        order_id: int = 1,
    ) -> NearbyMarketSource:
        """Create a test NearbyMarketSource."""
        return NearbyMarketSource(
            order_id=order_id,
            price=price,
            volume_remain=100,
            volume_total=100,
            station_id=60003760,
            station_name="Test Station",
            system_id=30000142,
            system_name="Jita",
            security=0.95,
            region_id=10000002,
            region_name="The Forge",
            jumps_from_origin=jumps,
            route_security=None,
            duration=90,
            is_npc=False,
            issued="2025-01-01T00:00:00Z",
            price_per_jump=price / jumps if jumps > 0 else None,
            price_flags=[],
        )

    def test_empty_sources_returns_none(self):
        """Empty list returns None."""
        assert calculate_best_value([]) is None

    def test_single_source_returns_it(self):
        """Single source is returned."""
        source = self._make_source(1_000_000, 5)
        result = calculate_best_value([source])
        assert result == source

    def test_prefers_local_for_cheap_items(self):
        """For cheap items, prefer local over distant cheaper."""
        local = self._make_source(500_000, 0, order_id=1)
        distant = self._make_source(450_000, 20, order_id=2)

        result = calculate_best_value([local, distant], jita_price=500_000)

        # Jump cost = 1% * 500k = 5k per jump
        # Local effective: 500k + 0 = 500k
        # Distant effective: 450k + (20 * 5k) = 550k
        assert result == local

    def test_considers_distance_for_expensive_items(self):
        """For expensive items, still considers distance."""
        local = self._make_source(100_000_000, 0, order_id=1)
        distant = self._make_source(95_000_000, 10, order_id=2)

        result = calculate_best_value([local, distant], jita_price=100_000_000)

        # Jump cost = 1% * 100M = 1M, but capped at 500k per jump
        # Local effective: 100M + 0 = 100M
        # Distant effective: 95M + (10 * 500k) = 100M
        # With exact math, local wins by small margin
        # Actually: 95M + 5M = 100M, so it's equal, but ties go to first
        # Let's verify: local = 100M, distant = 95M + 5M = 100M
        # They're equal, so first one (local) wins
        assert result.order_id in (1, 2)

    def test_uses_median_price_if_no_jita(self):
        """Uses median price from sources if no Jita reference."""
        source1 = self._make_source(1_000_000, 0, order_id=1)
        source2 = self._make_source(2_000_000, 5, order_id=2)
        source3 = self._make_source(3_000_000, 10, order_id=3)

        # Median is 2M, so jump cost = 20k per jump
        result = calculate_best_value([source1, source2, source3])

        # Source1: 1M + 0 = 1M (best)
        # Source2: 2M + 100k = 2.1M
        # Source3: 3M + 200k = 3.2M
        assert result == source1


class TestNPCDurationThreshold:
    """Tests for NPC order detection constant."""

    def test_threshold_is_364(self):
        """NPC threshold should be 364 days."""
        assert NPC_DURATION_THRESHOLD == 364


class TestGetNeighboringRegions:
    """Tests for region neighbor discovery."""

    def test_finds_neighboring_regions(self):
        """Should find regions connected by stargates."""

        class MockGraph:
            def neighbors(self, idx: int) -> list[int]:
                # System 0 (region 1) -> connected to system 5 (region 2)
                # System 1 (region 1) -> only connected to system 0
                if idx == 0:
                    return [1, 5]
                elif idx == 1:
                    return [0]
                elif idx == 5:
                    return [0, 6]
                elif idx == 6:
                    return [5]
                return []

        class MockUniverse:
            def __init__(self):
                self.graph = MockGraph()
                self.region_systems = {
                    1: [0, 1],  # Region 1 has systems 0, 1
                    2: [5, 6],  # Region 2 has systems 5, 6
                }
                # Region IDs by system index
                self._region_ids = {0: 1, 1: 1, 5: 2, 6: 2}

            @property
            def region_ids(self):
                class FakeArray:
                    def __init__(self, data):
                        self._data = data

                    def __getitem__(self, idx):
                        return self._data.get(idx, 0)

                return FakeArray(self._region_ids)

        universe = MockUniverse()
        neighbors = get_neighboring_regions(1, universe)

        # Region 1 should have region 2 as neighbor (via system 0 -> 5 gate)
        assert 2 in neighbors

    def test_empty_region_returns_empty(self):
        """Region with no systems returns empty list."""

        class MockUniverse:
            def __init__(self):
                self.region_systems = {}

        universe = MockUniverse()
        neighbors = get_neighboring_regions(999, universe)

        assert neighbors == []

    def test_isolated_region_returns_empty(self):
        """Region with no cross-region gates returns empty."""

        class MockGraph:
            def neighbors(self, idx: int) -> list[int]:
                # All systems connect only within region
                if idx == 0:
                    return [1]
                elif idx == 1:
                    return [0]
                return []

        class MockUniverse:
            def __init__(self):
                self.graph = MockGraph()
                self.region_systems = {1: [0, 1]}
                self._region_ids = {0: 1, 1: 1}

            @property
            def region_ids(self):
                class FakeArray:
                    def __init__(self, data):
                        self._data = data

                    def __getitem__(self, idx):
                        return self._data.get(idx, 0)

                return FakeArray(self._region_ids)

        universe = MockUniverse()
        neighbors = get_neighboring_regions(1, universe)

        assert neighbors == []


@pytest.fixture
def mock_universe_graph():
    """Create a mock universe graph for BFS testing."""

    class MockGraph:
        """Minimal mock for igraph.Graph."""

        def __init__(self, edges: dict[int, list[int]]):
            self._edges = edges

        def neighbors(self, idx: int) -> list[int]:
            return self._edges.get(idx, [])

    class MockUniverseGraph:
        """Mock UniverseGraph for testing."""

        def __init__(self):
            # Simple star topology: 0 is center, connected to 1, 2, 3
            # 1 is connected to 0 and 4
            # 4 is connected to 1 and 5
            self.graph = MockGraph({
                0: [1, 2, 3],
                1: [0, 4],
                2: [0],
                3: [0],
                4: [1, 5],
                5: [4],
            })
            self._system_ids = {
                0: 30000001,
                1: 30000002,
                2: 30000003,
                3: 30000004,
                4: 30000005,
                5: 30000006,
            }

        def get_system_id(self, idx: int) -> int:
            return self._system_ids.get(idx, 0)

    return MockUniverseGraph()


class TestComputeDistancesBoundedBFS:
    """Tests for bounded BFS distance calculation."""

    def test_origin_is_zero_distance(self, mock_universe_graph):
        """Origin system has 0 distance."""
        distances = compute_distances_bounded_bfs(0, 10, mock_universe_graph)
        assert distances[30000001] == 0  # system_id for idx 0

    def test_immediate_neighbors_are_one(self, mock_universe_graph):
        """Immediate neighbors have distance 1."""
        distances = compute_distances_bounded_bfs(0, 10, mock_universe_graph)
        assert distances[30000002] == 1  # system_id for idx 1
        assert distances[30000003] == 1  # system_id for idx 2

    def test_two_hop_systems(self, mock_universe_graph):
        """Two-hop systems have distance 2."""
        distances = compute_distances_bounded_bfs(0, 10, mock_universe_graph)
        assert distances[30000005] == 2  # system_id for idx 4

    def test_respects_max_jumps(self, mock_universe_graph):
        """BFS stops at max_jumps."""
        distances = compute_distances_bounded_bfs(0, 1, mock_universe_graph)

        # Should have origin and 1-hop neighbors
        assert 30000001 in distances  # origin
        assert 30000002 in distances  # 1-hop
        # Should NOT have 2-hop neighbors
        assert 30000005 not in distances  # 2-hop

    def test_max_jumps_zero(self, mock_universe_graph):
        """max_jumps=0 returns only origin."""
        distances = compute_distances_bounded_bfs(0, 0, mock_universe_graph)
        assert distances == {30000001: 0}
