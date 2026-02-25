"""
Tests for Hub-Centric Market Engine Ad-hoc Schema.

Tests cover:
- Watchlist CRUD operations and constraints
- Market scope CRUD operations and constraints
- Market scope prices CRUD operations and constraints
- Core hub seeding
"""

from __future__ import annotations

import sqlite3
import tempfile
import time
from pathlib import Path

import pytest

from aria_esi.mcp.market.database import (
    MarketDatabase,
    MarketScopePrice,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = MarketDatabase(db_path)
        yield db
        db.close()


# =============================================================================
# Watchlist Schema Tests
# =============================================================================


class TestWatchlistSchema:
    """Tests for watchlist CRUD operations and constraints."""

    def test_create_watchlist(self, temp_db: MarketDatabase):
        """Test creating a watchlist."""
        watchlist = temp_db.create_watchlist("Test Watchlist")

        assert watchlist.watchlist_id is not None
        assert watchlist.name == "Test Watchlist"
        assert watchlist.owner_character_id is None
        assert watchlist.created_at > 0

    def test_create_watchlist_with_owner(self, temp_db: MarketDatabase):
        """Test creating a watchlist with owner."""
        watchlist = temp_db.create_watchlist("My List", owner_character_id=12345)

        assert watchlist.owner_character_id == 12345

    def test_get_watchlist_global(self, temp_db: MarketDatabase):
        """Test getting a global watchlist."""
        created = temp_db.create_watchlist("Global List")
        retrieved = temp_db.get_watchlist("Global List")

        assert retrieved is not None
        assert retrieved.watchlist_id == created.watchlist_id
        assert retrieved.name == "Global List"

    def test_get_watchlist_with_owner(self, temp_db: MarketDatabase):
        """Test getting a watchlist with owner."""
        created = temp_db.create_watchlist("My List", owner_character_id=12345)
        retrieved = temp_db.get_watchlist("My List", owner_character_id=12345)

        assert retrieved is not None
        assert retrieved.watchlist_id == created.watchlist_id

    def test_get_watchlist_not_found(self, temp_db: MarketDatabase):
        """Test getting a non-existent watchlist."""
        result = temp_db.get_watchlist("Does Not Exist")
        assert result is None

    def test_get_watchlist_by_id(self, temp_db: MarketDatabase):
        """Test getting a watchlist by ID."""
        created = temp_db.create_watchlist("Test")
        retrieved = temp_db.get_watchlist_by_id(created.watchlist_id)

        assert retrieved is not None
        assert retrieved.name == "Test"

    def test_list_watchlists_global(self, temp_db: MarketDatabase):
        """Test listing global watchlists."""
        temp_db.create_watchlist("Alpha")
        temp_db.create_watchlist("Beta")
        temp_db.create_watchlist("Gamma", owner_character_id=12345)

        global_lists = temp_db.list_watchlists()

        assert len(global_lists) == 2
        names = [w.name for w in global_lists]
        assert "Alpha" in names
        assert "Beta" in names
        assert "Gamma" not in names

    def test_list_watchlists_owned(self, temp_db: MarketDatabase):
        """Test listing owned watchlists."""
        temp_db.create_watchlist("Global")
        temp_db.create_watchlist("Mine", owner_character_id=12345)
        temp_db.create_watchlist("Also Mine", owner_character_id=12345)

        owned_lists = temp_db.list_watchlists(owner_character_id=12345)

        assert len(owned_lists) == 2
        names = [w.name for w in owned_lists]
        assert "Mine" in names
        assert "Also Mine" in names
        assert "Global" not in names

    def test_delete_watchlist(self, temp_db: MarketDatabase):
        """Test deleting a watchlist."""
        watchlist = temp_db.create_watchlist("To Delete")
        result = temp_db.delete_watchlist(watchlist.watchlist_id)

        assert result is True
        assert temp_db.get_watchlist_by_id(watchlist.watchlist_id) is None

    def test_delete_watchlist_not_found(self, temp_db: MarketDatabase):
        """Test deleting a non-existent watchlist."""
        result = temp_db.delete_watchlist(99999)
        assert result is False

    def test_unique_constraint_global(self, temp_db: MarketDatabase):
        """Test that duplicate global names are rejected."""
        temp_db.create_watchlist("Unique Name")

        with pytest.raises(sqlite3.IntegrityError):
            temp_db.create_watchlist("Unique Name")

    def test_unique_constraint_same_owner(self, temp_db: MarketDatabase):
        """Test that duplicate names for same owner are rejected."""
        temp_db.create_watchlist("My List", owner_character_id=12345)

        with pytest.raises(sqlite3.IntegrityError):
            temp_db.create_watchlist("My List", owner_character_id=12345)

    def test_same_name_different_owners_allowed(self, temp_db: MarketDatabase):
        """Test that same name with different owners is allowed."""
        w1 = temp_db.create_watchlist("Shared Name", owner_character_id=12345)
        w2 = temp_db.create_watchlist("Shared Name", owner_character_id=67890)
        w3 = temp_db.create_watchlist("Shared Name")  # Global

        assert w1.watchlist_id != w2.watchlist_id != w3.watchlist_id

    def test_add_watchlist_item(self, temp_db: MarketDatabase):
        """Test adding an item to a watchlist."""
        watchlist = temp_db.create_watchlist("Test")
        item = temp_db.add_watchlist_item(watchlist.watchlist_id, type_id=34)

        assert item.watchlist_id == watchlist.watchlist_id
        assert item.type_id == 34
        assert item.added_at > 0

    def test_get_watchlist_items(self, temp_db: MarketDatabase):
        """Test getting all items in a watchlist."""
        watchlist = temp_db.create_watchlist("Test")
        temp_db.add_watchlist_item(watchlist.watchlist_id, type_id=34)
        temp_db.add_watchlist_item(watchlist.watchlist_id, type_id=35)

        items = temp_db.get_watchlist_items(watchlist.watchlist_id)

        assert len(items) == 2
        type_ids = [i.type_id for i in items]
        assert 34 in type_ids
        assert 35 in type_ids

    def test_remove_watchlist_item(self, temp_db: MarketDatabase):
        """Test removing an item from a watchlist."""
        watchlist = temp_db.create_watchlist("Test")
        temp_db.add_watchlist_item(watchlist.watchlist_id, type_id=34)

        result = temp_db.remove_watchlist_item(watchlist.watchlist_id, type_id=34)
        assert result is True

        items = temp_db.get_watchlist_items(watchlist.watchlist_id)
        assert len(items) == 0

    def test_remove_watchlist_item_not_found(self, temp_db: MarketDatabase):
        """Test removing a non-existent item."""
        watchlist = temp_db.create_watchlist("Test")
        result = temp_db.remove_watchlist_item(watchlist.watchlist_id, type_id=99999)
        assert result is False

    def test_cascade_delete_watchlist_items(self, temp_db: MarketDatabase):
        """Test that deleting a watchlist cascades to items."""
        watchlist = temp_db.create_watchlist("Test")
        temp_db.add_watchlist_item(watchlist.watchlist_id, type_id=34)
        temp_db.add_watchlist_item(watchlist.watchlist_id, type_id=35)

        temp_db.delete_watchlist(watchlist.watchlist_id)

        # Verify items are gone by trying to get them (should be empty)
        items = temp_db.get_watchlist_items(watchlist.watchlist_id)
        assert len(items) == 0


# =============================================================================
# Market Scope Schema Tests
# =============================================================================


class TestMarketScopeSchema:
    """Tests for market scope CRUD operations and constraints."""

    def test_core_hub_seeding(self, temp_db: MarketDatabase):
        """Test that core hubs are seeded on initialization."""
        scopes = temp_db.list_scopes(include_core=True)

        core_scopes = [s for s in scopes if s.is_core]
        assert len(core_scopes) == 5

        names = {s.scope_name for s in core_scopes}
        assert names == {"Jita", "Amarr", "Dodixie", "Rens", "Hek"}

    def test_core_hub_properties(self, temp_db: MarketDatabase):
        """Test that core hubs have correct properties."""
        jita = temp_db.get_scope("Jita")

        assert jita is not None
        assert jita.is_core is True
        assert jita.scope_type == "hub_region"
        assert jita.source == "fuzzwork"
        assert jita.region_id == 10000002
        assert jita.watchlist_id is None
        assert jita.owner_character_id is None

    def test_create_adhoc_region_scope(self, temp_db: MarketDatabase):
        """Test creating an ad-hoc region scope."""
        watchlist = temp_db.create_watchlist("Test Items")
        scope = temp_db.create_scope(
            scope_name="Everyshore",
            scope_type="region",
            region_id=10000037,
            watchlist_id=watchlist.watchlist_id,
        )

        assert scope.scope_id is not None
        assert scope.scope_name == "Everyshore"
        assert scope.scope_type == "region"
        assert scope.is_core is False
        assert scope.source == "esi"
        assert scope.watchlist_id == watchlist.watchlist_id

    def test_create_adhoc_station_scope(self, temp_db: MarketDatabase):
        """Test creating an ad-hoc station scope."""
        watchlist = temp_db.create_watchlist("Test Items")
        scope = temp_db.create_scope(
            scope_name="My Station",
            scope_type="station",
            station_id=60003760,
            parent_region_id=10000002,
            watchlist_id=watchlist.watchlist_id,
        )

        assert scope.scope_type == "station"
        assert scope.station_id == 60003760
        assert scope.parent_region_id == 10000002

    def test_create_adhoc_structure_scope(self, temp_db: MarketDatabase):
        """Test creating an ad-hoc structure scope."""
        watchlist = temp_db.create_watchlist("Test Items")
        scope = temp_db.create_scope(
            scope_name="My Structure",
            scope_type="structure",
            structure_id=1234567890,
            parent_region_id=10000002,
            watchlist_id=watchlist.watchlist_id,
        )

        assert scope.scope_type == "structure"
        assert scope.structure_id == 1234567890

    def test_get_scope_by_id(self, temp_db: MarketDatabase):
        """Test getting a scope by ID."""
        jita = temp_db.get_scope("Jita")
        retrieved = temp_db.get_scope_by_id(jita.scope_id)

        assert retrieved is not None
        assert retrieved.scope_name == "Jita"

    def test_list_scopes_exclude_core(self, temp_db: MarketDatabase):
        """Test listing scopes without core hubs."""
        watchlist = temp_db.create_watchlist("Test")
        temp_db.create_scope(
            scope_name="Custom",
            scope_type="region",
            region_id=10000037,
            watchlist_id=watchlist.watchlist_id,
        )

        scopes = temp_db.list_scopes(include_core=False)

        assert len(scopes) == 1
        assert scopes[0].scope_name == "Custom"

    def test_delete_scope(self, temp_db: MarketDatabase):
        """Test deleting a scope."""
        watchlist = temp_db.create_watchlist("Test")
        scope = temp_db.create_scope(
            scope_name="ToDelete",
            scope_type="region",
            region_id=10000037,
            watchlist_id=watchlist.watchlist_id,
        )

        result = temp_db.delete_scope(scope.scope_id)
        assert result is True
        assert temp_db.get_scope_by_id(scope.scope_id) is None

    def test_update_scope_scan_status(self, temp_db: MarketDatabase):
        """Test updating scope scan status."""
        watchlist = temp_db.create_watchlist("Test")
        scope = temp_db.create_scope(
            scope_name="Test",
            scope_type="region",
            region_id=10000037,
            watchlist_id=watchlist.watchlist_id,
        )

        assert scope.last_scan_status == "new"
        assert scope.last_scanned_at is None

        now = int(time.time())
        temp_db.update_scope_scan_status(scope.scope_id, "complete", now)

        updated = temp_db.get_scope_by_id(scope.scope_id)
        assert updated.last_scan_status == "complete"
        assert updated.last_scanned_at == now

    def test_location_exclusivity_region(self, temp_db: MarketDatabase):
        """Test that region scope requires only region_id."""
        watchlist = temp_db.create_watchlist("Test")

        # This should fail - station_id provided for region type
        with pytest.raises(sqlite3.IntegrityError):
            temp_db.create_scope(
                scope_name="Invalid",
                scope_type="region",
                region_id=10000037,
                station_id=60003760,  # Not allowed for region type
                watchlist_id=watchlist.watchlist_id,
            )

    def test_location_exclusivity_station(self, temp_db: MarketDatabase):
        """Test that station scope requires only station_id."""
        watchlist = temp_db.create_watchlist("Test")

        # This should fail - region_id provided for station type
        with pytest.raises(sqlite3.IntegrityError):
            temp_db.create_scope(
                scope_name="Invalid",
                scope_type="station",
                region_id=10000037,  # Not allowed for station type
                station_id=60003760,
                watchlist_id=watchlist.watchlist_id,
            )

    def test_core_adhoc_rule_core_requires_fuzzwork(self, temp_db: MarketDatabase):
        """Test that core scopes require fuzzwork source."""
        # This should fail - core scope with ESI source
        with pytest.raises(sqlite3.IntegrityError):
            temp_db.create_scope(
                scope_name="BadCore",
                scope_type="hub_region",
                region_id=10000002,
                is_core=True,
                source="esi",  # Core must use fuzzwork
            )

    def test_core_adhoc_rule_adhoc_requires_watchlist(self, temp_db: MarketDatabase):
        """Test that ad-hoc scopes require a watchlist."""
        # This should fail - ad-hoc scope without watchlist
        with pytest.raises(sqlite3.IntegrityError):
            temp_db.create_scope(
                scope_name="BadAdhoc",
                scope_type="region",
                region_id=10000037,
                # No watchlist_id - required for ad-hoc
            )

    def test_scope_unique_constraint_global(self, temp_db: MarketDatabase):
        """Test that duplicate global scope names are rejected."""
        watchlist = temp_db.create_watchlist("Test")
        temp_db.create_scope(
            scope_name="MyScope",
            scope_type="region",
            region_id=10000037,
            watchlist_id=watchlist.watchlist_id,
        )

        with pytest.raises(sqlite3.IntegrityError):
            temp_db.create_scope(
                scope_name="MyScope",
                scope_type="region",
                region_id=10000038,
                watchlist_id=watchlist.watchlist_id,
            )

    def test_scope_same_name_different_owners(self, temp_db: MarketDatabase):
        """Test that same scope name with different owners is allowed."""
        watchlist = temp_db.create_watchlist("Test")
        s1 = temp_db.create_scope(
            scope_name="MyScope",
            scope_type="region",
            region_id=10000037,
            watchlist_id=watchlist.watchlist_id,
            owner_character_id=12345,
        )
        s2 = temp_db.create_scope(
            scope_name="MyScope",
            scope_type="region",
            region_id=10000037,
            watchlist_id=watchlist.watchlist_id,
            owner_character_id=67890,
        )

        assert s1.scope_id != s2.scope_id

    def test_invalid_scan_status_rejected(self, temp_db: MarketDatabase):
        """Test that invalid scan status is rejected."""
        watchlist = temp_db.create_watchlist("Test")
        scope = temp_db.create_scope(
            scope_name="Test",
            scope_type="region",
            region_id=10000037,
            watchlist_id=watchlist.watchlist_id,
        )

        # Try to set invalid status via direct SQL
        conn = temp_db._get_connection()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "UPDATE market_scopes SET last_scan_status = ? WHERE scope_id = ?",
                ("invalid_status", scope.scope_id),
            )
            conn.commit()


