---
name: killmail
description: Analyze individual killmails with enriched tactical context
model: sonnet
category: tactical
triggers:
  - "/killmail"
  - "analyze killmail"
  - "zkillboard.com/kill/"
requires_pilot: false
has_persona_overlay: true
external_sources:
  - zkillboard.com
---

# ARIA Killmail Intel Module

## Input Formats

Accept these formats:
- Full URL: `https://zkillboard.com/kill/12345678/`
- Short URL: `zkillboard.com/kill/12345678`
- Raw ID: `12345678`

## Data Flow

1. Call `killmails(action="analyze", killmail_input=<url_or_id>)` — handles fetching, parsing, and enrichment in one call
2. If the MCP response contains unresolved type IDs, use `sde(action="item_info")` to resolve them
3. Present with persona voice

### Fallback (if MCP unavailable)

```bash
uv run aria-esi analyze-killmail https://zkillboard.com/kill/12345678/
uv run aria-esi analyze-killmail 12345678
# Short alias:
uv run aria-esi akm 12345678
```

## Response Format

```
═══════════════════════════════════════════════════════════════════
ARIA KILLMAIL ANALYSIS
───────────────────────────────────────────────────────────────────
KILL: 12345678 | SYSTEM: Tama (0.3) | 2026-01-15 14:32
───────────────────────────────────────────────────────────────────

VICTIM:
  Pilot: VictimName [CORP]
  Ship: Proteus (12.4B ISK)
  Alliance: Example Alliance

FITTING ANALYSIS:
  Type: Blaster/AB brawler
  Tank: 32k EHP armor buffer
  DPS: ~650 (hybrid)
  Notes: Expensive deadspace tank, limited range

ATTACKERS: 8 pilots
  Corp: Snuffed Out (6/8)
  Ships: 2x Loki, 3x Legion, 2x Proteus, 1x Curse

  Final Blow: AttackerName (Legion)

CONTEXT:
  ⚠️ Part of active gatecamp (3 kills in 10 min)
  System has 12 kills in last hour

───────────────────────────────────────────────────────────────────
https://zkillboard.com/kill/12345678/
═══════════════════════════════════════════════════════════════════
```

## Error Handling

### Kill Not Found

```
Kill ID 12345678 not found on zKillboard.

Possible reasons:
• Invalid kill ID
• Kill hasn't synced yet (wait a few minutes)
• Kill may be very old (zKillboard prunes old data)
```

### API Error

```
Unable to fetch killmail data.

Try again in a moment, or check the URL at:
https://zkillboard.com/kill/12345678/
```

## Disambiguation

`/killmail` analyzes any public kill by URL/ID (no auth required). `/killmails` shows your personal kill/loss history (requires ESI auth).
