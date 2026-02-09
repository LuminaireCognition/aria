# Local Intel & Orient Feature Proposal

**Status:** Draft
**Author:** ARIA Development
**Date:** 2026-01-26
**Branch:** `feature/orient-local-intel`

## Executive Summary

Pilots who enter unknown space via wormholes or filaments need immediate situational awareness. Currently, gathering this intel requires 4-5 separate queries that must be mentally correlated. This proposal introduces a unified `/orient` skill and supporting `local_area` MCP dispatcher action to provide actionable tactical orientation in a single command.

## The Scenario

A pilot takes a wormhole or filament and lands in unknown null-sec space. They need immediate answers:

- What's the threat picture around me?
- Where are the quiet systems for stealth mining?
- Where are the ratting banks that attract PvP?
- What are my escape routes?
- What's the local "weather" for the next few jumps?

**Current state:** Pilot must make 4-5 separate queries and mentally correlate results.
**Goal:** Single command provides actionable tactical orientation.

## Current Capabilities

### Topology System (Static, Configuration-Driven)

| Component | Purpose | Status |
|-----------|---------|--------|
| Geographic Layer | Home/hunting/transit systems | Mature |
| Entity Layer | Corp/alliance/war targets | Mature |
| Route Layer | Named logistics corridors | Mature |
| Asset Layer | Structures and offices | Mature |
| Pattern Layer | Gatecamp/spike escalation | Mature |
| Interest Calculator | Multi-layer scoring | Mature |

**Limitation:** Topology is pre-configured around known operational areas. It doesn't help when dropped into completely unknown space.

### Activity System (Dynamic, Real-Time)

| Tool | Purpose | Status |
|------|---------|--------|
| `activity` | Kill/jump counts for systems | Mature |
| `hotspots` | High-activity nearby systems | Mature |
| `gatecamp_risk` | Chokepoint analysis on route | Mature |
| `nearest` | Find systems by predicates | Mature |
| `search` | Multi-criteria system search | Mature |
| `fw_frontlines` | Faction Warfare status | Mature |

**Limitation:** Tools are isolated. No single "orient me" command. Cannot combine activity + security + distance in one query.

## Gap Analysis

### 1. Situational Briefing
- No consolidated "what's around me" command
- Must call hotspots, nearest, activity, borders separately
- No unified threat/opportunity picture

### 2. Activity-Based System Ranking
- Cannot query: "safest systems within 10 jumps"
- Cannot query: "most active ratting pocket nearby"
- Activity is not a search predicate for nearest/search tools

### 3. Dynamic Topology (Ad-Hoc Interest Map)
- Topology requires pre-configuration
- Cannot build ephemeral interest map around current location
- No "temporary home" concept for explorers

### 4. Opportunity Detection
- Cannot identify ratting banks (high NPC kills = targets)
- Cannot find quiet corners (low activity = stealth ops)
- Cannot suggest optimal positioning based on local patterns

### 5. Escape Route Awareness
- No automatic identification of nearest safe harbor
- No "path to nearest NPC station" query
- Border system detection works, but not integrated into briefing

## Proposed Solution

### Phase 1: New MCP Dispatcher Action

```python
universe(action="local_area", origin="ZZ-TOP", max_jumps=10, ...)
```

Returns consolidated view:

```json
{
  "origin": "ZZ-TOP",
  "security": -0.4,
  "region": "Vale of the Silent",
  "constellation": "...",

  "threat_summary": {
    "level": "MEDIUM",
    "kills_10j": 47,
    "pods_10j": 12,
    "active_camps": ["X-7OMU gate"]
  },

  "hotspots": [
    {"system": "X-7OMU", "kills": 23, "jumps": 2, "reason": "active camp"},
    {"system": "PZMA-E", "kills": 15, "jumps": 4, "reason": "ratting bank"}
  ],

  "quiet_zones": [
    {"system": "R-BGSU", "kills": 0, "jumps": 8, "npc_kills": 3},
    {"system": "JI-LGM", "kills": 0, "jumps": 6, "npc_kills": 0}
  ],

  "ratting_banks": [
    {"system": "PZMA-E", "npc_kills": 847, "jumps": 4},
    {"system": "H-PA29", "npc_kills": 523, "jumps": 7}
  ],

  "escape_routes": [
    {"destination": "Jita", "jumps": 34, "via": "low-sec"},
    {"destination": "nearest_npc_station", "jumps": 12, "system": "..."}
  ],

  "borders": [
    {"system": "...", "type": "null_to_low", "jumps": 8}
  ]
}
```

### Phase 2: Activity-Aware Search Predicates

Extend `universe(action="nearest", ...)` with:

