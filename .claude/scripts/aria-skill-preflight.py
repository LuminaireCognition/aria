#!/usr/bin/env python3
"""
ARIA Skill Preflight Validator

Validates skill prerequisites before execution:
- Active pilot (if requires_pilot=true)
- Data sources (files must exist)
- ESI scopes (must be authorized)

Usage:
    uv run python .claude/scripts/aria-skill-preflight.py <skill-name>
    uv run python .claude/scripts/aria-skill-preflight.py --all

Output:
    JSON with validation result:
    {
        "ok": true/false,
        "skill": "skill-name",
        "missing_pilot": true/false,
        "missing_sources": ["path1", "path2"],
        "missing_scopes": ["scope1", "scope2"],
        "warnings": ["optional warnings"]
    }

Exit codes:
    0: Preflight passed
    1: Preflight failed (missing requirements)
    2: Skill not found or other error
"""

import json
import sys
from pathlib import Path
from typing import Any, Optional


def find_project_root() -> Path:
    """Find project root by walking up from script location."""
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / "userdata").is_dir() or (current / ".claude").is_dir():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    # Default to two levels up from script
    return Path(__file__).resolve().parents[2]


def load_skill_index(root: Path) -> dict[str, Any]:
    """Load the skill index file."""
    index_path = root / ".claude" / "skills" / "_index.json"
    if not index_path.exists():
        return {"skills": [], "error": f"Index not found: {index_path}"}
    return json.loads(index_path.read_text(encoding="utf-8"))


def get_skill_by_name(index: dict[str, Any], name: str) -> Optional[dict[str, Any]]:
    """Look up a skill by name."""
    for skill in index.get("skills", []):
        if skill.get("name") == name:
            return skill
    return None


def resolve_active_pilot(root: Path) -> tuple[Optional[str], Optional[str]]:
    """
    Resolve the active pilot directory.

    Returns:
        Tuple of (character_id, directory_name) or (None, None)
    """
    # Read config to get active_pilot
    config_path = root / "userdata" / "config.json"
    if not config_path.exists():
        # Try legacy path
        config_path = root / ".aria-config.json"

    active_pilot_id = None
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            active_pilot_id = config.get("active_pilot")
        except (json.JSONDecodeError, OSError):
            pass

    if not active_pilot_id:
        return None, None

    # Read registry to get directory
    registry_path = root / "userdata" / "pilots" / "_registry.json"
    if not registry_path.exists():
        # Try legacy path
        registry_path = root / "pilots" / "_registry.json"

    if registry_path.exists():
        try:
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            for pilot in registry.get("pilots", []):
                if str(pilot.get("character_id")) == str(active_pilot_id):
                    return active_pilot_id, pilot.get("directory")
        except (json.JSONDecodeError, OSError):
            pass

    return active_pilot_id, None


def load_pilot_scopes(root: Path, character_id: str) -> list[str]:
    """
    Load ESI scopes from pilot credentials.

    Checks credentials file for the scope list.
    """
    # Check new structure first
    creds_path = root / "userdata" / "credentials" / f"{character_id}.json"
    if not creds_path.exists():
        # Try legacy path
        creds_path = root / "credentials" / f"{character_id}.json"

    if not creds_path.exists():
        return []

    try:
        creds = json.loads(creds_path.read_text(encoding="utf-8"))
        return creds.get("scopes", [])
    except (json.JSONDecodeError, OSError):
        return []


# Byte limits for data source validation (RAG/chunking Phase 1)
# Large files may exceed LLM context limits and need future chunking infrastructure
MAX_DATA_SOURCE_BYTES = 50000   # 50KB per individual source
MAX_TOTAL_BYTES = 100000        # 100KB total across all sources


def expand_data_source(source: str, active_pilot_dir: Optional[str]) -> str:
    """Expand template variables in data source paths."""
    if active_pilot_dir:
        return source.replace("{active_pilot}", active_pilot_dir)
    return source


def validate_data_source_sizes(
    root: Path,
    data_sources: list[str],
    pilot_dir: Optional[str],
) -> dict[str, Any]:
    """
    Validate data source file sizes against byte limits.

    Args:
        root: Project root path
        data_sources: List of data source paths from skill metadata
        pilot_dir: Active pilot directory (for path expansion)

    Returns:
        Dict with size validation results:
        - total_bytes: Sum of all source sizes
        - oversized_sources: List of {path, bytes, limit} for sources exceeding limit
        - exceeds_total: True if total exceeds MAX_TOTAL_BYTES
        - warnings: Human-readable warning messages
    """
    result: dict[str, Any] = {
        "total_bytes": 0,
        "oversized_sources": [],
        "exceeds_total": False,
        "warnings": [],
    }

    for source in data_sources:
        # Skip wildcard patterns
        if "*" in source:
            continue

        expanded = expand_data_source(source, pilot_dir)
        source_path = root / expanded

        if not source_path.exists():
            # Skip missing files - handled by main validation
            continue

        try:
            size = source_path.stat().st_size
            result["total_bytes"] += size

            if size > MAX_DATA_SOURCE_BYTES:
                result["oversized_sources"].append({
                    "path": expanded,
                    "bytes": size,
                    "limit": MAX_DATA_SOURCE_BYTES,
                })
                result["warnings"].append(
                    f"Data source '{expanded}' is {size:,} bytes "
                    f"(exceeds {MAX_DATA_SOURCE_BYTES:,} byte limit)"
                )
        except OSError:
            # Can't stat the file - skip
            continue

    if result["total_bytes"] > MAX_TOTAL_BYTES:
        result["exceeds_total"] = True
        result["warnings"].append(
            f"Total data source size is {result['total_bytes']:,} bytes "
            f"(exceeds {MAX_TOTAL_BYTES:,} byte limit)"
        )

    return result


