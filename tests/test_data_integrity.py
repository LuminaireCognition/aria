"""
Tests for aria_esi.core.data_integrity

Tests for checksum computation, manifest loading, and integrity verification.
"""

import json

import pytest


class TestComputeSha256:
    """Tests for SHA256 checksum computation."""

    def test_compute_sha256_returns_hex_string(self, tmp_path):
        """Test that compute_sha256 returns a hex string."""
        from aria_esi.core.data_integrity import compute_sha256

        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        result = compute_sha256(test_file)

        assert isinstance(result, str)
        assert len(result) == 64  # SHA256 produces 64 hex characters
        assert all(c in "0123456789abcdef" for c in result)

    def test_compute_sha256_consistent(self, tmp_path):
        """Test that compute_sha256 returns consistent results."""
        from aria_esi.core.data_integrity import compute_sha256

        test_file = tmp_path / "test.txt"
        test_file.write_text("Consistent content")

        result1 = compute_sha256(test_file)
        result2 = compute_sha256(test_file)

        assert result1 == result2

    def test_compute_sha256_known_value(self, tmp_path):
        """Test compute_sha256 against a known hash."""
        from aria_esi.core.data_integrity import compute_sha256

        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        result = compute_sha256(test_file)

        # SHA256 of "test" is well-known
        expected = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
        assert result == expected

    def test_compute_sha256_empty_file(self, tmp_path):
        """Test compute_sha256 with an empty file."""
        from aria_esi.core.data_integrity import compute_sha256

        test_file = tmp_path / "empty.txt"
        test_file.write_text("")

        result = compute_sha256(test_file)

        # SHA256 of empty string
        expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        assert result == expected

    def test_compute_sha256_missing_file(self, tmp_path):
        """Test compute_sha256 raises for missing file."""
        from aria_esi.core.data_integrity import compute_sha256

        missing_file = tmp_path / "nonexistent.txt"

        with pytest.raises(FileNotFoundError):
            compute_sha256(missing_file)


class TestVerifyChecksum:
    """Tests for checksum verification."""

    def test_verify_checksum_match(self, tmp_path):
        """Test verify_checksum returns True for matching checksums."""
        from aria_esi.core.data_integrity import compute_sha256, verify_checksum

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        expected = compute_sha256(test_file)
        result = verify_checksum(test_file, expected)

        assert result is True

    def test_verify_checksum_mismatch(self, tmp_path):
        """Test verify_checksum returns False for mismatched checksums."""
        from aria_esi.core.data_integrity import verify_checksum

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        wrong_checksum = "a" * 64

        result = verify_checksum(test_file, wrong_checksum)

        assert result is False

    def test_verify_checksum_case_insensitive(self, tmp_path):
        """Test verify_checksum is case-insensitive."""
        from aria_esi.core.data_integrity import compute_sha256, verify_checksum

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        expected = compute_sha256(test_file)
        upper_expected = expected.upper()

        result = verify_checksum(test_file, upper_expected)

        assert result is True


class TestLoadDataManifest:
    """Tests for manifest loading."""

    def test_load_manifest_success(self, tmp_path):
        """Test loading a valid manifest file."""
        from aria_esi.core.data_integrity import load_data_manifest

        manifest_path = tmp_path / "data-sources.json"
        manifest_content = {
            "schema_version": 1,
            "sources": {
                "sde": {"pinned_version": "latest"},
                "eos": {"pinned_commit": None},
            },
        }
        manifest_path.write_text(json.dumps(manifest_content))

        result = load_data_manifest(manifest_path)

        assert result["schema_version"] == 1
        assert "sources" in result
        assert "sde" in result["sources"]

    def test_load_manifest_missing_file(self, tmp_path):
        """Test loading a missing manifest raises FileNotFoundError."""
        from aria_esi.core.data_integrity import load_data_manifest

        missing_path = tmp_path / "nonexistent.json"

        with pytest.raises(FileNotFoundError):
            load_data_manifest(missing_path)

    def test_load_manifest_invalid_json(self, tmp_path):
        """Test loading invalid JSON raises JSONDecodeError."""
        from aria_esi.core.data_integrity import load_data_manifest

        manifest_path = tmp_path / "invalid.json"
        manifest_path.write_text("{ not valid json }")

        with pytest.raises(json.JSONDecodeError):
            load_data_manifest(manifest_path)


