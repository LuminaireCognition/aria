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
data_sources:
  - userdata/pilots/{active_pilot}/profile.md
  - userdata/pilots/{active_pilot}/ships.md
  - reference/archetypes/hulls/{class}/{ship}/manifest.yaml
  - reference/archetypes/hulls/{class}/{ship}/**/*.yaml
  - reference/archetypes/_shared/*.yaml
  - reference/fittings/MODULE_NAMES.md
---

# ARIA Fitting Module

## Purpose
Provide ship fitting recommendations, export fittings in proper EFT format, analyze fitting performance, and suggest module alternatives appropriate to the capsuleer's faction and operational constraints.

## Trigger Phrases
- "fit my [ship]"
- "export fitting"
- "EFT format"
- "fitting recommendations"
- "tank analysis"
- "survival fit"
- "what modules for [ship]"

## Prerequisites (Load Before Building Fits)

**MANDATORY:** Before constructing ANY EFT string, load these files:

1. **Read `EFT-FORMAT.md`** - Module section order is Low → Mid → High → Rigs
2. **Read `reference/mechanics/drones.json`** - When recommending drones
3. **Read `reference/fittings/MODULE_NAMES.md`** - Common naming gotchas
4. **Query ship slot layout:** `sde(action="item_info", item="[ship name]")` - Know how many slots to fill

These files MUST be loaded before the first `fitting(action="calculate_stats")` call. Do not attempt to build a fit from memory—the iteration cost of failed validations exceeds the cost of reading documentation upfront.

**Slot Layout Verification:** The ship info query returns slot counts. Plan modules for ALL available slots before building the EFT string. Empty slots are a fitting error.

## Reference Documentation
- EFT format specification: [EFT-FORMAT.md](EFT-FORMAT.md)
- Module naming issues: [MODULE_NAMES.md](../../../reference/fittings/MODULE_NAMES.md)
- Fitting checklist: [CHECKLIST.md](CHECKLIST.md)

## Pilot Resolution (First Step)

Before accessing pilot files, resolve the active pilot path:
1. Read `userdata/config.json` → get `active_pilot` character ID
2. Read `userdata/pilots/_registry.json` → match ID to `directory` field
3. Use that directory for all pilot paths below

**Single-pilot shortcut:** If config is missing, read the registry - if only one pilot exists, use that pilot's directory.

## Reference Fit Lookup (MANDATORY FIRST STEP)

**CRITICAL:** Before building ANY fit from scratch, check for existing archetype fits.

### Archetype Structure

```
reference/archetypes/hulls/{class}/{ship}/
├── manifest.yaml                    # Hull metadata, slot layout, roles
└── pve/missions/{level}/
    ├── alpha.yaml                   # Alpha clone variant
    ├── low.yaml                     # New pilot variant
    ├── medium.yaml                  # Established pilot variant
    └── high.yaml                    # Maxed skills variant
```

**Ship classes:** `frigate`, `destroyer`, `cruiser`, `battlecruiser`, `battleship`, `mining_barge`, `industrial`, `industrial_command`

**Activity types:** `pve/missions/{l1-l5}`, `pve/ratting`, `exploration`, `mining/ore`, `mining/gas`, `hauling`

### Lookup Workflow

```
Request for [ship] fit for [activity]
    │
    ├─→ Glob: reference/archetypes/hulls/*/{ship}/manifest.yaml
    │       Found? → Read manifest for hull info
    │
    ├─→ Glob: reference/archetypes/hulls/*/{ship}/{activity}/**/*.yaml
    │       Found? → Select skill tier matching pilot's module_tier
    │                Load YAML, validate with pilot skills, adapt if needed
    │
    └─→ No archetype exists → Build from scratch (proceed to Prerequisites)
