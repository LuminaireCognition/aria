"""
Tests for Hauling Score Arbitrage Features.

Tests the V2 arbitrage features:
- Volume and density calculations
- Net profit calculations with fees
- History cache service
- Hauling score algorithm
- Sort mode ordering
"""

from __future__ import annotations

import pytest

from aria_esi.models.market import DEFAULT_VOLUME_M3, ArbitrageOpportunity
from aria_esi.services.arbitrage_engine import V2_BROKER_FEE_PCT, V2_SALES_TAX_PCT, ArbitrageEngine
from aria_esi.services.hauling_score import (
    MIN_SAFE_QUANTITY,
    HaulingScoreResult,
    calculate_hauling_score,
    calculate_hauling_scores_batch,
)

# =============================================================================
# Phase 1: Volume & Density Tests
# =============================================================================


class TestEffectiveVolume:
    """Test the effective volume fallback chain."""

    def test_packaged_volume_preferred(self):
        """Packaged volume takes priority over regular volume."""
        engine = ArbitrageEngine()
        volume, source = engine._get_effective_volume(volume=100.0, packaged_volume=10.0)
        assert volume == 10.0
        assert source == "sde_packaged"

    def test_volume_used_when_no_packaged(self):
        """Regular volume used when packaged not available."""
        engine = ArbitrageEngine()
        volume, source = engine._get_effective_volume(volume=100.0, packaged_volume=None)
        assert volume == 100.0
        assert source == "sde_volume"

    def test_default_when_no_volume(self):
        """Default volume used when neither is available."""
        engine = ArbitrageEngine()
        volume, source = engine._get_effective_volume(volume=None, packaged_volume=None)
        assert volume == DEFAULT_VOLUME_M3
        assert source == "fallback"

    def test_default_when_zero_volume(self):
        """Default volume used when values are zero."""
        engine = ArbitrageEngine()
        volume, source = engine._get_effective_volume(volume=0.0, packaged_volume=0.0)
        assert volume == DEFAULT_VOLUME_M3
        assert source == "fallback"

    def test_packaged_zero_falls_through(self):
        """Zero packaged volume falls through to regular volume."""
        engine = ArbitrageEngine()
        volume, source = engine._get_effective_volume(volume=50.0, packaged_volume=0.0)
        assert volume == 50.0
        assert source == "sde_volume"


class TestNetProfitCalculation:
    """Test fee-adjusted net profit calculations."""

    def test_basic_net_profit(self):
        """Test basic net profit calculation with immediate mode (default)."""
        engine = ArbitrageEngine()
        net_profit, net_margin, gross_profit, gross_margin = engine._calculate_net_profit(
            buy_price=100.0,
            sell_price=110.0,
            trade_mode="immediate",  # Explicit: taker-taker, no broker fees
            broker_fee_pct=V2_BROKER_FEE_PCT,
            sales_tax_pct=V2_SALES_TAX_PCT,
        )

        # Gross profit should be 10 ISK
        assert gross_profit == 10.0

        # Gross margin should be 10%
        assert gross_margin == 10.0

        # Immediate mode: no broker fees, only sales tax on sell
        # buy_cost = 100 (no broker fee when taking orders)
        # sell_revenue = 110 * (1 - 0.036) = 110 * 0.964 = 106.04
        # net_profit = 106.04 - 100 = 6.04
        assert net_profit == pytest.approx(6.04, rel=0.01)
        assert net_profit < gross_profit  # Sales tax reduces profit

    def test_high_margin_opportunity(self):
        """Test a high margin opportunity with station_trading mode (broker on both sides)."""
        engine = ArbitrageEngine()
        net_profit, net_margin, gross_profit, gross_margin = engine._calculate_net_profit(
            buy_price=100.0,
            sell_price=120.0,  # 20% gross margin
            trade_mode="station_trading",  # Broker fees on both buy and sell
            broker_fee_pct=V2_BROKER_FEE_PCT,
            sales_tax_pct=V2_SALES_TAX_PCT,
        )

        # Gross: 20 ISK, 20%
        assert gross_profit == 20.0
        assert gross_margin == 20.0

        # Net should be positive with 20% gross margin (station_trading mode)
        # Buy cost = 100 * 1.03 = 103
        # Sell revenue = 120 * (1 - 0.03 - 0.036) = 120 * 0.934 = 112.08
        # Net profit = 112.08 - 103 = 9.08
        assert net_profit > 0
        assert net_profit == pytest.approx(9.08, rel=0.01)

    def test_zero_buy_price_handling(self):
        """Test handling of zero buy price (avoid division by zero)."""
        engine = ArbitrageEngine()
        net_profit, net_margin, gross_profit, gross_margin = engine._calculate_net_profit(
            buy_price=0.0,
            sell_price=100.0,
            broker_fee_pct=V2_BROKER_FEE_PCT,
            sales_tax_pct=V2_SALES_TAX_PCT,
        )

        # Should handle without error, margin calculations return 0
        assert gross_margin == 0.0
        assert net_margin == 0.0

    def test_custom_fee_rates(self):
        """Test with custom fee rates in station_trading mode."""
        engine = ArbitrageEngine()
        net_profit, net_margin, gross_profit, gross_margin = engine._calculate_net_profit(
            buy_price=100.0,
            sell_price=115.0,
            trade_mode="station_trading",  # Broker fees on both buy and sell
            broker_fee_pct=0.01,  # 1% (max standings + skills)
            sales_tax_pct=0.036,  # Accounting V
        )

        # With lower fees and station_trading mode
        # Buy cost = 100 * 1.01 = 101
        # Sell revenue = 115 * (1 - 0.01 - 0.036) = 115 * 0.954 = 109.71
        # Net profit = 109.71 - 101 = 8.71
        assert net_profit == pytest.approx(8.71, rel=0.01)


