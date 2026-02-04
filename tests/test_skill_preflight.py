"""
Tests for ARIA skill preflight validation.

Tests the .claude/scripts/aria-skill-preflight.py script that validates
skill prerequisites before execution.
"""

import json
import sys
from pathlib import Path

import pytest

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parents[1] / ".claude" / "scripts"))

# Import the module under test
import importlib.util

spec = importlib.util.spec_from_file_location(
    "aria_skill_preflight",
    Path(__file__).parents[1] / ".claude" / "scripts" / "aria-skill-preflight.py",
)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


class TestExpandDataSource:
    """Tests for data source template expansion."""

    def test_expands_active_pilot_template(self) -> None:
        """Should expand {active_pilot} template variable."""
        source = "userdata/pilots/{active_pilot}/profile.md"
        result = preflight.expand_data_source(source, "12345_test_pilot")
        assert result == "userdata/pilots/12345_test_pilot/profile.md"

    def test_no_expansion_without_pilot_dir(self) -> None:
        """Should leave template unchanged when no pilot dir provided."""
        source = "userdata/pilots/{active_pilot}/profile.md"
        result = preflight.expand_data_source(source, None)
        assert result == source

    def test_no_template_unchanged(self) -> None:
        """Should leave paths without templates unchanged."""
        source = "reference/mechanics/drones.json"
        result = preflight.expand_data_source(source, "12345_test")
        assert result == source


class TestValidateSkill:
    """Tests for skill validation logic."""

    @pytest.fixture
    def project_root(self, tmp_path: Path) -> Path:
        """Create minimal project structure for testing."""
        # Create required directories
        (tmp_path / "userdata" / "pilots" / "12345_test").mkdir(parents=True)
        (tmp_path / "userdata" / "credentials").mkdir(parents=True)
        (tmp_path / "reference" / "mechanics").mkdir(parents=True)

        # Create config
        config = {"version": "2.0", "active_pilot": "12345"}
        (tmp_path / "userdata" / "config.json").write_text(json.dumps(config))

        # Create registry
        registry = {
            "pilots": [{"character_id": "12345", "directory": "12345_test"}]
        }
        (tmp_path / "userdata" / "pilots" / "_registry.json").write_text(
            json.dumps(registry)
        )

        # Create credentials with scopes
        creds = {
            "character_id": 12345,
            "access_token": "test",
            "scopes": ["esi-wallet.read_character_wallet.v1", "esi-clones.read_clones.v1"],
        }
        (tmp_path / "userdata" / "credentials" / "12345.json").write_text(
            json.dumps(creds)
        )

        # Create some data files
        (tmp_path / "userdata" / "pilots" / "12345_test" / "profile.md").write_text(
            "# Test Profile"
        )
        (tmp_path / "reference" / "mechanics" / "drones.json").write_text("{}")

        return tmp_path

    def test_skill_without_requirements_passes(self, project_root: Path) -> None:
        """Skill with no requirements should pass."""
        skill = {
            "name": "help",
            "requires_pilot": False,
            "data_sources": [],
            "esi_scopes": [],
        }
        result = preflight.validate_skill(project_root, skill, "12345", "12345_test", [])
        assert result["ok"] is True
        assert result["missing_pilot"] is False
        assert result["missing_sources"] == []
        assert result["missing_scopes"] == []

    def test_requires_pilot_fails_without_pilot(self, project_root: Path) -> None:
        """Skill requiring pilot should fail when no pilot active."""
        skill = {
            "name": "clones",
            "requires_pilot": True,
            "data_sources": [],
            "esi_scopes": [],
        }
        result = preflight.validate_skill(project_root, skill, None, None, [])
        assert result["ok"] is False
        assert result["missing_pilot"] is True

    def test_requires_pilot_passes_with_pilot(self, project_root: Path) -> None:
        """Skill requiring pilot should pass when pilot active."""
        skill = {
            "name": "clones",
            "requires_pilot": True,
            "data_sources": [],
            "esi_scopes": [],
        }
        result = preflight.validate_skill(project_root, skill, "12345", "12345_test", [])
        assert result["ok"] is True
        assert result["missing_pilot"] is False

    def test_missing_data_source_fails(self, project_root: Path) -> None:
        """Skill should fail when data source is missing."""
        skill = {
            "name": "test",
            "requires_pilot": False,
            "data_sources": ["reference/missing/file.md"],
            "esi_scopes": [],
        }
        result = preflight.validate_skill(project_root, skill, "12345", "12345_test", [])
        assert result["ok"] is False
        assert "reference/missing/file.md" in result["missing_sources"]

    def test_existing_data_source_passes(self, project_root: Path) -> None:
        """Skill should pass when data source exists."""
        skill = {
            "name": "test",
            "requires_pilot": False,
            "data_sources": ["reference/mechanics/drones.json"],
            "esi_scopes": [],
        }
        result = preflight.validate_skill(project_root, skill, "12345", "12345_test", [])
        assert result["ok"] is True
        assert result["missing_sources"] == []

    def test_pilot_data_source_expanded(self, project_root: Path) -> None:
        """Pilot-specific data source should be expanded and checked."""
        skill = {
            "name": "test",
            "requires_pilot": True,
            "data_sources": ["userdata/pilots/{active_pilot}/profile.md"],
            "esi_scopes": [],
        }
        result = preflight.validate_skill(project_root, skill, "12345", "12345_test", [])
        assert result["ok"] is True
        assert result["missing_sources"] == []

    def test_missing_scope_fails(self, project_root: Path) -> None:
        """Skill should fail when ESI scope is missing."""
        skill = {
            "name": "test",
            "requires_pilot": True,
            "data_sources": [],
            "esi_scopes": ["esi-mail.read_mail.v1"],
        }
        result = preflight.validate_skill(
            project_root, skill, "12345", "12345_test", ["esi-wallet.read_character_wallet.v1"]
        )
        assert result["ok"] is False
        assert "esi-mail.read_mail.v1" in result["missing_scopes"]

    def test_present_scope_passes(self, project_root: Path) -> None:
        """Skill should pass when ESI scope is present."""
        skill = {
            "name": "test",
            "requires_pilot": True,
            "data_sources": [],
            "esi_scopes": ["esi-wallet.read_character_wallet.v1"],
        }
        result = preflight.validate_skill(
            project_root, skill, "12345", "12345_test", ["esi-wallet.read_character_wallet.v1"]
        )
        assert result["ok"] is True
        assert result["missing_scopes"] == []

    def test_wildcard_sources_skipped(self, project_root: Path) -> None:
        """Wildcard data sources should be skipped (can't validate)."""
        skill = {
            "name": "test",
            "requires_pilot": False,
            "data_sources": ["reference/ships/fittings/*.md"],
            "esi_scopes": [],
        }
        result = preflight.validate_skill(project_root, skill, "12345", "12345_test", [])
        assert result["ok"] is True
        assert result["missing_sources"] == []

    def test_esi_scopes_as_string_handled(self, project_root: Path) -> None:
        """Handle esi_scopes stored as JSON string (edge case in some skills)."""
        skill = {
            "name": "test",
            "requires_pilot": False,
            "data_sources": [],
            "esi_scopes": "[]",  # String instead of list
        }
        result = preflight.validate_skill(project_root, skill, "12345", "12345_test", [])
        assert result["ok"] is True


