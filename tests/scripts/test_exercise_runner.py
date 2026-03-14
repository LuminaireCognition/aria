"""Tests for exercise runner pre-flight checks, git state, and brevity."""

from __future__ import annotations

import importlib
import logging
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import exercise-runner.py (hyphenated filename requires importlib)
_runner_path = Path(__file__).resolve().parent.parent.parent / "dev" / "scripts" / "exercise-runner.py"
_spec = importlib.util.spec_from_file_location("exercise_runner", _runner_path)
exercise_runner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(exercise_runner)
preflight_checks = exercise_runner.preflight_checks
_git_state_snapshot = exercise_runner._git_state_snapshot
_check_git_state = exercise_runner._check_git_state
_check_brevity = exercise_runner._check_brevity
quality_check = exercise_runner.quality_check


class TestPreflightChecks:
    """Test pre-flight check warnings."""

    @patch.object(exercise_runner, "subprocess")
    @patch.object(exercise_runner, "Path")
    def test_preflight_failed_migrate_warns(self, mock_path_cls, mock_subprocess):
        """Failed db-migrate should produce a warning."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "migration error"
        mock_subprocess.run.return_value = mock_result

        mock_ref_dir = MagicMock()
        mock_ref_dir.is_dir.return_value = False
        mock_graph = MagicMock()
        mock_graph.is_file.return_value = True

        def path_side_effect(arg):
            if arg == "reference":
                return mock_ref_dir
            if arg == "src/aria_esi/data/universe.universe":
                return mock_graph
            return MagicMock()

        mock_path_cls.side_effect = path_side_effect

        warnings = preflight_checks()
        assert any("db-migrate failed" in w for w in warnings)

    @patch.object(exercise_runner, "subprocess")
    def test_preflight_stale_reference_warns(self, mock_subprocess, tmp_path):
        """Stale reference files should produce a warning."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess.run.return_value = mock_result

        # Create a stale reference file
        ref_dir = tmp_path / "reference"
        ref_dir.mkdir()
        stale_file = ref_dir / "test.json"
        stale_file.write_text("{}")
        old_time = time.time() - (60 * 86400)
        import os
        os.utime(stale_file, (old_time, old_time))

        # Create universe graph
        graph_dir = tmp_path / "src" / "aria_esi" / "data"
        graph_dir.mkdir(parents=True)
        (graph_dir / "universe.universe").write_text("")

        with patch.object(exercise_runner, "Path") as mock_path_cls:
            def path_side_effect(arg):
                if arg == "reference":
                    return ref_dir
                if arg == "src/aria_esi/data/universe.universe":
                    return graph_dir / "universe.universe"
                return Path(arg)

            mock_path_cls.side_effect = path_side_effect

            warnings = preflight_checks()
            assert any("reference files older than 30 days" in w for w in warnings)

    @patch.object(exercise_runner, "subprocess")
    @patch.object(exercise_runner, "Path")
    def test_preflight_missing_graph_warns(self, mock_path_cls, mock_subprocess):
        """Missing universe graph should produce a warning."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess.run.return_value = mock_result

        mock_ref_dir = MagicMock()
        mock_ref_dir.is_dir.return_value = False
        mock_graph = MagicMock()
        mock_graph.is_file.return_value = False

        def path_side_effect(arg):
            if arg == "reference":
                return mock_ref_dir
            if arg == "src/aria_esi/data/universe.universe":
                return mock_graph
            return MagicMock()

        mock_path_cls.side_effect = path_side_effect

        warnings = preflight_checks()
        assert any("Universe graph not found" in w for w in warnings)


class TestGitStateAssertions:
    """Test git state snapshot and dirty detection."""

    @patch.object(exercise_runner, "subprocess")
    def test_git_state_snapshot_returns_porcelain(self, mock_subprocess):
        """Snapshot returns stdout from git status --porcelain."""
        mock_result = MagicMock()
        mock_result.stdout = " M file.py\n?? new.txt\n"
        mock_subprocess.run.return_value = mock_result
        result = _git_state_snapshot()
        assert result == " M file.py\n?? new.txt\n"

    @patch.object(exercise_runner, "subprocess")
    def test_check_git_state_clean(self, mock_subprocess):
        """Same baseline and current state returns None."""
        baseline = " M file.py\n"
        mock_result = MagicMock()
        mock_result.stdout = " M file.py\n"
        mock_subprocess.run.return_value = mock_result
        assert _check_git_state("test-q1", baseline) is None

    @patch.object(exercise_runner, "subprocess")
    def test_check_git_state_dirty(self, mock_subprocess, caplog):
        """Different state returns 'git-dirty' and logs warning."""
        baseline = " M file.py\n"
        mock_result = MagicMock()
        mock_result.stdout = " M file.py\n M other.py\n"
        mock_subprocess.run.return_value = mock_result
        with caplog.at_level(logging.WARNING):
            result = _check_git_state("build-cost-q1", baseline)
        assert result == "git-dirty"
        assert "build-cost-q1" in caplog.text

    @patch.object(exercise_runner, "subprocess")
    def test_git_state_snapshot_git_failure(self, mock_subprocess):
        """Non-zero git exit raises CalledProcessError."""
        mock_subprocess.run.side_effect = subprocess.CalledProcessError(
            128, ["git", "status", "--porcelain"]
        )
        with pytest.raises(subprocess.CalledProcessError):
            _git_state_snapshot()

    @patch.object(exercise_runner, "subprocess")
    def test_check_git_state_subprocess_error(self, mock_subprocess):
        """OSError from subprocess propagates."""
        mock_subprocess.run.side_effect = OSError("no such file")
        with pytest.raises(OSError):
            _check_git_state("test-q1", "")


class TestBrevityChecks:
    """Test brevity cap enforcement."""

    def test_check_brevity_under_limit(self):
        """25 lines, non-exempt skill returns None."""
        assert _check_brevity("price-q1", 25) is None

    def test_check_brevity_over_limit(self):
        """35 lines, non-exempt skill returns 'verbose'."""
        assert _check_brevity("build-cost-q1", 35) == "verbose"

    def test_check_brevity_exempt_skill(self):
        """Exempt skill (help) returns None regardless of line count."""
        assert _check_brevity("help-q1", 60) is None

    def test_check_brevity_no_q_suffix(self):
        """Label without -q suffix is not incorrectly exempt."""
        assert _check_brevity("standalone", 35) == "verbose"

    def test_quality_check_brevity_integration(self):
        """End-to-end: quality_check flags verbose responses."""
        body = "\n".join(f"line {i}" for i in range(35))
        query = {"skill": "build-cost", "query_num": 1, "query_text": "test"}
        flags = quality_check(
            tool_calls=[],
            body=body,
            query=query,
            explicit=False,
        )
        assert "verbose" in flags
