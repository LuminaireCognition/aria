# ESI:MEDIUM/HIGH Skill Hardening

## Problem

ESI:NONE and ESI:LOW skills have been hardened over multiple rounds of exercise runs, producing a set of defensive patterns that dramatically reduce hallucination, dead-end responses, and stale data presentation. The three ESI:MEDIUM/HIGH skills — `pilot` (3 scopes), `corp` (5 scopes), and `esi-query` (6 scopes) — predate this hardening work and lack most of these patterns.

These three skills are high-traffic. `/esi-query` is the general-purpose data gateway for volatile pilot state. `/pilot` is the identity card. `/corp` is the most scope-heavy skill. Their current state creates inconsistent user experience: a pilot who gets crisp, guarded output from `/contracts` and then runs `/esi-query` encounters vague error handling, no freshness checks, and no hallucination guardrails beyond a brief prose mention.

### Gap Inventory

| Pattern | contracts | assets | skillplan | pilot | corp | esi-query |
|---------|-----------|--------|-----------|-------|------|-----------|
| Field → Source Mapping | — | ✅ | ✅ | ❌ | ❌ | ❌ |
| Freshness Gate | — | — | ✅ | ❌ | ❌ | ❌ |
| Degraded Mode Output | — | ✅ | ✅ | ❌ | ❌ | ❌ |
| Anti-Patterns (❌/✅) | — | ✅ | ✅ | ❌ | ❌ | ❌ |
| MCP + CLI Dual-Path | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| `allowed-tools` | ✅ | ✅ | — | ❌ | ❌ | ❌ |
| `preferred_max_lines` | — | — | — | ❌ | ❌ | ❌ |
| Contextual Suggestions | ✅ | ✅ | — | partial | ✅ | ❌ |
| Experience-Based Adaptation | — | — | — | ❌ | ❌ | ❌ |
| Positive-Path Early Exit | — | — | — | ❌ | ❌ | ❌ |

## Proposed Changes

Ten patterns, applied to three skills. Each pattern section specifies the exact text to add or modify in each SKILL.md. Patterns are ordered by priority.

---

### Pattern 1: Field → Source Mapping (P0)

Every output field traces to exactly one tool call. Without this table, the model mixes data from profile files, ESI responses, and training memory.

#### `pilot` — add after "Data Sources by Query Type"

````markdown
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
| Corp Roles | ESI authenticated | `uv run aria-esi pilot` (roles field) |
| EVE Experience | Local profile | `Read profile.md` |
| RP Level | Local profile | `Read profile.md` |
| Module Tier | Local profile | `Read profile.md` |
| Faction Alignment | Local profile | `Read profile.md` |
| Constraints | Local profile | `Read profile.md` |
| ESI Scope Count | Credentials metadata | `uv run aria-esi pilot` → `esi_status` field |

**Note:** The `pilot` CLI fetches wallet and skill points in a single call. Do not make separate `wallet` or `skills` CLI calls — the `pilot` response already includes both as `wallet_balance` and `skill_points.total`. If either ESI scope is missing, the field is simply absent from the response (not an error).
````

#### `corp` — add after "Hallucination Guard"

````markdown
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
| Pilot's Corp Role | ESI authenticated (personal) | `uv run aria-esi pilot` (roles field) |

**Cross-contamination guard:** Data from one subcommand MUST NOT appear in another subcommand's output section. If only `/corp wallet` was called, do not populate asset or blueprint sections from memory.
````

#### `esi-query` — add after "Volatility Classifications"

````markdown
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
````

---

### Pattern 2: Anti-Patterns (P0)

Explicit ❌/✅ pairs that catch the specific failure modes the model exhibits with these skills. Low effort, high impact.

#### `pilot` — add new section before "Cross-References"

````markdown
## Anti-Patterns

- **WRONG:** Present wallet balance from a prior conversation turn or from profile.md
- **RIGHT:** Call `uv run aria-esi pilot` and present only the `wallet_balance` from its response with timestamp

- **WRONG:** Show "12,450,000 SP" from training data or estimation
- **RIGHT:** Call `uv run aria-esi pilot` and present the `skill_points.total` from its response

- **WRONG:** State corporation roles without querying ESI
- **RIGHT:** Call `uv run aria-esi pilot` and read the roles field from the response

- **WRONG:** Say "ESI not configured" when wallet scope is missing but other scopes work
- **RIGHT:** Say "ESI is connected but the wallet scope isn't authorized" (per shared error handling)
````

