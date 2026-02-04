# L4 Missions Guide

The definitive guide to Level 4 Security missions - the endgame of solo highsec PvE.

## What Are L4 Missions?

Level 4 Security missions are the highest-tier solo mission content in highsec:
- Require 5.0+ standing with the agent's corporation
- Battleship-level enemies
- 10-30 minutes per mission (typical)
- 15-40M ISK/hour (ship dependent)

## Requirements

### Standings
- **5.0 Corporation Standing** minimum for L4 agents
- Derived from faction + corp standing combined
- Use the Connections skill to reduce grind

### Skills (Minimum)
| Category | Requirement |
|----------|-------------|
| Ship | Battleship III+ |
| Weapons | Large weapon system IV+ |
| Tank | Shield/Armor compensation III+ |
| Support | Capacitor Management IV+ |

### Ship
Any faction battleship works. See faction fits:
- **Caldari:** Raven (`raven_l4_general.md`)
- **Gallente:** Dominix (`dominix_l4_general.md`)
- **Amarr:** Apocalypse (`apocalypse_l4_general.md`)
- **Minmatar:** Maelstrom (`maelstrom_l4_general.md`)

### ISK Investment
| Ship Type | Hull + Fit Cost |
|-----------|-----------------|
| T1 Battleship | 150-250M ISK |
| Faction Battleship | 400-600M ISK |
| Marauder | 2-3B ISK |

---

## Mission Structure

### Typical L4 Mission Flow

1. **Accept mission** from agent
2. **Read mission details** - Check enemy type
3. **Fit appropriate tank** for damage type
4. **Load correct ammo** for enemy weakness
5. **Complete objectives** - Usually "kill all" or "destroy structure"
6. **Return to agent** - Collect reward + standing
7. **Salvage** (optional) - Return for loot/salvage

### Mission Types

| Type | Description | Example |
|------|-------------|---------|
| Kill | Destroy all enemies | Blockade L4 |
| Kill + Retrieve | Destroy enemies, get item | Cargo Delivery L4 |
| Structure Bash | Destroy specific structure | (Various) |
| Courier | Transport goods | (Not covered here) |

### Pocket Structure

L4 missions often have multiple "pockets" (rooms):
- Acceleration gates between rooms
- Each room has separate spawns
- Clear current room before proceeding
- Can't easily retreat once committed

---

## Rewards

### Per-Mission Rewards

| Component | Typical Value |
|-----------|---------------|
| Base ISK Reward | 1-3M ISK |
| Time Bonus | 0.5-2M ISK |
| Bounties | 5-15M ISK |
| LP | 3,000-8,000 LP |
| Loot | 2-10M ISK |
| Salvage | 1-5M ISK |

### ISK/Hour Expectations

| Setup | ISK/Hour | Notes |
|-------|----------|-------|
| T1 Battleship | 15-25M | Learning phase |
| Skilled T1 BS | 25-35M | Optimized |
| Faction BS | 30-45M | Faster clears |
| Marauder | 50-80M | With blitzing |
| Marauder + MTU/Salvage | 60-100M | Maximum extraction |

### LP Value

Loyalty Points convert to ISK via the LP store:
- Typical conversion: 1,000-2,000 ISK per LP
- Faction-dependent value
- Research LP store for best items

---

## Common L4 Missions

### High-Frequency Missions

| Mission | Faction | Difficulty | Notes |
|---------|---------|------------|-------|
| The Blockade | All | Medium | Multi-pocket, standard |
| Enemies Abound | All | Hard | 5 pockets, long |
| Worlds Collide | Mixed | Hard | Two faction types |
| Gone Berserk | EoM | Easy | Single pocket |
| Angel Extravaganza | Angel | Medium | Escalation chance |
| Damsel in Distress | Multiple | Easy | Rescue mission |
| Recon | All | Medium | Multi-pocket scout |
| Cargo Delivery | All | Easy | Kill + retrieve |

### Missions to Decline

Some L4s are inefficient or dangerous:

| Mission | Reason |
|---------|--------|
| Vengeance | Long, low reward |
| Dread Pirate Scarlet | Excessive travel |
| Any courier L4 | Use a hauler instead |
| Storyline vs. empire | Faction standing loss |

