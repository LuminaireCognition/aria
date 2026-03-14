#!/usr/bin/env python3
"""
Validate schema structure of ARIA reference JSON and YAML files.

Checks ~20 reference files that have no schema validation today,
verifying parse correctness, required keys, staleness, and optionally
cross-referencing IDs against the SDE database.

Tier A: Schema validation (offline, always runs)
Tier B: SDE cross-reference (requires cache/aria.db, SKIP if missing)

Usage:
    uv run python dev/scripts/validate-reference-schemas.py
    uv run python dev/scripts/validate-reference-schemas.py --verbose

Exit codes:
    0 = all checks pass (warnings are OK)
    1 = at least one FAIL
"""

from __future__ import annotations

import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
REFERENCE_DIR = PROJECT_ROOT / "reference"
DB_PATH = PROJECT_ROOT / "cache" / "aria.db"

# ---------------------------------------------------------------------------
# Colour helpers (shared pattern with validate-reference-data.py)
# ---------------------------------------------------------------------------

COLORS = {
    "FAIL": "\033[91m",
    "WARN": "\033[93m",
    "PASS": "\033[92m",
    "SKIP": "\033[90m",
    "RESET": "\033[0m",
    "BOLD": "\033[1m",
}


def colored(text: str, style: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"{COLORS.get(style, '')}{text}{COLORS['RESET']}"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class CheckResult:
    check: str  # e.g. "parse", "required_keys", "staleness"
    subject: str  # e.g. "mechanics/abyssal_deadspace.json"
    verdict: str  # PASS / FAIL / WARN / SKIP
    detail: str = ""  # human-readable explanation (empty for PASS)


# ---------------------------------------------------------------------------
# Schema definitions
# ---------------------------------------------------------------------------

SCHEMAS: dict[str, dict] = {
    "mechanics/abyssal_deadspace.json": {
        "required_keys": ["_meta", "weather_types", "tiers"],
        "format": "json",
        "staleness": True,
    },
    "mechanics/chokepoints.json": {
        "required_keys": ["systems"],
        "format": "json",
        "staleness": False,
        "sde_cross_ref": {
            "field": "systems[].system_id",
            "table": "solar_systems",
            "column": "system_id",
        },
    },
    "mechanics/epic_arcs.json": {
        "required_keys": ["_meta", "arcs"],
        "format": "json",
        "staleness": True,
    },
    "mechanics/planetary-interaction.json": {
        "required_keys": ["_meta", "p0_to_p1", "p2_schematics"],
        "format": "json",
        "staleness": True,
    },
    "mechanics/standings_thresholds.json": {
        "required_keys": ["_meta", "agent_levels"],
        "format": "json",
        "staleness": True,
    },
    "mechanics/security_status.json": {
        "required_keys": ["_meta"],
        "format": "json",
        "staleness": True,
    },
    "mechanics/hybrid_turrets.json": {
        "required_keys": ["_meta", "turret_types"],
        "format": "json",
        "staleness": True,
    },
    "mechanics/laser_turrets.json": {
        "required_keys": ["_meta", "turret_types"],
        "format": "json",
        "staleness": True,
    },
    "mechanics/projectile_turrets.json": {
        "required_keys": ["_meta", "turret_types"],
        "format": "json",
        "staleness": True,
    },
    "industry/fuel_blocks.json": {
        "required_keys": ["_meta", "fuel_blocks"],
        "format": "json",
        "staleness": True,
    },
    "industry/facility_bonuses.json": {
        "required_keys": ["_meta", "facilities"],
        "format": "json",
        "staleness": True,
    },
    "industry/invention_materials.json": {
        "required_keys": ["_meta"],
        "format": "json",
        "staleness": True,
    },
    "industry/material_sources.json": {
        "required_keys": ["_meta"],
        "format": "json",
        "staleness": True,
    },
    "industry/terminal_materials.json": {
        "required_keys": ["_meta"],
        "format": "json",
        "staleness": True,
    },
    "constants/trade_hubs.json": {
        "required_keys": ["_meta", "trade_hubs"],
        "format": "json",
        "staleness": True,
        "sde_cross_ref": {
            "field": "station_ids",
            "table": "stations",
            "column": "station_id",
        },
    },
    "factions/npc_corporations.json": {
        "required_keys": [],
        "format": "json",
        "staleness": False,
        "entry_required_keys": ["faction_id", "corporations"],
    },
}

YAML_SCHEMAS: dict[str, dict] = {
    "activities/skill_plans.yaml": {
        "format": "yaml",
        "staleness": False,
        "entry_required_keys": ["display_name", "category"],
    },
    "activities/isk_estimates.yaml": {
        "required_keys": ["_meta"],
        "format": "yaml",
        "staleness": True,
    },
    "skills/breakpoint_skills.yaml": {
        "format": "yaml",
        "staleness": False,
        "entry_required_keys": ["breakpoint_level", "effect"],
    },
    "skills/meta_module_alternatives.yaml": {
        "format": "yaml",
        "staleness": False,
    },
    "skills/ship_efficacy_rules.yaml": {
        "required_keys": ["ship_roles"],
        "format": "yaml",
        "staleness": False,
    },
    "archetypes/_shared/skill_tiers.yaml": {
        "required_keys": ["tiers"],
        "format": "yaml",
        "staleness": False,
    },
}

ALL_SCHEMAS: dict[str, dict] = {**SCHEMAS, **YAML_SCHEMAS}

# ---------------------------------------------------------------------------
# Staleness check (90-day threshold)
# ---------------------------------------------------------------------------

STALENESS_DAYS = 90


def check_staleness(data: dict, rel_path: str) -> CheckResult:
    """Check _meta.last_verified is a valid ISO date within 90 days."""
    meta = data.get("_meta", {})
    if not isinstance(meta, dict):
        return CheckResult(
            "staleness", rel_path, "WARN", "No _meta dict found",
        )

    last_verified = meta.get("last_verified")
    if not last_verified:
        return CheckResult(
            "staleness", rel_path, "WARN", "No _meta.last_verified date",
        )

    try:
        verified_date = datetime.strptime(str(last_verified), "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        )
        now = datetime.now(timezone.utc)
        days_ago = (now - verified_date).days
        if days_ago > STALENESS_DAYS:
            return CheckResult(
                "staleness", rel_path, "WARN",
                f"last_verified: {last_verified} ({days_ago} days ago, >{STALENESS_DAYS}d)",
            )
        return CheckResult(
            "staleness", rel_path, "PASS",
            f"last_verified: {last_verified} ({days_ago} days ago)",
        )
    except ValueError:
        return CheckResult(
            "staleness", rel_path, "WARN",
            f"Invalid date format: {last_verified}",
        )


# ---------------------------------------------------------------------------
# Tier A: Schema validation
# ---------------------------------------------------------------------------


def validate_file(rel_path: str, schema: dict) -> list[CheckResult]:
    """Run Tier A checks for a single reference file."""
    results: list[CheckResult] = []
    file_path = REFERENCE_DIR / rel_path

    # Check 1: File exists
    if not file_path.exists():
        results.append(CheckResult("parse", rel_path, "SKIP", "File not found"))
        return results

    # Check 2: Parse
    fmt = schema.get("format", "json")
    raw = file_path.read_text()
    data = None

    try:
        if fmt == "json":
            data = json.loads(raw)
        else:
            data = yaml.safe_load(raw)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        results.append(CheckResult("parse", rel_path, "FAIL", str(exc)))
        return results

    if data is None:
        results.append(CheckResult("parse", rel_path, "FAIL", "File is empty"))
        return results

    if not isinstance(data, dict):
        results.append(CheckResult(
            "parse", rel_path, "FAIL",
            f"Expected top-level dict, got {type(data).__name__}",
        ))
        return results

    results.append(CheckResult("parse", rel_path, "PASS"))

    # Check 3: Required top-level keys
    required_keys = schema.get("required_keys", [])
    if required_keys:
        missing = [k for k in required_keys if k not in data]
        if missing:
            results.append(CheckResult(
                "required_keys", rel_path, "FAIL",
                f"Missing keys: {', '.join(missing)}",
            ))
        else:
            results.append(CheckResult("required_keys", rel_path, "PASS"))

    # Check 4: Staleness
    if schema.get("staleness"):
        results.append(check_staleness(data, rel_path))

    # Check 5: Entry-level required keys
    entry_keys = schema.get("entry_required_keys")
    if entry_keys:
        bad_entries: list[str] = []
        for key, value in data.items():
            # Skip meta keys
            if key.startswith("_"):
                continue
            if not isinstance(value, dict):
                continue
            missing_entry_keys = [k for k in entry_keys if k not in value]
            if missing_entry_keys:
                bad_entries.append(f"{key}: missing {', '.join(missing_entry_keys)}")

        if bad_entries:
            detail = "; ".join(bad_entries[:10])
            if len(bad_entries) > 10:
                detail += f" ... and {len(bad_entries) - 10} more"
            results.append(CheckResult(
                "entry_keys", rel_path, "FAIL", detail,
            ))
        else:
            results.append(CheckResult("entry_keys", rel_path, "PASS"))

    return results


# ---------------------------------------------------------------------------
# Tier B: SDE cross-reference
# ---------------------------------------------------------------------------


def extract_chokepoint_system_ids(data: dict) -> list[int]:
    """Extract system_id values from chokepoints.json systems[]."""
    ids: list[int] = []
    for entry in data.get("systems", []):
        if isinstance(entry, dict) and "system_id" in entry:
            ids.append(entry["system_id"])
    return ids


def extract_trade_hub_station_ids(data: dict) -> list[int]:
    """Extract station_id values from trade_hubs.json trade_hubs."""
    ids: list[int] = []
    hubs = data.get("trade_hubs", {})
    if isinstance(hubs, dict):
        for _name, entry in hubs.items():
            if isinstance(entry, dict) and "station_id" in entry:
                ids.append(entry["station_id"])
    return ids


def validate_ids_against_sde(
    ids: list[int],
    table: str,
    column: str,
    db_path: Path,
) -> tuple[set[int], set[int]]:
    """Check IDs against an SDE table. Returns (found, missing)."""
    conn = sqlite3.connect(str(db_path))
    found: set[int] = set()
    batch_size = 500

    for i in range(0, len(ids), batch_size):
        batch = ids[i : i + batch_size]
        placeholders = ",".join("?" * len(batch))
        cursor = conn.execute(
            f"SELECT {column} FROM {table} WHERE {column} IN ({placeholders})",
            batch,
        )
        for (val,) in cursor.fetchall():
            found.add(val)

    conn.close()
    all_ids = set(ids)
    return found, all_ids - found


def run_sde_cross_refs() -> list[CheckResult]:
    """Run Tier B: SDE cross-reference checks."""
    results: list[CheckResult] = []

    if not DB_PATH.exists():
        results.append(CheckResult(
            "sde_cross_ref", "cache/aria.db", "SKIP",
            "SDE database not found — run 'uv run aria-esi sde-import' first",
        ))
        return results

    for rel_path, schema in ALL_SCHEMAS.items():
        cross_ref = schema.get("sde_cross_ref")
        if not cross_ref:
            continue

        file_path = REFERENCE_DIR / rel_path
        if not file_path.exists():
            continue

        fmt = schema.get("format", "json")
        try:
            raw = file_path.read_text()
            if fmt == "json":
                data = json.loads(raw)
            else:
                data = yaml.safe_load(raw)
        except (json.JSONDecodeError, yaml.YAMLError):
            continue  # Already reported in Tier A

        # Extract IDs based on field spec
        field = cross_ref["field"]
        table = cross_ref["table"]
        column = cross_ref["column"]

        if field == "systems[].system_id":
            ids = extract_chokepoint_system_ids(data)
        elif field == "station_ids":
            ids = extract_trade_hub_station_ids(data)
        else:
            results.append(CheckResult(
                "sde_cross_ref", rel_path, "SKIP",
                f"Unknown field extractor: {field}",
            ))
            continue

        if not ids:
            results.append(CheckResult(
                "sde_cross_ref", rel_path, "WARN", "No IDs extracted to validate",
            ))
            continue

        found, missing = validate_ids_against_sde(ids, table, column, DB_PATH)

        if missing:
            results.append(CheckResult(
                "sde_cross_ref", rel_path, "FAIL",
                f"{len(missing)} ID(s) not in {table}.{column}: {sorted(missing)[:10]}",
            ))
        else:
            results.append(CheckResult(
                "sde_cross_ref", rel_path, "PASS",
                f"All {len(found)} IDs validated against {table}",
            ))

    return results


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_all_checks() -> list[CheckResult]:
    """Run all validation checks and return results."""
    results: list[CheckResult] = []

    # Tier A: Schema validation
    for rel_path, schema in sorted(ALL_SCHEMAS.items()):
        results.extend(validate_file(rel_path, schema))

    # Tier B: SDE cross-reference
    results.extend(run_sde_cross_refs())

    return results


def print_results(results: list[CheckResult], verbose: bool = False) -> None:
    """Print formatted validation report."""
    print()
    print(colored("=== Reference Schema Validation ===", "BOLD"))
    print()

    current_check = ""
    for r in results:
        if r.check != current_check:
            current_check = r.check
            label = current_check.replace("_", " ").title()
            print(f"  {colored(label, 'BOLD')}")

        if r.verdict == "PASS" and not verbose:
            continue

        tag = colored(r.verdict, r.verdict)
        print(f"  {tag}  {r.subject}")
        if r.detail:
            for line in r.detail.split("\n"):
                print(f"        {line}")

    # Summary
    counts: dict[str, int] = {"PASS": 0, "FAIL": 0, "WARN": 0, "SKIP": 0}
    for r in results:
        counts[r.verdict] = counts.get(r.verdict, 0) + 1

    print()
    print(colored("  --- Summary ---", "BOLD"))
    print(
        f"  Checks: {colored(str(counts['PASS']), 'PASS')} passed, "
        f"{colored(str(counts['FAIL']), 'FAIL')} failed, "
        f"{colored(str(counts['WARN']), 'WARN')} warnings, "
        f"{colored(str(counts['SKIP']), 'SKIP')} skipped"
    )
    print()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate ARIA reference file schemas and structure",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show PASS results too",
    )
    args = parser.parse_args()

    results = run_all_checks()
    print_results(results, verbose=args.verbose)

    if any(r.verdict == "FAIL" for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