#### `corp` — add new section before "Contextual Suggestions"

````markdown
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
````

#### `esi-query` — add new section before "Security Notes"

````markdown
## Anti-Patterns

- **WRONG:** Name the system the pilot is in based on earlier conversation context
- **RIGHT:** Re-query `uv run aria-esi location` for every location reference — the pilot may have moved

- **WRONG:** Show wallet balance from a prior turn's query without re-querying
- **RIGHT:** Every volatile data reference requires a fresh CLI call in the current turn

- **WRONG:** Respond to "what skills do I have" with a partial list from training data
- **RIGHT:** Call `uv run aria-esi skills` and present only what ESI returns

- **WRONG:** Present standings for a faction not in the ESI response
- **RIGHT:** Only show entities present in the `uv run aria-esi standings` output

- **WRONG:** Combine data from multiple queries into a single "status report" without labelling timestamps per source
- **RIGHT:** Each data source gets its own timestamp. Location (14:32 UTC), Wallet (14:32 UTC), etc.
````

---

### Pattern 3: Freshness Gate (P1)

Prevents stale cached data from being presented as current. Critical for skills that answer eligibility questions.

The freshness registry (`src/aria_esi/core/freshness.py`) supports exactly two sections: `standings` (TTL 24h) and `skills` (TTL 12h). Only these two support `ensure-fresh`. All other data types (location, wallet, blueprints) are always-live with no local cache.

#### `pilot` — add new section after "Implementation"

````markdown
## Freshness Gate

The `pilot` CLI fetches wallet and SP live from ESI on every call — no local cache, no freshness concern for those fields.

**For standings queries referenced in the response** (e.g., when showing agent access eligibility): use the freshness gate:

```bash
uv run aria-esi ensure-fresh standings
```

| `fresh` | `esi_available` | Action |
|---------|-----------------|--------|
| `true`  | —               | Proceed with data |
| `false` | `false`         | Show cached data + staleness warning. Refuse definitive claims if `age_hours > 168` |
| `false` | `true` (sync failed) | Warn about sync failure, use cached data |

**Non-eligibility queries** (identity display, profile overview): use profile data directly without the gate.
````

#### `corp` — add after "Prerequisites"

````markdown
## Freshness Gate

Corporation data changes when members join/leave, wallets transact, or jobs complete. Every corp subcommand fetches live from ESI — there is no local cache. If ESI is unavailable:

1. Report "Corp data requires live ESI connection"
2. For `/corp info` only: this uses public endpoints which are more reliable. Retry once before failing.
3. Do not present stale corp data from prior sessions or conversation context
````

#### `esi-query` — add after "Volatility Classifications"

````markdown
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
````

---

### Pattern 4: Degraded Mode Output (P1)

When one or more scopes are missing, show what you CAN show instead of dead-ending.

#### `pilot` — add new section after "Freshness Gate"

````markdown
## Degraded Mode

`/pilot` queries up to 3 ESI scopes. Missing scopes degrade individual sections, not the entire response. The `pilot` CLI silently omits fields for unauthorized scopes (no error — the field is just absent from JSON).

| Missing Scope | Section Affected | Degraded Behavior |
|---------------|-----------------|-------------------|
| `read_corporation_roles` | Corp Roles line | Show "Roles: [scope not authorized]" |
| `read_character_wallet` | Wallet line (`wallet_balance` absent) | Show "Wallet: [scope not authorized — run `uv run aria-esi setup` to add]" |
| `read_skills` | Skill Points line (`skill_points` absent) | Show "SP: [scope not authorized]" |
| All scopes (no ESI) | ACCOUNT SNAPSHOT section | Omit entire section. Show "ESI: Not configured — showing profile data only" |
| Public endpoint failure | Identity section | Show local profile data with "ESI unavailable" banner |

**Always show:** Character name (from credentials), ARIA Configuration (from profile.md), profile path. These never require ESI.
````

#### `corp` — add after "Freshness Gate"

````markdown
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
````

#### `esi-query` — add after "Freshness Gate"

````markdown
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
````

---

### Pattern 5: `allowed-tools` Declaration (P1)

Restricts the tool set to prevent off-domain tool usage. These are SKILL.md frontmatter changes only — `_index.json` does not have an `allowed-tools` field.

#### Frontmatter changes

