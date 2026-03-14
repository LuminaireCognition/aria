---
name: mission-brief
description: ARIA tactical intelligence briefing for Eve Online missions. Use for mission analysis, enemy intel, fitting advice, or combat preparation.
model: opus
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
injected_prerequisites:
  - reference/mechanics/npc_damage_types.md
  - reference/mechanics/drones.json
  - reference/mechanics/missiles.json
  - reference/mechanics/projectile_turrets.json
  - reference/mechanics/laser_turrets.json
  - reference/mechanics/hybrid_turrets.json
  - reference/pve-intel/INDEX.md
  - reference/pve-intel/missions/INDEX.md
  - reference/archetypes/INDEX.md
  - reference/archetypes/_shared/faction_tuning.yaml
prerequisite_files:
  - userdata/pilots/{active_pilot}/profile.md
  - userdata/pilots/{active_pilot}/skills.json
  - userdata/pilots/{active_pilot}/ships.md
data_sources:
  - reference/archetypes/{hull_path}     # loaded once hull is identified
external_sources:
  - wiki.eveuniversity.org
argument-hint: "<mission_name> [--level N]"
preferred_max_lines: 45
allowed-tools: [Read, Grep, Glob, Bash, WebFetch, WebSearch, "mcp__aria-universe__fitting", AskUserQuestion]
---

# Mission Brief

## Protocol

**Intel first, fitting second.** Present Quick Reference, Spawns, Blitz, and Tactical Notes immediately from prerequisite data and wiki. Append the Mission Fit after fitting engine validation. The user gets actionable intel while the fitting call runs.

## Intel Retrieval

1. Check `reference/pve-intel/missions/INDEX.md` for curated intel, then `reference/pve-intel/cache/INDEX.md` (either may not exist — treat failure as cache miss)
2. If miss → WebFetch `https://wiki.eveuniversity.org/Special:Search?search=KEYWORDS&fulltext=1` (strip articles from mission name, preserve capitalization)
3. Fetch the matching mission page and extract: damage profile, EWAR, spawns/waves, blitz, objective
4. On fetch failure: fall back to `npc_damage_types.md` for generic faction data, flag to user, continue to fitting

**Only** use `wiki.eveuniversity.org` for external data. Never guess the faction — if ambiguous or multiple variants exist, ask with `AskUserQuestion`.

## Spawn Data Guard

**If no cache file was Read AND no WebFetch response was received for this mission:**
- Present the Quick Reference table from `npc_damage_types.md` for the relevant faction
- State: "Detailed spawn data unavailable — check [EVE University Wiki](https://wiki.eveuniversity.org/) for wave/room details."
- Do **NOT** generate wave compositions, NPC ship names, trigger ships, or room layouts
- Proceed directly to fitting

This guard is absolute. Training-data recall of spawn details is unreliable and violates Verify Before Claiming.

## Response Format

Target 20–30 lines. Sections in order:

1. **Quick Reference** — table: Tank, Deal, EWAR, Objective
2. **Mission Fit** — single adapted EFT block in code fence
3. **Blitz** — numbered steps (omit if unavailable)
4. **Spawns** — wave structure with distances and triggers
5. **Tactical Notes** — EWAR warnings, special mechanics (omit if trivial)

Omit: verbose damage explanations, "swap X for Y" prose, bounty estimates, multiple fit options.

## Pilot Data Gate

Read ALL three `prerequisite_files` before generating any output:

1. `profile.md` — module tier, operational constraints
2. `skills.json` — pilot skill levels (required for fit validation and `check_requirements`)
3. `ships.md` — available hulls and existing fits

Items 1–3 are independent reads — issue them in a single parallel tool call. If `skills.json` is unavailable, warn the user and skip `check_requirements` rather than guessing skill levels.

## Ship Roster Check

Read `ships.md` before generating any fit. If the pilot lacks a viable hull:
- L1–L2: use available hull, warn if none suitable
- L3: warn if pilot only has frigates/destroyers
- L4: **strongly warn** — state "You need a battleship or HAC for L4 missions"

Never silently fit a hull the pilot doesn't own.

## Tank Hardener Reference (injected from faction_tuning.yaml)

!`uv run python3 ${CLAUDE_SKILL_DIR}/scripts/tank_summary.py`

## Archetype Selection

When selecting a fit archetype for a mission:

1. Check for exact tier match: `archetypes/{hull}/pve/missions/l{level}/`
2. If no match exists, check one tier below: `l{level-1}/`
3. **If using a lower-tier archetype, explicitly state this** in the response:
   "No L{level} archetype for {hull}. Adapting L{level-1} template."
