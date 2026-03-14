#!/usr/bin/env python3
"""
Validate structural aspects of archetype YAML files.

Checks that archetype files have consistent paths, valid enums, and that
INDEX.md is complete and accurate.

Checks:
    1. hull_path_consistency — hull name matches directory name
    2. skill_tier_enum — skill_tier is a valid value
    3. damage_type_enum — default_damage is a valid damage type
    4. tank_profile_valid — tank_profile matches a known profile
    5. index_paths_resolve — all INDEX.md paths exist on disk
    6. index_completeness — all YAML files appear in INDEX.md

Usage:
    uv run python dev/scripts/validate-archetype-structure.py
    uv run python dev/scripts/validate-archetype-structure.py --verbose

Exit codes:
    0 = all checks pass
    1 = at least one FAIL
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ARCHETYPES_DIR = PROJECT_ROOT / "reference" / "archetypes"
HULLS_DIR = ARCHETYPES_DIR / "hulls"

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
    check: str  # e.g. "hull_path_consistency"
    subject: str
    verdict: str  # PASS / FAIL / WARN / SKIP
    detail: str = ""


# ---------------------------------------------------------------------------
# Valid enums
# ---------------------------------------------------------------------------

VALID_SKILL_TIERS = {"t1", "meta", "t2_budget", "t2_optimal"}
VALID_DAMAGE_TYPES = {
    "kinetic", "thermal", "em", "explosive",
    # Compound types for weapons dealing split damage (e.g. lasers = em_thermal)
    "em_thermal", "kinetic_thermal", "em_kinetic",
    "explosive_kinetic", "explosive_thermal", "em_explosive",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

INDEX_PATH_RE = re.compile(r"`(hulls/[^`]+\.yaml)`")


def load_known_tank_profiles() -> set[str]:
    """Read top-level keys from faction_tuning.yaml as known tank profiles.

    Excludes non-profile keys like drone_types and drone_tech_suffix.
    """
    faction_tuning_path = ARCHETYPES_DIR / "_shared" / "faction_tuning.yaml"
    if not faction_tuning_path.exists():
        return set()
    data = yaml.safe_load(faction_tuning_path.read_text())
    if not data or not isinstance(data, dict):
        return set()
    # Only include keys whose values are dicts of faction entries
    profiles: set[str] = set()
    for key, value in data.items():
        if isinstance(value, dict):
            # Check if it looks like a faction map (values are dicts with modules/drones)
            sample = next(iter(value.values()), None)
            if isinstance(sample, dict):
                profiles.add(key)
    return profiles


def parse_index_paths() -> list[str]:
    """Extract archetype paths from INDEX.md table rows."""
    index_path = ARCHETYPES_DIR / "INDEX.md"
    if not index_path.exists():
        return []
    paths: list[str] = []
    for line in index_path.read_text().splitlines():
        if not line.startswith("|"):
            continue
        m = INDEX_PATH_RE.search(line)
        if m:
            paths.append(m.group(1))
    return paths


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def run_validation(verbose: bool = False) -> list[CheckResult]:
    """Run all structural validation checks."""
    results: list[CheckResult] = []

    # Load known tank profiles at startup
    known_profiles = load_known_tank_profiles()

    # Collect all YAML files under hulls/
    yaml_files = sorted(HULLS_DIR.rglob("*.yaml"))

    if not yaml_files:
        results.append(CheckResult(
            "hull_path_consistency",
            "hulls/",
            "SKIP",
            "no YAML files found under hulls/",
        ))
        return results

    # -----------------------------------------------------------------------
    # Per-file checks
    # -----------------------------------------------------------------------

    for path in yaml_files:
        rel = str(path.relative_to(ARCHETYPES_DIR))
        parts = path.relative_to(HULLS_DIR).parts
        # Path structure: {class}/{ship}/.../*.yaml
        if len(parts) < 2:
            continue
        ship_dir = parts[1]

        data = yaml.safe_load(path.read_text())
        if not data or not isinstance(data, dict):
            continue

        archetype = data.get("archetype", {})
        if not isinstance(archetype, dict):
            continue

        # Check 1: hull_path_consistency
        hull = archetype.get("hull")
        if hull:
            if hull.lower() == ship_dir:
                if verbose:
                    results.append(CheckResult(
                        "hull_path_consistency", rel, "PASS",
                    ))
            else:
                results.append(CheckResult(
                    "hull_path_consistency", rel, "FAIL",
                    f"archetype.hull '{hull}' does not match directory '{ship_dir}'",
                ))

        # Check 2: skill_tier_enum
        skill_tier = archetype.get("skill_tier")
        if skill_tier is not None:
            if skill_tier in VALID_SKILL_TIERS:
                if verbose:
                    results.append(CheckResult(
                        "skill_tier_enum", rel, "PASS", f"skill_tier: {skill_tier}",
                    ))
            else:
                results.append(CheckResult(
                    "skill_tier_enum", rel, "FAIL",
                    f"skill_tier '{skill_tier}' not in {sorted(VALID_SKILL_TIERS)}",
                ))
        else:
            if verbose:
                results.append(CheckResult(
                    "skill_tier_enum", rel, "SKIP", "no skill_tier field",
                ))

        # Check 3: damage_type_enum
        damage_tuning = data.get("damage_tuning", {})
        if isinstance(damage_tuning, dict) and damage_tuning:
            default_damage = damage_tuning.get("default_damage")
            if default_damage is not None:
                if default_damage in VALID_DAMAGE_TYPES:
                    if verbose:
                        results.append(CheckResult(
                            "damage_type_enum", rel, "PASS",
                            f"default_damage: {default_damage}",
                        ))
                else:
                    results.append(CheckResult(
                        "damage_type_enum", rel, "FAIL",
                        f"default_damage '{default_damage}' not in "
                        f"{sorted(VALID_DAMAGE_TYPES)}",
                    ))
            else:
                if verbose:
                    results.append(CheckResult(
                        "damage_type_enum", rel, "SKIP",
                        "no default_damage field",
                    ))

            # Check 4: tank_profile_valid
            tank_profile = damage_tuning.get("tank_profile")
            if tank_profile is not None:
                if not known_profiles:
                    results.append(CheckResult(
                        "tank_profile_valid", rel, "SKIP",
                        "faction_tuning.yaml not found — cannot validate",
                    ))
                elif tank_profile in known_profiles:
                    if verbose:
                        results.append(CheckResult(
                            "tank_profile_valid", rel, "PASS",
                            f"tank_profile: {tank_profile}",
                        ))
                else:
                    results.append(CheckResult(
                        "tank_profile_valid", rel, "WARN",
                        f"tank_profile '{tank_profile}' not in "
                        f"{sorted(known_profiles)}",
                    ))
            else:
                if verbose:
                    results.append(CheckResult(
                        "tank_profile_valid", rel, "SKIP",
                        "no tank_profile field",
                    ))
        else:
            if verbose:
                results.append(CheckResult(
                    "damage_type_enum", rel, "SKIP", "no damage_tuning section",
                ))
                results.append(CheckResult(
                    "tank_profile_valid", rel, "SKIP", "no damage_tuning section",
                ))

    # -----------------------------------------------------------------------
    # Index checks
    # -----------------------------------------------------------------------

    # Check 5: index_paths_resolve
    index_paths = parse_index_paths()
    if not index_paths:
        results.append(CheckResult(
            "index_paths_resolve",
            "INDEX.md",
            "SKIP",
            "no paths found in INDEX.md",
        ))
    else:
        for idx_path in index_paths:
            full = ARCHETYPES_DIR / idx_path
            if full.exists():
                if verbose:
                    results.append(CheckResult(
                        "index_paths_resolve", idx_path, "PASS",
                    ))
            else:
                results.append(CheckResult(
                    "index_paths_resolve", idx_path, "FAIL",
                    "path listed in INDEX.md does not exist on disk",
                ))

    # Check 6: index_completeness
    index_path_set = set(index_paths)
    for path in yaml_files:
        rel_from_archetypes = str(path.relative_to(ARCHETYPES_DIR))
        if rel_from_archetypes in index_path_set:
            if verbose:
                results.append(CheckResult(
                    "index_completeness", rel_from_archetypes, "PASS",
                ))
        else:
            results.append(CheckResult(
                "index_completeness", rel_from_archetypes, "WARN",
                "YAML file not listed in INDEX.md",
            ))

    return results


def print_results(results: list[CheckResult], verbose: bool = False) -> None:
    """Print formatted validation report."""
    print()
    print(colored("=== Archetype Structure Validation ===", "BOLD"))
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
        description="Validate structural aspects of archetype YAML files",
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