class TestBreakGlassEnabled:
    """Tests for break-glass mode detection."""

    def test_break_glass_disabled_by_default(self, monkeypatch):
        """Test that break-glass is disabled when env var is not set."""
        from aria_esi.core.data_integrity import is_break_glass_enabled

        # Ensure env var is not set
        monkeypatch.delenv("ARIA_ALLOW_UNPINNED", raising=False)

        result = is_break_glass_enabled()

        assert result is False

    def test_break_glass_enabled_with_1(self, monkeypatch):
        """Test that break-glass is enabled with '1'."""
        from aria_esi.core.data_integrity import is_break_glass_enabled

        monkeypatch.setenv("ARIA_ALLOW_UNPINNED", "1")

        result = is_break_glass_enabled()

        assert result is True

    def test_break_glass_enabled_with_true(self, monkeypatch):
        """Test that break-glass is enabled with 'true'."""
        from aria_esi.core.data_integrity import is_break_glass_enabled

        monkeypatch.setenv("ARIA_ALLOW_UNPINNED", "true")

        result = is_break_glass_enabled()

        assert result is True

    def test_break_glass_enabled_with_yes(self, monkeypatch):
        """Test that break-glass is enabled with 'yes'."""
        from aria_esi.core.data_integrity import is_break_glass_enabled

        monkeypatch.setenv("ARIA_ALLOW_UNPINNED", "yes")

        result = is_break_glass_enabled()

        assert result is True

    def test_break_glass_case_insensitive(self, monkeypatch):
        """Test that break-glass detection is case-insensitive."""
        from aria_esi.core.data_integrity import is_break_glass_enabled

        monkeypatch.setenv("ARIA_ALLOW_UNPINNED", "TRUE")

        result = is_break_glass_enabled()

        assert result is True


class TestGetPinnedSdeUrl:
    """Tests for SDE URL retrieval."""

    def test_get_pinned_sde_url_default(self, tmp_path, monkeypatch):
        """Test default URL when manifest has latest version."""
        from aria_esi.core import data_integrity

        manifest_path = tmp_path / "data-sources.json"
        manifest_content = {
            "schema_version": 1,
            "sources": {
                "sde": {
                    "url_latest": "https://example.com/sde-latest.sqlite.bz2",
                    "pinned_version": "latest",
                    "sha256": None,
                },
            },
        }
        manifest_path.write_text(json.dumps(manifest_content))
        monkeypatch.setattr(data_integrity, "MANIFEST_PATH", manifest_path)

        url, checksum = data_integrity.get_pinned_sde_url()

        assert url == "https://example.com/sde-latest.sqlite.bz2"
        assert checksum is None

    def test_get_pinned_sde_url_with_checksum(self, tmp_path, monkeypatch):
        """Test URL retrieval with checksum configured."""
        from aria_esi.core import data_integrity

        manifest_path = tmp_path / "data-sources.json"
        manifest_content = {
            "schema_version": 1,
            "sources": {
                "sde": {
                    "url_latest": "https://example.com/sde-latest.sqlite.bz2",
                    "pinned_version": "latest",
                    "sha256": "abc123def456",
                },
            },
        }
        manifest_path.write_text(json.dumps(manifest_content))
        monkeypatch.setattr(data_integrity, "MANIFEST_PATH", manifest_path)

        url, checksum = data_integrity.get_pinned_sde_url()

        assert url == "https://example.com/sde-latest.sqlite.bz2"
        assert checksum == "abc123def456"

    def test_get_pinned_sde_url_specific_version(self, tmp_path, monkeypatch):
        """Test URL with specific version pinned."""
        from aria_esi.core import data_integrity

        manifest_path = tmp_path / "data-sources.json"
        manifest_content = {
            "schema_version": 1,
            "sources": {
                "sde": {
                    "url_template": "https://example.com/sde-{version}.sqlite.bz2",
                    "pinned_version": "20250101",
                    "sha256": "abc123",
                },
            },
        }
        manifest_path.write_text(json.dumps(manifest_content))
        monkeypatch.setattr(data_integrity, "MANIFEST_PATH", manifest_path)

        url, checksum = data_integrity.get_pinned_sde_url()

        assert url == "https://example.com/sde-20250101.sqlite.bz2"
        assert checksum == "abc123"


class TestGetPinnedEosCommit:
    """Tests for EOS commit retrieval."""

    def test_get_pinned_eos_commit_none(self, tmp_path, monkeypatch):
        """Test commit retrieval when not pinned."""
        from aria_esi.core import data_integrity

        manifest_path = tmp_path / "data-sources.json"
        manifest_content = {
            "schema_version": 1,
            "sources": {
                "eos": {"pinned_commit": None},
            },
        }
        manifest_path.write_text(json.dumps(manifest_content))
        monkeypatch.setattr(data_integrity, "MANIFEST_PATH", manifest_path)

        result = data_integrity.get_pinned_eos_commit()

        assert result is None

    def test_get_pinned_eos_commit_with_value(self, tmp_path, monkeypatch):
        """Test commit retrieval when pinned."""
        from aria_esi.core import data_integrity

        manifest_path = tmp_path / "data-sources.json"
        manifest_content = {
            "schema_version": 1,
            "sources": {
                "eos": {"pinned_commit": "abc123def456"},
            },
        }
        manifest_path.write_text(json.dumps(manifest_content))
        monkeypatch.setattr(data_integrity, "MANIFEST_PATH", manifest_path)

        result = data_integrity.get_pinned_eos_commit()

        assert result == "abc123def456"


