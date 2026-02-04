"""
ARIA ESI Profile Sync Command

Syncs standings and security status from ESI to pilot profile.md.
Uses HTML comment markers for reliable section updates.
"""

import argparse
import re
from datetime import datetime, timezone
from typing import Optional

from ..core import (
    CredentialsError,
    ESIClient,
    ESIError,
    get_authenticated_client,
    get_pilot_directory,
    get_utc_timestamp,
)

# =============================================================================
# Constants
# =============================================================================

# Standing relation thresholds (value, label)
# Sorted from highest to lowest threshold
STANDING_RELATIONS = [
    (5.0, "Allied"),
    (1.0, "Aligned"),
    (0.1, "Friendly"),
    (-0.9, "Neutral"),
    (-4.9, "Unfriendly"),
    (-10.0, "Hostile"),
]

# Empire faction IDs
EMPIRE_FACTION_IDS = {
    500001,  # Caldari State
    500002,  # Minmatar Republic
    500003,  # Amarr Empire
    500004,  # Gallente Federation
}

# Pirate faction IDs
PIRATE_FACTION_IDS = {
    500010,  # Serpentis Corporation
    500011,  # Angel Cartel
    500012,  # Blood Raider Covenant
    500019,  # Sansha's Nation
    500020,  # Guristas Pirates
}

# Section markers for profile updates
MARKERS = {
    "empire": (
        "<!-- ESI-SYNC:STANDINGS-EMPIRE:START -->",
        "<!-- ESI-SYNC:STANDINGS-EMPIRE:END -->",
    ),
    "corps": (
        "<!-- ESI-SYNC:STANDINGS-CORPS:START -->",
        "<!-- ESI-SYNC:STANDINGS-CORPS:END -->",
    ),
    "pirates": (
        "<!-- ESI-SYNC:STANDINGS-PIRATES:START -->",
        "<!-- ESI-SYNC:STANDINGS-PIRATES:END -->",
    ),
    "security": (
        "<!-- ESI-SYNC:SECURITY:START -->",
        "<!-- ESI-SYNC:SECURITY:END -->",
    ),
}


# =============================================================================
# Helper Functions
# =============================================================================


def get_relation(standing: float) -> str:
    """Convert standing value to relation label."""
    for threshold, label in STANDING_RELATIONS:
        if standing >= threshold:
            return label
    return "Hostile"


def get_mission_access(standing: float) -> str:
    """Determine mission access level based on standing."""
    if standing >= 5.0:
        return "**L4 Missions**"
    elif standing >= 3.0:
        return "**L3 Missions** (L4 @ 5.0)"
    elif standing >= 1.0:
        return "**L2 Missions** (L3 @ 3.0)"
    elif standing >= 0.0:
        return "L1 Missions (L2 @ 1.0)"
    else:
        return "No access"


def format_sync_timestamp() -> str:
    """Format current timestamp for sync annotation."""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%d %H:%M UTC")


def update_section(content: str, section: str, new_content: str) -> tuple[str, bool]:
    """
    Update a section in the profile content between markers.

    Returns (updated_content, was_updated).
    If markers don't exist, returns original content unchanged.
    """
    start_marker, end_marker = MARKERS[section]

    # Pattern to match existing marker section
    pattern = re.compile(re.escape(start_marker) + r".*?" + re.escape(end_marker), re.DOTALL)

    # New section with markers
    new_section = f"{start_marker}\n{new_content}\n{end_marker}"

    if pattern.search(content):
        # Replace existing section
        updated = pattern.sub(new_section, content)
        return updated, True
    else:
        # Markers don't exist - cannot update
        return content, False


def add_markers_to_section(content: str, section_header: str, section_key: str) -> str:
    """
    Add markers around an existing section if they don't exist.

    Looks for the section header and wraps the table that follows it.
    """
    start_marker, end_marker = MARKERS[section_key]

    # Skip if markers already exist
    if start_marker in content:
        return content

    # Find the section header
    header_pattern = re.compile(
        rf"(### {re.escape(section_header)}\n)"
        r"(\|[^\n]+\|\n"  # Header row
        r"\|[-| ]+\|\n"  # Separator row
        r"(?:\|[^\n]+\|\n)*)"  # Data rows
    )

    match = header_pattern.search(content)
    if match:
        header = match.group(1)
        table = match.group(2).rstrip("\n")
        replacement = f"{header}{start_marker}\n{table}\n{end_marker}\n"
        content = content[: match.start()] + replacement + content[match.end() :]

    return content


