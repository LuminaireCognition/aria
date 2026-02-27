# Skill Review: agents-research

**Skill path:** `.claude/skills/agents-research/SKILL.md`
**Review timestamp:** 2026-02-26-2228
**File stats:** 347 lines, ~3,400 tokens

## 1. Executive Summary

The agents-research skill is significantly bloated by three categories of dead weight: verbose ASCII-box response templates consuming ~100 lines (Pattern E), a duplicated ESI availability check that restates CLAUDE.md behavior (Pattern B), and an inlined Research Skills Reference table (lines 205-221) that belongs in an SDE query or reference file rather than the skill prompt. The skill's standings freshness gate (lines 19-48) is well-structured and unique, but the overall file could lose ~40% of its tokens without degrading output.

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| Data-first enforcement | 🟢 | The standings freshness gate (lines 19-48) is a strong pattern — forces `ensure-fresh standings` before eligibility claims. ESI data is fetched via CLI before presentation. |
| Prompt hygiene | 🟡 | Clear about ESI data requirements, but the Research Skills Reference table (lines 205-221) inlines game data that should come from SDE queries. |
| Failure handling | 🟢 | Comprehensive: ESI unavailable (lines 103-128), scope missing (lines 303-316), no agents (lines 179-193, 269-283), staleness warnings (lines 43-46). |
| Context window efficiency | 🔴 | ASCII box templates (lines 243-283, 287-316) consume ~80 lines for formatting that a 3-line instruction could achieve. Two duplicate response formats (standard + RP). ESI availability block duplicates CLAUDE.md. |

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 103-128 | "ESI Availability Check" section — duplicates CLAUDE.md session hook ESI check | **REMOVE** — Pattern B, system-level behavior | ~200 tokens |
| `SKILL.md` | 243-266 | ASCII-box "Formatted Version (rp_level: moderate or full)" response template | **CONSOLIDATE** — replace with 3-line format instruction: "Use RP formatting when rp_level is on/full: ARIA header, boxed sections, GalNet Sync timestamp." Pattern E. | ~180 tokens |
| `SKILL.md` | 269-283 | ASCII-box "No Agents Display" template | **REMOVE** — a single instruction "If no agents, state that and suggest how to start R&D" covers this. Pattern E. | ~100 tokens |
| `SKILL.md` | 285-316 | ASCII-box error templates (ESI not configured, missing scope) — two separate box templates | **CONSOLIDATE** — replace with imperative: "If ESI not configured or scope missing, state the limitation and provide the setup command." Pattern E. | ~200 tokens |
| `SKILL.md` | 205-221 | Research Skills Reference table — 12 rows of skill-to-datacore mappings | **REMOVE** — this is static game data. Should be queried via `sde(action="search", query="Engineering", category="Skill")` or moved to a reference file. Pattern A. | ~120 tokens |
| `SKILL.md` | 91-101 | ESI Requirement section with setup command — redundant with lines 103-128 and the error templates | **REMOVE** — consolidated into error handling | ~80 tokens |
| `SKILL.md` | 334-347 | "Self-Sufficiency Context" and "Behavior Notes" sections — mixed useful and noise | **CONSOLIDATE** — keep sorting/rounding rules (4 lines), remove self-sufficiency context (pilot profile already captures this) | ~80 tokens |
| `SKILL.md` | 137-176 | Full JSON response structure example — 40 lines of sample JSON | **CONSOLIDATE** — reduce to field list with types, not a full rendered example | ~120 tokens |

**Total estimated savings: ~1,080 tokens (~32% of skill)**

## 4. Specific Findings

### High Severity

**H1. ESI Availability Check duplicates CLAUDE.md (Pattern B)**
- **File:** `SKILL.md`, lines 103-128
- **Issue:** This section restates the ESI availability check that CLAUDE.md's session hook already performs. The skill loading mechanism runs after session init, so ESI status is already known.
- **Action:** **REMOVE** the entire section. If ESI-specific behavior is needed, a single line suffices: "If ESI is unavailable (session hook), respond with the in-game alternative and do not attempt ESI queries."

**H2. Four ASCII-box response templates (Pattern E)**
- **File:** `SKILL.md`, lines 243-266 (RP format), 269-283 (no agents), 287-301 (ESI not configured), 303-316 (missing scope)
- **Issue:** Four separate ASCII-art box templates using ═ and ─ characters. These consume ~100 lines for formatting that imperative instructions handle in ~10 lines total. The RP formatting is already governed by the persona overlay system.
- **Action:** **CONSOLIDATE** all four into imperative formatting instructions. Keep the standard table format (lines 224-238) as the primary template; reduce RP variant to a one-line modifier.

### Medium Severity

**M1. Research Skills Reference table inlines game data (Pattern A)**
- **File:** `SKILL.md`, lines 205-221
- **Issue:** A 12-row table mapping research skills to datacore types and common uses. This is static SDE data that could be queried at runtime. If it needs to be available, it should be a declared `data_source` or `prerequisite_file`, not inlined.
- **Action:** **REMOVE** the table. Replace with: "Query `sde(action='search', query='datacore', category='Skill')` for research skill-to-datacore mappings."

**M2. Full JSON response structure is over-specified**
- **File:** `SKILL.md`, lines 137-176
- **Issue:** 40 lines of sample JSON output including two complete agent records and an empty response variant. The CLI command produces this output; Claude doesn't need to know the exact JSON shape in this detail — it just needs to present the data.
- **Action:** **CONSOLIDATE** to a 10-line field summary: list the key fields (agent_name, agent_corp, skill_name, points_per_day, accumulated_rp, days_active) and note the summary block.

**M3. Duplicate ESI setup instructions**
- **File:** `SKILL.md`, lines 91-101 (ESI Requirement) and lines 287-316 (error templates)
- **Issue:** The setup command `uv run python .claude/scripts/aria-oauth-setup.py` appears three times: line 99, line 299, line 313. The scope name `esi-characters.read_agents_research.v1` appears in frontmatter line 14, line 93, line 100, and line 314.
- **Action:** **REMOVE** lines 91-101 entirely. The frontmatter declares the scope; the error template (consolidated) can mention the setup command once.

### Low Severity

**L1. Self-Sufficiency Context section (lines 334-339)**
- **File:** `SKILL.md`, lines 334-339
- **Issue:** "For pilots with `market_trading: false`" — this is profile-driven context that the pilot profile already captures. The skill should read the profile to determine emphasis, not carry an inline rule.
- **Action:** **REMOVE** — the pilot profile and operations.md already contain this context.

**L2. SDE Agent Search Limitations section is useful but verbose**
- **File:** `SKILL.md`, lines 195-203
- **Issue:** This section documents real SDE data gaps and workarounds. It's genuinely useful for agent-related queries. However, it applies more broadly than just this skill — it's relevant to any agent search.
- **Action:** Keep, but note this could be a candidate for a shared protocol file in `reference/protocols/` if other skills also do agent searches.

## 5. Prioritized Recommendations

1. **REMOVE** ESI Availability Check section (lines 103-128) — pure CLAUDE.md duplication. (Pattern B)
2. **CONSOLIDATE** all four ASCII-box templates (lines 243-316) into ~10 lines of imperative formatting instructions. (Pattern E)
3. **REMOVE** Research Skills Reference table (lines 205-221) — inline game data. (Pattern A)
4. **REMOVE** ESI Requirement section (lines 91-101) — redundant with frontmatter and error handling.
5. **CONSOLIDATE** JSON response structure (lines 137-176) to a field list.
6. **REMOVE** Self-Sufficiency Context (lines 334-339) — profile-driven, not skill-driven.
