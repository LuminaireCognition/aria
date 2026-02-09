"""
Tests for Hub-Centric Market Engine MCP Management Tools.

Tests cover the 8 MCP tools for watchlist and scope management:
- market_watchlist_create
- market_watchlist_add_item
- market_watchlist_list
- market_watchlist_get
- market_watchlist_delete
- market_scope_create
- market_scope_list
- market_scope_delete
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aria_esi.mcp.market.database import MarketDatabase
from aria_esi.mcp.market.tools_management import register_management_tools

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = MarketDatabase(db_path)

        # Add some test types for item resolution
        conn = db._get_connection()
        test_types = [
            (34, "Tritanium", "tritanium", None, None, None, 0.01, 0.01),
            (35, "Pyerite", "pyerite", None, None, None, 0.01, 0.01),
            (36, "Mexallon", "mexallon", None, None, None, 0.01, 0.01),
            (37, "Isogen", "isogen", None, None, None, 0.01, 0.01),
            (1230, "Veldspar", "veldspar", None, None, None, 0.1, 0.1),
            (1228, "Scordite", "scordite", None, None, None, 0.15, 0.15),
            (17459, "Pyroxeres", "pyroxeres", None, None, None, 0.3, 0.3),
        ]
        conn.executemany(
            """
            INSERT OR REPLACE INTO types (
                type_id, type_name, type_name_lower,
                group_id, category_id, market_group_id, volume, packaged_volume
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            test_types,
        )
        conn.commit()

        yield db
        db.close()


@pytest.fixture
def management_tools(temp_db):
    """Register management tools and return them with the temp database.

    Each test gets a fresh database and fresh tool registration.
    """
    # Create mock server
    server = MagicMock()
    tools = {}

    def tool_decorator():
        def decorator(func):
            tools[func.__name__] = func
            return func

        return decorator

    server.tool = tool_decorator

    # Patch get_market_database to return our temp_db for all tool calls
    with patch("aria_esi.mcp.market.tools_management.get_market_database") as mock_get_db:
        mock_get_db.return_value = temp_db
        register_management_tools(server)

        # Yield the tools dict along with the patcher active
        # so tool calls use the temp_db
        yield tools, temp_db


# =============================================================================
# Watchlist Create Tests
# =============================================================================


class TestWatchlistCreate:
    """Tests for market_watchlist_create tool."""

    @pytest.mark.asyncio
    async def test_create_empty_watchlist(self, management_tools):
        """Test creating an empty watchlist."""
        tools, db = management_tools
        create = tools["market_watchlist_create"]

        result = await create(name="test_list")

        assert "error" not in result
        assert result["watchlist"]["name"] == "test_list"
        assert result["watchlist"]["item_count"] == 0
        assert result["items_added"] == 0
        assert result["unresolved_items"] == []

    @pytest.mark.asyncio
    async def test_create_watchlist_with_items(self, management_tools):
        """Test creating a watchlist with initial items."""
        tools, db = management_tools
        create = tools["market_watchlist_create"]

        result = await create(
            name="mining_ores",
            items=["Veldspar", "Scordite", "Pyroxeres"],
        )

        assert "error" not in result
        assert result["watchlist"]["name"] == "mining_ores"
        assert result["watchlist"]["item_count"] == 3
        assert result["items_added"] == 3
        assert result["unresolved_items"] == []

    @pytest.mark.asyncio
    async def test_create_watchlist_with_unresolved_items(self, management_tools):
        """Test creating a watchlist with some unresolved items."""
        tools, db = management_tools
        create = tools["market_watchlist_create"]

        result = await create(
            name="mixed_list",
            items=["Tritanium", "NonexistentItem", "Pyerite"],
        )

        assert "error" not in result
        assert result["watchlist"]["item_count"] == 2
        assert result["items_added"] == 2
        assert "NonexistentItem" in result["unresolved_items"]

    @pytest.mark.asyncio
    async def test_create_watchlist_with_owner(self, management_tools):
        """Test creating a watchlist with owner."""
        tools, db = management_tools
        create = tools["market_watchlist_create"]

        result = await create(
            name="personal_list",
            owner_character_id=12345,
        )

        assert "error" not in result
        assert result["watchlist"]["owner_character_id"] == 12345

    @pytest.mark.asyncio
    async def test_create_duplicate_name_error(self, management_tools):
        """Test that duplicate names return an error."""
        tools, db = management_tools
        create = tools["market_watchlist_create"]

        # Create first watchlist
        await create(name="duplicate_test")

        # Try to create second with same name
        result = await create(name="duplicate_test")

        assert "error" in result
        assert result["error"]["code"] == "DUPLICATE_NAME"

    @pytest.mark.asyncio
    async def test_same_name_different_owners_allowed(self, management_tools):
        """Test that same name with different owners is allowed."""
        tools, db = management_tools
        create = tools["market_watchlist_create"]

        result1 = await create(name="shared_name", owner_character_id=12345)
        result2 = await create(name="shared_name", owner_character_id=67890)
        result3 = await create(name="shared_name")  # Global

        assert "error" not in result1
        assert "error" not in result2
        assert "error" not in result3


