# Killmail Store Redesign Proposal

## Status

| Field | Value |
|-------|-------|
| Status | Implementation Complete |
| Author | ARIA / Capsuleer |
| Created | 2026-01-26 |
| Updated | 2026-01-26 |
| Reviewed | 2026-01-26 (rev2: ESI attempts tracking, MCP resolution) |
| Supersedes | Portions of REDISQ_REALTIME_INTEL_PROPOSAL.md |

---

## Implementation Notes

### Completed Phases
- **Phase 1: Storage Foundation** ✅ - SQLiteKillmailStore with migrations, WAL mode, expunge
- **Phase 2: Ingest Refactor** ✅ - BoundedKillQueue with backpressure, poller integration
- **Phase 3: Worker Refactor** ✅ - NotificationWorker with system filtering, rate limit handling, rollups
- **Phase 4: MCP Exposure** ✅ - Status dispatcher includes ingest/worker metrics

### Known Limitations
- Rollup formatting is minimal (per "ship and iterate" guidance)

### Resolved Limitations
- ~~ESI fetch within worker loop deferred~~ → Implemented with claim coordination (2026-01-26)
- ~~MCP `killmails` dispatcher pending~~ → Implemented with query/stats/recent actions (2026-01-26)

---

## Executive Summary

The current killmail alert infrastructure uses a two-stage filter architecture that creates confusion and limits functionality. Kills are filtered at ingestion (topology pre-filter) and again at notification (profile filter), with different configurations controlling each stage. This design makes it difficult to reason about what data is available and prevents historical queries.

This proposal introduces an **Ingest-Store-Worker** architecture:

1. **Ingest Layer**: Receive ALL kills from zKillboard RedisQ without pre-filtering
2. **Storage Layer**: Persist kills to a local SQLite database with auto-expunge
3. **Worker Layer**: Independent notification workers poll the database and deliver alerts

**Key Benefits:**

| Aspect | Current | Proposed |
|--------|---------|----------|
| Data availability | Filtered at ingestion | All kills stored |
| Historical queries | Not possible | 7-day rolling window |
| MCP exposure | None | Full query capability |
| Configuration | Two filter stages | Single worker config |
| Extensibility | Tightly coupled | Add workers without touching ingest |

---

## Problem Statement

### Current Architecture

```
RedisQ → Topology Filter → ESI Fetch → Notification Filter → Discord
              ↓                              ↓
        (kills discarded)            (kills not alerted)
```

### Issues

**1. Two-Stage Filter Confusion**

The current system has two separate filter configurations:

| Stage | Config Location | Purpose |
|-------|-----------------|---------|
| Topology pre-filter | `config.json → context_topology` | Decide which kills to fetch from ESI |
| Notification filter | `userdata/notifications/*.yaml` | Decide which fetched kills trigger Discord |

When these filter different systems (e.g., home systems vs trade hubs), no alerts fire because the stages don't overlap. Users must understand both configurations to debug why alerts aren't working.

**2. Lost Data**

Kills filtered at Stage 1 are discarded permanently. There's no way to:
- Query historical kills in a region
- Retroactively analyze activity patterns
- Answer questions like "show me all kills in Jita yesterday"

**3. No MCP Exposure**

Claude Code skills cannot query killmail data directly. Every tactical question requires external API calls or pre-aggregated data.

**4. ESI Quota Coupling**

The decision to fetch ESI details is coupled to topology configuration, not actual need. A user monitoring trade hubs for Discord alerts but wanting full galaxy data for analysis cannot achieve both.

---

## Proposed Solution

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         INGEST LAYER                                │
│                                                                     │
│  zKillboard RedisQ ─────────────────────────────────────────────┐   │
│       │                                                         │   │
│       ▼                                                         │   │
│  ┌─────────────────────────────────────────────────────────┐    │   │
│  │  Ingest Service                                         │    │   │
│  │  • Receives ALL kills (~30k/day)                        │    │   │
│  │  • Extracts metadata from RedisQ package                │    │   │
│  │  • Writes to killmail store immediately                 │    │   │
│  │  • NO filtering at this stage                           │    │   │
│  └─────────────────────────────────────────────────────────┘    │   │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         STORAGE LAYER                               │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────┐        │
│  │  Killmail Store (SQLite)                                │        │
│  │                                                         │        │
│  │  Tables:                                                │        │
│  │  • killmails: RedisQ metadata (kill_id, system, time)   │        │
│  │  • esi_details: Full ESI data (lazy-populated)          │        │
│  │                                                         │        │
│  │  Features:                                              │        │
│  │  • Indexed by system_id, kill_time, corp_id, alliance   │        │
│  │  • Auto-expunge after retention period (default 7 days) │        │
│  │  • Storage engine interface for future migration        │        │
│  └─────────────────────────────────────────────────────────┘        │
│                          │                                          │
│                          ▼                                          │
│  ┌─────────────────────────────────────────────────────────┐        │
│  │  MCP Interface                                          │        │
│  │                                                         │        │
│  │  Tools:                                                 │        │
│  │  • killmails(action="query", system="Jita", hours=1)    │        │
│  │  • killmails(action="stats", systems=[...])             │        │
│  │                                                         │        │
│  │  Resources:                                             │        │
│  │  • killmail://{kill_id}                                 │        │
│  └─────────────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
┌───────────────────────────────┐ ┌─────────────────────────────────┐
│  WORKER: trade-hub-intel      │ │  WORKER: home-ops               │
│                               │ │                                 │
│  Config:                      │ │  Config:                        │
│    userdata/notifications/    │ │    userdata/notifications/      │
│    trade-hub-intel.yaml       │ │    home-ops.yaml                │
│                               │ │                                 │
│  Poll interval: 60s           │ │  Poll interval: 30s             │
│  Systems: Jita, Amarr, etc.   │ │  Systems: Simela, Sortet, etc.  │
│  Triggers: value > 500M       │ │  Triggers: any kill             │
│  Action: Discord webhook      │ │  Action: Discord webhook        │
│                               │ │                                 │
│  Queries DB for new kills     │ │  Queries DB for new kills       │
│  Fetches ESI if needed        │ │  Fetches ESI if needed          │
│  Formats and sends alert      │ │  Formats and sends alert        │
└───────────────────────────────┘ └─────────────────────────────────┘
```

---

## Design Decisions

### D1: Storage Engine (SQLite with Abstraction)

**Decision:** Use SQLite with a pluggable storage engine interface.

**Rationale:**
- SQLite is simple, file-based, and requires no external services
- 210k records (7 days × 30k/day) is well within SQLite's capabilities
- Storage engine interface allows future migration to Redis, PostgreSQL, etc.

**Concurrency Configuration:**

SQLite supports concurrent reads and writes with WAL (Write-Ahead Logging) mode. The implementation must:

```python
# Connection setup
connection.execute("PRAGMA journal_mode=WAL")
connection.execute("PRAGMA busy_timeout=5000")  # 5 second retry on lock
connection.execute("PRAGMA synchronous=NORMAL")  # Balance durability vs speed
```

**Transaction Boundaries:**

Batch inserts from the ingest queue use a single transaction for atomicity. If any insert fails, the entire batch rolls back and can be retried.

```python
async def write_batch(self, kills: list[KillmailRecord]) -> int:
    """Write batch in single transaction. Returns count written."""
    async with self.db.execute("BEGIN IMMEDIATE"):
        for kill in kills:
            await self._insert_kill(kill)
        await self.db.commit()
    return len(kills)
```

| Component | Connections | Access Pattern |
|-----------|-------------|----------------|
| Ingest writer | 1 | Batch inserts every 1s |
| Worker pool | 1 per worker | Queries + processed_kills writes |
| Expunge task | 1 | Periodic deletes |
| MCP queries | Pool of 3 | Read-only queries |

**Connection Pool:** Use a shared `aiosqlite` connection pool with max 10 connections. Workers share the pool rather than holding dedicated connections.

**Index Maintenance:**

High write volume combined with auto-expunge creates index fragmentation over time. The expunge task runs periodic optimization:

```python
async def optimize_database(self) -> None:
    """Run SQLite optimization. Call after expunge operations."""
    await self.db.execute("PRAGMA optimize")  # Analyzes and optimizes indices
