# Sovereignty & Territory Data Proposal

**Status:** PROPOSED (2026-02-04)
**Related:** `/hunting-grounds`, `/threat-assessment`, `/orient`, `universe()` MCP dispatcher

---

## Executive Summary

Add sovereignty and coalition territory awareness to ARIA's navigation and intelligence systems. Currently, pilots can ask "is this system safe?" but cannot ask "am I in Goon space?" or "route me through ratting systems avoiding PVP hotspots."

**Primary value:** Enable territory-aware routing and hunting ground analysis for null-sec operations.

**Data sources:**
- ESI `/sovereignty/map/` - System → Alliance mapping (authoritative, dynamic)
- ESI `/sovereignty/structures/` - TCU/IHub data for vulnerability analysis
- Manual YAML - Alliance → Coalition mapping (community-maintained)
- ESI Faction Warfare endpoints - System → Faction occupancy (dynamic)

---

## Problem Statement

### Current Limitations

ARIA's navigation tools understand:
- System security status (high/low/null)
- Kill/jump activity (hourly aggregates + real-time via RedisQ)
- Route optimization (shortest/safe/unsafe)

ARIA does **not** understand:
- Which alliance controls a system
- Coalition boundaries (Imperium, PanFam, etc.)
- Ratting activity patterns by territory
- Faction Warfare frontlines and contested systems

### Real Scenarios Where This Fails

**Scenario 1: Filament into Unknown Space**
> Pilot filaments into null-sec: "Where am I?"
> ARIA shows security, gates, recent kills.
> Cannot tell pilot they're in Delve (Imperium space) surrounded by krabbing Goons.

**Scenario 2: Hunting Route Planning**
> Pilot asks: "Plan me a route through ratting systems"
> ARIA can find high-NPC-kill systems but cannot distinguish:
> - Active ratting (targets) vs. recent fleet fight (danger)
> - Renter space (soft targets) vs. staging systems (hardened)

**Scenario 3: Faction Warfare Intel**
> Pilot in FW asks: "Which systems are contested?"
> ARIA has no FW occupancy data.

---

## Data Architecture

### Layer Model

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: Coalitions (Manual YAML)                           │
│ - Imperium: [Goonswarm, TNT, INIT, ...]                    │
│ - PanFam: [Pandemic Horde, PL, NC., ...]                   │
│ - Fire: [FRT, ...]                                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: Alliance Sovereignty (ESI)                         │
│ - System 30004759 → Alliance 1354830081 (Goonswarm)        │
│ - System 30004760 → Alliance 1354830081 (Goonswarm)        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: System Topology (Existing)                         │
│ - System 30004759: Delve, sec -0.54, gates [...]           │
└─────────────────────────────────────────────────────────────┘
```

### Faction Warfare Layer (Parallel)

```
┌─────────────────────────────────────────────────────────────┐
│ FW Occupancy (ESI)                                          │
│ - System 30002057 (Tama): Caldari (contested 45%)          │
│ - System 30002058 (Kedama): Gallente (stable)              │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation Phases

### Dependency Graph

```
Phase 1 ─────────────────────────────────────────────────────►
    │
    ├── Phase 2A (Sov Data) ────────────────────────────────►
    │       │
    │       └── Phase 3A (Coalition Layer) ─────────────────►
    │               │
    │               └── Phase 4 (Skill Integration) ────────►
    │
    └── Phase 2B (FW Data) ─────────────────────────────────►
            │
            └── Phase 3B (FW Skill Integration) ────────────►
```

### Phase Summary

| Phase | Deliverable | ROI | Criticality | Dependencies |
|-------|-------------|-----|-------------|--------------|
| **1** | Data infrastructure | Foundation | **CRITICAL** | None |
| **2A** | Null-sec sovereignty | High | **HIGH** | Phase 1 |
| **2B** | Faction Warfare occupancy | Medium | MEDIUM | Phase 1 |
| **3A** | Coalition mapping | High | **HIGH** | Phase 2A |
| **3B** | FW skill integration | Medium | MEDIUM | Phase 2B |
| **4** | Skill integration (hunting/routing) | **Very High** | **HIGH** | Phase 3A |

---

## Phase 1: Data Infrastructure

**Goal:** Establish storage, refresh patterns, and CLI update mechanism.

**Criticality:** CRITICAL (blocks all other phases)

**ROI:** Low standalone, but required foundation.

### Deliverables

- [ ] Database schema for sovereignty data (`sovereignty_map`, `fw_occupancy`)
- [ ] Cache abstraction layer for ESI-sourced territorial data
- [ ] CLI command: `uv run aria-esi sov-update` (mirrors `sde-update` pattern)
- [ ] Shipped snapshot: `src/aria_esi/data/sovereignty/` with initial data
- [ ] TTL-based freshness tracking (sov: 24h default, FW: 1h default)

