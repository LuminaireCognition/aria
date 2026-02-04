"""
Market NPC Sources MCP Tools.

Provides market_npc_sources tool for discovering NPC-seeded items
and their locations.

Includes ESI fallback for items not yet in SDE - detects NPC orders
by their 365-day duration signature even when npc_seeding table is incomplete.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from aria_esi.core.logging import get_logger
from aria_esi.mcp.market.database import get_market_database
from aria_esi.mcp.sde.queries import SDENotSeededError, get_sde_query_service

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from aria_esi.core.async_client import AsyncESIClient

logger = get_logger("aria_market.tools_npc")

# Maximum concurrent ESI requests for region scanning
MAX_CONCURRENT_REGION_SCANS = 10

# NPC order duration threshold (days) - NPC orders always have 365-day expiration
NPC_ORDER_DURATION_THRESHOLD = 364

# Empire trade hub regions for fallback when corporation has no station presence
# These cover the major empire market hubs where standard T1 blueprints are sold
EMPIRE_TRADE_REGIONS: list[tuple[int, str]] = [
    (10000002, "The Forge"),  # Jita (Caldari)
    (10000043, "Domain"),  # Amarr (Amarr)
    (10000032, "Sinq Laison"),  # Dodixie (Gallente)
    (10000042, "Metropolis"),  # Hek (Minmatar)
    (10000030, "Heimatar"),  # Rens (Minmatar)
]


# =============================================================================
# ESI Fallback Scanner
# =============================================================================


async def _scan_region_for_npc_orders(
    client: AsyncESIClient,
    region_id: int,
    type_id: int,
) -> list[dict]:
    """
    Scan a single region for NPC orders (365-day duration).

    Args:
        client: Async ESI client instance
        region_id: Region to scan
        type_id: Item type to look for

    Returns:
        List of order dicts that appear to be NPC-seeded
    """
    try:
        data = await client.get(
            f"/markets/{region_id}/orders/",
            params={"type_id": str(type_id), "order_type": "sell"},
        )

        if not isinstance(data, list):
            return []

        # Filter for NPC orders (364+ day duration)
        return [order for order in data if order.get("duration", 0) >= NPC_ORDER_DURATION_THRESHOLD]

    except Exception as e:
        logger.debug("Failed to scan region %d for type %d: %s", region_id, type_id, e)
        return []


async def _esi_fallback_scan(
    type_id: int,
    type_name: str,
    limit: int,
) -> tuple[list[NPCSourceInfo], list[str], int]:
    """
    Scan ESI for NPC orders when SDE seeding data is missing.

    This fallback detects NPC-seeded items by their 365-day order duration,
    even when the npc_seeding table doesn't have the item.

    Args:
        type_id: Item type ID to search for
        type_name: Item name (for logging)
        limit: Maximum orders per source

    Returns:
        Tuple of (sources, warnings, total_orders)
    """
    warnings: list[str] = []
    sources: list[NPCSourceInfo] = []
    total_orders = 0

    try:
        query_service = get_sde_query_service()
        npc_regions = query_service.get_npc_station_regions()
    except SDENotSeededError:
        warnings.append("SDE not seeded - cannot perform ESI fallback scan.")
        return sources, warnings, total_orders
    except Exception as e:
        warnings.append(f"Failed to get NPC regions: {e}")
        return sources, warnings, total_orders

    if not npc_regions:
        warnings.append("No NPC station regions found in SDE.")
        return sources, warnings, total_orders

    logger.info(
        "ESI fallback: scanning %d regions for NPC orders of '%s' (type_id=%d)",
        len(npc_regions),
        type_name,
        type_id,
    )

    try:
        from aria_esi.mcp.esi_client import get_async_esi_client

        client = await get_async_esi_client()
    except Exception as e:
        warnings.append(f"ESI client not available for fallback scan: {e}")
        return sources, warnings, total_orders

    # Scan regions with concurrency limit
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REGION_SCANS)
    all_npc_orders: list[tuple[int, str, dict]] = []  # (region_id, region_name, order)

    async def scan_with_limit(region_id: int, region_name: str) -> list[tuple[int, str, Any]]:
        async with semaphore:
            orders = await _scan_region_for_npc_orders(client, region_id, type_id)
            return [(region_id, region_name, order) for order in orders]

    # Create tasks for all regions
    tasks = [scan_with_limit(region_id, region_name) for region_id, region_name in npc_regions]

    # Gather results
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, BaseException):
            logger.debug("Region scan failed: %s", result)
            continue
        if isinstance(result, list):
            all_npc_orders.extend(result)

    if not all_npc_orders:
        warnings.append(
            f"ESI fallback scan found no NPC orders for '{type_name}' across {len(npc_regions)} regions."
        )
        return sources, warnings, total_orders

    logger.info(
        "ESI fallback found %d NPC orders for '%s'",
        len(all_npc_orders),
        type_name,
    )

    # Collect unique station IDs for bulk lookup
    station_ids = list({order["location_id"] for _, _, order in all_npc_orders})

    # Look up station ownership
    try:
        station_info = query_service.get_stations_bulk(station_ids)
    except Exception as e:
        logger.warning("Failed to look up station info: %s", e)
        station_info = {}

    # Group orders by corporation
    orders_by_corp: dict[tuple[int, str, int, str], list[dict]] = defaultdict(list)

    for region_id, region_name, order in all_npc_orders:
        station_id = order.get("location_id", 0)
        info = station_info.get(station_id)

        if info:
            corp_key = (info.corporation_id, info.corporation_name, region_id, region_name)
        else:
            # Unknown station (possibly player structure or unmapped NPC station)
            corp_key = (0, "Unknown Corporation", region_id, region_name)

        orders_by_corp[corp_key].append(order)

    # Build source results
    for (corp_id, corp_name, region_id, region_name), orders in orders_by_corp.items():
        # Sort by price and limit
        orders.sort(key=lambda x: x.get("price", 0))
        limited_orders = orders[:limit]

        npc_orders = []
        for order in limited_orders:
            location_id = order.get("location_id", 0)
            station = station_info.get(location_id)
            npc_orders.append(
                NPCOrder(
                    order_id=order.get("order_id", 0),
                    price=order.get("price", 0),
                    volume_remain=order.get("volume_remain", 0),
                    location_id=location_id,
                    location_name=station.station_name if station else None,
                    system_id=order.get("system_id", 0),
                    system_name=None,  # System name not available in SDE station data
                    duration=order.get("duration", 0),
                    is_npc=True,
                )
            )

        sources.append(
            NPCSourceInfo(
                corporation_id=corp_id,
                corporation_name=corp_name,
                region_id=region_id,
                region_name=region_name,
                orders=npc_orders,
                order_count=len(npc_orders),
            )
        )
        total_orders += len(npc_orders)

    # Sort sources by order count descending
    sources.sort(key=lambda x: x.order_count, reverse=True)

    warnings.append(
        f"Data from ESI fallback scan (item not in SDE npc_seeding table). "
        f"Found {total_orders} NPC orders in {len(sources)} locations."
    )

    return sources, warnings, total_orders


# =============================================================================
# Models for NPC Sources
# =============================================================================


class NPCSourceModel(BaseModel):
    """Base model for NPC source data."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class NPCOrder(NPCSourceModel):
    """An NPC-seeded market order."""

    order_id: int = Field(ge=1, description="Order ID")
    price: float = Field(ge=0, description="Price per unit")
    volume_remain: int = Field(ge=0, description="Remaining volume")
    location_id: int = Field(ge=1, description="Station ID")
    location_name: str | None = Field(default=None, description="Station name")
    system_id: int = Field(ge=1, description="Solar system ID")
    system_name: str | None = Field(default=None, description="Solar system name")
    duration: int = Field(ge=0, description="Order duration in days")
    is_npc: bool = Field(description="True if likely an NPC order (364+ day duration)")


