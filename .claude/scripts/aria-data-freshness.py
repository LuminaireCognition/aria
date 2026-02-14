#!/usr/bin/env python3
"""
ARIA Data Freshness Validator

Checks if cached profile data is fresh enough for eligibility decisions.
Use this before answering threshold-based questions ("Can I...", "Do I qualify...").

Delegates to the core freshness library for standings/skills checks.
Retains wallet/location rules which are not sync-gated (never cached).

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
        "recommendation": "Run: uv run aria-esi ensure-fresh standings"
    }

Exit codes:
    0: Data is fresh
    1: Data is stale (should refresh)
    2: Error (file not found, parse error, etc.)
"""

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

# Import core freshness library
from aria_esi.core.freshness import (
    SECTION_REGISTRY,
    parse_sync_marker,  # noqa: F401 — re-exported for backward compatibility
)
from aria_esi.core.freshness import (
    check_freshness as lib_check_freshness,
)

# Sync commands for recommendations (library handles sync itself, these are for display)
SYNC_COMMANDS = {
    "standings": "uv run aria-esi ensure-fresh standings",
    "skills": "uv run aria-esi ensure-fresh skills",
    "wallet": "uv run aria-esi wallet",
    "location": "uv run aria-esi location",
}

# Non-syncable data types (not in the library registry)
NON_SYNCABLE_RULES = {
    "wallet": {
        "ttl_hours": 0.083,  # 5 minutes
        "sync_command": "uv run aria-esi wallet",
        "description": "ISK balance",
    },
    "location": {
        "ttl_hours": 0,  # Never trust cached
        "sync_command": "uv run aria-esi location",
        "description": "Current system and station",
    },
}

# All known data types (library + non-syncable)
ALL_DATA_TYPES = list(SECTION_REGISTRY.keys()) + list(NON_SYNCABLE_RULES.keys())


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


def resolve_active_pilot(root: Path) -> tuple[Optional[str], Optional[Path]]:
    """
    Resolve the active pilot directory.

    Returns:
        Tuple of (character_id, pilot_dir_path) or (None, None)
    """
    config_path = root / "userdata" / "config.json"

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

    if registry_path.exists():
        try:
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            for pilot in registry.get("pilots", []):
                if str(pilot.get("character_id")) == str(active_pilot_id):
                    directory = pilot.get("directory")
                    if directory:
                        pilot_dir = root / "userdata" / "pilots" / directory
                        return active_pilot_id, pilot_dir
        except (json.JSONDecodeError, OSError):
            pass

    return active_pilot_id, None


def check_freshness(root: Path, data_type: str, pilot_dir: Optional[Path]) -> dict[str, Any]:
    """
    Check if cached data is fresh enough.

    Delegates to the core library for registry-known sections (standings, skills).
    Handles wallet/location directly (never-cache types).

    Returns dict with freshness status and recommendations.
    """
    if data_type not in ALL_DATA_TYPES:
        return {
            "error": f"Unknown data type: {data_type}",
            "valid_types": ALL_DATA_TYPES,
        }

    # Non-syncable types (wallet, location) — never trust cached
    if data_type in NON_SYNCABLE_RULES:
        rules = NON_SYNCABLE_RULES[data_type]
        result: dict[str, Any] = {
            "data_type": data_type,
            "description": rules["description"],
            "ttl_hours": rules["ttl_hours"],
            "sync_command": rules["sync_command"],
            "fresh": False,
        }
        if rules["ttl_hours"] == 0:
            result["recommendation"] = f"Always query live: {rules['sync_command']}"
            result["reason"] = "This data type should never use cached values"
        else:
            result["recommendation"] = f"Short-lived cache. Run: {rules['sync_command']}"
            result["reason"] = f"TTL is {rules['ttl_hours']} hours — always query live"
        return result

    # Library-backed sections (standings, skills)
    sync_result = lib_check_freshness(data_type, pilot_dir)
    sync_command = SYNC_COMMANDS.get(data_type, f"uv run aria-esi ensure-fresh {data_type}")

    result = {
        "data_type": data_type,
        "ttl_hours": sync_result.ttl_hours,
        "sync_command": sync_command,
        "fresh": sync_result.fresh,
        "synced_at": sync_result.synced_at,
        "age_hours": sync_result.age_hours,
        "source": sync_result.source,
    }

    if sync_result.error:
        result["error"] = sync_result.error

    if sync_result.fresh:
        # Calculate stale_after and hours_until_stale
        if sync_result.synced_at:
            try:
                synced_at = datetime.fromisoformat(sync_result.synced_at.replace("Z", "+00:00"))
                stale_after = synced_at + timedelta(hours=sync_result.ttl_hours)
                now = datetime.now(UTC)
                result["stale_after"] = stale_after.isoformat()
                result["hours_until_stale"] = round((stale_after - now).total_seconds() / 3600, 2)
            except (ValueError, TypeError):
                pass
        result["recommendation"] = "Data is fresh - safe to use cached values"
    elif sync_result.source == "missing":
        result["recommendation"] = f"No sync data found. Run: {sync_command}"
        result["reason"] = "Missing sync metadata"
    else:
        hours_overdue = (
            round(sync_result.age_hours - sync_result.ttl_hours, 1)
            if sync_result.age_hours is not None
            else None
        )
        if hours_overdue is not None:
            result["hours_overdue"] = hours_overdue
            result["reason"] = f"Data is {hours_overdue} hours past TTL"
        result["recommendation"] = f"Data is stale. Run: {sync_command}"

    return result


def check_all_freshness(root: Path, pilot_dir: Optional[Path]) -> dict[str, Any]:
    """Check freshness of all data types."""
    results: dict[str, Any] = {
        "checked_at": datetime.now(UTC).isoformat(),
        "pilot_directory": str(pilot_dir) if pilot_dir else None,
        "data_types": {},
        "summary": {
            "total": 0,
            "fresh": 0,
            "stale": 0,
        },
    }

    for data_type in ALL_DATA_TYPES:
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
        print(f"\nData types: {', '.join(ALL_DATA_TYPES)}", file=sys.stderr)
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

    if "error" in result and "valid_types" in result:
        return 2
    return 0 if result.get("fresh", False) else 1


if __name__ == "__main__":
    sys.exit(main())
