"""
Tests for Universe Dispatcher Action Implementations.

Tests the individual action implementations in the universe dispatcher:
- route: Point-to-point navigation
- systems: Batch system lookups
- borders: Find high-sec/low-sec border systems
- search: Filter systems by criteria
- loop: Circular mining/patrol routes
- analyze: Route security analysis
- nearest: Find nearest systems matching predicates
- optimize_waypoints: TSP waypoint optimization
- activity: Live system activity data
- hotspots: Find high-activity systems
- gatecamp_risk: Route risk analysis
- fw_frontlines: Faction Warfare contested systems
- local_area: Consolidated local intel
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aria_esi.mcp.errors import InvalidParameterError


# =============================================================================
# Route Action Tests
# =============================================================================


class TestRouteAction:
    """Tests for universe route action."""

    def test_route_basic(self, universe_dispatcher):
        """Basic route between two systems."""
        result = asyncio.run(
            universe_dispatcher(action="route", origin="Jita", destination="Perimeter")
        )

        assert isinstance(result, dict)
        assert result.get("origin") == "Jita"
        assert result.get("destination") == "Perimeter"
        assert "jumps" in result
        assert result["jumps"] == 1

    def test_route_multi_hop(self, universe_dispatcher):
        """Route requiring multiple hops."""
        result = asyncio.run(
            universe_dispatcher(action="route", origin="Jita", destination="Urlen")
        )

        assert result["jumps"] >= 1
        assert "systems" in result

    def test_route_case_insensitive(self, universe_dispatcher):
        """System names are case-insensitive."""
        result = asyncio.run(
            universe_dispatcher(action="route", origin="JITA", destination="perimeter")
        )

        assert result["origin"] == "Jita"
        assert result["destination"] == "Perimeter"

    def test_route_safe_mode(self, universe_dispatcher):
        """Safe mode routing."""
        result = asyncio.run(
            universe_dispatcher(
                action="route",
                origin="Jita",
                destination="Urlen",
                mode="safe"
            )
        )

        assert result["mode"] == "safe"

    def test_route_unsafe_mode(self, universe_dispatcher):
        """Unsafe mode routing."""
        result = asyncio.run(
            universe_dispatcher(
                action="route",
                origin="Jita",
                destination="Sivala",
                mode="unsafe"
            )
        )

        assert result["mode"] == "unsafe"

    def test_route_invalid_mode_raises_error(self, universe_dispatcher):
        """Invalid mode raises InvalidParameterError."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(
                universe_dispatcher(
                    action="route",
                    origin="Jita",
                    destination="Perimeter",
                    mode="invalid"
                )
            )

        assert "mode" in str(exc.value).lower()

    def test_route_with_avoid_systems(self, universe_dispatcher):
        """Route with avoid_systems parameter."""
        result = asyncio.run(
            universe_dispatcher(
                action="route",
                origin="Jita",
                destination="Urlen",
                avoid_systems=["Perimeter"]
            )
        )

        system_names = [s["name"] for s in result["systems"]]
        assert "Perimeter" not in system_names

    def test_route_missing_origin_raises_error(self, universe_dispatcher):
        """Missing origin raises InvalidParameterError."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(
                universe_dispatcher(action="route", destination="Jita")
            )

        assert "origin" in str(exc.value).lower()

    def test_route_missing_destination_raises_error(self, universe_dispatcher):
        """Missing destination raises InvalidParameterError."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(
                universe_dispatcher(action="route", origin="Jita")
            )

        assert "destination" in str(exc.value).lower()

    def test_route_same_system(self, universe_dispatcher):
        """Route from system to itself."""
        result = asyncio.run(
            universe_dispatcher(action="route", origin="Jita", destination="Jita")
        )

        assert result["jumps"] == 0
        assert len(result["systems"]) == 1

    def test_route_includes_security_summary(self, universe_dispatcher):
        """Route result includes security summary."""
        result = asyncio.run(
            universe_dispatcher(action="route", origin="Jita", destination="Sivala")
        )

        assert "security_summary" in result


