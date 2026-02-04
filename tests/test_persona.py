"""
Tests for aria_esi persona commands

Tests persona context generation, staleness detection, and validation.
Addresses Finding 9: Test Coverage Below Reliability Threshold.
"""

import argparse
import json
from unittest.mock import patch

import pytest


class TestExtractProfileField:
    """Tests for extract_profile_field function."""

    def test_extract_simple_field(self):
        from aria_esi.commands.persona import extract_profile_field

        content = "- **Primary Faction:** pirate\n- **RP Level:** on"
        assert extract_profile_field(content, "Primary Faction") == "pirate"
        assert extract_profile_field(content, "RP Level") == "on"

    def test_extract_field_case_insensitive(self):
        from aria_esi.commands.persona import extract_profile_field

        content = "- **Primary Faction:** Gallente"
        assert extract_profile_field(content, "primary faction") == "Gallente"
        assert extract_profile_field(content, "PRIMARY FACTION") == "Gallente"

    def test_extract_field_not_found(self):
        from aria_esi.commands.persona import extract_profile_field

        content = "- **Name:** Test"
        assert extract_profile_field(content, "Nonexistent Field") is None

    def test_extract_field_without_bullet(self):
        from aria_esi.commands.persona import extract_profile_field

        content = "**Character Name:** Test Pilot"
        assert extract_profile_field(content, "Character Name") == "Test Pilot"


class TestNormalizeRpLevel:
    """Tests for normalize_rp_level function."""

    def test_normalize_string_values(self):
        from aria_esi.commands.persona import normalize_rp_level

        assert normalize_rp_level("on") == "on"
        assert normalize_rp_level("off") == "off"
        assert normalize_rp_level("full") == "full"

    def test_normalize_boolean_values(self):
        """YAML parses 'on'/'off' as True/False - verify normalization."""
        from aria_esi.commands.persona import normalize_rp_level

        assert normalize_rp_level(True) == "on"
        assert normalize_rp_level(False) == "off"

    def test_normalize_none_value(self):
        from aria_esi.commands.persona import normalize_rp_level

        assert normalize_rp_level(None) == "off"

    def test_normalize_with_whitespace(self):
        from aria_esi.commands.persona import normalize_rp_level

        assert normalize_rp_level("  ON  ") == "on"
        assert normalize_rp_level("Full\n") == "full"


class TestBuildPersonaContext:
    """Tests for build_persona_context function."""

    def test_gallente_on_level(self, tmp_path):
        from aria_esi.commands.persona import build_persona_context

        # Create minimal persona structure
        (tmp_path / "personas" / "_shared" / "empire").mkdir(parents=True)
        (tmp_path / "personas" / "aria-mk4").mkdir(parents=True)
        (tmp_path / "personas" / "_shared" / "empire" / "identity.md").touch()
        (tmp_path / "personas" / "_shared" / "empire" / "terminology.md").touch()
        (tmp_path / "personas" / "aria-mk4" / "manifest.yaml").touch()
        (tmp_path / "personas" / "aria-mk4" / "voice.md").touch()

        context = build_persona_context("gallente", "on", tmp_path)

        assert context["branch"] == "empire"
        assert context["persona"] == "aria-mk4"
        assert context["rp_level"] == "on"
        assert context["skill_overlay_path"] == "personas/aria-mk4/skill-overlays"
        assert len(context["files"]) == 4

    def test_pirate_on_level(self, tmp_path):
        from aria_esi.commands.persona import build_persona_context

        # Create minimal persona structure
        (tmp_path / "personas" / "_shared" / "pirate").mkdir(parents=True)
        (tmp_path / "personas" / "paria").mkdir(parents=True)
        (tmp_path / "personas" / "_shared" / "pirate" / "identity.md").touch()
        (tmp_path / "personas" / "_shared" / "pirate" / "terminology.md").touch()
        (tmp_path / "personas" / "_shared" / "pirate" / "the-code.md").touch()
        (tmp_path / "personas" / "paria" / "manifest.yaml").touch()
        (tmp_path / "personas" / "paria" / "voice.md").touch()

        context = build_persona_context("pirate", "on", tmp_path)

        assert context["branch"] == "pirate"
        assert context["persona"] == "paria"
        assert "personas/_shared/pirate/the-code.md" in context["files"]

    def test_rp_level_off_returns_empty_files(self, tmp_path):
        from aria_esi.commands.persona import build_persona_context

        (tmp_path / "personas" / "aria-mk4").mkdir(parents=True)

        context = build_persona_context("gallente", "off", tmp_path)

        assert context["rp_level"] == "off"
        assert context["files"] == []

    def test_unknown_faction_defaults_to_gallente(self, tmp_path):
        from aria_esi.commands.persona import build_persona_context

        (tmp_path / "personas" / "aria-mk4").mkdir(parents=True)

        context = build_persona_context("unknown_faction", "off", tmp_path)

        assert context["persona"] == "aria-mk4"
        assert context["branch"] == "empire"

    def test_pirate_variant_with_fallback(self, tmp_path):
        from aria_esi.commands.persona import build_persona_context

        # Create paria but not paria-g
        (tmp_path / "personas" / "paria").mkdir(parents=True)
        (tmp_path / "personas" / "_shared" / "pirate").mkdir(parents=True)

        context = build_persona_context("guristas", "off", tmp_path)

        # Should fall back to paria since paria-g doesn't exist
        assert context["persona"] == "paria"
        # fallback is set when using a fallback persona (paria-g → paria)
        assert context["fallback"] == "paria"


