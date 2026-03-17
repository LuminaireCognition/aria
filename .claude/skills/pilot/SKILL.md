---
name: pilot
description: View pilot identity and configuration. Shows full data for authenticated pilot, public data for others.
category: identity
triggers:
  - "/pilot"
  - "/pilot me"
  - "/pilot [name]"
  - "who am I"
  - "my profile"
  - "show my profile"
  - "pilot identity"
  - "look up [name]"
  - "who is [name]"
requires_pilot: true
data_sources:
  - userdata/pilots/{active_pilot}/profile.md
esi_scopes:
  - esi-characters.read_corporation_roles.v1
  - esi-wallet.read_character_wallet.v1
  - esi-skills.read_skills.v1
argument-hint: "[pilot_name]"
injected_prerequisites:
  - .claude/skills/_shared/esi-error-handling.md
allowed-tools: [Read, Grep, Glob, Bash, "mcp__aria-universe__pilot", "mcp__aria-universe__sde"]
preferred_max_lines: 20
---

# ARIA Pilot Identity Module

## Command Syntax

```
/pilot           # Show authenticated pilot's full identity
/pilot me        # Same as above (explicit self-reference)
/pilot <name>    # Look up another pilot (public data only)
/pilot <id>      # Look up by character ID (public data only)
```

## Implementation

All pilot identity data is CLI-only. No MCP dispatcher actions exist for pilot identity, wallet, or skill point queries.

### CLI

```bash
# Authenticated pilot (full data: identity + wallet + SP + corp + scopes)
uv run aria-esi pilot

# Public lookup (name, corp, alliance, security, birthday only)
uv run aria-esi pilot "Character Name"
uv run aria-esi pilot 2123984364
```

### Data Path Summary

| Data | MCP Available | CLI Command |
|------|--------------|-------------|
| Authenticated identity (full) | No | `uv run aria-esi pilot` |
| Public info (any pilot) | No | `uv run aria-esi pilot "<name>"` |
| Wallet balance | No (included in `pilot` response) | `uv run aria-esi pilot` → `wallet_balance` |
| Skill points | No (included in `pilot` response) | `uv run aria-esi pilot` → `skill_points.total` |
| Standings | No | `uv run aria-esi standings` |

The `pilot()` MCP dispatcher exists but serves other skills (`mail_list`, `contracts`, `fittings_list`, etc.) — it has no identity/wallet/SP actions.

If ESI is unavailable, fall back to local profile data and note "Showing local profile (ESI unavailable)". Do not run CLI commands when ESI is unavailable.

## Data Sources by Query Type

| Data | Source | Self | Public |
|------|--------|------|--------|
| Character ID/Name | Credentials / ESI search | Yes | Yes |
| Corporation/Alliance | ESI public endpoint | Yes | Yes |
| Security Status | ESI public endpoint | Yes | Yes |
| Birthday | ESI public endpoint | Yes | Yes |
| Faction Alignment | Local profile.md | Yes | No |
| EVE Experience | Local profile.md | Yes | No |
| RP Level | Local profile.md | Yes | No |
| Module Tier | Local profile.md | Yes | No |
| Operational Constraints | Local profile.md | Yes | No |
| Standings | ESI authenticated | Yes | No |
| ESI Scopes Available | Credentials file | Yes | No |
| Wallet Balance | ESI authenticated | Yes | No |
| Skill Points | ESI authenticated | Yes | No |

### Field → Source Mapping

Every value in the response MUST come from the source listed here. If the source was not queried or returned an error, show `[no data]` for that field.

| Output Field | Required Source | Tool Call |
|-------------|----------------|-----------|
| Character Name/ID | ESI public endpoint | `uv run aria-esi pilot` |
| Corporation/Alliance | ESI public endpoint | `uv run aria-esi pilot` |
| Security Status | ESI public endpoint | `uv run aria-esi pilot` |
| Birthday | ESI public endpoint | `uv run aria-esi pilot` |
| Wallet Balance | ESI authenticated | `uv run aria-esi pilot` → `wallet_balance` field |
| Total Skill Points | ESI authenticated | `uv run aria-esi pilot` → `skill_points.total` field |
| EVE Experience | Local profile | `Read profile.md` |
| RP Level | Local profile | `Read profile.md` |
| Module Tier | Local profile | `Read profile.md` |
| Faction Alignment | Local profile | `Read profile.md` |
| Constraints | Local profile | `Read profile.md` |
| ESI Scope Count | Credentials metadata | `uv run aria-esi pilot` → `esi_status` field |

**Note:** The `pilot` CLI fetches wallet and skill points in a single call. Do not make separate `wallet` or `skills` CLI calls — the `pilot` response already includes both as `wallet_balance` and `skill_points.total`. If either ESI scope is missing, the field is simply absent from the response (not an error).

## Hallucination Guard

Present only data returned by ESI or read from profile.md. If data is missing, state what is unavailable — do not estimate or fabricate values (especially wallet balance and skill points).

## Freshness Gate

The `pilot` CLI fetches wallet and SP live from ESI on every call — no local cache, no freshness concern for those fields.

**For standings queries referenced in the response** (e.g., when showing agent access eligibility): use the freshness gate:

```bash
uv run aria-esi ensure-fresh standings
```