### Schema

```sql
-- Null-sec sovereignty (ESI /sovereignty/map/)
CREATE TABLE sovereignty_map (
    system_id INTEGER PRIMARY KEY,
    alliance_id INTEGER,              -- NULL = unclaimed
    faction_id INTEGER,               -- For NPC null-sec (Serpentis, Sansha, etc.)
    updated_at INTEGER NOT NULL,
    FOREIGN KEY (system_id) REFERENCES systems(system_id)
);

CREATE INDEX idx_sov_alliance ON sovereignty_map(alliance_id);

-- Faction Warfare occupancy (ESI /fw/systems/)
CREATE TABLE fw_occupancy (
    system_id INTEGER PRIMARY KEY,
    owner_faction_id INTEGER NOT NULL,
    occupier_faction_id INTEGER NOT NULL,
    contested REAL,                   -- 0.0-1.0 contestation level
    victory_points INTEGER,
    victory_points_threshold INTEGER,
    updated_at INTEGER NOT NULL
);

CREATE INDEX idx_fw_occupier ON fw_occupancy(occupier_faction_id);
CREATE INDEX idx_fw_contested ON fw_occupancy(contested);
```

### CLI Pattern

```bash
# Update sovereignty data from ESI
uv run aria-esi sov-update

# Update with specific TTL override
uv run aria-esi sov-update --force

# Check freshness
uv run aria-esi sov-status
```

**Output example:**
```
Sovereignty data status:
  Null-sec systems: 3,294 (updated 2h ago)
  FW systems: 101 (updated 15m ago)
  Coalition mappings: 847 alliances across 7 coalitions

  Data freshness: OK (within TTL)
```

### Shipped Snapshot

```
src/aria_esi/data/sovereignty/
├── sov_map.json              # ESI snapshot (generated)
├── fw_systems.json           # ESI snapshot (generated)
├── coalitions.yaml           # Manual (committed)
└── FRESHNESS.json            # Generation timestamp
```

**First-run behavior:**
1. Check if local DB has sov data
2. If not, load from shipped snapshot
3. Schedule background refresh (if ESI available)

---

## Phase 2A: Null-Sec Sovereignty

**Goal:** Populate system → alliance mapping from ESI.

**Criticality:** HIGH (enables Phase 3A and Phase 4)

**ROI:** Medium standalone (raw data), High when combined with coalitions.

**Dependencies:** Phase 1

### ESI Integration

```python
async def fetch_sovereignty_map() -> list[SovereigntyEntry]:
    """
    Fetch current null-sec sovereignty from ESI.

    Endpoint: GET /sovereignty/map/
    Cache: 1 hour (ESI-side)
    """
    response = await esi_client.get("/sovereignty/map/")
    return [
        SovereigntyEntry(
            system_id=entry["system_id"],
            alliance_id=entry.get("alliance_id"),
            faction_id=entry.get("faction_id"),
        )
        for entry in response
    ]
```

### Deliverables

- [ ] ESI client method for `/sovereignty/map/`
- [ ] Batch upsert to `sovereignty_map` table
- [ ] Alliance name resolution (ESI `/alliances/{id}/`)
- [ ] Alliance → Corporation membership cache (for renter detection)
- [ ] MCP integration: `universe(action="systems")` includes `sovereignty` field

### MCP Response Enhancement

```python
# Current
universe(action="systems", systems=["1DQ1-A"])
# Returns: {"1DQ1-A": {"security": -0.54, "region": "Delve", ...}}

# Enhanced
universe(action="systems", systems=["1DQ1-A"])
# Returns: {
#   "1DQ1-A": {
#     "security": -0.54,
#     "region": "Delve",
#     "sovereignty": {
#       "alliance_id": 1354830081,
#       "alliance_name": "Goonswarm Federation",
#       "coalition": "imperium"  # From Phase 3A
#     }
#   }
# }
```

---

## Phase 2B: Faction Warfare Occupancy

**Goal:** Track FW system ownership and contestation.

**Criticality:** MEDIUM (parallel track, enables FW-specific features)

**ROI:** Medium (valuable for FW pilots, narrower audience)

**Dependencies:** Phase 1

### ESI Integration

