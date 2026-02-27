"""
ARIA ESI Sync Command

Pre-fetches EVE Online data to populate local files.
Runs in background during boot to minimize startup latency.

Synced Data:
    - Ship roster (from assets API) → ships.md
    - Current ship/location (volatile snapshot) → .esi-sync.json
    - Blueprints → industry/blueprints.md
    - Wallet balance → .esi-sync.json
"""

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..core import (
    CredentialsError,
    ESIClient,
    ESIError,
    get_authenticated_client,
    get_pilot_directory,
    get_ship_group_ids,
    get_utc_timestamp,
)

# =============================================================================
# Data Fetching
# =============================================================================


def fetch_ship_roster(client: ESIClient, char_id: int) -> list[dict[str, Any]]:
    """Fetch all ships from character assets."""
    try:
        assets = client.get_list(f"/characters/{char_id}/assets/", auth=True)
    except ESIError:
        return []

    # Collect assembled hangar items and their type IDs
    ship_assets = []
    type_ids: set[int] = set()

    for asset in assets:
        if not asset.get("is_singleton", False):
            continue
        if asset.get("location_flag") != "Hangar":
            continue
        type_ids.add(asset["type_id"])
        ship_assets.append(asset)

    # Resolve type info to filter to ships and get names
    ship_group_ids = get_ship_group_ids()
    type_info: dict[int, dict[str, Any]] = {}
    for tid in type_ids:
        info = client.get_dict_safe(f"/universe/types/{tid}/")
        if info and "name" in info:
            type_info[tid] = {"name": info["name"], "group_id": info.get("group_id", 0)}

    # Filter to only ships and build roster
    ships: list[dict[str, Any]] = []
    ship_item_ids: list[int] = []

    for asset in ship_assets:
        tid = asset["type_id"]
        tinfo = type_info.get(tid, {})

        if tinfo.get("group_id", 0) not in ship_group_ids:
            continue

        ships.append(
            {
                "item_id": asset["item_id"],
                "type_id": tid,
                "type_name": tinfo.get("name", f"Unknown-{tid}"),
                "location_id": asset["location_id"],
            }
        )
        ship_item_ids.append(asset["item_id"])

    # Fetch custom ship names
    if ship_item_ids:
        names_response = client.post_safe(
            f"/characters/{char_id}/assets/names/", data=ship_item_ids, auth=True
        )
        if isinstance(names_response, list):
            name_lookup = {n["item_id"]: n["name"] for n in names_response}
            for ship in ships:
                custom_name = name_lookup.get(ship["item_id"], "")
                ship["custom_name"] = custom_name if custom_name != ship["type_name"] else ""

    # Resolve location names
    location_ids = {s["location_id"] for s in ships}
    location_names: dict[int, str] = {}
    for lid in location_ids:
        station_info = client.get_dict_safe(f"/universe/stations/{lid}/")
        if station_info and "name" in station_info:
            location_names[lid] = station_info["name"]
        else:
            location_names[lid] = f"Structure-{lid}"

    for ship in ships:
        ship["location_name"] = location_names.get(ship["location_id"], "Unknown")

    return ships


def fetch_current_location(client: ESIClient, char_id: int) -> dict[str, Any]:
    """Fetch current location and ship (volatile)."""
    location = client.get_dict_safe(f"/characters/{char_id}/location/", auth=True)
    ship = client.get_dict_safe(f"/characters/{char_id}/ship/", auth=True)

    if not location or not ship:
        return {"error": "Failed to fetch location/ship"}

    # Resolve names
    system_id = location.get("solar_system_id", 0)
    ship_type_id = ship.get("ship_type_id", 0)

    system_info = client.get_dict_safe(f"/universe/systems/{system_id}/")
    ship_type_info = client.get_dict_safe(f"/universe/types/{ship_type_id}/")

    result: dict[str, Any] = {
        "solar_system_id": system_id,
        "solar_system_name": system_info.get("name", "Unknown") if system_info else "Unknown",
        "security_status": round(system_info.get("security_status", 0), 1) if system_info else 0,
        "ship_type_id": ship_type_id,
        "ship_type_name": ship_type_info.get("name", "Unknown") if ship_type_info else "Unknown",
        "ship_name": ship.get("ship_name", ""),
        "ship_item_id": ship.get("ship_item_id", 0),
    }

    # Check if docked
    station_id = location.get("station_id")
    if station_id:
        station_info = client.get_dict_safe(f"/universe/stations/{station_id}/")
        result["station_id"] = station_id
        result["station_name"] = station_info.get("name", "Unknown") if station_info else "Unknown"
        result["docked"] = True
    else:
        result["docked"] = False

    return result