# =============================================================================
# Watchlist Add Item Tests
# =============================================================================


class TestWatchlistAddItem:
    """Tests for market_watchlist_add_item tool."""

    @pytest.mark.asyncio
    async def test_add_item_success(self, management_tools):
        """Test successfully adding an item to a watchlist."""
        tools, db = management_tools
        create = tools["market_watchlist_create"]
        add_item = tools["market_watchlist_add_item"]

        # Create watchlist first
        await create(name="test_list")

        # Add item
        result = await add_item(
            watchlist_name="test_list",
            item_name="Tritanium",
        )

        assert "error" not in result
        assert result["item"]["type_id"] == 34
        assert result["item"]["type_name"] == "Tritanium"
        assert result["watchlist_name"] == "test_list"

    @pytest.mark.asyncio
    async def test_add_item_watchlist_not_found(self, management_tools):
        """Test adding to a non-existent watchlist."""
        tools, db = management_tools
        add_item = tools["market_watchlist_add_item"]

        result = await add_item(
            watchlist_name="nonexistent",
            item_name="Tritanium",
        )

        assert "error" in result
        assert result["error"]["code"] == "WATCHLIST_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_add_item_type_not_found(self, management_tools):
        """Test adding an unresolvable item."""
        tools, db = management_tools
        create = tools["market_watchlist_create"]
        add_item = tools["market_watchlist_add_item"]

        await create(name="test_list")

        result = await add_item(
            watchlist_name="test_list",
            item_name="CompletelyFakeItem",
        )

        assert "error" in result
        assert result["error"]["code"] == "TYPE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_add_item_duplicate_error(self, management_tools):
        """Test adding a duplicate item."""
        tools, db = management_tools
        create = tools["market_watchlist_create"]
        add_item = tools["market_watchlist_add_item"]

        await create(name="test_list")

        # Add item first time
        await add_item(watchlist_name="test_list", item_name="Tritanium")

        # Try to add same item again
        result = await add_item(watchlist_name="test_list", item_name="Tritanium")

        assert "error" in result
        assert result["error"]["code"] == "DUPLICATE_ITEM"

    @pytest.mark.asyncio
    async def test_add_item_case_insensitive(self, management_tools):
        """Test that item names are case-insensitive."""
        tools, db = management_tools
        create = tools["market_watchlist_create"]
        add_item = tools["market_watchlist_add_item"]

        await create(name="test_list")

        result = await add_item(
            watchlist_name="test_list",
            item_name="TRITANIUM",  # All caps
        )

        assert "error" not in result
        assert result["item"]["type_name"] == "Tritanium"


# =============================================================================
# Watchlist List Tests
# =============================================================================


