# Skill Planning Advisor Proposal

## Executive Summary

This proposal outlines a skill planning advisor that helps capsuleers understand training requirements for specific goals. Given an activity, ship, module, or R&D agent, the advisor returns:

1. **Full requirements:** Complete skill list with total training time
2. **Easy 80%:** Skills to achieve ~80% efficacy without Level V grinds

The "Easy 80%" output applies the Pareto principle to EVE skill training—Level IV skills train in ~20% of the time of Level V but provide 80% of the benefit. This helps new and mid-game pilots prioritize training for practical effectiveness over theoretical perfection.

**Key dependency:** Requires SDE skill prerequisite data (currently not exposed by `sde_item_info`).

---

## Use Cases

### 1. Ship Readiness
```
> /skillplan ship Vexor Navy Issue

VEXOR NAVY ISSUE - SKILL REQUIREMENTS
═══════════════════════════════════════════════════════════════════
FULL REQUIREMENTS (to sit in hull):
  Gallente Cruiser III         ~2d 8h (you have III ✓)
  Spaceship Command III        (you have IV ✓)

FULL MASTERY (all bonuses at V):
  Gallente Cruiser V           ~24d 18h
  Medium Drone Operation V     ~9d 6h
  Drone Interfacing V          ~24d 18h
  ...
  Total: ~89 days

EASY 80% (Level IV caps):
  Gallente Cruiser IV          ~4d 22h
  Medium Drone Operation IV    ~1d 20h
  Drone Interfacing IV         ~4d 22h
  Drone Sharpshooting IV       ~1d 20h
  ...
  Total: ~18 days

  Efficacy: ~82% of max DPS, ~85% of drone HP
═══════════════════════════════════════════════════════════════════
```

### 2. R&D Agent Access
```
> /skillplan "level 2 mechanical engineering agent"

LEVEL 2 R&D AGENT - MECHANICAL ENGINEERING
═══════════════════════════════════════════════════════════════════
REQUIREMENTS:
  Science V                    (you have V ✓)
  Mechanics V                  ~4d 9h (you have III)
  Mechanical Engineering II    ~1.4h

  Total new training: ~4d 10h
  Standing required: 3.0 effective

ALTERNATIVE (fastest to any L2 R&D):
  Laser Physics II             ~1.4h (no additional prereqs)
  Quantum Physics II           ~1.4h (no additional prereqs)
═══════════════════════════════════════════════════════════════════
```

### 3. Module Fitting
```
> /skillplan module "Medium Armor Repairer II"

MEDIUM ARMOR REPAIRER II
═══════════════════════════════════════════════════════════════════
REQUIREMENTS (to fit):
  Repair Systems IV            ~1d 20h (you have II)
  Mechanics V                  ~4d 9h (you have III)
  Hull Upgrades IV             ~1d 20h (you have III)

  Total: ~7d 15h

EASY 80% (operational):
  Same as above - T2 modules have hard requirements

  Note: T2 requires exact skills. Consider Meta 4 alternative:
  - 'Meditation' Medium Armor Repairer I
  - Requires only Repair Systems I
  - ~90% of T2 rep amount
═══════════════════════════════════════════════════════════════════
```

### 4. Activity Planning
```
> /skillplan activity "gas huffing"

GAS HARVESTING
═══════════════════════════════════════════════════════════════════
MINIMUM VIABLE:
  Mining Frigate I             ~20 min
  Gas Cloud Harvesting I       ~4h (requires Mining IV)
  Mining IV                    ~1d 1h (you have IV ✓)

  Total: ~4h 20min to start huffing

EASY 80%:
  Gas Cloud Harvesting IV      ~1d 20h
  Mining Frigate IV            ~1d 1h

  Total: ~3d
  Yield: 80% of maximum m³/hour

FULL:
  Gas Cloud Harvesting V       ~9d 6h
  Mining Frigate V             ~4d 22h
  Expedition Frigates IV       ~4d 22h (Prospect)
  ...
═══════════════════════════════════════════════════════════════════
```

---

## The "Easy 80%" Philosophy

### EVE Skill Training Math

