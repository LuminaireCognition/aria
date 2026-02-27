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

## Command Syntax

```
/build-cost <item>                    # Basic cost calculation (ME 0)
/build-cost <item> --me <N>           # With ME research level (0-10)
/build-cost <item> --runs <N>         # Multiple runs
/build-cost <item> --facility Azbel   # With facility bonuses
/build-cost <item> --full-chain       # Resolve component build chains
/build-cost <item> --t2               # T2 invention + manufacturing cost
```

## Material Extraction Protocol (MANDATORY)

**CRITICAL:** Never hardcode material lists. Always extract ALL materials from SDE response.

### Steps:
1. Query `sde(action="blueprint_info", item=...)`
2. Extract **ALL** entries from `materials` array - not just minerals
3. Include product name for market comparison
4. Query prices for the complete list: `market(action="prices", items=material_names)`
5. Verify price completeness: count materials from SDE vs prices received. If mismatch, display prominent warning.

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

**CRITICAL:** Always fetch ALL material prices in a single `market(action="prices")` call.

## Implementation

This skill orchestrates existing MCP dispatchers. No CLI command required.

### Step 1: Get Bill of Materials

```python
sde(action="blueprint_info", item="Dominix")
```

**IMPORTANT:** All material names and quantities MUST come from `sde(action="blueprint_info")` at runtime. Never use example quantities for actual cost calculations.

### Step 2: Apply ME Efficiency

```
Formula: actual_qty = ceil(base_qty * (1 - me_level * 0.01))
```

### Step 3: Get Market Prices

```python
market(action="prices", items=material_names)
```

### Step 4: Classify Materials and Calculate Costs

Reference `reference/industry/material_sources.json` for classification into minerals, components, PI materials, etc.

### Step 5: Calculate Profitability

```
product_value = product_price * product_quantity * runs
profit = product_value - total_cost
margin = (profit / product_value) * 100
profit_per_hour = profit / (manufacturing_time_hours)
```

## Pre-Response Validation (MANDATORY)

Before presenting build cost results, verify:

1. All materials from `blueprint_info` have corresponding prices
2. Component costs are included (not just minerals)
3. Total equals sum of ALL material categories
4. Profit calculation uses complete costs
5. Any missing data is prominently flagged
6. Complexity rating matches material types

**If any step fails:** Do not present as complete. Show warning.

### Warning Format (MANDATORY when prices missing):

```
## Build Cost: [Item]

**INCOMPLETE CALCULATION**

Missing prices for N materials:
- Material Name (quantity units)

The totals below are UNDERSTATED. Do not make build decisions without complete data.
```

## Complexity Rating System

| Rating | Criteria |
|--------|----------|
| Simple | Minerals only |
| Moderate | Minerals + PI (P1/P2) or ice |
| Complex | Minerals + PI (P3/P4) + Components |
| Advanced | T2/T3 (not supported in standard mode) |

Classification logic: check each material against `reference/industry/material_sources.json`. Highest-complexity material determines overall rating.

## Response Format

```
## Build Cost: [Item] [Complexity]

**Blueprint:** [name]
**ME Level:** [N] ([N]% material reduction)
**Runs:** [N]

### Bill of Materials

| Material | Category | Base Qty | ME Qty | Price/Unit | Total |
|----------|----------|----------|--------|------------|-------|
| ... | ... | ... | ... | ... | ... |

**Mineral Cost:** [X] ISK
**Component Cost:** [X] ISK
**Total Material Cost:** [X] ISK

### Profitability

| Metric | Value |
|--------|-------|
| Material Cost | [X] ISK |
| Product Value (Jita sell) | [X] ISK |
| **Gross Profit** | **[X] ISK** |
| **Margin** | **[X]%** |
| Manufacturing Time | [time] |
| **Profit/Hour** | **[X] ISK/hr** |

### Supply Chain Requirements
(for complex items with non-mineral inputs)

*Prices from Jita. Does not include job fees, facility bonuses, or taxes.*
```