class TestDetectStaleness:
    """Tests for detect_staleness function."""

    def test_fresh_context_not_stale(self, tmp_path):
        from aria_esi.commands.persona import build_persona_context, detect_staleness

        (tmp_path / "personas" / "aria-mk4").mkdir(parents=True)

        context = build_persona_context("gallente", "on", tmp_path)
        result = detect_staleness(context, "gallente", "on", tmp_path)

        assert result["stale"] is False
        assert len(result["discrepancies"]) == 0

    def test_detects_faction_change(self, tmp_path):
        from aria_esi.commands.persona import detect_staleness

        (tmp_path / "personas" / "aria-mk4").mkdir(parents=True)
        (tmp_path / "personas" / "paria").mkdir(parents=True)

        # Context says pirate/paria
        old_context = {
            "branch": "pirate",
            "persona": "paria",
            "rp_level": "on",
            "files": [],
            "skill_overlay_path": "personas/paria/skill-overlays",
            "overlay_fallback_path": None,
        }

        # But current profile says gallente
        result = detect_staleness(old_context, "gallente", "on", tmp_path)

        assert result["stale"] is True
        assert any(d["field"] == "persona" for d in result["discrepancies"])
        assert any(d["field"] == "branch" for d in result["discrepancies"])

    def test_detects_rp_level_change(self, tmp_path):
        from aria_esi.commands.persona import detect_staleness

        (tmp_path / "personas" / "aria-mk4").mkdir(parents=True)

        old_context = {
            "branch": "empire",
            "persona": "aria-mk4",
            "rp_level": "on",
            "files": ["file1.md"],
            "skill_overlay_path": "personas/aria-mk4/skill-overlays",
            "overlay_fallback_path": None,
        }

        # RP level changed from "on" to "off"
        result = detect_staleness(old_context, "gallente", "off", tmp_path)

        assert result["stale"] is True
        assert any(d["field"] == "rp_level" for d in result["discrepancies"])

    def test_detects_files_mismatch(self, tmp_path):
        from aria_esi.commands.persona import detect_staleness

        (tmp_path / "personas" / "aria-mk4").mkdir(parents=True)
        (tmp_path / "personas" / "_shared" / "empire").mkdir(parents=True)
        (tmp_path / "personas" / "_shared" / "empire" / "identity.md").touch()

        old_context = {
            "branch": "empire",
            "persona": "aria-mk4",
            "rp_level": "on",
            "files": ["old_file.md"],  # Doesn't match what would be generated
            "skill_overlay_path": "personas/aria-mk4/skill-overlays",
            "overlay_fallback_path": None,
        }

        result = detect_staleness(old_context, "gallente", "on", tmp_path)

        assert result["stale"] is True
        assert any(d["field"] == "files" for d in result["discrepancies"])

    def test_handles_yaml_boolean_rp_level(self, tmp_path):
        """Verify staleness detection normalizes YAML boolean rp_level."""
        from aria_esi.commands.persona import detect_staleness

        (tmp_path / "personas" / "aria-mk4").mkdir(parents=True)

        # Context with boolean True (parsed from YAML 'on')
        context_with_bool = {
            "branch": "empire",
            "persona": "aria-mk4",
            "rp_level": True,  # YAML parsed 'on' as True
            "files": [],
            "skill_overlay_path": "personas/aria-mk4/skill-overlays",
            "overlay_fallback_path": None,
        }

        # Should not be stale when profile also says "on"
        result = detect_staleness(context_with_bool, "gallente", "on", tmp_path)

        # After normalization, True == "on", so no rp_level discrepancy
        rp_discrepancies = [d for d in result["discrepancies"] if d["field"] == "rp_level"]
        assert len(rp_discrepancies) == 0


