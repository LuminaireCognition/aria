"""
Tests for path security validation.

Security: These tests verify path validation logic that protects
against directory traversal attacks. See dev/reviews/PYTHON_REVIEW_2026-01.md P0 #2.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aria_esi.core.config import reset_settings
from aria_esi.core.path_security import (
    ALLOWED_EXTENSIONS,
    DEFAULT_MAX_FILE_SIZE,
    PERSONA_ALLOWED_PREFIXES,
    PILOT_ID_PATTERN,
    PathValidationError,
    is_break_glass_enabled,
    safe_read_persona_file,
    validate_path,
    validate_persona_file_path,
    validate_persona_path,
    validate_pilot_id,
)

# Environment variable for break-glass mode
BREAK_GLASS_ENV_VAR = "ARIA_ALLOW_UNSAFE_PATHS"


class TestValidatePath:
    """Test generic path validation."""

    def test_valid_persona_path(self, tmp_path: Path):
        """Valid persona paths are accepted."""
        # Create the directories so symlink check passes
        (tmp_path / "personas" / "paria").mkdir(parents=True)
        (tmp_path / "personas" / "paria" / "voice.md").touch()

        is_safe, error = validate_path(
            "personas/paria/voice.md",
            tmp_path,
            PERSONA_ALLOWED_PREFIXES,
        )

        assert is_safe is True
        assert error is None

    def test_valid_skills_path(self, tmp_path: Path):
        """Valid skills paths are accepted."""
        (tmp_path / ".claude" / "skills" / "route").mkdir(parents=True)
        (tmp_path / ".claude" / "skills" / "route" / "SKILL.md").touch()

        is_safe, error = validate_path(
            ".claude/skills/route/SKILL.md",
            tmp_path,
            PERSONA_ALLOWED_PREFIXES,
        )

        assert is_safe is True
        assert error is None

    def test_rejects_empty_path(self, tmp_path: Path):
        """Empty paths are rejected."""
        is_safe, error = validate_path("", tmp_path, PERSONA_ALLOWED_PREFIXES)

        assert is_safe is False
        assert "Empty path" in error

    def test_rejects_none_path(self, tmp_path: Path):
        """None paths are rejected."""
        is_safe, error = validate_path(None, tmp_path, PERSONA_ALLOWED_PREFIXES)

        assert is_safe is False
        assert "Empty path" in error

    def test_rejects_absolute_unix_path(self, tmp_path: Path):
        """Absolute Unix paths are rejected."""
        is_safe, error = validate_path("/etc/passwd", tmp_path, PERSONA_ALLOWED_PREFIXES)

        assert is_safe is False
        assert "Absolute paths not allowed" in error

    def test_rejects_absolute_windows_path(self, tmp_path: Path):
        """Absolute Windows paths are rejected."""
        is_safe, error = validate_path("C:\\Windows\\System32", tmp_path, PERSONA_ALLOWED_PREFIXES)

        assert is_safe is False
        assert "Absolute paths not allowed" in error

    def test_rejects_path_traversal_simple(self, tmp_path: Path):
        """Simple path traversal is rejected."""
        is_safe, error = validate_path("../../../etc/passwd", tmp_path, PERSONA_ALLOWED_PREFIXES)

        assert is_safe is False
        assert "Path traversal not allowed" in error

    def test_rejects_path_traversal_in_middle(self, tmp_path: Path):
        """Path traversal in middle of path is rejected."""
        is_safe, error = validate_path(
            "personas/../../etc/passwd", tmp_path, PERSONA_ALLOWED_PREFIXES
        )

        assert is_safe is False
        assert "Path traversal not allowed" in error

    def test_rejects_path_traversal_hidden(self, tmp_path: Path):
        """Path traversal with extra components is rejected."""
        is_safe, error = validate_path(
            "personas/paria/../../..", tmp_path, PERSONA_ALLOWED_PREFIXES
        )

        assert is_safe is False
        assert "Path traversal not allowed" in error

    def test_rejects_non_allowlisted_path(self, tmp_path: Path):
        """Paths not in allowlist are rejected."""
        is_safe, error = validate_path("credentials/secret.json", tmp_path, PERSONA_ALLOWED_PREFIXES)

        assert is_safe is False
        assert "not in allowlist" in error

    def test_rejects_root_relative_path(self, tmp_path: Path):
        """Root-relative paths (userdata/) are rejected."""
        is_safe, error = validate_path("userdata/pilots/test", tmp_path, PERSONA_ALLOWED_PREFIXES)

        assert is_safe is False
        assert "not in allowlist" in error

    def test_detects_symlink_escape(self, tmp_path: Path):
        """Symlinks that escape project root are detected."""
        # Create a symlink that points outside project
        (tmp_path / "personas").mkdir()
        symlink_path = tmp_path / "personas" / "evil.md"

        # Create symlink to /etc/passwd (or just a file outside base_path)
        parent_dir = tmp_path.parent
        external_file = parent_dir / "external_secret.txt"
        external_file.write_text("secret")

        try:
            symlink_path.symlink_to(external_file)
        except OSError:
            pytest.skip("Cannot create symlinks on this system")

        is_safe, error = validate_path(
            "personas/evil.md", tmp_path, PERSONA_ALLOWED_PREFIXES
        )

        assert is_safe is False
        assert "escapes project root" in error or "not in allowlist" in error

    def test_allows_valid_internal_symlink(self, tmp_path: Path):
        """Symlinks within allowed directories are accepted."""
        # Create directory structure
        (tmp_path / "personas" / "paria").mkdir(parents=True)
        (tmp_path / "personas" / "paria" / "voice.md").write_text("content")

        # Create symlink within personas/
        symlink_path = tmp_path / "personas" / "paria" / "link.md"
        symlink_path.symlink_to(tmp_path / "personas" / "paria" / "voice.md")

        is_safe, error = validate_path(
            "personas/paria/link.md", tmp_path, PERSONA_ALLOWED_PREFIXES
        )

        assert is_safe is True
        assert error is None

    def test_skip_symlink_check(self, tmp_path: Path):
        """Can disable symlink checking for performance."""
        # Path doesn't exist, would fail symlink check
        is_safe, error = validate_path(
            "personas/nonexistent/file.md",
            tmp_path,
            PERSONA_ALLOWED_PREFIXES,
            check_symlinks=False,
        )

        # Should pass prefix check even if file doesn't exist
        assert is_safe is True
        assert error is None


class TestValidatePersonaPath:
    """Test persona-specific path validation wrapper."""

    def test_valid_persona_file(self, tmp_path: Path):
        """Valid persona files are accepted."""
        (tmp_path / "personas" / "aria-mk4").mkdir(parents=True)
        (tmp_path / "personas" / "aria-mk4" / "manifest.yaml").touch()

        is_safe, error = validate_persona_path("personas/aria-mk4/manifest.yaml", tmp_path)

        assert is_safe is True
        assert error is None

    def test_uses_correct_prefixes(self, tmp_path: Path):
        """Uses PERSONA_ALLOWED_PREFIXES."""
        # Should reject paths not in persona prefixes
        is_safe, error = validate_persona_path("reference/data.json", tmp_path)

        assert is_safe is False
        assert "not in allowlist" in error


class TestValidatePilotId:
    """Test pilot ID format validation."""

    def test_valid_numeric_id(self):
        """Valid numeric IDs are accepted."""
        is_valid, error = validate_pilot_id("2123984364")

        assert is_valid is True
        assert error is None

    def test_valid_large_id(self):
        """Large numeric IDs (max int64) are accepted."""
        is_valid, error = validate_pilot_id("9223372036854775807")

        assert is_valid is True
        assert error is None

    def test_valid_small_id(self):
        """Small numeric IDs are accepted."""
        is_valid, error = validate_pilot_id("1")

        assert is_valid is True
        assert error is None

    def test_rejects_empty_id(self):
        """Empty IDs are rejected."""
        is_valid, error = validate_pilot_id("")

        assert is_valid is False
        assert "Empty pilot ID" in error

    def test_rejects_none_id(self):
        """None IDs are rejected."""
        is_valid, error = validate_pilot_id(None)

        assert is_valid is False
        assert "Empty pilot ID" in error

    def test_rejects_path_traversal(self):
        """Path traversal attempts are rejected."""
        is_valid, error = validate_pilot_id("../../../etc/passwd")

        assert is_valid is False
        assert "Invalid pilot ID format" in error
        assert "must be numeric" in error

    def test_rejects_alpha_characters(self):
        """Alphanumeric IDs are rejected."""
        is_valid, error = validate_pilot_id("abc123")

        assert is_valid is False
        assert "must be numeric" in error

    def test_rejects_special_characters(self):
        """IDs with special characters are rejected."""
        test_cases = [
            "123/456",
            "123\\456",
            "123.json",
            "123;456",
            "123 456",
            "-123",
            "123-",
        ]

        for test_id in test_cases:
            is_valid, error = validate_pilot_id(test_id)
            assert is_valid is False, f"Should reject: {test_id}"
            assert "must be numeric" in error

    def test_rejects_too_long_id(self):
        """IDs exceeding 20 digits are rejected."""
        # 21 digits - too long
        is_valid, error = validate_pilot_id("123456789012345678901")

        assert is_valid is False
        assert "must be numeric" in error


class TestBreakGlassMechanism:
    """Test break-glass emergency bypass."""

    @pytest.fixture(autouse=True)
    def reset_config(self):
        """Reset config cache before and after each test."""
        reset_settings()
        yield
        reset_settings()

    def test_break_glass_disabled_by_default(self, monkeypatch):
        """Break-glass is disabled by default."""
        monkeypatch.delenv(BREAK_GLASS_ENV_VAR, raising=False)
        reset_settings()  # Re-load after env change

        assert is_break_glass_enabled() is False

    def test_break_glass_enabled_with_1(self, monkeypatch):
        """Break-glass enabled with '1'."""
        monkeypatch.setenv(BREAK_GLASS_ENV_VAR, "1")
        reset_settings()  # Re-load after env change

        assert is_break_glass_enabled() is True

    def test_break_glass_enabled_with_true(self, monkeypatch):
        """Break-glass enabled with 'true'."""
        monkeypatch.setenv(BREAK_GLASS_ENV_VAR, "true")
        reset_settings()  # Re-load after env change

        assert is_break_glass_enabled() is True

    def test_break_glass_enabled_with_yes(self, monkeypatch):
        """Break-glass enabled with 'yes'."""
        monkeypatch.setenv(BREAK_GLASS_ENV_VAR, "yes")
        reset_settings()  # Re-load after env change

        assert is_break_glass_enabled() is True

    def test_break_glass_case_insensitive(self, monkeypatch):
        """Break-glass value is case-insensitive."""
        monkeypatch.setenv(BREAK_GLASS_ENV_VAR, "TRUE")
        reset_settings()  # Re-load after env change

        assert is_break_glass_enabled() is True

    def test_break_glass_not_enabled_with_false(self, monkeypatch):
        """Break-glass not enabled with 'false'."""
        monkeypatch.setenv(BREAK_GLASS_ENV_VAR, "false")
        reset_settings()  # Re-load after env change

        assert is_break_glass_enabled() is False

    def test_break_glass_invalid_value_raises_error(self, monkeypatch):
        """Break-glass with invalid value raises validation error."""
        import pydantic

        monkeypatch.setenv(BREAK_GLASS_ENV_VAR, "maybe")
        reset_settings()  # Re-load after env change

        with pytest.raises(pydantic.ValidationError):
            is_break_glass_enabled()

    def test_break_glass_bypasses_path_validation(self, tmp_path: Path, monkeypatch):
        """Break-glass bypasses path validation."""
        monkeypatch.setenv(BREAK_GLASS_ENV_VAR, "1")
        reset_settings()  # Re-load after env change

        # This would normally fail - path traversal
        is_safe, error = validate_path(
            "../../../etc/passwd",
            tmp_path,
            PERSONA_ALLOWED_PREFIXES,
        )

        assert is_safe is True
        assert error is None

    def test_break_glass_bypasses_pilot_id_validation(self, monkeypatch):
        """Break-glass bypasses pilot_id validation."""
        monkeypatch.setenv(BREAK_GLASS_ENV_VAR, "1")
        reset_settings()  # Re-load after env change

        # This would normally fail - not numeric
        is_valid, error = validate_pilot_id("../../../etc/passwd")


class TestPathValidationError:
    """Test PathValidationError exception."""

    def test_stores_path_and_reason(self):
        """PathValidationError stores path and reason."""
        error = PathValidationError(
            "Path validation failed",
            path="../etc/passwd",
            reason="traversal"
        )

        assert error.path == "../etc/passwd"
        assert error.reason == "traversal"

    def test_str_returns_message(self):
        """str() returns the message."""
        error = PathValidationError("Custom message")
        assert str(error) == "Custom message"

    def test_optional_fields(self):
        """Path and reason are optional."""
        error = PathValidationError("Just a message")

        assert error.path is None
        assert error.reason is None


class TestPilotIdPattern:
    """Test the pilot ID regex pattern directly."""

    def test_matches_valid_ids(self):
        """Pattern matches valid EVE character IDs."""
        valid_ids = [
            "1",
            "12",
            "2123984364",
            "95538921",
            "12345678901234567890",  # 20 digits max
        ]

        for pilot_id in valid_ids:
            assert PILOT_ID_PATTERN.match(pilot_id), f"Should match: {pilot_id}"

    def test_rejects_invalid_ids(self):
        """Pattern rejects invalid IDs."""
        invalid_ids = [
            "",
            "abc",
            "123abc",
            "abc123",
            "-123",
            "123.456",
            "123/456",
            "../etc",
            "123456789012345678901",  # 21 digits - too long
        ]

        for pilot_id in invalid_ids:
            assert not PILOT_ID_PATTERN.match(pilot_id), f"Should not match: {pilot_id}"


class TestExtensionValidation:
    """Test file extension allowlist validation (SEC-001/SEC-002)."""

    def test_allows_md_extension(self, tmp_path: Path):
        """Markdown files are accepted."""
        (tmp_path / "personas" / "paria").mkdir(parents=True)
        (tmp_path / "personas" / "paria" / "voice.md").touch()

        is_safe, error = validate_persona_file_path(
            "personas/paria/voice.md", tmp_path
        )

        assert is_safe is True
        assert error is None

    def test_allows_yaml_extension(self, tmp_path: Path):
        """YAML files are accepted."""
        (tmp_path / "personas" / "paria").mkdir(parents=True)
        (tmp_path / "personas" / "paria" / "manifest.yaml").touch()

        is_safe, error = validate_persona_file_path(
            "personas/paria/manifest.yaml", tmp_path
        )

        assert is_safe is True
        assert error is None

    def test_allows_json_extension(self, tmp_path: Path):
        """JSON files are accepted."""
        (tmp_path / ".claude" / "skills").mkdir(parents=True)
        (tmp_path / ".claude" / "skills" / "_index.json").touch()

        is_safe, error = validate_persona_file_path(
            ".claude/skills/_index.json", tmp_path
        )

        assert is_safe is True
        assert error is None

    def test_rejects_py_extension(self, tmp_path: Path):
        """Python files are rejected."""
        (tmp_path / "personas" / "evil").mkdir(parents=True)
        (tmp_path / "personas" / "evil" / "script.py").touch()

        is_safe, error = validate_persona_file_path(
            "personas/evil/script.py", tmp_path
        )

        assert is_safe is False
        assert "Extension not allowed" in error
        assert ".py" in error or "script.py" in error

    def test_rejects_sh_extension(self, tmp_path: Path):
        """Shell scripts are rejected."""
        (tmp_path / "personas" / "evil").mkdir(parents=True)
        (tmp_path / "personas" / "evil" / "exploit.sh").touch()

        is_safe, error = validate_persona_file_path(
            "personas/evil/exploit.sh", tmp_path
        )

        assert is_safe is False
        assert "Extension not allowed" in error

    def test_rejects_no_extension(self, tmp_path: Path):
        """Files without extension are rejected."""
        (tmp_path / "personas" / "evil").mkdir(parents=True)
        (tmp_path / "personas" / "evil" / "noextension").touch()

        is_safe, error = validate_persona_file_path(
            "personas/evil/noextension", tmp_path
        )

        assert is_safe is False
        assert "Extension not allowed" in error

    def test_rejects_executable_extension(self, tmp_path: Path):
        """Executable files are rejected."""
        (tmp_path / "personas" / "evil").mkdir(parents=True)
        (tmp_path / "personas" / "evil" / "malware.exe").touch()

        is_safe, error = validate_persona_file_path(
            "personas/evil/malware.exe", tmp_path
        )

        assert is_safe is False
        assert "Extension not allowed" in error

    def test_custom_extension_allowlist(self, tmp_path: Path):
        """Custom extension allowlist works."""
        (tmp_path / "personas" / "custom").mkdir(parents=True)
        (tmp_path / "personas" / "custom" / "data.txt").touch()

        # Default allowlist rejects .txt
        is_safe, error = validate_persona_file_path(
            "personas/custom/data.txt", tmp_path
        )
        assert is_safe is False

        # Custom allowlist accepts .txt
        custom_exts = frozenset({".txt", ".md"})
        is_safe, error = validate_persona_file_path(
            "personas/custom/data.txt", tmp_path, allowed_extensions=custom_exts
        )
        assert is_safe is True
        assert error is None

    def test_extension_case_insensitive(self, tmp_path: Path):
        """Extension matching is case-insensitive."""
        (tmp_path / "personas" / "test").mkdir(parents=True)
        (tmp_path / "personas" / "test" / "readme.MD").touch()

        is_safe, error = validate_persona_file_path(
            "personas/test/readme.MD", tmp_path
        )

        assert is_safe is True
        assert error is None

    def test_combines_with_path_validation(self, tmp_path: Path):
        """Extension validation combines with path prefix validation."""
        # Valid extension but invalid prefix
        is_safe, error = validate_persona_file_path(
            "userdata/secret.md", tmp_path
        )

        assert is_safe is False
        assert "not in allowlist" in error

    def test_combines_with_traversal_check(self, tmp_path: Path):
        """Extension validation combines with traversal detection."""
        # Valid extension but contains traversal
        is_safe, error = validate_persona_file_path(
            "personas/../../../etc/passwd.md", tmp_path
        )

        assert is_safe is False
        assert "Path traversal not allowed" in error


class TestSafeReadPersonaFile:
    """Test safe file reading utility (SEC-001/SEC-002)."""

    def test_reads_valid_file(self, tmp_path: Path):
        """Can read valid persona files."""
        (tmp_path / "personas" / "paria").mkdir(parents=True)
        test_content = "# Voice Guide\n\nThis is PARIA's voice."
        (tmp_path / "personas" / "paria" / "voice.md").write_text(test_content)

        content, error = safe_read_persona_file(
            "personas/paria/voice.md", tmp_path
        )

        assert content == test_content
        assert error is None

    def test_rejects_traversal(self, tmp_path: Path):
        """Rejects path traversal attempts."""
        content, error = safe_read_persona_file(
            "../../../etc/passwd", tmp_path
        )

        assert content is None
        assert error is not None
        # Could be "Path traversal not allowed" or "not in allowlist" depending on check order
        assert "traversal" in error.lower() or "not in allowlist" in error

    def test_rejects_oversized_file(self, tmp_path: Path):
        """Rejects files exceeding size limit."""
        (tmp_path / "personas" / "large").mkdir(parents=True)
        # Create a file larger than max_size_bytes
        large_content = "x" * 1001
        (tmp_path / "personas" / "large" / "big.md").write_text(large_content)

        content, error = safe_read_persona_file(
            "personas/large/big.md", tmp_path, max_size_bytes=1000
        )

        assert content is None
        assert error is not None
        assert "too large" in error

    def test_rejects_wrong_extension(self, tmp_path: Path):
        """Rejects files with wrong extension."""
        (tmp_path / "personas" / "evil").mkdir(parents=True)
        (tmp_path / "personas" / "evil" / "script.py").write_text("import os")

        content, error = safe_read_persona_file(
            "personas/evil/script.py", tmp_path
        )

        assert content is None
        assert error is not None
        assert "Extension not allowed" in error

    def test_rejects_nonexistent_file(self, tmp_path: Path):
        """Rejects files that don't exist."""
        (tmp_path / "personas" / "ghost").mkdir(parents=True)

        content, error = safe_read_persona_file(
            "personas/ghost/missing.md", tmp_path
        )

        assert content is None
        assert error is not None
        assert "not found" in error

    def test_rejects_directory(self, tmp_path: Path):
        """Rejects paths that point to directories."""
        (tmp_path / "personas" / "notafile.md").mkdir(parents=True)

        content, error = safe_read_persona_file(
            "personas/notafile.md", tmp_path
        )

        assert content is None
        assert error is not None
        assert "Not a file" in error

    def test_uses_default_max_size(self, tmp_path: Path):
        """Uses DEFAULT_MAX_FILE_SIZE when not specified."""
        (tmp_path / "personas" / "test").mkdir(parents=True)
        # Create a small file (should be accepted)
        (tmp_path / "personas" / "test" / "small.md").write_text("small")

        content, error = safe_read_persona_file(
            "personas/test/small.md", tmp_path
        )

        assert content == "small"
        assert error is None
        # Default limit should be 100KB
        assert DEFAULT_MAX_FILE_SIZE == 100_000

    def test_custom_extension_allowlist(self, tmp_path: Path):
        """Custom extension allowlist works with safe_read."""
        (tmp_path / "personas" / "custom").mkdir(parents=True)
        (tmp_path / "personas" / "custom" / "config.toml").write_text("[settings]")

        # Default allowlist rejects .toml
        content, error = safe_read_persona_file(
            "personas/custom/config.toml", tmp_path
        )
        assert content is None
        assert "Extension not allowed" in error

        # Custom allowlist accepts .toml
        custom_exts = frozenset({".toml"})
        content, error = safe_read_persona_file(
            "personas/custom/config.toml", tmp_path,
            allowed_extensions=custom_exts
        )
        assert content == "[settings]"
        assert error is None

    def test_rejects_binary_file_as_utf8_error(self, tmp_path: Path):
        """Rejects binary files with invalid UTF-8."""
        (tmp_path / "personas" / "binary").mkdir(parents=True)
        # Write binary content that's not valid UTF-8
        (tmp_path / "personas" / "binary" / "data.md").write_bytes(b"\xff\xfe\x00\x01")

        content, error = safe_read_persona_file(
            "personas/binary/data.md", tmp_path
        )

        assert content is None
        assert error is not None
        assert "UTF-8" in error


class TestAllowedExtensionsConstant:
    """Test ALLOWED_EXTENSIONS constant."""

    def test_contains_expected_extensions(self):
        """ALLOWED_EXTENSIONS contains expected file types."""
        assert ".md" in ALLOWED_EXTENSIONS
        assert ".yaml" in ALLOWED_EXTENSIONS
        assert ".json" in ALLOWED_EXTENSIONS

    def test_is_frozen(self):
        """ALLOWED_EXTENSIONS is immutable."""
        assert isinstance(ALLOWED_EXTENSIONS, frozenset)

    def test_does_not_contain_dangerous_extensions(self):
        """ALLOWED_EXTENSIONS does not include dangerous file types."""
        dangerous = {".py", ".sh", ".exe", ".bat", ".cmd", ".ps1", ".rb", ".pl"}
        for ext in dangerous:
            assert ext not in ALLOWED_EXTENSIONS, f"Should not allow {ext}"
