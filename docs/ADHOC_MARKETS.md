# Ad-hoc Market Scopes

Extend ARIA's market analysis beyond the 5 core trade hubs by defining custom market scopes for any region, station, system, or structure.

## Overview

By default, ARIA's arbitrage scanner uses pre-aggregated data from the five major trade hubs (Jita, Amarr, Dodixie, Rens, Hek). Ad-hoc market scopes let you add custom locations to this analysis while keeping the hub-centric defaults fast and reliable.

**Key Concepts:**
- **Watchlist**: A named list of items to track (bounds ESI queries)
- **Scope**: A market location (region/station/system/structure) linked to a watchlist
- **Refresh**: Fetching current prices from ESI for a scope's watchlist items

## Quick Start

### 1. Create a Watchlist

```
# Create watchlist with initial items
market_watchlist_create("mining_ores", items=["Veldspar", "Scordite", "Pyroxeres"])

# Or create empty and add items later
market_watchlist_create("my_items")
market_watchlist_add_item("my_items", "Tritanium")
market_watchlist_add_item("my_items", "Pyerite")
```

### 2. Create a Market Scope

```
# Region scope (e.g., Everyshore)
market_scope_create("Everyshore Minerals", "region", 10000037, "mining_ores")

# Station scope (requires parent_region_id for efficiency)
market_scope_create("Oursulaert Hub", "station", 60011866, "my_items", parent_region_id=10000032)

# System scope
market_scope_create("Dodixie System", "system", 30002659, "my_items", parent_region_id=10000032)

# Structure scope (high bandwidth - use sparingly)
market_scope_create("My Fortizar", "structure", 1234567890, "my_items")
```

### 3. Refresh Scope Data

```
# Fetch current prices from ESI
market_scope_refresh("Everyshore Minerals")

# Force refresh even if cache is fresh
market_scope_refresh("Everyshore Minerals", force_refresh=True)
```

### 4. Include in Arbitrage Scan

```
# Scan hubs + custom scopes
market_arbitrage_scan(include_custom_scopes=True)

# Scan specific scopes only
market_arbitrage_scan(include_custom_scopes=True, scopes=["Everyshore Minerals"])
```

## Scope Types

| Type | Location ID | ESI Behavior | Cost |
|------|-------------|--------------|------|
| `region` | Region ID | Fetches per type_id from watchlist | Low |
| `station` | Station ID | Fetches region, filters by station | Low |
| `system` | System ID | Fetches region, filters by system | Low |
| `structure` | Structure ID | Fetches ALL orders, filters locally | **High** |

### Structure Scope Warning

Structure scopes cannot filter by item type at the ESI level. All orders are fetched (paginated) then filtered locally against your watchlist. Large structures may have 50+ pages of orders.

**Guardrails:**
- Default page limit: 5 pages
- Increase with `max_structure_pages` parameter
- Orders beyond the limit are marked as `truncated`

```
# Fetch more pages for large structures
market_scope_refresh("My Fortizar", max_structure_pages=20)
```

## MCP Tools Reference

### Watchlist Management

| Tool | Description |
|------|-------------|
| `market_watchlist_create` | Create a new watchlist |
| `market_watchlist_add_item` | Add item by name (SDE-resolved) |
| `market_watchlist_list` | List watchlists (supports owner filtering) |
| `market_watchlist_get` | Get watchlist details with all items |
| `market_watchlist_delete` | Delete watchlist (cascades to scopes) |

### Scope Management

| Tool | Description |
|------|-------------|
| `market_scope_create` | Create ad-hoc scope linked to watchlist |
| `market_scope_list` | List scopes (core hubs + ad-hoc) |
| `market_scope_delete` | Delete ad-hoc scope (core hubs protected) |
| `market_scope_refresh` | Fetch prices from ESI for scope |

### Arbitrage Integration

