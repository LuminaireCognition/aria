# Standings Tracker & Optimizer Proposal

## Executive Summary

Add a `/standings` skill that tracks faction and corporation standings with progression planning. This answers "How many missions until I can use L4 agents?" and "What's my standing with X?"

**Primary value:** Mission runners can plan their standing progression without spreadsheets.

---

## Problem Statement

Standings are critical for mission running, yet:

1. **Hidden thresholds** - "What standing do I need for L4 missions?" requires wiki lookup
2. **Progression math is complex** - Derived standings, social skills, diminishing returns
3. **No planning tools** - "How many L3s to reach 5.0?" requires external calculators
4. **Standing decay** - Players forget they're losing standing with opposing factions

ARIA has ESI standings data and the agent threshold knowledge. It just needs a unified skill.

---

## Standing Mechanics Reference

### Agent Level Requirements

| Agent Level | Effective Standing Required |
|-------------|---------------------------|
| L1 | -10.0 to +10.0 (any) |
| L2 | 1.0 |
| L3 | 3.0 |
| L4 | 5.0 |
| L5 | 7.0 (low-sec only) |

### Effective Standing Formula

```
Effective = Raw + (10 - Raw) * (0.04 * Connections)
```

With Connections V, a 3.67 raw becomes 5.0 effective.

### Standing Gain Formula (Simplified)

```
Gain = Base * (1 + 0.05 * Social) * (1 - CurrentStanding/10)
```

Higher standings = diminishing returns.

### Derived Standings

Faction standing affects corporation standings:
- Corp under faction inherits partial faction standing
- Formula: `NewCorp = OldCorp + (FactionChange * 0.20)`

---

## ESI Foundation

### Required Scope

```
esi-characters.read_standings.v1
```

Returns:
```json
[
  {"from_id": 500001, "from_type": "faction", "standing": 2.34},
  {"from_id": 1000125, "from_type": "npc_corporation", "standing": 4.56}
]
```

### Resolution

- `from_id` → faction/corporation name via SDE
- `from_type` → "faction" or "npc_corporation"

---

## Proposed Skill: `/standings`

### Triggers

```yaml
triggers:
  - "/standings"
  - "my standings"
  - "faction standings"
  - "standing with [faction]"
  - "can I use L4 agents"
  - "how to get standing with [faction]"
  - "missions to reach [standing]"
```

### Commands

| Command | Description |
|---------|-------------|
| `/standings` | Overview of all faction standings |
| `/standings <faction>` | Detailed standing with specific faction |
| `/standings agents <corp>` | What agents can I use with this corp? |
| `/standings plan <faction> <target>` | How to reach target standing |
| `/standings compare` | Side-by-side faction comparison |

### Example Interactions

**Overview:**
```
User: /standings

ARIA: ## Faction Standings

      | Faction | Raw | Effective* | Agent Access |
      |---------|-----|------------|--------------|
      | Gallente Federation | 4.23 | 5.48 | L4 |
      | Federation Navy | 5.12 | 6.35 | L4+ |
      | Caldari State | -1.24 | -0.80 | L1 |
      | Serpentis | -3.45 | -2.76 | Hostile |

      *Effective includes Connections IV (+0.24 per level above raw)

      ### Highlights
      - 0.77 from L5 access with Federation Navy
      - Caldari standing is recoverable (above -2.0 threshold)
      - Serpentis will aggress in high-sec below -5.0

      Skills: Connections IV, Social III, Diplomacy III
```

**Specific faction:**
```
User: /standings Federation Navy

ARIA: ## Federation Navy Standing

      | Metric | Value |
      |--------|-------|
      | Raw Standing | 5.12 |
      | Connections IV Bonus | +0.98 |
      | Effective Standing | 6.10 |

      ### Agent Access
      | Level | Status |
      |-------|--------|
      | L1-L3 | Available |
      | L4 | Available (need 5.0) |
      | L5 | 0.90 away (need 7.0 effective) |

      ### Nearby Agents
      | Agent | Level | System | Jumps |
      |-------|-------|--------|-------|
      | Arlie Parise | L4 Security | Sortet | 0 |
      | Ourielle Mansen | L4 Security | Masalle | 4 |
      | Keita Eslin | L5 Security | Aubenall | 12 (low) |

      Run `/standings plan "Federation Navy" 7.0` for L5 progression.
```

