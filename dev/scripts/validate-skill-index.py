#!/usr/bin/env python3
"""
Validate integrity of .claude/skills/_index.json.

Checks skill count, file paths, trigger uniqueness, frontmatter sync,
field enums, tool format, and ESI scope format.

Usage:
    uv run python dev/scripts/validate-skill-index.py
    uv run python dev/scripts/validate-skill-index.py --verbose

Exit codes:
    0 = all checks pass (warnings are OK)
    1 = at least one FAIL
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

INDEX_PATH = PROJECT_ROOT / ".claude" / "skills" / "_index.json"

# ---------------------------------------------------------------------------
# Valid enums
# ---------------------------------------------------------------------------

VALID_CATEGORIES = {"tactical", "operations", "financial", "identity", "industry", "system"}
VALID_MODELS = {"haiku", "sonnet", "opus"}

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
    check: str  # e.g. "skill_count"
    subject: str  # e.g. "abyssal"
    verdict: str  # PASS / FAIL / WARN / SKIP
    detail: str = ""  # human-readable explanation (empty for PASS)


# ---------------------------------------------------------------------------
# Frontmatter parser (no PyYAML dependency)
# ---------------------------------------------------------------------------


def parse_frontmatter(path: Path) -> dict | None:
    """Parse YAML frontmatter from a SKILL.md file. Returns dict or None."""
    text = path.read_text()
    if not text.startswith("---"):
        return None
    try:
        end = text.index("---", 3)
    except ValueError:
        return None
    fm_text = text[3:end].strip()
    # Parse simple key: value and key:\n  - item lists
    result = {}
    current_key = None
    current_list = None
    for line in fm_text.splitlines():
        if line.startswith("  - "):
            if current_key and current_list is not None:
                current_list.append(line[4:].strip().strip('"').strip("'"))
        elif ":" in line:
            if current_key and current_list is not None:
                result[current_key] = current_list
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if value:
                result[key] = value
                current_key = None
                current_list = None
            else:
                current_key = key
                current_list = []
    if current_key and current_list is not None:
        result[current_key] = current_list
    return result


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def check_skill_count(data: dict) -> list[CheckResult]:
    """Check 1: skill_count field matches len(skills) array."""
    declared = data.get("skill_count", 0)
    actual = len(data.get("skills", []))
    subject = f"declared={declared}, actual={actual}"
    if declared == actual:
        return [CheckResult("skill_count", subject, "PASS")]
    return [CheckResult(
        "skill_count", subject, "FAIL",
        f"skill_count field ({declared}) does not match skills array length ({actual})",
    )]


def check_skill_path_exists(skills: list[dict]) -> list[CheckResult]:
    """Check 2: Each skill's path resolves to an existing file."""
    results: list[CheckResult] = []
    for skill in skills:
        name = skill.get("name", "?")
        path_str = skill.get("path", "")
        subject = f"{name} -> {path_str}"
        if not path_str:
            results.append(CheckResult("skill_path_exists", subject, "FAIL", "No path defined"))
            continue
        full_path = PROJECT_ROOT / path_str
        if full_path.is_file():
            results.append(CheckResult("skill_path_exists", subject, "PASS"))
        else:
            results.append(CheckResult(
                "skill_path_exists", subject, "FAIL",
                f"File not found: {path_str}",
            ))
    return results


def check_skill_directory_exists(skills: list[dict]) -> list[CheckResult]:
    """Check 3: Each skill's directory is a real dir under .claude/skills/."""
    results: list[CheckResult] = []
    for skill in skills:
        name = skill.get("name", "?")
        directory = skill.get("directory", "")
        subject = f"{name} -> {directory}"
        if not directory:
            results.append(CheckResult(
                "skill_directory_exists", subject, "FAIL", "No directory defined",
            ))
            continue
        full_dir = PROJECT_ROOT / ".claude" / "skills" / directory
        if full_dir.is_dir():
            results.append(CheckResult("skill_directory_exists", subject, "PASS"))
        else:
            results.append(CheckResult(
                "skill_directory_exists", subject, "FAIL",
                f"Directory not found: .claude/skills/{directory}",
            ))
    return results


