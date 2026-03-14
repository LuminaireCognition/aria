---
name: orient
description: Local area intel for orientation in unknown space. Use after wormhole jumps, filaments, or when dropped into unfamiliar territory.
model: sonnet
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
allowed-tools: [Read, Grep, Glob, "mcp__aria-universe__universe"]
preferred_max_lines: 45
---

# ARIA Local Orientation Module

## Data Authority

Data authority hierarchy follows `dev/docs/ai-runtime/DATA_TRUST.md`. Coalition data is validated against ESI before loading into cache; run `sov-validate` to verify.

## Required Tool Calls (MANDATORY)

Orientation intel MUST come from tool calls. Do NOT fabricate sovereignty, activity, or escape route data.

| Step | Call | Required For |
|------|------|-------------|
| 1 | `universe(action="local_area", origin="...", max_jumps=10, include_realtime=True)` | All orientation data: threats, sovereignty, hotspots, escape routes |
| 2 | `universe(action="systems", systems=["..."])` | Sovereignty details (only if not in local_area response) |

**The `local_area` response is the single source of truth for orientation.** Present only fields that exist in the response. If the response has no `sovereignty` field, do NOT add sovereignty data from training knowledge.

> **[!] HALLUCINATION GUARD:** Every system name, sovereignty claim, kill count, escape route, and threat level MUST come from the `local_area` response or other MCP calls made in this session. If a field is not in the tool response, it does not exist for this assessment. NEVER supplement tool data with training data knowledge.

> ❌ **NEVER** use `include_realtime=False` — this disables real-time gatecamp detection and recent kill alerts. The MCP default is `false`, so you MUST explicitly set `include_realtime=True`.

> **Failure handling:** If `local_area` fails or returns an error, surface the failure explicitly: "Orientation data unavailable: [error]. Cannot assess this system without live MCP data." Do NOT fabricate threat levels, sovereignty, or escape routes from training knowledge.

All output fields come from the `local_area` response. Key response fields: `origin`, `threat_summary`, `sovereignty`, `hotspots`, `quiet_zones`, `ratting_banks`, `escape_routes`, `fw_systems`. If `sovereignty` is absent from `local_area`, supplement via `universe(action="systems", systems=[...])`.

## Output Format

Present sections in this order. FW warzone data follows sovereignty when present. Omit empty sections.

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

- **Hotspots (Avoid or Hunt):** Systems with 5+ PvP kills in the last hour.
- **Quiet Zones (Stealth Ops):** Systems with 0 PvP kills.
- **Ratting Banks (Content):** Systems with 100+ NPC kills.

## Real-Time Enhancement

When `include_realtime=True` and the RedisQ poller is healthy:
- Active gatecamp detection (kill clustering analysis)
- Minute-level kill data instead of hourly
- Force asymmetry detection (camps vs fleet fights)

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

[!] 1 vulnerable system nearby - expect heavy militia activity
```

### When to Show FW Data

- Always show when `fw_systems` contains entries
- Prioritize vulnerable and contested systems
- Include total FW system count if many are in range

## Output Rules

- System table: cap at 8 nearest systems, sort by jumps
- Target: ≤30 lines
- Append a one-line `Sources:` footer listing MCP calls made

## Anti-Patterns

❌ **WRONG:** Present activity data for systems outside the `max_jumps` radius
✅ **RIGHT:** Only include systems returned by `local_area`

❌ **WRONG:** State "Region: Delve" or other regional context from training data memory
✅ **RIGHT:** Region name comes from the `local_area` response `origin.region` field
