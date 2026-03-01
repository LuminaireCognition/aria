---
name: abyssal
description: Abyssal Deadspace guide for weather types, tiers, ship fits, and NPC threats.
model: sonnet
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
prerequisite_files:
  - reference/mechanics/abyssal_deadspace.json
---

# Abyssal Deadspace Module

```
/abyssal weather <type>       # Weather type details and recommendations
/abyssal tier <N>             # Tier difficulty and rewards
/abyssal ship <hull>          # Ship recommendations for abyssals
/abyssal npc <faction>        # NPC faction threat intel
/abyssal fit <ship>           # Fitting guidance → redirects to /fitting
```

## Data Gate

Read `reference/mechanics/abyssal_deadspace.json` before any output. If the file could not be read, is empty, or lacks the queried item — state "no verified data available" and suggest [abyss.eve-nt.uk](https://abyss.eve-nt.uk). Do not provide partial answers from training data. A missing detail should be reported as missing, not filled in.

## Query Routing

| Query Type | JSON Path | SDE Cross-Check |
|-----------|-----------|-----------------|
| Weather | `weather_types[name]` | — |
| Tier | `tiers[N]` | — |
| Ship | `ship_recommendations[hull]` | `sde(item_info, item=hull)` to confirm hull exists |
| NPC | `npc_factions[name]` + `special_npcs` | — |
| Fit | Redirect to `/fitting <ship> for <weather> abyssal` | — |

For Ship queries, call `sde(action="item_info", item="<hull>")` to verify the ship exists. If SDE and reference file disagree on ship class, trust SDE and flag the discrepancy.

## Safety Warning

Always include: Abyssal Deadspace has a strict **20-minute time limit** — failure means ship AND pod loss. Exiting a filament leaves a visible trace that can be camped.

## Rules

- Every stat must trace to the reference file — no training-data backfill
- If the reference file lacks the queried data, stop and say what is missing
- For Ship queries, cross-validate hull via `sde(item_info)` before presenting
- Do not guarantee specific loot values (RNG varies widely)
- Do not recommend T5/T6 to inexperienced pilots
- Do not generate fits, module lists, or EFT blocks — defer to `/fitting`
