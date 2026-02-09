# Fitting Theory Guide

Understanding how to build and adapt ship fits. This guide explains the mechanics behind module selection, fitting resources, and making intelligent tradeoffs.

## Core Fitting Resources

Every ship has two fitting resources that constrain what modules you can equip:

| Resource | Icon | What It Does |
|----------|------|--------------|
| **Powergrid (PG)** | Lightning bolt | Power supply for modules |
| **CPU** | Chip/processor | Processing capacity |

Each module consumes some combination of PG and CPU. If you exceed either limit, you cannot fit the module.

### Checking Your Fit

In the fitting window:
- **Green bar** = Resource available
- **Red bar** = Over budget (cannot undock)
- Hover over bars to see exact numbers

### Common Fitting Problems

| Problem | Solutions |
|---------|-----------|
| CPU over | Compact modules, CPU implant, Co-Processor |
| PG over | Compact modules, PG implant, Reactor Control Unit, Power Diagnostic System |
| Both over | Downgrade module tier, use fitting mods |

---

## Module Naming Conventions

EVE modules follow a naming pattern that tells you their special property at a glance.

### Named Variants (Meta Modules)

These are improved T1 modules with specific advantages:

| Name Pattern | Advantage | Best For |
|--------------|-----------|----------|
| **Compact** | Lower CPU/PG requirement | Tight fits, frigates |
| **Enduring** | Lower capacitor use | Cap-hungry ships (Amarr) |
| **Restrained** | Reduced drawback | MWDs (less sig bloom) |
| **Scoped** | Improved range | Sensor boosters, painters |
| **Ample** | Larger capacity | Cap boosters, cargo |
| **Upgraded** | Balanced improvement | General upgrade |

### Examples in Practice

| Module | Named Variant | Difference |
|--------|---------------|------------|
| 5MN MWD I | 5MN Compact MWD | 20 CPU → 15 CPU |
| 5MN MWD I | 5MN Enduring MWD | 45 GJ/cycle → 36 GJ/cycle |
| 5MN MWD I | 5MN Restrained MWD | 500% sig → 450% sig |
| Cap Booster I | Compact Cap Booster | Less fitting |
| Cap Booster I | Ample Cap Booster | Larger charges |

### How to Choose

1. **Default choice:** Compact (fitting is usually the constraint)
2. **Amarr/active tank:** Enduring (cap matters more)
3. **MWD in PvP:** Restrained (sig reduction helps survival)
4. **Plenty of fitting:** Upgraded or T2

---

## Module Tiers

Modules come in several quality tiers with different stats, prices, and skill requirements.

### Tier Overview

| Tier | Skill Req | Fitting | Stats | Price | Source |
|------|-----------|---------|-------|-------|--------|
| **Civilian** | None | Very low | Terrible | Free | Starter ships |
| **T1** | Level I | Low | Baseline | Cheap | Market, drops |
| **Named/Meta** | Level I | Varies | Better | Cheap-Moderate | Drops, market |
| **T2** | Level V | High | Best (usually) | Moderate | Market |
| **Faction** | Level I | Medium | Excellent | Expensive | LP stores, drops |
| **Deadspace** | Level I | Medium | Best | Very expensive | DED sites |
| **Officer** | Level I | Low | Extreme | Billions | Rare spawns |

### T1 vs T2: When to Upgrade

T2 modules require the base skill at level V. They offer:
- **Higher stats** (typically 20-25% better)
- **Access to T2 ammo** (often the real prize)
- **Higher fitting requirements**

| Module Type | T2 Priority | Reason |
|-------------|-------------|--------|
| Weapons | **High** | T2 ammo is huge DPS boost |
| Damage Mods | High | Direct DPS increase |
| Tank Modules | Medium | Better resists/rep |
| Prop Mods | Low | Marginal speed gain |
| Utility | Low | Minimal improvement |

**Rule of Thumb:** Train weapon skills to V first. T2 guns + T2 ammo is the biggest power spike.

### T2 vs Faction: The Tradeoff

| Aspect | T2 | Faction |
|--------|----|----|
| Stats | Good | Better |
| Fitting | Higher | Lower |
| Skill req | Level V | Level I |
| Price | Moderate | Expensive |
| Best use | Primary fit | Squeezing extra performance |

**When Faction makes sense:**
- You have ISK but not skills
- Fitting is very tight
- The module is critical (hardeners, DCU)
- PvP ship worth the investment

