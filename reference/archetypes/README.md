# Archetype Fittings Library

The Archetype Fittings Library provides hierarchical, skill-tiered ship fittings organized by hull, activity, and skill level. Each archetype serves as a tunable reference fit that can be adapted for specific damage profiles, skill levels, and operational constraints.

## Quick Start

```bash
# List all available archetypes
uv run aria-esi archetype list

# List archetypes for a specific hull
uv run aria-esi archetype list vexor

# Show archetype details
uv run aria-esi archetype show vexor/pve/missions/l2/medium

# Generate faction-tuned fit
uv run aria-esi archetype generate vexor/pve/missions/l2/medium --faction serpentis

# Validate all archetypes
uv run aria-esi archetype validate --all
```

## Directory Structure

```
reference/archetypes/
├── README.md                           # This file
├── _shared/                            # Shared configuration
│   ├── damage_profiles.yaml            # Faction damage dealt/resisted
│   ├── faction_tuning.yaml             # Tank/drone adjustments by faction
│   ├── module_tiers.yaml               # T1 → Meta → T2 upgrade paths
│   ├── skill_tiers.yaml                # What defines t1/meta/t2/t2_optimal
│   └── tank_archetypes.yaml            # Tank philosophy definitions
│
└── hulls/                              # Hull-organized archetypes
    └── {class}/                        # Ship class (frigate, cruiser, etc.)
        └── {hull}/                     # Hull name (vexor, drake, etc.)
            ├── manifest.yaml           # Hull metadata and rules
            └── pve/                    # PvE activity branch
                └── missions/           # Security missions
                    ├── _design.md      # Design rationale (documentation)
                    └── l3/             # Mission level
                        ├── meta.yaml   # Variant selection metadata
                        ├── armor/      # Armor tank variants
                        │   ├── meta.yaml
                        │   ├── t2.yaml
                        │   └── t2_optimal.yaml
                        └── shield/     # Shield tank variants
                            └── t2_buffer.yaml
```

## Skill Tiers

| Tier | Description | Typical SP | Modules |
|------|-------------|------------|---------|
| **t1** | Entry-level, basic modules | 500k - 2M | T1/Meta 0 |
| **meta** | Established pilot, meta modules | 5M - 15M | Compact/Meta, T2 tank |
| **t2** | Skilled pilot, T2 modules | 15M - 25M | Full T2 |
| **t2_optimal** | Specialized, maxed skills | 25M+ | T2 + faction where needed |

## Path Format

Archetype paths follow this format:
```
{hull}/{activity_branch}/{activity}/{level}/{tier}
```

Examples:
- `vexor/pve/missions/l2/medium`
- `drake/pve/missions/l3/alpha`

## Faction Tuning

Archetypes can be tuned for specific factions using the `--faction` flag:

```bash
uv run aria-esi archetype generate vexor/pve/missions/l2/medium --faction serpentis
```

Supported factions:
- `serpentis` - Kinetic/Thermal damage, weak to Thermal
- `guristas` - Kinetic/Thermal damage, weak to Kinetic
- `blood_raiders` - EM/Thermal damage, weak to EM
- `sansha` - EM/Thermal damage, weak to EM
- `angel_cartel` - Explosive/Kinetic damage, weak to Explosive
- `rogue_drones` - Omni damage, weak to EM

## Tank Variants

Some hulls support multiple tank types (armor vs shield). When variants exist, fits are organized into subdirectories:

```
l3/
├── meta.yaml           # Variant selection metadata
├── armor/              # Armor tank variants
│   ├── meta.yaml
│   ├── t2.yaml
│   └── t2_optimal.yaml
└── shield/             # Shield tank variants
    └── t2_buffer.yaml
```

