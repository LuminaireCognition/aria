# Skill Review: ship-next

**Skill path:** `.claude/skills/ship-next/SKILL.md`
**Review timestamp:** 2026-02-26-2228
**Files reviewed:** `SKILL.md` (333 lines, single file)

---

## 1. Executive Summary

The ship-next skill is significantly bloated at 333 lines, with roughly half the content being inlined ship progression tables and worked examples that duplicate data available from MCP tools (SDE item lookups, skill requirements, market prices). The skill hardcodes faction-specific ship progression paths, mining/exploration tier tables, and budget thresholds without declaring any `prerequisite_files`. The MCP tool usage section (lines 40-50) is well-structured, and the freshness gate pattern (lines 51-71) is a good model, but the massive ship database section (lines 198-224) and activity-specific guidance examples (lines 226-284) overwhelm the actual execution logic.

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | :yellow_circle: | Lines 40-44 correctly list required MCP tools. Lines 139-141 show the correct call sequence for readiness checks. But the skill then hardcodes ship progression paths (lines 99-133), ship database tables (lines 198-224), and budget tiers (lines 289-296) as inline reference data, giving Claude a bypass around MCP queries. |
| Prompt hygiene | :yellow_circle: | Line 45 has a good warning about `sde(action="item_info")` limitations. But the inlined faction progression tables (lines 107-112, 120-125) present specific ship recommendations as static truth rather than requiring SDE/market verification at runtime. |
| Failure handling | :green_circle: | Lines 299-305 cover no-skill-data, unknown faction, and no-activity-specified cases. The freshness gate (lines 51-71) handles ESI unavailability with clear fallback paths. |
| Context window efficiency | :red_circle: | ~130 lines of inlined ship data (lines 99-133 progression paths, 198-224 ship database, 226-284 worked examples) that should be either fetched from MCP or extracted to a reference file. The "Veteran-Endorsed Wisdom" section (lines 317-324) is flavor text. The "Skill Transfer Awareness" section (lines 274-284) is generic advice. |

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 99-133 | Faction-specific ship progression paths (Mission Running, Exploration, Mining) with full tables | **CONSOLIDATE** -- replace with imperative instruction: "Query `sde(action="search", category="Ship")` filtered by faction and class to build progression. Use pilot's trained faction from profile." Keep the abstract pattern (Frig -> Dest -> Cruiser -> BC -> BS) but remove the 4-faction tables. | ~250 tokens |
| `SKILL.md` | 198-224 | "Ship Database" section with Mission Running, Exploration, and Mining tier tables | **REMOVE** -- duplicates the progression paths above and can be derived from SDE queries at runtime | ~200 tokens |
| `SKILL.md` | 226-270 | Activity-Specific Guidance with two worked examples ("I want to do L2 missions" and "I'm in a Vexor, what's next?") | **CONSOLIDATE** -- reduce to one 8-line example showing the pattern. The second example (lines 248-270) is a near-duplicate of the first with a different starting ship. | ~250 tokens |
| `SKILL.md` | 272-284 | "Skill Transfer Awareness" section with cross-faction skill overlap examples | **REMOVE** -- generic EVE knowledge that Claude can derive from SDE skill requirements. Not a protocol instruction. | ~100 tokens |
| `SKILL.md` | 289-296 | Budget Awareness table (4 wallet tiers) | **CONSOLIDATE** -- reduce to 2-line instruction: "Scale recommendations to wallet. Suggest maintaining 3x replacement cost." The tier breakpoints are obvious. | ~60 tokens |
| `SKILL.md` | 307-314 | "Integration with Other Skills" table | **REMOVE** -- CLAUDE.md command suggestion protocol (Pattern B) | ~60 tokens |
| `SKILL.md` | 316-324 | "Veteran-Endorsed Wisdom" section (5 bullet points of generic advice) | **REMOVE** -- flavor text with no execution steering value (Pattern D) | ~80 tokens |
| `SKILL.md` | 326-333 | "Behavior Notes" section (5 bullet points) | **CONSOLIDATE** -- retain "default to pilot's faction" and "show at least one ready-now option." Remove the rest. | ~40 tokens |

**Estimated total savings:** ~1,040 tokens (~31% of file)

## 4. Specific Findings

### High Severity

**H1. Massive inlined ship data without prerequisite_files (Pattern A)**
- **File:** `SKILL.md`, lines 99-133 and 198-224
- Faction-specific progression tables and a "Ship Database" section hardcode ~50 lines of ship recommendations. This data can be queried from SDE at runtime and should not be inlined. The skill declares no `prerequisite_files`.
- **Action:** Remove the hardcoded tables. Replace with imperative instructions to query SDE for ship options by faction and class. If ship progression data is considered stable enough to warrant a reference file, create `reference/ships/progression_paths.yaml` and declare it as a prerequisite.

**H2. Ship bonuses and attributes not verified from MCP**
- **File:** `SKILL.md`, lines 226-270
- Worked examples include specific claims like "your Drones IV transfers directly" and "+50% drone damage" for the VNI. These ship attributes should come from `sde(action="item_info")` or `fitting(action="calculate_stats")` at runtime, not from training data baked into the skill.
- **Action:** Add a grounding instruction: "Verify ship bonuses via `sde(action="item_info")` before presenting upgrade rationale."

### Medium Severity

**M1. Two worked examples where one suffices (Pattern G adjacent)**
- **File:** `SKILL.md`, lines 226-270
- Two activity-specific guidance examples that follow the same pattern (current ship -> recommended next -> alternative -> long term). One example teaches the pattern; two wastes tokens.
- **Action:** **CONSOLIDATE** to one example.

**M2. "Veteran-Endorsed Wisdom" is flavor text (Pattern D)**
- **File:** `SKILL.md`, lines 316-324
- Five bullet points of generic advice ("Drake is boring but incredibly forgiving"). This is not an execution instruction.
- **Action:** **REMOVE**.

**M3. Skill Transfer Awareness is encyclopedic content**
- **File:** `SKILL.md`, lines 272-284
- Cross-faction skill overlap information that Claude can derive from SDE skill requirements data.
- **Action:** **REMOVE**.

### Low Severity

**L1. Integration table (Pattern B)**
- **File:** `SKILL.md`, lines 307-314
- Standard command suggestion table handled by CLAUDE.md.
- **Action:** **REMOVE**.

**L2. Budget tiers over-specified**
- **File:** `SKILL.md`, lines 289-296
- Four wallet tiers with specific ISK thresholds. The instruction "scale to wallet, maintain 3x replacement" is sufficient.
- **Action:** **CONSOLIDATE** to 2 lines.

## 5. Prioritized Recommendations

1. **Remove** hardcoded ship progression tables (lines 99-133) and Ship Database (lines 198-224). Replace with imperative MCP query instructions using SDE ship search by faction and class. (High impact -- ~450 tokens, eliminates Pattern A)

2. **Add** grounding instruction requiring `sde(action="item_info")` verification for ship bonuses before presenting recommendations. (High impact -- prevents hallucinated ship attributes)

3. **Consolidate** activity-specific guidance (lines 226-270) to one worked example. (Medium impact -- ~250 tokens)

4. **Remove** "Veteran-Endorsed Wisdom" (lines 316-324) and "Skill Transfer Awareness" (lines 272-284). (Medium impact -- ~180 tokens of zero-steering content)

5. **Remove** Integration table (lines 307-314). **Consolidate** Budget Awareness (lines 289-296) and Behavior Notes (lines 326-333). (Low impact -- ~160 tokens combined)
