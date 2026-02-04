"""
Tests for MCP Dispatcher Functions.

Tests the unified dispatchers for universe, market, sde, skills, fitting, and status.
Focus on action validation, parameter validation, and dispatch logic.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aria_esi.mcp.errors import InvalidParameterError
from aria_esi.mcp.policy import PolicyEngine

# =============================================================================
# Universe Dispatcher Tests
# =============================================================================


class TestUniverseDispatcher:
    """Tests for universe dispatcher action validation and dispatch."""

    @pytest.fixture
    def mock_universe(self, standard_universe):
        """Use standard_universe from conftest."""
        return standard_universe

    @pytest.fixture
    def universe_dispatcher(self, mock_universe):
        """Create dispatcher with mock server."""
        from aria_esi.mcp.dispatchers.universe import register_universe_dispatcher
        from aria_esi.mcp.tools import register_tools

        mock_server = MagicMock()
        captured_func = None

        def mock_tool():
            def decorator(func):
                nonlocal captured_func
                captured_func = func
                return func
            return decorator

        mock_server.tool = mock_tool
        register_tools(mock_server, mock_universe)
        register_universe_dispatcher(mock_server, mock_universe)
        return captured_func

    def test_invalid_action_raises_error(self, universe_dispatcher):
        """Invalid action parameter raises InvalidParameterError."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(universe_dispatcher(action="invalid_action"))

        assert "action" in str(exc.value).lower()
        assert "must be one of" in str(exc.value).lower()

    def test_route_requires_origin(self, universe_dispatcher):
        """Route action requires origin parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(universe_dispatcher(action="route", destination="Jita"))

        assert "origin" in str(exc.value).lower()

    def test_route_requires_destination(self, universe_dispatcher):
        """Route action requires destination parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(universe_dispatcher(action="route", origin="Jita"))

        assert "destination" in str(exc.value).lower()

    def test_route_basic_execution(self, universe_dispatcher):
        """Route action executes successfully with valid parameters."""
        result = asyncio.run(
            universe_dispatcher(action="route", origin="Jita", destination="Perimeter")
        )

        assert "origin" in result or "route" in result
        assert isinstance(result, dict)

    def test_systems_requires_systems_param(self, universe_dispatcher):
        """Systems action requires systems parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(universe_dispatcher(action="systems"))

        assert "systems" in str(exc.value).lower()

    def test_systems_basic_execution(self, universe_dispatcher):
        """Systems action executes successfully."""
        result = asyncio.run(
            universe_dispatcher(action="systems", systems=["Jita", "Perimeter"])
        )

        assert "systems" in result
        assert isinstance(result, dict)

    def test_borders_requires_origin(self, universe_dispatcher):
        """Borders action requires origin parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(universe_dispatcher(action="borders"))

        assert "origin" in str(exc.value).lower()

    def test_borders_basic_execution(self, universe_dispatcher):
        """Borders action executes successfully."""
        result = asyncio.run(
            universe_dispatcher(action="borders", origin="Maurasi")
        )

        assert isinstance(result, dict)

    def test_analyze_requires_minimum_systems(self, universe_dispatcher):
        """Analyze action requires at least 2 systems."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(universe_dispatcher(action="analyze", systems=["Jita"]))

        assert "2 systems" in str(exc.value).lower()

    def test_analyze_basic_execution(self, universe_dispatcher):
        """Analyze action executes successfully."""
        result = asyncio.run(
            universe_dispatcher(action="analyze", systems=["Jita", "Perimeter", "Urlen"])
        )

        assert isinstance(result, dict)

    def test_loop_requires_origin(self, universe_dispatcher):
        """Loop action requires origin parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(universe_dispatcher(action="loop"))

        assert "origin" in str(exc.value).lower()

    def test_nearest_requires_origin(self, universe_dispatcher):
        """Nearest action requires origin parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(universe_dispatcher(action="nearest"))

        assert "origin" in str(exc.value).lower()

    def test_optimize_waypoints_requires_waypoints(self, universe_dispatcher):
        """Optimize waypoints action requires waypoints parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(universe_dispatcher(action="optimize_waypoints"))

        assert "waypoints" in str(exc.value).lower()

    def test_activity_requires_systems(self, universe_dispatcher):
        """Activity action requires systems parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(universe_dispatcher(action="activity"))

        assert "systems" in str(exc.value).lower()

    def test_hotspots_requires_origin(self, universe_dispatcher):
        """Hotspots action requires origin parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(universe_dispatcher(action="hotspots"))

        assert "origin" in str(exc.value).lower()


