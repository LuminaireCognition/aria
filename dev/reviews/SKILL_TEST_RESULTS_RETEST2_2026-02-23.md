# ARIA Skill Retest Results (Round 2) - 2026-02-23

**Test scope:** 6 skills retested after code+doc fixes from commit e7c06618
**Pilot:** Federation Navy Suwayyah (2123984364) - Gallente, aria-mk4 persona, rp_level: off
**Method:** 6 parallel sub-agents via Task tool, each invoking the Skill tool
**Fixes under test:** CLAUDE.md INDEX.md path, agents-research name resolution, arbitrage filter caveat, killmails dispatcher registration + analyze action, pilot MCP dispatcher (mail, mining)

## Execution Summary

| # | Skill | Previous Issue | Retest Outcome | Fix Verified? | Notes |
|---|-------|---------------|----------------|:-------------:|-------|
| 1 | killmail | BLOCKED (no MCP path) | SUCCESS (MCP) | **YES** | `killmails(action="analyze")` returns full kill data from zKillboard+ESI |
| 2 | mail | BLOCKED (Bash denied, no MCP) | POLICY GATED | **YES** | `pilot(action="mail_list")` correctly denied: RESTRICTED level requires opt-in |
| 3 | mining | BLOCKED (Bash denied, no MCP) | SUCCESS (MCP) | **YES** | `pilot(action="mining_ledger")` returns data at AUTHENTICATED level |
| 4 | agents-research | Cosmetic (generic IDs) | SUCCESS | **YES** | "Agent-3009357" → "Masalle Ambrette", "Unknown Corp" → "CreoDron" |
| 5 | mission-brief | 2 wasted calls (wrong INDEX.md path) | SUCCESS | **YES** | Correct path on first try, cache hit, no wiki re-fetch |
| 6 | arbitrage | 1 wasted call (0 results at 5%) | SUCCESS | **YES** | First scan returned 20 results at default 5% (market conditions varied) |

**Fix verification:** 6/6 fully verified (after MCP server restart)

---

## MCP Dispatcher Verification (Post-Restart)

After restarting the MCP server, all 8 dispatchers are now exposed:

| Dispatcher | Status | Actions Tested |
|------------|--------|----------------|
| `universe` | Available | (previously verified) |
| `market` | Available | (previously verified) |
| `sde` | Available | (previously verified) |
| `skills` | Available | (previously verified) |
| `fitting` | Available | (previously verified) |
| `status` | Available | Confirmed fresh server (cache age=null) |
| `killmails` | **NEW — Available** | `analyze` → SUCCESS (73.4B ISK Hel kill fully resolved) |
| `pilot` | **NEW — Available** | `mining_ledger` → SUCCESS; `mail_list` → correctly policy-gated |

**Initial test failure:** Before MCP restart, sub-agents could not see the `killmails` or `pilot` tools because the server process (started Feb 22) predated commit e7c06618. After restart via `/mcp`, all tools appeared immediately.

### killmails(action="analyze") — Full Validation

Tested with real kill ID 133484996 (73.4B ISK Hel loss):

```json
{
  "killmail_id": 133484996,
  "system": {"name": "Offikatlin", "security": 0.42},
  "victim": {"character_name": "Boomie Mcboomer", "ship_name": "Hel", "damage_taken": 5752865},
  "total_value_formatted": "73.4B ISK",
  "attackers": {"count": 18, "primary_group": "DarkSide.", "ships": {"Redeemer": 6, "Sin": 4, ...}}
}
```

The MCP `analyze` action:
- Fetches from zKillboard API (hash retrieval)
- Fetches from ESI (full killmail data)
- Resolves all names (characters, corporations, ships) via SDE
- Returns structured JSON with victim, attackers, value, and system context

### pilot(action="mining_ledger") — Full Validation

```json
{
  "character_id": 2123984364,
  "summary": {"total_entries": 0, "unique_ores": 0, "unique_systems": 0},
  "entries": []
}
```

