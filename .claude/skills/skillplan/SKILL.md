---
name: skillplan
description: Skill planning advisor for EVE Online. Analyze skill requirements for ships, modules, or activities with training time estimates and "Easy 80%" recommendations.
model: haiku
category: tactical
triggers:
  - "/skillplan"
  - "what skills for [ship]"
  - "skills needed for [item]"
  - "how long to train [skill/ship]"
  - "skill requirements for [item]"
  - "can I fly [ship]"
  - "what do I need for [activity]"
requires_pilot: true
esi_scopes: [esi-skills.read_skills.v1]
data_sources:
  - reference/activities/skill_plans.yaml
  - reference/skills/ship_efficacy_rules.yaml
  - reference/skills/meta_module_alternatives.yaml
external_sources: []
---

# ARIA Skill Planning Advisor

## Purpose

Provide skill requirement analysis and training time estimates for ships, modules, skills, and activities in EVE Online. Implements the "Easy 80%" philosophy - achieving ~80% effectiveness with ~20% of the training time by capping most skills at Level IV.

## Command Syntax

```
/skillplan ship <ship_name>              # Ship requirements
/skillplan module <module_name>          # Module requirements
/skillplan skill <skill_name>            # Skill prerequisites
/skillplan activity <activity_name>      # Activity skill plan
/skillplan "<goal description>"          # Natural language goal
```

### Options

```
--full          Show full requirements only (no Easy 80%)
--easy          Show Easy 80% plan only
--minimum       Show minimum viable skills only (activities)
--tier <tier>   Specify tier: minimum, easy_80, or full
```

## MCP Tools Required

This skill requires the following MCP tools from the `aria-universe` server:

| Tool | Purpose |
|------|---------|
| `sde_skill_requirements` | Get skill prerequisite tree for items |
| `skill_training_time` | Calculate training time for skill plans |
| `skill_easy_80_plan` | Generate Easy 80% plan with efficacy estimates |
| `skill_get_multipliers` | Get high-impact multiplier skills by role |
| `skill_t2_requirements` | Check T2 items for Level V requirements |
| `activity_skill_plan` | Get skill requirements for activities |
| `activity_list` | List available activity templates |
| `activity_search` | Search activities by keyword |
| `activity_compare_tiers` | Compare training times across tiers |
| `sde_item_info` | Look up item details and category |

**CRITICAL:** Check that these tools are available before proceeding. If unavailable, inform the user that skill planning requires the SDE MCP server.

## Pilot Skills — Mandatory for Accurate Training Times

**CRITICAL:** Training time estimates are **wrong** if `current_skills` is not passed to `easy_80_plan`. Without it, all times calculate from level 0 — massively overstating training needed.

### Step 0: Ensure Fresh Skills (Before Anything Else)

**CRITICAL:** Training time estimates are **wrong** without `current_skills`. Always attempt to load fresh skills first.

#### Freshness Gate

```bash
uv run aria-esi ensure-fresh skills
```

| `fresh` | `esi_available` | Action |
|---------|-----------------|--------|
| `true`  | —               | Load skills from cache (now fresh), pass to `easy_80_plan` |
| `false` | `false`         | Load stale cache if exists + **strong warning**: "⚠️ ESI offline — training times may be inaccurate if skills have changed since last sync." If no cache exists, warn: "⚠️ No cached skills — all training times are from-scratch estimates." |
| `false` | `true` (sync failed) | Use cached skills if `age_hours < 72`, warn if older |

#### After Freshness Gate: Load Skills

```bash
uv run aria-esi skills
```

**CLI syntax notes:**
- Filter is a **positional** argument: `uv run aria-esi skills "Drones"` (filters by name substring)
- **Wrong:** `uv run aria-esi skills --filter "Drones"` (the `--filter` flag does not exist)

Extract skill names and levels from the output into a `{name: level}` dict:

```python
# From CLI output, build:
current_skills = {"Gallente Cruiser": 3, "Drones": 5, "Drone Interfacing": 4, ...}
```

Then pass to every `easy_80_plan` call:

```python
skills(action="easy_80_plan", item="Vexor Navy Issue", current_skills=current_skills)
```

### Golden Path — Minimal MCP Call Sequence

For most queries, the optimal call sequence is:

