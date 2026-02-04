#!/usr/bin/env python3
"""
ARIA Skill Index Generator

Scans all SKILL.md files and generates a machine-readable index
at .claude/skills/_index.json for skill discovery and validation.

Usage:
    uv run python .claude/scripts/aria-skill-index.py
    uv run python .claude/scripts/aria-skill-index.py --validate
    uv run python .claude/scripts/aria-skill-index.py --validate --strict
    uv run python .claude/scripts/aria-skill-index.py --validate --report
    uv run python .claude/scripts/aria-skill-index.py --check

Flags:
    --validate  Check skill metadata for completeness (missing fields, etc.)
    --strict    With --validate: exit 1 if any skill missing ADR-002 required fields
    --report    With --validate: output JSON compliance report to stdout
    --check     Verify index is current (exit 1 if stale). Use in CI/pre-commit.
"""

import json
import sys
from pathlib import Path
from typing import Any, Optional


def parse_yaml_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """
    Parse YAML frontmatter from markdown content.

    Returns:
        Tuple of (frontmatter_dict, remaining_content)
    """
    if not content.startswith("---"):
        return {}, content

    # Find the closing ---
    lines = content.split("\n")
    end_idx = None
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return {}, content

    # Parse the YAML-like frontmatter (simple parser, not full YAML)
    frontmatter: dict[str, Any] = {}
    yaml_lines = lines[1:end_idx]

    current_key: Optional[str] = None
    current_list: list[str] = []

    for line in yaml_lines:
        # Skip empty lines
        if not line.strip():
            continue

        # Check for list item (starts with "  - ")
        if line.startswith("  - "):
            if current_key:
                current_list.append(line[4:].strip().strip('"').strip("'"))
            continue

        # Save previous list if we have one
        if current_key and current_list:
            frontmatter[current_key] = current_list
            current_list = []
            current_key = None

        # Parse key: value
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            if value:
                # Convert boolean strings
                if value.lower() == "true":
                    frontmatter[key] = True
                elif value.lower() == "false":
                    frontmatter[key] = False
                elif value == "[]":
                    # Inline empty array
                    frontmatter[key] = []
                else:
                    frontmatter[key] = value
            else:
                # Empty value means list follows
                current_key = key
                current_list = []

    # Don't forget the last list
    if current_key and current_list:
        frontmatter[current_key] = current_list

    remaining = "\n".join(lines[end_idx + 1 :])
    return frontmatter, remaining


def find_persona_overlays(project_root: Path) -> set[str]:
    """
    Scan all personas for skill overlays.

    Returns:
        Set of skill names that have at least one persona overlay
    """
    overlay_skills: set[str] = set()
    personas_dir = project_root / "personas"

    if not personas_dir.exists():
        return overlay_skills

    for persona_dir in personas_dir.iterdir():
        if not persona_dir.is_dir() or persona_dir.name.startswith("_"):
            continue

        overlay_dir = persona_dir / "skill-overlays"
        if overlay_dir.exists():
            for overlay_file in overlay_dir.glob("*.md"):
                # Skip .gitkeep and other non-skill files
                if overlay_file.stem and not overlay_file.stem.startswith("."):
                    overlay_skills.add(overlay_file.stem)

    return overlay_skills


def scan_skills(skills_dir: Path) -> list[dict[str, Any]]:
    """
    Scan all SKILL.md files and extract metadata.

    For persona-exclusive skills (those with 'redirect' field), reads
    metadata from the redirect target to ensure index has complete info.

    Returns:
        List of skill metadata dictionaries
    """
    skills = []
    warnings = []
    project_root = skills_dir.parent.parent

    # Find all skills that have persona overlays
    skills_with_overlays = find_persona_overlays(project_root)

    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        if skill_dir.name.startswith("_"):
            continue

        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            continue

        try:
            content = skill_file.read_text(encoding="utf-8")
            frontmatter, _ = parse_yaml_frontmatter(content)

            if not frontmatter:
                warnings.append(f"  {skill_dir.name}: No frontmatter found")
                continue

            # Validate required fields
            if "name" not in frontmatter:
                warnings.append(f"  {skill_dir.name}: Missing 'name' field")
                frontmatter["name"] = skill_dir.name

            # Handle persona-exclusive skills: read metadata from redirect target
            if "redirect" in frontmatter and "persona_exclusive" in frontmatter:
                redirect_path = project_root / frontmatter["redirect"]
                if redirect_path.exists():
                    redirect_content = redirect_path.read_text(encoding="utf-8")
                    redirect_fm, _ = parse_yaml_frontmatter(redirect_content)

                    if redirect_fm:
                        # Merge redirect metadata, preserving stub's routing fields
                        persona_exclusive = frontmatter["persona_exclusive"]
                        redirect = frontmatter["redirect"]

                        # Copy all fields from redirect (description, triggers, etc.)
                        for key, value in redirect_fm.items():
                            if key not in ("name",):  # Keep name from stub
                                frontmatter[key] = value

                        # Restore routing fields from stub
                        frontmatter["persona_exclusive"] = persona_exclusive
                        frontmatter["redirect"] = redirect
                    else:
                        warnings.append(f"  {skill_dir.name}: Redirect file has no frontmatter")
                else:
                    warnings.append(f"  {skill_dir.name}: Redirect file not found: {redirect_path}")

            if "description" not in frontmatter:
                warnings.append(f"  {skill_dir.name}: Missing 'description' field")

            # Add derived fields
            frontmatter["path"] = str(skill_file.relative_to(project_root))
            frontmatter["directory"] = skill_dir.name

            # Set defaults for optional fields
            frontmatter.setdefault("triggers", [])
            frontmatter.setdefault("requires_pilot", False)
            frontmatter.setdefault("data_sources", [])
            frontmatter.setdefault("external_sources", [])
            frontmatter.setdefault("esi_scopes", [])
            frontmatter.setdefault("category", "general")

            # Check if this skill has persona overlays
            skill_name = frontmatter.get("name", skill_dir.name)
            if skill_name in skills_with_overlays:
                frontmatter["has_persona_overlay"] = True

            skills.append(frontmatter)

        except Exception as e:
            warnings.append(f"  {skill_dir.name}: Error parsing - {e}")

    if warnings:
        print("Warnings:")
        for w in warnings:
            print(w)
        print()

    return skills


