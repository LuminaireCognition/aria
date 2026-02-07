"""
ARIA Persona Context Commands

Pre-compute persona loading context for pilot profiles.
Removes runtime conditional evaluation from the LLM.

Includes validation to detect stale or missing overlay dependencies.

Security: Path validation centralized in core.path_security per
dev/reviews/PYTHON_REVIEW_2026-01.md P0 #2
"""

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml

from ..core import get_pilot_directory, get_utc_timestamp
from ..core.path_security import (
    ALLOWED_EXTENSIONS,
    validate_persona_file_path,
    validate_persona_path as validate_safe_path,
)
from ..persona.compiler import compile_persona_context, verify_persona_artifact

# =============================================================================
# Faction-to-Persona Mapping
# =============================================================================

FACTION_PERSONA_MAP = {
    # Empire branch
    "gallente": {"persona": "aria-mk4", "branch": "empire", "fallback": None},
    "caldari": {"persona": "aura-c", "branch": "empire", "fallback": None},
    "minmatar": {"persona": "vind", "branch": "empire", "fallback": None},
    "amarr": {"persona": "throne", "branch": "empire", "fallback": None},
    # Pirate branch
    "pirate": {"persona": "paria", "branch": "pirate", "fallback": None},
    "angel_cartel": {"persona": "paria-a", "branch": "pirate", "fallback": "paria"},
    "serpentis": {"persona": "paria-s", "branch": "pirate", "fallback": "paria"},
    "guristas": {"persona": "paria-g", "branch": "pirate", "fallback": "paria"},
    "blood_raiders": {"persona": "paria-b", "branch": "pirate", "fallback": "paria"},
    "sanshas_nation": {"persona": "paria-n", "branch": "pirate", "fallback": "paria"},
}

# Default faction when missing or invalid
DEFAULT_FACTION = "gallente"

# Valid RP levels
VALID_RP_LEVELS = {"off", "on", "full"}

# Migration map for old RP levels
RP_LEVEL_MIGRATION = {
    "lite": "off",
    "moderate": "on",
}


# =============================================================================
# File Lists by RP Level and Branch
# =============================================================================


def get_files_for_context(
    branch: str,
    persona: str,
    rp_level: str,
    persona_dir_exists: bool,
    base_path: Path | None = None,
) -> list[str]:
    """
    Build the file list based on branch, persona, and RP level.

    Only includes files that actually exist, enabling phased rollout of shared content.

    Args:
        branch: 'empire' or 'pirate'
        persona: Persona directory name (e.g., 'aria-mk4', 'paria')
        rp_level: 'off', 'on', or 'full'
        persona_dir_exists: Whether the persona directory exists
        base_path: Project root path for checking file existence (defaults to cwd)

    Returns:
        List of file paths to load (only existing files)
    """
    if rp_level == "off":
        return []

    if base_path is None:
        base_path = Path.cwd()

    files = []

    def add_if_exists(relative_path: str) -> None:
        """Add file to list if it exists."""
        if (base_path / relative_path).exists():
            files.append(relative_path)

    # Branch shared files - only add files that exist (supports phased rollout)
    # Phase 1: identity.md only
    # Phase 2: terminology.md, the-code.md, intel-*.md
    if branch == "empire":
        add_if_exists(f"personas/_shared/{branch}/identity.md")
        add_if_exists(f"personas/_shared/{branch}/terminology.md")
        if rp_level == "full":
            add_if_exists(f"personas/_shared/{branch}/intel-universal.md")
    elif branch == "pirate":
        add_if_exists(f"personas/_shared/{branch}/identity.md")
        add_if_exists(f"personas/_shared/{branch}/terminology.md")
        add_if_exists(f"personas/_shared/{branch}/the-code.md")
        if rp_level == "full":
            add_if_exists(f"personas/_shared/{branch}/intel-underworld.md")

    # Persona-specific files
    if persona_dir_exists:
        add_if_exists(f"personas/{persona}/manifest.yaml")
        add_if_exists(f"personas/{persona}/voice.md")
        if rp_level == "full":
            add_if_exists(f"personas/{persona}/intel-sources.md")

    return files


# =============================================================================
# Profile Parsing
# =============================================================================


