"""
ARIA Notification Profile Commands

Manage notification profiles for Discord webhook notifications.
Profiles allow multiple Discord channels with independent topology filters,
triggers, and throttling.
"""

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from ..core import get_utc_timestamp
from ..services.redisq.notifications import (
    NotificationProfile,
    ProfileLoader,
    get_profiles_summary,
)

# =============================================================================
# List Command
# =============================================================================


def cmd_notifications_list(args: argparse.Namespace) -> dict[str, Any]:
    """
    List all notification profiles.

    Args:
        args: Parsed arguments

    Returns:
        Result dict with profile list
    """
    query_ts = get_utc_timestamp()

    summary = get_profiles_summary()

    return {
        "query_timestamp": query_ts,
        "status": "ok",
        **summary,
    }


# =============================================================================
# Show Command
# =============================================================================


def cmd_notifications_show(args: argparse.Namespace) -> dict[str, Any]:
    """
    Show details of a specific profile.

    Args:
        args: Parsed arguments with name

    Returns:
        Result dict with profile details
    """
    query_ts = get_utc_timestamp()
    name = args.name

    try:
        profile = ProfileLoader.load_profile(name)
    except FileNotFoundError:
        return {
            "query_timestamp": query_ts,
            "status": "error",
            "error": "not_found",
            "message": f"Profile not found: {name}",
        }
    except ValueError as e:
        return {
            "query_timestamp": query_ts,
            "status": "error",
            "error": "invalid",
            "message": str(e),
        }

    # Build detailed profile view
    result = {
        "query_timestamp": query_ts,
        "status": "ok",
        "profile": {
            "name": profile.name,
            "display_name": profile.display_name,
            "enabled": profile.enabled,
            "webhook_url": profile.mask_webhook_url(),
            "description": profile.description or None,
            "schema_version": profile.schema_version,
        },
        "topology": {
            "has_topology": profile.has_topology,
            "system_count": profile.system_count,
        },
        "triggers": {
            "watchlist_activity": profile.triggers.watchlist_activity,
            "gatecamp_detected": profile.triggers.gatecamp_detected,
            "high_value_threshold": profile.triggers.high_value_threshold,
        },
        "throttle_minutes": profile.throttle_minutes,
        "quiet_hours": {
            "enabled": profile.quiet_hours.enabled,
            "start": profile.quiet_hours.start,
            "end": profile.quiet_hours.end,
            "timezone": profile.quiet_hours.timezone,
        },
    }

    # Include topology details if present
    if profile.has_topology:
        geographic = profile.topology.get("geographic", {})
        systems = geographic.get("systems", [])
        result["topology"]["systems"] = [
            s.get("name") if isinstance(s, dict) else s for s in systems[:10]
        ]
        if len(systems) > 10:
            result["topology"]["systems_truncated"] = len(systems) - 10

    # Include commentary if configured
    if profile.commentary and profile.commentary.enabled:
        result["commentary"] = {
            "enabled": True,
            "model": profile.commentary.model,
        }

    return result


# =============================================================================
# Create Command
# =============================================================================


