"""
Tests for break-glass environment variable audit trail.

Security: These tests verify that break-glass overrides are centrally detected
and logged with appropriate severity. See dev/reviews/archive/SECURITY_000.md #8.
"""

from __future__ import annotations

import logging

import pytest

from aria_esi.core.config import AriaSettings, audit_break_glass_state, reset_settings


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    """Reset settings cache between tests."""
    reset_settings()
    yield
    reset_settings()


class TestAuditBreakGlassState:
    """Test break-glass state auditing."""

    def test_no_overrides_returns_empty(self, monkeypatch):
        """No break-glass overrides returns empty set."""
        monkeypatch.delenv("ARIA_ALLOW_UNSAFE_PATHS", raising=False)
        monkeypatch.delenv("ARIA_ALLOW_UNPINNED", raising=False)
        monkeypatch.delenv("ARIA_MCP_BYPASS_POLICY", raising=False)

        active = audit_break_glass_state()

        assert active == set()

    def test_single_override_returns_feature(self, monkeypatch):
        """Single break-glass override returns that feature."""
        monkeypatch.setenv("ARIA_ALLOW_UNSAFE_PATHS", "1")
        monkeypatch.delenv("ARIA_ALLOW_UNPINNED", raising=False)
        monkeypatch.delenv("ARIA_MCP_BYPASS_POLICY", raising=False)

        active = audit_break_glass_state()

        assert active == {"paths"}

    def test_single_override_logs_warning(self, monkeypatch, caplog):
        """Single break-glass override logs at WARNING level."""
        monkeypatch.setenv("ARIA_ALLOW_UNPINNED", "1")
        monkeypatch.delenv("ARIA_ALLOW_UNSAFE_PATHS", raising=False)
        monkeypatch.delenv("ARIA_MCP_BYPASS_POLICY", raising=False)

        with caplog.at_level(logging.WARNING, logger="aria_esi.core.config"):
            audit_break_glass_state()

        warning_logs = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any("ARIA_ALLOW_UNPINNED" in r.message for r in warning_logs)

    def test_multiple_overrides_returns_all(self, monkeypatch):
        """Multiple break-glass overrides returns all features."""
        monkeypatch.setenv("ARIA_ALLOW_UNSAFE_PATHS", "1")
        monkeypatch.setenv("ARIA_MCP_BYPASS_POLICY", "1")
        monkeypatch.delenv("ARIA_ALLOW_UNPINNED", raising=False)

        active = audit_break_glass_state()

        assert active == {"paths", "policy"}

    def test_multiple_overrides_logs_error(self, monkeypatch, caplog):
        """Multiple break-glass overrides logs at ERROR level."""
        monkeypatch.setenv("ARIA_ALLOW_UNSAFE_PATHS", "1")
        monkeypatch.setenv("ARIA_ALLOW_UNPINNED", "1")
        monkeypatch.delenv("ARIA_MCP_BYPASS_POLICY", raising=False)

        with caplog.at_level(logging.ERROR, logger="aria_esi.core.config"):
            audit_break_glass_state()

        error_logs = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert any("Multiple break-glass" in r.message for r in error_logs)

    def test_all_three_overrides(self, monkeypatch):
        """All three break-glass overrides active."""
        monkeypatch.setenv("ARIA_ALLOW_UNSAFE_PATHS", "1")
        monkeypatch.setenv("ARIA_ALLOW_UNPINNED", "1")
        monkeypatch.setenv("ARIA_MCP_BYPASS_POLICY", "1")

        active = audit_break_glass_state()

        assert active == {"paths", "integrity", "policy"}

    def test_instance_method(self, monkeypatch):
        """AriaSettings.audit_break_glass_state() works as instance method."""
        monkeypatch.setenv("ARIA_ALLOW_UNSAFE_PATHS", "1")
        monkeypatch.delenv("ARIA_ALLOW_UNPINNED", raising=False)
        monkeypatch.delenv("ARIA_MCP_BYPASS_POLICY", raising=False)

        settings = AriaSettings()
        active = settings.audit_break_glass_state()

        assert "paths" in active
