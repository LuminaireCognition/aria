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
data_sources:
  - userdata/pilots/{active_pilot}/profile.md
  - userdata/pilots/{active_pilot}/ships.md
  - reference/pve-intel/INDEX.md
  - reference/mechanics/npc_damage_types.md
  - reference/mechanics/drones.json
  - reference/mechanics/missiles.json
  - reference/mechanics/projectile_turrets.json
  - reference/mechanics/laser_turrets.json
  - reference/mechanics/hybrid_turrets.json
external_sources:
  - wiki.eveuniversity.org
---

# ARIA Mission Intelligence Module

## Purpose
Provide tactical briefings for security missions including enemy intelligence, recommended loadouts, and combat strategies. Works for all empire navy agents (Federation Navy, Caldari Navy, Republic Fleet, Imperial Navy) and other mission-giving corporations.

## Trigger Phrases
- "mission brief"
- "I accepted a mission against [faction]"
- "what should I know about [mission/faction]"
- "prepare for [mission type]"

## Response Format

The brief follows a strict information hierarchy optimized for in-game usability:

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. QUICK REFERENCE                                              │
│    Glanceable table: Tank | Deal | EWAR | Objective             │
│    "I'm in warp, what do I need to know?"                       │
├─────────────────────────────────────────────────────────────────┤
│ 2. MISSION FIT (EFT block)                                      │
│    Ready-to-import fitting adapted for this specific mission    │
│    Copy → Paste → Undock                                        │
├─────────────────────────────────────────────────────────────────┤
│ 3. BLITZ (if available)                                         │
│    3-4 numbered steps for speed-runners                         │
├─────────────────────────────────────────────────────────────────┤
│ 4. SPAWNS                                                       │
│    What you'll face, distances, wave structure                  │
├─────────────────────────────────────────────────────────────────┤
│ 5. TACTICAL NOTES                                               │
│    EWAR warnings, triggers, special mechanics                   │
└─────────────────────────────────────────────────────────────────┘
```

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

**Fit Adaptation Rules:**
- Start from pilot's existing fit for that hull (from ships.md)
- Swap hardeners to match enemy damage profile
- Swap drones to match enemy weakness (from drones.json)
- Swap ammo/charges/crystals to match enemy weakness (from weapon JSON files)
- Preserve pilot's module tier (T1/Meta/T2)
- OMIT rigs (pilots keep general-purpose rigs installed)

**Ammo Section (always present for turret/missile fits):**
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

## Enemy Faction Data

> **Reference:** See `reference/mechanics/npc_damage_types.md` for complete faction damage profiles, tank priorities, and EWAR types.

This skill file has `reference/mechanics/npc_damage_types.md` listed in `data_sources` - load it when generating mission briefs to get accurate damage/tank recommendations.

## Data Sources
- **Primary:** Check `reference/pve-intel/` for cached intel (authoritative)
- **Secondary:** Fetch from wiki.eveuniversity.org using protocol below
- **Index:** See `reference/pve-intel/INDEX.md` for available intel
- **Fitting Format:** See `.claude/skills/fitting/EFT-FORMAT.md` for EFT spec

## Mission Disambiguation Protocol

Many EVE missions exist in multiple variants (different factions, different levels). When a capsuleer requests a mission brief, **never assume** the faction or level - gather all variants and disambiguate.

### Input Parsing

Extract from user request:
- `mission_name`: Required (e.g., "Unauthorized Military Presence", "The Blockade")
- `level`: Optional (e.g., "L2", "level 2", "2")
- `faction`: Optional (e.g., "Angel Cartel", "Serpentis", "against Angels")

### Disambiguation Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: Parse User Input                                        │
├─────────────────────────────────────────────────────────────────┤
│ Extract: mission_name, level (optional), faction (optional)     │
│ Normalize level formats: "L2", "level 2", "lvl 2" → 2           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: Search for ALL Variants                                 │
├─────────────────────────────────────────────────────────────────┤
│ A. Search local cache (INDEX.md) for mission_name               │
│ B. Search wiki for mission_name (collect ALL level/faction)     │
│ Combine results into variant list                               │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 3: Filter by Known Parameters                              │
├─────────────────────────────────────────────────────────────────┤
│ If level specified → filter to that level only                  │
│ If faction specified → filter to that faction only              │
│ Result: filtered_variants list                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 4: Disambiguate or Proceed                                 │
├─────────────────────────────────────────────────────────────────┤
│ 0 variants → Use faction quick reference, note data is generic  │
│ 1 variant  → Proceed directly to intel retrieval                │
│ 2+ variants → Present options via AskUserQuestion (see below)   │
└─────────────────────────────────────────────────────────────────┘
```

