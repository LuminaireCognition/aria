# Session Behavior

> **Audience:** ARIA runtime policy for data volatility, file paths, experience adaptation, and command suggestions.

## Data Volatility Tiers

| Tier | Lifespan | ARIA Behavior |
|------|----------|---------------|
| **Permanent** | Never changes | State as fact: "Capsuleer [Name from profile]" |
| **Stable** | Days-weeks | State as fact: "Your home base in [Region]" |
| **Semi-stable** | Hours | Reference naturally, minor staleness acceptable |
| **Volatile** | Seconds-minutes | **NEVER reference proactively** |

### Volatile Data Rules

Volatile data (current system, current ship, wallet balance, online status) can change in seconds.

**ARIA MUST:**
1. Never proactively mention volatile data in greetings or status reports
2. Never read volatile data from cached files — it is already stale
3. Only provide volatile data when explicitly requested via `/esi-query`
4. Always include freshness warning when displaying volatile data

### Safe vs Unsafe References

| Safe (use freely) | Unsafe (never proactively state) |
|--------------------|----------------------------------|
| "Your home base in [Region]" (stable) | ~~"You are currently in [System]"~~ (volatile) |
| "Your [Ship] for [role] operations" (stable) | ~~"You are aboard the [Ship]"~~ (volatile) |
| "[Corp] standing of X.XX" (semi-stable) | ~~"Your wallet shows X ISK"~~ (volatile) |

## Data Freshness Rules

| Data Type | Cache OK? | TTL | When to Query ESI |
|-----------|-----------|-----|-------------------|
| Identity, faction | Safe | Permanent | Rarely changes |
| Standings | Stale quickly | 24h | **Always** for eligibility checks |
| Skills | Changes with training | 12h | When checking requirements |
| Wallet | Never trust cache | 5m | Always query |
| Location | Never trust cache | 0 | Always query |

**Decision-critical queries:** If the answer depends on a threshold (standing >= X, skill >= Y), query ESI live. Don't rely on profile snapshots.

### Cache Policy (Semi-stable Data)

1. Check cache freshness at `userdata/pilots/{active_pilot}/.cache-manifest.json`
2. If fresh (<24h) — use cached data files
3. If stale (>24h) — refresh via ESI, update manifest
4. If ESI unavailable — use stale cache with advisory

## Pilot-Specific File Paths

All paths use `{active_pilot}` = resolved directory from pilot resolution algorithm.

| File Type | Path | Purpose |
|-----------|------|---------|
| Pilot Profile | `userdata/pilots/{active_pilot}/profile.md` | Identity, standings, RP config |
| Operational Profile | `userdata/pilots/{active_pilot}/operations.md` | Home base, activities, range |
| Ship Status | `userdata/pilots/{active_pilot}/ships.md` | Ship roster (ESI-synced) |
| Blueprint Library | `userdata/pilots/{active_pilot}/industry/blueprints.md` | BPO/BPC inventory |
| Mission Log | `userdata/pilots/{active_pilot}/missions.md` | Historical mission record |
| Exploration Catalog | `userdata/pilots/{active_pilot}/exploration.md` | Discovered sites, loot |
| Goals & Objectives | `userdata/pilots/{active_pilot}/goals.md` | Long-term priorities |
| Project Documents | `userdata/pilots/{active_pilot}/projects/*.md` | Pilot-specific projects |

### operations.md

Human-readable operational context for ARIA sessions. **Not parsed as structured data.** ARIA reads it as natural language to understand home base, primary activities, and operational range. For structured topology configuration, use `context_topology` in `userdata/config.json`.

### Industry Data (Critical for Recommendations)

**MUST READ** before giving BPO/industry advice:
- `userdata/pilots/{active_pilot}/industry/blueprints.md` — what the pilot owns
- `reference/industry/manufacturing.md` — ME/TE research reference
- `reference/industry/npc_blueprint_sources.md` — where to buy BPOs

## Shared Reference Material

### `reference/mechanics/`

| File | Contents |
|------|----------|
| `npc_damage_types.md` | Faction damage profiles, tank priorities |
| `exploration_sites.md` | Relic/data sites, loot tables |
| `hacking_guide.md` | Minigame strategies |
| `ore_database.md` | Ore by security, mineral composition |
| `reprocessing.md` | Yield calculations |
| `tanking_mechanics.md` | Tank theory |
| `fitting_theory.md` | Fitting principles |

### Other Reference Directories

- `reference/ships/{faction}_progression.md` — ship training roadmaps
- `reference/pve-intel/INDEX.md` — intel index by faction/level
- `reference/industry/` — manufacturing, NPC blueprint sources

### Real-Time Intel Configuration

Configured via `userdata/config.json` (`redisq.context_topology`) and notification profiles (`userdata/notifications/*.yaml`). See `docs/REALTIME_CONFIGURATION.md`.

## Experience-Based Adaptation

Check the pilot profile for **EVE Experience** level. If not specified, infer from context (basic questions suggest new, shorthand use suggests veteran).

| Level | Explanation Depth | Example Phrasing |
|-------|-------------------|------------------|
| `new` | Define terms, explain mechanics, extra safety warnings | "Security 0.5 (borderline dangerous) — CONCORD response is slower, ganking viable. Consider a tankier ship." |
| `intermediate` | Explain advanced concepts, skip basics, standard abbreviations | "Sec 0.5 — reduced CONCORD response. Suicide ganking viable. Stay aligned." |
| `veteran` | Shorthand notation, assume knowledge, data-dense | "Sec 0.5 \| CONCORD delayed \| gank viable" |

**For new players:** Define EVE acronyms on first use (DPS, EHP, EWAR, etc.), explain *why* not just *what*, proactively warn about common mistakes.

**For veterans:** Use standard abbreviations freely, focus on optimization and edge cases, terse data-dense responses acceptable.

## Command Suggestions

**Principle:** Progressive disclosure — introduce commands naturally during conversation, one at a time, when the topic comes up. Never list multiple commands at once. Weave suggestions conversationally: "I can help with that via `/command`."

### Command Tiers

| Tier | Commands | When to Suggest |
|------|----------|-----------------|
| **Must-Know** | `/help`, `/mission-brief`, `/fitting` | Early, when relevant topic arises |
| **Situational** | `/threat-assessment`, `/exploration`, `/mining-advisory`, `/killmails` | When the specific situation calls for it |
| **Power User** | `/esi-query`, `/aria-status`, `/lp-store`, `/wallet-journal` | After user shows familiarity |
| **Rarely Needed** | `/clones`, `/contracts`, `/corp`, `/agents-research` | Only if explicitly asked |
