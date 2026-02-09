# Skill-Aware Fit Selection Proposal

**Status:** ✅ COMPLETE (2026-02-02)
**Completed:** Archetype structure, MCP fitting actions (check_requirements, extract_requirements), module/skill tier definitions, stats caching CLI, omega/T2 consistency validation

---

## Implementation Summary

All 5 ROI items from the plan have been implemented:

| Item | Implementation |
|------|----------------|
| omega_required flag | Validator consistency check added in `validator.py` |
| Tier renaming | Already done - files use t1/meta/t2_budget/t2_optimal |
| Primary resists derivation | Integrated into `fit update-stats` command |
| Stats caching in fit YAML | New `aria-esi fit update-stats` CLI command |
| Tank type classification | Integrated from `tank_classifier.py` |

### New CLI Commands

```bash
# Update stats for a single archetype
aria-esi fit update-stats vexor/pve/missions/l2/t1 --dry-run

# Update all archetypes for a hull
aria-esi fit update-stats --hull vexor

# Run fit validation
aria-esi fit validate vexor/pve/missions/l2/t1
```

### Files Modified

- `src/aria_esi/commands/fit.py` - Added `update-stats` and `validate` commands
- `src/aria_esi/archetypes/loader.py` - Added `update_archetype_stats()` YAML writer
- `src/aria_esi/archetypes/validator.py` - Added omega/T2 consistency validation

---

## Executive Summary

This proposal extends the Archetype Fittings Library with **pilot-aware fit selection**. Fits are organized by progression tier (T1 → Meta → T2 Budget → T2 Optimal) with machine-readable metadata. A selection algorithm filters fits by pilot eligibility (deterministic skill checks + alpha/omega status) and optionally matches against mission requirements. The result: pilots see only fits they can fly, with risk-appropriate options for their activity.

**Key changes from original archetype proposal:**

| Aspect | Original Proposal | This Proposal |
|--------|-------------------|---------------|
| Tier naming | low/medium/high/alpha | T1/meta/t2_budget/t2_optimal |
| Tier meaning | Pilot skill level | Module progression |
| Selection logic | Manual tier matching | Deterministic eligibility check |
| Alpha handling | Separate alpha.yaml files | `omega_required` flag + filtering |
| Mission matching | Not addressed | Damage type + level-based filtering |
| Tank handling | Not addressed | Type-aware thresholds (active/buffer/passive) |
| Presentation | Single fit recommendation | Recommended (single) or Efficient/Premium (multiple) |

**Goals:**

1. Don't show fits the pilot can't fly
2. Don't waste veteran time with entry-level fits
3. Match fits to mission requirements when context is known
4. Present risk-appropriate options (cheap vs expensive)

---

## Problem Statement

The current approach shows all fits regardless of pilot capability:

- A 2M SP alpha sees T2 fits they literally cannot use
- A 100M SP omega wades through T1 fits they'd never fly
- No connection between mission requirements and fit recommendations
- No risk/reward framing for fit selection

---

## Proposed Solution

### Progression Tiers

Organize fits by **module progression**, not pilot skill labels:

| Tier | Description | Typical Modules | Omega Required |
|------|-------------|-----------------|----------------|
| `t1` | Strict Tech 1 | T1 modules, rigs, drones | No |
| `meta` | Common meta modules | Named meta variants, accessible on regional market | No |
| `t2_budget` | Essential T2, gaps filled with meta | Core T2 (weapons, tank), meta utility | Yes |
| `t2_optimal` | Full T2/faction performance | T2 everything, faction where it matters | Yes |

**Key insight:** A given archetype may have 1-4 fits across this spectrum. Not every tier is required. A simple hull might only need T1 and T2 optimal. A progression-friendly hull might have all four.

### Metadata Schema

Each fit includes machine-readable metadata for selection:

