# Skill Review: fitting

**Skill path:** `.claude/skills/fitting`
**Review timestamp:** 2026-02-26-2116

---

## 1. Executive Summary

The `fitting` skill has strong grounding discipline — the SDE verification gate and mandatory EOS validation are well-enforced and failure paths are properly handled. The primary problem is structural: SKILL.md (391 lines) carries significant dead weight from redundant content that duplicates CHECKLIST.md, global CLAUDE.md session logic, and generic EVE knowledge that needs no grounding. Estimated reduction: ~900 tokens (~15%) with no loss of output quality.

---

## 2. Grounding Discipline Scorecard

| Area | Rating | Assessment |
|------|--------|------------|
| MCP-first enforcement | 🟢 | Clear mandatory gates: SDE verification for every module (Step 1), EOS validation before any fit is presented (Step 2). "Never present a fitting recommendation without EOS validation" is unambiguous. Drone data grounding is enforced via `drones.json` read requirement. |
| Prompt hygiene | 🟡 | Individual instructions are unambiguous, but redundancy across SKILL.md and CHECKLIST.md creates a bloated context. The same validation tables, tank coherence rules, and warning protocols appear in both files — Claude may read inconsistent or outdated copies. |
| Failure handling | 🟢 | Each validation failure type has a named action. EOS unavailability is handled with explicit "warn + no stats" instruction. "If SDE returns no match: do NOT include it in the fit" is clear. |
| Context window efficiency | 🟡 | Significant redundancy between SKILL.md and CHECKLIST.md (~250 tokens of Tank Coherence Rules copied nearly verbatim). Pilot resolution logic (covered by CLAUDE.md global init), generic faction knowledge, and fitting philosophy guidelines add ~400 tokens with no grounding value. |

---

## 3. Reduction Inventory

| # | File / Lines | What It Is | Action | Est. Tokens Saved |
|---|-------------|-----------|--------|-------------------|
| 1 | `SKILL.md` lines 35–42 | "Trigger Phrases" H2 section — identical to `triggers` list in front-matter (lines 7–14) | **REMOVE** | ~50 |
| 2 | `SKILL.md` lines 53–56 | "Reference Documentation" H2 section — lists `EFT-FORMAT.md`, `MODULE_NAMES.md`, `CHECKLIST.md`, all already in `prerequisite_files` front-matter | **REMOVE** | ~40 |
| 3 | `SKILL.md` lines 57–66 | "Pilot Resolution" H2 section — verbatim restatement of Session Initialization logic from `CLAUDE.md`. Global, not fitting-specific. | **REMOVE** | ~100 |
| 4 | `SKILL.md` lines 265–286 | "Fitting Philosophy Guidelines" — four sub-sections (Survival, Mining, Mission, Exploration) giving generic advice Claude already handles (align < 6s, match tank to damage, probe strength). Zero grounding value. | **REMOVE** | ~160 |
| 5 | `SKILL.md` lines 287–312 | "Tank Coherence Rules" — duplicates `CHECKLIST.md` lines 60–82. The CHECKLIST.md copy is where Claude is instructed to use it during construction. Replace with a pointer: "See Tank Coherence Rules in CHECKLIST.md." | **CONSOLIDATE** | ~230 |
| 6 | `SKILL.md` lines 315–321 | "Manufacturing Awareness" — 7-line standalone section that can be merged as a bullet into the "Operational Constraints / self-sufficiency mode" section above it | **CONSOLIDATE** | ~70 |
| 7 | `SKILL.md` lines 346–354 | "Faction-Specific Fitting Guidance" table — Gallente=Armor/Drones, Caldari=Shield/Missiles, etc. Basic EVE faction knowledge; no grounding required, Claude already knows this. | **REMOVE** | ~80 |
| 8 | `SKILL.md` lines 357–361 (bullets 1–3 only) | "Maintain ARIA persona throughout", "Provide tactical reasoning", "Warn about fitting pitfalls" — global persona directives, not fitting-specific. Keep bullets 4–6 (brevity, rig inclusion). | **REMOVE** | ~30 |
| 9 | `EFT-FORMAT.md` lines 152–161 | "DNA Format (Alternative)" — numeric type ID compact format. File comment says "primarily for programmatic use." The fitting skill never generates DNA format. | **REMOVE** | ~80 |
| 10 | `CHECKLIST.md` lines 60–82 | "Tank Coherence Rules" table — if item #5 is actioned and the canonical copy stays in CHECKLIST.md, then SKILL.md pointer is satisfied. Otherwise if kept in SKILL.md, remove from CHECKLIST.md to pick one canonical location. Either way: consolidate to one copy. | **CONSOLIDATE** (if #5 reversed) | ~230 |

