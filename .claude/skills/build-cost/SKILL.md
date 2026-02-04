---
name: build-cost
description: Manufacturing cost calculator for T1 items. Calculates material costs, profit margins, and ME efficiency.
model: haiku
category: industry
triggers:
  - "/build-cost"
  - "cost to build [item]"
  - "manufacturing cost"
  - "is it profitable to build [item]"
  - "build vs buy [item]"
  - "BOM for [item]"
requires_pilot: false
---

# ARIA Build Cost Calculator

## Purpose

Calculate manufacturing costs for T1 items by fetching blueprint bill of materials from SDE and current market prices. Helps pilots decide whether to build or buy, and optimize production with ME research.

**Scope:** T1 manufacturing only. T2 invention chains (datacores, decryptors) are not covered in this version.

## Trigger Phrases

- "/build-cost"
- "cost to build [item]"
- "manufacturing cost"
- "is it profitable to build [item]"
- "build vs buy [item]"
- "BOM for [item]"

## Command Syntax

```
/build-cost <item>                    # Basic cost calculation (ME 0)
/build-cost <item> --me <N>           # With ME research level (0-10)
/build-cost <item> --runs <N>         # Multiple runs
/build-cost <item> --me 10 --runs 100 # Combined
/build-cost <item> --facility Azbel   # With facility bonuses
/build-cost <item> --system Perimeter # With system cost index
/build-cost <item> --full-chain       # Resolve component build chains
/build-cost <item> --facility Sotiyo --system Perimeter --me 10  # Full calculation
```

## Material Extraction Protocol (MANDATORY)

**CRITICAL:** Never hardcode material lists. Always extract ALL materials from SDE response.

### Steps:
1. Query `sde(action="blueprint_info", item=...)`
2. Extract **ALL** entries from `materials` array - not just minerals
3. Include product name for market comparison
4. Query prices for the complete list

### Validation Rule:
- Count materials returned by `sde(action="blueprint_info")`
- Count prices received from `market(action="prices")`
- If mismatch → **MUST display prominent warning**
- Silent omission of materials is **FORBIDDEN**

### Example - WRONG (hardcoded minerals):
```python
# DO NOT DO THIS - misses components, PI, reactions
materials = ["Tritanium", "Pyerite", "Mexallon", "Isogen", "Nocxium", "Zydrine", "Megacyte"]
```

### Example - CORRECT (dynamic extraction):
```python
blueprint = sde(action="blueprint_info", item="Dominix")
material_names = [m["type_name"] for m in blueprint["materials"]]
# Returns ALL materials: minerals + components + PI + reactions
```

## Implementation

This skill orchestrates existing MCP dispatchers. No CLI command required.

### Step 1: Get Bill of Materials

```python
# Query SDE for blueprint materials
sde(action="blueprint_info", item="Dominix Blueprint")
# or
sde(action="blueprint_info", item="Dominix")  # Auto-detects blueprint
```

**Response contains all materials:**
```json
{
  "blueprint": "Dominix Blueprint",
  "product": "Dominix",
  "product_quantity": 1,
  "materials": [
    {"type_name": "Tritanium", "quantity": 13333334},
    {"type_name": "Pyerite", "quantity": 2666667},
    {"type_name": "Mexallon", "quantity": 666667},
    {"type_name": "Isogen", "quantity": 200000},
    {"type_name": "Nocxium", "quantity": 33334},
    {"type_name": "Zydrine", "quantity": 13334},
    {"type_name": "Megacyte", "quantity": 3334},
    {"type_name": "Auto-Integrity Preservation Seal", "quantity": 150},
    {"type_name": "Life Support Backup Unit", "quantity": 75},
    {"type_name": "Core Temperature Regulator", "quantity": 1}
  ],
  "time_seconds": 14400
}
```

### Step 2: Extract ALL Materials

```python
# CORRECT: Extract from response, not hardcoded
material_names = [m["type_name"] for m in blueprint["materials"]]
# ["Tritanium", "Pyerite", ..., "Auto-Integrity Preservation Seal", ...]

# Add product for market comparison
material_names.append(blueprint["product"])
```

### Step 3: Apply ME Efficiency

