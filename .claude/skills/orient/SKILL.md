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

## Data Authority

Sovereignty data follows the authority hierarchy defined in `dev/docs/ai-runtime/DATA_AUTHORITY.md`:

| Data Type | Source | Authority |
|-----------|--------|-----------|
| Alliance ID/Name | ESI `/sovereignty/map/` | Authoritative |
| Coalition membership | `coalitions.yaml` | Community (validated against ESI) |
| System security | Universe graph (SDE) | Authoritative |
| Activity data | ESI `/kills/`, RedisQ | Authoritative |

**Validation:** Coalition data is validated against ESI before loading into cache. Run `sov-validate` to verify.

## Required Tool Calls (MANDATORY)

Orientation intel MUST come from tool calls. Do NOT fabricate sovereignty, activity, or escape route data.

| Step | Call | Required For |
|------|------|-------------|
| 1 | `universe(action="local_area", origin="...", max_jumps=10, include_realtime=True)` | All orientation data: threats, sovereignty, hotspots, escape routes |
| 2 | `universe(action="systems", systems=["..."])` | Sovereignty details (only if not in local_area response) |

**The `local_area` response is the single source of truth for orientation.** Present only fields that exist in the response. If the response has no `sovereignty` field, do NOT add sovereignty data from training knowledge.

> **⚠️ HALLUCINATION GUARD:** Every system name, sovereignty claim, kill count, escape route, and threat level MUST come from the `local_area` response or other MCP calls made in this session. If a field is not in the tool response, it does not exist for this assessment. NEVER supplement tool data with training data knowledge.

> ❌ **NEVER** use `include_realtime=False` — this disables real-time gatecamp detection and recent kill alerts. The MCP default is `false`, so you MUST explicitly set `include_realtime=True`.

### Field → Source Mapping

| Output Field | Required Source | Tool Call |
|-------------|----------------|-----------|
| Origin system (name, security, region, constellation) | local_area response `origin` | `universe(action="local_area", origin="...", max_jumps=10, include_realtime=True)` |
| Threat level (LOW/MEDIUM/HIGH/EXTREME) | local_area response `threat_summary` | `universe(action="local_area", ...)` |
| Total kills within radius | local_area response `threat_summary` | `universe(action="local_area", ...)` |
| Active gatecamp warnings | local_area response (realtime) | `universe(action="local_area", ..., include_realtime=True)` |
| Sovereignty (alliance, coalition) | local_area response `sovereignty` or systems response | `universe(action="local_area", ...)` or `universe(action="systems", systems=[...])` |
| Hotspot systems (avoid list) | local_area response `hotspots` | `universe(action="local_area", ...)` |
| Quiet zones (stealth ops) | local_area response `quiet_zones` | `universe(action="local_area", ...)` |
| Ratting banks (content) | local_area response `ratting_banks` | `universe(action="local_area", ...)` |
| Escape routes (nearest safe) | local_area response `escape_routes` | `universe(action="local_area", ...)` |
| FW warzone data | local_area response `fw_systems` | `universe(action="local_area", ...)` |

## Data Sources

### MCP Tools (preferred)

If the `aria-universe` MCP server is connected, use the `universe` dispatcher:

```
universe(action="local_area", origin="ZZ-TOP", max_jumps=10, include_realtime=True)
```

**Response includes:**
- Origin system details (security, region, constellation)
- Sovereignty data (alliance, coalition) for null-sec systems
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

SOVEREIGNTY: [Alliance Ticker] Alliance Name
  Coalition: [Coalition Name] (if applicable)
  [Territorial context for threat assessment]

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

## Sovereignty Context (Null-Sec Only)

When the origin system is in null-sec (security <= 0.0), include sovereignty information:

### What to Show

1. **Owning Alliance** - Who holds sovereignty (from `systems` response `sovereignty.alliance_name`)
2. **Coalition** - If the alliance is part of a known coalition (from `sovereignty.coalition_name`)
3. **Territorial Threat Context** - Whether you're in hostile/neutral/friendly space

### Example Sovereignty Block

```
SOVEREIGNTY: [GSF] Goonswarm Federation
  Coalition: The Imperium
  Status: Hostile territory - expect organized response
```

### Threat Implications by Territory Type

| Territory | Implication |
|-----------|-------------|
| Major Coalition (Imperium, PanFam, FIRE) | Organized standing fleets, rapid response |
| Smaller Alliance | Variable response capability |
| NPC Null-sec | No player sovereignty - NPC presence only |
| Unclaimed | Disputed or recently lost - may be contested |

### Getting Sovereignty Data

Sovereignty is included in the `systems` response for null-sec systems:

```
universe(action="systems", systems=["1DQ1-A"])
```

Response includes:
```json
{
  "sovereignty": {
    "alliance_id": 1354830081,
    "alliance_name": "[GSF] Goonswarm Federation",
    "coalition_id": "imperium",
    "coalition_name": "The Imperium"
  }
}
```

## Faction Warfare Context

When `fw_systems` is present and non-empty in the `local_area` response, include FW warzone intel:

### FW Status Interpretation

| Status | Meaning | Tactical Implication |
|--------|---------|---------------------|
| `uncontested` | Stable ownership | Normal militia patrols |
| `contested` | Active plexing | Militia fleets likely, small gang PvP |
| `vulnerable` | Near system flip | Heavy militia activity, large fleets possible |

### Example FW Output Block

```
FACTION WARFARE WARZONE
│ System   │ Jumps │ Owner    │ Occupier  │ Status      │ Contested │
│ Tama     │ 0     │ Caldari  │ Gallente  │ contested   │ 45%       │
│ Kedama   │ 1     │ Caldari  │ Caldari   │ uncontested │ 12%       │
│ Enaluri  │ 2     │ Caldari  │ Gallente  │ vulnerable  │ 92%       │

⚠️ 1 vulnerable system nearby - expect heavy militia activity
```

### When to Show FW Data

- Always show when `fw_systems` contains entries
- Prioritize vulnerable and contested systems
- Include total FW system count if many are in range

## Anti-Patterns

❌ **WRONG:** Show "SOVEREIGNTY: [GSF] Goonswarm Federation / The Imperium" when `local_area` returned no sovereignty field
✅ **RIGHT:** Only show sovereignty data if it appears in the `local_area` or `systems` response

❌ **WRONG:** Present activity data for systems outside the `max_jumps` radius
✅ **RIGHT:** Only include systems returned by `local_area`

❌ **WRONG:** State "Region: Delve" or other regional context from training data memory
✅ **RIGHT:** Region name comes from the `local_area` response `origin.region` field

❌ **WRONG:** Add FW contestation percentages when no `fw_systems` data was returned
✅ **RIGHT:** FW data appears only when `fw_systems` is present and non-empty in the response

## Response Priority

When presenting results, prioritize:
1. **Immediate threats** - Active camps, extreme activity
2. **Sovereignty context** - Whose space you're in (null-sec only)
3. **Faction Warfare** - FW warzone status (low-sec FW systems)
4. **Escape routes** - How to get to safer space
5. **Tactical opportunities** - Quiet zones, ratting banks
6. **Context** - Regional info, border systems
