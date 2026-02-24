# ARIA Skill Test Results (isk-compare) - 2026-02-23

**Test scope:** 1 skill (MED ESI, previously untested)
**Pilot:** Federation Navy Suwayyah (2123984364) - Gallente, aria-mk4 persona, rp_level: off
**Method:** 2 sub-agents via Task tool (one per exercise query, parallel)
**Code state:** Post-commit 01544e75 (skill-testing-cleanup branch)
**MCP dispatchers available:** All 8 (universe, market, sde, skills, fitting, status, killmails, pilot)
**Preflight:** PASS (ok: true, no missing sources or scopes)

## Execution Summary

| # | Query | Calls | Eff% | Outcome | Notes |
|---|-------|------:|-----:|---------|-------|
| 1 | What is the best way to make ISK with my current skills? | 7 | 86 | SUCCESS | Full activity comparison, correct skill gating |
| 2 | Compare ISK per hour for low-risk activities only | 7 | 100 | SUCCESS | Correctly filtered to highsec, no wasted calls |

**Totals:** 2/2 SUCCESS
**Aggregate calls:** 14 | **Aggregate efficiency:** 93%

---

## Per-Query Results

### 1. Best ISK with current skills (MED ESI)
**Query:** "What is the best way to make ISK with my current skills?"
**Calls:** 7 | **Efficiency:** 86% (6 necessary, 1 arguable)

**Call sequence:**

| # | Tool | Action | Result |
|---|------|--------|--------|
| 1 | Skill | `isk-compare` | Loaded skill instructions |
| 2 | Bash | `aria-esi ensure-fresh skills` | Fresh: true, age 0.73h |
| 3 | Read | pilot profile | Standings, constraints, playstyle |
| 4 | Read | isk_estimates.yaml | Baseline ISK/hr for all activities |
| 5 | Read | operations.md | Ships: Venture, Imicus; Highsec pref |
| 6 | Bash | `aria-esi skills` | 101 skills, 6.2M SP (first call, truncated output) |
| 7 | Bash | `aria-esi skills \| jq ... \| sort` | Full skill list extracted and sorted |

**Waste analysis:**
- Call 6: Initial `aria-esi skills` returned truncated JSON — agent then made call 7 with jq filtering to get complete sorted skill list. The first call was **partially wasteful** since the agent needed to re-query with jq to get usable data. However, the first call did provide the SP total and skill count header, so it contributed some context.

**Response quality:** Comprehensive. Covered all activity categories (missions L2-L4, exploration highsec/lowsec, mining, combat sites, abyssal, passive income). Correctly identified L2 missions as best current option (4-8M/hr), flagged L3 missions as next upgrade (needs BC III, ~8-10 days training). Included variance warnings for exploration. Correctly excluded activities pilot lacks skills for (Battlecruiser, Mining Barge, PI). Standing-aware: identified multiple corps with L2+ access.

**Notable observations:**
- Did NOT use MCP dispatchers at all — relied entirely on CLI + file reads
- Did NOT query standings via `aria-esi standings` — used profile's cached standings instead
- This is valid per skill instructions: "Profile-Based Fallback: The pilot profile contains enough for useful recommendations"
- Correctly identified pilot cannot do L3 missions yet (no BC skill) despite having L3 standings

**Missing from skill instructions compliance:**
- Did not query `aria-esi standings` as Step 1 prescribes — used profile cache instead (acceptable shortcut, profile was fresh <24h)
- Did not validate constraints with explicit "Constraints Validated" template — included constraint awareness in recommendations but not as formal block

---

### 2. Low-risk activities only (MED ESI)
**Query:** "Compare ISK per hour for low-risk activities only"
**Calls:** 7 | **Efficiency:** 100%

**Call sequence:**

| # | Tool | Action | Result |
|---|------|--------|--------|
| 1 | Skill | `isk-compare` | Loaded skill instructions |
| 2 | Bash | `aria-esi ensure-fresh skills` | Fresh: true, age 0.73h |
| 3 | Bash | `aria-esi skills` | 101 skills, 6.2M SP (truncated) |
| 4 | Bash | `aria-esi standings` | 68 standings entries |
| 5 | Read | pilot profile | Standings, constraints, security pref |
| 6 | Read | operations.md | Ships, home region, security pref |
| 7 | Read | isk_estimates.yaml | Baseline ISK/hr for all activities |

**Response quality:** Excellent. Properly filtered to highsec-only activities as requested. Produced ranked comparison table. Correctly gated activities by pilot skills:
- L3 missions: **8-15M/hr** — accessible (has cruiser skill + L3 standings)
- Exploration (relic): **2-8M/hr** — accessible (Astrometrics IV, Archaeology III)
- Venture mining: **2-5M/hr** — accessible (Mining IV, owns Venture)
- Anomalies: **2-5M/hr** — accessible (Cruiser III)
- L4 missions: **15-30M/hr** — NOT accessible (needs BS III, ~30 days)
- Abyssal T1: **15-20M/hr** — NOT accessible (needs Cruiser IV)
- PI: **1.5-2M/day** — NOT accessible (needs CCU skill)

