# Skill Review: mining-advisory

**Path:** `.claude/skills/mining-advisory/SKILL.md`
**Timestamp:** 2026-02-26-2228
**File:** 130 lines, ~1,470 tokens

## 1. Executive Summary

The mining-advisory skill is the leanest of the batch and the best-grounded: it declares `ore_database.md` as a prerequisite, has an explicit hallucination guard, and mandates MCP calls for system security and market prices before responding. The main issue is a 14-line inlined ore reference table (lines 76-86) that partially duplicates the declared `ore_database.md` prerequisite, plus a "Venture Optimization Tips" section that inlines ship-specific fitting advice without MCP verification. At ~1,470 tokens this skill is close to its ideal weight; targeted cuts of ~200 tokens would bring it to optimal.

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | 🟢 | Lines 23-31: Required Tool Calls table mandating `ore_database.md` read, `universe(action="systems")`, and `market(action="prices")`. Clear three-step gate. |
| Prompt hygiene | 🟢 | Lines 35-47: Field-to-Source mapping table with explicit "Required Source" column. Lines 100-109: Anti-patterns section with concrete wrong/right examples. Hallucination guard at lines 34-35. |
| Failure handling | 🟡 | No explicit failure handling for when MCP calls fail (e.g., market prices unavailable). The skill assumes all three data sources will return successfully. |
| Context window efficiency | 🟡 | At 130 lines this is reasonably compact, but the ore reference table (lines 76-86) duplicates the prerequisite file and the Venture tips (lines 93-98) are unverified inlined advice. |

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 76-86 | "Ore Reference (Gallente High-Sec)" — two tables listing manufacturing priority ores and ores to avoid for Venture | **REMOVE** — inlined reference data (Pattern A). This is a subset of `ore_database.md` which is already a declared prerequisite. The inline copy creates staleness risk and may cause Claude to skip the prerequisite read. | ~100 tokens |
| `SKILL.md` | 93-98 | "Venture Optimization Tips" — 5 bullet points of fitting/gameplay advice | **CONSOLIDATE** — some tips are useful (align while mining, use survey scanner) but others are ship-specific fitting advice ("Fit Mining Laser Upgrade in low slot") that should come from `fitting()` or `sde()` calls, not be hardcoded. Remove fitting-specific tips, keep safety tips. | ~40 tokens |
| `SKILL.md` | 116 | "Intelligence Framing" behavior note embedded in Behavior section | **REMOVE** — "Present ore data as live survey scans" is persona overlay territory. The instruction to "Follow the Intelligence Sourcing Protocol in CLAUDE.md" is a reference to CLAUDE.md behavior that belongs in the persona system, not the skill (Pattern B). | ~40 tokens |
| `SKILL.md` | 32-33 | "Step 1 is a `data_source` for this skill and MUST be read before responding" | **CONSOLIDATE** — this restates the prerequisite_files gate mechanism from CLAUDE.md's skill loading section (Pattern B). The prerequisite_files declaration in frontmatter already forces the read. | ~20 tokens |

**Total estimated savings: ~200 tokens (~14%)**

## 4. Specific Findings

### High Severity

**H1. Ore reference table duplicates prerequisite file (Pattern A)**
- **File:** `SKILL.md`, lines 76-86
- **Issue:** Two tables under "Ore Reference (Gallente High-Sec)" list 8 ores with minerals and notes (lines 78-86), plus 2 ores to avoid for Venture (lines 88-91). These are a subset of `ore_database.md`, which is declared as `prerequisite_files[0]` in frontmatter. ADR-006 Rule 2 is explicit: "SKILL.md must not inline data from prerequisite files."
- **Action:** **REMOVE** both tables. Replace with a one-line imperative: "Read `ore_database.md` for ore availability by security band and mineral yields." The Required Tool Calls table at line 29 already instructs this read.

### Medium Severity

**M1. Venture-specific fitting advice is unverified**
- **File:** `SKILL.md`, lines 93-98
- **Issue:** "Fit Mining Laser Upgrade in low slot" and "Venture's built-in +2 warp core stabilization" are specific ship mechanics claims that should be verified via `sde(action="item_info", item="Venture")` or `fitting()`. Inlining them risks staleness if the Venture is rebalanced.
- **Action:** **CONSOLIDATE** — keep the gameplay safety tips (align while mining, use survey scanner), remove the fitting-specific claims.

**M2. No failure handling for MCP data gaps**
- **File:** `SKILL.md` (entire file)
- **Issue:** The Required Tool Calls table mandates three data sources but there is no instruction for what to do if `market(action="prices")` or `universe(action="systems")` returns an error. The hallucination guard says don't fabricate, but doesn't say what to present instead.
- **Action:** **ADD** a brief failure instruction: "If market prices are unavailable, present ore recommendations based on mineral utility without ISK rankings. If system security lookup fails, ask the user to confirm their system's security level."

### Low Severity

**L1. Intelligence Framing is persona territory (Pattern B)**
- **File:** `SKILL.md`, line 116
- **Issue:** "Follow the Intelligence Sourcing Protocol in CLAUDE.md" references a CLAUDE.md behavior. The instruction to "Present ore data as live survey scans" is RP framing that belongs in a persona overlay.
- **Action:** **REMOVE** the Intelligence Framing sentence. Keep the "Brevity" note on the same line.

**L2. Prerequisite gate restatement (Pattern B)**
- **File:** `SKILL.md`, lines 32-33
- **Issue:** "Step 1 is a `data_source` for this skill and MUST be read before responding" restates the skill loading mechanism's prerequisite_files gate.
- **Action:** **CONSOLIDATE** — the line is low-cost but technically redundant. Could be trimmed to save ~20 tokens.

**L3. Contextual Suggestions section is well-scoped**
- **File:** `SKILL.md`, lines 119-130
- **Issue:** None. Four context/suggest pairs with a "don't over-suggest" note. Appropriate.
- **Action:** Keep.

## 5. Prioritized Recommendations

1. **REMOVE** Ore Reference tables (lines 76-91) — direct Pattern A violation; duplicates declared prerequisite file. (~100 tokens)
2. **ADD** failure handling instructions for when MCP calls return errors — currently missing.
3. **CONSOLIDATE** Venture Optimization Tips (lines 93-98) — keep safety tips, remove unverified fitting claims. (~40 tokens)
4. **REMOVE** Intelligence Framing sentence (line 116) — persona overlay territory. (~40 tokens)
5. **CONSOLIDATE** prerequisite gate restatement (lines 32-33) — redundant with skill loading mechanism. (~20 tokens)
