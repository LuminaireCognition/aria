---
name: route
description: Calculate safe travel routes between EVE Online systems. Use for route planning, security analysis, or navigation assistance.
model: haiku
category: tactical
triggers:
  - "/route"
  - "route from [origin] to [destination]"
  - "how do I get to [system]"
  - "path to [system]"
  - "navigate to [system]"
  - "safest route to [system]"
  - "plot course to [system]"
requires_pilot: false
---

# ARIA Route Planning Module

## Purpose
Calculate optimal routes between solar systems with security preferences. Uses ESI route endpoint (public, no auth required) to provide navigation intelligence.

## Trigger Phrases
- "/route"
- "route from [origin] to [destination]"
- "how do I get to [system]"
- "path to [system]"
- "navigate to [system]"
- "safest route to [system]"
- "shortest route to [system]"
- "plot course to [system]"

## Command Syntax

```
/route <origin> <destination> [--safe|--shortest|--risky]
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

## Data Sources (Fallback Chain)

Route data can be obtained from multiple sources. Use in order of preference:

### 1. MCP Tools (preferred if available)

If the `aria-universe` MCP server is connected, use the `universe_route` tool:

```
universe_route(origin="Jita", destination="Amarr", mode="safe")
```

**Advantages:** Sub-millisecond response, security analysis included, system avoidance support.

### 2. CLI Commands (fallback)

If MCP tools are not available, use the `aria-esi route` CLI:

```bash
uv run aria-esi route Jita Amarr --safe
```

### 3. ESI Endpoint (last resort)

For cases where local graph is unavailable:

**Endpoint:** `GET /route/{origin}/{destination}/`
**Authentication:** None required (public endpoint)
**Cache:** 86400 seconds (24 hours)

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `origin` | integer | Origin solar system ID |
| `destination` | integer | Destination solar system ID |
| `flag` | string | Route preference: `shortest`, `secure`, `insecure` |
| `avoid` | array | System IDs to avoid (max 100) |
| `connections` | array | Additional connections to consider |

### Response

Returns array of solar system IDs representing the route, in order from origin to destination.

## Activity Data Integration

Route displays **MUST** include live activity data from the last hour. After calculating the route, fetch activity for all systems:

```
universe(action="activity", systems=["System1", "System2", ...], include_realtime=True)
```

This provides:
- `ship_kills` → Ships column
- `pod_kills` → Pods column
- `ship_jumps` → Jumps column

**Cache behavior:** Activity data refreshes every ~10 minutes. ESI aggregates hourly.

### Real-Time Gatecamp Detection

When `include_realtime=True` returns gatecamp data for systems on the route, display alerts in the Notes column:

**Gatecamp Flag Format:**
```
⚠️ **ACTIVE CAMP** (3/10min, HIGH)
```

Format: `(kills in last 10 min, confidence level)`

**Confidence Levels:**
- **HIGH** - Multiple kills in short window, force asymmetry detected
- **MEDIUM** - Sustained kills but lower density
- **LOW** - Some kills but pattern unclear

**Example Route Table with Gatecamp:**

| System | Sec | Ships | Pods | Jumps | Notes |
|--------|-----|------:|-----:|------:|-------|
| Jita | 0.95 | 1 | 0 | 4521 | Trade hub |
| Perimeter | 0.96 | 0 | 0 | 3201 | |
| Urlen | 0.93 | 0 | 0 | 892 | |
| Sirppala | 0.55 | 2 | 1 | 456 | Border system |
| Niarja | 0.50 | 5 | 3 | 890 | ⚠️ **ACTIVE CAMP** (3/10min, HIGH) |
| Madirmilire | 0.55 | 0 | 0 | 412 | |
| Amarr | 0.99 | 0 | 0 | 2103 | Trade hub |

**When to Escalate Warnings:**
- If any system has an active gatecamp, add a warning block at the top of the route response
- Include suggested alternatives if the camped system is avoidable

## System Name Resolution

Users provide system names, not IDs. Resolution workflow:

1. **Name to ID:** `POST /universe/ids/` with `["System Name"]`
   - Returns: `{"systems": [{"id": 30000142, "name": "Jita"}]}`

2. **ID to Info:** `GET /universe/systems/{id}/`
   - Returns: System name, security status, constellation, region

## Response Format

### Standard Response (rp_level: off or lite)

```markdown
## Route: Dodixie → Jita

**Mode:** Safest Route (high-sec only)
**Jumps:** 14

