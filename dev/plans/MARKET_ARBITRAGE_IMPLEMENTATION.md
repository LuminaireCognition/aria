# Market Arbitrage System Implementation Plan

## Overview

Enable ARIA to detect arbitrage opportunities across EVE regions and present actionable intelligence to pilots.

**Goal:** Identify profitable buy-in-region-A, sell-in-region-B opportunities with clear confidence indicators and execution guidance.

**Architecture Principle:** Request-triggered refresh with SQLite caching. No background daemons—fits Claude Code's request-response model.

---

## Scope Phases

| Phase | Scope | Value Delivered |
|-------|-------|-----------------|
| **V1** | Trade hub arbitrage (5 regions) | Core functionality, validates approach |
| **V2** | Secondary hubs (+10 regions) + Discovery | Broader coverage, dynamic item tracking |
| **V3** | Active nullsec (+20 regions) | Full market coverage |

This plan covers V1 in detail. V2/V3 expand the region set using the same infrastructure.

**Key V1 Simplifications:**
- Ship with pre-seeded trade hub data (no discovery phase required)
- Simple freshness-based confidence (not multi-factor scoring)
- Execution planning deferred to V2
- Focus on core scan → detail workflow

---

## API Strategy

### Fuzzwork vs ESI: When to Use Each

This system uses a **dual-API strategy** that leverages each service's strengths:

| Data Need | API | Why |
|-----------|-----|-----|
| Price aggregates (bulk) | **Fuzzwork** | 1 request = 100 items × 1 region |
| Regional trading activity | **ESI** | History endpoint shows actual volume |
| Order book depth | **ESI** | Individual orders for execution planning |
| NPC vs player orders | **ESI** | Duration field distinguishes them |
| Continuous monitoring | **Fuzzwork** | Efficient for known-active items |

### The Core Principle: Don't Scrape Dead Markets

**Problem:** Jita has orders for ~25,000 item types. A random nullsec region might have ~500. Most items have zero regional arbitrage potential.

**Solution:** Use ESI to *discover* what's worth tracking, then use Fuzzwork to *monitor* those items efficiently.

```
┌─────────────────────────────────────────────────────────────────┐
│                    DATA FLOW ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │              DISCOVERY LAYER (ESI)                       │   │
│   │              Runs: Weekly / On-demand                    │   │
│   │                                                          │   │
│   │   ESI /markets/{region}/history/                         │   │
│   │   → Which items actually trade in each region?           │   │
│   │   → What's the daily volume?                             │   │
│   │   → Worth monitoring?                                    │   │
│   │                                                          │   │
│   └─────────────────────┬───────────────────────────────────┘   │
│                         │                                        │
│                         ▼                                        │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │              TRACKING DATABASE                           │   │
│   │                                                          │   │
│   │   region_item_tracking:                                  │   │
│   │   - region_id, type_id, avg_daily_volume, last_seen     │   │
│   │   - Only items with volume > threshold                   │   │
│   │                                                          │   │
│   └─────────────────────┬───────────────────────────────────┘   │
│                         │                                        │
│                         ▼                                        │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │              MONITORING LAYER (Fuzzwork)                 │   │
│   │              Runs: On-demand with TTL (5-60 min tiers)   │   │
│   │                                                          │   │
│   │   Fuzzwork /aggregates/?region={id}&types={100 items}   │   │
│   │   → Only queries items known to trade in that region     │   │
│   │   → Efficient: 1 request per 100 items                   │   │
│   │   → Updates region_prices table                          │   │
│   │                                                          │   │
│   └─────────────────────┬───────────────────────────────────┘   │
│                         │                                        │
│                         ▼                                        │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │              ARBITRAGE DETECTION                         │   │
│   │              Runs: On-demand after refresh               │   │
│   │                                                          │   │
│   │   SQL joins across region_prices                         │   │
│   │   → Find price differentials                             │   │
│   │   → Calculate profit after fees                          │   │
│   │   → Populate arbitrage_opportunities table               │   │
│   │                                                          │   │
│   └─────────────────────┬───────────────────────────────────┘   │
│                         │                                        │
│                         ▼                                        │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │              DETAIL LAYER (ESI)                          │   │
│   │              Runs: On-demand only                        │   │
│   │                                                          │   │
│   │   ESI /markets/{region}/orders/?type_id={item}          │   │
│   │   → Full order book when user drills into opportunity    │   │
│   │   → Execution planning for large trades                  │   │
│   │   → NOT used for continuous monitoring                   │   │
│   │                                                          │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Rate Limit Budget

**Discovery Phase (ESI, weekly background):**
```
80 regions × 1000 candidate items = 80,000 history requests
ESI rate: ~150 req/sec sustained
Time to complete: ~9 minutes
Spread over a week: trivial load (~0.008 req/sec average)
```

**Monitoring Phase (Fuzzwork, continuous):**
```
Fuzzwork limit: ~30 req/min = 1,800 req/hr

Tier 1 (5 hubs, 5-min refresh):
  5 regions × 500 active items = 25 batches/cycle
  25 batches × 12 cycles/hr = 300 req/hr

Tier 2 (10 secondary, 15-min refresh):
  10 regions × 200 active items = 20 batches/cycle
  20 batches × 4 cycles/hr = 80 req/hr

Tier 3 (20 active nullsec, 1-hr refresh):
  20 regions × 50 active items = 10 batches/cycle
  10 batches × 1 cycle/hr = 10 req/hr

Tier 4 (45 other regions, 6-hr refresh):
  45 regions × 20 active items = 9 batches/cycle
  9 batches × 0.17 cycles/hr = 2 req/hr

TOTAL: ~392 req/hr (22% of budget)
```

**Detail Phase (ESI, on-demand):**
```
User requests order book depth: 1-2 requests per query
Negligible impact on rate limits
```

---

## V1 Cold Start: Pre-Seeded Data

**Problem:** Fresh installs have no market data. Without seeding, the first `/arbitrage` call returns empty results or requires a lengthy discovery process.

**Solution:** Ship V1 with pre-generated trade hub data. Discovery becomes a V2 enhancement.

### Seed Data Contents

```
.claude/scripts/aria_esi/data/
├── market_seed.db.gz          # SQLite database with trade hub items
└── seed_manifest.json         # Version info and item counts
```

**Seed database includes:**
- ~500 actively traded items per trade hub (2,500 total rows)
- Items selected by Jita volume (top 500 by daily turnover)
- Initial price snapshots (will refresh on first query)
- Region metadata for 5 trade hubs

### Seed Generation (Build-Time)

```python
# scripts/generate_market_seed.py
# Run during release build, not at runtime

async def generate_seed_database(output_path: str) -> None:
    """
    Generate seed database from current Fuzzwork data.
    Run this during release preparation, not at user runtime.
    """
    db = MarketDatabase(output_path)
    await db.initialize_schema()

    # Get top items from Jita (proxy for "items worth tracking")
    jita_items = await fuzzwork.get_top_traded_items(
        region_id=TRADE_HUBS["jita"]["region_id"],
        limit=500
    )

    # Populate tracking table for all 5 hubs
    for hub_name, hub_info in TRADE_HUBS.items():
        await db.seed_region_tracking(
            region_id=hub_info["region_id"],
            type_ids=[item.type_id for item in jita_items],
        )

    # Fetch initial prices (will be stale, but provides baseline)
    for hub_name, hub_info in TRADE_HUBS.items():
        prices = await fuzzwork.get_aggregates(
            [item.type_id for item in jita_items],
            region_id=hub_info["region_id"]
        )
        await db.upsert_region_prices(hub_info["region_id"], prices)

    # Compress for distribution
    compress_database(output_path, f"{output_path}.gz")
```

### Seed Extraction (First Run)

```python
# database.py

class MarketDatabase:
    async def ensure_seeded(self) -> bool:
        """
        Ensure database has seed data. Called on first arbitrage query.
        Returns True if seed was extracted, False if data already exists.
        """
        if await self.has_trade_hub_data():
            return False

        seed_path = Path(__file__).parent / "data" / "market_seed.db.gz"
        if not seed_path.exists():
            logger.warning("No seed data found - arbitrage will need discovery")
            return False

        logger.info("Extracting market seed data (first run)...")
        await self.import_seed_data(seed_path)
        return True

    async def has_trade_hub_data(self) -> bool:
        """Check if we have any tracked items for trade hubs."""
        count = await self.query_one("""
            SELECT COUNT(*) FROM region_item_tracking
            WHERE region_id IN (10000002, 10000043, 10000032, 10000042, 10000030)
        """)
        return count > 0
```

### CLI Commands

```bash
# Generate seed (maintainer only, during release)
uv run aria-esi market-seed generate --output data/market_seed.db

# Check seed status
uv run aria-esi market-seed status

# Force re-extract seed (troubleshooting)
uv run aria-esi market-seed extract --force
```

### Seed Data Freshness

Seed prices will be stale on first use. This is acceptable because:
1. First `/arbitrage` query triggers refresh anyway (TTL check)
2. Seed provides item list, not price accuracy
3. Users see "Data refreshed X minutes ago" in output

**Update cadence:** Generate new seed with each ARIA release (~monthly).

---

## Phase 0: Market Discovery (V2)

**Purpose:** Bootstrap the tracking database by discovering which items actually trade in each region.

**Note:** This phase is deferred to V2. V1 ships with pre-seeded trade hub data.

### 0.1 Discovery Schema

```sql
-- Track which items are worth monitoring per region
CREATE TABLE region_item_tracking (
    region_id INTEGER NOT NULL,
    type_id INTEGER NOT NULL,
    avg_daily_volume REAL,          -- 7-day average
    last_trade_date DATE,           -- Most recent trade
    discovery_date TIMESTAMP,       -- When we found this
    is_active BOOLEAN DEFAULT TRUE, -- Still worth tracking?
    PRIMARY KEY (region_id, type_id)
);

CREATE INDEX idx_tracking_region ON region_item_tracking(region_id);
CREATE INDEX idx_tracking_active ON region_item_tracking(is_active);
CREATE INDEX idx_tracking_volume ON region_item_tracking(avg_daily_volume DESC);

-- Discovery job status
CREATE TABLE discovery_jobs (
    region_id INTEGER PRIMARY KEY,
    last_full_scan TIMESTAMP,
    items_discovered INTEGER,
    next_scan_due TIMESTAMP,
    status TEXT DEFAULT 'pending'   -- pending, running, complete, error
);
```

### 0.2 Discovery Implementation

```python
# .claude/scripts/aria_esi/services/market_discovery.py