```yaml
archetype:
  hull: Vexor
  tier: t2_budget              # Progression tier
  omega_required: true         # Hard filter for clone status (T2 modules or omega-only hulls)

eft: |
  [Vexor, L2 Mission - T2 Budget]
  ...

# Skill requirements - dynamically extracted, cached here for reference
# Authoritative source: fitting(action="extract_requirements", eft=...)
skill_requirements:
  - Gallente Cruiser III
  - Drones V
  - Medium Drone Operation IV
  - Drone Interfacing III

# Performance stats (from EOS)
stats:
  # Tank profile
  ehp: 18500
  tank_type: active            # active | buffer | passive
  tank_regen: 85               # Sustained tank in EHP/s (active/passive only, 0 for buffer)

  # Resist profile for mission matching
  # primary_resists: damage types where resist >= 60% (derived from resists{})
  # Algorithm: [type for type in resists if resists[type] >= 60]
  primary_resists: [thermal, kinetic]
  resists:                     # Full resist profile (percentages)
    em: 45
    thermal: 72
    kinetic: 68
    explosive: 50

  # Damage profile
  dps_total: 420
  primary_damage: [thermal, kinetic]   # Drone/weapon damage types
  dps_by_type:                 # For missions with specific weaknesses
    thermal: 280
    kinetic: 140

  capacitor_stable: true

  # Cost estimation (from local Jita market cache)
  # Refreshed during fit validation via: market(action="valuation", items=modules, region="jita")
  estimated_isk: 35000000
  isk_updated: "2026-01-24"    # When price was last computed

  # Validation metadata
  validated_date: "2026-01-24"
  eos_version: "2548611"
```

### Selection Algorithm

```
INPUT: pilot_skills, clone_status, archetype_path, [mission_context]

1. Load all fits from archetype_path

2. For each fit:
   a. If clone_status == "alpha" AND fit.omega_required == true:
      → REJECT (alpha cannot use T2 modules or omega-only hulls)

   b. Run deterministic skill check via EOS/MCP:
      can_fly = fitting(action="check_requirements",
                        eft=fit.eft,
                        pilot_skills=pilot_skills)
      If not can_fly:
      → REJECT (missing skills)

   c. Add to eligible_fits[]

3. If mission_context provided:
   a. Get mission profile: damage_types[] and level (see "Mission Data Availability")
   b. Verify fit resists match mission damage types:
      fit.stats.primary_resists intersects mission.damage_types
   c. Verify fit meets level-based tank threshold (see Tank Threshold Logic below)
   d. Verify fit damage output matches mission weaknesses (optional):
      fit.stats.primary_damage intersects mission.damage_to_deal

4. Sort eligible_fits by tier (t1 < meta < t2_budget < t2_optimal)

5. Select fits to present:
   - If only ONE fit eligible:
     → Present as RECOMMENDED (no dual framing)
   - If multiple fits eligible:
     → EFFICIENT: Lowest estimated_isk from eligible set
     → PREMIUM: Highest tier (best performance) from eligible set

OUTPUT: { recommended: Fit } | { efficient: Fit, premium: Fit }
```

### Tank Threshold Logic

Tank adequacy depends on tank type:

```
FUNCTION meets_tank_threshold(fit, mission_level):
  thresholds = LEVEL_THRESHOLDS[mission_level]

  SWITCH fit.tank_type:
    CASE "active":
      RETURN fit.tank_regen >= thresholds.regen_ehps
    CASE "passive":
      RETURN fit.tank_regen >= thresholds.regen_ehps
    CASE "buffer":
      RETURN fit.ehp >= thresholds.buffer_ehp
```

**Rationale:** Buffer tanks trade sustained regen for raw EHP. A buffer fit with 25k EHP can survive L2 missions by killing NPCs before buffer depletes, even though it has 0 EHP/s regen.

### Presentation Framing

When presenting fits to a pilot:

**Single Eligible Fit (Recommended):**
> "This is the fit you can fly for this activity. Estimated cost: 25M ISK."

No dual framing—presenting identical fits as "Efficient" and "Premium" would be confusing.

