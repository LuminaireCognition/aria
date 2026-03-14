---
name: fitting
description: ARIA ship fitting assistance for Eve Online. Use for fitting exports, EFT format generation, module recommendations, tank analysis, or fitting optimization.
model: sonnet
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
injected_prerequisites:
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
argument-hint: "<ship> [<activity>]"
allowed-tools: [Read, Grep, Glob, "mcp__aria-universe__fitting", "mcp__aria-universe__sde", "mcp__aria-universe__market", "mcp__aria-universe__pilot"]
preferred_max_lines: 45
---

# Fitting Module

## Query Triage

Classify the request before starting any build work:

**Export / retrieval** ("export my Drake", "show my Vexor fit", "what's my X fitting"):
1. Read pilot's `ships.md` for locally cached fits
2. If a matching fit exists → skip to Phase 2 (validate) + Phase 5 (present as copy-paste EFT)
3. If not found locally, attempt `pilot(action="fittings_list", ship_filter="<hull>")`
4. If both fail, report both failures in one response — do not send the user to `/fittings`
   only for it to also fail. Offer to build a new fit instead.

**Build / recommend** ("fit my Drake for L3s", "what modules for a Vexor"):
→ Proceed to Three-Phase Output Protocol below

## Three-Phase Output Protocol

**Phase 1 — Build:** Generate the EFT block (module list only). No numerical stats.

**Phase 2 — Validate:** Call `fitting(action="calculate_stats", eft="...")`. Present stats ONLY from the tool response, prefixed with "**Fitting engine:**". If the call fails: "Stats unavailable — verify in-game (Alt+F)."

**Phase 3 — Consistency Check (INTERNAL ONLY — never output to user):** Re-read the EFT block and verify every capability claimed in prose (active rep, cap stable, weapon type, damage application, etc.) corresponds to a module actually present in the EFT block. Remove or correct any claims that don't match. Phase 3 is a silent verification pass — do not include its reasoning, type ID lookups, EOS artifacts, or any validation commentary in the response. The user sees only the final EFT block (Phase 1), fitting engine stats (Phase 2), brief tuning notes, and the Sources footer.

## Module Size Rules

| Hull Class | AB | MWD | Weapons/Reps |
|------------|-----|-----|--------------|
| Frigates/destroyers | 1MN | 5MN | Small |
| Cruisers/battlecruisers | 10MN | 50MN | Medium |
| Battleships | 100MN | 500MN | Large |

PvE default: Afterburner (MWD causes signature bloom and cap drain).

## Prerequisites (Load Before Building)

Reference data (EFT format, drones, module names) is injected below — do not re-read those files. Before constructing any EFT string, still load:

1. Read pilot's `profile.md` — module tier, operational constraints
2. Read pilot's `ships.md` — existing fits for reference
3. Query `sde(action="item_info", item="<ship>")` — get slot counts

**Batching:** Items 1-2 are independent file reads. Issue them in a single parallel tool call batch alongside item 3 (the SDE query) to minimize latency.

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

Drone reference data is injected from `reference/mechanics/drones.json`. Match drone damage type to enemy weakness using `enemy_recommendations`.

**Bandwidth gate (mandatory):** Before adding any drone to a fit, check `common_drone_ships` or `hull_stats` for the ship's `drone_bandwidth`. Only select drones whose total bandwidth ≤ the ship's limit. Heavy and sentry drones require 25 Mbit/s each — many drone-bonused hulls cannot field them (e.g., Gila has only 20 Mbit/s bandwidth despite a 100 m³ bay — it can only use light or medium drones). Never assume a "drone ship" can use heavies.

## Gear Tier

Check pilot's `ships.md` and `profile.md` for module tier indicators. Default to **T1/Meta** when uncertain. Named meta modules are superior to T1 base — never suggest T1 base as an upgrade from named meta.

## Charge Coherence

- **No turrets in fit** → do not recommend turret ammo (hybrid charges, projectile ammo, frequency crystals)
- **No launchers in fit** → do not recommend missiles or torpedoes
- Only recommend charges/ammo for weapon systems actually present in the EFT block
- Cap boosters, scan scripts, and other non-weapon charges are fine if their parent module is fitted

**EFT parsing note:** Ammo/charge lines may be misparsed as drones. Signs: `drones.launched > 5`, drone bay overflow, unexpectedly low DPS. Workaround: place ammo after an extra blank line (cargo section).

## Rules

- Keep response under 50 lines (EFT block + stats + brief notes)
- Append a one-line `Sources:` footer listing MCP calls and reference files used
- All stats from tool calls only — never quote DPS/EHP/cap from memory
- When presenting DPS, EHP, or HP values that are calculated or estimated rather than returned directly by the fitting engine tool, suffix with `(est.)`. Example: `DPS: ~124 (est.) | EHP: ~12,500 (est.)`. Stats returned by `fitting(action="calculate_stats")` do not need the suffix.
- Fill all available slots — empty slots are a fitting error
- EOS validation is mandatory — no fit presented without it

## Injected Reference Data

### Reference: EFT Format (injected)
<!-- prerequisite: .claude/skills/fitting/EFT-FORMAT.md -->
!`cat .claude/skills/fitting/EFT-FORMAT.md`

### Reference: Drones (injected)
<!-- prerequisite: reference/mechanics/drones.json -->
!`cat reference/mechanics/drones.json`

### Reference: Module Names (injected)
<!-- prerequisite: reference/fittings/MODULE_NAMES.md -->
!`cat reference/fittings/MODULE_NAMES.md`