class TestWatchlistList:
    """Tests for market_watchlist_list tool."""

    @pytest.mark.asyncio
    async def test_list_global_watchlists(self, management_tools):
        """Test listing global watchlists."""
        tools, db = management_tools
        create = tools["market_watchlist_create"]
        list_watchlists = tools["market_watchlist_list"]

        await create(name="global_1")
        await create(name="global_2")
        await create(name="owned", owner_character_id=12345)

        result = await list_watchlists()

        assert "error" not in result
        assert result["total"] == 2
        names = [w["name"] for w in result["watchlists"]]
        assert "global_1" in names
        assert "global_2" in names
        assert "owned" not in names

    @pytest.mark.asyncio
    async def test_list_owner_watchlists(self, management_tools):
        """Test listing owner's watchlists."""
        tools, db = management_tools
        create = tools["market_watchlist_create"]
        list_watchlists = tools["market_watchlist_list"]

        await create(name="global")
        await create(name="owned_1", owner_character_id=12345)
        await create(name="owned_2", owner_character_id=12345)

        result = await list_watchlists(owner_character_id=12345)

        assert "error" not in result
        # Should include owner's + global
        assert result["total"] == 3
        names = [w["name"] for w in result["watchlists"]]
        assert "global" in names
        assert "owned_1" in names
        assert "owned_2" in names

    @pytest.mark.asyncio
    async def test_list_owner_only_exclude_global(self, management_tools):
        """Test listing owner's watchlists excluding global."""
        tools, db = management_tools
        create = tools["market_watchlist_create"]
        list_watchlists = tools["market_watchlist_list"]

        await create(name="global")
        await create(name="owned", owner_character_id=12345)

        result = await list_watchlists(
            owner_character_id=12345,
            include_global=False,
        )

        assert "error" not in result
        assert result["total"] == 1
        assert result["watchlists"][0]["name"] == "owned"

    @pytest.mark.asyncio
    async def test_list_empty(self, management_tools):
        """Test listing when no watchlists exist."""
        tools, db = management_tools
        list_watchlists = tools["market_watchlist_list"]

        result = await list_watchlists()

        assert "error" not in result
        assert result["total"] == 0
        assert result["watchlists"] == []


# =============================================================================
# Watchlist Get Tests
# =============================================================================


class TestWatchlistGet:
    """Tests for market_watchlist_get tool."""

    @pytest.mark.asyncio
    async def test_get_watchlist_with_items(self, management_tools):
        """Test getting a watchlist with items."""
        tools, db = management_tools
        create = tools["market_watchlist_create"]
        get_watchlist = tools["market_watchlist_get"]

        await create(
            name="test_list",
            items=["Tritanium", "Pyerite"],
        )

        result = await get_watchlist(name="test_list")

        assert "error" not in result
        assert result["name"] == "test_list"
        assert len(result["items"]) == 2
        type_names = [i["type_name"] for i in result["items"]]
        assert "Tritanium" in type_names
        assert "Pyerite" in type_names

    @pytest.mark.asyncio
    async def test_get_watchlist_not_found(self, management_tools):
        """Test getting a non-existent watchlist."""
        tools, db = management_tools
        get_watchlist = tools["market_watchlist_get"]

        result = await get_watchlist(name="nonexistent")

        assert "error" in result
        assert result["error"]["code"] == "WATCHLIST_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_get_empty_watchlist(self, management_tools):
        """Test getting an empty watchlist."""
        tools, db = management_tools
        create = tools["market_watchlist_create"]
        get_watchlist = tools["market_watchlist_get"]

        await create(name="empty_list")

        result = await get_watchlist(name="empty_list")

        assert "error" not in result
        assert result["items"] == []


# =============================================================================
# Watchlist Delete Tests
# =============================================================================


class TestWatchlistDelete:
    """Tests for market_watchlist_delete tool."""

    @pytest.mark.asyncio
    async def test_delete_success(self, management_tools):
        """Test successfully deleting a watchlist."""
        tools, db = management_tools
        create = tools["market_watchlist_create"]
        delete = tools["market_watchlist_delete"]
        get_watchlist = tools["market_watchlist_get"]

        await create(name="to_delete", items=["Tritanium", "Pyerite"])

        result = await delete(name="to_delete")

        assert "error" not in result
        assert result["deleted"] is True
        assert result["watchlist_name"] == "to_delete"
        assert result["items_deleted"] == 2

        # Verify it's gone
        get_result = await get_watchlist(name="to_delete")
        assert "error" in get_result

    @pytest.mark.asyncio
    async def test_delete_not_found(self, management_tools):
        """Test deleting a non-existent watchlist."""
        tools, db = management_tools
        delete = tools["market_watchlist_delete"]

        result = await delete(name="nonexistent")

        assert "error" in result
        assert result["error"]["code"] == "WATCHLIST_NOT_FOUND"


# =============================================================================
# Scope Create Tests
# =============================================================================


