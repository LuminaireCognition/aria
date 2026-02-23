# ARIA Skill Test Results (Final Run) - 2026-02-23

**Test scope:** 37 skills (all NONE/LOW ESI, excluding first-run-setup)
**Pilot:** Federation Navy Suwayyah (2123984364) - Gallente, aria-mk4 persona, rp_level: off
**Method:** 37 parallel sub-agents in 4 batches via Task tool
**Code state:** Post-commit a6c1f934 (all fixes applied, MCP server restarted)
**MCP dispatchers available:** All 8 (universe, market, sde, skills, fitting, status, killmails, pilot)

## Execution Summary

| # | Skill | ESI | Calls | Eff% | Outcome | Notes |
|---|-------|-----|------:|-----:|---------|-------|
| 1 | help | NONE | 0 | — | SUCCESS | Skill prompt self-contained |
| 2 | abyssal | NONE | 1 | 100 | SUCCESS | Single reference file read |
| 3 | fitting | NONE | 4 | 75 | SUCCESS | Archetype + EOS validation |
| 4 | gatecamp | NONE | 2 | 50 | PARTIAL | Niarja in Pochven; activity data contextually inapplicable |
| 5 | mission-brief | NONE | 4 | 100 | SUCCESS | Cache hit, correct INDEX.md path on first try |
| 6 | orient | NONE | 2 | 100 | SUCCESS | MCP local_area + systems |
| 7 | route | NONE | 2 | 100 | SUCCESS | MCP route + activity |
| 8 | threat-assessment | NONE | 3 | 100 | SUCCESS | Activity + systems + local_area |
| 9 | arbitrage | NONE | 2 | 100 | SUCCESS | Scan + detail, 20 opportunities |
| 10 | find | NONE | 2 | 50 | SUCCESS | NPC filter empty → expanded search found 31 sources |
| 11 | price | NONE | 2 | 100 | SUCCESS | MCP prices + SDE item_info |
| 12 | exploration | NONE | 1 | 100 | SUCCESS | Single reference file read |
| 13 | journal | NONE | 2 | 100 | SUCCESS | Read + edit missions.md |
| 14 | pi | NONE | 1 | 100 | SUCCESS | Single reference file read |
| 15 | build-cost | NONE | 2 | 100 | SUCCESS | SDE blueprint + market prices |
| 16 | reactions | NONE | 2 | 100 | SUCCESS | Market prices + calculation |
| 17 | mining-advisory | NONE | 2 | 100 | SUCCESS | sysinfo + ore_database.md |
| 18 | killmail | NONE | 1 | 100 | SUCCESS | MCP killmails(analyze) — real kill ID, full data |
| 19 | skillqueue | LOW | 1 | 100 | SUCCESS | Single CLI call, 33 skills |
| 20 | lp-store | LOW | 2 | 50 | PARTIAL | LP balance OK; lp-offers timed out (sequential type resolution) |
| 21 | orders | LOW | 1 | 100 | SUCCESS | Direct CLI, no --active detour |
| 22 | wallet-journal | LOW | 1 | 100 | SUCCESS | Single CLI call, 48 entries |
| 23 | mail | LOW | 2 | 100 | SUCCESS | MCP policy-blocked → CLI fallback, 0 unread |
| 24 | mining | LOW | 1 | 100 | SUCCESS | MCP pilot(mining_ledger), 0 entries |
| 25 | killmails | LOW | 2 | 100 | SUCCESS | Losses + detail analysis |
| 26 | skillplan | LOW | 3 | 100 | SUCCESS | Freshness check + skills + easy_80_plan |
| 27 | assets | LOW | 1 | 0 | BLOCKED | ESI timeout (token refresh failure) |
| 28 | contracts | LOW | 1 | 100 | SUCCESS | 0 contracts (expected) |
| 29 | fittings | LOW | 1 | 100 | SUCCESS | 2 saved fittings retrieved |
| 30 | agents-research | LOW | 1 | 100 | SUCCESS | Name resolution working: Masalle Ambrette / CreoDron |
| 31 | industry-jobs | LOW | 1 | 100 | SUCCESS | 1 completed job awaiting delivery |
| 32 | watchlist | NONE | 4 | 75 | SUCCESS | Resolve + add + verify |
| 33 | hunting-grounds | NONE | 1 | 100 | STUB | Clean stub, no cascading |
| 34 | mark-assessment | NONE | 0 | — | STUB | Clean stub, no cascading |
| 35 | escape-route | LOW | 0 | — | STUB | Clean stub, no cascading |
| 36 | sec-status | LOW | 0 | — | STUB | Clean stub, no cascading |
| 37 | ransom-calc | NONE | 1 | 100 | STUB | Clean stub, minimal verification |

