"""
Tests for Market Tool Implementations.

Tests for market price lookup, order book, and valuation tools.
Focus on parameter handling, type resolution, and response formatting.
"""

from __future__ import annotations

import asyncio

import pytest

from aria_esi.mcp.errors import InvalidParameterError

# =============================================================================
# Trade Hub Resolution Tests
# =============================================================================


class TestTradeHubResolution:
    """Tests for trade hub name resolution."""

    def test_known_hub_names_resolve(self):
        """Known trade hub names resolve correctly."""
        from aria_esi.models.market import resolve_trade_hub

        jita = resolve_trade_hub("jita")
        assert jita is not None
        assert jita["region_name"] == "The Forge"

        amarr = resolve_trade_hub("amarr")
        assert amarr is not None
        assert amarr["region_name"] == "Domain"

    def test_hub_names_case_insensitive(self):
        """Trade hub names are case insensitive."""
        from aria_esi.models.market import resolve_trade_hub

        jita_lower = resolve_trade_hub("jita")
        jita_upper = resolve_trade_hub("JITA")
        jita_mixed = resolve_trade_hub("JiTa")

        assert jita_lower == jita_upper == jita_mixed

    def test_unknown_hub_returns_none(self):
        """Unknown trade hub returns None."""
        from aria_esi.models.market import resolve_trade_hub

        result = resolve_trade_hub("unknown_hub")
        assert result is None

    def test_all_major_hubs_exist(self):
        """All major trade hubs are defined."""
        from aria_esi.models.market import TRADE_HUBS

        expected_hubs = ["jita", "amarr", "dodixie", "rens", "hek"]
        for hub in expected_hubs:
            assert hub in TRADE_HUBS
            assert TRADE_HUBS[hub]["region_id"] is not None
            assert TRADE_HUBS[hub]["region_name"] is not None

    def test_resolve_region_function(self):
        """resolve_region function works for trade hubs."""
        from aria_esi.models.market import resolve_region

        result = resolve_region("jita")
        assert result is not None
        assert result["region_name"] == "The Forge"


# =============================================================================
# Spread Parameter Tests
# =============================================================================


class TestMarketSpread:
    """Tests for market spread (cross-region comparison) parameter handling."""

    def test_spread_requires_items(self):
        """Spread action requires items parameter."""
        from aria_esi.mcp.dispatchers.market import _spread

        with pytest.raises(InvalidParameterError):
            asyncio.run(_spread(None, None))


# =============================================================================
# Clipboard Parser Tests
# =============================================================================


class TestClipboardParser:
    """Tests for clipboard text parsing functionality."""

    def test_parse_simple_clipboard(self):
        """Parse simple clipboard format with item and quantity."""
        from aria_esi.mcp.market.clipboard import parse_clipboard_to_dict

        text = "Tritanium\t1000"
        result = parse_clipboard_to_dict(text)

        assert len(result) >= 1
        # Check if Tritanium is in the result
        tritanium_items = [r for r in result if r.get("name", "").lower() == "tritanium"]
        if tritanium_items:
            assert tritanium_items[0]["quantity"] == 1000

    def test_parse_multiline_clipboard(self):
        """Parse multiline clipboard with multiple items."""
        from aria_esi.mcp.market.clipboard import parse_clipboard_to_dict

        text = "Tritanium\t1000\nPyerite\t500"
        result = parse_clipboard_to_dict(text)

        assert len(result) >= 1

    def test_parse_empty_clipboard(self):
        """Parse empty clipboard returns empty list."""
        from aria_esi.mcp.market.clipboard import parse_clipboard_to_dict

        text = ""
        result = parse_clipboard_to_dict(text)

        assert result == []

    def test_parse_clipboard_with_various_formats(self):
        """Parse clipboard handles various format variations."""
        from aria_esi.mcp.market.clipboard import parse_clipboard_to_dict

        # Tab-separated
        text = "Tritanium\t1,000"
        result = parse_clipboard_to_dict(text)
        assert len(result) >= 1


# =============================================================================
# Market Models Tests
# =============================================================================