### Disambiguation with AskUserQuestion

When multiple variants remain after filtering, use `AskUserQuestion` to let the capsuleer choose. Include damage profile summaries to help identification.

**Option Format:**
```
"{Faction} L{N} ({damage_dealt} damage)"
```

**Examples:**
- "Angel Cartel L2 (Exp/Kin damage)"
- "Blood Raiders L2 (EM/Therm damage)"
- "Guristas L3 (Kin/Therm damage, ECM)"

**RP-Adapted Prompts:**

| RP Level | Question Text |
|----------|---------------|
| `full` | "Multiple intelligence operations match this designation. Which theater requires tactical analysis, Capsuleer?" |
| `moderate` | "Multiple intel files found for this mission. Which variant do you need?" |
| `lite`/`off` | "Found multiple versions of this mission. Which one?" |

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

### Variant Collection WebFetch Prompt

When searching the wiki for variants, use this prompt:

```
List ALL variants of this mission found in search results. For each variant, extract:
- Faction name
- Mission level (1, 2, 3, 4, or 5)
- Page URL

Format as a list. Include every faction and level combination found.
```

### Edge Cases

| Scenario | Behavior |
|----------|----------|
| User specifies level but not faction | Show all factions at that level |
| User specifies faction but not level | Show all levels for that faction |
| Only 1 variant exists in EVE | Proceed without disambiguation |
| Wiki has no data for specified combo | Note gap, offer closest alternative or use faction defaults |
| User's faction differs from mission | Normal - pilots run missions against various factions |

### Why Disambiguation Matters

1. **Accuracy:** Different factions deal different damage types - wrong intel = wrong tank
2. **Efficiency:** Avoids wasted wiki fetches for wrong variant
3. **UX:** Capsuleer picks from clear options rather than re-requesting
4. **RP Coherence:** Intelligence agencies track multiple simultaneous operations

## GalNet Intelligence Network Protocol

### Trusted Source Policy

**CRITICAL:** For external mission intelligence, ONLY use `wiki.eveuniversity.org`.

**Why this restriction:**
- EVE University Wiki is a trusted, community-maintained resource
- Consistent formatting enables reliable data extraction
- Limits exposure to prompt injection attacks from untrusted sources
- MediaWiki structure is deterministic and well-documented

**NEVER fetch mission data from:**
- General web searches
- Other EVE fan sites
- Forum posts or Reddit
- Any source other than wiki.eveuniversity.org

### Keyword Extraction

Before searching, extract minimal keywords from the mission name:

**Rules:**
1. Strip common articles: "the", "a", "an"
2. Keep all other significant words
3. Preserve capitalization

**Examples:**
| Mission Name | Keywords |
|--------------|----------|
| The Blockade | `Blockade` |
| Listening Post | `Listening Post` |
| Break Their Will | `Break Their Will` |
| The Mordus Headhunters | `Mordus Headhunters` |

**CRITICAL - Never add these to searches:**
- "mission" - breaks wiki search
- "Level X" or "L2" etc. - breaks wiki search
- "EVE" or "EVE Online" - unnecessary noise

The wiki search works best with just the mission name keywords.

### Data Retrieval Protocol

Follow this sequence when capsuleer requests mission intel.

