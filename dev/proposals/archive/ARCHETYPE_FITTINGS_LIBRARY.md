# Archetype Fittings Library Proposal

## Executive Summary

This proposal establishes a hierarchical library of archetype ship fittings organized by hull, activity, and skill tier. Each archetype serves as a tunable reference fit that can be adapted for specific damage profiles, skill levels, and operational constraints. The system includes hull-specific rules (e.g., drone boats may have intentionally empty high slots) and damage tuning instructions.

**Goals:**
- Provide validated reference fits for common hull/activity combinations
- Support skill-tiered variants (low/medium/high) for each archetype
- Enable damage profile tuning for faction-specific optimization
- Encode hull-specific fitting wisdom (empty slots, weapon choices, tank philosophy)
- Integrate with existing EOS validation and fitting skill

**Scope:** This proposal covers PvE archetypes only. PvP fits are highly meta-dependent and will be addressed in a separate follow-on proposal once the PvE foundation is validated.

---

## Problem Statement

### Current Limitations

1. **Flat organization:** All fits are in `reference/ships/fittings/` with inconsistent naming
2. **No skill variants:** Each fit assumes a single skill level (usually mid-tier)
3. **Limited damage tuning:** Faction-specific fits are separate files (e.g., `vexor_serpentis.md`)
4. **No hull metadata:** Special rules (drone boats, weapon platforms) live only in skill docs
5. **Manual duplication:** Creating variants requires copying and modifying entire fits

### Example Gaps

| Request | Current State | Desired State |
|---------|---------------|---------------|
| "Low-skill Vexor for L2" | Only one Vexor L2 fit | `vexor/pve/missions/l2/low.yaml` |
| "Vexor for Blood Raiders" | No fit exists | Tuned from base + `blood_raiders` profile |
| "Why empty high slots?" | Explained ad-hoc | Documented in hull manifest |
| "Alpha-friendly Thorax" | Not documented | `alpha.yaml` variant |

---

## Proposed Solution

### Directory Structure

```
reference/archetypes/
├── README.md                           # Library overview and usage guide
├── _schema/                            # JSON schemas for validation
│   ├── archetype.schema.json           # Fit definition schema
│   ├── manifest.schema.json            # Hull manifest schema
│   └── damage_profile.schema.json      # Damage profile schema
│
├── _shared/                            # Shared configuration
│   ├── damage_profiles.yaml            # Faction damage dealt/resisted
│   ├── faction_tuning.yaml             # Tank/drone adjustments by faction
│   ├── module_tiers.yaml               # T1 → Meta → T2 upgrade paths
│   ├── skill_tiers.yaml                # What defines low/medium/high
│   └── tank_archetypes.yaml            # Armor active, shield passive, etc.
│
└── hulls/                              # Hull-organized archetypes
    └── {class}/                        # Ship class (frigate, cruiser, etc.)
        └── {hull}/                     # Hull name (vexor, drake, etc.)
            ├── manifest.yaml           # Hull metadata and rules
            │
            ├── pve/                    # PvE activity branch
            │   ├── missions/           # Security missions
            │   │   ├── _design.md      # Design rationale (documentation only)
            │   │   ├── l1/             # Mission level variants
            │   │   ├── l2/
            │   │   │   ├── low.yaml    # Low skill variant
            │   │   │   ├── medium.yaml # Medium skill variant
            │   │   │   ├── high.yaml   # High skill variant
            │   │   │   └── alpha.yaml  # Alpha clone variant
            │   │   ├── l3/
            │   │   └── l4/
            │   │
            │   ├── anomalies/          # Combat site anomalies
            │   │   ├── belt/           # Belt ratting (highsec/lowsec)
            │   │   │   ├── low.yaml
            │   │   │   └── medium.yaml
            │   │   └── combat/         # Combat anomalies (Forsaken Hubs, etc.)
            │   │       ├── low.yaml
            │   │       ├── medium.yaml
            │   │       └── high.yaml
            │   │
            │   └── abyss/              # Abyssal deadspace
            │       ├── t1-electrical.yaml
            │       ├── t1-dark.yaml
            │       ├── t1-exotic.yaml
            │       ├── t3-electrical.yaml
            │       ├── t3-dark.yaml
            │       └── t3-exotic.yaml
            │
            └── mining/                 # Mining/industrial (if applicable)
                └── belt.yaml
```

**Design decisions:**

