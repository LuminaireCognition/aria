---
name: sec-status
persona_exclusive: paria
redirect: personas/paria-exclusive/sec-status.md
---

# Security Status

This skill is exclusive to **PARIA** (pirate persona).

**Skill definition:** `personas/paria-exclusive/sec-status.md`

## Availability

This skill is available to pilots with **pirate faction alignment** OR personas with **unrestricted skill access**:

| Faction | Persona | Access |
|---------|---------|--------|
| `pirate` | PARIA | Yes |
| `angel_cartel` | PARIA-A | Yes |
| `serpentis` | PARIA-S | Yes |
| `guristas` | PARIA-G | Yes |
| `blood_raiders` | PARIA-B | Yes |
| `sanshas_nation` | PARIA-N | Yes |
| *(any)* | FORGE | Yes (unrestricted) |
| Empire factions | ARIA/AURA-C/VIND/THRONE | No |

### Unrestricted Skills Flag

Personas with `unrestricted_skills: true` in their manifest bypass exclusivity checks entirely. Check `persona_context.unrestricted_skills` in the pilot profile - if `true`, grant access regardless of faction alignment.

## For Empire Pilots

This skill tracks negative security status, tag costs, and empire access restrictions—primarily relevant for pilots with criminal standings. Empire pilots can use:

- `/pilot` - View pilot identity and standings
- `/esi-query` - Query character standings via ESI

## Enabling This Skill

To access pirate-exclusive skills, update your faction alignment:

1. Edit `userdata/pilots/{active_pilot}/profile.md`
2. Change `faction:` to `pirate` (or a specific pirate faction)
3. Regenerate persona context:
   ```bash
   uv run aria-esi persona-context
   ```
4. Start a new session for changes to take effect