def fetch_blueprints(client: ESIClient, char_id: int) -> dict[str, Any]:
    """Fetch character blueprints."""
    try:
        blueprints = client.get_list(f"/characters/{char_id}/blueprints/", auth=True)
    except ESIError:
        return {"error": "Failed to fetch blueprints", "bpos": [], "bpcs": []}

    # Resolve type names
    type_ids = {bp["type_id"] for bp in blueprints}
    type_names: dict[int, str] = {}
    for tid in type_ids:
        info = client.get_dict_safe(f"/universe/types/{tid}/")
        if info and "name" in info:
            type_names[tid] = info["name"]

    bpos: list[dict[str, Any]] = []
    bpcs: list[dict[str, Any]] = []

    for bp in blueprints:
        tid = bp["type_id"]
        entry: dict[str, Any] = {
            "type_id": tid,
            "name": type_names.get(tid, f"Unknown-{tid}"),
            "material_efficiency": bp.get("material_efficiency", 0),
            "time_efficiency": bp.get("time_efficiency", 0),
        }

        if bp.get("quantity") == -1:
            bpos.append(entry)
        else:
            entry["runs"] = bp.get("runs", 0)
            bpcs.append(entry)

    bpos.sort(key=lambda x: x["name"])
    bpcs.sort(key=lambda x: x["name"])

    return {"bpos": bpos, "bpcs": bpcs}


def fetch_wallet(client: ESIClient, char_id: int) -> float:
    """Fetch wallet balance."""
    result = client.get_safe(f"/characters/{char_id}/wallet/", auth=True)
    if isinstance(result, (int, float)):
        return float(result)
    return 0.0


# =============================================================================
# File Updates
# =============================================================================


def update_ships_md(pilot_dir: Path, ships: list[dict[str, Any]]) -> bool:
    """Update ships.md with synced roster while preserving fitting details."""
    ships_path = pilot_dir / "ships.md"

    # Read existing content
    existing_content = ""
    if ships_path.exists():
        try:
            existing_content = ships_path.read_text()
        except OSError:
            pass

    # Build new roster section
    sync_time = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    roster_lines = [
        "<!-- ESI-SYNC:ROSTER:START -->",
        "## Ship Roster (ESI Synced)",
        f"*Last sync: {sync_time}*",
        "",
        "| Name | Hull | Location |",
        "|------|------|----------|",
    ]

    for ship in sorted(ships, key=lambda x: x["type_name"]):
        name = ship.get("custom_name") or "(unnamed)"
        hull = ship["type_name"]
        location = (
            ship["location_name"].split(" - ")[0]
            if " - " in ship["location_name"]
            else ship["location_name"]
        )
        if len(location) > 25:
            location = location[:22] + "..."
        roster_lines.append(f"| {name} | {hull} | {location} |")

    roster_lines.extend(["", f"*{len(ships)} ships in hangars*", "<!-- ESI-SYNC:ROSTER:END -->"])

    new_roster = "\n".join(roster_lines)

    # Check if file has sync markers
    if "<!-- ESI-SYNC:ROSTER:START -->" in existing_content:
        pattern = r"<!-- ESI-SYNC:ROSTER:START -->.*?<!-- ESI-SYNC:ROSTER:END -->"
        new_content = re.sub(pattern, new_roster, existing_content, flags=re.DOTALL)
    else:
        header_match = re.search(r"^# Ship Status\n+", existing_content)
        if header_match:
            insert_pos = header_match.end()
            new_content = (
                existing_content[:insert_pos] + new_roster + "\n\n" + existing_content[insert_pos:]
            )
        else:
            new_content = "# Ship Status\n\n" + new_roster + "\n\n" + existing_content

    try:
        ships_path.write_text(new_content)
        return True
    except OSError:
        return False