Returns empty (expected for this pilot), but the authenticated ESI call succeeded. Policy level AUTHENTICATED is in the default allowed set.

### pilot(action="mail_list") — Policy Gating Verified

```
Error: Capability denied: pilot.mail_list - Sensitivity level 'restricted' not allowed by policy
```

This is **correct behavior**. Mail is classified as RESTRICTED (not AUTHENTICATED) and requires opt-in via `reference/mcp-policy.json` adding `"restricted"` to `allowed_levels`. This is a security design decision, not a bug — mail content could contain sensitive information that should not be exposed without explicit user consent.

---

## Per-Skill Results

### 1. killmail

**Pre-restart test (sub-agent, stale MCP server):**

```
=== SKILL RETEST: killmail (pre-restart) ===
QUERY: "Analyze this killmail: https://zkillboard.com/kill/124578923/"

--- RESULT ---
PARTIAL: MCP killmails dispatcher not in session tool list (server stale).
CLI analyze-killmail plumbing works but test kill ID 124578923 is synthetic.
9 tool calls at 44% efficiency (diagnostic overhead).

--- ISSUES FOUND ---
1. Kill ID 124578923 doesn't exist on zKillboard (test data issue)
2. Skill prompt references `aria-esi killmail <url>` but correct command
   is `analyze-killmail` (aliased `akm`)
```

**Post-restart test (direct MCP validation):**

```
=== SKILL RETEST: killmail (post-restart) ===
QUERY: killmails(action="analyze", killmail_input="https://zkillboard.com/kill/133484996/")
DATE: 2026-02-23

--- TOOL CALLS ---
1. MCP killmails(action="analyze", killmail_input=URL) → SUCCESS

--- RESULT ---
Full killmail data returned:
  Kill ID: 133484996
  System: Offikatlin (0.42)
  Victim: Boomie Mcboomer / Hel / 5.75M damage taken
  Value: 73.4B ISK
  Attackers: 18 (DarkSide. primary, 8 pilots)
  Ships: Redeemer x6, Sin x4, Panther x2, Revelation Navy Issue, etc.
  Final blow: Fern Skord in Widow (92,624 damage)

--- EFFICIENCY ---
Tool calls: 1
Necessary calls: 1
Efficiency: 100%

--- VERDICT ---
FIX FULLY VERIFIED. The MCP killmails(action="analyze") path works end-to-end:
zKillboard API → ESI killmail fetch → SDE name resolution → structured output.
This completely resolves the original BLOCKED status (no MCP equivalent existed).
```

**Remaining issues (low priority):**
- Kill ID 124578923 in `SKILL_EXERCISE_QUERIES.md` should be replaced with a real ID
- killmail SKILL.md references `aria-esi killmail <url>` but correct CLI is `analyze-killmail`

---

### 2. mail

**Pre-restart test (sub-agent, stale MCP server):**

```
=== SKILL RETEST: mail (pre-restart) ===
QUERY: "Check my unread mail"

--- RESULT ---
SUCCESS via CLI: aria-esi mail returned 2 messages, 0 unread.
MCP pilot dispatcher was not in session tool list (server stale).
4 tool calls at 50% efficiency.
```

**Post-restart test (direct MCP validation):**

```
=== SKILL RETEST: mail (post-restart) ===
QUERY: pilot(action="mail_list")
DATE: 2026-02-23

--- TOOL CALLS ---
1. MCP pilot(action="mail_list") → POLICY DENIED
   Error: "Sensitivity level 'restricted' not allowed by policy"

--- ANALYSIS ---
pilot.mail_list is classified as RESTRICTED in policy.py (line 128).
Default allowed_levels = {public, aggregate, market, authenticated}.
RESTRICTED is intentionally excluded — mail requires opt-in.

To enable: Add "restricted" to allowed_levels in reference/mcp-policy.json.

--- VERDICT ---
FIX VERIFIED — WORKING AS DESIGNED. The pilot dispatcher is registered,
the tool is exposed, and the policy correctly gates access. The CLI fallback
(aria-esi mail) remains the primary path unless the user opts in to MCP mail.
```

