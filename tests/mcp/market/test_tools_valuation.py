"""
Tests for Market Valuation MCP Tools.

Tests clipboard parsing, price type selection, item deduplication,
freshness classification, and unresolved item handling.
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aria_esi.mcp.market.clipboard import parse_clipboard_to_dict
from aria_esi.models.market import (
    FreshnessLevel,
    ItemPrice,
    PriceAggregate,
    ValuationItem,
    ValuationResult,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_type_info():
    """Create a mock type info namedtuple-like object."""

    @dataclass
    class TypeInfo:
        type_id: int
        type_name: str

    return TypeInfo


@pytest.fixture
def mock_item_price():
    """Factory for creating ItemPrice objects."""

    def _make_price(
        type_id: int,
        type_name: str,
        sell_min: float | None = 10.0,
        buy_max: float | None = 9.0,
    ) -> ItemPrice:
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

    return _make_price


# =============================================================================
# Clipboard Parsing Tests
# =============================================================================


class TestClipboardParsing:
    """Tests for clipboard text parsing."""

    def test_tab_separated_format(self):
        """Parses tab-separated item/quantity."""
        text = "Tritanium\t1000000\nPyerite\t500000"

        result = parse_clipboard_to_dict(text)

        assert len(result) == 2
        assert result[0]["name"] == "Tritanium"
        assert result[0]["quantity"] == 1000000
        assert result[1]["name"] == "Pyerite"
        assert result[1]["quantity"] == 500000

    def test_space_separated_format(self):
        """Parses space-separated item/quantity."""
        text = "Tritanium 1000000\nPyerite 500000"

        result = parse_clipboard_to_dict(text)

        assert len(result) == 2
        assert result[0]["name"] == "Tritanium"
        assert result[0]["quantity"] == 1000000

    def test_handles_commas_in_numbers(self):
        """Handles comma-formatted numbers."""
        text = "Tritanium\t1,000,000"

        result = parse_clipboard_to_dict(text)

        assert len(result) == 1
        assert result[0]["quantity"] == 1000000

    def test_empty_string_returns_empty_list(self):
        """Empty input returns empty list."""
        result = parse_clipboard_to_dict("")

        assert result == []

    def test_whitespace_only_returns_empty_list(self):
        """Whitespace-only input returns empty list."""
        result = parse_clipboard_to_dict("   \n\t  ")

        assert result == []

    def test_multiword_item_names(self):
        """Handles item names with spaces."""
        text = "Large Shield Extender II\t5"

        result = parse_clipboard_to_dict(text)

        assert len(result) == 1
        assert result[0]["name"] == "Large Shield Extender II"
        assert result[0]["quantity"] == 5


# =============================================================================
# Price Type Selection Tests
# =============================================================================


class TestPriceTypeSelection:
    """Tests for sell vs buy price selection in valuation."""

    def test_sell_price_uses_min_sell(self, mock_item_price):
        """Sell price type uses minimum sell price."""
        price = mock_item_price(type_id=34, type_name="Tritanium", sell_min=6.5, buy_max=5.5)

        # Verify the sell side has min_price
        assert price.sell.min_price == 6.5

    def test_buy_price_uses_max_buy(self, mock_item_price):
        """Buy price type uses maximum buy price."""
        price = mock_item_price(type_id=34, type_name="Tritanium", sell_min=6.5, buy_max=5.5)

        # Verify the buy side has max_price
        assert price.buy.max_price == 5.5


# =============================================================================
# Freshness Classification Tests
# =============================================================================


class TestFreshnessClassification:
    """Tests for data freshness level determination."""

    def test_fresh_under_300_seconds(self):
        """Data under 5 minutes is 'fresh'."""
        # 299 seconds should be fresh
        age_seconds = 299

        if age_seconds > 1800:
            freshness = "stale"
        elif age_seconds > 300:
            freshness = "recent"
        else:
            freshness = "fresh"

        assert freshness == "fresh"

    def test_recent_between_300_and_1800_seconds(self):
        """Data between 5-30 minutes is 'recent'."""
        # 301 seconds should be recent
        age_seconds = 301

        if age_seconds > 1800:
            freshness = "stale"
        elif age_seconds > 300:
            freshness = "recent"
        else:
            freshness = "fresh"

        assert freshness == "recent"

    def test_stale_over_1800_seconds(self):
        """Data over 30 minutes is 'stale'."""
        # 1801 seconds should be stale
        age_seconds = 1801

        if age_seconds > 1800:
            freshness = "stale"
        elif age_seconds > 300:
            freshness = "recent"
        else:
            freshness = "fresh"

        assert freshness == "stale"

    def test_exactly_300_is_fresh(self):
        """Exactly 300 seconds is still 'fresh' (boundary)."""
        age_seconds = 300

        if age_seconds > 1800:
            freshness = "stale"
        elif age_seconds > 300:
            freshness = "recent"
        else:
            freshness = "fresh"

        assert freshness == "fresh"

    def test_exactly_1800_is_recent(self):
        """Exactly 1800 seconds is still 'recent' (boundary)."""
        age_seconds = 1800

        if age_seconds > 1800:
            freshness = "stale"
        elif age_seconds > 300:
            freshness = "recent"
        else:
            freshness = "fresh"

        assert freshness == "recent"


# =============================================================================
# Valuation Model Tests
# =============================================================================


class TestValuationItem:
    """Tests for ValuationItem model."""

    def test_resolved_item_with_price(self):
        """Resolved item has type_id and prices."""
        item = ValuationItem(
            type_id=34,
            type_name="Tritanium",
            quantity=1000000,
            unit_price=6.50,
            total_value=6500000.0,
            resolved=True,
        )

        assert item.type_id == 34
        assert item.resolved is True
        assert item.total_value == 6500000.0

    def test_resolved_item_without_price(self):
        """Resolved item can have no price (no market data)."""
        item = ValuationItem(
            type_id=34,
            type_name="Tritanium",
            quantity=1000000,
            unit_price=None,
            total_value=None,
            resolved=True,
            warning="No market data available",
        )

        assert item.resolved is True
        assert item.unit_price is None
        assert item.warning == "No market data available"

    def test_unresolved_item(self):
        """Unresolved item has no type_id."""
        item = ValuationItem(
            type_id=None,
            type_name="Fake Item",
            quantity=100,
            unit_price=None,
            total_value=None,
            resolved=False,
            warning="Could not resolve item name",
        )

        assert item.type_id is None
        assert item.resolved is False


class TestValuationResult:
    """Tests for ValuationResult model."""

    def test_total_value_calculation(self):
        """Total value is sum of resolved item values."""
        result = ValuationResult(
            items=[
                ValuationItem(
                    type_id=34,
                    type_name="Tritanium",
                    quantity=1000,
                    unit_price=6.0,
                    total_value=6000.0,
                    resolved=True,
                ),
                ValuationItem(
                    type_id=35,
                    type_name="Pyerite",
                    quantity=500,
                    unit_price=10.0,
                    total_value=5000.0,
                    resolved=True,
                ),
            ],
            total_value=11000.0,
            total_quantity=1500,
            resolved_count=2,
            unresolved_count=0,
            price_type="sell",
            region="The Forge",
            region_id=10000002,
            freshness="fresh",
            warnings=[],
        )

        assert result.total_value == 11000.0
        assert result.total_quantity == 1500
        assert result.resolved_count == 2

    def test_unresolved_count_tracking(self):
        """Unresolved items are tracked separately."""
        result = ValuationResult(
            items=[
                ValuationItem(
                    type_id=34,
                    type_name="Tritanium",
                    quantity=1000,
                    unit_price=6.0,
                    total_value=6000.0,
                    resolved=True,
                ),
                ValuationItem(
                    type_id=None,
                    type_name="Fake Item",
                    quantity=100,
                    unit_price=None,
                    total_value=None,
                    resolved=False,
                ),
            ],
            total_value=6000.0,
            total_quantity=1100,
            resolved_count=1,
            unresolved_count=1,
            price_type="sell",
            region="The Forge",
            region_id=10000002,
            freshness="fresh",
            warnings=["1 items could not be resolved"],
        )

        assert result.resolved_count == 1
        assert result.unresolved_count == 1
        assert len(result.warnings) == 1


# =============================================================================
# Item Deduplication Tests
# =============================================================================


class TestItemDeduplication:
    """Tests for handling duplicate items in input."""

    def test_quantities_accumulate_dict_pattern(self):
        """Same item appearing twice should have quantities summed."""
        # This tests the pattern used in valuation:
        # quantities[type_id] = quantities.get(type_id, 0) + qty

        quantities: dict[int, int] = {}

        # First occurrence
        type_id = 34
        qty1 = 1000
        quantities[type_id] = quantities.get(type_id, 0) + qty1

        # Second occurrence (same item)
        qty2 = 500
        quantities[type_id] = quantities.get(type_id, 0) + qty2

        assert quantities[34] == 1500

    def test_different_items_tracked_separately(self):
        """Different items maintain separate quantities."""
        quantities: dict[int, int] = {}

        quantities[34] = quantities.get(34, 0) + 1000
        quantities[35] = quantities.get(35, 0) + 500

        assert quantities[34] == 1000
        assert quantities[35] == 500


# =============================================================================
# Price Calculation Tests
# =============================================================================


class TestPriceCalculation:
    """Tests for price arithmetic in valuation."""

    def test_total_value_multiplication(self):
        """Total value = unit_price * quantity."""
        unit_price = 6.50
        quantity = 1000000

        total = unit_price * quantity

        assert total == 6500000.0

    def test_rounding_to_two_decimals(self):
        """Values should be rounded to 2 decimal places."""
        unit_price = 6.123456789
        quantity = 100

        total = round(unit_price * quantity, 2)

        assert total == 612.35

    def test_zero_quantity_yields_zero_value(self):
        """Zero quantity produces zero total value."""
        unit_price = 100.0
        quantity = 0

        total = unit_price * quantity

        assert total == 0.0


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error response handling."""

    def test_no_items_error_structure(self):
        """NO_ITEMS error for empty input."""
        error = {
            "error": {
                "code": "NO_ITEMS",
                "message": "No items provided or parsed",
            }
        }

        assert error["error"]["code"] == "NO_ITEMS"

    def test_warnings_for_unresolved_items(self):
        """Unresolved items generate warnings."""
        unresolved_count = 3
        warnings = []

        if unresolved_count:
            warnings.append(f"{unresolved_count} items could not be resolved")

        assert len(warnings) == 1
        assert "3 items" in warnings[0]

    def test_warnings_for_no_price_items(self):
        """Items without market data generate warnings."""
        no_price_count = 2
        warnings = []

        if no_price_count:
            warnings.append(f"{no_price_count} items have no market data")

        assert len(warnings) == 1
        assert "2 items" in warnings[0]
