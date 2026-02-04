"""Tests for MCP dispatcher parameter validation."""

import pytest

from aria_esi.mcp.validation import (
    FITTING_ACTION_PARAMS,
    MARKET_ACTION_PARAMS,
    SDE_ACTION_PARAMS,
    SKILLS_ACTION_PARAMS,
    UNIVERSE_ACTION_PARAMS,
    add_validation_warnings,
    get_default_values,
    validate_action_params,
)


class TestParameterSchemas:
    """Test that parameter schemas are complete and valid."""

    def test_universe_schema_has_all_actions(self):
        """Verify universe schema covers all documented actions."""
        expected_actions = {
            "route",
            "systems",
            "borders",
            "search",
            "loop",
            "analyze",
            "nearest",
            "optimize_waypoints",
            "activity",
            "hotspots",
            "gatecamp_risk",
            "fw_frontlines",
            "local_area",
        }
        assert set(UNIVERSE_ACTION_PARAMS.keys()) == expected_actions

    def test_market_schema_has_all_actions(self):
        """Verify market schema covers all documented actions."""
        expected_actions = {
            "prices",
            "orders",
            "valuation",
            "spread",
            "history",
            "find_nearby",
            "npc_sources",
            "arbitrage_scan",
            "arbitrage_detail",
            "route_value",
            "watchlist_create",
            "watchlist_add_item",
            "watchlist_list",
            "watchlist_get",
            "watchlist_delete",
            "scope_create",
            "scope_list",
            "scope_delete",
            "scope_refresh",
        }
        assert set(MARKET_ACTION_PARAMS.keys()) == expected_actions

    def test_sde_schema_has_all_actions(self):
        """Verify SDE schema covers all documented actions."""
        expected_actions = {
            "item_info",
            "blueprint_info",
            "search",
            "skill_requirements",
            "corporation_info",
            "agent_search",
            "agent_divisions",
            "cache_status",
        }
        assert set(SDE_ACTION_PARAMS.keys()) == expected_actions

    def test_skills_schema_has_all_actions(self):
        """Verify skills schema covers all documented actions."""
        expected_actions = {
            "training_time",
            "easy_80_plan",
            "get_multipliers",
            "get_breakpoints",
            "t2_requirements",
            "activity_plan",
            "activity_list",
            "activity_search",
            "activity_compare",
        }
        assert set(SKILLS_ACTION_PARAMS.keys()) == expected_actions

    def test_fitting_schema_has_all_actions(self):
        """Verify fitting schema covers all documented actions."""
        expected_actions = {
            "calculate_stats",
            "check_requirements",
            "extract_requirements",
        }
        assert set(FITTING_ACTION_PARAMS.keys()) == expected_actions


