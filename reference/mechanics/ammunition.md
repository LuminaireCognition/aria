# Ammunition Reference

Master reference for EVE Online ammunition selection by weapon system.

**Source:** [EVE University Wiki - Ammunition](https://wiki.eveuniversity.org/Ammunition)

> **Note:** For programmatic lookups, see the structured JSON reference files:
> - `reference/mechanics/missiles.json` - Missile ammo by damage type and faction
> - `reference/mechanics/projectile_turrets.json` - Projectile ammo by damage type and faction
> - `reference/mechanics/laser_turrets.json` - Laser crystals and faction effectiveness
> - `reference/mechanics/hybrid_turrets.json` - Hybrid charges and faction effectiveness
> - `reference/mechanics/drones.json` - Drone damage types and faction recommendations

## Ammo Selection by Enemy Faction

Quick reference for matching damage type to enemy weakness. For complete faction damage profiles, see `reference/mechanics/npc_damage_types.md`.

### Missiles

All missile types (rockets, light, heavy assault, heavy, cruise, torpedoes) share the same damage type naming:

| Ammo Name | Damage Type | Best Against |
|-----------|-------------|--------------|
| **Scourge** | Kinetic | Guristas, Serpentis, Caldari Navy |
| **Mjolnir** | EM | Blood Raiders, Sansha, Rogue Drones |
| **Nova** | Explosive | Angel Cartel, Minmatar Navy |
| **Inferno** | Thermal | Serpentis (secondary), Mercenaries |

**Default recommendation:** Scourge (Kinetic) - effective against most common PvE factions.

### Projectiles (Autocannons & Artillery)

Projectile ammo deals mixed damage types. Primary damage listed first.

#### Short Range (-50% optimal, highest damage)

| Ammo Name | Primary | Secondary | Best Against |
|-----------|---------|-----------|--------------|
| **EMP** | EM | Kinetic/Exp | Blood Raiders, Sansha |
| **Fusion** | Explosive | Kinetic | Angel Cartel |
| **Phased Plasma** | Thermal | Kinetic | Serpentis |

#### Medium Range (standard optimal, +20% tracking)

| Ammo Name | Primary | Secondary | Best Against |
|-----------|---------|-----------|--------------|
| **Titanium Sabot** | Kinetic | Explosive | Guristas |
| **Depleted Uranium** | Mixed | All types | General purpose |

#### Long Range (+60% optimal, lowest damage)

| Ammo Name | Primary | Secondary | Best Against |
|-----------|---------|-----------|--------------|
| **Carbonized Lead** | Kinetic | Explosive | Guristas (at range) |
| **Nuclear** | Explosive | Kinetic | Angel Cartel (at range) |
| **Proton** | EM | Kinetic | Blood Raiders (at range) |

**Range note:** Short-range ammo (EMP, Fusion, Phased Plasma) deals 50% more damage (150% modifier) but has -50% optimal. Long-range ammo (Proton, Nuclear, Carbonized Lead) has +60% optimal but only 62.5% damage. Medium-range ammo (Titanium Sabot, Depleted Uranium) has standard damage with +20% tracking bonus.

**Default recommendation:** Titanium Sabot - good balance of range, tracking, and kinetic damage.

### Hybrids (Blasters & Railguns)

Hybrid turrets deal **Kinetic/Thermal only** - no damage type selection via ammo. Ammo choice affects damage and range.

| Ammo Name | Damage | Range | Usage |
|-----------|--------|-------|-------|
| **Antimatter** | Highest | Shortest | Close brawling |
| **Void** (T2) | Very High | Short | Maximum DPS |
| **Null** (T2) | Lower | Very Long | Kiting |
| **Thorium** | Medium | Medium | General purpose |
| **Lead** | Medium | Long | Ranged combat |
| **Spike** (T2 Rail) | Lower | Extreme | Sniping |

**Faction limitation:** Hybrids cannot exploit EM or Explosive weaknesses. They work best against:
- Serpentis (Thermal weakness)
- Guristas (Kinetic weakness)
- Caldari/Gallente Navy (Kinetic/Thermal weakness)

**Default recommendation:** Antimatter for brawling, Lead for range.

### Lasers (Pulse & Beam)

Laser turrets deal **EM/Thermal only** - no damage type selection. Crystal choice affects damage and range.

| Crystal | Damage | Range | Usage |
|---------|--------|-------|-------|
| **Multifrequency** | Highest | Shortest | Close combat |
| **Conflagration** (T2) | Very High | Short | Maximum DPS |
| **Scorch** (T2) | Lower | Very Long | Kiting |
| **Standard** | Medium | Medium | General purpose |
| **Radio** | Lowest | Longest | Extreme sniping |

**T1 vs T2 Crystals:**
- T1 crystals never deplete - use indefinitely
- T2 crystals (Conflagration, Scorch, Aurora, Gleam) deplete after ~1000-3000 shots

**Faction limitation:** Lasers cannot exploit Kinetic or Explosive weaknesses. They excel against:
- Blood Raiders (EM weakness)
- Sansha's Nation (EM weakness)
- Rogue Drones (EM weakness)
- Amarr Navy (EM weakness)

**Default recommendation:** Multifrequency for damage, Standard for versatility.

---

## Faction-to-Ammo Quick Reference

Complete mapping of enemy faction to optimal ammunition for each weapon system:

| Enemy Faction | Weakness | Missile | Projectile | Hybrid | Laser | Drone |
|---------------|----------|---------|------------|--------|-------|-------|
| **Serpentis** | Therm > Kin | Inferno | Phased Plasma | Antimatter | Multifreq | Hammerhead |
| **Guristas** | Kin > Therm | Scourge | Titanium Sabot | Antimatter | Multifreq | Vespa |
| **Blood Raiders** | EM > Therm | Mjolnir | EMP | Antimatter | Multifreq | Infiltrator |
| **Sansha's Nation** | EM > Therm | Mjolnir | EMP | Antimatter | Multifreq | Infiltrator |
| **Angel Cartel** | Exp > Kin | Nova | Fusion | - | - | Valkyrie |
| **Rogue Drones** | EM > Therm | Mjolnir | EMP | Antimatter | Multifreq | Acolyte |
| **Mercenaries** | Therm > Kin | Inferno | Phased Plasma | Antimatter | Multifreq | Hammerhead |
| **Mordu's Legion** | Kin > EM | Scourge | Titanium Sabot | Antimatter | Multifreq | Hornet |

**Note:** Hybrids and Lasers marked with "-" indicate the weapon system cannot deal the optimal damage type. Use Antimatter/Multifrequency for thermal component, but consider drones or missiles for better damage matching.

> **Reference:** See `reference/mechanics/drones.md` for drone selection by faction.

---

## Ammo Quantity Guidelines

How much ammo to carry for different activities:

| Activity | Missiles | Projectiles | Notes |
|----------|----------|-------------|-------|
| L1-L2 Missions | 500 primary | 1000 primary | Single mission |
| L3 Missions | 1000 primary, 500 backup | 2000 primary, 1000 backup | Extended sessions |
| L4 Missions | 2000 primary, 1000 each backup | 3000 primary, 1500 each backup | Multi-hour sessions |
| Exploration | 500 of each type | 1000 of each type | Unknown encounters |

**Lasers:** T1 crystals don't deplete. Carry one set of each type.

**Hybrids:** Carry 3000+ rounds for extended missions. Ammo consumption is higher than missiles.

---

## T2 Ammo Overview

T2 launchers and turrets unlock specialized ammunition:

### Missiles

| Type | Name | Effect | Best For |
|------|------|--------|----------|
| Short Range | Rage (Rockets/Torps) | +20% damage, worse application | Large targets |
| Long Range | Javelin (Rockets/Torps) | +15% range, slightly worse damage | Kiting |
| Precision | Precision (Light/Heavy/Cruise) | -15% damage, better application | Small targets |
| Fury | Fury (Light/Heavy/Cruise) | +20% damage, worse application | Large targets |

### Turrets

| Weapon | Close Range T2 | Long Range T2 | Notes |
|--------|----------------|---------------|-------|
| Blasters | Void | Null | Void for DPS, Null for kiting |
| Railguns | Javelin | Spike | Spike for extreme range sniping |
| Autocannons | Hail | Barrage | Hail for brawling, Barrage for falloff |
| Artillery | Quake | Tremor | Quake for alpha, Tremor for range |
| Pulse Lasers | Conflagration | Scorch | Scorch is exceptional for kiting |
| Beam Lasers | Gleam | Aurora | Aurora for sniping |

---

## Weapon System Damage Flexibility

| Weapon System | Damage Types Available | Flexibility |
|---------------|------------------------|-------------|
| Missiles | EM, Thermal, Kinetic, Explosive | Full selection |
| Projectiles | EM, Thermal, Kinetic, Explosive | Full selection (mixed per ammo) |
| Hybrids | Kinetic, Thermal only | Limited |
| Lasers | EM, Thermal only | Limited |
| Drones | All (swap drones) | Full selection |

**Recommendation:** For maximum flexibility, missiles and projectiles allow targeting any resist hole. Hybrid and laser pilots should rely on drones for damage types their weapons cannot deal.

---

*Last verified: 2026-01-18 from EVE University Wiki*
