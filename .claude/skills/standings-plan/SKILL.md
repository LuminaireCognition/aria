---
name: standings-plan
description: Plan your path to target standings for mission agent access. Shows current standings, requirements, and the fastest strategies to reach your goal.
model: haiku
category: identity
triggers:
  - "/standings-plan"
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

# ARIA Standings Progression Planner

## Purpose

Help pilots understand standings requirements and plan the most efficient path to reach their goals. This skill answers:
- What standing do I need for L3/L4/L5 agents?
- How long will it take to get there?
- What's the fastest path?

## The Problem This Solves

Standings are deeply confusing for new players. They don't understand:
- They need 5.0 standing for L4 agents
- How long it takes to get there
- That storyline missions are the key
- That the SOE epic arc exists
- The difference between corp and faction standing

## Target Audience

- New players finishing L1/L2 missions wanting to progress
- Intermediate players aiming for L4 access
- Anyone with damaged standings needing repair strategies

## Command Syntax

```
/standings-plan                               # Overall standings assessment
/standings-plan <faction/corp>                # Plan for specific entity
/standings-plan "Federation Navy" 5.0         # Plan to reach specific goal
/standings-plan repair Caldari                # Repair damaged standing
```

## MCP Tools Required

| Tool | Purpose |
|------|---------|
| `sde(action="agent_search")` | Find agents for standings grinding |
| `sde(action="corporation_info")` | Get corp faction relationships |
| `skills(action="training_time")` | Calculate Social skill training |

**CRITICAL - Agent Search Limits:**

Always use `limit=100` when searching for agents to avoid silent truncation:
```python
sde(action="agent_search", corporation="Federation Navy", level=4, limit=100)
```

The default limit is 20 results. Without explicit `limit=100`, comprehensive queries (e.g., "all agents in region X") will return incomplete data.

**ESI queries:**
```bash
uv run aria-esi standings   # Current standings
uv run aria-esi skills      # Connections/Diplomacy levels
```

## Reference Data

- `reference/mechanics/standings_thresholds.json` - Agent level requirements
- `reference/mechanics/epic_arcs.json` - Epic arc data and rewards

## ESI Availability Check (CRITICAL)

**BEFORE making any ESI queries**, check the session hook output for ESI status:

```json
"esi": {"status": "UNAVAILABLE"}
```

### If ESI is UNAVAILABLE:

1. **DO NOT** run `uv run aria-esi` commands - they will timeout
2. **USE** profile standings tables instead:
   - Empire Factions table has faction standings
   - Mission Corporations table has corp standings + access levels
   - Data may note sync time and staleness warning
3. **ANSWER IMMEDIATELY** from cached standings
4. **NOTE** in response: "Based on cached standings (ESI unavailable) - data from [sync date]"
5. **Assume** Connections IV-V for effective standing calculations (common for mission runners)

### If ESI is AVAILABLE:

Proceed with live queries for precise standings and skill levels.

### Profile Standings Format

The profile contains pre-formatted standings:
```markdown
| Corporation | Standing | Access |
|-------------|----------|--------|
| Federation Navy | 4.59 | **L3 Missions** (L4 @ 5.0) |
```

This already includes access level calculations - use directly.

**Rationale:** Standings don't change rapidly. Profile cache is usually accurate enough for planning.

## Execution Flow

### Step 1: Query Current State

**If ESI available:**
```bash
uv run aria-esi standings
uv run aria-esi skills
```

**If ESI unavailable:**
Read `userdata/pilots/{active_pilot}/profile.md` standings tables.

Extract:
- Raw standings with all factions/corps
- Connections level (for positive standings) - assume IV-V if unknown
- Diplomacy level (for negative standings)
- Social level (affects gain rate)

### Step 2: Calculate Effective Standings

Apply skill modifiers to raw standings:

```python
# Connections (positive standings only)
if raw >= 0:
    effective = raw + (10 - raw) * connections_level * 0.04

# Diplomacy (negative standings only)
if raw < 0:
    effective = raw + (raw + 10) * diplomacy_level * 0.04
```

### Step 3: Determine Current Access

Compare effective standings to thresholds:

| Level | Requirement |
|-------|-------------|
| L1 | None |
| L2 | 1.0 effective |
| L3 | 3.0 effective |
| L4 | 5.0 effective |
| L5 | 7.0 effective |

### Step 4: Calculate Gap to Goal

If pilot specifies a target (e.g., "5.0 for L4"):
```python
gap = target - effective_standing
raw_needed = calculate_raw_needed(target, connections_level)
```

### Step 5: Generate Progression Plan

Based on current standing and goal, recommend path:

#### Starting from Neutral (0.0) → L4 (5.0)

**Phase 1: Reach L2 Access (1.0)**
- Run L1 missions for target corp
- ~10-15 missions typically
- Est. time: 2-3 hours

**Phase 2: Reach L3 Access (3.0)**
- Run L2 missions
- Every 16 missions → storyline mission (faction standing!)
- ~40-50 missions
- Est. time: 6-8 hours

