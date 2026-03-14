#!/usr/bin/env python3
"""
Validate rig items in archetype YAML files against the SDE database.

Checks that all rigs used in archetype fits are:
    1. Real rig items (SDE group starts with "Rig ")
    2. Correctly sized for the hull class (Small/Medium/Large)

Sources validated:
    - EFT blocks (rig section identified by position)
    - damage_tuning.overrides rigs[].from / to
    - _shared/faction_tuning.yaml optional_swap rigs

Usage:
    uv run python dev/scripts/validate-archetype-rigs.py
    uv run python dev/scripts/validate-archetype-rigs.py --verbose

Exit codes:
    0 = all checks pass
    1 = at least one FAIL
"""

from __future__ import annotations

import re
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ARCHETYPES_DIR = PROJECT_ROOT / "reference" / "archetypes"
HULLS_DIR = ARCHETYPES_DIR / "hulls"
SHARED_DIR = ARCHETYPES_DIR / "_shared"
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
class RigReference:
    """A reference to a rig item found in an archetype file."""

    name: str
    source: str  # e.g. "eft[rig]", "overrides.angel_cartel.rigs.to"
    file: str  # relative path from archetypes/
    hull_class: str  # e.g. "frigate", "cruiser", "battleship"


@dataclass
class CheckResult:
    check: str  # e.g. "rig_exists", "rig_size"
    subject: str
    verdict: str  # PASS / FAIL / WARN / SKIP
    detail: str = ""


# ---------------------------------------------------------------------------
# Hull class to expected rig size
# ---------------------------------------------------------------------------

HULL_CLASS_RIG_SIZE: dict[str, str] = {
    "frigate": "Small",
    "destroyer": "Small",
    "mining_frigate": "Small",
    "cruiser": "Medium",
    "battlecruiser": "Medium",
    "industrial": "Medium",
    "barge": "Medium",
    "battleship": "Large",
}

# ---------------------------------------------------------------------------
# EFT rig extraction
# ---------------------------------------------------------------------------

EFT_HEADER_RE = re.compile(r"^\[(.+?),\s*(.+)\]$")
EMPTY_SLOT_RE = re.compile(r"^\[Empty .+ slot\]$", re.IGNORECASE)
QUANTITY_RE = re.compile(r"\s+x(\d+)$")

# After removing the header line, EFT sections separated by blank lines are:
# 0=low, 1=mid, 2=high, 3=rigs, 4=subsystems, 5=drones, 6=cargo
RIG_SECTION_INDEX = 3


def extract_eft_rigs(eft_block: str) -> list[str]:
    """Extract rig names from the rig section of an EFT block.

    Returns a list of rig item names (excludes empty rig slots).
    The header line is stripped first so section counting starts from low slots.
    """
    lines = eft_block.strip().splitlines()

    # Remove the header line (first non-blank line matching [Ship, Name])
    body_lines: list[str] = []
    header_found = False
    for line in lines:
        stripped = line.strip()
        if not header_found and EFT_HEADER_RE.match(stripped):
            header_found = True
            continue
        body_lines.append(stripped)

    # Split remaining lines into sections by blank lines,
    # skipping any leading blank lines after header removal
    sections: list[list[str]] = []
    current: list[str] = []

    for line in body_lines:
        if not line:
            if current:
                sections.append(current)
                current = []
        else:
            current.append(line)
    if current:
        sections.append(current)

    if len(sections) <= RIG_SECTION_INDEX:
        return []

    rig_section = sections[RIG_SECTION_INDEX]
    rigs: list[str] = []
    for line in rig_section:
        if EMPTY_SLOT_RE.match(line):
            continue
        # Strip quantity suffix (shouldn't appear on rigs, but be safe)
        line = QUANTITY_RE.sub("", line)
        # Strip charge after comma
        if ", " in line:
            line = line.split(", ", 1)[0].strip()
        rigs.append(line)

    return rigs


# ---------------------------------------------------------------------------
# Reference collection
# ---------------------------------------------------------------------------


