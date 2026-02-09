---
name: pi
description: Planetary Interaction guide for production chains, planet resources, and colony planning.
model: haiku
category: operations
triggers:
  - "/pi"
  - "PI production chain"
  - "what planet for [resource]"
  - "how to make [P1/P2/P3/P4 item]"
  - "planetary interaction"
  - "PI guide"
  - "what planets have [resource]"
requires_pilot: false
data_sources:
  - reference/mechanics/planetary-interaction.json
---

# ARIA Planetary Interaction Module

## Purpose

Provide guidance on EVE Online Planetary Interaction (PI) production chains, planet resource availability, and colony planning. Uses static reference data for production schematics and can integrate with market prices for profit analysis.

## Trigger Phrases

- "/pi"
- "PI production chain"
- "what planet for [resource]"
- "how to make [P1/P2/P3/P4 item]"
- "planetary interaction"
- "PI guide"
- "what planets have [resource]"

## Command Syntax

```
/pi chain <product>           # Show production chain for an item
/pi planets <resource>        # Find planets with a resource
/pi single-planet             # Show P2 products makeable on single planet
/pi skills                    # PI skill recommendations
/pi profit [product]          # Profit analysis with market prices
/pi near <product>            # Find planets near home systems for production
```

## Location-Aware Planning

The `/pi near` command finds planets near your home systems that can produce a specific PI product.

### CLI Commands

```bash
# Build planet cache for nearby systems
uv run aria-esi cache-planets --around Dodixie --jumps 15

# Find planets for Robotics production near home
uv run aria-esi pi-near Robotics

# Check what planets are in a specific system
uv run aria-esi pi-planets Dodixie
```

### Example: Finding Planets for Robotics

```
/pi near Robotics
```

**Response:**
```
## PI Location Finder: Robotics (P3)

**Required P0 Resources:**
- Base Metals (Reactive Metals → Mechanical Parts)
- Noble Metals (Precious Metals → Mechanical Parts)
- Non-CS Crystals (Chiral Structures → Consumer Electronics)
- Heavy Metals (Toxic Metals → Consumer Electronics)

**Single-Planet Options:**
Planet types that have all 4 P0 resources:
- Barren
- Plasma

**Home Systems:** Dodixie, Sortet, Masalle

### Nearby Systems with Suitable Planets

| System | Barren | Plasma | Distance |
|--------|--------|--------|----------|
| Colelie | 2 | 0 | 3 jumps |
| Pucherie | 1 | 1 | 5 jumps |
| Sortet | 1 | 0 | 0 jumps (home) |

*Based on cached planet data. Run `uv run aria-esi cache-planets --around <system>` to expand coverage.*
```

### Building the Planet Cache

Planet types must be cached before `/pi near` can work. The cache stores planet types for each system.

```bash
# Cache systems around a central point
uv run aria-esi cache-planets --around Dodixie --jumps 10

# Cache a specific region
uv run aria-esi cache-planets --region "Sinq Laison"

# Cache specific systems
uv run aria-esi cache-planets --systems Jita Perimeter Maurasi

# View cache statistics
uv run aria-esi cache-planets

# Clear cache
uv run aria-esi cache-planets --clear
```

### Cache File Location

Planet data is cached to: `userdata/cache/planet_types.json`

**Cache structure:**
```json
{
  "systems": {
    "Dodixie": {
      "system_id": 30002659,
      "planets": [
        {"planet_id": 40168301, "type_id": 11, "type_name": "Temperate"},
        {"planet_id": 40168302, "type_id": 2016, "type_name": "Barren"}
      ]
    }
  },
  "metadata": {
    "last_updated": "2026-02-02T12:00:00Z",
    "systems_count": 150,
    "planets_count": 1200
  }
}
```

### Home System Configuration

Home systems are read from `userdata/config.json`:

```json
{
  "redisq": {
    "context_topology": {
      "geographic": {
        "systems": [
          {"name": "Dodixie", "classification": "home"},
          {"name": "Sortet", "classification": "home"}
        ]
      }
    }
  }
}
```

### POCO Tax Awareness

When using `/pi profit`, you can specify POCO tax rate:

```
/pi profit Robotics --poco-tax 5
```

- NPC-controlled POCOs (Interbus): 10% base tax
- Player-owned POCOs: 0-100% (varies by owner)

## Data Source

All PI data comes from `reference/mechanics/planetary-interaction.json`:
- Production chains (P0 → P1 → P2 → P3 → P4)
- Planet resources by type
- Production cycle times and quantities
- Skill requirements

**CRITICAL:** Always read the reference file before answering PI questions. Do not rely on training data for specific schematics or resource locations.

## Profit Calculation Implementation

When asked about PI profit (`/pi profit <product>`):

### Step 1: Identify Product Tier and Inputs