def cmd_notifications_create(args: argparse.Namespace) -> dict[str, Any]:
    """
    Create a new profile from a template.

    Args:
        args: Parsed arguments with name, template, webhook, persona

    Returns:
        Result dict with created profile
    """
    query_ts = get_utc_timestamp()
    name = args.name
    template = args.template
    webhook_url = args.webhook
    persona = getattr(args, "persona", None)

    # Validate webhook URL
    if not webhook_url.startswith("https://discord.com/api/webhooks/"):
        return {
            "query_timestamp": query_ts,
            "status": "error",
            "error": "invalid_webhook",
            "message": "Webhook URL must be a Discord webhook URL",
        }

    # Validate persona if specified
    if persona:
        from ..services.redisq.notifications.persona import VOICE_SUMMARIES

        if persona not in VOICE_SUMMARIES:
            valid = ", ".join(sorted(VOICE_SUMMARIES.keys()))
            return {
                "query_timestamp": query_ts,
                "status": "error",
                "error": "invalid_persona",
                "message": f"Unknown persona '{persona}'. Valid options: {valid}",
            }

    # Check if profile already exists
    if ProfileLoader.profile_exists(name):
        return {
            "query_timestamp": query_ts,
            "status": "error",
            "error": "already_exists",
            "message": f"Profile already exists: {name}",
        }

    # Check if template exists
    if template not in ProfileLoader.list_templates():
        return {
            "query_timestamp": query_ts,
            "status": "error",
            "error": "template_not_found",
            "message": f"Template not found: {template}",
            "available_templates": ProfileLoader.list_templates(),
        }

    try:
        profile = ProfileLoader.create_from_template(
            template_name=template,
            profile_name=name,
            webhook_url=webhook_url,
            persona=persona,
        )
        path = ProfileLoader.save_profile(profile)
    except Exception as e:
        return {
            "query_timestamp": query_ts,
            "status": "error",
            "error": "creation_failed",
            "message": str(e),
        }

    result: dict[str, Any] = {
        "query_timestamp": query_ts,
        "status": "ok",
        "message": f"Profile '{name}' created from template '{template}'",
        "profile": {
            "name": profile.name,
            "display_name": profile.display_name,
            "enabled": profile.enabled,
            "system_count": profile.system_count,
        },
        "path": str(path),
    }

    # Include persona info if set
    if persona:
        result["profile"]["persona"] = persona
        result["profile"]["commentary_enabled"] = True

    return result


# =============================================================================
# Enable/Disable Commands
# =============================================================================


def cmd_notifications_enable(args: argparse.Namespace) -> dict[str, Any]:
    """
    Enable a profile.

    Args:
        args: Parsed arguments with name

    Returns:
        Result dict
    """
    return _set_profile_enabled(args.name, True)


def cmd_notifications_disable(args: argparse.Namespace) -> dict[str, Any]:
    """
    Disable a profile.

    Args:
        args: Parsed arguments with name

    Returns:
        Result dict
    """
    return _set_profile_enabled(args.name, False)


def _set_profile_enabled(name: str, enabled: bool) -> dict[str, Any]:
    """
    Set profile enabled status.

    Args:
        name: Profile name
        enabled: New enabled status

    Returns:
        Result dict
    """
    query_ts = get_utc_timestamp()

    try:
        profile = ProfileLoader.load_profile(name)
    except FileNotFoundError:
        return {
            "query_timestamp": query_ts,
            "status": "error",
            "error": "not_found",
            "message": f"Profile not found: {name}",
        }

    if profile.enabled == enabled:
        action = "enabled" if enabled else "disabled"
        return {
            "query_timestamp": query_ts,
            "status": "ok",
            "message": f"Profile '{name}' is already {action}",
            "profile": {
                "name": profile.name,
                "enabled": profile.enabled,
            },
        }

    profile.enabled = enabled
    ProfileLoader.save_profile(profile)

    action = "enabled" if enabled else "disabled"
    return {
        "query_timestamp": query_ts,
        "status": "ok",
        "message": f"Profile '{name}' {action}",
        "profile": {
            "name": profile.name,
            "enabled": profile.enabled,
        },
    }


# =============================================================================
# Test Command
# =============================================================================