class MarketDiscovery:
    """Discover tradeable items per region using ESI history."""

    # Minimum volume to consider an item worth tracking
    MIN_DAILY_VOLUME = 5

    # Candidate items: start with Jita's most traded items
    # (avoids checking 30k items in regions with 500 active)
    MAX_CANDIDATES = 2000

    async def discover_region(self, region_id: int) -> DiscoveryResult:
        """
        Scan a region to find items with actual trading activity.

        Uses ESI /markets/{region_id}/history/ endpoint.
        """
        candidates = await self.db.get_candidate_items(limit=self.MAX_CANDIDATES)
        active_items = []

        for batch in chunked(candidates, 50):  # Parallel batches
            tasks = [
                self.esi.get_market_history(region_id, type_id)
                for type_id in batch
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for type_id, history in zip(batch, results):
                if isinstance(history, Exception):
                    continue

                # Calculate 7-day average volume
                recent = [h for h in history if h.date >= date.today() - timedelta(days=7)]
                if recent:
                    avg_volume = sum(h.volume for h in recent) / len(recent)
                    if avg_volume >= self.MIN_DAILY_VOLUME:
                        active_items.append(RegionItemTracking(
                            region_id=region_id,
                            type_id=type_id,
                            avg_daily_volume=avg_volume,
                            last_trade_date=max(h.date for h in recent)
                        ))

        await self.db.upsert_region_tracking(active_items)
        return DiscoveryResult(
            region_id=region_id,
            items_found=len(active_items),
            timestamp=datetime.utcnow()
        )

    async def full_discovery_scan(self) -> None:
        """
        Run discovery for all regions. Designed to run weekly.
        """
        regions = await self.db.get_all_regions()

        for region in regions:
            logger.info(f"Discovering market activity in {region.name}")
            await self.discover_region(region.region_id)
            # Brief pause between regions to be nice to ESI
            await asyncio.sleep(1)

    async def adaptive_cleanup(self) -> int:
        """
        Remove items that haven't traded in 30 days.
        Returns count of items deactivated.
        """
        cutoff = date.today() - timedelta(days=30)
        return await self.db.deactivate_stale_tracking(cutoff)
```

### 0.3 Candidate Item Selection

Instead of checking all 30,000+ item types, start with items known to have market activity:

```python
async def get_candidate_items(self, limit: int = 2000) -> list[int]:
    """
    Get candidate items worth checking in other regions.

    Strategy: Use Jita's most-traded items as candidates.
    If it doesn't trade in Jita, it probably doesn't trade anywhere.
    """
    # Option 1: Query Jita history for high-volume items
    jita_active = await self.db.query("""
        SELECT type_id FROM region_item_tracking
        WHERE region_id = 10000002  -- The Forge (Jita)
        AND is_active = TRUE
        ORDER BY avg_daily_volume DESC
        LIMIT ?
    """, (limit,))

    # Option 2: Use SDE market groups for tradeable items
    # Fallback if Jita hasn't been scanned yet
    if not jita_active:
        return await self.db.query("""
            SELECT type_id FROM types
            WHERE market_group_id IS NOT NULL
            ORDER BY type_id
            LIMIT ?
        """, (limit,))

    return [r.type_id for r in jita_active]
```

### 0.4 CLI Commands

```bash
# Run full discovery (all regions)
uv run aria-esi market-discovery full

# Discover specific region
uv run aria-esi market-discovery region "Delve"

# Show discovery status
uv run aria-esi market-discovery status

# Cleanup stale tracking entries
uv run aria-esi market-discovery cleanup --days 30
```

---

## Phase 1: Data Infrastructure

### 1.1 Database Schema

**Current:** SQLite with basic aggregates table
**Target:** SQLite with expanded schema (PostgreSQL optional for heavy usage)

```sql
-- Regional price snapshots (aggregated from Fuzzwork)
CREATE TABLE region_prices (
    type_id INTEGER NOT NULL,
    region_id INTEGER NOT NULL,
    buy_max REAL,           -- Best buy order price
    buy_volume INTEGER,     -- Total buy volume
    sell_min REAL,          -- Best sell order price
    sell_volume INTEGER,    -- Total sell volume
    spread_pct REAL,        -- (sell_min - buy_max) / sell_min * 100
    updated_at TIMESTAMP NOT NULL,
    PRIMARY KEY (type_id, region_id)
);

CREATE INDEX idx_region_prices_type ON region_prices(type_id);
CREATE INDEX idx_region_prices_updated ON region_prices(updated_at);

-- Regional metadata
CREATE TABLE regions (
    region_id INTEGER PRIMARY KEY,
    region_name TEXT NOT NULL,
    refresh_tier INTEGER DEFAULT 4,  -- 1=5min, 2=15min, 3=1hr, 4=6hr
    last_refresh TIMESTAMP,
    tracked_item_count INTEGER,      -- Items actively monitored
    is_active BOOLEAN DEFAULT TRUE
);

-- Global item metadata (from SDE)
CREATE TABLE tracked_items (
    type_id INTEGER PRIMARY KEY,
    type_name TEXT NOT NULL,
    category TEXT,                   -- Ship, Module, Implant, etc.
    volume_m3 REAL,                  -- For cargo calculations
    jita_daily_volume INTEGER,       -- Jita baseline for prioritization
    is_tracked BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 3       -- 1=high, 2=medium, 3=low
);

-- Arbitrage opportunities (computed)
CREATE TABLE arbitrage_opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type_id INTEGER NOT NULL,
    type_name TEXT NOT NULL,
    buy_region_id INTEGER NOT NULL,
    buy_region_name TEXT NOT NULL,
    buy_price REAL NOT NULL,
    sell_region_id INTEGER NOT NULL,
    sell_region_name TEXT NOT NULL,
    sell_price REAL NOT NULL,
    profit_per_unit REAL NOT NULL,
    profit_pct REAL NOT NULL,
    available_volume INTEGER,
    total_profit_potential REAL,
    route_jumps INTEGER,
    detected_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP,            -- Data staleness estimate
    UNIQUE(type_id, buy_region_id, sell_region_id)
);

CREATE INDEX idx_arb_profit ON arbitrage_opportunities(profit_pct DESC);
CREATE INDEX idx_arb_detected ON arbitrage_opportunities(detected_at);
```

### 1.2 Fuzzwork Client Enhancement

Fuzzwork already supports all regions. Ensure the client handles this properly:

```python
# .claude/scripts/aria_esi/mcp/market/clients.py

class FuzzworkClient:
    """
    Client for Fuzzwork market aggregates API.

    Supports ALL EVE regions, not just trade hubs.
    """

    BASE_URL = "https://market.fuzzwork.co.uk/aggregates/"
    MIN_REQUEST_INTERVAL = 2.0  # seconds
    MAX_TYPES_PER_REQUEST = 100

    async def get_aggregates(
        self,
        type_ids: list[int],
        region_id: int = 10000002,  # Default: The Forge (Jita)
        station_id: int | None = None
    ) -> dict[int, FuzzworkAggregate]:
        """
        Fetch aggregated market data for items in a region.

        Args:
            type_ids: List of type IDs (max 100 per request, auto-batched)
            region_id: EVE region ID (works for ANY region)
            station_id: Optional station filter (trade hubs only)

        Returns:
            Dict mapping type_id to aggregate data
        """
        results = {}

        for batch in chunked(type_ids, self.MAX_TYPES_PER_REQUEST):
            await self._rate_limit()

            params = {
                "region": region_id,
                "types": ",".join(str(t) for t in batch)
            }
            if station_id:
                params["station"] = station_id

            response = await self.session.get(self.BASE_URL, params=params)
            data = await response.json()

            for type_id_str, agg in data.items():
                results[int(type_id_str)] = FuzzworkAggregate(
                    buy_max=agg["buy"]["max"],
                    buy_min=agg["buy"]["min"],
                    buy_volume=agg["buy"]["volume"],
                    sell_max=agg["sell"]["max"],
                    sell_min=agg["sell"]["min"],
                    sell_volume=agg["sell"]["volume"],
                    # ... other fields
                )

        return results
```

---

## Phase 2: Request-Triggered Refresh

### 2.1 Architecture

**Key Design Decision:** No background daemon. Refresh happens on-demand when user queries arbitrage data. This fits Claude Code's request-response model and avoids process management complexity.

```
┌──────────────────────────────────────────────────────────────────┐
│                Request-Triggered Refresh Flow                     │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  User invokes /arbitrage or market_arbitrage_scan                │
│                                │                                  │
│                                ▼                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                  Staleness Check                            │  │
│  │                                                             │  │
│  │   For each region in query scope:                          │  │
│  │   1. Check last_refresh timestamp                          │  │
│  │   2. Compare against tier TTL (5min/15min/1hr/6hr)         │  │
│  │   3. Build list of stale regions                           │  │
│  │                                                             │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                │                                  │
│                                ▼                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                  Parallel Refresh                           │  │
│  │                                                             │  │
│  │   asyncio.gather() for stale regions:                      │  │
│  │   1. Get active items from region_item_tracking            │  │
│  │   2. Batch into 100-item chunks                            │  │
│  │   3. Query Fuzzwork aggregates (with rate limiting)        │  │
│  │   4. Update region_prices table                            │  │
│  │                                                             │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                │                                  │
│                                ▼                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                  Arbitrage Detection                        │  │
│  │                                                             │  │
│  │   Run cross-region SQL query on refreshed data:            │  │
│  │   1. Find price differentials                              │  │
│  │   2. Calculate profit after fees                           │  │
│  │   3. Score opportunities by confidence                     │  │
│  │   4. Return ranked results                                 │  │
│  │                                                             │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                │                                  │
│                                ▼                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                     SQLite Database                         │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

**Benefits over daemon approach:**
- No process management (start/stop/restart handling)
- No state synchronization between daemon and skill
- Data refreshed exactly when needed
- Zero resource consumption when not in use
- Fits Claude Code's existing request-response model

### 2.2 Refresh Tiers

| Tier | Regions | Refresh | Tracked Items | Rationale |
|------|---------|---------|---------------|-----------|
| 1 | Jita, Amarr, Dodixie, Rens, Hek | 5 min | ~500 each | Primary trade hubs, highest volume |
| 2 | Stacmon, Tash-Murkon, Agil, Orvolle, etc. | 15 min | ~200 each | Secondary hubs, lowsec staging |
| 3 | Delve, Fountain, Querious, Period Basis | 1 hour | ~50 each | Active nullsec markets |
| 4 | All other regions | 6 hours | ~20 each | Background coverage, low activity |

**Tier assignment is dynamic:** Regions graduate to higher tiers based on discovered trading activity.

### 2.3 Refresh Implementation

```python
# .claude/scripts/aria_esi/services/market_refresh.py

class MarketRefreshService:
    """
    On-demand market data refresh service.

    Uses Fuzzwork exclusively for price monitoring.
    Only queries items known to be active in each region.
    Refreshes stale data when queried, not on a schedule.
    """

    # TTL per tier (seconds)
    TIER_TTL = {
        1: 300,    # 5 minutes - trade hubs
        2: 900,    # 15 minutes - secondary hubs
        3: 3600,   # 1 hour - active nullsec
        4: 21600,  # 6 hours - background regions
    }

    def __init__(self, db_path: str):
        self.db = MarketDatabase(db_path)
        self.fuzzwork = FuzzworkClient()
        self.rate_limiter = TokenBucket(tokens=30, refill_rate=0.5)

    async def ensure_fresh_data(
        self,
        regions: list[int] | None = None,
        force_refresh: bool = False,
    ) -> RefreshResult:
        """
        Ensure data is fresh for specified regions before query.

        Args:
            regions: Region IDs to check (None = all tracked regions)
            force_refresh: Bypass staleness check, refresh anyway

        Returns:
            RefreshResult with regions refreshed and timing info
        """
        if regions is None:
            regions = await self.db.get_tracked_region_ids()

        # Check staleness
        stale_regions = []
        for region_id in regions:
            region = await self.db.get_region(region_id)
            if not region:
                continue

            ttl = self.TIER_TTL.get(region.refresh_tier, 21600)
            age = (datetime.utcnow() - region.last_refresh).total_seconds()

            if force_refresh or age > ttl:
                stale_regions.append(region)

        if not stale_regions:
            return RefreshResult(regions_refreshed=0, from_cache=True)

        # Parallel refresh with rate limiting
        start_time = time.time()
        tasks = [
            self._refresh_region(region)
            for region in stale_regions
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        success_count = sum(1 for r in results if not isinstance(r, Exception))
        errors = [str(r) for r in results if isinstance(r, Exception)]

        return RefreshResult(
            regions_refreshed=success_count,
            from_cache=False,
            refresh_time_seconds=time.time() - start_time,
            errors=errors if errors else None,
        )

    async def _refresh_region(self, region: Region) -> int:
        """
        Refresh a single region's price data from Fuzzwork.

        Returns count of items updated.
        """
        # Get only items that actually trade in this region
        active_items = await self.db.get_active_items_for_region(
            region.region_id
        )

        if not active_items:
            logger.debug(f"No active items for {region.name}, skipping")
            return 0

        total_updated = 0

        # Batch query Fuzzwork (100 items per request)
        for batch in chunked(active_items, 100):
            await self.rate_limiter.acquire()

            try:
                prices = await self.fuzzwork.get_aggregates(
                    [item.type_id for item in batch],
                    region_id=region.region_id
                )
                await self.db.upsert_region_prices(region.region_id, prices)
                total_updated += len(prices)

            except Exception as e:
                logger.error(f"Fuzzwork error for {region.name}: {e}")
                raise  # Let gather() collect the exception

        await self.db.update_region_last_refresh(region.region_id)
        return total_updated


@dataclass
class RefreshResult:
    """Result of a refresh operation."""
    regions_refreshed: int
    from_cache: bool = False
    refresh_time_seconds: float | None = None
    errors: list[str] | None = None
    api_unavailable: bool = False      # True if Fuzzwork/ESI was unreachable
    fallback_used: bool = False        # True if using stale cached data


class FuzzworkUnavailable(Exception):
    """Raised when Fuzzwork API is unreachable."""
    pass
```

