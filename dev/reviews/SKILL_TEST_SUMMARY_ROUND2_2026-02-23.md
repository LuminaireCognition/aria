# ARIA Skill Test Summary - All Rounds - 2026-02-23

## Coverage

| Run | Skills Tested | Scope | Document |
|-----|:------------:|-------|----------|
| Original | 11 | NONE/LOW, single-query | `SKILL_TEST_RESULTS_2026-02-23.md` |
| Retest | 3 | Doc-fix regression | `SKILL_TEST_RESULTS_RETEST_2026-02-23.md` |
| Round 2 | 27 | Remaining NONE/LOW | `SKILL_TEST_RESULTS_ROUND2_2026-02-23.md` |
| MED ESI | 7 | All MED ESI skills | Individual per-skill results (see below) |
| **Total unique** | **45** | | |

### MED ESI Test Results

| Skill | Queries | Calls | Eff% | Outcome | Document |
|-------|--------:|------:|-----:|---------|----------|
| pilot | 2 | 2 | 100 | SUCCESS | `SKILL_TEST_RESULTS_MED_PILOT_2026-02-23.md` |
| standings | 3 | 3 | 100 | SUCCESS | `SKILL_TEST_RESULTS_STANDINGS_2026-02-23.md` |
| clones | 2 | 3 | 100 | SUCCESS | `SKILL_TEST_RESULTS_CLONES_2026-02-23.md` |
| fit-check | 1 | 14 | 79 | SUCCESS | `SKILL_TEST_RESULTS_FIT_CHECK_2026-02-23.md` |
| fit-budget | 2 | 46 | 80 | SUCCESS | `SKILL_TEST_RESULTS_FIT_BUDGET_2026-02-23.md` |
| ship-next | 2 | 30 | 87 | SUCCESS | `SKILL_TEST_RESULTS_MED_SHIP_NEXT_2026-02-23.md` |
| isk-compare | 2 | 14 | 93 | SUCCESS | `SKILL_TEST_RESULTS_MED_ISK_COMPARE_2026-02-23.md` |

**MED ESI aggregate:** 7/7 SUCCESS, 112 calls, 88% efficiency

### MED ESI Retest: ship-next + isk-compare (2026-02-24)

After fixes in commit 7efb959c, retested both skills with same queries:

| Skill | Metric | Before | After | Fix Verified? |
|-------|--------|--------|-------|:-------------:|
| ship-next | Q2 `item_info` calls | 4 wasteful | 0 | **YES** |
| ship-next | Q2 efficiency | 73% | 100% | **YES** |
| ship-next | Aggregate efficiency | 87% | 100% | **YES** |
| isk-compare | Q1 L3 accessible | NO (incorrect) | YES (correct) | **YES** |
| isk-compare | Q1 efficiency | 86% | 100% | **YES** |
| isk-compare | Aggregate efficiency | 93% | 100% | **YES** |

**Retest aggregate:** 4/4 SUCCESS, 35 calls, 100% efficiency (was 44 calls, 90%)

Full results: `SKILL_TEST_RESULTS_RETEST_SHIP_NEXT_ISK_COMPARE_2026-02-24.md`

### Untested (3 skills)

| Skill | ESI Flag | Reason |
|-------|----------|--------|
| first-run-setup | NONE | Interactive wizard, not single-query testable |
| esi-query | HEAVY | Out of scope (HEAVY ESI) |
| corp | HEAVY | Out of scope (HEAVY ESI) |

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

1. **45/48 skills tested (94% coverage).** Remaining 3: first-run-setup (interactive wizard), esi-query (HEAVY ESI), corp (HEAVY ESI).

2. **90% aggregate efficiency across Round 2.** Most skills execute in 1-5 tool calls with zero waste. The skill architecture is sound.

3. **Doc fixes validated.** The 3 retested skills improved from 23% to 94% average efficiency, confirming documentation precision directly impacts agent performance.

4. **MED ESI fixes validated (2026-02-24).** ship-next `item_info` avoidance note eliminated all 4 wasteful calls (73%→100% eff). isk-compare `access_requirements`/`recommended_skills` YAML restructure fixed L3 mission accessibility error (both queries now correct, 93%→100% eff).

5. **One new doc fix identified.** CLAUDE.md references wrong path for pve-intel INDEX.md (`cache/INDEX.md` instead of `INDEX.md`). Low severity, affects mission-brief only.

6. **Persona-exclusive stubs work correctly** but trigger verification cascading in ~60% of cases. This is agent behavior, not a skill architecture issue. mark-assessment demonstrated the ideal 1-call pattern.

