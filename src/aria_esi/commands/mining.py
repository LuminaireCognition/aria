"""
ARIA ESI Mining Commands

Mining ledger and extraction history.
All commands require authentication.
"""

import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from ..core import (
    CredentialsError,
    ESIClient,
    ESIError,
    get_authenticated_client,
    get_utc_timestamp,
)

# =============================================================================
# Mining Ledger Command
# =============================================================================


def cmd_mining(args: argparse.Namespace) -> dict:
    """
    Fetch mining ledger entries.

    Shows ore extraction history over the past 30 days (ESI limit).
    """
    query_ts = get_utc_timestamp()
    days_limit = getattr(args, "days", 30)
    system_filter = getattr(args, "system", None)
    ore_filter = getattr(args, "ore", None)

    try:
        client, creds = get_authenticated_client()
    except CredentialsError as e:
        return e.to_dict() | {"query_timestamp": query_ts}

    char_id = creds.character_id

    # Check scope
    if not creds.has_scope("esi-industry.read_character_mining.v1"):
        return {
            "error": "scope_not_authorized",
            "message": "Missing required scope: esi-industry.read_character_mining.v1",
            "action": "Re-run OAuth setup to authorize mining ledger access",
            "command": "python3 .claude/scripts/aria-oauth-setup.py",
            "query_timestamp": query_ts,
        }

    public_client = ESIClient()

    # Fetch mining ledger (paginated)
    all_entries: list = []
    page = 1
    while True:
        try:
            entries = client.get(f"/characters/{char_id}/mining/", auth=True, params={"page": page})
            if not isinstance(entries, list) or not entries:
                break
            all_entries.extend(entries)
            page += 1
            # Safety limit
            if page > 20:
                break
        except ESIError as e:
            if page == 1:
                return {
                    "error": "esi_error",
                    "message": f"Could not fetch mining ledger: {e.message}",
                    "hint": "Ensure esi-industry.read_character_mining.v1 scope is authorized",
                    "query_timestamp": query_ts,
                }
            break

    # Empty check
    if not all_entries:
        return {
            "query_timestamp": query_ts,
            "volatility": "semi_stable",
            "character_id": char_id,
            "summary": {
                "total_entries": 0,
                "total_quantity": 0,
                "unique_ores": 0,
                "unique_systems": 0,
                "days_covered": 0,
            },
            "entries": [],
            "message": "No mining activity in the last 30 days",
        }

    # Filter by date range
    cutoff_date = None
    if days_limit and days_limit < 30:
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days_limit)).date()

    # Collect IDs for resolution
    type_ids = set()
    system_ids = set()
    for entry in all_entries:
        type_ids.add(entry.get("type_id", 0))
        system_ids.add(entry.get("solar_system_id", 0))

    # Resolve type names (ore names)
    type_names = {}
    for tid in type_ids:
        if tid:
            info = public_client.get_safe(f"/universe/types/{tid}/")
            if info and "name" in info:
                type_names[tid] = info["name"]
            else:
                type_names[tid] = f"Unknown-{tid}"

    # Resolve system names and security
    system_info = {}
    for sid in system_ids:
        if sid:
            info = public_client.get_dict_safe(f"/universe/systems/{sid}/")
            if info:
                system_info[sid] = {
                    "name": info.get("name", f"System-{sid}"),
                    "security": round(info.get("security_status", 0.0), 1),
                }
            else:
                system_info[sid] = {"name": f"System-{sid}", "security": 0.0}

    # Process entries
    processed_entries = []
    total_quantity = 0
    unique_ores = set()
    unique_systems = set()
    dates_seen = set()

    for entry in all_entries:
        entry_date = entry.get("date", "")
        type_id = entry.get("type_id", 0)
        system_id = entry.get("solar_system_id", 0)
        quantity = entry.get("quantity", 0)

        # Apply date filter
        if cutoff_date and entry_date:
            try:
                entry_date_obj = datetime.strptime(entry_date, "%Y-%m-%d").date()
                if entry_date_obj < cutoff_date:
                    continue
            except ValueError:
                pass

        type_name = type_names.get(type_id, f"Unknown-{type_id}")
        sys_data = system_info.get(system_id, {"name": "Unknown", "security": 0.0})

        # Apply system filter
        if system_filter:
            if system_filter.lower() not in sys_data["name"].lower():
                continue

        # Apply ore filter
        if ore_filter:
            if ore_filter.lower() not in type_name.lower():
                continue

        processed_entry = {
            "date": entry_date,
            "type_id": type_id,
            "type_name": type_name,
            "quantity": quantity,
            "solar_system_id": system_id,
            "solar_system_name": sys_data["name"],
            "security": sys_data["security"],
        }

        processed_entries.append(processed_entry)
        total_quantity += quantity
        unique_ores.add(type_id)
        unique_systems.add(system_id)
        dates_seen.add(entry_date)

    # Sort by date descending, then by ore name
    processed_entries.sort(key=lambda e: (e["date"], e["type_name"]), reverse=True)

    return {
        "query_timestamp": query_ts,
        "volatility": "semi_stable",
        "character_id": char_id,
        "summary": {
            "total_entries": len(processed_entries),
            "total_quantity": total_quantity,
            "unique_ores": len(unique_ores),
            "unique_systems": len(unique_systems),
            "days_covered": len(dates_seen),
        },
        "entries": processed_entries,
        "filters": {"days": days_limit, "system": system_filter, "ore": ore_filter},
    }


