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

> **HALLUCINATION GUARD:** Every fitting name, ship hull, module list, and fitting ID in the response MUST come from a `pilot(action="fittings_list", ...)` or `pilot(action="fittings_detail", ...)` MCP call, or a CLI call made in this session. If neither was called or returned an error, present only the error state. NEVER fill in fittings from training data.

**You MUST call the MCP tool or CLI command below before presenting any fitting data.** Do not summarize, guess, or present fittings without executing the command first.

## Implementation

### MCP (preferred)

```
pilot(action="fittings_list")
pilot(action="fittings_list", ship_filter="Vexor")
pilot(action="fittings_detail", fitting_id=12345)
pilot(action="fittings_detail", fitting_id=12345, eft=True)
```

**Parameters:**

| Action | Parameter | Description | Default |
|--------|-----------|-------------|---------|
| `fittings_list` | `ship_filter` | Filter by ship hull name (partial match) | None |
| `fittings_detail` | `fitting_id` | Fitting ID to show (required) | - |
| `fittings_detail` | `eft` | Return EFT format only | False |

### CLI (fallback)

```bash
PYTHONPATH=.claude/scripts uv run python -m aria_esi fittings [--ship <hull>]
PYTHONPATH=.claude/scripts uv run python -m aria_esi fittings-detail <fitting_id> [--eft]
```

## Response Format

Present fittings in a structured display including:
- **Header:** Query timestamp
- **Fitting list:** Name, ship hull, module count, and fitting ID
- **Detail view:** Full slot layout (high/med/low/rig/drone) and EFT export
- **Summary:** Total fittings and unique hull count

CLI returns JSON with fitting list/details. Format per template above.

Adapt format to RP level: markdown table for `off`, box-drawing for `on`/`full`.

## Error Handling (Mandatory)

When the MCP tool returns an error response:

1. **Check `error` field value:**
   - If `"scope_not_authorized"` → Tell the user: "ESI is connected but the
     fittings scope (`esi-fittings.read_fittings.v1`) isn't authorized. Re-run
     OAuth setup to add it." Include the command from the response.
   - If credentials RuntimeError → Tell the user: "ESI isn't configured yet."
     Offer `/fitting` as alternative.

2. **Never say "ESI authentication isn't configured" when the error is
   `scope_not_authorized`.** Other ESI features work — the user just needs
   to add one scope.

**Never produce a dead-end response.** If ESI is unavailable, always offer an actionable alternative (create a fit via `/fitting`, or check in-game).

## Behavior Notes

- **Brevity:** Default to table format unless RP mode requests formatted boxes
- **Sorting:** Alphabetical by name
- **EFT Format:** Standard EVE fitting format for import/export
- **IDs:** Show fitting IDs for reference
- **Hull Filter:** Match partial hull names (e.g., "vex" matches "Vexor")