```python
# ME reduces material requirements
# Formula: actual_qty = ceil(base_qty * (1 - me_level * 0.01))
def apply_me(base_qty: int, me_level: int) -> int:
    return math.ceil(base_qty * (1 - me_level * 0.01))

# Example: 13,333,334 Tritanium at ME 10
# 13333334 * 0.90 = 12,000,001
```

### Step 4: Get Market Prices

```python
# Fetch prices for ALL materials + product (single query)
market(action="prices", items=material_names)
```

### Step 5: Verify Price Completeness

```python
requested = set(material_names)
received = set(price["type_name"] for price in prices["items"])
missing = requested - received

if missing:
    # MUST display prominent warning before any results
    # MUST NOT present totals as complete
```

### Warning Format (MANDATORY when prices missing):

```
## Build Cost: Dominix

**INCOMPLETE CALCULATION**

Missing prices for N materials:
- Material Name (quantity units)
- ...

The totals below are UNDERSTATED. Do not make build decisions without complete data.
```

### Step 6: Classify Materials and Calculate Costs

Reference `reference/industry/material_sources.json` for classification:

```python
mineral_cost = sum(qty * price for minerals)
component_cost = sum(qty * price for components)
pi_cost = sum(qty * price for pi_materials)
total_cost = mineral_cost + component_cost + pi_cost
```

### Step 7: Calculate Profitability

```python
product_value = product_price * product_quantity * runs
profit = product_value - total_cost
margin = (profit / product_value) * 100
```

## Complexity Rating System

Assess supply chain complexity based on material types:

| Rating | Criteria | Icon |
|--------|----------|------|
| Simple | Minerals only | Simple |
| Moderate | Minerals + PI (P1/P2) or ice | Moderate |
| Complex | Minerals + PI (P3/P4) + Components | Complex |
| Advanced | T2/T3 (not supported) | Advanced |

Display rating in output header:
```
## Build Cost: Dominix [Complex]
```

**Classification logic:**
- Check each material against `reference/industry/material_sources.json`
- Highest-complexity material determines overall rating
- If any material is unclassified, note as "unknown source"

## Supply Chain Requirements (Complex Items)

For items with non-mineral inputs, add this section to output:

```markdown
### Supply Chain Requirements

| Source | Materials | Acquisition |
|--------|-----------|-------------|
| Minerals | Tritanium, Pyerite, ... | Mining / Market |
| PI | Nanites, Test Cultures, ... | Planetary colonies |
| Components | Auto-Integrity Preservation Seal, ... | Build or buy |
```

## Component Analysis (Optional)

For items with manufactured components, offer breakdown on request:

```markdown
### Component Cost Breakdown

| Component | Qty | Market Price | Build Cost | Recommendation |
|-----------|-----|--------------|------------|----------------|
| Auto-Integrity Preservation Seal | 150 | 8.4M | 7.1M | Build (save 1.3M) |
| Life Support Backup Unit | 75 | 6.4M | 5.8M | Build (save 0.6M) |
| Core Temperature Regulator | 1 | 4.8M | 4.2M | Build (save 0.6M) |

**Strategy Summary:**
- Buy from market: 19.6M total
- Build yourself: 17.1M (saves 2.5M, requires PI/reactions)
```

**Note:** Component breakdown requires additional SDE queries. Only perform when explicitly requested or when component costs are significant (>10% of total).

## Response Format

**Example Response:**

