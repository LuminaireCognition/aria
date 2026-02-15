#!/usr/bin/env python3
"""Generate docs/COMMANDS.md from .claude/skills/_index.json.

Usage:
    uv run python .claude/scripts/generate-commands-md.py          # Regenerate
    uv run python .claude/scripts/generate-commands-md.py --check  # Exit 1 if stale
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
INDEX_PATH = ROOT / ".claude" / "skills" / "_index.json"
COMMANDS_PATH = ROOT / "docs" / "COMMANDS.md"

# Map internal categories to display sections
CATEGORY_DISPLAY = {
    "tactical": "Combat & Tactical",
    "financial": "Market & Finance",
    "operations": "Industry & Operations",
    "industry": "Industry & Operations",
    "identity": "Identity & Status",
    "system": "System",
}

# Display order for sections
SECTION_ORDER = [
    "Combat & Tactical",
    "Market & Finance",
    "Industry & Operations",
    "Identity & Status",
    "System",
    "Pirate-Exclusive Commands",
]


def load_index() -> dict:
    with open(INDEX_PATH) as f:
        return json.load(f)


def get_example(skill: dict) -> str:
    """Get the first natural-language trigger as the example."""
    triggers = skill.get("triggers", [])
    for trigger in triggers:
        # Skip slash command triggers
        if not trigger.startswith("/"):
            return f'"{trigger}"'
    # Fallback to first trigger if all are slash commands
    if triggers:
        return f'"{triggers[0]}"'
    return ""


def generate() -> str:
    index = load_index()
    skills = index["skills"]

    # Separate pirate-exclusive from regular skills
    sections: dict[str, list[dict]] = {}
    pirate_skills: list[dict] = []

    for skill in skills:
        if skill.get("persona_exclusive") == "paria":
            pirate_skills.append(skill)
            continue

        category = skill.get("category", "system")
        display = CATEGORY_DISPLAY.get(category, "System")

        if display not in sections:
            sections[display] = []
        sections[display].append(skill)

    # Sort skills within each section by name
    for section_skills in sections.values():
        section_skills.sort(key=lambda s: s["name"])
    pirate_skills.sort(key=lambda s: s["name"])

    # Build output
    lines: list[str] = []
    lines.append("# ARIA Command Reference")
    lines.append("")
    lines.append(
        "All commands can be invoked as slash commands (`/command`) or as natural"
        " language. ARIA understands both."
    )
    lines.append("")
    lines.append(
        "**Quick tip:** You don't need to memorize commands. Just describe what you"
        ' want — "what should I mine?", "is this system safe?", "fit my Vexor" — and'
        " ARIA will figure it out."
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    # Regular sections
    for section_name in SECTION_ORDER:
        if section_name == "Pirate-Exclusive Commands":
            if not pirate_skills:
                continue
            skill_list = pirate_skills
        else:
            skill_list = sections.get(section_name, [])
            if not skill_list:
                continue

        lines.append(f"## {section_name}")
        lines.append("")

        if section_name == "Pirate-Exclusive Commands":
            lines.append(
                "These commands are only available when using the PARIA persona"
                " (pirate faction alignment)."
            )
            lines.append("")

        lines.append("| Command | Description | Example |")
        lines.append("|---------|-------------|---------|")

        for skill in skill_list:
            name = skill["name"]
            desc = skill.get("description", "")
            example = get_example(skill)
            # Use first slash trigger
            cmd = f"/{name}"
            lines.append(f"| `{cmd}` | {desc} | {example} |")

        lines.append("")

    # Natural language section
    lines.append("---")
    lines.append("")
    lines.append("## Natural Language")
    lines.append("")
    lines.append("You don't need slash commands at all. ARIA responds to natural phrasing:")
    lines.append("")
    lines.append('- "I accepted a mission against Serpentis" → triggers mission brief')
    lines.append('- "Is the route to Jita safe?" → triggers threat assessment + route')
    lines.append('- "What skills do I need for a Dominix?" → triggers skill planning')
    lines.append('- "How much is Tritanium worth?" → triggers price check')
    lines.append("")
    lines.append(
        "Multiple commands can chain naturally in conversation — ask a follow-up and"
        " ARIA uses context from previous answers."
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    # Footer with count
    total = index.get("skill_count", len(skills))
    category_count = len(
        [
            s
            for s in SECTION_ORDER
            if s in sections or (s == "Pirate-Exclusive Commands" and pirate_skills)
        ]
    )
    lines.append(
        f"*{total} commands across {category_count} categories. For in-session help, type `/help`.*"
    )
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    check_mode = "--check" in sys.argv

    generated = generate()

    if check_mode:
        if not COMMANDS_PATH.exists():
            print("ERROR: docs/COMMANDS.md does not exist", file=sys.stderr)
            sys.exit(1)

        current = COMMANDS_PATH.read_text()
        if current != generated:
            print(
                "ERROR: docs/COMMANDS.md is stale. Run:\n"
                "  uv run python .claude/scripts/generate-commands-md.py",
                file=sys.stderr,
            )
            sys.exit(1)

        print("OK: docs/COMMANDS.md is up to date")
        sys.exit(0)

    COMMANDS_PATH.write_text(generated)
    print(f"Generated {COMMANDS_PATH} ({len(generated)} bytes)")


if __name__ == "__main__":
    main()
