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

## Purpose

Calculate costs, production times, and profitability for moon material reactions and fuel blocks. Helps industrialists optimize their reaction operations.

**Scope:** Fuel blocks and common reactions. Does not cover T2 component manufacturing (use `/build-cost` with `--full-chain` for those).

## Trigger Phrases

- "/reactions"
- "fuel block cost"
- "reaction profitability"
- "how much to make [fuel block]"
- "fuel block calculator"

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

## Implementation

### Step 1: Get Fuel Block Info

```python
from aria_esi.services.reactions import (
    get_fuel_block_info,
    list_fuel_blocks,
    calculate_fuel_block_cost,
    calculate_fuel_block_profit,
    format_fuel_block_summary,
)

# List all fuel blocks
fuel_blocks = list_fuel_blocks()
# [{"name": "Nitrogen Fuel Block", "faction": "Caldari", ...}, ...]

# Get specific fuel block
fb = get_fuel_block_info("Nitrogen")
# {"name": "Nitrogen Fuel Block", "faction": "Caldari", "isotope": "Nitrogen Isotopes",
#  "inputs": {"Coolant": 150, "Enriched Uranium": 150, ...}, "output_quantity": 40, ...}
```

### Step 2: Get Material Prices

```python
# Get all input material names
material_names = list(fb["inputs"].keys())
material_names.append(fb["name"])  # Add fuel block for profit calc

# Query prices
prices_result = market(action="prices", items=material_names)

# Build price dict
material_prices = {}
for item in prices_result.get("items", []):
    material_prices[item["type_name"]] = item.get("sell_min", 0)
```

### Step 3: Calculate Cost

```python
cost_result = calculate_fuel_block_cost(
    fuel_block_name="Nitrogen Fuel Block",
    material_prices=material_prices,
    reactions_skill=4,        # 0-5
    refinery_name="Tatara",   # or "Athanor"
    runs=100,
)

# cost_result = {
#     "fuel_block": "Nitrogen Fuel Block",
#     "faction": "Caldari",
#     "runs": 100,
#     "total_output": 4000,
#     "total_input_cost": 12500000.0,
#     "cost_per_unit": 3125.0,
#     "production_time": {...},
#     ...
# }
```

### Step 4: Calculate Profit (Optional)

```python
profit_result = calculate_fuel_block_profit(
    fuel_block_name="Nitrogen Fuel Block",
    material_prices=material_prices,
    fuel_block_price=4500,    # Market price per block
    reactions_skill=4,
    refinery_name="Tatara",
    runs=100,
)

# profit_result includes:
# - gross_profit: revenue - cost
# - margin_percent: profit margin
# - profit_per_hour: ISK/hr
```

### Step 5: Format Output

```python
print(format_fuel_block_summary(profit_result))
```

## Response Format

```
## Fuel Block Production: Nitrogen Fuel Block

**Faction:** Caldari
**Isotope:** Nitrogen Isotopes
**Runs:** 100 (Output: 4,000 blocks)

### Input Materials

| Material | Per Run | Total | Price | Cost |
|----------|---------|-------|-------|------|
| Coolant | 150 | 15,000 | 10.5K ISK | 157.5M ISK |
| Enriched Uranium | 150 | 15,000 | 8.2K ISK | 123.0M ISK |
| Mechanical Parts | 150 | 15,000 | 9.1K ISK | 136.5M ISK |
| Oxygen | 450 | 45,000 | 450 ISK | 20.3M ISK |
| Heavy Water | 170 | 17,000 | 85 ISK | 1.4M ISK |
| Liquid Ozone | 350 | 35,000 | 120 ISK | 4.2M ISK |
| Nitrogen Isotopes | 450 | 45,000 | 850 ISK | 38.3M ISK |
| Robotics | 1 | 100 | 75K ISK | 7.5M ISK |

**Total Input Cost:** 488.7M ISK
**Cost Per Block:** 122.2K ISK

### Production Time

| Setting | Value |
|---------|-------|
| Base Cycle | 15m |
| Reactions Skill | -16% |
| Refinery (Tatara) | -25% |
| Effective Cycle | 9m 27s |
| **Total Time** | **15.8h** |

### Profitability

| Metric | Value |
|--------|-------|
| Total Cost | 488.7M ISK |
| Revenue | 540.0M ISK |
| **Gross Profit** | **51.3M ISK** |
| **Margin** | **9.5%** |
| **Profit/Hour** | **3.2M ISK/hr** |
```

