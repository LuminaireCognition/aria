---
name: fittings
description: View saved ship fittings from ESI. List fittings, filter by hull, and export to EFT format.
model: haiku
category: operations
triggers:
  - "/fittings"
  - "my saved fits"
  - "saved fittings"
  - "show my fits"
  - "list fittings"
requires_pilot: true
esi_scopes:
  - esi-fittings.read_fittings.v1
---

# ARIA Saved Fittings Browser

## Purpose

Query the capsuleer's saved fittings to list and export ship configurations. Enables reviewing fits stored in-game and exporting them to EFT format for sharing or analysis.

**Note:** This is separate from the existing `/fitting` skill which provides fitting *assistance*. This skill reads *saved fittings* from ESI.

## ESI Write Capability

Unlike most ESI endpoints, fittings has **limited write capability**:
- **POST** - Create new saved fitting
- **DELETE** - Remove saved fitting by ID

**Current Implementation:** Read-only. Write operations documented but not implemented to prevent accidental data modification.

## CRITICAL: Data Volatility

Saved fittings data is **stable** - only changes when you save/delete fits:

1. **Display query timestamp** - fittings rarely change
2. **Safe to cache** - only updated by explicit action
3. **Fitting IDs are unique** - useful for reference

## Trigger Phrases

- `/fittings`
- "my saved fits"
- "saved fittings"
- "show my fits"
- "list fittings"
- "what fits do I have"
- "export fit"

## ESI Requirement

**Requires:** `esi-fittings.read_fittings.v1` scope

If scope is not authorized:
```
Saved fittings access requires ESI authentication.

To enable: uv run python .claude/scripts/aria-oauth-setup.py
Select "esi-fittings.read_fittings.v1" during scope selection.
```

## ESI Availability Check (CRITICAL)

**BEFORE making any ESI queries**, check the session hook output for ESI status:

```json
"esi": {"status": "UNAVAILABLE"}
```

### If ESI is UNAVAILABLE:

1. **DO NOT** run `uv run aria-esi` commands - they will timeout
2. **RESPOND IMMEDIATELY** with:
   ```
   Saved fittings requires live ESI data which is currently unavailable.

   Check this in-game: Fitting window (Alt+F) → Fittings tab

   Workaround: Paste an EFT fit directly and use /fitting for analysis.

   ESI usually recovers automatically.
   ```
3. **DO NOT** block waiting for ESI

### If ESI is AVAILABLE:

Proceed with normal fittings queries.

## Implementation

Run the ESI wrapper commands:
```bash
PYTHONPATH=.claude/scripts uv run python -m aria_esi fittings [options]
PYTHONPATH=.claude/scripts uv run python -m aria_esi fittings-detail <fitting_id> [options]
```

### Commands

| Command | Description |
|---------|-------------|
| `fittings` | List all saved fittings |
| `fittings-detail <id>` | Show fitting details with EFT export |

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--ship <hull>` | Filter by ship hull name | - |
| `--eft` | Output in EFT format (fittings-detail only) | - |

### JSON Response Structure (fittings)

```json
{
  "query_timestamp": "2026-01-15T14:30:00Z",
  "volatility": "stable",
  "character_id": 2119654321,
  "summary": {
    "total_fittings": 5,
    "unique_hulls": 3
  },
  "fittings": [
    {
      "fitting_id": 123456,
      "name": "Venture - Mining Alpha",
      "description": "Basic Venture mining fit",
      "ship_type_id": 32880,
      "ship_type_name": "Venture",
      "module_count": 8
    },
    {
      "fitting_id": 123457,
      "name": "Vexor - Ratting",
      "description": "Drone boat for anomalies",
      "ship_type_id": 626,
      "ship_type_name": "Vexor",
      "module_count": 15
    }
  ]
}
```

### JSON Response Structure (fittings-detail)

```json
{
  "query_timestamp": "2026-01-15T14:30:00Z",
  "volatility": "stable",
  "character_id": 2119654321,
  "fitting": {
    "fitting_id": 123456,
    "name": "Venture - Mining Alpha",
    "description": "Basic Venture mining fit",
    "ship_type_id": 32880,
    "ship_type_name": "Venture",
    "slots": {
      "high": [
        {"type_id": 17482, "type_name": "Miner II", "quantity": 2}
      ],
      "medium": [
        {"type_id": 5973, "type_name": "Survey Scanner I", "quantity": 1},
        {"type_id": 527, "type_name": "1MN Afterburner I", "quantity": 1}
      ],
      "low": [],
      "rig": [
        {"type_id": 31117, "type_name": "Small Cargohold Optimization I", "quantity": 2}
      ],
      "drone": [
        {"type_id": 2488, "type_name": "Hobgoblin II", "quantity": 2}
      ],
      "cargo": []
    },
    "eft_format": "[Venture, Venture - Mining Alpha]\n\nMiner II\nMiner II\n\nSurvey Scanner I\n1MN Afterburner I\n\n\nSmall Cargohold Optimization I\nSmall Cargohold Optimization I\n\n\nHobgoblin II x2"
  }
}
```

### Empty Response

```json
{
  "query_timestamp": "2026-01-15T14:30:00Z",
  "volatility": "stable",
  "character_id": 2119654321,
  "summary": {
    "total_fittings": 0,
    "unique_hulls": 0
  },
  "fittings": [],
  "message": "No saved fittings found"
}
```

## Slot Flag Mapping

ESI uses flag values to identify slots:

| Flag | Slot Type |
|------|-----------|
| HiSlot0-7 | High slots |
| MedSlot0-7 | Medium slots |
| LoSlot0-7 | Low slots |
| RigSlot0-2 | Rig slots |
| SubSystemSlot0-3 | T3 subsystems |
| DroneBay | Drone bay |
| FighterBay | Fighters (carriers) |
| Cargo | Cargo hold |
| ServiceSlot0-7 | Structure services |

## Response Formats

### Standard Display (rp_level: off or lite)

```markdown
## Saved Fittings
*Query: 14:30 UTC*

