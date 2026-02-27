# Skill Review: killmail

**Skill Path:** `.claude/skills/killmail/SKILL.md`
**Review Timestamp:** 2026-02-26-2228
**Files in skill directory:** `SKILL.md` (1 file, 192 lines)

---

## 1. Executive Summary

The killmail skill is one of the better-structured skills in this batch, with clear MCP integration via `killmails(action="analyze")` and `sde(action="item_info")`. However, the skill still carries significant dead weight: a manual data flow with inline Python URL parsing (lines 84-98) and raw API curl examples (lines 101-131) that duplicate what the MCP `killmails(action="analyze")` dispatcher already handles, plus a threat cache integration section (lines 139-148) referencing Python imports that Claude cannot execute. The response format template is well-proportioned.

---

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | :yellow_circle: | Lines 134 and 38-43 reference both MCP (`sde(action="item_info")`) and CLI (`uv run aria-esi analyze-killmail`), but the primary data flow (lines 28-35) describes a manual fetch-parse-enrich pipeline. The skill should lead with `killmails(action="analyze")` as the single entry point, with CLI as fallback. |
| Prompt hygiene | :yellow_circle: | The response format (lines 47-78) is clean and well-structured. But the inline data flow (lines 28-35) describes 6 manual steps that the MCP dispatcher handles in one call, creating ambiguity about which path Claude should take. |
| Failure handling | :green_circle: | Kill-not-found and API error cases (lines 152-170) are clear and actionable. |
| Context window efficiency | :yellow_circle: | The Python URL parsing function (lines 84-98), curl API examples (lines 101-131), and threat cache import code (lines 139-148) consume ~100 lines for functionality already encapsulated in MCP tools. |

---

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 26-35 | "Data Flow" 6-step manual pipeline -- MCP `killmails(action="analyze")` handles all of this in one call | **CONSOLIDATE** | ~100 tokens |
| `SKILL.md` | 84-98 | Python URL parsing function -- MCP dispatcher accepts URLs, short URLs, and raw IDs natively; this code is dead weight | **REMOVE** | ~120 tokens |
| `SKILL.md` | 100-131 | "zKillboard API" and "ESI Killmail" curl examples with JSON response samples -- MCP handles fetching; Claude doesn't need to know the raw API structure | **REMOVE** | ~250 tokens |
| `SKILL.md` | 139-148 | "Threat Cache Integration" Python import block -- Claude cannot execute Python imports; the MCP response includes system context | **REMOVE** | ~80 tokens |
| `SKILL.md` | 172-180 | "Differences from /killmails" comparison table -- useful for disambiguation but could be 2 lines instead of a 7-row table | **CONSOLIDATE** | ~80 tokens |
| `SKILL.md` | 182-192 | "Related Commands" contextual suggestion table -- standard pattern, could be more compact | **CONSOLIDATE** | ~60 tokens |

**Total estimated savings: ~690 tokens (~36% of file)**

---

## 4. Specific Findings

### High Severity

**H1. Manual data flow pipeline contradicts MCP usage (lines 26-35)**
The "Data Flow" section describes a 6-step manual process (parse input, fetch zKillboard, fetch ESI, enrich with SDE, cross-reference threat cache, present). The MCP `killmails(action="analyze")` dispatcher handles steps 1-4 in a single call. The skill should state: "1. Call `killmails(action='analyze', killmail_input=<url_or_id>)`. 2. Enrich with `sde()` if needed. 3. Present." The current 6-step flow invites Claude to manually call curl endpoints.

**H2. Inline Python and curl examples are dead code (lines 84-148)**
65 lines of Python URL parsing, curl commands, JSON response examples, and Python import statements. None of this is executable by Claude. The MCP dispatcher abstracts all of it. Remove entirely.

### Medium Severity

**M1. CLI command section should be clearly labeled as fallback (lines 38-43)**
The CLI commands (`uv run aria-esi analyze-killmail`) are valid fallback when MCP is unavailable, but they appear before the response format, giving them equal prominence with MCP. Per CLAUDE.md's MCP fallback pattern, MCP should be primary with CLI clearly marked as fallback.

**M2. SDE enrichment instruction is vague (line 134)**
"Use `sde(action='item_info')` to resolve: Ship type ID -> Name, Module type IDs -> Names, System ID -> Name, security" -- the MCP `killmails(action="analyze")` response likely already includes resolved names. This instruction should be conditional: "If the MCP response contains unresolved type IDs, use `sde(action='item_info')` to resolve them."

### Low Severity

**L1. Differences table is useful but oversized (lines 172-180)**
The `/killmail` vs `/killmails` disambiguation is valuable but could be a 2-line note instead of a 7-row table.

---

## 5. Prioritized Recommendations

1. **Remove** Python URL parsing, curl examples, and threat cache import (lines 84-148) -- dead code that the MCP dispatcher replaces.
2. **Consolidate** data flow (lines 26-35) into a 3-step MCP-first flow: call `killmails(action="analyze")`, optionally enrich with `sde()`, present.
3. **Modify** CLI section (lines 38-43) to clearly label as "Fallback (if MCP unavailable)."
4. **Modify** SDE enrichment instruction (line 134) to be conditional on MCP response content.
5. **Consolidate** differences table (lines 172-180) into a 2-line disambiguation note.
6. **Consolidate** related commands table (lines 182-192) into compact text.
