---
name: isk-compare
description: Compare ISK/hour across activities you can do with your current skills and ships. Find the most efficient way to earn ISK at your level.
model: haiku
category: financial
triggers:
  - "/isk-compare"
  - "best way to make ISK"
  - "ISK per hour"
  - "what should I do for money"
  - "most profitable activity"
  - "compare money making"
  - "how to earn ISK"
requires_pilot: true
esi_scopes:
  - esi-skills.read_skills.v1
  - esi-characters.read_standings.v1
data_sources:
  - userdata/pilots/{active_pilot}/profile.md
  - userdata/pilots/{active_pilot}/operations.md
  - reference/activities/isk_estimates.yaml
external_sources: []
---

# ARIA ISK/Hour Comparison Module

## Purpose

Help pilots make informed decisions about how to spend their gaming time by comparing ISK/hour across activities they can actually do with their current skills and ships.

## The Problem This Solves

"Should I do missions or mining or exploration?" Players waste time on inefficient activities because they don't know the math. A veteran once said: "I mined for a month in a Venture making 2M/hour when I could have been running L2s at 5M/hour. Nobody told me."

## Target Audience

- New players deciding how to make their first ISK
- Intermediate players optimizing their income
- Returning players catching up on current meta

## Command Syntax

```
/isk-compare                         # Full comparison based on skills
/isk-compare missions                # Focus on mission running
/isk-compare --passive               # Include passive income methods
/isk-compare --risk low              # Only safe activities
```

## Data Sources

### Reference Data (ISK Estimates)

Create/use: `reference/activities/isk_estimates.yaml`

This file contains baseline ISK/hour estimates for activities, with requirements and notes.

### ESI Data (when available)

- Skills: Determine accessible activities
- Standings: Mission agent access levels
- (Optional) Assets: Ships available

## ESI Availability Check (CRITICAL)

**BEFORE making any ESI queries**, check the session hook output for ESI status:

```json
"esi": {"status": "UNAVAILABLE"}
```

### If ESI is UNAVAILABLE:

1. **DO NOT** run `uv run aria-esi` commands - they will timeout
2. **USE** profile data instead:
   - Standings section shows mission access levels
   - `module_tier` indicates skill tier
   - Primary Activities section shows current capabilities
   - Operations file shows available ships
3. **ANSWER IMMEDIATELY** from profile + reference data
4. **NOTE** in response: "Based on profile data (ESI unavailable)"

### If ESI is AVAILABLE:

Proceed with live queries for precise skill/standing checks.

### Profile-Based Fallback

The pilot profile contains enough for useful recommendations:

| Profile Field | Use For |
|---------------|---------|
| Standings tables | Mission level access |
| Primary Activities | Current capabilities |
| Module tier | Skill tier estimation |
| Current Goals | Activity preferences |

**Rationale:** ISK/hour estimates are approximations anyway. Profile data is sufficient for recommendations.

## Execution Flow

### Step 1: Query Pilot State

```bash
# Get skills
uv run aria-esi skills

# Get standings for mission access
uv run aria-esi standings
```

### Step 2: Determine Accessible Activities

For each activity, check requirements:

| Activity | Skill Requirements | Other Requirements |
|----------|-------------------|-------------------|
| L1 Security Missions | Frigate III | None |
| L2 Security Missions | Cruiser III | 1.0 corp standing |
| L3 Security Missions | Battlecruiser III | 3.0 corp standing |
| L4 Security Missions | Battleship III | 5.0 corp standing |
| Highsec Data/Relic | Astrometrics III, Hacking I | Exploration frigate |
| Lowsec Exploration | Same + cloak recommended | Risk tolerance |
| Venture Mining | Mining III | Venture |
| Barge Mining | Mining Barge I | Procurer/Retriever |
| Gas Huffing | Gas Cloud Harvesting I | Venture |
| Planetary Interaction | Command Center Upgrades I | Setup time |
| Abyssal T1-2 | Cruiser IV, tank skills | ~50M fit |
| Hauling | Industrial I | Capital for goods |

### Step 3: Calculate Estimated ISK/Hour

Use reference data with skill-based modifiers:

