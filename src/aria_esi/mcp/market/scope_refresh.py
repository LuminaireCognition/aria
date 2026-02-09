"""
Market Scope Refresh Service.

ESI-backed market data fetcher for ad-hoc scopes (region, station, system, structure).
Fetches orders from ESI, aggregates them, and stores results in market_scope_prices.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from aria_esi.core.client import ESIClient, ESIError
from aria_esi.core.logging import get_logger
from aria_esi.models.market import ScopePriceRefreshInfo, ScopeRefreshResult

if TYPE_CHECKING:
    from .database import MarketScope, MarketScopePrice, WatchlistItem
    from .database_async import AsyncMarketDatabase

logger = get_logger(__name__)


@dataclass
class AggregatedPrice:
    """Aggregated price data from ESI orders."""

    type_id: int
    buy_max: float | None = None
    buy_volume: int = 0
    buy_order_count: int = 0
    sell_min: float | None = None
    sell_volume: int = 0
    sell_order_count: int = 0
    spread_pct: float | None = None

    def calculate_spread(self) -> None:
        """Calculate spread percentage from buy_max and sell_min."""
        if self.buy_max is not None and self.sell_min is not None and self.sell_min > 0:
            self.spread_pct = ((self.sell_min - self.buy_max) / self.sell_min) * 100
        else:
            self.spread_pct = None


@dataclass
class FetchContext:
    """Context for a scope refresh operation."""

    scope: MarketScope
    watchlist_items: list[WatchlistItem]
    start_time: float = field(default_factory=time.time)
    http_last_modified: int | None = None
    http_expires: int | None = None
    was_conditional: bool = False
    pages_fetched: int = 0
    pages_truncated: bool = False
    scan_status: str = "complete"
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    prices: dict[int, AggregatedPrice] = field(default_factory=dict)

    @property
    def duration_ms(self) -> int:
        """Calculate duration in milliseconds."""
        return int((time.time() - self.start_time) * 1000)


class MarketScopeFetcher:
    """
    ESI-backed market data fetcher for ad-hoc scopes.

    Handles fetching market orders from ESI, aggregating them into
    buy_max/sell_min prices, and storing results in market_scope_prices.

    Supports different scope types:
    - region: Fetch orders per type_id from watchlist
    - station: Fetch region orders, filter by location_id
    - system: Fetch region orders, filter by system_id
    - structure: Fetch all structure orders (paginated), filter by watchlist

    Caching:
        Uses TTL-based caching (DEFAULT_TTL_SECONDS). If data was fetched
        within the TTL window, cached results are returned without ESI calls.

    Future Optimization:
        Conditional requests (If-Modified-Since) could reduce bandwidth when
        ESI data hasn't changed, returning 304 Not Modified. This would require
        tracking http_last_modified per endpoint (complex for region/station/system
        scopes that make multiple per-type calls). The ESIClient already supports
        this via the if_modified_since parameter on get_with_headers().
    """

    DEFAULT_TTL_SECONDS = 900  # 15 minutes
    MAX_STRUCTURE_PAGES = 5
    MAX_CONCURRENT_FETCHES = 10

    def __init__(
        self,
        db: AsyncMarketDatabase,
        client: ESIClient | None = None,
    ):
        """
        Initialize the scope fetcher.

        Args:
            db: Async market database for storage
            client: Optional ESI client (creates one if not provided)
        """
        self.db = db
        self.client = client or ESIClient()

    async def refresh_scope(
        self,
        scope: MarketScope,
        force_refresh: bool = False,
        max_structure_pages: int | None = None,
    ) -> ScopeRefreshResult:
        """
        Refresh market data for an ad-hoc scope.

        Args:
            scope: MarketScope to refresh
            force_refresh: Force refresh even if data is fresh
            max_structure_pages: Override MAX_STRUCTURE_PAGES for structure scopes

        Returns:
            ScopeRefreshResult with refresh details and price data

        Raises:
            ValueError: If scope is a core hub scope (use Fuzzwork instead)
        """
        # Validate scope
        if scope.is_core:
            return self._error_result(
                scope,
                "CORE_SCOPE_REFRESH_DENIED",
                "Core hub scopes use Fuzzwork aggregates, not ESI refresh",
            )

        if scope.watchlist_id is None:
            return self._error_result(
                scope,
                "NO_WATCHLIST",
                "Ad-hoc scopes require a watchlist",
            )

        # Get watchlist items
        watchlist_items = await self.db.get_watchlist_items_for_scope(scope.scope_id)
        if not watchlist_items:
            return self._error_result(
                scope,
                "EMPTY_WATCHLIST",
                "Scope has no watchlist items to refresh",
            )

        # Check TTL unless force_refresh
        if not force_refresh and scope.last_scanned_at:
            age = int(time.time()) - scope.last_scanned_at
            if age < self.DEFAULT_TTL_SECONDS:
                # Return cached data without re-fetching
                return await self._build_cached_result(scope)

        # Create fetch context
        ctx = FetchContext(
            scope=scope,
            watchlist_items=watchlist_items,
        )

        # Dispatch to appropriate handler
        if scope.scope_type == "region":
            await self._refresh_region_scope(ctx)
        elif scope.scope_type in ("station", "system"):
            await self._refresh_filtered_scope(ctx)
        elif scope.scope_type == "structure":
            await self._refresh_structure_scope(
                ctx,
                max_pages=max_structure_pages or self.MAX_STRUCTURE_PAGES,
            )
        else:
            return self._error_result(
                scope,
                "INVALID_SCOPE_TYPE",
                f"Unknown scope type: {scope.scope_type}",
            )

        # Store results
        await self._store_results(ctx)

        # Build result
        return await self._build_result(ctx)

    async def _refresh_region_scope(self, ctx: FetchContext) -> None:
        """
        Refresh a region scope by fetching orders per type_id.

        For each watchlist item, fetches orders from ESI and aggregates them.
        """
        region_id = ctx.scope.region_id
        if region_id is None:
            ctx.errors.append("Region scope missing region_id")
            ctx.scan_status = "error"
            return

        # Fetch orders for each type in watchlist
        type_ids = [item.type_id for item in ctx.watchlist_items]
        await self._fetch_type_orders_batch(ctx, region_id, type_ids)

    async def _refresh_filtered_scope(self, ctx: FetchContext) -> None:
        """
        Refresh a station or system scope by fetching region orders and filtering.

        Fetches orders from the parent region, then filters by location_id (station)
        or system_id (system).
        """
        # Determine parent region
        region_id = ctx.scope.parent_region_id
        if region_id is None:
            ctx.errors.append(f"{ctx.scope.scope_type.title()} scope missing parent_region_id")
            ctx.scan_status = "error"
            return

        # Fetch orders for each type in watchlist
        type_ids = [item.type_id for item in ctx.watchlist_items]

        # Determine filter
        if ctx.scope.scope_type == "station":
            filter_key = "location_id"
            filter_value = ctx.scope.station_id
        else:  # system
            filter_key = "system_id"
            filter_value = ctx.scope.system_id

        if filter_value is None:
            ctx.errors.append(f"{ctx.scope.scope_type.title()} scope missing {filter_key}")
            ctx.scan_status = "error"
            return

        await self._fetch_type_orders_batch(
            ctx,
            region_id,
            type_ids,
            filter_key=filter_key,
            filter_value=filter_value,
        )

    async def _refresh_structure_scope(
        self,
        ctx: FetchContext,
        max_pages: int,
    ) -> None:
        """
        Refresh a structure scope by fetching all structure orders (paginated).

        Structure orders cannot be filtered by type_id, so we fetch all pages
        up to max_pages and then filter by watchlist.

        Args:
            ctx: Fetch context
            max_pages: Maximum pages to fetch before truncating
        """
        structure_id = ctx.scope.structure_id
        if structure_id is None:
            ctx.errors.append("Structure scope missing structure_id")
            ctx.scan_status = "error"
            return

        # Build watchlist type_id set for filtering
        watchlist_type_ids = {item.type_id for item in ctx.watchlist_items}

        # Initialize prices dict for all watchlist items
        for type_id in watchlist_type_ids:
            ctx.prices[type_id] = AggregatedPrice(type_id=type_id)

        # Fetch pages
        page = 1
        total_pages = None

        while page <= max_pages:
            try:
                response = self.client.get_with_headers(
                    f"/markets/structures/{structure_id}/",
                    auth=True,
                    params={"page": str(page)},
                )

                # Update headers from first page
                if page == 1:
                    ctx.http_last_modified = response.last_modified_timestamp
                    ctx.http_expires = response.expires_timestamp
                    total_pages = response.x_pages

                ctx.pages_fetched = page

                # Process orders
                if response.data and isinstance(response.data, list):
                    self._aggregate_orders(
                        ctx,
                        response.data,
                        filter_type_ids=watchlist_type_ids,
                    )

                # Check if we've fetched all pages
                if total_pages and page >= total_pages:
                    break

                page += 1

            except ESIError as e:
                if e.status_code == 403:
                    ctx.errors.append(
                        f"Access denied to structure {structure_id}. "
                        "Authentication may be required or structure access revoked."
                    )
                elif e.status_code == 404:
                    ctx.errors.append(
                        f"Structure {structure_id} not found. It may have been destroyed."
                    )
                else:
                    ctx.errors.append(f"ESI error: {e.message}")
                ctx.scan_status = "error"
                return

        # Check for truncation
        if total_pages and page < total_pages:
            ctx.pages_truncated = True
            ctx.scan_status = "truncated"
            ctx.warnings.append(
                f"Truncated at page {page}/{total_pages}. Some watchlist items may be missing."
            )

            # Mark unfound watchlist items as skipped_truncation
            for type_id in watchlist_type_ids:
                price = ctx.prices.get(type_id)
                if price and price.buy_order_count == 0 and price.sell_order_count == 0:
                    # This item wasn't found - could be on later pages
                    pass  # Will be marked as skipped_truncation in _store_results

        # Calculate spreads
        for price in ctx.prices.values():
            price.calculate_spread()

    async def _fetch_type_orders_batch(
        self,
        ctx: FetchContext,
        region_id: int,
        type_ids: list[int],
        filter_key: str | None = None,
        filter_value: int | None = None,
    ) -> None:
        """
        Fetch orders for multiple type_ids with optional filtering.

        Uses asyncio semaphore to limit concurrent requests.

        Args:
            ctx: Fetch context
            region_id: Region ID to fetch from
            type_ids: List of type IDs to fetch
            filter_key: Optional filter key (location_id or system_id)
            filter_value: Optional filter value
        """
        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_FETCHES)

        async def fetch_one(type_id: int) -> None:
            async with semaphore:
                await self._fetch_type_orders(
                    ctx,
                    region_id,
                    type_id,
                    filter_key=filter_key,
                    filter_value=filter_value,
                )

        # Run fetches concurrently
        await asyncio.gather(*[fetch_one(tid) for tid in type_ids])

    async def _fetch_type_orders(
        self,
        ctx: FetchContext,
        region_id: int,
        type_id: int,
        filter_key: str | None = None,
        filter_value: int | None = None,
    ) -> None:
        """
        Fetch and aggregate orders for a single type_id.

        Args:
            ctx: Fetch context
            region_id: Region ID to fetch from
            type_id: Type ID to fetch
            filter_key: Optional filter key (location_id or system_id)
            filter_value: Optional filter value
        """
        try:
            # Use asyncio.to_thread since ESIClient is sync
            response = await asyncio.to_thread(
                self.client.get_with_headers,
                f"/markets/{region_id}/orders/",
                params={"type_id": str(type_id)},
            )

            # Update headers from first response
            if ctx.http_last_modified is None:
                ctx.http_last_modified = response.last_modified_timestamp
                ctx.http_expires = response.expires_timestamp

            # Initialize price entry
            price = AggregatedPrice(type_id=type_id)

            if response.data:
                orders = response.data
                if isinstance(orders, list):
                    # Apply filter if specified
                    if filter_key and filter_value is not None:
                        orders = [o for o in orders if o.get(filter_key) == filter_value]

                    # Aggregate
                    for order in orders:
                        is_buy = order.get("is_buy_order", False)
                        order_price = order.get("price", 0)
                        volume = order.get("volume_remain", 0)

                        if is_buy:
                            price.buy_order_count += 1
                            price.buy_volume += volume
                            if price.buy_max is None or order_price > price.buy_max:
                                price.buy_max = order_price
                        else:
                            price.sell_order_count += 1
                            price.sell_volume += volume
                            if price.sell_min is None or order_price < price.sell_min:
                                price.sell_min = order_price

            # Calculate spread
            price.calculate_spread()

            # Store in context
            ctx.prices[type_id] = price

        except ESIError as e:
            ctx.warnings.append(f"Failed to fetch type {type_id}: {e.message}")
            # Create empty price entry so we don't skip it
            ctx.prices[type_id] = AggregatedPrice(type_id=type_id)

    def _aggregate_orders(
        self,
        ctx: FetchContext,
        orders: list[dict],
        filter_type_ids: set[int] | None = None,
    ) -> None:
        """
        Aggregate a batch of orders into the context prices dict.

        Args:
            ctx: Fetch context
            orders: List of order dicts from ESI
            filter_type_ids: Optional set of type_ids to include
        """
        for order in orders:
            type_id = order.get("type_id")
            if type_id is None:
                continue

            # Filter by watchlist if specified
            if filter_type_ids and type_id not in filter_type_ids:
                continue

            # Get or create price entry
            if type_id not in ctx.prices:
                ctx.prices[type_id] = AggregatedPrice(type_id=type_id)
            price = ctx.prices[type_id]

            # Aggregate
            is_buy = order.get("is_buy_order", False)
            order_price = order.get("price", 0)
            volume = order.get("volume_remain", 0)

            if is_buy:
                price.buy_order_count += 1
                price.buy_volume += volume
                if price.buy_max is None or order_price > price.buy_max:
                    price.buy_max = order_price
            else:
                price.sell_order_count += 1
                price.sell_volume += volume
                if price.sell_min is None or order_price < price.sell_min:
                    price.sell_min = order_price

    async def _store_results(self, ctx: FetchContext) -> None:
        """
        Store aggregated prices to the database.

        Creates MarketScopePrice records for each type in the watchlist,
        including zero-rows for items with no orders found.
        """
        from .database import MarketScopePrice

        now = int(time.time())

        # Apply missing headers fallback (per proposal spec)
        # If ESI didn't return headers, use current time as last_modified
        # and current time + TTL as expires
        if ctx.http_last_modified is None:
            ctx.http_last_modified = now
        if ctx.http_expires is None:
            ctx.http_expires = now + self.DEFAULT_TTL_SECONDS

        watchlist_type_ids = {item.type_id for item in ctx.watchlist_items}

        # Determine fetch status for items not found
        missing_status = "skipped_truncation" if ctx.pages_truncated else "complete"

        # Build price records
        prices_to_store: list[MarketScopePrice] = []

        for type_id in watchlist_type_ids:
            price = ctx.prices.get(type_id)

            if price:
                # Determine fetch status
                if (
                    ctx.pages_truncated
                    and price.buy_order_count == 0
                    and price.sell_order_count == 0
                ):
                    fetch_status = "skipped_truncation"
                elif ctx.pages_truncated:
                    fetch_status = "truncated"
                else:
                    fetch_status = "complete"

                prices_to_store.append(
                    MarketScopePrice(
                        scope_id=ctx.scope.scope_id,
                        type_id=type_id,
                        buy_max=price.buy_max,
                        buy_volume=price.buy_volume,
                        sell_min=price.sell_min,
                        sell_volume=price.sell_volume,
                        spread_pct=price.spread_pct,
                        order_count_buy=price.buy_order_count,
                        order_count_sell=price.sell_order_count,
                        updated_at=now,
                        http_last_modified=ctx.http_last_modified,
                        http_expires=ctx.http_expires,
                        source="esi",
                        coverage_type="watchlist",
                        fetch_status=fetch_status,
                    )
                )
            else:
                # Item was in watchlist but not fetched (shouldn't happen for region/station/system)
                prices_to_store.append(
                    MarketScopePrice(
                        scope_id=ctx.scope.scope_id,
                        type_id=type_id,
                        buy_max=None,
                        buy_volume=0,
                        sell_min=None,
                        sell_volume=0,
                        spread_pct=None,
                        order_count_buy=0,
                        order_count_sell=0,
                        updated_at=now,
                        http_last_modified=ctx.http_last_modified,
                        http_expires=ctx.http_expires,
                        source="esi",
                        coverage_type="watchlist",
                        fetch_status=missing_status,
                    )
                )

        # Batch upsert
        if prices_to_store:
            await self.db.upsert_scope_prices_batch(prices_to_store)

        # Update scope scan status
        await self.db.update_scope_scan_status(
            ctx.scope.scope_id,
            ctx.scan_status,
            scanned_at=now,
        )

    async def _build_result(self, ctx: FetchContext) -> ScopeRefreshResult:
        """Build ScopeRefreshResult from fetch context."""
        # Batch resolve type names
        type_ids = list(ctx.prices.keys())
        type_names = await self.db.resolve_type_ids_batch(type_ids)

        # Build price info list
        prices_info: list[ScopePriceRefreshInfo] = []
        items_with_orders = 0
        items_without_orders = 0
        items_skipped = 0

        for type_id, price in ctx.prices.items():
            # Resolve type name (fallback to "Type {id}" if not in DB)
            type_name = type_names.get(type_id, f"Type {type_id}")

            has_orders = price.buy_order_count > 0 or price.sell_order_count > 0
            if has_orders:
                items_with_orders += 1
            else:
                items_without_orders += 1

            # Determine fetch status
            if ctx.pages_truncated and not has_orders:
                fetch_status = "skipped_truncation"
                items_skipped += 1
            elif ctx.pages_truncated:
                fetch_status = "truncated"
            else:
                fetch_status = "complete"

            prices_info.append(
                ScopePriceRefreshInfo(
                    type_id=type_id,
                    type_name=type_name,
                    fetch_status=fetch_status,
                    order_count_buy=price.buy_order_count,
                    order_count_sell=price.sell_order_count,
                    buy_max=price.buy_max,
                    sell_min=price.sell_min,
                )
            )

        return ScopeRefreshResult(
            scope_id=ctx.scope.scope_id,
            scope_name=ctx.scope.scope_name,
            scope_type=ctx.scope.scope_type,
            items_refreshed=len(ctx.prices),
            items_skipped=items_skipped,
            items_with_orders=items_with_orders,
            items_without_orders=items_without_orders,
            refresh_duration_ms=ctx.duration_ms,
            http_last_modified=ctx.http_last_modified,
            http_expires=ctx.http_expires,
            scan_status=ctx.scan_status,
            was_conditional=ctx.was_conditional,
            pages_fetched=ctx.pages_fetched if ctx.scope.scope_type == "structure" else None,
            pages_truncated=ctx.pages_truncated,
            prices=prices_info,
            warnings=ctx.warnings,
            errors=ctx.errors,
        )

    async def _build_cached_result(self, scope: MarketScope) -> ScopeRefreshResult:
        """Build result from cached data without re-fetching."""
        prices = await self.db.get_scope_prices(scope.scope_id)

        # Batch resolve type names
        type_ids = [p.type_id for p in prices]
        type_names = await self.db.resolve_type_ids_batch(type_ids)

        prices_info: list[ScopePriceRefreshInfo] = []
        items_with_orders = 0
        items_without_orders = 0
        items_skipped = 0

        for price in prices:
            has_orders = price.order_count_buy > 0 or price.order_count_sell > 0
            if has_orders:
                items_with_orders += 1
            elif price.fetch_status == "skipped_truncation":
                items_skipped += 1
            else:
                items_without_orders += 1

            prices_info.append(
                ScopePriceRefreshInfo(
                    type_id=price.type_id,
                    type_name=type_names.get(price.type_id, f"Type {price.type_id}"),
                    fetch_status=price.fetch_status,
                    order_count_buy=price.order_count_buy,
                    order_count_sell=price.order_count_sell,
                    buy_max=price.buy_max,
                    sell_min=price.sell_min,
                )
            )

        # Determine overall scan status
        scan_status = scope.last_scan_status or "complete"
        pages_truncated = scan_status == "truncated"

        return ScopeRefreshResult(
            scope_id=scope.scope_id,
            scope_name=scope.scope_name,
            scope_type=scope.scope_type,
            items_refreshed=len(prices),
            items_skipped=items_skipped,
            items_with_orders=items_with_orders,
            items_without_orders=items_without_orders,
            refresh_duration_ms=0,  # Cached result
            http_last_modified=prices[0].http_last_modified if prices else None,
            http_expires=prices[0].http_expires if prices else None,
            scan_status=scan_status,
            was_conditional=False,
            pages_fetched=None,
            pages_truncated=pages_truncated,
            prices=prices_info,
            warnings=["Data returned from cache (within TTL)"],
            errors=[],
        )

    def _error_result(
        self,
        scope: MarketScope,
        code: str,
        message: str,
    ) -> ScopeRefreshResult:
        """Build an error result."""
        return ScopeRefreshResult(
            scope_id=scope.scope_id,
            scope_name=scope.scope_name,
            scope_type=scope.scope_type,
            items_refreshed=0,
            items_skipped=0,
            items_with_orders=0,
            items_without_orders=0,
            refresh_duration_ms=0,
            http_last_modified=None,
            http_expires=None,
            scan_status="error",
            was_conditional=False,
            pages_fetched=None,
            pages_truncated=False,
            prices=[],
            warnings=[],
            errors=[f"{code}: {message}"],
        )
