# Capacitor Mechanics Guide

Understanding capacitor management - the energy system that powers your ship's modules. Poor cap management is the #1 cause of death for new pilots running active tanks.

## Capacitor Basics

Your capacitor (cap) is the energy pool that powers most active modules:
- Repair modules (armor repairers, shield boosters)
- Active hardeners
- Propulsion modules (MWD, AB)
- Electronic warfare
- Energy weapons (lasers, hybrids)

**When cap runs out, these modules stop working.**

### The Cap Bar

| Cap Level | Status | Meaning |
|-----------|--------|---------|
| 100% | Full | Maximum stored energy |
| 30-40% | **Peak Recharge** | Fastest passive regeneration |
| 25% | Low | Warning zone |
| 0% | Empty | Active modules offline |

---

## The Recharge Curve

**Critical Concept:** Capacitor recharge is NOT linear.

### Peak Recharge at ~33%

Your capacitor recharges fastest at approximately 33% (actually ~25-36% depending on skills).

```
Recharge Rate vs Cap Level:

100% |                              *
     |                           *
 75% |                        *
     |                     *
 50% |                  *
     |               *
 33% |            * ← PEAK RECHARGE
     |          *
 25% |        *
     |      *
  0% |*  *
    ──────────────────────────────
         Recharge Rate →
```

### What This Means

| Cap Level | Recharge Rate | Implication |
|-----------|---------------|-------------|
| 90-100% | Slow | Not efficiently regenerating |
| 30-40% | **Maximum** | Ideal operating range |
| 10-20% | Moderate | Still okay but risky |
| 0-10% | Slow | Danger zone |

**Practical Application:**
- Don't panic when cap drops to 40%
- Hovering at 30-40% means you're recharging fastest
- Only worry when cap drops below 25%

---

## The "Cap Stable" Myth

New pilots often ask: "Is this fit cap stable?"

**Cap stability is overrated for most PvE content.**

### When Cap Stable Matters

| Activity | Cap Stable Needed? | Why |
|----------|-------------------|-----|
| AFK missions | Yes | You're not managing modules |
| L4 missions (long) | Helpful | 20+ minute fights |
| Incursions | Depends | Fleet logistics help |
| PvP | Almost never | Fights are short |
| L1-L2 missions | No | Fights are short |
| Exploration | No | Brief combat |

### Why Cap Stable Often Doesn't Matter

1. **Fights end before cap does** - L1-L2 missions last 2-5 minutes
2. **You can pulse modules** - Run repper at 80% armor, stop at 100%
3. **Cap boosters exist** - Inject cap when needed
4. **NPCs die** - Dead enemies don't shoot you

### The Cap Stable Trap

Pilots sacrifice tank or DPS for cap stability they don't need:

| Trap Fit | Problem |
|----------|---------|
| Cap Recharger instead of damage mod | Kill slower, take more total damage |
| Smaller guns for cap | Lower DPS, longer fight |
| No prop mod for cap | Can't control range or escape |

**Better Approach:** Fit for enough cap to complete fights, use active management.

---

## Pulsing Modules

The core skill of capacitor management.

### How to Pulse

Instead of running modules continuously:
1. **Activate** when needed (armor at 80%, shields at 70%)
2. **Deactivate** when topped off (armor at 100%)
3. **Wait** for next damage spike
4. **Repeat**

### Pulsing Math

| Method | Cap Use | Effect |
|--------|---------|--------|
| Repper always on | 100% usage | Often wasted repair |
| Pulse at 80% armor | 40-60% usage | Same survival, more cap |

### What to Pulse

| Module | Pulse? | Why |
|--------|--------|-----|
| Armor Repairer | **Yes** | Only need repair when damaged |
| Shield Booster | **Yes** | Same as above |
| Active Hardeners | Sometimes | Cap cost is lower, but can pulse |
| MWD | **Yes** | Only when moving/escaping |
| Guns | No | Need continuous DPS |

### Pulsing Protocol for Active Tank

```
IF armor < 80%:
    Activate repairer

IF armor = 100%:
    Deactivate repairer

IF capacitor < 30%:
    Activate cap booster (if fitted)
    Consider warping out
```

---

## Capacitor Pressure: Neuts and Nos

