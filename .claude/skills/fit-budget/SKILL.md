---
name: fit-budget
description: Downgrade a T2/expensive fit to match your current skills while maintaining the fit's purpose. Shows performance comparison between original and budget versions.
model: haiku
category: tactical
triggers:
  - "/fit-budget"
  - "budget version of this fit"
  - "make this fit cheaper"
  - "T1 version of this fit"
  - "downgrade fit"
  - "affordable version"
  - "fit I can actually use"
requires_pilot: true
esi_scopes:
  - esi-skills.read_skills.v1
  - esi-wallet.read_character_wallet.v1
data_sources:
  - userdata/pilots/{active_pilot}/profile.md
external_sources: []
---

# ARIA Budget Fit Generator

## Purpose

Take any EFT fit (typically T2/expensive) and generate a budget version that:
1. Uses only modules the pilot can fly
2. Stays within a target budget
3. Maintains the fit's core purpose and role
4. Shows the performance tradeoff

## The Problem This Solves

"All public fits assume T2 skills. New players need 'the same fit but with modules I can actually use' automatically generated."

## Target Audience

- New players copying fits from guides/Reddit/Discord
- Pilots who can't afford T2 modules
- Players who want to try a ship before investing in full T2 training

## Command Syntax

```
/fit-budget                          # Prompts for EFT paste
/fit-budget [EFT block]              # Direct conversion
/fit-budget --target 20m             # Set budget target
/fit-budget --skills-only            # Match skills only, ignore budget
```

## MCP Tools Required

| Tool | Purpose |
|------|---------|
| `fitting(action="check_requirements")` | Check which modules pilot can use |
| `fitting(action="calculate_stats")` | Compare performance |
| `sde(action="meta_variants")` | Find downgrade options |
| `sde(action="skill_requirements")` | Check variant requirements |
| `market(action="valuation")` | Price comparison |

**ESI queries (when available):**
- Skills: `uv run aria-esi skills`
- Wallet: `uv run aria-esi wallet`

## ESI Availability Check (CRITICAL)

**BEFORE making any ESI queries**, check the session hook output for ESI status:

```json
"esi": {"status": "UNAVAILABLE"}
```

### If ESI is UNAVAILABLE:

1. **DO NOT** run `uv run aria-esi` commands - they will timeout
2. **USE** profile `module_tier` field:
   - `t1` → Downgrade everything to T1/Meta
   - `t2` → Pilot likely can use T2, minimal downgrades needed
3. **STILL PROVIDE** full budget conversion using tier assumption
4. **ANSWER IMMEDIATELY** with assumed tier
5. **NOTE** in response: "Assuming T1/Meta skills based on profile (ESI unavailable)"

### If ESI is AVAILABLE:

Proceed with precise skill-based substitutions.

### Tier-Based Fallback

When ESI unavailable, use profile's `module_tier`:

| Profile Tier | Assumption |
|--------------|------------|
| `t1` | Downgrade all T2 → T1/Meta |
| `t2` | Keep T2, downgrade faction/deadspace only |
| Not specified | Default to T1 (safe assumption) |

**Rationale:** A budget fit based on tier assumption is still useful. The pilot can verify in-game.

## Execution Flow

### Step 1: Parse Original Fit

Accept EFT format, extract:
- Ship hull
- All modules by slot
- Drones
- Charges (if present)

### Step 2: Identify Unflyable Modules

For each module, check if pilot meets requirements:
```
fitting(action="check_requirements", eft="...", pilot_skills={...})
```

Create list of modules that need substitution.

### Step 3: Find Substitutes

For each unflyable module, get alternatives:
```
sde(action="meta_variants", item="Module Name")
```

Returns variants from lowest to highest tier:
- Meta 0 (T1 base)
- Meta 1-4 (named/compact/enduring)
- T2
- Faction
- Deadspace/Officer

**Selection priority:**
1. Best variant pilot can use
2. Prefer Meta 4 over Meta 1-3 (better stats)
3. Prefer Compact variants for CPU-constrained fits
4. Prefer Enduring variants for cap-constrained fits

