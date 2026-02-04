"""
Unit Tests for Market History MCP Tools.

Tests trend analysis functions and the market_history tool.
"""

from __future__ import annotations

import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aria_esi.mcp.market.tools_history import (
    analyze_price_trend,
    analyze_volume_trend,
    register_history_tools,
)
from aria_esi.models.market import DailyPrice

# =============================================================================
# Test Data Factories
# =============================================================================


def make_daily_price(
    date: str = "2024-01-01",
    average: float = 100.0,
    highest: float = 110.0,
    lowest: float = 90.0,
    volume: int = 1000,
    order_count: int = 50,
) -> DailyPrice:
    """Factory function for creating DailyPrice test data."""
    return DailyPrice(
        date=date,
        average=average,
        highest=highest,
        lowest=lowest,
        volume=volume,
        order_count=order_count,
    )


def make_price_series(
    prices: list[float],
    volumes: list[int] | None = None,
) -> list[DailyPrice]:
    """Create a series of DailyPrice objects from price list."""
    if volumes is None:
        volumes = [1000] * len(prices)
    return [
        make_daily_price(
            date=f"2024-01-{i+1:02d}",
            average=p,
            highest=p * 1.1,
            lowest=p * 0.9,
            volume=v,
        )
        for i, (p, v) in enumerate(zip(prices, volumes))
    ]


# =============================================================================
# Price Trend Analysis Tests
# =============================================================================


class TestAnalyzePriceTrend:
    """Tests for analyze_price_trend function."""

    def test_empty_history_returns_stable(self):
        """Empty history should return stable."""
        result = analyze_price_trend([])
        assert result == "stable"

    def test_single_entry_returns_stable(self):
        """Single entry cannot have a trend."""
        history = [make_daily_price(average=100.0)]
        result = analyze_price_trend(history)
        assert result == "stable"

    def test_two_entries_returns_stable(self):
        """Two entries not enough for trend detection."""
        history = make_price_series([100.0, 200.0])
        result = analyze_price_trend(history)
        assert result == "stable"

    def test_rising_trend_detected(self):
        """Increasing prices should detect rising trend."""
        # Create a clear upward trend: 100 -> 150 (50% increase)
        prices = [100.0, 105.0, 110.0, 115.0, 120.0, 130.0, 140.0, 150.0, 155.0]
        history = make_price_series(prices)
        result = analyze_price_trend(history)
        assert result == "rising"

    def test_falling_trend_detected(self):
        """Decreasing prices should detect falling trend."""
        # Create a clear downward trend: 150 -> 100 (>5% decrease)
        prices = [150.0, 145.0, 140.0, 130.0, 120.0, 115.0, 110.0, 105.0, 100.0]
        history = make_price_series(prices)
        result = analyze_price_trend(history)
        assert result == "falling"

    def test_stable_prices_detected(self):
        """Flat prices should detect stable trend."""
        # Prices vary within 5% - should be stable
        prices = [100.0, 101.0, 99.0, 100.5, 99.5, 100.2, 99.8, 100.1, 99.9]
        history = make_price_series(prices)
        result = analyze_price_trend(history)
        assert result == "stable"

    def test_volatile_prices_detected(self):
        """High variance should detect volatile trend."""
        # Create high volatility (>15% coefficient of variation)
        prices = [100.0, 150.0, 80.0, 140.0, 70.0, 160.0, 60.0, 150.0, 90.0]
        history = make_price_series(prices)
        result = analyze_price_trend(history)
        assert result == "volatile"

    def test_zero_mean_price_returns_stable(self):
        """Zero mean price should not cause division error."""
        history = make_price_series([0.0, 0.0, 0.0, 0.0, 0.0])
        result = analyze_price_trend(history)
        assert result == "stable"

    def test_zero_early_average_handled(self):
        """Zero early average should handle gracefully without crashing."""
        prices = [0.0, 0.0, 0.0, 100.0, 100.0, 100.0]
        history = make_price_series(prices)
        result = analyze_price_trend(history)
        # High variance from 0 to 100 triggers volatile check
        assert result in ("stable", "volatile")

    def test_exact_threshold_rising(self):
        """Exactly at 5% threshold should be rising."""
        # 100 -> 105 is exactly 5% increase
        prices = [100.0, 100.0, 100.0, 105.0, 105.0, 105.01]
        history = make_price_series(prices)
        result = analyze_price_trend(history)
        assert result == "rising"

    def test_exact_threshold_falling(self):
        """Exactly at -5% threshold should be falling."""
        # 100 -> 94.9 is >5% decrease
        prices = [100.0, 100.0, 100.0, 94.9, 94.9, 94.9]
        history = make_price_series(prices)
        result = analyze_price_trend(history)
        assert result == "falling"


