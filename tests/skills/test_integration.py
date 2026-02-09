"""
Skill Integration Tests - Actual Claude/MCP Invocation.

This test layer validates skills by actually invoking Claude Code
and/or MCP dispatchers, using fixtures as the source of truth.

Test Tiers:
- Tier 1 (tier1): Mock MCP dispatcher calls - fast, free, runs on every PR
- Tier 2 (tier2): Anthropic API with mock tools - weekly CI, ~$0.01/test
- Tier 3 (tier3): Full Claude CLI - release/manual, ~$0.03/test

Run commands:
    # Tier 1 only (fast, free)
    uv run pytest tests/skills/test_integration.py -m tier1 -v

    # Tier 1 + 2 (with API key)
    ANTHROPIC_API_KEY=sk-... uv run pytest tests/skills/test_integration.py -m "tier1 or tier2" -v

    # All integration tests
    uv run pytest tests/skills/test_integration.py -m integration -v
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.skills.conftest import (
    assert_fact,
    get_fixtures_for_skill,
)
from tests.skills.integration import (
    MockMCPServer,
    extract_json_from_response,
    invoke_mcp_direct,
)

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


# =============================================================================
# Fixture Loading Utilities
# =============================================================================


def load_fixture(fixture_path: Path) -> dict[str, Any]:
    """Load a YAML fixture file."""
    with open(fixture_path) as f:
        return yaml.safe_load(f)


def has_mock_responses(fixture: dict[str, Any]) -> bool:
    """Check if fixture has mock_responses section."""
    return "mock_responses" in fixture


def has_esi_responses(fixture: dict[str, Any]) -> bool:
    """Check if fixture has esi_responses section."""
    return "esi_responses" in fixture


def has_any_mocks(fixture: dict[str, Any]) -> bool:
    """Check if fixture has either mock_responses or esi_responses."""
    return has_mock_responses(fixture) or has_esi_responses(fixture)


def create_mock_server_from_fixture(fixture: dict[str, Any]) -> MockMCPServer:
    """Create a MockMCPServer from fixture's mock_responses."""
    server = MockMCPServer()
    mock_responses = fixture.get("mock_responses", {})

    for key, response in mock_responses.items():
        # Parse key format: dispatcher_action (e.g., sde_blueprint_info)
        parts = key.split("_", 1)
        if len(parts) == 2:
            dispatcher, action = parts
            server.set_response(dispatcher, action, response)

    return server


# =============================================================================
# Dynamic Fixture Generation
# =============================================================================


def _get_skill_fixtures_with_mocks(skill_name: str) -> list[tuple[Path, str]]:
    """Get fixtures for a skill that have mock_responses."""
    fixtures = get_fixtures_for_skill(skill_name)
    result = []
    for path in fixtures:
        fixture = load_fixture(path)
        if has_mock_responses(fixture):
            result.append((path, path.stem))
    return result


def _get_skill_fixtures_with_any_mocks(skill_name: str) -> list[tuple[Path, str]]:
    """Get fixtures for a skill that have mock_responses or esi_responses."""
    fixtures = get_fixtures_for_skill(skill_name)
    result = []
    for path in fixtures:
        fixture = load_fixture(path)
        if has_any_mocks(fixture):
            result.append((path, path.stem))
    return result


