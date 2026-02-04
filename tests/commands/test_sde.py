"""
Tests for sde command module.

Tests SDE status, item lookup, and blueprint lookup commands.
"""

import argparse
from unittest.mock import MagicMock, patch

import pytest

from aria_esi.commands.sde import cmd_sde_blueprint, cmd_sde_item, cmd_sde_status


class TestSDEStatusCommand:
    """Tests for cmd_sde_status."""

    def test_sde_status_not_seeded(self, empty_args):
        """Test status when SDE not yet seeded."""
        mock_status = MagicMock()
        mock_status.seeded = False

        mock_db_stats = {"database_path": "/test/path/market.db"}

        mock_db = MagicMock()
        mock_db.get_stats.return_value = mock_db_stats

        mock_importer = MagicMock()
        mock_importer.get_sde_status.return_value = mock_status

        with patch("aria_esi.mcp.market.database.MarketDatabase") as mock_db_cls:
            with patch("aria_esi.mcp.sde.importer.SDEImporter") as mock_imp_cls:
                mock_db_cls.return_value = mock_db
                mock_imp_cls.return_value = mock_importer

                result = cmd_sde_status(empty_args)

                assert result["status"] == "not_seeded"
                assert "hint" in result
                assert "sde-seed" in result["hint"]

    def test_sde_status_seeded(self, empty_args):
        """Test status when SDE is seeded."""
        mock_status = MagicMock()
        mock_status.seeded = True
        mock_status.category_count = 50
        mock_status.group_count = 500
        mock_status.type_count = 45000
        mock_status.blueprint_count = 10000
        mock_status.npc_seeding_count = 5000
        mock_status.npc_corp_count = 100
        mock_status.sde_version = "2025.01"
        mock_status.import_timestamp = "2026-01-20T12:00:00Z"
        mock_status.source_checksum = "abc123"

        mock_db_stats = {
            "database_path": "/test/path/market.db",
            "database_size_mb": 150.5,
        }

        mock_db = MagicMock()
        mock_db.get_stats.return_value = mock_db_stats

        mock_importer = MagicMock()
        mock_importer.get_sde_status.return_value = mock_status

        with patch("aria_esi.mcp.market.database.MarketDatabase") as mock_db_cls:
            with patch("aria_esi.mcp.sde.importer.SDEImporter") as mock_imp_cls:
                mock_db_cls.return_value = mock_db
                mock_imp_cls.return_value = mock_importer

                result = cmd_sde_status(empty_args)

                assert result["status"] == "ok"
                assert result["seeded"] is True
                assert result["type_count"] == 45000
                assert result["blueprint_count"] == 10000

    def test_sde_status_database_error(self, empty_args):
        """Test status when database error occurs."""
        with patch("aria_esi.mcp.market.database.MarketDatabase") as mock_db_cls:
            mock_db_cls.side_effect = Exception("Database connection failed")

            result = cmd_sde_status(empty_args)

            assert result["error"] == "database_error"


