"""
Tests for Market Analysis MCP Tools (integration-style).

Tests cross-region price comparison, item resolution, arbitrage
calculation, and region validation for the market_spread tool.
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aria_esi.mcp.market.tools_analysis import register_analysis_tools
from aria_esi.models.market import (
    ItemPrice,
    PriceAggregate,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@dataclass
class TypeInfo:
    """Mock type info returned by resolve_type_name."""

    type_id: int
    type_name: str


def _make_price(
    type_id: int,
    type_name: str,
    sell_min: float = 10.0,
    buy_max: float = 9.0,
) -> ItemPrice:
    """Factory for creating ItemPrice objects with controllable prices."""
    return ItemPrice(
        type_id=type_id,
        type_name=type_name,
        buy=PriceAggregate(
            order_count=10,
            volume=1000,
            min_price=buy_max * 0.9 if buy_max else None,
            max_price=buy_max,
            weighted_avg=buy_max * 0.95 if buy_max else None,
        ),
        sell=PriceAggregate(
            order_count=20,
            volume=2000,
            min_price=sell_min,
            max_price=sell_min * 1.1 if sell_min else None,
            weighted_avg=sell_min * 1.05 if sell_min else None,
        ),
        freshness="fresh",
    )


@pytest.fixture
def spread_tools():
    """Register analysis tools and yield tools dict with mocks."""
    server = MagicMock()
    tools = {}

    def tool_decorator():
        def decorator(func):
            tools[func.__name__] = func
            return func

        return decorator

    server.tool = tool_decorator

    with (
        patch("aria_esi.mcp.market.tools_analysis.get_market_database") as mock_db_fn,
        patch("aria_esi.mcp.market.tools_analysis.MarketCache") as mock_cache_cls,
    ):
        register_analysis_tools(server)
        yield tools, mock_db_fn, mock_cache_cls


# =============================================================================
# Happy Path Tests
# =============================================================================


class TestMarketSpreadHappyPath:
    """Tests for successful market_spread queries."""

    @pytest.mark.asyncio
    async def test_queries_all_trade_hubs_by_default(self, spread_tools):
        """Without explicit regions, queries all 5 trade hubs."""
        tools, mock_db_fn, mock_cache_cls = spread_tools

        db = MagicMock()
        mock_db_fn.return_value = db
        db.resolve_type_name.return_value = TypeInfo(34, "Tritanium")

        # Each cache instance returns prices for the queried region
        mock_cache_instance = MagicMock()
        mock_cache_cls.return_value = mock_cache_instance
        mock_cache_instance.get_prices = AsyncMock(
            return_value=[_make_price(34, "Tritanium", sell_min=6.5, buy_max=6.0)]
        )

        result = await tools["market_spread"](items=["Tritanium"])

        assert len(result["regions_queried"]) == 5
        assert "The Forge" in result["regions_queried"]
        assert "Domain" in result["regions_queried"]
        assert len(result["items"]) == 1
        assert result["items"][0]["type_name"] == "Tritanium"

    @pytest.mark.asyncio
    async def test_queries_specific_regions(self, spread_tools):
        """Queries only the requested regions."""
        tools, mock_db_fn, mock_cache_cls = spread_tools

        db = MagicMock()
        mock_db_fn.return_value = db
        db.resolve_type_name.return_value = TypeInfo(34, "Tritanium")

        mock_cache_instance = MagicMock()
        mock_cache_cls.return_value = mock_cache_instance
        mock_cache_instance.get_prices = AsyncMock(
            return_value=[_make_price(34, "Tritanium")]
        )

        result = await tools["market_spread"](
            items=["Tritanium"], regions=["jita", "amarr"]
        )

        assert len(result["regions_queried"]) == 2
        assert "The Forge" in result["regions_queried"]
        assert "Domain" in result["regions_queried"]

    @pytest.mark.asyncio
    async def test_best_buy_sell_regions_identified(self, spread_tools):
        """Identifies highest buy and lowest sell regions correctly."""
        tools, mock_db_fn, mock_cache_cls = spread_tools

        db = MagicMock()
        mock_db_fn.return_value = db
        db.resolve_type_name.return_value = TypeInfo(34, "Tritanium")

        # Return different prices per region to test best buy/sell detection
        call_count = 0
        region_prices = {
            "jita": (6.0, 5.5),      # sell_min=6.0, buy_max=5.5
            "amarr": (5.5, 5.8),     # sell_min=5.5, buy_max=5.8 (best buy)
        }

        def make_cache(**kwargs):
            nonlocal call_count
            cache = MagicMock()
            region = kwargs.get("region", "jita")
            prices = region_prices.get(region, (6.0, 5.5))
            cache.get_prices = AsyncMock(
                return_value=[_make_price(34, "Tritanium", sell_min=prices[0], buy_max=prices[1])]
            )
            call_count += 1
            return cache

        mock_cache_cls.side_effect = make_cache

        result = await tools["market_spread"](
            items=["Tritanium"], regions=["jita", "amarr"]
        )

        item_spread = result["items"][0]
        assert item_spread["best_sell_region"] == "Domain"  # Amarr has lower sell
        assert item_spread["best_buy_region"] == "Domain"   # Amarr has higher buy


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestMarketSpreadErrors:
    """Tests for error handling in market_spread."""

    @pytest.mark.asyncio
    async def test_no_items_resolved_returns_error(self, spread_tools):
        """All items failing resolution returns NO_ITEMS_RESOLVED."""
        tools, mock_db_fn, _ = spread_tools

        db = MagicMock()
        mock_db_fn.return_value = db
        db.resolve_type_name.return_value = None

        result = await tools["market_spread"](items=["FakeItem", "AnotherFake"])

        assert result["error"]["code"] == "NO_ITEMS_RESOLVED"
        assert "FakeItem" in result["error"]["data"]["unresolved"]

    @pytest.mark.asyncio
    async def test_unresolved_items_produce_warnings(self, spread_tools):
        """Partially unresolved items generate warnings but don't fail."""
        tools, mock_db_fn, mock_cache_cls = spread_tools

        db = MagicMock()
        mock_db_fn.return_value = db
        db.resolve_type_name.side_effect = lambda name: (
            TypeInfo(34, "Tritanium") if name == "Tritanium" else None
        )

        mock_cache_instance = MagicMock()
        mock_cache_cls.return_value = mock_cache_instance
        mock_cache_instance.get_prices = AsyncMock(
            return_value=[_make_price(34, "Tritanium")]
        )

        result = await tools["market_spread"](items=["Tritanium", "FakeItem"])

        assert len(result["warnings"]) >= 1
        assert "Could not resolve 1 items" in result["warnings"][0]
        assert len(result["items"]) == 1


