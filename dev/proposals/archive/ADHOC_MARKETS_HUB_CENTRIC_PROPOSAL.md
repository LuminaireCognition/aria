# Hub-Centric Market Engine with Opt-in Ad-hoc Markets (ESI-backed)

## Summary
Keep the default arbitrage/analysis engine fast and reliable by scanning only the five core trade hubs (Fuzzwork aggregates). Add an opt-in extension layer that lets players attach ad-hoc markets (region, station, system, structure) of interest. Ad-hoc markets use ESI-backed aggregation, are scoped to explicit item lists (watchlists/categories), and are clearly labeled for data provenance, coverage, freshness, and cost.

**Critical Constraint:** Structure markets via ESI do *not* support item filtering. Adding a structure scope implies fetching *all* orders for that structure (paginated). This proposal mandates strict pagination limits and explicit user opt-in for structure scopes to prevent "firehose" data costs.

---

## Goals
1. **Default remains hub-centric**: existing behavior (5 hubs, Fuzzwork aggregates, 5-minute TTL) stays the default scan path.
2. **Ad-hoc markets are explicit**: users must opt in per scan or per profile, and must define scope + item list (watchlist).
3. **Data quality is visible**: every ad-hoc result labels source (ESI vs Fuzzwork), coverage type (watchlist vs full), fetch status (complete vs truncated), and freshness (from ESI headers).
4. **Cost is controlled**: ESI calls are bounded by explicit caps, caching, TTLs, and concurrency limits. Structure scopes are "high cost" and treated with extra guardrails.
5. **Simple, additive implementation**: avoid rewriting core arbitrage logic; add a scoped layer alongside it.

## Non-goals
- Universal region/system scanning for all types.
- Real-time order book tracking for every location.
- Mixing ad-hoc data into default scans without explicit user action.
- "Cheap" structure scanning (impossible due to ESI API design).

---

## Current Constraints (from repo)
- Refresh service is **trade-hub only** and rejects non-hub regions.
- `region_prices` is keyed by `(type_id, region_id)` and can’t represent station/system/structure-level markets.
- ESI fallback exists but is limited to `type_id` per region and uses per-type order pulls.

---

## Design Principles
1. **Hub core is authoritative for default scans**
   - Keep existing hub refresh pipeline and data store unchanged for baseline scans.

2. **Ad-hoc markets are scoped and explicit**
   - No ad-hoc market data used unless requested via tool parameters or player profile settings.
   - **Structure Scopes** require a "high bandwidth" acknowledgement (explicit flag).

3. **Labeling is first-class**
   - Results carry data source, freshness (cache age), and coverage flags.
   - UI clearly differentiates “core hub” vs “ad-hoc market” results.

4. **Cost-aware by design**
   - Ad-hoc scans require a **Watchlist** (named list of items) to bound ESI calls (except for structures, where watchlists only filter the *result*).
   - Hard caps on items per scan and total scope count.

---

## Proposed Data Model

### New Table: `watchlists`
Formalizes the concept of a named list of items.

```sql
CREATE TABLE IF NOT EXISTS watchlists (
    watchlist_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    owner_character_id INTEGER,         -- null = global/system list; INTEGER = immutable character ID
    created_at INTEGER NOT NULL
);
-- Partial indexes to enforce uniqueness for both global (NULL) and character-owned lists
CREATE UNIQUE INDEX IF NOT EXISTS idx_watchlists_owner ON watchlists(name, owner_character_id) WHERE owner_character_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_watchlists_global ON watchlists(name) WHERE owner_character_id IS NULL;
```

### New Table: `watchlist_items`
```sql
CREATE TABLE IF NOT EXISTS watchlist_items (
    watchlist_id INTEGER NOT NULL,
    type_id INTEGER NOT NULL,
    added_at INTEGER NOT NULL,
    PRIMARY KEY (watchlist_id, type_id),
    FOREIGN KEY (watchlist_id) REFERENCES watchlists(watchlist_id) ON DELETE CASCADE
);
```

### New Table: `market_scopes`
Defines both core and ad-hoc market scopes. Linked to a watchlist to define "what to scan".

