"""
Tests for aria_esi.commands.fitting download logic.

Tests the tag-first priority chain in download_pyfa_staticdata.
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aria_esi.commands.fitting import DownloadResult, download_pyfa_staticdata

# =============================================================================
# Helpers
# =============================================================================


def _make_staticdata(repo_dir: Path) -> None:
    """Create a fake staticdata directory so the download doesn't fail validation."""
    (repo_dir / "staticdata").mkdir(parents=True, exist_ok=True)


def _mock_subprocess_success(*args, **kwargs):
    """Default mock for subprocess.run that succeeds."""
    result = MagicMock()
    result.stdout = "abc123def456\n"
    result.returncode = 0
    return result


# =============================================================================
# Tag Clone Tests
# =============================================================================


class TestTagClone:
    """Tests for tag-based cloning (Strategy 1)."""

    @patch("aria_esi.core.data_integrity.verify_eos_commit", return_value=(True, "abc123def456"))
    @patch("aria_esi.core.data_integrity.get_pinned_eos_tag", return_value="v2.65.4")
    @patch("aria_esi.core.data_integrity.get_pinned_eos_commit", return_value="abc123def456")
    @patch("aria_esi.core.data_integrity.get_eos_repository", return_value="https://github.com/pyfa-org/Pyfa.git")
    @patch("aria_esi.core.data_integrity.is_break_glass_enabled", return_value=False)
    def test_tag_clone_success(
        self, mock_bg, mock_repo, mock_commit, mock_tag, mock_verify, tmp_path
    ):
        """Tag clone succeeds → returns pin_status='tag_pinned'."""
        repo_dir = tmp_path / "pyfa"

        def fake_run(cmd, **kwargs):
            # Create staticdata on clone
            if "clone" in cmd:
                _make_staticdata(repo_dir)
            result = MagicMock()
            result.stdout = "abc123def456\n"
            result.returncode = 0
            return result

        with patch("aria_esi.commands.fitting.subprocess.run", side_effect=fake_run):
            result = download_pyfa_staticdata(tmp_path)

        assert isinstance(result, DownloadResult)
        assert result.pin_status == "tag_pinned"
        assert result.actual_commit == "abc123def456"
        assert result.warning is None

    @patch("aria_esi.core.data_integrity.verify_eos_commit", return_value=(False, "different123"))
    @patch("aria_esi.core.data_integrity.get_pinned_eos_tag", return_value="v2.65.4")
    @patch("aria_esi.core.data_integrity.get_pinned_eos_commit", return_value="expected123")
    @patch("aria_esi.core.data_integrity.get_eos_repository", return_value="https://github.com/pyfa-org/Pyfa.git")
    @patch("aria_esi.core.data_integrity.is_break_glass_enabled", return_value=False)
    def test_tag_clone_commit_mismatch_warns(
        self, mock_bg, mock_repo, mock_commit, mock_tag, mock_verify, tmp_path
    ):
        """Tag resolves to different commit → warns but succeeds."""
        repo_dir = tmp_path / "pyfa"

        def fake_run(cmd, **kwargs):
            if "clone" in cmd:
                _make_staticdata(repo_dir)
            result = MagicMock()
            result.stdout = "different123456\n"
            result.returncode = 0
            return result

        with patch("aria_esi.commands.fitting.subprocess.run", side_effect=fake_run):
            result = download_pyfa_staticdata(tmp_path)

        assert result.pin_status == "tag_pinned"
        assert result.warning is not None
        assert "expected123" in result.warning


# =============================================================================
# Commit Fallback Tests
# =============================================================================


class TestCommitFallback:
    """Tests for commit checkout fallback (Strategy 2)."""

    @patch("aria_esi.core.data_integrity.get_pinned_eos_tag", return_value="v2.65.4")
    @patch("aria_esi.core.data_integrity.get_pinned_eos_commit", return_value="abc123def456")
    @patch("aria_esi.core.data_integrity.get_eos_repository", return_value="https://github.com/pyfa-org/Pyfa.git")
    @patch("aria_esi.core.data_integrity.is_break_glass_enabled", return_value=False)
    def test_tag_fails_commit_succeeds(self, mock_bg, mock_repo, mock_commit, mock_tag, tmp_path):
        """Tag clone fails → falls back to commit checkout."""
        repo_dir = tmp_path / "pyfa"
        call_count = 0

        def fake_run(cmd, **kwargs):
            nonlocal call_count
            call_count += 1
            # First clone (tag) fails
            if "clone" in cmd and "--branch" in cmd:
                raise subprocess.CalledProcessError(128, cmd)
            # Second clone (commit checkout) succeeds
            if "clone" in cmd:
                _make_staticdata(repo_dir)
            result = MagicMock()
            result.stdout = "abc123def456\n"
            result.returncode = 0
            return result

        with patch("aria_esi.commands.fitting.subprocess.run", side_effect=fake_run):
            result = download_pyfa_staticdata(tmp_path)

        assert result.pin_status == "commit_pinned"
        assert result.actual_commit == "abc123def456"


# =============================================================================
# HEAD Fallback Tests
# =============================================================================