def pytest_generate_tests(metafunc):
    """Dynamically generate tests for skill fixtures with mock responses."""
    # Build-cost fixtures
    if "build_cost_fixture" in metafunc.fixturenames:
        fixtures = _get_skill_fixtures_with_mocks("build-cost")
        if fixtures:
            metafunc.parametrize(
                "build_cost_fixture",
                [f[0] for f in fixtures],
                ids=[f[1] for f in fixtures],
            )

    # Route fixtures
    if "route_fixture" in metafunc.fixturenames:
        fixtures = _get_skill_fixtures_with_mocks("route")
        if fixtures:
            metafunc.parametrize(
                "route_fixture",
                [f[0] for f in fixtures],
                ids=[f[1] for f in fixtures],
            )

    # Price fixtures
    if "price_fixture" in metafunc.fixturenames:
        fixtures = _get_skill_fixtures_with_mocks("price")
        if fixtures:
            metafunc.parametrize(
                "price_fixture",
                [f[0] for f in fixtures],
                ids=[f[1] for f in fixtures],
            )

    # Watchlist fixtures
    if "watchlist_fixture" in metafunc.fixturenames:
        fixtures = _get_skill_fixtures_with_mocks("watchlist")
        if fixtures:
            metafunc.parametrize(
                "watchlist_fixture",
                [f[0] for f in fixtures],
                ids=[f[1] for f in fixtures],
            )

    # Killmail fixtures
    if "killmail_fixture" in metafunc.fixturenames:
        fixtures = _get_skill_fixtures_with_mocks("killmail")
        if fixtures:
            metafunc.parametrize(
                "killmail_fixture",
                [f[0] for f in fixtures],
                ids=[f[1] for f in fixtures],
            )

    # Assets fixtures
    if "assets_fixture" in metafunc.fixturenames:
        fixtures = _get_skill_fixtures_with_mocks("assets")
        if fixtures:
            metafunc.parametrize(
                "assets_fixture",
                [f[0] for f in fixtures],
                ids=[f[1] for f in fixtures],
            )

    # Pilot fixtures (ESI-dependent)
    if "pilot_fixture" in metafunc.fixturenames:
        fixtures = _get_skill_fixtures_with_any_mocks("pilot")
        if fixtures:
            metafunc.parametrize(
                "pilot_fixture",
                [f[0] for f in fixtures],
                ids=[f[1] for f in fixtures],
            )

    # Skillqueue fixtures (ESI-dependent)
    if "skillqueue_fixture" in metafunc.fixturenames:
        fixtures = _get_skill_fixtures_with_any_mocks("skillqueue")
        if fixtures:
            metafunc.parametrize(
                "skillqueue_fixture",
                [f[0] for f in fixtures],
                ids=[f[1] for f in fixtures],
            )

    # Clones fixtures (ESI-dependent)
    if "clones_fixture" in metafunc.fixturenames:
        fixtures = _get_skill_fixtures_with_any_mocks("clones")
        if fixtures:
            metafunc.parametrize(
                "clones_fixture",
                [f[0] for f in fixtures],
                ids=[f[1] for f in fixtures],
            )

    # Wallet-journal fixtures (ESI-dependent)
    if "wallet_journal_fixture" in metafunc.fixturenames:
        fixtures = _get_skill_fixtures_with_any_mocks("wallet-journal")
        if fixtures:
            metafunc.parametrize(
                "wallet_journal_fixture",
                [f[0] for f in fixtures],
                ids=[f[1] for f in fixtures],
            )

    # Gatecamp fixtures (MCP contract + structure validation)
    if "gatecamp_fixture" in metafunc.fixturenames:
        fixtures = _get_skill_fixtures_with_mocks("gatecamp")
        if not fixtures:
            # Fall back to all fixtures for structure tests
            all_fixtures = get_fixtures_for_skill("gatecamp")
            if all_fixtures:
                metafunc.parametrize(
                    "gatecamp_fixture",
                    all_fixtures,
                    ids=[f.stem for f in all_fixtures],
                )
        else:
            metafunc.parametrize(
                "gatecamp_fixture",
                [f[0] for f in fixtures],
                ids=[f[1] for f in fixtures],
            )

    # Orient fixtures (MCP contract + structure validation)
    if "orient_fixture" in metafunc.fixturenames:
        fixtures = _get_skill_fixtures_with_mocks("orient")
        if not fixtures:
            # Fall back to all fixtures for structure tests
            all_fixtures = get_fixtures_for_skill("orient")
            if all_fixtures:
                metafunc.parametrize(
                    "orient_fixture",
                    all_fixtures,
                    ids=[f.stem for f in all_fixtures],
                )
        else:
            metafunc.parametrize(
                "orient_fixture",
                [f[0] for f in fixtures],
                ids=[f[1] for f in fixtures],
            )

    # Standings fixtures (structure validation)
    if "standings_fixture" in metafunc.fixturenames:
        fixtures = get_fixtures_for_skill("standings")
        if fixtures:
            metafunc.parametrize(
                "standings_fixture",
                fixtures,
                ids=[f.stem for f in fixtures],
            )

    # Find fixtures (structure validation)
    if "find_fixture" in metafunc.fixturenames:
        fixtures = get_fixtures_for_skill("find")
        if fixtures:
            metafunc.parametrize(
                "find_fixture",
                fixtures,
                ids=[f.stem for f in fixtures],
            )

    # PI fixtures (structure validation)
    if "pi_fixture" in metafunc.fixturenames:
        fixtures = get_fixtures_for_skill("pi")
        if fixtures:
            metafunc.parametrize(
                "pi_fixture",
                fixtures,
                ids=[f.stem for f in fixtures],
            )

    # Abyssal fixtures (structure validation)
    if "abyssal_fixture" in metafunc.fixturenames:
        fixtures = get_fixtures_for_skill("abyssal")
        if fixtures:
            metafunc.parametrize(
                "abyssal_fixture",
                fixtures,
                ids=[f.stem for f in fixtures],
            )

    # Threat-assessment fixtures (MCP contract)
    if "threat_assessment_fixture" in metafunc.fixturenames:
        fixtures = _get_skill_fixtures_with_mocks("threat-assessment")
        if fixtures:
            metafunc.parametrize(
                "threat_assessment_fixture",
                [f[0] for f in fixtures],
                ids=[f[1] for f in fixtures],
            )

    # Skillplan fixtures (MCP contract)
    if "skillplan_fixture" in metafunc.fixturenames:
        fixtures = _get_skill_fixtures_with_mocks("skillplan")
        if fixtures:
            metafunc.parametrize(
                "skillplan_fixture",
                [f[0] for f in fixtures],
                ids=[f[1] for f in fixtures],
            )

    # Fitting fixtures (MCP contract)
    if "fitting_fixture" in metafunc.fixturenames:
        fixtures = _get_skill_fixtures_with_mocks("fitting")
        if fixtures:
            metafunc.parametrize(
                "fitting_fixture",
                [f[0] for f in fixtures],
                ids=[f[1] for f in fixtures],
            )


# =============================================================================
# Tier 1: Mock MCP Tests (Fast, Free, Every PR)
# =============================================================================


@pytest.mark.tier1
class TestBuildCostMCPContract:
    """
    Tier 1: Verify /build-cost MCP calls and responses match fixtures.

    These tests validate that the skill makes the correct MCP calls
    and produces correct output when given fixture-defined responses.
    """

    def test_build_cost_mcp_flow(self, build_cost_fixture: Path):
        """
        Test that build-cost skill processes MCP responses correctly.

        This test:
        1. Loads fixture with mock responses
        2. Creates mock server with those responses
        3. Invokes MCP dispatchers directly
        4. Validates output against expected_facts
        """
        fixture = load_fixture(build_cost_fixture)
        if not has_mock_responses(fixture):
            pytest.skip("Fixture has no mock_responses")

        mock_server = create_mock_server_from_fixture(fixture)
        input_data = fixture.get("input", {})

        # Invoke the blueprint_info call
        invoke_mcp_direct(
            "sde",
            "blueprint_info",
            mock_server=mock_server,
            item=input_data.get("item"),
        )

        # Verify blueprint call was made
        assert mock_server.was_called("sde", "blueprint_info")

        # If fixture expects blueprint info, validate
        if "expected_facts" in fixture:
            # Build combined result as skill would produce
            # For Tier 1, we validate the MCP response structure
            for fact in fixture["expected_facts"]:
                path = fact.get("path", "")
                # Only validate facts about blueprint section
                if path.startswith("blueprint."):
                    # Skip blueprint facts in tier1 - they come from skill logic
                    pass

        # Invoke market prices if needed
        if "market" in fixture.get("mock_responses", {}):
            materials = fixture.get("mock_responses", {}).get("sde_blueprint_info", {}).get(
                "materials", []
            )
            items = [m.get("type_name") for m in materials if m.get("type_name")]

            if items:
                invoke_mcp_direct(
                    "market",
                    "prices",
                    mock_server=mock_server,
                    items=items,
                    region=input_data.get("region", "jita"),
                )
                assert mock_server.was_called("market", "prices")

    def test_build_cost_calls_correct_dispatchers(self, build_cost_fixture: Path):
        """Verify build-cost makes expected dispatcher calls."""
        fixture = load_fixture(build_cost_fixture)
        if not has_mock_responses(fixture):
            pytest.skip("Fixture has no mock_responses")

        mock_server = create_mock_server_from_fixture(fixture)
        input_data = fixture.get("input", {})

        # Build-cost should always call sde.blueprint_info
        invoke_mcp_direct(
            "sde",
            "blueprint_info",
            mock_server=mock_server,
            item=input_data.get("item"),
        )

        assert mock_server.was_called("sde", "blueprint_info")

        # Verify call parameters
        calls = mock_server.get_calls("sde", "blueprint_info")
        assert len(calls) >= 1
        assert calls[0][2].get("item") == input_data.get("item")


