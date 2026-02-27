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

> **HALLUCINATION GUARD:** All corporation data fields MUST come from CLI output. If a field is missing, display "N/A" — never fill from memory.

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

Present the dashboard with these sections: Identity (name, ticker, members, CEO, tax rate), Financial Summary (wallet balances), Assets (locations, ships), Industry (active jobs, blueprints). If some scopes are missing, show "N/A" for unauthorized sections.

### `/corp info [target]`

Query public corporation information. Works for ANY corporation without auth.

**Arguments:**
- No argument or `my` → User's own corporation
- Corporation ID → Direct lookup
- Corporation name → Search and lookup

**Script:** `uv run aria-esi corp info [target]`

Present: corporation name, ticker, member count, CEO, tax rate, founded date, alliance (or "Independent"), description (first 500 chars).

### `/corp wallet`

Query corporation wallet balances and transaction journal.

**Options:**
- `--journal` - Show transaction history
- `--div N` - Query specific division (1-7)
- `--limit N` - Number of journal entries

**Script:** `uv run aria-esi corp wallet [options]`

Wallet data is volatile — always include query timestamp.

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

- **NPC Corporation:** Inform the user that corp management features require a player corporation. The `/corp info` subcommand still works for lookups.
- **Missing Scopes:** State which scope is required and provide the setup command (`uv run python .claude/scripts/aria-oauth-setup.py`).
- **Insufficient Role:** Explain that the subcommand requires CEO or Director role. Note that recently granted roles may take up to 24 hours for ESI to recognize.
- **Corporation Not Found:** Suggest checking spelling, using the corporation ID, or searching for part of the name.

## Contextual Suggestions

| Context | Suggest |
|---------|---------|
| Viewing wallet | "Track transactions with `/wallet-journal`" |
| Viewing assets | "For personal assets, use `/assets`" |
| Viewing jobs | "For personal jobs, use `/industry-jobs`" |

## Behavior Notes

- **JSON Output:** Script returns structured JSON for ARIA to format
- **Timestamp Protocol:** Wallet data always includes query timestamp
- **Role-Based Access:** ESI enforces CEO/Director role server-side
