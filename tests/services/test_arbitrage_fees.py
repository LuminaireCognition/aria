"""
Tests for arbitrage_fees module.

Tests fee calculation and net profit computation.
"""

import pytest

from aria_esi.services.arbitrage_fees import (
    DEFAULT_BROKER_FEE_PCT,
    DEFAULT_SALES_TAX_PCT,
    V2_BROKER_FEE_PCT,
    V2_SALES_TAX_PCT,
    ArbitrageCalculator,
    calculate_net_profit,
)


class TestArbitrageCalculator:
    """Tests for ArbitrageCalculator class."""

    def test_default_fee_rates(self):
        """Test that default fee rates are set correctly."""
        calc = ArbitrageCalculator()
        assert calc.broker_fee_pct == DEFAULT_BROKER_FEE_PCT
        assert calc.sales_tax_pct == DEFAULT_SALES_TAX_PCT

    def test_custom_fee_rates(self):
        """Test that custom fee rates can be set."""
        calc = ArbitrageCalculator(broker_fee_pct=1.5, sales_tax_pct=2.0)
        assert calc.broker_fee_pct == 1.5
        assert calc.sales_tax_pct == 2.0

    def test_calculate_fees_basic(self):
        """Test basic fee calculation."""
        calc = ArbitrageCalculator(broker_fee_pct=3.0, sales_tax_pct=5.0)

        broker, tax, total = calc.calculate_fees(
            buy_price=100.0,
            sell_price=150.0,
            quantity=10,
        )

        # Buy total: 100 * 10 = 1000
        # Sell total: 150 * 10 = 1500
        # Broker fee: (1000 + 1500) * 0.03 = 75
        # Sales tax: 1500 * 0.05 = 75
        assert broker == 75.0
        assert tax == 75.0
        assert total == 150.0

    def test_calculate_fees_zero_quantity(self):
        """Test fee calculation with zero quantity."""
        calc = ArbitrageCalculator()
        broker, tax, total = calc.calculate_fees(100.0, 150.0, 0)

        assert broker == 0.0
        assert tax == 0.0
        assert total == 0.0

    def test_calculate_true_profit_positive(self):
        """Test true profit calculation with profitable trade."""
        calc = ArbitrageCalculator(broker_fee_pct=3.0, sales_tax_pct=5.0)

        result = calc.calculate_true_profit(
            buy_price=100.0,
            sell_price=200.0,
            quantity=10,
            cargo_volume=5.0,
        )

        # Buy: 100 * 10 = 1000
        # Sell: 200 * 10 = 2000
        # Gross: 2000 - 1000 = 1000
        # Broker: (1000 + 2000) * 0.03 = 90
        # Tax: 2000 * 0.05 = 100
        # Net: 1000 - 190 = 810
        # ROI: 810 / 1000 * 100 = 81%
        assert result.total_investment == 1000.0
        assert result.estimated_profit == 810.0
        assert result.broker_fee == 90.0
        assert result.sales_tax == 100.0
        assert result.roi_pct == 81.0
        assert result.cargo_volume == 50.0  # 5.0 * 10

    def test_calculate_true_profit_negative(self):
        """Test true profit calculation with losing trade."""
        calc = ArbitrageCalculator(broker_fee_pct=3.0, sales_tax_pct=5.0)

        result = calc.calculate_true_profit(
            buy_price=100.0,
            sell_price=105.0,  # Only 5% gross margin
            quantity=10,
        )

        # Gross profit: 50
        # Fees will eat into profit
        assert result.estimated_profit < 50

    def test_calculate_true_profit_zero_investment(self):
        """Test ROI calculation doesn't divide by zero."""
        calc = ArbitrageCalculator()

        result = calc.calculate_true_profit(
            buy_price=0.0,
            sell_price=100.0,
            quantity=10,
        )

        assert result.roi_pct == 0.0


