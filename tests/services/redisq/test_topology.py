"""
Unit tests for the Operational Topology module.

Tests InterestMap, TopologyBuilder, and TopologyFilter.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from aria_esi.services.redisq.models import QueuedKill
from aria_esi.services.redisq.notifications.config import TopologyConfig
from aria_esi.services.redisq.topology import (
    InterestMap,
    SystemInterest,
    TopologyBuilder,
    TopologyFilter,
)

# =============================================================================
# TopologyConfig Tests
# =============================================================================


class TestTopologyConfig:
    """Tests for TopologyConfig dataclass."""

    def test_default_config(self):
        """Default config should have topology disabled."""
        config = TopologyConfig()
        assert config.enabled is False
        assert config.operational_systems == []
        assert config.interest_weights == {
            "operational": 1.0,
            "hop_1": 1.0,
            "hop_2": 0.7,
        }

    def test_from_dict_basic(self):
        """Should parse basic configuration."""
        data = {
            "enabled": True,
            "operational_systems": ["Simela", "Masalle"],
            "interest_weights": {
                "operational": 1.0,
                "hop_1": 0.9,
                "hop_2": 0.5,
            },
        }
        config = TopologyConfig.from_dict(data)
        assert config.enabled is True
        assert config.operational_systems == ["Simela", "Masalle"]
        assert config.interest_weights["hop_2"] == 0.5

    def test_from_dict_none(self):
        """Should return default for None input."""
        config = TopologyConfig.from_dict(None)
        assert config.enabled is False

    def test_validate_empty_systems_when_enabled(self):
        """Should error if enabled but no systems."""
        config = TopologyConfig(enabled=True, operational_systems=[])
        errors = config.validate()
        assert len(errors) == 1
        assert "operational_systems must be non-empty" in errors[0]

    def test_validate_invalid_weight_key(self):
        """Should error on unknown weight keys."""
        config = TopologyConfig(
            enabled=True,
            operational_systems=["Jita"],
            interest_weights={"invalid_key": 0.5},
        )
        errors = config.validate()
        assert any("Unknown interest weight key" in e for e in errors)

    def test_validate_weight_out_of_range(self):
        """Should error if weight is out of range."""
        config = TopologyConfig(
            enabled=True,
            operational_systems=["Jita"],
            interest_weights={"operational": 1.5},  # > 1.0
        )
        errors = config.validate()
        assert any("must be between 0 and 1" in e for e in errors)


# =============================================================================
# InterestMap Tests
# =============================================================================


class TestInterestMap:
    """Tests for InterestMap class."""

    def test_empty_map(self):
        """Empty map should return 0 interest for any system."""
        interest_map = InterestMap()
        assert interest_map.get_interest(30000142) == 0.0  # Jita
        assert interest_map.is_interesting(30000142) is False
        assert interest_map.total_systems == 0

    def test_get_interest(self):
        """Should return correct interest for tracked systems."""
        interest_map = InterestMap(
            systems={
                30000142: SystemInterest(
                    system_id=30000142,
                    system_name="Jita",
                    interest=1.0,
                    hop_level=0,
                ),
                30000143: SystemInterest(
                    system_id=30000143,
                    system_name="Perimeter",
                    interest=0.7,
                    hop_level=1,
                ),
            }
        )
        assert interest_map.get_interest(30000142) == 1.0
        assert interest_map.get_interest(30000143) == 0.7
        assert interest_map.get_interest(99999999) == 0.0

    def test_is_interesting(self):
        """Should correctly identify tracked systems."""
        interest_map = InterestMap(
            systems={
                30000142: SystemInterest(
                    system_id=30000142,
                    system_name="Jita",
                    interest=1.0,
                    hop_level=0,
                ),
            }
        )
        assert interest_map.is_interesting(30000142) is True
        assert interest_map.is_interesting(99999999) is False

    def test_get_systems_by_hop(self):
        """Should filter systems by hop level."""
        interest_map = InterestMap(
            systems={
                1: SystemInterest(1, "Op1", 1.0, 0),
                2: SystemInterest(2, "Hop1a", 1.0, 1),
                3: SystemInterest(3, "Hop1b", 1.0, 1),
                4: SystemInterest(4, "Hop2a", 0.7, 2),
            }
        )
        hop_0 = interest_map.get_systems_by_hop(0)
        hop_1 = interest_map.get_systems_by_hop(1)
        hop_2 = interest_map.get_systems_by_hop(2)

        assert len(hop_0) == 1
        assert len(hop_1) == 2
        assert len(hop_2) == 1
        assert hop_0[0].system_name == "Op1"

    def test_get_special_systems(self):
        """Should categorize special systems."""
        interest_map = InterestMap(
            systems={
                1: SystemInterest(1, "Normal", 1.0, 0),
                2: SystemInterest(2, "Border", 1.0, 1, is_border=True),
                3: SystemInterest(3, "Uedama", 0.7, 2, is_gank_pipe=True),
                4: SystemInterest(4, "Jita", 0.7, 2, is_trade_hub=True),
            }
        )
        special = interest_map.get_special_systems()
        assert "Border" in special["border_systems"]
        assert "Uedama" in special["gank_pipes"]
        assert "Jita" in special["trade_hubs"]

    def test_serialization_roundtrip(self):
        """Should serialize and deserialize correctly."""
        original = InterestMap(
            systems={
                30000142: SystemInterest(
                    system_id=30000142,
                    system_name="Jita",
                    interest=1.0,
                    hop_level=0,
                    is_trade_hub=True,
                ),
            },
            operational_systems=["Jita"],
            interest_weights={"operational": 1.0, "hop_1": 0.9, "hop_2": 0.5},
            built_at=1234567890.0,
            routes={"Jita -> Amarr": ["Jita", "Perimeter", "Amarr"]},
        )

        # Serialize
        data = original.to_dict()

        # Deserialize
        restored = InterestMap.from_dict(data)

        assert restored.total_systems == original.total_systems
        assert restored.get_interest(30000142) == 1.0
        assert restored.operational_systems == ["Jita"]
        assert restored.interest_weights["hop_2"] == 0.5
        assert restored.built_at == 1234567890.0
        assert "Jita -> Amarr" in restored.routes

    def test_save_and_load(self, tmp_path):
        """Should save to and load from file."""
        cache_path = tmp_path / "topology_map.json"

        original = InterestMap(
            systems={
                123: SystemInterest(123, "TestSystem", 0.8, 1),
            },
            operational_systems=["TestBase"],
            built_at=1000000.0,
        )

        original.save(cache_path)
        assert cache_path.exists()

        loaded = InterestMap.load(cache_path)
        assert loaded is not None
        assert loaded.total_systems == 1
        assert loaded.get_interest(123) == 0.8

    def test_load_missing_file(self, tmp_path):
        """Should return None for missing file."""
        result = InterestMap.load(tmp_path / "nonexistent.json")
        assert result is None

    def test_load_corrupt_file(self, tmp_path):
        """Should return None for corrupt file."""
        corrupt_path = tmp_path / "corrupt.json"
        corrupt_path.write_text("not valid json {{{")

        result = InterestMap.load(corrupt_path)
        assert result is None


# =============================================================================
# TopologyBuilder Tests
# =============================================================================


class TestTopologyBuilder:
    """Tests for TopologyBuilder class."""

    @pytest.fixture
    def mock_graph(self):
        """Create a mock UniverseGraph for testing."""
        graph = MagicMock()

        # System data: idx -> (id, name, security)
        systems = {
            0: (30000001, "SystemA", 0.9),  # Operational
            1: (30000002, "SystemB", 0.7),  # 1-hop from A
            2: (30000003, "SystemC", 0.8),  # 1-hop from A
            3: (30000004, "SystemD", 0.5),  # 2-hop from A (via B)
            4: (30000005, "SystemE", 0.3),  # 2-hop from A (via C), border
        }

        # Neighbor relationships
        neighbors = {
            0: [1, 2],  # A connects to B, C
            1: [0, 3],  # B connects to A, D
            2: [0, 4],  # C connects to A, E
            3: [1],  # D connects to B
            4: [2],  # E connects to C
        }

        graph.resolve_name = MagicMock(
            side_effect=lambda name: {"SystemA": 0, "SystemB": 1}.get(name)
        )
        graph.get_system_id = MagicMock(side_effect=lambda idx: systems[idx][0])
        graph.idx_to_name = {i: s[1] for i, s in systems.items()}
        graph.is_border_system = MagicMock(side_effect=lambda idx: idx == 4)
        graph.graph = MagicMock()
        graph.graph.neighbors = MagicMock(side_effect=lambda idx: neighbors.get(idx, []))
        graph.graph.get_shortest_paths = MagicMock(return_value=[[0, 1]])

        return graph

    def test_build_basic(self, mock_graph):
        """Should build topology with correct hop levels."""
        builder = TopologyBuilder(mock_graph)
        interest_map = builder.build(["SystemA"])

        # SystemA is operational (hop 0)
        assert interest_map.get_interest(30000001) == 1.0
        info_a = interest_map.get_system_info(30000001)
        assert info_a is not None
        assert info_a.hop_level == 0

        # SystemB, SystemC are 1-hop
        assert interest_map.get_interest(30000002) == 1.0
        assert interest_map.get_interest(30000003) == 1.0
        info_b = interest_map.get_system_info(30000002)
        assert info_b is not None
        assert info_b.hop_level == 1

        # SystemD, SystemE are 2-hop
        assert interest_map.get_interest(30000004) == 0.7
        assert interest_map.get_interest(30000005) == 0.7

    def test_build_with_custom_weights(self, mock_graph):
        """Should use custom interest weights."""
        builder = TopologyBuilder(mock_graph)
        weights = {"operational": 1.0, "hop_1": 0.5, "hop_2": 0.2}
        interest_map = builder.build(["SystemA"], weights)

        assert interest_map.get_interest(30000001) == 1.0  # operational
        assert interest_map.get_interest(30000002) == 0.5  # hop 1
        assert interest_map.get_interest(30000004) == 0.2  # hop 2

    def test_build_marks_border_systems(self, mock_graph):
        """Should mark border systems correctly."""
        builder = TopologyBuilder(mock_graph)
        interest_map = builder.build(["SystemA"])

        info_e = interest_map.get_system_info(30000005)
        assert info_e is not None
        assert info_e.is_border is True

    def test_build_unknown_system(self, mock_graph):
        """Should handle unknown system names gracefully."""
        mock_graph.resolve_name = MagicMock(return_value=None)
        builder = TopologyBuilder(mock_graph)
        interest_map = builder.build(["UnknownSystem"])

        assert interest_map.total_systems == 0

    def test_gank_pipe_detection(self, mock_graph):
        """Should detect known gank pipe systems."""
        # Override to return Uedama
        systems = {
            0: (30002187, "Uedama", 0.5),
            1: (30002188, "Neighbor", 0.6),
        }
        neighbors = {0: [1], 1: [0]}

        mock_graph.resolve_name = MagicMock(side_effect=lambda name: {"Uedama": 0}.get(name))
        mock_graph.get_system_id = MagicMock(side_effect=lambda idx: systems[idx][0])
        mock_graph.idx_to_name = {i: s[1] for i, s in systems.items()}
        mock_graph.graph.neighbors = MagicMock(side_effect=lambda idx: neighbors.get(idx, []))
        mock_graph.is_border_system = MagicMock(return_value=False)

        builder = TopologyBuilder(mock_graph)
        interest_map = builder.build(["Uedama"])

        info = interest_map.get_system_info(30002187)
        assert info is not None
        assert info.is_gank_pipe is True


# =============================================================================
# TopologyFilter Tests
# =============================================================================


class TestTopologyFilter:
    """Tests for TopologyFilter class."""

    def test_inactive_filter_passes_all(self):
        """Inactive filter should pass all kills."""
        filter = TopologyFilter()
        assert filter.is_active is False

        kill = QueuedKill(
            kill_id=123,
            hash="abc",
            zkb_data={},
            queued_at=1000.0,
            solar_system_id=99999,
        )
        assert filter.should_fetch(kill) is True

    def test_active_filter_passes_interesting(self):
        """Active filter should pass kills in topology."""
        interest_map = InterestMap(
            systems={
                30000142: SystemInterest(30000142, "Jita", 1.0, 0),
            }
        )
        filter = TopologyFilter(interest_map=interest_map)
        assert filter.is_active is True

        kill = QueuedKill(
            kill_id=123,
            hash="abc",
            zkb_data={},
            queued_at=1000.0,
            solar_system_id=30000142,
        )
        assert filter.should_fetch(kill) is True

    def test_active_filter_blocks_uninteresting(self):
        """Active filter should block kills outside topology."""
        interest_map = InterestMap(
            systems={
                30000142: SystemInterest(30000142, "Jita", 1.0, 0),
            }
        )
        filter = TopologyFilter(interest_map=interest_map)

        kill = QueuedKill(
            kill_id=123,
            hash="abc",
            zkb_data={},
            queued_at=1000.0,
            solar_system_id=99999999,  # Not in topology
        )
        assert filter.should_fetch(kill) is False

    def test_filter_passes_when_system_id_missing(self):
        """Filter should pass kills without system_id (conservative)."""
        interest_map = InterestMap(
            systems={
                30000142: SystemInterest(30000142, "Jita", 1.0, 0),
            }
        )
        filter = TopologyFilter(interest_map=interest_map)

        kill = QueuedKill(
            kill_id=123,
            hash="abc",
            zkb_data={},
            queued_at=1000.0,
            solar_system_id=None,
        )
        assert filter.should_fetch(kill) is True

    def test_metrics_tracking(self):
        """Filter should track pass/filter metrics."""
        interest_map = InterestMap(
            systems={
                30000142: SystemInterest(30000142, "Jita", 1.0, 0),
            }
        )
        filter = TopologyFilter(interest_map=interest_map)

        # Pass one
        kill1 = QueuedKill(123, "a", {}, 1000.0, solar_system_id=30000142)
        filter.should_fetch(kill1)

        # Filter one
        kill2 = QueuedKill(124, "b", {}, 1001.0, solar_system_id=99999)
        filter.should_fetch(kill2)

        metrics = filter.get_metrics()
        assert metrics["passed"] == 1
        assert metrics["filtered"] == 1
        assert metrics["total"] == 2

    def test_reset_metrics(self):
        """Should reset metrics to zero."""
        interest_map = InterestMap(
            systems={
                30000142: SystemInterest(30000142, "Jita", 1.0, 0),
            }
        )
        filter = TopologyFilter(interest_map=interest_map)

        kill = QueuedKill(123, "a", {}, 1000.0, solar_system_id=30000142)
        filter.should_fetch(kill)

        filter.reset_metrics()
        metrics = filter.get_metrics()
        assert metrics["passed"] == 0
        assert metrics["filtered"] == 0


# =============================================================================
# QueuedKill solar_system_id Tests
# =============================================================================


class TestQueuedKillSolarSystemId:
    """Tests for solar_system_id extraction in QueuedKill."""

    def test_from_redisq_package_with_solar_system(self):
        """Should extract solar_system_id from package."""
        package = {
            "killID": 123456,
            "killmail": {
                "killmail_id": 123456,
                "solar_system_id": 30000142,
            },
            "zkb": {
                "hash": "abc123",
            },
        }
        kill = QueuedKill.from_redisq_package(package, 1000.0)
        assert kill.kill_id == 123456
        assert kill.solar_system_id == 30000142

    def test_from_redisq_package_without_solar_system(self):
        """Should handle missing solar_system_id."""
        package = {
            "killID": 123456,
            "zkb": {
                "hash": "abc123",
            },
        }
        kill = QueuedKill.from_redisq_package(package, 1000.0)
        assert kill.kill_id == 123456
        assert kill.solar_system_id is None

    def test_from_redisq_package_old_format(self):
        """Should handle old format with nested killmail."""
        package = {
            "killmail": {
                "killmail_id": 123456,
                "solar_system_id": 30000142,
            },
            "zkb": {
                "hash": "abc123",
            },
        }
        kill = QueuedKill.from_redisq_package(package, 1000.0)
        assert kill.kill_id == 123456
        assert kill.solar_system_id == 30000142