| System | Sec | Ships | Pods | Jumps | Notes |
|--------|-----|------:|-----:|------:|-------|
| Dodixie | 0.87 | 0 | 0 | 1203 | Trade hub |
| Botane | 0.84 | 0 | 0 | 412 | |
| ... | ... | ... | ... | ... | |
| Jita | 0.95 | 1 | 0 | 4521 | Trade hub |

**Security Summary:**
- High-sec (1.0-0.5): 14 systems
- Low-sec (0.4-0.1): 0 systems
- Null-sec (≤0.0): 0 systems

*Activity data from last hour. Route cached 24h.*
```

### Formatted Response (rp_level: moderate or full)

```
═══════════════════════════════════════════════════════════════════
ARIA ROUTE INTELLIGENCE
───────────────────────────────────────────────────────────────────
ORIGIN:       Dodixie (0.87) - Sinq Laison
DESTINATION:  Jita (0.95) - The Forge
ROUTE MODE:   Secure (high-sec priority)
TOTAL JUMPS:  14
───────────────────────────────────────────────────────────────────
JUMP  SYSTEM          SEC   SHIPS  PODS  JUMPS   NOTES
─────────────────────────────────────────────────────────────────
  1   Dodixie         0.87      0     0   1203   Trade hub
  2   Botane          0.84      0     0    412
  3   Ourapheh        0.73      0     0    287
 ...
 14   Jita            0.95      1     0   4521   Trade hub
───────────────────────────────────────────────────────────────────
SECURITY BREAKDOWN:
  High-sec (≥0.5):  14 jumps
  Low-sec (0.1-0.4): 0 jumps
  Null-sec (≤0.0):   0 jumps

THREAT ASSESSMENT: MINIMAL
No low-security or null-security systems on this route.
───────────────────────────────────────────────────────────────────
Route data cached for 24 hours. Real-time conditions may vary.
═══════════════════════════════════════════════════════════════════
```

### Formatted Response with Gatecamp Warning

When real-time data detects an active gatecamp on the route:

```
═══════════════════════════════════════════════════════════════════
ARIA ROUTE INTELLIGENCE
───────────────────────────────────────────────────────────────────
ORIGIN:       Jita (0.95) - The Forge
DESTINATION:  Amarr (0.99) - Domain
ROUTE MODE:   Secure (high-sec priority)
TOTAL JUMPS:  9
───────────────────────────────────────────────────────────────────
⚠️ ACTIVE GATECAMP DETECTED ON ROUTE
  System: Niarja (0.5)
  Kills: 5 in last 10 minutes
  Attackers: CODE. (Tornado, Thrasher)
  Consider: Alternative route via Dodixie (+6 jumps)
───────────────────────────────────────────────────────────────────
JUMP  SYSTEM          SEC   SHIPS  PODS  JUMPS   NOTES
─────────────────────────────────────────────────────────────────
  1   Jita            0.95      1     0   4521   Trade hub
  2   Perimeter       0.96      0     0   3201
  ...
  5   Niarja          0.50      5     3    890   ⚠️ **ACTIVE CAMP**
  ...
  9   Amarr           0.99      0     0   2103   Trade hub
───────────────────────────────────────────────────────────────────
THREAT ASSESSMENT: ELEVATED
Active gatecamp detected. Recommend alternative route or scout.
═══════════════════════════════════════════════════════════════════
```

### Compact Response (for short routes)

For routes ≤5 jumps, use inline format:

```
Route: Dodixie → Botane → Ourapheh → Algogille (3 jumps, all high-sec)
```

## Threat Level Integration

Based on route security composition:

| Composition | Threat Level | Advisory |
|-------------|--------------|----------|
| All high-sec (≥0.5) | MINIMAL | Standard autopilot safe |
| Contains 0.5 systems | ELEVATED | Possible gank points, stay alert |
| Contains low-sec | HIGH | Manual piloting recommended, fit for survival |
| Contains null-sec | CRITICAL | Extreme caution, scout ahead or use covops |

## Route-Level Gatecamp Analysis

For routes through dangerous space (low-sec, 0.5 systems), consider using the `gatecamp_risk` action for comprehensive analysis:

```
universe(action="gatecamp_risk", origin="Jita", destination="Amarr", mode="safe")
```

This provides:
- Per-system gatecamp detection with confidence levels
- Route-wide risk summary
- Attacker analysis (corporations, ship types)
- Recent kill details

**When to Suggest Gatecamp Analysis:**
- Route passes through known gank systems (Uedama, Niarja)
- Route contains low-sec segments
- User is hauling valuable cargo
- User explicitly asks about safety

**Integration Note:** Real-time gatecamp detection is automatic when the RedisQ poller is healthy. The activity call with `include_realtime=True` includes gatecamp data in the response. For deeper analysis (attacker details, kill timeline), use the dedicated `gatecamp_risk` action.

## Error Handling

### System Not Found

```json
{
  "error": "system_not_found",
  "message": "Could not find system: Jota",
  "suggestions": ["Jita", "Jotain", "Josameto"],
  "query_timestamp": "2026-01-15T10:30:00Z"
}
```

### No Route Available

```json
{
  "error": "no_route",
  "message": "No route available from Jita to J123456",
  "reason": "Wormhole systems are not connected via stargates",
  "query_timestamp": "2026-01-15T10:30:00Z"
}
```

### Same System

```json
{
  "error": "same_system",
  "message": "Origin and destination are the same system",
  "query_timestamp": "2026-01-15T10:30:00Z"
}
```

## Experience-Based Adaptation

### New Players

```
Route: Dodixie → Jita (14 jumps)

