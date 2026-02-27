# Skill Review: wallet-journal

**Path:** `.claude/skills/wallet-journal/SKILL.md`
**Review timestamp:** 2026-02-26-2228
**Size:** 294 lines, ~2,690 tokens

## 1. Executive Summary

The wallet-journal skill is a clean ESI-backed financial report with no MCP dependencies. Its main weakness is pattern B duplication: the ESI Availability Check boilerplate (identical to 18 other skills) and the Ref Type Reference table at the end (lines 276-294) which is static ESI metadata that should be in a reference file. The skill is moderately sized and reasonably efficient, but ~25% of tokens can be reclaimed through boilerplate removal and response template consolidation.

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| Data-first enforcement | 🟢 | All data comes from `uv run aria-esi wallet-journal`. No MCP tools involved. Clear CLI invocation pattern. |
| Prompt hygiene | 🟢 | Clean imperative flow: run CLI with arguments, parse JSON, render format. No ambiguity. |
| Failure handling | 🟢 | ESI unavailable, not configured, and empty period cases all handled with concrete responses. |
| Context window efficiency | 🟡 | Pattern B boilerplate (~180 tokens), verbose RP-formatted response template (~200 tokens), and Ref Type Reference table (~120 tokens) add up. Not as bloated as other skills but still has clear cuts. |

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 31-54 | "ESI Availability Check" section — identical boilerplate across 18+ skills | **REMOVE** (pattern B) | ~180 tokens |
| `SKILL.md` | 56-62 | "ESI Endpoints Used" table — implementation detail; the scope is in frontmatter and the CLI abstracts the endpoints | **REMOVE** | ~50 tokens |
| `SKILL.md` | 170-198 | "Formatted Version (rp_level: moderate or full)" — ASCII box response template. Plain markdown format (lines 136-169) is sufficient. Persona overlays handle RP flavor. | **REMOVE** (pattern G) | ~200 tokens |
| `SKILL.md` | 210-224 | "Error Handling: ESI Not Configured" — ASCII box error response. Already covered by ESI Availability Check. | **REMOVE** (pattern G) | ~80 tokens |
| `SKILL.md` | 276-294 | "Ref Type Reference" table — 19-line static ESI metadata table. This is reference data that doesn't change. | **REMOVE** (pattern A) — move to a reference file if needed | ~120 tokens |
| `SKILL.md` | 22-29 | "CRITICAL: Data Volatility" section — restates CLAUDE.md §Data Volatility policy | **REMOVE** (pattern B) | ~60 tokens |
| `SKILL.md` | 237-245 | "Self-Sufficiency Context" section — 9 lines about `market_trading: false` pilots. Profile-aware behavior is a CLAUDE.md system behavior. | **CONSOLIDATE** — reduce to one line | ~50 tokens |

**Total estimated savings:** ~740 tokens (~28%)

## 4. Specific Findings

### High Severity

**H1. Pattern B: ESI Availability Check boilerplate** (lines 31-54)
Identical 24-line block found in 18+ skills. This is a system-level concern.
**Action:** REMOVE. Same as all other skills — extract to shared protocol or rely on session hook.

### Medium Severity

**M1. Pattern G: RP-formatted ASCII box response** (lines 170-198)
A 29-line ASCII box variant of the standard markdown response. The standard format (lines 136-169) already shows the data structure. RP formatting is persona overlay territory.
**Action:** REMOVE the ASCII box variant.

**M2. Pattern A: Ref Type Reference table** (lines 276-294)
A 19-row table mapping ESI `ref_type` values to categories and descriptions. This is static ESI metadata. The CLI already categorizes transactions in its output (the `summary.income_breakdown` and `summary.expense_breakdown` fields handle this). Claude doesn't need a ref_type lookup table.
**Action:** REMOVE. If needed for edge cases, move to `reference/mechanics/esi_ref_types.json`.

**M3. Pattern B: Data Volatility section** (lines 22-29)
CLAUDE.md §Data Volatility already defines volatility tiers and handling rules. The "semi-stable" classification here is the only novel piece.
**Action:** REMOVE the section. The CLI response already includes a `volatility` field.

### Low Severity

**L1. ESI Endpoints Used table** (lines 56-62)
Lists the raw ESI endpoint paths and scopes. The CLI abstracts these. The scope is already in frontmatter `esi_scopes`.
**Action:** REMOVE. Implementation detail.

**L2. Error handling for ESI Not Configured** (lines 210-224)
An ASCII box error message that duplicates the ESI Availability Check handling.
**Action:** REMOVE.

**L3. Self-Sufficiency Context** (lines 237-245)
"For pilots with `market_trading: false`" — this profile-aware behavior is reasonable but verbose. The "Never suggest selling items" directive is the only actionable line.
**Action:** CONSOLIDATE to: "If profile has `market_trading: false`, never suggest selling items."

## 5. Prioritized Recommendations

1. **REMOVE** ESI Availability Check boilerplate (lines 31-54) — pattern B, 180 tokens. *(remove)*
2. **REMOVE** RP-formatted ASCII box response (lines 170-198) — pattern G, 200 tokens. *(remove)*
3. **REMOVE** Ref Type Reference table (lines 276-294) — pattern A, 120 tokens. Move to reference file if needed. *(remove)*
4. **REMOVE** Data Volatility section (lines 22-29) — pattern B, 60 tokens. *(remove)*
5. **REMOVE** ESI Endpoints Used table (lines 56-62) and ESI Not Configured error (lines 210-224) — implementation detail and duplication, 130 tokens. *(remove)*
6. **CONSOLIDATE** Self-Sufficiency Context (lines 237-245) to one directive line. *(modify)*
