"""
Tests for Character Industry Service.
"""

import pytest
from unittest.mock import Mock

from aria_esi.services.character_industry import (
    INDUSTRY_SKILL_IDS,
    SKILL_ID_TO_NAME,
    get_character_blueprints,
    find_blueprint_for_item,
    get_character_industry_skills,
    get_invention_skills_for_item,
    calculate_character_invention_bonus,
    summarize_industry_capabilities,
)


class TestSkillMappings:
    """Test skill ID mappings."""

    @pytest.mark.unit
    def test_industry_skill_ids_populated(self):
        """Should have industry skill IDs."""
        assert len(INDUSTRY_SKILL_IDS) > 0
        assert "Industry" in INDUSTRY_SKILL_IDS
        assert "Advanced Industry" in INDUSTRY_SKILL_IDS

    @pytest.mark.unit
    def test_reverse_lookup_populated(self):
        """Should have reverse lookup."""
        assert len(SKILL_ID_TO_NAME) == len(INDUSTRY_SKILL_IDS)
        # Check Industry skill
        industry_id = INDUSTRY_SKILL_IDS["Industry"]
        assert SKILL_ID_TO_NAME[industry_id] == "Industry"

    @pytest.mark.unit
    def test_encryption_skills_present(self):
        """Should have all faction encryption skills."""
        assert "Amarr Encryption Methods" in INDUSTRY_SKILL_IDS
        assert "Caldari Encryption Methods" in INDUSTRY_SKILL_IDS
        assert "Gallente Encryption Methods" in INDUSTRY_SKILL_IDS
        assert "Minmatar Encryption Methods" in INDUSTRY_SKILL_IDS


class TestGetCharacterBlueprints:
    """Test blueprint fetching from ESI."""

    @pytest.mark.unit
    def test_returns_blueprints(self):
        """Should parse blueprint response."""
        mock_client = Mock()
        mock_client.get.return_value = [
            {
                "type_id": 1234,
                "item_id": 5678,
                "location_id": 60003760,
                "material_efficiency": 10,
                "time_efficiency": 20,
                "runs": 0,
                "quantity": -1,  # BPO
            },
            {
                "type_id": 2345,
                "item_id": 6789,
                "location_id": 60003760,
                "material_efficiency": 0,
                "time_efficiency": 0,
                "runs": 5,
                "quantity": -2,  # BPC
            },
        ]

        blueprints = get_character_blueprints(123456789, mock_client)

        assert len(blueprints) == 2
        # Check BPO
        assert blueprints[0]["type_id"] == 1234
        assert blueprints[0]["material_efficiency"] == 10
        assert blueprints[0]["is_bpo"] is True
        assert blueprints[0]["is_bpc"] is False
        # Check BPC
        assert blueprints[1]["type_id"] == 2345
        assert blueprints[1]["is_bpo"] is False
        assert blueprints[1]["is_bpc"] is True

    @pytest.mark.unit
    def test_handles_esi_error(self):
        """Should return empty list on ESI error."""
        mock_client = Mock()
        mock_client.get.side_effect = Exception("ESI Error")

        blueprints = get_character_blueprints(123456789, mock_client)

        assert blueprints == []

    @pytest.mark.unit
    def test_handles_non_list_response(self):
        """Should return empty list for non-list response."""
        mock_client = Mock()
        mock_client.get.return_value = None

        blueprints = get_character_blueprints(123456789, mock_client)

        assert blueprints == []