- **Anomalies consolidation:** `ratting/` and `anomalies/` merged into `anomalies/` with `belt/` (simple belt rats) and `combat/` (escalation-capable sites) subdirectories.
- **Abyss flattening:** Tier and filament type combined into single filename (`t1-electrical.yaml`) for consistent structure.
- **Alpha variants:** Explicitly included in mission level directories where applicable.
- **Design docs:** `_base.yaml` renamed to `_design.md` to clarify it's prose documentation, not a processable template.

### File Specifications

#### 1. Hull Manifest (`manifest.yaml`)

**Location:** `reference/archetypes/hulls/{class}/{hull}/manifest.yaml`

**Purpose:** Defines hull-specific metadata, slot layout, bonuses, and special fitting rules.

**Required Fields:**
```yaml
# manifest.yaml
hull: Vexor
class: cruiser
faction: gallente
tech_level: 1

# Slot layout (from SDE, cached here for reference)
slots:
  high: 4
  mid: 3
  low: 5
  rig: 3

# Drone/fighter capacity
drones:
  bandwidth: 75
  bay: 125

# Hull bonuses summary
bonuses:
  - "10% drone damage and hitpoints per level"
  - "7.5% drone tracking per level"

# Ship role classification
roles:
  - drone_boat
  - armor_tank

# CRITICAL: Hull-specific fitting rules
fitting_rules:
  # Intentionally empty slots
  empty_slots:
    high: true  # Drone boats may leave high slots empty
    reason: "Primary damage comes from drones. High slots optional for utility."

  # Preferred tank type
  tank_type: armor_active

  # Weapon system (if any)
  weapons:
    primary: drones
    secondary: null  # Hybrids optional

  # Special instructions
  notes:
    - "Focus fitting resources on drone support and tank"
    - "High slots best used for: Drone Link Augmentor, Neuts, or left empty"
    - "Do NOT fit turrets expecting DPS contribution"
```

**Optional Fields:**
```yaml
# Recommended drone loadout by size
drone_recommendations:
  primary: "Hammerhead I"      # Medium - main DPS
  anti_frigate: "Hobgoblin I"  # Light - fast targets
  utility: "Salvage Drone I"   # Utility

# Cap stability expectations
capacitor:
  stable_expected: true
  notes: "Should be cap stable with active tank running"

# Typical engagement profile
engagement:
  range: "30-60km (drone control range)"
  speed: "kiting preferred"
  signature: "medium - MWD blooms sig"
```

#### 2. Archetype Fit File (`*.yaml`)

**Location:** `reference/archetypes/hulls/{class}/{hull}/{activity}/{variant}.yaml`

**Purpose:** Defines a complete fit with EFT block, stats, tuning instructions, and documentation.

**Required Fields:**
```yaml
# medium.yaml
archetype:
  hull: Vexor
  skill_tier: medium        # low | medium | high | alpha
  # Note: activity is derived from file path, not stored in file

# The actual fit in EFT format
eft: |
  [Vexor, L2 Missions - Medium Skills]

  Drone Damage Amplifier I
  Drone Damage Amplifier I
  Medium Armor Repairer I
  Energized Adaptive Nano Membrane I
  Reactive Armor Hardener

  50MN Microwarpdrive I
  Large Compact Pb-Acid Cap Battery
  Drone Navigation Computer I

  Drone Link Augmentor I
  [Empty High slot]
  [Empty High slot]
  [Empty High slot]

  Medium Auxiliary Nano Pump I
  Medium Auxiliary Nano Pump I
  Medium Nanobot Accelerator I

  Hammerhead I x5
  Hobgoblin I x5
  Hornet I x5

# Minimum skill requirements for this variant
skill_requirements:
  required:
    Drones: 4
    Medium Drone Operation: 3
    Gallente Cruiser: 3
    Armor Repair Systems: 3
  recommended:
    Drone Interfacing: 3
    Armor Compensation Skills: 3

# Expected performance (EOS-validated baseline)
stats:
  dps: 210
  ehp: 12500
  tank_sustained: 95      # HP/s active rep
  capacitor_stable: true
  align_time: 8.2
  speed_mwd: 1180
  drone_control_range: 56000
  validated_date: "2026-01-15"

# Documentation
notes:
  purpose: "General-purpose L2 mission runner for pilots with moderate skills"
  engagement: "Orbit at 30-40km, let drones do the work"
  warnings:
    - "Not cap stable with MWD running continuously"
    - "Recall drones before warping"
```

**Damage Tuning Section (Optional):**

Archetypes reference shared tuning profiles from `_shared/faction_tuning.yaml` rather than embedding faction-specific rules. This avoids repetition across archetypes.

