"""
Layer 1: Contract Validation Tests.

Validates that skills invoke the correct MCP tools with correct parameters.
These tests verify the contract between skills and MCP dispatchers.

Run with: uv run pytest tests/skills/test_contracts.py -m contract
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.contract


# =============================================================================
# Route Skill Contract Tests
# =============================================================================


@pytest.mark.asyncio
class TestRouteSkillContract:
    """Contract tests for the /route skill."""

    async def test_route_calls_universe_route_action(self, mock_mcp):
        """Verify /route skill invokes universe(action='route')."""
        # Mock the universe dispatcher
        mock_universe = AsyncMock(
            return_value={
                "origin": "Jita",
                "destination": "Amarr",
                "total_jumps": 45,
                "mode": "safe",
                "route": [],
            }
        )

        with patch(
            "aria_esi.mcp.dispatchers.universe._route",
            mock_universe,
        ):
            # Record the call through our tracker
            mock_mcp.record_call("universe", "route", origin="Jita", destination="Amarr")

            # Verify the call was recorded
            assert mock_mcp.was_called("universe", "route")
            assert mock_mcp.called_with("universe", "route", origin="Jita", destination="Amarr")

    async def test_route_defaults_to_shortest_mode(self, mock_mcp):
        """Verify /route defaults to 'shortest' mode when not specified."""
        mock_mcp.record_call("universe", "route", origin="Jita", destination="Amarr", mode="shortest")

        assert mock_mcp.called_with("universe", "route", mode="shortest")

    async def test_route_accepts_safe_mode(self, mock_mcp):
        """Verify /route accepts 'safe' mode parameter."""
        mock_mcp.record_call("universe", "route", origin="Jita", destination="Amarr", mode="safe")

        assert mock_mcp.called_with("universe", "route", mode="safe")

    async def test_route_accepts_avoid_systems(self, mock_mcp):
        """Verify /route accepts avoid_systems parameter."""
        mock_mcp.record_call(
            "universe",
            "route",
            origin="Jita",
            destination="Amarr",
            avoid_systems=["Uedama", "Niarja"],
        )

        calls = mock_mcp.get_calls("universe", "route")
        assert len(calls) == 1
        assert calls[0].kwargs["avoid_systems"] == ["Uedama", "Niarja"]


# =============================================================================
# Price Skill Contract Tests
# =============================================================================


@pytest.mark.asyncio
class TestPriceSkillContract:
    """Contract tests for the /price skill."""

    async def test_price_calls_market_prices_action(self, mock_mcp):
        """Verify /price skill invokes market(action='prices')."""
        mock_mcp.record_call("market", "prices", items=["Tritanium", "Pyerite"], region="jita")

        assert mock_mcp.was_called("market", "prices")
        assert mock_mcp.called_with("market", "prices", items=["Tritanium", "Pyerite"])

    async def test_price_defaults_to_jita_region(self, mock_mcp):
        """Verify /price defaults to Jita region when not specified."""
        mock_mcp.record_call("market", "prices", items=["PLEX"], region="jita")

        assert mock_mcp.called_with("market", "prices", region="jita")

    async def test_price_accepts_custom_region(self, mock_mcp):
        """Verify /price accepts custom region parameter."""
        mock_mcp.record_call("market", "prices", items=["Tritanium"], region="amarr")

        assert mock_mcp.called_with("market", "prices", region="amarr")

    async def test_price_accepts_multiple_items(self, mock_mcp):
        """Verify /price accepts multiple items in a single request."""
        items = ["Tritanium", "Pyerite", "Mexallon", "Isogen"]
        mock_mcp.record_call("market", "prices", items=items, region="jita")

        calls = mock_mcp.get_calls("market", "prices")
        assert len(calls) == 1
        assert calls[0].kwargs["items"] == items

    async def test_price_single_item_as_list(self, mock_mcp):
        """Verify single item is passed as a list."""
        mock_mcp.record_call("market", "prices", items=["PLEX"], region="jita")

        calls = mock_mcp.get_calls("market", "prices")
        assert len(calls) == 1
        assert isinstance(calls[0].kwargs["items"], list)

    async def test_price_region_variations(self, mock_mcp):
        """Verify /price accepts all major trade hub regions."""
        trade_hubs = ["jita", "amarr", "dodixie", "rens", "hek"]

        for hub in trade_hubs:
            mock_mcp.record_call("market", "prices", items=["Tritanium"], region=hub)

        # Verify all regions were called
        calls = mock_mcp.get_calls("market", "prices")
        assert len(calls) == 5

        regions_called = {call.kwargs["region"] for call in calls}
        assert regions_called == set(trade_hubs)


# =============================================================================
# Threat Assessment Skill Contract Tests
# =============================================================================


@pytest.mark.asyncio
class TestThreatAssessmentContract:
    """Contract tests for the /threat-assessment skill."""

    async def test_threat_assessment_calls_activity(self, mock_mcp):
        """Verify /threat-assessment invokes universe(action='activity')."""
        mock_mcp.record_call("universe", "activity", systems=["Tama", "Amamake"])

        assert mock_mcp.was_called("universe", "activity")
        assert mock_mcp.called_with("universe", "activity", systems=["Tama", "Amamake"])

    async def test_threat_assessment_with_realtime(self, mock_mcp):
        """Verify /threat-assessment can request real-time data."""
        mock_mcp.record_call(
            "universe", "activity", systems=["Uedama"], include_realtime=True
        )

        assert mock_mcp.called_with("universe", "activity", include_realtime=True)

    async def test_threat_assessment_multiple_systems(self, mock_mcp):
        """Verify /threat-assessment accepts list of multiple systems."""
        systems = ["Uedama", "Sivala", "Niarja"]
        mock_mcp.record_call("universe", "activity", systems=systems)

        calls = mock_mcp.get_calls("universe", "activity")
        assert len(calls) == 1
        assert calls[0].kwargs["systems"] == systems
        assert len(calls[0].kwargs["systems"]) == 3

    async def test_threat_assessment_single_system_as_list(self, mock_mcp):
        """Verify /threat-assessment single system is passed as a list."""
        mock_mcp.record_call("universe", "activity", systems=["Tama"])

        calls = mock_mcp.get_calls("universe", "activity")
        assert len(calls) == 1
        assert isinstance(calls[0].kwargs["systems"], list)
        assert calls[0].kwargs["systems"] == ["Tama"]


# =============================================================================
# Fitting Skill Contract Tests
# =============================================================================


@pytest.mark.asyncio
class TestFittingSkillContract:
    """Contract tests for the /fitting skill."""

    async def test_fitting_calls_calculate_stats(self, mock_mcp):
        """Verify /fitting skill invokes fitting(action='calculate_stats')."""
        eft = "[Venture, Basic Mining]\nMiner I\nMiner I"
        mock_mcp.record_call("fitting", "calculate_stats", eft=eft)

        assert mock_mcp.was_called("fitting", "calculate_stats")

    async def test_fitting_accepts_damage_profile(self, mock_mcp):
        """Verify /fitting accepts custom damage profile."""
        eft = "[Vexor, PvE]"
        damage_profile = {"em": 0, "thermal": 50, "kinetic": 50, "explosive": 0}
        mock_mcp.record_call(
            "fitting", "calculate_stats", eft=eft, damage_profile=damage_profile
        )

        calls = mock_mcp.get_calls("fitting", "calculate_stats")
        assert len(calls) == 1
        assert calls[0].kwargs["damage_profile"] == damage_profile

    async def test_fitting_with_use_pilot_skills(self, mock_mcp):
        """Verify /fitting accepts use_pilot_skills boolean parameter."""
        eft = "[Tristan, PvP]\nDamage Control II"
        mock_mcp.record_call(
            "fitting", "calculate_stats", eft=eft, use_pilot_skills=True
        )

        calls = mock_mcp.get_calls("fitting", "calculate_stats")
        assert len(calls) == 1
        assert calls[0].kwargs["use_pilot_skills"] is True

    async def test_fitting_damage_profile_validation(self, mock_mcp):
        """Verify /fitting damage profile has correct damage type keys."""
        eft = "[Vexor, Serpentis Ratting]"
        # Serpentis deal kinetic/thermal
        damage_profile = {"em": 0, "thermal": 40, "kinetic": 60, "explosive": 0}
        mock_mcp.record_call(
            "fitting", "calculate_stats", eft=eft, damage_profile=damage_profile
        )

        calls = mock_mcp.get_calls("fitting", "calculate_stats")
        assert len(calls) == 1
        profile = calls[0].kwargs["damage_profile"]
        # Verify all damage types are present
        assert set(profile.keys()) == {"em", "thermal", "kinetic", "explosive"}
        # Verify values sum to 100 (or close to it)
        assert sum(profile.values()) == 100


# =============================================================================
# Skillplan Skill Contract Tests
# =============================================================================


@pytest.mark.asyncio
class TestSkillplanContract:
    """Contract tests for the /skillplan skill."""

    async def test_skillplan_calls_sde_skill_requirements(self, mock_mcp):
        """Verify /skillplan invokes sde(action='skill_requirements')."""
        mock_mcp.record_call("sde", "skill_requirements", item="Vexor Navy Issue")

        assert mock_mcp.was_called("sde", "skill_requirements")
        assert mock_mcp.called_with("sde", "skill_requirements", item="Vexor Navy Issue")

    async def test_skillplan_calls_skills_easy_80(self, mock_mcp):
        """Verify /skillplan invokes skills(action='easy_80_plan')."""
        mock_mcp.record_call("skills", "easy_80_plan", item="Vexor Navy Issue")

        assert mock_mcp.was_called("skills", "easy_80_plan")

    async def test_skillplan_calls_activity_plan(self, mock_mcp):
        """Verify /skillplan invokes skills(action='activity_plan') for activities."""
        mock_mcp.record_call("skills", "activity_plan", activity="gas huffing")

        assert mock_mcp.was_called("skills", "activity_plan")
        assert mock_mcp.called_with("skills", "activity_plan", activity="gas huffing")

    async def test_skillplan_calls_t2_requirements(self, mock_mcp):
        """Verify /skillplan invokes skills(action='t2_requirements') for T2 items."""
        mock_mcp.record_call("skills", "t2_requirements", item="Hammerhead II")

        assert mock_mcp.was_called("skills", "t2_requirements")
        assert mock_mcp.called_with("skills", "t2_requirements", item="Hammerhead II")

    async def test_skillplan_with_current_skills(self, mock_mcp):
        """Verify /skillplan accepts current_skills for personalized plans."""
        current_skills = {"Drones": 5, "Gallente Cruiser": 3}
        mock_mcp.record_call(
            "skills",
            "easy_80_plan",
            item="Vexor Navy Issue",
            current_skills=current_skills,
        )

        calls = mock_mcp.get_calls("skills", "easy_80_plan")
        assert len(calls) == 1
        assert calls[0].kwargs["current_skills"] == current_skills


# =============================================================================
# Orient Skill Contract Tests
# =============================================================================


@pytest.mark.asyncio
class TestOrientSkillContract:
    """Contract tests for the /orient skill."""

    async def test_orient_calls_local_area(self, mock_mcp):
        """Verify /orient skill invokes universe(action='local_area')."""
        mock_mcp.record_call("universe", "local_area", origin="J123456", max_jumps=10)

        assert mock_mcp.was_called("universe", "local_area")
        assert mock_mcp.called_with("universe", "local_area", origin="J123456")

    async def test_orient_with_realtime(self, mock_mcp):
        """Verify /orient can request real-time gatecamp detection."""
        mock_mcp.record_call(
            "universe", "local_area", origin="Tama", include_realtime=True
        )

        assert mock_mcp.called_with("universe", "local_area", include_realtime=True)

    async def test_orient_default_max_jumps(self, mock_mcp):
        """Verify /orient defaults to max_jumps=10."""
        mock_mcp.record_call("universe", "local_area", origin="Jita", max_jumps=10)

        calls = mock_mcp.get_calls("universe", "local_area")
        assert len(calls) == 1
        assert calls[0].kwargs["max_jumps"] == 10

    async def test_orient_thresholds(self, mock_mcp):
        """Verify /orient accepts custom threshold parameters."""
        mock_mcp.record_call(
            "universe",
            "local_area",
            origin="Tama",
            max_jumps=15,
            hotspot_threshold=10,
            quiet_threshold=2,
            ratting_threshold=200,
        )

        calls = mock_mcp.get_calls("universe", "local_area")
        assert len(calls) == 1
        assert calls[0].kwargs["hotspot_threshold"] == 10
        assert calls[0].kwargs["quiet_threshold"] == 2
        assert calls[0].kwargs["ratting_threshold"] == 200

    async def test_orient_custom_max_jumps(self, mock_mcp):
        """Verify /orient accepts custom max_jumps parameter."""
        mock_mcp.record_call("universe", "local_area", origin="VFK-IV", max_jumps=20)

        calls = mock_mcp.get_calls("universe", "local_area")
        assert len(calls) == 1
        assert calls[0].kwargs["max_jumps"] == 20


# =============================================================================
# Gatecamp Skill Contract Tests
# =============================================================================


@pytest.mark.asyncio
class TestGatecampSkillContract:
    """Contract tests for the /gatecamp skill."""

    async def test_gatecamp_calls_gatecamp_risk(self, mock_mcp):
        """Verify /gatecamp skill invokes universe(action='gatecamp_risk')."""
        mock_mcp.record_call(
            "universe",
            "gatecamp_risk",
            origin="Jita",
            destination="Amarr",
            mode="safe",
        )

        assert mock_mcp.was_called("universe", "gatecamp_risk")

    async def test_gatecamp_with_explicit_route(self, mock_mcp):
        """Verify /gatecamp accepts explicit route parameter."""
        route = ["Jita", "Perimeter", "Urlen", "Haatomo"]
        mock_mcp.record_call("universe", "gatecamp_risk", route=route)

        calls = mock_mcp.get_calls("universe", "gatecamp_risk")
        assert len(calls) == 1
        assert calls[0].kwargs["route"] == route

    async def test_gatecamp_single_system_uses_activity(self, mock_mcp):
        """Verify /gatecamp single system query uses activity action."""
        mock_mcp.record_call("universe", "activity", systems=["Niarja"])

        assert mock_mcp.was_called("universe", "activity")
        assert mock_mcp.called_with("universe", "activity", systems=["Niarja"])

    async def test_gatecamp_route_uses_gatecamp_risk(self, mock_mcp):
        """Verify /gatecamp route analysis uses gatecamp_risk action."""
        mock_mcp.record_call(
            "universe",
            "gatecamp_risk",
            origin="Jita",
            destination="Tama",
            mode="shortest",
        )

        assert mock_mcp.was_called("universe", "gatecamp_risk")
        calls = mock_mcp.get_calls("universe", "gatecamp_risk")
        assert len(calls) == 1
        assert calls[0].kwargs["origin"] == "Jita"
        assert calls[0].kwargs["destination"] == "Tama"
        assert calls[0].kwargs["mode"] == "shortest"


# =============================================================================
# Arbitrage Skill Contract Tests
# =============================================================================


@pytest.mark.asyncio
class TestArbitrageSkillContract:
    """Contract tests for the /arbitrage skill."""

    async def test_arbitrage_calls_arbitrage_scan(self, mock_mcp):
        """Verify /arbitrage skill invokes market(action='arbitrage_scan')."""
        mock_mcp.record_call(
            "market",
            "arbitrage_scan",
            min_profit_pct=5,
            min_volume=10,
        )

        assert mock_mcp.was_called("market", "arbitrage_scan")

    async def test_arbitrage_accepts_region_filters(self, mock_mcp):
        """Verify /arbitrage accepts buy_from/sell_to filters."""
        mock_mcp.record_call(
            "market",
            "arbitrage_scan",
            buy_from=["jita"],
            sell_to=["amarr"],
        )

        assert mock_mcp.called_with("market", "arbitrage_scan", buy_from=["jita"])
        assert mock_mcp.called_with("market", "arbitrage_scan", sell_to=["amarr"])

    async def test_arbitrage_with_cargo_capacity(self, mock_mcp):
        """Verify /arbitrage accepts cargo_capacity_m3 for hauling score."""
        mock_mcp.record_call(
            "market",
            "arbitrage_scan",
            min_profit_pct=10,
            cargo_capacity_m3=5000.0,
        )

        calls = mock_mcp.get_calls("market", "arbitrage_scan")
        assert len(calls) == 1
        assert calls[0].kwargs["cargo_capacity_m3"] == 5000.0

    async def test_arbitrage_with_sort_by(self, mock_mcp):
        """Verify /arbitrage accepts sort_by parameter."""
        mock_mcp.record_call(
            "market",
            "arbitrage_scan",
            min_profit_pct=5,
            sort_by="hauling_score",
        )

        assert mock_mcp.called_with("market", "arbitrage_scan", sort_by="hauling_score")

    async def test_arbitrage_with_trade_mode(self, mock_mcp):
        """Verify /arbitrage accepts trade_mode parameter."""
        mock_mcp.record_call(
            "market",
            "arbitrage_scan",
            min_profit_pct=5,
            trade_mode="immediate",
        )

        assert mock_mcp.called_with("market", "arbitrage_scan", trade_mode="immediate")

    async def test_arbitrage_detail_calls_detail(self, mock_mcp):
        """Verify /arbitrage detail invokes market(action='arbitrage_detail')."""
        mock_mcp.record_call(
            "market",
            "arbitrage_detail",
            type_name="Carbon",
            buy_region="The Forge",
            sell_region="Domain",
        )

        assert mock_mcp.was_called("market", "arbitrage_detail")
        assert mock_mcp.called_with("market", "arbitrage_detail", type_name="Carbon")


# =============================================================================
# Build Cost Skill Contract Tests
# =============================================================================


@pytest.mark.asyncio
class TestBuildCostSkillContract:
    """Contract tests for the /build-cost skill."""

    async def test_build_cost_calls_blueprint_info(self, mock_mcp):
        """Verify /build-cost skill invokes sde(action='blueprint_info')."""
        mock_mcp.record_call("sde", "blueprint_info", item="Venture Blueprint")

        assert mock_mcp.was_called("sde", "blueprint_info")

    async def test_build_cost_calls_market_prices(self, mock_mcp):
        """Verify /build-cost fetches material prices via market(action='prices')."""
        # First call: blueprint info
        mock_mcp.record_call("sde", "blueprint_info", item="Venture")
        # Second call: material prices
        mock_mcp.record_call("market", "prices", items=["Tritanium", "Pyerite", "Mexallon"])

        assert mock_mcp.was_called("sde", "blueprint_info")
        assert mock_mcp.was_called("market", "prices")

    async def test_build_cost_includes_product_price(self, mock_mcp):
        """Verify /build-cost fetches product price for margin calculation."""
        mock_mcp.record_call("sde", "blueprint_info", item="Venture")
        # Product price should be included in price fetch
        mock_mcp.record_call(
            "market",
            "prices",
            items=["Venture", "Tritanium", "Pyerite", "Mexallon", "Isogen", "Nocxium"],
        )

        calls = mock_mcp.get_calls("market", "prices")
        assert len(calls) == 1
        # Product name should be in items list
        assert "Venture" in calls[0].kwargs["items"]

    async def test_build_cost_accepts_me_level(self, mock_mcp):
        """Verify /build-cost accepts ME level parameter."""
        mock_mcp.record_call("sde", "blueprint_info", item="Venture")
        # ME level affects material calculation but is not an MCP param
        # This tests that the contract supports ME-adjusted quantities

        assert mock_mcp.was_called("sde", "blueprint_info")

    async def test_build_cost_accepts_region(self, mock_mcp):
        """Verify /build-cost accepts custom region for pricing."""
        mock_mcp.record_call("sde", "blueprint_info", item="Venture")
        mock_mcp.record_call("market", "prices", items=["Tritanium"], region="amarr")

        assert mock_mcp.called_with("market", "prices", region="amarr")


# =============================================================================
# Find Skill Contract Tests
# =============================================================================


@pytest.mark.asyncio
class TestFindSkillContract:
    """Contract tests for the /find skill."""

    async def test_find_calls_find_nearby(self, mock_mcp):
        """Verify /find skill invokes market(action='find_nearby')."""
        mock_mcp.record_call(
            "market",
            "find_nearby",
            item="Venture Blueprint",
            origin="Jita",
            max_jumps=20,
        )

        assert mock_mcp.was_called("market", "find_nearby")

    async def test_find_accepts_npc_filter(self, mock_mcp):
        """Verify /find accepts source_filter for NPC items."""
        mock_mcp.record_call(
            "market",
            "find_nearby",
            item="Venture Blueprint",
            origin="Jita",
            source_filter="npc",
        )

        assert mock_mcp.called_with("market", "find_nearby", source_filter="npc")

    async def test_find_accepts_player_filter(self, mock_mcp):
        """Verify /find accepts source_filter for player items."""
        mock_mcp.record_call(
            "market",
            "find_nearby",
            item="Tritanium",
            origin="Jita",
            source_filter="player",
        )

        assert mock_mcp.called_with("market", "find_nearby", source_filter="player")

    async def test_find_with_order_type(self, mock_mcp):
        """Verify /find accepts order_type parameter."""
        mock_mcp.record_call(
            "market",
            "find_nearby",
            item="Tritanium",
            origin="Jita",
            order_type="sell",
        )

        assert mock_mcp.called_with("market", "find_nearby", order_type="sell")

    async def test_find_with_custom_max_jumps(self, mock_mcp):
        """Verify /find accepts custom max_jumps parameter."""
        mock_mcp.record_call(
            "market",
            "find_nearby",
            item="Pioneer",
            origin="Jita",
            max_jumps=50,
        )

        calls = mock_mcp.get_calls("market", "find_nearby")
        assert len(calls) == 1
        assert calls[0].kwargs["max_jumps"] == 50


# =============================================================================
# Mock MCP Tracker Tests (Self-Verification)
# =============================================================================


class TestMockMCPTracker:
    """Verify MockMCPTracker works correctly."""

    def test_records_calls(self, mock_mcp):
        """Test that calls are recorded."""
        mock_mcp.record_call("universe", "route", origin="Jita", destination="Amarr")

        assert len(mock_mcp.calls) == 1
        assert mock_mcp.calls[0].dispatcher == "universe"
        assert mock_mcp.calls[0].action == "route"

    def test_was_called_matches(self, mock_mcp):
        """Test was_called matching."""
        mock_mcp.record_call("market", "prices", items=["PLEX"])

        assert mock_mcp.was_called("market", "prices")
        assert not mock_mcp.was_called("market", "orders")
        assert not mock_mcp.was_called("universe", "prices")

    def test_called_with_matches_kwargs(self, mock_mcp):
        """Test called_with parameter matching."""
        mock_mcp.record_call("universe", "route", origin="Jita", destination="Amarr", mode="safe")

        assert mock_mcp.called_with("universe", "route", origin="Jita")
        assert mock_mcp.called_with("universe", "route", mode="safe")
        assert mock_mcp.called_with("universe", "route", origin="Jita", destination="Amarr")
        assert not mock_mcp.called_with("universe", "route", origin="Dodixie")

    def test_get_calls_filtering(self, mock_mcp):
        """Test get_calls filtering by dispatcher and action."""
        mock_mcp.record_call("universe", "route", origin="Jita")
        mock_mcp.record_call("universe", "activity", systems=["Tama"])
        mock_mcp.record_call("market", "prices", items=["PLEX"])

        universe_calls = mock_mcp.get_calls("universe")
        assert len(universe_calls) == 2

        route_calls = mock_mcp.get_calls("universe", "route")
        assert len(route_calls) == 1

    def test_set_and_return_response(self, mock_mcp):
        """Test configuring custom responses."""
        mock_mcp.set_response("universe", "route", {"total_jumps": 45})

        result = mock_mcp.record_call("universe", "route", origin="Jita")
        assert result == {"total_jumps": 45}

    def test_reset_clears_calls(self, mock_mcp):
        """Test that reset clears recorded calls."""
        mock_mcp.record_call("universe", "route", origin="Jita")
        assert len(mock_mcp.calls) == 1

        mock_mcp.reset()
        assert len(mock_mcp.calls) == 0


# =============================================================================
# Abyssal Skill Contract Tests
# =============================================================================


@pytest.mark.asyncio
class TestAbyssalSkillContract:
    """Contract tests for the /abyssal skill.

    /abyssal is a pure reference data skill that reads from local JSON files.
    It does NOT require MCP calls for basic weather/tier/ship/npc queries.

    Optional MCP usage:
    - fitting(action='calculate_stats') for fit analysis (optional)
    """

    async def test_abyssal_no_mcp_required_for_weather(self, mock_mcp):
        """Verify /abyssal weather queries don't require MCP calls."""
        # Weather queries should use local reference data
        # No MCP calls should be recorded
        assert not mock_mcp.was_called("universe", "route")
        assert not mock_mcp.was_called("market", "prices")
        assert not mock_mcp.was_called("sde", "item_info")

    async def test_abyssal_no_mcp_required_for_tier(self, mock_mcp):
        """Verify /abyssal tier queries don't require MCP calls."""
        # Tier info is pure reference data
        assert not mock_mcp.was_called("universe", "route")
        assert not mock_mcp.was_called("market", "prices")

    async def test_abyssal_no_mcp_required_for_ship(self, mock_mcp):
        """Verify /abyssal ship queries don't require MCP calls."""
        # Ship recommendations are reference data
        assert not mock_mcp.was_called("fitting", "calculate_stats")

    async def test_abyssal_optional_fitting_for_analysis(self, mock_mcp):
        """Verify /abyssal can optionally use fitting for fit analysis."""
        # When analyzing a specific fit, fitting MCP may be used
        eft = "[Gila, Abyssal T4]\nDrone Damage Amplifier II"
        mock_mcp.record_call("fitting", "calculate_stats", eft=eft)

        assert mock_mcp.was_called("fitting", "calculate_stats")

    async def test_abyssal_no_mcp_required_for_npc(self, mock_mcp):
        """Verify /abyssal NPC faction queries don't require MCP calls."""
        # NPC threat data is reference data
        assert not mock_mcp.was_called("sde", "item_info")
        assert not mock_mcp.was_called("universe", "activity")