```python
async def fetch_fw_systems() -> list[FWSystem]:
    """
    Fetch current FW system status.

    Endpoint: GET /fw/systems/
    Cache: 30 minutes (ESI-side)
    """
    response = await esi_client.get("/fw/systems/")
    return [
        FWSystem(
            system_id=entry["solar_system_id"],
            owner_faction_id=entry["owner_faction_id"],
            occupier_faction_id=entry["occupier_faction_id"],
            contested=entry["contested"],
            victory_points=entry["victory_points"],
            victory_points_threshold=entry["victory_points_threshold"],
        )
        for entry in response
    ]
```

### Deliverables

- [ ] ESI client method for `/fw/systems/`
- [ ] Batch upsert to `fw_occupancy` table
- [ ] Faction name constants (Caldari State, Gallente Federation, etc.)
- [ ] MCP integration: `universe(action="fw_frontlines")` (already stubbed)

### MCP Action Enhancement

```python
# Existing stub - implement fully
universe(action="fw_frontlines", faction="caldari")
# Returns: {
#   "contested_systems": [
#     {"system": "Tama", "contested": 0.45, "owner": "Caldari", "occupier": "Gallente"},
#     ...
#   ],
#   "vulnerable_systems": [...],
#   "recently_flipped": [...]
# }
```

---

## Phase 3A: Coalition Mapping

**Goal:** Map alliances to coalitions for human-readable territory queries.

**Criticality:** HIGH (transforms raw data into actionable intel)

**ROI:** High (enables "am I in Goon space?" queries)

**Dependencies:** Phase 2A

### Coalition Definition File

```yaml
# src/aria_esi/data/sovereignty/coalitions.yaml

schema_version: "1.0"
last_updated: "2026-02-04"
source_notes: |
  Coalition membership compiled from:
  - r/Eve political maps
  - DOTLAN alliance tracker
  - EVE University wiki

  Update when major political shifts occur.
  Minor alliance changes can lag behind reality.

coalitions:
  imperium:
    display_name: "The Imperium"
    aliases: ["goons", "goonswarm", "gsf", "bees"]
    primary_region: "Delve"
    alliances:
      - id: 1354830081
        name: "Goonswarm Federation"
        role: "executor"
      - id: 937872513
        name: "Tactical Narcotics Team"
      - id: 1900696668
        name: "The Initiative."
      # ... additional member alliances

  panfam:
    display_name: "PanFam"
    aliases: ["pandemic", "horde", "ph"]
    primary_region: "Malpais"
    alliances:
      - id: 99005338
        name: "Pandemic Horde"
        role: "executor"
      - id: 386292982
        name: "Pandemic Legion"
      - id: 99000006
        name: "Northern Coalition."
      # ...

  fire:
    display_name: "Fire Coalition"
    aliases: ["frt", "winter", "fraternity"]
    primary_region: "Oasa"
    alliances:
      - id: 99003581
        name: "Fraternity."
        role: "executor"
      # ...

  # Additional coalitions: B2, TEST/Legacy remnants, smaller blocs

# Special categories
npc_nullsec:
  description: "NPC-controlled null-sec regions"
  regions:
    - "Syndicate"
    - "Curse"
    - "Great Wildlands"
    - "Stain"
    - "Venal"
    - "Outer Ring"

renter_alliances:
  description: "Known renter alliances (soft targets)"
  notes: "Renter status inferred from alliance ticker patterns and historical data"
  patterns:
    - regex: ".*RENTAL.*"
    - regex: ".*RENTER.*"
  explicit:
    - id: 99009082
      name: "Rate My Ticks"
      landlord: "imperium"
```

### Deliverables

- [ ] Coalition YAML schema and initial data file
- [ ] Parser with validation
- [ ] Lookup functions: `get_coalition_for_alliance()`, `get_alliances_in_coalition()`
- [ ] Alias resolution: "goon space" → "imperium"
- [ ] Renter detection heuristics
- [ ] MCP enhancement: `sovereignty.coalition` field in system queries

### Query Examples

```python
# Alliance → Coalition lookup
get_coalition("Goonswarm Federation")  # → "imperium"
get_coalition(1354830081)               # → "imperium"

# Coalition → Systems (via sov map)
get_coalition_systems("imperium")       # → [30004759, 30004760, ...]

# Natural language alias
resolve_coalition_alias("goon space")   # → "imperium"
resolve_coalition_alias("PanFam")       # → "panfam"
```

---

## Phase 3B: FW Skill Integration

**Goal:** Surface FW data in relevant skills.

**Criticality:** MEDIUM

**ROI:** Medium (FW-specific audience)

**Dependencies:** Phase 2B

### Deliverables

- [ ] `/fw-frontlines` skill (or integrate with `/orient` for FW space)
- [ ] FW system highlighting in `/route` when traveling through warzone
- [ ] Contested system warnings in `/threat-assessment`