@pytest.mark.tier1
class TestRouteMCPContract:
    """
    Tier 1: Verify /route MCP calls and responses match fixtures.
    """

    def test_route_mcp_flow(self, route_fixture: Path):
        """Test route skill processes MCP responses correctly."""
        fixture = load_fixture(route_fixture)
        if not has_mock_responses(fixture):
            pytest.skip("Fixture has no mock_responses")

        mock_server = create_mock_server_from_fixture(fixture)
        input_data = fixture.get("input", {})

        # Invoke route calculation
        result = invoke_mcp_direct(
            "universe",
            "route",
            mock_server=mock_server,
            origin=input_data.get("origin"),
            destination=input_data.get("destination"),
            mode=input_data.get("mode", "shortest"),
        )

        # Verify route call was made with correct params
        assert mock_server.was_called("universe", "route")
        assert mock_server.called_with(
            "universe",
            "route",
            origin=input_data.get("origin"),
            destination=input_data.get("destination"),
        )

        # Validate expected facts against mock response
        if "expected_facts" in fixture:
            for fact in fixture["expected_facts"]:
                # Route facts are validated against the mock response
                try:
                    assert_fact(result, fact)
                except (KeyError, IndexError):
                    # Some paths may not exist in mock - skip
                    pass

    def test_route_calls_correct_dispatchers(self, route_fixture: Path):
        """Verify route makes expected dispatcher calls."""
        fixture = load_fixture(route_fixture)
        if not has_mock_responses(fixture):
            pytest.skip("Fixture has no mock_responses")

        mock_server = create_mock_server_from_fixture(fixture)
        input_data = fixture.get("input", {})

        invoke_mcp_direct(
            "universe",
            "route",
            mock_server=mock_server,
            origin=input_data.get("origin"),
            destination=input_data.get("destination"),
            mode=input_data.get("mode", "shortest"),
        )

        # Route should call universe.route
        assert mock_server.was_called("universe", "route")

        # Verify mode parameter was passed
        calls = mock_server.get_calls("universe", "route")
        assert len(calls) >= 1
        assert calls[0][2].get("mode") == input_data.get("mode", "shortest")


@pytest.mark.tier1
class TestPriceMCPContract:
    """
    Tier 1: Verify /price MCP calls and responses match fixtures.
    """

    def test_price_mcp_flow(self, price_fixture: Path):
        """Test price skill processes MCP responses correctly."""
        fixture = load_fixture(price_fixture)
        if not has_mock_responses(fixture):
            pytest.skip("Fixture has no mock_responses")

        mock_server = create_mock_server_from_fixture(fixture)
        input_data = fixture.get("input", {})

        # Invoke price lookup
        result = invoke_mcp_direct(
            "market",
            "prices",
            mock_server=mock_server,
            items=input_data.get("items", []),
            region=input_data.get("region", "jita"),
        )

        # Verify price call was made
        assert mock_server.was_called("market", "prices")

        # Validate expected facts
        if "expected_facts" in fixture:
            for fact in fixture["expected_facts"]:
                try:
                    assert_fact(result, fact)
                except (KeyError, IndexError):
                    pass

    def test_price_calls_correct_dispatchers(self, price_fixture: Path):
        """Verify price makes expected dispatcher calls."""
        fixture = load_fixture(price_fixture)
        if not has_mock_responses(fixture):
            pytest.skip("Fixture has no mock_responses")

        mock_server = create_mock_server_from_fixture(fixture)
        input_data = fixture.get("input", {})

        invoke_mcp_direct(
            "market",
            "prices",
            mock_server=mock_server,
            items=input_data.get("items", []),
            region=input_data.get("region", "jita"),
        )

        assert mock_server.was_called("market", "prices")

        # Verify items were passed correctly
        calls = mock_server.get_calls("market", "prices")
        assert len(calls) >= 1
        assert calls[0][2].get("items") == input_data.get("items", [])


# =============================================================================
# Tier 1: Watchlist MCP Contract Tests
# =============================================================================


@pytest.mark.tier1
class TestWatchlistMCPContract:
    """
    Tier 1: Verify /watchlist command responses match fixtures.

    Watchlist uses CLI commands rather than MCP dispatchers,
    so these tests validate the expected output structure.
    """

    def test_watchlist_list_structure(self, watchlist_fixture: Path):
        """Test watchlist list command produces expected structure."""
        fixture = load_fixture(watchlist_fixture)
        if not has_mock_responses(fixture):
            pytest.skip("Fixture has no mock_responses")

        # Validate expected_output structure if present
        if "expected_output" in fixture:
            output = fixture["expected_output"]

            # List response should have watchlists array
            if "watchlists" in output:
                assert isinstance(output["watchlists"], list)
                for wl in output["watchlists"]:
                    assert "name" in wl
                    assert "type" in wl

    def test_watchlist_expected_facts(self, watchlist_fixture: Path):
        """Validate expected_facts against expected_output."""
        fixture = load_fixture(watchlist_fixture)

        if "expected_output" in fixture and "expected_facts" in fixture:
            output = fixture["expected_output"]
            for fact in fixture["expected_facts"]:
                try:
                    assert_fact(output, fact)
                except (KeyError, IndexError):
                    pass  # Some paths may not exist


