#!/usr/bin/env python3
"""
ARIA ESI Sync Engine
═══════════════════════════════════════════════════════════════════
Pre-fetches EVE Online data at session start to populate local files.
Runs in background during boot to minimize startup latency.

Usage:
    python aria-esi-sync.py                    # Full sync
    python aria-esi-sync.py --ships-only       # Only sync ship roster
    python aria-esi-sync.py --quick            # Quick sync (ships + location)
    python aria-esi-sync.py --status           # Check sync status

Synced Data:
    - Ship roster (from assets API) → ships.md
    - Current ship/location (volatile snapshot) → .esi-sync.json
    - Blueprints → industry/blueprints.md
    - Skills summary → .esi-sync.json

No external dependencies - uses only Python standard library.
═══════════════════════════════════════════════════════════════════
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════

ESI_BASE = "https://esi.evetech.net/latest"
TOKEN_ENDPOINT = "https://login.eveonline.com/v2/oauth/token"
REQUEST_TIMEOUT = 30

# Ship group IDs (for filtering assets)
SHIP_GROUP_IDS = {
    25,
    26,
    27,
    28,
    29,
    30,
    31,
    237,
    324,
    358,
    380,
    381,
    419,
    420,
    463,
    485,
    513,
    540,
    541,
    543,
    547,
    659,
    830,
    831,
    832,
    833,
    834,
    893,
    894,
    898,
    900,
    902,
    906,
    941,
    963,
    1022,
    1201,
    1202,
    1283,
    1305,
    1527,
    1534,
    1538,
    1972,
    2001,  # 2001 = Mining Frigate (Venture)
}


# ═══════════════════════════════════════════════════════════════════
# Path Resolution
# ═══════════════════════════════════════════════════════════════════


def get_project_root() -> Path:
    """Find the ARIA project root directory."""
    env_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_dir:
        return Path(env_dir)

    script_dir = Path(__file__).parent
    if script_dir.name == "scripts":
        project_root = script_dir.parent.parent
        if (project_root / "CLAUDE.md").exists():
            return project_root

    cwd = Path.cwd()
    if (cwd / "CLAUDE.md").exists():
        return cwd

    return Path(__file__).parent.parent.parent


def get_active_pilot_id(project_root: Path) -> str:
    """Get the active pilot ID from environment or config."""
    pilot_id = os.environ.get("ARIA_PILOT")
    if pilot_id:
        return pilot_id

    config_path = project_root / ".aria-config.json"
    if config_path.exists():
        try:
            with open(config_path) as f:
                config = json.load(f)
            pilot_id = config.get("active_pilot")
            if pilot_id:
                return str(pilot_id)
        except (OSError, json.JSONDecodeError):
            pass

    creds_dir = project_root / "credentials"
    if creds_dir.exists():
        cred_files = list(creds_dir.glob("*.json"))
        if cred_files:
            return cred_files[0].stem

    return ""


def find_pilot_directory(project_root: Path, pilot_id: str) -> Path:
    """Find the pilot's directory."""
    pilots_dir = project_root / "pilots"
    if not pilots_dir.exists():
        return None

    # Look for directory matching pattern: {pilot_id}_*
    matches = list(pilots_dir.glob(f"{pilot_id}_*"))
    if matches:
        return matches[0]

    return None


# ═══════════════════════════════════════════════════════════════════
# Credentials & Token Management
# ═══════════════════════════════════════════════════════════════════


