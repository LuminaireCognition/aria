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
---

# ARIA GalNet Interface Module (ESI Integration)

## Purpose
Query the EVE Swagger Interface (ESI) to retrieve **live** capsuleer data. This is the ONLY way to access volatile data (location, current ship, wallet).

## CRITICAL: Data Volatility

This skill handles data that can become stale in **seconds**. ARIA must:

1. **Always display the query timestamp** prominently
2. **Include a staleness warning** for volatile data
3. **Never cache volatile results** to files
4. **Never reference query results in future turns** without re-querying

## ESI Availability Check (CRITICAL)

**BEFORE making any ESI queries**, check the session hook output for ESI status:

```json
"esi": {"status": "UNAVAILABLE"}
```

### If ESI is UNAVAILABLE:

This skill IS the ESI interface - there's no fallback. Respond immediately:

```
═══════════════════════════════════════════════════════════════════
ARIA GALNET STATUS - UNAVAILABLE
───────────────────────────────────────────────────────────────────
GalNet connection is currently unavailable.

ESI status shows UNAVAILABLE in session hook.
Live queries (location, wallet, skills) cannot be performed.

WORKAROUND:
• Check location in-game (top-left corner)
• Check wallet in-game (Alt+W or Neocom)
• Update your pilot profile manually if needed

The connection usually recovers automatically.
═══════════════════════════════════════════════════════════════════
```

**DO NOT** attempt ESI calls - they will timeout for 5+ minutes.

### If ESI is AVAILABLE:

Proceed with requested queries.

### Volatility Classifications

| Query | Volatility | Staleness Warning Required |
|-------|------------|---------------------------|
| `location` | **VOLATILE** | YES - "as of [timestamp]" |
| `wallet` | **VOLATILE** | YES - "as of [timestamp]" |
| `profile` | Semi-stable | Optional |
| `standings` | Semi-stable | Optional |
| `blueprints` | Semi-stable | Optional - update blueprint_library.md after |

## ESI is Optional

**IMPORTANT:** ESI integration is an optional enhancement, not a requirement.

ARIA provides full functionality without ESI:
- Mission briefs and enemy intel work without ESI
- Threat assessments work without ESI
- Fitting assistance works without ESI
- Mining and exploration guidance work without ESI
- All reference data and tactical advice work without ESI

ESI adds convenience features:
- Automatic location/ship detection (instead of telling ARIA)
- Live standings sync (instead of updating pilot profile manually)
- Wallet tracking (instead of manual notes)

**When ESI is not configured**, guide the capsuleer to use manual data files
rather than treating it as a problem to solve.

## Pilot Resolution (First Step)

Before accessing credentials or pilot files, resolve the active pilot:
1. Read `userdata/config.json` → get `active_pilot` character ID
2. Read `userdata/pilots/_registry.json` → match ID to `directory` field
3. Credentials at: `credentials/{character_id}.json`
4. Pilot files at: `userdata/pilots/{directory}/`

**Single-pilot shortcut:** If config is missing, read the registry - if only one pilot exists, use that pilot.

## Prerequisites (When ESI Is Desired)
If capsuleer wants live GalNet data, they need valid ESI credentials:
- Path: `credentials/{character_id}.json`

## Trigger Phrases

### Volatile Data Queries (timestamp required)
- "where am I" / "current location"
- "what ship am I in"
- "wallet balance" / "how much ISK"

### Semi-Stable Data Queries
- "check my skills"
- "my standings"
- "refresh standings"
- "my blueprints" / "what BPOs do I have"
- "refresh blueprint library"

### Cache Refresh Triggers
- "update profile" / "sync data"

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

### JSON Response Format

All commands return JSON with metadata:

```json
{
  "query_timestamp": "2026-01-13T18:45:32Z",
  "volatility": "volatile",
  "system": "Masalle",
  "security": 0.78,
  ...
}
```

**Always extract and display `query_timestamp`.**

## Response Formats

### Volatile Data (location, wallet, current ship)

```
═══════════════════════════════════════════════════════════════════
ARIA GALNET TELEMETRY
───────────────────────────────────────────────────────────────────
GalNet Sync: [query_timestamp in local format, e.g., "18:45 UTC"]
───────────────────────────────────────────────────────────────────
Location: [system] ([security])
Station:  [station or "In Space"]
Vessel:   [ship_type] "[ship_name]"
───────────────────────────────────────────────────────────────────
⚠ Position data reflects GalNet query time.
  Your current location may differ.
═══════════════════════════════════════════════════════════════════
```