### Output Example

```
User: /orient Tama

ARIA: ## Tama (The Citadel)

Security: 0.30 (low-sec)
Faction Warfare: ACTIVE WARZONE

### FW Status
Owner: Caldari State
Occupier: Gallente Federation
Contested: 45% (medium activity)
VP: 12,450 / 27,500

⚠️ System is contested. Expect militia activity.
   Caldari advantage: 2 jumps to Ichoriya (stable)
   Gallente advantage: Plex spawns favor attackers

### Activity (Last Hour)
Ship kills: 8
Pod kills: 3
```

---

## Phase 4: Skill Integration

**Goal:** Enable territory-aware queries in hunting and routing skills.

**Criticality:** HIGH (primary user value)

**ROI:** **Very High** (unlocks the motivating use cases)

**Dependencies:** Phase 3A

### Use Cases

#### Use Case 1: Territory-Aware Routing

```
User: Route me through Goon ratting systems avoiding staging

ARIA: Analyzing Imperium territory...

Identified ratting systems (high NPC kills, low PVP):
- 39P-1J (Period Basis) - 847 NPC kills/hr, 2 ship kills
- TCAG-3 (Querious) - 623 NPC kills/hr, 0 ship kills
- ...

Avoiding:
- 1DQ1-A (staging system, high PVP activity)
- T5ZI-S (regional gate, traffic chokepoint)

## Suggested Route (12 jumps through ratting space)

| System | Sec | NPC Kills | PVP | Notes |
|--------|-----|-----------|-----|-------|
| Entry via Khanid | | | | |
| ... | | | | |
```

#### Use Case 2: "Where Am I?"

```
User: /orient J-GAMP

ARIA: ## J-GAMP (Esoteria)

Security: -0.21 (null-sec)

### Sovereignty
Alliance: Army of Mango Alliance
Coalition: **The Imperium** (renter space)

⚠️ You are in Imperium territory.
   Nearest NPC null: 8 jumps (Stain)
   Nearest low-sec: 12 jumps (Aridia)

### Tactical Assessment
- Renter system (softer response expected)
- High ratting activity (potential targets)
- Standing fleet likely in 1DQ1-A (14 jumps)
```

#### Use Case 3: Hunting Ground Analysis

```
User: /hunting-grounds --coalition imperium --avoid-staging

ARIA: ## Imperium Hunting Grounds Analysis

### Prime Targets (ratting systems, low response)
| System | Region | NPC/hr | PVP/hr | Response Time |
|--------|--------|--------|--------|---------------|
| 39P-1J | Period Basis | 847 | 2 | ~8 min |
| TCAG-3 | Querious | 623 | 0 | ~12 min |

### Systems to Avoid
| System | Reason |
|--------|--------|
| 1DQ1-A | Staging (instant response) |
| T5ZI-S | Gate camp common |

### Entry Points
- Via Aridia: 4 jumps to Period Basis ratting
- Via Stain: 6 jumps to Esoteria renters
```

### Deliverables

- [ ] `universe(action="search")` supports `coalition` filter
- [ ] `universe(action="route")` supports `prefer_territory` / `avoid_territory`
- [ ] New action: `universe(action="territory_analysis", coalition="imperium")`
- [ ] `/hunting-grounds` skill enhancement (PARIA-exclusive)
- [ ] `/orient` skill enhancement with sovereignty context
- [ ] `/threat-assessment` skill enhancement with territorial context

### MCP Action: Territory Analysis

```python
universe(
    action="territory_analysis",
    coalition="imperium",
    include_ratting=True,
    include_staging=True,
    include_entry_points=True
)
# Returns: {
#   "coalition": "imperium",
#   "display_name": "The Imperium",
#   "regions": ["Delve", "Querious", "Period Basis", ...],
#   "system_count": 847,
#   "ratting_hotspots": [
#     {"system": "39P-1J", "npc_kills_1h": 847, "ship_kills_1h": 2}
#   ],
#   "staging_systems": [
#     {"system": "1DQ1-A", "type": "main_staging"},
#     {"system": "T5ZI-S", "type": "forward_staging"}
#   ],
#   "entry_points": [
#     {"system": "Sakht", "type": "lowsec_entry", "jumps_to_ratting": 4}
#   ]
# }
```

---

## ROI Analysis

### Value Estimation

| Phase | Dev Effort | User Value | Confidence |
|-------|------------|------------|------------|
| Phase 1 | Medium | None (infrastructure) | High |
| Phase 2A | Low | Low (raw data) | High |
| Phase 2B | Low | Medium (FW pilots) | Medium |
| Phase 3A | Medium | High (territory awareness) | High |
| Phase 3B | Low | Medium (FW pilots) | Medium |
| Phase 4 | Medium | **Very High** (hunting/routing) | High |