**CRITICAL: Cache-First Pattern**
All mission intel presented to the capsuleer MUST come from local cache files.
Never present data directly from a WebFetch response. If the mission is not
cached, populate the cache first, then read from cache to present.

```
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: Extract Keywords & Parse Parameters                     │
├─────────────────────────────────────────────────────────────────┤
│ Strip articles (the, a, an) from mission name                   │
│ Extract level if provided (normalize: "L2", "level 2" → 2)      │
│ Extract faction if provided                                     │
│ DO NOT add "mission", "Level X", or "EVE" to search keywords    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: Check Local Cache                                       │
├─────────────────────────────────────────────────────────────────┤
│ Search INDEX.md for mission name (case-insensitive)             │
│ If FOUND with matching level/faction → Skip to STEP 6           │
│ If NOT FOUND → Continue to STEP 3                               │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 3: Search Wiki for Variants                                │
├─────────────────────────────────────────────────────────────────┤
│ Use Special:Search with extracted keywords ONLY                 │
│ URL: wiki.eveuniversity.org/Special:Search?search=KEYWORDS      │
│ Collect ALL matching mission pages (all factions, all levels)   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 4: Filter & Disambiguate                                   │
├─────────────────────────────────────────────────────────────────┤
│ Apply level filter if user specified level                      │
│ Apply faction filter if user specified faction                  │
│ If 1 variant remains → Proceed to Step 5                        │
│ If 2+ variants remain → Use AskUserQuestion (see Disambig.)     │
│ If 0 variants → Use Zero Results Clarification Protocol         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 5: Populate Cache (REQUIRED before presenting)             │
├─────────────────────────────────────────────────────────────────┤
│ A. Fetch mission page from wiki.eveuniversity.org               │
│ B. Extract intel using WebFetch prompt (see below)              │
│ C. Write cache file: reference/pve-intel/cache/{name}_l{N}.md   │
│ D. Update INDEX.md with new entry under appropriate faction     │
│ E. Confirm cache file exists before proceeding                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 6: Present Intel FROM CACHE                                │
├─────────────────────────────────────────────────────────────────┤
│ Read the local cache file (reference/pve-intel/cache/{name})    │
│ Format and present intel to capsuleer                           │
│ Source of truth is ALWAYS the cache file, never raw WebFetch    │
└─────────────────────────────────────────────────────────────────┘
```

**Why cache-first?**
- Ensures caching happens as a prerequisite, not an afterthought
- Prevents "forgot to cache" failure mode
- Creates single source of truth for mission data
- Makes cache population structurally required, not behaviorally requested

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
3. **Collect ALL matching results** - do not pick one yet
4. Extract faction and level from each page title
5. Build variant list: `[{faction, level, url, cached: false}, ...]`

**Why collect all, not pick one?**
- User may not know the faction name (mission briefing just says "pirates")
- Presenting options with damage profiles helps user identify correct variant
- Avoids wasted fetches and re-requests

**Why not URL construction?**
EVE University Wiki uses inconsistent naming:
- Some missions: `Mission_Name_(Faction)_(Level_X)`
- Other missions: `Mission_Name` (covers all levels on one page)
- Faction names vary: "Angel Cartel", "Guristas Pirates", "Blood Raiders"

Search is more reliable than guessing the URL pattern.

### WebFetch Prompts

When using WebFetch to retrieve mission pages, use specific extraction prompts:

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
| 0 variants found | **DO NOT GUESS** - Use clarification protocol below |
| Wiki unavailable | Use faction quick reference, advise capsuleer to retry later |
| 2+ variants after filtering | Use AskUserQuestion with damage profile descriptions |
| Selected variant not in cache | Populate cache (Step 5), then present from cache (Step 6) |
| Cache write fails | Report error, do NOT present raw WebFetch data |
| Requested level/faction combo doesn't exist | Note gap, offer closest alternative or generic data |

### Zero Results Clarification Protocol

**CRITICAL:** When wiki search returns no results, NEVER guess the faction or provide "generic" briefs. Wrong tank advice gets pilots killed.

