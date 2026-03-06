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
  - reference/pve-intel/INDEX.md
  - reference/archetypes/INDEX.md
  - userdata/pilots/{active_pilot}/profile.md
  - userdata/pilots/{active_pilot}/skills.json
  - userdata/pilots/{active_pilot}/ships.md
data_sources:
  - reference/archetypes/{hull_path}     # loaded once hull is identified
external_sources:
  - wiki.eveuniversity.org
---

# ARIA Mission Intelligence Module

## Anti-Confabulation Gate: Two-Phase Output (BLOCKING)

**Phase 1 — Build:** Generate the adapted EFT block based on pilot roster, faction resistance profile, and archetype. Do NOT write any numerical stats (DPS, EHP, CPU, powergrid, resists).

**Phase 2 — Validate:** Call `fitting(action="calculate_stats", eft="...", use_pilot_skills=True)`. Present stats ONLY from the tool response, prefixed with "**Fitting engine:**". If the call fails, write: "Stats unavailable — verify in-game (Alt+F)."

**NEVER write Phase 2 content without completing the tool call.**

## Ship Roster Check (BLOCKING)

Before generating any fit, read `userdata/pilots/{active_pilot}/ships.md` and check if the pilot owns the recommended hull. If the hull is not in the roster:

| Mission Level | Minimum Hull Class | Action if Pilot Lacks Hull |
|---------------|-------------------|----------------------------|
| L1 | Frigate/Destroyer | Use pilot's available hull; warn if none suitable |
| L2 | Cruiser | Use pilot's available hull; warn if none suitable |
| L3 | Battlecruiser or well-fitted cruiser | **Warn explicitly** if pilot only has frigates/destroyers |
| L4 | Battleship or T2/faction cruiser | **Strongly warn** — L4s are not viable in T1 cruisers. State "You need a battleship or HAC for L4 missions" |

**Never silently generate a fit for a hull the pilot doesn't own without flagging the mismatch.**

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
2. Attempt to read `reference/pve-intel/cache/INDEX.md` (may not exist — this is normal). If readable, check for exact match
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

### Streamlined Retrieval (Deferred Caching)

Cache and wiki data are used inline — **no cache writes occur during queries**. Cache population is a separate concern handled outside the query path.

1. Read `reference/pve-intel/cache/INDEX.md` as a separate non-blocking read (this file is auto-generated and may not exist — treat failure as cache miss). Issue this read in its own tool call, NOT batched with other reads.
   - If hit → read the cache file. If the cache file referenced by INDEX is missing or unreadable, treat as a cache miss and fall through to step 2
2. If miss → WebFetch `Special:Search?search=KEYWORDS&fulltext=1` (keywords per extraction rules above)
3. Parse search results for the mission page URL matching the mission name and level
4. WebFetch the identified mission page URL — extract intel inline. Do NOT write a cache file.
5. If WebFetch fails with a non-404 error (timeout, 5xx, malformed response) → **abort intel retrieval**:
   - Present available intel from prerequisite data (`npc_damage_types.md` for faction damage profiles)
   - Flag the missing intel to the user with the failure reason
   - Do NOT retry within the same query — retries waste a full round (~25s)
   - Continue to the fitting phase
6. If the wiki page returns HTTP 200 but contains no parseable mission intel (disambiguation page, stub, redirect, or multi-part series index) → treat as unparseable:
   - Present available intel from prerequisite data (`npc_damage_types.md`)
   - Flag to the user: "Wiki page found but does not contain single-mission intel — using generic faction data"
   - Continue to the fitting phase

**NEVER write to `reference/pve-intel/cache/` during a mission-brief query.**

### Special:Search Fallback

URL pattern: `https://wiki.eveuniversity.org/Special:Search?search=KEYWORDS&fulltext=1`

Parse search results with WebFetch:
1. Identify title matches containing the mission name
2. Collect ALL faction/level variants
3. Extract faction and level from each variant URL/title

### WebFetch Prompts

**Mission page extraction** (on individual mission page):
> "Extract mission intel: 1) Damage to tank (types and priority), 2) Damage to deal (enemy weakness), 3) EWAR types present, 4) Spawn/wave structure with triggers and distances, 5) Blitz strategy if available, 6) Objective. Return structured data only."

**Variant collection** (on search results page):
> "List all search results that are EVE mission pages for '{mission_name}'. For each, extract: mission name, faction, level, and URL. Ignore player guides, ship pages, and lore articles. Return as a structured list."

### Error Handling

| Situation | Action |
|-----------|--------|
| 0 variants from search | Report "no mission intel found for '{name}'" → ask capsuleer to clarify name/spelling |
| Wiki unavailable (non-404 WebFetch error) | Present generic faction guidance from `npc_damage_types.md` with **clear warning** it is generic; continue to fitting phase |
| Unparseable wiki page (200 but no mission intel) | Present generic faction guidance from `npc_damage_types.md`; flag "wiki page found but not parseable"; continue to fitting phase |
| 2+ variants found | Use `AskUserQuestion` with damage profile descriptions per variant |

## Fit Adaptation

### Adaptation Rules

