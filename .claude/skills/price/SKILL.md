---
name: price
description: EVE Online market price lookups. Use for item valuation, buy/sell spreads, or market analysis.
model: haiku
category: financial
triggers:
  - "/price"
  - "price check [item]"
  - "how much is [item] worth"
  - "what's [item] selling for"
  - "market price for [item]"
  - "value of [item]"
requires_pilot: false
---

# ARIA Market Price Module

## Purpose
Query market prices for items in EVE Online. Useful for loot valuation, manufacturing cost analysis, LP store comparisons, and general market awareness. Uses public ESI endpoints (no authentication required).

## Trigger Phrases
- "/price"
- "price check [item]"
- "how much is [item] worth"
- "what's [item] selling for"
- "market price for [item]"
- "value of [item]"

## Command Syntax

```
/price <item_name> [--region]
/price <item_name> [--jita|--amarr|--dodixie|--rens|--hek]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `item_name` | Item to look up (name or type_id). Use quotes for multi-word names. |

### Region Flags

| Flag | Region | Trade Hub |
|------|--------|-----------|
| `--jita` | The Forge (10000002) | Jita 4-4 |
| `--amarr` | Domain (10000043) | Amarr VIII |
| `--dodixie` | Sinq Laison (10000032) | Dodixie IX |
| `--rens` | Heimatar (10000030) | Rens VI |
| `--hek` | Metropolis (10000042) | Hek VIII |

If no region specified, returns global average price only.

## ESI Endpoints

### Global Prices (Default)
**Endpoint:** `GET /markets/prices/`
**Authentication:** None required (public)
**Cache:** 3600 seconds (1 hour)
**Returns:** adjusted_price and average_price for all items

### Regional Orders (With Region Flag)
**Endpoint:** `GET /markets/{region_id}/orders/`
**Authentication:** None required (public)
**Cache:** 300 seconds (5 minutes)
**Parameters:**
- `region_id` - Region ID
- `type_id` - Item type ID
- `order_type` - `buy`, `sell`, or `all`

## Response Format

### Simple Price (No Region)

```markdown
## Price: Tritanium

| Metric | Value |
|--------|-------|
| Average Price | 4.50 ISK |
| Adjusted Price | 4.32 ISK |

*Global average from ESI market data.*
```

### Regional Price (With Region Flag)

```markdown
## Price: Tritanium (Jita / The Forge)

**Sell Orders:**
| Best Price | Volume | Location |
|------------|--------|----------|
| 4.10 ISK | 50,000,000 | Jita 4-4 |
| 4.15 ISK | 12,000,000 | Jita 4-4 |

**Buy Orders:**
| Best Price | Volume | Location |
|------------|--------|----------|
| 3.95 ISK | 100,000,000 | Jita 4-4 |
| 3.90 ISK | 25,000,000 | Jita 4-4 |

**Summary:**
- Sell (Instant Buy): 4.10 ISK
- Buy (Instant Sell): 3.95 ISK
- Spread: 0.15 ISK (3.8%)

*Regional orders from The Forge. Data cached for 5 minutes.*
```

### Formatted Response (rp_level: moderate or full)

```
═══════════════════════════════════════════════════════════════════
ARIA MARKET INTELLIGENCE
───────────────────────────────────────────────────────────────────
ITEM:    Tritanium (Type ID: 34)
REGION:  The Forge (Jita)
───────────────────────────────────────────────────────────────────
SELL ORDERS (Instant Buy):
  4.10 ISK .... 50,000,000 units @ Jita 4-4
  4.15 ISK .... 12,000,000 units @ Jita 4-4

BUY ORDERS (Instant Sell):
  3.95 ISK .... 100,000,000 units @ Jita 4-4
  3.90 ISK ....  25,000,000 units @ Jita 4-4

SPREAD: 0.15 ISK (3.8%)
───────────────────────────────────────────────────────────────────
Global Average: 4.50 ISK | Adjusted: 4.32 ISK
Data cached for 5 minutes. Real-time conditions may vary.
═══════════════════════════════════════════════════════════════════
```

## JSON Output Format

```json
{
  "query_timestamp": "2026-01-15T10:30:00Z",
  "volatility": "semi_stable",
  "item": {
    "type_id": 34,
    "name": "Tritanium"
  },
  "global_prices": {
    "average_price": 4.50,
    "adjusted_price": 4.32
  },
  "regional_data": {
    "region_id": 10000002,
    "region_name": "The Forge",
    "hub_name": "Jita",
    "sell_orders": [
      {"price": 4.10, "volume": 50000000, "location": "Jita IV - Moon 4 - Caldari Navy Assembly Plant"},
      {"price": 4.15, "volume": 12000000, "location": "Jita IV - Moon 4 - Caldari Navy Assembly Plant"}
    ],
    "buy_orders": [
      {"price": 3.95, "volume": 100000000, "location": "Jita IV - Moon 4 - Caldari Navy Assembly Plant"},
      {"price": 3.90, "volume": 25000000, "location": "Jita IV - Moon 4 - Caldari Navy Assembly Plant"}
    ],
    "best_sell": 4.10,
    "best_buy": 3.95,
    "spread": 0.15,
    "spread_percent": 3.8
  }
}
```

## Error Handling

### Item Not Found

```json
{
  "error": "item_not_found",
  "message": "Could not find item: Tritainium",
  "hint": "Check spelling. Item names are case-insensitive.",
  "suggestions": ["Tritanium"],
  "query_timestamp": "2026-01-15T10:30:00Z"
}
```

### No Market Data

```json
{
  "error": "no_market_data",
  "message": "No market data available for: Tritanium Blueprint",
  "hint": "This item may not be tradeable on the market.",
  "query_timestamp": "2026-01-15T10:30:00Z"
}
```

### No Regional Orders

```json
{
  "error": "no_regional_orders",
  "message": "No sell orders for Tritanium in Domain",
  "global_prices": {
    "average_price": 4.50,
    "adjusted_price": 4.32
  },
  "query_timestamp": "2026-01-15T10:30:00Z"
}
```

## Experience-Based Adaptation

### New Players

```
Price: Tritanium

