# Skill Review: industry-jobs

**Skill Path:** `.claude/skills/industry-jobs/SKILL.md`
**Review Timestamp:** 2026-02-26-2228
**Files in skill directory:** `SKILL.md` (1 file, 333 lines)

---

## 1. Executive Summary

The industry-jobs skill is a CLI-backed ESI skill that is significantly bloated by verbose response format templates (3 RP variants plus compact, error, and no-jobs displays consuming ~60% of the file), inlined reference data for activity types, and an ESI availability check block that duplicates CLAUDE.md system behavior. The skill has no MCP integration despite the `pilot()` dispatcher potentially supporting industry data, and relies entirely on `uv run aria-esi industry-jobs` CLI calls.

---

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | N/A | CLI-only skill; no MCP dispatcher for industry jobs exists. Data comes from ESI via CLI. Acceptable. |
| Prompt hygiene | :yellow_circle: | Job data comes from ESI (good), but activity type table (lines 176-186) is inlined reference data that could go stale. |
| Failure handling | :green_circle: | ESI unavailable, missing scope, and empty results all have explicit handling paths. |
| Context window efficiency | :red_circle: | ~200 lines of response format templates (58% of file). Three RP-variant display blocks, two error blocks, and a JSON schema example consume massive tokens for what is a straightforward table display. |

---

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 20-33 | Read-only limitation block duplicating CLAUDE.md ESI Capability Boundaries table | **REMOVE** | ~120 tokens |
| `SKILL.md` | 35-43 | "Data Volatility" section -- justification prose (pattern D) explaining that jobs have fixed timers | **REMOVE** | ~80 tokens |
| `SKILL.md` | 45-56 | "ESI Requirement" section restating scope and auth setup -- already in frontmatter `esi_scopes` and CLAUDE.md handles missing scopes | **REMOVE** | ~100 tokens |
| `SKILL.md` | 58-83 | "ESI Availability Check" block -- duplicates CLAUDE.md system behavior (pattern B); session hook check is a system-level mechanism | **REMOVE** | ~200 tokens |
| `SKILL.md` | 101-157 | Full JSON response structure example with every field documented -- Claude can parse any JSON; a 2-line description of key fields suffices | **CONSOLIDATE** | ~400 tokens |
| `SKILL.md` | 160-174 | Empty jobs response JSON example -- redundant with the full response example above | **REMOVE** | ~100 tokens |
| `SKILL.md` | 176-186 | Activity types reference table -- inlined reference data (pattern A) that should be a prerequisite file or part of the CLI output | **CONSOLIDATE** | ~100 tokens |
| `SKILL.md` | 210-237 | Formatted RP response template -- ASCII box art consuming 27 lines; a brief description of RP styling would suffice (pattern E) | **CONSOLIDATE** | ~250 tokens |
| `SKILL.md` | 239-253 | "No Jobs Display" RP variant -- another 14-line ASCII template | **REMOVE** | ~120 tokens |
| `SKILL.md` | 264-296 | Error handling blocks (ESI Not Configured + Missing Scope) -- two more ASCII box templates duplicating the error path already covered in lines 58-83 | **REMOVE** | ~250 tokens |
| `SKILL.md` | 309-316 | Cross-References table -- lists commands that don't need to be pre-loaded | **REMOVE** | ~60 tokens |
| `SKILL.md` | 318-323 | "Self-Sufficiency Context" section -- niche advisory that adds tokens for an edge case | **REMOVE** | ~50 tokens |

**Total estimated savings: ~1,830 tokens (~55% of file)**

---

## 4. Specific Findings

### High Severity

**H1. Massive response template bloat (lines 188-296)**
The file devotes 108 lines to 5 different response format templates: standard display, RP formatted, no-jobs display, ESI-not-configured error, and missing-scope error. Each uses ASCII box art (pattern E). A single compact template with a note about RP styling would steer just as well. This is the single largest token waste in the file.

**H2. ESI availability check duplicates CLAUDE.md (lines 58-83, pattern B)**
The "ESI Availability Check (CRITICAL)" section restates the session hook check mechanism that CLAUDE.md already defines. Every ESI-backed skill loads this same boilerplate. It should be removed entirely; the system-level mechanism handles this.

### Medium Severity

**M1. Full JSON schema example is unnecessary (lines 101-157)**
Claude can parse arbitrary JSON. Providing a 56-line example of every possible field in the response is over-documentation. Replace with a 3-line note about key fields: `status` (active/ready), `time_remaining`, `progress_percent`.

**M2. Read-only limitation block restates CLAUDE.md (lines 20-33, pattern B)**
The "CRITICAL: Read-Only Limitation" section restates the ESI Capability Boundaries table from CLAUDE.md. The frontmatter already signals this is read-only. A single line "Remind the pilot that job delivery requires in-game action (Industry window, Alt+S)" would be sufficient.

**M3. Inlined activity type table (lines 176-186, pattern A)**
The activity ID-to-name mapping is static game data. If needed at all, it should be in a prerequisite file or embedded in CLI output. Claude doesn't need to memorize activity IDs.

### Low Severity

**L1. Data volatility justification (lines 35-43, pattern D)**
The "Data Volatility" section explains *why* job data is semi-stable. Claude needs the instruction ("display query timestamp"), not the justification.

**L2. Cross-references and self-sufficiency sections (lines 309-323)**
These are low-value sections that could be removed without degrading output quality.

---

## 5. Prioritized Recommendations

1. **Remove** ESI availability check block (lines 58-83) -- pattern B duplication, ~200 tokens. System-level.
2. **Remove** all ASCII box error templates (lines 264-296) -- replace with 2-line error descriptions.
3. **Consolidate** response format section (lines 188-263) into one compact template plus a brief RP styling note. Target: ~15 lines total instead of ~75.
4. **Consolidate** JSON response example (lines 101-174) into a 5-line field summary.
5. **Remove** read-only limitation block (lines 20-33) -- replace with single line about in-game delivery.
6. **Remove** data volatility section (lines 35-43) and ESI requirement section (lines 45-56).
7. **Remove** activity type table (lines 176-186) or move to a data file.
8. **Remove** cross-references and self-sufficiency sections (lines 309-323).
