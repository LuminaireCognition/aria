# Skill Review: skillplan

**Skill path:** `.claude/skills/skillplan/SKILL.md`
**Review timestamp:** 2026-02-26-2228
**Files reviewed:** `SKILL.md` (520 lines, single file)

---

## 1. Executive Summary

The skillplan skill is the largest of this batch at 520 lines, but it earns more of its length than the others due to genuine complexity (multiple query types, min-max vs easy-80 plans, activity plans, pilot-aware vs from-scratch modes). Its grounding discipline is excellent -- the hallucination guard (line 52), field-to-source mapping table (lines 56-70), anti-patterns section (lines 492-502), and "Golden Path" call sequence (lines 115-131) are model examples. The primary reduction opportunities are in the four verbose output examples (lines 337-456, ~120 lines) and the inlined Training Time Reference / Default Attributes sections (lines 304-325) which duplicate data the MCP tools already compute.

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | :green_circle: | Line 52 has an explicit hallucination guard: "Every training time, skill name, skill level, and efficacy estimate MUST come from MCP tool responses." Lines 115-131 define the "Golden Path" minimal call sequence. Line 132 explicitly warns against redundant `sde(action="skill_requirements")` calls. |
| Prompt hygiene | :green_circle: | The field-to-source mapping table (lines 56-70) is exemplary -- every output field has a named MCP source. Lines 492-502 provide anti-patterns with wrong/right examples. Lines 72-74 explain why `current_skills` matters. |
| Failure handling | :green_circle: | Lines 86-90 handle ESI freshness gate with three states. Lines 370-396 show a complete from-scratch fallback example with prominent warning. Lines 329-333 cover item-not-found, no-skill-data, and MCP-unavailable errors. |
| Context window efficiency | :yellow_circle: | Four full output examples (lines 337-456) consume ~120 lines. The Training Time Reference table (lines 304-313) and Default Attributes section (lines 315-325) duplicate information that MCP tools already use internally. The Multiplier Skills table (lines 469-481) duplicates data available from `skills(action="get_multipliers")`. |

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 370-396 | "Ship Example (ESI unavailable)" -- full 27-line output example nearly identical to lines 337-368 but with a warning banner | **CONSOLIDATE** -- show only the delta: the warning banner and one line demonstrating "from scratch" formatting. Remove the full duplicate example. | ~150 tokens |
| `SKILL.md` | 398-421 | "Module Example" -- 23-line output example | **CONSOLIDATE** -- reduce to 8-line skeleton showing the unique aspects (T2 Level V requirement, meta alternative suggestion). The full table formatting is already established by the ship example. | ~100 tokens |
| `SKILL.md` | 423-456 | "Activity Example" -- 33-line output example | **CONSOLIDATE** -- reduce to 10-line skeleton showing the unique three-tier structure (minimum/easy_80/full). The pattern is already established. | ~150 tokens |
| `SKILL.md` | 304-313 | "Training Time Reference" table (level multipliers and cumulative times) | **REMOVE** -- the MCP `skills(action="training_time")` tool computes these. Claude should not be presenting pre-computed training time tables. The "key insight" on line 314 is the only valuable part -- keep that as a one-liner. | ~80 tokens |
| `SKILL.md` | 315-325 | "Default Attributes" section (attribute values for a fresh character) | **REMOVE** -- the MCP tool already uses these defaults when no attributes are passed. This is implementation detail that doesn't affect Claude's behavior. | ~70 tokens |
| `SKILL.md` | 469-481 | "Multiplier Skills" table (6 rows of skill names and effects) | **REMOVE** -- duplicates data from `skills(action="get_multipliers")` which is already referenced on line 470. Replace with one-line imperative: "Use `skills(action='get_multipliers')` to identify high-impact skills." | ~80 tokens |
| `SKILL.md` | 483-489 | "Reference Data" section listing prerequisite file paths | **REMOVE** -- these files are already declared in frontmatter `prerequisite_files` (lines 21-23). The skill loading mechanism reads them automatically. Restating the paths is Pattern B. | ~50 tokens |
| `SKILL.md` | 513-520 | "Persona Adaptation" section | **REMOVE** -- duplicates CLAUDE.md skill loading mechanism (Pattern B) | ~40 tokens |
| `SKILL.md` | 458-467 | "Contextual Suggestions" table | **REMOVE** -- CLAUDE.md command suggestion protocol (Pattern B) | ~50 tokens |

