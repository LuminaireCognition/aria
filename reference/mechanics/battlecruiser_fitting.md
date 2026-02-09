# Battlecruiser Fitting Philosophy

A guide to understanding, fitting, and flying battlecruisers for Level 3 missions.

## What Makes Battlecruisers Different

Battlecruisers bridge the gap between cruisers and battleships:

| Aspect | Cruiser | Battlecruiser | Battleship |
|--------|---------|---------------|------------|
| Signature | ~150m | ~270m | ~400m |
| Tank | Light | Medium-Heavy | Heavy |
| DPS | 200-300 | 350-500 | 500-800+ |
| Speed | Fast | Medium | Slow |
| Warp Speed | Fast | Medium | Slow |
| Cost | 10-20M | 40-80M | 150-300M |

**Key Insight:** Battlecruisers hit harder than cruisers but aren't as sluggish as battleships. They're the "sweet spot" for L3 content - enough firepower to kill quickly, enough tank to survive comfortably.

## The Four L3 Battlecruisers

| Ship | Faction | Weapons | Tank | Style |
|------|---------|---------|------|-------|
| **Myrmidon** | Gallente | Drones | Armor Active | Set drones, orbit, repair |
| **Drake** | Caldari | Heavy Missiles | Shield Passive | Lock, fire, survive everything |
| **Hurricane** | Minmatar | Projectiles | Shield Buffer | Alpha strike, reposition |
| **Harbinger** | Amarr | Lasers | Armor Active | Range control, cap management |

## Core Fitting Principles

### 1. Tank to the Ship's Strength

Each faction's battlecruiser has specific tank bonuses:

| Ship | Tank Bonus | Use |
|------|-----------|-----|
| Myrmidon | +7.5% armor repair/level | Active armor |
| Drake | +4% shield resist/level | Passive shield |
| Hurricane | +7.5% shield boost/level | Buffer or active shield |
| Harbinger | +7.5% armor resist/level | Active armor |

**Rule:** Fit the tank type your ship has bonuses for. A shield-tanked Harbinger wastes its armor bonus.

### 2. Weapon Slots Are Sacred

Never sacrifice weapon slots for utility except in extreme circumstances:
- 6 turrets/launchers is standard for BCs
- DPS is how you complete missions faster
- An empty high slot is acceptable; an empty weapon slot is not

### 3. Support Your Weapons

Each weapon system has specific needs:

| Weapon | Needs | Support Modules |
|--------|-------|-----------------|
| Drones | Travel time, tracking | Drone Nav Computer, Tracking Link |
| Missiles | None (fire and forget) | - |
| Projectiles | Tracking, falloff | Tracking Enhancer, Tracking Computer |
| Lasers | Capacitor, tracking | Cap Recharger, Tracking Computer |

### 4. Capacitor Stability Isn't Always Required

**Myth:** "Your fit must be cap stable."

**Reality:**
- Passive tanks (Drake) don't need cap stability
- Active tanks need to run for the mission duration (10-20 minutes)
- Weapons vary: missiles/projectiles don't care, lasers care a lot

**Rule of Thumb:**
- If your tank is active: aim for stable or 10+ minutes
- If your tank is passive: cap stability is a bonus, not a requirement

### 5. Speed vs. Signature Trade-offs

| Propulsion | Speed Bonus | Signature Penalty |
|------------|-------------|-------------------|
| Afterburner | +135% | None |
| Microwarpdrive | +500% | +500% |

**For L3 PvE:**
- **AB is usually better** - no sig bloom means less incoming damage
- **MWD is fine** if you need to reposition quickly (Hurricane)
- **No prop mod** is acceptable on passive tanks (Drake)

## Fitting Order of Priority

When building a fit, prioritize in this order:

1. **Weapons** - Your primary damage source
2. **Tank** - Enough to survive the mission
3. **Capacitor** - Enough to run your tank and weapons
4. **Damage Mods** - Increase DPS (gyros, BCUs, DDAs, heat sinks)
5. **Utility** - Tracking computers, drone mods, prop mods
6. **Rigs** - Enhance your weakest area

## Common Fitting Mistakes

### Over-Tanking

**Mistake:** Fitting 3 large shield extenders and 2 invulns on a Drake.

**Why It's Wrong:** L3 missions don't require that much tank. You're sacrificing DPS or utility for tank you don't need.

**Rule:** Tank enough to survive comfortably, then focus on killing faster.

### Under-Tanking

**Mistake:** Fitting all damage mods, no tank, assuming you'll "just kill them faster."

**Why It's Wrong:** L3 missions have enough incoming DPS to overwhelm a paper-thin tank.

**Rule:** You can't deal DPS if you're dead.

### Wrong Damage Type

**Mistake:** Always using thermal drones against all factions.

