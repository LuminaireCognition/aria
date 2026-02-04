"""
Tests for core keyring backend module.
"""

from __future__ import annotations

import os
import warnings
from unittest.mock import patch

import pytest

import aria_esi.core.keyring_backend as keyring_backend
from aria_esi.core.keyring_backend import (
    KEYRING_SERVICE,
    KeyringCredentialStore,
    _warn_keyring_unavailable,
    get_keyring_status,
    get_keyring_store,
    is_keyring_enabled,
)

# Environment variable name for disabling keyring (matches config.py)
NO_KEYRING_ENV = "ARIA_NO_KEYRING"


class TestIsKeyringEnabled:
    """Tests for is_keyring_enabled function."""

    def test_disabled_by_env_var_1(self):
        """Should be disabled when ARIA_NO_KEYRING=1."""
        with patch.dict(os.environ, {NO_KEYRING_ENV: "1"}):
            assert is_keyring_enabled() is False

    def test_disabled_by_env_var_true(self):
        """Should be disabled when ARIA_NO_KEYRING=true."""
        with patch.dict(os.environ, {NO_KEYRING_ENV: "true"}):
            assert is_keyring_enabled() is False

    def test_disabled_by_env_var_yes(self):
        """Should be disabled when ARIA_NO_KEYRING=yes."""
        with patch.dict(os.environ, {NO_KEYRING_ENV: "yes"}):
            assert is_keyring_enabled() is False

    def test_disabled_by_env_var_case_insensitive(self):
        """Should be case insensitive."""
        with patch.dict(os.environ, {NO_KEYRING_ENV: "TRUE"}):
            assert is_keyring_enabled() is False


class TestGetKeyringStatus:
    """Tests for get_keyring_status function."""

    def test_returns_dict(self):
        """Should return a dictionary."""
        status = get_keyring_status()
        assert isinstance(status, dict)

    def test_has_required_keys(self):
        """Should have all required keys."""
        status = get_keyring_status()
        required_keys = {"available", "backend", "reason", "enabled", "env_disabled"}
        assert set(status.keys()) == required_keys

    def test_env_disabled_reflects_env_var(self):
        """env_disabled should reflect environment variable."""
        with patch.dict(os.environ, {NO_KEYRING_ENV: "1"}):
            status = get_keyring_status()
            assert status["env_disabled"] is True

    def test_env_disabled_false_when_unset(self):
        """env_disabled should be False when env var unset."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove the env var if present
            os.environ.pop(NO_KEYRING_ENV, None)
            status = get_keyring_status()
            assert status["env_disabled"] is False


class TestKeyringCredentialStore:
    """Tests for KeyringCredentialStore class."""

    def test_init_default_service(self):
        """Should use default service name."""
        store = KeyringCredentialStore()
        assert store.service == KEYRING_SERVICE

    def test_init_custom_service(self):
        """Should accept custom service name."""
        store = KeyringCredentialStore(service="custom-service")
        assert store.service == "custom-service"

    def test_is_available_returns_bool(self):
        """is_available should return boolean."""
        store = KeyringCredentialStore()
        result = store.is_available()
        assert isinstance(result, bool)

    def test_get_credentials_disabled_returns_none(self):
        """get_credentials should return None when keyring disabled."""
        store = KeyringCredentialStore()
        with patch("aria_esi.core.keyring_backend.is_keyring_enabled", return_value=False):
            result = store.get_credentials("12345")
        assert result is None

    def test_set_credentials_disabled_returns_false(self):
        """set_credentials should return False when keyring disabled."""
        store = KeyringCredentialStore()
        with patch("aria_esi.core.keyring_backend.is_keyring_enabled", return_value=False):
            result = store.set_credentials("12345", {"access_token": "test"})
        assert result is False

    def test_delete_credentials_disabled_returns_false(self):
        """delete_credentials should return False when keyring disabled."""
        store = KeyringCredentialStore()
        with patch("aria_esi.core.keyring_backend.is_keyring_enabled", return_value=False):
            result = store.delete_credentials("12345")
        assert result is False

    def test_has_credentials_disabled_returns_false(self):
        """has_credentials should return False when keyring disabled."""
        store = KeyringCredentialStore()
        with patch("aria_esi.core.keyring_backend.is_keyring_enabled", return_value=False):
            result = store.has_credentials("12345")
        assert result is False


class TestGetKeyringStore:
    """Tests for get_keyring_store singleton function."""

    def test_returns_store(self):
        """Should return a KeyringCredentialStore."""
        store = get_keyring_store()
        assert isinstance(store, KeyringCredentialStore)

    def test_returns_same_instance(self):
        """Should return singleton instance."""
        store1 = get_keyring_store()
        store2 = get_keyring_store()
        assert store1 is store2


class TestKeyringConstants:
    """Tests for module constants."""

    def test_keyring_service_defined(self):
        """KEYRING_SERVICE should be defined."""
        assert KEYRING_SERVICE == "aria-eve-online"

    def test_no_keyring_env_defined(self):
        """NO_KEYRING_ENV should be defined."""
        assert NO_KEYRING_ENV == "ARIA_NO_KEYRING"


class TestKeyringWarning:
    """Tests for keyring unavailability warnings."""

    def test_warn_keyring_unavailable_issues_warning(self):
        """Should issue UserWarning when keyring unavailable."""
        # Reset warning state for this test
        keyring_backend._KEYRING_WARNING_ISSUED = False

        with (
            patch.object(keyring_backend, "KEYRING_AVAILABLE", False),
            patch.object(keyring_backend, "KEYRING_REASON", "test reason"),
            patch.dict(os.environ, {}, clear=True),
        ):
            # Remove env var if present
            os.environ.pop(NO_KEYRING_ENV, None)

            with pytest.warns(UserWarning, match="SECURITY"):
                _warn_keyring_unavailable()

    def test_warn_keyring_unavailable_only_once(self):
        """Should only issue warning once per session."""
        # Reset warning state for this test
        keyring_backend._KEYRING_WARNING_ISSUED = False

        with (
            patch.object(keyring_backend, "KEYRING_AVAILABLE", False),
            patch.object(keyring_backend, "KEYRING_REASON", "test reason"),
            patch.dict(os.environ, {}, clear=True),
        ):
            os.environ.pop(NO_KEYRING_ENV, None)

            # First call should warn
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                _warn_keyring_unavailable()
                assert len(w) == 1

            # Second call should not warn (already issued)
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                _warn_keyring_unavailable()
                assert len(w) == 0

    def test_warn_keyring_unavailable_suppressed_by_env(self):
        """Should not warn when ARIA_NO_KEYRING is set."""
        # Reset warning state for this test
        keyring_backend._KEYRING_WARNING_ISSUED = False

        with (
            patch.object(keyring_backend, "KEYRING_AVAILABLE", False),
            patch.object(keyring_backend, "KEYRING_REASON", "test reason"),
            patch.dict(os.environ, {NO_KEYRING_ENV: "1"}),
        ):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                _warn_keyring_unavailable()
                assert len(w) == 0
