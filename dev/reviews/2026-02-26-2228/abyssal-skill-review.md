# Skill Review: abyssal

**Skill path:** `.claude/skills/abyssal/SKILL.md`
**Review timestamp:** 2026-02-26-2228
**File stats:** 257 lines, ~1,725 tokens

## 1. Executive Summary

The abyssal skill is overwhelmingly composed of example response templates that inline the very data the skill's `data_sources` declaration points to (`reference/mechanics/abyssal_deadspace.json`). Lines 52-222 consist of five lengthy example responses containing specific ship names, weather effects, damage profiles, NPC behaviors, and fitting advice — all of which should come from the JSON reference file at runtime. Removing these examples and replacing them with terse structural templates would cut the skill by ~60%.

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | 🟡 | Lines 48, 81, 114, 152 correctly instruct "Read reference file first," but the massive inline examples undermine this by providing the data Claude needs without reading the file. |
| Prompt hygiene | 🔴 | Example responses on lines 54-76, 88-108, 120-146, 159-184, 196-222 contain specific game data (damage profiles, ship stats, weather effects) that should only come from the JSON file. Claude can pattern-match from examples instead of querying. |
| Failure handling | 🔴 | No instruction for what to do if the reference file is missing, incomplete, or lacks data for a queried weather/ship/NPC. |
| Context window efficiency | 🔴 | ~170 of 257 lines are example responses with inlined reference data. Estimated ~1,100 wasted tokens. |

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 52-76 | Weather type example response with inlined damage profiles, ship recommendations | **REMOVE** — replace with 3-line structural template | ~200 tokens |
| `SKILL.md` | 88-108 | Tier query example with inlined loot values, requirements, progression advice | **REMOVE** — replace with 3-line structural template | ~170 tokens |
| `SKILL.md` | 120-146 | Ship recommendation example with inlined strengths/weaknesses/weather preferences | **REMOVE** — replace with 3-line structural template | ~220 tokens |
| `SKILL.md` | 159-184 | NPC threat example with inlined damage/resist profiles, kill priorities, mechanics | **REMOVE** — replace with 3-line structural template | ~210 tokens |
| `SKILL.md` | 196-222 | Fitting guidance example with inlined module names, target stats, drone picks | **REMOVE** — replace with 3-line structural template | ~220 tokens |
| `SKILL.md` | 224-231 | "Integration with Other Skills" table — generic cross-references | **REMOVE** — provides minimal steering value | ~50 tokens |
| `SKILL.md` | 232-242 | Safety warnings block — useful content but verbose with code block wrapping | **CONSOLIDATE** — reduce to 2 imperative lines | ~40 tokens |
| `SKILL.md` | 251-257 | "Notes" section — general abyssal facts Claude can derive from JSON | **REMOVE** — the JSON file is the authority | ~50 tokens |

**Total estimated savings: ~1,160 tokens (~67% of skill)**

## 4. Specific Findings

### High Severity

**H1. Example responses inline reference data (Pattern A)**
- **File:** `SKILL.md`, lines 52-222
- **Issue:** Five example responses contain specific damage percentages, ship names with strengths/weaknesses, NPC kill priorities, module names, and EHP targets. All of this data exists in (or should exist in) `reference/mechanics/abyssal_deadspace.json`. The examples give Claude a shortcut to skip the file read entirely, which is the opposite of what lines 48, 81, 114, 152 instruct.
- **Action:** **REMOVE** all five example response blocks. Replace each with a 3-line structural template showing section headers only (e.g., "Environmental Effects / NPC Damage Profile / Tank Recommendation / Best Ships / Notes"). The JSON file provides the actual data.

**H2. No failure handling for missing or incomplete data**
- **File:** `SKILL.md` (entire file)
- **Issue:** If the reference JSON lacks an entry for a queried weather type, ship, or NPC faction, there is no instruction for how to respond. Claude would fall back to training data recall — the exact failure mode grounding discipline exists to prevent.
- **Action:** **Add** a failure handling section: "If the reference file does not contain an entry for the queried item, state that no verified data is available and suggest checking community resources."

### Medium Severity

**M1. Line 40 references external community resource without guardrail**
- **File:** `SKILL.md`, line 40
- **Issue:** "Verify current meta on community resources like abyss.eve-nt.uk" — this instruction is vague and gives no protocol for how to verify or what to do if the resource disagrees with the JSON file.
- **Action:** **Modify** — either remove the community resource reference or make it explicit: "If the pilot asks about current meta, suggest they check abyss.eve-nt.uk. Do not fetch or infer meta data."

**M2. Fitting guidance example contains specific module names (Pattern A)**
- **File:** `SKILL.md`, lines 196-222
- **Issue:** Lists "Large Shield Extender II x2", "Drone Damage Amplifier II x3", "Ogre II", "Gecko" etc. These are training-data-sourced recommendations, not from any declared data source. The skill has no `prerequisite_files` for module data.
- **Action:** **REMOVE** the example. Fitting guidance should defer to the `/fitting` skill or `fitting(action="calculate_stats")` as line 192 already suggests.

### Low Severity

**L1. "Integration with Other Skills" table is generic noise**
- **File:** `SKILL.md`, lines 224-231
- **Issue:** Cross-references to `/fitting`, `/price`, `/skillplan` are generic suggestions that CLAUDE.md's command suggestion system already handles.
- **Action:** **REMOVE** — duplicates CLAUDE.md behavior (Pattern B).

**L2. "Notes" section restates general knowledge**
- **File:** `SKILL.md`, lines 251-257
- **Issue:** Facts like "weather effects apply to both player and NPCs" and "room layouts are randomized" are general game knowledge that should be in the JSON reference, not inlined.
- **Action:** **REMOVE** — either the JSON file has this or it doesn't need to be in the skill.

## 5. Prioritized Recommendations

1. **REMOVE** all five example response blocks (lines 52-222). Replace with structural templates showing section headers only. This is the single highest-impact change — eliminates ~1,020 tokens of inlined reference data and forces proper JSON reads. (Pattern A)
2. **Add** failure handling instructions for when the reference JSON lacks data for a query.
3. **REMOVE** "Notes" section (lines 251-257) and "Integration" table (lines 224-231). (Patterns A, B)
4. **Modify** community resource reference on line 40 to be a concrete suggestion to the pilot, not a vague instruction to Claude.
5. **CONSOLIDATE** safety warnings (lines 232-242) into 2 imperative lines without code block wrapping.
