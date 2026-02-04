-- =============================================================================
-- Killmail Store Database Schema - Initial Migration
-- =============================================================================
--
-- Migration 001: Initial schema
-- Creates all tables, indices, and configuration for the killmail store.
--
-- Design notes:
-- - All timestamps are Unix epoch integers (seconds)
-- - kill_id is globally unique, assigned by CCP
-- - ESI details are lazy-populated; sentinel rows mark unfetchable kills
-- - Indices optimized for worker polling and MCP queries
--
-- =============================================================================


-- -----------------------------------------------------------------------------
-- Table: killmails
-- -----------------------------------------------------------------------------
-- Stores RedisQ metadata immediately upon receipt.
-- This is the primary table - all kills from zKillboard are stored here.
--
-- Data authority note (D6): Fields like victim_corporation_id are denormalized
-- from zkb for fast filtering. When ESI details exist, prefer esi_details
-- values for display (ESI is authoritative).

CREATE TABLE IF NOT EXISTS killmails (
    kill_id INTEGER PRIMARY KEY,
    kill_time INTEGER NOT NULL,           -- Unix timestamp (when kill occurred)
    solar_system_id INTEGER NOT NULL,
    zkb_hash TEXT NOT NULL,               -- Required for ESI fetch
    zkb_total_value REAL,
    zkb_points INTEGER,
    zkb_is_npc BOOLEAN DEFAULT FALSE,
    zkb_is_solo BOOLEAN DEFAULT FALSE,
    zkb_is_awox BOOLEAN DEFAULT FALSE,
    ingested_at INTEGER NOT NULL,         -- Unix timestamp (when we received it)

    -- Denormalized victim data from zkb package (for fast filtering/routing)
    victim_ship_type_id INTEGER,
    victim_corporation_id INTEGER,
    victim_alliance_id INTEGER
);

-- Primary query pattern: kills in system(s) within time range
CREATE INDEX IF NOT EXISTS idx_killmails_system_time
    ON killmails(solar_system_id, kill_time);

-- Worker polling: recent kills by time
CREATE INDEX IF NOT EXISTS idx_killmails_time
    ON killmails(kill_time);

-- High-value kill queries
CREATE INDEX IF NOT EXISTS idx_killmails_value
    ON killmails(zkb_total_value);

-- Corporation/alliance activity tracking
CREATE INDEX IF NOT EXISTS idx_killmails_victim_corp
    ON killmails(victim_corporation_id);

CREATE INDEX IF NOT EXISTS idx_killmails_victim_alliance
    ON killmails(victim_alliance_id);

-- Observability: find ingestion gaps during backpressure analysis
CREATE INDEX IF NOT EXISTS idx_killmails_ingested
    ON killmails(ingested_at);


-- -----------------------------------------------------------------------------
-- Table: esi_details
-- -----------------------------------------------------------------------------
-- Stores full ESI killmail data, populated on-demand by workers.
-- This is the AUTHORITATIVE source for victim/attacker details when present.
--
-- Sentinel rows:
--   When ESI fetch permanently fails (after max attempts), a sentinel is stored:
--   - fetched_at = 0
--   - fetch_status = 'unfetchable'
--   - All detail fields NULL
--   Workers check fetch_status before attempting ESI fetch.

CREATE TABLE IF NOT EXISTS esi_details (
    kill_id INTEGER PRIMARY KEY REFERENCES killmails(kill_id) ON DELETE CASCADE,
    fetched_at INTEGER NOT NULL,          -- 0 for sentinel rows
    fetch_status TEXT DEFAULT 'success',  -- 'success' or 'unfetchable'
    fetch_attempts INTEGER DEFAULT 1,

    -- Victim details (authoritative when present)
    victim_character_id INTEGER,
    victim_ship_type_id INTEGER,
    victim_corporation_id INTEGER,
    victim_alliance_id INTEGER,
    victim_damage_taken INTEGER,

    -- Attacker summary
    attacker_count INTEGER,
    final_blow_character_id INTEGER,
    final_blow_ship_type_id INTEGER,
    final_blow_corporation_id INTEGER,

    -- Serialized full data for complex queries
    attackers_json TEXT,                  -- Full attacker list as JSON array
    items_json TEXT,                      -- Dropped/destroyed items as JSON
    position_json TEXT                    -- {x, y, z} coordinates
);

-- Cleanup queries for fetched data
CREATE INDEX IF NOT EXISTS idx_esi_fetched
    ON esi_details(fetched_at);

