"""Tests for sovereignty data validation.

These tests verify that coalition data in coalitions.yaml is valid
against authoritative sources (ESI for alliance IDs).

See docs/DATA_AUTHORITY.md for data authority hierarchy.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from aria_esi.commands.sovereignty import validate_coalitions_yaml

# Path where the sync fetch function is defined
FETCH_PATCH_PATH = "aria_esi.services.sovereignty.fetcher.fetch_alliances_batch_sync"


@pytest.fixture
def valid_coalition_yaml(tmp_path: Path) -> Path:
    """Create a valid coalition YAML for testing."""
    data = {
        "schema_version": "1.1",
        "last_updated": "2026-02-04",
        "coalitions": {
            "test_coalition": {
                "display_name": "Test Coalition",
                "aliases": ["test", "tc"],
                "alliances": [
                    {"id": 1000001, "name": "Test Alliance One"},
                    {"id": 1000002, "name": "Test Alliance Two"},
                ],
            },
        },
        "metadata": {
            "source": "Test",
        },
    }
    yaml_path = tmp_path / "coalitions.yaml"
    with open(yaml_path, "w") as f:
        yaml.dump(data, f)
    return yaml_path


@pytest.fixture
def invalid_alliance_yaml(tmp_path: Path) -> Path:
    """Create a coalition YAML with invalid alliance IDs."""
    data = {
        "schema_version": "1.1",
        "coalitions": {
            "test_coalition": {
                "display_name": "Test Coalition",
                "aliases": [],
                "alliances": [
                    {"id": 1000001, "name": "Test Alliance One"},  # Valid
                    {"id": 9999999, "name": "Invalid Alliance"},  # Does not exist
                ],
            },
        },
    }
    yaml_path = tmp_path / "coalitions.yaml"
    with open(yaml_path, "w") as f:
        yaml.dump(data, f)
    return yaml_path


@pytest.fixture
def name_mismatch_yaml(tmp_path: Path) -> Path:
    """Create a coalition YAML with name mismatch."""
    data = {
        "schema_version": "1.1",
        "coalitions": {
            "test_coalition": {
                "display_name": "Test Coalition",
                "aliases": [],
                "alliances": [
                    {"id": 1000001, "name": "Wrong Name"},  # Name doesn't match ESI
                ],
            },
        },
    }
    yaml_path = tmp_path / "coalitions.yaml"
    with open(yaml_path, "w") as f:
        yaml.dump(data, f)
    return yaml_path


@pytest.fixture
def duplicate_alliance_yaml(tmp_path: Path) -> Path:
    """Create a coalition YAML with duplicate alliance ID across coalitions."""
    data = {
        "schema_version": "1.1",
        "coalitions": {
            "coalition_a": {
                "display_name": "Coalition A",
                "aliases": [],
                "alliances": [
                    {"id": 1000001, "name": "Test Alliance One"},
                ],
            },
            "coalition_b": {
                "display_name": "Coalition B",
                "aliases": [],
                "alliances": [
                    {"id": 1000001, "name": "Test Alliance One"},  # Duplicate!
                    {"id": 1000002, "name": "Test Alliance Two"},
                ],
            },
        },
    }
    yaml_path = tmp_path / "coalitions.yaml"
    with open(yaml_path, "w") as f:
        yaml.dump(data, f)
    return yaml_path


@pytest.fixture
def mock_esi_responses():
    """Mock ESI responses for alliance lookups."""
    return {
        1000001: {"name": "Test Alliance One", "ticker": "TA1"},
        1000002: {"name": "Test Alliance Two", "ticker": "TA2"},
        # 9999999 is intentionally missing (not found)
    }


class TestValidateCoalitionsYaml:
    """Tests for validate_coalitions_yaml function."""

    def test_valid_yaml_passes(
        self, valid_coalition_yaml: Path, mock_esi_responses: dict
    ):
        """Test that valid YAML passes validation."""
        def mock_fetch(ids):
            return {aid: mock_esi_responses[aid] for aid in ids if aid in mock_esi_responses}

        with patch(FETCH_PATCH_PATH, mock_fetch):
            result = validate_coalitions_yaml(yaml_path=valid_coalition_yaml)

        assert result["valid"] is True
        assert result["alliances_checked"] == 2
        assert result["valid_count"] == 2
        assert result["invalid_count"] == 0
        assert result["duplicate_count"] == 0

    def test_invalid_alliance_fails(
        self, invalid_alliance_yaml: Path, mock_esi_responses: dict
    ):
        """Test that invalid alliance IDs cause validation to fail."""
        def mock_fetch(ids):
            return {aid: mock_esi_responses[aid] for aid in ids if aid in mock_esi_responses}

        with patch(FETCH_PATCH_PATH, mock_fetch):
            result = validate_coalitions_yaml(yaml_path=invalid_alliance_yaml)

        assert result["valid"] is False
        assert result["invalid_count"] == 1
        assert len(result["invalid_entries"]) == 1
        assert result["invalid_entries"][0]["alliance_id"] == 9999999
        assert "not found" in result["invalid_entries"][0]["reason"].lower()

    def test_name_mismatch_fails(
        self, name_mismatch_yaml: Path, mock_esi_responses: dict
    ):
        """Test that name mismatches cause validation to fail."""
        def mock_fetch(ids):
            return {aid: mock_esi_responses[aid] for aid in ids if aid in mock_esi_responses}

        with patch(FETCH_PATCH_PATH, mock_fetch):
            result = validate_coalitions_yaml(yaml_path=name_mismatch_yaml)

        assert result["valid"] is False
        assert result["invalid_count"] == 1
        assert "mismatch" in result["invalid_entries"][0]["reason"].lower()

    def test_fix_removes_invalid_entries(
        self, invalid_alliance_yaml: Path, mock_esi_responses: dict
    ):
        """Test that --fix removes invalid entries."""
        def mock_fetch(ids):
            return {aid: mock_esi_responses[aid] for aid in ids if aid in mock_esi_responses}

        with patch(FETCH_PATCH_PATH, mock_fetch):
            result = validate_coalitions_yaml(
                yaml_path=invalid_alliance_yaml, fix=True
            )

        assert result["fixes_applied"]["removed"] == 1

        # Verify the file was updated
        with open(invalid_alliance_yaml) as f:
            updated_data = yaml.safe_load(f)

        alliances = updated_data["coalitions"]["test_coalition"]["alliances"]
        alliance_ids = [a["id"] for a in alliances]
        assert 9999999 not in alliance_ids
        assert 1000001 in alliance_ids

    def test_fix_corrects_names(
        self, name_mismatch_yaml: Path, mock_esi_responses: dict
    ):
        """Test that --fix corrects name mismatches."""
        def mock_fetch(ids):
            return {aid: mock_esi_responses[aid] for aid in ids if aid in mock_esi_responses}

        with patch(FETCH_PATCH_PATH, mock_fetch):
            result = validate_coalitions_yaml(yaml_path=name_mismatch_yaml, fix=True)

        assert result["fixes_applied"]["name_fixed"] == 1

        # Verify the file was updated
        with open(name_mismatch_yaml) as f:
            updated_data = yaml.safe_load(f)

        alliances = updated_data["coalitions"]["test_coalition"]["alliances"]
        assert alliances[0]["name"] == "Test Alliance One"

    def test_fix_includes_warning_about_comments(
        self, invalid_alliance_yaml: Path, mock_esi_responses: dict
    ):
        """Test that --fix result includes warning about lost comments."""
        def mock_fetch(ids):
            return {aid: mock_esi_responses[aid] for aid in ids if aid in mock_esi_responses}

        with patch(FETCH_PATCH_PATH, mock_fetch):
            result = validate_coalitions_yaml(
                yaml_path=invalid_alliance_yaml, fix=True
            )

        assert "warning" in result
        assert "comment" in result["warning"].lower()

    def test_esi_unavailable_fails(self, valid_coalition_yaml: Path):
        """Test that ESI unavailability causes validation to fail."""
        def mock_fetch(ids):
            raise Exception("ESI unavailable")

        with patch(FETCH_PATCH_PATH, mock_fetch):
            result = validate_coalitions_yaml(yaml_path=valid_coalition_yaml)

        assert result["valid"] is False
        assert result["error"] == "esi_unavailable"

    def test_duplicate_alliance_fails(
        self, duplicate_alliance_yaml: Path, mock_esi_responses: dict
    ):
        """Test that duplicate alliance IDs across coalitions cause validation to fail."""
        def mock_fetch(ids):
            return {aid: mock_esi_responses[aid] for aid in ids if aid in mock_esi_responses}

        with patch(FETCH_PATCH_PATH, mock_fetch):
            result = validate_coalitions_yaml(yaml_path=duplicate_alliance_yaml)

        assert result["valid"] is False
        assert result["duplicate_count"] == 1
        assert result["error"] == "duplicate_alliance_ids"
        assert len(result["duplicate_entries"]) == 1
        dup = result["duplicate_entries"][0]
        assert dup["alliance_id"] == 1000001
        assert dup["first_coalition"] == "coalition_a"
        assert dup["duplicate_coalition"] == "coalition_b"

    def test_missing_file_fails(self, tmp_path: Path):
        """Test that missing YAML file causes validation to fail."""
        result = validate_coalitions_yaml(yaml_path=tmp_path / "nonexistent.yaml")

        assert result["valid"] is False
        assert result["error"] == "file_not_found"

    def test_empty_coalitions_passes(self, tmp_path: Path):
        """Test that YAML with no alliances passes validation."""
        data = {
            "schema_version": "1.1",
            "coalitions": {
                "empty_coalition": {
                    "display_name": "Empty",
                    "aliases": [],
                    "alliances": [],
                },
            },
        }
        yaml_path = tmp_path / "coalitions.yaml"
        with open(yaml_path, "w") as f:
            yaml.dump(data, f)

        # No ESI call should be made for empty alliances
        result = validate_coalitions_yaml(yaml_path=yaml_path)

        assert result["valid"] is True
        assert result["alliances_checked"] == 0


class TestProductionCoalitionsYaml:
    """Tests that validate the actual coalitions.yaml in the repository.

    These tests run against the real coalition data to ensure it remains
    valid before merging changes.
    """

    @pytest.fixture
    def production_yaml_path(self) -> Path:
        """Get path to production coalitions.yaml."""
        return (
            Path(__file__).parent.parent.parent.parent
            / "src"
            / "aria_esi"
            / "data"
            / "sovereignty"
            / "coalitions.yaml"
        )

    def test_production_yaml_exists(self, production_yaml_path: Path):
        """Test that production coalitions.yaml exists."""
        assert production_yaml_path.exists(), f"Missing: {production_yaml_path}"

    def test_production_yaml_valid_schema(self, production_yaml_path: Path):
        """Test that production YAML has valid schema."""
        with open(production_yaml_path) as f:
            data = yaml.safe_load(f)

        assert "schema_version" in data
        assert "coalitions" in data
        assert isinstance(data["coalitions"], dict)

        for coalition_id, coalition_info in data["coalitions"].items():
            assert "display_name" in coalition_info
            assert "aliases" in coalition_info
            assert "alliances" in coalition_info
            assert isinstance(coalition_info["alliances"], list)

            for alliance in coalition_info["alliances"]:
                assert "id" in alliance, f"Alliance missing ID in {coalition_id}"
                assert "name" in alliance, f"Alliance missing name in {coalition_id}"
                assert isinstance(
                    alliance["id"], int
                ), f"Alliance ID not int in {coalition_id}"

    def test_production_yaml_no_duplicate_ids(self, production_yaml_path: Path):
        """Test that no alliance ID appears more than once."""
        with open(production_yaml_path) as f:
            data = yaml.safe_load(f)

        all_ids = []
        for coalition_id, coalition_info in data.get("coalitions", {}).items():
            for alliance in coalition_info.get("alliances", []):
                all_ids.append((alliance["id"], coalition_id, alliance.get("name")))

        # Check for duplicates
        seen = {}
        duplicates = []
        for alliance_id, coalition_id, name in all_ids:
            if alliance_id in seen:
                duplicates.append(
                    f"ID {alliance_id} ({name}) in {coalition_id} "
                    f"also appears in {seen[alliance_id]}"
                )
            seen[alliance_id] = coalition_id

        assert not duplicates, "Duplicate alliance IDs found:\n" + "\n".join(duplicates)

    @pytest.mark.skipif(
        True,  # Skip by default - enable when ESI is available
        reason="Requires live ESI access - run manually with --run-esi-tests",
    )
    def test_production_yaml_valid_against_esi(self, production_yaml_path: Path):
        """Test that all alliance IDs in production YAML are valid in ESI.

        This test requires live ESI access and is skipped by default.
        Run with: pytest -k test_production_yaml_valid_against_esi --run-esi-tests
        """
        result = validate_coalitions_yaml(yaml_path=production_yaml_path)

        assert result.get("error") != "esi_unavailable", "ESI unavailable"
        assert result["valid"], (
            f"Production coalitions.yaml validation failed:\n"
            f"Invalid entries: {result.get('invalid_entries', [])}"
        )