```python
# Read reference file
pi_data = read("reference/mechanics/planetary-interaction.json")

# Find product in schematics (check P2, P3, P4)
if product in pi_data["p2_schematics"]:
    tier = "P2"
    schematic = pi_data["p2_schematics"][product]
    inputs = schematic["inputs"]  # P1 inputs
    output_qty = pi_data["production_constants"]["p1_to_p2"]["output_qty"]  # 5
    input_qty = pi_data["production_constants"]["p1_to_p2"]["input_qty_each"]  # 40
    cycle_hours = 1  # 3600 seconds
elif product in pi_data["p3_schematics"]:
    tier = "P3"
    schematic = pi_data["p3_schematics"][product]
    inputs = schematic["inputs"]  # P2 inputs
    output_qty = pi_data["production_constants"]["p2_to_p3"]["output_qty"]  # 3
    input_qty = pi_data["production_constants"]["p2_to_p3"]["input_qty_each"]  # 10
    cycle_hours = 1
elif product in pi_data["p4_schematics"]:
    tier = "P4"
    schematic = pi_data["p4_schematics"][product]
    # P4 has variable inputs (P3 + optional P1)
    ...
```

### Step 2: Fetch Market Prices

```python
# Build item list for market query
items_to_price = [product] + inputs

# Use market dispatcher
market(action="prices", items=items_to_price, region="jita")
```

### Step 3: Calculate Costs and Profit

```python
# P2/P3 calculation (P4 is more complex)
input_cost = sum(input_qty * price[input_name] for input_name in inputs)
output_value = output_qty * price[product]

# Export tax (POCO)
base_export_cost = pi_data["export_costs_per_unit"][tier]
export_tax = output_qty * base_export_cost * poco_tax_rate

# Net profit
gross_profit = output_value - input_cost
net_profit = gross_profit - export_tax
margin = (net_profit / output_value) * 100
isk_per_hour = net_profit / cycle_hours
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--poco-tax` | 10% | POCO export tax rate (player-owned POCOs vary) |
| `--region` | jita | Price source region |

## Response Patterns

### Production Chain Query

When asked about producing an item (e.g., "how to make Robotics"):

1. Read `reference/mechanics/planetary-interaction.json`
2. Find the item in p2_schematics, p3_schematics, or p4_schematics
3. Trace backwards to raw resources (P0)
4. Present the full chain

**Example Response:**

```
## Robotics Production Chain (P3)

**Final Product:** Robotics (P3)

**Direct Inputs (P2):**
- Consumer Electronics (10 units)
- Mechanical Parts (10 units)

**P2 → P1 Requirements:**
Consumer Electronics:
  - Chiral Structures ← Non-CS Crystals (P0)
  - Toxic Metals ← Heavy Metals (P0)

Mechanical Parts:
  - Precious Metals ← Noble Metals (P0)
  - Reactive Metals ← Base Metals (P0)

**Raw Resources Needed (P0):**
- Base Metals
- Heavy Metals
- Noble Metals
- Non-CS Crystals

**Viable Planet Types:**
Barren and Plasma have all four P0 resources for single-system production.
```

### Planet Resource Query

When asked about planets for a resource (e.g., "what planets have Reactive Gas"):

1. Read `reference/mechanics/planetary-interaction.json`
2. Check `planet_resources` section
3. List all planet types containing that resource

**Example Response:**

```
## Reactive Gas Sources

**Planet Types with Reactive Gas:**
- Gas
- Storm

**Produces:** Oxidizing Compound (P1)

**P2 Products using Oxidizing Compound:**
- Oxides (with Oxygen)
- Polyaramids (with Industrial Fibers)
- Silicate Glass (with Silicon)
```

### Single-Planet P2 Query

When asked about single-planet production:

1. Read `reference/mechanics/planetary-interaction.json`
2. Return `single_planet_p2` section

**Example Response:**

```
## Single-Planet P2 Production

These P2 products can be manufactured entirely on one planet type:

**Barren:**
- Construction Blocks
- Enriched Uranium
- Mechanical Parts
- Miniature Electronics
- Nanites

**Gas:**
- Coolant
- Oxides
- Rocket Fuel
- Synthetic Oil

**Oceanic:**
- Fertilizer
- Genetically Enhanced Livestock
- Livestock
- Supertensile Plastics
- Test Cultures
- Viral Agent

(See full list in reference data)
```

### Profit Analysis

When asked about PI profit (`/pi profit <product>` or `/pi profit <product> --poco-tax 5`):

1. Read reference data for production chain and type_ids
2. Use `market(action="prices", items=[...])` to get current prices
3. Calculate input costs vs. output value
4. Calculate export tax based on tier and POCO rate
5. Present net profit, margin, and ISK/hour

**Example Response (P3 Product):**

