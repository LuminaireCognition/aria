"""
Tests for Market Models.

Tests model validation, trade hub resolution, and region lookup.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError


# =============================================================================
# MarketModel Tests
# =============================================================================


class TestMarketModel:
    """Test MarketModel base class."""

    def test_frozen_config(self):
        """Models are frozen by default."""
        from aria_esi.models.market import PriceAggregate

        agg = PriceAggregate(order_count=10, volume=1000)
        with pytest.raises(ValidationError):
            agg.order_count = 20

    def test_extra_forbid(self):
        """Extra fields are forbidden."""
        from aria_esi.models.market import PriceAggregate

        with pytest.raises(ValidationError):
            PriceAggregate(order_count=10, volume=1000, unknown_field="test")


# =============================================================================
# PriceAggregate Tests
# =============================================================================


class TestPriceAggregate:
    """Test PriceAggregate model."""

    def test_valid_construction(self):
        """Valid PriceAggregate constructs correctly."""
        from aria_esi.models.market import PriceAggregate

        agg = PriceAggregate(
            order_count=10,
            volume=1000,
            min_price=100.0,
            max_price=200.0,
            weighted_avg=150.0,
        )
        assert agg.order_count == 10
        assert agg.volume == 1000
        assert agg.min_price == 100.0

    def test_defaults(self):
        """PriceAggregate has correct defaults."""
        from aria_esi.models.market import PriceAggregate

        agg = PriceAggregate(order_count=0, volume=0)
        assert agg.min_price is None
        assert agg.max_price is None
        assert agg.weighted_avg is None
        assert agg.median is None

    def test_validation_negative_count(self):
        """Negative order count is rejected."""
        from aria_esi.models.market import PriceAggregate

        with pytest.raises(ValidationError):
            PriceAggregate(order_count=-1, volume=0)


# =============================================================================
# ItemPrice Tests
# =============================================================================


class TestItemPrice:
    """Test ItemPrice model."""

    def test_valid_construction(self):
        """Valid ItemPrice constructs correctly."""
        from aria_esi.models.market import ItemPrice, PriceAggregate

        buy = PriceAggregate(order_count=5, volume=500)
        sell = PriceAggregate(order_count=10, volume=1000)
        item = ItemPrice(
            type_id=34,
            type_name="Tritanium",
            buy=buy,
            sell=sell,
        )
        assert item.type_id == 34
        assert item.type_name == "Tritanium"

    def test_spread_values(self):
        """ItemPrice can have spread values."""
        from aria_esi.models.market import ItemPrice, PriceAggregate

        buy = PriceAggregate(order_count=5, volume=500)
        sell = PriceAggregate(order_count=10, volume=1000)
        item = ItemPrice(
            type_id=34,
            type_name="Tritanium",
            buy=buy,
            sell=sell,
            spread=10.5,
            spread_percent=5.0,
        )
        assert item.spread == 10.5
        assert item.spread_percent == 5.0


# =============================================================================
# Trade Hub Resolution Tests
# =============================================================================


class TestResolveTradeHub:
    """Test resolve_trade_hub function."""

    def test_direct_match(self):
        """Direct hub name matches."""
        from aria_esi.models.market import resolve_trade_hub

        hub = resolve_trade_hub("jita")
        assert hub is not None
        assert hub["region_name"] == "The Forge"
        assert hub["station_id"] == 60003760

    def test_case_insensitive(self):
        """Hub lookup is case-insensitive."""
        from aria_esi.models.market import resolve_trade_hub

        hub = resolve_trade_hub("JITA")
        assert hub is not None
        assert hub["region_name"] == "The Forge"

        hub = resolve_trade_hub("JiTa")
        assert hub is not None
        assert hub["region_name"] == "The Forge"

    def test_whitespace_trimmed(self):
        """Whitespace is trimmed from input."""
        from aria_esi.models.market import resolve_trade_hub

        hub = resolve_trade_hub("  jita  ")
        assert hub is not None
        assert hub["region_name"] == "The Forge"

    def test_partial_match(self):
        """Partial hub names match."""
        from aria_esi.models.market import resolve_trade_hub

        hub = resolve_trade_hub("jit")
        assert hub is not None
        assert hub["region_name"] == "The Forge"

        hub = resolve_trade_hub("ama")
        assert hub is not None
        assert hub["region_name"] == "Domain"

    def test_unknown_hub(self):
        """Unknown hub returns None."""
        from aria_esi.models.market import resolve_trade_hub

        hub = resolve_trade_hub("unknown_hub")
        assert hub is None

    def test_all_major_hubs(self):
        """All major hubs resolve correctly."""
        from aria_esi.models.market import resolve_trade_hub

        hubs = ["jita", "amarr", "dodixie", "rens", "hek"]
        for hub_name in hubs:
            hub = resolve_trade_hub(hub_name)
            assert hub is not None, f"Failed to resolve {hub_name}"
            assert "region_id" in hub
            assert "station_id" in hub


# =============================================================================
# Region Resolution Tests
# =============================================================================


class TestResolveRegion:
    """Test resolve_region function."""

    def test_trade_hub_returns_full_info(self):
        """Trade hub lookup returns full station info."""
        from aria_esi.models.market import resolve_region

        region = resolve_region("jita")
        assert region is not None
        assert region["region_name"] == "The Forge"
        assert region["station_id"] == 60003760
        assert region["system_id"] == 30000142

    def test_numeric_region_id(self):
        """Numeric region ID returns minimal info."""
        from aria_esi.models.market import resolve_region

        region = resolve_region("10000002")
        assert region is not None
        assert region["region_id"] == 10000002
        assert region["station_id"] is None
        assert region["system_id"] is None


# =============================================================================
# Trade Hub Constants Tests
# =============================================================================


class TestTradeHubConstants:
    """Test TRADE_HUBS constant."""

    def test_trade_hubs_defined(self):
        """TRADE_HUBS dict is defined with expected hubs."""
        from aria_esi.models.market import TRADE_HUBS

        assert "jita" in TRADE_HUBS
        assert "amarr" in TRADE_HUBS
        assert "dodixie" in TRADE_HUBS
        assert "rens" in TRADE_HUBS
        assert "hek" in TRADE_HUBS

    def test_trade_hub_structure(self):
        """Each trade hub has required fields."""
        from aria_esi.models.market import TRADE_HUBS

        for hub_name, config in TRADE_HUBS.items():
            assert "region_id" in config, f"{hub_name} missing region_id"
            assert "region_name" in config, f"{hub_name} missing region_name"
            assert "station_id" in config, f"{hub_name} missing station_id"
            assert "station_name" in config, f"{hub_name} missing station_name"
            assert "system_id" in config, f"{hub_name} missing system_id"

    def test_jita_specific_values(self):
        """Jita has correct values."""
        from aria_esi.models.market import TRADE_HUBS

        jita = TRADE_HUBS["jita"]
        assert jita["region_id"] == 10000002
        assert jita["system_id"] == 30000142
        assert "Caldari Navy" in jita["station_name"]


# =============================================================================
# Type Alias Tests
# =============================================================================


class TestTypeAliases:
    """Test type alias validation."""

    def test_freshness_level_values(self):
        """FreshnessLevel accepts valid values."""
        from aria_esi.models.market import ItemPrice, PriceAggregate

        buy = PriceAggregate(order_count=0, volume=0)
        sell = PriceAggregate(order_count=0, volume=0)

        for freshness in ["fresh", "recent", "stale"]:
            item = ItemPrice(
                type_id=1,
                type_name="Test",
                buy=buy,
                sell=sell,
                freshness=freshness,
            )
            assert item.freshness == freshness

    def test_order_type_values(self):
        """OrderType is correctly defined."""
        from aria_esi.models.market import MarketOrdersResult

        # Build valid result
        result = MarketOrdersResult(
            type_id=34,
            type_name="Tritanium",
            region="The Forge",
            region_id=10000002,
        )
        assert result is not None


# =============================================================================
# Default Volume Constant Tests
# =============================================================================


class TestVolumeConstants:
    """Test volume-related constants."""

    def test_default_volume_defined(self):
        """DEFAULT_VOLUME_M3 is defined and positive."""
        from aria_esi.models.market import DEFAULT_VOLUME_M3

        assert DEFAULT_VOLUME_M3 > 0
        assert DEFAULT_VOLUME_M3 == 0.01
