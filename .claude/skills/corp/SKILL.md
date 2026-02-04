---
name: corp
description: Corporation management and queries. Use for corp status, wallet, assets, blueprints, or industry jobs.
model: haiku
category: identity
triggers:
  - "/corp"
  - "corp status"
  - "corporation status"
  - "corp wallet"
  - "corp blueprints"
requires_pilot: true
esi_scopes:
  - esi-corporations.read_corporation_membership.v1
  - esi-wallet.read_corporation_wallets.v1
  - esi-assets.read_corporation_assets.v1
  - esi-corporations.read_blueprints.v1
  - esi-industry.read_corporation_jobs.v1
---

# ARIA Corporation Management Module

## Purpose

Query and manage corporation data for player corporations. Provides a consolidated `/corp` command with subcommands for wallet, assets, blueprints, and industry jobs.

## Prerequisites

**For `/corp info`:** No prerequisites - uses public ESI endpoints.

**For all other subcommands:**
1. Must be in a player corporation (not NPC corp)
2. Must have CEO or Director role
3. Must have authorized corporation ESI scopes

**Setup:**
```bash
uv run python .claude/scripts/aria-oauth-setup.py
# Select "Y" when asked about corporation scopes
```

## ESI Availability Check (CRITICAL)

**BEFORE making any ESI queries**, check the session hook output for ESI status:

```json
"esi": {"status": "UNAVAILABLE"}
```

### If ESI is UNAVAILABLE:

1. **DO NOT** run `uv run aria-esi corp` commands - they will timeout
2. **EXCEPTION:** `/corp info` MAY work for public lookups (test carefully)
3. **RESPOND IMMEDIATELY** with:
   ```
   Corporation data requires live ESI data which is currently unavailable.

   Check this in-game:
   • Corporation window (Alt+C) → Home tab, Wallet tab, etc.
   • Industry window for corp jobs

   Note: '/corp info <name>' for public lookups may still work.

   ESI usually recovers automatically.
   ```
4. **DO NOT** block waiting for ESI

### If ESI is AVAILABLE:

Proceed with normal corporation queries.

## Trigger Phrases

### Default Dashboard (/corp)
- "/corp"
- "corp status"
- "corporation status"
- "how's the corp"
- "check on corp"

### Info Subcommand
- "/corp info"
- "corp info [name]"
- "lookup corporation"
- "what is [corp name]"
- "look up [corp name]"

### Wallet Subcommand
- "/corp wallet"
- "corp wallet"
- "corp finances"
- "corporation balance"
- "corp journal"
- "corp transactions"

### Assets Subcommand
- "/corp assets"
- "corp assets"
- "corp hangar"
- "what's in corp hangar"
- "corporation inventory"
- "corp ships"

### Blueprints Subcommand
- "/corp blueprints"
- "corp blueprints"
- "corp BPOs"
- "corporation blueprint library"
- "corp industry prints"

### Jobs Subcommand
- "/corp jobs"
- "corp jobs"
- "manufacturing status"
- "what's being built"
- "corp industry"
- "corp manufacturing"

## Command Reference

```
/corp                              # Status dashboard (default)
/corp help                         # List available subcommands
/corp info [name|id]               # Public corp lookup (any corporation)
/corp wallet [--journal] [--div N] # Wallet balances and journal
/corp assets [--ships] [--loc X]   # Corporation hangar inventory
/corp blueprints [--filter X]      # BPO/BPC library
/corp jobs [--active|--history]    # Industry job status
```

## Subcommand Behavior

### `/corp` (Status Dashboard)

Default behavior when no subcommand specified. Shows overview of all corporation data.

**Script:** `uv run aria-esi corp`

**Response Format (rp_level: moderate or full):**
```
═══════════════════════════════════════════════════════════════════
[CORP NAME] [[TICKER]] - CORPORATION STATUS
───────────────────────────────────────────────────────────────────
GalNet Sync: [timestamp]

IDENTITY
  Corporation:   [Name]
  Ticker:        [TICK]
  Members:       [count]
  CEO:           [Character Name]
  Tax Rate:      [X]%

FINANCIAL SUMMARY
  Master Wallet: [X,XXX,XXX] ISK
  Total:         [X,XXX,XXX] ISK

ASSETS
  Locations:     [N] stations
  Ships:         [N] assembled

INDUSTRY
  Active Jobs:   [N] ([next completion])
  Blueprints:    [N] BPOs, [N] BPCs

───────────────────────────────────────────────────────────────────
Subcommands: info, wallet, assets, blueprints, jobs
═══════════════════════════════════════════════════════════════════
```

**Graceful Degradation:** If some scopes are missing, show "N/A" for unauthorized sections.

### `/corp info [target]`

Query public corporation information. Works for ANY corporation without auth.

**Arguments:**
- No argument or `my` → User's own corporation
- Corporation ID → Direct lookup
- Corporation name → Search and lookup

**Script:** `uv run aria-esi corp info [target]`

**Response Format:**
```
═══════════════════════════════════════════════════════════════════
ARIA CORPORATION INTELLIGENCE
───────────────────────────────────────────────────────────────────
GalNet Query: [timestamp]

CORPORATION: [Name]
TICKER:      [TICK]
MEMBERS:     [count]
CEO:         [Character Name]
TAX RATE:    [X]%
FOUNDED:     [date]
ALLIANCE:    [Alliance Name or "Independent"]

DESCRIPTION:
[Corporation bio - first 500 chars]

───────────────────────────────────────────────────────────────────
Public record query. No authentication required.
═══════════════════════════════════════════════════════════════════
```