# =============================================================================
# Market Scope Prices Schema Tests
# =============================================================================


class TestMarketScopePricesSchema:
    """Tests for market scope prices CRUD operations and constraints."""

    def test_upsert_scope_price(self, temp_db: MarketDatabase):
        """Test inserting a scope price."""
        watchlist = temp_db.create_watchlist("Test")
        scope = temp_db.create_scope(
            scope_name="Test",
            scope_type="region",
            region_id=10000037,
            watchlist_id=watchlist.watchlist_id,
        )

        now = int(time.time())
        price = MarketScopePrice(
            scope_id=scope.scope_id,
            type_id=34,
            buy_max=5.5,
            buy_volume=1000000,
            sell_min=5.0,
            sell_volume=2000000,
            spread_pct=10.0,
            order_count_buy=100,
            order_count_sell=150,
            updated_at=now,
            http_last_modified=now - 60,
            http_expires=now + 300,
            source="esi",
            coverage_type="watchlist",
            fetch_status="complete",
        )

        temp_db.upsert_scope_price(price)

        retrieved = temp_db.get_scope_price(scope.scope_id, 34)
        assert retrieved is not None
        assert retrieved.buy_max == 5.5
        assert retrieved.sell_min == 5.0
        assert retrieved.fetch_status == "complete"

    def test_upsert_scope_price_update(self, temp_db: MarketDatabase):
        """Test updating an existing scope price."""
        watchlist = temp_db.create_watchlist("Test")
        scope = temp_db.create_scope(
            scope_name="Test",
            scope_type="region",
            region_id=10000037,
            watchlist_id=watchlist.watchlist_id,
        )

        now = int(time.time())
        price1 = MarketScopePrice(
            scope_id=scope.scope_id,
            type_id=34,
            buy_max=5.5,
            buy_volume=1000000,
            sell_min=5.0,
            sell_volume=2000000,
            spread_pct=10.0,
            order_count_buy=100,
            order_count_sell=150,
            updated_at=now,
            http_last_modified=now,
            http_expires=now + 300,
            source="esi",
            coverage_type="watchlist",
            fetch_status="complete",
        )
        temp_db.upsert_scope_price(price1)

        # Update with new price
        price2 = MarketScopePrice(
            scope_id=scope.scope_id,
            type_id=34,
            buy_max=6.0,
            buy_volume=1500000,
            sell_min=5.5,
            sell_volume=2500000,
            spread_pct=9.0,
            order_count_buy=120,
            order_count_sell=180,
            updated_at=now + 60,
            http_last_modified=now + 60,
            http_expires=now + 360,
            source="esi",
            coverage_type="watchlist",
            fetch_status="complete",
        )
        temp_db.upsert_scope_price(price2)

        retrieved = temp_db.get_scope_price(scope.scope_id, 34)
        assert retrieved.buy_max == 6.0
        assert retrieved.sell_min == 5.5

    def test_upsert_scope_prices_batch(self, temp_db: MarketDatabase):
        """Test batch inserting scope prices."""
        watchlist = temp_db.create_watchlist("Test")
        scope = temp_db.create_scope(
            scope_name="Test",
            scope_type="region",
            region_id=10000037,
            watchlist_id=watchlist.watchlist_id,
        )

        now = int(time.time())
        prices = [
            MarketScopePrice(
                scope_id=scope.scope_id,
                type_id=type_id,
                buy_max=5.0 + type_id * 0.1,
                buy_volume=1000000,
                sell_min=4.5 + type_id * 0.1,
                sell_volume=2000000,
                spread_pct=10.0,
                order_count_buy=100,
                order_count_sell=150,
                updated_at=now,
                http_last_modified=now,
                http_expires=now + 300,
                source="esi",
                coverage_type="watchlist",
                fetch_status="complete",
            )
            for type_id in [34, 35, 36]
        ]

        count = temp_db.upsert_scope_prices_batch(prices)
        assert count == 3

        all_prices = temp_db.get_scope_prices(scope.scope_id)
        assert len(all_prices) == 3

    def test_get_scope_prices_with_max_age(self, temp_db: MarketDatabase):
        """Test getting scope prices with max age filter."""
        watchlist = temp_db.create_watchlist("Test")
        scope = temp_db.create_scope(
            scope_name="Test",
            scope_type="region",
            region_id=10000037,
            watchlist_id=watchlist.watchlist_id,
        )

        now = int(time.time())
        old_price = MarketScopePrice(
            scope_id=scope.scope_id,
            type_id=34,
            buy_max=5.0,
            buy_volume=1000000,
            sell_min=4.5,
            sell_volume=2000000,
            spread_pct=10.0,
            order_count_buy=100,
            order_count_sell=150,
            updated_at=now - 3600,  # 1 hour old
            http_last_modified=now - 3600,
            http_expires=now - 3300,
            source="esi",
            coverage_type="watchlist",
            fetch_status="complete",
        )
        new_price = MarketScopePrice(
            scope_id=scope.scope_id,
            type_id=35,
            buy_max=10.0,
            buy_volume=500000,
            sell_min=9.5,
            sell_volume=1000000,
            spread_pct=5.0,
            order_count_buy=50,
            order_count_sell=75,
            updated_at=now,  # Fresh
            http_last_modified=now,
            http_expires=now + 300,
            source="esi",
            coverage_type="watchlist",
            fetch_status="complete",
        )
        temp_db.upsert_scope_price(old_price)
        temp_db.upsert_scope_price(new_price)

        # Only fresh prices (< 30 min)
        fresh_prices = temp_db.get_scope_prices(scope.scope_id, max_age_seconds=1800)
        assert len(fresh_prices) == 1
        assert fresh_prices[0].type_id == 35

        # All prices
        all_prices = temp_db.get_scope_prices(scope.scope_id)
        assert len(all_prices) == 2

    def test_clear_scope_prices(self, temp_db: MarketDatabase):
        """Test clearing all prices for a scope."""
        watchlist = temp_db.create_watchlist("Test")
        scope = temp_db.create_scope(
            scope_name="Test",
            scope_type="region",
            region_id=10000037,
            watchlist_id=watchlist.watchlist_id,
        )

        now = int(time.time())
        prices = [
            MarketScopePrice(
                scope_id=scope.scope_id,
                type_id=type_id,
                buy_max=5.0,
                buy_volume=1000000,
                sell_min=4.5,
                sell_volume=2000000,
                spread_pct=10.0,
                order_count_buy=100,
                order_count_sell=150,
                updated_at=now,
                http_last_modified=now,
                http_expires=now + 300,
                source="esi",
                coverage_type="watchlist",
                fetch_status="complete",
            )
            for type_id in [34, 35, 36]
        ]
        temp_db.upsert_scope_prices_batch(prices)

        count = temp_db.clear_scope_prices(scope.scope_id)
        assert count == 3

        remaining = temp_db.get_scope_prices(scope.scope_id)
        assert len(remaining) == 0

    def test_cascade_delete_scope_prices(self, temp_db: MarketDatabase):
        """Test that deleting a scope cascades to prices."""
        watchlist = temp_db.create_watchlist("Test")
        scope = temp_db.create_scope(
            scope_name="Test",
            scope_type="region",
            region_id=10000037,
            watchlist_id=watchlist.watchlist_id,
        )

        now = int(time.time())
        price = MarketScopePrice(
            scope_id=scope.scope_id,
            type_id=34,
            buy_max=5.0,
            buy_volume=1000000,
            sell_min=4.5,
            sell_volume=2000000,
            spread_pct=10.0,
            order_count_buy=100,
            order_count_sell=150,
            updated_at=now,
            http_last_modified=now,
            http_expires=now + 300,
            source="esi",
            coverage_type="watchlist",
            fetch_status="complete",
        )
        temp_db.upsert_scope_price(price)

        # Delete scope
        temp_db.delete_scope(scope.scope_id)

        # Prices should be gone
        remaining = temp_db.get_scope_prices(scope.scope_id)
        assert len(remaining) == 0

    def test_invalid_fetch_status_rejected(self, temp_db: MarketDatabase):
        """Test that invalid fetch_status is rejected."""
        watchlist = temp_db.create_watchlist("Test")
        scope = temp_db.create_scope(
            scope_name="Test",
            scope_type="region",
            region_id=10000037,
            watchlist_id=watchlist.watchlist_id,
        )

        # Try to insert with invalid fetch_status via direct SQL
        conn = temp_db._get_connection()
        now = int(time.time())
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO market_scope_prices (
                    scope_id, type_id, buy_max, buy_volume, sell_min, sell_volume,
                    spread_pct, order_count_buy, order_count_sell, updated_at,
                    http_last_modified, http_expires, source, coverage_type, fetch_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scope.scope_id,
                    34,
                    5.0,
                    1000000,
                    4.5,
                    2000000,
                    10.0,
                    100,
                    150,
                    now,
                    now,
                    now + 300,
                    "esi",
                    "watchlist",
                    "invalid_status",  # Invalid
                ),
            )
            conn.commit()

    def test_valid_fetch_status_values(self, temp_db: MarketDatabase):
        """Test that all valid fetch_status values are accepted."""
        watchlist = temp_db.create_watchlist("Test")
        scope = temp_db.create_scope(
            scope_name="Test",
            scope_type="region",
            region_id=10000037,
            watchlist_id=watchlist.watchlist_id,
        )

        now = int(time.time())
        valid_statuses = ["complete", "truncated", "skipped_truncation"]

        for i, status in enumerate(valid_statuses):
            price = MarketScopePrice(
                scope_id=scope.scope_id,
                type_id=34 + i,
                buy_max=5.0,
                buy_volume=1000000,
                sell_min=4.5,
                sell_volume=2000000,
                spread_pct=10.0,
                order_count_buy=100,
                order_count_sell=150,
                updated_at=now,
                http_last_modified=now,
                http_expires=now + 300,
                source="esi",
                coverage_type="watchlist",
                fetch_status=status,
            )
            temp_db.upsert_scope_price(price)

        all_prices = temp_db.get_scope_prices(scope.scope_id)
        assert len(all_prices) == 3


