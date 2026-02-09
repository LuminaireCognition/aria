"""
Market Database for ARIA.

SQLite-backed storage for market data, type resolution, and caching.
Supports bulk CSV import from Fuzzwork and fuzzy name matching.
"""

from __future__ import annotations

import csv
import io
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ...core.config import get_settings
from ...core.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = get_logger(__name__)

# =============================================================================
# Constants
# =============================================================================

# Schema version for migrations
SCHEMA_VERSION = 8

# Common item categories for pre-warming
COMMON_ITEM_CATEGORIES = [
    "minerals",  # Tritanium, Pyerite, etc.
    "salvage",  # Salvage materials
    "planetary",  # PI commodities
    "fuel",  # Fuel blocks
    "ore",  # Raw ores
]

# Fuzzy matching thresholds
MAX_LEVENSHTEIN_DISTANCE = 3
MIN_PREFIX_LENGTH = 3


# =============================================================================
# Database Schema
# =============================================================================

SCHEMA_SQL = """
-- Type information from SDE
CREATE TABLE IF NOT EXISTS types (
    type_id INTEGER PRIMARY KEY,
    type_name TEXT NOT NULL,
    type_name_lower TEXT NOT NULL,
    group_id INTEGER,
    category_id INTEGER,
    market_group_id INTEGER,
    volume REAL,
    packaged_volume REAL
);

CREATE INDEX IF NOT EXISTS idx_types_name_lower ON types(type_name_lower);
CREATE INDEX IF NOT EXISTS idx_types_market_group ON types(market_group_id);

-- Cached price aggregates from Fuzzwork
CREATE TABLE IF NOT EXISTS aggregates (
    type_id INTEGER PRIMARY KEY,
    region_id INTEGER NOT NULL,
    station_id INTEGER,
    buy_weighted_avg REAL,
    buy_max REAL,
    buy_min REAL,
    buy_stddev REAL,
    buy_median REAL,
    buy_volume INTEGER,
    buy_order_count INTEGER,
    buy_percentile REAL,
    sell_weighted_avg REAL,
    sell_max REAL,
    sell_min REAL,
    sell_stddev REAL,
    sell_median REAL,
    sell_volume INTEGER,
    sell_order_count INTEGER,
    sell_percentile REAL,
    updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_aggregates_region ON aggregates(region_id);
CREATE INDEX IF NOT EXISTS idx_aggregates_updated ON aggregates(updated_at);

-- Common items for pre-warming cache
CREATE TABLE IF NOT EXISTS common_items (
    type_id INTEGER PRIMARY KEY,
    category TEXT NOT NULL,
    priority INTEGER DEFAULT 0
);

-- Database metadata
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Market history cache for daily volume data
CREATE TABLE IF NOT EXISTS market_history_cache (
    type_id INTEGER NOT NULL,
    region_id INTEGER NOT NULL,
    avg_daily_volume INTEGER,
    avg_daily_isk REAL,
    volatility_pct REAL,
    updated_at INTEGER,
    PRIMARY KEY (type_id, region_id)
);

CREATE INDEX IF NOT EXISTS idx_history_updated ON market_history_cache(updated_at);

-- ============================================================================
-- Arbitrage Schema: Region prices and tracking tables
-- ============================================================================

-- Region Prices: Snapshot prices per region for cross-region comparison
-- Updated by MarketRefreshService on TTL expiry or force refresh
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
);

CREATE INDEX IF NOT EXISTS idx_region_prices_region ON region_prices(region_id);
CREATE INDEX IF NOT EXISTS idx_region_prices_updated ON region_prices(updated_at);
CREATE INDEX IF NOT EXISTS idx_region_prices_sell ON region_prices(region_id, sell_min);
CREATE INDEX IF NOT EXISTS idx_region_prices_buy ON region_prices(region_id, buy_max);

-- Region Item Tracking: Items worth monitoring per region
-- Tracks which items have sufficient market activity to be worth monitoring
CREATE TABLE IF NOT EXISTS region_item_tracking (
    region_id INTEGER NOT NULL,
    type_id INTEGER NOT NULL,
    avg_daily_volume REAL DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    last_checked INTEGER NOT NULL,
    PRIMARY KEY (region_id, type_id)
);

CREATE INDEX IF NOT EXISTS idx_tracking_active ON region_item_tracking(is_active);
CREATE INDEX IF NOT EXISTS idx_tracking_volume ON region_item_tracking(avg_daily_volume);

-- Arbitrage Opportunities: Computed opportunities cache
-- Opportunities are ephemeral - cleared and recalculated on each scan
CREATE TABLE IF NOT EXISTS arbitrage_opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type_id INTEGER NOT NULL,
    type_name TEXT NOT NULL,
    buy_region_id INTEGER NOT NULL,
    buy_region_name TEXT NOT NULL,
    sell_region_id INTEGER NOT NULL,
    sell_region_name TEXT NOT NULL,
    buy_price REAL NOT NULL,
    sell_price REAL NOT NULL,
    profit_per_unit REAL NOT NULL,
    profit_pct REAL NOT NULL,
    available_volume INTEGER NOT NULL,
    detected_at INTEGER NOT NULL,
    route_jumps INTEGER,
    route_safe INTEGER DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_arb_profit ON arbitrage_opportunities(profit_pct DESC);
CREATE INDEX IF NOT EXISTS idx_arb_detected ON arbitrage_opportunities(detected_at);
CREATE INDEX IF NOT EXISTS idx_arb_type ON arbitrage_opportunities(type_id);

-- Region Refresh Tracking: Track when each region was last refreshed
CREATE TABLE IF NOT EXISTS region_refresh_tracking (
    region_id INTEGER PRIMARY KEY,
    region_name TEXT NOT NULL,
    last_refresh INTEGER NOT NULL,
    items_refreshed INTEGER DEFAULT 0,
    refresh_duration_ms INTEGER DEFAULT 0
);

-- ============================================================================
-- Hub-Centric Market Engine: Ad-hoc Market Schema
-- ============================================================================

-- Watchlists: Named item lists for scoped market fetching
CREATE TABLE IF NOT EXISTS watchlists (
    watchlist_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    owner_character_id INTEGER,         -- null = global/system list; INTEGER = immutable character ID
    created_at INTEGER NOT NULL
);
-- Partial indexes to enforce uniqueness for both global (NULL) and character-owned lists
CREATE UNIQUE INDEX IF NOT EXISTS idx_watchlists_owner ON watchlists(name, owner_character_id) WHERE owner_character_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_watchlists_global ON watchlists(name) WHERE owner_character_id IS NULL;

-- Watchlist Items: Items in a watchlist
CREATE TABLE IF NOT EXISTS watchlist_items (
    watchlist_id INTEGER NOT NULL,
    type_id INTEGER NOT NULL,
    added_at INTEGER NOT NULL,
    PRIMARY KEY (watchlist_id, type_id),
    FOREIGN KEY (watchlist_id) REFERENCES watchlists(watchlist_id) ON DELETE CASCADE
);

-- Market Scopes: Core and ad-hoc market scope definitions
CREATE TABLE IF NOT EXISTS market_scopes (
    scope_id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope_name TEXT NOT NULL,
    scope_type TEXT NOT NULL CHECK(scope_type IN ('hub_region', 'region', 'station', 'system', 'structure')),

    -- Location IDs (Exactly one must be set - enforced by CHECK)
    region_id INTEGER,
    station_id INTEGER,
    system_id INTEGER,
    structure_id INTEGER,

    -- Optimization for station/system/structure scopes to avoid ESI lookups
    parent_region_id INTEGER,

    watchlist_id INTEGER,               -- Mandatory for ad-hoc scopes, NULL for core

    is_core INTEGER DEFAULT 0,          -- 1 for default trade hubs
    source TEXT NOT NULL,               -- fuzzwork | esi
    owner_character_id INTEGER,         -- optional: character/persona association (immutable ID)
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,

    -- Fetch Metadata (Scope Level)
    last_scanned_at INTEGER,            -- Timestamp of last attempt
    last_scan_status TEXT DEFAULT 'new', -- 'new' | 'complete' | 'truncated' | 'error'

    FOREIGN KEY (watchlist_id) REFERENCES watchlists(watchlist_id) ON DELETE CASCADE,

    CHECK (
        last_scan_status IN ('new', 'complete', 'truncated', 'error')
    ),
    CHECK (
        -- Location exclusivity and Type binding
        (scope_type IN ('region', 'hub_region') AND region_id IS NOT NULL AND station_id IS NULL AND system_id IS NULL AND structure_id IS NULL) OR
        (scope_type = 'station' AND region_id IS NULL AND station_id IS NOT NULL AND system_id IS NULL AND structure_id IS NULL) OR
        (scope_type = 'system' AND region_id IS NULL AND station_id IS NULL AND system_id IS NOT NULL AND structure_id IS NULL) OR
        (scope_type = 'structure' AND region_id IS NULL AND station_id IS NULL AND system_id IS NULL AND structure_id IS NOT NULL)
    ),
    CHECK (
        -- Core hubs use Fuzzwork, NO watchlist, and must be global; Ad-hoc use ESI and MUST have watchlist
        (is_core = 1 AND source = 'fuzzwork' AND watchlist_id IS NULL AND scope_type = 'hub_region' AND owner_character_id IS NULL) OR
        (is_core = 0 AND source = 'esi' AND watchlist_id IS NOT NULL AND scope_type IN ('region', 'station', 'system', 'structure'))
    )
);
-- Partial indexes for scope uniqueness
CREATE UNIQUE INDEX IF NOT EXISTS idx_market_scopes_owner ON market_scopes(scope_name, owner_character_id) WHERE owner_character_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_market_scopes_global ON market_scopes(scope_name) WHERE owner_character_id IS NULL;

-- Market Scope Prices: Aggregated prices for ad-hoc scopes
CREATE TABLE IF NOT EXISTS market_scope_prices (
    scope_id INTEGER NOT NULL,
    type_id INTEGER NOT NULL,
    buy_max REAL,
    buy_volume INTEGER DEFAULT 0,
    sell_min REAL,
    sell_volume INTEGER DEFAULT 0,
    spread_pct REAL,
    order_count_buy INTEGER DEFAULT 0,
    order_count_sell INTEGER DEFAULT 0,

    updated_at INTEGER NOT NULL,        -- Local fetch time (Unix Timestamp)
    http_last_modified INTEGER,         -- From ESI Header (Unix Timestamp)
    http_expires INTEGER,               -- From ESI Header (Unix Timestamp)

    source TEXT NOT NULL,               -- esi
    coverage_type TEXT NOT NULL,        -- 'watchlist' (Ad-hoc only)
    fetch_status TEXT NOT NULL,         -- 'complete' | 'truncated' | 'skipped_truncation'

    PRIMARY KEY (scope_id, type_id),
    FOREIGN KEY (scope_id) REFERENCES market_scopes(scope_id) ON DELETE CASCADE,
    CHECK (fetch_status IN ('complete', 'truncated', 'skipped_truncation')),
    -- Ad-hoc scopes are ESI-backed with watchlist coverage only
    CHECK (source = 'esi'),
    CHECK (coverage_type = 'watchlist')
);

-- ============================================================================
-- RedisQ Real-Time Intelligence Schema
-- ============================================================================

-- Realtime kills from RedisQ
CREATE TABLE IF NOT EXISTS realtime_kills (
    kill_id INTEGER PRIMARY KEY,
    kill_time INTEGER NOT NULL,
    solar_system_id INTEGER NOT NULL,
    victim_ship_type_id INTEGER,
    victim_corporation_id INTEGER,
    victim_alliance_id INTEGER,
    attacker_count INTEGER,
    attacker_corps TEXT,              -- JSON array of corporation IDs
    attacker_alliances TEXT,          -- JSON array of alliance IDs
    attacker_ship_types TEXT,         -- JSON array of ship type IDs
    final_blow_ship_type_id INTEGER,
    total_value REAL,
    is_pod_kill INTEGER DEFAULT 0,
    created_at INTEGER DEFAULT (strftime('%s', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_kills_system_time ON realtime_kills(solar_system_id, kill_time);
CREATE INDEX IF NOT EXISTS idx_kills_time ON realtime_kills(kill_time);

-- RedisQ service state persistence
CREATE TABLE IF NOT EXISTS redisq_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at INTEGER NOT NULL
);

-- Gatecamp detections for backtesting analysis
CREATE TABLE IF NOT EXISTS gatecamp_detections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    system_id INTEGER NOT NULL,
    detected_at INTEGER NOT NULL,
    confidence TEXT,
    kill_count INTEGER,
    attacker_corps TEXT,               -- JSON array for post-hoc analysis
    force_asymmetry REAL,
    is_smartbomb INTEGER DEFAULT 0,
    created_at INTEGER DEFAULT (strftime('%s', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_detections_system_time ON gatecamp_detections(system_id, detected_at);

-- ============================================================================
-- Entity Tracking Schema (Phase 4)
-- ============================================================================

-- Entity watchlists for tracking corps/alliances
CREATE TABLE IF NOT EXISTS entity_watchlists (
    watchlist_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    watchlist_type TEXT NOT NULL CHECK(watchlist_type IN ('manual', 'war_targets', 'contacts')),
    owner_character_id INTEGER,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_entity_watchlists_owner
    ON entity_watchlists(name, owner_character_id) WHERE owner_character_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_entity_watchlists_global
    ON entity_watchlists(name) WHERE owner_character_id IS NULL;

-- Watchlist items (corps/alliances being tracked)
CREATE TABLE IF NOT EXISTS entity_watchlist_items (
    watchlist_id INTEGER NOT NULL,
    entity_id INTEGER NOT NULL,
    entity_type TEXT NOT NULL CHECK(entity_type IN ('corporation', 'alliance')),
    entity_name TEXT,
    added_at INTEGER NOT NULL,
    added_reason TEXT,
    PRIMARY KEY (watchlist_id, entity_id, entity_type),
    FOREIGN KEY (watchlist_id) REFERENCES entity_watchlists(watchlist_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_entity_items_entity ON entity_watchlist_items(entity_id, entity_type);

-- ============================================================================
-- War Context Schema (Phase 5)
-- ============================================================================

-- Known wars for war engagement detection
-- Tracks both ESI-synced wars and inferred wars from kill patterns
CREATE TABLE IF NOT EXISTS known_wars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    aggressor_alliance_id INTEGER,
    aggressor_corp_id INTEGER,
    defender_alliance_id INTEGER,
    defender_corp_id INTEGER,
    is_mutual INTEGER DEFAULT 0,
    source TEXT NOT NULL,              -- 'esi_sync' or 'inferred'
    first_observed INTEGER NOT NULL,
    last_observed INTEGER NOT NULL,
    kill_count INTEGER DEFAULT 1,
    UNIQUE(aggressor_alliance_id, defender_alliance_id)
);

CREATE INDEX IF NOT EXISTS idx_known_wars_aggressor ON known_wars(aggressor_alliance_id);
CREATE INDEX IF NOT EXISTS idx_known_wars_defender ON known_wars(defender_alliance_id);
CREATE INDEX IF NOT EXISTS idx_known_wars_last_observed ON known_wars(last_observed);

-- Insert schema version
INSERT OR REPLACE INTO metadata (key, value) VALUES ('schema_version', '8');
"""


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class TypeInfo:
    """Basic type information from database."""

    type_id: int
    type_name: str
    group_id: int | None = None
    category_id: int | None = None
    market_group_id: int | None = None
    volume: float | None = None


