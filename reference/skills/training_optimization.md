# Skill Training Optimization

Maximize training efficiency through attributes, implants, and planning.

## The Five Attributes

| Attribute | Primary Skills | Secondary Skills |
|-----------|----------------|------------------|
| **Perception** | Spaceship Command, Gunnery, Missiles | Navigation |
| **Willpower** | Spaceship Command, Gunnery, Missiles | Drones |
| **Intelligence** | Electronics, Engineering, Science, Industry | Most support skills |
| **Memory** | Engineering, Armor, Shields, Drones | Science, Industry |
| **Charisma** | Social, Leadership, Trade | Corporation Management |

## Training Speed Formula

```
SP/minute = Primary Attribute + (Secondary Attribute × 0.5)
```

**Omega clone:** Full rate
**Alpha clone:** 50% rate

## Default vs Optimized Attributes

| Setup | SP/minute | SP/hour | SP/day |
|-------|-----------|---------|--------|
| Default (20 all, 19 cha) | ~30 | 1,800 | 43,200 |
| Remapped + Basic Implants | ~36 | 2,160 | 51,840 |
| Optimized + +5 Implants | ~45 | 2,700 | 64,800 |

**Maximum possible:** 45 SP/minute with perfect remap and +5 implants.

## Neural Remapping

### Constraints
- **Total base points:** 99 (fixed)
- **Redistributable:** 14 points
- **Minimum per attribute:** 17
- **Maximum per attribute:** 27

### Remap Availability
- **Normal remap:** 1 per year (refreshes annually)
- **Bonus remaps:** 2 one-time use (new characters)

### Recommended Remaps by Focus

| Focus | Primary | Secondary | Distribution |
|-------|---------|-----------|--------------|
| Combat/Ships | Perception | Willpower | Per 27 / Wil 21 |
| Industry/Science | Intelligence | Memory | Int 27 / Mem 21 |
| Drones | Memory | Perception | Mem 27 / Per 21 |
| Trade/Social | Charisma | Willpower | Cha 27 / Wil 21 |

**New player advice:** Don't remap until you know your focus. Train the "Magic 14" first.

## Attribute Implants

Implants occupy slots 1-5 and boost specific attributes:

| Implant Grade | Bonus | Approximate Cost |
|---------------|-------|------------------|
| Limited (+1) | +1 | ~3M ISK |
| Limited (+2) | +2 | ~10M ISK |
| Standard (+3) | +3 | ~25M ISK |
| Improved (+4) | +4 | ~80M ISK |
| Advanced (+5) | +5 | ~150M+ ISK |

### Implant Slot Mapping

| Slot | Attribute | Example +3 Implant |
|------|-----------|-------------------|
| 1 | Perception | Ocular Filter |
| 2 | Memory | Memory Augmentation |
| 3 | Willpower | Neural Boost |
| 4 | Intelligence | Cybernetic Subprocessor |
| 5 | Charisma | Social Adaptation Chip |

**Skill Required:** Cybernetics I (for +1/+2), up to Cybernetics V (for +5)

**Warning:** Implants are destroyed if your pod is killed.

## The "Magic 14" Core Skills

Train these before specializing (all use Int/Mem):

| Skill | Effect | Train To |
|-------|--------|----------|
| CPU Management | +5% CPU/level | V |
| Power Grid Management | +5% PG/level | V |
| Capacitor Management | +5% cap/level | IV |
| Capacitor Systems Operation | -5% cap recharge/level | IV |
| Mechanics | +5% structure HP/level | IV |
| Hull Upgrades | +5% armor HP/level | IV |
| Shield Management | +5% shield HP/level | IV |
| Shield Operation | -5% shield recharge/level | III |
| Navigation | +5% speed/level | IV |
| Evasive Maneuvering | +5% agility/level | III |
| Warp Drive Operation | -10% cap for warp/level | III |
| Spaceship Command | +2% agility/level | IV |
| Thermodynamics | Allows overheating | IV |
| Target Management | +1 target/level | IV |

## Skill Training by Career Path

### Mining Focus

| Skill Category | Primary Attr | Secondary Attr |
|----------------|--------------|----------------|
| Mining | Memory | Intelligence |
| Mining Upgrades | Memory | Intelligence |
| Reprocessing | Memory | Intelligence |
| Industry | Memory | Intelligence |

**Optimal remap:** Memory 27 / Intelligence 21

### Combat/Mission Focus

| Skill Category | Primary Attr | Secondary Attr |
|----------------|--------------|----------------|
| Spaceship Command | Perception | Willpower |
| Gunnery | Perception | Willpower |
| Drones | Memory | Perception |
| Armor/Shields | Intelligence | Memory |

**Optimal remap:** Perception 27 / Willpower 21 (accept slower drone training)

### Exploration Focus

| Skill Category | Primary Attr | Secondary Attr |
|----------------|--------------|----------------|
| Scanning | Intelligence | Memory |
| Hacking/Archaeology | Intelligence | Memory |
| Navigation | Intelligence | Perception |
| Cloaking | Intelligence | Memory |

**Optimal remap:** Intelligence 27 / Memory 21

## Training Queue Strategy

1. **Short skills first** during uncertain periods
2. **Long skills** before extended breaks
3. **Group by attribute** to maximize remap efficiency
4. **Use EVEMon** or similar planner for optimization

## Cerebral Accelerators

Temporary attribute boosters from events/store:

| Type | Bonus | Duration |
|------|-------|----------|
| Basic | +3 all | 24 hours |
| Standard | +6 all | 24 hours |
| Extended | +10 all | 14 days |
| Master | +12 all | 35 days |

**Stack with implants** for maximum training speed during events.

## Self-Sufficient Training Priority

For your operational profile:

### Phase 1: Foundation
1. Magic 14 to recommended levels
2. Drones V (unlocks T2 drones)
3. Mining Frigate III-IV

### Phase 2: Capability
1. Gallente Cruiser IV (better Vexor)
2. Mining Barge I-III
3. Scanning skills IV
4. Hacking/Archaeology IV

### Phase 3: Specialization
1. Heavy Assault Cruisers (Ishtar path) OR
2. Exhumers (Skiff/Mackinaw) OR
3. Covert Ops (Helios)

---
Source: EVE University Wiki
Last updated: YC128 (2026)
