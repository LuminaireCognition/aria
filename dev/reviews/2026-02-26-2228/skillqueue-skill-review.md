# Skill Review: skillqueue

**Path:** `.claude/skills/skillqueue/SKILL.md`
**Review timestamp:** 2026-02-26-2228
**Size:** 303 lines, ~2,752 tokens

## 1. Executive Summary

The skillqueue skill is a straightforward ESI-backed queue viewer with no MCP dependencies, but it carries significant dead weight from pattern (B) duplication of CLAUDE.md behaviors (ESI read-only limitations, ESI availability checks) and pattern (G) redundant response format variants. Roughly 40% of the file is boilerplate or verbose examples that could be cut without degrading output quality.

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| Data-first enforcement | 🟢 | All data comes from `uv run aria-esi skillqueue`. No MCP tools involved. No path to hallucinate data. |
| Prompt hygiene | 🟢 | Clear imperative: run CLI, parse JSON, render. No ambiguity about data source. |
| Failure handling | 🟢 | Covers ESI unavailable, missing scope, empty queue — all with concrete fallback responses. |
| Context window efficiency | 🔴 | ~40% of tokens spent on duplicated CLAUDE.md behaviors, verbose response templates, and a Python progress bar snippet that Claude doesn't execute. |

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 20-33 | "CRITICAL: Read-Only Limitation" section — restates CLAUDE.md §ESI Capability Boundaries verbatim | **REMOVE** (pattern B) | ~120 tokens |
| `SKILL.md` | 35-44 | "CRITICAL: Data Volatility" section — restates CLAUDE.md §Data Volatility. The CLI already includes `volatility` field in JSON output. | **REMOVE** (pattern B) | ~80 tokens |
| `SKILL.md` | 46-56 | "ESI Requirement" section — scope name is already in frontmatter `esi_scopes`; setup instructions duplicate other skills | **REMOVE** (pattern B) | ~80 tokens |
| `SKILL.md` | 58-81 | "ESI Availability Check" section — identical boilerplate found in 18+ skills. System-level concern, not skill-specific. | **REMOVE** (pattern B) | ~180 tokens |
| `SKILL.md` | 91-145 | Full JSON response structure examples (active queue + empty queue) — verbose example data. One compact example would suffice. | **CONSOLIDATE** | ~200 tokens |
| `SKILL.md` | 172-199 | "Formatted version (rp_level: moderate or full)" — 28-line ASCII box response template. The plain markdown table already steers correctly; persona overlay can add flavor. | **REMOVE** | ~200 tokens |
| `SKILL.md` | 201-218 | "Empty Queue Warning" — another ASCII box variant. The plain version at L209 already covers this. | **REMOVE** (pattern G) | ~100 tokens |
| `SKILL.md` | 232-248 | "Error Handling: ESI Not Configured" — ASCII box error message; already covered by the ESI Availability Check block above | **REMOVE** (pattern G) | ~100 tokens |
| `SKILL.md` | 250-263 | "Error Handling: Missing Scope" — ASCII box for missing scope; duplicates the ESI Requirement section | **REMOVE** (pattern G) | ~80 tokens |
| `SKILL.md` | 286-295 | "Progress Bar Generation" — Python function Claude doesn't execute; the example in the formatted template already shows the visual pattern | **REMOVE** | ~60 tokens |

**Total estimated savings:** ~1,200 tokens (~44%)

## 4. Specific Findings

### High Severity

**H1. Pattern B: ESI read-only limitation duplicates CLAUDE.md** (lines 20-33)
CLAUDE.md §ESI Capability Boundaries already states "ESI is read-only" with an identical can/cannot table. The skill restates "ARIA CANNOT: Add or remove skills from the queue, Pause or restart training, Inject skill points or extractors, Interact with the EVE client." This is pure duplication.
**Action:** REMOVE the entire section. Replace with a single line: "When asked to modify the queue, explain ESI is read-only and provide in-game steps (Alt+A)."

**H2. Pattern B: ESI Availability Check boilerplate** (lines 58-81)
This 24-line block is copy-pasted across 18+ skills. It checks session hook output for ESI status. This is a system-level concern that should live in a shared protocol file or CLAUDE.md.
**Action:** REMOVE. Extract to `reference/protocols/esi-availability-check.md` if not already done, or rely on the session hook already providing this context.

### Medium Severity

**M1. Pattern G: Redundant response format variants** (lines 149-263)
The skill provides four separate response templates: standard (plain), formatted (RP), compact, and empty queue — each in full. The standard table format (lines 149-172) is sufficient to steer Claude. RP formatting can be left to persona overlays. The compact and empty variants are minor variations that Claude can derive.
**Action:** Keep the standard format (lines 149-172) and compact format (lines 220-229). REMOVE the formatted RP box (lines 172-199) and the duplicate empty queue/error ASCII boxes (lines 201-263).

**M2. Verbose JSON examples** (lines 91-145)
Two full JSON response examples (active queue, empty queue) consume ~200 tokens. The active queue example alone would suffice — the empty case is trivially derivable (`queue_status: "empty"`, `skills: []`).
**Action:** CONSOLIDATE to one example. Remove the empty queue JSON example.

### Low Severity

**L1. Progress bar Python function** (lines 286-295)
A Python code block for rendering a progress bar. Claude doesn't execute Python for rendering — it generates text directly. The formatted template (line 183) already shows the visual pattern `[████████░░░░░░░░░░░░]`.
**Action:** REMOVE the Python block.

**L2. Data Volatility section restates CLAUDE.md** (lines 35-44)
CLAUDE.md §Data Volatility already covers volatile data handling. The four bullet points here restate the same policy.
**Action:** REMOVE. Add one line: "Skill queue data is volatile — always display query timestamp and staleness warning."

## 5. Prioritized Recommendations

1. **REMOVE** ESI Availability Check boilerplate (lines 58-81) — pattern B, 180 tokens. This is the most impactful single cut and should be extracted to a shared protocol. *(remove)*
2. **REMOVE** ESI read-only limitation section (lines 20-33) — pattern B, 120 tokens. Replace with one-line directive. *(modify)*
3. **REMOVE** RP-formatted ASCII box templates (lines 172-218) and error ASCII boxes (lines 232-263) — pattern G, 480 tokens. Keep standard table format only. *(remove)*
4. **CONSOLIDATE** JSON response examples (lines 91-145) — keep only the active queue example. *(modify)*
5. **REMOVE** Data Volatility section (lines 35-44) — pattern B, condense to one line. *(modify)*
6. **REMOVE** Progress bar Python function (lines 286-295). *(remove)*
7. **REMOVE** ESI Requirement section (lines 46-56) — scope is in frontmatter. *(remove)*
