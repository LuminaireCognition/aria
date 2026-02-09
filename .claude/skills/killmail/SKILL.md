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

## Purpose

Analyze individual killmails from zKillboard URLs or kill IDs. Provides enriched tactical context including ship fitting analysis, attacker composition, and gatecamp detection. This differs from `/killmails` which shows your personal kill/loss history.

## When to Use

- User pastes a zKillboard URL
- User asks to "analyze killmail [id]"
- User wants intel on a specific kill
- Investigating gatecamp activity

## Input Formats

Accept these formats:
- Full URL: `https://zkillboard.com/kill/12345678/`
- Short URL: `zkillboard.com/kill/12345678`
- Raw ID: `12345678`

## Data Flow

1. **Parse Input** → Extract kill ID from URL or raw input
2. **Fetch from zKillboard** → `https://zkillboard.com/api/killID/{id}/`
   - Returns: kill hash, zkb metadata (value, points, NPC flag)
3. **Fetch from ESI** → `GET /v1/killmails/{id}/{hash}/`
   - Returns: Full killmail with victim, attackers, items
4. **Enrich Data** → Use SDE for ship/module names
5. **Cross-reference** → Check threat cache for gatecamp context
6. **Present** → Format with persona voice

## CLI Command

```bash
uv run aria-esi killmail https://zkillboard.com/kill/12345678/
uv run aria-esi killmail 12345678
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

## Implementation

### URL Parsing

```python
import re

def parse_killmail_input(input_str: str) -> int | None:
    """Extract kill ID from various input formats."""
    # Try raw ID first
    if input_str.isdigit():
        return int(input_str)

    # Try URL patterns
    match = re.search(r'kill/(\d+)', input_str)
    if match:
        return int(match.group(1))

    return None
```

### zKillboard API

```bash
# Get kill data (includes hash and zkb metadata)
curl https://zkillboard.com/api/killID/12345678/
```

Response:
```json
[{
  "killmail_id": 12345678,
  "killmail_time": "2026-01-15T14:32:18Z",
  "solar_system_id": 30002813,
  "victim": {...},
  "attackers": [...],
  "zkb": {
    "hash": "abc123...",
    "totalValue": 12400000000.00,
    "points": 42,
    "npc": false
  }
}]
```

### ESI Killmail

```bash
# Get full killmail with fitting
curl https://esi.evetech.net/v1/killmails/12345678/abc123.../?datasource=tranquility
```

### SDE Enrichment

Use `sde(action="item_info")` to resolve:
- Ship type ID → Name
- Module type IDs → Names
- System ID → Name, security

### Threat Cache Integration

Check for gatecamp context:
```python
from aria_esi.services.redisq.threat_cache import get_threat_cache

cache = get_threat_cache()
gatecamp = cache.get_gatecamp_status(system_id)
activity = cache.get_activity_summary(system_id)
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

## Differences from /killmails

| Feature | /killmail | /killmails |
|---------|-----------|------------|
| Input | Any kill URL/ID | Your character only |
| Source | zKillboard public API | ESI authenticated |
| Auth | Not required | Requires ESI scope |
| Use case | Intel on any kill | Your personal history |
| Context | Gatecamp detection | Loss patterns |

## Related Commands

After presenting killmail, suggest contextually:

| Context | Suggest |
|---------|---------|
| Kill in dangerous system | `/threat-assessment {system}` |
| Expensive fitting | `/fitting` for similar builds |
| Part of gatecamp | `/gatecamp {system}` for current status |
| Watched entity involved | `/watchlist` to track them |