### Cumulative ROI

```
Phase 1 alone:     ████░░░░░░ (foundation only)
+ Phase 2A:        █████░░░░░ (data available but not actionable)
+ Phase 3A:        ████████░░ (territory queries work)
+ Phase 4:         ██████████ (full value realized)
```

### Recommendation

**Minimum viable: Phases 1 → 2A → 3A → 4**

FW phases (2B, 3B) can be deferred or parallelized based on pilot demand.

---

## Maintenance Considerations

### Sovereignty Data (Automated)

- ESI provides authoritative data
- `sov-update` CLI refreshes on demand
- Default TTL: 24 hours (sov changes slowly outside wars)
- War-time: Manual `--force` refresh recommended

### Coalition Data (Manual)

**When to update `coalitions.yaml`:**
- Major alliance joins/leaves coalition (r/Eve will announce)
- New coalition forms
- Coalition disbands

**Update frequency:** Monthly review, immediate update for major shifts.

**Sources for updates:**
- r/Eve political updates
- DOTLAN alliance changes
- EVE University coalition page
- Direct observation (zkillboard alliance tags)

### FW Data (Automated)

- ESI provides real-time occupancy
- Default TTL: 1 hour (FW changes frequently)
- No manual maintenance required

---

## Testing Strategy

### Unit Tests

```python
def test_coalition_lookup():
    """Alliance ID resolves to correct coalition."""
    assert get_coalition(1354830081) == "imperium"
    assert get_coalition(99005338) == "panfam"
    assert get_coalition(999999999) is None  # Unknown alliance

def test_alias_resolution():
    """Natural language aliases resolve correctly."""
    assert resolve_coalition_alias("goon space") == "imperium"
    assert resolve_coalition_alias("Goonswarm") == "imperium"
    assert resolve_coalition_alias("ph") == "panfam"

def test_renter_detection():
    """Renter alliances flagged correctly."""
    assert is_renter_alliance("Rate My Ticks")
    assert not is_renter_alliance("Goonswarm Federation")
```

### Integration Tests

```python
@pytest.mark.integration
async def test_sov_update_from_esi():
    """Sovereignty update fetches and stores ESI data."""
    await sov_update()

    # Verify known systems have sov data
    delve_system = get_sovereignty(30004759)  # 1DQ1-A
    assert delve_system.alliance_id == 1354830081

@pytest.mark.integration
async def test_territory_analysis():
    """Territory analysis returns expected structure."""
    result = await universe(action="territory_analysis", coalition="imperium")

    assert result["coalition"] == "imperium"
    assert len(result["regions"]) > 0
    assert "Delve" in result["regions"]
```

---

## Open Questions

1. **Staging system identification**
   - Option A: Manual list in `coalitions.yaml`
   - Option B: Infer from jump bridge data (if available)
   - Option C: Infer from high capital kill activity
   - **Recommendation:** Manual list initially, enhance with inference later

2. **Renter space handling**
   - Should renters be flagged separately from coalition?
   - **Recommendation:** Yes, include `is_renter` boolean in sovereignty response

3. **Historical sovereignty (for pattern analysis)**
   - Store sov changes over time?
   - **Recommendation:** Out of scope for MVP; focus on current state

4. **Coalition membership disputes**
   - Some alliances have ambiguous affiliation
   - **Recommendation:** Document in YAML comments; default to "unaffiliated" if unclear

---

## Summary

| Aspect | Decision |
|--------|----------|
| **Scope** | Null-sec sovereignty + FW occupancy |
| **Data refresh** | CLI command (`sov-update`) + shipped snapshot |
| **Coalition source** | Manual YAML (community-maintained) |
| **Primary value** | Territory-aware hunting and routing |
| **MVP path** | Phases 1 → 2A → 3A → 4 |
| **FW priority** | Deferred (parallel track) |

### Implementation Order (Recommended)

1. **Phase 1** - Data infrastructure (CRITICAL, blocks everything)
2. **Phase 2A** - Null-sec sovereignty (HIGH, enables coalition layer)
3. **Phase 3A** - Coalition mapping (HIGH, enables skill integration)
4. **Phase 4** - Skill integration (HIGH, delivers user value)
5. **Phase 2B** - FW occupancy (MEDIUM, can parallel with 3A/4)
6. **Phase 3B** - FW skills (MEDIUM, after 2B)

Total estimated effort: Medium-Large (comparable to RedisQ integration)

Primary beneficiaries: Null-sec hunters, wormholers using filaments, FW pilots