class TestFindBlueprintForItem:
    """Test blueprint matching logic."""

    @pytest.fixture
    def sample_blueprints(self):
        """Sample blueprint data."""
        return [
            {
                "type_id": 1234,
                "item_id": 1,
                "location_id": 60003760,
                "material_efficiency": 10,
                "time_efficiency": 20,
                "runs": 0,
                "is_bpo": True,
                "is_bpc": False,
            },
            {
                "type_id": 1234,
                "item_id": 2,
                "location_id": 60003760,
                "material_efficiency": 5,
                "time_efficiency": 10,
                "runs": 10,
                "is_bpo": False,
                "is_bpc": True,
            },
            {
                "type_id": 5678,
                "item_id": 3,
                "location_id": 60003760,
                "material_efficiency": 8,
                "time_efficiency": 16,
                "runs": 0,
                "is_bpo": True,
                "is_bpc": False,
            },
        ]

    @pytest.mark.unit
    def test_finds_matching_blueprint(self, sample_blueprints):
        """Should find blueprint by type ID."""
        bp = find_blueprint_for_item(sample_blueprints, 1234)
        assert bp is not None
        assert bp["type_id"] == 1234

    @pytest.mark.unit
    def test_prefers_bpo_by_default(self, sample_blueprints):
        """Should prefer BPO over BPC when prefer_bpo=True."""
        bp = find_blueprint_for_item(sample_blueprints, 1234, prefer_bpo=True)
        assert bp is not None
        assert bp["is_bpo"] is True
        assert bp["material_efficiency"] == 10

    @pytest.mark.unit
    def test_prefers_bpc_when_specified(self, sample_blueprints):
        """Should prefer BPC when prefer_bpo=False."""
        bp = find_blueprint_for_item(sample_blueprints, 1234, prefer_bpo=False)
        assert bp is not None
        assert bp["is_bpc"] is True
        assert bp["material_efficiency"] == 5

    @pytest.mark.unit
    def test_returns_none_when_not_found(self, sample_blueprints):
        """Should return None when no matching blueprint."""
        bp = find_blueprint_for_item(sample_blueprints, 9999)
        assert bp is None

    @pytest.mark.unit
    def test_empty_blueprint_list(self):
        """Should return None for empty list."""
        bp = find_blueprint_for_item([], 1234)
        assert bp is None


class TestGetCharacterIndustrySkills:
    """Test industry skill fetching from ESI."""

    @pytest.mark.unit
    def test_extracts_industry_skills(self):
        """Should extract industry-relevant skills."""
        mock_client = Mock()
        mock_client.get.return_value = {
            "skills": [
                {"skill_id": 3380, "trained_skill_level": 5},  # Industry
                {"skill_id": 3388, "trained_skill_level": 4},  # Advanced Industry
                {"skill_id": 99999, "trained_skill_level": 5},  # Non-industry skill
            ]
        }

        skills = get_character_industry_skills(123456789, mock_client)

        assert skills["Industry"] == 5
        assert skills["Advanced Industry"] == 4
        assert len(skills) == 2  # Only industry skills

    @pytest.mark.unit
    def test_handles_esi_error(self):
        """Should return empty dict on ESI error."""
        mock_client = Mock()
        mock_client.get.side_effect = Exception("ESI Error")

        skills = get_character_industry_skills(123456789, mock_client)

        assert skills == {}

    @pytest.mark.unit
    def test_handles_missing_skills_field(self):
        """Should return empty dict when skills field missing."""
        mock_client = Mock()
        mock_client.get.return_value = {}

        skills = get_character_industry_skills(123456789, mock_client)

        assert skills == {}


class TestGetInventionSkillsForItem:
    """Test invention skill mapping for items."""

    @pytest.mark.unit
    def test_gallente_ship_skills(self):
        """Should return Gallente skills for Gallente faction."""
        skills = get_invention_skills_for_item("Vexor", faction="Gallente")

        assert skills["encryption_skill"] == "Gallente Encryption Methods"
        assert skills["science_skill_1"] == "Gallentean Starship Engineering"
        assert skills["science_skill_2"] == "Mechanical Engineering"

    @pytest.mark.unit
    def test_minmatar_ship_skills(self):
        """Should handle Minmatar naming convention."""
        skills = get_invention_skills_for_item("Thrasher", faction="Minmatar")

        assert skills["encryption_skill"] == "Minmatar Encryption Methods"
        assert skills["science_skill_1"] == "Minmatar Starship Engineering"

    @pytest.mark.unit
    def test_shield_module_skills(self):
        """Should detect shield module skills."""
        skills = get_invention_skills_for_item("Medium Shield Extender II")

        assert skills["science_skill_1"] == "Electromagnetic Physics"
        assert skills["science_skill_2"] == "Graviton Physics"

    @pytest.mark.unit
    def test_armor_module_skills(self):
        """Should detect armor module skills."""
        skills = get_invention_skills_for_item("800mm Steel Plates II")

        assert skills["science_skill_1"] == "Mechanical Engineering"
        assert skills["science_skill_2"] == "Nanite Engineering"

    @pytest.mark.unit
    def test_drone_skills(self):
        """Should detect drone skills."""
        skills = get_invention_skills_for_item("Hammerhead II")

        assert skills["science_skill_1"] == "Mechanical Engineering"
        assert skills["science_skill_2"] == "Electronic Engineering"


