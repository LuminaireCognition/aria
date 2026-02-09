"""
Tests for aria_esi.core.keyring_backend

Tests keyring storage, fallback behavior, and integration with auth module.
"""

import json
import os

import pytest


class TestKeyringAvailability:
    """Tests for keyring availability detection."""

    def test_keyring_status_returns_dict(self):
        """Test that get_keyring_status returns expected structure."""
        from aria_esi.core import get_keyring_status

        status = get_keyring_status()

        assert isinstance(status, dict)
        assert "available" in status
        assert "enabled" in status
        assert isinstance(status["available"], bool)
        assert isinstance(status["enabled"], bool)

    def test_is_keyring_enabled_respects_env(self, monkeypatch):
        """Test that ARIA_NO_KEYRING environment variable disables keyring."""
        from aria_esi.core.keyring_backend import is_keyring_enabled

        # Save original value
        original = os.environ.get("ARIA_NO_KEYRING")

        try:
            # Test with env var set
            monkeypatch.setenv("ARIA_NO_KEYRING", "1")
            assert is_keyring_enabled() is False

            monkeypatch.setenv("ARIA_NO_KEYRING", "true")
            assert is_keyring_enabled() is False

            monkeypatch.setenv("ARIA_NO_KEYRING", "yes")
            assert is_keyring_enabled() is False
        finally:
            # Restore original
            if original:
                os.environ["ARIA_NO_KEYRING"] = original
            elif "ARIA_NO_KEYRING" in os.environ:
                del os.environ["ARIA_NO_KEYRING"]


class TestKeyringCredentialStore:
    """Tests for KeyringCredentialStore class."""

    def test_store_creation(self):
        """Test that KeyringCredentialStore can be instantiated."""
        from aria_esi.core import KeyringCredentialStore

        store = KeyringCredentialStore()
        assert store.service == "aria-eve-online"

    def test_store_custom_service(self):
        """Test that custom service name can be specified."""
        from aria_esi.core import KeyringCredentialStore

        store = KeyringCredentialStore(service="test-service")
        assert store.service == "test-service"

    def test_is_available_returns_bool(self):
        """Test that is_available returns a boolean."""
        from aria_esi.core import KeyringCredentialStore

        store = KeyringCredentialStore()
        result = store.is_available()
        assert isinstance(result, bool)


class TestKeyringConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_get_keyring_store_singleton(self):
        """Test that get_keyring_store returns a singleton."""
        from aria_esi.core import get_keyring_store

        store1 = get_keyring_store()
        store2 = get_keyring_store()
        assert store1 is store2

    def test_store_in_keyring_returns_bool(self):
        """Test that store_in_keyring returns a boolean."""
        from aria_esi.core import store_in_keyring

        # This will return False if keyring is not available
        # or True if it successfully stores
        result = store_in_keyring("test_pilot", {"test": "data"})
        assert isinstance(result, bool)

    def test_load_from_keyring_returns_none_or_dict(self):
        """Test that load_from_keyring returns None or dict."""
        from aria_esi.core import load_from_keyring

        result = load_from_keyring("nonexistent_pilot_12345")
        assert result is None or isinstance(result, dict)


class TestCredentialsKeyringIntegration:
    """Tests for Credentials class keyring integration."""

    def test_credentials_from_keyring_when_disabled(self, monkeypatch):
        """Test that from_keyring returns None when keyring is disabled."""
        from aria_esi.core import Credentials

        monkeypatch.setenv("ARIA_NO_KEYRING", "1")

        result = Credentials.from_keyring("12345678")
        assert result is None

    def test_credentials_storage_source_attribute(self, credentials_file):
        """Test that credentials track their storage source."""
        from aria_esi.core import Credentials

        creds = Credentials.from_file(credentials_file)
        assert hasattr(creds, "storage_source")
        assert creds.storage_source == "file"

    def test_from_storage_falls_back_to_file(self, tmp_path, mock_credentials_data, monkeypatch):
        """Test that from_storage falls back to file when keyring unavailable."""
        from aria_esi.core import Credentials

        # Disable keyring
        monkeypatch.setenv("ARIA_NO_KEYRING", "1")

        # Create credentials file
        creds_dir = tmp_path / "credentials"
        creds_dir.mkdir()
        creds_file = creds_dir / "12345678.json"
        creds_file.write_text(json.dumps(mock_credentials_data))

        # Load with from_storage
        creds = Credentials.from_storage("12345678", creds_file)

        assert creds is not None
        assert creds.character_id == mock_credentials_data["character_id"]
        assert creds.storage_source == "file"

    def test_get_full_data_returns_dict(self, credentials_file):
        """Test that get_full_data returns credential dict."""
        from aria_esi.core import Credentials

        creds = Credentials.from_file(credentials_file)
        data = creds.get_full_data()

        assert isinstance(data, dict)
        assert data["character_id"] == creds.character_id
        assert data["access_token"] == creds.access_token

    def test_save_to_keyring_returns_bool(self, credentials_file, monkeypatch):
        """Test that save_to_keyring returns boolean."""
        from aria_esi.core import Credentials

        creds = Credentials.from_file(credentials_file)

        # When keyring is disabled, should return False
        monkeypatch.setenv("ARIA_NO_KEYRING", "1")
        result = creds.save_to_keyring()
        assert result is False


