# ARIA Skill Test Analysis - 2026-02-23

## Overview

Eleven skills were tested by dispatching sub-agents that invoked each skill via the Skill tool and followed the loaded prompt to completion. This document analyzes each skill's execution for correctness, efficiency, and issues requiring action.

**Test context:** Federation Navy Suwayyah (2123984364), Gallente, aria-mk4 persona, rp_level: off, 1-day-old character.

**Selection criteria:** Single-query skills with ESI flag NONE or LOW.

---

## Per-Skill Analysis

### 1. aria-status

**Query:** "Give me a status report"
**ESI flag:** NONE
**Outcome:** SUCCESS

**Execution path (8 tool calls):**

| # | Call | Verdict |
|---|------|---------|
| 1 | Read config.json | Necessary |
| 2 | Read _registry.json | Necessary |
| 3 | Read profile.md | Necessary |
| 4 | Read operations.md | Necessary |
| 5 | Read missions.md | Necessary |
| 6 | Read ships.md | Necessary |
| 7 | Bash: `aria-esi sync-profile` | Necessary |
| 8 | MCP: `status()` | Dead end (permission denied) |

**Efficiency:** 7/8 calls necessary (88%). Near-optimal. The MCP denial was unforeseeable.

**Issues:**

| Issue | Severity | Action |
|-------|----------|--------|
| Home base fields show `[To be determined]` | None (pilot state) | No action needed |
| ships.md (13 ships) vs operations.md (3 ships) ambiguity | Low | Consider documenting which is authoritative |
| MCP status tool has no CLI fallback | Low | Agent degraded gracefully; not blocking |

---

### 2. killmail

**Query:** "Analyze this killmail: https://zkillboard.com/kill/124578923/"
**ESI flag:** NONE
**Outcome:** BLOCKED

**Execution path (6 tool calls):**

| # | Call | Verdict |
|---|------|---------|
| 1 | Skill("killmail") | Necessary |
| 2 | WebFetch (zKillboard API) | Dead end (denied) |
| 3 | Bash (curl fallback) | Dead end (denied) |
| 4 | Glob for killmail source code | Unnecessary |
| 5 | Read killmail.py (444 lines) | Unnecessary |
| 6 | Read killmails.py MCP dispatcher | Unnecessary |

**Efficiency:** 1/6 calls necessary (17%). After the two permission denials, the agent should have reported the limitation. Instead it spent 3 calls reverse-engineering source code that produced no user-facing output.

**Issues:**

| Issue | Severity | Action |
|-------|----------|--------|
| No MCP action for single-killmail analysis | Medium | Add `killmail` action to the killmails MCP dispatcher, or document as CLI-only |
| Skill has hard dependency on WebFetch (zKillboard) + Bash | Medium | No degradation path when either is unavailable |
| Agent explored source code instead of failing fast | Low | Agent behavior, not a skill bug |

---

### 3. mining-advisory

**Query:** "What ore should I mine in Masalle for manufacturing?"
**ESI flag:** NONE
**Outcome:** SUCCESS (but highly inefficient)

**Execution path (20 tool calls):**

| # | Call | Verdict |
|---|------|---------|
| 1 | Skill("mining-advisory") | Necessary |
| 2 | MCP: universe systems lookup | Dead end (denied) |
| 3 | Bash: `aria-esi systems Masalle` | Dead end (wrong command name) |
| 4 | Bash: `aria-esi sysinfo Masalle` | Necessary |
| 5 | Read profile.md | Necessary |
| 6 | Read operations.md | Necessary |
| 7 | Bash: `ls` pilot directory | Unnecessary (could read file directly) |
| 8 | Bash: `ls` industry directory | Unnecessary (could read file directly) |
| 9 | Read industry/blueprints.md | Marginal (profile already stated "no manufacturing capability") |
| 10 | Read planetary-interaction.json | Unnecessary (wrong game system — PI is not mining) |
| 11 | Bash: `find reference/` for data files | Unnecessary (`data_sources` already listed the file) |
| 12 | Read material_sources.json | Unnecessary (superseded by ore_database.md) |
| 13 | Bash: `find` for ore files | Unnecessary (`data_sources` already listed the file) |
| 14 | Read ore_database.md | Necessary |
| 15 | Bash: `aria-esi assets` (full dump, ~91s) | Unnecessary ("what should I mine" ≠ "what do I have") |
| 16 | Bash: `aria-esi assets | grep` (~93s) | Unnecessary (same wrong premise, second attempt) |
| 17 | Bash: `aria-esi skills | grep Mining` | Marginal (useful for yield estimates, not strictly required) |
| 18 | Read skill directory (EISDIR error) | Dead end |
| 19 | Bash: `ls` skill directory | Unnecessary |
| 20 | Read SKILL.md (already loaded by Skill tool) | Unnecessary |