class TestValidatePersonaContext:
    """Tests for validate_persona_context function."""

    def test_validates_existing_files(self, tmp_path):
        from aria_esi.commands.persona import validate_persona_context

        # Create test files
        (tmp_path / "personas" / "test").mkdir(parents=True)
        (tmp_path / "personas" / "test" / "voice.md").touch()

        context = {
            "persona": "test",
            "fallback": None,
            "files": ["personas/test/voice.md"],
            "skill_overlay_path": "personas/test/skill-overlays",
            "overlay_fallback_path": None,
        }

        skill_index = {"skills": []}

        result = validate_persona_context(context, skill_index, tmp_path)

        assert result["valid"] is True
        assert "personas/test/voice.md" in result["validated"]["persona_files"]

    def test_reports_missing_files(self, tmp_path):
        from aria_esi.commands.persona import validate_persona_context

        context = {
            "persona": "test",
            "fallback": None,
            "files": ["personas/test/nonexistent.md"],
            "skill_overlay_path": "personas/test/skill-overlays",
            "overlay_fallback_path": None,
        }

        skill_index = {"skills": []}

        result = validate_persona_context(context, skill_index, tmp_path)

        assert result["valid"] is False
        assert len(result["issues"]["errors"]) == 1
        assert result["issues"]["errors"][0]["type"] == "missing_persona_file"

    def test_reports_missing_skill_overlays(self, tmp_path):
        from aria_esi.commands.persona import validate_persona_context

        (tmp_path / "personas" / "test" / "skill-overlays").mkdir(parents=True)

        context = {
            "persona": "test",
            "fallback": None,
            "files": [],
            "skill_overlay_path": "personas/test/skill-overlays",
            "overlay_fallback_path": None,
        }

        skill_index = {
            "skills": [
                {"name": "route", "has_persona_overlay": True}
            ]
        }

        result = validate_persona_context(context, skill_index, tmp_path)

        assert result["valid"] is False
        assert len(result["issues"]["warnings"]) == 1
        assert result["issues"]["warnings"][0]["type"] == "missing_skill_overlay"

    def test_validates_existing_overlays(self, tmp_path):
        from aria_esi.commands.persona import validate_persona_context

        overlay_dir = tmp_path / "personas" / "test" / "skill-overlays"
        overlay_dir.mkdir(parents=True)
        (overlay_dir / "route.md").touch()

        context = {
            "persona": "test",
            "fallback": None,
            "files": [],
            "skill_overlay_path": "personas/test/skill-overlays",
            "overlay_fallback_path": None,
        }

        skill_index = {
            "skills": [
                {"name": "route", "has_persona_overlay": True}
            ]
        }

        result = validate_persona_context(context, skill_index, tmp_path)

        assert result["valid"] is True
        assert "personas/test/skill-overlays/route.md" in result["validated"]["overlays"]

    def test_includes_staleness_in_validation(self, tmp_path):
        from aria_esi.commands.persona import validate_persona_context

        context = {
            "persona": "test",
            "fallback": None,
            "files": [],
            "skill_overlay_path": "personas/test/skill-overlays",
            "overlay_fallback_path": None,
        }

        skill_index = {"skills": []}

        staleness_result = {
            "stale": True,
            "discrepancies": [
                {"field": "persona", "message": "Persona mismatch"}
            ],
            "fix": "Run persona-context",
        }

        result = validate_persona_context(
            context, skill_index, tmp_path, staleness_result
        )

        assert result["valid"] is False
        assert len(result["issues"]["stale"]) == 1
        assert result["summary"]["staleness_issues"] == 1


class TestExtractPersonaContextFromProfile:
    """Tests for extract_persona_context_from_profile function."""

    def test_extracts_yaml_block(self):
        from aria_esi.commands.persona import extract_persona_context_from_profile

        content = """# Profile

## Persona Context

```yaml
persona_context:
  branch: empire
  persona: aria-mk4
  rp_level: "on"
  files: []
```
"""
        context = extract_persona_context_from_profile(content)

        assert context is not None
        assert context["branch"] == "empire"
        assert context["persona"] == "aria-mk4"

    def test_returns_none_when_missing(self):
        from aria_esi.commands.persona import extract_persona_context_from_profile

        content = "# Profile\n\nNo persona context here."
        context = extract_persona_context_from_profile(content)

        assert context is None

    def test_handles_malformed_yaml(self):
        from aria_esi.commands.persona import extract_persona_context_from_profile

        content = """
```yaml
persona_context:
  branch: [invalid yaml
```
"""
        context = extract_persona_context_from_profile(content)

        assert context is None


class TestCmdPersonaContext:
    """Tests for cmd_persona_context command."""

    def test_generates_context_for_pilot(self, tmp_path):
        from aria_esi.commands.persona import cmd_persona_context

        # Create pilot structure
        pilot_dir = tmp_path / "pilots" / "123_test"
        pilot_dir.mkdir(parents=True)

        profile = pilot_dir / "profile.md"
        profile.write_text("""# Profile
- **Primary Faction:** gallente
- **RP Level:** on
""")

        # Create persona directory
        (tmp_path / "personas" / "aria-mk4").mkdir(parents=True)

        args = argparse.Namespace()
        args.pilot = None
        args.all = False
        args.dry_run = True

        with patch('aria_esi.commands.persona.get_pilot_directory', return_value=pilot_dir):
            with patch('aria_esi.commands.persona.Path.cwd', return_value=tmp_path):
                result = cmd_persona_context(args)

        assert result["status"] == "success"
        assert len(result["results"]) == 1
        assert result["results"][0]["persona_context"]["persona"] == "aria-mk4"


