"""
Tests for CLI Notifications Commands.

Tests notification profile management commands.
"""

from __future__ import annotations

import argparse
from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# List Command Tests
# =============================================================================


class TestCmdNotificationsList:
    """Test cmd_notifications_list function."""

    def test_list_returns_summary(self):
        """List command returns profile summary."""
        from aria_esi.commands.notifications import cmd_notifications_list

        args = argparse.Namespace()

        mock_summary = {
            "profiles": [
                {"name": "profile1", "enabled": True},
                {"name": "profile2", "enabled": False},
            ],
            "count": 2,
            "enabled_count": 1,
        }

        with patch("aria_esi.commands.notifications.get_profiles_summary", return_value=mock_summary):
            result = cmd_notifications_list(args)

        assert result["status"] == "ok"
        assert result["count"] == 2
        assert result["enabled_count"] == 1

    def test_list_empty_profiles(self):
        """List command handles empty profile list."""
        from aria_esi.commands.notifications import cmd_notifications_list

        args = argparse.Namespace()

        mock_summary = {
            "profiles": [],
            "count": 0,
            "enabled_count": 0,
        }

        with patch("aria_esi.commands.notifications.get_profiles_summary", return_value=mock_summary):
            result = cmd_notifications_list(args)

        assert result["status"] == "ok"
        assert result["count"] == 0


# =============================================================================
# Show Command Tests
# =============================================================================


class TestCmdNotificationsShow:
    """Test cmd_notifications_show function."""

    def test_show_profile_not_found(self):
        """Show command returns error for missing profile."""
        from aria_esi.commands.notifications import cmd_notifications_show

        args = argparse.Namespace(name="nonexistent")

        with patch("aria_esi.commands.notifications.ProfileLoader.load_profile", side_effect=FileNotFoundError()):
            result = cmd_notifications_show(args)

        assert result["status"] == "error"
        assert result["error"] == "not_found"

    def test_show_invalid_profile(self):
        """Show command returns error for invalid profile."""
        from aria_esi.commands.notifications import cmd_notifications_show

        args = argparse.Namespace(name="invalid")

        with patch("aria_esi.commands.notifications.ProfileLoader.load_profile", side_effect=ValueError("Invalid YAML")):
            result = cmd_notifications_show(args)

        assert result["status"] == "error"
        assert result["error"] == "invalid"

    def test_show_profile_success(self):
        """Show command returns profile details."""
        from aria_esi.commands.notifications import cmd_notifications_show

        args = argparse.Namespace(name="test-profile")

        mock_profile = MagicMock()
        mock_profile.name = "test-profile"
        mock_profile.display_name = "Test Profile"
        mock_profile.enabled = True
        mock_profile.mask_webhook_url.return_value = "https://discord.com/api/webhooks/***"
        mock_profile.description = "A test profile"
        mock_profile.schema_version = "1.0"
        mock_profile.has_topology = False
        mock_profile.system_count = 0
        mock_profile.triggers = MagicMock()
        mock_profile.triggers.watchlist_activity = True
        mock_profile.triggers.gatecamp_detected = True
        mock_profile.triggers.high_value_threshold = 100000000
        mock_profile.throttle_minutes = 5
        mock_profile.quiet_hours = MagicMock()
        mock_profile.quiet_hours.enabled = False
        mock_profile.quiet_hours.start = "22:00"
        mock_profile.quiet_hours.end = "08:00"
        mock_profile.quiet_hours.timezone = "UTC"
        mock_profile.commentary = None

        with patch("aria_esi.commands.notifications.ProfileLoader.load_profile", return_value=mock_profile):
            result = cmd_notifications_show(args)

        assert result["status"] == "ok"
        assert result["profile"]["name"] == "test-profile"
        assert result["profile"]["enabled"] is True
        assert result["triggers"]["watchlist_activity"] is True


# =============================================================================
# Create Command Tests
# =============================================================================


class TestCmdNotificationsCreate:
    """Test cmd_notifications_create function."""

    def test_create_invalid_webhook(self):
        """Create command returns error for invalid webhook URL."""
        from aria_esi.commands.notifications import cmd_notifications_create

        args = argparse.Namespace(
            name="new-profile",
            template="basic",
            webhook="https://invalid.com/not-a-webhook",
            persona=None,
        )

        result = cmd_notifications_create(args)

        assert result["status"] == "error"
        assert result["error"] == "invalid_webhook"

    def test_create_profile_already_exists(self):
        """Create command returns error if profile already exists."""
        from aria_esi.commands.notifications import cmd_notifications_create

        args = argparse.Namespace(
            name="existing-profile",
            template="basic",
            webhook="https://discord.com/api/webhooks/123/abc",
            persona=None,
        )

        with patch("aria_esi.commands.notifications.ProfileLoader.profile_exists", return_value=True):
            result = cmd_notifications_create(args)

        assert result["status"] == "error"
        assert result["error"] == "already_exists"

    def test_create_missing_template(self):
        """Create command returns error for missing template."""
        from aria_esi.commands.notifications import cmd_notifications_create

        args = argparse.Namespace(
            name="new-profile",
            template="nonexistent-template",
            webhook="https://discord.com/api/webhooks/123/abc",
            persona=None,
        )

        with patch("aria_esi.commands.notifications.ProfileLoader.profile_exists", return_value=False), \
             patch("aria_esi.commands.notifications.ProfileLoader.list_templates", return_value=["basic", "market-hubs"]):
            result = cmd_notifications_create(args)

        assert result["status"] == "error"
        assert result["error"] == "template_not_found"


