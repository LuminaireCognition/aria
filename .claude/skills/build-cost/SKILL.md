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
/build-cost <item>                    # Basic cost (shows ME 0/5/10 comparison)
/build-cost <item> --me <N>           # With ME research level (0-10)
/build-cost <item> --runs <N>         # Multiple runs
/build-cost <item> --facility Azbel   # With facility bonuses
```

## Implementation

**Single tool call.** All computation is server-side. Never do arithmetic.

```python
market(action="build_cost", item="Dominix", me_level=10, runs=1, facility="Azbel", region="jita")
```

### Parameter Extraction

Parse the user request to extract:
- `item`: The item name (required)
- `me_level`: ME level from `--me N` (default 0)
- `runs`: Run count from `--runs N` (default 1)
- `facility`: Facility from `--facility Name` (default None)
- `region`: Market hub from `--region Name` (default "jita")

### ME Comparison Mode

When **no ME is specified**, make 3 calls for ME 0, 5, and 10:

```python
market(action="build_cost", item="Dominix", me_level=0)
market(action="build_cost", item="Dominix", me_level=5)
market(action="build_cost", item="Dominix", me_level=10)
```

Present as a comparison table showing cost and savings at each ME level.

## Response Presentation

**Never do arithmetic.** Use pre-formatted strings directly from the response.

### Blueprint Not Found

If `found` is `false`, show suggestions from the response.

### Incomplete Calculation

If `is_complete` is `false`, lead with:

```
## Build Cost: [Item]

**INCOMPLETE CALCULATION**

Missing prices for N materials (see warnings).
The totals below are UNDERSTATED.
```

### Standard Response

```
## Build Cost: [Item] [complexity]

**Blueprint:** blueprint.blueprint_name
**ME Level:** blueprint.me_level (N% material reduction)
**Runs:** blueprint.runs
**Facility:** blueprint.facility (blueprint.facility_me_bonus% ME bonus)

### Bill of Materials

| Material | Category | Base Qty | ME Qty | Price/Unit | Total |
|----------|----------|----------|--------|------------|-------|
(use materials[] — present unit_price_formatted and total_cost_formatted directly)

### Category Subtotals
(use category_subtotals[] — present total_cost_formatted directly)

**Total Material Cost:** total_material_cost_formatted

### Profitability
(use profitability object — present all *_formatted fields directly)

| Metric | Value |
|--------|-------|
| Material Cost | total_material_cost_formatted |
| Product Value | profitability.product_total_formatted |
| **Gross Profit** | **profitability.gross_profit_formatted** |
| **Margin** | **profitability.margin_pct%** |

*Prices from region. Does not include job fees, facility bonuses beyond ME, or taxes.*
```

### ME Comparison Table

When showing ME 0/5/10:

```
| ME Level | Material Cost | Savings vs ME 0 |
|----------|---------------|------------------|
| ME 0     | (from result) | —                |
| ME 5     | (from result) | (ME0 cost field minus ME5 cost field — use formatted values) |
| ME 10    | (from result) | ... |
```

For savings, use the raw `total_material_cost` numbers to compute the difference, then describe using formatted values from each result.

## DO NOT

- **DO NOT** perform any arithmetic on prices or quantities
- **DO NOT** reformat ISK values — use the `*_formatted` fields as-is
- **DO NOT** query `sde(action="blueprint_info")` or `market(action="prices")` separately
- **DO NOT** present incomplete calculations as complete
- **DO NOT** include speculative pricing or predictions
