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

## Command Syntax

```
/abyssal weather <type>       # Weather type details and recommendations
/abyssal tier <N>             # Tier difficulty and rewards
/abyssal ship <hull>          # Ship recommendations for abyssals
/abyssal npc <faction>        # NPC faction threat intel
/abyssal fit <ship>           # Fitting guidance for a hull
```

## Data Source

All abyssal data comes from `reference/mechanics/abyssal_deadspace.json`. Read this file before answering any abyssal question.

## Response Patterns

### Weather Type Query

When asked about a weather type (e.g., "/abyssal electrical"):

1. Read `reference/mechanics/abyssal_deadspace.json`
2. Find the weather in `weather_types`
3. Present: Environmental Effects / NPC Damage Profile / Tank Recommendation / Best Ships / Notes

### Tier Query

When asked about a tier (e.g., "/abyssal tier 4"):

1. Read `reference/mechanics/abyssal_deadspace.json`
2. Find the tier in `tiers`
3. Present: Difficulty / Time Limit / Ship Class / Average Loot / Requirements / Risk Assessment / Recommended Progression

### Ship Recommendation Query

When asked about ships (e.g., "/abyssal ship gila"):

1. Read `reference/mechanics/abyssal_deadspace.json`
2. Find the ship in `ship_recommendations`
3. Present: Hull Class / Max Recommended Tier / Strengths / Weaknesses / Preferred Weather / Avoid Weather / Notes

### NPC Threat Query

When asked about NPCs (e.g., "/abyssal npc triglavian"):

1. Read `reference/mechanics/abyssal_deadspace.json`
2. Find the faction in `npc_factions` and related `special_npcs`
3. Present: Damage Dealt / Resist Profile / Recommended Damage Type / Kill Priority / Special Mechanics / Tactical Notes

### Fitting Guidance

When asked about fitting (e.g., "/abyssal fit gila"):

1. Read reference data for general guidance on tank style and weather-specific resists
2. **NEVER generate a complete ship fit** from this skill — no EFT blocks, no module lists, no specific module names
3. Present: General Tank Approach / Weather-Specific Resist Priority / Drone Strategy (from reference data only)
4. Direct the pilot to use `/fitting <ship> for <weather> abyssal` for a validated fit

Module names and stats change across patches. The `/fitting` skill uses EOS for validated output.

## Failure Handling

If the reference file does not contain an entry for the queried weather type, ship, NPC faction, or tier, state that no verified data is available. Suggest checking community resources like abyss.eve-nt.uk or providing more details.

## Safety Warnings

Always warn: Abyssal Deadspace has a strict 20-minute time limit -- failure means ship AND pod loss. Exiting a filament leaves a visible trace that gankers can camp.

## DO NOT

- **DO NOT** guarantee specific loot values (RNG varies widely)
- **DO NOT** recommend T5/T6 to inexperienced pilots
- **DO NOT** provide exact fits without EOS validation
- **DO NOT** claim knowledge of current meta without noting verification sources
- **DO NOT** generate ship fits, module lists, or EFT-format fittings — defer ALL fitting requests to `/fitting`