# =============================================================================
# Phase 3: Hauling Score Tests
# =============================================================================


class TestHaulingScoreCalculation:
    """Test the hauling score algorithm."""

    def test_basic_hauling_score(self):
        """Test basic hauling score calculation."""
        result = calculate_hauling_score(
            net_profit_per_unit=10.0,  # 10 ISK per unit
            volume_m3=0.01,  # Small item (like minerals)
            packaged_volume_m3=None,
            daily_volume=10000,  # High volume
            buy_available_volume=1000,
            sell_available_volume=1000,
            cargo_capacity_m3=10000.0,  # 10k m³ cargo
        )

        # Max by cargo = 10000 / 0.01 = 1,000,000
        # Max by liquidity = 10000 * 0.10 = 1000
        # Max by supply = min(1000, 1000) = 1000
        # safe_quantity = min(1000000, 1000, 1000, 1000) = 1000
        assert result.safe_quantity == 1000

        # Limiting factor should be liquidity (or supply, they're equal)
        assert result.limiting_factor in ["liquidity", "market_supply_buy", "market_supply_sell"]

        # Fill ratio = (1000 * 0.01) / 10000 = 0.001
        assert result.fill_ratio == pytest.approx(0.001, rel=0.01)

        # Expected profit = 10 * 1000 = 10,000
        assert result.expected_profit == 10000.0

    def test_cargo_limited_opportunity(self):
        """Test when cargo capacity is the limiting factor."""
        result = calculate_hauling_score(
            net_profit_per_unit=1000.0,  # High profit per unit
            volume_m3=100.0,  # Large item (100 m³)
            packaged_volume_m3=None,
            daily_volume=10000,  # High volume
            buy_available_volume=10000,
            sell_available_volume=10000,
            cargo_capacity_m3=1000.0,  # Small cargo (1k m³)
        )

        # Max by cargo = 1000 / 100 = 10
        # Max by liquidity = 10000 * 0.10 = 1000
        # safe_quantity = min(10, 1000, 10000, 10000) = 10
        assert result.safe_quantity == 10
        assert result.limiting_factor == "cargo"

        # Fill ratio should be 1.0 (fully filled)
        assert result.fill_ratio == 1.0

        # Expected profit = 1000 * 10 = 10,000
        assert result.expected_profit == 10000.0

    def test_liquidity_limited_opportunity(self):
        """Test when liquidity is the limiting factor."""
        result = calculate_hauling_score(
            net_profit_per_unit=100.0,
            volume_m3=1.0,
            packaged_volume_m3=None,
            daily_volume=100,  # Low daily volume
            buy_available_volume=10000,
            sell_available_volume=10000,
            cargo_capacity_m3=10000.0,
        )

        # Max by cargo = 10000 / 1 = 10000
        # Max by liquidity = 100 * 0.10 = 10
        # safe_quantity = min(10000, 10, 10000, 10000) = 10
        assert result.safe_quantity == 10
        assert result.limiting_factor == "liquidity"

    def test_market_supply_limited_buy(self):
        """Test when buy supply is the limiting factor."""
        result = calculate_hauling_score(
            net_profit_per_unit=100.0,
            volume_m3=1.0,
            packaged_volume_m3=None,
            daily_volume=10000,
            buy_available_volume=5,  # Very limited buy supply
            sell_available_volume=10000,
            cargo_capacity_m3=10000.0,
        )

        # safe_quantity limited by buy supply = 5
        assert result.safe_quantity == 5
        assert result.limiting_factor == "market_supply_buy"

    def test_market_supply_limited_sell(self):
        """Test when sell supply is the limiting factor."""
        result = calculate_hauling_score(
            net_profit_per_unit=100.0,
            volume_m3=1.0,
            packaged_volume_m3=None,
            daily_volume=10000,
            buy_available_volume=10000,
            sell_available_volume=3,  # Very limited sell supply
            cargo_capacity_m3=10000.0,
        )

        # safe_quantity limited by sell supply = 3
        assert result.safe_quantity == 3
        assert result.limiting_factor == "market_supply_sell"

    def test_minimum_safe_quantity(self):
        """Test that safe_quantity is at least MIN_SAFE_QUANTITY."""
        result = calculate_hauling_score(
            net_profit_per_unit=100.0,
            volume_m3=1.0,
            packaged_volume_m3=None,
            daily_volume=1,  # Extremely low volume
            buy_available_volume=100,
            sell_available_volume=100,
            cargo_capacity_m3=10000.0,
        )

        # Even with very low liquidity, should have at least 1 unit
        assert result.safe_quantity >= MIN_SAFE_QUANTITY

    def test_packaged_volume_preferred_in_score(self):
        """Test that packaged volume is used when available."""
        # Ship with large volume but small packaged
        result = calculate_hauling_score(
            net_profit_per_unit=1000000.0,
            volume_m3=50000.0,  # Huge ship volume
            packaged_volume_m3=2500.0,  # But packaged is 2500 m³
            daily_volume=100,
            buy_available_volume=10,
            sell_available_volume=10,
            cargo_capacity_m3=60000.0,
        )

        # Should use packaged volume
        # Max by cargo = 60000 / 2500 = 24
        # But limited by supply = 10
        assert result.safe_quantity == 10

        # Cargo used should be based on packaged volume
        assert result.cargo_used == 10 * 2500.0  # 25000 m³

    def test_no_history_uses_market_proxy(self):
        """Test that absent history falls back to market proxy with 10% liquidity factor."""
        result = calculate_hauling_score(
            net_profit_per_unit=100.0,
            volume_m3=1.0,
            packaged_volume_m3=None,
            daily_volume=None,  # No history
            buy_available_volume=100,
            sell_available_volume=50,
            cargo_capacity_m3=10000.0,
        )

        # Should use market proxy (min of buy/sell available)
        assert result.daily_volume_source == "market_proxy"
        # market_available = min(100, 50) = 50
        # max_by_liquidity = max(1, int(50 * 0.10)) = max(1, 5) = 5
        # safe_quantity = min(10000, 5, 100, 50) = 5
        assert result.safe_quantity == 5
        assert result.limiting_factor == "liquidity"

    def test_no_history_and_no_availability_returns_no_data(self):
        """Test that when both history AND availability are missing, returns no_data."""
        result = calculate_hauling_score(
            net_profit_per_unit=100.0,
            volume_m3=1.0,
            packaged_volume_m3=None,
            daily_volume=None,  # No history
            buy_available_volume=None,  # No availability data
            sell_available_volume=None,  # No availability data
            cargo_capacity_m3=10000.0,
        )

        # Truly no data = no_data limiting factor
        assert result.daily_volume_source == "none"
        assert result.availability_source == "none"
        assert result.safe_quantity == 0
        assert result.score == 0.0
        assert result.limiting_factor == "no_data"
        assert result.limiting_factors == ["no_data"]

    def test_zero_availability_with_history_returns_no_supply(self):
        """Test that when history exists but availability is zero, returns no_supply."""
        result = calculate_hauling_score(
            net_profit_per_unit=100.0,
            volume_m3=1.0,
            packaged_volume_m3=None,
            daily_volume=1000,  # History exists
            buy_available_volume=0,  # Zero supply
            sell_available_volume=0,  # Zero demand
            cargo_capacity_m3=10000.0,
        )

        # We have data but supply is zero = no_supply limiting factor
        assert result.daily_volume_source == "history"
        assert result.availability_source == "both_available"
        assert result.safe_quantity == 0
        assert result.score == 0.0
        assert result.limiting_factor == "no_supply"
        assert result.limiting_factors == ["no_supply"]

    def test_no_availability_with_history_returns_no_data(self):
        """Test that when availability is unknown (None) but history exists, returns no_data.

        This is distinct from zero availability - None means we don't know the supply,
        not that supply is confirmed zero. Having history data doesn't change that.
        """
        result = calculate_hauling_score(
            net_profit_per_unit=100.0,
            volume_m3=1.0,
            packaged_volume_m3=None,
            daily_volume=1000,  # History exists
            buy_available_volume=None,  # Unknown, not zero
            sell_available_volume=None,  # Unknown, not zero
            cargo_capacity_m3=10000.0,
        )

        # Availability is unknown - this is no_data, not no_supply
        assert result.daily_volume_source == "history"
        assert result.availability_source == "none"
        assert result.safe_quantity == 0
        assert result.score == 0.0
        assert result.limiting_factor == "no_data"
        assert result.limiting_factors == ["no_data"]

    def test_proxy_from_sell_excludes_buy_from_limiting_factors(self):
        """Test that when proxying from sell, market_supply_buy is not reported as limiting."""
        result = calculate_hauling_score(
            net_profit_per_unit=100.0,
            volume_m3=1.0,
            packaged_volume_m3=None,
            daily_volume=1000,
            buy_available_volume=None,  # Proxied from sell
            sell_available_volume=50,  # This is the real data
            cargo_capacity_m3=10000.0,
        )

        # Should proxy from sell
        assert result.availability_source == "proxy_from_sell"
        # market_supply_buy should NOT be in limiting_factors since it's proxied
        assert "market_supply_buy" not in result.limiting_factors

    def test_proxy_from_buy_excludes_sell_from_limiting_factors(self):
        """Test that when proxying from buy, market_supply_sell is not reported as limiting."""
        result = calculate_hauling_score(
            net_profit_per_unit=100.0,
            volume_m3=1.0,
            packaged_volume_m3=None,
            daily_volume=1000,
            buy_available_volume=50,  # This is the real data
            sell_available_volume=None,  # Proxied from buy
            cargo_capacity_m3=10000.0,
        )

        # Should proxy from buy
        assert result.availability_source == "proxy_from_buy"
        # market_supply_sell should NOT be in limiting_factors since it's proxied
        assert "market_supply_sell" not in result.limiting_factors

    def test_multiple_limiting_factors(self):
        """Test identification of multiple binding constraints."""
        result = calculate_hauling_score(
            net_profit_per_unit=100.0,
            volume_m3=1.0,
            packaged_volume_m3=None,
            daily_volume=100,  # Max by liquidity = 10
            buy_available_volume=10,  # Also 10
            sell_available_volume=10,  # Also 10
            cargo_capacity_m3=10000.0,
        )

        # Multiple factors are binding at 10
        assert result.safe_quantity == 10
        assert len(result.limiting_factors) >= 2

    def test_fallback_volume_when_both_none(self):
        """Test that fallback volume is used when both volumes are None."""
        result = calculate_hauling_score(
            net_profit_per_unit=100.0,
            volume_m3=None,  # No volume data
            packaged_volume_m3=None,  # No packaged volume either
            daily_volume=1000,
            buy_available_volume=100,
            sell_available_volume=100,
            cargo_capacity_m3=10.0,  # Small cargo
        )

        # Should use fallback volume (0.01 m³)
        assert result.volume_source == "fallback"
        # With fallback volume 0.01, max by cargo = 10 / 0.01 = 1000
        # safe_quantity = min(1000, 100, 100, 100) = 100 (limited by liquidity or supply)
        assert result.safe_quantity == 100

    def test_fallback_volume_when_both_zero(self):
        """Test that fallback volume is used when both volumes are zero."""
        result = calculate_hauling_score(
            net_profit_per_unit=100.0,
            volume_m3=0.0,  # Zero volume
            packaged_volume_m3=0.0,  # Zero packaged volume
            daily_volume=1000,
            buy_available_volume=100,
            sell_available_volume=100,
            cargo_capacity_m3=10.0,
        )

        # Should use fallback volume (0.01 m³)
        assert result.volume_source == "fallback"


