# ADR-004: Roleplay Opt-In Design

**Status:** Accepted
**Date:** 2026-01

## Context

ARIA supports faction-specific AI personas (ARIA Mk.IV for Gallente, AURA-C for Caldari, VIND for Minmatar, THRONE for Amarr) with in-universe framing, formatted tactical reports, and immersive communication.

However, many users just want accurate EVE information without roleplay elements.

## Decision

Make roleplay **opt-in** with four levels:

| Level | Persona | Address | Formatting | In-Universe |
|-------|---------|---------|------------|-------------|
| `off` (default) | None | Natural | Standard markdown | None |
| `lite` | None | Natural | Standard markdown | EVE terms only |
| `moderate` | Light | "pilot" | Boxes for reports | Light flavor |
| `full` | Full faction | "Capsuleer" | ═══════ boxes | Full immersion |

### Configuration

Set `rp_level` in pilot profile.md:

```markdown
**RP Level:** moderate
```

### Default Behavior

When `rp_level` is not set or set to `off`:
- No AI persona name
- No special address
- No formatted boxes
- No in-universe framing
- Direct, helpful responses

## Consequences

### Positive

- Most users get clean, direct responses by default
- Immersion available for those who want it
- Progressive disclosure (can increase RP gradually)
- Faction personas remain polished for enthusiasts
- No "cringe factor" for users who want utility

### Negative

- Faction persona work underutilized by default
- Must check rp_level before every response
- Some cool features hidden unless enabled

## Alternatives Considered

### Roleplay On by Default
Rejected: Many users found it distracting, wanted "just the facts."

### Binary On/Off
Rejected: No middle ground for users wanting light flavor.

### Auto-Detect from Questions
Rejected: Unreliable, inconsistent experience.

### Separate "Serious Mode" Command
Rejected: Requires remembering to toggle, easy to forget.