This route passes through HIGH-SECURITY space only (security 0.5 or
higher). CONCORD will respond to any attacks, making this relatively
safe for autopilot travel.

Security Tip: Even in high-sec, valuable cargo can attract "suicide
gankers" who accept ship loss to destroy you. For expensive hauling,
consider a tankier ship or splitting cargo across trips.

[Full system list...]
```

### Veterans

```
Dodixie → Jita | 14j | all HS | AP safe
Lowest sec: 0.5 (gank possible) | ETA: ~7min AP
```

## Script Command

```bash
# Basic route
uv run aria-esi route Dodixie Jita

# Safe route (high-sec only)
uv run aria-esi route Dodixie Jita --safe

# Shortest route (may include low/null)
uv run aria-esi route Dodixie Jita --shortest

# Risky route (prefers low/null)
uv run aria-esi route Amarr Jita --risky

# From current location (requires ESI auth)
uv run aria-esi route Jita
```

## JSON Output Format

```json
{
  "query_timestamp": "2026-01-15T10:30:00Z",
  "volatility": "stable",
  "origin": {
    "system_id": 30002659,
    "name": "Dodixie",
    "security": 0.87,
    "region": "Sinq Laison"
  },
  "destination": {
    "system_id": 30000142,
    "name": "Jita",
    "security": 0.95,
    "region": "The Forge"
  },
  "route_mode": "secure",
  "total_jumps": 14,
  "systems": [
    {"system_id": 30002659, "name": "Dodixie", "security": 0.87, "region": "Sinq Laison"},
    {"system_id": 30002660, "name": "Botane", "security": 0.84, "region": "Sinq Laison"},
    ...
  ],
  "security_summary": {
    "high_sec": 14,
    "low_sec": 0,
    "null_sec": 0,
    "lowest_security": 0.5,
    "threat_level": "MINIMAL"
  }
}
```

## Contextual Suggestions

After providing route, suggest related commands when appropriate:

| Context | Suggest |
|---------|---------|
| Route contains low-sec | "Run `/threat-assessment` for the dangerous segments" |
| Long route (>15 jumps) | "Consider `/fitting` for a fast travel ship" |
| Route ends in mission hub | "Use `/mission-brief` when you arrive" |

## Behavior Notes

- **No Auth Required:** Route calculation is a public endpoint
- **Cache Awareness:** Routes are cached for 24 hours by ESI
- **Current Location:** If origin omitted, attempt ESI location query (requires auth)
- **Fuzzy Matching:** If exact system name not found, suggest close matches
- **Wormhole Systems:** J-space systems have no stargate routes - explain this
- **Pochven:** Triglavian systems have limited connectivity - warn if involved

## Integration with Threat Assessment

When route contains dangerous systems, offer to run `/threat-assessment`:

```
This route passes through Rancer (0.4 low-sec) - a known pirate hotspot.

For detailed threat analysis of dangerous segments, I can run
`/threat-assessment Rancer` to evaluate current risk factors.
```

## DO NOT

- **DO NOT** recommend routes through Niarja without warning (destroyed system)
- **DO NOT** ignore Pochven systems (limited connectivity)
- **DO NOT** assume wormhole routes exist (J-space has no stargates)
- **DO NOT** cache route results locally (ESI handles caching)

---

## Persona Adaptation

This skill supports persona-specific overlays. When active persona has an overlay file, load additional context from:

```
personas/{active_persona}/skill-overlays/route.md
```

If no overlay exists, use the default (empire) framing above.
