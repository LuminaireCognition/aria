"""
Tests for Route Interest Layer.
"""

from __future__ import annotations

import pytest

from aria_esi.services.redisq.interest.layers import (
    RouteConfig,
    RouteDefinition,
    RouteLayer,
)
from tests.mcp.conftest import create_mock_universe

from .conftest import make_kill

# =============================================================================
# Test Universe Setup
# =============================================================================

# Linear route: Tama -> Kedama -> Sujarento -> Jita
TEST_SYSTEMS = [
    {"name": "Tama", "id": 30002537, "sec": 0.3, "const": 20000001, "region": 10000001},
    {"name": "Kedama", "id": 30002538, "sec": 0.2, "const": 20000001, "region": 10000001},
    {"name": "Sujarento", "id": 30002539, "sec": 0.4, "const": 20000001, "region": 10000001},
    {"name": "Jita", "id": 30000142, "sec": 0.9, "const": 20000020, "region": 10000002},
    {"name": "Perimeter", "id": 30000144, "sec": 0.9, "const": 20000020, "region": 10000002},
    {"name": "Other", "id": 30003458, "sec": 0.5, "const": 20000003, "region": 10000003},
]

TEST_EDGES = [
    (0, 1),  # Tama -- Kedama
    (1, 2),  # Kedama -- Sujarento
    (2, 3),  # Sujarento -- Jita
    (3, 4),  # Jita -- Perimeter
]


@pytest.fixture
def test_universe():
    """Create test universe with linear route topology."""
    return create_mock_universe(TEST_SYSTEMS, TEST_EDGES)


# =============================================================================
# Configuration Tests
# =============================================================================


class TestRouteDefinition:
    """Tests for RouteDefinition."""

    def test_from_dict_parses_all_fields(self) -> None:
        """Route definition parses all fields."""
        data = {
            "name": "logistics",
            "waypoints": ["Tama", "Jita"],
            "interest": 0.95,
            "ship_filter": ["Freighter", "Industrial"],
            "bidirectional": True,
        }

        route = RouteDefinition.from_dict(data)

        assert route.name == "logistics"
        assert route.waypoints == ["Tama", "Jita"]
        assert route.interest == 0.95
        assert route.ship_filter == ["Freighter", "Industrial"]
        assert route.bidirectional is True

    def test_from_dict_defaults(self) -> None:
        """Route definition uses defaults for missing fields."""
        data = {
            "waypoints": ["Tama", "Jita"],
        }

        route = RouteDefinition.from_dict(data)

        assert route.name == "unnamed"
        assert route.interest == 0.95
        assert route.ship_filter is None
        assert route.bidirectional is True

    def test_matches_ship_no_filter_matches_all(self) -> None:
        """Without ship filter, all ships match."""
        route = RouteDefinition(name="test", waypoints=["A", "B"], ship_filter=None)

        assert route.matches_ship(587) is True  # Rifter
        assert route.matches_ship(20183) is True  # Charon
        assert route.matches_ship(None) is True

    def test_matches_ship_with_filter(self) -> None:
        """With ship filter, only matching ships pass."""
        route = RouteDefinition(
            name="test",
            waypoints=["A", "B"],
            ship_filter=["Freighter"],
        )

        assert route.matches_ship(20183) is True  # Charon (freighter)
        assert route.matches_ship(587) is False  # Rifter (frigate)
        assert route.matches_ship(None) is False


class TestRouteConfig:
    """Tests for RouteConfig."""

    def test_from_dict_parses_routes(self) -> None:
        """Config parses multiple routes."""
        data = {
            "routes": [
                {"name": "route1", "waypoints": ["A", "B"]},
                {"name": "route2", "waypoints": ["C", "D"]},
            ]
        }

        config = RouteConfig.from_dict(data)

        assert len(config.routes) == 2
        assert config.is_configured is True

    def test_empty_config(self) -> None:
        """Empty config has no routes."""
        config = RouteConfig.from_dict(None)

        assert len(config.routes) == 0
        assert config.is_configured is False


# =============================================================================
# Layer Construction Tests
# =============================================================================


class TestRouteLayerConstruction:
    """Tests for building route layer."""

    def test_from_config_includes_waypoints(self, test_universe) -> None:
        """Route includes all waypoint systems."""
        config = RouteConfig(
            routes=[
                RouteDefinition(
                    name="tama_jita",
                    waypoints=["Tama", "Jita"],
                )
            ]
        )

        layer = RouteLayer.from_config(config, test_universe)

        # All systems along the path should be included
        assert 30002537 in layer._route_systems  # Tama
        assert 30002538 in layer._route_systems  # Kedama (on path)
        assert 30002539 in layer._route_systems  # Sujarento (on path)
        assert 30000142 in layer._route_systems  # Jita

    def test_from_config_includes_intermediate_systems(self, test_universe) -> None:
        """Route includes all intermediate systems."""
        config = RouteConfig(
            routes=[
                RouteDefinition(
                    name="direct",
                    waypoints=["Tama", "Sujarento"],  # Kedama is in between
                )
            ]
        )

        layer = RouteLayer.from_config(config, test_universe)

        # Kedama should be included even though it's not a waypoint
        assert 30002538 in layer._route_systems  # Kedama

    def test_from_config_excludes_unconnected_systems(self, test_universe) -> None:
        """Unconnected systems are not included."""
        config = RouteConfig(
            routes=[
                RouteDefinition(
                    name="tama_jita",
                    waypoints=["Tama", "Jita"],
                )
            ]
        )

        layer = RouteLayer.from_config(config, test_universe)

        # "Other" is not connected to the route
        assert 30003458 not in layer._route_systems