```yaml
# How to adapt this fit for specific factions
damage_tuning:
  # Default damage dealt (drone types)
  default_damage: thermal  # Gallente drones

  # Reference shared tuning profile
  tank_profile: armor_active  # Lookup from _shared/faction_tuning.yaml

  # Override specific factions if needed (rare)
  overrides:
    angel_cartel:
      # Angels require rig changes for explosive resist
      rigs:
        - from: "Medium Auxiliary Nano Pump I"
          to: "Medium Anti-Explosive Pump I"
```

**Shared faction tuning** (`_shared/faction_tuning.yaml`) defines substitutions by tank type:

```yaml
# _shared/faction_tuning.yaml
armor_active:
  serpentis:
    modules:
      - from: "Energized Adaptive Nano Membrane I"
        to: "Armor Kinetic Hardener I"
      - from: "Reactive Armor Hardener"
        to: "Armor Thermal Hardener I"
    drones:
      primary: thermal    # Hammerhead
      anti_frigate: thermal  # Hobgoblin

  guristas:
    modules:
      - from: "Energized Adaptive Nano Membrane I"
        to: "Armor Kinetic Hardener I"
      - from: "Reactive Armor Hardener"
        to: "Armor Thermal Hardener I"
    drones:
      primary: kinetic    # Vespa
      anti_frigate: kinetic  # Hornet

  blood_raiders:
    modules:
      - from: "Energized Adaptive Nano Membrane I"
        to: "Armor EM Hardener I"
      - from: "Reactive Armor Hardener"
        to: "Armor Thermal Hardener I"
    drones:
      primary: em         # Infiltrator
      anti_frigate: em    # Acolyte

  sansha:
    # Same resist profile as Blood Raiders
    inherit: blood_raiders

  angel_cartel:
    modules:
      - from: "Energized Adaptive Nano Membrane I"
        to: "Armor Explosive Hardener I"
      - from: "Reactive Armor Hardener"
        to: "Armor Kinetic Hardener I"
    # Angels may require rig changes - archetype overrides handle this
    drones:
      primary: em         # Infiltrator (weakness)
      anti_frigate: em    # Acolyte

shield_passive:
  # Similar structure for shield tank profiles
  serpentis:
    modules:
      - from: "Adaptive Invulnerability Shield Hardener I"
        to: "Kinetic Shield Hardener I"
      # etc.
```

**Benefits of shared tuning:**
- Single source of truth for faction resist profiles
- Archetypes only specify tank type, not every faction substitution
- `overrides` section handles edge cases (rig swaps, unusual fits)
- Drone damage types use keywords (`thermal`, `kinetic`) resolved to actual drone names by skill tier

**Damage Tuning Output Behavior:**

When a user requests a faction-tuned fit (e.g., `--faction serpentis`), the CLI:
1. Loads the base archetype EFT
2. Resolves `tank_profile` from `_shared/faction_tuning.yaml`
3. Applies module substitutions from shared profile
4. Applies any archetype-specific `overrides` (e.g., rig swaps for Angels)
5. Resolves drone damage types to actual drone names using `drone_types` mapping and skill tier
6. Validates the resulting fit via EOS (catches invalid substitutions, fitting overflow)
7. Returns the modified EFT with a header noting the tuning applied

Example output:
```
# Tuned for Serpentis (Kin/Therm damage, Thermal weakness)
# Base: vexor/pve/missions/l2/medium
# Tank profile: armor_active

[Vexor, L2 Missions - Medium Skills - Anti-Serpentis]
...
```

**Upgrade Path Section (Optional):**
```yaml
# Progression to higher skill variants
upgrade_path:
  next_tier: high
  key_upgrades:
    - module: "Drone Damage Amplifier I"
      upgrade_to: "Drone Damage Amplifier II"
      skill_required: "Weapon Upgrades 4"

    - module: "Hammerhead I"
      upgrade_to: "Hammerhead II"
      skill_required: "Medium Drone Operation 5"

    - module: "Medium Armor Repairer I"
      upgrade_to: "Medium Armor Repairer II"
      skill_required: "Repair Systems 5"
```

**Note:** Hull progression (e.g., "next ship: Myrmidon") is intentionally excluded. Career advice belongs in pilot guidance documentation, not fitting data.

#### 3. Design Document (`_design.md`)

**Location:** `reference/archetypes/hulls/{class}/{hull}/{activity}/_design.md`

**Purpose:** Documents the design rationale and slot philosophy for all variants of an activity. This is **prose documentation only**—tier variants are complete standalone YAML files, not generated from any template.

