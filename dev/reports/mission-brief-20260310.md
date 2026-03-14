# Mission Brief Session Review — 2026-03-10

**Skill:** `/mission-brief`
**Request:** Damsel in Distress L3, Vexor, strictly T1 and meta
**Pilot:** Federation Navy Suwayyah

## Summary

The mission brief produced a fit with an invalid ammo/turret pairing that the fitting engine flagged via zero turret DPS, but the signal was misinterpreted. Multiple tool calls failed or returned empty, forcing manual fit construction where the error originated.

---

## Critical Errors

### 1. Wrong ammo size (charge/turret mismatch)

150mm Railgun I is a **small** hybrid turret. It accepts Small hybrid charges only. The fit specified Antimatter Charge M (medium), which cannot load. This is the direct cause of 0 turret DPS in the fitting engine output.

**Correct pairing options:**
- 150mm Railgun I + Antimatter Charge S (small turret, small ammo)
- 200mm Railgun I + Antimatter Charge M (medium turret, medium ammo)

### 2. Wrong turret class for hull

The Vexor has medium turret hardpoints. Fitting small turrets (150mm Railgun I) is legal but suboptimal — medium turrets (200mm Railgun I) would provide significantly more DPS. With CPU at 78% utilization, there was ample room for medium turrets.

### 3. Missed diagnostic signal

The fitting engine returned `"kinetic": 0.0` in the DPS breakdown despite Antimatter charges having a kinetic damage component. This should have been immediately recognized as a charge load failure. Instead, the output was rationalized as a possible pilot skill gap, and the fit was presented with a hedge ("turret DPS may not be applying — if you lack Medium Hybrid Turret skill...").

---

## Failed Tool Calls

| Call | Error | Impact |
|------|-------|--------|
| `WebFetch` `/Damsel_in_Distress` | 404 — wrong URL format | Required search + second fetch (2 extra calls) |
| `Read` `reference/pve-intel/npc_damage_types.md` | File not found (correct path: `reference/mechanics/`) | Required Glob fallback (1 extra call) |
| `Read` `reference/pve-intel/cache/INDEX.md` | File not found (cache dir doesn't exist) | Expected miss, no real cost |
| `fitting(check_requirements, pilot_skills="use_pilot")` | Invalid format — tool expects JSON dict, not string | Never validated pilot can fly the fit |
| `fitting(recommend, role="missions-l3", hull="Vexor")` | No archetypes matched | Forced manual fit construction |

## Dead Ends

### Wiki URL pattern

The skill instructs to search `Special:Search` on miss, but the initial direct fetch used `/Damsel_in_Distress` instead of `/The_Damsel_in_Distress_(Level_3)`. EVE University wiki mission pages consistently use `The_` prefix and `_(Level_N)` suffix. This pattern should be internalized to reduce 404s.

### check_requirements API

The `check_requirements` action requires an explicit `pilot_skills` dict (skill_id → level mapping). There is no `"use_pilot"` shorthand like `calculate_stats` has with `use_pilot_skills=true`. The asymmetry between the two actions caused the failure. The fallback should have been `extract_requirements` to at least list what skills were needed.

### No archetype for Vexor L3

The archetype library had no match for `missions-l3` + `Vexor` + `meta` tier. This is the root cause of the manual fit path that introduced the turret/ammo error. Archetype coverage gap.

---

## Suboptimal Decisions

### Drone bandwidth underutilization

The fit used 50 of 75 Mbit bandwidth (5x Hammerhead I). Better options:
- 1x Ogre I + 4x Hammerhead I = 65 Mbit (30% more heavy drone DPS)
- 3x Ogre I = 75 Mbit (max bandwidth, fewer but harder-hitting drones)

The Hammerhead-only choice was made for simplicity but sacrificed meaningful DPS in a fit that was already low on damage output.

### Validation warnings dismissed

The fitting engine returned state restriction warnings on 6 modules. These were dismissed as "cosmetic" without investigation. While Cap Recharger and Energized Membrane are indeed passive modules (the warnings likely reflect a fitting engine state-modeling quirk), the pattern of dismissing warnings without analysis is a process failure.

---

## Root Cause Chain

```
No archetype available for Vexor/missions-l3/meta
  → Manual fit construction required
    → Confused 150mm (small) with medium-class railgun
      → Paired with Antimatter Charge M (medium)
        → Fitting engine returned 0 kinetic DPS
          → Signal misattributed to pilot skill gap
            → Invalid fit presented to user
```

## Corrective Actions

| Action | Category |
|--------|----------|
| When fitting engine shows 0 DPS on a weapon system, investigate charge compatibility before attributing to skills | **Process** |
| EVE University wiki mission URLs follow `The_{Name}_(Level_N)` — use this pattern for direct fetches | **Knowledge** |
| `check_requirements` needs a skill dict; `calculate_stats` accepts `use_pilot_skills=true` — these APIs are asymmetric | **Tool API** |
| Vexor medium turret hardpoints → fit 200mm class railguns, not 150mm | **EVE mechanics** |
| Consider archetype coverage: Vexor/missions-l3 is a common use case that should have an archetype | **Data gap** |

## Corrected Fit

```
[Vexor, Damsel L3]
Drone Damage Amplifier I
Drone Damage Amplifier I
Medium Armor Repairer I
Multispectrum Energized Membrane I
Armor Thermal Hardener I

10MN Afterburner I
Cap Recharger I
Cap Recharger I
Drone Navigation Computer I

200mm Railgun I
200mm Railgun I
200mm Railgun I
200mm Railgun I

Hammerhead I x5
Hobgoblin I x5

Antimatter Charge M x1000
```

*Note: Corrected fit not yet validated through fitting engine. Should be validated before presenting to pilot.*
