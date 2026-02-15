# Min-Max Skill Planning Proposal

**Status:** READY FOR IMPLEMENTATION (2026-02-15) — All open decisions resolved (Q1-Q3)
**Related:** `skills()` MCP dispatcher, `fitting()` dispatcher, `/skillplan` skill, Easy 80% system

**Changelog:**
- **2026-02-15c:** Resolved Q3 (dependency injection target level) with S1 (minimum required level, placed in Phase 2 before dependent skill). Added `injected_prerequisite` scoring bucket. Expanded Cross-Phase Dependency Guarantee with orphan prerequisite definition and injection mechanics. Added `resolve_injected_prerequisites()` to Phase A. Added Golden Test 4 (Venture injection-heavy). All open decisions now resolved.
- **2026-02-15b:** Resolved Q2 (missing efficacy fallback) with per-role data threshold (S4 hybrid). Added Per-Role Data Threshold section to Phase 2 algorithm. Added `classify_role_strength()` to Phase A implementation plan. Updated risk mitigation for incomplete efficacy rules.
- **2026-02-15:** Synced with codebase post-cleanup. Fixed `1/rank` → `-rank` fallback inconsistency in Phase A.3. Added `validation.py` to Phase B modified files and "What Needs to Be Built" table. Added Q1 resolution to Open Decisions. Updated `ship_category_roles` limitation to note archetype library now covers destroyers/haulers. Added Sigil/Epithal to proposed hauler `example_ships`. Fixed skill name: "Armor Resistance Phasing" → "Resistance Phasing" (matching YAML). Annotated MULTIPLIER_SKILLS with exact 8-skill inventory. Added mtime-cache and SkillRequirementsResult model notes to viability table.
- **2026-02-08:** Review fixes applied. Added multi-role scoring rule, open decisions Q1-Q3.

---

## Executive Summary

Add role-scoped min-max skill planning to ARIA's skill system. Where the Easy 80% philosophy optimizes for *generalist efficiency* ("get 80% of everything for 20% of the time"), min-max planning optimizes for *role-specific maximization* ("get to 100% for this one role as fast as possible, and nothing else").

**Primary value:** Dedicated alt pilots and focused mains can get an ordered, prioritized training plan that takes them from zero to maximum effectiveness for a specific role, without wasting a single SP on irrelevant skills.

**Motivating example:** A player creating a dedicated Ark jump freighter pilot wants:
1. Phase 1 — *Get online*: The absolute minimum skills to sit in the ship (SDE prerequisites)
2. Phase 2 — *Get effective*: Skills that provide the biggest bang-per-SP for jump freighter operations
3. Phase 3 — *Get maximal*: Every remaining role-relevant skill trained to V

They do **not** want to train Drones, Gunnery, or any other skill that doesn't directly serve the JF hauler role.

---

## Problem Statement

### Current Limitations

ARIA's skill planning operates at three levels today:

| Tier | Philosophy | Scope | Weakness for Min-Maxers |
|------|-----------|-------|------------------------|
| **minimum** | Bare minimum to participate | Activity-specific (YAML) | No training order; no role scoping |
| **easy_80** | 80% effectiveness for 20% time | Ship + detected roles | Leaves 20% on the table; includes "nice to have" skills |
| **full** | All skills to V | Ship + detected roles | Trains irrelevant skills; no priority ordering |

### What Min-Maxers Actually Need

**Scenario 1: Dedicated Jump Freighter Pilot**
> Player asks: "Plan a dedicated Ark pilot from scratch."
> Current ARIA: Can show Easy 80% for the ship, but can't prioritize within the plan — Jump Drive Calibration V (massive jump range gain) is not distinguished from Evasive Maneuvering IV (minor agility). The pilot needs to know what to train *first* for maximum impact.

**Scenario 2: Dedicated Ratting Ishtar**
> Player asks: "I want to max out my Ishtar for null-sec ratting. What's the fastest path?"
> Current ARIA: Easy 80% plan shows Drone Interfacing IV. Min-maxer wants to know: "Train Drones V first (breakpoint: 5th drone), then Drone Interfacing to V (10%/level multiplier), then Heavy Drone Operation V..." — ordered by effectiveness gain per SP invested.

**Scenario 3: Fit-Specific Max Plan** *(future enhancement)*
> Player pastes an EFT fit: "Max out everything for this specific fit."
> Current ARIA: `fitting(action="extract_requirements")` returns all skills at V. No priority order. No phases. No distinction between "this skill gives you 10% more DPS" and "this skill saves 2% capacitor."

### The Gap

The infrastructure for min-max planning **largely exists** in fragments:

- **Role detection** identifies `drone_boat`, `armor_tank`, `jump_capable`, etc.
- **Multiplier skills** have per-level impact percentages and priority rankings
- **Breakpoint skills** identify non-linear unlock thresholds
- **Efficacy rules** define per-skill contributions to each role
- **Training time calculation** can compute exact SP/time costs

What's missing is the **orchestration layer** that combines these into a prioritized, phased, role-scoped training plan.

---

## Proposed Solution

### New Action: `minmax_plan`

Add a new action to the `skills()` dispatcher:

```python
skills(
    action="minmax_plan",
    item="Ark",                          # Ship, module, or activity
    roles=["jump_capable"],              # Optional: override detected roles (list)
    current_skills={"Drones": 4, ...},   # Optional: pilot's current skills
    attributes={"intelligence": 27, ...}, # Optional: character attributes
)
```

**Parameter details:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `item` | `str` | *required* | Ship name, module name, or activity |
| `roles` | `list[str] \| None` | `None` | Override auto-detected roles. Values must exist in `ship_efficacy_rules.yaml`. If `None`, uses `detect_ship_roles()` |
| `current_skills` | `dict \| None` | `None` | Current skill levels `{"Skill Name": level}`. When provided, completed skills are omitted, partially-trained skills start from current level, and empty phases are collapsed |
| `attributes` | `dict \| None` | `None` | Character attributes for training time calculation. Defaults to balanced 20/20/20/20/19 |

**Role validation:** The `roles` parameter accepts only values that exist as keys in `ship_efficacy_rules.yaml`. Invalid role names return an error listing valid options. This avoids an unconstrained taxonomy while allowing role composition via lists (e.g., `roles=["jump_capable", "navigation"]`).

### Output Structure: Phased Training Plan