# =============================================================================
# Main Sync Logic
# =============================================================================


def fetch_standings_data(client: ESIClient, char_id: int) -> dict:
    """Fetch and categorize standings from ESI."""
    public_client = ESIClient()

    # Fetch all standings
    try:
        standings = client.get(f"/characters/{char_id}/standings/", auth=True)
    except ESIError as e:
        return {"error": f"Failed to fetch standings: {e.message}"}

    if not isinstance(standings, list):
        standings = []

    # Fetch all faction info for name resolution
    factions = {}
    faction_data = public_client.get_list_safe("/universe/factions/")
    for f in faction_data:
        if isinstance(f, dict):
            factions[f.get("faction_id")] = f.get("name", f"Faction {f.get('faction_id')}")

    # Categorize standings
    empire_standings = []
    corp_standings = []
    pirate_standings = []

    for s in standings:
        from_id = s.get("from_id")
        from_type = s.get("from_type")
        standing = round(s.get("standing", 0), 2)

        if from_type == "faction":
            name = factions.get(from_id, f"Faction {from_id}")
            entry = {"id": from_id, "name": name, "standing": standing}

            if from_id in EMPIRE_FACTION_IDS:
                empire_standings.append(entry)
            elif from_id in PIRATE_FACTION_IDS:
                pirate_standings.append(entry)

        elif from_type == "npc_corp":
            # Resolve corporation name
            corp_info = public_client.get_dict_safe(f"/corporations/{from_id}/")
            name = (
                corp_info.get("name", f"Corporation {from_id}")
                if corp_info
                else f"Corporation {from_id}"
            )
            corp_standings.append({"id": from_id, "name": name, "standing": standing})

    # Sort by standing (highest first)
    empire_standings.sort(key=lambda x: x["standing"], reverse=True)
    corp_standings.sort(key=lambda x: x["standing"], reverse=True)
    pirate_standings.sort(key=lambda x: x["standing"], reverse=True)

    return {
        "empire": empire_standings,
        "corps": corp_standings,
        "pirates": pirate_standings,
    }


def fetch_security_status(char_id: int) -> Optional[float]:
    """Fetch character security status from public info."""
    public_client = ESIClient()
    char_info = public_client.get_dict_safe(f"/characters/{char_id}/")
    if char_info:
        return round(char_info.get("security_status", 0), 2)
    return None


def format_empire_table(standings: list, timestamp: str) -> str:
    """Format empire factions standings table."""
    lines = [
        "| Faction | Standing | Relation |",
        "|---------|----------|----------|",
    ]
    for s in standings:
        relation = get_relation(s["standing"])
        lines.append(f"| {s['name']} | {s['standing']:.2f} | {relation} |")
    lines.append(f"*Synced: {timestamp}*")
    return "\n".join(lines)


def format_corps_table(standings: list, timestamp: str) -> str:
    """Format mission corporations standings table."""
    lines = [
        "| Corporation | Standing | Access |",
        "|-------------|----------|--------|",
    ]
    for s in standings:
        access = get_mission_access(s["standing"])
        lines.append(f"| {s['name']} | {s['standing']:.2f} | {access} |")
    lines.append(f"*Synced: {timestamp}*")
    return "\n".join(lines)


def format_pirates_table(standings: list, timestamp: str) -> str:
    """Format pirate factions standings table."""
    lines = [
        "| Faction | Standing | Notes |",
        "|---------|----------|-------|",
    ]
    for s in standings:
        # Negative standings are normal for pirates
        note = "Target" if s["standing"] < 0 else "Friendly"
        lines.append(f"| {s['name']} | {s['standing']:.2f} | {note} |")
    lines.append(f"*Synced: {timestamp}*")
    return "\n".join(lines)