| Parameter | Type | Description |
|-----------|------|-------------|
| `max_kills` | int | Maximum ship kills (last hour) |
| `min_npc_kills` | int | Minimum NPC kills (ratting indicator) |
| `activity_level` | str | "none", "low", "medium", "high" |

Example: "Find safest staging within 15 jumps"
```python
universe(action="nearest", origin="ZZ-TOP", max_jumps=15,
         security_min=-0.5, max_kills=2, limit=5)
```

### Phase 3: `/orient` Skill

User says: "I just landed in ZZ-TOP via wormhole, orient me"

ARIA executes:
1. Get current location (or use provided system)
2. `universe(action="local_area", origin="ZZ-TOP", max_jumps=10)`
3. Format tactical briefing

**Sample Output:**
```
═══════════════════════════════════════════════════════════════
ARIA LOCAL ORIENTATION - ZZ-TOP (Vale of the Silent)
───────────────────────────────────────────────────────────────
THREAT LEVEL: MEDIUM
  47 ship kills within 10 jumps (last hour)
  Active gatecamp detected: X-7OMU (2 jumps)

AVOID (High Activity)
│ System   │ Jumps │ Kills │ Threat          │
│ X-7OMU   │ 2     │ 23    │ Gatecamp        │
│ PZMA-E   │ 4     │ 15    │ Ratting traffic │

QUIET ZONES (Stealth Ops)
│ System   │ Jumps │ Kills │ NPC Kills │
│ R-BGSU   │ 8     │ 0     │ 3         │
│ JI-LGM   │ 6     │ 0     │ 0         │

RATTING BANKS (Content)
│ System   │ Jumps │ NPC Kills │ Potential      │
│ PZMA-E   │ 4     │ 847       │ Active ratters │
│ H-PA29   │ 7     │ 523       │ Quiet pocket   │

ESCAPE ROUTES
  Nearest low-sec: 8 jumps via YZ-LQL
  Nearest NPC station: 12 jumps
═══════════════════════════════════════════════════════════════
```

## Implementation Roadmap

### Step 1: Add activity predicates to nearest/search tools

**File:** `src/aria_esi/mcp/tools_nearest.py`
**Effort:** Small - extend existing predicate system

Add parameters:
- `max_kills: int | None`
- `min_npc_kills: int | None`
- `activity_level: str | None`

Integration point: Predicate evaluation in BFS traversal.

### Step 2: Create `local_area` dispatcher action

**File:** `src/aria_esi/mcp/dispatchers/universe.py`
**Effort:** Medium - orchestrates existing tools

Dependencies:
- Activity cache (`get_activity_cache()`)
- Hotspots (`_hotspots()`)
- Borders (`_borders()`)
- Search/nearest (`_nearest()`)
- Gatecamp detection (threat_cache)

Algorithm:
1. BFS expand from origin to max_jumps
2. Fetch activity for all systems in radius
3. Classify: hotspots (high kills), quiet zones (zero kills), ratting banks (high NPC)
4. Find security borders (null→low, low→high transitions)
5. Compute escape routes (nearest low-sec, nearest NPC station)
6. Aggregate threat summary

### Step 3: Add NPC station lookup

**File:** `src/aria_esi/mcp/tools_nearest.py`
**Effort:** Small - need station data from SDE

New predicate: `has_npc_station: bool`

May require SDE enhancement for station ownership data (distinguish NPC vs player stations).

### Step 4: Create `/orient` skill

**File:** `.claude/skills/orient/SKILL.md`
**Effort:** Small - mostly formatting, calls local_area

Skill metadata:
```yaml
name: orient
triggers:
  - "orient me"
  - "what's around me"
  - "local intel"
  - "situational awareness"
requires_pilot: false  # Can work with just a system name
```

### Step 5: CLI equivalent

**Command:** `uv run aria-esi orient <system> [--max-jumps N]`
**File:** `src/aria_esi/cli/commands/orient.py`
**Effort:** Small

## Data Sources

### Already Available

| Data | Source | Cache TTL |
|------|--------|-----------|
| Ship/pod kills per system | ESI `/universe/system_kills/` | 10 min |
| NPC kills per system | ESI `/universe/system_kills/` | 10 min |
| Ship jumps per system | ESI `/universe/system_jumps/` | 10 min |
| System security status | SDE/graph cache | Static |
| Border system index | Pre-computed | Static |
| Gatecamp detection | threat_cache (RedisQ) | Real-time |
| Region/constellation mapping | SDE | Static |

### May Need Enhancement

| Data | Source | Notes |
|------|--------|-------|
| NPC station locations | SDE | Need station ownership query |
| Nearest NPC null-sec station | Algorithm | New BFS predicate |
| Regional sovereignty | ESI | Optional, for "friendly space" |

