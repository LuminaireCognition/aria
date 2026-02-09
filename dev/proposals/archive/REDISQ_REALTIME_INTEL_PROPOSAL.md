# RedisQ Real-Time Intelligence Proposal

## Executive Summary

ARIA's threat assessment currently relies on **hourly aggregated activity data** from ESI. While useful for general situational awareness, this data lacks the granularity needed for tactical decision-making in dangerous space. A gatecamp that formed 10 minutes ago won't appear in hourly kills—but pilots need to know about it *now*.

This proposal introduces **real-time killmail streaming** via zKillboard's RedisQ service. A background poller monitors the kill feed, processes relevant events, and updates ARIA's threat intelligence layer. The result: minute-by-minute awareness of hostile activity, active gatecamp detection, and operational alerts for pilots in dangerous regions.

**Key capabilities:**

| Capability | Current State | With RedisQ |
|------------|---------------|-------------|
| Threat data freshness | 1 hour | ~1 minute |
| Gatecamp detection | Historical only | Real-time (multiple kills = active camp) |
| Target tracking | Manual ESI queries | Automatic alerts on tracked entities |
| Fleet doctrine intel | Not available | Inferred from recent losses |

**Integration scope:**
- Background polling daemon
- Kill event processor with filtering
- Threat cache updates
- Optional: Pilot alerts for operational areas

---

## Problem Statement

### Current Limitations

ARIA's `/threat-assessment` skill uses `universe(action="activity")` which returns **hourly aggregates**:

```python
universe(action="activity", systems=["Tama", "Amamake"])
# Returns: {"Tama": {"ship_kills": 12, "pod_kills": 8, "jumps": 450}, ...}
```

This data answers "how dangerous is this system generally?" but cannot answer:

1. **Is there an active gatecamp right now?** (Kills from 45 minutes ago ≠ current threat)
2. **Who is doing the killing?** (No attacker information in aggregates)
3. **What ships are they using?** (No fleet composition data)
4. **Is my war target active in this region?** (No entity filtering)

### Real Scenarios Where This Fails

**Scenario 1: Fresh Gatecamp**
> Pilot asks: "Is Niarja safe right now?"
> ARIA checks hourly data: "3 ship kills in the last hour, moderate risk."
> Reality: A 15-man Tornado fleet set up 5 minutes ago. Pilot jumps in and dies.

**Scenario 2: Stale Threat**
> Hourly data shows 20 kills in Tama.
> Pilot avoids Tama entirely.
> Reality: Those kills were from a single fight 55 minutes ago. Tama has been quiet since.

**Scenario 3: War Target Intel**
> Corp is war-decced by a known group.
> Pilot has no way to know if war targets are currently active nearby.
> Reality: War targets are camping the route to Jita right now.

### What Pilots Actually Need

Real-time answers to:
- "Are there active hunters in my operational area?"
- "Has anyone died on this gate in the last 10 minutes?"
- "Is [hostile corp] currently active?"
- "What ships are being used to kill people in this pipe?"

---

## Proposed Solution

### Architecture Overview

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   zKillboard    │     │  ARIA Poller     │     │  Threat Cache   │
│   RedisQ API    │────▶│  (Background)    │────▶│  (SQLite)       │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                │                         │
                                │                         │
                                ▼                         ▼
                        ┌──────────────────┐     ┌─────────────────┐
                        │  Event Filters   │     │  ARIA Skills    │
                        │  - Region        │     │  - /threat      │
                        │  - Entity        │     │  - /route       │
                        │  - Value         │     │  - /gatecamp    │
                        └──────────────────┘     └─────────────────┘
```

### RedisQ Integration

**Endpoint:** `https://zkillredisq.stream/listen.php`

**Polling Pattern:**
```python
async def poll_redisq(queue_id: str, ttw: int = 10) -> Kill | None:
    """
    Long-poll RedisQ for next killmail.

    Args:
        queue_id: Unique identifier (e.g., "aria-{installation_uuid}")
        ttw: Time to wait (1-10 seconds)

    Returns:
        Kill object or None if no kill within ttw
    """
    url = f"https://zkillredisq.stream/listen.php?queueID={queue_id}&ttw={ttw}"
    response = await http_client.get(url)
    data = response.json()

    if data.get("package") is None:
        return None

    # RedisQ returns kill ID + hash; queue for async fetch
    kill_id = data["package"]["killID"]
    zkb = data["package"]["zkb"]

    # Don't fetch inline - queue for rate-limited processing
    return QueuedKill(kill_id=kill_id, hash=zkb["hash"], zkb_data=zkb)
```

**Rate Limiting:**
- One active request per queueID (429 if violated)
- 2 requests/second per IP (CloudFlare enforced)
- Excessive 429 errors trigger IP bans

**Queue Persistence:**
- Queue state retained for 3 hours
- Gaps >3 hours lose intermediate kills
- See **Gap Recovery** below for backfill strategy

### Kill Fetch Queue (Avoiding N+1)

RedisQ returns only kill ID + hash; full killmail data requires an ESI call per kill. During high-activity events (large fights, active gank fleets), this can mean hundreds of kills in quick succession.

**Solution:** Decouple polling from fetching via an internal queue with rate limiting.

```python
class KillFetchQueue:
    """
    Rate-limited queue for ESI killmail fetches.

    Prevents overwhelming ESI during high-activity periods while
    ensuring recent kills are prioritized over backlog.
    """
    MAX_CONCURRENT_FETCHES = 5
    FETCH_RATE_LIMIT = 20  # per second (ESI allows ~30)
    MAX_QUEUE_SIZE = 1000  # Drop oldest if exceeded

    def __init__(self):
        self._queue: deque[QueuedKill] = deque(maxlen=self.MAX_QUEUE_SIZE)
        self._semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_FETCHES)
        self._rate_limiter = RateLimiter(self.FETCH_RATE_LIMIT)

    async def enqueue(self, kill: QueuedKill) -> None:
        """Add kill to fetch queue. Drops oldest if at capacity."""
        self._queue.append(kill)

    async def process_queue(self) -> None:
        """Process queued kills with rate limiting."""
        while self._queue:
            kill = self._queue.popleft()
            async with self._semaphore:
                await self._rate_limiter.acquire()
                try:
                    full_kill = await fetch_full_killmail(kill.kill_id, kill.hash)
                    await self._process_kill(full_kill)
                except ESIError as e:
                    if e.status == 420:  # ESI rate limit
                        # Re-queue and back off
                        self._queue.appendleft(kill)
                        await asyncio.sleep(60)
                    else:
                        logger.warning(f"Failed to fetch kill {kill.kill_id}: {e}")

    @property
    def backlog_size(self) -> int:
        """Current queue depth for health monitoring."""
        return len(self._queue)
```

**Prioritization:** The `deque` with `maxlen` ensures that if backlog grows too large (e.g., during massive battles), oldest kills are dropped in favor of recent ones. Tactical intel prioritizes freshness over completeness.

### Gap Recovery (Backfill)

When ARIA restarts after being offline >3 hours, the RedisQ queue state is lost. To recover recent tactical intel:

```python
async def backfill_from_zkillboard(
    regions: list[int],
    since: datetime,
    max_kills: int = 500,
) -> list[ProcessedKill]:
    """
    Backfill kills from zKillboard API after extended downtime.

    Called on startup if last_poll_time > 3 hours ago.
    Uses zKillboard's public API (not RedisQ) for historical data.
    """
    kills = []
    for region_id in regions:
        url = f"https://zkillboard.com/api/kills/regionID/{region_id}/"
        response = await http_client.get(url)

        for kill_data in response.json():
            kill_time = parse_kill_time(kill_data["killmail_time"])
            if kill_time < since:
                break  # API returns newest first
            kills.append(await process_zkb_kill(kill_data))

            if len(kills) >= max_kills:
                return kills

    return kills


async def startup_recovery(config: RedisQConfig) -> None:
    """Check for gaps and backfill on startup."""
    last_poll = await get_last_poll_time()

    if last_poll is None:
        # First run - no backfill needed
        return

    gap_hours = (datetime.now() - last_poll).total_seconds() / 3600

    if gap_hours > 3:
        logger.info(f"Gap detected: {gap_hours:.1f}h. Backfilling from zKillboard...")
        kills = await backfill_from_zkillboard(
            regions=config.filter_regions,
            since=last_poll,
        )
        logger.info(f"Backfilled {len(kills)} kills")
        for kill in kills:
            await threat_cache.add_kill(kill)
```

