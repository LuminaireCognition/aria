"""
SDE Blueprint Info MCP Tool.

Provides blueprint information including manufacturing data,
materials, and where to acquire BPOs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from aria_esi.core.logging import get_logger
from aria_esi.mcp.market.database import get_market_database
from aria_esi.mcp.sde.queries import SDENotSeededError, get_sde_query_service
from aria_esi.models.sde import (
    BlueprintInfo,
    BlueprintInfoResult,
    BlueprintMaterial,
    BlueprintSource,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = get_logger("aria_sde.tools_blueprint")


# =============================================================================
# Standalone Implementation Functions (for dispatcher imports)
# =============================================================================


async def _blueprint_info_impl(item: str) -> dict:
    """
    Get blueprint information for an item.

    Standalone implementation callable by both MCP tool and dispatcher.

    Args:
        item: Product name (e.g., "Pioneer") or blueprint name (e.g., "Pioneer Blueprint")

    Returns:
        BlueprintInfoResult with blueprint details or suggestions
    """
    db = get_market_database()
    conn = db._get_connection()

    # Normalize query
    query = item.strip()
    query_lower = query.lower()

    # Check if SDE tables exist
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='blueprints'")
    if not cursor.fetchone():
        return BlueprintInfoResult(
            blueprint=None,
            found=False,
            query=query,
            searched_as="product",
            suggestions=[],
            warnings=["SDE data not seeded. Run 'aria-esi sde-seed' first."],
        ).model_dump()

    # First, try to find as a product name
    blueprint_data = _lookup_blueprint_by_product(conn, query_lower)
    searched_as: Literal["product", "blueprint"] = "product"

    if not blueprint_data:
        # Try as blueprint name
        blueprint_data = _lookup_blueprint_by_name(conn, query_lower)
        if blueprint_data:
            searched_as = "blueprint"

    if blueprint_data:
        # Get materials
        materials = _get_blueprint_materials(conn, blueprint_data["blueprint_type_id"])

        # Get sources (where to acquire)
        sources = _get_blueprint_sources(conn, blueprint_data["blueprint_type_id"])

        result = BlueprintInfo(
            blueprint_type_id=blueprint_data["blueprint_type_id"],
            blueprint_name=blueprint_data["blueprint_name"],
            product_type_id=blueprint_data["product_type_id"],
            product_name=blueprint_data["product_name"],
            product_quantity=blueprint_data.get("product_quantity", 1),
            manufacturing_time=blueprint_data.get("manufacturing_time"),
            copying_time=blueprint_data.get("copying_time"),
            research_me_time=blueprint_data.get("research_material_time"),
            research_te_time=blueprint_data.get("research_time_time"),
            invention_time=blueprint_data.get("invention_time"),
            max_production_limit=blueprint_data.get("max_production_limit", 1),
            materials=materials,
            sources=sources,
        )

        return BlueprintInfoResult(
            blueprint=result,
            found=True,
            query=query,
            searched_as=searched_as,
            suggestions=[],
            warnings=[],
        ).model_dump()

    # Not found - check if item exists but has no blueprint
    warnings = []
    item_exists = _check_item_exists(conn, query_lower)
    if item_exists:
        warnings.append(
            f"'{item_exists}' exists but has no associated blueprint. "
            "It may be acquired through other means (loot, LP store, etc.)."
        )

    # Get suggestions
    suggestions = _find_blueprint_suggestions(conn, query_lower)

    return BlueprintInfoResult(
        blueprint=None,
        found=False,
        query=query,
        searched_as=searched_as,
        suggestions=suggestions,
        warnings=warnings,
    ).model_dump()


# =============================================================================
# MCP Tool Registration
# =============================================================================


def register_blueprint_tools(server: FastMCP) -> None:
    """Register SDE blueprint lookup tools with MCP server."""

    @server.tool()
    async def sde_blueprint_info(item: str) -> dict:
        """
        Get blueprint information for an item.

        Searches by product name or blueprint name. Returns manufacturing
        data, materials, and where to acquire the blueprint.

        PREFER THIS TOOL when users ask "where can I buy X blueprint" or
        "how do I make X". Provides authoritative SDE data.

        Args:
            item: Product name (e.g., "Pioneer") or blueprint name (e.g., "Pioneer Blueprint")

        Returns:
            BlueprintInfoResult with blueprint details or suggestions

        Examples:
            sde_blueprint_info("Pioneer")  # Search by product name
            sde_blueprint_info("Venture Blueprint")  # Search by blueprint name
            sde_blueprint_info("Tritanium")  # No blueprint (mineral)
        """
        return await _blueprint_info_impl(item)


def _lookup_blueprint_by_product(conn, query_lower: str) -> dict | None:
    """Look up blueprint by product name."""
    # Exact match on product name
    cursor = conn.execute(
        """
        SELECT
            bp.type_id as blueprint_type_id,
            bp_type.type_name as blueprint_name,
            bpp.product_type_id,
            prod_type.type_name as product_name,
            bpp.quantity as product_quantity,
            bp.manufacturing_time,
            bp.copying_time,
            bp.research_material_time,
            bp.research_time_time,
            bp.invention_time,
            bp.max_production_limit
        FROM blueprints bp
        JOIN blueprint_products bpp ON bp.type_id = bpp.blueprint_type_id
        JOIN types bp_type ON bp.type_id = bp_type.type_id
        JOIN types prod_type ON bpp.product_type_id = prod_type.type_id
        WHERE prod_type.type_name_lower = ?
        LIMIT 1
        """,
        (query_lower,),
    )

    row = cursor.fetchone()
    if not row:
        # Try prefix match
        cursor = conn.execute(
            """
            SELECT
                bp.type_id as blueprint_type_id,
                bp_type.type_name as blueprint_name,
                bpp.product_type_id,
                prod_type.type_name as product_name,
                bpp.quantity as product_quantity,
                bp.manufacturing_time,
                bp.copying_time,
                bp.research_material_time,
                bp.research_time_time,
                bp.invention_time,
                bp.max_production_limit
            FROM blueprints bp
            JOIN blueprint_products bpp ON bp.type_id = bpp.blueprint_type_id
            JOIN types bp_type ON bp.type_id = bp_type.type_id
            JOIN types prod_type ON bpp.product_type_id = prod_type.type_id
            WHERE prod_type.type_name_lower LIKE ?
            AND prod_type.published = 1
            ORDER BY length(prod_type.type_name)
            LIMIT 1
            """,
            (f"{query_lower}%",),
        )
        row = cursor.fetchone()

    if row:
        return {
            "blueprint_type_id": row[0],
            "blueprint_name": row[1],
            "product_type_id": row[2],
            "product_name": row[3],
            "product_quantity": row[4],
            "manufacturing_time": row[5],
            "copying_time": row[6],
            "research_material_time": row[7],
            "research_time_time": row[8],
            "invention_time": row[9],
            "max_production_limit": row[10],
        }

    return None


def _lookup_blueprint_by_name(conn, query_lower: str) -> dict | None:
    """Look up blueprint by blueprint item name."""
    # Handle "X Blueprint" -> look for blueprint directly
    if not query_lower.endswith(" blueprint"):
        query_lower = query_lower + " blueprint"

    cursor = conn.execute(
        """
        SELECT
            bp.type_id as blueprint_type_id,
            bp_type.type_name as blueprint_name,
            bpp.product_type_id,
            prod_type.type_name as product_name,
            bpp.quantity as product_quantity,
            bp.manufacturing_time,
            bp.copying_time,
            bp.research_material_time,
            bp.research_time_time,
            bp.invention_time,
            bp.max_production_limit
        FROM blueprints bp
        JOIN blueprint_products bpp ON bp.type_id = bpp.blueprint_type_id
        JOIN types bp_type ON bp.type_id = bp_type.type_id
        JOIN types prod_type ON bpp.product_type_id = prod_type.type_id
        WHERE bp_type.type_name_lower = ?
        LIMIT 1
        """,
        (query_lower,),
    )

    row = cursor.fetchone()
    if row:
        return {
            "blueprint_type_id": row[0],
            "blueprint_name": row[1],
            "product_type_id": row[2],
            "product_name": row[3],
            "product_quantity": row[4],
            "manufacturing_time": row[5],
            "copying_time": row[6],
            "research_material_time": row[7],
            "research_time_time": row[8],
            "invention_time": row[9],
            "max_production_limit": row[10],
        }

    return None


def _get_blueprint_materials(conn, blueprint_type_id: int) -> list[BlueprintMaterial]:
    """Get manufacturing materials for a blueprint."""
    cursor = conn.execute(
        """
        SELECT
            bm.material_type_id,
            t.type_name,
            bm.quantity
        FROM blueprint_materials bm
        JOIN types t ON bm.material_type_id = t.type_id
        WHERE bm.blueprint_type_id = ?
        ORDER BY bm.quantity DESC
        """,
        (blueprint_type_id,),
    )

    return [
        BlueprintMaterial(
            type_id=row[0],
            type_name=row[1],
            quantity=row[2],
        )
        for row in cursor.fetchall()
    ]


def _get_blueprint_sources(conn, blueprint_type_id: int) -> list[BlueprintSource]:
    """Get sources where blueprint can be acquired."""
    sources = []

    # Check NPC seeding
    cursor = conn.execute(
        """
        SELECT
            ns.corporation_id,
            nc.corporation_name
        FROM npc_seeding ns
        JOIN npc_corporations nc ON ns.corporation_id = nc.corporation_id
        WHERE ns.type_id = ?
        """,
        (blueprint_type_id,),
    )

    # Get the query service for dynamic region lookups
    try:
        query_service = get_sde_query_service()
    except Exception:
        query_service = None

    for row in cursor.fetchall():
        corp_id = row[0]
        corp_name = row[1]

        # Look up region dynamically from database
        region = None
        region_id = None
        suggested_regions = None

        if query_service:
            try:
                corp_regions = query_service.get_corporation_regions(corp_id)
                if corp_regions and corp_regions.regions:
                    region_id = corp_regions.primary_region_id
                    region = corp_regions.primary_region_name
                    # Convert to list of (region_id, region_name) tuples for compatibility
                    suggested_regions = [(r[0], r[1]) for r in corp_regions.regions]
            except SDENotSeededError:
                pass  # Fall back to None values

        sources.append(
            BlueprintSource(
                source_type="npc",
                corporation_id=corp_id,
                corporation_name=corp_name,
                region=region,
                region_id=region_id,
                suggested_regions=suggested_regions,
                notes=f"Seeded at {corp_name} stations",
            )
        )

    # If no NPC seeding found, check if it's likely a loot/invention item
    if not sources:
        # Check the blueprint's group to infer acquisition method
        cursor = conn.execute(
            """
            SELECT g.group_name, c.category_name
            FROM types t
            JOIN groups g ON t.group_id = g.group_id
            JOIN categories c ON t.category_id = c.category_id
            WHERE t.type_id = ?
            """,
            (blueprint_type_id,),
        )
        row = cursor.fetchone()

        if row:
            group_name = row[0] or ""
            group_lower = group_name.lower()

            # T2 items require invention
            if "ii" in group_lower or "tech ii" in group_lower:
                sources.append(
                    BlueprintSource(
                        source_type="invention",
                        notes="Tech II blueprint - obtained through invention",
                    )
                )
            # Faction/pirate items are usually loot
            elif any(
                x in group_lower for x in ["faction", "pirate", "storyline", "deadspace", "officer"]
            ):
                sources.append(
                    BlueprintSource(
                        source_type="loot",
                        notes="Faction item - BPC obtained as loot from NPCs or LP stores",
                    )
                )

    return sources


def _check_item_exists(conn, query_lower: str) -> str | None:
    """Check if an item exists by name, return its name if found."""
    cursor = conn.execute(
        """
        SELECT type_name FROM types
        WHERE type_name_lower = ?
        OR type_name_lower LIKE ?
        LIMIT 1
        """,
        (query_lower, f"{query_lower}%"),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def _find_blueprint_suggestions(conn, query_lower: str, limit: int = 5) -> list[str]:
    """Find similar product names that have blueprints."""
    suggestions = []

    cursor = conn.execute(
        """
        SELECT DISTINCT prod_type.type_name
        FROM blueprint_products bpp
        JOIN types prod_type ON bpp.product_type_id = prod_type.type_id
        WHERE prod_type.type_name_lower LIKE ?
        AND prod_type.published = 1
        ORDER BY length(prod_type.type_name)
        LIMIT ?
        """,
        (f"%{query_lower}%", limit),
    )

    suggestions.extend(row[0] for row in cursor.fetchall())
    return suggestions