**Why prose instead of YAML?** Earlier drafts used a `_base.yaml` with structured `slot_template` and `tier_mapping` fields. This implied tooling that wouldn't exist and created maintenance burden. Prose documentation serves the actual use cases:
1. Onboarding contributors to the archetype's philosophy
2. Explaining non-obvious choices (empty slots, specific module selections)
3. Providing context for code review of new variants

**Example: `_design.md` for Vexor missions**

```markdown
# Vexor Mission Fit Design

## Philosophy

The Vexor is a drone boat. Primary DPS comes from drones, not turrets.
This archetype prioritizes drone support and active armor tank.

## Slot Allocation

### Lows (5 slots)
- **2x Drone Damage Amplifier** - Core DPS multiplier
- **1x Medium Armor Repairer** - Active tank sustain
- **2x Resist modules** - Adaptive or faction-specific hardeners

### Mids (3 slots)
- **1x Propulsion** - MWD for range control
- **1x Cap Battery** - Sustain active tank
- **1x Drone Navigation Computer** - Drone speed for application

### Highs (4 slots)
- **1x Drone Link Augmentor** - Extended control range
- **3x Empty** - Intentionally unfitted. See hull manifest.

### Rigs (3 slots)
- **2x Auxiliary Nano Pump** - Rep amount
- **1x Nanobot Accelerator** - Rep speed

### Drones
- **5x Medium (primary)** - Main DPS, match to enemy weakness
- **5x Light (anti-frigate)** - Fast target cleanup
- **5x Light (utility)** - Alternate damage type or salvage

## Tier Progression

| Component | Low | Medium | High | Alpha |
|-----------|-----|--------|------|-------|
| DDAs | T1 | T1 | T2 | T1 |
| Repper | T1 | T1 | T2 | T1 |
| MWD | Enduring | T1 | Restrained | Compact |
| Drones | T1 | T1 | T2 | T1 |

## Notes

- Cap stable with repper running, not with MWD
- Recall drones before warping (drone aggro loss)
- For Angels, consider swapping one Nano Pump for Anti-Explosive
```

This format is easier to maintain, clearly communicates intent, and doesn't suggest nonexistent tooling.

#### 4. Shared Configuration Files

**`_shared/damage_profiles.yaml`:**

Reference data for faction damage. Used by `faction_tuning.yaml` and displayed in mission briefs.

```yaml
# Faction damage dealt and weaknesses
factions:
  serpentis:
    damage_dealt:
      thermal: 55
      kinetic: 45
    weakness: thermal
    ewar: sensor_dampener

  guristas:
    damage_dealt:
      kinetic: 80
      thermal: 20
    weakness: kinetic
    ewar: ecm

  blood_raiders:
    damage_dealt:
      em: 50
      thermal: 50
    weakness: em
    ewar: energy_neutralizer

  sansha:
    damage_dealt:
      em: 55
      thermal: 45
    weakness: em
    ewar: tracking_disruptor

  angel_cartel:
    damage_dealt:
      explosive: 50
      kinetic: 42
      thermal: 8
    weakness: explosive
    ewar: target_painter

  rogue_drones:
    damage_dealt:
      explosive: 30
      kinetic: 25
      thermal: 25
      em: 20
    weakness: em
    ewar: none

  triglavian:
    damage_dealt:
      thermal: 60
      explosive: 40
    weakness: thermal
    ewar: none
    notes: "Damage ramps up over time"
```

**`_shared/faction_tuning.yaml`:**

Centralized module/drone substitutions by tank type. Archetypes reference a `tank_profile` instead of embedding faction rules.

```yaml
# Tank-specific faction tuning rules
# Archetypes reference these by tank_profile name

armor_active:
  serpentis:
    modules:
      - slot: resist
        to: ["Armor Kinetic Hardener I", "Armor Thermal Hardener I"]
    drones: { primary: thermal, anti_frigate: thermal }

  guristas:
    modules:
      - slot: resist
        to: ["Armor Kinetic Hardener I", "Armor Thermal Hardener I"]
    drones: { primary: kinetic, anti_frigate: kinetic }

  blood_raiders:
    modules:
      - slot: resist
        to: ["Armor EM Hardener I", "Armor Thermal Hardener I"]
    drones: { primary: em, anti_frigate: em }

  sansha:
    inherit: blood_raiders

  angel_cartel:
    modules:
      - slot: resist
        to: ["Armor Explosive Hardener I", "Armor Kinetic Hardener I"]
    rigs:
      # Angels often need explosive rig - archetype can override
      - slot: tank_rig
        optional_swap: "Medium Anti-Explosive Pump I"
    drones: { primary: em, anti_frigate: em }

  rogue_drones:
    modules:
      - slot: resist
        to: ["Armor EM Hardener I", "Armor Thermal Hardener I"]
    drones: { primary: em, anti_frigate: em }

shield_passive:
  serpentis:
    modules:
      - slot: resist
        to: ["Kinetic Shield Hardener I", "Thermal Shield Hardener I"]
    drones: { primary: thermal, anti_frigate: thermal }
  # ... similar structure for other factions

shield_active:
  # ... similar structure

# Drone type resolution by skill tier
drone_types:
  thermal: { light: "Hobgoblin", medium: "Hammerhead", heavy: "Ogre" }
  kinetic: { light: "Hornet", medium: "Vespa", heavy: "Wasp" }
  em: { light: "Acolyte", medium: "Infiltrator", heavy: "Praetor" }
  explosive: { light: "Warrior", medium: "Valkyrie", heavy: "Berserker" }
```

