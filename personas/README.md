# ARIA Persona System

Faction personas provide immersive roleplay experiences for EVE Online pilots. Personas are **opt-in** (default: off).

## Structure

```
personas/
├── _shared/
│   ├── rp-levels.md        # RP level definitions (always referenced)
│   └── skill-loading.md    # Overlay system documentation
│
├── aria-mk4/               # Gallente Federation
│   ├── manifest.yaml       # Metadata, address forms, greetings
│   ├── voice.md            # Tone, phrases, communication style
│   ├── intel-sources.md    # FNI, FIO, SDII references
│   └── skill-overlays/     # Persona-specific skill adaptations
│
├── aura-c/                 # Caldari State
│   └── skill-overlays/
├── vind/                   # Minmatar Republic
│   └── skill-overlays/
├── throne/                 # Amarr Empire
│   └── skill-overlays/
├── paria/                  # Pirate / Outlaw
│   └── skill-overlays/     # PARIA adaptations for multi-persona skills
│       ├── threat-assessment.md
│       ├── route.md
│       ├── fitting.md
│       ├── price.md
│       └── mission-brief.md
│
├── forge/                  # Development & Research (manual selection)
│   ├── manifest.yaml
│   ├── voice.md
│   ├── intel-sources.md
│   └── skill-overlays/
│       ├── journal.md
│       └── aria-status.md
│
└── paria-exclusive/        # Skills only available to PARIA
    ├── mark-assessment.md
    ├── hunting-grounds.md
    ├── ransom-calc.md
    ├── escape-route.md
    └── sec-status.md
```

## Activation

Personas activate based on pilot profile settings:

```markdown
## Preferences
- **Primary Faction:** gallente
- **RP Level:** full
```

| Faction Value | Persona |
|---------------|---------|
| `gallente` | ARIA Mk.IV |
| `caldari` | AURA-C |
| `minmatar` | VIND |
| `amarr` | THRONE |
| `pirate`, `angel_cartel`, `serpentis`, `guristas`, `blood_raiders`, `sanshas_nation` | PARIA |

## Manual Persona Selection

Some personas are not tied to EVE factions and require explicit selection via the `Persona:` field:

```markdown
## Identity
- **Character Name:** Federation Navy Suwayyah
- **Persona:** forge
- **Primary Faction:** gallente
- **RP Level:** on
```

**Selection precedence:**
1. If `Persona:` field exists → use that persona directly
2. Else → use `Primary Faction:` with faction-to-persona mapping

### Manual Personas

| Persona | Purpose |
|---------|---------|
| `forge` | FORGE - Development & Research Intelligence Array |

### Manifest Requirements

Manual personas must declare their branch explicitly (since there's no faction to infer it from):

```yaml
# personas/forge/manifest.yaml
name: FORGE
directory: forge
branch: empire                    # Required for manual personas

factions: []                      # Empty = not auto-selected by faction
```

### Regenerating Context

After changing the `Persona:` field:

```bash
uv run aria-esi persona-context
```

## File Purposes

### manifest.yaml

Machine-readable metadata:
- `name`: Display name
- `subtitle`: Tagline
- `factions`: Which faction values trigger this persona
- `address`: How to address the pilot at each RP level
- `greeting`: Session start phrases

### voice.md

Runtime voice guidance (~50-80 lines):
- Identity table
- Tone bullet points
- Signature phrases
- What to avoid
- RP level scaling

### intel-sources.md

Intelligence agency references:
- Faction-specific agencies with abbreviations
- Language patterns for framing intel
- What sources to avoid

### skill-overlays/

Persona-specific adaptations for multi-persona skills:
- Loaded **in addition to** base skill content
- Contains terminology shifts, response format changes
- Only loaded when persona matches

Example: `paria/skill-overlays/threat-assessment.md` changes "Threat Assessment" to "Hunting Ground Analysis" and reframes danger as opportunity.

### {persona}-exclusive/

Skills that only exist for a specific persona:
- Full skill definitions (not overlays)
- Base skill location contains redirect stub
- Unavailable to non-matching personas

Example: `paria-exclusive/mark-assessment.md` is the complete skill; `.claude/skills/mark-assessment/SKILL.md` is just a 18-line redirect stub.

## Context Loading

Only load what's needed:

| RP Level | Files Loaded |
|----------|--------------|
| `off` / `lite` | `_shared/rp-levels.md` only |
| `moderate` | + `{persona}/voice.md` |
| `full` | + `{persona}/intel-sources.md` |

## Adding a New Persona

1. Create directory: `personas/{name}/`
2. Create `manifest.yaml` with metadata
3. Create `voice.md` with tone and phrases
4. Create `intel-sources.md` with agency references
5. Update `.claude/hooks/aria-boot.d/persona-detect.sh` to detect the faction

## Design Principles

- **Minimal context:** Each file is concise (<100 lines)
- **Consistent structure:** All personas follow the same layout
- **Opt-in complexity:** Basic files always small; detail files optional
- **Machine-readable metadata:** manifest.yaml enables programmatic access