4. When adapting upward, upgrade modules where pilot skills allow:
   - T1 → compact meta (always available)
   - T1 → T2 (check via `fitting(check_requirements)`)
   - Add rigs if slots are empty
5. If no archetype exists within 1 tier, recommend a more appropriate hull
   from the pilot's ship roster instead of using a 2+ tier mismatch.

## Fit Adaptation

1. **Source the baseline:** pilot's existing fit from `ships.md`, or archetype from `reference/archetypes/INDEX.md`. If neither, build from hull role. Mark non-hangar fits as "(suggested fit)".
2. **Tank what they DEAL:** Select hardeners for the mission faction using this authority order:
   1. **Mission cache** `Tank:` field (most specific — mission-verified data)
   2. **Archetype override** `damage_tuning.overrides.{faction}` (ship-specific tuning)
   3. **Injected tank reference** above (pre-rendered from `faction_tuning.yaml`)
   4. **`npc_damage_types.md`** "They Deal" column (general faction fallback)
   Use the highest-priority source available. The injected reference is authoritative for hardener module names — copy them verbatim, do not substitute.
3. **Deal what they're weak to:** Swap drones via `drones.json → enemy_recommendations.{faction}`. Swap ammo via the matching weapon JSON → `enemy_recommendations.{faction}`.
4. **Preserve pilot's module tier.** Default T1/Meta unless profile or existing fits indicate T2. Omit rigs.
5. **EFT format:** `[Ship, Name]` header → lows → mids → highs → drones → ammo. Omit empty slots and rigs.

## Fitting Validation

**Never fabricate stats.** Generate the EFT block, then validate:

- Call `fitting(action="calculate_stats", eft="...", use_pilot_skills=True)` and `fitting(action="check_requirements", eft="...", pilot_skills={...})` in parallel
- Present stats **only** from tool response. If the call fails: "Stats unavailable — verify in-game (Alt+F)."
- If CPU/PG overloaded: suggest downgrading the tightest module
- If `can_fly` is false: list missing skills with required vs current levels
- For ad-hoc fits (no archetype source): fix actionable errors and re-validate before presenting
- All rig slots are filled (rigs are cheap and always beneficial)
- All high slots have modules or are explicitly marked as empty
- If adapting an archetype, carry over rigs unless they conflict with the new tank type

## Injected Reference Data

<!-- Injected prerequisites loaded via !`cat` below. Agent-loaded prerequisites
     (pilot data in prerequisite_files) must still be read before producing output. -->

### Reference: NPC Damage Types (injected)
<!-- prerequisite: reference/mechanics/npc_damage_types.md -->
!`cat reference/mechanics/npc_damage_types.md`

### Reference: Drones (injected)
<!-- prerequisite: reference/mechanics/drones.json -->
!`cat reference/mechanics/drones.json`

### Reference: Missiles (injected)
<!-- prerequisite: reference/mechanics/missiles.json -->
!`cat reference/mechanics/missiles.json`

### Reference: Projectile Turrets (injected)
<!-- prerequisite: reference/mechanics/projectile_turrets.json -->
!`cat reference/mechanics/projectile_turrets.json`

### Reference: Laser Turrets (injected)
<!-- prerequisite: reference/mechanics/laser_turrets.json -->
!`cat reference/mechanics/laser_turrets.json`

### Reference: Hybrid Turrets (injected)
<!-- prerequisite: reference/mechanics/hybrid_turrets.json -->
!`cat reference/mechanics/hybrid_turrets.json`

### Reference: PVE Intel Index (injected)
<!-- prerequisite: reference/pve-intel/INDEX.md -->
!`cat reference/pve-intel/INDEX.md`

### Reference: Missions Index (injected)
<!-- prerequisite: reference/pve-intel/missions/INDEX.md -->
!`cat reference/pve-intel/missions/INDEX.md`

### Reference: Archetypes Index (injected)
<!-- prerequisite: reference/archetypes/INDEX.md -->
!`cat reference/archetypes/INDEX.md`

### Reference: Faction Tuning (injected)
<!-- prerequisite: reference/archetypes/_shared/faction_tuning.yaml -->
!`cat reference/archetypes/_shared/faction_tuning.yaml`

## Output Rules

- Keep response under 45 lines
- Append one-line `Sources:` footer. Tag spawn data provenance: `Wiki:fetched`, `Wiki:cached`, or `⚠ Spawn data: unavailable`