```
## Build Cost: Dominix [Complex]

**Blueprint:** Dominix Blueprint
**ME Level:** 10 (10% material reduction)
**Runs:** 1

### Bill of Materials

| Material | Category | Base Qty | ME 10 Qty | Price/Unit | Total |
|----------|----------|----------|-----------|------------|-------|
| Tritanium | Mineral | 13,333,334 | 12,000,001 | 4.50 | 54.0M |
| Pyerite | Mineral | 2,666,667 | 2,400,001 | 8.20 | 19.7M |
| Mexallon | Mineral | 666,667 | 600,001 | 42.00 | 25.2M |
| Isogen | Mineral | 200,000 | 180,000 | 85.00 | 15.3M |
| Nocxium | Mineral | 33,334 | 30,001 | 450.00 | 13.5M |
| Zydrine | Mineral | 13,334 | 12,001 | 1,200.00 | 14.4M |
| Megacyte | Mineral | 3,334 | 3,001 | 2,800.00 | 8.4M |
| Auto-Integrity Preservation Seal | Component | 150 | 135 | 56,000 | 7.6M |
| Life Support Backup Unit | Component | 75 | 68 | 85,000 | 5.8M |
| Core Temperature Regulator | Component | 1 | 1 | 4,800,000 | 4.8M |

**Mineral Cost:** 150.5M ISK
**Component Cost:** 18.2M ISK
**Total Material Cost:** 168.7M ISK

### Profitability

| Metric | Value |
|--------|-------|
| Material Cost | 168.7M ISK |
| Product Value (Jita sell) | 185.0M ISK |
| **Gross Profit** | **16.3M ISK** |
| **Margin** | **8.8%** |
| Manufacturing Time | 4h 0m (TE 0) |
| **Profit/Hour** | **4.1M ISK/hr** |

### Supply Chain Requirements

| Source | Materials | Acquisition |
|--------|-----------|-------------|
| Minerals | Tritanium, Pyerite, Mexallon, Isogen, Nocxium, Zydrine, Megacyte | Mining / Market |
| Components | Auto-Integrity Preservation Seal, Life Support Backup Unit, Core Temperature Regulator | Build or buy (PI + reactions required for build) |

*Prices from Jita. Does not include job fees, facility bonuses, or taxes.*
```

### Multi-Run Example

```
## Build Cost: Dominix (10 runs) [Complex]

**ME Level:** 10
**Runs:** 10

### Bill of Materials (per run x 10)

| Material | Category | Per Run | Total Qty | Total Cost |
|----------|----------|---------|-----------|------------|
| Tritanium | Mineral | 12,000,001 | 120,000,010 | 540.0M |
| ... | ... | ... | ... | ... |
| Core Temperature Regulator | Component | 1 | 10 | 48.0M |

**Total Material Cost:** 1,687.0M ISK

### Profitability (10 units)

| Metric | Value |
|--------|-------|
| Material Cost | 1,687.0M ISK |
| Product Value | 1,850.0M ISK |
| **Gross Profit** | **163.0M ISK** |
| **Profit/Unit** | **16.3M ISK** |
| **Margin** | **8.8%** |
| Manufacturing Time | 40h 0m (TE 0) |
| **Profit/Hour** | **4.1M ISK/hr** |
```

## Simple Item Example (Hammerhead I)

For mineral-only items, the output is simpler:

```
## Build Cost: Hammerhead I [Simple]

**Blueprint:** Hammerhead I Blueprint
**ME Level:** 10 (10% material reduction)
**Runs:** 1

### Bill of Materials

| Material | Base Qty | ME 10 Qty | Price/Unit | Total |
|----------|----------|-----------|------------|-------|
| Tritanium | 2,600 | 2,340 | 4.50 | 10,530 |
| Pyerite | 600 | 540 | 8.20 | 4,428 |
| Mexallon | 150 | 135 | 42.00 | 5,670 |
| Isogen | 10 | 9 | 85.00 | 765 |
| Nocxium | 1 | 1 | 450.00 | 450 |

**Total Material Cost:** 21,843 ISK

### Profitability

| Metric | Value |
|--------|-------|
| Material Cost | 21,843 ISK |
| Product Value (Jita sell) | 45,000 ISK |
| **Gross Profit** | **23,157 ISK** |
| **Margin** | **51.5%** |
| Manufacturing Time | 20m (TE 0) |
| **Profit/Hour** | **69.5K ISK/hr** |

*Prices from Jita. Does not include job fees, facility bonuses, or taxes.*
```

## ME Comparison Table

When no ME is specified, show a comparison:

```
## ME Efficiency Comparison: Dominix

| ME Level | Material Cost | Savings vs ME 0 |
|----------|---------------|-----------------|
| 0 | 187.4M ISK | - |
| 5 | 178.1M ISK | 9.4M ISK (5.0%) |
| 10 | 168.7M ISK | 18.7M ISK (10.0%) |

**Recommendation:** ME 10 saves 18.7M ISK/unit.
At 10 units, that's 187M ISK saved.
```