class TestSDEItemCommand:
    """Tests for cmd_sde_item."""

    @pytest.fixture
    def item_args(self):
        """Create args for item lookup."""
        args = argparse.Namespace()
        args.item_name = ["Tritanium"]
        return args

    def test_sde_item_not_seeded(self, item_args):
        """Test item lookup when SDE not seeded."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None  # No categories table
        mock_conn.execute.return_value = mock_cursor

        mock_db = MagicMock()
        mock_db._get_connection.return_value = mock_conn

        with patch("aria_esi.mcp.market.database.MarketDatabase") as mock_db_cls:
            mock_db_cls.return_value = mock_db

            result = cmd_sde_item(item_args)

            assert result["error"] == "not_seeded"

    def test_sde_item_found(self, item_args):
        """Test successful item lookup."""
        mock_conn = MagicMock()
        mock_cursor_exists = MagicMock()
        mock_cursor_exists.fetchone.return_value = ("categories",)  # Table exists

        mock_cursor_item = MagicMock()
        # Return item row: (type_id, type_name, desc, group_id, category_id,
        #                   market_group_id, volume, packaged_volume, published,
        #                   group_name, category_name)
        mock_cursor_item.fetchone.return_value = (
            34,  # type_id
            "Tritanium",  # type_name
            "A refined mineral",  # description
            18,  # group_id
            4,  # category_id (Material)
            1857,  # market_group_id
            0.01,  # volume
            0.01,  # packaged_volume
            1,  # published
            "Mineral",  # group_name
            "Material",  # category_name
        )

        def execute_impl(query, params=None):
            if "sqlite_master" in query:
                return mock_cursor_exists
            return mock_cursor_item

        mock_conn.execute.side_effect = execute_impl

        mock_db = MagicMock()
        mock_db._get_connection.return_value = mock_conn

        with patch("aria_esi.mcp.market.database.MarketDatabase") as mock_db_cls:
            mock_db_cls.return_value = mock_db

            result = cmd_sde_item(item_args)

            assert result["found"] is True
            assert result["item"]["type_id"] == 34
            assert result["item"]["type_name"] == "Tritanium"
            assert result["item"]["group_name"] == "Mineral"

    def test_sde_item_not_found(self, item_args):
        """Test item lookup when item not found."""
        item_args.item_name = ["NonexistentItem"]

        mock_conn = MagicMock()
        mock_cursor_exists = MagicMock()
        mock_cursor_exists.fetchone.return_value = ("categories",)

        mock_cursor_item = MagicMock()
        mock_cursor_item.fetchone.return_value = None  # Not found

        def execute_impl(query, params=None):
            if "sqlite_master" in query:
                return mock_cursor_exists
            return mock_cursor_item

        mock_conn.execute.side_effect = execute_impl

        mock_db = MagicMock()
        mock_db._get_connection.return_value = mock_conn

        with patch("aria_esi.mcp.market.database.MarketDatabase") as mock_db_cls:
            mock_db_cls.return_value = mock_db

            result = cmd_sde_item(item_args)

            assert result["found"] is False
            assert "not found" in result["message"]

    def test_sde_item_multi_word_name(self):
        """Test item lookup with multi-word name."""
        args = argparse.Namespace()
        args.item_name = ["Medium", "Shield", "Booster", "I"]

        mock_conn = MagicMock()
        mock_cursor_exists = MagicMock()
        mock_cursor_exists.fetchone.return_value = ("categories",)

        mock_cursor_item = MagicMock()
        mock_cursor_item.fetchone.return_value = (
            3834, "Medium Shield Booster I", "A shield booster",
            40, 7, 564, 5.0, 5.0, 1, "Shield Boosters", "Module"
        )

        def execute_impl(query, params=None):
            if "sqlite_master" in query:
                return mock_cursor_exists
            return mock_cursor_item

        mock_conn.execute.side_effect = execute_impl

        mock_db = MagicMock()
        mock_db._get_connection.return_value = mock_conn

        with patch("aria_esi.mcp.market.database.MarketDatabase") as mock_db_cls:
            mock_db_cls.return_value = mock_db

            result = cmd_sde_item(args)

            assert result["found"] is True
            assert result["item"]["type_name"] == "Medium Shield Booster I"


class TestSDEBlueprintCommand:
    """Tests for cmd_sde_blueprint."""

    @pytest.fixture
    def bp_args(self):
        """Create args for blueprint lookup."""
        args = argparse.Namespace()
        args.item_name = ["Rifter"]
        return args

    def test_sde_blueprint_not_seeded(self, bp_args):
        """Test blueprint lookup when SDE not seeded."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None  # No blueprints table
        mock_conn.execute.return_value = mock_cursor

        mock_db = MagicMock()
        mock_db._get_connection.return_value = mock_conn

        with patch("aria_esi.mcp.market.database.MarketDatabase") as mock_db_cls:
            mock_db_cls.return_value = mock_db

            result = cmd_sde_blueprint(bp_args)

            assert result["error"] == "not_seeded"

    def test_sde_blueprint_found_by_product(self, bp_args):
        """Test successful blueprint lookup by product name."""
        mock_conn = MagicMock()
        mock_cursor_exists = MagicMock()
        mock_cursor_exists.fetchone.return_value = ("blueprints",)

        mock_cursor_bp = MagicMock()
        # Return blueprint row
        mock_cursor_bp.fetchone.return_value = (
            687,  # blueprint_type_id
            "Rifter Blueprint",  # blueprint_name
            587,  # product_type_id
            "Rifter",  # product_name
            1,  # product_quantity
            3600,  # manufacturing_time
            4800,  # copying_time
            10,  # max_production_limit
        )

        mock_cursor_materials = MagicMock()
        mock_cursor_materials.fetchall.return_value = [
            ("Tritanium", 22500),
            ("Pyerite", 7500),
            ("Mexallon", 1875),
        ]

        mock_cursor_sources = MagicMock()
        mock_cursor_sources.fetchall.return_value = [
            ("Republic Fleet",),
        ]

        call_count = [0]

        def execute_impl(query, params=None):
            call_count[0] += 1
            if "sqlite_master" in query:
                return mock_cursor_exists
            elif "blueprint_materials" in query:
                return mock_cursor_materials
            elif "npc_seeding" in query:
                return mock_cursor_sources
            return mock_cursor_bp

        mock_conn.execute.side_effect = execute_impl

        mock_db = MagicMock()
        mock_db._get_connection.return_value = mock_conn

        with patch("aria_esi.mcp.market.database.MarketDatabase") as mock_db_cls:
            mock_db_cls.return_value = mock_db

            result = cmd_sde_blueprint(bp_args)

            assert result["found"] is True
            assert result["blueprint"]["blueprint_name"] == "Rifter Blueprint"
            assert result["blueprint"]["product_name"] == "Rifter"
            assert len(result["blueprint"]["materials"]) == 3
            assert result["searched_as"] == "product"

    def test_sde_blueprint_not_found(self, bp_args):
        """Test blueprint lookup when no blueprint exists."""
        bp_args.item_name = ["Tritanium"]  # Has no blueprint

        mock_conn = MagicMock()
        mock_cursor_exists = MagicMock()
        mock_cursor_exists.fetchone.return_value = ("blueprints",)

        mock_cursor_bp = MagicMock()
        mock_cursor_bp.fetchone.return_value = None  # Not found

        def execute_impl(query, params=None):
            if "sqlite_master" in query:
                return mock_cursor_exists
            return mock_cursor_bp

        mock_conn.execute.side_effect = execute_impl

        mock_db = MagicMock()
        mock_db._get_connection.return_value = mock_conn

        with patch("aria_esi.mcp.market.database.MarketDatabase") as mock_db_cls:
            mock_db_cls.return_value = mock_db

            result = cmd_sde_blueprint(bp_args)

            assert result["found"] is False
            assert "hint" in result


