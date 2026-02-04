"""
SDE Item Info MCP Tool.

Provides detailed item information including classification,
description, and metadata from the EVE SDE.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aria_esi.core.logging import get_logger
from aria_esi.mcp.market.database import get_market_database
from aria_esi.models.sde import (
    CATEGORY_BLUEPRINT,
    ItemInfo,
    ItemInfoResult,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = get_logger("aria_sde.tools_item")


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
        db = get_market_database()
        conn = db._get_connection()

        # Normalize query
        query = item.strip()
        query_lower = query.lower()

        # Check if SDE tables exist
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='categories'"
        )
        if not cursor.fetchone():
            return ItemInfoResult(
                item=None,
                found=False,
                query=query,
                suggestions=[],
                warnings=["SDE data not seeded. Run 'aria-esi sde-seed' first."],
            ).model_dump()

        # Try exact match first
        item_data = _lookup_item(conn, query_lower, exact=True)

        if not item_data:
            # Try fuzzy match
            item_data = _lookup_item(conn, query_lower, exact=False)

        if item_data:
            # Check if this is a blueprint
            is_blueprint = False
            if item_data.get("category_id") == CATEGORY_BLUEPRINT:
                is_blueprint = True
            elif item_data.get("type_name", "").lower().endswith(" blueprint"):
                is_blueprint = True

            # Check if this is a skill (category_id = 16)
            skill_rank = None
            skill_primary = None
            skill_secondary = None
            skill_prereqs = None
            if item_data.get("category_id") == 16:  # CATEGORY_SKILL
                # Check if skill_attributes table exists
                skill_table_cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='skill_attributes'"
                )
                if skill_table_cursor.fetchone():
                    # Look up skill attributes
                    skill_cursor = conn.execute(
                        """
                        SELECT rank, primary_attribute, secondary_attribute
                        FROM skill_attributes
                        WHERE type_id = ?
                        """,
                        (item_data["type_id"],),
                    )
                    skill_row = skill_cursor.fetchone()
                    if skill_row:
                        skill_rank = skill_row[0]
                        skill_primary = skill_row[1]
                        skill_secondary = skill_row[2]

                    # Get skill prerequisites
                    from .queries import get_sde_query_service

                    query_service = get_sde_query_service()
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
        suggestions = _find_suggestions(conn, query_lower)

        return ItemInfoResult(
            item=None,
            found=False,
            query=query,
            suggestions=suggestions,
            warnings=[f"Item '{query}' not found in SDE."],
        ).model_dump()


def _lookup_item(conn, query_lower: str, exact: bool = True) -> dict | None:
    """
    Look up item by name with optional fuzzy matching.

    Args:
        conn: SQLite connection
        query_lower: Lowercase search query
        exact: If True, only exact match; if False, allow prefix/contains

    Returns:
        Dict with item data or None
    """
    if exact:
        # Exact case-insensitive match
        cursor = conn.execute(
            """
            SELECT
                t.type_id,
                t.type_name,
                t.description,
                t.group_id,
                t.category_id,
                t.market_group_id,
                t.volume,
                t.packaged_volume,
                t.published,
                g.group_name,
                c.category_name
            FROM types t
            LEFT JOIN groups g ON t.group_id = g.group_id
            LEFT JOIN categories c ON t.category_id = c.category_id
            WHERE t.type_name_lower = ?
            LIMIT 1
            """,
            (query_lower,),
        )
    else:
        # Prefix match first
        cursor = conn.execute(
            """
            SELECT
                t.type_id,
                t.type_name,
                t.description,
                t.group_id,
                t.category_id,
                t.market_group_id,
                t.volume,
                t.packaged_volume,
                t.published,
                g.group_name,
                c.category_name
            FROM types t
            LEFT JOIN groups g ON t.group_id = g.group_id
            LEFT JOIN categories c ON t.category_id = c.category_id
            WHERE t.type_name_lower LIKE ?
            AND t.published = 1
            ORDER BY length(t.type_name)
            LIMIT 1
            """,
            (f"{query_lower}%",),
        )

    row = cursor.fetchone()

    if not row and not exact:
        # Try contains match
        cursor = conn.execute(
            """
            SELECT
                t.type_id,
                t.type_name,
                t.description,
                t.group_id,
                t.category_id,
                t.market_group_id,
                t.volume,
                t.packaged_volume,
                t.published,
                g.group_name,
                c.category_name
            FROM types t
            LEFT JOIN groups g ON t.group_id = g.group_id
            LEFT JOIN categories c ON t.category_id = c.category_id
            WHERE t.type_name_lower LIKE ?
            AND t.published = 1
            ORDER BY length(t.type_name)
            LIMIT 1
            """,
            (f"%{query_lower}%",),
        )
        row = cursor.fetchone()

    if row:
        return {
            "type_id": row[0],
            "type_name": row[1],
            "description": row[2],
            "group_id": row[3],
            "category_id": row[4],
            "market_group_id": row[5],
            "volume": row[6],
            "packaged_volume": row[7],
            "published": row[8],
            "group_name": row[9],
            "category_name": row[10],
        }

    return None


def _find_suggestions(conn, query_lower: str, limit: int = 5) -> list[str]:
    """Find similar item names for suggestions."""
    suggestions = []

    # Prefix matches
    cursor = conn.execute(
        """
        SELECT type_name FROM types
        WHERE type_name_lower LIKE ?
        AND published = 1
        ORDER BY length(type_name)
        LIMIT ?
        """,
        (f"{query_lower}%", limit),
    )
    suggestions.extend(row[0] for row in cursor.fetchall())

    if len(suggestions) < limit:
        # Contains matches
        remaining = limit - len(suggestions)
        cursor = conn.execute(
            """
            SELECT type_name FROM types
            WHERE type_name_lower LIKE ?
            AND type_name_lower NOT LIKE ?
            AND published = 1
            ORDER BY length(type_name)
            LIMIT ?
            """,
            (f"%{query_lower}%", f"{query_lower}%", remaining),
        )
        suggestions.extend(row[0] for row in cursor.fetchall())

    return suggestions