class TestCalculateHaulingScoresBatch:
    """Tests for calculate_hauling_scores_batch function."""

    def test_batch_basic(self):
        """Test batch calculation on multiple opportunities."""
        opportunities = [
            {
                "type_id": 34,
                "net_profit_per_unit": 0.50,
                "item_volume_m3": 0.01,
                "buy_available_volume": 1000000,
                "sell_available_volume": 1000000,
                "daily_volume": 100000000,
            },
            {
                "type_id": 35,
                "net_profit_per_unit": 0.75,
                "item_volume_m3": 0.01,
                "buy_available_volume": 500000,
                "sell_available_volume": 500000,
                "daily_volume": 50000000,
            },
        ]

        results = calculate_hauling_scores_batch(opportunities, cargo_capacity_m3=60000.0)

        assert len(results) == 2
        assert 34 in results
        assert 35 in results
        assert isinstance(results[34], HaulingScoreResult)
        assert isinstance(results[35], HaulingScoreResult)

    def test_batch_empty_list(self):
        """Test batch calculation with empty list."""
        results = calculate_hauling_scores_batch([], cargo_capacity_m3=60000.0)
        assert results == {}

    def test_batch_with_missing_fields(self):
        """Test batch calculation handles missing optional fields."""
        opportunities = [
            {
                "type_id": 34,
                "net_profit_per_unit": 100.0,
                # Missing volume, daily_volume, availability
            },
        ]

        results = calculate_hauling_scores_batch(opportunities, cargo_capacity_m3=60000.0)

        assert 34 in results
        # Should work with defaults/None values
        assert results[34].limiting_factor in ("no_data", "cargo", "liquidity")

    def test_batch_uses_packaged_volume(self):
        """Test batch calculation prefers packaged volume."""
        opportunities = [
            {
                "type_id": 34,
                "net_profit_per_unit": 100.0,
                "item_volume_m3": 100.0,  # Large volume
                "item_packaged_volume_m3": 1.0,  # Small packaged
                "buy_available_volume": 1000,
                "sell_available_volume": 1000,
                "daily_volume": 10000,
            },
        ]

        results = calculate_hauling_scores_batch(opportunities, cargo_capacity_m3=60000.0)

        # Should use packaged volume (1.0) not regular (100.0)
        assert results[34].volume_source == "sde_packaged"