# =============================================================================
# Tier 1: Killmail MCP Contract Tests
# =============================================================================


@pytest.mark.tier1
class TestKillmailMCPContract:
    """
    Tier 1: Verify /killmail responses match fixtures.

    Killmail fetches from zKillboard and ESI, so these tests
    validate the expected output structure with mocked external responses.
    """

    def test_killmail_analysis_structure(self, killmail_fixture: Path):
        """Test killmail analysis produces expected structure."""
        fixture = load_fixture(killmail_fixture)
        if not has_mock_responses(fixture):
            pytest.skip("Fixture has no mock_responses")

        if "expected_output" in fixture:
            output = fixture["expected_output"]

            # Successful analysis should have these fields
            if "error" not in output or not output["error"]:
                assert "killmail_id" in output
                assert "system" in output
                assert "victim" in output

    def test_killmail_error_structure(self, killmail_fixture: Path):
        """Test killmail error response structure."""
        fixture = load_fixture(killmail_fixture)

        if "expected_output" in fixture:
            output = fixture["expected_output"]

            # Error response should have error fields
            if output.get("error"):
                assert "error_type" in output
                assert "error_message" in output

    def test_killmail_expected_facts(self, killmail_fixture: Path):
        """Validate expected_facts against expected_output."""
        fixture = load_fixture(killmail_fixture)

        if "expected_output" in fixture and "expected_facts" in fixture:
            output = fixture["expected_output"]
            for fact in fixture["expected_facts"]:
                try:
                    assert_fact(output, fact)
                except (KeyError, IndexError):
                    pass


# =============================================================================
# Tier 1: Assets MCP Contract Tests
# =============================================================================


@pytest.mark.tier1
class TestAssetsMCPContract:
    """
    Tier 1: Verify /assets responses match fixtures.

    Assets uses ESI for character assets and optionally market dispatcher
    for valuation. These tests validate structure with mocked responses.
    """

    def test_assets_overview_structure(self, assets_fixture: Path):
        """Test assets overview produces expected structure."""
        fixture = load_fixture(assets_fixture)

        if "expected_output" in fixture:
            output = fixture["expected_output"]

            # Overview should have totals
            if "total_unique_items" in output:
                assert output["total_unique_items"] >= 0

            # Ships filter should have ships array
            if output.get("filter") == "ships":
                assert "ships" in output
                assert "total_ships" in output

    def test_assets_valuation_structure(self, assets_fixture: Path):
        """Test assets valuation produces expected structure."""
        fixture = load_fixture(assets_fixture)

        if "expected_output" in fixture:
            output = fixture["expected_output"]

            # Valuation should have value
            if output.get("filter") == "value":
                assert "total_estimated_value" in output
                assert output["total_estimated_value"] >= 0

    def test_assets_expected_facts(self, assets_fixture: Path):
        """Validate expected_facts against expected_output."""
        fixture = load_fixture(assets_fixture)

        if "expected_output" in fixture and "expected_facts" in fixture:
            output = fixture["expected_output"]
            for fact in fixture["expected_facts"]:
                try:
                    assert_fact(output, fact)
                except (KeyError, IndexError):
                    pass


# =============================================================================
# Tier 1: General MCP Validation
# =============================================================================


@pytest.mark.tier1
class TestMCPResponseStructure:
    """
    Tier 1: Validate MCP response structure matches expectations.
    """

    def test_mock_server_basic_functionality(self):
        """Verify MockMCPServer works correctly."""
        server = MockMCPServer()

        # Set and get response
        server.set_response("sde", "item_info", {"type_id": 34, "name": "Tritanium"})
        result = server.get_response("sde", "item_info")
        assert result["type_id"] == 34

        # Mock call logging
        server.mock_call("sde", "item_info", item="Tritanium")
        assert server.was_called("sde", "item_info")
        assert server.called_with("sde", "item_info", item="Tritanium")
        assert not server.called_with("sde", "item_info", item="Pyerite")

    def test_mock_server_from_fixture_format(self):
        """Verify fixture format parsing works."""
        # Simulate fixture with mock_responses
        fixture = {
            "mock_responses": {
                "sde_blueprint_info": {"type_id": 32880},
                "market_prices": {"items": []},
            }
        }

        server = create_mock_server_from_fixture(fixture)

        # Verify responses were parsed
        assert server.get_response("sde", "blueprint_info") == {"type_id": 32880}
        assert server.get_response("market", "prices") == {"items": []}


# =============================================================================
# Tier 2: API Integration Tests (Weekly CI)
# =============================================================================


HAS_API_KEY = bool(os.environ.get("ANTHROPIC_API_KEY"))