**Step 1: Report the failure clearly**
```
No intel found for "{mission_name}" in the EVE University database.
```

**Step 2: Ask for clarification using AskUserQuestion**
```json
{
  "questions": [{
    "question": "Could you double-check the mission name? (Exact spelling from your journal helps.) If the name is correct, which faction are you fighting?",
    "header": "Mission",
    "options": [
      {"label": "Let me check the name", "description": "I'll verify the exact mission name from my journal"},
      {"label": "Serpentis", "description": "Kin/Therm damage, sensor damps - Gallente space pirates"},
      {"label": "Rogue Drones", "description": "Omni damage, no EWAR - weak to EM"},
      {"label": "Mercenaries", "description": "Mixed damage, varies - weak to Thermal"}
    ],
    "multiSelect": false
  }]
}
```

**Adapt options to pilot's region/faction:**
- Gallente space: Serpentis, Rogue Drones, Mercenaries
- Caldari space: Guristas, Rogue Drones, Mercenaries
- Amarr space: Blood Raiders, Sansha, Rogue Drones
- Minmatar space: Angel Cartel, Rogue Drones, Mercenaries

**Step 3: Handle response**

| User Response | Action |
|---------------|--------|
| "Let me check the name" | Wait for corrected name, restart search |
| Faction selected | Provide faction damage profile (tank/deal/EWAR) but clearly note: "No mission-specific intel available. This is generic faction guidance." |

**Why this matters:**
- Federation Navy L2s can be Serpentis, Rogue Drones, Mercenaries, or EoM
- Guessing Serpentis when it's Rogue Drones = wrong tank = ship loss
- A round-trip to clarify is better than confident-but-wrong advice

### Cache File Format

When caching wiki-fetched intel, use this template:

**Filename:** `{mission_name_snake_case}_l{level}.md`
- Example: `listening_post_l2.md`, `the_blockade_serpentis_l1.md`
- For faction-variant missions, include faction: `{mission}_{faction}_l{N}.md`

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
<!-- Include this section if mission fits use turrets or missiles -->
| Weapon Type | Primary Ammo | Damage | Secondary Ammo |
|-------------|--------------|--------|----------------|
| {weapon_type} | {primary_ammo} | {damage_type} | {secondary_ammo} |

<!-- Note for lasers/hybrids if enemy weakness doesn't match weapon damage profile -->
<!-- Example: "Lasers deal EM/Thermal. Use Warrior drones for explosive damage against Angel Cartel." -->

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

## Behavior

### Pilot Resolution (First Step)
Before accessing any pilot files, resolve the active pilot path:
1. Read `userdata/config.json` → get `active_pilot` character ID
2. Read `userdata/pilots/_registry.json` → match ID to `directory` field
3. Use that directory for all pilot paths below (e.g., `userdata/pilots/{directory}/`)

**Single-pilot shortcut:** If config is missing, read the registry directly - if only one pilot exists, use that pilot's directory.

