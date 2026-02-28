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
  - userdata/pilots/{active_pilot}/profile.md
  - userdata/pilots/{active_pilot}/skills.json
data_sources:
  - userdata/pilots/{active_pilot}/ships.md
  - reference/pve-intel/cache/INDEX.md
  - reference/archetypes/INDEX.md
  - reference/mechanics/missiles.json
  - reference/mechanics/projectile_turrets.json
  - reference/mechanics/laser_turrets.json
  - reference/mechanics/hybrid_turrets.json
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

1. Parse mission name and level from capsuleer input
2. Check `reference/pve-intel/cache/INDEX.md` for exact match
3. If no cache hit, search wiki via Special:Search (see below)
4. Filter results to mission pages only (ignore player guides, ship articles, lore)
5. If **0 variants** found → report "no mission intel found" and ask for clarification
6. If **1 variant** found → proceed with that variant
7. If **2+ variants** found → use `AskUserQuestion` to let capsuleer choose:

```json
{
  "question": "Multiple variants found for {mission}. Which one?",
  "options": [
    {"label": "{Mission} - {Faction} L{N}", "description": "Tank {damage}, Deal {weakness}"},
    {"label": "{Mission} - {Faction2} L{N}", "description": "Tank {damage2}, Deal {weakness2}"}
  ]
}
```

**NEVER guess the faction or provide "generic" briefs** — wrong tank advice gets pilots killed. If the pilot confirms a faction but no mission-specific intel exists, provide generic faction guidance from `reference/mechanics/npc_damage_types.md` with a clear note that it is generic.

## Intel Retrieval Protocol

### Trusted Sources

**ONLY** use `wiki.eveuniversity.org` for external mission data. Never fetch from general web searches, other fan sites, forums, or Reddit.

### Keyword Extraction

Strip articles (a, an, the). Preserve original capitalization. Never add "mission", "Level X", or "EVE".

| Input | Keywords |
|-------|----------|
| "The Blockade L4 against Serpentis" | `Blockade` |
| "Gone Berserk level 3" | `Gone Berserk` |
| "Enemies Abound (2 of 5)" | `Enemies Abound` |

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

### Special:Search Method

URL pattern: `https://wiki.eveuniversity.org/Special:Search?search=KEYWORDS&fulltext=1`

| Mission Input | Search URL |
|---------------|-----------|
| "The Blockade L4" | `Special:Search?search=Blockade&fulltext=1` |
| "Gone Berserk level 3" | `Special:Search?search=Gone+Berserk&fulltext=1` |

Parse search results with WebFetch:
1. Identify title matches containing the mission name
2. Collect ALL faction/level variants (e.g., "The Blockade (Serpentis) (Level 4)", "The Blockade (Angel Cartel) (Level 4)")
3. Extract faction and level from each variant URL/title

### WebFetch Prompts

**Variant collection** (on search results page):
> "List all search results that are EVE mission pages for '{mission_name}'. For each, extract: mission name, faction, level, and URL. Ignore player guides, ship pages, and lore articles. Return as a structured list."

**Mission page extraction** (on individual mission page):
> "Extract mission intel: 1) Damage to tank (types and priority), 2) Damage to deal (enemy weakness), 3) EWAR types present, 4) Spawn/wave structure with triggers and distances, 5) Blitz strategy if available, 6) Objective. Return structured data only."

### Error Handling

| Situation | Action |
|-----------|--------|
| 0 variants from search | Report "no mission intel found for '{name}'" → ask capsuleer to clarify name/spelling |
| Wiki unavailable (WebFetch error) | Provide generic faction guidance from `npc_damage_types.md` with **clear warning** it is generic |
| 2+ variants found | Use `AskUserQuestion` with damage profile descriptions per variant |
| Cache write fails | Report error to capsuleer — **never present raw WebFetch output** as a brief |

### Cache File Format

**Naming convention:**

| Variant Type | Suffix | Example |
|-------------|--------|---------|
| Faction-specific | `_{faction}_l{N}` | `the_blockade_serpentis_l4.md` |
| No faction | `_l{N}` | `the_damsel_in_distress_l2.md` |
| DED complex | `_ded{N}` | `serpentis_phi_outpost_ded5.md` |

**File skeleton** (match existing cache files):
```markdown
# {Mission Name} (Level {N}) - {Faction}
Source: {wiki_url}

## Quick Reference
| Field | Value |
|-------|-------|
| Tank | {damage_types} |
| Deal | {weakness} |
| EWAR | {ewar_types} |
| Objective | {objective} |

## Blitz
1. {step}

## Spawns
### Wave 1 (on warp-in)
{ships with distances}
```

After writing, update `reference/pve-intel/cache/INDEX.md` under the appropriate faction heading.

## Fit Adaptation

