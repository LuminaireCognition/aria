---
name: standings
description: Standings tracker and progression planner for agent access, faction requirements, and standing repair strategies.
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
  - "how to get L4 agents"
  - "path to 5.0 standing"
  - "how long to reach L4"
  - "standings grind"
  - "standing requirements for L[N]"
  - "fastest way to raise standings"
requires_pilot: true
esi_scopes:
  - esi-characters.read_standings.v1
  - esi-skills.read_skills.v1
data_sources:
  - reference/mechanics/standings_thresholds.json
  - reference/mechanics/epic_arcs.json
external_sources: []
---

# ARIA Standings Module

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

**CRITICAL:** Always ensure fresh standings data before answering eligibility questions. Use the freshness gate below.

## MCP Tools

| Tool | Purpose |
|------|---------|
| `sde(action="agent_search")` | Find agents for standings grinding |
| `sde(action="corporation_info")` | Get corp faction relationships |
| `skills(action="training_time")` | Calculate Social skill training |

## Freshness Gate (before eligibility checks)

**Every standings query that involves eligibility ("Can I use L3 agents?", "Do I qualify?") must run this first:**

```bash
uv run aria-esi ensure-fresh standings
```

This single call checks cache age, syncs from ESI if stale and available, and returns a result you can branch on:

| `fresh` | `esi_available` | Action |
|---------|-----------------|--------|
| `true`  | —               | Use data confidently |
| `false` | `false`         | Use cached data + **strong staleness warning**. Refuse definitive eligibility claims if `age_hours > 168` (7 days). |
| `false` | `true` (sync failed) | Warn about sync failure and use cached data |

**For non-eligibility queries** (general overview, progression planning): use profile data directly without the freshness gate. Staleness is less critical for advisory responses.

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

### Research Agent Query

When asked about R&D / research agents (e.g., "How do I get L4 research agents for CreoDron?"):

1. **Verify corporation faction** via `sde(action="corporation_info", corporation_name="CreoDron")`.
   Never guess which faction a corporation belongs to from training data — always verify.
2. Query standings (ESI or profile cache) and calculate effective standing with Connections bonus.
3. Look up R&D agents via `sde(action="agent_search", corporation="CreoDron", level=4, division="R&D", limit=100)`.
   **Note:** The SDE canonical division name is `"R&D"`, not `"Research"`. Both are accepted by the search tool.
4. Route to nearest agents via `universe(action="route", ...)`.

**Example Response:**

```
## Research Agent Access: CreoDron

**Corporation Faction:** Gallente Federation (verified via SDE)

**Current Standing:**
- Raw: 3.8
- Connections V: +20% → Effective: 5.04

**L4 R&D Agent Requirement:** 5.0 effective standing
**Result:** You meet the threshold.

### Available L4 R&D Agents

| Agent | System | Sec | Region | Jumps |
|-------|--------|-----|--------|------:|
| Fajaf Ansen | Stacmon | 0.60 | Placid | 4 |
| Ogmar Nedar | Alentene | 0.63 | Verge Vendor | 7 |
| Tanelan Vansen | Oursulaert | 0.94 | Essence | 12 |

**Skill reminder:** Train Research Project Management to increase max concurrent R&D agents.
```

**Faction verification warning:** If the user asks about a corporation whose faction you are unsure of, always call `sde(action="corporation_info")` first. Recommending the wrong epic arc based on a wrong faction guess is a critical error.

### Standing Plan Query

When asked how to reach a standing (e.g., "/standings plan Caldari 5.0"):

1. Query current standing from ESI
2. Calculate gap to target
3. Recommend strategy based on reference data

**Example Response:**