# =============================================================================
# Core Hub Seeding Tests
# =============================================================================


class TestCoreHubSeeding:
    """Tests for core hub seeding."""

    def test_idempotent_seeding(self, temp_db: MarketDatabase):
        """Test that seeding is idempotent."""
        # Get initial count
        scopes_before = temp_db.list_scopes(include_core=True)
        core_before = [s for s in scopes_before if s.is_core]
        count_before = len(core_before)

        # Trigger seeding again
        temp_db._seed_core_scopes()

        # Count should be the same
        scopes_after = temp_db.list_scopes(include_core=True)
        core_after = [s for s in scopes_after if s.is_core]
        count_after = len(core_after)

        assert count_before == count_after == 5

    def test_core_hub_region_ids(self, temp_db: MarketDatabase):
        """Test that core hubs have correct region IDs."""
        expected_regions = {
            "Jita": 10000002,
            "Amarr": 10000043,
            "Dodixie": 10000032,
            "Rens": 10000030,
            "Hek": 10000042,
        }

        for hub_name, expected_region in expected_regions.items():
            scope = temp_db.get_scope(hub_name)
            assert scope is not None, f"Core hub {hub_name} not found"
            assert scope.region_id == expected_region, f"{hub_name} has wrong region_id"

    def test_core_hubs_are_global(self, temp_db: MarketDatabase):
        """Test that core hubs have no owner."""
        scopes = temp_db.list_scopes(include_core=True)
        core_scopes = [s for s in scopes if s.is_core]

        for scope in core_scopes:
            assert scope.owner_character_id is None

    def test_core_hubs_initial_status(self, temp_db: MarketDatabase):
        """Test that core hubs have initial 'new' status."""
        scopes = temp_db.list_scopes(include_core=True)
        core_scopes = [s for s in scopes if s.is_core]

        for scope in core_scopes:
            assert scope.last_scan_status == "new"
            assert scope.last_scanned_at is None


