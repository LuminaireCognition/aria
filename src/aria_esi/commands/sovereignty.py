"""
ARIA ESI Sovereignty Commands

CLI commands for sovereignty data management:
- sov-update: Fetch and cache sovereignty data from ESI
- sov-status: Show sovereignty cache status
- sov-lookup: Look up sovereignty for a system
- sov-validate: Validate coalition data against authoritative sources
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from ..core import get_utc_timestamp
from ..core.logging import get_logger

logger = get_logger(__name__)


def cmd_sov_update(args: argparse.Namespace) -> dict:
    """
    Fetch sovereignty data from ESI and update local cache.

    Fetches:
    - Sovereignty map from ESI /sovereignty/map/
    - Alliance names for all alliances holding sovereignty

    Updates:
    - Local SQLite database
    """
    query_ts = get_utc_timestamp()

    try:
        from ..services.sovereignty import (
            fetch_alliances_batch_sync,
            fetch_sovereignty_map_sync,
            get_sovereignty_database,
        )
        from ..services.sovereignty.database import AllianceRecord, SovereigntyRecord
    except ImportError as e:
        return {
            "error": "import_error",
            "message": f"Failed to import sovereignty service: {e}",
            "query_timestamp": query_ts,
        }

    force = getattr(args, "force", False)

    try:
        db = get_sovereignty_database()
        stats_before = db.get_stats()

        # Check if we need to update
        if not force and stats_before["sov_newest_seconds"] is not None:
            age_hours = stats_before["sov_newest_seconds"] / 3600
            if age_hours < 1:
                return {
                    "status": "skipped",
                    "message": f"Sovereignty data is {age_hours:.1f} hours old. Use --force to refresh.",
                    "stats": stats_before,
                    "query_timestamp": query_ts,
                }

        # Fetch sovereignty map from ESI
        logger.info("Fetching sovereignty map from ESI...")
        sov_data = fetch_sovereignty_map_sync()

        # Convert to records
        now = int(time.time())
        records = [
            SovereigntyRecord(
                system_id=entry["system_id"],
                alliance_id=entry.get("alliance_id"),
                corporation_id=entry.get("corporation_id"),
                faction_id=entry.get("faction_id"),
                updated_at=now,
            )
            for entry in sov_data
        ]

        # Clear and save new data
        db.clear_sovereignty()
        saved_count = db.save_sovereignty_batch(records)
        logger.info("Saved %d sovereignty records", saved_count)

        # Collect unique alliance IDs
        alliance_ids = list(
            {r.alliance_id for r in records if r.alliance_id is not None}
        )
        logger.info("Found %d unique alliances holding sovereignty", len(alliance_ids))

        # Fetch alliance info
        alliances_fetched = 0
        if alliance_ids:
            logger.info("Fetching alliance information...")
            alliance_data = fetch_alliances_batch_sync(alliance_ids)

            # Save alliance records
            alliance_records = [
                AllianceRecord(
                    alliance_id=aid,
                    name=data["name"],
                    ticker=data["ticker"],
                    executor_corporation_id=data.get("executor_corporation_id"),
                    faction_id=data.get("faction_id"),
                    updated_at=now,
                )
                for aid, data in alliance_data.items()
            ]
            db.save_alliances_batch(alliance_records)
            alliances_fetched = len(alliance_records)
            logger.info("Saved %d alliance records", alliances_fetched)

        stats_after = db.get_stats()

        return {
            "status": "success",
            "message": f"Updated sovereignty data: {saved_count} systems, {alliances_fetched} alliances",
            "sovereignty_count": saved_count,
            "alliances_fetched": alliances_fetched,
            "unique_alliances": len(alliance_ids),
            "stats": stats_after,
            "query_timestamp": query_ts,
        }

    except Exception as e:
        logger.exception("Sovereignty update failed")
        return {
            "error": "update_failed",
            "message": str(e),
            "query_timestamp": query_ts,
        }


def cmd_sov_status(args: argparse.Namespace) -> dict:
    """
    Show sovereignty cache status.

    Displays:
    - Database location and size
    - Number of cached sovereignty entries
    - Number of cached alliances
    - Data freshness
    """
    query_ts = get_utc_timestamp()

    try:
        from ..services.sovereignty import get_sovereignty_database
    except ImportError as e:
        return {
            "error": "import_error",
            "message": f"Failed to import sovereignty service: {e}",
            "query_timestamp": query_ts,
        }

    try:
        db = get_sovereignty_database()
        stats = db.get_stats()

        # Format age nicely
        freshness = "unknown"
        if stats["sov_newest_seconds"] is not None:
            hours = stats["sov_newest_seconds"] / 3600
            if hours < 1:
                freshness = f"{stats['sov_newest_seconds'] / 60:.0f} minutes"
            elif hours < 24:
                freshness = f"{hours:.1f} hours"
            else:
                freshness = f"{hours / 24:.1f} days"

        return {
            "status": "ok",
            "sovereignty_count": stats["sovereignty_count"],
            "alliance_count": stats["alliance_count"],
            "coalition_count": stats["coalition_count"],
            "data_age": freshness,
            "database_path": stats["database_path"],
            "database_size_kb": stats["database_size_kb"],
            "query_timestamp": query_ts,
        }

    except Exception as e:
        return {
            "error": "status_failed",
            "message": str(e),
            "query_timestamp": query_ts,
        }


def cmd_sov_lookup(args: argparse.Namespace) -> dict:
    """
    Look up sovereignty for a system.

    Args:
        system: System name or ID
    """
    query_ts = get_utc_timestamp()

    try:
        from ..services.sovereignty import get_sovereignty_database
        from ..universe.builder import load_universe_graph
    except ImportError as e:
        return {
            "error": "import_error",
            "message": f"Failed to import required modules: {e}",
            "query_timestamp": query_ts,
        }

    system_input = args.system

    try:
        # Load universe graph for name resolution
        universe = load_universe_graph()
        db = get_sovereignty_database()

        # Resolve system name to ID
        system_id = None
        system_name = None

        if system_input.isdigit():
            system_id = int(system_input)
            idx = universe.id_to_idx.get(system_id)
            if idx is not None:
                system_name = universe.idx_to_name[idx]
        else:
            idx = universe.resolve_name(system_input)
            if idx is not None:
                system_id = int(universe.system_ids[idx])
                system_name = universe.idx_to_name[idx]

        if system_id is None:
            return {
                "error": "system_not_found",
                "message": f"System not found: {system_input}",
                "query_timestamp": query_ts,
            }

        # Get sovereignty
        sov = db.get_sovereignty(system_id)

        result = {
            "system": {
                "name": system_name,
                "id": system_id,
            },
            "query_timestamp": query_ts,
        }

        if sov is None:
            # Check what kind of system this is to provide accurate messaging
            idx = universe.id_to_idx.get(system_id)
            result["sovereignty"] = None

            # Check if it's a wormhole system (J-space)
            # J-space systems have names starting with "J" followed by digits
            # or are Thera/special wormhole systems
            # WH system ID range check works even if system isn't in graph
            is_wormhole = (
                (system_name and system_name.startswith("J") and
                 len(system_name) > 1 and system_name[1:].replace("-", "").isdigit())
                or system_name == "Thera"
                or (system_id and 31000000 <= system_id < 32000000)  # WH system ID range
            )

            if is_wormhole:
                result["note"] = "Wormhole system - sovereignty does not apply"
            elif idx is not None:
                sec = float(universe.security[idx])
                if sec > 0.0:
                    result["note"] = "Not a null-sec system (no sovereignty data)"
                else:
                    # Actual null-sec without data - might need update
                    result["note"] = "No sovereignty data cached. Run 'sov-update' to refresh."
            else:
                # System not in graph and not detected as wormhole
                result["note"] = "System not in universe graph - no additional context available"
            return result

        # Resolve alliance name
        alliance_name = None
        if sov.alliance_id:
            alliance = db.get_alliance(sov.alliance_id)
            if alliance:
                alliance_name = f"[{alliance.ticker}] {alliance.name}"

        # Check coalition
        coalition_id = None
        coalition_name = None
        if sov.alliance_id:
            coalition_id = db.get_coalition_for_alliance(sov.alliance_id)
            if coalition_id:
                coalition = db.get_coalition(coalition_id)
                if coalition:
                    coalition_name = coalition.display_name

        result["sovereignty"] = {
            "alliance_id": sov.alliance_id,
            "alliance_name": alliance_name,
            "corporation_id": sov.corporation_id,
            "faction_id": sov.faction_id,
            "coalition_id": coalition_id,
            "coalition_name": coalition_name,
            "updated_at": sov.updated_at,
        }

        return result

    except Exception as e:
        return {
            "error": "lookup_failed",
            "message": str(e),
            "query_timestamp": query_ts,
        }


def cmd_sov_coalitions(args: argparse.Namespace) -> dict:
    """
    List known coalitions.

    Shows coalitions loaded from coalitions.yaml with member counts.
    """
    query_ts = get_utc_timestamp()

    try:
        from ..services.sovereignty import get_sovereignty_database
    except ImportError as e:
        return {
            "error": "import_error",
            "message": f"Failed to import sovereignty service: {e}",
            "query_timestamp": query_ts,
        }

    try:
        db = get_sovereignty_database()
        coalitions = db.get_all_coalitions()

        result_coalitions = []
        for c in coalitions:
            alliance_ids = db.get_coalition_alliances(c.coalition_id)
            result_coalitions.append({
                "id": c.coalition_id,
                "name": c.display_name,
                "aliases": c.aliases,
                "alliance_count": len(alliance_ids),
            })

        return {
            "coalitions": result_coalitions,
            "total": len(result_coalitions),
            "query_timestamp": query_ts,
        }

    except Exception as e:
        return {
            "error": "coalitions_failed",
            "message": str(e),
            "query_timestamp": query_ts,
        }


def cmd_sov_load_coalitions(args: argparse.Namespace) -> dict:
    """
    Load coalition data from YAML into database.

    Reads coalitions.yaml and populates the coalitions and
    coalition_members tables.

    By default, validates alliance IDs against ESI before loading (fail-fast).
    Use --skip-validation to bypass (not recommended).
    """
    query_ts = get_utc_timestamp()

    try:
        import yaml

        from ..services.sovereignty import get_sovereignty_database
        from ..services.sovereignty.database import CoalitionRecord
    except ImportError as e:
        return {
            "error": "import_error",
            "message": f"Failed to import required modules: {e}",
            "query_timestamp": query_ts,
        }

    skip_validation = getattr(args, "skip_validation", False)

    try:
        # Load YAML
        yaml_path = Path(__file__).parent.parent / "data" / "sovereignty" / "coalitions.yaml"
        if not yaml_path.exists():
            return {
                "error": "file_not_found",
                "message": f"Coalition file not found: {yaml_path}",
                "query_timestamp": query_ts,
            }

        # Fail-fast: Validate before loading
        if not skip_validation:
            logger.info("Validating coalition data against ESI...")
            validation_result = validate_coalitions_yaml(yaml_path=yaml_path, fix=False)

            if validation_result.get("error") == "esi_unavailable":
                return {
                    "error": "validation_failed",
                    "message": "ESI unavailable - cannot validate coalition data. Use --skip-validation to bypass (not recommended).",
                    "validation": validation_result,
                    "query_timestamp": query_ts,
                }

            if not validation_result.get("valid", False):
                # Build error message based on what failed
                error_parts = []
                hints = []

                if validation_result.get("duplicate_count", 0) > 0:
                    error_parts.append(
                        f"{validation_result['duplicate_count']} duplicate alliance ID(s) across coalitions"
                    )
                    hints.append("Fix duplicates manually - each alliance can only belong to one coalition")

                if validation_result.get("invalid_count", 0) > 0:
                    error_parts.append(
                        f"{validation_result['invalid_count']} invalid alliance entries"
                    )
                    hints.append("Run 'sov-validate --fix' to correct invalid entries")

                message = "Coalition data contains " + " and ".join(error_parts) + "."
                if hints:
                    message += " " + "; ".join(hints) + "."

                return {
                    "error": "validation_failed",
                    "message": message,
                    "validation": validation_result,
                    "query_timestamp": query_ts,
                }

            logger.info("Validation passed: %d alliances verified", validation_result.get("valid_count", 0))

        with open(yaml_path) as f:
            data = yaml.safe_load(f)

        db = get_sovereignty_database()
        now = int(time.time())

        # Clear existing coalition data before loading to remove stale entries
        # This ensures coalitions deleted from YAML don't persist in the DB
        cleared_count = db.clear_coalitions()
        if cleared_count > 0:
            logger.info("Cleared %d existing coalitions before reload", cleared_count)

        coalitions_loaded = 0
        members_loaded = 0

        coalitions_data = data.get("coalitions", {})
        for coalition_id, coalition_info in coalitions_data.items():
            # Create coalition record
            record = CoalitionRecord(
                coalition_id=coalition_id,
                display_name=coalition_info.get("display_name", coalition_id),
                aliases=coalition_info.get("aliases", []),
                updated_at=now,
            )
            db.save_coalition(record)
            coalitions_loaded += 1

            # Add members
            alliances = coalition_info.get("alliances", [])
            alliance_ids = [a["id"] for a in alliances if "id" in a]
            if alliance_ids:
                count = db.save_coalition_members(coalition_id, alliance_ids)
                members_loaded += count

        return {
            "status": "success",
            "coalitions_loaded": coalitions_loaded,
            "members_loaded": members_loaded,
            "source": str(yaml_path),
            "query_timestamp": query_ts,
        }

    except Exception as e:
        return {
            "error": "load_failed",
            "message": str(e),
            "query_timestamp": query_ts,
        }


def validate_coalitions_yaml(
    yaml_path: Path | None = None,
    fix: bool = False,
) -> dict:
    """
    Validate coalition data against authoritative sources.

    Validates:
    - Alliance IDs against ESI (authoritative)
    - No duplicate alliance IDs across coalitions (would corrupt DB)

    Args:
        yaml_path: Path to coalitions.yaml (defaults to standard location)
        fix: If True, auto-fix invalid IDs from ESI

    Returns:
        Validation result dict with errors, warnings, and fixes applied
    """
    import yaml

    from ..services.sovereignty import fetch_alliances_batch_sync

    if yaml_path is None:
        yaml_path = Path(__file__).parent.parent / "data" / "sovereignty" / "coalitions.yaml"

    if not yaml_path.exists():
        return {
            "valid": False,
            "error": "file_not_found",
            "message": f"Coalition file not found: {yaml_path}",
        }

    # Load YAML
    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    coalitions_data = data.get("coalitions", {})

    # Collect all alliance IDs and check for duplicates
    alliance_entries: list[tuple[str, str, int]] = []  # (coalition_id, alliance_name, alliance_id)
    seen_alliance_ids: dict[int, str] = {}  # alliance_id -> first coalition_id
    duplicate_entries: list[dict] = []  # Duplicates found

    for coalition_id, coalition_info in coalitions_data.items():
        for alliance in coalition_info.get("alliances", []):
            if "id" in alliance and "name" in alliance:
                aid = alliance["id"]
                if aid in seen_alliance_ids:
                    # Duplicate found - same alliance in multiple coalitions
                    duplicate_entries.append({
                        "alliance_id": aid,
                        "alliance_name": alliance["name"],
                        "first_coalition": seen_alliance_ids[aid],
                        "duplicate_coalition": coalition_id,
                    })
                    logger.warning(
                        "Duplicate alliance ID %d (%s) found in coalitions '%s' and '%s'",
                        aid, alliance["name"], seen_alliance_ids[aid], coalition_id
                    )
                else:
                    seen_alliance_ids[aid] = coalition_id
                alliance_entries.append((coalition_id, alliance["name"], aid))

    if not alliance_entries:
        return {
            "valid": True,
            "message": "No alliance entries to validate",
            "alliances_checked": 0,
        }

    # Fetch all alliance IDs from ESI to validate
    alliance_ids = [entry[2] for entry in alliance_entries]
    logger.info("Validating %d alliance IDs against ESI...", len(alliance_ids))

    try:
        esi_results = fetch_alliances_batch_sync(alliance_ids)
    except Exception as e:
        return {
            "valid": False,
            "error": "esi_unavailable",
            "message": f"ESI unavailable - cannot validate: {e}",
        }

    # Check results
    valid_entries: list[tuple[str, str, int]] = []
    invalid_entries: list[tuple[str, str, int, str]] = []  # includes reason

    for coalition_id, alliance_name, alliance_id in alliance_entries:
        if alliance_id in esi_results:
            esi_name = esi_results[alliance_id].get("name", "")
            if esi_name != alliance_name:
                # Name mismatch - ID is valid but name differs
                invalid_entries.append(
                    (coalition_id, alliance_name, alliance_id, f"Name mismatch: ESI says '{esi_name}'")
                )
            else:
                valid_entries.append((coalition_id, alliance_name, alliance_id))
        else:
            # Alliance not found in ESI
            invalid_entries.append(
                (coalition_id, alliance_name, alliance_id, "Alliance not found in ESI")
            )

    # Validation fails if there are invalid ESI entries OR duplicate alliance IDs
    has_duplicates = len(duplicate_entries) > 0
    has_invalid = len(invalid_entries) > 0

    result = {
        "valid": not has_invalid and not has_duplicates,
        "alliances_checked": len(alliance_entries),
        "valid_count": len(valid_entries),
        "invalid_count": len(invalid_entries),
        "duplicate_count": len(duplicate_entries),
        "invalid_entries": [
            {
                "coalition": e[0],
                "alliance_name": e[1],
                "alliance_id": e[2],
                "reason": e[3],
            }
            for e in invalid_entries
        ],
        "duplicate_entries": duplicate_entries,
    }

    # Fail early if duplicates found - these corrupt the database
    if has_duplicates:
        result["error"] = "duplicate_alliance_ids"
        result["message"] = (
            f"Found {len(duplicate_entries)} duplicate alliance ID(s) across coalitions. "
            "Each alliance can only belong to one coalition. Fix manually before loading."
        )

    # Handle fixes if requested
    if fix and invalid_entries:
        removed_count = 0
        name_fixed_count = 0

        for coalition_id, alliance_name, alliance_id, reason in invalid_entries:
            if "not found" in reason.lower():
                # Remove invalid alliance from coalition
                alliances = coalitions_data[coalition_id].get("alliances", [])
                coalitions_data[coalition_id]["alliances"] = [
                    a for a in alliances if a.get("id") != alliance_id
                ]
                removed_count += 1
                logger.warning(
                    "Removed invalid alliance '%s' (ID: %d) from %s: %s",
                    alliance_name, alliance_id, coalition_id, reason
                )
            elif "Name mismatch" in reason:
                # Fix the name
                alliances = coalitions_data[coalition_id].get("alliances", [])
                for a in alliances:
                    if a.get("id") == alliance_id:
                        esi_name = esi_results[alliance_id].get("name", "")
                        a["name"] = esi_name
                        name_fixed_count += 1
                        logger.info(
                            "Fixed alliance name: '%s' -> '%s' (ID: %d)",
                            alliance_name, esi_name, alliance_id
                        )

        # Write back to YAML
        # WARNING: yaml.dump strips all comments from the file
        logger.warning(
            "Writing fixed YAML - all comments and formatting will be lost. "
            "You may want to restore comments from git history."
        )
        with open(yaml_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        result["fixes_applied"] = {
            "removed": removed_count,
            "name_fixed": name_fixed_count,
        }

        fix_message = f"Removed {removed_count} invalid entries, fixed {name_fixed_count} names."

        # If duplicates exist, preserve that error message alongside fix results
        if has_duplicates:
            # Keep the duplicate error as the primary message, add fix results
            result["fix_summary"] = fix_message
            # result["message"] already set to duplicate error - don't overwrite
        else:
            result["message"] = fix_message

        result["warning"] = (
            "YAML comments and formatting were lost during fix. "
            "Consider restoring header comments from git history."
        )

    return result


def cmd_sov_validate(args: argparse.Namespace) -> dict:
    """
    Validate coalition data against authoritative sources.

    Validates alliance IDs in coalitions.yaml against ESI.
    With --fix, automatically removes invalid entries and corrects names.

    This command enforces data authority:
    - ESI is authoritative for alliance IDs and names
    - Invalid entries are removed (with --fix)
    - Name mismatches are corrected (with --fix)
    - Duplicate alliance IDs across coalitions are detected

    WARNING: --fix rewrites the YAML file using PyYAML, which strips all
    comments and reformats the file. Consider restoring header comments
    from git history after fixing.
    """
    query_ts = get_utc_timestamp()

    fix = getattr(args, "fix", False)

    try:
        result = validate_coalitions_yaml(fix=fix)
        result["query_timestamp"] = query_ts

        if result.get("error") == "esi_unavailable":
            # ESI unavailable is a blocking error
            return result

        if not result.get("valid", False):
            if not fix:
                # Provide error-aware hint
                has_duplicates = result.get("duplicate_count", 0) > 0
                has_invalid = result.get("invalid_count", 0) > 0

                hints = []
                if has_duplicates:
                    hints.append("Duplicates must be fixed manually in coalitions.yaml")
                if has_invalid:
                    hints.append("Run with --fix to auto-remove invalid entries")

                if hints:
                    result["hint"] = "; ".join(hints)

        return result

    except Exception as e:
        logger.exception("Validation failed")
        return {
            "error": "validation_failed",
            "message": str(e),
            "query_timestamp": query_ts,
        }


# =============================================================================
# Argument Parser Registration
# =============================================================================


def register_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Register sovereignty command parsers."""

    # sov-update: Fetch ESI data
    update_parser = subparsers.add_parser(
        "sov-update",
        help="Fetch sovereignty data from ESI",
    )
    update_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force update even if data is fresh",
    )
    update_parser.set_defaults(func=cmd_sov_update)

    # sov-status: Show cache status
    status_parser = subparsers.add_parser(
        "sov-status",
        help="Show sovereignty cache status",
    )
    status_parser.set_defaults(func=cmd_sov_status)

    # sov-lookup: Look up sovereignty for a system
    lookup_parser = subparsers.add_parser(
        "sov-lookup",
        help="Look up sovereignty for a system",
    )
    lookup_parser.add_argument(
        "system",
        help="System name or ID to look up",
    )
    lookup_parser.set_defaults(func=cmd_sov_lookup)

    # sov-coalitions: List known coalitions
    coalitions_parser = subparsers.add_parser(
        "sov-coalitions",
        help="List known coalitions",
    )
    coalitions_parser.set_defaults(func=cmd_sov_coalitions)

    # sov-load-coalitions: Load coalition YAML
    load_parser = subparsers.add_parser(
        "sov-load-coalitions",
        help="Load coalition data from YAML into database",
    )
    load_parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip ESI validation (not recommended)",
    )
    load_parser.set_defaults(func=cmd_sov_load_coalitions)

    # sov-validate: Validate coalition data
    validate_parser = subparsers.add_parser(
        "sov-validate",
        help="Validate coalition data against ESI",
    )
    validate_parser.add_argument(
        "--fix",
        action="store_true",
        help="Auto-fix invalid entries (WARNING: strips all YAML comments)",
    )
    validate_parser.set_defaults(func=cmd_sov_validate)
