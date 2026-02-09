"""
ARIA ESI SDE Commands

Static Data Export management commands for downloading and querying
EVE game data (items, blueprints, NPC seeding).

Includes:
- sde-seed: Download and import SDE from Fuzzwork
- sde-status: Show SDE database status
- sde-item: Look up item information
- sde-blueprint: Look up blueprint information
"""

import argparse
import sys

from ..core import get_utc_timestamp

# =============================================================================
# SDE Seed Command
# =============================================================================


def cmd_sde_seed(args: argparse.Namespace) -> dict:
    """
    Download and import SDE data from Fuzzwork.

    Downloads the complete Fuzzwork SQLite conversion of the EVE SDE
    and imports categories, groups, types, blueprints, and NPC seeding.

    Args:
        args: Parsed arguments (--check for update check only)

    Returns:
        Import status with row counts
    """
    query_ts = get_utc_timestamp()

    try:
        from ..mcp.market.database import MarketDatabase
        from ..mcp.sde.importer import SDEImporter, seed_sde
    except ImportError as e:
        return {
            "error": "import_error",
            "message": f"Failed to import SDE modules: {e}",
            "hint": "Ensure httpx is installed: uv pip install httpx",
            "query_timestamp": query_ts,
        }

    # Check-only mode
    if getattr(args, "check", False):
        print("Checking SDE status...", file=sys.stderr)
        db = MarketDatabase()
        importer = SDEImporter(db)
        status = importer.get_sde_status()
        db.close()

        if status.seeded:
            return {
                "status": "seeded",
                "blueprint_count": status.blueprint_count,
                "type_count": status.type_count,
                "import_timestamp": status.import_timestamp,
                "needs_update": False,  # TODO: Check Fuzzwork for newer version
                "query_timestamp": query_ts,
            }
        else:
            return {
                "status": "not_seeded",
                "message": "SDE data not yet imported",
                "hint": "Run 'aria-esi sde-seed' to download and import",
                "query_timestamp": query_ts,
            }

    # Get flag values
    break_glass = getattr(args, "break_glass_latest", False)
    show_checksum = getattr(args, "show_checksum", False)

    # Full import
    print("Starting SDE import from Fuzzwork...", file=sys.stderr)
    print("This downloads ~100MB and may take a few minutes.", file=sys.stderr)

    if break_glass:
        print("WARNING: Break-glass mode enabled, skipping checksum verification", file=sys.stderr)

    def progress_callback(step: str | int, count: int | None) -> None:
        if isinstance(step, str):
            if count:
                print(f"  {step}: {count:,} rows", file=sys.stderr)
            else:
                print(f"  {step}...", file=sys.stderr)
        else:
            # Download progress (bytes)
            if count and count > 0:
                pct = int((step / count) * 100)
                mb = step / (1024 * 1024)
                print(f"\r  Downloading: {mb:.1f} MB ({pct}%)", end="", file=sys.stderr)

    try:
        db = MarketDatabase()
        result = seed_sde(
            db, progress_callback, break_glass=break_glass, show_checksum=show_checksum
        )
        db.close()
    except Exception as e:
        error_type = type(e).__name__
        return {
            "error": "seed_error",
            "error_type": error_type,
            "message": f"Failed to seed SDE: {e}",
            "query_timestamp": query_ts,
        }

    print("", file=sys.stderr)  # Newline after progress

    if result.success:
        # Get the checksum from the database status
        try:
            db = MarketDatabase()
            importer = SDEImporter(db)
            status = importer.get_sde_status()
            source_checksum = status.source_checksum
            db.close()
        except Exception:
            source_checksum = None

        if show_checksum and source_checksum:
            print(f"\nSDE SHA256 checksum: {source_checksum}", file=sys.stderr)

        response = {
            "status": "success",
            "categories_imported": result.categories_imported,
            "groups_imported": result.groups_imported,
            "types_imported": result.types_imported,
            "blueprints_imported": result.blueprints_imported,
            "blueprint_products_imported": result.blueprint_products_imported,
            "blueprint_materials_imported": result.blueprint_materials_imported,
            "npc_corporations_imported": result.npc_corporations_imported,
            "npc_seeding_imported": result.npc_seeding_imported,
            "download_time_seconds": round(result.download_time_seconds, 1),
            "import_time_seconds": round(result.import_time_seconds, 1),
            "source": "fuzzwork_sqlite",
            "query_timestamp": query_ts,
        }
        if source_checksum:
            response["source_checksum"] = source_checksum
        return response
    else:
        return {
            "error": "import_error",
            "message": result.error or "Unknown error during import",
            "query_timestamp": query_ts,
        }


# =============================================================================
# SDE Status Command
# =============================================================================