# =============================================================================
# Code Review Fix Tests
# =============================================================================


class TestListScopesGlobalInclusion:
    """Tests for list_scopes including global ad-hoc scopes when owner is provided."""

    def test_list_scopes_includes_global_adhoc_with_owner(self, temp_db: MarketDatabase):
        """Test that list_scopes includes global ad-hoc scopes when owner_character_id is provided."""
        # Create a global ad-hoc scope
        watchlist = temp_db.create_watchlist("Global Watchlist")
        temp_db.create_scope(
            scope_name="GlobalAdhoc",
            scope_type="region",
            region_id=10000037,
            watchlist_id=watchlist.watchlist_id,
        )

        # Create an owner-specific scope
        owner_watchlist = temp_db.create_watchlist("Owner Watchlist", owner_character_id=12345)
        temp_db.create_scope(
            scope_name="OwnerScope",
            scope_type="region",
            region_id=10000038,
            watchlist_id=owner_watchlist.watchlist_id,
            owner_character_id=12345,
        )

        # List scopes for owner - should include owner's scope + global (core + ad-hoc)
        scopes = temp_db.list_scopes(owner_character_id=12345, include_core=True)

        names = {s.scope_name for s in scopes}
        # Should have: 5 core hubs + GlobalAdhoc + OwnerScope
        assert "OwnerScope" in names
        assert "GlobalAdhoc" in names
        assert "Jita" in names  # Core hub
        assert len(scopes) == 7  # 5 core + 1 global ad-hoc + 1 owner

    def test_list_scopes_exclude_global_with_flag(self, temp_db: MarketDatabase):
        """Test that list_scopes can exclude global scopes with include_global=False."""
        # Create a global ad-hoc scope
        watchlist = temp_db.create_watchlist("Global Watchlist")
        temp_db.create_scope(
            scope_name="GlobalAdhoc",
            scope_type="region",
            region_id=10000037,
            watchlist_id=watchlist.watchlist_id,
        )

        # Create an owner-specific scope
        owner_watchlist = temp_db.create_watchlist("Owner Watchlist", owner_character_id=12345)
        temp_db.create_scope(
            scope_name="OwnerScope",
            scope_type="region",
            region_id=10000038,
            watchlist_id=owner_watchlist.watchlist_id,
            owner_character_id=12345,
        )

        # List only owner scopes
        scopes = temp_db.list_scopes(
            owner_character_id=12345,
            include_core=True,
            include_global=False,
        )

        names = {s.scope_name for s in scopes}
        assert "OwnerScope" in names
        assert "GlobalAdhoc" not in names
        assert "Jita" not in names  # Core hub excluded
        assert len(scopes) == 1


