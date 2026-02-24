# ARIA Skill Test Results (fit-check) - 2026-02-23

**Test scope:** 1 skill (MED ESI, previously untested)
**Pilot:** Federation Navy Suwayyah (2123984364) - Gallente, aria-mk4 persona, rp_level: off
**Method:** 1 sub-agent via Task tool
**Code state:** Post-commit be026d53 (skill-testing-cleanup branch)
**MCP dispatchers available:** All 8 (universe, market, sde, skills, fitting, status, killmails, pilot)
**Preflight:** PASS (ok: true, no missing sources or scopes)

## Execution Summary

| # | Query | Calls | Eff% | Outcome | Notes |
|---|-------|------:|-----:|---------|-------|
| 1 | Can I fly this Vexor fit and afford it? | 14 | 79 | SUCCESS | +1 fitting failure recovery (legacy module name), +1 unnecessary meta_variants on skill, +1 redundant SDE lookup |

**Totals:** 1/1 SUCCESS
**Aggregate calls:** 14 | **Aggregate efficiency:** 79%

---

## Per-Query Results

### 1. Fit check with full EFT (MED ESI)
**Query:** "Can I fly this fit and afford it?" with Vexor L2 Mission Runner EFT
**Calls:** 14 | **Efficiency:** 79% (11 necessary, 3 waste)

**Call sequence:**

| # | Tool | Action | Result |
|---|------|--------|--------|
| 1 | Bash | `ensure-fresh skills` | fresh (age 6.84h, TTL 12h) |
| 2 | MCP fitting | `extract_requirements` (original EFT) | **FAILED** — Unknown type "Energized Adaptive Nano Membrane II" |
| 3 | MCP sde | `search` query="Energized" category="Module" | 169 results; found "EM Energized Membrane II" |
| 4 | MCP fitting | `extract_requirements` (corrected EFT) | 30 unique skills extracted |
| 5 | Bash | `aria-esi skills` | 101 skills, 6.2M SP |
| 6 | MCP fitting | `check_requirements` | NOT flyable — 6 missing skills |
| 7 | MCP skills | `training_time` (6 missing skills) | 30d 10h total |
| 8 | Bash | `aria-esi wallet` | 125,512,441 ISK |
| 9 | MCP market | `valuation` (fit items) | 31,966,600 ISK total |
| 10 | MCP sde | `meta_variants` (Hammerhead II) | 4 variants found (T1, faction) |
| 11 | MCP sde | `meta_variants` (Medium Drone Operation) | **UNNECESSARY** — skills have no meta variants |
| 12 | MCP sde | `skill_requirements` (Hammerhead II) | Med Drone Op V, Drones V, Gal Drone Spec I |
| 13 | MCP sde | `skill_requirements` (Hammerhead I) | Med Drone Op I, Drones III — pilot qualifies |
| 14 | MCP sde | `skill_requirements` (Federation Navy Hammerhead) | Med Drone Op I, Drones III — pilot qualifies |

**Efficiency breakdown:**
- Calls 1, 4-9: Core workflow (freshness, extract, check, train time, wallet, valuation) — **7 necessary**
- Calls 10, 12-14: Substitution analysis for unflyable T2 drones — **4 necessary** (skill mandates substitution suggestions)
- Call 2: Failed due to legacy module name in exercise query — **1 recovery** (not agent fault)
- Call 3: SDE search to find correct module name — **1 recovery** (not agent fault)
- Call 11: meta_variants on a skill name (no variants exist) — **1 unnecessary**

**Adjusted efficiency (excluding exercise query fault):** 11/12 = 92%

**Data returned:**

Missing skills (6):
| Skill | Current | Required | Training Time |
|-------|--------:|--------:|--------------:|
| Afterburner | III | IV | 20h 41m |
| Gallente Drone Specialization | 0 | I | 41m |
| Hull Upgrades | III | V | 11d 11h |
| Light Drone Operation | IV | V | 4d 21h |
| Medium Drone Operation | III | V | 11d 11h |
| Weapon Upgrades | III | IV | 1d 17h |

Cost analysis:
| Item | Value |
|------|------:|
| Fit total cost | 31,966,600 ISK |
| Wallet balance | 125,512,441 ISK |
| Remaining after purchase | 93,545,841 ISK |
| Replacement buffer | 3.9x |

**Response quality:** Comprehensive. Included skill gap analysis, training time, cost breakdown, wallet check, substitution suggestions (Hammerhead I / Federation Navy Hammerhead as flyable alternatives), and three action options (fly modified now, train first, budget alternative).

---

## Issues Found

### Issue 1: Legacy Module Name in Exercise Query (RESOLVED)
**Severity:** Medium → **Fixed**
**Affected:** Exercise queries, reference data, source code

**Finding:** The EFT in the exercise query contained "Energized Adaptive Nano Membrane II" — a module name CCP renamed to "Multispectrum Energized Membrane II" in 2018. The fitting engine correctly rejected the non-existent name. The agent recovered via SDE search, costing 2 extra calls.

**Resolution:** Updated all references across the codebase to use current SDE-canonical module names. No fitting engine changes needed — users are expected to use current module names. Files updated: `eos_bridge.py`, `test_tank_classifier.py`, `module_tiers.yaml`, `meta_module_alternatives.yaml`, `fit-budget/SKILL.md`, `fitting/EFT-FORMAT.md`, `tanking_mechanics.md`, `l4_missions_guide.md`, `faction_tuning.yaml`, exercise queries, examples, and archived proposals.

---

## Verification Anchors

These values can be checked against future runs to detect regressions:

| Field | Value | Stability |
|-------|-------|-----------|
| Pilot can fly fit | No (6 missing skills) | Changes with training |
| Total missing skills | 6 | Decreases as pilot trains |
| Total training time | 30d 10h | Decreases as pilot trains |
| Fit total cost (Jita sell) | ~32M ISK | Volatile (market prices) |
| Wallet balance | ~125.5M ISK | Volatile (transactions) |
| Replacement buffer | ~3.9x | Volatile |
| Hammerhead II flyable | No (needs Med Drone Op V) | Changes with training |
| Hammerhead I flyable | Yes | Stable |
| Federation Navy Hammerhead flyable | Yes | Stable |
| Exercise query module names | Current SDE-canonical | Stable (updated this commit) |
| MCP fitting extract_requirements works | Yes (with correct names) | Stable |
| MCP fitting check_requirements works | Yes | Stable |
| MCP skills training_time works | Yes | Stable |
| MCP market valuation works | Yes | Stable |

## Retest: Post Module Name Fix (commit 439e03f1)

After updating the exercise query EFT to use the current SDE-canonical name "Multispectrum Energized Membrane II", retest confirms the legacy name issue is resolved.

### Retest Execution Summary

| # | Query | Calls | Eff% | Outcome | Notes |
|---|-------|------:|-----:|---------|-------|
| 1 | Can I fly this Vexor fit and afford it? | 12 | 75 | SUCCESS | No legacy name failure; +1 wrong meta_variants scope, +2 unnecessary skill prereq lookups |

**Calls:** 12 (down from 14) | **Efficiency:** 75% (9 necessary, 3 waste)

### Retest Call Sequence

| # | Tool | Action | Result |
|---|------|--------|--------|
| 1 | Bash | `ensure-fresh skills` | fresh (age 0.0h) |
| 2 | MCP fitting | `extract_requirements` | **SUCCESS** — 30 unique skills (no failure) |
| 3 | Bash | `aria-esi skills` | 101 skills, 6.2M SP |
| 4 | Bash | `aria-esi wallet` | 125,512,441 ISK |
| 5 | MCP fitting | `check_requirements` | NOT flyable — 6 missing skills |
| 6 | MCP market | `valuation` (fit items) | 32,367,300 ISK total |
| 7 | MCP skills | `training_time` (6 missing skills) | 30d 19h total |
| 8 | MCP sde | `meta_variants` ("Afterburner II") | Wrong scope — returned 1MN variants not 10MN |
| 9 | MCP sde | `meta_variants` ("10MN Afterburner II") | Correct — 18 variants including T1 options |
| 10 | MCP sde | `skill_requirements` (Hull Upgrades) | Prereq lookup — Mechanics I |
| 11 | MCP sde | `skill_requirements` (Light Drone Operation) | Prereq lookup — Drones I |
| 12 | MCP sde | `skill_requirements` (Medium Drone Operation) | Prereq lookup — Drones III |

### Retest Efficiency Breakdown

- Calls 1-7: Core workflow (freshness, extract, skills, wallet, check, valuation, training time) — **7 necessary**
- Call 9: Substitution analysis for afterburner — **1 necessary** (suggests T1 alternative pilot can use now)
- Call 8: Wrong meta_variants scope ("Afterburner II" → 1MN results) — **1 waste** (should have queried "10MN Afterburner II" directly)
- Calls 10-12: Skill prereq lookups for skills the pilot is missing — **1 necessary, 2 redundant** (check_requirements already identified the gap; only one prereq lookup would be needed to confirm trainability)

### Retest Comparison

| Metric | Original Run | Retest |
|--------|:-----------:|:------:|
| Total calls | 14 | 12 |
| Efficiency | 79% (adj. 92%) | 75% |
| extract_requirements failures | 1 | 0 |
| Legacy name recovery calls | 2 | 0 |
| Unnecessary SDE calls | 1 | 3 |
| Core workflow calls | 7 | 7 |

The legacy name fix eliminated 2 calls. The retest introduced different waste (wrong meta_variants scope + redundant skill prereq lookups) that wasn't present in the original run — this is agent variance, not a regression. Core workflow (7 calls) is identical.

### Retest Data Consistency

| Field | Original | Retest | Match? |
|-------|----------|--------|:------:|
| Can fly fit | No | No | ✓ |
| Missing skills | 6 | 6 | ✓ |
| Training time | 30d 10h | 30d 19h | ~✓ (attribute rounding) |
| Fit cost | ~32.0M | ~32.4M | ~✓ (market price drift) |
| Wallet | 125.5M | 125.5M | ✓ |
| Replacement buffer | 3.9x | 3.9x | ✓ |

All key findings consistent between runs. Minor variations in training time and fit cost are expected (attribute calculation rounding, market price changes).

---

## Notes

- This skill was previously categorized as "MED ESI, out of scope" in the NONE/LOW testing rounds
- fit-check is the most complex MED ESI skill tested so far: it chains freshness gate → fitting engine → skill check → training time → wallet → market valuation → substitution analysis
- The MCP dispatcher chain (fitting → sde → skills → market) works end-to-end with no fallback to CLI needed except for `ensure-fresh` and `skills`/`wallet` queries
- The legacy module name issue (original run) has been resolved by updating all references to SDE-canonical names
- 12 calls is higher than most skills but justified given the multi-domain analysis required (fitting + skills + market + SDE)
- Agent variance in SDE exploration calls (meta_variants, skill_requirements) accounts for most waste — this is inherent to the open-ended substitution analysis the skill mandates
