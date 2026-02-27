"""
Unit Tests for SDE Item Info and Search MCP Tools.

Tests the sde_item_info, sde_search, and sde_cache_status tools.
"""

from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from aria_esi.mcp.sde.tools_search import register_search_tools
from aria_esi.store.sde.queries import SDEQueryService

# =============================================================================
# Mock Database Fixtures
# =============================================================================


@pytest.fixture
def mock_sde_db():
    """Create a mock database with SDE tables for item lookups."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    conn.executescript(
        """
        CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT);
        INSERT INTO metadata VALUES ('sde_schema_version', '1.0');
        INSERT INTO metadata VALUES ('sde_import_timestamp', '2024-01-01T00:00:00Z');

        CREATE TABLE categories (
            category_id INTEGER PRIMARY KEY,
            category_name TEXT,
            category_name_lower TEXT
        );
        INSERT INTO categories VALUES (6, 'Ship', 'ship');
        INSERT INTO categories VALUES (9, 'Blueprint', 'blueprint');
        INSERT INTO categories VALUES (16, 'Skill', 'skill');
        INSERT INTO categories VALUES (4, 'Material', 'material');

        CREATE TABLE groups (
            group_id INTEGER PRIMARY KEY,
            group_name TEXT,
            group_name_lower TEXT,
            category_id INTEGER
        );
        INSERT INTO groups VALUES (25, 'Frigate', 'frigate', 6);
        INSERT INTO groups VALUES (105, 'Ship Blueprint', 'ship blueprint', 9);
        INSERT INTO groups VALUES (18, 'Mineral', 'mineral', 4);
        INSERT INTO groups VALUES (255, 'Spaceship Command', 'spaceship command', 16);
        INSERT INTO groups VALUES (256, 'Advanced Spaceship Command', 'advanced spaceship command', 16);

        CREATE TABLE types (
            type_id INTEGER PRIMARY KEY,
            type_name TEXT,
            type_name_lower TEXT,
            description TEXT,
            group_id INTEGER,
            category_id INTEGER,
            market_group_id INTEGER,
            volume REAL,
            packaged_volume REAL,
            published INTEGER DEFAULT 1
        );
        INSERT INTO types VALUES (32880, 'Venture', 'venture', 'Mining frigate', 25, 6, 1361, 15000, 5000, 1);
        INSERT INTO types VALUES (32881, 'Venture Blueprint', 'venture blueprint', 'Blueprint for Venture', 105, 9, NULL, 0.01, NULL, 1);
        INSERT INTO types VALUES (34, 'Tritanium', 'tritanium', 'A mineral', 18, 4, 1857, 0.01, NULL, 1);
        INSERT INTO types VALUES (35, 'Pyerite', 'pyerite', 'A mineral', 18, 4, 1858, 0.01, NULL, 1);
        INSERT INTO types VALUES (3300, 'Spaceship Command', 'spaceship command', 'Core spaceship skill', 255, 16, NULL, 0.01, NULL, 1);
        INSERT INTO types VALUES (3301, 'Advanced Spaceship Command', 'advanced spaceship command', 'Advanced skill', 256, 16, NULL, 0.01, NULL, 1);
        INSERT INTO types VALUES (99999, 'Unpublished Item', 'unpublished item', 'Should not appear', 18, 4, NULL, 0.01, NULL, 0);

        CREATE TABLE blueprints (
            blueprint_type_id INTEGER PRIMARY KEY,
            product_type_id INTEGER
        );
        INSERT INTO blueprints VALUES (32881, 32880);

        CREATE TABLE npc_seeding (
            type_id INTEGER,
            corporation_id INTEGER,
            PRIMARY KEY (type_id, corporation_id)
        );
        INSERT INTO npc_seeding VALUES (32881, 1000129);

        CREATE TABLE npc_corporations (
            corporation_id INTEGER PRIMARY KEY,
            corporation_name TEXT,
            corporation_name_lower TEXT
        );
        INSERT INTO npc_corporations VALUES (1000129, 'Outer Ring Excavations', 'outer ring excavations');

        CREATE TABLE stations (
            station_id INTEGER PRIMARY KEY,
            station_name TEXT,
            station_name_lower TEXT,
            system_id INTEGER,
            region_id INTEGER,
            corporation_id INTEGER
        );

        CREATE TABLE regions (
            region_id INTEGER PRIMARY KEY,
            region_name TEXT,
            region_name_lower TEXT
        );

        CREATE TABLE skill_attributes (
            type_id INTEGER PRIMARY KEY,
            rank INTEGER,
            primary_attribute TEXT,
            secondary_attribute TEXT
        );
        INSERT INTO skill_attributes VALUES (3300, 1, 'perception', 'willpower');
        INSERT INTO skill_attributes VALUES (3301, 3, 'willpower', 'perception');

        CREATE TABLE skill_prerequisites (
            skill_type_id INTEGER,
            prerequisite_skill_id INTEGER,
            prerequisite_level INTEGER,
            PRIMARY KEY (skill_type_id, prerequisite_skill_id)
        );
        INSERT INTO skill_prerequisites VALUES (3301, 3300, 4);
        """
    )
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def mock_db_object(mock_sde_db, tmp_path):
    """Create a mock database object that returns the test connection."""
    # Create actual temp file for realistic Path behavior
    db_file = tmp_path / "test_market.db"
    db_file.write_bytes(b"x" * (1024 * 1024))  # 1MB file

    mock = MagicMock()
    mock._get_connection.return_value = mock_sde_db
    mock.db_path = db_file
    return mock


@pytest.fixture
def query_service(mock_db_object):
    """Create an SDEQueryService with the mock database."""
    return SDEQueryService(mock_db_object)


@pytest.fixture
def empty_db():
    """Create a database without SDE tables."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


