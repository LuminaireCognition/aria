---
name: gatecamp
description: Real-time gatecamp detection and intel. Check for active camps in systems or along routes.
model: sonnet
category: tactical
triggers:
  - "/gatecamp"
  - "is there a camp in [system]"
  - "gatecamp check"
  - "camp status"
  - "any camps on route to [system]"
requires_pilot: false
has_persona_overlay: true
injected_prerequisites:
  - reference/mechanics/chokepoints.json
argument-hint: "<system|route>"
allowed-tools: [Read, Grep, Glob, "mcp__aria-universe__universe", "mcp__aria-universe__killmails"]
---

# Gatecamp Intelligence

## Command Syntax

```
/gatecamp <system>                         # Check single system
/gatecamp --route <origin> <destination>   # Check systems along route
/gatecamp                                  # Check current region (default)
```

### Default Behavior

When no system is specified, queries default to the pilot's current region:
1. ESI location if available (requires `esi-location.read_location.v1` scope)
2. Profile home region as fallback (from `operations.md`)

## Data Source

Always use MCP with real-time enabled:

```
universe(action="activity", systems=["<system>"], include_realtime=True)
```

For route analysis, use the dedicated gatecamp_risk action:

```
universe(action="gatecamp_risk", origin="<origin>", destination="<dest>", mode="safe")
```

## Response Format

```
GATECAMP INTEL: <System> (<sec>)
STATUS: <ACTIVE GATECAMP DETECTED | NO ACTIVE CAMP DETECTED | REAL-TIME INTEL UNAVAILABLE>
CONFIDENCE: <from tool response>

DETECTION SUMMARY:
  Kills in last 10 min: <N>
  Last kill: <age>
  Force asymmetry: <ratio>

ATTACKER ANALYSIS:
  Corporations: <corp> [[!] ON WATCHLIST if matched]
  Ship types: <types with counts>
  Camp type: <from tool response>

RECENT KILLS:
  <age>  <victim_ship>  (<attacker_count> attackers, <corp>) [[!] WATCHLIST if matched]

RECOMMENDATION:
  <avoidance advice and alternative routes>
```

**Conditional sections:**
- If no camp detected: Show hourly activity (ship kills, pod kills, jumps) and brief assessment instead of detection/attacker/kills sections.
- For route analysis: List each flagged system with its camp data, then overall route risk and recommendations.
- If real-time unavailable: Show hourly aggregates with clear warning that active camps cannot be detected.

## Watchlist Integration

Cross-reference attackers against configured watchlists. Query watched entity kills:
```bash
uv run aria-esi redisq-watched --system <system_id> --minutes 60
```
Flag matched entities with `[!] ON WATCHLIST` or `[!] WATCHLIST` indicators. Prominently warn if camp is run by watched entities.

## Pochven Awareness

Systems with `security_class: "POCHVEN"` are **Triglavian-controlled space**, not generic null-sec. When a queried system is in Pochven:

- Label it as **POCHVEN** (not NULL-SEC) in the header: `GATECAMP INTEL: Niarja (-1.0 POCHVEN)`
- Note that **access requires filaments or Triglavian standings** — standard stargate travel does not work
- Pochven has unique NPC behavior and mechanics distinct from null-sec
- If the system appears in a route, warn that the route transits Pochven and may be impassable without filaments

The MCP tool returns `security_class: "POCHVEN"` and `region: "Pochven"` for these systems. Use either field to detect them.

## Security Mechanics

Warp disruption bubbles (anchored, interdiction probe, and heavy interdictor) **only function in nullsec and wormhole space**. They do not work in lowsec or highsec.

- **Nullsec/WH:** Mention bubble risk in camp assessments
- **Lowsec:** Camps use gate guns + tackle (scrams/points/webs). Never reference bubbles.
- **Highsec:** Camps use suicide ganking (CONCORD response). Never reference bubbles or tackle.

If the queried system has security > 0.0, do not mention bubbles in the assessment.

## Known Chokepoints

Chokepoint reference data is injected below — do not re-read `reference/mechanics/chokepoints.json`.

When a queried system or route system matches a known chokepoint:
- Flag it with `[!] KNOWN CHOKEPOINT` even if current activity is zero
- Include the `reason` and `camp_frequency` from the reference data
- Suggest `safe_alternatives` from the reference data
- Never report "no chokepoints identified" if the route transits a known chokepoint system

This supplements the algorithmic pipe/hub detection with historical community knowledge for systems that may appear quiet but are persistently dangerous.

## Output Rules

- Keep response under 30 lines
- Append a one-line `Sources:` footer listing MCP calls and reference files used

## Behavior Notes

- **Never give false assurance** - "No active camp" means no recent kills, not guaranteed safety
- **Include alternatives** - When camps are detected, compute alternative routes via tool calls.
  **NEVER suggest routes from training data.** EVE geography in training data is unreliable.
  1. Use `universe(action="route", origin="...", destination="...", mode="safe", avoid_systems=["<camped_system>"])` to compute alternatives
  2. Reference `safe_alternatives` from chokepoints.json for known chokepoints
  3. If no tool-computed alternative is available, state that explicitly
  **NEVER assert which routes a chokepoint does or does not lie on** without a `route` tool call to verify. EVE route topology changed with Pochven and changes across patches. Claims like "Uedama is not on the Jita-Amarr route" require verification via `universe(action="route", ...)`. When listing chokepoints for context, state their general danger (from `chokepoints.json`) without claiming route membership.
- **Time sensitivity** - Camp status can change in minutes; include timestamp
- **Graceful degradation** - If real-time unavailable, fall back to hourly data with clear warning
- **Scout recommendation** - For high-value cargo, always recommend scouting regardless of data
- **Known chokepoints** - Always cross-reference against prerequisite chokepoints.json, even when live data shows zero activity

## Reference: Chokepoints (injected)
<!-- prerequisite: reference/mechanics/chokepoints.json -->
!`cat reference/mechanics/chokepoints.json`