NPCs and players can drain your capacitor with electronic warfare.

### Energy Neutralizers (Neuts)

**Effect:** Drain YOUR capacitor
**Used by:** Blood Raiders, Sansha, some others

| Neut Size | Cap Drained/Cycle |
|-----------|-------------------|
| Small | ~45-65 GJ |
| Medium | ~180-270 GJ |
| Large | ~450-675 GJ |

**Counter:** Your cap is being drained from outside. Defense options below.

### Energy Nosferatu (Nos)

**Effect:** Transfer cap FROM you TO attacker (only works if you have more cap %)
**Used by:** Some NPCs, PvP

**Key Difference:** Nos only works if target has higher cap percentage than user.

### NPC Neut Factions

| Faction | Neut Pressure | Notes |
|---------|---------------|-------|
| Blood Raiders | **Heavy** | Primary threat is neuts |
| Sansha's Nation | Heavy | Combined with tracking disruptors |
| Serpentis | None | Sensor damps instead |
| Guristas | None | ECM instead |
| Angel Cartel | Light | Some neuts, mostly damage |

**Blood Raiders and Sansha require special cap preparation.**

---

## Capacitor Defense Modules

### Cap Boosters

Inject capacitor charges from cargo.

| Aspect | Details |
|--------|---------|
| **How it works** | Consumes charges, instantly adds cap |
| **Charge sizes** | 25, 50, 75, 100, 150, 200, 400, 800, 3200 |
| **Fitting** | Medium slot |
| **Downside** | Cargo dependent, runs out |

**Best Use:** Burst cap when under pressure, not sustained use.

| Ship Size | Typical Charge Size |
|-----------|---------------------|
| Frigate | 150-200 |
| Cruiser | 400-800 |
| Battleship | 800-3200 |

**Tip:** Bring extra charges. Running out mid-fight is death.

### Cap Batteries

Increase cap pool and resist neutralizers.

| Aspect | Details |
|--------|---------|
| **How it works** | Passive module, increases max cap |
| **Neut Resistance** | 20-25% less cap drained by neuts |
| **Fitting** | Medium slot |
| **Downside** | Takes slot, no burst cap |

**Best Use:** Fighting Blood Raiders/Sansha, sustained fights.

### Cap Rechargers

Increase passive recharge rate.

| Aspect | Details |
|--------|---------|
| **How it works** | Passive, % boost to recharge |
| **Fitting** | Medium slot, low PG/CPU |
| **Downside** | Takes slot, low impact per slot |

**Best Use:** Only when no other option, trying to reach cap stable.

### Capacitor Power Relays

Sacrifice shield for cap recharge.

| Aspect | Details |
|--------|---------|
| **How it works** | Passive, boost recharge |
| **Fitting** | Low slot |
| **Downside** | -11% shield boost amount |

**Best Use:** Armor ships that don't need shields.

---

## Capacitor Skills

Skills that improve capacitor performance:

### Primary Cap Skills

| Skill | Effect | Priority |
|-------|--------|----------|
| **Capacitor Management** | +5% cap per level | **Train to IV+** |
| **Capacitor Systems Operation** | -5% recharge time per level | **Train to IV+** |

At Level V each:
- +25% total capacitor
- -25% recharge time
- Combined: Massive cap improvement

### Weapon Cap Skills

| Skill | Effect | Applies To |
|-------|--------|------------|
| **Controlled Bursts** | -5% cap use per level | Hybrid turrets |
| **Small/Med/Large Energy Turret** | Secondary: -5% cap | Lasers |

### Cap Emission Skills

| Skill | Effect |
|-------|--------|
| Capacitor Emission Systems | -5% cap use for remote reppers/cap transfers |
| Energy Nosferatu Operation | +5% nos drain amount |

---

## Weapon Capacitor Use

Different weapon systems have vastly different cap needs.

### Cap Use by Weapon Type

| Weapon | Cap Use | Notes |
|--------|---------|-------|
| **Lasers** | Very High | Amarr's burden |
| **Hybrid (Blasters/Rails)** | High | Gallente/Caldari turrets |
| **Projectiles** | None | Minmatar advantage |
| **Missiles** | None | Caldari advantage |
| **Drones** | None | Set and forget |