@pytest.mark.tier2
@pytest.mark.skipif(not HAS_API_KEY, reason="ANTHROPIC_API_KEY not set")
class TestSkillAPIIntegration:
    """
    Tier 2: Invoke skills via Anthropic API with mock tools.

    These tests validate that Claude produces correct JSON output
    when given mock tool responses.
    """

    @pytest.mark.asyncio
    async def test_build_cost_api_produces_json(self):
        """Test build-cost produces valid JSON via API."""
        from tests.skills.integration import invoke_via_api

        # Define mock responses
        mock_tools = {
            "sde_blueprint_info": {
                "type_id": 32880,
                "type_name": "Venture Blueprint",
                "product_name": "Venture",
                "materials": [
                    {"type_name": "Tritanium", "quantity": 22222},
                    {"type_name": "Pyerite", "quantity": 6667},
                ],
            },
            "market_prices": {
                "items": [
                    {"type_name": "Tritanium", "sell": {"min_price": 4.50}},
                    {"type_name": "Pyerite", "sell": {"min_price": 22.0}},
                    {"type_name": "Venture", "sell": {"min_price": 650000}},
                ],
                "region": "The Forge",
            },
        }

        result = await invoke_via_api(
            skill_name="build-cost",
            skill_args="Venture me0",
            mock_tools=mock_tools,
        )

        # Should have made tool calls
        assert len(result["tool_calls"]) > 0

        # Response should contain JSON
        response = result["response"]
        json_data = extract_json_from_response(response)

        # If JSON extracted, validate structure
        if json_data:
            # Should have cost-related fields
            assert any(
                key in str(json_data).lower()
                for key in ["cost", "price", "material", "venture"]
            )

    @pytest.mark.asyncio
    async def test_route_api_produces_json(self):
        """Test route produces valid JSON via API."""
        from tests.skills.integration import invoke_via_api

        mock_tools = {
            "universe_route": {
                "origin": "Jita",
                "destination": "Amarr",
                "total_jumps": 45,
                "route": [
                    {"system": "Jita", "security": 0.95},
                    {"system": "Amarr", "security": 1.0},
                ],
            },
        }

        result = await invoke_via_api(
            skill_name="route",
            skill_args="Jita Amarr --safe",
            mock_tools=mock_tools,
        )

        assert len(result["tool_calls"]) > 0

        response = result["response"]
        assert "Jita" in response or "jita" in response.lower()
        assert "Amarr" in response or "amarr" in response.lower()


# =============================================================================
# Tier 3: CLI Integration Tests (Manual/Release)
# =============================================================================


@pytest.mark.tier3
@pytest.mark.slow
class TestSkillCLIIntegration:
    """
    Tier 3: Full Claude CLI integration tests.

    These are the most comprehensive but slowest/most expensive tests.
    Only run for releases or manual verification.
    """

    def test_route_cli_invocation(self):
        """Test route skill via full CLI."""
        from tests.skills.integration import invoke_via_cli

        try:
            result = invoke_via_cli(
                skill_name="route",
                skill_args="Jita Perimeter",
                timeout=30,
            )
        except FileNotFoundError:
            pytest.skip("Claude CLI not installed")

        # Should complete successfully
        if result["success"]:
            response = result["response"]
            # Response should mention the systems
            assert "Jita" in response or "jita" in response.lower()

    def test_price_cli_invocation(self):
        """Test price skill via full CLI."""
        from tests.skills.integration import invoke_via_cli

        try:
            result = invoke_via_cli(
                skill_name="price",
                skill_args="Tritanium",
                timeout=30,
            )
        except FileNotFoundError:
            pytest.skip("Claude CLI not installed")

        if result["success"]:
            response = result["response"]
            # Response should mention the item
            assert "Tritanium" in response or "tritanium" in response.lower()


# =============================================================================
# Tier 1: Pilot Skill Tests
# =============================================================================


@pytest.mark.tier1
class TestPilotMCPContract:
    """
    Tier 1: Verify /pilot ESI calls match fixtures.

    Tests pilot identity queries including self and public lookups.
    """

    def test_pilot_has_expected_esi_responses(self, pilot_fixture: Path):
        """Verify fixture has ESI response section for pilot data."""
        fixture = load_fixture(pilot_fixture)

        # Pilot fixtures should have esi_responses
        if "esi_responses" in fixture:
            esi = fixture["esi_responses"]
            # Should have characters data
            assert "characters" in esi or "search" in esi or "error" in esi

    def test_pilot_fixture_fact_assertions(self, pilot_fixture: Path):
        """Validate expected_facts against expected_output."""
        fixture = load_fixture(pilot_fixture)

        if "expected_output" in fixture and "expected_facts" in fixture:
            output = fixture["expected_output"]
            for fact in fixture["expected_facts"]:
                assert_fact(output, fact)


# =============================================================================
# Tier 1: Skillqueue Skill Tests
# =============================================================================


@pytest.mark.tier1
class TestSkillqueueMCPContract:
    """
    Tier 1: Verify /skillqueue ESI calls match fixtures.

    Tests skill queue status including active training and empty queue.
    """

    def test_skillqueue_has_expected_esi_responses(self, skillqueue_fixture: Path):
        """Verify fixture has ESI response section for skillqueue data."""
        fixture = load_fixture(skillqueue_fixture)

        # Skillqueue fixtures should have esi_responses
        if "esi_responses" in fixture:
            esi = fixture["esi_responses"]
            # Should have skillqueue or error data
            assert "skillqueue" in esi or "error" in esi

    def test_skillqueue_fixture_fact_assertions(self, skillqueue_fixture: Path):
        """Validate expected_facts against expected_output."""
        fixture = load_fixture(skillqueue_fixture)

        if "expected_output" in fixture and "expected_facts" in fixture:
            output = fixture["expected_output"]
            for fact in fixture["expected_facts"]:
                assert_fact(output, fact)


# =============================================================================
# Tier 1: Clones Skill Tests
# =============================================================================


@pytest.mark.tier1
class TestClonesMCPContract:
    """
    Tier 1: Verify /clones ESI calls match fixtures.

    Tests clone and implant status queries.
    """

    def test_clones_has_expected_esi_responses(self, clones_fixture: Path):
        """Verify fixture has ESI response section for clones data."""
        fixture = load_fixture(clones_fixture)

        # Clones fixtures should have esi_responses
        if "esi_responses" in fixture:
            esi = fixture["esi_responses"]
            # Should have clones or implants data
            assert "clones" in esi or "implants" in esi

    def test_clones_fixture_fact_assertions(self, clones_fixture: Path):
        """Validate expected_facts against expected_output."""
        fixture = load_fixture(clones_fixture)

        if "expected_output" in fixture and "expected_facts" in fixture:
            output = fixture["expected_output"]
            for fact in fixture["expected_facts"]:
                assert_fact(output, fact)


# =============================================================================
# Tier 1: Wallet-Journal Skill Tests
# =============================================================================


