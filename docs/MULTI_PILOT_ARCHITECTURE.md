# Multi-Pilot Directory Architecture

## Overview

ARIA supports multiple pilots per EVE account and multiple accounts. Each pilot has isolated data while sharing common reference material.

---

## Directory Structure

```
/EveOnline/
├── userdata/                   # User data (gitignored)
│   ├── config.json             # Active pilot selection
│   ├── credentials/            # ESI OAuth tokens
│   │   └── {character_id}.json
│   └── pilots/
│       ├── _registry.json      # Pilot index
│       └── {id}_{slug}/        # Per-pilot data
│           ├── profile.md
│           ├── operations.md
│           ├── ships.md
│           ├── missions.md
│           ├── exploration.md
│           └── industry/blueprints.md
├── reference/                  # Shared reference (committed)
│   ├── mechanics/
│   ├── lore/
│   ├── ships/
│   └── missions/
└── templates/                  # Profile templates
```

---

## Key Files

### userdata/config.json

```json
{
  "version": "2.0",
  "active_pilot": "2123984364",
  "settings": {
    "boot_greeting": true,
    "auto_refresh_tokens": true
  }
}
```

### userdata/pilots/_registry.json

```json
{
  "schema_version": "1.0",
  "pilots": [
    {
      "character_id": "2123984364",
      "character_name": "Federation Navy Suwayyah",
      "directory": "2123984364_federation_navy",
      "faction": "Gallente"
    }
  ]
}
```

**Valid faction values:**

| Type | Values | Persona |
|------|--------|---------|
| Empire | `Gallente`, `Caldari`, `Minmatar`, `Amarr` | ARIA (faction-flavored) |
| Pirate | `pirate`, `angel_cartel`, `serpentis`, `guristas`, `blood_raiders`, `sanshas_nation` | PARIA |

Pirate factions activate the **PARIA** persona instead of ARIA. See `personas/paria/voice.md`.

### Directory Naming

Format: `{character_id}_{slug}`
- `character_id`: Unique EVE ID (ensures uniqueness)
- `slug`: Sanitized name (lowercase, underscores, max 32 chars)

---

## Pilot Selection

**Priority order:**
1. `ARIA_PILOT` environment variable
2. `userdata/config.json` → `active_pilot`
3. Auto-select if single pilot exists
4. Prompt if multiple pilots, none selected

**Switching pilots:**
```bash
# Session-specific
ARIA_PILOT=9876543210 claude

# Persistent (edit config)
# Set "active_pilot" in userdata/config.json
```

---

## Data Classification

| Type | Location | Scope |
|------|----------|-------|
| Identity, standings | `userdata/pilots/{id}/profile.md` | Per-pilot |
| Ships, fittings | `userdata/pilots/{id}/ships.md` | Per-pilot |
| Mission/exploration logs | `userdata/pilots/{id}/*.md` | Per-pilot |
| Blueprints | `userdata/pilots/{id}/industry/` | Per-pilot |
| Game mechanics | `reference/mechanics/` | Shared |
| Faction lore | `reference/lore/` | Shared |
| Ship guides | `reference/ships/` | Shared |
| PvE intel | `reference/pve-intel/` | Shared |

---

## Adding a New Pilot

1. Run OAuth setup: `uv run python .claude/scripts/aria-oauth-setup.py`
2. System creates credential file and pilot directory
3. Complete `/setup` to configure profile

**Manual setup:**
```bash
mkdir -p userdata/pilots/9876543210_my_alt
cp templates/*.template.md userdata/pilots/9876543210_my_alt/
# Rename .template.md → .md, edit files
```

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Per-pilot credential files | Isolation, independent refresh |
| Character ID in directory names | Guaranteed uniqueness |
| Registry JSON | Fast enumeration without filesystem scan |
| Shared reference data | Avoid duplication |
| Environment variable override | Easy scripting, temp switches |

---

*See [ADR-001](../dev/decisions/ADR-001-multi-pilot-architecture.md) for architectural decision record.*
