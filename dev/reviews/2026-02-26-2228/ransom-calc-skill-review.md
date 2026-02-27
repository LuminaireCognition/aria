# Skill Review: ransom-calc

**Skill path:** `.claude/skills/ransom-calc/`
**Review timestamp:** 2026-02-26-2228
**Files:** `SKILL.md` (238 lines, ~1,681 tokens)

## 1. Executive Summary

The ransom-calc skill is a medium-sized pirate-themed skill that is almost entirely composed of inlined reference data: ship value tables, implant tiers, negotiation scripts, and cargo adjustment formulas. None of this data is fetched from MCP or any live source -- it is hardcoded game knowledge from training data, with no declared `prerequisite_files` or reference JSON to ground it. This makes the skill the worst offender among the five reviewed for grounding discipline: every number in the skill (ship values, insurance payouts, implant prices) is a stale training-data assertion that will drift from reality. The skill should fetch hull prices from `market(action="prices")` and use SDE for insurance calculations rather than inlining static tables.

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | :red_circle: | **No MCP usage at all.** Every price figure (ship values, implant costs, insurance payouts) is hardcoded in the skill file. No `market()` or `sde()` calls. No `prerequisite_files`. No `data_sources` (profile.md is listed but not used for pricing). |
| Prompt hygiene | :red_circle: | No "do not assume/recall" guardrail. The entire skill is built on recalled data. Ship value tables (L92-119) present specific ISK figures without any data source. |
| Failure handling | :red_circle: | No failure handling at all. No consideration of what happens if market data is unavailable, if the ship type isn't recognized, or if prices have changed dramatically. |
| Context window efficiency | :yellow_circle: | The inlined tables are at least compact. Negotiation scripts (L139-173) are flavor text that could be trimmed. But the bigger issue is that most of this content shouldn't be inline at all -- it should be fetched. |

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 92-119 | Three ship ransom baseline tables (Mining, Industrial, Mission/Ratting). Hardcoded ISK values with no data source. Pattern (A) without even having a prerequisite file. | **REMOVE** -- replace with MCP-based price fetch instructions | ~250 tokens |
| `SKILL.md` | 122-137 | Pod ransom / implant tier table. Hardcoded ISK values. | **REMOVE** -- replace with dynamic pricing note: "Use `market(action='prices')` for current implant set prices" | ~100 tokens |
| `SKILL.md` | 139-173 | Negotiation tactics section with four dialogue script examples. Flavor text, not operational data. | **REMOVE** | ~200 tokens |
| `SKILL.md` | 70-88 | "Ransom Philosophy" section with economics formula and reputation advice. Pattern (D) -- justification prose. | **CONSOLIDATE** to 3 lines: the formula, "honor ransoms," and "ransom < replacement - insurance" | ~100 tokens |
| `SKILL.md` | 174-184 | Cargo considerations table. Heuristic adjustment percentages. Could be 2 lines. | **CONSOLIDATE** | ~60 tokens |
| `SKILL.md` | 186-193 | Time pressure section. Generic PvP advice. | **REMOVE** | ~50 tokens |
| `SKILL.md` | 195-215 | Edge cases section (corp marks, new players, repeat customers). Generic advice, mostly flavor. | **REMOVE** or **CONSOLIDATE** to 3 lines | ~100 tokens |
| `SKILL.md` | 30-68 | Response format ASCII-box template. Verbose example with hardcoded numbers. | **CONSOLIDATE** to a compact template with placeholder markers | ~150 tokens |

**Total estimated savings: ~1,010 tokens (~60% reduction)**

## 4. Specific Findings

### High Severity

**H1. Zero data grounding -- all prices are hardcoded training data**
- File: `SKILL.md`, L92-119, L122-137
- Every ISK figure in the skill is a static assertion: "Retriever fit value: 35-45M", "Mackinaw insurance: 80M", "+5 implants: 1-2B". These are training-data snapshots that will become stale as the EVE economy evolves. No `prerequisite_files`, no `market()` calls, no `sde()` lookups.
- **Action:** **Remove** all hardcoded price tables. Replace with a MCP-first workflow:
  1. `sde(action="item_info", item="<ship>")` for hull metadata
  2. `market(action="prices", items=["<ship>"])` for current hull price
  3. Apply ransom heuristic (40-60% of estimated fitted value)
  4. For pods: ask the mark or estimate based on character age/corp

