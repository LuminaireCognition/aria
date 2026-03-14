---
name: arbitrage
description: Cross-region arbitrage opportunity scanner. Find profitable trade routes between trade hubs with hauling score analysis.
model: sonnet
category: financial
triggers:
  - "/arbitrage"
  - "arbitrage opportunities"
  - "trade route finder"
  - "what can I haul for profit"
  - "cross-region trading"
  - "price gaps between hubs"
requires_pilot: false
argument-hint: "[--cargo M3] [--sort mode] [--min-profit %]"
allowed-tools: [Read, Grep, Glob, "mcp__aria-universe__market"]
---

# ARIA Market Arbitrage Module (V2)

## Command Syntax

```
/arbitrage [options]
/arbitrage --cargo 60000 --sort hauling_score --history
/arbitrage detail <item> <buy_region> <sell_region>
```

### Scan Options

| Option | Argument | Description |
|--------|----------|-------------|
| `--cargo` | `m3` | Ship transport capacity (e.g., 60000). Required for hauling score. |
| `--sort` | `mode` | Ranking: `margin` (default), `profit_density`, `hauling_score` |
| `--history` | (flag) | Fetch daily volume history for liquidity analysis (slower) |
| `--min-profit` | `pct` | Minimum gross profit percentage (default 5.0) |
| `--min-volume` | `units` | Minimum available volume (default 10) |
| `--max-results` | `count` | Maximum opportunities to return (default 20) |
| `--trade-mode` | `mode` | `immediate` (default), `hybrid`, `station_trading` |
| `--force-refresh` | (flag) | Force data refresh before scanning |
| `--scopes` | `names` | Ad-hoc scope names to include (comma-separated) |
| `--include-scopes` | (flag) | Enable ad-hoc scope data in scan |

**Note on default filters:** The default `--min-profit 5` (5% minimum margin) often returns 0 results during low-volatility periods when trade hub prices are closely aligned.

**Empty results recovery sequence:**
1. Retry at `min_profit_pct=2`, then `min_profit_pct=1` before reporting no opportunities
2. Try different `sort_by` values: `hauling_score` (best for haulers), `profit_density` (ISK/m³)
3. Try `trade_mode="hybrid"` or `trade_mode="station_trading"` for different fee structures

**Expected response schema** (even when empty): `opportunities` (list), `scan_params` (dict with filters used), `market_summary` (dict with hub price freshness). When results exist, each opportunity includes: `type_name`, `buy_price`, `sell_price`, `margin_pct`, `volume`, `profit_per_unit`, `buy_region`, `sell_region`.

### Empty Results: Scan Diagnostics Block

When `opportunities` is empty after all recovery steps, **always render the Scan Diagnostics block** before offering fallback options. This lets the user (and reviewer) verify the scanner ran correctly rather than failed silently.

```
**Scan Diagnostics**
- Filters tried: [list thresholds attempted, e.g. "min_profit 5% → 2% → 1%"; trade modes tried — from scan_params]
- Data freshness: [hub price ages — from market_summary, e.g. "Jita: 4m ago, Amarr: 12m ago"]
- Best near-miss: [highest-margin item found below threshold, with margin% and route — if available in response; otherwise "none returned"]
- Items evaluated: [count if returned by tool; otherwise omit line]
```

Use `scan_params` and `market_summary` from the tool response to populate this block. Do not omit it — an empty Scan Diagnostics block (all "none") is still more informative than silence.

### Trade Modes & Fees

Affects how net profit is calculated:
- **immediate** (default): Take sell orders → Take buy orders. **Fees:** Sales tax only. Best for haulers.
- **hybrid**: Take sell orders → Place sell order. **Fees:** Broker + Sales tax on sell.
- **station_trading**: Place buy order → Place sell order. **Fees:** Broker on both + Sales tax.

## MCP Tools

Use `market(action="arbitrage_scan")` and `market(action="arbitrage_detail")` — see MCP tool schema for parameters.

### Natural Language Parameter Extraction

When the user describes parameters in natural language, extract and map to MCP tool arguments:

| User phrase | MCP parameter | Value |
|-------------|--------------|-------|
| "60000 m3 cargo" / "my Bustard" | `cargo_capacity` | Extract m3 number; for ship names use known cargo capacity |
| "sorted by hauling score" | `sort_by` | `hauling_score` |
| "with volume history" | `include_history` | `true` |
| "minimum 10% profit" / "above 15%" | `min_profit_pct` | Extract number |
| "station trading" | `trade_mode` | `station_trading` |
| "include my scopes" | `include_custom_scopes` | `true` |

**MANDATORY:** If the user specifies parameters, pass them to `market(action="arbitrage_scan", ...)`. Do not silently use defaults when the user provided explicit values.

## Response Format

Present results as a markdown table:

| Item | Route | Net Margin | Score | Limit |
|------|-------|------------|-------|-------|

- **Score** = Net ISK profit per m³ of transport capacity
- **Limit** = Binding constraint (cargo | liquidity | market supply)

## Fee Calculation

V2 uses updated defaults based on typical standings:

| Fee Type | Default | Notes |
|----------|---------|-------|
| Broker Fee | 3.0% | Varies by standings/skills (min 1.0%) |
| Sales Tax | 3.6% | Accounting IV default (max 8.0%, min 3.6%) |

Net Profit = Sell Revenue (after tax/fees) - Buy Cost (after fees)

## Limits & Constraints

The MCP tool calculates cargo, liquidity, and market limits internally. The binding constraint is returned as the `limit` field in each opportunity.

## Use Cases

### Hauler Optimization
"What should I haul in my Bustard (60k m³)?"
```
/arbitrage --cargo 60000 --sort hauling_score --history
```

### High Margin Search
"Show me high-profit opportunities"
```
/arbitrage --min-profit 15 --sort margin
```

### Station Trading
"High margin items for station trading"
```
/arbitrage --trade-mode station_trading --sort margin
```

### Ad-hoc Scope Integration
"Include my custom Everyshore scope"
```
/arbitrage --include-scopes --scopes "Everyshore Minerals"
```

## Ad-hoc Market Scopes

Ad-hoc scopes extend scanning beyond the 5 trade hubs. Pass `include_custom_scopes=True` and `scopes=[...]` to the scan. Full setup and scope types: `docs/ADHOC_MARKETS.md`.

## DO NOT

- **DO NOT** use `profit_pct` for sorting (it's gross margin). Use `net_margin_pct`.
- **DO NOT** ignore liquidity. High margin items often have low volume.
- **DO NOT** assume all items fit in cargo (check packaged volume).
- Append a one-line `Sources:` footer listing MCP calls made

