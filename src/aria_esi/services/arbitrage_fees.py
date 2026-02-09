"""
Arbitrage Fee Calculation Module.

Pure calculation logic for broker fees, sales tax, and profit computation.
Extracted from arbitrage_engine.py for testability and reuse.
"""

from __future__ import annotations

from dataclasses import dataclass

from aria_esi.models.market import BasicExecutionInfo

# =============================================================================
# Default Fee Rates
# =============================================================================

# V1 fee rates (percentage) - used by ArbitrageCalculator
DEFAULT_BROKER_FEE_PCT = 3.0  # Base broker fee (skills reduce this)
DEFAULT_SALES_TAX_PCT = 5.0  # Base sales tax (skills reduce this)

# V2 fee rates (more realistic defaults based on typical standings)
# These are the fee rates used for net profit calculations in hauling score
V2_BROKER_FEE_PCT = 0.03  # 3% broker fee (decimal form)
V2_SALES_TAX_PCT = 0.036  # 3.6% sales tax (Accounting IV)


# =============================================================================
# Fee Calculator
# =============================================================================


@dataclass
class ArbitrageCalculator:
    """
    Calculator for arbitrage profit with fee estimation.

    Handles broker fees and sales tax calculation based on
    character skills. V1 uses default rates.

    Attributes:
        broker_fee_pct: Broker fee percentage (default 3.0%)
        sales_tax_pct: Sales tax percentage (default 5.0%)
    """

    broker_fee_pct: float = DEFAULT_BROKER_FEE_PCT
    sales_tax_pct: float = DEFAULT_SALES_TAX_PCT

    def calculate_fees(
        self,
        buy_price: float,
        sell_price: float,
        quantity: int,
    ) -> tuple[float, float, float]:
        """
        Calculate broker fees and sales tax.

        Args:
            buy_price: Price per unit when buying
            sell_price: Price per unit when selling
            quantity: Number of units

        Returns:
            Tuple of (broker_fee, sales_tax, total_fees)
        """
        total_buy = buy_price * quantity
        total_sell = sell_price * quantity

        # Broker fee applies to both buy and sell orders
        broker_fee = (total_buy + total_sell) * (self.broker_fee_pct / 100)

        # Sales tax applies only to sell orders
        sales_tax = total_sell * (self.sales_tax_pct / 100)

        return broker_fee, sales_tax, broker_fee + sales_tax

    def calculate_true_profit(
        self,
        buy_price: float,
        sell_price: float,
        quantity: int,
        cargo_volume: float = 0.0,
    ) -> BasicExecutionInfo:
        """
        Calculate true profit after fees.

        Args:
            buy_price: Price per unit when buying
            sell_price: Price per unit when selling
            quantity: Number of units
            cargo_volume: Volume per unit in m3

        Returns:
            BasicExecutionInfo with profit breakdown
        """
        total_investment = buy_price * quantity
        gross_revenue = sell_price * quantity
        gross_profit = gross_revenue - total_investment

        broker_fee, sales_tax, total_fees = self.calculate_fees(buy_price, sell_price, quantity)

        net_profit = gross_profit - total_fees
        roi_pct = (net_profit / total_investment * 100) if total_investment > 0 else 0

        return BasicExecutionInfo(
            cargo_volume=cargo_volume * quantity,
            estimated_profit=round(net_profit, 2),
            broker_fee=round(broker_fee, 2),
            sales_tax=round(sales_tax, 2),
            total_investment=round(total_investment, 2),
            roi_pct=round(roi_pct, 2),
        )


# =============================================================================
# Net Profit Calculation
# =============================================================================


def calculate_net_profit(
    buy_price: float,
    sell_price: float,
    trade_mode: str = "immediate",
    broker_fee_pct: float = V2_BROKER_FEE_PCT,
    sales_tax_pct: float = V2_SALES_TAX_PCT,
) -> tuple[float, float, float, float]:
    """
    Calculate fee-adjusted net profit per unit based on trade mode.

    Fee model varies by trade execution mode:
    - immediate: Take sell orders -> Take buy orders. No broker fees, only sales tax.
    - hybrid: Take sell orders -> Place sell orders. Broker fee on sell + sales tax.
    - station_trading: Place buy orders -> Place sell orders. Broker fees on both + sales tax.

    Args:
        buy_price: Price per unit when buying
        sell_price: Price per unit when selling
        trade_mode: Trade execution mode ("immediate", "hybrid", "station_trading")
        broker_fee_pct: Broker fee percentage (decimal, e.g., 0.03 for 3%)
        sales_tax_pct: Sales tax percentage (decimal, e.g., 0.036 for 3.6%)

    Returns:
        Tuple of (net_profit_per_unit, net_margin_pct, gross_profit_per_unit, gross_margin_pct)
    """
    # Gross profit (before fees)
    gross_profit = sell_price - buy_price
    gross_margin = (gross_profit / buy_price * 100) if buy_price > 0 else 0.0

    # Net profit calculation varies by trade mode
    if trade_mode == "immediate":
        # Take sell orders -> Take buy orders
        # No broker fees when taking existing orders
        buy_cost = buy_price
        sell_revenue = sell_price * (1 - sales_tax_pct)
    elif trade_mode == "hybrid":
        # Take sell orders -> Place sell orders
        # No broker fee on buy, broker + sales tax on sell
        buy_cost = buy_price
        sell_revenue = sell_price * (1 - broker_fee_pct - sales_tax_pct)
    else:  # station_trading
        # Place buy orders -> Place sell orders
        # Broker fees on both sides + sales tax on sell
        buy_cost = buy_price * (1 + broker_fee_pct)
        sell_revenue = sell_price * (1 - broker_fee_pct - sales_tax_pct)

    net_profit = sell_revenue - buy_cost
    net_margin = (net_profit / buy_cost * 100) if buy_cost > 0 else 0.0

    return net_profit, net_margin, gross_profit, gross_margin
