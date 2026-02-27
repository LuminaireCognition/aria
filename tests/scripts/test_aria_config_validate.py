"""Tests for .claude/scripts/aria-config-validate.

Subprocess-based tests for the bash configuration validation script.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / ".claude" / "scripts" / "aria-config-validate"


def _run_validate(
    workspace: Path,
    *,
    output_format: str = "json",
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(workspace)
    env.pop("ARIA_PILOT", None)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(SCRIPT_PATH), output_format],
        cwd=workspace,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def _setup_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "ws"
    (workspace / "userdata" / "pilots").mkdir(parents=True)
    return workspace


# ── Single pilot directory → validates successfully ────────────────


def test_single_pilot_dir_validates(tmp_path: Path) -> None:
    workspace = _setup_workspace(tmp_path)
    pilot_dir = workspace / "userdata" / "pilots" / "12345_test_pilot"
    pilot_dir.mkdir()
    (pilot_dir / "profile.md").write_text(
        "# Pilot Profile\n\nCharacter Name: Test Pilot\nPrimary Faction: Gallente\n",
        encoding="utf-8",
    )
    (pilot_dir / "operations.md").write_text("# Operations\n", encoding="utf-8")

    result = _run_validate(workspace)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    data = json.loads(result.stdout)
    assert data["valid"] is True


# ── Multiple pilot directories without selector → error ───────────


def test_multiple_pilot_dirs_exits_error(tmp_path: Path) -> None:
    workspace = _setup_workspace(tmp_path)
    (workspace / "userdata" / "pilots" / "1001_alpha").mkdir()
    (workspace / "userdata" / "pilots" / "1002_beta").mkdir()

    result = _run_validate(workspace)
    assert result.returncode != 0
    assert "Multiple pilot directories" in result.stderr


# ── Placeholder 0_* directory excluded from fallback ──────────────


def test_placeholder_dir_excluded(tmp_path: Path) -> None:
    """A 0_placeholder directory should not be counted as a real pilot dir."""
    workspace = _setup_workspace(tmp_path)
    (workspace / "userdata" / "pilots" / "0_placeholder").mkdir()
    pilot_dir = workspace / "userdata" / "pilots" / "12345_real_pilot"
    pilot_dir.mkdir()
    (pilot_dir / "profile.md").write_text(
        "# Pilot Profile\n\nCharacter Name: Real Pilot\nPrimary Faction: Gallente\n",
        encoding="utf-8",
    )
    (pilot_dir / "operations.md").write_text("# Operations\n", encoding="utf-8")

    result = _run_validate(workspace)
    # Should succeed because 0_placeholder is ignored and only one real dir remains
    assert result.returncode == 0, f"stderr: {result.stderr}"
    data = json.loads(result.stdout)
    assert data["valid"] is True


# ── ARIA_PILOT env var selects correct directory ──────────────────


def test_aria_pilot_env_selects_directory(tmp_path: Path) -> None:
    workspace = _setup_workspace(tmp_path)
    (workspace / "userdata" / "pilots" / "1001_alpha").mkdir()
    pilot_dir = workspace / "userdata" / "pilots" / "1002_beta"
    pilot_dir.mkdir()
    (pilot_dir / "profile.md").write_text(
        "# Pilot Profile\n\nCharacter Name: Beta Pilot\nPrimary Faction: Caldari\n",
        encoding="utf-8",
    )
    (pilot_dir / "operations.md").write_text("# Operations\n", encoding="utf-8")

    result = _run_validate(workspace, extra_env={"ARIA_PILOT": "1002"})
    assert result.returncode == 0, f"stderr: {result.stderr}"
    data = json.loads(result.stdout)
    assert data["valid"] is True
