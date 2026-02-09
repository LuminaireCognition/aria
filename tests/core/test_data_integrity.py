"""
Tests for data integrity verification.

Security: These tests verify the checksum verification logic that protects
against RCE from tampered pickle files. See dev/reviews/SECURITY_000.md #3.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aria_esi.core.data_integrity import (
    IntegrityError,
    compute_sha256,
    get_universe_graph_checksum,
    verify_universe_graph_integrity,
)


class TestComputeSha256:
    """Test SHA256 computation."""

    def test_computes_hash(self, tmp_path: Path):
        """Computes correct SHA256 for known content."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")

        result = compute_sha256(test_file)

        # Known SHA256 for "hello world"
        assert result == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"

    def test_different_content_different_hash(self, tmp_path: Path):
        """Different content produces different hash."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("content1")
        file2.write_text("content2")

        assert compute_sha256(file1) != compute_sha256(file2)

    def test_same_content_same_hash(self, tmp_path: Path):
        """Same content in different files produces same hash."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("identical")
        file2.write_text("identical")

        assert compute_sha256(file1) == compute_sha256(file2)

    def test_binary_file(self, tmp_path: Path):
        """Handles binary files correctly."""
        binary_file = tmp_path / "test.bin"
        binary_file.write_bytes(b"\x00\x01\x02\x03\xff\xfe\xfd")

        result = compute_sha256(binary_file)
        assert len(result) == 64  # SHA256 hex is 64 chars


class TestVerifyUniverseGraphIntegrity:
    """Test universe graph integrity verification."""

    def test_passes_with_correct_checksum(self, tmp_path: Path):
        """Verification passes when checksum matches."""
        test_file = tmp_path / "test.pkl"
        test_file.write_bytes(b"test content")

        expected = compute_sha256(test_file)
        success, actual = verify_universe_graph_integrity(test_file, expected_checksum=expected)

        assert success is True
        assert actual == expected

    def test_fails_with_wrong_checksum(self, tmp_path: Path):
        """Verification fails when checksum doesn't match."""
        test_file = tmp_path / "test.pkl"
        test_file.write_bytes(b"test content")

        wrong_checksum = "a" * 64

        with pytest.raises(IntegrityError) as exc_info:
            verify_universe_graph_integrity(test_file, expected_checksum=wrong_checksum)

        assert "checksum mismatch" in str(exc_info.value).lower()
        assert exc_info.value.expected == wrong_checksum
        assert exc_info.value.actual is not None

    def test_error_includes_bypass_instructions(self, tmp_path: Path):
        """Error message includes break-glass instructions."""
        test_file = tmp_path / "test.pkl"
        test_file.write_bytes(b"test content")

        with pytest.raises(IntegrityError) as exc_info:
            verify_universe_graph_integrity(test_file, expected_checksum="a" * 64)

        error_msg = str(exc_info.value)
        assert "ARIA_ALLOW_UNPINNED" in error_msg

    def test_break_glass_bypasses_verification(self, tmp_path: Path):
        """Break-glass mode skips verification."""
        test_file = tmp_path / "test.pkl"
        test_file.write_bytes(b"test content")

        # With break_glass=True, even wrong checksum passes
        success, _ = verify_universe_graph_integrity(
            test_file, expected_checksum="a" * 64, break_glass=True
        )

        assert success is True

    def test_passes_with_no_checksum_configured(self, tmp_path: Path, monkeypatch):
        """Verification passes with warning when no checksum is configured."""
        test_file = tmp_path / "test.pkl"
        test_file.write_bytes(b"test content")

        # Create a manifest without checksum to simulate unconfigured state
        manifest = {
            "schema_version": 1,
            "sources": {"universe_graph": {"sha256": None}},
        }
        manifest_path = tmp_path / "data-sources.json"
        manifest_path.write_text(json.dumps(manifest))

        from aria_esi.core import data_integrity

        monkeypatch.setattr(data_integrity, "MANIFEST_PATH", manifest_path)

        # With no checksum in manifest, verification should pass with warning
        success, actual = verify_universe_graph_integrity(test_file)

        assert success is True
        assert len(actual) == 64  # Still computed the hash

    def test_case_insensitive_checksum_comparison(self, tmp_path: Path):
        """Checksum comparison is case-insensitive."""
        test_file = tmp_path / "test.pkl"
        test_file.write_bytes(b"test content")

        actual = compute_sha256(test_file)

        # Upper case should work
        success, _ = verify_universe_graph_integrity(
            test_file, expected_checksum=actual.upper()
        )
        assert success is True

        # Mixed case should work
        success, _ = verify_universe_graph_integrity(
            test_file, expected_checksum=actual.swapcase()
        )
        assert success is True


class TestIntegrityError:
    """Test IntegrityError exception."""

    def test_stores_expected_and_actual(self):
        """IntegrityError stores expected and actual values."""
        error = IntegrityError("test", expected="abc", actual="xyz")

        assert error.expected == "abc"
        assert error.actual == "xyz"

    def test_str_returns_message(self):
        """str() returns the message."""
        error = IntegrityError("Custom message")
        assert str(error) == "Custom message"


class TestGetUniverseGraphChecksum:
    """Test manifest checksum retrieval."""

    def test_returns_none_when_not_configured(self, tmp_path: Path, monkeypatch):
        """Returns None when no checksum is in manifest."""
        # Create a manifest without universe_graph checksum
        manifest = {
            "schema_version": 1,
            "sources": {"universe_graph": {"sha256": None}},
        }
        manifest_path = tmp_path / "data-sources.json"
        manifest_path.write_text(json.dumps(manifest))

        from aria_esi.core import data_integrity

        monkeypatch.setattr(data_integrity, "MANIFEST_PATH", manifest_path)

        result = get_universe_graph_checksum()
        assert result is None

    def test_returns_checksum_when_configured(self, tmp_path: Path, monkeypatch):
        """Returns checksum when configured in manifest."""
        expected_checksum = "abc123" * 10 + "abcd"  # 64 chars
        manifest = {
            "schema_version": 1,
            "sources": {"universe_graph": {"sha256": expected_checksum}},
        }
        manifest_path = tmp_path / "data-sources.json"
        manifest_path.write_text(json.dumps(manifest))

        from aria_esi.core import data_integrity

        monkeypatch.setattr(data_integrity, "MANIFEST_PATH", manifest_path)

        result = get_universe_graph_checksum()
        assert result == expected_checksum