# =============================================================================
# Test Command Tests
# =============================================================================


class TestCmdNotificationsTest:
    """Test cmd_notifications_test function."""

    def test_test_profile_not_found(self):
        """Test command returns error for missing profile."""
        from aria_esi.commands.notifications import cmd_notifications_test

        args = argparse.Namespace(name="nonexistent")

        with patch("aria_esi.commands.notifications.ProfileLoader.load_profile", side_effect=FileNotFoundError()):
            result = cmd_notifications_test(args)

        assert result["status"] == "error"
        assert result["error"] == "not_found"

    def test_test_profile_found(self):
        """Test command loads profile successfully when it exists."""
        from aria_esi.commands.notifications import cmd_notifications_test

        args = argparse.Namespace(name="test-profile")

        mock_profile = MagicMock()
        mock_profile.name = "test-profile"
        mock_profile.enabled = True
        mock_profile.webhook_url = "https://discord.com/api/webhooks/123/abc"
        mock_profile.mask_webhook_url.return_value = "***masked***"
        mock_profile.display_name = "Test Profile"

        # The test will fail HTTP call but profile should be found
        with patch("aria_esi.commands.notifications.ProfileLoader.load_profile", return_value=mock_profile):
            result = cmd_notifications_test(args)

        # Status can be ok or error depending on HTTP success, but profile was found
        assert result["status"] in ("ok", "error")
        assert "not_found" not in result.get("error", "")


# =============================================================================
# Validate Command Tests
# =============================================================================


class TestCmdNotificationsValidate:
    """Test cmd_notifications_validate function."""

    def test_validate_no_profiles(self):
        """Validate command handles no profiles."""
        from aria_esi.commands.notifications import cmd_notifications_validate

        args = argparse.Namespace()

        with patch("aria_esi.commands.notifications.ProfileLoader.list_profiles", return_value=[]):
            result = cmd_notifications_validate(args)

        assert result["status"] == "ok"
        assert result.get("profiles_checked", 0) == 0

    def test_validate_all_valid(self):
        """Validate command succeeds with valid profiles."""
        from aria_esi.commands.notifications import cmd_notifications_validate

        args = argparse.Namespace()

        mock_profile = MagicMock()
        mock_profile.name = "valid-profile"
        mock_profile.schema_version = 1  # Valid schema version
        mock_profile.webhook_url = "https://discord.com/api/webhooks/123/abc"
        mock_profile.triggers = MagicMock()
        mock_profile.triggers.watchlist_activity = False
        mock_profile.triggers.gatecamp_detected = False
        mock_profile.has_topology = False
        mock_profile.topology = {}

        with patch("aria_esi.commands.notifications.ProfileLoader.list_profiles", return_value=["valid-profile"]), \
             patch("aria_esi.commands.notifications.ProfileLoader.load_profile", return_value=mock_profile), \
             patch("aria_esi.commands.notifications.ProfileLoader.validate_profile", return_value=[]):
            result = cmd_notifications_validate(args)

        assert result["status"] == "ok" or result["all_valid"] is True

    def test_validate_with_errors(self):
        """Validate command reports profile errors."""
        from aria_esi.commands.notifications import cmd_notifications_validate

        args = argparse.Namespace()

        with patch("aria_esi.commands.notifications.ProfileLoader.list_profiles", return_value=["broken-profile"]), \
             patch("aria_esi.commands.notifications.ProfileLoader.load_profile", side_effect=ValueError("Invalid schema")):
            result = cmd_notifications_validate(args)

        # Should report validation errors in results
        assert result["all_valid"] is False or result["status"] == "issues_found"


# =============================================================================
# Templates Command Tests
# =============================================================================


class TestCmdNotificationsTemplates:
    """Test cmd_notifications_templates function."""

    def test_templates_list(self):
        """Templates command lists available templates."""
        from aria_esi.commands.notifications import cmd_notifications_templates

        args = argparse.Namespace()

        mock_templates = [
            {"name": "basic", "description": "Basic notification template"},
            {"name": "market-hubs", "description": "Market hub monitoring"},
        ]

        with patch("aria_esi.commands.notifications.ProfileLoader.list_templates", return_value=mock_templates):
            result = cmd_notifications_templates(args)

        assert result["status"] == "ok"
        assert len(result["templates"]) == 2
