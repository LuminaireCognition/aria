---
name: price
description: EVE Online market price lookups. Use for item valuation, buy/sell spreads, or market analysis.
model: sonnet
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

## Command Syntax

```
/price <item_name> [--region]
/price <item_name> [--jita|--amarr|--dodixie|--rens|--hek]
```

Defaults to Jita if no region specified.

## Tool Calls

| Query Type | Call |
|------------|------|
| Price lookup | `market(action="prices", items=["<item>"], region="<hub>")` |
| Order book | `market(action="orders", item="<item>", region="<hub>")` |
| Cross-region | `market(action="spread", items=["<item>"])` |
| Price history | `market(action="history", item="<item>", region="<hub>")` |
| CLI fallback | `uv run aria-esi price "<item>" [--jita|--amarr|...]` |

All prices come from tool calls. If a call fails, say so.

> **HALLUCINATION GUARD:** Every price, volume, and spread figure MUST come from `market()` tool responses in this session. Market prices change constantly — do NOT quote prices from training data. If the tool call fails or returns no data, say "price unavailable" — never substitute a memorized price.

### Field → Source Mapping

| Output Field | Required Source |
|-------------|----------------|
| Sell price | `market(prices)` → `sell` or `market(orders)` → sell orders |
| Buy price | `market(prices)` → `buy` or `market(orders)` → buy orders |
| Volume | `market(orders)` response |
| Spread | Computed from sell − buy (both from tool response) |
| History data | `market(history)` response |
| Item name/ID | `sde(search)` if item not found |

### Anti-Patterns

❌ **WRONG:** "Tritanium sells for 4.10 ISK in Jita" when no tool call was made this session
✅ **RIGHT:** Call `market(action="prices", items=["Tritanium"])` first, then quote the returned price

❌ **WRONG:** Show a price table with plausible-looking numbers without a preceding tool call
✅ **RIGHT:** Every number in the price table traces to a `market()` response field

## Response Format

```markdown
## Price: <Item Name> (<Hub> / <Region>)

**Sell Orders:**
| Best Price | Volume | Location |
|------------|--------|----------|
| 4.10 ISK | 50,000,000 | Jita 4-4 |

**Buy Orders:**
| Best Price | Volume | Location |
|------------|--------|----------|
| 3.95 ISK | 100,000,000 | Jita 4-4 |

**Summary:**
- Sell (Instant Buy): 4.10 ISK
- Buy (Instant Sell): 3.95 ISK
- Spread: 0.15 ISK (3.8%)

*Regional orders from The Forge. Data cached up to 5 minutes.*
```

Show top 5 buy and sell orders by default. Always include volume and spread.

## Empty Results

**Item not found:** Use `sde(action="search", query="<term>")` for close matches.

**No orders for PLEX?**

PLEX trades on the **Global PLEX Market** (region_id `19000001`), not on regional markets.
This change took effect July 7, 2025. Use:
  `market(action="orders", item="PLEX", region_id=19000001)`

Do **not** show regional history data for PLEX — it is stale (last entry July 7, 2025, price ~6M ISK).
The current price is available via the global market query above.

**No orders for Large Skill Injector, Skill Extractor, or Multiple Pilot Training Certificate?**

These items trade on regional markets. Empty results = data gap in the tool. Use this response verbatim:

> No orders returned — this is a data freshness issue with the market data source. [Item] trades on the regional market in-game. Last known price: [from history if available, or "unavailable"].

Do not add explanation, speculation, or commentary about why the data is missing.

**No orders for other items:** Show `average_price` if available. If `prices` has data but `orders` is empty, it may be NES-only (some SKINs/apparel).

## Contextual Suggestions

After price data, suggest ONE related command if relevant:

| Context | Suggest |
|---------|---------|
| Minerals | `/mining-advisory` |
| Ships | `/fitting` |
| Blueprints | `/find [blueprint] --from [system]` |

## Behavior Notes

- Global prices cached 1 hour, regional orders 5 minutes
- No trading advice, price predictions, or market manipulation speculation
- No selling recommendations for pilots with `market_trading: false`