When no ME is specified, show ME 0/5/10 comparison.

## ME Comparison

When no ME is specified, show a comparison table with ME 0, 5, and 10 showing material cost and savings vs ME 0.

## Edge Cases

### Item Not Found
Suggest similar items from SDE search.

### T2 Item Requested
T2 manufacturing requires invention. Use `/build-cost <T2 item> --t2` for full analysis. See T2 Invention section below.

### Blueprint Not Available
Note that faction/drop-only items cannot be manufactured. Suggest `/price` for market value.

## Component Analysis (Optional)

For items with manufactured components, offer build-vs-buy breakdown on request. Requires additional SDE queries. Only perform when explicitly requested or when component costs are significant (>10% of total).

## Full Chain Resolution (`--full-chain`)

When `--full-chain` is specified, recursively resolve component blueprints to show "build from minerals" vs "buy components" cost comparison.

Read `reference/industry/terminal_materials.json` for the list of terminal materials where chain resolution stops (minerals, PI P0/P1, ice products, moon materials, salvage).

### Chain Depth Limits
- Maximum depth: 5 levels
- Circular reference protection via `seen` set
- Items without blueprints are treated as terminal

## Job Installation Cost Calculation

When `--facility` or `--system` is provided, include job installation costs.

Read `reference/industry/facility_bonuses.json` for facility ME/TE bonuses.

### Job Cost Formula

```
Job Cost = EIV * System Index + EIV * SCC Surcharge + EIV * Facility Tax

Where:
- EIV = Estimated Item Value (sum of adjusted input prices, from CCP)
- System Index = Manufacturing cost index (varies by system, 0.1% to 15%+)
- SCC Surcharge = 4% (mandatory)
- Facility Tax = Structure owner's tax (0-50%) or NPC tax (0.25%)
```

## Cost Considerations

When facility/system NOT specified, note that calculation excludes: job fees, sales tax, blueprint cost.
When facility/system IS specified, note that calculation excludes: sales tax, blueprint cost, rig bonuses.

## T2 Invention Cost Calculation

When calculating T2 manufacturing costs, invention must be factored in.

### Invention Success Rate Formula

```
Success Rate = Base Rate * (1 + Skill Bonus) * Decryptor Modifier

Where:
- Base Rate = 26% for most T2 items (40% for ammo)
- Skill Bonus = (Encryption + Science1 + Science2) * 1%
- Decryptor Modifier = varies by decryptor (0.6 to 1.8)
```

Read `reference/industry/invention_materials.json` for base success rates, decryptor modifiers, and datacore requirements.

### T2 Cost Components

Total T2 cost per unit = (Invention cost / BPC runs) + T2 material cost + job fees.

Invention cost = (datacore costs + decryptor cost) / success rate.

## Character Integration

When the capsuleer has authenticated ESI access:
1. Fetch character blueprints to find ME/TE for the target item
2. If blueprint found, use its ME/TE instead of defaults
3. If not found, fall back to ME 0 and note "No matching blueprint found. Use --me to specify."
4. For T2 invention, fetch industry skills to calculate actual invention bonus

## Industry Advisory Protocol

Before recommending BPO purchases or manufacturing priorities:
1. Read the active pilot's blueprint library at `userdata/pilots/{active_pilot}/industry/blueprints.md`
2. Never recommend acquiring BPOs the capsuleer already owns
3. Base recommendations on actual inventory, not generic starter advice

## DO NOT

- **DO NOT** hardcode material lists - always extract from SDE response
- **DO NOT** silently omit materials when prices unavailable
- **DO NOT** include speculative pricing or predictions
- **DO NOT** recommend specific facilities (varies by location)
- **DO NOT** present incomplete calculations as complete
- **DO NOT** forget to amortize invention cost across T2 BPC runs