**Progression planning:**
```
User: /standings plan "Federation Navy" 7.0

ARIA: ## Standing Progression Plan

      Current: 5.12 raw (6.10 effective)
      Target: 7.0 effective (L5 agent access)
      Gap: 0.90 effective standing

      ### Option 1: Train Connections V
      Your Connections IV → V would add +0.24 effective.
      New effective: 6.34 (still 0.66 short)

      ### Option 2: Run L4 Missions
      | Missions | New Raw | New Effective | Notes |
      |----------|---------|---------------|-------|
      | ~15 L4s | 5.72 | 6.68 | With storyline |
      | ~25 L4s | 6.15 | 7.03 | With storyline |
      | ~35 L4s | 6.45 | 7.24 | Comfortable buffer |

      Note: Estimates assume Security missions with storyline
      every 16 missions. Actual gain depends on mission type.

      ### Option 3: COSMOS/Epic Arc
      - Gallente Epic Arc (once/3mo): +0.25 - 0.50 raw
      - COSMOS missions (once): Variable, some give large boosts

      Fastest path: Connections V + ~15 L4 missions
```

**Agent eligibility check:**
```
User: Can I use L4 agents for Caldari Navy?

ARIA: ## Caldari Navy Agent Access

      Raw Standing: 2.34
      Effective (Conn IV): 3.41

      | Level | Required | Your Effective | Status |
      |-------|----------|----------------|--------|
      | L1 | Any | 3.41 | Yes |
      | L2 | 1.0 | 3.41 | Yes |
      | L3 | 3.0 | 3.41 | Yes |
      | L4 | 5.0 | 3.41 | No (1.59 short) |

      To unlock L4 agents:
      - ~20 L3 Security missions (estimated)
      - Or train Connections IV → V (+0.24) then ~15 L3s
```

---

## Implementation

### Phase 1: Standing Display

**Deliverables:**
- [ ] Create `/standings` skill definition
- [ ] ESI standings fetch via `aria-esi standings`
- [ ] Faction/corporation name resolution via SDE
- [ ] Effective standing calculation with skill lookup

**CLI command:**
```bash
uv run aria-esi standings [--faction <name>] [--format json|table]
```

### Phase 2: Agent Eligibility

**Deliverables:**
- [ ] Agent level thresholds (static data)
- [ ] Current access level calculation
- [ ] "Next level" gap analysis

**Threshold data:**
```json
{
  "agent_thresholds": {
    "L1": -10.0,
    "L2": 1.0,
    "L3": 3.0,
    "L4": 5.0,
    "L5": 7.0
  }
}
```

### Phase 3: Progression Estimation

**Deliverables:**
- [ ] Standing gain formula implementation
- [ ] Mission-to-standing calculator
- [ ] Storyline mission factoring

**Key challenge:** Actual standing gain varies by:
- Mission type (Security, Distribution, Mining)
- Agent quality (affects base gain)
- Current standing (diminishing returns)
- Social skills

Recommendation: Use average values with disclaimers.

### Phase 4: Epic Arc & COSMOS Integration

**Deliverables:**
- [ ] Epic arc standing rewards reference
- [ ] COSMOS mission data (complex, low priority)
- [ ] Recommendation engine for fastest path

---

## Skill Definition

```yaml
---
name: standings
description: Faction and corporation standing tracker with progression planning. Check agent access eligibility and calculate missions to target standings.
model: haiku
category: identity
triggers:
  - "/standings"
  - "my standings"
  - "faction standings"
  - "standing with [faction]"
  - "can I use L4 agents"
  - "how to get standing with [faction]"
  - "missions to reach [standing]"
  - "agent access"
requires_pilot: true
esi_scopes:
  - esi-characters.read_standings.v1
  - esi-skills.read_skills.v1
data_sources:
  - reference/mechanics/standings_thresholds.json
  - reference/mechanics/epic_arcs.json
has_persona_overlay: false
---
```

---

## Reference Data Requirements

