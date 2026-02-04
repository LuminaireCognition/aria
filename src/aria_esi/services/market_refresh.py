"""
Market Refresh Service for Arbitrage.

Handles request-triggered refresh of market data for arbitrage detection.
Uses TTL-based staleness checks with Fuzzwork primary, ESI fallback.

V1 Implementation:
- 5 trade hubs only (Jita, Amarr, Dodixie, Rens, Hek)
- Pre-seeded with ~500 items from Jita
- Request-triggered refresh (no daemon)
- 5-minute TTL for tier 1 (trade hubs)
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from aria_esi.core.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

    from aria_esi.mcp.market.clients import FuzzworkAggregate

from aria_esi.mcp.market.clients import create_client
from aria_esi.mcp.market.database_async import AsyncMarketDatabase, get_async_market_database
from aria_esi.models.market import TRADE_HUBS, FreshnessLevel, RefreshResult

logger = get_logger("aria_market.refresh")

# =============================================================================
# Constants
# =============================================================================

# TTL settings per tier (seconds)
TIER_1_TTL_SECONDS = 300  # 5 minutes for trade hubs

# Freshness thresholds (seconds)
FRESH_THRESHOLD = 300  # 5 minutes
RECENT_THRESHOLD = 1800  # 30 minutes

# Rate limiting
MAX_CONCURRENT_REGIONS = 3  # Don't hammer Fuzzwork too hard
REFRESH_TIMEOUT_SECONDS = 60  # Max time per region refresh

# ESI fallback settings
ESI_FALLBACK_ITEM_LIMIT = 100  # Limit items when falling back to ESI (slower)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class RegionRefreshStatus:
    """Status tracking for a region's refresh state."""

    region_id: int
    region_name: str
    last_refresh: int = 0  # Unix timestamp
    items_refreshed: int = 0
    is_refreshing: bool = False
    last_error: str | None = None


# =============================================================================
# Market Refresh Service
# =============================================================================


