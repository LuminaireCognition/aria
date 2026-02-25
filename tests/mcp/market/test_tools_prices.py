"""
Tests for Market Price MCP Tools.

Tests item resolution, region handling, cache source selection,
freshness aggregation, and cache status reporting for the
market_prices and market_cache_status tools.
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aria_esi.mcp.market.tools_prices import register_price_tools
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
    freshness: str = "fresh",
) -> ItemPrice:
    """Factory for creating ItemPrice objects."""
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
        freshness=freshness,
    )


@pytest.fixture
def price_tools():
    """Register price tools and yield tools dict with mocks."""
    server = MagicMock()
    tools = {}

    def tool_decorator():
        def decorator(func):
            tools[func.__name__] = func
            return func

        return decorator

    server.tool = tool_decorator

    with (
        patch("aria_esi.mcp.market.tools_prices.get_market_database") as mock_db_fn,
        patch("aria_esi.mcp.market.tools_prices.MarketCache") as mock_cache_cls,
        patch("aria_esi.mcp.market.tools_prices.get_market_cache") as mock_get_cache,
    ):
        register_price_tools(server)
        yield tools, mock_db_fn, mock_cache_cls, mock_get_cache


# =============================================================================
# market_prices Tests
# =============================================================================


class TestMarketPrices:
    """Tests for the market_prices tool."""

    @pytest.mark.asyncio
    async def test_happy_path_jita(self, price_tools):
        """Resolves items and returns prices from Jita."""
        tools, mock_db_fn, mock_cache_cls, _ = price_tools

        # Configure mock DB
        db = MagicMock()
        mock_db_fn.return_value = db
        db.resolve_type_name.side_effect = lambda name: {
            "Tritanium": TypeInfo(34, "Tritanium"),
            "Pyerite": TypeInfo(35, "Pyerite"),
        }.get(name)

        # Configure mock cache
        mock_cache_instance = MagicMock()
        mock_cache_cls.return_value = mock_cache_instance
        mock_cache_instance.get_prices = AsyncMock(
            return_value=[
                _make_price(34, "Tritanium"),
                _make_price(35, "Pyerite"),
            ]
        )
        mock_cache_instance.get_cache_status.return_value = {
            "fuzzwork": {"cached_types": 2, "age_seconds": 60, "ttl_seconds": 900, "stale": False},
        }

        result = await tools["market_prices"](items=["Tritanium", "Pyerite"])

        assert result["region"] == "The Forge"
        assert result["source"] == "fuzzwork"
        assert len(result["items"]) == 2
        assert result["warnings"] == []
        assert result["unresolved_items"] == []

    @pytest.mark.asyncio
    async def test_unresolved_items_produce_warnings(self, price_tools):
        """Unresolved items are listed in warnings."""
        tools, mock_db_fn, mock_cache_cls, _ = price_tools

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
        mock_cache_instance.get_cache_status.return_value = {
            "fuzzwork": {"cached_types": 1, "age_seconds": 60, "ttl_seconds": 900, "stale": False},
        }

        result = await tools["market_prices"](items=["Tritanium", "FakeItem", "AnotherFake"])

        assert len(result["warnings"]) >= 1
        assert "Could not resolve 2 items" in result["warnings"][0]
        assert result["unresolved_items"] == ["FakeItem", "AnotherFake"]

    @pytest.mark.asyncio
    async def test_unknown_region_falls_back_to_jita(self, price_tools):
        """Unknown region name falls back to Jita."""
        tools, mock_db_fn, mock_cache_cls, _ = price_tools

        db = MagicMock()
        mock_db_fn.return_value = db
        db.resolve_type_name.return_value = TypeInfo(34, "Tritanium")

        mock_cache_instance = MagicMock()
        mock_cache_cls.return_value = mock_cache_instance
        mock_cache_instance.get_prices = AsyncMock(
            return_value=[_make_price(34, "Tritanium")]
        )
        mock_cache_instance.get_cache_status.return_value = {
            "fuzzwork": {"cached_types": 1, "age_seconds": 30, "ttl_seconds": 900, "stale": False},
        }

        # Patch resolve_region to return None for unknown, then Jita for fallback
        with patch("aria_esi.mcp.market.tools_prices.resolve_region") as mock_resolve:
            mock_resolve.side_effect = lambda name: (
                None
                if name == "nonexistent_region"
                else {
                    "region_id": 10000002,
                    "region_name": "The Forge",
                    "station_id": 60003760,
                    "station_name": "Jita IV - Moon 4 - Caldari Navy Assembly Plant",
                    "system_id": 30000142,
                }
            )

            result = await tools["market_prices"](
                items=["Tritanium"], region="nonexistent_region"
            )

        assert result["region"] == "The Forge"
        assert result["source"] == "fuzzwork"

    @pytest.mark.asyncio
    async def test_non_trade_hub_region_uses_esi_source(self, price_tools):
        """Non-trade-hub regions use ESI source instead of Fuzzwork."""
        tools, mock_db_fn, mock_cache_cls, _ = price_tools

        db = MagicMock()
        mock_db_fn.return_value = db
        db.resolve_type_name.return_value = TypeInfo(34, "Tritanium")

        mock_cache_instance = MagicMock()
        mock_cache_cls.return_value = mock_cache_instance
        mock_cache_instance.get_prices = AsyncMock(
            return_value=[_make_price(34, "Tritanium")]
        )
        mock_cache_instance.get_cache_status.return_value = {}

        with patch("aria_esi.mcp.market.tools_prices.resolve_region") as mock_resolve:
            # Non-trade-hub region has no station_id
            mock_resolve.return_value = {
                "region_id": 10000064,
                "region_name": "Essence",
                "station_id": None,
                "station_name": None,
                "system_id": None,
            }

            result = await tools["market_prices"](
                items=["Tritanium"], region="Essence"
            )

        assert result["source"] == "esi"
        assert result["station"] is None

    @pytest.mark.asyncio
    async def test_freshness_aggregation_stale_overrides(self, price_tools):
        """Overall freshness is stale if any item is stale."""
        tools, mock_db_fn, mock_cache_cls, _ = price_tools

        db = MagicMock()
        mock_db_fn.return_value = db
        db.resolve_type_name.side_effect = lambda name: {
            "Tritanium": TypeInfo(34, "Tritanium"),
            "Pyerite": TypeInfo(35, "Pyerite"),
        }.get(name)

        mock_cache_instance = MagicMock()
        mock_cache_cls.return_value = mock_cache_instance
        mock_cache_instance.get_prices = AsyncMock(
            return_value=[
                _make_price(34, "Tritanium", freshness="fresh"),
                _make_price(35, "Pyerite", freshness="stale"),
            ]
        )
        mock_cache_instance.get_cache_status.return_value = {
            "fuzzwork": {"cached_types": 2, "age_seconds": 2000, "ttl_seconds": 900, "stale": True},
        }

        result = await tools["market_prices"](items=["Tritanium", "Pyerite"])

        assert result["freshness"] == "stale"


# =============================================================================
# market_cache_status Tests
# =============================================================================


class TestMarketCacheStatus:
    """Tests for the market_cache_status tool."""

    @pytest.mark.asyncio
    async def test_returns_structured_result(self, price_tools):
        """Cache status returns properly structured result with all layers."""
        tools, mock_db_fn, _, mock_get_cache = price_tools

        # Configure cache status
        mock_cache = MagicMock()
        mock_get_cache.return_value = mock_cache
        mock_cache.get_cache_status.return_value = {
            "fuzzwork": {
                "cached_types": 100,
                "age_seconds": 120,
                "ttl_seconds": 900,
                "stale": False,
                "last_error": None,
            },
            "esi_orders": {
                "cached_types": 5,
                "age_seconds": 60,
                "ttl_seconds": 300,
                "stale": False,
                "last_error": None,
            },
        }

        # Configure DB stats
        db = MagicMock()
        mock_db_fn.return_value = db
        db.get_stats.return_value = {
            "database_path": "/tmp/market.db",
            "database_size_mb": 15.234,
            "type_count": 45000,
        }

        result = await tools["market_cache_status"]()

        assert result["fuzzwork"]["cached_types"] == 100
        assert result["fuzzwork"]["stale"] is False
        assert result["esi_orders"]["cached_types"] == 5
        assert result["database_path"] == "/tmp/market.db"
        assert result["database_size_mb"] == 15.23
        assert result["type_count"] == 45000
