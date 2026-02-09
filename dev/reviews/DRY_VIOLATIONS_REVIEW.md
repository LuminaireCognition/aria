# DRY Violations Review

Review of duplicated game mechanics data across the ARIA project. Follows the consolidation pattern established by `reference/mechanics/drones.md`.

**Review Date:** 2026-01-18

---

## Executive Summary

The drone damage type consolidation into `reference/mechanics/drones.md` successfully reduced errors and maintenance burden. This review identifies similar opportunities where verifiable EVE Online game mechanics are duplicated across multiple files.

| Priority | Violation | Files Affected | Estimated Lines | Status |
|----------|-----------|----------------|-----------------|--------|
| High | NPC Damage Types | 5 | ~60 | ✅ Resolved |
| High | Mining Ship Stats | 7 | ~60 | ✅ Resolved |
| Medium | Ammunition Mappings | 7 | ~60 | ✅ Resolved |
| Medium | Site Difficulty Tables | 3 | ~30 | ✅ Resolved |

---

## High Priority Violations

### 1. NPC Damage Types - ✅ RESOLVED

**Master Reference:** `reference/mechanics/npc_damage_types.md` (57 lines)

**Resolution Date:** 2026-01-18

**Changes Made:**
- Verified master reference against EVE University wiki (data is accurate)
- Updated 5 files to reference the master file instead of embedding duplicate tables
- Master reference already listed in mission-brief `data_sources`

**Files Updated:**
- `.claude/skills/mission-brief/SKILL.md` - Removed 38-line quick reference section
- `reference/mechanics/combat_anomalies.md` - Removed tank requirements table
- `reference/mechanics/l4_missions_guide.md` - Removed damage by faction table
- `reference/ships/fittings/myrmidon_l3_general.md` - Removed faction→drone mapping table
- `reference/ships/fittings/vexor_serpentis.md` - Removed Serpentis threat profile table

**Original Issue (for reference):**
Inline damage type tables were duplicated across multiple files, creating risk of inconsistent tank/damage recommendations.

---

### 2. Mining Ship Stats (Verbatim Duplication) - ✅ RESOLVED

**Master Reference Created:** `reference/mechanics/mining_ships.md`

**Resolution Date:** 2026-01-18

**Changes Made:**
- Created comprehensive `reference/mechanics/mining_ships.md` with wiki-verified data
- Updated 4 faction progression files to reference the master file
- Updated `reference/mechanics/fleet_mining.md` to reference the master file
- Updated fitting files (`procurer_fleet.md`, `retriever_solo.md`) to reference the master file
- Fixed incorrect ore hold values discovered during consolidation:
  - Covetor: 7,000 → 9,000 m³
  - Skiff: 15,000 → 18,500 m³
  - Mackinaw: 35,000 → 31,500 m³
  - Hulk: 8,500 → 11,500 m³
  - Procurer (in some files): 12,000 → 16,000 m³

**Files Updated:**
- `reference/ships/gallente_progression.md`
- `reference/ships/caldari_progression.md`
- `reference/ships/amarr_progression.md`
- `reference/ships/minmatar_progression.md`
- `reference/mechanics/fleet_mining.md`
- `reference/ships/fittings/procurer_fleet.md`
- `reference/ships/fittings/retriever_solo.md`

**Original Issue (for reference):**
The identical mining ship comparison table was copy-pasted across all faction progression files with several incorrect ore hold values.

---

## Medium Priority Violations

### 3. Ammunition Type Mappings - ✅ RESOLVED

**Master Reference Created:** `reference/mechanics/ammunition.md`

**Resolution Date:** 2026-01-18

**Changes Made:**
- Created comprehensive `reference/mechanics/ammunition.md` with wiki-verified data
- Structured by weapon type (missiles, projectiles, hybrids, lasers)
- Includes faction-to-ammo quick reference table for all weapon systems
- Added T2 ammo overview and quantity guidelines
- Updated 7 files to reference the master file instead of embedding duplicate tables

**Files Updated:**
- `reference/mechanics/l4_missions_guide.md` - Removed ammo selection table
- `reference/mechanics/battlecruiser_fitting.md` - Removed faction→ammo/drone table
- `reference/ships/fittings/drake_l3_general.md` - Removed missile ammo table
- `reference/ships/fittings/hurricane_l3_general.md` - Removed projectile ammo table
- `reference/ships/fittings/raven_l4_general.md` - Removed missile ammo table
- `reference/ships/fittings/caracal_l2_general.md` - Removed missile ammo table
- `reference/ships/fittings/kestrel_l1_combat.md` - Removed faction→rocket table

**Original Issue (for reference):**
Inline damage type → ammunition mappings were duplicated across multiple fitting and guide files, creating risk of inconsistent ammo recommendations.

---

### 4. Site Difficulty Tables - ✅ RESOLVED

**Authoritative Source:** `reference/mechanics/exploration_sites.md`

**Resolution Date:** 2026-01-18

**Changes Made:**
- Designated `reference/mechanics/exploration_sites.md` as the authoritative source for site types, difficulty ratings, ISK estimates, and loot tables
- Removed duplicate "Site Difficulty by Type" table from `reference/mechanics/hacking_guide.md`, replaced with reference
- Added explicit reference note in `.claude/skills/exploration/SKILL.md` pointing to authoritative source
- Skill file retains condensed prefix/faction tables for quick lookups (already listed in `data_sources`)

**Files Updated:**
- `reference/mechanics/hacking_guide.md` - Removed 9-line difficulty table, added reference
- `.claude/skills/exploration/SKILL.md` - Added reference note to authoritative source

**Original Issue (for reference):**
Exploration site difficulty information was duplicated across multiple files with different levels of detail, creating maintenance overhead.

---

## Proposed Consolidation Files

| New File | Consolidates | Replaces Content In | Status |
|----------|--------------|---------------------|--------|
| `reference/mechanics/mining_ships.md` | ORE ship stats, ore holds, yields | 7 files (faction progressions, fleet_mining, fittings) | ✅ Created |
| `reference/mechanics/ammunition.md` | Damage type → ammo for all weapons | l4_missions_guide, battlecruiser_fitting, 5 fitting files | ✅ Created |

**Note:** `reference/mechanics/npc_damage_types.md` already exists and is now consistently referenced.

---

## Consolidation Pattern (from drones.md)

The drone reference consolidation succeeded by following this pattern:

1. **Single Source of Truth:** One authoritative file
2. **Structured Data:** JSON companion for programmatic access
3. **Explicit References:** Other files note: `> **Reference:** See reference/mechanics/drones.md`
4. **Stable Data:** Contains verifiable game mechanics unlikely to change frequently
5. **Comprehensive:** Covers all variants (light/medium/heavy/sentry, all factions)

Apply this same pattern to the violations identified above.

---

## Implementation Priority

1. ~~**NPC Damage Types** - Highest impact, most widespread duplication~~ ✅ Done
2. ~~**Mining Ships** - Clean verbatim duplication, easy win~~ ✅ Done
3. ~~**Ammunition** - Requires new file creation, moderate effort~~ ✅ Done
4. ~~**Site Difficulty** - Lower priority, less critical data~~ ✅ Done

**All identified DRY violations have been resolved.**

---

## Verification Checklist

After consolidation, verify:

- [ ] All inline tables removed from secondary files
- [ ] Reference notes added pointing to master file
- [ ] Skills that need the data list the reference in `data_sources`
- [ ] No conflicting values remain across project
- [ ] JSON companion files created where programmatic access is useful

---

*Review conducted as part of ARIA data quality initiative.*
