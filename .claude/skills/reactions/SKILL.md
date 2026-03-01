---
name: reactions
description: Moon material reactions and fuel block calculator. Calculate costs, profits, and production times for reactions.
model: sonnet
category: industry
triggers:
  - "/reactions"
  - "fuel block cost"
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

Read `reference/industry/fuel_blocks.json` before any output. If the file could not be read or is empty, state "no verified data available" — do not answer from training data.

Every fuel block type, faction, and isotope in the response must come from `fuel_blocks.json`. Material quantities and prices for cost queries come from SDE and market tool calls.

## Source Rules

| Field | Source |
|-------|--------|
| Fuel block types, factions, isotopes | `fuel_blocks.json` |
| Material quantities | `sde(blueprint_info)` — cross-check against `fuel_blocks.json`, trust SDE on disagreement |
| Prices | `market(prices)` — single call for all inputs + output |
| Reaction time, refinery bonuses | `fuel_blocks.json` → `reaction_time_modifiers`, `refinery_bonuses` |
| Total cost / Revenue / Profit | Computed from above |

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