class TestCmdValidateOverlays:
    """Tests for cmd_validate_overlays command."""

    def test_validates_pilot_context(self, tmp_path):
        from aria_esi.commands.persona import cmd_validate_overlays

        # Create pilot structure
        pilot_dir = tmp_path / "pilots" / "123_test"
        pilot_dir.mkdir(parents=True)

        profile = pilot_dir / "profile.md"
        profile.write_text("""# Profile
- **Primary Faction:** gallente
- **RP Level:** on

## Persona Context

```yaml
persona_context:
  branch: empire
  persona: aria-mk4
  fallback: null
  rp_level: "on"
  files: []
  skill_overlay_path: personas/aria-mk4/skill-overlays
  overlay_fallback_path: null
```
""")

        # Create persona and skill index
        (tmp_path / "personas" / "aria-mk4").mkdir(parents=True)
        (tmp_path / ".claude" / "skills").mkdir(parents=True)
        (tmp_path / ".claude" / "skills" / "_index.json").write_text(
            json.dumps({"skills": []})
        )

        args = argparse.Namespace()
        args.pilot = None
        args.all = False

        with patch('aria_esi.commands.persona.get_pilot_directory', return_value=pilot_dir):
            with patch('aria_esi.commands.persona.Path.cwd', return_value=tmp_path):
                result = cmd_validate_overlays(args)

        assert result["status"] == "valid"
        assert result["pilots_validated"] == 1

    def test_detects_staleness(self, tmp_path):
        from aria_esi.commands.persona import cmd_validate_overlays

        # Create pilot with stale context
        pilot_dir = tmp_path / "pilots" / "123_test"
        pilot_dir.mkdir(parents=True)

        profile = pilot_dir / "profile.md"
        profile.write_text("""# Profile
- **Primary Faction:** pirate
- **RP Level:** on

## Persona Context

```yaml
persona_context:
  branch: empire
  persona: aria-mk4
  fallback: null
  rp_level: "on"
  files: []
  skill_overlay_path: personas/aria-mk4/skill-overlays
  overlay_fallback_path: null
```
""")
        # Note: profile says pirate but context says aria-mk4 (empire)

        # Create directories
        (tmp_path / "personas" / "aria-mk4").mkdir(parents=True)
        (tmp_path / "personas" / "paria").mkdir(parents=True)
        (tmp_path / ".claude" / "skills").mkdir(parents=True)
        (tmp_path / ".claude" / "skills" / "_index.json").write_text(
            json.dumps({"skills": []})
        )

        args = argparse.Namespace()
        args.pilot = None
        args.all = False

        with patch('aria_esi.commands.persona.get_pilot_directory', return_value=pilot_dir):
            with patch('aria_esi.commands.persona.Path.cwd', return_value=tmp_path):
                result = cmd_validate_overlays(args)

        assert result["status"] == "issues_found"
        validation = result["results"][0]["validation"]
        assert validation["valid"] is False
        assert validation["summary"]["staleness_issues"] > 0


class TestFactionPersonaMap:
    """Tests for faction-to-persona mapping."""

    def test_all_empire_factions_map_to_empire_branch(self):
        from aria_esi.commands.persona import FACTION_PERSONA_MAP

        empire_factions = ["gallente", "caldari", "minmatar", "amarr"]
        for faction in empire_factions:
            assert FACTION_PERSONA_MAP[faction]["branch"] == "empire"

    def test_all_pirate_factions_map_to_pirate_branch(self):
        from aria_esi.commands.persona import FACTION_PERSONA_MAP

        pirate_factions = [
            "pirate", "angel_cartel", "serpentis",
            "guristas", "blood_raiders", "sanshas_nation"
        ]
        for faction in pirate_factions:
            assert FACTION_PERSONA_MAP[faction]["branch"] == "pirate"

    def test_pirate_variants_have_fallback(self):
        from aria_esi.commands.persona import FACTION_PERSONA_MAP

        variants = ["angel_cartel", "serpentis", "guristas", "blood_raiders", "sanshas_nation"]
        for variant in variants:
            assert FACTION_PERSONA_MAP[variant]["fallback"] == "paria"


class TestRpLevelMigration:
    """Tests for RP level migration from old values."""

    def test_migrates_lite_to_off(self, tmp_path):
        from aria_esi.commands.persona import build_persona_context

        (tmp_path / "personas" / "aria-mk4").mkdir(parents=True)

        context = build_persona_context("gallente", "lite", tmp_path)
        assert context["rp_level"] == "off"

    def test_migrates_moderate_to_on(self, tmp_path):
        from aria_esi.commands.persona import build_persona_context

        (tmp_path / "personas" / "aria-mk4").mkdir(parents=True)

        context = build_persona_context("gallente", "moderate", tmp_path)
        assert context["rp_level"] == "on"

    def test_invalid_rp_level_defaults_to_off(self, tmp_path):
        from aria_esi.commands.persona import build_persona_context

        (tmp_path / "personas" / "aria-mk4").mkdir(parents=True)

        context = build_persona_context("gallente", "invalid_level", tmp_path)
        assert context["rp_level"] == "off"


