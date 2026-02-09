# Speed and Signature Guide

Understanding how speed and signature radius affect your survivability. These mechanics determine how much damage you take and how easily you can escape.

## Core Concepts

Two ship attributes fundamentally affect incoming damage:

| Attribute | What It Is | Effect on Damage |
|-----------|------------|------------------|
| **Signature Radius** | How "big" your ship appears to weapons | Larger = easier to hit, more damage |
| **Velocity** | How fast you're moving | Faster = harder to track, less damage |

Weapons systems use these values to calculate whether they hit and for how much damage.

---

## Signature Radius Explained

Signature radius (sig) represents your ship's targeting profile - how large it appears to enemy weapons and sensors.

### Base Signature by Ship Class

| Ship Class | Typical Signature | Relative Size |
|------------|-------------------|---------------|
| Capsule | 25m | Tiny |
| Frigate | 30-40m | Small |
| Destroyer | 50-80m | Small-Medium |
| Cruiser | 100-150m | Medium |
| Battlecruiser | 200-300m | Large |
| Battleship | 350-450m | Very Large |
| Capital | 2000-15000m | Massive |

### Why Signature Matters

**For Turrets:**
- Tracking calculation uses your sig relative to turret tracking
- Larger sig = turret tracks you more easily = more hits, more damage

**For Missiles:**
- Damage formula compares your sig to missile explosion radius
- If your sig < explosion radius, damage is reduced
- Larger sig = closer to full missile damage

**For Targeting:**
- Larger sig = faster to lock
- Smaller sig = harder to lock quickly

### Signature Bloom

Certain modules temporarily increase your signature:

| Module | Sig Increase | Duration |
|--------|--------------|----------|
| **Microwarpdrive (MWD)** | +500% (5x larger) | While active |
| Shield Extender | +10-15% | Permanent (passive) |
| Target Spectrum Breaker | +100% | While active |

**The MWD Signature Problem:**

A frigate with 35m signature activates MWD:
- Normal sig: 35m
- With MWD: 35m × 5 = **175m** (cruiser-sized!)

This means:
- Missiles that would barely scratch you now deal full damage
- Turrets that couldn't track you now hit easily
- You become much easier to lock

---

## Speed and Damage Mitigation

Moving fast reduces incoming damage from turrets (not missiles).

### How Speed Helps Against Turrets

Turrets must **track** targets. Tracking depends on:
- **Angular velocity** - how fast you move across the turret's field of view
- **Distance** - closer targets have higher angular velocity

The formula simplified:
```
Hit Chance ∝ (Turret Tracking × Distance) / (Angular Velocity × Target Sig)
```

**Faster movement = higher angular velocity = harder to hit**

### Practical Example

