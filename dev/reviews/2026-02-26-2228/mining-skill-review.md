# Skill Review: mining

**Path:** `.claude/skills/mining/SKILL.md`
**Timestamp:** 2026-02-26-2228
**File:** 352 lines, ~3,080 tokens

## 1. Executive Summary

The mining skill is a straightforward ESI data display skill that is inflated to 352 lines by three full JSON response schemas (~90 lines), a 16-row ore reference table that duplicates data available from `ore_database.md` (used by sibling skill mining-advisory), and three verbose response format templates. The MCP integration is clean (`pilot(action="mining_ledger")`), but the skill lacks an explicit hallucination guard despite mining ledger data being entirely ESI-sourced. Cutting the JSON schemas and ore table alone would reduce the file by ~35%.

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | 🟡 | Lines 88-91 show MCP calls, but there is no explicit "MANDATORY" gate or hallucination guard. The skill assumes Claude will use MCP but doesn't enforce it. |
| Prompt hygiene | 🟡 | Implementation is clear (lines 86-91), but ore reference table (lines 198-219) introduces static data that Claude might use to annotate mining ledger entries, bypassing MCP verification. |
| Failure handling | 🟢 | ESI unavailable (lines 59-84), ESI not configured (lines 289-303), missing scope (lines 305-318), and empty response (lines 267-285) — four distinct failure paths. |
| Context window efficiency | 🔴 | Three JSON schemas (~90 lines), 16-row ore table (~22 lines), three response templates (~65 lines), and a Self-Sufficiency Context section — most of which is dead weight. |

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 108-196 | Three JSON response structure blocks (mining ledger, mining summary, empty response) | **REMOVE** — API response schemas. Claude receives actual JSON from MCP at runtime. These 89 lines document the API, not behavior. | ~500 tokens |
| `SKILL.md` | 198-219 | "Common Ore Types" table — 16 ores with type IDs, primary minerals, and where found | **REMOVE** — this is inlined reference data (Pattern A). The sibling skill mining-advisory already declares `ore_database.md` as a prerequisite. If this skill needs ore context, it should declare the same prerequisite rather than inlining a subset. | ~150 tokens |
| `SKILL.md` | 221-285 | Three response format templates (Standard, Formatted/RP, No Activity) totaling ~65 lines | **CONSOLIDATE** — reduce to one template with variant notes. The standard and RP templates differ only in box-drawing vs. markdown table. | ~300 tokens |
| `SKILL.md` | 93-106 | "Commands" and "Options" tables documenting CLI usage | **CONSOLIDATE** — the skill uses MCP (lines 88-91). CLI tables are fallback documentation handled by CLAUDE.md. Reduce to one-line fallback note. | ~80 tokens |
| `SKILL.md` | 337-343 | "Self-Sufficiency Context" section | **REMOVE** — pilot profile already captures `market_trading: false`. Restating "mining is a primary resource acquisition method" for self-sufficient pilots is noise. | ~50 tokens |
| `SKILL.md` | 17-34 | "CRITICAL: Read-Only Limitation" and "CRITICAL: Data Retention" sections | **CONSOLIDATE** — "ARIA CANNOT start mining" is covered by CLAUDE.md's ESI read-only table. "30-day data retention" is one line of useful info buried in 8 lines. | ~60 tokens |

**Total estimated savings: ~1,140 tokens (~37%)**

## 4. Specific Findings

### High Severity

**H1. JSON response schemas are dead weight (Pattern A-adjacent)**
- **File:** `SKILL.md`, lines 108-196
- **Issue:** Three full JSON blocks documenting the mining ledger API response structure. Claude receives the actual JSON when the MCP tool returns. Documenting the schema in the prompt teaches Claude nothing it won't learn from the actual response and consumes ~500 tokens.
- **Action:** **REMOVE** entirely.

**H2. Ore reference table is inlined reference data (Pattern A)**
- **File:** `SKILL.md`, lines 198-219
- **Issue:** A 16-row table of ore types with type IDs, primary minerals, and security locations. This data exists authoritatively in `reference/mechanics/ore_database.md` (declared as a prerequisite by the sibling mining-advisory skill). Inlining a potentially stale subset here violates ADR-006 Rule 2.
- **Action:** **REMOVE** the table. If ore context is needed for mining ledger presentation, add `ore_database.md` to `prerequisite_files` or `data_sources` in frontmatter.

**H3. Missing hallucination guard**
- **File:** `SKILL.md` (entire file)
- **Issue:** No explicit instruction preventing Claude from fabricating mining ledger data. While mining ledger entries are clearly ESI data, the skill should have a guard: "Every ore name, quantity, system, and date MUST come from a `pilot()` call. NEVER fabricate mining history."
- **Action:** **ADD** hallucination guard after line 91.

### Medium Severity

**M1. Verbose response format templates**
- **File:** `SKILL.md`, lines 221-285
- **Issue:** Three templates (standard, RP, no activity) consume ~65 lines. Structural differences are minimal — RP adds box-drawing, standard uses markdown table.
- **Action:** **CONSOLIDATE** to one template with variant notes.

**M2. CLI command tables alongside MCP calls**
- **File:** `SKILL.md`, lines 93-106
- **Issue:** CLI documentation (`mining`, `mining-summary`, `--days`, `--system`, `--ore`) when the Implementation section shows MCP calls. CLAUDE.md handles fallback.
- **Action:** **CONSOLIDATE** to MCP-primary with one-line CLI fallback.

**M3. Read-Only Limitation section restates CLAUDE.md (Pattern B)**
- **File:** `SKILL.md`, lines 17-30
- **Issue:** "ARIA CANNOT: Start or stop mining, Jettison ore, Control mining lasers, Interact with the EVE client" — this is a restatement of CLAUDE.md's ESI read-only table. 14 lines for something the system-level context already covers.
- **Action:** **CONSOLIDATE** to one line: "Mining endpoints are read-only (see CLAUDE.md ESI boundaries)."

### Low Severity

**L1. Self-Sufficiency Context**
- **File:** `SKILL.md`, lines 337-343
- **Issue:** "For pilots with `market_trading: false`: Mining is a primary resource acquisition method." This is pilot profile awareness that CLAUDE.md handles.
- **Action:** **REMOVE**.

**L2. Cross-References table is useful**
- **File:** `SKILL.md`, lines 329-335
- **Issue:** References /mining-advisory, /price, /threat-assessment, /industry-jobs. Low cost, contextually relevant.
- **Action:** Keep.

## 5. Prioritized Recommendations

1. **REMOVE** JSON response structure blocks (lines 108-196) — 89 lines of API documentation. (~500 tokens)
2. **REMOVE** Common Ore Types table (lines 198-219) — inlined reference data that should come from `ore_database.md`. (~150 tokens)
3. **ADD** hallucination guard after line 91.
4. **CONSOLIDATE** three response format templates (lines 221-285) into one with variant notes. (~300 tokens)
5. **CONSOLIDATE** CLI command tables (lines 93-106) to one-line fallback. (~80 tokens)
6. **CONSOLIDATE** Read-Only Limitation section (lines 17-30) to one line. (~60 tokens)
7. **REMOVE** Self-Sufficiency Context section (lines 337-343). (~50 tokens)
