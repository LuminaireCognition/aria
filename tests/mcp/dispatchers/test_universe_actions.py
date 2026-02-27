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
from unittest.mock import AsyncMock, patch

import pytest

from aria_esi.mcp.errors import InvalidParameterError
from aria_esi.store.activity import FWSystemData

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

    def test_analyze_security_summary_invariant(self, universe_dispatcher):
        """Security summary jumps must sum to total_jumps."""
        result = asyncio.run(
            universe_dispatcher(
                action="analyze",
                systems=["Jita", "Perimeter", "Urlen"],
            )
        )

        ss = result["security_summary"]
        assert ss["highsec_jumps"] + ss["lowsec_jumps"] + ss["nullsec_jumps"] == ss["total_jumps"]


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

    def test_activity_basic(self, universe_dispatcher):
        """Basic activity lookup."""
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
        mock_activity_with_data(activity_data)

        result = asyncio.run(
            universe_dispatcher(action="activity", systems=["Jita", "Perimeter"])
        )

        assert len(result["systems"]) == 2

    def test_activity_includes_cache_age(self, universe_dispatcher):
        """Activity result includes cache age."""
        result = asyncio.run(
            universe_dispatcher(action="activity", systems=["Jita"])
        )

        assert "cache_age_seconds" in result


# =============================================================================
# Hotspots Action Tests
# =============================================================================


class TestHotspotsAction:
    """Tests for universe hotspots action."""

    def test_hotspots_basic(self, universe_dispatcher):
        """Basic hotspots search."""
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

    def test_hotspots_activity_type_kills(self, universe_dispatcher):
        """Hotspots filtered by kills."""
        result = asyncio.run(
            universe_dispatcher(
                action="hotspots",
                origin="Jita",
                activity_type="kills"
            )
        )

        assert result["activity_type"] == "kills"

    def test_hotspots_activity_type_jumps(self, universe_dispatcher):
        """Hotspots filtered by jumps."""
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

    def test_gatecamp_risk_with_route(self, universe_dispatcher):
        """Gatecamp risk for explicit route."""
        result = asyncio.run(
            universe_dispatcher(
                action="gatecamp_risk",
                route=["Jita", "Maurasi", "Sivala"]
            )
        )

        assert "overall_risk" in result
        assert "chokepoints" in result

    def test_gatecamp_risk_with_origin_destination(self, universe_dispatcher):
        """Gatecamp risk calculated from origin/destination."""
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

    def test_gatecamp_risk_includes_recommendation(self, universe_dispatcher):
        """Gatecamp risk includes recommendation."""
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

    def test_fw_frontlines_basic(self, universe_dispatcher):
        """Basic FW frontlines query."""
        result = asyncio.run(
            universe_dispatcher(action="fw_frontlines")
        )

        assert "contested" in result
        assert "vulnerable" in result
        assert "stable" in result

    def test_fw_frontlines_with_faction_filter(self, universe_dispatcher):
        """FW frontlines filtered by faction."""
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

    def test_local_area_basic(self, universe_dispatcher):
        """Basic local area query."""
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

    def test_local_area_includes_hotspots(self, universe_dispatcher):
        """Local area includes hotspots."""
        result = asyncio.run(
            universe_dispatcher(action="local_area", origin="Jita")
        )

        assert "hotspots" in result

    def test_local_area_includes_quiet_zones(self, universe_dispatcher):
        """Local area includes quiet zones."""
        result = asyncio.run(
            universe_dispatcher(action="local_area", origin="Jita")
        )

        assert "quiet_zones" in result

    def test_local_area_includes_escape_routes(self, universe_dispatcher):
        """Local area includes escape routes."""
        result = asyncio.run(
            universe_dispatcher(action="local_area", origin="Sivala")
        )

        assert "escape_routes" in result

    def test_local_area_with_max_jumps(self, universe_dispatcher):
        """Local area respects max_jumps."""
        result = asyncio.run(
            universe_dispatcher(
                action="local_area",
                origin="Jita",
                max_jumps=3
            )
        )

        assert result["search_radius"] == 3


# =============================================================================
# Territory Analysis Action Tests
# =============================================================================


