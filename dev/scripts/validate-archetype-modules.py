#!/usr/bin/env python3
"""
Validate item names in archetype YAML files against the SDE database.

Checks that all module, drone, ammo, rig, and hull names used in archetype
fits resolve to real EVE Online type names in the local SDE.

Sources validated:
    - EFT blocks (hull, modules, drones, charges)
    - damage_tuning.overrides (modules, rigs, drones, ammo)
    - upgrade_path.key_upgrades (module, upgrade_to, ship)
    - _shared/module_tiers.yaml (upgrade_paths)

Usage:
    uv run python dev/scripts/validate-archetype-modules.py
    uv run python dev/scripts/validate-archetype-modules.py --verbose

Exit codes:
    0 = all checks pass
    1 = at least one FAIL (unresolved item name)
"""

from __future__ import annotations

import re
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass
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
class ItemReference:
    """A reference to an item name found in a YAML file."""

    name: str
    source: str  # e.g. "eft", "damage_tuning.overrides.serpentis.modules.to"
    file: str  # relative path from archetypes/


@dataclass
class CheckResult:
    check: str  # e.g. "item_name"
    subject: str  # e.g. the item name
    verdict: str  # PASS / FAIL / WARN / SKIP
    detail: str = ""


# ---------------------------------------------------------------------------
# EFT Parsing
# ---------------------------------------------------------------------------

EMPTY_SLOT_RE = re.compile(r"^\[Empty .+ slot\]$")
EFT_HEADER_RE = re.compile(r"^\[(.+?),\s*(.+)\]$")
QUANTITY_RE = re.compile(r"\s+x(\d+)$")


def parse_eft_items(eft_block: str) -> list[tuple[str, str]]:
    """Extract item names from an EFT block.

    Returns list of (item_name, source_label) tuples.
    """
    items: list[tuple[str, str]] = []

    for line in eft_block.strip().splitlines():
        line = line.strip()
        if not line:
            continue

        # Header: [Ship, Fit Name]
        header_m = EFT_HEADER_RE.match(line)
        if header_m:
            items.append((header_m.group(1).strip(), "eft[hull]"))
            continue

        # Empty slots
        if EMPTY_SLOT_RE.match(line):
            continue

        # Strip quantity suffix: "Hobgoblin I x5" -> "Hobgoblin I"
        line = QUANTITY_RE.sub("", line)

        # Handle "Module, Charge" format (e.g. "Sensor Booster I, Scan Resolution Script")
        if ", " in line:
            parts = line.split(", ", 1)
            items.append((parts[0].strip(), "eft"))
            items.append((parts[1].strip(), "eft[charge]"))
        else:
            items.append((line, "eft"))

    return items


# ---------------------------------------------------------------------------
# YAML Item Extraction
# ---------------------------------------------------------------------------


def extract_items_from_yaml(data: dict, rel_path: str) -> list[ItemReference]:
    """Extract all item name references from an archetype YAML."""
    refs: list[ItemReference] = []

    # 1. EFT block
    eft = data.get("eft", "")
    if eft:
        for name, source in parse_eft_items(eft):
            refs.append(ItemReference(name=name, source=source, file=rel_path))

    # 2. damage_tuning.overrides
    dt = data.get("damage_tuning", {})
    if isinstance(dt, dict):
        overrides = dt.get("overrides", {})
        if isinstance(overrides, dict):
            for faction, entry in overrides.items():
                if not isinstance(entry, dict):
                    continue
                prefix = f"overrides.{faction}"

                # modules[].from / to
                for mod in entry.get("modules", []):
                    if isinstance(mod, dict):
                        for key in ("from", "to"):
                            if key in mod:
                                refs.append(ItemReference(
                                    name=mod[key],
                                    source=f"{prefix}.modules.{key}",
                                    file=rel_path,
                                ))

                # rigs[].from / to
                for rig in entry.get("rigs", []):
                    if isinstance(rig, dict):
                        for key in ("from", "to"):
                            if key in rig:
                                refs.append(ItemReference(
                                    name=rig[key],
                                    source=f"{prefix}.rigs.{key}",
                                    file=rel_path,
                                ))

                # drones (dict of role: name)
                drones = entry.get("drones", {})
                if isinstance(drones, dict):
                    for role, drone_name in drones.items():
                        if isinstance(drone_name, str):
                            refs.append(ItemReference(
                                name=drone_name,
                                source=f"{prefix}.drones.{role}",
                                file=rel_path,
                            ))

                # ammo (string)
                ammo = entry.get("ammo")
                if isinstance(ammo, str):
                    refs.append(ItemReference(
                        name=ammo,
                        source=f"{prefix}.ammo",
                        file=rel_path,
                    ))

    # 3. upgrade_path.key_upgrades
    up = data.get("upgrade_path", {})
    if isinstance(up, dict):
        for upgrade in up.get("key_upgrades", []):
            if not isinstance(upgrade, dict):
                continue
            if "module" in upgrade:
                refs.append(ItemReference(
                    name=upgrade["module"],
                    source="upgrade_path.module",
                    file=rel_path,
                ))
            if "upgrade_to" in upgrade:
                refs.append(ItemReference(
                    name=upgrade["upgrade_to"],
                    source="upgrade_path.upgrade_to",
                    file=rel_path,
                ))
            if "ship" in upgrade:
                # Strip parenthetical notes: "Buzzard (Covert Ops)" -> "Buzzard"
                ship = re.sub(r"\s*\(.*\)$", "", upgrade["ship"])
                refs.append(ItemReference(
                    name=ship,
                    source="upgrade_path.ship",
                    file=rel_path,
                ))

    return refs