class TestScopeCreate:
    """Tests for market_scope_create tool."""

    @pytest.mark.asyncio
    async def test_create_region_scope(self, management_tools):
        """Test creating a region scope."""
        tools, db = management_tools
        create_watchlist = tools["market_watchlist_create"]
        create_scope = tools["market_scope_create"]

        await create_watchlist(name="test_items", items=["Tritanium"])

        result = await create_scope(
            name="Everyshore",
            scope_type="region",
            location_id=10000037,
            watchlist_name="test_items",
        )

        assert "error" not in result
        assert result["scope"]["scope_name"] == "Everyshore"
        assert result["scope"]["scope_type"] == "region"
        assert result["scope"]["location_id"] == 10000037
        assert result["scope"]["is_core"] is False
        assert result["scope"]["source"] == "esi"
        assert result["scope"]["watchlist_name"] == "test_items"

    @pytest.mark.asyncio
    async def test_create_station_scope(self, management_tools):
        """Test creating a station scope."""
        tools, db = management_tools
        create_watchlist = tools["market_watchlist_create"]
        create_scope = tools["market_scope_create"]

        await create_watchlist(name="test_items")

        result = await create_scope(
            name="My Station",
            scope_type="station",
            location_id=60003760,
            watchlist_name="test_items",
            parent_region_id=10000002,
        )

        assert "error" not in result
        assert result["scope"]["scope_type"] == "station"
        assert result["scope"]["parent_region_id"] == 10000002

    @pytest.mark.asyncio
    async def test_create_system_scope(self, management_tools):
        """Test creating a system scope."""
        tools, db = management_tools
        create_watchlist = tools["market_watchlist_create"]
        create_scope = tools["market_scope_create"]

        await create_watchlist(name="test_items")

        result = await create_scope(
            name="Jita System",
            scope_type="system",
            location_id=30000142,
            watchlist_name="test_items",
            parent_region_id=10000002,
        )

        assert "error" not in result
        assert result["scope"]["scope_type"] == "system"

    @pytest.mark.asyncio
    async def test_create_structure_scope(self, management_tools):
        """Test creating a structure scope."""
        tools, db = management_tools
        create_watchlist = tools["market_watchlist_create"]
        create_scope = tools["market_scope_create"]

        await create_watchlist(name="test_items")

        result = await create_scope(
            name="My Citadel",
            scope_type="structure",
            location_id=1234567890,
            watchlist_name="test_items",
            parent_region_id=10000002,
        )

        assert "error" not in result
        assert result["scope"]["scope_type"] == "structure"

    @pytest.mark.asyncio
    async def test_create_scope_invalid_type(self, management_tools):
        """Test creating a scope with invalid type."""
        tools, db = management_tools
        create_watchlist = tools["market_watchlist_create"]
        create_scope = tools["market_scope_create"]

        await create_watchlist(name="test_items")

        result = await create_scope(
            name="Bad Scope",
            scope_type="hub_region",  # Reserved for core
            location_id=10000002,
            watchlist_name="test_items",
        )

        assert "error" in result
        assert result["error"]["code"] == "INVALID_SCOPE_TYPE"

    @pytest.mark.asyncio
    async def test_create_scope_watchlist_not_found(self, management_tools):
        """Test creating a scope with non-existent watchlist."""
        tools, db = management_tools
        create_scope = tools["market_scope_create"]

        result = await create_scope(
            name="Test",
            scope_type="region",
            location_id=10000037,
            watchlist_name="nonexistent",
        )

        assert "error" in result
        assert result["error"]["code"] == "WATCHLIST_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_create_scope_duplicate_name(self, management_tools):
        """Test creating a scope with duplicate name."""
        tools, db = management_tools
        create_watchlist = tools["market_watchlist_create"]
        create_scope = tools["market_scope_create"]

        await create_watchlist(name="test_items")

        await create_scope(
            name="Duplicate",
            scope_type="region",
            location_id=10000037,
            watchlist_name="test_items",
        )

        result = await create_scope(
            name="Duplicate",
            scope_type="region",
            location_id=10000038,
            watchlist_name="test_items",
        )

        assert "error" in result
        assert result["error"]["code"] == "DUPLICATE_NAME"

    @pytest.mark.asyncio
    async def test_create_scope_uses_global_watchlist_fallback(self, management_tools):
        """Test that scope creation falls back to global watchlist."""
        tools, db = management_tools
        create_watchlist = tools["market_watchlist_create"]
        create_scope = tools["market_scope_create"]

        # Create global watchlist
        await create_watchlist(name="global_items")

        # Create scope for owner using global watchlist
        result = await create_scope(
            name="Owner Scope",
            scope_type="region",
            location_id=10000037,
            watchlist_name="global_items",
            owner_character_id=12345,
        )

        assert "error" not in result
        assert result["scope"]["watchlist_name"] == "global_items"


