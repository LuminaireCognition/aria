"""
ARIA ESI Pilot Commands

Pilot identity lookup and profile information.
Supports both public lookups and authenticated self-queries.
"""

import argparse
import re
from pathlib import Path

from ..core import (
    ESIClient,
    ESIError,
    get_credentials,
    get_pilot_directory,
    get_security_description,
    get_utc_timestamp,
)

# =============================================================================
# Pilot Command
# =============================================================================


def cmd_pilot(args: argparse.Namespace) -> dict:
    """
    Look up pilot identity information.

    Args:
        args: Parsed arguments with optional target (name/id)

    Returns:
        Pilot data dict with character info, corporation, alliance
    """
    target = getattr(args, "target", None)

    # Self query if no target or target is "me"/"self"
    if not target or target.lower() in ("me", "self"):
        return _cmd_pilot_self()

    # Public query for other pilots
    return _cmd_pilot_public(target)


def _cmd_pilot_self() -> dict:
    """
    Get full identity card for authenticated pilot.

    Includes ESI data and ARIA configuration from local profile.
    """
    query_ts = get_utc_timestamp()
    client = ESIClient()

    output = {"query_timestamp": query_ts, "query_type": "self", "esi_configured": False}

    # Try to get credentials
    try:
        creds = get_credentials(require=False)
    except Exception:
        creds = None

    if creds:
        output["esi_configured"] = True

        # Refresh token if needed
        creds.refresh_if_needed()

        # Create authenticated client
        auth_client = ESIClient(token=creds.access_token)
        char_id = creds.character_id

        # Get character public info
        char_info = client.get_character_info(char_id)
        if char_info:
            sec_status = char_info.get("security_status", 0)
            output["character"] = {
                "id": char_id,
                "name": char_info.get("name"),
                "birthday": char_info.get("birthday"),
                "security_status": round(sec_status, 2),
                "security_desc": get_security_description(sec_status),
            }

            # Resolve corporation
            corp_id = char_info.get("corporation_id")
            if corp_id:
                corp_info = client.get_corporation_info(corp_id)
                if corp_info:
                    output["character"]["corporation"] = {
                        "id": corp_id,
                        "name": corp_info.get("name"),
                        "ticker": corp_info.get("ticker"),
                    }

            # Resolve alliance if any
            alliance_id = char_info.get("alliance_id")
            if alliance_id:
                alliance_info = client.get_alliance_info(alliance_id)
                if alliance_info:
                    output["character"]["alliance"] = {
                        "id": alliance_id,
                        "name": alliance_info.get("name"),
                        "ticker": alliance_info.get("ticker"),
                    }

        # Get wallet (authenticated)
        try:
            wallet = auth_client.get(f"/characters/{char_id}/wallet/", auth=True)
            if wallet is not None and not isinstance(wallet, dict):
                output["wallet_balance"] = wallet
        except ESIError:
            pass

        # Get skills summary (authenticated)
        try:
            skills_data = auth_client.get(f"/characters/{char_id}/skills/", auth=True)
            if skills_data and isinstance(skills_data, dict) and "total_sp" in skills_data:
                output["skill_points"] = {
                    "total": skills_data.get("total_sp", 0),
                    "unallocated": skills_data.get("unallocated_sp", 0),
                }
        except ESIError:
            pass

        # ESI status from credentials
        output["esi_status"] = {
            "personal_scopes": len(creds.get_personal_scopes()),
            "corporation_scopes": len(creds.get_corp_scopes()),
            "token_expiry": creds.token_expiry,
        }

    # ARIA configuration from local profile
    pilot_dir = get_pilot_directory()
    if pilot_dir:
        profile_path = pilot_dir / "profile.md"
        if profile_path.exists():
            profile_config = _parse_profile_config(profile_path)
            if profile_config:
                output["aria_config"] = {
                    "eve_experience": profile_config.get("eve_experience", "intermediate"),
                    "rp_level": profile_config.get("rp_level", "off"),
                    "module_tier": profile_config.get("module_tier", "t1"),
                    "primary_faction": profile_config.get("primary_faction"),
                }

                if profile_config.get("constraints"):
                    output["constraints"] = profile_config["constraints"]

            output["profile_path"] = str(profile_path)

    return output