## Pre-Response Validation (MANDATORY)

Before presenting build cost results, verify:

- [ ] All materials from `blueprint_info` have corresponding prices
- [ ] Component costs are included (not just minerals)
- [ ] Total equals sum of ALL material categories
- [ ] Profit calculation uses complete costs
- [ ] Any missing data is prominently flagged
- [ ] Complexity rating matches material types

**If any checkbox fails:** Do not present as complete. Show warning.

## Edge Cases

### Item Not Found

```
Error: Could not find blueprint for "Hammerhead III"

Did you mean:
- Hammerhead I
- Hammerhead II (T2 - not supported)
```

### T2 Item Requested

T2 manufacturing requires invention. Use `/build-cost <T2 item> --t2` for full analysis.

```
/build-cost "Hammerhead II" --t2
```

See the **T2 Invention Cost Calculation** section below.

### Blueprint Not Available

```
Note: "Vexor Navy Issue" cannot be manufactured from blueprint.

This is a faction item obtained from:
- LP store (check `/lp-store`)
- Direct drop
- Market purchase

Check `/price Vexor Navy Issue` for current market value.
```

### Missing Prices Warning

```
## Build Cost: Dominix [Complex]

**INCOMPLETE CALCULATION**

Missing prices for 3 materials:
- Auto-Integrity Preservation Seal (150 units)
- Life Support Backup Unit (75 units)
- Core Temperature Regulator (1 unit)

The totals below are UNDERSTATED by an unknown amount.
Do not make build decisions without complete data.

Try: `/price Auto-Integrity Preservation Seal` to check availability

---

[Partial results with available materials only...]
```

## Integration with Other Skills

| Context | Suggest |
|---------|---------|
| Blueprint location | "Check your blueprints with `/corp blueprints` or `uv run aria-esi blueprints`" |
| Material sourcing | "For mineral prices by region, try `/price [mineral] --jita`" |
| Industry jobs | "Monitor active jobs with `/industry-jobs`" |
| Sell price analysis | "For market depth, try `/price [item] --jita`" |
| Component costs | "For component breakdown, ask 'show component costs for [item]'" |

## Full Chain Resolution (`--full-chain`)

When `--full-chain` is specified, recursively resolve component blueprints to show "build from minerals" vs "buy components" cost comparison.

### Implementation

```python
from aria_esi.services.industry_chains import (
    ChainResolver,
    format_chain_summary,
)

# Create resolver with SDE and market lookup functions
def sde_lookup(item_name):
    return sde(action="blueprint_info", item=item_name)

def market_lookup(item_names):
    return market(action="prices", items=item_names)

resolver = ChainResolver(
    sde_lookup=sde_lookup,
    market_lookup=market_lookup,
    me_level=10,
    runs=1,
)

# Resolve the chain
result = resolver.resolve("Dominix")

# Format for display
print(format_chain_summary(result))
```

### Terminal Materials

Chain resolution stops at **terminal materials** - items that cannot be manufactured:
- **Minerals:** Tritanium, Pyerite, Mexallon, Isogen, Nocxium, Zydrine, Megacyte, Morphite
- **PI P0/P1:** Raw planetary materials
- **Ice Products:** Heavy Water, Liquid Ozone, Isotopes
- **Moon Materials:** Raw moon goo (Technetium, Dysprosium, etc.)
- **Salvage:** Components from salvaging wrecks

See `reference/industry/terminal_materials.json` for the full list.

### Output Format (Full Chain)