```python
{
    "item": "Ark",
    "detected_roles": ["jump_capable", "hauler"],
    "phases": [
        {
            "phase": 1,
            "name": "Get Online",
            "description": "SDE prerequisites to board ship",
            "skills": [
                {
                    "skill_name": "Spaceship Command",
                    "from_level": 0,
                    "to_level": 5,
                    "training_seconds": 512001,
                    "training_formatted": "5d 22h",
                    "reason": "SDE prerequisite (rank 1)",
                    "scoring_bucket": "prerequisite",
                }
                # ... ordered by dependency chain (prerequisites first)
            ],
            "phase_total_seconds": 9175107,
            "phase_total_formatted": "106d 4h",
            "efficacy_at_phase_end": 38.0,
        },
        {
            "phase": 2,
            "name": "Get Effective",
            "description": "Breakpoints and multipliers ordered by impact tier, then by effectiveness/SP",
            "skills": [
                {
                    "skill_name": "Jump Drive Calibration",
                    "from_level": 1,
                    "to_level": 5,
                    "training_seconds": 4603500,
                    "training_formatted": "53d 6h",
                    "reason": "BREAKPOINT [critical]: +2 LY jump range per level",
                    "scoring_bucket": "breakpoint",
                    "impact_tier": "critical",
                },
                {
                    "skill_name": "Jump Fuel Conservation",
                    "from_level": 0,
                    "to_level": 4,
                    "training_seconds": 724080,
                    "training_formatted": "8d 9h",
                    "reason": "MULTIPLIER: 10% fuel reduction per level",
                    "scoring_bucket": "multiplier",
                    "effectiveness_per_sp": 0.00011,
                }
                # ...
            ],
            "phase_total_seconds": 6693740,
            "phase_total_formatted": "77d 11h",
            "efficacy_at_phase_end": 88.0,
        },
        {
            "phase": 3,
            "name": "Get Maximal",
            "description": "Remaining role-relevant skills to V",
            "skills": [
                # ...
            ],
            "phase_total_seconds": 16598700,
            "phase_total_formatted": "165d 19h",
            "efficacy_at_phase_end": 100.0,
        }
    ],
    "total_training_seconds": 32467547,
    "total_training_formatted": "349d 10h",
    "excluded_skills": [
        {"skill_name": "Drones", "reason": "Not in any detected role's efficacy rules"},
    ],
    "warnings": [],
}
```

### Phase Assignment Algorithm

Phase assignment is deterministic and follows explicit rules:

#### Phase 1: Get Online

**Definition:** The complete prerequisite tree returned by `sde(action="skill_requirements")`, at the exact levels the SDE specifies.

**Algorithm:**
1. Call `sde(action="skill_requirements", item=item)` to get `full_prerequisite_tree`
2. For each skill in the tree, set `target_level = required_level` from SDE
3. Order topologically (prerequisites before dependents)

**No additional skills are added in Phase 1.** This phase is purely "what does the game require to board/use this item." For the Ark, this includes Spaceship Command V, Industry V, Jump Drive Operation V, etc. — these are non-negotiable SDE requirements.

#### SDE Direct Requirement Inclusion Rule

**Skills in the item's `direct_requirements` are always role-relevant**, regardless of whether they appear in any role's `skills` list in `ship_efficacy_rules.yaml`.

**Rationale:** The SDE distinguishes between an item's *direct* requirements (the skills listed on the item's info panel) and their *transitive* prerequisites (skills needed to inject those). Direct requirements are the ship's hull skills and primary operational skills — they provide per-level bonuses specific to the ship and are always relevant for a min-max plan.

**Example for Ark:** The SDE returns three direct requirements:
- `Amarr Freighter IV` — hull skill, provides per-level freighter bonuses
- `Jump Freighters I` — hull skill, provides per-level JF bonuses
- `Jump Drive Calibration I` — already in `jump_capable` role

Without this rule, Amarr Freighter and Jump Freighters would be excluded (they aren't in any role's efficacy `skills` list). With this rule, they are automatically role-relevant and eligible for Phase 2 promotion and Phase 3 completion to V.

**Implementation:** `sde(action="skill_requirements")` returns both `direct_requirements` and `full_prerequisite_tree`. The algorithm uses `direct_requirements` to build the always-relevant set. Skills in this set that aren't already covered by a role's efficacy rules are placed in the `role_support` bucket with a default `per_level` of 0 (scored by rank; see Scoring section).

#### Phase 2: Get Effective

**Definition:** Role-relevant skills not in Phase 1, plus Phase 1 skills whose SDE-required level is below their role-optimal level, trained to their Phase 2 target. Ordered by scoring bucket priority, then by effectiveness/SP within each bucket.

**Algorithm:**
1. Build the role-relevant skill set:
   a. All skills from efficacy rules for detected roles
   b. All skills from the item's `direct_requirements` (per SDE Direct Requirement Inclusion Rule)
   c. Union of (a) and (b), deduplicated
2. Filter to skills NOT fully satisfied by Phase 1
3. For each skill, determine Phase 2 target:
   - Breakpoint skills: train to `breakpoint_level` (from `breakpoint_skills.yaml`)
   - Multiplier skills: train to IV
   - Other role skills: train to IV
4. Exclude any skill where Phase 1 already meets or exceeds the Phase 2 target
5. Classify each role as **strong** or **weak** (see Per-Role Data Threshold below)
6. Sort strong-role skills by scoring bucket priority (see Scoring section), then by effectiveness/SP within bucket
7. Append weak-role skills after all strong-role skills, ordered by rank ascending (faster to train first)

#### Per-Role Data Threshold

Each detected role is classified before Phase 2 ordering:

```python
MINIMUM_SCORED_SKILLS = 2  # At least 2 skills with per_level > 0

def classify_role_strength(role: str, efficacy_rules: dict) -> str:
    """Classify a role as 'strong' or 'weak' based on efficacy data coverage."""
    role_data = efficacy_rules["ship_roles"].get(role, {})
    scored_skills = [
        s for s in role_data.get("skills", [])
        if s.get("per_level", 0) > 0
    ]
    return "strong" if len(scored_skills) >= MINIMUM_SCORED_SKILLS else "weak"
```

**Strong roles** (>= 2 skills with `per_level > 0`) contribute to Phase 2 normally — their skills are scored by bucket priority and effectiveness/SP.

**Weak roles** (< 2 scored skills) have their skills included in the plan but placed *after* all strong-role skills in Phase 2, ordered by rank ascending (lower rank = faster to train = first). A warning is emitted:

```python
if weak_roles:
    warnings.append(
        f"Role(s) {weak_roles} have limited efficacy data. "
        f"Their skills appear in Phase 2 but without effectiveness-based ordering."
    )
```

**Rationale:** This per-role granularity avoids two failure modes: (1) a single sparse role degrading the ordering quality of a data-rich role (solved by scoring strong and weak roles independently), and (2) blocking the entire plan because one role lacks data (solved by always generating a plan). The threshold of 2 is the minimum needed for effectiveness/SP comparisons to be meaningful — with only 1 scored skill there is nothing to compare against.

**Edge case — all roles are weak:** The plan still generates. Phase 2 contains all role-relevant skills ordered by rank. The warning makes clear that ordering is by training speed, not effectiveness. This is strictly better than no plan (the user still gets role scoping and excluded-skill transparency) while being honest about the limitation.

**Phase 2 target of IV — design choice:** The IV ceiling for non-breakpoint skills is inherited from the Easy 80% observation that Level IV provides ~80% of the Level V bonus for ~20% of the SP cost. This is a reasonable default for Phase 2 ("Get Effective"), since Phase 3 ("Get Maximal") exists to take everything to V. For skills with linear per-level bonuses (e.g., Jump Fuel Conservation at 10%/level), the per-SP efficiency is identical at every level — the argument for stopping at IV is purely that V costs as much SP as I→IV combined, making it a diminishing-returns boundary. This is acknowledged as a design choice, not a min-max derivation.

