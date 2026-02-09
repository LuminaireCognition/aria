# SDE Ground Truth: Eliminating Hardcoded EVE Data

**Status:** PROPOSED (2026-02-08)
**Related:** `sde()` MCP dispatcher, `fitting()` dispatcher, `SDEQueryService`, `fitting/skills.py`

---

## Executive Summary

Replace hardcoded EVE type IDs throughout ARIA's codebase with name-based resolution from the SDE database at startup. This eliminates a class of silent data-corruption bugs where confabulated integer IDs map to the wrong in-game items.

**Motivating incident:** On 2026-02-08, seven of nine entries in `DRONE_SKILL_IDS` were found to be mislabeled. The bonus skill injection at `fitting/skills.py:400` included type ID 3443 (Trade) instead of 3442 (Drone Interfacing), causing `fitting(action="extract_requirements")` to report Trade V as a requirement for any drone fit. Two other IDs mapped to Caldari Drone Specialization and the Prospect (a ship), not the intended drone support skills. The comments described the correct skills with correct effect descriptions, but the integer literals were wrong. A subsequent full audit revealed **23 of 63** hardcoded skill IDs (37%) are wrong across all constants.

**Root cause:** LLMs hallucinated type IDs from training data instead of consulting the SDE database that is cached locally and available to them via MCP tools. The IDs are not random garbage — they are plausible-looking integers in the right numeric neighborhood (e.g., 3426 for "Capacitor Systems Operation" when the real ID is 3417; 3319 for "Advanced Weapon Upgrades" when it's actually 11207). This pattern — correct skill names paired with confidently wrong IDs — is characteristic of LLM confabulation: the model "knows" these skills exist and generates integers that feel right but were never verified against ground truth. The SDE was available via `sde(action="item_info")` at every point these constants were written, but was never queried.

**Proposed fix:** Resolve all skill/type IDs by name from the SDE at startup. A typo in a skill name fails loudly at boot. A confabulated integer fails silently in production for months. This structurally prevents LLMs from introducing this bug class — they write human-readable names (which they get right), and the SDE provides the integers (which it gets right by definition).

---

## Problem Statement

### Current State

ARIA's codebase contains ~230 lines of hardcoded EVE type IDs across six files:

| File | Constants | Lines | Bug risk |
|------|-----------|-------|----------|
| `fitting/skills.py` | `DRONE_SKILL_IDS`, `FITTING_SKILL_IDS`, `TANK_SKILL_IDS`, `NAVIGATION_SKILL_IDS`, `BONUS_SKILL_IDS` | ~100 | **HIGH** — 7 of 9 drone IDs were wrong |
| `archetypes/tank_selection.py` | `TANK_SKILL_IDS` | ~12 | Medium — separate hardcoded mapping, not validated |
| `core/constants.py` | `SHIP_GROUP_IDS` | ~45 | Medium — 45 group IDs, none validated against SDE |
| `core/constants.py` | `TRADE_HUB_STATIONS`, `STATION_NAMES` | ~30 | Low — stable, but duplicated across 3 files |
| `models/sde.py` | `CATEGORY_*`, `META_GROUP_*` | ~15 | Low — these are protocol-level IDs, stable |
| `mcp/sde/tools_easy80.py` | `MULTIPLIER_SKILLS`, `SKILLS_REQUIRING_V` | ~50 | Medium — keyed by name (good), but IDs resolved at runtime via hardcoded fallback |

Additionally, reference YAML files (`ship_efficacy_rules.yaml`, `breakpoint_skills.yaml`, `meta_module_alternatives.yaml`) reference skills by name but are never validated against the SDE. A typo in a YAML skill name silently produces no effect rather than failing.

### The Pattern That Creates Bugs

```python
# This pattern is the source of every bug found on 2026-02-08:
DRONE_SKILL_IDS = [
    3443,  # Drone Interfacing    ← WRONG: 3443 = Trade
    24241, # Drone Sharpshooting  ← WRONG: 24241 = Light Drone Operation
    3442,  # Drone Navigation     ← WRONG: 3442 = Drone Interfacing
    3441,  # Drone Durability     ← WRONG: 3441 = Heavy Drone Operation
]

# Same pattern, still live in the codebase:
FITTING_SKILL_IDS = [
    3318,  # Weapon Upgrades              ← CORRECT
    3426,  # Capacitor Systems Operation  ← WRONG: 3426 = CPU Management (real: 3417)
    3424,  # Capacitor Management         ← WRONG: 3424 = Energy Grid Upgrades (real: 3418)
    3319,  # Advanced Weapon Upgrades     ← WRONG: 3319 = Missile Launcher Operation (real: 11207)
    3421,  # Capacitor Emission Systems   ← WRONG: 3421 = Energy Pulse Weapons (real: 3423)
]
```

The comments are authoritative (they describe real skills correctly), but the integers are confabulated. LLMs generate skill names accurately from training data, but when asked to also produce the corresponding integer IDs, they hallucinate plausible values instead of querying the SDE. This inversion — where the human-readable comment is right and the machine-readable value is wrong — is uniquely dangerous because:

1. **Code review catches neither:** the comments look correct, and integer literals can't be eyeball-verified
2. **LLMs reviewing the code also can't catch it:** they suffer from the same confabulation when verifying IDs
3. **The only reliable verifier is the SDE itself**, which was available but never consulted

### Known Bugs (as of 2026-02-08)

| Location | Bug | Status |
|----------|-----|--------|
| `fitting/skills.py:400` | Trade V injected into all drone fits | **Fixed** (commit ff1d2e9) |
| `fitting/skills.py:207-217` | 7/9 DRONE_SKILL_IDS entries mislabeled | **Fixed** (commit ff1d2e9) |
| `fitting/skills.py:220-229` | TANK_SKILL_IDS had 7 wrong IDs | **Fixed** (commit 0e843d8) |
| `fitting/skills.py:274-279` | BONUS_SKILL_IDS drone section had 4 wrong IDs | **Fixed** (commit ff1d2e9) |
| `fitting/skills.py:288-290` | BONUS_SKILL_IDS tank section: 3394 labeled "Shield Operation" (actually "Repair Systems") | **Open** — label wrong, may indicate ID mismatch |
| `tank_selection.py:82-93` | TANK_SKILL_IDS has 26252 for "Armor Rigging" vs 26253 in fitting/skills.py | **Open** — one file has wrong ID |

**Pre-implementation requirement:** All current ID constants must be audited against SDE before writing name lists.

### Pre-Implementation Audit (COMPLETED 2026-02-08)

Every hardcoded ID was verified against SDE via `sde(action="item_info", item=<name>)`. Results below.

#### Original Audit Table (Known Discrepancies)

| Constant | Name (comment) | Hardcoded ID | SDE ID | Match? | Actually maps to |
|----------|---------------|-------------|---------|--------|-----------------|
| `fitting/skills.py` TANK_SKILL_IDS[6] | Armor Rigging | 26253 | 26253 | **YES** | Armor Rigging |
| `tank_selection.py` TANK_SKILL_IDS | Armor Rigging | 26252 | 26253 | **NO** | 26252 = Jury Rigging |
| `fitting/skills.py` BONUS_SKILL_IDS | 3394 labeled "Shield Operation" | 3394 | 3416 | **NO** | 3394 = Hull Upgrades |
| `tank_selection.py` TANK_SKILL_IDS | 3394 labeled "Repair Systems" | 3394 | 3393 | **NO** | 3394 = Hull Upgrades |
| `fitting/skills.py` BONUS_SKILL_IDS | 3393 labeled "Hull Upgrades" | 3393 | 3394 | **NO** | 3393 = Repair Systems |

**Summary:** `fitting/skills.py` TANK_SKILL_IDS[6] (Armor Rigging = 26253) is correct. All other entries have wrong IDs — the labels and IDs are swapped or offset.

#### Full Audit: All Hardcoded Constants vs SDE Ground Truth

The full audit revealed the bug class is **far wider** than the 5 known discrepancies. The table below covers every hardcoded ID across all constants.

##### DRONE_SKILL_IDS (`fitting/skills.py:207-217`) — 9/9 correct

| Comment | Hardcoded ID | SDE ID | Match? |
|---------|-------------|---------|--------|
| Drones | 3436 | 3436 | YES |
| Light Drone Operation | 24241 | 24241 | YES |
| Medium Drone Operation | 33699 | 33699 | YES |
| Heavy Drone Operation | 3441 | 3441 | YES |
| Drone Avionics | 3437 | 3437 | YES |
| Drone Interfacing | 3442 | 3442 | YES |
| Drone Navigation | 12305 | 12305 | YES |
| Drone Sharpshooting | 23606 | 23606 | YES |
| Drone Durability | 23618 | 23618 | YES |

##### FITTING_SKILL_IDS (`fitting/skills.py:198-204`) — 1/5 correct

| Comment | Hardcoded ID | SDE ID | Match? | Actually maps to |
|---------|-------------|---------|--------|-----------------|
| Weapon Upgrades | 3318 | 3318 | **YES** | Weapon Upgrades |
| Capacitor Systems Operation | 3426 | 3417 | **NO** | 3426 = CPU Management |
| Capacitor Management | 3424 | 3418 | **NO** | 3424 = Energy Grid Upgrades |
| Advanced Weapon Upgrades | 3319 | 11207 | **NO** | 3319 = Missile Launcher Operation |
| Capacitor Emission Systems | 3421 | 3423 | **NO** | 3421 = Energy Pulse Weapons |

##### TANK_SKILL_IDS (`fitting/skills.py:220-229`) — 8/8 correct

| Comment | Hardcoded ID | SDE ID | Match? |
|---------|-------------|---------|--------|
| Mechanics | 3392 | 3392 | YES |
| Hull Upgrades | 3394 | 3394 | YES |
| Shield Operation | 3416 | 3416 | YES |
| Shield Management | 3419 | 3419 | YES |
| Shield Compensation | 21059 | 21059 | YES |
| Shield Upgrades | 3425 | 3425 | YES |
| Armor Rigging | 26253 | 26253 | YES |
| Shield Rigging | 26261 | 26261 | YES |

##### NAVIGATION_SKILL_IDS (`fitting/skills.py:232-239`) — 3/6 correct

| Comment | Hardcoded ID | SDE ID | Match? | Actually maps to |
|---------|-------------|---------|--------|-----------------|
| Navigation | 3449 | 3449 | **YES** | Navigation |
| Afterburner | 3450 | 3450 | **YES** | Afterburner |
| Warp Drive Operation | 3451 | 3455 | **NO** | 3451 = Fuel Conservation |
| Evasive Maneuvering | 3453 | 3453 | **YES** | Evasive Maneuvering |
| Fuel Conservation | 3454 | 3451 | **NO** | 3454 = High Speed Maneuvering |
| Acceleration Control | 3456 | 3452 | **NO** | 3456 = Jump Drive Operation |

##### BONUS_SKILL_IDS (`fitting/skills.py:274-297`) — 9/16 correct

**Entry count verified:** `len(BONUS_SKILL_IDS) == 16` (confirmed against live codebase: lines 274–297, keys 3442, 23606, 12305, 23618, 3318, 3319, 3426, 3424, 3392, 3393, 3394, 3416, 3449, 3453, 3456, 3413). The new name lists contain `len(BONUS_DRONE_SKILL_NAMES) == 4` and `len(BONUS_CORE_SKILL_NAMES) == 12`. After deduplication (drone skills overlap), the unique bonus skill count is 16 — equal to the old `len(BONUS_SKILL_IDS)`. However, the composition differs: Power Grid Management is added, and Repair Systems is removed (it was never intended as a core bonus skill — its presence was a bug caused by swapped IDs). The term "superset" refers specifically to `BONUS_CORE_SKILL_NAMES` (12 entries) being a superset of the old inline `core_skills` dict (7 entries at `fitting/skills.py:405-413`), not the overall bonus set.

| Hardcoded ID | Label | SDE ID for label | Match? | Actually maps to |
|-------------|-------|-----------------|--------|-----------------|
| 3442 | Drone Interfacing | 3442 | **YES** | — |
| 23606 | Drone Sharpshooting | 23606 | **YES** | — |
| 12305 | Drone Navigation | 12305 | **YES** | — |
| 23618 | Drone Durability | 23618 | **YES** | — |
| 3318 | Weapon Upgrades | 3318 | **YES** | — |
| 3319 | Advanced Weapon Upgrades | 11207 | **NO** | 3319 = Missile Launcher Operation |
| 3426 | Capacitor Systems Operation | 3417 | **NO** | 3426 = CPU Management |
| 3424 | Capacitor Management | 3418 | **NO** | 3424 = Energy Grid Upgrades |
| 3392 | Mechanics | 3392 | **YES** | — |
| 3393 | Hull Upgrades | 3394 | **NO** | 3393 = Repair Systems |
| 3394 | Shield Operation | 3416 | **NO** | 3394 = Hull Upgrades |
| 3416 | Shield Management | 3419 | **NO** | 3416 = Shield Operation |
| 3449 | Navigation | 3449 | **YES** | — |
| 3453 | Evasive Maneuvering | 3453 | **YES** | — |
| 3456 | Acceleration Control | 3452 | **NO** | 3456 = Jump Drive Operation |
| 3413 | Power Grid Management | 3413 | **YES** | — |

##### Inline core_skills list (`fitting/skills.py:405-413`) — 4/7 correct

The `core_skills` variable at line 405 is a **list of integer IDs** (not a dict). It is iterated with `for skill_id in core_skills:` to inject bonus skills into the extracted skill set.

| Comment | Hardcoded ID | SDE ID | Match? | Actually maps to |
|---------|-------------|---------|--------|-----------------|
| Weapon Upgrades | 3318 | 3318 | **YES** | — |
| Capacitor Systems Operation | 3426 | 3417 | **NO** | 3426 = CPU Management |
| Capacitor Management | 3424 | 3418 | **NO** | 3424 = Energy Grid Upgrades |
| Mechanics | 3392 | 3392 | **YES** | — |
| Hull Upgrades | 3393 | 3394 | **NO** | 3393 = Repair Systems |
| Navigation | 3449 | 3449 | **YES** | — |
| Evasive Maneuvering | 3453 | 3453 | **YES** | — |

##### Inline drone bonus IDs (`fitting/skills.py:400`) — 4/4 correct

| Comment | Hardcoded ID | SDE ID | Match? |
|---------|-------------|---------|--------|
| Drone Interfacing | 3442 | 3442 | YES |
| Drone Sharpshooting | 23606 | 23606 | YES |
| Drone Navigation | 12305 | 12305 | YES |
| Drone Durability | 23618 | 23618 | YES |

##### TANK_SKILL_IDS (`tank_selection.py:82-93`) — 2/8 correct

| Name key | Hardcoded ID | SDE ID | Match? | Actually maps to |
|----------|-------------|---------|--------|-----------------|
| Hull Upgrades | 3393 | 3394 | **NO** | 3393 = Repair Systems |
| Mechanics | 3392 | 3392 | **YES** | — |
| Repair Systems | 3394 | 3393 | **NO** | 3394 = Hull Upgrades |
| Armor Rigging | 26252 | 26253 | **NO** | 26252 = Jury Rigging |
| Shield Management | 3416 | 3419 | **NO** | 3416 = Shield Operation |
| Shield Operation | 3419 | 3416 | **NO** | 3419 = Shield Management |
| Shield Upgrades | 21059 | 3425 | **NO** | 21059 = Shield Compensation |
| Tactical Shield Manipulation | 3420 | 3420 | **YES** | — |

#### Audit Summary

| Constant | File | Total | Correct | Wrong | Accuracy |
|----------|------|-------|---------|-------|----------|
| DRONE_SKILL_IDS | fitting/skills.py | 9 | 9 | 0 | 100% |
| TANK_SKILL_IDS | fitting/skills.py | 8 | 8 | 0 | 100% |
| FITTING_SKILL_IDS | fitting/skills.py | 5 | 1 | 4 | **20%** |
| NAVIGATION_SKILL_IDS | fitting/skills.py | 6 | 3 | 3 | **50%** |
| BONUS_SKILL_IDS | fitting/skills.py | 16 | 9 | 7 | **56%** |
| Inline core_skills | fitting/skills.py:405 | 7 | 4 | 3 | **57%** |
| Inline drone bonus | fitting/skills.py:400 | 4 | 4 | 0 | 100% |
| TANK_SKILL_IDS | tank_selection.py | 8 | 2 | 6 | **25%** |
| **TOTAL** | | **63** | **40** | **23** | **63%** |

**37% of all hardcoded skill IDs are wrong.** The recently fixed DRONE_SKILL_IDS and TANK_SKILL_IDS in `fitting/skills.py` (commits ff1d2e9 and 0e843d8) are now correct, but FITTING_SKILL_IDS, NAVIGATION_SKILL_IDS, BONUS_SKILL_IDS, the inline core_skills, and `tank_selection.py` TANK_SKILL_IDS remain broken.

**Implication for the proposal:** These are live bugs. The FITTING_SKILL_IDS, NAVIGATION_SKILL_IDS, and inline core_skills bugs affect `extract_skills_for_fit()` and `get_relevant_skills_for_fit()` output for every fit processed. The `tank_selection.py` bugs affect tank archetype scoring. All must be fixed — either as a pre-implementation hotfix (like the drone/tank fixes in ff1d2e9 and 0e843d8) or as part of Phase C/D migration to name-based resolution.

---

## Proposed Solution

### New SDE Query Methods

Add one method and one exception to `SDEQueryService` in `queries.py`:

#### 1. `resolve_skill_ids(names: list[str]) -> dict[str, int]`

Batch skill name-to-ID resolution. Returns a dict mapping each name to its `type_id`. Raises on any unresolved name. Searches only `category_id = 16` (Skills). For non-skill type resolution, use existing `SDEQueryService` methods (e.g., `get_station_info()` for stations).

```python
def resolve_skill_ids(self, names: list[str]) -> dict[str, int]:
    """
    Resolve skill names to type IDs from the SDE database.

    Searches only category_id=16 (Skills). For non-skill type resolution,
    use existing SDEQueryService methods (e.g., get_station_info() for stations).

    Args:
        names: List of exact skill names (case-insensitive)

    Returns:
        Dict mapping each input name to its type_id

    Raises:
        SDEResolutionError: If any name cannot be resolved in the Skills category

    Note: Does not filter on ``published`` — all skills in category 16 are
    considered, including unpublished. This is intentional: skill type IDs are
    used as dictionary keys for pilot skill lookups, where the SDE record must
    match regardless of publish status.
    """
    self._check_cache_validity()
    self.ensure_sde_seeded()
    if not names:
        return {}
    conn = self._db._get_connection()
    lower_to_original = {n.lower(): n for n in names}
    placeholders = ",".join("?" * len(lower_to_original))
    rows = conn.execute(
        f"SELECT type_name_lower, type_id FROM types "
        f"WHERE type_name_lower IN ({placeholders}) AND category_id = 16",
        list(lower_to_original.keys()),
    ).fetchall()

    found = {}
    for lower_name, type_id in rows:
        if lower_name in found:
            raise SDEResolutionError(
                f"Ambiguous skill name '{lower_to_original[lower_name]}': "
                f"multiple matches in SDE",
                missing_names=[lower_to_original[lower_name]],
            )
        found[lower_name] = type_id

    missing = [lower_to_original[ln] for ln in lower_to_original if ln not in found]
    if missing:
        raise SDEResolutionError(
            f"Cannot resolve {len(missing)} type names from SDE: {missing}",
            missing_names=missing,
        )
    return {lower_to_original[ln]: tid for ln, tid in found.items()}
```

**Why batch SQL:** A single `SELECT ... IN (...)` query resolving 30 names is both cleaner and atomic — no risk of cache invalidation between individual queries if `_check_cache_validity()` detects a mid-session SDE reimport. The "fail if any are missing" behavior is explicit via the `missing` check after the single query.

**Internal API note:** `self._db._get_connection()` is the standard accessor used by all existing `SDEQueryService` methods (e.g., `get_meta_group()` at line 882, `get_station_info()` at line 544, `get_category_id()` at line 399 — 16+ methods total). Despite the underscore prefix, this is the established internal pattern — `_db` is the `MarketDatabase` instance injected at construction (`__init__` at line 175), and `_get_connection()` returns the thread-local SQLite connection. Do not replace with an alternative accessor.

**Threading:** `resolve_skill_ids()` does not cache its own results — each call queries the SDE directly. It calls `_check_cache_validity()` for SDE freshness validation (consistent with all other public `SDEQueryService` methods) and `ensure_sde_seeded()` before querying. The batch SQL query is atomic within a single connection, so there is no window for stale/fresh data mixing. Skill name resolution happens once at startup via `get_skill_registry()`, so per-call caching adds complexity with no benefit. An empty input list returns `{}` without error.

**Concurrent call safety:** If two threads call `resolve_skill_ids()` simultaneously and `_check_cache_validity()` triggers a cache reset between one thread's validity check and its query, the query still executes correctly — SQLite connections are thread-local (via `_get_connection()`), and the `types` table data is immutable within a single SDE import. The race is benign.

**Invariant:** `_check_cache_validity()` MUST NOT clear or reset the `SkillRegistry` singleton. The registry's lifecycle is process-scoped (initialized once, never refreshed), while `_check_cache_validity()` handles session-scoped SDE cache invalidation. These are deliberately independent — the registry freezes skill IDs at process start, and a mid-session SDE reimport requires a process restart to take effect.

**Duplicate input handling:** If the same name appears multiple times in the input list, `lower_to_original` deduplicates by lowercase key, keeping the last original-case spelling. The returned dict contains one entry per unique (case-insensitive) name. This is benign — callers use `sorted(set(...))` for `ALL_SKILL_NAMES` anyway.

**SQLite parameter limit:** The batch `IN (...)` query is bounded by `SQLITE_MAX_VARIABLE_NUMBER` (default 999 in SQLite <3.32.0, 32766 in 3.32.0+). With `ALL_SKILL_NAMES` containing 31 entries, this limit is never approached. If future extensions grow the name list beyond ~900 entries, partition the query into batches.

**Return key casing contract:** The returned dict keys use the *caller's input casing*, not the SDE canonical casing. If the caller passes `"drone interfacing"`, the key is `"drone interfacing"`. The `SkillRegistry` constructor receives these keys, so callers MUST pass names matching the canonical casing in `ALL_SKILL_NAMES` to ensure `registry.id("Drone Interfacing")` works. This is guaranteed by construction — `get_skill_registry()` passes `ALL_SKILL_NAMES` directly, which contains title-cased names matching the SDE `type_name` field.

### SkillRegistry: Centralized Name-to-ID Resolution

**New file:** `src/aria_esi/fitting/skill_registry.py`

A thin startup-time resolver that replaces all hardcoded skill ID constants:

```python
"""
Skill Registry — SDE-backed name-to-ID resolution.

Replaces hardcoded skill ID lists with names resolved from the SDE
at startup. A typo in a skill name fails at boot instead of silently
mapping to the wrong type ID in production.
"""

from __future__ import annotations

from aria_esi.core.logging import get_logger

logger = get_logger(__name__)


class SkillRegistry:
    """
    Registry of skill name-to-ID mappings resolved from the SDE.

    Usage:
        registry = get_skill_registry()
        drone_interfacing_id = registry.id("Drone Interfacing")  # 3442
        drone_ids = registry.ids(DRONE_SKILL_NAMES)  # [3436, 24241, ...]
    """

    def __init__(self, resolved: dict[str, int]):
        self._by_name = resolved
        self._by_id = {v: k for k, v in resolved.items()}

    def id(self, name: str) -> int:
        """Get type ID for a skill name. Raises KeyError if not registered."""
        return self._by_name[name]

    def ids(self, names: list[str]) -> list[int]:
        """Get type IDs for a list of skill names, in input order.

        All names must be registered (present in ALL_SKILL_NAMES).
        Raises KeyError on the first name missing from the registry,
        consistent with ``id()`` behavior.
        """
        return [self._by_name[n] for n in names]

    def name(self, type_id: int) -> str | None:
        """Reverse lookup: type ID to name."""
        return self._by_id.get(type_id)

    def contains(self, name: str) -> bool:
        return name in self._by_name


# Skill names that the fitting module needs — the ONLY source of truth
# is the name string. The integer ID comes from the SDE at startup.

DRONE_SKILL_NAMES = [
    "Drones",
    "Light Drone Operation",
    "Medium Drone Operation",
    "Heavy Drone Operation",
    "Drone Avionics",
    "Drone Interfacing",
    "Drone Navigation",
    "Drone Sharpshooting",
    "Drone Durability",
]

FITTING_SKILL_NAMES = [
    "Weapon Upgrades",
    "Advanced Weapon Upgrades",
    "Capacitor Systems Operation",
    "Capacitor Management",
    "Capacitor Emission Systems",
]

TANK_SKILL_NAMES = [
    "Mechanics",
    "Hull Upgrades",
    "Repair Systems",
    "Shield Operation",
    "Shield Management",
    "Shield Compensation",
    "Shield Upgrades",
    "Tactical Shield Manipulation",
    "Armor Rigging",
    "Shield Rigging",
]

NAVIGATION_SKILL_NAMES = [
    "Navigation",
    "Afterburner",
    "Warp Drive Operation",
    "Evasive Maneuvering",
    "Fuel Conservation",
    "Acceleration Control",
]

BONUS_DRONE_SKILL_NAMES = [
    "Drone Interfacing",
    "Drone Sharpshooting",
    "Drone Navigation",
    "Drone Durability",
]

BONUS_CORE_SKILL_NAMES = [
    # Fitting skills
    "Weapon Upgrades",
    "Advanced Weapon Upgrades",
    # Capacitor skills
    "Capacitor Systems Operation",
    "Capacitor Management",
    # Tank skills
    "Mechanics",
    "Hull Upgrades",
    "Shield Operation",
    "Shield Management",
    # Navigation skills
    "Navigation",
    "Evasive Maneuvering",
    "Acceleration Control",
    # Engineering skills
    "Power Grid Management",
]

# All skill names the registry must resolve at startup
ALL_SKILL_NAMES = sorted(set(
    DRONE_SKILL_NAMES
    + FITTING_SKILL_NAMES
    + TANK_SKILL_NAMES
    + NAVIGATION_SKILL_NAMES
    + BONUS_DRONE_SKILL_NAMES
    + BONUS_CORE_SKILL_NAMES
))


import threading

_skill_registry: SkillRegistry | None = None
_registry_lock = threading.Lock()
_registry_attempted = False


def get_skill_registry() -> SkillRegistry | None:
    """
    Get or create the skill registry (thread-safe, singleton).

    On first call, resolves all skill names from the SDE.
    Returns None if SDE is unavailable (logs warning).
    After a failed attempt, returns None immediately on subsequent calls
    to avoid retry storms — SDE unavailability requires process restart.

    The lazy import of ``get_sde_query_service`` inside the function body
    is deliberate: it prevents circular imports between ``fitting/`` and
    ``mcp/sde/``. Do not move it to module level.
    """
    global _skill_registry, _registry_attempted

    if _skill_registry is not None:
        return _skill_registry

    with _registry_lock:
        # Double-checked locking: another thread may have initialized
        if _skill_registry is not None:
            return _skill_registry
        if _registry_attempted:
            return None  # already failed, don't retry until restart

        try:
            from aria_esi.mcp.sde.queries import (
                get_sde_query_service,
                SDEResolutionError,
            )

            sde = get_sde_query_service()
            resolved = sde.resolve_skill_ids(ALL_SKILL_NAMES)
            _skill_registry = SkillRegistry(resolved)
            logger.info("Skill registry initialized: %d skills resolved", len(resolved))
            return _skill_registry
        except SDEResolutionError as e:
            _registry_attempted = True
            logger.error(
                "Skill registry failed — %d names not found in SDE: %s",
                len(e.missing_names),
                e.missing_names,
            )
            return None
        except Exception as e:
            _registry_attempted = True
            logger.warning("Skill registry unavailable (SDE infrastructure): %s", e)
            return None


def reset_skill_registry() -> None:
    """Reset registry state for testing. Not for production use."""
    global _skill_registry, _registry_attempted
    with _registry_lock:
        _skill_registry = None
        _registry_attempted = False
```

### Behavioral Changes from Migration

The migration introduces intentional changes to bonus skill injection relative to the old (buggy) code. These are documented here so implementers and reviewers can distinguish bug fixes from deliberate design changes.

#### Bonus core skill injection (`extract_skills_for_fit()`)

The old inline `core_skills` dict at `fitting/skills.py:405-413` contained 7 entries. `BONUS_CORE_SKILL_NAMES` contains 12 — a deliberate superset reflecting the intended design rather than the accidentally-truncated old list.

| Change | Old behavior | New behavior | Rationale |
|--------|-------------|--------------|-----------|
| Repair Systems | Accidentally injected (ID 3393 labeled "Hull Upgrades") | Not injected as bonus | Repair Systems is a tank skill, not a core fitting skill. Still available via `TANK_SKILL_NAMES` in `get_relevant_skills_for_fit()`. |
| Advanced Weapon Upgrades | Not injected (ID 3319 = Missile Launcher Op) | Injected as bonus | Was intended but wrong ID prevented it. Core fitting skill. |
| Shield Operation / Shield Management | Swapped IDs — one injected as the other | Both correctly injected | Bug fix. |
| Acceleration Control | Not injected (ID 3456 = Jump Drive Op) | Injected as bonus | Was intended but wrong ID prevented it. Core navigation skill. |
| Power Grid Management | Not in old inline `core_skills` | Injected as bonus | Intentional addition — PG Management is a universal fitting skill. |

#### Relevant skill lists (`get_relevant_skills_for_fit()`)

`TANK_SKILL_NAMES` is a 10-entry union of the old `fitting/skills.py` TANK_SKILL_IDS (8 entries) and `tank_selection.py` TANK_SKILL_IDS (8 entries, partially overlapping). This means `get_relevant_skills_for_fit()` will now return two skills it previously excluded:

| Skill | Previously in fitting TANK_SKILL_IDS? | Previously in tank_selection TANK_SKILL_IDS? | In unified TANK_SKILL_NAMES? |
|-------|---------------------------------------|---------------------------------------------|------------------------------|
| Repair Systems | No | Yes | **Yes** — intentional: relevant to armor fits |
| Tactical Shield Manipulation | No | Yes | **Yes** — intentional: relevant to shield fits |
| Shield Compensation | Yes | No | **Yes** — carried forward |
| Shield Rigging | Yes | No | **Yes** — carried forward |

The unified list is intentional. Both consumers (fitting analysis and tank archetype scoring) benefit from the full set. If a future need arises for consumer-specific subsets, they can filter from the unified list rather than maintaining parallel lists.

#### Branching logic (`get_relevant_skills_for_fit()`)

The current code conditionally includes tank skills only for `"armor_tank"` and `"shield_tank"` fit types. The `"generic"` and `"drone_boat"` types return only FITTING + NAVIGATION (no tank). The migrated code preserves this branching logic exactly. If a future change wants to always include tank skills for all fit types, it should be made as a separate deliberate change with its own rationale.

| Fit type | Skill categories included (before and after) |
|----------|----------------------------------------------|
| `"generic"` | FITTING + NAVIGATION |
| `"drone_boat"` | FITTING + DRONE + NAVIGATION |
| `"armor_tank"` | FITTING + TANK + NAVIGATION |
| `"shield_tank"` | FITTING + TANK + NAVIGATION |

#### `tank_selection.py` database fallback removal

The old `resolve_skill_name_to_id()` fell back to `MarketDatabase.resolve_type_name()` for names not in the hardcoded dict. The migrated version uses the registry only. Skills not in the pre-registered `ALL_SKILL_NAMES` set will return `None`. If `tank_selection.py` consumers reference skills outside the registered set (e.g., from YAML configs that list "EM Armor Compensation"), those must be added to `TANK_SKILL_NAMES` or resolved separately via `sde.resolve_skill_ids()`.

---

### Migration of Existing Code

#### `fitting/skills.py` — Before and After

**Before** (hardcoded IDs, proven wrong):
```python
DRONE_SKILL_IDS = [
    3436,   # Drones
    24241,  # Light Drone Operation
    ...
]

if has_drones:
    for skill_id in [3442, 23606, 12305, 23618]:
        if skill_id not in skills:
            skills[skill_id] = level
```

**After** (names resolved from SDE, with `None`-registry guard):
```python
from aria_esi.fitting.skill_registry import (
    get_skill_registry,
    BONUS_DRONE_SKILL_NAMES,
    BONUS_CORE_SKILL_NAMES,
)

if has_drones:
    registry = get_skill_registry()
    if registry is not None:
        for skill_id in registry.ids(BONUS_DRONE_SKILL_NAMES):
            if skill_id not in skills:
                skills[skill_id] = level
    else:
        logger.warning("Skill registry unavailable — skipping drone bonus injection")

# Core bonus skills
registry = get_skill_registry()
if registry is not None:
    for skill_id in registry.ids(BONUS_CORE_SKILL_NAMES):
        if skill_id not in skills:
            skills[skill_id] = level
else:
    logger.warning("Skill registry unavailable — skipping core bonus injection")
```

**`get_relevant_skills_for_fit()` — Before and After**

This function is a primary consumer of all four skill ID lists. Its entire return value depends on the registry.

**Before** (hardcoded IDs):
```python
def get_relevant_skills_for_fit(fit_type: str = "generic") -> list[int]:
    # Start with common skills
    skills = list(FITTING_SKILL_IDS)

    if fit_type == "drone_boat":
        skills.extend(DRONE_SKILL_IDS)
    elif fit_type == "armor_tank":
        skills.extend(TANK_SKILL_IDS)
    elif fit_type == "shield_tank":
        skills.extend(TANK_SKILL_IDS)

    # Always include navigation
    skills.extend(NAVIGATION_SKILL_IDS)
    return list(set(skills))
```

**After** (registry-backed, with `None`-registry guard):
```python
from aria_esi.fitting.skill_registry import (
    get_skill_registry,
    DRONE_SKILL_NAMES,
    FITTING_SKILL_NAMES,
    TANK_SKILL_NAMES,
    NAVIGATION_SKILL_NAMES,
)

def get_relevant_skills_for_fit(fit_type: str = "generic") -> list[int]:
    """Return relevant skill IDs for a fit type, or empty list if registry unavailable."""
    registry = get_skill_registry()
    if registry is None:
        logger.warning(
            "Skill registry unavailable — returning empty skill list for fit type '%s'",
            fit_type,
        )
        return []

    skill_names = list(FITTING_SKILL_NAMES)

    if fit_type == "drone_boat":
        skill_names += DRONE_SKILL_NAMES
    elif fit_type in ("armor_tank", "shield_tank"):
        skill_names += TANK_SKILL_NAMES

    skill_names += NAVIGATION_SKILL_NAMES
    return registry.ids(list(dict.fromkeys(skill_names)))  # deduplicated, order-preserved
```

**`None`-registry behavior for `get_relevant_skills_for_fit()`:** Returns `[]`. Callers already handle this gracefully — `get_relevant_skills_for_fit()` is used to *filter* which skills to display in fit analysis output. An empty list means "no supplementary skills shown," not "fit analysis fails." The core skill extraction path (`extract_skills_for_fit()` → EOS data) is unaffected.

#### `BONUS_SKILL_IDS` Usage Audit

`BONUS_SKILL_IDS` is a `dict[int, str]` (ID → name) at lines 274-297. All usages audited:

| Location | Usage pattern | Migration |
|----------|--------------|-----------|
| `extract_skills_for_fit()` lines 398-413 | Forward iteration: loops over IDs to inject into skills dict | Use `registry.ids(BONUS_DRONE_SKILL_NAMES)` and `registry.ids(BONUS_CORE_SKILL_NAMES)` |

**No reverse-lookup consumers exist.** The dict format `{id: "name"}` served only as inline documentation. The `SkillRegistry.name()` method is provided for future use but is not needed for this migration. `BONUS_SKILL_IDS` is replaced entirely by the two name lists + `registry.ids()`.

---

**`None`-registry contract:** When `get_skill_registry()` returns `None` (SDE unavailable), all call sites MUST guard with `if registry is not None` and log a warning. Bonus skill injection is skipped — fits will still work but without bonus skills in the output. This is preferred over crashing, since bonus skills are supplementary to the core skill extraction from EOS. `get_relevant_skills_for_fit()` returns `[]`, which downstream consumers handle as "no supplementary skills" (see above).

The hardcoded `DRONE_SKILL_IDS`, `FITTING_SKILL_IDS`, `TANK_SKILL_IDS`, `NAVIGATION_SKILL_IDS`, and `BONUS_SKILL_IDS` constants are deleted entirely. Their consumers use the registry instead.

#### `archetypes/tank_selection.py` — Already Half-Migrated

This file already has a `resolve_skill_name_to_id()` function that checks hardcoded IDs first, then falls back to the database. The proposal replaces it:

**Before:**
```python
TANK_SKILL_IDS: dict[str, int] = {
    "Hull Upgrades": 3393,
    "Mechanics": 3392,
    ...
}

def resolve_skill_name_to_id(skill_name: str) -> int | None:
    if skill_name in TANK_SKILL_IDS:
        return TANK_SKILL_IDS[skill_name]
    # fallback to database...
```

**After:**
```python
from aria_esi.fitting.skill_registry import get_skill_registry

def resolve_skill_name_to_id(skill_name: str) -> int | None:
    """Resolve skill name to type ID via the shared registry.

    Returns None if registry is unavailable or name is not in the
    pre-registered set. Callers receiving None should treat the skill
    as unresolvable (log and skip).
    """
    registry = get_skill_registry()
    if registry is None:
        logger.warning("Skill registry unavailable — cannot resolve '%s'", skill_name)
        return None
    if not registry.contains(skill_name):
        logger.warning("Skill '%s' not in registry — not a pre-registered skill. Add to TANK_SKILL_NAMES if this is intentional.", skill_name)
        return None
    return registry.id(skill_name)
```

The hardcoded `TANK_SKILL_IDS` dict is deleted.

#### `mcp/sde/tools_easy80.py` — Keys Stay as Names

`MULTIPLIER_SKILLS` and `SKILLS_REQUIRING_V` are already keyed by name (good). Their consumers use `sde(action="item_info", item=name)` to resolve IDs at runtime. No change needed — these are already following the right pattern.

---

## What Stays Hardcoded

Not all hardcoded data should be migrated. Three categories are better left as constants:

### 1. Protocol-Level IDs (Stable, Low Risk)

| Constant | Value | Rationale |
|----------|-------|-----------|
| `CATEGORY_SHIP` | 6 | SDE schema constant. Changes only when CCP restructures categories. |
| `CATEGORY_SKILL` | 16 | Same. Used in SQL WHERE clauses. |
| `META_GROUP_TECH_II` | 2 | Same. |
| `ACTIVITY_TYPES` | {1: "Manufacturing", ...} | ESI enum values. |
| `SLOT_ORDER` | {"LoSlot0": 0, ...} | ESI flag strings. |
| `HIGH_SEC_THRESHOLD` | 0.45 | Game mechanics constant. |

These are structural constants embedded in the EVE data model. Querying the SDE for `get_category_id("Ship")` at every call site adds latency for zero safety benefit — these IDs have been stable for 20+ years.

**Recommendation:** Keep hardcoded but import from `models/sde.py` instead of using inline magic numbers. Existing inline `16` references should use `CATEGORY_SKILL`.

### 2. Curated Analysis Data (Human-Authored, Not in SDE)

| File | Lines | Content |
|------|-------|---------|
| `ship_efficacy_rules.yaml` | 882 | Role-to-skill importance weights |
| `breakpoint_skills.yaml` | 186 | Non-linear unlock thresholds |
| `meta_module_alternatives.yaml` | 370 | T1/T2 substitution advice |
| `damage_profiles.yaml` | ~100 | NPC faction damage types |

The SDE knows that Drone Interfacing gives +10% per level, but it has no concept of "this skill is high priority for a drone boat." That's human analysis. These files must remain as authored reference data.

**Recommendation:** Add startup validation — resolve every skill name in these YAML files against the SDE and warn on mismatch. This catches typos without removing the curated content.

### 3. EOS Vendored Constants (Do Not Touch)

The `_vendor/eos/const/eve.py` file contains `AttrId`, `EffectId`, and `TypeCategoryId` enums with 120+ hardcoded IDs. These are part of the vendored EOS fitting engine and must not be modified — they're synchronized with the EOS data export process.

### 4. Trade Hub Configuration

| Constant | Recommendation |
|----------|----------------|
| `TRADE_HUB_REGIONS` | Keep — these define which hubs ARIA considers "major" (a policy choice, not SDE data) |
| `TRADE_HUB_STATIONS` | Keep — maps region IDs to station IDs for policy-defined "major" trade hubs. Station IDs are stable, no bugs exist, and the mapping is a configuration choice. Migration deferred to a future proposal if needed. |
| `STATION_NAMES` | **Delete** — duplicates `TRADE_HUB_STATIONS` with reversed keys |
| `DEFAULT_STATION_ID` in `market/clients.py` | Keep — policy constant (Jita as default) |

### 5. Ship Group IDs

`SHIP_GROUP_IDS` in `core/constants.py` lists 45 group IDs for filtering assembled ships from assets. This can be replaced with a startup query:

```python
SELECT DISTINCT group_id FROM groups WHERE category_id = 6
```

This also future-proofs against CCP adding new ship classes (which they do periodically).

---

## YAML Validation Layer

For curated reference files that can't be replaced but reference SDE entities by name, add a validation pass at MCP server startup:

Each YAML file has a different schema, so validation uses per-file extractors that return skill name strings for SDE checking.

**Verified YAML schemas (representative snippets):**

`ship_efficacy_rules.yaml` — `ship_roles` → role → `skills` → `skill`:
```yaml
ship_roles:
  drone_boat:
    skills:
      - skill: Drones
        effect: "+5% drone damage and HP per level"
        per_level: 5
        category: weapon
      - skill: Drone Interfacing
        ...
```

`breakpoint_skills.yaml` — top-level keys are skill names:
```yaml
Drones:
  breakpoint_level: 5
  effect: "Unlocks 5th active drone (25% damage increase)"
  impact: "critical"
Advanced Weapon Upgrades:
  breakpoint_level: 5
  ...
```

`meta_module_alternatives.yaml` — category → module → `requires_v` (list of skill names):
```yaml
armor_repairers:
  Small Armor Repairer II:
    requires_v:
      - Mechanics
    meta_alternative:
      name: Small I-a Enduring Armor Repairer
      effectiveness: 89
```

Extractors below match these schemas:

```python
def _extract_skill_names_efficacy(yaml_data: dict) -> list[tuple[str, str]]:
    """Extract (context, skill_name) pairs from ship_efficacy_rules.yaml."""
    if not isinstance(yaml_data, dict):
        return []
    results = []
    for role_name, role_data in yaml_data.get("ship_roles", {}).items():
        if not isinstance(role_data, dict):
            continue
        for skill_entry in role_data.get("skills", []):
            if not isinstance(skill_entry, dict):
                continue
            skill_name = skill_entry.get("skill")
            if skill_name:
                results.append((f"role '{role_name}'", skill_name))
    return results


def _extract_skill_names_breakpoints(yaml_data: dict) -> list[tuple[str, str]]:
    """Extract (context, skill_name) pairs from breakpoint_skills.yaml.

    Schema: top-level keys are skill names (e.g., "Drones", "Advanced Weapon Upgrades").
    Each key maps to a dict of properties (breakpoint_level, effect, etc.).
    """
    if not isinstance(yaml_data, dict):
        return []
    return [("breakpoint", skill_name) for skill_name in yaml_data.keys()]


def _extract_skill_names_meta_alternatives(yaml_data: dict) -> list[tuple[str, str]]:
    """Extract (context, skill_name) pairs from meta_module_alternatives.yaml.

    Schema: category → module_name → {requires_v: ["Skill Name", ...], ...}
    The requires_v field lists skills required at level V for the T2 module.
    """
    if not isinstance(yaml_data, dict):
        return []
    results = []
    for category, modules in yaml_data.items():
        if not isinstance(modules, dict):
            continue
        for module_name, props in modules.items():
            if not isinstance(props, dict):
                continue
            for skill_name in props.get("requires_v", []):
                if isinstance(skill_name, str):
                    results.append((f"module '{module_name}'", skill_name))
    return results


# Extractor registry — maps filename stems to their extractors
from collections.abc import Callable

YAML_SKILL_EXTRACTORS: dict[str, Callable] = {
    "ship_efficacy_rules": _extract_skill_names_efficacy,
    "breakpoint_skills": _extract_skill_names_breakpoints,
    "meta_module_alternatives": _extract_skill_names_meta_alternatives,
}


def validate_yaml_skill_references(
    yaml_data: dict, source: str, extractor_key: str,
) -> list[str]:
    """
    Validate that all skill names in a YAML config resolve in the SDE.

    Queries the SDE database directly (not the SkillRegistry) to validate
    the full skill namespace. YAML files like ship_efficacy_rules.yaml
    reference skills outside the fitting module's ALL_SKILL_NAMES set
    (e.g., "Surgical Strike", "Rapid Firing"), so the limited registry
    would produce false-positive warnings. Direct SDE validation covers
    all ~400 skills in category 16.

    Args:
        yaml_data: Parsed YAML content
        source: Human-readable source label for warning messages
        extractor_key: Key into YAML_SKILL_EXTRACTORS for schema-specific extraction

    Returns list of warning strings for unresolvable names.
    Returns empty list if SDE is unavailable or extractor_key is unknown.
    """
    try:
        from aria_esi.mcp.sde.queries import get_sde_query_service, SDEResolutionError
        sde = get_sde_query_service()
    except Exception:
        return []

    extractor = YAML_SKILL_EXTRACTORS.get(extractor_key)
    if extractor is None:
        return [f"{source}: No skill extractor registered for '{extractor_key}'"]

    pairs = extractor(yaml_data)
    if not pairs:
        return []

    # Deduplicate skill names for batch resolution
    skill_names = list({name for _, name in pairs})
    try:
        sde.resolve_skill_ids(skill_names)
        return []
    except SDEResolutionError as e:
        # Map missing names back to their contexts for actionable warnings
        missing_set = set(e.missing_names)
        return [
            f"{source}: {context} references unknown skill '{name}'"
            for context, name in pairs
            if name in missing_set
        ]
```

This catches:
- Typos in skill names ("Drone Interferring" instead of "Drone Interfacing")
- Renamed skills after SDE updates
- Copy-paste errors in YAML editing

Warnings are logged at startup, not fatal — degraded functionality is better than a boot failure for a YAML typo. Adding support for a new YAML file requires only writing an extractor function and registering it in `YAML_SKILL_EXTRACTORS`.

**Extractor robustness:** Each extractor MUST handle malformed YAML values gracefully (e.g., `skills` being a string instead of a list, `None` values for expected dicts). Use `isinstance()` checks before iteration. Return empty list on unexpected types rather than raising `TypeError`.

---

## Implementation Plan

### Phase A: SDE Query Methods (Small)

**Modified file:** `src/aria_esi/mcp/sde/queries.py`

1. Add `resolve_skill_ids()` — batch skill name→ID resolution with error on missing
2. Add `SDEResolutionError` exception class:

**Deferred:** `get_types_in_group()` (group membership query) has no consumer in this proposal. Phase E uses a dedicated `get_all_ship_group_ids()` method instead. Add `get_types_in_group()` when a concrete use case arises.

**Phase E note:** `get_all_ship_group_ids()` (Phase E) is a separate SDE method querying the `groups` table. It does not use `resolve_skill_ids()` — the two methods serve different domains (skill names → IDs vs. category → group IDs).

```python
class SDEResolutionError(Exception):
    """Raised when type name resolution fails against SDE."""

    def __init__(self, message: str, missing_names: list[str] | None = None):
        super().__init__(message)
        self.missing_names = missing_names or []
```

`SDEResolutionError` inherits from `Exception` (not `SDENotSeededError`) because the SDE is available but the requested names don't exist — a data problem, not an infrastructure problem. The `missing_names` attribute allows callers to programmatically inspect which names failed.

**Export:** `SDEResolutionError` is defined in `mcp/sde/queries.py` alongside `SDENotSeededError`. Canonical import: `from aria_esi.mcp.sde.queries import SDEResolutionError`. No `__init__.py` re-export needed — consumers are internal to the `aria_esi` package.

**Pre-requisite (affects all phases): Add `types` and `groups` to `ensure_sde_seeded()` check.** The existing `ensure_sde_seeded()` checks for `["npc_corporations", "npc_seeding", "stations", "regions"]` but not `"types"` or `"groups"`. Since `resolve_skill_ids()` (Phase A), many existing SDE methods, and `get_all_ship_group_ids()` (Phase E) query these tables, a missing `types` or `groups` table would produce a raw `sqlite3.OperationalError` instead of a clean `SDENotSeededError`. Add both to the `required_tables` list:

```python
required_tables = ["npc_corporations", "npc_seeding", "stations", "regions", "types", "groups"]
```

This change must land before any other phase code. It ensures `resolve_skill_ids()` and `get_all_ship_group_ids()` get clean `SDENotSeededError` exceptions when the SDE is not fully seeded, and also benefits all existing SDE methods that query `types` or `groups`.

**Estimated effort:** ~45 lines of new code (including `ensure_sde_seeded()` fix). Follows established `SDEQueryService` patterns exactly.

### Phase B: Skill Registry (Medium)

**New file:** `src/aria_esi/fitting/skill_registry.py`

1. Define all skill name lists (DRONE_SKILL_NAMES, etc.)
2. Implement `SkillRegistry` class with `id()`, `ids()`, `name()`, `contains()`
3. Implement `get_skill_registry()` with lazy initialization

**Estimated effort:** ~120 lines. Self-contained module with no external dependencies beyond `SDEQueryService`.

### Phase C: Fitting Skills Migration (Medium)

**Modified file:** `src/aria_esi/fitting/skills.py`

1. Delete `FITTING_SKILL_IDS`, `DRONE_SKILL_IDS`, `TANK_SKILL_IDS`, `NAVIGATION_SKILL_IDS`
2. Delete `BONUS_SKILL_IDS` dict
3. Replace `get_relevant_skills_for_fit()` to use registry
4. Replace bonus injection in `extract_skills_for_fit()` to use registry
5. Update tests (see migration strategy below)

#### Import Audit: Fitting Skill Constants

All imports of deleted constants verified via codebase grep:

| Constant | Importers (production) | Importers (test) |
|----------|----------------------|------------------|
| `FITTING_SKILL_IDS` | None (used only within `fitting/skills.py`) | `tests/fitting/test_skills.py` |
| `DRONE_SKILL_IDS` | None (used only within `fitting/skills.py`) | `tests/fitting/test_skills.py` |
| `TANK_SKILL_IDS` | None (used only within `fitting/skills.py`) | `tests/fitting/test_skills.py` |
| `NAVIGATION_SKILL_IDS` | None (used only within `fitting/skills.py`) | `tests/fitting/test_skills.py` |
| `BONUS_SKILL_IDS` | None (used only within `fitting/skills.py`) | `tests/fitting/test_skills.py` |

No production files outside `fitting/skills.py` import these constants. Test imports are migrated in the test migration strategy below.

**Estimated effort:** Net negative lines (deleting ~100 lines of constants, adding ~20 lines of registry usage).

#### Test Migration Strategy

`tests/fitting/test_skills.py` imports all five hardcoded constant lists at lines 18–23:

```python
from aria_esi.fitting.skills import (
    BONUS_SKILL_IDS,
    DRONE_SKILL_IDS,
    FITTING_SKILL_IDS,
    NAVIGATION_SKILL_IDS,
    TANK_SKILL_IDS,
    ...
)
```

These imports break when the constants are deleted. The migration pattern for each test class:

**`TestGetRelevantSkillsForFit` (lines 139–171):** Currently iterates over hardcoded ID lists to assert membership. Migrate to monkeypatching `get_skill_registry()` with a pre-built `SkillRegistry` instance, then assert using name lists:

```python
# Before:
def test_generic_includes_fitting_and_navigation(self):
    skills = get_relevant_skills_for_fit("generic")
    for skill_id in FITTING_SKILL_IDS:
        assert skill_id in skills

# After:
def test_generic_includes_fitting_and_navigation(self, mock_skill_registry):
    """mock_skill_registry fixture monkeypatches get_skill_registry()."""
    skills = get_relevant_skills_for_fit("generic")
    for name in FITTING_SKILL_NAMES:
        assert mock_skill_registry.id(name) in skills
    for name in NAVIGATION_SKILL_NAMES:
        assert mock_skill_registry.id(name) in skills
```

**`TestExtractSkillsForFit` (lines 179–327):** Assertions like `assert 3442 in skills` use IDs that happen to be correct (drone IDs were fixed in ff1d2e9). Migrate to registry-resolved assertions:

```python
# Before:
assert 3442 in skills  # Drone Interfacing

# After:
assert mock_skill_registry.id("Drone Interfacing") in skills
```

**`TestSkillConstants` (lines 335–353):** Tests like `test_fitting_skill_ids_are_integers` and `test_bonus_skill_ids_dict_structure` validate the structure of deleted constants. **Delete entirely** — the registry's type guarantees replace these.

**New test class `TestRegistryNoneFallback`:** Add tests verifying that `get_relevant_skills_for_fit()` returns `[]` and `extract_skills_for_fit()` skips bonus injection when registry is `None` (monkeypatch `get_skill_registry` to return `None`).

**Fixture:** Add a `mock_skill_registry` fixture to `tests/conftest.py` (project-level, see Test Infrastructure below).

### Phase D: Tank Selection Migration (Small)

**Modified file:** `src/aria_esi/archetypes/tank_selection.py`

1. Delete `TANK_SKILL_IDS` dict
2. Replace `resolve_skill_name_to_id()` to use registry
3. `resolve_skill_names_to_ids()` (line 127) delegates to the migrated singular function — no code change needed, but verify existing tests at `tests/archetypes/test_tank_selection.py:85-96` continue to pass (they monkeypatch the singular function, so the batch wrapper exercises the right code path)
4. Update tests

**Caller audit (completed):** All callers of `resolve_skill_name_to_id()` receive skill names from `meta.yaml` `skill_comparison` sections. Verified meta.yaml files: Vexor L3 (armor: Hull Upgrades, Mechanics, Repair Systems, Armor Rigging; shield: Shield Management, Shield Operation, Shield Upgrades, Tactical Shield Manipulation), Dominix L4 (armor only, same set), Myrmidon L3 (armor only, same set). All names are present in `TANK_SKILL_NAMES` / `ALL_SKILL_NAMES`. No additional names need to be added.

**Test correction:** `tests/archetypes/test_tank_selection.py:80` asserts `resolve_skill_name_to_id("Hull Upgrades") == 3393`. This is asserting the *buggy hardcoded value* (3393 = Repair Systems; Hull Upgrades is actually 3394 per SDE). After migration, the registry will correctly return 3394. Update the test to use the mock registry fixture:

```python
def test_resolve_skill_name_to_id_uses_registry(self, mock_skill_registry):
    assert resolve_skill_name_to_id("Hull Upgrades") == mock_skill_registry.id("Hull Upgrades")
```

This is a behavioral change that constitutes a bug fix (the old test asserted the wrong value), not a regression.

**Estimated effort:** ~10 lines changed.

### Phase E: Ship Group IDs (Small)

**Modified files:** `src/aria_esi/mcp/sde/queries.py`, `src/aria_esi/core/constants.py`

1. Add `get_all_ship_group_ids()` to `SDEQueryService`:

```python
# In SDEQueryService (queries.py):
def get_all_ship_group_ids(self) -> set[int]:
    """Return all group IDs in the Ship category (category_id=6)."""
    self._check_cache_validity()
    self.ensure_sde_seeded()
    conn = self._db._get_connection()
    rows = conn.execute(
        "SELECT DISTINCT group_id FROM groups WHERE category_id = 6"
    ).fetchall()
    return {row[0] for row in rows}
```

**Schema assumption (verified):** The SDE `groups` table has columns `group_id INTEGER` and `category_id INTEGER`. This matches the standard EVE SDE schema (confirmed via `PRAGMA table_info(groups)` on a seeded database). If a future SDE restructuring renames `category_id`, the query fails and `get_ship_group_ids()` falls back to the hardcoded set.

2. Rename current `SHIP_GROUP_IDS` to `_SHIP_GROUP_IDS_FALLBACK` (private, used only as fallback)
3. Add a module-level cached function in `constants.py`:

```python
import threading

_ship_group_ids: set[int] | None = None
_ship_group_lock = threading.Lock()


def get_ship_group_ids() -> set[int]:
    """
    Return all ship group IDs from SDE, with hardcoded fallback.

    Delegates to ``SDEQueryService.get_all_ship_group_ids()`` on first
    call. Result is cached for the process lifetime. Falls back to
    ``_SHIP_GROUP_IDS_FALLBACK`` (the current hardcoded set) if SDE
    is unavailable.

    Thread-safe via double-checked locking, consistent with
    ``get_skill_registry()`` in Phase B.
    """
    global _ship_group_ids
    if _ship_group_ids is not None:
        return _ship_group_ids
    with _ship_group_lock:
        if _ship_group_ids is not None:
            return _ship_group_ids
        try:
            from aria_esi.mcp.sde.queries import get_sde_query_service
            sde_result = get_sde_query_service().get_all_ship_group_ids()
            # Guard against corrupted/empty SDE returning empty set.
            # Note: a non-empty but smaller-than-expected set (e.g., CCP removed
            # a ship group) is accepted as valid — the SDE is authoritative.
            _ship_group_ids = sde_result if sde_result else _SHIP_GROUP_IDS_FALLBACK
        except Exception:
            _ship_group_ids = _SHIP_GROUP_IDS_FALLBACK
        return _ship_group_ids
```

4. Add a `reset_ship_group_ids()` function for test teardown:

```python
def reset_ship_group_ids() -> None:
    """Reset cached ship group IDs for testing. Not for production use."""
    global _ship_group_ids
    with _ship_group_lock:
        _ship_group_ids = None
```

5. Update all callers from `group_id in SHIP_GROUP_IDS` to `group_id in get_ship_group_ids()`

#### Verified `SHIP_GROUP_IDS` Import Audit

All imports and usages of `SHIP_GROUP_IDS` across the codebase (verified via grep):

| File | Line | Import path | Usage |
|------|------|-------------|-------|
| `core/constants.py` | 22 | (definition) | `SHIP_GROUP_IDS = {` — set of 45 group IDs |
| `core/__init__.py` | 29 | `from .constants import SHIP_GROUP_IDS` | Re-export in `__all__` (line 187) |
| `__main__.py` | 310 | `from .core import SHIP_GROUP_IDS` | Health check reference |
| `commands/assets.py` | 17 | `from ..core import SHIP_GROUP_IDS` | Membership test at line 153, function arg at line 547, membership test at line 758 |
| `commands/corporation.py` | 15 | `from ..core import SHIP_GROUP_IDS` | Membership test at line 500 |
| `.claude/scripts/aria-esi-sync.py` | 43 | (duplicate definition) | Membership test at line 332 |
| `tests/test_constants.py` | 26, 30, 36 | `from aria_esi.core import SHIP_GROUP_IDS` | Assertions: non-empty, all ints, known group IDs present |
| `tests/test_commands_esi.py` | 1683, 1903, 1927, 1973, 1997, 2034, 2071 | `patch("aria_esi.commands.assets.SHIP_GROUP_IDS", {25})` | Test mocks replacing constant with `{25}` (Frigate) |

**Production callers (4 files, 4 membership-test sites):**
- `commands/assets.py:153` — `if group_id not in SHIP_GROUP_IDS:` → `if group_id not in get_ship_group_ids():`
- `commands/assets.py:547` — function argument → pass `get_ship_group_ids()`
- `commands/assets.py:758` — `if tinfo["group_id"] not in SHIP_GROUP_IDS:` → `if tinfo["group_id"] not in get_ship_group_ids():`
- `commands/corporation.py:500` — `if group_id in SHIP_GROUP_IDS` → `if group_id in get_ship_group_ids()`

**Test callers (migration notes):**
- `tests/test_constants.py:26-43` — update assertions to use `get_ship_group_ids()` instead of the constant directly; or test both the function and the fallback set
- `tests/test_commands_esi.py` (7 sites) — update `patch` targets from `"aria_esi.commands.assets.SHIP_GROUP_IDS"` to mock `get_ship_group_ids` return value

**Other:**
- `core/__init__.py:29,187` — remove `SHIP_GROUP_IDS` from import and `__all__`; add `get_ship_group_ids` export instead
- `__main__.py:310` — update import to `get_ship_group_ids`
- `.claude/scripts/aria-esi-sync.py:43` — Keep the local definition and rename to `_SHIP_GROUP_IDS_STANDALONE`. This script runs outside the MCP server context and must not depend on SDE infrastructure. Add a comment: `# Standalone copy — authoritative source is aria_esi.core.constants.get_ship_group_ids()`

**Estimated effort:** ~35 lines changed (SDEQueryService method + constants function + reset function + caller updates across 4 production files + 2 test files).

### Phase F: YAML Validation (Small)

**Modified files:** `src/aria_esi/mcp/sde/tools_easy80.py`, `src/aria_esi/mcp/server.py`

1. Add `validate_yaml_skill_references()`, extractor functions, and `YAML_SKILL_EXTRACTORS` registry to `tools_easy80.py` (co-located with the YAML loaders it validates)
2. Add a `_validate_yaml_configs()` helper method to `UniverseServer` in `server.py`
3. Call `_validate_yaml_configs()` from `UniverseServer.warm_sde_caches()` (server.py:95–113), **after** `service.warm_caches()` succeeds — not inside `SDEQueryService.warm_caches()` itself, to avoid coupling the SDE layer to fitting-layer YAML schemas
4. Log warnings for unresolvable skill names (non-fatal)

**Integration point — `server.py:warm_sde_caches()`:**

The MCP server startup sequence in `UniverseServer.run()` (server.py:115–124) is:
1. `load_graph()` — universe topology
2. `register_tools()` — MCP tool dispatchers
3. `warm_sde_caches()` — SDE cache warming **← YAML validation goes here**

```python
def warm_sde_caches(self) -> None:
    """Warm SDE query caches at startup and validate YAML configs."""
    try:
        from .sde.queries import get_sde_query_service
        service = get_sde_query_service()
        stats = service.warm_caches()

        if stats["corporations"] > 0:
            logger.info(
                "SDE caches warmed: %d corporations, %d categories",
                stats["corporations"],
                stats["categories"],
            )

        # Validate YAML skill references after SDE is confirmed available
        self._validate_yaml_configs()

    except Exception as e:
        logger.debug("SDE cache warming skipped (non-fatal): %s", e)

def _validate_yaml_configs(self) -> None:
    """Validate skill names in YAML config files against SDE."""
    from .sde.tools_easy80 import (
        validate_yaml_skill_references,
        load_breakpoint_skills,
        load_efficacy_rules,
        load_meta_alternatives,
    )
    yaml_sources = [
        (load_breakpoint_skills, "breakpoint_skills.yaml", "breakpoint_skills"),
        (load_efficacy_rules, "ship_efficacy_rules.yaml", "ship_efficacy_rules"),
        (load_meta_alternatives, "meta_module_alternatives.yaml", "meta_module_alternatives"),
    ]
    for loader, source, extractor_key in yaml_sources:
        try:
            data = loader()
            warnings = validate_yaml_skill_references(data, source, extractor_key)
            for w in warnings:
                logger.warning(w)
        except Exception as e:
            logger.debug("YAML validation for %s skipped: %s", source, e)
```

**Why not inside `SDEQueryService.warm_caches()`:** `warm_caches()` lives in `mcp/sde/queries.py` and handles SDE-level caching (corporation regions, category IDs). YAML validation is a consumer-level concern that imports YAML loaders from `tools_easy80.py`. Placing it in the server layer keeps the SDE query service decoupled from its consumers.

**YAML loader signatures (verified):** All three loaders are zero-argument functions returning `dict`:
- `load_breakpoint_skills()` → `dict` (tools_easy80.py:166)
- `load_efficacy_rules()` → `dict` (tools_easy80.py:196)
- `load_meta_alternatives()` → `dict` (tools_easy80.py:226)

Each uses internal file-modification-time caching and reloads automatically if the backing YAML file changes. No arguments needed — file paths are resolved internally.

**Estimated effort:** ~80 lines across two files (extractors + validation function in `tools_easy80.py`, integration in `server.py`).

### Phase G: Station Name Dedup (Small)

**Modified files:** `src/aria_esi/core/constants.py`, `src/aria_esi/core/__init__.py`, `src/aria_esi/core/client.py`, `src/aria_esi/commands/market.py`, `tests/core/test_init.py`, `tests/test_constants.py`

#### Verified `STATION_NAMES` Import Audit

All import paths for `STATION_NAMES` across the codebase (verified via grep):

| File | Line | Import path | Usage |
|------|------|-------------|-------|
| `core/constants.py` | 92–98 | (definition) | `dict[int, str]` — 5 trade hub station IDs → names |
| `core/__init__.py` | 31 | `from .constants import STATION_NAMES` | Re-export in `__all__` (line 190) |
| `commands/market.py` | 20 | `from ..core import STATION_NAMES` | Forward lookup (ID→name) at line 186 |
| `core/client.py` | 872 | `from .constants import STATION_NAMES` | Forward lookup (ID→name) at lines 874–875 (lazy import inside `get_station_name()`) |
| `tests/core/test_init.py` | 196 | `from aria_esi.core import STATION_NAMES` | Asserts `isinstance(STATION_NAMES, dict)` |
| `tests/test_constants.py` | 73 | `from aria_esi.core import STATION_NAMES` | Asserts Jita entry exists |

**Finding:** All production usages are forward lookups (ID→name). No reverse lookups (name→ID) exist. Both consumers import via `core` (the re-export), not `core.constants` directly — except `client.py` which uses a lazy import from `core.constants`.

#### Migration Steps

1. Delete `STATION_NAMES` dict from `core/constants.py` (lines 92–98)
2. Remove `STATION_NAMES` from `core/__init__.py` import (line 31) and `__all__` (line 190)
3. In `core/client.py`: update `get_station_name()` to remove the hardcoded cache-first path
4. In `commands/market.py`: replace direct `STATION_NAMES` lookup with `client.get_station_name()`
5. Update `tests/core/test_init.py`: remove `STATION_NAMES` from the import assertion test
6. Update `tests/test_constants.py`: delete `test_station_names` test

#### `core/client.py` — Before and After

**Before** (lines 872–878 of `ESIClient.get_station_name()`):
```python
def get_station_name(self, station_id: int) -> Optional[str]:
    # Check cache first (for known trade hubs)
    from .constants import STATION_NAMES

    if station_id in STATION_NAMES:
        return STATION_NAMES[station_id]

    result = self.get_safe(f"/universe/stations/{station_id}/")
    return result.get("name") if isinstance(result, dict) else None
```

**After:**
```python
def get_station_name(self, station_id: int) -> Optional[str]:
    try:
        from aria_esi.mcp.sde.queries import get_sde_query_service
        info = get_sde_query_service().get_station_info(station_id)
        if info:
            return info.station_name
    except Exception:
        pass

    result = self.get_safe(f"/universe/stations/{station_id}/")
    return result.get("name") if isinstance(result, dict) else None
```

**`get_station_info()` return type:** Returns a `StationInfo` dataclass (defined in `queries.py:95–108`), not a dict. Access fields via attribute syntax (`info.station_name`), not dict syntax.

**Method signature:** `get_station_info(self, station_id: int) -> StationInfo | None` (queries.py line ~544). Takes integer `station_id` directly — compatible with the `client.get_station_name(station_id)` call site.

Full schema:

```python
@dataclass
class StationInfo:
    station_id: int
    station_name: str
    corporation_id: int
    corporation_name: str
    system_id: int
    region_id: int
    region_name: str
```

**Fallback chain:** SDE lookup → ESI API call → `None`. The ESI fallback is retained (it already existed) so station names resolve even if SDE is unavailable. The caller-side `or f"Station {location_id}"` in `_format_orders()` provides the final fallback when both SDE and ESI return `None`. Station names are cosmetic (display only), not behavioral. The full chain is: SDE → ESI → literal ID string.

**Latency note:** In non-MCP contexts (CLI commands), `get_sde_query_service()` may not be initialized, causing the `except Exception: pass` guard to trigger on every call. This replaces an O(1) dict lookup (old `STATION_NAMES`) with an ESI HTTP call for known trade hub stations — a latency regression for CLI callers. This is accepted because station name resolution is cosmetic (display-only) and the ESI call was already the fallback path. If CLI latency becomes an issue, a future optimization could add a lightweight SDE accessor that doesn't require the full MCP singleton.

#### `commands/market.py` — Before and After

**Before** (lines 186–188 of `_format_orders()`):
```python
from ..core import (
    STATION_NAMES,
    ...
)
...
station_name = STATION_NAMES.get(location_id)
if not station_name:
    station_name = client.get_station_name(location_id) or f"Station {location_id}"
```

**After:**
```python
# Remove STATION_NAMES from the import block entirely.
# Replace the two-step lookup with a single client call:
station_name = client.get_station_name(location_id) or f"Station {location_id}"
```

**Rationale:** `client.get_station_name()` already handles SDE lookup internally (after Phase G migration above). The old code duplicated the hardcoded lookup in two places — once in `_format_orders()` via `STATION_NAMES.get()` and again in the fallback via `client.get_station_name()`. After migration, the single `client.get_station_name()` call covers both paths: SDE → ESI → `None`.

**Client access (verified):** `_format_orders()` already has a `client` variable in scope — the existing fallback at line 188 calls `client.get_station_name(location_id)`, confirming the ESI client is available at the call site. No lazy import pattern is needed; the migration simply removes the `STATION_NAMES.get()` shortcut and uses the existing `client` directly.

**Estimated effort:** ~20 lines changed across 6 files.

**Recommended order:** A > B > C > D > F > E > G

Phases A+B are prerequisites (SDE method + registry). Phase C is the highest-value change (fixes live bugs in FITTING_SKILL_IDS, NAVIGATION_SKILL_IDS, BONUS_SKILL_IDS, and inline core_skills). Phase D is a small extension of C (same pattern, different file). Phase F (YAML validation) is ordered before E (ship group IDs) because F validates data integrity — running it sooner provides earlier confidence that SDE resolution works correctly in production before extending the pattern to ship groups. Phases E and G are independent of each other and could be reordered.

---

## Test Plan

Each phase requires tests before merging. Test infrastructure is detailed below.

### Test Infrastructure

The codebase has an established mock SDE database pattern in `tests/mcp/test_sde_skills.py`. Phase A/B/C/D tests reuse this pattern. Phase F/Golden tests use the real SDE via `@requires_sde`.

#### Mock SDE Fixture (for unit tests — Phases A, B, C, D)

Add a `mock_skill_registry` fixture to `tests/conftest.py` (project-level) that builds a minimal SQLite database with all skills from `ALL_SKILL_NAMES`, creates an `SDEQueryService` from it, resolves the registry, and returns it. This follows the pattern from `tests/mcp/test_sde_skills.py:mock_db`:

```python
import sqlite3
from aria_esi.fitting.skill_registry import (
    SkillRegistry, ALL_SKILL_NAMES, reset_skill_registry,
    DRONE_SKILL_NAMES, FITTING_SKILL_NAMES, TANK_SKILL_NAMES,
    NAVIGATION_SKILL_NAMES, BONUS_DRONE_SKILL_NAMES, BONUS_CORE_SKILL_NAMES,
)

# Ground truth: every skill in ALL_SKILL_NAMES mapped to its SDE type_id.
# Sourced from the pre-implementation audit (verified via sde(action="item_info")).
_SKILL_NAME_TO_ID = {
    "Acceleration Control": 3452,
    "Advanced Weapon Upgrades": 11207,
    "Afterburner": 3450,
    "Armor Rigging": 26253,
    "Capacitor Emission Systems": 3423,
    "Capacitor Management": 3418,
    "Capacitor Systems Operation": 3417,
    "Drone Avionics": 3437,
    "Drone Durability": 23618,
    "Drone Interfacing": 3442,
    "Drone Navigation": 12305,
    "Drone Sharpshooting": 23606,
    "Drones": 3436,
    "Evasive Maneuvering": 3453,
    "Fuel Conservation": 3451,
    "Heavy Drone Operation": 3441,
    "Hull Upgrades": 3394,
    "Light Drone Operation": 24241,
    "Mechanics": 3392,
    "Medium Drone Operation": 33699,
    "Navigation": 3449,
    "Power Grid Management": 3413,
    "Repair Systems": 3393,
    "Shield Compensation": 21059,
    "Shield Management": 3419,
    "Shield Operation": 3416,
    "Shield Rigging": 26261,
    "Shield Upgrades": 3425,
    "Tactical Shield Manipulation": 3420,
    "Warp Drive Operation": 3455,
    "Weapon Upgrades": 3318,
}

@pytest.fixture
def mock_sde_db(tmp_path):
    """Create a minimal SDE SQLite database with all registry skills.

    Creates all tables that ensure_sde_seeded() checks in required_tables,
    plus the metadata table required by _check_cache_validity(), so
    resolve_skill_ids() and get_all_ship_group_ids() pass both the seeding
    gate and cache validity check without monkeypatching. Non-types tables
    are empty — only their existence is required.
    """
    db_path = tmp_path / "test_sde.db"
    conn = sqlite3.connect(str(db_path))
    # All tables in ensure_sde_seeded() required_tables list
    conn.execute("""
        CREATE TABLE types (
            type_id INTEGER PRIMARY KEY,
            type_name TEXT,
            type_name_lower TEXT,
            category_id INTEGER,
            published INTEGER DEFAULT 1
        )
    """)
    conn.execute("CREATE TABLE groups (group_id INTEGER PRIMARY KEY, category_id INTEGER, group_name TEXT)")
    conn.execute("CREATE TABLE npc_corporations (corporation_id INTEGER PRIMARY KEY)")
    conn.execute("CREATE TABLE npc_seeding (type_id INTEGER)")
    conn.execute("CREATE TABLE stations (station_id INTEGER PRIMARY KEY)")
    conn.execute("CREATE TABLE regions (region_id INTEGER PRIMARY KEY)")
    # Required by _check_cache_validity() — queries metadata table without
    # error handling (unlike get_skill_attributes which checks table existence).
    # Empty table means no cache invalidation, which is desired for unit tests.
    conn.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")
    for name, type_id in _SKILL_NAME_TO_ID.items():
        conn.execute(
            "INSERT INTO types VALUES (?, ?, ?, 16, 1)",
            (type_id, name, name.lower()),
        )
    # Add a non-skill type to test category filtering
    conn.execute("INSERT INTO types VALUES (626, 'Vexor', 'vexor', 6, 1)")
    # Add ship groups for Phase E tests
    conn.execute("INSERT INTO groups VALUES (25, 6, 'Frigate')")
    conn.execute("INSERT INTO groups VALUES (26, 6, 'Cruiser')")
    conn.commit()
    conn.close()
    return db_path

@pytest.fixture
def mock_skill_registry(mock_sde_db, monkeypatch):
    """Return a SkillRegistry backed by the mock SDE database.

    Patches the module-level singleton so production code paths
    (get_skill_registry()) return this mock during the test.
    """
    reset_skill_registry()
    registry = SkillRegistry(_SKILL_NAME_TO_ID)
    monkeypatch.setattr(
        "aria_esi.fitting.skill_registry._skill_registry", registry
    )
    yield registry
    reset_skill_registry()
```

The `_SKILL_NAME_TO_ID` dict contains all 31 skills from `ALL_SKILL_NAMES` with their SDE-verified type IDs from the pre-implementation audit. This is the single source of truth for test assertions — tests assert `mock_skill_registry.id("Drone Interfacing")` instead of hardcoding `3442`.

**Phase A tests** additionally need the `mock_sde_db` fixture wrapped in an `SDEQueryService` to test `resolve_skill_ids()` directly. The fixture constructs a minimal service instance backed by the mock SQLite database, following the `MockMarketDatabase` pattern from `tests/mcp/test_sde_skills.py:mock_market_db`:

```python
import threading

@pytest.fixture
def mock_sde_service(mock_sde_db, monkeypatch):
    """Create an SDEQueryService backed by the mock SDE database.

    For Phase A tests that need to call resolve_skill_ids() directly.
    Follows the pattern from tests/mcp/test_sde_skills.py:mock_market_db.
    """
    from unittest.mock import MagicMock
    from aria_esi.mcp.sde.queries import SDEQueryService

    mock_db = MagicMock()
    mock_db._get_connection.return_value = sqlite3.connect(str(mock_sde_db))

    service = SDEQueryService.__new__(SDEQueryService)
    service._db = mock_db
    service._lock = threading.Lock()
    # Initialize all caches matching SDEQueryService.__init__ (queries.py:179-198)
    service._corp_regions = {}
    service._seeding_corps = {}
    service._category_ids = {}
    service._corp_info = {}
    service._station_info = {}
    service._npc_station_regions = None
    service._skill_attrs = {}
    service._skill_prereqs = {}
    service._type_requirements = {}
    service._meta_groups = {}
    service._meta_variants_by_parent = {}
    service._parent_type = {}
    service._cache_import_timestamp = None

    monkeypatch.setattr("aria_esi.mcp.sde.queries._sde_query_service", service)
    yield service
```

**Note:** The `mock_sde_db` fixture (defined above) creates a minimal SQLite database with all tables in `ensure_sde_seeded()`'s `required_tables` list. The `SDEQueryService` is constructed via `__new__` to bypass `__init__` and injected with the mock database connection.

**Singleton variable name (verified):** The module-level singleton is `_sde_query_service` in `queries.py:1106` (defined alongside `get_sde_query_service()` which accesses it). The monkeypatch target `"aria_esi.mcp.sde.queries._sde_query_service"` is verified against this definition. If the variable name changes, the `mock_sde_service` fixture's monkeypatch must be updated accordingly.

**Cache validity:** `_check_cache_validity()` queries a `metadata` table for the SDE import timestamp (`queries.py:205`). It does **not** catch `sqlite3.OperationalError` for a missing table — unlike `get_skill_attributes()` and `get_skill_prerequisites()`, which check table existence before querying. Therefore the `mock_sde_db` fixture **MUST** create the `metadata` table. Add `conn.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")` to the fixture (an empty table is sufficient — no rows means no cache invalidation, which is the desired behavior for unit tests).

**Seeding gate:** `ensure_sde_seeded()` checks that all `required_tables` exist. The mock DB creates all of them (most are empty — only their existence is required). This avoids `SDENotSeededError` in unit tests without monkeypatching.

#### Real SDE Fixture (for integration tests — Phase F, Golden)

The `@requires_sde` marker is defined locally in `tests/integration/test_sde_data_integrity.py:38` (and duplicated in `test_sde_performance.py:38`). The golden integration test should be placed in `tests/integration/test_skill_registry.py` with either a local marker definition or a shared one extracted to `tests/integration/conftest.py`:

```python
# tests/integration/conftest.py (shared marker for all integration tests)
def _sde_available() -> bool:
    try:
        from aria_esi.mcp.sde.queries import get_sde_query_service
        get_sde_query_service().ensure_sde_seeded()
        return True
    except Exception:
        return False

requires_sde = pytest.mark.skipif(
    not _sde_available(),
    reason="SDE not seeded. Run 'uv run aria-esi sde-seed' first.",
)
```

Use this marker for:
- Golden integration test (`test_all_skill_names_resolve_against_sde`)
- YAML validation tests that verify real YAML files against the full SDE

```python
@requires_sde
def test_all_skill_names_resolve_against_sde():
    from aria_esi.fitting.skill_registry import ALL_SKILL_NAMES
    sde = get_sde_query_service()
    resolved = sde.resolve_skill_ids(ALL_SKILL_NAMES)
    assert len(resolved) == len(ALL_SKILL_NAMES)
```

#### Singleton Reset

`tests/conftest.py` has an autouse `reset_all_singletons` fixture (lines 755–1045) that resets module-level singletons between tests. Add skill registry reset to it:

```python
try:
    from aria_esi.fitting.skill_registry import reset_skill_registry
    reset_skill_registry()
except ImportError:
    pass

try:
    from aria_esi.core.constants import reset_ship_group_ids
    reset_ship_group_ids()
except ImportError:
    pass
```

### Phase A: SDE Query Methods

| Test | What it proves |
|------|----------------|
| `test_resolve_skill_ids_returns_correct_ids` | Given a seeded SDE, batch resolution maps known names (e.g., "Drones", "Drone Interfacing") to their correct type_ids |
| `test_resolve_skill_ids_raises_on_missing_name` | `SDEResolutionError` raised with correct `missing_names` attribute listing all failures |
| `test_resolve_skill_ids_case_insensitive` | `"drone interfacing"` resolves same as `"Drone Interfacing"` |
| `test_resolve_skill_ids_empty_list` | Empty input returns `{}` without error |
| `test_resolve_skill_ids_filters_to_skills_category` | A name that exists in another category (e.g., ship group name) is not resolved — raises `SDEResolutionError` |
| `test_resolve_skill_ids_with_duplicates` | Duplicate input names produce a dict with one entry per unique name |
| `test_resolve_skill_ids_ambiguous_name` | If SDE contains duplicate names in category 16, `SDEResolutionError` is raised (uniqueness assertion) |
| `test_resolve_skill_ids_partial_failure_reports_all_missing` | Given `["Drones", "FakeSkill1", "FakeSkill2"]`, error's `missing_names` contains both fake names |
| `test_resolve_skill_ids_sde_not_seeded` | When `types` table is missing, `SDENotSeededError` is raised (not `OperationalError`) |
| `test_resolve_skill_ids_empty_types_table` | When `types` table exists but has zero rows, `SDEResolutionError` is raised with all input names in `missing_names` |
| `test_resolve_skill_ids_preserves_input_key_casing` | Returned dict keys match input casing (e.g., `"drone interfacing"` key, not SDE canonical `"Drone Interfacing"`) |

**Test file:** `tests/mcp/test_sde_resolution.py` (new file — co-located with existing `test_sde_skills.py`).

**Test file locations for other phases:** Phase B and C tests go in `tests/fitting/test_skill_registry.py` and `tests/fitting/test_skills.py` respectively. Phase D tests go in `tests/archetypes/test_tank_selection.py`. Phase E tests go in `tests/test_constants.py`. Phase F unit tests go in `tests/mcp/test_yaml_validation.py`; integration tests go in `tests/integration/test_skill_registry.py`. Phase G tests go in `tests/test_commands_esi.py` and `tests/core/test_init.py`.

**Shared fixtures:** `mock_sde_db`, `mock_skill_registry`, and `mock_sde_service` are all defined in `tests/conftest.py` (project-level) since they are needed by tests in `tests/fitting/`, `tests/archetypes/`, and `tests/mcp/`. No directory-level `conftest.py` files are needed for these fixtures.

### Phase B: Skill Registry

| Test | What it proves |
|------|----------------|
| `test_skill_registry_id_lookup` | `registry.id("Drones")` returns correct type_id |
| `test_skill_registry_ids_batch` | `registry.ids(DRONE_SKILL_NAMES)` returns list of correct IDs in input order |
| `test_skill_registry_name_reverse_lookup` | `registry.name(3436)` returns `"Drones"` |
| `test_skill_registry_contains` | `registry.contains("Drones")` is `True`; `registry.contains("Nonexistent")` is `False` |
| `test_skill_registry_id_raises_on_unknown` | `registry.id("Nonexistent")` raises `KeyError` |
| `test_skill_registry_ids_raises_on_unknown` | `registry.ids(["Drones", "Nonexistent"])` raises `KeyError` |
| `test_all_skill_names_count_is_31` | `len(ALL_SKILL_NAMES) == 31` — guards against accidental list addition/removal |
| `test_bonus_core_skill_names_count_is_12` | `len(BONUS_CORE_SKILL_NAMES) == 12` — guards against accidental modification of the expanded core skills list (intentionally larger than the old 7-entry `core_skills` inline dict) |
| `test_get_skill_registry_singleton` | Two calls return the same instance |
| `test_get_skill_registry_returns_none_when_sde_unavailable` | Returns `None` when SDE is not seeded |
| `test_get_skill_registry_no_retry_after_failure` | After SDE failure, returns `None` immediately without re-querying SDE |
| `test_reset_skill_registry_clears_state` | After `reset_skill_registry()`, next call re-initializes from SDE |
| `test_get_skill_registry_thread_safety` | Two threads calling `get_skill_registry()` concurrently both get the same instance (no double-init) |
| `test_check_cache_validity_does_not_affect_registry` | After registry init, calling `_check_cache_validity()` (simulating SDE reimport) does not clear or replace the `_skill_registry` singleton |

### Phase C: Fitting Skills Migration

| Test | What it proves |
|------|----------------|
| `test_extract_skills_for_fit_with_registry` | Regression: output for a known fit matches expected skill IDs (replacing old hardcoded-constant tests) |
| `test_extract_skills_for_fit_registry_none_skips_bonus` | When registry is `None`, bonus injection is skipped; core EOS-based extraction still works |
| `test_get_relevant_skills_for_fit_generic` | `"generic"` returns FITTING + NAVIGATION skill IDs only |
| `test_get_relevant_skills_for_fit_drone_boat` | `"drone_boat"` returns FITTING + DRONE + NAVIGATION skill IDs |
| `test_get_relevant_skills_for_fit_armor_tank` | `"armor_tank"` returns FITTING + TANK + NAVIGATION skill IDs |
| `test_get_relevant_skills_for_fit_registry_none` | Returns `[]` when registry is `None` |
| `test_extract_skills_bonus_core_includes_power_grid_management` | Verifies the intentional addition of Power Grid Management (behavioral change from old 7-entry `core_skills` to new 12-entry `BONUS_CORE_SKILL_NAMES`) |
| `test_extract_skills_bonus_core_excludes_repair_systems` | Verifies Repair Systems is NOT in bonus core skills (was present in old code only due to swapped IDs — bug fix, not regression) |

### Phase D: Tank Selection Migration

| Test | What it proves |
|------|----------------|
| `test_tank_selection_resolve_uses_registry` | `resolve_skill_name_to_id("Mechanics")` returns SDE-backed ID |
| `test_tank_selection_resolve_unknown_skill` | Returns `None` for skill not in registry |
| `test_tank_selection_resolve_registry_none` | Returns `None` with warning when registry unavailable |

### Phase E: Ship Group IDs

| Test | What it proves |
|------|----------------|
| `test_get_all_ship_group_ids_from_sde` | `SDEQueryService.get_all_ship_group_ids()` returns non-empty set of group IDs |
| `test_get_ship_group_ids_uses_sde_when_available` | `get_ship_group_ids()` returns SDE result (not fallback) when SDE is available |
| `test_get_ship_group_ids_fallback` | `get_ship_group_ids()` returns `_SHIP_GROUP_IDS_FALLBACK` when SDE unavailable |
| `test_reset_ship_group_ids_clears_cache` | After `reset_ship_group_ids()`, next call re-queries SDE |
| `test_get_ship_group_ids_caches_across_calls` | Second call returns cached result without re-querying SDE |
| `test_get_ship_group_ids_empty_sde_result_uses_fallback` | When SDE returns empty set, fallback is used (guards against corrupted/empty SDE) |
| `test_get_ship_group_ids_thread_safety` | Two threads calling `get_ship_group_ids()` concurrently both get the same result (no double-query) |

### Phase F: YAML Validation

| Test | What it proves |
|------|----------------|
| `test_yaml_validation_catches_typo` | Extractor reports warning for a deliberately misspelled skill name via SDE resolution |
| `test_yaml_validation_passes_for_valid_names` | No warnings for file with correct skill names (including skills outside `ALL_SKILL_NAMES`, e.g., "Surgical Strike") |
| `test_yaml_validation_returns_empty_when_sde_unavailable` | Returns `[]` when SDE is unavailable (graceful degradation) |
| `test_yaml_validation_unknown_extractor_key` | Returns warning for unregistered extractor key |
| `test_yaml_validation_empty_yaml_data` | `validate_yaml_skill_references({}, "test", "breakpoint_skills")` returns `[]` (no skills to validate) |
| `test_extractor_handles_none_yaml_data` | Each extractor returns `[]` when `yaml_data` is `None` (guards against `yaml.safe_load()` returning `None` for empty files) |
| `test_yaml_validation_with_skills_outside_all_skill_names` | YAML validation resolves skills like "Surgical Strike" that are NOT in `ALL_SKILL_NAMES` but ARE in SDE category 16 — confirms validation uses full SDE, not limited registry |
| `test_extractor_breakpoint_skills_real_yaml` | Extractor finds >0 skill names from real `breakpoint_skills.yaml` (guards against schema mismatch). `@requires_sde` |
| `test_extractor_efficacy_rules_real_yaml` | Extractor finds >0 skill names from real `ship_efficacy_rules.yaml`. `@requires_sde` |
| `test_extractor_meta_alternatives_real_yaml` | Extractor finds >0 skill names from real `meta_module_alternatives.yaml`. `@requires_sde` |

### Phase G: Station Name Dedup

| Test | What it proves |
|------|----------------|
| `test_get_station_name_uses_sde` | `get_station_name(60003760)` returns "Jita IV - Moon 4 - Caldari Navy Assembly Plant" via SDE path (not hardcoded `STATION_NAMES`) |
| `test_get_station_name_falls_back_to_esi` | When SDE is unavailable, ESI fallback path is exercised |
| `test_format_orders_without_station_names_import` | `_format_orders()` works after `STATION_NAMES` removal — uses `client.get_station_name()` directly |

### Golden Integration Test

| Test | What it proves |
|------|----------------|
| `test_all_skill_names_resolve_against_sde` | Every name in `ALL_SKILL_NAMES` resolves to a real type_id in a seeded SDE database. This is the primary regression gate — if a name is misspelled or removed from the SDE, this test fails at CI time rather than silently at runtime. |

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| SDE not available at startup (fresh install, import failed) | Boot failure | Graceful fallback: log warning, provide `None` registry. Callers that need IDs fail at point of use with clear error. |
| Skill name doesn't match SDE exactly (case, whitespace) | Resolution failure at boot | Use case-insensitive matching (already indexed). Log the failed name for easy debugging. |
| Performance: SDE queries at startup add latency | Slower MCP boot | Batch query (~30 names in one pass). Measured overhead: <50ms for SQLite lookup of 30 names. |
| Registry becomes a god object | Architecture smell | Registry is read-only after init, contains only ID mappings, no logic. Intentionally thin. |
| YAML validation produces false positives | Noisy logs | Validation is warn-only, never fatal. Names must match SDE exactly to pass. |
| SDE reimported mid-session (e.g., after game patch) | Stale skill IDs in registry | The SkillRegistry is initialized once per process. SDE reimport requires MCP server restart. This matches existing behavior for other startup-cached data (EOS data files, YAML configs). A `status()` MCP call could be extended to show registry age for observability. |

### Edge Cases and Specified Behavior

| Scenario | Specified behavior |
|----------|-------------------|
| SDE is seeded but `types` table has zero rows | `resolve_skill_ids()` raises `SDEResolutionError` with all input names in `missing_names`. This is the normal "missing name" path — an empty table means every name is unresolved. |
| SDE is reimported mid-session with renamed skills | Registry is NOT re-resolved on cache invalidation. `_check_cache_validity()` may clear other SDE caches, but the `SkillRegistry` singleton is independent — it is initialized once per process and requires a restart to refresh. |
| `ALL_SKILL_NAMES` contains a name removed in a game patch | `SDEResolutionError` at boot for that name → `get_skill_registry()` returns `None` for the entire session. Resolution is all-or-nothing by design — partial resolution would leave callers with an incomplete registry that silently omits skills. |
| Two skills in SDE have the same `type_name_lower` in category 16 | `resolve_skill_ids()` raises `SDEResolutionError` with "Ambiguous" message. This is a hard failure — ambiguity prevents the entire registry from initializing, since the wrong ID could be silently chosen. In practice, CCP maintains unique skill names within category 16. |
| `get_ship_group_ids()` returns an SDE result that is a strict subset of the fallback | Accepted as valid (SDE is authoritative). If CCP removed ship groups, the SDE reflects ground truth. A `logger.info` noting the count difference may aid debugging but is not required. |
| `validate_yaml_skill_references()` is called before SDE is seeded | Returns `[]` (empty warnings) and logs no message. This means YAML validation is silently skipped when SDE is unavailable. This is acceptable — YAML validation is a bonus check, not a gate. The `warm_sde_caches()` caller already handles SDE unavailability at a higher level. |
| `tank_selection.py` receives a skill name not in `ALL_SKILL_NAMES` | `resolve_skill_name_to_id()` returns `None` and logs at `warning` level (with remediation hint to add to `TANK_SKILL_NAMES`). Callers receiving `None` should treat the skill as unresolvable (log and skip). If new meta.yaml files reference skills outside the registered set, those skills must be added to `TANK_SKILL_NAMES` (and thus `ALL_SKILL_NAMES`). |

---

## Relationship to Existing Patterns

### `resolve_skill_name_to_id()` in `tank_selection.py`

This function already implements the "name first, ID second" pattern but with a hardcoded fallback. The proposal promotes this pattern to a shared service and removes the fallback — the SDE is the single source of truth.

### `MULTIPLIER_SKILLS` in `tools_easy80.py`

Already keyed by name. No migration needed. This is the pattern all skill data should follow.

### `SDEQueryService.get_category_id()`

Already exists and returns `int | None`. The proposed `resolve_skill_ids()` follows the same pattern but operates on skill names in batch.

---

## Verdict: Viable

**Viability: HIGH.** The proposal is low-risk and moderate-effort:

1. **The SDE database already has all the data** — `types` table with `type_name_lower` index supports case-insensitive name lookup
2. **The query service pattern is established** — `SDEQueryService` already has 18 public methods with caching; adding `resolve_skill_ids()` is mechanical
3. **The migration is incremental** — each phase is independently deployable and testable
4. **The primary value is bug prevention** — structurally eliminates the class of bug found on 2026-02-08, where 7 of 9 hardcoded IDs were wrong
5. **Net code reduction** — deletes ~230 lines of hardcoded constants, adds ~200 lines of registry + queries (net: fewer lines, and the remaining lines are self-validating)
