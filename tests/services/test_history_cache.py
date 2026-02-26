"""
Tests for History Cache Service.

Tests cover the HistoryCacheService which provides daily volume data
from ESI market history with caching:
- Single item history fetch with cache hits/misses
- Batch history fetch with parallel ESI calls
- ESI history fetch and statistics calculation
- Cache TTL handling
- Fallback to market proxy
- Error handling and recovery
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aria_esi.services.history_cache import (
    HISTORY_CACHE_TTL_SECONDS,
    HISTORY_DAYS,
    MIN_HISTORY_DAYS,
    HistoryCacheService,
    HistoryResult,
    get_history_cache_service,
    reset_history_cache_service,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def history_service():
    """Create a fresh HistoryCacheService for each test."""
    reset_history_cache_service()
    return HistoryCacheService()


@pytest.fixture
def mock_async_db():
    """Create a mock async market database."""
    db = AsyncMock()
    db.get_history_cache = AsyncMock(return_value=None)
    db.get_history_cache_batch = AsyncMock(return_value={})
    db.save_history_cache = AsyncMock()
    return db


# =============================================================================
# Unit Tests: HistoryResult
# =============================================================================


class TestHistoryResult:
    """Tests for HistoryResult data class."""

    def test_is_from_history_with_history_source(self):
        """Test is_from_history returns True for history source."""
        result = HistoryResult(
            type_id=34,
            region_id=10000002,
            daily_volume=1000,
            daily_isk=50000.0,
            volatility_pct=5.0,
            source="history",
        )
        assert result.is_from_history is True

    def test_is_from_history_with_cache_source(self):
        """Test is_from_history returns True for cache source."""
        result = HistoryResult(
            type_id=34,
            region_id=10000002,
            daily_volume=1000,
            daily_isk=50000.0,
            volatility_pct=5.0,
            source="cache",
        )
        assert result.is_from_history is True

    def test_is_from_history_with_market_proxy_source(self):
        """Test is_from_history returns False for market_proxy source."""
        result = HistoryResult(
            type_id=34,
            region_id=10000002,
            daily_volume=1000,
            daily_isk=None,
            volatility_pct=None,
            source="market_proxy",
        )
        assert result.is_from_history is False

    def test_result_with_none_values(self):
        """Test HistoryResult accepts None for optional fields."""
        result = HistoryResult(
            type_id=34,
            region_id=10000002,
            daily_volume=None,
            daily_isk=None,
            volatility_pct=None,
            source="market_proxy",
        )
        assert result.daily_volume is None
        assert result.daily_isk is None
        assert result.volatility_pct is None


# =============================================================================
# Unit Tests: Cache Behavior
# =============================================================================


class TestHistoryCacheHits:
    """Tests for cache hit scenarios."""

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_data(self, history_service, mock_async_db):
        """Test that cache hit returns cached data without ESI fetch."""
        # Setup cached data
        cached_data = MagicMock()
        cached_data.avg_daily_volume = 5000
        cached_data.avg_daily_isk = 25000.0
        cached_data.volatility_pct = 3.5
        mock_async_db.get_history_cache.return_value = cached_data

        with patch.object(history_service, "_get_database", return_value=mock_async_db):
            result = await history_service.get_daily_volume(34, 10000002)

        assert result.source == "cache"
        assert result.daily_volume == 5000
        assert result.daily_isk == 25000.0
        assert result.volatility_pct == 3.5

    @pytest.mark.asyncio
    async def test_cache_miss_fetches_from_esi(self, history_service, mock_async_db):
        """Test that cache miss triggers ESI fetch."""
        mock_async_db.get_history_cache.return_value = None

        with (
            patch.object(history_service, "_get_database", return_value=mock_async_db),
            patch.object(
                history_service,
                "_fetch_history",
                return_value={"daily_volume": 3000, "daily_isk": 15000.0, "volatility_pct": 2.0},
            ),
        ):
            result = await history_service.get_daily_volume(34, 10000002)

        assert result.source == "history"
        assert result.daily_volume == 3000
        mock_async_db.save_history_cache.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_to_market_proxy_on_fetch_failure(self, history_service, mock_async_db):
        """Test fallback to market proxy when ESI fetch fails."""
        mock_async_db.get_history_cache.return_value = None

        with (
            patch.object(history_service, "_get_database", return_value=mock_async_db),
            patch.object(history_service, "_fetch_history", side_effect=Exception("ESI error")),
        ):
            result = await history_service.get_daily_volume(34, 10000002, available_volume=100)

        assert result.source == "market_proxy"
        assert result.daily_volume == 100
        assert result.daily_isk is None
        assert result.volatility_pct is None

    @pytest.mark.asyncio
    async def test_fallback_without_available_volume(self, history_service, mock_async_db):
        """Test fallback returns None volume when no available_volume provided."""
        mock_async_db.get_history_cache.return_value = None

        with (
            patch.object(history_service, "_get_database", return_value=mock_async_db),
            patch.object(history_service, "_fetch_history", return_value=None),
        ):
            result = await history_service.get_daily_volume(34, 10000002)

        assert result.source == "market_proxy"
        assert result.daily_volume is None


# =============================================================================
# Unit Tests: Batch Operations
# =============================================================================


class TestHistoryBatchOperations:
    """Tests for batch history fetch operations."""

    @pytest.mark.asyncio
    async def test_batch_empty_items(self, history_service, mock_async_db):
        """Test batch with empty items returns empty dict."""
        with patch.object(history_service, "_get_database", return_value=mock_async_db):
            result = await history_service.get_daily_volumes_batch([])

        assert result == {}

    @pytest.mark.asyncio
    async def test_batch_all_cache_hits(self, history_service, mock_async_db):
        """Test batch where all items are in cache."""
        cached_34 = MagicMock()
        cached_34.avg_daily_volume = 5000
        cached_34.avg_daily_isk = 25000.0
        cached_34.volatility_pct = 3.5

        cached_35 = MagicMock()
        cached_35.avg_daily_volume = 3000
        cached_35.avg_daily_isk = 12000.0
        cached_35.volatility_pct = 2.0

        mock_async_db.get_history_cache_batch.return_value = {34: cached_34, 35: cached_35}

        with patch.object(history_service, "_get_database", return_value=mock_async_db):
            result = await history_service.get_daily_volumes_batch(
                [(34, 10000002, 100), (35, 10000002, 50)]
            )

        assert 34 in result
        assert 35 in result
        assert result[34].source == "cache"
        assert result[35].source == "cache"

    @pytest.mark.asyncio
    async def test_batch_mixed_cache_and_fetch(self, history_service, mock_async_db):
        """Test batch with some cache hits and some fetches."""
        cached_34 = MagicMock()
        cached_34.avg_daily_volume = 5000
        cached_34.avg_daily_isk = 25000.0
        cached_34.volatility_pct = 3.5

        # Only type 34 is cached, type 35 needs fetch
        mock_async_db.get_history_cache_batch.return_value = {34: cached_34}

        with (
            patch.object(history_service, "_get_database", return_value=mock_async_db),
            patch.object(
                history_service,
                "_fetch_and_cache_history",
                return_value=HistoryResult(
                    type_id=35,
                    region_id=10000002,
                    daily_volume=2000,
                    daily_isk=8000.0,
                    volatility_pct=1.5,
                    source="history",
                ),
            ),
        ):
            result = await history_service.get_daily_volumes_batch(
                [(34, 10000002, 100), (35, 10000002, 50)]
            )

        assert result[34].source == "cache"
        assert result[34].daily_volume == 5000
        assert result[35].source == "history"
        assert result[35].daily_volume == 2000

    @pytest.mark.asyncio
    async def test_batch_fetch_failure_uses_fallback(self, history_service, mock_async_db):
        """Test batch fetch failure falls back to available_volume."""
        mock_async_db.get_history_cache_batch.return_value = {}

        with (
            patch.object(history_service, "_get_database", return_value=mock_async_db),
            patch.object(
                history_service,
                "_fetch_and_cache_history",
                side_effect=Exception("Network error"),
            ),
        ):
            result = await history_service.get_daily_volumes_batch([(34, 10000002, 100)])

        assert result[34].source == "market_proxy"
        assert result[34].daily_volume == 100

    @pytest.mark.asyncio
    async def test_batch_multiple_regions(self, history_service, mock_async_db):
        """Test batch with items from multiple regions."""
        # Different regions should trigger separate cache lookups
        mock_async_db.get_history_cache_batch.return_value = {}

        async def mock_fetch(type_id, region_id):
            return HistoryResult(
                type_id=type_id,
                region_id=region_id,
                daily_volume=type_id * 100,  # Unique per type
                daily_isk=None,
                volatility_pct=None,
                source="history",
            )

        with (
            patch.object(history_service, "_get_database", return_value=mock_async_db),
            patch.object(history_service, "_fetch_and_cache_history", side_effect=mock_fetch),
        ):
            result = await history_service.get_daily_volumes_batch(
                [
                    (34, 10000002, 100),  # Forge
                    (35, 10000043, 50),  # Domain
                ]
            )

        # Each should have been processed
        assert 34 in result
        assert 35 in result


# =============================================================================
# Unit Tests: ESI History Fetch
# =============================================================================


class TestHistoryFetch:
    """Tests for ESI history fetching and statistics calculation."""

    @pytest.mark.asyncio
    async def test_fetch_history_calculates_statistics(self, history_service):
        """Test that _fetch_history calculates correct statistics."""
        # Mock ESI response with 10 days of history
        mock_history = [
            {"date": "2024-01-01", "volume": 1000, "average": 5.0},
            {"date": "2024-01-02", "volume": 1200, "average": 5.2},
            {"date": "2024-01-03", "volume": 800, "average": 4.8},
            {"date": "2024-01-04", "volume": 1100, "average": 5.1},
            {"date": "2024-01-05", "volume": 900, "average": 4.9},
            {"date": "2024-01-06", "volume": 1050, "average": 5.0},
            {"date": "2024-01-07", "volume": 950, "average": 5.05},
            {"date": "2024-01-08", "volume": 1000, "average": 5.0},
            {"date": "2024-01-09", "volume": 1150, "average": 5.1},
            {"date": "2024-01-10", "volume": 1050, "average": 5.0},
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_history

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        # Create async context manager mock
        async_cm = AsyncMock()
        async_cm.__aenter__.return_value = mock_client
        async_cm.__aexit__.return_value = None

        with patch(
            "aria_esi.mcp.market.clients.create_client",
            return_value=async_cm,
        ):
            result = await history_service._fetch_history(34, 10000002)

        assert result is not None
        assert "daily_volume" in result
        assert result["daily_volume"] > 0
        assert "daily_isk" in result
        assert "volatility_pct" in result

    @pytest.mark.asyncio
    async def test_fetch_history_returns_none_on_error_status(self, history_service):
        """Test that _fetch_history returns None on non-200 status."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        async_cm = AsyncMock()
        async_cm.__aenter__.return_value = mock_client
        async_cm.__aexit__.return_value = None

        with patch(
            "aria_esi.mcp.market.clients.create_client",
            return_value=async_cm,
        ):
            result = await history_service._fetch_history(34, 10000002)

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_history_returns_none_on_empty_history(self, history_service):
        """Test that _fetch_history returns None for empty history."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        async_cm = AsyncMock()
        async_cm.__aenter__.return_value = mock_client
        async_cm.__aexit__.return_value = None

        with patch(
            "aria_esi.mcp.market.clients.create_client",
            return_value=async_cm,
        ):
            result = await history_service._fetch_history(34, 10000002)

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_history_returns_none_on_insufficient_days(self, history_service):
        """Test that _fetch_history returns None if fewer than MIN_HISTORY_DAYS."""
        # Only 5 days of history (less than MIN_HISTORY_DAYS=7)
        mock_history = [
            {"date": f"2024-01-0{i}", "volume": 1000, "average": 5.0} for i in range(1, 6)
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_history

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        async_cm = AsyncMock()
        async_cm.__aenter__.return_value = mock_client
        async_cm.__aexit__.return_value = None

        with patch(
            "aria_esi.mcp.market.clients.create_client",
            return_value=async_cm,
        ):
            result = await history_service._fetch_history(34, 10000002)

        assert result is None


# =============================================================================
# Unit Tests: Volatility Calculation
# =============================================================================


class TestVolatilityCalculation:
    """Tests for price volatility calculation."""

    @pytest.mark.asyncio
    async def test_volatility_with_stable_prices(self, history_service):
        """Test volatility calculation with stable prices."""
        # All prices exactly the same = 0 volatility
        mock_history = [
            {"date": f"2024-01-{i:02d}", "volume": 1000, "average": 10.0} for i in range(1, 15)
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_history

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        async_cm = AsyncMock()
        async_cm.__aenter__.return_value = mock_client
        async_cm.__aexit__.return_value = None

        with patch(
            "aria_esi.mcp.market.clients.create_client",
            return_value=async_cm,
        ):
            result = await history_service._fetch_history(34, 10000002)

        assert result is not None
        assert result["volatility_pct"] == 0.0

    @pytest.mark.asyncio
    async def test_volatility_with_varying_prices(self, history_service):
        """Test volatility calculation with varying prices."""
        # Prices vary significantly
        mock_history = [
            {"date": "2024-01-01", "volume": 1000, "average": 8.0},
            {"date": "2024-01-02", "volume": 1000, "average": 10.0},
            {"date": "2024-01-03", "volume": 1000, "average": 12.0},
            {"date": "2024-01-04", "volume": 1000, "average": 9.0},
            {"date": "2024-01-05", "volume": 1000, "average": 11.0},
            {"date": "2024-01-06", "volume": 1000, "average": 10.0},
            {"date": "2024-01-07", "volume": 1000, "average": 10.0},
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_history

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        async_cm = AsyncMock()
        async_cm.__aenter__.return_value = mock_client
        async_cm.__aexit__.return_value = None

        with patch(
            "aria_esi.mcp.market.clients.create_client",
            return_value=async_cm,
        ):
            result = await history_service._fetch_history(34, 10000002)

        assert result is not None
        assert result["volatility_pct"] is not None
        assert result["volatility_pct"] > 0  # Should have some volatility


# =============================================================================
# Unit Tests: Singleton Management
# =============================================================================


class TestSingletonManagement:
    """Tests for singleton service management."""

    @pytest.mark.asyncio
    async def test_get_history_cache_service_returns_singleton(self):
        """Test that get_history_cache_service returns the same instance."""
        reset_history_cache_service()

        service1 = await get_history_cache_service()
        service2 = await get_history_cache_service()

        assert service1 is service2

    def test_reset_clears_singleton(self):
        """Test that reset_history_cache_service clears the singleton."""
        reset_history_cache_service()
        # After reset, a new call should create a fresh instance
        # (we just verify the reset doesn't raise)
        reset_history_cache_service()  # Should not raise


# =============================================================================
# Unit Tests: Rate Limiting
# =============================================================================


class TestRateLimiting:
    """Tests for rate limiting via semaphore."""

    @pytest.mark.asyncio
    async def test_semaphore_is_created_lazily(self, history_service):
        """Test that semaphore is created on first use."""
        assert history_service._fetch_semaphore is None

        semaphore = await history_service._get_semaphore()

        assert semaphore is not None
        assert history_service._fetch_semaphore is semaphore

    @pytest.mark.asyncio
    async def test_semaphore_is_reused(self, history_service):
        """Test that the same semaphore is returned on subsequent calls."""
        semaphore1 = await history_service._get_semaphore()
        semaphore2 = await history_service._get_semaphore()

        assert semaphore1 is semaphore2


# =============================================================================
# Unit Tests: Database Connection
# =============================================================================


class TestDatabaseConnection:
    """Tests for database connection management."""

    @pytest.mark.asyncio
    async def test_database_is_created_lazily(self, history_service):
        """Test that database connection is created on first use."""
        assert history_service._database is None

        # Mock the get_async_market_database function
        mock_db = AsyncMock()
        with patch(
            "aria_esi.services.history_cache.get_async_market_database",
            return_value=mock_db,
        ):
            db = await history_service._get_database()

        assert db is mock_db
        assert history_service._database is mock_db

    @pytest.mark.asyncio
    async def test_database_is_reused(self, history_service):
        """Test that the same database is returned on subsequent calls."""
        mock_db = AsyncMock()
        with patch(
            "aria_esi.services.history_cache.get_async_market_database",
            return_value=mock_db,
        ):
            db1 = await history_service._get_database()
            db2 = await history_service._get_database()

        assert db1 is db2


# =============================================================================
# Unit Tests: Fetch and Cache History
# =============================================================================


class TestFetchAndCacheHistory:
    """Tests for _fetch_and_cache_history method."""

    @pytest.mark.asyncio
    async def test_fetch_and_cache_saves_to_database(self, history_service, mock_async_db):
        """Test that successful fetch saves data to database."""
        with (
            patch.object(history_service, "_get_database", return_value=mock_async_db),
            patch.object(history_service, "_get_semaphore", return_value=asyncio.Semaphore(10)),
            patch.object(
                history_service,
                "_fetch_history",
                return_value={"daily_volume": 5000, "daily_isk": 25000.0, "volatility_pct": 3.0},
            ),
        ):
            result = await history_service._fetch_and_cache_history(34, 10000002)

        assert result is not None
        assert result.source == "history"
        assert result.daily_volume == 5000
        mock_async_db.save_history_cache.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_and_cache_returns_none_on_fetch_failure(
        self, history_service, mock_async_db
    ):
        """Test that fetch failure returns None."""
        with (
            patch.object(history_service, "_get_database", return_value=mock_async_db),
            patch.object(history_service, "_get_semaphore", return_value=asyncio.Semaphore(10)),
            patch.object(history_service, "_fetch_history", return_value=None),
        ):
            result = await history_service._fetch_and_cache_history(34, 10000002)

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_and_cache_returns_none_on_exception(self, history_service, mock_async_db):
        """Test that exception during fetch returns None."""
        with (
            patch.object(history_service, "_get_database", return_value=mock_async_db),
            patch.object(history_service, "_get_semaphore", return_value=asyncio.Semaphore(10)),
            patch.object(history_service, "_fetch_history", side_effect=Exception("Network error")),
        ):
            result = await history_service._fetch_and_cache_history(34, 10000002)

        assert result is None


# =============================================================================
# Unit Tests: Constants
# =============================================================================


class TestConstants:
    """Tests to verify constants are correctly defined."""

    def test_history_cache_ttl_is_24_hours(self):
        """Test that cache TTL is 24 hours (86400 seconds)."""
        assert HISTORY_CACHE_TTL_SECONDS == 86400

    def test_history_days_is_30(self):
        """Test that history period is 30 days."""
        assert HISTORY_DAYS == 30

    def test_min_history_days_is_7(self):
        """Test that minimum required history is 7 days."""
        assert MIN_HISTORY_DAYS == 7
