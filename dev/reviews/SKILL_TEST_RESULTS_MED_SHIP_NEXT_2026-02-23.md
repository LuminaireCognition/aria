# ARIA Skill Test Results (ship-next) - 2026-02-23

**Test scope:** 1 skill (MED ESI, previously untested)
**Pilot:** Federation Navy Suwayyah (2123984364) - Gallente, aria-mk4 persona, rp_level: off
**Method:** 2 sub-agents via Task tool (one per exercise query, parallel)
**Code state:** Post-commit 01544e75 (skill-testing-cleanup branch)
**MCP dispatchers available:** All 8 (universe, market, sde, skills, fitting, status, killmails, pilot)
**Preflight:** PASS (ok: true, no missing sources or scopes)

## Execution Summary

| # | Query | Calls | Eff% | Outcome | Notes |
|---|-------|------:|-----:|---------|-------|
| 1 | What ship should I fly next for L3 missions as Gallente? | 15 | 100 | SUCCESS | Full progression path with prices, training times, budget analysis |
| 2 | I'm in a Vexor, what's the upgrade path? | 15 | 73 | SUCCESS | Same quality output, 4 wasteful item_info calls |

**Totals:** 2/2 SUCCESS
**Aggregate calls:** 30 | **Aggregate efficiency:** 87%

---

## Per-Query Results

### 1. Ship recommendation for L3 missions (MED ESI)
**Query:** "What ship should I fly next for L3 missions as Gallente?"
**Calls:** 15 | **Efficiency:** 100%

**Call sequence:**

| # | Tool | Action | Result |
|---|------|--------|--------|
| 1 | Skill | `ship-next` | Loaded skill instructions |
| 2 | Bash | `aria-esi ensure-fresh skills` | Fresh: true, age 0.73h |
| 3 | Bash | `aria-esi skills` | 101 skills, 6.2M SP, Gallente Cruiser III |
| 4 | Bash | `aria-esi wallet` | 125.5M ISK |
| 5 | Read | pilot profile | Gallente, L3 access FedNav 4.59, L4 IZS 6.35 |
| 6 | Read | operations.md | Ships: Rookie, Venture, Imicus |
| 7 | MCP sde | `skill_requirements` (Vexor) | Gallente Cruiser I — pilot has III ✓ |
| 8 | MCP sde | `skill_requirements` (Myrmidon) | Gallente Battlecruiser I — missing |
| 9 | MCP sde | `item_info` (Vexor) | Cruiser, type 626 |
| 10 | MCP sde | `item_info` (Myrmidon) | Combat Battlecruiser, type 24700 |
| 11 | MCP market | `prices` (Vexor, Myrmidon) | Vexor 12M, Myrmidon 52M sell |
| 12 | MCP skills | `training_time` (Gal BC 0→1) | 50 minutes |
| 13 | MCP sde | `item_info` (Vexor Navy Issue) | Cruiser faction variant |
| 14 | MCP sde | `skill_requirements` (VNI) | Gallente Cruiser II — pilot has III ✓ |
| 15 | MCP market | `prices` (VNI) | 39.9M sell |

**Response quality:** Comprehensive. Included three tiers (Ready Now: Vexor/VNI, Train <1 week: Myrmidon, Aspirational: Dominix). Budget analysis with 3x replacement cost warning. Training focus recommendations. Cross-skill transfer notes.

**Notable behavior:**
- Correctly identified Myrmidon as 50 minutes away (only BC I missing)
- Correctly identified VNI as ready-now alternative (Cruiser II required, pilot has III)
- Included Dominix as aspirational despite not querying it via SDE — used skill prompt's ship database
- Wallet-aware: noted 125.5M covers Vexor/VNI + fit, marginal for Myrmidon

---

### 2. Vexor upgrade path (MED ESI)
**Query:** "I'm in a Vexor, what's the upgrade path?"
**Calls:** 15 | **Efficiency:** 73% (11 necessary, 4 waste)

**Call sequence:**

