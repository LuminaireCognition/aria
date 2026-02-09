"""
ARIA ESI Validation Commands

Validation commands for reference data integrity checks.

Includes:
- validate-sites: Validate site composition data against SDE
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from ..core import get_utc_timestamp

# =============================================================================
# Constants
# =============================================================================

# Staleness threshold for source verification (days)
SOURCE_STALENESS_DAYS = 90

# Default path relative to current working directory
SITE_COMPOSITIONS_RELATIVE = Path("reference") / "sites" / "site-compositions.yaml"


# =============================================================================
# Validate Sites Command
# =============================================================================


def collect_type_ids(data: dict) -> list[tuple[int, str, str]]:
    """
    Recursively collect all type_id values from data structure.

    Returns:
        List of (type_id, item_name, path) tuples
    """
    results = []

    def _extract_name(obj: dict, path: str) -> str:
        """Extract item name from various possible fields or path."""
        # Try common name fields
        for field in ("ore", "gas_type", "name", "type_name"):
            if field in obj and obj[field]:
                return obj[field]

        # Extract name from path (e.g., "flavors.amber_cytoserocin" -> "amber cytoserocin")
        if "." in path:
            last_part = path.split(".")[-1]
            # Convert snake_case to title case
            return last_part.replace("_", " ").title()

        return "unknown"

    def _traverse(obj: dict | list, path: str = "") -> None:
        if isinstance(obj, dict):
            # Check for type_id key
            if "type_id" in obj:
                type_id = obj["type_id"]
                item_name = _extract_name(obj, path)
                results.append((type_id, item_name, path))

            # Recurse into nested structures
            for key, value in obj.items():
                if key.startswith("_"):
                    continue  # Skip metadata
                new_path = f"{path}.{key}" if path else key
                _traverse(value, new_path)

        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                _traverse(item, f"{path}[{i}]")

    _traverse(data)
    return results


def collect_sources(data: dict) -> list[tuple[str, str, str]]:
    """
    Recursively collect all source entries with accessed dates.

    Returns:
        List of (url, accessed_date, path) tuples
    """
    results = []

    def _traverse(obj: dict | list, path: str = "") -> None:
        if isinstance(obj, dict):
            # Check for sources array
            if "sources" in obj and isinstance(obj["sources"], list):
                for i, source in enumerate(obj["sources"]):
                    if isinstance(source, dict):
                        url = source.get("url", "")
                        accessed = source.get("accessed", "")
                        results.append((url, accessed, f"{path}.sources[{i}]"))

            # Recurse into nested structures
            for key, value in obj.items():
                if key.startswith("_"):
                    continue  # Skip metadata
                new_path = f"{path}.{key}" if path else key
                _traverse(value, new_path)

        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                _traverse(item, f"{path}[{i}]")

    _traverse(data)
    return results


def validate_type_ids_against_sde(type_ids: list[tuple[int, str, str]]) -> list[dict[str, Any]]:
    """
    Validate type_ids exist in SDE database.

    Args:
        type_ids: List of (type_id, item_name, path) tuples

    Returns:
        List of validation issues
    """
    issues = []

    try:
        from ..mcp.market.database import MarketDatabase

        db = MarketDatabase()
        conn = db._get_connection()

        # Check if SDE is seeded
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='types'")
        if not cursor.fetchone():
            db.close()
            return [
                {
                    "level": "error",
                    "type": "sde_not_seeded",
                    "message": "SDE data not imported. Run 'aria-esi sde-seed' first.",
                }
            ]

        # Validate each type_id
        for type_id, item_name, path in type_ids:
            if type_id is None:
                issues.append(
                    {
                        "level": "warning",
                        "type": "null_type_id",
                        "path": path,
                        "item_name": item_name,
                        "message": f"type_id is null for {item_name}",
                    }
                )
                continue

            cursor = conn.execute("SELECT type_name FROM types WHERE type_id = ?", (type_id,))
            row = cursor.fetchone()

            if not row:
                issues.append(
                    {
                        "level": "error",
                        "type": "unknown_type_id",
                        "path": path,
                        "type_id": type_id,
                        "item_name": item_name,
                        "message": f"Unknown type_id {type_id} for {item_name}",
                    }
                )
            else:
                sde_name = row[0]
                # Check if names match (case-insensitive)
                if item_name.lower() != sde_name.lower():
                    issues.append(
                        {
                            "level": "info",
                            "type": "name_mismatch",
                            "path": path,
                            "type_id": type_id,
                            "data_name": item_name,
                            "sde_name": sde_name,
                            "message": f"Name mismatch: data has '{item_name}', SDE has '{sde_name}'",
                        }
                    )

        db.close()

    except ImportError as e:
        issues.append(
            {
                "level": "error",
                "type": "import_error",
                "message": f"Failed to import database module: {e}",
            }
        )

    return issues


def validate_source_freshness(
    sources: list[tuple[str, str, str]], staleness_days: int = SOURCE_STALENESS_DAYS
) -> list[dict[str, Any]]:
    """
    Check if sources have been verified recently.

    Args:
        sources: List of (url, accessed_date, path) tuples
        staleness_days: Number of days before a source is considered stale

    Returns:
        List of validation warnings
    """
    issues: list[dict[str, Any]] = []
    today = datetime.now()

    for url, accessed, path in sources:
        if not accessed:
            issues.append(
                {
                    "level": "warning",
                    "type": "missing_accessed_date",
                    "path": path,
                    "url": url,
                    "message": f"Source missing accessed date: {url}",
                }
            )
            continue

        try:
            accessed_date = datetime.strptime(accessed, "%Y-%m-%d")
            days_old = (today - accessed_date).days

            if days_old > staleness_days:
                issues.append(
                    {
                        "level": "warning",
                        "type": "stale_source",
                        "path": path,
                        "url": url,
                        "accessed": accessed,
                        "days_old": days_old,
                        "message": f"Source not verified in {days_old} days: {url}",
                    }
                )
        except ValueError:
            issues.append(
                {
                    "level": "warning",
                    "type": "invalid_date_format",
                    "path": path,
                    "url": url,
                    "accessed": accessed,
                    "message": f"Invalid date format '{accessed}' (expected YYYY-MM-DD)",
                }
            )

    return issues


def cmd_validate_sites(args: argparse.Namespace) -> dict:
    """
    Validate site composition data against SDE.

    Checks:
    1. All type_ids exist in SDE
    2. Names match SDE canonical names
    3. Sources have been verified recently

    Args:
        args: Parsed arguments

    Returns:
        Validation results
    """
    query_ts = get_utc_timestamp()

    # Check if data file exists
    if hasattr(args, "file") and args.file:
        data_path = Path(args.file)
    else:
        data_path = Path.cwd() / SITE_COMPOSITIONS_RELATIVE

    if not data_path.exists():
        return {
            "status": "error",
            "error": "file_not_found",
            "message": f"Site composition file not found: {data_path}",
            "hint": "Create the file at reference/sites/site-compositions.yaml",
            "query_timestamp": query_ts,
        }

    # Load YAML data
    try:
        with open(data_path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        return {
            "status": "error",
            "error": "yaml_parse_error",
            "message": f"Failed to parse YAML: {e}",
            "query_timestamp": query_ts,
        }

    if not data:
        return {
            "status": "error",
            "error": "empty_file",
            "message": "Site composition file is empty",
            "query_timestamp": query_ts,
        }

    print(f"Validating {data_path}...", file=sys.stderr)

    # Collect type_ids and sources
    type_ids = collect_type_ids(data)
    sources = collect_sources(data)

    print(f"  Found {len(type_ids)} type_id references", file=sys.stderr)
    print(f"  Found {len(sources)} source citations", file=sys.stderr)

    # Run validations
    issues = []

    # Validate type_ids against SDE
    print("  Validating type_ids against SDE...", file=sys.stderr)
    type_issues = validate_type_ids_against_sde(type_ids)
    issues.extend(type_issues)

    # Validate source freshness
    print("  Checking source freshness...", file=sys.stderr)
    source_issues = validate_source_freshness(sources)
    issues.extend(source_issues)

    # Count issues by level
    errors = [i for i in issues if i["level"] == "error"]
    warnings = [i for i in issues if i["level"] == "warning"]
    info = [i for i in issues if i["level"] == "info"]

    # Print summary to stderr
    print("", file=sys.stderr)
    if errors:
        print(f"  ERRORS: {len(errors)}", file=sys.stderr)
        for e in errors:
            print(f"    - {e['message']}", file=sys.stderr)
    if warnings:
        print(f"  WARNINGS: {len(warnings)}", file=sys.stderr)
        for w in warnings:
            print(f"    - {w['message']}", file=sys.stderr)
    if info:
        print(f"  INFO: {len(info)}", file=sys.stderr)

    if not issues:
        print("  All validations passed!", file=sys.stderr)

    # Determine overall status
    if errors:
        status = "failed"
    elif warnings:
        status = "warnings"
    else:
        status = "passed"

    return {
        "status": status,
        "file": str(data_path),
        "type_ids_checked": len(type_ids),
        "sources_checked": len(sources),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "info_count": len(info),
        "issues": issues if args.verbose else (errors + warnings),
        "schema_version": data.get("schema_version"),
        "last_updated": data.get("last_updated"),
        "query_timestamp": query_ts,
    }


# =============================================================================
# Argument Parser Registration
# =============================================================================


def register_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Register validation command parsers."""

    # validate-sites command
    parser = subparsers.add_parser(
        "validate-sites",
        help="Validate site composition data against SDE",
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Path to site compositions YAML file (default: reference/sites/site-compositions.yaml)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Include info-level issues in output",
    )
    parser.set_defaults(func=cmd_validate_sites, verbose=False)
