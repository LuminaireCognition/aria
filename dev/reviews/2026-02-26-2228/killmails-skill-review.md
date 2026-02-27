# Skill Review: killmails

**Skill Path:** `.claude/skills/killmails/SKILL.md`
**Review Timestamp:** 2026-02-26-2228
**Files in skill directory:** `SKILL.md` (1 file, 310 lines)

---

## 1. Executive Summary

The killmails skill is a moderately bloated ESI-backed skill with two significant issues: (1) it uses legacy `PYTHONPATH=.claude/scripts uv run python -m aria_esi` command patterns (lines 26-48) instead of the standard `uv run aria-esi` CLI or MCP dispatchers, suggesting the skill predates the current CLI architecture, and (2) it inlines a substantial damage type reference table (lines 160-175, pattern A) that should be a prerequisite file. The experience-based adaptation section (lines 177-215) and three verbose response format templates consume the bulk of the remaining token budget.

---

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | :red_circle: | The skill makes no reference to MCP `killmails()` or `pilot()` dispatchers despite both being directly relevant. Uses legacy PYTHONPATH commands exclusively. CLAUDE.md maps `/killmails` to MCP but this skill doesn't reflect that. |
| Prompt hygiene | :yellow_circle: | Response templates are clear and well-structured. However, the damage type table (lines 160-175) is inlined reference data that could go stale, and the "What Damage Types Mean" section (lines 159-175) includes reference data that belongs in a prerequisite file. |
| Failure handling | :green_circle: | Store-not-initialized, ESI unavailable, no killmails found, and missing scope cases are all handled with clear recovery paths (lines 248-305). |
| Context window efficiency | :yellow_circle: | Three full response format templates (list, detailed analysis, pattern analysis) consume ~90 lines. Experience adaptation section adds ~40 lines of RP-variant examples. Damage type table and explanation consume ~50 lines. Total: ~180 lines of templates and reference data (~58% of file). |

---

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 26-48 | Legacy `PYTHONPATH=.claude/scripts uv run python -m aria_esi` commands -- should be replaced with MCP `killmails()` dispatcher calls as primary, with `uv run aria-esi` CLI as fallback | **CONSOLIDATE** | ~150 tokens |
| `SKILL.md` | 159-175 | "Damage Type Analysis" table and "What Damage Types Mean" -- inlined reference data (pattern A) that should be a prerequisite file like `reference/mechanics/npc_damage_types.md` or similar | **REMOVE** | ~150 tokens |
| `SKILL.md` | 167-175 | "Using Damage Analysis" subsection with example and action items -- tutorial prose (pattern D) explaining how to interpret damage breakdowns | **REMOVE** | ~80 tokens |
| `SKILL.md` | 177-204 | "Experience-Based Adaptation" section with 3 verbosity tiers for loss explanation and damage breakdown -- 27 lines of RP-variant examples; a 3-line instruction about adapting verbosity to experience level would suffice | **CONSOLIDATE** | ~200 tokens |
| `SKILL.md` | 122-153 | "Pattern Analysis" response format template -- 31-line ASCII block (pattern E) for a secondary feature | **CONSOLIDATE** | ~200 tokens |
| `SKILL.md` | 248-265 | "ESI Availability Check" block -- duplicates CLAUDE.md system behavior (pattern B) | **REMOVE** | ~150 tokens |
| `SKILL.md` | 228-239 | "Learning Integration" section -- proactive killmail-based warnings and fitting suggestions; useful concept but the two example blocks (lines 233-239, 241-245) could be a single imperative line each | **CONSOLIDATE** | ~80 tokens |
| `SKILL.md` | 281-293 | "No Killmails Found" block -- verbose explanation including NPC kill mechanics that don't add value | **CONSOLIDATE** | ~60 tokens |
| `SKILL.md` | 295-305 | "Missing Scope" error block -- duplicates setup instructions found elsewhere | **CONSOLIDATE** | ~60 tokens |
| `SKILL.md` | 307-309 | "Privacy Note" -- not needed; killmail privacy is not a skill concern | **REMOVE** | ~30 tokens |
| `SKILL.md` | 217-227 | "Contextual Suggestions" table -- standard pattern, could be compact | **CONSOLIDATE** | ~50 tokens |

**Total estimated savings: ~1,210 tokens (~39% of file)**

---

## 4. Specific Findings

### High Severity

**H1. No MCP integration despite dispatcher availability (lines 26-48)**
The skill exclusively uses legacy `PYTHONPATH=.claude/scripts uv run python -m aria_esi` commands, which is a pre-CLI pattern. CLAUDE.md's MCP fallback table explicitly maps `/killmails` queries to `killmails(action="query")`, `killmails(action="stats")`, and `killmails(action="recent")`. The skill should lead with MCP dispatcher calls:
- List kills/losses: `killmails(action="query", systems=[...])` or `killmails(action="recent")`
- Analyze specific: `killmails(action="analyze", killmail_input=<id>)`
- Pattern analysis: `killmails(action="stats", group_by="system")`

With `uv run aria-esi killmails` as the explicit CLI fallback.

**H2. Inlined damage type reference table (lines 159-175, pattern A)**
The "What Damage Types Mean" table maps damage types to common sources and tank priorities. This is static game data that belongs in a prerequisite file (e.g., `reference/mechanics/npc_damage_types.md`). Inlining it risks staleness and duplicates data available via SDE.

### Medium Severity

**M1. Experience adaptation examples are over-specified (lines 177-204)**
Three full example blocks (new, intermediate, veteran) for loss explanation, plus two more for damage breakdown. These consume ~27 lines. A single instruction -- "Adapt verbosity to the pilot's experience level: new players get explanations of what killmails are and damage type meanings; veterans get terse summaries" -- steers identically.

**M2. ESI availability check duplicates CLAUDE.md (lines 248-265, pattern B)**
Same boilerplate as every other ESI skill. System-level mechanism.

**M3. Pattern analysis template is oversized (lines 122-153, pattern E)**
31 lines of ASCII art for a pattern analysis response. Could be compressed to a 10-line template showing the key sections (breakdown, ships lost, dangerous systems, recommendations) without the full ASCII rendering.

### Low Severity

**L1. Learning Integration section is speculative (lines 228-239)**
The proactive warning and fitting suggestion concepts ("You lost a Venture in Tama 2 days ago") are good ideas but are presented as multi-line example blocks. Compress to imperative instructions.

**L2. Privacy note is unnecessary (lines 307-309)**
A brief note about killmail privacy doesn't affect output quality.

---

## 5. Prioritized Recommendations

1. **Modify** command section (lines 26-48) to use MCP `killmails()` dispatcher as primary, with standard `uv run aria-esi` CLI as fallback. Remove legacy PYTHONPATH commands entirely.
2. **Remove** inlined damage type table (lines 159-175) -- add `reference/mechanics/npc_damage_types.md` or equivalent as a `prerequisite_files` entry, or use `sde()` for runtime lookups.
3. **Remove** ESI availability check block (lines 248-265) -- system-level duplication.
4. **Consolidate** experience adaptation examples (lines 177-204) into a 3-line verbosity instruction.
5. **Consolidate** pattern analysis template (lines 122-153) into a compact 10-line version.
6. **Consolidate** learning integration examples (lines 228-239) into imperative one-liners.
7. **Remove** privacy note (lines 307-309).
8. **Consolidate** error handling blocks (lines 281-305) into compact descriptions.