def cmd_notifications_test(args: argparse.Namespace) -> dict[str, Any]:
    """
    Send a test notification to a profile's webhook.

    Args:
        args: Parsed arguments with name

    Returns:
        Result dict
    """
    query_ts = get_utc_timestamp()
    name = args.name

    try:
        profile = ProfileLoader.load_profile(name)
    except FileNotFoundError:
        return {
            "query_timestamp": query_ts,
            "status": "error",
            "error": "not_found",
            "message": f"Profile not found: {name}",
        }

    if not profile.webhook_url:
        return {
            "query_timestamp": query_ts,
            "status": "error",
            "error": "no_webhook",
            "message": f"Profile '{name}' has no webhook URL configured",
        }

    # Send test message
    from ..services.redisq.notifications import DiscordClient, MessageFormatter

    async def send_test() -> tuple[bool, str]:
        client = DiscordClient(webhook_url=profile.webhook_url)
        formatter = MessageFormatter()
        payload = formatter.format_test_message()
        result = await client.send(payload)
        await client.close()
        return result.success, result.error or "OK"

    success, message = asyncio.run(send_test())

    if success:
        return {
            "query_timestamp": query_ts,
            "status": "ok",
            "message": f"Test message sent to profile '{name}'",
            "webhook": profile.mask_webhook_url(),
        }
    else:
        return {
            "query_timestamp": query_ts,
            "status": "error",
            "error": "send_failed",
            "message": f"Failed to send test message: {message}",
            "webhook": profile.mask_webhook_url(),
        }


# =============================================================================
# Validate Command
# =============================================================================


def cmd_notifications_validate(args: argparse.Namespace) -> dict[str, Any]:
    """
    Validate all profiles.

    Args:
        args: Parsed arguments

    Returns:
        Result dict with validation results
    """
    query_ts = get_utc_timestamp()

    results = ProfileLoader.validate_all_profiles()

    all_valid = all(len(errors) == 0 for errors in results.values())

    return {
        "query_timestamp": query_ts,
        "status": "ok" if all_valid else "issues_found",
        "profiles_validated": len(results),
        "all_valid": all_valid,
        "results": {
            name: {"valid": len(errors) == 0, "errors": errors} for name, errors in results.items()
        },
    }


# =============================================================================
# Templates Command
# =============================================================================


def cmd_notifications_templates(args: argparse.Namespace) -> dict[str, Any]:
    """
    List available profile templates.

    Args:
        args: Parsed arguments

    Returns:
        Result dict with template list
    """
    query_ts = get_utc_timestamp()

    templates = ProfileLoader.list_templates()

    # Load template details
    template_details = []
    for name in templates:
        try:
            data = ProfileLoader.load_template(name)
            template_details.append(
                {
                    "name": name,
                    "display_name": data.get("display_name", name),
                    "description": data.get("description", ""),
                    "system_count": len(
                        data.get("topology", {}).get("geographic", {}).get("systems", [])
                    ),
                }
            )
        except Exception:
            template_details.append(
                {
                    "name": name,
                    "display_name": name,
                    "description": "(failed to load)",
                    "system_count": 0,
                }
            )

    return {
        "query_timestamp": query_ts,
        "status": "ok",
        "template_count": len(templates),
        "templates": template_details,
    }


# =============================================================================
# Migrate Command
# =============================================================================


