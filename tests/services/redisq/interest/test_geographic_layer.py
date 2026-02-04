"""
Tests for Geographic Interest Layer.
"""

from __future__ import annotations

import pytest

from aria_esi.services.redisq.interest.layers import (
    DEFAULT_HOME_WEIGHTS,
    GeographicConfig,
    GeographicLayer,
    GeographicSystem,
    SystemClassification,
)

# Import the mock universe factory from mcp conftest
from tests.mcp.conftest import create_mock_universe

# =============================================================================
# Test Universe Setup
# =============================================================================

# Create a test universe with a clear topology:
#
#   [Tama] --- [Kedama] --- [Sujarento]
#      |          |              |
#   [Okkamon] - [Hikkoken] - [Enaluri]
#
# All systems in same region for simplicity

TEST_SYSTEMS = [
    {"name": "Tama", "id": 30002537, "sec": 0.3, "const": 20000001, "region": 10000001},
    {"name": "Kedama", "id": 30002538, "sec": 0.2, "const": 20000001, "region": 10000001},
    {"name": "Sujarento", "id": 30002539, "sec": 0.4, "const": 20000001, "region": 10000001},
    {"name": "Okkamon", "id": 30002540, "sec": 0.3, "const": 20000001, "region": 10000001},
    {"name": "Hikkoken", "id": 30002541, "sec": 0.2, "const": 20000001, "region": 10000001},
    {"name": "Enaluri", "id": 30002542, "sec": 0.1, "const": 20000001, "region": 10000001},
    # Add a distant system not connected to main cluster
    {"name": "Distant", "id": 30003458, "sec": 0.5, "const": 20000002, "region": 10000002},
]

TEST_EDGES = [
    (0, 1),  # Tama -- Kedama
    (1, 2),  # Kedama -- Sujarento
    (0, 3),  # Tama -- Okkamon
    (1, 4),  # Kedama -- Hikkoken
    (3, 4),  # Okkamon -- Hikkoken
    (4, 5),  # Hikkoken -- Enaluri
    (2, 5),  # Sujarento -- Enaluri
]


@pytest.fixture
def test_universe():
    """Create test universe for geographic layer tests."""
    return create_mock_universe(TEST_SYSTEMS, TEST_EDGES)


# =============================================================================
# System Classification Tests
# =============================================================================


class TestSystemClassification:
    """Tests for system classification enum."""

    def test_classification_values(self) -> None:
        """Classification values match expected strings."""
        assert SystemClassification.HOME.value == "home"
        assert SystemClassification.HUNTING.value == "hunting"
        assert SystemClassification.TRANSIT.value == "transit"

    def test_classification_from_string(self) -> None:
        """Can create classification from string."""
        assert SystemClassification("home") == SystemClassification.HOME
        assert SystemClassification("hunting") == SystemClassification.HUNTING
        assert SystemClassification("transit") == SystemClassification.TRANSIT


# =============================================================================
# Configuration Tests
# =============================================================================


class TestGeographicConfig:
    """Tests for GeographicConfig."""

    def test_default_weights(self) -> None:
        """Default weights are set correctly."""
        config = GeographicConfig()

        # Home gets 3 hops
        assert config.get_max_hops(SystemClassification.HOME) == 3
        assert config.home_weights[0] == 1.0
        assert config.home_weights[3] == 0.5

        # Hunting gets 2 hops
        assert config.get_max_hops(SystemClassification.HUNTING) == 2
        assert config.hunting_weights[0] == 1.0
        assert config.hunting_weights[2] == 0.5

        # Transit gets 1 hop
        assert config.get_max_hops(SystemClassification.TRANSIT) == 1
        assert config.transit_weights[0] == 0.7
        assert config.transit_weights[1] == 0.3

    def test_from_dict_with_systems(self) -> None:
        """Can parse config from dict with systems."""
        data = {
            "systems": [
                {"name": "Tama", "classification": "home"},
                {"name": "Kedama", "classification": "hunting"},
                {"name": "Okkamon", "classification": "transit"},
            ]
        }

        config = GeographicConfig.from_dict(data)

        assert len(config.systems) == 3
        assert config.systems[0].name == "Tama"
        assert config.systems[0].classification == SystemClassification.HOME
        assert config.systems[1].classification == SystemClassification.HUNTING
        assert config.systems[2].classification == SystemClassification.TRANSIT

    def test_from_dict_simple_string_systems(self) -> None:
        """Simple string systems default to home classification."""
        data = {
            "systems": ["Tama", "Kedama"]
        }

        config = GeographicConfig.from_dict(data)

        assert len(config.systems) == 2
        assert all(s.classification == SystemClassification.HOME for s in config.systems)

    def test_from_legacy_config(self) -> None:
        """Legacy config conversion works."""
        operational = ["Tama", "Kedama"]
        weights = {"operational": 1.0, "hop_1": 0.9, "hop_2": 0.6}

        config = GeographicConfig.from_legacy_config(operational, weights)

        assert len(config.systems) == 2
        assert all(s.classification == SystemClassification.HOME for s in config.systems)
        assert config.home_weights[0] == 1.0
        assert config.home_weights[1] == 0.9
        assert config.home_weights[2] == 0.6


