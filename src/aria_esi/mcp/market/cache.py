"""
Market Cache for MCP Market Tools.

Provides in-memory caching of market data with multi-layer fallback:
1. Fuzzwork aggregated prices (primary, station-filtered)
2. ESI regional orders (fallback)
3. Database cache (stale fallback)

Follows the ActivityCache pattern: on-demand refresh with async locks
to prevent duplicate API calls.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from aria_esi.core.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

from aria_esi.mcp.market.clients import FuzzworkAggregate, FuzzworkClient, create_client
from aria_esi.mcp.market.database import MarketDatabase, get_market_database
from aria_esi.mcp.market.database_async import AsyncMarketDatabase, get_async_market_database
from aria_esi.models.market import (
    TRADE_HUBS,
    FreshnessLevel,
    ItemPrice,
    PriceAggregate,
    RegionConfig,
    resolve_trade_hub,
)

logger = get_logger("aria_market.cache")

# =============================================================================
# Cache Configuration
# =============================================================================

# TTL settings (seconds)
FUZZWORK_TTL_SECONDS = 900  # 15 minutes
ESI_ORDERS_TTL_SECONDS = 300  # 5 minutes
ESI_HISTORY_TTL_SECONDS = 3600  # 1 hour

# Freshness thresholds (seconds)
FRESH_THRESHOLD = 300  # 5 minutes
RECENT_THRESHOLD = 1800  # 30 minutes


# =============================================================================
# Cached Data Structures
# =============================================================================


@dataclass
class CachedPrice:
    """Cached price data for a single type ID."""

    type_id: int
    type_name: str
    buy: PriceAggregate
    sell: PriceAggregate
    spread: float | None
    spread_percent: float | None
    timestamp: float
    source: str  # "fuzzwork", "esi", "database"


@dataclass
class CacheLayer:
    """Status tracking for a single cache layer."""

    name: str
    data: dict[int, CachedPrice] = field(default_factory=dict)
    timestamp: float = 0.0
    ttl_seconds: int = 900
    last_error: str | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def is_stale(self) -> bool:
        """Check if cache is stale."""
        return (time.time() - self.timestamp) > self.ttl_seconds

    def get_age_seconds(self) -> int | None:
        """Get cache age in seconds."""
        if self.timestamp == 0:
            return None
        return int(time.time() - self.timestamp)


@dataclass
class CachedOrders:
    """Cached raw orders for a region/type/order_type combination."""

    orders: list[dict]
    timestamp: float
    region_id: int
    type_id: int
    order_type: str  # "sell", "buy", or "all"


# =============================================================================
# Market Cache
# =============================================================================


class MarketCache:
    """
    Multi-layer cache for market price data.

    Layers (in order of preference):
    1. Fuzzwork - Aggregated prices, station-filtered (trade hubs only)
    2. ESI Orders - Raw order data, region-wide (any region)
    3. Database - Persistent cache, potentially stale

    Thread-safety: Uses asyncio.Lock per layer to prevent concurrent
    refresh operations. Designed for single async event loop.
    """

    def __init__(
        self,
        region: str = "jita",
        station_only: bool = True,
        region_id: int | None = None,
        region_name: str | None = None,
    ):
        """
        Initialize market cache.

        Args:
            region: Trade hub name (jita, amarr, dodixie, rens, hek)
            station_only: If True, filter prices to trade hub station
            region_id: Direct region ID (bypasses trade hub resolution)
            region_name: Region name (used with region_id for non-trade-hub regions)
        """
        self._hub: RegionConfig
        # If region_id is provided directly, use ESI-only mode
        if region_id is not None:
            self._hub = RegionConfig(
                region_id=region_id,
                region_name=region_name or f"Region {region_id}",
                station_id=None,
                station_name=None,
                system_id=None,
            )
            self._is_trade_hub = False
        else:
            hub = resolve_trade_hub(region) or TRADE_HUBS["jita"]
            self._hub = RegionConfig(
                region_id=hub["region_id"],
                region_name=hub["region_name"],
                station_id=hub["station_id"],
                station_name=hub["station_name"],
                system_id=hub["system_id"],
            )
            self._is_trade_hub = True

        self._region_id: int = self._hub["region_id"]
        self._station_id: int | None = (
            self._hub["station_id"] if station_only and self._is_trade_hub else None
        )
        self._station_only = station_only

        # Cache layers
        self._fuzzwork = CacheLayer(name="fuzzwork", ttl_seconds=FUZZWORK_TTL_SECONDS)
        self._esi_orders = CacheLayer(name="esi_orders", ttl_seconds=ESI_ORDERS_TTL_SECONDS)

        # Raw orders cache: key = (region_id, type_id, order_type)
        self._raw_orders_cache: dict[tuple[int, int, str], CachedOrders] = {}
        self._raw_orders_lock = asyncio.Lock()

        # Clients (lazy-loaded)
        self._fuzzwork_client: FuzzworkClient | None = None
        self._esi_client: Any | None = None  # ESIClient
        self._database: MarketDatabase | None = None
        self._async_database: AsyncMarketDatabase | None = None

    def _get_fuzzwork_client(self) -> FuzzworkClient:
        """Get or create Fuzzwork client."""
        if self._fuzzwork_client is None:
            self._fuzzwork_client = create_client(
                region=self._hub.get("region_name", "The Forge"),
                station_only=self._station_only,
            )
            # Update with actual region/station IDs
            self._fuzzwork_client.region_id = self._region_id
            self._fuzzwork_client.station_id = self._station_id
        return self._fuzzwork_client

    def _get_database(self) -> MarketDatabase:
        """Get or create database connection (sync)."""
        if self._database is None:
            self._database = get_market_database()
        return self._database

    async def _get_async_database(self) -> AsyncMarketDatabase:
        """Get or create async database connection."""
        if self._async_database is None:
            self._async_database = await get_async_market_database()
        return self._async_database

    # =========================================================================
    # Public API
    # =========================================================================

    async def get_prices(
        self,
        type_ids: Sequence[int],
        type_names: dict[int, str] | None = None,
    ) -> list[ItemPrice]:
        """
        Get prices for multiple type IDs.

        Args:
            type_ids: List of type IDs to fetch
            type_names: Optional mapping of type_id to name

        Returns:
            List of ItemPrice objects
        """
        if not type_ids:
            return []

        type_names = type_names or {}

        # For trade hubs, use Fuzzwork (aggregated data)
        # For other regions, use ESI directly
        if self._is_trade_hub:
            # Try Fuzzwork first
            cached = await self._get_from_fuzzwork(type_ids, type_names)

            # Check for missing items
            found_ids = {item.type_id for item in cached}
            missing_ids = [tid for tid in type_ids if tid not in found_ids]

            if missing_ids:
                # Fall back to async database for missing items
                db_results = await self._get_from_database_async(missing_ids, type_names)
                cached.extend(db_results)

            return cached
        else:
            # Non-trade-hub region: use ESI directly
            return await self._get_from_esi(type_ids, type_names)

    async def get_price(
        self,
        type_id: int,
        type_name: str | None = None,
    ) -> ItemPrice | None:
        """
        Get price for a single type ID.

        Args:
            type_id: Type ID to fetch
            type_name: Optional item name

        Returns:
            ItemPrice or None if not found
        """
        names = {type_id: type_name} if type_name else {}
        results = await self.get_prices([type_id], names)
        return results[0] if results else None

    def get_cache_status(self) -> dict[str, Any]:
        """
        Get cache status for diagnostics.

        Returns:
            Dict with layer status information
        """
        return {
            "fuzzwork": {
                "cached_types": len(self._fuzzwork.data),
                "age_seconds": self._fuzzwork.get_age_seconds(),
                "ttl_seconds": self._fuzzwork.ttl_seconds,
                "stale": self._fuzzwork.is_stale(),
                "last_error": self._fuzzwork.last_error,
            },
            "esi_orders": {
                "cached_types": len(self._esi_orders.data),
                "age_seconds": self._esi_orders.get_age_seconds(),
                "ttl_seconds": self._esi_orders.ttl_seconds,
                "stale": self._esi_orders.is_stale(),
                "last_error": self._esi_orders.last_error,
            },
            "region_id": self._region_id,
            "station_id": self._station_id,
        }

    def get_freshness(self, timestamp: float) -> FreshnessLevel:
        """Classify freshness based on data timestamp."""
        age = time.time() - timestamp
        if age < FRESH_THRESHOLD:
            return "fresh"
        elif age < RECENT_THRESHOLD:
            return "recent"
        return "stale"

    async def get_regional_orders(
        self,
        region_id: int,
        type_id: int,
        order_type: str = "sell",
    ) -> list[dict]:
        """
        Get raw market orders for a type in a region.

        Provides cached access to ESI market orders with TTL-based expiry.
        Used by market_find_nearby for proximity searches.

        Args:
            region_id: Region to query
            type_id: Item type ID
            order_type: "sell", "buy", or "all"

        Returns:
            List of raw ESI order dicts
        """
        cache_key = (region_id, type_id, order_type)

        # Check cache first (outside lock for read)
        cached = self._raw_orders_cache.get(cache_key)
        if cached and (time.time() - cached.timestamp) < ESI_ORDERS_TTL_SECONDS:
            logger.debug(
                "Cache hit for orders: region=%d type=%d order_type=%s",
                region_id,
                type_id,
                order_type,
            )
            return cached.orders

        # Fetch with lock to prevent duplicate requests
        async with self._raw_orders_lock:
            # Double-check cache after acquiring lock
            cached = self._raw_orders_cache.get(cache_key)
            if cached and (time.time() - cached.timestamp) < ESI_ORDERS_TTL_SECONDS:
                return cached.orders

            # Fetch from ESI
            orders = await self._fetch_raw_orders(region_id, type_id, order_type)

            # Cache the result
            self._raw_orders_cache[cache_key] = CachedOrders(
                orders=orders,
                timestamp=time.time(),
                region_id=region_id,
                type_id=type_id,
                order_type=order_type,
            )

            logger.debug(
                "Fetched %d orders from ESI: region=%d type=%d order_type=%s",
                len(orders),
                region_id,
                type_id,
                order_type,
            )
            return orders

    async def _fetch_raw_orders(
        self,
        region_id: int,
        type_id: int,
        order_type: str,
    ) -> list[dict]:
        """
        Fetch raw orders from ESI.

        Internal method - use get_regional_orders() for cached access.
        """
        try:
            from aria_esi.mcp.esi_client import get_async_esi_client

            client = await get_async_esi_client()
        except Exception as e:
            logger.warning("ESI client not available: %s", e)
            return []

        all_orders: list[dict] = []

        if order_type in ("sell", "all"):
            try:
                data = await client.get(
                    f"/markets/{region_id}/orders/",
                    params={"type_id": str(type_id), "order_type": "sell"},
                )
                if isinstance(data, list):
                    all_orders.extend(data)
            except Exception as e:
                logger.debug("Failed to fetch sell orders: %s", e)

        if order_type in ("buy", "all"):
            try:
                data = await client.get(
                    f"/markets/{region_id}/orders/",
                    params={"type_id": str(type_id), "order_type": "buy"},
                )
                if isinstance(data, list):
                    all_orders.extend(data)
            except Exception as e:
                logger.debug("Failed to fetch buy orders: %s", e)

        return all_orders

    # =========================================================================
    # Fuzzwork Layer
    # =========================================================================

    async def _get_from_fuzzwork(
        self,
        type_ids: Sequence[int],
        type_names: dict[int, str],
    ) -> list[ItemPrice]:
        """
        Fetch prices from Fuzzwork API.

        Uses async lock to prevent concurrent API calls.
        """
        async with self._fuzzwork.lock:
            try:
                client = self._get_fuzzwork_client()
                aggregates = await client.get_aggregates(type_ids)
                self._fuzzwork.timestamp = time.time()
                self._fuzzwork.last_error = None

                results = []
                for type_id, agg in aggregates.items():
                    price = self._aggregate_to_item_price(
                        type_id,
                        agg,
                        type_names.get(type_id, f"Type {type_id}"),
                        source="fuzzwork",
                    )
                    self._fuzzwork.data[type_id] = CachedPrice(
                        type_id=type_id,
                        type_name=price.type_name,
                        buy=price.buy,
                        sell=price.sell,
                        spread=price.spread,
                        spread_percent=price.spread_percent,
                        timestamp=time.time(),
                        source="fuzzwork",
                    )
                    results.append(price)

                logger.debug("Fetched %d prices from Fuzzwork", len(results))
                return results

            except Exception as e:
                self._fuzzwork.last_error = str(e)
                logger.warning("Fuzzwork fetch failed: %s", e)
                return []

    def _aggregate_to_item_price(
        self,
        type_id: int,
        agg: FuzzworkAggregate,
        type_name: str,
        source: str,
    ) -> ItemPrice:
        """Convert FuzzworkAggregate to ItemPrice model."""
        buy_agg = PriceAggregate(
            order_count=agg.buy_order_count,
            volume=agg.buy_volume,
            min_price=agg.buy_min if agg.buy_min > 0 else None,
            max_price=agg.buy_max if agg.buy_max > 0 else None,
            weighted_avg=agg.buy_weighted_average if agg.buy_weighted_average > 0 else None,
            median=agg.buy_median if agg.buy_median > 0 else None,
            percentile_5=agg.buy_percentile if agg.buy_percentile > 0 else None,
            stddev=agg.buy_stddev if agg.buy_stddev > 0 else None,
        )

        sell_agg = PriceAggregate(
            order_count=agg.sell_order_count,
            volume=agg.sell_volume,
            min_price=agg.sell_min if agg.sell_min > 0 else None,
            max_price=agg.sell_max if agg.sell_max > 0 else None,
            weighted_avg=agg.sell_weighted_average if agg.sell_weighted_average > 0 else None,
            median=agg.sell_median if agg.sell_median > 0 else None,
            percentile_5=agg.sell_percentile if agg.sell_percentile > 0 else None,
            stddev=agg.sell_stddev if agg.sell_stddev > 0 else None,
        )

        # Calculate spread
        spread = None
        spread_percent = None
        if sell_agg.min_price and buy_agg.max_price:
            spread = round(sell_agg.min_price - buy_agg.max_price, 2)
            if sell_agg.min_price > 0:
                spread_percent = round((spread / sell_agg.min_price) * 100, 2)

        return ItemPrice(
            type_id=type_id,
            type_name=type_name,
            buy=buy_agg,
            sell=sell_agg,
            spread=spread,
            spread_percent=spread_percent,
            freshness=self.get_freshness(time.time()),
        )

    # =========================================================================
    # ESI Layer (Non-Trade-Hub Regions)
    # =========================================================================

    async def _get_from_esi(
        self,
        type_ids: Sequence[int],
        type_names: dict[int, str],
    ) -> list[ItemPrice]:
        """
        Get prices directly from ESI for non-trade-hub regions.

        Fetches raw orders and aggregates them into buy/sell stats.
        """
        try:
            from aria_esi.mcp.esi_client import get_async_esi_client

            client = await get_async_esi_client()
        except Exception as e:
            logger.warning("ESI client not available: %s", e)
            return []

        results: list[ItemPrice] = []

        for type_id in type_ids:
            name = type_names.get(type_id, f"Type {type_id}")

            try:
                # Fetch buy and sell orders
                buy_orders: list[dict] = []
                sell_orders: list[dict] = []

                try:
                    data = await client.get(
                        f"/markets/{self._region_id}/orders/",
                        params={"type_id": str(type_id), "order_type": "buy"},
                    )
                    if isinstance(data, list):
                        buy_orders = data
                except Exception as e:
                    logger.debug("Failed to fetch buy orders for %d: %s", type_id, e)

                try:
                    data = await client.get(
                        f"/markets/{self._region_id}/orders/",
                        params={"type_id": str(type_id), "order_type": "sell"},
                    )
                    if isinstance(data, list):
                        sell_orders = data
                except Exception as e:
                    logger.debug("Failed to fetch sell orders for %d: %s", type_id, e)

                # Aggregate buy orders
                buy_agg = self._aggregate_orders(buy_orders, is_buy=True)
                sell_agg = self._aggregate_orders(sell_orders, is_buy=False)

                # Calculate spread
                spread = None
                spread_percent = None
                if sell_agg.min_price and buy_agg.max_price:
                    spread = round(sell_agg.min_price - buy_agg.max_price, 2)
                    if sell_agg.min_price > 0:
                        spread_percent = round((spread / sell_agg.min_price) * 100, 2)

                results.append(
                    ItemPrice(
                        type_id=type_id,
                        type_name=name,
                        buy=buy_agg,
                        sell=sell_agg,
                        spread=spread,
                        spread_percent=spread_percent,
                        freshness="fresh",
                    )
                )

            except Exception as e:
                logger.warning("Failed to fetch ESI prices for %d: %s", type_id, e)

        return results

    def _aggregate_orders(self, orders: list[dict], is_buy: bool) -> PriceAggregate:
        """Aggregate raw ESI orders into price statistics."""
        from statistics import median as calc_median
        from statistics import stdev as calc_stdev

        if not orders:
            return PriceAggregate(
                order_count=0,
                volume=0,
                min_price=None,
                max_price=None,
                weighted_avg=None,
                median=None,
                percentile_5=None,
                stddev=None,
            )

        prices = [o["price"] for o in orders]
        volumes = [o["volume_remain"] for o in orders]
        total_volume = sum(volumes)

        # Weighted average
        if total_volume > 0:
            weighted_avg = sum(p * v for p, v in zip(prices, volumes)) / total_volume
        else:
            weighted_avg = sum(prices) / len(prices) if prices else None

        # Percentile 5 (for buys: top 5%, for sells: bottom 5%)
        sorted_prices = sorted(prices, reverse=is_buy)
        idx_5 = max(0, int(len(sorted_prices) * 0.05))
        percentile_5 = sorted_prices[idx_5] if sorted_prices else None

        # Standard deviation
        try:
            stddev_val = calc_stdev(prices) if len(prices) > 1 else 0.0
        except Exception:
            stddev_val = None

        return PriceAggregate(
            order_count=len(orders),
            volume=total_volume,
            min_price=min(prices) if prices else None,
            max_price=max(prices) if prices else None,
            weighted_avg=round(weighted_avg, 2) if weighted_avg else None,
            median=round(calc_median(prices), 2) if prices else None,
            percentile_5=round(percentile_5, 2) if percentile_5 else None,
            stddev=round(stddev_val, 2) if stddev_val else None,
        )

    # =========================================================================
    # Database Layer (Stale Fallback)
    # =========================================================================

    def _get_from_database(
        self,
        type_ids: Sequence[int],
        type_names: dict[int, str],
    ) -> list[ItemPrice]:
        """
        Get cached prices from database.

        This is the stale fallback when Fuzzwork is unavailable.
        """
        try:
            db = self._get_database()
            cached = db.get_aggregates_batch(
                type_ids,
                self._region_id,
                max_age_seconds=86400,  # Accept up to 24h old data as fallback
            )

            results = []
            for type_id, agg in cached.items():
                name = type_names.get(type_id)
                if not name:
                    type_info = db.resolve_type_id(type_id)
                    name = type_info.type_name if type_info else f"Type {type_id}"

                # Convert database aggregate to ItemPrice
                buy_agg = PriceAggregate(
                    order_count=agg.buy_order_count,
                    volume=agg.buy_volume,
                    min_price=agg.buy_min,
                    max_price=agg.buy_max,
                    weighted_avg=agg.buy_weighted_avg,
                    median=agg.buy_median,
                    percentile_5=agg.buy_percentile,
                    stddev=agg.buy_stddev,
                )

                sell_agg = PriceAggregate(
                    order_count=agg.sell_order_count,
                    volume=agg.sell_volume,
                    min_price=agg.sell_min,
                    max_price=agg.sell_max,
                    weighted_avg=agg.sell_weighted_avg,
                    median=agg.sell_median,
                    percentile_5=agg.sell_percentile,
                    stddev=agg.sell_stddev,
                )

                spread = None
                spread_percent = None
                if sell_agg.min_price and buy_agg.max_price:
                    spread = round(sell_agg.min_price - buy_agg.max_price, 2)
                    if sell_agg.min_price > 0:
                        spread_percent = round((spread / sell_agg.min_price) * 100, 2)

                results.append(
                    ItemPrice(
                        type_id=type_id,
                        type_name=name,
                        buy=buy_agg,
                        sell=sell_agg,
                        spread=spread,
                        spread_percent=spread_percent,
                        freshness=self.get_freshness(agg.updated_at),
                    )
                )

            logger.debug("Got %d prices from database cache", len(results))
            return results

        except Exception as e:
            logger.warning("Database cache read failed: %s", e)
            return []

    async def _get_from_database_async(
        self,
        type_ids: Sequence[int],
        type_names: dict[int, str],
    ) -> list[ItemPrice]:
        """
        Get cached prices from async database.

        This is the async version of the stale fallback.
        """
        try:
            db = await self._get_async_database()
            cached = await db.get_aggregates_batch(
                type_ids,
                self._region_id,
                max_age_seconds=86400,  # Accept up to 24h old data as fallback
            )

            results = []
            for type_id, agg in cached.items():
                name = type_names.get(type_id)
                if not name:
                    type_info = await db.resolve_type_id(type_id)
                    name = type_info.type_name if type_info else f"Type {type_id}"

                # Convert database aggregate to ItemPrice
                buy_agg = PriceAggregate(
                    order_count=agg.buy_order_count,
                    volume=agg.buy_volume,
                    min_price=agg.buy_min,
                    max_price=agg.buy_max,
                    weighted_avg=agg.buy_weighted_avg,
                    median=agg.buy_median,
                    percentile_5=agg.buy_percentile,
                    stddev=agg.buy_stddev,
                )

                sell_agg = PriceAggregate(
                    order_count=agg.sell_order_count,
                    volume=agg.sell_volume,
                    min_price=agg.sell_min,
                    max_price=agg.sell_max,
                    weighted_avg=agg.sell_weighted_avg,
                    median=agg.sell_median,
                    percentile_5=agg.sell_percentile,
                    stddev=agg.sell_stddev,
                )

                spread = None
                spread_percent = None
                if sell_agg.min_price and buy_agg.max_price:
                    spread = round(sell_agg.min_price - buy_agg.max_price, 2)
                    if sell_agg.min_price > 0:
                        spread_percent = round((spread / sell_agg.min_price) * 100, 2)

                results.append(
                    ItemPrice(
                        type_id=type_id,
                        type_name=name,
                        buy=buy_agg,
                        sell=sell_agg,
                        spread=spread,
                        spread_percent=spread_percent,
                        freshness=self.get_freshness(agg.updated_at),
                    )
                )

            logger.debug("Got %d prices from async database cache", len(results))
            return results

        except Exception as e:
            logger.warning("Async database cache read failed: %s", e)
            return []


# =============================================================================
# Module-level Singleton
# =============================================================================

_market_cache: MarketCache | None = None


def get_market_cache(region: str = "jita") -> MarketCache:
    """
    Get or create the market cache singleton.

    Note: This creates a singleton for the specified region.
    If you need caches for multiple regions, create separate instances.
    """
    global _market_cache
    if _market_cache is None:
        _market_cache = MarketCache(region=region)
    return _market_cache


def reset_market_cache() -> None:
    """Reset the market cache singleton (mainly for testing)."""
    global _market_cache
    _market_cache = None
