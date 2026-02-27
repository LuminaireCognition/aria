---
name: help
description: Display available ARIA commands and capabilities. Use when capsuleer needs guidance on what ARIA can do.
model: haiku
category: system
triggers:
  - "/help"
  - "help"
  - "what can you do"
  - "commands"
  - "what commands are available"
  - "how do I..."
  - "show me the options"
requires_pilot: false
data_sources:
  - .claude/skills/_index.json
---

# ARIA Help — Dynamic Dispatcher

This skill generates help output from `.claude/skills/_index.json` at runtime. Do not hardcode command lists or topic descriptions.

## Step 1: Load the Index

Read `.claude/skills/_index.json`. Parse the `skills` array. Each entry has: `name`, `description`, `category`, `triggers`, `requires_pilot`, `esi_scopes`, `data_sources`, `prerequisite_files`.

## Step 2: Determine Request Type

- **`/help`** (no argument) — show the full command listing (see "Command Listing Format")
- **`/help <topic>`** — show detail for the matching skill (see "Topic Detail Format")
- **"how do I..."** / general capability questions — show the command listing with a brief intro

## Command Listing Format

Group skills by `category`. Present categories in this display order with these labels:

| category (from index) | Display Label |
|------------------------|---------------|
| `identity` | Identity & Status |
| `tactical` | Tactical & Navigation |
| `financial` | Financial & Market |
| `industry` | Industry |
| `operations` | Operations |
| `system` | System |

For each skill, show `/<name>` and a short description (use the `description` field, truncated to one phrase if needed). Exclude the `help` skill itself and internal skills like `aria-review`.

**Output constraints:**
- Target ~25 lines. Use markdown tables at `rp_level: off`, box-formatted layout at `on`/`full`.
- End with: `Natural language works too: "is Hek safe", "fit my Vexor", "prepare for Serpentis"`
- If `rp_level` is not `off`, end with: `For reference data: say "show database" or "data index"`

## Topic Detail Format

Match `<topic>` against skill names, triggers, and category keywords. When matched, present:

1. **Command name** — `/<skill.name>`
2. **Description** — from `skill.description`
3. **Triggers** — from `skill.triggers` (natural language examples)
4. **ESI requirement** — if `skill.esi_scopes` is non-empty, list required scopes
5. **Data sources** — if `skill.data_sources` is non-empty, mention them
6. **Related commands** — suggest 1-2 skills from the same category

Use box formatting only when `rp_level` is `on` or `full`. Otherwise use plain markdown.

## Special Topics (not backed by a single skill)

These topics require custom handling rather than a direct skill lookup:

- **`/help rp`** or **`/help roleplay`** — Explain RP levels (`off`/`on`/`full`), how to change in profile, and temporary toggle ("ARIA, drop RP" / "ARIA, resume"). RP is off by default.
- **`/help experience`** or **`/help level`** — Explain experience levels (`new`/`intermediate`/`veteran`), how they affect response detail, and how to set in profile.
- **`/help faction`** or **`/help persona`** — List the four faction personas (Gallente=ARIA Mk.IV, Caldari=AURA-C, Minmatar=VIND, Amarr=THRONE). Note personas only apply when RP is enabled.
- **`/help data`** or **`/help database`** — Point to `reference/INDEX.md` and key reference files (npc_damage_types.md, ore_database.md, hacking_guide.md).
- **`/help esi`** — Explain ESI is optional, list `/esi-query` subtypes (location, wallet, standings, skills, blueprints), point to `docs/ESI.md` for setup.

## Unknown Topic

If `<topic>` does not match any skill name, trigger, or special topic:
1. Say the topic was not recognized
2. List all skill names from the index as available topics
3. Suggest `/help` for the full listing

## Behavior

- **Brevity:** Default `/help` output should fit on one screen (~25 lines)
- **New player detection:** If the user seems unfamiliar with ARIA, highlight `/mission-brief`, `/fitting`, `/mining-advisory`, and `/threat-assessment` as starting points
- **Natural language reminder:** Always mention that natural phrasing works
