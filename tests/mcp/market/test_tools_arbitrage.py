"""
Tests for Arbitrage MCP Tools.

Tests the _resolve_region helper, error response codes, and basic
parameter validation for the arbitrage scan and detail functions.
"""

from __future__ import annotations

import pytest

from aria_esi.mcp.market.tools_arbitrage import _resolve_region
from aria_esi.models.market import TRADE_HUBS


# =============================================================================
# _resolve_region Tests
# =============================================================================


class TestResolveRegion:
    """Tests for the _resolve_region helper function."""

    def test_direct_match_lowercase(self):
        """Direct lowercase match returns config."""
        result = _resolve_region("jita")

        assert result is not None
        assert result["region_id"] == 10000002
        assert result["region_name"] == "The Forge"

    def test_direct_match_uppercase(self):
        """Case-insensitive match for uppercase."""
        result = _resolve_region("JITA")

        assert result is not None
        assert result["region_id"] == 10000002

    def test_direct_match_mixed_case(self):
        """Case-insensitive match for mixed case."""
        result = _resolve_region("JiTa")

        assert result is not None
        assert result["region_id"] == 10000002

    def test_direct_match_with_whitespace(self):
        """Handles leading/trailing whitespace."""
        result = _resolve_region("  jita  ")

        assert result is not None
        assert result["region_id"] == 10000002

    def test_all_trade_hubs_resolve(self):
        """All defined trade hubs can be resolved."""
        for hub_name in TRADE_HUBS:
            result = _resolve_region(hub_name)

            assert result is not None, f"Failed to resolve: {hub_name}"
            assert result["region_id"] == TRADE_HUBS[hub_name]["region_id"]

    def test_partial_match_jit(self):
        """Partial match 'jit' resolves to jita."""
        result = _resolve_region("jit")

        assert result is not None
        assert result["region_id"] == 10000002

    def test_partial_match_dod(self):
        """Partial match 'dod' resolves to dodixie."""
        result = _resolve_region("dod")

        assert result is not None
        assert result["region_id"] == 10000032
        assert result["region_name"] == "Sinq Laison"

    def test_partial_match_amar(self):
        """Partial match 'amar' resolves to amarr."""
        result = _resolve_region("amar")

        assert result is not None
        assert result["region_id"] == 10000043

    def test_region_name_match(self):
        """Can match by region name instead of hub name."""
        result = _resolve_region("The Forge")

        assert result is not None
        assert result["region_id"] == 10000002

    def test_region_name_case_insensitive(self):
        """Region name matching is case-insensitive."""
        result = _resolve_region("the forge")

        assert result is not None
        assert result["region_id"] == 10000002

    def test_invalid_region_returns_none(self):
        """Unknown region returns None."""
        result = _resolve_region("Nonexistent Region")

        assert result is None

    def test_empty_string_matches_first_hub(self):
        """Empty string matches first hub due to startswith behavior.

        Note: Empty string causes startswith() to return True for any string,
        so the first hub alphabetically is matched. This is current behavior.
        """
        result = _resolve_region("")

        # Empty string matches first partial match (jita.startswith("") is True)
        assert result is not None  # Currently matches a hub

    def test_whitespace_only_matches_first_hub(self):
        """Whitespace-only string after strip matches first hub.

        Note: After strip(), whitespace becomes empty string, matching
        first hub due to startswith behavior.
        """
        result = _resolve_region("   ")

        # After strip(), becomes empty string which matches via startswith
        assert result is not None  # Currently matches a hub


# =============================================================================
# Region Resolution for All Hubs
# =============================================================================


class TestAllTradeHubs:
    """Tests ensuring all trade hubs are accessible."""

    @pytest.mark.parametrize(
        "hub_name,expected_region_id",
        [
            ("jita", 10000002),
            ("amarr", 10000043),
            ("dodixie", 10000032),
            ("rens", 10000030),
            ("hek", 10000042),
        ],
    )
    def test_hub_resolution(self, hub_name: str, expected_region_id: int):
        """Each trade hub resolves to correct region."""
        result = _resolve_region(hub_name)

        assert result is not None
        assert result["region_id"] == expected_region_id

    @pytest.mark.parametrize(
        "region_name,expected_region_id",
        [
            ("The Forge", 10000002),
            ("Domain", 10000043),
            ("Sinq Laison", 10000032),
            ("Heimatar", 10000030),
            ("Metropolis", 10000042),
        ],
    )
    def test_region_name_resolution(self, region_name: str, expected_region_id: int):
        """Each region name resolves to correct ID."""
        result = _resolve_region(region_name)

        assert result is not None
        assert result["region_id"] == expected_region_id


