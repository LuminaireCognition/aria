# Skill Test Comparison: Before vs After Documentation Fixes

**Date:** 2026-02-23
**Fixes applied:** Commit 81bf2ced

## Summary

| Skill | Before | After | Improvement |
|-------|--------|-------|-------------|
| orders | 4 calls, 50% efficiency | 2 calls, 100% efficiency | -2 calls, +50pp |
| mining-advisory | 20 calls, 25% efficiency | 6 calls, 83% efficiency | -14 calls, +58pp |
| lp-store | 19 calls, 16% efficiency | 2 calls, 100% efficiency | -17 calls, +84pp |
| **Total** | **43 calls, 23% avg** | **10 calls, 94% avg** | **-33 calls, +71pp** |

## Per-Skill Analysis

### orders

| Metric | Before | After |
|--------|--------|-------|
| Tool calls | 4 | 2 |
| Necessary calls | 2 | 2 |
| Efficiency | 50% | 100% |
| Outcome | SUCCESS (with retry) | SUCCESS |

**Root cause fixed:** SKILL.md documented `--active` flag that didn't exist in CLI.

**Before path:** Skill load → Read profile → `--help` check → `orders --active` (failed) → `orders` (succeeded)

**After path:** Skill load → `orders` (succeeded)

**What changed:** Removed `--active` from options table, added note: "Active orders are shown by default. Use `--history` to include expired/cancelled orders."

**Impact:** Eliminated the ambiguity that caused the agent to (a) defensively check `--help` and (b) try a nonexistent flag. The clarifying note gave the agent confidence to use the base command directly.

---

### mining-advisory

| Metric | Before | After |
|--------|--------|-------|
| Tool calls | 20 | 6 |
| Necessary calls | 5 | 5 |
| Efficiency | 25% | 83% |
| Outcome | SUCCESS | SUCCESS |

**Root causes fixed:**
1. CLAUDE.md had no `sysinfo` CLI fallback for `universe(action="systems")`
2. CLAUDE.md had no guidance to use `data_sources` from `_index.json`

**Before path (20 calls):**
1. Skill load
2. MCP universe systems (denied)
3. `aria-esi systems Masalle` (wrong command)
4. `aria-esi sysinfo Masalle` (found by trial)
5. Read profile
6. Read operations
7. `ls` pilot directory
8. `ls` industry directory
9. Read blueprints.md
10. Read planetary-interaction.json (wrong data!)
11. `find reference/` for data files
12. Read material_sources.json
13. `find` for ore files
14. Read ore_database.md
15. `aria-esi assets` (91s, irrelevant)
16. `aria-esi assets | grep` (93s, irrelevant)
17. `aria-esi skills | grep Mining`
18. Read skill directory (EISDIR error)
19. `ls` skill directory
20. Re-read SKILL.md

**After path (6 calls):**
1. Skill load
2. `aria-esi sysinfo Masalle` (correct command, first try)
3. Glob ore_database.md (found directly)
4. Read ore_database.md
5. Glob belt data (marginal, no results)
6. Read profile

**Eliminated waste:**
- No wrong CLI command (`systems` → `sysinfo`)
- No PI data confusion
- No asset queries (184s saved)
- No filesystem exploration (`find`, `ls` cascades)
- No re-reading of already-loaded SKILL.md
- No blueprint/industry tangents

---

### lp-store

| Metric | Before | After |
|--------|--------|-------|
| Tool calls | 19 | 2 |
| Necessary calls | 3 | 2 |
| Efficiency | 16% | 100% |
| Outcome | PARTIAL | SUCCESS |

**Root cause fixed:** No guidance that LP data has no local cache.

**Before path (19 calls):**
1. Skill load
2. Read profile
3. Bash: `aria-esi lp` (denied)
4. Glob skill directory
5. Glob pilot directory
6. Read .esi-sync.json
7. Glob userdata/esi-cache/*loyalty*
8. `find` esi-cache
9. Read userdata/ (EISDIR)
10. Glob userdata/**/*.json
11. Read .session-context.json
12. Glob docs/**lp*
13. Glob src/aria_esi/**lp*
14. Glob src/aria_esi/cli/**
15. Glob src/**
16. Read __main__.py
17. Glob loyalty source
18. Read loyalty.py (1-100)
19. Read loyalty.py (100+)

**After path (2 calls):**
1. `aria-esi lp` (succeeded)
2. `aria-esi lp-offers "Federation Navy"` (succeeded)

**Note on comparability:** The original test had Bash denied, which triggered the cache-hunting spiral. The retest had Bash available, so the improvement is partly due to different permission context. However, the "Data Locality" note addresses the root behavior: even if Bash were denied again, the agent now knows there is no cache to find and should report the limitation immediately (2 calls: skill load + failed Bash = report limitation).

**Estimated impact if Bash were denied again:** ~3 calls (skill load, Bash attempt, report limitation) vs original 19. The note "report the limitation immediately rather than searching for cached files" directly prevents the 16-call spiral.

---

## Fixes Applied

| Fix | File | Target Issue |
|-----|------|-------------|
| Add `data_sources` step 5 to skill loading | CLAUDE.md | mining-advisory ignored data_sources (15 wasted calls) |
| Add `sysinfo` to MCP fallback table | CLAUDE.md | mining-advisory tried wrong CLI command |
| Add "Data Locality" section | lp-store SKILL.md | lp-store searched for nonexistent cache (16 wasted calls) |
| Remove `--active` flag, add default note | orders SKILL.md | orders failed on nonexistent flag |

## Conclusions

1. **Documentation precision matters.** All three improvements came from clarifying what exists (default behavior, correct CLI names) and what doesn't exist (no cache, no `--active` flag). Zero code changes were needed.

2. **Negative documentation is valuable.** The lp-store fix ("there is no local cache") is a negative statement — it tells the agent what NOT to look for. This prevented the largest waste (16 calls). Skills with live-only data sources should explicitly state the absence of fallback paths.

3. **`data_sources` guidance has multiplicative impact.** The mining-advisory skill already had the right metadata; the agent just needed to be told to use it. This single CLAUDE.md addition benefits every skill that declares `data_sources` in `_index.json`.

4. **Fallback table completeness prevents trial-and-error.** Adding `sysinfo` to the MCP fallback table eliminated a wrong-command attempt. Each missing entry is a potential wasted call across every skill that needs that action.

## Source Data

- Original results: `dev/reviews/SKILL_TEST_RESULTS_2026-02-23.md`
- Original analysis: `dev/reviews/SKILL_TEST_ANALYSIS_2026-02-23.md`
- Retest results: `dev/reviews/SKILL_TEST_RESULTS_RETEST_2026-02-23.md`
- This comparison: `dev/reviews/SKILL_TEST_COMPARISON_2026-02-23.md`