1. **`uv run aria-esi skills`** → fetch pilot's current skills (when ESI available)
2. **`skills(action="easy_80_plan", item="...", current_skills={...})`** → generates the full plan with accurate delta-based training times

That's it. Two calls. The `easy_80_plan` response includes:
- `easy_80_plan`: Categorized skills (required, cap_at_4, train_to_5)
- `easy_80_time`: Training time for the Easy 80% plan
- `full_mastery_time`: Training time for all skills to V
- `time_savings`: How much time Easy 80% saves
- `efficacy_estimate`: Approximate effectiveness percentage
- `meta_suggestions`: Alternatives for T2 items requiring Level V

**Optional third call:** `sde(action="item_info", item="...")` — only if you need item description, category, or other metadata not included in the plan response.

> **⚠️ Anti-Pattern:** Do NOT call `sde(action="skill_requirements")` alongside `easy_80_plan`. The `easy_80_plan` response already contains the full prerequisite tree, categorized into training tiers. Calling both is redundant and wastes a round-trip.

## Execution Flow

### Step 1: Parse Request

Determine the query type from user input:

| Pattern | Type | Example |
|---------|------|---------|
| `ship <name>` | Ship | `/skillplan ship Vexor Navy Issue` |
| `module <name>` | Module | `/skillplan module Medium Armor Repairer II` |
| `skill <name>` | Skill | `/skillplan skill Gallente Cruiser` |
| `activity <name>` | Activity | `/skillplan activity gas huffing` |
| Natural language | Infer | "what do I need to fly a Vexor?" |

For activity queries, use `activity_skill_plan` instead of `skill_easy_80_plan`.

### Step 2: Generate Easy 80% Plan

Call `easy_80_plan` with the item name **and `current_skills`** from Step 0:

```python
# With ESI data (accurate delta-based times):
skills(action="easy_80_plan", item="Vexor Navy Issue", current_skills={"Gallente Cruiser": 3, "Drones": 5, ...})

# Without ESI (from-scratch fallback — warn the user):
skills(action="easy_80_plan", item="Vexor Navy Issue")
```

> **⚠️ WARNING:** Calling `easy_80_plan` without `current_skills` calculates ALL training times from level 0. A pilot who already has Drones V will see "train Drones V: 5d 15h" instead of "✓ already trained". Always pass `current_skills` when ESI is available.

The tool returns:
- `easy_80_plan`: Categorized skills
  - `required_at_level`: Skills that must be at their required level
  - `cap_at_4`: Skills to cap at Level IV for Easy 80%
  - `train_to_5`: Skills recommended at V (T2 requirements)
- `easy_80_time`: Training time breakdown for the plan
- `full_mastery_time`: Time for all skills to V (comparison)
- `time_savings`: Seconds saved and percentage
- `efficacy_estimate`: Approximate % effectiveness
- `multiplier_skills`: High-impact skills flagged

### Step 3: Check for T2 Requirements (Modules Only)

For T2 modules, also call `skill_t2_requirements`:

```
skill_t2_requirements(item="Medium Armor Repairer II")
```

Returns:
- `skills_requiring_v`: Skills that must be at Level V
- `meta_alternatives`: Suggested alternatives to avoid V requirements

### Step 4: Apply Easy 80% Rules

The `skill_easy_80_plan` tool automatically applies these rules:

1. **Cap most skills at Level IV** - 80% bonus for ~20% of total time
2. **Train to V only when required** - T2 modules, ship prerequisites
3. **Identify multiplier skills** - Skills with outsized impact (Drone Interfacing, etc.)
4. **Calculate efficacy** - Estimate effectiveness at Easy 80% levels

### Step 5: Format Output

## Response Format

```
===============================================================================
ARIA SKILL PLAN
[Item Name] - [Category]
-------------------------------------------------------------------------------
REQUIREMENTS TO USE:
  [Skill Name] [Level]        [Training Time] (prerequisite: [Parent Skill])
  ...

  Total: [X] skills, [Time] training
-------------------------------------------------------------------------------
EASY 80% PLAN (Level IV caps):
  [Skill Name] IV             [Training Time]
  ...

  Total: [Time] training
  Estimated efficacy: ~80-85% of maximum potential
-------------------------------------------------------------------------------
FULL MASTERY (all to V):
  [Skill Name] V              [Training Time]
  ...

  Total: [Time] training
===============================================================================
```

