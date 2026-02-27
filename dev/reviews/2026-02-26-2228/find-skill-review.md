# Skill Review: find

**Skill path:** `.claude/skills/find/SKILL.md`
**Review timestamp:** 2026-02-26-2228
**Files reviewed:** 1 (SKILL.md only, 250 lines, ~1,959 tokens)

## 1. Executive Summary

The find skill is well-structured with good MCP-first discipline and a useful NPC fallback pattern. Its main issues are an outdated MCP tool reference (line 75 references `market_find_nearby` as a standalone tool rather than the unified `market(action="find_nearby")` dispatcher), verbose response format examples consuming ~300 tokens, and a trailing Persona Adaptation section that duplicates CLAUDE.md's skill-loading mechanism. The skill would benefit from trimming examples and removing the stale MCP reference block.

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | 🟢 | Clear MCP tool usage pattern. NPC fallback from `find_nearby` to `npc_sources` is well-documented (lines 57-71). |
| Prompt hygiene | 🟢 | Smart defaults table (lines 45-55) clearly maps item categories to filter behavior. No ambiguity about data sources. |
| Failure handling | 🟢 | No-results template (lines 138-151) with actionable suggestions. Error handling for item/system not found (lines 153-174). |
| Context window efficiency | 🟡 | Three response format examples (lines 93-151) are verbose. MCP Tool section (lines 73-88) duplicates dispatcher documentation. Persona Adaptation section duplicates CLAUDE.md. |

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 73-88 | "MCP Tool" section -- documents `market_find_nearby` with stale standalone syntax. The dispatcher is already documented in CLAUDE.md and the skill uses `market(action="find_nearby")` elsewhere | REMOVE (Pattern B) | ~130 tokens |
| `SKILL.md` | 115-135 | "NPC Blueprint Search" response example -- second full example showing null-sec BPO scenario. One example is sufficient | REMOVE | ~120 tokens |
| `SKILL.md` | 153-174 | "Error Handling" JSON examples -- two JSON blocks showing error responses. Claude doesn't need to see error JSON format; it should handle errors naturally | REMOVE | ~120 tokens |
| `SKILL.md` | 176-202 | "Experience-Based Adaptation" section -- 27 lines showing new-player vs veteran formatting. This is a cross-cutting concern handled by CLAUDE.md's experience adaptation protocol | REMOVE (Pattern B) | ~150 tokens |
| `SKILL.md` | 240-250 | "Persona Adaptation" section -- duplicates CLAUDE.md's skill-loading overlay mechanism | REMOVE (Pattern B) | ~60 tokens |
| `SKILL.md` | 204-212 | "Self-Sufficiency Integration" section -- pilot playstyle adaptation is a cross-cutting concern, and the specific behavior (prefer NPC sources) is already in Smart Defaults | CONSOLIDATE | ~60 tokens |
| `SKILL.md` | 225-231 | "Behavior Notes" section -- 5 bullets describing MCP tool internals (BFS, anomaly detection) that don't steer output | REMOVE | ~60 tokens |

**Total estimated savings: ~700 tokens (~36%)**

## 4. Specific Findings

### High Severity

**H1. Stale MCP tool reference (Pattern B / vestigial)**
- `SKILL.md` lines 73-88: Documents `market_find_nearby(...)` as a standalone function call with 8 named parameters
- CLAUDE.md already documents `market(action="find_nearby", ...)` as the unified dispatcher pattern
- The skill itself uses the correct dispatcher syntax in lines 57-71 (fallback pattern), making this section both stale and self-contradictory

**Fix:** Delete lines 73-88 entirely. The dispatcher pattern is already shown in the fallback section.

**H2. Experience-Based Adaptation section duplicates CLAUDE.md (Pattern B)**
- `SKILL.md` lines 176-202: Shows new-player vs veteran response formatting
- CLAUDE.md's "Experience Adaptation" protocol (referenced at `dev/docs/ai-runtime/EXPERIENCE_ADAPTATION.md`) handles this cross-cutting concern
- 27 lines of examples that don't add skill-specific value

### Medium Severity

**M1. Three response format examples where one suffices**
- `SKILL.md` lines 93-151: Standard results (22 lines), NPC Blueprint Search (21 lines), No Results (14 lines)
- The Standard Results example adequately demonstrates the format. The NPC example is a minor variation. The No Results case could be a 3-line instruction.

**M2. Error handling JSON blocks are not useful**
- `SKILL.md` lines 153-174: Shows JSON error payloads from the MCP tool
- Claude doesn't need to see the JSON format of errors -- it will see them live. The important instruction is "suggest spelling corrections" which can be stated in one line.

### Low Severity

**L1. Persona Adaptation section is pure CLAUDE.md duplication**
- `SKILL.md` lines 240-250: Explains overlay loading. This is exactly the skill-loading mechanism defined in CLAUDE.md.

**L2. Behavior Notes describe MCP internals**
- `SKILL.md` lines 225-231: "NPC Detection: Orders with duration >= 364 days", "Distance Calculation: Uses bounded BFS"
- These describe tool internals, not skill behavior. Claude doesn't need to know the algorithm.

## 5. Prioritized Recommendations

1. **REMOVE** the "MCP Tool" section (lines 73-88). It uses stale syntax and contradicts the fallback section above it. (~130 tokens saved)

2. **REMOVE** the "Experience-Based Adaptation" section (lines 176-202). Defer to CLAUDE.md's experience protocol. (~150 tokens saved)

3. **REMOVE** the NPC Blueprint Search example (lines 115-135). One example suffices. (~120 tokens saved)

4. **REMOVE** the error handling JSON blocks (lines 153-174). Replace with one-line instruction: "On item/system not found, suggest corrections based on fuzzy match suggestions from the tool." (~120 tokens saved)

5. **REMOVE** the Persona Adaptation section (lines 240-250). CLAUDE.md handles overlay loading. (~60 tokens saved)

6. **REMOVE** the Behavior Notes section (lines 225-231). Tool internals don't steer output. (~60 tokens saved)

7. **Modify** the Self-Sufficiency Integration section (lines 204-212) to a single line: "For pilots with `market_trading: false`, prefer NPC sources over distant trade hubs."