**Limitations:**
- zKillboard API rate limits: 10 requests/second
- Backfill limited to 500 kills to avoid slow startup
- Only covers configured filter regions

### Kill Event Processing

**Data Flow:**

```
1. Receive kill from RedisQ (ID + hash only)
2. Fetch full killmail from ESI
3. Extract tactical data:
   - System ID → location
   - Victim ship/corp/alliance
   - Attackers (ships, corps, alliances)
   - Timestamp
   - Total value
4. Apply filters (region, entity, value threshold)
5. Update threat cache
6. Trigger alerts if configured
```

**Killmail Schema (from ESI):**

```python
@dataclass
class ProcessedKill:
    kill_id: int
    kill_time: datetime
    solar_system_id: int

    # Victim
    victim_ship_type_id: int
    victim_corporation_id: int
    victim_alliance_id: int | None

    # Attackers (full composition for fleet analysis)
    attacker_count: int
    attacker_corps: list[int]
    attacker_alliances: list[int]
    attacker_ship_types: list[int]  # All attacker ships, not just final blow
    final_blow_ship_type_id: int

    # Value
    total_value: float

    # Derived
    is_pod_kill: bool


@dataclass
class GatecampStatus:
    system_id: int
    kill_count: int
    window_minutes: int
    attacker_corps: list[int]
    attacker_ships: list[int]      # Full fleet composition from all kills
    confidence: str                 # "low", "medium", "high"
    last_kill: datetime
    is_smartbomb_camp: bool
    force_asymmetry: float          # Average attackers per kill
```

### Threat Cache Schema

```sql
CREATE TABLE realtime_kills (
    kill_id INTEGER PRIMARY KEY,
    kill_time INTEGER NOT NULL,           -- Unix timestamp
    solar_system_id INTEGER NOT NULL,

    victim_ship_type_id INTEGER,
    victim_corporation_id INTEGER,
    victim_alliance_id INTEGER,

    attacker_count INTEGER,
    attacker_corps TEXT,                  -- JSON array
    attacker_alliances TEXT,              -- JSON array
    attacker_ship_types TEXT,             -- JSON array
    final_blow_ship_type_id INTEGER,

    total_value REAL,
    is_pod_kill INTEGER,

    -- Indexing
    created_at INTEGER DEFAULT (strftime('%s', 'now'))
);

CREATE INDEX idx_kills_system_time ON realtime_kills(solar_system_id, kill_time);
CREATE INDEX idx_kills_time ON realtime_kills(kill_time);
CREATE INDEX idx_kills_attacker_corps ON realtime_kills(attacker_corps);

-- Cleanup: Remove kills older than 24 hours
-- (Run periodically or on startup)
DELETE FROM realtime_kills WHERE kill_time < strftime('%s', 'now') - 86400;
```

### Gatecamp Detection Algorithm

```python
from collections import Counter
from datetime import datetime, timedelta

GATECAMP_WINDOW_SECONDS = 600  # 10 minutes
GATECAMP_MIN_KILLS = 3
SMARTBOMB_WINDOW_SECONDS = 60  # Multiple kills within 60s window
FORCE_ASYMMETRY_THRESHOLD = 5  # Attackers outnumber victim 5:1 = camp behavior

# Common smartbomb platform type IDs
SMARTBOMB_SHIP_TYPES = {
    24690,  # Rokh
    24688,  # Apocalypse
    17740,  # Machariel
    17738,  # Nightmare
    24694,  # Hyperion
}

def detect_gatecamp(system_id: int, cache: ThreatCache) -> GatecampStatus | None:
    """
    Detect active gatecamp based on recent kill clustering.

    Heuristics:
    - 3+ kills in same system within 10 minutes = likely camp
    - Force asymmetry: attackers consistently outnumber victims 5:1+
    - Multiple victim corps OR high force asymmetry = camp (not fleet fight)
    - High pod:ship ratio increases confidence (camps kill pods)
    - Consistent attackers across kills increases confidence
    - Smartbomb detection via ship types + timing clusters
    """
    recent_kills = cache.get_kills(
        system_id=system_id,
        since=datetime.now() - timedelta(seconds=GATECAMP_WINDOW_SECONDS)
    )

    if len(recent_kills) < GATECAMP_MIN_KILLS:
        return None

    # Analyze kill pattern
    victim_corps = set(k.victim_corporation_id for k in recent_kills)
    attacker_corps = set()
    attacker_corp_counts = Counter()
    all_attacker_ships = set()
    for k in recent_kills:
        attacker_corps.update(k.attacker_corps)
        all_attacker_ships.update(k.attacker_ship_types)
        for corp in k.attacker_corps:
            attacker_corp_counts[corp] += 1

    # Calculate force asymmetry (attackers vs victims per kill)
    avg_attacker_count = sum(k.attacker_count for k in recent_kills) / len(recent_kills)
    high_force_asymmetry = avg_attacker_count >= FORCE_ASYMMETRY_THRESHOLD

    # Camp detection: multiple victim corps OR high force asymmetry
    # Single victim corp with similar-sized forces = fleet fight
    # Single victim corp but 5:1 attacker ratio = still a camp (small gang picked off)
    is_camp = len(victim_corps) > 1 or high_force_asymmetry

    if not is_camp:
        return None

    # Calculate confidence factors
    confidence_score = 0

    # Factor 1: Kill count
    if len(recent_kills) >= 5:
        confidence_score += 2
    else:
        confidence_score += 1

    # Factor 2: Pod kill ratio (camps kill pods, fights often don't)
    pod_kills = sum(1 for k in recent_kills if k.is_pod_kill)
    ship_kills = len(recent_kills) - pod_kills
    if ship_kills > 0 and pod_kills / ship_kills >= 0.5:
        confidence_score += 1

    # Factor 3: Attacker consistency (same group across kills)
    most_common_attacker_count = attacker_corp_counts.most_common(1)[0][1]
    if most_common_attacker_count >= len(recent_kills) * 0.7:
        confidence_score += 1

    # Factor 4: Smartbomb camp detection
    is_smartbomb = detect_smartbomb_camp(recent_kills, all_attacker_ships)
    if is_smartbomb:
        confidence_score += 1

    # Factor 5: Force asymmetry bonus
    if high_force_asymmetry:
        confidence_score += 1

    # Map score to confidence level
    if confidence_score >= 4:
        confidence = "high"
    elif confidence_score >= 2:
        confidence = "medium"
    else:
        confidence = "low"

    return GatecampStatus(
        system_id=system_id,
        kill_count=len(recent_kills),
        window_minutes=GATECAMP_WINDOW_SECONDS // 60,
        attacker_corps=list(attacker_corps),
        attacker_ships=list(all_attacker_ships),  # Full fleet composition
        confidence=confidence,
        last_kill=max(k.kill_time for k in recent_kills),
        is_smartbomb_camp=is_smartbomb,
        force_asymmetry=round(avg_attacker_count, 1),
    )


def detect_smartbomb_camp(kills: list[ProcessedKill], attacker_ships: set[int]) -> bool:
    """
    Detect smartbomb camps via ship types + timing patterns.

    Smartbomb camps have characteristic signatures:
    - Known smartbomb platform ships (Rokh, Apocalypse, Machariel, etc.)
    - Multiple distinct victims dying within a tight window (chain smartbombing)
    """
    # Check for characteristic smartbomb ships in attackers
    has_smartbomb_ships = bool(attacker_ships & SMARTBOMB_SHIP_TYPES)

    if not has_smartbomb_ships:
        return False

    # Check timing: 3+ kills within 60s window suggests smartbomb chain
    kill_times = sorted(k.kill_time for k in kills)
    window_duration = (kill_times[-1] - kill_times[0]).total_seconds()

    return window_duration <= SMARTBOMB_WINDOW_SECONDS and len(kills) >= 3
```

