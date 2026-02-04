# Abyssal Deadspace Guide Proposal

## Executive Summary

Enhance the `/exploration` skill or create a dedicated `/abyssal` skill that provides tier recommendations, damage profiles, and room tactics for Abyssal Deadspace content. This demystifies one of EVE's most popular but intimidating PvE activities.

**Primary value:** Confident filament selection and ship preparation.

---

## Problem Statement

Abyssal Deadspace is:

1. **High-stakes** - Ship destruction in a failed run (20-minute timer)
2. **Complex** - 5 tiers × 6 weather types × multiple room layouts
3. **Opaque** - No in-game information about what's inside a filament
4. **Skill-dependent** - Wrong tier = death, right tier = ISK

Players rely on YouTube videos and community guides. ARIA should synthesize this into actionable intel.

---

## Existing Reference Data

`reference/mechanics/abyssal_deadspace.md` exists with partial data. Needs expansion:

### Current Coverage

- Basic tier descriptions
- Some weather type effects
- General ship recommendations

### Gaps

- Complete damage profiles per weather type
- Room type breakdown and tactics
- NPC spawn tables
- Loot tier analysis
- Ship fitting requirements by tier

---

## Proposed Skill: `/abyssal`

### Triggers

```yaml
triggers:
  - "/abyssal"
  - "abyssal deadspace"
  - "filament guide"
  - "what tier abyssal can I run"
  - "abyssal [weather] tier [N]"
  - "abyssal fitting"
  - "is my ship ready for abyssals"
```

### Commands

| Command | Description |
|---------|-------------|
| `/abyssal` | Overview of tiers and weather types |
| `/abyssal <weather>` | Specific weather type breakdown |
| `/abyssal tier <N>` | Requirements and rewards for tier |
| `/abyssal fit <ship>` | Ship viability assessment |
| `/abyssal loot <tier>` | Expected loot and ISK/hour |

### Example Interactions

**Overview:**
```
User: /abyssal

ARIA: ## Abyssal Deadspace Overview

      ### Tiers
      | Tier | Difficulty | Est. Reward | Ship Class |
      |------|------------|-------------|------------|
      | T0 (Calm) | Tutorial | ~5M | Frigate/Cruiser |
      | T1 (Agitated) | Easy | ~10M | Cruiser |
      | T2 (Fierce) | Medium | ~20M | Cruiser |
      | T3 (Raging) | Hard | ~35M | Cruiser (skilled) |
      | T4 (Chaotic) | Very Hard | ~50M | Cruiser (elite) |
      | T5 (Cataclysmic) | Extreme | ~80M | Cruiser (max) |

      ### Weather Types
      | Weather | Color | Effect | Recommended Resist |
      |---------|-------|--------|-------------------|
      | Electrical | Blue | +50% EM, capacitor | EM |
      | Dark | Black | -50% turret range | EM/Therm |
      | Exotic | Yellow | +50% Kinetic | Kinetic |
      | Firestorm | Red | +50% Thermal, armor | Thermal |
      | Gamma | Green | +50% Explosive | Explosive |

      Run `/abyssal <weather>` for detailed breakdown.
      Run `/abyssal fit <ship>` to check your ship's viability.
```

**Specific weather:**
```
User: /abyssal electrical

ARIA: ## Electrical Abyssal Weather

      ### Environmental Effects
      | Effect | Modifier |
      |--------|----------|
      | EM damage dealt by NPCs | +50% |
      | Capacitor recharge | -50% |
      | Turret optimal range | +50% |

      ### NPC Factions
      | Faction | Damage | Tank |
      |---------|--------|------|
      | Triglavian | Therm/Exp | Therm/Exp |
      | Sleepers | Omni | Omni |
      | Drones (Rogue) | Exp/Therm | EM/Therm |
      | Drifter | Omni (heavy EM) | Omni |

      ### Recommended Fit Profile
      - **Resist priority:** EM > Thermal > Explosive > Kinetic
      - **Capacitor:** Fit cap boosters or batteries (cap penalty)
      - **Damage type:** Thermal or Explosive
      - **Range:** Can extend with weather bonus

      ### Ship Recommendations by Tier

      | Tier | Ship | Notes |
      |------|------|-------|
      | T1-T2 | Gila | Passive shield, drone damage |
      | T3 | Gila, Vagabond | Shield extenders, cap battery |
      | T4 | Gila, Sacrilege | High EM resist, oversized AB |
      | T5 | Gila (bling), Cerberus | Expensive, need experience |

      ### Danger Rooms
      - **Deviant Automata Suppressor** - Neuts heavily, orbits
      - **Vila Swarmer** - High DPS, target first
      - **Starving Vedmak** - Ramping damage, kill fast
```