# =============================================================================
# Market Dispatcher Tests
# =============================================================================


class TestMarketDispatcher:
    """Tests for market dispatcher action validation."""

    @pytest.fixture
    def market_dispatcher(self, standard_universe):
        """Create market dispatcher with mock server."""
        from aria_esi.mcp.dispatchers.market import register_market_dispatcher

        mock_server = MagicMock()
        captured_func = None

        def mock_tool():
            def decorator(func):
                nonlocal captured_func
                captured_func = func
                return func
            return decorator

        mock_server.tool = mock_tool
        register_market_dispatcher(mock_server, standard_universe)
        return captured_func

    def test_invalid_action_raises_error(self, market_dispatcher):
        """Invalid action parameter raises InvalidParameterError."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(market_dispatcher(action="invalid_action"))

        assert "action" in str(exc.value)

    def test_prices_requires_items(self, market_dispatcher):
        """Prices action requires items parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(market_dispatcher(action="prices"))

        assert "items" in str(exc.value).lower()

    def test_orders_requires_item(self, market_dispatcher):
        """Orders action requires item parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(market_dispatcher(action="orders"))

        assert "item" in str(exc.value).lower()

    def test_valuation_requires_items(self, market_dispatcher):
        """Valuation action requires items parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(market_dispatcher(action="valuation"))

        assert "items" in str(exc.value).lower()

    def test_spread_requires_items(self, market_dispatcher):
        """Spread action requires items parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(market_dispatcher(action="spread"))

        assert "items" in str(exc.value).lower()

    def test_history_requires_item(self, market_dispatcher):
        """History action requires item parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(market_dispatcher(action="history"))

        assert "item" in str(exc.value).lower()

    def test_find_nearby_requires_item_and_origin(self, market_dispatcher):
        """Find nearby action requires item and origin parameters."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(market_dispatcher(action="find_nearby"))

        # Should complain about missing item first
        assert "item" in str(exc.value).lower()

    def test_npc_sources_requires_item(self, market_dispatcher):
        """NPC sources action requires item parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(market_dispatcher(action="npc_sources"))

        assert "item" in str(exc.value).lower()

    def test_arbitrage_detail_requires_params(self, market_dispatcher):
        """Arbitrage detail action requires type_name, buy_region, sell_region."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(market_dispatcher(action="arbitrage_detail"))

        assert "type_name" in str(exc.value).lower()

    def test_route_value_requires_items_and_route(self, market_dispatcher):
        """Route value action requires items and route parameters."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(market_dispatcher(action="route_value"))

        assert "items" in str(exc.value).lower()

    def test_watchlist_create_requires_name(self, market_dispatcher):
        """Watchlist create action requires name parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(market_dispatcher(action="watchlist_create"))

        assert "name" in str(exc.value).lower()

    def test_watchlist_add_item_requires_params(self, market_dispatcher):
        """Watchlist add item action requires watchlist_name and item_name."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(market_dispatcher(action="watchlist_add_item"))

        assert "watchlist_name" in str(exc.value).lower()

    def test_watchlist_get_requires_name(self, market_dispatcher):
        """Watchlist get action requires name parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(market_dispatcher(action="watchlist_get"))

        assert "name" in str(exc.value).lower()

    def test_watchlist_delete_requires_name(self, market_dispatcher):
        """Watchlist delete action requires name parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(market_dispatcher(action="watchlist_delete"))

        assert "name" in str(exc.value).lower()

    def test_scope_create_requires_params(self, market_dispatcher):
        """Scope create action requires name, scope_type, location_id, watchlist_name."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(market_dispatcher(action="scope_create"))

        assert "name" in str(exc.value).lower()

    def test_scope_delete_requires_name(self, market_dispatcher):
        """Scope delete action requires name parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(market_dispatcher(action="scope_delete"))

        assert "name" in str(exc.value).lower()

    def test_scope_refresh_requires_scope_name(self, market_dispatcher):
        """Scope refresh action requires scope_name parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(market_dispatcher(action="scope_refresh"))

        assert "scope_name" in str(exc.value).lower()


# =============================================================================
# SDE Dispatcher Tests
# =============================================================================


class TestSDEDispatcher:
    """Tests for SDE dispatcher action validation."""

    @pytest.fixture
    def sde_dispatcher(self, standard_universe):
        """Create SDE dispatcher with mock server."""
        from aria_esi.mcp.dispatchers.sde import register_sde_dispatcher

        mock_server = MagicMock()
        captured_func = None

        def mock_tool():
            def decorator(func):
                nonlocal captured_func
                captured_func = func
                return func
            return decorator

        mock_server.tool = mock_tool
        register_sde_dispatcher(mock_server, standard_universe)
        return captured_func

    def test_invalid_action_raises_error(self, sde_dispatcher):
        """Invalid action parameter raises InvalidParameterError."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(sde_dispatcher(action="invalid_action"))

        assert "action" in str(exc.value)

    def test_item_info_requires_item(self, sde_dispatcher):
        """Item info action requires item parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(sde_dispatcher(action="item_info"))

        assert "item" in str(exc.value).lower()

    def test_blueprint_info_requires_item(self, sde_dispatcher):
        """Blueprint info action requires item parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(sde_dispatcher(action="blueprint_info"))

        assert "item" in str(exc.value).lower()

    def test_search_requires_query(self, sde_dispatcher):
        """Search action requires query parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(sde_dispatcher(action="search"))

        assert "query" in str(exc.value).lower()

    def test_skill_requirements_requires_item(self, sde_dispatcher):
        """Skill requirements action requires item parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(sde_dispatcher(action="skill_requirements"))

        assert "item" in str(exc.value).lower()

    def test_corporation_info_requires_id_or_name(self, sde_dispatcher):
        """Corporation info action requires corporation_id or corporation_name."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(sde_dispatcher(action="corporation_info"))

        assert "corporation" in str(exc.value).lower()


# =============================================================================
# Skills Dispatcher Tests
# =============================================================================


class TestSkillsDispatcher:
    """Tests for skills dispatcher action validation."""

    @pytest.fixture
    def skills_dispatcher(self, standard_universe):
        """Create skills dispatcher with mock server."""
        from aria_esi.mcp.dispatchers.skills import register_skills_dispatcher

        mock_server = MagicMock()
        captured_func = None

        def mock_tool():
            def decorator(func):
                nonlocal captured_func
                captured_func = func
                return func
            return decorator

        mock_server.tool = mock_tool
        register_skills_dispatcher(mock_server, standard_universe)
        return captured_func

    def test_invalid_action_raises_error(self, skills_dispatcher):
        """Invalid action parameter raises InvalidParameterError."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(skills_dispatcher(action="invalid_action"))

        assert "action" in str(exc.value)

    def test_training_time_requires_skill_list(self, skills_dispatcher):
        """Training time action requires skill_list parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(skills_dispatcher(action="training_time"))

        assert "skill_list" in str(exc.value).lower()

    def test_easy_80_plan_requires_item(self, skills_dispatcher):
        """Easy 80 plan action requires item parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(skills_dispatcher(action="easy_80_plan"))

        assert "item" in str(exc.value).lower()

    def test_t2_requirements_requires_item(self, skills_dispatcher):
        """T2 requirements action requires item parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(skills_dispatcher(action="t2_requirements"))

        assert "item" in str(exc.value).lower()

    def test_activity_plan_requires_activity(self, skills_dispatcher):
        """Activity plan action requires activity parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(skills_dispatcher(action="activity_plan"))

        assert "activity" in str(exc.value).lower()

    def test_activity_search_requires_query(self, skills_dispatcher):
        """Activity search action requires query parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(skills_dispatcher(action="activity_search"))

        assert "query" in str(exc.value).lower()

    def test_activity_compare_requires_activity(self, skills_dispatcher):
        """Activity compare action requires activity parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(skills_dispatcher(action="activity_compare"))

        assert "activity" in str(exc.value).lower()