class TestCalculateNetProfit:
    """Tests for calculate_net_profit function."""

    def test_immediate_mode_no_broker_fee(self):
        """Test immediate mode applies only sales tax."""
        net, net_margin, gross, gross_margin = calculate_net_profit(
            buy_price=100.0,
            sell_price=120.0,
            trade_mode="immediate",
            broker_fee_pct=0.03,
            sales_tax_pct=0.036,
        )

        # Immediate: buy at 100, sell at 120 * (1 - 0.036)
        # Net = 115.68 - 100 = 15.68
        assert gross == 20.0  # 120 - 100
        assert gross_margin == 20.0  # (20/100) * 100
        assert net == pytest.approx(15.68, abs=0.01)

    def test_hybrid_mode_broker_on_sell(self):
        """Test hybrid mode applies broker + tax on sell only."""
        net, net_margin, gross, gross_margin = calculate_net_profit(
            buy_price=100.0,
            sell_price=120.0,
            trade_mode="hybrid",
            broker_fee_pct=0.03,
            sales_tax_pct=0.036,
        )

        # Hybrid: buy at 100, sell at 120 * (1 - 0.03 - 0.036) = 120 * 0.934 = 112.08
        # Net = 112.08 - 100 = 12.08
        assert gross == 20.0
        assert net == pytest.approx(12.08, abs=0.01)

    def test_station_trading_mode_broker_both_sides(self):
        """Test station trading applies broker to both + tax on sell."""
        net, net_margin, gross, gross_margin = calculate_net_profit(
            buy_price=100.0,
            sell_price=120.0,
            trade_mode="station_trading",
            broker_fee_pct=0.03,
            sales_tax_pct=0.036,
        )

        # Station: buy at 100 * 1.03 = 103, sell at 120 * 0.934 = 112.08
        # Net = 112.08 - 103 = 9.08
        assert gross == 20.0
        assert net == pytest.approx(9.08, abs=0.01)

    def test_net_margin_calculation(self):
        """Test that net margin is calculated correctly."""
        net, net_margin, gross, gross_margin = calculate_net_profit(
            buy_price=100.0,
            sell_price=150.0,
            trade_mode="immediate",
            sales_tax_pct=0.036,
        )

        # Net margin = (net_profit / buy_cost) * 100
        expected_sell = 150 * (1 - 0.036)  # 144.6
        expected_net = expected_sell - 100  # 44.6
        expected_margin = (expected_net / 100) * 100  # 44.6%

        assert net_margin == pytest.approx(expected_margin, abs=0.1)

    def test_zero_buy_price_no_div_zero(self):
        """Test that zero buy price doesn't cause division by zero."""
        net, net_margin, gross, gross_margin = calculate_net_profit(
            buy_price=0.0,
            sell_price=100.0,
            trade_mode="immediate",
        )

        assert gross_margin == 0.0
        # Net margin would be calculated from buy_cost=0, returns 0

    def test_default_fee_rates(self):
        """Test that default V2 fee rates are used."""
        # Just verify the function works with defaults
        net, _, _, _ = calculate_net_profit(100.0, 120.0)
        assert net > 0

    def test_profit_ordering_by_mode(self):
        """Test that immediate > hybrid > station_trading for profit."""
        immediate_net, _, _, _ = calculate_net_profit(100.0, 120.0, "immediate")
        hybrid_net, _, _, _ = calculate_net_profit(100.0, 120.0, "hybrid")
        station_net, _, _, _ = calculate_net_profit(100.0, 120.0, "station_trading")

        # Immediate should be most profitable (lowest fees)
        # Station trading should be least profitable (highest fees)
        assert immediate_net > hybrid_net > station_net


class TestConstants:
    """Tests for module constants."""

    def test_v1_fee_rates(self):
        """Test V1 (percentage) fee rate constants."""
        assert DEFAULT_BROKER_FEE_PCT == 3.0
        assert DEFAULT_SALES_TAX_PCT == 5.0

    def test_v2_fee_rates(self):
        """Test V2 (decimal) fee rate constants."""
        assert V2_BROKER_FEE_PCT == 0.03
        assert V2_SALES_TAX_PCT == 0.036
