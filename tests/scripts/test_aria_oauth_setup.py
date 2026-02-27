from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / ".claude" / "scripts" / "aria-oauth-setup.py"

spec = importlib.util.spec_from_file_location("aria_oauth_setup", SCRIPT_PATH)
oauth_setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oauth_setup)


def test_reuses_existing_registry_directory_when_character_exists(tmp_path: Path) -> None:
    pilots_root = tmp_path / "userdata" / "pilots"
    pilots_root.mkdir(parents=True)
    (pilots_root / "12345_existing_slug").mkdir()
    (pilots_root / "_registry.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "pilots": [
                    {
                        "character_id": "12345",
                        "character_name": "Old Pilot",
                        "directory": "12345_existing_slug",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    directory_name = oauth_setup.resolve_pilot_directory(tmp_path, 12345, "Different Name")
    oauth_setup.update_pilot_registry(tmp_path, 12345, "Different Name", directory_name)

    registry = json.loads((pilots_root / "_registry.json").read_text(encoding="utf-8"))
    entry = registry["pilots"][0]
    assert directory_name == "12345_existing_slug"
    assert entry["directory"] == "12345_existing_slug"
    assert entry["character_name"] == "Different Name"
    assert not (pilots_root / "12345_different_name").exists()


def test_registry_entry_with_missing_directory_fails(tmp_path: Path) -> None:
    pilots_root = tmp_path / "userdata" / "pilots"
    pilots_root.mkdir(parents=True)
    (pilots_root / "_registry.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "pilots": [
                    {
                        "character_id": "12345",
                        "character_name": "Old Pilot",
                        "directory": "12345_missing_dir",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="directory is missing"):
        oauth_setup.resolve_pilot_directory(tmp_path, 12345, "Different Name")

    assert not (pilots_root / "12345_different_name").exists()