```
## PI Profit Analysis: Robotics

**Product:** Robotics (P3)
**Cycle Time:** 1 hour
**Output:** 3 units/cycle

### Market Prices (Jita)

| Item | Role | Price/Unit |
|------|------|------------|
| Robotics | Output | 85,000 ISK |
| Consumer Electronics | Input | 12,500 ISK |
| Mechanical Parts | Input | 8,200 ISK |

### Production Economics

| Metric | Calculation | Value |
|--------|-------------|-------|
| **Output Value** | 3 × 85,000 | 255,000 ISK |
| **Input Cost** | (10 × 12,500) + (10 × 8,200) | 207,000 ISK |
| **Gross Profit** | 255,000 - 207,000 | 48,000 ISK |
| **Export Tax (10%)** | 3 × 60,000 × 0.10 | 18,000 ISK |
| **Net Profit** | 48,000 - 18,000 | **30,000 ISK** |
| **Margin** | 30,000 / 255,000 | **11.8%** |
| **ISK/Hour** | | **30,000 ISK** |

### Tax Sensitivity

| POCO Tax | Export Cost | Net Profit | Margin |
|----------|-------------|------------|--------|
| 5% | 9,000 ISK | 39,000 ISK | 15.3% |
| 10% (default) | 18,000 ISK | 30,000 ISK | 11.8% |
| 15% | 27,000 ISK | 21,000 ISK | 8.2% |

*Prices from Jita. Assumes buying inputs and selling outputs at market.*
```

**Example Response (P2 Product):**

```
## PI Profit Analysis: Mechanical Parts

**Product:** Mechanical Parts (P2)
**Cycle Time:** 1 hour
**Output:** 5 units/cycle

### Market Prices (Jita)

| Item | Role | Price/Unit |
|------|------|------------|
| Mechanical Parts | Output | 8,200 ISK |
| Precious Metals | Input (P1) | 520 ISK |
| Reactive Metals | Input (P1) | 380 ISK |

### Production Economics

| Metric | Calculation | Value |
|--------|-------------|-------|
| **Output Value** | 5 × 8,200 | 41,000 ISK |
| **Input Cost** | (40 × 520) + (40 × 380) | 36,000 ISK |
| **Gross Profit** | 41,000 - 36,000 | 5,000 ISK |
| **Export Tax (10%)** | 5 × 7,200 × 0.10 | 3,600 ISK |
| **Net Profit** | 5,000 - 3,600 | **1,400 ISK** |
| **Margin** | 1,400 / 41,000 | **3.4%** |
| **ISK/Hour** | | **1,400 ISK** |

*Low margin typical for P2. Consider vertical integration (extract P0 yourself).*
```

**Example Response (P4 Product):**

```
## PI Profit Analysis: Broadcast Node

**Product:** Broadcast Node (P4)
**Cycle Time:** 1 hour
**Output:** 1 unit/cycle
**Note:** Requires Barren or Temperate planet

### Market Prices (Jita)

| Item | Role | Qty | Price/Unit | Total |
|------|------|-----|------------|-------|
| Broadcast Node | Output | 1 | 1,450,000 ISK | 1,450,000 ISK |
| Data Chips | Input (P3) | 6 | 72,000 ISK | 432,000 ISK |
| High-Tech Transmitters | Input (P3) | 6 | 95,000 ISK | 570,000 ISK |
| Neocoms | Input (P3) | 6 | 68,000 ISK | 408,000 ISK |

### Production Economics

| Metric | Value |
|--------|-------|
| **Output Value** | 1,450,000 ISK |
| **Input Cost** | 1,410,000 ISK |
| **Gross Profit** | 40,000 ISK |
| **Export Tax (10%)** | 120,000 ISK |
| **Net Profit** | **-80,000 ISK** |

**Warning:** P4 production is currently unprofitable at 10% POCO tax.
Consider: Lower POCO tax (<3%), vertical integration, or different product.
```

## Skill Recommendations

When asked about PI skills:

```
## PI Skill Priorities

**Essential (Train First):**
1. Command Center Upgrades V - Max CPU/PG for production planets
2. Interplanetary Consolidation IV - 5 planets (sufficient for most chains)

**Recommended:**
3. Planetology IV - Better resource hotspot visibility
4. Advanced Planetology III - Fine-grained detection

**Low Priority:**
5. Remote Sensing III - Only for scanning distant systems
```

## Integration with Other Skills

| Context | Suggest |
|---------|---------|
| Looking up P4 components | "For fuel block manufacturing, check `/industry-jobs`" |
| Asking about POCO locations | "For system intel, try `/orient [system]`" |
| Profit optimization | "For market spread, try `/price [item] --jita`" |

## DO NOT

- **DO NOT** guess production chains - always read the reference file
- **DO NOT** recommend specific systems (PI is done anywhere)
- **DO NOT** discuss Equinox colony materials (separate sovereignty system)
- **DO NOT** provide exact ISK/hour calculations (too many variables)

## Notes

- P4 production requires Barren or Temperate planets (High Tech Production Plant restriction)
- All P3 products require 2-3 different P2 inputs
- Some P4 products require P1 inputs in addition to P3
- Export tax is based on tier, not market value
