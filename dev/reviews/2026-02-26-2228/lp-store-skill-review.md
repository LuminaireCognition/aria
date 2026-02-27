# Skill Review: lp-store

**Path:** `.claude/skills/lp-store/SKILL.md`
**Timestamp:** 2026-02-26-2228
**File:** 314 lines, ~3,270 tokens

## 1. Executive Summary

The lp-store skill has strong MCP-first enforcement with explicit hallucination guards but suffers from significant bloat: verbose ASCII-box response templates (3 variants, ~65 lines), a redundant Field-to-Source mapping table that restates the Required Tool Calls table, and a full "Self-Sufficiency Context" section that duplicates pilot profile awareness. Approximately 40% of the file could be cut without degrading steering quality.

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | 🟢 | Lines 72-84: Explicit "Required Tool Calls (MANDATORY)" table with hallucination guard. CLI calls are the only data path. |
| Prompt hygiene | 🟢 | Lines 86-96: Field-to-Source mapping makes every output field traceable. Anti-patterns section (lines 276-284) reinforces with concrete wrong/right examples. |
| Failure handling | 🟢 | Lines 236-268: Three distinct error states (no LP, corp not found, no LP store) with user-actionable guidance. ESI availability check at lines 286-314. |
| Context window efficiency | 🔴 | Three full ASCII-box response templates (~65 lines), duplicate sourcing tables, self-sufficiency prose, and experience-adaptation examples all consume tokens without proportional value. |

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 86-96 | Field-to-Source Mapping table | **REMOVE** — duplicates lines 72-84 Required Tool Calls table with identical information in a different layout | ~120 tokens |
| `SKILL.md` | 99-165 | Three ASCII-box response templates (LP Balance, LP Store Browse, Self-Sufficiency Analysis) | **CONSOLIDATE** — reduce to one compact template with inline notes for variants | ~350 tokens |
| `SKILL.md` | 167-190 | "Self-Sufficiency Context" section with "Offer Types by Accessibility" table and "Recommended Workflow" | **REMOVE** — pilot profile already captures `market_trading: false`; the accessibility table is static game knowledge that doesn't improve steering | ~200 tokens |
| `SKILL.md` | 200-233 | "Experience-Based Adaptation" section with three verbatim example blocks (new/intermediate/veteran) | **CONSOLIDATE** — replace with a 3-line summary: "new: explain LP concept; intermediate: show offers directly; veteran: terse summary" | ~250 tokens |
| `SKILL.md` | 57-70 | Corporation Shortcuts table | **CONSOLIDATE** — the CLI already handles fuzzy matching; reduce to a note saying "Common shortcuts like 'fed navy' are supported" | ~100 tokens |
| `SKILL.md` | 192-198 | "Intelligence Framing" behavior note | **REMOVE** — persona overlay responsibility, not skill behavior. Line 194 tells Claude to use "GalNet loyalty databases" framing which is persona territory. | ~30 tokens |
| `SKILL.md` | 270-273 | "Scopes Required" section | **REMOVE** — duplicates frontmatter `esi_scopes` field (line 14) | ~30 tokens |

**Total estimated savings: ~1,080 tokens (~33%)**

## 4. Specific Findings

### High Severity

**H1. Redundant sourcing tables (Pattern G)**
- **File:** `SKILL.md`, lines 72-96
- **Issue:** The "Required Tool Calls (MANDATORY)" table (lines 72-84) and the "Field -> Source Mapping" table (lines 86-96) convey identical information in different layouts. Both map output fields to CLI calls.
- **Action:** **REMOVE** lines 86-96. The Required Tool Calls table is more actionable.

**H2. Inlined static game data (Pattern A)**
- **File:** `SKILL.md`, lines 167-190
- **Issue:** "Self-Sufficiency Context" section inlines offer type accessibility rules ("LP + ISK only = YES", "LP + ISK + Tags = Maybe", etc.) and a recommended workflow. This is static game knowledge that doesn't change and is not sourced from any prerequisite file. It occupies ~24 lines to express what could be one sentence: "Highlight offers requiring only LP + ISK for self-sufficient pilots."
- **Action:** **REMOVE** section, replace with one-line behavior note.

### Medium Severity

**M1. Verbose response templates**
- **File:** `SKILL.md`, lines 99-165
- **Issue:** Three full ASCII-box templates consume ~65 lines. The LP Balance Report, LP Store Browse, and Self-Sufficiency Analysis templates are structurally identical (header, body, footer). Claude can infer the pattern from one example.
- **Action:** **CONSOLIDATE** to one template with variant notes.

**M2. Experience-based adaptation examples too verbose (Pattern D-adjacent)**
- **File:** `SKILL.md`, lines 200-233
- **Issue:** Three full response blocks (new/intermediate/veteran) spend ~34 lines demonstrating adaptation levels. A 3-line summary would steer identically.
- **Action:** **CONSOLIDATE** to terse description.

**M3. Corporation shortcuts table is CLI documentation, not skill behavior**
- **File:** `SKILL.md`, lines 57-70
- **Issue:** The CLI already handles fuzzy corp name matching. Listing 8 shortcuts with IDs in the skill prompt doesn't improve Claude's behavior — Claude passes the user's input to the CLI verbatim.
- **Action:** **CONSOLIDATE** to a one-line note that shortcuts exist.

### Low Severity

**L1. ESI scope duplication**
- **File:** `SKILL.md`, lines 270-273
- **Issue:** "Scopes Required" section restates what frontmatter line 14 already declares.
- **Action:** **REMOVE**.

**L2. Contextual Suggestions table is thin**
- **File:** `SKILL.md`, lines 225-234
- **Issue:** Four context/suggest pairs. Low token cost but marginal steering value since CLAUDE.md already instructs contextual command suggestions.
- **Action:** Keep (low token cost, provides skill-specific suggestions).

## 5. Prioritized Recommendations

1. **REMOVE** Field-to-Source Mapping table (lines 86-96) — pure duplication of Required Tool Calls table. (~120 tokens)
2. **REMOVE** Self-Sufficiency Context section (lines 167-190) — replace with one behavior note. (~200 tokens)
3. **CONSOLIDATE** three response templates (lines 99-165) into one with variant notes. (~350 tokens)
4. **CONSOLIDATE** Experience-Based Adaptation (lines 200-233) to 3-line summary. (~250 tokens)
5. **CONSOLIDATE** Corporation Shortcuts table (lines 57-70) to one-line note. (~100 tokens)
6. **REMOVE** Scopes Required section (lines 270-273). (~30 tokens)
7. **REMOVE** Intelligence Framing behavior note (line 194). (~30 tokens)
