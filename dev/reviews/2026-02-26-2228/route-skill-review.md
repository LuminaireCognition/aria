# Skill Review: route

**Skill path:** `.claude/skills/route/SKILL.md`
**Review timestamp:** 2026-02-26-2228
**Files reviewed:** `SKILL.md` (411 lines, single file)

---

## 1. Executive Summary

The route skill is one of the largest at 411 lines, driven primarily by three verbose response format templates (standard, RP, gatecamp-with-warning) that together consume ~100 lines of ASCII-boxed examples. Grounding discipline is solid -- MCP calls are clearly specified, bulk-call requirements are enforced, and real-time gatecamp integration is well-documented. The main reduction opportunity is consolidating the three response format examples into a single annotated template, and removing the JSON output format section (lines 329-359) which duplicates MCP response structure that Claude already receives.

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | :green_circle: | Lines 43-47 mandate live activity data fetch. Lines 58-64 enforce single bulk call with "CRITICAL" label. Line 210-212 shows `gatecamp_risk` action. All route data comes from `universe(action="route")`. |
| Prompt hygiene | :green_circle: | Clear separation between MCP-sourced data (route, activity, gatecamp) and presentation logic. Lines 63-64 explicitly forbid per-system fetching. No ambiguous language that would allow training-data recall. |
| Failure handling | :green_circle: | Lines 249-280 cover system-not-found, no-route, and same-system errors with example responses. Fuzzy matching is mentioned (line 378). |
| Context window efficiency | :yellow_circle: | Three full response format examples (lines 100-185) are ~85 lines where one annotated template would suffice. JSON output format (lines 329-359) duplicates MCP response structure. The persona adaptation section (lines 401-411) duplicates CLAUDE.md skill loading mechanism. |

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 122-152 | "Formatted Response (rp_level: moderate or full)" -- 30-line ASCII-boxed template | **CONSOLIDATE** -- merge into the standard response format as annotation ("When RP is active, use box-drawing frame") | ~200 tokens |
| `SKILL.md` | 154-185 | "Formatted Response with Gatecamp Warning" -- 31-line ASCII-boxed template nearly identical to lines 122-152 with a warning block prepended | **CONSOLIDATE** -- show only the delta (the warning block) as an addendum to the base template | ~200 tokens |
| `SKILL.md` | 329-359 | "JSON Output Format" section -- 30-line JSON example of route response structure | **REMOVE** -- Claude already receives this structure from `universe(action="route")`. This section teaches Claude what it already gets from MCP. | ~200 tokens |
| `SKILL.md` | 401-411 | "Persona Adaptation" section explaining overlay loading | **REMOVE** -- duplicates CLAUDE.md skill loading mechanism (Pattern B). The overlay path is already defined in the skill loading system. | ~60 tokens |
| `SKILL.md` | 283-306 | "Experience-Based Adaptation" section with new player and veteran examples | **CONSOLIDATE** -- reduce to 5-line guidance ("New players: explain security concepts. Veterans: compact one-line format.") instead of two full output examples | ~150 tokens |
| `SKILL.md` | 363-371 | "Contextual Suggestions" table | **REMOVE** -- CLAUDE.md command suggestion protocol handles this (Pattern B) | ~60 tokens |
| `SKILL.md` | 373-380 | "Behavior Notes" bullet list (7 items, mostly obvious like "fuzzy matching" and "wormhole systems have no routes") | **CONSOLIDATE** -- keep only Pochven warning (line 379) which is non-obvious | ~50 tokens |
| `SKILL.md` | 382-391 | "Integration with Threat Assessment" section with example output | **REMOVE** -- already covered by contextual suggestions and the gatecamp_risk section (lines 206-226) | ~70 tokens |

**Estimated total savings:** ~990 tokens (~24% of file)

## 4. Specific Findings

### High Severity

**H1. Three near-identical response format templates (Pattern G)**
- **File:** `SKILL.md`, lines 100-185
- Three templates: standard (lines 100-121), RP (lines 122-152), and RP-with-gatecamp (lines 154-185). The RP template is the standard template with box-drawing characters. The gatecamp template is the RP template with a warning block prepended. Together they consume ~85 lines for content that could be expressed as: "Base template + RP: use box-drawing frame + Gatecamp: prepend warning block."
- **Action:** Keep the standard response template. Add 3-line annotations for RP framing and gatecamp warning block. **CONSOLIDATE** from ~85 to ~35 lines.

**H2. JSON Output Format section duplicates MCP response (Pattern A adjacent)**
- **File:** `SKILL.md`, lines 329-359
- This 30-line JSON block teaches Claude the structure of the route response. But Claude receives this exact structure from `universe(action="route")` -- there is no need to teach it what the response looks like.
- **Action:** **REMOVE** entirely.

### Medium Severity

**M1. Experience adaptation examples are verbose**
- **File:** `SKILL.md`, lines 283-306
- Two full output examples (new player: 10 lines, veteran: 3 lines) to communicate "adapt verbosity to experience level." A 5-line instruction would steer identically.
- **Action:** **CONSOLIDATE** to concise instruction.

**M2. Persona Adaptation section duplicates CLAUDE.md (Pattern B)**
- **File:** `SKILL.md`, lines 401-411
- Explains overlay loading which is already handled by the skill loading mechanism in CLAUDE.md.
- **Action:** **REMOVE**.

### Low Severity

**L1. Contextual Suggestions table (Pattern B)**
- **File:** `SKILL.md`, lines 363-371
- CLAUDE.md command suggestion protocol already covers when to suggest related commands.
- **Action:** **REMOVE**.

**L2. Behavior Notes section mostly redundant**
- **File:** `SKILL.md`, lines 373-380
- Seven bullet points, most of which are obvious ("No Auth Required: Route calculation is a public endpoint") or already stated elsewhere. Only Pochven connectivity (line 379) adds unique value.
- **Action:** **CONSOLIDATE** to Pochven note only.

**L3. Integration with Threat Assessment section (Pattern G)**
- **File:** `SKILL.md`, lines 382-391
- Already covered by the gatecamp analysis section (lines 206-226) and the contextual suggestions table.
- **Action:** **REMOVE**.

## 5. Prioritized Recommendations

1. **Consolidate** three response format templates (lines 100-185) into one annotated template with RP and gatecamp deltas noted inline. (High impact -- ~400 tokens saved, eliminates Pattern G)

2. **Remove** JSON Output Format section (lines 329-359). Claude receives this structure from MCP and does not need it taught. (High impact -- ~200 tokens)

3. **Consolidate** experience adaptation examples (lines 283-306) to a 5-line instruction. (Medium impact -- ~150 tokens)

4. **Remove** Persona Adaptation section (lines 401-411), Contextual Suggestions table (lines 363-371), and Integration with Threat Assessment (lines 382-391). All duplicate CLAUDE.md behaviors or other sections of this file. (Medium impact -- ~190 tokens combined)

5. **Consolidate** Behavior Notes (lines 373-380) to retain only the Pochven warning. (Low impact -- ~50 tokens)