## Item Type Handling

### Ships

For ships, show:
1. **Requirements to sit in hull** - Minimum skills to board
2. **Easy 80%** - Level IV on hull skill + relevant support skills
3. **Full Mastery** - All to V for maximum performance

Ship bonuses come from the hull skill level, so Level IV = 80% of hull bonuses.

### Modules

For modules, show:
1. **Requirements to fit** - All prerequisite skills at required levels
2. **Easy 80%** - Often same as requirements (T2 has hard reqs)
3. **Meta alternatives** - If T2 requires V, suggest meta 4 options

Note: T2 modules have fixed requirements. Recommend meta alternatives when T2 requires Level V skills.

### Skills

For skills, show:
1. **Prerequisites** - Skills needed before training this one
2. **Training time by level** - Time for each level I-V
3. **What it unlocks** - Ships/modules that require this skill

### Activities

For activities (mining, exploration, missions, etc.), use `activity_skill_plan`:

```
activity_skill_plan(activity="gas huffing", tier="all")
```

Activities have three tiers:
- **minimum**: Bare minimum to participate (often inefficient)
- **easy_80**: ~80% effectiveness with reasonable training
- **full**: Maximum effectiveness

Some activities are parameterized (e.g., R&D agents need a research field):
```
activity_skill_plan(activity="research agents", parameters={"field": "Mechanical Engineering"})
```

Use `activity_list` to see available activities by category:
- mining: Basic mining, barge, gas, ice
- exploration: Scanning, hacking, wormholes
- combat: Missions L1-L4, ratting, abyssal, faction warfare
- industry: Manufacturing T1/T2, reprocessing, PI
- research: R&D agents, blueprint research, copying
- trade: Station trading, hauling

## Training Time Reference

| Level | Multiplier | Cumulative Time (Rank 1) |
|-------|------------|--------------------------|
| I | 1x | ~8 min |
| II | 6x | ~45 min |
| III | 32x | ~4h 20min |
| IV | 181x | ~1d 30min |
| V | 1024x | ~5d 15h |

**Key insight:** Level V takes ~4.5x longer than I-IV combined, but only adds 20% more bonus.

## Default Attributes

When calculating training time, use balanced attributes if not specified:
- Intelligence: 20
- Memory: 20
- Perception: 20
- Willpower: 20
- Charisma: 19

This represents a fresh character with no implants or remaps.

## Error Handling

| Error | Response |
|-------|----------|
| Item not found | "Item '[name]' not found in SDE. Did you mean: [suggestions]?" |
| No skill data | "Skill data not available. The SDE may need updating." |
| MCP unavailable | "Skill planning requires the SDE MCP server to be running." |

## Example Outputs

### Ship Example (with ESI — pilot-aware)

```
===============================================================================
ARIA SKILL PLAN
Vexor Navy Issue - Cruiser
-------------------------------------------------------------------------------
REQUIREMENTS TO SIT IN HULL:
  Spaceship Command III       ✓ you have IV
  Gallente Frigate III        ✓ you have III
  Gallente Destroyer III      ✓ you have III
  Gallente Cruiser III        ~1d 1h (you have II → III)

  Remaining: 1 skill to train, ~1d 1h
-------------------------------------------------------------------------------
EASY 80% PLAN:
  Gallente Cruiser IV         ~3d 21h (from III → IV)
  Drone Interfacing IV        ✓ you have IV
  Medium Drone Operation IV   ~1d 20h (from I → IV)
  Drones V                    ✓ you have V

  Remaining: ~5d 17h training
  Estimated efficacy: ~82% of max DPS, ~85% drone HP
-------------------------------------------------------------------------------
FULL MASTERY:
  Gallente Cruiser V          ~24d 18h (from III → V)
  Medium Drone Operation V    ~10d 10h (from I → V)
  ...

  Remaining: ~35d training
===============================================================================
```

### Ship Example (ESI unavailable — from-scratch fallback)

