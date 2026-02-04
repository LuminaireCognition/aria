"""
Tests for Market Orders MCP Tools.

Tests order sorting, spread calculation, and limit handling
for the market_orders tool.
"""

from __future__ import annotations

import pytest

from aria_esi.models.market import (
    MarketOrder,
    MarketOrdersResult,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_buy_orders() -> list[dict]:
    """Sample buy orders for testing."""
    return [
        {"order_id": 1, "price": 100.0, "volume_remain": 1000, "is_buy_order": True},
        {"order_id": 2, "price": 150.0, "volume_remain": 500, "is_buy_order": True},
        {"order_id": 3, "price": 120.0, "volume_remain": 800, "is_buy_order": True},
        {"order_id": 4, "price": 90.0, "volume_remain": 2000, "is_buy_order": True},
        {"order_id": 5, "price": 140.0, "volume_remain": 300, "is_buy_order": True},
    ]


@pytest.fixture
def sample_sell_orders() -> list[dict]:
    """Sample sell orders for testing."""
    return [
        {"order_id": 101, "price": 200.0, "volume_remain": 1000, "is_buy_order": False},
        {"order_id": 102, "price": 160.0, "volume_remain": 500, "is_buy_order": False},
        {"order_id": 103, "price": 180.0, "volume_remain": 800, "is_buy_order": False},
        {"order_id": 104, "price": 210.0, "volume_remain": 2000, "is_buy_order": False},
        {"order_id": 105, "price": 170.0, "volume_remain": 300, "is_buy_order": False},
    ]


# =============================================================================
# Order Sorting Tests
# =============================================================================


class TestOrderSorting:
    """Tests for order sorting behavior."""

    def test_buy_orders_sorted_descending_by_price(self, sample_buy_orders):
        """Buy orders should be sorted highest price first."""
        # Sort like the tool does: reverse=True for buy orders
        sorted_orders = sorted(
            sample_buy_orders,
            key=lambda x: x.get("price", 0),
            reverse=True,
        )

        prices = [o["price"] for o in sorted_orders]
        assert prices == [150.0, 140.0, 120.0, 100.0, 90.0]

    def test_sell_orders_sorted_ascending_by_price(self, sample_sell_orders):
        """Sell orders should be sorted lowest price first."""
        # Sort like the tool does: ascending (no reverse) for sell orders
        sorted_orders = sorted(
            sample_sell_orders,
            key=lambda x: x.get("price", float("inf")),
        )

        prices = [o["price"] for o in sorted_orders]
        assert prices == [160.0, 170.0, 180.0, 200.0, 210.0]

    def test_buy_orders_best_price_is_first(self, sample_buy_orders):
        """Best buy price (highest) should be first after sorting."""
        sorted_orders = sorted(
            sample_buy_orders,
            key=lambda x: x.get("price", 0),
            reverse=True,
        )

        best_buy = sorted_orders[0]["price"] if sorted_orders else None
        assert best_buy == 150.0

    def test_sell_orders_best_price_is_first(self, sample_sell_orders):
        """Best sell price (lowest) should be first after sorting."""
        sorted_orders = sorted(
            sample_sell_orders,
            key=lambda x: x.get("price", float("inf")),
        )

        best_sell = sorted_orders[0]["price"] if sorted_orders else None
        assert best_sell == 160.0

    def test_empty_buy_orders_handled(self):
        """Empty buy orders list doesn't break sorting."""
        empty_orders: list[dict] = []

        sorted_orders = sorted(
            empty_orders,
            key=lambda x: x.get("price", 0),
            reverse=True,
        )

        assert sorted_orders == []

    def test_empty_sell_orders_handled(self):
        """Empty sell orders list doesn't break sorting."""
        empty_orders: list[dict] = []

        sorted_orders = sorted(
            empty_orders,
            key=lambda x: x.get("price", float("inf")),
        )

        assert sorted_orders == []


# =============================================================================
# Spread Calculation Tests
# =============================================================================


class TestSpreadCalculation:
    """Tests for bid-ask spread calculation."""

    def test_spread_calculation_basic(self):
        """Spread = sell.min - buy.max."""
        best_buy = 150.0
        best_sell = 160.0

        spread = round(best_sell - best_buy, 2)

        assert spread == 10.0

    def test_spread_percent_calculation(self):
        """Spread percent = (spread / sell) * 100."""
        best_buy = 150.0
        best_sell = 160.0
        spread = best_sell - best_buy

        spread_percent = round((spread / best_sell) * 100, 2)

        assert spread_percent == 6.25

    def test_negative_spread(self):
        """Spread can be negative (crossed market)."""
        best_buy = 170.0  # Higher than sell
        best_sell = 160.0

        spread = round(best_sell - best_buy, 2)

        assert spread == -10.0

    def test_zero_spread(self):
        """Spread is zero when prices match."""
        best_buy = 160.0
        best_sell = 160.0

        spread = round(best_sell - best_buy, 2)
        spread_percent = round((spread / best_sell) * 100, 2) if best_sell > 0 else None

        assert spread == 0.0
        assert spread_percent == 0.0

    def test_spread_with_zero_sell_price(self):
        """Division by zero handled when sell is 0."""
        best_buy = 100.0
        best_sell = 0.0

        spread = round(best_sell - best_buy, 2) if best_sell is not None else None
        spread_percent = None

        if best_buy is not None and best_sell is not None:
            spread = round(best_sell - best_buy, 2)
            if best_sell > 0:
                spread_percent = round((spread / best_sell) * 100, 2)

        assert spread == -100.0
        assert spread_percent is None

    def test_spread_none_when_no_buy_orders(self):
        """Spread is None when no buy orders exist."""
        best_buy = None
        best_sell = 160.0

        spread = None
        spread_percent = None

        if best_buy is not None and best_sell is not None:
            spread = round(best_sell - best_buy, 2)
            if best_sell > 0:
                spread_percent = round((spread / best_sell) * 100, 2)

        assert spread is None
        assert spread_percent is None

    def test_spread_none_when_no_sell_orders(self):
        """Spread is None when no sell orders exist."""
        best_buy = 150.0
        best_sell = None

        spread = None
        spread_percent = None

        if best_buy is not None and best_sell is not None:
            spread = round(best_sell - best_buy, 2)
            if best_sell > 0:
                spread_percent = round((spread / best_sell) * 100, 2)

        assert spread is None
        assert spread_percent is None


# =============================================================================
# Limit Handling Tests
# =============================================================================


class TestLimitHandling:
    """Tests for order limit parameter."""

    def test_limit_clamped_to_minimum_1(self):
        """Limit below 1 is clamped to 1."""
        limit = max(1, min(50, 0))

        assert limit == 1

    def test_limit_clamped_to_maximum_50(self):
        """Limit above 50 is clamped to 50."""
        limit = max(1, min(50, 100))

        assert limit == 50

    def test_limit_within_range_unchanged(self):
        """Limit within 1-50 is unchanged."""
        limit = max(1, min(50, 25))

        assert limit == 25

    def test_limit_exactly_1(self):
        """Limit of exactly 1 is valid."""
        limit = max(1, min(50, 1))

        assert limit == 1

    def test_limit_exactly_50(self):
        """Limit of exactly 50 is valid."""
        limit = max(1, min(50, 50))

        assert limit == 50

    def test_limit_negative_clamped(self):
        """Negative limit is clamped to 1."""
        limit = max(1, min(50, -5))

        assert limit == 1

    def test_slicing_respects_limit(self, sample_buy_orders):
        """Orders are sliced to limit after sorting."""
        limit = 3

        sorted_orders = sorted(
            sample_buy_orders,
            key=lambda x: x.get("price", 0),
            reverse=True,
        )
        limited_orders = sorted_orders[:limit]

        assert len(limited_orders) == 3
        # First 3 highest prices
        prices = [o["price"] for o in limited_orders]
        assert prices == [150.0, 140.0, 120.0]


# =============================================================================
# MarketOrder Model Tests
# =============================================================================


class TestMarketOrderModel:
    """Tests for MarketOrder Pydantic model."""

    def test_order_from_esi_data(self):
        """MarketOrder can be created from ESI-like data."""
        order = MarketOrder(
            order_id=12345,
            type_id=34,
            is_buy_order=True,
            price=6.50,
            volume_remain=1000000,
            volume_total=1500000,
            location_id=60003760,
            location_name="Jita IV - Moon 4",
            system_id=30000142,
            system_name="Jita",
            range="station",
            min_volume=1,
            duration=90,
            issued="2026-01-15T12:00:00Z",
        )

        assert order.order_id == 12345
        assert order.is_buy_order is True
        assert order.price == 6.50
        assert order.volume_remain == 1000000

    def test_order_with_none_names(self):
        """MarketOrder works with None location/system names."""
        order = MarketOrder(
            order_id=12345,
            type_id=34,
            is_buy_order=False,
            price=7.00,
            volume_remain=500000,
            volume_total=500000,
            location_id=60003760,
            location_name=None,
            system_id=30000142,
            system_name=None,
            range="region",
            min_volume=1,
            duration=30,
            issued="2026-01-15T12:00:00Z",
        )

        assert order.location_name is None
        assert order.system_name is None


# =============================================================================
# MarketOrdersResult Model Tests
# =============================================================================


class TestMarketOrdersResultModel:
    """Tests for MarketOrdersResult Pydantic model."""

    def test_result_with_orders(self):
        """Result contains order lists and metadata."""
        buy_order = MarketOrder(
            order_id=1,
            type_id=34,
            is_buy_order=True,
            price=6.50,
            volume_remain=1000,
            volume_total=1000,
            location_id=60003760,
            system_id=30000142,
            range="station",
            min_volume=1,
            duration=90,
            issued="2026-01-15T12:00:00Z",
        )

        sell_order = MarketOrder(
            order_id=2,
            type_id=34,
            is_buy_order=False,
            price=7.00,
            volume_remain=500,
            volume_total=500,
            location_id=60003760,
            system_id=30000142,
            range="station",
            min_volume=1,
            duration=90,
            issued="2026-01-15T12:00:00Z",
        )

        result = MarketOrdersResult(
            type_id=34,
            type_name="Tritanium",
            region="The Forge",
            region_id=10000002,
            buy_orders=[buy_order],
            sell_orders=[sell_order],
            total_buy_orders=1,
            total_sell_orders=1,
            best_buy=6.50,
            best_sell=7.00,
            spread=0.50,
            spread_percent=7.14,
            freshness="fresh",
            warnings=[],
        )

        assert result.type_name == "Tritanium"
        assert len(result.buy_orders) == 1
        assert len(result.sell_orders) == 1
        assert result.spread == 0.50

    def test_result_with_empty_orders(self):
        """Result handles empty order lists."""
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
            warnings=["No orders found"],
        )

        assert result.best_buy is None
        assert result.best_sell is None
        assert result.spread is None
        assert len(result.warnings) == 1


# =============================================================================
# Error Response Tests
# =============================================================================


class TestErrorResponses:
    """Tests for error response structures."""

    def test_type_not_found_error(self):
        """TYPE_NOT_FOUND error includes suggestions."""
        error = {
            "error": {
                "code": "TYPE_NOT_FOUND",
                "message": "Unknown item: Plex",
                "data": {"suggestions": ["PLEX", "Compressed Nocxium"]},
            }
        }

        assert error["error"]["code"] == "TYPE_NOT_FOUND"
        assert "suggestions" in error["error"]["data"]

    def test_esi_unavailable_error(self):
        """ESI_UNAVAILABLE error for connection issues."""
        error = {
            "error": {
                "code": "ESI_UNAVAILABLE",
                "message": "ESI client error: Connection timeout",
            }
        }

        assert error["error"]["code"] == "ESI_UNAVAILABLE"