```

`PRAGMA optimize` is lightweight and safe to run frequently (it only acts when beneficial). Run after each expunge cycle. Full `VACUUM` is not needed for this workload—WAL mode handles space reclamation automatically.

**Interface:**

See [`killmail_store_protocol.py`](killmail_store_protocol.py) for the complete `KillmailStore` protocol interface, including:
- Data classes (`KillmailRecord`, `ESIKillmail`, `WorkerState`, `ESIClaim`, `StoreStats`)
- Core killmail operations (insert, query, ESI details)
- Worker state management
- Duplicate detection and delivery tracking
- ESI fetch coordination
- Maintenance operations (expunge, optimize)

**Implementation:**

The `SQLiteKillmailStore` class implements this protocol using WAL mode for concurrent access. Connection configuration is documented in the protocol file.

### D2: Worker Polling Intervals (Per-Worker Config)

**Decision:** Each worker defines its own polling interval.

**Rationale:**
- Home systems may warrant more aggressive monitoring (30s)
- Distant trade hubs can poll less frequently (60s)
- Reduces unnecessary database queries for low-priority profiles

**Profile Schema Addition:**

```yaml
schema_version: 2  # Bump version

name: "home-ops"
poll_interval_seconds: 30  # NEW FIELD

# ... rest of profile
```

### D3: ESI Data Persistence (Shared Cache with Coordination)

**Decision:** ESI details are fetched on-demand by workers and persisted to a shared `esi_details` table.

**Flow:**

```
Worker needs full killmail data
        │
        ▼
┌─────────────────────────────┐
│ Check esi_details table     │
│ SELECT * FROM esi_details   │
│ WHERE kill_id = ?           │
└─────────────────────────────┘
        │
        ├─── Found ──────────▶ Use cached data
        │
        └─── Not found
                │
                ▼
┌─────────────────────────────┐
│ Acquire lock for kill_id    │
│ (prevents duplicate fetches)│
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│ Fetch from ESI              │
│ GET /killmails/{id}/{hash}/ │
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│ INSERT INTO esi_details     │
│ (or skip if another worker  │
│  inserted while we fetched) │
└─────────────────────────────┘
```

**Coordination Strategy: Claim Table (Option D)**

With 30k kills/day and multiple workers potentially polling overlapping systems, duplicate ESI fetches are a real concern. ESI enforces error rate limits (5% over 1 minute window), making wasted API calls risky. We commit to Option D (claim table) upfront—the complexity is low and the protection is worth it.

**Expected Contention Rate:**

The claim table adds ~1ms overhead per ESI fetch (one INSERT, one DELETE). In practice, contention is rare:

| Scenario | Workers | Overlap | Expected Contention |
|----------|---------|---------|---------------------|
| Solo user | 2-3 | Low (home vs trade hub) | < 1% of fetches |
| Active user | 5-10 | Moderate | 2-5% of fetches |
| Pathological | 10+ watching same system | High | 10-20% of fetches |

Even in high-contention scenarios, the losing worker simply waits for the winner to populate `esi_details`—no wasted ESI calls. The coordination overhead is justified by ESI rate limit protection.

**Mechanism:**

```sql
-- Worker attempts to claim a kill for ESI fetch
INSERT OR IGNORE INTO esi_fetch_claims (kill_id, claimed_by, claimed_at)
VALUES (?, ?, ?);

-- Check if we won the claim
SELECT claimed_by FROM esi_fetch_claims WHERE kill_id = ?;
-- If claimed_by matches our worker_name, proceed with fetch
-- Otherwise, wait for the other worker to populate esi_details
```

**Claim Lifecycle:**

1. Worker needs ESI data for kill_id
2. Check `esi_details` table first (maybe another worker already fetched)
3. If not found, attempt to insert claim
4. If claim won → fetch from ESI → insert to `esi_details` → delete claim
5. If claim lost → poll `esi_details` with exponential backoff until data appears

**Stale Claim Handling:**

Claims older than 60 seconds are considered abandoned (worker crashed mid-fetch). The expunge task cleans these up, allowing retry by another worker.

**Claim Wait Strategy:**

When a worker loses the claim race, it must wait for the winning worker to populate `esi_details`. This waiting has failure modes:

| Scenario | Detection | Resolution |
|----------|-----------|------------|
| Winner succeeds | `esi_details` populated | Use cached data |
| Winner slow | Claim exists, no `esi_details` after timeout | Continue waiting up to 60s |
| Winner crashed | Claim stale (>60s), no `esi_details` | Delete stale claim, retry claim |

**Implementation:**

```python
async def get_or_fetch_esi(self, kill_id: int, zkb_hash: str) -> ESIKillmail | None:
    """Get ESI details, coordinating with other workers."""
    # Fast path: already cached
    if details := await self.store.get_esi_details(kill_id):
        return details

    # Try to claim this fetch
    claimed = await self.store.try_claim_esi_fetch(kill_id, self.worker_name)

    if claimed:
        # We won - fetch and store
        try:
            details = await self.esi_client.get_killmail(kill_id, zkb_hash)
            await self.store.insert_esi_details(kill_id, details)
            return details
        finally:
            await self.store.delete_esi_claim(kill_id)
    else:
        # Another worker is fetching - wait with timeout
        return await self._wait_for_esi_details(kill_id, timeout=60.0)

async def _wait_for_esi_details(self, kill_id: int, timeout: float) -> ESIKillmail | None:
    """Wait for another worker to populate ESI details."""
    deadline = time.time() + timeout
    backoff = 0.5

    while time.time() < deadline:
        # Check if data appeared
        if details := await self.store.get_esi_details(kill_id):
            return details

        # Check if claim is stale (holder crashed)
        claim = await self.store.get_esi_claim(kill_id)
        if claim and claim.is_stale(threshold_seconds=60):
            # Claim abandoned - delete and retry
            await self.store.delete_esi_claim(kill_id)
            return await self.get_or_fetch_esi(kill_id)  # Recursive retry

        await asyncio.sleep(backoff)
        backoff = min(backoff * 1.5, 5.0)

    # Timeout - proceed without ESI details (use zkb data)
    logger.warning("Timeout waiting for ESI details for kill %d", kill_id)
    return None
```

**Persistent ESI Failure Handling:**

ESI may return persistent errors (404 for deleted characters, 403 for auth issues). To prevent infinite retry loops, track fetch attempts in a dedicated table and store a sentinel after max attempts.

**ESI Fetch Attempts Table:**

Attempts must be tracked *before* the first successful fetch, so `esi_details.fetch_attempts` is insufficient. A separate `esi_fetch_attempts` table provides this:

```sql
CREATE TABLE IF NOT EXISTS esi_fetch_attempts (
    kill_id INTEGER PRIMARY KEY,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_attempt_at INTEGER NOT NULL,
    last_error TEXT  -- Optional: store error message for debugging
);
```

**Lifecycle:**
1. First fetch attempt → INSERT with `attempts=1`
2. Subsequent failures → UPDATE `attempts += 1`
3. Success → DELETE row (data now in `esi_details`)
4. Max attempts reached → INSERT sentinel to `esi_details`, DELETE from `esi_fetch_attempts`

This keeps `esi_fetch_attempts` small (only in-flight or failed fetches) while providing accurate tracking across worker restarts.

```python
MAX_ESI_FETCH_ATTEMPTS = 3