```python
base_isk = activity.base_isk_per_hour
skill_modifier = calculate_skill_bonus(pilot_skills, activity.scaling_skills)
adjusted_isk = base_isk * skill_modifier
```

### Step 4: Categorize by Availability

| Category | Definition |
|----------|------------|
| **You can do this** | Meets all requirements |
| **Needs training** | Missing skills (show time) |
| **Needs standings** | Has skills but not standing |
| **Needs ship/ISK** | Skill-ready but capital limited |

### Step 5: Add Context

For each activity:
- Effort level (active/semi-active/passive)
- Risk level (safe/moderate/dangerous)
- Variance (consistent/variable)
- Scaling (does it get better with skills?)

## ISK Estimate Database

### Mission Running

| Activity | ISK/Hour (baseline) | Variance | Notes |
|----------|---------------------|----------|-------|
| L1 Security | 1-2M | Low | Career agent ships work |
| L2 Security | 4-8M | Low | Cruiser required |
| L3 Security | 8-15M | Medium | Battlecruiser optimal |
| L4 Security | 15-30M | Medium | Battleship, blitz-able |
| L4 Burners | 40-80M | High | Specialized fits, skill |
| Epic Arcs | 10-20M | Low | One-time every 90 days |

**Factors affecting mission ISK:**
- LP conversion efficiency (varies by corp)
- Salvage/loot value
- Blitzing vs completing
- Mission selection (decline bad missions)

### Exploration

| Activity | ISK/Hour (baseline) | Variance | Notes |
|----------|---------------------|----------|-------|
| Highsec Data Sites | 1-5M | Very High | Often worthless |
| Highsec Relic Sites | 2-8M | Very High | Better than data |
| Lowsec Data/Relic | 10-30M | Very High | PvP risk |
| Nullsec Relic | 20-50M | Very High | Bubble camps |
| C1-C2 Wormhole | 15-40M | High | Need scout/tank |
| Ghost Sites | 20-100M | Very High | Difficult, rare |

**Variance note:** Exploration has extreme variance. Some hours net 0 ISK, others 100M+.

### Mining

| Activity | ISK/Hour (baseline) | Variance | Notes |
|----------|---------------------|----------|-------|
| Venture (Veldspar) | 2-3M | Very Low | Almost no variance |
| Venture (Scordite) | 3-5M | Very Low | Slightly better ores |
| Retriever (Highsec) | 6-10M | Low | Yield focused |
| Procurer (Highsec) | 5-8M | Low | Tank focused |
| Ice Mining (Barge) | 8-15M | Low | Seasonal demand |
| Moon Mining | 10-20M | Low | Corp operations |
| Gas Huffing (WH) | 30-100M | High | Risk + time limited |

### Passive/Semi-Passive Income

| Activity | ISK/Day | Effort | Notes |
|----------|---------|--------|-------|
| Basic PI (1 planet) | 1-2M | 5 min/day | Scales with planets |
| Optimized PI (5 planets) | 8-15M | 30 min/day | Requires setup knowledge |
| Research Agents | 0.5-2M | 0 | Truly passive, low yield |
| Market Trading | Variable | Variable | Capital intensive |
| Hauling Contracts | 5-15M | Active | Requires industrial |

### Combat Anomalies

| Activity | ISK/Hour (baseline) | Variance | Notes |
|----------|---------------------|----------|-------|
| Highsec Anomalies | 2-5M | Low | Unrated sites |
| Lowsec Anomalies | 10-20M | Medium | PvP risk |
| Abyssal T1-2 | 15-25M | Medium | ~50M fit |
| Abyssal T3 | 30-50M | Medium | ~150M fit |
| Abyssal T4-5 | 50-100M | High | ~500M+ fit, skill |

### DED Sites

| Activity | ISK/Hour (baseline) | Variance | Notes |
|----------|---------------------|----------|-------|
| DED 1-2 (Highsec) | 5-15M | High | Depends on drops |
| DED 3-4 (Low/Null) | 20-50M | High | Faction drops |
| DED 5-6 | 50-100M | Very High | Big faction drops |

## Response Format