# =============================================================================
# SDEQueryService.lookup_item Tests
# =============================================================================


class TestLookupItem:
    """Tests for the SDEQueryService.lookup_item method."""

    def test_exact_match_found(self, query_service):
        """Exact match should find the item."""
        result = query_service.lookup_item("venture", exact=True)
        assert result is not None
        assert result["type_id"] == 32880
        assert result["type_name"] == "Venture"

    def test_exact_match_case_insensitive(self, query_service):
        """Exact match should be case-insensitive (lowered internally)."""
        result = query_service.lookup_item("VENTURE", exact=True)
        assert result is not None
        assert result["type_name"] == "Venture"

    def test_exact_match_not_found(self, query_service):
        """Non-existent item should return None."""
        result = query_service.lookup_item("nonexistent", exact=True)
        assert result is None

    def test_fuzzy_prefix_match(self, query_service):
        """Fuzzy match should find prefix matches."""
        result = query_service.lookup_item("vent", exact=False)
        assert result is not None
        assert result["type_id"] == 32880

    def test_fuzzy_contains_match(self, query_service):
        """Fuzzy match should find contains matches."""
        result = query_service.lookup_item("entur", exact=False)
        assert result is not None
        assert result["type_id"] == 32880

    def test_fuzzy_no_match(self, query_service):
        """Fuzzy match should return None for no matches."""
        result = query_service.lookup_item("zzzzzzz", exact=False)
        assert result is None

    def test_fuzzy_excludes_unpublished(self, query_service):
        """Fuzzy match should exclude unpublished items."""
        result = query_service.lookup_item("unpublished", exact=False)
        assert result is None

    def test_returns_all_fields(self, query_service):
        """Should return all expected fields."""
        result = query_service.lookup_item("tritanium", exact=True)
        assert result is not None
        assert "type_id" in result
        assert "type_name" in result
        assert "description" in result
        assert "group_id" in result
        assert "category_id" in result
        assert "market_group_id" in result
        assert "volume" in result
        assert "packaged_volume" in result
        assert "published" in result
        assert "group_name" in result
        assert "category_name" in result


