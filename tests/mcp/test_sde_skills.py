"""
Tests for SDE skill requirements and training time tools.
"""

import sqlite3

import pytest

from aria_esi.mcp.sde.queries import (
    SDEQueryService,
    SkillAttributes,
    SkillPrereq,
    TypeRequirement,
    reset_sde_query_service,
)
from aria_esi.mcp.sde.tools_skills import (
    SP_PER_LEVEL,
    calculate_sp_for_level,
    calculate_sp_per_minute,
    format_training_time,
)
from aria_esi.models.sde import (
    SkillInfo,
    SkillPrerequisite,
    SkillRequirementsResult,
    TrainingTimeResult,
    TypeSkillRequirement,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_db(tmp_path):
    """Create a mock database with skill tables."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Create required tables
    conn.executescript("""
        CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT);
        INSERT INTO metadata VALUES ('sde_import_timestamp', '2024-01-01T00:00:00Z');

        CREATE TABLE types (
            type_id INTEGER PRIMARY KEY,
            type_name TEXT,
            type_name_lower TEXT,
            category_id INTEGER,
            published INTEGER DEFAULT 1
        );

        CREATE TABLE categories (
            category_id INTEGER PRIMARY KEY,
            category_name TEXT,
            category_name_lower TEXT
        );

        CREATE TABLE skill_attributes (
            type_id INTEGER PRIMARY KEY,
            rank INTEGER,
            primary_attribute TEXT,
            secondary_attribute TEXT
        );

        CREATE TABLE skill_prerequisites (
            skill_type_id INTEGER,
            prerequisite_skill_id INTEGER,
            prerequisite_level INTEGER,
            PRIMARY KEY (skill_type_id, prerequisite_skill_id)
        );

        CREATE TABLE type_skill_requirements (
            type_id INTEGER,
            required_skill_id INTEGER,
            required_level INTEGER,
            PRIMARY KEY (type_id, required_skill_id)
        );

        -- Insert test categories
        INSERT INTO categories VALUES (6, 'Ship', 'ship');
        INSERT INTO categories VALUES (16, 'Skill', 'skill');

        -- Insert test skills
        INSERT INTO types VALUES (3426, 'Spaceship Command', 'spaceship command', 16, 1);
        INSERT INTO types VALUES (3327, 'Gallente Frigate', 'gallente frigate', 16, 1);
        INSERT INTO types VALUES (3328, 'Gallente Destroyer', 'gallente destroyer', 16, 1);
        INSERT INTO types VALUES (3329, 'Gallente Cruiser', 'gallente cruiser', 16, 1);
        INSERT INTO types VALUES (3392, 'Mechanics', 'mechanics', 16, 1);

        -- Insert test ship
        INSERT INTO types VALUES (17720, 'Vexor Navy Issue', 'vexor navy issue', 6, 1);

        -- Insert skill attributes
        INSERT INTO skill_attributes VALUES (3426, 1, 'perception', 'willpower');
        INSERT INTO skill_attributes VALUES (3327, 2, 'perception', 'willpower');
        INSERT INTO skill_attributes VALUES (3328, 4, 'perception', 'willpower');
        INSERT INTO skill_attributes VALUES (3329, 5, 'perception', 'willpower');
        INSERT INTO skill_attributes VALUES (3392, 1, 'intelligence', 'memory');

        -- Insert skill prerequisites (Gallente Frigate -> Spaceship Command III)
        INSERT INTO skill_prerequisites VALUES (3327, 3426, 3);
        -- Gallente Destroyer -> Gallente Frigate III
        INSERT INTO skill_prerequisites VALUES (3328, 3327, 3);
        -- Gallente Cruiser -> Gallente Destroyer III
        INSERT INTO skill_prerequisites VALUES (3329, 3328, 3);

        -- Insert ship skill requirements (Vexor Navy Issue -> Gallente Cruiser III)
        INSERT INTO type_skill_requirements VALUES (17720, 3329, 3);

        -- Required SDE tables for ensure_sde_seeded
        CREATE TABLE npc_corporations (corporation_id INTEGER PRIMARY KEY);
        CREATE TABLE npc_seeding (type_id INTEGER, corporation_id INTEGER);
        CREATE TABLE stations (station_id INTEGER PRIMARY KEY);
        CREATE TABLE regions (region_id INTEGER PRIMARY KEY);
    """)
    conn.commit()
    conn.close()

    return db_path


@pytest.fixture
def mock_market_db(mock_db):
    """Create a mock MarketDatabase that uses the test database."""

    class MockMarketDatabase:
        def __init__(self, db_path):
            self._db_path = db_path
            self._conn = None

        def _get_connection(self):
            if self._conn is None:
                self._conn = sqlite3.connect(str(self._db_path))
                self._conn.row_factory = sqlite3.Row
            return self._conn

        def close(self):
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    db = MockMarketDatabase(mock_db)
    yield db
    db.close()


@pytest.fixture
def query_service(mock_market_db):
    """Create a query service with mock database."""
    reset_sde_query_service()
    return SDEQueryService(mock_market_db)


# =============================================================================
# Training Time Calculation Tests
# =============================================================================


class TestTrainingTimeCalculations:
    """Test training time calculation utilities."""

    def test_sp_per_level_constants(self):
        """Verify SP per level constants are correct."""
        assert SP_PER_LEVEL[1] == 250
        assert SP_PER_LEVEL[2] == 1415
        assert SP_PER_LEVEL[3] == 8000
        assert SP_PER_LEVEL[4] == 45255
        assert SP_PER_LEVEL[5] == 256000

    def test_calculate_sp_for_level(self):
        """Test SP calculation for different ranks and levels."""
        # Rank 1 skill
        assert calculate_sp_for_level(1, 1) == 250
        assert calculate_sp_for_level(1, 5) == 256000

        # Rank 5 skill
        assert calculate_sp_for_level(5, 1) == 1250
        assert calculate_sp_for_level(5, 5) == 1280000

        # Invalid levels
        assert calculate_sp_for_level(1, 0) == 0
        assert calculate_sp_for_level(1, 6) == 0

    def test_calculate_sp_per_minute(self):
        """Test SP/min calculation with various attributes."""
        # Default attributes (20/20)
        sp_min = calculate_sp_per_minute("intelligence", "memory")
        assert sp_min == 30.0  # 20 + 20/2

        # Custom attributes
        attrs = {"intelligence": 27, "memory": 21}
        sp_min = calculate_sp_per_minute("intelligence", "memory", attrs)
        assert sp_min == 37.5  # 27 + 21/2

        # When secondary is None, it defaults to "memory" key lookup
        sp_min = calculate_sp_per_minute("intelligence", None, attrs)
        assert sp_min == 37.5  # 27 + 21/2 (memory in attrs is 21)


class TestFormatTrainingTime:
    """Test training time formatting."""

    def test_seconds(self):
        assert format_training_time(45) == "45s"

    def test_minutes(self):
        assert format_training_time(600) == "10m"
        assert format_training_time(3540) == "59m"

    def test_hours(self):
        assert format_training_time(3600) == "1h"
        assert format_training_time(7200) == "2h"
        assert format_training_time(9000) == "2h 30m"

    def test_days(self):
        assert format_training_time(86400) == "1d"
        assert format_training_time(172800) == "2d"
        assert format_training_time(90000) == "1d 1h"


# =============================================================================
# Query Service Tests
# =============================================================================


class TestSkillAttributes:
    """Test skill attribute queries."""

    def test_get_skill_attributes_found(self, query_service):
        """Test getting skill attributes for a known skill."""
        attrs = query_service.get_skill_attributes(3392)  # Mechanics

        assert attrs is not None
        assert attrs.type_id == 3392
        assert attrs.type_name == "Mechanics"
        assert attrs.rank == 1
        assert attrs.primary_attribute == "intelligence"
        assert attrs.secondary_attribute == "memory"

    def test_get_skill_attributes_not_found(self, query_service):
        """Test getting attributes for nonexistent skill."""
        attrs = query_service.get_skill_attributes(99999)
        assert attrs is None

    def test_get_skill_attributes_cached(self, query_service):
        """Test that skill attributes are cached."""
        attrs1 = query_service.get_skill_attributes(3392)
        attrs2 = query_service.get_skill_attributes(3392)

        # Same object (cached)
        assert attrs1 is attrs2


class TestSkillPrerequisites:
    """Test skill prerequisite queries."""

    def test_get_skill_prerequisites(self, query_service):
        """Test getting prerequisites for a skill."""
        prereqs = query_service.get_skill_prerequisites(3327)  # Gallente Frigate

        assert len(prereqs) == 1
        assert prereqs[0].skill_id == 3426  # Spaceship Command
        assert prereqs[0].skill_name == "Spaceship Command"
        assert prereqs[0].required_level == 3

    def test_get_skill_prerequisites_none(self, query_service):
        """Test skill with no prerequisites."""
        prereqs = query_service.get_skill_prerequisites(3426)  # Spaceship Command
        assert len(prereqs) == 0


class TestTypeRequirements:
    """Test type skill requirement queries."""

    def test_get_type_skill_requirements(self, query_service):
        """Test getting requirements for a ship."""
        reqs = query_service.get_type_skill_requirements(17720)  # Vexor Navy Issue

        assert len(reqs) == 1
        assert reqs[0].skill_id == 3329  # Gallente Cruiser
        assert reqs[0].skill_name == "Gallente Cruiser"
        assert reqs[0].required_level == 3

    def test_get_type_skill_requirements_none(self, query_service):
        """Test item with no requirements."""
        reqs = query_service.get_type_skill_requirements(3426)  # Spaceship Command (a skill)
        assert len(reqs) == 0


class TestFullSkillTree:
    """Test full skill tree resolution."""

    def test_get_full_skill_tree_ship(self, query_service):
        """Test getting full tree for a ship."""
        tree = query_service.get_full_skill_tree(17720)  # Vexor Navy Issue

        # Should include: Gallente Cruiser -> Gallente Destroyer -> Gallente Frigate -> Spaceship Command
        assert len(tree) == 4

        # Check all skills are present
        skill_ids = {s[0] for s in tree}
        assert 3329 in skill_ids  # Gallente Cruiser
        assert 3328 in skill_ids  # Gallente Destroyer
        assert 3327 in skill_ids  # Gallente Frigate
        assert 3426 in skill_ids  # Spaceship Command

    def test_get_full_skill_tree_skill(self, query_service):
        """Test getting full tree for a skill."""
        tree = query_service.get_full_skill_tree(3329)  # Gallente Cruiser

        # Should include: Gallente Destroyer -> Gallente Frigate -> Spaceship Command
        assert len(tree) == 3

        skill_ids = {s[0] for s in tree}
        assert 3328 in skill_ids  # Gallente Destroyer
        assert 3327 in skill_ids  # Gallente Frigate
        assert 3426 in skill_ids  # Spaceship Command


# =============================================================================
# Data Model Tests
# =============================================================================


class TestSkillModels:
    """Test skill-related data models."""

    def test_skill_prerequisite_model(self):
        """Test SkillPrerequisite model."""
        prereq = SkillPrerequisite(
            skill_id=3426,
            skill_name="Spaceship Command",
            required_level=3,
        )
        assert prereq.skill_id == 3426
        assert prereq.skill_name == "Spaceship Command"
        assert prereq.required_level == 3

    def test_skill_info_model(self):
        """Test SkillInfo model."""
        info = SkillInfo(
            type_id=3392,
            type_name="Mechanics",
            rank=1,
            primary_attribute="intelligence",
            secondary_attribute="memory",
            prerequisites=[],
        )
        assert info.type_id == 3392
        assert info.rank == 1

    def test_skill_requirements_result_model(self):
        """Test SkillRequirementsResult model."""
        result = SkillRequirementsResult(
            item="Vexor Navy Issue",
            item_type_id=17720,
            item_category="Ship",
            found=True,
            direct_requirements=[
                TypeSkillRequirement(
                    skill_id=3329,
                    skill_name="Gallente Cruiser",
                    required_level=3,
                )
            ],
            full_prerequisite_tree=[],
            total_skills=4,
        )
        assert result.found is True
        assert len(result.direct_requirements) == 1
        assert result.total_skills == 4

    def test_training_time_result_model(self):
        """Test TrainingTimeResult model."""
        result = TrainingTimeResult(
            skills=[{"skill_name": "Mechanics", "sp_needed": 256000}],
            total_skillpoints=256000,
            total_training_seconds=14222,
            total_training_formatted="3h 57m",
            warnings=[],
        )
        assert result.total_skillpoints == 256000
        assert "3h 57m" in result.total_training_formatted


# =============================================================================
# Data Class Tests
# =============================================================================


class TestQueryDataClasses:
    """Test query service data classes."""

    def test_skill_attributes_immutable(self):
        """Test SkillAttributes is immutable."""
        attrs = SkillAttributes(
            type_id=3392,
            type_name="Mechanics",
            rank=1,
            primary_attribute="intelligence",
            secondary_attribute="memory",
        )
        with pytest.raises(AttributeError):
            attrs.rank = 5

    def test_skill_prereq_immutable(self):
        """Test SkillPrereq is immutable."""
        prereq = SkillPrereq(
            skill_id=3426,
            skill_name="Spaceship Command",
            required_level=3,
        )
        with pytest.raises(AttributeError):
            prereq.required_level = 5

    def test_type_requirement_immutable(self):
        """Test TypeRequirement is immutable."""
        req = TypeRequirement(
            skill_id=3329,
            skill_name="Gallente Cruiser",
            required_level=3,
        )
        with pytest.raises(AttributeError):
            req.required_level = 5
