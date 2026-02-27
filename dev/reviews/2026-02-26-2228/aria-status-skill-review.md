# Skill Review: aria-status

**Skill path:** `.claude/skills/aria-status/SKILL.md`
**Review timestamp:** 2026-02-26-2228
**File stats:** 139 lines, ~1,340 tokens

## 1. Executive Summary

The aria-status skill is compact and well-focused on its core purpose: presenting a stable-data operational summary from pilot profile and operations files. It correctly avoids volatile data and explicitly defers to `/esi-query` for live telemetry. The primary issues are a duplicated response template (the "Example Output" section repeats the "Response Format" section nearly verbatim), and the ASCII-box formatting that could be simplified. At 139 lines this is already a lean skill; estimated savings are modest (~20%).

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| Data-first enforcement | 🟢 | Lines 25-29 run `aria-esi sync-profile` before generating. Data sources declared in frontmatter. Volatility table (lines 36-51) explicitly gates what can and cannot be included. |
| Prompt hygiene | 🟢 | Clear separation of stable vs. volatile data. Lines 47-51 "DO NOT Include" table is unambiguous. |
| Failure handling | 🟡 | Lines 28-29 handle sync failure gracefully ("continue with existing data and note sync status"). However, no handling for missing profile or operations files. |
| Context window efficiency | 🟡 | Duplicate response template (Pattern G) and ASCII-box formatting (Pattern E) waste ~100 tokens in an otherwise lean file. |

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 94-119 | "Example Output" section — near-verbatim duplicate of "Response Format" (lines 52-78) with filled-in example data | **REMOVE** — Pattern G. The format template on lines 52-78 already shows structure; the example adds ~25 lines of token cost for minimal additional steering. | ~200 tokens |
| `SKILL.md` | 52-78 | ASCII-box response format with ═ and ─ characters | **CONSOLIDATE** — convert to markdown section template (Pattern E). Keep the field names and structure, drop the box drawing. | ~50 tokens |
| `SKILL.md` | 80-91 | "Data Sources" section — restates what frontmatter `data_sources` already declares | **REMOVE** — the frontmatter lists `profile.md`, `operations.md`, `ships.md`, `missions.md`. Lines 80-91 restate this with labels like "Primary (Always Safe)" and "Secondary". The skill loading mechanism already reads data_sources. | ~80 tokens |
| `SKILL.md` | 126-127 | "Maintain ARIA persona throughout" — duplicates persona loading from CLAUDE.md | **REMOVE** — Pattern B. Persona is loaded at session init. | ~10 tokens |

**Total estimated savings: ~340 tokens (~25% of skill)**

## 4. Specific Findings

### High Severity

**H1. Duplicate response template (Pattern G)**
- **File:** `SKILL.md`, lines 94-119 ("Example Output") vs. lines 52-78 ("Response Format")
- **Issue:** The "Example Output" section is a filled-in version of the "Response Format" template. Both use the same ASCII-box structure, same section headers (CAPSULEER, HOME BASE, SHIP ROSTER, STANDINGS, OBJECTIVES). The example adds concrete values ("Federation Navy Suwayyah", "Masalle", "Imicus") but these come from the pilot profile at runtime — the example doesn't add steering value.
- **Action:** **REMOVE** lines 94-119 entirely. The format template is sufficient.

### Medium Severity

**M1. Data Sources section duplicates frontmatter**
- **File:** `SKILL.md`, lines 80-91
- **Issue:** Restates the data sources already declared in the frontmatter `data_sources` array (lines 14-18). The "Primary (Always Safe)" / "Secondary" / "Never Read" categorization adds some value but the "Never Read" items (current location, volatile ESI) are already covered by the volatility table on lines 47-51.
- **Action:** **REMOVE** lines 80-91. The volatility table (lines 36-51) already covers what to include/exclude, and the frontmatter declares the files.

**M2. No handling for missing profile or operations files**
- **File:** `SKILL.md` (entire file)
- **Issue:** The skill assumes profile.md and operations.md exist and are populated. If a pilot hasn't completed setup (first-run state), the skill has no fallback.
- **Action:** **Add** a single line: "If profile or operations data is missing, suggest `/setup` and present only available data."

### Low Severity

**L1. ASCII-box formatting (Pattern E)**
- **File:** `SKILL.md`, lines 52-78
- **Issue:** Uses ═ and ─ box-drawing characters. These cost more tokens than markdown headers and are fragile in rendering.
- **Action:** **CONSOLIDATE** to markdown section headers. Note: this skill has `has_persona_overlay: true`, so the persona overlay may override formatting anyway.

**L2. "Maintain ARIA persona throughout" (Pattern B)**
- **File:** `SKILL.md`, line 126
- **Issue:** One-liner that restates system-level persona behavior.
- **Action:** **REMOVE** — persona is handled by session init and overlay loading.

## 5. Prioritized Recommendations

1. **REMOVE** duplicate "Example Output" section (lines 94-119) — pure token waste. (Pattern G)
2. **REMOVE** "Data Sources" section (lines 80-91) — duplicates frontmatter and volatility table.
3. **Add** missing-profile fallback instruction.
4. **CONSOLIDATE** ASCII-box format template (lines 52-78) to markdown sections. (Pattern E)
5. **REMOVE** "Maintain ARIA persona throughout" on line 126. (Pattern B)
