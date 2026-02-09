"""Tests for RouteSignal provider."""

from __future__ import annotations

import pytest

from aria_esi.services.redisq.interest_v2.signals.routes import RouteSignal

from .conftest import MockProcessedKill


class TestRouteSignalScore:
    """Tests for RouteSignal.score() method."""

    @pytest.fixture
    def signal(self) -> RouteSignal:
        """Create a RouteSignal instance."""
        return RouteSignal()

    def test_score_no_routes_configured(self, signal: RouteSignal) -> None:
        """Test scoring with no routes configured returns 0."""
        kill = MockProcessedKill()
        result = signal.score(kill, 30000142, {})
        assert result.score == 0.0
        assert "No routes configured" in result.reason
        assert result.prefetch_capable is False

    def test_score_empty_routes_list(self, signal: RouteSignal) -> None:
        """Test scoring with empty routes list returns 0."""
        kill = MockProcessedKill()
        result = signal.score(kill, 30000142, {"routes": []})
        assert result.score == 0.0

    def test_score_system_not_on_route(self, signal: RouteSignal) -> None:
        """Test scoring when system is not on any route."""
        kill = MockProcessedKill()
        config = {
            "routes": [
                {"name": "Jita-Amarr", "systems": [30000142, 30000144, 30002187], "score": 0.9},
            ]
        }
        result = signal.score(kill, 30005000, config)  # Random system
        assert result.score == 0.0
        assert "not on any route" in result.reason.lower()

    def test_score_system_on_route(
        self, signal: RouteSignal, mock_kill_on_route: MockProcessedKill
    ) -> None:
        """Test scoring when system is on a route."""
        config = {
            "routes": [
                {"name": "Jita-Amarr", "systems": [30000142, 30000144, 30002187], "score": 0.9},
            ]
        }
        # Perimeter (30000144) is on the route
        result = signal.score(mock_kill_on_route, 30000144, config)
        assert result.score == 0.9
        assert "Jita-Amarr" in result.reason

    def test_score_default_route_score(self, signal: RouteSignal) -> None:
        """Test default route score is 0.9."""
        kill = MockProcessedKill()
        config = {
            "routes": [
                {"name": "Trade Route", "systems": [30000142]},  # No score specified
            ]
        }
        result = signal.score(kill, 30000142, config)
        assert result.score == 0.9  # Default

    def test_score_custom_route_score(self, signal: RouteSignal) -> None:
        """Test custom route score."""
        kill = MockProcessedKill()
        config = {
            "routes": [
                {"name": "Trade Route", "systems": [30000142], "score": 0.7},
            ]
        }
        result = signal.score(kill, 30000142, config)
        assert result.score == 0.7

    def test_score_ship_filter_match(
        self, signal: RouteSignal, mock_kill_freighter: MockProcessedKill
    ) -> None:
        """Test route with ship filter that matches."""
        config = {
            "routes": [
                {
                    "name": "Freighter Route",
                    "systems": [30000142],
                    "score": 0.95,
                    "ship_filter": ["freighter", "jump_freighter"],
                },
            ]
        }
        # Freighter kill
        mock_kill_freighter.solar_system_id = 30000142
        result = signal.score(mock_kill_freighter, 30000142, config)
        assert result.score == 0.95
        assert "Freighter Route" in result.reason

    def test_score_ship_filter_no_match(self, signal: RouteSignal) -> None:
        """Test route with ship filter that doesn't match."""
        kill = MockProcessedKill(victim_ship_type_id=24690)  # Vexor
        config = {
            "routes": [
                {
                    "name": "Freighter Route",
                    "systems": [30000142],
                    "score": 0.95,
                    "ship_filter": ["freighter"],
                },
            ]
        }
        result = signal.score(kill, 30000142, config)
        assert result.score == 0.0
        assert "Ship type not in route filter" in result.reason

    def test_score_ship_filter_none_kill(self, signal: RouteSignal) -> None:
        """Test ship filter with None kill (no ship data)."""
        config = {
            "routes": [
                {
                    "name": "Freighter Route",
                    "systems": [30000142],
                    "ship_filter": ["freighter"],
                },
            ]
        }
        # System is on route - ship filter only checked if kill exists
        # With None kill, the filter check is skipped (line 93: if ship_filter and kill)
        result = signal.score(None, 30000142, config)
        # With no kill to check, filter is skipped and route matches
        assert result.score == 0.9

    def test_score_multiple_routes_best_score(self, signal: RouteSignal) -> None:
        """Test best score from multiple matching routes."""
        kill = MockProcessedKill()
        config = {
            "routes": [
                {"name": "Low Priority", "systems": [30000142], "score": 0.5},
                {"name": "High Priority", "systems": [30000142], "score": 0.95},
            ]
        }
        result = signal.score(kill, 30000142, config)
        assert result.score == 0.95
        assert "High Priority" in result.reason

    def test_score_route_with_ship_filter_and_without(self, signal: RouteSignal) -> None:
        """Test system on route with filter (no match) and without filter."""
        kill = MockProcessedKill(victim_ship_type_id=24690)  # Vexor
        config = {
            "routes": [
                {
                    "name": "Freighter Route",
                    "systems": [30000142],
                    "score": 0.95,
                    "ship_filter": ["freighter"],
                },
                {"name": "General Route", "systems": [30000142], "score": 0.7},
            ]
        }
        result = signal.score(kill, 30000142, config)
        # Should match general route (no filter)
        assert result.score == 0.7
        assert "General Route" in result.reason

    def test_score_unnamed_route(self, signal: RouteSignal) -> None:
        """Test route without name uses 'Unnamed'."""
        kill = MockProcessedKill()
        config = {
            "routes": [
                {"systems": [30000142], "score": 0.8},  # No name
            ]
        }
        result = signal.score(kill, 30000142, config)
        assert result.score == 0.8
        assert "Unnamed" in result.reason

    def test_score_raw_value_includes_route(
        self, signal: RouteSignal, mock_kill_on_route: MockProcessedKill
    ) -> None:
        """Test raw_value includes matched route name."""
        config = {
            "routes": [
                {"name": "Test Route", "systems": [30000144], "score": 0.9},
            ]
        }
        result = signal.score(mock_kill_on_route, 30000144, config)
        assert result.raw_value is not None
        assert result.raw_value["route"] == "Test Route"

    def test_score_dst_filter(self, signal: RouteSignal) -> None:
        """Test DST ship filter."""
        kill = MockProcessedKill(victim_ship_type_id=12753)  # DST
        config = {
            "routes": [
                {"name": "DST Route", "systems": [30000142], "ship_filter": ["dst"]},
            ]
        }
        result = signal.score(kill, 30000142, config)
        assert result.score == 0.9

    def test_score_blockade_runner_filter(self, signal: RouteSignal) -> None:
        """Test blockade runner ship filter."""
        kill = MockProcessedKill(victim_ship_type_id=12731)  # BR
        config = {
            "routes": [
                {
                    "name": "BR Route",
                    "systems": [30000142],
                    "ship_filter": ["blockade_runner"],
                },
            ]
        }
        result = signal.score(kill, 30000142, config)
        assert result.score == 0.9