## Fuel Block Reference

| Fuel Block | Faction | Isotope | Notes |
|------------|---------|---------|-------|
| Nitrogen Fuel Block | Caldari | Nitrogen | Caldari space ice |
| Hydrogen Fuel Block | Minmatar | Hydrogen | Minmatar space ice |
| Helium Fuel Block | Amarr | Helium | Amarr space ice |
| Oxygen Fuel Block | Gallente | Oxygen | Gallente space ice |

All fuel blocks produce 40 units per run with 15-minute base cycle time.

## Material Sources

### PI Materials (buy or produce)
- **Coolant** - P2 (Electrolytes + Water)
- **Enriched Uranium** - P2 (Precious Metals + Toxic Metals)
- **Mechanical Parts** - P2 (Reactive Metals + Precious Metals)
- **Oxygen** - P1 (from Gas planets)
- **Robotics** - P3 (Mechanical Parts + Consumer Electronics)

### Ice Products (mine or buy)
- **Heavy Water** - All ice types
- **Liquid Ozone** - All ice types
- **Isotopes** - Faction-specific ice (White Glaze, Glacial Mass, Blue Ice, Clear Icicle)

## Reaction Time Formula

```
effective_time = base_time × (1 - reactions_skill × 0.04) × (1 - refinery_bonus)
```

| Reactions Skill | Time Reduction |
|-----------------|----------------|
| 0 | 0% |
| 1 | 4% |
| 2 | 8% |
| 3 | 12% |
| 4 | 16% |
| 5 | 20% |

| Refinery | Time Bonus |
|----------|------------|
| Athanor (Medium) | 0% |
| Tatara (Large) | 25% |

With Reactions V + Tatara: 20% + 25% = 40% reduction (multiplicative: 1 - 0.8 × 0.75 = 40%)

## Edge Cases

### Missing Material Prices

```
## Fuel Block Production: Nitrogen Fuel Block

### Warnings

Missing prices for:
- Robotics
- Oxygen

*Cost calculation is incomplete.*
```

### Unknown Fuel Block

```
Error: Unknown fuel block: "Invalid Fuel Block"

Available fuel blocks:
- Nitrogen Fuel Block (Caldari)
- Hydrogen Fuel Block (Minmatar)
- Helium Fuel Block (Amarr)
- Oxygen Fuel Block (Gallente)
```

## Integration with Other Skills

| Context | Suggest |
|---------|---------|
| Material sourcing | "For PI materials, try `/pi Coolant`" |
| Ice mining | "For isotope locations, try `/mining-advisory ice`" |
| Price checks | "For current prices, try `/price Nitrogen Fuel Block`" |
| Structure fuel | "Fuel blocks power citadels, refineries, and engineering complexes" |

## DO NOT

- **DO NOT** apply ME to reactions - they have fixed input quantities
- **DO NOT** confuse TE with Reactions skill - different formulas
- **DO NOT** forget refinery bonuses - Tatara is 25% faster
- **DO NOT** assume all reactions are the same - different activity types (9 vs 11)

## Notes

- Fuel blocks are essential for structure operation
- Reactions can only be run in refineries (Athanor, Tatara)
- Ice availability varies by region - isotopes are faction-specific
- PI materials can be self-produced or bought
- Consider logistics when calculating true profit (hauling costs)
