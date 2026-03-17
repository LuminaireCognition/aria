---
name: abyssal
description: Abyssal Deadspace guide for weather types, tiers, ship fits, and NPC threats.
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
injected_prerequisites:
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

Abyssal reference data is injected below — do not re-read `reference/mechanics/abyssal_deadspace.json`. All responses must trace to this data — no training-data backfill.

If the file cannot be read: **do not output a blanket failure**. Proceed to the routing table below — it specifies per-query-type fallbacks (inline tables for weather/tier, explicit "no verified data" for ship/NPC queries that have no inline fallback).

### Weather Type Reference (distilled from abyssal_deadspace.json)

For any weather query, output this table first, then add ship-specific context:

| Weather | Colour | Your Damage Bonus | Your Drawback | NPC Damage Focus |
|---------|--------|-------------------|---------------|------------------|
| Electrical | Blue | +50% EM | None (cap recharges 2x faster — a bonus) | EM 50%, Thermal 30% |
| Exotic | Gold | +50% Kinetic | -50% scan resolution | Kinetic 50%, Thermal 20% |
| Firestorm | Red | +50% Thermal | -50% armor HP | Thermal 60%, Kinetic 20% |
| Gamma | Green | +50% Explosive | -50% shield HP | Explosive 60%, Kinetic 20% |
| Dark | Purple | n/a (turrets -50% range) | n/a | Balanced (25% each) |

> Source: `weather_types[name].effects` and `weather_types[name].npc_damage_profile`
>
> **Note:** NPC damage profiles are approximate and vary by NPC variant within each weather type. Do not state splits as exact ratios.

### Tier Reference (distilled from abyssal_deadspace.json)

| Tier | Name | Ship Class | Difficulty | Avg Loot |
|------|------|-----------|-----------|---------|
| 0 | Tranquil | Destroyer | Tutorial | ~5M ISK |
| 1 | Calm | Cruiser | Easy | ~15M ISK |
| 2 | Agitated | Cruiser | Moderate | ~25M ISK |
| 3 | Fierce | Cruiser | Hard | ~40M ISK |
| 4 | Raging | Cruiser | Very Hard | ~60M ISK |
| 5 | Chaotic | Cruiser | Extreme | ~100M ISK |
| 6 | Cataclysmic | Cruiser | Extreme+ | ~150M ISK |

> Source: `tiers[N].difficulty` and `tiers[N].avg_loot_isk`

## Query Routing

| Query Type | JSON Path | If path is missing from file |
|-----------|-----------|------------------------------|
| Weather | `weather_types[name]` | Cite the inline table above |
| Tier | `tiers[N]` | Cite the inline table above |
| Ship | `ship_recommendations[hull]` + SDE cross-check | "Hull not in reference — check SDE only" |
| Which weather for [ship] | `ship_recommendations[hull].preferred_weather` → then `weather_types[name]` | "No ship data in reference — see [abyss.eve-nt.uk](https://abyss.eve-nt.uk)" |
| NPC | `npc_factions[name]`, `weather_npc_pools[weather]` | "No verified NPC data for this query — see abyss.eve-nt.uk" |

> **NPC damage profiles are approximate** across all query types (weather and NPC faction). Do not state damage splits as exact ratios (e.g., "50/50"). Use `~` prefix or say "primarily X / secondary Y" instead.
| Fit | Redirect to `/fitting <ship> for <weather> abyssal` | n/a |

**Compound queries** (e.g., "best weather for [ship] at tier [N]"): apply all matching rows. Tier context enriches the answer but does not change the routing path.

For Ship queries, call `sde(action="item_info", item="<hull>")` to verify the ship exists. If SDE and reference file disagree on ship class, trust SDE and flag the discrepancy.

**Data-level failure** (file readable but JSON path missing): use the routing table's per-type fallback for that row. Do not say the file "could not be read" when the file was read but the field is absent.

## Safety Warning

Always include: Abyssal Deadspace has a strict **20-minute time limit** — failure means ship AND pod loss. Exiting a filament leaves a visible trace that can be camped.

## Rules

- Keep response under 30 lines
- Append a one-line `Sources:` footer listing MCP calls and reference files used
- Every stat must trace to the reference file — no training-data backfill
- If the reference file lacks the queried data, stop and say what is missing
- For Ship queries, cross-validate hull via `sde(item_info)` before presenting
- Do not guarantee specific loot values (RNG varies widely)
- Do not recommend T5/T6 to inexperienced pilots
- Do not generate fits, module lists, or EFT blocks — defer to `/fitting`
- Do not recommend specific drone types or sizes — drone selection depends on hull bandwidth, which varies per ship. Defer to `/fitting`
- Ship queries: only cite fields from `ship_recommendations[hull]` (strengths, weaknesses, preferred_weather, notes, max_recommended_tier). Do NOT name specific NPC entities or sub-types — describe mechanics instead (e.g., "neut structures can drain cap" not "Ephialtes Lancers neut")
- Weather queries: only cite fields from `weather_types[name]`. Do NOT generate NPC entity names or describe room compositions — that requires `weather_npc_pools` and belongs to NPC queries
- NPC queries: cite `npc_factions[name]` and `weather_npc_pools[weather]`. You may name special NPCs from `special_npcs` only when the key exists in that section

## Reference: Abyssal Deadspace Data (injected)
<!-- prerequisite: reference/mechanics/abyssal_deadspace.json -->
!`cat reference/mechanics/abyssal_deadspace.json`
