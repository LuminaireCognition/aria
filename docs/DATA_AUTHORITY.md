# Data Authority

**Purpose:** Define authoritative sources for cached data and validation requirements before data is persisted locally.

## Core Principle

> **All data persisted to local cache must be sourced from or validated against authoritative sources.**

Local cache includes:
- Static data files (`src/aria_esi/data/`)
- SQLite databases (`userdata/cache/`)
- Reference files (`reference/`)

## Relationship to Other Documentation

| Document | Focus |
|----------|-------|
| **DATA_AUTHORITY.md** (this file) | Where data comes from, validation before caching |
| **DATA_VERIFICATION.md** | Verifying claims before presenting to user |
| **DATA_SOURCES.md** | External sources for data not in ESI/SDE |

**Key distinction:**
- `DATA_AUTHORITY` = "Is this data valid for the cache?"
- `DATA_VERIFICATION` = "Is this claim valid to tell the user?"

Data that passes authority checks can be trusted when read from cache later. Data that fails authority checks should never be cached.

## Authority Hierarchy

When populating local cache, data must come from these sources in order of preference:

| Priority | Source | Authority Level | Use For |
|----------|--------|-----------------|---------|
| 1 | **ESI** | Authoritative | Alliance IDs, sovereignty, market, pilot data |
| 2 | **SDE** | Authoritative | Item stats, faction IDs, NPC corps, agents |
| 3 | **DOTLAN** | Semi-authoritative | Supplemental reference, alliance lookup |
| 4 | **EVE University Wiki** | Community reference | Mechanics explanations, PvE intel |
| 5 | **Training data** | NOT AUTHORITATIVE | Never cache directly |

### Authoritative Sources

Data from **authoritative sources** (ESI, SDE) can be cached directly after successful retrieval.

### Semi-Authoritative Sources

Data from **semi-authoritative sources** (DOTLAN) should be:
1. Cross-referenced with authoritative sources when possible
2. Validated against ESI/SDE for IDs and names
3. Cached with source annotation

### Non-Authoritative Sources

Data from **training data** or "made up" MUST be validated against an authoritative source before caching.

**CRITICAL:** If data cannot be validated against an authoritative source, it should NOT be cached. Acknowledge the gap and suggest in-game verification.

## Data Type Authority

| Data Type | Authoritative Source | Validation Command |
|-----------|---------------------|-------------------|
| Alliance IDs | ESI `/alliances/{id}/` | `sov-validate` |
| Alliance names | ESI `/alliances/{id}/` | `sov-validate` |
| Faction IDs | SDE `corporation_info` | `sov-validate` |
| Sovereignty map | ESI `/sovereignty/map/` | `sov-update` |
| Coalition membership | Community (DOTLAN) | Manual verification |
| Item stats | SDE `item_info` | N/A (SDE is authoritative) |
| Market prices | ESI `/markets/` | N/A (live query) |
| Pilot data | ESI (authenticated) | N/A (live query) |

## Validation Requirements

### Before Caching Community Data

Community-maintained data (like coalition definitions) MUST be validated before loading into local cache:

```bash
# Validate coalition data against ESI
uv run aria-esi sov-validate

# Auto-fix invalid entries from ESI
uv run aria-esi sov-validate --fix

# Load validated data into database (runs validation first)
uv run aria-esi sov-load-coalitions
```

### Fail-Fast Behavior

Commands that load community data into cache should **fail-fast** if validation fails:

1. Run validation against authoritative source (ESI)
2. If validation fails, refuse to load
3. Report specific failures to user
4. Suggest fix command or manual correction

**Example:** `sov-load-coalitions` validates all alliance IDs against ESI before loading. If any ID is invalid, the command fails with a clear message.

### ESI Unavailable

If ESI is unavailable during validation:

1. **Fail the operation** - do not proceed with unvalidated data
2. **Report clearly** - "ESI unavailable - cannot validate"
3. **Suggest retry** - "Try again when ESI is available"
4. **Provide escape hatch** - `--skip-validation` flag (not recommended)

## Data Flow

```
External Source
     │
     ▼
┌─────────────────────────────────┐
│ Is source authoritative?        │
│ (ESI, SDE)                      │
└─────────────────────────────────┘
     │
     ├── Yes → Cache directly
     │
     ▼ No
┌─────────────────────────────────┐
│ Can data be validated against   │
│ authoritative source?           │
└─────────────────────────────────┘
     │
     ├── Yes → Validate first, then cache
     │
     ▼ No
┌─────────────────────────────────┐
│ DO NOT CACHE                    │
│ • Acknowledge the gap           │
│ • Suggest in-game verification  │
│ • Mark as community-maintained  │
└─────────────────────────────────┘
```

## Cache Freshness

Once data is validated and cached, it is trusted until manually updated:

| Data Type | Validation Frequency | Trigger |
|-----------|---------------------|---------|
| Alliance IDs | On edit | `sov-validate` before commit |
| Sovereignty map | On demand | `sov-update` |
| Coalition membership | Monthly | Community updates |
| Reference files | On contribution | PR review |

**Note:** This differs from live data (wallet, location) which should always be queried fresh. See `DATA_FILES.md` for data freshness rules.

## File-Specific Requirements

### `coalitions.yaml`

**Contains:** Player coalition definitions (community-maintained)
**Authoritative fields:** Alliance IDs (validate via ESI)
**Community fields:** Coalition membership, aliases

```yaml
# REQUIRED: Validate before commit
# Run: uv run aria-esi sov-validate --fix

coalitions:
  imperium:
    alliances:
      - id: 1354830081        # ← MUST be valid ESI alliance ID
        name: "Goonswarm Federation"  # ← MUST match ESI name
```

### `reference/` files

**Contains:** Static game data, mechanics reference
**Source:** SDE, EVE University Wiki, or documented community sources

```yaml
# Source annotation required for non-SDE data
# Source: https://wiki.eveuniversity.org/Agent
# Verified: 2026-02
- "L4 agents require 5.0 standing"
```

### SQLite databases

**Contains:** Cached ESI/SDE data
**Source:** Direct from authoritative APIs
**Validation:** Built-in to fetch commands (`sov-update`)

## CI Integration

The test suite validates cached data integrity:

```bash
# Run as part of test suite
uv run pytest tests/services/sovereignty/test_validation.py
```

Tests verify:
- Alliance IDs in `coalitions.yaml` are valid (mock ESI)
- Faction IDs match SDE
- No duplicate IDs
- Schema version consistency

## Claude Code Instructions

When Claude Code is caching or presenting data:

### Caching Data

1. **Check authority level** of the source
2. **Validate against authoritative source** if community data
3. **Never cache training data** directly
4. **Annotate source** for future reference

### Presenting Cached Data

Data that has been validated and cached can be presented directly without re-validation. The validation happened at cache time.

### Filling Gaps

If authoritative source lacks data:
1. **Do not fill with training data**
2. **Acknowledge the gap** explicitly
3. **Suggest in-game verification** or blessed external source
4. See `DATA_VERIFICATION.md` for gap-handling protocol

## Summary

1. **ESI and SDE are authoritative** - cache directly
2. **Community data must be validated** - against ESI/SDE before caching
3. **Training data is never authoritative** - always validate
4. **Fail-fast on validation failure** - don't cache invalid data
5. **Once validated, data is trusted** - until manually updated
6. **Annotate sources** - for future verification