class TestCoreScopeMustBeGlobal:
    """Tests for core scope owner constraint."""

    def test_core_scope_with_owner_rejected(self, temp_db: MarketDatabase):
        """Test that core scopes with owner_character_id are rejected."""
        with pytest.raises(sqlite3.IntegrityError):
            temp_db.create_scope(
                scope_name="BadCore",
                scope_type="hub_region",
                region_id=10000002,
                is_core=True,
                source="fuzzwork",
                owner_character_id=12345,  # Not allowed for core scopes
            )


class TestCoreHubSeedingDoesNotSkipNonCore:
    """Tests for core hub seeding behavior with existing non-core scopes."""

    def test_seeding_is_idempotent(self, temp_db: MarketDatabase):
        """Test that core hub seeding is idempotent - calling it again doesn't fail.

        The seeding checks for existing core scopes with the same name before
        inserting. Running seeding multiple times should be safe.
        """
        # Verify core hubs exist
        scopes = temp_db.list_scopes(include_core=True)
        core_scopes = [s for s in scopes if s.is_core]
        assert len(core_scopes) == 5

        # Call seeding again - should be idempotent
        temp_db._seed_core_scopes()

        # Should still have exactly 5 core hubs
        scopes = temp_db.list_scopes(include_core=True)
        core_scopes = [s for s in scopes if s.is_core]
        assert len(core_scopes) == 5

    def test_seeding_checks_for_core_not_just_name(self, temp_db: MarketDatabase):
        """Test that seeding logic checks is_core flag, not just scope name.

        Note: Due to the unique index on (scope_name) WHERE owner_character_id IS NULL,
        we cannot have both a global non-core scope and a global core scope with the
        same name. This test verifies the behavior by checking that a character-owned
        scope with the same name doesn't block core hub seeding.
        """
        # Verify Jita core hub exists
        jita = temp_db.get_scope("Jita")
        assert jita is not None
        assert jita.is_core is True

        # Create a character-owned "Jita" scope (different namespace)
        owner_id = 12345678
        watchlist = temp_db.create_watchlist("Test", owner_character_id=owner_id)
        char_jita = temp_db.create_scope(
            scope_name="Jita",  # Same name but character-owned
            scope_type="region",
            region_id=10000002,
            watchlist_id=watchlist.watchlist_id,
            owner_character_id=owner_id,
        )
        assert char_jita is not None
        assert char_jita.is_core is False

        # Core Jita still exists (wasn't affected by character-owned "Jita")
        jita = temp_db.get_scope("Jita")  # Gets global one
        assert jita is not None
        assert jita.is_core is True

        # Seeding again should be safe
        temp_db._seed_core_scopes()

        # Still have exactly 5 core hubs
        scopes = temp_db.list_scopes(include_core=True)
        core_scopes = [s for s in scopes if s.is_core]
        assert len(core_scopes) == 5


