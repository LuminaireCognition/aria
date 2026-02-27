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

## ESI Availability Check (CRITICAL)

**BEFORE making any ESI queries**, check the session hook output for ESI status:

```json
"esi": {"status": "UNAVAILABLE"}
```

### If ESI is UNAVAILABLE:

1. **DO NOT** run `uv run aria-esi` commands - they will timeout
2. **RESPOND IMMEDIATELY** with:
   ```
   Asset inventory requires live ESI data which is currently unavailable.

   Check this in-game: Alt+T (Inventory) → Personal Assets

   ESI usually recovers automatically.
   ```
3. **DO NOT** block waiting for ESI

### If ESI is AVAILABLE:

Proceed with normal asset queries.

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

> **⚠️ HALLUCINATION GUARD:** Every item, location, quantity, ship name, and price in the response MUST come from a tool call made in this session. If ESI was not queried, you have ZERO asset data. NEVER fill in plausible-looking inventories from training data.

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

## Response Patterns

### Basic Asset Overview

When asked for general assets ("/assets"):

```
## Asset Inventory

**Total Unique Items:** 847
**Locations:** 12 stations

### Top Locations by Item Count

| Location | Items | Ships |
|----------|-------|-------|
| Jita IV - Moon 4 - CNI | 312 | 3 |
| Dodixie IX - Moon 20 | 186 | 5 |
| Arnon IX - SoE Bureau | 45 | 1 |

### Assembled Ships

| Ship | Location |
|------|----------|
| Gila | Jita IV - Moon 4 - CNI |
| Vexor Navy Issue | Jita IV - Moon 4 - CNI |
| Venture | Dodixie IX - Moon 20 |
| Heron | Dodixie IX - Moon 20 |

*Use `/assets --value` for market valuations.*
```

### Asset Valuation

When asked for value ("/assets --value"):

1. Fetch assets from ESI
2. Group assets by type_id
3. Batch price lookup via `market(action="valuation", items=[...])`
4. Present totals

```
## Asset Valuation

**Valuation Date:** 2026-01-29 21:30 UTC
**Price Source:** Jita sell orders

### By Location

| Location | Est. Value |
|----------|------------|
| Jita IV - Moon 4 - CNI | 1,245,000,000 |
| Dodixie IX - Moon 20 | 342,000,000 |
| Arnon IX - SoE Bureau | 28,000,000 |

**Total Estimated Value:** 1,615,000,000 ISK

### Top Value Items

| Item | Qty | Unit Price | Total Value |
|------|-----|------------|-------------|
| Gila | 1 | 280,000,000 | 280,000,000 |
| Vexor Navy Issue | 1 | 95,000,000 | 95,000,000 |
| PLEX | 15 | 4,500,000 | 67,500,000 |
| Hammerhead II | 50 | 1,200,000 | 60,000,000 |
| Ogre II | 10 | 5,500,000 | 55,000,000 |

*Values are estimates based on current Jita sell prices.*
*Actual value may vary. Citadel contents shown as "Structure (ID)".*
```

### Ships Only

When asked for ships ("/assets --ships"):

```
## Assembled Ships

| Ship | Location | Item ID |
|------|----------|---------|
| Gila | Jita IV - Moon 4 - CNI | 1234567890 |
| Vexor Navy Issue | Jita IV - Moon 4 - CNI | 1234567891 |
| Venture | Dodixie IX - Moon 20 | 1234567892 |
| Heron | Dodixie IX - Moon 20 | 1234567893 |
| Astero | Dodixie IX - Moon 20 | 1234567894 |

**Total Ships:** 5

*Use `/fitting <ship_name>` to export a ship's fitting.*
```

### Filtered by Type

When filtering by type ("/assets --type Hammerhead"):

```
## Assets: Hammerhead

| Item | Qty | Location |
|------|-----|----------|
| Hammerhead II | 25 | Jita IV - Moon 4 - CNI |
| Hammerhead II | 15 | Dodixie IX - Moon 20 |
| Hammerhead I | 50 | Jita IV - Moon 4 - CNI |
| Hammerhead I Blueprint | 1 | Jita IV - Moon 4 - CNI |

**Total Matching:** 4 stacks (91 items)
```

### Filtered by Location

When filtering by location ("/assets --location Jita"):

```
## Assets in Jita IV - Moon 4 - CNI

**Unique Items:** 312

### Ships
- Gila
- Vexor Navy Issue
- Catalyst

### High Value Items
| Item | Qty |
|------|-----|
| PLEX | 15 |
| Skill Injector | 3 |
| Hammerhead II | 25 |

### Modules (truncated, 100+ items)
Use `--type <name>` to filter specific modules.
```

## Valuation Implementation

Use market dispatcher for batch valuation:

```python
# 1. Group assets by type_id
inventory = {}
for asset in assets:
    type_id = asset["type_id"]
    inventory[type_id] = inventory.get(type_id, 0) + asset.get("quantity", 1)

# 2. Build valuation request
items = [{"name": type_name, "quantity": qty} for type_name, qty in inventory.items()]

# 3. Call market dispatcher
market(action="valuation", items=items, price_type="sell", region="jita")
```

**Response format:**
```json
{
  "total_value": 1615000000,
  "item_values": [
    {"name": "Gila", "quantity": 1, "unit_price": 280000000, "total": 280000000},
    {"name": "PLEX", "quantity": 15, "unit_price": 4500000, "total": 67500000}
  ]
}
```

## Structure/Citadel Handling

Assets in player structures show as "Structure (ID)" because:
- Structure names require authenticated ESI call
- Many pilots have assets in hundreds of structures
- Name resolution is expensive

**Future Enhancement:** Cache resolved structure names.

## Trend Tracking

