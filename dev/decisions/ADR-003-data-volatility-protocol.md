# ADR-003: Data Volatility Protocol

**Status:** Accepted
**Date:** 2026-01

## Context

EVE Online data varies in how frequently it changes:

- **Stable**: Character name, skills, blueprint library (changes rarely)
- **Semi-stable**: Ship fittings, standings (changes occasionally)
- **Volatile**: Location, wallet balance, current ship (changes constantly)

Proactively mentioning stale volatile data creates confusion ("ARIA says I have 10M ISK but I just spent it").

## Decision

Implement a Data Volatility Protocol:

### Classification

| Category | Examples | Cache | Proactive Mention |
|----------|----------|-------|-------------------|
| Stable | Skills, BPOs, profile | Days | Yes |
| Semi-stable | Fittings, standings | Hours | With timestamp |
| Volatile | Location, wallet, ship | Never | Only on request |

### Rules

1. **Never proactively mention volatile data** (location, wallet, current ship)
2. **Always include query timestamp** in volatile data responses
3. **Add staleness warning** if data older than threshold
4. **Use ESI for volatile data** rather than cached files

### Implementation

- Skills specify `volatility` in output
- Volatile queries include `query_timestamp`
- CLAUDE.md instructs ARIA not to proactively reference volatile data

## Consequences

### Positive

- Reduces user confusion from stale data
- Clear guidance for skill authors
- Timestamps enable users to judge freshness
- Separates "what ARIA knows" from "current game state"

### Negative

- ARIA can't proactively warn about low wallet
- Must query ESI for current state
- Some useful proactive features disabled

## Alternatives Considered

### Always Query Live
Rejected: ESI rate limits, slow responses, unnecessary for stable data.

### Cache Everything
Rejected: Creates confusion when data changes in-game.

### User-Configurable Staleness
Rejected: Adds complexity, most users want sensible defaults.
