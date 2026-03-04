---
name: reactions
description: Moon material reactions and fuel block reference data. Authoritative source for fuel block types, factions, and recipes. Calculate costs, profits, and production times.
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

All fuel block attributes MUST come from `reference/industry/fuel_blocks.json` (project-root-relative path, not skill-directory path). If the file wasn't loaded, read it before answering. If a read fails, report the exact path that failed — do not substitute training data. Never answer fuel block queries from training data alone.

> **Confabulation risk:** Training data maps fuel block factions incorrectly (Hydrogen→Caldari, Nitrogen→Gallente, Oxygen→Minmatar — all wrong). Always use the reference table below.

### Fuel Block Reference (from fuel_blocks.json)

| Fuel Block | Faction | Isotope | Type ID |
|---|---|---|---|
| Nitrogen Fuel Block | **Caldari** | Nitrogen Isotopes | 4051 |
| Hydrogen Fuel Block | **Minmatar** | Hydrogen Isotopes | 4246 |
| Helium Fuel Block | **Amarr** | Helium Isotopes | 4247 |
| Oxygen Fuel Block | **Gallente** | Oxygen Isotopes | 4312 |

For enumeration queries ("list fuel block types" etc.), output this table directly.

### Data Sources

| Field | Source |
|---|---|
| Names, factions, isotopes, type IDs | Reference table above / `fuel_blocks.json` |
| Material quantities | `fuel_blocks.json` inputs; cross-check with `sde(blueprint_info)` |
| Prices | `market(prices)` — single call for all inputs + output |
| Refinery bonuses | `fuel_blocks.json` → `refinery_bonuses` |
| Cycle time | `fuel_blocks.json` → `cycle_time_seconds` (SDE returns null for reaction blueprints — do NOT query SDE for this value) |

## Production Time

```
effective_time = cycle_time × (1 - skill_level × 0.04) × (1 - refinery_bonus)
```

**Cycle time:** Use `cycle_time_seconds` from `fuel_blocks.json` (3600s / 1h per run). Do not query SDE for this value — `sde(blueprint_info)` returns null for fuel block blueprints because they use the reactions activity rather than standard manufacturing.

Refinery bonuses: Athanor 0%, Tatara 25%. Reactions V + Tatara: 63% of base time.

**Example — 100 runs, Reactions IV, Tatara:**
`effective_time = 3600 × (1 − 4×0.04) × (1 − 0.25) = 3600 × 0.84 × 0.75 = 2268s per run`
Total = 100 × 2268s = 226,800s ≈ 63.0h

## Response Format

```
## Fuel Block Production: [Name] Fuel Block

**Faction:** [from reference] | **Isotope:** [from reference]
**Runs:** [N] | **Output:** [N × output_quantity] blocks

### Input Materials

| Material | Per Run | Total | Price | Cost |
|----------|---------|-------|-------|------|

**Total Input Cost:** [computed]
**Cost Per Block:** [computed]

### Profitability

| Metric | Value |
|--------|-------|
| Revenue | ... |
| Total Cost | ... |
| **Gross Profit** | **...** |
| **Margin** | **...** |
```

## Rules

- No ME on reactions — input quantities are fixed (unlike manufacturing)
- All prices from `market(prices)` in this session — never from training data
- Reactions run in refineries only (Athanor or Tatara)
- For fit queries → redirect to `/fitting`
