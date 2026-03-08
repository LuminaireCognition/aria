---
name: killmails
description: Kill and loss history analysis. Post-mortem on ship losses to understand what killed you and how to improve survivability.
model: haiku
category: tactical
triggers:
  - "/killmails"
  - "what killed me"
  - "how did I die"
  - "show my losses"
  - "analyze my last loss"
  - "killmail analysis"
  - "loss history"
requires_pilot: true
esi_scopes:
  - esi-killmails.read_killmails.v1
---

# ARIA Killmail Analysis Module

## Hallucination Guard

**All killmail data MUST come from MCP tool calls.** Do not reconstruct, assume, or recall kill details from training data. If a tool call fails, say so -- never fabricate killmail information.

## Mandatory Tool Calls

| Query Type | MCP Dispatcher Call |
|------------|---------------------|
| Recent kills/losses | `killmails(action="recent", limit=N)` |
| Query by system/time | `killmails(action="query", systems=["..."], hours=N)` |
| Query by character | `killmails(action="query", character_id=12345)` |
| Kill statistics | `killmails(action="stats", systems=["..."], group_by="system"\|"hour"\|"corporation")` |
| Analyze specific kill | `killmails(action="analyze", killmail_input="<zkill_url_or_id>")` |
| **CLI fallback** | `uv run aria-esi killmails` / `uv run aria-esi analyze-killmail <url>` |

Use MCP dispatchers as the primary path. Fall back to CLI only if MCP is unavailable.

## Response Format

### Kill/Loss List

```
RECENT LOSSES: 3 | RECENT KILLS: 7

LOSSES:
  2026-01-15 14:32 | Venture | Tama (0.3) | 5 attackers | 12,450 dmg
  2026-01-14 22:15 | Imicus | Hek (0.5) | 1 attacker | 3,200 dmg

KILLS:
  2026-01-15 16:00 | Serpentis Frigate | Masalle (0.9) | Solo
```

### Detailed Loss Analysis

```
KILLMAIL: 12345678
TIME: 2026-01-15 14:32:18 UTC
SYSTEM: Tama (0.3)

VICTIM: Venture | 12,450 dmg taken

ATTACKERS: 5 (all players)
  1. PirateName [YARR] - Thrasher - 6,200 dmg (Final Blow)
  2. GankAlt1 - Catalyst - 3,100 dmg
  ...

DAMAGE: kin 45% / therm 35% / exp 20%

ANALYSIS:
Coordinated gank by 4 Catalysts + Thrasher. Tama (0.3) is a known hotspot.

RECOMMENDATIONS:
- Keep aligned and D-scan in low-sec
- Avoid Tama or fit for survivability
```

### Pattern Analysis

```
LOSS PATTERNS (Last 90 days) — 8 losses

PvP: 5 (62%) | PvE: 3 (38%)
Ships lost: Venture x3, Imicus x2, Catalyst x2, Vexor x1
Dangerous systems: Tama (2), Auviken (1), Hek (1)

RECOMMENDATIONS:
- Most losses to players — improve D-scan vigilance, safer routes
- 3 Ventures lost — review fit or try a different hull
```

## Experience-Based Adaptation

Adapt verbosity to pilot experience: new players get explanations of what killmails are, damage type meanings, and specific module suggestions. Veterans get terse summaries (e.g., "5x Cat gank | Tama | kin/therm | alpha'd").

## Contextual Suggestions

After providing killmail data, suggest ONE related command when contextually relevant:

| Context | Suggest |
|---------|---------|
| Died to NPC pirates | `/mission-brief` for damage profiles |
| Died in low-sec | `/threat-assessment` before returning |
| Lost expensive implants | `/clones` to track implant locations |
| Fit could be improved | `/fitting` for an optimized build |

## Learning Integration

- **Before risky operations:** If pilot discusses returning to a system where they recently died, warn about the prior loss and suggest caution or alternate routes.
- **When fitting ships:** Reference past loss damage profiles to prioritize resistances in suggested fits.

## Error Handling

### Store Not Initialized / Poller Not Running

If `killmails(action="query")`, `killmails(action="stats")`, or `killmails(action="recent")` returns an error about the store not being initialized or no data available, the real-time killmail poller is not running.

**Recovery:**
1. **Individual killmail analysis still works** -- use `killmails(action="analyze", killmail_input="<zkillboard_url>")` for specific kills
2. **Suggest zKillboard** for browsing: `https://zkillboard.com/character/{character_id}/`
3. **To enable the poller:** `uv run aria-esi redisq-start` (requires configuration)

Do NOT retry query/stats/recent -- they will keep failing until the poller is started.

### No Killmails Found

No recent kills or losses. The pilot either hasn't lost ships recently, hasn't scored kills, or killmails are older than the query window. NPC-only kills do not generate killmails unless a player is also involved.

### Missing Scope

Killmail access requires ESI authorization with `esi-killmails.read_killmails.v1`. Direct pilot to: `uv run aria-esi setup`

### Incomplete Data (Missing ESI Details)

If kill records show `has_esi_details: false` or `system_id: null`:
- **Present what IS available:** timestamps, ISK values, zkb metadata (NPC/solo flags), ship type IDs
- **Acknowledge gaps:** "System and attacker details unavailable — ESI enrichment pending"
- **Do NOT redirect entirely to zKillboard** — use the available data first
- **Suggest:** "For full details on a specific kill, use `/killmail <zkill_url>`" (the analyze action fetches ESI directly)

## DO NOT

- **DO NOT** recall or fabricate killmail data from training data -- always use tool calls
- **DO NOT** speculate about kills that were not returned by MCP
- **DO NOT** present damage type analysis without actual killmail data to back it up