# =============================================================================
# Mining Summary Command
# =============================================================================


def cmd_mining_summary(args: argparse.Namespace) -> dict:
    """
    Fetch aggregated mining summary.

    Shows totals by ore type and system.
    """
    query_ts = get_utc_timestamp()
    days_limit = getattr(args, "days", 30)

    try:
        client, creds = get_authenticated_client()
    except CredentialsError as e:
        return e.to_dict() | {"query_timestamp": query_ts}

    char_id = creds.character_id

    # Check scope
    if not creds.has_scope("esi-industry.read_character_mining.v1"):
        return {
            "error": "scope_not_authorized",
            "message": "Missing required scope: esi-industry.read_character_mining.v1",
            "action": "Re-run OAuth setup to authorize mining ledger access",
            "command": "python3 .claude/scripts/aria-oauth-setup.py",
            "query_timestamp": query_ts,
        }

    public_client = ESIClient()

    # Fetch mining ledger (paginated)
    all_entries: list = []
    page = 1
    while True:
        try:
            entries = client.get(f"/characters/{char_id}/mining/", auth=True, params={"page": page})
            if not isinstance(entries, list) or not entries:
                break
            all_entries.extend(entries)
            page += 1
            if page > 20:
                break
        except ESIError as e:
            if page == 1:
                return {
                    "error": "esi_error",
                    "message": f"Could not fetch mining ledger: {e.message}",
                    "query_timestamp": query_ts,
                }
            break

    # Empty check
    if not all_entries:
        return {
            "query_timestamp": query_ts,
            "volatility": "semi_stable",
            "character_id": char_id,
            "summary": {"total_quantity": 0, "unique_ores": 0, "days_covered": 0},
            "by_ore": [],
            "by_system": [],
            "message": "No mining activity in the last 30 days",
        }

    # Filter by date range
    cutoff_date = None
    if days_limit and days_limit < 30:
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days_limit)).date()

    # Aggregate data
    ore_totals = defaultdict(int)
    system_totals = defaultdict(int)
    type_ids = set()
    system_ids = set()
    dates_seen = set()
    total_quantity = 0

    for entry in all_entries:
        entry_date = entry.get("date", "")
        type_id = entry.get("type_id", 0)
        system_id = entry.get("solar_system_id", 0)
        quantity = entry.get("quantity", 0)

        # Apply date filter
        if cutoff_date and entry_date:
            try:
                entry_date_obj = datetime.strptime(entry_date, "%Y-%m-%d").date()
                if entry_date_obj < cutoff_date:
                    continue
            except ValueError:
                pass

        ore_totals[type_id] += quantity
        system_totals[system_id] += quantity
        type_ids.add(type_id)
        system_ids.add(system_id)
        dates_seen.add(entry_date)
        total_quantity += quantity

    # Resolve names
    type_names = {}
    for tid in type_ids:
        if tid:
            info = public_client.get_safe(f"/universe/types/{tid}/")
            if info and "name" in info:
                type_names[tid] = info["name"]
            else:
                type_names[tid] = f"Unknown-{tid}"

    system_names = {}
    for sid in system_ids:
        if sid:
            info = public_client.get_safe(f"/universe/systems/{sid}/")
            if info and "name" in info:
                system_names[sid] = info["name"]
            else:
                system_names[sid] = f"System-{sid}"

    # Build by_ore list
    by_ore = []
    for tid, qty in sorted(ore_totals.items(), key=lambda x: x[1], reverse=True):
        by_ore.append(
            {
                "type_id": tid,
                "type_name": type_names.get(tid, f"Unknown-{tid}"),
                "total_quantity": qty,
            }
        )

    # Build by_system list
    by_system = []
    for sid, qty in sorted(system_totals.items(), key=lambda x: x[1], reverse=True):
        by_system.append(
            {
                "solar_system_id": sid,
                "solar_system_name": system_names.get(sid, f"System-{sid}"),
                "total_quantity": qty,
            }
        )

    return {
        "query_timestamp": query_ts,
        "volatility": "semi_stable",
        "character_id": char_id,
        "summary": {
            "total_quantity": total_quantity,
            "unique_ores": len(type_ids),
            "days_covered": len(dates_seen),
        },
        "by_ore": by_ore,
        "by_system": by_system,
        "filters": {"days": days_limit},
    }


# =============================================================================
# Argument Parser Registration
# =============================================================================


def register_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Register mining command parsers."""

    # Mining ledger command
    mining_parser = subparsers.add_parser(
        "mining", help="Show mining ledger (ore extraction history)"
    )
    mining_parser.add_argument(
        "--days",
        "-d",
        type=int,
        default=30,
        help="Limit to last N days (default: 30, max available)",
    )
    mining_parser.add_argument("--system", "-s", type=str, help="Filter by system name")
    mining_parser.add_argument("--ore", "-o", type=str, help="Filter by ore type name")
    mining_parser.set_defaults(func=cmd_mining)

    # Mining summary command
    summary_parser = subparsers.add_parser(
        "mining-summary", help="Show mining summary (aggregated totals)"
    )
    summary_parser.add_argument(
        "--days", "-d", type=int, default=30, help="Limit to last N days (default: 30)"
    )
    summary_parser.set_defaults(func=cmd_mining_summary)
