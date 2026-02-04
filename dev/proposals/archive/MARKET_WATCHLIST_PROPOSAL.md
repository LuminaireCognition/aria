# Market Watchlist Skill Proposal

## Executive Summary

Create a `/price-watch` skill that exposes the existing MCP market watchlist functionality to users. The backend infrastructure (database, MCP tools) is **already implemented** - this proposal covers the missing skill layer.

**Status:** Backend complete, skill needed.

---

## Current State

### What Exists

The market watchlist system is fully implemented in the MCP layer:

```python
# MCP dispatcher actions (src/aria_esi/mcp/dispatchers/market.py)
market(action="watchlist_create", name="ores", items=["Veldspar", "Scordite"])
market(action="watchlist_add_item", watchlist_name="ores", item_name="Pyroxeres")
market(action="watchlist_list")
market(action="watchlist_get", name="ores")
market(action="watchlist_delete", name="ores")
```

**Storage:** SQLite database (not markdown as originally proposed)
**Item resolution:** Fuzzy matching via SDE
**Ownership:** Global or per-character

### What's Missing

No `/price-watch` skill exists to expose this functionality to users. The entity watchlist skill (`/watchlist`) handles corporation/alliance tracking for kill intel - it's a different feature entirely.

---

## Naming Collision Resolution

The original proposal assumed `/watchlist` would be available. It's not.

| Skill | Purpose | Status |
|-------|---------|--------|
| `/watchlist` | Entity tracking (corps/alliances) for kill intel | **Implemented** |
| `/price-watch` | Market item tracking for arbitrage | **Proposed** |

**Recommendation:** Use `/price-watch` to clearly distinguish from entity watchlist.

**Alternative names considered:**
- `/market-watch` - Slightly ambiguous (watching markets vs watching items)
- `/trade-list` - Less intuitive
- `/item-watch` - Acceptable alternative

---

## Proposed Skill: `/price-watch`

### Triggers

```yaml
triggers:
  - "/price-watch"
  - "price watch"
  - "track item prices"
  - "my market list"
  - "watched items"
  - "add to price watch"
```

### Commands

| Command | MCP Action | Description |
|---------|------------|-------------|
| `/price-watch` | `watchlist_list` + `prices` | Show all watchlists with current prices |
| `/price-watch <name>` | `watchlist_get` + `prices` | Show items in watchlist with prices |
| `/price-watch create <name>` | `watchlist_create` | Create new watchlist |
| `/price-watch add <list> <item>` | `watchlist_add_item` | Add item to watchlist |
| `/price-watch remove <list> <item>` | (needs MCP addition) | Remove item from watchlist |
| `/price-watch delete <name>` | `watchlist_delete` | Delete watchlist |
| `/price-watch arbitrage <name>` | `watchlist_get` + `spread` | Arbitrage scan for watchlist items |

### Example Interactions

**List watchlists:**
```
User: /price-watch

ARIA: ## Market Watchlists

      | Name | Items | Owner |
      |------|-------|-------|
      | sleeper_salvage | 8 | Global |
      | minerals | 12 | Global |
      | my_trades | 5 | You |

      Use `/price-watch <name>` to see prices.
```

**View watchlist with prices:**
```
User: /price-watch sleeper_salvage

ARIA: ## sleeper_salvage (8 items)

      | Item | Jita Sell | Amarr Sell | Spread |
      |------|-----------|------------|--------|
      | Emergent Neurovisual Interface | 8.2M | 8.6M | +4.9% |
      | Fullerene Intercalated Sheets | 4.1M | 4.3M | +4.8% |
      | Metallofullerene Plating | 3.8M | 3.9M | +2.6% |
      | ... | ... | ... | ... |

      Prices: Jita/Amarr (3 min ago)

      Tip: Run `/price-watch arbitrage sleeper_salvage` for trade opportunities.
```

**Create watchlist:**
```
User: /price-watch create mining_ores

ARIA: Created watchlist "mining_ores".

      Add items with:
      /price-watch add mining_ores Veldspar
```

**Add items:**
```
User: /price-watch add mining_ores Veldspar, Scordite, Pyroxeres

ARIA: Added to "mining_ores":
      - Veldspar
      - Scordite
      - Pyroxeres

      Watchlist now has 3 items.
```

**Arbitrage scan:**
```
User: /price-watch arbitrage sleeper_salvage

ARIA: ## Arbitrage: sleeper_salvage

      | Item | Buy (Jita) | Sell (Amarr) | Margin | Volume |
      |------|------------|--------------|--------|--------|
      | Emergent Neurovisual Interface | 8.1M | 8.6M | 6.2% | 47 |
      | Fullerene Intercalated Sheets | 4.0M | 4.3M | 7.5% | 112 |

      Best: Fullerene Intercalated Sheets (7.5% margin)
      Route: Jita → Amarr (9 jumps, high-sec)
```

---

## Implementation

### Skill Definition