class TestMarketScopePriceConstraints:
    """Tests for source and coverage_type constraints in market_scope_prices."""

    def test_invalid_source_rejected(self, temp_db: MarketDatabase):
        """Test that invalid source values are rejected."""
        watchlist = temp_db.create_watchlist("Test")
        scope = temp_db.create_scope(
            scope_name="Test",
            scope_type="region",
            region_id=10000037,
            watchlist_id=watchlist.watchlist_id,
        )

        conn = temp_db._get_connection()
        now = int(time.time())
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO market_scope_prices (
                    scope_id, type_id, buy_max, buy_volume, sell_min, sell_volume,
                    spread_pct, order_count_buy, order_count_sell, updated_at,
                    http_last_modified, http_expires, source, coverage_type, fetch_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scope.scope_id,
                    34,
                    5.0,
                    1000000,
                    4.5,
                    2000000,
                    10.0,
                    100,
                    150,
                    now,
                    now,
                    now + 300,
                    "invalid_source",  # Invalid
                    "watchlist",
                    "complete",
                ),
            )
            conn.commit()

    def test_invalid_coverage_type_rejected(self, temp_db: MarketDatabase):
        """Test that invalid coverage_type values are rejected."""
        watchlist = temp_db.create_watchlist("Test")
        scope = temp_db.create_scope(
            scope_name="Test",
            scope_type="region",
            region_id=10000037,
            watchlist_id=watchlist.watchlist_id,
        )

        conn = temp_db._get_connection()
        now = int(time.time())
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO market_scope_prices (
                    scope_id, type_id, buy_max, buy_volume, sell_min, sell_volume,
                    spread_pct, order_count_buy, order_count_sell, updated_at,
                    http_last_modified, http_expires, source, coverage_type, fetch_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scope.scope_id,
                    34,
                    5.0,
                    1000000,
                    4.5,
                    2000000,
                    10.0,
                    100,
                    150,
                    now,
                    now,
                    now + 300,
                    "esi",
                    "invalid_coverage",  # Invalid
                    "complete",
                ),
            )
            conn.commit()

    def test_valid_source_and_coverage_accepted(self, temp_db: MarketDatabase):
        """Test that valid source and coverage_type values are accepted.

        Ad-hoc scope prices must use ESI source with watchlist coverage only.
        """
        watchlist = temp_db.create_watchlist("Test")
        scope = temp_db.create_scope(
            scope_name="Test",
            scope_type="region",
            region_id=10000037,
            watchlist_id=watchlist.watchlist_id,
        )

        now = int(time.time())

        # Test esi + watchlist (the only valid combination for ad-hoc scopes)
        price1 = MarketScopePrice(
            scope_id=scope.scope_id,
            type_id=34,
            buy_max=5.0,
            buy_volume=1000000,
            sell_min=4.5,
            sell_volume=2000000,
            spread_pct=10.0,
            order_count_buy=100,
            order_count_sell=150,
            updated_at=now,
            http_last_modified=now,
            http_expires=now + 300,
            source="esi",
            coverage_type="watchlist",
            fetch_status="complete",
        )
        temp_db.upsert_scope_price(price1)

        # Test another item with same valid values
        price2 = MarketScopePrice(
            scope_id=scope.scope_id,
            type_id=35,
            buy_max=10.0,
            buy_volume=500000,
            sell_min=9.5,
            sell_volume=1000000,
            spread_pct=5.0,
            order_count_buy=50,
            order_count_sell=75,
            updated_at=now,
            http_last_modified=now,
            http_expires=now + 300,
            source="esi",
            coverage_type="watchlist",
            fetch_status="complete",
        )
        temp_db.upsert_scope_price(price2)

        prices = temp_db.get_scope_prices(scope.scope_id)
        assert len(prices) == 2

    def test_fuzzwork_source_rejected(self, temp_db: MarketDatabase):
        """Test that fuzzwork source is rejected for ad-hoc scope prices.

        Ad-hoc scopes are ESI-backed only. Core hubs use the separate
        region_prices table for Fuzzwork data.
        """
        watchlist = temp_db.create_watchlist("Test")
        scope = temp_db.create_scope(
            scope_name="Test",
            scope_type="region",
            region_id=10000037,
            watchlist_id=watchlist.watchlist_id,
        )

        now = int(time.time())
        conn = temp_db._get_connection()

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO market_scope_prices
                (scope_id, type_id, buy_max, buy_volume, sell_min, sell_volume,
                 spread_pct, order_count_buy, order_count_sell, updated_at,
                 http_last_modified, http_expires, source, coverage_type, fetch_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scope.scope_id,
                    34,
                    5.0,
                    1000000,
                    4.5,
                    2000000,
                    10.0,
                    100,
                    150,
                    now,
                    now,
                    now + 300,
                    "fuzzwork",  # Invalid for ad-hoc
                    "watchlist",
                    "complete",
                ),
            )

    def test_full_coverage_rejected(self, temp_db: MarketDatabase):
        """Test that full coverage is rejected for ad-hoc scope prices.

        Ad-hoc scopes must use watchlist coverage to bound ESI calls.
        """
        watchlist = temp_db.create_watchlist("Test")
        scope = temp_db.create_scope(
            scope_name="Test",
            scope_type="region",
            region_id=10000037,
            watchlist_id=watchlist.watchlist_id,
        )

        now = int(time.time())
        conn = temp_db._get_connection()

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO market_scope_prices
                (scope_id, type_id, buy_max, buy_volume, sell_min, sell_volume,
                 spread_pct, order_count_buy, order_count_sell, updated_at,
                 http_last_modified, http_expires, source, coverage_type, fetch_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scope.scope_id,
                    34,
                    5.0,
                    1000000,
                    4.5,
                    2000000,
                    10.0,
                    100,
                    150,
                    now,
                    now,
                    now + 300,
                    "esi",
                    "full",  # Invalid for ad-hoc
                    "complete",
                ),
            )


