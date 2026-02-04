---
name: find
description: Find market sources near your location. Use for finding blueprints, items, or specific market sources by proximity.
model: haiku
category: financial
triggers:
  - "/find"
  - "find [item] near me"
  - "where can I buy [item]"
  - "nearest [item]"
  - "find blueprint for [item]"
  - "NPC selling [item]"
requires_pilot: false
---

# ARIA Proximity Market Search Module

## Purpose

Find market sources for items near a specific location. Unlike `/price` which shows region-wide market data, `/find` locates specific stations selling an item sorted by distance from your position. Particularly useful for:

- Finding NPC-seeded blueprints (automatically filters to NPC orders)
- Locating hard-to-find items in nearby stations
- Identifying the closest source when you need something urgently

Uses the `market_find_nearby` MCP tool for proximity-based market search.

## Trigger Phrases

- "/find"
- "find [item] near me"
- "where can I buy [item]"
- "nearest [item]"
- "find blueprint for [item]"
- "NPC selling [item]"

## Command Syntax

```
/find <item_name> [--from <system>] [--jumps <max>] [--npc|--player|--all]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `item_name` | Item to search for (name or partial name). Use quotes for multi-word names. |

### Flags

| Flag | Description |
|------|-------------|
| `--from <system>` | Origin system for distance calculation. Defaults to current location if authenticated. |
| `--jumps <n>` | Maximum jump distance to include (default: 20, max: 50) |
| `--npc` | Only show NPC-seeded orders (364+ day duration) |
| `--player` | Only show player orders |
| `--all` | Show both NPC and player orders (default) |
| `--expand` | Search neighboring regions (default: true) |

## Smart Defaults

ARIA automatically suggests the best source filter based on item category:

| Category | Default Filter | Reason |
|----------|---------------|--------|
| Blueprint | `npc` | Most T1 BPOs are NPC-seeded |
| Skillbook | `npc` | All skillbooks are NPC-seeded |
| Module | `all` | Player and NPC sources both common |
| Ship | `all` | Player market primary source |
| Other | `all` | Check all sources |

When the suggested filter differs from the applied filter, ARIA will note this in the response.

## MCP Tool

This skill uses the `market_find_nearby` MCP tool:

```
market_find_nearby(
  item: str,           # Item name (fuzzy matched)
  origin: str,         # Starting system
  max_jumps: int,      # Maximum distance (default: 20)
  order_type: str,     # "sell", "buy", or "all"
  source_filter: str,  # "all", "npc", or "player"
  expand_regions: bool, # Search neighbor regions (default: true)
  max_regions: int,    # Max regions to search (default: 5)
  limit: int           # Max results (default: 10)
)
```

## Response Format

### Standard Results

```markdown
## Finding: Venture Blueprint

**Origin:** Sortet (Everyshore)
**Filter:** NPC orders only (suggested for blueprints)
**Regions searched:** Everyshore, Sinq Laison, Placid

| # | System | Sec | Station | Price | Vol | Jumps |
|---|--------|-----|---------|-------|-----|-------|
| 1 | Oursulaert | 0.87 | Fed Navy Assembly | 250,000 | 10 | 3 |
| 2 | Dodixie | 0.87 | Fed Navy Logistics | 250,000 | 5 | 8 |
| 3 | Villore | 0.86 | Fed Navy Academy | 250,000 | 10 | 12 |

**Best options:**
- **Nearest:** Oursulaert (3 jumps)
- **Cheapest:** All sources have same price
- **Best value:** Oursulaert (balances price and distance)

*Total found: 5 sources across 3 regions*
```

### NPC Blueprint Search

```markdown
## Finding: Pioneer Blueprint

**Origin:** Jita (The Forge)
**Filter:** NPC orders only (suggested for blueprints)
**Regions searched:** The Forge, Lonetrek, The Citadel, Metropolis, Heimatar

| # | System | Sec | Station | Price | Vol | Jumps |
|---|--------|-----|---------|-------|-----|-------|
| 1 | X7R-LB | -0.04 | ORE Refinery | 65,000,000 | 1 | 42 |

