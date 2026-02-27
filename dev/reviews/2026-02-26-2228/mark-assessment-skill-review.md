# Skill Review: mark-assessment

**Path:** `.claude/skills/mark-assessment/SKILL.md`
**Timestamp:** 2026-02-26-2228
**File:** 221 lines, ~1,730 tokens

## 1. Executive Summary

The mark-assessment skill has a critical grounding failure: it contains ~100 lines of inlined ship statistics, gank calculations, and CONCORD response times (lines 68-135) that are presented as static reference data but have no declared `prerequisite_files` and no MCP verification gate. Claude will recite these numbers from the prompt without verifying against SDE or fitting tools, meaning any data drift goes undetected. The skill needs either prerequisite files for its reference tables or explicit MCP-first gates to verify ship stats at runtime.

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | 🔴 | No MCP tool calls anywhere. No `sde(action="item_info")` for ship stats, no `fitting(action="calculate_stats")` for EHP, no `market(action="prices")` for hull values. All data is inlined in the prompt. |
| Prompt hygiene | 🔴 | Lines 68-135 present ship values, EHP, and DPS figures as static tables. No instruction to verify against any data source. Claude will parrot these numbers without question. |
| Failure handling | 🟡 | Lines 215-221 "DO NOT" list covers ethical boundaries but there is no data-failure handling. If SDE/market data were queried, there would need to be fallback instructions. |
| Context window efficiency | 🔴 | ~100 lines of static reference tables (ship categories, CONCORD times, gank ship reference, profitability formula) that should either be in a prerequisite file or fetched from MCP. |

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 68-103 | "Ship Category Assessments" — three tables (Mining Ships, Industrial Ships, Mission Ships) with hull values, typical fit costs, tank EHP | **REMOVE** — inlined reference data with no authoritative source. Values like "Retriever: 28M hull, 15-25K EHP" will go stale. Should be replaced by MCP calls: `sde(action="item_info")` for ship data + `market(action="prices")` for hull value. | ~250 tokens |
| `SKILL.md` | 104-135 | "Gank Viability Calculations" — CONCORD response times table, gank ship DPS/cost reference, profitability formula | **REMOVE** — inlined static data. CONCORD response times are game mechanics that change rarely but the DPS/cost figures for gank ships are market-dependent. Extract to a prerequisite file or fetch from MCP. | ~200 tokens |
| `SKILL.md` | 137-162 | "Engagement Considerations" — high-sec ganking checklist, low-sec engagement checklist, target behavior indicators table | **CONSOLIDATE** — the behavior indicators table (lines 153-162) is useful tactical guidance; the checklists (lines 137-151) restate common PvP knowledge at length. Compress to a concise list. | ~100 tokens |
| `SKILL.md` | 164-196 | "Cargo Scanning" and "Risk Assessment" sections — green/yellow/red flag lists | **CONSOLIDATE** — three risk-tier lists (15 items total) that could be a single compact table. | ~80 tokens |
| `SKILL.md` | 30-66 | Full ASCII-box response template with example Retriever assessment | **CONSOLIDATE** — the example is useful but occupies 37 lines. Compress the template to show structure without filling in every example field. | ~120 tokens |

**Total estimated savings: ~750 tokens (~43%)**

## 4. Specific Findings

### High Severity

**H1. No MCP integration at all — pure training-data skill**
- **File:** `SKILL.md` (entire file)
- **Issue:** This skill has zero MCP tool calls. No `sde()`, no `market()`, no `fitting()`, no `universe()`. Every data point in the response — hull value, typical fit cost, EHP, DPS, CONCORD response times — comes either from inlined tables or Claude's training data. This is the exact anti-pattern ADR-006 warns against.
- **Action:** **ADD** Required Tool Calls section mandating:
  - `sde(action="item_info", item="<target_ship>")` for ship attributes
  - `market(action="prices", items=["<target_ship>"])` for current hull value
  - `fitting(action="calculate_stats", eft="...")` for EHP if a fit is provided/assumed
  - Hallucination guard: "Ship stats, hull values, and EHP figures MUST come from MCP tool calls. Do NOT use the inlined reference tables as the sole source of truth."

**H2. Inlined ship statistics tables will go stale (Pattern A)**
- **File:** `SKILL.md`, lines 68-103
- **Issue:** Three tables containing 20+ ships with hull values, typical fit costs, EHP ranges, and viability assessments. These numbers are market-dependent (hull values) and fit-dependent (EHP). Without a prerequisite file or MCP gate, they will silently go stale.
- **Action:** **REMOVE** tables. Replace with MCP-first instructions. If approximate reference data is wanted for fast responses, extract to a `reference/mechanics/gank_reference.md` prerequisite file that can be maintained independently.

**H3. CONCORD response times and gank DPS figures are unverifiable**
- **File:** `SKILL.md`, lines 104-135
- **Issue:** CONCORD response times by security level and gank ship DPS numbers are presented without source attribution. CONCORD times are stable game mechanics but the gank ship costs and DPS figures are fit-dependent and market-dependent.
- **Action:** **REMOVE** gank ship cost/DPS table (lines 119-124). Keep CONCORD response times as a brief inline reference (they are stable mechanics), or extract to a prerequisite file.

### Medium Severity

**M1. Response template is verbose**
- **File:** `SKILL.md`, lines 30-66
- **Issue:** 37-line ASCII-box example with a fully worked Retriever assessment. The structure is useful but the filled-in example values will conflict with MCP-fetched data if MCP gates are added.
- **Action:** **CONSOLIDATE** — show template structure with placeholder labels, not filled values. (~120 tokens)

**M2. Risk assessment lists are sprawling**
- **File:** `SKILL.md`, lines 164-196
- **Issue:** Green/Yellow/Red flag lists (15 items across 33 lines) enumerate common PvP situational awareness. Useful but verbose.
- **Action:** **CONSOLIDATE** into a single compact table with 3 columns (Green, Yellow, Red).

### Low Severity

**L1. "DO NOT" section is good ethical guardrailing**
- **File:** `SKILL.md`, lines 215-221
- **Issue:** None — this is appropriate and well-scoped.
- **Action:** Keep.

**L2. Integration with Other Skills table**
- **File:** `SKILL.md`, lines 198-204
- **Issue:** Three cross-references to /price, /ransom-calc, /fitting. Low token cost, contextually appropriate.
- **Action:** Keep.

## 5. Prioritized Recommendations

1. **ADD** Required Tool Calls (MANDATORY) section with `sde()`, `market()`, and `fitting()` gates — the skill currently has zero data grounding. This is the highest-priority fix.
2. **ADD** hallucination guard: "Ship stats, hull values, and EHP MUST come from MCP tool calls in this session."
3. **REMOVE** Ship Category Assessments tables (lines 68-103) — replace with MCP-first flow. (~250 tokens)
4. **REMOVE** gank ship cost/DPS reference table (lines 119-124) — market-dependent data without source. (~80 tokens)
5. **CONSOLIDATE** CONCORD response times (lines 106-116) — keep as brief reference or extract to prerequisite file. (~60 tokens)
6. **CONSOLIDATE** response template (lines 30-66) to structural outline with placeholders. (~120 tokens)
7. **CONSOLIDATE** risk assessment lists (lines 164-196) into a single compact table. (~80 tokens)