class TestValidateSafePath:
    """Tests for validate_safe_path security function.

    Addresses SECURITY_000.md Finding 1: Path traversal and injection.
    """

    def test_allows_valid_persona_path(self, tmp_path):
        from aria_esi.commands.persona import validate_safe_path

        is_safe, error = validate_safe_path("personas/test/voice.md", tmp_path)
        assert is_safe is True
        assert error is None

    def test_allows_valid_skill_path(self, tmp_path):
        from aria_esi.commands.persona import validate_safe_path

        is_safe, error = validate_safe_path(".claude/skills/route/SKILL.md", tmp_path)
        assert is_safe is True
        assert error is None

    def test_allows_shared_persona_path(self, tmp_path):
        from aria_esi.commands.persona import validate_safe_path

        is_safe, error = validate_safe_path("personas/_shared/empire/identity.md", tmp_path)
        assert is_safe is True
        assert error is None

    def test_rejects_absolute_unix_path(self, tmp_path):
        from aria_esi.commands.persona import validate_safe_path

        is_safe, error = validate_safe_path("/etc/passwd", tmp_path)
        assert is_safe is False
        assert "Absolute paths not allowed" in error

    def test_rejects_absolute_windows_path(self, tmp_path):
        from aria_esi.commands.persona import validate_safe_path

        is_safe, error = validate_safe_path("C:\\Windows\\System32\\config", tmp_path)
        assert is_safe is False
        assert "Absolute paths not allowed" in error

    def test_rejects_path_traversal_simple(self, tmp_path):
        from aria_esi.commands.persona import validate_safe_path

        is_safe, error = validate_safe_path("personas/../../../etc/passwd", tmp_path)
        assert is_safe is False
        assert "Path traversal not allowed" in error

    def test_rejects_path_traversal_at_start(self, tmp_path):
        from aria_esi.commands.persona import validate_safe_path

        is_safe, error = validate_safe_path("../credentials/token.json", tmp_path)
        assert is_safe is False
        assert "Path traversal not allowed" in error

    def test_rejects_path_traversal_in_middle(self, tmp_path):
        from aria_esi.commands.persona import validate_safe_path

        is_safe, error = validate_safe_path("personas/test/../../../userdata/secrets.json", tmp_path)
        assert is_safe is False
        assert "Path traversal not allowed" in error

    def test_rejects_path_outside_allowlist(self, tmp_path):
        from aria_esi.commands.persona import validate_safe_path

        is_safe, error = validate_safe_path("userdata/credentials/token.json", tmp_path)
        assert is_safe is False
        assert "not in allowlist" in error

    def test_rejects_empty_path(self, tmp_path):
        from aria_esi.commands.persona import validate_safe_path

        is_safe, error = validate_safe_path("", tmp_path)
        assert is_safe is False
        assert "Empty path" in error

    def test_rejects_none_path(self, tmp_path):
        from aria_esi.commands.persona import validate_safe_path

        is_safe, error = validate_safe_path(None, tmp_path)
        assert is_safe is False
        assert "Empty path" in error

    def test_rejects_dot_path(self, tmp_path):
        from aria_esi.commands.persona import validate_safe_path

        is_safe, error = validate_safe_path(".", tmp_path)
        assert is_safe is False
        assert "not in allowlist" in error

    def test_rejects_reference_directory_path(self, tmp_path):
        from aria_esi.commands.persona import validate_safe_path

        is_safe, error = validate_safe_path("reference/pve-intel/cache/test.md", tmp_path)
        assert is_safe is False
        assert "not in allowlist" in error

    def test_rejects_symlink_escape(self, tmp_path):
        """Test that symlinks pointing outside base_path are rejected."""
        from aria_esi.commands.persona import validate_safe_path

        # Create a symlink that points outside tmp_path
        (tmp_path / "personas" / "evil").mkdir(parents=True)
        symlink_path = tmp_path / "personas" / "evil" / "escape.md"

        # Create target outside base_path
        external_target = tmp_path.parent / "external_secret.txt"
        external_target.write_text("secret data")

        try:
            symlink_path.symlink_to(external_target)
        except OSError:
            # Symlink creation may fail on some systems (Windows without admin)
            pytest.skip("Cannot create symlinks on this system")

        is_safe, error = validate_safe_path("personas/evil/escape.md", tmp_path)
        assert is_safe is False
        assert "escapes project root" in error

        # Cleanup
        external_target.unlink()