def sync_profile(dry_run: bool = False) -> dict:
    """
    Sync standings from ESI to pilot profile.md.

    Args:
        dry_run: If True, show changes without writing to file

    Returns:
        Result dict with sync status
    """
    query_ts = get_utc_timestamp()

    # Authenticate
    try:
        client, creds = get_authenticated_client()
    except CredentialsError as e:
        return e.to_dict() | {"query_timestamp": query_ts}

    char_id = creds.character_id

    # Get pilot directory
    pilot_dir = get_pilot_directory()
    if not pilot_dir:
        return {
            "error": "no_pilot_directory",
            "message": "Could not resolve active pilot directory",
            "query_timestamp": query_ts,
        }

    profile_path = pilot_dir / "profile.md"
    if not profile_path.exists():
        return {
            "error": "no_profile",
            "message": f"Profile not found: {profile_path}",
            "query_timestamp": query_ts,
        }

    # Fetch data
    standings_data = fetch_standings_data(client, char_id)
    if "error" in standings_data:
        return {
            "error": "esi_error",
            "message": standings_data["error"],
            "query_timestamp": query_ts,
        }

    security_status = fetch_security_status(char_id)

    # Read current profile
    profile_content = profile_path.read_text()
    original_content = profile_content

    # Format timestamp
    timestamp = format_sync_timestamp()

    # Add markers if they don't exist
    profile_content = add_markers_to_section(profile_content, "Empire Factions", "empire")
    profile_content = add_markers_to_section(profile_content, "Mission Corporations", "corps")
    profile_content = add_markers_to_section(profile_content, "Pirate Factions", "pirates")

    # Track what was updated
    updates = []

    # Update empire standings
    if standings_data["empire"]:
        table = format_empire_table(standings_data["empire"], timestamp)
        profile_content, updated = update_section(profile_content, "empire", table)
        if updated:
            updates.append("empire_standings")

    # Update corp standings
    if standings_data["corps"]:
        table = format_corps_table(standings_data["corps"], timestamp)
        profile_content, updated = update_section(profile_content, "corps", table)
        if updated:
            updates.append("corp_standings")

    # Update pirate standings
    if standings_data["pirates"]:
        table = format_pirates_table(standings_data["pirates"], timestamp)
        profile_content, updated = update_section(profile_content, "pirates", table)
        if updated:
            updates.append("pirate_standings")

    # Update security status in the identity section
    if security_status is not None:
        # Pattern to match security status line
        sec_pattern = re.compile(r"- \*\*Security Status:\*\* [^\n]+")
        new_sec_line = f"- **Security Status:** {security_status:.2f} (synced {timestamp})"
        if sec_pattern.search(profile_content):
            profile_content = sec_pattern.sub(new_sec_line, profile_content)
            updates.append("security_status")

    # Prepare result
    result = {
        "query_timestamp": query_ts,
        "pilot_directory": str(pilot_dir),
        "profile_path": str(profile_path),
        "dry_run": dry_run,
        "updates": updates,
        "standings_found": {
            "empire": len(standings_data["empire"]),
            "corps": len(standings_data["corps"]),
            "pirates": len(standings_data["pirates"]),
        },
        "security_status": security_status,
    }

    # Check if anything changed
    if profile_content == original_content:
        result["status"] = "no_changes"
        result["message"] = "Profile already up to date or markers not found"
        return result

    if dry_run:
        result["status"] = "dry_run"
        result["message"] = "Changes detected (not written)"
        result["changes_preview"] = {
            "sections_updated": updates,
        }
    else:
        # Write updated profile
        profile_path.write_text(profile_content)
        result["status"] = "synced"
        result["message"] = f"Profile updated: {', '.join(updates)}"

    return result


# =============================================================================
# Command Handler
# =============================================================================


def cmd_sync_profile(args: argparse.Namespace) -> dict:
    """Handle sync-profile command."""
    return sync_profile(dry_run=args.dry_run)


# =============================================================================
# Argument Parser Registration
# =============================================================================


def register_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Register sync-profile command parser."""
    parser = subparsers.add_parser(
        "sync-profile",
        help="Sync standings from ESI to pilot profile.md",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing to file",
    )
    parser.set_defaults(func=cmd_sync_profile)