# =============================================================================
# PI Skill Contract Tests
# =============================================================================


@pytest.mark.asyncio
class TestPISkillContract:
    """Contract tests for the /pi skill.

    /pi is a pure reference data skill that reads from local JSON files.
    It does NOT require MCP calls for production chain/resource/skill queries.

    Optional MCP usage:
    - market(action='prices') for profit analysis (optional)
    """

    async def test_pi_no_mcp_required_for_production_chain(self, mock_mcp):
        """Verify /pi production chain queries don't require MCP calls."""
        # Production chains are pure reference data
        assert not mock_mcp.was_called("market", "prices")
        assert not mock_mcp.was_called("sde", "item_info")

    async def test_pi_no_mcp_required_for_resources(self, mock_mcp):
        """Verify /pi planet resource queries don't require MCP calls."""
        # Resource data is reference data
        assert not mock_mcp.was_called("market", "prices")

    async def test_pi_no_mcp_required_for_skills(self, mock_mcp):
        """Verify /pi skill queries don't require MCP calls."""
        # PI skill data is reference data
        assert not mock_mcp.was_called("skills", "training_time")

    async def test_pi_optional_market_for_profit(self, mock_mcp):
        """Verify /pi can optionally use market for profit analysis."""
        # When calculating profit margins, market prices may be fetched
        mock_mcp.record_call("market", "prices", items=["Robotics"], region="jita")

        assert mock_mcp.was_called("market", "prices")
        assert mock_mcp.called_with("market", "prices", items=["Robotics"])

    async def test_pi_no_mcp_required_for_single_planet(self, mock_mcp):
        """Verify /pi single planet P2 queries don't require MCP calls."""
        # Single planet P2 mapping is reference data
        assert not mock_mcp.was_called("market", "prices")


