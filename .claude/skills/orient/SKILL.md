---
name: orient
description: Local area intel for orientation in unknown space. Use after wormhole jumps, filaments, or when dropped into unfamiliar territory.
model: haiku
category: tactical
triggers:
  - "/orient"
  - "orient me"
  - "what's around me"
  - "local intel"
  - "where am I"
  - "just landed in [system]"
  - "dropped into [system]"
  - "situational awareness"
requires_pilot: false
---

# ARIA Local Orientation Module

## Purpose
Provide consolidated tactical intelligence when a pilot finds themselves in unknown space, typically after wormhole jumps, filaments, or other unexpected relocations.

## Trigger Phrases
- "orient me"
- "what's around me"
- "local intel"
- "just landed in [system]"
- "dropped into [system]"

## Data Sources

### MCP Tools (preferred)

If the `aria-universe` MCP server is connected, use the `universe` dispatcher:

```
universe(action="local_area", origin="ZZ-TOP", max_jumps=10, include_realtime=True)
```

**Response includes:**
- Origin system details (security, region, constellation)
- Threat summary (total kills, active camps, threat level)
- Hotspots (high PvP activity systems)
- Quiet zones (zero/low activity for stealth ops)
- Ratting banks (high NPC kills indicating targets)
- Escape routes (nearest low-sec, high-sec)
- Security borders (transition points)

### CLI Fallback

If MCP tools are not available:

```bash
uv run aria-esi orient <system> [--max-jumps N] [--realtime]
```

## Output Format

```
═══════════════════════════════════════════════════════════════
ARIA LOCAL ORIENTATION - [System] ([Region])
───────────────────────────────────────────────────────────────
THREAT LEVEL: [LOW/MEDIUM/HIGH/EXTREME]
  [X] ship kills within [N] jumps (last hour)
  [Active gatecamp warning if detected]

AVOID (High Activity)
│ System   │ Jumps │ Kills │ Threat          │
│ ...      │ ...   │ ...   │ ...             │

QUIET ZONES (Stealth Ops)
│ System   │ Jumps │ Kills │ NPC Kills │
│ ...      │ ...   │ ...   │ ...       │

RATTING BANKS (Content)
│ System   │ Jumps │ NPC Kills │ Potential      │
│ ...      │ ...   │ ...       │ ...            │

ESCAPE ROUTES
  Nearest [security]: [X] jumps via [system]
═══════════════════════════════════════════════════════════════
```

## Threat Level Classification

| Level | Criteria |
|-------|----------|
| LOW | < 20 kills, no camps, < 2 hotspots |
| MEDIUM | 20-49 kills, or 2-4 hotspots |
| HIGH | 50+ kills, or 5+ hotspots, or 1 active camp |
| EXTREME | 3+ active camps |

## System Classification

### Hotspots (Avoid or Hunt)
Systems with 5+ PvP kills in the last hour. These are active combat zones:
- Gate camps
- Fleet engagements
- Roaming gangs

### Quiet Zones (Stealth Ops)
Systems with 0 PvP kills. Good for:
- Stealth mining
- Safe passage
- Staging operations

### Ratting Banks (Content)
Systems with 100+ NPC kills. Indicates:
- Active ratting activity
- Potential targets for hunters
- Profitable PvE areas

## Real-Time Enhancement

When `include_realtime=True` and the RedisQ poller is healthy:
- Active gatecamp detection (kill clustering analysis)
- Minute-level kill data instead of hourly
- Force asymmetry detection (camps vs fleet fights)

## Use Cases

### Wormhole Exit
"I just jumped out of a wormhole and landed in XYZ-12, orient me"
- Immediate threat assessment
- Nearest escape routes to k-space
- Quiet systems for scanning

### Filament Activation
"Used a filament and now I'm in null-sec, what's around me?"
- Regional threat picture
- Ratting banks to hunt or avoid
- Path back to safer space

### Roaming Fleet
"We're in hostile space, give me local intel"
- Identify active systems (targets)
- Avoid detected camps
- Find staging points

## Response Priority

When presenting results, prioritize:
1. **Immediate threats** - Active camps, extreme activity
2. **Escape routes** - How to get to safer space
3. **Tactical opportunities** - Quiet zones, ratting banks
4. **Context** - Regional info, border systems
