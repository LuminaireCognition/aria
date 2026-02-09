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

# ARIA Gatecamp Intelligence Module

## Purpose
Provide real-time gatecamp detection and analysis for specific systems or along routes. Uses RedisQ killmail data to identify active camps with attacker analysis and tactical recommendations.

## Trigger Phrases
- "/gatecamp"
- "is there a camp in [system]"
- "gatecamp check"
- "camp status"
- "any camps on route to [system]"

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

### Arguments

| Argument | Description |
|----------|-------------|
| `system` | System name to check for gatecamp activity |
| `--route` | Check all systems along a route |
| `origin` | Starting system (for route mode) |
| `destination` | Target system (for route mode) |

## Data Source

Always use MCP with real-time enabled:

```
universe(action="activity", systems=["Niarja"], include_realtime=True)
```

For route analysis, use the dedicated gatecamp_risk action:

```
universe(action="gatecamp_risk", origin="Jita", destination="Amarr", mode="safe")
```

## Response Fields from Real-Time Data

When `include_realtime=True` is used, the response includes:

```json
{
  "system": "Niarja",
  "security": 0.5,
  "ship_kills": 47,
  "pod_kills": 12,
  "realtime": {
    "gatecamp": {
      "detected": true,
      "confidence": "HIGH",
      "kills_10min": 5,
      "last_kill_age_seconds": 120,
      "force_asymmetry": 8.3,
      "attackers": [
        {"corporation": "CODE.", "kills": 5}
      ],
      "ship_types": ["Tornado", "Thrasher"],
      "camp_type": "alpha_strike"
    },
    "recent_kills": [
      {
        "age_seconds": 120,
        "victim_ship": "Procurer",
        "attacker_count": 6,
        "attacker_corp": "CODE."
      }
    ],
    "kills_10min": 5,
    "kills_1hour": 47
  },
  "realtime_healthy": true
}
```

## Response Format

### Single System - Active Camp Detected

```
===============================================================
ARIA GATECAMP INTEL
---------------------------------------------------------------
SYSTEM: Niarja (0.5)
STATUS: ACTIVE GATECAMP DETECTED
CONFIDENCE: HIGH
---------------------------------------------------------------
DETECTION SUMMARY:
  Kills in last 10 min: 5
  Last kill: 2 minutes ago
  Force asymmetry: 8.3:1

ATTACKER ANALYSIS:
  Corporations: CODE. ⚠️ ON WATCHLIST
  Ship types: Tornado (4), Thrasher (2)
  Camp type: Alpha strike

RECENT KILLS:
  2 min ago   Procurer    (6 attackers, CODE.) ⚠️ WATCHLIST
  5 min ago   Retriever   (5 attackers, CODE.) ⚠️ WATCHLIST
  8 min ago   Capsule     (1 attacker, CODE.) ⚠️ WATCHLIST

RECOMMENDATION:
  Avoid or use webbing alt / cloak+MWD trick
  Alternative routes: via Amarr (+4j) or Dodixie (+6j)
===============================================================
```

### Single System - No Camp Detected

```
===============================================================
ARIA GATECAMP INTEL
---------------------------------------------------------------
SYSTEM: Tama (0.3)
STATUS: NO ACTIVE CAMP DETECTED
---------------------------------------------------------------
HOURLY ACTIVITY:
  Ship kills: 12
  Pod kills: 3
  Jumps: 456

ASSESSMENT:
  System is active but no concentrated gatecamp pattern.
  Some PvP activity - stay alert when transiting.
===============================================================
```

### Route Analysis

```
===============================================================
ARIA ROUTE GATECAMP ANALYSIS
---------------------------------------------------------------
ROUTE: Jita -> Amarr (9 jumps, high-sec)
---------------------------------------------------------------
SYSTEMS WITH ACTIVE CAMPS:

  NIARJA (0.5) - HIGH CONFIDENCE
    5 kills in 10 min | CODE. (Tornado fleet)
    Camp type: Alpha strike
    Last kill: 2 minutes ago

SYSTEMS WITH ELEVATED ACTIVITY:

  UEDAMA (0.5) - ELEVATED
    3 kills in 1 hour | No pattern detected

---------------------------------------------------------------
ROUTE RISK: ELEVATED

RECOMMENDATIONS:
  1. Avoid Niarja - active gatecamp
  2. Alternative: Route via Dodixie adds 6 jumps but avoids camp
  3. If transit required: Use scout or webbing alt
===============================================================
```