**Split-skill handling:** A skill can span phases. Example: Amarr Freighter is required at IV by SDE (Phase 1), then V in Phase 3. The Phase 3 entry shows `from_level: 4, to_level: 5`.

#### Phase 3: Get Maximal

**Definition:** All remaining role-relevant skills trained to V.

**Algorithm:**
1. For every skill that appeared in Phase 1 or Phase 2, and whose current target is below V, add a Phase 3 entry for `from_level: current_target, to_level: 5`
2. Sort by effectiveness/SP (descending)

#### Cross-Phase Dependency Guarantee

Before emitting the plan, validate that every skill's prerequisites are satisfied by an earlier phase or an earlier entry within the same phase.

**Orphan prerequisites** are skills that:
1. Are NOT in the item's SDE prerequisite tree (not Phase 1)
2. Are NOT in any detected role's `skills` list (not role-relevant)
3. Are NOT in the item's `direct_requirements`
4. ARE required by a Phase 2 or Phase 3 skill as a training prerequisite

Common orphans include Power Grid Management (required by all shield_tank skills, Thermodynamics, Capacitor Management) and Science (required by Astrogeology, Astrometrics, Jump Drive Operation, Thermodynamics). These skills appear in zero role definitions but gate nearly half the roles in the system.

**Injection algorithm:**

```python
def resolve_injected_prerequisites(phase_skills: list, phase1_skills: dict) -> list:
    """
    Scan Phase 2/3 skills for unmet prerequisites. Inject orphans at minimum
    required level, placed immediately before the first skill that needs them.

    Orphan prerequisites do NOT appear in Phase 3 — they train to the minimum
    level needed and no further.
    """
    injected = {}  # skill_name -> {to_level, placed_before}

    for skill in phase_skills:
        for prereq_name, prereq_level in get_skill_prerequisites(skill.skill_name):
            # Already satisfied by Phase 1?
            if phase1_skills.get(prereq_name, 0) >= prereq_level:
                continue
            # Already a role skill in this phase?
            if any(s.skill_name == prereq_name for s in phase_skills):
                continue
            # Already injected at sufficient level?
            if injected.get(prereq_name, {}).get("to_level", 0) >= prereq_level:
                continue

            # Inject at minimum required level
            injected[prereq_name] = {
                "to_level": prereq_level,
                "placed_before": skill.skill_name,
                "scoring_bucket": "injected_prerequisite",
                "reason": f"Prerequisite for {skill.skill_name} (minimum level)",
            }

    # Recursively check injected skills' own prerequisites
    # (e.g., Electronics Upgrades III requires CPU Management II AND PGM II)
    resolve_injected_prerequisites(list(injected.values()), phase1_skills)

    return merge_injected_into_phase(phase_skills, injected)
```

**Key rules:**
- **Minimum level only.** An orphan trains to `max(required_level)` across all dependents in the plan. If Shield Management needs PGM III and Thermodynamics needs PGM IV, the orphan trains to IV.
- **No Phase 3 entry.** Orphan prerequisites have zero role efficacy. Training them beyond the minimum wastes SP, which violates min-max philosophy.
- **Placement is local.** The orphan appears immediately before the first skill that depends on it, within that skill's bucket position. This makes the training order self-documenting ("train Science IV *because* Astrogeology needs it").
- **Recursive resolution.** Injected orphans may themselves have prerequisites (e.g., Hacking requires Electronics Upgrades III, which requires CPU Management II and Power Grid Management II). The algorithm resolves transitively.
- **Orphans are neither excluded nor role-relevant.** They appear in the plan as `scoring_bucket: "injected_prerequisite"` but are not counted in the `excluded_skills` list (they ARE trained) and do not contribute to efficacy calculations (they have zero role effectiveness).

### current_skills Interaction

When `current_skills` is provided:

1. Each skill's `from_level` is set to `max(current_level, phase_start_level)` where `phase_start_level` is the level the skill would have at the end of the previous phase
2. Skills where `current_level >= target_level` are omitted entirely
3. Phases with zero remaining skills are omitted from output
4. `efficacy_at_phase_end` is recalculated against the role-scoped target, incorporating current skills as the baseline

**Example:** If a pilot already has Spaceship Command V, Industry V, and Navigation V, Phase 1 would show only the remaining prerequisites, with a shorter total time.

### Scoring: Category-Specific Buckets

The single `effectiveness_per_sp` scoring function is replaced with **category-specific scoring buckets** that are sorted independently and then merged in priority order.

#### Bucket Priority (Phase 2 ordering)

Skills within Phase 2 are ordered by bucket, then by within-bucket score:

| Priority | Bucket | Contains | Ordering Within Bucket |
|----------|--------|----------|----------------------|
| 1 | **breakpoint** | Skills from `breakpoint_skills.yaml` applicable to detected roles | By `impact` tier: `critical` > `high` > `medium`, then by rank ascending (faster to train first) |
| — | **injected_prerequisite** | Orphan prerequisites of breakpoint skills (see Cross-Phase Dependency Guarantee) | Immediately before the dependent skill within the breakpoint bucket |
| 2 | **multiplier** | Skills in `MULTIPLIER_SKILLS` applicable to detected roles | By `effectiveness_per_sp` descending |
| — | **injected_prerequisite** | Orphan prerequisites of multiplier skills | Immediately before the dependent skill within the multiplier bucket |
| 3 | **role_support** | Other skills from efficacy rules for detected roles | By `effectiveness_per_sp` descending |
| — | **injected_prerequisite** | Orphan prerequisites of role_support skills | Immediately before the dependent skill within the role_support bucket |

**`injected_prerequisite` placement rule:** An injected orphan prerequisite is placed immediately before the *first* skill that depends on it, within that skill's bucket position. If multiple skills in different buckets depend on the same orphan, the orphan is placed before the highest-priority dependent (i.e., it appears as early as needed). Injected prerequisites train to the **minimum level required** by any dependent skill in the plan — no Phase 3 entry is created for them. See "Cross-Phase Dependency Guarantee" for the full injection algorithm.

#### Effectiveness-Per-SP Calculation

For multiplier and role_support skills, the score is comparable *within* each bucket:

```python
def effectiveness_per_sp(skill_name: str, from_level: int, to_level: int, rank: int, role: str) -> float:
    """
    Score a skill by effectiveness gain per SP invested.

    Only comparable within the same scoring bucket.
    Higher score = train this first within the bucket.
    """
    sp_cost = calculate_sp_for_level(rank, to_level) - calculate_sp_for_level(rank, from_level)

    role_data = efficacy_rules["ship_roles"].get(role, {})
    skill_info = next((s for s in role_data.get("skills", []) if s["skill"] == skill_name), None)

    if skill_info:
        per_level = skill_info.get("per_level", 0)
    else:
        # Skill not in role efficacy rules (e.g., direct requirement hull skill).
        # Default to 0 — scored by rank fallback below.
        per_level = 0

    if per_level == 0:
        # Discrete/binary skills (per_level=0) and direct-requirement hull skills
        # can't be scored by effectiveness gain. Use negative rank as a sort key
        # to order by training speed (lower rank = faster = train first).
        # These skills sort AFTER all skills with real per_level scores within
        # the same bucket, because any positive effectiveness_per_sp beats a
        # negative tiebreaker. This is intentional: measurable bonuses should
        # train before unmeasured hull skills.
        return -rank

    levels_gained = to_level - from_level
    effectiveness_gain = per_level * levels_gained

    return effectiveness_gain / max(sp_cost, 1)
```