def update_blueprints_md(pilot_dir: Path, bp_data: dict[str, Any]) -> bool:
    """Update blueprints.md with synced data."""
    bp_path = pilot_dir / "industry" / "blueprints.md"

    # Ensure industry directory exists
    (pilot_dir / "industry").mkdir(exist_ok=True)

    sync_time = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "# Blueprint Library",
        "",
        "<!-- ESI-SYNC:BLUEPRINTS:START -->",
        f"*Last ESI sync: {sync_time}*",
        "",
        "## Blueprint Originals (BPOs)",
        "",
        "| Blueprint | ME | TE |",
        "|-----------|----|----|",
    ]

    for bpo in bp_data.get("bpos", []):
        lines.append(
            f"| {bpo['name']} | {bpo['material_efficiency']}% | {bpo['time_efficiency']}% |"
        )

    if not bp_data.get("bpos"):
        lines.append("| *No BPOs owned* | - | - |")

    lines.extend(
        [
            "",
            f"*{len(bp_data.get('bpos', []))} BPOs total*",
            "",
            "## Blueprint Copies (BPCs)",
            "",
            "| Blueprint | Runs | ME | TE |",
            "|-----------|------|----|----|",
        ]
    )

    for bpc in bp_data.get("bpcs", []):
        lines.append(
            f"| {bpc['name']} | {bpc.get('runs', '?')} "
            f"| {bpc['material_efficiency']}% | {bpc['time_efficiency']}% |"
        )

    if not bp_data.get("bpcs"):
        lines.append("| *No BPCs owned* | - | - | - |")

    lines.extend(
        ["", f"*{len(bp_data.get('bpcs', []))} BPCs total*", "<!-- ESI-SYNC:BLUEPRINTS:END -->"]
    )

    try:
        bp_path.write_text("\n".join(lines))
        return True
    except OSError:
        return False


def write_sync_manifest(pilot_dir: Path, manifest_data: dict[str, Any]) -> bool:
    """Write the sync manifest."""
    manifest_path = pilot_dir / ".esi-sync.json"

    try:
        manifest_path.write_text(json.dumps(manifest_data, indent=2))
        return True
    except OSError:
        return False


# =============================================================================
# Character Name Resolution
# =============================================================================


def _get_character_name(creds_file: Path | None, char_id: int) -> str:
    """Read character name from credentials file, with fallback."""
    if creds_file and creds_file.exists():
        try:
            with open(creds_file) as f:
                data = json.load(f)
            name = data.get("character_name")
            if name:
                return name
        except (OSError, json.JSONDecodeError):
            pass
    return f"Pilot {char_id}"


# =============================================================================
# Main Sync Logic
# =============================================================================


def run_sync(quick: bool = False, ships_only: bool = False, quiet: bool = False) -> dict[str, Any]:
    """Run the ESI sync process."""
    result: dict[str, Any] = {
        "sync_timestamp": get_utc_timestamp(),
        "status": "success",
        "synced": [],
        "errors": [],
        "volatile_snapshot": {},
    }

    # Authenticate and resolve pilot directory
    try:
        client, creds = get_authenticated_client()
    except CredentialsError as e:
        result["status"] = "error"
        result["errors"].append(str(e))
        return result

    pilot_dir = get_pilot_directory()
    if not pilot_dir:
        result["status"] = "error"
        result["errors"].append("Pilot directory not found")
        return result

    char_id = creds.character_id
    result["character_id"] = str(char_id)
    result["character_name"] = _get_character_name(creds.credentials_file, char_id)

    if not quiet:
        print(f"ARIA ESI Sync: Starting for {result['character_name']}...", file=sys.stderr)

    # Fetch current location (volatile snapshot)
    location_data = fetch_current_location(client, char_id)
    if "error" not in location_data:
        result["volatile_snapshot"]["current_location"] = location_data
        result["synced"].append("location")
        if not quiet:
            print(
                f"  Location: {location_data['solar_system_name']} "
                f"({location_data['security_status']})",
                file=sys.stderr,
            )
            print(
                f"  Ship: {location_data['ship_type_name']} "
                f"- {location_data.get('ship_name', 'unnamed')}",
                file=sys.stderr,
            )
    else:
        result["errors"].append("Failed to fetch location")

    # Fetch wallet (volatile)
    wallet = fetch_wallet(client, char_id)
    result["volatile_snapshot"]["wallet_balance"] = wallet

    # Fetch ship roster
    ships = fetch_ship_roster(client, char_id)
    if ships:
        result["ship_roster"] = ships
        result["ship_count"] = len(ships)
        result["synced"].append("ships")

        if update_ships_md(pilot_dir, ships):
            result["synced"].append("ships.md")
            if not quiet:
                print(f"  Ships: {len(ships)} ships synced to ships.md", file=sys.stderr)
        else:
            result["errors"].append("Failed to update ships.md")
    else:
        result["errors"].append("No ships found or fetch failed")

    # Stop here if quick/ships-only mode
    if quick or ships_only:
        write_sync_manifest(pilot_dir, result)
        return result

    # Fetch blueprints
    bp_data = fetch_blueprints(client, char_id)
    if "error" not in bp_data:
        result["blueprint_count"] = {
            "bpos": len(bp_data.get("bpos", [])),
            "bpcs": len(bp_data.get("bpcs", [])),
        }
        result["synced"].append("blueprints")

        if update_blueprints_md(pilot_dir, bp_data):
            result["synced"].append("blueprints.md")
            if not quiet:
                print(
                    f"  Blueprints: {result['blueprint_count']['bpos']} BPOs, "
                    f"{result['blueprint_count']['bpcs']} BPCs",
                    file=sys.stderr,
                )
        else:
            result["errors"].append("Failed to update blueprints.md")
    else:
        result["errors"].append("Failed to fetch blueprints")

    # Write manifest
    write_sync_manifest(pilot_dir, result)

    if not quiet:
        print(f"ARIA ESI Sync: Complete. Synced: {', '.join(result['synced'])}", file=sys.stderr)

    return result


