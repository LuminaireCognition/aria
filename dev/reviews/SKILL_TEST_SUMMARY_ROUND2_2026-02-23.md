# ARIA Skill Test Summary - All Rounds - 2026-02-23

## Coverage

| Run | Skills Tested | Scope | Document |
|-----|:------------:|-------|----------|
| Original | 11 | NONE/LOW, single-query | `SKILL_TEST_RESULTS_2026-02-23.md` |
| Retest | 3 | Doc-fix regression | `SKILL_TEST_RESULTS_RETEST_2026-02-23.md` |
| Round 2 | 27 | Remaining NONE/LOW | `SKILL_TEST_RESULTS_ROUND2_2026-02-23.md` |
| **Total unique** | **38** | | |

### Untested (10 skills)

| Skill | ESI Flag | Reason |
|-------|----------|--------|
| first-run-setup | NONE | Interactive wizard, not single-query testable |
| esi-query | HEAVY | Out of scope (HEAVY ESI) |
| pilot | MED | Out of scope (MED ESI) |
| corp | HEAVY | Out of scope (HEAVY ESI) |
| standings | MED | Out of scope (MED ESI) |
| clones | MED | Out of scope (MED ESI) |
| fit-check | MED | Out of scope (MED ESI) |
| fit-budget | MED | Out of scope (MED ESI) |
| ship-next | MED | Out of scope (MED ESI) |
| isk-compare | MED | Out of scope (MED ESI) |

## Aggregate Results

### All 38 Unique Skills

| Outcome | Count | Skills |
|---------|------:|--------|
| SUCCESS | 29 | help, abyssal, fitting, gatecamp, mission-brief, orient, route, threat-assessment, watchlist, arbitrage, find, price, exploration, journal, pi, build-cost, reactions, killmails, skillplan, assets, contracts, fittings, agents-research, industry-jobs, aria-status, skillqueue, wallet-journal, orders, mining-advisory |
| STUB (expected) | 5 | ransom-calc, sec-status, hunting-grounds, mark-assessment, escape-route |
| BLOCKED (permissions) | 3 | killmail, mail, mining |
| PARTIAL | 1 | lp-store (original run only; succeeded in retest) |

### Efficiency by Category

| Category | Skills | Total Calls | Necessary | Efficiency |
|----------|-------:|------------:|----------:|-----------:|
| MCP-primary (route, orient, etc.) | 10 | 30 | 30 | 100% |
| CLI-primary (assets, fittings, etc.) | 10 | 19 | 17 | 89% |
| Reference-only (help, pi, abyssal) | 5 | 5 | 5 | 100% |
| Complex multi-source (fitting, build-cost) | 5 | 36 | 33 | 92% |
| Persona-exclusive stubs | 5 | 18 | 5 | 28% |
| Blocked (no fallback path) | 3 | 10 | 5 | 50% |

### Efficiency Distribution (Non-Stub Skills)

| Efficiency | Count | Skills |
|-----------|------:|--------|
| 100% | 22 | help, abyssal, fitting, gatecamp, orient, route, threat-assessment, arbitrage, find, price, pi, build-cost, reactions, killmails, skillplan, assets, fittings, agents-research, industry-jobs, skillqueue, wallet-journal, mark-assessment |
| 75-99% | 4 | mission-brief (80%), exploration (75%), mining-advisory (83% retest), lp-store (100% retest) |
| 50-74% | 4 | watchlist (67%), journal (67%), contracts (50%), orders (100% retest, was 50%) |
| <50% | 3 | killmail (17%), lp-store (16% original), mining-advisory (25% original) |

## Issues Requiring Action

### Documentation Fixes (actionable)

| Priority | Issue | Affected | Status |
|----------|-------|----------|--------|
| Low | CLAUDE.md wrong INDEX.md path (`cache/INDEX.md` → `INDEX.md`) | mission-brief | **New** |
| Low | Remove `--active` from orders SKILL.md | orders | **Done** (commit 81bf2ced) |
| Low | Add `data_sources` guidance to CLAUDE.md | mining-advisory | **Done** (commit 81bf2ced) |
| Low | Add `sysinfo` to MCP fallback table | mining-advisory | **Done** (commit 81bf2ced) |
| Low | Add "no local cache" note to lp-store | lp-store | **Done** (commit 81bf2ced) |

### Feature Gaps (out of scope for doc fixes)

| Priority | Issue | Affected |
|----------|-------|----------|
| Medium | No MCP actions for mail, mining, killmail | 3 CLI-only skills |
| Low | Player corp name resolution not in SDE/MCP | watchlist |
| Low | Agent name resolution returns generic IDs | agents-research |
| Low | Arbitrage default filter too restrictive | arbitrage |

### Agent Behavior Patterns (no code fix possible)

| Pattern | Frequency | Impact |
|---------|-----------|--------|
| Verification cascading on stubs | 3/5 stubs | 2-7 wasted calls per occurrence |
| Source code archaeology after denial | 2/38 skills | 5-16 wasted calls |
| Redundant verification reads | 3/38 skills | 1 wasted call each |

## Doc Fix Effectiveness (Retest Results)

| Skill | Before (calls/eff) | After (calls/eff) | Improvement |
|-------|:------------------:|:-----------------:|:-----------:|
| orders | 4 / 50% | 2 / 100% | -2 calls, +50pp |
| mining-advisory | 20 / 25% | 6 / 83% | -14 calls, +58pp |
| lp-store | 19 / 16% | 2 / 100% | -17 calls, +84pp |
| **Total** | **43 / 23%** | **10 / 94%** | **-33 calls, +71pp** |

## Conclusions

1. **38/48 skills tested (79% coverage).** Remaining 10 are MED/HEAVY ESI or interactive.

2. **90% aggregate efficiency across Round 2.** Most skills execute in 1-5 tool calls with zero waste. The skill architecture is sound.

3. **Doc fixes validated.** The 3 retested skills improved from 23% to 94% average efficiency, confirming documentation precision directly impacts agent performance.

4. **One new doc fix identified.** CLAUDE.md references wrong path for pve-intel INDEX.md (`cache/INDEX.md` instead of `INDEX.md`). Low severity, affects mission-brief only.

5. **Persona-exclusive stubs work correctly** but trigger verification cascading in ~60% of cases. This is agent behavior, not a skill architecture issue. mark-assessment demonstrated the ideal 1-call pattern.

6. **MCP-primary skills are the most efficient.** Skills using MCP dispatchers average 100% efficiency vs 89% for CLI-primary skills. The structured MCP interface eliminates trial-and-error command discovery.

## File Index

| File | Contents |
|------|----------|
| `SKILL_EXERCISE_QUERIES.md` | Full 48-skill query catalog |
| `SKILL_TEST_RESULTS_2026-02-23.md` | Original run (11 skills) |
| `SKILL_TEST_ANALYSIS_2026-02-23.md` | Original run analysis |
| `SKILL_TEST_SUMMARY_2026-02-23.md` | Original run summary |
| `SKILL_TEST_RESULTS_RETEST_2026-02-23.md` | Doc-fix retest (3 skills) |
| `SKILL_TEST_COMPARISON_2026-02-23.md` | Before/after comparison |
| `SKILL_TEST_RESULTS_ROUND2_2026-02-23.md` | Round 2 (27 skills) |
| `SKILL_TEST_SUMMARY_ROUND2_2026-02-23.md` | This file (all-rounds summary) |
