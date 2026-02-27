# Skill Review: build-cost

**Skill path:** `.claude/skills/build-cost/SKILL.md`
**Review timestamp:** 2026-02-26-2228
**File size:** 29,656 bytes (~7,400 tokens)

## 1. Executive Summary

The build-cost skill is the largest of the five reviewed at ~7,400 tokens and contains significant bloat from verbose response format examples, inlined reference data (facility bonuses, decryptor tables, terminal materials), and pseudocode that duplicates what MCP dispatchers already handle. The MCP-first discipline is strong for material extraction but weakens in later sections where hardcoded data tables and Python import blocks reference non-existent service modules.

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | :green_circle: | Strong. Material Extraction Protocol (lines 31-58) explicitly forbids hardcoded materials; steps 1-5 mandate `sde(action="blueprint_info")` and `market(action="prices")`. |
| Prompt hygiene | :yellow_circle: | Steps 1-5 are clear. But facility bonuses (lines 597-604), decryptor table (lines 789-801), terminal materials (lines 473-479), and NPC null regions are inlined as static data rather than sourced from reference files or MCP. |
| Failure handling | :green_circle: | Excellent. Lines 122-146 mandate price completeness verification with a prominent warning format. Pre-Response Validation (lines 358-369) adds a second gate. |
| Context window efficiency | :red_circle: | Severely bloated. Three full response format examples (standard, multi-run, simple item) consume ~2,000 tokens. Pseudocode blocks import from non-existent modules. Decryptor table and facility bonus data are inlined instead of referenced. |

## 3. Reduction Inventory

| File | Lines | What | Action | Est. Token Savings |
|------|-------|------|--------|-------------------|
| SKILL.md | 222-302 | Response Format: full Dominix example + multi-run example | CONSOLIDATE | ~600 tokens. Keep one terse example, remove the other. |
| SKILL.md | 304-339 | Simple Item Example (Hammerhead I) | REMOVE | ~300 tokens. The standard format example already demonstrates the pattern; a second simpler one adds nothing. |
| SKILL.md | 341-356 | ME Comparison Table example | CONSOLIDATE | ~120 tokens. One sentence describing the table suffices. |
| SKILL.md | 444-468 | Full Chain Implementation block with `from aria_esi.services.industry_chains import` | REMOVE | ~200 tokens. Module does not exist; pseudocode is aspirational, not steering. |
| SKILL.md | 473-479 | Terminal Materials inline list | REMOVE | ~60 tokens. Line 480 already references `reference/industry/terminal_materials.json`. The inline list duplicates it (pattern A). |
| SKILL.md | 482-516 | Full Chain Output Format example | CONSOLIDATE | ~250 tokens. Merge into a 5-line skeleton. |
| SKILL.md | 534-569 | Profit Per Hour Implementation with `from aria_esi.services.industry_costs import` | REMOVE | ~250 tokens. Module does not exist; the formula is in the response format already. |
| SKILL.md | 571-587 | TE Comparison Table example output | REMOVE | ~130 tokens. Duplicates information already implicit in the response format. |
| SKILL.md | 589-695 | Job Installation Cost section with facility bonuses, formula, implementation, response formats, and facility comparison table | CONSOLIDATE | ~800 tokens. The inlined facility bonuses dict (lines 597-604) duplicates `reference/industry/facility_bonuses.json`. Keep the formula, remove inline data and verbose examples. |
| SKILL.md | 697-713 | Cost Considerations (Show in Notes) | CONSOLIDATE | ~100 tokens. Two nearly identical note blocks; merge to one. |
| SKILL.md | 715-858 | T2 Invention Cost Calculation (entire section) | CONSOLIDATE | ~1,100 tokens. Decryptor table (lines 789-801) is inlined reference data (pattern A). Python imports reference non-existent modules. Keep the formula and response skeleton, remove pseudocode and inline tables. |
| SKILL.md | 860-996 | Character Integration section | CONSOLIDATE | ~1,000 tokens. Pseudocode imports from `aria_esi.services.character_industry` (does not exist). Response formats are verbose. Reduce to behavioral instructions only. |
| SKILL.md | 998-1008 | DO NOT list | CONSOLIDATE | ~80 tokens. Several items duplicate the Material Extraction Protocol and Pre-Response Validation. |
| SKILL.md | 1009-1034 | Industry Advisory Protocol + Notes | CONSOLIDATE | ~150 tokens. Lines 1026-1034 repeat information from earlier sections. |