def cmd_notifications_migrate(args: argparse.Namespace) -> dict[str, Any]:
    """
    Migrate legacy config.json webhook settings to YAML profile.

    Reads redisq.notifications from userdata/config.json and creates
    a new YAML profile named "migrated" (or user-specified name).

    Args:
        args: Parsed arguments with optional name

    Returns:
        Result dict with migration status
    """
    query_ts = get_utc_timestamp()
    profile_name = getattr(args, "name", "migrated") or "migrated"

    config_path = Path("userdata/config.json")

    # Check if config.json exists
    if not config_path.exists():
        return {
            "query_timestamp": query_ts,
            "status": "error",
            "error": "no_config",
            "message": "userdata/config.json not found",
        }

    # Load config
    try:
        with open(config_path) as f:
            config = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return {
            "query_timestamp": query_ts,
            "status": "error",
            "error": "config_read_error",
            "message": f"Failed to read config.json: {e}",
        }

    # Check for legacy notifications section
    redisq = config.get("redisq", {})
    notifications = redisq.get("notifications", {})

    if not notifications:
        return {
            "query_timestamp": query_ts,
            "status": "not_found",
            "message": "No legacy redisq.notifications section found in config.json",
            "hint": "Legacy webhook config uses redisq.notifications.discord_webhook_url",
        }

    webhook_url = notifications.get("discord_webhook_url", "")
    if not webhook_url:
        return {
            "query_timestamp": query_ts,
            "status": "error",
            "error": "no_webhook",
            "message": "Legacy config exists but discord_webhook_url is empty",
        }

    # Validate webhook URL format
    if not webhook_url.startswith("https://discord.com/api/webhooks/"):
        return {
            "query_timestamp": query_ts,
            "status": "error",
            "error": "invalid_webhook",
            "message": "discord_webhook_url must be a Discord webhook URL",
            "hint": "URL should start with https://discord.com/api/webhooks/",
        }

    # Check if profile already exists
    if ProfileLoader.profile_exists(profile_name):
        return {
            "query_timestamp": query_ts,
            "status": "error",
            "error": "already_exists",
            "message": f"Profile '{profile_name}' already exists",
            "hint": "Use --name to specify a different profile name",
        }

    # Extract settings from legacy config
    triggers = notifications.get("triggers", {})
    quiet_hours_data = notifications.get("quiet_hours", {})

    # Build profile data
    profile_data: dict[str, Any] = {
        "name": profile_name,
        "display_name": "Migrated from config.json",
        "description": "Automatically migrated from legacy redisq.notifications config",
        "enabled": True,
        "webhook_url": webhook_url,
        "triggers": {
            "watchlist_activity": triggers.get("watchlist_activity", True),
            "gatecamp_detected": triggers.get("gatecamp_detected", True),
            "high_value_threshold": triggers.get("high_value_threshold", 1000000000),
        },
        "throttle_minutes": notifications.get("throttle_minutes", 5),
    }

    # Migrate quiet hours if present
    if quiet_hours_data.get("enabled"):
        profile_data["quiet_hours"] = {
            "enabled": True,
            "start": quiet_hours_data.get("start", "02:00"),
            "end": quiet_hours_data.get("end", "08:00"),
            "timezone": quiet_hours_data.get("timezone", "UTC"),
        }

    # Migrate topology from context_topology if present
    # Copy all layers, not just geographic, to preserve user's full configuration
    # Use `in` check (not truthiness) to preserve explicit empty values like routes: []
    context_topology = redisq.get("context_topology", {})
    if context_topology:
        topology_data: dict[str, Any] = {}

        # Copy archetype if present (enables preset behavior in migrated profile)
        if "archetype" in context_topology:
            topology_data["archetype"] = context_topology["archetype"]

        # Copy all topology layers that are present (including explicit empties)
        for layer_key in ["geographic", "entity", "routes", "assets", "patterns"]:
            if layer_key in context_topology:
                topology_data[layer_key] = context_topology[layer_key]

        # Copy threshold values if present
        for threshold_key in [
            "fetch_threshold",
            "log_threshold",
            "digest_threshold",
            "priority_threshold",
        ]:
            if threshold_key in context_topology:
                topology_data[threshold_key] = context_topology[threshold_key]

        if topology_data:
            profile_data["topology"] = topology_data

    # Create and save profile
    try:
        profile = NotificationProfile.from_dict(profile_data, name=profile_name)
        path = ProfileLoader.save_profile(profile)
    except Exception as e:
        return {
            "query_timestamp": query_ts,
            "status": "error",
            "error": "save_failed",
            "message": f"Failed to save profile: {e}",
        }

    return {
        "query_timestamp": query_ts,
        "status": "ok",
        "message": f"Migrated legacy config to profile '{profile_name}'",
        "profile": {
            "name": profile.name,
            "display_name": profile.display_name,
            "enabled": profile.enabled,
            "system_count": profile.system_count,
        },
        "path": str(path),
        "next_steps": [
            f"Test the webhook: uv run aria-esi notifications test {profile_name}",
            "Remove the redisq.notifications section from userdata/config.json",
            f"Customize the profile: userdata/notifications/{profile_name}.yaml",
        ],
    }


