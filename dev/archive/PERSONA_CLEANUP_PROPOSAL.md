# Persona System Cleanup Proposal

## Executive Summary

The persona system has grown organically and inconsistently. Empire personas are defined in a table (15-20 lines each), while PARIA has a 388-line standalone document. Documentation is scattered across 4+ files, all potentially loaded into context regardless of which persona is active.

**Goals:**
1. Consistent structure across all personas
2. Move definitions out of `docs/` into dedicated directory
3. Load only what's needed for the active persona
4. Minimize context impact

---

## Current State Analysis

### File Inventory

| File | Lines | Purpose | Context Impact |
|------|-------|---------|----------------|
| `docs/PERSONAS.md` | 222 | Faction table + intel sourcing | Always loaded |
| `docs/ROLEPLAY_CONFIG.md` | 186 | RP levels + PARIA specifics | Always loaded |
| `docs/PARIA_PERSONA.md` | 388 | Complete PARIA spec | Always loaded |
| `docs/PROJECT_PARIA.md` | 358 | Implementation tracking | Not needed at runtime |
| `docs/ROGUES_PHILOSOPHY.md` | ~200 | Background philosophy | Not needed at runtime |

**Total potential context load:** ~1,000+ lines of persona documentation

### Structural Inconsistencies

| Aspect | Empire Personas | PARIA |
|--------|-----------------|-------|
| Definition location | Table in PERSONAS.md | Standalone doc |
| Detail level | ~20 lines each | 388 lines |
| Intel sourcing | Table in PERSONAS.md | Duplicated in both files |
| RP level scaling | ROLEPLAY_CONFIG.md | Both files |
| Dialogue examples | Brief greeting only | 8 detailed scenarios |
| Boot detection | persona-detect.sh ✓ | Missing from script |

### Boot Detection Gap

The `persona-detect.sh` script handles:
- GALLENTE → ARIA Mk.IV
- CALDARI → AURA-C
- MINMATAR → VIND
- AMARR → THRONE
- *Everything else → generic ARIA*

**PARIA is not detected.** Pirate-aligned pilots get the generic fallback.

---

## Proposed Structure

### New Directory Layout

```
personas/
├── README.md                    # How personas work, how to add new ones
├── _shared/
│   ├── rp-levels.md            # RP level definitions (shared behavior)
│   └── detection.md            # Faction → persona mapping rules
│
├── aria-mk4/                   # Gallente
│   ├── manifest.yaml           # Metadata: faction, subtitle, address forms
│   ├── voice.md                # Core: 50-80 lines
│   └── intel-sources.md        # Optional: agency references
│
├── aura-c/                     # Caldari
│   ├── manifest.yaml
│   ├── voice.md
│   └── intel-sources.md
│
├── vind/                       # Minmatar
│   ├── manifest.yaml
│   ├── voice.md
│   └── intel-sources.md
│
├── throne/                     # Amarr
│   ├── manifest.yaml
│   ├── voice.md
│   └── intel-sources.md
│
└── paria/                      # Pirate
    ├── manifest.yaml
    ├── voice.md                # Core identity: condensed to ~100 lines
    ├── intel-sources.md
    └── code.md                 # The Code (only at full RP)
```

### manifest.yaml Structure

```yaml
name: PARIA
subtitle: Unlicensed Tactical Intelligence Array
factions:
  - pirate
  - angel_cartel
  - serpentis
  - guristas
  - blood_raiders
  - sanshas_nation

address:
  full: Captain
  moderate: Captain
  lite: null      # Natural address
  off: null

greeting:
  full: "A merry life and a short one, Captain."
  moderate: "Ready when you are, Captain."
```

### voice.md Structure (Target: 50-100 lines)

Each persona's `voice.md` contains only runtime-essential content:

```markdown
# [Persona Name] Voice

## Identity
| Attribute | Value |
|-----------|-------|
| Designation | ... |
| Classification | ... |

## Tone
[3-5 bullet points describing communication style]

## Signature Phrases
- "..."
- "..."

## What to Avoid
- [Anti-patterns]

## RP Level Behavior
| Level | Notes |
|-------|-------|
| full | ... |
| moderate | ... |
```

**Explicitly excluded from voice.md:**
- Detailed dialogue examples (move to reference doc)
- Historical philosophy (keep in ROGUES_PHILOSOPHY.md)
- Implementation notes
- Project tracking

### Context Loading Strategy

```
IF rp_level == "off" OR "lite":
    Load: personas/_shared/rp-levels.md only (for break character triggers)
    Skip: All persona voice files

ELSE IF rp_level == "moderate" OR "full":
    Load: personas/_shared/rp-levels.md
    Load: personas/{active_persona}/voice.md

    IF rp_level == "full":
        Load: personas/{active_persona}/intel-sources.md (optional)
        Load: personas/{active_persona}/code.md (PARIA only)
```

**Estimated context reduction:**
- Current: ~1,000 lines always loaded
- Proposed (RP off): ~50 lines
- Proposed (RP moderate): ~150 lines
- Proposed (RP full): ~200-250 lines

---

## Migration Plan

### Phase 1: Create Directory Structure

1. Create `personas/` directory
2. Create `_shared/` with extracted common content
3. Create empty persona directories

