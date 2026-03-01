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

## Command Syntax

```
/price <item_name> [--region]
/price <item_name> [--jita|--amarr|--dodixie|--rens|--hek]
```

If no region specified, defaults to Jita.

## Hallucination Guard

**All prices and game mechanics MUST come from MCP tool calls or this skill document.** Do not recall, estimate, or assume any price from training data. Do not speculate about why items may or may not be tradeable. If a tool call fails, say so -- never fill in numbers or explanations from memory.

## Mandatory Tool Calls

| Query Type | MCP Dispatcher Call |
|------------|---------------------|
| Price lookup (single/multi) | `market(action="prices", items=["<item>"], region="<hub>")` |
| Order book detail | `market(action="orders", item="<item>", region="<hub>")` |
| Cross-region comparison | `market(action="spread", items=["<item>"])` |
| Price history | `market(action="history", item="<item>", region="<hub>")` |
| **CLI fallback** | `uv run aria-esi price "<item>" [--jita\|--amarr\|...]` |

Use MCP dispatchers as the primary path. Fall back to CLI only if MCP is unavailable.

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

## Error Handling

- **Item not found:** Suggest spelling corrections. Use `sde(action="search", query="<term>")` to find close matches.
- **No market data:** Report "no orders found — this may be a data freshness issue." Show the global average price if available via `market(action="prices")`. Do NOT speculate about why orders are missing (e.g., do not claim items are untradeable or NES-only unless confirmed by the NES section below).
- **No regional orders:** Show global average and suggest trying a different hub.

## NES / PLEX Market Items

PLEX, Skill Extractors, Skill Injectors, and Multiple Pilot Training Certificates trade on the regional market -- query them normally.

Some items (certain SKINs, apparel) are NES-only with no regional orders. Detection: `market(action="prices")` returns data but `market(action="orders")` returns no results. Inform the user and show `average_price` if available.

## Experience-Based Adaptation

For new players, explain spread concept and suggest regional lookup. For veterans, use compact single-line format.

## Contextual Suggestions

After providing price data, suggest ONE related command when contextually relevant:

| Context | Suggest |
|---------|---------|
| Looking up minerals | `/mining-advisory` |
| Looking up ship | `/fitting` |
| Blueprint output | `/find [blueprint] --from [system]` for nearby NPC sources |
| Looking for nearest source | `/find [item] --from [system]` |

## Behavior Notes

- **Cache Awareness:** Global prices cached 1 hour, regional orders 5 minutes
- **Volume Matters:** Show volume at each price point, not just price
- **Spread Calculation:** Always show buy/sell spread for regional data
- **Top N Orders:** Show top 5 buy and sell orders by default

## DO NOT

- **DO NOT** recommend selling items to pilots with `market_trading: false`
- **DO NOT** provide trading advice (buy low, sell high strategies)
- **DO NOT** speculate on price movements or market manipulation
- **DO NOT** recall or estimate prices from training data -- always use tool calls
