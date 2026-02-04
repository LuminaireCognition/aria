#!/usr/bin/env python3
"""
ARIA Data Freshness Validator

Checks if cached profile data is fresh enough for eligibility decisions.
Use this before answering threshold-based questions ("Can I...", "Do I qualify...").

Usage:
    uv run python .claude/scripts/aria-data-freshness.py standings
    uv run python .claude/scripts/aria-data-freshness.py skills
    uv run python .claude/scripts/aria-data-freshness.py --all

Output:
    JSON with freshness status:
    {
        "data_type": "standings",
        "fresh": false,
        "synced_at": "2026-01-25T04:59:00Z",
        "stale_after": "2026-01-26T04:59:00Z",
        "age_hours": 120.5,
        "ttl_hours": 24,
        "recommendation": "Run: uv run aria-esi standings"
    }

Exit codes:
    0: Data is fresh
    1: Data is stale (should refresh)
    2: Error (file not found, parse error, etc.)
"""

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional


# Freshness rules: how long cached data remains trustworthy
FRESHNESS_RULES = {
    "standings": {
        "ttl_hours": 24,
        "sync_command": "uv run aria-esi standings",
        "description": "Corporation and faction standings",
        "marker_patterns": [
            r"ESI-SYNC:STANDINGS-EMPIRE:START",
            r"ESI-SYNC:STANDINGS-CORPS:START",
            r"ESI-SYNC:STANDINGS-PIRATES:START",
        ],
    },
    "skills": {
        "ttl_hours": 12,
        "sync_command": "uv run aria-esi skills sync",
        "description": "Trained skills and levels",
        "marker_patterns": [
            r"ESI-SYNC:SKILLS:START",
        ],
    },
    "wallet": {
        "ttl_hours": 0.083,  # 5 minutes
        "sync_command": "uv run aria-esi wallet",
        "description": "ISK balance",
        "marker_patterns": [],  # Wallet should never be cached
    },
    "location": {
        "ttl_hours": 0,  # Never trust cached
        "sync_command": "uv run aria-esi location",
        "description": "Current system and station",
        "marker_patterns": [],  # Location should never be cached
    },
}


def find_project_root() -> Path:
    """Find project root by walking up from script location."""
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / "userdata").is_dir() or (current / ".claude").is_dir():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return Path(__file__).resolve().parents[2]


def resolve_active_pilot(root: Path) -> tuple[Optional[str], Optional[str]]:
    """
    Resolve the active pilot directory.

    Returns:
        Tuple of (character_id, directory_name) or (None, None)
    """
    config_path = root / "userdata" / "config.json"
    if not config_path.exists():
        config_path = root / ".aria-config.json"

    active_pilot_id = None
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            active_pilot_id = config.get("active_pilot")
        except (json.JSONDecodeError, OSError):
            pass

    if not active_pilot_id:
        return None, None

    registry_path = root / "userdata" / "pilots" / "_registry.json"
    if not registry_path.exists():
        registry_path = root / "pilots" / "_registry.json"

    if registry_path.exists():
        try:
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            for pilot in registry.get("pilots", []):
                if str(pilot.get("character_id")) == str(active_pilot_id):
                    return active_pilot_id, pilot.get("directory")
        except (json.JSONDecodeError, OSError):
            pass

    return active_pilot_id, None


def parse_sync_marker(content: str, pattern: str) -> Optional[dict[str, Any]]:
    """
    Parse ESI-SYNC marker to extract metadata.

    Markers look like:
    <!-- ESI-SYNC:STANDINGS-CORPS:START ttl_hours=24 synced_at=2026-01-25T04:59:00Z stale_after=2026-01-26T04:59:00Z -->
    """
    # Find the marker line
    marker_match = re.search(rf"<!--\s*{pattern}\s+([^>]+)-->", content)
    if not marker_match:
        # Try legacy format without metadata
        legacy_match = re.search(rf"<!--\s*{pattern}\s*-->", content)
        if legacy_match:
            # Look for *Synced: timestamp* pattern
            synced_match = re.search(
                r"\*Synced:\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s*UTC\*",
                content[legacy_match.end() : legacy_match.end() + 500],
            )
            if synced_match:
                try:
                    synced_at = datetime.strptime(
                        synced_match.group(1), "%Y-%m-%d %H:%M"
                    ).replace(tzinfo=timezone.utc)
                    return {
                        "synced_at": synced_at.isoformat(),
                        "format": "legacy",
                    }
                except ValueError:
                    pass
        return None

    # Parse key=value pairs from marker
    metadata_str = marker_match.group(1)
    metadata: dict[str, Any] = {"format": "enhanced"}

    for match in re.finditer(r"(\w+)=([^\s]+)", metadata_str):
        key, value = match.groups()
        if key in ("ttl_hours",):
            try:
                metadata[key] = float(value)
            except ValueError:
                metadata[key] = value
        else:
            metadata[key] = value

    return metadata