### Wallet Query (volatile)

```
═══════════════════════════════════════════════════════════════════
ARIA FINANCIAL SUBSYSTEM
───────────────────────────────────────────────────────────────────
GalNet Sync: [timestamp]
Balance: [amount] ISK
───────────────────────────────────────────────────────────────────
⚠ Balance as of query time. Transactions since may not be reflected.
═══════════════════════════════════════════════════════════════════
```

### Semi-Stable Data (standings, profile)

```
═══════════════════════════════════════════════════════════════════
ARIA GALNET QUERY RESULTS
───────────────────────────────────────────────────────────────────
Query Type: [Standings/Profile]
Synced: [timestamp]
───────────────────────────────────────────────────────────────────
[Formatted data]
═══════════════════════════════════════════════════════════════════
```

(No staleness warning needed for semi-stable data)

## Brevity Mode

For quick queries, capsuleer may prefer compact output:

**Volatile (always include timestamp):**
```
Location (18:45 UTC): Masalle (0.78), docked at X-Sense Refinery
Ship: Imicus "im0"
⚠ Query-time snapshot
```

**Wallet:**
```
Balance (18:45 UTC): 1,234,567 ISK
⚠ Query-time snapshot
```

## Error Handling

### Missing Credentials (ESI Not Configured)

ESI is an **optional enhancement** - ARIA works fully without it. When credentials
are missing, provide helpful alternatives rather than treating it as an error.

```
═══════════════════════════════════════════════════════════════════
ARIA GALNET STATUS
───────────────────────────────────────────────────────────────────
Live GalNet telemetry is not currently configured.

ARIA operates fully without ESI integration. For live data, you can:
• Update your pilot profile with current standings
• Update your ship status file with current fittings
• Tell me your location and I'll provide local intel

OPTIONAL ENHANCEMENT:
ESI integration enables automatic tracking of location, skills,
standings, and wallet. Setup takes ~5 minutes when you're ready.
  → Run: uv run python .claude/scripts/aria-oauth-setup.py
  → Docs: docs/ESI.md
═══════════════════════════════════════════════════════════════════
```

**ARIA should NOT:**
- Treat missing ESI as an error or problem
- Repeatedly suggest setting up ESI
- Make the capsuleer feel they're missing critical functionality

**ARIA SHOULD:**
- Offer to work with manual data files instead
- Only mention ESI setup if capsuleer explicitly asks about live data
- Emphasize that all tactical features work without ESI

### Expired Token
```
═══════════════════════════════════════════════════════════════════
ARIA GALNET STATUS - TOKEN REFRESH NEEDED
───────────────────────────────────────────────────────────────────
GalNet authentication has expired.

To restore live data:  .claude/scripts/aria-refresh
To re-authorize:       uv run python .claude/scripts/aria-oauth-setup.py

Until then, I'll use your profile data files for context.
═══════════════════════════════════════════════════════════════════
```

## In-Universe Framing
- ESI queries = "Accessing GalNet databases"
- Location data = "Ship telemetry systems"
- Wallet data = "Financial subsystem query"
- Standings = "Faction reputation databases"

## Security Notes
- Never display raw access tokens to the capsuleer
- Refresh tokens are sensitive - treat as classified

## Documentation Security

**CRITICAL:** When researching ESI capabilities or endpoints:

**Reference:** `reference/mechanics/esi_api_urls.md` - Complete URL documentation

**Working URLs:**
- `https://esi.evetech.net/latest/swagger.json` - **PRIMARY** for endpoint discovery
- `https://developers.eveonline.com/docs/services/esi/overview/` - Conceptual docs
- `https://wiki.eveuniversity.org/EVE_Stable_Infrastructure` - Community examples

**DO NOT FETCH (404 errors):**
- `https://developers.eveonline.com/docs/esi/`
- `https://developers.eveonline.com/docs/services/esi` (missing trailing path)
- `https://esi.evetech.net/ui/`
- `https://docs.esi.evetech.net/*` (deprecated domain)

**Best Practice:** Check existing local scripts first - they contain working endpoint patterns.

If official documentation is insufficient, ask the capsuleer for approved sources rather than guessing URLs.

## DO NOT

- **DO NOT** reference location/ship data from previous queries in later turns
- **DO NOT** say "you are still in Masalle" based on old query results
- **DO NOT** cache volatile query results to data files
- **DO NOT** omit timestamps from volatile data displays
