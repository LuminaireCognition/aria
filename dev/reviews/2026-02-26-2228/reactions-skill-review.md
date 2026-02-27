# Skill Review: reactions

**Skill path:** `.claude/skills/reactions/SKILL.md`
**Review timestamp:** 2026-02-26-2228
**Files reviewed:** `SKILL.md` (276 lines, single file)

---

## 1. Executive Summary

The reactions skill is bloated with inlined reference data (fuel block tables, material sources, reaction time formulas) that should live in prerequisite files or be fetched from MCP at runtime. At 276 lines it is roughly 2x its necessary size. The Python code examples reference a `reactions` service module but the skill has no `prerequisite_files` or `data_sources` declared, meaning all the inlined data is the only source of truth -- a staleness risk that should be resolved by either creating a reference data file or relying on MCP/SDE lookups.

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | :yellow_circle: | Lines 73-79 correctly use `market(action="prices")` for live prices. Line 42 mentions `sde(action="search")` and `sde(action="item_info")`. But the skill also hardcodes fuel block data (lines 178-186), material sources (lines 190-201), and reaction formulas (lines 203-223) inline -- allowing Claude to skip MCP entirely. |
| Prompt hygiene | :yellow_circle: | Line 80-81 has a good "CRITICAL" bulk-call instruction. Line 132 correctly warns quantities are illustrative. However, lines 178-201 present static game data as authoritative without requiring MCP verification, creating ambiguity about what's ground truth. |
| Failure handling | :green_circle: | Lines 228-251 cover missing prices and unknown fuel blocks cleanly with example error formats. |
| Context window efficiency | :red_circle: | The response format example (lines 134-176) is 42 lines of illustrative numbers that could be 10 lines. The fuel block reference table, material sources, and reaction time formula sections (lines 178-223) duplicate data that should be fetched from SDE/blueprint_info at runtime. The Python import examples (lines 47-63) reference a service module that may or may not exist. |

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 134-176 | Response format example with fake illustrative numbers spanning 42 lines | **CONSOLIDATE** -- reduce to 15-line skeleton with `[computed]` placeholders | ~250 tokens |
| `SKILL.md` | 178-186 | Fuel Block Reference table (4-row static table) | **REMOVE** -- fetch from `sde(action="blueprint_info")` at runtime; add one-line imperative instruction | ~80 tokens |
| `SKILL.md` | 188-201 | Material Sources section (PI materials + ice products) | **REMOVE** -- this is static game data that belongs in a reference file or should be fetched from SDE | ~120 tokens |
| `SKILL.md` | 203-223 | Reaction Time Formula section with per-level table and refinery table | **CONSOLIDATE** -- keep the formula (1 line), remove the two expansion tables (lines 209-223) which spell out trivial arithmetic | ~120 tokens |
| `SKILL.md` | 46-128 | Python code examples spanning 82 lines with full import paths, variable assignments, and comments | **CONSOLIDATE** -- replace with 20-line pseudocode showing the call sequence without boilerplate | ~400 tokens |
| `SKILL.md` | 253-260 | "Integration with Other Skills" suggestion table | **REMOVE** -- CLAUDE.md command suggestion protocol already handles this | ~60 tokens |
| `SKILL.md` | 262-268 | "DO NOT" section (4 items, some obvious) | **CONSOLIDATE** -- keep only the non-obvious ME warning (line 265); the rest are redundant with the formulas section | ~40 tokens |
| `SKILL.md` | 269-276 | "Notes" section with generic truisms ("fuel blocks are essential", "PI materials can be self-produced or bought") | **REMOVE** -- zero steering value | ~60 tokens |

**Estimated total savings:** ~1,130 tokens (~40% of file)

## 4. Specific Findings

### High Severity

**H1. Inlined reference data without prerequisite_files declaration (Pattern A)**
- **File:** `SKILL.md`, lines 178-201
- The fuel block reference table and material sources sections hardcode static game data. There is no `prerequisite_files` or `data_sources` entry in the frontmatter. If this data changes with a game patch, the skill goes stale silently.
- **Action:** Either create `reference/mechanics/fuel_blocks.json` and add to `prerequisite_files`, or replace inline data with imperative SDE lookups: `sde(action="blueprint_info", item="Nitrogen Fuel Block")`.

**H2. Python service imports may reference non-existent module**
- **File:** `SKILL.md`, lines 47-53
- The skill imports from `aria_esi.services.reactions` (functions like `get_fuel_block_info`, `calculate_fuel_block_cost`, etc.). If this module does not exist, the entire execution flow is broken.
- **Action:** Verify the module exists. If it does, the Python code examples are still too verbose -- reduce to call sequence pseudocode. If it does not, remove the code examples and replace with MCP-only flow.

### Medium Severity

**M1. Overly verbose response format example (Pattern E adjacent)**
- **File:** `SKILL.md`, lines 134-176
- 42 lines of illustrative output with fake numbers. A 15-line skeleton template with `[computed]` placeholders would steer identically.
- **Action:** **CONSOLIDATE** to skeleton format.

**M2. Reaction time formula expansion tables are trivial arithmetic**
- **File:** `SKILL.md`, lines 209-223
- Two tables spelling out `skill_level * 4%` and listing exactly two refineries. Claude can compute `4 * 4 = 16%` without a lookup table.
- **Action:** **REMOVE** the tables, keep only the formula on line 206-207.

### Low Severity

**L1. "Notes" section is zero-value padding**
- **File:** `SKILL.md`, lines 269-276
- Generic statements like "fuel blocks are essential for structure operation" and "PI materials can be self-produced or bought" provide no steering value.
- **Action:** **REMOVE** entirely.

**L2. Integration table duplicates CLAUDE.md command suggestion behavior (Pattern B)**
- **File:** `SKILL.md`, lines 253-260
- CLAUDE.md already has a command suggestion protocol. This table adds skill-specific suggestions that could be a single line: "Suggest `/pi`, `/mining-advisory ice`, or `/price` when contextually relevant."
- **Action:** **REMOVE** table, replace with one-line note if needed.

## 5. Prioritized Recommendations

1. **Remove** inlined fuel block and material source data (lines 178-201). Replace with imperative MCP/SDE lookups. Either create a prerequisite data file or add `sde(action="blueprint_info")` as the authoritative source. (High impact -- eliminates staleness risk)

2. **Consolidate** Python code examples (lines 46-128) from 82 lines to ~20-line pseudocode call sequence. Remove import boilerplate and inline comments. (High impact -- ~400 token savings)

3. **Consolidate** response format example (lines 134-176) to a 15-line skeleton template with `[computed]` placeholders instead of fake numbers. (Medium impact -- ~250 tokens)

4. **Remove** reaction time expansion tables (lines 209-223). Keep only the formula. (Medium impact -- ~120 tokens)

5. **Remove** "Notes" section (lines 269-276) and "Integration" table (lines 253-260). (Low impact -- ~120 tokens combined)

6. **Add** `prerequisite_files` or `data_sources` to frontmatter if reference data files are created for fuel block mechanics.
