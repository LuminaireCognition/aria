"""
Tests for aria_esi.mcp.market.database

Tests SQLite database operations for market data.
"""

import time
from pathlib import Path

import pytest


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """Create a temporary database path."""
    return tmp_path / "test_aria.db"


@pytest.fixture
def market_db(temp_db: Path):
    """Create a MarketDatabase instance with temp path."""
    from aria_esi.mcp.market.database import MarketDatabase

    db = MarketDatabase(db_path=temp_db)
    yield db
    db.close()


class TestMarketDatabaseInit:
    """Tests for MarketDatabase initialization."""

    def test_creates_database_file(self, temp_db: Path):
        from aria_esi.mcp.market.database import MarketDatabase

        db = MarketDatabase(db_path=temp_db)
        db._get_connection()  # Trigger initialization

        assert temp_db.exists()
        db.close()

    def test_creates_parent_directories(self, tmp_path: Path):
        from aria_esi.mcp.market.database import MarketDatabase

        deep_path = tmp_path / "nested" / "dirs" / "aria.db"
        db = MarketDatabase(db_path=deep_path)
        db._get_connection()

        assert deep_path.parent.exists()
        db.close()

    def test_default_path_uses_canonical_name(self, monkeypatch):
        """Verify default db_path uses aria.db from settings when ARIA_DB is unset."""
        from aria_esi.core.config import get_settings, reset_settings
        from aria_esi.mcp.market.database import MarketDatabase

        # Ensure ARIA_DB env var is not set
        monkeypatch.delenv("ARIA_DB", raising=False)
        reset_settings()  # Clear cached settings

        # Get the expected path from settings
        expected_path = get_settings().db_path

        # Verify path structure: should be instance_root/cache/aria.db
        assert expected_path.name == "aria.db"
        assert expected_path.parent.name == "cache"

        # Verify MarketDatabase uses this default
        db = MarketDatabase()
        assert db.db_path == expected_path
        # Don't initialize the connection - just check the path

    def test_schema_created(self, market_db):
        """Verify schema tables are created."""
        conn = market_db._get_connection()

        # Check tables exist
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in cursor.fetchall()}

        assert "types" in tables
        assert "aggregates" in tables
        assert "common_items" in tables
        assert "metadata" in tables


class TestTypeResolution:
    """Tests for type name resolution."""

    def test_resolve_exact_match(self, market_db):
        """Exact name match (case-insensitive)."""
        # Insert test type
        conn = market_db._get_connection()
        conn.execute(
            """
            INSERT INTO types (type_id, type_name, type_name_lower)
            VALUES (34, 'Tritanium', 'tritanium')
            """
        )
        conn.commit()

        result = market_db.resolve_type_name("Tritanium")

        assert result is not None
        assert result.type_id == 34
        assert result.type_name == "Tritanium"

    def test_resolve_case_insensitive(self, market_db):
        """Case insensitive matching."""
        conn = market_db._get_connection()
        conn.execute(
            """
            INSERT INTO types (type_id, type_name, type_name_lower)
            VALUES (34, 'Tritanium', 'tritanium')
            """
        )
        conn.commit()

        result = market_db.resolve_type_name("TRITANIUM")

        assert result is not None
        assert result.type_id == 34

    def test_resolve_prefix_match(self, market_db):
        """Prefix matching for partial names."""
        conn = market_db._get_connection()
        conn.execute(
            """
            INSERT INTO types (type_id, type_name, type_name_lower)
            VALUES (34, 'Tritanium', 'tritanium')
            """
        )
        conn.commit()

        result = market_db.resolve_type_name("Trit")

        assert result is not None
        assert result.type_id == 34

    def test_resolve_contains_match(self, market_db):
        """Contains matching as fallback."""
        conn = market_db._get_connection()
        conn.execute(
            """
            INSERT INTO types (type_id, type_name, type_name_lower)
            VALUES (11578, 'Heavy Assault Missile Launcher II', 'heavy assault missile launcher ii')
            """
        )
        conn.commit()

        result = market_db.resolve_type_name("Assault Missile")

        assert result is not None
        assert result.type_id == 11578

    def test_resolve_not_found(self, market_db):
        """Returns None when type not found."""
        result = market_db.resolve_type_name("NonexistentItem123")

        assert result is None

    def test_resolve_type_id(self, market_db):
        """Resolve by type ID."""
        conn = market_db._get_connection()
        conn.execute(
            """
            INSERT INTO types (type_id, type_name, type_name_lower)
            VALUES (34, 'Tritanium', 'tritanium')
            """
        )
        conn.commit()

        result = market_db.resolve_type_id(34)

        assert result is not None
        assert result.type_name == "Tritanium"

    def test_resolve_type_id_not_found(self, market_db):
        """Returns None when type ID not found."""
        result = market_db.resolve_type_id(99999999)

        assert result is None


