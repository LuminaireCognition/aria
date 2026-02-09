"""
Tests for Hauling Score Calculator.

Tests the hauling score algorithm that transforms arbitrage ranking
from "highest margin" to "best ISK per trip".
"""

from __future__ import annotations

import pytest


# =============================================================================
# Constants Tests
# =============================================================================


class TestHaulingScoreConstants:
    """Test hauling score constants."""

    def test_default_liquidity_factor(self):
        """Default liquidity factor is 10%."""
        from aria_esi.services.hauling_score import DEFAULT_LIQUIDITY_FACTOR

        assert DEFAULT_LIQUIDITY_FACTOR == 0.10

    def test_min_safe_quantity(self):
        """Minimum safe quantity is 1."""
        from aria_esi.services.hauling_score import MIN_SAFE_QUANTITY

        assert MIN_SAFE_QUANTITY == 1


# =============================================================================
# Basic Hauling Score Tests
# =============================================================================


class TestCalculateHaulingScore:
    """Test calculate_hauling_score function."""

    def test_basic_calculation(self):
        """Basic hauling score calculation works."""
        from aria_esi.services.hauling_score import calculate_hauling_score

        result = calculate_hauling_score(
            net_profit_per_unit=1000.0,
            volume_m3=1.0,
            packaged_volume_m3=None,
            daily_volume=100,
            buy_available_volume=50,
            sell_available_volume=50,
            cargo_capacity_m3=100.0,
        )

        assert result.score > 0
        assert result.safe_quantity > 0
        assert result.expected_profit > 0

    def test_uses_packaged_volume_when_available(self):
        """Packaged volume takes priority over regular volume."""
        from aria_esi.services.hauling_score import calculate_hauling_score

        result = calculate_hauling_score(
            net_profit_per_unit=1000.0,
            volume_m3=10.0,
            packaged_volume_m3=1.0,  # Smaller packaged volume
            daily_volume=100,
            buy_available_volume=50,
            sell_available_volume=50,
            cargo_capacity_m3=100.0,
        )

        assert result.volume_source == "sde_packaged"

    def test_uses_regular_volume_when_no_packaged(self):
        """Regular volume used when no packaged volume."""
        from aria_esi.services.hauling_score import calculate_hauling_score

        result = calculate_hauling_score(
            net_profit_per_unit=1000.0,
            volume_m3=1.0,
            packaged_volume_m3=None,
            daily_volume=100,
            buy_available_volume=50,
            sell_available_volume=50,
            cargo_capacity_m3=100.0,
        )

        assert result.volume_source == "sde_volume"

    def test_fallback_volume_when_no_volume_data(self):
        """Falls back to default volume when none provided."""
        from aria_esi.services.hauling_score import calculate_hauling_score

        result = calculate_hauling_score(
            net_profit_per_unit=1000.0,
            volume_m3=None,
            packaged_volume_m3=None,
            daily_volume=100,
            buy_available_volume=50,
            sell_available_volume=50,
            cargo_capacity_m3=100.0,
        )

        assert result.volume_source == "fallback"


# =============================================================================
# Limiting Factor Tests
# =============================================================================


