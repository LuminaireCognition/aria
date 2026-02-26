"""
Tests for YAML skill reference validation — Phase F.

Validates that the extractors and validation function correctly
identify skill names in YAML files and report missing names.
"""

from __future__ import annotations

import pytest

from aria_esi.mcp.sde.tools_easy80 import (
    YAML_SKILL_EXTRACTORS,
    _extract_skill_names_breakpoints,
    _extract_skill_names_efficacy,
    _extract_skill_names_meta_alternatives,
    validate_yaml_skill_references,
)


class TestExtractors:
    """Tests for YAML skill name extractors."""

    def test_extractor_efficacy_extracts_skill_names(self):
        data = {
            "ship_roles": {
                "drone_boat": {
                    "skills": [
                        {"skill": "Drones", "effect": "test", "per_level": 5},
                        {"skill": "Drone Interfacing", "effect": "test"},
                    ]
                }
            }
        }
        pairs = _extract_skill_names_efficacy(data)
        names = [name for _, name in pairs]
        assert "Drones" in names
        assert "Drone Interfacing" in names

    def test_extractor_breakpoints_extracts_skill_names(self):
        data = {
            "Drones": {"breakpoint_level": 5, "effect": "test"},
            "Advanced Weapon Upgrades": {"breakpoint_level": 5},
        }
        pairs = _extract_skill_names_breakpoints(data)
        names = [name for _, name in pairs]
        assert "Drones" in names
        assert "Advanced Weapon Upgrades" in names

    def test_extractor_meta_alternatives_extracts_skill_names(self):
        data = {
            "armor_repairers": {
                "Small Armor Repairer II": {
                    "requires_v": ["Mechanics"],
                    "meta_alternative": {"name": "test", "effectiveness": 89},
                }
            }
        }
        pairs = _extract_skill_names_meta_alternatives(data)
        names = [name for _, name in pairs]
        assert "Mechanics" in names

    def test_extractor_handles_none_yaml_data(self):
        assert _extract_skill_names_efficacy(None) == []
        assert _extract_skill_names_breakpoints(None) == []
        assert _extract_skill_names_meta_alternatives(None) == []

    def test_extractor_handles_empty_dict(self):
        assert _extract_skill_names_efficacy({}) == []
        assert _extract_skill_names_breakpoints({}) == []
        assert _extract_skill_names_meta_alternatives({}) == []

    def test_extractor_handles_malformed_data(self):
        """Extractors should handle unexpected types gracefully."""
        assert _extract_skill_names_efficacy({"ship_roles": "not_a_dict"}) == []
        assert _extract_skill_names_meta_alternatives({"cat": "not_a_dict"}) == []


class TestValidateYamlSkillReferences:
    """Tests for validate_yaml_skill_references()."""

    def test_yaml_validation_catches_typo(self, mock_sde_service):
        data = {"Drone Interferring": {"breakpoint_level": 5}}
        warnings = validate_yaml_skill_references(data, "test.yaml", "breakpoint_skills")
        assert len(warnings) == 1
        assert "Drone Interferring" in warnings[0]

    def test_yaml_validation_passes_for_valid_names(self, mock_sde_service):
        data = {"Drones": {"breakpoint_level": 5}, "Mechanics": {"breakpoint_level": 4}}
        warnings = validate_yaml_skill_references(data, "test.yaml", "breakpoint_skills")
        assert warnings == []

    def test_yaml_validation_returns_empty_when_sde_unavailable(self, monkeypatch):
        """Returns [] when SDE is unavailable."""

        def raise_no_sde():
            raise RuntimeError("no sde")

        # The function imports get_sde_query_service inside the try block
        # from aria_esi.store.sde.queries, so patch at that module level.
        monkeypatch.setattr(
            "aria_esi.store.sde.queries.get_sde_query_service",
            raise_no_sde,
        )
        data = {"FakeSkill": {"breakpoint_level": 5}}
        warnings = validate_yaml_skill_references(data, "test.yaml", "breakpoint_skills")
        assert warnings == []

    def test_yaml_validation_unknown_extractor_key(self, mock_sde_service):
        warnings = validate_yaml_skill_references({}, "test.yaml", "nonexistent_key")
        assert len(warnings) == 1
        assert "No skill extractor" in warnings[0]

    def test_yaml_validation_empty_yaml_data(self, mock_sde_service):
        warnings = validate_yaml_skill_references({}, "test.yaml", "breakpoint_skills")
        assert warnings == []

    def test_yaml_validation_with_skills_outside_all_skill_names(self, mock_sde_service):
        """YAML validation resolves skills not in ALL_SKILL_NAMES but in SDE category 16.

        The mock SDE only has ALL_SKILL_NAMES skills, so a skill outside that set
        should produce a warning (since it's not in the mock DB).
        """
        data = {"Surgical Strike": {"breakpoint_level": 5}}
        warnings = validate_yaml_skill_references(data, "test.yaml", "breakpoint_skills")
        # Surgical Strike is not in the mock DB, so it should warn
        assert len(warnings) == 1
        assert "Surgical Strike" in warnings[0]

    def test_yaml_extractors_registry_has_all_keys(self):
        assert "ship_efficacy_rules" in YAML_SKILL_EXTRACTORS
        assert "breakpoint_skills" in YAML_SKILL_EXTRACTORS
        assert "meta_module_alternatives" in YAML_SKILL_EXTRACTORS
