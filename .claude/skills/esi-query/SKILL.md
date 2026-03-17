---
name: esi-query
description: Query EVE Online ESI API for live character data. Use when capsuleer asks for current location, skills, wallet, or standings.
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
allowed-tools: [Read, Grep, Glob, Bash, "mcp__aria-universe__pilot", "mcp__aria-universe__sde"]
preferred_max_lines: 10
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

### Field → Source Mapping

| Output Field | Required Source | Tool Call |
|-------------|----------------|-----------|
| Current System | ESI location | `uv run aria-esi location` |
| Current Ship | ESI location | `uv run aria-esi location` |
| Docked Station | ESI location | `uv run aria-esi location` |
| Wallet Balance | ESI wallet | `uv run aria-esi wallet` |
| Standings (per entity) | ESI standings | `uv run aria-esi standings` |
| Skill Levels | ESI skills | `uv run aria-esi skills` |
| Blueprint Library | ESI blueprints | `uv run aria-esi blueprints` |

**Isolation rule:** Each query type uses its own CLI command. Do not answer a wallet question using data from a location query, even if both were called in the same session. Re-query the specific endpoint for each question.

**Compound queries:** When the user asks multiple things at once ("where am I and how much ISK do I have"), call each CLI command independently and present all results with per-source timestamps. Isolation means provenance tracking, not refusing to combine results.

## Freshness Gate

**VOLATILE queries (location, wallet, ship):** Always query live. Never present cached values. If the CLI fails, report the error — do not fall back to prior results.

**SEMI-STABLE queries with freshness registry support (standings, skills):**

```bash
uv run aria-esi ensure-fresh standings
uv run aria-esi ensure-fresh skills
```

| `fresh` | `esi_available` | Action |
|---------|-----------------|--------|
| `true`  | —               | Use data confidently |
| `false` | `false`         | Use cached data + **strong staleness warning**. Add "(cached, ESI offline)" after the timestamp |
| `false` | `true` (sync failed) | Warn about sync failure, use cached data with age warning |

**Blueprints:** Always-live (no freshness registry entry). Query `uv run aria-esi blueprints` directly — there is no `ensure-fresh blueprints`.

**Eligibility questions** ("do I have enough ISK?", "can I use L4 agents?"): require fresh data. If fresh data is unavailable, state "Cannot make a definitive assessment with stale data" and show the cached value with its age.

## Degraded Mode

Each query type is independent. A failed query should not prevent other queries from succeeding.

| Query | Required Scope | Degraded Output |
|-------|---------------|-----------------|
| `location` | `read_location` + `read_ship_type` | "Location requires ESI location scope. Check in-game: top-left shows current system." |
| `wallet` | `read_character_wallet` | "Wallet requires wallet scope. Check in-game: Alt+W" |
| `standings` | `read_standings` | "Standings require standings scope. Check in-game: Interactions → Standings" |
| `skills` | `read_skills` | "Skills require skills scope. Check in-game: Alt+A" |
| `blueprints` | `read_blueprints` | "Blueprints require blueprints scope. Check in-game: Industry → Blueprints" |

**In-game alternative:** Every degraded message includes the in-game keyboard shortcut or menu path. This ensures the pilot is never dead-ended.

**Multi-query degradation:** If the user asks a compound question ("where am I and how much ISK do I have"), attempt both queries independently. Show results for those that succeed and degraded messages for those that fail.

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

### Data Path Summary

| Query | MCP Available | CLI Command |
|-------|--------------|-------------|
| Location | No | `uv run aria-esi location` |
| Wallet | No | `uv run aria-esi wallet` |
| Standings | No | `uv run aria-esi standings` |
| Skills | No | `uv run aria-esi skills` |
| Blueprints | No | `uv run aria-esi blueprints` |
| Profile | No | `uv run aria-esi profile` |

All esi-query data paths are CLI-only. The `pilot()` MCP dispatcher supports `mail_list`, `mining_ledger`, `contracts`, `fittings_list`, and `lp_balance` — but those are routed through their own dedicated skills, not through `/esi-query`.

### Blueprints Query

Use `blueprints` to refresh the capsuleer’s BPO/BPC inventory:

```bash
uv run aria-esi blueprints
```

Returns JSON with:
- `bpo_count` / `bpc_count` - totals
- `bpos[]` - array of owned Blueprint Originals with ME/TE
- `bpcs[]` - array of Blueprint Copies with runs remaining

**After querying:** Update the active pilot’s blueprint library with results.
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

### Experience-Based Adaptation

- **new**: Include brief context with each data point ("Your wallet balance is the ISK you have available to spend")
- **intermediate**: Standard format with labels
- **veteran**: Ultra-compact single-line format for volatile queries. Example: `Masalle (0.78) docked | Imicus "im0" | 142.3M ISK`

## Anti-Patterns

- **WRONG:** Name the system the pilot is in based on earlier conversation context
- **RIGHT:** Re-query `uv run aria-esi location` for every location reference — the pilot may have moved

- **WRONG:** Show wallet balance from a prior turn’s query without re-querying
- **RIGHT:** Every volatile data reference requires a fresh CLI call in the current turn

- **WRONG:** Respond to "what skills do I have" with a partial list from training data
- **RIGHT:** Call `uv run aria-esi skills` and present only what ESI returns

- **WRONG:** Present standings for a faction not in the ESI response
- **RIGHT:** Only show entities present in the `uv run aria-esi standings` output

- **WRONG:** Combine data from multiple queries into a single "status report" without labelling timestamps per source
- **RIGHT:** Each data source gets its own timestamp. Location (14:32 UTC), Wallet (14:32 UTC), etc.

## Contextual Suggestions

After displaying query results, suggest ONE related command when contextually relevant:

| Context | Suggest |
|---------|---------|
| In low/null-sec | "Check safety with `/threat-assessment`" |
| Wallet below 5M ISK | "Track income with `/wallet-journal`" |
| Skill completing soon | "View full queue with `/skillqueue`" |
| Standings near threshold | "Plan progression with `/standings`" |
| Blueprint query | "Check build costs with `/build-cost`" |
| No ESI configured | "Connect ESI: `uv run aria-esi setup` (docs: `/help`)" |

## Error Handling

### No ESI Early Exit

If credentials are missing entirely (the first CLI call returns a credentials error), do not attempt remaining query commands. Present:

```
ESI is not configured. Live data queries require authentication.

Setup: uv run aria-esi setup (see docs/ESI.md)

Meanwhile, your profile data is available:
  /pilot — identity and ARIA configuration
  /standings — cached standings from profile
```

This prevents 3-4 sequential CLI failures when ESI is obviously unconfigured.

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

## Sources Footer

Append a one-line `Sources:` footer to every response:

```
Sources: CLI: [command(s) called]
```

## Reference: ESI Error Handling (injected)
<!-- prerequisite: .claude/skills/_shared/esi-error-handling.md -->
!`cat .claude/skills/_shared/esi-error-handling.md`
