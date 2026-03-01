---
name: build-cost
description: Manufacturing cost calculator. Calculates material costs, profit margins, and ME efficiency.
model: sonnet
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

## Query Classification Gate

**Do this first.** The `build_cost` tool returns manufacturing material cost for one assembly step. It knows nothing about invention, datacores, decryptors, success rates, or BPC acquisition.

Ask: *Can `build_cost` alone fully answer this query?*

- **Yes** (T1 item, or T2 material/BOM cost only) → call `build_cost`, use Response Template
- **No** (T2 profitability, invention ROI, vertical integration, build chains) → Out-of-Scope Template, then stop

"Is it profitable to build [T2 item]?" requires invention economics → out of scope.

### Out-of-Scope Template

Emit verbatim, then stop:

```
## Build Cost: {item_name}

Answering this fully requires [invention economics / vertical integration analysis / job fee
data] — which the `build_cost` tool does not provide. I can only show manufacturing material
cost for a single assembly step.

**What I can do:** `/build-cost {item_name}` — material cost assuming you already have a BPC.

**What you'd need externally:**
- Invention calculator (datacores, decryptor choice, success rates)
- Component build-vs-buy comparison (run `/build-cost` per component individually)
- Job fee estimator (system cost index × item value)

Want me to run the manufacturing-only cost?
```

## Implementation

**Single tool call.** All computation is server-side.

```python
market(action="build_cost", item="Dominix", me_level=10, runs=1, facility="Azbel", region="jita")
```

Extract from the user request: `item` (required), `me_level` (default 0), `runs` (default 1), `facility` (default None), `region` (default "jita").

### ME Comparison Mode

When no ME is specified, make 3 parallel calls for ME 0, 5, and 10. Present as a comparison table with cost and savings at each level.

### T2 Items

T2 BPC ME is fixed by invention (base ME 0, modified by decryptor). Skip ME comparison — use ME 0 and present a single result with this note:

> T2 BPC ME depends on the decryptor used during invention. Showing ME 0 (invention base). Specify `--me N` to calculate at a different level.

If the user names a decryptor, look up its ME modifier via `sde(action="item_info", item="<Decryptor Name>")` and use that ME value. Only use the ME modifier — do not estimate any other decryptor effects.

For T2 items, add this scope notice immediately after the heading:

> **Scope:** Manufacturing material cost only. Invention inputs (datacores, decryptors, success rates) are not included. The margin shown is manufacturing-step-only.

After the profitability table, do not estimate or speculate about invention costs, success rates, or net profitability. End with the footer.

## Response Template

Use `*_formatted` fields from the tool response as-is. No arithmetic, no reformatting.

If `found` is false, show suggestions from the response.

If `is_complete` is false, lead with **INCOMPLETE CALCULATION** warning (missing prices, totals understated).

```
## Build Cost: {item_name} ({complexity})

**Blueprint:** blueprint.blueprint_name
**ME Level:** blueprint.me_level | **Runs:** blueprint.runs
**Facility:** blueprint.facility (blueprint.facility_me_bonus% ME bonus)

### Bill of Materials

| Material | Category | Base Qty | ME Qty | Price/Unit | Total |
|----------|----------|----------|--------|------------|-------|
(from materials[] — use unit_price_formatted, total_cost_formatted)

### Category Subtotals

| Category | Items | Total |
|----------|-------|-------|
(from category_subtotals[])

**Total Material Cost:** total_material_cost_formatted

### Profitability

| Metric | Value |
|--------|-------|
| Material Cost | total_material_cost_formatted |
| Product Value | profitability.product_total_formatted |
| **Gross Profit** | **profitability.gross_profit_formatted** |
| **Margin** | **profitability.margin_pct%** |

---
*Prices from {region}. Does not include job fees, facility bonuses beyond ME, or taxes.*
```

If margin < 0 and there's room to improve (ME < 10 for T1, or no facility), suggest re-running with better parameters. For T2, do not suggest `--me 10` (unreachable via invention).

## Rules

- Every ISK figure must trace to a `build_cost` response field
- One tool: `market(action="build_cost")` — no side-queries to `sde(blueprint_info)` or `market(prices)`
- For T2/invention/vertical queries, follow the Query Classification Gate
