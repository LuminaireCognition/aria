---
name: gatecamp
description: Real-time gatecamp detection and intel. Check for active camps in systems or along routes.
model: haiku
category: tactical
triggers:
  - "/gatecamp"
  - "is there a camp in [system]"
  - "gatecamp check"
  - "camp status"
  - "any camps on route to [system]"
requires_pilot: false
has_persona_overlay: true
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
  Corporations: <corp> [⚠️ ON WATCHLIST if matched]
  Ship types: <types with counts>
  Camp type: <from tool response>

RECENT KILLS:
  <age>  <victim_ship>  (<attacker_count> attackers, <corp>) [⚠️ WATCHLIST if matched]

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
Flag matched entities with `⚠️ ON WATCHLIST` or `⚠️ WATCHLIST` indicators. Prominently warn if camp is run by watched entities.

## Behavior Notes

- **Never give false assurance** - "No active camp" means no recent kills, not guaranteed safety
- **Include alternatives** - Always suggest route alternatives when camps are detected
- **Time sensitivity** - Camp status can change in minutes; include timestamp
- **Graceful degradation** - If real-time unavailable, fall back to hourly data with clear warning
- **Scout recommendation** - For high-value cargo, always recommend scouting regardless of data