The `meta.yaml` at the level root defines:
- Available tank variants
- Default variant (typically matches hull's native tank)
- Selection strategy (skill-based auto-selection)
- Skill comparison rules for choosing armor vs shield

### Skill-Based Selection

When `selection_strategy: skill_based` is set, the system compares pilot skills:

```yaml
skill_comparison:
  armor:
    skills: [Hull Upgrades, Mechanics, Repair Systems, Armor Rigging]
  shield:
    skills: [Shield Management, Shield Operation, Shield Upgrades, Tactical Shield Manipulation]
  tie_breaker: armor
```

The variant with higher total skill points is recommended.

### Specifying Tank Type

```bash
# Auto-select based on skills
uv run aria-esi archetype recommend vexor/pve/missions/l3

# Explicitly request shield variant
uv run aria-esi archetype show vexor/pve/missions/l3/shield/t2_buffer

# List all variants
uv run aria-esi archetype list vexor/pve/missions/l3 --show-variants
```

## Community Fits & Attribution

Community-contributed fits include an `attribution` block:

```yaml
attribution:
  author: "iBeast"
  source: "HiSec PvE Community Fits"
  source_url: "https://..."      # optional
  license: community             # community | public_domain | aria_original
  verified_date: "2026-02-04"
```

**License types:**
- `aria_original` - Created by ARIA/project maintainers
- `community` - Contributed by EVE community members
- `public_domain` - No attribution required

When displaying community fits, credit the original author.

## Hull Manifests

Each hull has a `manifest.yaml` that defines:

```yaml
hull: Vexor
class: cruiser
faction: gallente

slots:
  high: 4
  mid: 3
  low: 5
  rig: 3

drones:
  bandwidth: 75
  bay: 125

fitting_rules:
  tank_type: armor_active
  empty_slots:
    high: true
    reason: "Drone boat - primary DPS from drones"
  weapons:
    primary: drones
```

## Archetype Files

Each archetype YAML file contains:

```yaml
archetype:
  hull: Vexor
  skill_tier: t2
  tank_type: armor_active      # Required: armor_active, armor_passive, shield_active, shield_buffer
  omega_required: true

# Optional: for community-contributed fits
attribution:
  author: "iBeast"
  source: "HiSec PvE Community Fits"
  license: community

eft: |
  [Vexor, L3 Missions - Armor T2]
  Drone Damage Amplifier II
  ...

skill_requirements:
  required:
    Drones: 5
    Medium Drone Operation: 5
  recommended:
    Drone Interfacing: 4

stats:
  dps: 340
  ehp: 9900
  tank_sustained: 130
  capacitor_stable: true

damage_tuning:
  default_damage: thermal
  tank_profile: armor_active

notes:
  purpose: "Solid L3 runner with T2 performance"
  engagement: "Orbit at 30-40km, let drones do the work"
  warnings:
    - "Still a cruiser in BC content - manage aggro"
```

## Validation

Validate archetypes to ensure correctness:

```bash
# Validate specific archetype
uv run aria-esi archetype validate vexor/pve/missions/l2/medium

# Validate all archetypes
uv run aria-esi archetype validate --all

# Include EOS fit validation
uv run aria-esi archetype validate --all --eos
```

Validation checks:
- Schema compliance (required fields, valid values)
- Alpha restrictions (no T2 modules for alpha tier)
- Hull/manifest consistency
- EOS fitting validity (optional, with `--eos`)

## Available Archetypes

### Cruisers

**Vexor** (Gallente drone cruiser)

L2 Missions:
- `vexor/pve/missions/l2/t1`
- `vexor/pve/missions/l2/meta`
- `vexor/pve/missions/l2/t2_optimal`

L3 Missions (with tank variants):
- Armor variants:
  - `vexor/pve/missions/l3/armor/meta`
  - `vexor/pve/missions/l3/armor/t2`
  - `vexor/pve/missions/l3/armor/t2_optimal`
- Shield variants:
  - `vexor/pve/missions/l3/shield/t2_buffer` *(community: iBeast)*

### Battlecruisers

**Drake** (Caldari passive shield tank)
- `drake/pve/missions/l3/t1`
- `drake/pve/missions/l3/meta`
- `drake/pve/missions/l3/t2_optimal`

## Contributing

### Adding a New Hull

1. Create hull directory: `hulls/{class}/{hull}/`
2. Create `manifest.yaml` with hull metadata
3. Create activity directory: `pve/missions/{level}/`
4. Create `_design.md` with slot philosophy
5. Create tier variants: `t1.yaml`, `meta.yaml`, `t2.yaml`, `t2_optimal.yaml`
6. Run validation: `uv run aria-esi archetype validate --all`

### Adding Tank Variants

1. Create tank subdirectories: `armor/`, `shield/`
2. Move existing fits to appropriate subdirectory
3. Add `tank_type` field to each archetype
4. Create `meta.yaml` at level root with variant selection logic
5. Update hull manifest if needed

### Contributing Community Fits

1. Create fit file in appropriate tank subdirectory
2. Include `attribution` block with author credit
3. Use descriptive filename: `t2_buffer.yaml`, `speed_tank.yaml`
4. Ensure fit is EOS-validated
5. Submit PR with fit description and use case

See existing archetypes for examples.
