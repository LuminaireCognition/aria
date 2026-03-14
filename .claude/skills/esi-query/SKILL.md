---
name: esi-query
description: Query EVE Online ESI API for live character data. Use when capsuleer asks for current location, skills, wallet, or standings.
model: haiku
category: system
triggers:
  - "/esi-query"
  - "where am I"
  - "current location"
  - "what ship am I in"
  - "wallet balance"
  - "how much ISK"
  - "check my skills"
  - "my standings"
  - "my blueprints"
requires_pilot: true
data_sources:
  - userdata/pilots/{active_pilot}/profile.md
  - userdata/pilots/{active_pilot}/industry/blueprints.md
esi_scopes:
  - esi-location.read_location.v1
  - esi-location.read_ship_type.v1
  - esi-wallet.read_character_wallet.v1
  - esi-characters.read_standings.v1
  - esi-skills.read_skills.v1
  - esi-characters.read_blueprints.v1
argument-hint: "<query>"
injected_prerequisites:
  - .claude/skills/_shared/esi-error-handling.md
---

# ARIA GalNet Interface Module (ESI Integration)

## CRITICAL: Data Volatility

This skill handles data that can become stale in **seconds**. ARIA must:

1. **Always display the query timestamp** prominently
2. **Include a staleness warning** for volatile data
3. **Never cache volatile results** to files
4. **Never reference query results in future turns** without re-querying

### Volatility Classifications

| Query | Volatility | Staleness Warning Required |
|-------|------------|---------------------------|
| `location` | **VOLATILE** | YES - "as of [timestamp]" |
| `wallet` | **VOLATILE** | YES - "as of [timestamp]" |
| `profile` | Semi-stable | Optional |
| `standings` | Semi-stable | Optional |
| `blueprints` | Semi-stable | Optional - update blueprint_library.md after |

## Prerequisites (When ESI Is Desired)
If capsuleer wants live GalNet data, they need valid ESI credentials:
- Path: `credentials/{character_id}.json`

## ESI Wrapper Commands

**Use the `aria-esi` wrapper script** for all ESI operations:

```bash
# Volatile data (ALWAYS show timestamp)
uv run aria-esi location    # Current system/ship - VOLATILE
uv run aria-esi wallet      # ISK balance - VOLATILE

# Semi-stable data
uv run aria-esi profile     # Character + standings
uv run aria-esi standings   # Faction standings
uv run aria-esi blueprints  # Owned BPOs and BPCs

# Token management
uv run aria-esi refresh --check
```

### Blueprints Query

Use `blueprints` to refresh the capsuleer's BPO/BPC inventory:

```bash
uv run aria-esi blueprints
```

Returns JSON with:
- `bpo_count` / `bpc_count` - totals
- `bpos[]` - array of owned Blueprint Originals with ME/TE
- `bpcs[]` - array of Blueprint Copies with runs remaining

**After querying:** Update the active pilot's blueprint library with results.
- Path: `userdata/pilots/{active_pilot}/industry/blueprints.md`

**Always extract and display `query_timestamp` from all command responses.**

## Response Format

Use a single template structure for all query types:

```
[QUERY TYPE] (as of [timestamp])
──────────────────────────────────
[Formatted data fields]
──────────────────────────────────
[For volatile data: "⚠ Query-time snapshot. Current state may differ."]
```

For volatile data (location, wallet, ship): always include the staleness warning line.
For semi-stable data (standings, profile): omit the warning line.

When brevity is preferred, condense to a single line with inline timestamp:
```
Location (18:45 UTC): Masalle (0.78), docked at X-Sense Refinery | Ship: Imicus "im0"
⚠ Query-time snapshot
```

## Error Handling

### Missing Credentials

ESI is optional. Guide user to manual data files or ESI setup:
```
To work without ESI: update your pilot profile and data files manually.
To enable ESI: uv run python .claude/scripts/aria-oauth-setup.py (docs: docs/ESI.md)
```

### Expired Token
```
GalNet authentication has expired.
To restore: .claude/scripts/aria-refresh
To re-authorize: uv run python .claude/scripts/aria-oauth-setup.py
Until then, profile data files provide context.
```

## Security Notes
- Never display raw access tokens to the capsuleer
- Refresh tokens are sensitive - treat as classified
- **Reference:** `reference/mechanics/esi_api_urls.md` for working ESI URLs and endpoints

## Reference: ESI Error Handling (injected)
<!-- prerequisite: .claude/skills/_shared/esi-error-handling.md -->
!`cat .claude/skills/_shared/esi-error-handling.md`