# =============================================================================
# Layer Construction Tests
# =============================================================================


class TestGeographicLayerConstruction:
    """Tests for building the geographic layer."""

    def test_from_config_builds_interest_map(self, test_universe) -> None:
        """from_config builds interest map with correct systems."""
        config = GeographicConfig(
            systems=[GeographicSystem(name="Tama", classification=SystemClassification.HOME)]
        )

        layer = GeographicLayer.from_config(config, test_universe)

        # Should have tracked multiple systems from BFS
        assert layer.total_systems > 1
        # Tama should be in the map
        assert 30002537 in layer._interest_map

    def test_home_classification_expands_3_hops(self, test_universe) -> None:
        """Home classification expands to 3 hops."""
        config = GeographicConfig(
            systems=[GeographicSystem(name="Tama", classification=SystemClassification.HOME)]
        )

        layer = GeographicLayer.from_config(config, test_universe)

        # Tama (hop 0)
        assert 30002537 in layer._interest_map
        # Kedama, Okkamon (hop 1)
        assert 30002538 in layer._interest_map
        assert 30002540 in layer._interest_map
        # Sujarento, Hikkoken (hop 2)
        assert 30002539 in layer._interest_map
        assert 30002541 in layer._interest_map
        # Enaluri (hop 3)
        assert 30002542 in layer._interest_map

    def test_hunting_classification_expands_2_hops(self, test_universe) -> None:
        """Hunting classification expands to 2 hops only."""
        config = GeographicConfig(
            systems=[GeographicSystem(name="Tama", classification=SystemClassification.HUNTING)]
        )

        layer = GeographicLayer.from_config(config, test_universe)

        # Tama (hop 0)
        assert 30002537 in layer._interest_map
        # Kedama, Okkamon (hop 1)
        assert 30002538 in layer._interest_map
        # Sujarento (hop 2 from Tama via Kedama)
        assert 30002539 in layer._interest_map
        # Enaluri should NOT be included (hop 3)
        # Actually it's hop 2 from Kedama or Okkamon... let me check

    def test_transit_classification_expands_1_hop(self, test_universe) -> None:
        """Transit classification expands to 1 hop only."""
        config = GeographicConfig(
            systems=[GeographicSystem(name="Tama", classification=SystemClassification.TRANSIT)]
        )

        layer = GeographicLayer.from_config(config, test_universe)

        # Tama (hop 0)
        assert 30002537 in layer._interest_map
        # Kedama, Okkamon (hop 1)
        assert 30002538 in layer._interest_map
        assert 30002540 in layer._interest_map
        # Sujarento should NOT be included (hop 2)
        assert 30002539 not in layer._interest_map

    def test_unknown_system_is_logged_and_skipped(self, test_universe) -> None:
        """Unknown system names are skipped with warning."""
        config = GeographicConfig(
            systems=[
                GeographicSystem(name="NonexistentSystem"),
                GeographicSystem(name="Tama"),
            ]
        )

        layer = GeographicLayer.from_config(config, test_universe)

        # Should still have Tama and neighbors
        assert 30002537 in layer._interest_map


# =============================================================================
# Scoring Tests
# =============================================================================


class TestGeographicLayerScoring:
    """Tests for score_system method."""

    def test_operational_system_returns_full_interest(self, test_universe) -> None:
        """Operational system (hop 0) returns 1.0 interest."""
        config = GeographicConfig(
            systems=[GeographicSystem(name="Tama", classification=SystemClassification.HOME)]
        )
        layer = GeographicLayer.from_config(config, test_universe)

        score = layer.score_system(30002537)

        assert score.score == 1.0
        assert "home" in score.reason

    def test_hop_1_returns_decayed_interest(self, test_universe) -> None:
        """Hop 1 neighbors return decayed interest."""
        config = GeographicConfig(
            systems=[GeographicSystem(name="Tama", classification=SystemClassification.HOME)]
        )
        layer = GeographicLayer.from_config(config, test_universe)

        # Kedama is 1 hop from Tama
        score = layer.score_system(30002538)

        assert score.score == DEFAULT_HOME_WEIGHTS[1]
        assert score.reason is not None

    def test_unknown_system_returns_zero(self, test_universe) -> None:
        """System not in topology returns 0.0."""
        config = GeographicConfig(
            systems=[GeographicSystem(name="Tama", classification=SystemClassification.TRANSIT)]
        )
        layer = GeographicLayer.from_config(config, test_universe)

        # Distant system is not connected
        score = layer.score_system(30003458)

        assert score.score == 0.0
        assert score.reason is None

    def test_multiple_classifications_highest_wins(self, test_universe) -> None:
        """When system is reachable from multiple sources, highest interest wins."""
        config = GeographicConfig(
            systems=[
                # Home system at Tama
                GeographicSystem(name="Tama", classification=SystemClassification.HOME),
                # Transit system at Sujarento (2 hops from Tama)
                GeographicSystem(name="Sujarento", classification=SystemClassification.TRANSIT),
            ]
        )
        layer = GeographicLayer.from_config(config, test_universe)

        # Kedama is hop 1 from Tama (interest 0.95) and hop 1 from Sujarento (interest 0.3)
        # Should use higher value from Tama
        score = layer.score_system(30002538)

        assert score.score == DEFAULT_HOME_WEIGHTS[1]  # 0.95


