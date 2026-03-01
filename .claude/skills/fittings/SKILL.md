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

**Note:** This is separate from `/fitting` which provides fitting *assistance*. This skill reads *saved fittings* from ESI.

Saved fittings data is stable — only changes when you save/delete fits in-game.

## Implementation

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

## Response Format

Present fittings in a structured display including:
- **Header:** Query timestamp
- **Fitting list:** Name, ship hull, module count, and fitting ID
- **Detail view:** Full slot layout (high/med/low/rig/drone) and EFT export
- **Summary:** Total fittings and unique hull count

CLI returns JSON with fitting list/details. Format per template above.

Adapt format to RP level: markdown table for `off`, box-drawing for `on`/`full`.

## Error Handling

| Condition | Action |
|-----------|--------|
| ESI not configured | Explain saved fittings require ESI authentication. Offer two alternatives: (1) run `/fitting` to create a recommended fit for their hull, (2) use the in-game fitting window (Alt+F) to view/export saved fits |
| Missing scope | Direct to setup script, specify `esi-fittings.read_fittings.v1` scope |
| ESI configured but request fails | Report the error and suggest checking in-game (Alt+F) |

**Never produce a dead-end response.** If ESI is unavailable, always offer an actionable alternative (create a fit via `/fitting`, or check in-game).

## Behavior Notes

- **Brevity:** Default to table format unless RP mode requests formatted boxes
- **Sorting:** Alphabetical by name
- **EFT Format:** Standard EVE fitting format for import/export
- **IDs:** Show fitting IDs for reference
- **Hull Filter:** Match partial hull names (e.g., "vex" matches "Vexor")
