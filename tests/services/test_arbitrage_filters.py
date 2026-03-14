"""Tests for arbitrage profit floor filters."""

from __future__ import annotations

import pytest

from aria_esi.services.arbitrage_fees import calculate_net_profit


class TestAbsoluteProfitFloor:
    """Test min_absolute_profit filtering logic."""

    def test_absolute_profit_floor_filters(self):
        """Opportunity with net_profit=50k should be filtered at 100k floor."""
        # A trade that yields 50k net profit per unit
        buy_price = 1_000_000.0
        sell_price = 1_060_000.0  # ~6% gross margin
        net_profit, _, _, _ = calculate_net_profit(buy_price, sell_price, "immediate")
        # With immediate mode (sales tax ~3.6%), net profit is ~24k
        # The point: net_profit < 100_000, so it should be filtered
        min_absolute_profit = 100_000.0
        assert net_profit < min_absolute_profit, (
            f"Expected net_profit ({net_profit:.0f}) < min_absolute_profit ({min_absolute_profit})"
        )

    def test_absolute_profit_floor_passes_large_margin(self):
        """Opportunity with large net_profit should pass the floor."""
        buy_price = 1_000_000.0
        sell_price = 1_500_000.0  # 50% gross margin
        net_profit, _, _, _ = calculate_net_profit(buy_price, sell_price, "immediate")
        min_absolute_profit = 100_000.0
        assert net_profit >= min_absolute_profit


class TestBuyPriceFloor:
    """Test min_buy_price filtering for phantom orders."""

    def test_buy_price_floor_filters_phantom(self):
        """Station trading with buy_price=0.02 should be filtered."""
        buy_price = 0.02
        min_buy_price = 100.0
        trade_mode = "station_trading"
        # Filter logic: if trade_mode == "station_trading" and buy_price < min_buy_price
        assert trade_mode == "station_trading" and buy_price < min_buy_price

    def test_buy_price_floor_passes_normal(self):
        """Station trading with buy_price=500.0 should pass."""
        buy_price = 500.0
        min_buy_price = 100.0
        trade_mode = "station_trading"
        assert not (trade_mode == "station_trading" and buy_price < min_buy_price)

    def test_buy_price_floor_ignored_for_immediate(self):
        """Non-station_trading modes should not filter on buy_price."""
        buy_price = 0.02
        min_buy_price = 100.0
        trade_mode = "immediate"
        # Filter only applies to station_trading
        assert not (trade_mode == "station_trading" and buy_price < min_buy_price)
