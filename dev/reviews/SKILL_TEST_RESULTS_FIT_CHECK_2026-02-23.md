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

## Notes

- This skill was previously categorized as "MED ESI, out of scope" in the NONE/LOW testing rounds
- fit-check is the most complex MED ESI skill tested so far: it chains freshness gate → fitting engine → skill check → training time → wallet → market valuation → substitution analysis
- The MCP dispatcher chain (fitting → sde → skills → market) works end-to-end with no fallback to CLI needed except for `ensure-fresh` and `skills`/`wallet` queries
- The legacy module name issue is the only finding; the core workflow is sound
- 14 calls is higher than most skills but justified given the multi-domain analysis required (fitting + skills + market + SDE)