class TestHaulingScoreRanking:
    """Test that hauling score correctly ranks opportunities."""

    def test_tritanium_vs_plex_ranking(self):
        """Test that high-value items rank higher despite lower margin."""
        # Tritanium: High margin but low profit density
        tritanium = calculate_hauling_score(
            net_profit_per_unit=0.50,  # 0.50 ISK per unit
            volume_m3=0.01,  # Very small
            packaged_volume_m3=None,
            daily_volume=100000000,  # Very high volume
            buy_available_volume=10000000,
            sell_available_volume=10000000,
            cargo_capacity_m3=60000.0,  # Iteron cargo
        )

        # PLEX: Lower margin but much higher profit density
        plex = calculate_hauling_score(
            net_profit_per_unit=100000.0,  # 100k ISK per unit
            volume_m3=0.01,  # Same small volume
            packaged_volume_m3=None,
            daily_volume=5000,  # Lower volume
            buy_available_volume=1000,
            sell_available_volume=1000,
            cargo_capacity_m3=60000.0,
        )

        # PLEX should have higher score despite lower daily volume
        # Tritanium: profit_density = 0.50 / 0.01 = 50 ISK/m³
        # PLEX: profit_density = 100000 / 0.01 = 10,000,000 ISK/m³
        assert plex.score > tritanium.score

    def test_expected_profit_comparison(self):
        """Test expected profit reflects liquidity constraints."""
        # Item A: High margin, low liquidity
        item_a = calculate_hauling_score(
            net_profit_per_unit=10000.0,
            volume_m3=1.0,
            packaged_volume_m3=None,
            daily_volume=10,  # Very low
            buy_available_volume=5,
            sell_available_volume=5,
            cargo_capacity_m3=10000.0,
        )

        # Item B: Lower margin, high liquidity
        item_b = calculate_hauling_score(
            net_profit_per_unit=100.0,  # 100x less profit per unit
            volume_m3=1.0,
            packaged_volume_m3=None,
            daily_volume=100000,  # High
            buy_available_volume=50000,
            sell_available_volume=50000,
            cargo_capacity_m3=10000.0,
        )

        # Item B might have higher expected profit due to volume
        # Item A: safe_quantity = min(10000, 1, 5, 5) = 1, expected = 10000
        # Item B: safe_quantity = min(10000, 10000, 50000, 50000) = 10000, expected = 1,000,000
        assert item_b.expected_profit > item_a.expected_profit