### Step 4: Apply Budget Constraint

If `--target` specified:
1. Price the current working fit
2. If over budget, find cheaper alternatives for expensive items
3. Iterate until under budget

**Cost reduction strategies:**
- T2 → Meta 4 (often 80% stats for 30% cost)
- Faction → T2 → Meta (if budget tight)
- Named drones → T1 base
- Expensive rigs → cheaper variants

### Step 5: Validate Budget Fit

Run the budget fit through EOS:
```
fitting(action="calculate_stats", eft="[budget fit]", use_pilot_skills=true)
```

Ensure:
- CPU/PG fits
- No validation errors
- Cap stability acceptable (if original was stable)

### Step 6: Compare Performance

Calculate key metrics for both fits:

| Metric | Calculation |
|--------|-------------|
| DPS | `fitting.dps.total` |
| EHP | `fitting.tank.ehp` |
| Tank (active) | `fitting.tank.reinforced_hp_per_second` |
| Cap Stability | `fitting.capacitor.is_stable` |
| Speed | `fitting.mobility.max_velocity` |

Show percentage difference for each.

## Response Format

```
═══════════════════════════════════════════════════════════════════════════════
BUDGET CONVERSION: [Ship] - [Fit Name]
───────────────────────────────────────────────────────────────────────────────

SUBSTITUTIONS:
  [Original Module] → [Budget Module]
    [Stat change] | Saves [X]M

  [Original Module] → [Budget Module]
    [Stat change] | Saves [X]M

  ...

PERFORMANCE COMPARISON:
                      Original    Budget      Difference
  DPS:                412         328         -20%
  EHP:                18,200      16,100      -12%
  Active Tank:        128 hp/s    102 hp/s    -20%
  Cap Stable:         Yes         Yes         ─
  Speed:              1,250 m/s   1,250 m/s   ─

COST COMPARISON:
  Original:           37.0M
  Budget:             18.5M
  Savings:            18.5M (-50%)

  Your wallet: [X]M
  Can afford: [X] budget fits

VERDICT:
  [Assessment of what content this budget fit can handle]

───────────────────────────────────────────────────────────────────────────────
BUDGET FIT (copy to clipboard):

[EFT Block]
═══════════════════════════════════════════════════════════════════════════════
```

## Substitution Database

### Common T2 → Budget Substitutions

#### Weapons

| T2 Module | Budget Alternative | Stat Difference |
|-----------|-------------------|-----------------|
| Heavy Missile Launcher II | 'Arbalest' Heavy Missile Launcher | -5% DPS |
| 200mm AutoCannon II | 200mm Carbine Repeating Cannon | -8% DPS |
| Dual Light Beam Laser II | Dual Anode Light Beam Laser I | -12% DPS |
| Light Neutron Blaster II | Modal Light Neutron Particle Accelerator I | -10% DPS |

#### Tank (Armor)

| T2 Module | Budget Alternative | Stat Difference |
|-----------|-------------------|-----------------|
| Medium Armor Repairer II | 'Meditation' Medium Armor Repairer I | -12% rep |
| Energized Adaptive Nano Membrane II | Adaptive Nano Plating II | -15% resists |
| Armor Hardener II | Armor Hardener I | -10% resist |
| 1600mm Steel Plates II | 1600mm Crystalline Carbonide Restrained Plates | -8% HP |

#### Tank (Shield)

| T2 Module | Budget Alternative | Stat Difference |
|-----------|-------------------|-----------------|
| Large Shield Extender II | Large Azeotropic Shield Extender | -5% HP |
| Adaptive Invulnerability Field II | Adaptive Invulnerability Shield Hardener I | -15% resists |
| Shield Boost Amplifier II | Shield Boost Amplifier I | -20% boost |

#### Drones

