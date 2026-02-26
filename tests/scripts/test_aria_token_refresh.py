from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / ".claude" / "scripts" / "aria-token-refresh.py"

spec = importlib.util.spec_from_file_location("aria_token_refresh", SCRIPT_PATH)
token_refresh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(token_refresh)


# ── get_active_pilot_id ──────────────────────────────────────────


def test_env_var_takes_priority(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARIA_PILOT", "99999")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    (tmp_path / "userdata" / "credentials").mkdir(parents=True)
    (tmp_path / "userdata" / "credentials" / "11111.json").write_text("{}", encoding="utf-8")
    (tmp_path / "userdata" / "config.json").write_text('{"active_pilot":"22222"}', encoding="utf-8")

    result = token_refresh.get_active_pilot_id(tmp_path)
    assert result == "99999"


def test_config_active_pilot_takes_priority_over_scan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ARIA_PILOT", raising=False)
    (tmp_path / "userdata" / "credentials").mkdir(parents=True)
    (tmp_path / "userdata" / "credentials" / "11111.json").write_text("{}", encoding="utf-8")
    (tmp_path / "userdata" / "config.json").write_text('{"active_pilot":"22222"}', encoding="utf-8")

    result = token_refresh.get_active_pilot_id(tmp_path)
    assert result == "22222"


def test_single_numeric_credential_file_returned(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ARIA_PILOT", raising=False)
    creds = tmp_path / "userdata" / "credentials"
    creds.mkdir(parents=True)
    (creds / "12345.json").write_text("{}", encoding="utf-8")

    result = token_refresh.get_active_pilot_id(tmp_path)
    assert result == "12345"


def test_non_numeric_credential_files_ignored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ARIA_PILOT", raising=False)
    creds = tmp_path / "userdata" / "credentials"
    creds.mkdir(parents=True)
    (creds / ".gitkeep").write_text("", encoding="utf-8")
    (creds / "backup.json").write_text("{}", encoding="utf-8")
    (creds / "notes.json").write_text("{}", encoding="utf-8")
    (creds / "12345.json").write_text("{}", encoding="utf-8")

    result = token_refresh.get_active_pilot_id(tmp_path)
    assert result == "12345"


def test_multiple_numeric_credential_files_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ARIA_PILOT", raising=False)
    creds = tmp_path / "userdata" / "credentials"
    creds.mkdir(parents=True)
    (creds / "11111.json").write_text("{}", encoding="utf-8")
    (creds / "22222.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="Multiple credential files"):
        token_refresh.get_active_pilot_id(tmp_path)


def test_unicode_digit_filename_ignored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """str.isdigit() would match Unicode digits like ½ or ²; re.fullmatch(r'[0-9]+') should not."""
    monkeypatch.delenv("ARIA_PILOT", raising=False)
    creds = tmp_path / "userdata" / "credentials"
    creds.mkdir(parents=True)
    # U+00B2 = superscript 2 — isdigit() returns True, but not ASCII [0-9]
    (creds / "\u00b2.json").write_text("{}", encoding="utf-8")
    (creds / "12345.json").write_text("{}", encoding="utf-8")

    result = token_refresh.get_active_pilot_id(tmp_path)
    assert result == "12345"


def test_empty_credentials_dir_returns_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ARIA_PILOT", raising=False)
    (tmp_path / "userdata" / "credentials").mkdir(parents=True)

    result = token_refresh.get_active_pilot_id(tmp_path)
    assert result == ""


def test_no_userdata_returns_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ARIA_PILOT", raising=False)

    result = token_refresh.get_active_pilot_id(tmp_path)
    assert result == ""


# ── find_credentials_file ────────────────────────────────────────


def test_find_credentials_specific_pilot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("ARIA_PILOT", raising=False)
    creds = tmp_path / "userdata" / "credentials"
    creds.mkdir(parents=True)
    (creds / "12345.json").write_text("{}", encoding="utf-8")

    result = token_refresh.find_credentials_file("12345")
    assert result is not None
    assert result.name == "12345.json"


def test_find_credentials_fallback_ignores_non_numeric(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("ARIA_PILOT", raising=False)
    creds = tmp_path / "userdata" / "credentials"
    creds.mkdir(parents=True)
    (creds / "backup.json").write_text("{}", encoding="utf-8")
    (creds / "99999.json").write_text("{}", encoding="utf-8")

    result = token_refresh.find_credentials_file()
    assert result is not None
    assert result.name == "99999.json"


def test_find_credentials_fallback_multiple_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("ARIA_PILOT", raising=False)
    creds = tmp_path / "userdata" / "credentials"
    creds.mkdir(parents=True)
    (creds / "11111.json").write_text("{}", encoding="utf-8")
    (creds / "22222.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="Multiple credential files"):
        token_refresh.find_credentials_file()