class TestValidateActionParams:
    """Test validate_action_params function."""

    def test_valid_params_returns_empty(self):
        """Valid parameters should return no warnings."""
        warnings = validate_action_params(
            "universe",
            "route",
            {"origin": "Jita", "destination": "Amarr", "mode": "safe"},
        )
        assert warnings == []

    def test_irrelevant_param_returns_warning(self):
        """Irrelevant parameters should generate warnings."""
        warnings = validate_action_params(
            "universe",
            "route",
            {
                "origin": "Jita",
                "destination": "Amarr",
                "mode": "safe",
                "security_min": 0.5,  # Not used by route action
            },
        )
        assert len(warnings) == 1
        assert "security_min" in warnings[0]
        assert "route" in warnings[0]

    def test_none_values_ignored(self):
        """None values should not trigger warnings."""
        warnings = validate_action_params(
            "universe",
            "route",
            {
                "origin": "Jita",
                "destination": "Amarr",
                "mode": "safe",
                "security_min": None,  # None should be ignored
                "security_max": None,
            },
        )
        assert warnings == []

    def test_default_values_ignored(self):
        """Default values should not trigger warnings."""
        warnings = validate_action_params(
            "universe",
            "route",
            {
                "origin": "Jita",
                "destination": "Amarr",
                "mode": "shortest",  # Default value
                "limit": 20,  # Default value (not used by route, but default)
            },
        )
        assert warnings == []

    def test_multiple_irrelevant_params(self):
        """Multiple irrelevant parameters should each generate a warning."""
        warnings = validate_action_params(
            "universe",
            "route",
            {
                "origin": "Jita",
                "destination": "Amarr",
                "mode": "safe",
                "security_min": 0.5,
                "activity_type": "jumps",  # Non-default value to trigger warning
                "faction": "caldari",
            },
        )
        assert len(warnings) == 3

    def test_unknown_dispatcher_returns_empty(self):
        """Unknown dispatcher should return empty warnings."""
        warnings = validate_action_params(
            "unknown_dispatcher",
            "some_action",
            {"param": "value"},
        )
        assert warnings == []

    def test_unknown_action_returns_empty(self):
        """Unknown action should return empty warnings (let dispatcher handle error)."""
        warnings = validate_action_params(
            "universe",
            "unknown_action",
            {"param": "value"},
        )
        assert warnings == []

    def test_market_prices_validation(self):
        """Test market prices action validation."""
        # Valid params
        warnings = validate_action_params(
            "market",
            "prices",
            {"items": ["Tritanium"], "region": "jita", "station_only": True},
        )
        assert warnings == []

        # Invalid param
        warnings = validate_action_params(
            "market",
            "prices",
            {"items": ["Tritanium"], "min_profit_pct": 10.0},  # Arbitrage param
        )
        assert len(warnings) == 1
        assert "min_profit_pct" in warnings[0]

    def test_sde_item_info_validation(self):
        """Test SDE item_info action validation."""
        # Valid params
        warnings = validate_action_params(
            "sde",
            "item_info",
            {"item": "Vexor"},
        )
        assert warnings == []

        # Invalid param
        warnings = validate_action_params(
            "sde",
            "item_info",
            {"item": "Vexor", "level": 4},  # Agent search param
        )
        assert len(warnings) == 1
        assert "level" in warnings[0]

    def test_fitting_calculate_stats_validation(self):
        """Test fitting calculate_stats action validation."""
        # Valid params
        warnings = validate_action_params(
            "fitting",
            "calculate_stats",
            {"eft": "[Vexor, Test]", "damage_profile": None, "use_pilot_skills": True},
        )
        assert warnings == []

        # Invalid param
        warnings = validate_action_params(
            "fitting",
            "calculate_stats",
            {"eft": "[Vexor, Test]", "pilot_skills": {}},  # check_requirements param
        )
        assert len(warnings) == 1
        assert "pilot_skills" in warnings[0]

    def test_strict_mode_raises_error(self):
        """Strict mode should raise an error for irrelevant params."""
        from aria_esi.mcp.errors import InvalidParameterError

        with pytest.raises(InvalidParameterError) as exc_info:
            validate_action_params(
                "universe",
                "route",
                {"origin": "Jita", "destination": "Amarr", "faction": "caldari"},
                strict=True,
            )

        assert "faction" in str(exc_info.value)


class TestAddValidationWarnings:
    """Test add_validation_warnings function."""

    def test_no_warnings_returns_unchanged(self):
        """No warnings should return result unchanged."""
        result = {"data": "value", "warnings": ["existing"]}
        output = add_validation_warnings(result, [])
        assert output == result
        assert output["warnings"] == ["existing"]

    def test_warnings_added_to_existing(self):
        """Warnings should be appended to existing warnings."""
        result = {"data": "value", "warnings": ["existing"]}
        output = add_validation_warnings(result, ["new warning"])
        assert output["warnings"] == ["existing", "new warning"]

    def test_warnings_create_list_if_missing(self):
        """Warnings should create list if none exists."""
        result = {"data": "value"}
        output = add_validation_warnings(result, ["warning1", "warning2"])
        assert output["warnings"] == ["warning1", "warning2"]

    def test_warnings_handle_non_list_warnings(self):
        """Warnings should handle non-list existing warnings."""
        result = {"data": "value", "warnings": "existing"}
        output = add_validation_warnings(result, ["new warning"])
        assert output["warnings"] == ["new warning"]


class TestGetDefaultValues:
    """Test get_default_values function."""

    def test_universe_defaults(self):
        """Test universe dispatcher defaults."""
        defaults = get_default_values("universe")
        assert defaults["mode"] == "shortest"
        assert defaults["limit"] == 20
        assert defaults["security_filter"] == "highsec"

    def test_market_defaults(self):
        """Test market dispatcher defaults."""
        defaults = get_default_values("market")
        assert defaults["region"] == "jita"
        assert defaults["station_only"] is True
        assert defaults["min_profit_pct"] == 5.0

    def test_unknown_dispatcher_returns_empty(self):
        """Unknown dispatcher should return empty defaults."""
        defaults = get_default_values("unknown")
        assert defaults == {}
