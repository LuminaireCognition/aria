"""
Tests for MarketRefreshService.

Covers the pure/near-pure functions that don't require database mocking:
- is_stale() - TTL comparison
- get_freshness() - timestamp classification
- get_stale_regions() - region filtering
- _resolve_regions() - name/ID resolution
- _aggregate_esi_orders() - ESI order aggregation
- get_status() - status reporting
"""

import time

import pytest

from aria_esi.services.market_refresh import (
    FRESH_THRESHOLD,
    RECENT_THRESHOLD,
    TIER_1_TTL_SECONDS,
    MarketRefreshService,
    RegionRefreshStatus,
    reset_refresh_service,
)


# =============================================================================
# RegionRefreshStatus Tests
# =============================================================================


class TestRegionRefreshStatus:
    """Tests for the RegionRefreshStatus dataclass."""

    def test_default_values(self):
        """Status initializes with sensible defaults."""
        status = RegionRefreshStatus(region_id=10000002, region_name="The Forge")

        assert status.region_id == 10000002
        assert status.region_name == "The Forge"
        assert status.last_refresh == 0
        assert status.items_refreshed == 0
        assert status.is_refreshing is False
        assert status.last_error is None

    def test_custom_values(self):
        """Status accepts custom values."""
        now = int(time.time())
        status = RegionRefreshStatus(
            region_id=10000043,
            region_name="Domain",
            last_refresh=now,
            items_refreshed=500,
            is_refreshing=True,
            last_error="Connection timeout",
        )

        assert status.region_id == 10000043
        assert status.region_name == "Domain"
        assert status.last_refresh == now
        assert status.items_refreshed == 500
        assert status.is_refreshing is True
        assert status.last_error == "Connection timeout"


# =============================================================================
# is_stale() Tests
# =============================================================================


class TestIsStale:
    """Tests for the is_stale() method."""

    def test_unknown_region_is_stale(self):
        """Unknown region ID returns True (stale)."""
        service = MarketRefreshService()
        # No regions initialized, so any region is unknown
        assert service.is_stale(99999999) is True

    def test_never_refreshed_is_stale(self):
        """Region with last_refresh=0 is stale."""
        service = MarketRefreshService()
        service._region_status[10000002] = RegionRefreshStatus(
            region_id=10000002,
            region_name="The Forge",
            last_refresh=0,
        )

        assert service.is_stale(10000002) is True

    def test_recently_refreshed_not_stale(self):
        """Region refreshed within TTL is not stale."""
        service = MarketRefreshService()
        now = int(time.time())
        service._region_status[10000002] = RegionRefreshStatus(
            region_id=10000002,
            region_name="The Forge",
            last_refresh=now - 60,  # 1 minute ago
        )

        assert service.is_stale(10000002) is False

    def test_old_refresh_is_stale(self):
        """Region refreshed beyond TTL is stale."""
        service = MarketRefreshService()
        now = int(time.time())
        service._region_status[10000002] = RegionRefreshStatus(
            region_id=10000002,
            region_name="The Forge",
            last_refresh=now - TIER_1_TTL_SECONDS - 60,  # Past TTL
        )

        assert service.is_stale(10000002) is True

    def test_exactly_at_ttl_boundary(self, frozen_time):
        """Region at exact TTL boundary is not stale (edge case)."""
        service = MarketRefreshService()
        now = int(time.time())
        # Exactly at TTL - should NOT be stale (> not >=)
        service._region_status[10000002] = RegionRefreshStatus(
            region_id=10000002,
            region_name="The Forge",
            last_refresh=now - TIER_1_TTL_SECONDS,
        )

        assert service.is_stale(10000002) is False

    def test_custom_ttl(self):
        """Service respects custom TTL setting."""
        service = MarketRefreshService(ttl_seconds=60)  # 1 minute TTL
        now = int(time.time())

        service._region_status[10000002] = RegionRefreshStatus(
            region_id=10000002,
            region_name="The Forge",
            last_refresh=now - 30,  # 30 seconds ago
        )
        assert service.is_stale(10000002) is False

        service._region_status[10000002].last_refresh = now - 90  # 90 seconds ago
        assert service.is_stale(10000002) is True


