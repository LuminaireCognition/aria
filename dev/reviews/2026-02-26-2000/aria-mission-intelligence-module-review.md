# Skill Review: ARIA Mission Intelligence Module

**Path:** `.claude/skills/mission-brief/SKILL.md`
**Overlay:** `personas/paria/skill-overlays/mission-brief.md`
**Reviewer:** Claude Code (automated)
**Date:** 2026-02-26

---

## 1. Executive Summary

The mission-brief skill is the largest single skill file in the project (~9,800 tokens for SKILL.md alone) and its primary problem is **massive redundancy with CLAUDE.md and its own prerequisite files**. Large chunks of the skill re-state drone damage tables, ammo damage tables, and mission caching protocols that are already defined elsewhere — burning tokens to tell Claude what it could read from `drones.json` at runtime. The grounding discipline is strong in principle (prerequisite gate, validation checklists, cache-first protocol) but the bloat dilutes the steering signal and invites skimming.

---

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | :green_circle: | Strong. Fit validation via `fitting(action="calculate_stats")`, module name verification via `sde(action="item_info")`, and wiki fetch via WebFetch are all explicitly gated. Cache-first pattern structurally prevents presenting unfetched data. |
| Prompt hygiene | :yellow_circle: | Generally clear "do not assume" language, but the sheer volume of inline reference tables (drone damage, ammo damage, laser/hybrid effectiveness) creates a paradox: Claude has the data *in the prompt* and may skip reading the JSON files since the tables appear authoritative. The tables should be removed — they exist in the prerequisite files. |
| Failure handling | :green_circle: | Excellent. Zero-results clarification protocol, cache-write failure handling, disambiguation flow, and "never guess faction" rule are all well-defined. Region-adapted AskUserQuestion options are a nice touch. |
| Context window efficiency | :red_circle: | ~9,800 tokens for SKILL.md is far too large. Approximately 40% of the file is redundant reference data (inline damage tables, ammo tables, EWAR tables) that duplicates content from `npc_damage_types.md`, `drones.json`, and the four weapon JSON files — all of which are already listed in `prerequisite_files` or `data_sources`. The flowchart-style ASCII boxes, while clear, consume ~3x the tokens of equivalent numbered lists. |

---

## 3. Reduction Inventory

| File / Section | What | Recommendation | Est. Savings |
|---|---|---|---|
| SKILL.md L641–662: Drone Damage Types table + validation checklist | Inline drone→damage mapping duplicates `drones.json` `by_faction` and `enemy_recommendations` sections | **REMOVE** — replace with one-liner: "Consult `drones.json → enemy_recommendations.{faction}` for correct drones" | ~500 tokens |
| SKILL.md L682–749: Full Weapon Ammo tables (Missile, Projectile, Laser, Hybrid effectiveness) | Four faction→ammo mapping tables that duplicate the four weapon JSON files listed in `data_sources` | **REMOVE** — replace with: "Consult the appropriate weapon JSON file (see `data_sources`) for ammo selection" | ~1,500 tokens |
| SKILL.md L31–44: Purpose + Trigger Phrases section | Restates the YAML frontmatter triggers almost verbatim; "Purpose" is obvious from the description | **REMOVE** — frontmatter is the single source of truth for triggers | ~200 tokens |
| SKILL.md L176–180: Enemy Faction Data section | Says "see `npc_damage_types.md`" and "load it when generating" — this is already enforced by `prerequisite_files` in frontmatter | **REMOVE** — the prerequisite gate in CLAUDE.md already mandates this | ~100 tokens |
| SKILL.md L201–232, L345–406: Two ASCII flowcharts (Disambiguation + Data Retrieval) | 60+ lines of box-drawing for flows that could be compact numbered lists | **CONSOLIDATE** — convert to numbered steps; keeps same information at ~40% token cost | ~600 tokens |
| SKILL.md L596–612: Pilot Resolution section | Duplicates CLAUDE.md §Session Initialization step 1-3 verbatim | **REMOVE** — pilot resolution is a system-level behavior, not skill-specific | ~300 tokens |
| SKILL.md L606–608: "Intelligence Framing" with agency acronyms (FNI/FIO/CNI/RFI/RSS/INI/MIO/DED) | Persona framing belongs in persona overlays, not base skill. Also references an "Intelligence Sourcing Protocol" that doesn't exist in CLAUDE.md | **REMOVE** — vestigial reference to removed protocol; persona overlay handles this | ~150 tokens |
| SKILL.md L755–766: Faction-Specific Fitting Guidance table | Static ship progression info that should come from `reference/ships/{faction}_progression.md` at runtime, not be hardcoded | **REMOVE** — already references the progression files, table is redundant | ~200 tokens |
| SKILL.md L293–299: "Why Disambiguation Matters" section | Explains rationale for disambiguation after already defining it — defensive prose that adds no steering | **REMOVE** — the disambiguation flow is self-justifying | ~150 tokens |
| SKILL.md L408–413: "Why cache-first?" section | Explains rationale for cache-first after already defining the flow | **REMOVE** — same pattern; the flow diagram is sufficient | ~100 tokens |
| SKILL.md L439–446: "Why collect all, not pick one?" and "Why not URL construction?" | More justification prose | **REMOVE** — Claude doesn't need to understand *why*, just *what to do* | ~150 tokens |
| overlay L93–115: Full example dialogue blocks | Two long example conversations; one terse example per persona would suffice | **CONSOLIDATE** — shorten to 2-3 lines each | ~200 tokens |

**Total estimated savings: ~4,150 tokens (~42% of SKILL.md)**

---

## 4. Specific Findings

### Critical

**4.1 Inline reference tables undermine prerequisite gate (SKILL.md L641–749)**

