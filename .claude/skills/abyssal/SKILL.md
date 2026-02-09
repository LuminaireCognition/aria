---
name: abyssal
description: Abyssal Deadspace guide for weather types, tiers, ship fits, and NPC threats.
model: haiku
category: tactical
triggers:
  - "/abyssal"
  - "abyssal deadspace"
  - "abyssal guide"
  - "what weather for [ship]"
  - "abyssal tier [N]"
  - "abyssal fit"
  - "filament guide"
requires_pilot: false
data_sources:
  - reference/mechanics/abyssal_deadspace.json
---

# ARIA Abyssal Deadspace Module

## Purpose

Provide tactical guidance for EVE Online Abyssal Deadspace content including weather type selection, tier difficulty, ship recommendations, NPC threat priorities, and fitting considerations. Uses static reference data for mechanics and can integrate with fitting tools for ship analysis.

## Trigger Phrases

- "/abyssal"
- "abyssal deadspace"
- "abyssal guide"
- "what weather for [ship]"
- "abyssal tier [N]"
- "abyssal fit"
- "filament guide"

## Command Syntax

```
/abyssal weather <type>       # Weather type details and recommendations
/abyssal tier <N>             # Tier difficulty and rewards
/abyssal ship <hull>          # Ship recommendations for abyssals
/abyssal npc <faction>        # NPC faction threat intel
/abyssal fit <ship>           # Fitting guidance for a hull
```

## Data Source

All abyssal data comes from `reference/mechanics/abyssal_deadspace.json`:
- Weather type effects and NPC damage profiles
- Tier difficulty and average loot values
- Ship recommendations by hull
- NPC faction mechanics and priorities
- Room hazards and special NPCs

**CRITICAL:** Always read the reference file before answering abyssal questions. Verify current meta on community resources like abyss.eve-nt.uk.

## Response Patterns

### Weather Type Query

When asked about a weather type (e.g., "/abyssal electrical"):

1. Read `reference/mechanics/abyssal_deadspace.json`
2. Find the weather in `weather_types`
3. Present effects, damage profile, and recommendations

**Example Response:**

```
## Electrical Weather (Blue Filaments)

**Environmental Effects:**
- +50% EM damage dealt
- -50% capacitor recharge time (faster recharge)

**NPC Damage Profile:**
- EM: 50%
- Thermal: 30%
- Kinetic: 10%
- Explosive: 10%

**Tank Recommendation:** EM resist priority

**Best Ships:**
- Gila (passive shield, cap-stable drones)
- Ishtar (drone damage bonus)
- Stormbringer (capacitor benefits from effect)

**Notes:** Capacitor-hungry fits benefit from faster recharge.
Drones are ideal as they don't consume capacitor.
```

### Tier Query

When asked about a tier (e.g., "/abyssal tier 4"):

1. Read `reference/mechanics/abyssal_deadspace.json`
2. Find the tier in `tiers`
3. Present difficulty, rewards, and requirements

**Example Response:**

```
## Tier 4: Raging Filaments

**Difficulty:** Very Hard
**Time Limit:** 20 minutes
**Ship Class:** Cruiser

**Average Loot:** ~60M ISK/run

**Requirements:**
- T2 modules minimum, faction/deadspace recommended
- All V support skills strongly recommended
- Experience with T3 content required

**Risk Assessment:**
High risk of ship loss without proper preparation.
Weather selection critical - match tank to weather effects.

**Recommended Progression:**
Master T3 first. Consistent clears with time to spare before moving up.
```

### Ship Recommendation Query

When asked about ships (e.g., "/abyssal ship gila"):

1. Read `reference/mechanics/abyssal_deadspace.json`
2. Find the ship in `ship_recommendations`
3. Present strengths, weaknesses, and weather preferences

**Example Response:**