# =============================================================================
# Region Validation Tests
# =============================================================================


class TestMarketSpreadRegionValidation:
    """Tests for region validation in market_spread."""

    @pytest.mark.asyncio
    async def test_invalid_regions_fall_back_to_all_hubs(self, spread_tools):
        """Invalid region names cause fallback to all trade hubs."""
        tools, mock_db_fn, mock_cache_cls = spread_tools

        db = MagicMock()
        mock_db_fn.return_value = db
        db.resolve_type_name.return_value = TypeInfo(34, "Tritanium")

        mock_cache_instance = MagicMock()
        mock_cache_cls.return_value = mock_cache_instance
        mock_cache_instance.get_prices = AsyncMock(
            return_value=[_make_price(34, "Tritanium")]
        )

        result = await tools["market_spread"](
            items=["Tritanium"], regions=["nonexistent1", "nonexistent2"]
        )

        # Falls back to all 5 trade hubs
        assert len(result["regions_queried"]) == 5


# =============================================================================
# Arbitrage Calculation Tests
# =============================================================================


class TestMarketSpreadArbitrage:
    """Tests for arbitrage profit calculation."""

    @pytest.mark.asyncio
    async def test_positive_arbitrage_calculated(self, spread_tools):
        """Arbitrage profit is calculated when buy > sell across regions."""
        tools, mock_db_fn, mock_cache_cls = spread_tools

        db = MagicMock()
        mock_db_fn.return_value = db
        db.resolve_type_name.return_value = TypeInfo(34, "Tritanium")

        # Jita: buy_max=10.0 (best buy), Amarr: sell_min=8.0 (best sell)
        region_prices = {
            "jita": (9.0, 10.0),   # sell_min=9.0, buy_max=10.0
            "amarr": (8.0, 9.0),   # sell_min=8.0, buy_max=9.0
        }

        def make_cache(**kwargs):
            cache = MagicMock()
            region = kwargs.get("region", "jita")
            prices = region_prices.get(region, (9.0, 10.0))
            cache.get_prices = AsyncMock(
                return_value=[_make_price(34, "Tritanium", sell_min=prices[0], buy_max=prices[1])]
            )
            return cache

        mock_cache_cls.side_effect = make_cache

        result = await tools["market_spread"](
            items=["Tritanium"], regions=["jita", "amarr"]
        )

        item_spread = result["items"][0]
        # Arbitrage = best_buy_price - best_sell_price = 10.0 - 8.0 = 2.0
        assert item_spread["arbitrage_profit"] == 2.0
        assert item_spread["arbitrage_percent"] == 25.0  # 2.0 / 8.0 * 100

    @pytest.mark.asyncio
    async def test_no_arbitrage_when_sell_exceeds_buy(self, spread_tools):
        """No arbitrage profit when best sell > best buy."""
        tools, mock_db_fn, mock_cache_cls = spread_tools

        db = MagicMock()
        mock_db_fn.return_value = db
        db.resolve_type_name.return_value = TypeInfo(34, "Tritanium")

        # Both regions have sell_min > buy_max (no arbitrage)
        mock_cache_instance = MagicMock()
        mock_cache_cls.return_value = mock_cache_instance
        mock_cache_instance.get_prices = AsyncMock(
            return_value=[_make_price(34, "Tritanium", sell_min=10.0, buy_max=8.0)]
        )

        result = await tools["market_spread"](
            items=["Tritanium"], regions=["jita", "amarr"]
        )

        item_spread = result["items"][0]
        # buy_max (8.0) - sell_min (10.0) = -2.0, which is negative, so None
        assert item_spread["arbitrage_profit"] is None
        assert item_spread["arbitrage_percent"] is None
