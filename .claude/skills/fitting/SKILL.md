---
name: fitting
description: ARIA ship fitting assistance for Eve Online. Use for fitting exports, EFT format generation, module recommendations, tank analysis, or fitting optimization.
model: haiku
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

# ARIA Fitting Module

## Prerequisites (Load Before Building Fits)

**MANDATORY:** Before constructing ANY EFT string, load these files:

1. **Read `EFT-FORMAT.md`** - Module section order is Low → Mid → High → Rigs
2. **Read `reference/mechanics/drones.json`** - When recommending drones
3. **Read `reference/fittings/MODULE_NAMES.md`** - Common naming gotchas
4. **Query ship slot layout:** `sde(action="item_info", item="[ship name]")` - Know how many slots to fill

These files MUST be loaded before the first `fitting(action="calculate_stats")` call. Do not attempt to build a fit from memory—the iteration cost of failed validations exceeds the cost of reading documentation upfront.

### Archetype Reference

When building a new fit for a hull + activity:
1. Check `reference/archetypes/INDEX.md` for matching archetype
2. If found: use archetype EFT as template, adjust tier per pilot profile
3. For tier adjustments: read `reference/archetypes/_shared/module_tiers.yaml`
4. Proceed to validation (existing SDE + EOS pipeline)

**Slot Layout Verification:** The ship info query returns slot counts. Plan modules for ALL available slots before building the EFT string. Empty slots are a fitting error.

## Reference Documentation
- EFT format specification: [EFT-FORMAT.md](EFT-FORMAT.md)
- Module naming issues: [MODULE_NAMES.md](../../../reference/fittings/MODULE_NAMES.md)
- Fitting checklist: [CHECKLIST.md](CHECKLIST.md)

### Gear Tier Validation Protocol

**CRITICAL:** Before recommending specific modules, you MUST:

1. **Read the pilot's ships.md** (`userdata/pilots/{active_pilot}/ships.md`)
2. **Check existing fittings** for module tier indicators:
   - T1 modules: End in "I" (e.g., "Hammerhead I", "Armor Repairer I")
   - T2 modules: End in "II" (e.g., "Hammerhead II", "Armor Repairer II")
   - Meta modules: Named variants (e.g., "Malkuth", "Arbalest", "Compact")
3. **Check profile.md** for explicit `module_tier` field in Operational Constraints
4. **Default to T1/Meta** when tier is uncertain or not explicitly T2

**Module Tier Rules:**
| Indicator | Recommendation |
|-----------|----------------|
| Existing fits show T1 only | T1/Meta only |
| Existing fits show T2 | T2 acceptable |
| `module_tier: t1` in profile | T1/Meta only |
| `module_tier: t2` in profile | T2 acceptable |
| Uncertain/no data | **Default to T1/Meta** |

**Never recommend T2 modules/drones unless explicitly confirmed.**

## Known Limitation: Ammo Lines in EFT

Ammo/charge lines (e.g., `Scourge Heavy Missile x1000`) in EFT format may be misparsed as drones by the parser. The parser uses category lookups and quantity heuristics to classify items, but edge cases exist.

**Validation signs of misparsed ammo:**
- `drones.launched` exceeds 5 (impossible for most ships)
- Drone bay capacity overflows
- DPS seems unreasonably low for a missile/turret ship (ammo not being applied)

**Workaround:** Place ammo lines after an extra blank line (cargo section) in the EFT format. The parser always routes cargo-section items correctly.

## Fit Validation Protocol (MANDATORY)

**CRITICAL:** Never present a fitting recommendation without EOS validation.

### Step 1: Verify ALL Item Names via SDE (BLOCKING GATE)

**Every module, charge, drone, and rig** in the proposed fit must be verified before proceeding:
```
sde(action="item_info", item="Module Name")
```

Run this for **each distinct item**. Do NOT skip items you are "confident" about — training data contains fabricated names (e.g., "Precursor Beam Weapon", "EM Ward Amplifier II", "EMP Heavy Missile" — none exist in SDE).

