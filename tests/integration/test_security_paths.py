"""
Integration tests for path security validation.

SEC-001: Persona file path allowlisting
SEC-002: Skill overlay path validation

These tests verify end-to-end rejection of malicious paths in:
- Persona context file lists
- Skill overlay paths
- Skill redirect paths
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aria_esi.commands.persona import (
    build_persona_context,
    validate_persona_context,
)
from aria_esi.core.path_security import (
    safe_read_persona_file,
    validate_persona_file_path,
)


class TestMaliciousPersonaFilePaths:
    """
    SEC-001: Test rejection of malicious persona file paths.

    Simulates compromised profile.md with injected file paths.
    """

    def test_rejects_traversal_in_file_list(self, tmp_path: Path):
        """Rejects path traversal in persona_context.files."""
        # Create a minimal skill index
        skill_index = {"skills": []}

        # Create malicious persona_context with traversal attempt
        persona_context = {
            "branch": "pirate",
            "persona": "paria",
            "fallback": None,
            "rp_level": "on",
            "files": [
                "personas/paria/voice.md",
                "../../../etc/passwd",  # Malicious!
                "personas/_shared/pirate/identity.md",
            ],
            "skill_overlay_path": "personas/paria/skill-overlays",
            "overlay_fallback_path": None,
        }

        result = validate_persona_context(
            persona_context, skill_index, tmp_path
        )

        # Should have security issue for the traversal path
        assert not result["valid"]
        security_issues = result["issues"]["security"]
        assert len(security_issues) >= 1

        traversal_issue = next(
            (i for i in security_issues if "../../../etc/passwd" in i.get("path", "")),
            None,
        )
        assert traversal_issue is not None
        assert "unsafe_persona_file_path" in traversal_issue["type"]

    def test_rejects_absolute_path_in_file_list(self, tmp_path: Path):
        """Rejects absolute paths in persona_context.files."""
        skill_index = {"skills": []}

        persona_context = {
            "branch": "empire",
            "persona": "aria-mk4",
            "fallback": None,
            "rp_level": "full",
            "files": [
                "/etc/passwd",  # Absolute path - malicious!
                "personas/aria-mk4/voice.md",
            ],
            "skill_overlay_path": "personas/aria-mk4/skill-overlays",
            "overlay_fallback_path": None,
        }

        result = validate_persona_context(
            persona_context, skill_index, tmp_path
        )

        assert not result["valid"]
        security_issues = result["issues"]["security"]

        # Find the issue for absolute path
        abs_issue = next(
            (i for i in security_issues if "/etc/passwd" in i.get("path", "")),
            None,
        )
        assert abs_issue is not None

    def test_rejects_windows_absolute_path(self, tmp_path: Path):
        """Rejects Windows-style absolute paths."""
        skill_index = {"skills": []}

        persona_context = {
            "branch": "empire",
            "persona": "aria-mk4",
            "fallback": None,
            "rp_level": "on",
            "files": [
                "C:\\Windows\\System32\\config\\SAM",  # Windows path
            ],
            "skill_overlay_path": "personas/aria-mk4/skill-overlays",
            "overlay_fallback_path": None,
        }

        result = validate_persona_context(
            persona_context, skill_index, tmp_path
        )

        assert not result["valid"]
        assert len(result["issues"]["security"]) >= 1

    def test_rejects_non_allowlisted_prefix(self, tmp_path: Path):
        """Rejects paths outside allowed prefixes."""
        skill_index = {"skills": []}

        persona_context = {
            "branch": "pirate",
            "persona": "paria",
            "fallback": None,
            "rp_level": "on",
            "files": [
                "userdata/credentials/secret.json",  # Not in personas/ or .claude/skills/
            ],
            "skill_overlay_path": "personas/paria/skill-overlays",
            "overlay_fallback_path": None,
        }

        result = validate_persona_context(
            persona_context, skill_index, tmp_path
        )

        assert not result["valid"]
        assert len(result["issues"]["security"]) >= 1


class TestMaliciousOverlayPaths:
    """
    SEC-002: Test rejection of malicious skill overlay paths.

    Simulates compromised persona_context with injected overlay paths.
    """

    def test_rejects_traversal_in_overlay_path(self, tmp_path: Path):
        """Rejects path traversal in skill_overlay_path."""
        # Create skill index with overlay-enabled skill
        skill_index = {
            "skills": [
                {
                    "name": "route",
                    "has_persona_overlay": True,
                },
            ]
        }

        # Malicious overlay path with traversal
        persona_context = {
            "branch": "pirate",
            "persona": "paria",
            "fallback": None,
            "rp_level": "on",
            "files": [],
            "skill_overlay_path": "personas/../../etc",  # Malicious!
            "overlay_fallback_path": None,
        }

        result = validate_persona_context(
            persona_context, skill_index, tmp_path
        )

        # Should detect unsafe overlay path
        assert not result["valid"]
        security_issues = result["issues"]["security"]
        assert len(security_issues) >= 1

        overlay_issue = next(
            (i for i in security_issues if i.get("type") == "unsafe_overlay_path"),
            None,
        )
        assert overlay_issue is not None

    def test_rejects_non_allowlisted_overlay_path(self, tmp_path: Path):
        """Rejects overlay paths outside allowed prefixes."""
        skill_index = {
            "skills": [
                {
                    "name": "secret-skill",
                    "has_persona_overlay": True,
                },
            ]
        }

        persona_context = {
            "branch": "empire",
            "persona": "aria-mk4",
            "fallback": None,
            "rp_level": "full",
            "files": [],
            "skill_overlay_path": "userdata/malicious-overlays",  # Not allowed!
            "overlay_fallback_path": None,
        }

        result = validate_persona_context(
            persona_context, skill_index, tmp_path
        )

        assert not result["valid"]
        assert any(
            i.get("type") == "unsafe_overlay_path"
            for i in result["issues"]["security"]
        )


class TestExtensionEnforcement:
    """Test that extension allowlist is enforced consistently."""

    def test_py_extension_blocked_everywhere(self, tmp_path: Path):
        """Python files are blocked in all contexts."""
        (tmp_path / "personas" / "test").mkdir(parents=True)
        (tmp_path / "personas" / "test" / "evil.py").write_text("print('pwned')")

        # Direct validation
        is_safe, error = validate_persona_file_path(
            "personas/test/evil.py", tmp_path
        )
        assert is_safe is False

        # Safe read
        content, error = safe_read_persona_file(
            "personas/test/evil.py", tmp_path
        )
        assert content is None
        assert "Extension not allowed" in error

    def test_sh_extension_blocked_everywhere(self, tmp_path: Path):
        """Shell scripts are blocked in all contexts."""
        (tmp_path / "personas" / "test").mkdir(parents=True)
        (tmp_path / "personas" / "test" / "exploit.sh").write_text("#!/bin/bash\nrm -rf /")

        is_safe, error = validate_persona_file_path(
            "personas/test/exploit.sh", tmp_path
        )
        assert is_safe is False

        content, error = safe_read_persona_file(
            "personas/test/exploit.sh", tmp_path
        )
        assert content is None


class TestSymlinkEscapeDetection:
    """Test symlink escape detection in persona paths."""

    def test_detects_symlink_to_secrets(self, tmp_path: Path):
        """Detects symlinks that escape to sensitive files."""
        # Create personas directory
        (tmp_path / "personas" / "evil").mkdir(parents=True)

        # Create a "secret" file outside personas
        secrets_dir = tmp_path / "userdata" / "credentials"
        secrets_dir.mkdir(parents=True)
        (secrets_dir / "tokens.json").write_text('{"access_token": "secret123"}')

        # Create symlink in personas pointing to secrets
        symlink_path = tmp_path / "personas" / "evil" / "tokens.md"
        try:
            symlink_path.symlink_to(secrets_dir / "tokens.json")
        except OSError:
            pytest.skip("Cannot create symlinks on this system")

        # Should detect and reject
        is_safe, error = validate_persona_file_path(
            "personas/evil/tokens.md", tmp_path
        )

        assert is_safe is False
        # Should catch either "escapes project root" or "not in allowlist"
        assert error is not None


class TestBuildPersonaContextSecurity:
    """Test that build_persona_context only includes safe paths."""

    def test_only_includes_existing_safe_files(self, tmp_path: Path):
        """Build only includes files that exist and are safe."""
        # Create valid persona structure
        (tmp_path / "personas" / "_shared" / "pirate").mkdir(parents=True)
        (tmp_path / "personas" / "_shared" / "pirate" / "identity.md").write_text("Identity")

        (tmp_path / "personas" / "paria").mkdir(parents=True)
        (tmp_path / "personas" / "paria" / "manifest.yaml").write_text("name: PARIA")
        (tmp_path / "personas" / "paria" / "voice.md").write_text("Voice")

        context = build_persona_context(
            faction="pirate",
            rp_level="on",
            base_path=tmp_path,
        )

        # All files in context should be within allowed prefixes
        for file_path in context["files"]:
            assert file_path.startswith("personas/"), f"Unexpected path: {file_path}"
            # All should have safe extensions
            assert file_path.endswith((".md", ".yaml", ".json")), f"Bad extension: {file_path}"
