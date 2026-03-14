# Reference Data Validation Strategy

## Problem

ARIA's reference data contains claims about EVE Online game mechanics — damage profiles, tank recommendations, NPC compositions, weapon stats — that directly drive fitting and tactical output. When these claims are wrong, the model produces wrong fits. When multiple sources disagree, the model picks one unpredictably.

The EoM/Gone Berserk incident demonstrates the failure mode: `npc_damage_types.md`, `faction_tuning.yaml`, `pve-intel/INDEX.md`, and the Vexor archetype override all claimed EoM deals EM/Thermal. The mission cache files (sourced from EVE University Wiki) correctly said Kinetic/Thermal. Five authoritative sources were wrong; the wiki-sourced cache was right. This went undetected across multiple review cycles because no validation process checks local data against its upstream sources.

The reference corpus is now large enough (41 mechanics files, 17 mission intel files, 3 shared archetype configs, 40+ hull archetypes) that manual auditing doesn't scale.

## Scope

Two categories of validation, in priority order:

### 1. Internal Consistency (offline, no network)

Check that local data sources agree with each other. These checks are fast, deterministic, and catch the exact class of bug that caused the EoM incident.

| Check | Source A | Source B | Rule |
|-------|----------|----------|------|
| Faction damage → hardeners | `npc_damage_types.md` "They Deal" | `faction_tuning.yaml` resist modules | Hardener damage types must match "They Deal" types |
| Mission cache → faction profile | `missions/*.md` "Tank" field | `npc_damage_types.md` "They Deal" | Must agree, or mission file must note exception |
| Index → faction profile | `pve-intel/INDEX.md` "They Deal" | `npc_damage_types.md` "They Deal" | Must match exactly |
| Archetype overrides → tuning | `meta.yaml` `damage_tuning.overrides` | `faction_tuning.yaml` | Override hardeners must match tuning entry |
| Faction completeness | `npc_damage_types.md` factions | `faction_tuning.yaml` factions | Every faction in damage types must have a tuning entry per profile |
| Drone recommendations | `npc_damage_types.md` "You Deal" | `drones.json` `enemy_recommendations` | Recommended drone damage type must match "You Deal" |

### 2. External Validation (network, EVE University Wiki + SDE)

Check that local data matches its upstream source. These checks are slower and require fetching, but catch data that was wrong at creation time or has gone stale.