class TestIntegrityError:
    """Tests for IntegrityError exception."""

    def test_integrity_error_message(self):
        """Test IntegrityError preserves message."""
        from aria_esi.core.data_integrity import IntegrityError

        error = IntegrityError("Test error message")

        assert str(error) == "Test error message"
        assert error.message == "Test error message"

    def test_integrity_error_with_expected_actual(self):
        """Test IntegrityError stores expected and actual values."""
        from aria_esi.core.data_integrity import IntegrityError

        error = IntegrityError(
            "Checksum mismatch",
            expected="abc123",
            actual="def456",
        )

        assert error.expected == "abc123"
        assert error.actual == "def456"


class TestGetIntegrityStatus:
    """Tests for overall integrity status retrieval."""

    def test_get_integrity_status_with_manifest(self, tmp_path, monkeypatch):
        """Test status retrieval with valid manifest."""
        from aria_esi.core import data_integrity

        manifest_path = tmp_path / "data-sources.json"
        manifest_content = {
            "schema_version": 1,
            "sources": {
                "sde": {
                    "pinned_version": "latest",
                    "sha256": "abc123",
                    "last_verified": "2025-01-01",
                },
                "eos": {
                    "pinned_commit": "def456",
                    "last_verified": "2025-01-02",
                },
            },
        }
        manifest_path.write_text(json.dumps(manifest_content))
        monkeypatch.setattr(data_integrity, "MANIFEST_PATH", manifest_path)

        status = data_integrity.get_integrity_status()

        assert status["manifest_available"] is True
        assert status["schema_version"] == 1
        assert status["sources"]["sde"]["pinned_version"] == "latest"
        assert status["sources"]["sde"]["has_checksum"] is True
        assert status["sources"]["eos"]["pinned_commit"] == "def456"

    def test_get_integrity_status_missing_manifest(self, tmp_path, monkeypatch):
        """Test status retrieval when manifest is missing."""
        from aria_esi.core import data_integrity

        missing_path = tmp_path / "nonexistent.json"
        monkeypatch.setattr(data_integrity, "MANIFEST_PATH", missing_path)

        status = data_integrity.get_integrity_status()

        assert status["manifest_available"] is False
        assert "sources" in status


class TestVerifySdeIntegrity:
    """Tests for SDE integrity verification."""

    def test_verify_sde_integrity_no_checksum_configured(self, tmp_path, monkeypatch):
        """Test verification passes when no checksum is configured."""
        from aria_esi.core import data_integrity

        # Create test file
        test_file = tmp_path / "sde.sqlite.bz2"
        test_file.write_text("test content")

        # Create manifest with no checksum
        manifest_path = tmp_path / "data-sources.json"
        manifest_content = {
            "schema_version": 1,
            "sources": {
                "sde": {"pinned_version": "latest", "sha256": None},
            },
        }
        manifest_path.write_text(json.dumps(manifest_content))
        monkeypatch.setattr(data_integrity, "MANIFEST_PATH", manifest_path)

        success, actual = data_integrity.verify_sde_integrity(test_file)

        assert success is True
        assert len(actual) == 64  # SHA256 hex length

    def test_verify_sde_integrity_break_glass(self, tmp_path, monkeypatch):
        """Test verification passes in break-glass mode."""
        from aria_esi.core import data_integrity

        # Create test file
        test_file = tmp_path / "sde.sqlite.bz2"
        test_file.write_text("test content")

        success, actual = data_integrity.verify_sde_integrity(
            test_file,
            expected_checksum="wrong_checksum",
            break_glass=True,
        )

        assert success is True

    def test_verify_sde_integrity_matching_checksum(self, tmp_path, monkeypatch):
        """Test verification passes with matching checksum."""
        from aria_esi.core import data_integrity

        # Create test file
        test_file = tmp_path / "sde.sqlite.bz2"
        test_file.write_text("test content")

        # Get actual checksum
        actual_checksum = data_integrity.compute_sha256(test_file)

        success, returned = data_integrity.verify_sde_integrity(
            test_file,
            expected_checksum=actual_checksum,
        )

        assert success is True
        assert returned == actual_checksum

    def test_verify_sde_integrity_mismatched_checksum(self, tmp_path, monkeypatch):
        """Test verification raises on mismatched checksum."""
        from aria_esi.core.data_integrity import IntegrityError, verify_sde_integrity

        # Create test file
        test_file = tmp_path / "sde.sqlite.bz2"
        test_file.write_text("test content")

        with pytest.raises(IntegrityError) as exc_info:
            verify_sde_integrity(test_file, expected_checksum="wrong_checksum")

        assert "mismatch" in str(exc_info.value).lower()