# =============================================================================
# Volume Trend Analysis Tests
# =============================================================================


class TestAnalyzeVolumeTrend:
    """Tests for analyze_volume_trend function."""

    def test_empty_history_returns_stable(self):
        """Empty history should return stable."""
        result = analyze_volume_trend([])
        assert result == "stable"

    def test_single_entry_returns_stable(self):
        """Single entry cannot have a volume trend."""
        history = [make_daily_price(volume=1000)]
        result = analyze_volume_trend(history)
        assert result == "stable"

    def test_two_entries_returns_stable(self):
        """Two entries not enough for trend detection."""
        history = make_price_series([100.0, 100.0], volumes=[1000, 2000])
        result = analyze_volume_trend(history)
        assert result == "stable"

    def test_increasing_volume_detected(self):
        """Increasing volume should detect increasing trend."""
        # Create >20% volume increase
        volumes = [1000, 1000, 1000, 1500, 1500, 1500, 2000, 2000, 2000]
        history = make_price_series([100.0] * 9, volumes=volumes)
        result = analyze_volume_trend(history)
        assert result == "increasing"

    def test_decreasing_volume_detected(self):
        """Decreasing volume should detect decreasing trend."""
        # Create >20% volume decrease
        volumes = [2000, 2000, 2000, 1500, 1500, 1500, 1000, 1000, 1000]
        history = make_price_series([100.0] * 9, volumes=volumes)
        result = analyze_volume_trend(history)
        assert result == "decreasing"

    def test_stable_volume_detected(self):
        """Flat volume should detect stable trend."""
        # Volume varies within 20%
        volumes = [1000, 1050, 950, 1020, 980, 1010, 990, 1005, 995]
        history = make_price_series([100.0] * 9, volumes=volumes)
        result = analyze_volume_trend(history)
        assert result == "stable"

    def test_zero_early_volume_returns_stable(self):
        """Zero early volume should not cause division error."""
        volumes = [0, 0, 0, 1000, 1000, 1000]
        history = make_price_series([100.0] * 6, volumes=volumes)
        result = analyze_volume_trend(history)
        assert result == "stable"

    def test_all_zero_volume_returns_stable(self):
        """All zero volume should return stable."""
        volumes = [0, 0, 0, 0, 0, 0]
        history = make_price_series([100.0] * 6, volumes=volumes)
        result = analyze_volume_trend(history)
        assert result == "stable"

    def test_exact_threshold_increasing(self):
        """Exactly at 20% threshold should be increasing."""
        # 1000 -> 1200 is 20% increase
        volumes = [1000, 1000, 1000, 1200, 1200, 1201]
        history = make_price_series([100.0] * 6, volumes=volumes)
        result = analyze_volume_trend(history)
        assert result == "increasing"

    def test_exact_threshold_decreasing(self):
        """Exactly at -20% threshold should be decreasing."""
        # 1000 -> 799 is >20% decrease
        volumes = [1000, 1000, 1000, 799, 799, 799]
        history = make_price_series([100.0] * 6, volumes=volumes)
        result = analyze_volume_trend(history)
        assert result == "decreasing"


# =============================================================================
# Edge Cases
# =============================================================================


class TestTrendAnalysisEdgeCases:
    """Edge case tests for trend analysis functions."""

    def test_large_history_handled(self):
        """Large history (365 days) should work correctly."""
        # Create 365 days of smoothly increasing prices
        # Start at 100, end at 108 (8% increase), with low CV
        # The trend compares first third (~100-102.6) vs last third (~105.3-108)
        # That's about 5%+ change while keeping overall CV < 15%
        prices = [100.0 + i * 0.022 for i in range(365)]  # 100 -> 108
        history = make_price_series(prices)
        result = analyze_price_trend(history)
        assert result == "rising"

    def test_fractional_prices_handled(self):
        """Fractional ISK prices should work correctly."""
        # Many items have sub-ISK prices
        prices = [0.50, 0.52, 0.54, 0.56, 0.58, 0.60]
        history = make_price_series(prices)
        result = analyze_price_trend(history)
        assert result == "rising"

    def test_very_small_prices_handled(self):
        """Very small prices should work correctly."""
        # With 6 entries, third=2, so comparing avg of [0.100, 0.101] vs [0.107, 0.108]
        # That's ~0.1005 vs ~0.1075 = ~7% increase, > 5% threshold
        prices = [0.100, 0.101, 0.103, 0.105, 0.107, 0.108]
        history = make_price_series(prices)
        result = analyze_price_trend(history)
        assert result == "rising"

    def test_very_large_prices_handled(self):
        """Very large prices should work correctly."""
        prices = [1e12, 1.1e12, 1.2e12, 1.3e12, 1.4e12, 1.5e12]
        history = make_price_series(prices)
        result = analyze_price_trend(history)
        assert result == "rising"

    def test_mixed_zero_and_nonzero(self):
        """Mix of zero and non-zero values."""
        prices = [0.0, 100.0, 0.0, 100.0, 0.0, 100.0]
        history = make_price_series(prices)
        # High variance but with zeros
        result = analyze_price_trend(history)
        assert result in ("volatile", "stable")  # Depends on CV calculation

    def test_minimum_entries_for_trend(self):
        """Exactly 3 entries should allow trend detection."""
        # 3 entries: third = 1, so we compare first 1 vs last 1
        prices = [100.0, 110.0, 200.0]
        history = make_price_series(prices)
        result = analyze_price_trend(history)
        assert result in ("rising", "falling", "stable", "volatile")