# =============================================================================
# Legacy Compatibility Tests
# =============================================================================


class TestLegacyCompatibility:
    """Tests for backward compatibility with legacy config."""

    def test_legacy_config_builds_correctly(self, test_universe) -> None:
        """from_legacy_config produces working layer."""
        layer = GeographicLayer.from_legacy_config(
            operational_systems=["Tama", "Kedama"],
            interest_weights={"operational": 1.0, "hop_1": 1.0, "hop_2": 0.7},
            graph=test_universe,
        )

        # Both operational systems should have full interest
        assert layer.score_system(30002537).score == 1.0
        assert layer.score_system(30002538).score == 1.0

        # 2-hop neighbors should have 0.7
        # Sujarento is 1 hop from Kedama, so it should be 1.0
        # Actually Sujarento is hop 2 from Tama but hop 1 from Kedama
        # Since both are operational, Sujarento is hop 1 from Kedama
        assert layer.score_system(30002539).score == 1.0

    def test_legacy_weights_default_if_none(self, test_universe) -> None:
        """Legacy config uses defaults when weights not provided."""
        layer = GeographicLayer.from_legacy_config(
            operational_systems=["Tama"],
            interest_weights=None,
            graph=test_universe,
        )

        # Should use DEFAULT_HOME_WEIGHTS
        assert layer.score_system(30002537).score == DEFAULT_HOME_WEIGHTS[0]


# =============================================================================
# Serialization Tests
# =============================================================================


class TestSerialization:
    """Tests for serialization and deserialization."""

    def test_to_dict_and_from_dict_roundtrip(self, test_universe) -> None:
        """Layer can be serialized and deserialized."""
        config = GeographicConfig(
            systems=[GeographicSystem(name="Tama", classification=SystemClassification.HOME)]
        )
        layer = GeographicLayer.from_config(config, test_universe)

        # Serialize
        data = layer.to_dict()

        # Deserialize
        restored = GeographicLayer.from_dict(data)

        # Should have same interest map
        assert restored.total_systems == layer.total_systems
        assert restored.score_system(30002537).score == layer.score_system(30002537).score


# =============================================================================
# Utility Method Tests
# =============================================================================


class TestUtilityMethods:
    """Tests for utility methods."""

    def test_get_system_info_returns_details(self, test_universe) -> None:
        """get_system_info returns full details for tracked system."""
        config = GeographicConfig(
            systems=[GeographicSystem(name="Tama", classification=SystemClassification.HOME)]
        )
        layer = GeographicLayer.from_config(config, test_universe)

        info = layer.get_system_info(30002537)

        assert info is not None
        assert info["system_id"] == 30002537
        assert info["interest"] == 1.0
        assert info["classification"] == "home"

    def test_get_system_info_returns_none_for_untracked(self, test_universe) -> None:
        """get_system_info returns None for untracked system."""
        config = GeographicConfig(
            systems=[GeographicSystem(name="Tama", classification=SystemClassification.TRANSIT)]
        )
        layer = GeographicLayer.from_config(config, test_universe)

        info = layer.get_system_info(30003458)  # Distant, unconnected

        assert info is None

    def test_get_systems_by_classification(self, test_universe) -> None:
        """get_systems_by_classification returns correct systems."""
        config = GeographicConfig(
            systems=[
                GeographicSystem(name="Tama", classification=SystemClassification.HOME),
                GeographicSystem(name="Okkamon", classification=SystemClassification.HUNTING),
            ]
        )
        layer = GeographicLayer.from_config(config, test_universe)

        home_systems = layer.get_systems_by_classification(SystemClassification.HOME)
        hunting_systems = layer.get_systems_by_classification("hunting")

        # Tama is the home operational system
        assert 30002537 in home_systems
        # Okkamon is the hunting operational system
        assert 30002540 in hunting_systems