**`_shared/module_tiers.yaml`:**
```yaml
# Module upgrade paths by category
# Ordered: meta variants → T1 → T2 → faction (increasing skill/cost)
upgrade_paths:
  drone_damage_amplifier:
    # No meta variants exist for DDAs
    t1: "Drone Damage Amplifier I"
    t2: "Drone Damage Amplifier II"
    faction: "Federation Navy Drone Damage Amplifier"

  medium_armor_repairer:
    enduring: "Medium I-a Enduring Armor Repairer"    # Low cap use
    compact: "Medium Compact Armor Repairer"          # Low fitting
    t1: "Medium Armor Repairer I"
    t2: "Medium Armor Repairer II"
    faction: "Corpum C-Type Medium Armor Repairer"

  mwd_50mn:
    enduring: "50MN Cold-Gas Enduring Microwarpdrive" # Low cap use
    compact: "50MN Y-T8 Compact Microwarpdrive"       # Low fitting
    restrained: "50MN Quad LiF Restrained Microwarpdrive"  # Low sig bloom
    t1: "50MN Microwarpdrive I"
    t2: "50MN Microwarpdrive II"
```

**`_shared/skill_tiers.yaml`:**
```yaml
# What defines each skill tier
tiers:
  alpha:
    description: "Alpha clone limitations"
    max_skill_level: 5        # Most skills capped at 5, some at 3-4
    module_restriction: "T1 and Meta only, no T2 weapons"
    notes: "Cannot use T2 weapons, limited ship selection"

  low:
    description: "New pilot, basic trained"
    typical_sp: "500k - 2M"
    core_skills: 3
    weapon_skills: 3
    ship_skills: 3

  medium:
    description: "Established pilot, focused training"
    typical_sp: "5M - 15M"
    core_skills: 4
    weapon_skills: 4
    ship_skills: 4

  high:
    description: "Specialized pilot, maxed relevant skills"
    typical_sp: "20M+"
    core_skills: 5
    weapon_skills: 5
    ship_skills: 5
```

---

## Naming Conventions

### Directory Names

| Level | Convention | Examples |
|-------|------------|----------|
| Class | Lowercase, singular | `frigate`, `cruiser`, `battleship` |
| Hull | Lowercase | `vexor`, `drake`, `raven` |
| Activity | Lowercase, descriptive | `missions`, `ratting`, `abyss` |
| Sub-activity | Lowercase | `l2`, `highsec`, `t3` |

### File Names

| File Type | Convention | Examples |
|-----------|------------|----------|
| Manifest | `manifest.yaml` | Always this name |
| Design doc | `_design.md` | Prose documentation, prefixed with underscore |
| Skill variant | `{tier}.yaml` | `low.yaml`, `medium.yaml`, `high.yaml`, `alpha.yaml` |
| Damage variant | `{faction}.yaml` | `serpentis.yaml`, `guristas.yaml` |
| Role variant | `{role}.yaml` | `kiting.yaml`, `brawl.yaml`, `tackle.yaml` |

### EFT Fit Names

Format: `[Hull, Activity - Skill Tier]`

Examples:
- `[Vexor, L2 Missions - Low Skills]`
- `[Vexor, L2 Missions - Medium Skills]`
- `[Vexor, Anti-Serpentis - Medium Skills]`
- `[Drake, L3 Passive Shield - Alpha]`

---

## File Role Summary

### Mandatory Files

| File | Purpose | Required |
|------|---------|----------|
| `manifest.yaml` | Hull metadata, slot layout, fitting rules | Per hull |
| At least one `{tier}.yaml` | Actual fit definition | Per activity |