**Total estimated savings: ~5,140 tokens (~69% reduction)**

## 4. Specific Findings

### High Severity

**H1. Inlined reference data duplicates declared files (Pattern A)**
- File: `SKILL.md`, lines 597-604 — Facility bonuses dict duplicates `reference/industry/facility_bonuses.json`
- File: `SKILL.md`, lines 473-479 — Terminal materials list duplicates `reference/industry/terminal_materials.json`
- File: `SKILL.md`, lines 789-801 — Decryptor modifier table likely duplicates `reference/industry/invention_materials.json`
- **Action:** REMOVE inline data. Replace each with a one-line imperative reference: "Read `reference/industry/facility_bonuses.json` for facility ME/TE bonuses."

**H2. Pseudocode imports from non-existent modules**
- File: `SKILL.md`, lines 444-468 — `from aria_esi.services.industry_chains import ChainResolver, format_chain_summary`
- File: `SKILL.md`, lines 534-569 — `from aria_esi.services.industry_costs import calculate_profit_per_hour, ...`
- File: `SKILL.md`, lines 740-787 — `from aria_esi.services.industry_costs import calculate_invention_success_rate, ...`
- File: `SKILL.md`, lines 860-949 — `from aria_esi.services.character_industry import ...`
- **Action:** REMOVE. These modules do not exist. The pseudocode steers Claude to call non-existent functions, which will fail at runtime. Replace with MCP dispatcher instructions or formulas.

### Medium Severity

**M1. Three redundant response format examples**
- File: `SKILL.md`, lines 222-302 (Dominix standard + multi-run), lines 304-339 (Hammerhead simple)
- **Action:** CONSOLIDATE to one concise example. The Dominix example is sufficient.

**M2. ME Comparison and TE Comparison tables are output templates, not behavioral instructions**
- File: `SKILL.md`, lines 341-356 and 571-587
- **Action:** CONSOLIDATE each to a one-sentence instruction: "When no ME is specified, show ME 0/5/10 comparison."

**M3. Duplicate validation gates**
- Pre-Response Validation (lines 358-369) substantially overlaps with the Validation Rule in Material Extraction Protocol (lines 42-45) and Step 5 (lines 122-132).
- **Action:** CONSOLIDATE. Keep Pre-Response Validation as the single gate; remove the redundant validation from steps 2 and 5.

### Low Severity

**L1. Command syntax section is verbose**
- File: `SKILL.md`, lines 20-29 — Eight example invocations where 3-4 would suffice.
- **Action:** CONSOLIDATE to 4 representative examples.

**L2. "Integration with Other Skills" table (lines 428-436) is low-value**
- These are generic cross-references that CLAUDE.md's command suggestion system already handles.
- **Action:** REMOVE.

## 5. Prioritized Recommendations

1. **REMOVE** all pseudocode blocks importing from non-existent modules (lines 444-468, 534-569, 740-787, 860-949). Replace with concise MCP dispatcher instructions or formulas. (~2,450 tokens)
2. **REMOVE** inlined reference data (facility bonuses, terminal materials, decryptor table). Replace with one-line "Read `reference/...`" directives. (~260 tokens)
3. **CONSOLIDATE** response format examples from three to one. Remove Simple Item Example and Multi-Run Example entirely. (~900 tokens)
4. **CONSOLIDATE** the T2 Invention section to formula + response skeleton only. (~500 tokens)
5. **CONSOLIDATE** Job Installation Cost section: keep formula, remove inline data and verbose examples. (~500 tokens)
6. **REMOVE** "Integration with Other Skills" table. (~60 tokens)
7. **MODIFY** Pre-Response Validation to be the single validation gate; remove redundant validation steps.