**Estimated total savings:** ~770 tokens (~15% of file)

## 4. Specific Findings

### High Severity

**H1. Training Time Reference table is MCP-computed data (Pattern A)**
- **File:** `SKILL.md`, lines 304-313
- The level multiplier and cumulative time table presents pre-computed values that the MCP `training_time` action computes dynamically. Inlining these values means Claude might present them directly instead of calling MCP. The "key insight" (Level V = ~4.5x more than I-IV) on line 314 is the only behaviorally useful part.
- **Action:** **REMOVE** the table. Keep line 314 as a one-line insight to guide Easy 80% framing.

**H2. Multiplier Skills table duplicates MCP tool output**
- **File:** `SKILL.md`, lines 469-481
- Six hardcoded skill/effect pairs that are available from `skills(action="get_multipliers")`. The line immediately above (470) even references this tool, making the inline table redundant.
- **Action:** **REMOVE** the table. Keep the one-line reference to the MCP tool.

### Medium Severity

**M1. Four output examples where two would suffice (Pattern G)**
- **File:** `SKILL.md`, lines 337-456
- Four complete output examples totaling ~120 lines: ship (pilot-aware), ship (from-scratch), module, and activity. The ship examples are near-identical except for the ESI warning. The module and activity examples establish patterns already shown in the ship example.
- **Action:** Keep the pilot-aware ship example (lines 337-368) as the primary template. For the from-scratch variant, show only the warning delta (3 lines). For module and activity, show 8-10 line skeletons highlighting unique aspects (T2 meta alternatives; three-tier activity structure).

**M2. Default Attributes section is internal implementation detail**
- **File:** `SKILL.md`, lines 315-325
- Lists the five attribute values used when no implants/remaps are specified. The MCP tool already uses these defaults internally. Including them here adds no steering value.
- **Action:** **REMOVE**.

**M3. Reference Data section duplicates frontmatter (Pattern B)**
- **File:** `SKILL.md`, lines 483-489
- Lists the three prerequisite files that are already declared in lines 21-23 of the frontmatter. The skill loading mechanism already reads these before the skill produces output.
- **Action:** **REMOVE**.

### Low Severity

**L1. Contextual Suggestions table (Pattern B)**
- **File:** `SKILL.md`, lines 458-467
- Standard command suggestion table covered by CLAUDE.md.
- **Action:** **REMOVE**.

**L2. Persona Adaptation section (Pattern B)**
- **File:** `SKILL.md`, lines 513-520
- Duplicates CLAUDE.md skill loading overlay mechanism.
- **Action:** **REMOVE**.

**L3. Step 4 "Apply Easy 80% Rules" section is descriptive, not prescriptive**
- **File:** `SKILL.md`, lines 214-219
- Describes what the `easy_80_plan` tool does internally (cap at IV, train to V when required, identify multipliers, calculate efficacy). Since the tool does this automatically, this section describes MCP internals rather than instructing Claude.
- **Action:** **CONSOLIDATE** to one line: "The `easy_80_plan` response includes categorized skills, efficacy estimates, and multiplier flags. Present these directly."

## 5. Prioritized Recommendations

1. **Remove** Training Time Reference table (lines 304-313) and Default Attributes (lines 315-325). Keep only the "Level V = 4.5x more" insight as a one-liner. (High impact -- eliminates inlined MCP-computed data)

2. **Remove** Multiplier Skills table (lines 469-481). Replace with one-line MCP reference. (High impact -- eliminates Pattern A)

3. **Consolidate** output examples (lines 337-456) from four full examples (~120 lines) to one primary + three skeleton deltas (~50 lines). (Medium impact -- ~300 tokens)

4. **Remove** Reference Data section (lines 483-489), Contextual Suggestions (lines 458-467), and Persona Adaptation (lines 513-520). All are Pattern B duplicates. (Medium impact -- ~140 tokens)

5. **Consolidate** Step 4 "Apply Easy 80% Rules" (lines 214-219) to one-line description. (Low impact -- ~30 tokens)

6. **Modify** -- the skill's grounding discipline (hallucination guard, field-source mapping, anti-patterns, Golden Path) is exemplary and should be preserved as-is. Consider extracting the anti-patterns format as a pattern for other skills to adopt.