```
## Build vs Buy Analysis: Ishtar

### Cost Comparison

| Strategy | Total Cost |
|----------|------------|
| Buy from Market | 450.0M ISK |
| Build Everything | 385.0M ISK |
| **Savings** | **65.0M ISK** (14.4%) |

### Buildable Components

| Component | Qty | Market Price | Build? |
|-----------|-----|--------------|--------|
| Auto-Integrity Preservation Seal | 375 | 21.0M ISK | Check BOM |
| Life Support Backup Unit | 188 | 16.0M ISK | Check BOM |
| Core Temperature Regulator | 3 | 14.4M ISK | Check BOM |

### Raw Materials Required

| Material | Qty | Source |
|----------|-----|--------|
| Tritanium | 45,333,334 | Mining/PI/Moon |
| Pyerite | 9,066,667 | Mining/PI/Moon |
| Mexallon | 2,266,667 | Mining/PI/Moon |
| Nanites | 1,875 | Market only |
| Construction Blocks | 1,125 | Market only |

### Notes
- Component build costs assume ME 10
- PI materials (Nanites, Construction Blocks) treated as terminal
```

### Chain Depth Limits

To prevent infinite recursion and excessive API calls:
- Maximum depth: 5 levels
- Circular reference protection via `seen` set
- Items without blueprints are treated as terminal

### When to Use Full Chain

| Scenario | Recommendation |
|----------|----------------|
| Quick profit check | Standard mode (no flag) |
| Optimizing component production | `--full-chain` |
| Comparing vertical integration | `--full-chain` |
| Very deep T2/T3 chains | Standard mode (T2 components usually bought) |

## Profit Per Hour Calculation

When calculating profitability, include profit per hour (ISK/hr) to compare manufacturing efficiency across different items.

### Implementation

```python
from aria_esi.services.industry_costs import (
    calculate_profit_per_hour,
    format_time_duration,
    format_isk,
)

# Get manufacturing time from blueprint
blueprint = sde(action="blueprint_info", item="Dominix")
base_time = blueprint["time_seconds"]  # e.g., 14400 (4 hours)

# Calculate profit/hour
profit_result = calculate_profit_per_hour(
    gross_profit=16_300_000,        # Sell price - material cost
    manufacturing_time_seconds=base_time,
    runs=1,
    te_level=0,                      # Blueprint TE (0-20)
    facility_te_bonus=0,             # Facility bonus (e.g., 15 for Raitaru)
)

# profit_result = {
#     "profit_per_hour": 4075000.0,    # 4.1M ISK/hr
#     "effective_time_hours": 4.0,
#     "time_per_run_seconds": 14400,
#     "te_savings_percent": 0.0,
# }

# Format for display
print(f"Profit/Hour: {format_isk(profit_result['profit_per_hour'])}/hr")
print(f"Manufacturing Time: {format_time_duration(profit_result['time_per_run_seconds'])}")
```

### TE Comparison Table

When showing profitability, include a TE comparison to show how facility choice affects ISK/hr:

```
### Profit/Hour by Facility

| Facility | TE Bonus | Time | Profit/Hour |
|----------|----------|------|-------------|
| NPC Station | 0% | 4h 0m | 4.1M ISK/hr |
| Raitaru | 15% | 3h 24m | 4.8M ISK/hr |
| Azbel | 20% | 3h 12m | 5.1M ISK/hr |
| Sotiyo | 30% | 2h 48m | 5.8M ISK/hr |

*Blueprint TE 0 assumed. Add blueprint TE (0-20%) for actual values.*
```

## Job Installation Cost Calculation

When `--facility` or `--system` is provided, include job installation costs.

### Reference Data

Load facility bonuses from `reference/industry/facility_bonuses.json`:

```python
# Facility bonuses
facilities = {
    "NPC Station": {"me_bonus": 0, "te_bonus": 0},
    "Raitaru": {"me_bonus": 1, "te_bonus": 15},
    "Azbel": {"me_bonus": 1, "te_bonus": 20},
    "Sotiyo": {"me_bonus": 1, "te_bonus": 30},
}
```

### Job Cost Formula

```
Job Cost = EIV × System Index + EIV × SCC Surcharge + EIV × Facility Tax

Where:
- EIV = Estimated Item Value (sum of adjusted input prices, from CCP)
- System Index = Manufacturing cost index (varies by system, 0.1% to 15%+)
- SCC Surcharge = 4% (mandatory)
- Facility Tax = Structure owner's tax (0-50%) or NPC tax (0.25%)
```

### Implementation