### Phase 2: Extract Empire Personas

From `docs/PERSONAS.md`, extract into individual directories:

| Current | Target |
|---------|--------|
| Gallente table row + FNI/FIO/SDII | `personas/aria-mk4/` |
| Caldari table row + CNI/CSD/InSec | `personas/aura-c/` |
| Minmatar table row + RFI/RSS | `personas/vind/` |
| Amarr table row + INI/MIO | `personas/throne/` |

### Phase 3: Condense PARIA

Reduce `docs/PARIA_PERSONA.md` from 388 lines to:

| Current Section | Action |
|-----------------|--------|
| Identity (50 lines) | Keep, condense to 20 |
| The Creed (60 lines) | Move to ROGUES_PHILOSOPHY.md |
| Voice & Communication (60 lines) | Keep in voice.md |
| Intelligence Sourcing (40 lines) | Separate file |
| Behavioral Guidelines (50 lines) | Keep, condense |
| Session Initialization (30 lines) | Move to manifest.yaml |
| Dialogue Examples (80 lines) | Move to reference doc or delete |
| Breaking Character (20 lines) | Move to _shared/rp-levels.md |
| RP Level Scaling (10 lines) | Move to manifest.yaml |
| Faction Variants (20 lines) | Keep in voice.md |
| Integration Notes (20 lines) | Delete (implementation complete) |

### Phase 4: Update Boot Detection

Add PARIA to `persona-detect.sh`:

```bash
case "$FACTION" in
    "PIRATE"|"ANGEL_CARTEL"|"SERPENTIS"|"GURISTAS"|"BLOOD_RAIDERS"|"SANSHAS_NATION")
        AI_PERSONA="PARIA"
        AI_SUBTITLE="Unlicensed Tactical Intelligence Array"
        ;;
    # ... existing cases
esac
```

### Phase 5: Update CLAUDE.md References

Replace:
```markdown
See `docs/PERSONAS.md` for faction personas.
See `docs/PARIA_PERSONA.md` for pirate details.
See `docs/ROLEPLAY_CONFIG.md` for RP levels.
```

With:
```markdown
See `personas/` for faction persona definitions.
Check `personas/_shared/rp-levels.md` for RP configuration.
```

### Phase 6: Archive Old Files

```
docs/
├── PERSONAS.md              → Delete (split into personas/)
├── ROLEPLAY_CONFIG.md       → Delete (moved to personas/_shared/)
├── PARIA_PERSONA.md         → Delete (moved to personas/paria/)
├── PROJECT_PARIA.md         → Move to docs/archive/ (implementation complete)
└── ROGUES_PHILOSOPHY.md     → Keep as reference
```

---

## Skill Persona References

Currently, 10 skills reference PARIA:
- 5 exclusive: hunting-grounds, mark-assessment, ransom-calc, escape-route, sec-status
- 5 adapted: threat-assessment, route, mission-brief, fitting, price

### Recommendation

Skills should reference personas by checking the active persona rather than duplicating persona behavior:

```markdown
## Persona Adaptation

Check active persona in pilot profile. For persona-specific behavior:
- See `personas/{persona}/voice.md` for tone and terminology
- See `personas/{persona}/intel-sources.md` for attribution

| Persona | Key Adaptation |
|---------|----------------|
| PARIA | Use underworld intel sources, "Captain" address |
| ARIA/Empire | Use faction agency sources, standard address |
```

This avoids duplicating PARIA voice documentation in every skill file.

---

## File Size Comparison

### Before

| File | Lines |
|------|-------|
| docs/PERSONAS.md | 222 |
| docs/ROLEPLAY_CONFIG.md | 186 |
| docs/PARIA_PERSONA.md | 388 |
| **Total always-loadable** | **796** |

### After

| File | Lines | When Loaded |
|------|-------|-------------|
| personas/_shared/rp-levels.md | ~50 | Always |
| personas/{persona}/manifest.yaml | ~15 | When RP enabled |
| personas/{persona}/voice.md | ~80 | When RP enabled |
| personas/{persona}/intel-sources.md | ~40 | At full RP only |
| **Total for RP off** | **~50** | |
| **Total for RP moderate** | **~145** | |
| **Total for RP full** | **~185** | |

**Context reduction: 75-95%** depending on RP level.

---

## Open Questions

1. **Skill adaptation consolidation:** Should persona adaptation sections be removed from skills and handled via a single lookup file?

2. **Faction variants:** PARIA has Angel/Serpentis/Guristas variants. Should empire personas get subfaction variants (e.g., Federation Navy vs Black Eagles)?

3. **Greeting generation:** Should boot hook dynamically generate greetings from manifest.yaml, or keep static examples?

4. **Reference documentation:** Create `docs/PERSONA_DESIGN.md` for detailed examples and philosophy, separate from runtime voice files?

---

## Summary

| Change | Impact |
|--------|--------|
| Create `personas/` directory | Logical organization |
| Split monolithic docs | Per-persona isolation |
| manifest.yaml for metadata | Machine-readable config |
| Condense voice files | 75-95% context reduction |
| Fix boot detection | PARIA actually activates |
| Load only active persona | Context efficiency |
| Archive completed project files | Clean docs/ directory |

The core principle: **Load only what's needed for the current session's persona and RP level.**
