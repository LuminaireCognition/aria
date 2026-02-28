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

### T2 Items

T2 BPC ME is fixed by the invention process (base ME 0, modified by decryptor). When the item is T2 and no ME is specified, **skip ME comparison mode** — use ME 0 and present a single result. Add a note:

> T2 BPC ME depends on the decryptor used during invention. Showing ME 0 (invention base). Specify `--me N` to calculate at a different level.

**When the user names a specific decryptor** (e.g., "with the Attainment decryptor"), look up its ME modifier via `sde(action="item_info", item="Attainment Decryptor")` and use the resulting ME value in the `build_cost` call. This is SDE-sourced data, not fabrication. If the SDE lookup fails, fall back to ME 0 with the standard note above.

## Scope Boundaries

The `build_cost` tool calculates manufacturing cost from an existing BPC/BPO. It does **NOT** cover:

- **T2 invention costs** — datacores, decryptors, success rates, amortized attempt costs
- **Recursive build chains** — build-vs-buy at each component tier, vertical integration analysis
- **Job installation fees** — system cost indices, facility taxes, SCC surcharges

If the user's question involves any of these, **state the limitation upfront** before presenting results. Example:

> **Note:** `build_cost` covers manufacturing material cost only. Invention economics (datacore costs, decryptor modifiers, success rates) are not included — the margin shown is manufacturing-only and does not reflect total T2 production cost.

Then present what the tool can provide. Do not attempt to fill the gap with generated analysis. End with a brief actionable pointer for the user (e.g., "Use an external T2 invention calculator to factor in decryptor economics" or "A full vertical integration analysis requires comparing component build costs individually").

### Scope Limitation Ordering

For T2 and complex items, the scope limitation notice MUST appear **immediately after the heading/metadata block and before the BOM table**. A single sentence is sufficient. Do NOT place scope limitations at the end of the response — users scanning quickly will miss them.

### Fabrication Stop-Gate

If you find yourself writing prices, rates, costs, or probabilities that did not come from a `build_cost` tool response, **STOP — you are fabricating**. This includes:

- Datacore or decryptor prices
- Invention success rates or attempt counts
- Amortized invention costs per BPC
- Component self-build cost estimates
- Any "net profitability" that combines tool data with your own numbers

**Bad example (DO NOT do this):**
> Attainment Decryptor: ~2.54M ISK. Datacores: ~31.7K + ~90K ISK. Success rate: ~47%. Amortized invention cost: ~5.8M ISK/BPC. Net profit after invention: -2.7M ISK.

Every number above is fabricated. The correct response states the limitation and stops.

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

**Heading format uses parentheses**, not square brackets: `(complex)` not `[complex]`.

```
## Build Cost: {item_name} ({complexity})

**Blueprint:** blueprint.blueprint_name
**ME Level:** blueprint.me_level (N% material reduction)
**Runs:** blueprint.runs
**Facility:** blueprint.facility (blueprint.facility_me_bonus% ME bonus)

### Bill of Materials

| Material | Category | Base Qty | ME Qty | Price/Unit | Total |
|----------|----------|----------|--------|------------|-------|
(use materials[] — present unit_price_formatted and total_cost_formatted directly)

### Category Subtotals

| Category | Items | Total |
|----------|-------|-------|
(use category_subtotals[] — present category_label, item_count, and total_cost_formatted directly)

**Total Material Cost:** total_material_cost_formatted

### Profitability
(use profitability object — present all *_formatted fields directly)

| Metric | Value |
|--------|-------|
| Material Cost | total_material_cost_formatted |
| Product Value | profitability.product_total_formatted |
| **Gross Profit** | **profitability.gross_profit_formatted** |
| **Margin** | **profitability.margin_pct%** |

(REQUIRED — always include this horizontal rule and footer)
---
*Prices from {region}. Does not include job fees, facility bonuses beyond ME, or taxes.*

(REQUIRED when profitability.margin_pct < 0 AND (me_level < 10 OR no facility):)
For T1 items:
*Consider re-running with higher ME or a facility bonus — e.g. `/build-cost {item_name} --me 10 --facility Azbel`*
For T2 items (do NOT suggest --me 10 — it is unreachable via invention):
*Consider re-running with a facility bonus — e.g. `/build-cost {item_name} --facility Azbel`. Specify `--me N` if your BPC has ME from a decryptor.*
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

### Output Checklist

Every response MUST include all of these elements:
1. Heading: `## Build Cost: {item_name} ({complexity})` — pull `complexity` from `result.complexity` verbatim
2. Blueprint metadata block (name, ME, runs, facility)
3. Bill of Materials table
4. Profitability table
5. Footer disclaimer line
6. Negative-margin suggestion (if margin < 0 and ME < 10 or no facility)

## DO NOT

- **DO NOT** perform any arithmetic on prices or quantities
- **DO NOT** reformat ISK values — use the `*_formatted` fields as-is
- **DO NOT** query `sde(action="blueprint_info")` or `market(action="prices")` separately
- **DO NOT** present incomplete calculations as complete
- **DO NOT** include speculative pricing or predictions
- **DO NOT** fabricate build chain analysis, vertical integration comparisons, or cost estimates not sourced from the tool response
- **DO NOT** answer T2 invention or decryptor questions as if the manufacturing-only margin is the full answer