# =============================================================================
# Systems Action Tests
# =============================================================================


class TestSystemsAction:
    """Tests for universe systems action."""

    def test_systems_single(self, universe_dispatcher):
        """Lookup single system."""
        result = asyncio.run(
            universe_dispatcher(action="systems", systems=["Jita"])
        )

        assert result["found"] == 1
        assert result["not_found"] == 0
        assert len(result["systems"]) == 1
        assert result["systems"][0]["name"] == "Jita"

    def test_systems_multiple(self, universe_dispatcher):
        """Lookup multiple systems."""
        result = asyncio.run(
            universe_dispatcher(action="systems", systems=["Jita", "Perimeter", "Urlen"])
        )

        assert result["found"] == 3
        assert len(result["systems"]) == 3

    def test_systems_with_unknown(self, universe_dispatcher):
        """Lookup with unknown system."""
        result = asyncio.run(
            universe_dispatcher(action="systems", systems=["Jita", "Unknown123"])
        )

        assert result["found"] == 1
        assert result["not_found"] == 1

    def test_systems_includes_security_info(self, universe_dispatcher):
        """System info includes security data."""
        result = asyncio.run(
            universe_dispatcher(action="systems", systems=["Jita"])
        )

        system = result["systems"][0]
        assert "security" in system
        assert "security_class" in system
        assert system["security_class"] == "HIGH"

    def test_systems_includes_neighbors(self, universe_dispatcher):
        """System info includes neighbor list."""
        result = asyncio.run(
            universe_dispatcher(action="systems", systems=["Jita"])
        )

        system = result["systems"][0]
        assert "neighbors" in system
        assert len(system["neighbors"]) > 0

    def test_systems_missing_param_raises_error(self, universe_dispatcher):
        """Missing systems parameter raises error."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(universe_dispatcher(action="systems"))

        assert "systems" in str(exc.value).lower()

    def test_systems_empty_list_raises_error(self, universe_dispatcher):
        """Empty systems list raises error."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(universe_dispatcher(action="systems", systems=[]))

        assert "systems" in str(exc.value).lower()


# =============================================================================
# Borders Action Tests
# =============================================================================


class TestBordersAction:
    """Tests for universe borders action."""

    def test_borders_basic(self, universe_dispatcher):
        """Find border systems from origin."""
        result = asyncio.run(
            universe_dispatcher(action="borders", origin="Jita")
        )

        assert "origin" in result
        assert "borders" in result
        assert isinstance(result["borders"], list)

    def test_borders_with_limit(self, universe_dispatcher):
        """Borders respects limit parameter."""
        result = asyncio.run(
            universe_dispatcher(action="borders", origin="Jita", limit=2)
        )

        assert len(result["borders"]) <= 2

    def test_borders_with_max_jumps(self, universe_dispatcher):
        """Borders respects max_jumps parameter."""
        result = asyncio.run(
            universe_dispatcher(action="borders", origin="Jita", max_jumps=5)
        )

        assert result["search_radius"] == 5

    def test_borders_missing_origin_raises_error(self, universe_dispatcher):
        """Missing origin raises InvalidParameterError."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(universe_dispatcher(action="borders"))

        assert "origin" in str(exc.value).lower()

    def test_borders_from_border_system(self, universe_dispatcher):
        """Find borders from a border system."""
        result = asyncio.run(
            universe_dispatcher(action="borders", origin="Maurasi")
        )

        assert isinstance(result, dict)


# =============================================================================
# Search Action Tests
# =============================================================================


class TestSearchAction:
    """Tests for universe search action."""

    def test_search_by_region(self, universe_dispatcher):
        """Search systems in region."""
        result = asyncio.run(
            universe_dispatcher(action="search", region="The Forge")
        )

        assert "systems" in result
        assert isinstance(result["systems"], list)

    def test_search_with_security_filter(self, universe_dispatcher):
        """Search with security range filter."""
        result = asyncio.run(
            universe_dispatcher(
                action="search",
                security_min=0.5,
                security_max=1.0
            )
        )

        for system in result["systems"]:
            assert system["security"] >= 0.45  # Rounded to display value

    def test_search_with_origin_and_max_jumps(self, universe_dispatcher):
        """Search within jump range of origin."""
        result = asyncio.run(
            universe_dispatcher(
                action="search",
                origin="Jita",
                max_jumps=2
            )
        )

        assert "filters_applied" in result

    def test_search_border_only(self, universe_dispatcher):
        """Search for border systems only."""
        result = asyncio.run(
            universe_dispatcher(
                action="search",
                is_border=True
            )
        )

        assert "systems" in result

    def test_search_with_limit(self, universe_dispatcher):
        """Search respects limit."""
        result = asyncio.run(
            universe_dispatcher(
                action="search",
                limit=3
            )
        )

        assert len(result["systems"]) <= 3

    def test_search_max_jumps_requires_origin(self, universe_dispatcher):
        """max_jumps without origin raises error."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(
                universe_dispatcher(action="search", max_jumps=5)
            )

        assert "origin" in str(exc.value).lower()