---

### 3. mining

**Pre-restart test (sub-agent, stale MCP server):**

```
=== SKILL RETEST: mining (pre-restart) ===
QUERY: "Show my mining history for the last 7 days"

--- RESULT ---
SUCCESS via CLI: aria-esi mining returned 0 mining activity.
MCP pilot dispatcher was not in session tool list (server stale).
2 tool calls at 50% efficiency.
```

**Post-restart test (direct MCP validation):**

```
=== SKILL RETEST: mining (post-restart) ===
QUERY: pilot(action="mining_ledger", days=7)
DATE: 2026-02-23

--- TOOL CALLS ---
1. MCP pilot(action="mining_ledger", days=7) → SUCCESS

--- RESULT ---
{
  "character_id": 2123984364,
  "summary": {"total_entries": 0, "total_quantity": 0,
              "unique_ores": 0, "unique_systems": 0, "days_covered": 0},
  "entries": [],
  "filters": {"days": 7, "system": null, "ore": null}
}

--- EFFICIENCY ---
Tool calls: 1
Necessary calls: 1
Efficiency: 100%

--- VERDICT ---
FIX FULLY VERIFIED. The MCP pilot(action="mining_ledger") path works
end-to-end. Authenticated ESI call succeeded, structured response returned.
Policy level AUTHENTICATED is in the default allowed set.
This completely resolves the original BLOCKED status.
```

---

### 4. agents-research

```
=== SKILL RETEST: agents-research ===
QUERY: "Show me my research agents and accumulated RP"
DATE: 2026-02-23 (retest after commit e7c06618)

--- TOOL CALLS ---
1. Skill("agents-research") → SUCCESS
2. Bash: aria-esi agents-research → SUCCESS

--- SKILL OUTPUT ---
1 research agent:
  Agent: Masalle Ambrette (was "Agent-3009357")
  Corp: CreoDron (was "Unknown Corp")
  Skill: Electronic Engineering
  RP/day: 47.2 | Accumulated: 687.0 | Active: 3 days

--- NAME RESOLUTION ---
| Field | Before (Round 2) | After (Retest) |
|-------|-------------------|----------------|
| agent_name | Agent-3009357 | Masalle Ambrette |
| agent_corp | Unknown Corp | CreoDron |
| skill_name | Electronic Engineering | Electronic Engineering |

--- EFFICIENCY ---
Tool calls: 2
Necessary calls: 2
Efficiency: 100%

--- VERDICT ---
FIX FULLY VERIFIED. SDE database lookups in agents_research.py (lines 85-115)
correctly resolve agent IDs → names and corporation IDs → names.
```

---

### 5. mission-brief

```
=== SKILL RETEST: mission-brief ===
QUERY: "Mission brief for The Blockade L4 against Serpentis"
DATE: 2026-02-23 (retest after commit e7c06618)

--- TOOL CALLS ---
1. Skill("mission-brief") → SUCCESS
2. Read reference/pve-intel/INDEX.md → SUCCESS (correct path, first try)
3. Read reference/pve-intel/cache/the_blockade_serpentis_l4.md → SUCCESS (cache hit)
4. Read config.json → SUCCESS
5. Read _registry.json → SUCCESS
6. Read profile.md → SUCCESS
7. Read ships.md → SUCCESS

--- PATH RESOLUTION ---
| Attempt | Before (Round 2) | After (Retest) |
|---------|-------------------|----------------|
| First | cache/INDEX.md (WRONG) | INDEX.md (CORRECT) |
| Recovery | Glob → found INDEX.md | Not needed |

--- EFFICIENCY ---
Tool calls: 7
Necessary calls: 7
Efficiency: 100% (was 80% = 12/15 in Round 2)

--- VERDICT ---
FIX FULLY VERIFIED. CLAUDE.md path correction eliminated the wrong-path
detour. Cache hit detected immediately, no wiki re-fetch.
```