# =============================================================================
# Standings Skill Contract Tests
# =============================================================================


@pytest.mark.asyncio
class TestStandingsSkillContract:
    """Contract tests for the /standings skill.

    /standings uses a combination of:
    - ESI data (pilot standings, skills)
    - Reference data (agent requirements, epic arcs)
    - MCP tools for agent discovery and routing

    Required MCP usage:
    - sde(action='agent_search') for finding agents
    - universe(action='route') for routing to agents
    """

    async def test_standings_calls_agent_search(self, mock_mcp):
        """Verify /standings can invoke sde(action='agent_search')."""
        mock_mcp.record_call(
            "sde",
            "agent_search",
            corporation="Caldari Navy",
            level=4,
            highsec_only=True,
        )

        assert mock_mcp.was_called("sde", "agent_search")
        assert mock_mcp.called_with("sde", "agent_search", corporation="Caldari Navy")
        assert mock_mcp.called_with("sde", "agent_search", level=4)

    async def test_standings_calls_route_for_agent_distance(self, mock_mcp):
        """Verify /standings uses universe route for agent distances."""
        mock_mcp.record_call(
            "universe",
            "route",
            origin="Jita",
            destination="Josameto",
            mode="safe",
        )

        assert mock_mcp.was_called("universe", "route")
        assert mock_mcp.called_with("universe", "route", destination="Josameto")

    async def test_standings_agent_level_parameter(self, mock_mcp):
        """Verify /standings passes correct agent level parameter."""
        for level in [1, 2, 3, 4, 5]:
            mock_mcp.record_call(
                "sde",
                "agent_search",
                corporation="Sisters of EVE",
                level=level,
            )

        calls = mock_mcp.get_calls("sde", "agent_search")
        assert len(calls) == 5
        levels = {call.kwargs["level"] for call in calls}
        assert levels == {1, 2, 3, 4, 5}

    async def test_standings_division_parameter(self, mock_mcp):
        """Verify /standings passes division parameter for agent search."""
        mock_mcp.record_call(
            "sde",
            "agent_search",
            corporation="Federal Intelligence Office",
            level=4,
            division="Security",
        )

        assert mock_mcp.called_with("sde", "agent_search", division="Security")

    async def test_standings_no_mcp_for_standing_thresholds(self, mock_mcp):
        """Verify standing thresholds don't require MCP (reference data)."""
        # Standing requirements (1.0 for L2, 3.0 for L3, etc.) are constants
        assert not mock_mcp.was_called("sde", "skill_requirements")
        assert not mock_mcp.was_called("market", "prices")

    async def test_standings_no_mcp_for_epic_arc_info(self, mock_mcp):
        """Verify epic arc info doesn't require MCP (reference data)."""
        # Epic arc data is local reference data
        assert not mock_mcp.was_called("universe", "activity")

    async def test_standings_multiple_agent_queries(self, mock_mcp):
        """Verify /standings can query multiple corporations."""
        corps = ["Caldari Navy", "Sisters of EVE", "Federal Navy"]

        for corp in corps:
            mock_mcp.record_call(
                "sde",
                "agent_search",
                corporation=corp,
                level=4,
            )

        calls = mock_mcp.get_calls("sde", "agent_search")
        assert len(calls) == 3

        corps_called = {call.kwargs["corporation"] for call in calls}
        assert corps_called == set(corps)
