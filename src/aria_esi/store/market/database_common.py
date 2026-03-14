"""
Common market database types shared between sync and async implementations.

Extracted to break the import dependency cycle: database_async previously
imported shared types from database (sync), creating a false dependency.
"""

from __future__ import annotations

from dataclasses import dataclass

# =============================================================================
# Constants
# =============================================================================

# Schema version for migrations
SCHEMA_VERSION = 10

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
    hull_value REAL,
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
    name TEXT NOT NULL COLLATE NOCASE,
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
INSERT OR REPLACE INTO metadata (key, value) VALUES ('schema_version', '{schema_version}');
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