**Known Limitations:**

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| System-level only | Cannot identify which gate is camped | ESI killmails lack gate proximity; accept system granularity |
| Natural pipe traffic | High-traffic chokepoints may false-positive | Force asymmetry + attacker consistency checks reduce this |
| Null bubble mechanics | Different patterns than lowsec camps | Future: add security-aware heuristics |
| Smartbomb ship heuristic | May miss camps using unusual platforms | Conservative; can expand ship list based on observed patterns |
| Small gang wipes | 3-person gang dying fast could trigger detection | Force asymmetry check (attackers must outnumber victims 5:1+) mitigates this |

### Filtering Architecture

Filtering happens at two levels with different capabilities:

#### Level 1: RedisQ URL Filters (Coarse, Pre-Fetch)

RedisQ supports limited URL-based filtering. Use these to reduce overall traffic when operational scope is narrow:

```python
# Region filter - most useful for regional operations
url = f"https://zkillredisq.stream/listen.php?queueID={queue_id}&regionID={region_id}"

# These filters are AND-combined
url = f"...&regionID={region_id}&zkb[totalValue]>=100000000"
```

**RedisQ filter limitations:**
- Only simple AND logic
- Limited filter types (region, corp, alliance, value threshold)
- Cannot express OR conditions (e.g., "region A OR region B")
- No system-level filtering at URL level

**Recommendation:** Use region filters only. Keep broad (2-3 regions max) to avoid missing relevant kills. Fine-grained filtering happens post-fetch.

#### Level 2: Post-Fetch Processing Filters (Fine-Grained)

Most filtering should happen after fetching the full killmail:

```python
class KillFilter:
    """Post-fetch kill filtering with full flexibility."""

    def __init__(self, config: FilterConfig):
        self.systems: set[int] = set(config.systems or [])
        self.regions: set[int] = set(config.regions or [])
        self.watch_corps: set[int] = set(config.watch_corporations or [])
        self.watch_alliances: set[int] = set(config.watch_alliances or [])
        self.min_value: int = config.min_value or 0

    def should_process(self, kill: ProcessedKill) -> bool:
        """Determine if kill is relevant for threat cache."""
        # Location filters (OR logic - any match)
        if self.systems and kill.solar_system_id not in self.systems:
            if self.regions:
                kill_region = get_region_for_system(kill.solar_system_id)
                if kill_region not in self.regions:
                    return False
            else:
                return False

        # Value filter
        if kill.total_value < self.min_value:
            return False

        return True

    def is_watched_entity(self, kill: ProcessedKill) -> bool:
        """Check if kill involves a watched corp/alliance (attacker or victim)."""
        if self.watch_corps:
            if kill.victim_corporation_id in self.watch_corps:
                return True
            if self.watch_corps & set(kill.attacker_corps):
                return True

        if self.watch_alliances:
            if kill.victim_alliance_id in self.watch_alliances:
                return True
            if self.watch_alliances & set(kill.attacker_alliances):
                return True

        return False
```

**Filter application flow:**
```
RedisQ → (URL filter: broad region) → Fetch Queue → ESI Fetch → Post-Filter → Threat Cache
                                                                     ↓
                                                              (entity watch → alerts)
```

---

## Integration Points

### 1. Background Poller Service

**File:** `src/aria_esi/services/redisq_poller.py`

**Responsibilities:**
- Maintain persistent connection to RedisQ
- Handle reconnection on failure
- Route kills to processor
- Respect rate limits

**Configuration:**
```yaml
# userdata/config.yaml (or environment)
redisq:
  enabled: true
  queue_id: "aria-{character_id}"
  poll_interval: 10  # seconds (ttw parameter)
  filters:
    regions: [10000002, 10000043]  # The Forge, Domain
    min_value: 10000000  # 10M ISK minimum
  retention_hours: 24
```

### 2. Threat Cache Integration

**File:** `src/aria_esi/mcp/universe/threat_cache.py`

**New Methods:**
```python
class ThreatCache:
    def add_kill(self, kill: ProcessedKill) -> None:
        """Add kill to real-time cache."""

    def get_recent_kills(
        self,
        system_id: int | None = None,
        region_id: int | None = None,
        since_minutes: int = 60,
    ) -> list[ProcessedKill]:
        """Query recent kills with optional filters."""

    def get_gatecamp_status(self, system_id: int) -> GatecampStatus | None:
        """Check for active gatecamp in system."""

    def get_activity_summary(
        self,
        system_ids: list[int],
        window_minutes: int = 60,
    ) -> dict[int, ActivitySummary]:
        """Get kill/activity summary for systems."""
```

### 3. Enhanced Threat Assessment

**File:** `.claude/skills/threat-assessment/SKILL.md`

**Current behavior:**
```
/threat-assessment Tama
→ Uses universe(action="activity") for hourly data
```

**Enhanced behavior:**
```
/threat-assessment Tama
→ Check real-time cache first (if RedisQ enabled)
→ Merge with hourly aggregates for context
→ Flag active gatecamps
→ Show recent kill details
```

**Output Enhancement:**
```
## Threat Assessment: Tama

### Real-Time Intel (Last 60 minutes)
| Time | Victim | Ship | Attackers | Value |
|------|--------|------|-----------|-------|
| 12:45 | [CORP] Pilot | Prowler | 8 (CODE.) | 1.2B |
| 12:42 | [TEST] Pilot | Epithal | 8 (CODE.) | 45M |
| 12:38 | [BRAVE] Pilot | Venture | 8 (CODE.) | 2M |

⚠️ **ACTIVE GATECAMP DETECTED**
- 3 kills in 7 minutes
- Attackers: CODE. (8 pilots)
- Ships: Tornado, Thrasher
- Confidence: High

### Historical Context (Hourly Aggregates)
- Ship kills: 12 (last hour)
- Pod kills: 8
- Jump traffic: 450
```

### 4. Route Integration

**File:** `.claude/skills/route/SKILL.md`

**Enhancement:** Flag systems with active gatecamps on route display.

```
## Route: Jita → Amarr (Safe, 45 jumps)

| System | Sec | Ships | Pods | Jumps | Notes |
|--------|-----|------:|-----:|------:|-------|
| Perimeter | 0.95 | 0 | 0 | 1,200 | Trade hub exit |
| Urlen | 0.87 | 0 | 0 | 340 | |
| ...
| Niarja | 0.50 | 5 | 3 | 890 | ⚠️ **ACTIVE CAMP** (3 kills/10min) |
| ...
```

### 5. New Skill: /gatecamp

**File:** `.claude/skills/gatecamp/SKILL.md`

**Purpose:** Dedicated gatecamp intelligence.

```
/gatecamp Niarja
→ Real-time kill feed for system
→ Attacker analysis (who, ships, typical times)
→ Historical pattern (is this a known camp spot?)

/gatecamp --route Jita Amarr
→ Check all systems on route for active camps
```

---

## API Design

### Extending Existing Actions (Preferred)

Rather than adding new actions, extend the existing `activity` action with a `realtime` flag. This maintains backward compatibility and reduces API surface area.

```python
# Existing behavior (unchanged)
universe(action="activity", systems=["Tama", "Amamake"])
# Returns: {"Tama": {"ship_kills": 12, "pod_kills": 8, "jumps": 450}, ...}

# Enhanced behavior with real-time data
universe(action="activity", systems=["Tama", "Amamake"], include_realtime=True)
# Returns: {
#   "Tama": {
#     "ship_kills": 12,          # Hourly aggregate (ESI)
#     "pod_kills": 8,
#     "jumps": 450,
#     "realtime": {              # New: real-time overlay
#       "kills_10m": 3,
#       "kills_1h": 5,
#       "recent_kills": [...],   # Last 5 kills with details
#       "gatecamp": {            # Present only if detected
#         "confidence": "high",
#         "kill_count": 3,
#         "attacker_corps": [...],
#         "is_smartbomb": false
#       }
#     }
#   }
# }
```