**H2. No failure handling for any data path**
- File: `SKILL.md` (absent)
- If the ship name isn't recognized, or market data is unavailable, or the user provides ambiguous input, the skill has no error handling instructions.
- **Action:** Add error handling: "If market data unavailable, state that prices cannot be verified and provide only the ransom formula without specific ISK figures."

**H3. No "do not fabricate" guardrail**
- File: `SKILL.md` (absent)
- The most critical skill to have this guardrail (since ransom amounts directly affect gameplay) is the one that lacks it entirely.
- **Action:** Add: "All price figures must come from MCP market data. Do not recall or estimate prices from training data."

### Medium Severity

**M1. Negotiation tactics section is pure flavor**
- File: `SKILL.md`, L139-173
- Four dialogue scripts ("120M and you keep your ship...", "100M. Final offer.", "10 seconds. Pay or pop.", "Pleasure doing business."). This is roleplaying flavor, not operational guidance. It consumes ~200 tokens.
- **Action:** **Remove** entirely. If negotiation guidance is wanted, add one line: "Open at the high end of the ransom range, be willing to settle at the low end."

**M2. Ransom philosophy section is Pattern (D) justification prose**
- File: `SKILL.md`, L70-88
- "The Economics of Ransom" explains why ransom works. Claude doesn't need the economic theory -- it needs the formula and the instruction.
- **Action:** **Consolidate** to: "Ransom formula: ransom < (replacement_cost - insurance_payout) + cargo_value. This ensures paying is the rational choice. Always honor ransom agreements."

**M3. Edge cases section is generic PvP advice**
- File: `SKILL.md`, L195-215
- "Corp marks may have backup coming", "new players -- check character age", "repeat customers -- adjust ransom". These are generic observations, not data-grounded instructions.
- **Action:** **Remove** or reduce to 3 bullet points max.

### Low Severity

**L1. Time pressure section is generic advice**
- File: `SKILL.md`, L186-193
- "Backup may be coming", "don't rush so fast they can't pay". Not skill-specific operational guidance.
- **Action:** **Remove**.

**L2. Response format template uses hardcoded values**
- File: `SKILL.md`, L30-68
- The example response shows "Mackinaw" with specific ISK figures (200M hull, 280-350M fit, 80M insurance). These would be replaced by live data in an MCP-first implementation.
- **Action:** **Consolidate** to a template with `{hull_price}`, `{fitted_estimate}`, `{insurance}` placeholders after MCP migration.

**L3. Overlap with price skill's PARIA overlay**
- File: `SKILL.md` vs `personas/paria/skill-overlays/price.md`
- The PARIA price overlay already includes ransom baseline calculations, gank math, and loot assessment. There is conceptual overlap between ransom-calc and the price overlay's ransom features. This isn't a bug but should be acknowledged.
- **Action:** Note for future: consider whether ransom-calc should reference the price overlay's ransom logic or vice versa to avoid divergence.

## 5. Prioritized Recommendations

1. **Modify** to MCP-first architecture: replace all hardcoded price tables with `market(action="prices")` and `sde(action="item_info")` calls -- this is the single highest-impact change across all five reviewed skills.
2. **Add** "do not fabricate prices" guardrail and error handling for missing data.
3. **Remove** negotiation tactics scripts (L139-173) -- saves ~200 tokens of pure flavor.
4. **Remove** hardcoded ship/implant price tables (L92-137) -- saves ~350 tokens, replaced by MCP calls.
5. **Consolidate** ransom philosophy (L70-88) to 3 lines -- Pattern (D), saves ~100 tokens.
6. **Remove** time pressure (L186-193) and edge cases (L195-215) generic advice -- saves ~150 tokens.
7. **Consolidate** response template to use placeholder markers for live data.