| T2 Drone | Budget Alternative | Stat Difference |
|----------|-------------------|-----------------|
| Hammerhead II | Hammerhead I | -15% DPS |
| Hobgoblin II | Hobgoblin I | -15% DPS |
| Warrior II | Warrior I | -15% DPS |
| Ogre II | Ogre I | -15% DPS |
| Salvage Drone II | Salvage Drone I | Same cycle time |

#### Support Modules

| T2 Module | Budget Alternative | Stat Difference |
|-----------|-------------------|-----------------|
| Drone Damage Amplifier II | 'Basic' Drone Damage Amplifier | -8% damage bonus |
| Ballistic Control System II | Ballistic Control System I | -8% damage bonus |
| Heat Sink II | Heat Sink I | -8% damage bonus |
| Cap Recharger II | Cap Recharger I | -10% recharge |
| 10MN Afterburner II | 10MN Monopropellant Enduring Afterburner | Same speed, worse cap |
| 10MN Microwarpdrive II | 10MN Y-S8 Compact Microwarpdrive | -3% speed, better fitting |

## Fit Purpose Preservation

### Preserve These Properties

When downgrading, maintain:
- **Tank type** (armor/shield - never mix)
- **Active vs passive tank** (don't switch from active to buffer)
- **Range profile** (brawl vs kite)
- **Capacitor stability** (if original was stable)
- **Slot usage** (fill same slots, don't empty)

### Acceptable Tradeoffs

- 10-25% DPS reduction
- 10-20% tank reduction
- Cap stability margin reduction (if still stable)
- Fitting room tightness

### Unacceptable Changes

- Switching tank type (armor → shield)
- Removing prop mod
- Removing essential utility (web, scram for PvP)
- Making cap unstable if original was stable

## Verdict Guidelines

Based on performance comparison, provide a practical assessment:

| Performance Loss | Verdict |
|------------------|---------|
| < 15% | "Budget fit handles same content as original comfortably." |
| 15-25% | "Budget fit handles [lower tier]. Train for T2 before [higher tier]." |
| 25-40% | "Significant performance gap. Consider this a stepping stone." |
| > 40% | "Major compromise. Original fit targets different content tier." |

### Examples

```
VERDICT: Budget fit handles L2 missions comfortably.
         For L3s, train Medium Drone Operation V first.
```

```
VERDICT: -22% DPS still clears Tier 1-2 abyssals.
         Original fit targets Tier 3+, which needs T2 tank.
```

## Error Handling

| Scenario | Response |
|----------|----------|
| All modules flyable | "Good news! You can already use all modules in this fit." |
| No valid substitutes | "No suitable substitute for [module]. Consider training [skill] first." |
| Can't maintain role | "This fit can't be budgetized without changing its purpose. Try a different ship." |
| Ship unflyable | "You can't fly the [ship] yet. Train [skill] to [level] first." |

## Integration with Other Skills

| After fit-budget | Suggest |
|------------------|---------|
| Budget fit generated | "Use `/fit-check` to verify you can fly this version" |
| Training identified | "Run `/skillplan` to optimize training for T2 upgrades" |
| Want original | "Save ISK for T2 with `/isk-compare`" |

## Edge Cases

### When Original is Already T1

If the input fit is already T1/meta:
- Check for faction → T1 downgrades
- Check for expensive meta → cheaper meta
- If truly budget already, say so

### When Budget Would Break the Fit

Some fits can't be meaningfully downgraded:
- T2 logistics (T1 logi is rarely viable)
- Covert ops (cloak requirement)
- Interdictors (bubble launcher is T2 only)

In these cases, explain why and suggest alternatives.

### Alpha Clone Mode

If pilot is alpha (detected from profile):
- Limit to alpha-compatible modules
- Note omega-only modules explicitly
- Suggest omega subscription if many modules blocked

## Behavior Notes

- Always preserve the fit's intended role
- Show exact stat differences, not vague descriptions
- Include the full EFT block for easy copying
- Be honest about performance gaps
- Frame downgrades positively ("stepping stone to T2")
