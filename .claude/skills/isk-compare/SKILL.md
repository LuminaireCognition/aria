---
name: isk-compare
description: Compare ISK/hour across activities you can do with your current skills and ships. Find the most efficient way to earn ISK at your level.
model: sonnet
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

## Command Syntax

```
/isk-compare                         # Full comparison based on skills
/isk-compare missions                # Focus on mission running
/isk-compare --passive               # Include passive income methods
/isk-compare --risk low              # Only safe activities
```

## Data Sources

Read `reference/activities/isk_estimates.yaml` for all ISK/hour baselines, activity requirements, access gates, effort levels, variance data, and scaling notes.

### ESI Data (when available)

- Skills: Determine accessible activities
- Standings: Mission agent access levels

### Profile-Based Fallback

If ESI is unavailable, the pilot profile contains enough for useful recommendations:
- Standings tables for mission level access
- Primary Activities for current capabilities
- Module tier for skill tier estimation
- Operations file for available ships

Note in response: "Based on profile data (ESI unavailable)"

## Execution Flow

### Step 1: Query Pilot State

```bash
uv run aria-esi skills
uv run aria-esi standings
```

### Step 2: Determine Accessible Activities

Read `reference/activities/isk_estimates.yaml` for activity requirements and access gates. Cross-reference against pilot skills and standings to categorize each activity.

### Step 3: Categorize by Availability

| Category | Definition |
|----------|------------|
| **You can do this** | Meets all requirements |
| **Needs training** | Missing skills (show time) |
| **Needs standings** | Has skills but not standing |
| **Needs ship/ISK** | Skill-ready but capital limited |

### Step 4: Add Context

For each activity, include effort level, risk level, variance, and scaling from `isk_estimates.yaml`.

## Response Format

```
ISK/HOUR COMPARISON (Your Skills)

MISSION RUNNING:
  L2 Security (Vexor)         4-8M/hr     [You can do this]
  L3 Security (Vexor*)        8-15M/hr    [You can do this - slower in cruiser]
  L4 Security (Dominix)       15-30M/hr   [Needs: BS III + 5.0 standing]

EXPLORATION:
  Highsec Data/Relic          2-8M/hr     [You can do this - high variance]

MINING:
  Venture (Veldspar)          2-3M/hr     [You can do this]

PASSIVE INCOME:
  Planetary Interaction       5-10M/day   [Setup takes 2-3 hours]

RECOMMENDATION:
  Your best active ISK right now: [activity] ([range]/hr)
  - [reason]
  - [next upgrade path]
```

## Economic Advisory Protocol

Validate each recommendation against the pilot's operational constraints (profile.md). If `market_trading: false`, activity must generate value without market sales. If `fleet_required: false`, activity must be solo-viable. If `security_preference` is set, activity must match. State which constraints were checked.

## Error Handling

- No skill data: "Cannot determine your capabilities. Ensure ESI is connected."
- Very new player: Focus on career agents and early activities
- No standings data: Show mission estimates with "standing required" notes

## Behavior Notes

- Always base estimates on activities pilot can ACTUALLY do
- Be honest about variance (exploration is gambling)
- Include passive income options (often overlooked)
- Frame recommendations around pilot's current state
- Don't oversell any activity - be realistic
