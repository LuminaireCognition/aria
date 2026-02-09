"""
Tests for Core Package Initialization.

Tests module exports and accessibility of core components.
"""

from __future__ import annotations


# =============================================================================
# Module Exports Tests
# =============================================================================


class TestModuleExports:
    """Test __all__ exports are accessible."""

    def test_all_defined(self):
        """__all__ is defined and non-empty."""
        import aria_esi.core as core

        assert hasattr(core, "__all__")
        assert len(core.__all__) > 0

    def test_all_exports_accessible(self):
        """All items in __all__ are importable."""
        import aria_esi.core as core

        for name in core.__all__:
            assert hasattr(core, name), f"Missing export: {name}"


# =============================================================================
# Client Exports Tests
# =============================================================================


class TestClientExports:
    """Test ESI client exports."""

    def test_esi_client_accessible(self):
        """ESIClient can be imported."""
        from aria_esi.core import ESIClient

        assert ESIClient is not None

    def test_esi_error_accessible(self):
        """ESIError can be imported."""
        from aria_esi.core import ESIError

        assert ESIError is not None


# =============================================================================
# Auth Exports Tests
# =============================================================================


class TestAuthExports:
    """Test authentication exports."""

    def test_credentials_accessible(self):
        """Credentials can be imported."""
        from aria_esi.core import Credentials

        assert Credentials is not None

    def test_credentials_error_accessible(self):
        """CredentialsError can be imported."""
        from aria_esi.core import CredentialsError

        assert CredentialsError is not None

    def test_get_credentials_accessible(self):
        """get_credentials can be imported."""
        from aria_esi.core import get_credentials

        assert callable(get_credentials)

    def test_get_authenticated_client_accessible(self):
        """get_authenticated_client can be imported."""
        from aria_esi.core import get_authenticated_client

        assert callable(get_authenticated_client)


# =============================================================================
# Retry Exports Tests
# =============================================================================


class TestRetryExports:
    """Test retry functionality exports."""

    def test_retryable_esi_error_accessible(self):
        """RetryableESIError can be imported."""
        from aria_esi.core import RetryableESIError

        assert RetryableESIError is not None

    def test_non_retryable_esi_error_accessible(self):
        """NonRetryableESIError can be imported."""
        from aria_esi.core import NonRetryableESIError

        assert NonRetryableESIError is not None

    def test_esi_retry_accessible(self):
        """esi_retry decorator can be imported."""
        from aria_esi.core import esi_retry

        assert callable(esi_retry)

    def test_retry_status_functions_accessible(self):
        """Retry status functions can be imported."""
        from aria_esi.core import get_retry_status, is_retry_enabled

        assert callable(get_retry_status)
        assert callable(is_retry_enabled)


# =============================================================================
# Formatter Exports Tests
# =============================================================================


class TestFormatterExports:
    """Test formatter exports."""

    def test_format_isk_accessible(self):
        """format_isk can be imported."""
        from aria_esi.core import format_isk

        assert callable(format_isk)

    def test_format_duration_accessible(self):
        """format_duration can be imported."""
        from aria_esi.core import format_duration

        assert callable(format_duration)

    def test_format_security_accessible(self):
        """format_security can be imported."""
        from aria_esi.core import format_security

        assert callable(format_security)

    def test_datetime_functions_accessible(self):
        """DateTime utility functions can be imported."""
        from aria_esi.core import (
            format_datetime,
            get_utc_now,
            get_utc_timestamp,
            parse_datetime,
            time_since,
            time_until,
        )

        assert callable(format_datetime)
        assert callable(parse_datetime)
        assert callable(get_utc_now)
        assert callable(get_utc_timestamp)
        assert callable(time_until)
        assert callable(time_since)

    def test_eft_formatters_accessible(self):
        """EFT format functions can be imported."""
        from aria_esi.core import (
            format_eft_cargo,
            format_eft_drone,
            format_eft_header,
        )

        assert callable(format_eft_header)
        assert callable(format_eft_drone)
        assert callable(format_eft_cargo)


# =============================================================================
# Constants Exports Tests
# =============================================================================


class TestConstantsExports:
    """Test constants exports."""

    def test_esi_constants_accessible(self):
        """ESI constants can be imported."""
        from aria_esi.core import ESI_BASE_URL, ESI_DATASOURCE

        assert isinstance(ESI_BASE_URL, str)
        assert isinstance(ESI_DATASOURCE, str)

    def test_trade_hub_constants_accessible(self):
        """Trade hub constants can be imported."""
        from aria_esi.core import (
            STATION_NAMES,
            TRADE_HUB_REGIONS,
            TRADE_HUB_STATIONS,
        )

        assert isinstance(TRADE_HUB_REGIONS, dict)
        assert isinstance(TRADE_HUB_STATIONS, dict)
        assert isinstance(STATION_NAMES, dict)

    def test_security_constants_accessible(self):
        """Security threshold constants can be imported."""
        from aria_esi.core import HIGH_SEC_THRESHOLD, LOW_SEC_THRESHOLD

        assert isinstance(HIGH_SEC_THRESHOLD, (int, float))
        assert isinstance(LOW_SEC_THRESHOLD, (int, float))


