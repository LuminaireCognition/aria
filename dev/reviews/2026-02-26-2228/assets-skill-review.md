# Skill Review: assets

**Skill path:** `.claude/skills/assets/SKILL.md`
**Review timestamp:** 2026-02-26-2228
**File stats:** 513 lines, ~3,400 tokens

## 1. Executive Summary

The assets skill has the strongest hallucination guardrails of any skill reviewed in this batch — the mandatory tool call gate (lines 87-98), field-to-source mapping (lines 100-113), and anti-patterns section (lines 486-498) are exemplary grounding patterns. However, the skill is severely bloated at 513 lines due to six verbose response pattern examples (lines 115-246), a 90-line Smart Insights section (lines 355-449) that functions as a near-complete feature spec, and an ESI availability check (lines 20-43) that duplicates CLAUDE.md. Estimated 40% of tokens can be cut without degrading output quality.

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | 🟢 | Lines 87-98 are a model "Required Tool Calls (MANDATORY)" gate. Line 98 has an explicit hallucination guard. Field-to-source mapping (lines 100-113) traces every output field to a specific tool call. Best-in-class. |
| Prompt hygiene | 🟢 | Lines 486-498 provide concrete anti-patterns with wrong/right examples. No vague language. Every data point is sourced. |
| Failure handling | 🟢 | ESI unavailable (lines 20-43), missing data shows `[no data]` (line 102), error state presentation (line 96). |
| Context window efficiency | 🔴 | 6 response examples (lines 115-246) with fabricated data consume ~130 lines. Smart Insights section (lines 355-449) is a feature spec, not a skill instruction. ESI availability check (lines 20-43) duplicates CLAUDE.md. Total waste: ~250 lines. |

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 20-43 | "ESI Availability Check" section — duplicates CLAUDE.md session hook ESI check | **REMOVE** — Pattern B. Same section appears in agents-research; system-level behavior. | ~180 tokens |
| `SKILL.md` | 119-145 | "Basic Asset Overview" example — fabricated data (847 items, 12 stations, specific ship names) | **REMOVE** — response format template is sufficient. These fabricated numbers risk being echoed as real data. | ~180 tokens |
| `SKILL.md` | 149-184 | "Asset Valuation" example — fabricated prices and totals | **REMOVE** — the valuation implementation section (lines 248-275) already shows the flow. Fabricated ISK values in examples are dangerous. | ~200 tokens |
| `SKILL.md` | 188-204 | "Ships Only" example — fabricated ship names and item IDs | **REMOVE** — 3-line format instruction sufficient. | ~100 tokens |
| `SKILL.md` | 208-221 | "Filtered by Type" example — fabricated quantities | **REMOVE** | ~80 tokens |
| `SKILL.md` | 225-246 | "Filtered by Location" example — fabricated item counts | **REMOVE** | ~100 tokens |
| `SKILL.md` | 248-275 | "Valuation Implementation" pseudo-Python code block | **CONSOLIDATE** — replace with 3-step imperative: "1. Group ESI assets by type_id. 2. Build valuation request. 3. Call `market(action='valuation')`." The Python code is not executed. | ~100 tokens |
| `SKILL.md` | 355-449 | "Smart Insights" section — 95-line feature specification with response format, CLI command, detection rules, trade hub list, home system config | **CONSOLIDATE** — this reads like a feature spec/design doc, not a skill instruction. Reduce to: "With `--insights`, run `uv run aria-esi assets --insights` and present results. Detects forgotten assets (<5M ISK, non-hub), duplicate ships, consolidation opportunities." (~5 lines) | ~400 tokens |
| `SKILL.md` | 461-477 | "ESI Response Structure" — JSON schema for raw ESI assets response | **REMOVE** — the CLI command (`aria-esi assets`) handles ESI parsing. Claude doesn't need the raw ESI schema. | ~100 tokens |
| `SKILL.md` | 277-284 | "Structure/Citadel Handling" with "Future Enhancement" note | **CONSOLIDATE** — remove the "Future Enhancement" line (Pattern D rationale). Keep the 2-line explanation. | ~30 tokens |

**Total estimated savings: ~1,470 tokens (~43% of skill)**

## 4. Specific Findings

### High Severity