```

### Selecting Skill Tier

Match pilot's `module_tier` from profile to archetype variant:

| Profile `module_tier` | Archetype Variant |
|-----------------------|-------------------|
| `t1` | `low.yaml` (T1/Meta modules) |
| `t2` | `medium.yaml` or `high.yaml` |
| Not specified | `low.yaml` (default safe) |
| Alpha clone | `alpha.yaml` |

### Adapting Archetype Fits

When an archetype fit exists:
1. **Load the YAML** - Read the EFT block and metadata
2. **Check `damage_tuning.overrides`** - Apply faction-specific module swaps if mission enemy matches
3. **Validate with pilot skills** - Run through EOS to get actual stats
4. **Minor adaptation only** - Swap drones for enemy weakness, adjust hardeners for damage profile

**Do NOT rebuild from scratch** when an archetype exists.

### Why This Matters

Archetype fits are:
- **Tested** - Validated with EOS across skill tiers
- **Documented** - Include skill requirements, upgrade paths, engagement notes
- **Consistent** - Same fit structure across skill levels
- **Maintained** - Single source of truth for each hull + activity

Building from scratch ignores this work and risks errors.

## Operational Constraints

CRITICAL: Before making recommendations, check the active pilot's profile for:
- **Operational Constraints** section (market access, contracts, etc.)
- **Primary Faction** (determines default ship/module recommendations)
- **Playstyle restrictions** (self-sufficiency mode, etc.)

**Profile Location:** `userdata/pilots/{active_pilot}/profile.md`

**If self-sufficiency mode enabled:**
1. **Primary Recommendations**: Tech 1 modules manufacturable from NPC-seeded BPOs
2. **Meta Alternatives**: Note common meta module drops from missions
3. **No Market Dependencies**: Never assume market access for modules

**If standard playstyle:**
1. Recommend optimal modules regardless of acquisition method
2. Note T2 upgrades where appropriate
3. Consider faction/deadspace modules for advanced fits

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

## Fit Validation Protocol (MANDATORY)

**CRITICAL:** Never present a fitting recommendation without EOS validation.

### Why Validation is Required

1. **Training data is not ground truth** - Module names and slot assignments from memory may be wrong
2. **Many modules have non-standard names** - "Reactive Armor Hardener" (no "I" suffix), size-prefixed MWDs, etc.
3. **Slot assignments must be verified** - Data Analyzer goes in mid slots, not high slots
4. **Stats must be calculated, not estimated** - DPS, EHP, and cap stability depend on pilot skills

### Validation Steps

Before presenting ANY fit:

#### Step 1: Verify Module Names via SDE

For each module in the proposed fit:
```
sde(action="item_info", item="Module Name")
```

- Confirm the exact item name (many modules lack "I" suffix)
- Confirm the module exists and is published
- Reference: `reference/fittings/MODULE_NAMES.md` for common naming issues

#### Step 2: Build and Validate via EOS

```
fitting(action="calculate_stats", eft="[Ship, Fit Name]\n...", use_pilot_skills=true)
```

This catches:
- Slot mismatches (mid slot module in high slot)
- CPU/PG overloads
- Invalid module names
- Provides accurate DPS/tank with pilot skills

#### Step 3: Check Validation Response

| Response | Action |
|----------|--------|
| `validation_errors` present | Fit is INVALID - fix before presenting |
| `resources.cpu.overloaded: true` | CPU exceeded - reduce/downgrade modules |
| `resources.powergrid.overloaded: true` | PG exceeded - downgrade modules |
| `metadata.warnings` | **Investigate before proceeding** (see Warning Protocol) |
| Clean validation | Proceed to presentation |

#### Step 4: Handle Validation Failures

**Unknown type error:**
```json
{"error": "type_resolution_error", "message": "Unknown type: Reactive Armor Hardener I"}
```
→ Query SDE for correct name, rebuild EFT, re-validate

**CPU/PG overload:**
→ Suggest alternatives: downgrade modules, add fitting implants, or choose different modules

**Slot mismatch:**
→ Verify module slot type, rebuild fit with correct slot assignment

### Warning Investigation Protocol

**CRITICAL:** Never dismiss warnings without verification.

When `metadata.warnings` contains entries:

1. **Read each warning message**
2. **For slot-related warnings:** Query `sde(action="item_info", item="...")` to verify slot type
3. **For unknown type warnings:** The module name is wrong—query SDE for correct name
4. **For resource warnings:** Review fitting room, consider downgrades

| Warning Type | Required Action |
|--------------|-----------------|
| "Unknown type" | SDE lookup, correct name, rebuild fit |
| "Slot mismatch" | SDE lookup, verify slot type, correct EFT section |
| "CPU/PG exceeded" | Downgrade modules or add fitting mods |
| "Drone bandwidth" | Reduce drone count or use smaller drones |
| "Capacitor unstable" | Add cap mods or reduce active modules |
| **"Empty slots"** | Add modules to fill all available slots |
| **"Mixed tank detected"** | Remove conflicting modules (see Tank Coherence Rules) |

**Do not proceed to presentation** until all warnings have been investigated and either:
- Resolved (fit corrected)
- Documented (warning is cosmetic/known limitation)

**Empty Slot Warnings:** The tool now warns when `slots.used < slots.total`. A fit with empty slots is incomplete. Either:
- Fill the slots with useful modules
- Document why slots are intentionally empty (rare—usually CPU/PG constrained edge cases)

**Mixed Tank Warnings:** The tool detects armor rigs + shield modules (or vice versa). This is always a fitting error. See Tank Coherence Rules in Fitting Philosophy.

### Mission Fit Requirements

When building fits for specific missions:

1. Read mission cache for required equipment (Data Analyzer, Probe Launcher, etc.)
2. Verify required modules fit in available slots BEFORE finalizing
3. Example: Data Analyzer (mid slot) requires a free mid slot - do not place in high slots

### Presenting Validated Fits

Only present fits that pass EOS validation. Include:

1. **EFT block** (copy-paste ready)
2. **Calculated stats** (DPS, EHP, cap stability) with skill context
3. **Fitting room** (CPU%, PG%) - warn if tight
4. **Validation source** - "Stats calculated via EOS with your skills"

### EOS Unavailability

If the fitting engine is unavailable:
- **Warn the user** that the fit is unvalidated
- **Do not present stats** as they would be estimates
- **Suggest** verifying in-game with the Fitting Simulation tool

## Response Format

When providing fitting recommendations:

```
═══════════════════════════════════════════════════════════════════
ARIA FITTING ANALYSIS
[Ship Class] — [Fit Purpose]
───────────────────────────────────────────────────────────────────
[Analysis content organized in clear sections]
═══════════════════════════════════════════════════════════════════
```

When exporting fittings, always provide:
1. Properly formatted EFT block (see EFT-FORMAT.md)
2. Import instructions for EVE client
3. Manufacturing notes if relevant

## Fitting Philosophy Guidelines

### Survival Fits
- Prioritize align time (sub-6 seconds ideal for industrials)
- Include Cloak+MWD trick capability where appropriate
- Balance between speed tank and buffer tank based on threat profile

### Mining Fits
- Maximize yield within safety parameters
- Consider ore hold vs cargo capacity
- Always include escape capability

### Mission Fits
- Match tank to expected enemy damage types
- Reference mission-brief skill for enemy intel
- Prefer capacitor stability for extended engagements

### Exploration Fits
- Prioritize probe strength and scan resolution
- Include escape capability (cloak, align time)
- Balance analyzer strength vs survivability

### Tank Coherence Rules

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

**Why This Matters:**
- Shield modules become useless once shields are stripped (armor-tanked ships lose shields fast)
- Armor rigs commit the ship to armor tanking—don't waste mid slots on shield
- Damage Control is the one exception (provides hull resist, used in all tanks)

**The tool now detects:**
- Armor rigs + shield modules → warning
- Shield rigs + armor modules → warning
- Both active tank types → warning

## Manufacturing Awareness

When recommending fittings for self-sufficient pilots, provide:
- Primary mineral requirements for T1 modules
- Salvage requirements for rigs
- Note which meta modules commonly drop from L2 missions

## Drone Selection Protocol

When recommending drones for a fit:

1. **Read `reference/mechanics/drones.json`** - REQUIRED before claiming damage types
2. **Match drone to enemy weakness** - Use the `enemy_recommendations` section
3. **Verify bandwidth fits ship** - Use `common_drone_ships` or query SDE for ship drone bandwidth
4. **Quote damage type from file** - Do not rely on training data for damage types

**Drone selection workflow:**
```
1. Identify enemy faction from mission/activity context
2. Read drones.json → enemy_recommendations → {faction} → weakness
3. Select drone that deals that damage type
4. Verify ship can field the drone (bandwidth check)
5. Include damage type in fit presentation (cite source)
```

**Example:** Mission against Serpentis
- Read `enemy_recommendations.serpentis.weakness` → "thermal"
- Select Hammerhead (medium, thermal) or Hobgoblin (light, thermal)
- Present as "Hammerhead I x5 (Thermal damage, matches Serpentis weakness)"

## Faction-Specific Fitting Guidance

Reference archetype fits by faction's typical tank and weapon system:

| Faction | Tank | Primary Weapon | Hull Examples |
|---------|------|----------------|---------------|
| Gallente | Armor | Drones/Hybrids | Vexor, Myrmidon, Dominix |
| Caldari | Shield | Missiles | Caracal, Drake, Raven |
| Minmatar | Shield/Flex | Projectiles | Rupture, Hurricane, Maelstrom |
| Amarr | Armor | Lasers | Omen, Harbinger, Apocalypse |

Archetype fits are located at `reference/archetypes/hulls/{class}/{ship}/`.

## Behavior
- Maintain ARIA persona throughout
- Provide tactical reasoning for fitting choices
- Warn about fitting pitfalls (cap stability, CPU/PG issues)
- Offer alternatives when primary recommendations may be difficult to source
- **Brevity:** EFT block + key notes only. Full analysis/manufacturing info on request.
- **Rig Inclusion:**
  - New ship builds: Include rig recommendations
  - Refits/mission loadouts: OMIT rigs (assume already installed)
  - When in doubt, ask: "Include rig suggestions for a new hull?"

## Contextual Suggestions

After providing a fitting, suggest ONE related command when contextually relevant:

| Context | Suggest |
|---------|---------|
| Fit is for missions | "Run `/mission-brief` for enemy intel before undocking" |
| Fit is for exploration | "Try `/exploration` when you find a site" |
| Fit is for mining | "My `/mining-advisory` can recommend ores" |
| Capsuleer asks about dangerous space | "Check `/threat-assessment` for the area first" |

Don't add suggestions to every fitting - only when clearly helpful.

---

## Persona Adaptation

This skill supports persona-specific overlays. When active persona has an overlay file, load additional context from:

```
personas/{active_persona}/skill-overlays/fitting.md
```

If no overlay exists, use the default (empire) framing above.
