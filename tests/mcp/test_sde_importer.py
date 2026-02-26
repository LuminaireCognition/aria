"""Tests for SDE Importer.

Covers:
- _qi() SQL identifier validation and quoting
- SDEImportResult dataclass defaults and field assignment
- SDEImporter.initialize_schema() table creation and idempotency
- Import methods: categories, groups, types, blueprints, blueprint products,
  blueprint materials
- download_sde() checksum verification and break-glass mode
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aria_esi.store.market.database import MarketDatabase
from aria_esi.store.sde.importer import (
    _VALID_SDE_IDENTIFIERS,
    SDEImporter,
    SDEImportResult,
    _qi,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_market_db(tmp_path):
    """Create a temporary MarketDatabase for testing."""
    db_path = tmp_path / "test_market.db"
    db = MarketDatabase(db_path)
    yield db
    db.close()


@pytest.fixture
def sde_source_db():
    """Create an in-memory SQLite database mimicking Fuzzwork SDE structure.

    Includes invCategories, invGroups, invTypes (with marketGroupID and
    packagedVolume), industryBlueprints, industryActivities,
    industryActivityProducts, and industryActivityMaterials with minimal
    test data.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE invCategories (
            categoryID INTEGER PRIMARY KEY,
            categoryName TEXT,
            published INTEGER DEFAULT 1
        );

        CREATE TABLE invGroups (
            groupID INTEGER PRIMARY KEY,
            categoryID INTEGER,
            groupName TEXT,
            published INTEGER DEFAULT 1
        );

        CREATE TABLE invTypes (
            typeID INTEGER PRIMARY KEY,
            groupID INTEGER,
            typeName TEXT,
            volume REAL,
            packagedVolume REAL,
            marketGroupID INTEGER,
            description TEXT,
            published INTEGER DEFAULT 1
        );

        CREATE TABLE industryBlueprints (
            typeID INTEGER PRIMARY KEY,
            maxProductionLimit INTEGER
        );

        CREATE TABLE industryActivities (
            blueprintTypeID INTEGER,
            activityID INTEGER,
            time INTEGER,
            PRIMARY KEY (blueprintTypeID, activityID)
        );

        CREATE TABLE industryActivityProducts (
            blueprintTypeID INTEGER,
            activityID INTEGER,
            productTypeID INTEGER,
            quantity INTEGER
        );

        CREATE TABLE industryActivityMaterials (
            blueprintTypeID INTEGER,
            activityID INTEGER,
            materialTypeID INTEGER,
            quantity INTEGER
        );
    """)

    # Insert test data
    conn.executemany(
        "INSERT INTO invCategories (categoryID, categoryName, published) VALUES (?, ?, ?)",
        [
            (6, "Ship", 1),
            (7, "Module", 1),
            (8, "Charge", 1),
            (99, "Unpublished Category", 0),
        ],
    )
    conn.executemany(
        "INSERT INTO invGroups (groupID, categoryID, groupName, published) VALUES (?, ?, ?, ?)",
        [
            (25, 6, "Frigate", 1),
            (26, 6, "Cruiser", 1),
            (27, 7, "Armor Repair", 1),
            (999, 99, "Unpublished Group", 0),
        ],
    )
    conn.executemany(
        "INSERT INTO invTypes (typeID, groupID, typeName, volume, packagedVolume, "
        "marketGroupID, description, published) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (587, 25, "Rifter", 27289.0, 2500.0, 100, "A fast Minmatar frigate", 1),
            (24690, 26, "Vexor", 101000.0, 10000.0, 200, "A Gallente cruiser", 1),
            (688, 25, "Rifter Blueprint", 0.01, 0.01, None, "Blueprint for Rifter", 1),
            (9999, 25, "Hidden Ship", 1000.0, 500.0, None, "Unpublished item", 0),
        ],
    )
    conn.executemany("INSERT INTO industryBlueprints (typeID, maxProductionLimit) VALUES (?, ?)", [
        (688, 300),
    ])
    conn.executemany(
        "INSERT INTO industryActivities (blueprintTypeID, activityID, time) VALUES (?, ?, ?)",
        [
            (688, 1, 6000),   # Manufacturing
            (688, 3, 1200),   # TE research
            (688, 4, 1200),   # ME research
            (688, 5, 3000),   # Copying
            (688, 8, 18000),  # Invention
        ],
    )
    conn.executemany(
        "INSERT INTO industryActivityProducts "
        "(blueprintTypeID, activityID, productTypeID, quantity) VALUES (?, ?, ?, ?)",
        [
            (688, 1, 587, 1),  # Rifter Blueprint produces Rifter
        ],
    )
    conn.executemany(
        "INSERT INTO industryActivityMaterials "
        "(blueprintTypeID, activityID, materialTypeID, quantity) VALUES (?, ?, ?, ?)",
        [
            (688, 1, 34, 2200),   # Tritanium for manufacturing
            (688, 1, 35, 2400),   # Pyerite for manufacturing
            (688, 9, 34, 100),    # Tritanium for reactions
        ],
    )
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def sde_source_no_packaged_volume():
    """SDE source database without packagedVolume column in invTypes."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE invCategories (
            categoryID INTEGER PRIMARY KEY,
            categoryName TEXT,
            published INTEGER DEFAULT 1
        );

        CREATE TABLE invGroups (
            groupID INTEGER PRIMARY KEY,
            categoryID INTEGER,
            groupName TEXT,
            published INTEGER DEFAULT 1
        );

        CREATE TABLE invTypes (
            typeID INTEGER PRIMARY KEY,
            groupID INTEGER,
            typeName TEXT,
            volume REAL,
            marketGroupID INTEGER,
            description TEXT,
            published INTEGER DEFAULT 1
        );
    """)
    conn.executemany(
        "INSERT INTO invCategories (categoryID, categoryName, published) VALUES (?, ?, ?)",
        [(6, "Ship", 1)],
    )
    conn.executemany(
        "INSERT INTO invGroups (groupID, categoryID, groupName, published) VALUES (?, ?, ?, ?)",
        [(25, 6, "Frigate", 1)],
    )
    conn.executemany(
        "INSERT INTO invTypes (typeID, groupID, typeName, volume, marketGroupID, "
        "description, published) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (587, 25, "Rifter", 27289.0, 100, "A fast Minmatar frigate", 1),
        ],
    )
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def sde_source_no_blueprints():
    """SDE source database without industryBlueprints table.

    This exercises the fallback path that identifies blueprints by name.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE invCategories (
            categoryID INTEGER PRIMARY KEY,
            categoryName TEXT,
            published INTEGER DEFAULT 1
        );

        CREATE TABLE invGroups (
            groupID INTEGER PRIMARY KEY,
            categoryID INTEGER,
            groupName TEXT,
            published INTEGER DEFAULT 1
        );

        CREATE TABLE invTypes (
            typeID INTEGER PRIMARY KEY,
            groupID INTEGER,
            typeName TEXT,
            volume REAL,
            packagedVolume REAL,
            marketGroupID INTEGER,
            description TEXT,
            published INTEGER DEFAULT 1
        );
    """)
    conn.executemany(
        "INSERT INTO invCategories (categoryID, categoryName, published) VALUES (?, ?, ?)",
        [(6, "Ship", 1), (9, "Blueprint", 1)],
    )
    conn.executemany(
        "INSERT INTO invGroups (groupID, categoryID, groupName, published) VALUES (?, ?, ?, ?)",
        [(25, 6, "Frigate", 1), (105, 9, "Frigate Blueprint", 1)],
    )
    conn.executemany(
        "INSERT INTO invTypes (typeID, groupID, typeName, volume, packagedVolume, "
        "marketGroupID, description, published) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (587, 25, "Rifter", 27289.0, 2500.0, 100, "A fast Minmatar frigate", 1),
            (688, 105, "Rifter Blueprint", 0.01, 0.01, None, "Blueprint", 1),
        ],
    )
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def importer(temp_market_db):
    """Create an SDEImporter with a temporary MarketDatabase."""
    return SDEImporter(temp_market_db)


# =============================================================================
# Tests: _qi() SQL Identifier Validation
# =============================================================================


class TestQiIdentifierValidation:
    """Tests for _qi() SQL identifier allowlist function."""

    def test_valid_identifier_typeID(self):
        """Standard column name returns double-quoted identifier."""
        assert _qi("typeID") == '"typeID"'

    def test_valid_identifier_blueprintTypeID(self):
        """Blueprint column name returns double-quoted identifier."""
        assert _qi("blueprintTypeID") == '"blueprintTypeID"'

    def test_valid_identifier_productTypeID(self):
        """Product column name returns double-quoted identifier."""
        assert _qi("productTypeID") == '"productTypeID"'

    def test_valid_identifier_categoryID(self):
        """All registered SDE identifiers should be accepted."""
        # Test a sampling of identifiers from different table domains
        for name in ["corporationID", "regionID", "agentID", "metaGroupID", "level"]:
            result = _qi(name)
            assert result == f'"{name}"', f"Expected quoted {name}"

    def test_sql_literal_null(self):
        """SQL literal NULL is returned unquoted."""
        assert _qi("NULL") == "NULL"

    def test_sql_literal_one(self):
        """SQL literal 1 is returned unquoted."""
        assert _qi("1") == "1"

    def test_invalid_identifier_raises_valueerror(self):
        """Unknown identifier raises ValueError."""
        with pytest.raises(ValueError, match="Unknown SDE identifier"):
            _qi("DROP TABLE users")

    def test_sql_injection_attempt_raises(self):
        """Identifier containing SQL injection payload is rejected."""
        with pytest.raises(ValueError):
            _qi("typeID; DROP TABLE--")

    def test_empty_string_raises(self):
        """Empty string is not a valid identifier."""
        with pytest.raises(ValueError):
            _qi("")

    def test_similar_but_invalid_identifier(self):
        """Identifier not in allowlist but similar to valid ones is rejected."""
        with pytest.raises(ValueError):
            _qi("typeId")  # wrong case

    def test_all_allowlisted_identifiers_pass(self):
        """Every identifier in the allowlist should be accepted by _qi()."""
        for ident in _VALID_SDE_IDENTIFIERS:
            result = _qi(ident)
            if ident in ("NULL", "1"):
                assert result == ident
            else:
                assert result == f'"{ident}"'


# =============================================================================
# Tests: SDEImportResult Dataclass
# =============================================================================


class TestSDEImportResult:
    """Tests for SDEImportResult dataclass defaults and field assignment."""

    def test_success_defaults(self):
        """Successful result has zero counts and no error by default."""
        result = SDEImportResult(success=True)
        assert result.success is True
        assert result.categories_imported == 0
        assert result.groups_imported == 0
        assert result.types_imported == 0
        assert result.blueprints_imported == 0
        assert result.blueprint_products_imported == 0
        assert result.blueprint_materials_imported == 0
        assert result.npc_seeding_imported == 0
        assert result.npc_corporations_imported == 0
        assert result.regions_imported == 0
        assert result.stations_imported == 0
        assert result.skill_attributes_imported == 0
        assert result.skill_prerequisites_imported == 0
        assert result.type_skill_requirements_imported == 0
        assert result.agent_divisions_imported == 0
        assert result.agent_types_imported == 0
        assert result.agents_imported == 0
        assert result.meta_groups_imported == 0
        assert result.meta_types_imported == 0
        assert result.download_time_seconds == 0.0
        assert result.import_time_seconds == 0.0
        assert result.error is None

    def test_failure_with_error(self):
        """Failed result stores error message."""
        result = SDEImportResult(success=False, error="Download failed")
        assert result.success is False
        assert result.error == "Download failed"

    def test_individual_counts(self):
        """Can set individual import counts."""
        result = SDEImportResult(
            success=True,
            categories_imported=10,
            groups_imported=50,
            types_imported=45000,
            blueprints_imported=1200,
        )
        assert result.categories_imported == 10
        assert result.groups_imported == 50
        assert result.types_imported == 45000
        assert result.blueprints_imported == 1200
        # Others remain at default
        assert result.npc_seeding_imported == 0

    def test_timing_fields(self):
        """Timing fields can be set."""
        result = SDEImportResult(
            success=True,
            download_time_seconds=12.5,
            import_time_seconds=3.7,
        )
        assert result.download_time_seconds == 12.5
        assert result.import_time_seconds == 3.7


# =============================================================================
# Tests: SDEImporter.initialize_schema()
# =============================================================================


class TestInitializeSchema:
    """Tests for schema initialization and idempotency."""

    def test_creates_sde_tables(self, importer, temp_market_db):
        """initialize_schema creates categories, groups, blueprints tables."""
        importer.initialize_schema()
        conn = temp_market_db._get_connection()

        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in cursor.fetchall()}

        # SDE tables
        assert "categories" in tables
        assert "groups" in tables
        assert "blueprints" in tables
        assert "blueprint_products" in tables
        assert "blueprint_materials" in tables
        assert "npc_seeding" in tables
        assert "npc_corporations" in tables
        assert "regions" in tables
        assert "stations" in tables
        # Skill tables
        assert "skill_attributes" in tables
        assert "skill_prerequisites" in tables
        assert "type_skill_requirements" in tables
        # Agent tables
        assert "agent_divisions" in tables
        assert "agent_types" in tables
        assert "agents" in tables
        # Meta type tables
        assert "meta_groups" in tables
        assert "meta_types" in tables

    def test_idempotent(self, importer, temp_market_db):
        """Running initialize_schema twice does not raise errors."""
        importer.initialize_schema()
        # Second call should succeed without errors
        importer.initialize_schema()

        conn = temp_market_db._get_connection()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='categories'"
        )
        assert cursor.fetchone() is not None

    def test_adds_description_column(self, importer, temp_market_db):
        """initialize_schema adds description column to types table if missing."""
        conn = temp_market_db._get_connection()

        # Before schema init, check that the base types table exists
        # (MarketDatabase creates it on init)
        cursor = conn.execute("PRAGMA table_info(types)")
        columns_before = {row[1] for row in cursor.fetchall()}

        importer.initialize_schema()

        cursor = conn.execute("PRAGMA table_info(types)")
        columns_after = {row[1] for row in cursor.fetchall()}

        assert "description" in columns_after
        assert "published" in columns_after

    def test_adds_published_column(self, importer, temp_market_db):
        """initialize_schema adds published column to types table if missing."""
        importer.initialize_schema()
        conn = temp_market_db._get_connection()

        cursor = conn.execute("PRAGMA table_info(types)")
        columns = {row[1] for row in cursor.fetchall()}
        assert "published" in columns


# =============================================================================
# Tests: _import_categories
# =============================================================================


class TestImportCategories:
    """Tests for category import from SDE source."""

    def test_imports_published_categories(self, importer, temp_market_db, sde_source_db):
        """Only published categories are imported."""
        importer.initialize_schema()
        target_conn = temp_market_db._get_connection()

        count = importer._import_categories(sde_source_db, target_conn)

        # 3 published categories (Ship, Module, Charge); 1 unpublished is skipped
        assert count == 3

        cursor = target_conn.execute("SELECT * FROM categories ORDER BY category_id")
        rows = cursor.fetchall()
        assert len(rows) == 3
        assert rows[0]["category_name"] == "Ship"
        assert rows[1]["category_name"] == "Module"
        assert rows[2]["category_name"] == "Charge"

    def test_lowercase_names(self, importer, temp_market_db, sde_source_db):
        """Imported categories have lowercased name field for search."""
        importer.initialize_schema()
        target_conn = temp_market_db._get_connection()

        importer._import_categories(sde_source_db, target_conn)

        cursor = target_conn.execute("SELECT category_name_lower FROM categories WHERE category_id = 6")
        row = cursor.fetchone()
        assert row["category_name_lower"] == "ship"

    def test_empty_source(self, importer, temp_market_db):
        """Import from empty source returns zero."""
        importer.initialize_schema()
        target_conn = temp_market_db._get_connection()

        empty_conn = sqlite3.connect(":memory:")
        empty_conn.row_factory = sqlite3.Row
        empty_conn.execute(
            "CREATE TABLE invCategories "
            "(categoryID INTEGER PRIMARY KEY, categoryName TEXT, published INTEGER DEFAULT 1)"
        )
        empty_conn.commit()

        count = importer._import_categories(empty_conn, target_conn)
        assert count == 0

        empty_conn.close()

    def test_upsert_on_reimport(self, importer, temp_market_db, sde_source_db):
        """Re-importing same categories does not create duplicates."""
        importer.initialize_schema()
        target_conn = temp_market_db._get_connection()

        count1 = importer._import_categories(sde_source_db, target_conn)
        count2 = importer._import_categories(sde_source_db, target_conn)

        assert count1 == count2

        cursor = target_conn.execute("SELECT COUNT(*) as cnt FROM categories")
        assert cursor.fetchone()["cnt"] == 3


# =============================================================================
# Tests: _import_groups
# =============================================================================


class TestImportGroups:
    """Tests for group import from SDE source."""

    def test_imports_published_groups(self, importer, temp_market_db, sde_source_db):
        """Only published groups are imported."""
        importer.initialize_schema()
        target_conn = temp_market_db._get_connection()

        count = importer._import_groups(sde_source_db, target_conn)

        # 3 published groups (Frigate, Cruiser, Armor Repair); 1 unpublished is skipped
        assert count == 3

    def test_preserves_category_id(self, importer, temp_market_db, sde_source_db):
        """Group records include their parent category_id."""
        importer.initialize_schema()
        target_conn = temp_market_db._get_connection()

        importer._import_groups(sde_source_db, target_conn)

        cursor = target_conn.execute("SELECT category_id FROM groups WHERE group_id = 25")
        row = cursor.fetchone()
        assert row["category_id"] == 6  # Ship

    def test_lowercase_names(self, importer, temp_market_db, sde_source_db):
        """Group names are lowercased for search."""
        importer.initialize_schema()
        target_conn = temp_market_db._get_connection()

        importer._import_groups(sde_source_db, target_conn)

        cursor = target_conn.execute("SELECT group_name_lower FROM groups WHERE group_id = 27")
        row = cursor.fetchone()
        assert row["group_name_lower"] == "armor repair"


# =============================================================================
# Tests: _import_types
# =============================================================================


class TestImportTypes:
    """Tests for type import from SDE source."""

    def test_imports_all_types_including_unpublished(self, importer, temp_market_db, sde_source_db):
        """_import_types imports all types (no published filter in its query)."""
        importer.initialize_schema()
        target_conn = temp_market_db._get_connection()

        count = importer._import_types(sde_source_db, target_conn)

        # All 4 types including unpublished
        assert count == 4

    def test_type_fields_populated(self, importer, temp_market_db, sde_source_db):
        """Imported types have all expected fields."""
        importer.initialize_schema()
        target_conn = temp_market_db._get_connection()

        importer._import_types(sde_source_db, target_conn)

        cursor = target_conn.execute("SELECT * FROM types WHERE type_id = 587")
        row = cursor.fetchone()
        assert row["type_name"] == "Rifter"
        assert row["type_name_lower"] == "rifter"
        assert row["group_id"] == 25
        assert row["category_id"] == 6  # Joined from invGroups
        assert row["volume"] == 27289.0
        assert row["packaged_volume"] == 2500.0
        assert row["description"] == "A fast Minmatar frigate"
        assert row["published"] == 1

    def test_handles_missing_packaged_volume(
        self, importer, temp_market_db, sde_source_no_packaged_volume
    ):
        """When packagedVolume column is absent, NULL is used instead."""
        importer.initialize_schema()
        target_conn = temp_market_db._get_connection()

        count = importer._import_types(sde_source_no_packaged_volume, target_conn)
        assert count == 1

        cursor = target_conn.execute("SELECT packaged_volume FROM types WHERE type_id = 587")
        row = cursor.fetchone()
        assert row["packaged_volume"] is None

    def test_lowercase_names(self, importer, temp_market_db, sde_source_db):
        """Type names are lowercased for search."""
        importer.initialize_schema()
        target_conn = temp_market_db._get_connection()

        importer._import_types(sde_source_db, target_conn)

        cursor = target_conn.execute(
            "SELECT type_name_lower FROM types WHERE type_id = 24690"
        )
        row = cursor.fetchone()
        assert row["type_name_lower"] == "vexor"

    def test_joins_category_from_groups(self, importer, temp_market_db, sde_source_db):
        """category_id is populated via LEFT JOIN on invGroups."""
        importer.initialize_schema()
        target_conn = temp_market_db._get_connection()

        importer._import_types(sde_source_db, target_conn)

        cursor = target_conn.execute("SELECT category_id FROM types WHERE type_id = 24690")
        row = cursor.fetchone()
        assert row["category_id"] == 6  # Cruiser group belongs to Ship category

    def test_chunked_import_large_batch(self, importer, temp_market_db):
        """Types are imported in chunks of 10000 for large datasets."""
        importer.initialize_schema()
        target_conn = temp_market_db._get_connection()

        # Create a source with more than 10000 items
        source_conn = sqlite3.connect(":memory:")
        source_conn.row_factory = sqlite3.Row
        source_conn.executescript("""
            CREATE TABLE invGroups (
                groupID INTEGER PRIMARY KEY,
                categoryID INTEGER,
                groupName TEXT,
                published INTEGER DEFAULT 1
            );
            CREATE TABLE invTypes (
                typeID INTEGER PRIMARY KEY,
                groupID INTEGER,
                typeName TEXT,
                volume REAL,
                packagedVolume REAL,
                marketGroupID INTEGER,
                description TEXT,
                published INTEGER DEFAULT 1
            );
        """)
        source_conn.execute(
            "INSERT INTO invGroups VALUES (1, 1, 'TestGroup', 1)"
        )

        # Insert 15000 types to test chunked insertion
        batch = [(i, 1, f"Type {i}", 1.0, 1.0, 1, f"Desc {i}", 1) for i in range(15000)]
        source_conn.executemany(
            "INSERT INTO invTypes VALUES (?, ?, ?, ?, ?, ?, ?, ?)", batch
        )
        source_conn.commit()

        count = importer._import_types(source_conn, target_conn)
        assert count == 15000

        cursor = target_conn.execute("SELECT COUNT(*) as cnt FROM types")
        assert cursor.fetchone()["cnt"] == 15000

        source_conn.close()


# =============================================================================
# Tests: _import_blueprints
# =============================================================================


class TestImportBlueprints:
    """Tests for blueprint import from SDE source."""

    def test_imports_from_industry_blueprints(self, importer, temp_market_db, sde_source_db):
        """Blueprints are imported from industryBlueprints table."""
        importer.initialize_schema()
        target_conn = temp_market_db._get_connection()

        count = importer._import_blueprints(sde_source_db, target_conn)
        assert count == 1

        cursor = target_conn.execute("SELECT * FROM blueprints WHERE type_id = 688")
        row = cursor.fetchone()
        assert row is not None
        assert row["max_production_limit"] == 300

    def test_activity_times_populated(self, importer, temp_market_db, sde_source_db):
        """Activity times from industryActivities are stored correctly."""
        importer.initialize_schema()
        target_conn = temp_market_db._get_connection()

        importer._import_blueprints(sde_source_db, target_conn)

        cursor = target_conn.execute("SELECT * FROM blueprints WHERE type_id = 688")
        row = cursor.fetchone()
        assert row["manufacturing_time"] == 6000       # activityID 1
        assert row["copying_time"] == 3000              # activityID 5
        assert row["research_material_time"] == 1200    # activityID 4
        assert row["research_time_time"] == 1200        # activityID 3
        assert row["invention_time"] == 18000           # activityID 8

    def test_fallback_without_industry_blueprints(
        self, importer, temp_market_db, sde_source_no_blueprints
    ):
        """When industryBlueprints table is missing, blueprints are inferred by name."""
        importer.initialize_schema()
        target_conn = temp_market_db._get_connection()

        count = importer._import_blueprints(sde_source_no_blueprints, target_conn)
        assert count == 1

        cursor = target_conn.execute("SELECT * FROM blueprints WHERE type_id = 688")
        row = cursor.fetchone()
        assert row is not None
        # Fallback uses default max runs of 10
        assert row["max_production_limit"] == 10
        # No activity times available in fallback
        assert row["manufacturing_time"] is None
        assert row["copying_time"] is None

    def test_no_blueprints_returns_zero(self, importer, temp_market_db):
        """Source with no matching blueprints returns zero."""
        importer.initialize_schema()
        target_conn = temp_market_db._get_connection()

        empty_conn = sqlite3.connect(":memory:")
        empty_conn.row_factory = sqlite3.Row
        # No blueprint tables, no types with "Blueprint" in name
        empty_conn.executescript("""
            CREATE TABLE invTypes (
                typeID INTEGER PRIMARY KEY,
                typeName TEXT,
                published INTEGER DEFAULT 1
            );
        """)
        empty_conn.execute("INSERT INTO invTypes VALUES (1, 'Rifter', 1)")
        empty_conn.commit()

        count = importer._import_blueprints(empty_conn, target_conn)
        assert count == 0

        empty_conn.close()

    def test_blueprint_without_activities(self, importer, temp_market_db):
        """Blueprint with no industryActivities has NULL activity times."""
        importer.initialize_schema()
        target_conn = temp_market_db._get_connection()

        source_conn = sqlite3.connect(":memory:")
        source_conn.row_factory = sqlite3.Row
        source_conn.executescript("""
            CREATE TABLE industryBlueprints (
                typeID INTEGER PRIMARY KEY,
                maxProductionLimit INTEGER
            );
        """)
        source_conn.execute("INSERT INTO industryBlueprints VALUES (100, 50)")
        source_conn.commit()

        count = importer._import_blueprints(source_conn, target_conn)
        assert count == 1

        cursor = target_conn.execute("SELECT * FROM blueprints WHERE type_id = 100")
        row = cursor.fetchone()
        assert row["manufacturing_time"] is None
        assert row["copying_time"] is None
        assert row["max_production_limit"] == 50

        source_conn.close()


# =============================================================================
# Tests: _import_blueprint_products
# =============================================================================


class TestImportBlueprintProducts:
    """Tests for blueprint product import from SDE source."""

    def test_imports_manufacturing_products(self, importer, temp_market_db, sde_source_db):
        """Blueprint products for manufacturing (activityID=1) are imported."""
        importer.initialize_schema()
        target_conn = temp_market_db._get_connection()

        # Need types imported first so product filtering works
        importer._import_types(sde_source_db, target_conn)
        count = importer._import_blueprint_products(sde_source_db, target_conn)

        assert count == 1

        cursor = target_conn.execute(
            "SELECT * FROM blueprint_products WHERE blueprint_type_id = 688"
        )
        row = cursor.fetchone()
        assert row["product_type_id"] == 587  # Rifter
        assert row["quantity"] == 1

    def test_filters_orphan_products(self, importer, temp_market_db):
        """Products referencing non-existent types are filtered out."""
        importer.initialize_schema()
        target_conn = temp_market_db._get_connection()

        source_conn = sqlite3.connect(":memory:")
        source_conn.row_factory = sqlite3.Row
        source_conn.executescript("""
            CREATE TABLE industryActivityProducts (
                blueprintTypeID INTEGER,
                activityID INTEGER,
                productTypeID INTEGER,
                quantity INTEGER
            );
        """)
        # Product type 99999 does not exist in target types table
        source_conn.execute(
            "INSERT INTO industryActivityProducts VALUES (100, 1, 99999, 1)"
        )
        source_conn.commit()

        count = importer._import_blueprint_products(source_conn, target_conn)
        assert count == 0

        source_conn.close()

    def test_fallback_infer_from_names(self, importer, temp_market_db, sde_source_no_blueprints):
        """Without industryActivityProducts, products are inferred from names."""
        importer.initialize_schema()
        target_conn = temp_market_db._get_connection()

        # Need types imported for name-based fallback
        importer._import_types(sde_source_no_blueprints, target_conn)
        count = importer._import_blueprint_products(sde_source_no_blueprints, target_conn)

        # "Rifter Blueprint" should infer product "Rifter"
        assert count == 1

        cursor = target_conn.execute(
            "SELECT * FROM blueprint_products WHERE blueprint_type_id = 688"
        )
        row = cursor.fetchone()
        assert row["product_type_id"] == 587


# =============================================================================
# Tests: _import_blueprint_materials
# =============================================================================


class TestImportBlueprintMaterials:
    """Tests for blueprint material import from SDE source."""

    def test_imports_manufacturing_materials(self, importer, temp_market_db, sde_source_db):
        """Materials for manufacturing and reaction activities are imported."""
        importer.initialize_schema()
        target_conn = temp_market_db._get_connection()

        count = importer._import_blueprint_materials(sde_source_db, target_conn)

        # 2 manufacturing materials + 1 reaction material = 3
        assert count == 3

    def test_returns_zero_when_table_missing(self, importer, temp_market_db):
        """Returns zero when industryActivityMaterials table does not exist."""
        importer.initialize_schema()
        target_conn = temp_market_db._get_connection()

        empty_conn = sqlite3.connect(":memory:")
        empty_conn.row_factory = sqlite3.Row
        # Create a minimal schema without the materials table
        empty_conn.execute("CREATE TABLE placeholder (id INTEGER)")
        empty_conn.commit()

        count = importer._import_blueprint_materials(empty_conn, target_conn)
        assert count == 0

        empty_conn.close()

    def test_material_quantities(self, importer, temp_market_db, sde_source_db):
        """Material quantities match SDE source data."""
        importer.initialize_schema()
        target_conn = temp_market_db._get_connection()

        importer._import_blueprint_materials(sde_source_db, target_conn)

        cursor = target_conn.execute(
            "SELECT material_type_id, quantity, activity_id "
            "FROM blueprint_materials WHERE blueprint_type_id = 688 "
            "ORDER BY material_type_id, activity_id"
        )
        rows = cursor.fetchall()

        # Tritanium manufacturing
        assert rows[0]["material_type_id"] == 34
        assert rows[0]["quantity"] == 2200
        assert rows[0]["activity_id"] == 1

        # Tritanium reaction
        assert rows[1]["material_type_id"] == 34
        assert rows[1]["quantity"] == 100
        assert rows[1]["activity_id"] == 9

        # Pyerite manufacturing
        assert rows[2]["material_type_id"] == 35
        assert rows[2]["quantity"] == 2400
        assert rows[2]["activity_id"] == 1


# =============================================================================
# Tests: import_from_sde (Integration)
# =============================================================================


class TestImportFromSDE:
    """Tests for the full import_from_sde workflow using a file-based SDE source."""

    def test_full_import(self, importer, temp_market_db, sde_source_db, tmp_path):
        """Full import populates target database with all data."""
        # Write SDE source to a file (import_from_sde opens its own connection)
        sde_path = tmp_path / "sde_source.sqlite"
        file_conn = sqlite3.connect(str(sde_path))
        sde_source_db.backup(file_conn)
        file_conn.close()

        result = importer.import_from_sde(sde_path)

        assert result.success is True
        assert result.categories_imported == 3
        assert result.groups_imported == 3
        assert result.types_imported == 4
        assert result.blueprints_imported == 1
        assert result.blueprint_products_imported == 1
        assert result.blueprint_materials_imported == 3
        assert result.error is None
        assert result.import_time_seconds > 0

    def test_progress_callback(self, importer, temp_market_db, sde_source_db, tmp_path):
        """Progress callback receives step names and counts."""
        sde_path = tmp_path / "sde_source.sqlite"
        file_conn = sqlite3.connect(str(sde_path))
        sde_source_db.backup(file_conn)
        file_conn.close()

        calls = []
        importer.import_from_sde(sde_path, progress_callback=lambda step, count: calls.append((step, count)))

        step_names = [c[0] for c in calls]
        assert "categories" in step_names
        assert "groups" in step_names
        assert "types" in step_names
        assert "blueprints" in step_names

    def test_import_failure_returns_error(self, importer, tmp_path):
        """Import from non-existent file returns error result."""
        bad_path = tmp_path / "nonexistent.sqlite"

        result = importer.import_from_sde(bad_path)

        assert result.success is False
        assert result.error is not None

    def test_metadata_timestamp(self, importer, temp_market_db, sde_source_db, tmp_path):
        """Import stores timestamp in metadata table."""
        sde_path = tmp_path / "sde_source.sqlite"
        file_conn = sqlite3.connect(str(sde_path))
        sde_source_db.backup(file_conn)
        file_conn.close()

        result = importer.import_from_sde(sde_path)
        assert result.success is True

        conn = temp_market_db._get_connection()
        cursor = conn.execute(
            "SELECT value FROM metadata WHERE key = 'sde_import_timestamp'"
        )
        row = cursor.fetchone()
        assert row is not None
        assert len(row["value"]) > 0  # ISO format timestamp


# =============================================================================
# Tests: download_sde
# =============================================================================


class TestDownloadSDE:
    """Tests for download_sde() checksum verification and break-glass mode.

    All network and file I/O is mocked to avoid real downloads.
    """

    @patch("aria_esi.store.sde.importer.verify_sde_integrity")
    @patch("aria_esi.store.sde.importer.compute_sha256")
    @patch("aria_esi.store.sde.importer.is_break_glass_enabled")
    @patch("aria_esi.store.sde.importer.get_pinned_sde_url")
    @patch("aria_esi.store.sde.importer.httpx")
    @patch("aria_esi.store.sde.importer.bz2")
    def test_checksum_pass(
        self, mock_bz2, mock_httpx, mock_get_url, mock_break_glass, mock_sha256, mock_verify, importer, tmp_path
    ):
        """Successful download with matching checksum returns decompressed path."""
        expected_checksum = "abc123def456"
        mock_get_url.return_value = ("https://example.com/sde.bz2", expected_checksum)
        mock_break_glass.return_value = False
        mock_sha256.return_value = expected_checksum
        mock_verify.return_value = (True, expected_checksum)

        # Mock httpx.stream context manager
        mock_response = MagicMock()
        mock_response.headers = {"content-length": "1000"}
        mock_response.iter_bytes.return_value = [b"fake compressed data"]
        mock_httpx.stream.return_value.__enter__ = MagicMock(return_value=mock_response)
        mock_httpx.stream.return_value.__exit__ = MagicMock(return_value=False)

        # Mock bz2.open context manager
        mock_bz2_file = MagicMock()
        mock_bz2_file.read.side_effect = [b"fake decompressed data", b""]
        mock_bz2.open.return_value.__enter__ = MagicMock(return_value=mock_bz2_file)
        mock_bz2.open.return_value.__exit__ = MagicMock(return_value=False)

        result = importer.download_sde()

        assert result.name == "sde-latest.sqlite"
        mock_httpx.stream.assert_called_once()
        mock_sha256.assert_called_once()

    @patch("aria_esi.store.sde.importer.verify_sde_integrity")
    @patch("aria_esi.store.sde.importer.compute_sha256")
    @patch("aria_esi.store.sde.importer.is_break_glass_enabled")
    @patch("aria_esi.store.sde.importer.get_pinned_sde_url")
    @patch("aria_esi.store.sde.importer.httpx")
    def test_checksum_mismatch_raises(
        self, mock_httpx, mock_get_url, mock_break_glass, mock_sha256, mock_verify, importer, tmp_path
    ):
        """Checksum mismatch raises IntegrityError."""
        from aria_esi.core.data_integrity import IntegrityError

        mock_get_url.return_value = ("https://example.com/sde.bz2", "expected_hash")
        mock_break_glass.return_value = False
        mock_sha256.return_value = "wrong_hash"
        mock_verify.side_effect = IntegrityError(
            "SDE checksum mismatch: expected expected_hash, got wrong_hash",
            expected="expected_hash",
            actual="wrong_hash",
        )

        # Mock httpx.stream context manager
        mock_response = MagicMock()
        mock_response.headers = {"content-length": "1000"}
        mock_response.iter_bytes.return_value = [b"data"]
        mock_httpx.stream.return_value.__enter__ = MagicMock(return_value=mock_response)
        mock_httpx.stream.return_value.__exit__ = MagicMock(return_value=False)

        with pytest.raises(IntegrityError, match="checksum mismatch"):
            importer.download_sde()

    @patch("aria_esi.store.sde.importer.verify_sde_integrity")
    @patch("aria_esi.store.sde.importer.compute_sha256")
    @patch("aria_esi.store.sde.importer.is_break_glass_enabled")
    @patch("aria_esi.store.sde.importer.get_pinned_sde_url")
    @patch("aria_esi.store.sde.importer.httpx")
    @patch("aria_esi.store.sde.importer.bz2")
    def test_break_glass_skips_checksum(
        self, mock_bz2, mock_httpx, mock_get_url, mock_break_glass, mock_sha256, mock_verify, importer
    ):
        """Break-glass mode skips checksum verification even on mismatch."""
        mock_get_url.return_value = ("https://example.com/sde.bz2", "expected_hash")
        mock_break_glass.return_value = False
        mock_sha256.return_value = "different_hash"
        mock_verify.return_value = (True, "different_hash")  # break_glass=True passes

        # Mock httpx.stream context manager
        mock_response = MagicMock()
        mock_response.headers = {"content-length": "1000"}
        mock_response.iter_bytes.return_value = [b"data"]
        mock_httpx.stream.return_value.__enter__ = MagicMock(return_value=mock_response)
        mock_httpx.stream.return_value.__exit__ = MagicMock(return_value=False)

        # Mock bz2.open context manager
        mock_bz2_file = MagicMock()
        mock_bz2_file.read.side_effect = [b"decompressed", b""]
        mock_bz2.open.return_value.__enter__ = MagicMock(return_value=mock_bz2_file)
        mock_bz2.open.return_value.__exit__ = MagicMock(return_value=False)

        # With break_glass=True parameter, checksum mismatch is tolerated
        result = importer.download_sde(break_glass=True)
        assert result.name == "sde-latest.sqlite"

    @patch("aria_esi.store.sde.importer.verify_sde_integrity")
    @patch("aria_esi.store.sde.importer.compute_sha256")
    @patch("aria_esi.store.sde.importer.is_break_glass_enabled")
    @patch("aria_esi.store.sde.importer.get_pinned_sde_url")
    @patch("aria_esi.store.sde.importer.httpx")
    @patch("aria_esi.store.sde.importer.bz2")
    def test_env_break_glass_skips_checksum(
        self, mock_bz2, mock_httpx, mock_get_url, mock_break_glass, mock_sha256, mock_verify, importer
    ):
        """Environment-level break-glass also skips checksum."""
        mock_get_url.return_value = ("https://example.com/sde.bz2", "expected_hash")
        mock_break_glass.return_value = True  # Environment says break-glass
        mock_sha256.return_value = "different_hash"
        mock_verify.return_value = (True, "different_hash")  # break-glass passes

        # Mock httpx.stream context manager
        mock_response = MagicMock()
        mock_response.headers = {"content-length": "1000"}
        mock_response.iter_bytes.return_value = [b"data"]
        mock_httpx.stream.return_value.__enter__ = MagicMock(return_value=mock_response)
        mock_httpx.stream.return_value.__exit__ = MagicMock(return_value=False)

        # Mock bz2.open context manager
        mock_bz2_file = MagicMock()
        mock_bz2_file.read.side_effect = [b"decompressed", b""]
        mock_bz2.open.return_value.__enter__ = MagicMock(return_value=mock_bz2_file)
        mock_bz2.open.return_value.__exit__ = MagicMock(return_value=False)

        result = importer.download_sde()
        assert result.name == "sde-latest.sqlite"

    @patch("aria_esi.store.sde.importer.update_sde_checksum")
    @patch("aria_esi.store.sde.importer.verify_sde_integrity")
    @patch("aria_esi.store.sde.importer.compute_sha256")
    @patch("aria_esi.store.sde.importer.is_break_glass_enabled")
    @patch("aria_esi.store.sde.importer.get_pinned_sde_url")
    @patch("aria_esi.store.sde.importer.httpx")
    @patch("aria_esi.store.sde.importer.bz2")
    def test_no_expected_checksum(
        self, mock_bz2, mock_httpx, mock_get_url, mock_break_glass, mock_sha256, mock_verify, mock_update, importer
    ):
        """When no expected checksum is configured, auto-pins after download."""
        from aria_esi.core.data_integrity import IntegrityError

        mock_get_url.return_value = ("https://example.com/sde.bz2", None)
        mock_break_glass.return_value = False
        mock_sha256.return_value = "any_hash"
        # verify_sde_integrity raises IntegrityError with expected=None (no checksum)
        mock_verify.side_effect = IntegrityError(
            "No SDE checksum configured", expected=None, actual="any_hash"
        )

        # Mock httpx.stream context manager
        mock_response = MagicMock()
        mock_response.headers = {"content-length": "1000"}
        mock_response.iter_bytes.return_value = [b"data"]
        mock_httpx.stream.return_value.__enter__ = MagicMock(return_value=mock_response)
        mock_httpx.stream.return_value.__exit__ = MagicMock(return_value=False)

        # Mock bz2.open context manager
        mock_bz2_file = MagicMock()
        mock_bz2_file.read.side_effect = [b"decompressed", b""]
        mock_bz2.open.return_value.__enter__ = MagicMock(return_value=mock_bz2_file)
        mock_bz2.open.return_value.__exit__ = MagicMock(return_value=False)

        result = importer.download_sde()
        assert result.name == "sde-latest.sqlite"
        mock_update.assert_called_once()  # Auto-pin was called

    @patch("aria_esi.store.sde.importer.update_sde_checksum")
    @patch("aria_esi.store.sde.importer.verify_sde_integrity")
    @patch("aria_esi.store.sde.importer.compute_sha256")
    @patch("aria_esi.store.sde.importer.is_break_glass_enabled")
    @patch("aria_esi.store.sde.importer.get_pinned_sde_url")
    @patch("aria_esi.store.sde.importer.httpx")
    @patch("aria_esi.store.sde.importer.bz2")
    def test_show_checksum_flag(
        self, mock_bz2, mock_httpx, mock_get_url, mock_break_glass, mock_sha256, mock_verify, mock_update, importer
    ):
        """show_checksum parameter stores the checksum on the importer."""
        from aria_esi.core.data_integrity import IntegrityError

        mock_get_url.return_value = ("https://example.com/sde.bz2", None)
        mock_break_glass.return_value = False
        mock_sha256.return_value = "the_sha256_hash"
        mock_verify.side_effect = IntegrityError(
            "No SDE checksum configured", expected=None, actual="the_sha256_hash"
        )

        # Mock httpx.stream context manager
        mock_response = MagicMock()
        mock_response.headers = {"content-length": "500"}
        mock_response.iter_bytes.return_value = [b"data"]
        mock_httpx.stream.return_value.__enter__ = MagicMock(return_value=mock_response)
        mock_httpx.stream.return_value.__exit__ = MagicMock(return_value=False)

        # Mock bz2.open context manager
        mock_bz2_file = MagicMock()
        mock_bz2_file.read.side_effect = [b"decompressed", b""]
        mock_bz2.open.return_value.__enter__ = MagicMock(return_value=mock_bz2_file)
        mock_bz2.open.return_value.__exit__ = MagicMock(return_value=False)

        importer.download_sde(show_checksum=True)
        assert importer._source_checksum == "the_sha256_hash"

    @patch("aria_esi.store.sde.importer.update_sde_checksum")
    @patch("aria_esi.store.sde.importer.verify_sde_integrity")
    @patch("aria_esi.store.sde.importer.compute_sha256")
    @patch("aria_esi.store.sde.importer.is_break_glass_enabled")
    @patch("aria_esi.store.sde.importer.get_pinned_sde_url")
    @patch("aria_esi.store.sde.importer.httpx")
    @patch("aria_esi.store.sde.importer.bz2")
    def test_progress_callback_called(
        self, mock_bz2, mock_httpx, mock_get_url, mock_break_glass, mock_sha256, mock_verify, mock_update, importer
    ):
        """Progress callback receives download progress."""
        from aria_esi.core.data_integrity import IntegrityError

        mock_get_url.return_value = ("https://example.com/sde.bz2", None)
        mock_break_glass.return_value = False
        mock_sha256.return_value = "hash"
        mock_verify.side_effect = IntegrityError(
            "No SDE checksum configured", expected=None, actual="hash"
        )

        # Return multiple chunks to test callback
        mock_response = MagicMock()
        mock_response.headers = {"content-length": "200"}
        mock_response.iter_bytes.return_value = [b"a" * 100, b"b" * 100]
        mock_httpx.stream.return_value.__enter__ = MagicMock(return_value=mock_response)
        mock_httpx.stream.return_value.__exit__ = MagicMock(return_value=False)

        mock_bz2_file = MagicMock()
        mock_bz2_file.read.side_effect = [b"data", b""]
        mock_bz2.open.return_value.__enter__ = MagicMock(return_value=mock_bz2_file)
        mock_bz2.open.return_value.__exit__ = MagicMock(return_value=False)

        progress_calls = []
        importer.download_sde(progress_callback=lambda downloaded, total: progress_calls.append((downloaded, total)))

        assert len(progress_calls) == 2
        assert progress_calls[0] == (100, 200)
        assert progress_calls[1] == (200, 200)

    @patch("aria_esi.store.sde.importer.verify_sde_integrity")
    @patch("aria_esi.store.sde.importer.compute_sha256")
    @patch("aria_esi.store.sde.importer.is_break_glass_enabled")
    @patch("aria_esi.store.sde.importer.get_pinned_sde_url")
    @patch("aria_esi.store.sde.importer.httpx")
    def test_checksum_case_insensitive(
        self, mock_httpx, mock_get_url, mock_break_glass, mock_sha256, mock_verify, importer
    ):
        """Checksum comparison is case-insensitive (delegated to verify_sde_integrity)."""
        mock_get_url.return_value = ("https://example.com/sde.bz2", "ABCDEF123456")
        mock_break_glass.return_value = False
        mock_sha256.return_value = "abcdef123456"
        mock_verify.return_value = (True, "abcdef123456")

        mock_response = MagicMock()
        mock_response.headers = {"content-length": "100"}
        mock_response.iter_bytes.return_value = [b"data"]
        mock_httpx.stream.return_value.__enter__ = MagicMock(return_value=mock_response)
        mock_httpx.stream.return_value.__exit__ = MagicMock(return_value=False)

        # Should not raise - case-insensitive comparison should pass
        # We need to mock bz2 for the decompression step
        with patch("aria_esi.store.sde.importer.bz2") as mock_bz2:
            mock_bz2_file = MagicMock()
            mock_bz2_file.read.side_effect = [b"data", b""]
            mock_bz2.open.return_value.__enter__ = MagicMock(return_value=mock_bz2_file)
            mock_bz2.open.return_value.__exit__ = MagicMock(return_value=False)

            result = importer.download_sde()
            assert result.name == "sde-latest.sqlite"


# =============================================================================
# Tests: SDEImporter initialization
# =============================================================================


class TestSDEImporterInit:
    """Tests for SDEImporter constructor and state management."""

    def test_stores_market_db_reference(self, temp_market_db):
        """Constructor stores reference to the MarketDatabase."""
        imp = SDEImporter(temp_market_db)
        assert imp.market_db is temp_market_db

    def test_initial_state(self, temp_market_db):
        """Initial state has no temp path and no checksum."""
        imp = SDEImporter(temp_market_db)
        assert imp._temp_sde_path is None
        assert imp._source_checksum is None


# =============================================================================
# Tests: Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_import_types_with_empty_type_name(self, importer, temp_market_db):
        """Types with empty typeName produce empty lowercase version."""
        importer.initialize_schema()
        target_conn = temp_market_db._get_connection()

        source_conn = sqlite3.connect(":memory:")
        source_conn.row_factory = sqlite3.Row
        source_conn.executescript("""
            CREATE TABLE invGroups (
                groupID INTEGER PRIMARY KEY,
                categoryID INTEGER,
                groupName TEXT,
                published INTEGER DEFAULT 1
            );
            CREATE TABLE invTypes (
                typeID INTEGER PRIMARY KEY,
                groupID INTEGER,
                typeName TEXT,
                volume REAL,
                packagedVolume REAL,
                marketGroupID INTEGER,
                description TEXT,
                published INTEGER DEFAULT 1
            );
        """)
        source_conn.execute("INSERT INTO invGroups VALUES (1, 1, 'Group', 1)")
        # typeName is empty string (not NULL — NULL would violate NOT NULL constraint)
        source_conn.execute(
            "INSERT INTO invTypes VALUES (1, 1, '', 1.0, 1.0, NULL, NULL, 1)"
        )
        source_conn.commit()

        count = importer._import_types(source_conn, target_conn)
        assert count == 1

        cursor = target_conn.execute("SELECT type_name_lower FROM types WHERE type_id = 1")
        row = cursor.fetchone()
        assert row["type_name_lower"] == ""

        source_conn.close()

    def test_import_groups_empty_source(self, importer, temp_market_db):
        """Empty groups table returns zero."""
        importer.initialize_schema()
        target_conn = temp_market_db._get_connection()

        source_conn = sqlite3.connect(":memory:")
        source_conn.row_factory = sqlite3.Row
        source_conn.execute(
            "CREATE TABLE invGroups "
            "(groupID INTEGER PRIMARY KEY, categoryID INTEGER, groupName TEXT, published INTEGER DEFAULT 1)"
        )
        source_conn.commit()

        count = importer._import_groups(source_conn, target_conn)
        assert count == 0

        source_conn.close()

    def test_blueprint_products_alternative_column_names(self, importer, temp_market_db):
        """Blueprint products with alternative column names (typeID instead of blueprintTypeID)."""
        importer.initialize_schema()
        target_conn = temp_market_db._get_connection()

        # Insert a type so the orphan filter passes
        target_conn.execute(
            "INSERT INTO types (type_id, type_name, type_name_lower) VALUES (587, 'Rifter', 'rifter')"
        )
        target_conn.commit()

        source_conn = sqlite3.connect(":memory:")
        source_conn.row_factory = sqlite3.Row
        # Use alternative column names
        source_conn.executescript("""
            CREATE TABLE industryActivityProducts (
                typeID INTEGER,
                activityID INTEGER,
                productTypeID INTEGER,
                quantity INTEGER
            );
        """)
        source_conn.execute(
            "INSERT INTO industryActivityProducts VALUES (688, 1, 587, 1)"
        )
        source_conn.commit()

        count = importer._import_blueprint_products(source_conn, target_conn)
        assert count == 1

        source_conn.close()

    def test_blueprint_materials_alternative_column_names(self, importer, temp_market_db):
        """Blueprint materials with alternative column names."""
        importer.initialize_schema()
        target_conn = temp_market_db._get_connection()

        source_conn = sqlite3.connect(":memory:")
        source_conn.row_factory = sqlite3.Row
        # Use alternative column names (typeID instead of blueprintTypeID)
        source_conn.executescript("""
            CREATE TABLE industryActivityMaterials (
                typeID INTEGER,
                activityID INTEGER,
                materialTypeID INTEGER,
                quantity INTEGER
            );
        """)
        source_conn.execute(
            "INSERT INTO industryActivityMaterials VALUES (688, 1, 34, 1000)"
        )
        source_conn.commit()

        count = importer._import_blueprint_materials(source_conn, target_conn)
        assert count == 1

        source_conn.close()

    def test_valid_sde_identifiers_is_frozenset(self):
        """_VALID_SDE_IDENTIFIERS is immutable frozenset."""
        assert isinstance(_VALID_SDE_IDENTIFIERS, frozenset)

    def test_valid_sde_identifiers_contains_expected_entries(self):
        """_VALID_SDE_IDENTIFIERS contains core column names."""
        assert "typeID" in _VALID_SDE_IDENTIFIERS
        assert "blueprintTypeID" in _VALID_SDE_IDENTIFIERS
        assert "productTypeID" in _VALID_SDE_IDENTIFIERS
        assert "materialTypeID" in _VALID_SDE_IDENTIFIERS
        assert "quantity" in _VALID_SDE_IDENTIFIERS
        assert "NULL" in _VALID_SDE_IDENTIFIERS
        assert "1" in _VALID_SDE_IDENTIFIERS


class TestSQLInterpolationSafety:
    """Regression test: all column variables in importer.py are wrapped in _qi().

    Security: This test scans the importer source for f-string column
    interpolations that bypass the _qi() allowlist. If a column variable
    is interpolated directly (e.g., {foo_col}) instead of via {_qi(foo_col)},
    it would bypass the SQL identifier allowlist and enable SQL injection.

    See dev/reviews/archive/SECURITY_000.md #7.
    """

    def test_no_col_variables_interpolated_without_qi(self):
        """Every {xxx_col} in importer.py must be wrapped in _qi()."""
        import re

        importer_path = Path(__file__).parent.parent.parent / "src" / "aria_esi" / "store" / "sde" / "importer.py"
        source = importer_path.read_text()

        # Pattern: find {some_col} that is NOT inside _qi(...)
        # We look for f-string interpolations containing _col that aren't
        # preceded by _qi(
        #
        # Match: {foo_col} — bare column interpolation (DANGEROUS)
        # Skip:  {_qi(foo_col)} — safely wrapped
        bare_col_pattern = re.compile(r'\{(?!_qi\()(\w+_col)\}')
        matches = bare_col_pattern.findall(source)

        assert matches == [], (
            f"Found column variables interpolated without _qi(): {matches}. "
            "All column variables in SQL f-strings must use _qi() for safe quoting."
        )
