# Skill Review: watchlist

**Path:** `.claude/skills/watchlist/SKILL.md`
**Review timestamp:** 2026-02-26-2228
**Size:** 228 lines, ~1,680 tokens

## 1. Executive Summary

The watchlist skill is the leanest in this batch and reasonably well-structured. It correctly uses MCP `sde(action="resolve_names")` for entity resolution before CLI operations. The main issues are the pattern B "Persona Adaptation" boilerplate at the end, a verbose "Integration with Threat Assessment" section that duplicates content owned by the threat-assessment skill, and response format examples that could be consolidated. Total savings are modest (~300 tokens, ~18%) reflecting the skill's already-compact size.

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | 🟢 | Entity resolution via `sde(action="resolve_names")` before CLI operations. Clear workflow: resolve name to ID, then pass ID to CLI. |
| Prompt hygiene | 🟢 | Explicit separation of MCP (name resolution) and CLI (CRUD operations). The "MCP unavailable fallback" note (line 162) is honest about limitations. |
| Failure handling | 🟡 | MCP unavailable fallback (line 162) says "ask the pilot for the entity ID directly" — reasonable. But no handling for CLI command failures (e.g., watchlist-add fails, watchlist not found). |
| Context window efficiency | 🟡 | Relatively lean already. The Integration with Threat Assessment section (lines 166-181) duplicates content that belongs in threat-assessment. Persona Adaptation (lines 220-228) is boilerplate. |

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 220-228 | "Persona Adaptation" section — standard overlay boilerplate handled by skill loader | **REMOVE** (pattern B) | ~50 tokens |
| `SKILL.md` | 166-181 | "Integration with Threat Assessment" — 16 lines describing how watched entities appear in other skills. This is owned by the consuming skills (threat-assessment, gatecamp), not by the watchlist skill itself. | **REMOVE** (pattern C inverted — cross-skill behavior described in wrong skill) | ~100 tokens |
| `SKILL.md` | 82-144 | Response format examples — three full ASCII-box examples (list watchlists, show watchlist, war sync result). Two would suffice. | **CONSOLIDATE** — remove the War Sync Result example (lines 127-144); it's a minor variant of the list format | ~80 tokens |
| `SKILL.md` | 183-198 | "War Target Synchronization" details — ESI scope, sync schedule, implementation details. The CLI command at line 64 already covers invocation. | **CONSOLIDATE** — keep just the scope requirement and "sync on demand or every 4 hours" | ~80 tokens |

**Total estimated savings:** ~310 tokens (~18%)

## 4. Specific Findings

### Medium Severity

**M1. Cross-skill behavior described in wrong skill** (lines 166-181)
The "Integration with Threat Assessment" section describes how watched entity kills appear in `/threat-assessment` and `/gatecamp` responses. This is behavior owned by those skills, not by the watchlist skill. The threat-assessment skill already has its own "Watched Entity Activity Integration" section (threat-assessment SKILL.md lines 174-225).
**Action:** REMOVE. The watchlist skill should document watchlist CRUD and entity resolution. How other skills consume watchlist data is those skills' responsibility.

**M2. Pattern B: Persona Adaptation boilerplate** (lines 220-228)
Standard 9-line section about loading persona overlays. The `has_persona_overlay: true` frontmatter flag and the skill loader handle this automatically.
**Action:** REMOVE.

### Low Severity

**L1. War Sync Result response example** (lines 127-144)
A 18-line ASCII box for war sync results. The format pattern is already established by the List Watchlists example (lines 82-98) and Show Watchlist example (lines 102-125). The sync result is a minor variant.
**Action:** REMOVE. Claude can derive the sync result format from the list/show patterns.

**L2. War Target Synchronization implementation details** (lines 183-198)
Includes ESI scope, sync schedule ("every 4 hours"), and poller startup behavior. The sync schedule is a poller implementation detail that doesn't affect how Claude invokes the command.
**Action:** CONSOLIDATE. Keep: "Requires `esi-wars.read_wars.v1`. Auto-syncs every 4 hours when poller active, or on demand via `/watchlist sync-wars`." Remove the rest.

**L3. No error handling section**
Unlike other skills in this batch, watchlist has no error handling section for common failure modes (entity not found, watchlist name collision, empty watchlist).
**Action:** ADD a brief error handling table covering: entity not resolvable, watchlist not found, duplicate entity.

## 5. Prioritized Recommendations

1. **REMOVE** "Integration with Threat Assessment" section (lines 166-181) — cross-skill behavior that belongs in consuming skills, ~100 tokens. *(remove)*
2. **REMOVE** "Persona Adaptation" boilerplate (lines 220-228) — pattern B, ~50 tokens. *(remove)*
3. **CONSOLIDATE** War Target Synchronization (lines 183-198) — keep essential facts, remove implementation details. *(modify)*
4. **REMOVE** War Sync Result response example (lines 127-144) — derivable from other examples. *(remove)*
5. **ADD** brief error handling table (3-4 rows) for common CLI failure modes. *(add)*