### Optional Files

| File | Purpose | When to Include |
|------|---------|-----------------|
| `_design.md` | Prose documentation of slot philosophy | When multiple tiers exist |
| `README.md` | Activity-specific notes | When additional context needed |

**Note:** Faction-specific fits are no longer separate files. Use `damage_tuning` section with shared `tank_profile` reference.

### Schema Files (One-Time Setup)

| File | Purpose |
|------|---------|
| `archetype.schema.json` | Validates fit files |
| `manifest.schema.json` | Validates hull manifests |
| `damage_profile.schema.json` | Validates damage tuning |

**Note:** JSON Schema definitions will be created during Phase 1 implementation. Key validations include:
- Required fields present (`hull`, `eft`, `skill_tier`)
- EFT format validity (starts with `[Hull, Name]`)
- Skill tier enum (`low` | `medium` | `high` | `alpha`)
- Stats numeric and non-negative
- Alpha variants: no T2 modules (pattern: ` II$`)
- Drone bay capacity: total drone volume ≤ manifest `drones.bay`

---

## Integration Points

### 1. Fitting Skill Enhancement

**File:** `.claude/skills/fitting/SKILL.md`

Add archetype lookup to the fitting workflow:

```markdown
## Archetype Lookup Protocol

When building a fit, first check for matching archetype:

1. **Search archetypes:** `reference/archetypes/hulls/{class}/{hull}/{activity}/`
2. **Match skill tier:** Use pilot profile to determine tier
3. **Apply damage tuning:** If mission/enemy specified, apply faction adjustments
4. **Validate via EOS:** Archetype is starting point, always validate

**If archetype exists:**
- Load archetype as base
- Apply any requested modifications
- Validate and present

**If no archetype exists:**
- Build fit from scratch using fitting philosophy
- Consider contributing new archetype afterward
```

### 2. CLI Commands

```bash
# List available archetypes for a hull
uv run aria-esi archetype list vexor

# Show archetype details
uv run aria-esi archetype show vexor/pve/missions/l2/medium

# Generate fit from archetype with damage tuning
uv run aria-esi archetype generate vexor/pve/missions/l2/medium --faction serpentis

# Validate all archetypes against EOS
uv run aria-esi archetype validate --all

# Validate specific archetype
uv run aria-esi archetype validate vexor/pve/missions/l2/medium
```

### 3. MCP Integration (Future)

Add `archetype` action to fitting dispatcher (singular, consistent with CLI):

```python
# List archetypes for a hull
fitting(action="archetype_list", hull="vexor")

# Show archetype details
fitting(action="archetype_show", path="vexor/pve/missions/l2/medium")

# Generate tuned fit
fitting(action="archetype_generate", path="vexor/pve/missions/l2/medium", faction="serpentis")

# Validate archetype(s)
fitting(action="archetype_validate", path="vexor/pve/missions/l2/medium")  # or path="all"
```

**Naming convention:** CLI and MCP use singular `archetype` with action verbs (`list`, `show`, `generate`, `validate`).

---

## Implementation Plan

### Phase 1: Foundation

- [ ] Create directory structure
- [ ] Define JSON schemas for validation (including alpha constraints)
- [ ] Create shared configuration files:
  - [ ] `_shared/damage_profiles.yaml`
  - [ ] `_shared/faction_tuning.yaml` (new: centralized tuning rules)
  - [ ] `_shared/module_tiers.yaml`
  - [ ] `_shared/skill_tiers.yaml`
  - [ ] `_shared/tank_archetypes.yaml`
- [ ] Write README and documentation

### Phase 2: Proof of Concept (Vexor + Drake)

Validate the schema with two hulls before expanding:

| Hull | Class | Activity Coverage |
|------|-------|-------------------|
| Vexor | Cruiser | PvE missions (L2), ratting |
| Drake | Battlecruiser | PvE missions (L3), ratting |

For each hull:
- [ ] Create manifest with fitting rules
- [ ] Implement low/medium/high/alpha variants
- [ ] Add damage tuning for 3+ factions
- [ ] Validate all fits via EOS
- [ ] Gather feedback on schema usability

**Exit criteria:** Both hulls fully implemented, schema validated, no blocking issues discovered.

### Phase 3: Expand PvE Coverage

After Phase 2 validation, expand to additional PvE hulls:

| Hull | Class | Activity Coverage |
|------|-------|-------------------|
| Myrmidon | Battlecruiser | PvE missions (L3) |
| Caracal | Cruiser | PvE missions (L2) |
| Venture | Mining Frigate | Mining, gas huffing |
| Heron | Frigate | Exploration |
| Praxis | Battleship | PvE missions (L4) |

