# ARIA Skill Retest Results (ship-next + isk-compare) - 2026-02-24

**Test scope:** 2 skills, 2 queries each (retest after fixes from commit 7efb959c)
**Pilot:** Federation Navy Suwayyah (2123984364) - Gallente, aria-mk4 persona, rp_level: off
**Method:** 4 sub-agents via Task tool (parallel, haiku model)
**Code state:** Post-commit 7efb959c (skill-testing-cleanup branch)
**MCP dispatchers available:** All 8 (universe, market, sde, skills, fitting, status, killmails, pilot)
**Preflight:** Both PASS (ok: true, no missing sources or scopes)

## Fixes Under Test

| Skill | Issue | Fix (commit 7efb959c) |
|-------|-------|----------------------|
| ship-next | Q2 made 4 wasteful `sde(action="item_info")` calls (73% eff) | Removed `item_info` from MCP tools table, added avoidance note |
| isk-compare | Q1 gated L3 missions on BC III skill (NOT ACCESSIBLE) | Separated `access_requirements` from `recommended_skills` in YAML, updated SKILL.md table |

## Execution Summary

| Skill | # | Query | Calls | Eff% | Outcome | Fix Verified? |
|-------|---|-------|------:|-----:|---------|---------------|
| ship-next | 1 | What ship should I fly next for L3 missions as Gallente? | 12 | 100 | SUCCESS | N/A (Q1 was clean before) |
| ship-next | 2 | I'm in a Vexor, what's the upgrade path? | 14 | 100 | SUCCESS | YES - 0 item_info calls (was 4) |
| isk-compare | 1 | What is the best way to make ISK with my current skills? | 4 | 100 | SUCCESS | YES - L3 marked ACCESSIBLE |
| isk-compare | 2 | Compare ISK per hour for low-risk activities only | 5 | 100 | SUCCESS | YES - L3 marked ACCESSIBLE |

**Totals:** 4/4 SUCCESS, 35 calls, 100% aggregate efficiency

---

## ship-next Retest

### Q1: Ship recommendation for L3 missions
**Calls:** 12 | **Efficiency:** 100%

**Call sequence:**

| # | Tool | Action | Result |
|---|------|--------|--------|
| 1 | Skill | `ship-next` | Loaded skill instructions |
| 2 | Bash | `aria-esi ensure-fresh skills` | Fresh: true, age 0.93h |
| 3 | Bash | `aria-esi skills` | 101 skills, 6.2M SP |
| 4 | Bash | `aria-esi wallet` | 125.5M ISK |
| 5 | Bash | `aria-esi skills` (filtered) | Combat/drone/ship skills extracted |
| 6 | Read | pilot profile | Gallente, standings, playstyle |
| 7 | Read | operations.md | Ships: Rookie, Venture, Imicus |
| 8 | MCP sde | `skill_requirements` (Myrmidon) | Gallente BC I — missing |
| 9 | MCP sde | `skill_requirements` (Vexor) | Gallente Cruiser I — pilot has III |
| 10 | MCP sde | `skill_requirements` (VNI) | Gallente Cruiser II — flyable |
| 11 | MCP market | `prices` (Vexor, Myrmidon, VNI) | Prices retrieved |
| 12 | MCP skills | `training_time` (Gal BC 0→1) | 50 minutes |

**item_info calls:** 0
**Response quality:** Comprehensive 3-tier recommendation (Vexor ready now, VNI premium option, Myrmidon 50min train). Budget-aware, skill-transfer notes included.

### Q2: Vexor upgrade path
**Calls:** 14 | **Efficiency:** 100% (was 73% / 4 wasteful calls)

**Call sequence:**

| # | Tool | Action | Result |
|---|------|--------|--------|
| 1 | Skill | `ship-next` | Loaded skill instructions |
| 2 | Bash | `aria-esi ensure-fresh skills` | Fresh: true |
| 3 | Read | pilot profile | Gallente, standings |
| 4 | Read | operations.md | Ships, home region |
| 5 | Bash | `aria-esi skills` | 101 skills, 6.2M SP |
| 6 | Bash | `aria-esi wallet` | 125.5M ISK |
| 7 | Bash | `aria-esi skills` (filtered) | Drone + ship skills |
| 8 | Read | archetype manifest? | Checked reference data |
| 9 | MCP sde | `skill_requirements` (Myrmidon) | Gallente BC I missing |
| 10 | MCP sde | `skill_requirements` (VNI) | Gallente Cruiser II — flyable |
| 11 | MCP sde | `skill_requirements` (Dominix) | Full prereq chain |
| 12 | MCP market | `prices` (Vexor, Myrmidon, VNI, Dominix) | All 4 hull prices |
| 13 | MCP skills | `training_time` (BC I, BC III, BS I, BS III) | 50m, 1d2h, 1h6m, 1d11h |
| 14 | Read | additional context | Profile re-check |

