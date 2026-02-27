# Skill Review: fit-check

**Skill path:** `.claude/skills/fit-check/SKILL.md`
**Review timestamp:** 2026-02-26-2228
**File stats:** 370 lines, ~2,900 tokens

## 1. Executive Summary

The fit-check skill is well-structured with strong MCP-first discipline and comprehensive tool-call documentation, but it carries significant dead weight in the form of pseudo-code blocks, a full-page example output, and EFT format documentation that duplicates knowledge available via the fitting MCP tools. Approximately 40% of the file (lines 219-370) could be removed or consolidated without degrading output quality.

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | :green_circle: | Lines 34-41 enumerate every required tool call with purpose. Steps 2-6 each mandate a specific MCP call before producing output. |
| Prompt hygiene | :green_circle: | Clear separation between what comes from MCP (skill data, market prices, meta variants) and what Claude derives (training time sums, replacement counts). |
| Failure handling | :green_circle: | Lines 47-75 define a freshness gate with explicit degraded-mode behavior. Wallet failure handled separately (line 63-67). |
| Context window efficiency | :red_circle: | Pseudo-code blocks (lines 224-237, 265-273), verbose example output (lines 316-354), and EFT format spec (lines 82-97) collectively consume ~600 tokens for marginal steering value. |

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 82-97 | EFT format spec — the fitting MCP tools already parse EFT; Claude doesn't need a format reference | REMOVE | ~80 tokens |
| `SKILL.md` | 219-237 | "Skill Check Logic" section with Python pseudo-code (`can_use_module`, `flyability_pct`) — Claude doesn't execute this; the MCP tool does | REMOVE | ~120 tokens |
| `SKILL.md` | 259-273 | "Cost Analysis Logic" section with Python pseudo-code (`replacements` calculation, conditional logic) — trivial arithmetic Claude can derive from the prose instructions in Step 8 | REMOVE | ~100 tokens |
| `SKILL.md` | 299-313 | "Partial Flyability" section — duplicates intent already expressed in the response format template (lines 184-216) and Step 5 substitution flow | REMOVE | ~100 tokens |
| `SKILL.md` | 316-354 | Full example output block — the response format template at lines 184-216 already defines the structure; a worked example adds little steering | REMOVE | ~250 tokens |
| `SKILL.md` | 356-363 | "Integration with Other Skills" table — generic cross-reference suggestions are low-value filler | REMOVE | ~50 tokens |
| `SKILL.md` | 365-370 | "Behavior Notes" section — lines 366-367 duplicate the freshness gate (line 47-53), line 368 duplicates Step 6 default, line 369 is a tone instruction that belongs in persona overlays | CONSOLIDATE | ~50 tokens |
| `SKILL.md` | 103-124 | Steps 2-3 verbose return-value documentation — Claude doesn't need field-by-field docs for MCP responses; it sees the actual response at runtime | CONSOLIDATE | ~100 tokens |
| `SKILL.md` | 149-166 | Step 6 JSON example for valuation items list — one-line description sufficient | CONSOLIDATE | ~80 tokens |

**Total estimated savings:** ~930 tokens (~32%)

## 4. Specific Findings

### High Severity

**H1. Pseudo-code blocks provide no steering value (Pattern D/dead code)**
- **File:** `SKILL.md`, lines 224-237, 265-273
- Python functions `can_use_module()` and `flyability_pct` are never executed. The `fitting(action="check_requirements")` MCP tool performs this logic. The replacement cost arithmetic (lines 265-273) is trivially derivable from the prose in Step 8 (line 179).
- **Action:** REMOVE both sections entirely.

**H2. Full example output duplicates response format template (Pattern G)**
- **File:** `SKILL.md`, lines 316-354
- The response format at lines 184-216 already defines the exact structure. The example at lines 316-354 repeats the same layout with sample data. A 39-line example for a format already specified in 33 lines is pure duplication.
- **Action:** REMOVE the example output section.

### Medium Severity

**M1. EFT format spec is unnecessary context (Pattern A)**
- **File:** `SKILL.md`, lines 82-97
- The fitting MCP tools accept EFT strings and handle parsing. Claude does not need to know EFT slot syntax to pass strings through to `fitting(action="check_requirements")`.
- **Action:** REMOVE. Replace with a one-line note: "Accept EFT-format fit from user. If none provided, prompt for paste."

**M2. Verbose MCP return-value documentation**
- **File:** `SKILL.md`, lines 103-124 (Steps 2-3 returns), lines 149-166 (Step 6 JSON)
- Claude sees actual MCP responses at runtime. Documenting every field in the skill file adds ~180 tokens of marginal value.
- **Action:** CONSOLIDATE to one-line descriptions per step: "Call X. Use the returned fields to..."

**M3. "Partial Flyability" section duplicates existing flow**
- **File:** `SKILL.md`, lines 299-313
- The substitution flow (Step 5, lines 139-148) and response format (lines 184-216) already cover partial flyability. This section restates the same concept with a redundant example.
- **Action:** REMOVE.

### Low Severity

**L1. "Integration with Other Skills" is generic filler**
- **File:** `SKILL.md`, lines 356-363
- Cross-skill suggestions are contextual and don't need a lookup table. Claude naturally suggests related commands. CLAUDE.md's command suggestion protocol already covers this.
- **Action:** REMOVE.

**L2. "Behavior Notes" partially duplicates earlier sections**
- **File:** `SKILL.md`, lines 365-370
- "Always query live ESI data" restates the freshness gate. "Default to Jita prices" restates Step 6. These are redundant echoes.
- **Action:** CONSOLIDATE unique items (lines 369-370 on tone) into a single line near the response format, remove the rest.

## 5. Prioritized Recommendations

1. **REMOVE** pseudo-code blocks (lines 219-237, 265-273) — they duplicate MCP tool logic and waste ~220 tokens. [remove]
2. **REMOVE** example output block (lines 316-354) — duplicates the response format template. [remove]
3. **REMOVE** EFT format spec (lines 82-97) — MCP handles parsing. [remove]
4. **CONSOLIDATE** MCP return-value docs (lines 103-124, 149-166) into terse one-liners. [modify]
5. **REMOVE** "Partial Flyability" section (lines 299-313) — covered by existing flow. [remove]
6. **REMOVE** "Integration with Other Skills" table (lines 356-363). [remove]
7. **CONSOLIDATE** "Behavior Notes" (lines 365-370) — merge unique items into response format section, delete duplicates. [modify]