```sql
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
        -- Core hubs use Fuzzwork and NO watchlist; Ad-hoc use ESI and MUST have watchlist
        (is_core = 1 AND source = 'fuzzwork' AND watchlist_id IS NULL AND scope_type = 'hub_region') OR
        (is_core = 0 AND source = 'esi' AND watchlist_id IS NOT NULL AND scope_type IN ('region', 'station', 'system', 'structure'))
    )
);
-- Partial indexes for scope uniqueness
CREATE UNIQUE INDEX IF NOT EXISTS idx_market_scopes_owner ON market_scopes(scope_name, owner_character_id) WHERE owner_character_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_market_scopes_global ON market_scopes(scope_name) WHERE owner_character_id IS NULL;
```

### New Table: `market_scope_prices`
Stores aggregated prices for ad-hoc scopes.

```sql
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
    CHECK (fetch_status IN ('complete', 'truncated', 'skipped_truncation'))
);
```

---

## Data Sources & Refresh Strategy

### Core Hubs (unchanged)
- **Source**: Fuzzwork aggregates
- **TTL**: 5 minutes
- **Storage**: `region_prices`

### Ad-hoc Scopes (new)
- **Source**: ESI region/structure orders
- **Aggregation**: local aggregation into buy_max/sell_min + volume/order counts
- **TTL**: Respect `http_expires` from ESI, or default 15 mins.
    - If ESI returns **304 Not Modified**, existing `http_last_modified` and `http_expires` are preserved, but `updated_at` (row) and `last_scanned_at` (scope) are updated to `now` to reflect the successful check.
    - If ESI headers are missing, fallback to:
        - `http_last_modified = updated_at` (now), so `data_age` is effectively 0 (unknown real age, but fresh fetch).
        - `http_expires = updated_at + 15 mins`.

#### Fetch Logic by Scope Type:
1.  **Region (ESI):**
    *   **Watchlist Required**: Yes.
    *   Iterate `watchlist_items`.
    *   Call `GET /markets/{region_id}/orders/?type_id={type_id}`.
    *   **Zero-Row Upsert**: If no orders are returned for a type, upsert a row with:
        *   `fetch_status='complete'`
        *   `order_count_buy=0`, `order_count_sell=0`
        *   `buy_volume=0`, `sell_volume=0`
        *   `buy_max=NULL`, `sell_min=NULL`, `spread_pct=NULL`
    *   Cheap, targeted.
2.  **Station / System (ESI):**
    *   **Watchlist Required**: Yes.
    *   **Region Resolution**: Use `parent_region_id` from scope if available, otherwise resolve location->region once.
    *   Iterate `watchlist_items`.
    *   Call `GET /markets/{region_id}/orders/?type_id={type_id}`.
    *   **Filtering**:
        *   **Station Scope**: Filter orders where `location_id == scope.station_id`.
        *   **System Scope**: Filter orders where `system_id == scope.system_id`. (Includes public structure orders in that system).
    *   **Zero-Row Upsert**: If matching orders are empty (after filtering), upsert a row with:
        *   `fetch_status='complete'`
        *   `order_count_buy=0`, `order_count_sell=0`
        *   `buy_volume=0`, `sell_volume=0`
        *   `buy_max=NULL`, `sell_min=NULL`, `spread_pct=NULL`
    *   Cheap, targeted.
3.  **Structure (ESI):**
    *   **Watchlist Required**: Yes (for filtering).
    *   **WARNING:** Cannot filter ESI fetch by type.
    *   Call `GET /markets/structures/{structure_id}/`.
    *   **Pagination:** Must fetch pages 1..N.
    *   **Truncation:** Stop after `MAX_STRUCTURE_PAGES` (default 5). If more pages exist, mark `fetch_status = 'truncated'`.
    *   **Filtering:** Discard orders not in `watchlist`.
    *   **Backfill:** Any watchlist items NOT found in the scanned pages must be upserted with `fetch_status='skipped_truncation'` (if truncated) or 'complete' (if not truncated but truly missing).
        *   **Important:** Upsert MUST explicitly set `buy_max=NULL`, `sell_min=NULL`, `buy_volume=0`, `sell_volume=0`, `spread_pct=NULL`, and `order_count_*=0` to clear any stale data from previous scans.
    *   **Cost:** High. 1 call per page. A large market might be 50+ pages.