async def get_or_fetch_esi(self, kill_id: int, zkb_hash: str) -> ESIKillmail | None:
    """Get ESI details with persistent failure handling."""
    # Check for cached data or sentinel
    cached = await self.store.get_esi_details(kill_id)
    if cached is not None:
        if cached.is_unfetchable:
            return None  # Previously marked as unfetchable
        return cached

    # Check attempt count (from esi_fetch_attempts table)
    attempts = await self.store.get_esi_fetch_attempts(kill_id)
    if attempts >= MAX_ESI_FETCH_ATTEMPTS:
        # Mark as permanently unfetchable
        await self.store.insert_esi_unfetchable(kill_id)
        await self.store.delete_esi_fetch_attempts(kill_id)  # Cleanup
        logger.warning("Kill %d marked unfetchable after %d attempts", kill_id, attempts)
        return None

    # Attempt fetch (with claim coordination as before)
    try:
        details = await self._fetch_with_claim(kill_id, zkb_hash)
        await self.store.delete_esi_fetch_attempts(kill_id)  # Cleanup on success
        return details
    except ESIError as e:
        await self.store.increment_esi_fetch_attempts(kill_id, error=str(e))
        if e.is_permanent:  # 404, 403, etc.
            logger.warning("Permanent ESI error for kill %d: %s", kill_id, e)
        raise
```

**ESI Details Sentinel:**

The `esi_details` table stores a sentinel row for unfetchable kills:

```sql
-- Sentinel: fetched_at = 0, all other fields NULL
INSERT INTO esi_details (kill_id, fetched_at, fetch_status)
VALUES (?, 0, 'unfetchable');
```

Workers check `fetch_status` before attempting ESI fetch. The `unfetchable` status prevents retry storms for permanently failed kills.

### D4: Discord Rate Limit Handling (Rollup Strategy)

**Decision:** Workers that encounter Discord rate limits exit gracefully; pending kills are rolled up on next poll.

**Flow:**

```
Worker polls DB: finds 5 new kills
        │
        ▼
Format and send kill #1 ───▶ Success
        │
        ▼
Format and send kill #2 ───▶ 429 Rate Limited
        │
        ▼
┌─────────────────────────────────────────────┐
│ Log: "Discord rate limited. 3 kills pending.│
│       Will retry/rollup on next poll."      │
│                                             │
│ Record high-water mark (last successful)    │
│ Exit worker iteration                       │
└─────────────────────────────────────────────┘
        │
        ▼
[Next poll interval]
        │
        ▼
Worker polls DB: finds 3 pending + 2 new = 5 kills
        │
        ▼
┌─────────────────────────────────────────────┐
│ If pending > rollup_threshold (e.g., 5):    │
│   Format as single rollup message           │
│   "5 kills in Jita (3 pending + 2 new)"     │
│ Else:                                       │
│   Send individually                         │
└─────────────────────────────────────────────┘
```

**Profile Schema Addition:**

```yaml
rate_limit_strategy:
  rollup_threshold: 5        # Roll up if more than N pending
  max_rollup_kills: 20       # Cap rollup size

delivery:
  max_attempts: 3            # Max delivery attempts per kill
  retry_delay_seconds: 30    # Delay between retries
```

**Delivery Failure Handling:**

Notification delivery may fail for reasons beyond rate limits (network errors, invalid webhook URL, Discord outage). To prevent infinite retries:

1. Track delivery attempts per kill in `processed_kills` table
2. After `max_attempts` failures, mark kill as "delivery_failed" and skip
3. Log failed deliveries for operator review

```python
async def _deliver_notification(self, profile: NotificationProfile, kill: KillmailRecord) -> bool:
    """Attempt delivery with retry tracking."""
    attempts = await self.store.get_delivery_attempts(profile.name, kill.kill_id)

    if attempts >= profile.delivery.max_attempts:
        logger.error(
            "Kill %d exceeded max delivery attempts (%d) for %s - skipping",
            kill.kill_id, attempts, profile.name
        )
        await self.store.mark_kill_processed(profile.name, kill.kill_id, status="failed")
        return False

    try:
        await self._send_discord_webhook(profile, kill)
        await self.store.mark_kill_processed(profile.name, kill.kill_id, status="delivered")
        return True
    except DiscordError as e:
        await self.store.increment_delivery_attempts(profile.name, kill.kill_id)
        if e.is_rate_limit:
            raise  # Let rate limit handler deal with it
        logger.warning("Delivery failed for kill %d: %s (attempt %d)", kill.kill_id, e, attempts + 1)
        return False
```

**Rollup Message Format (Decided):**

```
📊 Jita Activity (5 kills rolled up)
💀 2.3B ISK total | Top: Orca (1.2B)
🔗 https://zkillboard.com/related/30000142/202601261400/
```

Format rationale:
1. **Ship and iterate** - Working system with imperfect format beats delayed system with perfect format
2. **Fallback scenario** - Rollup only triggers during rate limits, not the primary experience
3. **Evolvable** - Format can change in schema v2.1 if real usage reveals issues
4. **Configurable templates** can be retrofitted later without architectural changes if divergent preferences emerge

### D5: Ingest Backpressure (Bounded Queue with Drop-Oldest)

**Decision:** Use a bounded in-memory queue between RedisQ reader and SQLite writer with drop-oldest semantics.

**Problem:**

RedisQ delivers kills at variable rates. Average is ~0.35 kills/second (30k/day), but large fleet battles can produce 1000+ kills in minutes. If SQLite writes can't keep pace (disk I/O, lock contention), unbounded queuing leads to memory exhaustion.

**Mechanism:**

```
RedisQ Reader ──▶ Bounded Queue (1000) ──▶ SQLite Writer
                        │
                        ├── Queue full? Drop oldest, log warning
                        └── Track: drops_total, queue_depth, write_latency
```

**Implementation:**

```python
import asyncio
from collections import deque
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class IngestMetrics:
    """Backpressure metrics for observability."""
    received_total: int = 0
    written_total: int = 0
    dropped_total: int = 0
    queue_depth: int = 0
    last_drop_time: float | None = None

class BoundedKillQueue:
    """Bounded queue with drop-oldest backpressure."""

    def __init__(self, maxsize: int = 1000):
        self._queue: deque[KillmailRecord] = deque(maxlen=maxsize)
        self._maxsize = maxsize
        self.metrics = IngestMetrics()
        self._lock = asyncio.Lock()

    async def put(self, kill: KillmailRecord) -> bool:
        """
        Add kill to queue. Returns True if accepted, False if dropped.

        When queue is full, oldest kill is dropped (deque maxlen behavior).
        """
        async with self._lock:
            self.metrics.received_total += 1
            was_full = len(self._queue) >= self._maxsize

            if was_full:
                # deque will auto-drop oldest when we append
                dropped = self._queue[0]
                self.metrics.dropped_total += 1
                self.metrics.last_drop_time = time.time()
                logger.warning(
                    "Backpressure: dropped kill %d (age: %.1fs) - queue full",
                    dropped.kill_id,
                    time.time() - dropped.ingested_at
                )

            self._queue.append(kill)
            self.metrics.queue_depth = len(self._queue)
            return not was_full

    async def get_batch(self, max_batch: int = 100) -> list[KillmailRecord]:
        """Get up to max_batch kills for writing."""
        async with self._lock:
            batch = []
            for _ in range(min(max_batch, len(self._queue))):
                batch.append(self._queue.popleft())
            self.metrics.queue_depth = len(self._queue)
            return batch