| Parameter | Description |
|-----------|-------------|
| `include_custom_scopes` | Enable ad-hoc scope data in scan (default: False) |
| `scopes` | List of specific scope names to include |
| `scope_owner_id` | Character ID for scope ownership resolution |

## Ownership Model

Scopes and watchlists support optional ownership:

- **Global** (`owner_character_id=None`): Available to all sessions
- **Character-owned**: Scoped to a specific character ID

**Precedence:** When a scope name exists in both global and character lists, the character-owned scope takes precedence (shadows global).

```
# Global watchlist
market_watchlist_create("common_items")

# Character-specific watchlist
market_watchlist_create("my_secret_list", owner_character_id=12345)

# List all (global + character)
market_watchlist_list(owner_character_id=12345)

# List global only
market_watchlist_list(owner_character_id=12345, include_global=False)
```

## Data Quality Labels

Ad-hoc scope results include provenance metadata:

| Field | Description |
|-------|-------------|
| `buy_scope_name` / `sell_scope_name` | Source scope for each side |
| `source_type` | `fuzzwork` (core hubs) or `esi` (ad-hoc) |
| `data_age` | Age of CCP data (from ESI headers) |
| `last_checked` | Time since last fetch attempt |
| `is_truncated` | True if data may be incomplete |

### Fetch Status

| Status | Meaning |
|--------|---------|
| `complete` | All data fetched successfully |
| `truncated` | Hit page limit (structure scopes) |
| `skipped_truncation` | Item in watchlist but not found due to truncation |

## Freshness Thresholds

| Scope Type | Fresh | Recent | Stale |
|------------|-------|--------|-------|
| Core Hubs | < 5 min | < 30 min | > 30 min |
| Ad-hoc | < 10 min | < 1 hour | > 1 hour |

Ad-hoc scopes have more lenient thresholds since ESI data updates less frequently than Fuzzwork aggregates.

## Common Patterns

### Mining Route Analysis

Track ore prices across high-sec border systems:

```
# Create ore watchlist
market_watchlist_create("ores", items=[
    "Veldspar", "Scordite", "Pyroxeres", "Plagioclase",
    "Omber", "Kernite", "Jaspet", "Hemorphite"
])

# Create scope for border region
market_scope_create("Placid Ores", "region", 10000048, "ores")

# Refresh and scan
market_scope_refresh("Placid Ores")
market_arbitrage_scan(include_custom_scopes=True, scopes=["Placid Ores"])
```

### Station Trading at a Specific Hub

Monitor a non-major station:

```
market_watchlist_create("station_items", items=["PLEX", "Skill Injector"])
market_scope_create("Hek Station", "station", 60005686, "station_items", parent_region_id=10000042)
market_scope_refresh("Hek Station")
```

### Structure Market Monitoring

Track items at a player structure:

```
market_watchlist_create("structure_watch", items=["Tritanium", "Pyerite", "Mexallon"])
market_scope_create("Corp Fortizar", "structure", 1035466617946, "structure_watch")
market_scope_refresh("Corp Fortizar", max_structure_pages=10)
```

## Limitations

1. **Watchlist required**: All ad-hoc scopes must have a watchlist to bound ESI queries
2. **No full-region scans**: Unbounded "scan everything" is disabled by design
3. **Structure bandwidth**: Structure scopes fetch all orders regardless of watchlist
4. **Core hubs protected**: Cannot delete the 5 default trade hub scopes
5. **ESI rate limits**: Shared fetcher respects global rate limits

## Troubleshooting

### "Scope not found"
- Check scope name spelling
- Verify `owner_character_id` if scope is character-owned
- Use `market_scope_list()` to see available scopes

### "Watchlist not found"
- Check watchlist name spelling
- Verify ownership matches scope ownership

### Truncated results
- Increase `max_structure_pages` for structure scopes
- Check `fetch_status` field in results

### Stale data warnings
- Run `market_scope_refresh()` to update
- Use `force_refresh=True` to bypass cache