```
═══════════════════════════════════════════════════════════════════════════════
STANDINGS PLAN: Caldari State → 5.0
───────────────────────────────────────────────────────────────────────────────

CURRENT STATUS:
  Caldari State:       2.1 raw → 3.68 effective
  Connections:         V (+20% bonus)
  Gap:                 +1.32 effective (need 3.0 raw)

AGENT ACCESS:
  L1 Agents: ✓ Available
  L2 Agents: ✓ Available
  L3 Agents: ✓ Available
  L4 Agents: ✗ Locked (need 5.0, you have 3.68)

───────────────────────────────────────────────────────────────────────────────
PROGRESSION PATH:

PHASE 1: Run L3 Security missions for Caldari Navy
  - Every 16 missions triggers a storyline
  - Storyline gives faction + corp standing
  - ~40-60 missions needed
  - Est. time: 12-18 hours

ACCELERATORS:
  - Epic Arc (every 90 days): Blood-Stained Stars → choose Caldari
    +10% of remaining = ~0.8 raw gain. No derived losses.
  - Data Center Tags (one-time): turn in pirate tags for quick boost
  - Distribution Missions: faster than security, same standing gains

TOTAL ESTIMATED TIME: 2-3 weeks of casual missioning

───────────────────────────────────────────────────────────────────────────────
SKILL RECOMMENDATIONS:

  Train Connections V if not already - it's the best passive standing boost.
  Train Social IV-V for +20-25% standing gains from missions.
═══════════════════════════════════════════════════════════════════════════════
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

### Required Raw for L4 by Connections Level

| Connections | Raw Needed for 5.0 Effective |
|-------------|------------------------------|
| 0 | 5.00 |
| I | 4.87 |
| II | 4.74 |
| III | 4.60 |
| IV | 4.44 |
| V | 4.17 |

**Key insight:** Connections V means you need 4.17 raw instead of 5.0 raw - saves significant grinding time.

## Standing Thresholds

| Level | Requirement |
|-------|-------------|
| L1 | None |
| L2 | 1.0 effective |
| L3 | 3.0 effective |
| L4 | 5.0 effective |
| L5 | 7.0 effective |

## Standing Gain Estimates

| Source | Corp Gain | Faction Gain | Frequency |
|--------|-----------|--------------|-----------|
| Regular mission | +0.01-0.05 | None | Every mission |
| Storyline mission | +0.1-0.3 | +0.1-0.3 | Every 16 missions |
| Epic arc (complete) | None | +0.5-1.5 | Every 90 days |
| Data center tags | +0.1-0.5 | +0.1-0.5 | One-time |
| COSMOS missions | +0.5-1.0 | +0.5-1.0 | One-time (forever) |

## Time Estimates (Neutral → L4)

| Mission Level | Time per Mission | Missions per Storyline |
|---------------|------------------|----------------------|
| L1 | 5-10 min | 16 |
| L2 | 10-15 min | 16 |
| L3 | 15-25 min | 16 |
| L4 | 20-40 min | 16 |

**Phase 1:** Neutral → L2 (1.0): ~10-15 missions, 2-3 hours
**Phase 2:** L2 → L3 (3.0): ~40-50 missions, 6-8 hours
**Phase 3:** L3 → L4 (5.0): ~40-60 missions, 12-18 hours

## Accelerator Strategies

### 1. Connections Skill (Passive)

Train Connections to V for maximum effective standing boost.
- Reduces raw standing needed by ~0.83 for L4 access
- Training time: ~5 days from 0

**Recommend this first if not trained.**

### 2. Social Skill (Active)

Increases standing gains from missions.
- Social IV: +20% to gains
- Social V: +25% to gains
- Fewer missions needed to reach target

### 3. Epic Arcs (Every 90 Days)

**Blood-Stained Stars (SOE):**
- No standing requirement to start
- Choose faction at end
- +10% of remaining faction standing
- No derived losses to enemies

**Faction Epic Arcs:**
- Require ~3.0 standing to start
- Larger rewards (~+10% of remaining)
- 90-day cooldown each

### 4. Data Center Tags (One-Time)

Turn in pirate tags at data centers:
- Quick one-time boost
- Costs ISK (tags from market)
- Cannot repeat

### 5. Storyline Mission Priority

**Critical:** Every 16 missions triggers a storyline.
- Storylines give FACTION standing (not just corp)
- Count is per faction, not per agent
- Don't skip storylines!

### 6. Distribution Missions (Fast Standings)

Courier missions:
- Faster than security missions
- Same standing gains
- Low risk
- Good while training combat skills

## Special Cases

### Cross-Faction Implications

Warn about derived standing losses:
- Running Gallente missions damages Caldari standing
- Running Caldari missions damages Gallente standing
- Amarr/Minmatar are similarly opposed
- Epic arcs avoid these losses!

```
⚠️ WARNING: [Faction] missions will damage your [Enemy Faction] standing.
Current [Enemy]: [X]
Consider using epic arcs instead if you want both factions positive.
```

### L5 Agents (Special Case)

L5 agents require 7.0 effective standing and are in lowsec only.
- Much harder to reach
- PvP risk during missions
- Higher rewards but time-intensive standing grind

## Integration with Other Skills

| Context | Action |
|---------|--------|
| Finding agents | Use `sde(action="agent_search", ...)` |
| Route to agent | Use `universe(action="route", ...)` |
| Mission preparation | Suggest `/mission-brief` |
| LP conversion | Suggest `/lp-store` |
| Need ISK for tags | Suggest `/isk-compare` |

**CRITICAL - Agent Search Limits:**

When searching for agents, **always use `limit=100`** to avoid silent truncation:
```python
sde(action="agent_search", corporation="CreoDron", level=4, division="Security", limit=100)
```

The default limit is 20 results. Without specifying `limit=100`, queries may return incomplete data.

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

**Parallel queries:** The standings and skills ESI calls are independent of each other — run both in parallel when you need both datasets.

**Response format from CLI:**
```json
{
  "standings": [
    {"from_id": 500001, "from_type": "faction", "name": "Caldari State", "standing": 2.1},
    {"from_id": 1000125, "from_type": "npc_corp", "name": "CreoDron", "standing": 3.8}
  ]
}
```

## Error Handling

| Scenario | Response |
|----------|----------|
| No standing data | "Cannot fetch standings. Ensure ESI is connected." |
| Unknown corp/faction | "Entity not found. Try the full name (e.g., 'Federation Navy')." |
| Already at target | "Good news! You already meet the requirement for [target]." |
| Negative standing repair | Prioritize epic arc strategy |

## DO NOT

- **DO NOT** make definitive eligibility claims on stale data (age > 7 days) — use the freshness gate
- **DO NOT** recommend killing friendly faction NPCs
- **DO NOT** suggest COSMOS missions without warning they're one-time only
- **DO NOT** forget to factor in Connections/Diplomacy skills

## Notes

- Standings are checked against faction OR corporation (whichever is higher)
- Epic arcs don't cause derived standing losses
- COSMOS missions cannot be repeated - ever
- Data center tags are one-time per tag type
- L5 agents (7.0 standing) are in low-sec only
