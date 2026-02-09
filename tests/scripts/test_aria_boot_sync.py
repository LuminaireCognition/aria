from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _stage_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "ws"
    scripts_dir = workspace / ".claude" / "scripts"
    scripts_dir.mkdir(parents=True)

    shutil.copy2(REPO_ROOT / ".claude" / "scripts" / "aria-boot-sync", scripts_dir / "aria-boot-sync")
    (scripts_dir / "aria-boot-sync").chmod(0o755)

    (scripts_dir / "aria-token-refresh.py").write_text(
        "import sys\nsys.exit(0)\n",
        encoding="utf-8",
    )
    (scripts_dir / "aria-esi").write_text(
        "#!/usr/bin/env bash\n"
        "echo '{\"standings\":[{\"from_id\":500004,\"from_type\":\"faction\",\"standing\":3.0}]}'\n",
        encoding="utf-8",
    )
    (scripts_dir / "aria-esi").chmod(0o755)

    pilot_dir = workspace / "userdata" / "pilots" / "12345_test_pilot"
    pilot_dir.mkdir(parents=True)
    (workspace / "userdata" / "credentials").mkdir(parents=True)

    (workspace / "userdata" / "config.json").write_text('{"active_pilot":"12345"}\n', encoding="utf-8")
    (workspace / "userdata" / "credentials" / "12345.json").write_text("{}", encoding="utf-8")
    (pilot_dir / "profile.md").write_text(
        "### Empire Factions\n"
        "| Faction | Standing |\n"
        "|---|---|\n"
        "| Gallente Federation | 1.0 |\n",
        encoding="utf-8",
    )
    return workspace


def test_profile_path_is_passed_to_standings_parser(tmp_path: Path) -> None:
    workspace = _stage_workspace(tmp_path)
    env = os.environ.copy()
    env.setdefault("TERM", "xterm")

    result = subprocess.run(
        [str(workspace / ".claude" / "scripts" / "aria-boot-sync"), "--quiet"],
        cwd=workspace,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["changes_detected"] is True
    assert payload["change_count"] >= 1
