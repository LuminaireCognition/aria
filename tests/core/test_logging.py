"""
Tests for ARIA ESI Structured Logging.

Tests logger configuration, formatters, and utility functions.
"""

from __future__ import annotations

import logging
from unittest.mock import patch, MagicMock

import pytest


# =============================================================================
# AriaFormatter Tests
# =============================================================================


class TestAriaFormatter:
    """Test AriaFormatter class."""

    def test_text_format_basic(self):
        """Text format includes level and module."""
        from aria_esi.core.logging import AriaFormatter

        formatter = AriaFormatter(json_output=False)

        record = logging.LogRecord(
            name="aria_esi.test.module",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)

        assert "ARIA INFO" in formatted
        assert "module" in formatted
        assert "Test message" in formatted

    def test_text_format_with_exception(self):
        """Text format includes exception info."""
        from aria_esi.core.logging import AriaFormatter

        formatter = AriaFormatter(json_output=False)

        try:
            raise ValueError("Test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="aria_esi.test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=10,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )

        formatted = formatter.format(record)

        assert "ValueError" in formatted
        assert "Test error" in formatted

    def test_json_format_basic(self):
        """JSON format produces valid JSON."""
        import json

        from aria_esi.core.logging import AriaFormatter

        formatter = AriaFormatter(json_output=True)

        record = logging.LogRecord(
            name="aria_esi.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)
        data = json.loads(formatted)

        assert data["level"] == "INFO"
        assert data["logger"] == "aria_esi.test"
        assert data["message"] == "Test message"
        assert "timestamp" in data

    def test_json_format_with_extra(self):
        """JSON format includes extra fields."""
        import json

        from aria_esi.core.logging import AriaFormatter

        formatter = AriaFormatter(json_output=True)

        record = logging.LogRecord(
            name="aria_esi.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.custom_field = "custom_value"

        formatted = formatter.format(record)
        data = json.loads(formatted)

        assert data["custom_field"] == "custom_value"

    def test_module_name_extraction(self):
        """Extracts last part of dotted module name."""
        from aria_esi.core.logging import AriaFormatter

        formatter = AriaFormatter(json_output=False)

        record = logging.LogRecord(
            name="aria_esi.services.navigation.router",
            level=logging.DEBUG,
            pathname="router.py",
            lineno=10,
            msg="Routing",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)

        assert "router" in formatted


# =============================================================================
# get_logger Tests
# =============================================================================


class TestGetLogger:
    """Test get_logger function."""

    def test_returns_logger(self):
        """get_logger returns a Logger instance."""
        from aria_esi.core.logging import get_logger

        logger = get_logger("test.module.unique1")

        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.module.unique1"

    def test_caches_loggers(self):
        """get_logger returns cached logger on subsequent calls."""
        from aria_esi.core.logging import get_logger

        logger1 = get_logger("test.module.unique2")
        logger2 = get_logger("test.module.unique2")

        assert logger1 is logger2

    def test_logger_does_not_propagate(self):
        """Logger does not propagate to root."""
        from aria_esi.core.logging import get_logger

        logger = get_logger("test.module.unique3")

        assert logger.propagate is False


# =============================================================================
# Utility Function Tests
# =============================================================================


class TestSetLogLevel:
    """Test set_log_level function."""

    def test_sets_level_on_all_loggers(self):
        """set_log_level updates all cached loggers."""
        from aria_esi.core.logging import get_logger, set_log_level

        # Create a logger
        logger = get_logger("test.module.unique4")

        # Change level
        set_log_level(logging.DEBUG)

        assert logger.level == logging.DEBUG

        # Reset to avoid side effects
        set_log_level(logging.WARNING)


class TestDebugEnabled:
    """Test debug_enabled function."""

    def test_returns_boolean(self):
        """debug_enabled returns a boolean."""
        from aria_esi.core.logging import debug_enabled

        result = debug_enabled()

        assert isinstance(result, bool)


class TestDebugLog:
    """Test debug_log legacy function."""

    def test_debug_log_runs_without_error(self):
        """debug_log executes without raising."""
        from aria_esi.core.logging import debug_log

        # Should not raise
        debug_log("Test legacy debug message")