**Best options:**
- **Nearest:** X7R-LB (42 jumps) - ORE-exclusive blueprint
- **Best value:** X7R-LB (only source)

**Route warning:** Route passes through null-sec space.

*Note: Pioneer Blueprint is only sold by ORE Corporation in Outer Ring.*
```

### No Results Found

```markdown
## Finding: Venture Blueprint

**Origin:** PR-8CA (Providence)
**Filter:** NPC orders only

No NPC sources found within 20 jumps.

**Suggestions:**
- Increase search radius: `/find "Venture Blueprint" --from PR-8CA --jumps 50`
- Try nearest trade hub: `/find "Venture Blueprint" --from Amarr`
- Check player market: `/find "Venture Blueprint" --all`
```

## Error Handling

### Item Not Found

```json
{
  "error": "item_not_found",
  "message": "Could not find item: Ventrue Blueprint",
  "suggestions": ["Venture Blueprint", "Venture", "Venture Mining Frigate"],
  "hint": "Check spelling. Item names are fuzzy-matched."
}
```

### System Not Found

```json
{
  "error": "system_not_found",
  "message": "Unknown system: Jitta",
  "hint": "Check spelling. System names are case-insensitive."
}
```

## Experience-Based Adaptation

### New Players

```
Finding: Venture Blueprint

I found the Venture Blueprint at 3 nearby NPC stations!

**Closest option:**
Oursulaert - Federal Navy Assembly Plant (3 jumps)
Price: 250,000 ISK

This is an NPC-seeded blueprint, meaning the price is fixed and stock
refreshes automatically. You can buy the Blueprint Original (BPO) to
manufacture Ventures yourself.

Tip: BPOs have unlimited uses. The first copy you make is an ME/TE 0
blueprint. Research it first for better efficiency!
```

### Veterans

```
Venture BPO | Oursulaert (3j) | 250k | Fed Navy | NPC
           | Dodixie (8j) | 250k | Fed Navy Logistics | NPC
```

## Use Cases

### Finding NPC Blueprints

"Where can I buy an Orca Blueprint?" - Searches for NPC-seeded BPOs, identifies ORE stations in Outer Ring.

### Urgent Module Need

"Find Damage Control II near Amarr" - Locates closest player market sources for immediate purchase.

### Regional Shopping

"Find Nanite Repair Paste within 10 jumps of Rens" - Limited radius search for consumables.

## Self-Sufficiency Integration

For pilots with `market_trading: false`, this skill focuses on:

- **Finding NPC sources:** Blueprint Originals for manufacturing
- **Local availability:** What's nearby vs. needing to travel
- **Minimizing market dependency:** Identifying self-sufficient alternatives

ARIA will not recommend distant trade hubs if local NPC sources exist.

## Contextual Suggestions

After providing results, suggest related commands when appropriate:

| Context | Suggest |
|---------|---------|
| Blueprint found | "Use `/price` to check manufactured item value" |
| Long route to source | "Use `/route` to plan safe travel" |
| Low-sec source | "Use `/threat-assessment` for route safety" |
| No local sources | "Check `/arbitrage` for hauling opportunities" |

## Behavior Notes

- **NPC Detection:** Orders with duration >= 364 days are classified as NPC-seeded
- **Multi-Region Search:** Automatically searches neighboring regions when enabled
- **Distance Calculation:** Uses bounded BFS from origin system
- **Best Value Scoring:** Balances price and travel distance based on item value
- **Price Anomaly Detection:** Warns about suspiciously high prices

## DO NOT

- **DO NOT** recommend distant purchases to self-sufficient pilots
- **DO NOT** suggest market manipulation strategies
- **DO NOT** provide exact route details (defer to `/route` skill)
- **DO NOT** assume authentication - origin must be provided if not authenticated

---

## Persona Adaptation

This skill supports persona-specific overlays. When active persona has an overlay file, load additional context from:

```
personas/{active_persona}/skill-overlays/find.md
```

If no overlay exists, use the default (empire) framing above.