## API Design

### `universe(action="local_area", ...)`

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `origin` | str | required | Starting system name |
| `max_jumps` | int | 10 | Search radius |
| `include_realtime` | bool | true | Include gatecamp detection |
| `hotspot_threshold` | int | 5 | Min kills for hotspot |
| `quiet_threshold` | int | 0 | Max kills for quiet zone |
| `ratting_threshold` | int | 100 | Min NPC kills for ratting bank |

**Response Schema:**

```python
@dataclass
class LocalAreaResult:
    origin: str
    origin_id: int
    security: float
    region: str
    constellation: str

    threat_summary: ThreatSummary
    hotspots: list[SystemActivity]      # High PvP activity
    quiet_zones: list[SystemActivity]   # Zero/low PvP
    ratting_banks: list[SystemActivity] # High NPC kills
    escape_routes: list[EscapeRoute]
    borders: list[SecurityBorder]

    systems_scanned: int
    cache_age_seconds: int
    realtime_healthy: bool

@dataclass
class ThreatSummary:
    level: str  # "LOW", "MEDIUM", "HIGH", "EXTREME"
    total_kills: int
    total_pods: int
    active_camps: list[str]  # System names with detected camps

@dataclass
class SystemActivity:
    system: str
    system_id: int
    security: float
    jumps: int  # Distance from origin
    ship_kills: int
    pod_kills: int
    npc_kills: int
    ship_jumps: int
    reason: str | None  # "gatecamp", "ratting bank", etc.

@dataclass
class EscapeRoute:
    destination: str
    destination_type: str  # "lowsec", "highsec", "npc_station"
    jumps: int
    via_system: str | None  # First waypoint

@dataclass
class SecurityBorder:
    system: str
    system_id: int
    jumps: int
    border_type: str  # "null_to_low", "low_to_high"
    adjacent_system: str
```

## Success Criteria

Pilot lands in unknown null-sec and asks "orient me":

| Criterion | Target |
|-----------|--------|
| Response time | < 3 seconds |
| Threat assessment accuracy | Identifies active camps |
| Quiet zone identification | Systems with 0 kills shown |
| Ratting bank detection | High NPC kill systems shown |
| Escape route calculation | Nearest low-sec/station found |
| Data freshness | < 10 minutes stale |

## Testing Strategy

### Unit Tests

- `test_local_area_basic`: Verify response structure
- `test_local_area_threat_levels`: Verify threat classification thresholds
- `test_local_area_quiet_zones`: Verify zero-kill systems identified
- `test_local_area_ratting_banks`: Verify NPC kill threshold
- `test_local_area_escape_routes`: Verify border detection

### Integration Tests

- `test_local_area_real_system`: Test with known EVE system
- `test_local_area_null_sec`: Test from null-sec origin
- `test_local_area_cache_behavior`: Verify caching works

### Manual Testing

1. Use filament to enter random null-sec
2. Run `/orient` or `uv run aria-esi orient <system>`
3. Verify intel matches in-game observations
4. Time response latency

## Future Extensions

### Phase 4: Sovereignty Integration

Add alliance sovereignty data to identify:
- Friendly space (blue standings)
- Hostile space (war targets)
- NPC null-sec (always accessible stations)

### Phase 5: Historical Patterns

Track activity over time to identify:
- Peak activity hours
- Regular gatecamp times
- Quiet windows for operations

### Phase 6: Wormhole Integration

If origin is a wormhole system:
- Show wormhole class and effects
- Identify static connections
- Adjust threat assessment for J-space

## File Changes Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `src/aria_esi/mcp/dispatchers/universe.py` | Modify | Add `local_area` action |
| `src/aria_esi/mcp/tools_nearest.py` | Modify | Add activity predicates |
| `src/aria_esi/mcp/models.py` | Modify | Add response dataclasses |
| `src/aria_esi/cli/commands/orient.py` | New | CLI command |
| `.claude/skills/orient/SKILL.md` | New | Skill definition |
| `.claude/skills/_index.json` | Modify | Register skill |
| `tests/mcp/test_local_area.py` | New | Unit tests |

## References

- [CONTEXT_AWARE_TOPOLOGY_PROPOSAL.md](./CONTEXT_AWARE_TOPOLOGY_PROPOSAL.md) - Topology layer architecture
- [REDISQ_REALTIME_INTEL_PROPOSAL.md](./REDISQ_REALTIME_INTEL_PROPOSAL.md) - Real-time gatecamp detection
- `docs/CONTEXT_AWARE_TOPOLOGY.md` - Current topology documentation