# =============================================================================
# SDEQueryService.find_item_suggestions Tests
# =============================================================================


class TestFindSuggestions:
    """Tests for the SDEQueryService.find_item_suggestions method."""

    def test_prefix_suggestions(self, query_service):
        """Should find prefix match suggestions."""
        suggestions = query_service.find_item_suggestions("vent")
        assert "Venture" in suggestions
        assert "Venture Blueprint" in suggestions

    def test_contains_suggestions(self, query_service):
        """Should find contains match suggestions when prefix exhausted."""
        suggestions = query_service.find_item_suggestions("rit", limit=5)
        assert "Tritanium" in suggestions

    def test_limit_respected(self, query_service):
        """Should respect the limit parameter."""
        suggestions = query_service.find_item_suggestions("vent", limit=1)
        assert len(suggestions) == 1

    def test_no_suggestions(self, query_service):
        """Should return empty list for no matches."""
        suggestions = query_service.find_item_suggestions("zzzzzzz")
        assert suggestions == []

    def test_excludes_unpublished(self, query_service):
        """Should exclude unpublished items from suggestions."""
        suggestions = query_service.find_item_suggestions("unpublish", limit=10)
        assert "Unpublished Item" not in suggestions


# =============================================================================
# SDEQueryService.resolve_skill_type_id Tests
# =============================================================================


class TestResolveSkillTypeId:
    """Tests for the SDEQueryService.resolve_skill_type_id method."""

    def test_resolve_existing_skill(self, query_service):
        """Should resolve a known skill name to type ID."""
        result = query_service.resolve_skill_type_id("Spaceship Command")
        assert result == 3300

    def test_resolve_case_insensitive(self, query_service):
        """Should be case-insensitive."""
        result = query_service.resolve_skill_type_id("spaceship command")
        assert result == 3300

    def test_resolve_nonexistent_skill(self, query_service):
        """Should return None for nonexistent skill."""
        result = query_service.resolve_skill_type_id("Nonexistent Skill")
        assert result is None

    def test_resolve_non_skill_type(self, query_service):
        """Should return None for non-skill items (category != 16)."""
        result = query_service.resolve_skill_type_id("Venture")
        assert result is None


# =============================================================================
# SDEQueryService.get_type_name Tests
# =============================================================================


class TestGetTypeName:
    """Tests for the SDEQueryService.get_type_name method."""

    def test_get_existing_type_name(self, query_service):
        """Should return type name for existing type ID."""
        result = query_service.get_type_name(32880)
        assert result == "Venture"

    def test_get_nonexistent_type_name(self, query_service):
        """Should return None for nonexistent type ID."""
        result = query_service.get_type_name(999999)
        assert result is None


# =============================================================================
# SDEQueryService.resolve_item_type Tests
# =============================================================================


class TestResolveItemType:
    """Tests for the SDEQueryService.resolve_item_type method."""

    def test_exact_match(self, query_service):
        """Should resolve exact item name."""
        result = query_service.resolve_item_type("Venture")
        assert result is not None
        type_id, type_name, category_name, category_id = result
        assert type_id == 32880
        assert type_name == "Venture"
        assert category_name == "Ship"
        assert category_id == 6

    def test_prefix_fallback(self, query_service):
        """Should fall back to prefix match."""
        result = query_service.resolve_item_type("Vent")
        assert result is not None
        assert result[1] == "Venture"

    def test_not_found(self, query_service):
        """Should return None for nonexistent item."""
        result = query_service.resolve_item_type("zzzznonexistent")
        assert result is None


# =============================================================================
# SDEQueryService.has_table Tests
# =============================================================================


class TestHasTable:
    """Tests for the SDEQueryService.has_table method."""

    def test_existing_table(self, query_service):
        """Should return True for existing table."""
        assert query_service.has_table("categories") is True

    def test_nonexistent_table(self, query_service):
        """Should return False for nonexistent table."""
        assert query_service.has_table("nonexistent_table") is False