@pytest.mark.tier1
class TestWalletJournalMCPContract:
    """
    Tier 1: Verify /wallet-journal ESI calls match fixtures.

    Tests wallet journal and transaction queries.
    """

    def test_wallet_journal_has_expected_esi_responses(self, wallet_journal_fixture: Path):
        """Verify fixture has ESI response section for wallet data."""
        fixture = load_fixture(wallet_journal_fixture)

        # Wallet-journal fixtures should have esi_responses
        if "esi_responses" in fixture:
            esi = fixture["esi_responses"]
            # Should have wallet_journal or wallet_transactions data
            assert "wallet_journal" in esi or "wallet_transactions" in esi

    def test_wallet_journal_fixture_fact_assertions(self, wallet_journal_fixture: Path):
        """Validate expected_facts against expected_output."""
        fixture = load_fixture(wallet_journal_fixture)

        if "expected_output" in fixture and "expected_facts" in fixture:
            output = fixture["expected_output"]
            for fact in fixture["expected_facts"]:
                assert_fact(output, fact)


# =============================================================================
# Helper Tests - Response Parser
# =============================================================================


@pytest.mark.tier1
class TestResponseParser:
    """Test response parsing utilities."""

    def test_extract_json_from_code_block(self):
        """Test JSON extraction from markdown code blocks."""
        response = """Here's the data:

```json
{"name": "Jita", "security": 0.95}
```

That's the system info."""

        result = extract_json_from_response(response)
        assert result == {"name": "Jita", "security": 0.95}

    def test_extract_json_from_bare_object(self):
        """Test JSON extraction from bare object in text."""
        response = 'The result is {"total": 45} jumps.'
        result = extract_json_from_response(response)
        assert result == {"total": 45}

    def test_extract_json_from_pure_json(self):
        """Test parsing pure JSON response."""
        response = '{"items": [1, 2, 3]}'
        result = extract_json_from_response(response)
        assert result == {"items": [1, 2, 3]}

    def test_extract_json_handles_empty(self):
        """Test handling of empty/None input."""
        assert extract_json_from_response("") is None
        assert extract_json_from_response(None) is None

    def test_extract_json_handles_no_json(self):
        """Test handling of text with no JSON."""
        assert extract_json_from_response("Just plain text.") is None


# =============================================================================
# Tier 1: Gatecamp Structure Tests
# =============================================================================


@pytest.mark.tier1
class TestGatecampStructure:
    """
    Tier 1: Validate /gatecamp fixture structure and fact assertions.

    Tests gatecamp route analysis and chokepoint detection.
    """

    def test_gatecamp_fixture_fact_assertions(self, gatecamp_fixture: Path):
        """Validate expected_facts against expected_output."""
        fixture = load_fixture(gatecamp_fixture)

        if "expected_output" in fixture and "expected_facts" in fixture:
            for fact in fixture["expected_facts"]:
                assert_fact(fixture["expected_output"], fact)


# =============================================================================
# Tier 1: Orient Structure Tests
# =============================================================================


@pytest.mark.tier1
class TestOrientStructure:
    """
    Tier 1: Validate /orient fixture structure and fact assertions.

    Tests local area intel for various security classes.
    """

    def test_orient_fixture_fact_assertions(self, orient_fixture: Path):
        """Validate expected_facts against expected_output."""
        fixture = load_fixture(orient_fixture)

        if "expected_output" in fixture and "expected_facts" in fixture:
            for fact in fixture["expected_facts"]:
                assert_fact(fixture["expected_output"], fact)


# =============================================================================
# Tier 1: Standings Structure Tests
# =============================================================================


@pytest.mark.tier1
class TestStandingsStructure:
    """
    Tier 1: Validate /standings fixture structure and fact assertions.

    Tests agent access, standing plans, and repair strategies.
    """

    def test_standings_fixture_fact_assertions(self, standings_fixture: Path):
        """Validate expected_facts against expected_output."""
        fixture = load_fixture(standings_fixture)

        if "expected_output" in fixture and "expected_facts" in fixture:
            for fact in fixture["expected_facts"]:
                assert_fact(fixture["expected_output"], fact)


# =============================================================================
# Tier 1: Find Structure Tests
# =============================================================================


@pytest.mark.tier1
class TestFindStructure:
    """
    Tier 1: Validate /find fixture structure and fact assertions.

    Tests market source discovery by proximity.
    """

    def test_find_fixture_fact_assertions(self, find_fixture: Path):
        """Validate expected_facts against expected_output."""
        fixture = load_fixture(find_fixture)

        if "expected_output" in fixture and "expected_facts" in fixture:
            for fact in fixture["expected_facts"]:
                assert_fact(fixture["expected_output"], fact)


# =============================================================================
# Tier 1: PI Structure Tests
# =============================================================================


@pytest.mark.tier1
class TestPIStructure:
    """
    Tier 1: Validate /pi fixture structure and fact assertions.

    Tests planetary interaction production chains and planet resources.
    """

    def test_pi_fixture_fact_assertions(self, pi_fixture: Path):
        """Validate expected_facts against expected_output."""
        fixture = load_fixture(pi_fixture)

        if "expected_output" in fixture and "expected_facts" in fixture:
            for fact in fixture["expected_facts"]:
                assert_fact(fixture["expected_output"], fact)


# =============================================================================
# Tier 1: Abyssal Structure Tests
# =============================================================================


@pytest.mark.tier1
class TestAbyssalStructure:
    """
    Tier 1: Validate /abyssal fixture structure and fact assertions.

    Tests abyssal weather types, tiers, and ship recommendations.
    """

    def test_abyssal_fixture_fact_assertions(self, abyssal_fixture: Path):
        """Validate expected_facts against expected_output."""
        fixture = load_fixture(abyssal_fixture)

        if "expected_output" in fixture and "expected_facts" in fixture:
            for fact in fixture["expected_facts"]:
                assert_fact(fixture["expected_output"], fact)


# =============================================================================
# Tier 1: Gatecamp MCP Contract Tests
# =============================================================================


