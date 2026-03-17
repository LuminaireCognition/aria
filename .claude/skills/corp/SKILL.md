---
name: corp
description: Corporation management and queries. Use for corp status, wallet, assets, blueprints, or industry jobs.
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
argument-hint: "[status|wallet|assets|blueprints|jobs]"
injected_prerequisites:
  - .claude/skills/_shared/esi-error-handling.md
allowed-tools: [Read, Grep, Glob, Bash, "mcp__aria-universe__pilot", "mcp__aria-universe__sde"]
preferred_max_lines: 25
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

### Field → Source Mapping

| Output Field | Required Source | Tool Call |
|-------------|----------------|-----------|
| Corp Name/Ticker/Members/CEO | ESI public endpoint | `uv run aria-esi corp info` |
| Tax Rate | ESI public endpoint | `uv run aria-esi corp info` |
| Alliance | ESI public endpoint | `uv run aria-esi corp info` |
| Wallet Balances (by division) | ESI authenticated (corp) | `uv run aria-esi corp wallet` |
| Journal Entries | ESI authenticated (corp) | `uv run aria-esi corp wallet --journal` |
| Asset Inventory | ESI authenticated (corp) | `uv run aria-esi corp assets` |
| Blueprint Library | ESI authenticated (corp) | `uv run aria-esi corp blueprints` |
| Industry Job Status | ESI authenticated (corp) | `uv run aria-esi corp jobs` |

**Cross-contamination guard:** Data from one subcommand MUST NOT appear in another subcommand’s output section. If only `/corp wallet` was called, do not populate asset or blueprint sections from memory.

## Freshness Gate

Corporation data changes when members join/leave, wallets transact, or jobs complete. Every corp subcommand fetches live from ESI — there is no local cache. If ESI is unavailable:

1. Report "Corp data requires live ESI connection"
2. For `/corp info` only: this uses public endpoints which are more reliable. Retry once before failing.
3. Do not present stale corp data from prior sessions or conversation context

## Degraded Mode

Corp subcommands have independent scope requirements. A missing scope degrades one section, not the dashboard.

| Subcommand | Required Scope | Degraded Output |
|------------|---------------|-----------------|
| `/corp info` | None (public) | Always works. If ESI is fully down, show "Public endpoint unavailable" |
| `/corp wallet` | `read_corporation_wallets` | "Wallet data requires the corporation wallet scope. Run `uv run aria-esi setup`" |
| `/corp assets` | `read_corporation_assets` | "Asset data requires the corporation assets scope." |
| `/corp blueprints` | `read_blueprints` | "Blueprint data requires the corporation blueprints scope." |
| `/corp jobs` | `read_corporation_jobs` | "Industry data requires the corporation jobs scope." |

**Dashboard (`/corp`):** Attempt all subcommands. For each that fails, show the scope-specific message in that section. Sections that succeed render normally. Never skip the entire dashboard because one scope is missing.

**Role errors:** If ESI returns "Forbidden" (not a scope error), the pilot lacks Director/CEO role. State this specifically — do not conflate with missing scopes.

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

## Data Path Summary

Corporation data uses CLI exclusively. No MCP dispatcher actions exist for corp endpoints.

| Subcommand | CLI Command | MCP Available |
|------------|-------------|---------------|
| `/corp` | `uv run aria-esi corp` | No |
| `/corp info` | `uv run aria-esi corp info [target]` | No |
| `/corp wallet` | `uv run aria-esi corp wallet [options]` | No |
| `/corp assets` | `uv run aria-esi corp assets [options]` | No |
| `/corp blueprints` | `uv run aria-esi corp blueprints [options]` | No |
| `/corp jobs` | `uv run aria-esi corp jobs [options]` | No |

Do not attempt `pilot(action="corp_*")` or similar — these actions do not exist.

## Subcommand Behavior

### NPC Corp Early Exit

The `corp` CLI already detects NPC corporations via `PLAYER_CORP_MIN_ID` (`src/aria_esi/core/constants.py`) and returns `"error": "npc_corporation"` for authenticated subcommands. The `/corp info` response also includes an `is_player_corp` boolean.

**When the CLI returns `"error": "npc_corporation"`**, present:

```
You're in [Corp Name], an NPC corporation. Corp management features
(wallet, assets, blueprints, jobs) require a player corporation.

Available: `/corp info [name]` to look up any corporation's public data.
```

Do not attempt other authenticated subcommands after receiving this error — they will all fail the same way. Skip directly to `/corp info` if the user wanted a dashboard.

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

## Anti-Patterns

- **WRONG:** Show corp wallet balances from a cached pilot profile
- **RIGHT:** Call `uv run aria-esi corp wallet` for live data

- **WRONG:** Present blueprint list when only `/corp` (dashboard) was called
- **RIGHT:** Each section requires its own CLI call. Dashboard calls `uv run aria-esi corp` which returns summary data only

- **WRONG:** Assume the pilot has Director role because they asked about corp data
- **RIGHT:** Let the CLI call fail with an insufficient-role error, then report it

- **WRONG:** Show member count from training data for a known corporation name
- **RIGHT:** Call `uv run aria-esi corp info` — even well-known corps change member counts daily

- **WRONG:** Run all subcommands when user asked for `/corp wallet` only
- **RIGHT:** Execute only the subcommand matching the user's query

## Error Handling

- **NPC Corporation:** Inform the user that corp management features require a player corporation. The `/corp info` subcommand still works for lookups.
- **Missing Scopes:** State which scope is required and provide the setup command (`uv run python .claude/scripts/aria-oauth-setup.py`).
- **Insufficient Role:** Explain that the subcommand requires CEO or Director role. Note that recently granted roles may take up to 24 hours for ESI to recognize.
- **Corporation Not Found:** ESI uses exact name matching. Suggest checking spelling or using the corporation ID. Point the user to zKillboard or DOTLAN for name verification. **Never retry with partial name fragments** — partial searches return unrelated entities and erode trust. If the CLI returns a `near_match` field, mention it as an unverified suggestion with the caveat that it may not be the intended corporation.

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
- **Experience Adaptation**: Check `eve_experience` in profile.md.
  - **new**: Explain what corp roles mean, what wallet divisions are for
  - **intermediate**: Standard output
  - **veteran**: Terse dashboard. Omit role explanations.

## Sources Footer

Append a one-line `Sources:` footer to every response:

```
Sources: CLI: corp [subcommand]
```

## Reference: ESI Error Handling (injected)
<!-- prerequisite: .claude/skills/_shared/esi-error-handling.md -->
!`cat .claude/skills/_shared/esi-error-handling.md`
