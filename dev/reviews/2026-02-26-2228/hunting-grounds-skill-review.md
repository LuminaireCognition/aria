# Skill Review: hunting-grounds

**Skill path:** `.claude/skills/hunting-grounds/SKILL.md`
**Review timestamp:** 2026-02-26-2228
**File stats:** 322 lines, ~3,100 tokens

## 1. Executive Summary

The hunting-grounds skill has the strongest MCP-first discipline of this batch, with explicit hallucination guards (lines 39-41), field-to-source mapping tables (lines 44-57), and anti-pattern examples (lines 307-315). However, it still carries ~800 tokens of static reference data (traffic thresholds, coalition response tables, system type taxonomies) that risks overriding MCP-derived analysis. The coalition intelligence section (lines 162-230) is disproportionately large for a feature that depends on an optional data source, and several sections duplicate each other.

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | :green_circle: | Lines 29-31 state "Every activity metric MUST come from a tool call." Lines 39-41 provide an explicit hallucination guard. Anti-pattern examples at lines 307-315 are concrete and useful. |
| Prompt hygiene | :green_circle: | Field-to-source mapping table (lines 44-57) is exceptionally clear. Each output field is traced to a specific MCP call. The `Derived` entries correctly note when inference is allowed. |
| Failure handling | :yellow_circle: | Line 173 handles `coalition_not_found` gracefully. But there's no explicit degraded-mode instruction for when `hotspots` or `activity` calls fail entirely (e.g., MCP server down). |
| Context window efficiency | :yellow_circle: | Static reference tables (lines 104-131, 175-184), coalition intelligence section (lines 162-230), and system type taxonomy (lines 133-160) consume ~800 tokens. Some provide useful thresholds; others are static game knowledge. |

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 175-184 | "Coalition Response Analysis" table — static game knowledge mapping coalitions to response patterns; risks becoming stale as coalitions change; not sourced from MCP | REMOVE | ~80 tokens |
| `SKILL.md` | 186-193 | "Renter Space Identification" section — heuristics for identifying renter space; this is inference guidance, not MCP data | CONSOLIDATE | ~50 tokens |
| `SKILL.md` | 195-205 | "Entry Point Analysis" section — describes using `universe(action="borders")` for entry points; this duplicates the tool call table at line 36 | REMOVE | ~60 tokens |
| `SKILL.md` | 207-218 | "Sovereignty Response Block" example format — a worked example of sov data in the response; the main response format (lines 69-99) already covers this | REMOVE | ~70 tokens |
| `SKILL.md` | 220-230 | "Coalition Staging Systems" section — says "use territory_analysis to identify concentration"; already in the tool call table at line 37 | REMOVE | ~60 tokens |
| `SKILL.md` | 133-160 | "System Type Analysis" section (Low-Sec Entry Points, Chokepoint Systems, Dead-End Pockets, Mission Hubs) — static game taxonomy; Claude knows this without a 28-line reference, and MCP provides the actual system data | REMOVE | ~180 tokens |
| `SKILL.md` | 232-260 | "Regional Analysis" section with full response format — the main response format at lines 69-99 already covers single-system analysis; this adds a "regional" variant that is structurally identical | CONSOLIDATE | ~150 tokens |
| `SKILL.md` | 262-268 | "Faction Warfare Considerations" — 7 lines of generic bullet points ("note militia presence", "blob risk from fleets") without MCP grounding | REMOVE | ~40 tokens |
| `SKILL.md` | 270-276 | "Time-Based Patterns" — generic advice about peak hours; not grounded in any data | REMOVE | ~40 tokens |
| `SKILL.md` | 278-283 | "Integration with Other Skills" — generic cross-references | REMOVE | ~40 tokens |
| `SKILL.md` | 44-57 | "Field -> Source Mapping" table — excellent grounding aid, BUT overlaps significantly with the "Required Tool Calls" table at lines 32-38; the two could be merged | CONSOLIDATE | ~80 tokens |
| `SKILL.md` | 317-322 | "DO NOT" section — generic ethical guardrails (no player names, no harassment) that belong in CLAUDE.md's system rules, not a skill file | REMOVE | ~40 tokens |

**Total estimated savings:** ~890 tokens (~29%)

## 4. Specific Findings

### High Severity

**H1. "Coalition Response Analysis" table is static, unsourced, and perishable (Pattern A)**
- **File:** `SKILL.md`, lines 175-184
- Maps specific coalition names (Imperium, PanFam, FIRE) to response characteristics and hunting viability. This data is not from MCP; it's inlined game knowledge that will become stale as the political landscape shifts. The `territory_analysis` MCP tool provides actual coalition data.
- **Action:** REMOVE. Replace with: "Use `territory_analysis` response to assess defense posture. Larger coalitions with more systems in a region indicate stronger defense."