The skill declares `reference/mechanics/drones.json` as a prerequisite file, meaning CLAUDE.md's skill loading forces Claude to read it before producing output. But SKILL.md then includes an inline "Drone Damage Types by Faction" table (L643–649) and four weapon ammo tables (L682–749) with the same data. This creates two problems:
1. Claude may treat the inline tables as sufficient and skip reading the JSON files
2. If the JSON files are updated but SKILL.md isn't, the inline tables become stale — a silent accuracy failure

**4.2 Vestigial reference to "Intelligence Sourcing Protocol" (L607)**

Line 607 says "Follow the Intelligence Sourcing Protocol in CLAUDE.md" but no such section exists in CLAUDE.md. This is a dead reference, likely to a removed section. Claude will either ignore it or confabulate a protocol.

### High

**4.3 Pilot Resolution duplication (L598–603)**

The full 5-step pilot resolution sequence is already a system-level behavior in CLAUDE.md §Session Initialization. Repeating it in the skill is pure noise — the pilot is already resolved before the skill loads.

**4.4 Two large ASCII flowcharts consume ~60 lines for sequential logic (L201–232, L345–406)**

The Disambiguation Flow and Data Retrieval Protocol use box-drawing characters for visual clarity but at enormous token cost. A numbered list like:
```
1. Parse input: extract mission_name, level, faction
2. Search local cache (INDEX.md)
3. If not cached: search wiki via Special:Search
4. Filter by known parameters
5. If 2+ variants: disambiguate via AskUserQuestion
```
...conveys the same information in ~10 lines instead of ~35.

**4.5 Ammo validation checklists are ceremonial (L651–660, L733–743)**

Two multi-line checkbox templates (`□ Read drones.json`, `□ Identified target faction weakness...`) serve as process checklists. Claude doesn't fill checkboxes — these are steering prose disguised as interactive forms. A single imperative sentence ("Read the weapon JSON, select ammo matching faction weakness, include quantities in EFT") steers equally well.

### Medium

**4.6 "What NOT to Include" table (L154–163) is good but partially redundant with brevity directive (L751)**

L751 says "Target 20-30 lines total." The "What NOT to Include" table reinforces this but could be tighter — some entries state the obvious (e.g., "Multiple fitting options" / "One fit, adapted correctly" — this is already implicit in the Response Format).

**4.7 Overlay sync date (overlay L117) creates maintenance debt**

The overlay has `*Last synced with base skill: 2026-01-17*`. This is a manual tracking mechanism that will inevitably go stale. If the overlay needs to stay in sync, the build tooling should enforce it.

**4.8 PARIA overlay duplicates response format (overlay L20–38)**

The overlay defines its own response format box that partially overlaps with the base skill's response format. Only the cosmetic changes (═ vs ─, "PARIA OPERATION BRIEF" vs standard) and the "Alternative Revenue" section are genuinely new.

### Low

**4.9 Escaped backtick fences in section templates (L85–95)**

The fit template uses `\`\`\`` (escaped backticks) inside a code fence — this works but is fragile. A different delimiter or indentation approach would be more robust.

**4.10 Experience-Level Adaptation table (L167–174) vs Behavior §Experience-Based Adaptation (L769–782)**

Two separate sections cover experience adaptation: one in Response Format, one in Behavior. They're consistent but having two locations increases risk of drift.

---

## 5. Prioritized Recommendations

### 1. **REMOVE** all inline damage/ammo reference tables (L641–749)
**Impact: High (grounding + efficiency)**
Replace ~1,500 tokens of inline tables with imperative one-liners pointing to the JSON files that are *already mandatory reads*. This simultaneously improves grounding (forces JSON reads) and saves the most tokens.

### 2. **REMOVE** Pilot Resolution section (L596–612)
**Impact: High (noise reduction)**
System-level behavior. Delete entirely — 300 tokens of pure duplication.

### 3. **CONSOLIDATE** ASCII flowcharts into numbered lists (L201–232, L345–406)
**Impact: High (efficiency)**
Convert two ~35-line box-drawing flowcharts to compact numbered step lists. Same steering, ~40% of the tokens.

### 4. **REMOVE** all "Why X?" justification sections (L293–299, L408–413, L439–446)
**Impact: Medium (noise reduction)**
~400 tokens of rationale prose that doesn't steer behavior. Claude needs instructions, not justifications.

### 5. **REMOVE** Purpose + Trigger Phrases prose section (L31–44)
**Impact: Medium (deduplication)**
The YAML frontmatter already carries this information. The prose adds nothing.

### 6. **REMOVE** vestigial "Intelligence Sourcing Protocol" reference (L607)
**Impact: Medium (correctness)**
Dead reference to nonexistent CLAUDE.md section. Either remove the line or define the protocol. Given that persona overlays handle framing, removal is the right call.

### 7. **CONSOLIDATE** ammo/drone validation checklists into imperative prose (L651–660, L733–743)
**Impact: Medium (clarity)**
Replace checkbox templates with single-paragraph imperatives. Same steering, ~60% fewer tokens.

### 8. **MODIFY** Experience-Based Adaptation — merge the two sections (L167–174 + L769–782)
**Impact: Low (maintainability)**
Keep one section. The Response Format table is the better location since it's adjacent to the output templates.

### 9. **REMOVE** Faction-Specific Fitting Guidance table (L755–766)
**Impact: Low (deduplication)**
Already references `reference/ships/{faction}_progression.md`. The inline table is a stale-data risk.

### 10. **MODIFY** overlay sync date to tooling-enforced check or remove entirely
**Impact: Low (maintenance hygiene)**
Manual `*Last synced*` dates always drift. Either automate the check or accept that overlay/base can diverge.
