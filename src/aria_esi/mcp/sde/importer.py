"""
SDE Importer for ARIA.

Downloads and imports EVE Static Data Export from Fuzzwork SQLite conversion.
The Fuzzwork SQLite dump contains all SDE tables pre-converted to SQLite format.
"""

from __future__ import annotations

import bz2
import sqlite3
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from aria_esi.core.data_integrity import (
    IntegrityError,
    compute_sha256,
    get_pinned_sde_url,
    is_break_glass_enabled,
)
from aria_esi.core.logging import get_logger

from .schema import (
    AGENT_TABLES_SQL,
    IMPORT_AGENT_DIVISIONS_SQL,
    IMPORT_AGENT_TYPES_SQL,
    IMPORT_AGENTS_SQL,
    IMPORT_BLUEPRINT_MATERIALS_SQL,
    IMPORT_BLUEPRINT_PRODUCTS_SQL,
    IMPORT_BLUEPRINTS_SQL,
    IMPORT_CATEGORIES_SQL,
    IMPORT_GROUPS_SQL,
    IMPORT_META_GROUPS_SQL,
    IMPORT_META_TYPES_SQL,
    IMPORT_NPC_CORPORATIONS_SQL,
    IMPORT_NPC_SEEDING_SQL,
    IMPORT_REGIONS_SQL,
    IMPORT_SKILL_ATTRIBUTES_SQL,
    IMPORT_SKILL_PREREQUISITES_SQL,
    IMPORT_STATIONS_SQL,
    IMPORT_TYPE_SKILL_REQUIREMENTS_SQL,
    IMPORT_TYPES_SQL,
    META_TYPE_TABLES_SQL,
    SDE_TABLES_SQL,
    SKILL_TABLES_SQL,
)

if TYPE_CHECKING:
    from ..market.database import MarketDatabase

logger = get_logger(__name__)

# =============================================================================
# Constants
# =============================================================================

# Fuzzwork SQLite dump URL
FUZZWORK_SQLITE_URL = "https://www.fuzzwork.co.uk/dump/sqlite-latest.sqlite.bz2"

# Temporary file for downloaded SDE
SDE_TEMP_DIR = Path(tempfile.gettempdir()) / "aria_sde"

# Connection timeout
DOWNLOAD_TIMEOUT = 300.0  # 5 minutes for large file

# Hardcoded NPC division names
# The crpNPCDivisions table is empty in the Fuzzwork SDE dump, so we maintain
# a static mapping of division IDs to names. These are stable EVE game constants.
# Source: Cross-referenced from EVEInfo, EVE University Wiki, and in-game data.
DIVISION_NAMES: dict[int, str] = {
    1: "Accounting",
    2: "Administration",
    3: "Advisory",
    4: "Archives",
    5: "Astrosurveying",
    6: "Command",
    7: "Distribution",
    8: "Financial",
    9: "Intelligence",
    10: "Internal Security",
    11: "Legal",
    12: "Manufacturing",
    13: "Marketing",
    14: "Mining",
    15: "Personnel",
    16: "Production",
    17: "Public Relations",
    18: "R&D",
    19: "Security",
    20: "Storage",
    21: "Surveillance",
    # Legacy/alternate IDs observed in agtAgents table
    22: "Distribution",
    23: "Mining",
    24: "Security",
    25: "Advisory",
    26: "Surveillance",
    27: "Command",
    28: "Administration",
    29: "Storage",
    37: "Financial",
}


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class SDEImportResult:
    """Result of SDE import operation."""

    success: bool
    categories_imported: int = 0
    groups_imported: int = 0
    types_imported: int = 0
    blueprints_imported: int = 0
    blueprint_products_imported: int = 0
    blueprint_materials_imported: int = 0
    npc_seeding_imported: int = 0
    npc_corporations_imported: int = 0
    regions_imported: int = 0
    stations_imported: int = 0
    skill_attributes_imported: int = 0
    skill_prerequisites_imported: int = 0
    type_skill_requirements_imported: int = 0
    agent_divisions_imported: int = 0
    agent_types_imported: int = 0
    agents_imported: int = 0
    meta_groups_imported: int = 0
    meta_types_imported: int = 0
    download_time_seconds: float = 0.0
    import_time_seconds: float = 0.0
    error: str | None = None


@dataclass
class SDEStatus:
    """SDE database status."""

    seeded: bool
    category_count: int = 0
    group_count: int = 0
    type_count: int = 0
    blueprint_count: int = 0
    npc_seeding_count: int = 0
    npc_corp_count: int = 0
    region_count: int = 0
    station_count: int = 0
    skill_attribute_count: int = 0
    skill_prerequisite_count: int = 0
    type_skill_requirement_count: int = 0
    agent_division_count: int = 0
    agent_type_count: int = 0
    agent_count: int = 0
    meta_group_count: int = 0
    meta_type_count: int = 0
    sde_version: str | None = None
    import_timestamp: str | None = None
    source_checksum: str | None = None


# =============================================================================
# Importer Class
# =============================================================================