### New: `reference/mechanics/standings_thresholds.json`

```json
{
  "agent_levels": {
    "L1": {"min_effective": -10.0, "note": "Any standing"},
    "L2": {"min_effective": 1.0},
    "L3": {"min_effective": 3.0},
    "L4": {"min_effective": 5.0},
    "L5": {"min_effective": 7.0, "note": "Low-sec only"}
  },
  "skill_bonuses": {
    "connections": {
      "formula": "(10 - raw) * 0.04 * level",
      "description": "Increases effective standing with positive entities"
    },
    "diplomacy": {
      "formula": "(10 + raw) * 0.04 * level",
      "description": "Increases effective standing with negative entities"
    }
  },
  "faction_penalties": {
    "below_-2.0": "Cannot dock at faction stations",
    "below_-5.0": "Faction navy will attack in high-sec"
  }
}
```

### New: `reference/mechanics/epic_arcs.json`

```json
{
  "gallente": {
    "name": "Syndication",
    "faction": "Gallente Federation",
    "standing_reward": "+0.25 to +0.50 (choice)",
    "cooldown_days": 90,
    "starting_agent": "Roineron Aviviere",
    "starting_system": "Dodixie"
  },
  "caldari": { ... },
  "amarr": { ... },
  "minmatar": { ... },
  "sisters_of_eve": { ... }
}
```

---

## Standing Gain Estimation

```python
def estimate_missions_to_standing(
    current_raw: float,
    target_effective: float,
    connections_level: int,
    social_level: int,
    mission_level: int = 4
) -> int:
    """
    Estimate number of missions to reach target effective standing.

    Very approximate - actual gains vary significantly.
    """
    # Base gain per mission (rough average for L4 security)
    BASE_GAIN = {
        1: 0.012,
        2: 0.024,
        3: 0.048,
        4: 0.096,
        5: 0.192
    }

    base = BASE_GAIN[mission_level]
    social_bonus = 1 + (0.05 * social_level)

    missions = 0
    current = current_raw

    while effective_standing(current, connections_level) < target_effective:
        # Diminishing returns
        gain = base * social_bonus * (1 - current / 10)
        current += gain
        missions += 1

        # Storyline every 16 missions
        if missions % 16 == 0:
            current += gain * 5  # Storyline gives ~5x normal

        if missions > 500:  # Safety limit
            break

    return missions
```

---

## Integration Points

### With SDE Tools

```python
# Resolve faction/corporation names
entity_info = sde(action="corporation_info", corporation_id=from_id)
```

### With Agent Search

```python
# Find available agents for faction
agents = sde(action="agent_search",
            corporation="Federation Navy",
            level=4,
            highsec_only=True)
```

### With Route Tools

```python
# Distance to nearest agent
route = universe(action="route",
                origin=current_system,
                destination=agent_system)
```

---

## Open Questions

1. **Include COSMOS missions?**
   - Complex one-time missions with standing rewards
   - Recommendation: Reference only, not detailed tracking

2. **Derived standings display?**
   - Show how faction standing affects member corps
   - Recommendation: Phase 2, mention in notes

3. **Standing history/trends?**
   - Track standing over time
   - Recommendation: Phase 3+, store snapshots like assets

4. **Tags for standing repair?**
   - Security tag turn-in for sec status
   - Different from faction standings
   - Recommendation: Separate `/sec-status` skill (exists for PARIA)

---

## Example CLI Integration

```bash
# All standings
uv run aria-esi standings

# Specific faction
uv run aria-esi standings --faction "Gallente Federation"

# Check agent access
uv run aria-esi standings --agents "Federation Navy"

# JSON output for processing
uv run aria-esi standings --format json
```

---

## Summary

| Aspect | Decision |
|--------|----------|
| Skill name | `/standings` |
| Required scopes | standings + skills |
| Agent thresholds | Static reference data |
| Progression estimates | Formula-based, approximate |
| Epic arc integration | Phase 2 (reference data) |
| COSMOS integration | Low priority (complexity) |
| MVP features | Display, eligibility, basic planning |

This addresses mission runner needs with existing ESI data and standing mechanics knowledge.