**Key design decisions:**
- **No cross-bucket comparison.** Breakpoints are always trained before multipliers, regardless of their per-SP efficiency. A critical breakpoint like Drones V (25% DPS gain) trains before Drone Interfacing IV (40% gain over 4 levels) because the breakpoint unlocks a discrete capability.
- **No synthetic weighting.** The old proposal used arbitrary constants (`25.0` for breakpoints, `1.2` for multiplicative). This design avoids magic numbers by sorting on separate axes.
- **`per_level` comparisons are within-bucket only.** Comparing "10% drone damage" to "2% turret RoF" is meaningless across roles, but within a single role's multiplier bucket (e.g., Drone Interfacing vs. Medium Drone Operation), both use the same metric (drone DPS contribution per level) and the comparison is valid.
- **`per_level: 0` fallback.** Skills with discrete effects (e.g., Exhumers, Resistance Phasing) and direct-requirement hull skills not in any role's efficacy rules score `-rank` instead of 0. This sorts them *after* all skills with measurable per-level bonuses within the same bucket (any positive score beats a negative tiebreaker), then orders among themselves by training speed (lower rank = less negative = first). This is intentional: measurable bonuses should train before unmeasured hull skills. Most `per_level: 0` skills are handled by the breakpoint bucket (Drones V, Cloaking IV, etc.) and never reach this fallback.

#### Phase 3 Ordering

Phase 3 uses simple `effectiveness_per_sp` across all remaining skills without bucket separation. At this stage all high-priority skills are done; the ordering optimizes "which last-mile skills give the most for their training time."


**Multi-role scoring rule:** When a skill appears in multiple active roles, compute `effectiveness_per_sp` using the maximum per-role `per_level` contribution for that skill. This keeps ordering conservative and prevents additive inflation across loosely related roles.
### Efficacy Calculation

**Definition:** 100% efficacy = all role-relevant skills at their Phase 3 target levels (V for most).

Efficacy at each phase boundary is calculated using a weighted-average function with:
- `skills_at_level`: the skill levels the pilot would have at the end of that phase
- `target_levels`: the Phase 3 target levels for all role-relevant skills
- `roles`: the detected roles

**Modification required:** The existing `calculate_efficacy()` in `tools_easy80.py` derives multiplier status from the hardcoded `MULTIPLIER_SKILLS` dict (8 skills: Drone Interfacing, Surgical Strike, etc.). This dict doesn't cover capital-specific multipliers like Jump Fuel Conservation or role-specific skills outside the original 8. For minmax planning, multiplier weight must be derived from the role's efficacy rules at runtime:

```python
# Current (Easy 80%): hardcoded multiplier detection
if skill in MULTIPLIER_SKILLS:
    weight = 3.0

# New (minmax): derive from role efficacy data
role_skills = union of all detected roles' skills lists
if skill in role_skills and role_skills[skill].get("multiplicative"):
    weight = 3.0
elif skill in role_skills:
    per_level = role_skills[skill].get("per_level", 0)
    weight = 1.0 + (per_level / 10.0)
else:
    weight = 1.0  # Direct-requirement or prerequisite skill
```

This is implemented as a new `calculate_minmax_efficacy()` function in `tools_minmax.py` rather than modifying the existing `calculate_efficacy()`, which continues to serve Easy 80% plans unchanged.

### Excluded Skills

**Definition:** A skill is excluded if it meets **all** of the following:
1. It is NOT in any detected role's `skills` list in `ship_efficacy_rules.yaml`
2. It is NOT in the item's `direct_requirements` (per the SDE Direct Requirement Inclusion Rule)
3. It is NOT an injected orphan prerequisite (per the Cross-Phase Dependency Guarantee)
4. It was added to the tree as a support skill (by Easy 80%), not as an SDE prerequisite

Skills in the SDE `full_prerequisite_tree` are never excluded — they are Phase 1 requirements. Skills in `direct_requirements` are never excluded — they are always role-relevant. Injected orphan prerequisites are never excluded — they are required to satisfy dependency chains (they appear in the plan as `scoring_bucket: "injected_prerequisite"`). Only support skills added beyond the SDE tree that don't match any detected role and aren't needed as prerequisites are excluded.

Excluded skills are reported in the output for transparency, so the user understands why certain skills were intentionally omitted.

**Example for Ark with `roles=["jump_capable", "hauler"]`:** Drones, Gunnery, and Shield Management would be excluded because they appear in neither the detected roles' efficacy rules nor the Ark's direct requirements.

---

## Concrete Example: Ark Jump Freighter Pilot

To ground the proposal, here's what a min-max plan for "dedicated Ark pilot" would produce. All training times verified against SDE (balanced 20/20/20/20/19 attributes, no implants).

**Detected roles:** `["jump_capable", "hauler"]` — `detect_ship_roles()` detects `jump_capable` from the jump freighter ship list and `hauler` from the new hauler role's `example_ships`. This requires updating `detect_ship_roles()` to detect `hauler` for freighters, jump freighters, DSTs, and blockade runners (see Implementation Plan, Phase A).

**Direct requirements (SDE):** Amarr Freighter IV, Jump Freighters I, Jump Drive Calibration I — these are always role-relevant per the SDE Direct Requirement Inclusion Rule, ensuring hull skills appear in Phase 2/3 even though they aren't in any role's efficacy `skills` list.

### Phase 1: Get Online

*SDE prerequisites to board the Ark. Ordered by dependency chain.*

| # | Skill | Level | Rank | Time | Reason |
|---|-------|-------|------|------|--------|
| 1 | Spaceship Command | V | 1 | 5d 22h | SDE prerequisite |
| 2 | Industry | V | 1 | 5d 22h | SDE prerequisite |
| 3 | Science | V | 1 | 5d 22h | SDE prerequisite |
| 4 | Navigation | V | 1 | 5d 22h | SDE prerequisite |
| 5 | Warp Drive Operation | V | 1 | 5d 22h | SDE prerequisite |
| 6 | Amarr Hauler | III | 4 | 17h 46m | SDE prerequisite |
| 7 | Advanced Spaceship Command | V | 5 | 29d 15h | SDE prerequisite |
| 8 | Jump Drive Operation | V | 5 | 29d 15h | SDE prerequisite |
| 9 | Jump Drive Calibration | I | 9 | 1h 15m | SDE prerequisite |
| 10 | Amarr Freighter | IV | 10 | 10d 11h | SDE prerequisite |
| 11 | Jump Freighters | I | 14 | 1h 56m | SDE prerequisite |

**Phase total: ~106d 4h** | **Efficacy: 57.8%**

Note: Phase 1 is large for capital ships because the SDE requires many skills at V. This is inherent to the ship class — there is no shortcut. The value of the min-max plan here is showing exactly what's required vs. what's optional.

