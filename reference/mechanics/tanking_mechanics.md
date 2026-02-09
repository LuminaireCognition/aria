# Tanking Mechanics Guide

Understanding how to survive in EVE. This guide explains the three tank types, when to use each, and how to maximize your effective HP.

## The Three Layers

Every ship has three layers of defense:

| Layer | Regenerates? | Primary For |
|-------|--------------|-------------|
| **Shields** | Yes (passive) | Caldari, some Minmatar |
| **Armor** | No | Gallente, Amarr, some Minmatar |
| **Hull** | No | Emergency only |

Damage flows: **Shields → Armor → Hull → Death**

---

## Shield Tanking

Shields are your first line of defense and regenerate automatically.

### Shield Characteristics

| Property | Details |
|----------|---------|
| **Regeneration** | Passive, peaks at ~33% shields |
| **Signature** | Shield extenders increase sig radius |
| **Capacitor** | Boosters use cap, passive regen doesn't |
| **EM Hole** | Most shields have 0% base EM resist |
| **Slot Location** | Mid slots |

### Shield Modules

| Module Type | Effect | Cap Use | Slot |
|-------------|--------|---------|------|
| Shield Booster | Active repair | Yes | Mid |
| Shield Extender | +Max HP | No | Mid |
| Invulnerability Field | +All resists | Yes | Mid |
| EM/Therm/Kin/Exp Hardener | +Specific resist | Yes | Mid |
| EM/Therm/Kin/Exp Amplifier | +Specific resist | No | Mid |
| Adaptive Invuln | +All resists (adaptive) | Yes | Mid |
| Shield Recharger | +Recharge rate | No | Mid |
| Shield Power Relay | +Recharge rate | No | Low |

### Shield Resist Holes

Most shields have weak EM resistance:

| Damage Type | Typical Base Resist |
|-------------|---------------------|
| EM | 0% (hole!) |
| Thermal | 20% |
| Kinetic | 40% |
| Explosive | 50% |

**Always plug your EM hole** when shield tanking.

### When to Shield Tank

| Situation | Shield Good? | Why |
|-----------|--------------|-----|
| Caldari ships | Yes | Bonuses, slot layout |
| Need mid slots | No | Tank competes with tackle/prop |
| Passive regen desired | Yes | Shields regen for free |
| Fighting EM damage | Maybe | Requires plugging EM hole |
| Signature matters | Careful | Extenders bloom sig |

---

## Armor Tanking

Armor is your second layer and does not regenerate naturally.

### Armor Characteristics

| Property | Details |
|----------|---------|
| **Regeneration** | None (requires repairer) |
| **Signature** | Plates don't affect sig |
| **Capacitor** | Repairers use cap, plates don't |
| **Explosive Hole** | Most armor has low explosive resist |
| **Slot Location** | Low slots |

### Armor Modules

| Module Type | Effect | Cap Use | Slot |
|-------------|--------|---------|------|
| Armor Repairer | Active repair | Yes | Low |
| Armor Plate | +Max HP | No | Low |
| Energized Adaptive Nano Membrane | +All resists | No | Low |
| Reactive Armor Hardener | +Adaptive resists | Yes | Low |
| EM/Therm/Kin/Exp Hardener | +Specific resist | Yes | Low |
| EM/Therm/Kin/Exp Membrane | +Specific resist | No | Low |
| EM/Therm/Kin/Exp Coating | +Specific resist (weak) | No | Low |
| Damage Control | +All resists (all layers) | No | Low |

### Armor Resist Holes

Most armor has weak explosive resistance:

| Damage Type | Typical Base Resist |
|-------------|---------------------|
| EM | 50% |
| Thermal | 35% |
| Kinetic | 25% |
| Explosive | 10% (hole!) |

**Watch your explosive hole** when armor tanking vs Angel Cartel.

### When to Armor Tank

| Situation | Armor Good? | Why |
|-----------|-------------|-----|
| Gallente/Amarr ships | Yes | Bonuses, slot layout |
| Need low slots | No | Tank competes with damage mods |
| Want free mid slots | Yes | Leaves mids for utility |
| Signature critical | Yes | Plates don't bloom sig |
| Fighting explosive damage | Maybe | Requires plugging explosive hole |

---

