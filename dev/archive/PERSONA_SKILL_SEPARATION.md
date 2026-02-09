# Persona-Skill Separation Proposal

**Status:** Implemented
**Created:** 2026-01-17
**Implemented:** 2026-01-17
**Branch:** `feature/persona-skill-separation`
**Problem:** Persona-specific content embedded in skills inflates context for all users

## Implementation Summary

All 5 phases completed. Commits:
1. `c873bfa` - Phase 1: Infrastructure (directories, skill-loading.md, schema)
2. `415d3eb` - Phase 2: Extract PARIA overlays (5 multi-persona skills)
3. `4a3accc` - Phase 3: Relocate PARIA-exclusive skills (5 skills)
4. `33dc5c4` - Phase 4: Document skill loading in CLAUDE.md
5. Phase 5: Cleanup and metrics (this update)

**Measured Context Reduction:**
| Category | Lines | Notes |
|----------|-------|-------|
| PARIA overlays | 562 | Not loaded for empire pilots |
| PARIA-exclusive skills | 1,193 | Full content in persona dir |
| Redirect stubs | 90 | Loaded instead for empire |
| **Empire pilot savings** | **~1,665** | Per session when skills referenced |

## Executive Summary

Refactor the persona system to extract persona-specific skill adaptations from SKILL.md files into persona directories. This reduces context loading by 20-40% for persona-adapted skills while improving separation of concerns.

## Current State Analysis

### Persona Files (Efficient)
```
personas/
├── _shared/rp-levels.md      # 47 lines - shared
├── paria/
│   ├── manifest.yaml         # 21 lines
│   ├── voice.md              # 84 lines
│   └── intel-sources.md      # 42 lines
└── aria-mk4/                 # ~100 lines total
```
**Total per persona:** 130-180 lines. Already efficient.

### Skill Files (Bloated)

| Skill | Lines | PARIA Content | Empire Content | Waste |
|-------|-------|---------------|----------------|-------|
| `threat-assessment` | 312 | 82 | 230 | 26-72% per user |
| `mark-assessment` | 237 | 237 | 0 | 100% for empire |
| `route` | ~200 | ~40 | ~160 | 20-80% per user |
| `fitting` | ~250 | ~50 | ~200 | 20-80% per user |
| `hunting-grounds` | ~150 | 150 | 0 | 100% for empire |
| `ransom-calc` | ~120 | 120 | 0 | 100% for empire |
| `escape-route` | ~100 | 100 | 0 | 100% for empire |
| `sec-status` | ~130 | 130 | 0 | 100% for empire |
| `price` | ~100 | ~20 | ~80 | 20-80% per user |
| `mission-brief` | ~180 | ~30 | ~150 | 17-83% per user |

**Estimated waste:** 400-600 lines loaded unnecessarily per session depending on pilot faction.

## Proposed Architecture

### Directory Structure

```
personas/
├── _shared/
│   ├── rp-levels.md                    # Unchanged
│   └── skill-loading.md                # NEW: Documents overlay system
│
├── aria-mk4/
│   ├── manifest.yaml                   # Unchanged
│   ├── voice.md                        # Unchanged
│   ├── intel-sources.md                # Unchanged
│   └── skill-overlays/                 # NEW: Mostly empty for default persona
│       └── .gitkeep
│
├── paria/
│   ├── manifest.yaml                   # Unchanged
│   ├── voice.md                        # Unchanged
│   ├── intel-sources.md                # Unchanged
│   └── skill-overlays/                 # NEW: Extracted from skills
│       ├── threat-assessment.md        # PARIA adaptation section
│       ├── route.md                    # PARIA adaptation section
│       ├── fitting.md                  # PARIA gank/escape fittings
│       ├── price.md                    # Ransom value framing
│       └── mission-brief.md            # Alternative revenue framing
│
└── paria-exclusive/                    # NEW: Skills that only exist for PARIA
    ├── mark-assessment.md              # Full skill (moved from .claude/skills/)
    ├── hunting-grounds.md              # Full skill
    ├── ransom-calc.md                  # Full skill
    ├── escape-route.md                 # Full skill
    └── sec-status.md                   # Full skill
```

### Skill File Changes

**Before (`threat-assessment/SKILL.md`):**
```markdown
# ARIA Threat Assessment Module
[230 lines of core content]

---

## PARIA Adaptation (Pirate Persona)
[82 lines of PARIA-specific content]
```

**After (`threat-assessment/SKILL.md`):**
```markdown
# Threat Assessment Module
[230 lines of core content]

---

## Persona Adaptation

Load persona-specific framing from: `personas/{active_persona}/skill-overlays/threat-assessment.md`

If no overlay exists, use default (empire) framing above.
```

### Skill Index Changes

Update `.claude/skills/_index.json` to mark persona-exclusive skills:

```json
{
  "name": "mark-assessment",
  "description": "Target evaluation for engagement viability",
  "persona_exclusive": "paria",
  "skill_source": "personas/paria-exclusive/mark-assessment.md"
}
```

For skills with overlays:
```json
{
  "name": "threat-assessment",
  "description": "Security and threat analysis",
  "has_persona_overlay": true
}
```

## Implementation Phases

### Phase 1: Create Overlay Infrastructure

**Tasks:**
1. Create `personas/{name}/skill-overlays/` directories
2. Create `personas/paria-exclusive/` directory
3. Write `personas/_shared/skill-loading.md` documentation
4. Update `_index.json` schema to support `persona_exclusive` and `has_persona_overlay`

**Files created:**
- `personas/_shared/skill-loading.md`
- `personas/aria-mk4/skill-overlays/.gitkeep`
- `personas/aura-c/skill-overlays/.gitkeep`
- `personas/vind/skill-overlays/.gitkeep`
- `personas/throne/skill-overlays/.gitkeep`
- `personas/paria/skill-overlays/.gitkeep`
- `personas/paria-exclusive/.gitkeep`

### Phase 2: Extract PARIA Skill Overlays

**Tasks:**
1. Extract PARIA adaptation sections from multi-persona skills
2. Create overlay files in `personas/paria/skill-overlays/`
3. Remove extracted sections from original SKILL.md files
4. Add overlay loading instructions to original skills

**Skills to modify:**
| Skill | Action |
|-------|--------|
| `threat-assessment` | Extract lines 230-312 → `paria/skill-overlays/threat-assessment.md` |
| `route` | Extract PARIA section → `paria/skill-overlays/route.md` |
| `fitting` | Extract gank/escape section → `paria/skill-overlays/fitting.md` |
| `price` | Extract ransom framing → `paria/skill-overlays/price.md` |
| `mission-brief` | Extract alt revenue section → `paria/skill-overlays/mission-brief.md` |

### Phase 3: Relocate PARIA-Exclusive Skills

**Tasks:**
1. Move full SKILL.md content to `personas/paria-exclusive/`
2. Replace original SKILL.md with redirect stub
3. Update `_index.json` with new paths

**Skills to relocate:**
| Skill | From | To |
|-------|------|-----|
| `mark-assessment` | `.claude/skills/mark-assessment/SKILL.md` | `personas/paria-exclusive/mark-assessment.md` |
| `hunting-grounds` | `.claude/skills/hunting-grounds/SKILL.md` | `personas/paria-exclusive/hunting-grounds.md` |
| `ransom-calc` | `.claude/skills/ransom-calc/SKILL.md` | `personas/paria-exclusive/ransom-calc.md` |
| `escape-route` | `.claude/skills/escape-route/SKILL.md` | `personas/paria-exclusive/escape-route.md` |
| `sec-status` | `.claude/skills/sec-status/SKILL.md` | `personas/paria-exclusive/sec-status.md` |

**Redirect stub example (`.claude/skills/mark-assessment/SKILL.md`):**
```markdown
---
name: mark-assessment
persona_exclusive: paria
redirect: personas/paria-exclusive/mark-assessment.md
---

# Mark Assessment

This skill is exclusive to PARIA (pirate persona).

**Skill definition:** `personas/paria-exclusive/mark-assessment.md`

For empire pilots, this skill is not available. Consider `/threat-assessment` instead.
```

### Phase 4: Update Skill Loading Logic

**Tasks:**
1. Update CLAUDE.md to document overlay loading
2. Add persona-aware skill resolution to boot sequence
3. Test skill invocation for both empire and pirate pilots

**CLAUDE.md additions:**
```markdown
## Skill Loading

When a skill is invoked:

1. Check `_index.json` for `persona_exclusive` - if set and doesn't match active persona, skill unavailable
2. Load base SKILL.md from `.claude/skills/{name}/`
3. If `has_persona_overlay: true`, check `personas/{active_persona}/skill-overlays/{name}.md`
4. If overlay exists, append to skill context
5. If no overlay, use base skill content only
```

### Phase 5: Cleanup and Testing

**Tasks:**
1. Remove orphaned PARIA content from archived docs
2. Update `personas/README.md` with new structure
3. Regenerate `_index.json` with updated metadata
4. Test all skills with empire pilot profile
5. Test all skills with PARIA pilot profile
6. Verify context reduction metrics

## File Manifest

### New Files
| File | Purpose | Est. Lines |
|------|---------|------------|
| `personas/_shared/skill-loading.md` | Document overlay system | 40 |
| `personas/paria/skill-overlays/threat-assessment.md` | PARIA threat framing | 82 |
| `personas/paria/skill-overlays/route.md` | PARIA route framing | 40 |
| `personas/paria/skill-overlays/fitting.md` | Gank/escape fits | 50 |
| `personas/paria/skill-overlays/price.md` | Ransom valuation | 20 |
| `personas/paria/skill-overlays/mission-brief.md` | Alt revenue | 30 |
| `personas/paria-exclusive/mark-assessment.md` | Full skill | 237 |
| `personas/paria-exclusive/hunting-grounds.md` | Full skill | 150 |
| `personas/paria-exclusive/ransom-calc.md` | Full skill | 120 |
| `personas/paria-exclusive/escape-route.md` | Full skill | 100 |
| `personas/paria-exclusive/sec-status.md` | Full skill | 130 |