| `fresh` | `esi_available` | Action |
|---------|-----------------|--------|
| `true`  | —             | Proceed with data |
| `false` | `false`         | Show cached data + staleness warning. Refuse definitive claims if `age_hours > 168` |
| `false` | `true` (sync failed) | Warn about sync failure, use cached data |

**Non-eligibility queries** (identity display, profile overview): use profile data directly without the gate.

## Degraded Mode

`/pilot` queries up to 3 ESI scopes. Missing scopes degrade individual sections, not the entire response. The `pilot` CLI silently omits fields for unauthorized scopes (no error — the field is just absent from JSON).

| Missing Scope | Section Affected | Degraded Behavior |
|---------------|-----------------|-------------------|
| `read_character_wallet` | Wallet line (`wallet_balance` absent) | Show "Wallet: [scope not authorized — run `uv run aria-esi setup` to add]" |
| `read_skills` | Skill Points line (`skill_points` absent) | Show "SP: [scope not authorized]" |
| All scopes (no ESI) | ACCOUNT SNAPSHOT section | Omit entire section. Show "ESI: Not configured — showing profile data only" |
| Public endpoint failure | Identity section | Show local profile data with "ESI unavailable" banner |

**Always show:** Character name (from credentials), ARIA Configuration (from profile.md), profile path. These never require ESI.

## Response Format

Use this template for self queries. For public queries, show only: name, corp, alliance, security, birthday.

```
═══════════════════════════════════════════════════════════════════
PILOT IDENTITY
───────────────────────────────────────────────────────────────────
CHARACTER:     [Name]
CHARACTER ID:  [ID]
CORPORATION:   [Corp Name] [[Ticker]]
ALLIANCE:      [Alliance or "None"]
SECURITY:      [Status]
CAPSULEER SINCE: [Date]

ARIA CONFIGURATION:
  EVE Experience:  [new/intermediate/veteran]
  RP Level:        [off/on/full]
  Module Tier:     [T1/Meta or T2]
  Faction:         [Primary Faction]

CONSTRAINTS:
  [Relevant constraints from profile]

ESI STATUS: [Connected/Not Configured]
  Scopes: [X] personal, [Y] corporation

ACCOUNT SNAPSHOT: (as of [timestamp])
  Wallet:       [X,XXX,XXX ISK]
  Skill Points: [X,XXX,XXX SP]
───────────────────────────────────────────────────────────────────
Profile: [path to profile.md]
═══════════════════════════════════════════════════════════════════
```

**For not found:** State the query and suggest checking spelling or using character ID.

**For no ESI credentials:** Show local profile data only with note that ESI setup enables live data (`uv run python .claude/scripts/aria-oauth-setup.py`).

**For ESI errors:** Show the error message and suggest retrying or checking ESI status.

## Anti-Patterns

- **WRONG:** Present wallet balance from a prior conversation turn or from profile.md
- **RIGHT:** Call `uv run aria-esi pilot` and present only the `wallet_balance` from its response with timestamp

- **WRONG:** Show "12,450,000 SP" from training data or estimation
- **RIGHT:** Call `uv run aria-esi pilot` and present the `skill_points.total` from its response

- **WRONG:** Say "ESI not configured" when wallet scope is missing but other scopes work
- **RIGHT:** Say "ESI is connected but the wallet scope isn't authorized" (per shared error handling)

## Behavior Notes

1. **Default to Self**: `/pilot` with no arguments shows authenticated pilot
2. **Data Exposure**: Clearly distinguish between public and authenticated data
3. **Timestamp Volatile Data**: Wallet/SP are volatile - always show query timestamp
4. **Profile Path**: Include profile file path for easy editing
5. **Experience Adaptation**: Check `eve_experience` in profile.md.
   - **new**: Include brief explanation of what security status means, what SP represents
   - **intermediate**: Standard output
   - **veteran**: Omit explanatory text, terse format. Consider compact single-line: `Pilot: Name | Corp [TICK] | 25.3M SP | 142M ISK | Sec: 1.2`
6. **Full ESI Early Exit**: If ESI is connected with all 3 scopes authorized, do not offer setup instructions or scope warnings. Present the full identity card cleanly.
7. **No ESI Early Exit**: If ESI is completely unconfigured (`esi_configured: false` in the `pilot` CLI response), do not attempt supplementary CLI calls. Show profile-only response immediately with a single setup suggestion at the bottom.

## Contextual Suggestions

After displaying pilot identity, suggest ONE related command when contextually relevant:

| Context | Suggest |
|---------|---------|
| Low security status | "Track empire access with `/sec-status`" |
| High skill points | "Plan next training with `/skillplan`" |
| In a player corp | "View corp details with `/corp`" |
| No ESI configured | "Connect ESI for live data: `uv run aria-esi setup`" |
| Missing scopes | "Add missing scopes: `uv run aria-esi setup`" |

**Cross-References** (for explicit requests, not contextual):

| For This | Use Instead |
|----------|-------------|
| Current location | `/esi-query location` |
| Detailed standings | `/standings` |
| Skills list | `/skillplan` or `/esi-query skills` |
| Corporation details | `/corp` |

## Sources Footer

Append a one-line `Sources:` footer to every response:

```
Sources: CLI: pilot | Read: profile.md
```

## Reference: ESI Error Handling (injected)
<!-- prerequisite: .claude/skills/_shared/esi-error-handling.md -->
!`cat .claude/skills/_shared/esi-error-handling.md`
