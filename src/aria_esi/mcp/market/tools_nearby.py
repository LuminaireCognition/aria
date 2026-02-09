"""
Proximity-Based Market Search MCP Tools.

Provides market_find_nearby tool for finding market sources near a location.
Supports NPC/player filtering, distance calculation, and smart category-based defaults.
"""

from __future__ import annotations

import asyncio
from collections import deque
from typing import TYPE_CHECKING, Literal

from aria_esi.core.logging import get_logger
from aria_esi.mcp.market.cache import MarketCache, get_market_cache
from aria_esi.mcp.market.database import get_market_database
from aria_esi.models.market import (
    MarketFindNearbyResult,
    NearbyMarketSource,
    SourceFilter,
)
from aria_esi.models.sde import CATEGORY_BLUEPRINT, CATEGORY_SKILL

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from aria_esi.universe.graph import UniverseGraph

logger = get_logger("aria_market.tools_nearby")

# NPC order duration threshold (364+ days indicates NPC-seeded)
NPC_DURATION_THRESHOLD = 364

# Category ID for implants (not in sde.py constants)
CATEGORY_IMPLANT = 20


def get_neighboring_regions(region_id: int, universe: UniverseGraph) -> list[int]:
    """
    Find regions connected by stargates to the given region.

    Uses universe graph to find border systems and their
    cross-region gate connections.

    Args:
        region_id: Region ID to find neighbors for
        universe: Universe graph for navigation

    Returns:
        List of neighboring region IDs
    """
    neighbor_regions: set[int] = set()

    # Get all systems in this region
    region_systems = universe.region_systems.get(region_id, [])

    for system_idx in region_systems:
        # Check each neighbor of this system
        for neighbor_idx in universe.graph.neighbors(system_idx):
            neighbor_region_id = int(universe.region_ids[neighbor_idx])
            if neighbor_region_id != region_id:
                neighbor_regions.add(neighbor_region_id)

    return list(neighbor_regions)


async def fetch_region_orders(
    region_id: int,
    type_id: int,
    order_type: str,
    cache: MarketCache | None = None,
) -> tuple[int, list[dict]]:
    """
    Fetch orders for a single region via MarketCache.

    Uses MarketCache for rate limit protection and TTL-based caching.

    Args:
        region_id: Region to query
        type_id: Item type ID
        order_type: "sell", "buy", or "all"
        cache: Optional MarketCache instance (creates one if not provided)

    Returns:
        Tuple of (region_id, orders_list)
    """
    try:
        if cache is None:
            cache = get_market_cache()

        orders = await cache.get_regional_orders(region_id, type_id, order_type)
        return (region_id, orders)

    except Exception as e:
        logger.debug("Failed to fetch orders for region %d: %s", region_id, e)
        return (region_id, [])


def suggest_source_filter(category_id: int | None) -> SourceFilter:
    """
    Suggest source_filter based on item classification.

    Args:
        category_id: Item category ID from SDE

    Returns:
        Suggested source filter based on item type
    """
    if category_id is None:
        return "all"

    # Blueprints: Prefer NPC (most T1 BPOs are seeded)
    if category_id == CATEGORY_BLUEPRINT:
        return "npc"

    # Skillbooks: Always NPC
    if category_id == CATEGORY_SKILL:
        return "npc"

    # Implants: Often NPC but also player-traded
    if category_id == CATEGORY_IMPLANT:
        return "all"

    # Everything else: All sources
    return "all"


def compute_distances_bounded_bfs(
    origin_idx: int,
    max_jumps: int,
    universe: UniverseGraph,
) -> dict[int, int]:
    """
    BFS from origin to compute distances to all reachable systems.

    Terminates at max_jumps to avoid unnecessary graph traversal.

    Args:
        origin_idx: Starting vertex index
        max_jumps: Maximum distance to explore
        universe: Universe graph for navigation

    Returns:
        Dict mapping system_id to jump distance
    """
    distances: dict[int, int] = {}
    queue: deque[tuple[int, int]] = deque([(origin_idx, 0)])
    visited: set[int] = {origin_idx}

    while queue:
        current_idx, dist = queue.popleft()
        system_id = universe.get_system_id(current_idx)
        distances[system_id] = dist

        if dist >= max_jumps:
            continue  # Don't explore beyond max_jumps

        for neighbor_idx in universe.graph.neighbors(current_idx):
            if neighbor_idx not in visited:
                visited.add(neighbor_idx)
                queue.append((neighbor_idx, dist + 1))

    return distances