### Phase 4: Integration

- [ ] Update fitting skill to use archetype lookup
- [ ] Implement CLI commands
- [ ] Add CI validation for archetype validity
- [ ] Document contribution process for new archetypes

### Phase 5: Migration

Existing fits in `reference/ships/fittings/` must be addressed:

**Migration strategy:**

| Current File | Action | Destination |
|--------------|--------|-------------|
| `vexor_l2_missions.md` | Migrate | `hulls/cruiser/vexor/pve/missions/l2/medium.yaml` |
| `vexor_serpentis.md` | Migrate as tuning | Inline in `damage_tuning.overrides` |
| `drake_l3_passive.md` | Migrate | `hulls/battlecruiser/drake/pve/missions/l3/` |
| Fits without clear activity | Review | Keep in legacy or archive |

**Process:**

1. **Inventory:** Catalog all existing fits with hull/activity/tier metadata
2. **Convert:** Transform markdown fits to YAML archetype format
3. **Validate:** Run EOS validation on converted archetypes
4. **Redirect:** Update fitting skill to check archetypes first, legacy second
5. **Deprecate:** Add deprecation notice to `reference/ships/fittings/README.md`
6. **Remove:** After 2 release cycles, delete legacy fits (keep git history)

**Coexistence period:** Both systems work during migration. Fitting skill checks:
1. `reference/archetypes/hulls/` (new)
2. `reference/ships/fittings/` (legacy fallback)

### Future: PvP Archetypes (Separate Proposal)

PvP fits are deferred to a follow-on proposal because:
- Highly meta-dependent (balance patches shift viability)
- Require different validation criteria (no EOS "success" metric)
- Different audience needs (theory vs. proven fits)

PvP will be addressed after PvE foundation is stable.

---

## Validation Protocol

All archetypes must pass these checks before merge:

### 1. Schema Validation

```bash
# Validate YAML against schema
uv run aria-esi archetype validate --schema
```

### 2. EOS Validation

```bash
# Validate all fits work in EOS
uv run aria-esi archetype validate --eos
```

### 3. Consistency Checks

- [ ] Hull in manifest matches directory name
- [ ] Skill tier in archetype matches filename
- [ ] All modules in EFT string exist in SDE
- [ ] Total DPS matches EOS output within 5% tolerance
- [ ] EHP matches EOS output within 5% tolerance
- [ ] Damage tuning references valid factions from `_shared/faction_tuning.yaml`
- [ ] Drone loadout fits within hull drone bay capacity (from manifest)

### 3a. Alpha Variant Validation

Alpha clones have module restrictions. Schema enforces:

```yaml
# archetype.schema.json (excerpt)
alpha_constraints:
  forbidden_module_patterns:
    - " II$"           # No T2 modules
    - "Siege Module"   # Capital modules
    - "Bastion Module"
  forbidden_ship_patterns:
    - "^Marauder"      # T2 hulls
    - "^Strategic"
  max_skill_levels:
    # Skills capped for alpha
    Medium Drone Operation: 4
    Gallente Cruiser: 3
```

**Validation rule:** If `skill_tier: alpha`, scan EFT block for forbidden patterns and reject on match.

### 4. Stats Drift Detection (CI)

Archetype stats (`dps`, `ehp`, `tank_sustained`, etc.) will drift from reality as:
- EOS data updates (new SDE releases)
- Module balance changes (patches)

**Automated revalidation:**
```bash
# CI job: weekly or on EOS data update
uv run aria-esi archetypes validate --eos --update-stats

# Flags archetypes where EOS output diverges >5% from declared stats
# Outputs diff report for review
```

**Revalidation triggers:**
- Weekly scheduled CI job
- EOS data file updates (detected via git diff)
- Manual trigger before releases

**On divergence:**
- CI creates issue/PR with updated stats
- Human reviews for unexpected changes (may indicate balance patch)
- `validated_date` updated on merge

### 5. Manual Review

- [ ] Fitting philosophy appropriate for activity
- [ ] Skill requirements realistic for tier
- [ ] Upgrade path is sensible
- [ ] Notes are helpful and accurate

---

## Example: Complete Vexor Archetype