**Total estimated savings: ~840 tokens** (removing items 1–9, keeping CHECKLIST.md as Tank Coherence canonical location)

---

## 4. Specific Findings

### HIGH — Structural redundancy (grounding risk)

**Finding H1: Tank Coherence Rules in two places**
- `SKILL.md` lines 287–312 and `CHECKLIST.md` lines 60–82 contain essentially the same armor/shield slot rules and warning table.
- Risk: if one copy drifts (e.g., new warnings are added to the tool and only one file is updated), Claude may follow stale rules from whichever file was loaded most recently.
- **Action:** Pick one canonical location (CHECKLIST.md, since that's the active reference during construction). Replace SKILL.md content with: "See Tank Coherence Rules in CHECKLIST.md."

**Finding H2: Trigger Phrases duplicated in front-matter and body**
- `SKILL.md` lines 7–14 (`triggers:` YAML list) and lines 35–42 ("Trigger Phrases" H2 section) list the same 7 phrases. The body section adds nothing.
- **Action:** **Remove** lines 35–42 entirely.

**Finding H3: Pilot Resolution duplicates CLAUDE.md global logic**
- `SKILL.md` lines 57–66 describe a 3-step pilot path resolution sequence (config.json → registry → directory). This exact logic is defined as a global session initialization step in `CLAUDE.md` and is not fitting-specific.
- Adding it here burns tokens and risks divergence if the global process changes.
- **Action:** **Remove** lines 57–66. The active pilot is already resolved before any skill runs.

### MEDIUM — Dead weight (no grounding or steering value)

**Finding M1: Fitting Philosophy Guidelines add no grounding**
- `SKILL.md` lines 265–286 contain four sections (Survival, Mining, Mission, Exploration fits) with advice like "prioritize align time (sub-6 seconds ideal for industrials)" and "include Cloak+MWD trick capability where appropriate."
- These are basic EVE conventions that Claude already handles correctly without prompting. They provide no MCP grounding and no edge-case steering that isn't already handled elsewhere.
- **Action:** **Remove** entire "Fitting Philosophy Guidelines" section (lines 265–286).

**Finding M2: Faction-Specific Fitting Guidance is unnecessary recall**
- `SKILL.md` lines 346–354 table (Gallente=Armor/Drones, Caldari=Shield/Missiles, etc.) is basic game knowledge.
- This is exactly the kind of training-data content the review framework flags as noise — it doesn't need to be grounded because it doesn't change, and Claude already knows it accurately.
- **Action:** **Remove** the "Faction-Specific Fitting Guidance" section (lines 346–354).

**Finding M3: Reference Documentation section redundant with front-matter**
- `SKILL.md` lines 53–56 list `EFT-FORMAT.md`, `MODULE_NAMES.md`, and `CHECKLIST.md` as links under "Reference Documentation."
- These files are already declared in `prerequisite_files` (front-matter lines 17–20) and CLAUDE.md enforces reading them before generating any output.
- **Action:** **Remove** lines 53–56.

**Finding M4: Manufacturing Awareness is a stub that should fold upward**
- `SKILL.md` lines 315–321 are a 7-line section giving bullet points about what to provide "when recommending fittings for self-sufficient pilots."
- The self-sufficiency check is already enforced in "Operational Constraints" (lines 80–88). These manufacturing bullets belong there as a sub-list, not as a standalone H2 section.
- **Action:** **Consolidate** lines 315–321 as bullets under the self-sufficiency block in lines 80–88; remove standalone section.

**Finding M5: DNA Format section in EFT-FORMAT.md is never used**
- `EFT-FORMAT.md` lines 152–161 describe DNA format (numeric type IDs, compact single-line form). The document itself says it's "primarily for programmatic use."
- The fitting skill builds EFT strings for clipboard export. DNA format is never requested or generated here.
- **Action:** **Remove** `EFT-FORMAT.md` lines 152–161.

**Finding M6: Behavior section bullets 1–3 are global persona directives**
- `SKILL.md` lines 357–361 open the Behavior section with "Maintain ARIA persona throughout", "Provide tactical reasoning for fitting choices", "Warn about fitting pitfalls (cap stability, CPU/PG issues)." These are global ARIA instructions, not fitting-specific steering.
- Bullets 4–6 (brevity, rig inclusion, when to add rig suggestions) are fitting-specific and should be kept.
- **Action:** **Remove** first three bullets (lines 357–361 approx); keep bullets 4–6.

### LOW — Minor issues

**Finding L1: `_index.json` missing `model` field while front-matter has `model: haiku`**
- `SKILL.md` front-matter (line 4) specifies `model: haiku`. `_index.json` has no `model` field.
- This creates inconsistency if anything reads `_index.json` for routing decisions.
- **Action:** Add `"model": "haiku"` to `_index.json`.

**Finding L2: EFT-FORMAT.md Import Instructions — marginal value**
- `EFT-FORMAT.md` lines 138–149 list 7 steps for importing fittings via the EVE client UI.
- These are stable, procedural UI instructions that Claude already knows. Low risk if kept, but low grounding value.
- **Action:** Low priority. Remove if context budget is tight; otherwise keep as a convenience reference.

**Finding L3: Warning Investigation Protocol table partially duplicated**
- `SKILL.md` lines 203–211 (warning table with "Required Action" column) overlaps with `CHECKLIST.md` Phase 3 checklist items.
- SKILL.md table is more complete (includes Empty Slots, Mixed Tank with explanation). CHECKLIST.md has simpler checkbox items.
- The two formats serve different purposes (rationale vs. checklist), so some overlap is acceptable here, but "Empty Slot Warnings" and "Mixed Tank Warnings" prose explanations below the table (lines 213–221) duplicate CHECKLIST.md Phase 4.
- **Action:** **Remove** `SKILL.md` lines 213–221 (the prose expansions below the warning table); the table itself is fine as the grounded reference.

---

## 5. Prioritized Recommendations

1. **REMOVE** Tank Coherence Rules from `SKILL.md` lines 287–312; replace with pointer to CHECKLIST.md. *(Fixes H1 — eliminates drift risk, saves ~230 tokens)*

2. **REMOVE** Pilot Resolution section `SKILL.md` lines 57–66. *(Fixes H3 — removes duplicated global logic, saves ~100 tokens)*

3. **REMOVE** Trigger Phrases body section `SKILL.md` lines 35–42. *(Fixes H2 — trivial cut, saves ~50 tokens)*

4. **REMOVE** Fitting Philosophy Guidelines `SKILL.md` lines 265–286. *(Fixes M1 — removes ungrounded generic advice, saves ~160 tokens)*

5. **REMOVE** Faction-Specific Fitting Guidance `SKILL.md` lines 346–354. *(Fixes M2 — removes unnecessary recall content, saves ~80 tokens)*

6. **REMOVE** Reference Documentation section `SKILL.md` lines 53–56. *(Fixes M3 — redundant with front-matter, saves ~40 tokens)*

7. **CONSOLIDATE** Manufacturing Awareness into self-sufficiency block; **remove** standalone section at lines 315–321. *(Fixes M4 — tightens structure, saves ~70 tokens)*

8. **REMOVE** DNA Format section from `EFT-FORMAT.md` lines 152–161. *(Fixes M5 — never used in this context, saves ~80 tokens)*

9. **REMOVE** first 3 Behavior section bullets `SKILL.md` lines 357–361. *(Fixes M6 — global directives belong in CLAUDE.md, saves ~30 tokens)*

10. **REMOVE** warning prose expansion `SKILL.md` lines 213–221. *(Fixes L3 — table above already covers it, saves ~60 tokens)*

11. **MODIFY** `_index.json` to add `"model": "haiku"`. *(Fixes L1 — consistency with front-matter)*
