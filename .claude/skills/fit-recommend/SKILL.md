---
name: fit-recommend
description: Recommend ship fittings from the archetype library based on role, hull, budget, and skill tier.
model: sonnet
category: tactical
triggers:
  - "/fit-recommend"
  - "recommend a fit"
  - "fit me a [ship] for [activity]"
  - "what fit for [activity]"
  - "suggest a fit"
  - "fit recommendation"
requires_pilot: false
esi_scopes: []
injected_prerequisites:
  - reference/archetypes/INDEX.md
data_sources:
  - userdata/pilots/{active_pilot}/profile.md
  - userdata/pilots/{active_pilot}/skills.json
external_sources: []
required_tools:
  - fitting.recommend
has_persona_overlay: false
argument-hint: "<hull|role> [--budget ISK] [--tier t1|t2]"
---

# ARIA Fit Recommendation

## Command Syntax

```
/fit-recommend --role missions-l2                     # All fits for L2 missions
/fit-recommend --role missions-l2 --hull Vexor        # Vexor fits for L2 missions
/fit-recommend --role mining-ore --budget 5000000     # Mining fits under 5M ISK
/fit-recommend --role exploration-data --tier t1      # T1 exploration fits
```

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--role` | Yes | Canonical role (e.g., `missions-l2`, `exploration-data`, `mining-ore`) |
| `--hull` | No | Filter to a specific hull |
| `--budget` | No | Maximum total fit cost in ISK (e.g., `15m`, `20000000`) |
| `--tier` | No | Skill tier filter: `t1`, `meta`, `t2_budget`, `t2_optimal` |

## Execution Protocol

### Step 1: Parse Query

Extract role, hull, budget, and tier from the user's request. Map natural language to canonical roles:

| User says | Role |
|-----------|------|
| "L1 missions", "level 1" | `missions-l1` |
| "L2 missions", "level 2" | `missions-l2` |
| "L3 missions", "level 3" | `missions-l3` |
| "L4 missions", "level 4" | `missions-l4` |
| "exploration", "scanning", "data sites" | `exploration-data` |
| "relic sites" | `exploration-relic` |
| "DED sites", "combat exploration" | `exploration-combat` |
| "mining", "ore mining" | `mining-ore` |
| "gas mining", "gas harvesting" | `mining-gas` |
| "ice mining" | `mining-ice` |
| "hauling" | `hauling-hisec` |
| "ratting", "anomalies" | `ratting-anomaly` |
| "abyssal", "filaments" | `abyssal` |
| "salvaging" | `salvaging` |

Parse budget shorthand: `15m` → `15000000`, `1.5b` → `1500000000`.

### Step 2: Query Archetype Library

Call `fitting(action="recommend")` with parsed parameters:

```
fitting(action="recommend", role="missions-l2", hull="Vexor", budget_isk=15000000, limit=5)
```

### Step 3: Handle Results

**On success (results non-empty):**
1. For the top result, read the full archetype YAML from the returned `path`
2. Present the EFT block, estimated cost, and key stats
3. List remaining results as brief alternatives

**On no-match (results empty):**
- Present the `message` field from the response
- Suggest broadening constraints (remove budget, try different tier, etc.)
- Do NOT fall back to ad-hoc fit generation

**On YAML load failure** (path from results doesn't resolve):
- Present a message indicating the archetype could not be loaded
- Suggest trying a different tier or role
- Do NOT fall back to ad-hoc generation

### Step 4: Present

```
FIT RECOMMENDATION: [Role] [Hull filter if any]
───────────────────────────────────────────────────────────────────

TOP MATCH: [Hull] ([Tier])                    Est. cost: [X]M ISK
Roles: [role1, role2]

[EFT block]

Key stats from archetype:
  EHP: [X] | DPS: [X] | Align: [X]s

ALTERNATIVES:
  [Hull] ([Tier])                             Est. cost: [X]M ISK
  [Hull] ([Tier])                             Est. cost: [X]M ISK

Path: reference/archetypes/[path]
───────────────────────────────────────────────────────────────────
```

When `estimated_cost` is `null`, display "Cost: N/A (market data unavailable)".

## Reference: Archetypes Index (injected)
<!-- prerequisite: reference/archetypes/INDEX.md -->
!`cat reference/archetypes/INDEX.md`
