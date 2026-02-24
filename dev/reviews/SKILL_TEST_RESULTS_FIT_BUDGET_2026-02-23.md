# ARIA Skill Test Results (fit-budget) - 2026-02-23

**Test scope:** 1 skill (MED ESI, previously untested)
**Pilot:** Federation Navy Suwayyah (2123984364) - Gallente, aria-mk4 persona, rp_level: off
**Method:** 2 sub-agents via Task tool (one per exercise query, parallel)
**Code state:** Post-commit 5ab435c8 (skill-testing-cleanup branch)
**MCP dispatchers available:** All 8 (universe, market, sde, skills, fitting, status, killmails, pilot)
**Preflight:** PASS (ok: true, no missing sources or scopes)

## Execution Summary

| # | Query | Calls | Eff% | Outcome | Notes |
|---|-------|------:|-----:|---------|-------|
| 1 | Make this fit cheaper (no budget target) | 33 | 70 | SUCCESS | Full substitution analysis with EOS validation |
| 2 | Budget version with 20M ISK target | 13 | 100 | SUCCESS | Tighter variant selection, both fits validated |

**Totals:** 2/2 SUCCESS
**Aggregate calls:** 46 | **Aggregate efficiency:** 80%

---

## Per-Query Results

### 1. Make this fit cheaper — no budget target (MED ESI)
**Query:** "Make this fit cheaper" with Vexor L3 Runner EFT
**Calls:** 33 | **Efficiency:** 70% (23 necessary, 10 waste)

**Call sequence:**

| # | Tool | Action | Result |
|---|------|--------|--------|
| 1 | Read | pilot profile | rp_level: off, ESI-linked |
| 2 | Bash | `aria-esi skills` | 101 skills, 6.2M SP |
| 3-9 | MCP sde | `skill_requirements` × 7 (each T2 module/drone) | 7 unflyable items identified |
| 10-16 | MCP sde | `meta_variants` × 7 (each unflyable item) | T1/compact alternatives found |
| 17-23 | MCP sde | `skill_requirements` × 7 (each T1 alternative) | All alternatives flyable |
| 24 | MCP market | `prices` (16 items — original + budget) | Fresh Jita prices |
| 25 | MCP market | `prices` (Large Cap Battery I — missed first batch) | 303.5K ISK |
| 26 | MCP fitting | `calculate_stats` (original fit) | 612 DPS, 10.3K EHP |
| 27 | MCP fitting | `calculate_stats` (budget fit) | 431 DPS, 10.1K EHP |

**Waste analysis:**
- Call 1: Profile read — skill already loaded profile context, **1 redundant**
- Call 25: Missed item in first price batch — **1 waste** (should have included all items upfront)
- Calls 17-23: Skill requirements for T1 alternatives — **~5 redundant** (most T1 modules require very low skills that could be inferred; only edge cases need checking)
- Calls 3-9: Could have used fitting `check_requirements` instead of 7 individual SDE calls — **~3 redundant** (one call replaces many)

**Budget result:** 21.3M ISK (down from 35.2M, -39% savings)

**Performance comparison:**
| Metric | Original | Budget | Change |
|--------|----------|--------|--------|
| DPS | 612 | 431 | -30% |
| EHP | 10,258 | 10,084 | -2% |
| Speed | 627 m/s | 599 m/s | -4% |
| Cap recharge | 16.6/s | 15.5/s | -7% |
| Cost | 35.2M | 21.3M | -39% |

**Response quality:** Comprehensive. Included per-module substitution table with savings, EOS-validated performance comparison, EFT-format budget fit for clipboard, and training priority roadmap.

---

### 2. Budget version with 20M ISK target (MED ESI)
**Query:** "Budget version of this fit with a 20M ISK target" with same Vexor EFT
**Calls:** 13 | **Efficiency:** 100%

**Call sequence:**

| # | Tool | Action | Result |
|---|------|--------|--------|
| 1 | MCP fitting | `extract_requirements` | 30 unique skills extracted |
| 2 | MCP market | `valuation` (original fit) | 32.37M ISK |
| 3-9 | MCP sde | `meta_variants` × 7 (T2 modules + drones) | Variants for all items |
| 10 | MCP market | `prices` (16 variant items) | Fresh Jita prices |
| 11 | MCP market | `prices` (Hobgoblin I — supplemental) | 15.7K ISK |
| 12 | MCP fitting | `calculate_stats` (original fit) | 612 DPS, 10.3K EHP |
| 13 | MCP fitting | `calculate_stats` (budget fit) | 431 DPS, 10.1K EHP |

**Budget result:** 18.98M ISK (under 20M target, -41% savings)

**Performance comparison:**
| Metric | Original | Budget | Change |
|--------|----------|--------|--------|
| DPS | 612 | 431 | -30% |
| EHP | 10,258 | 10,084 | -2% |
| Speed | 627 m/s | 599 m/s | -5% |
| Cap recharge | 16.6/s | 14.0/s | -16% |
| Cost | 32.37M | 18.98M | -41% |

**Response quality:** Comprehensive. Met the 20M budget target (18.98M actual). Included per-module substitution table, EOS-validated stats for both fits, resist profile comparison, fitting margin analysis, content recommendations by mission level, and copyable EFT budget fit.

---

## Verification Anchors

| Field | Value | Stability |
|-------|-------|-----------|
| Original fit cost | ~32-35M ISK | Volatile (market prices) |
| Budget fit cost | ~19-21M ISK | Volatile (market prices) |
| Cost savings | ~39-41% | Semi-stable (relative) |
| Original DPS (all V) | ~612 | Stable (EOS calculation) |
| Budget DPS (all V) | ~431 | Stable (EOS calculation) |
| DPS loss | ~30% | Stable |
| EHP loss | ~2% | Stable |
| Both fits EOS-validated | Yes | Stable |
| Budget fit meets 20M target | Yes (18.98M) | Volatile (market) |
| Module name resolution | All succeeded first try | Stable (names updated) |
| T1 alternatives all flyable | Yes | Changes with pilot skills |

## Issues Found

None. Both queries executed cleanly. Module name resolution succeeded on first try (post module-name fix). EOS validation worked for both original and budget fits.

## Notes

- This skill was previously categorized as "MED ESI, out of scope" in the NONE/LOW testing rounds
- fit-budget is the most call-intensive skill tested: query 1 used 33 calls due to exhaustive per-module variant research
- Query 2 was significantly more efficient (13 calls) — different agent approached the problem more directly using `extract_requirements` + `meta_variants` without redundant skill requirement lookups
- Both queries converged on nearly identical budget fits with consistent performance metrics, validating reproducibility
- The skill correctly uses EOS (`fitting calculate_stats`) to validate both original and budget fits rather than estimating performance
- Cap Recharger II was kept in both budget fits (already T2 but cheap at ~600K each) — correct cost/performance tradeoff
- Rigs were kept as-is in both (already T1, no downgrade possible) — correct behavior
