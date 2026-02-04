# Asset Audit & Net Worth Proposal

**Status:** ✅ COMPLETE (2026-02-02)
**Completed:** All 4 phases

> **Validation (2026-02-02):** Phase 4 (smart insights) is COMPLETE:
> - `--insights` flag implemented in `commands/assets.py` (lines 376-549)
> - `asset_insights.py` service with `identify_forgotten_assets()`, `suggest_consolidations()`, `find_duplicate_ships()`
> - Insights now persist to snapshots via `--insights --snapshot` combination
> - `save_snapshot()` extended to accept `insights` parameter
> - Location values properly wired from insights analysis to snapshot storage
>
> **Validation (2026-02-02):** Phase 3 (trend tracking/snapshots) is COMPLETE:
> - `AssetSnapshotService` implemented in `src/aria_esi/services/asset_snapshots.py` (279 lines)
> - Methods: `save_snapshot()`, `load_snapshot()`, `list_snapshots()`, `calculate_trends()`, `get_high_water_mark()`
> - CLI options `--snapshot`, `--trends`, `--history` functional in `commands/assets.py`
> - Snapshots stored as YAML in `userdata/pilots/{pilot}/assets/snapshots/YYYY-MM-DD.yaml`
> - Test coverage: 15 test methods in `tests/services/test_asset_snapshots.py`
> - Minor gaps: `by_location` always empty (would need aggregation refactor), category tagging uses string matching

---

## Executive Summary

Add an `/assets` skill that provides inventory tracking and net worth calculation across all character locations. This answers the universal question "what's my total wealth?" using existing ESI endpoints and market valuation tools.

**Primary value:** Unified view of character wealth without external tools.

---

## Problem Statement

EVE players accumulate assets across dozens of stations over months/years of play:

1. **No in-game net worth** - Assets window shows items, not values
2. **Scattered inventory** - Items spread across mission hubs, trade hubs, staging systems
3. **Forgotten caches** - Valuable items left in random stations
4. **No trend tracking** - "Am I actually getting richer?"

Third-party tools (jEveAssets, EVE Mogul) solve this but require setup and aren't conversational.

---

## ESI Foundation

### Required Scope

```
esi-assets.read_assets.v1
```

Already commonly authorized. Returns all character assets with:
- `type_id` - Item type
- `quantity` - Stack size
- `location_id` - Station/structure ID
- `location_flag` - Hangar, cargo, etc.
- `is_singleton` - Assembled ship vs. packaged

### Data Volume

Typical character: 500-5000 asset entries
Heavy industrialist: 10,000+ entries

Processing is feasible client-side with caching.

---

## Proposed Skill: `/assets`

### Triggers

```yaml
triggers:
  - "/assets"
  - "my assets"
  - "net worth"
  - "what's my total wealth"
  - "where are my things"
  - "asset audit"
  - "inventory value"
  - "what do I own"
```

### Commands

| Command | Description |
|---------|-------------|
| `/assets` | Net worth summary with top locations |
| `/assets breakdown` | Value by category (ships, modules, materials) |
| `/assets location <system>` | Detailed inventory at specific location |
| `/assets search <item>` | Find specific items across all locations |
| `/assets ships` | Ship inventory with hull values |
| `/assets valuable` | Top 20 most valuable individual items |

### Example Interactions

**Net worth summary:**
```
User: /assets

ARIA: ## Asset Summary

      Total Net Worth: 2.47B ISK

      ### Top Locations
      | Location | Value | Items |
      |----------|-------|-------|
      | Jita IV - Moon 4 | 892M | 127 |
      | Dodixie IX - Moon 20 | 445M | 89 |
      | Hek VIII - Moon 12 | 312M | 56 |
      | Sortet V - Moon 1 | 198M | 234 |
      | (12 other locations) | 623M | 445 |

      ### By Category
      | Category | Value | % |
      |----------|-------|---|
      | Ships | 1.12B | 45% |
      | Modules | 534M | 22% |
      | Minerals/Materials | 412M | 17% |
      | Blueprints | 245M | 10% |
      | Other | 159M | 6% |

      Prices: Jita sell (5 min ago)
```

**Ship inventory:**
```
User: /assets ships

ARIA: ## Ship Inventory

      | Ship | Location | Fitted | Value |
      |------|----------|--------|-------|
      | Vexor Navy Issue | Sortet V | Yes | 127M |
      | Vexor Navy Issue | Dodixie | No | 98M |
      | Stratios | Jita | Yes | 312M |
      | Venture | Sortet V | Yes | 1.2M |
      | Venture | Sortet V | Yes | 1.2M |
      | Epithal | Dodixie | No | 890K |

      Total: 6 ships, 540M ISK

      Note: Fitted values include modules based on standard fits.
      Actual module values require individual inspection.
```

**Find specific items:**
```
User: /assets search "Drone Damage Amplifier"

ARIA: ## Search: Drone Damage Amplifier

      | Item | Quantity | Location | Value |
      |------|----------|----------|-------|
      | Drone Damage Amplifier II | 4 | Jita IV | 3.2M |
      | Drone Damage Amplifier II | 2 | Sortet V (fitted) | 1.6M |
      | Drone Damage Amplifier I | 8 | Dodixie IX | 240K |

      Total: 14 units, 5.04M ISK
```

**Forgotten assets:**
```
User: Where are my things?

ARIA: ## Asset Distribution

      You have items in 15 locations across 4 regions.

      ### Potentially Forgotten
      These locations have < 5M ISK and haven't been visited recently:

      | Location | Value | Last Docked* |
      |----------|-------|--------------|
      | Stacmon V - Moon 9 | 2.3M | Unknown |
      | Arnon IX - Moon 3 | 890K | Unknown |

      *Last docked time requires location history (not available via ESI)

      Suggestion: Consider consolidating to reduce asset sprawl.
```