# =============================================================================
# _item_info_impl Tool Tests
# =============================================================================


class TestItemInfoImpl:
    """Tests for the _item_info_impl function."""

    @pytest.mark.asyncio
    async def test_exact_match_returns_item(self, query_service):
        """Should return item info for exact match."""
        from aria_esi.mcp.sde.tools_item import _item_info_impl

        with patch(
            "aria_esi.mcp.sde.tools_item.get_sde_query_service", return_value=query_service
        ):
            result = await _item_info_impl("Venture")

        assert result["found"] is True
        assert result["item"]["type_id"] == 32880
        assert result["item"]["type_name"] == "Venture"
        assert result["item"]["is_blueprint"] is False

    @pytest.mark.asyncio
    async def test_blueprint_detected(self, query_service):
        """Should detect blueprint items."""
        from aria_esi.mcp.sde.tools_item import _item_info_impl

        with patch(
            "aria_esi.mcp.sde.tools_item.get_sde_query_service", return_value=query_service
        ):
            result = await _item_info_impl("Venture Blueprint")

        assert result["found"] is True
        assert result["item"]["is_blueprint"] is True

    @pytest.mark.asyncio
    async def test_fuzzy_match_fallback(self, query_service):
        """Should fall back to fuzzy match when exact fails."""
        from aria_esi.mcp.sde.tools_item import _item_info_impl

        with patch(
            "aria_esi.mcp.sde.tools_item.get_sde_query_service", return_value=query_service
        ):
            result = await _item_info_impl("vent")

        assert result["found"] is True
        assert result["item"]["type_id"] == 32880

    @pytest.mark.asyncio
    async def test_not_found_returns_suggestions(self, query_service):
        """Should return suggestions when item not found."""
        from aria_esi.mcp.sde.tools_item import _item_info_impl

        with patch(
            "aria_esi.mcp.sde.tools_item.get_sde_query_service", return_value=query_service
        ):
            result = await _item_info_impl("zzznonexistent")

        assert result["found"] is False
        assert result["item"] is None
        assert "not found" in result["warnings"][0].lower()

    @pytest.mark.asyncio
    async def test_sde_not_seeded_warning(self):
        """Should warn if SDE not seeded."""
        from aria_esi.mcp.sde.tools_item import _item_info_impl

        empty_conn = sqlite3.connect(":memory:")
        empty_conn.row_factory = sqlite3.Row
        try:
            mock_db = MagicMock()
            mock_db._get_connection.return_value = empty_conn
            service = SDEQueryService(mock_db)

            with patch(
                "aria_esi.mcp.sde.tools_item.get_sde_query_service", return_value=service
            ):
                result = await _item_info_impl("Venture")

            assert result["found"] is False
            assert any("not seeded" in w.lower() for w in result["warnings"])
        finally:
            empty_conn.close()

    @pytest.mark.asyncio
    async def test_skill_item_returns_attributes(self, query_service):
        """Should return skill attributes for skill items."""
        from aria_esi.mcp.sde.tools_item import _item_info_impl

        with patch(
            "aria_esi.mcp.sde.tools_item.get_sde_query_service", return_value=query_service
        ):
            result = await _item_info_impl("Spaceship Command")

        assert result["found"] is True
        assert result["item"]["type_id"] == 3300
        assert result["item"]["skill_rank"] == 1
        assert result["item"]["skill_primary_attribute"] == "perception"
        assert result["item"]["skill_secondary_attribute"] == "willpower"

    @pytest.mark.asyncio
    async def test_non_skill_has_no_skill_attributes(self, query_service):
        """Non-skill items should have null skill attributes."""
        from aria_esi.mcp.sde.tools_item import _item_info_impl

        with patch(
            "aria_esi.mcp.sde.tools_item.get_sde_query_service", return_value=query_service
        ):
            result = await _item_info_impl("Tritanium")

        assert result["found"] is True
        assert result["item"]["skill_rank"] is None
        assert result["item"]["skill_primary_attribute"] is None
        assert result["item"]["skill_secondary_attribute"] is None


