# Proposal: Freshness-Gated Auto-Sync Library

## Context

A `/standings` query gave a definitive "you cannot access L3 R&D agents" based on 19-day-old cached standings. The pilot was already running those agents. The cache had explicit `stale_after=2026-01-26` metadata — 18 days overdue — but nothing in the system acted on it.

**Root cause:** No single call exists that checks freshness AND triggers a sync. Staleness logic is scattered across three disconnected mechanisms:

| Component | File | Can Detect Stale? | Can Sync? |
|-----------|------|--------------------|-----------|
| `aria-data-freshness.py` | `.claude/scripts/` | Yes | No |
| `is_skills_cache_stale()` | `src/aria_esi/commands/skills.py:56` | Yes (skills only) | No |
| `sync-profile` command | `src/aria_esi/commands/sync_profile.py` | No | Yes |

Skills are left to manually orchestrate both. None currently do.

## Goal

A single entry point — `ensure_fresh(section)` — that any skill can call. It checks cache age, syncs from ESI if stale and available, and returns a result object the skill can branch on.

## Library API

### New file: `src/aria_esi/core/freshness.py`

```python
@dataclass(frozen=True)
class SyncResult:
    section: str                          # "standings", "skills", etc.
    fresh: bool                           # Within TTL?
    synced_at: str | None                 # ISO 8601 timestamp of cache
    age_hours: float | None               # Hours since last sync
    ttl_hours: float                      # Configured TTL for this section
    refreshed: bool = False               # True if sync was triggered and succeeded
    esi_available: bool = True            # False if ESI was unreachable
    error: str | None = None              # Error message if sync failed
    source: str = "cache"                 # "cache" | "esi" | "missing"


def check_freshness(section: str, pilot_dir: Path | None = None) -> SyncResult:
    """Read-only freshness check. Does not attempt sync."""

def ensure_fresh(section: str, pilot_dir: Path | None = None, force: bool = False) -> SyncResult:
    """Check freshness; if stale AND ESI available, auto-sync. Returns result."""

def is_esi_available(timeout: float = 5.0) -> bool:
    """Lightweight ESI health check via token refresh test."""
```

**Decision tree for `ensure_fresh`:**
1. `check_freshness(section)` → if fresh and not force → return immediately
2. If stale → `is_esi_available()`?
   - Yes → call sync function → re-check → return with `refreshed=True`
   - No → return stale result with `esi_available=False`
3. If sync function raises → catch exception, return `SyncResult` with `error` populated, `refreshed=False`

### Section Registry

Centralizes what's currently duplicated between `aria-data-freshness.py:FRESHNESS_RULES` and hardcoded values in `sync_profile.py` and `skills.py`:

```python
SECTION_REGISTRY: dict[str, SectionConfig] = {
    "standings": SectionConfig(
        ttl_hours=24,
        sync_fn="aria_esi.commands.sync_profile.sync_profile",
        file_template="profile.md",
        format="marker",
        markers=["ESI-SYNC:STANDINGS-EMPIRE:START",
                 "ESI-SYNC:STANDINGS-CORPS:START",
                 "ESI-SYNC:STANDINGS-PIRATES:START"],
    ),
    "skills": SectionConfig(
        ttl_hours=12,
        sync_fn="aria_esi.commands.skills.cmd_sync_skills",
        file_template="skills.json",
        format="json_meta",
        markers=[],
    ),
}
```

`"standings"` is a composite key — one `sync_profile()` call updates all three marker sections atomically.

**Composite freshness rule:** For sections with multiple markers, freshness is determined by the **oldest** marker. A section is fresh only when **all** its markers are within TTL. `age_hours` and `synced_at` reflect the oldest marker. In practice the three standings markers will have near-identical timestamps (written atomically), but the oldest-wins rule is the safe fallback if a partial write ever occurs.

### Freshness parsing

Move `parse_sync_marker()` from `.claude/scripts/aria-data-freshness.py:120-165` into the library. It already handles both formats:
- **Enhanced:** `<!-- ESI-SYNC:SECTION:START ttl_hours=24 synced_at=... stale_after=... -->`
- **Legacy:** parses `*Synced: YYYY-MM-DD HH:MM UTC*` text inside markers