```

**Configuration:**

```python
# In config or constants
INGEST_QUEUE_SIZE = 1000      # ~15 minutes of average load
INGEST_BATCH_SIZE = 100       # Writes per transaction
INGEST_FLUSH_INTERVAL = 1.0   # Seconds between batch writes
```

**Queue Sizing Rationale:**

| Scenario | Kills/min | Queue Drain Time |
|----------|-----------|------------------|
| Normal load | ~21 | 48 minutes buffer |
| Major battle | ~500 | 2 minutes buffer |
| Extreme burst | ~1000 | 1 minute buffer |

A 1000-kill queue provides adequate buffer for typical bursts while bounding memory to ~200KB (1000 × 200 bytes per record).

**Observability:**

The `IngestMetrics` dataclass exposes:
- `received_total`: Kills received from RedisQ
- `written_total`: Kills persisted to SQLite
- `dropped_total`: Kills dropped due to backpressure
- `queue_depth`: Current queue size (for dashboards)
- `last_drop_time`: Timestamp of most recent drop (for alerting)

**Alert Thresholds:**

| Metric | Warning | Critical |
|--------|---------|----------|
| `dropped_total` increase | > 0 in 5 min | > 100 in 5 min |
| `queue_depth` | > 500 sustained | > 900 sustained |
| `write_latency_p99` | > 100ms | > 500ms |

**Structured Logging:**

Backpressure events are logged with structured data for log aggregation:

```python
# On drop
logger.warning(
    "Backpressure drop",
    extra={
        "event": "backpressure_drop",
        "kill_id": dropped.kill_id,
        "kill_age_seconds": time.time() - dropped.ingested_at,
        "queue_depth": self.metrics.queue_depth,
        "drops_total": self.metrics.dropped_total,
    }
)

# Periodic health (every 60s)
logger.info(
    "Ingest queue health",
    extra={
        "event": "ingest_health",
        "queue_depth": self.metrics.queue_depth,
        "received_total": self.metrics.received_total,
        "written_total": self.metrics.written_total,
        "dropped_total": self.metrics.dropped_total,
    }
)
```

Log output (JSON format for aggregation):
```json
{"level": "WARNING", "event": "backpressure_drop", "kill_id": 123456789, "kill_age_seconds": 45.2, "queue_depth": 1000, "drops_total": 1}
```

### D6: Data Authority (ESI Authoritative)

**Decision:** When data exists in both `killmails` (from zkb) and `esi_details` (from ESI), ESI is authoritative.

**Rationale:**

zKillboard's RedisQ package includes denormalized victim data extracted from ESI, but this data passes through zkb's processing pipeline and may occasionally differ from direct ESI responses due to:
- Timing differences in zkb's own ESI fetches
- zkb data transformation bugs
- Stale zkb cache during ESI outages

ESI is the canonical source for killmail data in EVE Online. When displaying killmail details, prefer `esi_details` fields over `killmails` fields.

**Implementation:**

```python
def get_victim_corporation_id(kill: KillmailRecord, esi: ESIDetails | None) -> int:
    """Return victim corp ID, preferring ESI data when available."""
    if esi and esi.victim_corporation_id:
        return esi.victim_corporation_id
    return kill.victim_corporation_id
```

**Display Priority:**

| Field | Primary Source | Fallback |
|-------|---------------|----------|
| victim_ship_type_id | esi_details | killmails |
| victim_corporation_id | esi_details | killmails |
| victim_alliance_id | esi_details | killmails |
| victim_character_id | esi_details | (none - zkb doesn't provide) |
| attackers | esi_details | (none) |
| items dropped/destroyed | esi_details | (none) |

**When zkb-only data is acceptable:**

- Filtering/routing decisions (which worker processes the kill)
- Quick activity counts (kills per hour in system)
- Any context where ESI fetch latency is unacceptable

**When ESI data is required:**

- Discord notification formatting (user-facing)
- MCP resource responses (`killmail://{id}`)
- Any detailed killmail display

### D7: Worker Lifecycle (Single-Process Asyncio Supervisor)

**Decision:** All notification workers run as async tasks within one process, managed by a supervisor coroutine.

**Rationale:**
- Fits existing asyncio architecture (RedisQ poller is already async)
- Low overhead for personal/small-group scale
- Simple implementation with no external dependencies
- Worker state already persisted to `worker_state` table enables recovery

**Supervisor Pattern:**

```python
class WorkerSupervisor:
    """Manages notification worker lifecycle."""

    def __init__(self, profiles: list[NotificationProfile], store: KillmailStore):
        self.profiles = profiles
        self.store = store
        self.tasks: dict[str, asyncio.Task] = {}
        self.running = True

    async def run(self):
        """Main supervisor loop - monitors and restarts workers."""
        while self.running:
            for profile in self.profiles:
                if profile.name not in self.tasks or self.tasks[profile.name].done():
                    # Worker missing or exited - (re)start it
                    self.tasks[profile.name] = asyncio.create_task(
                        self._run_worker_with_backoff(profile),
                        name=f"worker:{profile.name}"
                    )
            await asyncio.sleep(5)  # Health check interval

    async def _run_worker_with_backoff(self, profile: NotificationProfile):
        """Run worker with exponential backoff on failure."""
        backoff = 1.0
        max_backoff = 60.0

        while self.running:
            try:
                await self._worker_poll_loop(profile)
                backoff = 1.0  # Reset on successful poll cycle
            except Exception as e:
                logger.error("Worker %s failed: %s", profile.name, e)
                await self._record_failure(profile.name)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)

    async def shutdown(self):
        """Graceful shutdown - cancel all workers and wait."""
        self.running = False
        for task in self.tasks.values():
            task.cancel()
        await asyncio.gather(*self.tasks.values(), return_exceptions=True)

    async def _worker_poll_loop(self, profile: NotificationProfile):
        """Single poll iteration with time-based queries and duplicate detection."""
        worker_name = profile.name
        overlap_window = profile.polling.overlap_window_seconds

        # Get last processed time from state table
        state = await self.store.get_worker_state(worker_name)
        query_since = state.last_processed_time - overlap_window

        # Query kills with overlap to catch out-of-order arrivals
        kills = await self.store.query_kills(
            systems=profile.topology.system_ids,
            since=datetime.fromtimestamp(query_since),
            limit=profile.polling.batch_size,
        )

        max_kill_time = state.last_processed_time
        for kill in kills:
            # Duplicate detection: skip if already processed
            if await self.store.is_kill_processed(worker_name, kill.kill_id):
                continue

            # Process and notify
            await self._process_kill(profile, kill)

            # Record as processed (prevents future duplicates)
            await self.store.mark_kill_processed(worker_name, kill.kill_id)

            # Track highest kill_time seen
            if kill.kill_time > max_kill_time:
                max_kill_time = kill.kill_time

        # Advance high-water mark
        await self.store.update_worker_state(
            worker_name,
            last_processed_time=max_kill_time,
            last_poll_at=int(time.time()),
        )

        await asyncio.sleep(profile.polling.interval_seconds)
```

**Restart Policy:**

| Condition | Action |
|-----------|--------|
| Worker task completes normally | Restart immediately (poll loop exited unexpectedly) |
| Worker raises exception | Log error, increment `consecutive_failures`, restart with backoff |
| Backoff sequence | 1s → 2s → 4s → 8s → ... → 60s (max) |
| Backoff reset | After successful poll cycle |

**Health Checks:**

| Check | Frequency | Action on Failure |
|-------|-----------|-------------------|
| Task alive | 5 seconds | Restart task |
| `consecutive_failures` > 10 | Per failure | Log warning, continue backoff |
| `consecutive_failures` > 50 | Per failure | Log critical, disable worker until manual intervention |
| `last_poll_at` stale (> 5 min) | 5 seconds | Force restart task |

**Worker State Table Usage:**

The `worker_state` table tracks:
- `last_processed_time`: Time-based resume point after restart
- `last_poll_at`: Staleness detection
- `consecutive_failures`: Health metric

The `processed_kills` table provides duplicate detection:
- Workers query kills since `last_processed_time - overlap_window`
- Each kill is checked against `processed_kills` before notification
- Successfully notified kills are recorded to prevent duplicates

On startup, supervisor reads `worker_state` to resume workers from their last time position. The overlap window ensures no kills are missed due to out-of-order RedisQ delivery, while `processed_kills` prevents duplicate notifications.

**Cold Start Behavior:**

When a worker starts with no prior state (new profile or fresh database), it must initialize `last_processed_time`. Backfilling historical kills is explicitly not supported (see Resolved Questions).

