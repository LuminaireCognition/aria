"""
ARIA ESI Clone Commands

Clone status, jump clones, and implant tracking.
Safety-critical information for mission running and PvP.
"""

import argparse

from ..core import (
    CredentialsError,
    ESIClient,
    ESIError,
    format_duration,
    get_authenticated_client,
    get_utc_timestamp,
    parse_datetime,
)

# =============================================================================
# Implant Slot Mapping
# =============================================================================

# Implant slots are determined by dogma attributes, but we can infer from type
# These are common implant slot prefixes/patterns
IMPLANT_SLOT_HINTS = {
    # Attribute enhancers (slots 1-5)
    "Limited": 1,  # Often slot 1-5 variants
    "Limited Social Adaptation Chip": 1,
    "Memory Augmentation": 4,
    "Neural Boost": 5,
    "Ocular Filter": 1,
    "Cybernetic Subprocessor": 5,
    "Social Adaptation Chip": 1,
    # Hardwirings typically slots 6-10
    "Zainou": None,  # Various slots
    "Eifyr": None,
    "Inherent Implants": None,
    "Hardwiring": None,
}

# Slot number to name mapping
SLOT_NAMES = {
    1: "Perception",
    2: "Memory",
    3: "Willpower",
    4: "Intelligence",
    5: "Charisma",
    6: "Slot 6",
    7: "Slot 7",
    8: "Slot 8",
    9: "Slot 9",
    10: "Slot 10",
}


def _get_implant_details(client: ESIClient, type_id: int) -> dict:
    """
    Get implant details including name and slot.

    Returns dict with name, slot (if determinable), and description.
    """
    type_info = client.get_dict_safe(f"/universe/types/{type_id}/")

    if not type_info:
        return {
            "type_id": type_id,
            "name": f"Unknown Implant ({type_id})",
            "slot": None,
            "description": None,
        }

    name = type_info.get("name", f"Implant {type_id}")
    description = type_info.get("description", "")

    # Try to determine slot from dogma attributes
    slot = None
    dogma_attrs = type_info.get("dogma_attributes", [])

    for attr in dogma_attrs:
        # Attribute ID 331 is implantness (slot number)
        if attr.get("attribute_id") == 331:
            slot = int(attr.get("value", 0))
            break

    return {
        "type_id": type_id,
        "name": name,
        "slot": slot,
        "description": description[:200] if description else None,
    }


def _resolve_location(client: ESIClient, location_id: int, location_type: str) -> dict:
    """
    Resolve a location ID to name and details.

    Args:
        client: ESI client
        location_id: The location ID
        location_type: "station" or "structure"

    Returns:
        Dict with location_id, name, system_id, system_name
    """
    result = {
        "location_id": location_id,
        "location_type": location_type,
        "name": f"Unknown Location ({location_id})",
        "system_id": None,
        "system_name": None,
    }

    if location_type == "station":
        station_info = client.get_dict_safe(f"/universe/stations/{location_id}/")
        if station_info:
            result["name"] = station_info.get("name", result["name"])
            result["system_id"] = station_info.get("system_id")
    elif location_type == "structure":
        # Structures require auth and may not be accessible
        # Just note it's a player structure
        result["name"] = f"Player Structure ({location_id})"

    # Resolve system name if we have system_id
    if result["system_id"]:
        system_info = client.get_dict_safe(f"/universe/systems/{result['system_id']}/")
        if system_info:
            result["system_name"] = system_info.get("name")

    return result


# =============================================================================
# Clones Command
# =============================================================================