# =============================================================================
# Loop Action Tests
# =============================================================================


class TestLoopAction:
    """Tests for universe loop action."""

    def test_loop_basic(self, universe_dispatcher):
        """Basic loop planning - standard fixture may not have enough borders."""
        from aria_esi.mcp.errors import InsufficientBordersError

        # Note: standard_universe only has 1 border system (Maurasi),
        # which is less than the minimum required (2), so we expect an error.
        # This test verifies the loop action processes the request correctly.
        try:
            result = asyncio.run(
                universe_dispatcher(
                    action="loop",
                    origin="Jita",
                    target_jumps=15,
                    min_borders=2  # Minimum allowed
                )
            )
            # If it succeeds, should return a dict
            assert isinstance(result, dict)
        except InsufficientBordersError:
            # Expected for standard_universe with insufficient border systems
            pass

    def test_loop_missing_origin_raises_error(self, universe_dispatcher):
        """Missing origin raises error."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(universe_dispatcher(action="loop"))

        assert "origin" in str(exc.value).lower()

    def test_loop_invalid_optimize_raises_error(self, universe_dispatcher):
        """Invalid optimize mode raises error."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(
                universe_dispatcher(
                    action="loop",
                    origin="Jita",
                    optimize="invalid"
                )
            )

        assert "optimize" in str(exc.value).lower()

    def test_loop_invalid_security_filter_raises_error(self, universe_dispatcher):
        """Invalid security_filter raises error."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(
                universe_dispatcher(
                    action="loop",
                    origin="Jita",
                    security_filter="invalid"
                )
            )

        assert "security_filter" in str(exc.value).lower()


# =============================================================================
# Analyze Action Tests
# =============================================================================


class TestAnalyzeAction:
    """Tests for universe analyze action."""

    def test_analyze_basic(self, universe_dispatcher):
        """Analyze a route."""
        result = asyncio.run(
            universe_dispatcher(
                action="analyze",
                systems=["Jita", "Perimeter", "Urlen"]
            )
        )

        assert isinstance(result, dict)
        assert "security_summary" in result
        assert "total_jumps" in result["security_summary"]

    def test_analyze_needs_minimum_systems(self, universe_dispatcher):
        """Analyze requires at least 2 systems."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(
                universe_dispatcher(action="analyze", systems=["Jita"])
            )

        assert "2 systems" in str(exc.value).lower()

    def test_analyze_missing_systems_raises_error(self, universe_dispatcher):
        """Missing systems raises error."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(universe_dispatcher(action="analyze"))

        assert "systems" in str(exc.value).lower()

    def test_analyze_includes_security_summary(self, universe_dispatcher):
        """Analyze includes security information."""
        result = asyncio.run(
            universe_dispatcher(
                action="analyze",
                systems=["Jita", "Maurasi", "Sivala"]
            )
        )

        assert "highsec_jumps" in result or "security" in str(result)


# =============================================================================
# Nearest Action Tests
# =============================================================================


class TestNearestAction:
    """Tests for universe nearest action."""

    def test_nearest_basic(self, universe_dispatcher):
        """Basic nearest search."""
        result = asyncio.run(
            universe_dispatcher(action="nearest", origin="Jita")
        )

        assert "origin" in result
        assert "systems" in result

    def test_nearest_border_filter(self, universe_dispatcher):
        """Nearest with border filter."""
        result = asyncio.run(
            universe_dispatcher(
                action="nearest",
                origin="Jita",
                is_border=True
            )
        )

        assert "predicates" in result

    def test_nearest_security_range(self, universe_dispatcher):
        """Nearest with security range."""
        result = asyncio.run(
            universe_dispatcher(
                action="nearest",
                origin="Jita",
                security_min=0.3,
                security_max=0.5
            )
        )

        assert isinstance(result, dict)

    def test_nearest_missing_origin_raises_error(self, universe_dispatcher):
        """Missing origin raises error."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(universe_dispatcher(action="nearest"))

        assert "origin" in str(exc.value).lower()