# =============================================================================
# get_freshness() Tests
# =============================================================================


class TestGetFreshness:
    """Tests for the get_freshness() method."""

    def test_fresh_timestamp(self):
        """Recent timestamp returns 'fresh'."""
        service = MarketRefreshService()
        now = int(time.time())

        assert service.get_freshness(now) == "fresh"
        assert service.get_freshness(now - 60) == "fresh"  # 1 minute ago
        assert service.get_freshness(now - (FRESH_THRESHOLD - 1)) == "fresh"

    def test_recent_timestamp(self):
        """Moderately old timestamp returns 'recent'."""
        service = MarketRefreshService()
        now = int(time.time())

        # Just past fresh threshold
        assert service.get_freshness(now - FRESH_THRESHOLD - 1) == "recent"
        # Middle of recent range
        assert service.get_freshness(now - 900) == "recent"  # 15 minutes
        # Just before stale threshold
        assert service.get_freshness(now - (RECENT_THRESHOLD - 1)) == "recent"

    def test_stale_timestamp(self):
        """Old timestamp returns 'stale'."""
        service = MarketRefreshService()
        now = int(time.time())

        # Just past recent threshold
        assert service.get_freshness(now - RECENT_THRESHOLD - 1) == "stale"
        # Very old
        assert service.get_freshness(now - 3600) == "stale"  # 1 hour
        assert service.get_freshness(now - 86400) == "stale"  # 1 day

    def test_zero_timestamp_is_stale(self):
        """Timestamp of 0 (never refreshed) is stale."""
        service = MarketRefreshService()
        assert service.get_freshness(0) == "stale"

    def test_threshold_boundaries(self):
        """Test exact threshold boundaries."""
        service = MarketRefreshService()
        now = int(time.time())

        # Exactly at fresh threshold - still fresh (< not <=)
        assert service.get_freshness(now - FRESH_THRESHOLD) == "recent"

        # Exactly at recent threshold - still recent
        assert service.get_freshness(now - RECENT_THRESHOLD) == "stale"


# =============================================================================
# get_stale_regions() Tests
# =============================================================================


class TestGetStaleRegions:
    """Tests for the get_stale_regions() method."""

    def test_empty_status_returns_empty(self):
        """No regions tracked returns empty list."""
        service = MarketRefreshService()
        assert service.get_stale_regions() == []

    def test_all_fresh_returns_empty(self):
        """All fresh regions returns empty list."""
        service = MarketRefreshService()
        now = int(time.time())

        service._region_status[10000002] = RegionRefreshStatus(
            region_id=10000002, region_name="The Forge", last_refresh=now
        )
        service._region_status[10000043] = RegionRefreshStatus(
            region_id=10000043, region_name="Domain", last_refresh=now
        )

        assert service.get_stale_regions() == []

    def test_all_stale_returns_all(self):
        """All stale regions returns all region IDs."""
        service = MarketRefreshService()

        service._region_status[10000002] = RegionRefreshStatus(
            region_id=10000002, region_name="The Forge", last_refresh=0
        )
        service._region_status[10000043] = RegionRefreshStatus(
            region_id=10000043, region_name="Domain", last_refresh=0
        )

        stale = service.get_stale_regions()
        assert set(stale) == {10000002, 10000043}

    def test_mixed_freshness(self):
        """Mixed fresh/stale returns only stale regions."""
        service = MarketRefreshService()
        now = int(time.time())

        service._region_status[10000002] = RegionRefreshStatus(
            region_id=10000002, region_name="The Forge", last_refresh=now  # Fresh
        )
        service._region_status[10000043] = RegionRefreshStatus(
            region_id=10000043, region_name="Domain", last_refresh=0  # Stale
        )
        service._region_status[10000032] = RegionRefreshStatus(
            region_id=10000032, region_name="Sinq Laison", last_refresh=now  # Fresh
        )

        stale = service.get_stale_regions()
        assert stale == [10000043]


