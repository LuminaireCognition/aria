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

## Fuel Block Reference (MANDATORY)

All fuel block queries — including simple enumerations — must use this table. Never answer from memory.

| Fuel Block | Faction | Isotope |
|------------|---------|---------|
| Nitrogen Fuel Block | Caldari | Nitrogen Isotopes |
| Hydrogen Fuel Block | Minmatar | Hydrogen Isotopes |
| Helium Fuel Block | Amarr | Helium Isotopes |
| Oxygen Fuel Block | Gallente | Oxygen Isotopes |

## Tool Calls

| Step | Call | Purpose |
|------|------|---------|
| 1 | `sde(action="blueprint_info", item="<Name> Fuel Block")` | Materials, quantities |
| 2 | `market(action="prices", items=[...all inputs + output...])` | All prices in one call |

Fetch ALL material prices in a single `market(prices)` call. Never split across multiple queries.

## Reaction Time Formula

```
effective_time = base_time × (1 - skill × 0.04) × (1 - refinery_bonus)
```

Refinery bonuses: Athanor 0%, Tatara 25%. Reactions V + Tatara: 60% of base time.

## Response Format

```
## Fuel Block Production: [Name] Fuel Block

**Faction:** [from reference table]
**Isotope:** [from reference table]
**Runs:** [N] (Output: [N × 40] blocks)

### Input Materials

| Material | Per Run | Total | Price | Cost |
|----------|---------|-------|-------|------|
| [from blueprint_info] | ... | ... | ... | ... |

**Total Input Cost:** [computed]
**Cost Per Block:** [computed]

### Profitability

| Metric | Value |
|--------|-------|
| Total Cost | [computed] |
| Revenue | [computed] |
| **Gross Profit** | **[computed]** |
| **Margin** | **[computed]** |
```

## Rules

- **No ME on reactions** — input quantities are fixed (unlike manufacturing)
- All ISK figures from tool calls in this session
- Reactions run in refineries only (Athanor or Tatara)