class TestHeadFallback:
    """Tests for HEAD fallback (Strategy 3)."""

    @patch("aria_esi.core.data_integrity.get_pinned_eos_tag", return_value="v2.65.4")
    @patch("aria_esi.core.data_integrity.get_pinned_eos_commit", return_value="abc123def456")
    @patch("aria_esi.core.data_integrity.get_eos_repository", return_value="https://github.com/pyfa-org/Pyfa.git")
    @patch("aria_esi.core.data_integrity.is_break_glass_enabled", return_value=False)
    def test_both_fail_head_fallback(self, mock_bg, mock_repo, mock_commit, mock_tag, tmp_path):
        """Both tag and commit fail → falls back to HEAD with warning."""
        repo_dir = tmp_path / "pyfa"
        clone_attempts = 0

        def fake_run(cmd, **kwargs):
            nonlocal clone_attempts
            if "clone" in cmd:
                clone_attempts += 1
                # First two clone attempts fail (tag + commit)
                if clone_attempts <= 2:
                    raise subprocess.CalledProcessError(128, cmd)
                # Third clone (HEAD) succeeds
                _make_staticdata(repo_dir)
            # checkout fails for commit
            if "checkout" in cmd:
                raise subprocess.CalledProcessError(128, cmd)
            result = MagicMock()
            result.stdout = "head123456\n"
            result.returncode = 0
            return result

        with patch("aria_esi.commands.fitting.subprocess.run", side_effect=fake_run):
            result = download_pyfa_staticdata(tmp_path)

        assert result.pin_status == "head_fallback"
        assert result.warning is not None
        assert "HEAD" in result.warning or "unavailable" in result.warning

    @patch("aria_esi.core.data_integrity.get_pinned_eos_tag", return_value="v2.65.4")
    @patch("aria_esi.core.data_integrity.get_pinned_eos_commit", return_value="abc123def456")
    @patch("aria_esi.core.data_integrity.get_eos_repository", return_value="https://github.com/pyfa-org/Pyfa.git")
    @patch("aria_esi.core.data_integrity.is_break_glass_enabled", return_value=False)
    def test_strict_pin_prevents_head_fallback(
        self, mock_bg, mock_repo, mock_commit, mock_tag, tmp_path
    ):
        """strict_pin=True raises instead of falling back to HEAD."""
        clone_attempts = 0

        def fake_run(cmd, **kwargs):
            nonlocal clone_attempts
            if "clone" in cmd:
                clone_attempts += 1
                raise subprocess.CalledProcessError(128, cmd)
            if "checkout" in cmd:
                raise subprocess.CalledProcessError(128, cmd)
            result = MagicMock()
            result.stdout = ""
            result.returncode = 0
            return result

        with patch("aria_esi.commands.fitting.subprocess.run", side_effect=fake_run):
            with pytest.raises(RuntimeError, match="strict-pin"):
                download_pyfa_staticdata(tmp_path, strict_pin=True)


# =============================================================================
# Break-Glass Tests
# =============================================================================


class TestBreakGlass:
    """Tests for break-glass mode."""

    @patch("aria_esi.core.data_integrity.get_pinned_eos_tag", return_value="v2.65.4")
    @patch("aria_esi.core.data_integrity.get_pinned_eos_commit", return_value="abc123def456")
    @patch("aria_esi.core.data_integrity.get_eos_repository", return_value="https://github.com/pyfa-org/Pyfa.git")
    @patch("aria_esi.core.data_integrity.is_break_glass_enabled", return_value=False)
    def test_break_glass_skips_to_head(self, mock_bg, mock_repo, mock_commit, mock_tag, tmp_path):
        """break_glass=True skips directly to HEAD clone."""
        repo_dir = tmp_path / "pyfa"

        def fake_run(cmd, **kwargs):
            if "clone" in cmd:
                # Should be a shallow HEAD clone (--depth=1, no --branch)
                assert "--branch" not in cmd
                _make_staticdata(repo_dir)
            result = MagicMock()
            result.stdout = "head123456\n"
            result.returncode = 0
            return result

        with patch("aria_esi.commands.fitting.subprocess.run", side_effect=fake_run):
            result = download_pyfa_staticdata(tmp_path, break_glass=True)

        assert result.pin_status == "head_fallback"


# =============================================================================
# No Pin Configured Tests
# =============================================================================


class TestNoPinConfigured:
    """Tests when no tag or commit is configured."""

    @patch("aria_esi.core.data_integrity.get_pinned_eos_tag", return_value=None)
    @patch("aria_esi.core.data_integrity.get_pinned_eos_commit", return_value=None)
    @patch("aria_esi.core.data_integrity.get_eos_repository", return_value="https://github.com/pyfa-org/Pyfa.git")
    @patch("aria_esi.core.data_integrity.is_break_glass_enabled", return_value=False)
    def test_no_pin_falls_to_head(self, mock_bg, mock_repo, mock_commit, mock_tag, tmp_path):
        """No tag or commit configured → HEAD fallback."""
        repo_dir = tmp_path / "pyfa"

        def fake_run(cmd, **kwargs):
            if "clone" in cmd:
                _make_staticdata(repo_dir)
            result = MagicMock()
            result.stdout = "head123456\n"
            result.returncode = 0
            return result

        with patch("aria_esi.commands.fitting.subprocess.run", side_effect=fake_run):
            result = download_pyfa_staticdata(tmp_path)

        assert result.pin_status == "head_fallback"

    @patch("aria_esi.core.data_integrity.get_pinned_eos_tag", return_value=None)
    @patch("aria_esi.core.data_integrity.get_pinned_eos_commit", return_value=None)
    @patch("aria_esi.core.data_integrity.get_eos_repository", return_value="https://github.com/pyfa-org/Pyfa.git")
    @patch("aria_esi.core.data_integrity.is_break_glass_enabled", return_value=False)
    def test_strict_pin_no_config_raises(self, mock_bg, mock_repo, mock_commit, mock_tag, tmp_path):
        """strict_pin=True with no config raises immediately."""
        with patch("aria_esi.commands.fitting.subprocess.run"):
            with pytest.raises(RuntimeError, match="strict-pin"):
                download_pyfa_staticdata(tmp_path, strict_pin=True)