def check_prerequisite_files_exist(skills: list[dict]) -> list[CheckResult]:
    """Check 4: Every non-templated prerequisite_files path must exist."""
    results: list[CheckResult] = []
    for skill in skills:
        name = skill.get("name", "?")
        prereqs = skill.get("prerequisite_files", [])
        if not prereqs:
            continue
        for p in prereqs:
            subject = f"{name} -> {p}"
            if "{" in p:
                results.append(CheckResult(
                    "prerequisite_files_exist", subject, "SKIP",
                    "Template variable in path",
                ))
                continue
            full_path = PROJECT_ROOT / p
            if full_path.is_file():
                results.append(CheckResult("prerequisite_files_exist", subject, "PASS"))
            else:
                results.append(CheckResult(
                    "prerequisite_files_exist", subject, "FAIL",
                    f"File not found: {p}",
                ))
    return results


def check_data_sources_syntax(skills: list[dict]) -> list[CheckResult]:
    """Check 5: Non-templated data_sources paths must exist."""
    results: list[CheckResult] = []
    for skill in skills:
        name = skill.get("name", "?")
        sources = skill.get("data_sources", [])
        if not sources:
            continue
        for s in sources:
            subject = f"{name} -> {s}"
            if "{" in s:
                results.append(CheckResult(
                    "data_sources_syntax", subject, "SKIP",
                    "Template variable in path",
                ))
                continue
            full_path = PROJECT_ROOT / s
            if full_path.is_file():
                results.append(CheckResult("data_sources_syntax", subject, "PASS"))
            else:
                results.append(CheckResult(
                    "data_sources_syntax", subject, "FAIL",
                    f"File not found: {s}",
                ))
    return results


def check_trigger_uniqueness(skills: list[dict]) -> list[CheckResult]:
    """Check 6: No trigger should appear in more than one skill."""
    results: list[CheckResult] = []
    trigger_map: dict[str, list[str]] = defaultdict(list)

    for skill in skills:
        name = skill.get("name", "?")
        triggers = skill.get("triggers", [])
        for t in triggers:
            trigger_map[t.lower()].append(name)

    for trigger, owners in sorted(trigger_map.items()):
        subject = trigger
        if len(owners) > 1:
            results.append(CheckResult(
                "trigger_uniqueness", subject, "FAIL",
                f"Trigger shared by: {', '.join(owners)}",
            ))
        else:
            results.append(CheckResult("trigger_uniqueness", subject, "PASS"))

    return results


