"""
Tests for aria_esi.mcp.market.cache

Tests market cache logic including freshness, TTL, and fallback behavior.
"""

import time
from unittest.mock import patch

import pytest


class TestCacheLayer:
    """Tests for CacheLayer dataclass."""

    def test_default_state(self):
        from aria_esi.mcp.market.cache import CacheLayer

        layer = CacheLayer(name="test")

        assert layer.name == "test"
        assert layer.data == {}
        assert layer.timestamp == 0.0
        assert layer.is_stale() is True  # No data = stale

    def test_is_stale_fresh(self):
        from aria_esi.mcp.market.cache import CacheLayer

        layer = CacheLayer(name="test", ttl_seconds=300)
        layer.timestamp = time.time()  # Just set

        assert layer.is_stale() is False

    def test_is_stale_expired(self):
        from aria_esi.mcp.market.cache import CacheLayer

        layer = CacheLayer(name="test", ttl_seconds=300)
        layer.timestamp = time.time() - 400  # 400 seconds ago (> 300 TTL)

        assert layer.is_stale() is True

    def test_get_age_seconds_no_data(self):
        from aria_esi.mcp.market.cache import CacheLayer

        layer = CacheLayer(name="test")

        assert layer.get_age_seconds() is None

    def test_get_age_seconds_with_data(self):
        from aria_esi.mcp.market.cache import CacheLayer

        layer = CacheLayer(name="test")
        layer.timestamp = time.time() - 100  # 100 seconds ago

        age = layer.get_age_seconds()
        assert age is not None
        assert 99 <= age <= 101  # Allow small variance


class TestMarketCacheInit:
    """Tests for MarketCache initialization."""

    def test_default_init(self):
        from aria_esi.mcp.market.cache import MarketCache

        cache = MarketCache()

        assert cache._region_id == 10000002  # The Forge (Jita)
        assert cache._station_id == 60003760  # Jita 4-4
        assert cache._station_only is True

    def test_init_with_region(self):
        from aria_esi.mcp.market.cache import MarketCache

        cache = MarketCache(region="amarr")

        assert cache._region_id == 10000043  # Domain
        assert cache._station_id == 60008494  # Amarr

    def test_init_without_station_filter(self):
        from aria_esi.mcp.market.cache import MarketCache

        cache = MarketCache(station_only=False)

        assert cache._station_id is None

    def test_init_unknown_region_defaults_to_jita(self):
        from aria_esi.mcp.market.cache import MarketCache

        cache = MarketCache(region="nonexistent")

        # Should default to Jita
        assert cache._region_id == 10000002


class TestMarketCacheFreshness:
    """Tests for freshness classification."""

    def test_fresh_threshold(self):
        from aria_esi.mcp.market.cache import MarketCache

        cache = MarketCache()
        now = time.time()

        # Less than 5 minutes = fresh
        assert cache.get_freshness(now - 100) == "fresh"
        assert cache.get_freshness(now - 299) == "fresh"

    def test_recent_threshold(self):
        from aria_esi.mcp.market.cache import MarketCache

        cache = MarketCache()
        now = time.time()

        # 5-30 minutes = recent
        assert cache.get_freshness(now - 300) == "recent"
        assert cache.get_freshness(now - 600) == "recent"
        assert cache.get_freshness(now - 1799) == "recent"

    def test_stale_threshold(self):
        from aria_esi.mcp.market.cache import MarketCache

        cache = MarketCache()
        now = time.time()

        # More than 30 minutes = stale
        assert cache.get_freshness(now - 1800) == "stale"
        assert cache.get_freshness(now - 3600) == "stale"


class TestMarketCacheStatus:
    """Tests for cache status reporting."""

    def test_get_cache_status_empty(self):
        from aria_esi.mcp.market.cache import MarketCache

        cache = MarketCache()
        status = cache.get_cache_status()

        assert "fuzzwork" in status
        assert "esi_orders" in status
        assert status["fuzzwork"]["cached_types"] == 0
        assert status["fuzzwork"]["stale"] is True

    def test_get_cache_status_with_data(self):
        from aria_esi.mcp.market.cache import CachedPrice, MarketCache, PriceAggregate

        cache = MarketCache()

        # Add some cached data
        mock_price = CachedPrice(
            type_id=34,
            type_name="Tritanium",
            buy=PriceAggregate(order_count=100, volume=1000000),
            sell=PriceAggregate(order_count=50, volume=500000),
            spread=0.05,
            spread_percent=5.0,
            timestamp=time.time(),
            source="fuzzwork",
        )
        cache._fuzzwork.data[34] = mock_price
        cache._fuzzwork.timestamp = time.time()

        status = cache.get_cache_status()

        assert status["fuzzwork"]["cached_types"] == 1
        assert status["fuzzwork"]["stale"] is False


