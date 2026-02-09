# ADR-001: Multi-Pilot Architecture

**Status:** Accepted
**Date:** 2026-01

## Context

EVE Online accounts can have up to 3 characters, each with independent skills, assets, and standings. Players frequently switch between characters for different activities (main for PvP, alt for industry, etc.).

ARIA initially supported only a single pilot, requiring manual reconfiguration when switching characters.

## Decision

Implement a multi-pilot architecture with:

1. **Pilot Registry** (`userdata/pilots/_registry.json`) tracking all configured pilots
2. **Per-Pilot Directories** (`userdata/pilots/{character_id}_{slug}/`) containing:
   - Profile, operations, ships, goals, projects
   - ESI sync metadata
   - Session context
3. **Active Pilot Selection** via `userdata/config.json`
4. **Credential Isolation** (`userdata/credentials/{character_id}.json`)

### Selection Priority

1. `ARIA_PILOT` environment variable (highest)
2. `active_pilot` field in `userdata/config.json`
3. Legacy: `active_pilot` field in `.aria-config.json`
4. Auto-select if only one pilot exists
5. Prompt user if multiple pilots, no selection

## Consequences

### Positive

- Clean separation of pilot data
- Easy character switching via config change
- No credential conflicts between characters
- Supports common EVE multi-character patterns
- Future-proof for additional pilots

### Negative

- More complex boot sequence (must resolve pilot first)
- Path construction requires registry lookup
- Session context must be pilot-aware
- Skills must handle `{active_pilot}` placeholder

## Alternatives Considered

### Single-Pilot Only
Rejected: Doesn't match how EVE players actually play.

### Environment Variable Only
Rejected: Poor UX, requires shell configuration.

### Prompt Every Session
Rejected: Annoying for single-pilot users (majority).

### Database Storage
Rejected: Overkill for 1-3 pilots, reduces portability.