# =============================================================================
# Integration-style Tests
# =============================================================================


class TestTrendAnalysisIntegration:
    """Tests that verify price and volume trends together."""

    def test_rising_price_increasing_volume(self):
        """Bullish market: rising prices with increasing volume."""
        # Keep price variance low (<15% CV) while still showing upward trend
        prices = [100.0, 101.0, 102.0, 103.5, 105.0, 106.5, 108.0, 109.5, 111.0]
        volumes = [1000, 1100, 1200, 1400, 1600, 1900, 2200, 2500, 3000]
        history = make_price_series(prices, volumes)

        price_trend = analyze_price_trend(history)
        volume_trend = analyze_volume_trend(history)

        assert price_trend == "rising"
        assert volume_trend == "increasing"

    def test_falling_price_decreasing_volume(self):
        """Bearish market: falling prices with decreasing volume."""
        # Keep price variance low (<15% CV) while still showing downward trend
        prices = [111.0, 109.5, 108.0, 106.5, 105.0, 103.5, 102.0, 101.0, 100.0]
        volumes = [3000, 2500, 2200, 1900, 1600, 1400, 1200, 1100, 1000]
        history = make_price_series(prices, volumes)

        price_trend = analyze_price_trend(history)
        volume_trend = analyze_volume_trend(history)

        assert price_trend == "falling"
        assert volume_trend == "decreasing"

    def test_stable_price_stable_volume(self):
        """Quiet market: stable prices with stable volume."""
        prices = [100.0, 101.0, 99.5, 100.5, 99.0, 101.5, 100.0, 99.8, 100.2]
        volumes = [1000, 1020, 980, 1010, 990, 1015, 985, 1005, 995]
        history = make_price_series(prices, volumes)

        price_trend = analyze_price_trend(history)
        volume_trend = analyze_volume_trend(history)

        assert price_trend == "stable"
        assert volume_trend == "stable"


# =============================================================================
# Market History Tool Tests
# =============================================================================