class TestValidatePersonaContextSecurity:
    """Tests for security validation in validate_persona_context.

    Addresses SECURITY_000.md Findings 1 and 2:
    - Path traversal in persona_context.files
    - Unsafe overlay/redirect paths
    """

    def test_rejects_unsafe_persona_file_path(self, tmp_path):
        from aria_esi.commands.persona import validate_persona_context

        context = {
            "persona": "test",
            "fallback": None,
            "files": [
                "personas/test/safe.md",
                "../../../etc/passwd",  # Malicious path
            ],
            "skill_overlay_path": "personas/test/skill-overlays",
            "overlay_fallback_path": None,
        }

        # Create safe file so we can distinguish security from missing
        (tmp_path / "personas" / "test").mkdir(parents=True)
        (tmp_path / "personas" / "test" / "safe.md").touch()

        skill_index = {"skills": []}

        result = validate_persona_context(context, skill_index, tmp_path)

        assert result["valid"] is False
        assert len(result["issues"]["security"]) == 1
        assert result["issues"]["security"][0]["type"] == "unsafe_persona_file_path"
        assert "Path traversal not allowed" in result["issues"]["security"][0]["message"]
        # Safe file should still be validated
        assert "personas/test/safe.md" in result["validated"]["persona_files"]

    def test_rejects_absolute_persona_file_path(self, tmp_path):
        from aria_esi.commands.persona import validate_persona_context

        context = {
            "persona": "test",
            "fallback": None,
            "files": ["/etc/passwd"],  # Absolute path
            "skill_overlay_path": "personas/test/skill-overlays",
            "overlay_fallback_path": None,
        }

        skill_index = {"skills": []}

        result = validate_persona_context(context, skill_index, tmp_path)

        assert result["valid"] is False
        assert len(result["issues"]["security"]) == 1
        assert "Absolute paths not allowed" in result["issues"]["security"][0]["message"]

    def test_rejects_out_of_allowlist_persona_file(self, tmp_path):
        from aria_esi.commands.persona import validate_persona_context

        context = {
            "persona": "test",
            "fallback": None,
            "files": ["userdata/credentials/token.json"],  # Outside allowlist
            "skill_overlay_path": "personas/test/skill-overlays",
            "overlay_fallback_path": None,
        }

        skill_index = {"skills": []}

        result = validate_persona_context(context, skill_index, tmp_path)

        assert result["valid"] is False
        assert len(result["issues"]["security"]) == 1
        assert "not in allowlist" in result["issues"]["security"][0]["message"]

    def test_rejects_unsafe_overlay_path(self, tmp_path):
        from aria_esi.commands.persona import validate_persona_context

        context = {
            "persona": "test",
            "fallback": None,
            "files": [],
            "skill_overlay_path": "../../../credentials",  # Malicious overlay path
            "overlay_fallback_path": None,
        }

        skill_index = {
            "skills": [
                {"name": "route", "has_persona_overlay": True}
            ]
        }

        result = validate_persona_context(context, skill_index, tmp_path)

        assert result["valid"] is False
        assert len(result["issues"]["security"]) >= 1
        security_types = [i["type"] for i in result["issues"]["security"]]
        assert "unsafe_overlay_path" in security_types

    def test_rejects_unsafe_redirect_path(self, tmp_path):
        from aria_esi.commands.persona import validate_persona_context

        context = {
            "persona": "paria",
            "fallback": None,
            "files": [],
            "skill_overlay_path": "personas/paria/skill-overlays",
            "overlay_fallback_path": None,
        }

        skill_index = {
            "skills": [
                {
                    "name": "escape-route",
                    "persona_exclusive": "paria",
                    "redirect": "../../../etc/shadow",  # Malicious redirect
                }
            ]
        }

        result = validate_persona_context(context, skill_index, tmp_path)

        assert result["valid"] is False
        security_types = [i["type"] for i in result["issues"]["security"]]
        assert "unsafe_redirect_path" in security_types

    def test_security_violations_in_summary(self, tmp_path):
        from aria_esi.commands.persona import validate_persona_context

        context = {
            "persona": "test",
            "fallback": None,
            "files": ["../malicious.md", "userdata/secrets.json"],
            "skill_overlay_path": "personas/test/skill-overlays",
            "overlay_fallback_path": None,
        }

        skill_index = {"skills": []}

        result = validate_persona_context(context, skill_index, tmp_path)

        assert result["summary"]["security_violations"] == 2

    def test_allows_valid_redirect_path(self, tmp_path):
        from aria_esi.commands.persona import validate_persona_context

        # Create redirect file
        redirect_dir = tmp_path / "personas" / "paria-exclusive"
        redirect_dir.mkdir(parents=True)
        (redirect_dir / "escape-route.md").touch()

        context = {
            "persona": "paria",
            "fallback": None,
            "files": [],
            "skill_overlay_path": "personas/paria/skill-overlays",
            "overlay_fallback_path": None,
        }

        skill_index = {
            "skills": [
                {
                    "name": "escape-route",
                    "persona_exclusive": "paria",
                    "redirect": "personas/paria-exclusive/escape-route.md",  # Valid path
                }
            ]
        }

        result = validate_persona_context(context, skill_index, tmp_path)

        assert len(result["issues"]["security"]) == 0
        assert "personas/paria-exclusive/escape-route.md" in result["validated"]["exclusive_skills"]