**Efficiency:** 5/20 calls necessary (25%). The two `assets` calls alone consumed ~184 seconds on irrelevant data.

**Issues:**

| Issue | Severity | Action |
|-------|----------|--------|
| Agent ignored `data_sources` field listing `reference/mechanics/ore_database.md` | Medium | Skill docs are clear; this is agent behavior |
| Agent confused PI data with mining ore data | Low | Agent behavior |
| Agent queried assets for a forward-looking advisory | Low | Agent behavior |
| Agent re-read SKILL.md already loaded by the Skill tool | Low | Agent behavior |
| CLI command `aria-esi systems` doesn't exist (agent guessed wrong) | Low | CLAUDE.md fallback table doesn't list a `systems` CLI equivalent; consider adding a note |
| `data_sources` field lists `ships.md` but agent used `operations.md` for ship roster | Low | Clarify which file is authoritative for ship data |

**Structural observation:** The skill's `data_sources` metadata correctly listed the 3 files needed (profile.md, operations.md, ore_database.md). An agent that reads and trusts this field would have completed in 5 calls. The skill itself is well-structured; the inefficiency was entirely in agent navigation.

---

### 4. ransom-calc (paria-exclusive)

**Query:** "How much ransom should I charge for a Mackinaw with a pod?"
**ESI flag:** NONE
**Outcome:** STUB (expected — persona mismatch)

**Execution path (7 tool calls):**

| # | Call | Verdict |
|---|------|---------|
| 1 | Skill("ransom-calc") → stub returned | Necessary |
| 2 | Read _index.json (1529 lines) | Unnecessary (stub already declared exclusivity) |
| 3 | Read profile.md | Unnecessary (session context already provided persona) |
| 4 | Read SKILL.md | Unnecessary (identical to Skill tool output) |
| 5 | Read ransom-calc.md (redirect target, 253 lines) | Unnecessary (access was correctly denied) |
| 6 | Glob manifest.yaml | Unnecessary (path is deterministic) |
| 7 | Read manifest.yaml | Unnecessary (stub already showed access denied) |

**Efficiency:** 1/7 calls necessary (14%).

**Issues:**