def _cmd_pilot_public(target: str) -> dict:
    """
    Look up public information for any pilot.

    Args:
        target: Character name or ID

    Returns:
        Public pilot data dict
    """
    query_ts = get_utc_timestamp()
    client = ESIClient()

    # Resolve character
    if target.isdigit():
        char_id: int | None = int(target)
        resolved_name = None
    else:
        char_id, resolved_name = client.resolve_character(target)

    if not char_id:
        return {
            "query_timestamp": query_ts,
            "query_type": "public",
            "error": "not_found",
            "message": f"No pilot found matching: {target}",
            "suggestions": [
                "Check spelling of character name",
                "Try using character ID if known",
                "Names are case-sensitive for exact match",
            ],
        }

    # Get character public info
    char_info = client.get_character_info(char_id)

    if not char_info:
        return {
            "query_timestamp": query_ts,
            "query_type": "public",
            "error": "not_found",
            "message": f"Could not retrieve data for character ID: {char_id}",
        }

    sec_status = char_info.get("security_status", 0)
    output: dict = {
        "query_timestamp": query_ts,
        "query_type": "public",
        "character": {
            "id": char_id,
            "name": char_info.get("name"),
            "birthday": char_info.get("birthday"),
            "security_status": round(sec_status, 2),
            "security_desc": get_security_description(sec_status),
        },
    }

    # Resolve corporation
    corp_id = char_info.get("corporation_id")
    if corp_id:
        corp_info = client.get_corporation_info(corp_id)
        if corp_info:
            output["character"]["corporation"] = {
                "id": corp_id,
                "name": corp_info.get("name"),
                "ticker": corp_info.get("ticker"),
            }

    # Resolve alliance if any
    alliance_id = char_info.get("alliance_id")
    if alliance_id:
        alliance_info = client.get_alliance_info(alliance_id)
        if alliance_info:
            output["character"]["alliance"] = {
                "id": alliance_id,
                "name": alliance_info.get("name"),
                "ticker": alliance_info.get("ticker"),
            }

    output["public_data_only"] = True

    return output


def _parse_profile_config(profile_path: Path) -> dict:
    """
    Extract ARIA configuration from profile.md.

    Args:
        profile_path: Path to profile.md file

    Returns:
        Config dict with eve_experience, rp_level, module_tier, etc.
    """
    config = {
        "character_name": None,
        "eve_experience": "intermediate",
        "rp_level": "off",
        "module_tier": "t1",
        "primary_faction": None,
        "constraints": {},
    }

    try:
        with open(profile_path) as f:
            content = f.read()
    except OSError:
        return config

    # Parse key-value pairs from markdown
    patterns = {
        "character_name": r"\*\*Character Name:\*\*\s*(.+)",
        "eve_experience": r"\*\*EVE Experience:\*\*\s*(\w+)",
        "rp_level": r"\*\*RP Level:\*\*\s*(\w+)",
        "module_tier": r"\*\*Module Tier:\*\*\s*(.+)",
        "primary_faction": r"\*\*Primary Faction:\*\*\s*(\w+)",
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            config[key] = match.group(1).strip()

    # Parse yaml constraint block
    yaml_match = re.search(r"```yaml\s*(.*?)\s*```", content, re.DOTALL)
    if yaml_match:
        yaml_content = yaml_match.group(1)
        for line in yaml_content.split("\n"):
            if ":" in line:
                key, val = line.split(":", 1)
                key = key.strip()
                val = val.split("#")[0].strip()  # Remove comments
                if val.lower() == "true":
                    config["constraints"][key] = True
                elif val.lower() == "false":
                    config["constraints"][key] = False
                else:
                    try:
                        config["constraints"][key] = float(val)
                    except ValueError:
                        config["constraints"][key] = val

    return config


# =============================================================================
# Argument Parser Registration
# =============================================================================


def register_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Register pilot command parsers."""

    pilot_parser = subparsers.add_parser("pilot", help="Look up pilot identity information")
    pilot_parser.add_argument(
        "target", nargs="?", default="me", help="Character name, ID, or 'me' for self (default: me)"
    )
    pilot_parser.set_defaults(func=cmd_pilot)