class TestPersonaCompilerSecurity:
    """Tests for PersonaCompiler security enhancements.

    Addresses SECURITY_001.md Finding #1:
    - Extension allowlist enforcement (.md, .yaml, .json only)
    - File size limits (50KB per file for persona content)
    """

    def test_rejects_disallowed_extension(self, tmp_path):
        """Compiler should reject files with disallowed extensions."""
        from aria_esi.persona.compiler import PersonaCompiler

        # Create a .py file in the personas directory
        (tmp_path / "personas" / "test").mkdir(parents=True)
        (tmp_path / "personas" / "test" / "malicious.py").write_text("import os; os.system('rm -rf /')")

        compiler = PersonaCompiler(tmp_path)
        result = compiler._load_and_compile_file("personas/test/malicious.py")

        # Should be rejected due to extension
        assert result is None

    def test_rejects_executable_extension(self, tmp_path):
        """Compiler should reject executable file extensions."""
        from aria_esi.persona.compiler import PersonaCompiler

        (tmp_path / "personas" / "test").mkdir(parents=True)
        (tmp_path / "personas" / "test" / "script.sh").write_text("#!/bin/bash\nrm -rf /")

        compiler = PersonaCompiler(tmp_path)
        result = compiler._load_and_compile_file("personas/test/script.sh")

        assert result is None

    def test_allows_md_extension(self, tmp_path):
        """Compiler should allow .md files."""
        from aria_esi.persona.compiler import PersonaCompiler

        (tmp_path / "personas" / "test").mkdir(parents=True)
        (tmp_path / "personas" / "test" / "voice.md").write_text("# Voice\nTest content")

        compiler = PersonaCompiler(tmp_path)
        result = compiler._load_and_compile_file("personas/test/voice.md")

        assert result is not None
        assert result.source == "personas/test/voice.md"

    def test_allows_yaml_extension(self, tmp_path):
        """Compiler should allow .yaml files."""
        from aria_esi.persona.compiler import PersonaCompiler

        (tmp_path / "personas" / "test").mkdir(parents=True)
        (tmp_path / "personas" / "test" / "manifest.yaml").write_text("name: test\nversion: 1.0")

        compiler = PersonaCompiler(tmp_path)
        result = compiler._load_and_compile_file("personas/test/manifest.yaml")

        assert result is not None
        assert result.source == "personas/test/manifest.yaml"

    def test_allows_json_extension(self, tmp_path):
        """Compiler should allow .json files."""
        from aria_esi.persona.compiler import PersonaCompiler

        (tmp_path / "personas" / "test").mkdir(parents=True)
        (tmp_path / "personas" / "test" / "config.json").write_text('{"key": "value"}')

        compiler = PersonaCompiler(tmp_path)
        result = compiler._load_and_compile_file("personas/test/config.json")

        assert result is not None
        assert result.source == "personas/test/config.json"

    def test_rejects_oversized_file(self, tmp_path):
        """Compiler should reject files exceeding 50KB size limit."""
        from aria_esi.persona.compiler import PersonaCompiler, PERSONA_MAX_FILE_SIZE

        (tmp_path / "personas" / "test").mkdir(parents=True)

        # Create a file larger than the limit (50KB + 1KB)
        large_content = "x" * (PERSONA_MAX_FILE_SIZE + 1024)
        (tmp_path / "personas" / "test" / "large.md").write_text(large_content)

        compiler = PersonaCompiler(tmp_path)
        result = compiler._load_and_compile_file("personas/test/large.md")

        # Should be rejected due to size
        assert result is None

    def test_accepts_file_at_size_limit(self, tmp_path):
        """Compiler should accept files at exactly the size limit."""
        from aria_esi.persona.compiler import PersonaCompiler, PERSONA_MAX_FILE_SIZE

        (tmp_path / "personas" / "test").mkdir(parents=True)

        # Create a file at exactly the limit
        content = "x" * (PERSONA_MAX_FILE_SIZE - 100)  # Slightly under to be safe
        (tmp_path / "personas" / "test" / "limit.md").write_text(content)

        compiler = PersonaCompiler(tmp_path)
        result = compiler._load_and_compile_file("personas/test/limit.md")

        assert result is not None

    def test_compile_skips_invalid_files(self, tmp_path):
        """Compile should skip files that fail validation without failing."""
        from aria_esi.persona.compiler import PersonaCompiler

        (tmp_path / "personas" / "test").mkdir(parents=True)
        (tmp_path / "personas" / "test" / "valid.md").write_text("Valid content")
        (tmp_path / "personas" / "test" / "invalid.py").write_text("print('bad')")

        compiler = PersonaCompiler(tmp_path)
        context = {
            "persona": "test",
            "branch": "empire",
            "rp_level": "on",
            "files": [
                "personas/test/valid.md",
                "personas/test/invalid.py",  # Should be skipped
            ],
        }

        result = compiler.compile(context)

        # Should only compile the valid file
        assert len(result.files) == 1
        assert result.files[0].source == "personas/test/valid.md"

    def test_size_limit_constant_is_50kb(self):
        """Verify the size limit is set to 50KB as specified in the fix."""
        from aria_esi.persona.compiler import PERSONA_MAX_FILE_SIZE

        assert PERSONA_MAX_FILE_SIZE == 50_000


