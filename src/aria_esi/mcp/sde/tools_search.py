"""
SDE Search and Status MCP Tools.

Provides item search and SDE database status tools.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aria_esi.core.logging import get_logger
from aria_esi.mcp.market.database import get_market_database
from aria_esi.models.sde import (
    CATEGORY_BLUEPRINT,
    SDESearchResult,
    SDEStatusResult,
    SearchResultItem,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = get_logger("aria_sde.tools_search")


# =============================================================================
# Standalone Implementation Functions (for dispatcher imports)
# =============================================================================


async def _search_impl(
    query: str,
    category: str | None = None,
    limit: int = 10,
) -> dict:
    """
    Search for items by name with optional category filter.

    Standalone implementation callable by both MCP tool and dispatcher.

    Args:
        query: Search term (partial name, case-insensitive)
        category: Optional category filter (e.g., "Ship", "Module", "Blueprint")
        limit: Maximum results (default 10, max 50)

    Returns:
        SDESearchResult with matching items
    """
    db = get_market_database()
    conn = db._get_connection()

    # Normalize inputs
    query = query.strip()
    query_lower = query.lower()
    limit = min(max(1, limit), 50)  # Clamp to 1-50

    # Check if SDE tables exist
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='categories'")
    if not cursor.fetchone():
        return SDESearchResult(
            items=[],
            total_found=0,
            query=query,
            category_filter=category,
            limit=limit,
            warnings=["SDE data not seeded. Run 'aria-esi sde-seed' first."],
        ).model_dump()

    # Build query based on filters
    if category:
        category_lower = category.lower()
        cursor = conn.execute(
            """
            SELECT
                t.type_id,
                t.type_name,
                g.group_name,
                c.category_name,
                t.category_id
            FROM types t
            LEFT JOIN groups g ON t.group_id = g.group_id
            LEFT JOIN categories c ON t.category_id = c.category_id
            WHERE t.type_name_lower LIKE ?
            AND c.category_name_lower = ?
            AND t.published = 1
            ORDER BY length(t.type_name), t.type_name
            LIMIT ?
            """,
            (f"%{query_lower}%", category_lower, limit),
        )
    else:
        cursor = conn.execute(
            """
            SELECT
                t.type_id,
                t.type_name,
                g.group_name,
                c.category_name,
                t.category_id
            FROM types t
            LEFT JOIN groups g ON t.group_id = g.group_id
            LEFT JOIN categories c ON t.category_id = c.category_id
            WHERE t.type_name_lower LIKE ?
            AND t.published = 1
            ORDER BY length(t.type_name), t.type_name
            LIMIT ?
            """,
            (f"%{query_lower}%", limit),
        )

    items = []
    for row in cursor.fetchall():
        is_blueprint = row[4] == CATEGORY_BLUEPRINT or (
            row[1] and row[1].lower().endswith(" blueprint")
        )
        items.append(
            SearchResultItem(
                type_id=row[0],
                type_name=row[1],
                group_name=row[2],
                category_name=row[3],
                is_blueprint=is_blueprint,
            )
        )

    # Get total count (without limit) for informational purposes
    if category:
        count_cursor = conn.execute(
            """
            SELECT COUNT(*)
            FROM types t
            LEFT JOIN categories c ON t.category_id = c.category_id
            WHERE t.type_name_lower LIKE ?
            AND c.category_name_lower = ?
            AND t.published = 1
            """,
            (f"%{query_lower}%", category.lower()),
        )
    else:
        count_cursor = conn.execute(
            """
            SELECT COUNT(*)
            FROM types t
            WHERE t.type_name_lower LIKE ?
            AND t.published = 1
            """,
            (f"%{query_lower}%",),
        )

    total_found = count_cursor.fetchone()[0]

    warnings = []
    if total_found > limit:
        warnings.append(
            f"Showing {limit} of {total_found} matching items. Increase limit for more."
        )

    return SDESearchResult(
        items=items,
        total_found=total_found,
        query=query,
        category_filter=category,
        limit=limit,
        warnings=warnings,
    ).model_dump()


# =============================================================================
# MCP Tool Registration
# =============================================================================


def register_search_tools(server: FastMCP) -> None:
    """Register SDE search tools with MCP server."""

    @server.tool()
    async def sde_search(
        query: str,
        category: str | None = None,
        limit: int = 10,
    ) -> dict:
        """
        Search for items by name with optional category filter.

        Useful for finding items when you only know part of the name
        or want to see all items in a category.

        Args:
            query: Search term (partial name, case-insensitive)
            category: Optional category filter (e.g., "Ship", "Module", "Blueprint")
            limit: Maximum results (default 10, max 50)

        Returns:
            SDESearchResult with matching items

        Examples:
            sde_search("venture")  # All items containing "venture"
            sde_search("veldspar", category="Asteroid")  # Ores only
            sde_search("mining", category="Ship", limit=20)
        """
        return await _search_impl(query, category, limit)

    @server.tool()
    async def sde_cache_status() -> dict:
        """
        Get SDE database status and version info.

        Returns information about the imported SDE data including
        table counts, version, and last import timestamp.

        Returns:
            SDEStatusResult with database statistics
        """
        db = get_market_database()
        conn = db._get_connection()

        # Check if SDE tables exist
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('groups', 'categories', 'blueprints')"
        )
        tables = [row[0] for row in cursor.fetchall()]

        if len(tables) < 3:
            return SDEStatusResult(
                seeded=False,
                database_path=str(db.db_path),
                database_size_mb=round(db.db_path.stat().st_size / (1024 * 1024), 2)
                if db.db_path.exists()
                else 0,
            ).model_dump()

        # Get counts
        try:
            category_count = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
            group_count = conn.execute("SELECT COUNT(*) FROM groups").fetchone()[0]
            type_count = conn.execute("SELECT COUNT(*) FROM types WHERE published = 1").fetchone()[
                0
            ]
            blueprint_count = conn.execute("SELECT COUNT(*) FROM blueprints").fetchone()[0]
            seeding_count = conn.execute("SELECT COUNT(*) FROM npc_seeding").fetchone()[0]
            corp_count = conn.execute("SELECT COUNT(*) FROM npc_corporations").fetchone()[0]
        except Exception:
            return SDEStatusResult(seeded=False).model_dump()

        # Get metadata
        sde_version = None
        import_timestamp = None
        try:
            version_row = conn.execute(
                "SELECT value FROM metadata WHERE key = 'sde_schema_version'"
            ).fetchone()
            timestamp_row = conn.execute(
                "SELECT value FROM metadata WHERE key = 'sde_import_timestamp'"
            ).fetchone()
            sde_version = version_row[0] if version_row else None
            import_timestamp = timestamp_row[0] if timestamp_row else None
        except Exception:
            pass

        return SDEStatusResult(
            seeded=blueprint_count > 0,
            category_count=category_count,
            group_count=group_count,
            type_count=type_count,
            blueprint_count=blueprint_count,
            npc_seeding_count=seeding_count,
            npc_corporation_count=corp_count,
            sde_version=sde_version,
            import_timestamp=import_timestamp,
            database_path=str(db.db_path),
            database_size_mb=round(db.db_path.stat().st_size / (1024 * 1024), 2)
            if db.db_path.exists()
            else 0,
        ).model_dump()