**Gatecamp risk for routes** uses the existing `gatecamp_risk` action, enhanced with real-time data:

```python
# Existing action, now includes real-time when available
universe(action="gatecamp_risk", route=["Jita", "Perimeter", "Urlen", ...])
# Returns enhanced data if poller is active
```

### Graceful Degradation

Skills must transparently fall back to hourly data when real-time is unavailable:

```python
def get_threat_data(system_ids: list[int], include_realtime: bool = True) -> dict:
    """
    Fetch threat data with automatic fallback.

    If RedisQ poller is unhealthy or disabled, silently returns
    hourly-only data without the 'realtime' key.
    """
    hourly = get_hourly_activity(system_ids)

    if not include_realtime:
        return hourly

    if not poller.is_healthy():
        # Silent fallback - no error, just omit realtime key
        return hourly

    realtime = threat_cache.get_recent_activity(system_ids)
    return merge_threat_data(hourly, realtime)
```

**Health check criteria:**
- Poller has received a kill within last 5 minutes, OR
- Poller is actively polling (no errors in last 3 attempts)
- RedisQ not rate-limited (no 429 in last minute)

### CLI Commands

```bash
# Check real-time threat
uv run aria-esi threat Tama --realtime

# Gatecamp status
uv run aria-esi gatecamp Niarja
uv run aria-esi gatecamp --route Jita Amarr

# Start/stop poller (for testing)
uv run aria-esi redisq start
uv run aria-esi redisq stop
uv run aria-esi redisq status
```

---

## Implementation Phases

### Phase 1: Core Infrastructure ✅

**Goal:** Establish RedisQ connection, kill processing pipeline, and gap recovery

**Deliverables:**
- [x] RedisQ poller service with reconnection logic
- [x] Kill fetch queue with rate limiting (avoid N+1 overload)
- [x] ESI killmail fetcher with error handling
- [x] `realtime_kills` SQLite table
- [x] Basic post-fetch filtering (region-based)
- [x] Gap recovery: backfill from zKillboard API on startup
- [x] Manual start/stop via CLI (`aria-esi redisq start/stop/status`)

**Complexity:** Medium

**Implementation notes:**
- RedisQ poller in `src/aria_esi/services/redisq/poller.py`
- Kill fetch queue in `src/aria_esi/services/redisq/fetch_queue.py`
- Kill processing and filtering in `src/aria_esi/services/redisq/processor.py`
- Backfill and gap recovery in `src/aria_esi/services/redisq/backfill.py`
- CLI commands in `src/aria_esi/commands/redisq.py`

### Phase 2: Threat Cache Integration ✅

**Goal:** Make real-time data queryable with gatecamp detection

**Deliverables:**
- [x] `ThreatCache` class with query methods
- [x] Gatecamp detection algorithm (force asymmetry + smartbomb detection)
- [x] `gatecamp_detections` tracking table
- [x] Extend `universe(action="activity")` with `include_realtime` parameter
- [x] Data retention/cleanup job (24h kills, 7d detections)
- [x] Graceful degradation when poller unhealthy

**Complexity:** Medium

**Implementation notes:**
- ThreatCache in `src/aria_esi/services/redisq/threat_cache.py`
- Gatecamp detection uses multi-factor algorithm (force asymmetry, attacker consistency, pod ratio, smartbomb patterns)
- Unit tests in `tests/unit/test_gatecamp_detection.py` and `tests/unit/test_threat_cache.py`
- Schema migration to version 6 adds `gatecamp_detections` table
- `universe(action="gatecamp_risk")` also enhanced with real-time detection

### Phase 3: Skill Enhancements ✅

**Goal:** Surface real-time intel in ARIA skills (pull-based, not push alerts)

**Deliverables:**
- [x] Enhanced `/threat-assessment` with real-time merge
- [x] Route display with active gatecamp flags
- [x] Enhanced `universe(action="gatecamp_risk")` with real-time data
- [x] New `/gatecamp` skill for dedicated camp intel
- [x] Configuration for enabled regions in pilot profile
- [x] CLI commands with `--realtime` flag (`activity-systems`, `gatecamp-risk`, `gatecamp`)
- [x] Integration tests for real-time intel path

**Scope note:** "Alerts" in this phase means information displayed when skills are invoked, not push notifications. Users see gatecamp warnings when they run `/route` or `/threat-assessment`.

**Complexity:** Low-Medium

**Implementation notes:**
- Skill documentation in `.claude/skills/{threat-assessment,route,gatecamp}/SKILL.md`
- PARIA overlay for gatecamp in `personas/paria/skill-overlays/gatecamp.md`
- CLI `--realtime` flag added to `activity-systems` and `gatecamp-risk` commands
- New `gatecamp` CLI command for single-system analysis
- Region configuration documented in `docs/REALTIME_CONFIGURATION.md`
- Unit tests in `tests/unit/test_realtime_integration.py`

### Phase 4: Entity Tracking & Watchlists ✅

**Goal:** Targeted intelligence for specific threats

**Deliverables:**
- [x] Entity watchlist configuration (corps/alliances)
- [x] Watchlist match flagging in kill processing
- [x] `/watchlist` skill for managing tracked entities
- [x] War target integration (auto-add wardec entities)
- [x] Enhanced threat output showing watched entity activity

**Complexity:** Medium

**Implementation notes:**
- EntityWatchlistManager in `src/aria_esi/services/redisq/entity_watchlist.py`
- EntityAwareFilter in `src/aria_esi/services/redisq/entity_filter.py` with O(1) kill matching
- WarTargetSyncer class for ESI war sync with aggressor/defender logic
- Database schema v7 adds `entity_watchlists` and `entity_watchlist_items` tables
- Kill table enhanced with `watched_entity_match` and `watched_entity_ids` columns
- Skill documentation in `.claude/skills/watchlist/SKILL.md`
- CLI commands: `watchlist-list`, `watchlist-show`, `watchlist-create`, `watchlist-add`, `watchlist-remove`, `watchlist-delete`, `sync-wars`, `redisq-watched`
- Unit tests in `tests/unit/test_entity_watchlist.py` and `tests/unit/test_entity_filter.py`

### Phase 5: Push Notifications & Enriched Analysis ✅

**Goal:** Proactive alerts via Discord with optional Claude-enriched analysis

**Status:** Complete.

#### API Investigation: zKillboard 2025 Changes

Before implementing Phase 5B (`/killmail` skill), the following API changes must be accounted for. This investigation was conducted January 2026 against authoritative sources.