**Ship assessment:**
```
User: /abyssal fit Vexor Navy Issue

ARIA: ## Vexor Navy Issue Abyssal Viability

      ### Base Assessment
      | Attribute | Rating | Notes |
      |-----------|--------|-------|
      | Tank | Medium | Needs active rep or buffer |
      | DPS | Good | 600+ with drones |
      | Speed | Medium | 800-1000 m/s with AB |
      | Cap | Okay | Active tank is cap-hungry |

      ### Tier Recommendations
      | Tier | Viability | Requirements |
      |------|-----------|--------------|
      | T0-T1 | Easy | Basic skills |
      | T2 | Comfortable | T2 drones, good skills |
      | T3 | Challenging | Faction mods, experience |
      | T4+ | Not recommended | Hull limitation |

      ### Suggested Fit (T2 Electrical)
      - High: Drone Link Augmentor II
      - Mid: Large Shield Extender II, Cap Battery II, 10MN AB
      - Low: Drone Damage Amp II x3, Shield Power Relay II
      - Rigs: EM resist, drone speed

      ### Weather Suitability
      | Weather | Suitability | Notes |
      |---------|-------------|-------|
      | Electrical | Good | Drones unaffected by neuts |
      | Dark | Poor | Drone tracking issues |
      | Exotic | Medium | Kinetic resistance needed |
      | Firestorm | Good | Armor variant viable |
      | Gamma | Medium | Explosive resist needed |

      VNI is solid for T1-T2, marginal for T3.
      For T4+, consider Gila or HAC.
```

**Loot expectations:**
```
User: /abyssal loot tier 3

ARIA: ## Tier 3 Abyssal Loot

      ### Average Returns
      | Component | Value Range | Notes |
      |-----------|-------------|-------|
      | Triglavian Survey Data | 5-15M | Always drops |
      | Skill Extractors | 0-50M | Rare |
      | Mutaplasmids | 0-100M | Very rare |
      | Blueprints | 1-10M | Common |

      ### ISK/Hour Estimate
      | Efficiency | ISK/Hour |
      |------------|----------|
      | New runner | ~25M |
      | Experienced | ~40M |
      | Optimized | ~60M |

      Note: Includes time for travel, filament acquisition.
      Does not include ship loss risk (~1 in 50 for experienced).

      ### High-Value Drops
      - Unstable Mutaplasmids (50-500M)
      - Zero-Point Condensate (T5 ingredient)
      - Entropic Radiation Sink Blueprint

      T3 is the "efficiency breakpoint" - good ISK for
      moderate risk. T4+ has higher ceiling but ship loss hurts.
```

---

## Implementation

### Phase 1: Weather and Tier Reference

**Deliverables:**
- [ ] Create `/abyssal` skill definition
- [ ] Complete reference data for all weather types
- [ ] Tier difficulty and reward estimates
- [ ] Basic ship recommendations

**Reference data structure:**
```json
{
  "weather_types": {
    "electrical": {
      "color": "blue",
      "effects": {
        "em_damage_bonus": 0.50,
        "capacitor_penalty": -0.50,
        "turret_range_bonus": 0.50
      },
      "npc_damage_profile": "EM > Thermal",
      "npc_tank_profile": "Thermal > Explosive",
      "recommended_resist": "EM"
    }
  },
  "tiers": {
    "3": {
      "name": "Raging",
      "difficulty": "Hard",
      "avg_loot": 35000000,
      "required_dps": 400,
      "required_tank": 300,
      "time_limit_seconds": 1200
    }
  }
}
```

### Phase 2: Ship Assessment

**Deliverables:**
- [ ] Ship → tier viability mapping
- [ ] Weather suitability analysis
- [ ] Integration with `/fitting` for stat validation

**Logic:**
```python
def assess_abyssal_viability(ship_name: str, fit_eft: str = None) -> dict:
    """
    Assess ship's abyssal viability.
    If EFT fit provided, validate stats against tier requirements.
    """
    # Base hull assessment
    hull_data = sde(action="item_info", item=ship_name)

    # Check if fit provided
    if fit_eft:
        stats = fitting(action="calculate_stats", eft=fit_eft)
        # Compare DPS, tank, speed against tier thresholds

    return {
        "max_recommended_tier": 3,
        "weather_suitability": {...},
        "limiting_factors": ["cap stability", "EM resist"]
    }
```

### Phase 3: Room and NPC Intel

**Deliverables:**
- [ ] Room type database (Battleship spawn, drone swarm, etc.)
- [ ] NPC threat prioritization
- [ ] Danger room identification