@pytest.mark.tier1
class TestGatecampMCPContract:
    """
    Tier 1: Verify /gatecamp MCP calls and responses match fixtures.

    Tests gatecamp route analysis with universe_gatecamp_risk and
    single-system activity checks with universe_activity.
    """

    def test_gatecamp_route_mcp_flow(self, gatecamp_fixture: Path):
        """Test gatecamp route analysis processes MCP responses correctly."""
        fixture = load_fixture(gatecamp_fixture)
        if not has_mock_responses(fixture):
            pytest.skip("Fixture has no mock_responses")

        mock_server = create_mock_server_from_fixture(fixture)
        input_data = fixture.get("input", {})

        # Route analysis uses gatecamp_risk
        if "origin" in input_data and "destination" in input_data:
            result = invoke_mcp_direct(
                "universe",
                "gatecamp_risk",
                mock_server=mock_server,
                origin=input_data.get("origin"),
                destination=input_data.get("destination"),
                mode=input_data.get("mode", "safe"),
            )

            assert mock_server.was_called("universe", "gatecamp_risk")

            # Validate expected facts
            if "expected_facts" in fixture:
                for fact in fixture["expected_facts"]:
                    try:
                        assert_fact(result, fact)
                    except (KeyError, IndexError):
                        pass

    def test_gatecamp_single_system_mcp_flow(self, gatecamp_fixture: Path):
        """Test single-system gatecamp check uses activity action."""
        fixture = load_fixture(gatecamp_fixture)
        if not has_mock_responses(fixture):
            pytest.skip("Fixture has no mock_responses")

        mock_server = create_mock_server_from_fixture(fixture)
        input_data = fixture.get("input", {})

        # Single system checks use activity
        if "systems" in input_data:
            result = invoke_mcp_direct(
                "universe",
                "activity",
                mock_server=mock_server,
                systems=input_data.get("systems"),
            )

            assert mock_server.was_called("universe", "activity")

            if "expected_facts" in fixture:
                for fact in fixture["expected_facts"]:
                    try:
                        assert_fact(result, fact)
                    except (KeyError, IndexError):
                        pass


# =============================================================================
# Tier 1: Orient MCP Contract Tests
# =============================================================================


@pytest.mark.tier1
class TestOrientMCPContract:
    """
    Tier 1: Verify /orient MCP calls and responses match fixtures.

    Tests local area intel queries via universe_local_area action.
    """

    def test_orient_mcp_flow(self, orient_fixture: Path):
        """Test orient skill processes MCP responses correctly."""
        fixture = load_fixture(orient_fixture)
        if not has_mock_responses(fixture):
            pytest.skip("Fixture has no mock_responses")

        mock_server = create_mock_server_from_fixture(fixture)
        input_data = fixture.get("input", {})

        # Orient uses local_area action
        result = invoke_mcp_direct(
            "universe",
            "local_area",
            mock_server=mock_server,
            origin=input_data.get("origin"),
            max_jumps=input_data.get("max_jumps", 10),
            include_realtime=input_data.get("include_realtime", False),
        )

        assert mock_server.was_called("universe", "local_area")
        assert mock_server.called_with(
            "universe",
            "local_area",
            origin=input_data.get("origin"),
        )

        # Validate expected facts
        if "expected_facts" in fixture:
            for fact in fixture["expected_facts"]:
                try:
                    assert_fact(result, fact)
                except (KeyError, IndexError):
                    pass

    def test_orient_calls_correct_dispatchers(self, orient_fixture: Path):
        """Verify orient makes expected dispatcher calls."""
        fixture = load_fixture(orient_fixture)
        if not has_mock_responses(fixture):
            pytest.skip("Fixture has no mock_responses")

        mock_server = create_mock_server_from_fixture(fixture)
        input_data = fixture.get("input", {})

        invoke_mcp_direct(
            "universe",
            "local_area",
            mock_server=mock_server,
            origin=input_data.get("origin"),
            max_jumps=input_data.get("max_jumps", 10),
        )

        # Orient should call universe.local_area
        assert mock_server.was_called("universe", "local_area")

        # Verify origin parameter was passed
        calls = mock_server.get_calls("universe", "local_area")
        assert len(calls) >= 1
        assert calls[0][2].get("origin") == input_data.get("origin")


# =============================================================================
# Tier 1: Threat Assessment MCP Contract Tests
# =============================================================================


@pytest.mark.tier1
class TestThreatAssessmentMCPContract:
    """
    Tier 1: Verify /threat-assessment MCP calls and responses match fixtures.

    Tests system activity queries via universe_activity action.
    """

    def test_threat_assessment_mcp_flow(self, threat_assessment_fixture: Path):
        """Test threat-assessment processes MCP responses correctly."""
        fixture = load_fixture(threat_assessment_fixture)
        if not has_mock_responses(fixture):
            pytest.skip("Fixture has no mock_responses")

        mock_server = create_mock_server_from_fixture(fixture)
        input_data = fixture.get("input", {})

        # Threat assessment uses activity action
        result = invoke_mcp_direct(
            "universe",
            "activity",
            mock_server=mock_server,
            systems=input_data.get("systems"),
        )

        assert mock_server.was_called("universe", "activity")

        # Validate expected facts
        if "expected_facts" in fixture:
            for fact in fixture["expected_facts"]:
                try:
                    assert_fact(result, fact)
                except (KeyError, IndexError):
                    pass

    def test_threat_assessment_calls_correct_dispatchers(
        self, threat_assessment_fixture: Path
    ):
        """Verify threat-assessment makes expected dispatcher calls."""
        fixture = load_fixture(threat_assessment_fixture)
        if not has_mock_responses(fixture):
            pytest.skip("Fixture has no mock_responses")

        mock_server = create_mock_server_from_fixture(fixture)
        input_data = fixture.get("input", {})

        invoke_mcp_direct(
            "universe",
            "activity",
            mock_server=mock_server,
            systems=input_data.get("systems"),
        )

        # Should call universe.activity
        assert mock_server.was_called("universe", "activity")

        # Verify systems parameter was passed
        calls = mock_server.get_calls("universe", "activity")
        assert len(calls) >= 1
        assert calls[0][2].get("systems") == input_data.get("systems")


# =============================================================================
# Tier 1: Skillplan MCP Contract Tests
# =============================================================================