def check_frontmatter_sync(skills: list[dict]) -> list[CheckResult]:
    """Check 7: prerequisite_files and injected_prerequisites in SKILL.md frontmatter vs _index.json."""
    results: list[CheckResult] = []

    for skill in skills:
        name = skill.get("name", "?")
        path_str = skill.get("path", "")
        subject = name

        if not path_str:
            results.append(CheckResult(
                "frontmatter_sync", subject, "SKIP", "No path defined",
            ))
            continue

        full_path = PROJECT_ROOT / path_str
        if not full_path.is_file():
            results.append(CheckResult(
                "frontmatter_sync", subject, "SKIP", "SKILL.md not found",
            ))
            continue

        fm = parse_frontmatter(full_path)
        if fm is None:
            results.append(CheckResult(
                "frontmatter_sync", subject, "SKIP", "No frontmatter in SKILL.md",
            ))
            continue

        fm_prereqs = fm.get("prerequisite_files")
        fm_injected = fm.get("injected_prerequisites")

        # Skip if neither field is present in frontmatter
        if fm_prereqs is None and fm_injected is None:
            results.append(CheckResult(
                "frontmatter_sync", subject, "SKIP",
                "No prerequisite_files or injected_prerequisites in frontmatter",
            ))
            continue

        # Check prerequisite_files sync
        if fm_prereqs is not None:
            index_prereqs = skill.get("prerequisite_files", [])
            if sorted(fm_prereqs) != sorted(index_prereqs):
                results.append(CheckResult(
                    "frontmatter_sync", f"{subject}/prerequisite_files", "WARN",
                    f"Frontmatter: {fm_prereqs}, Index: {index_prereqs}",
                ))
            else:
                results.append(CheckResult("frontmatter_sync", f"{subject}/prerequisite_files", "PASS"))

        # Check injected_prerequisites sync
        if fm_injected is not None:
            index_injected = skill.get("injected_prerequisites", [])
            if sorted(fm_injected) != sorted(index_injected):
                results.append(CheckResult(
                    "frontmatter_sync", f"{subject}/injected_prerequisites", "WARN",
                    f"Frontmatter: {fm_injected}, Index: {index_injected}",
                ))
            else:
                results.append(CheckResult("frontmatter_sync", f"{subject}/injected_prerequisites", "PASS"))

        # If only one field present and it matches, still pass
        if fm_prereqs is None and fm_injected is not None:
            pass  # Already handled above
        elif fm_prereqs is not None and fm_injected is None:
            pass  # Already handled above

    return results


def check_category_enum(skills: list[dict]) -> list[CheckResult]:
    """Check 8: category must be one of the valid enum values."""
    results: list[CheckResult] = []
    for skill in skills:
        name = skill.get("name", "?")
        category = skill.get("category", "")
        subject = f"{name} -> {category}"
        if category in VALID_CATEGORIES:
            results.append(CheckResult("category_enum", subject, "PASS"))
        else:
            results.append(CheckResult(
                "category_enum", subject, "FAIL",
                f"Invalid category '{category}'. "
                f"Must be one of: {', '.join(sorted(VALID_CATEGORIES))}",
            ))
    return results


def check_model_enum(skills: list[dict]) -> list[CheckResult]:
    """Check 9: model must be one of the valid enum values."""
    results: list[CheckResult] = []
    for skill in skills:
        name = skill.get("name", "?")
        model = skill.get("model", "")
        subject = f"{name} -> {model}"
        if model in VALID_MODELS:
            results.append(CheckResult("model_enum", subject, "PASS"))
        else:
            results.append(CheckResult(
                "model_enum", subject, "FAIL",
                f"Invalid model '{model}'. "
                f"Must be one of: {', '.join(sorted(VALID_MODELS))}",
            ))
    return results


def check_required_tools_format(skills: list[dict]) -> list[CheckResult]:
    """Check 10: Each required_tools entry must contain a dot (dispatcher.action)."""
    results: list[CheckResult] = []
    for skill in skills:
        name = skill.get("name", "?")
        tools = skill.get("required_tools", [])
        if not tools:
            continue
        for tool in tools:
            subject = f"{name} -> {tool}"
            if "." in tool:
                results.append(CheckResult("required_tools_format", subject, "PASS"))
            else:
                results.append(CheckResult(
                    "required_tools_format", subject, "WARN",
                    f"Expected dispatcher.action format (missing '.'): {tool}",
                ))
    return results


def check_esi_scopes_format(skills: list[dict]) -> list[CheckResult]:
    """Check 11: Each esi_scopes entry must match esi-*.v\\d+ pattern."""
    results: list[CheckResult] = []
    scope_re = re.compile(r"^esi-.+\.v\d+$")
    for skill in skills:
        name = skill.get("name", "?")
        scopes = skill.get("esi_scopes", [])
        if not scopes:
            continue
        for scope in scopes:
            subject = f"{name} -> {scope}"
            if scope_re.match(scope):
                results.append(CheckResult("esi_scopes_format", subject, "PASS"))
            else:
                results.append(CheckResult(
                    "esi_scopes_format", subject, "WARN",
                    f"Does not match expected pattern esi-*.vN: {scope}",
                ))
    return results