**Multiple Eligible Fits:**

*Efficient Option:*
> "This fit handles the mission with acceptable risk. Estimated cost: 12M ISK. If you lose it, you're not out much."

*Premium Option:*
> "This fit clears faster and tanks harder. Estimated cost: 45M ISK. Better ISK/hour, but more ISK at stake if things go wrong."

---

## Implementation Components

| Component | Status | Notes |
|-----------|--------|-------|
| Fit eligibility check | **Buildable** | Add `check_requirements` action to fitting MCP |
| Alpha/omega detection | **Exists** | ESI character public info |
| Tank/DPS stats generation | **Exists** | EOS `calculate_stats` |
| Tank type classification | **Buildable** | Derive from fit: has repper/booster → active; has shield extender/armor plate only → buffer; passive shield regen → passive |
| Skill requirements extraction | **Buildable** | Add `extract_requirements` action to fitting MCP; cache results in fit YAML |
| ISK estimation | **Exists** | `market(action="valuation")` against local Jita cache |
| Primary resists derivation | **Trivial** | Filter `resists{}` for values >= 60% |
| Mission damage type matching | **Buildable** | EVE Uni Wiki templates provide damage types |
| Mission level thresholds | **Buildable** | Use level as intensity proxy (see research) |

### New MCP Actions

Add to `fitting` dispatcher:

```python
# Check if pilot can fly a fit
fitting(action="check_requirements",
        eft="[Vexor, ...]",
        pilot_skills={"Drones": 5, "Gallente Cruiser": 3, ...})
# Returns: { can_fly: bool, missing_skills: [...] }

# Extract skill requirements from fit
fitting(action="extract_requirements",
        eft="[Vexor, ...]")
# Returns: { skills: ["Drones V", "Gallente Cruiser III", ...] }
```

### CLI Commands

```bash
# Select fits for a pilot
uv run aria-esi fit select vexor/pve/missions/l2 --pilot <character_id>

# Select with mission context
uv run aria-esi fit select vexor/pve/missions/l2 --pilot <id> --mission "Enemies Abound"

# Check if pilot can fly a specific fit
uv run aria-esi fit check vexor/pve/missions/l2/t2_budget --pilot <id>

# Refresh ISK estimates for all fits in an archetype
uv run aria-esi fit refresh-prices vexor/pve/missions/l2
```

### Skill Requirements Workflow

Skill requirements are extracted dynamically and cached in fit YAML:

```
1. During fit validation:
   a. Call fitting(action="extract_requirements", eft=fit.eft)
   b. EOS returns list of skills with minimum levels
   c. Write skill_requirements[] to fit YAML

2. During fit selection:
   a. Call fitting(action="check_requirements", eft=fit.eft, pilot_skills={...})
   b. EOS compares pilot skills against fit requirements
   c. Returns { can_fly: bool, missing_skills: [...] }
```

**Why cache in YAML?** The cached `skill_requirements` field is for human reference and debugging. The authoritative check is always `fitting(action="check_requirements")` which computes requirements fresh from EFT.

**Why not just use cached requirements?** EOS may update skill calculations between versions. Fresh extraction ensures accuracy.

### ISK Estimation Workflow

Fit prices are computed from local Jita market cache:

```
1. During fit validation (manual or CI):
   a. Parse EFT to extract module list
   b. Call market(action="valuation", items=modules, region="jita")
   c. Write estimated_isk and isk_updated to fit YAML

2. Staleness check (optional, at selection time):
   a. If isk_updated > 24 hours old, warn but continue
   b. User can run `fit refresh-prices` to update
```

**Data source:** Local Jita market cache (Fuzzwork or ESI snapshot). No live API calls during fit selection—prices are pre-computed.

**Staleness tolerance:** 24 hours. EVE market prices for common modules rarely swing >10% daily. For high-value fits (>100M ISK), warn if prices are stale.

---

## Migration from Original Proposal

