---
name: skillplan
description: Skill planning advisor for EVE Online. Analyze skill requirements for ships, modules, or activities with training time estimates and "Easy 80%" recommendations. IMPORTANT: Always invoke this skill before calling skills or sde MCP tools. This skill loads reference data required for accurate responses.
model: sonnet
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
injected_prerequisites:
  - reference/activities/skill_plans.yaml
  - reference/skills/ship_efficacy_rules.yaml
  - reference/skills/meta_module_alternatives.yaml
  - .claude/skills/_shared/esi-error-handling.md
external_sources: []
argument-hint: "<ship|module|activity>"
---

# ARIA Skill Planning Advisor

## MCP Tool Availability

**CRITICAL:** If MCP tools are unavailable, inform the user that skill planning requires the SDE MCP server.

## Data Gate

All prerequisite reference files (skill plans, ship efficacy rules, meta module alternatives, ESI error handling) are injected below — do not re-read them.

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
| Ship efficacy rules | Prerequisite file | `reference/skills/ship_efficacy_rules.yaml` (pre-read) |
| Meta alternatives reference | Prerequisite file | `reference/skills/meta_module_alternatives.yaml` (pre-read) |

## Pilot Skills — Mandatory for Accurate Training Times

**CRITICAL:** Training time estimates are **wrong** if `current_skills` is not passed to `easy_80_plan`. Without it, all times calculate from level 0 — massively overstating training needed.

Load pilot skills via `uv run aria-esi skills` and build a `{name: level}` dict to pass as `current_skills` to every plan call.

### Golden Path — Minimal MCP Call Sequence

For most queries, the optimal call sequence is:

1. **`uv run aria-esi skills`** → fetch pilot's current skills (when ESI available)
2. **`skills(action="easy_80_plan", item="...", current_skills={...})`** → generates the full plan with accurate delta-based training times

That's it. Two calls. The `easy_80_plan` response includes:
- `easy_80_plan`: Categorized skills (required, cap_at_4, train_to_5)
- `easy_80_time`: Training time breakdown for the plan
- `full_mastery_time`: Training time for all skills to V (comparison)
- `time_savings`: How much time Easy 80% saves
- `efficacy_estimate`: Approximate effectiveness percentage
- `meta_suggestions`: Alternatives for T2 items requiring Level V

**Optional third call:** `sde(action="item_info", item="...")` — only if you need item description, category, or other metadata not included in the plan response.

For **min-max plans** (priority-ordered training), use `skills(action="minmax_plan", item="...", current_skills={...})` instead. Returns three phases: Get Online, Get Effective, Get Maximal — each with efficacy estimates.

For **activity plans** (mining, exploration, etc.), use `skills(action="activity_plan", activity="...", tier="all")` which returns minimum, easy_80, and full tiers.

## Anti-Patterns

> **Anti-Pattern:** Do NOT call `sde(action="skill_requirements")` alongside `easy_80_plan`. The `easy_80_plan` response already contains the full prerequisite tree, categorized into training tiers. Calling both is redundant and wastes a round-trip.

❌ **WRONG:** Show "Gallente Cruiser V: 29d 11h" when no MCP response contained that training time
✅ **RIGHT:** Training times come ONLY from `skills(action="easy_80_plan")` or `skills(action="training_time")` responses

❌ **WRONG:** Call `sde(action="skill_requirements")` alongside `easy_80_plan` (the plan already includes prerequisites)
✅ **RIGHT:** Follow the Golden Path — `easy_80_plan` returns the full categorized prerequisite tree

❌ **WRONG:** Present per-skill training times that don't appear in any tool response field
✅ **RIGHT:** The `easy_80_plan` response includes `easy_80_time` and `full_mastery_time` totals — use those

❌ **WRONG:** Call `easy_80_plan` without `current_skills` and present times as accurate
✅ **RIGHT:** Without `current_skills`, ALL times are from-scratch estimates. Show the warning.

## Injected Reference Data

### Reference: Skill Plans (injected)
<!-- prerequisite: reference/activities/skill_plans.yaml -->
!`cat reference/activities/skill_plans.yaml`

### Reference: Ship Efficacy Rules (injected)
<!-- prerequisite: reference/skills/ship_efficacy_rules.yaml -->
!`cat reference/skills/ship_efficacy_rules.yaml`

### Reference: Meta Module Alternatives (injected)
<!-- prerequisite: reference/skills/meta_module_alternatives.yaml -->
!`cat reference/skills/meta_module_alternatives.yaml`

### Reference: ESI Error Handling (injected)
<!-- prerequisite: .claude/skills/_shared/esi-error-handling.md -->
!`cat .claude/skills/_shared/esi-error-handling.md`