```python
async def _initialize_worker_state(self, worker_name: str) -> WorkerState:
    """Initialize state for a new worker."""
    state = await self.store.get_worker_state(worker_name)

    if state is None:
        # Cold start: begin from now, no historical backfill
        initial_time = int(time.time())
        await self.store.update_worker_state(
            worker_name,
            last_processed_time=initial_time,
            last_poll_at=initial_time,
            consecutive_failures=0,
        )
        logger.info(
            "Worker %s cold start: beginning from %s (no backfill)",
            worker_name,
            datetime.fromtimestamp(initial_time).isoformat()
        )
        return await self.store.get_worker_state(worker_name)

    return state
```

**Long Downtime Recovery:**

If a worker was offline longer than the `processed_kills` retention period (default 1 hour), resuming from `last_processed_time` risks duplicate notifications for kills that were processed before but whose `processed_kills` entries have expired.

**Resolution:** Cap the lookback window to the `processed_kills` retention period:

```python
async def _get_safe_query_since(self, state: WorkerState, profile: NotificationProfile) -> int:
    """Calculate query start time, capped to processed_kills retention."""
    overlap = profile.polling.overlap_window_seconds
    processed_kills_retention = 3600  # 1 hour

    # Normal case: query from last_processed_time minus overlap
    ideal_since = state.last_processed_time - overlap

    # Safety cap: don't look back further than processed_kills retention
    # This prevents duplicates when worker was down longer than retention
    min_since = int(time.time()) - processed_kills_retention

    if ideal_since < min_since:
        gap_hours = (min_since - ideal_since) / 3600
        logger.warning(
            "Worker %s was offline %.1f hours. Capping lookback to %d seconds "
            "to prevent duplicates. Some kills may be missed.",
            state.worker_name,
            gap_hours,
            processed_kills_retention
        )
        return min_since

    return ideal_since
```

| Downtime | Behavior |
|----------|----------|
| < 1 hour | Resume normally, `processed_kills` prevents duplicates |
| 1-24 hours | Cap lookback to 1 hour, log warning about potential missed kills |
| > 24 hours | Same as above; kills older than 7 days are expunged anyway |

**Debugging timing issues:** See "Appendix: Troubleshooting Guide" for the complete diagnosis flow when kills don't fire as expected.

**Operator Guidance:** If a worker was offline for an extended period, operators can:
1. Accept the gap (most common - missed kills are visible on zkillboard)
2. Manually query the MCP `killmails` tool for the gap period
3. Delete worker state to trigger cold start (loses gap, no duplicates)

**Graceful Shutdown:**

1. Set `running = False`
2. Cancel all worker tasks
3. Wait for in-flight Discord deliveries to complete (timeout: 10 seconds)
4. Persist final `worker_state` for each worker

```python
SHUTDOWN_TIMEOUT_SECONDS = 10

async def shutdown(self):
    """Graceful shutdown with timeout."""
    self.running = False

    # Cancel all worker tasks
    for task in self.tasks.values():
        task.cancel()

    # Wait for graceful completion with timeout
    try:
        await asyncio.wait_for(
            asyncio.gather(*self.tasks.values(), return_exceptions=True),
            timeout=SHUTDOWN_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        logger.warning(
            "Shutdown timeout after %ds - %d tasks forcibly cancelled",
            SHUTDOWN_TIMEOUT_SECONDS,
            len([t for t in self.tasks.values() if not t.done()])
        )

    # Persist final state for all workers
    for name, task in self.tasks.items():
        await self._persist_final_state(name)
```

**Pending kills at shutdown:** Kills that were queried but not yet delivered will be reprocessed on restart. The `processed_kills` table prevents duplicate notifications—workers will skip kills already marked as delivered.

**Limitations:**

- Process crash kills all workers (acceptable for this scale)
- No memory isolation between workers (shared ESI cache is a feature, not a bug)
- For production deployments, wrap with OS service manager (systemd/launchd) for process-level supervision

**Profile Hot Reload:**

Profile changes require supervisor restart. The supervisor does not watch profile files for changes.

**Rationale:**
- Hot reload adds complexity (file watchers, partial state migration)
- Profile changes are infrequent
- Restart is quick and ensures clean state

**Operator workflow:**
1. Edit profile YAML
2. Restart notification service (or send SIGHUP if implemented later)
3. Supervisor loads updated profiles on startup

**Orphaned State Cleanup:**

When profiles are deleted, their `worker_state` and `processed_kills` entries become orphaned. The expunge task cleans these up:

```python
async def expunge_orphaned_state(self, active_profiles: set[str]) -> int:
    """Remove state for profiles no longer in configuration."""
    result = await self.db.execute("""
        DELETE FROM worker_state
        WHERE worker_name NOT IN ({})
    """.format(",".join("?" * len(active_profiles))), tuple(active_profiles))

    await self.db.execute("""
        DELETE FROM processed_kills
        WHERE worker_name NOT IN ({})
    """.format(",".join("?" * len(active_profiles))), tuple(active_profiles))

    return result.rowcount
```

This runs on supervisor startup and periodically (hourly) to catch profiles deleted while running.

### D8: MCP Process Architecture

**Decision:** The `killmails` MCP tool runs within the aria-universe server, accessing the shared SQLite database via file path.

**Rationale:**

The notification system (ingest + workers) and aria-universe MCP server are separate processes. Both need access to `killmails.db`:

| Process | Access Pattern | Operations |
|---------|----------------|------------|
| Notification service | Read/write | Ingest, worker queries, state updates |
| aria-universe MCP | Read-only | Query, stats, resource reads |

**Database Location:**

```
cache/killmails.db  # Shared location, configurable via ARIA_KILLMAIL_DB
```

**Concurrency Safety:**

SQLite with WAL mode supports multiple readers and a single writer across processes. The MCP server only reads, so no write contention occurs. WAL checkpointing is handled by the notification service (the primary writer).

**Connection Configuration (MCP side):**

```python
# MCP server opens database read-only
connection = await aiosqlite.connect(
    db_path,
    mode="ro",  # Read-only mode
)
await connection.execute("PRAGMA query_only=ON")
```

**Alternative Considered:**

A dedicated killmail MCP server was considered but rejected:
- Additional process to manage
- Operational complexity (two MCP servers instead of one)
- No architectural benefit—SQLite handles cross-process access natively

**Startup Dependency:**

The aria-universe MCP server gracefully handles missing `killmails.db`:
- If database doesn't exist, `killmails()` tool returns error message directing user to start notification service
- MCP server continues serving other tools (universe, market, sde, etc.)

---

### D9: Database Schema Migrations

**Decision:** Use a migration table with versioned SQL scripts, applied automatically on startup.

**Rationale:**
- Schema will evolve as features are added (e.g., new indices, additional tables)
- SQLite doesn't have built-in migration support
- Manual migrations are error-prone and don't scale

**Migration Table:**

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at INTEGER NOT NULL,
    description TEXT
);
```

**Migration Runner:**

```python
from pathlib import Path
import aiosqlite

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

class MigrationRunner:
    """Apply database migrations on startup."""

    def __init__(self, db_path: Path):
        self.db_path = db_path

    async def run_migrations(self) -> int:
        """Apply pending migrations. Returns count applied."""
        async with aiosqlite.connect(self.db_path) as db:
            await self._ensure_migrations_table(db)
            current = await self._get_current_version(db)
            applied = 0

            for migration_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
                version = int(migration_file.stem.split("_")[0])
                if version > current:
                    await self._apply_migration(db, version, migration_file)
                    applied += 1

            return applied

    async def _apply_migration(
        self, db: aiosqlite.Connection, version: int, path: Path
    ) -> None:
        """Apply a single migration within a transaction."""
        sql = path.read_text()
        description = path.stem.split("_", 1)[1].replace("_", " ")

        await db.executescript(sql)
        await db.execute(
            "INSERT INTO schema_migrations (version, applied_at, description) VALUES (?, ?, ?)",
            (version, int(time.time()), description),
        )
        await db.commit()
        logger.info("Applied migration %d: %s", version, description)
