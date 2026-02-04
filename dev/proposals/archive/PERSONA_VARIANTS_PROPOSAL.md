# Persona Variants and Manual Selection Proposal

**Status:** Design Complete - Consolidated
**Consolidates:** FORGE_PERSONA_PROPOSAL.md, PARIA_S_SERPENTIS_PROPOSAL.md, PARIA_G_GURISTAS_PROPOSAL.md

---

## Executive Summary

This proposal consolidates persona management infrastructure:

1. **Manual Persona Selection** - A mechanism for personas not tied to EVE factions (FORGE)
2. **Pirate Faction Variants** - Faction-specific PARIA implementations (PARIA-S, PARIA-G)

Both use the same underlying infrastructure: manifest declarations, overlay fallbacks, and `persona_context` generation.

---

## Part 1: Manual Persona Selection

### The Problem

Current personas map to EVE factions:
- `faction: gallente` -> ARIA Mk.IV
- `faction: pirate` -> PARIA

Some personas (e.g., FORGE for development work) have no corresponding EVE faction. Adding synthetic faction values pollutes the namespace.

### Solution: Persona Override Field

Add an optional `persona:` field that takes precedence over faction-based auto-selection:

```markdown
## Identity
- **Persona:** forge              <- Manual selection (optional, new)
- **Primary Faction:** gallente   <- Preserved for game/ESI context
- **RP Level:** on
```

**Selection logic:**
1. If `persona:` field exists -> use that persona directly
2. Else -> use `faction:` field with `FACTION_PERSONA_MAP` (current behavior)

### Manifest Declaration

Manual personas declare their branch in `manifest.yaml`:

```yaml
# personas/forge/manifest.yaml
name: FORGE
subtitle: Framework for Operational Research and Generative Engineering
directory: forge
branch: empire                    # Declares branch for shared content loading
factions: []                      # Empty list - not auto-selected
```

### Implementation Changes

1. **Profile parsing** extracts `persona:` field from Identity section
2. **build_persona_context()** accepts `persona_override` parameter
3. **validate-overlays** scans all persona directories, not just faction-mapped ones

---

## Part 2: FORGE - Development Persona

### Identity

| Attribute | Value |
|-----------|-------|
| Designation | FORGE (Framework for Operational Research and Generative Engineering) |
| Classification | Development & Research Intelligence Array |
| Location | Federal Administration Information Center, Caldari Prime orbit |
| Branch | empire (Gallente-aligned per lore) |

### Voice Characteristics

- **Analytical:** Approaches problems systematically
- **Curious:** Treats unexpected behavior as interesting
- **Precise:** Uses exact terminology
- **Warm:** Collegial research partner, not cold terminal

### Use Case

Development-focused persona for ARIA development work. Exercises the persona system while building it.

### Directory Structure

```
personas/forge/
├── manifest.yaml
├── voice.md
├── intel-sources.md
└── skill-overlays/
    ├── journal.md
    └── aria-status.md
```

---

## Part 3: PARIA Faction Variants

### Architecture

Faction-specific PARIA implementations inherit from base PARIA but provide:
- Distinct voice and tone
- Faction-specific intel sources
- Custom skill overlays
- Overlay fallback to base PARIA

### PARIA-S (Serpentis)

| Attribute | Value |
|-----------|-------|
| Faction | `serpentis` |
| Tone | Polished corporate menace, Gallente sophistication |
| Address | "Associate" (full) / "Contractor" (on) |
| Intel Sources | Serpentis Corporate Intelligence, Guardian Angels Security, Inquest |

**Key differentiator:** Corporate crime sophistication vs. generic pirate roughness.

### PARIA-G (Guristas)

| Attribute | Value |
|-----------|-------|
| Faction | `guristas` |
| Tone | Direct military professional, Caldari discipline |
| Address | "Pilot" (full) / none (on) |
| Intel Sources | Listening Post Network, Guristas Production Intel, Octopus Squadron Veterans |

**Key differentiator:** Military professionalism refined for pirate operations.

### Directory Structure (per variant)

```
personas/paria-s/
├── manifest.yaml
├── voice.md
├── intel-sources.md
├── backstory.md              # Full RP only
└── skill-overlays/
    ├── route.md
    ├── price.md
    ├── threat-assessment.md
    └── fitting.md
```

### Manifest Structure

```yaml
name: PARIA-S
subtitle: Serpentis Intelligence & Operations Array
directory: paria-s
branch: pirate
fallback: paria                   # Skill overlay fallback

factions:
  - serpentis

address:
  full: Associate
  on: Contractor
  off: null
```

### persona_context Example

```yaml
persona_context:
  branch: pirate
  persona: paria-s
  fallback: paria
  rp_level: on
  files:
    - personas/_shared/pirate/identity.md
    - personas/_shared/pirate/terminology.md
    - personas/_shared/pirate/the-code.md
    - personas/paria-s/manifest.yaml
    - personas/paria-s/voice.md
  skill_overlay_path: personas/paria-s/skill-overlays
  overlay_fallback_path: personas/paria/skill-overlays
```

---

## Part 4: Implementation Plan

### Phase 1: Infrastructure

- [ ] Add `persona_override` parameter to `build_persona_context()`
- [ ] Update profile parsing to extract `persona:` field
- [ ] Update `validate-overlays` to scan all persona directories
- [ ] Update `FACTION_PERSONA_MAP` with new variants

### Phase 2: FORGE Persona

- [ ] Create `personas/forge/manifest.yaml`
- [ ] Create `personas/forge/voice.md`
- [ ] Create `personas/forge/intel-sources.md`

### Phase 3: PARIA-S (Serpentis)

- [ ] Create `personas/paria-s/manifest.yaml`
- [ ] Create `personas/paria-s/voice.md`
- [ ] Create `personas/paria-s/intel-sources.md`
- [ ] Create skill overlays (route, price, threat-assessment, fitting)

### Phase 4: PARIA-G (Guristas)

- [ ] Create `personas/paria-g/manifest.yaml`
- [ ] Create `personas/paria-g/voice.md`
- [ ] Create `personas/paria-g/intel-sources.md`
- [ ] Create skill overlays (route, price, threat-assessment, fitting)

### Future Variants

- PARIA-A (Angel Cartel)
- PARIA-B (Blood Raiders)
- PARIA-N (Sansha's Nation)

---

## Context Budget

All variants follow the same context budget:

| Component | Size |
|-----------|------|
| `_shared/{branch}/*` | ~2KB |
| `manifest.yaml` | ~0.5KB |
| `voice.md` | ~2KB |
| `intel-sources.md` | ~1KB (full RP only) |
| **Total (rp_level: on)** | ~4.5KB |
| **Total (rp_level: full)** | ~5.5-6.5KB |

---

## Success Criteria

1. Manual persona selection works via `persona:` field
2. Faction variants load with correct voice and overlays
3. Overlay fallback to base PARIA works correctly
4. `validate-overlays` validates all persona types
5. Context budget remains comparable to existing personas

---

## References

- Persona system: `personas/README.md`
- Persona loading: `docs/PERSONA_LOADING.md`
- Skill loading: `personas/_shared/skill-loading.md`
- RP levels: `personas/_shared/rp-levels.md`

---

## Changelog

- 2026-02-01: Consolidated from three separate proposals
- 2026-01-26: PARIA-G proposal created
- 2026-01-25: PARIA-S proposal created
- 2026-01-24: FORGE proposal created with manual selection mechanism