# =============================================================================
# sde_search Tool Tests
# =============================================================================


class TestSdeSearchTool:
    """Tests for the sde_search MCP tool."""

    @pytest.fixture
    def captured_tools(self, mock_db_object):
        """Capture the registered tool functions."""
        captured = {}

        def mock_tool():
            def decorator(func):
                captured[func.__name__] = func
                return func
            return decorator

        mock_server = MagicMock()
        mock_server.tool = mock_tool

        with patch(
            "aria_esi.mcp.sde.tools_search.get_market_database", return_value=mock_db_object
        ):
            register_search_tools(mock_server)

        return captured

    @pytest.mark.asyncio
    async def test_search_finds_items(self, captured_tools, mock_db_object):
        """Should find items matching search query."""
        with patch(
            "aria_esi.mcp.sde.tools_search.get_market_database", return_value=mock_db_object
        ):
            result = await captured_tools["sde_search"](query="Venture")

        assert result["total_found"] >= 1
        assert any(item["type_name"] == "Venture" for item in result["items"])

    @pytest.mark.asyncio
    async def test_search_with_category_filter(self, captured_tools, mock_db_object):
        """Should filter by category."""
        with patch(
            "aria_esi.mcp.sde.tools_search.get_market_database", return_value=mock_db_object
        ):
            result = await captured_tools["sde_search"](query="Venture", category="Ship")

        assert result["total_found"] >= 1
        assert result["category_filter"] == "Ship"
        # Should only include ships, not blueprints
        for item in result["items"]:
            assert item["category_name"] == "Ship"

    @pytest.mark.asyncio
    async def test_search_limit_respected(self, captured_tools, mock_db_object):
        """Should respect the limit parameter."""
        with patch(
            "aria_esi.mcp.sde.tools_search.get_market_database", return_value=mock_db_object
        ):
            result = await captured_tools["sde_search"](query="e", limit=2)

        assert len(result["items"]) <= 2

    @pytest.mark.asyncio
    async def test_search_limit_clamped(self, captured_tools, mock_db_object):
        """Should clamp limit to valid range."""
        with patch(
            "aria_esi.mcp.sde.tools_search.get_market_database", return_value=mock_db_object
        ):
            result = await captured_tools["sde_search"](query="e", limit=100)

        # Max is 50
        assert result["limit"] == 50

    @pytest.mark.asyncio
    async def test_search_no_results(self, captured_tools, mock_db_object):
        """Should handle no results gracefully."""
        with patch(
            "aria_esi.mcp.sde.tools_search.get_market_database", return_value=mock_db_object
        ):
            result = await captured_tools["sde_search"](query="zzzznonexistent")

        assert result["total_found"] == 0
        assert result["items"] == []

    @pytest.mark.asyncio
    async def test_search_truncation_warning(self, captured_tools, mock_db_object):
        """Should warn when results are truncated."""
        with patch(
            "aria_esi.mcp.sde.tools_search.get_market_database", return_value=mock_db_object
        ):
            # Search for something common with low limit
            result = await captured_tools["sde_search"](query="e", limit=1)

        if result["total_found"] > 1:
            assert any("Showing" in w for w in result["warnings"])

    @pytest.mark.asyncio
    async def test_search_detects_blueprints(self, captured_tools, mock_db_object):
        """Should mark blueprint items correctly."""
        with patch(
            "aria_esi.mcp.sde.tools_search.get_market_database", return_value=mock_db_object
        ):
            result = await captured_tools["sde_search"](query="Blueprint")

        blueprints = [i for i in result["items"] if i["is_blueprint"]]
        assert len(blueprints) > 0


# =============================================================================
# sde_cache_status Tool Tests
# =============================================================================