### 2.6 API Downtime Handling

Graceful degradation when external APIs are unavailable:

```python
async def ensure_fresh_data(
    self,
    regions: list[int] | None = None,
    force_refresh: bool = False,
) -> RefreshResult:
    """
    Ensure data is fresh, with graceful fallback on API failure.
    """
    if regions is None:
        regions = await self.db.get_tracked_region_ids()

    # Check staleness
    stale_regions = await self._get_stale_regions(regions, force_refresh)

    if not stale_regions:
        return RefreshResult(regions_refreshed=0, from_cache=True)

    # Attempt refresh with error handling
    try:
        results = await self._refresh_regions(stale_regions)
        return RefreshResult(
            regions_refreshed=len(results),
            from_cache=False,
            refresh_time_seconds=results.elapsed,
        )
    except FuzzworkUnavailable as e:
        logger.warning(f"Fuzzwork unavailable: {e}")

        # Check if we have usable cached data
        cached_data = await self.db.get_cached_prices(regions, max_age_hours=24)

        if cached_data:
            return RefreshResult(
                regions_refreshed=0,
                from_cache=True,
                api_unavailable=True,
                fallback_used=True,
                errors=[f"Using cached data (up to 24h old) - Fuzzwork unavailable: {e}"],
            )
        else:
            # No cached data at all - must fail
            raise ArbitrageDataUnavailable(
                "Cannot fetch market data: Fuzzwork unavailable and no cached data exists. "
                "Try again later or run 'aria-esi market-refresh --force' when API is available."
            ) from e
    except Exception as e:
        logger.error(f"Unexpected refresh error: {e}")
        return RefreshResult(
            regions_refreshed=0,
            from_cache=True,
            errors=[f"Refresh failed: {e}"],
        )
```

**User-facing behavior:**
- If API down but cache exists: Show results with warning banner
- If API down and no cache: Clear error message with retry suggestion
- Never silently return stale data without indication

### 2.7 ESI Aggregation Fallback (V1)

When Fuzzwork is unavailable and cached data is too stale, fall back to direct ESI aggregation. This pattern already exists in `cache.py:376-506` for non-trade-hub regions—we reuse it as a Fuzzwork fallback.

```python
# .claude/scripts/aria_esi/services/market_refresh.py

class ESIAggregationFallback:
    """
    Fallback price aggregation when Fuzzwork is unavailable.

    Uses ESI /markets/{region}/orders/ endpoint and aggregates locally.
    Slower than Fuzzwork (1 request per item vs 100 items per request)
    but provides resilience when Fuzzwork is down.
    """

    def __init__(self, esi_client: ESIClient):
        self.esi = esi_client
        self.rate_limiter = TokenBucket(tokens=100, refill_rate=50)  # ESI allows ~150/sec

    async def get_aggregates(
        self,
        type_ids: list[int],
        region_id: int,
    ) -> dict[int, FuzzworkAggregate]:
        """
        Fetch and aggregate prices from ESI orders.

        Note: Much slower than Fuzzwork. Use only as fallback.
        For 100 items: Fuzzwork = 1 request, ESI = 200 requests (buy + sell).
        """
        results = {}

        # Limit to essential items when in fallback mode
        priority_items = type_ids[:50]  # Cap at 50 items in fallback

        for type_id in priority_items:
            await self.rate_limiter.acquire()

            try:
                buy_orders = await self.esi.get_market_orders(
                    region_id, type_id, order_type="buy"
                )
                sell_orders = await self.esi.get_market_orders(
                    region_id, type_id, order_type="sell"
                )

                # Aggregate using existing pattern from cache.py
                results[type_id] = self._aggregate_to_fuzzwork_format(
                    buy_orders, sell_orders
                )
            except Exception as e:
                logger.debug(f"ESI fallback failed for {type_id}: {e}")
                continue

        return results

    def _aggregate_to_fuzzwork_format(
        self,
        buy_orders: list[dict],
        sell_orders: list[dict],
    ) -> FuzzworkAggregate:
        """Convert raw ESI orders to FuzzworkAggregate format."""
        # Reuse aggregation logic from MarketCache._aggregate_orders
        buy_agg = aggregate_orders(buy_orders, is_buy=True)
        sell_agg = aggregate_orders(sell_orders, is_buy=False)

        return FuzzworkAggregate(
            buy_max=buy_agg.max_price or 0,
            buy_min=buy_agg.min_price or 0,
            buy_volume=buy_agg.volume,
            buy_order_count=buy_agg.order_count,
            buy_weighted_average=buy_agg.weighted_avg or 0,
            sell_max=sell_agg.max_price or 0,
            sell_min=sell_agg.min_price or 0,
            sell_volume=sell_agg.volume,
            sell_order_count=sell_agg.order_count,
            sell_weighted_average=sell_agg.weighted_avg or 0,
        )
```

**Updated refresh flow with ESI fallback:**

```python
async def _refresh_region(self, region: Region) -> int:
    """Refresh region with Fuzzwork → ESI fallback chain."""
    active_items = await self.db.get_active_items_for_region(region.region_id)

    if not active_items:
        return 0

    type_ids = [item.type_id for item in active_items]

    # Try Fuzzwork first (fast, efficient)
    try:
        prices = await self.fuzzwork.get_aggregates(type_ids, region.region_id)
        await self.db.upsert_region_prices(region.region_id, prices)
        return len(prices)

    except FuzzworkUnavailable as e:
        logger.warning(f"Fuzzwork unavailable for {region.name}, trying ESI fallback")

        # Fall back to ESI aggregation (slower but works)
        try:
            prices = await self.esi_fallback.get_aggregates(type_ids, region.region_id)
            if prices:
                await self.db.upsert_region_prices(region.region_id, prices)
                logger.info(f"ESI fallback successful: {len(prices)} items for {region.name}")
                return len(prices)
        except Exception as esi_error:
            logger.warning(f"ESI fallback also failed: {esi_error}")

        # Both APIs failed - re-raise original Fuzzwork error
        raise
```

**Why this matters for V1:**
- Fuzzwork is a single point of failure maintained by one person
- ESI is CCP's official API with better availability guarantees
- The aggregation code already exists in `cache.py`—this just wires it as a fallback
- Minimal additional complexity for significant resilience improvement

### 2.4 Adaptive Tier Promotion

Regions can be promoted/demoted based on activity:

```python
async def evaluate_tier_assignments(self) -> list[TierChange]:
    """
    Evaluate regions for tier promotion/demotion based on activity.
    """
    changes = []

    for region in await self.db.get_all_regions():
        active_count = await self.db.count_active_items(region.region_id)
        current_tier = region.refresh_tier

        # Promotion thresholds
        if active_count >= 300 and current_tier > 1:
            changes.append(TierChange(region.region_id, current_tier, 1))
        elif active_count >= 100 and current_tier > 2:
            changes.append(TierChange(region.region_id, current_tier, 2))
        elif active_count >= 30 and current_tier > 3:
            changes.append(TierChange(region.region_id, current_tier, 3))

        # Demotion thresholds
        elif active_count < 10 and current_tier < 4:
            changes.append(TierChange(region.region_id, current_tier, 4))
        elif active_count < 30 and current_tier < 3:
            changes.append(TierChange(region.region_id, current_tier, 3))

    return changes
```

### 2.5 CLI Entry Points

```bash
# Refresh market data (on-demand, respects TTL)
uv run aria-esi market-refresh

# Force refresh all trade hubs
uv run aria-esi market-refresh --tier 1 --force

# Refresh specific region
uv run aria-esi market-refresh --region "The Forge"

# View data freshness status
uv run aria-esi market-status

# Adjust tier for a region
uv run aria-esi market-tier set "Delve" 2

# View tier assignments
uv run aria-esi market-tier list

# Evaluate tier changes based on activity
uv run aria-esi market-tier evaluate --apply
```

---

## Phase 3: Arbitrage Detection Engine

### 3.1 Opportunity Detection Query

```sql
WITH price_pairs AS (
    SELECT
        p1.type_id,
        t.type_name,
        t.volume_m3,
        p1.region_id AS buy_region,
        r1.region_name AS buy_region_name,
        p1.sell_min AS buy_price,      -- Buy from sell orders
        p1.sell_volume AS buy_avail,
        p2.region_id AS sell_region,
        r2.region_name AS sell_region_name,
        p2.buy_max AS sell_price,      -- Sell to buy orders
        p2.buy_volume AS sell_demand,
        p2.buy_max - p1.sell_min AS profit_per_unit,
        (p2.buy_max - p1.sell_min) / p1.sell_min * 100 AS profit_pct,
        MIN(p1.sell_volume, p2.buy_volume) AS tradeable_volume
    FROM region_prices p1
    JOIN region_prices p2 ON p1.type_id = p2.type_id AND p1.region_id != p2.region_id
    JOIN regions r1 ON p1.region_id = r1.region_id
    JOIN regions r2 ON p2.region_id = r2.region_id
    JOIN tracked_items t ON p1.type_id = t.type_id
    WHERE p1.updated_at > datetime('now', '-30 minutes')
      AND p2.updated_at > datetime('now', '-30 minutes')
      AND p2.buy_max > p1.sell_min  -- Actual profit exists
      AND p1.sell_min > 0           -- Valid prices
      AND p2.buy_max > 0
)
SELECT *,
    profit_per_unit * tradeable_volume AS total_profit
FROM price_pairs
WHERE profit_pct >= :min_profit_pct
  AND tradeable_volume >= :min_volume
ORDER BY total_profit DESC
LIMIT :limit;
```

### 3.2 Cost Adjustments

Real arbitrage profit must account for:

