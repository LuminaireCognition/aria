---
name: aria-status
description: ARIA operational status report. Use when capsuleer requests status, sitrep, or operational summary.
model: haiku
category: identity
triggers:
  - "/aria-status"
  - "status report"
  - "sitrep"
  - "what's my status"
  - "operational status"
requires_pilot: true
has_persona_overlay: true
data_sources:
  - userdata/pilots/{active_pilot}/profile.md
  - userdata/pilots/{active_pilot}/operations.md
  - userdata/pilots/{active_pilot}/ships.md
  - userdata/pilots/{active_pilot}/missions.md
---

# ARIA Status Report Module

## Purpose
Generate operational status reports using **stable** data. This skill does NOT display volatile data (current location, current ship) - use `/esi-query` for live telemetry.

## Trigger Phrases
- "status report"
- "sitrep"
- "what's my status"
- "operational status"
- `/aria-status`

## Pre-flight Sync

Before generating the status report, sync standings data from ESI:

1. Run: `uv run aria-esi sync-profile`
2. If sync succeeds, proceed with report generation using updated profile data
3. If sync fails (no ESI auth), continue with existing profile data and note the sync status

This ensures standings shown in the status report reflect current ESI values.

## CRITICAL: Volatility Awareness

Status reports use **stable and semi-stable data only**:

| Include | Source | Notes |
|---------|--------|-------|
| Capsuleer identity | Pilot Profile | Permanent |
| Home base | Operational Profile | Stable |
| Ship roster | Operational Profile | Stable |
| Standings | Pilot Profile | Semi-stable |
| Current goals | Pilot Profile | Stable |
| Mission log | Mission Log | Stable |

### Pilot Resolution (First Step)
Before accessing pilot files, resolve the active pilot path:
1. Read `userdata/config.json` → get `active_pilot` character ID
2. Read `userdata/pilots/_registry.json` → match ID to `directory` field
3. Use that directory for all pilot paths below (under `userdata/pilots/`)

**Single-pilot shortcut:** If config is missing, read the registry - if only one pilot exists, use that pilot's directory.

| DO NOT Include | Why |
|----------------|-----|
| Current location | Volatile - stale in seconds |
| Current ship | Volatile - use `/esi-query` |
| Wallet balance | Volatile - use `/esi-query` |

## Response Format

```
═══════════════════════════════════════════════════════════════════
ARIA OPERATIONAL STATUS
───────────────────────────────────────────────────────────────────
CAPSULEER: [Name]
HOME BASE: [Region] - [Station]
OPERATIONAL RANGE: [Security preference]
───────────────────────────────────────────────────────────────────
SHIP ROSTER:
• [Ship 1] - [Role]
• [Ship 2] - [Role]

STANDINGS SUMMARY:
• Federation Navy: [standing] (L[X] missions)
• [Other key standings]

CURRENT OBJECTIVES:
• [Goals from pilot_profile.md]

RECOMMENDATIONS:
• [Contextual suggestions]
═══════════════════════════════════════════════════════════════════

For live telemetry (location, ship, wallet), use /esi-query.
```

## Data Sources

### File Paths

| File Type | Path |
|-----------|------|
| Operational Profile | `userdata/pilots/{active_pilot}/operations.md` |
| Pilot Profile | `userdata/pilots/{active_pilot}/profile.md` |
| Mission Log | `userdata/pilots/{active_pilot}/missions.md` |
| Ship Status | `userdata/pilots/{active_pilot}/ships.md` |

### Primary (Always Safe)
- **Operational Profile** - Home base, ship roster, operational patterns
- **Pilot Profile** - Identity, standings, goals

### Secondary
- **Mission Log** - Recent mission history
- **Ship Status** - Ship fittings only (NOT current ship/location)

### Never Read For Status
- Current location/ship fields (deprecated)
- Any volatile ESI data

## Example Output

```
═══════════════════════════════════════════════════════════════════
ARIA OPERATIONAL STATUS
───────────────────────────────────────────────────────────────────
CAPSULEER: Federation Navy Suwayyah
HOME BASE: Sinq Laison - Masalle (X-Sense Chemical Refinery)
OPERATIONAL RANGE: Highsec (0.5+)
───────────────────────────────────────────────────────────────────
SHIP ROSTER:
• Imicus "im0" - Exploration
• Venture - Mining operations
• [Pending] - L2 mission runner

STANDINGS:
• Federation Navy: 3.52 (L2 access, L3 pending at 3.0)
• Gallente Federation: 0.99

OBJECTIVES:
• L3 mission access (need 3.0+ Fed Navy)
• Ship progression: Vexor for L2 missions
═══════════════════════════════════════════════════════════════════

For current location/ship, query: /esi-query
```

## Behavior Notes
- **Brevity:** Keep reports compact (<20 lines)
- Omit empty sections
- Offer `/esi-query` for live data rather than guessing location
- Reference ship roster by role, not "currently flying"
- Maintain ARIA persona throughout

## Contextual Suggestions

After providing status, suggest ONE related command when contextually relevant:

| Context | Suggest |
|---------|---------|
| Standings show mission goal progress | "Ready to run missions? `/mission-brief` for intel" |
| Ship roster shows exploration ship | "Use `/exploration` when you find sites" |
| Capsuleer seems uncertain what to do | "Try `/help` for available commands" |
| Goals mention specific activity | Suggest that activity's command |

The status report itself already mentions `/esi-query` for live data.
