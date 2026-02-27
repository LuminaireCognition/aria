---
name: escape-route
description: Escape route planning for Eve Online. Find fastest routes to safe harbor from current position.
model: haiku
category: tactical
triggers:
  - "/escape-route"
  - "escape route"
  - "get me out"
  - "nearest safe"
  - "route to safety"
  - "where can I dock"
requires_pilot: true
esi_scopes:
  - esi-location.read_location.v1
data_sources:
  - userdata/pilots/{active_pilot}/profile.md
---

# Escape Route Module

## Command Syntax

```
/escape-route                           # From current location (ESI)
/escape-route <system>                  # From specified system
/escape-route --lowsec                  # Nearest low-sec station
/escape-route --npc-null                # Nearest NPC null station
```

## Required Tool Calls (MANDATORY)

Every route and destination in the response MUST come from an actual tool call. Do NOT fabricate routes.

| Step | Call | Required For |
|------|------|-------------|
| 1 | `universe(action="route", origin="...", destination="...", mode="safe")` | Every named route with jump count |
| 2 | `universe(action="nearest", origin="...", security_min=..., security_max=...)` | Finding nearest safe harbors |
| 3 | `universe(action="activity", systems=[...], include_realtime=True)` | Activity data for route systems (Route Display Standard) |

**Every system name in the response MUST appear in a tool call response.** If a system was not returned by any MCP call, it cannot appear in the output.

> **⚠️ HALLUCINATION GUARD:** Every route, system name, jump count, and security status in the response MUST come from MCP/CLI calls made in this session. NEVER name systems from training data memory. If you cannot make the route call, say so — do not guess a route.

### Field → Source Mapping

| Output Field | Required Source | Tool Call |
|-------------|----------------|-----------|
| Current system | ESI location or user input | `uv run aria-esi location` or user-provided |
| Route system names | Universe route | `universe(action="route", origin="...", destination="...", mode="safe")` |
| Jump count per route | Universe route | `universe(action="route", ...)` response `total_jumps` |
| System security status | Universe route | Included in route response per system |
| Nearest safe harbor | Universe nearest | `universe(action="nearest", origin="...", security_min=..., security_max=...)` |
| Activity on route (kills, jumps) | Activity dispatcher | `universe(action="activity", systems=[...])` |
| NPC null station names | Universe nearest/route | `universe(action="nearest", ...)` or `universe(action="route", ...)` |

## Response Format

```
═══════════════════════════════════════════════════════════════════
ESCAPE ROUTE
───────────────────────────────────────────────────────────────────
CURRENT POSITION: Tama (0.3)
SECURITY STATUS: -4.2
───────────────────────────────────────────────────────────────────
NEAREST SAFE HARBORS:

1. LOW-SEC STATION (2 jumps)
   Hikkoken - State Protectorate
   Route: Tama -> Nourv -> Hikkoken
   Risk: Gate camps possible on Nourvukaiken

2. NPC NULL STATION (8 jumps)
   Venal - Guristas Assembly Plant
   Route: Through Tribute
   Risk: Bubble camps in null

3. HIGH-SEC (if sec >-2.0): N/A
   Your sec status bars high-sec docking

RECOMMENDED:
  Hikkoken station - 2 jumps, minimal exposure
───────────────────────────────────────────────────────────────────
Burn fast, Captain.
═══════════════════════════════════════════════════════════════════
```

## Safe Harbor Types

### By Security Status Access

| Sec Status | High-Sec | Low-Sec | NPC Null | Sov Null |
|------------|----------|---------|----------|----------|
| > -2.0 | Yes | Yes | Yes | Depends |
| -2.0 to -2.5 | 0.9+ only | Yes | Yes | Depends |
| -2.5 to -3.0 | 1.0 only | Yes | Yes | Depends |
| -3.0 to -4.0 | 0.9+ restricted | Yes | Yes | Depends |
| < -4.5 | No | Yes | Yes | Depends |
| < -5.0 | Faction police | Yes | Yes | Depends |