class TestResolveScopesWithShadowing:
    """Test resolve_scopes method handles owner-shadows-global precedence."""

    def test_resolve_global_scopes_only(self, temp_db: MarketDatabase):
        """Test resolving scopes when no owner specified returns globals."""
        # Create a global ad-hoc scope
        watchlist = temp_db.create_watchlist("TestList")
        temp_db.create_scope(
            scope_name="MyRegion",
            scope_type="region",
            region_id=10000037,
            watchlist_id=watchlist.watchlist_id,
        )

        # Resolve with no owner - should get global scope
        resolved = temp_db.resolve_scopes(["Jita", "MyRegion"])
        names = {s.scope_name for s in resolved}

        assert "Jita" in names  # Core hub
        assert "MyRegion" in names  # Global ad-hoc
        assert len(resolved) == 2

    def test_owner_scope_shadows_global(self, temp_db: MarketDatabase):
        """Test that owner scope shadows global scope with same name."""
        owner_id = 12345678

        # Create global ad-hoc scope
        global_watchlist = temp_db.create_watchlist("GlobalList")
        temp_db.create_scope(
            scope_name="SharedName",
            scope_type="region",
            region_id=10000037,
            watchlist_id=global_watchlist.watchlist_id,
        )

        # Create owner's scope with same name
        owner_watchlist = temp_db.create_watchlist("OwnerList", owner_character_id=owner_id)
        owner_scope = temp_db.create_scope(
            scope_name="SharedName",
            scope_type="region",
            region_id=10000043,  # Different region
            watchlist_id=owner_watchlist.watchlist_id,
            owner_character_id=owner_id,
        )

        # Resolve with owner - owner's scope should shadow global
        resolved = temp_db.resolve_scopes(["SharedName"], owner_character_id=owner_id)

        assert len(resolved) == 1
        assert resolved[0].scope_id == owner_scope.scope_id
        assert resolved[0].region_id == 10000043  # Owner's region
        assert resolved[0].owner_character_id == owner_id

    def test_owner_scope_does_not_shadow_different_name(self, temp_db: MarketDatabase):
        """Test that owner scopes only shadow globals with exact same name."""
        owner_id = 12345678

        # Create global ad-hoc scope
        global_watchlist = temp_db.create_watchlist("GlobalList")
        temp_db.create_scope(
            scope_name="GlobalScope",
            scope_type="region",
            region_id=10000037,
            watchlist_id=global_watchlist.watchlist_id,
        )

        # Create owner's scope with different name
        owner_watchlist = temp_db.create_watchlist("OwnerList", owner_character_id=owner_id)
        temp_db.create_scope(
            scope_name="OwnerScope",
            scope_type="region",
            region_id=10000043,
            watchlist_id=owner_watchlist.watchlist_id,
            owner_character_id=owner_id,
        )

        # Resolve both names - should get both scopes
        resolved = temp_db.resolve_scopes(
            ["GlobalScope", "OwnerScope"],
            owner_character_id=owner_id,
        )

        names = {s.scope_name for s in resolved}
        assert "GlobalScope" in names
        assert "OwnerScope" in names
        assert len(resolved) == 2

    def test_resolve_includes_core_hubs(self, temp_db: MarketDatabase):
        """Test that resolve_scopes includes core hubs by default."""
        resolved = temp_db.resolve_scopes(["Jita", "Amarr", "Dodixie"])

        names = {s.scope_name for s in resolved}
        assert "Jita" in names
        assert "Amarr" in names
        assert "Dodixie" in names
        assert all(s.is_core for s in resolved)

    def test_resolve_excludes_core_when_flag_false(self, temp_db: MarketDatabase):
        """Test that resolve_scopes excludes core hubs when include_core=False."""
        resolved = temp_db.resolve_scopes(["Jita", "Amarr"], include_core=False)

        assert len(resolved) == 0  # No non-core scopes with these names

    def test_resolve_empty_list(self, temp_db: MarketDatabase):
        """Test that resolve_scopes handles empty list."""
        resolved = temp_db.resolve_scopes([])
        assert resolved == []

    def test_resolve_nonexistent_scope(self, temp_db: MarketDatabase):
        """Test that resolve_scopes silently ignores nonexistent names."""
        resolved = temp_db.resolve_scopes(["Jita", "NonexistentScope"])

        names = {s.scope_name for s in resolved}
        assert "Jita" in names
        assert "NonexistentScope" not in names
        assert len(resolved) == 1


