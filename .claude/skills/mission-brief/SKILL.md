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
data_sources:
  - userdata/pilots/{active_pilot}/profile.md
  - userdata/pilots/{active_pilot}/ships.md
  - reference/pve-intel/cache/INDEX.md
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

### Section Templates

**1. Quick Reference (always present)**
```
┌─────────────────────────────────────────┐
│  {MISSION NAME} L{N} vs {FACTION}       │
├──────────┬──────────────────────────────┤
│ Tank     │ {Primary} > {Secondary}      │
│ Deal     │ {Optimal damage type}        │
│ EWAR     │ {Types present or "None"}    │
│ Objective│ {One-line goal}              │
└──────────┴──────────────────────────────┘
```

**2. Mission Fit (always present)**
```
**Mission Fit** ({Hull} → {Faction})
\`\`\`
[{Hull}, {Mission Name} - {Faction}]

{High slots}

{Mid slots}

{Low slots}

{Drones}
\`\`\`
```

Include recommended ammo after the drone bay section:
```
Scourge Heavy Missile x1000
Nova Heavy Missile x500
```
Or for turrets:
```
Antimatter Charge M x3000
Null M x1500
```

**3. Blitz (when available)**
```
**Blitz**
1. {Step one}
2. {Step two}
3. {Step three}
```

Keep to 3-4 steps maximum. If no blitz exists, omit section entirely.

**4. Spawns (always present)**
```
**Spawns**
- **Initial (Xkm):** {count}x {ship types}
- **Wave 2 (trigger: {trigger}):** {count}x {ship types}
```

Use compact format. Distances in km. Note triggers inline.

**5. Tactical Notes (context-dependent)**
```
**Tactical**
- {EWAR warning if present}
- {Special mechanic if present}
- {Threat level assessment if non-obvious}
```

Omit if nothing noteworthy. L2 in a cruiser = obviously fine, don't state it.

### What NOT to Include

| Omit | Why |
|------|-----|
| Verbose damage explanations | Quick reference table shows it |
| "Swap X for Y" prose | EFT fit is self-documenting |
| Risk assessment for trivial content | L2 in a Vexor needs no reassurance |
| Bounty estimates | Low value, often inaccurate |
| "Full brief available" offers | This IS the full brief |
| Multiple fitting options | One fit, adapted correctly |

### Experience-Level Adaptation

The structure stays the same; verbosity changes:

| Element | New | Intermediate | Veteran |
|---------|-----|--------------|---------|
| Quick ref table | Full labels | Abbreviated | Abbreviated |
| EWAR explanation | In tactical notes, explained | One-liner | Omit if minor |
| Blitz steps | Include "why" | Steps only | Steps only |
| Spawn details | Full ship names | Abbreviated | Count + class |

**New pilots:** Explain EWAR effects and what triggers are. Full ship names in spawns.
**Veterans:** Omit minor EWAR. Spawns as "5x frigs, 3x dessies". Maximum compression.

## Mission Disambiguation

Many EVE missions exist in multiple variants (different factions, different levels). **Never assume** the faction or level.

### Input Parsing

Extract from user request:
- `mission_name`: Required (e.g., "Unauthorized Military Presence", "The Blockade")
- `level`: Optional (e.g., "L2", "level 2", "2") — normalize to integer
- `faction`: Optional (e.g., "Angel Cartel", "Serpentis", "against Angels")

### Disambiguation Flow

1. Parse input: extract mission_name, level, faction
2. Search local cache (INDEX.md) for mission_name
3. If not cached, search wiki for all variants (see §Intel Retrieval)
4. Filter variants by known level/faction
5. **0 variants** → Zero Results Clarification Protocol
6. **1 variant** → proceed to intel retrieval
7. **2+ variants** → present options via AskUserQuestion

### Disambiguation with AskUserQuestion

When multiple variants remain, let the capsuleer choose. Include damage profile summaries.

**RP-Adapted Prompts:**

| RP Level | Question Text |
|----------|---------------|
| `full` | "Multiple intelligence operations match this designation. Which theater requires tactical analysis, Capsuleer?" |
| `on` | "Multiple intel files found for this mission. Which variant do you need?" |
| `off` | "Found multiple versions of this mission. Which one?" |