**H1. Six fabricated response examples risk data contamination**
- **File:** `SKILL.md`, lines 119-246
- **Issue:** Six response pattern examples contain fabricated data: "847" items, "12 stations", "Gila at Jita IV", "280,000,000 ISK", specific item IDs like "1234567890". These are dangerous because:
  1. Claude may echo fabricated numbers when ESI data is ambiguous
  2. The hallucination guard on line 98 says "NEVER fill in plausible-looking inventories" but the skill itself provides plausible-looking inventories as examples
  3. The fabricated data is indistinguishable from real data in format
- **Action:** **REMOVE** all six examples. Replace with a single structural template showing section headers and placeholder tokens like `{item_name}`, `{quantity}`, `{location}`. The field-to-source mapping table (lines 100-113) already defines what goes where.

**H2. Smart Insights section is a feature spec, not a skill instruction**
- **File:** `SKILL.md`, lines 355-449
- **Issue:** 95 lines including: detection rules for "forgotten assets" (< 5M ISK), duplicate ship logic, consolidation suggestion algorithm, a hardcoded trade hub reference list (lines 425-430), home system config JSON (lines 432-449), full response template with fabricated data. This is a design document embedded in a prompt. The CLI command `aria-esi assets --insights` presumably implements this logic — the skill just needs to present results.
- **Action:** **CONSOLIDATE** to ~5 lines: describe what `--insights` detects (forgotten assets, duplicate ships, consolidation opportunities) and instruct Claude to present CLI output. Remove the implementation details, trade hub list, and config JSON.

### Medium Severity

**M1. ESI Availability Check duplicates CLAUDE.md (Pattern B)**
- **File:** `SKILL.md`, lines 20-43
- **Issue:** Same pattern as agents-research: restates the ESI availability check from the session hook. System-level behavior.
- **Action:** **REMOVE** entirely.

**M2. ESI Response Structure is unnecessary for CLI-backed skill**
- **File:** `SKILL.md`, lines 461-477
- **Issue:** Documents the raw ESI JSON response structure (type_id, location_id, location_flag, etc.). The CLI command `aria-esi assets` handles ESI parsing and returns formatted output. Claude doesn't interact with raw ESI JSON.
- **Action:** **REMOVE** — the CLI abstracts this away. If location_flag values matter for presentation, keep a 2-line note about AssetSafety flagging.

**M3. Valuation Implementation uses pseudo-Python (Pattern E variant)**
- **File:** `SKILL.md`, lines 248-275
- **Issue:** A Python code block showing how to group assets and call the market dispatcher. Claude doesn't execute Python — this is prompt instruction dressed as code. The imperative sequence "group by type_id, build valuation request, call market dispatcher" conveys the same information in 3 lines.
- **Action:** **CONSOLIDATE** to 3 imperative steps.

### Low Severity

**L1. Hardcoded trade hub list in Smart Insights (Pattern A)**
- **File:** `SKILL.md`, lines 425-430
- **Issue:** Five hardcoded trade hub station names. If the trade hub list changes (unlikely but possible), this goes stale. More importantly, the CLI command should have this list internally.
- **Action:** **REMOVE** as part of Smart Insights consolidation.

**L2. "Future Enhancement" note (Pattern D)**
- **File:** `SKILL.md`, line 284
- **Issue:** "Future Enhancement: Cache resolved structure names." This is a development note, not a runtime instruction.
- **Action:** **REMOVE**.

**L3. Trend Tracking section is verbose but functional**
- **File:** `SKILL.md`, lines 286-353
- **Issue:** Snapshot/trends/history documentation with example responses. Verbose but these are distinct CLI subcommands that need disambiguation. The fabricated data in examples is lower-risk here (it's showing the format, not asset inventory).
- **Action:** Keep, but consider reducing the three example responses to a single combined format template.

## 5. Prioritized Recommendations

1. **REMOVE** all six fabricated response examples (lines 119-246) — highest contamination risk. Replace with a single structural template using placeholder tokens. (Pattern A)
2. **CONSOLIDATE** Smart Insights section (lines 355-449) from 95 lines to ~5 lines of instruction + CLI delegation. Remove embedded feature spec.
3. **REMOVE** ESI Availability Check (lines 20-43) — CLAUDE.md duplication. (Pattern B)
4. **REMOVE** ESI Response Structure (lines 461-477) — CLI abstracts raw ESI.
5. **CONSOLIDATE** Valuation Implementation (lines 248-275) to 3 imperative steps.
6. **REMOVE** "Future Enhancement" note on line 284. (Pattern D)