class TestCoreScopeDeletionGuard:
    """Test that core hub scopes cannot be deleted."""

    def test_delete_core_scope_raises_error(self, temp_db: MarketDatabase):
        """Test that attempting to delete a core scope raises ValueError."""
        # Get a core scope
        scopes = temp_db.list_scopes(include_core=True)
        core_scope = next(s for s in scopes if s.is_core)

        with pytest.raises(ValueError, match="Cannot delete core hub scope"):
            temp_db.delete_scope(core_scope.scope_id)

        # Verify scope still exists
        still_exists = temp_db.get_scope_by_id(core_scope.scope_id)
        assert still_exists is not None

    def test_delete_adhoc_scope_succeeds(self, temp_db: MarketDatabase):
        """Test that non-core scopes can be deleted normally."""
        watchlist = temp_db.create_watchlist("Test")
        scope = temp_db.create_scope(
            scope_name="DeletableScope",
            scope_type="region",
            region_id=10000037,
            watchlist_id=watchlist.watchlist_id,
        )

        # Should succeed
        result = temp_db.delete_scope(scope.scope_id)
        assert result is True

        # Verify deleted
        deleted = temp_db.get_scope_by_id(scope.scope_id)
        assert deleted is None

    def test_delete_nonexistent_scope_returns_false(self, temp_db: MarketDatabase):
        """Test that deleting nonexistent scope returns False."""
        result = temp_db.delete_scope(999999)
        assert result is False

    def test_core_hubs_survive_deletion_attempts(self, temp_db: MarketDatabase):
        """Test that all 5 core hubs survive deletion attempts."""
        scopes = temp_db.list_scopes(include_core=True)
        core_scopes = [s for s in scopes if s.is_core]

        assert len(core_scopes) == 5  # All 5 hubs present

        # Try to delete each one
        for scope in core_scopes:
            with pytest.raises(ValueError):
                temp_db.delete_scope(scope.scope_id)

        # Verify all still exist
        scopes_after = temp_db.list_scopes(include_core=True)
        core_after = [s for s in scopes_after if s.is_core]
        assert len(core_after) == 5