| # | Tool | Action | Result |
|---|------|--------|--------|
| 1 | Skill | `ship-next` | Loaded skill instructions |
| 2 | Bash | `aria-esi ensure-fresh skills` | Fresh: true |
| 3 | Bash | `aria-esi skills` | 101 skills, 6.2M SP |
| 4 | Bash | `aria-esi wallet` | 125.5M ISK |
| 5 | Read | pilot profile | Gallente, standings, playstyle |
| 6 | MCP sde | `skill_requirements` (Myrmidon) | Gallente BC I missing |
| 7 | MCP sde | `skill_requirements` (VNI) | Gallente Cruiser II — flyable |
| 8 | MCP sde | `skill_requirements` (Dominix) | Gallente BS I — full chain shown |
| 9 | MCP skills | `training_time` (BC I, Cruiser IV, BC III, BS I) | 50m, 4d7h, 1d2h, 1h6m |
| 10 | MCP market | `prices` (Vexor, VNI, Myrmidon, Dominix) | All 4 hull prices |
| 11 | MCP sde | `item_info` (Vexor) | Cruiser description |
| 12 | MCP sde | `item_info` (Myrmidon) | BC description |
| 13 | MCP sde | `item_info` (VNI) | Faction cruiser description |
| 14 | MCP sde | `item_info` (Dominix) | Battleship description |

**Waste analysis:**
- Calls 11-14: `item_info` for all 4 ships — **4 wasteful**. SDE `item_info` returns flavor text and classification only, not ship bonuses or stats. The skill prompt's built-in ship database already contains the relevant details (drone bonuses, tank characteristics). These calls added no actionable data to the response.

**Response quality:** Comprehensive. Full 4-ship progression (Vexor → VNI → Myrmidon → Dominix) with training times per step, budget table, skills transfer analysis, two recommended training paths (Fast Track vs Optimized), and next-step suggestions linking to other skills (/fit-check, /skillplan).

**Notable behavior:**
- Batched training_time into a single MCP call with 4 skill entries — efficient
- Batched market prices into a single call for all 4 ships — efficient
- Included full prerequisite chain for Dominix (SC IV → Frig III → Des III → Cruiser III → BC III → BS I)
- Correctly recommended Myrmidon before VNI for L3 missions (despite VNI being ready now) because BC is the L3-appropriate hull class

---

## Verification Anchors

| Field | Value | Stability |
|-------|-------|-----------|
| Vexor hull price (Jita sell) | ~12M ISK | Volatile (market) |
| VNI hull price (Jita sell) | ~40M ISK | Volatile (market) |
| Myrmidon hull price (Jita sell) | ~52M ISK | Volatile (market) |
| Dominix hull price (Jita sell) | ~166M ISK | Volatile (market) |
| Wallet balance | 125.5M ISK | Volatile (changes with activity) |
| Gallente BC I training time | 50 minutes | Stable (rank 6 skill at base attributes) |
| Gallente Cruiser IV training | 4d 7h | Stable (rank 5, level 3→4) |
| Gallente BS I training time | 1h 6m | Stable (rank 8 skill at base attributes) |
| Pilot can fly Vexor | Yes (Cruiser III) | Stable |
| Pilot can fly VNI | Yes (Cruiser II req, has III) | Stable |
| Pilot cannot fly Myrmidon | Missing BC I | Changes when trained |
| Skills freshness gate | PASS | Stable (gate logic) |
| Wallet query succeeded | Yes | Depends on ESI |

## Issues Found

### Issue 1: Wasteful `item_info` calls (LOW)
**Severity:** LOW — No impact on output quality, minor efficiency loss
**Description:** Query 2 agent made 4 `item_info` calls (Vexor, Myrmidon, VNI, Dominix) that returned only flavor text and category classification. The SDE `item_info` action does not include ship bonuses, slot layouts, or drone bandwidth — the data needed for ship comparison. The skill prompt already contains this information in its built-in ship database section.
**Root cause:** Agent behavior — haiku model explored item details despite having them in context from the skill prompt.
**Fix needed:** None. This is inherent to LLM exploration behavior. Query 1 agent also called `item_info` but only for ships it was actively researching (Vexor, Myrmidon, VNI) — a reasonable pattern. The difference is Query 2 called it for ALL ships including Dominix which was aspirational only.

## Notes

- Both queries correctly followed the freshness gate protocol (`ensure-fresh skills` before any ESI queries)
- Both queries successfully retrieved wallet balance via `aria-esi wallet`
- The skill works well with MCP dispatchers — SDE skill_requirements, skills training_time, and market prices are the core data pipeline
- Query 1 was more focused (L3 missions → specific ship class needed) while Query 2 was broader (upgrade path → full progression tree), explaining the call count similarity but different efficiency
- Both agents produced the expected response format from the skill prompt (READY NOW / TRAIN X / ASPIRATIONAL tiers)
- Ship recommendations were faction-appropriate (Gallente drone path: Vexor → VNI → Myrmidon → Dominix)
- Budget awareness was correct: 125.5M wallet flagged as sufficient for Vexor/VNI, marginal for Myrmidon, insufficient for Dominix