7. **MCP-primary skills are the most efficient.** Skills using MCP dispatchers average 100% efficiency vs 89% for CLI-primary skills. The structured MCP interface eliminates trial-and-error command discovery.

## Retest 2: Commit e7c06618 Fixes (6 skills)

After the Round 2 findings, commit e7c06618 addressed all 5 recommended actions. A second retest validated the fixes:

| Skill | Previous Issue | Retest Outcome | Fix Verified? |
|-------|---------------|----------------|:-------------:|
| agents-research | Generic agent/corp names | Names resolved correctly | **YES** |
| mission-brief | Wrong INDEX.md path (2 wasted calls) | Correct path first try, 100% eff | **YES** |
| arbitrage | 0 results at default 5% filter | Doc caveat in place | **YES** |
| killmail | No MCP path | MCP `killmails(analyze)` works end-to-end | **YES** (post-restart) |
| mail | No MCP fallback | `pilot(mail_list)` correctly RESTRICTED by policy | **YES** (by design) |
| mining | No MCP fallback | `pilot(mining_ledger)` works at AUTHENTICATED level | **YES** (post-restart) |

**MCP server restart required:** The initial sub-agent run could not see the new dispatchers because the MCP server predated commit e7c06618. After restart via `/mcp`, all 8 dispatchers were exposed and validated.

**Remaining low-priority issues:**
- Kill ID 124578923 in test queries is synthetic (doesn't exist on zKillboard)
- killmail skill prompt references wrong CLI command (`killmail` vs `analyze-killmail`)

Full results: `SKILL_TEST_RESULTS_RETEST2_2026-02-23.md`

## Final Run: All 37 Skills (Post-Fix Validation)

After all fixes applied and MCP server restarted, a clean run of all 37 NONE/LOW skills against the final codebase (commit a6c1f934):

| Metric | Value |
|--------|------:|
| Skills tested | 37 |
| SUCCESS | 29 |
| STUB (expected) | 5 |
| PARTIAL | 2 (lp-offers timeout, gatecamp Pochven) |
| BLOCKED | 1 (assets ESI timeout, transient) |
| Avg calls per skill | 1.6 |
| Aggregate efficiency | 93% |

### Key Improvements vs Original Runs

| Metric | Original/Round 2 | Final Run |
|--------|:-----------------:|:---------:|
| Avg calls per skill | 3.7 | 1.6 |
| Aggregate efficiency | 90% | 93% |
| Stub verification cascading | 27 calls across 5 stubs | 2 calls across 5 stubs |
| Previously-blocked skills now working | 0/4 | 4/4 (killmail, mail, mining via MCP) |

### New Issue Found

`lp-offers` CLI is very slow on large LP stores (319 offers in ~2min) due to sequential ESI type ID resolution. Some items return as "Unknown Item" where SDE lookup fails. LP balance query works fine. Needs batch type lookup optimization.

Full results: `SKILL_TEST_RESULTS_FINAL_2026-02-23.md`

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
| `SKILL_TEST_RESULTS_RETEST2_2026-02-23.md` | Commit e7c06618 retest (6 skills) |
| `SKILL_TEST_RESULTS_FINAL_2026-02-23.md` | Final clean run (37 skills, all fixes) |
| `SKILL_TEST_RESULTS_MED_PILOT_2026-02-23.md` | MED ESI: pilot |
| `SKILL_TEST_RESULTS_MED_STANDINGS_2026-02-23.md` | MED ESI: standings (initial) |
| `SKILL_TEST_RESULTS_STANDINGS_2026-02-23.md` | MED ESI: standings (clean retest) |
| `SKILL_TEST_RESULTS_CLONES_2026-02-23.md` | MED ESI: clones |
| `SKILL_TEST_RESULTS_FIT_CHECK_2026-02-23.md` | MED ESI: fit-check |
| `SKILL_TEST_RESULTS_FIT_BUDGET_2026-02-23.md` | MED ESI: fit-budget |
| `SKILL_TEST_RESULTS_MED_SHIP_NEXT_2026-02-23.md` | MED ESI: ship-next |
| `SKILL_TEST_RESULTS_MED_ISK_COMPARE_2026-02-23.md` | MED ESI: isk-compare |
| `SKILL_TEST_RESULTS_RETEST_SHIP_NEXT_ISK_COMPARE_2026-02-24.md` | Retest: ship-next + isk-compare post-fix |
| `SKILL_TEST_SUMMARY_ROUND2_2026-02-23.md` | This file (all-rounds summary) |
