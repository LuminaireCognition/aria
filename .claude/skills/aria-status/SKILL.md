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

## Pre-flight Sync

Before generating the status report, attempt to sync standings data from ESI — **only if ESI is available**:

1. Check session boot context for ESI status. If `esi.status` is `"none"` or ESI auth is unavailable, **skip sync entirely** and proceed with existing profile data.
2. If ESI is available, run: `uv run aria-esi sync-profile`
3. If sync succeeds, proceed with updated profile data
4. If sync fails at runtime, continue with existing profile data and note the sync status

**Never call `aria-esi sync-profile` or other ESI-authenticated commands when ESI is unavailable.** This skill must function fully from cached profile data alone.

## Objective Cross-Check

When presenting CURRENT OBJECTIVES from the pilot profile:
- If an objective references a standing threshold (e.g., "reach 5.0 with Caldari Navy"), cross-check against the standings data loaded from the synced profile
- If the threshold is already met, mark the objective as **COMPLETED** rather than presenting it as an active goal
- If standings data is unavailable (sync failed), present objectives as-is without status

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

| DO NOT Include | Why |
|----------------|-----|
| Current location | Volatile - stale in seconds |
| Current ship | Volatile - use `/esi-query` |
| Wallet balance | Volatile - use `/esi-query` |

## Response Format

Sections: CAPSULEER, HOME BASE, OPERATIONAL RANGE, SHIP ROSTER, STANDINGS SUMMARY, CURRENT OBJECTIVES, RECOMMENDATIONS. End with: "For live telemetry (location, ship, wallet), use /esi-query."

If profile or operations data is missing, suggest `/setup` and present only available data.

## Incomplete Profile Handling

When reading `operations.md`, check each field for placeholder values (`[To be determined]`, `TBD`, `N/A`, or similar).

- **Do not present placeholders as valid data.** A field reading `[To be determined]` is a data gap, not an answer.
- **Show the gap explicitly.** Use the format: `Home system: not configured (region: Sinq Laison)` — include any surrounding context (region, constellation) that is available, but mark the missing piece clearly.
- **Append a one-line prompt** when any gap is found: "Update `operations.md` to complete your home base configuration."

This applies to all sections: home constellation, primary station, operational range, or any other field that may be left as a placeholder during initial setup.

## Behavior Notes
- **Brevity:** Keep reports compact (<20 lines)
- Omit empty sections
- Offer `/esi-query` for live data rather than guessing location
- Reference ship roster by role, not "currently flying"

## Contextual Suggestions

After providing status, suggest ONE related command when contextually relevant:

| Context | Suggest |
|---------|---------|
| Standings show mission goal progress | "Ready to run missions? `/mission-brief` for intel" |
| Ship roster shows exploration ship | "Use `/exploration` when you find sites" |
| Capsuleer seems uncertain what to do | "Try `/help` for available commands" |
| Goals mention specific activity | Suggest that activity's command |

The status report itself already mentions `/esi-query` for live data.