### Phase 2: Get Effective

*Role-relevant skills beyond SDE prerequisites, ordered by bucket priority then effectiveness/SP.*

| # | Skill | From→To | Rank | Time | Bucket | Reason |
|---|-------|---------|------|------|--------|--------|
| 1 | Jump Drive Calibration | I→V | 9 | 53d 6h | breakpoint [critical] | +2 LY jump range per level |
| 2 | Evasive Maneuvering | 0→IV | 2 | 2d 2h | multiplier | +5% agility per level (from `hauler`, `multiplicative: true`) |
| 3 | Jump Fuel Conservation | 0→IV | 8 | 8d 9h | multiplier | 10% fuel reduction per level (from `jump_capable`, `multiplicative: true`) |
| 4 | Jump Freighters | I→IV | 14 | 14d 14h | role_support | JF hull bonuses (direct requirement, scored by `-rank`) |

**Phase total: ~78d 7h** | **Efficacy: 91.4%**

Notes:
- JDC ranks first as a critical breakpoint (jump range is discrete per level, not percentage)
- Evasive Maneuvering and Jump Fuel Conservation are both in the multiplier bucket (`multiplicative: true` in their respective roles). EM wins on effectiveness/SP: rank 2 costs ~4× less SP than rank 8 for the same number of levels, giving EM higher effectiveness per SP invested
- Jump Freighters appears via the SDE Direct Requirement Inclusion Rule — it's a direct requirement of the Ark, so it's always role-relevant even though it's not in any role's `skills` list. It lands in `role_support` (not multiplicative) and sorts by `-rank` tiebreaker
- JDO V is already required at V in Phase 1 by SDE, so it doesn't appear in Phase 2
- Spaceship Command, Navigation, and Warp Drive Operation (from `hauler` role) are already at V in Phase 1, so they don't appear in Phase 2

### Phase 3: Get Maximal

*All remaining role-relevant skills to V, ordered by effectiveness/SP.*

| # | Skill | From→To | Rank | Time | Reason |
|---|-------|---------|------|------|--------|
| 1 | Evasive Maneuvering | IV→V | 2 | 9d 18h | Final 5% agility |
| 2 | Jump Fuel Conservation | IV→V | 8 | 39d | Final 10% fuel savings |
| 3 | Amarr Freighter | IV→V | 10 | 48d 18h | Final hull bonuses |
| 4 | Jump Freighters | IV→V | 14 | 68d 7h | Final JF hull bonuses |

**Phase total: ~165d 19h** | **Efficacy: 100%**

### Excluded Skills (Not Trained)

| Skill | Reason |
|-------|--------|
| Drones | Not in detected roles or direct requirements |
| Gunnery | Not in detected roles or direct requirements |
| Shield/Armor compensation | Not in detected roles or direct requirements |

### Plan Summary

| Phase | Time | Cumulative | Efficacy |
|-------|------|------------|----------|
| 1: Get Online | 106d 4h | 106d 4h | 57.8% |
| 2: Get Effective | 78d 7h | 184d 11h | 91.4% |
| 3: Get Maximal | 165d 19h | 350d 6h | 100% |

**Total: ~350 days from 0 to maximal Ark pilot.** Phase 1 is dominated by SDE prerequisites. The min-max plan's value is most visible in Phases 2-3, where 78 days of targeted training jumps from 57.8% to 91.4% efficacy, while the final 8.6% improvement (Phase 3) takes 166 more days — clearly showing diminishing returns.

### Contrast: Cyno Alt (Illustrative, Not Algorithm Output)

A cyno alt is a common companion to a JF pilot but is a *different character* with a trivially small plan. This example is **not produced by `minmax_plan`** — there is no single item to pass as `item` that would generate it. It's shown here to illustrate why role scoping matters, and could be served by the existing `activity_plan` system (e.g., `skills(action="activity_plan", activity="cyno alt")`).

| # | Skill | Level | Rank | Time |
|---|-------|-------|------|------|
| 1 | CPU Management | V | 1 | 5d 22h |
| 2 | Cynosural Field Theory | I | 5 | 41m |

**Total: ~6 days.** A cyno alt and a JF pilot have completely different training profiles despite supporting the same operation.

---

## Implementation Plan

### Phase A: Core Algorithm + Hauler Role (New File + YAML)

**New file:** `src/aria_esi/mcp/sde/tools_minmax.py`

Build the minmax plan generator as a standalone module, following the same pattern as `tools_easy80.py`. Since the legacy MCP tools cleanup (commit `2340645`), all SDE tool implementations live under `src/aria_esi/mcp/sde/tools_*.py` and are dispatched from `src/aria_esi/mcp/dispatchers/skills.py`:

1. **`generate_minmax_plan()`** — Core orchestrator
   - Input: item name, detected roles, current skills, attributes
   - Output: phased plan with scoring
   - Calls SDE for prerequisite tree (both `full_prerequisite_tree` and `direct_requirements`)
   - Loads efficacy/breakpoint/multiplier data
   - Applies SDE Direct Requirement Inclusion Rule
   - Assigns skills to phases per the Phase Assignment Algorithm
   - Validates cross-phase dependencies

2. **`assign_phase()`** — Phase assignment for a single skill
   - Input: skill, SDE required level, role data, breakpoint data, multiplier data, is_direct_requirement
   - Output: phase number (1, 2, or 3) and target level for that phase
   - Deterministic: Phase 1 if SDE requires it, Phase 2 if breakpoint/multiplier/role-relevant to IV, Phase 3 for IV→V

3. **`score_within_bucket()`** — Within-bucket ordering
   - Input: skill, bucket type, role data
   - Output: sort key (impact tier for breakpoints, effectiveness/SP for others)
   - No cross-bucket comparison
   - Handles `per_level: 0` skills via `-rank` fallback (negative rank sorts after all positive scores, then orders by training speed)

4. **`classify_role_strength()`** — Per-role data threshold evaluation
   - Input: role name, efficacy rules
   - Output: `"strong"` or `"weak"`
   - A role is strong if it has >= `MINIMUM_SCORED_SKILLS` (2) skills with `per_level > 0`
   - Used by `generate_minmax_plan()` to partition roles before Phase 2 ordering
   - Weak-role skills are appended after strong-role skills in Phase 2, ordered by rank

5. **`resolve_injected_prerequisites()`** — Cross-phase dependency injection
   - Input: phase skills list, Phase 1 skill levels
   - Output: phase skills with orphan prerequisites injected
   - Scans each Phase 2/3 skill's prerequisites against Phase 1 and existing phase skills
   - Injects orphans at minimum required level, placed before the first dependent skill
   - Recursively resolves injected skills' own prerequisites
   - Orphans get `scoring_bucket: "injected_prerequisite"` and no Phase 3 entry

6. **`scope_skills_to_roles()`** — Role scoping filter
   - Input: full skill tree (SDE + support), detected roles, direct requirements
   - Output: filtered tree containing skills that appear in at least one of:
     (a) a detected role's `skills` list in efficacy rules, or
     (b) the item's `direct_requirements`
   - Exclusion list for transparency (only skills in neither set and not injected orphans)