def cmd_clones(args: argparse.Namespace) -> dict:
    """
    Fetch full clone status including home station, jump clones, and implants.

    This is safety-critical information - knowing your clone location
    before risky activities prevents loss of implants and skill points.
    """
    query_ts = get_utc_timestamp()
    show_implants = not getattr(args, "no_implants", False)

    try:
        client, creds = get_authenticated_client()
    except CredentialsError as e:
        return e.to_dict() | {"query_timestamp": query_ts}

    char_id = creds.character_id
    public_client = ESIClient()

    # Check for required scope
    if not creds.has_scope("esi-clones.read_clones.v1"):
        return {
            "error": "scope_not_authorized",
            "message": "Missing required scope: esi-clones.read_clones.v1",
            "action": "Re-run OAuth setup to authorize clone access",
            "command": "python3 .claude/scripts/aria-oauth-setup.py",
            "query_timestamp": query_ts,
        }

    # Fetch clone data
    try:
        clone_data = client.get(f"/characters/{char_id}/clones/", auth=True)
    except ESIError as e:
        return {
            "error": "esi_error",
            "message": f"Could not fetch clone data: {e.message}",
            "query_timestamp": query_ts,
        }

    if not isinstance(clone_data, dict):
        return {
            "error": "unexpected_response",
            "message": "Invalid clone data received from ESI",
            "query_timestamp": query_ts,
        }

    # Process home location
    home_location = None
    home_data = clone_data.get("home_location", {})
    if home_data:
        home_location = _resolve_location(
            public_client, home_data.get("location_id"), home_data.get("location_type", "station")
        )

    # Process jump clones
    jump_clones = []
    for jc in clone_data.get("jump_clones", []):
        jc_location = _resolve_location(
            public_client, jc.get("location_id"), jc.get("location_type", "station")
        )

        # Get implants in this jump clone
        jc_implants = []
        for impl_id in jc.get("implants", []):
            impl_info = _get_implant_details(public_client, impl_id)
            jc_implants.append(impl_info)

        # Sort implants by slot
        jc_implants.sort(key=lambda x: x.get("slot") or 99)

        jump_clones.append(
            {
                "jump_clone_id": jc.get("jump_clone_id"),
                "location": jc_location,
                "name": jc.get("name"),  # Player-assigned name
                "implant_count": len(jc_implants),
                "implants": jc_implants,
            }
        )

    # Calculate jump clone cooldown
    last_jump = clone_data.get("last_clone_jump_date")
    jump_cooldown = None
    can_jump = True

    if last_jump:
        last_jump_dt = parse_datetime(last_jump)
        if last_jump_dt:
            from datetime import datetime, timedelta, timezone

            now = datetime.now(timezone.utc)
            cooldown_end = last_jump_dt + timedelta(hours=24)

            if now < cooldown_end:
                remaining = (cooldown_end - now).total_seconds()
                jump_cooldown = format_duration(remaining)
                can_jump = False
            else:
                can_jump = True

    # Build output
    output = {
        "query_timestamp": query_ts,
        "volatility": "semi_stable",
        "home_location": home_location,
        "jump_clone_count": len(jump_clones),
        "jump_clones": jump_clones,
        "last_clone_jump": last_jump,
        "jump_available": can_jump,
        "jump_cooldown_remaining": jump_cooldown,
    }

    # Optionally fetch active implants
    if show_implants:
        if creds.has_scope("esi-clones.read_implants.v1"):
            try:
                implant_ids = client.get(f"/characters/{char_id}/implants/", auth=True)
                if isinstance(implant_ids, list):
                    active_implants = []
                    for impl_id in implant_ids:
                        impl_info = _get_implant_details(public_client, impl_id)
                        active_implants.append(impl_info)

                    # Sort by slot
                    active_implants.sort(key=lambda x: x.get("slot") or 99)
                    output["active_implants"] = active_implants
                    output["active_implant_count"] = len(active_implants)
            except ESIError:
                output["active_implants"] = None
                output["active_implants_error"] = "Could not fetch active implants"
        else:
            output["active_implants"] = None
            output["active_implants_note"] = "Scope esi-clones.read_implants.v1 not authorized"

    return output


# =============================================================================
# Implants Command
# =============================================================================


def cmd_implants(args: argparse.Namespace) -> dict:
    """
    Fetch active implants in current clone.

    Shows all implants currently plugged in, organized by slot.
    """
    query_ts = get_utc_timestamp()

    try:
        client, creds = get_authenticated_client()
    except CredentialsError as e:
        return e.to_dict() | {"query_timestamp": query_ts}

    char_id = creds.character_id
    public_client = ESIClient()

    # Check for required scope
    if not creds.has_scope("esi-clones.read_implants.v1"):
        return {
            "error": "scope_not_authorized",
            "message": "Missing required scope: esi-clones.read_implants.v1",
            "action": "Re-run OAuth setup to authorize implant access",
            "command": "python3 .claude/scripts/aria-oauth-setup.py",
            "query_timestamp": query_ts,
        }

    # Fetch implant data
    try:
        implant_ids = client.get(f"/characters/{char_id}/implants/", auth=True)
    except ESIError as e:
        return {
            "error": "esi_error",
            "message": f"Could not fetch implants: {e.message}",
            "query_timestamp": query_ts,
        }

    if not isinstance(implant_ids, list):
        implant_ids = []

    if not implant_ids:
        return {
            "query_timestamp": query_ts,
            "volatility": "semi_stable",
            "implant_count": 0,
            "implants": [],
            "message": "No implants currently installed in active clone",
        }

    # Resolve implant details
    implants = []
    attribute_implants = []  # Slots 1-5
    hardwiring_implants = []  # Slots 6-10

    for impl_id in implant_ids:
        impl_info = _get_implant_details(public_client, impl_id)
        slot = impl_info.get("slot")

        if slot and 1 <= slot <= 5:
            attribute_implants.append(impl_info)
        elif slot and 6 <= slot <= 10:
            hardwiring_implants.append(impl_info)
        else:
            implants.append(impl_info)

    # Sort each category by slot
    attribute_implants.sort(key=lambda x: x.get("slot") or 99)
    hardwiring_implants.sort(key=lambda x: x.get("slot") or 99)
    implants.sort(key=lambda x: x.get("slot") or 99)

    # Calculate total implant value risk
    # (Note: we don't have market prices here, but we note the count)

    return {
        "query_timestamp": query_ts,
        "volatility": "semi_stable",
        "implant_count": len(implant_ids),
        "attribute_enhancers": attribute_implants,
        "hardwirings": hardwiring_implants,
        "other": implants if implants else None,
        "safety_note": "These implants will be lost if your pod is destroyed",
    }