def load_credentials(project_root: Path, pilot_id: str) -> dict:
    """Load credentials for the specified pilot."""
    creds_path = project_root / "credentials" / f"{pilot_id}.json"
    if not creds_path.exists():
        return None

    try:
        with open(creds_path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def is_token_expired(creds: dict, buffer_minutes: int = 5) -> bool:
    """Check if token is expired or expiring soon."""
    expiry_str = creds.get("token_expiry", "")
    if not expiry_str:
        return True

    try:
        expiry = datetime.strptime(expiry_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return True

    now = datetime.now(timezone.utc)
    buffer = timedelta(minutes=buffer_minutes)
    return (expiry - now) < buffer


def refresh_token(creds: dict, creds_path: Path) -> bool:
    """Refresh the OAuth token if expired."""
    if not is_token_expired(creds):
        return True

    data = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "refresh_token": creds["refresh_token"],
            "client_id": creds["client_id"],
        }
    ).encode("utf-8")

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "User-Agent": "ARIA-ESI-Sync/1.0",
    }

    request = urllib.request.Request(TOKEN_ENDPOINT, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            token_data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError):
        return False

    # Update credentials
    now = datetime.now(timezone.utc)
    expires_in = token_data.get("expires_in", 1199)
    expiry = now + timedelta(seconds=expires_in)

    creds["access_token"] = token_data["access_token"]
    creds["token_expiry"] = expiry.strftime("%Y-%m-%dT%H:%M:%SZ")
    if "refresh_token" in token_data:
        creds["refresh_token"] = token_data["refresh_token"]
    creds["_last_refresh"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Save updated credentials
    try:
        with open(creds_path, "w") as f:
            json.dump(creds, f, indent=2)
        return True
    except OSError:
        return False


# ═══════════════════════════════════════════════════════════════════
# ESI API Calls
# ═══════════════════════════════════════════════════════════════════


def esi_get(endpoint: str, token: str = None) -> dict:
    """Make an ESI API request."""
    url = f"{ESI_BASE}{endpoint}?datasource=tranquility"
    headers = {"Accept": "application/json", "User-Agent": "ARIA-ESI-Sync/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
        return {"error": str(e)}


def esi_post(endpoint: str, data: list, token: str) -> dict:
    """Make an ESI POST request (for asset names)."""
    url = f"{ESI_BASE}{endpoint}?datasource=tranquility"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "ARIA-ESI-Sync/1.0",
        "Authorization": f"Bearer {token}",
    }

    request = urllib.request.Request(
        url, data=json.dumps(data).encode("utf-8"), headers=headers, method="POST"
    )

    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════════
# Data Fetching
# ═══════════════════════════════════════════════════════════════════


def fetch_ship_roster(char_id: str, token: str) -> list:
    """Fetch all ships from character assets."""
    assets = esi_get(f"/characters/{char_id}/assets/", token)
    if "error" in assets:
        return []

    # Collect type IDs for ships
    ship_assets = []
    type_ids = set()

    for asset in assets:
        # Only assembled ships in hangars
        if not asset.get("is_singleton", False):
            continue
        if asset.get("location_flag") != "Hangar":
            continue

        type_id = asset["type_id"]
        type_ids.add(type_id)
        ship_assets.append(asset)

    # Resolve type info to filter to ships and get names
    type_info = {}
    for tid in type_ids:
        info = esi_get(f"/universe/types/{tid}/")
        if info and "name" in info:
            type_info[tid] = {"name": info["name"], "group_id": info.get("group_id", 0)}

    # Filter to only ships and build roster
    ships = []
    ship_item_ids = []

    for asset in ship_assets:
        tid = asset["type_id"]
        tinfo = type_info.get(tid, {})

        if tinfo.get("group_id", 0) not in SHIP_GROUP_IDS:
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
        names_response = esi_post(f"/characters/{char_id}/assets/names/", ship_item_ids, token)
        if isinstance(names_response, list):
            name_lookup = {n["item_id"]: n["name"] for n in names_response}
            for ship in ships:
                custom_name = name_lookup.get(ship["item_id"], "")
                ship["custom_name"] = custom_name if custom_name != ship["type_name"] else ""

    # Resolve location names
    location_ids = set(s["location_id"] for s in ships)
    location_names = {}
    for lid in location_ids:
        station_info = esi_get(f"/universe/stations/{lid}/")
        if station_info and "name" in station_info:
            location_names[lid] = station_info["name"]
        else:
            location_names[lid] = f"Structure-{lid}"

    for ship in ships:
        ship["location_name"] = location_names.get(ship["location_id"], "Unknown")

    return ships


def fetch_current_location(char_id: str, token: str) -> dict:
    """Fetch current location and ship (volatile)."""
    location = esi_get(f"/characters/{char_id}/location/", token)
    ship = esi_get(f"/characters/{char_id}/ship/", token)

    if "error" in location or "error" in ship:
        return {"error": "Failed to fetch location/ship"}

    # Resolve names
    system_id = location.get("solar_system_id", 0)
    ship_type_id = ship.get("ship_type_id", 0)

    system_info = esi_get(f"/universe/systems/{system_id}/")
    ship_type_info = esi_get(f"/universe/types/{ship_type_id}/")

    result = {
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
        station_info = esi_get(f"/universe/stations/{station_id}/")
        result["station_id"] = station_id
        result["station_name"] = station_info.get("name", "Unknown") if station_info else "Unknown"
        result["docked"] = True
    else:
        result["docked"] = False

    return result


def fetch_blueprints(char_id: str, token: str) -> dict:
    """Fetch character blueprints."""
    blueprints = esi_get(f"/characters/{char_id}/blueprints/", token)
    if "error" in blueprints or not isinstance(blueprints, list):
        return {"error": "Failed to fetch blueprints", "bpos": [], "bpcs": []}

    # Resolve type names
    type_ids = set(bp["type_id"] for bp in blueprints)
    type_names = {}
    for tid in type_ids:
        info = esi_get(f"/universe/types/{tid}/")
        if info and "name" in info:
            type_names[tid] = info["name"]

    bpos = []
    bpcs = []

    for bp in blueprints:
        tid = bp["type_id"]
        entry = {
            "type_id": tid,
            "name": type_names.get(tid, f"Unknown-{tid}"),
            "material_efficiency": bp.get("material_efficiency", 0),
            "time_efficiency": bp.get("time_efficiency", 0),
        }

        if bp.get("quantity") == -1:
            # BPO (infinite runs)
            bpos.append(entry)
        else:
            # BPC
            entry["runs"] = bp.get("runs", 0)
            bpcs.append(entry)

    bpos.sort(key=lambda x: x["name"])
    bpcs.sort(key=lambda x: x["name"])

    return {"bpos": bpos, "bpcs": bpcs}


def fetch_wallet(char_id: str, token: str) -> float:
    """Fetch wallet balance."""
    result = esi_get(f"/characters/{char_id}/wallet/", token)
    if isinstance(result, (int, float)):
        return float(result)
    return 0.0


# ═══════════════════════════════════════════════════════════════════
# File Updates
# ═══════════════════════════════════════════════════════════════════


def update_ships_md(pilot_dir: Path, ships: list) -> bool:
    """Update ships.md with synced roster while preserving fitting details."""
    ships_path = pilot_dir / "ships.md"

    # Read existing content
    existing_content = ""
    if ships_path.exists():
        try:
            with open(ships_path) as f:
                existing_content = f.read()
        except OSError:
            pass

    # Build new roster section
    sync_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

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
        # Truncate long location names
        if len(location) > 25:
            location = location[:22] + "..."
        roster_lines.append(f"| {name} | {hull} | {location} |")

    roster_lines.extend(["", f"*{len(ships)} ships in hangars*", "<!-- ESI-SYNC:ROSTER:END -->"])

    new_roster = "\n".join(roster_lines)

    # Check if file has sync markers
    if "<!-- ESI-SYNC:ROSTER:START -->" in existing_content:
        # Replace existing roster section
        pattern = r"<!-- ESI-SYNC:ROSTER:START -->.*?<!-- ESI-SYNC:ROSTER:END -->"
        new_content = re.sub(pattern, new_roster, existing_content, flags=re.DOTALL)
    else:
        # Insert roster section after header or at start
        header_match = re.search(r"^# Ship Status\n+", existing_content)
        if header_match:
            insert_pos = header_match.end()
            new_content = (
                existing_content[:insert_pos] + new_roster + "\n\n" + existing_content[insert_pos:]
            )
        else:
            # Prepend with header
            new_content = "# Ship Status\n\n" + new_roster + "\n\n" + existing_content

    # Write updated content
    try:
        with open(ships_path, "w") as f:
            f.write(new_content)
        return True
    except OSError:
        return False


def update_blueprints_md(pilot_dir: Path, bp_data: dict) -> bool:
    """Update blueprints.md with synced data."""
    bp_path = pilot_dir / "industry" / "blueprints.md"

    # Ensure industry directory exists
    (pilot_dir / "industry").mkdir(exist_ok=True)

    sync_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

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
            f"| {bpc['name']} | {bpc.get('runs', '?')} | {bpc['material_efficiency']}% | {bpc['time_efficiency']}% |"
        )

    if not bp_data.get("bpcs"):
        lines.append("| *No BPCs owned* | - | - | - |")

    lines.extend(
        ["", f"*{len(bp_data.get('bpcs', []))} BPCs total*", "<!-- ESI-SYNC:BLUEPRINTS:END -->"]
    )

    try:
        with open(bp_path, "w") as f:
            f.write("\n".join(lines))
        return True
    except OSError:
        return False


def write_sync_manifest(pilot_dir: Path, manifest_data: dict) -> bool:
    """Write the sync manifest."""
    manifest_path = pilot_dir / ".esi-sync.json"

    try:
        with open(manifest_path, "w") as f:
            json.dump(manifest_data, f, indent=2)
        return True
    except OSError:
        return False


# ═══════════════════════════════════════════════════════════════════
# Main Sync Logic
# ═══════════════════════════════════════════════════════════════════


def run_sync(quick: bool = False, ships_only: bool = False, quiet: bool = False) -> dict:
    """Run the ESI sync process."""
    result = {
        "sync_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "success",
        "synced": [],
        "errors": [],
        "volatile_snapshot": {},
    }

    # Resolve paths
    project_root = get_project_root()
    pilot_id = get_active_pilot_id(project_root)

    if not pilot_id:
        result["status"] = "error"
        result["errors"].append("No active pilot configured")
        return result

    pilot_dir = find_pilot_directory(project_root, pilot_id)
    if not pilot_dir:
        result["status"] = "error"
        result["errors"].append(f"Pilot directory not found for {pilot_id}")
        return result

    # Load and refresh credentials
    creds = load_credentials(project_root, pilot_id)
    if not creds:
        result["status"] = "error"
        result["errors"].append("Credentials not found")
        return result

    creds_path = project_root / "credentials" / f"{pilot_id}.json"
    if not refresh_token(creds, creds_path):
        result["status"] = "error"
        result["errors"].append("Token refresh failed")
        return result

    token = creds["access_token"]
    char_id = str(creds["character_id"])
    result["character_id"] = char_id
    result["character_name"] = creds.get("character_name", "Unknown")

    if not quiet:
        print(f"ARIA ESI Sync: Starting for {result['character_name']}...", file=sys.stderr)

    # Fetch current location (volatile snapshot)
    location_data = fetch_current_location(char_id, token)
    if "error" not in location_data:
        result["volatile_snapshot"]["current_location"] = location_data
        result["synced"].append("location")
        if not quiet:
            print(
                f"  Location: {location_data['solar_system_name']} ({location_data['security_status']})",
                file=sys.stderr,
            )
            print(
                f"  Ship: {location_data['ship_type_name']} - {location_data.get('ship_name', 'unnamed')}",
                file=sys.stderr,
            )
    else:
        result["errors"].append("Failed to fetch location")

    # Fetch wallet (volatile)
    wallet = fetch_wallet(char_id, token)
    result["volatile_snapshot"]["wallet_balance"] = wallet

    # Fetch ship roster
    ships = fetch_ship_roster(char_id, token)
    if ships:
        result["ship_roster"] = ships
        result["ship_count"] = len(ships)
        result["synced"].append("ships")

        # Update ships.md
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
    bp_data = fetch_blueprints(char_id, token)
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
                    f"  Blueprints: {result['blueprint_count']['bpos']} BPOs, {result['blueprint_count']['bpcs']} BPCs",
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


def check_status() -> dict:
    """Check the current sync status."""
    project_root = get_project_root()
    pilot_id = get_active_pilot_id(project_root)

    if not pilot_id:
        return {"status": "no_pilot", "message": "No active pilot configured"}

    pilot_dir = find_pilot_directory(project_root, pilot_id)
    if not pilot_dir:
        return {"status": "no_pilot_dir", "message": f"Pilot directory not found: {pilot_id}"}

    manifest_path = pilot_dir / ".esi-sync.json"
    if not manifest_path.exists():
        return {"status": "never_synced", "message": "No sync manifest found"}

    try:
        with open(manifest_path) as f:
            manifest = json.load(f)

        # Calculate age
        sync_time = datetime.strptime(manifest["sync_timestamp"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        age = datetime.now(timezone.utc) - sync_time
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


# ═══════════════════════════════════════════════════════════════════
# CLI Interface
# ═══════════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(
        description="ARIA ESI Sync Engine - Pre-fetch EVE data for sessions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--quick", "-q", action="store_true", help="Quick sync (ships + location only)"
    )
    parser.add_argument("--ships-only", "-s", action="store_true", help="Only sync ship roster")
    parser.add_argument("--status", action="store_true", help="Check sync status")
    parser.add_argument("--quiet", action="store_true", help="Minimal output")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.status:
        status = check_status()
        if args.json:
            print(json.dumps(status, indent=2))
        else:
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
        return

    result = run_sync(quick=args.quick, ships_only=args.ships_only, quiet=args.quiet)

    if args.json:
        print(json.dumps(result, indent=2))
    elif not args.quiet:
        if result["errors"]:
            print(f"Errors: {', '.join(result['errors'])}", file=sys.stderr)


if __name__ == "__main__":
    main()