def collect_rig_references() -> list[RigReference]:
    """Collect all rig references from archetype YAMLs and shared configs."""
    refs: list[RigReference] = []

    # Archetype YAML files
    for path in sorted(HULLS_DIR.rglob("*.yaml")):
        rel = str(path.relative_to(ARCHETYPES_DIR))
        # Derive hull class from path: hulls/{class}/{ship}/...
        parts = path.relative_to(HULLS_DIR).parts
        if len(parts) < 2:
            continue
        hull_class = parts[0]

        data = yaml.safe_load(path.read_text())
        if not data or not isinstance(data, dict):
            continue

        # 1. EFT block rigs
        eft = data.get("eft", "")
        if eft:
            for rig_name in extract_eft_rigs(eft):
                refs.append(RigReference(
                    name=rig_name,
                    source="eft[rig]",
                    file=rel,
                    hull_class=hull_class,
                ))

        # 2. damage_tuning.overrides rigs
        dt = data.get("damage_tuning", {})
        if isinstance(dt, dict):
            overrides = dt.get("overrides", {})
            if isinstance(overrides, dict):
                for faction, entry in overrides.items():
                    if not isinstance(entry, dict):
                        continue
                    for rig in entry.get("rigs", []):
                        if isinstance(rig, dict):
                            for key in ("from", "to"):
                                if key in rig:
                                    refs.append(RigReference(
                                        name=rig[key],
                                        source=f"overrides.{faction}.rigs.{key}",
                                        file=rel,
                                        hull_class=hull_class,
                                    ))

    # 3. Shared faction_tuning.yaml rigs
    faction_tuning_path = SHARED_DIR / "faction_tuning.yaml"
    if faction_tuning_path.exists():
        data = yaml.safe_load(faction_tuning_path.read_text())
        if data and isinstance(data, dict):
            for profile, factions in data.items():
                if not isinstance(factions, dict):
                    continue
                for faction, entry in factions.items():
                    if not isinstance(entry, dict):
                        continue
                    for rig in entry.get("rigs", []):
                        if isinstance(rig, dict) and "optional_swap" in rig:
                            refs.append(RigReference(
                                name=rig["optional_swap"],
                                source=f"faction_tuning.{profile}.{faction}.rigs",
                                file="_shared/faction_tuning.yaml",
                                hull_class="",  # faction_tuning is hull-agnostic
                            ))

    return refs


# ---------------------------------------------------------------------------
# SDE validation
# ---------------------------------------------------------------------------


@dataclass
class RigInfo:
    """SDE data about a rig item."""

    type_name: str
    group_name: str
    is_rig: bool
    size_prefix: str  # "Small", "Medium", "Large", "Capital", or ""


def load_rig_info(names: set[str], db_path: Path) -> dict[str, RigInfo | None]:
    """Look up rig details from SDE.

    Returns {name: RigInfo} for found items, {name: None} for missing.
    """
    conn = sqlite3.connect(str(db_path))
    result: dict[str, RigInfo | None] = {n: None for n in names}

    # Build lowercase -> original mapping
    lower_to_original: dict[str, str] = {}
    for name in names:
        lower_to_original[name.lower()] = name

    # Batch lookup
    batch_size = 500
    lower_keys = list(lower_to_original.keys())

    for i in range(0, len(lower_keys), batch_size):
        batch = lower_keys[i : i + batch_size]
        placeholders = ",".join("?" * len(batch))
        cursor = conn.execute(
            f"SELECT t.type_name, t.type_name_lower, g.group_name "
            f"FROM types t "
            f"JOIN groups g ON t.group_id = g.group_id "
            f"WHERE t.type_name_lower IN ({placeholders}) AND t.published = 1",
            batch,
        )
        for type_name, type_name_lower, group_name in cursor.fetchall():
            original = lower_to_original.get(type_name_lower)
            if original is None:
                continue

            is_rig = group_name.startswith("Rig ")

            # Determine size prefix
            size_prefix = ""
            for prefix in ("Small", "Medium", "Large", "Capital"):
                if type_name.startswith(prefix + " "):
                    size_prefix = prefix
                    break

            result[original] = RigInfo(
                type_name=type_name,
                group_name=group_name,
                is_rig=is_rig,
                size_prefix=size_prefix,
            )

    conn.close()
    return result