7. **`calculate_minmax_efficacy()`** — Role-aware efficacy calculation
   - Input: skills_at_level, target_levels, detected roles
   - Output: efficacy percentage (0-100)
   - Derives multiplier weight from role efficacy data (`multiplicative` flag) instead of hardcoded `MULTIPLIER_SKILLS` dict
   - Injected orphan prerequisites are excluded from efficacy weighting (zero role contribution)
   - Does NOT modify the existing `calculate_efficacy()` in `tools_easy80.py`

8. **`_minmax_plan_impl()`** — Standalone async implementation for dispatcher

**YAML addition:** `reference/skills/ship_efficacy_rules.yaml` — add `hauler` role. Required because the motivating JF example needs agility/warp skills defined. Needed before core algorithm can be validated against the golden test cases.

Note: The `hauler` role defines *support skills* that benefit hauling (agility, warp, speed). Ship-specific hull skills (Amarr Freighter, Jump Freighters) are NOT included here — they are handled by the SDE Direct Requirement Inclusion Rule, which ensures all direct requirements are role-relevant regardless of role definitions.

```yaml
hauler:
  description: Ships focused on cargo transport (freighters, DSTs, blockade runners)
  primary_metric: cargo_and_agility
  example_ships:
    - Ark
    - Rhea
    - Anshar
    - Nomad
    - Impel
    - Occator
    - Bestower
    - Sigil
    - Epithal
  skills:
    - skill: Evasive Maneuvering
      effect: "+5% agility per level"
      per_level: 5
      category: agility
      multiplicative: true
    - skill: Spaceship Command
      effect: "+2% agility per level"
      per_level: 2
      category: agility
      multiplicative: true
    - skill: Warp Drive Operation
      effect: "-10% cap per warp per level"
      per_level: 10
      category: utility
      multiplicative: false
    - skill: Navigation
      effect: "+5% sub-warp velocity per level"
      per_level: 5
      category: speed
      multiplicative: true
  easy_80_plan:
    required_5: []
    cap_at_4:
      - Evasive Maneuvering
      - Spaceship Command
      - Warp Drive Operation
    optional:
      - Navigation
  efficacy_at_4:
    agility: 85
    overall: 83
```

**Code change:** `tools_easy80.py:detect_ship_roles()` — add `hauler` detection for freighters, jump freighters, DSTs, and blockade runners. Following the existing pattern:

```python
# Haulers (freighters, JFs, DSTs, blockade runners)
hauler_ships = ["bestower", "sigil", "badger", "tayra", "nereus", "epithal",
                "wreathe", "mammoth", "hoarder", "kryos", "miasmos",
                "impel", "occator", "bustard", "mastodon", "prorator",
                "viator", "crane", "prowler"]
for ship in hauler_ships + jump_freighters:
    if ship in type_lower:
        if "hauler" not in roles:
            roles.append("hauler")
        break

if any(g in group_lower for g in ["freighter", "jump freighter", "industrial",
                                    "deep space transport", "blockade runner"]):
    if "hauler" not in roles:
        roles.append("hauler")
```

**Estimated effort:** Medium. The scoring algorithm and direct-requirement rule are new, but all data sources and calculation utilities exist.

### Phase B: Dispatcher Integration

**Modified files:**
- `src/aria_esi/mcp/dispatchers/skills.py` — Add `minmax_plan` to `SkillsAction` literal and `VALID_ACTIONS` set; add `roles` parameter to the `skills()` function signature; wire `minmax_plan` to `_minmax_plan_impl`.
- `src/aria_esi/mcp/validation.py` — Add `"minmax_plan"` entry to `SKILLS_ACTION_PARAMS` schema (e.g., `{"item", "roles", "current_skills", "attributes"}`). Without this, the parameter validation layer will flag `roles` as an irrelevant parameter.

Rename the existing `role` parameter (singular) to `roles` (plural, `list[str] | None`) across all actions. This is a one-time migration — `get_multipliers` and `get_breakpoints` accept the first element of the list; `minmax_plan` uses the full list. No backwards compatibility shim needed. The `SKILLS_ACTION_PARAMS` entries for `get_multipliers` and `get_breakpoints` must be updated from `{"role"}` to `{"roles"}` to match.

**Validation:** If `roles` is provided, every entry must be a key in `ship_efficacy_rules.yaml`. Invalid entries raise `InvalidParameterError` with the list of valid role names.

**Estimated effort:** Small. Follows established dispatcher pattern exactly.

### Phase C: User-Facing Skill (SKILL.md Update)

**Modified file:** `.claude/skills/skillplan/SKILL.md`

Add documentation for the new capability. Natural language triggers:
- "Min-max plan for [ship/activity]"
- "Fastest path to [ship/role]"
- "Max out my [ship] skills"
- "Priority training order for [role]"

**Estimated effort:** Small. Documentation-only change.

### Phase D: Efficacy Rules Expansion

**Modified file:** `reference/skills/ship_efficacy_rules.yaml`

Expand role coverage for additional min-max scenarios:

| Role | Status | Priority |
|------|--------|----------|
| `hauler` | Added in Phase A | Required for JF example |
| `ewar` | **Missing** | Low — add when requested |
| `tackle` | **Missing** | Low — add when requested |
| `capital_support` | Minimal | Low — expand when capital planning is needed |

**Estimated effort:** Small per role. YAML-only changes, no code modifications.

### Phase E: Fit-Specific Plans (Future Proposal)

Deferred to a separate proposal. The current `extract_skills_for_fit()` in `fitting/skills.py` sets all skills to a single level (default V) and does not track which module requires which skill. Adapting this for min-max requires:

1. Preserving per-module required levels (not all-V)
2. Annotating each skill with which module/ship component needs it
3. Mapping module-required skills to role scoring buckets

This is a substantially different extraction model from the current one, not a minor parameter change. The ship+role path (Phases A-D) delivers the core feature without this dependency.

---

## Viability Assessment

### What Already Exists (Reusable)

| Component | Location | Reuse Level |
|-----------|----------|-------------|
| Role detection | `tools_easy80.py:detect_ship_roles()` | Reuse + extend (add `hauler` detection) |
| Efficacy rules (YAML) | `reference/skills/ship_efficacy_rules.yaml` | Direct reuse (13 roles defined: drone_boat, turret_boat, missile_boat, armor_tank, shield_tank, miner, explorer, stealth_ship, logi, active_tank, jump_capable, capital_support, gas_miner, ice_miner, navigation) |
| Breakpoint skills (YAML) | `reference/skills/breakpoint_skills.yaml` | Direct reuse (17 breakpoints across combat, tank, stealth, industrial, capital, exploration, logi categories) |
| Multiplier skills | `tools_easy80.py:MULTIPLIER_SKILLS` | Direct reuse (Easy 80% only; minmax derives from YAML). Contains 8 skills: Drone Interfacing, Surgical Strike, Rapid Firing, Warhead Upgrades, Rapid Launch, Repair Systems, Shield Management, Astrogeology |
| Training time calc | `tools_skills.py:calculate_sp_*()` | Direct reuse |
| SDE skill tree | `queries.py:get_full_skill_tree()` | Direct reuse |
| SDE direct requirements | SDE dispatcher `skill_requirements` action | Direct reuse (returns `direct_requirements` and `full_prerequisite_tree` via `SkillRequirementsResult` model) |
| Efficacy calculation | `tools_easy80.py:calculate_efficacy()` | **Not reused** — new `calculate_minmax_efficacy()` with role-derived weights |
| Dispatcher pattern | `dispatchers/skills.py` | Direct reuse |
| Parameter validation | `validation.py:SKILLS_ACTION_PARAMS` | Extend (add `minmax_plan` entry) |
| YAML caching pattern | `tools_easy80.py:load_*()` | Direct reuse (mtime-based cache invalidation) |

