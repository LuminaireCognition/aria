# Skill Review: gatecamp

**Skill path:** `.claude/skills/gatecamp/SKILL.md`
**Review timestamp:** 2026-02-26-2228
**File stats:** 294 lines, ~2,140 tokens

## 1. Executive Summary

The gatecamp skill has good MCP-first discipline with clear tool-call requirements (lines 43-53), but it carries a significant amount of static reference data that should either live in a prerequisite file or be removed entirely. The "Known Gatecamp Systems" table (lines 249-264), camp type identification table (lines 203-210), confidence level definitions (lines 212-219), and three verbose response format examples (lines 94-199) together consume roughly 40% of the file. Additionally, the "Persona Adaptation" section (lines 286-294) duplicates the persona overlay loading mechanism from CLAUDE.md.

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | :green_circle: | Lines 43-53 specify exact MCP calls: `universe(action="activity", include_realtime=True)` and `universe(action="gatecamp_risk")`. No ambiguity about data source. |
| Prompt hygiene | :yellow_circle: | Lines 249-264 inline "Known Gatecamp Systems" — static reference data that Claude could use instead of querying MCP for those systems. This undermines MCP-first by providing a fallback that doesn't require a tool call. |
| Failure handling | :green_circle: | Lines 176-199 define a complete "Degraded Mode" response for when real-time data is unavailable, with clear warning language. |
| Context window efficiency | :yellow_circle: | Four full response format examples (active camp, no camp, route analysis, degraded mode) consume ~105 lines. Camp type and confidence tables add ~20 lines of static reference. Watchlist integration section (lines 220-248) is verbose for what amounts to "flag watched entities." |

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 249-264 | "Known Gatecamp Systems" — inlined static reference data; risks Claude skipping MCP queries for these "known" systems | REMOVE | ~100 tokens |
| `SKILL.md` | 286-294 | "Persona Adaptation" section — duplicates CLAUDE.md skill loading mechanism (Pattern B); `has_persona_overlay: true` in frontmatter already handles this | REMOVE | ~60 tokens |
| `SKILL.md` | 125-143 | "No Camp Detected" response format — structurally identical to the active camp format with different field values; one format template with conditional notes suffices | CONSOLIDATE | ~80 tokens |
| `SKILL.md` | 176-199 | "Degraded Mode" response format — a full box template for what is essentially "show hourly aggregates with a warning banner" | CONSOLIDATE | ~100 tokens |
| `SKILL.md` | 55-91 | Full JSON response example for real-time data — Claude sees actual MCP responses at runtime; documenting the shape adds tokens without improving output | REMOVE | ~180 tokens |
| `SKILL.md` | 203-210 | "Camp Type Identification" table — static game knowledge that could be a prerequisite file if needed, but is also derivable from kill data patterns at runtime | REMOVE | ~60 tokens |
| `SKILL.md` | 212-219 | "Confidence Levels" table — implementation detail of the MCP `gatecamp_risk` tool; Claude doesn't set confidence levels, the tool does | REMOVE | ~50 tokens |
| `SKILL.md` | 220-248 | "Watchlist Integration" section — verbose for a feature that amounts to "cross-reference attackers with watchlist; flag matches" | CONSOLIDATE | ~150 tokens |
| `SKILL.md` | 276-283 | "Contextual Suggestions" table — generic cross-reference filler | REMOVE | ~40 tokens |

**Total estimated savings:** ~820 tokens (~38%)

## 4. Specific Findings

### High Severity

**H1. "Known Gatecamp Systems" is inlined static reference data (Pattern A)**
- **File:** `SKILL.md`, lines 249-264
- Lists specific systems (Uedama, Niarja, Tama, Rancer, etc.) with gate names and security statuses. This is precisely the kind of static reference data ADR-006 says should not be inlined. Worse, it provides a shortcut for Claude to skip MCP queries: "I know Tama is a gatecamp system" rather than checking live data.
- **Action:** REMOVE. If this data is valuable, extract to a reference file and declare as `data_sources`. But since the MCP `gatecamp_risk` tool handles detection based on live kills, this static list is of dubious value regardless.

**H2. Full JSON response structure duplicates runtime data (Pattern A)**
- **File:** `SKILL.md`, lines 55-91
- Documents the exact JSON shape of MCP real-time activity responses. Claude sees actual responses at runtime; pre-documenting the schema wastes ~180 tokens. The response format templates (lines 94-174) already show what fields to use.
- **Action:** REMOVE the JSON block. The response format templates implicitly define which fields matter.

### Medium Severity

**M1. "Persona Adaptation" duplicates CLAUDE.md skill loading (Pattern B)**
- **File:** `SKILL.md`, lines 286-294
- Restates the persona overlay loading mechanism. The frontmatter `has_persona_overlay: true` already triggers overlay loading via the CLAUDE.md skill loading system. This section is redundant.
- **Action:** REMOVE entirely.

**M2. Confidence Levels table documents MCP internals**
- **File:** `SKILL.md`, lines 212-219
- Defines HIGH/MEDIUM/LOW confidence criteria. But the `gatecamp_risk` MCP tool returns a `confidence` field — Claude doesn't compute this. Documenting the tool's internal logic is noise.
- **Action:** REMOVE. Claude should present the confidence level the tool returns, not re-derive it.

**M3. Camp Type Identification table is static game knowledge**
- **File:** `SKILL.md`, lines 203-210
- Maps camp types to indicators and countermeasures. The MCP tool returns `camp_type` in its response. The countermeasures are generic PvP advice.
- **Action:** REMOVE the indicators column (MCP provides camp_type). Keep countermeasures only if they add value — but these are generic enough that Claude knows them.

**M4. Watchlist Integration section is verbose**
- **File:** `SKILL.md`, lines 220-248
- 28 lines to say: "Cross-reference attackers against watchlists, flag matches with warning indicators." Includes a CLI command (`aria-esi redisq-watched`), example formatting, and a 3-step "when to show" list.
- **Action:** CONSOLIDATE to ~5 lines: the CLI command and a one-line formatting instruction.

### Low Severity

**L1. Four response format variants are excessive**
- **File:** `SKILL.md`, lines 94-199
- Active camp (lines 94-124), no camp (125-143), route analysis (145-174), degraded mode (176-199). The route and single-system formats share structure. One parameterized template would suffice.
- **Action:** CONSOLIDATE to one primary format with conditional sections noted inline.

**L2. "Contextual Suggestions" table is filler**
- **File:** `SKILL.md`, lines 276-283
- Generic cross-references handled naturally by Claude.
- **Action:** REMOVE.

## 5. Prioritized Recommendations

1. **REMOVE** "Known Gatecamp Systems" (lines 249-264) — inlined reference data that undermines MCP-first. [remove]
2. **REMOVE** JSON response structure (lines 55-91) — Claude sees actual responses at runtime. [remove]
3. **REMOVE** "Persona Adaptation" section (lines 286-294) — duplicates CLAUDE.md loading mechanism. [remove]
4. **REMOVE** "Confidence Levels" table (lines 212-219) — documents MCP tool internals. [remove]
5. **CONSOLIDATE** Watchlist Integration (lines 220-248) to ~5 lines. [modify]
6. **REMOVE** Camp Type Identification indicators (lines 203-210) — MCP returns camp_type. [remove]
7. **CONSOLIDATE** response format variants (lines 94-199) — merge into one parameterized template. [modify]
8. **REMOVE** "Contextual Suggestions" (lines 276-283). [remove]