# =============================================================================
# _resolve_regions() Tests
# =============================================================================


class TestResolveRegions:
    """Tests for the _resolve_regions() method."""

    def test_none_returns_all_trade_hubs(self):
        """None input returns all trade hub region IDs."""
        service = MarketRefreshService()
        result = service._resolve_regions(None)

        # Should have 5 trade hubs
        assert len(result) == 5
        assert 10000002 in result  # The Forge (Jita)
        assert 10000043 in result  # Domain (Amarr)
        assert 10000032 in result  # Sinq Laison (Dodixie)
        assert 10000030 in result  # Heimatar (Rens)
        assert 10000042 in result  # Metropolis (Hek)

    def test_empty_list_returns_all_trade_hubs(self):
        """Empty list returns all trade hub region IDs."""
        service = MarketRefreshService()
        result = service._resolve_regions([])

        assert len(result) == 5

    def test_integer_region_ids_pass_through(self):
        """Integer region IDs are returned as-is."""
        service = MarketRefreshService()
        result = service._resolve_regions([10000002, 10000043])

        assert result == [10000002, 10000043]

    def test_hub_names_resolve(self):
        """Trade hub names resolve to region IDs."""
        service = MarketRefreshService()

        assert service._resolve_regions(["jita"]) == [10000002]
        assert service._resolve_regions(["amarr"]) == [10000043]
        assert service._resolve_regions(["dodixie"]) == [10000032]
        assert service._resolve_regions(["rens"]) == [10000030]
        assert service._resolve_regions(["hek"]) == [10000042]

    def test_hub_names_case_insensitive(self):
        """Hub name resolution is case-insensitive."""
        service = MarketRefreshService()

        assert service._resolve_regions(["JITA"]) == [10000002]
        assert service._resolve_regions(["Jita"]) == [10000002]
        assert service._resolve_regions(["jItA"]) == [10000002]

    def test_region_names_resolve(self):
        """Full region names resolve to region IDs."""
        service = MarketRefreshService()

        assert service._resolve_regions(["the forge"]) == [10000002]
        assert service._resolve_regions(["domain"]) == [10000043]
        assert service._resolve_regions(["sinq laison"]) == [10000032]

    def test_mixed_ids_and_names(self):
        """Mix of IDs and names resolves correctly."""
        service = MarketRefreshService()
        result = service._resolve_regions([10000002, "amarr", "dodixie"])

        assert result == [10000002, 10000043, 10000032]

    def test_unknown_name_ignored(self):
        """Unknown region names are silently ignored."""
        service = MarketRefreshService()
        result = service._resolve_regions(["jita", "nonexistent", "amarr"])

        # Only known regions included
        assert result == [10000002, 10000043]

    def test_all_unknown_returns_empty(self):
        """All unknown names returns empty list."""
        service = MarketRefreshService()
        result = service._resolve_regions(["nonexistent", "fake_region"])

        assert result == []


# =============================================================================
# _aggregate_esi_orders() Tests
# =============================================================================


