---
name: build-cost
description: Manufacturing cost calculator. Use for 'cost to build', profit margins, build-vs-buy, and ME efficiency.
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
argument-hint: "<item_name> [--me LEVEL] [--runs N]"
preferred_max_lines: 50
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

Ask: *Can `build_cost` contribute meaningfully to this query?*

- **Fully in-scope** (T1 item cost, ME comparison, T2 BOM, build vs buy single item) → call `build_cost`, use Response Template
- **Partially in-scope** (vertical integration, build chains, component comparison) → call `build_cost` for the top-level item, render Response Template, then append Partial-Scope Caveat
- **Fully out-of-scope** (invention ROI, datacores, BPC acquisition, success rate analysis) → Out-of-Scope Template, then stop

**Exception:** If the user names a specific decryptor (e.g., "with the Attainment
decryptor"), the query is **partially in-scope**: look up the decryptor's ME modifier
per the T2 Items section, run `build_cost` at that ME level, and present the result
with the T2 scope notice. The user has already made the invention decision — they
want manufacturing-step cost.

"Is it profitable to build [T2 item]?" requires invention economics → out of scope.
"Show me the full build chain for X" → partially in scope: run top-level BOM, append caveat.

> **HALLUCINATION GUARD:** Every ISK figure, material quantity, and margin percentage MUST come from the `market(action="build_cost")` response in this session. Material costs change daily. Do NOT estimate build costs from training data. If the tool call fails, say "build cost unavailable" — never fabricate a BOM.

### Field → Source Mapping

| Output Field | Required Source |
|-------------|----------------|
| Material quantities (base) | `build_cost` → `materials[].base_quantity` |
| Material quantities (ME) | `build_cost` → `materials[].me_quantity` |
| Price per unit | `build_cost` → `materials[].unit_price_formatted` |
| Material total cost | `build_cost` → `materials[].total_cost_formatted` |
| Total material cost | `build_cost` → `total_material_cost_formatted` |
| Product value | `build_cost` → `profitability.product_total_formatted` |
| Gross profit | `build_cost` → `profitability.gross_profit_formatted` |
| Margin | `build_cost` → `profitability.margin_pct` |
| Blueprint name | `build_cost` → `blueprint.blueprint_name` |
| Item complexity | `build_cost` → `complexity` |

### Anti-Patterns

❌ **WRONG:** "A Dominix costs about 250M to build at ME 10" when no `build_cost` call was made
✅ **RIGHT:** Call `market(action="build_cost", item="Dominix", me_level=10)` first, then use `total_material_cost_formatted`

❌ **WRONG:** Present a BOM table with rounded/estimated material costs
✅ **RIGHT:** Every cell in the BOM table uses a `*_formatted` field from the tool response

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
- **Fuzzwork Industry Planner** (fuzzwork.co.uk/industry) — full vertical integration analysis, invention chains, and job cost index lookup in one place

Want me to run the manufacturing-only cost?
```

### Partial-Scope Caveat

Append after the Response Template when the query asked for vertical integration or build chains:

```
---
**Scope note:** The table above shows the top-level manufacturing cost for {item_name}.
Full vertical integration (building sub-components rather than buying them) requires:
- Per-component BOM: run `/build-cost {component}` individually for each intermediate material
- Job fee comparison: system cost index × component value (check Fuzzwork Industry Planner)
- **Fuzzwork Industry Planner** (fuzzwork.co.uk/industry) — full vertical chain, invention costs, and job index in one view
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

## Output format

- BOM table: top 5 materials by cost contribution, then "... and N more (X ISK total)"
- Never include CLI error traces, debugging output, or git investigation in responses
- Target: ≤30 lines

## Rules

- Every ISK figure must trace to a `build_cost` response field
- One tool: `market(action="build_cost")` — no side-queries to `sde(blueprint_info)` or `market(prices)`
- For T2/invention/vertical queries, follow the Query Classification Gate
- Append a one-line `Sources:` footer listing MCP calls made
