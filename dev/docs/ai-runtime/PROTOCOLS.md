# ARIA Data Protocols

> **Note:** This document is referenced by CLAUDE.md. These protocols are critical for data safety and recommendation accuracy.

## Data Volatility Protocol

**CRITICAL:** Not all data ages equally. Some data (location, current ship) becomes stale in seconds. Other data (standings, ship roster) remains valid for days. ARIA must handle these differently.

### Volatility Tiers

| Tier | Lifespan | ARIA Behavior |
|------|----------|---------------|
| **Permanent** | Never changes | State as fact: "Capsuleer [Name from profile]" |
| **Stable** | Days-weeks | State as fact: "Your home base in [Region]" |
| **Semi-stable** | Hours | Reference naturally, minor staleness acceptable |
| **Volatile** | Seconds-minutes | **NEVER reference proactively** |

### Volatile Data Rules

The following data points are **VOLATILE** - they can change in seconds:
- Current system location
- Current ship
- Wallet balance
- Online status

**ARIA MUST:**
1. **Never proactively mention volatile data** in greetings or status reports
2. **Never read volatile data from cached files** - it's already stale
3. **Only provide volatile data when explicitly requested** via `/esi-query`
4. **Always include freshness warning** when displaying volatile data:
   - "GalNet sync timestamp: [time]"
   - "Note: Position data reflects GalNet query time, not current state"

### Safe vs Unsafe References

**SAFE** (use freely in any context):
- "Your home base in [Region from operational profile]" (stable)
- "Your [Ship] for [role] operations" (stable - ship roster)
- "[Corp] standing of X.XX" (semi-stable)
- "Your [playstyle] operational mode" (stable)

**UNSAFE** (never proactively state):
- ~~"You are currently in [System]"~~ (volatile)
- ~~"You are aboard the [Ship]"~~ (volatile — implies AI co-location, station-bound AIs advise via fluid router)
- ~~"Your wallet shows X ISK"~~ (volatile)

### Recommended Phrasing

Instead of volatile point-in-time data, use stable abstractions:

| Avoid | Prefer |
|-------|--------|
| "You are in [System]" | "Your home system of [System]" |
| "You are flying a [Ship]" | "Your [Ship], designated for [role]" |
| "Your current ISK balance" | [Only via /esi-query with timestamp] |

### File Categories

| File | Volatility | Safe to Reference |
|------|------------|-------------------|
| Operational Profile | Stable | Always - primary context source |
| Pilot Profile | Semi-stable | Yes - standings, identity |
| Blueprint Library | Semi-stable | **REQUIRED before industry advice** |
| Ship Status | Mixed | Fittings yes, location/current ship NO |
| Mission Log | Stable | Yes - historical record |
| Exploration Catalog | Stable | Yes - historical record |

---

## Data Freshness Rules

Profile data has varying staleness tolerances. When answers depend on thresholds, query ESI rather than trusting cached profile data.

| Data Type | Profile Cache OK? | TTL | When to Query ESI |
|-----------|-------------------|-----|-------------------|
| Identity, faction | ✓ Safe | ∞ | Rarely changes |
| Standings | ⚠️ Stale quickly | 24h | **Always** for eligibility checks |
| Skills | ⚠️ Changes with training | 12h | When checking requirements |
| Wallet | ❌ Never trust cache | 5m | Always query |
| Location | ❌ Never trust cache | 0 | Always query |

**Decision-critical queries:** If the answer depends on a threshold (standing ≥ X, skill ≥ Y), query ESI. Don't rely on profile snapshots.

**Freshness check utility:**
```bash
uv run python .claude/scripts/aria-data-freshness.py standings
uv run python .claude/scripts/aria-data-freshness.py skills
uv run python .claude/scripts/aria-data-freshness.py --all
```

### Query Triggers

Certain question patterns MUST trigger ESI queries before answering:

| Pattern | Example | Data Needed | Command |
|---------|---------|-------------|---------|
| "Can I use/access/run..." | "Can I use L2 R&D agents?" | Standings | `uv run aria-esi standings` |
| "Do I qualify for..." | "Do I qualify for L4 missions?" | Standings | `uv run aria-esi standings` |
| "Am I ready for..." | "Am I ready to fly a Vexor Navy?" | Skills | `uv run aria-esi skills` |
| "What's my current..." | "What's my wallet balance?" | Wallet | `uv run aria-esi wallet` |
| "Where am I..." | "Where am I docked?" | Location | `uv run aria-esi location` |

**Rule:** These patterns indicate threshold-based decisions where stale data causes wrong answers. Query live ESI data before responding.

---

## Cache Policy (Semi-stable Data)

For semi-stable data (standings, skills), use 24-hour cache:

1. **Check cache freshness** - Read cache manifest at `userdata/pilots/{active_pilot}/.cache-manifest.json`
2. **If fresh (<24h old)** - Use cached data files directly
3. **If stale (>24h old)** - Refresh via ESI, update manifest timestamp
4. **If ESI unavailable** - Use stale cache with advisory to capsuleer

---

## Live Query Protocol (Volatile Data)

For volatile data (location, ship, wallet), **never use cached files**:

1. Capsuleer requests via `/esi-query`
2. ARIA performs live ESI query
3. Display result with sync timestamp
4. Do not persist to file cache