```python
from aria_esi.services.industry_costs import (
    calculate_job_cost,
    estimate_total_build_cost,
    get_facility_info,
    get_typical_system_index,
)

# Get facility bonuses
facility = get_facility_info("Azbel")  # me_bonus: 1, te_bonus: 20

# Get typical system index
system_index = get_typical_system_index("Perimeter")  # ~0.075

# Calculate job cost
job_cost = calculate_job_cost(
    estimated_item_value=185_000_000,  # EIV for Dominix
    system_cost_index=system_index,
    facility_name="Azbel",
    facility_tax=0.05,  # 5% structure tax
)

# Or get full build cost
total = estimate_total_build_cost(
    material_cost=168_700_000,
    estimated_item_value=185_000_000,
    system_cost_index=system_index,
    facility_name="Azbel",
    facility_tax=0.05,
)
```

### Response Format (With Job Costs)

When facility/system is specified, add this section:

```
### Job Installation Cost

| Component | Rate | Amount |
|-----------|------|--------|
| **Estimated Item Value** | | 185.0M ISK |
| System Cost Index | 5.23% | 9.7M ISK |
| SCC Surcharge | 4.00% | 7.4M ISK |
| Facility Tax | 5.00% | 9.3M ISK |
| Facility ME Bonus | -1% | (applied to materials) |
| **Total Job Cost** | | **26.4M ISK** |

### Total Build Cost

| Component | Amount |
|-----------|--------|
| Material Cost | 168.7M ISK |
| Job Cost | 26.4M ISK |
| **Total** | **195.1M ISK** |

*System: Perimeter (index 5.23%). Facility: Azbel (1% ME, 5% tax).*
```

### Facility Comparison Table

When no facility specified but user asks about facility impact:

```
### Facility Comparison (Perimeter, 5% tax)

| Facility | ME Bonus | Job Cost | Material Savings | Total |
|----------|----------|----------|------------------|-------|
| NPC Station | 0% | 28.1M | 0 | 196.8M |
| Raitaru | 1% | 26.4M | 1.7M | 193.4M |
| Azbel | 1% | 26.4M | 1.7M | 193.4M |
| Sotiyo | 1% | 26.4M | 1.7M | 193.4M |

*Note: Raitaru/Azbel/Sotiyo have same ME bonus. Sotiyo is 30% faster.*
```

## Cost Considerations (Show in Notes)

When facility/system NOT specified:
```
*Note: This calculation does not include:*
- Industry job installation fees (use --facility and --system for full cost)
- Sales tax (if selling output)
- Blueprint acquisition cost
```

When facility/system IS specified:
```
*Note: This calculation does not include:*
- Sales tax (if selling output)
- Blueprint acquisition cost
- Rig bonuses (T1 rigs add 1-2.4% ME in nullsec)
```

## T2 Invention Cost Calculation

When calculating T2 manufacturing costs, invention must be factored in.

### Command Syntax

```
/build-cost "Hammerhead II" --t2                    # Basic T2 cost
/build-cost "Hammerhead II" --t2 --decryptor "Attainment"  # With decryptor
/build-cost "Hammerhead II" --t2 --skills 5 4 4    # With skill levels
```

### Invention Success Rate Formula

```
Success Rate = Base Rate × (1 + Skill Bonus) × Decryptor Modifier

Where:
- Base Rate = 26% for most T2 items (40% for ammo)
- Skill Bonus = (Encryption + Science1 + Science2) × 1%
- Decryptor Modifier = varies by decryptor (0.6 to 1.8)
```

### Implementation

