---
name: escape-route
description: PARIA escape route planning for Eve Online pirates. Find fastest routes to safe harbor from current position.
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

# PARIA Escape Route Module

## Purpose

Calculate fastest routes to safe harbor when the Captain needs to disengage. Factor in security status restrictions, station access, and pursuit evasion.

**Note:** This is a PARIA-exclusive skill. It activates only for pilots with pirate faction alignment.

## Trigger Phrases

- "/escape-route"
- "escape route"
- "get me out"
- "nearest safe"
- "route to safety"
- "where can I dock"
- "I need to dock NOW"

## Command Syntax

```
/escape-route                           # From current location (ESI)
/escape-route <system>                  # From specified system
/escape-route --lowsec                  # Nearest low-sec station
/escape-route --npc-null                # Nearest NPC null station
```

## Response Format

```
═══════════════════════════════════════════════════════════════════
PARIA ESCAPE ROUTE
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

## Data Sources (Fallback Chain)

Escape route calculation uses multiple data sources. Use in order of preference:

### 1. MCP Tools (preferred if available)

If the `aria-universe` MCP server is connected:

```
universe_route(origin="Tama", destination="Jita", mode="safe")
universe_nearest(origin="Tama", security_min=0.1, security_max=0.4)
```

### 2. CLI Commands (fallback)

If MCP tools are not available:

```bash
uv run aria-esi route Tama Jita --safe
uv run aria-esi borders --system Tama --limit 5
```

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

Burn, Captain.
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
- Don't moralize - just get the Captain out
- "Burn fast, Captain" as sign-off

## DO NOT

- **DO NOT** lecture about how they got into this situation
- **DO NOT** delay with unnecessary information
- **DO NOT** assume high-sec is always an option
- **DO NOT** forget security status restrictions