# =============================================================================
# Jump Clone Command
# =============================================================================


def cmd_jump_clones(args: argparse.Namespace) -> dict:
    """
    Fetch jump clone locations and status.

    Shows where your jump clones are located and cooldown status.
    """
    query_ts = get_utc_timestamp()

    try:
        client, creds = get_authenticated_client()
    except CredentialsError as e:
        return e.to_dict() | {"query_timestamp": query_ts}

    char_id = creds.character_id
    public_client = ESIClient()

    # Check for required scope
    if not creds.has_scope("esi-clones.read_clones.v1"):
        return {
            "error": "scope_not_authorized",
            "message": "Missing required scope: esi-clones.read_clones.v1",
            "action": "Re-run OAuth setup to authorize clone access",
            "command": "python3 .claude/scripts/aria-oauth-setup.py",
            "query_timestamp": query_ts,
        }

    # Fetch clone data
    try:
        clone_data = client.get(f"/characters/{char_id}/clones/", auth=True)
    except ESIError as e:
        return {
            "error": "esi_error",
            "message": f"Could not fetch clone data: {e.message}",
            "query_timestamp": query_ts,
        }

    if not isinstance(clone_data, dict):
        return {
            "error": "unexpected_response",
            "message": "Invalid clone data received",
            "query_timestamp": query_ts,
        }

    # Process jump clones
    jump_clones = []
    for jc in clone_data.get("jump_clones", []):
        jc_location = _resolve_location(
            public_client, jc.get("location_id"), jc.get("location_type", "station")
        )

        implant_count = len(jc.get("implants", []))

        jump_clones.append(
            {
                "jump_clone_id": jc.get("jump_clone_id"),
                "name": jc.get("name"),
                "location": jc_location.get("name"),
                "system": jc_location.get("system_name"),
                "implant_count": implant_count,
            }
        )

    # Calculate cooldown
    last_jump = clone_data.get("last_clone_jump_date")
    jump_cooldown = None
    can_jump = True
    next_jump_available = None

    if last_jump:
        last_jump_dt = parse_datetime(last_jump)
        if last_jump_dt:
            from datetime import datetime, timedelta, timezone

            now = datetime.now(timezone.utc)
            cooldown_end = last_jump_dt + timedelta(hours=24)

            if now < cooldown_end:
                remaining = (cooldown_end - now).total_seconds()
                jump_cooldown = format_duration(remaining)
                next_jump_available = cooldown_end.isoformat()
                can_jump = False

    return {
        "query_timestamp": query_ts,
        "volatility": "semi_stable",
        "jump_clone_count": len(jump_clones),
        "jump_clones": jump_clones,
        "jump_available": can_jump,
        "cooldown_remaining": jump_cooldown,
        "next_jump_available": next_jump_available,
        "last_jump": last_jump,
    }


# =============================================================================
# Argument Parser Registration
# =============================================================================


def register_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Register clone command parsers."""

    # Full clone status command
    clones_parser = subparsers.add_parser(
        "clones", help="Full clone status (home, jump clones, implants)"
    )
    clones_parser.add_argument(
        "--no-implants", action="store_true", help="Skip fetching active implant details"
    )
    clones_parser.set_defaults(func=cmd_clones)

    # Active implants only
    implants_parser = subparsers.add_parser("implants", help="Active implants in current clone")
    implants_parser.set_defaults(func=cmd_implants)

    # Jump clones only
    jump_parser = subparsers.add_parser(
        "jump-clones", help="Jump clone locations and cooldown status"
    )
    jump_parser.set_defaults(func=cmd_jump_clones)