**Decline Rule:** You can decline one mission per agent every 4 hours without standing loss.

---

## Tank Configuration

### Damage by Enemy Faction

> **Reference:** See `reference/mechanics/npc_damage_types.md` for complete faction damage profiles and tank priorities.

Always check the mission enemy faction and fit appropriate resist modules. The reference file includes all major pirate, empire, and special factions.

### Shield Tank Template

```
Mid Slots:
- X-Large Shield Booster
- Adaptive Invulnerability Field
- [Specific resist amplifier based on enemy]
- Cap Battery or Cap Booster
- Propulsion (optional)
```

### Armor Tank Template

```
Low Slots:
- Large Armor Repairer
- Energized Adaptive Nano Membrane
- [Specific resist hardener based on enemy]
- Damage Control
```

---

## Damage Application

### Ammo/Crystal Selection

Always deal the damage type your enemy is weakest to.

> **Reference:** See `reference/mechanics/ammunition.md` for complete ammo selection by weapon system and enemy faction.

### Weapon System Considerations

| System | Pros | Cons |
|--------|------|------|
| Missiles | Selectable damage, easy application | Travel time, cap use |
| Projectiles | Selectable damage, no cap | Tracking issues |
| Lasers | No ammo cost (T1), high DPS | Cap hungry, limited damage types |
| Drones | Low attention, selectable | Aggro management, travel time |

---

## Marauder Progression

Marauders are Tech 2 battleships designed for L4 missions. They represent the pinnacle of solo PvE.

### What Makes Marauders Special

1. **Bastion Module** - Immobilizes ship but provides:
   - 100% bonus to weapon damage and range
   - 30% bonus to repair amount
   - Immunity to electronic warfare
   - Cannot be bumped or moved

2. **Tractor Beam Bonus** - Built-in range/speed bonus for looting
3. **Salvager Bonus** - Built-in cycle time bonus
4. **Massive Tank** - Extreme repair capability in Bastion

### The Four Marauders

| Hull | Faction | Weapon | Special |
|------|---------|--------|---------|
| **Golem** | Caldari | Cruise/Torpedo | Selectable damage, extreme range |
| **Kronos** | Gallente | Blasters | Highest raw DPS, short range |
| **Paladin** | Amarr | Lasers | Highest sustained DPS, no ammo |
| **Vargur** | Minmatar | Projectiles | Selectable damage, cap-free |

### Marauder Comparison

| Marauder | Effective DPS | Range | Tank Style | Difficulty |
|----------|--------------|-------|------------|------------|
| Golem | 1,200-1,500 | 100km+ | Shield | Easy |
| Kronos | 1,500-2,000 | 20km | Armor | Medium |
| Paladin | 1,300-1,600 | 40km | Armor | Medium |
| Vargur | 1,200-1,500 | 40km | Shield | Easy |

### Skill Requirements

Marauders require significant training:

| Skill | Level | Training Time |
|-------|-------|---------------|
| [Faction] Battleship | V | ~24 days |
| Marauders | IV | ~23 days |
| Large [Weapon] | V | ~24 days |
| Weapon Specialization | IV | ~8 days |
| **Total** | - | ~80+ days |

### Marauder Costs

| Component | Cost |
|-----------|------|
| Hull | 1.5-2B ISK |
| T2 Fit | 300-500M ISK |
| Faction Fit | 500M-1B ISK |
| **Total** | 2-3B ISK |

### Is a Marauder Worth It?

**Yes if:**
- You run L4s frequently (10+ hours/week)
- You have the skills already trained
- You want maximum ISK/hour efficiency
- You enjoy the playstyle

**No if:**
- You run L4s casually (few hours/week)
- You're still training core skills
- You'd rather diversify into other activities
- You can't afford to lose 2B+ ISK

### Marauder vs T1 Battleship

| Metric | T1 Battleship | Marauder |
|--------|---------------|----------|
| Clear Speed | 20-30 min | 10-15 min |
| Tank Margin | Comfortable | Overkill |
| ISK/Hour | 25-35M | 60-100M |
| Loss Cost | ~200M | ~2.5B |
| Skill Time | Weeks | Months |