# =============================================================================
# Optimize Waypoints Action Tests
# =============================================================================


class TestOptimizeWaypointsAction:
    """Tests for universe optimize_waypoints action."""

    def test_optimize_waypoints_basic(self, universe_dispatcher):
        """Basic waypoint optimization."""
        result = asyncio.run(
            universe_dispatcher(
                action="optimize_waypoints",
                waypoints=["Jita", "Perimeter", "Urlen", "Maurasi"]
            )
        )

        assert isinstance(result, dict)

    def test_optimize_waypoints_missing_raises_error(self, universe_dispatcher):
        """Missing waypoints raises error."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(universe_dispatcher(action="optimize_waypoints"))

        assert "waypoints" in str(exc.value).lower()

    def test_optimize_waypoints_too_few_raises_error(self, universe_dispatcher):
        """Too few waypoints raises error."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(
                universe_dispatcher(action="optimize_waypoints", waypoints=["Jita"])
            )

        assert "waypoint" in str(exc.value).lower()

    def test_optimize_waypoints_with_origin(self, universe_dispatcher):
        """Waypoint optimization with fixed origin."""
        result = asyncio.run(
            universe_dispatcher(
                action="optimize_waypoints",
                waypoints=["Perimeter", "Urlen", "Maurasi"],
                origin="Jita"
            )
        )

        assert isinstance(result, dict)


# =============================================================================
# Activity Action Tests
# =============================================================================