class TestSDESeedCommand:
    """Tests for cmd_sde_seed (limited - actual import is integration)."""

    def test_sde_seed_check_mode_not_seeded(self):
        """Test --check when not seeded."""
        args = argparse.Namespace()
        args.check = True

        mock_status = MagicMock()
        mock_status.seeded = False

        mock_db = MagicMock()
        mock_importer = MagicMock()
        mock_importer.get_sde_status.return_value = mock_status

        with patch("aria_esi.mcp.market.database.MarketDatabase") as mock_db_cls:
            with patch("aria_esi.mcp.sde.importer.SDEImporter") as mock_imp_cls:
                mock_db_cls.return_value = mock_db
                mock_imp_cls.return_value = mock_importer

                from aria_esi.commands.sde import cmd_sde_seed

                result = cmd_sde_seed(args)

                assert result["status"] == "not_seeded"

    def test_sde_seed_check_mode_seeded(self):
        """Test --check when already seeded."""
        args = argparse.Namespace()
        args.check = True

        mock_status = MagicMock()
        mock_status.seeded = True
        mock_status.blueprint_count = 10000
        mock_status.type_count = 45000
        mock_status.import_timestamp = "2026-01-20T12:00:00Z"

        mock_db = MagicMock()
        mock_importer = MagicMock()
        mock_importer.get_sde_status.return_value = mock_status

        with patch("aria_esi.mcp.market.database.MarketDatabase") as mock_db_cls:
            with patch("aria_esi.mcp.sde.importer.SDEImporter") as mock_imp_cls:
                mock_db_cls.return_value = mock_db
                mock_imp_cls.return_value = mock_importer

                from aria_esi.commands.sde import cmd_sde_seed

                result = cmd_sde_seed(args)

                assert result["status"] == "seeded"
                assert result["type_count"] == 45000
