"""Tests for .claude/scripts/aria-data-freshness.py.

Tests resolve_active_pilot() via importlib (Python script, not bash).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / ".claude" / "scripts" / "aria-data-freshness.py"

spec = importlib.util.spec_from_file_location("aria_data_freshness", SCRIPT_PATH)
data_freshness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(data_freshness)


# ── resolve_active_pilot ─────────────────────────────────────────


def test_resolve_returns_id_and_directory(tmp_path: Path) -> None:
    (tmp_path / "userdata").mkdir()
    (tmp_path / "userdata" / "config.json").write_text(
        json.dumps({"active_pilot": "12345"}), encoding="utf-8"
    )
    pilots_dir = tmp_path / "userdata" / "pilots"
    pilots_dir.mkdir()
    (pilots_dir / "_registry.json").write_text(
        json.dumps({"pilots": [{"character_id": 12345, "directory": "12345_test_pilot"}]}),
        encoding="utf-8",
    )

    char_id, pilot_dir = data_freshness.resolve_active_pilot(tmp_path)
    assert char_id == "12345"
    assert pilot_dir == tmp_path / "userdata" / "pilots" / "12345_test_pilot"


def test_missing_config_returns_none(tmp_path: Path) -> None:
    char_id, directory = data_freshness.resolve_active_pilot(tmp_path)
    assert char_id is None
    assert directory is None


def test_config_exists_but_pilot_not_in_registry(tmp_path: Path) -> None:
    (tmp_path / "userdata").mkdir()
    (tmp_path / "userdata" / "config.json").write_text(
        json.dumps({"active_pilot": "99999"}), encoding="utf-8"
    )
    pilots_dir = tmp_path / "userdata" / "pilots"
    pilots_dir.mkdir()
    (pilots_dir / "_registry.json").write_text(
        json.dumps({"pilots": [{"character_id": 12345, "directory": "12345_other"}]}),
        encoding="utf-8",
    )

    char_id, directory = data_freshness.resolve_active_pilot(tmp_path)
    assert char_id == "99999"
    assert directory is None


def test_corrupt_config_returns_none(tmp_path: Path) -> None:
    (tmp_path / "userdata").mkdir()
    (tmp_path / "userdata" / "config.json").write_text(
        "{not valid json", encoding="utf-8"
    )

    char_id, directory = data_freshness.resolve_active_pilot(tmp_path)
    assert char_id is None
    assert directory is None
