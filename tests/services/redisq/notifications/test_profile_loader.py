"""
Tests for notification profile loader.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import yaml

from aria_esi.services.redisq.notifications.profile_loader import (
    ProfileLoader,
    get_profiles_summary,
)
from aria_esi.services.redisq.notifications.profiles import NotificationProfile


@pytest.fixture
def temp_profiles_dir(monkeypatch):
    """Create temporary profiles directory."""
    with TemporaryDirectory() as tmpdir:
        profiles_path = Path(tmpdir) / "profiles"
        profiles_path.mkdir()
        monkeypatch.setattr(
            "aria_esi.services.redisq.notifications.profile_loader.PROFILES_DIR",
            profiles_path,
        )
        yield profiles_path


@pytest.fixture
def temp_templates_dir(monkeypatch):
    """Create temporary templates directory."""
    with TemporaryDirectory() as tmpdir:
        templates_path = Path(tmpdir) / "templates"
        templates_path.mkdir()
        monkeypatch.setattr(
            "aria_esi.services.redisq.notifications.profile_loader.TEMPLATES_DIR",
            templates_path,
        )
        yield templates_path


def write_profile_yaml(path: Path, name: str, data: dict) -> Path:
    """Helper to write a profile YAML file."""
    profile_path = path / f"{name}.yaml"
    with open(profile_path, "w") as f:
        yaml.dump(data, f)
    return profile_path


class TestProfileLoaderBasics:
    """Basic tests for ProfileLoader."""

    def test_list_profiles_empty(self, temp_profiles_dir):
        """Empty directory returns empty list."""
        profiles = ProfileLoader.list_profiles()
        assert profiles == []

    def test_list_profiles_with_files(self, temp_profiles_dir):
        """Lists profile names from YAML files."""
        write_profile_yaml(temp_profiles_dir, "profile-a", {"name": "profile-a"})
        write_profile_yaml(temp_profiles_dir, "profile-b", {"name": "profile-b"})

        profiles = ProfileLoader.list_profiles()
        assert sorted(profiles) == ["profile-a", "profile-b"]

    def test_list_profiles_yaml_and_yml(self, temp_profiles_dir):
        """Lists both .yaml and .yml files."""
        write_profile_yaml(temp_profiles_dir, "profile-a", {"name": "profile-a"})
        (temp_profiles_dir / "profile-b.yml").write_text("name: profile-b")

        profiles = ProfileLoader.list_profiles()
        assert sorted(profiles) == ["profile-a", "profile-b"]

    def test_profile_exists(self, temp_profiles_dir):
        """Check if profile exists."""
        write_profile_yaml(temp_profiles_dir, "exists", {"name": "exists"})

        assert ProfileLoader.profile_exists("exists") is True
        assert ProfileLoader.profile_exists("does-not-exist") is False


class TestProfileLoaderLoad:
    """Tests for loading profiles."""

    def test_load_profile_basic(self, temp_profiles_dir):
        """Load a basic profile."""
        write_profile_yaml(
            temp_profiles_dir,
            "test-profile",
            {
                "name": "test-profile",
                "display_name": "Test Profile",
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/123/abc",
            },
        )

        profile = ProfileLoader.load_profile("test-profile")

        assert profile.name == "test-profile"
        assert profile.display_name == "Test Profile"
        assert profile.enabled is True

    def test_load_profile_with_topology(self, temp_profiles_dir):
        """Load profile with topology configuration."""
        write_profile_yaml(
            temp_profiles_dir,
            "topo-profile",
            {
                "name": "topo-profile",
                "webhook_url": "https://discord.com/api/webhooks/123/abc",
                "topology": {
                    "geographic": {
                        "systems": [
                            {"name": "Jita", "classification": "hunting"},
                            {"name": "Perimeter", "classification": "transit"},
                        ]
                    }
                },
            },
        )

        profile = ProfileLoader.load_profile("topo-profile")

        assert profile.has_topology is True
        assert profile.system_count == 2

    def test_load_profile_not_found(self, temp_profiles_dir):
        """Loading non-existent profile raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            ProfileLoader.load_profile("not-found")

    def test_load_profile_invalid_yaml(self, temp_profiles_dir):
        """Loading invalid YAML raises ValueError."""
        (temp_profiles_dir / "invalid.yaml").write_text("{{invalid yaml")

        with pytest.raises(ValueError) as exc_info:
            ProfileLoader.load_profile("invalid")
        assert "Invalid YAML" in str(exc_info.value)

    def test_load_enabled_profiles(self, temp_profiles_dir):
        """Load only enabled profiles."""
        write_profile_yaml(
            temp_profiles_dir,
            "enabled",
            {
                "name": "enabled",
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/123/abc",
            },
        )
        write_profile_yaml(
            temp_profiles_dir,
            "disabled",
            {
                "name": "disabled",
                "enabled": False,
                "webhook_url": "https://discord.com/api/webhooks/123/abc",
            },
        )

        profiles = ProfileLoader.load_enabled_profiles()

        assert len(profiles) == 1
        assert profiles[0].name == "enabled"

    def test_load_all_profiles(self, temp_profiles_dir):
        """Load all profiles regardless of enabled status."""
        write_profile_yaml(
            temp_profiles_dir,
            "enabled",
            {"name": "enabled", "enabled": True},
        )
        write_profile_yaml(
            temp_profiles_dir,
            "disabled",
            {"name": "disabled", "enabled": False},
        )

        profiles = ProfileLoader.load_all_profiles()

        assert len(profiles) == 2
        names = [p.name for p in profiles]
        assert "enabled" in names
        assert "disabled" in names


