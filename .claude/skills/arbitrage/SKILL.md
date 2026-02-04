---
name: arbitrage
description: Cross-region arbitrage opportunity scanner. Find profitable trade routes between trade hubs with hauling score analysis.
model: haiku
category: financial
triggers:
  - "/arbitrage"
  - "arbitrage opportunities"
  - "trade route finder"
  - "what can I haul for profit"
  - "cross-region trading"
  - "price gaps between hubs"
requires_pilot: false
---

# ARIA Market Arbitrage Module (V2)

## Purpose

Scan for cross-region arbitrage opportunities across EVE's major trade hubs. Identifies items where buying in one region and selling in another yields profit.

**V2 Features:**
- **Hauling Score:** Ranks by profit per m³ of transport capacity (requires `--cargo`).
- **Net Profit:** Calculates true profit after broker fees and sales tax.
- **Liquidity Analysis:** Caps quantity at 10% of daily volume (requires `--history`).
- **Transport Capacity:** Limits quantity by your ship's cargo space.
- **Ad-hoc Scopes:** Extend analysis beyond trade hubs to custom regions, stations, or structures.

## Trigger Phrases

- "/arbitrage"
- "arbitrage opportunities"
- "trade route finder"
- "what can I haul for profit"
- "cross-region trading"
- "price gaps between hubs"

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

### Trade Modes & Fees

Affects how net profit is calculated:
- **immediate** (default): Take sell orders → Take buy orders. **Fees:** Sales tax only. Best for haulers.
- **hybrid**: Take sell orders → Place sell order. **Fees:** Broker + Sales tax on sell.
- **station_trading**: Place buy order → Place sell order. **Fees:** Broker on both + Sales tax.

## MCP Tools Used

### `market_arbitrage_scan`

Primary scan tool. Queries `region_prices` table for profitable spreads.

**Parameters:**
- `cargo_capacity_m3` (float): Transport capacity.
- `sort_by` (str): `margin`, `profit_density`, `hauling_score`.
- `include_history` (bool): Fetch market history.
- `trade_mode` (str): Execution strategy.
- `min_profit_pct` (float): Minimum profit %.
- `max_results` (int): Maximum results (default 20).
- `include_custom_scopes` (bool): Include ad-hoc scope data (default False).
- `scopes` (list[str]): Specific scope names to include.
- `scope_owner_id` (int): Character ID for scope ownership resolution.

### `market_arbitrage_detail`

Detailed analysis for a specific opportunity.

**Parameters:**
- `type_name` (str): Item name
- `buy_region` (str): Region to buy from
- `sell_region` (str): Region to sell to

## Response Format

### Scan Results (Hauling Score Mode)

```
═══════════════════════════════════════════════════════════════════
ARBITRAGE OPPORTUNITIES (60,000 m³ capacity)
Mode: immediate (Net profit uses sales tax only)
───────────────────────────────────────────────────────────────────
| Item                | Route      | Net Margin | Score    | Limit     |
|---------------------|------------|------------|----------|-----------|
| Skill Injector      | Amarr→Jita | 4.3%       | 63K/m³   | liquidity |
| Neurovisual         | Jita→Amarr | 7.8%       | 6.4K/m³  | liquidity |
| Tritanium           | Jita→Dodix | 2.2%       | 42/m³    | cargo     |

Score = Net ISK profit per m³ of transport capacity
Limit = Binding constraint (cargo | liquidity | market supply)
═══════════════════════════════════════════════════════════════════
```

## Fee Calculation

V2 uses updated defaults based on typical standings:

| Fee Type | Default | Notes |
|----------|---------|-------|
| Broker Fee | 3.0% | Varies by standings/skills (min 1.0%) |
| Sales Tax | 3.6% | Accounting IV default (max 8.0%, min 3.6%) |

Net Profit = Sell Revenue (after tax/fees) - Buy Cost (after fees)

## Limits & Constraints

- **Cargo Limit:** `cargo_capacity / item_volume`
- **Liquidity Limit:** `daily_volume * 10%` (requires history)
- **Market Limit:** `min(buy_available, sell_available)`
- **Safe Quantity:** `min(cargo, liquidity, market)`

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

Extend arbitrage analysis beyond the 5 trade hubs by adding custom market scopes.

**Full documentation:** `docs/ADHOC_MARKETS.md`

### Quick Setup

1. **Create a watchlist** (bounds which items to fetch):
```
market_watchlist_create("my_items", items=["Tritanium", "Pyerite"])
```

2. **Create a scope** (defines the market location):
```
market_scope_create("Everyshore", "region", 10000037, "my_items")
```

3. **Refresh data** (fetch from ESI):
```
market_scope_refresh("Everyshore")
```

4. **Include in scan**:
```
market_arbitrage_scan(include_custom_scopes=True, scopes=["Everyshore"])
```

### Scope Types

| Type | Cost | Notes |
|------|------|-------|
| `region` | Low | Fetches per type_id |
| `station` | Low | Filters region by station |
| `system` | Low | Filters region by system |
| `structure` | **High** | Fetches ALL orders, filters locally |

### Result Labels

When ad-hoc scopes are included, results contain provenance metadata:

| Field | Description |
|-------|-------------|
| `buy_scope_name` | Source scope for buy side |
| `sell_scope_name` | Source scope for sell side |
| `source_type` | `fuzzwork` (hubs) or `esi` (ad-hoc) |
| `data_age` | Age of CCP data |
| `is_truncated` | True if data may be incomplete |

## DO NOT

- **DO NOT** use `profit_pct` for sorting (it's gross margin). Use `net_margin_pct`.
- **DO NOT** ignore liquidity. High margin items often have low volume.
- **DO NOT** assume all items fit in cargo (check packaged volume).

---

## Persona Adaptation

This skill supports persona-specific overlays. When active persona has an overlay file, load additional context from:

```
personas/{active_persona}/skill-overlays/arbitrage.md
```