For JSON format (`skills.json`), reuse the `_meta.synced_at` pattern from `is_skills_cache_stale()`.

### ESI availability check

No unified function exists today. `is_esi_available()` will attempt `get_authenticated_client()` with a short timeout. If `CredentialsError` or `ESIError` → False. This tests the actual auth flow (token refresh) rather than the ESI status endpoint, which is itself sometimes unreliable.

## CLI Command

### New file: `src/aria_esi/commands/freshness.py`

```bash
# Check + auto-sync standings if stale
uv run aria-esi ensure-fresh standings

# Check only (no sync attempt)
uv run aria-esi ensure-fresh standings --check-only

# Force sync regardless of freshness
uv run aria-esi ensure-fresh standings --force

# Check all registered sections
uv run aria-esi ensure-fresh all
```

Returns JSON that skills can parse:

```json
{"section": "standings", "fresh": true, "age_hours": 2.5,
 "refreshed": true, "esi_available": true, "source": "esi"}
```

Or when ESI is down:

```json
{"section": "standings", "fresh": false, "age_hours": 450.0,
 "refreshed": false, "esi_available": false, "source": "cache"}
```

When `section` is `all`, returns a JSON **array** of results — one per registered section:

```json
[
  {"section": "standings", "fresh": true, "age_hours": 2.5,
   "refreshed": true, "esi_available": true, "source": "esi"},
  {"section": "skills", "fresh": false, "age_hours": 36.0,
   "refreshed": false, "esi_available": false, "source": "cache"}
]
```

### CLI Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All requested sections fresh (after sync attempts) |
| 1 | One or more sections still stale after sync attempts |
| 2 | Invalid arguments or programming error |

Register in `src/aria_esi/__main__.py` alongside existing commands.

## Enhanced Marker Writing

**Problem:** Profile already has enhanced markers (with `synced_at=`) but `sync_profile.py` only writes legacy `<!-- ESI-SYNC:SECTION:START -->` without metadata. After a sync, the enhanced metadata is lost.

**Fix in `src/aria_esi/commands/sync_profile.py`:**

Add `make_start_marker()` that generates the enhanced format:

```python
def make_start_marker(section_key: str, ttl_hours: float = 24) -> str:
    now = datetime.now(UTC)
    synced_at = now.isoformat().replace("+00:00", "Z")
    stale_after = (now + timedelta(hours=ttl_hours)).isoformat().replace("+00:00", "Z")
    # Produce: <!-- ESI-SYNC:STANDINGS-EMPIRE:START ttl_hours=24 synced_at=... stale_after=... -->
```

Modify `update_section()` (line 108) to use this instead of the static `MARKERS` dict for the start tag. The end marker stays unchanged. The regex in `update_section()` already matches `<!-- ESI-SYNC:SECTION:START ... -->` with any trailing content before `-->`, so backward compatibility is preserved.

## Skill Integration Pattern

The standings skill (and any other skill reading cached data) adds one step before answering eligibility questions:

```markdown
## Freshness Gate (before eligibility checks)

Run: `uv run aria-esi ensure-fresh standings`

| `fresh` | `esi_available` | Action |
|---------|-----------------|--------|
| true    | —               | Use data confidently |
| false   | false           | Use cached + strong staleness warning, refuse definitive eligibility claims if age > 7 days |
| false   | true (sync failed) | Warn and use cached |
```

This replaces the current contradictory guidance (ESI check section says "use cached data" while DO NOT section says "never trust cached data for eligibility").

## Boot Sync Expansion

Add to the existing boot pipeline in `.claude/hooks/aria-boot.d/boot-operations.sh`:

```bash
# Non-blocking standings refresh (background)
(nohup uv run --quiet aria-esi ensure-fresh standings >/dev/null 2>&1 &)
```

This runs alongside the existing `aria-esi-sync.py --quick --quiet` (ships + blueprints). Most sessions will start with fresh standings data, preventing the stale-cache problem before it occurs.

## Phased Delivery

### Phase 1: Core library + CLI *(fixes the original bug)*