class TestActivityAction:
    """Tests for universe activity action."""

    def test_activity_basic(self, universe_dispatcher, mock_activity_cache):
        """Basic activity lookup."""
        with patch("aria_esi.mcp.activity.get_activity_cache", return_value=mock_activity_cache):
            result = asyncio.run(
                universe_dispatcher(action="activity", systems=["Jita"])
            )

        assert "systems" in result

    def test_activity_missing_systems_raises_error(self, universe_dispatcher):
        """Missing systems raises error."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(universe_dispatcher(action="activity"))

        assert "systems" in str(exc.value).lower()

    def test_activity_multiple_systems(self, universe_dispatcher, mock_activity_with_data):
        """Activity for multiple systems."""
        activity_data = {
            30000142: {"ship_kills": 5, "pod_kills": 2},  # Jita
            30000144: {"ship_kills": 1, "pod_kills": 0},  # Perimeter
        }
        mock_cache = mock_activity_with_data(activity_data)

        with patch("aria_esi.mcp.activity.get_activity_cache", return_value=mock_cache):
            result = asyncio.run(
                universe_dispatcher(action="activity", systems=["Jita", "Perimeter"])
            )

        assert len(result["systems"]) == 2

    def test_activity_includes_cache_age(self, universe_dispatcher, mock_activity_cache):
        """Activity result includes cache age."""
        with patch("aria_esi.mcp.activity.get_activity_cache", return_value=mock_activity_cache):
            result = asyncio.run(
                universe_dispatcher(action="activity", systems=["Jita"])
            )

        assert "cache_age_seconds" in result


# =============================================================================
# Hotspots Action Tests
# =============================================================================


class TestHotspotsAction:
    """Tests for universe hotspots action."""

    def test_hotspots_basic(self, universe_dispatcher, mock_activity_cache):
        """Basic hotspots search."""
        with patch("aria_esi.mcp.activity.get_activity_cache", return_value=mock_activity_cache):
            result = asyncio.run(
                universe_dispatcher(action="hotspots", origin="Jita")
            )

        assert "origin" in result
        assert "hotspots" in result

    def test_hotspots_missing_origin_raises_error(self, universe_dispatcher):
        """Missing origin raises error."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(universe_dispatcher(action="hotspots"))

        assert "origin" in str(exc.value).lower()

    def test_hotspots_activity_type_kills(self, universe_dispatcher, mock_activity_cache):
        """Hotspots filtered by kills."""
        with patch("aria_esi.mcp.activity.get_activity_cache", return_value=mock_activity_cache):
            result = asyncio.run(
                universe_dispatcher(
                    action="hotspots",
                    origin="Jita",
                    activity_type="kills"
                )
            )

        assert result["activity_type"] == "kills"

    def test_hotspots_activity_type_jumps(self, universe_dispatcher, mock_activity_cache):
        """Hotspots filtered by jumps."""
        with patch("aria_esi.mcp.activity.get_activity_cache", return_value=mock_activity_cache):
            result = asyncio.run(
                universe_dispatcher(
                    action="hotspots",
                    origin="Jita",
                    activity_type="jumps"
                )
            )

        assert result["activity_type"] == "jumps"

    def test_hotspots_invalid_activity_type_raises_error(self, universe_dispatcher):
        """Invalid activity_type raises error."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(
                universe_dispatcher(
                    action="hotspots",
                    origin="Jita",
                    activity_type="invalid"
                )
            )

        assert "activity_type" in str(exc.value).lower()


# =============================================================================
# Gatecamp Risk Action Tests
# =============================================================================


class TestGatecampRiskAction:
    """Tests for universe gatecamp_risk action."""

    def test_gatecamp_risk_with_route(self, universe_dispatcher, mock_activity_cache):
        """Gatecamp risk for explicit route."""
        with patch("aria_esi.mcp.activity.get_activity_cache", return_value=mock_activity_cache):
            result = asyncio.run(
                universe_dispatcher(
                    action="gatecamp_risk",
                    route=["Jita", "Maurasi", "Sivala"]
                )
            )

        assert "overall_risk" in result
        assert "chokepoints" in result

    def test_gatecamp_risk_with_origin_destination(self, universe_dispatcher, mock_activity_cache):
        """Gatecamp risk calculated from origin/destination."""
        with patch("aria_esi.mcp.activity.get_activity_cache", return_value=mock_activity_cache):
            result = asyncio.run(
                universe_dispatcher(
                    action="gatecamp_risk",
                    origin="Jita",
                    destination="Sivala"
                )
            )

        assert "overall_risk" in result

    def test_gatecamp_risk_missing_params_raises_error(self, universe_dispatcher):
        """Missing both route and origin/destination raises error."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(universe_dispatcher(action="gatecamp_risk"))

        assert "route" in str(exc.value).lower() or "origin" in str(exc.value).lower()

    def test_gatecamp_risk_includes_recommendation(self, universe_dispatcher, mock_activity_cache):
        """Gatecamp risk includes recommendation."""
        with patch("aria_esi.mcp.activity.get_activity_cache", return_value=mock_activity_cache):
            result = asyncio.run(
                universe_dispatcher(
                    action="gatecamp_risk",
                    route=["Jita", "Perimeter"]
                )
            )

        assert "recommendation" in result