def extract_items_from_module_tiers(data: dict) -> list[ItemReference]:
    """Extract item names from module_tiers.yaml upgrade_paths."""
    refs: list[ItemReference] = []

    paths = data.get("upgrade_paths", {})
    if isinstance(paths, dict):
        for category, tiers in paths.items():
            if isinstance(tiers, dict):
                for tier, name in tiers.items():
                    if isinstance(name, str):
                        refs.append(ItemReference(
                            name=name,
                            source=f"upgrade_paths.{category}.{tier}",
                            file="_shared/module_tiers.yaml",
                        ))

    return refs


# ---------------------------------------------------------------------------
# SDE Validation
# ---------------------------------------------------------------------------


def validate_names_against_sde(
    names: set[str],
    db_path: Path,
) -> tuple[set[str], dict[str, list[str]]]:
    """Check item names against the SDE types table.

    Returns:
        (found_names, {missing_name: [suggestions]})
    """
    conn = sqlite3.connect(str(db_path))

    # Build lowercase -> original mapping
    lower_to_original: dict[str, str] = {}
    for name in names:
        lower_to_original[name.lower()] = name

    # Batch exact lookup (SQLite variable limit is 999)
    found: set[str] = set()
    batch_size = 500
    lower_keys = list(lower_to_original.keys())

    for i in range(0, len(lower_keys), batch_size):
        batch = lower_keys[i : i + batch_size]
        placeholders = ",".join("?" * len(batch))
        cursor = conn.execute(
            f"SELECT type_name_lower FROM types "
            f"WHERE type_name_lower IN ({placeholders})",
            batch,
        )
        for (lower_name,) in cursor.fetchall():
            found.add(lower_to_original[lower_name])

    missing = names - found

    # Get suggestions for missing names
    suggestions: dict[str, list[str]] = {}
    for name in missing:
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
            # Try matching on significant words
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

        suggestions[name] = sugs

    conn.close()
    return found, suggestions


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def collect_all_references() -> list[ItemReference]:
    """Collect all item name references from archetype YAMLs and shared configs."""
    all_refs: list[ItemReference] = []

    # Archetype YAML files
    for path in sorted(HULLS_DIR.rglob("*.yaml")):
        rel = str(path.relative_to(ARCHETYPES_DIR))
        data = yaml.safe_load(path.read_text())
        if data and isinstance(data, dict):
            all_refs.extend(extract_items_from_yaml(data, rel))

    # Shared module_tiers.yaml
    module_tiers_path = SHARED_DIR / "module_tiers.yaml"
    if module_tiers_path.exists():
        data = yaml.safe_load(module_tiers_path.read_text())
        if data and isinstance(data, dict):
            all_refs.extend(extract_items_from_module_tiers(data))

    return all_refs


def run_validation(verbose: bool = False) -> list[CheckResult]:
    """Run all item name validation checks."""
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

    # Collect all references
    all_refs = collect_all_references()
    unique_names = {ref.name for ref in all_refs}

    results.append(CheckResult(
        "item_count",
        f"{len(unique_names)} unique names across {len(all_refs)} references",
        "PASS",
    ))

    # Validate against SDE
    found, suggestions = validate_names_against_sde(unique_names, DB_PATH)

    # Group references by name for error reporting
    refs_by_name: dict[str, list[ItemReference]] = defaultdict(list)
    for ref in all_refs:
        refs_by_name[ref.name].append(ref)

    # Emit results
    for name in sorted(unique_names):
        if name in found:
            if verbose:
                results.append(CheckResult("item_name", name, "PASS"))
        else:
            locs = refs_by_name[name]
            files = sorted({r.file for r in locs})
            sources = sorted({r.source for r in locs})
            sugs = suggestions.get(name, [])

            detail = f"in {', '.join(files)}\n        source: {', '.join(sources)}"
            if sugs:
                detail += f"\n        did you mean: {', '.join(sugs)}"

            results.append(CheckResult("item_name", name, "FAIL", detail))

    return results


def print_results(results: list[CheckResult], verbose: bool = False) -> None:
    """Print formatted validation report."""
    print()
    print(colored("=== Archetype Module Name Validation ===", "BOLD"))
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
        description="Validate archetype item names against SDE database",
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
