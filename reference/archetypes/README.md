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
│   ├── skill_tiers.yaml                # What defines low/medium/high/alpha
│   └── tank_archetypes.yaml            # Tank philosophy definitions
│
└── hulls/                              # Hull-organized archetypes
    └── {class}/                        # Ship class (frigate, cruiser, etc.)
        └── {hull}/                     # Hull name (vexor, drake, etc.)
            ├── manifest.yaml           # Hull metadata and rules
            └── pve/                    # PvE activity branch
                └── missions/           # Security missions
                    ├── _design.md      # Design rationale (documentation)
                    └── l2/             # Mission level
                        ├── low.yaml    # Low skill variant
                        ├── medium.yaml # Medium skill variant
                        ├── high.yaml   # High skill variant
                        └── alpha.yaml  # Alpha clone variant
```

## Skill Tiers

| Tier | Description | Typical SP | Modules |
|------|-------------|------------|---------|
| **alpha** | Alpha clone restrictions | Varies | T1/Meta only |
| **low** | New pilot, basic trained | 500k - 2M | T1/Compact |
| **medium** | Established pilot | 5M - 15M | T1/T2 tank |
| **high** | Specialized pilot | 20M+ | Full T2 |

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
  skill_tier: medium

eft: |
  [Vexor, L2 Missions - Medium Skills]
  Drone Damage Amplifier I
  ...

skill_requirements:
  required:
    Drones: 4
    Medium Drone Operation: 3
  recommended:
    Drone Interfacing: 3

stats:
  dps: 210
  ehp: 12500
  tank_sustained: 95
  capacitor_stable: true

damage_tuning:
  default_damage: thermal
  tank_profile: armor_active

notes:
  purpose: "General-purpose L2 mission runner"
  engagement: "Orbit at 30-40km, let drones do the work"
  warnings:
    - "Not cap stable with MWD running continuously"
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
- `vexor/pve/missions/l2/low`
- `vexor/pve/missions/l2/medium`
- `vexor/pve/missions/l2/high`
- `vexor/pve/missions/l2/alpha`

### Battlecruisers

**Drake** (Caldari passive shield tank)
- `drake/pve/missions/l3/low`
- `drake/pve/missions/l3/medium`
- `drake/pve/missions/l3/high`
- `drake/pve/missions/l3/alpha`

## Contributing

To add a new archetype:

1. Create hull directory: `hulls/{class}/{hull}/`
2. Create `manifest.yaml` with hull metadata
3. Create activity directory: `pve/missions/{level}/`
4. Create `_design.md` with slot philosophy
5. Create tier variants: `low.yaml`, `medium.yaml`, `high.yaml`, `alpha.yaml`
6. Run validation: `uv run aria-esi archetype validate --all`

See existing archetypes for examples.
