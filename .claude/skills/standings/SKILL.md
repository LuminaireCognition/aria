---
name: standings
description: Standings tracker for agent access, faction requirements, and standing repair strategies.
model: haiku
category: identity
triggers:
  - "/standings"
  - "my standings"
  - "can I use L[N] agents"
  - "standing requirements"
  - "how to fix standings"
  - "agent access"
  - "faction standing"
requires_pilot: true
esi_scopes:
  - esi-characters.read_standings.v1
  - esi-skills.read_skills.v1
data_sources:
  - reference/mechanics/standings_thresholds.json
  - reference/mechanics/epic_arcs.json
---

# ARIA Standings Tracker Module

## Purpose

Track faction and corporation standings, determine agent access levels, and provide standing repair strategies. Integrates with ESI for live standings data and uses reference data for threshold calculations.

## Trigger Phrases

- "/standings"
- "my standings"
- "can I use L[N] agents"
- "standing requirements"
- "how to fix standings"
- "agent access"
- "faction standing"

## Command Syntax

```
/standings                     # Overview of all standings
/standings <faction/corp>      # Standing with specific entity
/standings agents <corp>       # What agent levels you can access
/standings plan <faction> <N>  # How to reach standing N
/standings repair <faction>    # Strategies to repair negative standing
```

## Data Sources

- **ESI:** Live standings via `uv run aria-esi standings`
- **Reference:** `reference/mechanics/standings_thresholds.json` for thresholds
- **Reference:** `reference/mechanics/epic_arcs.json` for epic arc data

**CRITICAL:** Always query ESI for current standings before answering eligibility questions. Profile data may be stale.

## ESI Availability Check (CRITICAL)

**BEFORE making any ESI queries**, check the session hook output for ESI status:

```json
"esi": {"status": "UNAVAILABLE"}
```

### If ESI is UNAVAILABLE:

1. **DO NOT** run `uv run aria-esi` commands - they will timeout
2. **USE** profile standings tables:
   - `userdata/pilots/{active_pilot}/profile.md` contains:
     - Empire Factions table with faction standings
     - Mission Corporations table with corp standings + access levels
   - Data may include sync timestamp and staleness warning
3. **ANSWER IMMEDIATELY** using cached standings
4. **NOTE** in response: "Based on cached standings (ESI unavailable) - data from [sync date if shown]"
5. **For eligibility checks:** Use profile standings but note they may be stale

### If ESI is AVAILABLE:

Proceed with live `uv run aria-esi standings` queries.

### Profile Standings Format

The profile contains pre-formatted standings:
```markdown
| Corporation | Standing | Access |
|-------------|----------|--------|
| Federation Navy | 4.59 | **L3 Missions** (L4 @ 5.0) |
```

This already includes access level calculations - use directly for quick answers.

## Response Patterns

### Overview Query

When asked for general standings ("/standings"):

1. Query ESI: `uv run aria-esi standings`
2. Read reference data for threshold context
3. Query skills for Connections/Diplomacy levels
4. Present organized by faction and corporation

**Example Response:**

```
## Current Standings

**Connections V active** (+20% effective on positive standings)

### Empire Factions
| Faction | Raw | Effective | L4 Access? |
|---------|-----|-----------|------------|
| Gallente Federation | 4.2 | 5.36 | Yes |
| Caldari State | 2.1 | 3.68 | No (need 5.0) |
| Amarr Empire | -0.5 | -0.5 | No |
| Minmatar Republic | 1.8 | 3.44 | No (need 5.0) |

### Key Corporations
| Corporation | Raw | Effective | Notes |
|-------------|-----|-----------|-------|
| Federation Navy | 5.1 | 6.08 | L4 access |
| CreoDron | 3.2 | 4.56 | L3 access |

*Effective standing includes Connections V bonus.*
```

### Agent Access Query

When asked about agent access (e.g., "can I use L4 agents with CreoDron"):

1. Query ESI for current standings
2. Query skills for Connections level
3. Calculate effective standing
4. Compare to threshold from reference data

**Example Response:**

```
## Agent Access: CreoDron

**Current Standing:**
- Raw: 3.8
- Connections V: +20% bonus
- Effective: 3.8 + (10 - 3.8) × 0.20 = 5.04

**L4 Agent Requirement:** 5.0 effective standing

**Result:** Yes, you can use L4 CreoDron agents.

**Nearest L4 Security Agent:**
Use `sde(action="agent_search", corporation="CreoDron", level=4, division="Security")`
to find locations.
```

