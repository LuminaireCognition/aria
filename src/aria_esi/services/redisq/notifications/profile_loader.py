"""
Notification Profile Loader.

Handles loading, saving, and managing notification profiles from YAML files
in userdata/notifications/.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ....core.logging import get_logger
from .profiles import SCHEMA_VERSION, NotificationProfile

logger = get_logger(__name__)

# Directory paths
PROFILES_DIR = Path("userdata/notifications")
TEMPLATES_DIR = Path("reference/notification-templates")


class ProfileLoader:
    """
    Load and manage notification profiles.

    Profiles are YAML files in userdata/notifications/. Each profile
    is a self-contained notification configuration with its own webhook,
    topology, triggers, and throttle settings.
    """

    @classmethod
    def ensure_directory(cls) -> None:
        """Ensure the profiles directory exists."""
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def list_profiles(cls) -> list[str]:
        """
        List all profile names (enabled and disabled).

        Returns:
            List of profile names (filename stems)
        """
        cls.ensure_directory()

        profiles = []
        for path in PROFILES_DIR.glob("*.yaml"):
            profiles.append(path.stem)
        for path in PROFILES_DIR.glob("*.yml"):
            profiles.append(path.stem)

        return sorted(set(profiles))

    @classmethod
    def profile_exists(cls, name: str) -> bool:
        """
        Check if a profile exists.

        Args:
            name: Profile name

        Returns:
            True if profile file exists
        """
        return cls._get_profile_path(name) is not None

    @classmethod
    def _get_profile_path(cls, name: str) -> Path | None:
        """
        Get the path to a profile file.

        Args:
            name: Profile name

        Returns:
            Path to profile file, or None if not found
        """
        # Try .yaml first, then .yml
        yaml_path = PROFILES_DIR / f"{name}.yaml"
        if yaml_path.exists():
            return yaml_path

        yml_path = PROFILES_DIR / f"{name}.yml"
        if yml_path.exists():
            return yml_path

        return None

    @classmethod
    def load_profile(cls, name: str) -> NotificationProfile:
        """
        Load a single profile by name.

        Args:
            name: Profile name (filename stem)

        Returns:
            NotificationProfile instance

        Raises:
            FileNotFoundError: If profile doesn't exist
            ValueError: If profile is invalid
        """
        path = cls._get_profile_path(name)
        if path is None:
            raise FileNotFoundError(f"Profile not found: {name}")

        try:
            with open(path) as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in profile {name}: {e}") from e

        if not isinstance(data, dict):
            raise ValueError(f"Profile {name} must be a YAML mapping")

        return NotificationProfile.from_dict(data, name=name)

    @classmethod
    def load_enabled_profiles(cls) -> list[NotificationProfile]:
        """
        Load all enabled profiles.

        Returns:
            List of NotificationProfile instances that have enabled=True
        """
        cls.ensure_directory()

        profiles = []
        for name in cls.list_profiles():
            try:
                profile = cls.load_profile(name)
                if profile.enabled:
                    profiles.append(profile)
                else:
                    logger.debug("Profile '%s' is disabled, skipping", name)
            except (FileNotFoundError, ValueError) as e:
                logger.warning("Failed to load profile '%s': %s", name, e)

        return profiles

    @classmethod
    def load_all_profiles(cls) -> list[NotificationProfile]:
        """
        Load all profiles (enabled and disabled).

        Returns:
            List of all NotificationProfile instances
        """
        cls.ensure_directory()

        profiles = []
        for name in cls.list_profiles():
            try:
                profile = cls.load_profile(name)
                profiles.append(profile)
            except (FileNotFoundError, ValueError) as e:
                logger.warning("Failed to load profile '%s': %s", name, e)

        return profiles

    @classmethod
    def save_profile(cls, profile: NotificationProfile) -> Path:
        """
        Save a profile to disk.

        Args:
            profile: NotificationProfile to save

        Returns:
            Path to saved file
        """
        cls.ensure_directory()

        path = PROFILES_DIR / f"{profile.name}.yaml"
        data = profile.to_dict()

        with open(path, "w") as f:
            yaml.dump(
                data,
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )

        logger.info("Saved profile '%s' to %s", profile.name, path)
        return path

    @classmethod
    def delete_profile(cls, name: str) -> bool:
        """
        Delete a profile.

        Args:
            name: Profile name

        Returns:
            True if deleted, False if not found
        """
        path = cls._get_profile_path(name)
        if path is None:
            return False

        path.unlink()
        logger.info("Deleted profile '%s'", name)
        return True

    @classmethod
    def list_templates(cls) -> list[str]:
        """
        List available profile templates.

        Returns:
            List of template names
        """
        if not TEMPLATES_DIR.exists():
            return []

        templates = []
        for path in TEMPLATES_DIR.glob("*.yaml"):
            if path.stem != "README":
                templates.append(path.stem)
        for path in TEMPLATES_DIR.glob("*.yml"):
            if path.stem != "README":
                templates.append(path.stem)

        return sorted(set(templates))

    @classmethod
    def load_template(cls, template_name: str) -> dict[str, Any]:
        """
        Load a template file.

        Args:
            template_name: Template name (filename stem)

        Returns:
            Template data as dict

        Raises:
            FileNotFoundError: If template doesn't exist
        """
        # Try .yaml first, then .yml
        yaml_path = TEMPLATES_DIR / f"{template_name}.yaml"
        if yaml_path.exists():
            path = yaml_path
        else:
            yml_path = TEMPLATES_DIR / f"{template_name}.yml"
            if yml_path.exists():
                path = yml_path
            else:
                raise FileNotFoundError(f"Template not found: {template_name}")

        with open(path) as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            raise ValueError(f"Template {template_name} must be a YAML mapping")

        return data

    @classmethod
    def create_from_template(
        cls,
        template_name: str,
        profile_name: str,
        webhook_url: str,
        enabled: bool = True,
        persona: str | None = None,
    ) -> NotificationProfile:
        """
        Create a new profile from a template.

        Args:
            template_name: Name of template to use
            profile_name: Name for the new profile
            webhook_url: Discord webhook URL
            enabled: Whether to enable the profile (default True)
            persona: Optional persona override for commentary (e.g., "paria-s")

        Returns:
            NotificationProfile instance (not yet saved)

        Raises:
            FileNotFoundError: If template doesn't exist
            ValueError: If profile already exists
        """
        if cls.profile_exists(profile_name):
            raise ValueError(f"Profile already exists: {profile_name}")

        template_data = cls.load_template(template_name)

        # Override template defaults with user values
        template_data["name"] = profile_name
        template_data["webhook_url"] = webhook_url
        template_data["enabled"] = enabled

        # Set persona in commentary config if specified
        if persona:
            if "commentary" not in template_data:
                template_data["commentary"] = {}
            template_data["commentary"]["persona"] = persona
            # Enable commentary if persona specified but not explicitly enabled
            if "enabled" not in template_data["commentary"]:
                template_data["commentary"]["enabled"] = True

        return NotificationProfile.from_dict(template_data, name=profile_name)

    @classmethod
    def validate_profile(cls, profile: NotificationProfile) -> list[str]:
        """
        Validate a profile configuration.

        Args:
            profile: NotificationProfile to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = profile.validate()

        # Additional loader-level validation
        if profile.schema_version > SCHEMA_VERSION:
            errors.append(
                f"Profile uses schema version {profile.schema_version}, "
                f"but only version {SCHEMA_VERSION} is supported"
            )

        # Validate topology references if present
        if profile.has_topology:
            topo_errors = cls._validate_topology(profile.topology)
            errors.extend(topo_errors)

        return errors

    @classmethod
    def _validate_topology(cls, topology: dict[str, Any]) -> list[str]:
        """
        Validate topology configuration.

        Args:
            topology: Topology configuration dict

        Returns:
            List of validation errors
        """
        errors = []

        geographic = topology.get("geographic", {})
        systems = geographic.get("systems", [])

        for i, system in enumerate(systems):
            if isinstance(system, dict):
                if "name" not in system:
                    errors.append(f"topology.geographic.systems[{i}]: missing 'name'")
                classification = system.get("classification", "")
                valid_classifications = {"home", "hunting", "transit", "avoidance", ""}
                if classification and classification not in valid_classifications:
                    errors.append(
                        f"topology.geographic.systems[{i}]: "
                        f"invalid classification '{classification}'"
                    )
            elif isinstance(system, str):
                # Simple string format is allowed
                pass
            else:
                errors.append(f"topology.geographic.systems[{i}]: must be string or dict")

        return errors

    @classmethod
    def validate_all_profiles(cls) -> dict[str, list[str]]:
        """
        Validate all profiles.

        Returns:
            Dict mapping profile name to list of errors
        """
        results = {}
        for name in cls.list_profiles():
            try:
                profile = cls.load_profile(name)
                errors = cls.validate_profile(profile)
                results[name] = errors
            except (FileNotFoundError, ValueError) as e:
                results[name] = [str(e)]

        return results


def get_profiles_summary() -> dict[str, Any]:
    """
    Get a summary of all notification profiles.

    Returns:
        Summary dict with counts and status
    """
    profiles = ProfileLoader.load_all_profiles()

    enabled = [p for p in profiles if p.enabled]
    disabled = [p for p in profiles if not p.enabled]

    return {
        "total": len(profiles),
        "enabled": len(enabled),
        "disabled": len(disabled),
        "profiles": [
            {
                "name": p.name,
                "display_name": p.display_name,
                "enabled": p.enabled,
                "system_count": p.system_count,
                "webhook_configured": bool(p.webhook_url),
            }
            for p in profiles
        ],
    }