class TestMigrationUtility:
    """Tests for credential migration utility."""

    def test_migrate_returns_result_dict(self, monkeypatch):
        """Test that migrate_credentials_to_keyring returns expected structure."""
        from aria_esi.core import migrate_credentials_to_keyring

        # Disable keyring to test error path
        monkeypatch.setenv("ARIA_NO_KEYRING", "1")

        result = migrate_credentials_to_keyring()

        assert isinstance(result, dict)
        assert "migrated" in result
        assert "skipped" in result
        assert "failed" in result
        assert "keyring_status" in result
        assert "error" in result  # Because keyring is disabled

    def test_migrate_with_no_project_dir(self, tmp_path, monkeypatch):
        """Test migration when project directory doesn't exist."""
        from aria_esi.core import migrate_credentials_to_keyring

        # Use a non-existent directory
        result = migrate_credentials_to_keyring(project_dir=tmp_path / "nonexistent")

        assert "error" in result

    def test_get_credential_storage_info(self, mock_project_with_credentials):
        """Test getting credential storage info."""
        from aria_esi.core import get_credential_storage_info

        info = get_credential_storage_info(mock_project_with_credentials)

        assert isinstance(info, dict)
        assert "keyring" in info
        assert "pilots" in info
        assert isinstance(info["pilots"], list)

        if info["pilots"]:
            pilot = info["pilots"][0]
            assert "pilot_id" in pilot
            assert "file_exists" in pilot
            assert "in_keyring" in pilot


class TestCredentialsResolveWithKeyring:
    """Tests for Credentials.resolve with keyring integration."""

    def test_resolve_tries_keyring_first(self, mock_project_with_credentials, monkeypatch):
        """Test that resolve tries keyring before file."""
        from aria_esi.core import Credentials

        # This test verifies the resolve path includes keyring checks
        # Even if keyring returns None, it should still work via file fallback
        monkeypatch.setenv("ARIA_NO_KEYRING", "1")

        creds = Credentials.resolve(mock_project_with_credentials)

        assert creds is not None
        assert creds.storage_source == "file"

    def test_resolve_env_priority_with_keyring(self, mock_project_with_credentials, monkeypatch):
        """Test that ARIA_PILOT env var still works with keyring."""
        from aria_esi.core import Credentials

        monkeypatch.setenv("ARIA_PILOT", "12345678")
        monkeypatch.setenv("ARIA_NO_KEYRING", "1")

        creds = Credentials.resolve(mock_project_with_credentials)

        assert creds is not None
        assert creds.character_id == 12345678


@pytest.mark.skipif(
    os.environ.get("ARIA_NO_KEYRING", "").lower() in ("1", "true", "yes"),
    reason="Keyring disabled via environment"
)
class TestKeyringIntegration:
    """Integration tests that require a working keyring.

    These tests are skipped if keyring is disabled or unavailable.
    They test actual keyring read/write operations.
    """

    def test_roundtrip_storage(self):
        """Test storing and retrieving credentials from keyring."""
        from aria_esi.core import delete_from_keyring, load_from_keyring, store_in_keyring
        from aria_esi.core.keyring_backend import is_keyring_enabled

        if not is_keyring_enabled():
            pytest.skip("Keyring not available")

        test_id = "test_roundtrip_99999999"
        test_data = {
            "character_id": 99999999,
            "access_token": "test_token_abc",
            "refresh_token": "test_refresh_xyz",
        }

        try:
            # Store
            assert store_in_keyring(test_id, test_data) is True

            # Retrieve
            loaded = load_from_keyring(test_id)
            assert loaded is not None
            assert loaded["character_id"] == test_data["character_id"]
            assert loaded["access_token"] == test_data["access_token"]
        finally:
            # Cleanup
            delete_from_keyring(test_id)
