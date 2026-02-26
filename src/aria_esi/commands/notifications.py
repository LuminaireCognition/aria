"""
ARIA Notification Profile Commands

Manage notification profiles for Discord webhook notifications.
Profiles allow multiple Discord channels with independent topology filters,
triggers, and throttling.
"""

import argparse
import asyncio
from typing import Any

from ..core import get_utc_timestamp


def _get_notifications():
    """Lazy import notification services (pulls in RedisQ dependencies)."""
    from ..services.redisq.notifications import (
        ProfileLoader,
        get_profiles_summary,
    )

    return ProfileLoader, get_profiles_summary


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
    _, get_profiles_summary = _get_notifications()
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
    ProfileLoader, _ = _get_notifications()
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
    ProfileLoader, _ = _get_notifications()
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
    except Exception as e:  # noqa: BLE001 -- CLI handler
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
    ProfileLoader, _ = _get_notifications()
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
    ProfileLoader, _ = _get_notifications()
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
    ProfileLoader, _ = _get_notifications()
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
    ProfileLoader, _ = _get_notifications()
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
        except Exception:  # noqa: BLE001 -- CLI handler
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
    ProfileLoader, _ = _get_notifications()
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
    ProfileLoader, _ = _get_notifications()
    query_ts = get_utc_timestamp()
    profile_name = args.profile
    _kill_id = args.kill_id  # Reserved for kill store integration
    _verbose = getattr(args, "verbose", False)  # Reserved for verbose output

    # Load profile (validates existence)
    try:
        ProfileLoader.load_profile(profile_name)
    except FileNotFoundError:
        return {
            "query_timestamp": query_ts,
            "status": "error",
            "error": "not_found",
            "message": f"Profile not found: {profile_name}",
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
    ProfileLoader, _ = _get_notifications()
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
    ProfileLoader, _ = _get_notifications()
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