class TestLimitingFactors:
    """Test limiting factor detection."""

    def test_cargo_limited(self):
        """Detects cargo as limiting factor."""
        from aria_esi.services.hauling_score import calculate_hauling_score

        result = calculate_hauling_score(
            net_profit_per_unit=1000.0,
            volume_m3=10.0,  # Large item
            packaged_volume_m3=None,
            daily_volume=10000,  # High liquidity
            buy_available_volume=10000,  # High availability
            sell_available_volume=10000,
            cargo_capacity_m3=50.0,  # Small cargo
        )

        assert "cargo" in result.limiting_factors

    def test_liquidity_limited(self):
        """Detects liquidity as limiting factor."""
        from aria_esi.services.hauling_score import calculate_hauling_score

        result = calculate_hauling_score(
            net_profit_per_unit=1000.0,
            volume_m3=0.01,  # Tiny item
            packaged_volume_m3=None,
            daily_volume=10,  # Low daily volume
            buy_available_volume=10000,
            sell_available_volume=10000,
            cargo_capacity_m3=10000.0,  # Huge cargo
        )

        assert "liquidity" in result.limiting_factors

    def test_market_supply_buy_limited(self):
        """Detects buy-side market supply as limiting factor."""
        from aria_esi.services.hauling_score import calculate_hauling_score

        result = calculate_hauling_score(
            net_profit_per_unit=1000.0,
            volume_m3=0.01,
            packaged_volume_m3=None,
            daily_volume=10000,
            buy_available_volume=5,  # Low buy availability
            sell_available_volume=10000,
            cargo_capacity_m3=10000.0,
        )

        assert "market_supply_buy" in result.limiting_factors

    def test_market_supply_sell_limited(self):
        """Detects sell-side market supply as limiting factor."""
        from aria_esi.services.hauling_score import calculate_hauling_score

        result = calculate_hauling_score(
            net_profit_per_unit=1000.0,
            volume_m3=0.01,
            packaged_volume_m3=None,
            daily_volume=10000,
            buy_available_volume=10000,
            sell_available_volume=5,  # Low sell availability
            cargo_capacity_m3=10000.0,
        )

        assert "market_supply_sell" in result.limiting_factors


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_zero_daily_volume_with_availability(self):
        """Handles zero daily volume when market availability exists."""
        from aria_esi.services.hauling_score import calculate_hauling_score

        result = calculate_hauling_score(
            net_profit_per_unit=1000.0,
            volume_m3=1.0,
            packaged_volume_m3=None,
            daily_volume=None,
            buy_available_volume=50,
            sell_available_volume=50,
            cargo_capacity_m3=100.0,
        )

        assert result.daily_volume_source == "market_proxy"
        assert result.safe_quantity > 0

    def test_no_data_returns_zero(self):
        """Returns zero score when no data available."""
        from aria_esi.services.hauling_score import calculate_hauling_score

        result = calculate_hauling_score(
            net_profit_per_unit=1000.0,
            volume_m3=1.0,
            packaged_volume_m3=None,
            daily_volume=None,
            buy_available_volume=None,
            sell_available_volume=None,
            cargo_capacity_m3=100.0,
        )

        assert result.score == 0.0
        assert result.safe_quantity == 0
        assert result.limiting_factor == "no_data"

    def test_no_supply_returns_zero(self):
        """Returns zero score when supply is exhausted."""
        from aria_esi.services.hauling_score import calculate_hauling_score

        result = calculate_hauling_score(
            net_profit_per_unit=1000.0,
            volume_m3=1.0,
            packaged_volume_m3=None,
            daily_volume=100,
            buy_available_volume=0,  # No supply
            sell_available_volume=0,
            cargo_capacity_m3=100.0,
        )

        assert result.score == 0.0
        assert result.limiting_factor == "no_supply"

    def test_proxy_from_sell(self):
        """Proxies buy availability from sell when buy is None."""
        from aria_esi.services.hauling_score import calculate_hauling_score

        result = calculate_hauling_score(
            net_profit_per_unit=1000.0,
            volume_m3=1.0,
            packaged_volume_m3=None,
            daily_volume=100,
            buy_available_volume=None,
            sell_available_volume=50,
            cargo_capacity_m3=100.0,
        )

        assert result.availability_source == "proxy_from_sell"
        assert result.safe_quantity > 0

    def test_proxy_from_buy(self):
        """Proxies sell availability from buy when sell is None."""
        from aria_esi.services.hauling_score import calculate_hauling_score

        result = calculate_hauling_score(
            net_profit_per_unit=1000.0,
            volume_m3=1.0,
            packaged_volume_m3=None,
            daily_volume=100,
            buy_available_volume=50,
            sell_available_volume=None,
            cargo_capacity_m3=100.0,
        )

        assert result.availability_source == "proxy_from_buy"
        assert result.safe_quantity > 0


