"""Tests for sovereignty database."""

import tempfile
from pathlib import Path

import pytest

from aria_esi.services.sovereignty.database import (
    AllianceRecord,
    CoalitionRecord,
    SovereigntyDatabase,
    SovereigntyRecord,
    get_sovereignty_database,
    reset_sovereignty_database,
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_sovereignty.db"
        db = SovereigntyDatabase(db_path=db_path)
        yield db
        db.close()


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the singleton before and after each test."""
    reset_sovereignty_database()
    yield
    reset_sovereignty_database()


class TestSovereigntyDatabaseInit:
    """Tests for database initialization."""

    def test_creates_database_file(self, temp_db: SovereigntyDatabase):
        """Test that database file is created."""
        # Access connection to trigger initialization
        _ = temp_db._get_connection()
        assert temp_db.db_path.exists()

    def test_schema_version_is_set(self, temp_db: SovereigntyDatabase):
        """Test that schema version is properly set."""
        conn = temp_db._get_connection()
        row = conn.execute(
            "SELECT value FROM metadata WHERE key = 'schema_version'"
        ).fetchone()
        assert row is not None
        assert row["value"] == "1"

    def test_tables_created(self, temp_db: SovereigntyDatabase):
        """Test that all required tables are created."""
        conn = temp_db._get_connection()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {row["name"] for row in tables}

        expected_tables = {
            "sovereignty_map",
            "alliances",
            "coalitions",
            "coalition_members",
            "metadata",
        }
        assert expected_tables.issubset(table_names)


class TestSovereigntyOperations:
    """Tests for sovereignty map CRUD operations."""

    def test_save_and_get_sovereignty(self, temp_db: SovereigntyDatabase):
        """Test saving and retrieving sovereignty."""
        record = SovereigntyRecord(
            system_id=30004759,
            alliance_id=1354830081,
            corporation_id=98169165,
            faction_id=None,
            updated_at=1700000000,
        )
        temp_db.save_sovereignty(record)

        result = temp_db.get_sovereignty(30004759)
        assert result is not None
        assert result.system_id == 30004759
        assert result.alliance_id == 1354830081
        assert result.corporation_id == 98169165

    def test_get_sovereignty_not_found(self, temp_db: SovereigntyDatabase):
        """Test getting non-existent sovereignty."""
        result = temp_db.get_sovereignty(99999999)
        assert result is None

    def test_save_sovereignty_batch(self, temp_db: SovereigntyDatabase):
        """Test saving multiple sovereignty records."""
        records = [
            SovereigntyRecord(
                system_id=30000001,
                alliance_id=1000001,
                corporation_id=None,
                faction_id=None,
                updated_at=1700000000,
            ),
            SovereigntyRecord(
                system_id=30000002,
                alliance_id=1000002,
                corporation_id=None,
                faction_id=None,
                updated_at=1700000000,
            ),
            SovereigntyRecord(
                system_id=30000003,
                alliance_id=None,
                corporation_id=None,
                faction_id=500010,
                updated_at=1700000000,
            ),
        ]
        count = temp_db.save_sovereignty_batch(records)
        assert count == 3

        # Verify all records
        result1 = temp_db.get_sovereignty(30000001)
        assert result1 is not None
        assert result1.alliance_id == 1000001

        result3 = temp_db.get_sovereignty(30000003)
        assert result3 is not None
        assert result3.faction_id == 500010

    def test_save_sovereignty_batch_empty(self, temp_db: SovereigntyDatabase):
        """Test saving empty batch."""
        count = temp_db.save_sovereignty_batch([])
        assert count == 0

    def test_get_sovereignty_batch(self, temp_db: SovereigntyDatabase):
        """Test batch retrieval of sovereignty."""
        records = [
            SovereigntyRecord(
                system_id=30000001, alliance_id=1000001, corporation_id=None,
                faction_id=None, updated_at=1700000000
            ),
            SovereigntyRecord(
                system_id=30000002, alliance_id=1000002, corporation_id=None,
                faction_id=None, updated_at=1700000000
            ),
        ]
        temp_db.save_sovereignty_batch(records)

        # Fetch batch including one non-existent
        results = temp_db.get_sovereignty_batch([30000001, 30000002, 99999999])
        assert len(results) == 2
        assert 30000001 in results
        assert 30000002 in results
        assert 99999999 not in results

    def test_get_sovereignty_batch_empty(self, temp_db: SovereigntyDatabase):
        """Test batch retrieval with empty list."""
        results = temp_db.get_sovereignty_batch([])
        assert results == {}

    def test_get_systems_by_alliance(self, temp_db: SovereigntyDatabase):
        """Test getting systems by alliance."""
        records = [
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
        temp_db.save_sovereignty_batch(records)

        systems = temp_db.get_systems_by_alliance(1000001)
        assert len(systems) == 2
        assert 30000001 in systems
        assert 30000002 in systems

    def test_get_systems_by_faction(self, temp_db: SovereigntyDatabase):
        """Test getting systems by NPC faction."""
        records = [
            SovereigntyRecord(
                system_id=30000001, alliance_id=None, corporation_id=None,
                faction_id=500010, updated_at=1700000000
            ),
            SovereigntyRecord(
                system_id=30000002, alliance_id=None, corporation_id=None,
                faction_id=500010, updated_at=1700000000
            ),
        ]
        temp_db.save_sovereignty_batch(records)

        systems = temp_db.get_systems_by_faction(500010)
        assert len(systems) == 2

    def test_clear_sovereignty(self, temp_db: SovereigntyDatabase):
        """Test clearing all sovereignty data."""
        records = [
            SovereigntyRecord(
                system_id=30000001, alliance_id=1000001, corporation_id=None,
                faction_id=None, updated_at=1700000000
            ),
        ]
        temp_db.save_sovereignty_batch(records)

        count = temp_db.clear_sovereignty()
        assert count == 1

        result = temp_db.get_sovereignty(30000001)
        assert result is None


class TestAllianceOperations:
    """Tests for alliance CRUD operations."""

    def test_save_and_get_alliance(self, temp_db: SovereigntyDatabase):
        """Test saving and retrieving alliance."""
        record = AllianceRecord(
            alliance_id=1354830081,
            name="Goonswarm Federation",
            ticker="CONDI",
            executor_corporation_id=98169165,
            faction_id=None,
            updated_at=1700000000,
        )
        temp_db.save_alliance(record)

        result = temp_db.get_alliance(1354830081)
        assert result is not None
        assert result.name == "Goonswarm Federation"
        assert result.ticker == "CONDI"

    def test_get_alliance_not_found(self, temp_db: SovereigntyDatabase):
        """Test getting non-existent alliance."""
        result = temp_db.get_alliance(99999999)
        assert result is None

    def test_save_alliances_batch(self, temp_db: SovereigntyDatabase):
        """Test saving multiple alliance records."""
        records = [
            AllianceRecord(
                alliance_id=1000001, name="Alliance One", ticker="ONE",
                executor_corporation_id=None, faction_id=None, updated_at=1700000000
            ),
            AllianceRecord(
                alliance_id=1000002, name="Alliance Two", ticker="TWO",
                executor_corporation_id=None, faction_id=None, updated_at=1700000000
            ),
        ]
        count = temp_db.save_alliances_batch(records)
        assert count == 2

    def test_get_alliances_batch(self, temp_db: SovereigntyDatabase):
        """Test batch retrieval of alliances."""
        records = [
            AllianceRecord(
                alliance_id=1000001, name="Alliance One", ticker="ONE",
                executor_corporation_id=None, faction_id=None, updated_at=1700000000
            ),
            AllianceRecord(
                alliance_id=1000002, name="Alliance Two", ticker="TWO",
                executor_corporation_id=None, faction_id=None, updated_at=1700000000
            ),
        ]
        temp_db.save_alliances_batch(records)

        results = temp_db.get_alliances_batch([1000001, 1000002, 99999999])
        assert len(results) == 2
        assert 1000001 in results
        assert results[1000001].name == "Alliance One"


class TestCoalitionOperations:
    """Tests for coalition CRUD operations."""

    def test_save_and_get_coalition(self, temp_db: SovereigntyDatabase):
        """Test saving and retrieving coalition."""
        record = CoalitionRecord(
            coalition_id="imperium",
            display_name="The Imperium",
            aliases=["goons", "gsf", "bees"],
            updated_at=1700000000,
        )
        temp_db.save_coalition(record)

        result = temp_db.get_coalition("imperium")
        assert result is not None
        assert result.display_name == "The Imperium"
        assert "goons" in result.aliases

    def test_get_coalition_not_found(self, temp_db: SovereigntyDatabase):
        """Test getting non-existent coalition."""
        result = temp_db.get_coalition("nonexistent")
        assert result is None

    def test_get_coalition_by_alias(self, temp_db: SovereigntyDatabase):
        """Test finding coalition by alias."""
        record = CoalitionRecord(
            coalition_id="imperium",
            display_name="The Imperium",
            aliases=["goons", "gsf", "bees"],
            updated_at=1700000000,
        )
        temp_db.save_coalition(record)

        # Search by alias
        result = temp_db.get_coalition_by_alias("goons")
        assert result is not None
        assert result.coalition_id == "imperium"

        # Search by display name (case insensitive)
        result = temp_db.get_coalition_by_alias("the imperium")
        assert result is not None

        # Search by coalition_id
        result = temp_db.get_coalition_by_alias("IMPERIUM")
        assert result is not None

    def test_get_coalition_by_alias_not_found(self, temp_db: SovereigntyDatabase):
        """Test finding coalition with non-existent alias."""
        result = temp_db.get_coalition_by_alias("nonexistent")
        assert result is None

    def test_get_all_coalitions(self, temp_db: SovereigntyDatabase):
        """Test getting all coalitions."""
        records = [
            CoalitionRecord(
                coalition_id="imperium", display_name="The Imperium",
                aliases=["goons"], updated_at=1700000000
            ),
            CoalitionRecord(
                coalition_id="panfam", display_name="PanFam",
                aliases=["pandemic"], updated_at=1700000000
            ),
        ]
        for r in records:
            temp_db.save_coalition(r)

        results = temp_db.get_all_coalitions()
        assert len(results) == 2
        # Should be ordered by display_name
        assert results[0].display_name == "PanFam"  # P before T

    def test_save_coalition_members(self, temp_db: SovereigntyDatabase):
        """Test saving coalition membership."""
        record = CoalitionRecord(
            coalition_id="imperium",
            display_name="The Imperium",
            aliases=["goons"],
            updated_at=1700000000,
        )
        temp_db.save_coalition(record)

        count = temp_db.save_coalition_members("imperium", [1000001, 1000002, 1000003])
        assert count == 3

        alliances = temp_db.get_coalition_alliances("imperium")
        assert len(alliances) == 3

    def test_get_coalition_for_alliance(self, temp_db: SovereigntyDatabase):
        """Test getting coalition for an alliance."""
        record = CoalitionRecord(
            coalition_id="imperium",
            display_name="The Imperium",
            aliases=["goons"],
            updated_at=1700000000,
        )
        temp_db.save_coalition(record)
        temp_db.save_coalition_members("imperium", [1354830081])

        coalition_id = temp_db.get_coalition_for_alliance(1354830081)
        assert coalition_id == "imperium"

        # Non-member alliance
        coalition_id = temp_db.get_coalition_for_alliance(99999999)
        assert coalition_id is None

    def test_save_coalition_members_replaces(self, temp_db: SovereigntyDatabase):
        """Test that saving coalition members replaces existing."""
        record = CoalitionRecord(
            coalition_id="imperium",
            display_name="The Imperium",
            aliases=["goons"],
            updated_at=1700000000,
        )
        temp_db.save_coalition(record)

        # Initial members
        temp_db.save_coalition_members("imperium", [1000001, 1000002])
        assert len(temp_db.get_coalition_alliances("imperium")) == 2

        # Replace with new members
        temp_db.save_coalition_members("imperium", [1000003])
        alliances = temp_db.get_coalition_alliances("imperium")
        assert len(alliances) == 1
        assert 1000003 in alliances

    def test_clear_coalitions(self, temp_db: SovereigntyDatabase):
        """Test clearing all coalition data removes coalitions and members."""
        # Create two coalitions with members
        records = [
            CoalitionRecord(
                coalition_id="imperium", display_name="The Imperium",
                aliases=["goons"], updated_at=1700000000
            ),
            CoalitionRecord(
                coalition_id="panfam", display_name="PanFam",
                aliases=["pandemic"], updated_at=1700000000
            ),
        ]
        for r in records:
            temp_db.save_coalition(r)

        temp_db.save_coalition_members("imperium", [1000001, 1000002])
        temp_db.save_coalition_members("panfam", [1000003])

        # Verify data exists
        assert len(temp_db.get_all_coalitions()) == 2
        assert len(temp_db.get_coalition_alliances("imperium")) == 2
        assert len(temp_db.get_coalition_alliances("panfam")) == 1

        # Clear all coalitions
        count = temp_db.clear_coalitions()
        assert count == 2  # Two coalitions were deleted

        # Verify all data is gone
        assert len(temp_db.get_all_coalitions()) == 0
        assert temp_db.get_coalition("imperium") is None
        assert temp_db.get_coalition("panfam") is None
        assert len(temp_db.get_coalition_alliances("imperium")) == 0
        assert temp_db.get_coalition_for_alliance(1000001) is None


class TestDatabaseStats:
    """Tests for database statistics."""

    def test_get_stats(self, temp_db: SovereigntyDatabase):
        """Test getting database statistics."""
        # Add some data
        sov_records = [
            SovereigntyRecord(
                system_id=30000001, alliance_id=1000001, corporation_id=None,
                faction_id=None, updated_at=1700000000
            ),
        ]
        temp_db.save_sovereignty_batch(sov_records)

        alliance_records = [
            AllianceRecord(
                alliance_id=1000001, name="Test Alliance", ticker="TEST",
                executor_corporation_id=None, faction_id=None, updated_at=1700000000
            ),
        ]
        temp_db.save_alliances_batch(alliance_records)

        coalition = CoalitionRecord(
            coalition_id="test",
            display_name="Test Coalition",
            aliases=[],
            updated_at=1700000000,
        )
        temp_db.save_coalition(coalition)

        stats = temp_db.get_stats()
        assert stats["sovereignty_count"] == 1
        assert stats["alliance_count"] == 1
        assert stats["coalition_count"] == 1
        assert "database_path" in stats
        assert "database_size_kb" in stats


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_sovereignty_database_returns_same_instance(self):
        """Test that get_sovereignty_database returns same instance."""
        db1 = get_sovereignty_database()
        db2 = get_sovereignty_database()
        assert db1 is db2

    def test_reset_clears_singleton(self):
        """Test that reset clears the singleton."""
        db1 = get_sovereignty_database()
        reset_sovereignty_database()
        db2 = get_sovereignty_database()
        assert db1 is not db2
