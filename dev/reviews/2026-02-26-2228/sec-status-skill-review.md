# Skill Review: sec-status

**Skill path:** `.claude/skills/sec-status/SKILL.md`
**Review timestamp:** 2026-02-26-2228
**Files reviewed:** `SKILL.md` (222 lines, single file)

---

## 1. Executive Summary

The sec-status skill is a moderately-sized skill (222 lines) that serves primarily as a reference document for security status mechanics. Its most significant issue is that it inlines extensive static game data (threshold tables, faction police response times, clone soldier tag values, sec loss values) without declaring any `prerequisite_files`, creating staleness risk and bloating the context window. The skill has good MCP discipline for tag prices but embeds roughly 120 lines of game mechanics reference data that should be extracted to a dedicated reference file.

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | :yellow_circle: | Line 115 correctly mandates `market(action="prices")` for tag prices with bold emphasis. However, sec status thresholds (lines 67-83), faction police response times (lines 87-94), tag sec gains (lines 108-114), tag farming locations (lines 119-124), and sec loss values (lines 157-163) are all hardcoded. These are static game data unlikely to change often, but the skill has no mechanism to detect if they do. |
| Prompt hygiene | :green_circle: | Line 115 is clear and unambiguous about fetching live prices. The static data tables are presented as reference, not as "go fetch this." The distinction is appropriate -- these are game constants, not volatile data. |
| Failure handling | :yellow_circle: | No explicit handling for ESI scope failure (the skill requires `esi-characters.read_standings.v1`). No guidance on what to do if the pilot's sec status can't be fetched from ESI. The cost calculation example (lines 134-151) assumes prices are available but doesn't address the case where market queries fail. |
| Context window efficiency | :red_circle: | ~120 lines of static reference data tables (lines 67-163) that should be in a prerequisite file. The "Practical Implications" section (lines 180-199) is generic gameplay advice. The "Living with Low Sec Status" section (lines 174-179) is flavor text. |

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 67-83 | Empire Access by Sec Status table (17 lines) | **CONSOLIDATE** -- extract to `reference/mechanics/security_status.json` and add to `prerequisite_files` | ~150 tokens |
| `SKILL.md` | 85-101 | Faction Police Response section (response times table + behavior list) | **CONSOLIDATE** -- extract to same reference file | ~120 tokens |
| `SKILL.md` | 107-124 | Clone Soldier Tags table + Tag Farming section | **CONSOLIDATE** -- extract tag data to reference file; keep the one-line MCP instruction for prices | ~100 tokens |
| `SKILL.md` | 126-151 | Ratting Recovery + Cost Calculations section with worked example | **CONSOLIDATE** -- the worked example (lines 134-151) is 17 lines for a simple division problem. Reduce to 3-line imperative: "Fetch tag prices, compute ISK-per-sec-point, recommend cheapest tags first." | ~120 tokens |
| `SKILL.md` | 153-179 | "Security Status Impacts" section (sec loss table + "Downward Spiral" + "Living with Low Sec Status") | **CONSOLIDATE** -- extract sec loss table to reference file. Remove "Downward Spiral" (lines 165-171, Pattern D -- explains consequences that are self-evident from the threshold table) and "Living with Low Sec Status" (lines 173-179, flavor text) | ~150 tokens |
| `SKILL.md` | 180-199 | "Practical Implications" section (Trading, Logistics, Mission Running) | **REMOVE** -- generic gameplay advice with no skill-specific steering value. Claude can infer these implications from the threshold table. | ~120 tokens |
| `SKILL.md` | 201-207 | "Integration with Other Skills" table | **REMOVE** -- CLAUDE.md command suggestion protocol handles this (Pattern B) | ~50 tokens |

**Estimated total savings:** ~810 tokens (~37% of file)

## 4. Specific Findings

### High Severity

**H1. Extensive inlined game data without prerequisite_files (Pattern A)**
- **File:** `SKILL.md`, lines 67-163
- Approximately 100 lines of static game data tables: sec status thresholds, faction police response times, clone soldier tag values, tag farming locations, sec loss values. None of this is declared in `prerequisite_files` or `data_sources`.
- **Action:** Create `reference/mechanics/security_status.json` containing all static sec status data. Add to `prerequisite_files` in frontmatter. Replace inline tables with imperative references: "Read security_status.json for threshold and tag data."

**H2. No ESI failure handling**
- **File:** `SKILL.md`, entire file
- The skill requires `esi-characters.read_standings.v1` but provides no guidance for what to do when ESI is unavailable or the scope is missing. The response format example (lines 34-63) assumes the current sec status is known, but there's no fallback for when it can't be fetched.
- **Action:** Add a 3-line error handling block: "If ESI unavailable, ask the pilot for their current sec status and note that the value is self-reported."

### Medium Severity

**M1. "Practical Implications" section is generic advice (Pattern D adjacent)**
- **File:** `SKILL.md`, lines 180-199
- Three subsections (Trading, Logistics, Mission Running) with generic gameplay tips like "use alt for market operations" and "plan routes through low-sec." This is not actionable skill instruction -- it's encyclopedic content that Claude can infer from context.
- **Action:** **REMOVE** entirely.

**M2. Cost Calculation worked example is verbose**
- **File:** `SKILL.md`, lines 134-151
- 17 lines to express: "Fetch tag prices via MCP, compute ISK per sec point for each tag type, recommend the cheapest option first."
- **Action:** **CONSOLIDATE** to 3-line imperative instruction.

**M3. "The Downward Spiral" and "Living with Low Sec Status" are flavor text**
- **File:** `SKILL.md`, lines 165-179
- 15 lines of narrative content about the consequences of low sec status and how pirates live with it. Zero steering value for the skill's execution logic.
- **Action:** **REMOVE** both subsections.

### Low Severity

**L1. Integration table duplicates CLAUDE.md (Pattern B)**
- **File:** `SKILL.md`, lines 201-207
- Standard "suggest related commands" table.
- **Action:** **REMOVE**.

**L2. Response format example has RP-flavored closing line**
- **File:** `SKILL.md`, line 61
- "The toll for the life, Captain." appears in the response format. This is persona-specific framing that should come from an overlay, not the base skill.
- **Action:** **Remove** the RP line from the base template. If an overlay exists, it will add persona flavor.

## 5. Prioritized Recommendations

1. **Create** `reference/mechanics/security_status.json` with all static game data (thresholds, faction police, tags, sec loss values). Add to `prerequisite_files`. Replace inline tables with one-line imperative references. (High impact -- eliminates Pattern A, ~420 tokens)

2. **Add** ESI failure handling: ask pilot for self-reported sec status when ESI is unavailable. (High impact -- addresses a real execution gap)

3. **Remove** "Practical Implications" section (lines 180-199). (Medium impact -- ~120 tokens of generic advice)

4. **Remove** "The Downward Spiral" and "Living with Low Sec Status" (lines 165-179). (Medium impact -- ~150 tokens of flavor text)

5. **Consolidate** cost calculation example (lines 134-151) to 3-line imperative. (Medium impact -- ~120 tokens)

6. **Remove** Integration table (lines 201-207) and RP closing line (line 61). (Low impact -- ~60 tokens combined)
