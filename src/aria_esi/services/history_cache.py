"""
History Cache Service for Arbitrage Hauling Score.

Provides daily volume data from ESI market history with caching.
Used by the hauling score algorithm to estimate liquidity constraints.

V2 Implementation:
- 24-hour cache TTL (history updates daily after downtime)
- Lazy refresh on cache miss
- Batch operations for arbitrage scans
- Falls back to available_volume as market proxy when history unavailable
"""

from __future__ import annotations

import asyncio
import statistics
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from aria_esi.core.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

from aria_esi.mcp.market.database_async import AsyncMarketDatabase, get_async_market_database

logger = get_logger("aria_market.history_cache")

# =============================================================================
# Constants
# =============================================================================

# Cache TTL: 24 hours (market history updates once daily after downtime)
HISTORY_CACHE_TTL_SECONDS = 86400

# History calculation parameters
HISTORY_DAYS = 30  # Days of history to average
MIN_HISTORY_DAYS = 7  # Minimum days required for valid average

# Rate limiting for ESI fetches
MAX_CONCURRENT_FETCHES = 10
FETCH_TIMEOUT_SECONDS = 30


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class HistoryResult:
    """Result of a history lookup with source tracking."""

    type_id: int
    region_id: int
    daily_volume: int | None
    daily_isk: float | None
    volatility_pct: float | None
    source: str  # "history" | "market_proxy" | "cache"

    @property
    def is_from_history(self) -> bool:
        """True if data came from actual market history."""
        return self.source in ("history", "cache")


# =============================================================================
# History Cache Service
# =============================================================================