```python
@dataclass
class ArbitrageCalculator:
    """
    Calculate true arbitrage profit with all costs.

    IMPORTANT: This assumes NPC station fees. Citadel fees vary (0-10%+)
    and are not modeled. Results include a warning for citadel trades.
    """

    # EVE Online market fees (base rates for NPC stations)
    BROKER_FEE_PCT = 1.0       # Base broker fee (skills reduce this)
    SALES_TAX_PCT = 2.0        # Base sales tax (skills reduce this)

    # Track last calculation for reporting
    last_broker_buy: float = 0.0
    last_broker_sell: float = 0.0
    last_sales_tax: float = 0.0
    last_total_fees: float = 0.0

    def calculate_true_profit(
        self,
        buy_price: float,
        sell_price: float,
        quantity: int,
        route_jumps: int,
        cargo_m3: float,
        broker_skill: int = 0,     # Broker Relations level (0-5)
        accounting_skill: int = 0  # Accounting level (0-5)
    ) -> ArbitrageResult:
        """
        Calculate profit after all costs.

        Fee formulas (as of 2025):
        - Broker fee: 1% base, -0.1% per Broker Relations level (min 0.5%)
        - Sales tax: 2% base, -0.11% per Accounting level (min ~1.45%)

        Note: Does not account for standings or citadel fees.
        """
        # Adjust fees for skills
        broker_fee = max(0.5, self.BROKER_FEE_PCT - 0.1 * broker_skill)
        sales_tax = max(1.45, self.SALES_TAX_PCT - 0.11 * accounting_skill)

        # Buy side costs (buying from sell orders)
        buy_total = buy_price * quantity
        buy_broker = buy_total * broker_fee / 100

        # Sell side costs (selling to buy orders = instant sell, no broker fee)
        # But if placing sell order, broker fee applies
        sell_total = sell_price * quantity
        sell_broker = sell_total * broker_fee / 100  # If placing order
        sell_tax = sell_total * sales_tax / 100

        gross_profit = sell_total - buy_total
        total_fees = buy_broker + sell_broker + sell_tax
        net_profit = gross_profit - total_fees

        # Store for reporting
        self.last_broker_buy = buy_broker
        self.last_broker_sell = sell_broker
        self.last_sales_tax = sell_tax
        self.last_total_fees = total_fees

        return ArbitrageResult(
            gross_profit=gross_profit,
            broker_fees=buy_broker + sell_broker,
            sales_tax=sell_tax,
            net_profit=net_profit,
            roi_pct=(net_profit / buy_total) * 100 if buy_total > 0 else 0,
            isk_per_jump=net_profit / max(1, route_jumps),
            isk_per_m3=net_profit / max(1, cargo_m3 * quantity)
        )


@dataclass
class ArbitrageResult:
    """Result of profit calculation."""
    gross_profit: float
    broker_fees: float
    sales_tax: float
    net_profit: float
    roi_pct: float
    isk_per_jump: float
    isk_per_m3: float
```

**Citadel Fee Limitation:** Player citadels can set arbitrary broker fees (0-10%+). This calculator assumes NPC station rates. When displaying results, include a warning:

> ⚠️ Fee calculation assumes NPC station rates. Citadel fees vary.

### 3.3 Opportunity Scoring & Confidence

#### V1: Simple Freshness-Based Confidence

For V1, confidence is based purely on data freshness. This is simple to implement and covers the primary concern (stale data leading to false opportunities).

```python
# V1 Implementation - Simple freshness-based confidence

FreshnessLevel = Literal["fresh", "recent", "stale"]


def determine_confidence_v1(data_age_seconds: int) -> FreshnessLevel:
    """
    V1: Simple freshness-based confidence.

    - fresh: Data < 5 minutes old (trade hub TTL)
    - recent: Data 5-30 minutes old
    - stale: Data > 30 minutes old (shown with warning)
    """
    if data_age_seconds < 300:  # 5 min
        return "fresh"
    elif data_age_seconds < 1800:  # 30 min
        return "recent"
    else:
        return "stale"


def score_opportunity_v1(opp: ArbitrageOpportunity) -> float:
    """
    V1: Simple scoring by profit percentage.

    More sophisticated scoring (volume, route safety) deferred to V2.
    """
    # Primary sort: profit percentage (capped at 50% to avoid outliers)
    return min(opp.profit_pct, 50.0)
```

**V1 Display:**
- `fresh` → Show normally
- `recent` → Show with subtle indicator (e.g., `(~15m ago)`)
- `stale` → **Prominent warning, require acknowledgment**

#### Strengthened Stale Data Handling

Stale data (>30 minutes) is the primary source of false arbitrage opportunities. Users acting on stale data lose ISK. To prevent this:

**Option A: Require explicit flag for stale results (Recommended)**

```python
async def market_arbitrage_scan(
    ...
    allow_stale: bool = False,  # Must opt-in to see stale data
) -> dict:
    """
    ...
    Args:
        allow_stale: If False (default), opportunities based on data older
                     than 30 minutes are excluded. Set True to include with
                     prominent warnings.
    """
    opportunities = await db.find_arbitrage(...)

    if not allow_stale:
        opportunities = [o for o in opportunities if o.freshness != "stale"]

        if excluded_count := len(original) - len(opportunities):
            warnings.append(
                f"Excluded {excluded_count} opportunities based on stale data. "
                "Use --allow-stale to include them (not recommended for trading)."
            )
```

**Option B: Prominent visual warning**

If stale data is included, render it distinctly:

```
═══════════════════════════════════════════════════════════════════
⚠️ WARNING: STALE DATA - DO NOT TRADE WITHOUT VERIFICATION
The following opportunities are based on data >30 minutes old.
Market conditions have likely changed. Use /arbitrage detail to
verify with live order book before acting.
───────────────────────────────────────────────────────────────────

| Item (STALE) | Buy (Region) | Sell (Region) | Margin | Vol | Age |
|--------------|--------------|---------------|--------|-----|-----|
| ⚠️ Caldari Navy... | 18.2M (Jita) | 21.5M (Amarr) | 12.3% | 45 | 47m |
```

**Skill output adaptation:**

```python
# In /arbitrage skill rendering
if any(opp.freshness == "stale" for opp in opportunities):
    output.insert(0, STALE_DATA_WARNING_BANNER)
    output.append("\nRun `/arbitrage --force-refresh` for current data.")
```

**Rationale:** Users skimming output may miss inline warnings. A header banner and distinct row formatting make stale data impossible to miss. The `allow_stale` flag makes seeing stale data a conscious decision.

#### V2: Multi-Factor Confidence (Deferred)

V2 adds volume and margin suspicion to confidence calculation:

```python
# V2 Implementation - Multi-factor confidence (DEFERRED)

ConfidenceLevel = Literal["high", "medium", "low"]


def determine_confidence_v2(
    data_age_seconds: int,
    volume: int,
    profit_margin: float,
) -> ConfidenceLevel:
    """
    V2: Multi-factor confidence scoring.

    High confidence: Fresh data, good volume, reasonable margin
    Medium confidence: Slightly stale or low volume
    Low confidence: Stale data, very low volume, or suspiciously high margin
    """
    # Suspiciously high margins often indicate stale data or errors
    if profit_margin > 50:
        return "low"

    # Very stale data
    if data_age_seconds > 1800:  # 30 min
        return "low"

    # Low volume = hard to execute
    if volume < 10:
        return "low"

    # Moderately stale or moderate volume
    if data_age_seconds > 600 or volume < 50:  # 10 min
        return "medium"

    return "high"


def score_opportunity_v2(opp: ArbitrageOpportunity) -> float:
    """
    V2: Weighted multi-factor scoring.
    """
    weights = {
        'profit_pct': 0.25,     # Higher margin = better
        'total_profit': 0.20,   # Absolute ISK matters
        'volume_ratio': 0.20,   # Good volume = executable
        'route_safety': 0.15,   # Highsec preferred
        'freshness': 0.20       # Recent data = reliable
    }

    scores = {
        'profit_pct': min(opp.profit_pct / 20, 1.0),
        'total_profit': min(opp.total_profit / 100_000_000, 1.0),
        'volume_ratio': min(opp.available_volume / 100, 1.0),
        'route_safety': 1.0 if opp.is_highsec_route else 0.3,
        'freshness': max(0, 1 - opp.data_age_seconds / 1800)
    }

    return sum(weights[k] * scores[k] for k in weights)
```

**Rationale for deferral:** V1 validates the core workflow. User feedback will inform whether multi-factor scoring adds value or just complexity.

---

### 3.4 Execution Planning

#### V1: Basic Execution Info

V1 provides essential information without complex modeling:

```python
@dataclass
class BasicExecutionInfo:
    """V1: Minimal execution information."""

    type_id: int
    type_name: str
    cargo_m3: float                    # Total cargo volume
    route_jumps: int | None            # Jump count (from universe_route)
    is_highsec_route: bool             # Route safety flag
    estimated_profit: float            # Gross profit (fees shown separately)

    # Fee disclaimer (not calculated precisely)
    fee_warning: str = "Assumes ~3% total fees (broker + tax). Actual fees depend on skills and station type."
```

**V1 explicitly does NOT include:**
- Slippage modeling
- Ship recommendations
- Gank threshold calculations
- Collateral recommendations

These are shown as static tips in the skill output instead.

#### V2: Full Execution Planning (Deferred)

V2 adds comprehensive execution planning as a separate tool:

```python
def build_execution_plan(
    buy_orders: list[MarketOrder],
    sell_orders: list[MarketOrder],
    type_info: TypeInfo,
    route: RouteResult | None,
    calculator: ArbitrageCalculator,
) -> ExecutionPlan:
    """
    Build practical execution advice for an arbitrage opportunity.

    Considers:
    - Order book depth (slippage for large orders)
    - Cargo volume and ship requirements
    - Route risk assessment
    - Collateral recommendations
    """
    # Calculate optimal quantity based on order depth
    # Don't recommend buying more than exists at reasonable prices
    buy_depth = calculate_depth_at_margin(buy_orders, margin_tolerance=0.02)
    sell_depth = calculate_depth_at_margin(sell_orders, margin_tolerance=0.02)
    recommended_qty = min(buy_depth.volume, sell_depth.volume)

    # Calculate slippage-adjusted costs
    expected_buy_cost = calculate_cost_with_slippage(buy_orders, recommended_qty)
    expected_sell_revenue = calculate_revenue_with_slippage(sell_orders, recommended_qty)

    # Cargo calculation
    cargo_m3 = type_info.volume_m3 * recommended_qty

    # Ship recommendation based on cargo
    if cargo_m3 < 5_000:
        recommended_ship = "T1 Industrial (Nereus, Badger)"
    elif cargo_m3 < 25_000:
        recommended_ship = "T1 Industrial with expanders or Epithal"
    elif cargo_m3 < 60_000:
        recommended_ship = "Deep Space Transport (Occator, Mastodon)"
    elif cargo_m3 < 350_000:
        recommended_ship = "Blockade Runner for high-value, Freighter for bulk"
    else:
        recommended_ship = "Freighter or multiple trips"

    # Route risk assessment
    route_risk = "safe"
    gank_risk_isk = None
    risk_notes = []

    if route:
        if any(s.security < 0.5 for s in route.systems):
            route_risk = "dangerous"
            risk_notes.append("Route passes through low/null security space")
        elif any(s.security < 0.7 for s in route.systems):
            route_risk = "moderate"
            risk_notes.append("Route passes through 0.5-0.6 security systems")

        # Gank threshold estimation (simplified)
        # Rough rule: Catalyst ganks profitable above ~100M in 0.5 systems
        if route_risk != "safe":
            min_sec = min(s.security for s in route.systems)
            if min_sec >= 0.5:
                gank_risk_isk = 100_000_000  # 100M threshold for high-sec ganks
                if expected_buy_cost > gank_risk_isk:
                    risk_notes.append(f"Cargo value exceeds gank threshold (~{gank_risk_isk/1e6:.0f}M)")

    # Collateral recommendation for courier contracts
    collateral = expected_buy_cost * 1.1 if expected_buy_cost > 50_000_000 else None

    return ExecutionPlan(
        type_id=type_info.type_id,
        type_name=type_info.type_name,
        recommended_quantity=recommended_qty,
        expected_buy_cost=expected_buy_cost,
        expected_sell_revenue=expected_sell_revenue,
        expected_net_profit=expected_sell_revenue - expected_buy_cost - calculator.last_total_fees,
        cargo_m3=cargo_m3,
        recommended_ship=recommended_ship,
        collateral_recommended=collateral,
        route_risk=route_risk,
        gank_risk_isk=gank_risk_isk,
        risk_notes=risk_notes,
    )


def calculate_cost_with_slippage(orders: list[MarketOrder], quantity: int) -> float:
    """
    Calculate total cost to buy `quantity` units, accounting for slippage.

    Works through the order book from best to worst price.
    """
    remaining = quantity
    total_cost = 0.0

    for order in sorted(orders, key=lambda o: o.price):  # Cheapest first
        if remaining <= 0:
            break
        take = min(remaining, order.volume_remain)
        total_cost += take * order.price
        remaining -= take

    return total_cost
```

