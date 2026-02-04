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
requires_pilot: false
esi_scopes: []
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

## ESI Availability Check

**Note:** This skill primarily uses MCP tools (`sde`, `skills` dispatchers) which work without ESI.

However, if you want to show "you already have X" context:

### If ESI is UNAVAILABLE:

1. **DO NOT** run `uv run aria-esi skills` - it will timeout
2. **USE** profile `module_tier` field to estimate capability:
   - `t1` → Assume base skills, no T2 modules
   - `t2` → Assume T2-capable for core skills
3. **PROCEED** with MCP-based skill plan (works fully)
4. **NOTE** if relevant: "Skill check unavailable (ESI offline) - showing full requirements"

### If ESI is AVAILABLE:

Optionally query `uv run aria-esi skills` to show which requirements the pilot already meets.

### Preferred Tool Flow

For most queries, use `skill_easy_80_plan` as the primary tool - it combines skill requirements, training time calculations, and Easy 80% logic in a single call:

```
skill_easy_80_plan(item="Vexor Navy Issue")
```

Returns:
- `easy_80_plan`: Categorized skills (required, cap_at_4, train_to_5)
- `easy_80_time`: Training time for Easy 80% plan
- `full_mastery_time`: Training time for all skills to V
- `time_savings`: How much time Easy 80% saves
- `efficacy_estimate`: Approximate effectiveness percentage
- `meta_suggestions`: Alternatives for T2 items requiring Level V

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

Call `skill_easy_80_plan` with the item name:

```
skill_easy_80_plan(item="Vexor Navy Issue")
```

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

### Ship Example

```
===============================================================================
ARIA SKILL PLAN
Vexor Navy Issue - Cruiser
-------------------------------------------------------------------------------
REQUIREMENTS TO SIT IN HULL:
  Spaceship Command III       (you likely have this)
  Gallente Frigate III        ~4h 20min
  Gallente Destroyer III      ~8h 40min
  Gallente Cruiser III        ~1d 1h

  Total: 4 skills, ~1d 14h from scratch
-------------------------------------------------------------------------------
EASY 80% PLAN:
  Gallente Cruiser IV         ~4d 22h
  Drone Interfacing IV        ~4d 22h
  Medium Drone Operation IV   ~1d 20h
  Drones V                    (required for T2)

  Total: ~12d training
  Estimated efficacy: ~82% of max DPS, ~85% drone HP
-------------------------------------------------------------------------------
FULL MASTERY:
  Gallente Cruiser V          ~24d 18h
  Drone Interfacing V         ~24d 18h
  Medium Drone Operation V    ~9d 6h
  ...

  Total: ~89d training
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