# =============================================================================
# Fitting Dispatcher Tests
# =============================================================================


class TestFittingDispatcher:
    """Tests for fitting dispatcher action validation."""

    @pytest.fixture(autouse=True)
    def reset_policy_singleton(self):
        """Reset policy singleton between tests."""
        PolicyEngine.reset_instance()
        yield
        PolicyEngine.reset_instance()

    @pytest.fixture
    def fitting_dispatcher(self, standard_universe):
        """Create fitting dispatcher with mock server."""
        from aria_esi.mcp.dispatchers.fitting import register_fitting_dispatcher

        mock_server = MagicMock()
        captured_func = None

        def mock_tool():
            def decorator(func):
                nonlocal captured_func
                captured_func = func
                return func
            return decorator

        mock_server.tool = mock_tool
        register_fitting_dispatcher(mock_server, standard_universe)
        return captured_func

    def test_invalid_action_raises_error(self, fitting_dispatcher):
        """Invalid action parameter raises InvalidParameterError."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(fitting_dispatcher(action="invalid_action"))

        assert "action" in str(exc.value)

    def test_calculate_stats_requires_eft(self, fitting_dispatcher):
        """Calculate stats action requires eft parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(fitting_dispatcher(action="calculate_stats"))

        assert "eft" in str(exc.value).lower()

    def test_calculate_stats_falls_back_when_authenticated_denied(self, fitting_dispatcher):
        """When policy denies authenticated, falls back to all-V with warning."""
        from aria_esi.mcp.policy import PolicyConfig, PolicyEngine, SensitivityLevel

        # Configure policy to deny authenticated
        engine = PolicyEngine.get_instance()
        engine.config = PolicyConfig(
            allowed_levels={SensitivityLevel.PUBLIC, SensitivityLevel.AGGREGATE, SensitivityLevel.MARKET}
        )

        # Mock the underlying calculation to avoid needing EOS data
        mock_result = {
            "ship": {"name": "Vexor", "fit_name": "Test"},
            "dps": {"total": 100},
            "tank": {"ehp": {"total": 10000}},
            "metadata": {},
        }

        with patch(
            "aria_esi.mcp.dispatchers.fitting._calculate_stats",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_calc:
            result = asyncio.run(
                fitting_dispatcher(
                    action="calculate_stats",
                    eft="[Vexor, Test]\nDrone Damage Amplifier I",
                    use_pilot_skills=True,  # Request pilot skills
                )
            )

            # Should have called with use_pilot_skills=False (fallback)
            mock_calc.assert_called_once()
            call_args = mock_calc.call_args
            assert call_args[0][2] is False  # use_pilot_skills arg should be False

            # Result should contain policy warning
            assert "metadata" in result
            assert "warnings" in result["metadata"]
            assert any("authenticated not allowed" in w for w in result["metadata"]["warnings"])


# =============================================================================
# Status Tool Tests
# =============================================================================


class TestStatusTool:
    """Tests for status tool."""

    @pytest.fixture
    def status_tool(self):
        """Create status tool with mock server."""
        from aria_esi.mcp.dispatchers.status import register_status_tool

        mock_server = MagicMock()
        captured_func = None

        def mock_tool():
            def decorator(func):
                nonlocal captured_func
                captured_func = func
                return func
            return decorator

        mock_server.tool = mock_tool
        register_status_tool(mock_server)
        return captured_func

    def test_status_returns_dict(self, status_tool):
        """Status tool returns a dictionary with expected keys."""
        # Mock internal dependencies - patch at the import location
        with patch("aria_esi.mcp.activity.get_activity_cache") as mock_activity, \
             patch("aria_esi.mcp.market.cache.get_market_cache") as mock_market, \
             patch("aria_esi.mcp.market.database.get_market_database") as mock_db, \
             patch("aria_esi.fitting.get_eos_data_manager") as mock_eos:

            # Setup activity cache mock
            mock_activity_cache = MagicMock()
            mock_activity_cache.get_cache_status.return_value = {
                "kills": {"cached_systems": 100, "age_seconds": 60, "ttl_seconds": 300, "stale": False},
                "jumps": {"cached_systems": 100, "age_seconds": 60, "ttl_seconds": 300, "stale": False},
                "fw": {"cached_systems": 50, "age_seconds": 60, "ttl_seconds": 300, "stale": False},
            }
            mock_activity.return_value = mock_activity_cache

            # Setup market cache mock
            mock_market_cache = MagicMock()
            mock_market_cache.get_cache_status.return_value = {
                "fuzzwork": {"cached_types": 100, "age_seconds": 30, "ttl_seconds": 900, "stale": False},
                "esi_orders": {"cached_types": 50, "age_seconds": 30, "ttl_seconds": 300, "stale": False},
            }
            mock_market.return_value = mock_market_cache

            # Setup market database mock
            mock_db_instance = MagicMock()
            mock_db_instance.get_stats.return_value = {
                "database_path": "/tmp/test.db",
                "database_size_mb": 10.5,
                "type_count": 45000,
            }
            mock_db.return_value = mock_db_instance

            # Setup EOS data manager mock
            mock_eos_instance = MagicMock()
            mock_validation = MagicMock()
            mock_validation.is_valid = True
            mock_validation.data_path = "/tmp/eos"
            mock_validation.version = "1.0"
            mock_validation.total_records = 45000
            mock_validation.missing_files = []
            mock_eos_instance.validate.return_value = mock_validation
            mock_eos.return_value = mock_eos_instance

            result = asyncio.run(status_tool())

            assert isinstance(result, dict)
            assert "activity" in result
            assert "market" in result
            assert "sde" in result
            assert "fitting" in result
            assert "summary" in result

    def test_status_handles_activity_cache_error(self, status_tool):
        """Status tool handles activity cache errors gracefully."""
        with patch("aria_esi.mcp.activity.get_activity_cache") as mock_activity, \
             patch("aria_esi.mcp.market.cache.get_market_cache") as mock_market, \
             patch("aria_esi.mcp.market.database.get_market_database") as mock_db, \
             patch("aria_esi.fitting.get_eos_data_manager") as mock_eos:

            # Simulate activity cache error
            mock_activity.side_effect = Exception("Activity cache unavailable")

            # Setup other mocks
            mock_market_cache = MagicMock()
            mock_market_cache.get_cache_status.return_value = {}
            mock_market.return_value = mock_market_cache

            mock_db_instance = MagicMock()
            mock_db_instance.get_stats.return_value = {"type_count": 0}
            mock_db.return_value = mock_db_instance

            mock_eos_instance = MagicMock()
            mock_validation = MagicMock()
            mock_validation.is_valid = False
            mock_validation.data_path = None
            mock_validation.version = None
            mock_validation.total_records = 0
            mock_validation.missing_files = ["types.json"]
            mock_eos_instance.validate.return_value = mock_validation
            mock_eos.return_value = mock_eos_instance

            result = asyncio.run(status_tool())

            assert isinstance(result, dict)
            assert "error" in result.get("activity", {})
            assert "Activity cache unavailable" in result["summary"]["issues"]


# =============================================================================
# Dispatcher Registration Tests
# =============================================================================


class TestDispatcherRegistration:
    """Test that all dispatchers can be registered without errors."""

    def test_universe_dispatcher_registers(self, standard_universe):
        """Universe dispatcher registers without error."""
        from aria_esi.mcp.dispatchers.universe import register_universe_dispatcher

        mock_server = MagicMock()
        # Should not raise
        register_universe_dispatcher(mock_server, standard_universe)
        mock_server.tool.assert_called()

    def test_market_dispatcher_registers(self, standard_universe):
        """Market dispatcher registers without error."""
        from aria_esi.mcp.dispatchers.market import register_market_dispatcher

        mock_server = MagicMock()
        register_market_dispatcher(mock_server, standard_universe)
        mock_server.tool.assert_called()

    def test_sde_dispatcher_registers(self, standard_universe):
        """SDE dispatcher registers without error."""
        from aria_esi.mcp.dispatchers.sde import register_sde_dispatcher

        mock_server = MagicMock()
        register_sde_dispatcher(mock_server, standard_universe)
        mock_server.tool.assert_called()

    def test_skills_dispatcher_registers(self, standard_universe):
        """Skills dispatcher registers without error."""
        from aria_esi.mcp.dispatchers.skills import register_skills_dispatcher

        mock_server = MagicMock()
        register_skills_dispatcher(mock_server, standard_universe)
        mock_server.tool.assert_called()

    def test_fitting_dispatcher_registers(self, standard_universe):
        """Fitting dispatcher registers without error."""
        from aria_esi.mcp.dispatchers.fitting import register_fitting_dispatcher

        mock_server = MagicMock()
        register_fitting_dispatcher(mock_server, standard_universe)
        mock_server.tool.assert_called()

    def test_status_tool_registers(self):
        """Status tool registers without error."""
        from aria_esi.mcp.dispatchers.status import register_status_tool

        mock_server = MagicMock()
        register_status_tool(mock_server)
        mock_server.tool.assert_called()