class TestRouteSignalValidate:
    """Tests for RouteSignal.validate() method."""

    @pytest.fixture
    def signal(self) -> RouteSignal:
        """Create a RouteSignal instance."""
        return RouteSignal()

    def test_validate_empty_config(self, signal: RouteSignal) -> None:
        """Test validation fails for empty config."""
        errors = signal.validate({})
        assert len(errors) == 1
        assert "At least one route" in errors[0]

    def test_validate_empty_routes_list(self, signal: RouteSignal) -> None:
        """Test validation fails for empty routes list."""
        errors = signal.validate({"routes": []})
        assert len(errors) == 1
        assert "At least one route" in errors[0]

    def test_validate_valid_config(self, signal: RouteSignal) -> None:
        """Test validation passes for valid config."""
        config = {
            "routes": [
                {"name": "Trade Route", "systems": [30000142, 30002187], "score": 0.9},
            ]
        }
        errors = signal.validate(config)
        assert errors == []

    def test_validate_route_not_dict(self, signal: RouteSignal) -> None:
        """Test validation fails when route is not a dict."""
        config = {"routes": ["Jita-Amarr"]}
        errors = signal.validate(config)
        assert len(errors) == 1
        assert "must be a dictionary" in errors[0]

    def test_validate_missing_systems(self, signal: RouteSignal) -> None:
        """Test validation fails when systems is missing."""
        config = {"routes": [{"name": "Empty Route"}]}
        errors = signal.validate(config)
        assert len(errors) == 1
        assert "systems" in errors[0]

    def test_validate_empty_systems(self, signal: RouteSignal) -> None:
        """Test validation fails for empty systems list."""
        config = {"routes": [{"name": "Empty Route", "systems": []}]}
        errors = signal.validate(config)
        assert len(errors) == 1
        assert "systems" in errors[0]

    def test_validate_score_out_of_range(self, signal: RouteSignal) -> None:
        """Test validation fails for score outside [0, 1]."""
        config = {"routes": [{"systems": [30000142], "score": 1.5}]}
        errors = signal.validate(config)
        assert len(errors) == 1
        assert "between 0 and 1" in errors[0]

    def test_validate_score_negative(self, signal: RouteSignal) -> None:
        """Test validation fails for negative score."""
        config = {"routes": [{"systems": [30000142], "score": -0.5}]}
        errors = signal.validate(config)
        assert len(errors) == 1
        assert "between 0 and 1" in errors[0]

    def test_validate_multiple_routes(self, signal: RouteSignal) -> None:
        """Test validation handles multiple routes."""
        config = {
            "routes": [
                {"name": "Route 1", "systems": [30000142]},
                {"name": "Route 2", "systems": [30002187], "score": 0.8},
            ]
        }
        errors = signal.validate(config)
        assert errors == []


