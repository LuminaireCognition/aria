# Skill Review: orient

**Skill path:** `.claude/skills/orient/SKILL.md`
**Reviewed:** 2026-02-26-2221
**Size:** 209 lines, 9,112 chars (~2,278 tokens)

---

## 1. Executive Summary

Orient is one of the better-grounded skills in the codebase — the MCP-first mandate is explicit, the hallucination guard is tight, and the data source attribution is thorough. The main issue is moderate redundancy: the Field → Source Mapping table (lines 50–62) restates what the Required Tool Calls table already establishes, the System Classification section is padded with "why" bullets that Claude doesn't need, and two anti-patterns duplicate guards already present earlier in the file. Cutting these yields ~30% token reduction with no behavioral loss.

---

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | 🟢 | Explicit MANDATORY table, ❌ markers, hallucination guard, `include_realtime=True` mandate with default warning. No paths to bypass MCP. |
| Prompt hygiene | 🟢 | Unambiguous. Anti-patterns name exact wrong behaviors. Field → Source mapping traces every output field to a tool response. No vague hedging. |
| Failure handling | 🟡 | No instruction for when `local_area` call fails entirely (network error, system not found). Skill is silent on this path — Claude may improvise. |
| Context window efficiency | 🟡 | Field → Source Mapping table (13 rows, 11 pointing to the same call) redundant with the Required Tool Calls table above it. System Classification "why" bullets add tokens without adding instructions. |

---

## 3. Reduction Inventory

| # | File | Lines | What It Is | Action | Est. Token Savings |
|---|------|-------|------------|--------|-------------------|
| 1 | SKILL.md | 23–31 | Data Authority table | CONSOLIDATE — replace with one-line reference to `DATA_AUTHORITY.md` + keep sov-validate note | ~90 |
| 2 | SKILL.md | 50–62 | Field → Source Mapping table | CONSOLIDATE — replace with 3-line prose: "All fields come from `local_area` response. Key fields: `origin`, `threat_summary`, `sovereignty`, `hotspots`, `quiet_zones`, `ratting_banks`, `escape_routes`, `fw_systems`. If sovereignty absent, supplement via `universe(action="systems")`." | ~130 |
| 3 | SKILL.md | 107–109 | Hotspots "why" bullets (Gate camps, Fleet engagements, Roaming gangs) | REMOVE — pattern D "why X?" prose. The output template already makes the meaning clear. | ~30 |
| 4 | SKILL.md | 111–115 | Quiet Zones "Good for:" bullet list | REMOVE — pattern D. Capsuleer knows what quiet space is for. | ~30 |
| 5 | SKILL.md | 117–121 | Ratting Banks "Indicates:" bullet list | REMOVE — pattern D. Same as above. | ~30 |
| 6 | SKILL.md | 187–189 | Anti-pattern 1 (sovereignty when not in response) | REMOVE — exact duplicate of the hallucination guard at lines 42–44. | ~25 |
| 7 | SKILL.md | 197–199 | Anti-pattern 4 (FW data when fw_systems absent) | REMOVE — already stated in FW section at lines 181–185: "Always show when `fw_systems` contains entries." | ~25 |
| 8 | SKILL.md | 201–210 | Response Priority section | CONSOLIDATE — priority is implicit in the output format template order. If kept, merge as a one-line note at the top of the output format section rather than a standalone section. | ~80 |

**Total estimated savings: ~440 tokens (~19% reduction)**

---

## 4. Specific Findings

### High

**[H1] No failure handling for `local_area` call failure**
Lines 33–46 mandate tool calls but say nothing about what happens if the call fails. If `local_area` returns an error (system not found, MCP unavailable), Claude has no instruction and may improvise data.

→ **modify** — Add after line 46:
```
If `local_area` fails or returns an error, surface the failure explicitly:
"Orientation data unavailable: [error]. Cannot assess this system without live MCP data."
Do NOT fabricate threat levels, sovereignty, or escape routes from training knowledge.
```