Global Average: 4.50 ISK per unit

This is the average price across all of New Eden. Prices vary by region:
- Jita (The Forge) typically has the best prices and highest volume
- Smaller trade hubs may have higher prices but less competition

To see regional buy/sell orders, try: /price Tritanium --jita

Tip: The "sell price" is what you pay to buy instantly. The "buy price"
is what you receive when selling instantly. The difference is the "spread"
- that's where traders make their profit.
```

### Veterans

```
Tritanium | 4.50 ISK avg | 4.32 adj
Jita: 4.10 sell / 3.95 buy | 3.8% spread
```

## Script Command

```bash
# Global average price
uv run aria-esi price Tritanium

# Regional prices (Jita)
uv run aria-esi price Tritanium --jita

# Multi-word item names
uv run aria-esi price "Hammerhead II" --jita

# Other trade hubs
uv run aria-esi price Veldspar --amarr
uv run aria-esi price "Medium Shield Extender II" --dodixie
```

## Use Cases

### Loot Valuation
"Is this worth hauling back?" - Quick price check to decide if loot is valuable enough to transport.

### Manufacturing Cost Analysis
Check mineral and component prices to estimate production costs. Compare against finished product prices.

### LP Store Optimization
Compare LP store item prices against market to calculate ISK/LP ratios.

### Salvage Prioritization
Check salvage component prices to prioritize what to keep vs. reprocess.

## Self-Sufficiency Integration

For pilots with `market_trading: false`, price lookups are still valuable for:
- **Reprocessing decisions:** Is it better to reprocess or use directly?
- **LP store purchases:** What gives best value for LP?
- **Loot triage:** What's worth keeping for personal use?

ARIA will not suggest "sell this on the market" to self-sufficient pilots.

## Contextual Suggestions

After providing price data, suggest related commands when appropriate:

| Context | Suggest |
|---------|---------|
| Looking up minerals | "For mining recommendations, try `/mining-advisory`" |
| Looking up ship | "For fitting assistance, try `/fitting`" |
| Looking up blueprint output | "Check your `/corp blueprints` for ME/TE levels" |
| Blueprint prices | "For nearby NPC sources, try `/find [blueprint] --from [system]`" |
| Looking for nearest source | "For proximity search, use `/find [item] --from [system]`" |

## Behavior Notes

- **No Auth Required:** Market data is a public endpoint
- **Cache Awareness:** Global prices cached 1 hour, regional orders 5 minutes
- **Volume Matters:** Show volume at each price point, not just price
- **Station Names:** Resolve station IDs to human-readable names
- **Spread Calculation:** Always show buy/sell spread for regional data
- **Top N Orders:** Show top 5 buy and sell orders by default

## Trade Hub Station IDs

For filtering orders to main trade hub stations:

| Hub | Station ID | Station Name |
|-----|------------|--------------|
| Jita | 60003760 | Jita IV - Moon 4 - Caldari Navy Assembly Plant |
| Amarr | 60008494 | Amarr VIII (Oris) - Emperor Family Academy |
| Dodixie | 60011866 | Dodixie IX - Moon 20 - Federation Navy Assembly Plant |
| Rens | 60004588 | Rens VI - Moon 8 - Brutor Tribe Treasury |
| Hek | 60005686 | Hek VIII - Moon 12 - Boundless Creation Factory |

## DO NOT

- **DO NOT** recommend selling items to pilots with `market_trading: false`
- **DO NOT** provide trading advice (buy low, sell high strategies)
- **DO NOT** speculate on price movements or market manipulation
- **DO NOT** cache results locally (ESI handles caching)

---

## Persona Adaptation

This skill supports persona-specific overlays. When active persona has an overlay file, load additional context from:

```
personas/{active_persona}/skill-overlays/price.md
```

If no overlay exists, use the default (empire) framing above.
