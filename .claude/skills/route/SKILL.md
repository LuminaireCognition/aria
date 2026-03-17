---
name: route
description: Calculate safe travel routes between EVE Online systems. Use for route planning, security analysis, or navigation assistance.
category: tactical
triggers:
  - "/route"
  - "route from [origin] to [destination]"
  - "how do I get to [system]"
  - "path to [system]"
  - "navigate to [system]"
  - "safest route to [system]"
  - "plot course to [system]"
  - "route avoiding [system]"
  - "route but not through [system]"
requires_pilot: false
argument-hint: "[<origin>] <destination> [--safe|--shortest]"
allowed-tools: [Read, Grep, Glob, "mcp__aria-universe__universe"]
preferred_max_lines: 45
---

# ARIA Route Planning Module

## Command Syntax

```
/route <origin> <destination> [--safe|--shortest|--risky] [--avoid <sys1,sys2,...>]
/route <destination>                    # Uses current location as origin
```

### Arguments

| Argument | Description |
|----------|-------------|
| `origin` | Starting system (name or ID). If omitted, infers from ESI location. |
| `destination` | Target system (name or ID). Required. |

### Flags

| Flag | ESI Parameter | Description |
|------|---------------|-------------|
| `--safe` | `secure` | Prefer high-sec routes, avoid low/null even if longer |
| `--shortest` | `shortest` | Shortest path regardless of security (default) |
| `--risky` | `insecure` | Prefer low-sec/null routes (faster through dangerous space) |
| `--avoid` | `avoid_systems` | Exclude specific systems from route (e.g., `--avoid Uedama,Niarja`) |

### Safe-Mode Intent Detection

When the user's query contains "safe", "safest", "secure", or "safely", use `mode="safe"` as the **primary** route. Show the shortest route as a brief alternative ("Shortest alternative: N jumps via [key system]"). Do not bury the safe route in prose while presenting the shortest route as the primary result.

### Avoiding Systems

To exclude specific systems from a route (e.g., known gank pipes):

```
/route Dodixie Jita --avoid Uedama
```

Maps to: `universe(action="route", origin="Dodixie", destination="Jita", avoid_systems=["Uedama"])`

Multiple systems: `/route Dodixie Jita --avoid Uedama,Niarja`

## Activity Data Integration

Route displays **MUST** include live activity data from the last hour. After calculating the route, fetch activity for all systems:

```
universe(action="activity", systems=["System1", "System2", ...], include_realtime=True)
```

This provides:
- `ship_kills` -> Ships column
- `pod_kills` -> Pods column
- `ship_jumps` -> Jumps column

**Cache behavior:** Activity data refreshes every ~10 minutes. ESI aggregates hourly.

### Efficiency: Single Bulk Call

**CRITICAL:** Always fetch activity for ALL route systems in a single call. Do NOT fetch activity or system data one system at a time. The `universe(action="route")` response already returns system names and security -- you only need the bulk activity call for Ships/Pods/Jumps columns.

### Real-Time Gatecamp Detection

When `include_realtime=True` returns gatecamp data for systems on the route, display alerts in the Notes column:

**Gatecamp Flag Format:** `ACTIVE CAMP (kills in last 10 min, confidence level)`

**Confidence Levels:**
- **HIGH** - Multiple kills in short window, force asymmetry detected
- **MEDIUM** - Sustained kills but lower density
- **LOW** - Some kills but pattern unclear

If any system has an active gatecamp, add a warning block at the top of the route response with suggested alternatives if the camped system is avoidable.

## Faction Warfare Warzone Warnings

Route results may include FW-related warnings when the route passes through warzone systems. These appear in the `warnings` list of the route result.

| Warning | Meaning |
|---------|---------|
| "Route passes through N FW warzone system(s)" | General FW presence on route |
| "Vulnerable FW system(s): ..." | Systems near ownership flip - high militia activity |
| "Contested FW system(s): ..." | Systems with active plexing - militia fleets likely |

Add FW context to the route table Notes column (e.g., "FW warzone (contested)").

## Response Format

```markdown
## Route: [Origin] -> [Destination]

**Mode:** [Route mode description]
**Jumps:** [N]

| System | Sec | Ships | Pods | Jumps | Notes |
|--------|-----|------:|-----:|------:|-------|
| [system] | [sec] | [n] | [n] | [n] | [trade hub / border / FW / gatecamp] |

**Security Summary:**
- High-sec (1.0-0.5): [N] systems
- Low-sec (0.4-0.1): [N] systems
- Null-sec (<=0.0): [N] systems

*Activity data from last hour. Route cached 24h.*
```

**RP framing (rp_level: moderate or full):** Use box-drawing frame characters around the response.

**Gatecamp warning block:** When active gatecamps detected, prepend a warning block before the route table showing the camped system, kill count, attacker info, and suggested alternative route.

**Compact format (routes <= 5 jumps):** Use inline: `Route: A -> B -> C (3 jumps, all high-sec)`

## Threat Level Integration

Based on route security composition:

| Composition | Threat Level | Advisory |
|-------------|--------------|----------|
| All high-sec (>=0.5) | MINIMAL | Standard autopilot safe |
| Contains 0.5 systems | ELEVATED | Possible gank points, stay alert |
| Contains low-sec | HIGH | Manual piloting recommended, fit for survival |
| Contains null-sec | CRITICAL | Extreme caution, scout ahead or use covops |

## Route-Level Gatecamp Analysis

For routes through dangerous space (low-sec, 0.5 systems), consider using the `gatecamp_risk` action for comprehensive analysis:

```
universe(action="gatecamp_risk", origin="Jita", destination="Amarr", mode="safe")
```

This provides per-system gatecamp detection with confidence levels, route-wide risk summary, attacker analysis, and recent kill details. Real-time gatecamp detection is automatic when the RedisQ poller is healthy. For deeper analysis, use the dedicated `gatecamp_risk` action.

## Experience-Based Adaptation

New players: explain security concepts, warn about suicide ganking in high-sec, provide full system list. Veterans: compact one-line format with just jump count, security summary, and ETA.

## Error Handling

### System Not Found

Provide fuzzy match suggestions from the MCP response.

### No Route Available

Explain that wormhole systems have no stargate routes and Pochven has limited connectivity.

### Same System

Note that origin and destination are the same.

## Script Command

```bash
uv run aria-esi route Dodixie Jita
uv run aria-esi route Dodixie Jita --safe
uv run aria-esi route Dodixie Jita --shortest
uv run aria-esi route Amarr Jita --risky
uv run aria-esi route Dodixie Jita --avoid Uedama
```

## Output Rules

- Keep response under 30 lines (route table + summary + threat advisory)
- Append a one-line `Sources:` footer listing MCP calls made

## Behavior Notes

- **Pochven:** Triglavian systems have limited connectivity - warn if route involves them

## DO NOT

- **DO NOT** recommend routes through Niarja without warning (destroyed system)
- **DO NOT** ignore Pochven systems (limited connectivity)
- **DO NOT** assume wormhole routes exist (J-space has no stargates)
- **DO NOT** cache route results locally (ESI handles caching)
- **DO NOT** fetch activity or system data one system at a time -- always use bulk calls
