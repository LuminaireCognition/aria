"""
ARIA ESI Character Commands

Basic character information: profile, location, standings.
All commands require authentication.
"""

import argparse

from ..core import (
    CredentialsError,
    ESIClient,
    ESIError,
    get_authenticated_client,
    get_utc_timestamp,
)

# =============================================================================
# Profile Command
# =============================================================================


def cmd_profile(args: argparse.Namespace) -> dict:
    """
    Fetch pilot profile and standings.

    Returns character info and faction/corporation standings.
    """
    query_ts = get_utc_timestamp()

    try:
        client, creds = get_authenticated_client()
    except CredentialsError as e:
        return e.to_dict() | {"query_timestamp": query_ts}

    char_id = creds.character_id
    public_client = ESIClient()  # For public endpoints

    # Get character public info
    char_info = public_client.get_dict_safe(f"/characters/{char_id}/")

    # Get standings (authenticated)
    try:
        standings = client.get(f"/characters/{char_id}/standings/", auth=True)
    except ESIError:
        standings = []

    return {
        "query_timestamp": query_ts,
        "volatility": "semi_stable",
        "character": char_info,
        "standings": standings,
    }


# =============================================================================
# Location Command
# =============================================================================


def cmd_location(args: argparse.Namespace) -> dict:
    """
    Fetch current location and ship.

    Returns current solar system, station (if docked), and ship info.
    This data is VOLATILE - it changes as the player moves.
    """
    query_ts = get_utc_timestamp()

    try:
        client, creds = get_authenticated_client()
    except CredentialsError as e:
        return e.to_dict() | {"query_timestamp": query_ts}

    char_id = creds.character_id
    public_client = ESIClient()

    # Get location (authenticated)
    try:
        location = client.get_dict(f"/characters/{char_id}/location/", auth=True)
    except ESIError as e:
        return {
            "error": "location_error",
            "message": f"Could not fetch location: {e.message}",
            "query_timestamp": query_ts,
        }

    # Get ship (authenticated)
    try:
        ship = client.get_dict(f"/characters/{char_id}/ship/", auth=True)
    except ESIError:
        ship = {}

    # Extract IDs for resolution
    system_id = location.get("solar_system_id")
    station_id = location.get("station_id")
    structure_id = location.get("structure_id")
    ship_type_id = ship.get("ship_type_id")

    # Resolve system info
    system_name = "Unknown"
    security = 0.0
    if system_id:
        system_info = public_client.get_dict_safe(f"/universe/systems/{system_id}/")
        if system_info:
            system_name = system_info.get("name", "Unknown")
            security = round(system_info.get("security_status", 0), 2)

    # Resolve ship type
    ship_type_name = "Unknown"
    if ship_type_id:
        ship_type_info = public_client.get_dict_safe(f"/universe/types/{ship_type_id}/")
        if ship_type_info:
            ship_type_name = ship_type_info.get("name", "Unknown")

    ship_name = ship.get("ship_name", "")

    # Resolve station name if docked
    station_name = ""
    docked = False
    if station_id:
        station_info = public_client.get_dict_safe(f"/universe/stations/{station_id}/")
        if station_info:
            station_name = station_info.get("name", "")
        docked = True
    elif structure_id:
        # Structure requires auth to resolve name, just note it's a structure
        station_name = f"Structure ({structure_id})"
        docked = True

    return {
        "query_timestamp": query_ts,
        "volatility": "volatile",
        "system": system_name,
        "security": security,
        "station": station_name,
        "ship_type": ship_type_name,
        "ship_name": ship_name,
        "docked": docked,
    }


# =============================================================================
# Standings Command
# =============================================================================


def cmd_standings(args: argparse.Namespace) -> dict:
    """
    Fetch faction and corporation standings.

    Returns list of standings with faction/corp/agent.
    """
    query_ts = get_utc_timestamp()

    try:
        client, creds = get_authenticated_client()
    except CredentialsError as e:
        return e.to_dict() | {"query_timestamp": query_ts}

    char_id = creds.character_id
    public_client = ESIClient()

    # Get standings (authenticated)
    try:
        standings = client.get_list(f"/characters/{char_id}/standings/", auth=True)
    except ESIError as e:
        return {
            "error": "standings_error",
            "message": f"Could not fetch standings: {e.message}",
            "query_timestamp": query_ts,
        }

    # Resolve entity names for better readability
    resolved_standings = []
    for standing in standings:
        from_id = standing.get("from_id")
        from_type = standing.get("from_type")
        standing_value = standing.get("standing", 0)

        # Resolve name based on type
        name = None
        if from_type == "faction":
            faction_info = public_client.get_list_safe("/universe/factions/")
            for faction in faction_info:
                if isinstance(faction, dict) and faction.get("faction_id") == from_id:
                    name = faction.get("name")
                    break
        elif from_type == "npc_corp":
            corp_info = public_client.get_dict_safe(f"/corporations/{from_id}/")
            if corp_info:
                name = corp_info.get("name")
        elif from_type == "agent":
            # Agents are harder to resolve, just use ID
            name = f"Agent {from_id}"

        resolved_standings.append(
            {
                "from_id": from_id,
                "from_type": from_type,
                "name": name or f"{from_type} {from_id}",
                "standing": round(standing_value, 2),
            }
        )

    # Sort by standing value (highest first)
    resolved_standings.sort(key=lambda x: x["standing"], reverse=True)

    return {
        "query_timestamp": query_ts,
        "volatility": "semi_stable",
        "standings": resolved_standings,
    }


# =============================================================================
# Argument Parser Registration
# =============================================================================


def register_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Register character command parsers."""

    # Profile command
    profile_parser = subparsers.add_parser("profile", help="Fetch pilot profile and standings")
    profile_parser.set_defaults(func=cmd_profile)

    # Location command
    location_parser = subparsers.add_parser(
        "location", help="Fetch current location and ship (volatile)"
    )
    location_parser.set_defaults(func=cmd_location)

    # Standings command
    standings_parser = subparsers.add_parser(
        "standings", help="Fetch faction and corporation standings"
    )
    standings_parser.set_defaults(func=cmd_standings)
