# Skill Review: escape-route

**Skill path:** `.claude/skills/escape-route/SKILL.md`
**Review timestamp:** 2026-02-26-2228
**File size:** 8,410 bytes (~2,100 tokens)

## 1. Executive Summary

The escape-route skill is the strongest of the five reviewed in terms of MCP grounding discipline. It has explicit hallucination guards, a field-to-source mapping table, and anti-pattern examples. However, it carries ~800 tokens of inlined game reference data (security status access table, NPC null regions, gate camp detection, evasion tactics) that are either static data better placed in reference files or general EVE gameplay advice that does not steer MCP usage.

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | :green_circle: | Excellent. Lines 31-43 mandate MCP calls for every route and destination. The hallucination guard (line 43) is explicit: "NEVER name systems from training data memory." Anti-patterns (lines 221-230) reinforce this with concrete wrong/right examples. |
| Prompt hygiene | :green_circle: | Field-to-source mapping table (lines 47-56) is exemplary — each output field has a required source and specific tool call. No ambiguity about what comes from MCP vs inference. |
| Failure handling | :yellow_circle: | The "if you cannot make the route call, say so" guardrail (line 43) is good. But there is no explicit handling for when `universe(action="nearest")` returns no results (e.g., no NPC null stations within range). |
| Context window efficiency | :yellow_circle: | The MCP grounding sections are well-justified. The fat is in the game mechanic reference sections: security status access table, NPC null regions, escape considerations, gate camp detection, and pursuit evasion. |

## 3. Reduction Inventory

| File | Lines | What | Action | Est. Token Savings |
|------|-------|------|--------|-------------------|
| SKILL.md | 88-108 | Safe Harbor Types: Security Status Access table + Station Types table | REMOVE | ~200 tokens. Pattern A — this is static game reference data. The security-status-to-access mapping is complex and error-prone if hardcoded. Either move to `reference/mechanics/security_access.json` or remove — the skill's job is to find routes, not to teach security mechanics. |
| SKILL.md | 110-121 | NPC Null Regions table | REMOVE | ~100 tokens. Pattern A — static reference data. `universe(action="nearest")` already finds NPC null stations dynamically. This hardcoded list could become stale. |
| SKILL.md | 123-148 | Escape Considerations: Immediate Escape + Pursuit Evasion | REMOVE | ~200 tokens. This is general EVE gameplay advice (align, overheat MWD, use tacticals, log off). It does not steer MCP tool usage or response formatting. A pilot who needs `/escape-route` needs a route, not a combat tutorial. |
| SKILL.md | 150-165 | Route Planning Intelligence: Gate Camp Detection + Known camp systems list | REMOVE | ~130 tokens. Pattern A — hardcoded system names (Rancer, Amamake, Tama, HED-GP, EC-P8R) from training data. The `universe(action="gatecamp_risk")` and `universe(action="activity")` tools provide live data. Static camp lists contradict the MCP-first principle. |
| SKILL.md | 159-165 | Alternative Routes section | CONSOLIDATE | ~60 tokens. Four bullet points of generic advice. Reduce to one sentence: "If primary route is camped, suggest wormholes, adjacent regions, or jump clones." |
| SKILL.md | 167-176 | Integration with ESI section | REMOVE | ~70 tokens. States obvious facts about ESI location scope. The command syntax (lines 24-25) already covers this with/without ESI cases. |
| SKILL.md | 204-210 | Integration with Other Skills table | REMOVE | ~50 tokens. Generic cross-references handled by CLAUDE.md command suggestion system. |

**Total estimated savings: ~810 tokens (~39% reduction)**

## 4. Specific Findings

### High Severity

**H1. Hardcoded gate camp system names contradict MCP-first principle**
- File: `SKILL.md`, lines 154-157
- "Known camp systems: Rancer, Amamake, Tama, HED-GP, EC-P8R" — these are training data, not MCP-sourced. The skill's own anti-patterns section (lines 229-230) says "Every system name must trace to a tool call response." Yet this section names systems from memory.
- **Action:** REMOVE. Use `universe(action="gatecamp_risk")` and `universe(action="activity")` for live gate camp data.

### Medium Severity

**M1. Security status access table is inlined reference data (Pattern A)**
- File: `SKILL.md`, lines 88-108
- A complex table mapping security status ranges to high-sec/low-sec/null access. This is game reference data that could drift with game changes.
- **Action:** REMOVE. If needed for correct routing, extract to `reference/mechanics/security_access.json` and add to `data_sources`.

**M2. NPC Null Regions table is inlined reference data (Pattern A)**
- File: `SKILL.md`, lines 110-121
- Six regions with faction associations. `universe(action="nearest")` finds these dynamically.
- **Action:** REMOVE. The MCP tool makes this list redundant.

**M3. Escape Considerations section is gameplay tutorial, not steering**
- File: `SKILL.md`, lines 123-148
- "Align to celestial," "Overheat MWD," "Check D-scan," "Log off in space" — none of these steer MCP calls or response formatting. This is general combat advice.
- **Action:** REMOVE. The skill's purpose is route planning, not combat instruction.

**M4. Missing failure handling for empty `nearest` results**
- No instruction for what to do when `universe(action="nearest")` returns no systems matching the security filter (e.g., pilot is deep in null-sec and `nearest` with `security_min=0.5` returns nothing within range).
- **Action:** ADD a one-line instruction: "If `nearest` returns no results, increase `max_jumps` to 50 and retry. If still empty, report 'No safe harbor found within range.'"

### Low Severity

**L1. Integration with ESI restates the obvious**
- File: `SKILL.md`, lines 167-176
- "With ESI location scope: Auto-detect current system" — this is already implied by the command syntax and the `esi_scopes` frontmatter.
- **Action:** REMOVE.

**L2. Integration with Other Skills table is generic**
- File: `SKILL.md`, lines 204-210
- **Action:** REMOVE.

**L3. Emergency Protocol response templates could be tighter**
- File: `SKILL.md`, lines 178-202
- "I'm Tackled" and "They're Following" templates are appropriately brief but could share a common structure.
- **Action:** CONSOLIDATE to save ~30 tokens. Low priority.

## 5. Prioritized Recommendations

1. **REMOVE** hardcoded gate camp system names (lines 150-165). Contradicts MCP-first and the skill's own anti-patterns. (~130 tokens)
2. **REMOVE** Escape Considerations gameplay tutorial (lines 123-148). Not steering. (~200 tokens)
3. **REMOVE** NPC Null Regions table (lines 110-121). MCP `nearest` makes it redundant. (~100 tokens)
4. **REMOVE** Security Status Access table (lines 88-108). Inlined reference data. (~200 tokens)
5. **ADD** failure handling for empty `nearest` results.
6. **REMOVE** Integration with ESI (lines 167-176) and Integration with Other Skills (lines 204-210). (~120 tokens)
7. **CONSOLIDATE** Alternative Routes to one sentence (lines 159-165). (~40 tokens)