### Degraded Mode (No Real-Time Data)

When the RedisQ poller is not running or data is stale:

```
===============================================================
ARIA GATECAMP INTEL
---------------------------------------------------------------
SYSTEM: Niarja (0.5)
STATUS: REAL-TIME INTEL UNAVAILABLE
---------------------------------------------------------------
Note: Real-time killmail data is unavailable. Showing hourly
      aggregates only. Active gatecamps cannot be detected.

HOURLY ACTIVITY (from ESI):
  Ship kills: 47
  Pod kills: 12
  Jumps: 890

ASSESSMENT:
  High kill count suggests possible gatecamp activity.
  Exercise caution - recommend scouting before transit.
===============================================================
```

## Camp Type Identification

Based on attacker ship composition and kill patterns:

| Camp Type | Indicators | Countermeasures |
|-----------|------------|-----------------|
| Alpha Strike | Tornado, Talos, high damage | Tank won't help, use speed |
| Smartbomb | Battleships, pods killed | Warp to tactical, not gate |
| Tackle Fleet | Interceptors, dictors | Stabs, fast align |
| Blops Drop | Stealth bombers, blops | Intel channels, scouts |

## Confidence Levels

| Level | Criteria |
|-------|----------|
| HIGH | 3+ kills in 10 min, force asymmetry > 5:1, consistent attackers |
| MEDIUM | 2+ kills in 10 min, some pattern detected |
| LOW | Recent kills but no clear camp pattern |

## Watchlist Integration

When entity watchlists are configured (via `/watchlist`), gatecamp intel automatically flags attackers that match watched entities:

**Watchlist Indicators:**
- `⚠️ ON WATCHLIST` - Attacker corporation/alliance is on a watchlist
- `⚠️ WATCHLIST` - Kill involved a watched entity

**Checking Watchlist Status:**

Query watched entity kills in the system using:
```bash
uv run aria-esi redisq-watched --system <system_id> --minutes 60
```

**Enhanced Attacker Analysis (with watchlist):**
```
ATTACKER ANALYSIS:
  Corporations: CODE. ⚠️ ON WATCHLIST
                Goonswarm Federation
  Alliances: The Imperium ⚠️ ON WATCHLIST
  Ship types: Tornado (4), Thrasher (2)
```

**When to Show Watchlist Flags:**
1. Check all attacker corps/alliances against configured watchlists
2. Flag individual kills that have `watched_entity_match=1` in database
3. Prominently warn if camp is run by watched entities (war targets, known hostiles)

## Known Gatecamp Systems

These systems have historically high gatecamp activity:

**High-Sec Ganking:**
- Uedama (0.5) - Sivala gate
- Niarja (0.5) - Madirmilire gate
- Aufay (0.5) - Balle gate

**Low-Sec Pipes:**
- Tama (0.3) - Nourvukaiken gate
- Rancer (0.4) - Crielere gate
- Amamake (0.4) - Dal gate
- Old Man Star (0.3) - Villore gate

Include historical context in assessments for these systems.

## Behavior Notes

- **Never give false assurance** - "No active camp" means no recent kills, not guaranteed safety
- **Include alternatives** - Always suggest route alternatives when camps are detected
- **Time sensitivity** - Camp status can change in minutes; include timestamp
- **Graceful degradation** - If real-time unavailable, fall back to hourly data with clear warning
- **Scout recommendation** - For high-value cargo, always recommend scouting regardless of data

## Contextual Suggestions

After providing gatecamp intel, suggest related commands when appropriate:

| Context | Suggest |
|---------|---------|
| Camp detected on route | "Try `/route` with --safe flag for alternatives" |
| User planning to haul | "Check `/price` to evaluate if cargo justifies risk" |
| Low-sec system | "Run `/threat-assessment` for full tactical picture" |

---

## Persona Adaptation

This skill supports persona-specific overlays. When active persona has an overlay file, load additional context from:

```
personas/{active_persona}/skill-overlays/gatecamp.md
```

If no overlay exists, use the default (empire) framing above.
