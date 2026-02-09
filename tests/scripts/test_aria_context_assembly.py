from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


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


def test_main_handles_active_pilot_ambiguity_without_traceback(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    pilots_dir = workspace / "userdata" / "pilots"
    pilots_dir.mkdir(parents=True)
    (pilots_dir / "1001_alpha").mkdir()
    (pilots_dir / "1002_beta").mkdir()

    result = _run_script(workspace, [])

    assert result.returncode == 1
    assert "Multiple pilot directories found and no active pilot selected" in result.stderr
    assert "Traceback" not in result.stderr


def test_status_handles_pilot_directory_ambiguity_without_traceback(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    pilots_dir = workspace / "userdata" / "pilots"
    pilots_dir.mkdir(parents=True)
    (workspace / "userdata" / "config.json").write_text(
        json.dumps({"active_pilot": "12345"}),
        encoding="utf-8",
    )
    (pilots_dir / "12345_alpha").mkdir()
    (pilots_dir / "12345_old").mkdir()

    result = _run_script(workspace, ["--status"])

    assert result.returncode == 1
    assert "Multiple pilot directories found for 12345" in result.stderr
    assert "Traceback" not in result.stderr
