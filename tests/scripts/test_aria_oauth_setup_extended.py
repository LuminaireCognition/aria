"""Extended tests for aria-oauth-setup.py per proposal test matrix.

Covers: pilot_slug(), resolve_pilot_directory() (placeholder adoption,
collision, force), _acquire_lock(), _atomic_write_json(),
update_pilot_registry(), update_config().
"""

from __future__ import annotations

import errno
import importlib.util
import json
import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / ".claude" / "scripts" / "aria-oauth-setup.py"

spec = importlib.util.spec_from_file_location("aria_oauth_setup", SCRIPT_PATH)
oauth_setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oauth_setup)


# ── pilot_slug ───────────────────────────────────────────────────


SLUG_VECTORS = [
    ("Simple Name", "simple_name"),
    ("  spaces  ", "__spaces__"),
    ("UPPER CASE", "upper_case"),
    ("Ünîcödé Nàmé", "ncd_nm"),
    ("a" * 100, "a" * 32),
    ("", "pilot"),
    ("!!!@@@###", "pilot"),
    ("test-pilot_v2", "testpilot_v2"),
    ("12345", "12345"),
    ("日本語パイロット", "pilot"),
]


@pytest.mark.parametrize("input_name,expected_slug", SLUG_VECTORS, ids=[v[0][:20] or "(empty)" for v in SLUG_VECTORS])
def test_pilot_slug(input_name: str, expected_slug: str) -> None:
    assert oauth_setup.pilot_slug(input_name) == expected_slug


def test_pilot_slug_none_returns_pilot() -> None:
    assert oauth_setup.pilot_slug(None) == "pilot"


# ── resolve_pilot_directory: placeholder adoption ────────────────


def test_placeholder_adoption_empty_directory(tmp_path: Path) -> None:
    """Empty 0_slug placeholder is adopted without prompt."""
    pilots = tmp_path / "userdata" / "pilots"
    pilots.mkdir(parents=True)
    (pilots / "0_test_slug").mkdir()

    result = oauth_setup.resolve_pilot_directory(tmp_path, 12345, "Test Pilot")
    assert result == "12345_test_slug"
    assert (pilots / "12345_test_slug").is_dir()
    assert not (pilots / "0_test_slug").exists()


def test_placeholder_adoption_preserves_slug(tmp_path: Path) -> None:
    """Slug from placeholder directory is preserved, not regenerated."""
    pilots = tmp_path / "userdata" / "pilots"
    pilots.mkdir(parents=True)
    (pilots / "0_original_slug").mkdir()

    result = oauth_setup.resolve_pilot_directory(tmp_path, 55555, "Different Name")
    assert result == "55555_original_slug"


def test_placeholder_adoption_collision_raises(tmp_path: Path) -> None:
    """Cannot adopt if target directory already exists."""
    pilots = tmp_path / "userdata" / "pilots"
    pilots.mkdir(parents=True)
    (pilots / "0_myslug").mkdir()
    (pilots / "12345_myslug").mkdir()

    with pytest.raises(RuntimeError, match="Target directory already exists"):
        oauth_setup.resolve_pilot_directory(tmp_path, 12345, "Test Pilot")


def test_placeholder_multiple_raises(tmp_path: Path) -> None:
    """Multiple 0_* placeholders → fail with explicit error."""
    pilots = tmp_path / "userdata" / "pilots"
    pilots.mkdir(parents=True)
    (pilots / "0_alpha").mkdir()
    (pilots / "0_beta").mkdir()

    with pytest.raises(RuntimeError, match="Multiple placeholder directories"):
        oauth_setup.resolve_pilot_directory(tmp_path, 12345, "Test Pilot")


def test_placeholder_populated_needs_force(tmp_path: Path) -> None:
    """Populated placeholder prompts for confirmation; force skips it."""
    pilots = tmp_path / "userdata" / "pilots"
    pilots.mkdir(parents=True)
    placeholder = pilots / "0_existing"
    placeholder.mkdir()
    (placeholder / "profile.md").write_text("# Profile", encoding="utf-8")

    # Without force, user input "n" → abort
    with patch("builtins.input", return_value="n"):
        with pytest.raises(RuntimeError, match="Aborted placeholder adoption"):
            oauth_setup.resolve_pilot_directory(tmp_path, 12345, "Test Pilot", force=False)

    # With force, no prompt needed
    result = oauth_setup.resolve_pilot_directory(tmp_path, 12345, "Test Pilot", force=True)
    assert result == "12345_existing"


def test_no_placeholder_creates_new_directory(tmp_path: Path) -> None:
    """No placeholder → create new {id}_{slug}/ directory."""
    pilots = tmp_path / "userdata" / "pilots"
    pilots.mkdir(parents=True)

    result = oauth_setup.resolve_pilot_directory(tmp_path, 12345, "Test Pilot")
    assert result == "12345_test_pilot"
    assert (pilots / "12345_test_pilot").is_dir()


def test_existing_registry_entry_reused(tmp_path: Path) -> None:
    """Existing registry entry for character reuses that directory."""
    pilots = tmp_path / "userdata" / "pilots"
    pilots.mkdir(parents=True)
    (pilots / "12345_old_slug").mkdir()
    registry = {
        "schema_version": "1.0",
        "pilots": [
            {
                "character_id": "12345",
                "character_name": "Old Name",
                "directory": "12345_old_slug",
            }
        ],
    }
    (pilots / "_registry.json").write_text(json.dumps(registry), encoding="utf-8")

    result = oauth_setup.resolve_pilot_directory(tmp_path, 12345, "New Name")
    assert result == "12345_old_slug"


# ── _acquire_lock ────────────────────────────────────────────────