- Confirm the exact item name (many modules lack "I" suffix)
- Confirm the module exists and is published
- Confirm charges match the weapon system (e.g., Heavy Missiles for HMLs, not "EMP Heavy Missile")
- Confirm drone tier (T1/T2/Faction/Augmented are distinct — don't call T2 "Faction")
- Reference: `reference/fittings/MODULE_NAMES.md` for common naming issues

**If SDE returns no match:** The item name is wrong. Do NOT include it in the fit. Search SDE for the correct name before continuing.

### Step 2: Build and Validate via EOS

```
fitting(action="calculate_stats", eft="[Ship, Fit Name]\n...", use_pilot_skills=true)
```

### Step 3: Check Validation Response

| Response | Action |
|----------|--------|
| `validation_errors` present | Fit is INVALID - fix before presenting |
| `resources.cpu.overloaded: true` | CPU exceeded - reduce/downgrade modules |
| `resources.powergrid.overloaded: true` | PG exceeded - downgrade modules |
| `metadata.warnings` | **Investigate before proceeding** (see Warning Protocol) |
| Clean validation | Proceed to presentation |

### Warning Investigation Protocol

**CRITICAL:** Never dismiss warnings without verification.

| Warning Type | Required Action |
|--------------|-----------------|
| "Unknown type" | SDE lookup, correct name, rebuild fit |
| "Slot mismatch" | SDE lookup, verify slot type, correct EFT section |
| "CPU/PG exceeded" | Downgrade modules or add fitting mods |
| "Drone bandwidth" | Reduce drone count or use smaller drones |
| "Capacitor unstable" | Add cap mods or reduce active modules |
| **"Empty slots"** | Add modules to fill all available slots |
| **"Mixed tank detected"** | Remove conflicting modules (see Tank Coherence Rules) |

**Do not proceed to presentation** until all warnings have been investigated and either resolved or documented as cosmetic/known limitation.

### Mission Fit Requirements

When building fits for specific missions:
1. Read mission cache for required equipment (Data Analyzer, Probe Launcher, etc.)
2. Verify required modules fit in available slots BEFORE finalizing

### EOS Unavailability

If the fitting engine is unavailable:
- **Warn the user** that the fit is unvalidated
- **Do not present stats** as they would be estimates
- **Suggest** verifying in-game with the Fitting Simulation tool

## Response Format

Present validated fits with: EFT block (copy-paste ready), calculated stats (DPS, EHP, cap stability) with skill context, fitting room (CPU%, PG%), and validation source note ("Stats calculated via EOS with your skills").

## Tank Coherence Rules

**CRITICAL:** Never mix armor and shield active tank modules. The fitting tool will warn about mixed tanks, but prevention is better than correction.

**Armor Tank (Gallente/Amarr):**
| Slot | Use For | Never |
|------|---------|-------|
| Low | Armor Repairer, Armor Hardeners, EANM, Damage Control, DDAs | - |
| Mid | Prop mod, Cap Battery, Tackle, EWAR, Application | Shield Hardener, Shield Booster, Shield Extender |
| Rig | Aux Nano Pump, Nanobot Accelerator, Trimark | Shield rigs |

**Shield Tank (Caldari/Minmatar):**
| Slot | Use For | Never |
|------|---------|-------|
| Mid | Shield Extender, Shield Hardener, Shield Booster, Prop mod | - |
| Low | Damage Control, Damage Mods, Application mods | Armor Repairer, Armor Hardeners |
| Rig | Core Defense Field Extender, Screen Reinforcer | Armor rigs |

**The tool detects:**
- Armor rigs + shield modules → warning
- Shield rigs + armor modules → warning
- Both active tank types → warning

## Drone Selection Protocol

When recommending drones for a fit:

1. **Read `reference/mechanics/drones.json`** - REQUIRED before claiming damage types
2. **Match drone to enemy weakness** - Use the `enemy_recommendations` section
3. **Verify bandwidth fits ship** - Use `common_drone_ships` or query SDE for ship drone bandwidth
4. **Quote damage type from file** - Do not rely on training data for damage types

**Example:** Mission against Serpentis
- Read `enemy_recommendations.serpentis.weakness` → "thermal"
- Select Hammerhead (medium, thermal) or Hobgoblin (light, thermal)
- Present as "Hammerhead I x5 (Thermal damage, matches Serpentis weakness)"

## Faction-Specific Fitting Guidance

| Faction | Tank | Primary Weapon | Hull Examples |
|---------|------|----------------|---------------|
| Gallente | Armor | Drones/Hybrids | Vexor, Myrmidon, Dominix |
| Caldari | Shield | Missiles | Caracal, Drake, Raven |
| Minmatar | Shield/Flex | Projectiles | Rupture, Hurricane, Maelstrom |
| Amarr | Armor | Lasers | Omen, Harbinger, Apocalypse |