def extract_profile_field(content: str, field: str) -> str | None:
    """
    Extract a field value from profile markdown.

    Handles formats:
    - **Field Name:** value
    - - **Field Name:** value

    Args:
        content: Profile markdown content
        field: Field name to extract (case-insensitive)

    Returns:
        Field value or None if not found
    """
    # Pattern: optional bullet, **Field:**, value
    pattern = rf"[-*]?\s*\*\*{re.escape(field)}:\*\*\s*(.+)"
    match = re.search(pattern, content, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def build_persona_context(
    faction: str,
    rp_level: str,
    base_path: Path,
    persona_override: str | None = None,
) -> dict:
    """
    Build the persona_context dictionary.

    Args:
        faction: Faction from profile (e.g., 'pirate', 'gallente')
        rp_level: RP level from profile ('off', 'on', 'full')
        base_path: Project root path for checking directory existence
        persona_override: Optional persona name from profile's Persona: field.
            If provided, loads persona manifest directly instead of using
            faction-based selection.

    Returns:
        persona_context dictionary
    """
    import logging

    # Normalize faction
    faction_lower = faction.lower().strip() if faction else DEFAULT_FACTION
    if faction_lower not in FACTION_PERSONA_MAP:
        faction_lower = DEFAULT_FACTION

    # Migrate old RP levels
    rp_level = rp_level.lower().strip() if rp_level else "off"
    rp_level = RP_LEVEL_MIGRATION.get(rp_level, rp_level)
    if rp_level not in VALID_RP_LEVELS:
        rp_level = "off"

    # Handle persona override (manual selection via Persona: field)
    unrestricted_skills = False
    if persona_override:
        manifest_path = base_path / "personas" / persona_override / "manifest.yaml"
        if manifest_path.exists():
            manifest = yaml.safe_load(manifest_path.read_text())
            persona = persona_override
            branch = manifest.get("branch", "empire")
            fallback = manifest.get("fallback")
            unrestricted_skills = manifest.get("unrestricted_skills", False)
        else:
            # Warn and fall back to faction-based selection
            logging.warning(
                f"Persona '{persona_override}' not found, using faction-based selection"
            )
            persona_override = None

    if not persona_override:
        # Faction-based selection (default behavior)
        info = FACTION_PERSONA_MAP[faction_lower]
        persona = info["persona"]
        branch = info["branch"]
        fallback = info["fallback"]

    # Check if persona directory exists
    persona_dir = base_path / "personas" / persona
    persona_dir_exists = persona_dir.exists()

    # If persona doesn't exist but fallback does, use fallback
    effective_persona = persona
    if not persona_dir_exists and fallback:
        fallback_dir = base_path / "personas" / fallback
        if fallback_dir.exists():
            effective_persona = fallback
            persona_dir_exists = True

    # Build file list
    files = get_files_for_context(
        branch, effective_persona, rp_level, persona_dir_exists, base_path
    )

    # Build context
    context = {
        "branch": branch,
        "persona": effective_persona,
        "fallback": fallback if persona != effective_persona else None,
        "rp_level": rp_level,
        "files": files,
        "skill_overlay_path": f"personas/{effective_persona}/skill-overlays",
        "overlay_fallback_path": (
            f"personas/{fallback}/skill-overlays"
            if fallback and persona != effective_persona
            else None
        ),
        "unrestricted_skills": unrestricted_skills,
    }

    return context


def update_profile_with_context(profile_path: Path, context: dict) -> str:
    """
    Update profile.md with the new persona_context section.

    Args:
        profile_path: Path to profile.md
        context: persona_context dictionary

    Returns:
        Updated profile content
    """
    content = profile_path.read_text()

    # Build YAML block
    yaml_lines = ["persona_context:"]
    yaml_lines.append(f"  branch: {context['branch']}")
    yaml_lines.append(f"  persona: {context['persona']}")
    yaml_lines.append(f"  fallback: {context['fallback'] if context['fallback'] else 'null'}")
    # Quote rp_level to prevent YAML parsing 'on'/'off' as booleans
    yaml_lines.append(f'  rp_level: "{context["rp_level"]}"')

    yaml_lines.append("  files:")
    if context["files"]:
        for f in context["files"]:
            yaml_lines.append(f"    - {f}")
    else:
        yaml_lines.append("    []")

    yaml_lines.append(f"  skill_overlay_path: {context['skill_overlay_path']}")
    overlay_fallback = context["overlay_fallback_path"]
    yaml_lines.append(
        f"  overlay_fallback_path: {overlay_fallback if overlay_fallback else 'null'}"
    )
    # Only include unrestricted_skills if true (dev/debug personas)
    if context.get("unrestricted_skills"):
        yaml_lines.append("  unrestricted_skills: true")

    yaml_block = "\n".join(yaml_lines)

    # Check if Persona Context section already exists
    persona_context_pattern = r"## Persona Context\n<!-- Pre-computed.*?-->\n<!-- Regenerate.*?-->\n\n```yaml\npersona_context:.*?```"

    if re.search(persona_context_pattern, content, re.DOTALL):
        # Replace existing section
        replacement = f"""## Persona Context
<!-- Pre-computed by: uv run aria-esi persona-context -->
<!-- Regenerate when faction or rp_level changes -->

```yaml
{yaml_block}
```"""
        content = re.sub(persona_context_pattern, replacement, content, flags=re.DOTALL)
    else:
        # Insert after Faction Alignment section
        faction_section_pattern = r"(## Faction Alignment\n\n- \*\*Primary Faction:\*\* [^\n]+)"
        match = re.search(faction_section_pattern, content)
        if match:
            insert_point = match.end()
            new_section = f"""

## Persona Context
<!-- Pre-computed by: uv run aria-esi persona-context -->
<!-- Regenerate when faction or rp_level changes -->

```yaml
{yaml_block}
```"""
            content = content[:insert_point] + new_section + content[insert_point:]
        else:
            # Fallback: append to end
            content += f"""

## Persona Context
<!-- Pre-computed by: uv run aria-esi persona-context -->
<!-- Regenerate when faction or rp_level changes -->

```yaml
{yaml_block}
```
"""

    return content


# =============================================================================
# Command Implementation
# =============================================================================


def cmd_persona_context(args: argparse.Namespace) -> dict:
    """
    Regenerate persona_context in pilot profile(s).

    Args:
        args: Parsed arguments with --pilot or --all

    Returns:
        Result dict with status and updated context(s)
    """
    query_ts = get_utc_timestamp()
    base_path = Path.cwd()

    # Determine which pilots to process
    pilots_to_process = []

    if getattr(args, "all", False):
        # Process all pilots from registry
        registry_path = base_path / "userdata" / "pilots" / "_registry.json"
        if registry_path.exists():
            registry = json.loads(registry_path.read_text())
            for pilot in registry.get("pilots", []):
                pilot_dir = base_path / "userdata" / "pilots" / pilot["directory"]
                if pilot_dir.exists():
                    pilots_to_process.append(
                        {
                            "id": pilot["character_id"],
                            "directory": pilot["directory"],
                            "path": pilot_dir,
                        }
                    )
    else:
        # Process single pilot (active or specified)
        pilot_id = getattr(args, "pilot", None)
        try:
            pilot_dir = get_pilot_directory(pilot_id)
            if pilot_dir:
                pilots_to_process.append(
                    {"id": pilot_id or "active", "directory": pilot_dir.name, "path": pilot_dir}
                )
        except Exception as e:
            return {
                "query_timestamp": query_ts,
                "status": "error",
                "message": f"Failed to resolve pilot: {e}",
            }

    if not pilots_to_process:
        return {
            "query_timestamp": query_ts,
            "status": "error",
            "message": "No pilots found to process",
        }

    # Process each pilot
    results = []
    for pilot in pilots_to_process:
        profile_path = pilot["path"] / "profile.md"
        if not profile_path.exists():
            results.append(
                {
                    "pilot_id": pilot["id"],
                    "status": "error",
                    "message": f"Profile not found: {profile_path}",
                }
            )
            continue

        # Read profile
        content = profile_path.read_text()

        # Extract faction, rp_level, and optional persona override
        faction = extract_profile_field(content, "Primary Faction")
        rp_level = extract_profile_field(content, "RP Level")
        persona_override = extract_profile_field(content, "Persona")

        if not faction:
            faction = DEFAULT_FACTION

        if not rp_level:
            rp_level = "off"

        # Build context (persona_override takes precedence over faction-based selection)
        context = build_persona_context(faction, rp_level, base_path, persona_override)

        # Update profile and compile context
        compiled_artifact_path = None
        if not getattr(args, "dry_run", False):
            updated_content = update_profile_with_context(profile_path, context)
            profile_path.write_text(updated_content)

            # Compile persona context with untrusted-data wrapping
            compiled_artifact_path = pilot["path"] / ".persona-context-compiled.json"
            compile_persona_context(
                persona_context=context,
                base_path=base_path,
                output_path=compiled_artifact_path,
            )

        results.append(
            {
                "pilot_id": pilot["id"],
                "directory": pilot["directory"],
                "status": "success",
                "faction": faction,
                "rp_level": rp_level,
                "persona_context": context,
                "compiled_artifact": str(compiled_artifact_path)
                if compiled_artifact_path
                else None,
            }
        )

    # SEC-002: Validate skill redirects at compile time
    redirect_issues = validate_skill_redirects(base_path)
    if redirect_issues:
        import logging

        for issue in redirect_issues:
            if issue["severity"] == "error":
                logging.warning(
                    "SEC-002: Unsafe redirect path in _index.json: %s -> %s (%s)",
                    issue["skill"],
                    issue["path"],
                    issue["error"],
                )
            else:
                logging.info(
                    "SEC-002: Missing redirect in _index.json: %s -> %s",
                    issue["skill"],
                    issue["path"],
                )

    return {
        "query_timestamp": query_ts,
        "status": "success",
        "pilots_processed": len(results),
        "results": results,
        "redirect_validation": {
            "issues": redirect_issues,
            "valid": len([i for i in redirect_issues if i["severity"] == "error"]) == 0,
        },
    }


# =============================================================================
# Overlay Validation
# =============================================================================


def extract_persona_context_from_profile(content: str) -> dict | None:
    """
    Extract persona_context YAML block from profile markdown.

    Args:
        content: Profile markdown content

    Returns:
        Parsed persona_context dict or None if not found
    """
    # Match the YAML code block containing persona_context
    pattern = r"```yaml\n(persona_context:.*?)```"
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        return None

    try:
        parsed = yaml.safe_load(match.group(1))
        return parsed.get("persona_context") if parsed else None
    except yaml.YAMLError:
        return None


def load_skill_index(base_path: Path) -> dict | None:
    """
    Load the skill index.

    Args:
        base_path: Project root path

    Returns:
        Skill index dict or None if not found
    """
    index_path = base_path / ".claude" / "skills" / "_index.json"
    if not index_path.exists():
        return None

    try:
        return json.loads(index_path.read_text())
    except json.JSONDecodeError:
        return None


def validate_skill_redirects(base_path: Path) -> list[dict]:
    """
    Validate all redirect paths in _index.json at compile time.

    SEC-002: Ensures that skill redirects point to valid, safe paths
    before they can be used at runtime.

    Args:
        base_path: Project root path

    Returns:
        List of validation issues (empty if all valid)
    """
    issues = []

    skill_index = load_skill_index(base_path)
    if not skill_index:
        return issues  # No index to validate

    skills = skill_index.get("skills", [])

    for skill in skills:
        skill_name = skill.get("name", "<unnamed>")

        # Validate redirect paths for persona-exclusive skills
        redirect_path = skill.get("redirect")
        if redirect_path:
            is_safe, error = validate_persona_file_path(redirect_path, base_path)
            if not is_safe:
                issues.append(
                    {
                        "type": "unsafe_redirect",
                        "skill": skill_name,
                        "path": redirect_path,
                        "error": error,
                        "severity": "error",
                    }
                )
            elif not (base_path / redirect_path).exists():
                issues.append(
                    {
                        "type": "missing_redirect",
                        "skill": skill_name,
                        "path": redirect_path,
                        "error": f"Redirect file not found: {redirect_path}",
                        "severity": "warning",
                    }
                )

        # Validate overlay path patterns (these are directory prefixes)
        # The actual overlay files are validated during validate_persona_context

    return issues


def normalize_rp_level(value: Any) -> str:
    """
    Normalize rp_level value, handling YAML boolean parsing.

    YAML 1.1 parses 'on'/'off' as True/False booleans. This normalizes
    those back to string values.

    Args:
        value: The rp_level value (may be str, bool, or None)

    Returns:
        Normalized string: 'on', 'off', or 'full'
    """
    if value is True:
        return "on"
    if value is False:
        return "off"
    if isinstance(value, str):
        return value.lower().strip()
    return "off"


def detect_staleness(
    persona_context: dict,
    current_faction: str,
    current_rp_level: str,
    base_path: Path,
    persona_override: str | None = None,
) -> dict[str, Any]:
    """
    Detect if persona_context is stale (out of sync with profile settings).

    Staleness occurs when:
    - User changes faction in profile without regenerating persona_context
    - User changes rp_level without regenerating persona_context
    - User changes persona override without regenerating persona_context
    - Persona files have been reorganized

    Args:
        persona_context: The persona_context from profile
        current_faction: Current faction value from profile
        current_rp_level: Current rp_level value from profile
        base_path: Project root path
        persona_override: Optional persona name from profile's Persona: field

    Returns:
        Staleness detection result with discrepancies
    """
    # Compute what persona_context SHOULD be (accounting for persona override)
    expected = build_persona_context(current_faction, current_rp_level, base_path, persona_override)

    # Normalize rp_level in persona_context (handles YAML boolean parsing)
    context_rp_level = normalize_rp_level(persona_context.get("rp_level"))

    discrepancies = []

    # Check persona mismatch (most critical - wrong persona loaded)
    if persona_context.get("persona") != expected["persona"]:
        discrepancies.append(
            {
                "field": "persona",
                "current": persona_context.get("persona"),
                "expected": expected["persona"],
                "message": f"Persona mismatch: profile has faction '{current_faction}' "
                f"which maps to '{expected['persona']}', but persona_context "
                f"has '{persona_context.get('persona')}'",
            }
        )

    # Check branch mismatch
    if persona_context.get("branch") != expected["branch"]:
        discrepancies.append(
            {
                "field": "branch",
                "current": persona_context.get("branch"),
                "expected": expected["branch"],
                "message": f"Branch mismatch: expected '{expected['branch']}' "
                f"but found '{persona_context.get('branch')}'",
            }
        )

    # Check rp_level mismatch (using normalized value)
    if context_rp_level != expected["rp_level"]:
        discrepancies.append(
            {
                "field": "rp_level",
                "current": context_rp_level,
                "expected": expected["rp_level"],
                "message": f"RP level mismatch: profile has '{current_rp_level}' "
                f"but persona_context has '{context_rp_level}'",
            }
        )

    # Check file list mismatch (could indicate reorganization or rp_level change)
    current_files = set(persona_context.get("files", []))
    expected_files = set(expected["files"])

    if current_files != expected_files:
        missing_files = expected_files - current_files
        extra_files = current_files - expected_files

        if missing_files or extra_files:
            discrepancies.append(
                {
                    "field": "files",
                    "missing": list(missing_files),
                    "extra": list(extra_files),
                    "message": "File list mismatch - persona_context may be stale",
                }
            )

    # Check overlay path mismatch
    if persona_context.get("skill_overlay_path") != expected["skill_overlay_path"]:
        discrepancies.append(
            {
                "field": "skill_overlay_path",
                "current": persona_context.get("skill_overlay_path"),
                "expected": expected["skill_overlay_path"],
                "message": f"Skill overlay path mismatch: expected "
                f"'{expected['skill_overlay_path']}' but found "
                f"'{persona_context.get('skill_overlay_path')}'",
            }
        )

    return {
        "stale": len(discrepancies) > 0,
        "discrepancies": discrepancies,
        "current_settings": {
            "faction": current_faction,
            "rp_level": current_rp_level,
        },
        "fix": "Run 'uv run aria-esi persona-context' to regenerate" if discrepancies else None,
    }


def validate_persona_context(
    persona_context: dict,
    skill_index: dict,
    base_path: Path,
    staleness_result: dict | None = None,
) -> dict[str, Any]:
    """
    Validate persona context paths and overlay dependencies.

    Args:
        persona_context: The persona_context from profile
        skill_index: The skill index
        base_path: Project root path
        staleness_result: Optional staleness detection result to include

    Returns:
        Validation result with issues categorized by severity
    """
    issues: dict[str, list[dict]] = {
        "errors": [],  # Missing critical files (persona files, exclusive skill redirects)
        "warnings": [],  # Missing optional files (overlays that degrade functionality)
        "stale": [],  # Staleness issues (persona_context out of sync with profile)
        "security": [],  # Path security violations (traversal, absolute paths, etc.)
    }
    validated: dict[str, list[str]] = {
        "persona_files": [],
        "overlays": [],
        "exclusive_skills": [],
    }

    # Add staleness issues if detected
    if staleness_result and staleness_result.get("stale"):
        for discrepancy in staleness_result.get("discrepancies", []):
            issues["stale"].append(
                {
                    "type": "stale_persona_context",
                    "field": discrepancy["field"],
                    "details": discrepancy,
                    "message": discrepancy["message"],
                    "fix": staleness_result["fix"],
                }
            )

    persona = persona_context.get("persona")
    fallback = persona_context.get("fallback")
    skill_overlay_path = persona_context.get("skill_overlay_path")
    overlay_fallback_path = persona_context.get("overlay_fallback_path")
    files = persona_context.get("files", [])

    # 1. Validate persona_context.files - security check then existence
    for file_path in files:
        # Security: validate path before any file operations
        is_safe, security_error = validate_safe_path(file_path, base_path)
        if not is_safe:
            issues["security"].append(
                {
                    "type": "unsafe_persona_file_path",
                    "path": file_path,
                    "message": f"Unsafe persona file path rejected: {security_error}",
                    "impact": "File will not be loaded - potential path traversal or injection",
                }
            )
            continue  # Don't check existence of unsafe paths

        full_path = base_path / file_path
        if full_path.exists():
            validated["persona_files"].append(file_path)
        else:
            issues["errors"].append(
                {
                    "type": "missing_persona_file",
                    "path": file_path,
                    "message": f"Persona file not found: {file_path}",
                    "fix": "Run 'uv run aria-esi persona-context' to regenerate",
                }
            )

    # 2. Validate skill overlays for skills with has_persona_overlay: true
    skills = skill_index.get("skills", [])
    for skill in skills:
        if not skill.get("has_persona_overlay"):
            continue

        skill_name = skill["name"]
        overlay_found = False
        checked_paths = []
        security_blocked = False

        # Check primary overlay path
        if skill_overlay_path:
            primary_path = f"{skill_overlay_path}/{skill_name}.md"
            # Security: validate constructed path
            is_safe, security_error = validate_safe_path(primary_path, base_path)
            if not is_safe:
                issues["security"].append(
                    {
                        "type": "unsafe_overlay_path",
                        "skill": skill_name,
                        "path": primary_path,
                        "message": f"Unsafe overlay path rejected: {security_error}",
                        "impact": "Overlay will not be loaded",
                    }
                )
                security_blocked = True
            else:
                checked_paths.append(primary_path)
                if (base_path / primary_path).exists():
                    overlay_found = True
                    validated["overlays"].append(primary_path)

        # Check fallback path if primary not found
        if not overlay_found and not security_blocked and overlay_fallback_path:
            fallback_path = f"{overlay_fallback_path}/{skill_name}.md"
            # Security: validate constructed path
            is_safe, security_error = validate_safe_path(fallback_path, base_path)
            if not is_safe:
                issues["security"].append(
                    {
                        "type": "unsafe_overlay_fallback_path",
                        "skill": skill_name,
                        "path": fallback_path,
                        "message": f"Unsafe fallback overlay path rejected: {security_error}",
                        "impact": "Fallback overlay will not be loaded",
                    }
                )
            else:
                checked_paths.append(fallback_path)
                if (base_path / fallback_path).exists():
                    overlay_found = True
                    validated["overlays"].append(fallback_path)

        # If no overlay found (and not blocked for security), it's a warning
        if not overlay_found and not security_blocked and checked_paths:
            issues["warnings"].append(
                {
                    "type": "missing_skill_overlay",
                    "skill": skill_name,
                    "checked_paths": checked_paths,
                    "message": f"Skill '{skill_name}' has has_persona_overlay=true but no overlay found",
                    "impact": "Skill will use base behavior without persona adaptation",
                }
            )

    # 3. Validate persona-exclusive skills the user should have access to
    unrestricted = persona_context.get("unrestricted_skills", False)

    for skill in skills:
        exclusive_to = skill.get("persona_exclusive")
        if not exclusive_to:
            continue

        # Check if this user has access (matches persona, fallback, or unrestricted)
        has_access = (
            exclusive_to == persona
            or exclusive_to == fallback
            or unrestricted
        )

        if has_access:
            redirect_path = skill.get("redirect")
            if redirect_path:
                # Security: validate redirect path before file operations
                is_safe, security_error = validate_safe_path(redirect_path, base_path)
                if not is_safe:
                    issues["security"].append(
                        {
                            "type": "unsafe_redirect_path",
                            "skill": skill["name"],
                            "path": redirect_path,
                            "message": f"Unsafe redirect path rejected: {security_error}",
                            "impact": "Exclusive skill will not be available",
                        }
                    )
                    continue  # Don't check existence of unsafe paths

                if (base_path / redirect_path).exists():
                    validated["exclusive_skills"].append(redirect_path)
                else:
                    issues["errors"].append(
                        {
                            "type": "missing_exclusive_skill",
                            "skill": skill["name"],
                            "redirect": redirect_path,
                            "message": f"Exclusive skill '{skill['name']}' redirect not found: {redirect_path}",
                            "impact": "Skill invocation will fail",
                        }
                    )

    return {
        "valid": (
            len(issues["errors"]) == 0
            and len(issues["warnings"]) == 0
            and len(issues["stale"]) == 0
            and len(issues["security"]) == 0
        ),
        "issues": issues,
        "validated": validated,
        "summary": {
            "persona_files_ok": len(validated["persona_files"]),
            "persona_files_missing": len(
                [i for i in issues["errors"] if i["type"] == "missing_persona_file"]
            ),
            "overlays_ok": len(validated["overlays"]),
            "overlays_missing": len(
                [i for i in issues["warnings"] if i["type"] == "missing_skill_overlay"]
            ),
            "exclusive_skills_ok": len(validated["exclusive_skills"]),
            "exclusive_skills_missing": len(
                [i for i in issues["errors"] if i["type"] == "missing_exclusive_skill"]
            ),
            "staleness_issues": len(issues["stale"]),
            "security_violations": len(issues["security"]),
        },
    }


def cmd_validate_overlays(args: argparse.Namespace) -> dict:
    """
    Validate persona context and overlay dependencies.

    Args:
        args: Parsed arguments with --pilot option

    Returns:
        Validation result dict
    """
    query_ts = get_utc_timestamp()
    base_path = Path.cwd()

    # Load skill index
    skill_index = load_skill_index(base_path)
    if not skill_index:
        return {
            "query_timestamp": query_ts,
            "status": "error",
            "message": "Skill index not found at .claude/skills/_index.json",
        }

    # Determine which pilots to validate
    pilots_to_validate = []

    if getattr(args, "all", False):
        # Validate all pilots from registry
        registry_path = base_path / "userdata" / "pilots" / "_registry.json"
        if registry_path.exists():
            registry = json.loads(registry_path.read_text())
            for pilot in registry.get("pilots", []):
                pilot_dir = base_path / "userdata" / "pilots" / pilot["directory"]
                if pilot_dir.exists():
                    pilots_to_validate.append(
                        {
                            "id": pilot["character_id"],
                            "directory": pilot["directory"],
                            "path": pilot_dir,
                        }
                    )
    else:
        # Validate single pilot (active or specified)
        pilot_id = getattr(args, "pilot", None)
        try:
            pilot_dir = get_pilot_directory(pilot_id)
            if pilot_dir:
                pilots_to_validate.append(
                    {
                        "id": pilot_id or "active",
                        "directory": pilot_dir.name,
                        "path": pilot_dir,
                    }
                )
        except Exception as e:
            return {
                "query_timestamp": query_ts,
                "status": "error",
                "message": f"Failed to resolve pilot: {e}",
            }

    if not pilots_to_validate:
        return {
            "query_timestamp": query_ts,
            "status": "error",
            "message": "No pilots found to validate",
        }

    # Validate each pilot
    results = []
    all_valid = True

    for pilot in pilots_to_validate:
        profile_path = pilot["path"] / "profile.md"
        if not profile_path.exists():
            results.append(
                {
                    "pilot_id": pilot["id"],
                    "directory": pilot["directory"],
                    "status": "error",
                    "message": f"Profile not found: {profile_path}",
                }
            )
            all_valid = False
            continue

        # Read profile and extract persona_context
        content = profile_path.read_text()
        persona_context = extract_persona_context_from_profile(content)

        if not persona_context:
            results.append(
                {
                    "pilot_id": pilot["id"],
                    "directory": pilot["directory"],
                    "status": "error",
                    "message": "No persona_context found in profile. Run 'uv run aria-esi persona-context'",
                }
            )
            all_valid = False
            continue

        # Extract current profile settings for staleness detection
        current_faction = extract_profile_field(content, "Primary Faction")
        current_rp_level = extract_profile_field(content, "RP Level")
        current_persona_override = extract_profile_field(content, "Persona")

        # Detect staleness (Finding 4: persona_context out of sync with profile)
        staleness_result = detect_staleness(
            persona_context,
            current_faction or DEFAULT_FACTION,
            current_rp_level or "off",
            base_path,
            current_persona_override,
        )

        # Validate (includes staleness check)
        validation = validate_persona_context(
            persona_context, skill_index, base_path, staleness_result
        )

        if not validation["valid"]:
            all_valid = False

        results.append(
            {
                "pilot_id": pilot["id"],
                "directory": pilot["directory"],
                "persona": persona_context.get("persona"),
                "status": "valid" if validation["valid"] else "issues_found",
                "validation": validation,
            }
        )

    return {
        "query_timestamp": query_ts,
        "status": "valid" if all_valid else "issues_found",
        "pilots_validated": len(results),
        "results": results,
    }


def cmd_verify_persona_context(args: argparse.Namespace) -> dict:
    """
    Verify integrity of compiled persona artifact.

    Checks that source files haven't changed since compilation and that
    the artifact hasn't been tampered with. This is a security check that
    should run at boot time to detect injection attempts.

    Security finding: SECURITY_001.md Finding #2

    Args:
        args: Parsed arguments with --pilot and --regenerate options

    Returns:
        Verification result dict
    """
    query_ts = get_utc_timestamp()
    base_path = Path.cwd()

    # Resolve pilot directory
    pilot_id = getattr(args, "pilot", None)
    try:
        pilot_dir = get_pilot_directory(pilot_id)
    except Exception as e:
        return {
            "query_timestamp": query_ts,
            "status": "error",
            "message": f"Failed to resolve pilot: {e}",
        }

    if not pilot_dir:
        return {
            "query_timestamp": query_ts,
            "status": "error",
            "message": "No pilot directory found",
        }

    # Path to compiled artifact
    artifact_path = pilot_dir / ".persona-context-compiled.json"

    # Verify the artifact
    result = verify_persona_artifact(artifact_path, base_path)

    # Handle regeneration request
    regenerate = getattr(args, "regenerate", False)

    if not result.valid and regenerate:
        # Attempt to regenerate from profile
        profile_path = pilot_dir / "profile.md"
        if not profile_path.exists():
            return {
                "query_timestamp": query_ts,
                "status": "error",
                "message": "Cannot regenerate: profile.md not found",
                "verification": result.to_dict(),
            }

        content = profile_path.read_text()
        persona_context = extract_persona_context_from_profile(content)

        if not persona_context:
            return {
                "query_timestamp": query_ts,
                "status": "error",
                "message": "Cannot regenerate: no persona_context in profile",
                "verification": result.to_dict(),
            }

        # Regenerate the artifact
        compile_persona_context(persona_context, base_path, artifact_path)

        # Re-verify after regeneration
        result = verify_persona_artifact(artifact_path, base_path)

        return {
            "query_timestamp": query_ts,
            "status": "regenerated" if result.valid else "regeneration_failed",
            "regenerated": True,
            "verification": result.to_dict(),
        }

    return {
        "query_timestamp": query_ts,
        "status": "valid" if result.valid else "integrity_failed",
        "verification": result.to_dict(),
    }


# =============================================================================
# Parser Registration
# =============================================================================


def register_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Register persona command parsers."""
    # persona-context command
    parser = subparsers.add_parser(
        "persona-context",
        help="Regenerate persona_context in pilot profile(s)",
        description="Pre-compute persona loading context for pilot profiles. "
        "This removes runtime conditional evaluation from the LLM.",
    )
    parser.add_argument(
        "--pilot",
        metavar="ID",
        help="Pilot character ID (default: active pilot)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all pilots in registry",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without writing",
    )
    parser.set_defaults(func=cmd_persona_context)

    # validate-overlays command
    validate_parser = subparsers.add_parser(
        "validate-overlays",
        help="Validate persona context and overlay dependencies",
        description="Check that all persona files, skill overlays, and exclusive skill "
        "redirects referenced in the profile actually exist. Reports errors (critical "
        "missing files) and warnings (missing overlays that degrade functionality).",
    )
    validate_parser.add_argument(
        "--pilot",
        metavar="ID",
        help="Pilot character ID (default: active pilot)",
    )
    validate_parser.add_argument(
        "--all",
        action="store_true",
        help="Validate all pilots in registry",
    )
    validate_parser.set_defaults(func=cmd_validate_overlays)

    # verify-persona-context command
    verify_parser = subparsers.add_parser(
        "verify-persona-context",
        help="Verify integrity of compiled persona artifact",
        description="Check that the compiled persona artifact matches source files. "
        "Detects tampering by recomputing hashes and comparing against stored values. "
        "This is a security check that runs at boot time (SECURITY_001.md Finding #2).",
    )
    verify_parser.add_argument(
        "--pilot",
        metavar="ID",
        help="Pilot character ID (default: active pilot)",
    )
    verify_parser.add_argument(
        "--regenerate",
        action="store_true",
        help="Regenerate artifact if verification fails",
    )
    verify_parser.set_defaults(func=cmd_verify_persona_context)
