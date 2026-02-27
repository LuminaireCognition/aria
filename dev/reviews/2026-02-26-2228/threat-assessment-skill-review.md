# Skill Review: threat-assessment

**Path:** `.claude/skills/threat-assessment/SKILL.md`
**Review timestamp:** 2026-02-26-2228
**Size:** 498 lines, ~4,972 tokens

## 1. Executive Summary

The threat-assessment skill has the strongest grounding discipline of any skill in this batch — its hallucination guards, field-to-source mapping, and anti-patterns section are exemplary. However, it is also the largest file (498 lines, ~4,972 tokens) and suffers from pattern G duplication: the response format is shown five separate times (base format, enhanced format, real-time format, watched entity format, and sovereignty block). These overlapping examples consume ~1,500 tokens for what could be expressed in one parameterized template. Secondary bloat comes from the inlined Security Status Reference table (pattern A — this is static game data) and verbose experience-adaptation examples.

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | 🟢 | Excellent. Mandatory tool call table (lines 28-35), field-to-source mapping (lines 45-54), hallucination guard (lines 41), and anti-patterns (lines 474-486) all reinforce MCP-first. "Every data point must come from a tool call" is unambiguous. |
| Prompt hygiene | 🟢 | Very clear separation of MCP-sourced vs derived data. Lines 37-39 explicitly require `include_realtime=True`. The field-source mapping table is best-in-class. |
| Failure handling | 🟡 | Degraded mode for real-time data (lines 166-171) is handled. But no explicit handling for MCP unavailability (what if `universe()` call fails entirely?). Implicit: the CLI fallback in CLAUDE.md covers this, but the skill doesn't acknowledge it. |
| Context window efficiency | 🔴 | Five response format variants (lines 82-218) for what is essentially the same template with optional sections. Security Status Reference table (lines 262-272) is static game data that doesn't change. Experience adaptation examples (lines 422-458) are verbose. |

## 3. Reduction Inventory

| File | Lines | What | Action | Token Savings |
|------|-------|------|--------|---------------|
| `SKILL.md` | 82-107 | "Enhanced Response Format" — first response template variant (with live intel) | **CONSOLIDATE** (pattern G) with other format variants into one parameterized template | ~150 tokens |
| `SKILL.md` | 109-164 | "Response Format with Real-Time Data" — second response variant with gatecamp alerts, recent kills | **CONSOLIDATE** (pattern G) | ~350 tokens |
| `SKILL.md` | 174-218 | "Watched Entity Activity" response variant — third response variant | **CONSOLIDATE** (pattern G) | ~300 tokens |
| `SKILL.md` | 239-260 | "Response Format" (base template) — fourth response variant, the simplest | Keep this one as the base | 0 tokens |
| `SKILL.md` | 262-272 | "Security Status Reference" table — static game data. Should be in a reference file or SDE. | **REMOVE** (pattern A) | ~80 tokens |
| `SKILL.md` | 274-335 | "Sovereignty-Aware Threat Assessment" — 62 lines including Data Authority citation, sovereignty examples, coalition response characteristics table | **CONSOLIDATE** — the MCP call pattern is already covered in Required Tool Calls table. The coalition characteristics (lines 318-323) are community data presented as fact. | ~300 tokens |
| `SKILL.md` | 337-380 | "Faction Warfare Threat Factors" — 44 lines. The FW tool call is already documented at lines 34 and the how-to at lines 359-367 repeats the pattern. | **CONSOLIDATE** — keep the FW status threat table (350-354), remove the duplicate how-to-query examples | ~150 tokens |
| `SKILL.md` | 389-418 | "Common Threats for Self-Sufficient Pilots" + "Safety Protocols for Venture Operations" — 30 lines of generic EVE safety advice. Not data-grounded, not threat-assessment specific. | **REMOVE** (pattern D — advisory prose) | ~200 tokens |
| `SKILL.md` | 419 | "Intelligence Framing" line references "Intelligence Sourcing Protocol in CLAUDE.md" — no such section exists in CLAUDE.md | **REMOVE** — vestigial reference | ~20 tokens |
| `SKILL.md` | 422-458 | "Experience-Based Adaptation" — three tiers of example output for security status explanation + risk factors. 37 lines. | **CONSOLIDATE** — replace with a 3-line tier summary | ~250 tokens |
| `SKILL.md` | 460-472 | "Contextual Suggestions" table — boilerplate cross-reference pattern found in many skills | **REMOVE** if standardized; otherwise keep | ~60 tokens |
| `SKILL.md` | 490-498 | "Persona Adaptation" section — 9 lines repeating the standard overlay loading pattern that the skill loader already handles | **REMOVE** (pattern B) | ~50 tokens |

