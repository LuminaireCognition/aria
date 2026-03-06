---
name: fitting
description: ARIA ship fitting assistance for Eve Online. Use for fitting exports, EFT format generation, module recommendations, tank analysis, or fitting optimization.
model: claude-opus-4-6
category: tactical
triggers:
  - "/fitting"
  - "fit my [ship]"
  - "export fitting"
  - "EFT format"
  - "fitting recommendations"
  - "tank analysis"
  - "what modules for [ship]"
requires_pilot: true
requires_eos_validation: true
validation_tool: "fitting(action='calculate_stats')"
prerequisite_files:
  - .claude/skills/fitting/EFT-FORMAT.md
  - reference/mechanics/drones.json
  - reference/fittings/MODULE_NAMES.md
data_sources:
  - userdata/pilots/{active_pilot}/profile.md
  - userdata/pilots/{active_pilot}/ships.md
  - reference/archetypes/INDEX.md
  - reference/archetypes/_shared/module_tiers.yaml
  - reference/mechanics/missiles.json
  - reference/mechanics/projectile_turrets.json
  - reference/mechanics/laser_turrets.json
  - reference/mechanics/hybrid_turrets.json
---

# Fitting Module

## Query Triage

Classify the request before starting any build work:

**Export / retrieval** ("export my Drake", "show my Vexor fit", "what's my X fitting"):
1. Read pilot's `ships.md` for locally cached fits
2. If a matching fit exists → skip to Phase 2 (validate) + Phase 5 (present as copy-paste EFT)
3. If no match → explain there is no locally cached fit, mention `/fittings` for ESI-based retrieval of in-game saved fits, and offer to build a new fit instead

**Build / recommend** ("fit my Drake for L3s", "what modules for a Vexor"):
→ Proceed to Three-Phase Output Protocol below

## Three-Phase Output Protocol

**Phase 1 — Build:** Generate the EFT block (module list only). No numerical stats.

**Phase 2 — Validate:** Call `fitting(action="calculate_stats", eft="...")`. Present stats ONLY from the tool response, prefixed with "**Fitting engine:**". If the call fails: "Stats unavailable — verify in-game (Alt+F)."

**Phase 3 — Consistency Check:** Re-read the EFT block and verify every capability claimed in prose (active rep, cap stable, weapon type, damage application, etc.) corresponds to a module actually present in the EFT block. Remove or correct any claims that don't match.

## Module Size Rules

| Hull Class | AB | MWD | Weapons/Reps |
|------------|-----|-----|--------------|
| Frigates/destroyers | 1MN | 5MN | Small |
| Cruisers/battlecruisers | 10MN | 50MN | Medium |
| Battleships | 100MN | 500MN | Large |

PvE default: Afterburner (MWD causes signature bloom and cap drain).

## Prerequisites (Load Before Building)

Load all reference data in parallel before constructing any EFT string:

1. Read `.claude/skills/fitting/EFT-FORMAT.md` (project-root-relative path, not skill-directory path) — slot order is Low → Mid → High → Rigs
2. Read pilot's `profile.md` — module tier, operational constraints
3. Read pilot's `ships.md` — existing fits for reference
4. Read `reference/mechanics/drones.json` (project-root-relative path, not skill-directory path) — when recommending drones
5. Read `reference/fittings/MODULE_NAMES.md` (project-root-relative path, not skill-directory path) — common naming issues
6. Query `sde(action="item_info", item="<ship>")` — get slot counts

**Batching:** Items 1-5 are independent file reads with no dependencies on each other. Issue them in a single parallel tool call batch alongside item 6 (the SDE query) to minimize latency. If a read fails, report the exact path that failed — do not substitute training data.

Check `reference/archetypes/INDEX.md` for matching archetype templates. Use `module_tiers.yaml` for tier adjustments. Plan modules for ALL available slots — empty slots are a fitting error.

## Fit Validation

### Step 1: Verify Item Names via SDE

Every module, charge, drone, and rig: `sde(action="item_info", item="<name>")`. Training data contains fabricated module names. If SDE returns no match, the name is wrong — search for the correct one.

### Step 2: EOS Validation

```
fitting(action="calculate_stats", eft="...", use_pilot_skills=true)
```

If `use_pilot_skills` fails, fall back to All V with a prominent warning that actual performance will be 15-25% lower.

### Step 3: Check Response

- `validation_errors` → fit is invalid, fix before presenting
- `resources.*.overloaded` → downgrade modules
- `metadata.warnings` → investigate and resolve before presenting
- Empty slots → add modules to fill all available slots

## Tank Coherence

Never mix armor and shield active tank.

- **Armor (Gallente/Amarr):** Repairers and hardeners in lows. Mids for prop/cap/EWAR. Armor rigs.
- **Shield (Caldari/Minmatar):** Extenders, hardeners, boosters in mids. Lows for damage/application. Shield rigs.

## Drone Selection

Read `reference/mechanics/drones.json` (project-root-relative path, not skill-directory path) before recommending drones. Match drone damage type to enemy weakness using `enemy_recommendations`. Verify bandwidth fits the ship.

## Gear Tier

Check pilot's `ships.md` and `profile.md` for module tier indicators. Default to **T1/Meta** when uncertain. Named meta modules are superior to T1 base — never suggest T1 base as an upgrade from named meta.

## EFT Ammo Note

Ammo/charge lines may be misparsed as drones. Signs: `drones.launched > 5`, drone bay overflow, unexpectedly low DPS. Workaround: place ammo after an extra blank line (cargo section).

## Rules

- All stats from tool calls only — never quote DPS/EHP/cap from memory
- Fill all available slots — empty slots are a fitting error
- EOS validation is mandatory — no fit presented without it