# =============================================================================
# Scoring Tests
# =============================================================================


class TestRouteLayerScoring:
    """Tests for route layer scoring."""

    def test_system_on_route_returns_interest(self, test_universe) -> None:
        """System on route returns configured interest."""
        config = RouteConfig(
            routes=[
                RouteDefinition(
                    name="logistics",
                    waypoints=["Tama", "Jita"],
                    interest=0.95,
                )
            ]
        )
        layer = RouteLayer.from_config(config, test_universe)

        score = layer.score_system(30002538)  # Kedama

        assert score.score == 0.95
        assert "logistics" in score.reason

    def test_system_not_on_route_returns_zero(self, test_universe) -> None:
        """System not on route returns 0."""
        config = RouteConfig(
            routes=[
                RouteDefinition(
                    name="logistics",
                    waypoints=["Tama", "Jita"],
                )
            ]
        )
        layer = RouteLayer.from_config(config, test_universe)

        score = layer.score_system(30003458)  # "Other" - not on route

        assert score.score == 0.0

    def test_ship_filter_matches_freighter(self, test_universe) -> None:
        """Route with freighter filter matches freighter kills."""
        config = RouteConfig(
            routes=[
                RouteDefinition(
                    name="logistics",
                    waypoints=["Tama", "Jita"],
                    interest=0.95,
                    ship_filter=["Freighter"],
                )
            ]
        )
        layer = RouteLayer.from_config(config, test_universe)

        # Freighter kill
        kill = make_kill(
            victim_ship_type_id=20183,  # Charon
            system_id=30002538,  # Kedama
        )
        score = layer.score_kill(30002538, kill)

        assert score.score == 0.95
        assert "logistics" in score.reason

    def test_ship_filter_rejects_frigate(self, test_universe) -> None:
        """Route with freighter filter rejects frigate kills."""
        config = RouteConfig(
            routes=[
                RouteDefinition(
                    name="logistics",
                    waypoints=["Tama", "Jita"],
                    interest=0.95,
                    ship_filter=["Freighter"],
                )
            ]
        )
        layer = RouteLayer.from_config(config, test_universe)

        # Frigate kill
        kill = make_kill(
            victim_ship_type_id=587,  # Rifter
            system_id=30002538,  # Kedama
        )
        score = layer.score_kill(30002538, kill)

        assert score.score == 0.0  # Doesn't match filter

    def test_no_filter_matches_all_ships(self, test_universe) -> None:
        """Route without filter matches all ships."""
        config = RouteConfig(
            routes=[
                RouteDefinition(
                    name="patrol",
                    waypoints=["Tama", "Jita"],
                    interest=0.85,
                    ship_filter=None,  # No filter
                )
            ]
        )
        layer = RouteLayer.from_config(config, test_universe)

        # Any ship type
        kill = make_kill(
            victim_ship_type_id=587,  # Rifter
            system_id=30002538,
        )
        score = layer.score_kill(30002538, kill)

        assert score.score == 0.85


# =============================================================================
# Multiple Routes Tests
# =============================================================================


class TestMultipleRoutes:
    """Tests for systems on multiple routes."""

    def test_highest_interest_wins(self, test_universe) -> None:
        """System on multiple routes uses highest interest."""
        config = RouteConfig(
            routes=[
                RouteDefinition(
                    name="low_priority",
                    waypoints=["Tama", "Jita"],
                    interest=0.7,
                ),
                RouteDefinition(
                    name="high_priority",
                    waypoints=["Tama", "Sujarento"],
                    interest=0.95,
                ),
            ]
        )
        layer = RouteLayer.from_config(config, test_universe)

        # Kedama is on both routes
        score = layer.score_system(30002538)

        assert score.score == 0.95  # High priority wins

    def test_get_routes_for_system(self, test_universe) -> None:
        """Can get list of routes for a system."""
        config = RouteConfig(
            routes=[
                RouteDefinition(name="route1", waypoints=["Tama", "Jita"]),
                RouteDefinition(name="route2", waypoints=["Tama", "Sujarento"]),
            ]
        )
        layer = RouteLayer.from_config(config, test_universe)

        routes = layer.get_routes_for_system(30002538)  # Kedama

        assert "route1" in routes
        assert "route2" in routes


# =============================================================================
# Serialization Tests
# =============================================================================


class TestSerialization:
    """Tests for serialization."""

    def test_to_dict_roundtrip(self, test_universe) -> None:
        """Can serialize and deserialize layer."""
        config = RouteConfig(
            routes=[
                RouteDefinition(
                    name="logistics",
                    waypoints=["Tama", "Jita"],
                    interest=0.95,
                )
            ]
        )
        layer = RouteLayer.from_config(config, test_universe)

        data = layer.to_dict()
        restored = RouteLayer.from_dict(data)

        assert restored.total_systems == layer.total_systems
        assert restored.score_system(30002538).score == 0.95