#### V2 Tool: `market_execution_plan` (Deferred)

Consider exposing execution planning as a separate MCP tool in V2:

```python
@tool
async def market_execution_plan(
    type_name: str,
    buy_region: str,
    sell_region: str,
    quantity: int | None = None,  # Auto-calculate if None
    pilot_skills: dict | None = None,
) -> dict:
    """
    V2: Generate detailed execution plan for an arbitrage trade.

    Separate from market_arbitrage_detail to keep core path simple.
    """
    ...
```

This keeps V1 focused on opportunity discovery while V2 adds execution optimization.

---

### 3.5 Pydantic Models

Add to `.claude/scripts/aria_esi/models/market.py`:

```python
# =============================================================================
# Arbitrage Models
# =============================================================================

# V1: Simple freshness-based classification
FreshnessLevel = Literal["fresh", "recent", "stale"]
"""
V1 freshness classification:
- fresh: Data < 5 minutes old
- recent: Data 5-30 minutes old
- stale: Data > 30 minutes old (shown with warning)
"""

# V2: Multi-factor confidence (deferred)
ConfidenceLevel = Literal["high", "medium", "low"]
"""
V2 confidence classification (DEFERRED):
- high: Fresh data (<10 min), good volume (>50), reasonable margin
- medium: Moderately stale or lower volume
- low: Stale data, very low volume, or suspiciously high margin
"""


class ArbitrageOpportunity(MarketModel):
    """
    A detected arbitrage opportunity between two regions.
    """

    type_id: int = Field(ge=1, description="Item type ID")
    type_name: str = Field(description="Item name")

    # Buy side (where to purchase)
    buy_region: str = Field(description="Region to buy from")
    buy_region_id: int = Field(ge=1)
    buy_price: float = Field(ge=0, description="Best sell order price (instant buy)")
    buy_volume: int = Field(ge=0, description="Volume available at buy_price")

    # Sell side (where to sell)
    sell_region: str = Field(description="Region to sell in")
    sell_region_id: int = Field(ge=1)
    sell_price: float = Field(ge=0, description="Best buy order price (instant sell)")
    sell_volume: int = Field(ge=0, description="Volume demanded at sell_price")

    # Profit calculation
    gross_profit_per_unit: float = Field(description="sell_price - buy_price")
    net_profit_per_unit: float = Field(description="After broker fees and sales tax")
    profit_pct: float = Field(description="Net profit as percentage of buy_price")
    available_volume: int = Field(ge=0, description="min(buy_volume, sell_volume)")
    total_profit_potential: float = Field(ge=0, description="net_profit * available_volume")

    # Route info (populated via universe_route integration)
    route_jumps: int | None = Field(default=None, ge=0, description="Jump count via safe route")
    is_highsec_route: bool = Field(default=True, description="True if route is entirely highsec")
    route_systems: list[str] | None = Field(default=None, description="System names if route calculated")

    # Data quality
    data_age_seconds: int = Field(ge=0, description="Age of oldest price data used")
    freshness: FreshnessLevel = Field(description="V1: Freshness level based on data age")
    confidence: ConfidenceLevel | None = Field(default=None, description="V2: Multi-factor confidence (optional)")
    score: float = Field(ge=0, le=1, description="Ranking score (V1: profit_pct, V2: multi-factor)")


class ArbitrageScanResult(MarketModel):
    """
    Result from market_arbitrage_scan tool.
    """

    opportunities: list[ArbitrageOpportunity] = Field(default_factory=list)
    total_found: int = Field(ge=0)
    regions_scanned: list[str] = Field(default_factory=list)
    refresh_performed: bool = Field(description="True if data was refreshed for this query")
    refresh_time_seconds: float | None = Field(default=None)
    filters_applied: dict = Field(default_factory=dict, description="Filters used in query")
    warnings: list[str] = Field(default_factory=list)


class BasicExecutionInfo(MarketModel):
    """
    V1: Minimal execution information.

    Provides essential data without complex modeling.
    """

    type_id: int = Field(ge=1)
    type_name: str
    cargo_m3: float = Field(ge=0, description="Total cargo volume for recommended quantity")
    route_jumps: int | None = Field(default=None, ge=0, description="Jump count via safe route")
    is_highsec_route: bool = Field(default=True, description="True if route is entirely highsec")
    estimated_gross_profit: float = Field(description="Gross profit before fees")

    # Fee disclaimer instead of precise calculation
    fee_estimate_pct: float = Field(default=3.0, description="Conservative fee estimate (broker + tax)")
    fee_warning: str = Field(
        default="Fee estimate assumes ~3% total. Actual fees depend on skills, standings, and station type."
    )


class ExecutionPlan(MarketModel):
    """
    V2: Full execution planning (DEFERRED).

    Practical advice for executing an arbitrage trade with slippage,
    ship recommendations, and risk assessment.
    """

    type_id: int = Field(ge=1)
    type_name: str

    # Recommended execution
    recommended_quantity: int = Field(ge=0, description="Quantity to trade for best profit")
    expected_buy_cost: float = Field(ge=0, description="Total buy cost including slippage")
    expected_sell_revenue: float = Field(ge=0, description="Total sell revenue including slippage")
    expected_net_profit: float = Field(description="Revenue - cost - fees")

    # Logistics
    cargo_m3: float = Field(ge=0, description="Total cargo volume")
    recommended_ship: str = Field(description="Ship recommendation based on cargo/route")
    collateral_recommended: float | None = Field(default=None, ge=0, description="If using courier contract")

    # Risk
    route_risk: Literal["safe", "moderate", "dangerous"] = Field(description="Route safety assessment")
    gank_risk_isk: float | None = Field(default=None, ge=0, description="Estimated gank threshold")
    risk_notes: list[str] = Field(default_factory=list)


class ArbitrageDetailResult(MarketModel):
    """
    Result from market_arbitrage_detail tool.

    Detailed analysis with live order book data.
    """

    opportunity: ArbitrageOpportunity

    # V1: Basic execution info
    execution_info: BasicExecutionInfo

    # V2: Full execution plan (optional, populated when available)
    execution_plan: ExecutionPlan | None = Field(default=None, description="V2: Full execution planning")

    # Live order book (from ESI, not cached)
    buy_orders: list[MarketOrder] = Field(default_factory=list, description="Sell orders to buy from")
    sell_orders: list[MarketOrder] = Field(default_factory=list, description="Buy orders to sell to")

    # Fee info (V1: estimates only, V2: precise calculation)
    fee_estimate_pct: float = Field(default=3.0, description="Conservative fee estimate")
    broker_fee_buy: float | None = Field(default=None, ge=0, description="V2: Precise broker fee")
    broker_fee_sell: float | None = Field(default=None, ge=0, description="V2: Precise broker fee")
    sales_tax: float | None = Field(default=None, ge=0, description="V2: Precise sales tax")
    total_fees: float | None = Field(default=None, ge=0, description="V2: Total precise fees")

    # Route detail
    route: list[dict] | None = Field(default=None, description="Full route from universe_route")

    freshness: FreshnessLevel = Field(default="fresh")
    warnings: list[str] = Field(default_factory=list)
```

---

## Phase 4: MCP Tools

### 4.1 New Tools

```python
# tools_arbitrage.py

@tool
async def market_arbitrage_scan(
    min_profit_pct: float = 5.0,
    min_volume: int = 10,
    max_results: int = 20,
    include_lowsec: bool = False,
    category_filter: str | None = None,
    min_confidence: str = "medium",  # "high", "medium", "low"
    force_refresh: bool = False,
) -> dict:
    """
    Scan for arbitrage opportunities across tracked regions.

    Automatically refreshes stale data before scanning. Use force_refresh
    to bypass TTL and get fresh data regardless of age.

    IMPORTANT: This is a scanner, not a trading bot. Always verify
    opportunities with market_arbitrage_detail before executing trades.

    Args:
        min_profit_pct: Minimum profit percentage after fees (default: 5%)
        min_volume: Minimum tradeable volume (default: 10)
        max_results: Maximum opportunities to return (default: 20)
        include_lowsec: Include routes through lowsec (default: False)
        category_filter: Filter by item category (ships, modules, etc.)
        min_confidence: Minimum confidence level (default: medium)
        force_refresh: Force data refresh regardless of TTL

    Returns:
        ArbitrageScanResult with ranked opportunities and confidence levels
    """
    # Ensure data freshness before querying
    refresh_service = MarketRefreshService()
    refresh_result = await refresh_service.ensure_fresh_data(
        force_refresh=force_refresh
    )

    # Query opportunities from database
    opportunities = await db.find_arbitrage(
        min_profit_pct=min_profit_pct,
        min_volume=min_volume,
        min_confidence=min_confidence,
    )

    # Calculate routes for top opportunities IN PARALLEL
    # Routes are independent, so parallelize for better latency
    opportunities_needing_routes = [
        opp for opp in opportunities[:max_results]
        if opp.route_jumps is None
    ]

    if opportunities_needing_routes:
        # Calculate routes in parallel with timeout to prevent slow routes from
        # blocking the entire scan. Route calculation typically takes 50ms-2s
        # but can occasionally hang. 3s timeout ensures responsive UX.
        ROUTE_TIMEOUT_SECONDS = 3.0

        route_tasks = [
            asyncio.wait_for(
                calculate_route(opp, include_lowsec),
                timeout=ROUTE_TIMEOUT_SECONDS
            )
            for opp in opportunities_needing_routes
        ]
        routes = await asyncio.gather(*route_tasks, return_exceptions=True)

        for opp, route in zip(opportunities_needing_routes, routes):
            if isinstance(route, asyncio.TimeoutError):
                logger.warning(f"Route calculation timed out for {opp.type_name}")
                opp.route_jumps = None
                opp.is_highsec_route = True  # Assume safe if unknown (conservative)
                opp.route_warning = "Route calculation timed out"
            elif isinstance(route, Exception):
                logger.warning(f"Route calculation failed for {opp.type_name}: {route}")
                opp.route_jumps = None
                opp.is_highsec_route = True  # Assume safe if unknown
            elif route:
                opp.route_jumps = route.total_jumps
                opp.is_highsec_route = route.is_highsec
            else:
                opp.route_jumps = None
                opp.is_highsec_route = True

    # Filter by route safety
    if not include_lowsec:
        opportunities = [o for o in opportunities if o.is_highsec_route]

    # Score and rank
    for opp in opportunities:
        opp.score, opp.confidence = score_opportunity(opp)

    opportunities.sort(key=lambda o: o.score, reverse=True)

    return ArbitrageScanResult(
        opportunities=opportunities[:max_results],
        total_found=len(opportunities),
        regions_scanned=await db.get_tracked_region_names(),
        refresh_performed=not refresh_result.from_cache,
        refresh_time_seconds=refresh_result.refresh_time_seconds,
        filters_applied={
            "min_profit_pct": min_profit_pct,
            "min_volume": min_volume,
            "include_lowsec": include_lowsec,
            "min_confidence": min_confidence,
        },
    ).model_dump()


@tool
async def market_arbitrage_detail(
    type_name: str,
    buy_region: str,
    sell_region: str,
    pilot_skills: dict | None = None,  # Optional: {"broker_relations": 5, "accounting": 4}
) -> dict:
    """
    Get detailed analysis of a specific arbitrage opportunity.

    Fetches LIVE order book from ESI (not cached) for accurate execution planning.
    Include pilot_skills to calculate accurate fees based on your character.

    Args:
        type_name: Item to analyze
        buy_region: Region to buy from (name or ID)
        sell_region: Region to sell in (name or ID)
        pilot_skills: Optional skill levels for fee calculation

    Returns:
        ArbitrageDetailResult with live order book, execution plan, and route
    """
    # Resolve type and regions
    type_info = db.resolve_type_name(type_name)
    buy_region_info = resolve_region(buy_region)
    sell_region_info = resolve_region(sell_region)

    # Fetch LIVE orders from ESI (not Fuzzwork cache)
    buy_orders = await esi.get_market_orders(
        buy_region_info["region_id"], type_info.type_id, "sell"
    )
    sell_orders = await esi.get_market_orders(
        sell_region_info["region_id"], type_info.type_id, "buy"
    )

    # Sort for execution planning
    buy_orders.sort(key=lambda o: o.price)  # Cheapest first
    sell_orders.sort(key=lambda o: o.price, reverse=True)  # Highest first

    # Calculate route via universe MCP tools
    route = await universe_route(
        origin=buy_region_info.get("system_name", "Jita"),
        destination=sell_region_info.get("system_name", "Amarr"),
        mode="safe",
    )

    # Calculate fees with pilot skills
    calculator = ArbitrageCalculator()
    if pilot_skills:
        calculator.broker_skill = pilot_skills.get("broker_relations", 0)
        calculator.accounting_skill = pilot_skills.get("accounting", 0)

    # Build execution plan
    execution_plan = build_execution_plan(
        buy_orders=buy_orders,
        sell_orders=sell_orders,
        type_info=type_info,
        route=route,
        calculator=calculator,
    )

    # Build opportunity with live data
    opportunity = build_opportunity_from_orders(
        buy_orders=buy_orders,
        sell_orders=sell_orders,
        type_info=type_info,
        buy_region_info=buy_region_info,
        sell_region_info=sell_region_info,
        route=route,
        calculator=calculator,
    )

    return ArbitrageDetailResult(
        opportunity=opportunity,
        execution_plan=execution_plan,
        buy_orders=buy_orders[:10],  # Top 10
        sell_orders=sell_orders[:10],
        broker_fee_buy=calculator.last_broker_buy,
        broker_fee_sell=calculator.last_broker_sell,
        sales_tax=calculator.last_sales_tax,
        total_fees=calculator.last_total_fees,
        route=[s.model_dump() for s in route.systems] if route else None,
        freshness="fresh",  # Live ESI data
    ).model_dump()


async def calculate_route(opp: ArbitrageOpportunity, include_lowsec: bool) -> RouteResult | None:
    """
    Calculate route between buy and sell regions using universe MCP tools.

    Note: This function is called in parallel via asyncio.gather() for multiple
    opportunities. Keep it stateless and handle exceptions gracefully.

    Timeout: Caller wraps this in asyncio.wait_for() with 3s timeout.
    If route calculation is slow (complex graph traversal), the opportunity
    will still be shown but without route info.
    """
    try:
        # Get hub systems for each region
        buy_hub = get_region_hub_system(opp.buy_region_id)
        sell_hub = get_region_hub_system(opp.sell_region_id)

        if not buy_hub or not sell_hub:
            return None

        mode = "shortest" if include_lowsec else "safe"
        return await universe_route(buy_hub, sell_hub, mode=mode)
    except Exception as e:
        logger.warning(f"Route calculation failed: {e}")
        return None
```

