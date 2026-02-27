"""Tests for auth.py credential resolution and pilot directory lookup.

Covers proposal checklist items for:
- Priority 3 credential scan filtering to ^[0-9]+.json$
- Non-numeric .json files ignored by Credentials.resolve()
- Multiple numeric credential files → CredentialsError
- get_pilot_directory() exact prefix matching
- get_pilot_directory() ambiguity fail
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from aria_esi.core.auth import Credentials, CredentialsError, get_pilot_directory

# ── Credentials.resolve() Priority 3 ────────────────────────────


def test_resolve_ignores_non_numeric_json(tmp_path: Path) -> None:
    """Non-numeric .json files (backup.json, .gitkeep) are ignored."""
    creds = tmp_path / "userdata" / "credentials"
    creds.mkdir(parents=True)
    (creds / ".gitkeep").write_text("", encoding="utf-8")
    (creds / "backup.json").write_text("{}", encoding="utf-8")
    (creds / "12345.json").write_text(
        json.dumps({
            "character_id": 12345,
            "access_token": "tok",
            "refresh_token": "ref",
            "token_expiry": "2099-01-01T00:00:00Z",
            "scopes": [],
        }),
        encoding="utf-8",
    )

    with patch.object(Credentials, "_find_project_dir", return_value=tmp_path):
        with patch("aria_esi.core.auth.is_keyring_enabled", return_value=False):
            result = Credentials.resolve(project_dir=tmp_path)

    assert result is not None
    assert str(result.character_id) == "12345"


def test_resolve_multiple_numeric_raises(tmp_path: Path) -> None:
    """Multiple numeric credential files → CredentialsError with file list."""
    creds = tmp_path / "userdata" / "credentials"
    creds.mkdir(parents=True)
    for cid in ("11111", "22222"):
        (creds / f"{cid}.json").write_text(
            json.dumps({
                "character_id": int(cid),
                "access_token": "tok",
                "refresh_token": "ref",
                "token_expiry": "2099-01-01T00:00:00Z",
                "scopes": [],
            }),
            encoding="utf-8",
        )

    with patch.object(Credentials, "_find_project_dir", return_value=tmp_path):
        with patch("aria_esi.core.auth.is_keyring_enabled", return_value=False):
            with pytest.raises(CredentialsError, match="Multiple credential files"):
                Credentials.resolve(project_dir=tmp_path)


def test_resolve_unicode_digit_ignored(tmp_path: Path) -> None:
    """Unicode digits (like ² U+00B2) should NOT match the [0-9]+ filter."""
    creds = tmp_path / "userdata" / "credentials"
    creds.mkdir(parents=True)
    (creds / "\u00b2.json").write_text("{}", encoding="utf-8")
    (creds / "12345.json").write_text(
        json.dumps({
            "character_id": 12345,
            "access_token": "tok",
            "refresh_token": "ref",
            "token_expiry": "2099-01-01T00:00:00Z",
            "scopes": [],
        }),
        encoding="utf-8",
    )

    with patch.object(Credentials, "_find_project_dir", return_value=tmp_path):
        with patch("aria_esi.core.auth.is_keyring_enabled", return_value=False):
            result = Credentials.resolve(project_dir=tmp_path)

    assert result is not None
    assert str(result.character_id) == "12345"


def test_resolve_no_credentials_returns_none(tmp_path: Path) -> None:
    creds = tmp_path / "userdata" / "credentials"
    creds.mkdir(parents=True)

    with patch.object(Credentials, "_find_project_dir", return_value=tmp_path):
        with patch("aria_esi.core.auth.is_keyring_enabled", return_value=False):
            result = Credentials.resolve(project_dir=tmp_path)

    assert result is None


# ── get_pilot_directory ──────────────────────────────────────────


def test_get_pilot_directory_exact_prefix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """get_pilot_directory() uses exact {id}_ prefix matching."""
    pilots = tmp_path / "userdata" / "pilots"
    pilots.mkdir(parents=True)
    (pilots / "12345_my_pilot").mkdir()
    config = {"active_pilot": "12345"}
    (tmp_path / "userdata" / "config.json").write_text(json.dumps(config), encoding="utf-8")

    monkeypatch.delenv("ARIA_PILOT", raising=False)

    with patch("aria_esi.core.config.get_settings") as mock_settings:
        mock_settings.return_value.pilot = None
        result = get_pilot_directory(tmp_path)

    assert result is not None
    assert result.name == "12345_my_pilot"


def test_get_pilot_directory_no_false_prefix_match(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """12345_ should not match 1234_slug (no false prefix overlap via startswith)."""
    pilots = tmp_path / "userdata" / "pilots"
    pilots.mkdir(parents=True)
    (pilots / "1234_other_pilot").mkdir()
    config = {"active_pilot": "12345"}
    (tmp_path / "userdata" / "config.json").write_text(json.dumps(config), encoding="utf-8")

    monkeypatch.delenv("ARIA_PILOT", raising=False)

    with patch("aria_esi.core.config.get_settings") as mock_settings:
        mock_settings.return_value.pilot = None
        result = get_pilot_directory(tmp_path)

    assert result is None


def test_get_pilot_directory_multiple_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Multiple {id}_* directories → CredentialsError."""
    pilots = tmp_path / "userdata" / "pilots"
    pilots.mkdir(parents=True)
    (pilots / "12345_alpha").mkdir()
    (pilots / "12345_beta").mkdir()
    config = {"active_pilot": "12345"}
    (tmp_path / "userdata" / "config.json").write_text(json.dumps(config), encoding="utf-8")

    monkeypatch.delenv("ARIA_PILOT", raising=False)

    with patch("aria_esi.core.config.get_settings") as mock_settings:
        mock_settings.return_value.pilot = None
        with pytest.raises(CredentialsError, match="Multiple pilot directories"):
            get_pilot_directory(tmp_path)