```

**Migration File Naming:**

```
migrations/
  001_initial_schema.sql
  002_add_processed_kills.sql
  003_add_esi_fetch_claims.sql
```

**Startup Integration:**

```python
class SQLiteKillmailStore:
    async def initialize(self) -> None:
        """Initialize database, running migrations if needed."""
        runner = MigrationRunner(self.db_path)
        applied = await runner.run_migrations()
        if applied:
            logger.info("Applied %d database migrations", applied)
```

**Rollback Strategy:** SQLite doesn't support transactional DDL rollback for all operations. Failed migrations leave the database in an inconsistent state. Mitigation:
1. Test migrations thoroughly before release
2. Backup `killmails.db` before upgrades (documented in release notes)
3. For catastrophic failures, delete database and cold start (data loss acceptable for 7-day rolling window)

---

## Database Schema

See [`killmail_store_schema.sql`](killmail_store_schema.sql) for the complete DDL including all tables, indices, and configuration notes.

### Schema Overview

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `killmails` | RedisQ metadata (all kills) | `kill_id`, `solar_system_id`, `kill_time`, `zkb_hash` |
| `esi_details` | Full ESI data (lazy-populated) | `kill_id`, `victim_*`, `attackers_json`, `fetch_status` |
| `esi_fetch_attempts` | Track failed ESI fetches | `kill_id`, `attempts`, `last_error` |
| `worker_state` | Worker checkpoints | `worker_name`, `last_processed_time` |
| `processed_kills` | Duplicate detection | `(worker_name, kill_id)`, `delivery_status` |
| `esi_fetch_claims` | ESI fetch coordination | `kill_id`, `claimed_by`, `claimed_at` |
| `schema_migrations` | Migration tracking | `version`, `applied_at` |

### Key Design Points

**Data Authority (D6):** The `killmails` table contains denormalized victim data from zkb for fast filtering. When `esi_details` exists, it is authoritative for display purposes.

**Sentinel Rows:** When ESI fetch permanently fails (after max attempts), a sentinel row is inserted in `esi_details`:
- `fetched_at = 0`
- `fetch_status = 'unfetchable'`
- All detail fields NULL

Workers check `fetch_status` before attempting ESI fetch to avoid retry storms.

**ESI Fetch Attempts Tracking:** The `esi_fetch_attempts` table tracks failed fetch attempts *before* the first successful fetch. This is necessary because `esi_details.fetch_attempts` only exists after success. Lifecycle:
1. First attempt fails → INSERT row with `attempts=1`
2. Subsequent failures → UPDATE `attempts += 1`
3. Success → DELETE row (data now in `esi_details`)
4. Max attempts (3) → INSERT sentinel to `esi_details`, DELETE from `esi_fetch_attempts`

This keeps the table small (only in-flight or recently-failed fetches) while providing accurate cross-worker tracking.

**Duplicate Detection Flow:**

```
Worker polls for kills since last_processed_time - overlap_window
        │
        ▼
For each kill in results:
        │
        ├─── kill_id in processed_kills? ──▶ Skip (already notified)
        │
        └─── Not found ──▶ Process kill ──▶ INSERT into processed_kills
                                │
                                ▼
                          Update last_processed_time if kill_time > current
```

**Why time-based with overlap?**

Kill IDs are globally unique but assigned at kill time on CCP's servers. RedisQ delivery order depends on zkillboard's processing queue, not kill time. A kill from 10 minutes ago may arrive after a kill from 5 minutes ago. ID-based high-water marks would skip the older kill.

The overlap window (default: 5 minutes) ensures workers re-query recent kills, with `processed_kills` preventing duplicate notifications.

**ESI Claim Lifecycle:** Claims are inserted before ESI fetch, deleted after successful insert to `esi_details`. Claims older than 60 seconds are considered abandoned and cleaned up by the expunge task.

---

## MCP Interface

### Tool: `killmails`

```python
def killmails(
    action: str,
    # Query params
    systems: list[str] | None = None,
    hours: int = 1,
    min_value: int | None = None,
    corporations: list[int] | None = None,
    alliances: list[int] | None = None,
    limit: int = 50,
    # Stats params
    group_by: str | None = None,  # "system", "hour", "corporation"
) -> dict:
    """
    Query local killmail store.

    Actions:
    - query: Return matching killmails
    - stats: Return aggregated statistics
    - recent: Return most recent N kills (no filter)
    """
```

**System Name Resolution:**

The `systems` parameter accepts human-readable system names (e.g., `"Jita"`, `"Uedama"`). The MCP tool resolves these to `solar_system_id` integers using the same universe graph lookup used elsewhere in aria-universe.

```python
async def _resolve_systems(self, names: list[str]) -> list[int]:
    """Resolve system names to IDs via universe graph."""
    system_ids = []
    for name in names:
        system_id = self.universe.get_system_id(name)
        if system_id is None:
            raise ValueError(f"Unknown system: {name}")
        system_ids.append(system_id)
    return system_ids
```

Invalid system names return an error response rather than silently returning no results. This matches the behavior of `universe(action="route")` and other MCP tools.

**Example Queries:**

```python
# Recent activity in Jita
killmails(action="query", systems=["Jita"], hours=1)

# High-value losses in home systems
killmails(action="query", systems=["Simela", "Sortet"], min_value=100_000_000)

# Activity stats for route
killmails(action="stats", systems=["Uedama", "Sivala", "Niarja"], group_by="system")
```

### Resource: `killmail://{kill_id}`

```python
# Returns full killmail data (fetches ESI if not cached)
ReadMcpResourceTool(server="aria-killmails", uri="killmail://12345678")
```

### Pagination Strategy

Large result sets (>100 kills) require cursor-based pagination to avoid memory issues and provide predictable response times.

**Cursor Design:**

The cursor encodes the last seen `(kill_time, kill_id)` tuple. This allows efficient keyset pagination using the existing `idx_killmails_time` index.

```python
def killmails(
    action: str,
    # ... existing params ...
    limit: int = 50,
    cursor: str | None = None,  # Opaque pagination cursor
) -> dict:
    """
    Returns:
        {
            "kills": [...],
            "next_cursor": "eyJ0IjoxNzA2MjkxMjAwLCJpIjoxMjM0NTY3OH0=",  # or None if no more
            "total_estimate": 1500,  # Approximate total matching (for UI)
        }
    """
```

**Cursor Encoding:**

```python
import base64
import json

def encode_cursor(kill_time: int, kill_id: int) -> str:
    """Encode pagination cursor as opaque string."""
    return base64.urlsafe_b64encode(
        json.dumps({"t": kill_time, "i": kill_id}).encode()
    ).decode()

def decode_cursor(cursor: str) -> tuple[int, int]:
    """Decode cursor to (kill_time, kill_id)."""
    data = json.loads(base64.urlsafe_b64decode(cursor))
    return data["t"], data["i"]
```

**Query with Cursor:**

```sql
-- First page (no cursor)
SELECT * FROM killmails
WHERE solar_system_id IN (?)
  AND kill_time >= ?
ORDER BY kill_time DESC, kill_id DESC
LIMIT ?;

-- Subsequent pages (with cursor)
SELECT * FROM killmails
WHERE solar_system_id IN (?)
  AND kill_time >= ?
  AND (kill_time, kill_id) < (?, ?)  -- Cursor values
ORDER BY kill_time DESC, kill_id DESC
LIMIT ?;
```

**Total Estimate:**

For UI pagination indicators, provide an approximate count without a full table scan:

```sql
-- Fast estimate using SQLite's internal stats
SELECT MAX(rowid) - MIN(rowid) AS estimate
FROM killmails
WHERE solar_system_id IN (?) AND kill_time >= ?;
```

This is an upper bound (may include deleted rows) but is O(1) and sufficient for "~1500 kills" display.

**Limits:**