### 4.2 Enhanced market_spread

```python
@tool
async def market_spread(
    items: list[str],
    regions: list[str] | None = None,
    include_arbitrage: bool = True
) -> MarketSpreadResult:
    """
    Compare prices across regions for arbitrage analysis.

    Now supports any region with discovered market activity.
    Uses cached data when available for fast response.
    """
    ...
```

---

## Phase 5: Skill Integration

### 5.1 New Skill: `/arbitrage`

Create `.claude/skills/arbitrage/SKILL.md`:

```yaml
---
name: arbitrage
description: Scan for market arbitrage opportunities across EVE regions.
model: sonnet
category: financial
triggers:
  - "/arbitrage"
  - "find arbitrage"
  - "trading opportunities"
  - "price differences between regions"
  - "what can I trade for profit"
requires_pilot: true
data_sources:
  - userdata/pilots/{active_pilot}/profile.md
esi_scopes:
  - esi-skills.read_skills.v1
---

# Arbitrage Scanner

Scan for market arbitrage opportunities across EVE regions. Identifies items
where buying in one region and selling in another yields profit after fees.

## Important Disclaimers

**This is a scanner, not a trading bot.** Market conditions change rapidly.
Always verify opportunities before executing:

1. Check the **confidence level** - "low" confidence means stale or questionable data
2. Use `/arbitrage detail <item>` to see live order book before trading
3. Consider cargo size, route safety, and your available capital

## Usage

```
/arbitrage [options]
/arbitrage detail <item> <buy_region> <sell_region>
```

## Commands

### Scan for Opportunities

```
/arbitrage                           # Show top 10 opportunities
/arbitrage --min-profit 10           # Only 10%+ profit margins
/arbitrage --min-confidence high     # Only high-confidence opportunities
/arbitrage --category ships          # Filter by category
/arbitrage --include-lowsec          # Include routes through lowsec
/arbitrage --force-refresh           # Refresh data before scanning
```

### Detailed Analysis

```
/arbitrage detail "Caldari Navy Hookbill" jita amarr
```

Shows:
- Live order book (not cached)
- Fee breakdown using your pilot's skills
- Execution plan (recommended quantity, expected profit)
- Route with jump count and security assessment
- Slippage estimate for large orders

## Output Format

### Scan Results

```
═══════════════════════════════════════════════════════════════════
ARBITRAGE OPPORTUNITIES
Data refreshed 2 minutes ago | 5 regions scanned
───────────────────────────────────────────────────────────────────

| Item | Buy (Region) | Sell (Region) | Margin | Vol | Confidence |
|------|--------------|---------------|--------|-----|------------|
| Caldari Navy Hookbill | 18.2M (Jita) | 21.5M (Amarr) | 12.3% | 45 | HIGH |
| Republic Fleet EMP M | 850 (Rens) | 1,120 (Dodixie) | 8.2% | 5000 | MEDIUM |

Showing 2 of 15 opportunities (filtered: min 5% profit, highsec only)

⚠️ Verify with `/arbitrage detail <item>` before trading
═══════════════════════════════════════════════════════════════════
```

### Detail View

```
═══════════════════════════════════════════════════════════════════
ARBITRAGE DETAIL: Caldari Navy Hookbill
───────────────────────────────────────────────────────────────────

BUY IN: Jita (The Forge)
  Best price: 18,234,500 ISK (143 available)
  Next: 18,245,000 ISK (52 available)

SELL IN: Amarr (Domain)
  Best price: 21,500,000 ISK (89 demanded)
  Next: 21,450,000 ISK (120 demanded)

EXECUTION PLAN:
  Recommended quantity: 89 units
  Buy cost: 1,622,870,500 ISK
  Sell revenue: 1,913,500,000 ISK
  Broker fees: 32,457,410 ISK (your skills: Broker 4, Accounting 4)
  Sales tax: 19,135,000 ISK
  NET PROFIT: 238,037,090 ISK (14.7% ROI)

ROUTE: Jita → Amarr (10 jumps, highsec)
  Cargo: 890,000 m³ (need freighter or contracts)
  Gank risk: MODERATE (high cargo value)

RECOMMENDATION: Use courier contract with 250M collateral

⚠️ Live data as of 2026-01-18 18:45:23 UTC
═══════════════════════════════════════════════════════════════════
```

## Self-Sufficiency Awareness

For pilots with `market_trading: false` in their profile, this skill adjusts:
- Emphasizes "for your own use" framing
- Suggests NPC-seeded items when applicable
- Avoids station trading advice

## Fee Calculation

If pilot has ESI authentication, reads Broker Relations and Accounting skills
to calculate accurate fees. Otherwise uses base rates (1% broker, 2% tax).

## Data Freshness

- Trade hub data: Refreshed if older than 5 minutes
- Secondary hubs: Refreshed if older than 15 minutes
- All data age shown in results
- Use `--force-refresh` to bypass TTL

## Performance & Latency

**Important:** MCP tool calls return complete results, not streaming updates. Progress indication during refresh is not possible in the current architecture.

| Cache State | Expected Latency | User Experience |
|-------------|------------------|-----------------|
| Fresh (all regions) | ~200-500ms | Near-instant results |
| Partial refresh (1-2 regions stale) | ~5-10s | Brief pause, then results |
| Full refresh (all regions stale) | ~15-30s | Noticeable wait |
| API unavailable (cache fallback) | ~200ms | Results with warning banner |

**Skill description should set expectations:**

> **Note:** First query after 5+ minutes may take 10-30 seconds while data refreshes.
> Subsequent queries are near-instant. If you see "Data refreshed X seconds ago",
> the query used cached data.

**Why no progress indication:**
- MCP tools execute to completion before returning
- Streaming/incremental output is not supported in the tool protocol
- The skill receives complete results, not partial updates

**Mitigations implemented:**
1. Parallel region refresh (5 regions refresh simultaneously, not sequentially)
2. Route calculation timeout (3s max per route, fail gracefully)
3. ESI fallback when Fuzzwork slow (prevents indefinite hang)
4. Clear latency documentation in skill description

**Alternative considered but rejected:**
- Two-phase response (quick "scanning..." message, then full results)
- Rejected because: Adds complexity, MCP doesn't support well, user still waits

## DO NOT

- **DO NOT** suggest this is guaranteed profit
- **DO NOT** recommend margin trading or speculation
- **DO NOT** encourage market manipulation
- **DO NOT** provide advice on large-scale industrial arbitrage

---

## Persona Adaptation

This skill supports persona-specific overlays. Check for:
```
personas/{active_persona}/skill-overlays/arbitrage.md
```
```

### 5.2 Enhanced `/price`

Add arbitrage awareness to existing price skill:

```
/price Tritanium --compare-regions   # Cross-region comparison
/price "Caldari Navy Hookbill" --arbitrage  # Show arbitrage if exists
```

### 5.3 Integration with `/aria-status`

Add market data status to the existing status skill instead of a separate tool:

```
═══════════════════════════════════════════════════════════════════
ARIA STATUS REPORT
───────────────────────────────────────────────────────────────────
...existing status...

MARKET DATA:
  Trade hubs: Fresh (2 min ago)
  Secondary hubs: Recent (12 min ago)
  Items tracked: 1,247 across 5 regions
  Last discovery: 2026-01-15

═══════════════════════════════════════════════════════════════════
```

---

## Phase 6: Testing & Operations

### 6.1 Test Strategy

Follow existing test patterns in `.claude/scripts/aria_esi/mcp/market/`.

