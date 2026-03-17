---
name: find
description: Find market sources near your location. Use for finding blueprints, items, or specific market sources by proximity.
category: financial
triggers:
  - "/find"
  - "find [item] near me"
  - "where can I buy [item]"
  - "nearest [item]"
  - "find blueprint for [item]"
  - "NPC selling [item]"
requires_pilot: false
argument-hint: "<item_name> [--near SYSTEM]"
---

# ARIA Proximity Market Search Module

Unlike `/price` (region-wide market data), `/find` locates specific stations selling an item sorted by distance from your position. Particularly useful for NPC-seeded blueprints, hard-to-find items, and urgent purchases.

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

### Blueprint and Skillbook Fallback

If `market(action="find_nearby", source_filter="npc")` returns empty results for blueprints or skillbooks, fall back to `market(action="npc_sources", item=...)` which queries SDE NPC seeding data directly rather than filtering live market orders. This is more reliable for NPC-exclusive items where no active orders may exist in nearby regions.

**Fallback pattern:**
```python
# Step 1: Try proximity search
result = market(action="find_nearby", item="Venture Blueprint", origin="Sortet", source_filter="npc")

# Step 2: If empty, use NPC sources
if not result.get("sources"):
    result = market(action="npc_sources", item="Venture Blueprint")
```

**Note:** `npc_sources` does not include distance data. Use `universe(action="route")` to calculate jump counts from the NPC source systems if needed.


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

On item or system not found, suggest corrections based on fuzzy match suggestions from the tool.

For pilots with `market_trading: false`, prefer NPC sources over distant trade hubs.

## Security Classification

When displaying system security in results:

| Displayed Sec | Classification | Formatting |
|---------------|---------------|------------|
| >= 0.5        | Highsec       | No warning indicator |
| 0.1 - 0.4    | Lowsec        | Flag with warning |
| <= 0.0        | Nullsec       | Flag with warning |

**Do not flag highsec systems (>= 0.5) as dangerous.** Systems like Uedama (0.51) are highsec despite ganking activity — flag only if the pilot specifically asks about gank risk.

## Contextual Suggestions

After providing results, suggest related commands when appropriate:

| Context | Suggest |
|---------|---------|
| Blueprint found | "Use `/price` to check manufactured item value" |
| Long route to source | "Use `/route` to plan safe travel" |
| Low-sec source | "Use `/threat-assessment` for route safety" |
| No local sources | "Check `/arbitrage` for hauling opportunities" |

## DO NOT

- **DO NOT** recommend distant purchases to self-sufficient pilots
- **DO NOT** suggest market manipulation strategies
- **DO NOT** provide exact route details (defer to `/route` skill)
- **DO NOT** assume authentication - origin must be provided if not authenticated
- Append a one-line `Sources:` footer listing MCP calls made

