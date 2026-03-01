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

Read `reference/mechanics/abyssal_deadspace.json` before any output. Every weather effect, tier stat, ship recommendation, NPC profile, and damage value in the response **must** trace to this file.

If the queried item has no entry in the file, state that no verified data is available and suggest [abyss.eve-nt.uk](https://abyss.eve-nt.uk). Do not backfill from training data.

## Query Routing

| Query Type | JSON Path | Present |
|-----------|-----------|---------|
| Weather | `weather_types[name]` | Effects, NPC damage profile, tank recommendation, best ships, avoid |
| Tier | `tiers[N]` | Difficulty, time limit, ship class, loot range, requirements, progression |
| Ship | `ship_recommendations[hull]` | Max tier, strengths, weaknesses, preferred/avoid weather |
| NPC | `npc_factions[name]` + `special_npcs` | Damage dealt, resist profile, recommended damage, kill priority, special mechanics |
| Fit | — | Redirect to `/fitting` (see below) |

## Fitting Queries

All fitting requests redirect. This skill provides general guidance only: tank style, weather-specific resist priority, drone strategy — all from reference data. No module names, no EFT blocks.

> For a validated fit: `/fitting <ship> for <weather> abyssal`

## Safety Warning

Always include: Abyssal Deadspace has a strict **20-minute time limit** — failure means ship AND pod loss. Exiting a filament leaves a visible trace that can be camped.

## Rules

- Every stat must cite the reference file — no training-data backfill
- If the reference file lacks the queried data, say so; do not guess
- Do not guarantee specific loot values (RNG varies widely)
- Do not recommend T5/T6 to inexperienced pilots
- Do not generate fits, module lists, or EFT blocks — defer to `/fitting`
