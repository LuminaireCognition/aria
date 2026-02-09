from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / ".claude" / "scripts" / "aria-esi-sync.py"

spec = importlib.util.spec_from_file_location("aria_esi_sync", SCRIPT_PATH)
esi_sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(esi_sync)


# ── get_active_pilot_id ──────────────────────────────────────────


def test_env_var_takes_priority(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARIA_PILOT", "99999")
    (tmp_path / "userdata" / "credentials").mkdir(parents=True)
    (tmp_path / "userdata" / "credentials" / "11111.json").write_text("{}", encoding="utf-8")
    (tmp_path / "userdata" / "config.json").write_text('{"active_pilot":"22222"}', encoding="utf-8")

    result = esi_sync.get_active_pilot_id(tmp_path)
    assert result == "99999"


def test_config_takes_priority_over_scan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ARIA_PILOT", raising=False)
    (tmp_path / "userdata" / "credentials").mkdir(parents=True)
    (tmp_path / "userdata" / "credentials" / "11111.json").write_text("{}", encoding="utf-8")
    (tmp_path / "userdata" / "config.json").write_text(
        json.dumps({"active_pilot": "22222"}), encoding="utf-8"
    )

    result = esi_sync.get_active_pilot_id(tmp_path)
    assert result == "22222"


def test_single_numeric_credential_returned(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ARIA_PILOT", raising=False)
    creds = tmp_path / "userdata" / "credentials"
    creds.mkdir(parents=True)
    (creds / "12345.json").write_text("{}", encoding="utf-8")

    result = esi_sync.get_active_pilot_id(tmp_path)
    assert result == "12345"


def test_non_numeric_credential_files_ignored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ARIA_PILOT", raising=False)
    creds = tmp_path / "userdata" / "credentials"
    creds.mkdir(parents=True)
    (creds / ".gitkeep").write_text("", encoding="utf-8")
    (creds / "backup.json").write_text("{}", encoding="utf-8")
    (creds / "67890.json").write_text("{}", encoding="utf-8")

    result = esi_sync.get_active_pilot_id(tmp_path)
    assert result == "67890"


def test_multiple_numeric_credential_files_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ARIA_PILOT", raising=False)
    creds = tmp_path / "userdata" / "credentials"
    creds.mkdir(parents=True)
    (creds / "11111.json").write_text("{}", encoding="utf-8")
    (creds / "22222.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="Multiple credential files"):
        esi_sync.get_active_pilot_id(tmp_path)


def test_unicode_digit_filename_ignored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ARIA_PILOT", raising=False)
    creds = tmp_path / "userdata" / "credentials"
    creds.mkdir(parents=True)
    (creds / "\u00b2.json").write_text("{}", encoding="utf-8")
    (creds / "12345.json").write_text("{}", encoding="utf-8")

    result = esi_sync.get_active_pilot_id(tmp_path)
    assert result == "12345"


# ── find_pilot_directory ─────────────────────────────────────────


def test_find_pilot_directory_exact_prefix(tmp_path: Path) -> None:
    pilots = tmp_path / "userdata" / "pilots"
    pilots.mkdir(parents=True)
    (pilots / "12345_my_pilot").mkdir()

    result = esi_sync.find_pilot_directory(tmp_path, "12345")
    assert result is not None
    assert result.name == "12345_my_pilot"


def test_find_pilot_directory_no_false_prefix_match(tmp_path: Path) -> None:
    """Ensure 1234 doesn't match 12345_slug (glob pattern is {pilot_id}_*)."""
    pilots = tmp_path / "userdata" / "pilots"
    pilots.mkdir(parents=True)
    (pilots / "12345_my_pilot").mkdir()

    result = esi_sync.find_pilot_directory(tmp_path, "1234")
    assert result is None


def test_find_pilot_directory_multiple_raises(tmp_path: Path) -> None:
    pilots = tmp_path / "userdata" / "pilots"
    pilots.mkdir(parents=True)
    (pilots / "12345_alpha").mkdir()
    (pilots / "12345_beta").mkdir()

    with pytest.raises(ValueError, match="Multiple pilot directories found"):
        esi_sync.find_pilot_directory(tmp_path, "12345")


def test_find_pilot_directory_missing_dir_returns_none(tmp_path: Path) -> None:
    pilots = tmp_path / "userdata" / "pilots"
    pilots.mkdir(parents=True)

    result = esi_sync.find_pilot_directory(tmp_path, "12345")
    assert result is None


def test_find_pilot_directory_no_pilots_dir_returns_none(tmp_path: Path) -> None:
    result = esi_sync.find_pilot_directory(tmp_path, "12345")
    assert result is None
