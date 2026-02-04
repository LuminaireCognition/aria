"""
Tests for core authentication module.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from aria_esi.core.auth import (
    Credentials,
    CredentialsError,
    is_player_corp,
)
from aria_esi.core.constants import PLAYER_CORP_MIN_ID


class TestIsPlayerCorp:
    """Tests for is_player_corp function."""

    def test_npc_corp_returns_false(self):
        """NPC corporation IDs should return False."""
        # NPC corps have IDs below PLAYER_CORP_MIN_ID
        assert is_player_corp(1000001) is False
        assert is_player_corp(1000125) is False  # Sisters of EVE

    def test_player_corp_returns_true(self):
        """Player corporation IDs should return True."""
        assert is_player_corp(PLAYER_CORP_MIN_ID) is True
        assert is_player_corp(PLAYER_CORP_MIN_ID + 1) is True
        assert is_player_corp(98000001) is True

    def test_boundary_value(self):
        """Test boundary between NPC and player corps."""
        assert is_player_corp(PLAYER_CORP_MIN_ID - 1) is False
        assert is_player_corp(PLAYER_CORP_MIN_ID) is True


class TestCredentialsError:
    """Tests for CredentialsError exception."""

    def test_basic_error(self):
        """Should create error with just message."""
        err = CredentialsError("Test error")
        assert err.message == "Test error"
        assert err.action is None
        assert err.command is None

    def test_error_with_action(self):
        """Should include action hint."""
        err = CredentialsError("Test error", action="Run setup")
        assert err.message == "Test error"
        assert err.action == "Run setup"
        assert err.command is None

    def test_error_with_command(self):
        """Should include command."""
        err = CredentialsError("Test error", command="python setup.py")
        assert err.command == "python setup.py"

    def test_to_dict_basic(self):
        """to_dict should return JSON-serializable dict."""
        err = CredentialsError("Test error")
        result = err.to_dict()
        assert result["error"] == "credentials_error"
        assert result["message"] == "Test error"
        assert "action" not in result
        assert "command" not in result

    def test_to_dict_full(self):
        """to_dict should include action and command if set."""
        err = CredentialsError("Test error", action="Run setup", command="python setup.py")
        result = err.to_dict()
        assert result["action"] == "Run setup"
        assert result["command"] == "python setup.py"

    def test_exception_message(self):
        """Should work as a standard exception."""
        with pytest.raises(CredentialsError) as exc_info:
            raise CredentialsError("Test error")
        assert str(exc_info.value) == "Test error"


class TestCredentials:
    """Tests for Credentials class."""

    def test_init_minimal(self):
        """Should initialize with required fields."""
        creds = Credentials(
            credentials_file=None,
            character_id=12345,
            access_token="test_token",
        )
        assert creds.character_id == 12345
        assert creds.access_token == "test_token"
        assert creds.refresh_token is None
        assert creds.scopes == []
        assert creds.storage_source == "file"

    def test_init_full(self):
        """Should initialize with all fields."""
        creds = Credentials(
            credentials_file=Path("/test/path.json"),
            character_id=12345,
            access_token="test_token",
            refresh_token="refresh_token",
            token_expiry="2024-01-01T00:00:00",
            scopes=["scope1", "scope2"],
            storage_source="keyring",
        )
        assert creds.credentials_file == Path("/test/path.json")
        assert creds.refresh_token == "refresh_token"
        assert creds.token_expiry == "2024-01-01T00:00:00"
        assert creds.scopes == ["scope1", "scope2"]
        assert creds.storage_source == "keyring"

    def test_has_scope_true(self):
        """Should return True when scope exists."""
        creds = Credentials(
            credentials_file=None,
            character_id=12345,
            access_token="test",
            scopes=["esi-wallet.read_character_wallet.v1"],
        )
        assert creds.has_scope("esi-wallet.read_character_wallet.v1") is True

    def test_has_scope_false(self):
        """Should return False when scope missing."""
        creds = Credentials(
            credentials_file=None,
            character_id=12345,
            access_token="test",
            scopes=["esi-wallet.read_character_wallet.v1"],
        )
        assert creds.has_scope("esi-skills.read_skills.v1") is False

    def test_get_personal_scopes(self):
        """Should filter out corporation scopes."""
        creds = Credentials(
            credentials_file=None,
            character_id=12345,
            access_token="test",
            scopes=[
                "esi-wallet.read_character_wallet.v1",
                "esi-wallet.read_corporation_wallet.v1",
                "esi-skills.read_skills.v1",
            ],
        )
        personal = creds.get_personal_scopes()
        assert "esi-wallet.read_character_wallet.v1" in personal
        assert "esi-skills.read_skills.v1" in personal
        assert "esi-wallet.read_corporation_wallet.v1" not in personal

    def test_get_corp_scopes(self):
        """Should return only corporation scopes."""
        creds = Credentials(
            credentials_file=None,
            character_id=12345,
            access_token="test",
            scopes=[
                "esi-wallet.read_character_wallet.v1",
                "esi-wallet.read_corporation_wallet.v1",
                "esi-corporations.read_corporation_membership.v1",
            ],
        )
        corp = creds.get_corp_scopes()
        assert "esi-wallet.read_corporation_wallet.v1" in corp
        assert "esi-corporations.read_corporation_membership.v1" in corp
        assert "esi-wallet.read_character_wallet.v1" not in corp

    def test_require_scope_success(self):
        """Should not raise when scope exists."""
        creds = Credentials(
            credentials_file=None,
            character_id=12345,
            access_token="test",
            scopes=["required_scope"],
        )
        creds.require_scope("required_scope")  # Should not raise

    def test_require_scope_raises(self):
        """Should raise CredentialsError when scope missing."""
        creds = Credentials(
            credentials_file=None,
            character_id=12345,
            access_token="test",
            scopes=[],
        )
        with pytest.raises(CredentialsError) as exc_info:
            creds.require_scope("missing_scope")
        assert "missing_scope" in str(exc_info.value)

    def test_get_full_data_minimal(self):
        """Should return dict with required fields."""
        creds = Credentials(
            credentials_file=None,
            character_id=12345,
            access_token="test_token",
        )
        data = creds.get_full_data()
        assert data["character_id"] == 12345
        assert data["access_token"] == "test_token"
        assert "refresh_token" not in data
        assert "scopes" not in data

    def test_get_full_data_full(self):
        """Should include optional fields when set."""
        creds = Credentials(
            credentials_file=None,
            character_id=12345,
            access_token="test_token",
            refresh_token="refresh",
            token_expiry="2024-01-01",
            scopes=["scope1"],
        )
        data = creds.get_full_data()
        assert data["refresh_token"] == "refresh"
        assert data["token_expiry"] == "2024-01-01"
        assert data["scopes"] == ["scope1"]

    def test_from_file_success(self, tmp_path):
        """Should load credentials from JSON file."""
        creds_file = tmp_path / "test.json"
        creds_file.write_text(
            json.dumps(
                {
                    "character_id": 12345,
                    "access_token": "test_token",
                    "refresh_token": "refresh",
                    "scopes": ["scope1"],
                }
            )
        )

        creds = Credentials.from_file(creds_file)

        assert creds.character_id == 12345
        assert creds.access_token == "test_token"
        assert creds.refresh_token == "refresh"
        assert creds.storage_source == "file"

    def test_from_file_not_found(self, tmp_path):
        """Should raise CredentialsError for missing file."""
        creds_file = tmp_path / "nonexistent.json"

        with pytest.raises(CredentialsError) as exc_info:
            Credentials.from_file(creds_file)
        assert "not found" in str(exc_info.value)

    def test_from_file_invalid_json(self, tmp_path):
        """Should raise CredentialsError for invalid JSON."""
        creds_file = tmp_path / "invalid.json"
        creds_file.write_text("not valid json {{{")

        with pytest.raises(CredentialsError) as exc_info:
            Credentials.from_file(creds_file)
        assert "Invalid credentials JSON" in str(exc_info.value)

    def test_from_file_missing_fields(self, tmp_path):
        """Should raise CredentialsError for missing required fields."""
        creds_file = tmp_path / "incomplete.json"
        creds_file.write_text(json.dumps({"character_id": 12345}))  # Missing access_token

        with pytest.raises(CredentialsError) as exc_info:
            Credentials.from_file(creds_file)
        assert "Missing required field" in str(exc_info.value)


class TestCredentialsFromKeyring:
    """Tests for Credentials.from_keyring method."""

    def test_keyring_disabled_returns_none(self):
        """Should return None when keyring is disabled."""
        with patch("aria_esi.core.auth.is_keyring_enabled", return_value=False):
            result = Credentials.from_keyring("12345")
        assert result is None

    def test_keyring_no_data_returns_none(self):
        """Should return None when no data in keyring."""
        with (
            patch("aria_esi.core.auth.is_keyring_enabled", return_value=True),
            patch("aria_esi.core.auth.load_from_keyring", return_value=None),
        ):
            result = Credentials.from_keyring("12345")
        assert result is None

    def test_keyring_invalid_data_returns_none(self):
        """Should return None when keyring data missing required fields."""
        with (
            patch("aria_esi.core.auth.is_keyring_enabled", return_value=True),
            patch(
                "aria_esi.core.auth.load_from_keyring",
                return_value={"character_id": 12345},  # Missing access_token
            ),
        ):
            result = Credentials.from_keyring("12345")
        assert result is None

    def test_keyring_success(self):
        """Should return Credentials from keyring data."""
        keyring_data = {
            "character_id": 12345,
            "access_token": "keyring_token",
            "refresh_token": "refresh",
            "scopes": ["scope1"],
        }
        with (
            patch("aria_esi.core.auth.is_keyring_enabled", return_value=True),
            patch("aria_esi.core.auth.load_from_keyring", return_value=keyring_data),
        ):
            result = Credentials.from_keyring("12345")

        assert result is not None
        assert result.character_id == 12345
        assert result.access_token == "keyring_token"
        assert result.storage_source == "keyring"


class TestCredentialsSaveToKeyring:
    """Tests for Credentials.save_to_keyring method."""

    def test_save_keyring_disabled(self):
        """Should return False when keyring disabled."""
        creds = Credentials(
            credentials_file=None,
            character_id=12345,
            access_token="test",
        )
        with patch("aria_esi.core.auth.is_keyring_enabled", return_value=False):
            result = creds.save_to_keyring()
        assert result is False

    def test_save_keyring_success(self):
        """Should save to keyring and update storage_source."""
        creds = Credentials(
            credentials_file=None,
            character_id=12345,
            access_token="test",
            refresh_token="refresh",
            scopes=["scope1"],
        )
        with (
            patch("aria_esi.core.auth.is_keyring_enabled", return_value=True),
            patch("aria_esi.core.auth.store_in_keyring", return_value=True) as mock_store,
        ):
            result = creds.save_to_keyring()

        assert result is True
        assert creds.storage_source == "keyring"
        # Verify data passed to store_in_keyring
        call_args = mock_store.call_args
        assert call_args[0][0] == 12345  # character_id
        assert call_args[0][1]["access_token"] == "test"

    def test_save_keyring_failure(self):
        """Should return False when store fails."""
        creds = Credentials(
            credentials_file=None,
            character_id=12345,
            access_token="test",
        )
        with (
            patch("aria_esi.core.auth.is_keyring_enabled", return_value=True),
            patch("aria_esi.core.auth.store_in_keyring", return_value=False),
        ):
            result = creds.save_to_keyring()

        assert result is False
        assert creds.storage_source == "file"  # Unchanged
