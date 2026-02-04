"""
Tests for aria_esi.core.auth

Tests credential loading, resolution, and scope checking.
"""

import json

import pytest


class TestCredentialsFromFile:
    """Tests for Credentials.from_file class method."""

    def test_load_valid_credentials(self, credentials_file, mock_credentials_data):
        from aria_esi.core import Credentials

        creds = Credentials.from_file(credentials_file)

        assert creds.character_id == mock_credentials_data["character_id"]
        assert creds.access_token == mock_credentials_data["access_token"]
        assert creds.refresh_token == mock_credentials_data["refresh_token"]
        assert creds.token_expiry == mock_credentials_data["token_expiry"]
        assert creds.scopes == mock_credentials_data["scopes"]

    def test_missing_file(self, tmp_path):
        from aria_esi.core import Credentials, CredentialsError

        nonexistent = tmp_path / "nonexistent.json"

        with pytest.raises(CredentialsError) as exc_info:
            Credentials.from_file(nonexistent)

        assert "not found" in str(exc_info.value.message)
        assert exc_info.value.action is not None

    def test_invalid_json(self, tmp_path):
        from aria_esi.core import Credentials, CredentialsError

        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json {{{")

        with pytest.raises(CredentialsError) as exc_info:
            Credentials.from_file(bad_file)

        assert "Invalid" in str(exc_info.value.message)

    def test_missing_required_field(self, tmp_path):
        from aria_esi.core import Credentials, CredentialsError

        incomplete = tmp_path / "incomplete.json"
        incomplete.write_text(json.dumps({"character_id": 12345}))  # Missing access_token

        with pytest.raises(CredentialsError) as exc_info:
            Credentials.from_file(incomplete)

        assert "access_token" in str(exc_info.value.message)

    def test_minimal_credentials(self, tmp_path):
        """Test that only required fields are needed."""
        from aria_esi.core import Credentials

        minimal = tmp_path / "minimal.json"
        minimal.write_text(json.dumps({
            "character_id": 99999,
            "access_token": "token123"
        }))

        creds = Credentials.from_file(minimal)
        assert creds.character_id == 99999
        assert creds.access_token == "token123"
        assert creds.refresh_token is None
        assert creds.scopes == []


class TestCredentialsResolve:
    """Tests for Credentials.resolve class method."""

    def test_resolve_from_environment(self, mock_project_with_credentials, monkeypatch):
        from aria_esi.core import Credentials

        monkeypatch.setenv("ARIA_PILOT", "12345678")

        creds = Credentials.resolve(mock_project_with_credentials)

        assert creds is not None
        assert creds.character_id == 12345678

    def test_resolve_from_config(self, mock_project_with_credentials):
        from aria_esi.core import Credentials

        creds = Credentials.resolve(mock_project_with_credentials)

        assert creds is not None
        assert creds.character_id == 12345678

    def test_resolve_no_credentials(self, tmp_path):
        from aria_esi.core import Credentials

        # Create empty project structure
        userdata = tmp_path / "userdata"
        userdata.mkdir()
        (userdata / "credentials").mkdir()

        creds = Credentials.resolve(tmp_path)
        assert creds is None

    def test_resolve_first_credentials_fallback(self, tmp_path):
        """Test that first credentials file is used as fallback."""
        from aria_esi.core import Credentials

        userdata = tmp_path / "userdata"
        userdata.mkdir()
        creds_dir = userdata / "credentials"
        creds_dir.mkdir()

        # Create credentials without config
        creds_file = creds_dir / "99999.json"
        creds_file.write_text(json.dumps({
            "character_id": 99999,
            "access_token": "fallback_token"
        }))

        creds = Credentials.resolve(tmp_path)
        assert creds is not None
        assert creds.character_id == 99999


class TestCredentialsScopeChecking:
    """Tests for scope checking methods."""

    def test_has_scope(self, credentials_file):
        from aria_esi.core import Credentials

        creds = Credentials.from_file(credentials_file)

        assert creds.has_scope("esi-location.read_location.v1") is True
        assert creds.has_scope("esi-nonexistent.scope.v1") is False

    def test_has_any_corp_scope(self, tmp_path):
        from aria_esi.core import Credentials

        # Without corp scopes
        no_corp = tmp_path / "no_corp.json"
        no_corp.write_text(json.dumps({
            "character_id": 11111,
            "access_token": "token",
            "scopes": ["esi-wallet.read_character_wallet.v1"]
        }))
        creds_no_corp = Credentials.from_file(no_corp)
        assert creds_no_corp.has_any_corp_scope() is False

        # With corp scopes
        with_corp = tmp_path / "with_corp.json"
        with_corp.write_text(json.dumps({
            "character_id": 22222,
            "access_token": "token",
            "scopes": ["esi-wallet.read_corporation_wallets.v1"]
        }))
        creds_with_corp = Credentials.from_file(with_corp)
        assert creds_with_corp.has_any_corp_scope() is True

    def test_require_scope_success(self, credentials_file):
        from aria_esi.core import Credentials

        creds = Credentials.from_file(credentials_file)
        # Should not raise
        creds.require_scope("esi-location.read_location.v1")

    def test_require_scope_failure(self, credentials_file):
        from aria_esi.core import Credentials, CredentialsError

        creds = Credentials.from_file(credentials_file)

        with pytest.raises(CredentialsError) as exc_info:
            creds.require_scope("esi-nonexistent.scope.v1")

        assert "Missing required scope" in str(exc_info.value.message)

    def test_get_personal_scopes(self, credentials_file):
        from aria_esi.core import Credentials

        creds = Credentials.from_file(credentials_file)
        personal = creds.get_personal_scopes()

        # All scopes in fixture are personal (no "corporation" in name)
        assert len(personal) == 4
        assert all("corporation" not in s for s in personal)

    def test_get_corp_scopes(self, tmp_path):
        from aria_esi.core import Credentials

        mixed = tmp_path / "mixed.json"
        mixed.write_text(json.dumps({
            "character_id": 33333,
            "access_token": "token",
            "scopes": [
                "esi-wallet.read_character_wallet.v1",
                "esi-wallet.read_corporation_wallets.v1"
            ]
        }))

        creds = Credentials.from_file(mixed)
        corp_scopes = creds.get_corp_scopes()

        assert len(corp_scopes) == 1
        assert "corporation" in corp_scopes[0]


class TestCredentialsErrorToDict:
    """Tests for CredentialsError.to_dict method."""

    def test_basic_error(self):
        from aria_esi.core import CredentialsError

        error = CredentialsError("Test error message")
        result = error.to_dict()

        assert result["error"] == "credentials_error"
        assert result["message"] == "Test error message"
        assert "action" not in result

    def test_error_with_action(self):
        from aria_esi.core import CredentialsError

        error = CredentialsError(
            "Token expired",
            action="Refresh the token",
            command="aria-refresh"
        )
        result = error.to_dict()

        assert result["error"] == "credentials_error"
        assert result["message"] == "Token expired"
        assert result["action"] == "Refresh the token"
        assert result["command"] == "aria-refresh"


class TestGetCredentialsHelper:
    """Tests for get_credentials helper function."""

    def test_get_credentials_success(self, mock_project_with_credentials):
        from aria_esi.core import get_credentials

        creds = get_credentials(mock_project_with_credentials)
        assert creds is not None
        assert creds.character_id == 12345678

    def test_get_credentials_require_true(self, tmp_path):
        from aria_esi.core import CredentialsError, get_credentials

        userdata = tmp_path / "userdata"
        userdata.mkdir()
        (userdata / "credentials").mkdir()

        with pytest.raises(CredentialsError):
            get_credentials(tmp_path, require=True)

    def test_get_credentials_require_false(self, tmp_path):
        from aria_esi.core import get_credentials

        userdata = tmp_path / "userdata"
        userdata.mkdir()
        (userdata / "credentials").mkdir()

        creds = get_credentials(tmp_path, require=False)
        assert creds is None


class TestIsPlayerCorp:
    """Tests for is_player_corp helper function."""

    def test_player_corp(self):
        from aria_esi.core import is_player_corp

        assert is_player_corp(98000001) is True
        assert is_player_corp(2000000) is True
        assert is_player_corp(5000000) is True

    def test_npc_corp(self):
        from aria_esi.core import is_player_corp

        assert is_player_corp(1000001) is False
        assert is_player_corp(1000125) is False  # Federal Navy Academy
        assert is_player_corp(1999999) is False