class TestRouteSignalProperties:
    """Tests for RouteSignal class properties."""

    def test_signal_name(self) -> None:
        """Test signal name is correct."""
        signal = RouteSignal()
        assert signal._name == "routes"

    def test_signal_category(self) -> None:
        """Test signal category is correct."""
        signal = RouteSignal()
        assert signal._category == "routes"

    def test_prefetch_capable(self) -> None:
        """Test signal is NOT prefetch capable."""
        signal = RouteSignal()
        assert signal._prefetch_capable is False


class TestRouteSignalMatchesShipFilter:
    """Tests for RouteSignal._matches_ship_filter method."""

    @pytest.fixture
    def signal(self) -> RouteSignal:
        """Create a RouteSignal instance."""
        return RouteSignal()

    def test_matches_none_ship_type(self, signal: RouteSignal) -> None:
        """Test None ship type doesn't match."""
        assert signal._matches_ship_filter(None, ["freighter"]) is False

    def test_matches_freighter(self, signal: RouteSignal) -> None:
        """Test freighter type ID matches."""
        assert signal._matches_ship_filter(20185, ["freighter"]) is True

    def test_matches_jump_freighter(self, signal: RouteSignal) -> None:
        """Test jump freighter type ID matches."""
        assert signal._matches_ship_filter(28846, ["jump_freighter"]) is True

    def test_matches_dst(self, signal: RouteSignal) -> None:
        """Test DST type ID matches."""
        assert signal._matches_ship_filter(12753, ["dst"]) is True

    def test_matches_blockade_runner(self, signal: RouteSignal) -> None:
        """Test blockade runner type ID matches."""
        assert signal._matches_ship_filter(12731, ["blockade_runner"]) is True

    def test_no_match_unknown_ship(self, signal: RouteSignal) -> None:
        """Test unknown ship doesn't match."""
        assert signal._matches_ship_filter(24690, ["freighter"]) is False  # Vexor

    def test_matches_multiple_categories(self, signal: RouteSignal) -> None:
        """Test matching with multiple categories."""
        # Freighter
        assert signal._matches_ship_filter(20185, ["freighter", "orca"]) is True
        # Neither
        assert signal._matches_ship_filter(24690, ["freighter", "orca"]) is False

    def test_category_normalization(self, signal: RouteSignal) -> None:
        """Test category name normalization (spaces, underscores)."""
        # With space
        assert signal._matches_ship_filter(28846, ["jump freighter"]) is True