@dataclass
class CachedAggregate:
    """Cached price aggregate with metadata."""

    type_id: int
    region_id: int
    station_id: int | None
    buy_weighted_avg: float | None
    buy_max: float | None
    buy_min: float | None
    buy_stddev: float | None
    buy_median: float | None
    buy_volume: int
    buy_order_count: int
    buy_percentile: float | None
    sell_weighted_avg: float | None
    sell_max: float | None
    sell_min: float | None
    sell_stddev: float | None
    sell_median: float | None
    sell_volume: int
    sell_order_count: int
    sell_percentile: float | None
    updated_at: int  # Unix timestamp


@dataclass
class CachedHistory:
    """Cached market history summary for daily volume calculations."""

    type_id: int
    region_id: int
    avg_daily_volume: int | None
    avg_daily_isk: float | None
    volatility_pct: float | None
    updated_at: int  # Unix timestamp


# =============================================================================
# Hub-Centric Market Engine Data Classes
# =============================================================================


@dataclass
class Watchlist:
    """Named list of items for scoped market fetching."""

    watchlist_id: int
    name: str
    owner_character_id: int | None  # None = global/system list
    created_at: int  # Unix timestamp


@dataclass
class WatchlistItem:
    """Item in a watchlist."""

    watchlist_id: int
    type_id: int
    added_at: int  # Unix timestamp