**Estimate: ~60% of the implementation is assembly of existing components.** The genuinely new code is:
1. The phase assignment logic with direct-requirement rule (~100 lines)
2. The bucket-based scoring and ordering with `per_level: 0` fallback (~80 lines)
3. The role-scoping filter with direct-requirement inclusion (~50 lines)
4. The per-role data threshold classification (~20 lines)
5. The orphan prerequisite injection with recursive resolution (~60 lines)
6. The `calculate_minmax_efficacy()` function (~50 lines)
7. The `_minmax_plan_impl` orchestrator (~300 lines)
8. Cross-phase dependency validation (~30 lines)
9. `detect_ship_roles()` hauler extension (~25 lines)
10. Tests and fixtures (~530 lines)

### What Needs to Be Built

| Component | Estimated Lines | Complexity |
|-----------|----------------|------------|
| `tools_minmax.py` (core) | ~690 | Medium — phase assignment + bucket scoring + role threshold + orphan injection + efficacy |
| `detect_ship_roles()` hauler addition | ~25 | Low — follows existing pattern |
| Dispatcher wiring + `role`→`roles` migration | ~50 | Low — follows exact pattern |
| `validation.py` parameter schema update | ~5 | Low — add `minmax_plan` entry + rename `role`→`roles` |
| `hauler` role (YAML) | ~30 | Low — data-only |
| SKILL.md updates | ~40 | Low — documentation |
| Test fixtures + golden tests | ~530 | Medium — need SDE-verified scenarios + weak-role + injection tests |
| **Total** | **~1295** | |

### Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Scoring produces unintuitive ordering within buckets | Medium — users would distrust the plan | Golden test cases validate ordering against known-good sequences; bucket separation prevents cross-category confusion |
| Incomplete efficacy rules for niche roles | Low — plan degrades gracefully | Per-role data threshold (Q2 resolution): strong roles drive Phase 2 ordering normally; weak roles have skills appended after strong-role skills, ordered by rank. Warning emitted for weak roles. Plan always generates. |
| Phase 1 is very large for capital ships | Low — correct behavior | Clearly label Phase 1 as "SDE requirements (non-negotiable)" so users understand this is inherent to the ship class, not a planning failure |
| Role composition produces conflicting priorities | Low — roles are additive | When multiple roles are detected/specified, union all skills from all roles' efficacy rules. Bucket assignment uses highest priority across roles (if a skill is a breakpoint in any role, it's a breakpoint) |
| Scope creep into "skill optimizer" territory | Medium — could become unbounded | Strict scope: minmax_plan returns a static plan, not an interactive optimizer. No "what if I train X first" mode |

### Known Limitations (v1)

These are acknowledged design boundaries, not bugs:

1. **No hull bonus awareness.** The algorithm knows that Heavy Assault Cruisers is a direct requirement for the Ishtar (via SDE Direct Requirement Inclusion Rule), but it doesn't know that HAC provides 10% drone damage per level as an Ishtar hull bonus. Hull bonuses are ship-specific and not captured in the role-agnostic efficacy rules. This means hull skills sort by `-rank` tiebreaker (after all measurable-bonus skills) in the `role_support` bucket rather than by their actual per-level impact. **Future fix:** Phase E (fit-specific plans) can extract per-module and per-hull bonuses from `fitting(action="calculate_stats")` to produce truly optimal hull skill ordering.

2. **`ship_category_roles` mapping is incomplete.** The YAML has category-to-role mappings for frigates, cruisers, battlecruisers, battleships, mining barges, and exhumers. It lacks mappings for destroyers, industrials/haulers, command ships, HACs, strategic cruisers, and other groups. `detect_ship_roles()` compensates with hardcoded ship name lists, but new ship types may not be detected. Note: the archetype library (`reference/archetypes/hulls/`) now includes destroyer hulls (Coercer, Dragoon) and hauler hulls (Sigil, Epithal), so the archetype coverage is ahead of the `ship_category_roles` YAML. Adding destroyer and hauler/industrial entries to `ship_category_roles` is a straightforward YAML addition in Phase D.

### Relationship to Easy 80%

Min-max planning **does not replace** Easy 80%. They serve different audiences:

| Dimension | Easy 80% | Min-Max |
|-----------|----------|---------|
| **Audience** | Generalist pilots, mains | Dedicated alts, focused mains |
| **Philosophy** | Good enough everywhere | Perfect for one thing |
| **Scope** | Ship + broad support skills | Role-scoped, nothing extra |
| **Training order** | Unordered (grouped by category) | Strictly ordered by bucket + effectiveness/SP |
| **Efficacy target** | ~80% | 100% for the role |
| **Output structure** | Flat categories | Phased milestones |

The two coexist as complementary tools. A pilot might use Easy 80% for their main and min-max plans for their alts.

---

## Golden Test Cases

The following scenarios have well-understood optimal training orders and serve as assertion-level tests for the scoring algorithm. Each test validates *relative ordering*, not exact scores.

### Test 1: Ishtar Drone Ratting (drone_boat + active_tank + armor_tank)

**Key ordering assertions for Phase 2:**
1. Drones V (breakpoint, critical) must appear before all multiplier skills
2. Medium Drone Operation to IV (multiplier, 5%/level, rank 2) must appear before Drone Interfacing to IV (multiplier, 10%/level, rank 5) — MDO has higher effectiveness/SP because rank 2 costs ~2.5× less SP than rank 5, outweighing DI's higher per_level
3. Heavy Drone Operation to IV must appear (applicable for battleship-sized drones on Ishtar)

**Exclusion note:**
Mining, Ice Harvesting, Gas Cloud Harvesting, and Missile Launcher Operation are not in the Ishtar's SDE prerequisite tree and are not in any detected role's skill list. They never enter the pipeline, so they do not appear in `excluded_skills`. The exclusion list only contains skills that *were* in the tree but filtered out by role scoping (e.g., support skills from a different role).

### Test 2: Ark Jump Freighter (jump_capable + hauler)

**Key ordering assertions for Phase 2:**
1. Jump Drive Calibration I→V (breakpoint, critical) must appear first
2. Evasive Maneuvering to IV (multiplier, 5%/level, rank 2) must appear before Jump Fuel Conservation to IV (multiplier, 10%/level, rank 8) — both are `multiplicative: true` in their roles, so both land in the multiplier bucket; EM wins on effectiveness/SP because rank 2 costs ~4× less SP than rank 8 for the same number of levels
3. Both Evasive Maneuvering and Jump Fuel Conservation (positive effectiveness_per_sp) must appear before Jump Freighters I→IV (direct requirement, `-rank` tiebreaker in role_support bucket)