| Issue | Severity | Action |
|-------|----------|--------|
| Agent re-read SKILL.md already returned by Skill tool | Low | Agent behavior (verification cascading) |
| Agent read the blocked redirect target | Low | Agent behavior (curiosity, not following the stub's instructions) |
| Agent read _index.json (1529 lines) to confirm what the stub already stated | Low | Agent behavior |
| No skill-level issues found | — | Persona exclusivity working correctly |

---

### 5. skillqueue

**Query:** "What am I currently training and when does my queue finish?"
**ESI flag:** LOW
**Outcome:** SUCCESS

**Execution path (1 tool call):**

| # | Call | Verdict |
|---|------|---------|
| 1 | Bash: `aria-esi skillqueue` | Necessary |

**Efficiency:** 1/1 calls necessary (100%). Optimal execution.

**Issues:** None. The CLI returned complete, pre-formatted data (30 skills, progress percentages, ETAs). The agent trusted the output and formatted it directly.

---

### 6. lp-store

**Query:** "How much LP do I have and what can I buy from the Federation Navy LP store?"
**ESI flag:** LOW
**Outcome:** PARTIAL (Bash blocked)

**Execution path (19 tool calls):**

| # | Call | Verdict |
|---|------|---------|
| 1 | Skill("lp-store") | Necessary |
| 2 | Read profile.md | Necessary |
| 3 | Bash: `aria-esi lp` | Necessary (but denied) |
| 4 | Glob skill directory | Unnecessary (already loaded by Skill tool) |
| 5 | Glob pilot directory | Unnecessary (profile already read) |
| 6 | Read .esi-sync.json | Dead end (no LP data cached here) |
| 7 | Glob userdata/esi-cache/*loyalty* | Dead end (directory doesn't exist) |
| 8 | Bash: find esi-cache | Dead end (empty/nonexistent) |
| 9 | Read userdata/ (directory) | Dead end (EISDIR error) |
| 10 | Glob userdata/**/*.json | Unnecessary (unfocused exploration) |
| 11 | Read .session-context.json | Dead end (no ESI data here) |
| 12 | Glob docs/**lp* | Unnecessary (SKILL.md already had instructions) |
| 13 | Glob src/aria_esi/**lp* | Unnecessary (file is named loyalty.py, not lp.py) |
| 14 | Glob src/aria_esi/cli/** | Dead end (directory doesn't exist) |
| 15 | Glob src/** | Unnecessary (overly broad) |
| 16 | Read __main__.py | Unnecessary (SKILL.md already listed commands) |
| 17 | Glob loyalty source | Unnecessary |
| 18 | Read loyalty.py (lines 1-100) | Unnecessary (source code archaeology) |
| 19 | Read loyalty.py (lines 100+) | Unnecessary (continued archaeology) |

**Efficiency:** 3/19 calls necessary (16%). After Bash denial at call #3, the agent should have reported the limitation. Instead it spent 16 calls searching for cached LP data (which doesn't exist) and reverse-engineering source code.

**Issues:**

| Issue | Severity | Action |
|-------|----------|--------|
| No MCP action for LP balance or LP store offers | Medium | Add `lp` and `lp-offers` actions to the market MCP dispatcher |
| Skill has no guidance for Bash-unavailable scenario | Low | Add a note in SKILL.md: "LP data is fetched live from ESI. There is no local cache." |
| Agent failed to pivot after permission denial | Low | Agent behavior, not skill bug |

---

### 7. orders

**Query:** "Show my active market orders"
**ESI flag:** LOW
**Outcome:** SUCCESS (with retracement)

**Execution path (4 tool calls):**

| # | Call | Verdict |
|---|------|---------|
| 1 | Read profile.md | Necessary |
| 2 | Bash: `aria-esi orders --help` | Unnecessary (should trust skill docs) |
| 3 | Bash: `aria-esi orders --active` | Dead end (flag doesn't exist) |
| 4 | Bash: `aria-esi orders` | Necessary |

**Efficiency:** 2/4 calls necessary (50%).

**Issues:**

| Issue | Severity | Action |
|-------|----------|--------|
| SKILL.md documented `--active` flag that doesn't exist in CLI | Low | **FIXED** — removed from SKILL.md, added note that active is the default |
| Agent defensively checked `--help` before trusting skill docs | Low | Agent behavior; ironically justified because docs were wrong |

---

### 8. wallet-journal

**Query:** "Show me my income breakdown for the last 7 days"
**ESI flag:** LOW
**Outcome:** SUCCESS

**Execution path (1 tool call):**

| # | Call | Verdict |
|---|------|---------|
| 1 | Bash: `aria-esi wallet-journal --days 7` | Necessary |

**Efficiency:** 1/1 calls necessary (100%). Optimal execution.

**Issues:** None. The CLI returned pre-aggregated income/expense breakdowns, 42 journal entries, and transaction data in a single response. The agent formatted and presented it correctly.

---

### 9. mail

**Query:** "Check my unread mail"
**ESI flag:** LOW
**Outcome:** BLOCKED (Bash denied)

**Execution path (2 tool calls):**

| # | Call | Verdict |
|---|------|---------|
| 1 | Skill("mail") | Necessary |
| 2 | Bash: any command | Necessary (but denied) |

**Efficiency:** 2/2 calls necessary (100%). The agent correctly reported the limitation without flailing.

**Issues:**

| Issue | Severity | Action |
|-------|----------|--------|
| No MCP action for mail | Medium | Add `mail` action to an MCP dispatcher |
| No CLI fallback documented in CLAUDE.md | Low | Add to the MCP fallback table |

---

### 10. mining

**Query:** "Show my mining history for the last 7 days"
**ESI flag:** LOW
**Outcome:** BLOCKED (Bash denied)

**Execution path (2 tool calls):**

| # | Call | Verdict |
|---|------|---------|
| 1 | Skill("mining") | Necessary |
| 2 | Bash: mining command | Necessary (but denied) |

**Efficiency:** 2/2 calls necessary (100%). Clean failure, documented expected behavior.

**Issues:**

| Issue | Severity | Action |
|-------|----------|--------|
| No MCP action for mining ledger | Medium | Add `mining` action to an MCP dispatcher |
| No CLI fallback documented in CLAUDE.md | Low | Add to the MCP fallback table |

---

### 11. sec-status (paria-exclusive)

**Query:** "What's my sec status and how much would tags cost to get back to -2.0 for full high-sec access?"
**ESI flag:** LOW
**Outcome:** STUB (expected — persona mismatch)

**Execution path (8 tool calls):**

| # | Call | Verdict |
|---|------|---------|
| 1 | Skill("sec-status") → stub returned | Necessary |
| 2 | Read _index.json (1529 lines) | Unnecessary |
| 3 | Read SKILL.md | Unnecessary (identical to Skill tool output) |
| 4 | Read sec-status.md (redirect target, 236 lines) | Unnecessary (access correctly denied) |
| 5 | Read profile.md | Borderline (sec status +1.58 added context to report) |
| 6 | Read .persona-context-compiled.json | Unnecessary |
| 7 | Glob manifest.yaml | Unnecessary (deterministic path) |
| 8 | Read manifest.yaml | Unnecessary |

**Efficiency:** 1/8 calls necessary (13%). Same verification cascading pattern as ransom-calc.

**Issues:**

| Issue | Severity | Action |
|-------|----------|--------|
| Agent re-read SKILL.md already returned by Skill tool | Low | Agent behavior |
| Agent read blocked redirect target | Low | Agent behavior |
| Test query premise mismatches pilot state (+1.58 asking about -2.0) | None | Test design issue, not skill bug |
| No skill-level issues found | — | Persona exclusivity working correctly |

---

## Cross-Cutting Issues

### Issue 1: CLI-Only Skills Have No Fallback

**Affected skills:** mail, mining, lp-store, killmail
**Severity:** Medium

These skills depend entirely on Bash execution of `uv run aria-esi` commands. Unlike route, price, and market skills (which have MCP dispatchers as primary paths), these skills have zero degradation path when CLI is unavailable.

**Recommendation:** Add MCP actions for these four skills to match the pattern used by the market/universe/sde dispatchers.

### Issue 2: Documentation Drift

**Affected skills:** orders (confirmed), potentially others
**Severity:** Low

The orders SKILL.md documented a `--active` flag that the CLI does not support. This caused a failed invocation and retry. While this specific instance has been fixed, it suggests skill docs may drift from CLI implementations over time.

**Recommendation:** Add a CI check or periodic validation that compares SKILL.md option tables against actual `--help` output.

### Issue 3: `data_sources` Field Ignored by Agents

**Affected skills:** mining-advisory (observed), potentially all skills with `data_sources`
**Severity:** Medium

The mining-advisory skill's `data_sources` metadata explicitly listed the 3 files needed (profile.md, operations.md, ore_database.md). The agent ignored this and spent 15 extra calls exploring the filesystem, reading wrong files (PI data), and querying irrelevant endpoints (assets). An agent that reads `data_sources` first would cut tool calls by 75%.

**Recommendation:** Add guidance to CLAUDE.md's Skill Loading section: "After loading a skill, check its `data_sources` field and read those files directly rather than exploring the filesystem."

### Issue 4: Agents Re-Read Content Already Returned by the Skill Tool

**Affected skills:** ransom-calc, sec-status, lp-store, mining-advisory
**Severity:** Low

In 4 of 11 tests, agents re-read the SKILL.md file that the Skill tool had already injected into their context. This is always a wasted call — the content is byte-identical.

**Recommendation:** This is agent behavior, not a skill architecture issue. No SKILL.md change needed.

### Issue 5: Verification Cascading on Persona-Exclusive Skills

**Affected skills:** ransom-calc, sec-status
**Severity:** Low

Both persona-exclusive stubs triggered a cascade where the agent independently verified the exclusivity decision by reading _index.json, profile.md, the redirect target, compiled artifacts, and the manifest. The stub's content already contained all of this information.

**Recommendation:** The stubs are well-designed and self-contained. No changes needed — this is agent behavior under a "be exhaustive" instruction.

### Issue 6: CLAUDE.md Missing CLI Equivalents for Some MCP Actions

**Affected skills:** mining-advisory
**Severity:** Low

The agent tried `aria-esi systems Masalle` (doesn't exist) as a CLI fallback for the `universe(action="systems")` MCP call. The CLAUDE.md MCP fallback table lists equivalents for route, activity, and hotspots, but not for the `systems` action.

**Recommendation:** Add `aria-esi sysinfo` to the fallback table, or note that not all MCP actions have CLI equivalents.

---

## Summary

| Category | Count | Skills |
|----------|------:|--------|
| Skills with no issues found | 5 | skillqueue, wallet-journal, mail, mining, aria-status |
| Skills with agent-behavior issues only | 3 | ransom-calc, sec-status, mining-advisory |
| Skills with documentation bugs | 1 | orders (fixed) |
| Skills with missing fallback paths | 4 | mail, mining, lp-store, killmail |

**Actionable items:**

| Priority | Item | Status |
|----------|------|--------|
| Low | Remove `--active` from orders SKILL.md | **Done** |
| Medium | Add MCP actions for mail, mining, lp-store, killmail | Open |
| Low | Add `data_sources` guidance to CLAUDE.md Skill Loading section | Open |
| Low | Add `sysinfo` to CLAUDE.md MCP fallback table | Open |
| Low | Add CLI flag validation check | Open |

## Source Data

- Full test results: `dev/reviews/SKILL_TEST_RESULTS_2026-02-23.md`
- Summary report: `dev/reviews/SKILL_TEST_SUMMARY_2026-02-23.md`
- Skill query catalog: `dev/reviews/SKILL_EXERCISE_QUERIES.md`
