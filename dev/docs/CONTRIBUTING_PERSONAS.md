# Contributing Personas

Step-by-step guide for creating a new ARIA persona.

## Quick Start Checklist

1. Create directory: `personas/{name}/`
2. Create `manifest.yaml` with metadata
3. Create `voice.md` with tone and communication style
4. Create `intel-sources.md` with intelligence agency references
5. Create `skill-overlays/` directory (even if empty initially)
6. Regenerate context: `uv run aria-esi persona-context`

## Persona Directory Anatomy

```
personas/{name}/
├── manifest.yaml         # Required — machine-readable metadata
├── voice.md              # Required — tone, phrases, RP level behavior
├── intel-sources.md      # Required for full RP — intelligence framing
└── skill-overlays/       # Optional — persona-specific skill adaptations
    ├── threat-assessment.md
    ├── route.md
    └── ...
```

## manifest.yaml

Machine-readable metadata that drives persona selection and context compilation.

```yaml
name: MY-PERSONA                    # Display name (uppercase convention)
subtitle: Descriptive Tagline       # Shown in boot sequence
directory: my-persona               # Matches directory name

# Faction auto-selection
factions:                            # EVE faction values that trigger this persona
  - gallente                         # Use [] for manual-only personas
branch: empire                       # "empire" or "pirate" — determines shared files

# Address forms by RP level
address:
  "on": pilot                       # How to address the user at RP level "on"
  "full": Capsuleer                  # How to address the user at RP level "full"

# Session greeting
greeting:
  "on": "Online and ready."
  "full": "Systems nominal. Awaiting directives, Capsuleer."
```

### Key Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Display name |
| `subtitle` | Yes | One-line description |
| `directory` | Yes | Directory name (kebab-case) |
| `factions` | Yes | List of EVE factions that auto-select this persona |
| `branch` | Yes | `empire` or `pirate` — determines which shared files load |
| `address` | Yes | How to address the pilot at each RP level |
| `greeting` | Yes | Session start phrases per RP level |

### Faction Mapping

| Faction Value | Branch | Current Persona |
|---------------|--------|-----------------|
| `gallente` | empire | ARIA Mk.IV |
| `caldari` | empire | AURA-C |
| `minmatar` | empire | VIND |
| `amarr` | empire | THRONE |
| `pirate` | pirate | PARIA |
| `angel_cartel` | pirate | PARIA (variant) |
| `serpentis` | pirate | PARIA (variant) |
| `guristas` | pirate | PARIA (variant) |
| `blood_raiders` | pirate | PARIA (variant) |
| `sanshas_nation` | pirate | PARIA (variant) |

### Manual-Only Personas

Personas not tied to an EVE faction (like FORGE) use empty `factions: []` and require explicit selection via `Persona: forge` in the pilot profile:

```yaml
factions: []                         # Not auto-selected
branch: empire                       # Must declare branch explicitly
```

## voice.md

Runtime voice guidance loaded at RP levels `on` and `full`. Keep under 80 lines.

### Recommended Structure

```markdown
# {PERSONA NAME} Voice

## Identity

| Field | Value |
|-------|-------|
| Full Name | {Full designation} |
| Role | {What this persona does} |
| Faction | {Aligned faction} |
| Tone | {2-3 adjective summary} |

## Communication Style

- [Bullet points describing tone and approach]
- [What makes this persona distinct]
- [Vocabulary preferences]

## Signature Phrases

- "{Characteristic phrase 1}"
- "{Characteristic phrase 2}"

## What to Avoid

- [Anti-patterns for this persona]
- [Things that would break immersion]

## RP Level Behavior

| Level | Behavior |
|-------|----------|
| `off` | No persona voice. Direct assistant. |
| `on` | Faction voice active. Professional tone. |
| `full` | Full immersion. Formal address. Intel source attribution. |
```

## Shared Files

Personas inherit shared resources based on their `branch`:

| Branch | Shared Directory | Provides |
|--------|-----------------|----------|
| `empire` | `personas/_shared/empire/` | Empire identity, terminology |
| `pirate` | `personas/_shared/pirate/` | Pirate identity, terminology, the Code |

Both branches also load from `personas/_shared/`:
- `rp-levels.md` — RP level definitions (always loaded)
- `skill-loading.md` — Overlay system documentation (developer reference)

## Skill Overlays

Overlays modify how existing skills present information for your persona.

### Creating an Overlay

1. Create `personas/{name}/skill-overlays/{skill-name}.md`
2. Set `has_persona_overlay: true` in the skill's `_index.json` entry (by adding it to the skill's frontmatter and regenerating the index)

### Naming Convention

Overlay files must exactly match the skill directory name: `{skill-name}.md`

### Content Format

```markdown
# {Skill Name} - {Persona} Overlay

> Loaded when active persona is {persona}. Supplements base skill.

## Persona Adaptation

### Terminology
- "threat" → "opportunity"
- "danger" → "competition"

### Response Framing
[How to present the skill's output in-character]

---
*Last synced with base skill: YYYY-MM-DD*
```

### Existing Overlays

PARIA has 5 skill overlays: `fitting`, `mission-brief`, `price`, `route`, `threat-assessment`. See `personas/paria/skill-overlays/` for real examples.

## Exclusive Skills

Skills that only exist for your persona.

### Creating Exclusive Skills

1. Create the full skill in `personas/{name}-exclusive/{skill-name}.md`
2. Create a redirect stub in `.claude/skills/{skill-name}/SKILL.md`
3. Register by adding an entry to `.claude/skills/_index.json`

See [CONTRIBUTING_SKILLS.md](CONTRIBUTING_SKILLS.md) for the complete exclusive skill workflow.

### Current Exclusives

PARIA has 5 exclusive skills: `mark-assessment`, `hunting-grounds`, `ransom-calc`, `escape-route`, `sec-status`.

## Context Compilation

After creating your persona, compile the context artifact:

```bash
uv run aria-esi persona-context
```

This generates `userdata/pilots/{active_pilot}/.persona-context-compiled.json` with:
- Pre-resolved file lists
- Security delimiters applied
- Branch-appropriate shared files included

**When to recompile:** After changing `faction`, `rp_level`, or `Persona:` in the pilot profile.

## Testing

1. Set your pilot profile to use the new persona:
   ```markdown
   ## Identity
   - **Persona:** my-persona
   - **Primary Faction:** gallente
   - **RP Level:** full
   ```
2. Recompile: `uv run aria-esi persona-context`
3. Start a new Claude Code session: `claude`
4. Verify:
   - Boot greeting uses your persona's greeting
   - Responses use your persona's voice and terminology
   - Skill overlays load correctly (test with `/threat-assessment` or similar)
   - RP level scaling works (`off` → no persona, `on` → voice, `full` → full immersion)

## Examples

| Persona | Complexity | Notable Features |
|---------|-----------|------------------|
| `aria-mk4` | Minimal empire | Basic manifest + voice, no overlays |
| `paria` | Full pirate | 5 overlays, pirate branch |
| `forge` | Manual selection | Empty factions, manual persona override |

## Related Documentation

- [personas/README.md](../../personas/README.md) — Persona system overview
- [rp-levels.md](../../personas/_shared/rp-levels.md) — RP level definitions
- [skill-loading.md](../../personas/_shared/skill-loading.md) — Overlay loading mechanics
- [PERSONA_LOADING.md](../../docs/PERSONA_LOADING.md) — User-facing persona configuration