| Action | File |
|--------|------|
| Create | `src/aria_esi/core/freshness.py` — `SyncResult`, `SECTION_REGISTRY`, `check_freshness()`, `ensure_fresh()`, `is_esi_available()`, `parse_sync_marker()` (moved from script) |
| Create | `src/aria_esi/commands/freshness.py` — CLI wrapper `ensure-fresh` |
| Modify | `src/aria_esi/__main__.py` — register `ensure-fresh` subcommand |
| Create | `tests/core/test_freshness.py` — unit tests for check/ensure/parse |

**Verification:**
- `uv run pytest tests/core/test_freshness.py -n auto -v`
- `uv run aria-esi ensure-fresh standings --check-only` returns valid JSON
- `uv run aria-esi ensure-fresh standings` triggers sync when stale + ESI available

### Phase 2: Enhanced marker writing

| Action | File |
|--------|------|
| Modify | `src/aria_esi/commands/sync_profile.py` — `make_start_marker()`, modify `update_section()` |
| Modify | `tests/test_sync_profile.py` — verify enhanced markers in output |

**Verification:**
- `uv run aria-esi sync-profile --dry-run` shows enhanced markers in output
- `uv run aria-esi ensure-fresh standings` correctly parses the new markers after a sync

### Phase 3: Consolidation + boot integration

| Action | File |
|--------|------|
| Modify | `.claude/scripts/aria-data-freshness.py` — replace `FRESHNESS_RULES` + `parse_sync_marker()` with imports from library |
| Modify | `src/aria_esi/commands/skills.py` — `is_skills_cache_stale()` delegates to `check_freshness("skills")` |
| Modify | Boot pipeline — add `ensure-fresh standings` to boot sequence |

### Phase 4: Standings skill update

| Action | File |
|--------|------|
| Modify | `.claude/skills/standings/SKILL.md` — replace ESI availability section with freshness gate pattern |

## Key Design Decisions

1. **Library in `core/`, not `commands/`.** Freshness checking is infrastructure. Commands are thin CLI wrappers.
2. **`ensure_fresh` calls existing sync functions** (`sync_profile()`, `cmd_sync_skills()`), not ESI directly. Avoids duplicating formatting/marker logic.
3. **Composite "standings" key.** One `ensure_fresh("standings")` call covers all three marker sections via a single `sync_profile()` invocation.
4. **Synchronous, not async.** The codebase uses synchronous httpx exclusively. Skills invoke via `uv run` subprocess, so async provides no benefit.
5. **`SyncResult` is frozen dataclass.** Type safety and documented contract. CLI converts to dict via `dataclasses.asdict()` for JSON output.
6. **No operational exceptions.** `ensure_fresh` and `check_freshness` never raise for operational failures (network errors, auth failures, sync crashes, missing cache files). All operational failures are represented in the `SyncResult` via the `error`, `fresh`, and `esi_available` fields. Only programmer errors (invalid section key → `KeyError`) raise.
7. **`sync_fn` contract.** Each registry entry's `sync_fn` is a dotted import path to a `(pilot_dir: Path) -> None` callable, resolved at call time via `importlib`. Success is the absence of an exception. After invocation, `ensure_fresh` re-runs `check_freshness` to verify markers actually advanced — a no-op sync (no exception but no update) is treated as a failure with `error="sync completed but markers did not advance"`.

## Files Summary

| File | Phase | Action |
|------|-------|--------|
| `src/aria_esi/core/freshness.py` | 1 | Create |
| `src/aria_esi/commands/freshness.py` | 1 | Create |
| `src/aria_esi/__main__.py` | 1 | Modify (register command) |
| `tests/core/test_freshness.py` | 1 | Create |
| `src/aria_esi/commands/sync_profile.py` | 2 | Modify (enhanced markers) |
| `.claude/scripts/aria-data-freshness.py` | 3 | Modify (import from library) |
| `src/aria_esi/commands/skills.py` | 3 | Modify (delegate to library) |
| Boot pipeline | 3 | Modify (add ensure-fresh) |
| `.claude/skills/standings/SKILL.md` | 4 | Modify (freshness gate) |
