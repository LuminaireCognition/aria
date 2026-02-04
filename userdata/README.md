# User Data Directory

This directory contains all personal data for ARIA. Everything here is gitignored except this README.

## Structure

```
userdata/
├── config.json          # Active pilot selector (character ID)
├── credentials/         # OAuth tokens per character
│   └── {character_id}.json
├── pilots/              # Pilot profiles and data
│   ├── _registry.json   # Maps character IDs to directories
│   └── {character_id}_{name}/
│       ├── profile.md       # Identity, faction, RP level
│       ├── operations.md    # Ship roster, activities, home base
│       ├── ships.md         # Ship inventory
│       ├── goals.md         # Current objectives
│       ├── industry/        # Manufacturing projects
│       └── projects/        # Long-term plans
└── sessions/            # Session logs and history
    └── *.json, *.md
```

## Migration from Legacy Locations

If you have existing data in the old locations, ARIA will automatically detect and use it:

| Legacy Location | New Location |
|-----------------|--------------|
| `.aria-config.json` | `userdata/config.json` |
| `credentials/` | `userdata/credentials/` |
| `pilots/` | `userdata/pilots/` |
| `sessions/` | `userdata/sessions/` |

To migrate manually, move your files to the new locations. ARIA checks both locations during the transition period.

## Privacy

This entire directory is gitignored. Your personal data, credentials, and session history are never committed to version control.