# =============================================================================
# Logging Exports Tests
# =============================================================================


class TestLoggingExports:
    """Test logging exports."""

    def test_get_logger_accessible(self):
        """get_logger can be imported."""
        from aria_esi.core import get_logger

        assert callable(get_logger)

    def test_set_log_level_accessible(self):
        """set_log_level can be imported."""
        from aria_esi.core import set_log_level

        assert callable(set_log_level)

    def test_debug_functions_accessible(self):
        """Debug utility functions can be imported."""
        from aria_esi.core import debug_enabled, debug_log

        assert callable(debug_enabled)
        assert callable(debug_log)


# =============================================================================
# Path Security Exports Tests
# =============================================================================


class TestPathSecurityExports:
    """Test path security exports."""

    def test_path_validation_error_accessible(self):
        """PathValidationError can be imported."""
        from aria_esi.core import PathValidationError

        assert PathValidationError is not None

    def test_validation_functions_accessible(self):
        """Path validation functions can be imported."""
        from aria_esi.core import (
            safe_read_persona_file,
            validate_path,
            validate_persona_file_path,
            validate_persona_path,
            validate_pilot_id,
        )

        assert callable(validate_path)
        assert callable(validate_persona_path)
        assert callable(validate_persona_file_path)
        assert callable(safe_read_persona_file)
        assert callable(validate_pilot_id)

    def test_path_security_constants_accessible(self):
        """Path security constants can be imported."""
        from aria_esi.core import (
            ALLOWED_EXTENSIONS,
            DEFAULT_MAX_FILE_SIZE,
            PERSONA_ALLOWED_PREFIXES,
            PILOT_ID_PATTERN,
        )

        assert ALLOWED_EXTENSIONS is not None
        assert DEFAULT_MAX_FILE_SIZE is not None
        assert PERSONA_ALLOWED_PREFIXES is not None
        assert PILOT_ID_PATTERN is not None


# =============================================================================
# Data Integrity Exports Tests
# =============================================================================


class TestDataIntegrityExports:
    """Test data integrity exports."""

    def test_integrity_error_accessible(self):
        """IntegrityError can be imported."""
        from aria_esi.core import IntegrityError

        assert IntegrityError is not None

    def test_checksum_functions_accessible(self):
        """Checksum functions can be imported."""
        from aria_esi.core import compute_sha256, verify_checksum

        assert callable(compute_sha256)
        assert callable(verify_checksum)

    def test_manifest_functions_accessible(self):
        """Manifest functions can be imported."""
        from aria_esi.core import load_data_manifest

        assert callable(load_data_manifest)

    def test_sde_functions_accessible(self):
        """SDE integrity functions can be imported."""
        from aria_esi.core import get_pinned_sde_url, verify_sde_integrity

        assert callable(get_pinned_sde_url)
        assert callable(verify_sde_integrity)

    def test_eos_functions_accessible(self):
        """EOS integrity functions can be imported."""
        from aria_esi.core import (
            get_eos_repository,
            get_pinned_eos_commit,
            verify_eos_commit,
        )

        assert callable(get_pinned_eos_commit)
        assert callable(get_eos_repository)
        assert callable(verify_eos_commit)

    def test_universe_graph_functions_accessible(self):
        """Universe graph integrity functions can be imported."""
        from aria_esi.core import (
            get_universe_graph_checksum,
            update_universe_graph_checksum,
            verify_universe_graph_integrity,
        )

        assert callable(get_universe_graph_checksum)
        assert callable(verify_universe_graph_integrity)
        assert callable(update_universe_graph_checksum)


# =============================================================================
# Keyring Exports Tests
# =============================================================================


class TestKeyringExports:
    """Test keyring functionality exports."""

    def test_keyring_constants_accessible(self):
        """Keyring availability constants can be imported."""
        from aria_esi.core import KEYRING_AVAILABLE, KEYRING_BACKEND

        assert isinstance(KEYRING_AVAILABLE, bool)
        # KEYRING_BACKEND can be None or a string

    def test_keyring_functions_accessible(self):
        """Keyring functions can be imported."""
        from aria_esi.core import (
            delete_from_keyring,
            get_keyring_status,
            get_keyring_store,
            is_keyring_enabled,
            load_from_keyring,
            store_in_keyring,
        )

        assert callable(is_keyring_enabled)
        assert callable(get_keyring_status)
        assert callable(get_keyring_store)
        assert callable(store_in_keyring)
        assert callable(load_from_keyring)
        assert callable(delete_from_keyring)

    def test_keyring_credential_store_accessible(self):
        """KeyringCredentialStore can be imported."""
        from aria_esi.core import KeyringCredentialStore

        assert KeyringCredentialStore is not None
