# Skill Review: standings

**Path:** `.claude/skills/standings/SKILL.md`
**Review timestamp:** 2026-02-26-2228
**Size:** 487 lines, ~3,909 tokens

## 1. Executive Summary

The standings skill is the largest in this batch and the most problematic for grounding discipline. It declares `standings_thresholds.json` and `epic_arcs.json` as `data_sources` but then inlines substantial portions of both files directly into SKILL.md (pattern A). The "Standing Thresholds" table (line 310-318), "Standing Gain Estimates" table (lines 320-328), "Time Estimates" section (lines 330-341), and "Accelerator Strategies" sections (lines 343-395) all duplicate reference data. Approximately 35-40% of the file is inlined reference data or verbose advisory prose that should be cut.

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | 🟡 | Uses ESI CLI for live standings and MCP `sde()` for agent search. However, the freshness gate is well-designed. Gap: coalition/alliance characteristics at lines 307+ (standings thresholds) are inlined rather than read from reference files. |
| Prompt hygiene | 🟡 | Good for live data (freshness gate). But advisory sections (accelerator strategies, time estimates) present training-data-quality estimates as if authoritative without sourcing them from reference files. |
| Failure handling | 🟢 | Freshness gate (lines 58-73) with clear branching on `fresh`/`esi_available` is excellent. Error handling table (lines 465-472) covers common cases. |
| Context window efficiency | 🔴 | Heavy duplication of reference file content (pattern A). Verbose example responses consume ~800 tokens. Multiple sections repeat the same facts (e.g., "epic arcs avoid derived losses" appears 4 times). |

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 310-318 | "Standing Thresholds" table — duplicates `standings_thresholds.json → agent_levels` | **REMOVE** (pattern A) | ~60 tokens |
| `SKILL.md` | 320-328 | "Standing Gain Estimates" table — duplicates `standings_thresholds.json → standing_gains` | **REMOVE** (pattern A) | ~80 tokens |
| `SKILL.md` | 330-341 | "Time Estimates (Neutral to L4)" — training-data estimates not from any reference file; unverifiable claims | **REMOVE** (pattern D) | ~100 tokens |
| `SKILL.md` | 343-395 | "Accelerator Strategies" — 53 lines restating content from `epic_arcs.json` and `standings_thresholds.json → repair_strategies` | **REMOVE** (pattern A) | ~350 tokens |
| `SKILL.md` | 282-308 | "Derived Standing Calculation" with Python code + "Required Raw for L4 by Connections Level" table — duplicates `standings_thresholds.json → derived_standings_formula` | **REMOVE** (pattern A) | ~180 tokens |
| `SKILL.md` | 397-409 | "Special Cases: Cross-Faction Implications" — restates `standings_thresholds.json → derived_standing_losses` | **REMOVE** (pattern A) | ~80 tokens |
| `SKILL.md` | 411-416 | "L5 Agents (Special Case)" — already in reference data `agent_levels.5` | **REMOVE** (pattern A) | ~40 tokens |
| `SKILL.md` | 198-237 | "Standing Plan Query" verbose example response — 40-line ASCII box format. A compact example would steer equally well. | **CONSOLIDATE** | ~250 tokens |
| `SKILL.md` | 247-279 | "Standing Repair Query" verbose example response — the data for this is already in `standings_thresholds.json → repair_strategies` and `epic_arcs.json` | **CONSOLIDATE** | ~200 tokens |
| `SKILL.md` | 428-441 | "Agent Search Limits" section — duplicates CLAUDE.md §External Data Queries ("Always use `limit=100`") | **REMOVE** (pattern B) | ~80 tokens |
| `SKILL.md` | 474-487 | "Notes" section — restates facts already in reference files (epic arcs no derived loss, COSMOS one-time, L5 lowsec) | **REMOVE** (pattern G) | ~60 tokens |
| `SKILL.md` | 443-463 | "ESI Query Pattern" — CLI invocation example + JSON response format. The CLI command is already shown at line 93. JSON structure is implementation detail. | **CONSOLIDATE** (pattern G) | ~120 tokens |

**Total estimated savings:** ~1,600 tokens (~41%)

## 4. Specific Findings

### High Severity

**H1. Pattern A: Massive inlining of reference data** (lines 282-416)
The skill declares `standings_thresholds.json` and `epic_arcs.json` as `data_sources` but then inlines their content across 135 lines covering: derived standing formulas, Connections level table, standing thresholds, standing gain estimates, time estimates, accelerator strategies, cross-faction implications, and L5 agents. This defeats the purpose of having reference files.
**Action:** REMOVE all inlined reference data (lines 282-416). Replace with imperative references:
- "Read `standings_thresholds.json → derived_standings_formula` to calculate effective standings."
- "Read `standings_thresholds.json → agent_levels` for access thresholds."
- "Read `epic_arcs.json` for arc details and repair strategy data."

**H2. "Epic arcs avoid derived losses" stated 4 times** (lines 366, 399, 403, 484)
The same fact appears in: the Accelerator Strategies section, the Cross-Faction Implications section, the Standing Repair example, and the Notes section. All four are also in the reference files.
**Action:** REMOVE all instances. The reference file already contains this fact.

### Medium Severity

**M1. Pattern B: Agent Search Limits** (lines 428-441)
CLAUDE.md §External Data Queries already contains "Always use `limit=100`" with the same rationale. Repeating it here is pure duplication.
**Action:** REMOVE.

**M2. Verbose example responses** (lines 98-148, 198-279)
Four full example responses (Overview, Agent Access, Research Agent, Standing Plan, Standing Repair) consume ~700 tokens. The format pattern is clear after one example.
**Action:** Keep the Overview example (lines 98-120) as the primary template. Replace others with 2-3 line format hints showing key differences (e.g., "Agent Access includes effective standing calculation; Standing Plan includes progression phases").

**M3. Time Estimates section is ungrounded** (lines 330-341)
"Phase 1: Neutral to L2 (1.0): ~10-15 missions, 2-3 hours" — these estimates don't come from any reference file. They're training-data approximations presented as facts.
**Action:** REMOVE. If estimates are needed, add them to the reference file as verified data.

### Low Severity

**L1. Pattern G: Notes section restates reference file content** (lines 474-487)
Seven bullet points that are all already in the reference JSON files.
**Action:** REMOVE entirely.

**L2. Duplicate ESI query pattern** (lines 443-463)
The CLI command `uv run aria-esi standings` already appears at line 93. The JSON response format (lines 456-463) is implementation detail that doesn't improve steering.
**Action:** CONSOLIDATE. Remove the JSON format example, keep only the CLI command reference at line 93.

## 5. Prioritized Recommendations

1. **REMOVE** inlined reference data blocks (lines 282-416) — pattern A, ~710 tokens. Replace with imperative one-line references to data_sources files. This is the highest-impact change. *(remove)*
2. **REMOVE** Agent Search Limits section (lines 428-441) — pattern B, duplicates CLAUDE.md. *(remove)*
3. **CONSOLIDATE** verbose example responses (lines 98-279) — keep one template, summarize format variations for others. ~400 token savings. *(modify)*
4. **REMOVE** Notes section (lines 474-487) — pattern G, all facts are in reference files. *(remove)*
5. **REMOVE** Time Estimates section (lines 330-341) — ungrounded training-data estimates. *(remove)*
6. **CONSOLIDATE** ESI Query Pattern section (lines 443-463) — remove duplicate CLI reference and JSON format. *(modify)*
7. **ADD** imperative reference lines directing Claude to read `standings_thresholds.json` and `epic_arcs.json` for specific data needs (thresholds, formulas, repair strategies, epic arc details). *(add)*
