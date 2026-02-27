---
name: mission-brief
description: ARIA tactical intelligence briefing for Eve Online missions. Use for mission analysis, enemy intel, fitting advice, or combat preparation.
model: sonnet
category: tactical
triggers:
  - "/mission-brief"
  - "mission brief"
  - "I accepted a mission against [faction]"
  - "what should I know about [mission/faction]"
  - "prepare for [mission type]"
  - "fitting for [ship] running [mission]"
  - "fit for [mission]"
  - "[mission name] level [N]"
  - "[mission name] L[N]"
requires_pilot: true
prerequisite_files:
  - reference/mechanics/npc_damage_types.md
  - reference/mechanics/drones.json
  - reference/mechanics/missiles.json
  - reference/mechanics/projectile_turrets.json
  - reference/mechanics/laser_turrets.json
  - reference/mechanics/hybrid_turrets.json
data_sources:
  - userdata/pilots/{active_pilot}/profile.md
  - userdata/pilots/{active_pilot}/ships.md
  - reference/pve-intel/cache/INDEX.md
external_sources:
  - wiki.eveuniversity.org
---

# ARIA Mission Intelligence Module

## Response Format

Brief sections in order. Target 20-30 lines total.

1. **Quick Reference** — glanceable table (Tank, Deal, EWAR, Objective)
2. **Mission Fit** — EFT block adapted for this mission, ready to import
3. **Blitz** — 3-4 numbered steps (if available, else omit)
4. **Spawns** — wave structure with distances and triggers
5. **Tactical Notes** — EWAR warnings, special mechanics (omit if nothing noteworthy)

### What NOT to Include

| Omit | Why |
|------|-----|
| Verbose damage explanations | Quick reference table shows it |
| "Swap X for Y" prose | EFT fit is self-documenting |
| Risk assessment for trivial content | L2 in a Vexor needs no reassurance |
| Bounty estimates | Low value, often inaccurate |
| "Full brief available" offers | This IS the full brief |
| Multiple fitting options | One fit, adapted correctly |

## Mission Disambiguation

Many EVE missions exist in multiple variants (different factions, different levels). **Never assume** the faction or level.

When multiple variants match, present options and let the capsuleer choose. When zero results are found from wiki search, report clearly and ask for clarification — **NEVER guess the faction or provide "generic" briefs**. Wrong tank advice gets pilots killed. If the pilot confirms a faction but no mission-specific intel exists, provide generic faction guidance from `npc_damage_types.md` with a clear note that it is generic.

## Intel Retrieval Protocol

### Trusted Sources

**ONLY** use `wiki.eveuniversity.org` for external mission data. Never fetch from general web searches, other fan sites, forums, or Reddit.

### Cache-First Retrieval

All intel presented to the capsuleer MUST come from local cache files. Never present raw WebFetch data.

1. Extract keywords from mission name (strip articles, never add "mission"/"Level X"/"EVE")
2. Check `reference/pve-intel/cache/INDEX.md` for match — if found, skip to step 6
3. Search wiki via `Special:Search?search=KEYWORDS&fulltext=1`
4. Filter and disambiguate
5. **Populate cache** (REQUIRED before presenting):
   a. Fetch mission page from wiki.eveuniversity.org
   b. Extract intel using WebFetch prompt
   c. Write cache file to `reference/pve-intel/cache/{name}_{suffix}.md`
   d. Update `reference/pve-intel/cache/INDEX.md` under faction
   e. Confirm cache file exists before proceeding
6. Read from cache file → format and present to capsuleer

**Direct URL shortcut:** When name and level are known, try `wiki.eveuniversity.org/{Mission_Name}_(Level_{N})` first (replace spaces with underscores, title-case). Fall back to Special:Search on 404.

## Fit Adaptation

### Adaptation Rules

- Start from pilot's existing fit for that hull (from ships.md)
- Swap hardeners to match enemy damage profile (from `npc_damage_types.md`)
- Swap drones to deal enemy's weakness — read `drones.json → enemy_recommendations.{faction}`
- Swap ammo/charges/crystals — read the weapon JSON for pilot's weapon system → `enemy_recommendations.{faction}`
- For fixed-damage weapons (lasers: EM/Therm, hybrids: Kin/Therm), note drone compensation in Tactical section
- Preserve pilot's module tier (T1/Meta/T2)
- OMIT rigs (pilots keep general-purpose rigs installed)
- Always EFT format in code fence. Adapt pilot's existing fit, don't invent new ones.

### Validation Gate

Complete ALL steps before presenting ANY fit:

1. Read `drones.json → enemy_recommendations.{faction}` → select drones matching faction weakness. Cross-check against Deal recommendation.
2. Read the weapon JSON for pilot's weapon system → select ammo matching faction weakness. Include primary + secondary ammo types with quantities in EFT output.
3. Verify swapped module names via `sde(action="item_info")` or `reference/fittings/MODULE_NAMES.md` — EVE module naming is inconsistent.
4. Validate the complete adapted fit via `fitting(action="calculate_stats", eft="...")` — check for `validation_errors`, CPU/PG overload, or unknown module types.
5. If validation fails, fix the fit and re-validate. **Never present an unvalidated fit.**

### Gear Tier Validation

**CRITICAL:** Before recommending ANY fitting, you MUST:

1. **Read the pilot's ships.md** (`userdata/pilots/{active_pilot}/ships.md`)
2. **Check existing fittings** for module tier indicators:
   - T1 modules: "Mining Laser I", "Hammerhead I", "Armor Repairer I"
   - T2 modules: "Mining Laser II", "Hammerhead II", "Armor Repairer II"
   - Meta modules: Named variants like "Malkuth", "Arbalest", etc.
3. **Check profile.md** for explicit `module_tier` field if present
4. **Default to T1/Meta** when tier is uncertain or not explicitly T2

**Never recommend T2 modules/drones unless:**
- Pilot's existing fits show T2 usage, OR
- Profile explicitly states `module_tier: t2` or `t2_access: true`