**Sources:**
- [zKillboard/RedisQ GitHub](https://github.com/zKillboard/RedisQ) - Official RedisQ documentation
- [zKillboard API (Killmails) Wiki](https://github.com/zKillboard/zKillboard/wiki/API-(Killmails)) - Official API reference
- Commit 53666d1 in this repository - Prior RedisQ fixes

**Timeline of Breaking Changes:**

| Date | Change | Impact |
|------|--------|--------|
| May 2025 | RedisQ endpoint moved from `redisq.zkillboard.com` to `zkillredisq.stream` | URL update required |
| Aug 2025 | `/listen.php` now redirects to `/object.php` with `objectID` parameter | Clients must support HTTP redirects |
| Dec 2025 | Embedded killmail data removed from RedisQ responses | Full killmail must be fetched from ESI separately |

**Current RedisQ Response Format (post-Dec 2025):**
```json
{
  "package": {
    "killID": 12345678,
    "zkb": {
      "locationID": 30002187,
      "hash": "abc123...",
      "fittedValue": 100000000,
      "droppedValue": 50000000,
      "destroyedValue": 150000000,
      "totalValue": 200000000,
      "points": 10,
      "npc": false,
      "solo": false,
      "awox": false,
      "labels": ["lowsec", "ganked"],
      "href": "https://esi.evetech.net/v1/killmails/12345678/abc123.../"
    }
  }
}
```

**Killmail Fetch Flow (Verified):**
1. RedisQ provides `killID` + `zkb.hash`
2. Full killmail fetched from ESI: `GET /killmails/{killmail_id}/{killmail_hash}/`
3. zKillboard API (`https://zkillboard.com/api/killID/{id}/`) provides zkb metadata only—**not** full killmail

**Rate Limits (Unchanged):**
- RedisQ: 1 concurrent request per queueID, 2 req/sec per IP (CloudFlare)
- zKillboard API: "Be polite" (no hard limit documented, but abuse triggers bans)
- ESI: ~30 req/sec with error limit tracking

**Implementation Validation:**
The existing codebase correctly handles these changes:
- `src/aria_esi/services/redisq/poller.py` uses `zkillredisq.stream` with `follow_redirects=True`
- `src/aria_esi/services/redisq/models.py` handles both old and new response formats
- `src/aria_esi/commands/killmails.py` uses correct ESI endpoint format

#### Architecture: Hybrid Approach

The notification system separates **urgency** (Discord) from **depth** (Claude skills):

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  RedisQ Poller  │────▶│  Discord Webhook │────▶│  Player Phone/  │
│  (Background)   │     │  (Immediate)     │     │  Desktop Alert  │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                │
                                ▼
                        Player sees ping
                                │
                                ▼
                        ┌──────────────────┐     ┌─────────────────┐
                        │  /killmail <url> │────▶│  Claude-enriched│
                        │  (On demand)     │     │  Analysis + RP  │
                        └──────────────────┘     └─────────────────┘
```

**Why this wins:**
- Discord handles urgency (mobile ping, overlay, persistent history)
- Claude handles depth (threat analysis, fitting breakdown, persona voice)
- No latency on critical alerts (webhook fires immediately)
- RP enrichment is opt-in, not blocking the critical path

#### Deliverables

**Phase 5A: Discord Webhook Integration**
- [x] Webhook configuration in `userdata/config.json`
- [x] Terse webhook formatter (system, victim, attacker count, zkill link)
- [x] Alert triggers:
  - Watchlist entity activity (from Phase 4)
  - Active gatecamp in configured systems
  - High-value kill in operational area
- [x] Throttling: per-trigger-type tracking, max 1 alert per (system, trigger_type) per 5 minutes
- [x] Quiet hours configuration (optional)
- [x] Webhook queue with Discord rate limiting (5 req/sec max)
- [x] Webhook queue max size: 100 alerts (drop oldest when exceeded during extended Discord outage)
- [x] Extended outage handling: after 3 consecutive failures spanning >5 minutes, pause queue processing and log warning; resume on next successful send
- [x] Retry logic: 3 attempts with exponential backoff on 5xx errors
- [x] Log warning if webhook returns 401/403 (invalid/revoked URL)
- [x] Discord health status in `status()` output: webhook success rate (last 1h), queue depth, last successful send
- [x] Security note in docs: webhook URLs are bearer credentials

**Webhook message format:**
```
⚠️ INTEL: Tama
Proteus down • 8 attackers (Snuffed Out)
12.4B ISK • 2 min ago
https://zkillboard.com/kill/12345678/
```

**Phase 5B: `/killmail` Skill for Enriched Analysis**
- [x] New skill: `/killmail <zkill_url>`
- [x] Accepts zkillboard URL or kill ID
- [x] Fetches full killmail data
- [x] Claude provides:
  - Victim fitting analysis (what went wrong)
  - Attacker fleet composition breakdown
  - Tactical context (known group? war target? camp behavior?)
  - Distance from home system
- [x] Persona overlay support (PARIA voice for pirate pilots)

**Data flow:**
```
1. Parse zkillboard URL → extract kill ID
   - Handles: zkillboard.com/kill/{id}/, zkillboard.com/kill/{id}
   - Also accepts raw kill ID as input
2. Fetch https://zkillboard.com/api/killID/{id}/ → get hash + zkb metadata
   (Note: endpoint is /killID/{id}/, not /kills/killID/{id}/ - see API Investigation above)
3. Fetch ESI GET /killmails/{id}/{hash}/ → full killmail with victim fitting
4. Enrich with SDE:
   - Ship/module names via sde(action="item_info")
   - Corp/alliance names via ESI public endpoints
5. Cross-reference with threat cache (if available):
   - Is this part of an active gatecamp?
   - Is attacker on watchlist?
```

**Example `/killmail` output:**
```
## Kill Analysis: Proteus in Tama

### Victim
Federation Navy Suwayyah [CORP] flying a 12.4B Proteus
Fit: Blaster/AB configuration, weak buffer tank (32k EHP)

### Attackers
8-man Snuffed Out gang:
- 2× Loki (web/point)
- 3× Legion (neut pressure)
- 2× Proteus (DPS)
- 1× Curse (tracking disruption)

### Assessment
Classic low-sec gate trap. Victim was caught on the
Nourvukaiken gate (1 jump from Jita). Snuffed Out has
been active in this pipe for the past hour (3 kills).

⚠️ This is 4 jumps from your home system.
```

**Phase 5C: Extended Analytics (Deferred)**

Evaluate after 5A/5B based on storage impact and pilot demand:
- Known gatecamp spots database (requires 7+ day retention)
- Time-of-day activity patterns
- "Dangerous hours" warnings

#### Configuration

```yaml
# userdata/config.json
{
  "redisq": {
    "enabled": true,
    "notifications": {
      "discord_webhook_url": "https://discord.com/api/webhooks/...",
      "triggers": {
        "watchlist_activity": true,
        "gatecamp_detected": true,
        "high_value_threshold": 1000000000  # 1B ISK
      },
      "throttle_minutes": 5,
      "quiet_hours": {
        "enabled": false,
        "start": "02:00",
        "end": "08:00",
        "timezone": "America/New_York"
      }
    }
  }
}
```

**⚠️ Security Note:** Discord webhook URLs are bearer credentials. Anyone with the URL can post messages to your channel. The `userdata/` directory should already be in `.gitignore`, but take care not to share your config file or include it in logs/screenshots.

#### Alternative Approaches Considered

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| Claude as webhook author | Persona voice, tactical context | Latency, requires active session | Rejected for urgency path |
| Terminal notifications only | Zero dependencies | Passive during gameplay, no history | Supplement only |
| Direct Discord (no Claude) | Simplest, lowest latency | Just another zkill mirror | Insufficient depth |
| Desktop overlay widget | Visible alongside EVE | Significant dev effort, screen real estate | Future consideration |

#### UX Considerations

**Multi-monitor gameplay scenario:**
- Terminal running Claude Code on monitor 1
- 3 EVE clients on monitors 2-4
- Player attention is on EVE clients during active play

**Notification flow:**
1. Kill occurs → RedisQ receives (30-60s)
2. Poller processes → Discord webhook fires (immediate)
3. Player sees Discord notification (phone vibrate, desktop popup, or Discord overlay)
4. If interested: `/killmail <url>` in Claude Code for deep analysis
5. Claude provides enriched intel with persona voice

This keeps critical alerts in the player's attention without requiring focus on the terminal.

**Complexity:** Medium (5A: Low-Medium, 5B: Medium, 5C: High)

**Implementation notes:**
- Webhook queue in `src/aria_esi/services/redisq/webhook_queue.py`
- Throttle manager in `src/aria_esi/services/redisq/webhook_throttle.py`
- Discord formatter in `src/aria_esi/services/redisq/discord_formatter.py`
- Skill documentation in `.claude/skills/killmail/SKILL.md`
- Unit tests in `tests/unit/test_webhook_*.py` and `tests/unit/test_killmail_*.py`
- Quiet hours uses `zoneinfo` (Python 3.9+) for timezone handling
- **DST edge case handling:** For nonexistent times during spring-forward (e.g., 2:30 AM doesn't exist), fold to the next valid time (3:00 AM). For ambiguous times during fall-back (e.g., 1:30 AM occurs twice), use the first occurrence (pre-transition). Implementation should use `datetime.fold` attribute for disambiguation.

---

## Test Strategy

### Unit Tests

**Gatecamp Detection Algorithm:**
```python
# tests/unit/test_gatecamp_detection.py

def test_basic_camp_detection():
    """3+ kills from different victim corps with high force asymmetry = camp."""
    kills = [
        make_kill(victim_corp=1, attacker_count=8, attackers=[100, 101]),
        make_kill(victim_corp=2, attacker_count=8, attackers=[100, 101]),
        make_kill(victim_corp=3, attacker_count=8, attackers=[100, 101]),
    ]
    result = detect_gatecamp(system_id=123, kills=kills)
    assert result is not None
    assert result.confidence in ("medium", "high")
    assert result.force_asymmetry >= 5.0

def test_fleet_fight_not_camp():
    """Single victim corp with similar-sized forces = fleet fight, not camp."""
    kills = [
        make_kill(victim_corp=1, attacker_count=2, attackers=[100]),
        make_kill(victim_corp=1, attacker_count=2, attackers=[100]),
        make_kill(victim_corp=1, attacker_count=2, attackers=[100]),
    ]
    result = detect_gatecamp(system_id=123, kills=kills)
    assert result is None

def test_single_corp_high_asymmetry_is_camp():
    """Single victim corp but 5:1+ force ratio = still a camp (small gang picked off)."""
    kills = [
        make_kill(victim_corp=1, attacker_count=10, attackers=[100, 101]),
        make_kill(victim_corp=1, attacker_count=10, attackers=[100, 101]),
        make_kill(victim_corp=1, attacker_count=10, attackers=[100, 101]),
    ]
    result = detect_gatecamp(system_id=123, kills=kills)
    assert result is not None  # High force asymmetry triggers detection

def test_smartbomb_detection():
    """Kills within 60s with smartbomb ships = smartbomb camp."""
    base_time = datetime.now()
    kills = [
        make_kill(
            kill_time=base_time,
            victim_corp=1,
            attacker_ship_types=[24690],  # Rokh
        ),
        make_kill(
            kill_time=base_time + timedelta(seconds=5),
            victim_corp=2,
            attacker_ship_types=[24690],
        ),
        make_kill(
            kill_time=base_time + timedelta(seconds=10),
            victim_corp=3,
            attacker_ship_types=[24690],
        ),
    ]
    result = detect_gatecamp(system_id=123, kills=kills)
    assert result.is_smartbomb_camp is True

def test_smartbomb_requires_ship_types():
    """Fast kills without smartbomb ships = not smartbomb camp."""
    base_time = datetime.now()
    kills = [
        make_kill(
            kill_time=base_time,
            victim_corp=1,
            attacker_ship_types=[587],  # Rifter (not a smartbomb ship)
        ),
        make_kill(
            kill_time=base_time + timedelta(seconds=5),
            victim_corp=2,
            attacker_ship_types=[587],
        ),
        make_kill(
            kill_time=base_time + timedelta(seconds=10),
            victim_corp=3,
            attacker_ship_types=[587],
        ),
    ]
    result = detect_gatecamp(system_id=123, kills=kills)
    assert result.is_smartbomb_camp is False

def test_confidence_factors():
    """High pod ratio + consistent attackers + force asymmetry = high confidence."""
    kills = [
        make_kill(victim_corp=1, attacker_count=10, is_pod=False),
        make_kill(victim_corp=1, attacker_count=10, is_pod=True),  # Pod kill
        make_kill(victim_corp=2, attacker_count=10, is_pod=False),
        make_kill(victim_corp=2, attacker_count=10, is_pod=True),
        make_kill(victim_corp=3, attacker_count=10, is_pod=False),
    ]
    result = detect_gatecamp(system_id=123, kills=kills)
    assert result.confidence == "high"
```

### Integration Tests

**RedisQ Poller:**
```python
# tests/integration/test_redisq_poller.py

@pytest.mark.integration
async def test_poller_reconnection():
    """Poller reconnects after connection drop."""
    poller = RedisQPoller(queue_id="test-queue")
    await poller.start()

    # Simulate disconnect
    await poller._connection.close()

    # Should auto-reconnect within 30s
    await asyncio.sleep(35)
    assert poller.is_healthy()

@pytest.mark.integration
async def test_rate_limit_backoff():
    """Poller backs off on 429 response."""
    # ... test backoff behavior
```

**Kill Fetch Queue:**
```python
# tests/integration/test_kill_fetch_queue.py

@pytest.mark.integration
async def test_queue_rate_limiting():
    """Queue respects ESI rate limits under load."""
    queue = KillFetchQueue()

    # Enqueue 100 kills rapidly
    for i in range(100):
        await queue.enqueue(QueuedKill(kill_id=i, hash="test"))

    start = time.monotonic()
    await queue.process_queue()
    elapsed = time.monotonic() - start

    # 100 kills at 20/sec = minimum 5 seconds
    assert elapsed >= 4.5  # Allow small margin

@pytest.mark.integration
async def test_queue_drops_oldest_at_capacity():
    """Queue drops oldest kills when at max capacity."""
    queue = KillFetchQueue()
    queue.MAX_QUEUE_SIZE = 10

    # Enqueue 15 kills
    for i in range(15):
        await queue.enqueue(QueuedKill(kill_id=i, hash="test"))

    assert queue.backlog_size == 10
    # Oldest 5 (IDs 0-4) should be dropped
    assert queue._queue[0].kill_id == 5
```

**Gap Recovery:**
```python
# tests/integration/test_gap_recovery.py

@pytest.mark.integration
async def test_backfill_from_zkillboard():
    """Backfill fetches kills from zKillboard API."""
    since = datetime.now() - timedelta(hours=4)
    kills = await backfill_from_zkillboard(
        regions=[10000002],  # The Forge
        since=since,
        max_kills=50,
    )

    assert len(kills) > 0
    assert all(k.kill_time >= since for k in kills)

@pytest.mark.integration
async def test_startup_recovery_triggers_on_gap():
    """Startup recovery runs when gap > 3 hours."""
    # Set last poll to 4 hours ago
    await set_last_poll_time(datetime.now() - timedelta(hours=4))

    with patch("backfill_from_zkillboard") as mock_backfill:
        mock_backfill.return_value = []
        await startup_recovery(config)

        mock_backfill.assert_called_once()
```

### Phase 5 Tests

**Webhook Throttling:**
```python
# tests/unit/test_webhook_throttle.py

def test_throttle_per_trigger_type():
    """Same system, different triggers = separate throttle tracking."""
    throttle = WebhookThrottle(minutes=5)

    # First watchlist alert for Tama
    assert throttle.should_send(system_id=123, trigger="watchlist") is True
    throttle.record(system_id=123, trigger="watchlist")

    # Gatecamp alert for same system should NOT be throttled
    assert throttle.should_send(system_id=123, trigger="gatecamp") is True
    throttle.record(system_id=123, trigger="gatecamp")

    # Second watchlist alert for Tama SHOULD be throttled
    assert throttle.should_send(system_id=123, trigger="watchlist") is False

def test_throttle_expires():
    """Throttle expires after configured duration."""
    throttle = WebhookThrottle(minutes=5)
    throttle.record(system_id=123, trigger="watchlist")

    # Advance time by 6 minutes
    with freeze_time(datetime.now() + timedelta(minutes=6)):
        assert throttle.should_send(system_id=123, trigger="watchlist") is True
```

**Webhook Formatting:**
```python
# tests/unit/test_webhook_format.py

def test_webhook_message_under_discord_limit():
    """Webhook message fits Discord embed limits (2000 chars)."""
    kill = make_kill(
        victim_name="Very Long Pilot Name Here",
        victim_corp="Extremely Long Corporation Name",
        attackers=["Attacker " + str(i) for i in range(50)],
        value=12_400_000_000,
    )
    message = format_webhook_message(kill)
    assert len(message) <= 2000

def test_webhook_format_terse():
    """Webhook message is terse with essential info only."""
    kill = make_kill(system="Tama", victim_ship="Proteus", value=12.4e9)
    message = format_webhook_message(kill)

    assert "Tama" in message
    assert "Proteus" in message
    assert "12.4B" in message or "12,400,000,000" in message
    assert "zkillboard.com" in message
```

**Quiet Hours:**
```python
# tests/unit/test_quiet_hours.py

def test_quiet_hours_timezone_boundary():
    """Quiet hours handles timezone correctly."""
    config = QuietHoursConfig(
        enabled=True,
        start="02:00",
        end="08:00",
        timezone="America/New_York",
    )

    # 3 AM New York = quiet
    with freeze_time("2026-01-25 08:00:00", tz_offset=-5):  # 3 AM EST
        assert is_quiet_hours(config) is True

    # 9 AM New York = not quiet
    with freeze_time("2026-01-25 14:00:00", tz_offset=-5):  # 9 AM EST
        assert is_quiet_hours(config) is False

def test_quiet_hours_dst_transition():
    """Quiet hours handles DST transition correctly."""
    config = QuietHoursConfig(
        enabled=True,
        start="02:00",
        end="08:00",
        timezone="America/New_York",
    )

    # During DST transition, 2 AM might not exist or exist twice
    # Implementation should use zoneinfo for correct handling
    # This test documents expected behavior

def test_quiet_hours_spring_forward():
    """Nonexistent time during spring-forward folds to next valid time."""
    config = QuietHoursConfig(
        enabled=True,
        start="02:30",  # Doesn't exist during spring-forward
        end="08:00",
        timezone="America/New_York",
    )

    # March 10, 2024: 2:30 AM doesn't exist (clocks jump 2:00 → 3:00)
    # Should fold to 3:00 AM, meaning quiet hours start at 3:00
    with freeze_time("2024-03-10 02:45:00", tz_offset=-5):  # 2:45 AM EST (doesn't exist)
        # This time doesn't exist, so we're actually at 3:45 AM EDT
        # which is within quiet hours (3:00 AM - 8:00 AM)
        assert is_quiet_hours(config) is True

def test_quiet_hours_fall_back():
    """Ambiguous time during fall-back uses first occurrence."""
    config = QuietHoursConfig(
        enabled=True,
        start="01:00",
        end="01:45",  # Occurs twice during fall-back
        timezone="America/New_York",
    )

    # Nov 3, 2024: 1:30 AM occurs twice (first in EDT, then in EST)
    # Using fold=0 (first occurrence) for end time
    # First 1:30 AM (EDT): within quiet hours
    # Second 1:30 AM (EST): outside quiet hours (end was first 1:45)
```

**Extended Outage Handling:**
```python
# tests/unit/test_webhook_outage.py

@pytest.mark.asyncio
async def test_webhook_queue_drops_oldest_at_capacity():
    """Queue drops oldest alerts when max size exceeded."""
    queue = WebhookQueue(max_size=100)

    # Fill queue beyond capacity
    for i in range(150):
        await queue.enqueue(make_alert(kill_id=i))

    assert queue.size == 100
    # Oldest 50 (IDs 0-49) should be dropped
    assert queue.peek().kill_id == 50

@pytest.mark.asyncio
async def test_webhook_pauses_after_extended_failure():
    """Queue pauses processing after 3 consecutive failures spanning >5 minutes."""
    queue = WebhookQueue()
    queue._consecutive_failures = 3
    queue._first_failure_time = datetime.now() - timedelta(minutes=6)

    assert queue.is_paused() is True
    assert "Discord unreachable" in queue.pause_reason

@pytest.mark.asyncio
async def test_webhook_resumes_on_success():
    """Queue resumes after successful send."""
    queue = WebhookQueue()
    queue._consecutive_failures = 5
    queue._paused = True

    await queue.record_success()

    assert queue.is_paused() is False
    assert queue._consecutive_failures == 0
```

**Discord Health Status:**
```python
# tests/unit/test_webhook_health.py

def test_status_includes_discord_health():
    """Status output includes Discord webhook health metrics."""
    status = get_unified_status()

    assert "discord" in status
    discord = status["discord"]
    assert "success_rate_1h" in discord  # e.g., 0.95
    assert "queue_depth" in discord       # e.g., 0
    assert "last_successful_send" in discord  # ISO timestamp or None
    assert "is_healthy" in discord        # bool

def test_discord_health_unhealthy_on_low_success_rate():
    """Discord marked unhealthy when success rate < 80%."""
    with patch("get_webhook_metrics") as mock:
        mock.return_value = WebhookMetrics(
            success_count=2,
            failure_count=8,
            queue_depth=50,
            last_success=datetime.now() - timedelta(minutes=30),
        )
        status = get_unified_status()

    assert status["discord"]["is_healthy"] is False
    assert status["discord"]["success_rate_1h"] == 0.2
```

**Webhook Retry Logic:**
```python
# tests/unit/test_webhook_retry.py

@pytest.mark.asyncio
async def test_webhook_retry_on_server_error():
    """Webhook retries with backoff on 5xx errors."""
    attempts = []

    async def mock_post(url, json):
        attempts.append(datetime.now())
        if len(attempts) < 3:
            raise HTTPError(status=503)
        return MockResponse(status=200)

    with patch("aiohttp.ClientSession.post", mock_post):
        await send_webhook_with_retry(url="...", payload={})

    assert len(attempts) == 3
    # Verify exponential backoff
    assert (attempts[1] - attempts[0]).seconds >= 1
    assert (attempts[2] - attempts[1]).seconds >= 2

@pytest.mark.asyncio
async def test_webhook_no_retry_on_client_error():
    """Webhook does not retry on 4xx errors (except 429)."""
    attempts = []

    async def mock_post(url, json):
        attempts.append(1)
        raise HTTPError(status=401)

    with patch("aiohttp.ClientSession.post", mock_post):
        with pytest.raises(WebhookAuthError):
            await send_webhook_with_retry(url="...", payload={})

    assert len(attempts) == 1  # No retry on auth error
```

**Killmail URL Parsing:**
```python
# tests/unit/test_killmail_parsing.py

@pytest.mark.parametrize("url,expected_id", [
    ("https://zkillboard.com/kill/12345678/", 12345678),
    ("https://zkillboard.com/kill/12345678", 12345678),
    ("zkillboard.com/kill/12345678/", 12345678),
    ("12345678", 12345678),  # Raw ID
])
def test_killmail_url_parsing(url, expected_id):
    """Handles various zkillboard URL formats."""
    assert parse_killmail_url(url) == expected_id

def test_killmail_url_invalid():
    """Rejects invalid URLs gracefully."""
    with pytest.raises(InvalidKillmailURL):
        parse_killmail_url("https://evewho.com/pilot/Someone")
```

### Backtesting Framework

To validate gatecamp detection accuracy against the 90% target:

```python
# scripts/backtest_gatecamp_detection.py

def backtest_detection(historical_kills: list[Kill], known_camps: list[CampEvent]):
    """
    Compare algorithm output against manually verified camp events.

    Args:
        historical_kills: Kill data from zKillboard API
        known_camps: Human-verified gatecamp events with timestamps

    Returns:
        Accuracy metrics (precision, recall, F1)
    """
    detected = run_detection_on_historical(historical_kills)

    true_positives = len(detected & known_camps)
    false_positives = len(detected - known_camps)
    false_negatives = len(known_camps - detected)

    precision = true_positives / (true_positives + false_positives)
    recall = true_positives / (true_positives + false_negatives)

    return {
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall),
        "false_positive_rate": false_positives / len(detected),
    }
```

**Verification data sources:**
- r/Eve gatecamp reports (community verification)
- Known camp systems (Niarja, Uedama, Rancer) during peak hours
- Manual sampling of algorithm output (10 random detections/week)

### False Positive Tracking

Detection accuracy is measured via backtesting (see above), not manual verification of live detections. The backtesting framework compares algorithm output against known camp events from community sources.

```sql
-- Track detections for backtesting analysis (not manual verification)
CREATE TABLE gatecamp_detections (
    id INTEGER PRIMARY KEY,
    system_id INTEGER NOT NULL,
    detected_at INTEGER NOT NULL,
    confidence TEXT,
    kill_count INTEGER,
    attacker_corps TEXT,        -- JSON array for post-hoc analysis
    force_asymmetry REAL,
    is_smartbomb INTEGER,
    -- No 'verified' column - backtesting handles accuracy measurement
    created_at INTEGER DEFAULT (strftime('%s', 'now'))
);

CREATE INDEX idx_detections_system_time ON gatecamp_detections(system_id, detected_at);

-- Cleanup: Remove detections older than 7 days (sufficient for weekly backtesting)
DELETE FROM gatecamp_detections WHERE detected_at < strftime('%s', 'now') - 604800;
```

**Accuracy measurement workflow:**
1. Weekly: Export `gatecamp_detections` from past 7 days
2. Cross-reference with known camp systems (Niarja, Uedama, Rancer) and r/Eve reports
3. Run backtesting framework to compute precision/recall
4. Adjust algorithm parameters if metrics drift below targets

---

## Operational Considerations

### Resource Usage

| Resource | Estimate | Notes |
|----------|----------|-------|
| Network | ~1 req/10s to RedisQ, ~1 req/kill to ESI | Low bandwidth |
| CPU | Minimal (parsing JSON) | Negligible |
| Storage | ~1KB per kill × 5000 kills/day = 5MB/day | 24h retention |
| Memory | Kill cache in SQLite, not RAM | Minimal |

**Storage calculation notes:** New Eden averages 25-30k kills daily. With regional filtering (e.g., The Forge + Domain), expect ~5000 kills/day in active regions. Conservative estimate assumes moderate filtering; adjust retention or filtering if storage becomes a concern.

### Failure Modes

| Failure | Impact | Mitigation |
|---------|--------|------------|
| RedisQ down | No real-time data | Fall back to hourly aggregates |
| ESI down | Can't fetch full killmails | Queue kill IDs, retry later |
| 3h+ gap | Missed kills | Acceptable (tactical intel, not audit log) |
| IP ban | No data | Backoff strategy, queue ID rotation |

### Privacy Considerations

- Kill data is public (zKillboard)
- No private pilot data exposed
- Entity tracking is opt-in (pilot configures watchlist)

---

## Alternatives Considered

### Alternative 1: ESI Killmail Polling

**Approach:** Poll ESI directly for character/corporation killmails

**Pros:**
- No third-party dependency
- Full killmail data in one call

**Cons:**
- Only works for kills involving authenticated character
- No galaxy-wide awareness
- Higher ESI cache times

**Decision:** Rejected. RedisQ provides broader coverage.

### Alternative 2: WebSocket Connection

**Approach:** Use zKillboard's WebSocket feed instead of RedisQ

**Pros:**
- Lower latency (push vs pull)
- No polling overhead

**Cons:**
- More complex connection management
- Requires persistent connection
- RedisQ specifically designed for simplicity

**Decision:** Rejected. RedisQ's simplicity outweighs WebSocket benefits.

### Alternative 3: Historical Kill Scraping

**Approach:** Periodically fetch recent kills from zKillboard API

**Pros:**
- Simpler implementation
- No queue state to manage

**Cons:**
- Higher latency (batch vs stream)
- Miss kills during gaps
- Rate limiting concerns

**Decision:** Rejected. RedisQ's queue model is more robust.

---

## Design Decisions

The following questions have been resolved:

1. **Default enabled or opt-in?**
   - **Decision:** Disabled by default, enable in config
   - **Rationale:** Conservative approach; users explicitly opt in to background polling

2. **Queue ID strategy?**
   - **Decision:** Per-installation (`aria-{uuid}`)
   - **Rationale:** Simpler than per-pilot; one queue serves all pilots in the installation
   - **Multi-pilot handling:** Filter configuration is the union of all pilots' operational regions. This is broader than any single pilot needs but ensures no relevant kills are missed. Post-fetch filtering narrows to active pilot's specific systems.
   - **Implementation:**
     ```python
     # On startup, compute union of all pilot operational regions
     def get_combined_filter_regions(registry: PilotRegistry) -> set[int]:
         regions = set()
         for pilot in registry.pilots:
             if pilot.operations_config:
                 regions.update(pilot.operations_config.regions)
         return regions
     ```

3. **Filter granularity?**
   - **Decision:** Broad at RedisQ level (regions), fine-grained post-fetch (systems, entities)
   - **Rationale:** RedisQ filters are limited; post-fetch processing has full flexibility

4. **Alert mechanism?**
   - **Decision:** Hybrid approach—Discord webhooks for urgency, Claude skills for depth
   - **Phase 3 scope:** Pull-based alerts displayed when skills are invoked (not push notifications)
   - **Phase 5 scope:** Discord webhooks fire immediately for configured triggers; `/killmail` skill provides on-demand enriched analysis with persona voice
   - **Rationale:** Separating urgency from depth optimizes for multi-monitor gameplay where terminal is passive during active play

5. **Merge strategy with hourly data?**
   - **Decision:** Always merge (real-time for recent, hourly for trend)
   - **Rationale:** Richer context; real-time shows "what's happening now," hourly shows "what usually happens"

---

## Success Criteria

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Kill ingestion latency | <2 minutes from occurrence | Timestamp comparison (kill_time vs created_at) |
| Gatecamp detection precision | 85%+ | Backtesting framework against known camp events |
| Gatecamp detection recall | 90%+ | Backtesting against known camp events |
| Data availability | 99%+ uptime when enabled | Poller health monitoring |
| Gap recovery success | 95%+ kills recovered for gaps <6h | Compare backfill results to zKillboard API totals |
| Queue backlog (normal) | <50 kills | Monitoring; indicates fetch rate keeps up |
| Queue backlog (peak) | <500 kills | Monitoring during large events |
| Resource overhead | <5% CPU, <50MB memory | System monitoring |
| Graceful degradation | 100% silent fallback | Integration tests |
| Discord webhook success rate | 95%+ when Discord reachable | `status()` health metrics |
| Webhook alert latency | <5 seconds from kill processing | Timestamp comparison (processed_at vs webhook_sent_at) |

---

## Summary

| Aspect | Current | Proposed |
|--------|---------|----------|
| **Data freshness** | 1 hour | ~1 minute |
| **Data source** | ESI aggregates only | ESI + zKillboard RedisQ |
| **Gatecamp detection** | Manual inference | Multi-factor algorithm (force asymmetry, attacker consistency, pod ratio) |
| **Smartbomb detection** | Not available | Automatic via ship type + timing analysis |
| **Entity tracking** | Not available | Corp/alliance watchlists with war target sync |
| **Route safety** | Historical only | Real-time camp warnings with confidence levels |
| **Push notifications** | Not available | Discord webhooks (immediate) + `/killmail` enrichment (on-demand) |
| **Notification health** | N/A | Discord webhook health in `status()` output with success rate, queue depth, pause state |
| **Gap recovery** | N/A | Automatic backfill from zKillboard API |
| **Graceful degradation** | N/A | Silent fallback to hourly data; webhook queue pauses during Discord outage |
| **Resource usage** | None | Minimal (~5MB/day storage, background poller) |

RedisQ integration transforms ARIA from a **historical analyst** into a **real-time tactical assistant**. Pilots operating in dangerous space gain minute-by-minute awareness of threats, enabling informed decisions about routes, timing, and risk. The phased approach allows incremental delivery of value while building toward comprehensive intel capabilities.

**Key design principles:**
1. **Extend, don't duplicate** - Real-time data augments existing `activity` action rather than adding parallel APIs
2. **Silent degradation** - Skills never fail due to RedisQ unavailability; they simply return hourly-only data
3. **Rate-limit aware** - Kill fetch queue prevents ESI overload during high-activity events
4. **Gap resilient** - Automatic backfill recovers intel after extended downtime
5. **Measurable accuracy** - Backtesting framework ensures detection quality meets targets
6. **Urgency vs depth** - Discord webhooks handle time-critical alerts; Claude skills provide enriched analysis on-demand
7. **Gameplay-aware UX** - Notification design optimized for multi-monitor setups where terminal is passive during active play
8. **Bounded failure modes** - Webhook queue has max size; extended outages pause processing rather than accumulating unbounded backlog