def suggest_items(name: str, db_path: Path) -> list[str]:
    """Find SDE suggestions for a missing item name."""
    conn = sqlite3.connect(str(db_path))
    query_lower = name.lower()

    # Try prefix match on first 12 chars
    prefix = query_lower[:12]
    cursor = conn.execute(
        "SELECT type_name FROM types "
        "WHERE type_name_lower LIKE ? AND published = 1 "
        "ORDER BY length(type_name) LIMIT 5",
        (f"{prefix}%",),
    )
    sugs = [row[0] for row in cursor.fetchall()]

    if not sugs:
        words = [w for w in query_lower.split() if len(w) > 2 and w not in ("the", "and")]
        if len(words) >= 2:
            pattern = f"%{words[0]}%{words[1]}%"
            cursor = conn.execute(
                "SELECT type_name FROM types "
                "WHERE type_name_lower LIKE ? AND published = 1 "
                "ORDER BY length(type_name) LIMIT 5",
                (pattern,),
            )
            sugs = [row[0] for row in cursor.fetchall()]

    conn.close()
    return sugs


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def run_validation(verbose: bool = False) -> list[CheckResult]:
    """Run all rig validation checks."""
    results: list[CheckResult] = []

    # Check database exists
    if not DB_PATH.exists():
        results.append(CheckResult(
            "sde_available",
            "cache/aria.db",
            "SKIP",
            "SDE database not found — run 'uv run aria-esi sde-import' first",
        ))
        return results

    results.append(CheckResult("sde_available", "cache/aria.db", "PASS"))

    # Collect all rig references
    all_refs = collect_rig_references()
    unique_names = {ref.name for ref in all_refs}

    results.append(CheckResult(
        "rig_count",
        f"{len(unique_names)} unique rigs across {len(all_refs)} references",
        "PASS",
    ))

    if not unique_names:
        results.append(CheckResult("rig_count", "no rigs found", "SKIP"))
        return results

    # Load rig info from SDE
    rig_info = load_rig_info(unique_names, DB_PATH)

    # Group references by name for reporting
    refs_by_name: dict[str, list[RigReference]] = defaultdict(list)
    for ref in all_refs:
        refs_by_name[ref.name].append(ref)

    # Check 1: rig_exists — does the item exist in SDE?
    for name in sorted(unique_names):
        info = rig_info[name]
        if info is None:
            locs = refs_by_name[name]
            files = sorted({r.file for r in locs})
            sugs = suggest_items(name, DB_PATH)
            detail = f"not found in SDE — {', '.join(files)}"
            if sugs:
                detail += f"\n        did you mean: {', '.join(sugs)}"
            results.append(CheckResult("rig_exists", name, "FAIL", detail))
        elif verbose:
            results.append(CheckResult("rig_exists", name, "PASS"))

    # Check 2: rig_type — is the item actually a rig?
    for name in sorted(unique_names):
        info = rig_info[name]
        if info is None:
            continue  # already reported in rig_exists
        if not info.is_rig:
            locs = refs_by_name[name]
            files = sorted({r.file for r in locs})
            sources = sorted({r.source for r in locs})
            results.append(CheckResult(
                "rig_type",
                name,
                "FAIL",
                f"SDE group '{info.group_name}' is not a rig group\n"
                f"        in {', '.join(files)}\n"
                f"        source: {', '.join(sources)}",
            ))
        elif verbose:
            results.append(CheckResult(
                "rig_type", name, "PASS", f"group: {info.group_name}",
            ))

    # Check 3: rig_size — does the rig size match the hull class?
    for name in sorted(unique_names):
        info = rig_info[name]
        if info is None or not info.is_rig:
            continue

        for ref in refs_by_name[name]:
            # Skip faction_tuning entries (hull-agnostic)
            if not ref.hull_class:
                continue

            expected_size = HULL_CLASS_RIG_SIZE.get(ref.hull_class)
            if expected_size is None:
                results.append(CheckResult(
                    "rig_size",
                    f"{name} in {ref.file}",
                    "WARN",
                    f"unknown hull class '{ref.hull_class}' — cannot verify rig size",
                ))
                continue

            if info.size_prefix and info.size_prefix != expected_size:
                results.append(CheckResult(
                    "rig_size",
                    f"{name} in {ref.file}",
                    "FAIL",
                    f"rig is {info.size_prefix} but {ref.hull_class} hulls need {expected_size}",
                ))
            elif verbose:
                results.append(CheckResult(
                    "rig_size",
                    f"{name} in {ref.file}",
                    "PASS",
                    f"{info.size_prefix} rig on {ref.hull_class}",
                ))

    return results


def print_results(results: list[CheckResult], verbose: bool = False) -> None:
    """Print formatted validation report."""
    print()
    print(colored("=== Archetype Rig Validation ===", "BOLD"))
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
        description="Validate archetype rig items against SDE database",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show PASS results too",
    )
    args = parser.parse_args()

    results = run_validation(verbose=args.verbose)
    print_results(results, verbose=args.verbose)

    if any(r.verdict == "FAIL" for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