class TestResolveActivePilot:
    """Tests for pilot resolution."""

    def test_resolves_from_config_and_registry(self, tmp_path: Path) -> None:
        """Should resolve pilot from config and registry."""
        # Setup
        (tmp_path / "userdata" / "pilots").mkdir(parents=True)
        config = {"active_pilot": "99999"}
        (tmp_path / "userdata" / "config.json").write_text(json.dumps(config))
        registry = {"pilots": [{"character_id": "99999", "directory": "99999_test_char"}]}
        (tmp_path / "userdata" / "pilots" / "_registry.json").write_text(
            json.dumps(registry)
        )

        char_id, directory = preflight.resolve_active_pilot(tmp_path)
        assert char_id == "99999"
        assert directory == "99999_test_char"

    def test_returns_none_without_config(self, tmp_path: Path) -> None:
        """Should return None when config doesn't exist."""
        char_id, directory = preflight.resolve_active_pilot(tmp_path)
        assert char_id is None
        assert directory is None

    def test_returns_none_without_registry_entry(self, tmp_path: Path) -> None:
        """Should return pilot ID but no directory when not in registry."""
        (tmp_path / "userdata" / "pilots").mkdir(parents=True)
        config = {"active_pilot": "99999"}
        (tmp_path / "userdata" / "config.json").write_text(json.dumps(config))
        registry = {"pilots": []}  # Empty registry
        (tmp_path / "userdata" / "pilots" / "_registry.json").write_text(
            json.dumps(registry)
        )

        char_id, directory = preflight.resolve_active_pilot(tmp_path)
        assert char_id == "99999"
        assert directory is None


class TestLoadPilotScopes:
    """Tests for scope loading from credentials."""

    def test_loads_scopes_from_credentials(self, tmp_path: Path) -> None:
        """Should load scopes from credentials file."""
        (tmp_path / "userdata" / "credentials").mkdir(parents=True)
        creds = {
            "character_id": 12345,
            "access_token": "test",
            "scopes": ["scope1", "scope2"],
        }
        (tmp_path / "userdata" / "credentials" / "12345.json").write_text(
            json.dumps(creds)
        )

        scopes = preflight.load_pilot_scopes(tmp_path, "12345")
        assert scopes == ["scope1", "scope2"]

    def test_returns_empty_without_credentials(self, tmp_path: Path) -> None:
        """Should return empty list when credentials don't exist."""
        scopes = preflight.load_pilot_scopes(tmp_path, "99999")
        assert scopes == []

    def test_returns_empty_without_scopes_field(self, tmp_path: Path) -> None:
        """Should return empty list when scopes field missing."""
        (tmp_path / "userdata" / "credentials").mkdir(parents=True)
        creds = {"character_id": 12345, "access_token": "test"}
        (tmp_path / "userdata" / "credentials" / "12345.json").write_text(
            json.dumps(creds)
        )

        scopes = preflight.load_pilot_scopes(tmp_path, "12345")
        assert scopes == []


class TestGetSkillByName:
    """Tests for skill lookup."""

    def test_finds_skill_by_name(self) -> None:
        """Should find skill by exact name match."""
        index = {
            "skills": [
                {"name": "help", "description": "Help skill"},
                {"name": "route", "description": "Route skill"},
            ]
        }
        skill = preflight.get_skill_by_name(index, "help")
        assert skill is not None
        assert skill["name"] == "help"

    def test_returns_none_for_missing_skill(self) -> None:
        """Should return None when skill not found."""
        index = {"skills": [{"name": "help"}]}
        skill = preflight.get_skill_by_name(index, "missing")
        assert skill is None
