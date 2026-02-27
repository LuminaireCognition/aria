# Skill Migration Guide (ADR-006)

How to slim a skill to comply with the self-contained ownership model.

**Decision record:** `dev/decisions/ADR-006-skill-context-ownership.md`
**Reference migration:** `mission-brief` — commit `35f261d7`
**Review prompt:** `dev/prompts/skill-review-prompt.md`

## Ownership Rules

| Layer | Owns | Red flag if it contains |
|-------|------|------------------------|
| **CLAUDE.md** | System mechanisms (session init, MCP tool map, skill loading, security) | Skill-specific protocols, response formats, or validation gates |
| **SKILL.md** | Skill behavior (what to do when invoked) | Inline copies of data from prerequisite files, pilot resolution steps, "Why X?" rationale |
| **Prerequisite/data files** | Facts and reference data | — |

## Migration Steps

### 1. Run the review prompt

```
Apply the prompt in @dev/prompts/skill-review-prompt.md to the /{skill-name} skill.
```

This produces a timestamped review in `dev/reviews/` with a grounding scorecard, reduction inventory, and prioritized recommendations.

### 2. Identify and cut redundancy

Work through the reduction inventory. Most skills will have some subset of these patterns:

#### A. Inlined reference data (REMOVE)

**Symptom:** Tables in SKILL.md that duplicate content from files listed in `prerequisite_files` or `data_sources`.

**Example (mission-brief):** Drone damage-by-faction table inlined in SKILL.md while `drones.json` is a declared prerequisite.

**Fix:** Delete the inline table. Replace with a one-line imperative reference:
```
Read `drones.json → enemy_recommendations.{faction}` to select drones.
```

**Why this matters:** The prerequisite gate already forces Claude to read the file before producing output. An inline copy lets Claude skip the read and risks staleness when the source file is updated.

#### B. Duplicated CLAUDE.md behaviors (REMOVE)

**Symptom:** SKILL.md restates system-level procedures that CLAUDE.md already defines.

**Common offenders:**
- Pilot resolution steps (CLAUDE.md §Session Initialization)
- Persona loading sequence
- MCP tool usage patterns
- "Read config.json → read registry → resolve directory"

**Fix:** Delete entirely. These run before skill loading — the skill can assume they're done.

#### C. Skill-specific protocols in CLAUDE.md (MOVE)

**Symptom:** CLAUDE.md contains a section that only applies when one specific skill is active.

**Example (mission-brief):** §Mission Data Lookup in CLAUDE.md described the cache-first retrieval protocol — a protocol only relevant during `/mission-brief`.

**Fix:** Ensure the protocol exists in SKILL.md, then delete the CLAUDE.md section. Every conversation was paying the token cost for a protocol that only one skill uses.

#### D. "Why X?" justification prose (REMOVE)

**Symptom:** Paragraphs explaining the rationale behind a protocol, placed right after the protocol itself.

**Examples:** "Why cache-first?", "Why disambiguation matters?", "Why collect all, not pick one?"

**Fix:** Delete. Claude needs instructions, not justifications. The protocol is self-documenting.

#### E. ASCII flowcharts (CONSOLIDATE)

**Symptom:** Box-drawing flowcharts (┌─┐│└─┘) spanning 20-40 lines for sequential logic.

**Fix:** Convert to numbered lists. Same information at ~40% of the token cost:

Before (35 lines):
```
┌──────────────────────────┐
│ STEP 1: Parse Input       │
├──────────────────────────┤
│ Extract mission_name ...  │
└──────────────────────────┘
              ↓
┌──────────────────────────┐
│ STEP 2: Check Cache       │
...
```

After (6 lines):
```
1. Parse input: extract mission_name, level, faction
2. Check local cache (INDEX.md) — if found, skip to step 6
3. Search wiki via Special:Search
4. Filter and disambiguate
5. Populate cache (required before presenting)
6. Read from cache → present to capsuleer
```

#### F. Checkbox-style validation checklists (CONSOLIDATE)

**Symptom:** `□ Read drones.json` / `□ Identified target faction weakness` templates.

**Fix:** Replace with imperative numbered steps. Claude doesn't fill checkboxes — a numbered sequence steers identically with fewer tokens.

#### G. Duplicate sections within the same file (CONSOLIDATE)

**Symptom:** Two sections in SKILL.md covering the same topic (e.g., experience adaptation in both "Response Format" and "Behavior").

**Fix:** Keep the one closest to where it's needed. Delete the other.

### 3. Check for content that needs to migrate IN

When removing a section from CLAUDE.md, check whether the skill's SKILL.md already covers it. If not, migrate the behavioral content into SKILL.md before deleting from CLAUDE.md.

**Example:** CLAUDE.md's §Mission Data Lookup included cache filename suffixes for DED sites, unrated sites, and expeditions. The skill's cache format section only had agent mission suffixes. The additional suffixes were added to SKILL.md before removing the CLAUDE.md section.

### 4. Verify completeness

After rewriting, verify that every behavioral instruction from the original skill is still present. Check:

- [ ] All response format templates preserved
- [ ] All validation gates preserved (steps, not necessarily verbatim)
- [ ] All error handling cases covered
- [ ] All edge cases covered
- [ ] References to prerequisite/data files are imperative ("Read X → do Y"), not passive
- [ ] No inline data tables duplicating declared prerequisite files
- [ ] No system-level procedures (pilot resolution, persona loading)
- [ ] Frontmatter unchanged (triggers, prerequisite_files, data_sources)

### 5. Measure

Compare before/after:

```bash
wc -l -c .claude/skills/{name}/SKILL.md
# Old: N lines, M chars, ~M/4 tokens
# New: N lines, M chars, ~M/4 tokens
```

The mission-brief migration achieved a 57% token reduction (806→448 lines, ~9,800→~4,150 tokens). Most skills should see 20-50% reduction depending on how much redundancy they accumulated.

## Migration Priorities

Not every skill needs migration urgently. Prioritize by token cost:

```bash
# List skills by file size (largest first)
wc -c .claude/skills/*/SKILL.md | sort -rn | head -20
```

Skills under ~2,000 tokens are unlikely to have significant redundancy. Focus on the largest skills first — they have the most to gain and are most likely to contain the patterns above.

## What NOT to Change

- **Frontmatter** — triggers, prerequisite_files, data_sources, model, category. These are consumed by tooling.
- **Persona overlays** — review separately; they have their own sync concerns.
- **Response format templates** — these are the core unique value of each skill. Compress prose around them, not the templates themselves.
- **_index.json** — hand-maintained. Update the entry manually if frontmatter changes.