**Why It's Suboptimal:** Matching damage to enemy weakness increases effective DPS by 20-30%.

**Rule:** Check enemy weaknesses, swap ammo/drones accordingly.

### Ignoring Frigate Defense

**Mistake:** Fitting only large weapons and wondering why frigates take forever to kill.

**Why It's Wrong:** Heavy missiles and large turrets apply damage poorly to small fast targets.

**Solution:**
- Carry light drones for frigate cleanup
- Use tracking computers with tracking scripts
- Consider weapon swaps for frigate-heavy missions

## Ammo/Drone Selection by Faction

Match your damage type to enemy weakness for optimal damage.

> **Reference:** See `reference/mechanics/ammunition.md` for complete ammo selection by weapon system and enemy faction.
>
> **Reference:** See `reference/mechanics/drones.md` for complete drone damage types and size recommendations.

**Note:** Lasers deal EM/Thermal only - they work well against Blood Raiders, Sansha, Rogue Drones, and acceptably against Serpentis. Hybrids deal Kinetic/Thermal only.

## Tank Adjustment Philosophy

Base fits use **omni-tank** (balanced resists against all damage types). For specific missions:

### When to Specialize Tank

Specialize when:
- You run the same mission type repeatedly
- You know the enemy faction in advance
- The mission has exceptionally high DPS

### How to Specialize

Swap one omni-resist module for a specific hardener:

| Enemy Deals | Swap This | For This |
|-------------|-----------|----------|
| Thermal heavy | EANM/Adaptive Invuln | Thermal Hardener |
| EM heavy | EANM/EM Amp | EM Hardener |
| Kinetic heavy | EANM/Adaptive Invuln | Kinetic Hardener |
| Explosive heavy | EANM/Adaptive Invuln | Explosive Hardener |

**Keep:** Always keep at least one omni-resist module - missions often have mixed spawns.

## Engagement Range by Ship

Each battlecruiser has an optimal engagement envelope:

| Ship | Optimal Range | Why |
|------|---------------|-----|
| Myrmidon | 20-40 km | Drone travel time, keep some distance for tank breathing room |
| Drake | 40-60 km | Heavy missiles apply well at range, passive tank doesn't care |
| Hurricane | 25-40 km (arty) / 5-15 km (AC) | Depends on weapon choice |
| Harbinger | 20-35 km | Crystal swap lets you adjust, beam tracking is decent |

## Skills That Matter for All Battlecruisers

### Universal

| Skill | Effect | Priority |
|-------|--------|----------|
| Spaceship Command | +2% agility/level | III |
| Battlecruisers | Enables BC flying | I (required) |
| [Faction] Battlecruiser | Ship bonuses | IV recommended |

### Tank Skills (All Ships)

| Skill | Effect | Priority |
|-------|--------|----------|
| Mechanics | +5% hull HP/level | IV |
| Hull Upgrades | +5% armor HP/level | IV |
| Shield Management | +5% shield HP/level | IV |

### Damage Skills (All Ships)

| Skill | Effect | Priority |
|-------|--------|----------|
| Weapon type skill | +5% damage/level | IV-V |
| Weapon support skills | Various | IV |

## The Battlecruiser Meta

Historically, the **Drake** has been the most popular L3 battlecruiser because:
1. Passive tank is foolproof
2. Missiles always hit (no tracking)
3. Kinetic damage works against common Caldari factions
4. It's extremely forgiving

However, each battlecruiser excels in different scenarios:

| Scenario | Best BC | Why |
|----------|---------|-----|
| First-time L3 pilot | Drake | Lowest skill floor |
| Max ISK efficiency | Hurricane | Highest DPS, fastest clears |
| AFK-ish running | Myrmidon | Set drones, orbit, repair |
| Blood Raiders space | Drake | Immune to neuts |
| Serpentis space | Myrmidon | Thermal drones, sensor damp immune |
| Mixed/unknown | Drake | Works everywhere |

## Upgrade Paths

When you've mastered your battlecruiser and want more:

| Current | Next Step | After That |
|---------|-----------|------------|
| Myrmidon | Dominix | Rattlesnake (faction) |
| Drake | Raven | Golem (marauder) |
| Hurricane | Maelstrom | Vargur (marauder) |
| Harbinger | Apocalypse | Paladin (marauder) |

**Don't Rush:** A well-skilled battlecruiser pilot often clears L3s faster than a poorly-skilled battleship pilot clears L4s. Master your ship before upgrading.

## Summary

1. **Match your tank to ship bonuses**
2. **Prioritize weapons, then tank, then utility**
3. **Swap damage types to match enemy weaknesses**
4. **Don't over-tank or under-tank**
5. **Consider frigates - bring light drones**
6. **Master your ship before upgrading**

The best battlecruiser is the one you can fly well.

---
