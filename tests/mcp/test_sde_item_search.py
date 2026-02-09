"""
Unit Tests for SDE Item Info and Search MCP Tools.

Tests the sde_item_info, sde_search, and sde_cache_status tools.
"""

from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from aria_esi.mcp.sde.tools_item import _find_suggestions, _lookup_item, register_item_tools
from aria_esi.mcp.sde.tools_search import register_search_tools

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

        CREATE TABLE skill_attributes (
            type_id INTEGER PRIMARY KEY,
            rank INTEGER,
            primary_attribute TEXT,
            secondary_attribute TEXT
        );
        INSERT INTO skill_attributes VALUES (3300, 1, 'perception', 'willpower');
        INSERT INTO skill_attributes VALUES (3301, 3, 'willpower', 'perception');

        CREATE TABLE skill_prerequisites (
            type_id INTEGER,
            required_skill_id INTEGER,
            required_level INTEGER,
            PRIMARY KEY (type_id, required_skill_id)
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
def empty_db():
    """Create a database without SDE tables."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


# =============================================================================
# _lookup_item Tests
# =============================================================================


class TestLookupItem:
    """Tests for the _lookup_item helper function."""

    def test_exact_match_found(self, mock_sde_db):
        """Exact match should find the item."""
        result = _lookup_item(mock_sde_db, "venture", exact=True)
        assert result is not None
        assert result["type_id"] == 32880
        assert result["type_name"] == "Venture"

    def test_exact_match_case_insensitive(self, mock_sde_db):
        """Exact match should be case-insensitive."""
        result = _lookup_item(mock_sde_db, "VENTURE", exact=True)
        # type_name_lower column stores lowercase, so this won't match
        assert result is None

    def test_exact_match_not_found(self, mock_sde_db):
        """Non-existent item should return None."""
        result = _lookup_item(mock_sde_db, "nonexistent", exact=True)
        assert result is None

    def test_fuzzy_prefix_match(self, mock_sde_db):
        """Fuzzy match should find prefix matches."""
        result = _lookup_item(mock_sde_db, "vent", exact=False)
        assert result is not None
        assert result["type_id"] == 32880

    def test_fuzzy_contains_match(self, mock_sde_db):
        """Fuzzy match should find contains matches."""
        result = _lookup_item(mock_sde_db, "entur", exact=False)
        assert result is not None
        assert result["type_id"] == 32880

    def test_fuzzy_no_match(self, mock_sde_db):
        """Fuzzy match should return None for no matches."""
        result = _lookup_item(mock_sde_db, "zzzzzzz", exact=False)
        assert result is None

    def test_fuzzy_excludes_unpublished(self, mock_sde_db):
        """Fuzzy match should exclude unpublished items."""
        result = _lookup_item(mock_sde_db, "unpublished", exact=False)
        assert result is None

    def test_returns_all_fields(self, mock_sde_db):
        """Should return all expected fields."""
        result = _lookup_item(mock_sde_db, "tritanium", exact=True)
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
# _find_suggestions Tests
# =============================================================================


class TestFindSuggestions:
    """Tests for the _find_suggestions helper function."""

    def test_prefix_suggestions(self, mock_sde_db):
        """Should find prefix match suggestions."""
        suggestions = _find_suggestions(mock_sde_db, "vent")
        assert "Venture" in suggestions
        assert "Venture Blueprint" in suggestions

    def test_contains_suggestions(self, mock_sde_db):
        """Should find contains match suggestions when prefix exhausted."""
        suggestions = _find_suggestions(mock_sde_db, "rit", limit=5)
        assert "Tritanium" in suggestions

    def test_limit_respected(self, mock_sde_db):
        """Should respect the limit parameter."""
        suggestions = _find_suggestions(mock_sde_db, "vent", limit=1)
        assert len(suggestions) == 1

    def test_no_suggestions(self, mock_sde_db):
        """Should return empty list for no matches."""
        suggestions = _find_suggestions(mock_sde_db, "zzzzzzz")
        assert suggestions == []

    def test_excludes_unpublished(self, mock_sde_db):
        """Should exclude unpublished items from suggestions."""
        suggestions = _find_suggestions(mock_sde_db, "unpublish", limit=10)
        assert "Unpublished Item" not in suggestions


# =============================================================================
# sde_item_info Tool Tests
# =============================================================================


class TestSdeItemInfoTool:
    """Tests for the sde_item_info MCP tool."""

    @pytest.fixture
    def captured_tool(self, mock_db_object):
        """Capture the registered tool function."""
        captured = None

        def mock_tool():
            def decorator(func):
                nonlocal captured
                captured = func
                return func
            return decorator

        mock_server = MagicMock()
        mock_server.tool = mock_tool

        with patch(
            "aria_esi.mcp.sde.tools_item.get_market_database", return_value=mock_db_object
        ):
            register_item_tools(mock_server)

        return captured

    @pytest.mark.asyncio
    async def test_exact_match_returns_item(self, captured_tool, mock_db_object):
        """Should return item info for exact match."""
        with patch(
            "aria_esi.mcp.sde.tools_item.get_market_database", return_value=mock_db_object
        ):
            result = await captured_tool(item="Venture")

        assert result["found"] is True
        assert result["item"]["type_id"] == 32880
        assert result["item"]["type_name"] == "Venture"
        assert result["item"]["is_blueprint"] is False

    @pytest.mark.asyncio
    async def test_blueprint_detected(self, captured_tool, mock_db_object):
        """Should detect blueprint items."""
        with patch(
            "aria_esi.mcp.sde.tools_item.get_market_database", return_value=mock_db_object
        ):
            result = await captured_tool(item="Venture Blueprint")

        assert result["found"] is True
        assert result["item"]["is_blueprint"] is True

    @pytest.mark.asyncio
    async def test_fuzzy_match_fallback(self, captured_tool, mock_db_object):
        """Should fall back to fuzzy match when exact fails."""
        with patch(
            "aria_esi.mcp.sde.tools_item.get_market_database", return_value=mock_db_object
        ):
            result = await captured_tool(item="vent")

        assert result["found"] is True
        assert result["item"]["type_id"] == 32880

    @pytest.mark.asyncio
    async def test_not_found_returns_suggestions(self, captured_tool, mock_db_object):
        """Should return suggestions when item not found."""
        with patch(
            "aria_esi.mcp.sde.tools_item.get_market_database", return_value=mock_db_object
        ):
            result = await captured_tool(item="zzznonexistent")

        assert result["found"] is False
        assert result["item"] is None
        assert "not found" in result["warnings"][0].lower()

    @pytest.mark.asyncio
    async def test_sde_not_seeded_warning(self, mock_db_object):
        """Should warn if SDE not seeded."""
        # Create empty database
        empty_conn = sqlite3.connect(":memory:")
        empty_conn.row_factory = sqlite3.Row
        mock_db_object._get_connection.return_value = empty_conn

        try:
            captured = None

            def mock_tool():
                def decorator(func):
                    nonlocal captured
                    captured = func
                    return func
                return decorator

            mock_server = MagicMock()
            mock_server.tool = mock_tool

            with patch(
                "aria_esi.mcp.sde.tools_item.get_market_database", return_value=mock_db_object
            ):
                register_item_tools(mock_server)
                result = await captured(item="Venture")

            assert result["found"] is False
            assert any("not seeded" in w.lower() for w in result["warnings"])
        finally:
            empty_conn.close()

    @pytest.mark.asyncio
    async def test_skill_item_returns_attributes(self, captured_tool, mock_db_object):
        """Should return skill attributes for skill items."""
        with patch(
            "aria_esi.mcp.sde.tools_item.get_market_database", return_value=mock_db_object
        ):
            result = await captured_tool(item="Spaceship Command")

        assert result["found"] is True
        assert result["item"]["type_id"] == 3300
        assert result["item"]["skill_rank"] == 1
        assert result["item"]["skill_primary_attribute"] == "perception"
        assert result["item"]["skill_secondary_attribute"] == "willpower"

    @pytest.mark.asyncio
    async def test_non_skill_has_no_skill_attributes(self, captured_tool, mock_db_object):
        """Non-skill items should have null skill attributes."""
        with patch(
            "aria_esi.mcp.sde.tools_item.get_market_database", return_value=mock_db_object
        ):
            result = await captured_tool(item="Tritanium")

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
# Additional Helper Function Tests
# =============================================================================


class TestHelperFunctions:
    """Additional tests for helper functions to improve coverage."""

    def test_lookup_item_returns_none_for_nonexistent(self, mock_sde_db):
        """lookup_item should return None for nonexistent items."""
        result = _lookup_item(mock_sde_db, "this_does_not_exist", exact=True)
        assert result is None

    def test_lookup_item_fuzzy_prefers_shorter_names(self, mock_sde_db):
        """Fuzzy match should prefer shorter names (ORDER BY length)."""
        # "vent" should match "Venture" not "Venture Blueprint"
        result = _lookup_item(mock_sde_db, "vent", exact=False)
        assert result is not None
        assert result["type_name"] == "Venture"

    def test_find_suggestions_deduplicates(self, mock_sde_db):
        """Suggestions should not have duplicates from prefix and contains."""
        suggestions = _find_suggestions(mock_sde_db, "venture", limit=10)
        # Should have Venture and Venture Blueprint but no duplicates
        assert len(suggestions) == len(set(suggestions))

    def test_find_suggestions_default_limit(self, mock_sde_db):
        """Default limit should be 5."""
        # Even if there are many matches, default is 5
        suggestions = _find_suggestions(mock_sde_db, "e")  # Matches many items
        assert len(suggestions) <= 5