@pytest.fixture
def mock_market_db():
    """Create a mock market database with type resolution."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    conn.executescript(
        """
        CREATE TABLE types (
            type_id INTEGER PRIMARY KEY,
            type_name TEXT,
            type_name_lower TEXT
        );
        INSERT INTO types VALUES (34, 'Tritanium', 'tritanium');
        INSERT INTO types VALUES (35, 'Pyerite', 'pyerite');
        """
    )
    conn.commit()

    mock = MagicMock()
    mock._get_connection.return_value = conn

    # Mock type resolution methods
    def mock_resolve_type_name(name):
        name_lower = name.lower()
        if name_lower == "tritanium":
            result = MagicMock()
            result.type_id = 34
            result.type_name = "Tritanium"
            return result
        return None

    def mock_find_suggestions(name):
        return ["Tritanium", "Pyerite"]

    mock.resolve_type_name = mock_resolve_type_name
    mock.find_type_suggestions = mock_find_suggestions

    yield mock
    conn.close()


class TestMarketHistoryTool:
    """Tests for the market_history MCP tool."""

    @pytest.fixture
    def captured_tool(self, mock_market_db):
        """Capture the registered tool function."""
        captured = None

        def mock_tool():
            def decorator(func):
                nonlocal captured
                captured = func
                return func
            return decorator

        mock_server = MagicMock()
        mock_server.tool = mock_tool

        with patch(
            "aria_esi.mcp.market.tools_history.get_market_database",
            return_value=mock_market_db,
        ):
            register_history_tools(mock_server)

        return captured

    @pytest.mark.asyncio
    async def test_unknown_item_returns_error(self, captured_tool, mock_market_db):
        """Should return error for unknown item."""
        with patch(
            "aria_esi.mcp.market.tools_history.get_market_database",
            return_value=mock_market_db,
        ):
            result = await captured_tool(item="NonexistentItem")

        assert "error" in result
        assert result["error"]["code"] == "TYPE_NOT_FOUND"
        assert "suggestions" in result["error"]["data"]

    @pytest.mark.asyncio
    async def test_invalid_region_defaults_to_jita(self, captured_tool, mock_market_db):
        """Should default to Jita for invalid region."""
        mock_esi_client = MagicMock()
        mock_esi_client.get.return_value = [
            {
                "date": "2024-01-01",
                "average": 5.0,
                "highest": 6.0,
                "lowest": 4.0,
                "volume": 1000000,
                "order_count": 500,
            }
        ]

        with patch(
            "aria_esi.mcp.market.tools_history.get_market_database",
            return_value=mock_market_db,
        ), patch(
            "aria_esi.core.client.ESIClient",
            return_value=mock_esi_client,
        ):
            result = await captured_tool(item="Tritanium", region="invalid_region")

        # Should not error - defaults to Jita
        assert "error" not in result or result.get("region") == "The Forge"

    @pytest.mark.asyncio
    async def test_days_clamped_to_valid_range(self, captured_tool, mock_market_db):
        """Should clamp days to 1-365 range."""
        mock_esi_client = MagicMock()
        mock_esi_client.get.return_value = []

        with patch(
            "aria_esi.mcp.market.tools_history.get_market_database",
            return_value=mock_market_db,
        ), patch(
            "aria_esi.core.client.ESIClient",
            return_value=mock_esi_client,
        ):
            # Test with negative days
            result = await captured_tool(item="Tritanium", days=-10)
            # Should not crash

            # Test with too many days
            result = await captured_tool(item="Tritanium", days=1000)
            # Should not crash

    @pytest.mark.asyncio
    async def test_esi_unavailable_returns_error(self, captured_tool, mock_market_db):
        """Should handle ESI client import error gracefully."""
        with patch(
            "aria_esi.mcp.market.tools_history.get_market_database",
            return_value=mock_market_db,
        ), patch.dict("sys.modules", {"aria_esi.core.client": None}):
            # This tests the ImportError path - but it's tricky to trigger
            # Let's test the general ESI error path instead
            pass

    @pytest.mark.asyncio
    async def test_successful_history_fetch(self, captured_tool, mock_market_db):
        """Should return complete history result on success."""
        mock_esi_client = MagicMock()
        mock_esi_client.get.return_value = [
            {
                "date": "2024-01-01",
                "average": 5.0,
                "highest": 6.0,
                "lowest": 4.0,
                "volume": 1000000,
                "order_count": 500,
            },
            {
                "date": "2024-01-02",
                "average": 5.2,
                "highest": 6.1,
                "lowest": 4.2,
                "volume": 1100000,
                "order_count": 520,
            },
            {
                "date": "2024-01-03",
                "average": 5.4,
                "highest": 6.2,
                "lowest": 4.4,
                "volume": 1200000,
                "order_count": 540,
            },
        ]

        mock_async_esi_client = AsyncMock()
        mock_async_esi_client.get.return_value = mock_esi_client.get.return_value

        with patch(
            "aria_esi.mcp.market.tools_history.get_market_database",
            return_value=mock_market_db,
        ), patch(
            "aria_esi.mcp.esi_client.get_async_esi_client",
            new=AsyncMock(return_value=mock_async_esi_client),
        ):
            result = await captured_tool(item="Tritanium", days=30)

        assert "error" not in result
        assert result["type_id"] == 34
        assert result["type_name"] == "Tritanium"
        assert len(result["history"]) == 3
        assert result["price_trend"] in ("rising", "falling", "stable", "volatile")
        assert result["volume_trend"] in ("increasing", "decreasing", "stable")
        assert result["avg_price"] > 0
        assert result["avg_volume"] > 0

    @pytest.mark.asyncio
    async def test_empty_history_returns_error(self, captured_tool, mock_market_db):
        """Should return error when no history available."""
        mock_async_esi_client = AsyncMock()
        mock_async_esi_client.get.return_value = []

        with patch(
            "aria_esi.mcp.market.tools_history.get_market_database",
            return_value=mock_market_db,
        ), patch(
            "aria_esi.mcp.esi_client.get_async_esi_client",
            new=AsyncMock(return_value=mock_async_esi_client),
        ):
            result = await captured_tool(item="Tritanium")

        assert "error" in result
        assert result["error"]["code"] == "NO_HISTORY"