**Direct requirement inclusion assertions:**
- Jump Freighters must appear in Phase 2 (I→IV) and Phase 3 (IV→V) via SDE Direct Requirement Inclusion Rule
- Amarr Freighter must appear in Phase 3 (IV→V) — Phase 1 satisfies it at IV, Phase 3 promotes to V
- Neither Jump Freighters nor Amarr Freighter appears in any role's `skills` list — inclusion comes from `direct_requirements`

**Phase 1 assertions (SDE ground truth):**
- Must contain exactly 11 skills (verified against `sde(action="skill_requirements", item="Ark")`)
- Must include Industry V and Science V (commonly forgotten prerequisites)
- Must NOT contain Amarr Frigate, Amarr Destroyer, Amarr Cruiser, Amarr Battlecruiser, or Amarr Battleship (these are NOT in the Ark's prerequisite chain)
- Skill name must be "Amarr Hauler" (not "Amarr Industrial")

### Test 3: Skiff Mining (miner + shield_tank)

**Key ordering assertions for Phase 2:**
1. Mining V (breakpoint, high — unlocks Mining Barge skill) must appear before Astrogeology to IV
2. Astrogeology to IV (multiplier, 5%/level yield) must appear before Mining Upgrades to IV (support, 5%/level CPU reduction — lower practical impact)

**Phase split assertion:**
- Mining V appears in Phase 1 if SDE requires it for the ship, OR in Phase 2 if it's a breakpoint beyond SDE requirements

### Test 4: Venture Mining (miner + shield_tank) — Orphan Prerequisite Injection

The Venture has a minimal SDE tree (Spaceship Command I, Mining Frigate I), making it the primary injection test case.

**Key injection assertions for Phase 2:**
1. Science IV must be injected before Astrogeology (Astrogeology requires Science IV; Science is not in any role's `skills` list)
2. Power Grid Management III must be injected before Shield Management (Shield Management requires PGM III; PGM is not in any role's `skills` list)
3. Power Grid Management III must also satisfy Shield Operation (requires PGM I) and Tactical Shield Manipulation (requires PGM III) — injected once at `max(I, III, III) = III`

**Injection bucket assertions:**
- Science IV and PGM III must have `scoring_bucket: "injected_prerequisite"`
- They must appear immediately before the first skill that depends on them within the bucket ordering
- Neither Science nor PGM appears in Phase 3 (zero role efficacy — no further training)

**Exclusion assertions:**
- Science and PGM must NOT appear in `excluded_skills` (they are trained, not excluded)
- Skills like Drones and Gunnery (not in miner or shield_tank roles, not SDE prerequisites, not needed as prerequisites) must appear in `excluded_skills`

**Efficacy assertion:**
- Science and PGM must NOT contribute to `efficacy_at_phase_end` calculations (they have zero role effectiveness)

---

## Alternative Approaches Considered

### Alternative 1: Extend Activity Plans with Priority Ordering
Add a `priority` field to existing activity YAML tiers. Rejected because activities are too coarse — "hauling" doesn't distinguish between JF and DST, and can't incorporate role-specific efficacy scoring.

### Alternative 2: Pure Fit-Based Planning Only
Only support minmax via EFT fits, no role-based path. Rejected because many min-max scenarios don't have a specific fit in mind yet ("I want a JF alt" precedes "I want *this specific* Ark fit"). Fit-specific planning is deferred to a future proposal (see Phase E).

### Alternative 3: Add "maximal" as a Fourth Activity Tier
Add a `maximal` tier to `skill_plans.yaml` alongside minimum/easy_80/full. Rejected because "maximal" requires the bucket-based ordering logic that activities don't support, and activity definitions are generic while min-max plans are role-specific.

### Alternative 4: Single Unified Scoring Function
Use one `effectiveness_per_sp` score across all skill types (breakpoints, multipliers, support) with synthetic weights. Rejected because:
- Breakpoint effectiveness values are inherently incomparable with percentage bonuses (Drones V = "25% DPS" vs. Mining V = "unlocks ship class" — both are critical, neither has a meaningful per-SP score)
- Magic weight constants (e.g., `25.0` for breakpoints, `1.2` for multiplicative) are arbitrary and untestable
- Bucket-based sorting is more transparent: users can see *why* a skill is prioritized (it's a breakpoint) rather than trusting an opaque score

---

## Verdict: Viable

**Viability: HIGH.** The proposal is implementable with moderate effort because:

1. **~60% of the infrastructure exists** — role detection, efficacy rules, breakpoint/multiplier skills, training time calculation, and the dispatcher pattern are all production-ready
2. **The new code is focused** — ~690 lines of core algorithm, plus ~80 lines of dispatcher/detection/validation changes
3. **The data model is extensible** — adding new roles to efficacy rules is YAML-only, no code changes
4. **The feature is orthogonal** — min-max planning doesn't modify or conflict with Easy 80%; they coexist as complementary tools
5. **The scoring approach is testable** — bucket-based sorting with golden test cases provides concrete pass/fail assertions, not "does this score look reasonable"

**Recommended implementation order:** Phase A (core algorithm + hauler role) > Phase B (dispatcher) > Phase C (SKILL.md) > Phase D (YAML expansion, as needed).

Phases A+B+C deliver the core feature with the JF and drone boat use cases. Phase D expands role coverage on demand. Phase E (fit-specific plans) is deferred to a separate proposal.

## Open Decisions (Auto-generated)

### Q1: minmax_multi_role_scoring_aggregation — RESOLVED

**Question:** How should `effectiveness_per_sp` be computed when a skill appears in multiple selected/detected roles?

**Decision:** `O1` — Use maximum per-role `per_level` contribution. This is codified in the Multi-role scoring rule (see Scoring section above).

### Q2: minmax_missing_efficacy_fallback — RESOLVED

**Question:** What is the canonical behavior when detected/specified roles have missing or empty efficacy definitions?

**Decision:** `S4` — Per-role data threshold with fallback. Each role is classified as **strong** (>= 2 skills with `per_level > 0`) or **weak** (< 2). Strong roles drive Phase 2 bucket-based ordering normally. Weak roles have their skills appended after all strong-role skills in Phase 2, ordered by rank ascending. A warning names the weak roles. The plan always generates — never blocks the user. See "Per-Role Data Threshold" in the Phase 2 algorithm section.

### Q3: minmax_dependency_injection_target_level — RESOLVED

**Question:** When unmet prerequisites are pulled in to satisfy a Phase 2/3 skill, what target level should the injected prerequisite use?

**Decision:** `S1` — Minimum required level, placed in Phase 2 before the dependent skill. Orphan prerequisites train to the exact level needed (the maximum across all dependents in the plan), are placed immediately before the first skill that depends on them within its bucket position, and receive `scoring_bucket: "injected_prerequisite"`. No Phase 3 entry is created — orphans have zero role efficacy and training them beyond the minimum wastes SP. See "Cross-Phase Dependency Guarantee" for the full injection algorithm and `injected_prerequisite` entries in the Bucket Priority table.