The existing archetype structure remains valid. Changes:

| Original | New |
|----------|-----|
| `low.yaml` | `t1.yaml` |
| `medium.yaml` | `meta.yaml` |
| `high.yaml` | `t2_optimal.yaml` |
| `alpha.yaml` | Remove; use `omega_required: false` on t1/meta |

Add `t2_budget.yaml` where appropriate (T2 weapons + meta utility).

### File Rename Map

```
l2/low.yaml    → l2/t1.yaml
l2/medium.yaml → l2/meta.yaml
l2/high.yaml   → l2/t2_optimal.yaml
l2/alpha.yaml  → (delete, t1.yaml has omega_required: false)
```

Add new metadata fields to each file:
- `omega_required` (true for T2 modules or omega-only hulls)
- `stats.tank_type` (active/buffer/passive)
- `stats.tank_regen` (sustained EHP/s, 0 for buffer)
- `stats.primary_resists` (derived: resists >= 60%)
- `stats.primary_damage` (for mission matching)
- `stats.estimated_isk` (from local Jita market cache)
- `stats.isk_updated` (timestamp for staleness tracking)

---

## Mission Data Availability

### Research Findings (EVE University Wiki)

Investigation of EVE Uni Wiki mission pages revealed a clear pattern:

**Structured Data (Template:Missiondetails):**

| Field | Available | Format |
|-------|-----------|--------|
| Damage to deal | ✅ Yes | Icons (Kin, Th, EM, Ex) |
| Damage to resist | ✅ Yes | Icons (Kin, Th, EM, Ex) |
| EWAR types | ✅ Yes | Text |
| Web/Point | ✅ Yes | Boolean |
| DPS numbers | ❌ No | Not in template |
| Tank requirements | ❌ No | Not in template |

**Unstructured Data (Body Text):**

Some missions include DPS numbers in prose, but inconsistently:

| Mission | Data Found |
|---------|------------|
| Sansha's Nation Neural Paralytic Facility | "~700 DPS EM/Thermal" |
| Evolution | "4,000-6,000 DPS" |
| Angel Extravaganza (L4) | "Explosive 49-55%/Kinetic 22-28%" |
| The Damsel in Distress (L4) | "incoming DPS is very high" (qualitative only) |

**Conclusion:** Damage TYPE is reliably available via wiki templates. Damage AMOUNT is not—it appears inconsistently in body text with no standard format.

### Revised Approach: Type + Level Matching