-- Find unfetchable kills (for debugging/metrics)
CREATE INDEX IF NOT EXISTS idx_esi_status
    ON esi_details(fetch_status)
    WHERE fetch_status != 'success';


-- -----------------------------------------------------------------------------
-- Table: worker_state
-- -----------------------------------------------------------------------------
-- Tracks worker time-based high-water marks for resumption after restart.
-- One row per notification profile (worker).

CREATE TABLE IF NOT EXISTS worker_state (
    worker_name TEXT PRIMARY KEY,
    last_processed_time INTEGER NOT NULL,  -- Unix timestamp of newest processed kill
    last_poll_at INTEGER,                  -- Unix timestamp of last successful poll
    consecutive_failures INTEGER DEFAULT 0  -- Health metric for alerting
);


-- -----------------------------------------------------------------------------
-- Table: processed_kills
-- -----------------------------------------------------------------------------
-- Tracks recently processed kills per worker to prevent duplicate notifications.
-- Required because kill IDs from RedisQ are not strictly time-ordered.
--
-- Lifecycle:
-- - Entries inserted after notification processing (success or failure)
-- - Expunge task removes entries older than retention period (default 1 hour)
-- - Retention must exceed maximum expected out-of-order delivery delay

CREATE TABLE IF NOT EXISTS processed_kills (
    worker_name TEXT NOT NULL,
    kill_id INTEGER NOT NULL,
    processed_at INTEGER NOT NULL,         -- Unix timestamp
    delivery_status TEXT DEFAULT 'delivered',  -- 'delivered', 'failed', 'pending'
    delivery_attempts INTEGER DEFAULT 1,
    PRIMARY KEY (worker_name, kill_id)
);

-- Cleanup query: delete old entries
CREATE INDEX IF NOT EXISTS idx_processed_kills_cleanup
    ON processed_kills(processed_at);

-- Find pending deliveries for retry
CREATE INDEX IF NOT EXISTS idx_processed_kills_pending
    ON processed_kills(worker_name, delivery_status)
    WHERE delivery_status = 'pending';


-- -----------------------------------------------------------------------------
-- Table: esi_fetch_attempts
-- -----------------------------------------------------------------------------
-- Tracks ESI fetch attempts BEFORE the first successful fetch.
-- Required because esi_details.fetch_attempts only exists after success.
--
-- Lifecycle:
-- 1. First attempt fails -> INSERT with attempts=1
-- 2. Subsequent failures -> UPDATE attempts += 1
-- 3. Success -> DELETE (data now in esi_details)
-- 4. Max attempts (3) -> INSERT sentinel to esi_details, DELETE from here
--
-- This table stays small: only in-flight or recently-failed fetches.

CREATE TABLE IF NOT EXISTS esi_fetch_attempts (
    kill_id INTEGER PRIMARY KEY,
    attempts INTEGER NOT NULL DEFAULT 1,
    last_attempt_at INTEGER NOT NULL,      -- Unix timestamp
    last_error TEXT                        -- Optional: error message for debugging
);

-- Cleanup old entries (kills that were expunged or never retried)
CREATE INDEX IF NOT EXISTS idx_esi_attempts_time
    ON esi_fetch_attempts(last_attempt_at);


-- -----------------------------------------------------------------------------
-- Table: esi_fetch_claims
-- -----------------------------------------------------------------------------
-- Coordinates ESI fetches across workers to prevent duplicate API calls.
-- Claims are transient - inserted before fetch, deleted after completion.
--
-- Stale claim handling:
-- - Claims older than threshold (60s) are considered abandoned
-- - Expunge task cleans up stale claims
-- - Another worker can then retry the fetch

CREATE TABLE IF NOT EXISTS esi_fetch_claims (
    kill_id INTEGER PRIMARY KEY,
    claimed_by TEXT NOT NULL,              -- Worker name that holds the claim
    claimed_at INTEGER NOT NULL            -- Unix timestamp
);

-- Find stale claims for cleanup
CREATE INDEX IF NOT EXISTS idx_esi_claims_stale
    ON esi_fetch_claims(claimed_at);


-- -----------------------------------------------------------------------------
-- Table: schema_migrations
-- -----------------------------------------------------------------------------
-- Tracks applied database migrations for upgrade management.
-- See D8: Database Schema Migrations in the proposal.

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at INTEGER NOT NULL,           -- Unix timestamp
    description TEXT
);
