# ARIA Skill Schema v1.0

This document defines the standard frontmatter schema for ARIA skills.

## Frontmatter Fields

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Skill identifier (kebab-case, matches directory name) |
| `description` | string | User-facing description for help text and skill discovery |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `model` | string | (inherited) | Model hint: `haiku` for fast/simple, `sonnet` for complex |
| `triggers` | string[] | [] | Natural language phrases that invoke this skill |
| `requires_pilot` | boolean | false | Whether skill needs active pilot context |
| `data_sources` | string[] | [] | Local files the skill reads (supports `{active_pilot}` placeholder) |
| `external_sources` | string[] | [] | Trusted external domains skill may fetch from |
| `esi_scopes` | string[] | [] | ESI scopes required for full functionality |
| `category` | string | "general" | Grouping: tactical, operations, financial, identity, system |

## Example Frontmatter

### Minimal (Backward Compatible)

```yaml
---
name: help
description: Display available ARIA commands and capabilities.
model: haiku
---
```

### Full Schema

```yaml
---
name: mission-brief
description: ARIA tactical intelligence briefing for Eve Online missions.
model: sonnet
category: tactical
triggers:
  - "mission brief"
  - "prepare for mission"
  - "I accepted a mission against [faction]"
requires_pilot: true
data_sources:
  - userdata/pilots/{active_pilot}/profile.md
  - userdata/pilots/{active_pilot}/ships.md
  - reference/pve-intel/INDEX.md
  - reference/mechanics/npc_damage_types.md
external_sources:
  - wiki.eveuniversity.org
esi_scopes: []
---
```

## Field Details

### triggers

Natural language phrases that should invoke this skill. Used for:
- Auto-generating help documentation
- Skill discovery and matching
- Progressive disclosure suggestions

**Guidelines:**
- Include the slash command itself (e.g., `/mission-brief`)
- Include common variations users might say
- Use `[placeholder]` for variable parts

### requires_pilot

Set to `true` if the skill needs to:
- Read pilot-specific files (profile.md, ships.md, etc.)
- Access ESI credentials
- Reference `{active_pilot}` in data_sources

### data_sources

Local files the skill reads. Use `{active_pilot}` placeholder for pilot-specific paths.

**Examples:**
```yaml
data_sources:
  - userdata/pilots/{active_pilot}/profile.md
  - reference/ships/fittings/*.md
  - reference/mechanics/ore_database.md
```

### external_sources

Trusted domains the skill may fetch from. Only these domains are allowed.

**Security:**
- Limits prompt injection attack surface
- Documents external dependencies
- Enables auditing of network access

### esi_scopes

ESI OAuth scopes required for full skill functionality.

**Examples:**
```yaml
esi_scopes:
  - esi-wallet.read_character_wallet.v1
  - esi-skills.read_skillqueue.v1
```

### category

Logical grouping for organization:

| Category | Skills |
|----------|--------|
| `identity` | pilot, help, aria-status |
| `tactical` | mission-brief, threat-assessment, fitting, route |
| `operations` | mining-advisory, exploration, journal |
| `financial` | price, wallet-journal, lp-store, orders |
| `industry` | industry-jobs, fittings |
| `system` | help, first-run-setup, esi-query |

## Index Generation

The skill index generator (`aria-skill-index.py`) reads all SKILL.md files and produces:

1. `.claude/skills/_index.json` - Machine-readable skill registry
2. Validation warnings for missing/invalid fields

Run with:
```bash
uv run python .claude/scripts/aria-skill-index.py
```

## Migration

Existing skills with minimal frontmatter continue to work. Enhanced fields are optional and additive.

To migrate a skill:
1. Add `triggers` array from the "Trigger Phrases" section
2. Add `requires_pilot: true` if it reads pilot files
3. Add `data_sources` from the "Data Sources" section
4. Add `category` for grouping