# =============================================================================
# Delete Command
# =============================================================================


def cmd_notifications_delete(args: argparse.Namespace) -> dict[str, Any]:
    """
    Delete a profile.

    Args:
        args: Parsed arguments with name

    Returns:
        Result dict
    """
    query_ts = get_utc_timestamp()
    name = args.name

    if not ProfileLoader.profile_exists(name):
        return {
            "query_timestamp": query_ts,
            "status": "error",
            "error": "not_found",
            "message": f"Profile not found: {name}",
        }

    if not args.force:
        return {
            "query_timestamp": query_ts,
            "status": "error",
            "error": "confirmation_required",
            "message": f"Add --force to confirm deletion of profile '{name}'",
        }

    deleted = ProfileLoader.delete_profile(name)
    if deleted:
        return {
            "query_timestamp": query_ts,
            "status": "ok",
            "message": f"Profile '{name}' deleted",
        }
    else:
        return {
            "query_timestamp": query_ts,
            "status": "error",
            "error": "delete_failed",
            "message": f"Failed to delete profile '{name}'",
        }


# =============================================================================
# Interest Engine v2 Commands
# =============================================================================


def cmd_notifications_explain(args: argparse.Namespace) -> dict[str, Any]:
    """
    Explain interest scoring for a specific kill.

    Uses the v2 interest engine to show detailed breakdown of how
    each signal and category contributed to the final score.

    Args:
        args: Parsed arguments with profile name and kill_id

    Returns:
        Result dict with explanation
    """
    query_ts = get_utc_timestamp()
    profile_name = args.profile
    _kill_id = args.kill_id  # Reserved for kill store integration
    _verbose = getattr(args, "verbose", False)  # Reserved for verbose output

    # Load profile
    try:
        profile = ProfileLoader.load_profile(profile_name)
    except FileNotFoundError:
        return {
            "query_timestamp": query_ts,
            "status": "error",
            "error": "not_found",
            "message": f"Profile not found: {profile_name}",
        }

    # Check if profile uses v2
    if not profile.uses_interest_v2:
        return {
            "query_timestamp": query_ts,
            "status": "error",
            "error": "not_v2",
            "message": f"Profile '{profile_name}' does not use interest engine v2",
            "hint": "Add 'interest.engine: v2' to the profile or use migrate-v2",
        }

    # For now, simulate with system_id only (full kill fetch TBD)
    # In a real implementation, we'd fetch the kill from the store
    return {
        "query_timestamp": query_ts,
        "status": "error",
        "error": "not_implemented",
        "message": "explain command requires kill store integration",
        "hint": "Use 'notifications simulate' to test scoring on historical kills",
    }


def cmd_notifications_simulate(args: argparse.Namespace) -> dict[str, Any]:
    """
    Simulate v2 scoring on historical kills.

    Replays recent kills through the v2 engine to compare with v1
    and identify potential notification changes.

    Args:
        args: Parsed arguments with profile name

    Returns:
        Result dict with simulation summary
    """
    query_ts = get_utc_timestamp()
    profile_name = args.profile
    hours = getattr(args, "hours", 24)

    # Load profile
    try:
        profile = ProfileLoader.load_profile(profile_name)
    except FileNotFoundError:
        return {
            "query_timestamp": query_ts,
            "status": "error",
            "error": "not_found",
            "message": f"Profile not found: {profile_name}",
        }

    # Check if profile uses v2
    if not profile.uses_interest_v2:
        return {
            "query_timestamp": query_ts,
            "status": "error",
            "error": "not_v2",
            "message": f"Profile '{profile_name}' does not use interest engine v2",
            "hint": "Add 'interest.engine: v2' to the profile or use migrate-v2",
        }

    # Build engine
    from ..services.redisq.interest_v2 import InterestConfigV2

    config = InterestConfigV2.from_dict(profile.interest)
    # Engine creation deferred until kill store integration
    # _engine = InterestEngineV2(config)

    # Note: Full simulation requires kill store integration
    return {
        "query_timestamp": query_ts,
        "status": "error",
        "error": "not_implemented",
        "message": f"simulate command requires kill store integration (would process {hours}h of kills)",
        "profile": profile_name,
        "config_tier": config.tier.value,
        "preset": config.preset,
    }