**Total estimated savings:** ~1,910 tokens (~38%)

## 4. Specific Findings

### High Severity

**H1. Pattern G: Five overlapping response format variants** (lines 82-260)
The response format is shown in five variants: enhanced (with live intel), real-time (with gatecamp alerts), watched entity, sovereignty block, and base template. Each is a full ASCII-box example. The differences between them are additive sections (gatecamp alert block, watched entity block, sovereignty block, FW block) that could be expressed as "include when relevant" annotations on a single base template.
**Action:** Keep the base template (lines 239-260). Replace the four variants with a list of conditional blocks: "When gatecamp data present, insert: [3-line block]. When watched entities active, insert: [3-line block]." This reduces ~800 tokens of redundant box-drawing to ~200 tokens of conditional inserts.

**H2. Vestigial reference to nonexistent CLAUDE.md section** (line 419)
"Follow the Intelligence Sourcing Protocol in CLAUDE.md" — this section does not exist in CLAUDE.md. A grep confirms it only exists in persona overlays and legacy files.
**Action:** REMOVE the reference. If intelligence framing is needed, it belongs in the skill itself or a persona overlay.

### Medium Severity

**M1. Pattern A: Security Status Reference table** (lines 262-272)
This is static game data (sec status ranges, CONCORD response times, PvP risk levels). It doesn't change and could be in a reference file. However, it's compact (11 lines) and directly used in threat level derivation.
**Action:** REMOVE or move to `reference/mechanics/security_status.json`. The MCP `universe(action="systems")` call already returns security status, and threat level derivation is already documented via the Interpreting Activity Data table (lines 73-81).

**M2. Generic EVE safety advice** (lines 389-418)
"Common Threats for Self-Sufficient Pilots" and "Safety Protocols for Venture Operations" are generic game knowledge not grounded in any data source. Lines like "Fit for align speed and warp stability" and "Never AFK mine below 0.9" are general EVE tips, not threat assessment outputs.
**Action:** REMOVE. Threat assessment should surface data-driven risks, not recite generic safety tips.

**M3. Coalition Response Characteristics table** (lines 318-323)
"Imperium: Standing fleets, organized caps, rapid comms" is community knowledge presented without sourcing. This changes as player organizations evolve.
**Action:** Flag as community data per DATA_AUTHORITY.md. Add a caveat or move to a community data reference file.

### Low Severity

**L1. Pattern B: Persona Adaptation section** (lines 490-498)
The standard "This skill supports persona-specific overlays" block is handled by the skill loader. The `has_persona_overlay: true` in frontmatter is sufficient.
**Action:** REMOVE.

**L2. Verbose experience adaptation examples** (lines 422-458)
Three full response examples for new/intermediate/veteran experience tiers. The pattern is clear from the first example.
**Action:** CONSOLIDATE to a 5-line summary: "new: explain terms, define risks. intermediate: terse risk list with brief context. veteran: minimal, assume knowledge."

**L3. Efficiency note about local_area duplicating activity** (lines 60)
"Do NOT make a separate `universe(action="activity")` call for the origin" — good operational guidance but could be a one-line note rather than a paragraph.
**Action:** Keep but trim.

## 5. Prioritized Recommendations

1. **CONSOLIDATE** five response format variants into one base template + conditional blocks (lines 82-260) — pattern G, ~800 tokens saved. This is the highest-impact change. *(modify)*
2. **REMOVE** "Common Threats for Self-Sufficient Pilots" and "Safety Protocols for Venture Operations" (lines 389-418) — ungrounded advisory prose, ~200 tokens. *(remove)*
3. **REMOVE** vestigial "Intelligence Sourcing Protocol" reference (line 419) — dead reference. *(remove)*
4. **CONSOLIDATE** Sovereignty section (lines 274-335) — keep tool call pattern and threat factors table, remove verbose examples and coalition characteristics. *(modify)*
5. **CONSOLIDATE** experience adaptation (lines 422-458) — replace three full examples with tier summary. *(modify)*
6. **REMOVE** Security Status Reference table (lines 262-272) — static data, move to reference file. *(remove)*
7. **REMOVE** Persona Adaptation section (lines 490-498) — pattern B, handled by skill loader. *(remove)*
8. **CONSOLIDATE** FW Threat Factors section (lines 337-380) — remove duplicate query examples, keep status threat table. *(modify)*
