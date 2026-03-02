---
name: reactions
description: Moon material reactions and fuel block calculator. Calculate costs, profits, and production times for reactions.
model: sonnet
category: industry
triggers:
  - "/reactions"
  - "fuel block cost"
  - "fuel block types"
  - "fuel blocks"
  - "reaction profitability"
  - "how much to make [fuel block]"
  - "fuel block calculator"
  - "reaction time"
requires_pilot: false
prerequisite_files:
  - reference/industry/fuel_blocks.json
---

# Reactions Calculator

**Scope:** Fuel blocks and common reactions. T2 component manufacturing → `/build-cost`.

```
/reactions fuel-blocks                     # List all fuel block types
/reactions fuel-blocks <type>              # Cost for specific fuel block
/reactions fuel-blocks <type> --runs 100   # Multiple runs
/reactions fuel-blocks <type> --skill 5    # With Reactions skill level
/reactions fuel-blocks <type> --refinery Tatara  # With refinery bonus
```

## Data Gate

Read `reference/industry/fuel_blocks.json` before any output — including simple enumerations like "list all fuel block types". If the file could not be read or is empty, state "no verified data available" — do not answer from training data.

> **HALLUCINATION GUARD:** Every fuel block name, faction, isotope, type ID, and material quantity MUST come from `fuel_blocks.json` (loaded via `prerequisite_files`). Fuel block faction mappings are a **known confabulation risk** — training data maps them incorrectly. Do NOT recite fuel block attributes from memory. If the reference file wasn't loaded, STOP and load it before answering.

### Field → Source Mapping

| Output Field | Required Source |
|-------------|----------------|
| Fuel block names, type IDs | `fuel_blocks.json` → `fuel_blocks` keys and `type_id` |
| Faction per fuel block | `fuel_blocks.json` → each block's `faction` field |
| Isotope per fuel block | `fuel_blocks.json` → each block's `isotope` field |
| Material quantities | `sde(blueprint_info)` — cross-check against `fuel_blocks.json`, trust SDE on disagreement |
| Prices | `market(prices)` — single call for all inputs + output |
| Reaction time, refinery bonuses | `fuel_blocks.json` → `refinery_bonuses` |
| Total cost / Revenue / Profit | Computed from above |

### Authoritative Fuel Block Reference (from fuel_blocks.json)

| Fuel Block | Faction | Isotope | Type ID |
|---|---|---|---|
| Nitrogen Fuel Block | **Caldari** | Nitrogen Isotopes | 4051 |
| Hydrogen Fuel Block | **Minmatar** | Hydrogen Isotopes | 4246 |
| Helium Fuel Block | **Amarr** | Helium Isotopes | 4247 |
| Oxygen Fuel Block | **Gallente** | Oxygen Isotopes | 4312 |

**Use this table for all fuel block identity queries.** For material quantities and prices, read the full JSON file + call market/SDE tools.

### Anti-Patterns

❌ **WRONG:** Answer "list all fuel block types" without consulting the reference table
✅ **RIGHT:** Copy faction, isotope, and type_id fields verbatim from the table above — no exceptions, no substitution from memory

## Reaction Time

```
effective_time = cycle_time × (1 - skill × 0.04) × (1 - refinery_bonus)
```

Refinery bonuses: Athanor 0%, Tatara 25%. Reactions V + Tatara: 63% of base time.

## Response Format

```
## Fuel Block Production: [Name] Fuel Block

**Faction:** [from fuel_blocks.json] | **Isotope:** [from fuel_blocks.json]
**Runs:** [N] (Output: [N × output_quantity] blocks)

### Input Materials

| Material | Per Run | Total | Price | Cost |
|----------|---------|-------|-------|------|

**Total Input Cost:** [computed]
**Cost Per Block:** [computed]

### Profitability

| Metric | Value |
|--------|-------|
| Total Cost | ... |
| Revenue | ... |
| **Gross Profit** | **...** |
| **Margin** | **...** |
```

## Rules

- No ME on reactions — input quantities are fixed (unlike manufacturing)
- All ISK figures from tool calls in this session — never from training data
- Reactions run in refineries only (Athanor or Tatara)
- For fit queries → redirect to `/fitting`