```
## Gila - Abyssal Running

**Hull Class:** Cruiser
**Max Recommended Tier:** 5

**Strengths:**
- Drone damage bonus (forgiving gameplay)
- Passive shield tank (no capacitor needed)
- Beginner-friendly playstyle

**Weaknesses:**
- Expensive hull (~250M+)
- Drone travel time (slower clear speed)
- Weather dependent (avoid Firestorm)

**Preferred Weather:**
- Electrical (cap bonus, EM resist focus)
- Exotic (kinetic resist focus)

**Avoid:**
- Firestorm (-50% armor HP doesn't affect shields, but thermal damage is rough)
- Gamma (-50% shield HP is brutal)

**Notes:** Gold standard for learning abyssals. Drone damage bonus
means you can focus on piloting rather than weapon management.
```

### NPC Threat Query

When asked about NPCs (e.g., "/abyssal npc triglavian"):

1. Read `reference/mechanics/abyssal_deadspace.json`
2. Find the faction in `npc_factions` and related `special_npcs`
3. Present damage profile, resist profile, and kill priorities

**Example Response:**

```
## Triglavian Collective NPCs

**Damage Dealt:**
- Thermal: 50%
- Explosive: 50%

**Resist Profile:**
- Weak to: Thermal, Explosive
- Strong to: EM

**Recommended Damage Type:** Thermal or Explosive

**Kill Priority (highest first):**
1. Tessella Escort (logistics) - Remote repairs allied ships
2. Leshak (battleship) - Ramping damage, extremely dangerous
3. Vedmak (cruiser) - Ramping damage, priority target

**Special Mechanics:**
- **Ramping Damage:** Triglavian weapons deal more damage the longer
  they fire at the same target. Do not let them stack on you.
- **Remote Repairs:** Logistics frigates heal other NPCs. Kill first.

**Tactical Notes:**
Kill logistics immediately. Kite ramping ships or burn them fast.
Never let a Leshak ramp fully - it will destroy you.
```

### Fitting Guidance

When asked about fitting (e.g., "/abyssal fit gila"):

1. Provide general guidance from reference data
2. Optionally use `fitting(action="calculate_stats")` for specific fits

**Example Response:**

```
## Gila Abyssal Fitting Guide

**Tank Style:** Passive Shield (preferred)

**Core Modules:**
- Large Shield Extender II x2
- Shield Recharger II / Pith B-Type Shield Amplifiers
- Drone Damage Amplifier II x3
- Drone Navigation Computer (optional for clear speed)

**Weather-Specific Resist:**
- Electrical: EM Ward Amplifier II
- Exotic: Kinetic Deflection Field II
- Dark: Omni resist

**Drones:**
- Heavy: Ogre II or Faction (Gecko for T5)
- Medium: Hammerhead II or Faction
- Light: Hobgoblin II (for frigates)

**Target Stats:**
- EHP: 40k+ for T3, 60k+ for T4, 80k+ for T5
- Shield Regen: Aim for 100+ HP/s passive
- DPS: 600+ applied drone damage

*For exact stats, paste your EFT fit for analysis.*
```

## Integration with Other Skills

| Context | Suggest |
|---------|---------|
| Asking about ship fitting | "For detailed fit analysis, try `/fitting` with your EFT fit" |
| Asking about loot value | "For mutaplasmid prices, try `/price [mutaplasmid type]`" |
| Skill planning | "For HAC skill requirements, try `/skillplan Gila`" |

## Safety Warnings

Always include appropriate warnings:

```
**WARNING:** Abyssal Deadspace has a strict 20-minute time limit.
If you don't reach the exit, your ship AND pod are destroyed.

**PvP Risk:** Exiting a filament leaves a visible trace.
Gankers camp popular entry systems. Exit with caution.
```

## DO NOT

- **DO NOT** guarantee specific loot values (RNG varies widely)
- **DO NOT** recommend T5/T6 to inexperienced pilots
- **DO NOT** provide exact fits without EOS validation
- **DO NOT** claim knowledge of current meta without noting verification sources

## Notes

- Weather effects apply to both player and NPCs
- Higher tiers spawn more dangerous NPC combinations
- Room layouts and spawns are randomized
- Some rooms have no NPCs (pylons/clouds only)
- Exit gate spawns after all NPCs in final room are killed