**Example room data:**
```json
{
  "room_types": {
    "drone_swarm": {
      "npcs": ["Vila Swarmer", "Renewing Automata"],
      "threat": "High DPS, weak tank",
      "tactic": "Focus Vila first, then drones"
    },
    "leshak_spawn": {
      "npcs": ["Starving Vedmak", "Ghosting Damavik", "Leshak"],
      "threat": "Ramping damage, must kill fast",
      "tactic": "Primary Leshak before ramp-up"
    }
  }
}
```

### Phase 4: Loot and ISK/Hour

**Deliverables:**
- [ ] Loot table expectations by tier
- [ ] Market integration for current values
- [ ] ISK/hour estimates with assumptions

---

## Skill Definition

```yaml
---
name: abyssal
description: Abyssal Deadspace guide for filament selection, weather effects, and ship preparation. Use for tier recommendations and loot analysis.
model: haiku
category: tactical
triggers:
  - "/abyssal"
  - "abyssal deadspace"
  - "filament guide"
  - "what tier abyssal can I run"
  - "abyssal [weather] tier [N]"
  - "abyssal fitting"
  - "is my ship ready for abyssals"
requires_pilot: false
esi_scopes: []
data_sources:
  - reference/mechanics/abyssal_deadspace.json
has_persona_overlay: false
---
```

---

## Reference Data Requirements

### Expand: `reference/mechanics/abyssal_deadspace.json`

```json
{
  "_meta": {
    "description": "Abyssal Deadspace weather types, tiers, and NPC data",
    "sources": [
      "EVE University Wiki",
      "Abyssal Lurkers Discord",
      "Abyss Tracker statistics"
    ],
    "last_verified": "2026-01-29"
  },
  "weather_types": {
    "electrical": {...},
    "dark": {...},
    "exotic": {...},
    "firestorm": {...},
    "gamma": {...}
  },
  "tiers": {
    "0": {...},
    "1": {...},
    "2": {...},
    "3": {...},
    "4": {...},
    "5": {...}
  },
  "npcs": {
    "starving_vedmak": {
      "name": "Starving Vedmak",
      "damage_type": "Thermal/Explosive",
      "tank_type": "Thermal/Explosive",
      "special": "Ramping damage (Entropic)",
      "threat_level": "High",
      "priority": 1
    }
  },
  "ships": {
    "gila": {
      "max_tier": 5,
      "recommended_tier": 4,
      "notes": "Top cruiser choice, passive tank"
    },
    "vexor_navy_issue": {
      "max_tier": 3,
      "recommended_tier": 2,
      "notes": "Good entry-level, limited at high tiers"
    }
  }
}
```

---

## Integration Points

### With Fitting Tools

```python
# Validate fit against tier requirements
stats = fitting(action="calculate_stats", eft=user_fit)

if stats["dps"]["total"] < tier_required_dps:
    warn("DPS may be insufficient for this tier")

if stats["tank"]["ehp"] < tier_required_tank:
    warn("Tank is light for this tier")
```

### With Market Tools

```python
# Get current prices for loot items
loot_prices = market(action="prices", items=[
    "Triglavian Survey Database",
    "Zero-Point Condensate",
    "Unstable Mutaplasmid"
])
```

### With Skill Tools

```python
# Check if pilot has required skills
skills = skills(action="skill_requirements", item="Gila")
```

---

## Open Questions

1. **Separate skill or enhance `/exploration`?**
   - Abyssals are distinct from normal exploration
   - Recommendation: Separate `/abyssal` skill

2. **Include PvP arenas (Proving Grounds)?**
   - Uses abyssal filaments but very different gameplay
   - Recommendation: Mention existence, don't cover in detail

3. **Track personal statistics?**
   - Run success rate, average loot, etc.
   - Recommendation: Phase 3+, would need manual logging

4. **Pochven integration?**
   - Related content (Triglavian ships, filaments)
   - Recommendation: Separate skill if needed

---

## Example CLI Integration

```bash
# Quick reference
uv run aria-esi abyssal --weather electrical

# Tier info
uv run aria-esi abyssal --tier 3

# Ship check
uv run aria-esi abyssal --check-ship "Gila"
```

---

## Summary

| Aspect | Decision |
|--------|----------|
| Skill name | `/abyssal` |
| Data source | Expanded `abyssal_deadspace.json` |
| Core features | Weather guide, tier requirements, ship assessment |
| Fitting integration | Validate stats against tier thresholds |
| Loot analysis | Market integration for value estimates |
| MVP | Weather effects + tier guide + ship recommendations |

This addresses a popular but intimidating PvE activity with structured reference data.