```python
from aria_esi.services.industry_costs import (
    calculate_invention_success_rate,
    calculate_invention_cost,
    calculate_t2_bpc_stats,
    estimate_t2_production_cost,
    list_decryptors,
)

# 1. Calculate success rate
rate = calculate_invention_success_rate(
    base_rate=0.26,
    encryption_skill=4,
    science_skill_1=4,
    science_skill_2=4,
    decryptor="Attainment Decryptor",
)
# rate["final_rate"] = 0.468, rate["expected_attempts"] = 2.14

# 2. Calculate invention cost
invention = calculate_invention_cost(
    datacore_costs={
        "Datacore - Mechanical Engineering": 50000,
        "Datacore - Electronic Engineering": 40000,
    },
    datacore_quantities={
        "Datacore - Mechanical Engineering": 2,
        "Datacore - Electronic Engineering": 2,
    },
    decryptor="Attainment Decryptor",
    decryptor_cost=500000,
    success_rate=rate["final_rate"],
)
# invention["expected_cost"] = ~1.4M ISK

# 3. Get T2 BPC stats
bpc = calculate_t2_bpc_stats(base_runs=10, decryptor="Attainment Decryptor")
# bpc["runs"] = 12, bpc["me"] = -3, bpc["te"] = 4

# 4. Estimate total T2 production cost
total = estimate_t2_production_cost(
    invention_cost=invention["expected_cost"],
    t2_material_cost=500000,  # Per unit
    t2_job_cost=50000,
    t2_bpc_runs=bpc["runs"],
)
# total["total_cost_per_unit"] = ~620K ISK
```

### Decryptor Comparison Table

| Decryptor | Success | ME | TE | Runs | Best For |
|-----------|---------|----|----|------|----------|
| Attainment | 1.8× | -1 | +4 | +2 | Maximum success rate |
| Parity | 1.5× | +1 | -2 | 0 | Good success, neutral runs |
| Accelerant | 1.2× | +2 | +10 | +1 | Balanced |
| Optimized Attainment | 1.1× | +1 | -2 | +2 | Extra runs with ME bonus |
| Process | 1.1× | +3 | +6 | 0 | Best ME result |
| Symmetry | 1.0× | +2 | 0 | +1 | ME without success penalty |
| Optimized Augmentation | 0.9× | +1 | +2 | +7 | Many runs |
| Augmentation | 0.6× | -2 | +2 | +9 | Maximum runs |

### T2 Response Format

```
## Build Cost: Hammerhead II (T2) [Advanced]

### Invention

| Metric | Value |
|--------|-------|
| Base Success Rate | 26% |
| With Skills (4/4/4) | 29.9% |
| With Attainment Decryptor | 53.8% |
| Expected Attempts | 1.86 |

**Invention Materials (per attempt):**

| Material | Qty | Unit Price | Total |
|----------|-----|------------|-------|
| Datacore - Mechanical Engineering | 2 | 50,000 | 100,000 |
| Datacore - Electronic Engineering | 2 | 40,000 | 80,000 |
| Attainment Decryptor | 1 | 500,000 | 500,000 |
| T1 BPC (Hammerhead I) | 1 | 5,000 | 5,000 |

**Expected Invention Cost:** 1,273,000 ISK (for one successful T2 BPC)

**T2 BPC Stats:** 12 runs, ME -3, TE 4

### T2 Manufacturing

| Material | Per Unit | × 12 Runs |
|----------|----------|-----------|
| Hammerhead I | 1 | 12 |
| Morphite | 6 | 72 |
| (other T2 components) | ... | ... |

**T2 Material Cost:** 500,000 ISK/unit × 12 = 6,000,000 ISK

### Total Cost Summary

| Component | Per Unit | Per Batch (12) |
|-----------|----------|----------------|
| Invention | 106,083 | 1,273,000 |
| T2 Materials | 500,000 | 6,000,000 |
| Job Fees | 4,167 | 50,000 |
| **Total** | **610,250** | **7,323,000** |

**Market Price:** 680,000 ISK
**Margin:** 10.3%
```

### Reference Data

Invention materials are stored in `reference/industry/invention_materials.json`:
- Base success rates by item category
- Decryptor modifiers
- Datacore type IDs for market queries
- Common T2 blueprint datacore requirements

## Character Integration

When the capsuleer has authenticated ESI access, ARIA can use their actual blueprints and skills.

### Workflow (When `--use-character` or ESI authenticated)

1. **Check for authenticated client:**
   ```python
   from aria_esi.core import get_authenticated_client
   client, creds = get_authenticated_client()
   character_id = creds.character_id
   ```

2. **Fetch character blueprints:**
   ```python
   blueprints = get_character_blueprints(character_id, client)
   ```