**AskUserQuestion Structure:**
```json
{
  "questions": [{
    "question": "[RP-appropriate question text]",
    "header": "Mission",
    "options": [
      {"label": "Angel Cartel L2", "description": "Exp/Kin damage, target painters"},
      {"label": "Blood Raiders L2", "description": "EM/Therm damage, neuts/tracking disrupt"},
      {"label": "Serpentis L2", "description": "Kin/Therm damage, sensor damps"}
    ],
    "multiSelect": false
  }]
}
```

### Edge Cases

| Scenario | Behavior |
|----------|----------|
| User specifies level but not faction | Show all factions at that level |
| User specifies faction but not level | Show all levels for that faction |
| Only 1 variant exists in EVE | Proceed without disambiguation |
| Wiki has no data for specified combo | Note gap, offer closest alternative or use faction defaults |
| User's faction differs from mission | Normal - pilots run missions against various factions |

## Intel Retrieval Protocol

### Trusted Sources

**ONLY** use `wiki.eveuniversity.org` for external mission data. Never fetch from general web searches, other fan sites, forums, or Reddit.

### Keyword Extraction

Before searching, extract minimal keywords from the mission name:

1. Strip common articles: "the", "a", "an"
2. Keep all other significant words
3. Preserve capitalization

| Mission Name | Keywords |
|--------------|----------|
| The Blockade | `Blockade` |
| Listening Post | `Listening Post` |
| Break Their Will | `Break Their Will` |
| The Mordus Headhunters | `Mordus Headhunters` |

**Never add to searches:** "mission", "Level X", "L2", "EVE", "EVE Online" — these break wiki search.

### Cache-First Retrieval

All intel presented to the capsuleer MUST come from local cache files. Never present raw WebFetch data.

1. Extract keywords from mission name (strip articles, never add "mission"/"Level X"/"EVE")
2. Check `reference/pve-intel/cache/INDEX.md` for match → if found, skip to step 6
3. Search wiki via `Special:Search?search=KEYWORDS&fulltext=1`
4. Filter and disambiguate (see §Disambiguation)
5. **Populate cache** (REQUIRED before presenting):
   a. Fetch mission page from wiki.eveuniversity.org
   b. Extract intel using WebFetch prompt
   c. Write cache file to `reference/pve-intel/cache/{name}_{suffix}.md`
   d. Update `reference/pve-intel/cache/INDEX.md` under faction
   e. Confirm cache file exists before proceeding
6. Read from cache file → format and present to capsuleer

**Direct URL shortcut:** When name and level are known, try `wiki.eveuniversity.org/{Mission_Name}_(Level_{N})` first (replace spaces with underscores, title-case). Fall back to Special:Search on 404.

### Special:Search Method

**URL Pattern:**
```
https://wiki.eveuniversity.org/Special:Search?search=KEYWORDS&fulltext=1
```

**Examples:**
| Mission | Search URL |
|---------|------------|
| Listening Post | `Special:Search?search=Listening+Post&fulltext=1` |
| The Blockade | `Special:Search?search=Blockade&fulltext=1` |
| Gone Berserk | `Special:Search?search=Gone+Berserk&fulltext=1` |

**Result Parsing:**
1. Look for "Page title matches" section (highest relevance)
2. Mission pages may have format: `Mission_Name_(Faction)_(Level_X)` or just `Mission_Name`
3. **Collect ALL matching results** — do not pick one yet
4. Extract faction and level from each page title
5. Build variant list: `[{faction, level, url, cached: false}, ...]`

Wiki uses inconsistent naming across missions — search is more reliable than constructing URLs.

### WebFetch Prompts

**For variant collection (search results):**
```
List ALL mission variants found in these search results. For each, extract:
- Full page title
- Faction name (e.g., "Angel Cartel", "Serpentis", "Guristas")
- Mission level (1, 2, 3, 4, or 5)
- Page URL path

Include EVERY faction and level combination. Do not filter or select "best" match.
```

**For mission page content (after disambiguation):**
```
Extract mission intel: enemy faction, damage types dealt by enemies,
recommended tank resistances, optimal damage to deal, wave structure,
spawn triggers, EWAR present, total bounties, blitz options, and any
special warnings or mechanics.
```

### Error Handling

| Situation | Response |
|-----------|----------|
| 0 variants found | **DO NOT GUESS** — use Zero Results Clarification below |
| Wiki unavailable | Use faction quick reference from `npc_damage_types.md`, advise retry later |
| 2+ variants after filtering | Use AskUserQuestion with damage profile descriptions |
| Selected variant not in cache | Populate cache (step 5), then present from cache (step 6) |
| Cache write fails | Report error, do NOT present raw WebFetch data |

