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
  - "min-max plan for [ship]"
  - "max out [ship] skills"
  - "priority training order for [ship]"
requires_pilot: true
esi_scopes:
  - esi-skills.read_skills.v1
prerequisite_files:
  - reference/activities/skill_plans.yaml
  - reference/skills/ship_efficacy_rules.yaml
  - reference/skills/meta_module_alternatives.yaml
external_sources: []
---

# ARIA Skill Planning Advisor

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

## MCP Tool Availability

**CRITICAL:** If MCP tools are unavailable, inform the user that skill planning requires the SDE MCP server.

> **HALLUCINATION GUARD:** Every training time, skill name, skill level, and efficacy estimate MUST come from MCP tool responses in this session. Training times are calculated server-side based on skill rank and attributes — do NOT estimate or fabricate training times from training data. If the tool did not return a training time for a specific skill, do not invent one.

### Field → Source Mapping

| Output Field | Required Source | Tool Call |
|-------------|----------------|-----------|
| Pilot's current skill levels | ESI skills endpoint | `uv run aria-esi skills` |
| Easy 80% plan (categorized skills) | Skills dispatcher | `skills(action="easy_80_plan", item="...", current_skills={...})` |
| Easy 80% training time | Skills dispatcher response `easy_80_time` | `skills(action="easy_80_plan", ...)` |
| Full mastery training time | Skills dispatcher response `full_mastery_time` | `skills(action="easy_80_plan", ...)` |
| Time savings (Easy 80% vs full) | Skills dispatcher response `time_savings` | `skills(action="easy_80_plan", ...)` |
| Efficacy estimate (% effectiveness) | Skills dispatcher response `efficacy_estimate` | `skills(action="easy_80_plan", ...)` |
| Meta module alternatives | Skills dispatcher response `meta_suggestions` | `skills(action="easy_80_plan", ...)` |
| Min-max phased plan | Skills dispatcher | `skills(action="minmax_plan", item="...", current_skills={...})` |
| T2 Level V requirements | Skills dispatcher | `skills(action="t2_requirements", item="...")` |
| Activity skill tiers | Skills dispatcher | `skills(action="activity_plan", activity="...", tier="all")` |
| Item category/description | SDE dispatcher | `sde(action="item_info", item="...")` (optional) |
| Ship efficacy rules | Prerequisite file | `reference/skills/ship_efficacy_rules.yaml` (pre-read) |
| Meta alternatives reference | Prerequisite file | `reference/skills/meta_module_alternatives.yaml` (pre-read) |

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

### Step 2b: Generate Min-Max Plan (Alternative)

For pilots who want a **priority-ordered training plan** rather than a flat skill list, use the min-max plan instead of (or in addition to) Easy 80%:

```python
skills(action="minmax_plan", item="Ishtar", current_skills=current_skills)
skills(action="minmax_plan", item="Ark", roles=["jump_capable", "hauler"], current_skills=current_skills)
```

**When to use minmax vs easy_80:**

| Scenario | Recommendation |
|----------|---------------|
| Quick "what do I need?" overview | `easy_80_plan` |
| Optimal training order for a specific ship | `minmax_plan` |
| Non-ship items (modules, skills) | `easy_80_plan` (unless roles specified) |
| Pilot wants phased progression | `minmax_plan` |

The min-max plan returns three phases:
- **Phase 1 — Get Online:** SDE prerequisites at exact required levels (board the ship)
- **Phase 2 — Get Effective:** Breakpoints, multipliers, and role skills to IV, ordered by effectiveness/SP
- **Phase 3 — Get Maximal:** All remaining role-relevant skills to V

Each phase includes efficacy estimates showing effectiveness at that training milestone.

### Step 3: Check for T2 Requirements (Modules Only)

For T2 modules, also call `skill_t2_requirements`:

```
skill_t2_requirements(item="Medium Armor Repairer II")
```

Returns:
- `skills_requiring_v`: Skills that must be at Level V
- `meta_alternatives`: Suggested alternatives to avoid V requirements

### Step 4: Format Output

The `easy_80_plan` response includes categorized skills, efficacy estimates, and multiplier flags. Present these directly.

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

**Key insight:** Level V takes ~4.5x longer than I-IV combined, but only adds 20% more bonus. This is why the Easy 80% plan caps most skills at IV.

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

Same format as above, but prepend the warning banner and label all times "from scratch":

```
⚠️ ESI offline — all training times are FROM-SCRATCH estimates.
   Actual remaining time will be lower if you already have some skills.
```

### Module Example

Same structure as ship example. Unique aspects for modules:
- T2 modules have fixed requirements — Easy 80% may equal full requirements
- Show **Meta 4 Alternative** when T2 requires Level V (name, reduced requirements, approximate performance vs T2)

### Activity Example

Activity plans use three tiers instead of the ship/module format:
- **MINIMUM** — bare minimum to participate (from `activity_plan` tier="minimum")
- **EASY 80%** — ~80% effectiveness (tier="easy_80")
- **FULL** — maximum effectiveness (tier="full")

Include recommended ships and activity-specific notes from the tool response.

## Multiplier Skills

Use `skills(action="get_multipliers")` to identify high-impact skills with outsized effectiveness per level. Train these to IV minimum, even if not strictly required.

## Anti-Patterns

❌ **WRONG:** Show "Gallente Cruiser V: 29d 11h" when no MCP response contained that training time
✅ **RIGHT:** Training times come ONLY from `skills(action="easy_80_plan")` or `skills(action="training_time")` responses

❌ **WRONG:** Call `sde(action="skill_requirements")` alongside `easy_80_plan` (the plan already includes prerequisites)
✅ **RIGHT:** Follow the Golden Path — `easy_80_plan` returns the full categorized prerequisite tree

❌ **WRONG:** Present per-skill training times that don't appear in any tool response field
✅ **RIGHT:** The `easy_80_plan` response includes `easy_80_time` and `full_mastery_time` totals — use those

❌ **WRONG:** Call `easy_80_plan` without `current_skills` and present times as accurate
✅ **RIGHT:** Without `current_skills`, ALL times are from-scratch estimates. Show the ⚠️ ESI warning.

## Behavior Notes

- Default to showing both requirements and Easy 80% plan
- Always explain the tradeoff between training time and effectiveness
- For T2 items, clearly note when Level V is mandatory
- Suggest meta alternatives when appropriate
- Keep output focused - details on request
- Highlight multiplier skills that have high impact
