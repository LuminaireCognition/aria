"""
Hauling Score Calculator for Arbitrage.

Implements the hauling score algorithm from the HAULING_SCORE_ARBITRAGE_PROPOSAL.
Transforms arbitrage ranking from "highest margin" to "best ISK per trip".

Core Algorithm:
1. Calculate max quantity by cargo (cargo_capacity / item_volume)
2. Calculate max quantity by liquidity (daily_volume * 0.10)
3. Calculate max quantity by market supply (min of buy/sell available)
4. safe_quantity = min(all constraints)
5. hauling_score = (net_profit_per_unit / effective_volume) * fill_ratio

The score represents expected ISK profit per m³ of transport capacity used.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


# =============================================================================
# Constants
# =============================================================================

# Liquidity factor: percentage of daily volume considered "safe" to trade
DEFAULT_LIQUIDITY_FACTOR = 0.10  # 10%

# Minimum safe quantity (even for very low volume items)
MIN_SAFE_QUANTITY = 1


# =============================================================================
# Data Classes
# =============================================================================


@dataclass(frozen=True)
class HaulingScoreResult:
    """
    Result of hauling score calculation.

    All values are calculated assuming immediate buy/sell execution
    (no waiting for order fills).
    """

    # Core score (ISK profit per m³ of transport capacity)
    score: float

    # Liquidity-adjusted quantity to trade
    safe_quantity: int

    # Expected total profit for safe_quantity
    expected_profit: float

    # Cargo space used (safe_quantity * item_volume)
    cargo_used: float

    # Ratio of cargo used to capacity (0.0 to 1.0)
    fill_ratio: float

    # Primary binding constraint
    # "no_data" = both history and availability missing; "no_supply" = data exists but supply is zero
    limiting_factor: str  # "cargo" | "liquidity" | "market_supply_buy" | "market_supply_sell" | "no_data" | "no_supply"

    # All constraints that are binding (equal to safe_quantity)
    limiting_factors: list[str]

    # Source of daily volume data
    daily_volume_source: str  # "history" | "market_proxy" | "none"

    # Source of item volume data (visibility for data quality)
    volume_source: str  # "sde_packaged" | "sde_volume" | "fallback"

    # Source of availability data (proxying status)
    availability_source: str  # "both_available" | "proxy_from_buy" | "proxy_from_sell" | "none"


# =============================================================================
# Calculator Functions
# =============================================================================


def calculate_hauling_score(
    net_profit_per_unit: float,
    volume_m3: float | None,
    packaged_volume_m3: float | None,
    daily_volume: int | None,
    buy_available_volume: int | None,
    sell_available_volume: int | None,
    cargo_capacity_m3: float,
    liquidity_factor: float = DEFAULT_LIQUIDITY_FACTOR,
    daily_volume_source: str = "none",
) -> HaulingScoreResult:
    """
    Calculate hauling score for an arbitrage opportunity.

    The hauling score represents expected ISK profit per m³ of transport
    capacity, accounting for:
    - Item volume (how much cargo space each unit uses)
    - Market liquidity (how many units can be traded without moving price)
    - Market supply (how many units are available to buy/sell)
    - Cargo capacity (how many units can be transported)

    Args:
        net_profit_per_unit: Profit per unit after fees (ISK). Should be
            already fee-adjusted by the caller based on trade_mode.
        volume_m3: Item volume from SDE (None if missing)
        packaged_volume_m3: Packaged volume from SDE (for ships/modules)
        daily_volume: Average daily trade volume (from history or proxy)
        buy_available_volume: Units available to buy at source (None proxies from sell)
        sell_available_volume: Units that can be sold at destination (None proxies from buy)
        cargo_capacity_m3: Ship cargo hold capacity in m³. Only include specialized
            holds if the item type can actually be stored there.
        liquidity_factor: Fraction of daily volume considered safe (default 0.10)
        daily_volume_source: Source of daily_volume data

    Returns:
        HaulingScoreResult with score, safe_quantity, and constraint analysis
    """
    # Get effective volume (packaged > volume > default)
    # Track source for visibility into data quality
    if packaged_volume_m3 is not None and packaged_volume_m3 > 0:
        effective_volume = packaged_volume_m3
        volume_source = "sde_packaged"
    elif volume_m3 is not None and volume_m3 > 0:
        effective_volume = volume_m3
        volume_source = "sde_volume"
    else:
        effective_volume = 0.01  # DEFAULT_VOLUME_M3
        volume_source = "fallback"

    # Handle None buy/sell availability with proxying
    # If one side is None, use the other as a proxy (market data may be incomplete)
    if buy_available_volume is None and sell_available_volume is None:
        effective_buy = 0
        effective_sell = 0
        availability_source = "none"
    elif buy_available_volume is None:
        assert sell_available_volume is not None  # Type narrowing for mypy
        effective_buy = sell_available_volume
        effective_sell = sell_available_volume
        availability_source = "proxy_from_sell"
    elif sell_available_volume is None:
        assert buy_available_volume is not None  # Type narrowing for mypy
        effective_buy = buy_available_volume
        effective_sell = buy_available_volume
        availability_source = "proxy_from_buy"
    else:
        effective_buy = buy_available_volume
        effective_sell = sell_available_volume
        availability_source = "both_available"

    # Calculate maximum quantities by each constraint
    max_by_cargo = int(cargo_capacity_m3 / effective_volume)

    # Market supply constraints (use effective values after proxying)
    max_by_buy = effective_buy
    max_by_sell = effective_sell
    market_available = min(effective_buy, effective_sell)

    # Liquidity constraint (min 1 unit even for very low volume items)
    if daily_volume is not None and daily_volume > 0:
        max_by_liquidity = max(MIN_SAFE_QUANTITY, int(daily_volume * liquidity_factor))
        # Preserve the caller's daily_volume_source (should be "history" if they provided valid data)
        if daily_volume_source == "none":
            daily_volume_source = "history"
    elif market_available > 0:
        # No history data but we have market availability - use as proxy
        # Apply the same liquidity_factor to maintain consistency with the 10% rule
        max_by_liquidity = max(MIN_SAFE_QUANTITY, int(market_available * liquidity_factor))
        daily_volume_source = "market_proxy"
    else:
        # Neither history nor market availability - no data at all
        # Cannot determine safe quantity, return 0 with "no_data" limiting factor
        max_by_liquidity = 0
        daily_volume_source = "none"

    # Safe quantity is the minimum of all constraints
    # When we have data, ensure at least 1 unit; when no data, allow 0
    raw_safe_quantity = min(max_by_cargo, max_by_liquidity, max_by_buy, max_by_sell)
    if raw_safe_quantity <= 0:
        # No tradeable quantity - either no availability or no liquidity data
        safe_quantity = 0
    else:
        safe_quantity = max(MIN_SAFE_QUANTITY, raw_safe_quantity)

    # Handle zero safe_quantity - distinguish "no data" from "no supply"
    if safe_quantity == 0:
        # "no_data" = availability is unknown (cannot confirm supply status)
        # "no_supply" = we have availability data confirming supply is zero
        # Note: Having history data doesn't tell us about current supply - only
        # availability_source indicates whether we can confirm supply status.
        if availability_source == "none":
            zero_factor = "no_data"
        else:
            zero_factor = "no_supply"

        return HaulingScoreResult(
            score=0.0,
            safe_quantity=0,
            expected_profit=0.0,
            cargo_used=0.0,
            fill_ratio=0.0,
            limiting_factor=zero_factor,
            limiting_factors=[zero_factor],
            daily_volume_source=daily_volume_source,
            volume_source=volume_source,
            availability_source=availability_source,
        )

    # Identify limiting factors (all constraints equal to safe_quantity)
    # Use effective values (max_by_buy/max_by_sell) not raw parameters,
    # since raw values may be None when proxying is in effect
    constraints = {
        "cargo": max_by_cargo,
        "liquidity": max_by_liquidity,
        "market_supply_buy": max_by_buy,
        "market_supply_sell": max_by_sell,
    }

    limiting_factors = [name for name, value in constraints.items() if value <= safe_quantity]

    # When proxying, only report the side that has actual data
    # If we proxied from sell, don't report market_supply_buy as a limiting factor
    # (since we don't actually know the buy-side availability)
    if availability_source == "proxy_from_sell" and "market_supply_buy" in limiting_factors:
        limiting_factors.remove("market_supply_buy")
    elif availability_source == "proxy_from_buy" and "market_supply_sell" in limiting_factors:
        limiting_factors.remove("market_supply_sell")

    # Primary limiting factor (prefer more meaningful ones)
    # Priority: market supply is hardest to change, then liquidity, then cargo
    priority_order = ["market_supply_buy", "market_supply_sell", "liquidity", "cargo"]
    limiting_factor = "cargo"  # Default
    for factor in priority_order:
        if factor in limiting_factors:
            limiting_factor = factor
            break

    # Calculate cargo usage and fill ratio
    cargo_used = safe_quantity * effective_volume
    fill_ratio = min(1.0, cargo_used / cargo_capacity_m3) if cargo_capacity_m3 > 0 else 0.0

    # Calculate expected profit
    expected_profit = net_profit_per_unit * safe_quantity

    # Calculate hauling score (ISK profit per m³ of transport capacity)
    # This is profit density (net_profit / volume) scaled by fill ratio
    profit_density = net_profit_per_unit / effective_volume
    score = profit_density * fill_ratio

    return HaulingScoreResult(
        score=round(score, 2),
        safe_quantity=safe_quantity,
        expected_profit=round(expected_profit, 2),
        cargo_used=round(cargo_used, 2),
        fill_ratio=round(fill_ratio, 4),
        limiting_factor=limiting_factor,
        limiting_factors=limiting_factors,
        daily_volume_source=daily_volume_source,
        volume_source=volume_source,
        availability_source=availability_source,
    )


def calculate_hauling_scores_batch(
    opportunities: list[dict],
    cargo_capacity_m3: float,
    liquidity_factor: float = DEFAULT_LIQUIDITY_FACTOR,
) -> dict[int, HaulingScoreResult]:
    """
    Calculate hauling scores for multiple opportunities.

    Args:
        opportunities: List of opportunity dicts with required fields:
            - type_id
            - net_profit_per_unit
            - item_volume_m3
            - item_packaged_volume_m3
            - daily_volume (optional)
            - buy_available_volume
            - sell_available_volume
            - daily_volume_source (optional)
        cargo_capacity_m3: Ship cargo capacity in m³
        liquidity_factor: Fraction of daily volume considered safe

    Returns:
        Dict mapping type_id to HaulingScoreResult
    """
    results = {}
    for opp in opportunities:
        type_id = opp["type_id"]
        result = calculate_hauling_score(
            net_profit_per_unit=opp["net_profit_per_unit"],
            volume_m3=opp.get("item_volume_m3"),
            packaged_volume_m3=opp.get("item_packaged_volume_m3"),
            daily_volume=opp.get("daily_volume"),
            buy_available_volume=opp.get("buy_available_volume"),  # None triggers proxy logic
            sell_available_volume=opp.get("sell_available_volume"),  # None triggers proxy logic
            cargo_capacity_m3=cargo_capacity_m3,
            liquidity_factor=liquidity_factor,
            daily_volume_source=opp.get("daily_volume_source", "none"),
        )
        results[type_id] = result
    return results