Snapshots allow tracking portfolio value over time:

### Save a Snapshot

```
/assets --value --snapshot
```

**Response:**
```
Snapshot saved: 2026-02-01.yaml
Total Value: 2,470,000,000 ISK
```

### View Trends

```
/assets --trends
```

**Response:**
```
## Asset Value Trends (7 days)

| Metric | Value |
|--------|-------|
| Current Value | 2,470,000,000 ISK |
| Previous Value (7 days ago) | 2,150,000,000 ISK |
| Change | +320,000,000 ISK (+14.9%) |
| High Water Mark | 2,520,000,000 ISK |
| Snapshots in Period | 5 |
```

### View History

```
/assets --history
```

**Response:**
```
## Asset Snapshots

| Date | Total Value |
|------|-------------|
| 2026-02-01 | 2,470,000,000 ISK |
| 2026-01-28 | 2,380,000,000 ISK |
| 2026-01-25 | 2,150,000,000 ISK |
| 2026-01-20 | 1,980,000,000 ISK |
```

### Snapshot Storage

Snapshots are stored in:
```
userdata/pilots/{pilot_id}/assets/snapshots/
  2026-02-01.yaml
  2026-01-28.yaml
  ...
```

Each snapshot includes:
- Total portfolio value
- Value by category (ships, modules, minerals, etc.)
- Top 20 items by value
- Timestamp

## Smart Insights

Use `--insights` to identify optimization opportunities in your asset portfolio.

### View Insights

```
/assets --insights
```

### CLI Command

```bash
uv run aria-esi assets --insights
```

### Response Format

```
## Asset Insights

### Summary

| Metric | Value |
|--------|-------|
| Forgotten Locations | 4 |
| Total Forgotten Value | 12.5M ISK |
| Duplicate Ship Types | 2 |

### Forgotten Assets

Locations under 5M ISK not in trade hubs:

| Location | Value | Items | Recommendation |
|----------|-------|-------|----------------|
| Arnon IX - Sisters Bureau | 2.5M | 8 | Consolidate to home |
| Hatakani III - School | 1.2M | 3 | Consolidate to hub |
| Bourynes VII - Federal Navy | 0.8M | 2 | Consolidate to hub |

### Duplicate Ships

| Ship Type | Locations | Count | Note |
|-----------|-----------|-------|------|
| Venture | Station A, Station B | 3 | Multiple locations |
| Rifter | Station A | 2 | Same location |

### Consolidation Suggestions

| Source | To Home | To Nearest Hub | Recommendation |
|--------|---------|----------------|----------------|
| Arnon (2.5M) | Dodixie: 5j | Dodixie: 5j | Consolidate home |
| Hatakani (1.2M) | Dodixie: 12j | Jita: 3j | Consolidate hub |
```

### What Insights Detects

1. **Forgotten Assets**: Locations with <5M ISK total value that aren't trade hubs
   - These are assets you may have abandoned or forgotten
   - Good candidates for consolidation or selling

2. **Duplicate Ships**: Same ship type at same or multiple locations
   - Same location duplicates may be accidental
   - Multiple location duplicates may indicate inefficient staging

3. **Consolidation Suggestions**: Where to move forgotten assets
   - Compares distance to home systems vs. nearest trade hub
   - Recommends closer destination

### Trade Hub Reference

The following stations are considered trade hubs (excluded from forgotten asset detection):
- Jita IV - Moon 4 - Caldari Navy Assembly Plant
- Amarr VIII (Oris) - Emperor Family Academy
- Dodixie IX - Moon 20 - Federation Navy Assembly Plant
- Rens VI - Moon 8 - Brutor Tribe Treasury
- Hek VIII - Moon 12 - Boundless Creation Factory

### Home System Configuration

Home systems are read from `userdata/config.json`:

```json
{
  "redisq": {
    "context_topology": {
      "geographic": {
        "systems": [
          {"name": "Dodixie", "classification": "home"},
          {"name": "Sortet", "classification": "home"}
        ]
      }
    }
  }
}
```

## Integration with Other Skills

| Context | Suggest |
|---------|---------|
| Ship fitting | "For fitting export, try `/fitting <ship_name>`" |
| Item pricing | "For market depth, try `/price <item> --jita`" |
| Selling items | "Check orders with `/orders`" |
| Industry | "For blueprint status, check `/corp blueprints`" |
| Value tracking | "Save snapshots with `--snapshot` to track over time" |

## ESI Response Structure

```json
{
  "assets": [
    {
      "item_id": 1234567890,
      "type_id": 17715,
      "location_id": 60003760,
      "location_type": "station",
      "location_flag": "Hangar",
      "quantity": 1,
      "is_singleton": true
    }
  ]
}
```

**Location Flags:**
- `Hangar` - Station hangar
- `AssetSafety` - Asset safety wrap
- `Cargo` - In a ship's cargo
- `DroneBay` - In a ship's drone bay
- Various slot names for fitted modules

## Anti-Patterns

❌ **WRONG:** Present 1,214 items across 6 locations with detailed valuations without calling `uv run aria-esi assets`
✅ **RIGHT:** Call `uv run aria-esi assets --value` first, present only what ESI returns

❌ **WRONG:** Show ship slot counts (e.g., "6H/4M/7L") from memory
✅ **RIGHT:** Call `sde(action="item_info", item="Gila")` to get verified slot layout

❌ **WRONG:** Claim "Hek is 4 jumps from Jita" in consolidation suggestions without route query
✅ **RIGHT:** Call `universe(action="route")` for actual jump distances

❌ **WRONG:** Include wallet balance (107M ISK) in "Total Net Worth" alongside asset value
✅ **RIGHT:** Wallet and assets are separate data — see DO NOT rules below

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