def compute_route_security(
    origin_idx: int,
    dest_idx: int,
    universe: UniverseGraph,
) -> Literal["high", "low", "mixed-low", "mixed-null", "null"]:
    """
    Compute route security classification between two systems.

    Args:
        origin_idx: Starting vertex index
        dest_idx: Destination vertex index
        universe: Universe graph for navigation

    Returns:
        Security classification for the route
    """
    # Use igraph's shortest path
    path_indices = universe.graph.get_shortest_paths(origin_idx, dest_idx)[0]
    if not path_indices:
        return "high"  # Same system or unreachable

    securities = [float(universe.security[idx]) for idx in path_indices]

    if all(sec >= 0.45 for sec in securities):
        return "high"
    elif all(sec <= 0.0 for sec in securities):
        return "null"
    elif any(sec <= 0.0 for sec in securities):
        return "mixed-null"
    elif any(sec < 0.45 for sec in securities):
        return "mixed-low"
    else:
        return "high"


def calculate_best_value(
    sources: list[NearbyMarketSource],
    jita_price: float | None = None,
) -> NearbyMarketSource | None:
    """
    Find the best value considering both price and travel cost.

    Uses a price-relative jump cost to avoid:
    - Overvaluing distance for cheap items (2M ISK blueprint + 10 jumps)
    - Undervaluing distance for expensive items (500M ISK module + 10 jumps)

    Args:
        sources: List of sources to evaluate
        jita_price: Reference price for calculating jump cost.
                   If None, uses median price from sources.

    Returns:
        Source with lowest effective_price = price + (jumps * jump_cost_isk)
    """
    if not sources:
        return None

    # Use Jita price or median price as reference
    if jita_price is None or jita_price <= 0:
        prices = sorted(s.price for s in sources if s.price > 0)
        if not prices:
            return sources[0]  # Fallback to first
        jita_price = prices[len(prices) // 2]

    # Jump cost = 1% of item price per jump, clamped to reasonable range
    # Min 50k (don't bother traveling for trivial savings)
    # Max 500k (cap for very expensive items)
    jump_cost_isk = max(50_000, min(500_000, jita_price * 0.01))

    return min(
        sources,
        key=lambda s: s.price + (s.jumps_from_origin * jump_cost_isk),
    )


def detect_price_anomalies(
    price: float,
    jita_price: float | None,
    volume_remain: int,
) -> list[str]:
    """
    Flag potential price anomalies.

    Args:
        price: The order price
        jita_price: Reference price from Jita (if available)
        volume_remain: Remaining volume on the order

    Returns:
        List of warning flags
    """
    flags = []

    if jita_price and jita_price > 0 and price > jita_price * 10:
        if volume_remain < 10:
            flags.append("⚠️ Price 10x+ Jita with low stock - possible scam")
        else:
            flags.append("⚠️ Price significantly above Jita")

    return flags


def get_category_name(category_id: int | None) -> str | None:
    """Get human-readable category name from ID."""
    category_names = {
        6: "Ship",
        7: "Module",
        8: "Charge",
        9: "Blueprint",
        16: "Skill",
        18: "Drone",
        20: "Implant",
        25: "Asteroid",
    }
    if category_id is None:
        return None
    return category_names.get(category_id)


# Module-level universe reference for direct tool registration
# Falls back to global registry when using dispatcher pattern
_universe: UniverseGraph | None = None


def get_universe() -> UniverseGraph:
    """Get the universe graph, with fallback to global registry.

    Supports two initialization patterns:
    1. Direct registration via register_nearby_tools() - sets module-level _universe
    2. Dispatcher pattern via dispatchers/market.py - uses global from tools.py
    """
    if _universe is not None:
        return _universe

    # Fallback to global registry (dispatcher pattern)
    from aria_esi.mcp.tools import get_universe as get_global_universe

    return get_global_universe()


async def _find_nearby_impl(
    item: str,
    origin: str,
    max_jumps: int = 20,
    order_type: str = "sell",
    source_filter: str = "all",
    expand_regions: bool = True,
    max_regions: int = 5,
    limit: int = 10,
) -> dict:
    """
    Implementation for find_nearby action.

    Find market sources for an item near a location.
    """
    universe = get_universe()

    # Clamp parameters
    max_jumps = max(1, min(50, max_jumps))
    limit = max(1, min(50, limit))

    # Normalize order_type and source_filter
    order_type = order_type.lower()
    if order_type not in ("sell", "buy", "all"):
        order_type = "sell"

    source_filter_normalized: SourceFilter = "all"
    if source_filter.lower() == "npc":
        source_filter_normalized = "npc"
    elif source_filter.lower() == "player":
        source_filter_normalized = "player"

    warnings: list[str] = []

    # Step 1: Resolve item name
    db = get_market_database()
    type_info = db.resolve_type_name(item)

    if not type_info:
        suggestions = db.find_type_suggestions(item)
        return {
            "error": {
                "code": "TYPE_NOT_FOUND",
                "message": f"Unknown item: {item}",
                "data": {"suggestions": suggestions},
            }
        }

    type_id = type_info.type_id
    type_name = type_info.type_name
    category_id = type_info.category_id
    category_name = get_category_name(category_id)

    # Step 2: Resolve origin system
    origin_idx = universe.resolve_name(origin)
    if origin_idx is None:
        return {
            "error": {
                "code": "SYSTEM_NOT_FOUND",
                "message": f"Unknown system: {origin}",
            }
        }

    origin_system_name = universe.idx_to_name[origin_idx]
    origin_region_id = int(universe.region_ids[origin_idx])
    origin_region_name = universe.get_region_name(origin_idx)

    # Step 3: Determine suggested source_filter
    suggested_filter = suggest_source_filter(category_id)

    # Step 4: Compute distances via bounded BFS
    distances = compute_distances_bounded_bfs(origin_idx, max_jumps, universe)

    # Step 5: Fetch orders from origin region first
    regions_searched_names = [origin_region_name]
    all_orders: list[dict] = []
    had_region_failures = False

    try:
        _region_id, origin_orders = await fetch_region_orders(origin_region_id, type_id, order_type)
        all_orders.extend(origin_orders)
    except Exception as e:
        logger.warning("Failed to fetch orders from origin region: %s", e)
        had_region_failures = True

    # Step 6: Count valid results from origin region
    origin_results_count = sum(1 for order in all_orders if order.get("system_id") in distances)

    # Step 7: Expand to neighboring regions if results sparse
    if expand_regions and origin_results_count < limit:
        # Clamp max_regions
        max_regions_clamped = max(1, min(10, max_regions))
        neighbor_region_ids = get_neighboring_regions(origin_region_id, universe)

        # Limit to max_regions - 1 (origin already searched)
        regions_to_expand = neighbor_region_ids[: max_regions_clamped - 1]

        if regions_to_expand:
            try:
                # Query neighbor regions in parallel
                tasks = [
                    fetch_region_orders(region_id, type_id, order_type)
                    for region_id in regions_to_expand
                ]

                results = await asyncio.gather(*tasks, return_exceptions=True)

                for fetch_result in results:
                    if isinstance(fetch_result, Exception):
                        logger.debug("Neighbor region query failed: %s", fetch_result)
                        had_region_failures = True
                    elif isinstance(fetch_result, tuple):
                        region_id, orders = fetch_result
                        all_orders.extend(orders)
                        # Add region name
                        region_name = universe.region_names.get(region_id, f"Region {region_id}")
                        if region_name not in regions_searched_names:
                            regions_searched_names.append(region_name)

            except Exception as e:
                logger.warning("Failed to fetch orders from neighbor regions: %s", e)
                had_region_failures = True

    # Add single warning if any region queries failed
    if had_region_failures:
        warnings.append("Some region queries failed")

    # Step 6: Get Jita reference price for anomaly detection
    jita_reference_price: float | None = None
    try:
        from aria_esi.mcp.market.cache import get_market_cache

        cache = get_market_cache()
        jita_prices = await cache.get_prices([type_id], {type_id: type_name})
        if jita_prices:
            for item_price in jita_prices:
                if item_price.type_id == type_id:
                    jita_reference_price = item_price.sell.min_price if item_price.sell else None
                    break
    except Exception as e:
        logger.debug("Could not fetch Jita reference price: %s", e)

    # Step 7: Filter and process orders
    sources: list[NearbyMarketSource] = []

    for order in all_orders:
        system_id = order.get("system_id")
        if system_id is None:
            continue

        # Check if system is within max_jumps
        if system_id not in distances:
            continue

        jumps = distances[system_id]

        # Apply source filter
        duration = order.get("duration", 0)
        is_npc = duration >= NPC_DURATION_THRESHOLD

        if source_filter_normalized == "npc" and not is_npc:
            continue
        elif source_filter_normalized == "player" and is_npc:
            continue

        # Resolve system info from universe graph
        system_idx = universe.id_to_idx.get(system_id)
        if system_idx is None:
            continue

        system_name = universe.idx_to_name[system_idx]
        security = float(universe.security[system_idx])
        region_id = int(universe.region_ids[system_idx])
        region_name = universe.get_region_name(system_idx)

        # Station name resolution (NPC stations only - player structures require auth)
        station_id = order.get("location_id", 0)
        station_name = resolve_station_name(station_id)

        price = order.get("price", 0)
        volume_remain = order.get("volume_remain", 0)

        # Calculate price per jump
        price_per_jump = price / jumps if jumps > 0 else None

        # Detect price anomalies
        price_flags = detect_price_anomalies(price, jita_reference_price, volume_remain)

        source = NearbyMarketSource(
            order_id=order.get("order_id", 0),
            price=price,
            volume_remain=volume_remain,
            volume_total=order.get("volume_total", 0),
            station_id=station_id,
            station_name=station_name,
            system_id=system_id,
            system_name=system_name,
            security=round(security, 2),
            region_id=region_id,
            region_name=region_name,
            jumps_from_origin=jumps,
            route_security=None,  # Computed later for top results
            duration=duration,
            is_npc=is_npc,
            issued=order.get("issued", ""),
            price_per_jump=round(price_per_jump, 2) if price_per_jump else None,
            price_flags=price_flags,
        )
        sources.append(source)

    # Sort by distance, then by price
    sources.sort(key=lambda s: (s.jumps_from_origin, s.price))

    total_found = len(sources)

    # Step 8: Compute route security for top results (deferred computation)
    for source in sources[:3]:
        dest_idx = universe.id_to_idx.get(source.system_id)
        if dest_idx is not None:
            # Create mutable copy with route security
            route_sec = compute_route_security(origin_idx, dest_idx, universe)
            # Update via dict manipulation since model is frozen
            source_dict = source.model_dump()
            source_dict["route_security"] = route_sec
            sources[sources.index(source)] = NearbyMarketSource(**source_dict)

    # Limit results
    limited_sources = sources[:limit]

    # Step 9: Calculate summary stats
    nearest_source = limited_sources[0] if limited_sources else None
    cheapest_source = min(limited_sources, key=lambda s: s.price) if limited_sources else None
    best_value = calculate_best_value(limited_sources, jita_reference_price)

    result = MarketFindNearbyResult(
        type_id=type_id,
        type_name=type_name,
        category_id=category_id,
        category_name=category_name,
        origin_system=origin_system_name,
        origin_region=origin_region_name,
        sources=limited_sources,
        total_found=total_found,
        regions_searched=regions_searched_names,
        source_filter_applied=source_filter_normalized,
        source_filter_suggested=suggested_filter,
        nearest_source=nearest_source,
        cheapest_source=cheapest_source,
        best_value=best_value,
        jita_reference_price=jita_reference_price,
        warnings=warnings,
    )

    return result.model_dump()


def register_nearby_tools(server: FastMCP, universe: UniverseGraph) -> None:
    """Register proximity-based market tools with MCP server."""
    global _universe
    _universe = universe

    @server.tool()
    async def market_find_nearby(
        item: str,
        origin: str,
        max_jumps: int = 20,
        order_type: str = "sell",
        source_filter: str = "all",
        expand_regions: bool = True,
        max_regions: int = 5,
        limit: int = 10,
    ) -> dict:
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
            expand_regions: Search neighboring regions if local results sparse (default: True)
            max_regions: Maximum regions to search (default: 5)
            limit: Maximum results to return (default: 10)

        Returns:
            Sources sorted by distance, with prices and station details

        Examples:
            market_find_nearby("EM Armor Hardener I Blueprint", "Sortet")
            market_find_nearby("Damage Control II", "Amarr", source_filter="all")
            market_find_nearby("Nanite Repair Paste", "Tama", max_jumps=5)
        """
        return await _find_nearby_impl(
            item, origin, max_jumps, order_type, source_filter, expand_regions, max_regions, limit
        )


def resolve_station_name(station_id: int) -> str | None:
    """
    Resolve station name from NPC station data.

    Returns None for player-owned structures (requires auth to resolve).

    Args:
        station_id: Station or structure ID

    Returns:
        Station name if NPC station, None otherwise
    """
    # NPC stations have IDs in the 60xxxxxx range
    # Player structures have much higher IDs (typically > 1000000000000)
    if station_id < 60000000 or station_id >= 70000000:
        return None

    # Try to look up from database
    try:
        db = get_market_database()
        conn = db._get_connection()

        # Check if stations table exists
        try:
            row = conn.execute(
                "SELECT station_name FROM stations WHERE station_id = ?",
                (station_id,),
            ).fetchone()
            if row:
                return row["station_name"]
        except Exception:
            pass  # Table doesn't exist or other error

    except Exception:
        pass

    return None