def validate_skill(
    root: Path,
    skill: dict[str, Any],
    character_id: Optional[str],
    pilot_dir: Optional[str],
    pilot_scopes: list[str],
) -> dict[str, Any]:
    """
    Validate a single skill's prerequisites.

    Returns validation result dict.
    """
    result: dict[str, Any] = {
        "ok": True,
        "skill": skill.get("name", "unknown"),
        "missing_pilot": False,
        "missing_sources": [],
        "missing_scopes": [],
        "oversized_sources": [],
        "warnings": [],
    }

    requires_pilot = skill.get("requires_pilot", False)
    data_sources = skill.get("data_sources", [])
    esi_scopes = skill.get("esi_scopes", [])

    # Check pilot requirement
    if requires_pilot and not character_id:
        result["ok"] = False
        result["missing_pilot"] = True
        result["warnings"].append("Skill requires authenticated pilot but none is active")

    # Check data sources
    for source in data_sources:
        # Skip wildcard patterns (e.g., reference/ships/fittings/*.md)
        if "*" in source:
            continue

        expanded = expand_data_source(source, pilot_dir)
        source_path = root / expanded

        if not source_path.exists():
            # Distinguish between pilot-specific and reference data
            if "{active_pilot}" in source and not pilot_dir:
                # Can't check without pilot - already flagged above
                continue
            result["missing_sources"].append(expanded)

    if result["missing_sources"]:
        result["ok"] = False

    # Check data source sizes (RAG/chunking Phase 1)
    size_validation = validate_data_source_sizes(root, data_sources, pilot_dir)
    if size_validation["oversized_sources"]:
        result["oversized_sources"] = size_validation["oversized_sources"]
        result["warnings"].extend(size_validation["warnings"])
        # Note: oversized sources are warnings, not failures
        # Future: consider failing if total exceeds limit significantly

    # Check ESI scopes
    # Handle case where esi_scopes might be a string "[]" instead of list
    if isinstance(esi_scopes, str):
        try:
            esi_scopes = json.loads(esi_scopes)
        except json.JSONDecodeError:
            esi_scopes = []

    for scope in esi_scopes:
        if scope not in pilot_scopes:
            result["missing_scopes"].append(scope)

    if result["missing_scopes"]:
        result["ok"] = False
        if not pilot_scopes and character_id:
            result["warnings"].append("No scopes found in credentials - token may need refresh")

    # Clean up empty fields
    if not result["warnings"]:
        del result["warnings"]
    if not result["oversized_sources"]:
        del result["oversized_sources"]

    return result


def validate_all_skills(root: Path, index: dict[str, Any]) -> dict[str, Any]:
    """Validate all skills and return summary."""
    character_id, pilot_dir = resolve_active_pilot(root)
    pilot_scopes = load_pilot_scopes(root, character_id) if character_id else []

    results = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "skills": [],
        "pilot_status": {
            "active": character_id is not None,
            "character_id": character_id,
            "directory": pilot_dir,
            "scope_count": len(pilot_scopes),
        },
    }

    for skill in index.get("skills", []):
        result = validate_skill(root, skill, character_id, pilot_dir, pilot_scopes)
        results["total"] += 1
        if result["ok"]:
            results["passed"] += 1
        else:
            results["failed"] += 1
            # Only include failed skills in detail output
            results["skills"].append(result)

    return results


def main() -> int:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: aria-skill-preflight.py <skill-name>", file=sys.stderr)
        print("       aria-skill-preflight.py --all", file=sys.stderr)
        return 2

    root = find_project_root()
    index = load_skill_index(root)

    if "error" in index:
        print(json.dumps({"ok": False, "error": index["error"]}))
        return 2

    # Handle --all flag
    if sys.argv[1] == "--all":
        result = validate_all_skills(root, index)
        print(json.dumps(result, indent=2))
        return 0 if result["failed"] == 0 else 1

    # Single skill validation
    skill_name = sys.argv[1]

    # Strip leading slash if present (e.g., /mission-brief -> mission-brief)
    if skill_name.startswith("/"):
        skill_name = skill_name[1:]

    skill = get_skill_by_name(index, skill_name)
    if not skill:
        print(json.dumps({"ok": False, "error": f"Skill not found: {skill_name}"}))
        return 2

    # Resolve pilot context
    character_id, pilot_dir = resolve_active_pilot(root)
    pilot_scopes = load_pilot_scopes(root, character_id) if character_id else []

    # Validate
    result = validate_skill(root, skill, character_id, pilot_dir, pilot_scopes)
    print(json.dumps(result, indent=2))

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