# =============================================================================
# Fill Ratio Tests
# =============================================================================


class TestFillRatio:
    """Test fill ratio calculations."""

    def test_full_cargo(self):
        """Fill ratio is 1.0 when cargo is full."""
        from aria_esi.services.hauling_score import calculate_hauling_score

        result = calculate_hauling_score(
            net_profit_per_unit=1000.0,
            volume_m3=10.0,
            packaged_volume_m3=None,
            daily_volume=1000,  # High liquidity
            buy_available_volume=1000,
            sell_available_volume=1000,
            cargo_capacity_m3=100.0,  # 10 items fill cargo
        )

        assert result.fill_ratio == 1.0 or result.fill_ratio > 0.9

    def test_partial_cargo(self):
        """Fill ratio less than 1.0 for partial cargo."""
        from aria_esi.services.hauling_score import calculate_hauling_score

        result = calculate_hauling_score(
            net_profit_per_unit=1000.0,
            volume_m3=10.0,
            packaged_volume_m3=None,
            daily_volume=5,  # Low liquidity limits to ~1 unit
            buy_available_volume=1000,
            sell_available_volume=1000,
            cargo_capacity_m3=1000.0,  # Much bigger than needed
        )

        # Fill ratio should be small (1 unit * 10m3 / 1000m3 = 0.01)
        assert result.fill_ratio < 0.5


# =============================================================================
# Batch Calculation Tests
# =============================================================================


class TestBatchCalculation:
    """Test batch hauling score calculation."""

    def test_batch_multiple_items(self):
        """Batch calculation handles multiple items."""
        from aria_esi.services.hauling_score import calculate_hauling_scores_batch

        opportunities = [
            {
                "type_id": 34,
                "net_profit_per_unit": 100.0,
                "item_volume_m3": 0.01,
                "item_packaged_volume_m3": None,
                "daily_volume": 1000000,
                "buy_available_volume": 10000,
                "sell_available_volume": 10000,
            },
            {
                "type_id": 35,
                "net_profit_per_unit": 50.0,
                "item_volume_m3": 0.01,
                "item_packaged_volume_m3": None,
                "daily_volume": 500000,
                "buy_available_volume": 5000,
                "sell_available_volume": 5000,
            },
        ]

        results = calculate_hauling_scores_batch(opportunities, cargo_capacity_m3=1000.0)

        assert 34 in results
        assert 35 in results
        assert results[34].score > 0
        assert results[35].score > 0

    def test_batch_empty_list(self):
        """Batch calculation handles empty list."""
        from aria_esi.services.hauling_score import calculate_hauling_scores_batch

        results = calculate_hauling_scores_batch([], cargo_capacity_m3=1000.0)

        assert results == {}

    def test_batch_with_custom_liquidity_factor(self):
        """Batch calculation respects custom liquidity factor."""
        from aria_esi.services.hauling_score import calculate_hauling_scores_batch

        opportunities = [
            {
                "type_id": 34,
                "net_profit_per_unit": 100.0,
                "item_volume_m3": 0.01,
                "item_packaged_volume_m3": None,
                "daily_volume": 100,
                "buy_available_volume": 10000,
                "sell_available_volume": 10000,
            },
        ]

        # Default 10% liquidity = 10 units
        results_default = calculate_hauling_scores_batch(
            opportunities, cargo_capacity_m3=1000.0, liquidity_factor=0.10
        )

        # Custom 5% liquidity = 5 units
        results_custom = calculate_hauling_scores_batch(
            opportunities, cargo_capacity_m3=1000.0, liquidity_factor=0.05
        )

        # Lower liquidity factor should result in lower safe_quantity
        assert results_custom[34].safe_quantity <= results_default[34].safe_quantity