def test_acquire_lock_success(tmp_path: Path) -> None:
    lockdir = tmp_path / "test.lock"
    oauth_setup._acquire_lock(lockdir)
    assert lockdir.is_dir()
    lockdir.rmdir()


def test_acquire_lock_contention_raises(tmp_path: Path) -> None:
    lockdir = tmp_path / "test.lock"
    lockdir.mkdir()

    with pytest.raises(RuntimeError, match="Lock exists"):
        oauth_setup._acquire_lock(lockdir)

    lockdir.rmdir()


def test_acquire_lock_stale_lock_broken(tmp_path: Path) -> None:
    """Locks older than 300s are automatically broken."""
    lockdir = tmp_path / "test.lock"
    lockdir.mkdir()
    # Set mtime to 600 seconds ago
    old_time = time.time() - 600
    os.utime(lockdir, (old_time, old_time))

    oauth_setup._acquire_lock(lockdir)
    assert lockdir.is_dir()
    lockdir.rmdir()


# ── _atomic_write_json ───────────────────────────────────────────


def test_atomic_write_json_creates_file(tmp_path: Path) -> None:
    path = tmp_path / "test.json"
    data = {"key": "value", "nested": {"a": 1}}

    oauth_setup._atomic_write_json(path, data)
    assert path.exists()
    result = json.loads(path.read_text(encoding="utf-8"))
    assert result == data


def test_atomic_write_json_overwrites(tmp_path: Path) -> None:
    path = tmp_path / "test.json"
    path.write_text('{"old": true}', encoding="utf-8")

    oauth_setup._atomic_write_json(path, {"new": True})
    result = json.loads(path.read_text(encoding="utf-8"))
    assert result == {"new": True}


def test_atomic_write_json_cleans_up_lock(tmp_path: Path) -> None:
    path = tmp_path / "test.json"
    oauth_setup._atomic_write_json(path, {"a": 1})
    lockdir = Path(f"{path}.lock")
    assert not lockdir.exists()


# ── update_pilot_registry ────────────────────────────────────────


def test_registry_preserves_existing_fields(tmp_path: Path) -> None:
    """Existing faction, account_tag, created_at are preserved on update."""
    pilots = tmp_path / "userdata" / "pilots"
    pilots.mkdir(parents=True)
    registry = {
        "schema_version": "1.0",
        "custom_key": "preserved",
        "pilots": [
            {
                "character_id": "12345",
                "character_name": "Old",
                "directory": "12345_slug",
                "faction": "Gallente",
                "account_tag": "alt",
                "created_at": "2025-01-01T00:00:00Z",
                "last_active": "2025-01-01T00:00:00Z",
            }
        ],
    }
    (pilots / "_registry.json").write_text(json.dumps(registry), encoding="utf-8")

    oauth_setup.update_pilot_registry(tmp_path, 12345, "New Name", "12345_slug")

    result = json.loads((pilots / "_registry.json").read_text(encoding="utf-8"))
    entry = result["pilots"][0]
    assert entry["character_name"] == "New Name"
    assert entry["faction"] == "Gallente"
    assert entry["account_tag"] == "alt"
    assert entry["created_at"] == "2025-01-01T00:00:00Z"
    assert result.get("custom_key") == "preserved"
    assert result.get("schema_version") == "1.0"


def test_registry_creates_new_entry(tmp_path: Path) -> None:
    pilots = tmp_path / "userdata" / "pilots"
    pilots.mkdir(parents=True)

    oauth_setup.update_pilot_registry(tmp_path, 12345, "New Pilot", "12345_new_pilot")

    registry = json.loads((pilots / "_registry.json").read_text(encoding="utf-8"))
    assert len(registry["pilots"]) == 1
    entry = registry["pilots"][0]
    assert entry["character_id"] == "12345"
    assert entry["character_name"] == "New Pilot"
    assert entry["directory"] == "12345_new_pilot"
    assert entry["faction"] == "Unknown"
    assert entry["account_tag"] == "main"
    assert "created_at" in entry
    assert "last_active" in entry


# ── update_config ────────────────────────────────────────────────


def test_config_sets_active_pilot_when_missing(tmp_path: Path) -> None:
    (tmp_path / "userdata").mkdir(parents=True)

    oauth_setup.update_config(tmp_path, 12345)

    config = json.loads((tmp_path / "userdata" / "config.json").read_text(encoding="utf-8"))
    assert config["active_pilot"] == "12345"


def test_config_preserves_existing_active_pilot(tmp_path: Path) -> None:
    (tmp_path / "userdata").mkdir(parents=True)
    (tmp_path / "userdata" / "config.json").write_text(
        json.dumps({"active_pilot": "99999", "redisq": {"enabled": True}}),
        encoding="utf-8",
    )

    oauth_setup.update_config(tmp_path, 12345)

    config = json.loads((tmp_path / "userdata" / "config.json").read_text(encoding="utf-8"))
    assert config["active_pilot"] == "99999"
    assert config["redisq"]["enabled"] is True


def test_config_preserves_unknown_keys(tmp_path: Path) -> None:
    """JSON merge semantics: non-core keys like 'redisq' survive updates."""
    (tmp_path / "userdata").mkdir(parents=True)
    (tmp_path / "userdata" / "config.json").write_text(
        json.dumps({"redisq": {"queue": "test"}, "custom_block": [1, 2, 3]}),
        encoding="utf-8",
    )

    oauth_setup.update_config(tmp_path, 12345)

    config = json.loads((tmp_path / "userdata" / "config.json").read_text(encoding="utf-8"))
    assert config["active_pilot"] == "12345"
    assert config["redisq"] == {"queue": "test"}
    assert config["custom_block"] == [1, 2, 3]
