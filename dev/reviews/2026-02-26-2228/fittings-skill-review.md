# Skill Review: fittings

**Skill path:** `.claude/skills/fittings/SKILL.md`
**Review timestamp:** 2026-02-26-2228
**File stats:** 315 lines, ~2,450 tokens

## 1. Executive Summary

The fittings skill is a straightforward ESI data browser that does not use MCP tools at all — it shells out to `aria-esi` CLI commands. Its primary problem is extreme verbosity: three full JSON response examples (lines 98-179), a slot flag mapping table (lines 181-196) that duplicates ESI documentation, two complete response format variants (lines 198-258), and multiple error handling blocks (lines 260-291) consume roughly half the file for a skill that amounts to "run a CLI command and format the output." The skill should be cut by at least 50%.

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | :yellow_circle: | No MCP tools used. Data comes from `aria-esi` CLI (lines 79-82). This is a valid fallback pattern, but the skill doesn't attempt MCP first. The ESI fittings endpoint could potentially be accessed via MCP pilot tools. |
| Prompt hygiene | :green_circle: | Clear that all data comes from ESI queries. No risk of hallucination since it's displaying returned data verbatim. |
| Failure handling | :green_circle: | Lines 49-74 define ESI unavailable behavior with a concrete response template. Lines 260-291 cover missing scope and no-auth cases. |
| Context window efficiency | :red_circle: | Three JSON response examples (~80 lines), two full response format variants (~60 lines), slot flag mapping table, and verbose error templates consume ~1,200 tokens for a simple data-display skill. |

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 98-128 | Full JSON response structure for `fittings` list — Claude sees the actual CLI output at runtime | REMOVE | ~200 tokens |
| `SKILL.md` | 130-163 | Full JSON response structure for `fittings-detail` — same reason | REMOVE | ~200 tokens |
| `SKILL.md` | 165-179 | Empty response JSON example — trivial case, not needed | REMOVE | ~80 tokens |
| `SKILL.md` | 181-196 | "Slot Flag Mapping" table — implementation detail of ESI flag parsing that the CLI handles; Claude never needs to map HiSlot0-7 | REMOVE | ~100 tokens |
| `SKILL.md` | 218-258 | Formatted RP response version and EFT export example — the standard display (lines 199-214) suffices; RP formatting is persona overlay territory | REMOVE | ~250 tokens |
| `SKILL.md` | 260-291 | Two verbose error-handling blocks with box-formatted templates — consolidate to a 3-line error table | CONSOLIDATE | ~150 tokens |
| `SKILL.md` | 22-27 | "ESI Write Capability" section — documents unimplemented write operations; pure noise | REMOVE | ~60 tokens |
| `SKILL.md` | 29-36 | "CRITICAL: Data Volatility" section — states fittings are stable; this is a one-liner, not a 7-line section with numbered list | CONSOLIDATE | ~40 tokens |
| `SKILL.md` | 37-47 | "ESI Requirement" section with setup instructions — duplicates the error handling blocks at lines 260-291 | REMOVE | ~60 tokens |
| `SKILL.md` | 293-308 | "Contextual Suggestions" and "Cross-References" tables — low-value filler | REMOVE | ~60 tokens |

**Total estimated savings:** ~1,200 tokens (~49%)

## 4. Specific Findings

### High Severity

**H1. Three complete JSON response examples serve no steering purpose (Pattern A)**
- **File:** `SKILL.md`, lines 98-179
- The CLI returns JSON that Claude formats for the user. Claude will see the actual response at runtime. Documenting the full response shape in the skill file is ~480 tokens of pure waste — Claude doesn't need to know the schema in advance to format it.
- **Action:** REMOVE all three JSON blocks. Replace with a 2-line note: "CLI returns JSON with fitting list/details. Format per response template below."

**H2. Slot Flag Mapping table is an implementation detail (dead weight)**
- **File:** `SKILL.md`, lines 181-196
- The `aria-esi` CLI handles ESI flag-to-slot mapping internally. Claude never needs to interpret raw flag values. This is internal documentation leaked into a prompt.
- **Action:** REMOVE entirely.

**H3. Duplicate RP response format (Pattern G)**
- **File:** `SKILL.md`, lines 218-258
- Two complete response format blocks (plain at 199-214, RP at 218-238, EFT at 240-258). The plain format is sufficient; persona overlays handle RP styling. The EFT format is returned by the CLI itself — Claude just passes it through.
- **Action:** REMOVE the RP format block (lines 218-238) and EFT example (lines 240-258). Keep only the standard display.

### Medium Severity

**M1. "ESI Write Capability" documents unimplemented features (Pattern D)**
- **File:** `SKILL.md`, lines 22-27
- Documents POST/DELETE operations explicitly marked as "not implemented." This wastes tokens on functionality that doesn't exist. It could even confuse Claude into thinking writes are possible.
- **Action:** REMOVE entirely.

**M2. ESI requirement section duplicates error handling**
- **File:** `SKILL.md`, lines 37-47
- Setup instructions for the scope appear here AND in the error block at lines 278-291. The error block is where Claude actually needs them (when it encounters the error).
- **Action:** REMOVE lines 37-47. Keep the error handling version.

**M3. Verbose error templates could be a simple table**
- **File:** `SKILL.md`, lines 260-291
- Two box-formatted error blocks (11 lines each) for "ESI Not Configured" and "Missing Scope." These are structurally identical and could be a 3-row table.
- **Action:** CONSOLIDATE into a table: `| Condition | Message | Setup Link |`

### Low Severity

**L1. "Data Volatility" section is over-documented**
- **File:** `SKILL.md`, lines 29-36
- States that fittings are "stable" data. This is a one-line fact inflated to 7 lines with a numbered list.
- **Action:** CONSOLIDATE to a single line in the behavior notes.

**L2. Cross-references and contextual suggestions are filler**
- **File:** `SKILL.md`, lines 293-308
- Generic command cross-references that Claude handles naturally.
- **Action:** REMOVE.

## 5. Prioritized Recommendations

1. **REMOVE** all three JSON response examples (lines 98-179) — Claude sees actual responses at runtime. [remove]
2. **REMOVE** slot flag mapping table (lines 181-196) — CLI implementation detail. [remove]
3. **REMOVE** RP response format and EFT example (lines 218-258) — duplicate of standard format; RP is overlay territory. [remove]
4. **REMOVE** "ESI Write Capability" section (lines 22-27) — documents non-existent features. [remove]
5. **REMOVE** ESI requirement section (lines 37-47) — duplicates error handling. [remove]
6. **CONSOLIDATE** error handling blocks (lines 260-291) into a compact table. [modify]
7. **CONSOLIDATE** data volatility (lines 29-36) to a single line. [modify]
8. **REMOVE** cross-references and contextual suggestions (lines 293-308). [remove]