```python
# tests/test_arbitrage.py

import pytest
from aria_esi.services.market_refresh import MarketRefreshService, RefreshResult
from aria_esi.models.market import ArbitrageOpportunity, ConfidenceLevel


class TestRefreshService:
    """Test request-triggered refresh logic."""

    @pytest.mark.asyncio
    async def test_fresh_data_skips_refresh(self, mock_db):
        """Data within TTL should not trigger refresh."""
        mock_db.set_region_last_refresh("The Forge", minutes_ago=2)  # Within 5min TTL

        service = MarketRefreshService(db=mock_db)
        result = await service.ensure_fresh_data(regions=[10000002])

        assert result.from_cache is True
        assert result.regions_refreshed == 0

    @pytest.mark.asyncio
    async def test_stale_data_triggers_refresh(self, mock_db, mock_fuzzwork):
        """Data beyond TTL should trigger refresh."""
        mock_db.set_region_last_refresh("The Forge", minutes_ago=10)  # Beyond 5min TTL

        service = MarketRefreshService(db=mock_db, fuzzwork=mock_fuzzwork)
        result = await service.ensure_fresh_data(regions=[10000002])

        assert result.from_cache is False
        assert result.regions_refreshed == 1
        mock_fuzzwork.get_aggregates.assert_called()

    @pytest.mark.asyncio
    async def test_force_refresh_bypasses_ttl(self, mock_db, mock_fuzzwork):
        """force_refresh=True should refresh regardless of TTL."""
        mock_db.set_region_last_refresh("The Forge", minutes_ago=1)  # Fresh

        service = MarketRefreshService(db=mock_db, fuzzwork=mock_fuzzwork)
        result = await service.ensure_fresh_data(regions=[10000002], force_refresh=True)

        assert result.from_cache is False
        assert result.regions_refreshed == 1

    @pytest.mark.asyncio
    async def test_fuzzwork_unavailable_uses_cache(self, mock_db, mock_fuzzwork):
        """When Fuzzwork fails, should fall back to cached data with warning."""
        mock_fuzzwork.get_aggregates.side_effect = FuzzworkUnavailable("Connection timeout")
        mock_db.set_region_last_refresh("The Forge", minutes_ago=10)  # Stale
        mock_db.set_cached_prices("The Forge", age_hours=2)  # Within 24h fallback window

        service = MarketRefreshService(db=mock_db, fuzzwork=mock_fuzzwork)
        result = await service.ensure_fresh_data(regions=[10000002])

        assert result.api_unavailable is True
        assert result.fallback_used is True
        assert result.from_cache is True
        assert any("cached data" in err.lower() for err in result.errors)
        assert any("fuzzwork unavailable" in err.lower() for err in result.errors)

    @pytest.mark.asyncio
    async def test_fuzzwork_unavailable_esi_fallback_succeeds(self, mock_db, mock_fuzzwork, mock_esi):
        """When Fuzzwork fails, ESI fallback should provide fresh data."""
        mock_fuzzwork.get_aggregates.side_effect = FuzzworkUnavailable("503 Service Unavailable")
        mock_esi.get_market_orders.return_value = [
            {"price": 100.0, "volume_remain": 1000, "is_buy_order": False}
        ]
        mock_db.set_region_last_refresh("The Forge", minutes_ago=10)

        service = MarketRefreshService(
            db=mock_db, fuzzwork=mock_fuzzwork, esi_fallback=ESIAggregationFallback(mock_esi)
        )
        result = await service.ensure_fresh_data(regions=[10000002])

        # ESI fallback should succeed, so we get fresh data
        assert result.from_cache is False
        assert result.regions_refreshed == 1
        mock_esi.get_market_orders.assert_called()

    @pytest.mark.asyncio
    async def test_both_apis_unavailable_no_cache_raises(self, mock_db, mock_fuzzwork, mock_esi):
        """When all APIs fail and no cache exists, should raise clear error."""
        mock_fuzzwork.get_aggregates.side_effect = FuzzworkUnavailable("timeout")
        mock_esi.get_market_orders.side_effect = Exception("ESI unavailable")
        mock_db.set_cached_prices("The Forge", age_hours=None)  # No cached data

        service = MarketRefreshService(
            db=mock_db, fuzzwork=mock_fuzzwork, esi_fallback=ESIAggregationFallback(mock_esi)
        )

        with pytest.raises(ArbitrageDataUnavailable) as exc_info:
            await service.ensure_fresh_data(regions=[10000002])

        assert "fuzzwork unavailable" in str(exc_info.value).lower()
        assert "try again later" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_route_timeout_returns_opportunity_without_route(self, mock_db):
        """Route calculation timeout should not block opportunity display."""
        # Setup opportunity that will have slow route calculation
        mock_db.set_arbitrage_opportunity(
            type_name="Expensive Ship",
            buy_region="The Forge",
            sell_region="Domain",
            profit_pct=15.0
        )

        # Mock universe_route to be slow
        async def slow_route(*args, **kwargs):
            await asyncio.sleep(5)  # Longer than 3s timeout
            return RouteResult(...)

        with patch("universe_route", slow_route):
            result = await market_arbitrage_scan(min_profit_pct=10.0)

        # Opportunity should still appear, just without route info
        assert len(result["opportunities"]) >= 1
        opp = result["opportunities"][0]
        assert opp["route_jumps"] is None
        assert opp["route_warning"] == "Route calculation timed out"


class TestConfidenceScoring:
    """Test opportunity confidence classification."""

    def test_high_confidence_fresh_data_good_volume(self):
        """Fresh data with good volume = high confidence."""
        confidence = determine_confidence(
            data_age_seconds=120,  # 2 minutes
            volume=100,
            profit_margin=8.0,
        )
        assert confidence == "high"

    def test_low_confidence_stale_data(self):
        """Stale data (>30min) = low confidence."""
        confidence = determine_confidence(
            data_age_seconds=2400,  # 40 minutes
            volume=100,
            profit_margin=8.0,
        )
        assert confidence == "low"

    def test_low_confidence_suspicious_margin(self):
        """Very high margin (>50%) suggests bad data."""
        confidence = determine_confidence(
            data_age_seconds=120,
            volume=100,
            profit_margin=75.0,  # Suspiciously high
        )
        assert confidence == "low"

    def test_medium_confidence_moderate_volume(self):
        """Low-ish volume = medium confidence."""
        confidence = determine_confidence(
            data_age_seconds=120,
            volume=25,  # Below 50 threshold
            profit_margin=8.0,
        )
        assert confidence == "medium"


class TestFeeCalculation:
    """Test arbitrage fee calculations."""

    def test_base_fees_no_skills(self):
        """Base fees without skill bonuses."""
        calc = ArbitrageCalculator()
        result = calc.calculate_true_profit(
            buy_price=100.0,
            sell_price=120.0,
            quantity=100,
            route_jumps=5,
            cargo_m3=10.0,
        )

        # 1% broker on buy (100 ISK), 1% broker on sell (120 ISK), 2% sales tax (240 ISK)
        assert result.broker_fees == pytest.approx(220, rel=0.01)
        assert result.sales_tax == pytest.approx(240, rel=0.01)

    def test_skilled_fees_reduction(self):
        """Skills should reduce fees."""
        calc = ArbitrageCalculator()
        result = calc.calculate_true_profit(
            buy_price=100.0,
            sell_price=120.0,
            quantity=100,
            route_jumps=5,
            cargo_m3=10.0,
            broker_skill=5,  # Max
            accounting_skill=5,  # Max
        )

        # Reduced rates
        assert result.broker_fees < 220
        assert result.sales_tax < 240


class TestArbitrageDetection:
    """Test the arbitrage detection query logic."""

    @pytest.mark.asyncio
    async def test_finds_profitable_spread(self, populated_db):
        """Should find item with profitable spread between regions."""
        # Setup: Tritanium sells for 4.0 in Jita, buys for 4.5 in Amarr
        populated_db.set_price("Tritanium", "The Forge", sell_min=4.0, buy_max=3.8)
        populated_db.set_price("Tritanium", "Domain", sell_min=4.8, buy_max=4.5)

        opportunities = await populated_db.find_arbitrage(min_profit_pct=5.0)

        assert len(opportunities) >= 1
        trit_opp = next(o for o in opportunities if o.type_name == "Tritanium")
        assert trit_opp.buy_region == "The Forge"
        assert trit_opp.sell_region == "Domain"
        assert trit_opp.profit_pct > 5.0

    @pytest.mark.asyncio
    async def test_ignores_negative_spread(self, populated_db):
        """Should not return opportunities with negative profit."""
        populated_db.set_price("Pyerite", "The Forge", sell_min=10.0, buy_max=9.0)
        populated_db.set_price("Pyerite", "Domain", sell_min=9.5, buy_max=8.5)

        opportunities = await populated_db.find_arbitrage(min_profit_pct=0.0)

        pyerite_opps = [o for o in opportunities if o.type_name == "Pyerite"]
        assert len(pyerite_opps) == 0  # No profitable spread exists
```

### 6.2 Database Management

```bash
# View database stats
uv run aria-esi market-db stats

# Prune old price data (default: keep 7 days)
uv run aria-esi market-db prune --days 7

# Export opportunities to CSV (for external analysis)
uv run aria-esi market-db export opportunities.csv

# Reset database (development only)
uv run aria-esi market-db reset --confirm
```

### 6.3 Health Monitoring

Integrated into `/aria-status` rather than separate monitoring:

```python
async def get_market_status() -> MarketStatusInfo:
    """Get market data status for /aria-status integration."""
    db = get_market_database()

    tier_status = {}
    for tier in [1, 2, 3, 4]:
        regions = await db.get_regions_by_tier(tier)
        ages = [
            (datetime.utcnow() - r.last_refresh).total_seconds()
            for r in regions if r.last_refresh
        ]
        tier_status[tier] = {
            "regions": len(regions),
            "avg_age_seconds": sum(ages) / len(ages) if ages else None,
            "stale_count": sum(1 for a in ages if a > TIER_TTL[tier]),
        }

    return MarketStatusInfo(
        tier_status=tier_status,
        total_tracked_items=await db.count_tracked_items(),
        total_regions=await db.count_active_regions(),
        last_discovery=await db.get_last_discovery_time(),
        db_size_mb=get_db_size(),
    )
```

### 6.4 Optional: Scheduled Refresh via Cron

For users who want pre-warmed data, provide optional cron setup:

```bash
# Add to crontab -e (refreshes trade hubs every 5 minutes)
*/5 * * * * cd ~/EveOnline && uv run aria-esi market-refresh --tier 1 --quiet
```

This is **optional** - the system works without it via on-demand refresh.

---

## Implementation Timeline

| Phase | Scope | Dependencies | Key Deliverable |
|-------|-------|--------------|-----------------|
| **Phase 1** | Data Infrastructure | None | Schema, Fuzzwork client, Pydantic models |
| **Phase 2** | Request-Triggered Refresh | Phase 1 | Refresh service, TTL system, API fallback |
| **Phase 3** | Arbitrage Detection | Phase 1, 2 | Detection query, V1 confidence (freshness-based) |
| **Phase 4** | MCP Tools | Phase 1, 3 | `market_arbitrage_scan`, `market_arbitrage_detail` |
| **Phase 5** | Testing | Phase 4 | Test suite, fee/confidence tests prioritized |
| **Phase 6** | Skill Integration | Phase 4, 5 | `/arbitrage` skill, `/aria-status` integration |
| **Phase 0** | Market Discovery | V2 | ESI history scanner (deferred to V2) |

### Recommended Implementation Order

**V1 (Trade Hubs Only) - Recommended Order:**

```
Phase 1.1 (Schema)
    ↓
Phase 1.2 (Seed Data Generation)  ← Ship with pre-seeded trade hub data
    ↓
Phase 2 (Refresh Service)
    ↓
Phase 3 (Arbitrage Detection)     ← V1 confidence (freshness only)
    ↓
Phase 4 (MCP Tools)
    ↓
Phase 5 (Tests)                   ← Before skill, not after
    ↓
Phase 6 (Skill)
```

**Rationale for order change:**
1. **Discovery deferred** - Ship with seed data; validate core path first
2. **Tests before skill** - Catch fee/confidence bugs before user-facing code
3. **Seed data early** - Eliminates cold start problem from day one

**V1 Deliverables Checklist:**
- [ ] Schema for 5 trade hubs
- [ ] Seed data generation script
- [ ] Refresh service with Fuzzwork → ESI fallback chain
- [ ] ESI aggregation fallback (reuse cache.py pattern)
- [ ] V1 confidence scoring (freshness-based)
- [ ] Stale data handling (`allow_stale` flag or prominent banner)
- [ ] Arbitrage detection query
- [ ] `market_arbitrage_scan` tool with route timeout (3s)
- [ ] `market_arbitrage_detail` tool
- [ ] Test coverage for fees, confidence, API unavailable, route timeout
- [ ] `/arbitrage` skill with V1 output format and latency documentation

**V2 (Expand Coverage + Discovery):**
1. Phase 0: Discovery system for secondary hubs
2. Multi-factor confidence scoring
3. Execution planning tool (`market_execution_plan`)
4. Add 10 secondary hubs to tier system
5. EVE Marketer fallback for Fuzzwork

**V3 (Full Coverage):**
1. Full discovery scan capability
2. Add nullsec regions
3. Adaptive tier promotion
4. Citadel market support