```
═══════════════════════════════════════════════════════════════════════════════
ISK/HOUR COMPARISON (Your Skills)
───────────────────────────────────────────────────────────────────────────────

MISSION RUNNING:
  L2 Security (Vexor)         4-8M/hr     [You can do this]
  L3 Security (Drake)         8-15M/hr    [Needs: Battlecruisers III - 8d]
  L4 Security (Dominix)       15-30M/hr   [Needs: BS III + 5.0 standing]

EXPLORATION:
  Highsec Data/Relic          2-8M/hr     [You can do this - high variance]
  Lowsec Data/Relic           10-30M/hr   [You can do this - PvP risk]

MINING:
  Venture (Veldspar)          2-3M/hr     [You can do this]
  Retriever (Scordite)        6-10M/hr    [Needs: Mining Barge III - 4d]

COMBAT SITES:
  Abyssal T1                  15-20M/hr   [Needs: ~50M fit]

PASSIVE INCOME:
  Planetary Interaction       5-10M/day   [Setup takes 2-3 hours]

───────────────────────────────────────────────────────────────────────────────
RECOMMENDATION:

Your best active ISK right now: L2 Security Missions (4-8M/hr)
  - You have the skills and standing
  - Consistent income, low risk
  - Train toward L3s for next upgrade

Consider setting up PI for passive income (8-15M/day for 30 min work).
═══════════════════════════════════════════════════════════════════════════════
```

## Recommendation Logic

### For New Players (< 5M SP)

Priority order:
1. L1-L2 missions (consistent, teaches combat)
2. Exploration (potentially high, teaches scanning)
3. PI (passive income while training)
4. Mining (last resort - low ISK, low engagement)

### For Intermediate Players (5-15M SP)

Priority order:
1. L3-L4 missions (depending on standings)
2. Abyssal sites (if ship/fit available)
3. Lowsec exploration (if risk tolerant)
4. Optimized PI (significant passive income)

### Risk Tolerance Adjustment

```
--risk low   → Only highsec activities
--risk med   → Include lowsec with warnings
--risk high  → Include null/WH activities
```

## Effort Level Classification

| Level | Definition | Examples |
|-------|------------|----------|
| Active | Constant attention | Combat, exploration |
| Semi-Active | Periodic attention | Mining, hauling |
| Passive | Set and forget | PI, research agents |

## Variance Explanation

Include variance in recommendations:

```
EXPLORATION (10-30M/hr):
  ⚠️ HIGH VARIANCE
  - Some hours: 0 ISK (no sites, bad loot)
  - Lucky hours: 100M+ (rare blueprints)
  - Average over time: 15-20M/hr
  - Not recommended for "I need ISK now" situations
```

## Standing Integration

Check standings to determine mission access:

```python
def get_mission_access(standings):
    access = []
    for corp, standing in standings.items():
        effective = calculate_effective_standing(standing, connections_level)
        if effective >= 5.0:
            access.append(("L4", corp))
        elif effective >= 3.0:
            access.append(("L3", corp))
        elif effective >= 1.0:
            access.append(("L2", corp))
        else:
            access.append(("L1", corp))
    return access
```

## Error Handling

| Scenario | Response |
|----------|----------|
| No skill data | "Cannot determine your capabilities. Ensure ESI is connected." |
| Very new player | Focus on career agents and early activities |
| No standings data | Show mission estimates with "standing required" notes |

## Caveats to Include

Always mention:
- "Estimates based on average performance. Your results may vary."
- "Market prices fluctuate. LP/loot values change."
- "Active time only - doesn't include travel, setup, selling."
- "Higher skill levels improve these numbers."

## Integration with Other Skills

| After isk-compare | Suggest |
|-------------------|---------|
| Missions chosen | "Use `/standings` to check agent access" |
| Exploration chosen | "Try `/exploration` for site analysis" |
| Mining chosen | "Run `/mining-advisory` for ore recommendations" |
| PI chosen | "Use `/pi` for production chain help" |
| Upgrade identified | "Check `/ship-next` for the right ship" |

## Behavior Notes

- Always base estimates on activities pilot can ACTUALLY do
- Be honest about variance (exploration is gambling)
- Include passive income options (often overlooked)
- Frame recommendations around pilot's current state
- Don't oversell any activity - be realistic