| Check | Local File | Upstream Source | Fields |
|-------|-----------|----------------|--------|
| Mission damage profiles | `missions/*.md` | Wiki mission page (URL in `Source:` header) | Damage Dealt, Tank, EWAR |
| NPC damage types | `npc_damage_types.md` | Wiki [NPC Damage Types](https://wiki.eveuniversity.org/NPC_damage_types) | They Deal, You Deal per faction |
| Drone stats | `drones.json` | SDE `invTypes` + Wiki drones page | Damage types, bandwidth, volume |
| Missile stats | `missiles.json` | SDE `invTypes` + Wiki missiles page | Damage types, launcher mappings |
| Turret stats | `*_turrets.json` | SDE `invTypes` + Wiki turrets pages | Damage types, tracking, optimal |
| Abyssal weather | `abyssal_deadspace.json` | Wiki [Abyssal Deadspace](https://wiki.eveuniversity.org/Abyssal_Deadspace) | Weather effects, NPC factions per tier |

## Implementation

### Phase 1: Internal Consistency Checker

A Python script at `dev/scripts/validate-reference-data.py` that runs offline and reports mismatches.

```python
"""
Validate internal consistency across reference data files.

Usage:
    uv run python3 dev/scripts/validate-reference-data.py

Exit codes:
    0 = all checks pass
    1 = mismatches found (prints report to stdout)
"""
```

**Core checks:**

```python
def check_faction_hardener_consistency(
    npc_damage: dict[str, dict],      # faction → {they_deal: [str], you_deal: [str]}
    faction_tuning: dict[str, dict],  # profile → faction → {modules: [...]}
) -> list[Mismatch]:
    """
    For each faction in npc_damage, verify that faction_tuning
    resist modules match the 'they_deal' damage types.

    Example mismatch (the EoM bug):
      npc_damage["equilibrium_of_mankind"]["they_deal"] = ["EM", "Thermal"]
      faction_tuning["armor_active"]["equilibrium_of_mankind"]["resist"] =
          ["Kinetic Armor Hardener I", "Thermal Armor Hardener I"]
      → Mismatch: EM in they_deal but Kinetic in hardener
    """

def check_mission_cache_consistency(
    mission_files: list[Path],        # reference/pve-intel/missions/*.md
    npc_damage: dict[str, dict],
) -> list[Mismatch]:
    """
    Parse each mission file's Quick Reference table.
    Compare 'Tank' field against npc_damage[faction]['they_deal'].
    Flag mismatches — but do NOT auto-correct, since mission-specific
    profiles can legitimately differ from general faction data.
    """

def check_index_consistency(
    pve_index: Path,                  # reference/pve-intel/INDEX.md
    npc_damage: dict[str, dict],
) -> list[Mismatch]:
    """INDEX.md 'They Deal' column must match npc_damage_types.md exactly."""
```

**Parser helpers** (needed to extract structured data from markdown tables and YAML):

```python
def parse_npc_damage_types(path: Path) -> dict[str, dict]:
    """Parse npc_damage_types.md markdown tables into structured data.
    Returns {faction_key: {they_deal: [...], you_deal: [...], ewar: [...]}}
    Normalizes faction names to snake_case keys."""

def parse_mission_quick_ref(path: Path) -> dict[str, str]:
    """Parse a mission intel file's Quick Reference table.
    Returns {field: value} dict, e.g. {'faction': 'EoM', 'tank': 'Kinetic, Thermal'}"""

DAMAGE_TYPE_TO_HARDENER = {
    ("EM", "armor"): "EM Armor Hardener I",
    ("Thermal", "armor"): "Thermal Armor Hardener I",
    ("Kinetic", "armor"): "Kinetic Armor Hardener I",
    ("Explosive", "armor"): "Explosive Armor Hardener I",
    ("EM", "shield"): "EM Shield Hardener I",
    # ...
}
```

**Output format:**

```
=== Reference Data Validation ===

PASS  faction_hardener_consistency: serpentis (armor_active)
PASS  faction_hardener_consistency: guristas (armor_active)
FAIL  faction_hardener_consistency: equilibrium_of_mankind (armor_active)
      npc_damage_types.md says: EM / Therm
      faction_tuning.yaml has: Kinetic Armor Hardener I + Thermal Armor Hardener I
      Expected: EM Armor Hardener I + Thermal Armor Hardener I

WARN  mission_cache_consistency: gone_berserk_eom_l3.md
      Cache says Tank: Kinetic, Thermal
      General profile says: EM, Thermal
      (Mission-specific profiles may legitimately differ — verify against wiki)

--- Summary ---
Checks: 47 passed, 1 failed, 2 warnings
```

Warnings (WARN) are emitted when mission-specific data differs from general faction data. This is expected for factions like EoM where the general profile doesn't match every mission. Failures (FAIL) are emitted for sources that should always agree (e.g., INDEX.md vs npc_damage_types.md, or faction_tuning.yaml vs npc_damage_types.md).

### Phase 2: External Validation (wiki-fetch)

A separate script (or `--external` flag) that fetches upstream sources and compares. This is designed to run periodically (monthly or after a game patch), not on every commit.

```python
"""
Validate reference data against EVE University Wiki.

Usage:
    uv run python3 dev/scripts/validate-reference-data.py --external

Fetches wiki pages listed in mission file Source: headers and
the NPC damage types summary page. Compares key fields.
"""
```

**Mission file validation flow:**

```
For each reference/pve-intel/missions/*.md:
  1. Extract Source: URL from header (e.g., https://wiki.eveuniversity.org/Gone_Berserk_(Level_3))
  2. Fetch the wiki page
  3. Extract: Damage Dealt, Recommended Resist, Damage to Deal
  4. Compare against local file's Quick Reference table
  5. Report mismatches with both local and upstream values
```

**NPC damage types validation flow:**

```
1. Fetch https://wiki.eveuniversity.org/NPC_damage_types
2. Parse the faction damage table
3. Compare each faction's They Deal / You Deal against npc_damage_types.md
4. Report mismatches
```

**Rate limiting:** Wiki fetches use 1-second delays between requests. The full mission corpus (17 files) takes ~20 seconds. Cache responses locally to `dev/.validation-cache/` (gitignored) with a 24-hour TTL to avoid redundant fetches during iterative fixes.

### Phase 3: Staleness Tracking

JSON reference files already have `_meta.last_verified` fields (e.g., `drones.json`: 2026-01-22, `missiles.json`: 2026-02-02). The validation script reports files with `last_verified` older than 90 days as stale.

Markdown files have no such field. Add an optional `Last verified: YYYY-MM-DD` line to the Quick Reference table in mission intel files. The validator treats missing dates as "unknown staleness" (WARN, not FAIL).

```
STALE drones.json — last_verified: 2026-01-22 (46 days ago)
STALE gone_berserk_eom_l1.md — no last_verified date
OK    missiles.json — last_verified: 2026-02-02 (35 days ago)
```

## Integration

### Exercise Runner

The internal consistency check (Phase 1) can run as a pre-flight in the exercise runner to catch data errors before they pollute exercise outputs:

```python
# In exercise-runner.py, before running queries:
from validate_reference_data import run_internal_checks

mismatches = run_internal_checks()
if mismatches:
    print(f"⚠ {len(mismatches)} reference data mismatches — run validate-reference-data.py")
```

### CI / Pre-commit

Phase 1 (internal consistency) is fast enough (~1s) for a pre-commit hook or CI check. Phase 2 (external validation) is too slow for CI but can run as a scheduled weekly job.

### Fixing Mismatches

When the validator finds a mismatch, the human decides which source is correct:
- If the wiki/SDE source is correct → fix the local file
- If the local file has a mission-specific exception → add a note to the file explaining the divergence
- Either way, all local sources must be updated to agree (the EoM fix pattern: update npc_damage_types.md + faction_tuning.yaml + archetype + INDEX.md together)

The validator does NOT auto-fix. Data corrections require domain knowledge about which source is authoritative for a given claim.

## Not In Scope

- **SDE database queries.** The SDE MCP tool could validate module stats, ship attributes, and skill requirements. This is valuable but architecturally different (requires MCP server running). Defer to a separate proposal.
- **Archetype fitting validation.** Checking that archetypes are CPU/PG valid requires the fitting engine. Already covered by exercise-runner fitting checks.
- **Auto-remediation.** Too dangerous — the EoM incident showed that "fixing" data to match the wrong source makes things worse.
- **Training data cross-check.** We cannot validate what the model "knows" from training data. The `!`command`` injection pattern and `prerequisite_files` gate are the correct mitigations for training-data confabulation.

## Priority

| Phase | Effort | Impact | Dependency |
|-------|--------|--------|------------|
| Phase 1: Internal consistency | Medium (1 script, ~200 LOC) | Catches the exact EoM class of bug | None |
| Phase 2: External validation | Medium (wiki parser + fetch logic) | Catches stale/wrong-at-creation data | Phase 1 parsers |
| Phase 3: Staleness tracking | Low (date comparison) | Prevents data rot | Phase 1 infra |
