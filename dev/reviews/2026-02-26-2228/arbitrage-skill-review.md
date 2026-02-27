# Skill Review: arbitrage

**Skill path:** `.claude/skills/arbitrage/SKILL.md`
**Review timestamp:** 2026-02-26-2228
**File stats:** 210 lines, ~1,890 tokens

## 1. Executive Summary

The arbitrage skill is one of the cleanest MCP-backed skills reviewed. It correctly delegates all data to `market(action="arbitrage_scan")` and `market(action="arbitrage_detail")`, includes an empty-results recovery sequence, and documents the expected response schema. The main issues are: an ASCII-box response template (Pattern E), a verbose MCP parameter documentation section that duplicates the tool's own schema, and a trailing persona adaptation section (lines 203-210) that restates the overlay loading mechanism from CLAUDE.md (Pattern B).

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | 🟢 | All data flows through `market_arbitrage_scan` and `market_arbitrage_detail`. No inlined market data. Lines 43-48 include a smart empty-results recovery sequence that retries with lower thresholds before giving up. |
| Prompt hygiene | 🟢 | Clear separation: MCP provides data, skill provides formatting. Line 48 documents expected response schema fields. No vague language that invites recall. |
| Failure handling | 🟢 | Empty results recovery (lines 43-46), expected schema documented (line 48), fee calculation defaults documented (lines 105-112). |
| Context window efficiency | 🟡 | MCP parameter docs (lines 59-73) duplicate tool schema. ASCII-box template (lines 87-101) could be a simpler format. Ad-hoc scope section (lines 147-194) is comprehensive but verbose for a feature most users won't use on first invocation. |

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 59-73 | `market_arbitrage_scan` parameter documentation — duplicates MCP tool schema | **REMOVE** — Claude already has the tool schema from MCP; restating parameters here is noise | ~120 tokens |
| `SKILL.md` | 75-81 | `market_arbitrage_detail` parameter documentation — same issue | **REMOVE** | ~50 tokens |
| `SKILL.md` | 87-101 | ASCII-box response template with ═ and ─ characters | **CONSOLIDATE** — convert to a plain markdown table template (Pattern E) | ~60 tokens |
| `SKILL.md` | 203-210 | "Persona Adaptation" section — restates overlay loading from CLAUDE.md/skill-loading.md | **REMOVE** — Pattern B, handled by skill loading mechanism. The `has_persona_overlay` field would be in frontmatter if applicable (it's not currently). | ~50 tokens |
| `SKILL.md` | 147-194 | Ad-hoc Market Scopes section — 48 lines of setup docs, scope types table, result labels | **CONSOLIDATE** — reduce to 5 lines pointing to `docs/ADHOC_MARKETS.md` (already referenced on line 151). The detailed setup steps, scope types table, and result labels duplicate that doc. | ~200 tokens |
| `SKILL.md` | 113-119 | Limits & Constraints section — formulas for cargo/liquidity/market/safe quantity | **CONSOLIDATE** — useful but could be 2 lines since the MCP tool calculates these internally | ~40 tokens |

**Total estimated savings: ~520 tokens (~28% of skill)**

## 4. Specific Findings

### High Severity

**H1. MCP parameter documentation duplicates tool schema (Pattern G — internal duplication with MCP)**
- **File:** `SKILL.md`, lines 57-81
- **Issue:** Two sections document `market_arbitrage_scan` and `market_arbitrage_detail` parameters with types and descriptions. Claude already receives this information from the MCP tool definition. Restating it in the skill wastes tokens and creates staleness risk if parameters change.
- **Action:** **REMOVE** both parameter sections (lines 57-81). Replace with a single line: "Use `market(action='arbitrage_scan')` and `market(action='arbitrage_detail')` — see MCP tool schema for parameters."

### Medium Severity

**M1. Ad-hoc Market Scopes section is verbose duplication**
- **File:** `SKILL.md`, lines 147-194
- **Issue:** 48 lines documenting watchlist creation, scope creation, scope types, and result labels. Line 151 already references `docs/ADHOC_MARKETS.md` as the full documentation. The inline content duplicates that doc and is too detailed for the skill context — most invocations won't use ad-hoc scopes.
- **Action:** **CONSOLIDATE** to ~5 lines: "Ad-hoc scopes extend scanning beyond trade hubs. Pass `include_custom_scopes=True` and `scopes=[...]` to the scan. Full setup: `docs/ADHOC_MARKETS.md`."

**M2. Persona Adaptation section restates system behavior (Pattern B)**
- **File:** `SKILL.md`, lines 203-210
- **Issue:** Restates the persona overlay loading mechanism. The skill's frontmatter doesn't even declare `has_persona_overlay: true`, so this section is both duplicative and potentially misleading.
- **Action:** **REMOVE** entirely. If the skill needs persona overlays, add `has_persona_overlay: true` to frontmatter — the loading mechanism handles the rest.

### Low Severity

**L1. ASCII-box response template (Pattern E)**
- **File:** `SKILL.md`, lines 87-101
- **Issue:** Uses ═ and ─ box-drawing characters for the response template. A plain markdown table conveys the same structure at lower token cost.
- **Action:** **CONSOLIDATE** to a markdown table template.

**L2. Use Cases section could be more compact**
- **File:** `SKILL.md`, lines 121-145
- **Issue:** Three use cases with example commands. Useful for disambiguation but verbose — the command syntax section (lines 19-39) already shows the same flags.
- **Action:** Keep but note as borderline. The examples add disambiguation value for natural-language triggers like "what should I haul."

## 5. Prioritized Recommendations

1. **REMOVE** MCP parameter documentation (lines 57-81) — duplicates tool schema, highest staleness risk. (Pattern G)
2. **CONSOLIDATE** Ad-hoc Market Scopes section (lines 147-194) to 5-line summary with doc pointer.
3. **REMOVE** Persona Adaptation section (lines 203-210) — restates system behavior and frontmatter lacks the flag. (Pattern B)
4. **CONSOLIDATE** ASCII-box template (lines 87-101) to markdown table. (Pattern E)
5. **CONSOLIDATE** Limits & Constraints (lines 113-119) to 2-line summary — MCP tool calculates internally.