### Adaptation Rules

- Start from pilot's existing fit for that hull (from ships.md). If no fit exists for this hull: check `reference/archetypes/INDEX.md` for a matching hull + activity archetype. If found, read the archetype YAML, use its `eft` block as baseline, apply `damage_tuning.overrides.{faction}` for hardener/drone/ammo swaps, and check `skill_requirements.required` against pilot tier. If no archetype match: build a basic fit matching the hull's role and pilot's module tier. Mark suggested fits as "(suggested fit — not from pilot's hangar)" in the brief.
- Swap hardeners to match enemy damage profile (from `reference/mechanics/npc_damage_types.md`)
- Swap drones to deal enemy's weakness — read `reference/mechanics/drones.json → enemy_recommendations.{faction}`
- Swap ammo/charges/crystals — read the weapon JSON (see Weapon JSON Lookup below) → `enemy_recommendations.{faction}`
- For fixed-damage weapons (lasers: EM/Therm, hybrids: Kin/Therm), note drone compensation in Tactical section
- Preserve pilot's module tier (T1/Meta/T2)
- OMIT rigs (pilots keep general-purpose rigs installed)
- Always EFT format in code fence. Adapt pilot's existing fit, don't invent new ones. EFT section order (blank-line separated): `[Ship, Name]` header → low slots → mid slots → high slots → drones (`Name x5`) → ammo (`Name x1000`). Omit rigs entirely. Never use `[Empty Low slot]` or similar — omit empty slots.

### Weapon JSON Lookup

Determine weapon system from the pilot's fit, then read the matching file:

| Weapon System | Reference File |
|---------------|----------------|
| Hybrid turrets (rails, blasters) | `reference/mechanics/hybrid_turrets.json` |
| Projectile turrets (autocannons, artillery) | `reference/mechanics/projectile_turrets.json` |
| Laser turrets (pulse, beam) | `reference/mechanics/laser_turrets.json` |
| Missiles (rockets, light missiles, etc.) | `reference/mechanics/missiles.json` |

### Validation Gate

Complete ALL steps before presenting ANY fit:

1. Read `reference/mechanics/drones.json → enemy_recommendations.{faction}` → select drones matching faction weakness. Cross-check against Deal recommendation.
2. Read the weapon JSON (see Weapon JSON Lookup) → `enemy_recommendations.{faction}` → select ammo matching faction weakness. Include primary + secondary ammo types with quantities in EFT output.
3. Verify swapped module names via `sde(action="item_info")` or `reference/fittings/MODULE_NAMES.md` — EVE module naming is inconsistent.
4. Validate the complete adapted fit via `fitting(action="calculate_stats", eft="...", use_pilot_skills=True)`. This calculates stats at the pilot's actual skill levels (falls back to All V if skills cache is unavailable). Check `metadata.skill_mode` to confirm which mode was used (`"pilot_skills"` or `"all_v"`). Check BOTH `validation_errors` AND `warnings` in response metadata:
   - **Ignorable:** `"Empty X slots: N of M unused"` — normal for partially-filled fits
   - **Actionable:** `item_class` / `allowed_classes` errors — modules in wrong slots. Fix EFT section order (must be lows → mids → highs)
   - **Actionable:** CPU/PG overload, unknown module types — downgrade or correct modules
4b. **Resource check:** If `metadata.skill_mode` = `"pilot_skills"`, CPU/PG values reflect the pilot's real skills — report them directly. If CPU or PG is overloaded (`overloaded: true`), the fit cannot be used as-is: identify the tightest module (propulsion mods and active tank are typically the largest consumers) and suggest downgrading to a compact/meta variant, or training the relevant fitting skill (CPU Management for CPU, Power Grid Management for PG). If `skill_mode` = `"all_v"` (skills cache miss), fall back to heuristic: warn if CPU/PG > 90% AND pilot < 60 days old.
5. If any actionable warning or error exists, fix the fit and re-validate. **Never present an unvalidated fit.**
6. **Skill gate (deterministic):** Read the pilot's skills from `userdata/pilots/{active_pilot}/skills.json` (loaded as prerequisite). Parse the `skills` object — keys are skill IDs (strings in JSON, convert to int), values are trained levels (int). Call `fitting(action="check_requirements", eft="...", pilot_skills={skill_id_int: level_int, ...})` — this returns `can_fly` (bool) and `missing_skills` (list with `skill_name`, `required` level, `current` level per entry). If `can_fly` is false, list the exact missing skills in the brief with required vs. current levels so the pilot knows exactly what to train. If `skills.json` is missing or unreadable (prerequisite load failed), fall back to `fitting(action="extract_requirements", eft="...")` and flag skills above level III for pilots < 60 days old (per profile.md `Capsuleer Since`).

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