def cmd_sde_status(args: argparse.Namespace) -> dict:
    """
    Show SDE database status and statistics.

    Args:
        args: Parsed arguments (currently no options)

    Returns:
        Database statistics
    """
    query_ts = get_utc_timestamp()

    try:
        from ..mcp.market.database import MarketDatabase
        from ..mcp.sde.importer import SDEImporter
    except ImportError as e:
        return {
            "error": "import_error",
            "message": f"Failed to import SDE modules: {e}",
            "query_timestamp": query_ts,
        }

    try:
        db = MarketDatabase()
        importer = SDEImporter(db)
        status = importer.get_sde_status()
        db_stats = db.get_stats()
        db.close()
    except Exception as e:
        return {
            "error": "database_error",
            "message": f"Failed to read database: {e}",
            "query_timestamp": query_ts,
        }

    if not status.seeded:
        return {
            "status": "not_seeded",
            "message": "SDE data not yet imported",
            "hint": "Run 'aria-esi sde-seed' to download and import",
            "database_path": db_stats.get("database_path"),
            "query_timestamp": query_ts,
        }

    response = {
        "status": "ok",
        "seeded": True,
        "category_count": status.category_count,
        "group_count": status.group_count,
        "type_count": status.type_count,
        "blueprint_count": status.blueprint_count,
        "npc_seeding_count": status.npc_seeding_count,
        "npc_corporation_count": status.npc_corp_count,
        "sde_version": status.sde_version,
        "import_timestamp": status.import_timestamp,
        "database_path": db_stats.get("database_path"),
        "database_size_mb": round(db_stats.get("database_size_mb", 0), 2),
        "query_timestamp": query_ts,
    }
    if status.source_checksum:
        response["source_checksum"] = status.source_checksum
    return response


# =============================================================================
# SDE Item Lookup Command
# =============================================================================


