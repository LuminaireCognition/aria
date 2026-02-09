# Damage Application Guide

Understanding how to make your weapons actually hit and deal full damage. Raw DPS means nothing if it doesn't apply to your target.

## The Core Problem

Your fitting tool says 500 DPS. But against that frigate, you're doing 50. Why?

**Damage application** is the gap between theoretical DPS and actual damage dealt. Different weapon systems have different application mechanics.

| Weapon Type | Application Limited By |
|-------------|------------------------|
| Turrets | Tracking speed, range |
| Missiles | Explosion radius, explosion velocity |
| Drones | Drone tracking, drone speed |
| Smartbombs | Range only (always hits in range) |

---

## Turret Mechanics

Turrets (lasers, hybrids, projectiles) must track targets and have optimal range.

### Range: Optimal and Falloff

Every turret has two range values:

| Range Type | Effect |
|------------|--------|
| **Optimal** | Full damage (100% hit chance for range) |
| **Falloff** | Damage decreases (-50% at optimal + falloff) |

**The Falloff Curve:**
```
Distance from target:

At optimal:           100% damage (range component)
At optimal + falloff: 50% damage
At optimal + 2×falloff: 6.25% damage
At optimal + 3×falloff: ~0% damage
```

### Range by Weapon Type

| Weapon | Optimal | Falloff | Style |
|--------|---------|---------|-------|
| Blasters | Very short | Short | Brawling |
| Pulse Lasers | Short | Medium | Brawling |
| Autocannons | Short | Long | Brawling/Skirmish |
| Railguns | Long | Short | Sniping |
| Beam Lasers | Long | Medium | Sniping |
| Artillery | Very long | Medium | Sniping/Alpha |

**Autocannon advantage:** Long falloff means graceful damage degradation at range.

**Railgun weakness:** Short falloff means damage drops sharply past optimal.

### Tracking Speed

Tracking determines if you can hit moving targets.

**The Problem:**
- Targets orbit you
- This creates **angular velocity** (how fast they cross your field of view)
- Your turrets must rotate to follow
- If they can't keep up, you miss

### The Tracking Formula

```
Hit Quality = Tracking Speed × Distance / (Angular Velocity × Target Signature)
```

Simplified:
```
Chance to Hit ∝ (Your Tracking × Target Sig) / (Angular Velocity)
```

**To hit better:**
- Higher tracking speed (your guns)
- Larger target signature (their ship)
- Lower angular velocity (they move slower relative to you)
- Greater distance (reduces angular velocity)

### Why Large Guns Miss Small Ships

| Factor | Large Turret | Small Turret |
|--------|--------------|--------------|
| Tracking | Very slow | Fast |
| Damage | High | Low |
| Optimal | Long | Short |

A battleship's large guns have terrible tracking. A frigate orbiting at 500m has extreme angular velocity. Result: 0% hits.

**Practical Example:**
```
Mega Pulse Laser II (Large)
- Tracking: 0.0275 rad/s

Frigate orbiting at 500m, 800 m/s:
- Angular velocity: ~1.6 rad/s

Tracking ratio: 0.0275 / 1.6 = 0.017 (1.7%)
Result: Almost never hits
```

### Improving Turret Application

| Method | Effect | Downside |
|--------|--------|----------|
| **Stasis Webifier** | Slows target (less angular velocity) | Mid slot, short range |
| **Target Painter** | Increases target sig | Mid slot |
| **Tracking Computer** | +Tracking or +Range | Mid slot |
| **Tracking Enhancer** | +Tracking, +Range | Low slot |
| **Get Closer** | Higher angular velocity | More danger |
| **Get Further** | Lower angular velocity | Less damage from falloff |
| **Smaller Guns** | Better tracking | Less raw DPS |

### Turret Size Guidelines

| Target Class | Effective Turret Size |
|--------------|----------------------|
| Frigates | Small |
| Destroyers | Small/Medium |
| Cruisers | Medium |
| Battlecruisers | Medium/Large |
| Battleships | Large |

**Rule:** Match gun size to target size, or use application mods.

---

## Missile Mechanics

Missiles always hit. But they don't always deal full damage.

### Explosion Radius and Velocity

Every missile has two application stats:

| Stat | What It Means |
|------|---------------|
| **Explosion Radius** | Size of the explosion |
| **Explosion Velocity** | Speed of the explosion |

These compare to the target's signature and speed.

### The Missile Damage Formula

```
Damage Modifier = MIN(1, Target Sig / Explosion Radius,
                       (Target Sig / Explosion Radius) × (Explosion Velocity / Target Speed))
```

Simplified:
- If target sig ≥ explosion radius AND target slow: Full damage
- If target sig < explosion radius: Reduced damage
- If target fast > explosion velocity: Reduced damage

### Missile Application Examples