def check_injected_prerequisites_exist(skills: list[dict]) -> list[CheckResult]:
    """Check 12: Every path in injected_prerequisites resolves to existing file."""
    results: list[CheckResult] = []
    for skill in skills:
        name = skill.get("name", "?")
        injected = skill.get("injected_prerequisites", [])
        if not injected:
            continue
        for p in injected:
            subject = f"{name} -> {p}"
            full_path = PROJECT_ROOT / p
            if full_path.is_file():
                results.append(CheckResult("injected_prerequisites_exist", subject, "PASS"))
            else:
                results.append(CheckResult(
                    "injected_prerequisites_exist", subject, "FAIL",
                    f"File not found: {p}",
                ))
    return results


def check_injection_presence(skills: list[dict]) -> list[CheckResult]:
    """Check 13: Each injected_prerequisites path has matching !`cat <path>` in SKILL.md."""
    results: list[CheckResult] = []
    for skill in skills:
        name = skill.get("name", "?")
        injected = skill.get("injected_prerequisites", [])
        path_str = skill.get("path", "")
        if not injected or not path_str:
            continue
        full_path = PROJECT_ROOT / path_str
        if not full_path.is_file():
            for p in injected:
                results.append(CheckResult(
                    "injection_presence", f"{name} -> {p}", "SKIP",
                    "SKILL.md not found",
                ))
            continue
        skill_text = full_path.read_text()
        for p in injected:
            subject = f"{name} -> {p}"
            # Match !`cat path` with optional surrounding whitespace
            if f"!`cat {p}`" in skill_text:
                results.append(CheckResult("injection_presence", subject, "PASS"))
            else:
                results.append(CheckResult(
                    "injection_presence", subject, "FAIL",
                    f"No !`cat {p}` found in {path_str}",
                ))
    return results


def check_no_overlap(skills: list[dict]) -> list[CheckResult]:
    """Check 14: No path in both prerequisite_files and injected_prerequisites."""
    results: list[CheckResult] = []
    for skill in skills:
        name = skill.get("name", "?")
        prereqs = set(skill.get("prerequisite_files", []))
        injected = set(skill.get("injected_prerequisites", []))
        overlap = prereqs & injected
        if not prereqs and not injected:
            continue
        if overlap:
            for p in sorted(overlap):
                results.append(CheckResult(
                    "no_overlap", f"{name} -> {p}", "FAIL",
                    f"Path in both prerequisite_files and injected_prerequisites",
                ))
        else:
            results.append(CheckResult("no_overlap", name, "PASS"))
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run_all_checks() -> list[CheckResult]:
    """Run all validation checks and return results."""
    data = json.loads(INDEX_PATH.read_text())
    skills = data.get("skills", [])

    results: list[CheckResult] = []
    results.extend(check_skill_count(data))
    results.extend(check_skill_path_exists(skills))
    results.extend(check_skill_directory_exists(skills))
    results.extend(check_prerequisite_files_exist(skills))
    results.extend(check_data_sources_syntax(skills))
    results.extend(check_trigger_uniqueness(skills))
    results.extend(check_frontmatter_sync(skills))
    results.extend(check_category_enum(skills))
    results.extend(check_model_enum(skills))
    results.extend(check_required_tools_format(skills))
    results.extend(check_esi_scopes_format(skills))
    results.extend(check_injected_prerequisites_exist(skills))
    results.extend(check_injection_presence(skills))
    results.extend(check_no_overlap(skills))
    return results


def print_results(results: list[CheckResult], verbose: bool = False) -> None:
    """Print formatted validation report."""
    print()
    print(colored("=== Skill Index Validation ===", "BOLD"))
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
            print(f"        {r.detail}")

    # Summary
    counts = {"PASS": 0, "FAIL": 0, "WARN": 0, "SKIP": 0}
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


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate ARIA skill index integrity",
    )
    parser.add_argument(
        "--verbose", "-v",
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
