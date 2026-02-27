---
name: assets
description: Asset inventory with valuation. View assets across stations with market value calculations.
model: haiku
category: financial
triggers:
  - "/assets"
  - "my assets"
  - "asset value"
  - "what do I own"
  - "inventory value"
  - "total net worth"
requires_pilot: true
esi_scopes:
  - esi-assets.read_assets.v1
---

# ARIA Asset Audit Module

## Command Syntax

```
/assets                         # Overview of all assets
/assets --ships                 # Show assembled ships only
/assets --type <name>           # Filter by item type
/assets --location <name>       # Filter by location
/assets --value                 # Include market valuations
/assets --location Jita --value # Location + value combined
/assets --snapshot              # Save current state for trend tracking
/assets --trends                # Show 7-day value changes
/assets --history               # List all available snapshots
```

## CLI Commands

```bash
# Basic asset listing
uv run aria-esi assets

# Ships only
uv run aria-esi assets --ships

# Filter by type
uv run aria-esi assets --type "Hammerhead"

# Filter by location
uv run aria-esi assets --location "Jita"

# With valuation
uv run aria-esi assets --value

# Save snapshot (requires --value to calculate totals)
uv run aria-esi assets --value --snapshot

# View trends over past week
uv run aria-esi assets --trends

# List all snapshots
uv run aria-esi assets --history
```

## Required Tool Calls (MANDATORY)

The following calls MUST be made before presenting any asset data. If a call fails or is unavailable, report the error — do NOT fabricate output.

| Step | Call | Required For |
|------|------|-------------|
| 1 | `uv run aria-esi assets` (or `assets --value`, `--ships`, etc.) | All asset data: items, locations, counts, ships |
| 2 | `market(action="valuation", items=[...])` | Price valuations (only after step 1 returns actual items) |

**If step 1 is not called or returns an error, do NOT present any asset inventory, ship list, or item counts. Present only the error state or ESI unavailability message.**

> **HALLUCINATION GUARD:** Every item, location, quantity, ship name, and price in the response MUST come from a tool call made in this session. If ESI was not queried, you have ZERO asset data. NEVER fill in plausible-looking inventories from training data.

### Field → Source Mapping

Every field in the response must trace to a specific source. If the source was not queried, the field must show `[no data]` or be omitted.

| Output Field | Required Source | Tool Call |
|-------------|----------------|-----------|
| Item names, quantities | ESI assets endpoint | `uv run aria-esi assets` |
| Item locations (station names) | ESI assets endpoint | `uv run aria-esi assets` |
| Ship names, assembled status | ESI assets endpoint | `uv run aria-esi assets --ships` |
| Ship slot counts (H/M/L) | SDE item data | `sde(action="item_info", item="...")` |
| Unit prices, total values | Market dispatcher | `market(action="valuation", items=[...])` |
| Item count per location | Derived from ESI response | Count from `uv run aria-esi assets` output |
| Jump distances between locations | Universe route | `universe(action="route", ...)` |
| Wallet balance | ESI wallet endpoint | **Separate data — DO NOT include in asset total** |

## Response Format

Present asset data using this structural template. All values MUST come from tool calls — use `{placeholder}` notation below to indicate where real data goes:

```markdown
## Asset Inventory
*Query: {timestamp}*

**Total Unique Items:** {count}
**Locations:** {station_count} stations

### Top Locations by Item Count
| Location | Items | Ships |
|----------|-------|-------|
| {location} | {count} | {ships} |

### Assembled Ships
| Ship | Location |
|------|----------|
| {ship_name} | {location} |
```

For valuations, add price columns sourced from `market(action="valuation")`.

## Valuation Flow

1. Group ESI assets by type_id
2. Build valuation request with item names and quantities
3. Call `market(action="valuation", items=[...], price_type="sell", region="jita")`

## Structure/Citadel Handling

Assets in player structures show as "Structure (ID)" because structure names require authenticated ESI calls and name resolution is expensive.

## Trend Tracking

Snapshots allow tracking portfolio value over time:

- **Save:** `/assets --value --snapshot` — saves current state
- **Trends:** `/assets --trends` — shows 7-day value changes with current vs previous value, change amount/percent
- **History:** `/assets --history` — lists all available snapshots with dates and values

Snapshots are stored in `userdata/pilots/{pilot_id}/assets/snapshots/` and include total portfolio value, value by category, top 20 items by value, and timestamp.

## Smart Insights

With `--insights`, run `uv run aria-esi assets --insights` and present results. Detects:
- **Forgotten assets**: locations with <5M ISK total value outside trade hubs
- **Duplicate ships**: same ship type at same or multiple locations
- **Consolidation opportunities**: compares distance to home systems vs nearest trade hub

## Integration with Other Skills

| Context | Suggest |
|---------|---------|
| Ship fitting | "For fitting export, try `/fitting <ship_name>`" |
| Item pricing | "For market depth, try `/price <item> --jita`" |
| Selling items | "Check orders with `/orders`" |
| Industry | "For blueprint status, check `/corp blueprints`" |
| Value tracking | "Save snapshots with `--snapshot` to track over time" |

## Anti-Patterns

- **WRONG:** Present inventories without calling `uv run aria-esi assets`
- **RIGHT:** Call `uv run aria-esi assets --value` first, present only what ESI returns

- **WRONG:** Show ship slot counts from memory
- **RIGHT:** Call `sde(action="item_info", item="...")` to get verified slot layout

- **WRONG:** Claim jump distances without route query
- **RIGHT:** Call `universe(action="route")` for actual jump distances

- **WRONG:** Include wallet balance in "Total Net Worth" alongside asset value
- **RIGHT:** Wallet and assets are separate data

## DO NOT

- **DO NOT** include items in asset safety without noting the 5-day delay
- **DO NOT** present valuation as exact (market prices fluctuate)
- **DO NOT** attempt to resolve all structure names (too slow)
- **DO NOT** include wallet balance in asset total (different data)

## Notes

- Assets update when you dock/undock or log in
- Items in containers show location as parent container ID
- Packaged ships count as items, not assembled ships
- PLEX in PLEX vault is a separate ESI endpoint (not included)
- Asset safety items are in limbo for 5-20 days
- Assets in AssetSafety flag have a 5-day delivery delay — always note this
