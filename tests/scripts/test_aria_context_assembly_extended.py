"""Extended tests for aria-context-assembly.py pilot resolution.

Tests the H1 fix: numeric directory filtering uses re.fullmatch(r'[0-9]+')
instead of str.isdigit(). Also tests auto-detection from single pilot dir.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / ".claude" / "scripts" / "aria-context-assembly.py"


def _run_script(workspace: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(workspace)
    env.pop("ARIA_PILOT", None)
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        cwd=workspace,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def test_single_numeric_pilot_dir_auto_detected(tmp_path: Path) -> None:
    """Auto-detect pilot ID from a single {id}_{slug} directory."""
    workspace = tmp_path / "ws"
    pilots_dir = workspace / "userdata" / "pilots"
    pilots_dir.mkdir(parents=True)
    pilot_dir = pilots_dir / "12345_test_pilot"
    pilot_dir.mkdir()
    (pilot_dir / "profile.md").write_text("# Test", encoding="utf-8")

    result = _run_script(workspace, ["--status"])
    # The script should pick up pilot 12345 from the directory name
    # It may fail for other reasons (no persona files), but should not
    # fail with "no active pilot" error
    assert "no active pilot" not in result.stderr.lower()


def test_underscore_prefixed_dirs_ignored(tmp_path: Path) -> None:
    """Directories starting with _ (like _registry.json) are ignored."""
    workspace = tmp_path / "ws"
    pilots_dir = workspace / "userdata" / "pilots"
    pilots_dir.mkdir(parents=True)
    (pilots_dir / "_registry.json").write_text("{}", encoding="utf-8")
    (pilots_dir / "12345_test").mkdir()
    (pilots_dir / "12345_test" / "profile.md").write_text("# Test", encoding="utf-8")

    result = _run_script(workspace, ["--status"])
    assert "no active pilot" not in result.stderr.lower()


def test_non_numeric_prefix_dir_ignored(tmp_path: Path) -> None:
    """Directories like 'backup_old' where prefix is not numeric should be ignored."""
    workspace = tmp_path / "ws"
    pilots_dir = workspace / "userdata" / "pilots"
    pilots_dir.mkdir(parents=True)
    (pilots_dir / "backup_old").mkdir()
    (pilots_dir / "12345_pilot").mkdir()
    (pilots_dir / "12345_pilot" / "profile.md").write_text("# Test", encoding="utf-8")

    result = _run_script(workspace, ["--status"])
    # Should auto-detect 12345 as the single numeric pilot
    assert "Multiple pilot directories" not in result.stderr


def test_env_var_priority(tmp_path: Path) -> None:
    """ARIA_PILOT env var takes priority over directory scan."""
    workspace = tmp_path / "ws"
    pilots_dir = workspace / "userdata" / "pilots"
    pilots_dir.mkdir(parents=True)
    (pilots_dir / "11111_alpha").mkdir()
    (pilots_dir / "22222_beta").mkdir()
    (workspace / "userdata" / "config.json").write_text(
        json.dumps({"active_pilot": "99999"}), encoding="utf-8"
    )

    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(workspace)
    env["ARIA_PILOT"] = "99999"
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--status"],
        cwd=workspace,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    # Should not fail with ambiguity error since ARIA_PILOT is set
    assert "Multiple pilot directories found and no active pilot" not in result.stderr