@dataclass
class MarketScope:
    """Market scope definition (core hub or ad-hoc)."""

    scope_id: int
    scope_name: str
    scope_type: str  # ScopeType: hub_region | region | station | system | structure
    region_id: int | None
    station_id: int | None
    system_id: int | None
    structure_id: int | None
    parent_region_id: int | None
    watchlist_id: int | None
    is_core: bool
    source: str  # ScopeSource: fuzzwork | esi
    owner_character_id: int | None
    created_at: int  # Unix timestamp
    updated_at: int  # Unix timestamp
    last_scanned_at: int | None
    last_scan_status: str  # ScanStatus: new | complete | truncated | error


@dataclass
class MarketScopePrice:
    """Aggregated price data for a scope/type combination."""

    scope_id: int
    type_id: int
    buy_max: float | None
    buy_volume: int
    sell_min: float | None
    sell_volume: int
    spread_pct: float | None
    order_count_buy: int
    order_count_sell: int
    updated_at: int  # Unix timestamp
    http_last_modified: int | None
    http_expires: int | None
    source: str
    coverage_type: str
    fetch_status: str  # FetchStatus: complete | truncated | skipped_truncation


# =============================================================================
# Database Class
# =============================================================================


class MarketDatabase:
    """
    SQLite database for market data.

    Handles type resolution, price caching, and bulk imports.
    Thread-safe for read operations; write operations should be serialized.
    """

    def __init__(self, db_path: Path | str | None = None):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database. Defaults to {instance_root}/cache/aria.db
        """
        if db_path is None:
            db_path = get_settings().db_path
        self.db_path = Path(db_path)

        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn: sqlite3.Connection | None = None
        self._initialized = False

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,  # Allow multi-thread reads
            )
            self._conn.row_factory = sqlite3.Row
            # Enable foreign key constraints for cascade deletes
            self._conn.execute("PRAGMA foreign_keys = ON")

            if not self._initialized:
                self._initialize_schema()
                self._initialized = True

        return self._conn

    def _initialize_schema(self) -> None:
        """Create database schema if needed and run migrations."""
        conn = self._conn
        if conn is None:
            return

        # Check current schema version
        current_version = self._get_schema_version()

        # Run migrations if needed
        if current_version < SCHEMA_VERSION:
            self._run_migrations(current_version)

        # Run full schema (IF NOT EXISTS is safe for existing tables)
        conn.executescript(SCHEMA_SQL)
        conn.commit()

        # Seed core trade hub scopes (after schema exists)
        self._seed_core_scopes()

        logger.info("Market database initialized at %s", self.db_path)

    def _get_schema_version(self) -> int:
        """Get current schema version from metadata table."""
        conn = self._conn
        if conn is None:
            return 0

        try:
            row = conn.execute("SELECT value FROM metadata WHERE key = 'schema_version'").fetchone()
            return int(row["value"]) if row else 0
        except sqlite3.OperationalError:
            # metadata table doesn't exist yet
            return 0

    def _run_migrations(self, from_version: int) -> None:
        """Run schema migrations from current version to SCHEMA_VERSION."""
        conn = self._conn
        if conn is None:
            return

        # Migration 4 -> 5: Add RedisQ real-time intel tables
        if from_version < 5:
            logger.info("Running migration 4 -> 5: Adding RedisQ tables")
            conn.executescript("""
                -- Realtime kills from RedisQ
                CREATE TABLE IF NOT EXISTS realtime_kills (
                    kill_id INTEGER PRIMARY KEY,
                    kill_time INTEGER NOT NULL,
                    solar_system_id INTEGER NOT NULL,
                    victim_ship_type_id INTEGER,
                    victim_corporation_id INTEGER,
                    victim_alliance_id INTEGER,
                    attacker_count INTEGER,
                    attacker_corps TEXT,
                    attacker_alliances TEXT,
                    attacker_ship_types TEXT,
                    final_blow_ship_type_id INTEGER,
                    total_value REAL,
                    is_pod_kill INTEGER DEFAULT 0,
                    created_at INTEGER DEFAULT (strftime('%s', 'now'))
                );

                CREATE INDEX IF NOT EXISTS idx_kills_system_time ON realtime_kills(solar_system_id, kill_time);
                CREATE INDEX IF NOT EXISTS idx_kills_time ON realtime_kills(kill_time);

                -- RedisQ service state persistence
                CREATE TABLE IF NOT EXISTS redisq_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at INTEGER NOT NULL
                );
            """)
            conn.commit()
            logger.info("Migration 4 -> 5 complete")

        # Migration 5 -> 6: Add gatecamp detections table
        if from_version < 6:
            logger.info("Running migration 5 -> 6: Adding gatecamp_detections table")
            conn.executescript("""
                -- Gatecamp detections for backtesting analysis
                CREATE TABLE IF NOT EXISTS gatecamp_detections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    system_id INTEGER NOT NULL,
                    detected_at INTEGER NOT NULL,
                    confidence TEXT,
                    kill_count INTEGER,
                    attacker_corps TEXT,
                    force_asymmetry REAL,
                    is_smartbomb INTEGER DEFAULT 0,
                    created_at INTEGER DEFAULT (strftime('%s', 'now'))
                );

                CREATE INDEX IF NOT EXISTS idx_detections_system_time ON gatecamp_detections(system_id, detected_at);
            """)
            conn.commit()
            logger.info("Migration 5 -> 6 complete")

        # Migration 6 -> 7: Add entity watchlist tables and kill entity tracking
        if from_version < 7:
            logger.info("Running migration 6 -> 7: Adding entity tracking tables")
            conn.executescript("""
                -- Entity watchlists for tracking corps/alliances
                CREATE TABLE IF NOT EXISTS entity_watchlists (
                    watchlist_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    watchlist_type TEXT NOT NULL CHECK(watchlist_type IN ('manual', 'war_targets', 'contacts')),
                    owner_character_id INTEGER,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_entity_watchlists_owner
                    ON entity_watchlists(name, owner_character_id) WHERE owner_character_id IS NOT NULL;
                CREATE UNIQUE INDEX IF NOT EXISTS idx_entity_watchlists_global
                    ON entity_watchlists(name) WHERE owner_character_id IS NULL;

                -- Watchlist items (corps/alliances being tracked)
                CREATE TABLE IF NOT EXISTS entity_watchlist_items (
                    watchlist_id INTEGER NOT NULL,
                    entity_id INTEGER NOT NULL,
                    entity_type TEXT NOT NULL CHECK(entity_type IN ('corporation', 'alliance')),
                    entity_name TEXT,
                    added_at INTEGER NOT NULL,
                    added_reason TEXT,
                    PRIMARY KEY (watchlist_id, entity_id, entity_type),
                    FOREIGN KEY (watchlist_id) REFERENCES entity_watchlists(watchlist_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_entity_items_entity ON entity_watchlist_items(entity_id, entity_type);
            """)
            # Add watched entity columns to realtime_kills if they don't exist
            # SQLite doesn't have IF NOT EXISTS for ALTER TABLE, so check first
            cursor = conn.execute("PRAGMA table_info(realtime_kills)")
            columns = {row[1] for row in cursor.fetchall()}
            if "watched_entity_match" not in columns:
                conn.execute(
                    "ALTER TABLE realtime_kills ADD COLUMN watched_entity_match INTEGER DEFAULT 0"
                )
            if "watched_entity_ids" not in columns:
                conn.execute("ALTER TABLE realtime_kills ADD COLUMN watched_entity_ids TEXT")
            conn.commit()
            logger.info("Migration 6 -> 7 complete")

        # Migration 7 -> 8: Add known wars table for war context detection
        if from_version < 8:
            logger.info("Running migration 7 -> 8: Adding known_wars table")
            conn.executescript("""
                -- Known wars for war engagement detection
                CREATE TABLE IF NOT EXISTS known_wars (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    aggressor_alliance_id INTEGER,
                    aggressor_corp_id INTEGER,
                    defender_alliance_id INTEGER,
                    defender_corp_id INTEGER,
                    is_mutual INTEGER DEFAULT 0,
                    source TEXT NOT NULL,
                    first_observed INTEGER NOT NULL,
                    last_observed INTEGER NOT NULL,
                    kill_count INTEGER DEFAULT 1,
                    UNIQUE(aggressor_alliance_id, defender_alliance_id)
                );

                CREATE INDEX IF NOT EXISTS idx_known_wars_aggressor ON known_wars(aggressor_alliance_id);
                CREATE INDEX IF NOT EXISTS idx_known_wars_defender ON known_wars(defender_alliance_id);
                CREATE INDEX IF NOT EXISTS idx_known_wars_last_observed ON known_wars(last_observed);
            """)
            conn.commit()
            logger.info("Migration 7 -> 8 complete")

    def _seed_core_scopes(self) -> None:
        """
        Seed core trade hub scopes if they don't exist.

        Creates 5 core hub_region scopes for the major trade hubs:
        - Jita (The Forge)
        - Amarr (Domain)
        - Dodixie (Sinq Laison)
        - Rens (Heimatar)
        - Hek (Metropolis)

        This is idempotent - skips if scopes already exist.
        """
        # Core trade hub definitions
        core_hubs = [
            {"name": "Jita", "region_id": 10000002},
            {"name": "Amarr", "region_id": 10000043},
            {"name": "Dodixie", "region_id": 10000032},
            {"name": "Rens", "region_id": 10000030},
            {"name": "Hek", "region_id": 10000042},
        ]

        conn = self._get_connection()
        now = int(time.time())

        for hub in core_hubs:
            # Check if core hub scope already exists (only skip if it's actually a core scope)
            existing = conn.execute(
                """
                SELECT scope_id FROM market_scopes
                WHERE scope_name = ? AND owner_character_id IS NULL AND is_core = 1
                """,
                (hub["name"],),
            ).fetchone()

            if existing:
                continue

            # Insert core hub scope
            conn.execute(
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
                    None,  # station_id
                    None,  # system_id
                    None,  # structure_id
                    None,  # parent_region_id
                    None,  # watchlist_id (core scopes don't use watchlists)
                    1,  # is_core = True
                    "fuzzwork",  # source
                    None,  # owner_character_id (global)
                    now,
                    now,
                    None,  # last_scanned_at
                    "new",  # last_scan_status
                ),
            )
            logger.debug("Seeded core hub scope: %s", hub["name"])

        conn.commit()

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    # =========================================================================
    # Type Resolution
    # =========================================================================

    def resolve_type_name(self, name: str) -> TypeInfo | None:
        """
        Resolve item name to type info.

        Tries exact match first, then case-insensitive, then fuzzy.

        Args:
            name: Item name to resolve

        Returns:
            TypeInfo if found, None otherwise
        """
        conn = self._get_connection()
        name_lower = name.lower().strip()

        # Try exact match (case-insensitive)
        row = conn.execute(
            "SELECT * FROM types WHERE type_name_lower = ?",
            (name_lower,),
        ).fetchone()

        if row:
            return self._row_to_type_info(row)

        # Try prefix match
        row = conn.execute(
            "SELECT * FROM types WHERE type_name_lower LIKE ? LIMIT 1",
            (f"{name_lower}%",),
        ).fetchone()

        if row:
            return self._row_to_type_info(row)

        # Try contains match
        row = conn.execute(
            "SELECT * FROM types WHERE type_name_lower LIKE ? LIMIT 1",
            (f"%{name_lower}%",),
        ).fetchone()

        if row:
            return self._row_to_type_info(row)

        return None

    def resolve_type_id(self, type_id: int) -> TypeInfo | None:
        """
        Get type info by ID.

        Args:
            type_id: Type ID to look up

        Returns:
            TypeInfo if found
        """
        conn = self._get_connection()
        row = conn.execute(
            "SELECT * FROM types WHERE type_id = ?",
            (type_id,),
        ).fetchone()

        return self._row_to_type_info(row) if row else None

    def find_type_suggestions(self, name: str, limit: int = 5) -> list[str]:
        """
        Find type name suggestions for fuzzy matching.

        Args:
            name: Partial or misspelled name
            limit: Maximum suggestions to return

        Returns:
            List of suggested type names
        """
        conn = self._get_connection()
        name_lower = name.lower().strip()

        # Start with prefix matches
        rows = conn.execute(
            """
            SELECT type_name FROM types
            WHERE type_name_lower LIKE ?
            ORDER BY length(type_name)
            LIMIT ?
            """,
            (f"{name_lower}%", limit),
        ).fetchall()

        suggestions = [row["type_name"] for row in rows]

        if len(suggestions) < limit:
            # Add contains matches
            remaining = limit - len(suggestions)
            rows = conn.execute(
                """
                SELECT type_name FROM types
                WHERE type_name_lower LIKE ?
                AND type_name_lower NOT LIKE ?
                ORDER BY length(type_name)
                LIMIT ?
                """,
                (f"%{name_lower}%", f"{name_lower}%", remaining),
            ).fetchall()
            suggestions.extend(row["type_name"] for row in rows)

        return suggestions

    def batch_resolve_names(self, names: Sequence[str]) -> dict[str, TypeInfo | None]:
        """
        Resolve multiple item names.

        Args:
            names: Item names to resolve

        Returns:
            Dict mapping input names to TypeInfo (or None if not found)
        """
        results: dict[str, TypeInfo | None] = {}
        for name in names:
            results[name] = self.resolve_type_name(name)
        return results

    def _row_to_type_info(self, row: sqlite3.Row) -> TypeInfo:
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
    # Region Resolution
    # =========================================================================

    def resolve_region_name(self, name: str) -> dict | None:
        """
        Resolve region name to region info.

        Tries exact match first, then case-insensitive prefix match.

        Args:
            name: Region name to resolve (e.g., "Everyshore", "The Forge")

        Returns:
            Dict with region_id and region_name if found, None otherwise
        """
        conn = self._get_connection()
        name_lower = name.lower().strip()

        # Check if regions table exists
        try:
            conn.execute("SELECT 1 FROM regions LIMIT 1")
        except sqlite3.OperationalError:
            return None

        # Try exact match (case-insensitive)
        row = conn.execute(
            "SELECT region_id, region_name FROM regions WHERE region_name_lower = ?",
            (name_lower,),
        ).fetchone()

        if row:
            return {"region_id": row["region_id"], "region_name": row["region_name"]}

        # Try prefix match
        row = conn.execute(
            "SELECT region_id, region_name FROM regions WHERE region_name_lower LIKE ? LIMIT 1",
            (f"{name_lower}%",),
        ).fetchone()

        if row:
            return {"region_id": row["region_id"], "region_name": row["region_name"]}

        # Try contains match
        row = conn.execute(
            "SELECT region_id, region_name FROM regions WHERE region_name_lower LIKE ? LIMIT 1",
            (f"%{name_lower}%",),
        ).fetchone()

        if row:
            return {"region_id": row["region_id"], "region_name": row["region_name"]}

        return None

    def get_all_regions(self) -> list[dict]:
        """
        Get all known regions.

        Returns:
            List of dicts with region_id and region_name
        """
        conn = self._get_connection()

        try:
            rows = conn.execute(
                "SELECT region_id, region_name FROM regions ORDER BY region_name"
            ).fetchall()
            return [
                {"region_id": row["region_id"], "region_name": row["region_name"]} for row in rows
            ]
        except sqlite3.OperationalError:
            return []

    # =========================================================================
    # Price Aggregates
    # =========================================================================

    def get_aggregate(
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
        conn = self._get_connection()
        cutoff = int(time.time()) - max_age_seconds

        row = conn.execute(
            """
            SELECT * FROM aggregates
            WHERE type_id = ? AND region_id = ? AND updated_at > ?
            """,
            (type_id, region_id, cutoff),
        ).fetchone()

        return self._row_to_aggregate(row) if row else None

    def get_aggregates_batch(
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

        conn = self._get_connection()
        cutoff = int(time.time()) - max_age_seconds

        # Use parameterized query with IN clause
        placeholders = ",".join("?" * len(type_ids))
        params = list(type_ids) + [region_id, cutoff]

        rows = conn.execute(
            f"""
            SELECT * FROM aggregates
            WHERE type_id IN ({placeholders})
            AND region_id = ? AND updated_at > ?
            """,
            params,
        ).fetchall()

        return {row["type_id"]: self._row_to_aggregate(row) for row in rows}

    def save_aggregate(self, aggregate: CachedAggregate) -> None:
        """Save a price aggregate to cache."""
        conn = self._get_connection()
        conn.execute(
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
        conn.commit()

    def save_aggregates_batch(self, aggregates: Sequence[CachedAggregate]) -> int:
        """
        Save multiple aggregates in a transaction.

        Args:
            aggregates: Aggregates to save

        Returns:
            Number of rows inserted/updated
        """
        if not aggregates:
            return 0

        conn = self._get_connection()
        cursor = conn.executemany(
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
        conn.commit()
        return cursor.rowcount

    def _row_to_aggregate(self, row: sqlite3.Row) -> CachedAggregate:
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
    # Bulk Import
    # =========================================================================

    def import_types_from_esi(self, types_data: list[dict]) -> int:
        """
        Import type data from ESI universe/types responses.

        Args:
            types_data: List of type dicts from ESI

        Returns:
            Number of types imported
        """
        conn = self._get_connection()
        cursor = conn.executemany(
            """
            INSERT OR REPLACE INTO types (
                type_id, type_name, type_name_lower,
                group_id, category_id, market_group_id, volume, packaged_volume
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    t["type_id"],
                    t["name"],
                    t["name"].lower(),
                    t.get("group_id"),
                    t.get("category_id"),
                    t.get("market_group_id"),
                    t.get("volume"),
                    t.get("packaged_volume"),
                )
                for t in types_data
            ],
        )
        conn.commit()
        return cursor.rowcount

    def import_fuzzwork_csv(self, csv_data: bytes) -> tuple[int, int]:
        """
        Import Fuzzwork bulk CSV data.

        CSV format from aggregatecsv.csv.gz:
        - what: "region_id|type_id|is_buy" (pipe-separated composite key)
        - weightedaverage, maxval, minval, stddev, median, volume, numorders, fivepercent

        Args:
            csv_data: Raw CSV bytes from Fuzzwork

        Returns:
            Tuple of (types_imported, aggregates_imported)
        """
        conn = self._get_connection()
        now = int(time.time())

        # Parse CSV
        text = csv_data.decode("utf-8")
        reader = csv.DictReader(io.StringIO(text))

        # Collect data by (region_id, type_id) to merge buy/sell rows
        # Key: (region_id, type_id) -> {"buy": row_data, "sell": row_data}
        aggregates_map: dict[tuple[int, int], dict] = {}
        type_ids_seen: set[int] = set()

        for row in reader:
            try:
                # Parse composite key: "region_id|type_id|is_buy"
                what = row.get("what", "")
                if not what or "|" not in what:
                    continue

                parts = what.split("|")
                if len(parts) != 3:
                    continue

                region_id = int(parts[0])
                type_id = int(parts[1])
                is_buy = parts[2].lower() == "true"

                # Only import The Forge (Jita) data
                if region_id != 10000002:
                    continue

                type_ids_seen.add(type_id)

                key = (region_id, type_id)
                if key not in aggregates_map:
                    aggregates_map[key] = {"buy": None, "sell": None}

                side_data = {
                    "weighted_avg": _safe_float(row.get("weightedaverage")),
                    "max": _safe_float(row.get("maxval")),
                    "min": _safe_float(row.get("minval")),
                    "stddev": _safe_float(row.get("stddev")),
                    "median": _safe_float(row.get("median")),
                    "volume": _safe_int(row.get("volume")),
                    "order_count": _safe_int(row.get("numorders")),
                    "percentile": _safe_float(row.get("fivepercent")),
                }

                if is_buy:
                    aggregates_map[key]["buy"] = side_data
                else:
                    aggregates_map[key]["sell"] = side_data

            except Exception as e:
                logger.warning("Failed to parse CSV row: %s", e)
                continue

        # Build aggregates from merged data
        aggregates_batch = []
        for (region_id, type_id), sides in aggregates_map.items():
            buy = sides.get("buy") or {}
            sell = sides.get("sell") or {}

            aggregates_batch.append(
                CachedAggregate(
                    type_id=type_id,
                    region_id=region_id,
                    station_id=60003760,  # Jita 4-4
                    buy_weighted_avg=buy.get("weighted_avg"),
                    buy_max=buy.get("max"),
                    buy_min=buy.get("min"),
                    buy_stddev=buy.get("stddev"),
                    buy_median=buy.get("median"),
                    buy_volume=buy.get("volume", 0),
                    buy_order_count=buy.get("order_count", 0),
                    buy_percentile=buy.get("percentile"),
                    sell_weighted_avg=sell.get("weighted_avg"),
                    sell_max=sell.get("max"),
                    sell_min=sell.get("min"),
                    sell_stddev=sell.get("stddev"),
                    sell_median=sell.get("median"),
                    sell_volume=sell.get("volume", 0),
                    sell_order_count=sell.get("order_count", 0),
                    sell_percentile=sell.get("percentile"),
                    updated_at=now,
                )
            )

        # Insert placeholder types (name will be resolved later via ESI)
        types_batch = [
            (type_id, f"Type {type_id}", f"type {type_id}", None, None, None, None, None)
            for type_id in type_ids_seen
        ]

        types_count = 0
        if types_batch:
            conn.executemany(
                """
                INSERT OR IGNORE INTO types (
                    type_id, type_name, type_name_lower,
                    group_id, category_id, market_group_id, volume, packaged_volume
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                types_batch,
            )
            types_count = len(types_batch)

        # Batch insert aggregates
        aggregates_count = 0
        if aggregates_batch:
            aggregates_count = self.save_aggregates_batch(aggregates_batch)

        conn.commit()
        logger.info(
            "Imported %d types and %d aggregates from Fuzzwork CSV",
            types_count,
            aggregates_count,
        )
        return types_count, aggregates_count

    def get_placeholder_type_ids(self) -> list[int]:
        """
        Get type IDs that have placeholder names (like "Type 34").

        Returns:
            List of type IDs needing name resolution
        """
        conn = self._get_connection()
        cursor = conn.execute("SELECT type_id FROM types WHERE type_name LIKE 'Type %'")
        return [row[0] for row in cursor.fetchall()]

    def update_type_names(self, names: dict[int, str]) -> int:
        """
        Update type names for existing type IDs.

        Args:
            names: Dict mapping type_id to type_name

        Returns:
            Number of types updated
        """
        conn = self._get_connection()
        batch = [(name, name.lower(), type_id) for type_id, name in names.items()]
        conn.executemany(
            "UPDATE types SET type_name = ?, type_name_lower = ? WHERE type_id = ?",
            batch,
        )
        conn.commit()
        return len(batch)

    # =========================================================================
    # Database Stats
    # =========================================================================

    def get_stats(self) -> dict:
        """
        Get database statistics.

        Returns:
            Dict with counts and freshness info
        """
        conn = self._get_connection()
        now = int(time.time())

        type_count = conn.execute("SELECT COUNT(*) FROM types").fetchone()[0]
        aggregate_count = conn.execute("SELECT COUNT(*) FROM aggregates").fetchone()[0]

        # Get freshness
        oldest = conn.execute("SELECT MIN(updated_at) FROM aggregates").fetchone()[0]
        newest = conn.execute("SELECT MAX(updated_at) FROM aggregates").fetchone()[0]

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
    # Watchlist Operations
    # =========================================================================

    def create_watchlist(
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
            sqlite3.IntegrityError: If name already exists for this owner
        """
        conn = self._get_connection()
        now = int(time.time())

        cursor = conn.execute(
            """
            INSERT INTO watchlists (name, owner_character_id, created_at)
            VALUES (?, ?, ?)
            """,
            (name, owner_character_id, now),
        )
        conn.commit()

        watchlist_id = cursor.lastrowid
        assert watchlist_id is not None, "INSERT should always return a lastrowid"

        return Watchlist(
            watchlist_id=watchlist_id,
            name=name,
            owner_character_id=owner_character_id,
            created_at=now,
        )

    def get_watchlist(
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
        conn = self._get_connection()

        if owner_character_id is None:
            row = conn.execute(
                """
                SELECT * FROM watchlists
                WHERE name = ? AND owner_character_id IS NULL
                """,
                (name,),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT * FROM watchlists
                WHERE name = ? AND owner_character_id = ?
                """,
                (name, owner_character_id),
            ).fetchone()

        return self._row_to_watchlist(row) if row else None

    def get_watchlist_by_id(self, watchlist_id: int) -> Watchlist | None:
        """
        Get a watchlist by ID.

        Args:
            watchlist_id: Watchlist ID

        Returns:
            Watchlist if found, None otherwise
        """
        conn = self._get_connection()
        row = conn.execute(
            "SELECT * FROM watchlists WHERE watchlist_id = ?",
            (watchlist_id,),
        ).fetchone()

        return self._row_to_watchlist(row) if row else None

    def list_watchlists(
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
        conn = self._get_connection()

        if owner_character_id is None:
            rows = conn.execute(
                """
                SELECT * FROM watchlists
                WHERE owner_character_id IS NULL
                ORDER BY name
                """
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM watchlists
                WHERE owner_character_id = ?
                ORDER BY name
                """,
                (owner_character_id,),
            ).fetchall()

        return [self._row_to_watchlist(row) for row in rows]

    def delete_watchlist(self, watchlist_id: int) -> bool:
        """
        Delete a watchlist and its items (cascade).

        Args:
            watchlist_id: Watchlist ID to delete

        Returns:
            True if deleted, False if not found
        """
        conn = self._get_connection()
        cursor = conn.execute(
            "DELETE FROM watchlists WHERE watchlist_id = ?",
            (watchlist_id,),
        )
        conn.commit()
        return cursor.rowcount > 0

    def add_watchlist_item(self, watchlist_id: int, type_id: int) -> WatchlistItem:
        """
        Add an item to a watchlist.

        Args:
            watchlist_id: Watchlist ID
            type_id: Type ID to add

        Returns:
            Created WatchlistItem

        Raises:
            sqlite3.IntegrityError: If item already in watchlist or watchlist doesn't exist
        """
        conn = self._get_connection()
        now = int(time.time())

        conn.execute(
            """
            INSERT INTO watchlist_items (watchlist_id, type_id, added_at)
            VALUES (?, ?, ?)
            """,
            (watchlist_id, type_id, now),
        )
        conn.commit()

        return WatchlistItem(
            watchlist_id=watchlist_id,
            type_id=type_id,
            added_at=now,
        )

    def remove_watchlist_item(self, watchlist_id: int, type_id: int) -> bool:
        """
        Remove an item from a watchlist.

        Args:
            watchlist_id: Watchlist ID
            type_id: Type ID to remove

        Returns:
            True if removed, False if not found
        """
        conn = self._get_connection()
        cursor = conn.execute(
            """
            DELETE FROM watchlist_items
            WHERE watchlist_id = ? AND type_id = ?
            """,
            (watchlist_id, type_id),
        )
        conn.commit()
        return cursor.rowcount > 0

    def get_watchlist_items(self, watchlist_id: int) -> list[WatchlistItem]:
        """
        Get all items in a watchlist.

        Args:
            watchlist_id: Watchlist ID

        Returns:
            List of WatchlistItem objects
        """
        conn = self._get_connection()
        rows = conn.execute(
            """
            SELECT * FROM watchlist_items
            WHERE watchlist_id = ?
            ORDER BY type_id
            """,
            (watchlist_id,),
        ).fetchall()

        return [
            WatchlistItem(
                watchlist_id=row["watchlist_id"],
                type_id=row["type_id"],
                added_at=row["added_at"],
            )
            for row in rows
        ]

    def _row_to_watchlist(self, row: sqlite3.Row) -> Watchlist:
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

    def create_scope(
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
            sqlite3.IntegrityError: If constraints violated
        """
        conn = self._get_connection()
        now = int(time.time())

        cursor = conn.execute(
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
        conn.commit()

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

    def get_scope(
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
        conn = self._get_connection()

        if owner_character_id is None:
            row = conn.execute(
                """
                SELECT * FROM market_scopes
                WHERE scope_name = ? AND owner_character_id IS NULL
                """,
                (scope_name,),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT * FROM market_scopes
                WHERE scope_name = ? AND owner_character_id = ?
                """,
                (scope_name, owner_character_id),
            ).fetchone()

        return self._row_to_scope(row) if row else None

    def get_scope_by_id(self, scope_id: int) -> MarketScope | None:
        """
        Get a scope by ID.

        Args:
            scope_id: Scope ID

        Returns:
            MarketScope if found, None otherwise
        """
        conn = self._get_connection()
        row = conn.execute(
            "SELECT * FROM market_scopes WHERE scope_id = ?",
            (scope_id,),
        ).fetchone()

        return self._row_to_scope(row) if row else None

    def list_scopes(
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
        conn = self._get_connection()

        if owner_character_id is None:
            # Global only mode
            if include_core:
                rows = conn.execute(
                    """
                    SELECT * FROM market_scopes
                    WHERE owner_character_id IS NULL
                    ORDER BY is_core DESC, scope_name
                    """
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM market_scopes
                    WHERE owner_character_id IS NULL AND is_core = 0
                    ORDER BY scope_name
                    """
                ).fetchall()
        else:
            # Owner mode - include owner's scopes + optionally global scopes
            if include_global:
                if include_core:
                    # Owner scopes + all global scopes (core + ad-hoc)
                    rows = conn.execute(
                        """
                        SELECT * FROM market_scopes
                        WHERE owner_character_id = ? OR owner_character_id IS NULL
                        ORDER BY is_core DESC, scope_name
                        """,
                        (owner_character_id,),
                    ).fetchall()
                else:
                    # Owner scopes + global ad-hoc scopes (no core)
                    rows = conn.execute(
                        """
                        SELECT * FROM market_scopes
                        WHERE owner_character_id = ?
                           OR (owner_character_id IS NULL AND is_core = 0)
                        ORDER BY scope_name
                        """,
                        (owner_character_id,),
                    ).fetchall()
            else:
                # Owner scopes only (no global)
                rows = conn.execute(
                    """
                    SELECT * FROM market_scopes
                    WHERE owner_character_id = ?
                    ORDER BY scope_name
                    """,
                    (owner_character_id,),
                ).fetchall()

        return [self._row_to_scope(row) for row in rows]

    def resolve_scopes(
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

        conn = self._get_connection()
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
                rows = conn.execute(query, scope_names).fetchall()
            else:
                query = f"""
                    SELECT * FROM market_scopes
                    WHERE owner_character_id IS NULL
                      AND is_core = 0
                      AND scope_name IN ({placeholders})
                    ORDER BY scope_name
                """
                rows = conn.execute(query, scope_names).fetchall()

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
            rows = conn.execute(query, scope_names).fetchall()
            for row in rows:
                scope = self._row_to_scope(row)
                resolved[scope.scope_name] = scope

            # Then, overlay owner scopes (shadowing globals)
            query = f"""
                SELECT * FROM market_scopes
                WHERE owner_character_id = ?
                  AND scope_name IN ({placeholders})
            """
            rows = conn.execute(query, [owner_character_id] + scope_names).fetchall()
            for row in rows:
                scope = self._row_to_scope(row)
                resolved[scope.scope_name] = scope  # Overwrites global

        return list(resolved.values())

    def delete_scope(self, scope_id: int) -> bool:
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
        conn = self._get_connection()

        # Check if this is a core scope
        row = conn.execute(
            "SELECT is_core FROM market_scopes WHERE scope_id = ?",
            (scope_id,),
        ).fetchone()

        if row is None:
            return False

        if row["is_core"]:
            raise ValueError(
                f"Cannot delete core hub scope (scope_id={scope_id}). "
                "Core hubs are protected to maintain the hub-centric default."
            )

        cursor = conn.execute(
            "DELETE FROM market_scopes WHERE scope_id = ?",
            (scope_id,),
        )
        conn.commit()
        return cursor.rowcount > 0

    def update_scope_scan_status(
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
        conn = self._get_connection()
        now = int(time.time())

        cursor = conn.execute(
            """
            UPDATE market_scopes
            SET last_scan_status = ?, last_scanned_at = ?, updated_at = ?
            WHERE scope_id = ?
            """,
            (status, scanned_at or now, now, scope_id),
        )
        conn.commit()
        return cursor.rowcount > 0

    def _row_to_scope(self, row: sqlite3.Row) -> MarketScope:
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

    def upsert_scope_price(self, price: MarketScopePrice) -> None:
        """
        Insert or update a scope price record.

        Args:
            price: MarketScopePrice to upsert
        """
        conn = self._get_connection()
        conn.execute(
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
        conn.commit()

    def upsert_scope_prices_batch(self, prices: Sequence[MarketScopePrice]) -> int:
        """
        Insert or update multiple scope price records.

        Args:
            prices: List of MarketScopePrice objects

        Returns:
            Number of rows affected
        """
        if not prices:
            return 0

        conn = self._get_connection()
        conn.executemany(
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
        conn.commit()
        return len(prices)

    def get_scope_price(
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
        conn = self._get_connection()
        row = conn.execute(
            """
            SELECT * FROM market_scope_prices
            WHERE scope_id = ? AND type_id = ?
            """,
            (scope_id, type_id),
        ).fetchone()

        return self._row_to_scope_price(row) if row else None

    def get_scope_prices(
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
        conn = self._get_connection()

        if max_age_seconds is not None:
            cutoff = int(time.time()) - max_age_seconds
            rows = conn.execute(
                """
                SELECT * FROM market_scope_prices
                WHERE scope_id = ? AND updated_at > ?
                ORDER BY type_id
                """,
                (scope_id, cutoff),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM market_scope_prices
                WHERE scope_id = ?
                ORDER BY type_id
                """,
                (scope_id,),
            ).fetchall()

        return [self._row_to_scope_price(row) for row in rows]

    def clear_scope_prices(self, scope_id: int) -> int:
        """
        Delete all prices for a scope.

        Args:
            scope_id: Scope ID

        Returns:
            Number of rows deleted
        """
        conn = self._get_connection()
        cursor = conn.execute(
            "DELETE FROM market_scope_prices WHERE scope_id = ?",
            (scope_id,),
        )
        conn.commit()
        return cursor.rowcount

    def _row_to_scope_price(self, row: sqlite3.Row) -> MarketScopePrice:
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
# Helper Functions
# =============================================================================


def _safe_float(value: str | None) -> float | None:
    """Safely convert string to float."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _safe_int(value: str | None) -> int:
    """Safely convert string to int, defaulting to 0."""
    if value is None or value == "":
        return 0
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return 0


def get_market_database() -> MarketDatabase:
    """Get or create the market database singleton."""
    global _market_db
    if "_market_db" not in globals() or _market_db is None:
        _market_db = MarketDatabase()
    return _market_db


def reset_market_database() -> None:
    """
    Reset the market database singleton.

    Closes the existing connection and clears the singleton.
    Use for testing to ensure clean state between tests.
    """
    global _market_db
    if _market_db is not None:
        _market_db.close()
        _market_db = None


_market_db: MarketDatabase | None = None