### Medium

**[M1] Field → Source Mapping table is largely redundant (lines 50–62)**
The Required Tool Calls table (lines 38–41) already states that `local_area` provides "All orientation data: threats, sovereignty, hotspots, escape routes." The 13-row mapping table then maps 11 of those back to the same `local_area` call. The only non-obvious information in the table is:
- the specific response field names (e.g., `origin`, `threat_summary`, `fw_systems`)
- the `systems` fallback for sovereignty

This can be captured in 3 lines of prose, saving ~130 tokens.

→ **modify** (see Reduction Inventory #2)

**[M2] Data Authority table duplicates DATA_AUTHORITY.md (lines 23–31)**
The table's presence in SKILL.md means it can drift from the authoritative source. The sov-validate note is behavioral and worth keeping, but the four-row authority table is pattern A (inlined reference data).

→ **modify** — Replace with:
```
Data authority hierarchy follows `dev/docs/ai-runtime/DATA_AUTHORITY.md`.
Coalition data is validated against ESI before loading into cache; run `sov-validate` to verify.
```

### Low

**[L1] System Classification "why" bullets (lines 103–121)**
The three subsections (Hotspots, Quiet Zones, Ratting Banks) correctly state the thresholds (5+ kills, 0 kills, 100+ NPC kills) — these are behavioral. But the sub-bullets explaining *why* each category matters ("Gate camps, Fleet engagements, Roaming gangs"; "Good for: Stealth mining..."; "Indicates: Active ratting...") are pattern D justification prose. Claude knows what to do with hotspots without being told that "gate camps" are dangerous.

→ **remove** bullets while keeping threshold lines (see Reduction Inventory #3–5)

**[L2] Anti-pattern duplicates (lines 187–199)**
Two of the four anti-patterns are already covered:
- Anti-pattern 1 (sovereignty fabrication) duplicates the `⚠️ HALLUCINATION GUARD` at lines 42–44
- Anti-pattern 4 (FW without data) duplicates the conditional at lines 181–182

Anti-patterns 2 and 3 (systems outside radius, region from training data) are unique and should be kept.

→ **remove** anti-patterns 1 and 4 (see Reduction Inventory #6–7)

**[L3] Response Priority section is implicit in output format (lines 201–210)**
The output format template (lines 64–92) already encodes the priority order: THREAT → SOVEREIGNTY → AVOID → QUIET → RATTING → ESCAPE. The Response Priority section restates this ordering in prose. The FW priority placement (rank 3) is the only information not already encoded in the template.

→ **consolidate** — Add a one-line note to the output format section: "FW data follows sovereignty block when present." Remove the standalone section.

**[L4] `include_realtime` default warning is strong but could be co-located**
The mandate "NEVER use `include_realtime=False`" (line 46) and the rationale that "MCP default is `false`" are currently split from the Required Tool Calls table by an intervening blockquote. The flow is slightly disjointed but not harmful. Low priority.

---

## 5. Prioritized Recommendations

1. **add** failure handling path for `local_area` call failure [H1] — closes the one genuine grounding gap. Single paragraph addition.

2. **modify** Field → Source Mapping table → 3-line prose [M1] — largest single token saving (~130 tokens), zero behavioral loss.

3. **modify** Data Authority table → 2-line cross-reference [M2] — eliminates drift risk from inlined reference data (~90 tokens).

4. **remove** System Classification "why" bullets [L1–Reduction #3–5] — ~90 tokens, pattern D cleanup.

5. **remove** duplicate anti-patterns 1 and 4 [L2–Reduction #6–7] — ~50 tokens, reduces redundancy.

6. **consolidate** Response Priority section into output format note [L3–Reduction #8] — ~80 tokens.

**Total projected size after changes:** ~165 lines, ~1,840 tokens (~19% reduction from 2,278 tokens)

The skill's grounding discipline is already strong. These changes make it tighter without altering any behavioral instructions.