| Parameter | Default | Max | Rationale |
|-----------|---------|-----|-----------|
| `limit` | 50 | 200 | Balance response size vs round trips |
| `hours` | 1 | 168 (7 days) | Match retention period |

---

## Worker Profile Schema (v2)

Updated schema with new fields:

```yaml
schema_version: 2

name: "home-ops"
display_name: "Home Operations"
enabled: true
webhook_url: "https://discord.com/api/webhooks/..."

# NEW: Worker polling configuration
polling:
  interval_seconds: 30          # How often to check for new kills
  batch_size: 10                # Max kills to process per poll
  overlap_window_seconds: 300   # Re-query window for out-of-order kills (default 5 min)

# NEW: Rate limit handling
rate_limit_strategy:
  rollup_threshold: 5           # Roll up if more than N pending
  max_rollup_kills: 20          # Cap rollup message size
  backoff_seconds: 60           # Wait time after rate limit

# NEW: Delivery failure handling
delivery:
  max_attempts: 3               # Max delivery attempts per kill before marking failed
  retry_delay_seconds: 30       # Delay between retries

# Topology (unchanged, but system names resolved to IDs at load)
topology:
  geographic:
    systems:
      - name: "Simela"          # Resolved to solar_system_id at profile load
        classification: "home"

# Triggers (unchanged)
triggers:
  watchlist_activity: true
  gatecamp_detected: true
  high_value_threshold: 100000000

# Throttle (unchanged)
throttle_minutes: 5

# Quiet hours (unchanged)
quiet_hours:
  enabled: false
```

**Schema Defaults (v1 → v2 upgrade):**

| Field | Default Value |
|-------|---------------|
| `polling.interval_seconds` | 60 |
| `polling.batch_size` | 10 |
| `polling.overlap_window_seconds` | 300 |
| `rate_limit_strategy.rollup_threshold` | 5 |
| `rate_limit_strategy.max_rollup_kills` | 20 |
| `rate_limit_strategy.backoff_seconds` | 60 |
| `delivery.max_attempts` | 3 |
| `delivery.retry_delay_seconds` | 30 |

---

## Implementation Phases

### Phase 1: Storage Foundation

1. Implement `KillmailStore` protocol and SQLite implementation
2. Create database schema with migrations (D9)
3. Configure WAL mode and connection pool (D1)
4. Add auto-expunge background task:
   - Killmails older than retention period
   - ESI details for expunged killmails
   - ESI fetch attempts for expunged killmails
   - Stale ESI fetch claims (>60s)
   - Processed kills older than 1 hour
   - Orphaned worker state for deleted profiles
5. Add index optimization after expunge cycles
6. Unit tests for storage operations
7. Integration tests for concurrent access scenarios

**Deliverables:**
- `src/aria_esi/services/killmail_store/protocol.py`
- `src/aria_esi/services/killmail_store/sqlite.py`
- `src/aria_esi/services/killmail_store/migrations.py`
- `src/aria_esi/services/killmail_store/migrations/*.sql`
- `src/aria_esi/services/killmail_store/expunge.py`

**Test Coverage:**
- Unit: CRUD operations, migration runner, cursor encoding, sentinel row handling
- Integration: Concurrent writers (simulate ingest + workers), connection pool exhaustion, WAL checkpoint behavior, orphaned state cleanup

### Phase 2: Ingest Refactor

1. Implement bounded queue with backpressure (D5)
2. Modify RedisQ poller to write ALL kills to store
3. Remove topology pre-filter from ingest path
4. Add ingest metrics and observability hooks
5. Ensure backward compatibility during transition

**Deliverables:**
- `src/aria_esi/services/killmail_store/queue.py` (bounded queue implementation)
- Modified `src/aria_esi/services/redisq/poller.py`
- Ingest metrics exposed via status endpoint
- Migration guide for existing users

### Phase 3: Worker Refactor

1. Refactor `NotificationManager` to poll from store
2. Implement per-worker polling intervals
3. Implement ESI fetch coordination with claim table (D3)
4. Implement rate limit rollup strategy (D4)
5. Implement delivery failure tracking with max attempts
6. Implement cold start and downtime recovery (D7)
7. Add system name → ID resolution at profile load time
8. Integration tests for coordination scenarios

**Deliverables:**
- `src/aria_esi/services/redisq/notifications/worker.py`
- `src/aria_esi/services/redisq/notifications/supervisor.py`
- `src/aria_esi/services/redisq/notifications/esi_coordinator.py`
- `src/aria_esi/services/redisq/notifications/system_resolver.py`
- Updated profile schema (v2)

**System Name Resolution:**

Profile YAML uses human-readable system names (`Simela`), but `killmails` table uses `solar_system_id`. Resolution happens at profile load:

```python
class ProfileLoader:
    def __init__(self, universe_graph: UniverseGraph):
        self.universe = universe_graph

    def load(self, path: Path) -> NotificationProfile:
        raw = yaml.safe_load(path.read_text())
        profile = NotificationProfile.from_dict(raw)

        # Resolve system names to IDs
        profile.topology.system_ids = [
            self.universe.get_system_id(s.name)
            for s in profile.topology.geographic.systems
        ]
        return profile
```

Invalid system names raise `ProfileValidationError` at load time, not at query time.

**Test Coverage:**
- Unit: Worker state initialization, cursor calculation, rollup formatting, system resolution
- Integration: Multi-worker claim races, stale claim recovery, long downtime simulation, duplicate detection across overlap window, delivery failure max attempts

### Phase 4: MCP Exposure

1. Add `killmails` tool to aria-universe MCP server
2. Implement cursor-based pagination
3. Add `killmail://` resource handler
4. Expose ingest and worker metrics via status endpoint
5. Performance benchmarks with realistic data volume
6. Update CLAUDE.md with new capabilities
7. Add troubleshooting guide for notification debugging

**Deliverables:**
- MCP tool implementation in `src/aria_mcp/tools/killmails.py`
- Metrics exposure in `status()` response
- Documentation updates
- `docs/NOTIFICATION_TROUBLESHOOTING.md` - "Why didn't my kill fire?" diagnosis guide

**Metrics Exposure:**

The `status()` dispatcher includes killmail store metrics:

```python
{
    "killmails": {
        "store": {
            "total_records": 187432,
            "oldest_record": "2026-01-19T12:00:00Z",
            "database_size_mb": 38.2
        },
        "ingest": {
            "received_total": 245000,
            "written_total": 244850,
            "dropped_total": 150,
            "queue_depth": 12,
            "last_drop_time": null
        },
        "workers": {
            "active": 3,
            "total_deliveries": 1523,
            "failed_deliveries": 7
        }
    }
}
```

**Test Coverage:**
- Unit: Cursor encoding/decoding, query building, result formatting
- Integration: Pagination through large result sets, concurrent MCP queries
- Benchmarks: Query latency at 50k/100k/200k records, index effectiveness validation

**Benchmark Targets:**

| Operation | Records | Target p50 | Target p99 |
|-----------|---------|------------|------------|
| Query by system (1 hour) | 200k | < 5 ms | < 20 ms |
| Query by system (7 days) | 200k | < 20 ms | < 100 ms |
| Stats aggregation | 200k | < 50 ms | < 200 ms |
| Cursor pagination (50 results) | 200k | < 5 ms | < 15 ms |

Benchmarks run against synthetic data matching production volume. If targets not met, investigate index usage with `EXPLAIN QUERY PLAN`.

---

## Risks and Open Questions

### Confirmed Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Storage growth | Medium | Auto-expunge + configurable retention |
| ESI rate limits | Medium | Lazy fetch + claim table coordination (D3) + sentinel for persistent failures |
| Discord rate limits | Low | Rollup strategy + max delivery attempts |
| Migration complexity | Medium | Phased rollout with backward compat + auto-upgrade v1→v2 |
| Ingest backpressure | Medium | Bounded queue with drop-oldest (D5) |
| Index fragmentation | Low | PRAGMA optimize after expunge cycles |
| Cross-process DB access | Low | WAL mode + read-only MCP connections (D8) |