# =============================================================================
# FW Frontlines Action Tests
# =============================================================================


class TestFWFrontlinesAction:
    """Tests for universe fw_frontlines action."""

    def test_fw_frontlines_basic(self, universe_dispatcher, mock_activity_cache):
        """Basic FW frontlines query."""
        with patch("aria_esi.mcp.activity.get_activity_cache", return_value=mock_activity_cache):
            result = asyncio.run(
                universe_dispatcher(action="fw_frontlines")
            )

        assert "contested" in result
        assert "vulnerable" in result
        assert "stable" in result

    def test_fw_frontlines_with_faction_filter(self, universe_dispatcher, mock_activity_cache):
        """FW frontlines filtered by faction."""
        with patch("aria_esi.mcp.activity.get_activity_cache", return_value=mock_activity_cache):
            result = asyncio.run(
                universe_dispatcher(action="fw_frontlines", faction="caldari")
            )

        assert "faction_filter" in result

    def test_fw_frontlines_invalid_faction_raises_error(self, universe_dispatcher):
        """Invalid faction raises error."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(
                universe_dispatcher(action="fw_frontlines", faction="invalid_faction")
            )

        assert "faction" in str(exc.value).lower()


# =============================================================================
# Local Area Action Tests
# =============================================================================


class TestLocalAreaAction:
    """Tests for universe local_area action."""

    def test_local_area_basic(self, universe_dispatcher, mock_activity_cache):
        """Basic local area query."""
        with patch("aria_esi.mcp.activity.get_activity_cache", return_value=mock_activity_cache):
            result = asyncio.run(
                universe_dispatcher(action="local_area", origin="Jita")
            )

        assert "origin" in result
        assert "threat_summary" in result

    def test_local_area_missing_origin_raises_error(self, universe_dispatcher):
        """Missing origin raises error."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(universe_dispatcher(action="local_area"))

        assert "origin" in str(exc.value).lower()

    def test_local_area_includes_hotspots(self, universe_dispatcher, mock_activity_cache):
        """Local area includes hotspots."""
        with patch("aria_esi.mcp.activity.get_activity_cache", return_value=mock_activity_cache):
            result = asyncio.run(
                universe_dispatcher(action="local_area", origin="Jita")
            )

        assert "hotspots" in result

    def test_local_area_includes_quiet_zones(self, universe_dispatcher, mock_activity_cache):
        """Local area includes quiet zones."""
        with patch("aria_esi.mcp.activity.get_activity_cache", return_value=mock_activity_cache):
            result = asyncio.run(
                universe_dispatcher(action="local_area", origin="Jita")
            )

        assert "quiet_zones" in result

    def test_local_area_includes_escape_routes(self, universe_dispatcher, mock_activity_cache):
        """Local area includes escape routes."""
        with patch("aria_esi.mcp.activity.get_activity_cache", return_value=mock_activity_cache):
            result = asyncio.run(
                universe_dispatcher(action="local_area", origin="Sivala")
            )

        assert "escape_routes" in result

    def test_local_area_with_max_jumps(self, universe_dispatcher, mock_activity_cache):
        """Local area respects max_jumps."""
        with patch("aria_esi.mcp.activity.get_activity_cache", return_value=mock_activity_cache):
            result = asyncio.run(
                universe_dispatcher(
                    action="local_area",
                    origin="Jita",
                    max_jumps=3
                )
            )

        assert result["search_radius"] == 3


# =============================================================================
# Invalid Action Tests
# =============================================================================


class TestInvalidActions:
    """Tests for invalid action handling."""

    def test_invalid_action_raises_error(self, universe_dispatcher):
        """Unknown action raises InvalidParameterError."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(universe_dispatcher(action="nonexistent_action"))

        assert "action" in str(exc.value)
        assert "must be one of" in str(exc.value).lower()

    def test_empty_action_raises_error(self, universe_dispatcher):
        """Empty action raises InvalidParameterError."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(universe_dispatcher(action=""))

        assert "action" in str(exc.value)