def check_freshness(
    root: Path, data_type: str, pilot_dir: Optional[str]
) -> dict[str, Any]:
    """
    Check if cached data is fresh enough.

    Returns dict with freshness status and recommendations.
    """
    if data_type not in FRESHNESS_RULES:
        return {
            "error": f"Unknown data type: {data_type}",
            "valid_types": list(FRESHNESS_RULES.keys()),
        }

    rules = FRESHNESS_RULES[data_type]
    result: dict[str, Any] = {
        "data_type": data_type,
        "description": rules["description"],
        "ttl_hours": rules["ttl_hours"],
        "sync_command": rules["sync_command"],
    }

    # Data types that should never be cached
    if rules["ttl_hours"] == 0:
        result["fresh"] = False
        result["recommendation"] = f"Always query live: {rules['sync_command']}"
        result["reason"] = "This data type should never use cached values"
        return result

    # Need pilot directory to check profile
    if not pilot_dir:
        result["fresh"] = False
        result["recommendation"] = "No active pilot configured"
        result["reason"] = "Cannot check freshness without pilot profile"
        return result

    # Read profile
    profile_path = root / "userdata" / "pilots" / pilot_dir / "profile.md"
    if not profile_path.exists():
        result["fresh"] = False
        result["recommendation"] = f"Profile not found: {profile_path}"
        return result

    try:
        content = profile_path.read_text(encoding="utf-8")
    except OSError as e:
        result["fresh"] = False
        result["recommendation"] = f"Cannot read profile: {e}"
        return result

    # Find sync markers
    synced_at: Optional[datetime] = None
    stale_after: Optional[datetime] = None

    for pattern in rules["marker_patterns"]:
        metadata = parse_sync_marker(content, pattern)
        if metadata:
            # Parse synced_at timestamp
            if "synced_at" in metadata:
                try:
                    synced_at = datetime.fromisoformat(
                        metadata["synced_at"].replace("Z", "+00:00")
                    )
                except ValueError:
                    pass

            # Parse stale_after if present
            if "stale_after" in metadata:
                try:
                    stale_after = datetime.fromisoformat(
                        metadata["stale_after"].replace("Z", "+00:00")
                    )
                except ValueError:
                    pass

            # Use first found marker
            if synced_at:
                break

    if not synced_at:
        result["fresh"] = False
        result["synced_at"] = None
        result["recommendation"] = f"No sync timestamp found. Run: {rules['sync_command']}"
        result["reason"] = "Missing sync metadata in profile"
        return result

    # Calculate age
    now = datetime.now(timezone.utc)
    age = now - synced_at
    age_hours = age.total_seconds() / 3600

    result["synced_at"] = synced_at.isoformat()
    result["age_hours"] = round(age_hours, 2)

    # Determine freshness
    if stale_after:
        result["stale_after"] = stale_after.isoformat()
        is_fresh = now < stale_after
    else:
        # Calculate based on TTL
        stale_after = synced_at + timedelta(hours=rules["ttl_hours"])
        result["stale_after"] = stale_after.isoformat()
        is_fresh = age_hours < rules["ttl_hours"]

    result["fresh"] = is_fresh

    if is_fresh:
        hours_remaining = (stale_after - now).total_seconds() / 3600
        result["hours_until_stale"] = round(hours_remaining, 2)
        result["recommendation"] = "Data is fresh - safe to use cached values"
    else:
        hours_overdue = age_hours - rules["ttl_hours"]
        result["hours_overdue"] = round(hours_overdue, 2)
        result["recommendation"] = f"Data is stale. Run: {rules['sync_command']}"
        result["reason"] = f"Data is {round(hours_overdue, 1)} hours past TTL"

    return result


def check_all_freshness(root: Path, pilot_dir: Optional[str]) -> dict[str, Any]:
    """Check freshness of all data types."""
    results: dict[str, Any] = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "pilot_directory": pilot_dir,
        "data_types": {},
        "summary": {
            "total": 0,
            "fresh": 0,
            "stale": 0,
        },
    }

    for data_type in FRESHNESS_RULES:
        check = check_freshness(root, data_type, pilot_dir)
        results["data_types"][data_type] = check
        results["summary"]["total"] += 1

        if check.get("fresh", False):
            results["summary"]["fresh"] += 1
        else:
            results["summary"]["stale"] += 1

    results["all_fresh"] = results["summary"]["stale"] == 0
    return results


def main() -> int:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: aria-data-freshness.py <data-type>", file=sys.stderr)
        print("       aria-data-freshness.py --all", file=sys.stderr)
        print(f"\nData types: {', '.join(FRESHNESS_RULES.keys())}", file=sys.stderr)
        return 2

    root = find_project_root()
    _, pilot_dir = resolve_active_pilot(root)

    if sys.argv[1] == "--all":
        result = check_all_freshness(root, pilot_dir)
        print(json.dumps(result, indent=2))
        return 0 if result["all_fresh"] else 1

    data_type = sys.argv[1].lower()
    result = check_freshness(root, data_type, pilot_dir)
    print(json.dumps(result, indent=2))

    if "error" in result:
        return 2
    return 0 if result.get("fresh", False) else 1


if __name__ == "__main__":
    sys.exit(main())
