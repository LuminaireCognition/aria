"""
Tests for aria_esi.store.market.database_async

Tests AsyncMarketDatabase against a real temp SQLite database.
Mirrors the sync test_database.py structure.
"""

import time
from pathlib import Path

import pytest
import pytest_asyncio

pytestmark = pytest.mark.asyncio

from aria_esi.store.market.database import (
    CachedAggregate,
    MarketScopePrice,
)
from aria_esi.store.market.database_async import (
    AsyncMarketDatabase,
    get_async_market_database,
    reset_async_market_database_sync,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def async_db(tmp_path: Path):
    """Create an AsyncMarketDatabase with temp path, yield, close."""
    db = AsyncMarketDatabase(db_path=tmp_path / "test_aria.db")
    yield db
    await db.close()


@pytest_asyncio.fixture
async def _seed_types(async_db: AsyncMarketDatabase):
    """Insert standard test types via raw SQL."""
    conn = await async_db._get_connection()
    await conn.executemany(
        """
        INSERT INTO types (type_id, type_name, type_name_lower)
        VALUES (?, ?, ?)
        """,
        [
            (34, "Tritanium", "tritanium"),
            (35, "Pyerite", "pyerite"),
            (36, "Mexallon", "mexallon"),
        ],
    )
    await conn.commit()


def _make_aggregate(type_id: int, region_id: int = 10000002, **overrides) -> CachedAggregate:
    """Factory for CachedAggregate with sensible defaults."""
    defaults = {
        "type_id": type_id,
        "region_id": region_id,
        "station_id": 60003760,
        "buy_weighted_avg": 3.95,
        "buy_max": 4.00,
        "buy_min": 3.50,
        "buy_stddev": 0.12,
        "buy_median": 3.97,
        "buy_volume": 50000000,
        "buy_order_count": 1542,
        "buy_percentile": 3.98,
        "sell_weighted_avg": 4.10,
        "sell_max": 5.00,
        "sell_min": 4.05,
        "sell_stddev": 0.15,
        "sell_median": 4.12,
        "sell_volume": 12000000,
        "sell_order_count": 892,
        "sell_percentile": 4.08,
        "updated_at": int(time.time()),
    }
    defaults.update(overrides)
    return CachedAggregate(**defaults)


async def _make_adhoc_scope(
    db: AsyncMarketDatabase, name: str, scope_type: str = "region", **kwargs
) -> "MarketScope":
    """Create a valid ad-hoc scope (satisfies CHECK constraint: source=esi + watchlist_id)."""
    if "watchlist_id" not in kwargs:
        wl = await db.create_watchlist(f"_wl_{name}")
        kwargs["watchlist_id"] = wl.watchlist_id
    kwargs.setdefault("source", "esi")
    return await db.create_scope(name, scope_type, **kwargs)


def _make_scope_price(scope_id: int, type_id: int, **overrides) -> MarketScopePrice:
    """Factory for MarketScopePrice with sensible defaults."""
    defaults = {
        "scope_id": scope_id,
        "type_id": type_id,
        "buy_max": 4.00,
        "buy_volume": 50000000,
        "sell_min": 4.05,
        "sell_volume": 12000000,
        "spread_pct": 1.25,
        "order_count_buy": 1542,
        "order_count_sell": 892,
        "updated_at": int(time.time()),
        "http_last_modified": None,
        "http_expires": None,
        "source": "esi",
        "coverage_type": "watchlist",
        "fetch_status": "complete",
    }
    defaults.update(overrides)
    return MarketScopePrice(**defaults)


# =============================================================================
# TestAsyncDatabaseInit
# =============================================================================


class TestAsyncDatabaseInit:
    """Tests for AsyncMarketDatabase initialization."""

    async def test_creates_db_file(self, tmp_path: Path):
        db = AsyncMarketDatabase(db_path=tmp_path / "test.db")
        await db._get_connection()
        assert (tmp_path / "test.db").exists()
        await db.close()

    async def test_creates_parent_dirs(self, tmp_path: Path):
        deep_path = tmp_path / "nested" / "dirs" / "aria.db"
        db = AsyncMarketDatabase(db_path=deep_path)
        await db._get_connection()
        assert deep_path.parent.exists()
        await db.close()

    async def test_schema_seeded_with_core_scopes(self, async_db: AsyncMarketDatabase):
        conn = await async_db._get_connection()
        async with conn.execute(
            "SELECT COUNT(*) FROM market_scopes WHERE is_core = 1"
        ) as cursor:
            count = (await cursor.fetchone())[0]
        assert count == 5


# =============================================================================
# TestTypeResolution
# =============================================================================


class TestTypeResolution:
    """Tests for type name resolution."""

    @pytest.mark.usefixtures("_seed_types")
    async def test_resolve_exact_match(self, async_db: AsyncMarketDatabase):
        result = await async_db.resolve_type_name("tritanium")
        assert result is not None
        assert result.type_id == 34
        assert result.type_name == "Tritanium"

    @pytest.mark.usefixtures("_seed_types")
    async def test_resolve_prefix_match(self, async_db: AsyncMarketDatabase):
        result = await async_db.resolve_type_name("Trit")
        assert result is not None
        assert result.type_id == 34

    async def test_resolve_contains_match(self, async_db: AsyncMarketDatabase):
        conn = await async_db._get_connection()
        await conn.execute(
            """
            INSERT INTO types (type_id, type_name, type_name_lower)
            VALUES (11578, 'Heavy Assault Missile Launcher II',
                    'heavy assault missile launcher ii')
            """
        )
        await conn.commit()

        result = await async_db.resolve_type_name("Assault Missile")
        assert result is not None
        assert result.type_id == 11578

    async def test_resolve_not_found(self, async_db: AsyncMarketDatabase):
        result = await async_db.resolve_type_name("NonexistentItem123")
        assert result is None

    @pytest.mark.usefixtures("_seed_types")
    async def test_resolve_type_id(self, async_db: AsyncMarketDatabase):
        result = await async_db.resolve_type_id(34)
        assert result is not None
        assert result.type_name == "Tritanium"

    async def test_resolve_type_id_not_found(self, async_db: AsyncMarketDatabase):
        result = await async_db.resolve_type_id(99999999)
        assert result is None

    @pytest.mark.usefixtures("_seed_types")
    async def test_resolve_type_ids_batch(self, async_db: AsyncMarketDatabase):
        result = await async_db.resolve_type_ids_batch([34, 35, 99999])
        assert result[34] == "Tritanium"
        assert result[35] == "Pyerite"
        assert 99999 not in result

    async def test_resolve_type_ids_batch_empty(self, async_db: AsyncMarketDatabase):
        result = await async_db.resolve_type_ids_batch([])
        assert result == {}

    @pytest.mark.usefixtures("_seed_types")
    async def test_find_suggestions(self, async_db: AsyncMarketDatabase):
        suggestions = await async_db.find_type_suggestions("tri", limit=5)
        assert "Tritanium" in suggestions

    @pytest.mark.usefixtures("_seed_types")
    async def test_batch_resolve_names(self, async_db: AsyncMarketDatabase):
        result = await async_db.batch_resolve_names(["Tritanium", "Unknown"])
        assert result["Tritanium"] is not None
        assert result["Tritanium"].type_id == 34
        assert result["Unknown"] is None


# =============================================================================
# TestAggregates
# =============================================================================


class TestAggregates:
    """Tests for price aggregate storage and retrieval."""

    async def test_save_and_get_aggregate(self, async_db: AsyncMarketDatabase):
        agg = _make_aggregate(34)
        await async_db.save_aggregate(agg)

        result = await async_db.get_aggregate(34, 10000002)
        assert result is not None
        assert result.type_id == 34
        assert result.buy_max == 4.00
        assert result.sell_min == 4.05

    async def test_get_aggregate_stale(self, async_db: AsyncMarketDatabase):
        old_time = int(time.time()) - 10000
        agg = _make_aggregate(34, updated_at=old_time)
        await async_db.save_aggregate(agg)

        result = await async_db.get_aggregate(34, 10000002, max_age_seconds=900)
        assert result is None

    async def test_get_aggregates_batch(self, async_db: AsyncMarketDatabase):
        for tid in [34, 35, 36]:
            await async_db.save_aggregate(_make_aggregate(tid))

        result = await async_db.get_aggregates_batch([34, 35, 36], 10000002)
        assert len(result) == 3
        assert 34 in result
        assert 35 in result
        assert 36 in result

    async def test_get_aggregates_batch_empty(self, async_db: AsyncMarketDatabase):
        result = await async_db.get_aggregates_batch([], 10000002)
        assert result == {}

    async def test_save_aggregates_batch(self, async_db: AsyncMarketDatabase):
        aggs = [_make_aggregate(tid) for tid in [34, 35, 36]]
        count = await async_db.save_aggregates_batch(aggs)
        assert count == 3

        result = await async_db.get_aggregates_batch([34, 35, 36], 10000002)
        assert len(result) == 3

    async def test_save_aggregates_batch_empty(self, async_db: AsyncMarketDatabase):
        count = await async_db.save_aggregates_batch([])
        assert count == 0


# =============================================================================
# TestHistoryCache
# =============================================================================


class TestHistoryCache:
    """Tests for history cache storage and retrieval."""

    async def test_save_and_get_history(self, async_db: AsyncMarketDatabase):
        await async_db.save_history_cache(34, 10000002, 1000000, 5000000.0, 2.5)

        result = await async_db.get_history_cache(34, 10000002)
        assert result is not None
        assert result.type_id == 34
        assert result.region_id == 10000002
        assert result.avg_daily_volume == 1000000
        assert result.avg_daily_isk == 5000000.0
        assert result.volatility_pct == 2.5

    async def test_get_history_stale(self, async_db: AsyncMarketDatabase):
        await async_db.save_history_cache(34, 10000002, 1000000)

        # Request with 1 second max age (will be stale immediately for any real data)
        result = await async_db.get_history_cache(34, 10000002, max_age_seconds=0)
        assert result is None

    async def test_get_history_batch(self, async_db: AsyncMarketDatabase):
        for tid in [34, 35, 36]:
            await async_db.save_history_cache(tid, 10000002, 1000000)

        result = await async_db.get_history_cache_batch([34, 35, 36], 10000002)
        assert len(result) == 3
        assert 34 in result
        assert 36 in result

    async def test_get_history_batch_empty(self, async_db: AsyncMarketDatabase):
        result = await async_db.get_history_cache_batch([], 10000002)
        assert result == {}

    async def test_save_history_batch(self, async_db: AsyncMarketDatabase):
        entries = [
            (34, 10000002, 1000000, 5000000.0, 2.5),
            (35, 10000002, 2000000, 8000000.0, 3.1),
        ]
        count = await async_db.save_history_cache_batch(entries)
        assert count == 2

        result = await async_db.get_history_cache_batch([34, 35], 10000002)
        assert len(result) == 2

    async def test_save_history_batch_empty(self, async_db: AsyncMarketDatabase):
        count = await async_db.save_history_cache_batch([])
        assert count == 0


# =============================================================================
# TestWatchlists
# =============================================================================


class TestWatchlists:
    """Tests for watchlist CRUD operations."""

    async def test_create_watchlist(self, async_db: AsyncMarketDatabase):
        wl = await async_db.create_watchlist("ores")
        assert wl.name == "ores"
        assert wl.watchlist_id > 0
        assert wl.owner_character_id is None

    async def test_get_watchlist_by_name(self, async_db: AsyncMarketDatabase):
        await async_db.create_watchlist("ores")
        result = await async_db.get_watchlist("ores")
        assert result is not None
        assert result.name == "ores"

    async def test_get_watchlist_by_name_with_owner(self, async_db: AsyncMarketDatabase):
        await async_db.create_watchlist("ores", owner_character_id=12345)
        result = await async_db.get_watchlist("ores", owner_character_id=12345)
        assert result is not None
        assert result.owner_character_id == 12345

        # Global lookup should not find owner-specific watchlist
        result_global = await async_db.get_watchlist("ores")
        assert result_global is None

    async def test_get_watchlist_by_id(self, async_db: AsyncMarketDatabase):
        wl = await async_db.create_watchlist("ores")
        result = await async_db.get_watchlist_by_id(wl.watchlist_id)
        assert result is not None
        assert result.name == "ores"

    async def test_get_watchlist_not_found(self, async_db: AsyncMarketDatabase):
        result = await async_db.get_watchlist("nonexistent")
        assert result is None

    async def test_list_watchlists_global(self, async_db: AsyncMarketDatabase):
        await async_db.create_watchlist("alpha")
        await async_db.create_watchlist("beta")
        await async_db.create_watchlist("gamma", owner_character_id=999)

        result = await async_db.list_watchlists()
        names = [w.name for w in result]
        assert "alpha" in names
        assert "beta" in names
        assert "gamma" not in names

    async def test_list_watchlists_owner(self, async_db: AsyncMarketDatabase):
        await async_db.create_watchlist("global_list")
        await async_db.create_watchlist("my_list", owner_character_id=999)

        result = await async_db.list_watchlists(owner_character_id=999)
        names = [w.name for w in result]
        assert "my_list" in names
        assert "global_list" not in names

    async def test_delete_watchlist(self, async_db: AsyncMarketDatabase):
        wl = await async_db.create_watchlist("doomed")
        assert await async_db.delete_watchlist(wl.watchlist_id) is True
        assert await async_db.get_watchlist("doomed") is None

    async def test_delete_watchlist_not_found(self, async_db: AsyncMarketDatabase):
        assert await async_db.delete_watchlist(99999) is False


# =============================================================================
# TestWatchlistItems
# =============================================================================


class TestWatchlistItems:
    """Tests for watchlist item operations."""

    async def test_add_and_get_items(self, async_db: AsyncMarketDatabase):
        wl = await async_db.create_watchlist("ores")
        await async_db.add_watchlist_item(wl.watchlist_id, 34)
        await async_db.add_watchlist_item(wl.watchlist_id, 35)

        items = await async_db.get_watchlist_items(wl.watchlist_id)
        type_ids = [i.type_id for i in items]
        assert 34 in type_ids
        assert 35 in type_ids

    async def test_remove_item(self, async_db: AsyncMarketDatabase):
        wl = await async_db.create_watchlist("ores")
        await async_db.add_watchlist_item(wl.watchlist_id, 34)

        assert await async_db.remove_watchlist_item(wl.watchlist_id, 34) is True
        items = await async_db.get_watchlist_items(wl.watchlist_id)
        assert len(items) == 0

    async def test_remove_item_not_found(self, async_db: AsyncMarketDatabase):
        wl = await async_db.create_watchlist("ores")
        assert await async_db.remove_watchlist_item(wl.watchlist_id, 99999) is False

    async def test_get_items_for_scope(self, async_db: AsyncMarketDatabase):
        wl = await async_db.create_watchlist("ores")
        await async_db.add_watchlist_item(wl.watchlist_id, 34)
        await async_db.add_watchlist_item(wl.watchlist_id, 35)

        scope = await _make_adhoc_scope(
            async_db,
            "test-scope",
            "station",
            station_id=60003760,
            watchlist_id=wl.watchlist_id,
        )

        items = await async_db.get_watchlist_items_for_scope(scope.scope_id)
        type_ids = [i.type_id for i in items]
        assert 34 in type_ids
        assert 35 in type_ids

    async def test_get_items_for_scope_no_watchlist(self, async_db: AsyncMarketDatabase):
        # Use a core scope (which has no watchlist) to test empty case
        jita = await async_db.get_scope("Jita")
        assert jita is not None
        items = await async_db.get_watchlist_items_for_scope(jita.scope_id)
        assert items == []


# =============================================================================
# TestMarketScopes
# =============================================================================


class TestMarketScopes:
    """Tests for market scope operations."""

    async def test_create_scope(self, async_db: AsyncMarketDatabase):
        scope = await _make_adhoc_scope(
            async_db,
            "My Station",
            "station",
            station_id=60003760,
            parent_region_id=10000002,
        )
        assert scope.scope_name == "My Station"
        assert scope.scope_type == "station"
        assert scope.station_id == 60003760
        assert scope.is_core is False
        assert scope.last_scan_status == "new"

    async def test_get_scope_by_name(self, async_db: AsyncMarketDatabase):
        await _make_adhoc_scope(async_db, "TestScope", "region", region_id=10000002)
        result = await async_db.get_scope("TestScope")
        assert result is not None
        assert result.scope_name == "TestScope"

    async def test_get_scope_by_name_with_owner(self, async_db: AsyncMarketDatabase):
        await _make_adhoc_scope(
            async_db, "MyScope", "region", region_id=10000002, owner_character_id=12345
        )
        result = await async_db.get_scope("MyScope", owner_character_id=12345)
        assert result is not None
        assert result.owner_character_id == 12345

        result_global = await async_db.get_scope("MyScope")
        assert result_global is None

    async def test_get_scope_by_id(self, async_db: AsyncMarketDatabase):
        scope = await _make_adhoc_scope(async_db, "IdScope", "region", region_id=10000002)
        result = await async_db.get_scope_by_id(scope.scope_id)
        assert result is not None
        assert result.scope_name == "IdScope"

    async def test_list_scopes_global_with_core(self, async_db: AsyncMarketDatabase):
        await _make_adhoc_scope(async_db, "CustomGlobal", "region", region_id=10000099)
        scopes = await async_db.list_scopes(include_core=True)
        names = [s.scope_name for s in scopes]
        assert "Jita" in names
        assert "Amarr" in names
        assert "CustomGlobal" in names

    async def test_list_scopes_global_no_core(self, async_db: AsyncMarketDatabase):
        await _make_adhoc_scope(async_db, "CustomGlobal", "region", region_id=10000099)
        scopes = await async_db.list_scopes(include_core=False)
        names = [s.scope_name for s in scopes]
        assert "Jita" not in names
        assert "CustomGlobal" in names

    async def test_list_scopes_owner_with_global(self, async_db: AsyncMarketDatabase):
        await _make_adhoc_scope(
            async_db, "OwnerScope", "region", region_id=10000099, owner_character_id=999
        )
        scopes = await async_db.list_scopes(owner_character_id=999, include_core=True, include_global=True)
        names = [s.scope_name for s in scopes]
        assert "OwnerScope" in names
        assert "Jita" in names

    async def test_list_scopes_owner_only(self, async_db: AsyncMarketDatabase):
        await _make_adhoc_scope(
            async_db, "OwnerScope", "region", region_id=10000099, owner_character_id=999
        )
        scopes = await async_db.list_scopes(owner_character_id=999, include_global=False)
        names = [s.scope_name for s in scopes]
        assert "OwnerScope" in names
        assert "Jita" not in names

    async def test_delete_scope(self, async_db: AsyncMarketDatabase):
        scope = await _make_adhoc_scope(async_db, "Deletable", "region", region_id=10000099)
        assert await async_db.delete_scope(scope.scope_id) is True
        assert await async_db.get_scope_by_id(scope.scope_id) is None

    async def test_delete_core_scope_raises(self, async_db: AsyncMarketDatabase):
        jita = await async_db.get_scope("Jita")
        assert jita is not None
        with pytest.raises(ValueError, match="Cannot delete core hub scope"):
            await async_db.delete_scope(jita.scope_id)

    async def test_resolve_scopes_owner_shadows_global(self, async_db: AsyncMarketDatabase):
        # Create global scope named "MyHub"
        wl_global = await async_db.create_watchlist("wl_global_hub")
        await async_db.create_scope(
            "MyHub", "region", region_id=10000002,
            source="esi", watchlist_id=wl_global.watchlist_id,
        )
        # Create owner scope with same name (needs its own watchlist)
        wl_owner = await async_db.create_watchlist("wl_owner_hub", owner_character_id=999)
        await async_db.create_scope(
            "MyHub", "region", region_id=10000099, owner_character_id=999,
            source="esi", watchlist_id=wl_owner.watchlist_id,
        )

        scopes = await async_db.resolve_scopes(["MyHub"], owner_character_id=999)
        assert len(scopes) == 1
        assert scopes[0].owner_character_id == 999
        assert scopes[0].region_id == 10000099

    async def test_resolve_scopes_empty(self, async_db: AsyncMarketDatabase):
        result = await async_db.resolve_scopes([])
        assert result == []

    async def test_update_scope_scan_status(self, async_db: AsyncMarketDatabase):
        scope = await _make_adhoc_scope(async_db, "ScanMe", "region", region_id=10000002)
        now = int(time.time())

        updated = await async_db.update_scope_scan_status(scope.scope_id, "complete", scanned_at=now)
        assert updated is True

        refreshed = await async_db.get_scope_by_id(scope.scope_id)
        assert refreshed is not None
        assert refreshed.last_scan_status == "complete"
        assert refreshed.last_scanned_at == now


# =============================================================================
# TestScopePrices
# =============================================================================


class TestScopePrices:
    """Tests for market scope price operations."""

    async def test_upsert_and_get_scope_price(self, async_db: AsyncMarketDatabase):
        scope = await _make_adhoc_scope(async_db, "PriceHub", "region", region_id=10000002)
        price = _make_scope_price(scope.scope_id, 34)

        await async_db.upsert_scope_price(price)
        result = await async_db.get_scope_price(scope.scope_id, 34)
        assert result is not None
        assert result.buy_max == 4.00
        assert result.sell_min == 4.05

    async def test_upsert_scope_prices_batch(self, async_db: AsyncMarketDatabase):
        scope = await _make_adhoc_scope(async_db, "BatchHub", "region", region_id=10000002)
        prices = [_make_scope_price(scope.scope_id, tid) for tid in [34, 35, 36]]

        count = await async_db.upsert_scope_prices_batch(prices)
        assert count == 3

    async def test_get_scope_prices(self, async_db: AsyncMarketDatabase):
        scope = await _make_adhoc_scope(async_db, "AllPrices", "region", region_id=10000002)
        for tid in [34, 35]:
            await async_db.upsert_scope_price(_make_scope_price(scope.scope_id, tid))

        prices = await async_db.get_scope_prices(scope.scope_id)
        assert len(prices) == 2

    async def test_get_scope_prices_with_max_age(self, async_db: AsyncMarketDatabase):
        scope = await _make_adhoc_scope(async_db, "AgePrices", "region", region_id=10000002)
        old_price = _make_scope_price(scope.scope_id, 34, updated_at=int(time.time()) - 10000)
        fresh_price = _make_scope_price(scope.scope_id, 35)

        await async_db.upsert_scope_price(old_price)
        await async_db.upsert_scope_price(fresh_price)

        prices = await async_db.get_scope_prices(scope.scope_id, max_age_seconds=900)
        assert len(prices) == 1
        assert prices[0].type_id == 35

    @pytest.mark.usefixtures("_seed_types")
    async def test_get_scope_prices_for_arbitrage(self, async_db: AsyncMarketDatabase):
        scope = await _make_adhoc_scope(async_db, "ArbHub", "region", region_id=10000002)
        price = _make_scope_price(scope.scope_id, 34)
        await async_db.upsert_scope_price(price)

        rows = await async_db.get_scope_prices_for_arbitrage([scope.scope_id])
        assert len(rows) == 1
        assert rows[0]["type_name"] == "Tritanium"
        assert rows[0]["scope_name"] == "ArbHub"

    async def test_clear_scope_prices(self, async_db: AsyncMarketDatabase):
        scope = await _make_adhoc_scope(async_db, "ClearHub", "region", region_id=10000002)
        for tid in [34, 35, 36]:
            await async_db.upsert_scope_price(_make_scope_price(scope.scope_id, tid))

        deleted = await async_db.clear_scope_prices(scope.scope_id)
        assert deleted == 3

        remaining = await async_db.get_scope_prices(scope.scope_id)
        assert len(remaining) == 0


# =============================================================================
# TestDatabaseStats
# =============================================================================


class TestDatabaseStats:
    """Tests for database statistics."""

    async def test_stats_empty(self, async_db: AsyncMarketDatabase):
        stats = await async_db.get_stats()
        assert stats["type_count"] == 0
        assert stats["aggregate_count"] == 0

    @pytest.mark.usefixtures("_seed_types")
    async def test_stats_with_data(self, async_db: AsyncMarketDatabase):
        await async_db.save_aggregate(_make_aggregate(34))

        stats = await async_db.get_stats()
        assert stats["type_count"] == 3
        assert stats["aggregate_count"] == 1
        assert stats["database_size_mb"] > 0


# =============================================================================
# TestSingleton
# =============================================================================


class TestSingleton:
    """Tests for singleton management."""

    async def test_get_returns_same_instance(self, monkeypatch, tmp_path: Path):
        reset_async_market_database_sync()
        monkeypatch.setenv("ARIA_DB", str(tmp_path / "singleton.db"))
        # Reset settings cache so new ARIA_DB takes effect
        from aria_esi.core.config import reset_settings

        reset_settings()

        try:
            db1 = await get_async_market_database()
            db2 = await get_async_market_database()
            assert db1 is db2
        finally:
            reset_async_market_database_sync()
            reset_settings()

    async def test_reset_clears_singleton(self, monkeypatch, tmp_path: Path):
        reset_async_market_database_sync()
        monkeypatch.setenv("ARIA_DB", str(tmp_path / "singleton2.db"))
        from aria_esi.core.config import reset_settings

        reset_settings()

        try:
            db1 = await get_async_market_database()
            reset_async_market_database_sync()
            db2 = await get_async_market_database()
            assert db1 is not db2
        finally:
            reset_async_market_database_sync()
            reset_settings()