## Hull Tanking

Hull is your last layer. When it's gone, you're dead.

### Hull Characteristics

| Property | Details |
|----------|---------|
| **Regeneration** | None |
| **When to Use** | Rarely, specialized fits only |
| **Modules** | Damage Control, Bulkheads, Hull Repairers |
| **Philosophy** | "Real men hull tank" (meme, not advice) |

### The Damage Control

The **Damage Control** module is unique:
- Provides resists to ALL three layers
- Only one can be fitted
- No stacking penalty with other modules
- Almost always worth fitting

| Layer | Damage Control Bonus |
|-------|----------------------|
| Shields | +12.5% all resists |
| Armor | +15% all resists |
| Hull | +60% all resists |

**Fit a Damage Control on almost every combat ship.**

### When to Hull Tank

Almost never. Exceptions:
- Specific doctrine fits (FC-directed)
- Maximum buffer for certain ships
- Meme fits

---

## Active vs Passive vs Buffer

Three philosophies of tanking:

### Active Tank

**Repair damage as you take it.**

| Aspect | Details |
|--------|---------|
| **Modules** | Armor Repairers, Shield Boosters |
| **Cap Use** | Yes, significant |
| **Sustain** | Indefinite if cap holds |
| **Burst** | Limited by rep amount |
| **Best For** | Solo PvE, sustained fights |

**Active Tank Formula:**
```
Survive if: Repair Rate ≥ Incoming DPS
```

### Passive Tank

**Regeneration exceeds incoming damage (shields only).**

| Aspect | Details |
|--------|---------|
| **Modules** | Shield Extenders, Shield Rechargers, Power Relays |
| **Cap Use** | None |
| **Sustain** | Indefinite |
| **Burst** | High HP buffer while regen works |
| **Best For** | AFK ratting, drone boats |

**Passive Tank Formula:**
```
Survive if: Shield Regen ≥ Incoming DPS
```

Only practical on ships with shield bonuses or large shield pools.

### Buffer Tank

**Enough HP to survive until objective complete or help arrives.**