# =============================================================================
# Scope List Tests
# =============================================================================


class TestScopeList:
    """Tests for market_scope_list tool."""

    @pytest.mark.asyncio
    async def test_list_includes_core_hubs(self, management_tools):
        """Test that list includes core hubs by default."""
        tools, db = management_tools
        list_scopes = tools["market_scope_list"]

        result = await list_scopes()

        assert "error" not in result
        assert result["core_count"] == 5
        core_names = [s["scope_name"] for s in result["scopes"] if s["is_core"]]
        assert set(core_names) == {"Jita", "Amarr", "Dodixie", "Rens", "Hek"}

    @pytest.mark.asyncio
    async def test_list_exclude_core(self, management_tools):
        """Test excluding core hubs."""
        tools, db = management_tools
        create_watchlist = tools["market_watchlist_create"]
        create_scope = tools["market_scope_create"]
        list_scopes = tools["market_scope_list"]

        await create_watchlist(name="test")
        await create_scope(
            name="Custom",
            scope_type="region",
            location_id=10000037,
            watchlist_name="test",
        )

        result = await list_scopes(include_core=False)

        assert "error" not in result
        assert result["core_count"] == 0
        assert result["adhoc_count"] == 1
        assert len(result["scopes"]) == 1
        assert result["scopes"][0]["scope_name"] == "Custom"

    @pytest.mark.asyncio
    async def test_list_by_owner(self, management_tools):
        """Test listing scopes by owner."""
        tools, db = management_tools
        create_watchlist = tools["market_watchlist_create"]
        create_scope = tools["market_scope_create"]
        list_scopes = tools["market_scope_list"]

        await create_watchlist(name="test")
        await create_scope(
            name="Owner Scope",
            scope_type="region",
            location_id=10000037,
            watchlist_name="test",
            owner_character_id=12345,
        )
        await create_scope(
            name="Global Scope",
            scope_type="region",
            location_id=10000038,
            watchlist_name="test",
        )

        # List for owner - includes owner's + global (core + ad-hoc)
        result = await list_scopes(owner_character_id=12345)

        assert "error" not in result
        names = [s["scope_name"] for s in result["scopes"]]
        assert "Owner Scope" in names
        assert "Global Scope" in names
        assert "Jita" in names

    @pytest.mark.asyncio
    async def test_list_owner_exclude_global(self, management_tools):
        """Test listing owner scopes excluding global."""
        tools, db = management_tools
        create_watchlist = tools["market_watchlist_create"]
        create_scope = tools["market_scope_create"]
        list_scopes = tools["market_scope_list"]

        await create_watchlist(name="test", owner_character_id=12345)
        await create_scope(
            name="Owner Scope",
            scope_type="region",
            location_id=10000037,
            watchlist_name="test",
            owner_character_id=12345,
        )

        result = await list_scopes(
            owner_character_id=12345,
            include_global=False,
        )

        assert "error" not in result
        assert len(result["scopes"]) == 1
        assert result["scopes"][0]["scope_name"] == "Owner Scope"


# =============================================================================
# Scope Delete Tests
# =============================================================================


