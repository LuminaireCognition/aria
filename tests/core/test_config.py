"""
Tests for centralized configuration module.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest import mock

import pytest

from aria_esi.core.config import (
    AriaSettings,
    get_settings,
    is_debug_enabled,
    is_json_logging,
    is_keyring_disabled,
    is_retry_disabled,
    reset_settings,
)


@pytest.fixture(autouse=True)
def clean_settings():
    """Reset settings cache before and after each test."""
    reset_settings()
    yield
    reset_settings()


class TestAriaSettings:
    """Test AriaSettings class."""

    def test_default_values(self):
        """Test that default values are correct."""
        with mock.patch.dict(os.environ, {}, clear=True):
            settings = AriaSettings()

            assert settings.log_level == "WARNING"
            assert settings.debug is False
            assert settings.log_json is False
            assert settings.pilot is None
            assert settings.no_keyring is False
            assert settings.no_retry is False
            assert settings.allow_unsafe_paths is False
            assert settings.allow_unpinned is False
            assert settings.mcp_bypass_policy is False
            assert settings.universe_log_level == "WARNING"
            assert settings.debug_timing is False

    def test_log_level_from_env(self):
        """Test log level parsing from environment."""
        with mock.patch.dict(os.environ, {"ARIA_LOG_LEVEL": "DEBUG"}, clear=True):
            settings = AriaSettings()
            assert settings.log_level == "DEBUG"
            assert settings.effective_log_level == "DEBUG"

    def test_log_level_case_insensitive(self):
        """Test log level is case-insensitive."""
        with mock.patch.dict(os.environ, {"ARIA_LOG_LEVEL": "debug"}, clear=True):
            settings = AriaSettings()
            assert settings.log_level == "DEBUG"

    def test_debug_legacy_flag(self):
        """Test legacy ARIA_DEBUG flag enables debug mode."""
        with mock.patch.dict(os.environ, {"ARIA_DEBUG": "1"}, clear=True):
            settings = AriaSettings()
            assert settings.debug is True
            assert settings.effective_log_level == "DEBUG"

    def test_debug_legacy_does_not_override_explicit_level(self):
        """Test explicit log level takes precedence over ARIA_DEBUG."""
        env = {"ARIA_LOG_LEVEL": "ERROR", "ARIA_DEBUG": "1"}
        with mock.patch.dict(os.environ, env, clear=True):
            settings = AriaSettings()
            # debug flag is set but log_level was explicitly set to ERROR
            assert settings.debug is True
            assert settings.log_level == "ERROR"
            # effective_log_level respects explicit setting
            assert settings.effective_log_level == "ERROR"

    def test_pilot_from_env(self):
        """Test pilot ID from environment."""
        with mock.patch.dict(os.environ, {"ARIA_PILOT": "12345678"}, clear=True):
            settings = AriaSettings()
            assert settings.pilot == "12345678"

    def test_boolean_flags(self):
        """Test various boolean flags."""
        env = {
            "ARIA_NO_KEYRING": "true",
            "ARIA_NO_RETRY": "1",
            "ARIA_ALLOW_UNSAFE_PATHS": "yes",
            "ARIA_ALLOW_UNPINNED": "TRUE",
            "ARIA_MCP_BYPASS_POLICY": "True",
            "ARIA_LOG_JSON": "1",
            "ARIA_DEBUG_TIMING": "true",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            settings = AriaSettings()
            assert settings.no_keyring is True
            assert settings.no_retry is True
            assert settings.allow_unsafe_paths is True
            assert settings.allow_unpinned is True
            assert settings.mcp_bypass_policy is True
            assert settings.log_json is True
            assert settings.debug_timing is True

    def test_path_fields(self):
        """Test path fields are parsed as Path objects."""
        env = {
            "ARIA_MCP_POLICY": "/custom/policy.json",
            "ARIA_UNIVERSE_GRAPH": "/data/universe.pkl",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            settings = AriaSettings()
            assert settings.mcp_policy == Path("/custom/policy.json")
            assert settings.universe_graph == Path("/data/universe.pkl")

    def test_data_paths(self):
        """Test data path properties return instance-local paths."""
        with mock.patch.dict(os.environ, {}, clear=True):
            settings = AriaSettings()
            # All data paths are under instance_root/cache/
            assert settings.eos_data_path == settings.instance_root / "cache" / "eos-data"
            assert settings.db_path == settings.instance_root / "cache" / "aria.db"
            assert settings.killmail_db_path == settings.instance_root / "cache" / "killmails.db"
            assert settings.cache_dir == settings.instance_root / "cache"

    def test_instance_root_default(self):
        """Test instance_root defaults to project root."""
        with mock.patch.dict(os.environ, {}, clear=True):
            settings = AriaSettings()
            # Instance root should be a directory (project root or cwd)
            assert settings.instance_root.is_dir() or not settings.instance_root.exists()

    def test_instance_root_override(self):
        """Test instance_root can be overridden via ARIA_INSTANCE_ROOT."""
        with mock.patch.dict(os.environ, {"ARIA_INSTANCE_ROOT": "/custom/root"}, clear=True):
            # Need to reload the module to pick up the env var change
            from aria_esi.core import config
            config.reset_settings()
            # Manually override the module-level constant for this test
            original_root = config._INSTANCE_ROOT
            config._INSTANCE_ROOT = Path("/custom/root")
            try:
                settings = AriaSettings()
                assert settings.instance_root == Path("/custom/root")
                assert settings.db_path == Path("/custom/root/cache/aria.db")
            finally:
                config._INSTANCE_ROOT = original_root

    def test_log_level_int(self):
        """Test log_level_int returns correct logging constant."""
        import logging

        with mock.patch.dict(os.environ, {"ARIA_LOG_LEVEL": "DEBUG"}, clear=True):
            settings = AriaSettings()
            assert settings.log_level_int == logging.DEBUG

        with mock.patch.dict(os.environ, {"ARIA_LOG_LEVEL": "ERROR"}, clear=True):
            settings = AriaSettings()
            assert settings.log_level_int == logging.ERROR

    def test_is_break_glass_enabled(self):
        """Test break-glass mode checking."""
        env = {
            "ARIA_ALLOW_UNSAFE_PATHS": "1",
            "ARIA_ALLOW_UNPINNED": "1",
            "ARIA_MCP_BYPASS_POLICY": "1",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            settings = AriaSettings()
            assert settings.is_break_glass_enabled("paths") is True
            assert settings.is_break_glass_enabled("integrity") is True
            assert settings.is_break_glass_enabled("policy") is True
            assert settings.is_break_glass_enabled("unknown") is False

    def test_invalid_log_level_rejected(self):
        """Test invalid log level is rejected."""
        with mock.patch.dict(os.environ, {"ARIA_LOG_LEVEL": "INVALID"}, clear=True):
            with pytest.raises(Exception):  # Pydantic validation error
                AriaSettings()


class TestSettingsSingleton:
    """Test singleton accessor functions."""

    def test_get_settings_returns_same_instance(self):
        """Test get_settings returns cached instance."""
        with mock.patch.dict(os.environ, {}, clear=True):
            settings1 = get_settings()
            settings2 = get_settings()
            assert settings1 is settings2

    def test_reset_settings_clears_cache(self):
        """Test reset_settings clears the cache."""
        with mock.patch.dict(os.environ, {"ARIA_LOG_LEVEL": "DEBUG"}, clear=True):
            settings1 = get_settings()
            assert settings1.log_level == "DEBUG"

        reset_settings()

        with mock.patch.dict(os.environ, {"ARIA_LOG_LEVEL": "ERROR"}, clear=True):
            settings2 = get_settings()
            assert settings2.log_level == "ERROR"
            assert settings1 is not settings2


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_is_debug_enabled(self):
        """Test is_debug_enabled function."""
        with mock.patch.dict(os.environ, {"ARIA_LOG_LEVEL": "DEBUG"}, clear=True):
            reset_settings()
            assert is_debug_enabled() is True

        with mock.patch.dict(os.environ, {"ARIA_LOG_LEVEL": "WARNING"}, clear=True):
            reset_settings()
            assert is_debug_enabled() is False

    def test_is_json_logging(self):
        """Test is_json_logging function."""
        with mock.patch.dict(os.environ, {"ARIA_LOG_JSON": "1"}, clear=True):
            reset_settings()
            assert is_json_logging() is True

        with mock.patch.dict(os.environ, {}, clear=True):
            reset_settings()
            assert is_json_logging() is False

    def test_is_keyring_disabled(self):
        """Test is_keyring_disabled function."""
        with mock.patch.dict(os.environ, {"ARIA_NO_KEYRING": "1"}, clear=True):
            reset_settings()
            assert is_keyring_disabled() is True

        with mock.patch.dict(os.environ, {}, clear=True):
            reset_settings()
            assert is_keyring_disabled() is False

    def test_is_retry_disabled(self):
        """Test is_retry_disabled function."""
        with mock.patch.dict(os.environ, {"ARIA_NO_RETRY": "true"}, clear=True):
            reset_settings()
            assert is_retry_disabled() is True

        with mock.patch.dict(os.environ, {}, clear=True):
            reset_settings()
            assert is_retry_disabled() is False