| Aspect | Details |
|--------|---------|
| **Modules** | Plates, Extenders, Hardeners |
| **Cap Use** | Minimal (only active hardeners) |
| **Sustain** | None (HP doesn't come back) |
| **Burst** | Very high |
| **Best For** | Fleet PvP, ganks, short fights |

**Buffer Tank Formula:**
```
Survive if: Your EHP > Damage before objective/escape
```

### Which Tank When?

| Activity | Tank Type | Why |
|----------|-----------|-----|
| L1-L3 Missions | Active | Sustained fights, solo |
| L4 Missions | Active or Passive | Long fights, need sustain |
| Fleet PvP | Buffer | Logi heals you, need burst HP |
| Solo PvP | Active or Buffer | Depends on engagement style |
| Exploration | Buffer (light) | Just survive long enough to escape |
| AFK Ratting | Passive | No input required |

---

## Effective HP (EHP)

Raw HP doesn't tell the full story. **Effective HP** accounts for resists.

### EHP Formula

```
EHP = Raw HP / (1 - Resist%)

Example:
1000 armor HP with 75% thermal resist
EHP vs thermal = 1000 / (1 - 0.75) = 1000 / 0.25 = 4000 EHP
```

### Why EHP Matters

| Ship | Raw HP | Resist | EHP |
|------|--------|--------|-----|
| A | 5000 | 50% | 10,000 |
| B | 3000 | 80% | 15,000 |

Ship B has less raw HP but survives longer due to higher resists.

### Diminishing Returns on Resists

Each additional resist module is less effective:

| Resist Level | Value of +10% |
|--------------|---------------|
| 0% → 10% | 11% more EHP |
| 50% → 60% | 25% more EHP |
| 75% → 85% | 67% more EHP |
| 90% → 100% | Infinity (invincible) |

**Higher base resists make additional resists more valuable.**

---

## Resist Stacking Penalties

Multiple modules affecting the same resist suffer diminishing returns.

### The Penalty

| Module # | Effectiveness |
|----------|---------------|
| 1st | 100% |
| 2nd | 87% |
| 3rd | 57% |
| 4th | 28% |
| 5th+ | Negligible |

### What Stacks Together

Modules affecting the **same specific attribute** stack:
- Two EM Hardeners (both affect EM resist)
- EANM + EM Hardener (both affect EM resist)

### What Doesn't Stack

Different attributes don't penalize each other:
- EM Hardener + Thermal Hardener (different resists)
- Hardener + Armor Plate (resist vs HP)

### Practical Application

| Setup | Result |
|-------|--------|
| 2 EM Hardeners | Good (100% + 87% = 187% total bonus) |
| 3 EM Hardeners | Okay (100% + 87% + 57% = 244%) |
| 4 EM Hardeners | Diminishing (only +28% for 4th) |
| 1 EM + 1 Therm + 1 Kin + 1 Exp | Each at 100%, no penalty |

**Rule of Thumb:** 2-3 modules per resist type maximum.

---

## Resist Module Categories

Different modules provide resists in different ways.

### Hardeners (Active)

| Property | Details |
|----------|---------|
| **Cap Use** | Yes |
| **Resist Amount** | High (~30% for T2) |
| **Skill Bonus** | NOT boosted by compensation skills |
| **Can Be Neuted** | Keeps working, but drains cap |
| **Best For** | When you have cap to spare |

Examples: Armor EM Hardener II, Adaptive Invulnerability Field II

### Energized Membranes (Passive)

| Property | Details |
|----------|---------|
| **Cap Use** | None |
| **Resist Amount** | Medium (~20% for T2) |
| **Skill Bonus** | Boosted by Compensation skills |
| **Best For** | Cap-tight fits, neut-heavy environments |

Examples: Energized EM Membrane II, EANM (Energized Adaptive Nano Membrane)

### Coatings/Amplifiers (Passive, Weak)

| Property | Details |
|----------|---------|
| **Cap Use** | None |
| **Resist Amount** | Low (~8-15%) |
| **Fitting** | Very light |
| **Best For** | Filling gaps, tight fits |

Examples: EM Armor Coating I, EM Shield Amplifier I

### Comparison Table

| Module Type | Resist | Cap | Skill Boost | Fitting |
|-------------|--------|-----|-------------|---------|
| Hardener | High | Yes | No | Heavy |
| Membrane/Amplifier | Medium | No | Yes | Medium |
| Coating | Low | No | Yes | Light |

### When to Use Which

| Situation | Recommendation |
|-----------|----------------|
| Plenty of cap | Hardeners (highest resist) |
| Fighting neut NPCs | Membranes (no cap dependency) |
| Fitting is tight | Membranes or Coatings |
| Have Compensation V | Membranes (skill bonus) |
| Need maximum resist | Hardener + Membrane (both) |

---

## HP Modules

Modules that add raw HP instead of resists.

### Armor Plates

| Property | Details |
|----------|---------|
| **Effect** | +Flat armor HP |
| **Signature** | No effect |
| **Speed** | Reduced (adds mass) |
| **Best For** | Buffer armor tanks |

Sizes: 200mm, 400mm, 800mm, 1600mm

### Shield Extenders

| Property | Details |
|----------|---------|
| **Effect** | +Flat shield HP |
| **Signature** | Increased (+10-15% per extender) |
| **Speed** | No effect |
| **Best For** | Buffer/passive shield tanks |

**Warning:** Extenders increase signature radius, making you easier to hit.

### HP vs Resist Balance

You need both HP and resists for effective tank:

| Too Much HP, No Resist | Too Much Resist, No HP |
|------------------------|------------------------|
| Damage bleeds through fast | One big hit kills you |
| Repair can't keep up | Nothing to repair into |

**Balanced approach:** Some HP modules + some resist modules.

---

## Compensation Skills

Passive skills that boost membrane/coating resists.

### Armor Compensation Skills

| Skill | Effect |
|-------|--------|
| EM Armor Compensation | +5% EM membrane resist per level |
| Thermal Armor Compensation | +5% Thermal membrane resist per level |
| Kinetic Armor Compensation | +5% Kinetic membrane resist per level |
| Explosive Armor Compensation | +5% Explosive membrane resist per level |

### Shield Compensation Skills

| Skill | Effect |
|-------|--------|
| EM Shield Compensation | +5% EM amplifier resist per level |
| Thermal Shield Compensation | +5% Thermal amplifier resist per level |
| Kinetic Shield Compensation | +5% Kinetic amplifier resist per level |
| Explosive Shield Compensation | +5% Explosive amplifier resist per level |

### Do These Skills Affect Hardeners?

**No.** Compensation skills only boost passive resist modules (membranes, amplifiers, coatings).

Hardeners are NOT affected by compensation skills.

### Training Priority

| Priority | When |
|----------|------|
| Low | If you use mostly hardeners |
| Medium | If you mix hardeners and membranes |
| High | If you use passive tank or fight neut NPCs |

---

## Reactive Armor Hardener

A special module that deserves its own section.

### How It Works

1. Starts with 15% resist to all four damage types
2. As you take damage, resists shift toward the damage you're receiving
3. Total resist stays at 60%, but distribution changes

### Example

```
Start: 15% EM, 15% Therm, 15% Kin, 15% Exp

Taking thermal damage...

After 30 seconds: 5% EM, 35% Therm, 10% Kin, 10% Exp
```

### When to Use

| Situation | Good? | Why |
|-----------|-------|-----|
| Mixed damage NPCs | **Excellent** | Adapts to whatever hits you |
| Single damage type | Good | Eventually maximizes that resist |
| PvP | Risky | Opponent can switch damage |
| Unknown enemies | **Excellent** | Don't need to know ahead of time |

### Fitting Note

Reactive Armor Hardener does use capacitor, but it's very efficient for the resist provided.

---

## Tank by Faction

Each empire favors different tank styles.

### Amarr (Armor)

| Aspect | Details |
|--------|---------|
| Tank Type | Heavy armor |
| Common Modules | Plates, Hardeners, Repairers |
| Strengths | Very high EHP, good EM/Thermal resist |
| Weaknesses | Slow, cap hungry with lasers + hardeners |
| Watch For | Explosive hole, cap management |

### Caldari (Shield)

| Aspect | Details |
|--------|---------|
| Tank Type | Shield (active or passive) |
| Common Modules | Extenders, Boosters, Hardeners |
| Strengths | Passive regen, missiles don't use cap |
| Weaknesses | EM hole, signature bloom from extenders |
| Watch For | EM damage, sig radius |

### Gallente (Armor)

| Aspect | Details |
|--------|---------|
| Tank Type | Active armor |
| Common Modules | Repairers, EANMs, Hardeners |
| Strengths | Drones don't use cap (more for tank) |
| Weaknesses | Explosive hole |
| Watch For | Cap for repper, explosive damage |

### Minmatar (Flexible)

| Aspect | Details |
|--------|---------|
| Tank Type | Either shield or armor |
| Common Modules | Depends on ship |
| Strengths | Flexibility, projectiles don't use cap |
| Weaknesses | Often lower base HP |
| Watch For | Choose tank based on ship bonuses |

---

## Common Tank Mistakes

| Mistake | Why It's Bad | Solution |
|---------|--------------|----------|
| No Damage Control | Losing 60% hull resist, huge EHP loss | Always fit DC |
| Ignoring resist holes | Die fast to that damage type | Plug EM (shield) or Exp (armor) |
| All HP, no resist | Low EHP despite high raw HP | Balance HP and resist |
| All resist, no HP | One-shot by big hits | Need some buffer |
| 4+ of same resist mod | Stacking penalty wastes slots | Max 2-3 per resist |
| Shield extenders everywhere | Sig blooms, easier to hit | Balance with resists |
| Active tank without cap | Tank fails mid-fight | Ensure cap sustains tank |

---

## Summary

| Concept | Key Point |
|---------|-----------|
| Shield | Regens, EM hole, sig bloom from extenders |
| Armor | No regen, explosive hole, no sig effect |
| Hull | Last resort, always fit Damage Control |
| Active | Repair as you go, needs cap |
| Passive | Shield regen only, no cap needed |
| Buffer | Raw HP, for short fights or logi |
| EHP | HP / (1 - resist), the real survival number |
| Stacking | 2-3 same-resist modules max |
| Hardeners | High resist, uses cap, no skill bonus |
| Membranes | Medium resist, no cap, skill bonuses |
| Compensation | Only boosts passive modules |

---
Source: EVE game mechanics, EVE University Wiki
Last updated: YC128 (2026)