### Zero Results Clarification

**CRITICAL:** When wiki search returns no results, NEVER guess the faction or provide "generic" briefs. Wrong tank advice gets pilots killed.

**Step 1:** Report clearly: `No intel found for "{mission_name}" in the EVE University database.`

**Step 2:** Ask for clarification via AskUserQuestion. Adapt faction options to pilot's region:
- Gallente space: Serpentis, Rogue Drones, Mercenaries
- Caldari space: Guristas, Rogue Drones, Mercenaries
- Amarr space: Blood Raiders, Sansha, Rogue Drones
- Minmatar space: Angel Cartel, Rogue Drones, Mercenaries

```json
{
  "questions": [{
    "question": "Could you double-check the mission name? (Exact spelling from your journal helps.) If the name is correct, which faction are you fighting?",
    "header": "Mission",
    "options": [
      {"label": "Let me check the name", "description": "I'll verify the exact mission name from my journal"},
      {"label": "{Region faction 1}", "description": "{damage profile}"},
      {"label": "{Region faction 2}", "description": "{damage profile}"},
      {"label": "{Region faction 3}", "description": "{damage profile}"}
    ],
    "multiSelect": false
  }]
}
```

**Step 3:** If faction selected, provide generic faction guidance (tank/deal/EWAR from `npc_damage_types.md`) but clearly note: "No mission-specific intel available. This is generic faction guidance."

### Cache File Format

**Filename:** `{mission_name_snake_case}_{suffix}.md`

| Content Type | Suffix | Example |
|--------------|--------|---------|
| Agent missions | `_l{N}` | `listening_post_l2.md` |
| Faction-variant missions | `_{faction}_l{N}` | `the_blockade_serpentis_l1.md` |
| DED sites | `_ded{N}` | `mul_zatah_monastery_ded4.md` |
| Unrated sites | `_unrated` | `desolate_site_unrated.md` |
| Expeditions | `_expedition` | `mare_sargassum_expedition.md` |

**Template:**
```markdown
# {Mission Name} (Level {N}) - {Enemy Faction}
Source: {wiki_url}

## Quick Reference
| Field | Value |
|-------|-------|
| Tank | {Primary} > {Secondary} |
| Deal | {optimal_damage} |
| EWAR | {ewar_types or "None"} |
| Objective | {one_line_goal} |

## Drones
<!-- REQUIRED: Look up reference/mechanics/drones.json → enemy_recommendations.{faction} -->
| Size | Drone | Damage |
|------|-------|--------|
| Light | {light_drone} | {damage_type} |
| Medium | {medium_drone} | {damage_type} |

## Weapon Ammo
<!-- REQUIRED: Look up appropriate weapon JSON file → enemy_recommendations.{faction} -->
| Weapon Type | Primary Ammo | Damage | Secondary Ammo |
|-------------|--------------|--------|----------------|
| {weapon_type} | {primary_ammo} | {damage_type} | {secondary_ammo} |

## Blitz
<!-- Omit section if no blitz available -->
1. {step_one}
2. {step_two}
3. {step_three}

## Spawns
- **Initial ({distance}km):** {count}x {ship_class}
- **Wave 2 (trigger: {trigger}):** {count}x {ship_class}

## Tactical
<!-- Omit section if nothing noteworthy -->
- {ewar_warning_if_present}
- {special_mechanic_if_present}
```

**INDEX.md Update:**
Add entry under the appropriate faction section:
```markdown
- [{Mission Name} L{N}]({filename}.md) - {damage_dealt}, deal {optimal}
```

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

## Behavior

- Check pilot profile for operational constraints before recommending fittings
- Reference faction ship progression from `reference/ships/{faction}_progression.md`
- Warn about mission mechanics that could result in ship loss

### Contextual Suggestions

After providing a mission brief, suggest ONE related command when contextually relevant:

| Context | Suggest |
|---------|---------|
| Capsuleer needs a ship fit | "For a complete fitting, try `/fitting`" |
| Mission involves travel to risky space | "I can assess the route with `/threat-assessment`" |
| Capsuleer just completed mission | "Log it with `/journal mission` to track progress" |

Don't add suggestions to every brief — only when the capsuleer would clearly benefit.

### Persona Adaptation

This skill supports persona-specific overlays. When active persona has an overlay file, load additional context from:

```
personas/{active_persona}/skill-overlays/mission-brief.md
```

If no overlay exists, use the default (empire) framing.
