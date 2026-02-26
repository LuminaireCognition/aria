"""
SDE Item Info MCP Tool.

Provides detailed item information including classification,
description, and metadata from the EVE SDE.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aria_esi.core.logging import get_logger
from aria_esi.models.sde import (
    CATEGORY_BLUEPRINT,
    ItemInfo,
    ItemInfoResult,
    MetaVariantInfo,
    MetaVariantsResult,
)

from .queries import get_sde_query_service

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = get_logger("aria_sde.tools_item")


# =============================================================================
# Standalone Implementation Functions (for dispatcher imports)
# =============================================================================


async def _item_info_impl(item: str) -> dict:
    """
    Get detailed item information from the SDE.

    Standalone implementation callable by both MCP tool and dispatcher.

    Args:
        item: Item name (case-insensitive, fuzzy match supported)

    Returns:
        ItemInfoResult dict
    """
    query_service = get_sde_query_service()
    query = item.strip()

    if not query_service.has_table("categories"):
        return ItemInfoResult(
            item=None,
            found=False,
            query=query,
            suggestions=[],
            warnings=["SDE data not seeded. Run 'aria-esi sde-seed' first."],
        ).model_dump()

    # Try exact match first, then fuzzy
    item_data = query_service.lookup_item(query, exact=True)
    if not item_data:
        item_data = query_service.lookup_item(query, exact=False)

    if item_data:
        is_blueprint = item_data.get("category_id") == CATEGORY_BLUEPRINT or item_data.get(
            "type_name", ""
        ).lower().endswith(" blueprint")

        skill_rank = None
        skill_primary = None
        skill_secondary = None
        skill_prereqs = None

        if item_data.get("category_id") == 16:  # CATEGORY_SKILL
            attrs = query_service.get_skill_attributes(item_data["type_id"])
            if attrs:
                skill_rank = attrs.rank
                skill_primary = attrs.primary_attribute
                skill_secondary = attrs.secondary_attribute

            prereqs = query_service.get_skill_prerequisites(item_data["type_id"])
            if prereqs:
                skill_prereqs = [
                    {
                        "skill_id": p.skill_id,
                        "skill_name": p.skill_name,
                        "level": p.required_level,
                    }
                    for p in prereqs
                ]

        result_item = ItemInfo(
            type_id=item_data["type_id"],
            type_name=item_data["type_name"],
            description=item_data.get("description"),
            group_id=item_data.get("group_id"),
            group_name=item_data.get("group_name"),
            category_id=item_data.get("category_id"),
            category_name=item_data.get("category_name"),
            market_group_id=item_data.get("market_group_id"),
            volume=item_data.get("volume"),
            packaged_volume=item_data.get("packaged_volume"),
            is_published=bool(item_data.get("published", 1)),
            is_blueprint=is_blueprint,
            skill_rank=skill_rank,
            skill_primary_attribute=skill_primary,
            skill_secondary_attribute=skill_secondary,
            skill_prerequisites=skill_prereqs,
        )

        return ItemInfoResult(
            item=result_item,
            found=True,
            query=query,
            suggestions=[],
            warnings=[],
        ).model_dump()

    # Not found - get suggestions
    suggestions = query_service.find_item_suggestions(query)

    return ItemInfoResult(
        item=None,
        found=False,
        query=query,
        suggestions=suggestions,
        warnings=[f"Item '{query}' not found in SDE."],
    ).model_dump()


async def _meta_variants_impl(item: str) -> dict:
    """
    Get all meta variants (T2/Faction/Officer) of an item.

    Standalone implementation callable by both MCP tool and dispatcher.

    Args:
        item: Item name (any variant or base item)

    Returns:
        MetaVariantsResult dict
    """
    query_service = get_sde_query_service()
    query = item.strip()

    if not query_service.has_table("meta_types"):
        return MetaVariantsResult(
            query=query,
            query_type_id=0,
            found=False,
            warnings=["Meta type data not imported. Run 'aria-esi sde-seed' to update SDE."],
        ).model_dump()

    # Look up the queried item
    item_data = query_service.lookup_item(query, exact=True)
    if not item_data:
        item_data = query_service.lookup_item(query, exact=False)

    if not item_data:
        return MetaVariantsResult(
            query=query,
            query_type_id=0,
            found=False,
            warnings=[f"Item '{query}' not found in SDE."],
        ).model_dump()

    type_id = item_data["type_id"]

    # Get variants
    variants = query_service.get_meta_variants(type_id)

    # Determine parent
    parent_id = query_service._get_parent_type_id(type_id)
    parent_name = None

    if parent_id:
        # Queried item is a variant, look up parent name
        parent_name = query_service.get_type_name(parent_id)
    elif variants:
        # Queried item is the parent
        parent_id = type_id
        parent_name = item_data["type_name"]

    variant_list = [
        MetaVariantInfo(
            type_id=v.type_id,
            type_name=v.type_name,
            meta_group_id=v.meta_group_id,
            meta_group_name=v.meta_group_name,
        )
        for v in variants
    ]

    return MetaVariantsResult(
        query=query,
        query_type_id=type_id,
        parent_type_id=parent_id,
        parent_type_name=parent_name,
        found=True,
        variants=variant_list,
        total_variants=len(variant_list),
        warnings=[] if variants else ["No meta variants found for this item."],
    ).model_dump()


# =============================================================================
# MCP Tool Registration
# =============================================================================


def register_item_tools(server: FastMCP) -> None:
    """Register SDE item lookup tools with MCP server."""

    @server.tool()
    async def sde_item_info(item: str) -> dict:
        """
        Get detailed item information from the EVE Static Data Export.

        PREFER THIS TOOL for authoritative item data. Provides:
        - Full item classification (category, group)
        - Item description
        - Volume and market info
        - Blueprint detection

        Args:
            item: Item name to look up (case-insensitive, fuzzy match supported)

        Returns:
            ItemInfoResult with item details or suggestions if not found

        Examples:
            sde_item_info("Pioneer")  # ORE Expedition Frigate
            sde_item_info("Tritanium")  # Mineral
            sde_item_info("Venture Blueprint")  # Blueprint item
        """
        return await _item_info_impl(item)