### General Behavior
- Always maintain ARIA persona (adapted to pilot's faction per their profile)
- **Intelligence Framing:** Follow the Intelligence Sourcing Protocol in CLAUDE.md - present all tactical data as live intelligence feeds, never archival records. Use faction-appropriate agency references (FNI/FIO for Gallente, CNI for Caldari, RFI/RSS for Minmatar, INI/MIO for Amarr, DED for pirate profiles).
- Check the pilot profile for operational constraints before recommending fittings
  - Path: `userdata/pilots/{active_pilot}/profile.md` (where `{active_pilot}` is the resolved directory)
- Reference appropriate faction ship progression from `reference/ships/[faction]_progression.md`
- Warn about any mission mechanics that could result in ship loss
- Offer to analyze specific fittings if requested

### Gear Tier Validation Protocol

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

**Validation failure = recommending gear the pilot cannot use.**

### Drone Recommendation Validation Protocol

**CRITICAL:** Before recommending ANY fitting with drones, you MUST:

1. **Read `reference/mechanics/drones.json`** - This is the authoritative source for drone damage types
2. **Look up `enemy_recommendations.{faction}`** - Get the correct drones for the target faction
3. **Cross-check drone damage vs "Deal" recommendation** - They MUST match
4. **If pilot's existing fit has wrong drones, explicitly note the swap**

**Drone Damage Types by Faction:**

| Drone Line | Damage Type | Use Against |
|------------|-------------|-------------|
| Warrior/Valkyrie/Berserker (Minmatar) | Explosive | Angel Cartel |
| Hobgoblin/Hammerhead/Ogre (Gallente) | Thermal | Serpentis, Mercenaries |
| Hornet/Vespa/Wasp (Caldari) | Kinetic | Guristas |
| Acolyte/Infiltrator/Praetor (Amarr) | EM | Blood Raiders, Sansha, Rogue Drones |

**Validation Checklist (must complete before presenting fit):**

```
□ Read drones.json
□ Identified target faction weakness: {damage_type}
□ Selected drones match weakness:
  - Light: {drone_name} ({damage_type})
  - Medium: {drone_name} ({damage_type})
□ If adapting existing fit: noted drone swap explicitly
```

**Failure mode this prevents:** Copying an existing fit optimized for one faction (e.g., Serpentis with thermal drones) and presenting it for a different faction (e.g., Angel Cartel requiring explosive drones) without adjusting the drone loadout.

### Weapon Ammo Recommendation Validation Protocol

**CRITICAL:** Before recommending ANY fitting with turrets or missiles, you MUST consult the appropriate weapon JSON file:

| Weapon Type | Reference File | Lookup Key |
|-------------|----------------|------------|
| Missiles (rockets, light, HAM, heavy, torpedoes, cruise) | `reference/mechanics/missiles.json` | `enemy_recommendations.{faction}` |
| Projectiles (autocannons, artillery) | `reference/mechanics/projectile_turrets.json` | `enemy_recommendations.{faction}` |
| Lasers (pulse, beam) | `reference/mechanics/laser_turrets.json` | `enemy_recommendations.{faction}` |
| Hybrids (blasters, railguns) | `reference/mechanics/hybrid_turrets.json` | `enemy_recommendations.{faction}` |

#### Missile Ammo Selection

1. **Read `reference/mechanics/missiles.json`**
2. **Look up `enemy_recommendations.{faction}.primary`** - Get the correct missile damage type
3. **Include both primary and secondary ammo types** for flexibility

**Missile Damage Types:**
| Ammo Name | Damage Type | Use Against |
|-----------|-------------|-------------|
| Mjolnir | EM | Blood Raiders, Sansha, Rogue Drones |
| Inferno | Thermal | Serpentis, Mercenaries |
| Scourge | Kinetic | Guristas, Mordu's Legion |
| Nova | Explosive | Angel Cartel |

#### Projectile Ammo Selection

1. **Read `reference/mechanics/projectile_turrets.json`**
2. **Look up `enemy_recommendations.{faction}`** - Get short/medium/long range recommendations
3. **Default to `short_range` for autocannons, `medium_range` for general use**

**Projectile Damage Types:**
| Ammo Name | Primary Damage | Use Against |
|-----------|---------------|-------------|
| EMP | EM | Blood Raiders, Sansha, Rogue Drones |
| Fusion | Explosive | Angel Cartel |
| Phased Plasma | Thermal | Serpentis, Mercenaries |
| Titanium Sabot | Kinetic | Guristas |

#### Laser Crystal Selection

1. **Read `reference/mechanics/laser_turrets.json`**
2. **Note:** Lasers deal EM/Thermal only - damage type cannot be changed
3. **If enemy is weak to Kinetic/Explosive, note in Tactical section that drones should handle damage matching**

**Laser Effectiveness:**
| Enemy Weakness | Laser Effective? | Recommendation |
|----------------|------------------|----------------|
| EM | Excellent | Lasers optimal |
| Thermal | Good | Lasers work well |
| Kinetic | Poor | Use kinetic drones |
| Explosive | Poor | Use explosive drones |

#### Hybrid Charge Selection

1. **Read `reference/mechanics/hybrid_turrets.json`**
2. **Note:** Hybrids deal Kinetic/Thermal only - damage type cannot be changed
3. **If enemy is weak to EM/Explosive, note in Tactical section that drones should handle damage matching**

**Hybrid Effectiveness:**
| Enemy Weakness | Hybrid Effective? | Recommendation |
|----------------|-------------------|----------------|
| Kinetic | Excellent | Hybrids optimal |
| Thermal | Excellent | Hybrids optimal |
| EM | Poor | Use EM drones |
| Explosive | Poor | Use explosive drones |

#### Ammo Validation Checklist (must complete before presenting fit)

```
□ Identified pilot's weapon system from existing fit
□ Read appropriate weapon JSON file
□ Identified target faction weakness: {damage_type}
□ For missiles/projectiles: Selected ammo matching weakness
  - Primary ammo: {ammo_name} ({damage_type})
  - Backup ammo: {ammo_name} ({damage_type})
□ For lasers/hybrids: Noted if weapon cannot deal optimal damage
  - If suboptimal: Added drone recommendation for damage matching
□ Included ammo quantities in EFT fit
```

**Failure modes this prevents:**
- Recommending Scourge missiles against Angel Cartel (should be Nova)
- Recommending Fusion ammo against Guristas (should be Titanium Sabot)
- Not noting that laser pilots need EM drones against Kinetic-weak factions
- Omitting ammo section entirely from EFT output

- **Brevity:** Target 20-30 lines total. The Response Format section defines the structure.
- **Fitting Output:** Always EFT format in code fence. Adapt pilot's existing fit, don't invent new ones.
- **No Rigs:** Omit rig section. Pilots keep general-purpose rigs; importing without rigs preserves them.

## Faction-Specific Fitting Guidance

When recommending mission ships, consider the pilot's faction:

| Faction | Primary Ships | Weapon System | Tank |
|---------|---------------|---------------|------|
| Gallente | Tristan→Vexor→Myrmidon | Drones/Hybrids | Armor |
| Caldari | Kestrel→Caracal→Drake | Missiles | Shields |
| Minmatar | Rifter→Rupture→Hurricane | Projectiles | Flex |
| Amarr | Punisher→Omen→Harbinger | Lasers | Armor |

Reference the appropriate faction's fitting files in `reference/ships/fittings/`.

## Experience-Based Adaptation

Check the pilot profile for **EVE Experience** level. The Response Format section includes an adaptation table. Key differences:

| Experience | Adaptation |
|------------|------------|
| **new** | Explain EWAR effects and counters. Explain what triggers are. Full ship names in spawns. |
| **intermediate** | One-liner EWAR notes. Triggers noted inline. Abbreviated ship classes. |
| **veteran** | Omit minor EWAR. Spawns as "5x frigs, 3x dessies". Maximum compression. |

**Example - EWAR for "new" pilots:**
> "Target Painters make your ship easier to hit by reducing your signature radius. Not dangerous alone, but increases incoming damage slightly."

**Example - EWAR for "veteran" pilots:**
> (Omit entirely for target painters - veteran knows they're negligible)

## Contextual Suggestions

After providing a mission brief, suggest ONE related command when contextually relevant:

| Context | Suggest |
|---------|---------|
| Capsuleer needs a ship fit | "For a complete fitting, try `/fitting`" |
| Mission involves travel to risky space | "I can assess the route with `/threat-assessment`" |
| Capsuleer just completed mission | "Log it with `/journal mission` to track progress" |

Don't add suggestions to every brief - only when the capsuleer would clearly benefit.

---

## Persona Adaptation

This skill supports persona-specific overlays. When active persona has an overlay file, load additional context from:

```
personas/{active_persona}/skill-overlays/mission-brief.md
```

If no overlay exists, use the default (empire) framing above.