def check_status() -> dict[str, Any]:
    """Check the current sync status."""
    pilot_dir = get_pilot_directory()
    if not pilot_dir:
        return {
            "status": "no_pilot",
            "message": "No active pilot configured or directory not found",
        }

    manifest_path = pilot_dir / ".esi-sync.json"
    if not manifest_path.exists():
        return {"status": "never_synced", "message": "No sync manifest found"}

    try:
        manifest = json.loads(manifest_path.read_text())

        # Calculate age
        sync_time = datetime.strptime(manifest["sync_timestamp"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=UTC
        )
        age = datetime.now(UTC) - sync_time
        age_minutes = int(age.total_seconds() / 60)

        manifest["age_minutes"] = age_minutes
        manifest["age_display"] = (
            f"{age_minutes}m ago"
            if age_minutes < 60
            else f"{age_minutes // 60}h {age_minutes % 60}m ago"
        )

        return manifest
    except (OSError, json.JSONDecodeError, KeyError) as e:
        return {"status": "error", "message": f"Failed to read manifest: {e}"}


# =============================================================================
# Command Handlers
# =============================================================================


def cmd_esi_sync(args: argparse.Namespace) -> dict[str, Any]:
    """Handle esi-sync command."""
    result = run_sync(quick=args.quick, ships_only=args.ships_only, quiet=args.quiet)

    if not args.json and not args.quiet:
        if result["errors"]:
            print(f"Errors: {', '.join(result['errors'])}", file=sys.stderr)

    if args.json:
        return result
    # For non-JSON mode, still return result for the CLI framework
    return result


def cmd_sync_status(args: argparse.Namespace) -> dict[str, Any]:
    """Handle sync-status command."""
    status = check_status()

    if not args.json:
        if status.get("status") == "success":
            print(f"Last sync: {status.get('age_display', 'unknown')}")
            print(f"Ships: {status.get('ship_count', '?')}")
            if "volatile_snapshot" in status:
                loc = status["volatile_snapshot"].get("current_location", {})
                print(f"Location (at sync): {loc.get('solar_system_name', '?')}")
                print(f"Ship (at sync): {loc.get('ship_type_name', '?')}")
        else:
            print(f"Status: {status.get('status', 'unknown')}")
            print(f"Message: {status.get('message', 'No details')}")

    return status


# =============================================================================
# Argument Parser Registration
# =============================================================================


def register_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Register esi-sync and sync-status command parsers."""
    # esi-sync command
    sync_parser = subparsers.add_parser(
        "esi-sync",
        help="Pre-fetch EVE data (ships, location, blueprints)",
    )
    sync_parser.add_argument(
        "--quick",
        "-q",
        action="store_true",
        help="Quick sync (ships + location only)",
    )
    sync_parser.add_argument(
        "--ships-only",
        "-s",
        action="store_true",
        help="Only sync ship roster",
    )
    sync_parser.add_argument(
        "--quiet",
        action="store_true",
        help="Minimal output",
    )
    sync_parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    sync_parser.set_defaults(func=cmd_esi_sync)

    # sync-status command
    status_parser = subparsers.add_parser(
        "sync-status",
        help="Check ESI sync status",
    )
    status_parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    status_parser.set_defaults(func=cmd_sync_status)