def cmd_notifications_migrate_v2(args: argparse.Namespace) -> dict[str, Any]:
    """
    Migrate a profile from v1 triggers to v2 interest engine.

    Creates a new interest configuration based on the profile's
    existing topology and trigger configuration.

    Args:
        args: Parsed arguments with profile name and strategy

    Returns:
        Result dict with migration result
    """
    query_ts = get_utc_timestamp()
    profile_name = args.profile
    strategy_name = getattr(args, "strategy", "hybrid")
    dry_run = getattr(args, "dry_run", False)
    preset = getattr(args, "preset", None)

    # Load profile
    try:
        profile = ProfileLoader.load_profile(profile_name)
    except FileNotFoundError:
        return {
            "query_timestamp": query_ts,
            "status": "error",
            "error": "not_found",
            "message": f"Profile not found: {profile_name}",
        }

    # Check if already v2
    if profile.uses_interest_v2:
        return {
            "query_timestamp": query_ts,
            "status": "error",
            "error": "already_v2",
            "message": f"Profile '{profile_name}' already uses interest engine v2",
        }

    # Import migration tools
    from ..services.redisq.interest_v2.cli.migrate import (
        MigrationStrategy,
        format_migration_diff,
        migrate_profile,
        validate_migration,
    )

    # Parse strategy
    try:
        strategy = MigrationStrategy(strategy_name)
    except ValueError:
        valid = [s.value for s in MigrationStrategy]
        return {
            "query_timestamp": query_ts,
            "status": "error",
            "error": "invalid_strategy",
            "message": f"Unknown strategy: {strategy_name}",
            "valid_strategies": valid,
        }

    # Get full profile data
    profile_data = profile.to_dict()

    # Run migration
    result = migrate_profile(profile_data, strategy=strategy, preset=preset)

    # Validate result
    validation_errors = validate_migration(result)
    if validation_errors:
        return {
            "query_timestamp": query_ts,
            "status": "error",
            "error": "validation_failed",
            "message": "Migration produced invalid configuration",
            "validation_errors": validation_errors,
            "interest": result.interest_config,
        }

    # Dry run - just show what would change
    if dry_run:
        diff = format_migration_diff(profile_data, result)
        return {
            "query_timestamp": query_ts,
            "status": "dry_run",
            "message": f"Migration preview for '{profile_name}'",
            "diff": diff,
            "interest": result.interest_config,
            "changes": result.changes,
            "warnings": result.warnings,
        }

    # Apply migration
    profile_data["interest"] = result.interest_config

    # Write updated profile
    try:
        import yaml

        profile_path = Path(f"userdata/notifications/{profile_name}.yaml")
        with open(profile_path, "w") as f:
            yaml.dump(profile_data, f, default_flow_style=False, sort_keys=False)
    except Exception as e:
        return {
            "query_timestamp": query_ts,
            "status": "error",
            "error": "write_failed",
            "message": f"Failed to write profile: {e}",
            "interest": result.interest_config,
        }

    return {
        "query_timestamp": query_ts,
        "status": "ok",
        "message": f"Profile '{profile_name}' migrated to v2",
        "strategy": strategy.value,
        "interest": result.interest_config,
        "changes": result.changes,
        "warnings": result.warnings,
    }