class TestScopeDelete:
    """Tests for market_scope_delete tool."""

    @pytest.mark.asyncio
    async def test_delete_adhoc_success(self, management_tools):
        """Test successfully deleting an ad-hoc scope."""
        tools, db = management_tools
        create_watchlist = tools["market_watchlist_create"]
        create_scope = tools["market_scope_create"]
        delete_scope = tools["market_scope_delete"]
        list_scopes = tools["market_scope_list"]

        await create_watchlist(name="test")
        await create_scope(
            name="ToDelete",
            scope_type="region",
            location_id=10000037,
            watchlist_name="test",
        )

        result = await delete_scope(name="ToDelete")

        assert "error" not in result
        assert result["deleted"] is True
        assert result["scope_name"] == "ToDelete"

        # Verify it's gone
        list_result = await list_scopes(include_core=False)
        names = [s["scope_name"] for s in list_result["scopes"]]
        assert "ToDelete" not in names

    @pytest.mark.asyncio
    async def test_delete_scope_not_found(self, management_tools):
        """Test deleting a non-existent scope."""
        tools, db = management_tools
        delete_scope = tools["market_scope_delete"]

        result = await delete_scope(name="nonexistent")

        assert "error" in result
        assert result["error"]["code"] == "SCOPE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_delete_core_scope_rejected(self, management_tools):
        """Test that deleting core scopes is rejected."""
        tools, db = management_tools
        delete_scope = tools["market_scope_delete"]

        result = await delete_scope(name="Jita")

        assert "error" in result
        assert result["error"]["code"] == "CORE_SCOPE_PROTECTED"

    @pytest.mark.asyncio
    async def test_all_core_hubs_protected(self, management_tools):
        """Test that all 5 core hubs are protected from deletion."""
        tools, db = management_tools
        delete_scope = tools["market_scope_delete"]

        for hub_name in ["Jita", "Amarr", "Dodixie", "Rens", "Hek"]:
            result = await delete_scope(name=hub_name)
            assert "error" in result
            assert result["error"]["code"] == "CORE_SCOPE_PROTECTED"


# =============================================================================
# Integration Tests
# =============================================================================


class TestManagementIntegration:
    """Integration tests for management tools working together."""

    @pytest.mark.asyncio
    async def test_full_watchlist_workflow(self, management_tools):
        """Test complete watchlist create -> add -> list -> get -> delete workflow."""
        tools, db = management_tools

        # Create
        create_result = await tools["market_watchlist_create"](
            name="workflow_test",
            items=["Tritanium"],
        )
        assert "error" not in create_result
        assert create_result["watchlist"]["item_count"] == 1

        # Add item
        add_result = await tools["market_watchlist_add_item"](
            watchlist_name="workflow_test",
            item_name="Pyerite",
        )
        assert "error" not in add_result

        # List
        list_result = await tools["market_watchlist_list"]()
        assert "error" not in list_result
        assert any(w["name"] == "workflow_test" for w in list_result["watchlists"])

        # Get
        get_result = await tools["market_watchlist_get"](name="workflow_test")
        assert "error" not in get_result
        assert len(get_result["items"]) == 2

        # Delete
        delete_result = await tools["market_watchlist_delete"](name="workflow_test")
        assert "error" not in delete_result
        assert delete_result["items_deleted"] == 2

    @pytest.mark.asyncio
    async def test_full_scope_workflow(self, management_tools):
        """Test complete scope create -> list -> delete workflow."""
        tools, db = management_tools

        # Create watchlist first
        await tools["market_watchlist_create"](
            name="scope_test_items",
            items=["Tritanium"],
        )

        # Create scope
        create_result = await tools["market_scope_create"](
            name="TestRegion",
            scope_type="region",
            location_id=10000037,
            watchlist_name="scope_test_items",
        )
        assert "error" not in create_result

        # List (exclude core for cleaner test)
        list_result = await tools["market_scope_list"](include_core=False)
        assert "error" not in list_result
        assert any(s["scope_name"] == "TestRegion" for s in list_result["scopes"])

        # Delete
        delete_result = await tools["market_scope_delete"](name="TestRegion")
        assert "error" not in delete_result
        assert delete_result["deleted"] is True

        # Verify deleted
        list_result_after = await tools["market_scope_list"](include_core=False)
        assert not any(s["scope_name"] == "TestRegion" for s in list_result_after["scopes"])

    @pytest.mark.asyncio
    async def test_scope_requires_valid_watchlist(self, management_tools):
        """Test that scopes require a valid watchlist reference."""
        tools, db = management_tools

        # Create watchlist and scope
        await tools["market_watchlist_create"](name="temp_list")
        create_result = await tools["market_scope_create"](
            name="TempScope",
            scope_type="region",
            location_id=10000037,
            watchlist_name="temp_list",
        )
        assert "error" not in create_result

        # Delete the watchlist (should cascade to invalidate scope references)
        await tools["market_watchlist_delete"](name="temp_list")

        # The scope should still exist but watchlist reference may be broken
        # This depends on CASCADE behavior - in our schema it cascades
        list_result = await tools["market_scope_list"](include_core=False)
        # Scope should be gone due to cascade
        assert not any(s["scope_name"] == "TempScope" for s in list_result["scopes"])