**`pilot`:**
```yaml
allowed-tools: [Read, Grep, Glob, Bash, "mcp__aria-universe__pilot", "mcp__aria-universe__sde"]
```
Rationale: pilot needs `sde` for name resolution of corp/alliance IDs. Does not need market, fitting, universe, or killmails.

**`corp`:**
```yaml
allowed-tools: [Read, Grep, Glob, Bash, "mcp__aria-universe__pilot", "mcp__aria-universe__sde"]
```
Rationale: corp data comes from CLI wrappers (which call ESI internally). SDE for name resolution. No market or fitting needed.

**`esi-query`:**
```yaml
allowed-tools: [Read, Grep, Glob, Bash, "mcp__aria-universe__pilot", "mcp__aria-universe__sde"]
```
Rationale: esi-query is a data display skill. It should not call market, fitting, universe, or killmails dispatchers. If the user needs those, route to the appropriate skill.

---

### Pattern 6: MCP + CLI Dual-Path Documentation (P2)

Document whether MCP dispatchers exist for each data path, or explicitly mark as CLI-only. All three skills are CLI-only for their core data — the `pilot()` MCP dispatcher serves different skills (mail, contracts, LP, fittings, mining).

#### `pilot` — replace "Implementation" section

````markdown
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
````

#### `corp` — add after "Command Reference"

````markdown
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
````

#### `esi-query` — add after "ESI Wrapper Commands"

````markdown
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
````

---

### Pattern 7: `preferred_max_lines` (P2)

SKILL.md frontmatter changes only — `_index.json` does not have a `preferred_max_lines` field.

#### Frontmatter changes

**`pilot`:**
```yaml
preferred_max_lines: 20
```
Rationale: It's a status card. The existing box-drawing template is ~20 lines.

**`corp`:**
```yaml
preferred_max_lines: 25
```
Rationale: Dashboard overview with 4-5 sections. Individual subcommands should target 15 lines.

**`esi-query`:**
```yaml
preferred_max_lines: 10
```
Rationale: Volatile data snapshots should be maximally terse. Most queries are single-value lookups (location, wallet). The compact format already targets a single line.

---

### Pattern 8: Contextual Suggestions (P2)

#### `pilot` — replace "Cross-References" with expanded version

````markdown
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
````

#### `esi-query` — add new section before "Security Notes"

````markdown
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
````

---

### Pattern 9: Experience-Based Adaptation (P3)

#### `pilot` — add to "Behavior Notes"

````markdown
5. **Experience Adaptation**: Check `eve_experience` in profile.md.
   - **new**: Include brief explanation of what security status means, what SP represents
   - **intermediate**: Standard output
   - **veteran**: Omit explanatory text, terse format. Consider compact single-line: `Pilot: Name | Corp [TICK] | 25.3M SP | 142M ISK | Sec: 1.2`
````

#### `corp` — add to "Behavior Notes"

````markdown
- **Experience Adaptation**: Check `eve_experience` in profile.md.
  - **new**: Explain what corp roles mean, what wallet divisions are for
  - **intermediate**: Standard output
  - **veteran**: Terse dashboard. Omit role explanations.
````

#### `esi-query` — add to existing response format description

````markdown
### Experience-Based Adaptation

- **new**: Include brief context with each data point ("Your wallet balance is the ISK you have available to spend")
- **intermediate**: Standard format with labels
- **veteran**: Ultra-compact single-line format for volatile queries. Example: `Masalle (0.78) docked | Imicus "im0" | 142.3M ISK`
````

---

### Pattern 10: Positive-Path Early Exit (P3)

#### `corp` — add to top of "Subcommand Behavior"

````markdown
### NPC Corp Early Exit

The `corp` CLI already detects NPC corporations via `PLAYER_CORP_MIN_ID` (`src/aria_esi/core/constants.py`) and returns `"error": "npc_corporation"` for authenticated subcommands. The `/corp info` response also includes an `is_player_corp` boolean.

**When the CLI returns `"error": "npc_corporation"`**, present:

```
You're in [Corp Name], an NPC corporation. Corp management features
(wallet, assets, blueprints, jobs) require a player corporation.

Available: `/corp info [name]` to look up any corporation's public data.
```

Do not attempt other authenticated subcommands after receiving this error — they will all fail the same way. Skip directly to `/corp info` if the user wanted a dashboard.
````

