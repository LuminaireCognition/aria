#!/usr/bin/env python3
"""
ARIA Context Assembly
═══════════════════════════════════════════════════════════════════
Generates session context from active projects for conversational awareness.
Runs at boot to enable natural references like "the new corp" without
explicit file references.

Usage:
    python aria-context-assembly.py              # Generate context
    python aria-context-assembly.py --status     # Show current context
    python aria-context-assembly.py --json       # Output as JSON

Output:
    userdata/pilots/{id}_{slug}/.session-context.json
    (or pilots/{id}_{slug}/.session-context.json for legacy installations)

No external dependencies - uses only Python standard library.
═══════════════════════════════════════════════════════════════════
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════
# Status Categories
# ═══════════════════════════════════════════════════════════════════

ACTIVE_STATUSES = {"planning", "active", "in progress", "in-progress", "on hold", "paused"}
COMPLETED_STATUSES = {"completed", "done", "finished", "closed"}
ABANDONED_STATUSES = {"abandoned", "cancelled", "canceled", "dropped"}


# ═══════════════════════════════════════════════════════════════════
# Input Sanitization (Security Hardening - Tier I)
# ═══════════════════════════════════════════════════════════════════
# Prevents injection attacks via project file fields.
# Reference: TODO_SECURITY.md, PROJECT_REVIEW_001.md Section 1.4

MAX_NAME_LENGTH = 100
MAX_TARGET_LENGTH = 150
MAX_SUMMARY_LENGTH = 200
MAX_ALIAS_LENGTH = 50
MAX_TASK_LENGTH = 150

# Patterns to strip from extracted fields
_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
_TEMPLATE_PATTERN = re.compile(r"\{[^}]*\}")
_MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]]*\]\([^)]*\)")
_MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_CODE_BLOCK_PATTERN = re.compile(r"`[^`]+`")
_DIRECTIVE_PATTERN = re.compile(r"^\s*(SYSTEM|IGNORE|OVERRIDE|ADMIN|EXECUTE)[\s:\-]", re.IGNORECASE)


# ═══════════════════════════════════════════════════════════════════
# Alias Validation (Security Hardening - Tier II)
# ═══════════════════════════════════════════════════════════════════
# Validates aliases against forbidden patterns to prevent injection
# attempts via the alias map.
# Reference: TODO_SECURITY.md Section "Session Context Injection Hardening"

# Patterns that should not appear in aliases (case-insensitive search)
FORBIDDEN_ALIAS_PATTERNS = [
    r"\bignore\b",  # Prompt injection: "ignore previous instructions"
    r"\boverride\b",  # Prompt injection: "override restrictions"
    r"\bsystem\b",  # Prompt injection: "system prompt"
    r"\badmin\b",  # Privilege escalation: "admin mode"
    r"\bcredential",  # Sensitive data: "credentials", "credential"
    r"\bsecret",  # Sensitive data: "secret", "secrets"
    r"\btoken\b",  # Sensitive data: "token"
    r"\bpassword\b",  # Sensitive data: "password"
    r"\bbypass\b",  # Security bypass attempts
    r"\brestrict",  # Prompt injection: "restrictions", "restrict"
    r"\bpermission",  # Privilege escalation: "permissions"
    r"\baccess\b",  # Privilege escalation: "access granted"
    r"\bexecute\b",  # Code execution: "execute command"
    r"\beval\b",  # Code execution: "eval"
    r"\bimport\b",  # Code execution: "import os"
    r"\b__\w+__\b",  # Python dunder methods: "__init__", "__import__"
]

# Allowed characters in aliases: word chars, spaces, hyphens, dots, apostrophes
# Unicode-aware to support non-English capsuleer names
ALLOWED_ALIAS_CHARS = re.compile(r"^[\w\s\-\.\'\,]+$", re.UNICODE)


def validate_alias(alias: str) -> tuple[bool, str]:
    """
    Validate an alias against security rules.

    Checks:
    1. Non-empty and within length limit
    2. Contains only allowed characters
    3. Does not match forbidden patterns

    Args:
        alias: The sanitized alias to validate

    Returns:
        Tuple of (is_valid, rejection_reason)
        - (True, "") if valid
        - (False, reason) if invalid
    """
    if not alias:
        return False, "empty"

    if len(alias) > MAX_ALIAS_LENGTH:
        return False, f"exceeds {MAX_ALIAS_LENGTH} char limit"

    if not ALLOWED_ALIAS_CHARS.match(alias):
        return False, "contains disallowed characters"

    alias_lower = alias.lower()
    for pattern in FORBIDDEN_ALIAS_PATTERNS:
        if re.search(pattern, alias_lower):
            return False, f"matches forbidden pattern: {pattern}"

    return True, ""


def sanitize_field(value: str, max_length: int) -> str:
    """
    Sanitize an extracted field to prevent injection attacks.

    Applies the following transformations:
    1. Truncates to max_length
    2. Strips HTML/XML-like tags
    3. Strips template/code syntax ({...}, `...`)
    4. Strips markdown links and images
    5. Removes directive-like prefixes
    6. Normalizes whitespace

    Args:
        value: The raw extracted value
        max_length: Maximum allowed length

    Returns:
        Sanitized string, or empty string if input was None/empty
    """
    if not value:
        return ""

    # Truncate first to limit processing on maliciously long inputs
    value = value[: max_length * 2]  # Allow some headroom for stripping

    # Strip HTML/XML tags: <script>, <img>, etc.
    value = _HTML_TAG_PATTERN.sub("", value)

    # Strip template syntax: {variable}, {{template}}, etc.
    value = _TEMPLATE_PATTERN.sub("", value)

    # Strip markdown images: ![alt](url)
    value = _MARKDOWN_IMAGE_PATTERN.sub("", value)

    # Strip markdown links: [text](url)
    value = _MARKDOWN_LINK_PATTERN.sub("", value)

    # Strip inline code: `code`
    value = _CODE_BLOCK_PATTERN.sub("", value)

    # Remove directive-like prefixes that could be injection attempts
    value = _DIRECTIVE_PATTERN.sub("", value)

    # Normalize whitespace (collapse multiple spaces, strip leading/trailing)
    value = " ".join(value.split())

    # Final truncation to exact max length
    value = value[:max_length]

    return value.strip()


# ═══════════════════════════════════════════════════════════════════
# Path Resolution
# ═══════════════════════════════════════════════════════════════════


def get_project_root() -> Path:
    """Find the ARIA project root directory."""
    env_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_dir:
        return Path(env_dir)

    script_dir = Path(__file__).parent
    if script_dir.name == "scripts":
        project_root = script_dir.parent.parent
        if (project_root / "CLAUDE.md").exists():
            return project_root

    cwd = Path.cwd()
    if (cwd / "CLAUDE.md").exists():
        return cwd

    return Path(__file__).parent.parent.parent


def get_active_pilot_id(project_root: Path) -> str:
    """Get the active pilot ID from environment or config.

    Checks in priority order:
    1. ARIA_PILOT environment variable
    2. userdata/config.json (new canonical location)
    3. .aria-config.json (legacy fallback)
    4. Auto-detect from single pilot in userdata/pilots/ or pilots/
    """
    pilot_id = os.environ.get("ARIA_PILOT")
    if pilot_id:
        return pilot_id

    # Check new canonical location first
    config_path = project_root / "userdata" / "config.json"
    if config_path.exists():
        try:
            with open(config_path) as f:
                config = json.load(f)
            pilot_id = config.get("active_pilot")
            if pilot_id:
                return str(pilot_id)
        except (OSError, json.JSONDecodeError):
            pass

    # Legacy fallback
    legacy_config_path = project_root / ".aria-config.json"
    if legacy_config_path.exists():
        try:
            with open(legacy_config_path) as f:
                config = json.load(f)
            pilot_id = config.get("active_pilot")
            if pilot_id:
                return str(pilot_id)
        except (OSError, json.JSONDecodeError):
            pass

    # Fallback: check pilots directory for single pilot
    # Check new location first
    for pilots_dir in [project_root / "userdata" / "pilots", project_root / "pilots"]:
        if pilots_dir.exists():
            pilot_dirs = [d for d in pilots_dir.iterdir() if d.is_dir() and not d.name.startswith("_")]
            if len(pilot_dirs) == 1:
                # Extract ID from directory name (format: {id}_{slug})
                parts = pilot_dirs[0].name.split("_", 1)
                if parts[0].isdigit():
                    return parts[0]

    return ""


def find_pilot_directory(project_root: Path, pilot_id: str) -> Path:
    """Find the pilot's directory.

    Checks in priority order:
    1. userdata/pilots/{pilot_id}_* (new canonical location)
    2. pilots/{pilot_id}_* (legacy fallback)
    """
    # Check new location first
    userdata_pilots = project_root / "userdata" / "pilots"
    if userdata_pilots.exists():
        matches = list(userdata_pilots.glob(f"{pilot_id}_*"))
        if matches:
            return matches[0]

    # Legacy fallback
    legacy_pilots = project_root / "pilots"
    if legacy_pilots.exists():
        matches = list(legacy_pilots.glob(f"{pilot_id}_*"))
        if matches:
            return matches[0]

    return None


# ═══════════════════════════════════════════════════════════════════
# Project File Parsing
# ═══════════════════════════════════════════════════════════════════


def parse_project_file(filepath: Path) -> dict:
    """Parse a project markdown file and extract metadata."""
    try:
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return None

    project = {
        "file": filepath.name,
        "path": str(filepath),
        "name": None,
        "status": None,
        "phase": None,
        "aliases": [],
        "summary": None,
        "target": None,
        "next_steps": [],
    }

    # Extract project name from # Project: Name
    # SECURITY: Sanitize to prevent injection via project name
    name_match = re.search(r"^#\s*Project:\s*(.+)$", content, re.MULTILINE)
    if name_match:
        project["name"] = sanitize_field(name_match.group(1), MAX_NAME_LENGTH)

    # Extract status from **Status:** Value
    # NOTE: Status already constrained to \w+ pattern (low risk)
    status_match = re.search(r"\*\*Status:\*\*\s*(\w+(?:\s+\w+)?)", content)
    if status_match:
        project["status"] = status_match.group(1).strip()

    # Extract target from **Target:** Value
    # SECURITY: Sanitize to prevent injection via target field
    target_match = re.search(r"\*\*Target:\*\*\s*(.+)$", content, re.MULTILINE)
    if target_match:
        project["target"] = sanitize_field(target_match.group(1), MAX_TARGET_LENGTH)

    # Extract aliases from **Aliases:** a, b, c
    # SECURITY: Sanitize and validate each alias to prevent injection via alias map
    # Tier I: Sanitization strips dangerous syntax
    # Tier II: Validation rejects forbidden patterns
    aliases_match = re.search(r"\*\*Aliases:\*\*\s*(.+)$", content, re.MULTILINE)
    if aliases_match:
        aliases_str = aliases_match.group(1).strip()
        raw_aliases = [a.strip() for a in aliases_str.split(",") if a.strip()]
        validated_aliases = []
        for raw_alias in raw_aliases:
            # Step 1: Sanitize (Tier I)
            sanitized = sanitize_field(raw_alias, MAX_ALIAS_LENGTH)
            if not sanitized:
                continue

            # Step 2: Validate (Tier II)
            is_valid, reason = validate_alias(sanitized)
            if is_valid:
                validated_aliases.append(sanitized)
            else:
                # Log warning for rejected aliases (to stderr for visibility)
                print(
                    f"ARIA Security: Alias rejected in {filepath.name}: "
                    f"'{sanitized[:30]}{'...' if len(sanitized) > 30 else ''}' ({reason})",
                    file=sys.stderr,
                )
        project["aliases"] = validated_aliases

    # Extract current phase - look for *(Current)* marker
    phase_match = re.search(r"###\s*(Phase\s*\d+[^*\n]*)\s*\*\(Current\)\*", content)
    if phase_match:
        project["phase"] = phase_match.group(1).strip()
    else:
        # Try **Current Phase** field
        phase_match = re.search(r"\*\*Current Phase[:\*]*\*?\*?\s*(.+)$", content, re.MULTILINE)
        if phase_match:
            project["phase"] = phase_match.group(1).strip()

    # Extract objective/summary from ## Objective section
    # SECURITY: Sanitize to prevent injection via objective text
    obj_match = re.search(r"##\s*Objective\s*\n+(.+?)(?=\n##|\n---|\Z)", content, re.DOTALL)
    if obj_match:
        obj_text = obj_match.group(1).strip()
        # Take first line or sentence
        first_line = obj_text.split("\n")[0].strip()
        project["summary"] = sanitize_field(first_line, MAX_SUMMARY_LENGTH)

    # Extract next steps - unchecked items from current phase section
    # SECURITY: Sanitize each task to prevent injection via task descriptions
    if project["phase"]:
        # Find the phase section and extract unchecked items
        phase_escaped = re.escape(project["phase"])
        phase_section = re.search(
            rf"###\s*{phase_escaped}.*?\n(.*?)(?=\n###|\n---|\Z)", content, re.DOTALL
        )
        if phase_section:
            raw_tasks = re.findall(r"-\s*\[\s*\]\s*(.+)$", phase_section.group(1), re.MULTILINE)
            project["next_steps"] = [
                sanitize_field(task, MAX_TASK_LENGTH)
                for task in raw_tasks[:5]  # Limit to 5
                if sanitize_field(task, MAX_TASK_LENGTH)  # Skip empty after sanitization
            ]

    return project


def categorize_status(status: str) -> str:
    """Determine if a project is active, completed, or abandoned."""
    if not status:
        return "active"  # Default to active if no status

    status_lower = status.lower()

    if status_lower in COMPLETED_STATUSES:
        return "completed"
    elif status_lower in ABANDONED_STATUSES:
        return "abandoned"
    else:
        return "active"


# ═══════════════════════════════════════════════════════════════════
# Context Assembly
# ═══════════════════════════════════════════════════════════════════


def assemble_context(pilot_dir: Path) -> dict:
    """Assemble context from all project files."""
    projects_dir = pilot_dir / "projects"

    context = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "active_pilot": pilot_dir.name.split("_")[0],
        "pilot_directory": str(pilot_dir),
        "active_projects": [],
        "completed_projects": [],
        "abandoned_projects": [],
        "alias_map": {},  # Maps aliases to project names
        "project_count": {"active": 0, "completed": 0, "abandoned": 0, "total": 0},
    }

    if not projects_dir.exists():
        return context

    for project_file in sorted(projects_dir.glob("*.md")):
        project = parse_project_file(project_file)
        if not project or not project["name"]:
            continue

        category = categorize_status(project["status"])

        if category == "active":
            context["active_projects"].append(project)
            context["project_count"]["active"] += 1

            # Build alias map for active projects
            for alias in project["aliases"]:
                context["alias_map"][alias.lower()] = project["name"]

        elif category == "completed":
            context["completed_projects"].append(project)
            context["project_count"]["completed"] += 1
        else:
            context["abandoned_projects"].append(project)
            context["project_count"]["abandoned"] += 1

        context["project_count"]["total"] += 1

    return context


def write_context(pilot_dir: Path, context: dict) -> bool:
    """Write the session context file."""
    output_path = pilot_dir / ".session-context.json"

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(context, f, indent=2)
        return True
    except OSError as e:
        print(f"Error writing context: {e}", file=sys.stderr)
        return False


# ═══════════════════════════════════════════════════════════════════
# Status Display
# ═══════════════════════════════════════════════════════════════════


def show_status(project_root: Path, pilot_id: str, as_json: bool = False):
    """Display current session context status."""
    pilot_dir = find_pilot_directory(project_root, pilot_id)
    if not pilot_dir:
        print(f"Pilot directory not found for {pilot_id}", file=sys.stderr)
        return

    context_path = pilot_dir / ".session-context.json"
    if not context_path.exists():
        print("No session context found. Run without --status to generate.", file=sys.stderr)
        return

    try:
        with open(context_path) as f:
            context = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"Error reading context: {e}", file=sys.stderr)
        return

    if as_json:
        print(json.dumps(context, indent=2))
        return

    # Human-readable output
    print(f"Session Context (generated: {context.get('generated', 'unknown')})")
    print(f"Pilot: {context.get('pilot_directory', 'unknown')}")
    print()

    active = context.get("active_projects", [])
    if active:
        print(f"Active Projects ({len(active)}):")
        for proj in active:
            aliases = ", ".join(proj.get("aliases", [])) or "none"
            print(f"  - {proj['name']} ({proj.get('status', 'unknown')})")
            print(f"    Aliases: {aliases}")
            if proj.get("phase"):
                print(f"    Phase: {proj['phase']}")
            if proj.get("next_steps"):
                print(f"    Next: {proj['next_steps'][0]}")
        print()

    alias_map = context.get("alias_map", {})
    if alias_map:
        print("Alias Map:")
        for alias, name in alias_map.items():
            print(f'  "{alias}" → {name}')


# ═══════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(
        description="ARIA Context Assembly - Generate session context from projects",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--status", "-s", action="store_true", help="Show current context status")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    parser.add_argument("--quiet", "-q", action="store_true", help="Minimal output")

    args = parser.parse_args()

    # Resolve paths
    project_root = get_project_root()
    pilot_id = get_active_pilot_id(project_root)

    if not pilot_id:
        if not args.quiet:
            print("No active pilot configured", file=sys.stderr)
        sys.exit(1)

    if args.status:
        show_status(project_root, pilot_id, args.json)
        return

    pilot_dir = find_pilot_directory(project_root, pilot_id)
    if not pilot_dir:
        if not args.quiet:
            print(f"Pilot directory not found for {pilot_id}", file=sys.stderr)
        sys.exit(1)

    # Assemble and write context
    context = assemble_context(pilot_dir)

    if write_context(pilot_dir, context):
        if args.json:
            print(json.dumps(context, indent=2))
        elif not args.quiet:
            active_count = context["project_count"]["active"]
            alias_count = len(context.get("alias_map", {}))
            print(f"Context assembled: {active_count} active project(s), {alias_count} alias(es)")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