class TestTypeSuggestions:
    """Tests for type name suggestions."""

    def test_find_suggestions_prefix(self, market_db):
        """Suggestions start with prefix matches."""
        conn = market_db._get_connection()
        conn.executemany(
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
        conn.commit()

        suggestions = market_db.find_type_suggestions("tri")

        assert "Tritanium" in suggestions

    def test_find_suggestions_contains(self, market_db):
        """Suggestions include contains matches."""
        conn = market_db._get_connection()
        conn.execute(
            """
            INSERT INTO types (type_id, type_name, type_name_lower)
            VALUES (11578, 'Heavy Assault Missile Launcher II', 'heavy assault missile launcher ii')
            """
        )
        conn.commit()

        suggestions = market_db.find_type_suggestions("missile")

        assert "Heavy Assault Missile Launcher II" in suggestions

    def test_find_suggestions_limit(self, market_db):
        """Respects suggestion limit."""
        conn = market_db._get_connection()
        conn.executemany(
            """
            INSERT INTO types (type_id, type_name, type_name_lower)
            VALUES (?, ?, ?)
            """,
            [(i, f"Test Item {i}", f"test item {i}") for i in range(100)],
        )
        conn.commit()

        suggestions = market_db.find_type_suggestions("test", limit=5)

        assert len(suggestions) <= 5


class TestBatchResolve:
    """Tests for batch name resolution."""

    def test_batch_resolve_all_found(self, market_db):
        """All names resolved."""
        conn = market_db._get_connection()
        conn.executemany(
            """
            INSERT INTO types (type_id, type_name, type_name_lower)
            VALUES (?, ?, ?)
            """,
            [
                (34, "Tritanium", "tritanium"),
                (35, "Pyerite", "pyerite"),
            ],
        )
        conn.commit()

        result = market_db.batch_resolve_names(["Tritanium", "Pyerite"])

        assert result["Tritanium"].type_id == 34
        assert result["Pyerite"].type_id == 35

    def test_batch_resolve_partial(self, market_db):
        """Some names not found."""
        conn = market_db._get_connection()
        conn.execute(
            """
            INSERT INTO types (type_id, type_name, type_name_lower)
            VALUES (34, 'Tritanium', 'tritanium')
            """
        )
        conn.commit()

        result = market_db.batch_resolve_names(["Tritanium", "Unknown"])

        assert result["Tritanium"].type_id == 34
        assert result["Unknown"] is None


class TestAggregates:
    """Tests for price aggregate storage and retrieval."""

    def test_save_and_get_aggregate(self, market_db):
        """Save and retrieve an aggregate."""
        from aria_esi.mcp.market.database import CachedAggregate

        agg = CachedAggregate(
            type_id=34,
            region_id=10000002,
            station_id=60003760,
            buy_weighted_avg=3.95,
            buy_max=4.00,
            buy_min=3.50,
            buy_stddev=0.12,
            buy_median=3.97,
            buy_volume=50000000,
            buy_order_count=1542,
            buy_percentile=3.98,
            sell_weighted_avg=4.10,
            sell_max=5.00,
            sell_min=4.05,
            sell_stddev=0.15,
            sell_median=4.12,
            sell_volume=12000000,
            sell_order_count=892,
            sell_percentile=4.08,
            updated_at=int(time.time()),
        )

        market_db.save_aggregate(agg)
        result = market_db.get_aggregate(34, 10000002)

        assert result is not None
        assert result.type_id == 34
        assert result.buy_max == 4.00
        assert result.sell_min == 4.05

    def test_get_aggregate_stale(self, market_db):
        """Returns None when aggregate is stale."""
        from aria_esi.mcp.market.database import CachedAggregate

        # Save with old timestamp
        old_time = int(time.time()) - 1000  # 1000 seconds ago
        agg = CachedAggregate(
            type_id=34,
            region_id=10000002,
            station_id=60003760,
            buy_weighted_avg=3.95,
            buy_max=4.00,
            buy_min=3.50,
            buy_stddev=0.12,
            buy_median=3.97,
            buy_volume=50000000,
            buy_order_count=1542,
            buy_percentile=3.98,
            sell_weighted_avg=4.10,
            sell_max=5.00,
            sell_min=4.05,
            sell_stddev=0.15,
            sell_median=4.12,
            sell_volume=12000000,
            sell_order_count=892,
            sell_percentile=4.08,
            updated_at=old_time,
        )
        market_db.save_aggregate(agg)

        # Request with 15 min max age
        result = market_db.get_aggregate(34, 10000002, max_age_seconds=900)

        assert result is None

    def test_get_aggregates_batch(self, market_db):
        """Batch retrieval of aggregates."""
        from aria_esi.mcp.market.database import CachedAggregate

        now = int(time.time())

        # Save multiple aggregates
        for type_id in [34, 35, 36]:
            agg = CachedAggregate(
                type_id=type_id,
                region_id=10000002,
                station_id=60003760,
                buy_weighted_avg=3.95,
                buy_max=4.00,
                buy_min=3.50,
                buy_stddev=0.12,
                buy_median=3.97,
                buy_volume=50000000,
                buy_order_count=1542,
                buy_percentile=3.98,
                sell_weighted_avg=4.10,
                sell_max=5.00,
                sell_min=4.05,
                sell_stddev=0.15,
                sell_median=4.12,
                sell_volume=12000000,
                sell_order_count=892,
                sell_percentile=4.08,
                updated_at=now,
            )
            market_db.save_aggregate(agg)

        result = market_db.get_aggregates_batch([34, 35, 36], 10000002)

        assert len(result) == 3
        assert 34 in result
        assert 35 in result
        assert 36 in result

    def test_save_aggregates_batch(self, market_db):
        """Batch saving of aggregates."""
        from aria_esi.mcp.market.database import CachedAggregate

        now = int(time.time())
        aggregates = []

        for type_id in [34, 35, 36]:
            agg = CachedAggregate(
                type_id=type_id,
                region_id=10000002,
                station_id=60003760,
                buy_weighted_avg=3.95,
                buy_max=4.00,
                buy_min=3.50,
                buy_stddev=0.12,
                buy_median=3.97,
                buy_volume=50000000,
                buy_order_count=1542,
                buy_percentile=3.98,
                sell_weighted_avg=4.10,
                sell_max=5.00,
                sell_min=4.05,
                sell_stddev=0.15,
                sell_median=4.12,
                sell_volume=12000000,
                sell_order_count=892,
                sell_percentile=4.08,
                updated_at=now,
            )
            aggregates.append(agg)

        count = market_db.save_aggregates_batch(aggregates)

        # Verify saved
        result = market_db.get_aggregates_batch([34, 35, 36], 10000002)
        assert len(result) == 3


class TestDatabaseStats:
    """Tests for database statistics."""

    def test_get_stats_empty(self, market_db):
        """Stats on empty database."""
        stats = market_db.get_stats()

        assert stats["type_count"] == 0
        assert stats["aggregate_count"] == 0

    def test_get_stats_with_data(self, market_db):
        """Stats with data."""
        from aria_esi.mcp.market.database import CachedAggregate

        # Add types
        conn = market_db._get_connection()
        conn.executemany(
            """
            INSERT INTO types (type_id, type_name, type_name_lower)
            VALUES (?, ?, ?)
            """,
            [
                (34, "Tritanium", "tritanium"),
                (35, "Pyerite", "pyerite"),
            ],
        )
        conn.commit()

        # Add aggregate
        agg = CachedAggregate(
            type_id=34,
            region_id=10000002,
            station_id=60003760,
            buy_weighted_avg=3.95,
            buy_max=4.00,
            buy_min=3.50,
            buy_stddev=0.12,
            buy_median=3.97,
            buy_volume=50000000,
            buy_order_count=1542,
            buy_percentile=3.98,
            sell_weighted_avg=4.10,
            sell_max=5.00,
            sell_min=4.05,
            sell_stddev=0.15,
            sell_median=4.12,
            sell_volume=12000000,
            sell_order_count=892,
            sell_percentile=4.08,
            updated_at=int(time.time()),
        )
        market_db.save_aggregate(agg)

        stats = market_db.get_stats()

        assert stats["type_count"] == 2
        assert stats["aggregate_count"] == 1


class TestImportTypes:
    """Tests for type import from ESI format."""

    def test_import_types_from_esi(self, market_db):
        """Import types from ESI-style data."""
        types_data = [
            {
                "type_id": 34,
                "name": "Tritanium",
                "group_id": 18,
                "market_group_id": 1857,
                "volume": 0.01,
            },
            {
                "type_id": 35,
                "name": "Pyerite",
                "group_id": 18,
                "market_group_id": 1857,
                "volume": 0.01,
            },
        ]

        count = market_db.import_types_from_esi(types_data)

        assert count == 2

        # Verify imported
        result = market_db.resolve_type_name("Tritanium")
        assert result is not None
        assert result.type_id == 34


class TestSafeHelpers:
    """Tests for safe conversion helpers."""

    def test_safe_float(self):
        from aria_esi.mcp.market.database import _safe_float

        assert _safe_float("3.14") == 3.14
        assert _safe_float("100") == 100.0
        assert _safe_float("") is None
        assert _safe_float(None) is None
        assert _safe_float("not a number") is None

    def test_safe_int(self):
        from aria_esi.mcp.market.database import _safe_int

        assert _safe_int("100") == 100
        assert _safe_int("3.14") == 3  # Truncates
        assert _safe_int("") == 0
        assert _safe_int(None) == 0
        assert _safe_int("not a number") == 0