---

## Implementation

### Phase 1: Basic Asset Query

**Deliverables:**
- [ ] Create `/assets` skill definition
- [ ] ESI asset fetching via `aria-esi assets`
- [ ] Location ID → station name resolution
- [ ] Basic value calculation using `market(action="prices")`

**CLI command:**
```bash
uv run aria-esi assets [--format json|table] [--location <system>]
```

**Caching strategy:**
- Cache asset list for 30 minutes (ESI cache timer)
- Cache price data for 5 minutes (market volatility)
- Store last snapshot for trend comparison

### Phase 2: Categorization and Search

**Deliverables:**
- [ ] Item categorization by market group
- [ ] Search functionality across all assets
- [ ] Ship vs. module vs. material breakdown

**Category mapping:**
```python
CATEGORY_GROUPS = {
    "ships": [25],  # Ship market group
    "modules": [9, 10, 11, ...],  # Module groups
    "drones": [157],
    "ammunition": [83],
    "minerals": [54],
    "planetary": [1334],
    "blueprints": [2],  # Special handling - BPO vs BPC
    # ...
}
```

### Phase 3: Trend Tracking

**Deliverables:**
- [ ] Snapshot storage in pilot data directory
- [ ] Week-over-week comparison
- [ ] "Richest I've been" milestone tracking

**Snapshot format:**
```yaml
# userdata/pilots/{active_pilot}/assets/snapshots/2026-01-29.yaml
timestamp: 2026-01-29T10:30:00Z
total_value: 2470000000
by_category:
  ships: 1120000000
  modules: 534000000
  # ...
by_location:
  60003760: 892000000  # Jita
  60011866: 445000000  # Dodixie
  # ...
top_items:
  - type_id: 33697
    name: "Stratios"
    value: 312000000
  # ...
```

### Phase 4: Smart Insights

**Deliverables:**
- [ ] "Forgotten assets" detection (low value, distant locations)
- [ ] Consolidation suggestions
- [ ] Duplicate detection ("You have 4 Ventures")
- [ ] Price change alerts on high-value items

---

## Skill Definition

```yaml
---
name: assets
description: Asset inventory and net worth tracking. View total wealth, find items across locations, and track asset value over time.
model: haiku
category: financial
triggers:
  - "/assets"
  - "my assets"
  - "net worth"
  - "what's my total wealth"
  - "where are my things"
  - "asset audit"
  - "inventory value"
  - "what do I own"
requires_pilot: true
esi_scopes:
  - esi-assets.read_assets.v1
data_sources:
  - userdata/pilots/{active_pilot}/assets/snapshots/
has_persona_overlay: false
---
```

---

## Technical Considerations

### Performance

Asset queries can be large. Mitigation:
1. **Pagination** - ESI returns paginated results, process incrementally
2. **Price batching** - Query prices in chunks of 100 items
3. **Caching** - Store results, don't re-query on every command

### Fitted Ships

ESI returns assembled ships as single items. Getting fitted module values requires:
- Fetching ship fitting via separate endpoint (if docked)
- OR using standard fit estimates (less accurate)

Recommendation: Phase 1 uses hull value only, note limitation.

### Blueprints

Blueprint value is complex:
- BPOs have base value + research value (ME/TE)
- BPCs have no direct market value (contract-based)

Recommendation: Use base BPO value, flag BPCs as "value varies."

### Structure Access

Player structures require `esi-universe.read_structures.v1` to resolve names. If unavailable, show structure ID with "Private Structure" label.

---

## Privacy Considerations

Asset data is sensitive. Guidelines:
1. Never log full asset lists
2. Snapshots stored locally only (pilot data directory)
3. Summary data only in responses (not item-by-item dumps)
4. Clear cache on pilot switch

---

## Integration Points

### With Market Tools

```python
# Get prices for all unique type_ids in assets
type_ids = list(set(asset["type_id"] for asset in assets))
prices = market(action="prices", items=type_ids)
```

### With Universe Tools

```python
# Resolve station names
station_names = universe(action="systems", systems=[...])
```

### With Profile

- Use home system for "distance from home" sorting
- Check trade hub preferences for price sourcing

---

## Open Questions

1. **Include corporation assets?**
   - Requires additional scope and role checks
   - Recommendation: Character-only for MVP, corp assets as separate skill

2. **Include market orders?**
   - Active sell orders are "assets" in a sense
   - Recommendation: Mention total escrow, don't double-count

3. **Include contracts?**
   - Items in contracts are in-transit
   - Recommendation: Note separately, don't include in main total

4. **Valuation methodology?**
   - Jita sell (conservative) vs. buy (liquidation) vs. average
   - Recommendation: Default to Jita sell, configurable

---

## Example CLI Integration

```bash
# Quick net worth check
uv run aria-esi assets --summary

# Full asset dump
uv run aria-esi assets --format json > assets.json

# Specific location
uv run aria-esi assets --location "Jita"

# Search
uv run aria-esi assets --search "Drone Damage"
```

---

## Summary

| Aspect | Decision |
|--------|----------|
| Skill name | `/assets` |
| Required scope | `esi-assets.read_assets.v1` |
| Price source | Jita sell via market MCP |
| Caching | 30 min assets, 5 min prices |
| Trend tracking | Daily snapshots in pilot data |
| MVP features | Net worth, location breakdown, search |
| Deferred | Fitted module values, corp assets, contracts |

This addresses a universal player need with existing ESI and market infrastructure.