class TestProfileLoaderSave:
    """Tests for saving profiles."""

    def test_save_profile(self, temp_profiles_dir):
        """Save a profile to disk."""
        profile = NotificationProfile(
            name="saved-profile",
            display_name="Saved Profile",
            enabled=True,
            webhook_url="https://discord.com/api/webhooks/123/abc",
            throttle_minutes=3,
        )

        path = ProfileLoader.save_profile(profile)

        assert path.exists()
        assert path.name == "saved-profile.yaml"

        # Verify content
        loaded = ProfileLoader.load_profile("saved-profile")
        assert loaded.name == "saved-profile"
        assert loaded.throttle_minutes == 3

    def test_save_profile_creates_directory(self, monkeypatch):
        """Save creates directory if it doesn't exist."""
        with TemporaryDirectory() as tmpdir:
            new_dir = Path(tmpdir) / "new" / "profiles"
            monkeypatch.setattr(
                "aria_esi.services.redisq.notifications.profile_loader.PROFILES_DIR",
                new_dir,
            )

            profile = NotificationProfile(
                name="test",
                webhook_url="https://discord.com/api/webhooks/123/abc",
            )
            path = ProfileLoader.save_profile(profile)

            assert new_dir.exists()
            assert path.exists()


class TestProfileLoaderDelete:
    """Tests for deleting profiles."""

    def test_delete_profile(self, temp_profiles_dir):
        """Delete an existing profile."""
        write_profile_yaml(temp_profiles_dir, "to-delete", {"name": "to-delete"})

        assert ProfileLoader.profile_exists("to-delete") is True

        deleted = ProfileLoader.delete_profile("to-delete")

        assert deleted is True
        assert ProfileLoader.profile_exists("to-delete") is False

    def test_delete_profile_not_found(self, temp_profiles_dir):
        """Deleting non-existent profile returns False."""
        deleted = ProfileLoader.delete_profile("not-found")
        assert deleted is False