---

## Risk Mitigation

| Risk | Mitigation | Status |
|------|------------|--------|
| **Cold start (no data)** | Ship with pre-seeded trade hub data | V1 |
| Fuzzwork rate limits | Token bucket rate limiter, exponential backoff | V1 |
| **Fuzzwork downtime** | ESI aggregation fallback (2.7), then 24h cache fallback | V1 ✓ |
| **Data staleness** | `allow_stale` flag required, prominent banner, detail view uses live ESI | V1 ✓ |
| False positive opportunities | Require minimum volume, verify with ESI on detail view | V1 |
| Database growth | Prune old data (7 day retention), index efficiently | V1 |
| **Variable query latency** | Parallel refresh, route timeout (3s), document expectations in skill | V1 ✓ |
| **Route calculation failure** | 3s timeout with `asyncio.wait_for()`, graceful null route_jumps | V1 ✓ |
| Fee calculation complexity | Conservative estimates, prominent disclaimers about citadels/skills | V1 |
| **User acts on stale data** | `allow_stale` flag, prominent banner, detail view required | V1 ✓ |
| Discovery takes too long | **Deferred** - V1 uses seed data, discovery in V2 | V2 |
| Tracking table bloat | Adaptive cleanup of inactive items (30 day threshold) | V2 |
| Multi-factor confidence complexity | **Deferred** - V1 uses freshness only, multi-factor in V2 | V2 |
| Execution planning complexity | **Deferred** - V1 basic info, separate tool in V2 | V2 |
| Concurrent session conflicts | Per-region async locks within process | V1 |
| SDE updates | Document update process, version check in status | V1 |
| **MCP streaming limitations** | Document latency expectations, no progress indication possible | V1 ✓ |

✓ = Enhanced in v2.2

### New Risks Addressed by Architecture Change

| Former Risk | Resolution |
|-------------|------------|
| Daemon process management | Eliminated - no daemon, request-triggered only |
| State sync between daemon and skill | Eliminated - single code path |
| Daemon crashes causing stale data | Eliminated - no persistent process to crash |
| Resource consumption when idle | Eliminated - zero overhead when not querying |

---

## Additional Considerations

### Concurrent User Sessions

**Scenario:** Two Claude Code sessions query arbitrage simultaneously, both triggering refresh.

**Risk:** Duplicate API calls, wasted rate limit budget.

**Mitigation:** Use async locks at the cache layer (existing pattern in `MarketCache`):

```python
class MarketRefreshService:
    _refresh_locks: dict[int, asyncio.Lock] = {}  # Per-region locks

    async def _refresh_region(self, region_id: int) -> int:
        # Acquire per-region lock to prevent duplicate refreshes
        if region_id not in self._refresh_locks:
            self._refresh_locks[region_id] = asyncio.Lock()

        async with self._refresh_locks[region_id]:
            # Check again after acquiring lock (another task may have refreshed)
            if not await self._is_stale(region_id):
                return 0  # Already refreshed by another task

            return await self._do_refresh(region_id)
```

**Note:** This only helps within a single process. Cross-process coordination would require file locks or a more complex solution (defer to V2 if needed).

### SDE Updates

**Scenario:** EVE patches add new items or change market groups.

**Risk:** New items won't appear in arbitrage results until SDE is updated.

**Mitigation:**
1. Document SDE update process
2. Add version check to `/aria-status`
3. Seed data regeneration includes SDE refresh

```bash
# Check SDE version
uv run aria-esi sde-status

# Update SDE (downloads latest from Fuzzwork)
uv run aria-esi sde-update

# Regenerate seed data after SDE update
uv run aria-esi market-seed generate
```

### Data Retention Policy

| Data Type | Retention | Rationale |
|-----------|-----------|-----------|
| Price snapshots (`region_prices`) | 7 days | Balance history vs DB size |
| Tracking data (`region_item_tracking`) | 30 days inactive | Cleanup stale items |
| Opportunity history | None (computed) | Regenerated on query |
| Discovery jobs | 90 days | Audit trail for debugging |

**Database size estimates:**
- V1 (5 hubs, 500 items): ~5 MB
- V2 (15 regions, 700 items): ~20 MB
- V3 (35 regions, 1000 items): ~50 MB

**Cleanup CLI:**
```bash
# Prune old price data
uv run aria-esi market-db prune --days 7

# Show database statistics
uv run aria-esi market-db stats
```

### Variable Query Latency

**Problem:** Query latency varies based on cache state:
- Cache fresh: ~100ms (database query only)
- Cache stale: 5-60 seconds (API refresh)

**User experience mitigations:**

1. **Progress indication in skill output:**
```
Scanning for arbitrage opportunities...
⟳ Refreshing The Forge (1/3)...
⟳ Refreshing Domain (2/3)...
⟳ Refreshing Metropolis (3/3)...
Found 12 opportunities.
```

2. **Document expected latency:**
```markdown
## Performance Notes

First query after >5 minutes may take 10-30 seconds as data refreshes.
Subsequent queries within TTL are near-instant.
Use `--force-refresh` only when you need the freshest data.
```

3. **Parallel region refresh** (already implemented in Phase 2):
```python
# Refresh multiple regions in parallel (limited by rate limiter)
tasks = [self._refresh_region(r) for r in stale_regions]
results = await asyncio.gather(*tasks, return_exceptions=True)
```

---

## Success Metrics

### V1 (Trade Hubs)

1. **Coverage:** 5 trade hubs with ~500 tracked items each
2. **Cold Start:** First query works without manual setup (seed data)
3. **Freshness:** Data refreshed within 5 minutes when queried
4. **Latency:**
   - Cache hit: < 500ms
   - Cache miss (refresh): < 30s for all 5 hubs
5. **API Resilience:** Graceful degradation when Fuzzwork unavailable
6. **Test Coverage:** 80%+ for fee calculation and confidence scoring
7. **User Experience:** Clear freshness indicators, no silent stale data

### V2+ (Expanded)

1. **Coverage:** 15+ regions with dynamic item discovery
2. **Freshness:** Trade hubs < 10 min, secondary < 20 min when queried
3. **Accuracy:** < 5% false positive rate for "high" confidence (multi-factor)
4. **Efficiency:** < 25% of Fuzzwork rate limit budget per query session
5. **Execution Planning:** Slippage estimates within 5% of actual

---

## Open Questions (Resolved)

| Question | Decision | Rationale |
|----------|----------|-----------|
| Third-party backup (EVE Marketer)? | **Yes, V2** | Add as Fuzzwork fallback. Same API pattern, low effort. |
| Historical analysis for trends? | **Defer** | Adds complexity. Existing `market_history` tool covers basic needs. |
| Push notifications? | **Defer** | High-value opportunities are fleeting. By notification time, they're gone. On-demand refresh is more practical. |
| Multi-pilot fee calculation? | **Yes, V1** | Read Broker Relations + Accounting from ESI skills endpoint. Already planned in `market_arbitrage_detail`. |
| Route integration? | **Yes, V1** | Essential for execution planning. Use existing `universe_route` MCP tool. Implemented in Phase 4. |
| Citadel markets? | **Defer to V3** | Requires structure IDs and additional complexity. NPC stations cover 90%+ of trade volume. |

## Future Considerations

1. **Slippage Modeling:** For large orders, estimate price impact based on order book depth. Show "effective price" for quantities beyond best order.

2. **Cargo Optimization:** Given a budget and cargo capacity, recommend the optimal mix of items to haul.

3. **Regional Market Health:** Track which regions are "dying" (declining volume) vs "growing" for strategic positioning.

4. **Courier Contract Integration:** Auto-generate courier contract parameters (collateral, reward) based on cargo value and route risk.

5. **Competition Detection:** Warn if an item is being actively traded by others (high order churn).

---

## Revision History

### v2.2 (2026-01-18)

Incorporated Claude Code/LLM integration engineering review. Focus on resilience, UX, and test coverage.

| Area | v2.1 | v2.2 |
|------|------|------|
| **Fuzzwork Fallback** | 24h cache fallback only | ESI aggregation fallback in V1 (uses existing code from cache.py) |
| **Route Timeout** | No timeout | 3s timeout per route with graceful degradation |
| **Stale Data UX** | Inline ⚠️ warning | Prominent banner + `allow_stale` flag required |
| **Test Coverage** | Basic refresh tests | Added API unavailable, ESI fallback, route timeout tests |
| **Latency Docs** | Mentioned in Additional Considerations | Dedicated section with latency table, MCP limitations explained |

**New Sections Added:**
- 2.7 ESI Aggregation Fallback (V1)
- Strengthened Stale Data Handling (in 3.3)
- Performance & Latency (in skill section)
- 5 new test cases in TestRefreshService

**Key Changes:**
1. **ESI fallback for Fuzzwork (V1):** When Fuzzwork is down, aggregate from ESI directly. Slower (50 items vs Fuzzwork's 100/request) but prevents total outage. Code pattern already exists in `cache.py:376-506`.

2. **Route calculation timeout:** `asyncio.wait_for()` wrapper with 3s timeout. Slow routes don't block scan; opportunity shown without route info.

3. **Stale data handling:** Option A (recommended): Require `--allow-stale` flag to see opportunities based on >30min data. Option B: Prominent warning banner before results table.

4. **MCP latency documentation:** Explicit note that streaming/progress indication is not possible. Set user expectations in skill description.

**Rationale:** The primary risk in V1 is external API failure causing degraded or failed queries. ESI fallback and timeout handling significantly improve resilience with minimal complexity since the underlying code already exists.

### v2.1 (2026-01-18)

Incorporated engineering review recommendations. Key changes:

| Area | v2.0 | v2.1 |
|------|------|------|
| **Cold Start** | Not addressed | Ship with pre-seeded trade hub data |
| **Confidence Model** | Multi-factor (high/medium/low) | V1: Freshness-only (fresh/recent/stale), V2: Multi-factor |
| **Execution Planning** | Full complexity in V1 | V1: Basic info only, V2: Separate tool |
| **API Downtime** | Implicit cache fallback | Explicit error handling with 24h fallback |
| **Route Calculation** | Sequential | Parallel with asyncio.gather() |
| **Phase Order** | Discovery first | Discovery deferred to V2, seed data for V1 |
| **Risk Table** | Mitigations only | Added V1/V2 status column |

**New Sections Added:**
- V1 Cold Start: Pre-Seeded Data
- API Downtime Handling (2.6)
- Additional Considerations (concurrent sessions, SDE updates, data retention, latency)

**Rationale:** V1 should validate core workflow with minimal complexity. Defer advanced features (discovery, multi-factor confidence, execution planning) to V2 after user feedback.

### v2.0 (2026-01-18)

Major revision based on architecture review. Key changes:

| Area | Original | Revised |
|------|----------|---------|
| **Architecture** | Background APScheduler daemon | Request-triggered refresh with TTL |
| **Scope** | All 80+ regions from start | Phased: V1=5 hubs, V2=+10, V3=+20 |
| **Confidence** | Basic scoring only | Explicit confidence levels (high/medium/low) surfaced to users |
| **Execution** | Profit calculation only | Full execution planning with slippage, ship recommendations, risk assessment |
| **Route Integration** | Mentioned but not implemented | Integrated with existing `universe_route` MCP tools |
| **Fee Calculation** | Base rates only | Skill-aware calculation with citadel fee warnings |
| **Models** | Undefined | Complete Pydantic model definitions |
| **Skill Schema** | Incomplete | Full schema following `.claude/skills/SCHEMA.md` |
| **Testing** | Not addressed | Test strategy with example test cases |
| **Deployment** | systemd/launchd daemon | Optional cron, no mandatory daemon |

**Rationale:** The daemon approach conflicted with Claude Code's request-response architecture. On-demand refresh fits the tool's usage patterns better and eliminates process management complexity.