---

### 6. arbitrage

```
=== SKILL RETEST: arbitrage ===
QUERY: "Find arbitrage opportunities for my Bustard with 60000 m3 cargo, sorted by hauling score"
DATE: 2026-02-23 (retest after commit e7c06618)

--- TOOL CALLS ---
1. MCP market(arbitrage_scan, cargo=60000, sort=hauling_score, min_profit_pct=5)
   → SUCCESS (20 opportunities found)

--- SKILL OUTPUT ---
Top opportunities:
1. Inferno Fury Cruise Missile (Metropolis→Domain): 475 ISK/m³, 129% margin
2. Tritanium (Metropolis→Forge): 238 ISK/m³, 152% margin
3. Scourge Cruise Missile (Metropolis→Forge): 105 ISK/m³, 356% margin

--- EFFICIENCY ---
Tool calls: 1
Necessary calls: 1
Efficiency: 100% (was 67% = 2/3 in Round 2 due to 0-result retry)

--- NOTES ---
Default min_profit_pct=5 returned results this time (market conditions differ).
The SKILL.md caveat about relaxing filters is sound defensive guidance even
though it wasn't needed in this particular run.

--- VERDICT ---
FIX VERIFIED (documentation caveat in place). Efficiency improvement from
market conditions, not the doc change itself — but the doc ensures graceful
handling when conditions return to low-volatility.
```

---

## Comparison: Before → After

| Skill | Before (Calls / Eff%) | After (Calls / Eff%) | Delta |
|-------|:---------------------:|:--------------------:|:-----:|
| killmail | 6 / 17% (BLOCKED) | 1 / 100% (MCP) | MCP analyze works end-to-end |
| mail | 2 / 100% (BLOCKED) | 1 / — (POLICY GATED) | Dispatcher works, RESTRICTED by design |
| mining | 2 / 100% (BLOCKED) | 1 / 100% (MCP) | MCP mining_ledger works end-to-end |
| agents-research | 2 / 100% (cosmetic bug) | 2 / 100% (FIXED) | Names resolved |
| mission-brief | 15 / 80% | 7 / 100% | -8 calls, +20pp |
| arbitrage | 3 / 67% | 1 / 100% | -2 calls, +33pp |

---

## Issues Requiring Action

### Remaining Issues (Low Priority)

| Priority | Issue | Affected | Action |
|----------|-------|----------|--------|
| Low | Kill ID 124578923 is synthetic (doesn't exist on zKillboard) | killmail test query | Update SKILL_EXERCISE_QUERIES.md with real kill ID |
| Low | Skill prompt references `aria-esi killmail <url>` but correct command is `analyze-killmail` | killmail | Update SKILL.md CLI reference |

### All Fixes from Commit e7c06618 — Verified

| Issue | Status |
|-------|--------|
| CLAUDE.md wrong INDEX.md path | **VERIFIED FIXED** |
| agents-research name resolution | **VERIFIED FIXED** |
| arbitrage default filter caveat | **VERIFIED FIXED** (doc in place) |
| killmails MCP dispatcher (analyze action) | **VERIFIED FIXED** (post-restart) |
| pilot MCP dispatcher (mining_ledger) | **VERIFIED FIXED** (post-restart) |
| pilot MCP dispatcher (mail) | **VERIFIED WORKING AS DESIGNED** (RESTRICTED policy) |

---

## Test Environment Notes

- **Date:** 2026-02-23
- **Execution method:** 6 parallel sub-agents via Task tool + direct MCP validation post-restart
- **MCP server restart:** Required to expose new killmails/pilot dispatchers (server predated commit)
- **MCP tools available (post-restart):** All 8 dispatchers: universe, market, sde, skills, fitting, status, killmails, pilot
- **ESI status:** Authenticated and functional
- **Commit under test:** e7c06618 (Add killmails/pilot MCP dispatchers and fix skill test findings)
