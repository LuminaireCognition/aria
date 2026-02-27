---
name: reactions
description: Moon material reactions and fuel block calculator. Calculate costs, profits, and production times for reactions.
model: haiku
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

# ARIA Reactions Calculator

**Scope:** Fuel blocks and common reactions. Does not cover T2 component manufacturing (use `/build-cost` with `--full-chain` for those).

## Command Syntax

```
/reactions fuel-blocks                     # List all fuel block types
/reactions fuel-blocks <type>              # Cost for specific fuel block
/reactions fuel-blocks <type> --runs 100   # Multiple runs
/reactions fuel-blocks <type> --skill 5    # With Reactions skill level
/reactions fuel-blocks <type> --refinery Tatara  # With refinery bonus
```

## Key Difference: Reactions vs Manufacturing

| Aspect | Manufacturing | Reactions |
|--------|--------------|-----------|
| Material Efficiency | ME 0-10 (-10%) | **No ME** - fixed inputs |
| Time Efficiency | TE 0-20 (-20%) | Reactions skill (-4%/level) |
| Location | Any station/structure | **Refinery only** |
| Slot skill | Mass Production | Mass Reactions |
| Time bonus structure | Engineering Complex | Refinery (Tatara: -25%) |

## Execution Flow

1. **Identify fuel block type:** Use `sde(action="blueprint_info", item="<Name> Fuel Block")` to get the blueprint, material inputs, and quantities. SDE categorizes fuel blocks as "Material", not "Charge".
2. **Fetch all material prices in one call:** `market(action="prices", items=[...all inputs + output...])`. **CRITICAL:** Always fetch ALL material prices in a single call. Never split across multiple queries.
3. **Calculate cost:** Use `calculate_fuel_block_cost()` from `aria_esi.services.reactions` with `fuel_block_name`, `material_prices`, `reactions_skill` (0-5), `refinery_name` ("Tatara" or "Athanor"), and `runs`.
4. **Calculate profit (optional):** Use `calculate_fuel_block_profit()` with the same params plus `fuel_block_price` from market data.
5. **Format output:** Use `format_fuel_block_summary()`.

## Reaction Time Formula

```
effective_time = base_time * (1 - reactions_skill * 0.04) * (1 - refinery_bonus)
```

Refinery bonuses: Athanor 0%, Tatara 25%. With Reactions V + Tatara: multiplicative 1 - (0.8 * 0.75) = 40% reduction.

## Response Format

```
## Fuel Block Production: [Name] Fuel Block

**Faction:** [Faction]
**Isotope:** [Isotope type]
**Runs:** [N] (Output: [N * 40] blocks)

### Input Materials

| Material | Per Run | Total | Price | Cost |
|----------|---------|-------|-------|------|
| [from blueprint_info] | [computed] | [computed] | [fetched] | [computed] |

**Total Input Cost:** [computed]
**Cost Per Block:** [computed]

### Production Time

| Setting | Value |
|---------|-------|
| Base Cycle | [from blueprint] |
| Reactions Skill | -[skill * 4]% |
| Refinery | -[bonus]% |
| **Total Time** | **[computed]** |

### Profitability

| Metric | Value |
|--------|-------|
| Total Cost | [computed] |
| Revenue | [computed] |
| **Gross Profit** | **[computed]** |
| **Margin** | **[computed]** |
| **Profit/Hour** | **[computed]** |
```

## Edge Cases

### Missing Material Prices

If any input prices are missing, display a warning and mark the cost calculation as incomplete.

### Unknown Fuel Block

If the fuel block name is not recognized, list the four available types: Nitrogen (Caldari), Hydrogen (Minmatar), Helium (Amarr), Oxygen (Gallente).

## DO NOT

- **DO NOT** apply ME to reactions - they have fixed input quantities
