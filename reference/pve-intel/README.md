# ARIA PvE Intel Database

Tactical intelligence for PvE combat content including agent missions, DED complexes, unrated sites, and expeditions.

## Directory Structure

```
reference/pve-intel/
├── INDEX.md          # Static damage/EWAR reference (tracked)
├── README.md         # This file (tracked)
├── LICENSE           # CC-BY-SA 4.0 (tracked)
└── cache/            # Fetched intel data (gitignored)
    ├── INDEX.md      # Auto-generated cache index
    └── *.md          # Individual intel files
```

**Cache is ephemeral:** `rm -rf reference/pve-intel/cache/*` is always safe.

## Content Types

| Type | Filename Suffix | Example |
|------|-----------------|---------|
| Agent Missions | `_l{N}` | `the_blockade_blood_raiders_l3.md` |
| DED Complexes | `_ded{N}` | `mul_zatah_monastery_ded4.md` |
| Unrated Sites | `_unrated` | `desolate_site_unrated.md` |
| Expeditions | `_expedition` | `mare_sargassum_expedition.md` |

## Source Attribution

**Content Source:** [EVE University Wiki](https://wiki.eveuniversity.org/)
**License:** [Creative Commons Attribution-ShareAlike 4.0](https://creativecommons.org/licenses/by-sa/4.0/)

Intel data in `cache/` is adapted from EVE University Wiki. Per CC-BY-SA 4.0, derived work maintains the same license.

## Usage

ARIA references these files when `/mission-brief` is invoked. Each cached file contains:
- Faction and damage profiles
- Objective and completion trigger
- Wave/spawn summary
- Tactical notes

## Cache File Format

```markdown
# Site Name (Type)
Source: [wiki URL]

## Quick Reference
| Field | Value |
|-------|-------|
| Faction | [Enemy faction] |
| Damage Dealt | [Incoming damage types] |
| Tank | [Resist priority] |
| Deal | [Your damage priority] |
| Objective | [Completion trigger] |

## Waves/Rooms
[Spawn summary]

## Tactical Notes
[Key warnings and tips]
```