# =============================================================================
# Model Tests
# =============================================================================


class TestArbitrageOpportunityModel:
    """Test the ArbitrageOpportunity model with V2 fields."""

    def test_default_volume_constant(self):
        """Test DEFAULT_VOLUME_M3 constant is set correctly."""
        assert DEFAULT_VOLUME_M3 == 0.01

    def test_v2_fields_have_defaults(self):
        """Test that V2 fields have appropriate defaults."""
        opp = ArbitrageOpportunity(
            type_id=34,
            type_name="Tritanium",
            buy_region="The Forge",
            buy_region_id=10000002,
            sell_region="Domain",
            sell_region_id=10000043,
            buy_price=5.0,
            sell_price=6.0,
            profit_per_unit=1.0,
            profit_pct=20.0,
            available_volume=1000,
        )

        # V2 defaults
        assert opp.item_volume_m3 == 0.01
        assert opp.item_packaged_volume_m3 is None
        assert opp.profit_density is None
        assert opp.broker_fee_pct == 0.03
        assert opp.sales_tax_pct == 0.036

        # Hauling score fields should be None by default
        assert opp.hauling_score is None
        assert opp.safe_quantity is None
        assert opp.expected_profit is None
        assert opp.limiting_factor is None

    def test_v2_fields_can_be_set(self):
        """Test that V2 fields can be set."""
        opp = ArbitrageOpportunity(
            type_id=34,
            type_name="Tritanium",
            buy_region="The Forge",
            buy_region_id=10000002,
            sell_region="Domain",
            sell_region_id=10000043,
            buy_price=5.0,
            sell_price=6.0,
            profit_per_unit=1.0,
            profit_pct=20.0,
            available_volume=1000,
            # V2 fields
            item_volume_m3=0.01,
            profit_density=100.0,
            net_profit_per_unit=0.85,
            net_margin_pct=15.0,
            daily_volume=5000000,
            daily_volume_source="history",
            hauling_score=500.0,
            safe_quantity=500,
            expected_profit=425.0,
            fill_ratio=0.005,
            limiting_factor="liquidity",
            limiting_factors=["liquidity"],
        )

        assert opp.profit_density == 100.0
        assert opp.net_profit_per_unit == 0.85
        assert opp.daily_volume == 5000000
        assert opp.hauling_score == 500.0
        assert opp.limiting_factor == "liquidity"


# =============================================================================
# Integration Tests (require database)
# =============================================================================


@pytest.mark.asyncio
class TestEngineIntegration:
    """Integration tests for the arbitrage engine (requires database)."""

    async def test_hauling_score_sort_requires_cargo(self):
        """Test that hauling_score sort requires cargo_capacity_m3."""
        engine = ArbitrageEngine(allow_stale=True)

        with pytest.raises(ValueError, match="requires cargo_capacity_m3"):
            await engine.find_opportunities(
                sort_by="hauling_score",
                cargo_capacity_m3=None,  # Missing!
            )

    async def test_cargo_capacity_enables_hauling_fields(self):
        """Test that providing cargo_capacity populates hauling fields."""
        # This test would require a populated database
        # Skipping actual execution, just verifying the interface
        engine = ArbitrageEngine(allow_stale=True)

        # The method should accept cargo_capacity_m3
        assert "cargo_capacity_m3" in engine.find_opportunities.__code__.co_varnames