def cmd_notifications_tune(args: argparse.Namespace) -> dict[str, Any]:
    """
    Show weight tuning visualization for a profile.

    Displays category weights and their current configuration,
    useful for interactive tuning.

    Args:
        args: Parsed arguments with profile name

    Returns:
        Result dict with weight visualization
    """
    query_ts = get_utc_timestamp()
    profile_name = args.profile

    # Load profile
    try:
        profile = ProfileLoader.load_profile(profile_name)
    except FileNotFoundError:
        return {
            "query_timestamp": query_ts,
            "status": "error",
            "error": "not_found",
            "message": f"Profile not found: {profile_name}",
        }

    # Check if profile uses v2
    if not profile.uses_interest_v2:
        return {
            "query_timestamp": query_ts,
            "status": "error",
            "error": "not_v2",
            "message": f"Profile '{profile_name}' does not use interest engine v2",
            "hint": "Use migrate-v2 to convert this profile first",
        }

    # Import tuning tools
    from ..services.redisq.interest_v2 import InterestConfigV2
    from ..services.redisq.interest_v2.cli.tune import format_weight_display
    from ..services.redisq.interest_v2.presets import get_preset_loader

    config = InterestConfigV2.from_dict(profile.interest)

    # Get effective weights
    if config.weights:
        weights = dict(config.weights)
    elif config.preset:
        loader = get_preset_loader()
        weights = loader.get_effective_weights(config.preset, config.customize)
    else:
        weights = {}

    # Format display
    display = format_weight_display(
        weights=weights,
        preset_name=config.preset,
        customize=config.customize,
    )

    return {
        "query_timestamp": query_ts,
        "status": "ok",
        "profile": profile_name,
        "display": display,
        "weights": weights,
        "preset": config.preset,
        "tier": config.tier.value,
    }


# =============================================================================
# Parser Registration
# =============================================================================