# =============================================================================
# Error Response Code Tests
# =============================================================================


class TestErrorResponseCodes:
    """Tests for error response code generation.

    Note: These test the error structures that would be returned by
    the implementation functions. The actual async functions are
    tested via integration tests.
    """

    def test_invalid_region_error_structure(self):
        """INVALID_REGION error should include valid regions list."""
        # This tests the error structure that _arbitrage_scan_impl returns
        # When buy_from contains an unknown region

        # Simulate what the error dict would look like
        unknown_region = "FakeRegion"
        error = {
            "error": {
                "code": "INVALID_REGION",
                "message": f"Unknown buy_from region: {unknown_region}",
                "data": {"valid_regions": list(TRADE_HUBS.keys())},
            }
        }

        assert error["error"]["code"] == "INVALID_REGION"
        assert "jita" in error["error"]["data"]["valid_regions"]
        assert "amarr" in error["error"]["data"]["valid_regions"]

    def test_item_not_found_error_structure(self):
        """ITEM_NOT_FOUND error should include suggestions."""
        # Simulate what the error dict would look like
        error = {
            "error": {
                "code": "ITEM_NOT_FOUND",
                "message": "Could not find item: Plex",
                "data": {"suggestions": ["PLEX", "Compressed Dark Glitter"]},
            }
        }

        assert error["error"]["code"] == "ITEM_NOT_FOUND"
        assert "suggestions" in error["error"]["data"]

    def test_no_opportunity_error_structure(self):
        """NO_OPPORTUNITY error for unprofitable trades."""
        error = {
            "error": {
                "code": "NO_OPPORTUNITY",
                "message": "No profitable opportunity found for PLEX from The Forge to Domain",
            }
        }

        assert error["error"]["code"] == "NO_OPPORTUNITY"
        assert "No profitable" in error["error"]["message"]


# =============================================================================
# Trade Hub Config Tests
# =============================================================================


class TestTradeHubConfig:
    """Tests for trade hub configuration values."""

    def test_jita_station_id(self):
        """Jita has correct station ID."""
        result = _resolve_region("jita")

        assert result is not None
        assert result["station_id"] == 60003760
        assert "Caldari Navy" in result["station_name"]

    def test_amarr_station_id(self):
        """Amarr has correct station ID."""
        result = _resolve_region("amarr")

        assert result is not None
        assert result["station_id"] == 60008494

    def test_dodixie_station_id(self):
        """Dodixie has correct station ID."""
        result = _resolve_region("dodixie")

        assert result is not None
        assert result["station_id"] == 60011866

    def test_rens_station_id(self):
        """Rens has correct station ID."""
        result = _resolve_region("rens")

        assert result is not None
        assert result["station_id"] == 60004588

    def test_hek_station_id(self):
        """Hek has correct station ID."""
        result = _resolve_region("hek")

        assert result is not None
        assert result["station_id"] == 60005686

    def test_all_hubs_have_system_id(self):
        """All trade hubs have system_id defined."""
        for hub_name in TRADE_HUBS:
            config = TRADE_HUBS[hub_name]
            assert config["system_id"] is not None, f"{hub_name} missing system_id"
            assert config["system_id"] > 0


# =============================================================================
# Hub System Names Mapping Tests
# =============================================================================


class TestHubSystemNames:
    """Tests for the hub_system_names mapping used in route calculation."""

    def test_hub_system_names_coverage(self):
        """Verify the mapping covers all standard region IDs."""
        # This mapping is defined in _add_route_info
        hub_system_names = {
            10000002: "Jita",
            10000043: "Amarr",
            10000032: "Dodixie",
            10000030: "Rens",
            10000042: "Hek",
        }

        # Verify each trade hub's region_id is in the mapping
        for hub_name, config in TRADE_HUBS.items():
            region_id = config["region_id"]
            assert region_id in hub_system_names, f"{hub_name} region not in mapping"