#### `pilot` — add to "Behavior Notes"

````markdown
6. **Full ESI Early Exit**: If ESI is connected with all 3 scopes authorized, do not offer setup instructions or scope warnings. Present the full identity card cleanly.
7. **No ESI Early Exit**: If ESI is completely unconfigured (`esi_configured: false` in the `pilot` CLI response), do not attempt supplementary CLI calls. Show profile-only response immediately with a single setup suggestion at the bottom.
````

#### `esi-query` — add to "Error Handling"

````markdown
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
````

---

## Implementation Plan

### Phase 1: P0 — Hallucination Prevention (est. ~200 lines changed)

1. Add Field → Source Mapping tables to all three SKILL.md files
2. Add Anti-Patterns sections to all three SKILL.md files

**Validation:** Run exercise queries against each skill. Verify Sources footers match field-source mapping.

### Phase 2: P1 — Resilience (est. ~250 lines changed)

3. Add Freshness Gate sections to all three SKILL.md files
4. Add Degraded Mode sections to all three SKILL.md files
5. Add `allowed-tools` to all three SKILL.md frontmatters

**Validation:** Test each skill with simulated scope failures (revoke one scope at a time). Verify degraded output matches the specified template.

### Phase 3: P2 — Consistency (est. ~200 lines changed)

6. Add MCP + CLI Dual-Path documentation to all three SKILL.md files
7. Add `preferred_max_lines` to all three SKILL.md frontmatters
8. Add/upgrade Contextual Suggestions in `pilot` and `esi-query` SKILL.md files

**Validation:** Measure response line counts across exercise queries. Verify contextual suggestions fire appropriately.

### Phase 4: P3 — Polish (est. ~80 lines changed)

9. Add Experience-Based Adaptation notes to all three SKILL.md files
10. Add Positive-Path Early Exit logic to all three SKILL.md files

**Validation:** Test with new/intermediate/veteran profile settings. Verify early exit prevents unnecessary CLI calls.

## Impact

| Metric | Before | After |
|--------|--------|-------|
| Hallucination guardrails | 1 (prose mention) | 4 (field mapping, anti-patterns, freshness, source isolation) |
| Dead-end responses on partial ESI | Common | Eliminated (degraded mode per scope) |
| Stale data presentation | No prevention | Freshness gate on eligibility queries |
| Off-domain tool calls | Unrestricted | `allowed-tools` limits to pilot/sde |
| Response verbosity control | None | `preferred_max_lines` per skill |
| ESI error specificity | Generic | Scope-specific with in-game alternatives |

## What This Does NOT Change

- **ESI error handling fragment** (`_shared/esi-error-handling.md`) — already injected in all three skills. No changes needed.
- **CLI wrapper scripts** — no changes to `aria-esi` commands or their output format.
- **MCP dispatchers** — no new dispatcher actions. Documentation clarifies what exists.
- **Skill-gate hooks** — no changes to hook infrastructure.
- **`_index.json`** — no changes. All modifications are to SKILL.md frontmatter and body content. `allowed-tools` and `preferred_max_lines` are Claude Code frontmatter keys that live in SKILL.md, not in `_index.json`.
- **Persona overlays** — these skills don't have persona overlays. No overlay changes needed.

## Risks

| Risk | Mitigation |
|------|------------|
| Longer SKILL.md files increase prompt token cost | Estimated +2-3K tokens per skill. Offset by `preferred_max_lines` reducing output tokens. Net neutral or positive. |
| Anti-patterns may be overly specific to current model behavior | Frame as "common failure modes" not "bugs." Review after model updates. |
| Freshness gate adds a CLI call before every eligibility query | `ensure-fresh` is fast (~200ms local cache check, ESI call only if stale). Acceptable latency for correctness. |
| Early exit logic adds conditional branches | Keep conditions simple and well-documented. Each early exit is a single `if` that short-circuits to a canned response. |

## Relationship to Existing Work

- **DATA_VALIDATION_GAPS_PROPOSAL.md** — validates reference data integrity. This proposal validates *runtime data presentation*. Complementary.
- **TOOL_TRACE_CAPTURE_PROPOSAL.md** — captures tool call traces for exercise verification. Once implemented, tool traces can verify that Field → Source Mappings are respected at runtime.
- **EXERCISE_RUN_REMEDIATION** — identified specific hallucination instances. This proposal prevents the categories of hallucination those instances represent.
