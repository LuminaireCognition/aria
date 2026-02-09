# ARIA Templates

This directory contains reference template files for new ARIA installations. The recommended setup method is to use the first-run setup command, but templates can also be copied manually to `userdata/pilots/{character_id}_{name}/`.

`aria-init` generates files from inline heredocs so it can interpolate user input directly. These template files are the canonical structure reference.

## Quick Setup (Recommended)

Use the first-run setup wizard:

```bash
uv run aria-esi setup
```

This will guide you through creating your pilot profile interactively.

## Manual Setup

```bash
# From the project root directory:
mkdir -p userdata/pilots/{your_character_id}_{name}/
cp templates/profile.template.md userdata/pilots/{your_character_id}_{name}/profile.md
cp templates/operations.template.md userdata/pilots/{your_character_id}_{name}/operations.md
cp templates/ships.template.md userdata/pilots/{your_character_id}_{name}/ships.md
cp templates/missions.template.md userdata/pilots/{your_character_id}_{name}/missions.md
cp templates/exploration.template.md userdata/pilots/{your_character_id}_{name}/exploration.md
cp templates/goals.template.md userdata/pilots/{your_character_id}_{name}/goals.md
mkdir -p userdata/pilots/{your_character_id}_{name}/industry/
cp templates/industry/blueprints.template.md userdata/pilots/{your_character_id}_{name}/industry/blueprints.md
```

## Template Files

| Template | Purpose | Priority |
|----------|---------|----------|
| `profile.template.md` | Character identity, faction, standings | **Required** |
| `operations.template.md` | Home base, ship roster, playstyle | **Required** |
| `ships.template.md` | Ship fittings and configurations | Recommended |
| `missions.template.md` | Mission tracking and history | Optional |
| `exploration.template.md` | Exploration discoveries | Optional |
| `goals.template.md` | Short-term and long-term planning goals | Optional |
| `industry/blueprints.template.md` | Blueprint inventory | Optional (ESI can populate) |

## After Copying

1. Edit `userdata/pilots/{your_pilot}/profile.md` first - this sets your faction and ARIA's persona
2. Edit `userdata/pilots/{your_pilot}/operations.md` - defines your home base and operations
3. Fill in other files as you play

## Placeholders

Templates use these placeholder markers:

- `[YOUR CHARACTER NAME]` - Replace with your info
- `[GALLENTE/CALDARI/MINMATAR/AMARR]` - Choose one
- `<!-- Example: ... -->` - Reference examples (can delete)
- `[ ]` - Checkbox items, delete non-applicable options

## ESI Integration

If you set up ESI integration (see `docs/ESI.md`), some data can be auto-populated:

```bash
# Refresh blueprint library from ESI
uv run aria-esi blueprints > userdata/pilots/{your_pilot}/industry/blueprints.md
```