**Notable behavior:**
- Queried `aria-esi standings` this time (unlike Q1) — proper ESI usage
- Included explicit constraints validation block as skill instructions require
- Correctly identified lowsec exploration as excluded per "low-risk" filter despite pilot having the skills
- Included training roadmap: BS III (30d) → L4 missions as next income tier
- Referenced LP store conversion as important ISK factor
- Mentioned blitzing L4s as advanced technique

**Discrepancy vs Q1:** Query 2 correctly identified L3 missions as accessible (8-15M/hr) while Query 1 only recommended L2 missions (4-8M/hr). The pilot has Gallente Cruiser III and L3 standings with multiple corps — L3 missions ARE accessible in a Vexor (cruiser class). The isk_estimates.yaml lists "Battlecruiser III" as the L3 requirement, but many L3 missions are completable in well-fit cruisers. **Q2's answer is more accurate for this pilot's specific situation** (L3 access with a cruiser, running drone-based missions where hull class matters less than DPS).

---

## Verification Anchors

| Field | Value | Stability |
|-------|-------|-----------|
| L2 mission ISK/hr | 4-8M (typical 5M) | Semi-stable (from reference data) |
| L3 mission ISK/hr | 8-15M (typical 10M) | Semi-stable (from reference data) |
| L4 mission ISK/hr | 15-30M (typical 20M) | Semi-stable (from reference data) |
| Venture mining ISK/hr | 2-5M | Semi-stable (from reference data) |
| Highsec relic ISK/hr | 2-8M | Semi-stable (from reference data) |
| Pilot has L3 standings | Yes (FedNav 4.59, SoE 3.63, CreoDron 3.20) | Changes with missions |
| Pilot has L4 standings | Yes (IZS 6.35) | Changes with missions |
| Pilot has Battlecruiser skill | No | Changes when trained |
| Pilot has Mining Barge skill | No | Changes when trained |
| Pilot has CCU skill (PI) | No | Changes when trained |
| Pilot has Astrometrics IV | Yes | Stable |
| Skills freshness gate | PASS | Stable (gate logic) |
| isk_estimates.yaml used | Yes | Stable (reference data) |
| Constraints validation shown | Q1: implicit, Q2: explicit | Behavioral |

## Issues Found

### Issue 1: L3 mission accessibility disagreement between queries (MED)
**Severity:** MEDIUM — Affects ISK recommendation accuracy
**Description:** Q1 agent said L3 missions require Battlecruiser III and marked them "NOT ACCESSIBLE", recommending L2 missions as best option (4-8M/hr). Q2 agent correctly identified L3 missions as accessible (8-15M/hr) since the pilot has L3 standings and a Cruiser III skill — L3 missions can be run in a well-fit Vexor (drone cruiser). The `isk_estimates.yaml` file lists "Battlecruisers level 3" as the recommended skill, which the Q1 agent interpreted as a hard gate.
**Root cause:** The reference data lists "recommended" ship class, not strict requirements. Mission level access is gated by standings (3.0+ for L3), not ship class. A Vexor can run most L3 missions (slowly but safely).
**Impact:** Q1 undervalued the pilot's current ISK potential by ~2x (recommended 4-8M/hr instead of 8-15M/hr).
**Suggested fix:** Clarify in `isk_estimates.yaml` that the skills listed are "recommended for efficient running" not "required for access". Add a `minimum_skills` vs `recommended_skills` distinction, or add a note: "Mission level access is gated by corporation standing, not ship class."

### Issue 2: Missing `aria-esi standings` in Q1 (LOW)
**Severity:** LOW — No impact on output quality due to profile fallback
**Description:** Q1 agent used profile-cached standings instead of querying `aria-esi standings` as the skill execution flow prescribes in Step 1. The profile standings were fresh (<24h) so this had no practical impact.
**Root cause:** Agent optimization — profile was already loaded and contained standings data.
**Impact:** None in this case. Would matter if profile standings were stale.
**Fix needed:** None. The skill instructions explicitly document profile-based fallback as valid when ESI data matches.

### Issue 3: Duplicate skills query in Q1 (LOW)
**Severity:** LOW — Minor efficiency loss
**Description:** Q1 agent called `aria-esi skills` twice: once raw (truncated output) then again piped through `jq` for clean extraction. The first call was partially wasted since the agent needed the second call for complete data.
**Root cause:** Agent didn't anticipate JSON output truncation and needed to re-query with filtering.
**Impact:** 1 extra CLI call (~18 seconds ESI round-trip). Output was still correct.
**Fix needed:** None. This is inherent behavior when CLI output exceeds context limits. Could be avoided by always using jq filtering on first call.

## Notes

- This is the most data-source-heavy MED ESI skill tested: requires skills, standings, profile, operations, AND reference YAML
- Both queries correctly used the isk_estimates.yaml reference data as their baseline — no training-data-only estimates
- The skill's ESI-unavailable fallback path was not tested (ESI was available for both queries)
- Interestingly, neither query used MCP dispatchers — both relied on CLI + file reads. This is valid since isk-compare doesn't need SDE item lookups or market prices; it works from skill levels, standings, and reference estimates
- Q2 produced a more structured output (ranked table, explicit constraint validation, training roadmap) — closer to the skill's response template than Q1
- Both queries correctly included the disclaimer about estimate variance, LP conversion, and active-time-only measurement
- The skill correctly respects the Economic Advisory Protocol (operational constraints validation) in Q2