class TestAggregateEsiOrders:
    """Tests for the _aggregate_esi_orders() method."""

    def test_empty_orders(self):
        """Empty order lists return zeroed aggregate."""
        service = MarketRefreshService()
        result = service._aggregate_esi_orders([], [])

        assert result.buy_max == 0
        assert result.buy_min == 0
        assert result.buy_volume == 0
        assert result.buy_order_count == 0
        assert result.sell_max == 0
        assert result.sell_min == 0
        assert result.sell_volume == 0
        assert result.sell_order_count == 0

    def test_single_buy_order(self):
        """Single buy order aggregates correctly."""
        service = MarketRefreshService()
        buy_orders = [{"price": 100.0, "volume_remain": 1000}]

        result = service._aggregate_esi_orders(buy_orders, [])

        assert result.buy_max == 100.0
        assert result.buy_min == 100.0
        assert result.buy_volume == 1000
        assert result.buy_order_count == 1
        assert result.buy_weighted_average == 100.0
        assert result.buy_median == 100.0

    def test_single_sell_order(self):
        """Single sell order aggregates correctly."""
        service = MarketRefreshService()
        sell_orders = [{"price": 150.0, "volume_remain": 500}]

        result = service._aggregate_esi_orders([], sell_orders)

        assert result.sell_max == 150.0
        assert result.sell_min == 150.0
        assert result.sell_volume == 500
        assert result.sell_order_count == 1
        assert result.sell_weighted_average == 150.0
        assert result.sell_median == 150.0

    def test_multiple_buy_orders(self):
        """Multiple buy orders aggregate min/max/volume correctly."""
        service = MarketRefreshService()
        buy_orders = [
            {"price": 100.0, "volume_remain": 1000},
            {"price": 110.0, "volume_remain": 500},
            {"price": 90.0, "volume_remain": 2000},
        ]

        result = service._aggregate_esi_orders(buy_orders, [])

        assert result.buy_max == 110.0
        assert result.buy_min == 90.0
        assert result.buy_volume == 3500
        assert result.buy_order_count == 3

    def test_multiple_sell_orders(self):
        """Multiple sell orders aggregate min/max/volume correctly."""
        service = MarketRefreshService()
        sell_orders = [
            {"price": 200.0, "volume_remain": 100},
            {"price": 180.0, "volume_remain": 200},
            {"price": 220.0, "volume_remain": 50},
        ]

        result = service._aggregate_esi_orders([], sell_orders)

        assert result.sell_max == 220.0
        assert result.sell_min == 180.0
        assert result.sell_volume == 350
        assert result.sell_order_count == 3

    def test_weighted_average_calculation(self):
        """Weighted average is calculated correctly."""
        service = MarketRefreshService()
        # 100 ISK * 1000 units = 100,000
        # 200 ISK * 3000 units = 600,000
        # Total: 700,000 / 4000 = 175 ISK weighted avg
        buy_orders = [
            {"price": 100.0, "volume_remain": 1000},
            {"price": 200.0, "volume_remain": 3000},
        ]

        result = service._aggregate_esi_orders(buy_orders, [])

        assert result.buy_weighted_average == 175.0

    def test_median_odd_count(self):
        """Median with odd number of orders."""
        service = MarketRefreshService()
        sell_orders = [
            {"price": 100.0, "volume_remain": 1},
            {"price": 200.0, "volume_remain": 1},
            {"price": 150.0, "volume_remain": 1},
        ]

        result = service._aggregate_esi_orders([], sell_orders)

        # Sorted: 100, 150, 200 -> median is 150
        assert result.sell_median == 150.0

    def test_median_even_count(self):
        """Median with even number of orders."""
        service = MarketRefreshService()
        sell_orders = [
            {"price": 100.0, "volume_remain": 1},
            {"price": 200.0, "volume_remain": 1},
            {"price": 150.0, "volume_remain": 1},
            {"price": 180.0, "volume_remain": 1},
        ]

        result = service._aggregate_esi_orders([], sell_orders)

        # Sorted: 100, 150, 180, 200 -> median is (150 + 180) / 2 = 165
        assert result.sell_median == 165.0

    def test_both_buy_and_sell(self):
        """Both buy and sell orders aggregate independently."""
        service = MarketRefreshService()
        buy_orders = [
            {"price": 100.0, "volume_remain": 1000},
            {"price": 95.0, "volume_remain": 500},
        ]
        sell_orders = [
            {"price": 110.0, "volume_remain": 800},
            {"price": 115.0, "volume_remain": 200},
        ]

        result = service._aggregate_esi_orders(buy_orders, sell_orders)

        # Buy side
        assert result.buy_max == 100.0
        assert result.buy_min == 95.0
        assert result.buy_volume == 1500

        # Sell side
        assert result.sell_max == 115.0
        assert result.sell_min == 110.0
        assert result.sell_volume == 1000