### Laser Capacitor Management

Amarr pilots must actively manage cap:

1. **Train cap skills** - Priority for Amarr
2. **Fit cap mods** - Cap batteries, boosters
3. **Use faction crystals** - Some use less cap
4. **Pulse weapons** - Even guns if desperate
5. **Choose fights wisely** - Avoid neut-heavy enemies early

### Hybrid Capacitor Management

Gallente/Caldari turret pilots:

1. **Less severe than lasers** - But still significant
2. **Rails > Blasters** - Rails use more cap, longer range
3. **Cap skills help** - Same as Amarr, just less urgent

---

## Capacitor Budgeting

Estimate if your fit can sustain a fight.

### The Basic Question

```
Cap Regeneration + Cap Injected  ≥  Cap Consumed

If yes: You can fight indefinitely
If no: You have a time limit
```

### Calculating Cap Life

In fitting tools (Pyfa, in-game):
- **Cap Stable at X%** - You regenerate faster than you spend
- **Lasts X minutes** - Time until cap empty

### Minimum Cap Life by Activity

| Activity | Minimum Cap Life |
|----------|------------------|
| L1 missions | 2 minutes |
| L2 missions | 3-5 minutes |
| L3 missions | 5-10 minutes |
| L4 missions | Cap stable or 15+ min |
| PvP | 2-3 minutes (with booster) |

### If Cap Life Is Too Short

Options to extend:
1. **Pulse modules** - First and easiest
2. **Downgrade MWD to AB** - Huge cap savings
3. **Swap to projectiles/missiles** - If cross-training
4. **Add cap mod** - Battery, booster, or recharger
5. **Remove active hardener** - Use passive instead
6. **Use Enduring variants** - Lower cap use modules

---

## Faction-Specific Cap Advice

### Amarr (Lasers)

**Cap is your primary concern.**

| Tip | Details |
|-----|---------|
| Train cap skills first | Before upgrading weapons |
| Always fit cap mod | Battery or booster |
| Carry extra charges | If using cap booster |
| Consider faction crystals | Reduced cap variants |
| Know your cap life | Don't engage if too short |

### Gallente (Hybrids + Drones)

**Moderate cap pressure.**

| Tip | Details |
|-----|---------|
| Drones are cap-free | Rely on them heavily |
| Rails use more cap | Blasters are better for cap |
| Active armor tank | Adds cap pressure |
| Cap skills important | But less urgent than Amarr |

### Caldari (Missiles + Shields)

**Low cap pressure from weapons, moderate from tank.**

| Tip | Details |
|-----|---------|
| Missiles use no cap | Major advantage |
| Shield boosters use cap | Your main drain |
| Passive shield viable | Zero cap tank option |
| XL shield booster | Very cap hungry |

### Minmatar (Projectiles)

**Lowest cap pressure overall.**

| Tip | Details |
|-----|---------|
| Projectiles use no cap | Huge advantage |
| Flex tank | Choose based on cap needs |
| Speed tank | AB uses cap, but not much |
| Cap for utility | All cap goes to prop/tank |

---

## Common Cap Mistakes

| Mistake | Why It's Bad | Solution |
|---------|--------------|----------|
| Repper always on | Wastes cap on full HP | Pulse at 80% armor |
| MWD always on | Massive cap drain | Pulse or use AB |
| No cap booster on Amarr | Will run dry | Always fit cap solution |
| Ignoring cap warning | Die with empty cap | Watch cap bar |
| Fighting Blood Raiders without prep | Get neuted to death | Fit cap battery |
| Cap stable obsession | Sacrifice DPS/tank | Accept 5+ minute cap |

---

## Summary

| Concept | Key Point |
|---------|-----------|
| Recharge curve | Peak recharge at ~33% cap |
| Cap stable | Overrated for short fights |
| Pulsing | Core skill for cap management |
| Neut pressure | Blood Raiders/Sansha are dangerous |
| Cap booster | Burst cap, bring extra charges |
| Cap battery | Neut resistance, passive |
| Weapon cap | Lasers > Hybrids > Projectiles/Missiles |
| Amarr priority | Train cap skills first |

---
Source: EVE game mechanics, EVE University Wiki
Last updated: YC128 (2026)