| Level | Training Time (Rank 1) | Cumulative | Bonus |
|-------|------------------------|------------|-------|
| I | 8 min | 8 min | 20% |
| II | 38 min | 46 min | 40% |
| III | 3h 34min | 4h 20min | 60% |
| IV | 20h 15min | 1d 30min | 80% |
| V | 4d 14h | 5d 15h | 100% |

**Key insight:** Level V takes ~4.5x longer than Levels I-IV combined, but only adds 20% more bonus.

### Easy 80% Rules

1. **Cap most skills at IV** - 80% bonus for 20% of total time
2. **Only train V when required** - T2 modules, ship prerequisites
3. **Identify the "multiplier" skills** - Some skills (Drone Interfacing, Surgical Strike) have outsized impact
4. **Suggest meta alternatives** - When T2 requires Level V, recommend meta modules

### Efficacy Calculation

For ships, calculate approximate effectiveness:

```python
def calculate_efficacy(skills_at_level: dict, max_levels: dict) -> float:
    """
    Calculate % of maximum potential.

    Example: Vexor Navy Issue drone DPS
    - Drone Interfacing: 10% damage per level
    - At IV: 40% bonus vs 50% at V = 40/50 = 80%

    Combined with other skills, total efficacy ~82%
    """
    total_efficacy = 1.0
    for skill, level in skills_at_level.items():
        max_level = max_levels[skill]
        skill_efficacy = level / max_level
        total_efficacy *= skill_efficacy  # Multiplicative for damage
    return total_efficacy
```

---

## Technical Requirements

### 1. SDE Skill Data Enhancement

**Current `sde_item_info` output:**
```json
{
  "type_id": 11452,
  "type_name": "Mechanical Engineering",
  "group_name": "Science",
  "category_name": "Skill"
}
```

**Required enhancement:**
```json
{
  "type_id": 11452,
  "type_name": "Mechanical Engineering",
  "group_name": "Science",
  "category_name": "Skill",
  "skill_info": {
    "rank": 5,
    "primary_attribute": "intelligence",
    "secondary_attribute": "memory",
    "prerequisites": [
      {"skill_id": 3392, "skill_name": "Mechanics", "level": 5},
      {"skill_id": 3402, "skill_name": "Science", "level": 5}
    ]
  }
}
```

**SDE tables required:**
- `dgmTypeAttributes` - Skill attributes (rank, prerequisites)
- `dogmaAttributes` - Attribute definitions (requiredSkill1, etc.)

### 2. New MCP Tool: `sde_skill_requirements`

```python
@server.tool()
async def sde_skill_requirements(
    item: str,
    include_prerequisites: bool = True,
    recursive: bool = True,
) -> SkillRequirementsResult:
    """
    Get skill requirements for an item (ship, module, skill).

    Args:
        item: Item name (ship, module, or skill)
        include_prerequisites: Include prereqs of prereqs
        recursive: Follow full prerequisite chain

    Returns:
        Complete skill tree with levels required
    """
```

**Output:**
```json
{
  "item": "Vexor Navy Issue",
  "type": "ship",
  "direct_requirements": [
    {"skill": "Gallente Cruiser", "level": 3}
  ],
  "full_tree": [
    {"skill": "Gallente Cruiser", "level": 3, "rank": 5},
    {"skill": "Gallente Destroyer", "level": 3, "rank": 4},
    {"skill": "Gallente Frigate", "level": 3, "rank": 2},
    {"skill": "Spaceship Command", "level": 3, "rank": 1}
  ],
  "mastery_skills": [
    {"skill": "Gallente Cruiser", "level": 5, "category": "hull"},
    {"skill": "Medium Drone Operation", "level": 5, "category": "weapon"},
    {"skill": "Drone Interfacing", "level": 5, "category": "damage"}
  ]
}
```

### 3. New MCP Tool: `skill_training_time`

```python
@server.tool()
async def skill_training_time(
    skills: list[dict],  # [{"skill": "Mechanics", "from_level": 3, "to_level": 5}]
    attributes: dict | None = None,  # {"intelligence": 27, "memory": 21}
    implants: dict | None = None,  # Attribute bonuses
) -> TrainingTimeResult:
    """
    Calculate training time for a skill plan.

    Uses standard formula:
    SP = 250 * rank * sqrt(primary * secondary)
    Time = SP / SP_per_minute
    """
```