# =============================================================================
# get_status() Tests
# =============================================================================


class TestGetStatus:
    """Tests for the get_status() method."""

    def test_empty_status(self):
        """Empty region status returns empty dict."""
        service = MarketRefreshService()
        assert service.get_status() == {}

    def test_single_region_status(self):
        """Single region returns correct status structure."""
        service = MarketRefreshService()
        now = int(time.time())

        service._region_status[10000002] = RegionRefreshStatus(
            region_id=10000002,
            region_name="The Forge",
            last_refresh=now,
            items_refreshed=500,
        )

        status = service.get_status()

        assert "The Forge" in status
        assert status["The Forge"]["region_id"] == 10000002
        assert status["The Forge"]["last_refresh"] == now
        assert status["The Forge"]["items_refreshed"] == 500
        assert status["The Forge"]["is_stale"] is False
        assert status["The Forge"]["freshness"] == "fresh"
        assert status["The Forge"]["is_refreshing"] is False
        assert status["The Forge"]["last_error"] is None

    def test_stale_region_status(self):
        """Stale region shows correct status."""
        service = MarketRefreshService()

        service._region_status[10000043] = RegionRefreshStatus(
            region_id=10000043,
            region_name="Domain",
            last_refresh=0,  # Never refreshed
        )

        status = service.get_status()

        assert status["Domain"]["is_stale"] is True
        assert status["Domain"]["freshness"] == "stale"

    def test_refreshing_region_status(self):
        """Currently refreshing region shows correct status."""
        service = MarketRefreshService()
        now = int(time.time())

        service._region_status[10000032] = RegionRefreshStatus(
            region_id=10000032,
            region_name="Sinq Laison",
            last_refresh=now,
            is_refreshing=True,
        )

        status = service.get_status()

        assert status["Sinq Laison"]["is_refreshing"] is True

    def test_error_region_status(self):
        """Region with error shows error in status."""
        service = MarketRefreshService()
        now = int(time.time())

        service._region_status[10000030] = RegionRefreshStatus(
            region_id=10000030,
            region_name="Heimatar",
            last_refresh=now - 600,  # 10 minutes ago
            last_error="Fuzzwork timeout",
        )

        status = service.get_status()

        assert status["Heimatar"]["last_error"] == "Fuzzwork timeout"
        assert status["Heimatar"]["freshness"] == "recent"

    def test_multiple_regions_status(self):
        """Multiple regions return all statuses."""
        service = MarketRefreshService()
        now = int(time.time())

        service._region_status[10000002] = RegionRefreshStatus(
            region_id=10000002, region_name="The Forge", last_refresh=now
        )
        service._region_status[10000043] = RegionRefreshStatus(
            region_id=10000043, region_name="Domain", last_refresh=0
        )

        status = service.get_status()

        assert len(status) == 2
        assert "The Forge" in status
        assert "Domain" in status


# =============================================================================
# Singleton Tests
# =============================================================================


class TestSingleton:
    """Tests for singleton management functions."""

    def test_reset_clears_singleton(self):
        """reset_refresh_service clears the global singleton."""
        from aria_esi.services.market_refresh import (
            _refresh_service,
            get_refresh_service,
            reset_refresh_service,
        )

        # Note: Can't directly test get_refresh_service() without async
        # but we can verify reset works
        reset_refresh_service()

        # Import again to check module-level variable
        from aria_esi.services import market_refresh

        assert market_refresh._refresh_service is None
