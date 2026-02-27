"""
Arbitrage Schema for Market Database.

DEPRECATED: The arbitrage schema tables (region_prices, region_item_tracking,
arbitrage_opportunities, region_refresh_tracking) have been moved to the main
SCHEMA_SQL in database.py for unified initialization.

This file is kept for backward compatibility and contains helper SQL functions.
The ARBITRAGE_SCHEMA_SQL constant below is no longer applied separately.
"""

from __future__ import annotations

# =============================================================================
# Arbitrage Schema SQL
# =============================================================================

ARBITRAGE_SCHEMA_SQL = """
-- ============================================================================
-- Region Prices: Snapshot prices per region
-- ============================================================================
-- Stores aggregated prices per region for cross-region comparison.
-- Updated by MarketRefreshService on TTL expiry or force refresh.
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

-- ============================================================================
-- Region Item Tracking: Items worth monitoring per region
-- ============================================================================
-- Tracks which items have sufficient market activity to be worth monitoring.
-- avg_daily_volume used for filtering low-volume items.
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

-- ============================================================================
-- Arbitrage Opportunities: Computed opportunities
-- ============================================================================
-- Stores detected arbitrage opportunities for quick retrieval.
-- Opportunities are ephemeral - cleared and recalculated on each scan.
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

-- ============================================================================
-- Refresh Tracking: Track when each region was last refreshed
-- ============================================================================
CREATE TABLE IF NOT EXISTS region_refresh_tracking (
    region_id INTEGER PRIMARY KEY,
    region_name TEXT NOT NULL,
    last_refresh INTEGER NOT NULL,
    items_refreshed INTEGER DEFAULT 0,
    refresh_duration_ms INTEGER DEFAULT 0
);

-- Insert schema version for arbitrage tables
INSERT OR REPLACE INTO metadata (key, value) VALUES ('arbitrage_schema_version', '1');
"""


# =============================================================================
# Helper Functions
# =============================================================================


def get_arbitrage_detection_sql(
    min_profit_pct: float = 5.0,
    min_volume: int = 10,
    limit: int = 50,
) -> str:
    """
    Generate SQL query for detecting arbitrage opportunities.

    Finds items where sell_min in one region is lower than buy_max in another,
    indicating potential profit from transporting goods.

    Args:
        min_profit_pct: Minimum profit percentage to include
        min_volume: Minimum available volume
        limit: Maximum results to return

    Returns:
        SQL query string
    """
    return f"""
    SELECT
        buy.type_id,
        t.type_name,
        sell.region_id AS sell_region_id,
        buy.region_id AS buy_region_id,
        sell.sell_min AS sell_price,
        buy.buy_max AS buy_price,
        (buy.buy_max - sell.sell_min) AS profit_per_unit,
        ROUND(((buy.buy_max - sell.sell_min) / sell.sell_min) * 100, 2) AS profit_pct,
        MIN(sell.sell_volume, buy.buy_volume) AS available_volume,
        sell.updated_at AS sell_updated,
        buy.updated_at AS buy_updated
    FROM region_prices sell
    JOIN region_prices buy ON sell.type_id = buy.type_id
        AND sell.region_id != buy.region_id
    LEFT JOIN types t ON t.type_id = sell.type_id
    WHERE
        sell.sell_min IS NOT NULL
        AND buy.buy_max IS NOT NULL
        AND sell.sell_min > 0
        AND buy.buy_max > sell.sell_min
        AND ((buy.buy_max - sell.sell_min) / sell.sell_min) * 100 >= {min_profit_pct}
        AND MIN(sell.sell_volume, buy.buy_volume) >= {min_volume}
    ORDER BY profit_pct DESC
    LIMIT {limit}
    """


def get_stale_regions_sql(max_age_seconds: int = 300) -> str:
    """
    Generate SQL to find regions needing refresh.

    Args:
        max_age_seconds: Maximum age before considered stale

    Returns:
        SQL query string
    """
    return f"""
    SELECT region_id, region_name, last_refresh
    FROM region_refresh_tracking
    WHERE last_refresh < (strftime('%s', 'now') - {max_age_seconds})
    ORDER BY last_refresh ASC
    """