A Marauder pays for itself after ~50-100 hours of missioning (compared to T1 BS).

---

## Efficiency Tips

### Blitzing

"Blitzing" = completing only the mission objective, skipping unnecessary kills.

| Mission Type | Blitz Strategy |
|--------------|----------------|
| Kill all | Can't blitz |
| Kill boss | Kill only required enemy |
| Structure bash | Ignore rats, destroy objective |
| Retrieve item | Grab item, warp out |

Blitzing cuts mission time 30-50% but reduces bounty income.

### Mobile Tractor Unit (MTU)

The MTU automatically tractors and loots wrecks:
- Deploy at start of pocket
- Collects loot while you fight
- Scoop before warping
- ~10M ISK for the module

### Salvaging

Options for salvage:
1. **Ignore it** - Lowest ISK/hour but simplest
2. **Return with Noctis** - Dedicated salvage ship
3. **Marauder built-in** - Bonus to salvagers
4. **Salvage drones** - Slow but passive

Salvage adds 10-30% to mission income but extends time.

### Agent Selection

Choose agents strategically:
- **0.5 security systems** - Harder rats, better loot
- **Near trade hub** - Sell loot efficiently
- **Multiple agents** - Decline bad missions, switch
- **Storyline proximity** - Don't travel far for storylines

---

## Safety Considerations

### Highsec Ganking

L4 mission ships are gank targets:
- **Marauders** attract attention
- **Expensive fits** increase risk
- **Bastion mode** = immobile = vulnerable

**Prevention:**
- Don't bling unnecessarily
- Watch local for scanner alts
- Fit some buffer tank
- Don't AFK in Bastion

### Mission Pocket Safety

- **Never warp unprepared** - Check mission details first
- **Carry mobile depot** - Refit mid-mission if needed
- **Bookmark warp-outs** - Know your escape route
- **Don't aggro full room** - Trigger waves systematically

### Standing Loss

Some missions cause faction standing loss:
- Storyline missions against empires
- Pirate faction missions (rare)

Check mission details before accepting. Decline empire-vs-empire storylines if you need that faction's standing.

---

## Progression Path

### From L3 to L4

1. **Reach 5.0 standing** with target corporation
2. **Train Battleship III** minimum
3. **Acquire T1 battleship** + fit (~200M ISK)
4. **Run easy L4s first** - Gone Berserk, Damsel in Distress
5. **Learn each mission type** - Multi-pocket, etc.
6. **Optimize tank** for each enemy faction
7. **Consider T2 weapons** when trained

### From T1 to Marauder

1. **Train faction Battleship V** (prerequisite)
2. **Train Marauders IV** minimum
3. **Accumulate 2.5B+ ISK** for hull + fit
4. **Learn Bastion timing** - When to activate/deactivate
5. **Optimize blitzing** - Maximize efficiency
6. **Enjoy the ISK/hour**

---

## Quick Reference

### L4 Checklist

```
BEFORE UNDOCKING:
[ ] Check enemy type in mission details
[ ] Fit appropriate resist modules
[ ] Load correct damage ammo
[ ] Bring MTU if salvaging
[ ] Have 2000+ ammo rounds

DURING MISSION:
[ ] Activate tank modules
[ ] Watch capacitor
[ ] Trigger waves carefully
[ ] Deploy MTU early
[ ] Recall drones before gate

AFTER MISSION:
[ ] Return to agent
[ ] Sell loot at trade hub
[ ] Consider salvaging
```

### ISK/Hour Optimization Priority

1. Clear speed (DPS)
2. Tank stability (no warping out)
3. Mission selection (decline bad ones)
4. Blitzing where possible
5. MTU for passive looting
6. LP conversion efficiency
7. Salvaging (if time allows)

---

## Summary

L4 missions are EVE's bread-and-butter solo PvE content:
- Accessible with ~200M ISK and basic battleship skills
- Scale to 80M+ ISK/hour with Marauders
- Consistent, predictable income
- Low risk in highsec

The path from T1 battleship to Marauder is long but rewarding. Start with what you can fly, optimize as you learn, and consider a Marauder only when you've mastered the content and have ISK to spare.

---
Source: EVE University Wiki, community experience
Last updated: YC128 (2026)
