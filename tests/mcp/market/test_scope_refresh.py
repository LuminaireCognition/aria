"""
Tests for Market Scope Refresh Service.

Tests cover the MarketScopeFetcher service and market_scope_refresh MCP tool:
- Region scope refresh
- Station scope refresh (filtered by location_id)
- System scope refresh (filtered by system_id)
- Structure scope refresh (paginated, watchlist filtered)
- Error handling for various scenarios
- TTL/caching behavior
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aria_esi.core.client import ESIError, ESIResponse
from aria_esi.mcp.market.database import MarketDatabase, MarketScope, WatchlistItem
from aria_esi.mcp.market.database_async import AsyncMarketDatabase
from aria_esi.mcp.market.scope_refresh import AggregatedPrice, MarketScopeFetcher

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_db():
    """Create a temporary sync database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = MarketDatabase(db_path)

        # Add test types
        conn = db._get_connection()
        test_types = [
            (34, "Tritanium", "tritanium", None, None, None, 0.01, 0.01),
            (35, "Pyerite", "pyerite", None, None, None, 0.01, 0.01),
            (36, "Mexallon", "mexallon", None, None, None, 0.01, 0.01),
            (37, "Isogen", "isogen", None, None, None, 0.01, 0.01),
        ]
        conn.executemany(
            """
            INSERT OR REPLACE INTO types (
                type_id, type_name, type_name_lower,
                group_id, category_id, market_group_id, volume, packaged_volume
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            test_types,
        )
        conn.commit()

        yield db, db_path
        db.close()


@pytest.fixture
def mock_esi_client():
    """Create a mock ESI client."""
    return MagicMock()


# =============================================================================
# Helper Functions
# =============================================================================


def create_test_scope(
    sync_db: MarketDatabase,
    scope_name: str,
    scope_type: str,
    *,
    region_id: int | None = None,
    station_id: int | None = None,
    system_id: int | None = None,
    structure_id: int | None = None,
    parent_region_id: int | None = None,
) -> tuple[MarketScope, list[WatchlistItem]]:
    """Create a test scope with watchlist."""
    # Create watchlist
    watchlist = sync_db.create_watchlist(f"{scope_name}_watchlist")

    # Add test items
    items = []
    for type_id in [34, 35]:  # Tritanium, Pyerite
        item = sync_db.add_watchlist_item(watchlist.watchlist_id, type_id)
        items.append(item)

    # Create scope
    scope = sync_db.create_scope(
        scope_name=scope_name,
        scope_type=scope_type,
        region_id=region_id,
        station_id=station_id,
        system_id=system_id,
        structure_id=structure_id,
        parent_region_id=parent_region_id,
        watchlist_id=watchlist.watchlist_id,
    )

    return scope, items


def make_esi_response(
    data: list | dict | None,
    status_code: int = 200,
    last_modified: str | None = "Wed, 22 Jan 2025 10:00:00 GMT",
    expires: str | None = "Wed, 22 Jan 2025 10:15:00 GMT",
    x_pages: int | None = None,
) -> ESIResponse:
    """Create an ESI response for testing."""
    headers = {}
    if last_modified:
        headers["Last-Modified"] = last_modified
    if expires:
        headers["Expires"] = expires
    if x_pages is not None:
        headers["X-Pages"] = str(x_pages)

    return ESIResponse(data=data, headers=headers, status_code=status_code)


def make_orders(
    type_id: int, buy_orders: list[tuple[float, int]], sell_orders: list[tuple[float, int]]
) -> list[dict]:
    """Create mock ESI orders."""
    orders = []
    for i, (price, volume) in enumerate(buy_orders):
        orders.append(
            {
                "order_id": i * 2,
                "type_id": type_id,
                "is_buy_order": True,
                "price": price,
                "volume_remain": volume,
                "location_id": 60003760,
                "system_id": 30000142,
            }
        )
    for i, (price, volume) in enumerate(sell_orders):
        orders.append(
            {
                "order_id": i * 2 + 1,
                "type_id": type_id,
                "is_buy_order": False,
                "price": price,
                "volume_remain": volume,
                "location_id": 60003760,
                "system_id": 30000142,
            }
        )
    return orders


# =============================================================================
# Unit Tests: AggregatedPrice
# =============================================================================


class TestAggregatedPrice:
    """Tests for AggregatedPrice data class."""

    def test_calculate_spread_with_both_prices(self):
        """Test spread calculation when both buy and sell prices exist."""
        price = AggregatedPrice(
            type_id=34,
            buy_max=100.0,
            sell_min=110.0,
        )
        price.calculate_spread()

        assert price.spread_pct is not None
        # (110 - 100) / 110 * 100 = 9.09%
        assert abs(price.spread_pct - 9.09) < 0.1

    def test_calculate_spread_no_buy_price(self):
        """Test spread calculation with no buy orders."""
        price = AggregatedPrice(
            type_id=34,
            buy_max=None,
            sell_min=100.0,
        )
        price.calculate_spread()

        assert price.spread_pct is None

    def test_calculate_spread_no_sell_price(self):
        """Test spread calculation with no sell orders."""
        price = AggregatedPrice(
            type_id=34,
            buy_max=100.0,
            sell_min=None,
        )
        price.calculate_spread()

        assert price.spread_pct is None

    def test_calculate_spread_zero_sell_price(self):
        """Test spread calculation with zero sell price (edge case)."""
        price = AggregatedPrice(
            type_id=34,
            buy_max=100.0,
            sell_min=0.0,
        )
        price.calculate_spread()

        assert price.spread_pct is None


# =============================================================================
# Unit Tests: ESIResponse
# =============================================================================


class TestESIResponseHeaders:
    """Tests for ESIResponse header parsing."""

    def test_parse_last_modified(self):
        """Test parsing Last-Modified header."""
        response = make_esi_response([], last_modified="Wed, 22 Jan 2025 10:00:00 GMT")
        ts = response.last_modified_timestamp

        assert ts is not None
        assert ts > 0

    def test_parse_expires(self):
        """Test parsing Expires header."""
        response = make_esi_response([], expires="Wed, 22 Jan 2025 10:15:00 GMT")
        ts = response.expires_timestamp

        assert ts is not None
        assert ts > 0

    def test_parse_x_pages(self):
        """Test parsing X-Pages header."""
        response = make_esi_response([], x_pages=5)
        pages = response.x_pages

        assert pages == 5

    def test_missing_headers(self):
        """Test handling of missing headers."""
        response = ESIResponse(data=[], headers={}, status_code=200)

        assert response.last_modified_timestamp is None
        assert response.expires_timestamp is None
        assert response.x_pages is None

    def test_is_not_modified(self):
        """Test 304 Not Modified detection."""
        response = ESIResponse(data=None, headers={}, status_code=304)

        assert response.is_not_modified is True

        normal_response = ESIResponse(data=[], headers={}, status_code=200)
        assert normal_response.is_not_modified is False


# =============================================================================
# Integration Tests: MarketScopeFetcher
# =============================================================================


class TestScopeFetcherRegion:
    """Tests for region scope refresh."""

    @pytest.mark.asyncio
    async def test_refresh_region_scope_success(self, temp_db, mock_esi_client):
        """Test successful region scope refresh."""
        sync_db, db_path = temp_db
        async_db = AsyncMarketDatabase(db_path)

        try:
            # Create test scope
            scope, items = create_test_scope(
                sync_db,
                "test_region",
                "region",
                region_id=10000002,
            )

            # Mock ESI responses
            def mock_get_with_headers(endpoint, params=None, **kwargs):
                type_id = int(params.get("type_id", 0))
                if type_id == 34:
                    return make_esi_response(make_orders(34, [(100.0, 1000)], [(110.0, 500)]))
                elif type_id == 35:
                    return make_esi_response(make_orders(35, [(50.0, 2000)], [(55.0, 1000)]))
                return make_esi_response([])

            mock_esi_client.get_with_headers = mock_get_with_headers

            # Create fetcher and refresh
            fetcher = MarketScopeFetcher(async_db, mock_esi_client)
            result = await fetcher.refresh_scope(scope, force_refresh=True)

            # Verify result
            assert result.scope_name == "test_region"
            assert result.scope_type == "region"
            assert result.scan_status == "complete"
            assert result.items_refreshed == 2
            assert result.items_with_orders == 2
            assert len(result.prices) == 2
            assert len(result.errors) == 0
        finally:
            await async_db.close()

    @pytest.mark.asyncio
    async def test_refresh_region_scope_empty_orders(self, temp_db, mock_esi_client):
        """Test region scope refresh with no orders found."""
        sync_db, db_path = temp_db
        async_db = AsyncMarketDatabase(db_path)

        try:
            scope, items = create_test_scope(
                sync_db,
                "empty_region",
                "region",
                region_id=10000037,
            )

            # Mock ESI returning empty orders
            mock_esi_client.get_with_headers = MagicMock(return_value=make_esi_response([]))

            fetcher = MarketScopeFetcher(async_db, mock_esi_client)
            result = await fetcher.refresh_scope(scope, force_refresh=True)

            assert result.scan_status == "complete"
            assert result.items_refreshed == 2
            assert result.items_with_orders == 0
            assert result.items_without_orders == 2

            # Verify prices have zeros
            for price_info in result.prices:
                assert price_info.order_count_buy == 0
                assert price_info.order_count_sell == 0
        finally:
            await async_db.close()


class TestScopeFetcherFiltered:
    """Tests for station and system scope refresh (filtered)."""

    @pytest.mark.asyncio
    async def test_refresh_station_scope_filters_location(self, temp_db, mock_esi_client):
        """Test station scope filters by location_id."""
        sync_db, db_path = temp_db
        async_db = AsyncMarketDatabase(db_path)

        try:
            scope, items = create_test_scope(
                sync_db,
                "test_station",
                "station",
                station_id=60003760,
                parent_region_id=10000002,
            )

            # Mock ESI with orders from multiple locations
            def mock_get_with_headers(endpoint, params=None, **kwargs):
                orders = [
                    # Orders at target station
                    {
                        "order_id": 1,
                        "type_id": 34,
                        "is_buy_order": True,
                        "price": 100.0,
                        "volume_remain": 1000,
                        "location_id": 60003760,
                        "system_id": 30000142,
                    },
                    {
                        "order_id": 2,
                        "type_id": 34,
                        "is_buy_order": False,
                        "price": 110.0,
                        "volume_remain": 500,
                        "location_id": 60003760,
                        "system_id": 30000142,
                    },
                    # Orders at other station (should be filtered out)
                    {
                        "order_id": 3,
                        "type_id": 34,
                        "is_buy_order": True,
                        "price": 200.0,
                        "volume_remain": 5000,
                        "location_id": 60003761,
                        "system_id": 30000142,
                    },
                ]
                return make_esi_response(orders)

            mock_esi_client.get_with_headers = mock_get_with_headers

            fetcher = MarketScopeFetcher(async_db, mock_esi_client)
            result = await fetcher.refresh_scope(scope, force_refresh=True)

            assert result.scan_status == "complete"

            # Find Tritanium price
            trit_price = next((p for p in result.prices if p.type_id == 34), None)
            assert trit_price is not None
            assert trit_price.order_count_buy == 1  # Only the one at 60003760
            assert trit_price.buy_max == 100.0  # Not 200.0 from other station
        finally:
            await async_db.close()

    @pytest.mark.asyncio
    async def test_refresh_system_scope_filters_system_id(self, temp_db, mock_esi_client):
        """Test system scope filters by system_id."""
        sync_db, db_path = temp_db
        async_db = AsyncMarketDatabase(db_path)

        try:
            scope, items = create_test_scope(
                sync_db,
                "test_system",
                "system",
                system_id=30000142,
                parent_region_id=10000002,
            )

            # Mock ESI with orders from multiple systems
            def mock_get_with_headers(endpoint, params=None, **kwargs):
                orders = [
                    # Orders in target system
                    {
                        "order_id": 1,
                        "type_id": 34,
                        "is_buy_order": True,
                        "price": 100.0,
                        "volume_remain": 1000,
                        "location_id": 60003760,
                        "system_id": 30000142,
                    },
                    # Orders in other system (should be filtered out)
                    {
                        "order_id": 2,
                        "type_id": 34,
                        "is_buy_order": True,
                        "price": 200.0,
                        "volume_remain": 5000,
                        "location_id": 60003761,
                        "system_id": 30000143,
                    },
                ]
                return make_esi_response(orders)

            mock_esi_client.get_with_headers = mock_get_with_headers

            fetcher = MarketScopeFetcher(async_db, mock_esi_client)
            result = await fetcher.refresh_scope(scope, force_refresh=True)

            assert result.scan_status == "complete"

            trit_price = next((p for p in result.prices if p.type_id == 34), None)
            assert trit_price is not None
            assert trit_price.order_count_buy == 1
            assert trit_price.buy_max == 100.0
        finally:
            await async_db.close()


class TestScopeFetcherStructure:
    """Tests for structure scope refresh (paginated)."""

    @pytest.mark.asyncio
    async def test_refresh_structure_scope_pagination(self, temp_db, mock_esi_client):
        """Test structure scope pagination."""
        sync_db, db_path = temp_db
        async_db = AsyncMarketDatabase(db_path)

        try:
            scope, items = create_test_scope(
                sync_db,
                "test_structure",
                "structure",
                structure_id=1234567890,
                parent_region_id=10000002,
            )

            # Mock ESI with multiple pages
            def mock_get_with_headers(endpoint, auth=False, params=None, **kwargs):
                page = int(params.get("page", 1)) if params else 1

                if page == 1:
                    return make_esi_response(
                        [
                            {
                                "order_id": 1,
                                "type_id": 34,
                                "is_buy_order": True,
                                "price": 100.0,
                                "volume_remain": 1000,
                            }
                        ],
                        x_pages=2,
                    )
                elif page == 2:
                    return make_esi_response(
                        [
                            {
                                "order_id": 2,
                                "type_id": 35,
                                "is_buy_order": False,
                                "price": 55.0,
                                "volume_remain": 500,
                            }
                        ],
                        x_pages=2,
                    )
                return make_esi_response([])

            mock_esi_client.get_with_headers = mock_get_with_headers

            fetcher = MarketScopeFetcher(async_db, mock_esi_client)
            result = await fetcher.refresh_scope(scope, force_refresh=True)

            assert result.scan_status == "complete"
            assert result.pages_fetched == 2
            assert result.pages_truncated is False
            assert result.items_with_orders == 2
        finally:
            await async_db.close()

    @pytest.mark.asyncio
    async def test_refresh_structure_scope_truncation(self, temp_db, mock_esi_client):
        """Test structure scope truncation at max pages."""
        sync_db, db_path = temp_db
        async_db = AsyncMarketDatabase(db_path)

        try:
            scope, items = create_test_scope(
                sync_db,
                "large_structure",
                "structure",
                structure_id=9876543210,
                parent_region_id=10000002,
            )

            # Mock ESI with more pages than limit
            def mock_get_with_headers(endpoint, auth=False, params=None, **kwargs):
                page = int(params.get("page", 1)) if params else 1
                # Always return data, indicate 10 total pages
                return make_esi_response(
                    [
                        {
                            "order_id": page,
                            "type_id": 34,
                            "is_buy_order": True,
                            "price": 100.0,
                            "volume_remain": 1000,
                        }
                    ],
                    x_pages=10,
                )

            mock_esi_client.get_with_headers = mock_get_with_headers

            fetcher = MarketScopeFetcher(async_db, mock_esi_client)
            result = await fetcher.refresh_scope(scope, force_refresh=True, max_structure_pages=3)

            assert result.scan_status == "truncated"
            assert result.pages_fetched == 3
            assert result.pages_truncated is True
            assert len(result.warnings) > 0
        finally:
            await async_db.close()

    @pytest.mark.asyncio
    async def test_refresh_structure_scope_auth_error(self, temp_db, mock_esi_client):
        """Test structure scope 403 handling."""
        sync_db, db_path = temp_db
        async_db = AsyncMarketDatabase(db_path)

        try:
            scope, items = create_test_scope(
                sync_db,
                "private_structure",
                "structure",
                structure_id=1111111111,
                parent_region_id=10000002,
            )

            # Mock ESI returning 403
            def mock_get_with_headers(endpoint, auth=False, params=None, **kwargs):
                raise ESIError("Access denied", status_code=403)

            mock_esi_client.get_with_headers = mock_get_with_headers

            fetcher = MarketScopeFetcher(async_db, mock_esi_client)
            result = await fetcher.refresh_scope(scope, force_refresh=True)

            assert result.scan_status == "error"
            assert len(result.errors) > 0
            assert "Access denied" in result.errors[0] or "403" in result.errors[0]
        finally:
            await async_db.close()


class TestScopeFetcherErrors:
    """Tests for error handling in scope refresh."""

    @pytest.mark.asyncio
    async def test_refresh_core_scope_rejected(self, temp_db, mock_esi_client):
        """Test that core scopes cannot be refreshed."""
        sync_db, db_path = temp_db
        async_db = AsyncMarketDatabase(db_path)

        try:
            # Get a core scope (Jita)
            scope = sync_db.get_scope("Jita")
            assert scope is not None
            assert scope.is_core

            fetcher = MarketScopeFetcher(async_db, mock_esi_client)
            result = await fetcher.refresh_scope(scope, force_refresh=True)

            assert result.scan_status == "error"
            assert "CORE_SCOPE_REFRESH_DENIED" in result.errors[0]
        finally:
            await async_db.close()

    @pytest.mark.asyncio
    async def test_refresh_scope_no_watchlist(self, temp_db, mock_esi_client):
        """Test error when scope has no watchlist items."""
        sync_db, db_path = temp_db
        async_db = AsyncMarketDatabase(db_path)

        try:
            # Create scope without watchlist items
            watchlist = sync_db.create_watchlist("empty_watchlist")
            scope = sync_db.create_scope(
                scope_name="empty_scope",
                scope_type="region",
                region_id=10000002,
                watchlist_id=watchlist.watchlist_id,
            )

            fetcher = MarketScopeFetcher(async_db, mock_esi_client)
            result = await fetcher.refresh_scope(scope, force_refresh=True)

            assert result.scan_status == "error"
            assert "EMPTY_WATCHLIST" in result.errors[0]
        finally:
            await async_db.close()


class TestScopeFetcherCaching:
    """Tests for TTL and caching behavior."""

    @pytest.mark.asyncio
    async def test_refresh_returns_cached_within_ttl(self, temp_db, mock_esi_client):
        """Test that refresh returns cached data within TTL."""
        sync_db, db_path = temp_db
        async_db = AsyncMarketDatabase(db_path)

        try:
            scope, items = create_test_scope(
                sync_db,
                "cached_scope",
                "region",
                region_id=10000002,
            )

            # First refresh
            call_count = 0

            def mock_get_with_headers(endpoint, params=None, **kwargs):
                nonlocal call_count
                call_count += 1
                return make_esi_response(make_orders(34, [(100.0, 1000)], [(110.0, 500)]))

            mock_esi_client.get_with_headers = mock_get_with_headers

            fetcher = MarketScopeFetcher(async_db, mock_esi_client)
            fetcher.DEFAULT_TTL_SECONDS = 900  # 15 minutes

            # First call - should fetch
            result1 = await fetcher.refresh_scope(scope, force_refresh=True)
            assert result1.scan_status == "complete"

            # Update scope's last_scanned_at in DB to now (simulating recent scan)
            await async_db.update_scope_scan_status(scope.scope_id, "complete")

            # Reload scope to get updated last_scanned_at
            scope = await async_db.get_scope_by_id(scope.scope_id)

            # Second call without force - should return cached
            result2 = await fetcher.refresh_scope(scope, force_refresh=False)

            # Should be a cached response (warning indicates cached)
            assert any("cache" in w.lower() for w in result2.warnings)
        finally:
            await async_db.close()

    @pytest.mark.asyncio
    async def test_force_refresh_ignores_ttl(self, temp_db, mock_esi_client):
        """Test that force_refresh bypasses TTL check."""
        sync_db, db_path = temp_db
        async_db = AsyncMarketDatabase(db_path)

        try:
            scope, items = create_test_scope(
                sync_db,
                "force_refresh_scope",
                "region",
                region_id=10000002,
            )

            call_count = 0

            def mock_get_with_headers(endpoint, params=None, **kwargs):
                nonlocal call_count
                call_count += 1
                return make_esi_response(make_orders(34, [(100.0, 1000)], [(110.0, 500)]))

            mock_esi_client.get_with_headers = mock_get_with_headers

            fetcher = MarketScopeFetcher(async_db, mock_esi_client)

            # First refresh
            await fetcher.refresh_scope(scope, force_refresh=True)
            first_count = call_count

            # Update scope's last_scanned_at
            await async_db.update_scope_scan_status(scope.scope_id, "complete")
            scope = await async_db.get_scope_by_id(scope.scope_id)

            # Force refresh should fetch again
            await fetcher.refresh_scope(scope, force_refresh=True)

            # Should have made more ESI calls
            assert call_count > first_count
        finally:
            await async_db.close()


# =============================================================================
# Header Handling Tests
# =============================================================================


class TestScopeFetcherHeaders:
    """Tests for ESI header handling and fallbacks."""

    @pytest.mark.asyncio
    async def test_headers_preserved_when_present(self, temp_db, mock_esi_client):
        """Test that ESI headers are preserved in results when present."""
        sync_db, db_path = temp_db
        async_db = AsyncMarketDatabase(db_path)

        try:
            scope, items = create_test_scope(
                sync_db,
                "headers_test",
                "region",
                region_id=10000002,
            )

            # Mock ESI response with headers
            mock_esi_client.get_with_headers = MagicMock(
                return_value=make_esi_response(
                    make_orders(34, [(100.0, 1000)], [(110.0, 500)]),
                    last_modified="Wed, 22 Jan 2025 10:00:00 GMT",
                    expires="Wed, 22 Jan 2025 10:15:00 GMT",
                )
            )

            fetcher = MarketScopeFetcher(async_db, mock_esi_client)
            result = await fetcher.refresh_scope(scope, force_refresh=True)

            assert result.scan_status == "complete"
            # Headers should be captured from ESI response
            assert result.http_last_modified is not None
            assert result.http_expires is not None
        finally:
            await async_db.close()

    @pytest.mark.asyncio
    async def test_headers_fallback_when_missing(self, temp_db, mock_esi_client):
        """Test that fallback values are used when ESI headers are missing."""
        sync_db, db_path = temp_db
        async_db = AsyncMarketDatabase(db_path)

        try:
            scope, items = create_test_scope(
                sync_db,
                "no_headers_test",
                "region",
                region_id=10000002,
            )

            # Mock ESI response WITHOUT headers
            mock_esi_client.get_with_headers = MagicMock(
                return_value=make_esi_response(
                    make_orders(34, [(100.0, 1000)], [(110.0, 500)]),
                    last_modified=None,
                    expires=None,
                )
            )

            fetcher = MarketScopeFetcher(async_db, mock_esi_client)
            before_time = int(time.time())
            result = await fetcher.refresh_scope(scope, force_refresh=True)
            after_time = int(time.time())

            assert result.scan_status == "complete"
            # Fallback should set http_last_modified to current time
            assert result.http_last_modified is not None
            assert before_time <= result.http_last_modified <= after_time
            # Fallback should set http_expires to current time + TTL (15 mins = 900s)
            assert result.http_expires is not None
            expected_expires = result.http_last_modified + fetcher.DEFAULT_TTL_SECONDS
            assert result.http_expires == expected_expires
        finally:
            await async_db.close()


# =============================================================================
# MCP Tool Tests
# =============================================================================


class TestMarketScopeRefreshTool:
    """Tests for market_scope_refresh MCP tool."""

    @pytest.mark.asyncio
    async def test_tool_scope_not_found(self, temp_db, mock_esi_client):
        """Test tool returns error when scope not found."""
        sync_db, db_path = temp_db
        async_db = AsyncMarketDatabase(db_path)

        try:
            from aria_esi.mcp.market.tools_scope_refresh import register_scope_refresh_tools

            server = MagicMock()
            tools = {}

            def tool_decorator():
                def decorator(func):
                    tools[func.__name__] = func
                    return func

                return decorator

            server.tool = tool_decorator

            # Patch at module level where it's imported from
            with patch(
                "aria_esi.mcp.market.database_async.get_async_market_database"
            ) as mock_get_db:
                mock_get_db.return_value = async_db
                register_scope_refresh_tools(server)

                result = await tools["market_scope_refresh"]("nonexistent_scope")

                assert "code" in result
                assert result["code"] == "SCOPE_NOT_FOUND"
        finally:
            await async_db.close()

    @pytest.mark.asyncio
    async def test_tool_refresh_success(self, temp_db, mock_esi_client):
        """Test successful scope refresh via tool."""
        sync_db, db_path = temp_db
        async_db = AsyncMarketDatabase(db_path)

        try:
            # Create test scope
            scope, items = create_test_scope(
                sync_db,
                "tool_test_scope",
                "region",
                region_id=10000002,
            )

            # Mock ESI
            mock_esi_client.get_with_headers = MagicMock(
                return_value=make_esi_response(make_orders(34, [(100.0, 1000)], [(110.0, 500)]))
            )

            from aria_esi.mcp.market.tools_scope_refresh import register_scope_refresh_tools

            server = MagicMock()
            tools = {}

            def tool_decorator():
                def decorator(func):
                    tools[func.__name__] = func
                    return func

                return decorator

            server.tool = tool_decorator

            # Patch dependencies at module level
            with patch(
                "aria_esi.mcp.market.tools_scope_refresh.get_async_market_database"
            ) as mock_get_db:
                mock_get_db.return_value = async_db

                with patch(
                    "aria_esi.mcp.market.tools_scope_refresh.MarketScopeFetcher"
                ) as mock_fetcher_class:
                    # Create a mock fetcher that returns expected result
                    mock_result = MagicMock()
                    mock_result.model_dump.return_value = {
                        "scope_id": scope.scope_id,
                        "scope_name": "tool_test_scope",
                        "scope_type": "region",
                        "scan_status": "complete",
                        "items_refreshed": 2,
                        "errors": [],
                    }
                    mock_fetcher = MagicMock()
                    mock_fetcher.refresh_scope = AsyncMock(return_value=mock_result)
                    mock_fetcher_class.return_value = mock_fetcher

                    register_scope_refresh_tools(server)

                    result = await tools["market_scope_refresh"](
                        "tool_test_scope",
                        force_refresh=True,
                    )

            # Check it succeeded
            assert result.get("scan_status") == "complete"
            assert result.get("scope_name") == "tool_test_scope"
        finally:
            await async_db.close()