| Name | Ship | Modules |
|------|------|---------|
| Venture - Mining Alpha | Venture | 8 |
| Vexor - Ratting | Vexor | 15 |
| Catalyst - Salvage | Catalyst | 12 |

**Total:** 5 fittings across 3 hull types

*Use `fittings-detail <id> --eft` for EFT export.*
```

### Formatted Version (rp_level: moderate or full)

```
═══════════════════════════════════════════════════════════════════
ARIA SAVED FITTINGS
───────────────────────────────────────────────────────────────────
GalNet Sync: 14:30 UTC
───────────────────────────────────────────────────────────────────
FITTINGS: 5 total (3 hull types)
───────────────────────────────────────────────────────────────────
  [123456] Venture - Mining Alpha
  Hull: Venture | 8 modules
  Basic Venture mining fit

  [123457] Vexor - Ratting
  Hull: Vexor | 15 modules
  Drone boat for anomalies

  [123458] Catalyst - Salvage
  Hull: Catalyst | 12 modules
───────────────────────────────────────────────────────────────────
Use `fittings-detail <id> --eft` for EFT export.
═══════════════════════════════════════════════════════════════════
```

### EFT Format Export

```
[Venture, Venture - Mining Alpha]

Miner II
Miner II

Survey Scanner I
1MN Afterburner I


Small Cargohold Optimization I
Small Cargohold Optimization I


Hobgoblin II x2
```

## Error Handling

### ESI Not Configured

```
═══════════════════════════════════════════════════════════════════
ARIA SAVED FITTINGS
───────────────────────────────────────────────────────────────────
Saved fittings access requires ESI authentication.

ARIA works fully without ESI - you can manage fits
directly in the EVE client's fitting window.

OPTIONAL: Enable live access (~5 min setup)
  uv run python .claude/scripts/aria-oauth-setup.py
═══════════════════════════════════════════════════════════════════
```

### Missing Scope

```
═══════════════════════════════════════════════════════════════════
ARIA SAVED FITTINGS - SCOPE NOT AUTHORIZED
───────────────────────────────────────────────────────────────────
ESI is configured but fittings scope is missing.

To enable:
  uv run python .claude/scripts/aria-oauth-setup.py

Select "esi-fittings.read_fittings.v1" during setup.
═══════════════════════════════════════════════════════════════════
```

## Contextual Suggestions

| Context | Suggest |
|---------|---------|
| Viewing fittings | "Use `/fitting` for fit recommendations" |
| Exporting EFT | "Copy EFT format to import into EVE" |
| Has few fittings | "Save fits in-game to access them here" |

## Cross-References

| Related Command | Use Case |
|-----------------|----------|
| `/fitting` | Get fitting recommendations and assistance |
| `/assets --ships` | View ships you own |
| `/price` | Check module prices for a fit |

## Behavior Notes

- **Brevity:** Default to table format unless RP mode requests formatted boxes
- **Sorting:** Alphabetical by name
- **EFT Format:** Standard EVE fitting format for import/export
- **IDs:** Show fitting IDs for reference
- **Hull Filter:** Match partial hull names (e.g., "vex" matches "Vexor")