### 4. Activity Definitions

Create activity templates that map to skill sets:

```yaml
# reference/activities/skill_plans.yaml
activities:
  gas_huffing:
    display_name: "Gas Cloud Harvesting"
    minimum:
      - skill: "Mining Frigate"
        level: 1
      - skill: "Gas Cloud Harvesting"
        level: 1
    easy_80:
      - skill: "Mining Frigate"
        level: 4
      - skill: "Gas Cloud Harvesting"
        level: 4
    full:
      - skill: "Mining Frigate"
        level: 5
      - skill: "Gas Cloud Harvesting"
        level: 5
      - skill: "Expedition Frigates"
        level: 4
        note: "For Prospect"

  r&d_agent_l2:
    display_name: "Level 2 R&D Agent"
    parameters:
      - name: field
        type: research_field
    minimum:
      - skill: "Science"
        level: 5
      - skill: "${field}"
        level: 2
    notes:
      - "Standing 3.0+ required with agent corporation"
      - "Connections skill reduces effective standing requirement"
```

---

## ARIA Skill: `/skillplan`

### File Location
`.claude/skills/skillplan/SKILL.md`

### Command Syntax

```
/skillplan ship <ship_name>              # Ship requirements
/skillplan module <module_name>          # Module requirements
/skillplan activity <activity>           # Activity skill plan
/skillplan skill <skill_name>            # Skill prerequisites
/skillplan "<goal description>"          # Natural language goal
```

### Options

```
--full          Show only full requirements (no Easy 80%)
--easy          Show only Easy 80% plan
--current       Compare against current skills (requires ESI)
--time-only     Show only total training times
```

### Data Flow

```
User Input
    │
    ▼
┌─────────────────────┐
│  Parse Goal Type    │
│  (ship/module/etc)  │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│  sde_skill_         │
│  requirements()     │◄─── SDE lookup
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│  Get Current Skills │◄─── ESI (optional)
│  (if authenticated) │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│  Calculate Deltas   │
│  & Training Times   │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│  Apply Easy 80%     │
│  Rules              │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│  Format Output      │
└─────────────────────┘
```

---

## Implementation Phases

### Phase 1: SDE Foundation
1. Add skill prerequisite queries to `sde_item_info`
2. Create `sde_skill_requirements` MCP tool
3. Add `skill_training_time` calculator

### Phase 2: Core Skill
1. Create `/skillplan` skill
2. Implement ship and module lookups
3. Add training time calculations

### Phase 3: Easy 80% Logic
1. Define efficacy rules per ship class
2. Implement mastery skill identification
3. Add meta module suggestions

### Phase 4: Activity Templates
1. Create activity definition format
2. Build initial activity library (mining, exploration, R&D, etc.)
3. Support parameterized activities

### Phase 5: Polish
1. ESI integration for current skill comparison
2. Skill queue optimization suggestions
3. "What can I fly now?" reverse lookup

---

## Open Questions

1. **Mastery data source:** EVE has official mastery levels per ship. Should we scrape these or define our own based on role effectiveness?

2. **Attribute remaps:** Should training time calculations assume optimal remaps? Show both?

3. **Implant assumptions:** Default to +3s? +4s? No implants? Make configurable?

4. **Activity scope:** How many pre-defined activities? Start minimal and expand, or comprehensive from day one?

5. **Efficacy precision:** How precise should efficacy calculations be? Rough percentages or exact DPS/tank numbers?

---

## Success Metrics

- Users can quickly assess training requirements for any goal
- "Easy 80%" recommendations reduce training time by 60%+ while maintaining viability
- Natural language queries resolve to correct skill plans 90%+ of the time
- No more web searches for "what skills do I need for X"

---

## Related Work

- [EVEMon](https://github.com/peterhaneve/evemon) - Desktop skill planner (Windows)
- [EVE Workbench](https://www.eveworkbench.com/) - Web-based fitting/planning
- [EVE University Wiki](https://wiki.eveuniversity.org/) - Skill documentation

The key differentiator is the "Easy 80%" philosophy and integration with ARIA's conversational interface.
