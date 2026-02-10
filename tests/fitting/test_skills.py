"""
Tests for Pilot Skill Integration.

Tests cover:
- fetch_pilot_skills() with mock ESI
- extract_skills_for_fit() skill extraction
- Skill level parameter verification
- Auth error handling
- Network error handling
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from aria_esi.fitting.skill_registry import (
    DRONE_SKILL_NAMES,
    FITTING_SKILL_NAMES,
    NAVIGATION_SKILL_NAMES,
    TANK_SKILL_NAMES,
    BONUS_DRONE_SKILL_NAMES,
    BONUS_CORE_SKILL_NAMES,
)
from aria_esi.fitting.skills import (
    SkillFetchError,
    extract_skills_for_fit,
    fetch_pilot_skills,
    get_all_v_skills,
    get_relevant_skills_for_fit,
)

# =============================================================================
# fetch_pilot_skills Tests
# =============================================================================


class TestFetchPilotSkills:
    """Tests for ESI skill fetching."""

    def test_fetch_skills_success(self, mock_credentials, mock_esi_skills_response):
        """Test successful skill fetch from ESI."""
        with patch("aria_esi.core.get_authenticated_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.get.return_value = mock_esi_skills_response
            mock_get_client.return_value = (mock_client, mock_credentials)

            result = fetch_pilot_skills()

            assert len(result) == 10
            assert result.source == "esi"
            assert result.skills[3332] == 5  # Gallente Cruiser
            assert result.skills[3436] == 5  # Drones
            assert result.skills[23606] == 3  # Drone Sharpshooting

    def test_fetch_skills_with_credentials(self, mock_credentials, mock_esi_skills_response):
        """Test fetch with explicit credentials."""
        with patch("aria_esi.core.ESIClient") as mock_esi_class:
            mock_client = MagicMock()
            mock_client.get.return_value = mock_esi_skills_response
            mock_esi_class.return_value = mock_client

            result = fetch_pilot_skills(creds=mock_credentials)

            mock_esi_class.assert_called_once_with(token=mock_credentials.access_token)
            assert len(result) == 10
            assert result.source == "esi"

    def test_fetch_skills_empty_response(self, mock_credentials, mock_empty_skills_response):
        """Test fetch with no skills."""
        with patch("aria_esi.core.get_authenticated_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.get.return_value = mock_empty_skills_response
            mock_get_client.return_value = (mock_client, mock_credentials)

            result = fetch_pilot_skills()

            assert result.skills == {}
            assert result.source == "esi"

    def test_fetch_skills_auth_error(self):
        """Test that auth errors raise SkillFetchError with is_auth_error=True."""
        from aria_esi.core import CredentialsError

        with patch("aria_esi.core.get_authenticated_client") as mock_get_client:
            mock_get_client.side_effect = CredentialsError("No credentials found")

            with pytest.raises(SkillFetchError) as exc_info:
                fetch_pilot_skills()

            assert exc_info.value.is_auth_error is True
            assert "No credentials found" in str(exc_info.value)

    def test_fetch_skills_esi_error(self, mock_credentials):
        """Test that ESI errors raise SkillFetchError."""
        from aria_esi.core import ESIError

        with patch("aria_esi.core.get_authenticated_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.get.side_effect = ESIError("ESI unavailable", 503)
            mock_get_client.return_value = (mock_client, mock_credentials)

            with pytest.raises(SkillFetchError) as exc_info:
                fetch_pilot_skills()

            assert exc_info.value.is_auth_error is False
            assert "ESI unavailable" in str(exc_info.value)

    def test_fetch_skills_invalid_response(self, mock_credentials):
        """Test that invalid response raises SkillFetchError."""
        with patch("aria_esi.core.get_authenticated_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.get.return_value = "not a dict"
            mock_get_client.return_value = (mock_client, mock_credentials)

            with pytest.raises(SkillFetchError) as exc_info:
                fetch_pilot_skills()

            assert "Invalid skills response" in str(exc_info.value)


# =============================================================================
# get_all_v_skills Tests
# =============================================================================


class TestGetAllVSkills:
    """Tests for all V skills mode."""

    def test_returns_none(self):
        """Test that all V mode returns None (indicating all skills at 5)."""
        result = get_all_v_skills()
        assert result is None


# =============================================================================
# get_relevant_skills_for_fit Tests
# =============================================================================


class TestGetRelevantSkillsForFit:
    """Tests for fit-type-specific skill lists."""

    def test_generic_includes_fitting_and_navigation(self, mock_skill_registry):
        """Test generic fit includes base skills."""
        skills = get_relevant_skills_for_fit("generic")

        # Should include fitting skills
        for name in FITTING_SKILL_NAMES:
            assert mock_skill_registry.id(name) in skills

        # Should include navigation skills
        for name in NAVIGATION_SKILL_NAMES:
            assert mock_skill_registry.id(name) in skills

    def test_drone_boat_includes_drone_skills(self, mock_skill_registry):
        """Test drone boat fit includes drone skills."""
        skills = get_relevant_skills_for_fit("drone_boat")

        for name in DRONE_SKILL_NAMES:
            assert mock_skill_registry.id(name) in skills

    def test_armor_tank_includes_tank_skills(self, mock_skill_registry):
        """Test armor tank fit includes tank skills."""
        skills = get_relevant_skills_for_fit("armor_tank")

        for name in TANK_SKILL_NAMES:
            assert mock_skill_registry.id(name) in skills

    def test_no_duplicates(self, mock_skill_registry):
        """Test that returned list has no duplicates."""
        skills = get_relevant_skills_for_fit("drone_boat")
        assert len(skills) == len(set(skills))

    def test_registry_none_returns_empty(self, monkeypatch):
        """Test that unavailable registry returns empty list."""
        monkeypatch.setattr(
            "aria_esi.fitting.skills.get_skill_registry", lambda: None
        )
        skills = get_relevant_skills_for_fit("generic")
        assert skills == []


# =============================================================================
# extract_skills_for_fit Tests
# =============================================================================


class TestExtractSkillsForFit:
    """Tests for dynamic skill extraction from fits."""

    def test_extract_ship_skills(self, vexor_parsed_fit, mock_skill_requirements_data, tmp_path):
        """Test that ship skills are extracted."""
        # Mock the skill requirements loading
        with patch("aria_esi.fitting.skills._load_skill_requirements") as mock_load:
            # Convert string keys to int for the mock
            requirements = {
                int(k): {int(sk): v for sk, v in skills.items()}
                for k, skills in mock_skill_requirements_data.items()
            }
            mock_load.return_value = requirements

            # Clear cached requirements
            import aria_esi.fitting.skills as skills_module

            skills_module._skill_requirements = None

            skills = extract_skills_for_fit(vexor_parsed_fit, level=5)

            # Should include Gallente Cruiser (required by Vexor)
            assert 3332 in skills
            assert skills[3332] == 5

    def test_extract_module_skills(self, vexor_parsed_fit, mock_skill_requirements_data):
        """Test that module skills are extracted."""
        with patch("aria_esi.fitting.skills._load_skill_requirements") as mock_load:
            requirements = {
                int(k): {int(sk): v for sk, v in skills.items()}
                for k, skills in mock_skill_requirements_data.items()
            }
            mock_load.return_value = requirements

            import aria_esi.fitting.skills as skills_module

            skills_module._skill_requirements = None

            skills = extract_skills_for_fit(vexor_parsed_fit, level=5)

            # Should include Drones (required by DDA II)
            assert 3436 in skills
            assert skills[3436] == 5

    def test_extract_drone_skills(self, vexor_parsed_fit, mock_skill_requirements_data):
        """Test that drone skills are extracted."""
        with patch("aria_esi.fitting.skills._load_skill_requirements") as mock_load:
            requirements = {
                int(k): {int(sk): v for sk, v in skills.items()}
                for k, skills in mock_skill_requirements_data.items()
            }
            mock_load.return_value = requirements

            import aria_esi.fitting.skills as skills_module

            skills_module._skill_requirements = None

            skills = extract_skills_for_fit(vexor_parsed_fit, level=5)

            # Should include Medium Drone Operation (required by Hammerhead II)
            assert 33699 in skills
            assert skills[33699] == 5

    def test_extract_bonus_skills_for_drones(
        self, vexor_parsed_fit, mock_skill_requirements_data, mock_skill_registry
    ):
        """Test that bonus skills are added for drone fits."""
        with patch("aria_esi.fitting.skills._load_skill_requirements") as mock_load:
            requirements = {
                int(k): {int(sk): v for sk, v in skills.items()}
                for k, skills in mock_skill_requirements_data.items()
            }
            mock_load.return_value = requirements

            import aria_esi.fitting.skills as skills_module

            skills_module._skill_requirements = None

            skills = extract_skills_for_fit(vexor_parsed_fit, level=5)

            # Should include Drone Interfacing (bonus skill for drone fits)
            assert mock_skill_registry.id("Drone Interfacing") in skills

    def test_extract_core_skills_always_added(
        self, minimal_fit, mock_skill_requirements_data, mock_skill_registry
    ):
        """Test that core skills are always added."""
        with patch("aria_esi.fitting.skills._load_skill_requirements") as mock_load:
            mock_load.return_value = {}

            import aria_esi.fitting.skills as skills_module

            skills_module._skill_requirements = None

            skills = extract_skills_for_fit(minimal_fit, level=5)

            # Should include core skills (resolved from SDE, not hardcoded)
            assert mock_skill_registry.id("Mechanics") in skills
            assert mock_skill_registry.id("Hull Upgrades") in skills
            assert mock_skill_registry.id("Navigation") in skills

    def test_extract_with_custom_level(self, minimal_fit, mock_skill_registry):
        """Test extraction with custom skill level."""
        with patch("aria_esi.fitting.skills._load_skill_requirements") as mock_load:
            mock_load.return_value = {}

            import aria_esi.fitting.skills as skills_module

            skills_module._skill_requirements = None

            skills = extract_skills_for_fit(minimal_fit, level=3)

            # All skills should be at level 3
            for skill_id, level in skills.items():
                assert level == 3

    def test_extract_resolves_prerequisites(self, vexor_parsed_fit, mock_skill_requirements_data):
        """Test that prerequisite skills are recursively resolved."""
        with patch("aria_esi.fitting.skills._load_skill_requirements") as mock_load:
            requirements = {
                int(k): {int(sk): v for sk, v in skills.items()}
                for k, skills in mock_skill_requirements_data.items()
            }
            mock_load.return_value = requirements

            import aria_esi.fitting.skills as skills_module

            skills_module._skill_requirements = None

            skills = extract_skills_for_fit(vexor_parsed_fit, level=5)

            # Gallente Cruiser requires Gallente Frigate, which requires Spaceship Command
            # Should have Spaceship Command (3327) from the prerequisite chain
            assert 3327 in skills

    def test_extract_no_duplicates(self, vexor_parsed_fit, mock_skill_requirements_data):
        """Test that extracted skills have no duplicates."""
        with patch("aria_esi.fitting.skills._load_skill_requirements") as mock_load:
            requirements = {
                int(k): {int(sk): v for sk, v in skills.items()}
                for k, skills in mock_skill_requirements_data.items()
            }
            mock_load.return_value = requirements

            import aria_esi.fitting.skills as skills_module

            skills_module._skill_requirements = None

            skills = extract_skills_for_fit(vexor_parsed_fit, level=5)

            # Skills dict naturally has no duplicate keys
            # Just verify we got a reasonable number
            assert len(skills) > 0


# =============================================================================
# Registry None Fallback Tests
# =============================================================================


class TestRegistryNoneFallback:
    """Tests for behavior when skill registry is unavailable."""

    def test_extract_skills_registry_none_skips_bonus(
        self, minimal_fit, monkeypatch
    ):
        """When registry is None, bonus injection is skipped; core extraction still works."""
        monkeypatch.setattr(
            "aria_esi.fitting.skills.get_skill_registry", lambda: None
        )
        with patch("aria_esi.fitting.skills._load_skill_requirements") as mock_load:
            mock_load.return_value = {}

            import aria_esi.fitting.skills as skills_module

            skills_module._skill_requirements = None

            skills = extract_skills_for_fit(minimal_fit, level=5)

            # No bonus skills should be injected — result should be empty
            # since there are no EOS-based requirements either
            assert skills == {}

    def test_extract_skills_bonus_core_includes_power_grid_management(
        self, minimal_fit, mock_skill_registry
    ):
        """Verify Power Grid Management is included in bonus core skills."""
        with patch("aria_esi.fitting.skills._load_skill_requirements") as mock_load:
            mock_load.return_value = {}

            import aria_esi.fitting.skills as skills_module

            skills_module._skill_requirements = None

            skills = extract_skills_for_fit(minimal_fit, level=5)

            assert mock_skill_registry.id("Power Grid Management") in skills

    def test_extract_skills_bonus_core_excludes_repair_systems(
        self, minimal_fit, mock_skill_registry
    ):
        """Verify Repair Systems is NOT in bonus core skills (bug fix from old swapped IDs)."""
        with patch("aria_esi.fitting.skills._load_skill_requirements") as mock_load:
            mock_load.return_value = {}

            import aria_esi.fitting.skills as skills_module

            skills_module._skill_requirements = None

            skills = extract_skills_for_fit(minimal_fit, level=5)

            # Repair Systems should NOT be in bonus core — it was only present
            # in old code due to swapped Hull Upgrades / Repair Systems IDs
            assert mock_skill_registry.id("Repair Systems") not in skills