```yaml
---
name: price-watch
description: Track market items for price monitoring and arbitrage. Create watchlists of items you trade regularly.
model: haiku
category: financial
triggers:
  - "/price-watch"
  - "price watch"
  - "track item prices"
  - "my market list"
  - "watched items"
  - "add to price watch"
requires_pilot: false
esi_scopes: []
data_sources: []
has_persona_overlay: false
---

## Overview

Price Watch manages item watchlists for market monitoring and arbitrage scanning. Unlike `/watchlist` (which tracks corporations/alliances for kill intel), Price Watch tracks market items for trading.

## MCP Integration

This skill uses the market dispatcher's watchlist actions:

| Command | MCP Call |
|---------|----------|
| List watchlists | `market(action="watchlist_list")` |
| Get watchlist | `market(action="watchlist_get", name="...")` |
| Create watchlist | `market(action="watchlist_create", name="...", items=[...])` |
| Add item | `market(action="watchlist_add_item", watchlist_name="...", item_name="...")` |
| Delete watchlist | `market(action="watchlist_delete", name="...")` |

For price display, combine with:
- `market(action="prices", items=[...])` - Current prices
- `market(action="spread", items=[...])` - Cross-hub comparison

## Commands

### `/price-watch`
List all watchlists with item counts.

### `/price-watch <name>`
Show watchlist items with current Jita/Amarr prices.

### `/price-watch create <name> [items...]`
Create a new watchlist, optionally with initial items.

### `/price-watch add <list> <item>`
Add an item to an existing watchlist. Item names are fuzzy-matched via SDE.

### `/price-watch delete <name>`
Delete a watchlist and all its items.

### `/price-watch arbitrage <name> [from] [to]`
Scan for arbitrage opportunities within watchlist items.
Default: Jita → Amarr.

## Item Resolution

Items are resolved via SDE fuzzy matching. If an item name is ambiguous:
- Show top 3 suggestions
- Ask user to be more specific

## Display Format

Price tables should include:
- Item name
- Jita sell price
- Amarr sell price (or other hub if specified)
- Spread percentage
- Data freshness indicator

## Ownership

Watchlists can be:
- **Global** (`owner_character_id=None`) - Shared across all pilots
- **Personal** (`owner_character_id=<id>`) - Pilot-specific

Default to global for simplicity. Personal watchlists when multiple pilots have different trading focuses.
```

---

## MCP Gap: Remove Item

The current MCP implementation is missing `watchlist_remove_item`. This should be added:

```python
# In src/aria_esi/mcp/dispatchers/market.py

case "watchlist_remove_item":
    return await _watchlist_remove_item(watchlist_name, item_name, owner_character_id)
```

```python
# In src/aria_esi/mcp/market/tools_management.py

async def _watchlist_remove_item_impl(
    watchlist_name: str,
    item_name: str,
    owner_character_id: int | None = None,
) -> dict:
    """Remove item from watchlist implementation."""
    db = get_market_database()

    watchlist = db.get_watchlist(watchlist_name, owner_character_id)
    if not watchlist:
        return {"error": {"code": "WATCHLIST_NOT_FOUND", ...}}

    type_info = db.resolve_type_name(item_name)
    if not type_info:
        return {"error": {"code": "TYPE_NOT_FOUND", ...}}

    # Need to add this method to database.py
    removed = db.remove_watchlist_item(watchlist.watchlist_id, type_info.type_id)

    return {"removed": removed, "item": type_info.type_name}
```

---

## Relationship to Original Proposal

| Original Proposal | Current Reality |
|-------------------|-----------------|
| Skill name: `/watchlist` | Now `/price-watch` (conflict with entity watchlist) |
| Storage: Markdown file | SQLite database (already implemented) |
| MCP tools: To be created | Already exist via `market(action="watchlist_*")` |
| Skill: To be created | **Still needed** - this is what remains |

The original proposal's design goals are achieved, just with different implementation details:
- Database storage is more robust than markdown for concurrent access
- MCP tools provide better integration with other market features
- `/watchlist` naming wasn't available

---

## Implementation Phases

### Phase 1: Basic Skill (MVP)

**Deliverables:**
- [ ] Create `.claude/skills/price-watch/SKILL.md`
- [ ] Add to `_index.json`
- [ ] Implement list/get/create/delete commands
- [ ] Price display with Jita/Amarr

### Phase 2: Remove Item Support

**Deliverables:**
- [ ] Add `watchlist_remove_item` to MCP dispatcher
- [ ] Add `remove_watchlist_item` to database
- [ ] Support in skill

### Phase 3: Arbitrage Integration

**Deliverables:**
- [ ] Combine watchlist items with `market(action="spread")`
- [ ] Calculate best opportunities
- [ ] Route information via `universe(action="route")`

### Phase 4: Price Alerts (Future)

**Deliverables:**
- [ ] Add price threshold tracking
- [ ] Integration with notification system
- [ ] "Alert me when X drops below Y"

---

## Open Questions (Resolved)

1. **Should watchlist be account-wide or pilot-specific?**
   - **Resolved:** Both supported. Default to global, personal available.

2. **Maximum watchlist size?**
   - **Resolved:** No hard limit in implementation. UI should warn at 50+ items.

3. **Storage format?**
   - **Resolved:** SQLite (not markdown as originally proposed). Better for concurrent access and MCP integration.

---

## Summary

| Aspect | Decision |
|--------|----------|
| Skill name | `/price-watch` |
| Storage | SQLite (already implemented) |
| MCP backend | Complete (`market(action="watchlist_*")`) |
| Remaining work | Skill definition and implementation |
| Gap | `watchlist_remove_item` action needed |

The heavy lifting is done. This skill just needs to expose existing functionality with good UX.