```
reference/archetypes/hulls/cruiser/vexor/
├── manifest.yaml               # Hull rules: drone_boat, empty highs OK
└── pve/
    ├── missions/
    │   ├── _design.md          # Prose documentation of slot philosophy
    │   └── l2/
    │       ├── low.yaml        # 500k SP pilot
    │       ├── medium.yaml     # 5M SP pilot
    │       ├── high.yaml       # 20M+ SP pilot
    │       └── alpha.yaml      # Alpha clone
    └── anomalies/
        ├── belt/
        │   └── medium.yaml     # Belt ratting
        └── combat/
            ├── low.yaml        # Combat anomalies, low skills
            └── medium.yaml     # Combat anomalies, medium skills
```

### `manifest.yaml` (excerpt)

```yaml
hull: Vexor
class: cruiser
faction: gallente

fitting_rules:
  empty_slots:
    high: true
    reason: "Drone boat - primary DPS from drones. Highs for utility only."
  tank_type: armor_active
  weapons:
    primary: drones
```

### `l2/medium.yaml` (excerpt)

```yaml
archetype:
  hull: Vexor
  skill_tier: medium
  # activity derived from path: pve/missions/l2

eft: |
  [Vexor, L2 Missions - Medium Skills]

  Drone Damage Amplifier I
  Drone Damage Amplifier I
  Medium Armor Repairer I
  Energized Adaptive Nano Membrane I
  Reactive Armor Hardener

  50MN Microwarpdrive I
  Large Compact Pb-Acid Cap Battery
  Drone Navigation Computer I

  Drone Link Augmentor I
  [Empty High slot]
  [Empty High slot]
  [Empty High slot]

  Medium Auxiliary Nano Pump I
  Medium Auxiliary Nano Pump I
  Medium Nanobot Accelerator I

  Hammerhead I x5
  Hobgoblin I x5
  Hornet I x5

# Faction tuning uses shared profiles
damage_tuning:
  default_damage: thermal
  tank_profile: armor_active  # References _shared/faction_tuning.yaml

  # Override for Angels (needs explosive rig)
  overrides:
    angel_cartel:
      rigs:
        - from: "Medium Auxiliary Nano Pump I"
          to: "Medium Anti-Explosive Pump I"
```

---

## Open Questions

1. **Should archetypes include faction/officer module variants?**
   - Recommendation: No - keep to T1/Meta/T2. Faction fits are edge cases.

2. **How to handle hulls with multiple valid tank philosophies?** (e.g., Gnosis can armor or shield)
   - Recommendation: Create separate activity branches (e.g., `missions-armor/`, `missions-shield/`)

3. **How granular should mission level variants be?**
   - Recommendation: L1/L2/L3/L4 for mission runners. Don't create L1-specific fits for hulls inappropriate for L1.

**Resolved questions:**

- **Abyssal fit organization?** → Flattened to `t{tier}-{filament}.yaml` format
- **Should damage tuning be validated via EOS?** → Yes, included in validation protocol
- **Ratting vs anomalies?** → Consolidated under `anomalies/` with `belt/` and `combat/` subdirectories

---

## Success Criteria

1. **Proof of concept:** Vexor and Drake archetypes fully implemented and validated
2. **Coverage:** Top 10 PvE hulls have complete archetype trees
3. **Validation:** 100% of archetypes pass EOS validation (including alpha constraints)
4. **Usability:** Fitting skill can locate and apply archetypes automatically
5. **Accuracy:** Stats in archetype files match EOS output within 5% (total DPS, EHP)
6. **Freshness:** CI detects and flags stats drift within 1 week of EOS data updates
7. **Documentation:** Every archetype has clear purpose, usage, and upgrade path
8. **Migration:** Legacy fits in `reference/ships/fittings/` catalogued with migration status

---

## Summary

| Aspect | Current State | Proposed State |
|--------|---------------|----------------|
| Organization | Flat file structure | Hierarchical by hull/activity/tier |
| Skill variants | One fit per hull/activity | low/medium/high/alpha variants |
| Damage tuning | Separate files | Shared `faction_tuning.yaml` with archetype overrides |
| Hull rules | Ad-hoc in skill docs | Manifest files per hull |
| Design docs | N/A | Prose `_design.md` (not processed) |
| Validation | Manual | Schema + EOS automated + CI drift detection |
| Alpha validation | None | Schema-enforced module restrictions |
| Discovery | File search | CLI and MCP lookup (singular `archetype` command) |
| Migration | N/A | Phased migration with coexistence period |
| Scope | PvE + PvP mixed | PvE only (PvP deferred) |

This library provides a structured foundation for PvE fitting recommendations while maintaining the flexibility to adapt to pilot skills, mission targets, and operational constraints. PvP archetypes will be addressed in a follow-on proposal once the PvE foundation is validated.