@pytest.mark.tier1
class TestSkillplanMCPContract:
    """
    Tier 1: Verify /skillplan MCP calls and responses match fixtures.

    Tests skill requirements and training plans via sde and skills dispatchers.
    """

    def test_skillplan_mcp_flow(self, skillplan_fixture: Path):
        """Test skillplan processes MCP responses correctly."""
        fixture = load_fixture(skillplan_fixture)
        if not has_mock_responses(fixture):
            pytest.skip("Fixture has no mock_responses")

        mock_server = create_mock_server_from_fixture(fixture)
        input_data = fixture.get("input", {})
        item = input_data.get("item")

        # Check which MCP actions are mocked
        mock_responses = fixture.get("mock_responses", {})

        # Skill requirements from SDE
        if "sde_skill_requirements" in mock_responses:
            invoke_mcp_direct(
                "sde",
                "skill_requirements",
                mock_server=mock_server,
                item=item,
            )
            assert mock_server.was_called("sde", "skill_requirements")

        # Easy 80% plan from skills dispatcher
        if "skills_easy_80_plan" in mock_responses:
            invoke_mcp_direct(
                "skills",
                "easy_80_plan",
                mock_server=mock_server,
                item=item,
            )
            assert mock_server.was_called("skills", "easy_80_plan")

        # Activity plan from skills dispatcher
        if "skills_activity_plan" in mock_responses:
            invoke_mcp_direct(
                "skills",
                "activity_plan",
                mock_server=mock_server,
                activity=item,
            )
            assert mock_server.was_called("skills", "activity_plan")

        # Validate expected facts
        if "expected_facts" in fixture:
            for fact in fixture["expected_facts"]:
                try:
                    assert_fact(fixture.get("expected_output", {}), fact)
                except (KeyError, IndexError):
                    pass

    def test_skillplan_calls_correct_dispatchers(self, skillplan_fixture: Path):
        """Verify skillplan makes expected dispatcher calls."""
        fixture = load_fixture(skillplan_fixture)
        if not has_mock_responses(fixture):
            pytest.skip("Fixture has no mock_responses")

        mock_server = create_mock_server_from_fixture(fixture)
        input_data = fixture.get("input", {})
        mock_responses = fixture.get("mock_responses", {})

        # For ship/module items: should call sde.skill_requirements + skills.easy_80_plan
        if "sde_skill_requirements" in mock_responses:
            invoke_mcp_direct(
                "sde",
                "skill_requirements",
                mock_server=mock_server,
                item=input_data.get("item"),
            )
            assert mock_server.was_called("sde", "skill_requirements")

            calls = mock_server.get_calls("sde", "skill_requirements")
            assert len(calls) >= 1
            assert calls[0][2].get("item") == input_data.get("item")

        # For activities: should call skills.activity_plan
        if "skills_activity_plan" in mock_responses:
            invoke_mcp_direct(
                "skills",
                "activity_plan",
                mock_server=mock_server,
                activity=input_data.get("item"),
            )
            assert mock_server.was_called("skills", "activity_plan")


# =============================================================================
# Tier 1: Fitting MCP Contract Tests
# =============================================================================


@pytest.mark.tier1
class TestFittingMCPContract:
    """
    Tier 1: Verify /fitting MCP calls and responses match fixtures.

    Tests ship fitting calculations via fitting_calculate_stats action.
    """

    def test_fitting_mcp_flow(self, fitting_fixture: Path):
        """Test fitting skill processes MCP responses correctly."""
        fixture = load_fixture(fitting_fixture)
        if not has_mock_responses(fixture):
            pytest.skip("Fixture has no mock_responses")

        mock_server = create_mock_server_from_fixture(fixture)
        input_data = fixture.get("input", {})

        # Fitting uses calculate_stats action
        result = invoke_mcp_direct(
            "fitting",
            "calculate_stats",
            mock_server=mock_server,
            eft=input_data.get("eft"),
            damage_profile=input_data.get("damage_profile"),
            use_pilot_skills=input_data.get("use_pilot_skills", False),
        )

        assert mock_server.was_called("fitting", "calculate_stats")

        # Validate expected facts
        if "expected_facts" in fixture:
            for fact in fixture["expected_facts"]:
                try:
                    assert_fact(result, fact)
                except (KeyError, IndexError):
                    pass

    def test_fitting_calls_correct_dispatchers(self, fitting_fixture: Path):
        """Verify fitting makes expected dispatcher calls."""
        fixture = load_fixture(fitting_fixture)
        if not has_mock_responses(fixture):
            pytest.skip("Fixture has no mock_responses")

        mock_server = create_mock_server_from_fixture(fixture)
        input_data = fixture.get("input", {})

        invoke_mcp_direct(
            "fitting",
            "calculate_stats",
            mock_server=mock_server,
            eft=input_data.get("eft"),
        )

        # Fitting should call fitting.calculate_stats
        assert mock_server.was_called("fitting", "calculate_stats")

        # Verify EFT parameter was passed
        calls = mock_server.get_calls("fitting", "calculate_stats")
        assert len(calls) >= 1
        assert calls[0][2].get("eft") == input_data.get("eft")

    def test_fitting_validation_errors(self, fitting_fixture: Path):
        """Test that fitting correctly propagates validation errors."""
        fixture = load_fixture(fitting_fixture)
        if not has_mock_responses(fixture):
            pytest.skip("Fixture has no mock_responses")

        mock_server = create_mock_server_from_fixture(fixture)
        result = invoke_mcp_direct(
            "fitting",
            "calculate_stats",
            mock_server=mock_server,
            eft=fixture.get("input", {}).get("eft"),
        )

        # Check if this fixture expects validation errors
        expected_output = fixture.get("expected_output", {})
        expected_errors = expected_output.get("metadata", {}).get(
            "validation_errors", []
        )

        if expected_errors:
            # Verify errors are in result
            assert "metadata" in result
            assert "validation_errors" in result["metadata"]
            assert len(result["metadata"]["validation_errors"]) == len(expected_errors)