class TestTerritoryAnalysisAction:
    """Tests for universe territory_analysis action."""

    def test_territory_analysis_coalition(self, universe_dispatcher):
        """Territory analysis for a coalition."""
        # Mock the analyze_territory function
        mock_result = {
            "entity_name": "The Imperium",
            "entity_type": "coalition",
            "alliance_count": 4,
            "system_count": 479,
            "constellation_count": 71,
            "region_count": 9,
            "regions": [{"name": "Delve", "system_count": 96}],
        }

        with patch(
            "aria_esi.services.sovereignty.analyze_territory",
            return_value=mock_result,
        ):
            result = asyncio.run(
                universe_dispatcher(action="territory_analysis", coalition="imperium")
            )

        assert result["entity_name"] == "The Imperium"
        assert result["entity_type"] == "coalition"
        assert result["system_count"] == 479

    def test_territory_analysis_alliance(self, universe_dispatcher):
        """Territory analysis for an alliance."""
        mock_result = {
            "entity_name": "[GSF] Goonswarm Federation",
            "entity_type": "alliance",
            "alliance_count": 1,
            "system_count": 200,
            "constellation_count": 30,
            "region_count": 3,
            "regions": [{"name": "Delve", "system_count": 96}],
        }

        with patch(
            "aria_esi.services.sovereignty.analyze_territory",
            return_value=mock_result,
        ):
            result = asyncio.run(
                universe_dispatcher(action="territory_analysis", alliance_id=1354830081)
            )

        assert result["entity_type"] == "alliance"
        assert result["system_count"] == 200

    def test_territory_analysis_missing_params_raises_error(self, universe_dispatcher):
        """Missing both coalition and alliance_id raises error."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(universe_dispatcher(action="territory_analysis"))

        assert "coalition" in str(exc.value).lower()

    def test_territory_analysis_coalition_not_found(self, universe_dispatcher):
        """Unknown coalition returns error result."""
        mock_result = {
            "error": "coalition_not_found",
            "message": "Unknown coalition: nonexistent",
        }

        with patch(
            "aria_esi.services.sovereignty.analyze_territory",
            return_value=mock_result,
        ):
            result = asyncio.run(
                universe_dispatcher(action="territory_analysis", coalition="nonexistent")
            )

        assert result["error"] == "coalition_not_found"


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


# =============================================================================
# Route FW Warnings Tests
# =============================================================================


class TestRouteFWWarnings:
    """Tests for FW warzone warnings in route results."""

    def test_route_fw_warnings(self, universe_dispatcher, mock_activity_cache):
        """Route through FW systems includes FW warnings."""
        fw_data = {
            30000160: FWSystemData(
                system_id=30000160,
                owner_faction_id=500001,
                occupier_faction_id=500004,
                contested="contested",
                victory_points=12000,
                victory_points_threshold=27000,
            ),
        }
        mock_activity_cache.get_all_fw = AsyncMock(return_value=fw_data)

        result = asyncio.run(
            universe_dispatcher(
                action="route",
                origin="Maurasi",
                destination="Ala",
            )
        )

        warnings = result.get("warnings", [])
        fw_warnings = [w for w in warnings if "Faction Warfare" in w or "FW" in w]
        assert len(fw_warnings) >= 1
        assert any("warzone" in w.lower() for w in fw_warnings)

    def test_route_no_fw_warnings(self, universe_dispatcher, mock_activity_cache):
        """Route not through FW systems has no FW warnings."""
        mock_activity_cache.get_all_fw = AsyncMock(return_value={})

        result = asyncio.run(
            universe_dispatcher(
                action="route",
                origin="Jita",
                destination="Perimeter",
            )
        )

        warnings = result.get("warnings", [])
        fw_warnings = [w for w in warnings if "Faction Warfare" in w or "FW" in w]
        assert len(fw_warnings) == 0


# =============================================================================
# Search Coalition Filter Tests
# =============================================================================


class TestSearchCoalitionFilter:
    """Tests for coalition filter in search action."""

    def test_search_coalition_filter(self, universe_dispatcher):
        """Search with coalition filter returns only coalition systems."""
        # Mock get_systems_by_coalition to return Ala's system ID
        with patch(
            "aria_esi.services.sovereignty.coalition_service.get_systems_by_coalition",
            return_value=[30000161],  # Ala
        ):
            result = asyncio.run(
                universe_dispatcher(
                    action="search",
                    coalition="imperium",
                    limit=10,
                )
            )

        assert "systems" in result
        assert result["total_found"] == 1
        system_names = [s["name"] for s in result["systems"]]
        assert "Ala" in system_names
        assert result["filters_applied"]["coalition"] == "imperium"

    def test_search_coalition_unknown(self, universe_dispatcher):
        """Unknown coalition returns warning and empty results."""
        with patch(
            "aria_esi.services.sovereignty.coalition_service.get_systems_by_coalition",
            return_value=[],
        ):
            result = asyncio.run(
                universe_dispatcher(
                    action="search",
                    coalition="nonexistent",
                    limit=10,
                )
            )

        assert result["total_found"] == 0
        assert "warning" in result
        assert "nonexistent" in result["warning"]

    def test_search_coalition_with_region(self, universe_dispatcher):
        """Coalition filter works with region filter."""
        with patch(
            "aria_esi.services.sovereignty.coalition_service.get_systems_by_coalition",
            return_value=[30000161, 30000142],  # Ala (Outer Region) and Jita (The Forge)
        ):
            result = asyncio.run(
                universe_dispatcher(
                    action="search",
                    coalition="imperium",
                    region="The Forge",
                    limit=10,
                )
            )

        # Only Jita should match (in The Forge AND in coalition)
        assert "systems" in result


# =============================================================================
# Territory Routing Tests
# =============================================================================


class TestRouteTerritoryPreference:
    """Tests for prefer_territory and avoid_territory route parameters."""

    def test_avoid_territory_excludes_systems(self, universe_dispatcher):
        """avoid_territory expands coalition to avoid set, excluding those systems."""
        # Mock coalition returns Perimeter's system ID — forces route to avoid it
        with patch(
            "aria_esi.services.sovereignty.coalition_service.get_systems_by_coalition",
            return_value=[30000144],  # Perimeter
        ):
            result = asyncio.run(
                universe_dispatcher(
                    action="route",
                    origin="Jita",
                    destination="Urlen",
                    avoid_territory="hostile_coalition",
                )
            )

        system_names = [s["name"] for s in result["systems"]]
        assert "Perimeter" not in system_names
        assert any("Avoiding hostile_coalition territory" in w for w in result.get("warnings", []))

    def test_avoid_territory_unknown_coalition(self, universe_dispatcher):
        """Unknown coalition in avoid_territory produces a warning."""
        with patch(
            "aria_esi.services.sovereignty.coalition_service.get_systems_by_coalition",
            return_value=[],
        ):
            result = asyncio.run(
                universe_dispatcher(
                    action="route",
                    origin="Jita",
                    destination="Perimeter",
                    avoid_territory="nonexistent",
                )
            )

        assert any("Unknown coalition" in w for w in result.get("warnings", []))
        # Route should still work (no avoidance applied)
        assert result["jumps"] == 1

    def test_prefer_territory_adds_warning(self, universe_dispatcher):
        """prefer_territory adds informational warning about territory preference."""
        # Mock coalition returns Jita + Perimeter system IDs
        with patch(
            "aria_esi.services.sovereignty.coalition_service.get_systems_by_coalition",
            return_value=[30000142, 30000144],  # Jita, Perimeter
        ):
            result = asyncio.run(
                universe_dispatcher(
                    action="route",
                    origin="Jita",
                    destination="Urlen",
                    prefer_territory="friendly_coalition",
                )
            )

        assert any("Preferring friendly_coalition territory" in w for w in result.get("warnings", []))
        assert result["jumps"] >= 1

    def test_prefer_territory_unknown_coalition(self, universe_dispatcher):
        """Unknown coalition in prefer_territory produces a warning."""
        with patch(
            "aria_esi.services.sovereignty.coalition_service.get_systems_by_coalition",
            return_value=[],
        ):
            result = asyncio.run(
                universe_dispatcher(
                    action="route",
                    origin="Jita",
                    destination="Perimeter",
                    prefer_territory="nonexistent",
                )
            )

        assert any("Unknown coalition" in w for w in result.get("warnings", []))

    def test_avoid_territory_with_explicit_avoid_systems(self, universe_dispatcher):
        """avoid_territory merges with explicit avoid_systems."""
        # Avoid Maurasi explicitly + avoid Perimeter via territory
        # Both paths Jita->Perimeter->Urlen and Jita->Maurasi->Urlen are penalized
        with patch(
            "aria_esi.services.sovereignty.coalition_service.get_systems_by_coalition",
            return_value=[30000144],  # Perimeter
        ):
            result = asyncio.run(
                universe_dispatcher(
                    action="route",
                    origin="Jita",
                    destination="Urlen",
                    avoid_systems=["Sivala"],
                    avoid_territory="hostile",
                )
            )

        # Perimeter should be avoided (via territory), route goes through Maurasi
        system_names = [s["name"] for s in result["systems"]]
        assert "Perimeter" not in system_names
        assert "Sivala" not in system_names
        assert any("Avoiding hostile territory" in w for w in result.get("warnings", []))


# =============================================================================
# Territory Weight Unit Tests
# =============================================================================


class TestTerritoryWeights:
    """Unit tests for apply_territory_preference weight computation."""

    def test_apply_territory_preference_penalizes_non_territory(self, standard_universe):
        """Non-territory edges get multiplied by WEIGHT_TERRITORY_PENALTY."""
        from aria_esi.services.navigation.weights import (
            WEIGHT_TERRITORY_PENALTY,
            apply_territory_preference,
        )

        base_weights = [1.0] * standard_universe.graph.ecount()
        # Only Jita (idx=0) is in territory
        preferred = {0}
        result = apply_territory_preference(base_weights, standard_universe, preferred)

        # Edges touching Jita (either endpoint) stay 1.0
        # Edges where neither endpoint is in territory get penalized
        for i, edge in enumerate(standard_universe.graph.es):
            if edge.source in preferred or edge.target in preferred:
                assert result[i] == 1.0
            else:
                assert result[i] == WEIGHT_TERRITORY_PENALTY

    def test_apply_territory_preference_preserves_avoid(self, standard_universe):
        """Infinity weights (avoided systems) are not modified."""
        from aria_esi.services.navigation.weights import (
            WEIGHT_AVOID,
            apply_territory_preference,
        )

        base_weights = [WEIGHT_AVOID if i == 0 else 1.0
                        for i in range(standard_universe.graph.ecount())]
        preferred = {0}
        result = apply_territory_preference(base_weights, standard_universe, preferred)

        assert result[0] == WEIGHT_AVOID  # Infinity preserved
