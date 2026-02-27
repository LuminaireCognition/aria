# Skill Review: pilot

**Skill path:** `.claude/skills/pilot/`
**Review timestamp:** 2026-02-26-2228
**Files:** `SKILL.md` (239 lines, ~2,366 tokens)

## 1. Executive Summary

The pilot skill is a moderately-sized ESI+profile hybrid skill that is reasonably well-structured but carries significant dead weight in verbose ASCII-box response templates. Five separate response templates (self query, public query, not found, no credentials, ESI error) consume roughly 55% of the skill's token budget while providing marginally different formatting for essentially the same data layout. The skill also duplicates CLAUDE.md's ESI availability check pattern and pilot resolution data sources table.

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | N/A (ESI + local profile) | Uses `uv run aria-esi pilot` for live data, local `profile.md` for config. No MCP involved -- appropriate for authenticated personal data. |
| Prompt hygiene | :green_circle: | Clear separation of data sources by query type (L71-99). Explicit about what's public vs authenticated vs local config. |
| Failure handling | :green_circle: | Good ESI unavailability fallback (L57-69) with local-only mode. Covers no credentials (L193-212), not found (L159-170), and ESI error (L220-229). |
| Context window efficiency | :yellow_circle: | Five ASCII-box templates (L103-170, L193-229) are verbose. The data sources table (L71-99) is useful but could be compressed. Security status descriptions (L174-182) are static game data. |

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 103-137 | Self query ASCII-box response template (35 lines). Verbose box-drawing format. | **CONSOLIDATE** to a compact field list (15 lines) | ~150 tokens |
| `SKILL.md` | 139-155 | Public query ASCII-box template. Nearly identical structure to self query with fewer fields. | **REMOVE** -- derive from self query template with "show public fields only" instruction | ~120 tokens |
| `SKILL.md` | 159-170 | Not found ASCII-box template. | **CONSOLIDATE** to 3 imperative lines | ~60 tokens |
| `SKILL.md` | 193-212 | No ESI credentials ASCII-box template. | **CONSOLIDATE** to 3 imperative lines | ~100 tokens |
| `SKILL.md` | 220-229 | ESI error ASCII-box template. | **CONSOLIDATE** to 2 imperative lines | ~60 tokens |
| `SKILL.md` | 49-69 | ESI availability check section. Duplicates the same pattern found in orders and other ESI skills. This is a cross-cutting concern. Pattern (B). | **CONSOLIDATE** to a one-line reference: "Check ESI availability (see session hook). If unavailable, use local profile only." | ~120 tokens |
| `SKILL.md` | 174-182 | Security status descriptions table. Static game data that Claude knows from training and that the CLI already resolves. | **REMOVE** | ~60 tokens |
| `SKILL.md` | 71-99 | Data sources by query type -- two tables (self + public). Useful but verbose. | **CONSOLIDATE** to a single merged table | ~80 tokens |

**Total estimated savings: ~750 tokens (~32% reduction)**

## 4. Specific Findings

### High Severity

**H1. Five ASCII-box response templates where one + instructions suffices**
- File: `SKILL.md`, L103-170, L193-229
- The skill dedicates ~130 lines to five nearly-identical ASCII-box templates. The structural difference between "self query" and "public query" is just which fields are included. The error templates are trivially different.
- **Action:** Keep one canonical template (self query in compact form). Replace others with imperative delta instructions: "For public queries, show only: name, corp, alliance, security, birthday." "For not found, state the query and suggest checking spelling."

**H2. ESI availability check is a cross-cutting pattern**
- File: `SKILL.md`, L49-69
- Pattern (B): This 20-line section is nearly identical to the one in `orders/SKILL.md` (L55-78). Every ESI skill repeats this. It should either be a shared protocol file or a single-line reference.
- **Action:** **Consolidate** to: "If ESI is unavailable (session hook status), fall back to local profile data and note 'Showing local profile (ESI unavailable)'. Do not run CLI commands."

### Medium Severity

**M1. Security status descriptions table is static game data**
- File: `SKILL.md`, L174-182
- This is well-known EVE game data (sec status ranges and labels). The CLI already resolves these labels. Including it in the skill template wastes tokens.
- **Action:** **Remove**. If needed, the CLI output includes the description.

**M2. Duplicate data source tables for self vs public queries**
- File: `SKILL.md`, L71-99
- Two separate tables (self: L75-89, public: L93-99) that could be one table with an "access level" column.
- **Action:** **Consolidate** into one table.

### Low Severity

**L1. Cross-references table is low-value**
- File: `SKILL.md`, L233-240
- Maps related commands. Marginally useful but Claude already knows about these skills from the index.
- **Action:** Keep but note as candidate for removal in a future pass.

**L2. No explicit "do not fabricate" guardrail**
- File: `SKILL.md` (absent)
- No instruction preventing Claude from inventing wallet balances or SP counts if ESI returns incomplete data.
- **Action:** Add: "Present only data returned by ESI or read from profile.md. If data is missing, state what's unavailable -- do not estimate or fabricate values."

## 5. Prioritized Recommendations

1. **Consolidate** five ASCII-box templates into one compact template + imperative delta instructions -- saves ~490 tokens.
2. **Consolidate** ESI availability check (L49-69) to a 2-line instruction -- Pattern (B), saves ~120 tokens.
3. **Remove** security status descriptions table (L174-182) -- saves ~60 tokens.
4. **Consolidate** two data source tables (L71-99) into one -- saves ~80 tokens.
5. **Add** a "do not fabricate" guardrail for volatile data (wallet, SP).