@dataclass
class HistoryCacheService:
    """
    Service for fetching and caching market history data.

    Provides daily volume estimates for the hauling score algorithm.
    Uses ESI market_history endpoint with 24-hour caching.

    When history is unavailable, falls back to available_volume as proxy.
    """

    ttl_seconds: int = HISTORY_CACHE_TTL_SECONDS
    _database: AsyncMarketDatabase | None = field(default=None, repr=False)
    _fetch_semaphore: asyncio.Semaphore | None = field(default=None, repr=False)

    async def _get_database(self) -> AsyncMarketDatabase:
        """Get database connection."""
        if self._database is None:
            self._database = await get_async_market_database()
        return self._database

    async def _get_semaphore(self) -> asyncio.Semaphore:
        """Get fetch semaphore for rate limiting."""
        if self._fetch_semaphore is None:
            self._fetch_semaphore = asyncio.Semaphore(MAX_CONCURRENT_FETCHES)
        return self._fetch_semaphore

    async def get_daily_volume(
        self,
        type_id: int,
        region_id: int,
        available_volume: int | None = None,
    ) -> HistoryResult:
        """
        Get daily volume for an item, using cache or fetching from ESI.

        Args:
            type_id: Item type ID
            region_id: Region ID
            available_volume: Fallback if history unavailable (market proxy)

        Returns:
            HistoryResult with daily_volume and source indicator
        """
        db = await self._get_database()

        # Check cache first
        cached = await db.get_history_cache(type_id, region_id, self.ttl_seconds)
        if cached:
            return HistoryResult(
                type_id=type_id,
                region_id=region_id,
                daily_volume=cached.avg_daily_volume,
                daily_isk=cached.avg_daily_isk,
                volatility_pct=cached.volatility_pct,
                source="cache",
            )

        # Try to fetch from ESI
        try:
            history_data = await self._fetch_history(type_id, region_id)
            if history_data:
                # Save to cache
                await db.save_history_cache(
                    type_id=type_id,
                    region_id=region_id,
                    avg_daily_volume=history_data["daily_volume"],
                    avg_daily_isk=history_data.get("daily_isk"),
                    volatility_pct=history_data.get("volatility_pct"),
                )
                return HistoryResult(
                    type_id=type_id,
                    region_id=region_id,
                    daily_volume=history_data["daily_volume"],
                    daily_isk=history_data.get("daily_isk"),
                    volatility_pct=history_data.get("volatility_pct"),
                    source="history",
                )
        except Exception as e:
            logger.warning("Failed to fetch history for type %d: %s", type_id, e)

        # Fall back to market proxy
        return HistoryResult(
            type_id=type_id,
            region_id=region_id,
            daily_volume=available_volume,
            daily_isk=None,
            volatility_pct=None,
            source="market_proxy",
        )

    async def get_daily_volumes_batch(
        self,
        items: Sequence[tuple[int, int, int | None]],
    ) -> dict[int, HistoryResult]:
        """
        Get daily volumes for multiple items.

        Args:
            items: List of (type_id, region_id, available_volume_fallback)

        Returns:
            Dict mapping type_id to HistoryResult
        """
        if not items:
            return {}

        db = await self._get_database()

        # Extract unique type_ids per region
        type_ids_by_region: dict[int, list[int]] = {}
        fallbacks: dict[int, int | None] = {}
        for type_id, region_id, fallback in items:
            if region_id not in type_ids_by_region:
                type_ids_by_region[region_id] = []
            type_ids_by_region[region_id].append(type_id)
            fallbacks[type_id] = fallback

        results: dict[int, HistoryResult] = {}
        missing: list[tuple[int, int]] = []  # (type_id, region_id)

        # Check cache for each region
        for region_id, type_ids in type_ids_by_region.items():
            cached = await db.get_history_cache_batch(type_ids, region_id, self.ttl_seconds)
            for type_id in type_ids:
                if type_id in cached:
                    c = cached[type_id]
                    results[type_id] = HistoryResult(
                        type_id=type_id,
                        region_id=region_id,
                        daily_volume=c.avg_daily_volume,
                        daily_isk=c.avg_daily_isk,
                        volatility_pct=c.volatility_pct,
                        source="cache",
                    )
                else:
                    missing.append((type_id, region_id))

        # Fetch missing from ESI in parallel
        if missing:
            fetch_tasks = [
                self._fetch_and_cache_history(type_id, region_id) for type_id, region_id in missing
            ]
            fetched = await asyncio.gather(*fetch_tasks, return_exceptions=True)

            for (type_id, region_id), fetch_result in zip(missing, fetched, strict=True):
                if isinstance(fetch_result, BaseException):
                    # Use fallback
                    results[type_id] = HistoryResult(
                        type_id=type_id,
                        region_id=region_id,
                        daily_volume=fallbacks.get(type_id),
                        daily_isk=None,
                        volatility_pct=None,
                        source="market_proxy",
                    )
                elif fetch_result:
                    results[type_id] = fetch_result
                else:
                    # Fetch returned None, use fallback
                    results[type_id] = HistoryResult(
                        type_id=type_id,
                        region_id=region_id,
                        daily_volume=fallbacks.get(type_id),
                        daily_isk=None,
                        volatility_pct=None,
                        source="market_proxy",
                    )

        return results

    async def _fetch_and_cache_history(
        self,
        type_id: int,
        region_id: int,
    ) -> HistoryResult | None:
        """
        Fetch history from ESI and cache it.

        Uses semaphore for rate limiting.
        """
        semaphore = await self._get_semaphore()
        async with semaphore:
            try:
                history_data = await self._fetch_history(type_id, region_id)
                if history_data:
                    db = await self._get_database()
                    await db.save_history_cache(
                        type_id=type_id,
                        region_id=region_id,
                        avg_daily_volume=history_data["daily_volume"],
                        avg_daily_isk=history_data.get("daily_isk"),
                        volatility_pct=history_data.get("volatility_pct"),
                    )
                    return HistoryResult(
                        type_id=type_id,
                        region_id=region_id,
                        daily_volume=history_data["daily_volume"],
                        daily_isk=history_data.get("daily_isk"),
                        volatility_pct=history_data.get("volatility_pct"),
                        source="history",
                    )
            except Exception as e:
                logger.debug("Failed to fetch history for type %d: %s", type_id, e)
        return None

    async def _fetch_history(
        self,
        type_id: int,
        region_id: int,
    ) -> dict | None:
        """
        Fetch market history from ESI and calculate daily averages.

        Returns:
            Dict with daily_volume, daily_isk, volatility_pct or None
        """
        try:
            from aria_esi.mcp.market.clients import create_client

            async with create_client() as client:
                # ESI market history endpoint
                url = f"https://esi.evetech.net/latest/markets/{region_id}/history/"
                params = {"type_id": type_id}

                response = await client.get(url, params=params, timeout=FETCH_TIMEOUT_SECONDS)
                if response.status_code != 200:
                    return None

                history = response.json()
                if not history:
                    return None

                # Get last N days
                recent = history[-HISTORY_DAYS:] if len(history) > HISTORY_DAYS else history
                if len(recent) < MIN_HISTORY_DAYS:
                    return None

                # Calculate averages
                volumes = [day.get("volume", 0) for day in recent]
                avg_daily_volume = int(statistics.mean(volumes)) if volumes else 0

                # Calculate daily ISK volume (volume * average price)
                isk_volumes = [day.get("volume", 0) * day.get("average", 0) for day in recent]
                avg_daily_isk = statistics.mean(isk_volumes) if isk_volumes else None

                # Calculate price volatility (std dev / mean)
                prices = [day.get("average", 0) for day in recent if day.get("average", 0) > 0]
                volatility_pct = None
                if len(prices) >= MIN_HISTORY_DAYS:
                    try:
                        mean_price = statistics.mean(prices)
                        if mean_price > 0:
                            std_dev = statistics.stdev(prices)
                            volatility_pct = (std_dev / mean_price) * 100
                    except statistics.StatisticsError:
                        pass

                return {
                    "daily_volume": avg_daily_volume,
                    "daily_isk": avg_daily_isk,
                    "volatility_pct": volatility_pct,
                }

        except ImportError:
            logger.warning("httpx client not available for history fetch")
            return None
        except Exception as e:
            logger.debug("History fetch error: %s", e)
            return None


# =============================================================================
# Singleton Management
# =============================================================================

_history_cache_service: HistoryCacheService | None = None


async def get_history_cache_service() -> HistoryCacheService:
    """Get or create the history cache service singleton."""
    global _history_cache_service
    if _history_cache_service is None:
        _history_cache_service = HistoryCacheService()
    return _history_cache_service


def reset_history_cache_service() -> None:
    """Reset the history cache service singleton (for testing)."""
    global _history_cache_service
    _history_cache_service = None
