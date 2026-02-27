# Skill Review: clones

**Skill path:** `.claude/skills/clones/SKILL.md`
**Review timestamp:** 2026-02-26-2228
**File size:** 11,004 bytes (~2,750 tokens)

## 1. Executive Summary

The clones skill is a CLI-backed ESI query skill at moderate size (~2,750 tokens). Its main issues are verbose ASCII-art response format templates consuming ~40% of the file, inlined game mechanic reference data (implant slot tables), and an experience-based adaptation section that duplicates what the experience adaptation protocol already handles. The ESI availability check (lines 236-262) duplicates CLAUDE.md system behavior.

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | :yellow_circle: | Skill uses CLI commands (`uv run python -m aria_esi clones`), not MCP dispatchers. This is appropriate since no MCP `pilot` action covers clones directly. But there is no explicit "do not recall/assume" guardrail for clone data. |
| Prompt hygiene | :yellow_circle: | CLI commands are clear (lines 27-52). However, implant slot reference tables (lines 149-173) are inlined game mechanics that should be in a reference file or omitted — Claude could hallucinate slot assignments if the tables drift. |
| Failure handling | :green_circle: | Good. ESI unavailable handling (lines 236-262), missing scope (lines 279-288), and no-jump-clones (lines 292-303) cases are all covered with actionable fallbacks. |
| Context window efficiency | :yellow_circle: | ASCII-art response templates (lines 58-147) are the heaviest section. Experience adaptation examples (lines 200-229) are verbose. Overall not terrible for a ~2,750 token skill but has clear fat. |

## 3. Reduction Inventory

| File | Lines | What | Action | Est. Token Savings |
|------|-------|------|--------|-------------------|
| SKILL.md | 58-87 | Full Clone Status ASCII response template | CONSOLIDATE | ~200 tokens. Replace with a 5-line structural description. |
| SKILL.md | 89-113 | Implants Only ASCII response template | CONSOLIDATE | ~150 tokens. Merge description into the Full Clone Status section. |
| SKILL.md | 115-147 | Jump Clone Status + Cooldown ASCII templates (two variants) | CONSOLIDATE | ~200 tokens. One compact template with a note about cooldown variant. |
| SKILL.md | 149-173 | Implant Slot Reference tables (Attribute Enhancers + Hardwirings) | REMOVE | ~200 tokens. This is inlined game reference data (pattern A). Not declared as prerequisite or data source. Either extract to a reference file or remove — Claude should not be the source of truth for slot-to-attribute mappings. |
| SKILL.md | 175-198 | Safety Protocols section (proactive warnings, risk assessment integration) | CONSOLIDATE | ~150 tokens. Reduce to 2-3 imperative sentences. The proactive warning behavior is a nice-to-have but the verbose format templates are dead weight. |
| SKILL.md | 200-229 | Experience-Based Adaptation section with three verbatim examples | REMOVE | ~250 tokens. Pattern B — experience adaptation is a system-level protocol defined in CLAUDE.md's referenced `EXPERIENCE_ADAPTATION.md`. Skill should not re-implement the protocol with inline examples. One sentence ("Adapt verbosity per pilot experience level") suffices. |
| SKILL.md | 231-235 | Scopes Required section | REMOVE | ~30 tokens. Duplicates frontmatter `esi_scopes` (lines 16-17). |
| SKILL.md | 236-262 | ESI Availability Check section | REMOVE | ~200 tokens. Pattern B — ESI availability checking is system-level behavior. CLAUDE.md session hook handling covers this. |
| SKILL.md | 264-273 | Contextual Suggestions table | CONSOLIDATE | ~60 tokens. Reduce to one sentence: "Suggest one related command when contextually relevant." |

**Total estimated savings: ~1,440 tokens (~52% reduction)**

## 4. Specific Findings

### High Severity

**H1. ESI Availability Check duplicates CLAUDE.md system behavior (Pattern B)**
- File: `SKILL.md`, lines 236-262
- The session hook already provides ESI status. Every ESI-backed skill would need this section if it were skill-owned, which contradicts ADR-006's ownership model.
- **Action:** REMOVE entirely.

**H2. Inlined implant slot reference data (Pattern A)**
- File: `SKILL.md`, lines 149-173
- Two tables mapping implant slots to attributes and common types. This is static game data that should live in a reference file if needed.
- **Action:** REMOVE. If this data is important for correct output, create `reference/mechanics/implant_slots.json` and add to `data_sources`. Otherwise just remove — the ESI response includes implant names which are self-documenting.

### Medium Severity

**M1. Experience-Based Adaptation re-implements system protocol (Pattern B)**
- File: `SKILL.md`, lines 200-229
- Three full verbatim response examples for new/intermediate/veteran. The experience adaptation system is referenced in CLAUDE.md and documented in `EXPERIENCE_ADAPTATION.md`.
- **Action:** REMOVE. Replace with: "Adapt clone status verbosity per pilot experience level."

**M2. Four ASCII response templates are verbose (Pattern E)**
- File: `SKILL.md`, lines 58-147
- Four separate templates with box-drawing characters for Full Status, Implants Only, Jump Clone Status, and Jump Clone on Cooldown.
- **Action:** CONSOLIDATE to one structural description with key fields listed. The ASCII art costs tokens without improving steering over a compact format description.

### Low Severity

**L1. Scopes Required section duplicates frontmatter**
- File: `SKILL.md`, lines 231-235
- `esi_scopes` is already declared in frontmatter (lines 16-17).
- **Action:** REMOVE.

**L2. Safety Protocols verbose warning templates**
- File: `SKILL.md`, lines 175-198
- Two warning format templates for proactive implant risk warnings. The behavior is valuable but the format blocks are verbose.
- **Action:** CONSOLIDATE to imperative instructions: "Warn about implant risk when pilot discusses low-sec, null-sec, PvP, or L4+ missions."

## 5. Prioritized Recommendations

1. **REMOVE** ESI Availability Check section — system-level behavior (lines 236-262). (~200 tokens)
2. **REMOVE** Experience-Based Adaptation section — duplicates system protocol (lines 200-229). Replace with one sentence. (~250 tokens)
3. **REMOVE** Implant Slot Reference tables — inlined game data without declared source (lines 149-173). (~200 tokens)
4. **CONSOLIDATE** four ASCII response templates into one compact structural description (lines 58-147). (~400 tokens)
5. **REMOVE** Scopes Required section — duplicates frontmatter (lines 231-235). (~30 tokens)
6. **CONSOLIDATE** Safety Protocols to imperative instructions (lines 175-198). (~100 tokens)
