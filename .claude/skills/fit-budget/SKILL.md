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
| `fitting(action="extract_requirements")` | Batch-extract all skill requirements from fit (preferred) |
| `fitting(action="check_requirements")` | Check pilot can fly fit (alternative to extract) |
| `fitting(action="calculate_stats")` | Compare performance (original vs budget) |
| `sde(action="meta_variants")` | Find downgrade options per module |
| `market(action="prices")` | Batch price all original + substitute items |
| `market(action="valuation")` | Price entire fit (alternative to batch prices) |

**Avoid:** `sde(action="skill_requirements")` per module — use batch fitting calls instead.

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

## Efficiency Target

A typical T2 fit budget conversion should complete in **12-15 MCP calls**. If approaching 20+, you are likely checking items individually instead of in batch. Use the batch patterns described below.

**Session context note:** The pilot profile is already loaded at session start. Do not re-read it.

## Execution Flow

### Step 1: Parse Original Fit

Accept EFT format, extract:
- Ship hull
- All modules by slot
- Drones
- Charges (if present)

### Step 2: Identify Unflyable Modules

**Use batch extraction — do NOT check modules individually.**

Extract all skill requirements in one call:
```
fitting(action="extract_requirements", eft="...")
```

Then compare against pilot skills (from `uv run aria-esi skills`) to identify which modules need substitution. Alternatively, use `check_requirements` with pilot skills dict to get a direct can/can't-fly verdict:
```
fitting(action="check_requirements", eft="...", pilot_skills={...})
```

**Do NOT** call `sde(action="skill_requirements")` per module — this wastes 5-10 calls that one batch call replaces.

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

**T1/Meta skill check shortcut:** T1 and named meta modules almost never require skills above level 1-2. After identifying T1 alternatives via `meta_variants`, assume they are flyable unless unusual (faction, storyline, or specialized). Only spot-check skill requirements for edge cases — do not re-verify every T1 substitute individually.

### Step 4: Apply Budget Constraint

**Price all items in a single batch call.** Collect every unique item name from both the original fit and all candidate substitutes, then make one call:
```
market(action="prices", items=["Item A", "Item B", "Item C", ...])
```
Do NOT make separate price calls per module — gather the full list upfront to avoid supplemental calls.

If `--target` specified:
1. Price the current working fit (from the batch above)
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

**These are category hints for common downgrade paths, NOT ground truth.** Always use `sde(action="meta_variants")` to find actual alternatives and `fitting(action="calculate_stats")` for real performance numbers. Never cite the percentages below as fact — they are rough approximations.

### Common T2 → Budget Substitutions

#### Weapons

| T2 Module | Typical Budget Alternative |
|-----------|---------------------------|
| Heavy Missile Launcher II | 'Arbalest' Heavy Missile Launcher |
| 200mm AutoCannon II | 200mm Carbine Repeating Cannon |
| Dual Light Beam Laser II | Dual Anode Light Beam Laser I |
| Light Neutron Blaster II | Modal Light Neutron Particle Accelerator I |

#### Tank (Armor)

| T2 Module | Typical Budget Alternative |
|-----------|---------------------------|
| Medium Armor Repairer II | 'Meditation' Medium Armor Repairer I |
| Multispectrum Energized Membrane II | Multispectrum Coating II |
| Armor Hardener II | Armor Hardener I |
| 1600mm Steel Plates II | 1600mm Crystalline Carbonide Restrained Plates |

#### Tank (Shield)

| T2 Module | Typical Budget Alternative |
|-----------|---------------------------|
| Large Shield Extender II | Large Azeotropic Shield Extender |
| Adaptive Invulnerability Field II | Adaptive Invulnerability Shield Hardener I |
| Shield Boost Amplifier II | Shield Boost Amplifier I |

#### Drones

| T2 Drone | Typical Budget Alternative |
|----------|---------------------------|
| Hammerhead II | Hammerhead I |
| Hobgoblin II | Hobgoblin I |
| Warrior II | Warrior I |
| Ogre II | Ogre I |
| Salvage Drone II | Salvage Drone I |

#### Support Modules

| T2 Module | Typical Budget Alternative |
|-----------|---------------------------|
| Drone Damage Amplifier II | 'Basic' Drone Damage Amplifier |
| Ballistic Control System II | Ballistic Control System I |
| Heat Sink II | Heat Sink I |
| Cap Recharger II | Cap Recharger I |
| 10MN Afterburner II | 10MN Monopropellant Enduring Afterburner |
| 10MN Microwarpdrive II | 10MN Y-S8 Compact Microwarpdrive |

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