### Modified Files
| File | Change |
|------|--------|
| `.claude/skills/threat-assessment/SKILL.md` | Remove PARIA section, add overlay reference |
| `.claude/skills/route/SKILL.md` | Remove PARIA section, add overlay reference |
| `.claude/skills/fitting/SKILL.md` | Remove PARIA section, add overlay reference |
| `.claude/skills/price/SKILL.md` | Remove PARIA section, add overlay reference |
| `.claude/skills/mission-brief/SKILL.md` | Remove PARIA section, add overlay reference |
| `.claude/skills/mark-assessment/SKILL.md` | Replace with redirect stub |
| `.claude/skills/hunting-grounds/SKILL.md` | Replace with redirect stub |
| `.claude/skills/ransom-calc/SKILL.md` | Replace with redirect stub |
| `.claude/skills/escape-route/SKILL.md` | Replace with redirect stub |
| `.claude/skills/sec-status/SKILL.md` | Replace with redirect stub |
| `.claude/skills/_index.json` | Add persona metadata fields |
| `personas/README.md` | Document new structure |
| `CLAUDE.md` | Add skill loading section |

### Deleted Content
| Location | Content Removed |
|----------|-----------------|
| `threat-assessment/SKILL.md` | ~82 lines (moved to overlay) |
| `route/SKILL.md` | ~40 lines (moved to overlay) |
| `fitting/SKILL.md` | ~50 lines (moved to overlay) |
| `price/SKILL.md` | ~20 lines (moved to overlay) |
| `mission-brief/SKILL.md` | ~30 lines (moved to overlay) |

## Context Impact Analysis

### Before (Current State)

| Scenario | Skills Loaded | Context Lines |
|----------|---------------|---------------|
| Empire pilot, `/threat-assessment` | Full skill | 312 |
| PARIA pilot, `/threat-assessment` | Full skill | 312 |
| Empire pilot, `/mark-assessment` | Full skill (unusable) | 237 |
| PARIA pilot, `/mark-assessment` | Full skill | 237 |

### After (Proposed)

| Scenario | Skills Loaded | Context Lines | Savings |
|----------|---------------|---------------|---------|
| Empire pilot, `/threat-assessment` | Base only | 230 | 26% |
| PARIA pilot, `/threat-assessment` | Base + overlay | 312 | 0% |
| Empire pilot, `/mark-assessment` | Stub only | 15 | 94% |
| PARIA pilot, `/mark-assessment` | Full (from paria-exclusive) | 237 | 0% |

### Aggregate Session Impact

**Empire pilot session:**
- Saves ~220 lines of PARIA content never loaded
- PARIA-exclusive skills show as unavailable (15 lines each vs 120-237)
- **Estimated savings: 400-600 lines per session**

**PARIA pilot session:**
- No change in total context (all PARIA content still available)
- Better organization (skills in persona directory)
- **Estimated savings: 0 lines** (as expected - PARIA needs PARIA content)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Skill loading becomes more complex | Medium | Document clearly in CLAUDE.md, test thoroughly |
| Overlay files get out of sync with base skills | Medium | Include "last synced" comment, periodic review |
| Empire pilots confused by unavailable skills | Low | Clear messaging in redirect stubs |
| Boot sequence performance | Low | Overlay check is simple file existence |

## Success Criteria

1. Empire pilots see 20-40% reduction in context for adapted skills
2. PARIA pilots have identical functionality to current state
3. All 31 skills pass invocation tests
4. No regression in skill behavior for either persona type
5. Clear documentation for adding future persona overlays

## Future Extensions

This architecture enables:

1. **New personas** - Add `personas/{name}/skill-overlays/` for faction-specific framing
2. **RP level overlays** - Could extend to `skill-overlays/{skill}/{rp-level}.md`
3. **Skill variants** - Different skill behavior per faction (e.g., Caldari efficiency metrics)
4. **Community personas** - Third-party persona packs with their own overlays

## Appendix: Overlay File Format

Each overlay file follows this structure:

```markdown
# {Skill Name} - {Persona} Overlay

> Loaded when active persona is {persona}. Supplements base skill in `.claude/skills/{name}/SKILL.md`

## Persona Adaptation

[Persona-specific framing, terminology shifts, response format changes]

## {Persona}-Specific Sections

[Any additional sections only relevant to this persona]

---
*Last synced with base skill: YYYY-MM-DD*
```