class TestProfileLoaderTemplates:
    """Tests for template handling."""

    def test_list_templates(self, temp_templates_dir):
        """List available templates."""
        (temp_templates_dir / "market-hubs.yaml").write_text("name: market-hubs")
        (temp_templates_dir / "gank-pipes.yaml").write_text("name: gank-pipes")

        templates = ProfileLoader.list_templates()

        assert sorted(templates) == ["gank-pipes", "market-hubs"]

    def test_list_templates_empty(self, temp_templates_dir):
        """Empty templates directory returns empty list."""
        templates = ProfileLoader.list_templates()
        assert templates == []

    def test_load_template(self, temp_templates_dir):
        """Load a template file."""
        template_data = {
            "name": "test-template",
            "display_name": "Test Template",
            "description": "A test template",
            "topology": {
                "geographic": {
                    "systems": [{"name": "Jita"}]
                }
            },
        }
        with open(temp_templates_dir / "test.yaml", "w") as f:
            yaml.dump(template_data, f)

        loaded = ProfileLoader.load_template("test")

        assert loaded["name"] == "test-template"
        assert loaded["description"] == "A test template"

    def test_load_template_not_found(self, temp_templates_dir):
        """Loading non-existent template raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            ProfileLoader.load_template("not-found")

    def test_create_from_template(self, temp_profiles_dir, temp_templates_dir):
        """Create profile from template."""
        template_data = {
            "name": "template-name",
            "display_name": "Template Display",
            "description": "Template description",
            "topology": {
                "geographic": {
                    "systems": [{"name": "Jita"}]
                }
            },
            "throttle_minutes": 2,
        }
        with open(temp_templates_dir / "market.yaml", "w") as f:
            yaml.dump(template_data, f)

        profile = ProfileLoader.create_from_template(
            template_name="market",
            profile_name="my-profile",
            webhook_url="https://discord.com/api/webhooks/123/abc",
        )

        assert profile.name == "my-profile"
        assert profile.webhook_url == "https://discord.com/api/webhooks/123/abc"
        assert profile.has_topology is True
        assert profile.throttle_minutes == 2

    def test_create_from_template_already_exists(self, temp_profiles_dir, temp_templates_dir):
        """Creating profile that already exists raises ValueError."""
        (temp_templates_dir / "template.yaml").write_text("name: template")
        write_profile_yaml(temp_profiles_dir, "existing", {"name": "existing"})

        with pytest.raises(ValueError) as exc_info:
            ProfileLoader.create_from_template(
                template_name="template",
                profile_name="existing",
                webhook_url="https://discord.com/api/webhooks/123/abc",
            )
        assert "already exists" in str(exc_info.value)


class TestProfileLoaderValidation:
    """Tests for profile validation."""

    def test_validate_profile_valid(self, temp_profiles_dir):
        """Valid profile has no errors."""
        profile = NotificationProfile(
            name="valid",
            webhook_url="https://discord.com/api/webhooks/123/abc",
        )
        errors = ProfileLoader.validate_profile(profile)
        assert errors == []

    def test_validate_profile_invalid(self, temp_profiles_dir):
        """Invalid profile returns errors."""
        profile = NotificationProfile(
            name="",
            webhook_url="not-a-webhook",
        )
        errors = ProfileLoader.validate_profile(profile)
        assert len(errors) > 0

    def test_validate_profile_topology_errors(self, temp_profiles_dir):
        """Invalid topology returns errors."""
        profile = NotificationProfile(
            name="topo-error",
            webhook_url="https://discord.com/api/webhooks/123/abc",
            topology={
                "geographic": {
                    "systems": [
                        {"classification": "hunting"},  # Missing name
                    ]
                }
            },
        )
        errors = ProfileLoader.validate_profile(profile)
        assert any("missing 'name'" in e for e in errors)

    def test_validate_all_profiles(self, temp_profiles_dir):
        """Validate all profiles in directory."""
        write_profile_yaml(
            temp_profiles_dir,
            "valid",
            {
                "name": "valid",
                "webhook_url": "https://discord.com/api/webhooks/123/abc",
            },
        )
        write_profile_yaml(
            temp_profiles_dir,
            "invalid",
            {
                "name": "",
                "webhook_url": "not-a-webhook",
            },
        )

        results = ProfileLoader.validate_all_profiles()

        assert "valid" in results
        assert "invalid" in results
        assert results["valid"] == []
        assert len(results["invalid"]) > 0


class TestGetProfilesSummary:
    """Tests for get_profiles_summary helper."""

    def test_summary_empty(self, temp_profiles_dir):
        """Summary with no profiles."""
        summary = get_profiles_summary()

        assert summary["total"] == 0
        assert summary["enabled"] == 0
        assert summary["disabled"] == 0
        assert summary["profiles"] == []

    def test_summary_with_profiles(self, temp_profiles_dir):
        """Summary with mixed profiles."""
        write_profile_yaml(
            temp_profiles_dir,
            "enabled-1",
            {
                "name": "enabled-1",
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/123/abc",
            },
        )
        write_profile_yaml(
            temp_profiles_dir,
            "enabled-2",
            {
                "name": "enabled-2",
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/123/def",
            },
        )
        write_profile_yaml(
            temp_profiles_dir,
            "disabled-1",
            {
                "name": "disabled-1",
                "enabled": False,
            },
        )

        summary = get_profiles_summary()

        assert summary["total"] == 3
        assert summary["enabled"] == 2
        assert summary["disabled"] == 1
        assert len(summary["profiles"]) == 3