def cmd_sde_item(args: argparse.Namespace) -> dict:
    """
    Look up item information from SDE.

    Args:
        args: Parsed arguments with item_name

    Returns:
        Item information or error
    """
    query_ts = get_utc_timestamp()
    item_name = " ".join(args.item_name) if isinstance(args.item_name, list) else args.item_name

    try:
        from ..mcp.market.database import MarketDatabase
        from ..models.sde import CATEGORY_BLUEPRINT
    except ImportError as e:
        return {
            "error": "import_error",
            "message": f"Failed to import SDE modules: {e}",
            "query_timestamp": query_ts,
        }

    try:
        db = MarketDatabase()
        conn = db._get_connection()

        # Check if SDE is seeded
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='categories'"
        )
        if not cursor.fetchone():
            db.close()
            return {
                "error": "not_seeded",
                "message": "SDE data not yet imported",
                "hint": "Run 'aria-esi sde-seed' first",
                "query_timestamp": query_ts,
            }

        query_lower = item_name.strip().lower()

        # Look up item with full details
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
            OR t.type_name_lower LIKE ?
            ORDER BY CASE WHEN t.type_name_lower = ? THEN 0 ELSE 1 END, length(t.type_name)
            LIMIT 1
            """,
            (query_lower, f"{query_lower}%", query_lower),
        )

        row = cursor.fetchone()
        db.close()

        if row:
            is_blueprint = row[4] == CATEGORY_BLUEPRINT or (
                row[1] and row[1].lower().endswith(" blueprint")
            )

            return {
                "found": True,
                "item": {
                    "type_id": row[0],
                    "type_name": row[1],
                    "description": row[2],
                    "group_id": row[3],
                    "group_name": row[9],
                    "category_id": row[4],
                    "category_name": row[10],
                    "market_group_id": row[5],
                    "volume": row[6],
                    "packaged_volume": row[7],
                    "published": bool(row[8]),
                    "is_blueprint": is_blueprint,
                },
                "query": item_name,
                "query_timestamp": query_ts,
            }
        else:
            return {
                "found": False,
                "message": f"Item '{item_name}' not found",
                "query": item_name,
                "query_timestamp": query_ts,
            }

    except Exception as e:
        return {
            "error": "lookup_error",
            "message": f"Failed to look up item: {e}",
            "query_timestamp": query_ts,
        }


# =============================================================================
# SDE Blueprint Lookup Command
# =============================================================================


def cmd_sde_blueprint(args: argparse.Namespace) -> dict:
    """
    Look up blueprint information from SDE.

    Args:
        args: Parsed arguments with item_name (product or blueprint name)

    Returns:
        Blueprint information including where to acquire
    """
    query_ts = get_utc_timestamp()
    item_name = " ".join(args.item_name) if isinstance(args.item_name, list) else args.item_name

    try:
        from ..mcp.market.database import MarketDatabase
    except ImportError as e:
        return {
            "error": "import_error",
            "message": f"Failed to import SDE modules: {e}",
            "query_timestamp": query_ts,
        }

    try:
        db = MarketDatabase()
        conn = db._get_connection()

        # Check if SDE is seeded
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='blueprints'"
        )
        if not cursor.fetchone():
            db.close()
            return {
                "error": "not_seeded",
                "message": "SDE data not yet imported",
                "hint": "Run 'aria-esi sde-seed' first",
                "query_timestamp": query_ts,
            }

        query_lower = item_name.strip().lower()

        # Try to find by product name first
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
                bp.max_production_limit
            FROM blueprints bp
            JOIN blueprint_products bpp ON bp.type_id = bpp.blueprint_type_id
            JOIN types bp_type ON bp.type_id = bp_type.type_id
            JOIN types prod_type ON bpp.product_type_id = prod_type.type_id
            WHERE prod_type.type_name_lower = ?
            OR prod_type.type_name_lower LIKE ?
            ORDER BY CASE WHEN prod_type.type_name_lower = ? THEN 0 ELSE 1 END, length(prod_type.type_name)
            LIMIT 1
            """,
            (query_lower, f"{query_lower}%", query_lower),
        )

        row = cursor.fetchone()
        searched_as = "product"

        if not row:
            # Try by blueprint name
            bp_query = (
                query_lower if query_lower.endswith(" blueprint") else f"{query_lower} blueprint"
            )
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
                    bp.max_production_limit
                FROM blueprints bp
                JOIN blueprint_products bpp ON bp.type_id = bpp.blueprint_type_id
                JOIN types bp_type ON bp.type_id = bp_type.type_id
                JOIN types prod_type ON bpp.product_type_id = prod_type.type_id
                WHERE bp_type.type_name_lower = ?
                LIMIT 1
                """,
                (bp_query,),
            )
            row = cursor.fetchone()
            if row:
                searched_as = "blueprint"

        if row:
            blueprint_type_id = row[0]

            # Get materials
            mat_cursor = conn.execute(
                """
                SELECT t.type_name, bm.quantity
                FROM blueprint_materials bm
                JOIN types t ON bm.material_type_id = t.type_id
                WHERE bm.blueprint_type_id = ?
                ORDER BY bm.quantity DESC
                """,
                (blueprint_type_id,),
            )
            materials = [{"name": r[0], "quantity": r[1]} for r in mat_cursor.fetchall()]

            # Get sources
            src_cursor = conn.execute(
                """
                SELECT nc.corporation_name
                FROM npc_seeding ns
                JOIN npc_corporations nc ON ns.corporation_id = nc.corporation_id
                WHERE ns.type_id = ?
                """,
                (blueprint_type_id,),
            )
            sources = [{"corporation": r[0], "type": "npc"} for r in src_cursor.fetchall()]

            db.close()

            return {
                "found": True,
                "blueprint": {
                    "blueprint_type_id": row[0],
                    "blueprint_name": row[1],
                    "product_type_id": row[2],
                    "product_name": row[3],
                    "product_quantity": row[4],
                    "manufacturing_time_seconds": row[5],
                    "copying_time_seconds": row[6],
                    "max_production_limit": row[7],
                    "materials": materials,
                    "sources": sources,
                },
                "searched_as": searched_as,
                "query": item_name,
                "query_timestamp": query_ts,
            }
        else:
            db.close()
            return {
                "found": False,
                "message": f"No blueprint found for '{item_name}'",
                "hint": "Item may not have a blueprint (e.g., minerals, loot drops)",
                "query": item_name,
                "query_timestamp": query_ts,
            }

    except Exception as e:
        return {
            "error": "lookup_error",
            "message": f"Failed to look up blueprint: {e}",
            "query_timestamp": query_ts,
        }


# =============================================================================
# Argument Parser Registration
# =============================================================================


def register_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Register SDE command parsers."""

    # sde-seed command
    seed_parser = subparsers.add_parser(
        "sde-seed",
        help="Download and import SDE from Fuzzwork",
    )
    seed_parser.add_argument(
        "--check",
        action="store_true",
        help="Check SDE status without downloading",
    )
    seed_parser.add_argument(
        "--break-glass-latest",
        action="store_true",
        dest="break_glass_latest",
        help="Skip checksum verification (use with caution)",
    )
    seed_parser.add_argument(
        "--show-checksum",
        action="store_true",
        dest="show_checksum",
        help="Display SHA256 of downloaded file for manifest updates",
    )
    seed_parser.set_defaults(func=cmd_sde_seed)

    # sde-status command
    status_parser = subparsers.add_parser(
        "sde-status",
        help="Show SDE database status",
    )
    status_parser.set_defaults(func=cmd_sde_status)

    # sde-item command
    item_parser = subparsers.add_parser(
        "sde-item",
        help="Look up item information from SDE",
    )
    item_parser.add_argument(
        "item_name",
        nargs="+",
        help="Item name to look up",
    )
    item_parser.set_defaults(func=cmd_sde_item)

    # sde-blueprint command
    blueprint_parser = subparsers.add_parser(
        "sde-blueprint",
        help="Look up blueprint information from SDE",
    )
    blueprint_parser.add_argument(
        "item_name",
        nargs="+",
        help="Product or blueprint name to look up",
    )
    blueprint_parser.set_defaults(func=cmd_sde_blueprint)