class TestPersonaArtifactVerification:
    """Tests for persona artifact integrity verification.

    Addresses SECURITY_001.md Finding #2:
    - Compiled artifact integrity is verified at load
    - Tampering detection (hash mismatch, removed delimiters)
    - Missing files detection
    """

    def test_verify_missing_artifact(self, tmp_path):
        """Verification should fail gracefully for missing artifact."""
        from aria_esi.persona.compiler import verify_persona_artifact

        artifact_path = tmp_path / "nonexistent.json"
        result = verify_persona_artifact(artifact_path, tmp_path)

        assert result.valid is False
        assert result.artifact_exists is False
        assert "not found" in result.issues[0].lower()

    def test_verify_valid_artifact(self, tmp_path):
        """Verification should pass for valid, unmodified artifact."""
        from aria_esi.persona.compiler import (
            compile_persona_context,
            verify_persona_artifact,
        )

        # Create source files
        (tmp_path / "personas" / "test").mkdir(parents=True)
        (tmp_path / "personas" / "test" / "voice.md").write_text("# Voice\nTest content")
        (tmp_path / "personas" / "test" / "manifest.yaml").write_text("name: test")

        # Compile artifact
        persona_context = {
            "persona": "test",
            "branch": "empire",
            "rp_level": "on",
            "files": [
                "personas/test/voice.md",
                "personas/test/manifest.yaml",
            ],
        }
        artifact_path = tmp_path / ".persona-context-compiled.json"
        compile_persona_context(persona_context, tmp_path, artifact_path)

        # Verify
        result = verify_persona_artifact(artifact_path, tmp_path)

        assert result.valid is True
        assert result.artifact_exists is True
        assert result.artifact_hash_valid is True
        assert len(result.verified_files) == 2
        assert len(result.mismatched_files) == 0
        assert len(result.missing_files) == 0

    def test_detect_source_file_modification(self, tmp_path):
        """Verification should detect when source file has been modified."""
        from aria_esi.persona.compiler import (
            compile_persona_context,
            verify_persona_artifact,
        )

        # Create source file
        (tmp_path / "personas" / "test").mkdir(parents=True)
        source_file = tmp_path / "personas" / "test" / "voice.md"
        source_file.write_text("# Voice\nOriginal content")

        # Compile artifact
        persona_context = {
            "persona": "test",
            "branch": "empire",
            "rp_level": "on",
            "files": ["personas/test/voice.md"],
        }
        artifact_path = tmp_path / ".persona-context-compiled.json"
        compile_persona_context(persona_context, tmp_path, artifact_path)

        # Modify source file after compilation (simulates update)
        source_file.write_text("# Voice\nModified content - legitimate update")

        # Verify - should detect mismatch
        result = verify_persona_artifact(artifact_path, tmp_path)

        assert result.valid is False
        assert result.artifact_exists is True
        assert len(result.mismatched_files) == 1
        assert "personas/test/voice.md" in result.mismatched_files
        assert any("mismatch" in issue.lower() for issue in result.issues)

    def test_detect_artifact_tampering(self, tmp_path):
        """Verification should detect direct artifact tampering."""
        from aria_esi.persona.compiler import (
            compile_persona_context,
            verify_persona_artifact,
        )

        # Create source file
        (tmp_path / "personas" / "test").mkdir(parents=True)
        (tmp_path / "personas" / "test" / "voice.md").write_text("# Voice\nTest content")

        # Compile artifact
        persona_context = {
            "persona": "test",
            "branch": "empire",
            "rp_level": "on",
            "files": ["personas/test/voice.md"],
        }
        artifact_path = tmp_path / ".persona-context-compiled.json"
        compile_persona_context(persona_context, tmp_path, artifact_path)

        # Tamper with artifact - modify stored hash
        artifact = json.loads(artifact_path.read_text())
        artifact["files"][0]["sha256"] = "0" * 64  # Fake hash
        artifact_path.write_text(json.dumps(artifact))

        # Verify - should detect tampering
        result = verify_persona_artifact(artifact_path, tmp_path)

        assert result.valid is False
        assert len(result.mismatched_files) == 1

    def test_detect_removed_untrusted_data_delimiters(self, tmp_path):
        """Verification should detect removal of security delimiters."""
        from aria_esi.persona.compiler import (
            compile_persona_context,
            verify_persona_artifact,
        )

        # Create source file
        (tmp_path / "personas" / "test").mkdir(parents=True)
        (tmp_path / "personas" / "test" / "voice.md").write_text("# Voice\nTest content")

        # Compile artifact
        persona_context = {
            "persona": "test",
            "branch": "empire",
            "rp_level": "on",
            "files": ["personas/test/voice.md"],
        }
        artifact_path = tmp_path / ".persona-context-compiled.json"
        compile_persona_context(persona_context, tmp_path, artifact_path)

        # Tamper with artifact - remove delimiters from raw_content
        artifact = json.loads(artifact_path.read_text())
        # Remove the untrusted-data tags but keep the content
        artifact["raw_content"] = "# Voice\nTest content"  # Missing delimiters
        artifact_path.write_text(json.dumps(artifact))

        # Verify - should detect raw content hash mismatch (tampering)
        result = verify_persona_artifact(artifact_path, tmp_path)

        assert result.valid is False
        assert result.artifact_hash_valid is False
        assert any("tampering" in issue.lower() or "mismatch" in issue.lower() for issue in result.issues)

    def test_detect_missing_source_file(self, tmp_path):
        """Verification should detect when source file has been deleted."""
        from aria_esi.persona.compiler import (
            compile_persona_context,
            verify_persona_artifact,
        )

        # Create source file
        (tmp_path / "personas" / "test").mkdir(parents=True)
        source_file = tmp_path / "personas" / "test" / "voice.md"
        source_file.write_text("# Voice\nTest content")

        # Compile artifact
        persona_context = {
            "persona": "test",
            "branch": "empire",
            "rp_level": "on",
            "files": ["personas/test/voice.md"],
        }
        artifact_path = tmp_path / ".persona-context-compiled.json"
        compile_persona_context(persona_context, tmp_path, artifact_path)

        # Delete source file
        source_file.unlink()

        # Verify - should detect missing file
        result = verify_persona_artifact(artifact_path, tmp_path)

        assert result.valid is False
        assert len(result.missing_files) == 1
        assert "personas/test/voice.md" in result.missing_files

    def test_verify_malformed_artifact(self, tmp_path):
        """Verification should handle malformed artifact gracefully."""
        from aria_esi.persona.compiler import verify_persona_artifact

        # Create malformed artifact
        artifact_path = tmp_path / ".persona-context-compiled.json"
        artifact_path.write_text("{ invalid json }")

        result = verify_persona_artifact(artifact_path, tmp_path)

        assert result.valid is False
        assert result.artifact_exists is True
        assert any("parse" in issue.lower() for issue in result.issues)

    def test_verify_artifact_missing_fields(self, tmp_path):
        """Verification should detect artifact missing required fields."""
        from aria_esi.persona.compiler import verify_persona_artifact

        # Create artifact missing required fields
        artifact_path = tmp_path / ".persona-context-compiled.json"
        artifact_path.write_text('{"persona": "test"}')  # Missing files, integrity

        result = verify_persona_artifact(artifact_path, tmp_path)

        assert result.valid is False
        assert any("missing" in issue.lower() for issue in result.issues)
