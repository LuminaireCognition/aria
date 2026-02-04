# Proposal: Proximity-Based Market Search

**Status:** Draft (Reviewed)
**Author:** ARIA Development
**Date:** 2026-01-19
**Reviewed:** 2026-01-19
**Supersedes:** BLUEPRINT_SEARCH_PROPOSAL.md
**Issue:** No way to find market items near a location without knowing which region to search

## Review Summary

This proposal has been reviewed for viability, risks, and implementation concerns. Key findings:

| Aspect | Assessment |
|--------|------------|
| Problem validity | ✅ Real gap, well-documented |
| Solution design | ✅ Follows existing patterns |
| Implementation feasibility | ✅ Builds on available infrastructure |
| Risks | ⚠️ Station names, category detection, rate limits |
| Recommendation | **Proceed with Phase 1** |

See [Engineering Notes](#engineering-notes) section for detailed findings.

---

## Problem Statement

Users frequently need to find items near their current location rather than at distant trade hubs. Current market tools only query specific regions (defaulting to Jita), leaving users unable to answer questions like:

- "Where can I buy EM Armor Hardener I Blueprint near Sortet?"
- "Find the nearest Damage Control II"
- "Where's Thermodynamics skillbook sold near Hek?"
- "I need Void M ammo - what's closest?"

### Current Limitations

1. **Trade hub bias**: `market_prices` and `market_orders` default to Jita, ignoring local options
2. **No proximity awareness**: No tool considers distance from the user's location
3. **Broken NPC discovery**: `market_npc_sources` depends on `FACTION_REGIONS` which maps only 11 corporations—empire school corps (which seed most T1 blueprints) are not mapped
4. **Manual region guessing**: Users must know which region to search

### Real-World Failure

Query: "Where can I find EM Armor Hardener I Blueprint near Sortet?"

Current behavior: Reports "not NPC-seeded" despite being available 5 jumps away in Diaderi.

**Root cause:** The EM Armor Hardener I Blueprint is seeded by empire school corps, not ORE or other factions in `FACTION_REGIONS`. The current tool cannot discover items seeded by unmapped corporations.

## Use Cases

| Category | Example Query | Expected Behavior |
|----------|---------------|-------------------|
| **Blueprints** | "EM Armor Hardener I Blueprint near Sortet" | Find NPC source in Diaderi (5j) |
| **Skillbooks** | "Thermodynamics near Hek" | Find nearest school station |
| **Modules** | "Damage Control II near Amarr" | Find cheapest nearby seller |
| **Ammo** | "Void M near my location" | List sources by distance |
| **Faction gear** | "Shadow Serpentis Gyro near Dodixie" | Search player markets in region |
| **Implants** | "+4 Willpower implant near Jita" | Find LP store or player orders |
| **Ships** | "Venture near Hek" | Find hull sellers nearby |
| **Restocking** | "Nanite Repair Paste within 10 jumps" | Urgent resupply query |

## Background

### NPC vs Player Orders

| Characteristic | NPC Orders | Player Orders |
|----------------|------------|---------------|
| Duration | 364+ days (typically 365) | Max 90 days |
| Price | Fixed (often higher) | Market-driven |
| Availability | Always in stock | Can sell out |
| Location | Specific stations | Trade hubs + scattered |

The 364-day duration is a reliable heuristic for identifying NPC-seeded orders via ESI. This is the key insight that makes this proposal viable without requiring complete NPC seeding metadata.

### Items Commonly NPC-Seeded

| Category | Examples | Typical Locations |
|----------|----------|-------------------|
| T1 Blueprints | Module, ship, ammo BPOs | Empire schoolcorps |
| Skillbooks | All skills | School stations, career agents |
| Faction BPOs | Venture, Astero, Nestor | ORE (Outer Ring), SOE (Syndicate) |
| Basic implants | Attribute enhancers | Medical stations |
| Trade goods | Tourists, Janitors | Specific stations |

## Proposed Solution

### New MCP Tool: `market_find_nearby`

```python
@server.tool()
async def market_find_nearby(
    item: str,
    origin: str,
    max_jumps: int = 20,
    order_type: Literal["all", "sell", "buy"] = "sell",
    source_filter: Literal["all", "npc", "player"] = "all",
    expand_regions: bool = True,
    max_regions: int = 5,
    limit: int = 10
) -> MarketFindNearbyResult:
    """
    Find market sources for an item near a location.

    Searches the origin system's region and optionally neighboring regions,
    returning results sorted by distance with smart defaults based on item type.

    Args:
        item: Item name (case-insensitive, fuzzy matched)
        origin: Starting system for distance calculation
        max_jumps: Maximum distance to include (default: 20)
        order_type: "sell" (buying from), "buy" (selling to), or "all"
        source_filter: "all", "npc" (364+ day orders), or "player" (<364 day)
        expand_regions: Search neighboring regions if local results sparse
        max_regions: Maximum regions to search (default: 5)
        limit: Maximum results to return (default: 10)

    Returns:
        Sources sorted by distance, with prices and station details
    """
```

### Smart Defaults by Item Category

Rather than requiring users to specify `source_filter`, detect item category and suggest appropriate behavior:

```python
def suggest_source_filter(type_id: int, category_id: int, group_id: int) -> str:
    """
    Suggest source_filter based on item classification.

    Note: Uses SDE category/group IDs from src/aria_esi/models/sde.py constants.
    """
    # Blueprints: Prefer NPC (most T1 BPOs are seeded)
    # CATEGORY_BLUEPRINT = 9
    if category_id == 9:
        return "npc"

    # Skillbooks: Always NPC
    # CATEGORY_SKILL = 16 (skills are a category, not a group)
    if category_id == 16:
        return "npc"

    # Implants: Often NPC but also player-traded
    # CATEGORY_IMPLANT = 20
    if category_id == 20:
        return "all"  # Show both, note which are NPC

    # Everything else: All sources
    return "all"
```

The tool applies this as a suggestion but respects explicit user preference.

**Implementation Note:** Verify category IDs against the SDE during implementation. The constants in `src/aria_esi/models/sde.py` define:
- `CATEGORY_BLUEPRINT = 9`
- `CATEGORY_SKILL = 16`

### Response Model

```python
class NearbyMarketSource(BaseModel):
    """A nearby market source for an item."""
    order_id: int
    price: float
    volume_remain: int
    volume_total: int

    # Location details
    station_id: int
    station_name: str | None  # May be None for player structures
    system_id: int
    system_name: str  # Always populated via UniverseGraph
    security: float
    region_id: int
    region_name: str

    # Distance and routing
    jumps_from_origin: int
    route_security: str | None  # Deferred: computed on-demand for top results only

    # Order classification
    duration: int
    is_npc: bool  # True if duration >= 364
    issued: datetime

    # Derived metrics
    price_per_jump: float | None  # price / jumps for comparison

    # Anomaly flags
    price_flags: list[str] | None  # e.g., ["high_price_warning"]


class MarketFindNearbyResult(BaseModel):
    """Result from market_find_nearby tool."""
    # Query info
    type_id: int
    type_name: str
    category_name: str
    origin_system: str
    origin_region: str

    # Results
    sources: list[NearbyMarketSource]
    total_found: int

    # Search metadata
    regions_searched: list[str]
    source_filter_applied: str
    source_filter_suggested: str  # What we'd recommend for this item type

    # Summary stats
    nearest_source: NearbyMarketSource | None
    cheapest_source: NearbyMarketSource | None
    best_value: NearbyMarketSource | None  # Balances price and distance

    # Reference price for anomaly detection
    jita_reference_price: float | None
```

### Best Value Calculation

For items where both price and distance matter, calculate a "best value" score using a price-relative jump cost:

```python
def calculate_best_value(
    sources: list[NearbyMarketSource],
    item_price: float | None = None
) -> NearbyMarketSource:
    """
    Find the best value considering both price and travel cost.

    Uses a price-relative jump cost to avoid:
    - Overvaluing distance for cheap items (2M ISK blueprint + 10 jumps)
    - Undervaluing distance for expensive items (500M ISK module + 10 jumps)

    Args:
        sources: List of sources to evaluate
        item_price: Reference price for calculating jump cost.
                   If None, uses median price from sources.

    Returns:
        Source with lowest effective_price = price + (jumps * jump_cost_isk)
    """
    if not sources:
        return None

    # Use median price as reference if not provided
    if item_price is None:
        prices = sorted(s.price for s in sources)
        item_price = prices[len(prices) // 2]

    # Jump cost = 1% of item price per jump, clamped to reasonable range
    # Min 50k (don't bother traveling for trivial savings)
    # Max 500k (cap for very expensive items)
    jump_cost_isk = max(50_000, min(500_000, item_price * 0.01))

    return min(
        sources,
        key=lambda s: s.price + (s.jumps_from_origin * jump_cost_isk)
    )
```

This helps answer: "Is it worth 10 extra jumps to save 500k ISK?" with context-appropriate thresholds.

### Price Anomaly Detection

Flag suspiciously high prices that might indicate scams or outdated orders:

```python
def detect_price_anomalies(
    source: NearbyMarketSource,
    jita_price: float | None
) -> list[str]:
    """
    Flag potential price anomalies.

    Args:
        source: The market source to check
        jita_price: Reference price from Jita (if available)

    Returns:
        List of warning flags
    """
    flags = []

    if jita_price and source.price > jita_price * 10:
        if source.volume_remain < 10:
            flags.append("⚠️ Price 10x+ Jita with low stock - possible scam")
        else:
            flags.append("⚠️ Price significantly above Jita")

    return flags
```

**Implementation:** Fetch Jita price as baseline (likely already cached via MarketCache).

## Algorithm

```
1. RESOLVE item name → type_id, category_id via SDE
2. RESOLVE origin system → system_id, region_id via universe graph
3. DETERMINE suggested source_filter from item category
4. FETCH Jita reference price (for anomaly detection, likely cached)
5. QUERY ESI /markets/{region_id}/orders/?type_id={type_id}
   - Use MarketCache layer for rate limit protection
6. FILTER by order_type (sell/buy/all)
7. FILTER by source_filter (npc/player/all) using duration heuristic
8. RESOLVE location names:
   - system_name: UniverseGraph.idx_to_name[id_to_idx[system_id]] (O(1))
   - station_name: NPC stations from SDE cache, None for player structures
9. CALCULATE jump distances from origin using single BFS (terminates at max_jumps)
10. FILTER by max_jumps
11. DETECT price anomalies against Jita reference
12. IF results < limit AND expand_regions:
    a. FIND neighboring regions via gate connections
    b. QUERY each neighbor in parallel (up to max_regions total)
    c. MERGE and re-sort results
13. CALCULATE best_value scores with price-relative jump cost
14. COMPUTE route_security for top 3 results only (deferred)
15. RETURN top {limit} results sorted by distance
```

### Region Neighbor Discovery

```python
async def get_neighboring_regions(region_id: int) -> list[int]:
    """
    Find regions connected by stargates to the given region.

    Uses universe graph to find border systems and their
    cross-region gate connections.
    """
    # Get all systems in region via UniverseGraph.region_systems[region_id]
    # Find systems with gates to other regions (different region_id)
    # Return unique connected region IDs
```

### Station Name Resolution

**Challenge:** The SDE contains NPC station data, but player-owned structures (Citadels, Engineering Complexes) require authenticated ESI calls.

**Solution:**
1. **NPC Stations:** Pre-seed from Fuzzwork static data dump into SQLite
2. **Player Structures:** Accept `station_name: None` (structure names require auth)
3. **System Names:** Always resolved via `UniverseGraph.idx_to_name` (O(1))

```python
def resolve_station_name(station_id: int, db: MarketDatabase) -> str | None:
    """
    Resolve station name from SDE cache.

    Returns None for player-owned structures (requires auth to resolve).
    """
    # Query npc_stations table (pre-seeded from SDE)
    result = db.get_station_name(station_id)
    return result  # None if not found (player structure)
```

### Route Security Computation (Deferred)

Computing `route_security` requires pathfinding from origin to each destination. This is expensive for many results.

**Strategy:** Defer computation to top N results only:

```python
def compute_route_security(
    origin: str,
    destinations: list[NearbyMarketSource],
    universe: UniverseGraph,
    top_n: int = 3
) -> None:
    """
    Compute route_security for top N results only.

    Mutates destination objects in-place.
    """
    for source in destinations[:top_n]:
        route = universe.shortest_path(origin, source.system_name)
        securities = [universe.security[universe.name_to_idx[s]] for s in route]

        if all(sec >= 0.45 for sec in securities):
            source.route_security = "high"
        elif all(sec < 0.0 for sec in securities):
            source.route_security = "null"
        elif any(sec < 0.0 for sec in securities):
            source.route_security = "mixed-null"
        elif any(sec < 0.45 for sec in securities):
            source.route_security = "mixed-low"
        else:
            source.route_security = "high"
```

## Example Interactions

### Blueprint Search (NPC)

**Query:** "Where can I find EM Armor Hardener I Blueprint near Sortet?"

```python
market_find_nearby("EM Armor Hardener I Blueprint", "Sortet")
```

**Response:**
```json
{
  "type_name": "EM Armor Hardener I Blueprint",
  "category_name": "Blueprint",
  "origin_system": "Sortet",
  "source_filter_suggested": "npc",
  "source_filter_applied": "npc",
  "jita_reference_price": 2250000.0,
  "sources": [
    {
      "price": 2250000.0,
      "station_name": "Diaderi VII - Moon 3 - Amarr Navy Assembly Plant",
      "system_name": "Diaderi",
      "region_name": "Genesis",
      "jumps_from_origin": 5,
      "route_security": "high",
      "is_npc": true,
      "price_flags": []
    }
  ],
  "regions_searched": ["Verge Vendor", "Genesis"],
  "nearest_source": { "system_name": "Diaderi", "jumps": 5 },
  "cheapest_source": { "system_name": "Diaderi", "price": 2250000 }
}
```

### Module Search (Player + NPC)

**Query:** "Find Damage Control II near Amarr"

```python
market_find_nearby("Damage Control II", "Amarr", source_filter="all")
```

**Response:**
```json
{
  "type_name": "Damage Control II",
  "category_name": "Module",
  "origin_system": "Amarr",
  "source_filter_suggested": "all",
  "sources": [
    {
      "price": 450000.0,
      "station_name": "Amarr VIII - Emperor Family Academy",
      "jumps_from_origin": 0,
      "is_npc": false
    },
    {
      "price": 465000.0,
      "station_name": "Sarum Prime - Market Hub",
      "jumps_from_origin": 2,
      "is_npc": false
    }
  ],
  "nearest_source": { "system_name": "Amarr", "jumps": 0 },
  "cheapest_source": { "system_name": "Amarr", "price": 450000 },
  "best_value": { "system_name": "Amarr", "price": 450000, "jumps": 0 }
}
```

### Urgent Resupply

**Query:** "Nanite Repair Paste within 5 jumps of Tama"

```python
market_find_nearby("Nanite Repair Paste", "Tama", max_jumps=5)
```

**Response:**
```json
{
  "type_name": "Nanite Repair Paste",
  "origin_system": "Tama",
  "sources": [
    {
      "price": 18500.0,
      "volume_remain": 5000,
      "system_name": "Nourvukaiken",
      "jumps_from_origin": 2,
      "route_security": "low"
    },
    {
      "price": 17200.0,
      "volume_remain": 12000,
      "system_name": "Jita",
      "jumps_from_origin": 5,
      "route_security": "high"
    }
  ],
  "best_value": { "system_name": "Jita", "reason": "Cheaper and safer route" }
}
```

## New Skill: `/find`

A dedicated skill for proximity searches:

```
/find <item> [near <system>] [within <N> jumps]
```

**Examples:**
- `/find Damage Control II` - Search near current location
- `/find Venture Blueprint near Hek` - Search near Hek
- `/find Void M within 10 jumps` - Limit search radius

### Skill Configuration

```yaml
---
name: find
description: Find market items near a location. Use for proximity-based market searches.
model: haiku  # Stateless, formulaic - doesn't need opus/sonnet
category: financial
triggers:
  - "/find"
  - "find [item] near [location]"
  - "where can I buy [item]"
  - "nearest [item]"
requires_pilot: false  # Location detection requires auth, but explicit location works without
---
```

### Skill Behavior

1. **Parse query** using structured extraction:
   - Item name: Required, everything before "near" or "within"
   - Location: Optional, after "near", before "within"
   - Max jumps: Optional, number after "within"
2. **Detect current location** from ESI if no location specified (requires auth)
3. **Call `market_find_nearby`** with appropriate parameters
4. **Format results** as tactical table:

```
═══════════════════════════════════════════════════════════════════
MARKET SCAN: Damage Control II
Origin: Dodixie (Sinq Laison)
═══════════════════════════════════════════════════════════════════

NEAREST SOURCES:
┌──────────────┬───────────┬────────┬───────────┬─────────┐
│ Station      │ System    │ Jumps  │ Price     │ Stock   │
├──────────────┼───────────┼────────┼───────────┼─────────┤
│ Fed Navy     │ Dodixie   │ 0      │ 455,000   │ 847     │
│ Roden Ship   │ Botane    │ 3      │ 448,500   │ 234     │
│ Duvolle Labs │ Clellinon │ 5      │ 442,000   │ 1,203   │
└──────────────┴───────────┴────────┴───────────┴─────────┘

💡 Best value: Clellinon (5j) saves 13,000 ISK vs local

Regions searched: Sinq Laison, Verge Vendor
```

## Integration with Existing Tools

### `/price` Enhancement

When `/price` is invoked:

1. Query trade hub prices as normal
2. If item is Blueprint/Skillbook AND no trade hub results:
   - Automatically invoke `market_find_nearby` with `source_filter="npc"`
   - Report: "Not available at trade hubs. Nearest NPC source: ..."
3. Add optional `--nearby` flag to always include proximity search

### Code Reuse with `market_orders`

Rather than duplicating ESI fetch logic, `market_find_nearby` should leverage existing infrastructure:

```python
# In tools_nearby.py
from aria_esi.mcp.market.cache import MarketCache

async def fetch_regional_orders(
    region_id: int,
    type_id: int,
    cache: MarketCache
) -> list[dict]:
    """
    Fetch orders using shared cache layer.

    Reuses MarketCache for rate limit protection and TTL management.
    """
    # Use existing cache infrastructure from tools_orders.py
    return await cache.get_regional_orders(region_id, type_id)
```

This ensures:
- Consistent caching behavior
- Rate limit protection across all market tools
- Single source of truth for ESI interaction

### Deprecation of `market_npc_sources`

The existing `market_npc_sources` tool is fundamentally limited:
- Depends on `FACTION_REGIONS` mapping only 11 corporations
- Empire school corps (which seed most T1 blueprints) are not mapped
- Cannot discover items dynamically
- Misleads users with "not NPC-seeded" for seeded items

**Deprecation Timeline:**

| Phase | Action | Timing |
|-------|--------|--------|
| 1 | Add `market_find_nearby` | This release |
| 2 | Update `/price` skill to prefer `market_find_nearby` for blueprints/skillbooks | This release |
| 3 | Add deprecation warning to `market_npc_sources` docstring | Next release |
| 4 | Remove `market_npc_sources` and `FACTION_REGIONS` | Release + 2 |

## Implementation Plan

### Phase 1: Core Tool (Single Region)

Start without region expansion to validate core functionality:

- [ ] Add `market_find_nearby` MCP tool (single region only)
- [ ] Implement station name resolution (NPC stations from SDE)
- [ ] Add jump distance calculation via bounded BFS
- [ ] Add system_name population via UniverseGraph
- [ ] Write integration tests against known items (see Success Criteria)

### Phase 2: Multi-Region + Smart Defaults

- [ ] Implement region neighbor discovery
- [ ] Add parallel region queries with MarketCache
- [ ] Implement item category detection
- [ ] Add `source_filter` suggestions
- [ ] Add price-relative best-value calculation
- [ ] Add Jita reference price fetch for anomaly detection

### Phase 3: Skill Integration

- [ ] Create `/find` skill with haiku model
- [ ] Enhance `/price` with proximity fallback
- [ ] Add `--nearby` flag to `/price`
- [ ] Add deferred route_security computation

### Phase 4: Cleanup

- [ ] Add deprecation warning to `market_npc_sources`
- [ ] Update documentation in `docs/MARKET_TOOLS.md`
- [ ] Document heuristics (364-day NPC detection, category suggestions, best-value calculation)

### Phase 5: Removal (Future Release)

- [ ] Remove `market_npc_sources` tool
- [ ] Remove `FACTION_REGIONS` constant
- [ ] Remove `npc_seeding` table dependencies

## Performance Considerations

### ESI Rate Limits

| Operation | ESI Calls | Mitigation |
|-----------|-----------|------------|
| Single region query | 1 | MarketCache with 10 min TTL |
| Expanded search (5 regions) | 5 | Parallelize with asyncio.gather, share cache |
| Jita reference price | 1 | Likely already cached from recent queries |
| Station name lookup | 0 | Pre-seeded in SQLite |

**Rate Limit Protection:** All ESI calls MUST go through `MarketCache` to ensure consistent rate limiting across all market tools. Do not make raw ESI calls.

### Distance Calculations

For N results, naive approach requires N pathfinding operations.

**Optimization:** Single BFS from origin computes distances to all systems simultaneously. **Critical:** Terminate BFS at `max_jumps` rather than exploring entire graph.

```python
async def compute_distances_from(
    origin: str,
    max_jumps: int,
    universe: UniverseGraph
) -> dict[int, int]:
    """
    BFS from origin, return {system_id: jump_count} for all reachable systems.

    Terminates at max_jumps to avoid unnecessary graph traversal.
    """
    distances = {}
    origin_idx = universe.name_to_idx.get(origin.lower())
    if origin_idx is None:
        return distances

    queue = deque([(origin_idx, 0)])
    visited = {origin_idx}

    while queue:
        current, dist = queue.popleft()
        distances[universe.system_ids[current]] = dist

        if dist >= max_jumps:
            continue  # Don't explore beyond max_jumps

        for neighbor in universe.graph.neighbors(current):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, dist + 1))

    return distances
```

### Caching Strategy

| Data | TTL | Storage |
|------|-----|---------|
| ESI market orders | 10 min | MarketCache (memory) |
| Station names | Permanent | SQLite (pre-seeded) |
| System distances | Session | Memory (computed per query) |
| Region neighbors | Permanent | SQLite or computed from graph |
| Jita reference prices | 10 min | MarketCache (shared) |

## Files to Modify

| File | Changes |
|------|---------|
| `src/aria_esi/mcp/market/tools_nearby.py` | New file: `market_find_nearby` tool |
| `src/aria_esi/mcp/market/models.py` | Add response models |
| `src/aria_esi/mcp/market/__init__.py` | Register new tool |
| `src/aria_esi/mcp/market/tools.py` | Import and register nearby tools |
| `src/aria_esi/mcp/universe/graph.py` | Add `get_neighboring_regions()` |
| `src/aria_esi/mcp/market/database.py` | Add NPC station name resolution |
| `.claude/skills/find/SKILL.md` | New skill |
| `.claude/skills/price/SKILL.md` | Add proximity fallback |
| `docs/MARKET_TOOLS.md` | Document new capabilities and heuristics |

## Resolved Design Decisions

Based on engineering review, the following open questions have been resolved:

| Question | Decision | Rationale |
|----------|----------|-----------|
| Default search radius | **20 jumps** | Covers most practical cases; expansion handles edge cases |
| Best-value jump cost | **Price-relative (1% clamped 50k-500k)** | Avoids over/under-valuing distance based on item price |
| Route security in results | **Deferred to top 3 only** | Full computation too expensive; most users care about top results |
| Volume thresholds | **No filter by default** | Edge case; users can see volume and judge |
| Price anomaly detection | **Yes, with Jita baseline** | Valuable safety feature; minimal extra cost if cached |

## Testing Strategy

### Integration Tests

Write tests against known items with predictable results:

```python
@pytest.mark.integration
async def test_em_armor_hardener_blueprint_near_sortet():
    """EM Armor Hardener I Blueprint should be found in Diaderi."""
    result = await market_find_nearby(
        "EM Armor Hardener I Blueprint",
        "Sortet"
    )
    assert result.sources
    assert any(s.system_name == "Diaderi" for s in result.sources)
    assert result.sources[0].is_npc is True

@pytest.mark.integration
async def test_damage_control_near_amarr():
    """Damage Control II should have player orders in Amarr."""
    result = await market_find_nearby(
        "Damage Control II",
        "Amarr"
    )
    assert result.sources
    assert result.sources[0].jumps_from_origin == 0  # In-system

@pytest.mark.integration
async def test_source_filter_suggestion():
    """Blueprints should suggest NPC filter."""
    result = await market_find_nearby(
        "Venture Blueprint",
        "Jita"
    )
    assert result.source_filter_suggested == "npc"
```

### Unit Tests

- Category detection logic
- Best-value calculation with various price ranges
- Price anomaly detection
- BFS termination at max_jumps

## Success Criteria

After implementation:

| Query | Expected Result |
|-------|-----------------|
| "EM Armor Hardener I Blueprint near Sortet" | Returns Diaderi (5j), is_npc=True |
| "Venture Blueprint near Jita" | Returns Outer Ring sources, is_npc=True |
| "Damage Control II near Amarr" | Returns local market options, is_npc=False |
| "Thermodynamics near Hek" | Returns school station, is_npc=True |
| "Void M within 10 jumps of Tama" | Returns nearest ammo source |

---

## Engineering Notes

### Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Station name resolution gap | Medium | Accept None for player structures; pre-seed NPC stations |
| Category detection reliability | Low | Verify against SDE during implementation |
| ESI rate limits with parallel expansion | Medium | Use shared MarketCache; don't bypass cache |
| BFS performance for large max_jumps | Low | Terminate at max_jumps, not full graph |

### Architecture Alignment

The proposal correctly identifies reusable components:
- `UniverseGraph`: region_systems, border detection, BFS infrastructure
- `MarketDatabase`: type/region resolution with fuzzy matching
- `MarketCache`: multi-layer caching with rate limit protection
- Existing patterns: error objects, Pydantic models, async caching

### Key Implementation Notes

1. **Always use MarketCache** - Never make raw ESI calls
2. **System names are free** - UniverseGraph.idx_to_name is O(1)
3. **Station names are limited** - Only NPC stations without auth
4. **Defer expensive operations** - Route security only for top results
5. **Test with real data** - Success criteria are verifiable against live ESI

---

## References

- Original proposal: `dev/proposals/BLUEPRINT_SEARCH_PROPOSAL.md`
- Current NPC tool: `src/aria_esi/mcp/market/tools_npc.py`
- Universe graph: `src/aria_esi/universe/graph.py`
- Market cache: `src/aria_esi/mcp/market/cache.py`
- SDE constants: `src/aria_esi/models/sde.py`
- ESI market endpoint: `GET /markets/{region_id}/orders/`