A frigate orbiting a battleship at 500m with AB:
- High angular velocity (you're orbiting fast)
- Close range (high relative motion)
- Small signature
- Result: Battleship large turrets can't track you

Same frigate at 50km:
- Low angular velocity (barely moving relative to turret)
- Result: Battleship turrets hit consistently

### Speed vs Missiles

**Speed does not help against missiles the same way.**

Missiles use explosion velocity to calculate damage:
```
If Target Speed > Explosion Velocity:
    Damage reduced proportionally
```

Most missiles have high explosion velocity. Frigates can sometimes outrun them, but cruisers and larger cannot.

| Missile Type | Explosion Velocity | Can Outrun? |
|--------------|-------------------|-------------|
| Light Missiles | 170-220 m/s | Frigates maybe |
| Heavy Missiles | 81-105 m/s | Very fast frigs |
| Cruise Missiles | 69-94 m/s | Almost nothing |
| Torpedoes | 56-69 m/s | Nothing |

**Against missiles, signature matters more than speed.**

---

## Afterburner vs Microwarpdrive

The core propulsion decision for any fit.

### Comparison Table

| Aspect | Afterburner (AB) | Microwarpdrive (MWD) |
|--------|------------------|----------------------|
| Speed Bonus | +125-200% | +500% |
| Signature Bloom | None | +500% |
| Capacitor Use | Low | Very High |
| Can be Shut Off | No | Yes (by scram) |
| Fitting | Light | Heavy |

### When to Use Afterburner

**PvE Missions/Ratting:**
- NPCs deal consistent damage
- No need to escape quickly
- Sig bloom would increase incoming damage
- Cap stability matters for sustained fights

**Brawling PvP:**
- You're already close, speed less critical
- Sig bloom hurts in close fights
- Can't be turned off by warp scrambler

**Armor Tanked Ships:**
- Already slow, MWD speed less impactful
- Cap is often tight
- Sustained survivability > burst speed

**Small Ships in PvE:**
- Your small sig is your tank
- MWD destroys that advantage

### When to Use Microwarpdrive

**Kiting PvP:**
- Need to control range
- Stay outside enemy optimal
- Speed is the defense

**Tackling:**
- Must catch targets
- Close gaps quickly
- Sig doesn't matter if you have enough tank

**Exploration:**
- Need to burn between cans
- Escape if caught
- Not taking sustained damage

**Fleet PvP:**
- Anchoring and maneuvering
- Sig doesn't matter as much in large fights
- Speed for positioning

### The Scram Problem

**Warp Scramblers shut off MWDs.**

If you're scrambled:
- MWD stops working
- You're slow AND have no sig benefit
- AB keeps working

This is why brawlers often prefer AB - it works even when tackled.

---

## Speed Tanking

Using speed and signature to avoid damage entirely.

### The Principle

If you move fast enough and stay small enough, large weapons cannot effectively hit you.

**Speed Tank Formula:**
```
Effective Tank = (Base HP) / (Damage Actually Hitting You)
```

If only 20% of enemy damage hits, you effectively have 5x your HP.

### Speed Tank Requirements

| Requirement | Why |
|-------------|-----|
| Small signature | Base for damage reduction |
| High speed | Increases angular velocity |
| Close orbit | Maximizes angular velocity |
| Correct target | Must fight things that can't track you |

### What Speed Tanks Well

| Ship | Speed Tank Viability | Notes |
|------|---------------------|-------|
| Interceptors | Excellent | Built for this |
| Assault Frigates | Good | Tankier version |
| Frigates | Good | Natural small sig |
| Destroyers | Moderate | Larger sig hurts |
| Cruisers | Poor | Too big |
| Larger | No | Don't try |

### What You Can Speed Tank

You can speed tank enemies with:
- Large turrets (battleship guns, large artillery)
- Slow tracking
- No webs or target painters

You **cannot** speed tank:
- Missiles (they don't care about speed much)
- Drones (they orbit and track well)
- Small turrets (designed to track you)
- Anything with webs (you'll be slowed)
- Smartbombs (instant, no tracking)

### Orbit Range for Speed Tanking

Closer = higher angular velocity = harder to hit

| Orbit Distance | Angular Velocity | Tracking Difficulty |
|----------------|------------------|---------------------|
| 500m | Very High | Very Hard to Hit |
| 2.5km | High | Hard to Hit |
| 7.5km | Moderate | Moderate |
| 15km+ | Low | Easy to Hit |

But beware:
- Too close = you might bump and stop
- Some NPCs have smart bombs
- Some NPCs web at close range

**Recommended PvE orbit: 2,500-7,500m** for most frigates.

---

## Align Time and Mass

How mass affects your ability to enter warp.

### Align Time Explained

**Align time** = how long to reach 75% max velocity in a direction

You cannot warp until:
1. Aligned to destination (facing within 5 degrees)
2. Traveling at 75%+ max velocity

### Align Time Formula

```
Align Time = ln(2) × Mass / Agility
            ≈ 0.693 × Mass / Agility
```

**Lower mass = faster align**
**Higher agility = faster align**

### Typical Align Times

| Ship Class | Typical Align | "Good" Align |
|------------|---------------|--------------|
| Capsule | 2.1s | - |
| Shuttle | 2.3s | - |
| Frigate | 3-5s | <3s (instawarp) |
| Destroyer | 4-6s | <4s |
| Cruiser | 7-10s | <6s |
| Battlecruiser | 10-14s | <10s |
| Battleship | 12-18s | <12s |

### Instawarp (Sub-2s Align)

If your align time is under 2 seconds, you warp before server ticks can catch you.

**Why 2 seconds?**
- Server updates every 1 second
- If you align in <2s, you're in warp before being locked
- Makes you effectively uncatchable on gates

**How to achieve:**
- Inertial Stabilizers (lower agility number = better)
- Nanofiber Internal Structures (lower mass + agility)
- Hyperspatial rigs
- Low Friction Nozzle Joints rigs

### Mass and MWD

**MWD adds mass while active:**
- 10MN MWD adds significant mass
- This increases align time while MWD is on
- You align faster with MWD OFF

**MWD Trick:**
1. Align to destination
2. Pulse MWD for one cycle
3. Turn MWD off
4. You reach 75% speed faster from the boost
5. Enter warp sooner than with sustained MWD

This is called the **"MWD cloak trick"** when combined with cloaking.

---

## Practical Applications

### Frigate PvE (Missions, Anoms)

**Recommended: Afterburner**

Why:
- Your small sig is your primary defense
- MWD makes you cruiser-sized
- NPCs will shred you with MWD sig bloom
- Orbit at 2,500-7,500m with AB

### Cruiser PvE

**Recommended: Afterburner or MWD (depends on fit)**

Active tank cruiser:
- AB for cap stability
- Sig bloom matters less at cruiser size
- But still hurts against larger NPCs

Kiting cruiser:
- MWD to maintain range
- Your tank is range, not sig

### Exploration

**Recommended: MWD**

Why:
- Need to burn between cans quickly
- Not in sustained combat
- Escape from camps requires speed
- Switch to AB for sites with rats

### Hauling/Travel

**Recommended: MWD (or none)**

Why:
- Align time matters most
- MWD pulse helps reach warp speed
- Not fighting, so sig doesn't matter
- Consider inertial stabilizers

### PvP Brawling

**Recommended: Afterburner**

Why:
- Works even when scrambled
- Lower sig in close fights helps
- Cap stability in extended fights

### PvP Kiting

**Recommended: MWD**

Why:
- Must control range
- Speed is your defense
- If you're caught, you're probably dead anyway

---

## Module Reference

### Afterburners

| Size | Fitting | Speed Bonus | Cap/Cycle |
|------|---------|-------------|-----------|
| 1MN | Low | +125% | Low |
| 10MN | Medium | +135% | Medium |
| 100MN | High | +150% | High |

Variants:
- **Compact**: Lower fitting (usually best)
- **Enduring**: Lower cap use
- **T2**: Best stats, higher fitting

### Microwarpdrives

| Size | Fitting | Speed Bonus | Sig Bloom | Cap/Cycle |
|------|---------|-------------|-----------|-----------|
| 5MN | Medium | +500% | +500% | High |
| 50MN | High | +500% | +500% | Very High |
| 500MN | Very High | +500% | +500% | Extreme |

Variants:
- **Compact**: Lower fitting (usually best)
- **Enduring**: Lower cap use (good for active tanks)
- **Restrained**: Lower sig bloom (+450% instead of +500%)
- **T2**: Best stats, highest fitting

### Agility Modules

| Module | Effect | Slot | Drawback |
|--------|--------|------|----------|
| Inertial Stabilizers | Better agility | Low | -% signature |
| Nanofiber Internal | Agility + speed | Low | -% structure HP |
| Overdrive Injector | +Speed | Low | -% cargo |
| Polycarbon Rigs | Agility | Rig | -% armor HP |

---

## Summary

| Concept | Key Point |
|---------|-----------|
| Signature | Larger = more damage taken |
| Speed | Faster = harder to track (turrets only) |
| MWD | +500% speed, but +500% signature |
| AB | Lower speed bonus, no sig penalty |
| Speed tank | Works for small ships vs large turrets |
| Align time | Mass / Agility, lower = faster warp |
| PvE general | Use AB to keep sig low |
| PvP kiting | Use MWD for range control |
| PvP brawling | Use AB (works when scrambled) |

---
Source: EVE game mechanics, EVE University Wiki
Last updated: YC128 (2026)