class NPCSourceInfo(NPCSourceModel):
    """Information about an NPC source for an item."""

    corporation_id: int = Field(ge=0, description="Seeding corporation ID (0 if unknown)")
    corporation_name: str = Field(description="Seeding corporation name")
    region_id: int = Field(ge=1, description="Region ID")
    region_name: str = Field(description="Region name")
    orders: list[NPCOrder] = Field(default_factory=list, description="Found NPC orders")
    order_count: int = Field(default=0, ge=0, description="Number of NPC orders found")


class NPCSourcesResult(NPCSourceModel):
    """Result from market_npc_sources tool."""

    type_id: int = Field(ge=1, description="Item type ID")
    type_name: str = Field(description="Item name")
    found: bool = Field(description="Whether any NPC sources were found")
    sources: list[NPCSourceInfo] = Field(default_factory=list, description="NPC source information")
    total_orders: int = Field(default=0, ge=0, description="Total NPC orders found")
    warnings: list[str] = Field(default_factory=list)


# =============================================================================
# Implementation Functions (for dispatcher access)
# =============================================================================


async def _npc_sources_impl(item: str, limit: int = 10) -> dict:
    """
    Implementation for npc_sources action.

    Find NPC sources for an item.
    """
    db = get_market_database()
    conn = db._get_connection()
    warnings: list[str] = []

    # Clamp limit
    limit = max(1, min(50, limit))

    # Resolve item name
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

    # Check if npc_seeding table exists
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='npc_seeding'"
    )
    if not cursor.fetchone():
        return NPCSourcesResult(
            type_id=type_id,
            type_name=type_name,
            found=False,
            sources=[],
            total_orders=0,
            warnings=["SDE data not seeded. Run 'aria-esi sde-seed' first."],
        ).model_dump()

    # Look up NPC seeding corporations for this item
    cursor = conn.execute(
        """
        SELECT
            ns.corporation_id,
            nc.corporation_name
        FROM npc_seeding ns
        JOIN npc_corporations nc ON ns.corporation_id = nc.corporation_id
        WHERE ns.type_id = ?
        """,
        (type_id,),
    )

    seeding_corps = cursor.fetchall()
    if not seeding_corps:
        # SDE doesn't know about this item's NPC seeding - try ESI fallback
        # This catches new items added to EVE before SDE is updated
        logger.info(
            "No SDE seeding data for '%s' (type_id=%d), trying ESI fallback",
            type_name,
            type_id,
        )

        fallback_sources, fallback_warnings, fallback_total = await _esi_fallback_scan(
            type_id, type_name, limit
        )

        if fallback_sources:
            # ESI fallback found NPC orders
            return NPCSourcesResult(
                type_id=type_id,
                type_name=type_name,
                found=True,
                sources=fallback_sources,
                total_orders=fallback_total,
                warnings=fallback_warnings,
            ).model_dump()
        else:
            # ESI fallback also found nothing - item is genuinely not NPC-seeded
            all_warnings = fallback_warnings + [
                f"'{type_name}' is not NPC-seeded. "
                "It may be obtained through other means (LP store, loot, invention)."
            ]
            return NPCSourcesResult(
                type_id=type_id,
                type_name=type_name,
                found=False,
                sources=[],
                total_orders=0,
                warnings=all_warnings,
            ).model_dump()

    # Build list of regions to query
    regions_to_query: list[
        tuple[int, str, int, str]
    ] = []  # (corp_id, corp_name, region_id, region_name)

    # Track corporations without specific region mappings
    unmapped_corps: list[tuple[int, str]] = []

    # Get the query service for dynamic region lookups
    try:
        query_service = get_sde_query_service()
    except Exception:
        query_service = None

    for corp_id, corp_name in seeding_corps:
        # Try dynamic lookup first
        corp_regions = None
        if query_service:
            try:
                corp_regions = query_service.get_corporation_regions(corp_id)
            except SDENotSeededError:
                pass

        if corp_regions and corp_regions.regions:
            for region_id, region_name, _ in corp_regions.regions:
                regions_to_query.append((corp_id, corp_name, region_id, region_name))
        else:
            unmapped_corps.append((corp_id, corp_name))

    # For unmapped corporations (typically empire manufacturers),
    # query major empire trade hub regions as fallback
    if unmapped_corps and not regions_to_query:
        for corp_id, corp_name in unmapped_corps:
            for region_id, region_name in EMPIRE_TRADE_REGIONS:
                regions_to_query.append((corp_id, corp_name, region_id, region_name))
        warnings.append(
            f"Using empire trade hub fallback for: {', '.join(name for _, name in unmapped_corps)}"
        )

    if not regions_to_query:
        return NPCSourcesResult(
            type_id=type_id,
            type_name=type_name,
            found=False,
            sources=[],
            total_orders=0,
            warnings=warnings
            + [
                "Found NPC seeding data but no region mappings. "
                "Item may be seeded in an unmapped region."
            ],
        ).model_dump()

    # Query ESI for orders in each region
    sources: list[NPCSourceInfo] = []
    total_orders = 0

    try:
        from aria_esi.mcp.esi_client import get_async_esi_client

        client = await get_async_esi_client()

        for corp_id, corp_name, region_id, region_name in regions_to_query:
            try:
                data = await client.get(
                    f"/markets/{region_id}/orders/",
                    params={"type_id": str(type_id), "order_type": "sell"},
                )

                if not isinstance(data, list):
                    continue

                # Filter for NPC orders (364+ day duration)
                npc_orders: list[NPCOrder] = []
                for order in data:
                    duration = order.get("duration", 0)
                    is_npc = duration >= 364

                    if is_npc:
                        npc_orders.append(
                            NPCOrder(
                                order_id=order.get("order_id", 0),
                                price=order.get("price", 0),
                                volume_remain=order.get("volume_remain", 0),
                                location_id=order.get("location_id", 0),
                                location_name=None,
                                system_id=order.get("system_id", 0),
                                system_name=None,
                                duration=duration,
                                is_npc=True,
                            )
                        )

                # Sort by price (lowest first) and limit
                npc_orders.sort(key=lambda x: x.price)
                npc_orders = npc_orders[:limit]

                if npc_orders:
                    sources.append(
                        NPCSourceInfo(
                            corporation_id=corp_id,
                            corporation_name=corp_name,
                            region_id=region_id,
                            region_name=region_name,
                            orders=npc_orders,
                            order_count=len(npc_orders),
                        )
                    )
                    total_orders += len(npc_orders)

            except Exception as e:
                logger.warning("Failed to fetch orders from region %s: %s", region_id, e)
                warnings.append(f"Failed to query {region_name}: {e}")

    except Exception as e:
        return {
            "error": {
                "code": "ESI_UNAVAILABLE",
                "message": f"ESI client error: {e}",
            }
        }

    # If SDE-based search found no orders, try ESI fallback
    # This handles cases where SDE seeding data is incorrect or outdated
    if not sources:
        logger.info(
            "SDE-based search found no NPC orders for '%s', trying ESI fallback",
            type_name,
        )
        fallback_sources, fallback_warnings, fallback_total = await _esi_fallback_scan(
            type_id, type_name, limit
        )

        if fallback_sources:
            # ESI fallback found orders that SDE-based search missed
            all_warnings = (
                warnings
                + fallback_warnings
                + [
                    f"SDE indicated seeding by {', '.join(c[1] for c in seeding_corps)} "
                    f"but no orders found. ESI fallback discovered actual sources."
                ]
            )
            return NPCSourcesResult(
                type_id=type_id,
                type_name=type_name,
                found=True,
                sources=fallback_sources,
                total_orders=fallback_total,
                warnings=all_warnings,
            ).model_dump()
        else:
            # Neither SDE-based search nor ESI fallback found orders
            all_warnings = warnings + fallback_warnings
            return NPCSourcesResult(
                type_id=type_id,
                type_name=type_name,
                found=False,
                sources=[],
                total_orders=0,
                warnings=all_warnings,
            ).model_dump()

    return NPCSourcesResult(
        type_id=type_id,
        type_name=type_name,
        found=len(sources) > 0,
        sources=sources,
        total_orders=total_orders,
        warnings=warnings,
    ).model_dump()


# =============================================================================
# Tool Registration
# =============================================================================


def register_npc_tools(server: FastMCP) -> None:
    """Register NPC source discovery tools with MCP server."""

    @server.tool()
    async def market_npc_sources(item: str, limit: int = 10) -> dict:
        """
        Find NPC sources for an item.

        DEPRECATION NOTICE: Consider using `market_find_nearby` instead, which
        provides distance-based search, automatic NPC detection for blueprints,
        and multi-region search capabilities.

        Discovers where an item is NPC-seeded by:
        1. Looking up the item's NPC seeding corporations in SDE
        2. Mapping corporations to their home regions
        3. Querying those regions for orders with 364+ day duration (NPC signature)

        Useful for finding blueprint originals that aren't available
        at standard trade hubs.

        Args:
            item: Item name to look up (case-insensitive)
            limit: Maximum orders to return per source (default 10, max 50)

        Returns:
            NPCSourcesResult with NPC source locations and orders

        Examples:
            market_npc_sources("Pioneer Blueprint")
            market_npc_sources("Astero Blueprint")
        """
        return await _npc_sources_impl(item, limit)