**item_info calls:** 0 (previously 4)
**Response quality:** Full 3-ship progression (VNI ready → Myrmidon 1d → Dominix 2w+). Budget table, two training paths, cross-skill analysis. Same quality as before with zero waste.

### ship-next Fix Verification: PASS

| Metric | Before (2026-02-23) | After (2026-02-24) | Delta |
|--------|---------------------|---------------------|-------|
| Q1 calls | 15 | 12 | -3 |
| Q1 efficiency | 100% | 100% | — |
| Q2 calls | 15 | 14 | -1 |
| Q2 efficiency | 73% (4 waste) | 100% (0 waste) | +27% |
| Q2 item_info calls | 4 | 0 | -4 |
| Aggregate efficiency | 87% | 100% | +13% |

The avoidance note in SKILL.md successfully prevents `sde(action="item_info")` calls. The agent uses the built-in Ship Database section for ship attributes instead.

---

## isk-compare Retest

### Q1: Best ISK with current skills
**Calls:** 4 | **Efficiency:** 100%

**Call sequence:**

| # | Tool | Action | Result |
|---|------|--------|--------|
| 1 | Skill | `isk-compare` | Loaded skill instructions |
| 2 | Read | pilot profile | Standings, constraints |
| 3 | Read | isk_estimates.yaml | All activity baselines |
| 4 | Read | operations.md | Ships, security pref |

**L3 missions marked accessible?** YES
- Correctly identified L3 access via Federation Navy (4.59), Sisters of EVE (3.63), CreoDron (3.20)
- Also correctly identified L4 access via Inner Zone Shipping (6.35)
- Noted cruiser limitation: "Your ship roster needs upgrading from Venture/Imicus to a proper cruiser (Vexor)"

**Response quality:** Full activity comparison. Correctly ranked L3 missions as best current option (8-15M/hr). Included L4 access discovery. Constraint validation present. Variance warnings for exploration.

**Notable:** Did not query ESI at all — used profile data exclusively (valid per skill instructions). Much more efficient than before (was 7 calls with duplicate skills query).

### Q2: Low-risk activities only
**Calls:** 5 | **Efficiency:** 100%

**Call sequence:**

| # | Tool | Action | Result |
|---|------|--------|--------|
| 1 | Skill | `isk-compare` | Loaded skill instructions |
| 2 | Read | pilot profile | Standings, constraints |
| 3 | Read | operations.md | Ships, security pref |
| 4 | Glob | `isk_estimates.yaml` | Located reference file |
| 5 | Read | isk_estimates.yaml | All activity baselines |

**L3 missions marked accessible?** YES
- Same correct standings-based assessment
- Correctly filtered to highsec-only activities
- Explicit constraint validation block included

**Response quality:** Comprehensive ranked table. Correctly separated "accessible now" from "needs training". Included standings-based access explanation. Training roadmap included.

### isk-compare Fix Verification: PASS

| Metric | Before (2026-02-23) | After (2026-02-24) | Delta |
|--------|---------------------|---------------------|-------|
| Q1 calls | 7 | 4 | -3 |
| Q1 efficiency | 86% | 100% | +14% |
| Q1 L3 accessible | NO (incorrect) | YES (correct) | FIXED |
| Q2 calls | 7 | 5 | -2 |
| Q2 efficiency | 100% | 100% | — |
| Q2 L3 accessible | YES | YES | — |
| Aggregate efficiency | 93% | 100% | +7% |

The YAML restructuring (`access_requirements` vs `recommended_skills`) and SKILL.md table update successfully prevent the agent from treating recommended ship skills as hard gates. Both queries now correctly identify L3 missions as accessible when the pilot has sufficient standings, regardless of ship class.

---

## Comparison: Before vs After

### Aggregate

| Metric | 2026-02-23 | 2026-02-24 | Delta |
|--------|------------|------------|-------|
| Total calls (4 queries) | 44 | 35 | -9 |
| Aggregate efficiency | 90% | 100% | +10% |
| Wasteful item_info calls | 4 | 0 | -4 |
| L3 accessibility errors | 1 | 0 | -1 |
| All queries correct | 3/4 | 4/4 | +1 |

### Per-Skill

| Skill | Before Eff% | After Eff% | Issues Remaining |
|-------|-------------|------------|------------------|
| ship-next | 87% | 100% | None |
| isk-compare | 93% | 100% | None |

## Issues Found

None. Both fixes verified successfully. No new issues detected.

## Notes

- The `access_requirements` / `recommended_skills` distinction in the YAML is working as intended — agents now check standings for mission access and treat ship skills as optimization guidance
- The `item_info` avoidance note is effective — neither ship-next agent attempted to call it
- isk-compare agents were more efficient overall (4-5 calls vs 7 before), partly because they relied on profile data instead of ESI queries — a valid optimization per skill instructions
- Both skills now achieve 100% efficiency across all test queries