## Aggregate Statistics

| Category | Count | Avg Calls | Avg Efficiency |
|----------|------:|----------:|---------------:|
| SUCCESS | 29 | 1.8 | 96% |
| STUB (expected) | 5 | 0.4 | 100% |
| PARTIAL | 2 | 2.0 | 50% |
| BLOCKED | 1 | 1.0 | 0% |
| **All 37** | **37** | **1.6** | **93%** |

| ESI Flag | Skills | Successes | Avg Efficiency |
|----------|-------:|----------:|---------------:|
| NONE | 23 | 21 (+ 4 stubs) | 94% |
| LOW | 14 | 12 (+ 1 stub) | 92% |

## Comparison: Previous Runs → Final Run

### Previously Problematic Skills

| Skill | Original | After Doc Fix | Final Run | Status |
|-------|----------|---------------|-----------|--------|
| orders | 4 calls / 50% | 2 / 100% | 1 / 100% | **Fixed** |
| mining-advisory | 20 / 25% | 6 / 83% | 2 / 100% | **Fixed** |
| lp-store | 19 / 16% | 2 / 100% | 2 / 50% | **Regression** (lp-offers timeout) |
| killmail | 6 / 17% (BLOCKED) | — | 1 / 100% | **Fixed** (MCP analyze) |
| mail | 2 / BLOCKED | — | 2 / 100% | **Fixed** (MCP→CLI fallback) |
| mining | 2 / BLOCKED | — | 1 / 100% | **Fixed** (MCP mining_ledger) |
| mission-brief | 15 / 80% | — | 4 / 100% | **Fixed** (INDEX.md path) |
| agents-research | 2 / cosmetic | — | 1 / 100% | **Fixed** (name resolution) |

### Stub Efficiency Improvement

| Skill | Original Calls | Final Calls | Improvement |
|-------|:--------------:|:-----------:|:-----------:|
| hunting-grounds | 5 | 1 | -4 calls |
| mark-assessment | 1 | 0 | -1 call |
| escape-route | 6 | 0 | -6 calls |
| sec-status | 8 | 0 | -8 calls |
| ransom-calc | 7 | 1 | -6 calls |
| **Total** | **27** | **2** | **-25 calls** |

Verification cascading on persona-exclusive stubs has been virtually eliminated. The "trust the stub" instruction in the sub-agent prompt was the key factor.

## Issues Found

### Active Issues

| Priority | Issue | Affected | New? |
|----------|-------|----------|:----:|
| Medium | `lp-offers` CLI hangs on large stores (sequential type ID resolution) | lp-store | **YES** |
| Low | `assets --value` ESI timeout (token refresh) | assets | **YES** (transient?) |
| Low | gatecamp skill doesn't handle Pochven systems specially | gatecamp | No (known) |

### Resolved Issues (verified in this run)

| Issue | Status |
|-------|--------|
| killmail had no MCP path | **FIXED** — `killmails(analyze)` works, 1 call |
| mail/mining had no MCP fallback | **FIXED** — pilot dispatcher + CLI fallback |
| orders `--active` flag didn't exist | **FIXED** — removed from docs |
| mining-advisory ignored data_sources | **FIXED** — 2 calls vs 20 |
| mission-brief wrong INDEX.md path | **FIXED** — correct path, 4 calls vs 15 |
| agents-research generic IDs | **FIXED** — "Masalle Ambrette" / "CreoDron" |
| Stub verification cascading | **FIXED** — 2 total calls vs 27 |

### lp-offers Timeout (New)

The `uv run aria-esi lp-offers "Federation Navy"` command hangs when resolving 300+ item type IDs sequentially via ESI. The LP balance query (`lp`) succeeds quickly but store browsing is blocked by the sequential resolution.

**Root cause:** Each type ID requires a separate ESI call during name resolution, creating O(n) latency for large stores.

**Recommendation:** Batch type lookups via POST `/universe/names/` or cache resolved type names in the SDE database.

## Test Environment Notes

- **Date:** 2026-02-23
- **Execution method:** 37 sub-agents in 4 batches (9-10 per batch)
- **MCP server:** Freshly restarted with all 8 dispatchers
- **MCP tools verified:** universe, market, sde, skills, fitting, status, killmails, pilot
- **ESI status:** Authenticated (intermittent timeout on assets endpoint)
- **Code state:** Commit a6c1f934 (final, all fixes applied)
