# Mission Brief: Pilot Skill Awareness Fix

## Problem Statement

The mission-brief skill has three related failures in pilot skill awareness:

1. **profile.md not read** — Listed as `data_sources` (optional) instead of `prerequisite_files` (mandatory). The model skipped it, missing that the pilot is 6 days old.
2. **check_requirements not called** — Validation Gate step 6 uses conditional language ("If pilot skill data is available"), giving the model an easy exit. It was skipped entirely.
3. **CPU risk undetected** — The fitting engine validated at All V skills (default). CPU was 97.8% — almost certainly overflows at real skill levels for a new pilot. No heuristic caught this.

## Solutions Considered

### Solution 1: Move profile.md to prerequisite_files

Change one line in SKILL.md front-matter. The skill loading system enforces prerequisite reads before output, making profile.md a mandatory gate.

- **Pros**: Uses existing enforcement mechanism. Zero new prose. Surgical.
- **Cons**: Only addresses root cause 1. Profile.md is always loaded even for repeat users where tier is already known.

### Solution 2: Add "Pilot Assessment" phase to SKILL.md

Insert a named section between Intel Retrieval and Fit Adaptation that mandates extracting pilot age, module tier, and approximate skill level from profile.md. Creates a visible checkpoint.

- **Pros**: Named phases are easier for models to anchor on. Can include tier inference rules (e.g., < 30 days → T1 only, cap skills likely III).
- **Cons**: More prose. Doesn't technically prevent skipping (it's still just instructions).

### Solution 3: Make Validation Gate step 6 unconditional

Rewrite from "If pilot skill data is available, verify flyability" to "ALWAYS call `fitting(action='extract_requirements')` and cross-reference against pilot tier." Remove the conditional escape hatch.

- **Pros**: Directly fixes root cause 2. Works even without cached pilot skill IDs.
- **Cons**: `extract_requirements` lists skill names but can't confirm pilot has them without ESI skill data or cached skill IDs.

### Solution 4: Add resource headroom heuristic

Add a rule: if CPU > 90% or PG > 90% at All V, and pilot age < 60 days, flag as "tight fit — may overflow at your skill level" and suggest meta module alternatives.

- **Pros**: Catches the specific CPU overflow scenario. Simple threshold check.
- **Cons**: Arbitrary threshold. Doesn't replace real skill checking.

### Solution 5: Use `use_pilot_skills: true` in fitting engine

The fitting MCP tool already supports `use_pilot_skills` parameter. When ESI is connected and skills are cached, validate at real skill levels instead of All V.

- **Pros**: Most accurate — shows real CPU/PG at pilot's actual skills.
- **Cons**: Requires ESI connection and cached pilot skills. Doesn't help offline. The current ESI integration may not cache skills in the format the fitting engine expects.

### Solution 6: Skill-tier-aware archetype variants

Create separate archetype files per skill tier (t1.yaml, meta.yaml, t2.yaml) with pre-validated CPU/PG for each tier.

- **Pros**: Systematic, data-driven.
- **Cons**: Over-engineering. Requires creating and maintaining 3x archetypes per hull. The problem is simpler than this.

## Recommended Path: Solutions 1 + 3 + 4

These three changes are complementary, non-overlapping, and all confined to SKILL.md edits:

| Solution | Addresses | Change Type |
|----------|-----------|-------------|
| 1: profile.md → prerequisite_files | Root cause 1 (profile not read) | Front-matter, 1 line |
| 3: Unconditional check_requirements | Root cause 2 (flyability not checked) | Validation Gate rewrite, ~5 lines |
| 4: Resource headroom heuristic | Root cause 3 (CPU overflow undetected) | Validation Gate addition, ~3 lines |

Solution 2 is subsumed — once profile.md is a prerequisite, the model reads it. The existing Gear Tier Validation section already tells the model what to extract (module tier, pilot age). No new section needed.

Solutions 5 and 6 are deferred. Solution 5 is valuable but depends on ESI plumbing that may not exist yet. Solution 6 is over-engineered.

## Implementation

### Change 1: Front-matter — move profile.md to prerequisite_files

```yaml
# Before
prerequisite_files:
  - reference/mechanics/npc_damage_types.md
  - reference/mechanics/drones.json
data_sources:
  - userdata/pilots/{active_pilot}/profile.md
  - userdata/pilots/{active_pilot}/ships.md
  # ...

# After
prerequisite_files:
  - reference/mechanics/npc_damage_types.md
  - reference/mechanics/drones.json
  - userdata/pilots/{active_pilot}/profile.md
data_sources:
  - userdata/pilots/{active_pilot}/ships.md
  # ...
```

### Change 2: Validation Gate step 6 — remove conditional

```markdown
# Before
6. If pilot skill data is available, verify flyability via
   `fitting(action="check_requirements", eft="...")`. For new pilots
   (< 30 days), assume T1 modules only and flag any T2 items as
   potentially unflyable.

# After
6. **ALWAYS** call `fitting(action="extract_requirements", eft="...")`
   to list all skill requirements. For new pilots (< 60 days per
   profile.md `Capsuleer Since`), flag any module requiring a skill
   above level III as potentially unflyable. If ESI skill data is
   cached, also call `fitting(action="check_requirements")` for
   exact verification.
```

### Change 3: Validation Gate — add step 4b (resource headroom)

Insert after step 4, before step 5:

```markdown
4b. **Resource headroom check:** If CPU usage > 90% or Powergrid
    usage > 90% at All V skills, AND the pilot is < 60 days old
    (per profile.md), add a warning: "Tight fit — CPU/PG may
    overflow at your current skill level. Train {relevant fitting
    skill} or downgrade {tightest module} to a compact/meta variant."
    Identify the fitting skill (CPU Management for CPU, Power Grid
    Management for PG) and the highest-consumption module that could
    be swapped to a compact variant.
```

## Files Changed

| File | Change |
|------|--------|
| `.claude/skills/mission-brief/SKILL.md` | 3 edits (front-matter, step 4b, step 6) |

No new files. No code changes. No archetype modifications.

## Validation

Re-run the same scenario after changes: `/mission-brief Level 2 Damsel in Distress in t1/meta vexor`. Verify:

1. profile.md is read before any output
2. `extract_requirements` is called on the final fit
3. CPU 97.8% triggers the headroom warning for a 6-day-old pilot
4. Brief includes a fitting skill training note or module downgrade suggestion
