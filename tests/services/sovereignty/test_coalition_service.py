"""Tests for coalition service."""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from aria_esi.services.sovereignty.coalition_service import (
    CoalitionRegistry,
    analyze_territory,
    get_coalition_registry,
    get_systems_by_coalition,
    reset_coalition_registry,
)
from aria_esi.services.sovereignty.database import (
    AllianceRecord,
    CoalitionRecord,
    SovereigntyDatabase,
    SovereigntyRecord,
    reset_sovereignty_database,
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_sovereignty.db"

        # Patch the get_sovereignty_database to return our temp db
        db = SovereigntyDatabase(db_path=db_path)

        with patch(
            "aria_esi.services.sovereignty.coalition_service.get_sovereignty_database",
            return_value=db,
        ):
            yield db

        db.close()


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singletons before and after each test."""
    reset_sovereignty_database()
    reset_coalition_registry()
    yield
    reset_sovereignty_database()
    reset_coalition_registry()


class TestCoalitionRegistry:
    """Tests for CoalitionRegistry class."""

    def test_get_coalition(self, temp_db: SovereigntyDatabase):
        """Test getting coalition by ID."""
        # Setup coalition data
        coalition = CoalitionRecord(
            coalition_id="imperium",
            display_name="The Imperium",
            aliases=["goons", "gsf"],
            updated_at=1700000000,
        )
        temp_db.save_coalition(coalition)

        registry = CoalitionRegistry()
        with patch(
            "aria_esi.services.sovereignty.coalition_service.get_sovereignty_database",
            return_value=temp_db,
        ):
            result = registry.get_coalition("imperium")

        assert result is not None
        assert result.coalition_id == "imperium"
        assert result.display_name == "The Imperium"

    def test_get_coalition_not_found(self, temp_db: SovereigntyDatabase):
        """Test getting non-existent coalition."""
        registry = CoalitionRegistry()
        with patch(
            "aria_esi.services.sovereignty.coalition_service.get_sovereignty_database",
            return_value=temp_db,
        ):
            result = registry.get_coalition("nonexistent")

        assert result is None

    def test_resolve_coalition_alias(self, temp_db: SovereigntyDatabase):
        """Test resolving coalition by alias."""
        coalition = CoalitionRecord(
            coalition_id="imperium",
            display_name="The Imperium",
            aliases=["goons", "gsf", "bees"],
            updated_at=1700000000,
        )
        temp_db.save_coalition(coalition)

        registry = CoalitionRegistry()
        with patch(
            "aria_esi.services.sovereignty.coalition_service.get_sovereignty_database",
            return_value=temp_db,
        ):
            result = registry.resolve_coalition_alias("goons")

        assert result is not None
        assert result.coalition_id == "imperium"

    def test_get_coalition_for_alliance(self, temp_db: SovereigntyDatabase):
        """Test getting coalition for an alliance."""
        coalition = CoalitionRecord(
            coalition_id="imperium",
            display_name="The Imperium",
            aliases=["goons"],
            updated_at=1700000000,
        )
        temp_db.save_coalition(coalition)
        temp_db.save_coalition_members("imperium", [1354830081])

        registry = CoalitionRegistry()
        with patch(
            "aria_esi.services.sovereignty.coalition_service.get_sovereignty_database",
            return_value=temp_db,
        ):
            result = registry.get_coalition_for_alliance(1354830081)

        assert result is not None
        assert result.coalition_id == "imperium"

    def test_get_coalition_for_alliance_not_in_coalition(
        self, temp_db: SovereigntyDatabase
    ):
        """Test getting coalition for alliance not in any coalition."""
        registry = CoalitionRegistry()
        with patch(
            "aria_esi.services.sovereignty.coalition_service.get_sovereignty_database",
            return_value=temp_db,
        ):
            result = registry.get_coalition_for_alliance(99999999)

        assert result is None

    def test_get_all_coalitions(self, temp_db: SovereigntyDatabase):
        """Test getting all coalitions."""
        coalitions = [
            CoalitionRecord(
                coalition_id="imperium",
                display_name="The Imperium",
                aliases=["goons"],
                updated_at=1700000000,
            ),
            CoalitionRecord(
                coalition_id="panfam",
                display_name="PanFam",
                aliases=["pandemic"],
                updated_at=1700000000,
            ),
        ]
        for c in coalitions:
            temp_db.save_coalition(c)

        registry = CoalitionRegistry()
        with patch(
            "aria_esi.services.sovereignty.coalition_service.get_sovereignty_database",
            return_value=temp_db,
        ):
            results = registry.get_all_coalitions()

        assert len(results) == 2

    def test_get_coalition_alliances(self, temp_db: SovereigntyDatabase):
        """Test getting alliances in a coalition."""
        coalition = CoalitionRecord(
            coalition_id="imperium",
            display_name="The Imperium",
            aliases=["goons"],
            updated_at=1700000000,
        )
        temp_db.save_coalition(coalition)
        temp_db.save_coalition_members("imperium", [1000001, 1000002, 1000003])

        registry = CoalitionRegistry()
        with patch(
            "aria_esi.services.sovereignty.coalition_service.get_sovereignty_database",
            return_value=temp_db,
        ):
            alliances = registry.get_coalition_alliances("imperium")

        assert len(alliances) == 3


class TestAnalyzeTerritory:
    """Tests for analyze_territory function."""

    def test_analyze_coalition_territory(self, temp_db: SovereigntyDatabase):
        """Test territory analysis for a coalition."""
        # Setup coalition
        coalition = CoalitionRecord(
            coalition_id="imperium",
            display_name="The Imperium",
            aliases=["goons"],
            updated_at=1700000000,
        )
        temp_db.save_coalition(coalition)
        temp_db.save_coalition_members("imperium", [1000001])

        # Setup alliance
        alliance = AllianceRecord(
            alliance_id=1000001,
            name="Test Alliance",
            ticker="TEST",
            executor_corporation_id=None,
            faction_id=None,
            updated_at=1700000000,
        )
        temp_db.save_alliance(alliance)

        # Setup sovereignty
        sov_records = [
            SovereigntyRecord(
                system_id=30004759,
                alliance_id=1000001,
                corporation_id=None,
                faction_id=None,
                updated_at=1700000000,
            ),
        ]
        temp_db.save_sovereignty_batch(sov_records)

        # Mock universe graph
        mock_universe = MagicMock()
        mock_universe.id_to_idx = {30004759: 0}
        mock_universe.idx_to_name = {0: "1DQ1-A"}
        mock_universe.get_region_name.return_value = "Delve"
        mock_universe.constellation_ids = [20000871]

        with patch(
            "aria_esi.services.sovereignty.coalition_service.get_sovereignty_database",
            return_value=temp_db,
        ):
            with patch(
                "aria_esi.universe.builder.load_universe_graph",
                return_value=mock_universe,
            ):
                result = analyze_territory(coalition_id="imperium")

        assert result["entity_name"] == "The Imperium"
        assert result["entity_type"] == "coalition"
        assert result["system_count"] == 1

    def test_analyze_alliance_territory(self, temp_db: SovereigntyDatabase):
        """Test territory analysis for an alliance."""
        # Setup alliance
        alliance = AllianceRecord(
            alliance_id=1000001,
            name="Test Alliance",
            ticker="TEST",
            executor_corporation_id=None,
            faction_id=None,
            updated_at=1700000000,
        )
        temp_db.save_alliance(alliance)

        # Setup sovereignty
        sov_records = [
            SovereigntyRecord(
                system_id=30004759,
                alliance_id=1000001,
                corporation_id=None,
                faction_id=None,
                updated_at=1700000000,
            ),
        ]
        temp_db.save_sovereignty_batch(sov_records)

        # Mock universe graph
        mock_universe = MagicMock()
        mock_universe.id_to_idx = {30004759: 0}
        mock_universe.idx_to_name = {0: "1DQ1-A"}
        mock_universe.get_region_name.return_value = "Delve"
        mock_universe.constellation_ids = [20000871]

        with patch(
            "aria_esi.services.sovereignty.coalition_service.get_sovereignty_database",
            return_value=temp_db,
        ):
            with patch(
                "aria_esi.universe.builder.load_universe_graph",
                return_value=mock_universe,
            ):
                result = analyze_territory(alliance_id=1000001)

        assert result["entity_name"] == "[TEST] Test Alliance"
        assert result["entity_type"] == "alliance"

    def test_analyze_territory_coalition_not_found(self, temp_db: SovereigntyDatabase):
        """Test territory analysis with unknown coalition."""
        with patch(
            "aria_esi.services.sovereignty.coalition_service.get_sovereignty_database",
            return_value=temp_db,
        ):
            result = analyze_territory(coalition_id="nonexistent")

        assert "error" in result
        assert result["error"] == "coalition_not_found"

    def test_analyze_territory_alliance_not_found(self, temp_db: SovereigntyDatabase):
        """Test territory analysis with unknown alliance."""
        with patch(
            "aria_esi.services.sovereignty.coalition_service.get_sovereignty_database",
            return_value=temp_db,
        ):
            result = analyze_territory(alliance_id=99999999)

        assert "error" in result
        assert result["error"] == "alliance_not_found"

    def test_analyze_territory_missing_parameter(self, temp_db: SovereigntyDatabase):
        """Test territory analysis with no parameters."""
        with patch(
            "aria_esi.services.sovereignty.coalition_service.get_sovereignty_database",
            return_value=temp_db,
        ):
            result = analyze_territory()

        assert "error" in result
        assert result["error"] == "missing_parameter"

    def test_analyze_territory_no_sovereignty(self, temp_db: SovereigntyDatabase):
        """Test territory analysis when alliance has no sovereignty."""
        # Setup alliance
        alliance = AllianceRecord(
            alliance_id=1000001,
            name="Test Alliance",
            ticker="TEST",
            executor_corporation_id=None,
            faction_id=None,
            updated_at=1700000000,
        )
        temp_db.save_alliance(alliance)

        with patch(
            "aria_esi.services.sovereignty.coalition_service.get_sovereignty_database",
            return_value=temp_db,
        ):
            result = analyze_territory(alliance_id=1000001)

        assert result["system_count"] == 0
        assert "message" in result


class TestGetSystemsByCoalition:
    """Tests for get_systems_by_coalition function."""

    def test_get_systems_by_coalition(self, temp_db: SovereigntyDatabase):
        """Test getting systems by coalition ID."""
        # Setup coalition
        coalition = CoalitionRecord(
            coalition_id="imperium",
            display_name="The Imperium",
            aliases=["goons"],
            updated_at=1700000000,
        )
        temp_db.save_coalition(coalition)
        temp_db.save_coalition_members("imperium", [1000001, 1000002])

        # Setup sovereignty
        sov_records = [
            SovereigntyRecord(
                system_id=30000001, alliance_id=1000001, corporation_id=None,
                faction_id=None, updated_at=1700000000
            ),
            SovereigntyRecord(
                system_id=30000002, alliance_id=1000001, corporation_id=None,
                faction_id=None, updated_at=1700000000
            ),
            SovereigntyRecord(
                system_id=30000003, alliance_id=1000002, corporation_id=None,
                faction_id=None, updated_at=1700000000
            ),
        ]
        temp_db.save_sovereignty_batch(sov_records)

        with patch(
            "aria_esi.services.sovereignty.coalition_service.get_sovereignty_database",
            return_value=temp_db,
        ):
            systems = get_systems_by_coalition("imperium")

        assert len(systems) == 3
        assert 30000001 in systems
        assert 30000002 in systems
        assert 30000003 in systems

    def test_get_systems_by_coalition_alias(self, temp_db: SovereigntyDatabase):
        """Test getting systems by coalition alias."""
        # Setup coalition
        coalition = CoalitionRecord(
            coalition_id="imperium",
            display_name="The Imperium",
            aliases=["goons", "bees"],
            updated_at=1700000000,
        )
        temp_db.save_coalition(coalition)
        temp_db.save_coalition_members("imperium", [1000001])

        # Setup sovereignty
        sov_records = [
            SovereigntyRecord(
                system_id=30000001, alliance_id=1000001, corporation_id=None,
                faction_id=None, updated_at=1700000000
            ),
        ]
        temp_db.save_sovereignty_batch(sov_records)

        with patch(
            "aria_esi.services.sovereignty.coalition_service.get_sovereignty_database",
            return_value=temp_db,
        ):
            systems = get_systems_by_coalition("goons")

        assert len(systems) == 1
        assert 30000001 in systems

    def test_get_systems_by_coalition_not_found(self, temp_db: SovereigntyDatabase):
        """Test getting systems for unknown coalition."""
        with patch(
            "aria_esi.services.sovereignty.coalition_service.get_sovereignty_database",
            return_value=temp_db,
        ):
            systems = get_systems_by_coalition("nonexistent")

        assert systems == []


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_coalition_registry_returns_same_instance(self):
        """Test that get_coalition_registry returns same instance."""
        registry1 = get_coalition_registry()
        registry2 = get_coalition_registry()
        assert registry1 is registry2

    def test_reset_clears_singleton(self):
        """Test that reset clears the singleton."""
        registry1 = get_coalition_registry()
        reset_coalition_registry()
        registry2 = get_coalition_registry()
        assert registry1 is not registry2