**Heavy Missile vs Battleship:**
```
Heavy Missile: 140m explosion radius, 81 m/s velocity
Battleship: 400m sig, 100 m/s speed

Sig ratio: 400/140 = 2.86 (capped at 1) → Full damage
Speed ratio: Not needed (sig already full)
Result: 100% damage
```

**Heavy Missile vs Frigate:**
```
Heavy Missile: 140m explosion radius, 81 m/s velocity
Frigate: 35m sig, 400 m/s speed

Sig ratio: 35/140 = 0.25
Speed check: 35/140 × 81/400 = 0.05

Result: 5% damage (ouch)
```

### Missile Types and Application

| Missile Type | Explosion Radius | Explosion Velocity | Best Against |
|--------------|------------------|-------------------|--------------|
| Rockets | 20m | 150 m/s | Frigates |
| Light Missiles | 40m | 170 m/s | Frigates/Destroyers |
| Heavy Assault Missiles | 125m | 101 m/s | Cruisers |
| Heavy Missiles | 140m | 81 m/s | Cruisers/BCs |
| Cruise Missiles | 330m | 69 m/s | Battleships |
| Torpedoes | 450m | 56 m/s | Battleships/Caps |

**Notice:** Larger missiles have worse application stats. Torpedoes barely scratch frigates.

### Improving Missile Application

| Method | Effect | Downside |
|--------|--------|----------|
| **Target Painter** | Increases target sig | Mid slot |
| **Stasis Webifier** | Slows target | Mid slot, short range |
| **Rigor Rig** | -Explosion radius | Rig slot, calibration |
| **Flare Rig** | +Explosion velocity | Rig slot, calibration |
| **Missile Guidance Computer** | +Application or +Range | Mid slot |
| **Missile Guidance Enhancer** | +Application | Low slot |
| **Smaller Missiles** | Better application | Less raw DPS |

### Precision vs Fury Ammo

T2 launchers unlock special ammo:

| Ammo Type | Damage | Application | Best For |
|-----------|--------|-------------|----------|
| Faction | Normal | Normal | General use |
| **Precision/Javelin** | -15% | Much better | Small targets |
| **Fury/Rage** | +20% | Much worse | Large targets |

**Use Precision** against targets smaller than your missile's intended class.

---

## Drone Mechanics

Drones are autonomous weapons with their own tracking and speed.

### Drone Stats That Matter

| Stat | Effect |
|------|--------|
| **Tracking** | Like turret tracking |
| **Optimal/Falloff** | Like turret range |
| **Speed** | Pursuit speed (not damage) |
| **Orbit Velocity** | How fast they orbit target |

### Drone Application

Drones use turret-like mechanics:
- They orbit the target
- They shoot with tracking-based weapons
- Small drones track better than large drones

### Drone Size Guidelines

| Drone Size | Bandwidth | Best Against |
|------------|-----------|--------------|
| Light (Hobgoblin, etc.) | 5 Mbit | Frigates |
| Medium (Hammerhead, etc.) | 10 Mbit | Cruisers |
| Heavy (Ogre, etc.) | 25 Mbit | Battleships |
| Sentry (Garde, etc.) | 25 Mbit | Stationary targets |

### Why Light Drones Hit Frigates

Light drones:
- Orbit at 500-1000m from target
- Move fast (up to 3000+ m/s with MWD)
- Have good tracking
- Small explosion radius equivalent

Result: They keep up with frigates and track well.

### Heavy Drones vs Frigates

