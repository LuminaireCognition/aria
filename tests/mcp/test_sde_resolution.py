"""
Tests for SDEQueryService.resolve_skill_ids() — Phase A.

Validates batch skill name-to-ID resolution against a mock SDE database.
"""

from __future__ import annotations

import sqlite3

import pytest

from aria_esi.mcp.sde.queries import SDEResolutionError


class TestResolveSkillIds:
    """Tests for SDEQueryService.resolve_skill_ids()."""

    def test_resolve_skill_ids_returns_correct_ids(self, mock_sde_service):
        result = mock_sde_service.resolve_skill_ids(["Drones", "Drone Interfacing"])
        assert result["Drones"] == 3436
        assert result["Drone Interfacing"] == 3442

    def test_resolve_skill_ids_raises_on_missing_name(self, mock_sde_service):
        with pytest.raises(SDEResolutionError) as exc_info:
            mock_sde_service.resolve_skill_ids(["FakeSkill"])
        assert "FakeSkill" in exc_info.value.missing_names

    def test_resolve_skill_ids_case_insensitive(self, mock_sde_service):
        result = mock_sde_service.resolve_skill_ids(["drone interfacing"])
        assert result["drone interfacing"] == 3442

    def test_resolve_skill_ids_empty_list(self, mock_sde_service):
        result = mock_sde_service.resolve_skill_ids([])
        assert result == {}

    def test_resolve_skill_ids_filters_to_skills_category(self, mock_sde_service):
        """A name that exists in category 6 (Ship) should not resolve as a skill."""
        with pytest.raises(SDEResolutionError) as exc_info:
            mock_sde_service.resolve_skill_ids(["Vexor"])
        assert "Vexor" in exc_info.value.missing_names

    def test_resolve_skill_ids_with_duplicates(self, mock_sde_service):
        result = mock_sde_service.resolve_skill_ids(["Drones", "Drones"])
        assert len(result) == 1
        assert result["Drones"] == 3436

    def test_resolve_skill_ids_ambiguous_name(self, mock_sde_db, monkeypatch):
        """If SDE contains duplicate names in category 16, raise SDEResolutionError."""
        import threading
        from unittest.mock import MagicMock
        from aria_esi.mcp.sde.queries import SDEQueryService

        conn = sqlite3.connect(str(mock_sde_db))
        # Insert a duplicate skill name with different type_id
        conn.execute("INSERT INTO types VALUES (99999, 'Drones', 'drones', 16, 1)")
        conn.commit()
        conn.close()

        mock_db = MagicMock()
        mock_db._get_connection.return_value = sqlite3.connect(str(mock_sde_db))

        service = SDEQueryService.__new__(SDEQueryService)
        service._db = mock_db
        service._lock = threading.Lock()
        service._corp_regions = {}
        service._seeding_corps = {}
        service._category_ids = {}
        service._corp_info = {}
        service._station_info = {}
        service._npc_station_regions = None
        service._skill_attrs = {}
        service._skill_prereqs = {}
        service._type_requirements = {}
        service._meta_groups = {}
        service._meta_variants_by_parent = {}
        service._parent_type = {}
        service._cache_import_timestamp = None

        with pytest.raises(SDEResolutionError, match="Ambiguous"):
            service.resolve_skill_ids(["Drones"])

    def test_resolve_skill_ids_partial_failure_reports_all_missing(self, mock_sde_service):
        with pytest.raises(SDEResolutionError) as exc_info:
            mock_sde_service.resolve_skill_ids(["Drones", "FakeSkill1", "FakeSkill2"])
        assert "FakeSkill1" in exc_info.value.missing_names
        assert "FakeSkill2" in exc_info.value.missing_names
        assert len(exc_info.value.missing_names) == 2

    def test_resolve_skill_ids_sde_not_seeded(self, tmp_path, monkeypatch):
        """When types table is missing, SDENotSeededError is raised."""
        import threading
        from unittest.mock import MagicMock
        from aria_esi.mcp.sde.queries import SDENotSeededError, SDEQueryService

        db_path = tmp_path / "empty.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")
        conn.commit()
        conn.close()

        mock_db = MagicMock()
        mock_db._get_connection.return_value = sqlite3.connect(str(db_path))

        service = SDEQueryService.__new__(SDEQueryService)
        service._db = mock_db
        service._lock = threading.Lock()
        service._corp_regions = {}
        service._seeding_corps = {}
        service._category_ids = {}
        service._corp_info = {}
        service._station_info = {}
        service._npc_station_regions = None
        service._skill_attrs = {}
        service._skill_prereqs = {}
        service._type_requirements = {}
        service._meta_groups = {}
        service._meta_variants_by_parent = {}
        service._parent_type = {}
        service._cache_import_timestamp = None

        with pytest.raises(SDENotSeededError):
            service.resolve_skill_ids(["Drones"])

    def test_resolve_skill_ids_empty_types_table(self, tmp_path):
        """When types table exists but has zero rows, all names are missing."""
        import threading
        from unittest.mock import MagicMock
        from aria_esi.mcp.sde.queries import SDEQueryService

        db_path = tmp_path / "empty_types.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "CREATE TABLE types (type_id INTEGER, type_name TEXT, type_name_lower TEXT, category_id INTEGER, published INTEGER)"
        )
        conn.execute("CREATE TABLE groups (group_id INTEGER, category_id INTEGER, group_name TEXT)")
        conn.execute("CREATE TABLE npc_corporations (corporation_id INTEGER)")
        conn.execute("CREATE TABLE npc_seeding (type_id INTEGER)")
        conn.execute("CREATE TABLE stations (station_id INTEGER)")
        conn.execute("CREATE TABLE regions (region_id INTEGER)")
        conn.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")
        conn.commit()
        conn.close()

        mock_db = MagicMock()
        mock_db._get_connection.return_value = sqlite3.connect(str(db_path))

        service = SDEQueryService.__new__(SDEQueryService)
        service._db = mock_db
        service._lock = threading.Lock()
        service._corp_regions = {}
        service._seeding_corps = {}
        service._category_ids = {}
        service._corp_info = {}
        service._station_info = {}
        service._npc_station_regions = None
        service._skill_attrs = {}
        service._skill_prereqs = {}
        service._type_requirements = {}
        service._meta_groups = {}
        service._meta_variants_by_parent = {}
        service._parent_type = {}
        service._cache_import_timestamp = None

        with pytest.raises(SDEResolutionError) as exc_info:
            service.resolve_skill_ids(["Drones", "Mechanics"])
        assert len(exc_info.value.missing_names) == 2

    def test_resolve_skill_ids_preserves_input_key_casing(self, mock_sde_service):
        result = mock_sde_service.resolve_skill_ids(["drone interfacing"])
        assert "drone interfacing" in result
        assert "Drone Interfacing" not in result