**Phase 3: Reach L4 Access (5.0)**
- Run L3 missions
- Continue storyline cycle
- ~40-60 missions
- Est. time: 12-18 hours

#### Starting from Negative → Positive

Use epic arcs (no derived standing losses):
- Blood-Stained Stars (SOE) - no standing requirement
- Faction epic arcs - require positive standing to start

### Step 6: Estimate Time

Based on typical mission completion rates:

| Mission Level | Time per Mission | Missions per Storyline |
|---------------|------------------|----------------------|
| L1 | 5-10 min | 16 |
| L2 | 10-15 min | 16 |
| L3 | 15-25 min | 16 |
| L4 | 20-40 min | 16 |

**Storyline mission frequency:** Every 16 regular missions for the same faction.

## Response Format

```
═══════════════════════════════════════════════════════════════════════════════
STANDINGS PLAN: [Corporation/Faction] → [Target]
───────────────────────────────────────────────────────────────────────────────

CURRENT STATUS:
  [Entity Name]:         [Raw] raw → [Effective] effective
  Connections:           [Level] (+[X]% bonus)
  Diplomacy:             [Level]

AGENT ACCESS:
  L1 Agents: ✓ Available
  L2 Agents: ✓ Available (need 1.0, you have [X])
  L3 Agents: ✗ Locked (need 3.0, you have [X])
  L4 Agents: ✗ Locked (need 5.0, you have [X])

TARGET: [Value] effective standing
GAP: [+X.XX] needed

───────────────────────────────────────────────────────────────────────────────
PROGRESSION PATH:

PHASE 1: [Current] → [Milestone 1] (Est. [X] hours)
  [Activity description]
  - Run [level] missions for [corp]
  - ~[X] missions needed
  - Tip: [Relevant advice]

PHASE 2: [Milestone 1] → [Milestone 2] (Est. [X] hours)
  [Activity description]
  - [Details]

ACCELERATORS:
  - [Method 1]: [Description]
  - [Method 2]: [Description]

TOTAL ESTIMATED TIME: [X] hours of mission running
───────────────────────────────────────────────────────────────────────────────
SKILL RECOMMENDATIONS:

  Connections [Current] → V
    Effect: +[X]% effective standing boost (passive)
    Training: [Time]
    Impact: Reach L4 at [X] raw instead of [Y] raw

  Social [Current] → IV
    Effect: +[X]% standing gains from missions
    Training: [Time]
    Impact: Faster progression (~[X]% fewer missions)
═══════════════════════════════════════════════════════════════════════════════
```

## Standings Math Reference

### Effective Standing Formula

```python
# Positive raw standing with Connections
effective = raw + (10 - raw) * connections_level * 0.04

# Example: 4.0 raw + Connections V
effective = 4.0 + (10 - 4.0) * 5 * 0.04
effective = 4.0 + 6.0 * 0.2
effective = 4.0 + 1.2
effective = 5.2  # Meets L4 requirement!
```

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

### Standing Gain Estimates

| Source | Corp Gain | Faction Gain | Frequency |
|--------|-----------|--------------|-----------|
| Regular mission | +0.01-0.05 | None | Every mission |
| Storyline mission | +0.1-0.3 | +0.1-0.3 | Every 16 missions |
| Epic arc (complete) | None | +0.5-1.5 | Every 90 days |
| Data center tags | +0.1-0.5 | +0.1-0.5 | One-time |
| COSMOS missions | +0.5-1.0 | +0.5-1.0 | One-time (forever) |

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

### Repairing Negative Standings

If standing is negative:

```
REPAIR STRATEGY: [Faction] (-3.2 raw)

1. EPIC ARC (Best Option)
   Blood-Stained Stars (no requirement)
   → Choose [Faction] at end
   → Gain: -3.2 → -1.9 (estimated)
   → Cooldown: 90 days

2. DIPLOMACY SKILL
   Current: [Level]
   → Train to V for +20% effective
   → -3.2 raw → -2.56 effective
   → Doesn't help with agent access directly

3. CAREER AGENTS (One-time)
   Run [Faction] career agents
   → Small gains, no cooldown
   → Check if already completed
```

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

## Error Handling

| Scenario | Response |
|----------|----------|
| No standing data | "Cannot fetch standings. Ensure ESI is connected." |
| Unknown corp/faction | "Entity not found. Try the full name (e.g., 'Federation Navy')." |
| Already at target | "Good news! You already meet the requirement for [target]." |
| Negative standing repair | Prioritize epic arc strategy |

## Integration with Other Skills

| After standings-plan | Suggest |
|---------------------|---------|
| Plan created | "Use `/standings` to track your current progress" |
| Agent access confirmed | "Use `sde(action=\"agent_search\", corporation=\"X\", level=N, limit=100)` to find agents" |
| Need ISK for tags | "Check `/isk-compare` for earning methods" |
| Missions mentioned | "Use `/mission-brief` for mission intel" |

## Behavior Notes

- Always show EFFECTIVE standing (with skill bonuses)
- Calculate raw standing needed for goals
- Emphasize Connections skill importance
- Warn about faction warfare implications
- Be realistic about time estimates
- Mention epic arcs early (often forgotten)