Heavy drones:
- Slower (can't catch fast frigates)
- Worse tracking
- Large guns

Result: They struggle to hit frigates that actively evade.

### Sentry Drones

Sentries don't move. They're stationary turrets.

| Sentry | Range | Tracking | Damage |
|--------|-------|----------|--------|
| Garde | Short | Good | High |
| Curator | Short | Medium | High |
| Bouncer | Long | Poor | Medium |
| Warden | Long | Medium | Medium |

**Sentries can't reposition.** If targets close range, your long-range sentries suffer.

### Drone Damage Modules

| Module | Effect | Slot |
|--------|--------|------|
| Drone Damage Amplifier | +Damage | Low |
| Omnidirectional Tracking Link | +Tracking, +Range | Mid |
| Drone Navigation Computer | +Drone speed | Mid |

**Drone Navigation Computer** helps drones reach targets faster and orbit better.

---

## Weapon Comparison

Choosing the right weapon system for your targets.

### Application Comparison

| Weapon | vs Frigates | vs Cruisers | vs Battleships |
|--------|-------------|-------------|----------------|
| Small Turrets | Excellent | Good | Poor (low DPS) |
| Medium Turrets | Poor | Excellent | Good |
| Large Turrets | Terrible | Poor | Excellent |
| Light Missiles | Good | Moderate | Poor |
| Heavy Missiles | Poor | Good | Good |
| Cruise/Torps | Terrible | Poor | Excellent |
| Light Drones | Excellent | Moderate | Poor |
| Medium Drones | Moderate | Excellent | Good |
| Heavy Drones | Poor | Good | Excellent |

### The Application Problem for Battleships

Battleships face a dilemma:
- Large guns/missiles for DPS
- But large weapons don't apply to small targets
- Frigates can kill you while you miss

**Solutions:**
1. **Carry light drones** - Most battleships have drone bay
2. **Fit application mods** - Webs, painters
3. **Use rapid launchers** - Rapid Heavy Missile Launcher uses light missiles
4. **Fleet support** - Let tackle handle frigates

---

## Application Modules Reference

### Stasis Webifier

| Property | Value |
|----------|-------|
| **Effect** | -50% to -60% target speed |
| **Range** | 10km (T2) |
| **Slot** | Mid |
| **Stacking** | Yes, but diminishing |

**Best application mod.** Slowing target helps both turrets AND missiles.

### Target Painter

| Property | Value |
|----------|-------|
| **Effect** | +22.5% to +30% target sig |
| **Range** | 60-100km |
| **Slot** | Mid |
| **Stacking** | Yes, but diminishing |

**Long range application.** Increases target signature for better missile and turret application.

### Tracking Computer

| Property | Value |
|----------|-------|
| **Effect** | +10-30% tracking OR +10-30% range |
| **Range** | Self |
| **Slot** | Mid |
| **Scripts** | Tracking or Range |

**Flexible.** Switch scripts based on engagement.

### Tracking Enhancer

| Property | Value |
|----------|-------|
| **Effect** | +7.5% tracking, +7.5% range |
| **Slot** | Low |
| **Stacking** | Yes |

**Passive bonus.** No scripts, always active.

### Missile Guidance Computer

| Property | Value |
|----------|-------|
| **Effect** | +10-25% application OR +10-25% range |
| **Slot** | Mid |
| **Scripts** | Precision or Range |

**Precision script** improves explosion radius and velocity.

### Missile Guidance Enhancer

| Property | Value |
|----------|-------|
| **Effect** | +7.5% explosion radius, +7.5% explosion velocity |
| **Slot** | Low |
| **Stacking** | Yes |

**Passive missile application.**

---

## Damage Types

Different weapon systems deal different damage types.

### Damage Type Flexibility

| Weapon | Damage Types | Flexibility |
|--------|--------------|-------------|
| Lasers | EM/Thermal only | None (swap crystals for range) |
| Hybrids | Kinetic/Thermal only | None |
| Projectiles | All four | High (swap ammo) |
| Missiles | All four | High (swap ammo) |
| Drones | Varies by drone | High (swap drones) |

### Matching Damage to Target

Always deal damage the target is weakest against:

| Target Faction | Weak To | Deal |
|----------------|---------|------|
| Serpentis | Kinetic > Thermal | Kinetic |
| Guristas | Kinetic > Thermal | Kinetic |
| Blood Raiders | EM > Thermal | EM |
| Sansha | EM > Thermal | EM |
| Angel Cartel | Explosive > Kinetic | Explosive |
| Rogue Drones | EM > Thermal | EM |

See `npc_damage_types.md` for complete reference.

---

## Common Application Mistakes

| Mistake | Why It's Bad | Solution |
|---------|--------------|----------|
| Large guns vs frigates | 0% hits | Carry light drones, fit web |
| Torpedoes vs cruisers | Minimal damage | Use HAMs or HMLs |
| No web on brawler | Targets orbit too fast | Always fit web for brawling |
| Heavy drones only | Can't kill tackle | Carry light drones too |
| Wrong ammo type | 50% damage wasted | Match ammo to resist hole |
| Max range sniping | Falloff kills damage | Stay within optimal |
| Ignoring tracking | Wonder why missing | Check turret tracking stats |

---

## Practical Fitting Guidelines

### For Frigate Pilots

- Your targets are often frigates too
- Small weapons apply well to each other
- Use webs to hold targets in place
- Speed tank means you're also hard to hit

### For Cruiser Pilots

- Medium weapons apply well to cruisers
- Struggle against frigates (bring light drones)
- Good against battleships (can hit, just lower DPS)
- Web is essential for catching frigates

### For Battleship Pilots

- Large weapons demolish other battleships
- Terrible against frigates (MUST have solution)
- Rapid launchers trade DPS for frigate application
- Light drones are mandatory
- Webs critical if you expect to be tackled

---

## Summary

| Concept | Key Point |
|---------|-----------|
| Turret tracking | Must match angular velocity of target |
| Turret range | Optimal = full, falloff = degraded |
| Missile explosion | Radius vs sig, velocity vs speed |
| Larger weapons | More DPS, worse application |
| Webifier | Best application mod (slows target) |
| Target painter | Increases sig (helps missiles + turrets) |
| Match weapon to target | Gun/missile size should match hull size |
| Damage types | Always hit resist holes |
| Light drones | Solution for anti-frigate |

---
Source: EVE game mechanics, EVE University Wiki
Last updated: YC128 (2026)