Instead of per-mission DPS thresholds (which don't exist in community sources), use:

1. **Damage type matching** (reliable, from wiki templates)
2. **Mission level as intensity proxy** (general thresholds)

**Level-Based Tank Thresholds:**

| Level | Typical Incoming DPS | Active/Passive (EHP/s) | Buffer (EHP) |
|-------|---------------------|------------------------|--------------|
| L1 | 20-50 | 15+ | 8,000+ |
| L2 | 50-150 | 50+ | 20,000+ |
| L3 | 150-400 | 150+ | 45,000+ |
| L4 | 300-800+ | 300+ | 80,000+ |

*Note: These are conservative estimates. Specific missions vary. The system errs toward "fit is adequate" rather than "fit is optimal."*

*Buffer EHP thresholds assume the pilot can clear the mission before depleting buffer. They're calibrated for typical mission completion times (10-20 minutes) with appropriate DPS output.*

**Mission Profile Schema:**

```yaml
# reference/pve-intel/profiles/{mission_name}_l{N}.yaml
mission:
  name: "The Damsel in Distress"
  level: 4
  faction: "Mercenaries"  # For standing implications

  # From EVE Uni Wiki template (reliable)
  damage_to_resist: [kinetic, thermal]
  damage_to_deal: [kinetic, thermal]
  ewar: [web, target_painter]

  # NOT included: specific DPS numbers (unreliable/unavailable)
```

**Fit Matching Logic:**

```
IF fit.primary_resists ∩ mission.damage_to_resist ≠ ∅
   AND fit.tank_regen >= LEVEL_THRESHOLDS[mission.level]
THEN fit is adequate for mission
```

This approach:
- Uses data that actually exists (damage types)
- Avoids per-mission DPS curation that would require manual research
- Provides reasonable safety margins via level-based thresholds
- Can be refined later if authoritative DPS data emerges

### Sources

- [Template:Missiondetails](https://wiki.eveuniversity.org/Template:Missiondetails) - Mission infobox structure
- [Template:Damage to resist](https://wiki.eveuniversity.org/index.php?title=Template:Damage_to_resist) - Faction damage lookup
- [The Damsel in Distress (Level 4)](https://wiki.eveuniversity.org/The_Damsel_in_Distress_(Level_4)) - Example mission page
- [Angel Extravaganza (Level 4)](https://wiki.eveuniversity.org/Angel_Extravaganza_(Level_4)) - Example with damage percentages

---

## Future Work

### Per-Mission DPS Data

The current approach uses mission level as an intensity proxy. If authoritative per-mission DPS data becomes available (e.g., from systematic testing or community databases), the system can be extended:

```yaml
# Optional refinement to mission profile
mission:
  dps_incoming:
    sustained: 450        # Average DPS when managing aggro
    burst: 800            # Peak DPS if all waves triggered
    damage_split:         # For precise resist optimization
      kinetic: 0.55
      thermal: 0.45
```

**Deferred** until reliable data source identified. Level-based thresholds provide adequate safety margins for v1.

### Regional Meta Fits

Some meta modules are more available in certain regions (Gallente Navy near Dodixie, Caldari Navy near Jita). The system should accommodate regional fit variants.

**Deferred** to avoid premature complexity.

### Live Market Pricing

Replace `estimated_isk` with real-time market lookup:

```python
market(action="valuation", items=fit.modules, region="jita")
```

**Buildable now**, integrate when base system stable.

---

## Success Criteria

1. **Eligibility accuracy:** 100% of "can fly" determinations match EOS simulation
2. **Alpha filtering:** No omega-required fits shown to alpha clones
3. **SP efficiency:** Pilots >50M SP never see T1 fits when T2 eligible
4. **Presentation clarity:** Single fit → "Recommended"; multiple fits → "Efficient/Premium"
5. **Stats accuracy:** Tank/DPS stats within 5% of EOS output
6. **Price freshness:** `estimated_isk` reflects Jita prices within 24 hours
7. **Response time:** Fit selection completes in <2 seconds

---

## Relationship to Archetype Library Proposal

This proposal **extends** the Archetype Fittings Library, not replaces it. The directory structure, manifest files, and shared configuration from the original proposal remain valid.

**Additive changes:**
- Tier renaming (skill-based → progression-based)
- New metadata fields per fit
- Selection algorithm implementation
- MCP/CLI integration for pilot-aware queries

The original proposal focused on **organizing fits**. This proposal focuses on **selecting the right fit for a pilot**.

---

## Summary

| Aspect | Before | After |
|--------|--------|-------|
| Fit organization | By skill tier (low/medium/high) | By progression tier (t1/meta/t2_budget/t2_optimal) |
| Pilot matching | Manual tier selection | Deterministic eligibility check |
| Alpha handling | Separate files | `omega_required` flag + automatic filtering |
| Tank evaluation | Not considered | Type-aware thresholds (active/buffer/passive) |
| Mission context | Not considered | Damage type + level threshold matching |
| Skill requirements | Not extracted | Dynamic extraction via EOS, cached in YAML |
| Presentation | Single fit | Recommended (single) or Efficient/Premium (multiple) |
| Risk framing | None | ISK at risk vs ISK/hour trade-off |
| Price data | Not tracked | Local Jita market cache with staleness tracking |

This system ensures pilots see only fits they can fly, filtered further by mission requirements when known, with clear risk/reward framing for their choice.