class SDEImporter:
    """
    Imports EVE SDE data from Fuzzwork SQLite dump into ARIA market database.

    The Fuzzwork dump is a complete SQLite conversion of the EVE SDE,
    updated with each game patch. This importer extracts the tables
    we need for item lookups, blueprint info, and NPC seeding data.
    """

    def __init__(self, market_db: MarketDatabase):
        """
        Initialize importer with target database.

        Args:
            market_db: MarketDatabase instance to import into
        """
        self.market_db = market_db
        self._temp_sde_path: Path | None = None
        self._source_checksum: str | None = None

    def initialize_schema(self) -> None:
        """Create SDE tables if they don't exist."""
        conn = self.market_db._get_connection()

        # Check if types table needs extension
        cursor = conn.execute("PRAGMA table_info(types)")
        columns = {row[1] for row in cursor.fetchall()}

        if "description" not in columns:
            try:
                conn.execute("ALTER TABLE types ADD COLUMN description TEXT")
                logger.info("Added description column to types table")
            except sqlite3.OperationalError:
                pass  # Column may already exist

        if "published" not in columns:
            try:
                conn.execute("ALTER TABLE types ADD COLUMN published INTEGER DEFAULT 1")
                logger.info("Added published column to types table")
            except sqlite3.OperationalError:
                pass  # Column may already exist

        # Create SDE tables
        conn.executescript(SDE_TABLES_SQL)
        # Create skill tables
        conn.executescript(SKILL_TABLES_SQL)
        # Create agent tables
        conn.executescript(AGENT_TABLES_SQL)
        # Create meta type tables
        conn.executescript(META_TYPE_TABLES_SQL)
        conn.commit()
        logger.info("SDE schema initialized")

    def download_sde(
        self,
        progress_callback=None,
        break_glass: bool = False,
        show_checksum: bool = False,
    ) -> Path:
        """
        Download Fuzzwork SQLite dump with optional integrity verification.

        Args:
            progress_callback: Optional callback(bytes_downloaded, total_bytes)
            break_glass: If True, skip checksum verification
            show_checksum: If True, display the SHA256 checksum after download

        Returns:
            Path to downloaded and decompressed SQLite file

        Raises:
            httpx.HTTPError: If download fails
            IntegrityError: If checksum verification fails (and not break_glass)
        """
        SDE_TEMP_DIR.mkdir(parents=True, exist_ok=True)
        compressed_path = SDE_TEMP_DIR / "sde-latest.sqlite.bz2"
        decompressed_path = SDE_TEMP_DIR / "sde-latest.sqlite"

        # Get pinned URL and expected checksum from manifest
        url, expected_checksum = get_pinned_sde_url()

        # Download with progress
        logger.info("Downloading SDE from %s", url)

        with httpx.stream("GET", url, timeout=DOWNLOAD_TIMEOUT) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length", 0))
            downloaded = 0

            with open(compressed_path, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total)

        logger.info("Downloaded %d MB compressed", compressed_path.stat().st_size // (1024 * 1024))

        # Compute checksum of compressed file
        actual_checksum = compute_sha256(compressed_path)
        self._source_checksum = actual_checksum

        if show_checksum:
            logger.info("SDE SHA256 checksum: %s", actual_checksum)

        # Verify checksum if configured and not in break-glass mode
        effective_break_glass = break_glass or is_break_glass_enabled()

        if expected_checksum and not effective_break_glass:
            if actual_checksum.lower() != expected_checksum.lower():
                # Clean up the bad download
                compressed_path.unlink(missing_ok=True)
                raise IntegrityError(
                    f"SDE checksum mismatch: expected {expected_checksum}, got {actual_checksum}",
                    expected=expected_checksum,
                    actual=actual_checksum,
                )
            logger.info("SDE checksum verified: %s...", actual_checksum[:16])
        elif expected_checksum and effective_break_glass:
            logger.warning("Break-glass mode: skipping SDE checksum verification")
        else:
            logger.info("No SDE checksum configured, skipping verification")

        # Decompress
        logger.info("Decompressing SDE...")
        with bz2.open(compressed_path, "rb") as f_in:
            with open(decompressed_path, "wb") as f_out:
                while True:
                    chunk = f_in.read(8192 * 1024)  # 8MB chunks
                    if not chunk:
                        break
                    f_out.write(chunk)

        # Clean up compressed file
        compressed_path.unlink()

        logger.info("Decompressed to %d MB", decompressed_path.stat().st_size // (1024 * 1024))
        self._temp_sde_path = decompressed_path
        return decompressed_path

    def import_from_sde(self, sde_path: Path, progress_callback=None) -> SDEImportResult:
        """
        Import SDE data from Fuzzwork SQLite file.

        Args:
            sde_path: Path to decompressed Fuzzwork SQLite
            progress_callback: Optional callback(step_name, count)

        Returns:
            SDEImportResult with counts and timing
        """
        result = SDEImportResult(success=False)
        start_time = time.time()

        # Connect to source SDE database
        sde_conn = sqlite3.connect(str(sde_path))
        sde_conn.row_factory = sqlite3.Row

        try:
            # Get target connection
            target_conn = self.market_db._get_connection()

            # Initialize schema first
            self.initialize_schema()

            # Import categories
            if progress_callback:
                progress_callback("categories", 0)
            result.categories_imported = self._import_categories(sde_conn, target_conn)
            if progress_callback:
                progress_callback("categories", result.categories_imported)

            # Import groups
            if progress_callback:
                progress_callback("groups", 0)
            result.groups_imported = self._import_groups(sde_conn, target_conn)
            if progress_callback:
                progress_callback("groups", result.groups_imported)

            # Import types
            if progress_callback:
                progress_callback("types", 0)
            result.types_imported = self._import_types(sde_conn, target_conn)
            if progress_callback:
                progress_callback("types", result.types_imported)

            # Import blueprints
            if progress_callback:
                progress_callback("blueprints", 0)
            result.blueprints_imported = self._import_blueprints(sde_conn, target_conn)
            if progress_callback:
                progress_callback("blueprints", result.blueprints_imported)

            # Import blueprint products
            if progress_callback:
                progress_callback("blueprint_products", 0)
            result.blueprint_products_imported = self._import_blueprint_products(
                sde_conn, target_conn
            )
            if progress_callback:
                progress_callback("blueprint_products", result.blueprint_products_imported)

            # Import blueprint materials
            if progress_callback:
                progress_callback("blueprint_materials", 0)
            result.blueprint_materials_imported = self._import_blueprint_materials(
                sde_conn, target_conn
            )
            if progress_callback:
                progress_callback("blueprint_materials", result.blueprint_materials_imported)

            # Import NPC corporations
            if progress_callback:
                progress_callback("npc_corporations", 0)
            result.npc_corporations_imported = self._import_npc_corporations(sde_conn, target_conn)
            if progress_callback:
                progress_callback("npc_corporations", result.npc_corporations_imported)

            # Import NPC seeding (BPO availability)
            if progress_callback:
                progress_callback("npc_seeding", 0)
            result.npc_seeding_imported = self._import_npc_seeding(sde_conn, target_conn)
            if progress_callback:
                progress_callback("npc_seeding", result.npc_seeding_imported)

            # Import regions (for market queries)
            if progress_callback:
                progress_callback("regions", 0)
            result.regions_imported = self._import_regions(sde_conn, target_conn)
            if progress_callback:
                progress_callback("regions", result.regions_imported)

            # Import NPC stations (for nearby market search)
            if progress_callback:
                progress_callback("stations", 0)
            result.stations_imported = self._import_stations(sde_conn, target_conn)
            if progress_callback:
                progress_callback("stations", result.stations_imported)

            # Import skill attributes (rank, training parameters)
            if progress_callback:
                progress_callback("skill_attributes", 0)
            result.skill_attributes_imported = self._import_skill_attributes(sde_conn, target_conn)
            if progress_callback:
                progress_callback("skill_attributes", result.skill_attributes_imported)

            # Import skill prerequisites
            if progress_callback:
                progress_callback("skill_prerequisites", 0)
            result.skill_prerequisites_imported = self._import_skill_prerequisites(
                sde_conn, target_conn
            )
            if progress_callback:
                progress_callback("skill_prerequisites", result.skill_prerequisites_imported)

            # Import type skill requirements (ships/modules)
            if progress_callback:
                progress_callback("type_skill_requirements", 0)
            result.type_skill_requirements_imported = self._import_type_skill_requirements(
                sde_conn, target_conn
            )
            if progress_callback:
                progress_callback(
                    "type_skill_requirements", result.type_skill_requirements_imported
                )

            # Import agent divisions
            if progress_callback:
                progress_callback("agent_divisions", 0)
            result.agent_divisions_imported = self._import_agent_divisions(sde_conn, target_conn)
            if progress_callback:
                progress_callback("agent_divisions", result.agent_divisions_imported)

            # Import agent types
            if progress_callback:
                progress_callback("agent_types", 0)
            result.agent_types_imported = self._import_agent_types(sde_conn, target_conn)
            if progress_callback:
                progress_callback("agent_types", result.agent_types_imported)

            # Import agents
            if progress_callback:
                progress_callback("agents", 0)
            result.agents_imported = self._import_agents(sde_conn, target_conn)
            if progress_callback:
                progress_callback("agents", result.agents_imported)

            # Import meta groups
            if progress_callback:
                progress_callback("meta_groups", 0)
            result.meta_groups_imported = self._import_meta_groups(sde_conn, target_conn)
            if progress_callback:
                progress_callback("meta_groups", result.meta_groups_imported)

            # Import meta types
            if progress_callback:
                progress_callback("meta_types", 0)
            result.meta_types_imported = self._import_meta_types(sde_conn, target_conn)
            if progress_callback:
                progress_callback("meta_types", result.meta_types_imported)

            # Record import timestamp and source checksum
            target_conn.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                ("sde_import_timestamp", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
            )
            if self._source_checksum:
                target_conn.execute(
                    "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                    ("sde_source_checksum", self._source_checksum),
                )
            target_conn.commit()

            # Explicit cache invalidation for same-process callers
            try:
                from aria_esi.mcp.sde.queries import get_sde_query_service

                get_sde_query_service().invalidate_all()
                logger.info("SDE query caches invalidated")
            except Exception:
                pass  # Service may not be initialized yet

            result.success = True
            result.import_time_seconds = time.time() - start_time

            logger.info(
                "SDE import complete: %d categories, %d groups, %d types, %d blueprints",
                result.categories_imported,
                result.groups_imported,
                result.types_imported,
                result.blueprints_imported,
            )

        except Exception as e:
            logger.error("SDE import failed: %s", e)
            result.error = str(e)
            result.import_time_seconds = time.time() - start_time

        finally:
            sde_conn.close()

        return result

    def _import_categories(
        self, sde_conn: sqlite3.Connection, target_conn: sqlite3.Connection
    ) -> int:
        """Import category data from SDE."""
        cursor = sde_conn.execute("""
            SELECT categoryID, categoryName
            FROM invCategories
            WHERE published = 1
        """)

        batch = []
        for row in cursor:
            batch.append(
                (
                    row["categoryID"],
                    row["categoryName"],
                    row["categoryName"].lower(),
                )
            )

        if batch:
            target_conn.executemany(IMPORT_CATEGORIES_SQL, batch)
            target_conn.commit()

        return len(batch)

    def _import_groups(self, sde_conn: sqlite3.Connection, target_conn: sqlite3.Connection) -> int:
        """Import group data from SDE."""
        cursor = sde_conn.execute("""
            SELECT groupID, groupName, categoryID
            FROM invGroups
            WHERE published = 1
        """)

        batch = []
        for row in cursor:
            batch.append(
                (
                    row["groupID"],
                    row["groupName"],
                    row["groupName"].lower(),
                    row["categoryID"],
                )
            )

        if batch:
            target_conn.executemany(IMPORT_GROUPS_SQL, batch)
            target_conn.commit()

        return len(batch)

    def _import_types(self, sde_conn: sqlite3.Connection, target_conn: sqlite3.Connection) -> int:
        """Import type data from SDE."""
        # Check if packagedVolume column exists (not present in all SDE versions)
        cursor = sde_conn.execute("PRAGMA table_info(invTypes)")
        columns = {row[1] for row in cursor.fetchall()}
        has_packaged_volume = "packagedVolume" in columns

        if has_packaged_volume:
            cursor = sde_conn.execute("""
                SELECT
                    t.typeID,
                    t.typeName,
                    t.groupID,
                    g.categoryID,
                    t.marketGroupID,
                    t.volume,
                    t.packagedVolume,
                    t.description,
                    t.published
                FROM invTypes t
                LEFT JOIN invGroups g ON t.groupID = g.groupID
            """)
        else:
            cursor = sde_conn.execute("""
                SELECT
                    t.typeID,
                    t.typeName,
                    t.groupID,
                    g.categoryID,
                    t.marketGroupID,
                    t.volume,
                    NULL as packagedVolume,
                    t.description,
                    t.published
                FROM invTypes t
                LEFT JOIN invGroups g ON t.groupID = g.groupID
            """)

        batch = []
        for row in cursor:
            # Use numeric indices since column names may vary
            batch.append(
                (
                    row[0],  # typeID
                    row[1],  # typeName
                    row[1].lower() if row[1] else "",  # type_name_lower
                    row[2],  # groupID
                    row[3],  # categoryID
                    row[4],  # marketGroupID
                    row[5],  # volume
                    row[6],  # packagedVolume (or NULL)
                    row[7],  # description
                    row[8],  # published
                )
            )

        if batch:
            # Import in chunks to avoid memory issues
            chunk_size = 10000
            for i in range(0, len(batch), chunk_size):
                chunk = batch[i : i + chunk_size]
                target_conn.executemany(IMPORT_TYPES_SQL, chunk)
            target_conn.commit()

        return len(batch)

    def _import_blueprints(
        self, sde_conn: sqlite3.Connection, target_conn: sqlite3.Connection
    ) -> int:
        """Import blueprint definitions from SDE."""
        # Check which tables exist - Fuzzwork SDE may have different structure
        cursor = sde_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%lueprint%'"
        )
        available_tables = {row[0] for row in cursor.fetchall()}
        logger.debug("Available blueprint tables: %s", available_tables)

        blueprints: dict[int, int] = {}
        activity_times: dict[int, dict[int, int]] = {}

        # Try industryBlueprints first, fall back to ramTypeRequirements for older SDE
        if "industryBlueprints" in available_tables:
            cursor = sde_conn.execute("""
                SELECT typeID, maxProductionLimit
                FROM industryBlueprints
            """)
            blueprints = {row[0]: row[1] for row in cursor}

            # Check for industryActivities
            cursor = sde_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='industryActivities'"
            )
            if cursor.fetchone():
                cursor = sde_conn.execute("""
                    SELECT blueprintTypeID, activityID, time
                    FROM industryActivities
                    WHERE activityID IN (1, 3, 4, 5, 8)
                """)
                for row in cursor:
                    bp_id = row[0]
                    if bp_id not in activity_times:
                        activity_times[bp_id] = {}
                    activity_times[bp_id][row[1]] = row[2]
        else:
            # Fallback: identify blueprints from type names ending in " Blueprint"
            cursor = sde_conn.execute("""
                SELECT typeID FROM invTypes
                WHERE typeName LIKE '% Blueprint'
                AND published = 1
            """)
            for row in cursor:
                blueprints[row[0]] = 10  # Default max runs

        batch = []
        for bp_id, max_runs in blueprints.items():
            times = activity_times.get(bp_id, {})
            batch.append(
                (
                    bp_id,
                    times.get(1),  # manufacturing_time
                    times.get(5),  # copying_time
                    times.get(4),  # research_material_time (ME)
                    times.get(3),  # research_time_time (TE)
                    times.get(8),  # invention_time
                    max_runs,
                )
            )

        if batch:
            target_conn.executemany(IMPORT_BLUEPRINTS_SQL, batch)
            target_conn.commit()

        return len(batch)

    def _import_blueprint_products(
        self, sde_conn: sqlite3.Connection, target_conn: sqlite3.Connection
    ) -> int:
        """Import what blueprints produce."""
        # Get valid type_ids from target database to filter orphans
        # (SDE contains blueprints for removed/obsolete items)
        valid_cursor = target_conn.execute("SELECT type_id FROM types")
        valid_type_ids = {row[0] for row in valid_cursor}

        # Check if table exists
        cursor = sde_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='industryActivityProducts'"
        )
        if cursor.fetchone():
            # Check actual column names in the table
            cursor = sde_conn.execute("PRAGMA table_info(industryActivityProducts)")
            columns = {row[1] for row in cursor.fetchall()}

            # Fuzzwork may use different column names
            if "blueprintTypeID" in columns:
                bp_col, prod_col, qty_col = "blueprintTypeID", "productTypeID", "quantity"
            else:
                # Try alternative column names
                bp_col = "typeID" if "typeID" in columns else "blueprintTypeID"
                prod_col = "productTypeID" if "productTypeID" in columns else "typeID"
                qty_col = "quantity" if "quantity" in columns else "1"

            # Activity 1 = Manufacturing
            cursor = sde_conn.execute(f"""
                SELECT {bp_col}, {prod_col}, {qty_col}
                FROM industryActivityProducts
                WHERE activityID = 1
            """)
            # Filter out products that don't exist in types table
            batch = [(row[0], row[1], row[2]) for row in cursor if row[1] in valid_type_ids]
        else:
            # Fallback: infer products from blueprint names
            # "X Blueprint" -> produces "X"
            cursor = sde_conn.execute("""
                SELECT bp.typeID, prod.typeID, 1
                FROM invTypes bp
                JOIN invTypes prod ON prod.typeName = REPLACE(bp.typeName, ' Blueprint', '')
                WHERE bp.typeName LIKE '% Blueprint'
                AND bp.published = 1
                AND prod.published = 1
            """)
            batch = [(row[0], row[1], row[2]) for row in cursor]

        if batch:
            target_conn.executemany(IMPORT_BLUEPRINT_PRODUCTS_SQL, batch)
            target_conn.commit()

        return len(batch)

    def _import_blueprint_materials(
        self, sde_conn: sqlite3.Connection, target_conn: sqlite3.Connection
    ) -> int:
        """Import blueprint manufacturing materials."""
        # Check if table exists
        cursor = sde_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='industryActivityMaterials'"
        )
        if not cursor.fetchone():
            # Materials table not available in this SDE version
            logger.warning("industryActivityMaterials table not found, skipping materials import")
            return 0

        # Check actual column names
        cursor = sde_conn.execute("PRAGMA table_info(industryActivityMaterials)")
        columns = {row[1] for row in cursor.fetchall()}

        if "blueprintTypeID" in columns:
            bp_col, mat_col, qty_col = "blueprintTypeID", "materialTypeID", "quantity"
        else:
            bp_col = "typeID" if "typeID" in columns else "blueprintTypeID"
            mat_col = "materialTypeID" if "materialTypeID" in columns else "typeID"
            qty_col = "quantity" if "quantity" in columns else "1"

        # Activity 1 = Manufacturing, 9 = Reactions, 11 = Simple Reactions
        cursor = sde_conn.execute(f"""
            SELECT {bp_col}, {mat_col}, {qty_col}, activityID
            FROM industryActivityMaterials
            WHERE activityID IN (1, 9, 11)
        """)

        batch = [(row[0], row[1], row[2], row[3]) for row in cursor]

        if batch:
            # Import in chunks
            chunk_size = 10000
            for i in range(0, len(batch), chunk_size):
                chunk = batch[i : i + chunk_size]
                target_conn.executemany(IMPORT_BLUEPRINT_MATERIALS_SQL, chunk)
            target_conn.commit()

        return len(batch)

    def _import_npc_corporations(
        self, sde_conn: sqlite3.Connection, target_conn: sqlite3.Connection
    ) -> int:
        """Import NPC corporation data."""
        # Check if table exists
        cursor = sde_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='crpNPCCorporations'"
        )
        if not cursor.fetchone():
            logger.warning("crpNPCCorporations table not found, using fallback data")
            # Insert known Outer Ring Excavations data (sells ORE mining ship BPOs)
            fallback = [
                (1000129, "Outer Ring Excavations", "outer ring excavations", 500014),
            ]
            target_conn.executemany(IMPORT_NPC_CORPORATIONS_SQL, fallback)
            target_conn.commit()
            return len(fallback)

        # Check actual column names
        cursor = sde_conn.execute("PRAGMA table_info(crpNPCCorporations)")
        columns = {row[1] for row in cursor.fetchall()}
        logger.debug("crpNPCCorporations columns: %s", columns)

        # Build query based on available columns
        corp_id_col = "corporationID" if "corporationID" in columns else "corporation_id"
        # corporationName might not exist - we may need to join with another table
        has_name = "corporationName" in columns

        if has_name:
            cursor = sde_conn.execute(f"""
                SELECT {corp_id_col}, corporationName, factionID
                FROM crpNPCCorporations
            """)
            batch = []
            for row in cursor:
                corp_name = row[1] if row[1] else f"Corp {row[0]}"
                batch.append((row[0], corp_name, corp_name.lower(), row[2]))
        else:
            # No name column in crpNPCCorporations - join with invNames for actual names
            faction_col = "factionID" if "factionID" in columns else "NULL"

            # Check if invNames table exists
            inv_names_cursor = sde_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='invNames'"
            )
            has_inv_names = inv_names_cursor.fetchone() is not None

            if has_inv_names:
                cursor = sde_conn.execute(f"""
                    SELECT c.{corp_id_col}, n.itemName, c.{faction_col}
                    FROM crpNPCCorporations c
                    LEFT JOIN invNames n ON c.{corp_id_col} = n.itemID
                """)
                batch = []
                for row in cursor:
                    corp_name = row[1] if row[1] else f"Corporation {row[0]}"
                    batch.append((row[0], corp_name, corp_name.lower(), row[2]))
            else:
                # Fallback to placeholder names
                cursor = sde_conn.execute(f"""
                    SELECT {corp_id_col}, {faction_col}
                    FROM crpNPCCorporations
                """)
                batch = []
                for row in cursor:
                    corp_name = f"Corporation {row[0]}"
                    batch.append((row[0], corp_name, corp_name.lower(), row[1]))

        if batch:
            target_conn.executemany(IMPORT_NPC_CORPORATIONS_SQL, batch)
            target_conn.commit()

        return len(batch)

    def _import_npc_seeding(
        self, sde_conn: sqlite3.Connection, target_conn: sqlite3.Connection
    ) -> int:
        """Import NPC seeding data from SDE crpNPCCorporationTrades table.

        The crpNPCCorporationTrades table maps corporation IDs to type IDs,
        indicating which NPC corporations sell which items at their stations.
        This includes blueprints, modules, ammo, and other NPC-seeded items.
        """
        # Check if crpNPCCorporationTrades table exists in SDE
        cursor = sde_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='crpNPCCorporationTrades'"
        )
        if not cursor.fetchone():
            logger.warning("crpNPCCorporationTrades table not found in SDE")
            return 0

        # Import all NPC seeding data from SDE
        # Table has columns: corporationID, typeID
        try:
            cursor = sde_conn.execute("SELECT typeID, corporationID FROM crpNPCCorporationTrades")
            rows = cursor.fetchall()

            if rows:
                target_conn.executemany(IMPORT_NPC_SEEDING_SQL, rows)
                target_conn.commit()
                logger.info("Imported %d NPC seeding records from SDE", len(rows))
                return len(rows)
            return 0

        except sqlite3.OperationalError as e:
            logger.warning("Could not import NPC seeding: %s", e)
            return 0

    def _import_regions(self, sde_conn: sqlite3.Connection, target_conn: sqlite3.Connection) -> int:
        """Import region data for market queries."""
        # Check if mapRegions table exists
        cursor = sde_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='mapRegions'"
        )
        if not cursor.fetchone():
            logger.warning("mapRegions table not found in SDE")
            return 0

        # Check actual column names
        cursor = sde_conn.execute("PRAGMA table_info(mapRegions)")
        columns = {row[1] for row in cursor.fetchall()}
        logger.debug("mapRegions columns: %s", columns)

        # Build query based on available columns
        region_id_col = "regionID" if "regionID" in columns else "region_id"
        region_name_col = "regionName" if "regionName" in columns else "region_name"

        try:
            cursor = sde_conn.execute(f"""
                SELECT {region_id_col}, {region_name_col}
                FROM mapRegions
                WHERE {region_name_col} IS NOT NULL
            """)
        except sqlite3.OperationalError as e:
            logger.warning("Could not query mapRegions: %s", e)
            return 0

        batch = []
        for row in cursor:
            region_id = row[0]
            region_name = row[1] if row[1] else f"Region {region_id}"
            batch.append((region_id, region_name, region_name.lower()))

        if batch:
            target_conn.executemany(IMPORT_REGIONS_SQL, batch)
            target_conn.commit()

        return len(batch)

    def _import_stations(
        self, sde_conn: sqlite3.Connection, target_conn: sqlite3.Connection
    ) -> int:
        """Import NPC station data for nearby market search."""
        # Check if staStations table exists
        cursor = sde_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='staStations'"
        )
        if not cursor.fetchone():
            logger.warning("staStations table not found in SDE")
            return 0

        # Check actual column names
        cursor = sde_conn.execute("PRAGMA table_info(staStations)")
        columns = {row[1] for row in cursor.fetchall()}
        logger.debug("staStations columns: %s", columns)

        # Build query based on available columns
        station_id_col = "stationID" if "stationID" in columns else "station_id"
        station_name_col = "stationName" if "stationName" in columns else "station_name"
        system_id_col = "solarSystemID" if "solarSystemID" in columns else "solar_system_id"
        region_id_col = "regionID" if "regionID" in columns else "region_id"
        corp_id_col = "corporationID" if "corporationID" in columns else "corporation_id"

        try:
            cursor = sde_conn.execute(f"""
                SELECT
                    {station_id_col},
                    {station_name_col},
                    {system_id_col},
                    {region_id_col},
                    {corp_id_col}
                FROM staStations
                WHERE {station_name_col} IS NOT NULL
            """)
        except sqlite3.OperationalError as e:
            logger.warning("Could not query staStations: %s", e)
            return 0

        batch = []
        for row in cursor:
            station_id = row[0]
            station_name = row[1] if row[1] else f"Station {station_id}"
            batch.append(
                (
                    station_id,
                    station_name,
                    station_name.lower(),
                    row[2],  # system_id
                    row[3],  # region_id
                    row[4],  # corporation_id
                )
            )

        if batch:
            # Import in chunks to avoid memory issues
            chunk_size = 5000
            for i in range(0, len(batch), chunk_size):
                chunk = batch[i : i + chunk_size]
                target_conn.executemany(IMPORT_STATIONS_SQL, chunk)
            target_conn.commit()

        return len(batch)

    def _import_skill_attributes(
        self, sde_conn: sqlite3.Connection, target_conn: sqlite3.Connection
    ) -> int:
        """
        Import skill attributes (rank, training attributes) from dgmTypeAttributes.

        EVE skill training attributes are stored as dogma attributes:
        - 275: skillTimeConstant (rank, 1-16)
        - 180: primaryAttribute (attribute ID)
        - 181: secondaryAttribute (attribute ID)

        Training attribute IDs map to:
        - 164: charisma
        - 165: intelligence
        - 166: memory
        - 167: perception
        - 168: willpower
        """
        # Check if dgmTypeAttributes table exists
        cursor = sde_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='dgmTypeAttributes'"
        )
        if not cursor.fetchone():
            logger.warning("dgmTypeAttributes table not found in SDE")
            return 0

        # Attribute IDs for skill training
        SKILL_TIME_CONSTANT = 275  # Rank (training time multiplier)
        PRIMARY_ATTRIBUTE = 180
        SECONDARY_ATTRIBUTE = 181

        # Attribute ID to name mapping
        ATTRIBUTE_MAP = {
            164: "charisma",
            165: "intelligence",
            166: "memory",
            167: "perception",
            168: "willpower",
        }

        # Get all skills (category 16)
        skill_cursor = target_conn.execute(
            "SELECT type_id FROM types WHERE category_id = 16 AND published = 1"
        )
        skill_ids = {row[0] for row in skill_cursor.fetchall()}

        if not skill_ids:
            logger.warning("No skills found in types table")
            return 0

        # Query skill attributes from SDE
        placeholders = ",".join("?" * len(skill_ids))
        cursor = sde_conn.execute(
            f"""
            SELECT typeID, attributeID, COALESCE(valueInt, valueFloat) as value
            FROM dgmTypeAttributes
            WHERE typeID IN ({placeholders})
            AND attributeID IN (?, ?, ?)
            """,
            list(skill_ids) + [SKILL_TIME_CONSTANT, PRIMARY_ATTRIBUTE, SECONDARY_ATTRIBUTE],
        )

        # Build skill attribute data
        skill_attrs: dict[int, dict[str, int | str | None]] = {}
        for row in cursor:
            type_id, attr_id, value = row[0], row[1], int(row[2])
            if type_id not in skill_attrs:
                skill_attrs[type_id] = {"rank": 1, "primary": None, "secondary": None}

            if attr_id == SKILL_TIME_CONSTANT:
                skill_attrs[type_id]["rank"] = value
            elif attr_id == PRIMARY_ATTRIBUTE:
                skill_attrs[type_id]["primary"] = ATTRIBUTE_MAP.get(value)
            elif attr_id == SECONDARY_ATTRIBUTE:
                skill_attrs[type_id]["secondary"] = ATTRIBUTE_MAP.get(value)

        # Prepare batch for import
        batch = []
        for type_id, attrs in skill_attrs.items():
            batch.append((type_id, attrs["rank"], attrs["primary"], attrs["secondary"]))

        if batch:
            target_conn.executemany(IMPORT_SKILL_ATTRIBUTES_SQL, batch)
            target_conn.commit()

        logger.info("Imported %d skill attributes from SDE", len(batch))
        return len(batch)

    def _import_skill_prerequisites(
        self, sde_conn: sqlite3.Connection, target_conn: sqlite3.Connection
    ) -> int:
        """
        Import skill prerequisites from dgmTypeAttributes.

        Skill prerequisites are stored as dogma attributes:
        - 182: Primary Skill required (type ID)
        - 277: Required skill level for skill 1
        - 183: Secondary Skill required (type ID)
        - 278: Required skill level for skill 2
        - 184: Tertiary Skill required (type ID)
        - 279: Required skill level for skill 3
        - 1285: Quaternary Skill required (type ID)
        - 1286: Required skill level for skill 4
        - 1289: Quinary Skill required (type ID)
        - 1287: Required skill level for skill 5
        - 1290: Senary Skill required (type ID)
        - 1288: Required skill level for skill 6
        """
        # Check if dgmTypeAttributes table exists
        cursor = sde_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='dgmTypeAttributes'"
        )
        if not cursor.fetchone():
            logger.warning("dgmTypeAttributes table not found in SDE")
            return 0

        # Attribute IDs for skill prerequisites (skill ID, level pairs)
        PREREQ_ATTRS = [
            (182, 277),  # Primary Skill required, Required skill level for skill 1
            (183, 278),  # Secondary Skill required, Required skill level for skill 2
            (184, 279),  # Tertiary Skill required, Required skill level for skill 3
            (1285, 1286),  # Quaternary Skill required, Required skill level for skill 4
            (1289, 1287),  # Quinary Skill required, Required skill level for skill 5
            (1290, 1288),  # Senary Skill required, Required skill level for skill 6
        ]

        # Get all skills (category 16)
        skill_cursor = target_conn.execute(
            "SELECT type_id FROM types WHERE category_id = 16 AND published = 1"
        )
        skill_ids = {row[0] for row in skill_cursor.fetchall()}

        if not skill_ids:
            logger.warning("No skills found in types table")
            return 0

        # Flatten prereq attribute IDs for query
        all_prereq_attrs = [attr for pair in PREREQ_ATTRS for attr in pair]

        # Query skill prerequisites from SDE
        placeholders = ",".join("?" * len(skill_ids))
        attr_placeholders = ",".join("?" * len(all_prereq_attrs))
        cursor = sde_conn.execute(
            f"""
            SELECT typeID, attributeID, COALESCE(valueInt, valueFloat) as value
            FROM dgmTypeAttributes
            WHERE typeID IN ({placeholders})
            AND attributeID IN ({attr_placeholders})
            """,
            list(skill_ids) + all_prereq_attrs,
        )

        # Build prerequisite data
        # First, collect all attributes per type
        type_attrs: dict[int, dict[int, int]] = {}
        for row in cursor:
            type_id, attr_id, value = row[0], row[1], int(row[2])
            if type_id not in type_attrs:
                type_attrs[type_id] = {}
            type_attrs[type_id][attr_id] = value

        # Then extract prerequisites
        batch = []
        for type_id, attrs in type_attrs.items():
            for skill_attr, level_attr in PREREQ_ATTRS:
                prereq_skill_id = attrs.get(skill_attr)
                prereq_level = attrs.get(level_attr, 1)
                if prereq_skill_id and prereq_skill_id > 0:
                    batch.append((type_id, int(prereq_skill_id), prereq_level))

        if batch:
            target_conn.executemany(IMPORT_SKILL_PREREQUISITES_SQL, batch)
            target_conn.commit()

        logger.info("Imported %d skill prerequisites from SDE", len(batch))
        return len(batch)

    def _import_type_skill_requirements(
        self, sde_conn: sqlite3.Connection, target_conn: sqlite3.Connection
    ) -> int:
        """
        Import skill requirements for ships, modules, and other items.

        Uses the same requiredSkill attributes as skill prerequisites,
        but for all non-skill types that have skill requirements.
        """
        # Check if dgmTypeAttributes table exists
        cursor = sde_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='dgmTypeAttributes'"
        )
        if not cursor.fetchone():
            logger.warning("dgmTypeAttributes table not found in SDE")
            return 0

        # Attribute IDs for skill requirements (same as prerequisites)
        PREREQ_ATTRS = [
            (182, 277),  # Primary Skill required, Required skill level for skill 1
            (183, 278),  # Secondary Skill required, Required skill level for skill 2
            (184, 279),  # Tertiary Skill required, Required skill level for skill 3
            (1285, 1286),  # Quaternary Skill required, Required skill level for skill 4
            (1289, 1287),  # Quinary Skill required, Required skill level for skill 5
            (1290, 1288),  # Senary Skill required, Required skill level for skill 6
        ]

        # Get non-skill published types that might have skill requirements
        # Categories: Ship(6), Module(7), Charge(8), Drone(18), etc.
        type_cursor = target_conn.execute(
            """
            SELECT type_id FROM types
            WHERE category_id != 16  -- Not skills
            AND category_id != 9     -- Not blueprints (they inherit from product)
            AND published = 1
            """
        )
        type_ids = [row[0] for row in type_cursor.fetchall()]

        if not type_ids:
            logger.warning("No non-skill types found")
            return 0

        # Flatten prereq attribute IDs for query
        all_prereq_attrs = [attr for pair in PREREQ_ATTRS for attr in pair]

        # Query in chunks to avoid huge queries
        # SQLite default SQLITE_MAX_VARIABLE_NUMBER is 999
        # We need len(chunk) + 12 (attribute IDs) placeholders per query
        # So chunk_size must be <= 987 to stay under the limit
        batch = []
        chunk_size = 900
        for i in range(0, len(type_ids), chunk_size):
            chunk_type_ids = type_ids[i : i + chunk_size]
            placeholders = ",".join("?" * len(chunk_type_ids))
            attr_placeholders = ",".join("?" * len(all_prereq_attrs))

            cursor = sde_conn.execute(
                f"""
                SELECT typeID, attributeID, COALESCE(valueInt, valueFloat) as value
                FROM dgmTypeAttributes
                WHERE typeID IN ({placeholders})
                AND attributeID IN ({attr_placeholders})
                """,
                chunk_type_ids + all_prereq_attrs,
            )

            # Build type attribute data for this chunk
            type_attrs: dict[int, dict[int, int]] = {}
            for row in cursor:
                type_id, attr_id, value = row[0], row[1], int(row[2])
                if type_id not in type_attrs:
                    type_attrs[type_id] = {}
                type_attrs[type_id][attr_id] = value

            # Extract requirements
            for type_id, attrs in type_attrs.items():
                for skill_attr, level_attr in PREREQ_ATTRS:
                    req_skill_id = attrs.get(skill_attr)
                    req_level = attrs.get(level_attr, 1)
                    if req_skill_id and req_skill_id > 0:
                        batch.append((type_id, int(req_skill_id), req_level))

        if batch:
            # Import in chunks
            for i in range(0, len(batch), 10000):
                chunk = batch[i : i + 10000]
                target_conn.executemany(IMPORT_TYPE_SKILL_REQUIREMENTS_SQL, chunk)
            target_conn.commit()

        logger.info("Imported %d type skill requirements from SDE", len(batch))
        return len(batch)

    def _import_agent_divisions(
        self, sde_conn: sqlite3.Connection, target_conn: sqlite3.Connection
    ) -> int:
        """
        Import NPC agent divisions from crpNPCDivisions table.

        Divisions determine mission type: Security, Distribution, Mining, etc.
        """
        batch = []

        # Check if crpNPCDivisions table exists
        cursor = sde_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='crpNPCDivisions'"
        )
        if cursor.fetchone():
            # Check actual column names
            cursor = sde_conn.execute("PRAGMA table_info(crpNPCDivisions)")
            columns = {row[1] for row in cursor.fetchall()}
            logger.debug("crpNPCDivisions columns: %s", columns)

            # Build query based on available columns
            div_id_col = "divisionID" if "divisionID" in columns else "division_id"
            div_name_col = "divisionName" if "divisionName" in columns else "division_name"

            try:
                cursor = sde_conn.execute(f"""
                    SELECT {div_id_col}, {div_name_col}
                    FROM crpNPCDivisions
                    WHERE {div_name_col} IS NOT NULL
                """)
                for row in cursor:
                    div_id = row[0]
                    div_name = row[1] if row[1] else f"Division {div_id}"
                    batch.append((div_id, div_name, div_name.lower()))
            except sqlite3.OperationalError as e:
                logger.warning("Could not query crpNPCDivisions: %s", e)

        # If no divisions from SDE, extract unique division_ids from agtAgents
        # and create placeholder entries to satisfy FK constraints
        if not batch:
            logger.info("No divisions from SDE, extracting from agtAgents")
            cursor = sde_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='agtAgents'"
            )
            if cursor.fetchone():
                cursor = sde_conn.execute("PRAGMA table_info(agtAgents)")
                columns = {row[1] for row in cursor.fetchall()}
                div_col = "divisionID" if "divisionID" in columns else "division_id"

                try:
                    cursor = sde_conn.execute(f"""
                        SELECT DISTINCT {div_col}
                        FROM agtAgents
                        WHERE {div_col} IS NOT NULL
                    """)
                    for row in cursor:
                        div_id = row[0]
                        # Use hardcoded names from DIVISION_NAMES, fall back to placeholder
                        div_name = DIVISION_NAMES.get(div_id, f"Division {div_id}")
                        batch.append((div_id, div_name, div_name.lower()))
                except sqlite3.OperationalError as e:
                    logger.warning("Could not extract divisions from agtAgents: %s", e)

        if batch:
            target_conn.executemany(IMPORT_AGENT_DIVISIONS_SQL, batch)
            target_conn.commit()

        logger.info("Imported %d agent divisions", len(batch))
        return len(batch)

    def _import_agent_types(
        self, sde_conn: sqlite3.Connection, target_conn: sqlite3.Connection
    ) -> int:
        """
        Import NPC agent types from agtAgentTypes table.

        Agent types: BasicAgent, ResearchAgent, StorylineMissionAgent, etc.
        """
        # Check if agtAgentTypes table exists
        cursor = sde_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='agtAgentTypes'"
        )
        if not cursor.fetchone():
            logger.warning("agtAgentTypes table not found in SDE")
            return 0

        # Check actual column names
        cursor = sde_conn.execute("PRAGMA table_info(agtAgentTypes)")
        columns = {row[1] for row in cursor.fetchall()}
        logger.debug("agtAgentTypes columns: %s", columns)

        # Build query based on available columns
        type_id_col = "agentTypeID" if "agentTypeID" in columns else "agent_type_id"
        type_name_col = "agentType" if "agentType" in columns else "agent_type"

        try:
            cursor = sde_conn.execute(f"""
                SELECT {type_id_col}, {type_name_col}
                FROM agtAgentTypes
            """)
        except sqlite3.OperationalError as e:
            logger.warning("Could not query agtAgentTypes: %s", e)
            return 0

        batch = []
        for row in cursor:
            type_id = row[0]
            type_name = row[1] if row[1] else f"AgentType {type_id}"
            batch.append((type_id, type_name))

        if batch:
            target_conn.executemany(IMPORT_AGENT_TYPES_SQL, batch)
            target_conn.commit()

        logger.info("Imported %d agent types from SDE", len(batch))
        return len(batch)

    def _import_agents(self, sde_conn: sqlite3.Connection, target_conn: sqlite3.Connection) -> int:
        """
        Import NPC agents from agtAgents table.

        Agents have level, division, corporation, and location info.
        """
        # Check if agtAgents table exists
        cursor = sde_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='agtAgents'"
        )
        if not cursor.fetchone():
            logger.warning("agtAgents table not found in SDE")
            return 0

        # Check actual column names
        cursor = sde_conn.execute("PRAGMA table_info(agtAgents)")
        columns = {row[1] for row in cursor.fetchall()}
        logger.debug("agtAgents columns: %s", columns)

        # Build column references based on available columns
        agent_id_col = "agentID" if "agentID" in columns else "agent_id"
        div_id_col = "divisionID" if "divisionID" in columns else "division_id"
        corp_id_col = "corporationID" if "corporationID" in columns else "corporation_id"
        loc_id_col = "locationID" if "locationID" in columns else "location_id"
        level_col = "level" if "level" in columns else "agent_level"
        type_id_col = "agentTypeID" if "agentTypeID" in columns else "agent_type_id"

        # Check if invNames table exists for agent names
        inv_names_cursor = sde_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='invNames'"
        )
        has_inv_names = inv_names_cursor.fetchone() is not None

        # Check if staStations exists to resolve station -> system mapping
        sta_cursor = sde_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='staStations'"
        )
        has_sta_stations = sta_cursor.fetchone() is not None

        try:
            if has_inv_names and has_sta_stations:
                # Full query with name and system resolution
                cursor = sde_conn.execute(f"""
                    SELECT
                        a.{agent_id_col},
                        n.itemName,
                        a.{div_id_col},
                        a.{corp_id_col},
                        a.{loc_id_col},
                        s.solarSystemID,
                        a.{level_col},
                        a.{type_id_col}
                    FROM agtAgents a
                    LEFT JOIN invNames n ON a.{agent_id_col} = n.itemID
                    LEFT JOIN staStations s ON a.{loc_id_col} = s.stationID
                """)
            elif has_inv_names:
                # Query with names but no system resolution
                cursor = sde_conn.execute(f"""
                    SELECT
                        a.{agent_id_col},
                        n.itemName,
                        a.{div_id_col},
                        a.{corp_id_col},
                        a.{loc_id_col},
                        NULL as solarSystemID,
                        a.{level_col},
                        a.{type_id_col}
                    FROM agtAgents a
                    LEFT JOIN invNames n ON a.{agent_id_col} = n.itemID
                """)
            else:
                # Minimal query without name resolution
                cursor = sde_conn.execute(f"""
                    SELECT
                        {agent_id_col},
                        NULL as itemName,
                        {div_id_col},
                        {corp_id_col},
                        {loc_id_col},
                        NULL as solarSystemID,
                        {level_col},
                        {type_id_col}
                    FROM agtAgents
                """)
        except sqlite3.OperationalError as e:
            logger.warning("Could not query agtAgents: %s", e)
            return 0

        # Get valid IDs from our tables to filter orphans (FK constraints)
        valid_station_cursor = target_conn.execute("SELECT station_id FROM stations")
        valid_station_ids = {row[0] for row in valid_station_cursor}

        valid_corp_cursor = target_conn.execute("SELECT corporation_id FROM npc_corporations")
        valid_corp_ids = {row[0] for row in valid_corp_cursor}

        valid_div_cursor = target_conn.execute("SELECT division_id FROM agent_divisions")
        valid_div_ids = {row[0] for row in valid_div_cursor}

        valid_type_cursor = target_conn.execute("SELECT agent_type_id FROM agent_types")
        valid_type_ids = {row[0] for row in valid_type_cursor}

        batch = []
        skipped = 0
        for row in cursor:
            agent_id = row[0]
            agent_name = row[1] if row[1] else f"Agent {agent_id}"
            division_id = row[2]
            corp_id = row[3]
            station_id = row[4]
            agent_type_id = row[7]

            # Skip agents with invalid corporation references (FK constraint)
            if corp_id not in valid_corp_ids:
                skipped += 1
                continue

            # Skip agents with station_ids that don't exist in our stations table (FK constraint)
            # NULL station_id is OK (agent might be in space or structure)
            if station_id is not None and station_id not in valid_station_ids:
                skipped += 1
                continue

            # Skip agents with invalid division_id references (FK constraint)
            # NULL division_id is OK
            if division_id is not None and division_id not in valid_div_ids:
                skipped += 1
                continue

            # Skip agents with invalid agent_type_id references (FK constraint)
            # NULL agent_type_id is OK
            if agent_type_id is not None and agent_type_id not in valid_type_ids:
                skipped += 1
                continue

            batch.append(
                (
                    agent_id,
                    agent_name,
                    agent_name.lower(),
                    division_id,  # division_id
                    corp_id,  # corporation_id
                    station_id,  # station_id (locationID)
                    row[5],  # system_id
                    row[6],  # level
                    agent_type_id,  # agent_type_id
                )
            )

        if skipped:
            logger.info("Skipped %d agents with invalid FK references", skipped)

        if batch:
            # Import in chunks
            chunk_size = 5000
            for i in range(0, len(batch), chunk_size):
                chunk = batch[i : i + chunk_size]
                target_conn.executemany(IMPORT_AGENTS_SQL, chunk)
            target_conn.commit()

        logger.info("Imported %d agents from SDE", len(batch))
        return len(batch)

    def _import_meta_groups(
        self, sde_conn: sqlite3.Connection, target_conn: sqlite3.Connection
    ) -> int:
        """Import meta group definitions (Tech I, Tech II, Faction, etc.)."""
        # Check if invMetaGroups table exists
        cursor = sde_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='invMetaGroups'"
        )
        if not cursor.fetchone():
            logger.warning("invMetaGroups table not found in SDE")
            return 0

        # Check actual column names
        cursor = sde_conn.execute("PRAGMA table_info(invMetaGroups)")
        columns = {row[1] for row in cursor.fetchall()}
        logger.debug("invMetaGroups columns: %s", columns)

        # Build query based on available columns
        group_id_col = "metaGroupID" if "metaGroupID" in columns else "meta_group_id"
        group_name_col = "metaGroupName" if "metaGroupName" in columns else "meta_group_name"

        try:
            cursor = sde_conn.execute(f"""
                SELECT {group_id_col}, {group_name_col}
                FROM invMetaGroups
                WHERE {group_name_col} IS NOT NULL
            """)
        except sqlite3.OperationalError as e:
            logger.warning("Could not query invMetaGroups: %s", e)
            return 0

        batch = []
        for row in cursor:
            group_id = row[0]
            group_name = row[1] if row[1] else f"Meta Group {group_id}"
            batch.append((group_id, group_name, group_name.lower()))

        if batch:
            target_conn.executemany(IMPORT_META_GROUPS_SQL, batch)
            target_conn.commit()

        logger.info("Imported %d meta groups from SDE", len(batch))
        return len(batch)

    def _import_meta_types(
        self, sde_conn: sqlite3.Connection, target_conn: sqlite3.Connection
    ) -> int:
        """Import meta type relationships (T1 → T2/Faction/etc variants)."""
        # Check if invMetaTypes table exists
        cursor = sde_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='invMetaTypes'"
        )
        if not cursor.fetchone():
            logger.warning("invMetaTypes table not found in SDE")
            return 0

        # Check actual column names
        cursor = sde_conn.execute("PRAGMA table_info(invMetaTypes)")
        columns = {row[1] for row in cursor.fetchall()}
        logger.debug("invMetaTypes columns: %s", columns)

        # Build query based on available columns
        type_id_col = "typeID" if "typeID" in columns else "type_id"
        parent_col = "parentTypeID" if "parentTypeID" in columns else "parent_type_id"
        meta_group_col = "metaGroupID" if "metaGroupID" in columns else "meta_group_id"

        # Get valid type_ids from target database to filter orphans
        valid_cursor = target_conn.execute("SELECT type_id FROM types")
        valid_type_ids = {row[0] for row in valid_cursor}

        # Get valid meta_group_ids
        valid_mg_cursor = target_conn.execute("SELECT meta_group_id FROM meta_groups")
        valid_meta_groups = {row[0] for row in valid_mg_cursor}

        try:
            cursor = sde_conn.execute(f"""
                SELECT {type_id_col}, {parent_col}, {meta_group_col}
                FROM invMetaTypes
            """)
        except sqlite3.OperationalError as e:
            logger.warning("Could not query invMetaTypes: %s", e)
            return 0

        batch = []
        skipped = 0
        for row in cursor:
            type_id, parent_id, meta_group_id = row[0], row[1], row[2]

            # Skip entries with invalid references
            if type_id not in valid_type_ids:
                skipped += 1
                continue
            if parent_id not in valid_type_ids:
                skipped += 1
                continue
            if meta_group_id not in valid_meta_groups:
                skipped += 1
                continue

            batch.append((type_id, parent_id, meta_group_id))

        if skipped:
            logger.info("Skipped %d meta types with invalid references", skipped)

        if batch:
            # Import in chunks
            chunk_size = 10000
            for i in range(0, len(batch), chunk_size):
                chunk = batch[i : i + chunk_size]
                target_conn.executemany(IMPORT_META_TYPES_SQL, chunk)
            target_conn.commit()

        logger.info("Imported %d meta types from SDE", len(batch))
        return len(batch)

    def cleanup(self) -> None:
        """Remove temporary SDE files."""
        if self._temp_sde_path and self._temp_sde_path.exists():
            self._temp_sde_path.unlink()
            logger.info("Cleaned up temporary SDE file")

    def get_sde_status(self) -> SDEStatus:
        """Get current SDE database status."""
        conn = self.market_db._get_connection()

        # Check if SDE tables exist
        cursor = conn.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name IN ('groups', 'categories', 'blueprints')
        """)
        tables = [row[0] for row in cursor.fetchall()]

        if len(tables) < 3:
            return SDEStatus(seeded=False)

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
            # Region count (may not exist in older schemas)
            try:
                region_count = conn.execute("SELECT COUNT(*) FROM regions").fetchone()[0]
            except sqlite3.OperationalError:
                region_count = 0
            # Station count (may not exist in older schemas)
            try:
                station_count = conn.execute("SELECT COUNT(*) FROM stations").fetchone()[0]
            except sqlite3.OperationalError:
                station_count = 0
            # Skill attribute count (may not exist in older schemas)
            try:
                skill_attr_count = conn.execute("SELECT COUNT(*) FROM skill_attributes").fetchone()[
                    0
                ]
            except sqlite3.OperationalError:
                skill_attr_count = 0
            # Skill prerequisite count (may not exist in older schemas)
            try:
                skill_prereq_count = conn.execute(
                    "SELECT COUNT(*) FROM skill_prerequisites"
                ).fetchone()[0]
            except sqlite3.OperationalError:
                skill_prereq_count = 0
            # Type skill requirement count (may not exist in older schemas)
            try:
                type_req_count = conn.execute(
                    "SELECT COUNT(*) FROM type_skill_requirements"
                ).fetchone()[0]
            except sqlite3.OperationalError:
                type_req_count = 0
            # Agent division count (may not exist in older schemas)
            try:
                agent_div_count = conn.execute("SELECT COUNT(*) FROM agent_divisions").fetchone()[0]
            except sqlite3.OperationalError:
                agent_div_count = 0
            # Agent type count (may not exist in older schemas)
            try:
                agent_type_count = conn.execute("SELECT COUNT(*) FROM agent_types").fetchone()[0]
            except sqlite3.OperationalError:
                agent_type_count = 0
            # Agent count (may not exist in older schemas)
            try:
                agent_count = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
            except sqlite3.OperationalError:
                agent_count = 0
            # Meta group count (may not exist in older schemas)
            try:
                meta_group_count = conn.execute("SELECT COUNT(*) FROM meta_groups").fetchone()[0]
            except sqlite3.OperationalError:
                meta_group_count = 0
            # Meta type count (may not exist in older schemas)
            try:
                meta_type_count = conn.execute("SELECT COUNT(*) FROM meta_types").fetchone()[0]
            except sqlite3.OperationalError:
                meta_type_count = 0
        except sqlite3.OperationalError:
            return SDEStatus(seeded=False)

        # Get metadata
        try:
            version_row = conn.execute(
                "SELECT value FROM metadata WHERE key = 'sde_schema_version'"
            ).fetchone()
            timestamp_row = conn.execute(
                "SELECT value FROM metadata WHERE key = 'sde_import_timestamp'"
            ).fetchone()
            checksum_row = conn.execute(
                "SELECT value FROM metadata WHERE key = 'sde_source_checksum'"
            ).fetchone()
        except sqlite3.OperationalError:
            version_row = None
            timestamp_row = None
            checksum_row = None

        return SDEStatus(
            seeded=blueprint_count > 0,
            category_count=category_count,
            group_count=group_count,
            type_count=type_count,
            blueprint_count=blueprint_count,
            npc_seeding_count=seeding_count,
            npc_corp_count=corp_count,
            region_count=region_count,
            station_count=station_count,
            skill_attribute_count=skill_attr_count,
            skill_prerequisite_count=skill_prereq_count,
            type_skill_requirement_count=type_req_count,
            agent_division_count=agent_div_count,
            agent_type_count=agent_type_count,
            agent_count=agent_count,
            meta_group_count=meta_group_count,
            meta_type_count=meta_type_count,
            sde_version=version_row[0] if version_row else None,
            import_timestamp=timestamp_row[0] if timestamp_row else None,
            source_checksum=checksum_row[0] if checksum_row else None,
        )


# =============================================================================
# Module Functions
# =============================================================================


def seed_sde(
    market_db: MarketDatabase,
    progress_callback=None,
    break_glass: bool = False,
    show_checksum: bool = False,
) -> SDEImportResult:
    """
    Download and import SDE data.

    Convenience function that handles the full import workflow.

    Args:
        market_db: MarketDatabase instance to import into
        progress_callback: Optional progress callback
        break_glass: If True, skip checksum verification
        show_checksum: If True, display the SHA256 checksum after download

    Returns:
        SDEImportResult with import statistics
    """
    importer = SDEImporter(market_db)
    result = SDEImportResult(success=False)

    try:
        # Download
        start = time.time()
        sde_path = importer.download_sde(
            progress_callback,
            break_glass=break_glass,
            show_checksum=show_checksum,
        )
        result.download_time_seconds = time.time() - start

        # Import
        import_result = importer.import_from_sde(sde_path, progress_callback)

        # Merge results
        result.success = import_result.success
        result.categories_imported = import_result.categories_imported
        result.groups_imported = import_result.groups_imported
        result.types_imported = import_result.types_imported
        result.blueprints_imported = import_result.blueprints_imported
        result.blueprint_products_imported = import_result.blueprint_products_imported
        result.blueprint_materials_imported = import_result.blueprint_materials_imported
        result.npc_seeding_imported = import_result.npc_seeding_imported
        result.npc_corporations_imported = import_result.npc_corporations_imported
        result.regions_imported = import_result.regions_imported
        result.stations_imported = import_result.stations_imported
        result.skill_attributes_imported = import_result.skill_attributes_imported
        result.skill_prerequisites_imported = import_result.skill_prerequisites_imported
        result.type_skill_requirements_imported = import_result.type_skill_requirements_imported
        result.agent_divisions_imported = import_result.agent_divisions_imported
        result.agent_types_imported = import_result.agent_types_imported
        result.agents_imported = import_result.agents_imported
        result.meta_groups_imported = import_result.meta_groups_imported
        result.meta_types_imported = import_result.meta_types_imported
        result.import_time_seconds = import_result.import_time_seconds
        result.error = import_result.error

    except Exception as e:
        result.error = str(e)
        logger.error("SDE seed failed: %s", e)

    finally:
        importer.cleanup()

    return result