**H2. "System Type Analysis" is static game taxonomy Claude already knows**
- **File:** `SKILL.md`, lines 133-160
- Four sub-sections (Low-Sec Entry Points, Chokepoint Systems, Dead-End Pockets, Mission Hubs) totaling 28 lines of generic EVE geography knowledge. Names specific systems (Tama, Rancer, Amamake, Huola) without MCP grounding.
- **Action:** REMOVE. The MCP `hotspots` and `borders` tools provide actual system data. Claude can classify systems based on MCP-returned topology.

### Medium Severity

**M1. Two tool-call reference tables overlap (Pattern G)**
- **File:** `SKILL.md`, lines 32-38 ("Required Tool Calls") and lines 44-57 ("Field -> Source Mapping")
- Both tables map output fields to MCP tool calls. The first is organized by query type; the second by output field. The field-source mapping is more precise and subsumes the first.
- **Action:** CONSOLIDATE into a single table. Keep the field-source mapping (lines 44-57) as it's more granular; merge the query-type context into it.

**M2. Coalition Intelligence section is disproportionately large**
- **File:** `SKILL.md`, lines 162-230
- 68 lines (~500 tokens) dedicated to null-sec coalition hunting. This is a niche use case that dominates the skill. Multiple sub-sections (Response Analysis, Renter Space, Entry Points, Staging Systems) each reference the same MCP calls already listed in the tool table.
- **Action:** CONSOLIDATE to ~15 lines: the two key MCP calls (`systems` for sov, `territory_analysis` for coalition intel), the graceful fallback note, and a brief assessment framework.

**M3. Regional Analysis response format duplicates main format**
- **File:** `SKILL.md`, lines 232-260
- A "REGIONAL HUNTING BRIEF" format that is structurally identical to the main response format (lines 69-99) but with multiple systems listed. One format with a note "for multiple systems, repeat the system block" suffices.
- **Action:** CONSOLIDATE into the main response format.

**M4. No explicit MCP failure handling**
- **File:** `SKILL.md` (missing)
- The skill handles `coalition_not_found` gracefully (line 173) but has no instruction for when `hotspots` or `activity` calls fail entirely. Given this is a tactical skill, total MCP failure should produce a clear "cannot provide hunting ground analysis without live data" message.
- **Action:** Add 2-3 lines of MCP failure handling after the tool call table.

### Low Severity

**L1. "DO NOT" section contains system-level rules (Pattern B)**
- **File:** `SKILL.md`, lines 317-322
- "Do not provide real player names", "do not encourage harassment" — these are system-level ethical guardrails that apply to all Claude interactions, not hunting-grounds-specific behavior.
- **Action:** REMOVE. These belong in CLAUDE.md (if not already there).

**L2. Generic advice sections lack MCP grounding**
- **File:** `SKILL.md`, lines 262-268 ("Faction Warfare"), 270-276 ("Time-Based Patterns")
- Brief bullet lists of generic PvP advice not tied to any data source.
- **Action:** REMOVE. FW data comes from `universe(action="fw_frontlines")`; if needed, add a tool call for it. Time patterns are not queryable.

**L3. Anti-pattern examples are good but could be shorter**
- **File:** `SKILL.md`, lines 307-315
- Three good anti-pattern examples, each with a wrong/right pair. These are the most effective grounding aids in the skill. Keep, but consider compressing slightly.
- **Action:** Keep as-is. Good token-to-steering ratio.

## 5. Prioritized Recommendations

1. **REMOVE** "Coalition Response Analysis" table (lines 175-184) — static, perishable, unsourced. [remove]
2. **REMOVE** "System Type Analysis" section (lines 133-160) — static taxonomy Claude already knows; MCP provides actual data. [remove]
3. **CONSOLIDATE** Coalition Intelligence section (lines 162-230) from 68 lines to ~15 lines. [modify]
4. **CONSOLIDATE** the two tool-call reference tables (lines 32-38 and 44-57) into one. [modify]
5. **CONSOLIDATE** Regional Analysis format (lines 232-260) into the main response format. [modify]
6. **REMOVE** generic advice sections: FW (lines 262-268), Time Patterns (lines 270-276), Cross-References (lines 278-283). [remove]
7. **REMOVE** "DO NOT" section (lines 317-322) — system-level rules belong in CLAUDE.md. [remove]
8. **Add** MCP failure handling (2-3 lines) for when activity/hotspot calls fail entirely. [add]