### Standing Plan Query

When asked how to reach a standing (e.g., "/standings plan Caldari 5.0"):

1. Query current standing from ESI
2. Calculate gap to target
3. Recommend strategy based on reference data

**Example Response:**

```
## Standing Plan: Caldari State → 5.0

**Current:** 2.1 raw, 3.68 effective (Connections V)
**Target:** 5.0 effective
**Gap:** 1.32 effective (need 3.0 raw)

### Recommended Path

1. **Storyline Missions** (primary method)
   - Run L2/L3 Security missions for Caldari Navy
   - Every 16 missions triggers a storyline
   - Storyline gives faction + corp standing

2. **Epic Arc** (every 90 days)
   - Run "Blood-Stained Stars" (no requirement)
   - Choose Caldari at the end
   - +10% of remaining = ~0.8 raw gain

3. **Data Center Tags** (one-time)
   - Turn in pirate tags at data centers
   - Quick boost, requires ISK for tags

**Estimated Time:** 2-3 weeks of casual missioning

*Train Connections V if not already - it's the best passive standing boost.*
```

### Standing Repair Query

When asked about repairing negative standings (e.g., "/standings repair Gallente"):

1. Query current standing
2. Read epic arc data
3. Recommend repair strategies

**Example Response:**

```
## Standing Repair: Gallente Federation

**Current:** -3.2 raw

### Repair Strategies (in order of effectiveness)

1. **Epic Arc: Blood-Stained Stars** (best option)
   - No standing requirement
   - Choose Gallente at the end
   - Gain: -3.2 → -1.88 (≈1.3 raw improvement)
   - Cooldown: 90 days
   - Location: Sister Alitura, Arnon IX

2. **Train Diplomacy Skill**
   - Only affects negative standings
   - Diplomacy V: +20% effective boost
   - -3.2 raw → -2.56 effective

3. **Career Agents** (one-time)
   - Run Gallente career agents
   - Small gains but no cooldown
   - Check if you've done them before

4. **Faction Warfare (indirect)**
   - Join Gallente FW (need 0.0+ standing first)
   - Not applicable while negative

**Warning:** Avoid killing Gallente NPCs while repairing.
Each kill causes standing loss.
```

## Derived Standing Calculation

The skill must calculate effective standings correctly:

```python
# Connections skill (positive standings only)
if raw_standing >= 0:
    effective = raw + (10 - raw) * connections_level * 0.04

# Diplomacy skill (negative standings only)
if raw_standing < 0:
    effective = raw + (raw + 10) * diplomacy_level * 0.04
```

**Always show both raw and effective standings in output.**

## Integration with Other Skills

| Context | Action |
|---------|--------|
| Finding agents | Use `sde(action="agent_search", ...)` |
| Route to agent | Use `universe(action="route", ...)` |
| Mission preparation | Suggest `/mission-brief` |
| LP conversion | Suggest `/lp-store` |

**CRITICAL - Agent Search Limits:**

When searching for agents, **always use `limit=100`** to avoid silent truncation:
```python
sde(action="agent_search", corporation="CreoDron", level=4, division="Security", limit=100)
```

The default limit is 20 results. Without specifying `limit=100`, queries may return incomplete data (e.g., only L1-L2 agents when L3-L4 also exist).

For comprehensive regional queries, run separate searches by level:
```python
for level in [1, 2, 3, 4, 5]:
    sde(action="agent_search", corporation="X", level=level, limit=100)
```

## ESI Query Pattern

```bash
# Get current standings
uv run aria-esi standings

# Get skills (for Connections/Diplomacy)
uv run aria-esi skills
```

**Response format from CLI:**
```json
{
  "standings": [
    {"from_id": 500001, "from_type": "faction", "name": "Caldari State", "standing": 2.1},
    {"from_id": 1000125, "from_type": "npc_corp", "name": "CreoDron", "standing": 3.8}
  ]
}
```

## DO NOT

- **DO NOT** trust cached profile standings for eligibility checks - always query ESI
- **DO NOT** recommend killing friendly faction NPCs
- **DO NOT** suggest COSMOS missions without warning they're one-time only
- **DO NOT** forget to factor in Connections/Diplomacy skills

## Notes

- Standings are checked against faction OR corporation (whichever is higher)
- Epic arcs don't cause derived standing losses
- COSMOS missions cannot be repeated - ever
- Data center tags are one-time per tag type
- L5 agents (7.0 standing) are in low-sec only