### Deadspace and Officer

These drop from difficult PvE content and offer extreme stats:

| Source | Example | Notes |
|--------|---------|-------|
| DED 3-4 | Gistii, Pithi, Corpii | A-Type/B-Type, small mods |
| DED 5-6 | Gistum, Pithum, Corpum | Medium mods |
| DED 7-8 | Gist, Pith, Corpus | Large mods, expensive |
| DED 9-10 | X-Type variants | Best deadspace |
| Officers | Draclira's, Tobias's | Billions, extreme stats |

**For new pilots:** Ignore deadspace/officer. Focus on T2.

---

## Fitting Tradeoffs

Every fit involves tradeoffs. Understanding these helps you make intentional choices.

### The Fitting Triangle

Most ships balance three competing priorities:

```
         DPS
        /   \
       /     \
    Tank --- Utility
```

- **More DPS** = less tank or utility slots
- **More Tank** = less DPS or utility
- **More Utility** = less DPS or tank

You cannot maximize all three. Decide what's most important for your activity.

### Common Tradeoffs

| Choice | Option A | Option B |
|--------|----------|----------|
| MWD vs AB | Speed, cap hungry, sig bloom | Less speed, cap stable, no bloom |
| Active vs Buffer | Sustained, needs cap | Burst, cap independent |
| DPS vs Range | Blasters, short range | Rails, less DPS |
| Resist vs HP | Less raw HP, more EHP | More raw HP, less vs specific |
| T2 vs Compact | Better stats | Actually fits |

### Making the Right Choice

Ask yourself:
1. **What will I fight?** (determines resist profile)
2. **How long will fights last?** (active vs buffer)
3. **Am I alone?** (need more self-sufficiency)
4. **Can I control range?** (weapon choice)
5. **What's my budget?** (T1 vs T2 vs faction)

---

## Rig Mechanics

Rigs are permanent modifications installed in rig slots. They cannot be removed without destruction.

### Rig Basics

| Property | Description |
|----------|-------------|
| **Calibration** | Ships have calibration points (usually 400) |
| **Size** | Small/Medium/Large/Capital (must match hull) |
| **Drawback** | Most rigs have a penalty |
| **Stacking** | Multiple same-effect rigs stack with penalty |

### Common Rig Categories

| Category | Effect | Drawback |
|----------|--------|----------|
| **Armor** | +HP, +repair, +resist | -Max velocity |
| **Shield** | +HP, +recharge, +resist | -Signature radius (bigger) |
| **Astronautic** | +speed, +agility | -Armor HP |
| **Weapon** | +damage, +RoF, +range | -Powergrid or CPU |
| **Drone** | +damage, +HP, +range | -CPU |
| **Electronics** | +lock range, +scan | -Shield HP |

### Rig Size and Calibration

| Rig Size | Hull Class | Typical Calibration |
|----------|------------|---------------------|
| Small | Frigate, Destroyer | 50-100 each |
| Medium | Cruiser, BC | 100-150 each |
| Large | Battleship | 150-200 each |
| Capital | Capitals | 200-400 each |

Most ships have 400 calibration. Three small rigs at 100 each = 300 used.

### T1 vs T2 Rigs

| Aspect | T1 Rig | T2 Rig |
|--------|--------|--------|
| Calibration | Lower | Higher |
| Stats | Good | 20% better |
| Drawback | Same | Same |
| Price | Cheap | Moderate-expensive |
| Best use | Most fits | When stats matter |

**T2 Rigs** are worth it for:
- Combat ships you'll fly repeatedly
- When the extra stats meaningfully help
- When calibration isn't tight

---

## Stacking Penalties

Multiple modules of the same type suffer diminishing returns.

### The Penalty Formula

| Module Count | Effectiveness |
|--------------|---------------|
| 1st | 100% |
| 2nd | 87% |
| 3rd | 57% |
| 4th | 28% |
| 5th | 10% |
| 6th+ | Negligible |

### What Stacks

Modules affecting the **same attribute** stack:
- Three Gyrostabilizers (all boost projectile damage)
- Two Tracking Enhancers + Tracking Computer (all boost tracking)

### What Doesn't Stack

Different module types don't stack-penalize each other:
- Gyrostabilizer (damage) + Tracking Enhancer (tracking) = both full effect
- Armor Repairer (rep) + Armor Hardener (resist) = both full effect

