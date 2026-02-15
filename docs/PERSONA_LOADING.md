# Persona Loading

This guide covers configuring ARIA's faction persona system — how to enable roleplay mode, choose a persona, and troubleshoot persona issues.

For developer internals (file loading mechanics, overlay resolution, security delimiters), see [dev/docs/PERSONA_LOADING.md](../dev/docs/PERSONA_LOADING.md).

## RP Levels

Three levels determine persona behavior:

| Level | Persona | Address | Content |
|-------|---------|---------|---------|
| `off` | None | Natural | No persona files loaded |
| `on` | Active | "pilot" / "Captain" | Identity, terminology, manifest, voice |
| `full` | Full immersion | "Capsuleer" / "Captain" | All above + intel sources |

### Level Behaviors

**off:**
- No persona voice
- Natural communication style
- EVE terminology when contextually useful

**on:**
- Faction persona voice active
- Address per manifest (`moderate` address forms)
- Formatted report boxes used sparingly
- No intel source attribution

**full:**
- Complete persona immersion
- Formal address forms ("Capsuleer" for empire)
- Full formatted output
- Intel sources referenced in responses
- Never break character unless triggered

## Branch Determination

| Branch | Factions |
|--------|----------|
| Empire | `gallente`, `caldari`, `minmatar`, `amarr` |
| Pirate | `pirate`, `angel_cartel`, `serpentis`, `guristas`, `blood_raiders`, `sanshas_nation` |

## Faction-to-Persona Mapping

| Faction | Persona | Directory | Branch | Fallback |
|---------|---------|-----------|--------|----------|
| `gallente` | ARIA Mk.IV | `aria-mk4` | Empire | — |
| `caldari` | AURA-C | `aura-c` | Empire | — |
| `minmatar` | VIND | `vind` | Empire | — |
| `amarr` | THRONE | `throne` | Empire | — |
| `pirate` | PARIA | `paria` | Pirate | — |
| `angel_cartel` | PARIA-A | `paria-a` | Pirate | `paria` |
| `serpentis` | PARIA-S | `paria-s` | Pirate | `paria` |
| `guristas` | PARIA-G | `paria-g` | Pirate | `paria` |
| `blood_raiders` | PARIA-B | `paria-b` | Pirate | `paria` |
| `sanshas_nation` | PARIA-N | `paria-n` | Pirate | `paria` |

## Manual Persona Selection

Some personas are not tied to EVE factions and require explicit selection via the `Persona:` field in the pilot profile:

```markdown
## Identity
- **Character Name:** Federation Navy Suwayyah
- **Persona:** forge
- **Primary Faction:** gallente
- **RP Level:** on
```

### Selection Precedence

1. If `Persona:` field exists → load that persona directly from its manifest
2. Else → use `Primary Faction:` field with faction-to-persona mapping table above

### How Manual Personas Work

When a `Persona:` field is present:

1. Load the manifest from `personas/{persona}/manifest.yaml`
2. Extract `branch` from manifest (required for manual personas)
3. Use that branch for shared content loading (`_shared/empire/` or `_shared/pirate/`)
4. Build file list normally based on RP level

### Manual Persona Manifest Requirements

Manual personas must declare their branch explicitly:

```yaml
# personas/forge/manifest.yaml
name: FORGE
directory: forge
branch: empire         # Required - no faction to infer from

factions: []           # Empty list = not auto-selected by faction
```

### Available Manual Personas

| Persona | Directory | Branch | Purpose |
|---------|-----------|--------|---------|
| FORGE | `forge` | Empire | Development & Research Intelligence Array |

## Regenerating persona_context

When pilot profile fields change (`faction`, `rp_level`, or `persona`), regenerate the context:

```bash
uv run aria-esi persona-context --pilot <pilot_id>

# Or regenerate all pilots:
uv run aria-esi persona-context --all
```

The command:
1. Reads current `faction`, `rp_level`, and optional `persona` from profile
2. If `persona` field exists, loads persona manifest directly for branch
3. Otherwise, determines branch and persona from faction mapping tables
4. Builds file list based on RP level
5. Writes `persona_context` block to profile frontmatter
6. **Compiles artifact:** Generates `.persona-context-compiled.json` with pre-wrapped delimiters and integrity hashes

## Validating persona_context

To detect stale or broken persona configurations:

```bash
uv run aria-esi validate-overlays --pilot <pilot_id>

# Or validate all pilots:
uv run aria-esi validate-overlays --all
```

The validation checks for:

### Staleness Issues

Detected when `persona_context` doesn't match current profile settings:

| Issue | Cause | Fix |
|-------|-------|-----|
| Persona mismatch | Faction changed without regeneration | `persona-context` |
| Branch mismatch | Empire↔Pirate faction switch | `persona-context` |
| RP level mismatch | RP level changed without regeneration | `persona-context` |
| Files list mismatch | Persona files reorganized | `persona-context` |
| Overlay path mismatch | Persona renamed or moved | `persona-context` |

### Missing Files

Detected when referenced files no longer exist:

| Issue | Impact | Fix |
|-------|--------|-----|
| Missing persona file | Session init fails to load context | Restore file or regenerate |
| Missing skill overlay | Skill uses base behavior (degraded) | Create overlay or remove flag |
| Missing exclusive skill | Skill invocation fails | Restore or remove from index |

### Example Output

```json
{
  "status": "issues_found",
  "validation": {
    "issues": {
      "stale": [
        {
          "field": "persona",
          "current": "paria",
          "expected": "aria-mk4",
          "message": "Persona mismatch: profile has faction 'gallente'..."
        }
      ]
    },
    "summary": {
      "staleness_issues": 1
    }
  }
}
```

## Breaking Character

Trigger phrases work at any RP level:
- "Seriously though," "Real talk," "No RP," "Actually"

Response pattern:
> Dropping the act for a second—[direct response]
>
> Back in character when you're ready.

Resume with: "Back to it" or continuing in-universe speech.