3. **Find blueprint for target item:**
   ```python
   bp = find_blueprint_for_item(blueprints, target_type_id)
   ```

4. **Use blueprint ME/TE or fall back to defaults:**
   ```python
   if bp:
       me_level = bp["material_efficiency"]
       te_level = bp["time_efficiency"]
   else:
       me_level = 0  # Default
       te_level = 0
   ```

### Command Syntax

```
/build-cost <item> --use-character          # Use character's blueprint ME/TE
/build-cost <item> --me 5                   # Override with manual ME
/build-cost <item> --t2 --use-character     # T2 with character's invention skills
```

### Blueprint Detection

```python
from aria_esi.services.character_industry import (
    get_character_blueprints,
    find_blueprint_for_item,
    get_character_industry_skills,
    calculate_character_invention_bonus,
    summarize_industry_capabilities,
)

# Fetch character's blueprints
blueprints = get_character_blueprints(character_id, esi_client)

# Find best blueprint for item
bp = find_blueprint_for_item(blueprints, target_type_id, prefer_bpo=True)
if bp:
    me_level = bp["material_efficiency"]  # 0-10
    te_level = bp["time_efficiency"]      # 0-20
    is_bpo = bp["is_bpo"]
```

### Skill-Aware Invention

For T2 invention calculations, character skills provide bonuses:

```python
# Fetch industry skills
skills = get_character_industry_skills(character_id, esi_client)
# {"Industry": 5, "Advanced Industry": 4, "Gallente Encryption Methods": 4, ...}

# Calculate invention bonus for specific item
bonus = calculate_character_invention_bonus(
    character_skills=skills,
    encryption_skill="Gallente Encryption Methods",
    science_skill_1="Gallentean Starship Engineering",
    science_skill_2="Mechanical Engineering",
)
# 0.12 = 12% skill bonus (4 + 4 + 4 levels)

# Or get full capability summary
capabilities = summarize_industry_capabilities(skills)
# {
#     "manufacturing_slots": 11,  # 1 + Mass Production + Adv Mass Production
#     "science_slots": 11,
#     "time_reduction_percent": 12.0,  # From Advanced Industry
#     "invention_bonuses": {...by faction...}
# }
```

### Response Format (With Character Data)

```
## Build Cost: Dominix [Complex]

**Using Character Blueprint:** ✓ ME 10 / TE 20 (BPO)
**Location:** Dodixie IX - Moon 20

### Bill of Materials
[... standard output ...]

*Blueprint detected in character assets. Using ME 10 from ESI.*
```

### Response Format (No Blueprint Found)

```
## Build Cost: Dominix [Complex]

**Blueprint:** Not found in character assets
**Assuming:** ME 0

### Bill of Materials
[... standard output ...]

*No matching blueprint found. Use --me to specify research level.*
```

### T2 With Character Skills

```
## Build Cost: Hammerhead II (T2) [Advanced]

**Using Character Skills:**
- Gallente Encryption Methods: 4
- Mechanical Engineering: 4
- Electronic Engineering: 4
- Skill Bonus: +12%

### Invention
| Metric | Value |
|--------|-------|
| Base Success Rate | 26% |
| With Your Skills | 29.1% |
| Expected Attempts | 3.44 |
```

## DO NOT

- **DO NOT** hardcode material lists - always extract from SDE response
- **DO NOT** silently omit materials when prices unavailable
- **DO NOT** include speculative pricing or predictions
- **DO NOT** recommend specific facilities (varies by location)
- **DO NOT** forget to apply ME correctly (ceil after percentage)
- **DO NOT** present incomplete calculations as complete
- **DO NOT** forget to amortize invention cost across T2 BPC runs
- **DO NOT** assume character has blueprints - always check and fall back gracefully

## Notes

- ME 10 is maximum research level (10% material reduction)
- TE only affects time, not costs (not calculated here)
- Job fees vary by system - higher in trade hubs
- Rigs and modules can reduce costs further (not calculated)
- Always compare to market price before committing to production
- Component materials (Seals, Backup Units, Regulators) are significant costs for ships
- T2 BPCs from invention start at ME -2 (worse than researched T1 BPOs)
- Decryptor choice significantly affects profitability
