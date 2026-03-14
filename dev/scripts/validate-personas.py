#!/usr/bin/env python3
"""
Validate persona directory structure and overlay coverage.

Checks that all persona directories have required files, valid manifests,
and complete skill overlay coverage for skills that declare
has_persona_overlay in the skill index.

Usage:
    uv run python dev/scripts/validate-personas.py
    uv run python dev/scripts/validate-personas.py --verbose

Exit codes:
    0 = all checks pass
    1 = at least one FAIL
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PERSONAS_DIR = PROJECT_ROOT / "personas"
SKILLS_INDEX = PROJECT_ROOT / ".claude" / "skills" / "_index.json"

# Directories inside personas/ that are not persona directories
EXCLUDED_DIRS = {"_shared"}

# Required keys in manifest.yaml
MANIFEST_REQUIRED_FIELDS = {"name", "subtitle", "directory", "factions", "address", "greeting"}

# Known factions for validation
KNOWN_FACTIONS = {
    "gallente",
    "caldari",
    "minmatar",
    "amarr",
    "pirate",
    "angel_cartel",
    "serpentis",
    "guristas",
    "blood_raiders",
    "sanshas_nation",
}

# Expected shared resource files
SHARED_EXPECTED: dict[str, list[str]] = {
    "empire": ["identity.md", "terminology.md"],
    "pirate": ["identity.md", "terminology.md", "philosophy.md", "the-code.md"],
}

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
    check: str  # e.g. "manifest_exists", "overlay_coverage"
    subject: str
    verdict: str  # PASS / FAIL / WARN / SKIP
    detail: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_persona_dirs() -> list[Path]:
    """Return sorted list of persona directories (excluding _shared and files)."""
    dirs = []
    for entry in sorted(PERSONAS_DIR.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name in EXCLUDED_DIRS:
            continue
        dirs.append(entry)
    return dirs


def load_overlay_skills() -> list[str]:
    """Load skill names where has_persona_overlay is true from _index.json."""
    data = json.loads(SKILLS_INDEX.read_text())
    names = []
    for skill in data.get("skills", []):
        if skill.get("has_persona_overlay"):
            names.append(skill["name"])
    return sorted(names)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def run_validation(verbose: bool = False) -> list[CheckResult]:
    """Run all persona validation checks."""
    results: list[CheckResult] = []
    persona_dirs = get_persona_dirs()

    if not persona_dirs:
        results.append(CheckResult(
            "persona_discovery",
            str(PERSONAS_DIR),
            "SKIP",
            "no persona directories found",
        ))
        return results

    results.append(CheckResult(
        "persona_discovery",
        f"{len(persona_dirs)} personas found",
        "PASS",
    ))

    # ------------------------------------------------------------------
    # Check 1: manifest_exists
    # ------------------------------------------------------------------
    for pdir in persona_dirs:
        manifest_path = pdir / "manifest.yaml"
        if not manifest_path.exists():
            results.append(CheckResult(
                "manifest_exists",
                pdir.name,
                "FAIL",
                "manifest.yaml not found",
            ))
        elif verbose:
            results.append(CheckResult("manifest_exists", pdir.name, "PASS"))

    # ------------------------------------------------------------------
    # Check 2 & 3 & 4: manifest field validation
    # ------------------------------------------------------------------
    for pdir in persona_dirs:
        manifest_path = pdir / "manifest.yaml"
        if not manifest_path.exists():
            continue

        data = yaml.safe_load(manifest_path.read_text())
        if not data or not isinstance(data, dict):
            results.append(CheckResult(
                "manifest_required_fields",
                pdir.name,
                "FAIL",
                "manifest.yaml is empty or not a mapping",
            ))
            continue

        # Check 2: manifest_required_fields
        missing = MANIFEST_REQUIRED_FIELDS - set(data.keys())
        if missing:
            for field in sorted(missing):
                results.append(CheckResult(
                    "manifest_required_fields",
                    f"{pdir.name}.{field}",
                    "FAIL",
                    f"required field '{field}' missing from manifest.yaml",
                ))
        elif verbose:
            results.append(CheckResult(
                "manifest_required_fields",
                pdir.name,
                "PASS",
                "all required fields present",
            ))

        # Check 3: manifest_directory_match
        manifest_dir = data.get("directory")
        if manifest_dir is not None:
            if str(manifest_dir) != pdir.name:
                results.append(CheckResult(
                    "manifest_directory_match",
                    pdir.name,
                    "FAIL",
                    f"manifest.directory is '{manifest_dir}' but actual directory is '{pdir.name}'",
                ))
            elif verbose:
                results.append(CheckResult(
                    "manifest_directory_match",
                    pdir.name,
                    "PASS",
                ))

        # Check 4: manifest_factions_valid
        factions = data.get("factions", [])
        if isinstance(factions, list):
            unknown = [f for f in factions if f not in KNOWN_FACTIONS]
            for faction in unknown:
                results.append(CheckResult(
                    "manifest_factions_valid",
                    f"{pdir.name}.factions",
                    "WARN",
                    f"unknown faction '{faction}'",
                ))
            if not unknown and verbose:
                results.append(CheckResult(
                    "manifest_factions_valid",
                    pdir.name,
                    "PASS",
                    f"factions: {', '.join(factions)}",
                ))

    # ------------------------------------------------------------------
    # Check 5: voice_exists
    # ------------------------------------------------------------------
    for pdir in persona_dirs:
        voice_path = pdir / "voice.md"
        if not voice_path.exists():
            results.append(CheckResult(
                "voice_exists",
                pdir.name,
                "FAIL",
                "voice.md not found",
            ))
        elif verbose:
            results.append(CheckResult("voice_exists", pdir.name, "PASS"))

    # ------------------------------------------------------------------
    # Check 6: overlay_coverage
    # ------------------------------------------------------------------
    if not SKILLS_INDEX.exists():
        results.append(CheckResult(
            "overlay_coverage",
            str(SKILLS_INDEX.relative_to(PROJECT_ROOT)),
            "SKIP",
            "skills _index.json not found",
        ))
    else:
        overlay_skills = load_overlay_skills()

        for pdir in persona_dirs:
            overlays_dir = pdir / "skill-overlays"

            # Collect actual overlay files (excluding .gitkeep)
            actual_overlays: set[str] = set()
            if overlays_dir.is_dir():
                for f in overlays_dir.iterdir():
                    if f.suffix == ".md" and f.name != ".gitkeep":
                        actual_overlays.add(f.stem)

            if actual_overlays:
                # Persona has some overlays — warn about missing ones
                missing = [s for s in overlay_skills if s not in actual_overlays]
                for skill_name in missing:
                    results.append(CheckResult(
                        "overlay_coverage",
                        f"{pdir.name}/{skill_name}",
                        "WARN",
                        f"overlay-requiring skill '{skill_name}' has no overlay in {pdir.name}/skill-overlays/",
                    ))
                covered = [s for s in overlay_skills if s in actual_overlays]
                if verbose:
                    for skill_name in covered:
                        results.append(CheckResult(
                            "overlay_coverage",
                            f"{pdir.name}/{skill_name}",
                            "PASS",
                        ))
            else:
                # No overlays at all — warn about fallback reliance
                results.append(CheckResult(
                    "overlay_coverage",
                    pdir.name,
                    "WARN",
                    "no skill overlays provided — relies entirely on fallback",
                ))

    # ------------------------------------------------------------------
    # Check 7: shared_resources
    # ------------------------------------------------------------------
    shared_dir = PERSONAS_DIR / "_shared"

    for branch, expected_files in sorted(SHARED_EXPECTED.items()):
        branch_dir = shared_dir / branch
        if not branch_dir.is_dir():
            results.append(CheckResult(
                "shared_resources",
                f"_shared/{branch}/",
                "WARN",
                "directory not found",
            ))
            continue

        for filename in expected_files:
            filepath = branch_dir / filename
            if not filepath.exists():
                results.append(CheckResult(
                    "shared_resources",
                    f"_shared/{branch}/{filename}",
                    "WARN",
                    "expected shared resource file missing",
                ))
            elif verbose:
                results.append(CheckResult(
                    "shared_resources",
                    f"_shared/{branch}/{filename}",
                    "PASS",
                ))

    return results


def print_results(results: list[CheckResult], verbose: bool = False) -> None:
    """Print formatted validation report."""
    print()
    print(colored("=== Persona Validation ===", "BOLD"))
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
        description="Validate persona directory structure and overlay coverage",
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