def register_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Register notification command parsers."""

    # Main notifications command with subcommands
    notifications_parser = subparsers.add_parser(
        "notifications",
        help="Manage notification profiles",
        description="Manage notification profiles for Discord webhook notifications. "
        "Profiles allow multiple Discord channels with independent topology filters, "
        "triggers, and throttling.",
    )

    notifications_subparsers = notifications_parser.add_subparsers(
        dest="notifications_command",
        help="Notification management commands",
    )

    # notifications list
    list_parser = notifications_subparsers.add_parser(
        "list",
        help="List all notification profiles",
    )
    list_parser.set_defaults(func=cmd_notifications_list)

    # notifications show <name>
    show_parser = notifications_subparsers.add_parser(
        "show",
        help="Show details of a profile",
    )
    show_parser.add_argument("name", help="Profile name")
    show_parser.set_defaults(func=cmd_notifications_show)

    # notifications create <name> --template <template> --webhook <url> [--persona <persona>]
    create_parser = notifications_subparsers.add_parser(
        "create",
        help="Create a new profile from template",
    )
    create_parser.add_argument("name", help="New profile name")
    create_parser.add_argument(
        "--template",
        required=True,
        help="Template to use (see 'notifications templates')",
    )
    create_parser.add_argument(
        "--webhook",
        required=True,
        help="Discord webhook URL",
    )
    create_parser.add_argument(
        "--persona",
        help="Persona for commentary (e.g., 'paria-s' for Serpentis). "
        "Enables commentary automatically. Options: aria, paria, paria-s",
    )
    create_parser.set_defaults(func=cmd_notifications_create)

    # notifications enable <name>
    enable_parser = notifications_subparsers.add_parser(
        "enable",
        help="Enable a profile",
    )
    enable_parser.add_argument("name", help="Profile name")
    enable_parser.set_defaults(func=cmd_notifications_enable)

    # notifications disable <name>
    disable_parser = notifications_subparsers.add_parser(
        "disable",
        help="Disable a profile",
    )
    disable_parser.add_argument("name", help="Profile name")
    disable_parser.set_defaults(func=cmd_notifications_disable)

    # notifications test <name>
    test_parser = notifications_subparsers.add_parser(
        "test",
        help="Send a test notification",
    )
    test_parser.add_argument("name", help="Profile name")
    test_parser.set_defaults(func=cmd_notifications_test)

    # notifications validate
    validate_parser = notifications_subparsers.add_parser(
        "validate",
        help="Validate all profiles",
    )
    validate_parser.set_defaults(func=cmd_notifications_validate)

    # notifications templates
    templates_parser = notifications_subparsers.add_parser(
        "templates",
        help="List available templates",
    )
    templates_parser.set_defaults(func=cmd_notifications_templates)

    # notifications delete <name> --force
    delete_parser = notifications_subparsers.add_parser(
        "delete",
        help="Delete a profile",
    )
    delete_parser.add_argument("name", help="Profile name")
    delete_parser.add_argument(
        "--force",
        action="store_true",
        help="Confirm deletion",
    )
    delete_parser.set_defaults(func=cmd_notifications_delete)

    # notifications migrate [--name <name>]
    migrate_parser = notifications_subparsers.add_parser(
        "migrate",
        help="Migrate legacy config.json webhook to YAML profile",
        description="Migrate webhook configuration from the legacy redisq.notifications "
        "section in config.json to a new YAML notification profile.",
    )
    migrate_parser.add_argument(
        "--name",
        default="migrated",
        help="Name for the new profile (default: 'migrated')",
    )
    migrate_parser.set_defaults(func=cmd_notifications_migrate)

    # =========================================================================
    # Interest Engine v2 Commands
    # =========================================================================

    # notifications explain <profile> <kill_id>
    explain_parser = notifications_subparsers.add_parser(
        "explain",
        help="Explain interest scoring for a kill (v2 only)",
        description="Show detailed breakdown of how each signal and category "
        "contributed to the interest score for a specific kill.",
    )
    explain_parser.add_argument("profile", help="Profile name")
    explain_parser.add_argument("kill_id", type=int, help="Kill ID to analyze")
    explain_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Include raw signal values",
    )
    explain_parser.set_defaults(func=cmd_notifications_explain)

    # notifications simulate <profile> [--hours N]
    simulate_parser = notifications_subparsers.add_parser(
        "simulate",
        help="Simulate v2 scoring on historical kills",
        description="Replay recent kills through the v2 engine to compare "
        "with v1 and identify potential notification changes.",
    )
    simulate_parser.add_argument("profile", help="Profile name")
    simulate_parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Hours of history to simulate (default: 24)",
    )
    simulate_parser.set_defaults(func=cmd_notifications_simulate)

    # notifications migrate-v2 <profile> [--strategy STR] [--preset NAME] [--dry-run]
    migrate_v2_parser = notifications_subparsers.add_parser(
        "migrate-v2",
        help="Migrate profile from v1 to v2 interest engine",
        description="Convert v1 topology and trigger configuration to v2 "
        "weighted interest scoring. Choose a strategy based on how you "
        "want to preserve existing behavior.",
    )
    migrate_v2_parser.add_argument("profile", help="Profile to migrate")
    migrate_v2_parser.add_argument(
        "--strategy",
        choices=["preserve-triggers", "weighted-only", "hybrid"],
        default="hybrid",
        help="Migration strategy: "
        "preserve-triggers (keep exact v1 behavior), "
        "weighted-only (pure weighted scoring), "
        "hybrid (weighted + critical triggers) [default]",
    )
    migrate_v2_parser.add_argument(
        "--preset",
        help="Override auto-detected preset (trade-hub, political, etc.)",
    )
    migrate_v2_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show migration diff without applying",
    )
    migrate_v2_parser.set_defaults(func=cmd_notifications_migrate_v2)

    # notifications tune <profile>
    tune_parser = notifications_subparsers.add_parser(
        "tune",
        help="Show weight tuning visualization (v2 only)",
        description="Display category weights for interactive tuning.",
    )
    tune_parser.add_argument("profile", help="Profile name")
    tune_parser.set_defaults(func=cmd_notifications_tune)

    # Set default for bare 'notifications' command
    notifications_parser.set_defaults(func=cmd_notifications_list)