class TestSdeCacheStatusTool:
    """Tests for the sde_cache_status MCP tool."""

    @pytest.fixture
    def captured_tools(self, mock_db_object):
        """Capture the registered tool functions."""
        captured = {}

        def mock_tool():
            def decorator(func):
                captured[func.__name__] = func
                return func
            return decorator

        mock_server = MagicMock()
        mock_server.tool = mock_tool

        with patch(
            "aria_esi.mcp.sde.tools_search.get_market_database", return_value=mock_db_object
        ):
            register_search_tools(mock_server)

        return captured

    @pytest.mark.asyncio
    async def test_status_when_seeded(self, captured_tools, mock_db_object):
        """Should return status when SDE is seeded."""
        with patch(
            "aria_esi.mcp.sde.tools_search.get_market_database", return_value=mock_db_object
        ):
            result = await captured_tools["sde_cache_status"]()

        assert result["seeded"] is True
        assert result["category_count"] > 0
        assert result["group_count"] > 0
        assert result["type_count"] > 0
        assert result["blueprint_count"] > 0

    @pytest.mark.asyncio
    async def test_status_when_not_seeded(self, mock_db_object):
        """Should return not seeded when tables missing."""
        empty_conn = sqlite3.connect(":memory:")
        empty_conn.row_factory = sqlite3.Row
        mock_db_object._get_connection.return_value = empty_conn

        try:
            captured = {}

            def mock_tool():
                def decorator(func):
                    captured[func.__name__] = func
                    return func
                return decorator

            mock_server = MagicMock()
            mock_server.tool = mock_tool

            with patch(
                "aria_esi.mcp.sde.tools_search.get_market_database", return_value=mock_db_object
            ):
                register_search_tools(mock_server)
                result = await captured["sde_cache_status"]()

            assert result["seeded"] is False
        finally:
            empty_conn.close()

    @pytest.mark.asyncio
    async def test_status_includes_metadata(self, captured_tools, mock_db_object):
        """Should include version and timestamp metadata."""
        with patch(
            "aria_esi.mcp.sde.tools_search.get_market_database", return_value=mock_db_object
        ):
            result = await captured_tools["sde_cache_status"]()

        assert result["sde_version"] == "1.0"
        assert result["import_timestamp"] == "2024-01-01T00:00:00Z"

    @pytest.mark.asyncio
    async def test_status_includes_database_info(self, captured_tools, mock_db_object):
        """Should include database path and size."""
        with patch(
            "aria_esi.mcp.sde.tools_search.get_market_database", return_value=mock_db_object
        ):
            result = await captured_tools["sde_cache_status"]()

        assert "database_path" in result
        assert "database_size_mb" in result


# =============================================================================
# Additional Helper Method Tests
# =============================================================================


class TestHelperMethods:
    """Additional tests for SDEQueryService helper methods to improve coverage."""

    def test_lookup_item_returns_none_for_nonexistent(self, query_service):
        """lookup_item should return None for nonexistent items."""
        result = query_service.lookup_item("this_does_not_exist", exact=True)
        assert result is None

    def test_lookup_item_fuzzy_prefers_shorter_names(self, query_service):
        """Fuzzy match should prefer shorter names (ORDER BY length)."""
        # "vent" should match "Venture" not "Venture Blueprint"
        result = query_service.lookup_item("vent", exact=False)
        assert result is not None
        assert result["type_name"] == "Venture"

    def test_find_suggestions_deduplicates(self, query_service):
        """Suggestions should not have duplicates from prefix and contains."""
        suggestions = query_service.find_item_suggestions("venture", limit=10)
        # Should have Venture and Venture Blueprint but no duplicates
        assert len(suggestions) == len(set(suggestions))

    def test_find_suggestions_default_limit(self, query_service):
        """Default limit should be 5."""
        # Even if there are many matches, default is 5
        suggestions = query_service.find_item_suggestions("e")  # Matches many items
        assert len(suggestions) <= 5
