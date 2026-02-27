# Skill Review: mail

**Path:** `.claude/skills/mail/SKILL.md`
**Timestamp:** 2026-02-26-2228
**File:** 301 lines, ~2,550 tokens

## 1. Executive Summary

The mail skill is well-structured with clear MCP integration (`pilot(action="mail_list")` / `pilot(action="mail_read")`) but is heavily bloated by three full JSON response structure examples (~70 lines) that document the API schema rather than steering Claude's behavior, plus two near-identical response format templates. The skill has no hallucination guard despite mail content being volatile data that must come from ESI. Approximately 40% of the file is API documentation that belongs in code, not in a prompt.

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | 🟡 | Lines 81-87 show MCP calls, but there is no explicit "MANDATORY" gate or hallucination guard. Claude is shown the API but not told "NEVER fabricate mail content." |
| Prompt hygiene | 🟡 | Implementation section (lines 79-87) is clear, but the three JSON schema blocks (lines 104-167) blur the line between "how to call" and "what the response looks like" — Claude doesn't need response schemas to present mail. |
| Failure handling | 🟢 | ESI unavailable (lines 47-77), ESI not configured (lines 244-258), missing scope (lines 260-273) — three distinct failure modes with user-actionable guidance. |
| Context window efficiency | 🔴 | ~70 lines of JSON response schemas, two full response format templates (standard + RP), and a separate mail body display template. Much of this is API documentation, not behavioral steering. |

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 104-167 | Three JSON response structure blocks (mail list, mail-read, empty response) | **REMOVE** — these are API response schemas. Claude receives the actual JSON at runtime; documenting the schema in the prompt is dead weight. | ~400 tokens |
| `SKILL.md` | 169-176 | "Recipient Types" table | **REMOVE** — static EVE reference data that Claude doesn't need in-prompt to present mail. The actual recipient types arrive in the JSON response. | ~40 tokens |
| `SKILL.md` | 19-25 | "ESI Write Capability" section | **REMOVE** — documents capabilities that are explicitly NOT implemented. "Send capability documented but not implemented" wastes tokens describing something the skill cannot do (Pattern D). | ~50 tokens |
| `SKILL.md` | 180-241 | Three response format templates (Standard, Formatted/RP, Mail Body) totaling ~60 lines | **CONSOLIDATE** — reduce to one template. The RP variant differs only in box-drawing; the standard variant is a markdown table. One example with a note about RP mode suffices. | ~300 tokens |
| `SKILL.md` | 89-102 | "Commands" and "Options" tables | **CONSOLIDATE** — these describe CLI commands (`mail`, `mail-read`, `mail-labels`) but the skill uses MCP (`pilot(action="mail_list")`). The CLI tables are a fallback reference, not the primary path. Reduce to a one-line fallback note. | ~80 tokens |
| `SKILL.md` | 275-277 | "MCP Policy" section | **REMOVE** — implementation detail about `reference/mcp-policy.json` that doesn't steer behavior. If MCP works, it works; if blocked, the error will surface. | ~30 tokens |
| `SKILL.md` | 36-37 | "ESI Requirement" section header + scope | **REMOVE** — duplicates frontmatter `esi_scopes` (line 14). The Missing Scope error handler already covers the failure case. | ~30 tokens |

**Total estimated savings: ~930 tokens (~36%)**

## 4. Specific Findings

### High Severity

**H1. Missing hallucination guard**
- **File:** `SKILL.md` (entire file)
- **Issue:** Unlike lp-store and mining-advisory, this skill has no explicit "NEVER fabricate mail content" or "every field must come from MCP" instruction. Mail content is volatile and entirely user-specific — there is zero chance Claude's training data contains correct mail. A hallucination guard is essential.
- **Action:** **ADD** a hallucination guard after line 87, similar to lp-store's pattern: "Every mail subject, sender, body, and timestamp MUST come from a `pilot()` call in this session. NEVER fabricate mail content."

**H2. JSON response schemas are dead weight (Pattern A-adjacent)**
- **File:** `SKILL.md`, lines 104-167
- **Issue:** Three full JSON blocks documenting the API response structure. Claude receives the actual JSON when the MCP tool returns. Documenting the schema in the prompt teaches Claude nothing it won't learn from the actual response. These 64 lines are pure noise.
- **Action:** **REMOVE** entirely.

### Medium Severity

**M1. ESI Write Capability section documents non-functionality (Pattern D)**
- **File:** `SKILL.md`, lines 19-25
- **Issue:** Documents that POST /mail/ and POST /mail/labels/ exist but are "not implemented due to abuse potential." This is justification prose for a design decision — it doesn't steer behavior.
- **Action:** **REMOVE**.

**M2. Verbose response format templates**
- **File:** `SKILL.md`, lines 180-241
- **Issue:** Three templates (standard markdown table, RP ASCII box, mail body display) occupy ~60 lines. The structural differences are minimal — RP mode adds box-drawing characters, standard mode uses a table. One template with a brief note is sufficient.
- **Action:** **CONSOLIDATE** to one template + variant note.

**M3. CLI command tables alongside MCP calls**
- **File:** `SKILL.md`, lines 89-102
- **Issue:** The "Commands" and "Options" tables document CLI usage (`mail`, `mail-read --unread --limit N`) but the Implementation section (lines 79-87) shows MCP calls. CLAUDE.md already handles MCP-to-CLI fallback. Including both in the skill is redundant.
- **Action:** **CONSOLIDATE** — keep MCP calls as primary, add one-line CLI fallback note.

### Low Severity

**L1. Cross-References table**
- **File:** `SKILL.md`, lines 287-292
- **Issue:** References `/contracts` and `/pilot` as related commands. Low token cost, marginal steering value.
- **Action:** Keep (low cost).

**L2. Data Volatility section restates general principle**
- **File:** `SKILL.md`, lines 28-33
- **Issue:** "Mail data is volatile — changes frequently" is true but CLAUDE.md already covers data volatility protocols. The specific instruction to "Display query timestamp" is the only unique value.
- **Action:** **CONSOLIDATE** to one line: "Display query timestamp — mail data is volatile."

## 5. Prioritized Recommendations

1. **ADD** explicit hallucination guard after line 87 — critical missing protection for volatile user-specific data.
2. **REMOVE** JSON response structure blocks (lines 104-167) — 64 lines of API documentation that Claude doesn't need. (~400 tokens)
3. **CONSOLIDATE** three response format templates (lines 180-241) into one with variant note. (~300 tokens)
4. **REMOVE** ESI Write Capability section (lines 19-25) — documents non-functionality. (~50 tokens)
5. **CONSOLIDATE** CLI command tables (lines 89-102) — MCP is the primary path; CLI is a one-line fallback. (~80 tokens)
6. **REMOVE** JSON Recipient Types table (lines 169-176). (~40 tokens)
7. **REMOVE** MCP Policy section (lines 275-277). (~30 tokens)