### Practical Application

| Situation | Recommendation |
|-----------|----------------|
| 2 damage mods | Both valuable (100% + 87% = 187%) |
| 3 damage mods | Third still decent (100% + 87% + 57% = 244%) |
| 4 damage mods | Marginal gain, slot better used elsewhere |
| 4 resist hardeners | Diminishing, but EHP is multiplicative |

**Rule of Thumb:** 3 of the same type is usually the practical limit.

---

## Slot Efficiency

Each slot has opportunity cost. What you fit there means something else you don't fit.

### Slot Values by Ship Type

| Ship Role | High Slots | Mid Slots | Low Slots |
|-----------|------------|-----------|-----------|
| DPS | Weapons | Prop, application | Damage mods, tank |
| Tank | Utility | Shield tank | Armor tank |
| Tackle | Point, web | Prop, tackle mods | Speed mods |
| Logistics | Reppers | Cap, prop | Fitting mods |

### Fitting Modules: The Tax

Modules that help you fit other modules (Co-Processors, RCUs) take slots:

| Module | Effect | Slot | Worth It? |
|--------|--------|------|-----------|
| Co-Processor | +CPU | Low | When it enables core fit |
| Reactor Control Unit | +PG | Low | When it enables core fit |
| Power Diagnostic | +PG, +cap, +shield | Low | Often worth it anyway |
| Micro Auxiliary Power Core | +PG (small amount) | Low | Frigates only |

**Best Practice:** Only use fitting mods if:
1. You can't make the fit work otherwise
2. The alternative (compact modules) loses more than the slot

### Empty Slots

Empty slots are acceptable when:
- No useful module exists for that slot
- Fitting resources are exhausted
- The slot would hurt you (high slot weapon on exploration ship)

Don't add junk just to fill slots.

---

## Implants for Fitting

Implants in slots 6-10 can help with fitting:

| Implant | Slot | Effect | Price |
|---------|------|--------|-------|
| Inherent Implants 'Squire' PG | 6 | +1% to +6% PG | Cheap-Moderate |
| Inherent Implants 'Squire' CPU | 7 | +1% to +6% CPU | Cheap-Moderate |

**Note:** Low-grade (+1%) implants are cheap. Use them freely for tight fits.

---

## Fitting Workflow

When building a fit from scratch:

### Step 1: Define Purpose
- What activity? (missions, exploration, PvP)
- What enemies? (determines tank)
- Solo or fleet? (affects self-sufficiency needs)

### Step 2: Core Modules First
1. Weapons (your DPS source)
2. Propulsion (you always need to move)
3. Tank (enough to survive the content)

### Step 3: Utility and Support
4. Application mods (tracking, painters, webs)
5. Damage mods (after tank is sufficient)
6. Cap management (if needed)

### Step 4: Rigs
7. Fill rig slots to enhance core purpose
8. Usually tank or damage rigs

### Step 5: Iterate
9. Check fitting - does it actually fit?
10. Swap to Compact variants if needed
11. Consider fitting implants
12. Verify cap stability (if required)

---

## Common Fitting Mistakes

| Mistake | Why It's Bad | Solution |
|---------|--------------|----------|
| All damage, no tank | Die before dealing damage | Balance DPS and survival |
| Too many tank mods | Kill slowly, eventually die anyway | Find the minimum viable tank |
| Mixing weapon types | Damage bonus only applies to one | Pick one weapon system |
| MWD on PvE ship | Sig bloom, cap drain | AB usually better for PvE |
| Cap unstable active tank | Tank fails mid-fight | Either go passive or fit cap |
| T2 everything | Often doesn't fit | Meta modules exist for a reason |
| Ignoring rig drawbacks | Shield rigs make you easier to hit | Read the penalties |

---

## Summary

| Concept | Key Point |
|---------|-----------|
| Fitting resources | CPU and PG limit what you can equip |
| Named modules | Compact = fitting, Enduring = cap, Restrained = drawback |
| Module tiers | T2 weapons first, then damage mods, then tank |
| Rigs | Permanent, have drawbacks, small/medium/large |
| Stacking penalty | 3 of same type is practical limit |
| Slot efficiency | Every slot has opportunity cost |
| Tradeoffs | DPS vs Tank vs Utility - pick two |

---
Source: EVE game mechanics, EVE University Wiki
Last updated: YC128 (2026)
