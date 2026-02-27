# Skill Review: pi

**Skill path:** `.claude/skills/pi/`
**Review timestamp:** 2026-02-26-2228
**Files:** `SKILL.md` (499 lines, ~3,371 tokens)

## 1. Executive Summary

The PI skill is the largest of the five reviewed skills at 499 lines and is severely bloated with example responses. Roughly 60% of the file (lines 252-458) consists of example response templates that duplicate the same table/calculation patterns with different item names. The skill correctly declares `reference/mechanics/planetary-interaction.json` as a data source and includes a good "do not guess production chains" guardrail, but then undermines its own grounding discipline by inlining extensive example data that Claude may treat as authoritative instead of reading the reference file. Additionally, the profit calculation pseudocode (L172-232) is an inline reimplementation of logic that should come from the reference data, not be hardcoded in the skill.

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | :yellow_circle: | Correctly uses `market(action="prices")` for profit calculation (L211). But no MCP for PI-specific data -- relies on reference JSON file, which is appropriate for static game data. |
| Prompt hygiene | :yellow_circle: | Good "CRITICAL: Always read the reference file" guardrail (L166). But L487-492 contradicts itself: "DO NOT provide exact ISK/hour calculations" while the profit section (L170-425) does exactly that with detailed examples. |
| Failure handling | :yellow_circle: | Good post-fetch validation for missing prices (L214). No handling for missing reference file or malformed reference data. |
| Context window efficiency | :red_circle: | ~200 lines of example responses (L252-458) repeat the same calculation pattern with different items. One example suffices. The profit pseudocode (L172-232) inlines production constants that exist in the reference file. |

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 355-425 | P2 product profit example + P4 product profit example. Exact same table structure as the P3 example (L355-393). Two redundant examples. | **REMOVE** | ~550 tokens |
| `SKILL.md` | 172-198 | Profit calculation pseudocode Step 1. Inlines production constants (`output_qty`, `input_qty_each`, `cycle_hours`) from the reference JSON. Pattern (A). | **CONSOLIDATE** to "Read production constants from reference file for the product's tier" | ~200 tokens |
| `SKILL.md` | 218-232 | Profit calculation pseudocode Step 3. Inlines export cost formula with reference to `pi_data["export_costs_per_unit"]`. Could be 3 imperative lines. | **CONSOLIDATE** | ~100 tokens |
| `SKILL.md` | 307-343 | "Single-Planet P2 Query" example response. Lists specific planet/product combos that exist in the reference file. Pattern (A). | **REMOVE** | ~200 tokens |
| `SKILL.md` | 460-477 | "Skill Recommendations" section. Inlines specific skill names and priorities that should come from the reference file's skills section. Pattern (A). | **REMOVE** | ~120 tokens |
| `SKILL.md` | 108-126 | Cache file JSON structure example. Implementation detail that doesn't help steer response quality. | **REMOVE** | ~100 tokens |
| `SKILL.md` | 128-145 | Home system configuration JSON example. Duplicates CLAUDE.md topology config knowledge. Pattern (B). | **REMOVE** | ~100 tokens |
| `SKILL.md` | 49-81 | `/pi near` example response (33 lines). Could be trimmed to 10 lines. | **CONSOLIDATE** | ~100 tokens |
| `SKILL.md` | 487-492 | "DO NOT provide exact ISK/hour calculations" contradicts the entire profit section. | **REMOVE** the contradictory line | ~10 tokens |

**Total estimated savings: ~1,480 tokens (~44% reduction)**

## 4. Specific Findings

### High Severity

**H1. Three profit examples where one suffices**
- File: `SKILL.md`, L355-425 (P2 and P4 examples) duplicating the pattern from L355-393 (P3 example)
- All three examples use identical table structures with different numbers. Claude can generalize from one example. The P4 example adds a "Note: Requires Barren or Temperate" that could be a one-line instruction.
- **Action:** **Remove** P2 and P4 examples. Keep P3 as the canonical example. Add one line: "For P4 products, note they require Barren or Temperate planets. If profit is negative, warn the pilot."

**H2. Inlined production constants duplicate reference file**
- File: `SKILL.md`, L172-198
- Pattern (A): The pseudocode hardcodes `output_qty: 5`, `input_qty_each: 40`, `cycle_hours: 1` etc. These values exist in `reference/mechanics/planetary-interaction.json` under `production_constants`. If the reference file is updated, this pseudocode becomes stale.
- **Action:** **Consolidate** to imperative steps: "1. Read product from reference schematics. 2. Get production constants for the product's tier. 3. Extract all input names from the schematic."

**H3. Self-contradictory "DO NOT" instruction**
- File: `SKILL.md`, L492
- "DO NOT provide exact ISK/hour calculations (too many variables)" directly contradicts the ISK/Hour row in the profit response templates (L382, L422).
- **Action:** **Remove** the contradictory DO NOT line. The skill clearly intends to provide ISK/hour calculations.

### Medium Severity

**M1. Single-planet P2 example inlines reference data**
- File: `SKILL.md`, L307-343
- Pattern (A): Lists specific planet types and their P2 products. This data is in `single_planet_p2` in the reference JSON. Claude should read the reference, not use this inline copy.
- **Action:** **Remove**. Replace with: "Read `single_planet_p2` from reference file. Present grouped by planet type."

**M2. Skill recommendations section inlines game data**
- File: `SKILL.md`, L460-477
- Pattern (A): Lists specific skills (Command Center Upgrades V, Interplanetary Consolidation IV, etc.) with priorities. This data is in the reference file's skills section.
- **Action:** **Remove**. Replace with: "Read skill requirements from reference file. Present in priority order: production skills first, then scanning skills."

**M3. Cache structure and config examples are implementation noise**
- File: `SKILL.md`, L108-145
- The cache JSON structure (L108-126) and home system config (L128-145) are implementation details. Claude doesn't need to know the cache format to use the CLI commands. Pattern (B) for the config section.
- **Action:** **Remove** both blocks.

### Low Severity

**L1. `/pi near` example response is verbose**
- File: `SKILL.md`, L49-81
- The 33-line example could be a 10-line compact version showing the key structure without full planet listings.
- **Action:** **Consolidate** to a shorter example.

**L2. No ESI availability check**
- File: `SKILL.md` (absent)
- The skill uses CLI commands (`uv run aria-esi cache-planets`, `uv run aria-esi pi-near`) but has no ESI availability check like the orders skill does. The cache commands may depend on ESI.
- **Action:** Add ESI availability note for the cache-building commands (not needed for reference-only queries).

## 5. Prioritized Recommendations

1. **Remove** P2 and P4 profit examples (L395-458) -- saves ~550 tokens for zero steering loss. One example is sufficient.
2. **Remove** single-planet P2 inline data (L307-343) and skill recommendations (L460-477) -- Pattern (A), saves ~320 tokens.
3. **Consolidate** profit pseudocode (L172-232) to imperative steps without inlined constants -- Pattern (A), saves ~300 tokens.
4. **Remove** cache structure and config examples (L108-145) -- implementation noise, saves ~200 tokens.
5. **Remove** contradictory "DO NOT provide ISK/hour" line (L492).
6. **Consolidate** `/pi near` example to a compact 10-line version.
