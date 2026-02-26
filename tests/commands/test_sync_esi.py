"""Tests for aria_esi.commands.sync_esi — ESI sync command."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from aria_esi.commands.sync_esi import (
    check_status,
    fetch_blueprints,
    fetch_current_location,
    fetch_ship_roster,
    fetch_wallet,
    run_sync,
    update_blueprints_md,
    update_ships_md,
    write_sync_manifest,
)
from aria_esi.core import CredentialsError, ESIError

# =============================================================================
# Helpers
# =============================================================================


def _make_client(**overrides: Any) -> MagicMock:
    """Create a mock ESIClient with sensible defaults."""
    client = MagicMock()
    client.get_list.return_value = []
    client.get_dict_safe.return_value = {}
    client.get_safe.return_value = None
    client.post_safe.return_value = None
    for k, v in overrides.items():
        setattr(client, k, v)
    return client


# =============================================================================
# TestFetchShipRoster
# =============================================================================


class TestFetchShipRoster:
    """Tests for fetch_ship_roster()."""

    def test_empty_assets_returns_empty(self) -> None:
        client = _make_client()
        client.get_list.return_value = []
        assert fetch_ship_roster(client, 123) == []

    def test_esi_error_returns_empty(self) -> None:
        client = _make_client()
        client.get_list.side_effect = ESIError("server error")
        assert fetch_ship_roster(client, 123) == []

    def test_filters_non_ship_assets(self) -> None:
        """Only items whose group_id is in SHIP_GROUP_IDS are returned."""
        client = _make_client()
        # Two assembled hangar items: one ship (group 25), one module (group 999)
        client.get_list.return_value = [
            {"item_id": 1, "type_id": 100, "is_singleton": True, "location_flag": "Hangar", "location_id": 60003760},
            {"item_id": 2, "type_id": 200, "is_singleton": True, "location_flag": "Hangar", "location_id": 60003760},
        ]
        # Type 100 = Frigate (group 25), Type 200 = Module (group 999)
        def type_lookup(endpoint, **kwargs):
            if "100" in endpoint:
                return {"name": "Rifter", "group_id": 25}
            if "200" in endpoint:
                return {"name": "1MN Afterburner", "group_id": 999}
            if "stations" in endpoint:
                return {"name": "Jita IV - Moon 4"}
            return {}

        client.get_dict_safe.side_effect = type_lookup
        client.post_safe.return_value = [
            {"item_id": 1, "name": "Rifter"},
        ]

        ships = fetch_ship_roster(client, 123)
        assert len(ships) == 1
        assert ships[0]["type_name"] == "Rifter"

    def test_custom_names_applied(self) -> None:
        """Custom ship names different from type name are applied."""
        client = _make_client()
        client.get_list.return_value = [
            {"item_id": 1, "type_id": 100, "is_singleton": True, "location_flag": "Hangar", "location_id": 60003760},
        ]

        def type_lookup(endpoint, **kwargs):
            if "types/100" in endpoint:
                return {"name": "Vexor", "group_id": 26}
            if "stations" in endpoint:
                return {"name": "Dodixie IX - Moon 20"}
            return {}

        client.get_dict_safe.side_effect = type_lookup
        client.post_safe.return_value = [
            {"item_id": 1, "name": "My Special Vexor"},
        ]

        ships = fetch_ship_roster(client, 123)
        assert ships[0]["custom_name"] == "My Special Vexor"

    def test_custom_name_same_as_type_is_empty(self) -> None:
        """If custom name == type name, custom_name should be empty string."""
        client = _make_client()
        client.get_list.return_value = [
            {"item_id": 1, "type_id": 100, "is_singleton": True, "location_flag": "Hangar", "location_id": 60003760},
        ]

        def type_lookup(endpoint, **kwargs):
            if "types/100" in endpoint:
                return {"name": "Vexor", "group_id": 26}
            if "stations" in endpoint:
                return {"name": "Dodixie"}
            return {}

        client.get_dict_safe.side_effect = type_lookup
        client.post_safe.return_value = [
            {"item_id": 1, "name": "Vexor"},
        ]

        ships = fetch_ship_roster(client, 123)
        assert ships[0]["custom_name"] == ""

    def test_unassembled_items_filtered(self) -> None:
        """Non-singleton items are excluded."""
        client = _make_client()
        client.get_list.return_value = [
            {"item_id": 1, "type_id": 100, "is_singleton": False, "location_flag": "Hangar", "location_id": 60003760},
        ]
        assert fetch_ship_roster(client, 123) == []

    def test_non_hangar_items_filtered(self) -> None:
        """Items not in Hangar are excluded."""
        client = _make_client()
        client.get_list.return_value = [
            {"item_id": 1, "type_id": 100, "is_singleton": True, "location_flag": "Cargo", "location_id": 60003760},
        ]
        assert fetch_ship_roster(client, 123) == []

    def test_structure_location_fallback(self) -> None:
        """Unknown locations fall back to Structure-{id} name."""
        client = _make_client()
        client.get_list.return_value = [
            {"item_id": 1, "type_id": 100, "is_singleton": True, "location_flag": "Hangar", "location_id": 999999999},
        ]

        def type_lookup(endpoint, **kwargs):
            if "types/100" in endpoint:
                return {"name": "Venture", "group_id": 25}
            # Station lookup returns empty (it's a player structure)
            if "stations" in endpoint:
                return {}
            return {}

        client.get_dict_safe.side_effect = type_lookup
        client.post_safe.return_value = [{"item_id": 1, "name": "Venture"}]

        ships = fetch_ship_roster(client, 123)
        assert ships[0]["location_name"] == "Structure-999999999"


# =============================================================================
# TestFetchCurrentLocation
# =============================================================================


class TestFetchCurrentLocation:
    """Tests for fetch_current_location()."""

    def test_undocked_returns_location(self) -> None:
        client = _make_client()

        def safe_get(endpoint, **kwargs):
            if "/location/" in endpoint:
                return {"solar_system_id": 30000142}
            if "/ship/" in endpoint:
                return {"ship_type_id": 587, "ship_name": "My Rifter", "ship_item_id": 42}
            if "/systems/30000142" in endpoint:
                return {"name": "Jita", "security_status": 0.9459}
            if "/types/587" in endpoint:
                return {"name": "Rifter"}
            return {}

        client.get_dict_safe.side_effect = safe_get

        result = fetch_current_location(client, 123)
        assert result["solar_system_name"] == "Jita"
        assert result["ship_type_name"] == "Rifter"
        assert result["docked"] is False
        assert "station_id" not in result

    def test_docked_includes_station(self) -> None:
        client = _make_client()

        def safe_get(endpoint, **kwargs):
            if "/location/" in endpoint:
                return {"solar_system_id": 30000142, "station_id": 60003760}
            if "/ship/" in endpoint:
                return {"ship_type_id": 587, "ship_name": "Docked Ship", "ship_item_id": 42}
            if "/systems/30000142" in endpoint:
                return {"name": "Jita", "security_status": 0.9459}
            if "/types/587" in endpoint:
                return {"name": "Rifter"}
            if "/stations/60003760" in endpoint:
                return {"name": "Jita IV - Moon 4 - Caldari Navy Assembly Plant"}
            return {}

        client.get_dict_safe.side_effect = safe_get

        result = fetch_current_location(client, 123)
        assert result["docked"] is True
        assert result["station_name"] == "Jita IV - Moon 4 - Caldari Navy Assembly Plant"

    def test_missing_location_returns_error(self) -> None:
        client = _make_client()
        client.get_dict_safe.return_value = None

        result = fetch_current_location(client, 123)
        assert "error" in result


# =============================================================================
# TestFetchBlueprints
# =============================================================================


class TestFetchBlueprints:
    """Tests for fetch_blueprints()."""

    def test_separates_bpos_and_bpcs(self) -> None:
        client = _make_client()
        client.get_list.return_value = [
            {"type_id": 100, "quantity": -1, "material_efficiency": 10, "time_efficiency": 20},
            {"type_id": 200, "quantity": 5, "runs": 3, "material_efficiency": 0, "time_efficiency": 0},
        ]

        def type_lookup(endpoint, **kwargs):
            if "100" in endpoint:
                return {"name": "Rifter Blueprint"}
            if "200" in endpoint:
                return {"name": "Vexor Blueprint"}
            return {}

        client.get_dict_safe.side_effect = type_lookup

        result = fetch_blueprints(client, 123)
        assert len(result["bpos"]) == 1
        assert len(result["bpcs"]) == 1
        assert result["bpos"][0]["name"] == "Rifter Blueprint"
        assert result["bpos"][0]["material_efficiency"] == 10
        assert result["bpcs"][0]["runs"] == 3

    def test_empty_blueprints(self) -> None:
        client = _make_client()
        client.get_list.return_value = []

        result = fetch_blueprints(client, 123)
        assert result["bpos"] == []
        assert result["bpcs"] == []

    def test_esi_error_returns_error_dict(self) -> None:
        client = _make_client()
        client.get_list.side_effect = ESIError("forbidden")

        result = fetch_blueprints(client, 123)
        assert "error" in result
        assert result["bpos"] == []
        assert result["bpcs"] == []

    def test_results_sorted_by_name(self) -> None:
        client = _make_client()
        client.get_list.return_value = [
            {"type_id": 200, "quantity": -1, "material_efficiency": 0, "time_efficiency": 0},
            {"type_id": 100, "quantity": -1, "material_efficiency": 0, "time_efficiency": 0},
        ]

        def type_lookup(endpoint, **kwargs):
            if "100" in endpoint:
                return {"name": "Alpha Blueprint"}
            if "200" in endpoint:
                return {"name": "Beta Blueprint"}
            return {}

        client.get_dict_safe.side_effect = type_lookup

        result = fetch_blueprints(client, 123)
        assert result["bpos"][0]["name"] == "Alpha Blueprint"
        assert result["bpos"][1]["name"] == "Beta Blueprint"


# =============================================================================
# TestFetchWallet
# =============================================================================


class TestFetchWallet:
    """Tests for fetch_wallet()."""

    def test_returns_balance(self) -> None:
        client = _make_client()
        client.get_safe.return_value = 1500000.50
        assert fetch_wallet(client, 123) == 1500000.50

    def test_integer_balance(self) -> None:
        client = _make_client()
        client.get_safe.return_value = 500000
        assert fetch_wallet(client, 123) == 500000.0

    def test_error_returns_zero(self) -> None:
        client = _make_client()
        client.get_safe.return_value = {"error": "forbidden"}
        assert fetch_wallet(client, 123) == 0.0


# =============================================================================
# TestUpdateShipsMd
# =============================================================================


class TestUpdateShipsMd:
    """Tests for update_ships_md()."""

    def test_creates_new_file(self, tmp_path: Path) -> None:
        ships = [
            {"type_name": "Vexor", "custom_name": "Battle Vexor", "location_name": "Dodixie IX"},
            {"type_name": "Rifter", "custom_name": "", "location_name": "Jita IV - Moon 4"},
        ]
        assert update_ships_md(tmp_path, ships) is True

        content = (tmp_path / "ships.md").read_text()
        assert "# Ship Status" in content
        assert "<!-- ESI-SYNC:ROSTER:START -->" in content
        assert "<!-- ESI-SYNC:ROSTER:END -->" in content
        assert "Battle Vexor" in content
        assert "(unnamed)" in content  # Rifter has no custom name
        assert "2 ships in hangars" in content

    def test_replaces_existing_markers(self, tmp_path: Path) -> None:
        ships_path = tmp_path / "ships.md"
        ships_path.write_text(
            "# Ship Status\n\n"
            "<!-- ESI-SYNC:ROSTER:START -->\nOLD CONTENT\n<!-- ESI-SYNC:ROSTER:END -->\n\n"
            "## Notes\nKeep this section.\n"
        )

        ships = [
            {"type_name": "Venture", "custom_name": "Miner", "location_name": "Hek"},
        ]
        assert update_ships_md(tmp_path, ships) is True

        content = ships_path.read_text()
        assert "OLD CONTENT" not in content
        assert "Miner" in content
        assert "## Notes" in content
        assert "Keep this section." in content

    def test_preserves_content_outside_markers(self, tmp_path: Path) -> None:
        ships_path = tmp_path / "ships.md"
        ships_path.write_text(
            "# Ship Status\n\n"
            "Some important notes.\n\n"
            "<!-- ESI-SYNC:ROSTER:START -->\nOLD\n<!-- ESI-SYNC:ROSTER:END -->\n\n"
            "## Fitting Details\n\nKeep all of this.\n"
        )

        ships = [{"type_name": "Drake", "custom_name": "", "location_name": "Amarr"}]
        update_ships_md(tmp_path, ships)

        content = ships_path.read_text()
        assert "Some important notes." in content
        assert "## Fitting Details" in content
        assert "Keep all of this." in content

    def test_long_location_truncated(self, tmp_path: Path) -> None:
        ships = [
            {
                "type_name": "Dominix",
                "custom_name": "",
                "location_name": "A Very Long Station Name That Exceeds Twenty Five Characters",
            },
        ]
        update_ships_md(tmp_path, ships)

        content = (tmp_path / "ships.md").read_text()
        assert "..." in content

    def test_location_split_on_dash(self, tmp_path: Path) -> None:
        """Location names like 'Jita IV - Moon 4 - CNR' split on first ' - '."""
        ships = [
            {"type_name": "Merlin", "custom_name": "", "location_name": "Jita IV - Moon 4 - CNR"},
        ]
        update_ships_md(tmp_path, ships)

        content = (tmp_path / "ships.md").read_text()
        assert "Jita IV" in content


# =============================================================================
# TestUpdateBlueprintsMd
# =============================================================================


class TestUpdateBlueprintsMd:
    """Tests for update_blueprints_md()."""

    def test_creates_directory_and_file(self, tmp_path: Path) -> None:
        bp_data = {
            "bpos": [{"name": "Rifter Blueprint", "material_efficiency": 10, "time_efficiency": 20}],
            "bpcs": [{"name": "Vexor Blueprint", "material_efficiency": 0, "time_efficiency": 0, "runs": 5}],
        }
        assert update_blueprints_md(tmp_path, bp_data) is True
        assert (tmp_path / "industry" / "blueprints.md").exists()

        content = (tmp_path / "industry" / "blueprints.md").read_text()
        assert "Rifter Blueprint" in content
        assert "10%" in content
        assert "Vexor Blueprint" in content
        assert "1 BPOs total" in content
        assert "1 BPCs total" in content

    def test_empty_blueprints(self, tmp_path: Path) -> None:
        bp_data = {"bpos": [], "bpcs": []}
        update_blueprints_md(tmp_path, bp_data)

        content = (tmp_path / "industry" / "blueprints.md").read_text()
        assert "*No BPOs owned*" in content
        assert "*No BPCs owned*" in content


# =============================================================================
# TestWriteSyncManifest
# =============================================================================


class TestWriteSyncManifest:
    """Tests for write_sync_manifest()."""

    def test_writes_json(self, tmp_path: Path) -> None:
        data = {"sync_timestamp": "2026-01-01T00:00:00Z", "status": "success"}
        assert write_sync_manifest(tmp_path, data) is True

        content = json.loads((tmp_path / ".esi-sync.json").read_text())
        assert content["status"] == "success"


# =============================================================================
# TestRunSync
# =============================================================================


class TestRunSync:
    """Tests for run_sync()."""

    @patch("aria_esi.commands.sync_esi.get_pilot_directory")
    @patch("aria_esi.commands.sync_esi.get_authenticated_client")
    def test_credentials_error_returns_error(self, mock_auth: MagicMock, mock_pilot: MagicMock) -> None:
        mock_auth.side_effect = CredentialsError("No credentials found")

        result = run_sync(quiet=True)
        assert result["status"] == "error"
        assert "No credentials found" in result["errors"][0]

    @patch("aria_esi.commands.sync_esi.write_sync_manifest")
    @patch("aria_esi.commands.sync_esi.update_ships_md")
    @patch("aria_esi.commands.sync_esi.fetch_ship_roster")
    @patch("aria_esi.commands.sync_esi.fetch_wallet")
    @patch("aria_esi.commands.sync_esi.fetch_current_location")
    @patch("aria_esi.commands.sync_esi.get_pilot_directory")
    @patch("aria_esi.commands.sync_esi.get_authenticated_client")
    def test_quick_mode_skips_blueprints(
        self,
        mock_auth: MagicMock,
        mock_pilot: MagicMock,
        mock_location: MagicMock,
        mock_wallet: MagicMock,
        mock_ships: MagicMock,
        mock_update: MagicMock,
        mock_manifest: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_creds = MagicMock()
        mock_creds.character_id = 123
        mock_creds.credentials_file = None
        mock_auth.return_value = (MagicMock(), mock_creds)
        mock_pilot.return_value = tmp_path
        mock_location.return_value = {"solar_system_name": "Jita", "security_status": 0.9}
        mock_wallet.return_value = 1000.0
        mock_ships.return_value = [{"type_name": "Rifter", "item_id": 1}]
        mock_update.return_value = True
        mock_manifest.return_value = True

        result = run_sync(quick=True, quiet=True)
        assert "blueprints" not in result.get("synced", [])
        mock_manifest.assert_called_once()

    @patch("aria_esi.commands.sync_esi.get_pilot_directory")
    @patch("aria_esi.commands.sync_esi.get_authenticated_client")
    def test_missing_pilot_dir_returns_error(self, mock_auth: MagicMock, mock_pilot: MagicMock) -> None:
        mock_creds = MagicMock()
        mock_creds.character_id = 123
        mock_auth.return_value = (MagicMock(), mock_creds)
        mock_pilot.return_value = None

        result = run_sync(quiet=True)
        assert result["status"] == "error"
        assert "Pilot directory not found" in result["errors"][0]

    @patch("aria_esi.commands.sync_esi.write_sync_manifest")
    @patch("aria_esi.commands.sync_esi.update_ships_md")
    @patch("aria_esi.commands.sync_esi.fetch_ship_roster")
    @patch("aria_esi.commands.sync_esi.fetch_wallet")
    @patch("aria_esi.commands.sync_esi.fetch_current_location")
    @patch("aria_esi.commands.sync_esi.get_pilot_directory")
    @patch("aria_esi.commands.sync_esi.get_authenticated_client")
    @patch("aria_esi.commands.sync_esi._get_character_name")
    def test_manifest_written_on_success(
        self,
        mock_name: MagicMock,
        mock_auth: MagicMock,
        mock_pilot: MagicMock,
        mock_location: MagicMock,
        mock_wallet: MagicMock,
        mock_ships: MagicMock,
        mock_update: MagicMock,
        mock_manifest: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_name.return_value = "Test Pilot"
        mock_creds = MagicMock()
        mock_creds.character_id = 123
        mock_creds.credentials_file = None
        mock_auth.return_value = (MagicMock(), mock_creds)
        mock_pilot.return_value = tmp_path
        mock_location.return_value = {"solar_system_name": "Jita", "security_status": 0.9}
        mock_wallet.return_value = 5000.0
        mock_ships.return_value = []
        mock_manifest.return_value = True

        result = run_sync(quick=True, quiet=True)
        mock_manifest.assert_called_once()
        assert result["character_name"] == "Test Pilot"


# =============================================================================
# TestCheckStatus
# =============================================================================


class TestCheckStatus:
    """Tests for check_status()."""

    @patch("aria_esi.commands.sync_esi.get_pilot_directory")
    def test_no_pilot_dir(self, mock_pilot: MagicMock) -> None:
        mock_pilot.return_value = None
        result = check_status()
        assert result["status"] == "no_pilot"

    @patch("aria_esi.commands.sync_esi.get_pilot_directory")
    def test_no_manifest(self, mock_pilot: MagicMock, tmp_path: Path) -> None:
        mock_pilot.return_value = tmp_path
        result = check_status()
        assert result["status"] == "never_synced"

    @patch("aria_esi.commands.sync_esi.get_pilot_directory")
    def test_reads_manifest_and_calculates_age(self, mock_pilot: MagicMock, tmp_path: Path) -> None:
        mock_pilot.return_value = tmp_path
        now = datetime.now(UTC)
        manifest = {
            "sync_timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": "success",
            "ship_count": 5,
            "volatile_snapshot": {
                "current_location": {"solar_system_name": "Jita"},
            },
        }
        (tmp_path / ".esi-sync.json").write_text(json.dumps(manifest))

        result = check_status()
        assert result["status"] == "success"
        assert "age_minutes" in result
        assert result["age_minutes"] >= 0
        assert "age_display" in result

    @patch("aria_esi.commands.sync_esi.get_pilot_directory")
    def test_corrupt_manifest(self, mock_pilot: MagicMock, tmp_path: Path) -> None:
        mock_pilot.return_value = tmp_path
        (tmp_path / ".esi-sync.json").write_text("not json")

        result = check_status()
        assert result["status"] == "error"


# =============================================================================
# TestGetCharacterName
# =============================================================================


class TestGetCharacterName:
    """Tests for _get_character_name()."""

    def test_reads_from_file(self, tmp_path: Path) -> None:
        from aria_esi.commands.sync_esi import _get_character_name

        creds_file = tmp_path / "creds.json"
        creds_file.write_text(json.dumps({"character_name": "Test Capsuleer"}))
        assert _get_character_name(creds_file, 123) == "Test Capsuleer"

    def test_fallback_when_no_file(self) -> None:
        from aria_esi.commands.sync_esi import _get_character_name

        assert _get_character_name(None, 12345) == "Pilot 12345"

    def test_fallback_when_file_missing(self, tmp_path: Path) -> None:
        from aria_esi.commands.sync_esi import _get_character_name

        assert _get_character_name(tmp_path / "nonexistent.json", 99) == "Pilot 99"

    def test_fallback_when_no_name_in_json(self, tmp_path: Path) -> None:
        from aria_esi.commands.sync_esi import _get_character_name

        creds_file = tmp_path / "creds.json"
        creds_file.write_text(json.dumps({"character_id": 123}))
        assert _get_character_name(creds_file, 123) == "Pilot 123"