def generate_index(skills: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Generate the skill index structure.
    """
    # Group by category
    by_category: dict[str, list[dict[str, Any]]] = {}
    for skill in skills:
        cat = skill.get("category", "general")
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(skill)

    # Build trigger map
    trigger_map: dict[str, str] = {}
    for skill in skills:
        for trigger in skill.get("triggers", []):
            # Normalize trigger for matching
            normalized = trigger.lower().strip()
            if normalized.startswith("/"):
                # Keep command as-is
                trigger_map[normalized] = skill["name"]
            else:
                # Natural language - store for fuzzy matching
                trigger_map[normalized] = skill["name"]

    return {
        "schema_version": "1.0",
        "generated_by": "aria-skill-index.py",
        "skill_count": len(skills),
        "skills": skills,
        "by_category": {
            cat: [s["name"] for s in cat_skills] for cat, cat_skills in sorted(by_category.items())
        },
        "trigger_map": trigger_map,
    }


def validate_skills(skills: list[dict[str, Any]], strict: bool = False) -> tuple[bool, dict]:
    """
    Validate skill metadata for completeness.

    ADR-002 defines:
    - Required fields: name, description
    - Recommended fields: triggers, category, model

    Args:
        skills: List of skill metadata dictionaries
        strict: If True, also fail on missing required fields (ADR-002)

    Returns:
        Tuple of (all_valid, compliance_report)
    """
    all_valid = True
    strict_failures = False

    # ADR-002 field definitions
    REQUIRED_FIELDS = ["name", "description"]
    RECOMMENDED_FIELDS = ["triggers", "category", "model"]

    compliance_report = {
        "total_skills": len(skills),
        "compliant": 0,
        "warnings": 0,
        "failures": 0,
        "skills": [],
    }

    print("Skill Validation Report")
    print("=" * 60)

    for skill in skills:
        name = skill.get("name", "unknown")
        issues = []
        warnings_list = []

        # ADR-002 Required field checks (strict mode failures)
        for field in REQUIRED_FIELDS:
            if not skill.get(field):
                issues.append(f"Missing required field: {field}")

        # ADR-002 Recommended field checks (warnings)
        for field in RECOMMENDED_FIELDS:
            if field == "triggers":
                if not skill.get("triggers"):
                    warnings_list.append("No triggers defined")
            elif field == "category":
                if not skill.get("category") or skill["category"] == "general":
                    warnings_list.append("No category specified (defaulted to 'general')")
            elif field == "model":
                if not skill.get("model"):
                    warnings_list.append("No model specified")

        # Additional semantic checks
        if skill.get("requires_pilot"):
            has_data = bool(skill.get("data_sources"))
            has_esi = bool(skill.get("esi_scopes"))
            if not has_data and not has_esi:
                warnings_list.append("requires_pilot=true but no data_sources or esi_scopes listed")

        # Build skill compliance entry
        skill_entry = {
            "name": name,
            "path": skill.get("path", "unknown"),
            "status": "compliant",
            "missing_required": [],
            "missing_recommended": [],
            "warnings": [],
        }

        if issues:
            strict_failures = True
            all_valid = False
            skill_entry["status"] = "failed"
            skill_entry["missing_required"] = [f.replace("Missing required field: ", "") for f in issues]
            compliance_report["failures"] += 1
            print(f"\n{name}: FAILED")
            for issue in issues:
                print(f"  - [REQUIRED] {issue}")
        elif warnings_list:
            all_valid = False
            skill_entry["status"] = "warning"
            skill_entry["warnings"] = warnings_list
            compliance_report["warnings"] += 1
            print(f"\n{name}: WARNING")
            for w in warnings_list:
                print(f"  - {w}")
        else:
            skill_entry["status"] = "compliant"
            compliance_report["compliant"] += 1
            print(f"\n{name}: OK")

        compliance_report["skills"].append(skill_entry)

    print("\n" + "=" * 60)
    print(f"Summary: {compliance_report['compliant']} compliant, "
          f"{compliance_report['warnings']} warnings, "
          f"{compliance_report['failures']} failures")

    if strict and strict_failures:
        print("\nSTRICT MODE: Failing due to missing required fields (ADR-002)")
        return False, compliance_report

    if all_valid:
        print("All skills pass validation!")
    else:
        print("Some skills need enhancement. See SCHEMA.md for guidance.")

    return not strict_failures if strict else True, compliance_report


def generate_compliance_report(skills: list[dict[str, Any]]) -> dict:
    """
    Generate a JSON compliance report for ADR-002 auditing.

    Returns:
        Dictionary containing detailed compliance information
    """
    _, report = validate_skills(skills, strict=True)
    return report


def check_staleness(index: dict[str, Any], index_file: Path) -> bool:
    """
    Check if the index file is stale (differs from what would be generated).

    Returns:
        True if index is current, False if stale or missing
    """
    if not index_file.exists():
        print(f"Index file missing: {index_file}")
        return False

    try:
        with open(index_file, "r", encoding="utf-8") as f:
            existing = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"Error reading index file: {e}")
        return False

    # Compare by serializing both to JSON (normalizes formatting)
    generated_json = json.dumps(index, indent=2, sort_keys=True)
    existing_json = json.dumps(existing, indent=2, sort_keys=True)

    if generated_json == existing_json:
        return True

    # Find what changed for helpful output
    gen_skills = {s["name"]: s for s in index.get("skills", [])}
    ext_skills = {s["name"]: s for s in existing.get("skills", [])}

    added = set(gen_skills.keys()) - set(ext_skills.keys())
    removed = set(ext_skills.keys()) - set(gen_skills.keys())

    # Check for modified skills
    modified = []
    for name in gen_skills.keys() & ext_skills.keys():
        if json.dumps(gen_skills[name], sort_keys=True) != json.dumps(ext_skills[name], sort_keys=True):
            modified.append(name)

    print("Index is STALE. Differences detected:")
    if added:
        print(f"  Added skills: {', '.join(sorted(added))}")
    if removed:
        print(f"  Removed skills: {', '.join(sorted(removed))}")
    if modified:
        print(f"  Modified skills: {', '.join(sorted(modified))}")
    if not added and not removed and not modified:
        print("  (metadata or trigger map changed)")

    return False


def main():
    # Find project root
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent.parent
    skills_dir = project_root / ".claude" / "skills"

    if not skills_dir.exists():
        print(f"Error: Skills directory not found at {skills_dir}", file=sys.stderr)
        sys.exit(1)

    # Check for report mode early to suppress all output
    report_mode = "--report" in sys.argv

    if not report_mode:
        print(f"Scanning skills in {skills_dir}...")

    # Scan skills (suppress warnings in report mode)
    import io
    if report_mode:
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()

    skills = scan_skills(skills_dir)

    if report_mode:
        sys.stdout = old_stdout
    else:
        print(f"Found {len(skills)} skills\n")

    # Check for validation flag
    if "--validate" in sys.argv:
        strict = "--strict" in sys.argv

        if report_mode:
            # Generate JSON report to stdout (suppress human-readable output)
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            _, report = validate_skills(skills, strict=strict)
            sys.stdout = old_stdout
            print(json.dumps(report, indent=2))
            # Determine exit code based on strict mode
            has_failures = report.get("failures", 0) > 0
            sys.exit(1 if strict and has_failures else 0)
        else:
            valid, _ = validate_skills(skills, strict=strict)
            sys.exit(0 if valid else 1)

    # Generate index
    index = generate_index(skills)
    index_file = skills_dir / "_index.json"

    # Check for staleness check flag
    if "--check" in sys.argv:
        is_current = check_staleness(index, index_file)
        if is_current:
            print("Index is up to date.")
            sys.exit(0)
        else:
            print("\nRun to fix: uv run python .claude/scripts/aria-skill-index.py")
            sys.exit(1)

    # Write index file
    with open(index_file, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)

    print(f"Generated {index_file}")
    print(f"  Skills: {index['skill_count']}")
    print(f"  Categories: {', '.join(index['by_category'].keys())}")
    print(f"  Triggers mapped: {len(index['trigger_map'])}")


if __name__ == "__main__":
    main()