class TestCalculateCharacterInventionBonus:
    """Test invention bonus calculation."""

    @pytest.mark.unit
    def test_zero_skills(self):
        """Should return 0 with no skills."""
        bonus = calculate_character_invention_bonus(
            character_skills={},
            encryption_skill="Gallente Encryption Methods",
            science_skill_1="Mechanical Engineering",
            science_skill_2="Electronic Engineering",
        )

        assert bonus == 0.0

    @pytest.mark.unit
    def test_max_skills(self):
        """Should calculate max bonus with level 5 skills."""
        skills = {
            "Gallente Encryption Methods": 5,
            "Mechanical Engineering": 5,
            "Electronic Engineering": 5,
        }

        bonus = calculate_character_invention_bonus(
            character_skills=skills,
            encryption_skill="Gallente Encryption Methods",
            science_skill_1="Mechanical Engineering",
            science_skill_2="Electronic Engineering",
        )

        # 5 + 5 + 5 = 15 levels * 0.01 = 0.15
        assert bonus == 0.15

    @pytest.mark.unit
    def test_partial_skills(self):
        """Should calculate with partial skill levels."""
        skills = {
            "Caldari Encryption Methods": 4,
            "Mechanical Engineering": 3,
        }

        bonus = calculate_character_invention_bonus(
            character_skills=skills,
            encryption_skill="Caldari Encryption Methods",
            science_skill_1="Mechanical Engineering",
            science_skill_2="Electronic Engineering",  # Not trained
        )

        # 4 + 3 + 0 = 7 levels * 0.01 = 0.07
        assert bonus == 0.07


class TestSummarizeIndustryCapabilities:
    """Test industry capability summary."""

    @pytest.mark.unit
    def test_base_slots(self):
        """Should calculate base manufacturing slots."""
        summary = summarize_industry_capabilities({})

        assert summary["manufacturing_slots"] == 1
        assert summary["science_slots"] == 1
        assert summary["time_reduction_percent"] == 0.0

    @pytest.mark.unit
    def test_max_slots(self):
        """Should calculate max slots with all skills at 5."""
        skills = {
            "Mass Production": 5,
            "Advanced Mass Production": 5,
            "Laboratory Operation": 5,
            "Advanced Laboratory Operation": 5,
            "Advanced Industry": 5,
        }

        summary = summarize_industry_capabilities(skills)

        # 1 base + 5 + 5 = 11 manufacturing slots
        assert summary["manufacturing_slots"] == 11
        # 1 base + 5 + 5 = 11 science slots
        assert summary["science_slots"] == 11
        # 5 * 3% = 15% time reduction
        assert summary["time_reduction_percent"] == 15.0

    @pytest.mark.unit
    def test_invention_bonuses_by_faction(self):
        """Should calculate invention bonuses per faction."""
        # Note: Skill names are Amarrian, Caldari (no suffix), Gallentean, Minmatar
        skills = {
            "Gallente Encryption Methods": 4,
            "Gallentean Starship Engineering": 4,
            "Caldari Encryption Methods": 3,
            "Caldari Starship Engineering": 3,  # Caldari (not "Caldariran")
        }

        summary = summarize_industry_capabilities(skills)

        bonuses = summary["invention_bonuses"]
        assert "Gallente" in bonuses
        assert "Caldari" in bonuses

        # Gallente: 4 + 4 = 8%
        assert bonuses["Gallente"]["encryption_level"] == 4
        assert bonuses["Gallente"]["starship_engineering_level"] == 4
        assert bonuses["Gallente"]["base_bonus_percent"] == 8

        # Caldari: 3 + 3 = 6%
        assert bonuses["Caldari"]["encryption_level"] == 3
        assert bonuses["Caldari"]["starship_engineering_level"] == 3
        assert bonuses["Caldari"]["base_bonus_percent"] == 6

    @pytest.mark.unit
    def test_includes_raw_skills(self):
        """Should include original skills in summary."""
        skills = {"Industry": 5, "Advanced Industry": 4}

        summary = summarize_industry_capabilities(skills)

        assert summary["skills"] == skills