```
===============================================================================
ARIA SKILL PLAN
Vexor Navy Issue - Cruiser

⚠️ ESI offline — all training times are FROM-SCRATCH estimates.
   Actual remaining time will be lower if you already have some skills.
-------------------------------------------------------------------------------
REQUIREMENTS TO SIT IN HULL:
  Spaceship Command III       ~4h 20min
  Gallente Frigate III        ~4h 20min
  Gallente Destroyer III      ~8h 40min
  Gallente Cruiser III        ~1d 1h

  Total: 4 skills, ~1d 18h from scratch
-------------------------------------------------------------------------------
EASY 80% PLAN:
  Gallente Cruiser IV         ~4d 22h
  Drone Interfacing IV        ~4d 22h
  Medium Drone Operation IV   ~1d 20h
  Drones V                    ~5d 15h

  Total: ~16d 19h from scratch
  Estimated efficacy: ~82% of max DPS, ~85% drone HP
===============================================================================
```

### Module Example

```
===============================================================================
ARIA SKILL PLAN
Medium Armor Repairer II - Module
-------------------------------------------------------------------------------
REQUIREMENTS TO FIT:
  Mechanics V                 ~4d 9h (prerequisite for T2)
  Repair Systems IV           ~1d 20h
  Hull Upgrades IV            ~1d 20h

  Total: 3 skills, ~7d 15h training
-------------------------------------------------------------------------------
EASY 80%:
  Same as above - T2 modules have fixed requirements

  Meta 4 Alternative: 'Meditation' Medium Armor Repairer I
  - Requires only Repair Systems I
  - ~90% of T2 rep amount
  - Saves ~7d training time
===============================================================================
```

### Activity Example

```
===============================================================================
ARIA SKILL PLAN
Gas Cloud Harvesting - Activity
-------------------------------------------------------------------------------
MINIMUM (to start):
  Mining IV                   (prerequisite for Gas Cloud Harvesting)
  Mining Frigate I            ~8min
  Gas Cloud Harvesting I      ~4h

  Total: ~4h 10min to start huffing in a Venture
-------------------------------------------------------------------------------
EASY 80% PLAN:
  Mining Frigate IV           ~1d 1h
  Gas Cloud Harvesting IV     ~1d 20h

  Total: ~3d training
  Yield: ~80% of maximum m³/hour
-------------------------------------------------------------------------------
FULL MASTERY:
  Mining Frigate V            ~4d 22h
  Gas Cloud Harvesting V      ~9d 6h
  Expedition Frigates IV      ~4d 22h (for Prospect)

  Total: ~19d training

SHIPS: Venture (minimum), Prospect (advanced, can cloak)
NOTES:
  - Gas sites spawn rats after 15-20 minutes
  - Most valuable gas is in wormholes and null-sec
===============================================================================
```

## Contextual Suggestions

After providing a skill plan, suggest ONE relevant follow-up:

| Context | Suggest |
|---------|---------|
| Ship skill plan | "Check `/fitting` for recommended fits" |
| Module with hard reqs | "Try `/find` to locate the module" |
| Long training time | "Your `/skillqueue` shows current training" |

## Multiplier Skills

Some skills have outsized impact on effectiveness. Use `skill_get_multipliers` to identify these:

| Skill | Effect | Priority |
|-------|--------|----------|
| Drone Interfacing | +10% drone damage/level | High |
| Surgical Strike | +3% turret damage/level | Medium |
| Rapid Firing | +4% turret ROF/level | Medium |
| Warhead Upgrades | +2% missile damage/level | Medium |
| Rapid Launch | +3% missile ROF/level | Medium |
| Astrogeology | +5% mining yield/level | High |

Train these to IV minimum, even if not strictly required.

## Reference Data

For detailed efficacy rules, meta alternatives, and activity definitions:
- `reference/skills/ship_efficacy_rules.yaml` - Per-role skill impact data
- `reference/skills/meta_module_alternatives.yaml` - T2 → Meta 4 suggestions
- `reference/activities/skill_plans.yaml` - Activity skill templates

## Behavior Notes

- Default to showing both requirements and Easy 80% plan
- Always explain the tradeoff between training time and effectiveness
- For T2 items, clearly note when Level V is mandatory
- Suggest meta alternatives when appropriate
- Keep output focused - details on request
- Highlight multiplier skills that have high impact

## Persona Adaptation

This skill supports persona overlays. When active persona has an overlay file, load additional context from:

```
personas/{active_persona}/skill-overlays/skillplan.md
```