### Station Types

| Type | Docking | Notes |
|------|---------|-------|
| NPC Station | Always open | Safe harbor |
| Player Citadel | Access list | May be locked |
| FW Station | Militia only | If in FW |
| Pirate NPC Station | Open | Found in NPC null |

## NPC Null Regions (Safe Harbors)

Pirate-friendly NPC stations:

| Region | Faction | Notes |
|--------|---------|-------|
| Venal | Guristas | Good market |
| Curse | Angel Cartel | Central location |
| Stain | Sansha | Remote |
| Syndicate | Syndicate | Near Gallente space |
| Great Wildlands | Thukker Tribe | Near Minmatar |
| Outer Ring | ORE | Limited services |

## Escape Considerations

### Immediate Escape (Combat)

When actively engaged:
1. **Align to celestial** - Start moving
2. **Overheat MWD** - Maximum speed
3. **Check D-scan** - Are you bubbled?
4. **Warp to safe** - Tactical bookmark preferred
5. **Then dock** - Once you've broken tackle

### Pursuit Evasion

When being chased:
- **Don't warp gate to gate** - Predictable
- **Use tactical bookmarks** - Off-grid safes
- **Consider wormholes** - Escape route or trap
- **Log off in space** - Last resort (15 min timer)

### Security Status Complications

If sec status restricts high-sec:
- Faction police spawn in high-sec
- Navy response gets faster as you go
- 1.0 systems = near-instant response
- Plan routes through low-sec or null

## Route Planning Intelligence

### Gate Camp Detection

Known camp systems to consider:
- **Low-sec pipes:** Rancer, Amamake, Tama
- **Null entries:** HED-GP, EC-P8R
- **Chokepoints:** Any single-gate system

### Alternative Routes

When primary route is camped:
- Check for wormhole connections
- Route through adjacent region
- Use jump clone if available
- Wait out the camp (patience)

## Integration with ESI

With ESI location scope:
- Auto-detect current system
- Factor in current ship type
- Consider jump clone locations

Without ESI:
- Requires manual system input
- Still provides route options

## Emergency Protocols

### "I'm Tackled" Response

```
Can't help with tackle - that's piloting.

If you get out:
  Nearest safe: [system] - [jumps] jumps
  Route: [system list]

Burn fast, Captain.
```

### "They're Following" Response

```
Break pursuit pattern:
1. Don't warp directly to out-gate
2. Warp to celestial at range
3. D-scan the gate before landing
4. Consider a safe log if outnumbered

Nearest harbor: [system] - [jumps] jumps
```

## Integration with Other Skills

| Context | Suggest |
|---------|---------|
| Need to assess route danger | "Run `/threat-assessment` on waypoints" |
| Planning return trip | "Use `/route` for hunting route back" |
| Checking sec status | "Try `/sec-status` for empire access" |

## Behavior Notes

- Speed is critical - provide immediate answers
- Prioritize nearest viable option
- Factor in security status restrictions
- Note known danger points on route
- Don't moralize - just get the pilot out
- "Burn fast, Captain" as sign-off

## Anti-Patterns

❌ **WRONG:** Present "Route: Tama → Nourv → Hikkoken" without calling `universe(action="route")`
✅ **RIGHT:** Call `universe(action="route", origin="Tama", destination="Hikkoken", mode="safe")` and present the returned path

❌ **WRONG:** Claim "NPC null station is 12-25 jumps" without a route query
✅ **RIGHT:** Call `universe(action="nearest")` or `universe(action="route")` for actual jump counts

❌ **WRONG:** Name systems that appear in no MCP response (fabricated from training data)
✅ **RIGHT:** Every system name must trace to a tool call response in this session

## DO NOT

- **DO NOT** lecture about how they got into this situation
- **DO NOT** delay with unnecessary information
- **DO NOT** assume high-sec is always an option
- **DO NOT** forget security status restrictions
