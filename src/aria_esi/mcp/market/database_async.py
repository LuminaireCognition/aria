"""
Async Market Database for ARIA.

Async SQLite-backed storage using aiosqlite for native async operations.
Used by MCP tools for non-blocking database access.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

import aiosqlite

from ...core.config import get_settings
from ...core.logging import get_logger
from .database import (
    SCHEMA_SQL,
    CachedAggregate,
    CachedHistory,
    MarketScope,
    MarketScopePrice,
    TypeInfo,
    Watchlist,
    WatchlistItem,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = get_logger(__name__)


class AsyncMarketDatabase:
    """
    Async SQLite database for market data.

    Provides native async operations for type resolution and price caching.
    Uses aiosqlite for non-blocking database access.
    """

    def __init__(self, db_path: Path | str | None = None):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database. Defaults to cache/aria.db
        """
        if db_path is None:
            db_path = get_settings().db_path
        self.db_path = Path(db_path)

        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn: aiosqlite.Connection | None = None
        self._initialized = False

    async def _get_connection(self) -> aiosqlite.Connection:
        """Get or create database connection."""
        if self._conn is None:
            self._conn = await aiosqlite.connect(str(self.db_path))
            self._conn.row_factory = aiosqlite.Row
            # Enable foreign key constraints for cascade deletes
            await self._conn.execute("PRAGMA foreign_keys = ON")

            if not self._initialized:
                await self._initialize_schema()
                self._initialized = True

        return self._conn

    async def _initialize_schema(self) -> None:
        """Create database schema if needed."""
        conn = self._conn
        if conn is None:
            return

        await conn.executescript(SCHEMA_SQL)
        await conn.commit()
        logger.info("Async market database initialized at %s", self.db_path)

        # Seed core trade hub scopes
        await self._seed_core_scopes()

    async def _seed_core_scopes(self) -> None:
        """
        Seed core trade hub scopes if they don't exist.

        Creates 5 core hub_region scopes for the major trade hubs.
        This is idempotent - skips if scopes already exist.
        """
        core_hubs = [
            {"name": "Jita", "region_id": 10000002},
            {"name": "Amarr", "region_id": 10000043},
            {"name": "Dodixie", "region_id": 10000032},
            {"name": "Rens", "region_id": 10000030},
            {"name": "Hek", "region_id": 10000042},
        ]

        conn = await self._get_connection()
        now = int(time.time())

        for hub in core_hubs:
            # Check if core hub scope already exists (only skip if it's actually a core scope)
            async with conn.execute(
                """
                SELECT scope_id FROM market_scopes
                WHERE scope_name = ? AND owner_character_id IS NULL AND is_core = 1
                """,
                (hub["name"],),
            ) as cursor:
                existing = await cursor.fetchone()

            if existing:
                continue

            await conn.execute(
                """
                INSERT INTO market_scopes (
                    scope_name, scope_type, region_id, station_id, system_id,
                    structure_id, parent_region_id, watchlist_id, is_core,
                    source, owner_character_id, created_at, updated_at,
                    last_scanned_at, last_scan_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    hub["name"],
                    "hub_region",
                    hub["region_id"],
                    None,
                    None,
                    None,
                    None,
                    None,
                    1,
                    "fuzzwork",
                    None,
                    now,
                    now,
                    None,
                    "new",
                ),
            )
            logger.debug("Seeded core hub scope: %s", hub["name"])

        await conn.commit()

    async def close(self) -> None:
        """Close database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None

    # =========================================================================
    # Type Resolution
    # =========================================================================

    async def resolve_type_name(self, name: str) -> TypeInfo | None:
        """
        Resolve item name to type info.

        Tries exact match first, then case-insensitive, then fuzzy.

        Args:
            name: Item name to resolve

        Returns:
            TypeInfo if found, None otherwise
        """
        conn = await self._get_connection()
        name_lower = name.lower().strip()

        # Try exact match (case-insensitive)
        async with conn.execute(
            "SELECT * FROM types WHERE type_name_lower = ?",
            (name_lower,),
        ) as cursor:
            row = await cursor.fetchone()

        if row:
            return self._row_to_type_info(row)

        # Try prefix match
        async with conn.execute(
            "SELECT * FROM types WHERE type_name_lower LIKE ? LIMIT 1",
            (f"{name_lower}%",),
        ) as cursor:
            row = await cursor.fetchone()

        if row:
            return self._row_to_type_info(row)

        # Try contains match
        async with conn.execute(
            "SELECT * FROM types WHERE type_name_lower LIKE ? LIMIT 1",
            (f"%{name_lower}%",),
        ) as cursor:
            row = await cursor.fetchone()

        if row:
            return self._row_to_type_info(row)

        return None

    async def resolve_type_id(self, type_id: int) -> TypeInfo | None:
        """
        Get type info by ID.

        Args:
            type_id: Type ID to look up

        Returns:
            TypeInfo if found
        """
        conn = await self._get_connection()
        async with conn.execute(
            "SELECT * FROM types WHERE type_id = ?",
            (type_id,),
        ) as cursor:
            row = await cursor.fetchone()

        return self._row_to_type_info(row) if row else None

    async def resolve_type_ids_batch(self, type_ids: list[int]) -> dict[int, str]:
        """
        Batch resolve type IDs to type names.

        Args:
            type_ids: List of type IDs to resolve

        Returns:
            Dict mapping type_id -> type_name (only includes found types)
        """
        if not type_ids:
            return {}

        conn = await self._get_connection()
        placeholders = ",".join("?" * len(type_ids))
        async with conn.execute(
            f"SELECT type_id, type_name FROM types WHERE type_id IN ({placeholders})",
            type_ids,
        ) as cursor:
            rows = await cursor.fetchall()

        return {row["type_id"]: row["type_name"] for row in rows}

    async def find_type_suggestions(self, name: str, limit: int = 5) -> list[str]:
        """
        Find type name suggestions for fuzzy matching.

        Args:
            name: Partial or misspelled name
            limit: Maximum suggestions to return

        Returns:
            List of suggested type names
        """
        conn = await self._get_connection()
        name_lower = name.lower().strip()

        # Start with prefix matches
        async with conn.execute(
            """
            SELECT type_name FROM types
            WHERE type_name_lower LIKE ?
            ORDER BY length(type_name)
            LIMIT ?
            """,
            (f"{name_lower}%", limit),
        ) as cursor:
            rows = await cursor.fetchall()

        suggestions = [row["type_name"] for row in rows]

        if len(suggestions) < limit:
            # Add contains matches
            remaining = limit - len(suggestions)
            async with conn.execute(
                """
                SELECT type_name FROM types
                WHERE type_name_lower LIKE ?
                AND type_name_lower NOT LIKE ?
                ORDER BY length(type_name)
                LIMIT ?
                """,
                (f"%{name_lower}%", f"{name_lower}%", remaining),
            ) as cursor:
                rows = await cursor.fetchall()
            suggestions.extend(row["type_name"] for row in rows)

        return suggestions

    async def batch_resolve_names(self, names: Sequence[str]) -> dict[str, TypeInfo | None]:
        """
        Resolve multiple item names.

        Args:
            names: Item names to resolve

        Returns:
            Dict mapping input names to TypeInfo (or None if not found)
        """
        results: dict[str, TypeInfo | None] = {}
        for name in names:
            results[name] = await self.resolve_type_name(name)
        return results

    def _row_to_type_info(self, row: aiosqlite.Row) -> TypeInfo:
        """Convert database row to TypeInfo."""
        return TypeInfo(
            type_id=row["type_id"],
            type_name=row["type_name"],
            group_id=row["group_id"],
            category_id=row["category_id"],
            market_group_id=row["market_group_id"],
            volume=row["volume"],
        )

    # =========================================================================
    # Price Aggregates
    # =========================================================================

    async def get_aggregate(
        self,
        type_id: int,
        region_id: int,
        max_age_seconds: int = 900,
    ) -> CachedAggregate | None:
        """
        Get cached price aggregate if fresh enough.

        Args:
            type_id: Type ID to look up
            region_id: Region ID
            max_age_seconds: Maximum cache age (default 15 min)

        Returns:
            CachedAggregate if found and fresh, None otherwise
        """
        conn = await self._get_connection()
        cutoff = int(time.time()) - max_age_seconds

        async with conn.execute(
            """
            SELECT * FROM aggregates
            WHERE type_id = ? AND region_id = ? AND updated_at > ?
            """,
            (type_id, region_id, cutoff),
        ) as cursor:
            row = await cursor.fetchone()

        return self._row_to_aggregate(row) if row else None

    async def get_aggregates_batch(
        self,
        type_ids: Sequence[int],
        region_id: int,
        max_age_seconds: int = 900,
    ) -> dict[int, CachedAggregate]:
        """
        Get multiple cached aggregates.

        Args:
            type_ids: Type IDs to look up
            region_id: Region ID
            max_age_seconds: Maximum cache age

        Returns:
            Dict mapping type_id to CachedAggregate (only fresh entries)
        """
        if not type_ids:
            return {}

        conn = await self._get_connection()
        cutoff = int(time.time()) - max_age_seconds

        # Use parameterized query with IN clause
        placeholders = ",".join("?" * len(type_ids))
        params = list(type_ids) + [region_id, cutoff]

        async with conn.execute(
            f"""
            SELECT * FROM aggregates
            WHERE type_id IN ({placeholders})
            AND region_id = ? AND updated_at > ?
            """,
            params,
        ) as cursor:
            rows = await cursor.fetchall()

        return {row["type_id"]: self._row_to_aggregate(row) for row in rows}

    async def save_aggregate(self, aggregate: CachedAggregate) -> None:
        """Save a price aggregate to cache."""
        conn = await self._get_connection()
        await conn.execute(
            """
            INSERT OR REPLACE INTO aggregates (
                type_id, region_id, station_id,
                buy_weighted_avg, buy_max, buy_min, buy_stddev,
                buy_median, buy_volume, buy_order_count, buy_percentile,
                sell_weighted_avg, sell_max, sell_min, sell_stddev,
                sell_median, sell_volume, sell_order_count, sell_percentile,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                aggregate.type_id,
                aggregate.region_id,
                aggregate.station_id,
                aggregate.buy_weighted_avg,
                aggregate.buy_max,
                aggregate.buy_min,
                aggregate.buy_stddev,
                aggregate.buy_median,
                aggregate.buy_volume,
                aggregate.buy_order_count,
                aggregate.buy_percentile,
                aggregate.sell_weighted_avg,
                aggregate.sell_max,
                aggregate.sell_min,
                aggregate.sell_stddev,
                aggregate.sell_median,
                aggregate.sell_volume,
                aggregate.sell_order_count,
                aggregate.sell_percentile,
                aggregate.updated_at,
            ),
        )
        await conn.commit()

    async def save_aggregates_batch(self, aggregates: Sequence[CachedAggregate]) -> int:
        """
        Save multiple aggregates in a transaction.

        Args:
            aggregates: Aggregates to save

        Returns:
            Number of rows inserted/updated
        """
        if not aggregates:
            return 0

        conn = await self._get_connection()
        await conn.executemany(
            """
            INSERT OR REPLACE INTO aggregates (
                type_id, region_id, station_id,
                buy_weighted_avg, buy_max, buy_min, buy_stddev,
                buy_median, buy_volume, buy_order_count, buy_percentile,
                sell_weighted_avg, sell_max, sell_min, sell_stddev,
                sell_median, sell_volume, sell_order_count, sell_percentile,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    a.type_id,
                    a.region_id,
                    a.station_id,
                    a.buy_weighted_avg,
                    a.buy_max,
                    a.buy_min,
                    a.buy_stddev,
                    a.buy_median,
                    a.buy_volume,
                    a.buy_order_count,
                    a.buy_percentile,
                    a.sell_weighted_avg,
                    a.sell_max,
                    a.sell_min,
                    a.sell_stddev,
                    a.sell_median,
                    a.sell_volume,
                    a.sell_order_count,
                    a.sell_percentile,
                    a.updated_at,
                )
                for a in aggregates
            ],
        )
        await conn.commit()
        return len(aggregates)

    def _row_to_aggregate(self, row: aiosqlite.Row) -> CachedAggregate:
        """Convert database row to CachedAggregate."""
        return CachedAggregate(
            type_id=row["type_id"],
            region_id=row["region_id"],
            station_id=row["station_id"],
            buy_weighted_avg=row["buy_weighted_avg"],
            buy_max=row["buy_max"],
            buy_min=row["buy_min"],
            buy_stddev=row["buy_stddev"],
            buy_median=row["buy_median"],
            buy_volume=row["buy_volume"] or 0,
            buy_order_count=row["buy_order_count"] or 0,
            buy_percentile=row["buy_percentile"],
            sell_weighted_avg=row["sell_weighted_avg"],
            sell_max=row["sell_max"],
            sell_min=row["sell_min"],
            sell_stddev=row["sell_stddev"],
            sell_median=row["sell_median"],
            sell_volume=row["sell_volume"] or 0,
            sell_order_count=row["sell_order_count"] or 0,
            sell_percentile=row["sell_percentile"],
            updated_at=row["updated_at"],
        )

    # =========================================================================
    # Database Stats
    # =========================================================================

    async def get_stats(self) -> dict:
        """
        Get database statistics.

        Returns:
            Dict with counts and freshness info
        """
        conn = await self._get_connection()
        now = int(time.time())

        async with conn.execute("SELECT COUNT(*) FROM types") as cursor:
            type_count = (await cursor.fetchone())[0]

        async with conn.execute("SELECT COUNT(*) FROM aggregates") as cursor:
            aggregate_count = (await cursor.fetchone())[0]

        async with conn.execute("SELECT MIN(updated_at) FROM aggregates") as cursor:
            oldest = (await cursor.fetchone())[0]

        async with conn.execute("SELECT MAX(updated_at) FROM aggregates") as cursor:
            newest = (await cursor.fetchone())[0]

        return {
            "type_count": type_count,
            "aggregate_count": aggregate_count,
            "oldest_update": now - oldest if oldest else None,
            "newest_update": now - newest if newest else None,
            "database_path": str(self.db_path),
            "database_size_mb": self.db_path.stat().st_size / (1024 * 1024)
            if self.db_path.exists()
            else 0,
        }

    # =========================================================================
    # History Cache
    # =========================================================================

    async def get_history_cache(
        self,
        type_id: int,
        region_id: int,
        max_age_seconds: int = 86400,  # 24 hours
    ) -> CachedHistory | None:
        """
        Get cached history data if fresh enough.

        Market history updates once daily after downtime, so TTL is 24 hours.

        Args:
            type_id: Type ID to look up
            region_id: Region ID
            max_age_seconds: Maximum cache age (default 24 hours)

        Returns:
            CachedHistory if found and fresh, None otherwise
        """
        conn = await self._get_connection()
        cutoff = int(time.time()) - max_age_seconds

        async with conn.execute(
            """
            SELECT * FROM market_history_cache
            WHERE type_id = ? AND region_id = ? AND updated_at > ?
            """,
            (type_id, region_id, cutoff),
        ) as cursor:
            row = await cursor.fetchone()

        return self._row_to_history(row) if row else None

    async def get_history_cache_batch(
        self,
        type_ids: Sequence[int],
        region_id: int,
        max_age_seconds: int = 86400,
    ) -> dict[int, CachedHistory]:
        """
        Get multiple cached history entries.

        Args:
            type_ids: Type IDs to look up
            region_id: Region ID
            max_age_seconds: Maximum cache age

        Returns:
            Dict mapping type_id to CachedHistory (only fresh entries)
        """
        if not type_ids:
            return {}

        conn = await self._get_connection()
        cutoff = int(time.time()) - max_age_seconds

        # Use parameterized query with IN clause
        placeholders = ",".join("?" * len(type_ids))
        params = list(type_ids) + [region_id, cutoff]

        async with conn.execute(
            f"""
            SELECT * FROM market_history_cache
            WHERE type_id IN ({placeholders})
            AND region_id = ? AND updated_at > ?
            """,
            params,
        ) as cursor:
            rows = await cursor.fetchall()

        return {row["type_id"]: self._row_to_history(row) for row in rows}

    async def save_history_cache(
        self,
        type_id: int,
        region_id: int,
        avg_daily_volume: int | None,
        avg_daily_isk: float | None = None,
        volatility_pct: float | None = None,
    ) -> None:
        """
        Save history data to cache.

        Args:
            type_id: Type ID
            region_id: Region ID
            avg_daily_volume: Average daily trade volume
            avg_daily_isk: Average daily ISK volume
            volatility_pct: Price volatility percentage
        """
        conn = await self._get_connection()
        now = int(time.time())

        await conn.execute(
            """
            INSERT OR REPLACE INTO market_history_cache (
                type_id, region_id, avg_daily_volume, avg_daily_isk,
                volatility_pct, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (type_id, region_id, avg_daily_volume, avg_daily_isk, volatility_pct, now),
        )
        await conn.commit()

    async def save_history_cache_batch(
        self,
        entries: Sequence[tuple[int, int, int | None, float | None, float | None]],
    ) -> int:
        """
        Save multiple history entries in a transaction.

        Args:
            entries: List of (type_id, region_id, avg_daily_volume, avg_daily_isk, volatility_pct)

        Returns:
            Number of rows inserted/updated
        """
        if not entries:
            return 0

        conn = await self._get_connection()
        now = int(time.time())

        await conn.executemany(
            """
            INSERT OR REPLACE INTO market_history_cache (
                type_id, region_id, avg_daily_volume, avg_daily_isk,
                volatility_pct, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [(*entry, now) for entry in entries],
        )
        await conn.commit()
        return len(entries)

    def _row_to_history(self, row: aiosqlite.Row) -> CachedHistory:
        """Convert database row to CachedHistory."""
        return CachedHistory(
            type_id=row["type_id"],
            region_id=row["region_id"],
            avg_daily_volume=row["avg_daily_volume"],
            avg_daily_isk=row["avg_daily_isk"],
            volatility_pct=row["volatility_pct"],
            updated_at=row["updated_at"],
        )

    # =========================================================================
    # Watchlist Operations
    # =========================================================================

    async def create_watchlist(
        self,
        name: str,
        owner_character_id: int | None = None,
    ) -> Watchlist:
        """
        Create a new watchlist.

        Args:
            name: Watchlist name
            owner_character_id: Character ID for ownership (None = global)

        Returns:
            Created Watchlist

        Raises:
            aiosqlite.IntegrityError: If name already exists for this owner
        """
        conn = await self._get_connection()
        now = int(time.time())

        cursor = await conn.execute(
            """
            INSERT INTO watchlists (name, owner_character_id, created_at)
            VALUES (?, ?, ?)
            """,
            (name, owner_character_id, now),
        )
        await conn.commit()

        watchlist_id = cursor.lastrowid
        assert watchlist_id is not None, "INSERT should always return a lastrowid"

        return Watchlist(
            watchlist_id=watchlist_id,
            name=name,
            owner_character_id=owner_character_id,
            created_at=now,
        )

    async def get_watchlist(
        self,
        name: str,
        owner_character_id: int | None = None,
    ) -> Watchlist | None:
        """
        Get a watchlist by name and owner.

        Args:
            name: Watchlist name
            owner_character_id: Character ID (None = global)

        Returns:
            Watchlist if found, None otherwise
        """
        conn = await self._get_connection()

        if owner_character_id is None:
            async with conn.execute(
                """
                SELECT * FROM watchlists
                WHERE name = ? AND owner_character_id IS NULL
                """,
                (name,),
            ) as cursor:
                row = await cursor.fetchone()
        else:
            async with conn.execute(
                """
                SELECT * FROM watchlists
                WHERE name = ? AND owner_character_id = ?
                """,
                (name, owner_character_id),
            ) as cursor:
                row = await cursor.fetchone()

        return self._row_to_watchlist(row) if row else None

    async def get_watchlist_by_id(self, watchlist_id: int) -> Watchlist | None:
        """
        Get a watchlist by ID.

        Args:
            watchlist_id: Watchlist ID

        Returns:
            Watchlist if found, None otherwise
        """
        conn = await self._get_connection()
        async with conn.execute(
            "SELECT * FROM watchlists WHERE watchlist_id = ?",
            (watchlist_id,),
        ) as cursor:
            row = await cursor.fetchone()

        return self._row_to_watchlist(row) if row else None

    async def list_watchlists(
        self,
        owner_character_id: int | None = None,
    ) -> list[Watchlist]:
        """
        List watchlists for an owner (or global watchlists).

        Args:
            owner_character_id: Character ID (None = global only)

        Returns:
            List of Watchlist objects
        """
        conn = await self._get_connection()

        if owner_character_id is None:
            async with conn.execute(
                """
                SELECT * FROM watchlists
                WHERE owner_character_id IS NULL
                ORDER BY name
                """
            ) as cursor:
                rows = await cursor.fetchall()
        else:
            async with conn.execute(
                """
                SELECT * FROM watchlists
                WHERE owner_character_id = ?
                ORDER BY name
                """,
                (owner_character_id,),
            ) as cursor:
                rows = await cursor.fetchall()

        return [self._row_to_watchlist(row) for row in rows]

    async def delete_watchlist(self, watchlist_id: int) -> bool:
        """
        Delete a watchlist and its items (cascade).

        Args:
            watchlist_id: Watchlist ID to delete

        Returns:
            True if deleted, False if not found
        """
        conn = await self._get_connection()
        cursor = await conn.execute(
            "DELETE FROM watchlists WHERE watchlist_id = ?",
            (watchlist_id,),
        )
        await conn.commit()
        return cursor.rowcount > 0

    async def add_watchlist_item(self, watchlist_id: int, type_id: int) -> WatchlistItem:
        """
        Add an item to a watchlist.

        Args:
            watchlist_id: Watchlist ID
            type_id: Type ID to add

        Returns:
            Created WatchlistItem

        Raises:
            aiosqlite.IntegrityError: If item already in watchlist or watchlist doesn't exist
        """
        conn = await self._get_connection()
        now = int(time.time())

        await conn.execute(
            """
            INSERT INTO watchlist_items (watchlist_id, type_id, added_at)
            VALUES (?, ?, ?)
            """,
            (watchlist_id, type_id, now),
        )
        await conn.commit()

        return WatchlistItem(
            watchlist_id=watchlist_id,
            type_id=type_id,
            added_at=now,
        )

    async def remove_watchlist_item(self, watchlist_id: int, type_id: int) -> bool:
        """
        Remove an item from a watchlist.

        Args:
            watchlist_id: Watchlist ID
            type_id: Type ID to remove

        Returns:
            True if removed, False if not found
        """
        conn = await self._get_connection()
        cursor = await conn.execute(
            """
            DELETE FROM watchlist_items
            WHERE watchlist_id = ? AND type_id = ?
            """,
            (watchlist_id, type_id),
        )
        await conn.commit()
        return cursor.rowcount > 0

    async def get_watchlist_items(self, watchlist_id: int) -> list[WatchlistItem]:
        """
        Get all items in a watchlist.

        Args:
            watchlist_id: Watchlist ID

        Returns:
            List of WatchlistItem objects
        """
        conn = await self._get_connection()
        async with conn.execute(
            """
            SELECT * FROM watchlist_items
            WHERE watchlist_id = ?
            ORDER BY type_id
            """,
            (watchlist_id,),
        ) as cursor:
            rows = await cursor.fetchall()

        return [
            WatchlistItem(
                watchlist_id=row["watchlist_id"],
                type_id=row["type_id"],
                added_at=row["added_at"],
            )
            for row in rows
        ]

    async def get_watchlist_items_for_scope(self, scope_id: int) -> list[WatchlistItem]:
        """
        Get watchlist items for a scope by joining through market_scopes.

        Args:
            scope_id: Scope ID

        Returns:
            List of WatchlistItem objects, or empty list if scope not found
            or has no watchlist
        """
        conn = await self._get_connection()
        async with conn.execute(
            """
            SELECT wi.watchlist_id, wi.type_id, wi.added_at
            FROM watchlist_items wi
            JOIN market_scopes ms ON ms.watchlist_id = wi.watchlist_id
            WHERE ms.scope_id = ?
            ORDER BY wi.type_id
            """,
            (scope_id,),
        ) as cursor:
            rows = await cursor.fetchall()

        return [
            WatchlistItem(
                watchlist_id=row["watchlist_id"],
                type_id=row["type_id"],
                added_at=row["added_at"],
            )
            for row in rows
        ]

    def _row_to_watchlist(self, row: aiosqlite.Row) -> Watchlist:
        """Convert database row to Watchlist."""
        return Watchlist(
            watchlist_id=row["watchlist_id"],
            name=row["name"],
            owner_character_id=row["owner_character_id"],
            created_at=row["created_at"],
        )

    # =========================================================================
    # Market Scope Operations
    # =========================================================================

    async def create_scope(
        self,
        scope_name: str,
        scope_type: str,
        *,
        region_id: int | None = None,
        station_id: int | None = None,
        system_id: int | None = None,
        structure_id: int | None = None,
        parent_region_id: int | None = None,
        watchlist_id: int | None = None,
        is_core: bool = False,
        source: str = "esi",
        owner_character_id: int | None = None,
    ) -> MarketScope:
        """
        Create a new market scope.

        Args:
            scope_name: Scope name
            scope_type: Scope type (hub_region, region, station, system, structure)
            region_id: Region ID (required for region/hub_region types)
            station_id: Station ID (required for station type)
            system_id: System ID (required for system type)
            structure_id: Structure ID (required for structure type)
            parent_region_id: Parent region for station/system/structure
            watchlist_id: Watchlist ID (required for ad-hoc scopes)
            is_core: True for core trade hub scopes
            source: Data source (fuzzwork for core, esi for ad-hoc)
            owner_character_id: Character ID for ownership (None = global)

        Returns:
            Created MarketScope

        Raises:
            aiosqlite.IntegrityError: If constraints violated
        """
        conn = await self._get_connection()
        now = int(time.time())

        cursor = await conn.execute(
            """
            INSERT INTO market_scopes (
                scope_name, scope_type, region_id, station_id, system_id,
                structure_id, parent_region_id, watchlist_id, is_core,
                source, owner_character_id, created_at, updated_at,
                last_scanned_at, last_scan_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scope_name,
                scope_type,
                region_id,
                station_id,
                system_id,
                structure_id,
                parent_region_id,
                watchlist_id,
                1 if is_core else 0,
                source,
                owner_character_id,
                now,
                now,
                None,
                "new",
            ),
        )
        await conn.commit()

        scope_id = cursor.lastrowid
        assert scope_id is not None, "INSERT should always return a lastrowid"

        return MarketScope(
            scope_id=scope_id,
            scope_name=scope_name,
            scope_type=scope_type,
            region_id=region_id,
            station_id=station_id,
            system_id=system_id,
            structure_id=structure_id,
            parent_region_id=parent_region_id,
            watchlist_id=watchlist_id,
            is_core=is_core,
            source=source,
            owner_character_id=owner_character_id,
            created_at=now,
            updated_at=now,
            last_scanned_at=None,
            last_scan_status="new",
        )

    async def get_scope(
        self,
        scope_name: str,
        owner_character_id: int | None = None,
    ) -> MarketScope | None:
        """
        Get a scope by name and owner.

        Args:
            scope_name: Scope name
            owner_character_id: Character ID (None = global)

        Returns:
            MarketScope if found, None otherwise
        """
        conn = await self._get_connection()

        if owner_character_id is None:
            async with conn.execute(
                """
                SELECT * FROM market_scopes
                WHERE scope_name = ? AND owner_character_id IS NULL
                """,
                (scope_name,),
            ) as cursor:
                row = await cursor.fetchone()
        else:
            async with conn.execute(
                """
                SELECT * FROM market_scopes
                WHERE scope_name = ? AND owner_character_id = ?
                """,
                (scope_name, owner_character_id),
            ) as cursor:
                row = await cursor.fetchone()

        return self._row_to_scope(row) if row else None

    async def get_scope_by_id(self, scope_id: int) -> MarketScope | None:
        """
        Get a scope by ID.

        Args:
            scope_id: Scope ID

        Returns:
            MarketScope if found, None otherwise
        """
        conn = await self._get_connection()
        async with conn.execute(
            "SELECT * FROM market_scopes WHERE scope_id = ?",
            (scope_id,),
        ) as cursor:
            row = await cursor.fetchone()

        return self._row_to_scope(row) if row else None

    async def list_scopes(
        self,
        owner_character_id: int | None = None,
        include_core: bool = True,
        include_global: bool = True,
    ) -> list[MarketScope]:
        """
        List scopes for an owner.

        When owner_character_id is provided, returns:
        - Owner's scopes
        - Global scopes (if include_global=True), which includes:
          - Core hub scopes (if include_core=True)
          - Global ad-hoc scopes

        Args:
            owner_character_id: Character ID (None = global only)
            include_core: Include core hub scopes in results
            include_global: Include global scopes when owner is provided

        Returns:
            List of MarketScope objects
        """
        conn = await self._get_connection()

        if owner_character_id is None:
            # Global only mode
            if include_core:
                async with conn.execute(
                    """
                    SELECT * FROM market_scopes
                    WHERE owner_character_id IS NULL
                    ORDER BY is_core DESC, scope_name
                    """
                ) as cursor:
                    rows = await cursor.fetchall()
            else:
                async with conn.execute(
                    """
                    SELECT * FROM market_scopes
                    WHERE owner_character_id IS NULL AND is_core = 0
                    ORDER BY scope_name
                    """
                ) as cursor:
                    rows = await cursor.fetchall()
        else:
            # Owner mode - include owner's scopes + optionally global scopes
            if include_global:
                if include_core:
                    # Owner scopes + all global scopes (core + ad-hoc)
                    async with conn.execute(
                        """
                        SELECT * FROM market_scopes
                        WHERE owner_character_id = ? OR owner_character_id IS NULL
                        ORDER BY is_core DESC, scope_name
                        """,
                        (owner_character_id,),
                    ) as cursor:
                        rows = await cursor.fetchall()
                else:
                    # Owner scopes + global ad-hoc scopes (no core)
                    async with conn.execute(
                        """
                        SELECT * FROM market_scopes
                        WHERE owner_character_id = ?
                           OR (owner_character_id IS NULL AND is_core = 0)
                        ORDER BY scope_name
                        """,
                        (owner_character_id,),
                    ) as cursor:
                        rows = await cursor.fetchall()
            else:
                # Owner scopes only (no global)
                async with conn.execute(
                    """
                    SELECT * FROM market_scopes
                    WHERE owner_character_id = ?
                    ORDER BY scope_name
                    """,
                    (owner_character_id,),
                ) as cursor:
                    rows = await cursor.fetchall()

        return [self._row_to_scope(row) for row in rows]

    async def resolve_scopes(
        self,
        scope_names: list[str],
        owner_character_id: int | None = None,
        include_core: bool = True,
    ) -> list[MarketScope]:
        """
        Resolve scope names with owner-shadows-global precedence.

        When owner_character_id is provided and a scope name exists in both
        the owner's scopes and global scopes, the owner's scope takes precedence
        (shadows the global one). This prevents double-scanning and ensures
        user customizations override system defaults.

        Args:
            scope_names: List of scope names to resolve
            owner_character_id: Character ID for precedence resolution
            include_core: Include core hub scopes in resolution

        Returns:
            List of resolved MarketScope objects (deduplicated by name)
        """
        if not scope_names:
            return []

        conn = await self._get_connection()
        resolved: dict[str, MarketScope] = {}

        # Build query with name filter
        placeholders = ",".join("?" * len(scope_names))

        if owner_character_id is None:
            # Global only - no shadowing needed
            if include_core:
                query = f"""
                    SELECT * FROM market_scopes
                    WHERE owner_character_id IS NULL
                      AND scope_name IN ({placeholders})
                    ORDER BY scope_name
                """
                async with conn.execute(query, scope_names) as cursor:
                    rows = await cursor.fetchall()
            else:
                query = f"""
                    SELECT * FROM market_scopes
                    WHERE owner_character_id IS NULL
                      AND is_core = 0
                      AND scope_name IN ({placeholders})
                    ORDER BY scope_name
                """
                async with conn.execute(query, scope_names) as cursor:
                    rows = await cursor.fetchall()

            for row in rows:
                scope = self._row_to_scope(row)
                resolved[scope.scope_name] = scope
        else:
            # Owner mode with shadowing: owner scopes take precedence
            # First, get global scopes
            if include_core:
                query = f"""
                    SELECT * FROM market_scopes
                    WHERE owner_character_id IS NULL
                      AND scope_name IN ({placeholders})
                """
            else:
                query = f"""
                    SELECT * FROM market_scopes
                    WHERE owner_character_id IS NULL
                      AND is_core = 0
                      AND scope_name IN ({placeholders})
                """
            async with conn.execute(query, scope_names) as cursor:
                rows = await cursor.fetchall()
            for row in rows:
                scope = self._row_to_scope(row)
                resolved[scope.scope_name] = scope

            # Then, overlay owner scopes (shadowing globals)
            query = f"""
                SELECT * FROM market_scopes
                WHERE owner_character_id = ?
                  AND scope_name IN ({placeholders})
            """
            async with conn.execute(query, [owner_character_id] + scope_names) as cursor:
                rows = await cursor.fetchall()
            for row in rows:
                scope = self._row_to_scope(row)
                resolved[scope.scope_name] = scope  # Overwrites global

        return list(resolved.values())

    async def delete_scope(self, scope_id: int) -> bool:
        """
        Delete a non-core scope and its prices (cascade).

        Core hub scopes cannot be deleted to maintain the hub-centric default
        invariant. Use _seed_core_scopes() to restore core hubs if needed.

        Args:
            scope_id: Scope ID to delete

        Returns:
            True if deleted, False if not found or is a core scope

        Raises:
            ValueError: If attempting to delete a core scope
        """
        conn = await self._get_connection()

        # Check if this is a core scope
        async with conn.execute(
            "SELECT is_core FROM market_scopes WHERE scope_id = ?",
            (scope_id,),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return False

        if row["is_core"]:
            raise ValueError(
                f"Cannot delete core hub scope (scope_id={scope_id}). "
                "Core hubs are protected to maintain the hub-centric default."
            )

        cursor = await conn.execute(
            "DELETE FROM market_scopes WHERE scope_id = ?",
            (scope_id,),
        )
        await conn.commit()
        return cursor.rowcount > 0

    async def update_scope_scan_status(
        self,
        scope_id: int,
        status: str,
        scanned_at: int | None = None,
    ) -> bool:
        """
        Update the scan status of a scope.

        Args:
            scope_id: Scope ID
            status: New status (new, complete, truncated, error)
            scanned_at: Timestamp of scan (default: now)

        Returns:
            True if updated, False if not found
        """
        conn = await self._get_connection()
        now = int(time.time())

        cursor = await conn.execute(
            """
            UPDATE market_scopes
            SET last_scan_status = ?, last_scanned_at = ?, updated_at = ?
            WHERE scope_id = ?
            """,
            (status, scanned_at or now, now, scope_id),
        )
        await conn.commit()
        return cursor.rowcount > 0

    def _row_to_scope(self, row: aiosqlite.Row) -> MarketScope:
        """Convert database row to MarketScope."""
        return MarketScope(
            scope_id=row["scope_id"],
            scope_name=row["scope_name"],
            scope_type=row["scope_type"],
            region_id=row["region_id"],
            station_id=row["station_id"],
            system_id=row["system_id"],
            structure_id=row["structure_id"],
            parent_region_id=row["parent_region_id"],
            watchlist_id=row["watchlist_id"],
            is_core=bool(row["is_core"]),
            source=row["source"],
            owner_character_id=row["owner_character_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_scanned_at=row["last_scanned_at"],
            last_scan_status=row["last_scan_status"],
        )

    # =========================================================================
    # Market Scope Price Operations
    # =========================================================================

    async def upsert_scope_price(self, price: MarketScopePrice) -> None:
        """
        Insert or update a scope price record.

        Args:
            price: MarketScopePrice to upsert
        """
        conn = await self._get_connection()
        await conn.execute(
            """
            INSERT OR REPLACE INTO market_scope_prices (
                scope_id, type_id, buy_max, buy_volume, sell_min, sell_volume,
                spread_pct, order_count_buy, order_count_sell, updated_at,
                http_last_modified, http_expires, source, coverage_type, fetch_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                price.scope_id,
                price.type_id,
                price.buy_max,
                price.buy_volume,
                price.sell_min,
                price.sell_volume,
                price.spread_pct,
                price.order_count_buy,
                price.order_count_sell,
                price.updated_at,
                price.http_last_modified,
                price.http_expires,
                price.source,
                price.coverage_type,
                price.fetch_status,
            ),
        )
        await conn.commit()

    async def upsert_scope_prices_batch(
        self,
        prices: Sequence[MarketScopePrice],
    ) -> int:
        """
        Insert or update multiple scope price records.

        Args:
            prices: List of MarketScopePrice objects

        Returns:
            Number of rows affected
        """
        if not prices:
            return 0

        conn = await self._get_connection()
        await conn.executemany(
            """
            INSERT OR REPLACE INTO market_scope_prices (
                scope_id, type_id, buy_max, buy_volume, sell_min, sell_volume,
                spread_pct, order_count_buy, order_count_sell, updated_at,
                http_last_modified, http_expires, source, coverage_type, fetch_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    p.scope_id,
                    p.type_id,
                    p.buy_max,
                    p.buy_volume,
                    p.sell_min,
                    p.sell_volume,
                    p.spread_pct,
                    p.order_count_buy,
                    p.order_count_sell,
                    p.updated_at,
                    p.http_last_modified,
                    p.http_expires,
                    p.source,
                    p.coverage_type,
                    p.fetch_status,
                )
                for p in prices
            ],
        )
        await conn.commit()
        return len(prices)

    async def get_scope_price(
        self,
        scope_id: int,
        type_id: int,
    ) -> MarketScopePrice | None:
        """
        Get a single scope price record.

        Args:
            scope_id: Scope ID
            type_id: Type ID

        Returns:
            MarketScopePrice if found, None otherwise
        """
        conn = await self._get_connection()
        async with conn.execute(
            """
            SELECT * FROM market_scope_prices
            WHERE scope_id = ? AND type_id = ?
            """,
            (scope_id, type_id),
        ) as cursor:
            row = await cursor.fetchone()

        return self._row_to_scope_price(row) if row else None

    async def get_scope_prices_for_arbitrage(
        self,
        scope_ids: list[int],
        max_age_seconds: int = 3600,
    ) -> list[dict]:
        """
        Get scope prices joined with scope metadata for arbitrage analysis.

        Returns price data with scope details needed for arbitrage opportunity
        detection, including scope name, type, region ID, and fetch status.

        Args:
            scope_ids: List of scope IDs to query
            max_age_seconds: Maximum age of data to include (default: 1 hour)

        Returns:
            List of dicts with price data + scope metadata:
            - All MarketScopePrice fields
            - scope_name, scope_type, last_scan_status, region_id
            - type_name, volume, packaged_volume from types table
        """
        if not scope_ids:
            return []

        conn = await self._get_connection()
        cutoff = int(time.time()) - max_age_seconds

        placeholders = ",".join("?" * len(scope_ids))
        query = f"""
            SELECT
                p.scope_id,
                p.type_id,
                p.buy_max,
                p.buy_volume,
                p.sell_min,
                p.sell_volume,
                p.spread_pct,
                p.order_count_buy,
                p.order_count_sell,
                p.updated_at,
                p.http_last_modified,
                p.http_expires,
                p.source,
                p.coverage_type,
                p.fetch_status,
                s.scope_name,
                s.scope_type,
                s.last_scan_status,
                s.region_id AS scope_region_id,
                COALESCE(t.type_name, 'Type ' || p.type_id) AS type_name,
                t.volume,
                t.packaged_volume
            FROM market_scope_prices p
            JOIN market_scopes s ON s.scope_id = p.scope_id
            LEFT JOIN types t ON t.type_id = p.type_id
            WHERE p.scope_id IN ({placeholders})
              AND p.updated_at > ?
              AND (p.buy_max IS NOT NULL OR p.sell_min IS NOT NULL)
            ORDER BY p.type_id, p.scope_id
        """

        async with conn.execute(query, [*scope_ids, cutoff]) as cursor:
            rows = await cursor.fetchall()

        return [dict(row) for row in rows]

    async def get_scope_prices(
        self,
        scope_id: int,
        max_age_seconds: int | None = None,
    ) -> list[MarketScopePrice]:
        """
        Get all prices for a scope.

        Args:
            scope_id: Scope ID
            max_age_seconds: Optional max age filter

        Returns:
            List of MarketScopePrice objects
        """
        conn = await self._get_connection()

        if max_age_seconds is not None:
            cutoff = int(time.time()) - max_age_seconds
            async with conn.execute(
                """
                SELECT * FROM market_scope_prices
                WHERE scope_id = ? AND updated_at > ?
                ORDER BY type_id
                """,
                (scope_id, cutoff),
            ) as cursor:
                rows = await cursor.fetchall()
        else:
            async with conn.execute(
                """
                SELECT * FROM market_scope_prices
                WHERE scope_id = ?
                ORDER BY type_id
                """,
                (scope_id,),
            ) as cursor:
                rows = await cursor.fetchall()

        return [self._row_to_scope_price(row) for row in rows]

    async def clear_scope_prices(self, scope_id: int) -> int:
        """
        Delete all prices for a scope.

        Args:
            scope_id: Scope ID

        Returns:
            Number of rows deleted
        """
        conn = await self._get_connection()
        cursor = await conn.execute(
            "DELETE FROM market_scope_prices WHERE scope_id = ?",
            (scope_id,),
        )
        await conn.commit()
        return cursor.rowcount

    def _row_to_scope_price(self, row: aiosqlite.Row) -> MarketScopePrice:
        """Convert database row to MarketScopePrice."""
        return MarketScopePrice(
            scope_id=row["scope_id"],
            type_id=row["type_id"],
            buy_max=row["buy_max"],
            buy_volume=row["buy_volume"] or 0,
            sell_min=row["sell_min"],
            sell_volume=row["sell_volume"] or 0,
            spread_pct=row["spread_pct"],
            order_count_buy=row["order_count_buy"] or 0,
            order_count_sell=row["order_count_sell"] or 0,
            updated_at=row["updated_at"],
            http_last_modified=row["http_last_modified"],
            http_expires=row["http_expires"],
            source=row["source"],
            coverage_type=row["coverage_type"],
            fetch_status=row["fetch_status"],
        )


# =============================================================================
# Singleton Management
# =============================================================================

_async_market_db: AsyncMarketDatabase | None = None


async def get_async_market_database() -> AsyncMarketDatabase:
    """Get or create the async market database singleton."""
    global _async_market_db
    if _async_market_db is None:
        _async_market_db = AsyncMarketDatabase()
    return _async_market_db


async def reset_async_market_database() -> None:
    """Reset the async market database singleton (async version)."""
    global _async_market_db
    if _async_market_db:
        await _async_market_db.close()
        _async_market_db = None


def reset_async_market_database_sync() -> None:
    """
    Reset the async market database singleton (sync version for testing).

    This is a synchronous reset that clears the singleton without awaiting
    the close() coroutine. Use in test fixtures where an event loop may
    not be running. The connection will be cleaned up on garbage collection.
    """
    global _async_market_db
    _async_market_db = None