class TestMarketCacheGetPrices:
    """Tests for get_prices method."""

    @pytest.mark.asyncio
    async def test_get_prices_empty_input(self):
        from aria_esi.mcp.market.cache import MarketCache

        cache = MarketCache()
        result = await cache.get_prices([])

        assert result == []

    @pytest.mark.asyncio
    async def test_get_price_single_item(self):
        from aria_esi.mcp.market.cache import MarketCache

        cache = MarketCache()

        # Mock the Fuzzwork client
        with patch.object(cache, "_get_from_fuzzwork") as mock_fuzzwork:
            from aria_esi.models.market import ItemPrice, PriceAggregate

            mock_price = ItemPrice(
                type_id=34,
                type_name="Tritanium",
                buy=PriceAggregate(order_count=100, volume=1000000, max_price=4.0),
                sell=PriceAggregate(order_count=50, volume=500000, min_price=4.05),
                spread=0.05,
                spread_percent=1.23,
            )
            mock_fuzzwork.return_value = [mock_price]

            result = await cache.get_price(34, "Tritanium")

            assert result is not None
            assert result.type_id == 34


class TestMarketCacheSingleton:
    """Tests for singleton pattern."""

    def test_get_market_cache_singleton(self):
        from aria_esi.mcp.market.cache import get_market_cache, reset_market_cache

        # Reset first to ensure clean state
        reset_market_cache()

        cache1 = get_market_cache()
        cache2 = get_market_cache()

        assert cache1 is cache2

    def test_reset_market_cache(self):
        from aria_esi.mcp.market.cache import get_market_cache, reset_market_cache

        cache1 = get_market_cache()
        reset_market_cache()
        cache2 = get_market_cache()

        assert cache1 is not cache2


class TestAggregateToItemPrice:
    """Tests for converting Fuzzwork aggregates to ItemPrice."""

    def test_full_aggregate(self):
        from aria_esi.mcp.market.cache import MarketCache
        from aria_esi.mcp.market.clients import FuzzworkAggregate

        cache = MarketCache()

        agg = FuzzworkAggregate(
            type_id=34,
            buy_weighted_average=3.95,
            buy_max=4.00,
            buy_min=3.50,
            buy_stddev=0.12,
            buy_median=3.97,
            buy_volume=50000000,
            buy_order_count=1542,
            buy_percentile=3.98,
            sell_weighted_average=4.10,
            sell_max=5.00,
            sell_min=4.05,
            sell_stddev=0.15,
            sell_median=4.12,
            sell_volume=12000000,
            sell_order_count=892,
            sell_percentile=4.08,
        )

        result = cache._aggregate_to_item_price(34, agg, "Tritanium", "fuzzwork")

        assert result.type_id == 34
        assert result.type_name == "Tritanium"
        assert result.buy.max_price == 4.00
        assert result.buy.min_price == 3.50
        assert result.sell.min_price == 4.05
        assert result.sell.max_price == 5.00
        assert result.spread == 0.05  # 4.05 - 4.00
        assert result.spread_percent is not None

    def test_aggregate_with_zero_values(self):
        """Handle aggregates where some values are zero."""
        from aria_esi.mcp.market.cache import MarketCache
        from aria_esi.mcp.market.clients import FuzzworkAggregate

        cache = MarketCache()

        agg = FuzzworkAggregate(
            type_id=34,
            buy_weighted_average=0,
            buy_max=0,
            buy_min=0,
            buy_stddev=0,
            buy_median=0,
            buy_volume=0,
            buy_order_count=0,
            buy_percentile=0,
            sell_weighted_average=4.10,
            sell_max=5.00,
            sell_min=4.05,
            sell_stddev=0.15,
            sell_median=4.12,
            sell_volume=12000000,
            sell_order_count=892,
            sell_percentile=4.08,
        )

        result = cache._aggregate_to_item_price(34, agg, "Tritanium", "fuzzwork")

        # Zero values should be None
        assert result.buy.max_price is None
        assert result.buy.min_price is None
        # Spread can't be calculated without buy max
        assert result.spread is None