### Data Quality Labels
Every ad-hoc row includes:
- `http_last_modified`: The actual "age" of the order data from CCP.
- `fetch_status`:
    - `complete`: We successfully scanned the requested scope/watchlist.
    - `truncated`: Scanned some pages but hit limit; volume potentially incomplete.
    - `skipped_truncation`: Item was in watchlist but we hit page limits before finding it (or finding all of it).

---

## Tooling & UX Changes

### New management tools
- `market_watchlist_create(name, items=[], owner_character_id=None)`
- `market_watchlist_add_item(name, type_name, owner_character_id=None)`
- `market_scope_create(name, scope_type, location_id, watchlist_name, source='esi', owner_character_id=None, parent_region_id=None)`
    - `location_id` maps to the column matching `scope_type` (e.g., `structure_id` if type='structure').
    - `watchlist_name` is **mandatory** for all ad-hoc scopes.
    - `owner_character_id` resolves name collisions (defaults to global if None, or specific character).
    - `parent_region_id` optional but recommended for station/system scopes.
- `market_scope_list(owner_character_id=None)`

### Update `market_arbitrage_scan`
Add parameters:
- `scopes: list[str] | None = None` (Name of scope to include)
- `scope_owner_id: int | None = None` (Disambiguate scope owner)
    - `None`: Default. Scans **Global** scopes + scopes owned by the **active character** (if any context exists).
    - `> 0`: Scans scopes owned by this specific `character_id`.
    - `-1`: Sentinel. Scans **Global scopes only** (explicitly excludes character scopes).
    - **Precedence:** If `None`, and a scope name exists in both Global and Character lists, the **Character-owned scope** takes precedence (shadows global).
- `include_custom_scopes: bool = False` (Must be True to use `scopes`)

### Result labeling
Extend `ArbitrageOpportunity` with:
- `scope_name`
- `data_age`: `(now - http_last_modified)` (Age of CCP data).
- `last_checked`: `(now - updated_at)` (Time since last fetch attempt).
- `is_truncated`: Boolean. True if the specific price row has `fetch_status != 'complete'` OR if `market_scopes.last_scan_status == 'truncated'`.

---

## Cost Control & Safety
1.  **Structure Guardrails:**
    - Default `MAX_STRUCTURE_PAGES = 5`.
    - User must acknowledge "Structure scans read the entire market book" in documentation.
2.  **Watchlist Enforcement:**
    - **All** ad-hoc scopes (Region, System, Station, Structure) *must* have a watchlist.
    - Unbounded "full scans" are disabled to prevent accidentally fetching millions of orders.
3.  **Concurrency:**
    - Shared ESI fetcher respects global rate limits.

---

## Testing Plan (Phase 3/4)
1.  **Unit Tests:**
    - **Schema Constraints:**
        - Verify `market_scopes` constraints (unique names).
        - **Negative Test:** Attempt insert with invalid `last_scan_status` (should fail).
        - **Negative Test:** Attempt insert with invalid `fetch_status` in `market_scope_prices` (should fail).
    - **Watchlist Logic:** Verify `watchlist_items` join correctly.
2.  **Integration Tests (ESI Mock):**
    - **Pagination Limit:** Mock a structure with 10 pages. set limit to 3. Verify `fetch_status='truncated'` and orders from pages 1-3 are present.
    - **Type Filtering:** Mock region orders. Verify only watchlist items are fetched.
    - **Structure Auth:** Mock 403 Forbidden. Verify graceful failure (error message, no crash).
    - **ESI Cache Headers:**
        - Test 304 Not Modified behavior (preserves old timestamp, bumps `updated_at`).
        - Test missing headers fallback (sets `http_last_modified` = `updated_at`).
    - **Zero-Row Upsert:** Verify that a watchlist item with NO matching orders in ESI creates a `complete` row with 0 volume/orders.

---

## Open Questions Resolved
1.  **Shared ESI Fetcher:** Yes, we will refactor `_fetch_from_esi_fallback` into a shared `MarketFetcher` service to be used by both systems.
2.  **Scope Name Uniqueness:** Enforced via partial unique indexes using `owner_character_id` (immutable int). One index for `(scope_name, owner_character_id)` where owner is not null, and one for `scope_name` where owner is null.
3.  **Category Filters:** Converted to explicit `watchlist` items at configuration time to ensure deterministic fetch counts.