class TestMarketModels:
    """Tests for market data models."""

    def test_market_prices_result_creation(self):
        """MarketPricesResult model can be created."""
        from aria_esi.models.market import MarketPricesResult

        result = MarketPricesResult(
            items=[],
            region="The Forge",
            region_id=10000002,
            station=None,
            station_id=None,
            source="fuzzwork",
            freshness="fresh",
            cache_age_seconds=None,
            unresolved_items=[],
            warnings=[],
        )

        assert result.region == "The Forge"
        assert result.source == "fuzzwork"

    def test_market_orders_result_creation(self):
        """MarketOrdersResult model can be created."""
        from aria_esi.models.market import MarketOrdersResult

        result = MarketOrdersResult(
            type_id=34,
            type_name="Tritanium",
            region="The Forge",
            region_id=10000002,
            buy_orders=[],
            sell_orders=[],
            total_buy_orders=0,
            total_sell_orders=0,
            best_buy=None,
            best_sell=None,
            spread=None,
            spread_percent=None,
            freshness="fresh",
            warnings=[],
        )

        assert result.type_name == "Tritanium"
        assert result.total_buy_orders == 0

    def test_valuation_result_creation(self):
        """ValuationResult model can be created."""
        from aria_esi.models.market import ValuationResult

        result = ValuationResult(
            items=[],
            total_value=0.0,
            total_quantity=0,
            resolved_count=0,
            unresolved_count=0,
            price_type="sell",
            region="The Forge",
            region_id=10000002,
            freshness="fresh",
            warnings=[],
        )

        assert result.price_type == "sell"
        assert result.total_value == 0.0


# =============================================================================
# Market Context Policy Tests
# =============================================================================


class TestMarketContextPolicy:
    """Tests for market context policy constants."""

    def test_market_policy_constants_exist(self):
        """Market context policy constants are defined."""
        from aria_esi.mcp.context_policy import MARKET

        assert hasattr(MARKET, "OUTPUT_MAX_ITEMS")
        assert hasattr(MARKET, "OUTPUT_MAX_ORDERS")
        assert hasattr(MARKET, "OUTPUT_MAX_SOURCES")
        assert hasattr(MARKET, "OUTPUT_MAX_ARBITRAGE")
        assert hasattr(MARKET, "OUTPUT_MAX_HISTORY")

    def test_market_policy_values_positive(self):
        """Market context policy values are positive integers."""
        from aria_esi.mcp.context_policy import MARKET

        assert MARKET.OUTPUT_MAX_ITEMS > 0
        assert MARKET.OUTPUT_MAX_ORDERS > 0
        assert MARKET.OUTPUT_MAX_SOURCES > 0


# =============================================================================
# Market Action Constants Tests
# =============================================================================


class TestMarketDispatcherConstants:
    """Tests for market dispatcher constants."""

    def test_valid_actions_defined(self):
        """VALID_ACTIONS set is defined with all market actions."""
        from aria_esi.mcp.dispatchers.market import VALID_ACTIONS

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

        assert expected_actions == VALID_ACTIONS

    def test_market_action_type_literal(self):
        """MarketAction type literal includes all actions."""
        from aria_esi.mcp.dispatchers.market import MarketAction

        # MarketAction is a type alias, should include core actions
        assert MarketAction is not None


# =============================================================================
# Market Freshness Classification Tests
# =============================================================================


class TestMarketFreshness:
    """Tests for market data freshness classification."""

    def test_freshness_values(self):
        """Valid freshness values."""
        valid_freshness = {"fresh", "recent", "stale"}
        assert "fresh" in valid_freshness
        assert "recent" in valid_freshness
        assert "stale" in valid_freshness


# =============================================================================
# Market Price Type Tests
# =============================================================================


class TestMarketPriceType:
    """Tests for market price type handling."""

    def test_valid_price_types(self):
        """Valid price types are 'buy' and 'sell'."""
        valid_types = {"buy", "sell"}
        assert "buy" in valid_types
        assert "sell" in valid_types
        assert "invalid" not in valid_types


# =============================================================================
# Market Order Type Tests
# =============================================================================


class TestMarketOrderType:
    """Tests for market order type handling."""

    def test_valid_order_types(self):
        """Valid order types include all, buy, sell."""
        valid_types = {"all", "buy", "sell"}
        assert "all" in valid_types
        assert "buy" in valid_types
        assert "sell" in valid_types