@dataclass
class MarketRefreshService:
    """
    Service for refreshing market data across trade hubs.

    Provides TTL-based staleness checks and request-triggered refresh.
    Uses Fuzzwork as primary data source with ESI fallback.

    Thread-safety: Uses asyncio.Lock per region to prevent concurrent
    refresh operations on the same region.
    """

    ttl_seconds: int = TIER_1_TTL_SECONDS
    _region_status: dict[int, RegionRefreshStatus] = field(default_factory=dict)
    _region_locks: dict[int, asyncio.Lock] = field(default_factory=dict)
    _database: AsyncMarketDatabase | None = field(default=None, repr=False)
    _initialized: bool = field(default=False, repr=False)

    async def _ensure_initialized(self) -> None:
        """Initialize database connection and region status."""
        if self._initialized:
            return

        self._database = await get_async_market_database()

        # Initialize status for all trade hubs
        for _hub_name, hub_config in TRADE_HUBS.items():
            region_id = hub_config["region_id"]
            self._region_status[region_id] = RegionRefreshStatus(
                region_id=region_id,
                region_name=hub_config["region_name"],
            )
            self._region_locks[region_id] = asyncio.Lock()

        # Load last refresh times from database
        await self._load_refresh_status()
        self._initialized = True

    async def _load_refresh_status(self) -> None:
        """Load refresh status from database."""
        if not self._database:
            return

        conn = await self._database._get_connection()

        # Check if tracking table exists
        async with conn.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='region_refresh_tracking'
            """
        ) as cursor:
            if not await cursor.fetchone():
                # Table doesn't exist yet, will be created on first refresh
                return

        async with conn.execute(
            "SELECT region_id, last_refresh, items_refreshed FROM region_refresh_tracking"
        ) as cursor:
            rows = await cursor.fetchall()

        for row in rows:
            region_id = row["region_id"]
            if region_id in self._region_status:
                self._region_status[region_id].last_refresh = row["last_refresh"]
                self._region_status[region_id].items_refreshed = row["items_refreshed"]

    async def _save_refresh_status(
        self, region_id: int, items_refreshed: int, duration_ms: int
    ) -> None:
        """Save refresh status to database."""
        if not self._database:
            return

        conn = await self._database._get_connection()

        # Ensure table exists
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS region_refresh_tracking (
                region_id INTEGER PRIMARY KEY,
                region_name TEXT NOT NULL,
                last_refresh INTEGER NOT NULL,
                items_refreshed INTEGER DEFAULT 0,
                refresh_duration_ms INTEGER DEFAULT 0
            )
            """
        )

        status = self._region_status.get(region_id)
        if status:
            await conn.execute(
                """
                INSERT OR REPLACE INTO region_refresh_tracking
                (region_id, region_name, last_refresh, items_refreshed, refresh_duration_ms)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    region_id,
                    status.region_name,
                    status.last_refresh,
                    items_refreshed,
                    duration_ms,
                ),
            )
            await conn.commit()

    def is_stale(self, region_id: int) -> bool:
        """Check if region data is stale (needs refresh)."""
        status = self._region_status.get(region_id)
        if not status or status.last_refresh == 0:
            return True
        return (time.time() - status.last_refresh) > self.ttl_seconds

    def get_freshness(self, timestamp: int) -> FreshnessLevel:
        """Classify freshness based on timestamp."""
        age = time.time() - timestamp
        if age < FRESH_THRESHOLD:
            return "fresh"
        elif age < RECENT_THRESHOLD:
            return "recent"
        return "stale"

    def get_stale_regions(self) -> list[int]:
        """Get list of region IDs that need refresh."""
        return [rid for rid in self._region_status if self.is_stale(rid)]

    async def ensure_fresh_data(
        self,
        regions: Sequence[int | str] | None = None,
        force_refresh: bool = False,
    ) -> RefreshResult:
        """
        Ensure market data is fresh for specified regions.

        If data is stale or force_refresh is True, triggers a refresh.
        Otherwise returns immediately.

        Args:
            regions: Region IDs or names to check (default: all trade hubs)
            force_refresh: Force refresh regardless of TTL

        Returns:
            RefreshResult with refresh metadata
        """
        await self._ensure_initialized()

        start_time = time.time()
        was_stale = False
        regions_refreshed: list[str] = []
        items_updated = 0
        errors: list[str] = []

        # Resolve region identifiers to IDs
        region_ids = self._resolve_regions(regions)

        # Check which regions need refresh
        regions_to_refresh = []
        for region_id in region_ids:
            if force_refresh or self.is_stale(region_id):
                regions_to_refresh.append(region_id)
                was_stale = True

        if not regions_to_refresh:
            # All data is fresh
            return RefreshResult(
                regions_refreshed=[self._region_status[rid].region_name for rid in region_ids],
                items_updated=0,
                duration_ms=0,
                errors=[],
                was_stale=False,
            )

        # Refresh stale regions (with concurrency limit)
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_REGIONS)

        async def refresh_with_limit(region_id: int) -> tuple[int, int, str | None]:
            async with semaphore:
                return await self._refresh_region(region_id)

        tasks = [refresh_with_limit(rid) for rid in regions_to_refresh]
        refresh_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for i, res in enumerate(refresh_results):
            region_id = regions_to_refresh[i]
            status = self._region_status.get(region_id)

            if isinstance(res, Exception):
                error_msg = f"{status.region_name if status else region_id}: {res}"
                errors.append(error_msg)
                logger.error("Refresh failed for region %d: %s", region_id, res)
            else:
                region_items, duration_ms, error = res
                if error:
                    errors.append(f"{status.region_name if status else region_id}: {error}")
                else:
                    items_updated += region_items
                    if status:
                        regions_refreshed.append(status.region_name)

        return RefreshResult(
            regions_refreshed=regions_refreshed,
            items_updated=items_updated,
            duration_ms=int((time.time() - start_time) * 1000),
            errors=errors,
            was_stale=was_stale,
        )

    async def _refresh_region(self, region_id: int) -> tuple[int, int, str | None]:
        """
        Refresh market data for a single region.

        Args:
            region_id: Region to refresh

        Returns:
            Tuple of (items_updated, duration_ms, error_message)
        """
        lock = self._region_locks.get(region_id)
        if not lock:
            return 0, 0, f"Unknown region: {region_id}"

        async with lock:
            status = self._region_status.get(region_id)
            if status:
                status.is_refreshing = True

            start_time = time.time()
            try:
                items_updated = await self._fetch_and_store_prices(region_id)
                duration_ms = int((time.time() - start_time) * 1000)

                # Update status
                if status:
                    status.last_refresh = int(time.time())
                    status.items_refreshed = items_updated
                    status.is_refreshing = False
                    status.last_error = None

                # Persist to database
                await self._save_refresh_status(region_id, items_updated, duration_ms)

                logger.info(
                    "Refreshed %d items for region %d in %dms",
                    items_updated,
                    region_id,
                    duration_ms,
                )
                return items_updated, duration_ms, None

            except Exception as e:
                if status:
                    status.is_refreshing = False
                    status.last_error = str(e)
                logger.error("Failed to refresh region %d: %s", region_id, e)
                return 0, 0, str(e)

    async def _fetch_and_store_prices(self, region_id: int) -> int:
        """
        Fetch prices from Fuzzwork and store in database.

        Args:
            region_id: Region to fetch

        Returns:
            Number of items updated
        """
        if not self._database:
            raise RuntimeError("Database not initialized")

        # Get the trade hub name for this region
        hub_name = None
        for name, config in TRADE_HUBS.items():
            if config["region_id"] == region_id:
                hub_name = name
                break

        if not hub_name:
            raise ValueError(f"Region {region_id} is not a trade hub")

        # Create Fuzzwork client for this region
        client = create_client(region=hub_name, station_only=True)

        # Get list of type IDs to refresh
        # Use type_ids from aggregates table (pre-seeded market items from Fuzzwork CSV)
        # Falls back to types with market_group_id if aggregates is empty
        conn = await self._database._get_connection()
        async with conn.execute(
            """
            SELECT DISTINCT type_id FROM aggregates
            UNION
            SELECT type_id FROM types WHERE market_group_id IS NOT NULL
            LIMIT 1000
            """
        ) as cursor:
            rows = await cursor.fetchall()

        type_ids = [row["type_id"] for row in rows]
        if not type_ids:
            logger.warning("No types in database to refresh")
            return 0

        # Fetch from Fuzzwork (with timeout), fall back to ESI if unavailable
        aggregates = None
        fuzzwork_error = None

        try:
            aggregates = await asyncio.wait_for(
                client.get_aggregates(type_ids),
                timeout=REFRESH_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            fuzzwork_error = f"Fuzzwork request timed out after {REFRESH_TIMEOUT_SECONDS}s"
            logger.warning(fuzzwork_error)
        except Exception as e:
            fuzzwork_error = f"Fuzzwork request failed: {e}"
            logger.warning(fuzzwork_error)

        # ESI fallback if Fuzzwork failed or returned empty
        if not aggregates:
            logger.info("Attempting ESI fallback for region %d", region_id)
            try:
                aggregates = await self._fetch_from_esi_fallback(
                    type_ids[:ESI_FALLBACK_ITEM_LIMIT],  # Limit items for ESI
                    region_id,
                )
                if aggregates:
                    logger.info(
                        "ESI fallback successful: %d items for region %d",
                        len(aggregates),
                        region_id,
                    )
            except Exception as esi_error:
                logger.warning("ESI fallback also failed: %s", esi_error)
                # Re-raise original Fuzzwork error if both failed
                if fuzzwork_error:
                    raise RuntimeError(fuzzwork_error) from esi_error
                raise

        if not aggregates:
            logger.warning("No aggregates returned for region %d", region_id)
            return 0

        # Store in region_prices table
        now = int(time.time())

        # Ensure region_prices table exists
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS region_prices (
                type_id INTEGER NOT NULL,
                region_id INTEGER NOT NULL,
                buy_max REAL,
                buy_volume INTEGER DEFAULT 0,
                sell_min REAL,
                sell_volume INTEGER DEFAULT 0,
                spread_pct REAL,
                updated_at INTEGER NOT NULL,
                PRIMARY KEY (type_id, region_id)
            )
            """
        )

        # Batch insert/update
        batch = []
        for type_id, agg in aggregates.items():
            # Calculate spread
            spread_pct = None
            if agg.sell_min and agg.sell_min > 0 and agg.buy_max:
                spread_pct = round(((agg.sell_min - agg.buy_max) / agg.sell_min) * 100, 2)

            batch.append(
                (
                    type_id,
                    region_id,
                    agg.buy_max if agg.buy_max > 0 else None,
                    agg.buy_volume,
                    agg.sell_min if agg.sell_min > 0 else None,
                    agg.sell_volume,
                    spread_pct,
                    now,
                )
            )

        if batch:
            await conn.executemany(
                """
                INSERT OR REPLACE INTO region_prices
                (type_id, region_id, buy_max, buy_volume, sell_min, sell_volume, spread_pct, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                batch,
            )
            await conn.commit()

        return len(batch)

    async def _fetch_from_esi_fallback(
        self,
        type_ids: list[int],
        region_id: int,
    ) -> dict[int, FuzzworkAggregate]:
        """
        Fetch prices directly from ESI as Fuzzwork fallback.

        Uses ESI /markets/{region}/orders/ endpoint and aggregates locally.
        Slower than Fuzzwork (1 request per item vs 100 items per request)
        but provides resilience when Fuzzwork is down.

        Args:
            type_ids: Type IDs to fetch (should be limited)
            region_id: Region to fetch

        Returns:
            Dict mapping type_id to FuzzworkAggregate-compatible data
        """

        try:
            from aria_esi.mcp.esi_client import get_async_esi_client

            client = await get_async_esi_client()
        except Exception as e:
            logger.warning("ESI client not available for fallback: %s", e)
            return {}

        results: dict[int, FuzzworkAggregate] = {}

        for type_id in type_ids:
            try:
                # Fetch buy orders
                buy_orders: list[dict] = []
                try:
                    data = await client.get(
                        f"/markets/{region_id}/orders/",
                        params={"type_id": str(type_id), "order_type": "buy"},
                    )
                    if isinstance(data, list):
                        buy_orders = data
                except Exception as e:
                    logger.debug("ESI buy orders failed for %d: %s", type_id, e)

                # Fetch sell orders
                sell_orders: list[dict] = []
                try:
                    data = await client.get(
                        f"/markets/{region_id}/orders/",
                        params={"type_id": str(type_id), "order_type": "sell"},
                    )
                    if isinstance(data, list):
                        sell_orders = data
                except Exception as e:
                    logger.debug("ESI sell orders failed for %d: %s", type_id, e)

                # Aggregate to Fuzzwork-compatible format
                results[type_id] = self._aggregate_esi_orders(buy_orders, sell_orders)

            except Exception as e:
                logger.debug("ESI fallback failed for type %d: %s", type_id, e)

        return results

    def _aggregate_esi_orders(
        self,
        buy_orders: list[dict],
        sell_orders: list[dict],
    ) -> FuzzworkAggregate:
        """
        Aggregate ESI orders into Fuzzwork-compatible format.

        Args:
            buy_orders: Raw ESI buy orders
            sell_orders: Raw ESI sell orders

        Returns:
            FuzzworkAggregate with aggregated data
        """
        from aria_esi.mcp.market.clients import FuzzworkAggregate

        def aggregate_side(orders: list[dict], is_buy: bool) -> dict:
            if not orders:
                return {
                    "max": 0,
                    "min": 0,
                    "volume": 0,
                    "order_count": 0,
                    "weighted_avg": 0,
                    "median": 0,
                    "percentile": 0,
                    "stddev": 0,
                }

            prices = [o["price"] for o in orders]
            volumes = [o["volume_remain"] for o in orders]
            total_volume = sum(volumes)

            # Weighted average
            if total_volume > 0:
                weighted_avg = sum(p * v for p, v in zip(prices, volumes)) / total_volume
            else:
                weighted_avg = sum(prices) / len(prices) if prices else 0

            # Median
            sorted_prices = sorted(prices)
            mid = len(sorted_prices) // 2
            if len(sorted_prices) % 2 == 0 and len(sorted_prices) > 1:
                median = (sorted_prices[mid - 1] + sorted_prices[mid]) / 2
            else:
                median = sorted_prices[mid] if sorted_prices else 0

            # Percentile (5th for buys = high end, for sells = low end)
            pct_idx = max(0, int(len(sorted_prices) * 0.05))
            if is_buy:
                sorted_for_pct = sorted(prices, reverse=True)
            else:
                sorted_for_pct = sorted(prices)
            percentile = sorted_for_pct[pct_idx] if sorted_for_pct else 0

            return {
                "max": max(prices) if prices else 0,
                "min": min(prices) if prices else 0,
                "volume": total_volume,
                "order_count": len(orders),
                "weighted_avg": weighted_avg,
                "median": median,
                "percentile": percentile,
                "stddev": 0,  # Skip stddev for performance
            }

        buy_agg = aggregate_side(buy_orders, is_buy=True)
        sell_agg = aggregate_side(sell_orders, is_buy=False)

        return FuzzworkAggregate(
            type_id=0,  # Will be set by caller
            buy_weighted_average=buy_agg["weighted_avg"],
            buy_max=buy_agg["max"],
            buy_min=buy_agg["min"],
            buy_stddev=buy_agg["stddev"],
            buy_median=buy_agg["median"],
            buy_volume=buy_agg["volume"],
            buy_order_count=buy_agg["order_count"],
            buy_percentile=buy_agg["percentile"],
            sell_weighted_average=sell_agg["weighted_avg"],
            sell_max=sell_agg["max"],
            sell_min=sell_agg["min"],
            sell_stddev=sell_agg["stddev"],
            sell_median=sell_agg["median"],
            sell_volume=sell_agg["volume"],
            sell_order_count=sell_agg["order_count"],
            sell_percentile=sell_agg["percentile"],
        )

    def _resolve_regions(self, regions: Sequence[int | str] | None) -> list[int]:
        """Resolve region identifiers to region IDs."""
        if not regions:
            # Default to all trade hubs
            return [config["region_id"] for config in TRADE_HUBS.values()]

        result = []
        for region in regions:
            if isinstance(region, int):
                result.append(region)
            else:
                # Try to resolve name
                region_lower = region.lower()
                if region_lower in TRADE_HUBS:
                    result.append(TRADE_HUBS[region_lower]["region_id"])
                else:
                    # Check region names
                    for config in TRADE_HUBS.values():
                        if config["region_name"].lower() == region_lower:
                            result.append(config["region_id"])
                            break

        return result

    def get_status(self) -> dict:
        """Get current refresh status for all regions."""
        return {
            status.region_name: {
                "region_id": status.region_id,
                "last_refresh": status.last_refresh,
                "items_refreshed": status.items_refreshed,
                "is_stale": self.is_stale(status.region_id),
                "freshness": self.get_freshness(status.last_refresh)
                if status.last_refresh > 0
                else "stale",
                "is_refreshing": status.is_refreshing,
                "last_error": status.last_error,
            }
            for status in self._region_status.values()
        }


# =============================================================================
# Module-level Singleton
# =============================================================================

_refresh_service: MarketRefreshService | None = None


async def get_refresh_service() -> MarketRefreshService:
    """Get or create the market refresh service singleton."""
    global _refresh_service
    if _refresh_service is None:
        _refresh_service = MarketRefreshService()
    return _refresh_service


def reset_refresh_service() -> None:
    """Reset the refresh service singleton (mainly for testing)."""
    global _refresh_service
    _refresh_service = None