### `/corp wallet`

Query corporation wallet balances and transaction journal.

**Options:**
- `--journal` - Show transaction history
- `--div N` - Query specific division (1-7)
- `--limit N` - Number of journal entries

**Script:** `uv run aria-esi corp wallet [options]`

**Response Format:**
```
═══════════════════════════════════════════════════════════════════
[CORP NAME] - FINANCIAL STATUS
───────────────────────────────────────────────────────────────────
GalNet Sync: [timestamp]

WALLET DIVISIONS:
  1. Master Wallet:     [X,XXX,XXX.XX] ISK
  2. [Division Name]:          [X.XX] ISK
  ...
                       ─────────────────
  TOTAL:               [X,XXX,XXX.XX] ISK

RECENT ACTIVITY (last 10):
  [date] + [amount] ISK  [type]
  [date] - [amount] ISK  [type]
  ...

───────────────────────────────────────────────────────────────────
⚠ Balance as of query time.
═══════════════════════════════════════════════════════════════════
```

### `/corp assets`

Query corporation asset inventory.

**Options:**
- `--ships` - Show assembled ships only
- `--location "name"` - Filter by location
- `--type "name"` - Filter by item type

**Script:** `uv run aria-esi corp assets [options]`

### `/corp blueprints`

Query corporation blueprint library.

**Options:**
- `--filter "name"` - Search by blueprint name
- `--bpos` - Show BPOs only
- `--bpcs` - Show BPCs only

**Script:** `uv run aria-esi corp blueprints [options]`

### `/corp jobs`

Query corporation industry job status.

**Options:**
- `--active` - Show active jobs only
- `--completed` - Show completed jobs only
- `--history` - Extended history (50 entries)

**Script:** `uv run aria-esi corp jobs [options]`

## Error Handling

### NPC Corporation

When character is in an NPC corporation:

```
═══════════════════════════════════════════════════════════════════
ARIA CORPORATION MODULE
───────────────────────────────────────────────────────────────────
You are currently in an NPC corporation.

Corporation management features require membership in a player
corporation. The 'info' subcommand still works for lookups:

  /corp info [corporation name or ID]

To access full corp features, join or create a player corporation.
═══════════════════════════════════════════════════════════════════
```

### Missing Scopes

When required scope is not authorized:

```
═══════════════════════════════════════════════════════════════════
ARIA CORPORATION MODULE - SCOPE REQUIRED
───────────────────────────────────────────────────────────────────
This operation requires: [scope name]

Corporation scopes were not authorized during ESI setup.

To enable corp features:
  uv run python .claude/scripts/aria-oauth-setup.py

Select "Y" when asked about corporation scopes.
═══════════════════════════════════════════════════════════════════
```

### Insufficient Role

When ESI returns 403 Forbidden due to missing corp role:

```
═══════════════════════════════════════════════════════════════════
ARIA CORPORATION MODULE - ACCESS DENIED
───────────────────────────────────────────────────────────────────
Your character lacks the required corporation role.

[Subcommand] access requires CEO or Director role.

If you recently received this role, it may take up to 24 hours
for ESI to recognize the change.
═══════════════════════════════════════════════════════════════════
```

### Corporation Not Found

When searching for a corporation that doesn't exist:

```
═══════════════════════════════════════════════════════════════════
ARIA CORPORATION INTELLIGENCE
───────────────────────────────────────────────────────────────────
No corporation found matching: [search term]

Try:
  • Check the spelling
  • Use the corporation ID if known
  • Search for part of the name
═══════════════════════════════════════════════════════════════════
```

## Data Volatility

| Subcommand | Volatility | Timestamp Required |
|------------|------------|-------------------|
| info | Stable | No |
| status | Semi-stable | Optional |
| wallet | **Volatile** | YES |
| assets | Semi-stable | Optional |
| blueprints | Semi-stable | Optional |
| jobs | Semi-stable | Optional |

**Wallet data is VOLATILE** - always include timestamp and staleness warning.

## Scopes Required

| Subcommand | Scope |
|------------|-------|
| info | None (public) |
| status | Multiple (graceful degradation) |
| wallet | `esi-wallet.read_corporation_wallets.v1` |
| assets | `esi-assets.read_corporation_assets.v1` |
| blueprints | `esi-corporations.read_blueprints.v1` |
| jobs | `esi-industry.read_corporation_jobs.v1` |

## In-Universe Framing

When `rp_level` is `moderate` or `full`:
- Corporate queries = "Accessing NEOCOM corporate interface"
- Wallet data = "Financial subsystem query"
- Assets = "Hangar manifest retrieval"
- Blueprints = "Industrial database query"
- Industry jobs = "Manufacturing queue status"

## Behavior Notes

- **Graceful Degradation:** Dashboard shows "N/A" for sections where scope is missing
- **Public Info Always Works:** `/corp info` works without any auth
- **Role-Based Access:** ESI enforces CEO/Director role server-side
- **JSON Output:** Script returns structured JSON for ARIA to format
- **Timestamp Protocol:** Wallet data always includes query timestamp

## ESI Documentation Reference

When researching corporation ESI endpoints, use these working URLs:

- `https://esi.evetech.net/latest/swagger.json` - Authoritative endpoint schema
- `https://developers.eveonline.com/docs/services/esi/overview/` - Conceptual docs

See `reference/mechanics/esi_api_urls.md` for complete URL documentation and known 404 paths to avoid.