### Resolved Questions

| Area | Decision | Rationale |
|------|----------|-----------|
| **Schema Migration** | Auto-upgrade v1 → v2 with backup | Profile loader detects `schema_version` field. If missing or v1: (1) creates backup at `{profile}.v1.backup.yaml`, (2) applies v2 defaults, (3) rewrites original file with `schema_version: 2`. Upgrade is automatic and in-place on first load. |
| **MCP Scope** | Part of aria-universe server | Shares database file (read-only) with notification service. Consistent with dispatcher pattern (`universe()`, `market()`, `sde()`). See D9 for process architecture. |
| **Backfill** | No backfill on first run | Data collection begins at first startup. Backfilling from zKillboard API would require rate-limited pagination and delay startup. Users expecting historical data should be directed to zkillboard.com for pre-startup queries. Document this expectation in setup guide. |
| **MCP Query Performance** | Cursor-based pagination | Keyset pagination using `(kill_time, kill_id)` cursor. See MCP Interface → Pagination Strategy. Default limit 50, max 200. Concrete benchmark targets defined in Phase 4. |
| **Profile Hot Reload** | Restart required | Hot reload adds complexity with limited benefit. Profile changes are infrequent. Supervisor reloads all profiles on startup. See D7 for details. |
| **System Name Resolution** | Resolve at profile load | Profile YAML uses human-readable names; resolution to system IDs happens once at load time via universe graph. Invalid names fail fast. See Phase 3. |
| **Delivery Failures** | Max attempts with permanent skip | After `max_attempts` (default 3) failures, kill is marked `failed` in `processed_kills` and skipped. Prevents infinite retry loops for bad webhooks. See D4. |
| **ESI Persistent Failures** | Sentinel rows after max attempts | Unfetchable kills (404, 403) get sentinel row in `esi_details` after 3 attempts. Prevents retry storms. See D3. |
| **ESI Fetch Attempts Tracking** | Separate `esi_fetch_attempts` table | Attempts must be tracked before first successful fetch (when `esi_details` doesn't exist). Dedicated table with lifecycle: INSERT on first failure, UPDATE on retry, DELETE on success or sentinel insertion. See D3. |
| **MCP System Name Resolution** | Resolve via universe graph | MCP `killmails` tool accepts human-readable system names and resolves to `solar_system_id` using the same universe graph lookup as other aria-universe tools. Invalid names return error. See MCP Interface section. |
| **Orphaned State** | Expunge on startup and hourly | Worker state for deleted profiles is cleaned up automatically. See D7. |

---

## Migration Path

### For Existing Users

1. **Phase 1-2:** No user action required. Ingest stores all kills; existing topology filter continues to work for ESI fetch decisions.

2. **Phase 3:** Notification profiles gain new optional fields. Existing profiles work unchanged (defaults applied).

3. **Phase 4:** MCP tools become available. `config.json → context_topology` can be deprecated for notification use cases.

### Deprecation Timeline

| Config | Status | Removal Target |
|--------|--------|----------------|
| `redisq.context_topology` | Deprecated for notifications | v3.0 |
| `redisq.topology` (legacy) | Deprecated | v2.5 |
| Profile schema v1 | Supported with auto-upgrade | v3.0 |

---

## Appendix: Troubleshooting Guide

### "Why Didn't My Kill Fire?"

When a kill doesn't trigger an expected notification, follow this diagnosis flow:

```
1. Was the kill ingested?
   └─ Query: killmails(action="query", systems=["Jita"], hours=1)
   └─ If missing: Check ingest service logs for backpressure drops

2. Does the profile match the system?
   └─ Check: profile.topology.geographic.systems includes the system
   └─ Note: System names are resolved to IDs at profile load time

3. Did the worker process this kill?
   └─ Query: SELECT * FROM processed_kills WHERE kill_id = ?
   └─ If missing: Worker hasn't reached this kill yet (check last_poll_at)
   └─ If status='failed': Delivery failed after max_attempts

4. Did the kill match profile triggers?
   └─ Check: high_value_threshold vs zkb_total_value
   └─ Check: watchlist_activity settings
   └─ Check: quiet_hours configuration

5. Was the worker offline during the kill?
   └─ Query: SELECT * FROM worker_state WHERE worker_name = ?
   └─ If last_poll_at is stale (> 5 min): Worker may have crashed
   └─ If offline > 1 hour: Kills during gap may be skipped (see D7)
```

### Key Timing Interactions

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `polling.interval_seconds` | 60 | How often worker checks for new kills |
| `polling.overlap_window_seconds` | 300 | Re-query window for out-of-order arrivals |
| `processed_kills` retention | 3600 (1 hr) | Duplicate detection window |
| Long downtime cap | 3600 (1 hr) | Max lookback after extended offline |

**Scenario: Worker offline for 2 hours**

1. Worker restarts, reads `last_processed_time` from 2 hours ago
2. Safety cap kicks in: lookback limited to 1 hour (not 2)
3. Kills from hour 1-2 of downtime are skipped (would cause duplicates)
4. Warning logged: "Worker was offline 2.0 hours. Capping lookback..."

**Operator options:**
- Accept the gap (kills visible on zkillboard.com)
- Query via MCP: `killmails(action="query", systems=[...], hours=2)`
- Delete worker state to force cold start (loses gap, no duplicates)

### Common Issues

| Symptom | Likely Cause | Resolution |
|---------|--------------|------------|
| No kills for any profile | Ingest service not running | Start `aria-esi redisq` |
| Kills appear but no Discord | Invalid webhook URL | Run `notifications test <profile>` |
| Some kills missing | Profile system mismatch | Check system name spelling in YAML |
| Duplicate notifications | `processed_kills` table corrupted | Delete and let worker rebuild |
| Delayed notifications | Discord rate limiting | Check rollup messages, increase interval |

---

## Appendix: Capacity Estimates

### Storage

| Metric | Value |
|--------|-------|
| Kills per day | ~30,000 |
| Retention (killmails) | 7 days |
| Retention (esi_details) | 7 days (follows killmails) |
| Retention (esi_fetch_attempts) | Follows killmails (orphan cleanup) |
| Retention (processed_kills) | 1 hour |
| Retention (esi_fetch_claims) | 60 seconds (stale threshold) |
| Total killmail records | ~210,000 |
| Total processed_kills records | ~1,250 per worker (30k/day ÷ 24) |
| Total esi_fetch_attempts records | ~100-500 (in-flight + recent failures) |
| Total esi_fetch_claims records | ~10-50 (transient, high turnover) |
| Avg record size (killmails) | ~200 bytes |
| Avg record size (esi_details) | ~2 KB |
| Avg record size (processed_kills) | ~60 bytes (with status fields) |
| Base storage (killmails only) | ~42 MB |
| Full storage (with ESI) | ~420 MB |
| Index overhead | ~15% of data size |

### Performance

| Operation | Expected Latency |
|-----------|------------------|
| Insert kill | < 1 ms |
| Query by system (1 hour) | < 10 ms |
| Query by system (7 days) | < 100 ms |
| Full table scan | < 1 s |

*Note: Estimates assume SQLite with proper indexing. Actual performance should be benchmarked.*

### Burst Handling

| Scenario | Rate | Duration | Total Kills | Queue Behavior |
|----------|------|----------|-------------|----------------|
| Normal operation | ~0.35/sec | Continuous | ~30k/day | Queue near-empty |
| Regional battle | ~8/sec | 10 min | ~5,000 | Queue fills, drains after |
| Major null-sec fight | ~17/sec | 30 min | ~30,000 | Queue saturates, drops expected |
| Historic battle (B-R5RB scale) | ~50/sec | 2 hours | ~360,000 | Significant drops, acceptable |

The bounded queue (D5) accepts data loss during extreme events in exchange for bounded memory usage and system stability. Dropped kills during major battles are acceptable—they remain queryable via zKillboard's API if needed for historical analysis.