- Start from pilot's existing fit for that hull (from ships.md). If no fit exists for this hull: check `reference/archetypes/INDEX.md` for a matching hull + activity archetype. If found, read the archetype YAML, use its `eft` block as baseline, apply `damage_tuning.overrides.{faction}` for hardener/drone/ammo swaps, and check `skill_requirements.required` against pilot tier. After applying damage_tuning overrides, check the archetype YAML's `damage_tuning` section for CPU/PG warnings (in YAML comments or `notes.warnings`). If a warning provides a proactive fix (e.g., "swap module X → Y when CPU exceeds"), apply that fix to the adapted EFT BEFORE calling calculate_stats. If no archetype match: build a basic fit matching the hull's role and pilot's module tier. Mark suggested fits as "(suggested fit — not from pilot's hangar)" in the brief.
- Swap hardeners to match enemy damage profile (from `reference/mechanics/npc_damage_types.md`)
- Swap drones to deal enemy's weakness — read `reference/mechanics/drones.json → enemy_recommendations.{faction}`
- Swap ammo/charges/crystals — read the weapon JSON (see Weapon JSON Lookup below) → `enemy_recommendations.{faction}`
- For fixed-damage weapons (lasers: EM/Therm, hybrids: Kin/Therm), note drone compensation in Tactical section
- Preserve pilot's module tier (T1/Meta/T2)
- OMIT rigs (pilots keep general-purpose rigs installed)
- Always EFT format in code fence. Adapt pilot's existing fit, don't invent new ones. EFT section order (blank-line separated): `[Ship, Name]` header → low slots → mid slots → high slots → drones (`Name x5`) → ammo (`Name x1000`). Omit rigs entirely. Never use `[Empty Low slot]` or similar — omit empty slots.

### Weapon JSON Lookup

Determine weapon system from the pilot's fit, then use the matching reference (already loaded as prerequisite):

| Weapon System | Reference File |
|---------------|----------------|
| Hybrid turrets (rails, blasters) | `reference/mechanics/hybrid_turrets.json` |
| Projectile turrets (autocannons, artillery) | `reference/mechanics/projectile_turrets.json` |
| Laser turrets (pulse, beam) | `reference/mechanics/laser_turrets.json` |
| Missiles (rockets, light missiles, etc.) | `reference/mechanics/missiles.json` |

### Validation Gate

Complete ALL steps before presenting ANY fit. Track whether the fit was sourced from an archetype YAML (archetype-sourced) or generated ad-hoc (no archetype match in INDEX).

**Fit source tracking:** Set `archetype_sourced = true` if and only if an archetype YAML file was successfully read and used as the basis for the fit in the Fit Adaptation phase. If INDEX had no match, or INDEX matched but the YAML read failed, set `archetype_sourced = false`.

1. Read `reference/mechanics/drones.json → enemy_recommendations.{faction}` (already in context from prerequisites) → select drones matching faction weakness. Cross-check against Deal recommendation.
2. Read the weapon JSON (already in context from prerequisites — see Weapon JSON Lookup) → `enemy_recommendations.{faction}` → select ammo matching faction weakness. Include primary + secondary ammo types with quantities in EFT output.
3. Verify swapped module names via `sde(action="item_info")` or `reference/fittings/MODULE_NAMES.md` — EVE module naming is inconsistent.
4. **Parallel validation:** Call BOTH fitting tools in a single parallel tool call batch:
   - `fitting(action="calculate_stats", eft="...", use_pilot_skills=True)` — stats at pilot's actual skill levels (falls back to All V if skills cache is unavailable)
   - `fitting(action="check_requirements", eft="...", pilot_skills={"skill_id": level, ...})` — skill requirements check using pilot's `skills.json` (loaded as prerequisite). JSON keys MUST be strings (e.g., `{"3300": 4, "3301": 5}`); values are trained levels as integers.

   These two calls have no data dependency — both need only the EFT string and pilot skills. Issue them as parallel tool calls in a single round.

   **Recovery:** If `check_requirements` returns a validation or parsing error, retry once with all `pilot_skills` keys explicitly coerced to strings.

   **`calculate_stats` response checks:**
   - Check `metadata.skill_mode` to confirm which mode was used (`"pilot_skills"` or `"all_v"`)
   - Check BOTH `validation_errors` AND `warnings` in response metadata:
     - **Ignorable:** `"Empty X slots: N of M unused"` — normal for partially-filled fits
     - **Actionable:** `item_class` / `allowed_classes` errors — modules in wrong slots. Fix EFT section order (must be lows → mids → highs)
     - **Actionable:** CPU/PG overload, unknown module types — downgrade or correct modules
   - **Resource check:** If `metadata.skill_mode` = `"pilot_skills"`, CPU/PG values reflect the pilot's real skills — report them directly. If CPU or PG is overloaded (`overloaded: true`), the fit cannot be used as-is: identify the tightest module and suggest downgrading to a compact/meta variant, or training the relevant fitting skill (CPU Management for CPU, Power Grid Management for PG). If `skill_mode` = `"all_v"` (skills cache miss), fall back to heuristic: warn if CPU/PG > 90% AND pilot < 60 days old.

   **`check_requirements` response checks:**
   - Returns `can_fly` (bool) and `missing_skills` (list with `skill_name`, `required` level, `current` level per entry)
   - If `can_fly` is false, list the exact missing skills in the brief with required vs. current levels
   - If `skills.json` is missing or unreadable (prerequisite load failed), fall back to `fitting(action="extract_requirements", eft="...")` and flag skills above level III for pilots < 60 days old (per profile.md `Capsuleer Since`)

5. **Conditional re-validation (fit source dependent):**
   - **If `archetype_sourced = true`:** Skip the re-validation loop. Archetype fits are pre-validated; any issues from `calculate_stats` surface as warnings in the brief rather than triggering iteration. Present the fit directly.
   - **If `archetype_sourced = false` (ad-hoc fit):** If any actionable warning or error exists from step 4, fix the fit and re-validate. **Never present an unvalidated ad-hoc fit.** This loop may add 1-2 rounds but is the safety net for ad-hoc fits that are prone to module name hallucination and slot errors.

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
