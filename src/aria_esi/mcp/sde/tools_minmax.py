"""
Min-Max Skill Planning Module.

Implements role-scoped, phased skill plans that optimize for maximum
effectiveness in a specific role. Three phases:
  Phase 1 - Get Online: SDE prerequisites at exact required levels
  Phase 2 - Get Effective: Breakpoints, multipliers, role skills to IV
  Phase 3 - Get Maximal: All remaining role-relevant skills to V

Complements (does not replace) the Easy 80% system.
"""

from __future__ import annotations

import math

from aria_esi.core.logging import get_logger
from aria_esi.mcp.market.database import get_market_database

from .queries import get_sde_query_service
from .tools_easy80 import (
    detect_ship_roles,
    load_breakpoint_skills,
    load_efficacy_rules,
)
from .tools_skills import (
    DEFAULT_ATTRIBUTES,
    calculate_sp_for_level,
    calculate_sp_per_minute,
    format_training_time,
)

logger = get_logger("aria_sde.tools_minmax")

# =============================================================================
# Constants
# =============================================================================

# Minimum number of skills with per_level > 0 for a role to be "strong"
MINIMUM_SCORED_SKILLS = 2

# Impact tier ordering for breakpoint skills (lower = higher priority)
IMPACT_TIER_ORDER = {"critical": 0, "high": 1, "medium": 2}


# =============================================================================
# Role Classification
# =============================================================================


def classify_role_strength(role: str, efficacy_rules: dict) -> str:
    """
    Classify a role as 'strong' or 'weak' based on efficacy data coverage.

    A role is strong if it has >= MINIMUM_SCORED_SKILLS skills with per_level > 0,
    meaning effectiveness/SP comparisons are meaningful.

    Args:
        role: Role name from ship_efficacy_rules.yaml
        efficacy_rules: Loaded efficacy rules dict

    Returns:
        "strong" or "weak"
    """
    ship_roles = efficacy_rules.get("ship_roles", {})
    role_data = ship_roles.get(role, {})
    scored_skills = [s for s in role_data.get("skills", []) if s.get("per_level", 0) > 0]
    return "strong" if len(scored_skills) >= MINIMUM_SCORED_SKILLS else "weak"


# =============================================================================
# Skill Scoping
# =============================================================================


def _build_role_skill_set(
    detected_roles: list[str],
    efficacy_rules: dict,
) -> dict[str, dict]:
    """
    Build the union of all role-relevant skills from efficacy rules.

    Returns:
        Dict mapping skill_name -> best skill_info dict (max per_level across roles).
    """
    ship_roles = efficacy_rules.get("ship_roles", {})
    role_skills: dict[str, dict] = {}

    for role in detected_roles:
        role_data = ship_roles.get(role, {})
        for skill_info in role_data.get("skills", []):
            skill_name = skill_info.get("skill")
            if not skill_name:
                continue
            existing = role_skills.get(skill_name)
            if existing is None or skill_info.get("per_level", 0) > existing.get("per_level", 0):
                role_skills[skill_name] = skill_info

    return role_skills


def scope_skills_to_roles(
    full_tree: list[dict],
    direct_requirement_names: set[str],
    detected_roles: list[str],
    efficacy_rules: dict,
) -> tuple[list[dict], list[dict]]:
    """
    Filter a skill tree to role-relevant skills.

    A skill is role-relevant if it appears in:
      (a) a detected role's skills list in efficacy rules, OR
      (b) the item's direct_requirements from SDE

    Skills in the SDE prerequisite tree (required_level > 0) are never excluded —
    they are Phase 1 requirements.

    Args:
        full_tree: Complete skill tree including SDE prerequisites and support skills
        direct_requirement_names: Set of skill names from SDE direct requirements
        detected_roles: List of detected/specified roles
        efficacy_rules: Loaded efficacy rules

    Returns:
        (included_skills, excluded_skills) — both are lists of skill dicts
    """
    role_skills = _build_role_skill_set(detected_roles, efficacy_rules)

    included = []
    excluded = []

    for skill in full_tree:
        skill_name = skill.get("skill_name", "")
        required_level = skill.get("required_level", 0)

        # SDE prerequisites are never excluded
        if required_level > 0:
            included.append(skill)
        # Direct requirements are always role-relevant
        elif skill_name in direct_requirement_names:
            included.append(skill)
        # Role skills are included
        elif skill_name in role_skills:
            included.append(skill)
        # Everything else is excluded
        else:
            excluded.append(
                {
                    "skill_name": skill_name,
                    "reason": "Not in any detected role's efficacy rules or direct requirements",
                }
            )

    return included, excluded


# =============================================================================
# Scoring
# =============================================================================


def effectiveness_per_sp(
    skill_name: str,
    from_level: int,
    to_level: int,
    rank: int,
    detected_roles: list[str],
    efficacy_rules: dict,
) -> float:
    """
    Score a skill by effectiveness gain per SP invested.

    Uses max per_level across all detected roles (multi-role scoring rule).
    Only comparable within the same scoring bucket.

    Args:
        skill_name: Skill name
        from_level: Starting level
        to_level: Target level
        rank: Skill training rank
        detected_roles: Active roles
        efficacy_rules: Loaded efficacy rules

    Returns:
        Effectiveness score. Positive for measurable bonuses, negative rank
        for unmeasured skills (sorts after all positive scores).
    """
    sp_cost = calculate_sp_for_level(rank, to_level) - calculate_sp_for_level(rank, from_level)
    if from_level == 0:
        sp_cost = calculate_sp_for_level(rank, to_level)

    # Find max per_level across all detected roles
    ship_roles = efficacy_rules.get("ship_roles", {})
    max_per_level = 0
    for role in detected_roles:
        role_data = ship_roles.get(role, {})
        for skill_info in role_data.get("skills", []):
            if skill_info.get("skill") == skill_name:
                max_per_level = max(max_per_level, skill_info.get("per_level", 0))

    if max_per_level == 0:
        # Unmeasured skill — use -rank so lower rank (faster training) sorts first
        # These sort after all positive scores within the same bucket
        return -rank

    levels_gained = to_level - from_level
    effectiveness_gain = max_per_level * levels_gained

    return effectiveness_gain / max(sp_cost, 1)


def _score_breakpoint(
    skill_name: str,
    rank: int,
    breakpoint_info: dict,
) -> tuple[int, int]:
    """
    Score a breakpoint skill for ordering within the breakpoint bucket.

    Returns:
        (impact_tier_order, rank) — sort by tier first, then rank ascending
    """
    impact = breakpoint_info.get("impact", "medium")
    tier_order = IMPACT_TIER_ORDER.get(impact, 2)
    return (tier_order, rank)


# =============================================================================
# Phase Assignment
# =============================================================================


def _get_applicable_breakpoints(
    detected_roles: list[str],
    breakpoint_skills: dict,
) -> dict[str, dict]:
    """Get breakpoint skills applicable to detected roles."""
    applicable = {}
    for skill_name, bp_info in breakpoint_skills.items():
        applies_to = bp_info.get("applies_to_roles")
        if applies_to is None or any(role in applies_to for role in detected_roles):
            applicable[skill_name] = bp_info
    return applicable


def _is_multiplier_in_roles(
    skill_name: str,
    detected_roles: list[str],
    efficacy_rules: dict,
) -> bool:
    """Check if a skill is marked as multiplicative in any detected role."""
    ship_roles = efficacy_rules.get("ship_roles", {})
    for role in detected_roles:
        role_data = ship_roles.get(role, {})
        for skill_info in role_data.get("skills", []):
            if skill_info.get("skill") == skill_name and skill_info.get("multiplicative"):
                return True
    return False


# =============================================================================
# Prerequisite Injection
# =============================================================================


def resolve_injected_prerequisites(
    phase_skills: list[dict],
    phase1_skill_levels: dict[str, int],
    query_service,
    db_conn,
) -> list[dict]:
    """
    Scan phase skills for unmet prerequisites. Inject orphans at minimum
    required level, placed immediately before the first skill that needs them.

    Orphan prerequisites do NOT appear in Phase 3 — they train to the minimum
    level needed and no further.

    Args:
        phase_skills: Ordered list of phase skill dicts
        phase1_skill_levels: Skill levels satisfied by Phase 1
        query_service: SDE query service for prerequisite lookups
        db_conn: Database connection for skill lookups

    Returns:
        Updated phase_skills with orphan prerequisites injected
    """
    # Collect all skill names already in this phase
    phase_skill_names = {s["skill_name"] for s in phase_skills}

    # Build injection map: skill_name -> {to_level, first_dependent_idx}
    injections: dict[str, dict] = {}

    for idx, skill in enumerate(phase_skills):
        skill_name = skill["skill_name"]
        prereqs = _get_skill_prerequisites(skill_name, query_service, db_conn)

        for prereq_name, prereq_level in prereqs:
            # Already satisfied by Phase 1?
            if phase1_skill_levels.get(prereq_name, 0) >= prereq_level:
                continue
            # Already a role skill in this phase?
            if prereq_name in phase_skill_names:
                continue
            # Already injected at sufficient level?
            existing = injections.get(prereq_name)
            if existing and existing["to_level"] >= prereq_level:
                # Update index if this dependent comes earlier
                existing["first_dependent_idx"] = min(existing["first_dependent_idx"], idx)
                continue

            injections[prereq_name] = {
                "to_level": prereq_level,
                "first_dependent_idx": idx,
                "first_dependent_name": skill_name,
            }

    if not injections:
        return phase_skills

    # Recursively check injected skills' own prerequisites
    _resolve_recursive_injections(
        injections, phase1_skill_levels, phase_skill_names, query_service, db_conn
    )

    # Build injection entries with skill attributes
    injection_entries: list[dict] = []
    for skill_name, inj_info in injections.items():
        skill_attrs = _lookup_skill_attrs(skill_name, query_service, db_conn)
        if not skill_attrs:
            continue

        from_level = phase1_skill_levels.get(skill_name, 0)
        to_level = inj_info["to_level"]
        if from_level >= to_level:
            continue

        rank = skill_attrs["rank"]
        sp_cost = calculate_sp_for_level(rank, to_level) - (
            calculate_sp_for_level(rank, from_level) if from_level > 0 else 0
        )
        sp_per_min = calculate_sp_per_minute(
            skill_attrs.get("primary_attribute"),
            skill_attrs.get("secondary_attribute"),
        )
        training_seconds = int(math.ceil((sp_cost / max(sp_per_min, 1)) * 60))

        injection_entries.append(
            {
                "skill_name": skill_name,
                "from_level": from_level,
                "to_level": to_level,
                "rank": rank,
                "training_seconds": training_seconds,
                "training_formatted": format_training_time(training_seconds),
                "reason": f"Prerequisite for {inj_info['first_dependent_name']} (minimum level)",
                "scoring_bucket": "injected_prerequisite",
                "insert_before_idx": inj_info["first_dependent_idx"],
                "primary_attribute": skill_attrs.get("primary_attribute"),
                "secondary_attribute": skill_attrs.get("secondary_attribute"),
            }
        )

    # Sort injections by their target insert position (stable)
    injection_entries.sort(key=lambda x: x["insert_before_idx"])

    # Merge into phase_skills: insert each injection before its target index
    # Work backwards to preserve index stability
    result = list(phase_skills)
    offset = 0
    for entry in injection_entries:
        insert_idx = entry.pop("insert_before_idx") + offset
        result.insert(insert_idx, entry)
        offset += 1

    return result


def _resolve_recursive_injections(
    injections: dict[str, dict],
    phase1_skill_levels: dict[str, int],
    phase_skill_names: set[str],
    query_service,
    db_conn,
    depth: int = 0,
) -> None:
    """Recursively resolve prerequisites of injected skills."""
    if depth > 5:
        return

    new_injections: dict[str, dict] = {}
    for inj_name, inj_info in list(injections.items()):
        prereqs = _get_skill_prerequisites(inj_name, query_service, db_conn)
        for prereq_name, prereq_level in prereqs:
            if phase1_skill_levels.get(prereq_name, 0) >= prereq_level:
                continue
            if prereq_name in phase_skill_names:
                continue
            if prereq_name in injections:
                existing = injections[prereq_name]
                existing["to_level"] = max(existing["to_level"], prereq_level)
                existing["first_dependent_idx"] = min(
                    existing["first_dependent_idx"], inj_info["first_dependent_idx"]
                )
                continue
            if prereq_name in new_injections:
                existing = new_injections[prereq_name]
                existing["to_level"] = max(existing["to_level"], prereq_level)
                existing["first_dependent_idx"] = min(
                    existing["first_dependent_idx"], inj_info["first_dependent_idx"]
                )
                continue

            new_injections[prereq_name] = {
                "to_level": prereq_level,
                "first_dependent_idx": inj_info["first_dependent_idx"],
                "first_dependent_name": inj_name,
            }

    if new_injections:
        injections.update(new_injections)
        _resolve_recursive_injections(
            injections, phase1_skill_levels, phase_skill_names, query_service, db_conn, depth + 1
        )


def _get_skill_prerequisites(
    skill_name: str,
    query_service,
    db_conn,
) -> list[tuple[str, int]]:
    """
    Get direct prerequisites for a skill.

    Returns:
        List of (prerequisite_skill_name, required_level) tuples
    """
    cursor = db_conn.execute(
        "SELECT type_id FROM types WHERE type_name_lower = ? AND category_id = 16 LIMIT 1",
        (skill_name.lower(),),
    )
    row = cursor.fetchone()
    if not row:
        return []

    skill_id = row[0]
    direct_reqs = query_service.get_type_skill_requirements(skill_id)
    return [(req.skill_name, req.required_level) for req in direct_reqs]


def _lookup_skill_attrs(
    skill_name: str,
    query_service,
    db_conn,
) -> dict | None:
    """Look up skill attributes from the SDE."""
    cursor = db_conn.execute(
        "SELECT type_id FROM types WHERE type_name_lower = ? AND category_id = 16 LIMIT 1",
        (skill_name.lower(),),
    )
    row = cursor.fetchone()
    if not row:
        return None

    attrs = query_service.get_skill_attributes(row[0])
    if not attrs:
        return None

    return {
        "skill_id": attrs.type_id,
        "rank": attrs.rank,
        "primary_attribute": attrs.primary_attribute,
        "secondary_attribute": attrs.secondary_attribute,
    }


# =============================================================================
# Efficacy Calculation
# =============================================================================


def calculate_minmax_efficacy(
    skills_at_level: dict[str, int],
    target_levels: dict[str, int],
    roles: list[str],
    efficacy_rules: dict,
) -> float:
    """
    Calculate efficacy percentage with role-derived weights.

    Unlike the Easy 80% calculate_efficacy(), this derives multiplier weights
    from the role's efficacy rules at runtime, rather than using the hardcoded
    MULTIPLIER_SKILLS dict. Injected orphan prerequisites are excluded from
    weighting (zero role contribution).

    Args:
        skills_at_level: Skill levels at the evaluation point
        target_levels: Phase 3 target levels (100% reference)
        roles: Detected roles for weight derivation
        efficacy_rules: Loaded efficacy rules

    Returns:
        Efficacy as percentage (0-100)
    """
    if not skills_at_level or not target_levels:
        return 100.0

    role_skills = _build_role_skill_set(roles, efficacy_rules)

    weighted_sum = 0.0
    total_weight = 0.0

    for skill_name, target in target_levels.items():
        current = skills_at_level.get(skill_name, 0)
        if target <= 0:
            continue

        ratio = current / target

        # Derive weight from role efficacy data
        if skill_name in role_skills:
            skill_info = role_skills[skill_name]
            if skill_info.get("multiplicative"):
                weight = 3.0
            else:
                per_level = skill_info.get("per_level", 0)
                weight = 1.0 + (per_level / 10.0)
        else:
            # Direct-requirement or prerequisite skill not in role rules
            weight = 1.0

        weighted_sum += ratio * weight
        total_weight += weight

    if total_weight == 0:
        return 100.0

    efficacy = (weighted_sum / total_weight) * 100
    return round(efficacy, 1)


# =============================================================================
# Plan Generation
# =============================================================================


def generate_minmax_plan(
    full_tree: list[dict],
    direct_requirement_names: set[str],
    detected_roles: list[str],
    efficacy_rules: dict,
    breakpoint_skills: dict,
    current_skills: dict[str, int] | None = None,
    attributes: dict[str, int] | None = None,
    query_service=None,
    db_conn=None,
) -> dict:
    """
    Generate a phased min-max skill plan.

    Args:
        full_tree: Complete skill tree (SDE prerequisites + support skills)
        direct_requirement_names: Set of skill names from SDE direct requirements
        detected_roles: List of roles to optimize for
        efficacy_rules: Loaded ship_efficacy_rules.yaml
        breakpoint_skills: Loaded breakpoint_skills.yaml
        current_skills: Pilot's current skill levels
        attributes: Character attributes for training time
        query_service: SDE query service (for prerequisite injection)
        db_conn: Database connection (for prerequisite injection)

    Returns:
        Plan dict with phases, totals, excluded_skills, and warnings
    """
    current = current_skills or {}
    attrs = attributes or DEFAULT_ATTRIBUTES

    # Build reference data
    role_skills = _build_role_skill_set(detected_roles, efficacy_rules)
    applicable_breakpoints = _get_applicable_breakpoints(detected_roles, breakpoint_skills)

    # Classify roles
    strong_roles = []
    weak_roles = []
    for role in detected_roles:
        if classify_role_strength(role, efficacy_rules) == "strong":
            strong_roles.append(role)
        else:
            weak_roles.append(role)

    warnings: list[str] = []
    if weak_roles:
        warnings.append(
            f"Role(s) {weak_roles} have limited efficacy data. "
            f"Their skills appear in Phase 2 but without effectiveness-based ordering."
        )

    # =================================================================
    # Phase 1: Get Online — SDE prerequisites at exact required levels
    # =================================================================
    phase1_skills: list[dict] = []
    phase1_skill_levels: dict[str, int] = {}  # skill_name -> level after phase 1

    for skill in full_tree:
        required_level = skill.get("required_level", 0)
        if required_level <= 0:
            continue

        skill_name = skill["skill_name"]
        from_level = current.get(skill_name, 0)
        if from_level >= required_level:
            # Already trained — still record in phase1_skill_levels
            phase1_skill_levels[skill_name] = max(
                phase1_skill_levels.get(skill_name, 0), required_level
            )
            continue

        rank = skill.get("rank", 1)
        sp_cost = calculate_sp_for_level(rank, required_level) - (
            calculate_sp_for_level(rank, from_level) if from_level > 0 else 0
        )
        sp_per_min = calculate_sp_per_minute(
            skill.get("primary_attribute"),
            skill.get("secondary_attribute"),
            attrs,
        )
        training_seconds = int(math.ceil((sp_cost / max(sp_per_min, 1)) * 60))

        phase1_skills.append(
            {
                "skill_name": skill_name,
                "from_level": from_level,
                "to_level": required_level,
                "rank": rank,
                "training_seconds": training_seconds,
                "training_formatted": format_training_time(training_seconds),
                "reason": f"SDE prerequisite (rank {rank})",
                "scoring_bucket": "prerequisite",
                "primary_attribute": skill.get("primary_attribute"),
                "secondary_attribute": skill.get("secondary_attribute"),
            }
        )
        phase1_skill_levels[skill_name] = required_level

    # Topological ordering: sort by rank ascending (lower rank = earlier in tree)
    phase1_skills.sort(key=lambda s: (s["rank"], s["skill_name"]))

    # =================================================================
    # Phase 2: Get Effective — role-relevant skills ordered by bucket
    # =================================================================
    phase2_candidates: list[dict] = []

    # Collect all role-relevant skill names (from efficacy rules + direct requirements)
    all_role_relevant = set(role_skills.keys()) | direct_requirement_names

    for skill_name in all_role_relevant:
        # Look up skill info from the full tree or SDE
        tree_entry = next((s for s in full_tree if s.get("skill_name") == skill_name), None)
        rank = tree_entry["rank"] if tree_entry else 1

        # Determine Phase 2 target level
        phase1_level = phase1_skill_levels.get(skill_name, 0)
        current_level = max(current.get(skill_name, 0), phase1_level)

        if skill_name in applicable_breakpoints:
            bp_level = applicable_breakpoints[skill_name]["breakpoint_level"]
            target = bp_level
            bucket = "breakpoint"
        elif skill_name in role_skills and role_skills[skill_name].get("multiplicative"):
            target = 4
            bucket = "multiplier"
        else:
            target = 4
            bucket = "role_support"

        # Skip if already at or above target
        if current_level >= target:
            continue

        from_level = current_level

        # Look up actual rank and attributes from tree or SDE
        primary_attr = tree_entry.get("primary_attribute") if tree_entry else None
        secondary_attr = tree_entry.get("secondary_attribute") if tree_entry else None

        # If not in tree, look up from SDE
        if tree_entry is None and db_conn and query_service:
            sde_attrs = _lookup_skill_attrs(skill_name, query_service, db_conn)
            if sde_attrs:
                rank = sde_attrs["rank"]
                primary_attr = sde_attrs.get("primary_attribute")
                secondary_attr = sde_attrs.get("secondary_attribute")

        sp_cost = calculate_sp_for_level(rank, target) - (
            calculate_sp_for_level(rank, from_level) if from_level > 0 else 0
        )
        sp_per_min = calculate_sp_per_minute(primary_attr, secondary_attr, attrs)
        training_seconds = int(math.ceil((sp_cost / max(sp_per_min, 1)) * 60))

        # Determine which roles this skill belongs to for strength classification
        skill_in_strong = any(
            skill_name
            in {
                s.get("skill")
                for s in efficacy_rules.get("ship_roles", {}).get(r, {}).get("skills", [])
            }
            or skill_name in direct_requirement_names
            for r in strong_roles
        )
        skill_in_weak_only = not skill_in_strong

        # Build reason string
        if bucket == "breakpoint":
            bp_info = applicable_breakpoints[skill_name]
            impact = bp_info.get("impact", "medium")
            reason = f"BREAKPOINT [{impact}]: {bp_info.get('effect', '')}"
        elif bucket == "multiplier":
            eff = role_skills.get(skill_name, {}).get("effect", "")
            reason = f"MULTIPLIER: {eff}"
        else:
            eff = role_skills.get(skill_name, {}).get("effect", "")
            if skill_name in direct_requirement_names and skill_name not in role_skills:
                reason = "Direct requirement hull skill (scored by rank)"
            else:
                reason = f"Role support: {eff}"

        # Compute sort score — tuple[int, int, float, str] for all branches
        sort_key: tuple[int, int, float, str]
        if bucket == "breakpoint":
            bp_score = _score_breakpoint(skill_name, rank, applicable_breakpoints[skill_name])
            sort_key = (0, bp_score[0], float(bp_score[1]), skill_name)
        elif bucket == "multiplier":
            eff_score = effectiveness_per_sp(
                skill_name, from_level, target, rank, detected_roles, efficacy_rules
            )
            sort_key = (1, 0, -eff_score, skill_name)
        else:
            eff_score = effectiveness_per_sp(
                skill_name, from_level, target, rank, detected_roles, efficacy_rules
            )
            sort_key = (2, 0, -eff_score, skill_name)

        entry = {
            "skill_name": skill_name,
            "from_level": from_level,
            "to_level": target,
            "rank": rank,
            "training_seconds": training_seconds,
            "training_formatted": format_training_time(training_seconds),
            "reason": reason,
            "scoring_bucket": bucket,
            "sort_key": sort_key,
            "is_weak_role_only": skill_in_weak_only,
            "primary_attribute": primary_attr,
            "secondary_attribute": secondary_attr,
        }

        if bucket == "breakpoint":
            entry["impact_tier"] = applicable_breakpoints[skill_name].get("impact", "medium")
        elif bucket in ("multiplier", "role_support"):
            entry["effectiveness_per_sp"] = effectiveness_per_sp(
                skill_name, from_level, target, rank, detected_roles, efficacy_rules
            )

        phase2_candidates.append(entry)

    # Sort: strong-role skills first (by bucket priority), then weak-role skills (by rank)
    strong_skills = [s for s in phase2_candidates if not s.get("is_weak_role_only")]
    weak_skills = [s for s in phase2_candidates if s.get("is_weak_role_only")]

    strong_skills.sort(key=lambda s: s["sort_key"])
    weak_skills.sort(key=lambda s: s["rank"])

    phase2_skills = strong_skills + weak_skills

    # Clean up sort keys from output
    for s in phase2_skills:
        s.pop("sort_key", None)
        s.pop("is_weak_role_only", None)

    # Inject orphan prerequisites for Phase 2
    if query_service and db_conn:
        phase2_skills = resolve_injected_prerequisites(
            phase2_skills, phase1_skill_levels, query_service, db_conn
        )

    # =================================================================
    # Phase 3: Get Maximal — remaining role-relevant skills to V
    # =================================================================
    # Track levels after Phase 2
    phase2_skill_levels = dict(phase1_skill_levels)
    for s in phase2_skills:
        phase2_skill_levels[s["skill_name"]] = max(
            phase2_skill_levels.get(s["skill_name"], 0), s["to_level"]
        )

    # Also track current skills
    for skill_name, level in current.items():
        phase2_skill_levels[skill_name] = max(phase2_skill_levels.get(skill_name, 0), level)

    phase3_candidates: list[dict] = []

    for skill_name in all_role_relevant:
        current_level = phase2_skill_levels.get(skill_name, current.get(skill_name, 0))
        if current_level >= 5:
            continue

        # Look up skill info
        tree_entry = next((s for s in full_tree if s.get("skill_name") == skill_name), None)
        rank = tree_entry["rank"] if tree_entry else 1
        primary_attr = tree_entry.get("primary_attribute") if tree_entry else None
        secondary_attr = tree_entry.get("secondary_attribute") if tree_entry else None

        if tree_entry is None and db_conn and query_service:
            sde_attrs = _lookup_skill_attrs(skill_name, query_service, db_conn)
            if sde_attrs:
                rank = sde_attrs["rank"]
                primary_attr = sde_attrs.get("primary_attribute")
                secondary_attr = sde_attrs.get("secondary_attribute")

        from_level = current_level
        sp_cost = calculate_sp_for_level(rank, 5) - (
            calculate_sp_for_level(rank, from_level) if from_level > 0 else 0
        )
        sp_per_min = calculate_sp_per_minute(primary_attr, secondary_attr, attrs)
        training_seconds = int(math.ceil((sp_cost / max(sp_per_min, 1)) * 60))

        eff_score = effectiveness_per_sp(
            skill_name, from_level, 5, rank, detected_roles, efficacy_rules
        )

        phase3_candidates.append(
            {
                "skill_name": skill_name,
                "from_level": from_level,
                "to_level": 5,
                "rank": rank,
                "training_seconds": training_seconds,
                "training_formatted": format_training_time(training_seconds),
                "reason": f"Final level: {role_skills.get(skill_name, {}).get('effect', 'hull bonuses')}",
                "scoring_bucket": "role_support",
                "effectiveness_per_sp": eff_score,
                "primary_attribute": primary_attr,
                "secondary_attribute": secondary_attr,
            }
        )

    # Sort Phase 3 by effectiveness/SP descending
    phase3_candidates.sort(key=lambda s: (-s.get("effectiveness_per_sp", 0), s["skill_name"]))

    # Also add Phase 1 skills that need to go to V (e.g., Amarr Freighter IV -> V)
    for skill_name in phase1_skill_levels:
        if skill_name not in all_role_relevant:
            continue
        current_level = phase2_skill_levels.get(skill_name, phase1_skill_levels[skill_name])
        if current_level >= 5:
            continue
        # Already in phase3_candidates?
        if any(s["skill_name"] == skill_name for s in phase3_candidates):
            continue

        tree_entry = next((s for s in full_tree if s.get("skill_name") == skill_name), None)
        if not tree_entry:
            continue
        rank = tree_entry["rank"]
        from_level = current_level
        sp_cost = calculate_sp_for_level(rank, 5) - (
            calculate_sp_for_level(rank, from_level) if from_level > 0 else 0
        )
        sp_per_min = calculate_sp_per_minute(
            tree_entry.get("primary_attribute"),
            tree_entry.get("secondary_attribute"),
            attrs,
        )
        training_seconds = int(math.ceil((sp_cost / max(sp_per_min, 1)) * 60))
        eff_score = effectiveness_per_sp(
            skill_name, from_level, 5, rank, detected_roles, efficacy_rules
        )

        phase3_candidates.append(
            {
                "skill_name": skill_name,
                "from_level": from_level,
                "to_level": 5,
                "rank": rank,
                "training_seconds": training_seconds,
                "training_formatted": format_training_time(training_seconds),
                "reason": "Final level: hull/prerequisite bonuses",
                "scoring_bucket": "role_support",
                "effectiveness_per_sp": eff_score,
                "primary_attribute": tree_entry.get("primary_attribute"),
                "secondary_attribute": tree_entry.get("secondary_attribute"),
            }
        )

    # Re-sort after adding Phase 1 overflow
    phase3_candidates.sort(key=lambda s: (-s.get("effectiveness_per_sp", 0), s["skill_name"]))

    # =================================================================
    # Excluded skills (from scope_skills_to_roles)
    # =================================================================
    _, excluded_skills = scope_skills_to_roles(
        full_tree, direct_requirement_names, detected_roles, efficacy_rules
    )
    # Remove injected prerequisites from excluded list
    injected_names = {
        s["skill_name"] for s in phase2_skills if s.get("scoring_bucket") == "injected_prerequisite"
    }
    excluded_skills = [e for e in excluded_skills if e["skill_name"] not in injected_names]

    # =================================================================
    # Compute efficacy at each phase boundary
    # =================================================================
    # Build target levels: all role-relevant skills at V
    target_levels = dict.fromkeys(all_role_relevant, 5)

    # Phase 1 end
    p1_levels = dict(current)
    for s in phase1_skills:
        p1_levels[s["skill_name"]] = s["to_level"]
    for skill_name, level in phase1_skill_levels.items():
        p1_levels[skill_name] = max(p1_levels.get(skill_name, 0), level)

    efficacy_p1 = calculate_minmax_efficacy(
        p1_levels, target_levels, detected_roles, efficacy_rules
    )

    # Phase 2 end
    p2_levels = dict(p1_levels)
    for s in phase2_skills:
        p2_levels[s["skill_name"]] = max(p2_levels.get(s["skill_name"], 0), s["to_level"])

    efficacy_p2 = calculate_minmax_efficacy(
        p2_levels, target_levels, detected_roles, efficacy_rules
    )

    # Phase 3 end = 100% by definition
    efficacy_p3 = 100.0

    # =================================================================
    # Build output
    # =================================================================
    # Strip internal fields from output
    def _clean_skill(s: dict) -> dict:
        return {k: v for k, v in s.items() if k not in ("primary_attribute", "secondary_attribute")}

    phase1_total = sum(s["training_seconds"] for s in phase1_skills)
    phase2_total = sum(s["training_seconds"] for s in phase2_skills)
    phase3_total = sum(s["training_seconds"] for s in phase3_candidates)

    phases = []

    if phase1_skills:
        phases.append(
            {
                "phase": 1,
                "name": "Get Online",
                "description": "SDE prerequisites to board ship",
                "skills": [_clean_skill(s) for s in phase1_skills],
                "phase_total_seconds": phase1_total,
                "phase_total_formatted": format_training_time(phase1_total),
                "efficacy_at_phase_end": efficacy_p1,
            }
        )

    if phase2_skills:
        phases.append(
            {
                "phase": 2,
                "name": "Get Effective",
                "description": "Breakpoints and multipliers ordered by impact tier, then by effectiveness/SP",
                "skills": [_clean_skill(s) for s in phase2_skills],
                "phase_total_seconds": phase2_total,
                "phase_total_formatted": format_training_time(phase2_total),
                "efficacy_at_phase_end": efficacy_p2,
            }
        )

    if phase3_candidates:
        phases.append(
            {
                "phase": 3,
                "name": "Get Maximal",
                "description": "Remaining role-relevant skills to V",
                "skills": [_clean_skill(s) for s in phase3_candidates],
                "phase_total_seconds": phase3_total,
                "phase_total_formatted": format_training_time(phase3_total),
                "efficacy_at_phase_end": efficacy_p3,
            }
        )

    total_seconds = phase1_total + phase2_total + phase3_total

    return {
        "detected_roles": detected_roles,
        "phases": phases,
        "total_training_seconds": total_seconds,
        "total_training_formatted": format_training_time(total_seconds),
        "excluded_skills": excluded_skills,
        "warnings": warnings,
    }


# =============================================================================
# Standalone Implementation (for dispatcher)
# =============================================================================


async def _minmax_plan_impl(
    item: str,
    roles: list[str] | None = None,
    current_skills: dict | None = None,
    attributes: dict | None = None,
) -> dict:
    """
    Generate a min-max phased skill plan for an item.

    Standalone implementation callable by dispatcher.

    Args:
        item: Item name (ship, module, or skill) — case-insensitive
        roles: Optional override for auto-detected roles
        current_skills: Optional dict of current skill levels
        attributes: Optional character attributes for time calculation

    Returns:
        MinMax plan result dict
    """
    db = get_market_database()
    conn = db._get_connection()
    query_service = get_sde_query_service()

    # Normalize query
    query = item.strip()
    query_lower = query.lower()

    # Look up item
    cursor = conn.execute(
        """
        SELECT t.type_id, t.type_name, c.category_name, t.category_id, g.group_name
        FROM types t
        LEFT JOIN categories c ON t.category_id = c.category_id
        LEFT JOIN groups g ON t.group_id = g.group_id
        WHERE t.type_name_lower = ?
        LIMIT 1
        """,
        (query_lower,),
    )
    row = cursor.fetchone()

    if not row:
        # Try fuzzy match
        cursor = conn.execute(
            """
            SELECT t.type_id, t.type_name, c.category_name, t.category_id, g.group_name
            FROM types t
            LEFT JOIN categories c ON t.category_id = c.category_id
            LEFT JOIN groups g ON t.group_id = g.group_id
            WHERE t.type_name_lower LIKE ?
            AND t.published = 1
            ORDER BY length(t.type_name)
            LIMIT 1
            """,
            (f"{query_lower}%",),
        )
        row = cursor.fetchone()

    if not row:
        return {
            "item": query,
            "found": False,
            "error": f"Item '{query}' not found in SDE.",
        }

    type_id, type_name, category_name, _category_id, group_name = row
    warnings: list[str] = []

    # Get full prerequisite tree
    tree_data = query_service.get_full_skill_tree(type_id)
    full_tree: list[dict] = []

    for skill_id, skill_name, level, rank in tree_data:
        skill_attrs = query_service.get_skill_attributes(skill_id)
        full_tree.append(
            {
                "skill_id": skill_id,
                "skill_name": skill_name,
                "required_level": level,
                "rank": rank,
                "primary_attribute": skill_attrs.primary_attribute if skill_attrs else None,
                "secondary_attribute": skill_attrs.secondary_attribute if skill_attrs else None,
            }
        )

    # Get direct requirements (for SDE Direct Requirement Inclusion Rule)
    direct_reqs = query_service.get_type_skill_requirements(type_id)
    direct_requirement_names = {req.skill_name for req in direct_reqs}

    # Detect or validate roles
    if roles is not None:
        # Validate provided roles
        efficacy_rules = load_efficacy_rules()
        valid_roles = set(efficacy_rules.get("ship_roles", {}).keys())
        invalid = [r for r in roles if r not in valid_roles]
        if invalid:
            return {
                "item": type_name,
                "found": False,
                "error": f"Invalid role(s): {invalid}. Valid roles: {sorted(valid_roles)}",
            }
        detected_roles = roles
    else:
        # Auto-detect from ship
        detected_roles = detect_ship_roles(group_name, type_name) if category_name == "Ship" else []

    if not detected_roles:
        warnings.append(
            "No roles detected. The plan will contain only SDE prerequisites (Phase 1). "
            "Specify roles manually with the 'roles' parameter for Phase 2/3 optimization."
        )

    # Load YAML data
    efficacy_rules = load_efficacy_rules()
    breakpoint_skills_data = load_breakpoint_skills()

    # Add support skills from detected roles to the tree
    if detected_roles:
        role_skills = _build_role_skill_set(detected_roles, efficacy_rules)
        existing_skill_names = {s["skill_name"] for s in full_tree}

        for skill_name in role_skills:
            if skill_name in existing_skill_names:
                continue
            # Look up skill attributes
            sde_attrs = _lookup_skill_attrs(skill_name, query_service, conn)
            if sde_attrs:
                full_tree.append(
                    {
                        "skill_id": sde_attrs["skill_id"],
                        "skill_name": skill_name,
                        "required_level": 0,  # Support skill, not SDE required
                        "rank": sde_attrs["rank"],
                        "primary_attribute": sde_attrs.get("primary_attribute"),
                        "secondary_attribute": sde_attrs.get("secondary_attribute"),
                    }
                )

        # Also add direct requirements that might not be in the tree
        for req_name in direct_requirement_names:
            if req_name in existing_skill_names or req_name in {s["skill_name"] for s in full_tree}:
                continue
            sde_attrs = _lookup_skill_attrs(req_name, query_service, conn)
            if sde_attrs:
                full_tree.append(
                    {
                        "skill_id": sde_attrs["skill_id"],
                        "skill_name": req_name,
                        "required_level": 0,
                        "rank": sde_attrs["rank"],
                        "primary_attribute": sde_attrs.get("primary_attribute"),
                        "secondary_attribute": sde_attrs.get("secondary_attribute"),
                    }
                )

    # Generate the plan
    plan = generate_minmax_plan(
        full_tree=full_tree,
        direct_requirement_names=direct_requirement_names,
        detected_roles=detected_roles,
        efficacy_rules=efficacy_rules,
        breakpoint_skills=breakpoint_skills_data,
        current_skills=current_skills,
        attributes=attributes,
        query_service=query_service,
        db_conn=conn,
    )

    # Merge warnings
    plan_warnings = plan.get("warnings", [])
    all_warnings = warnings + plan_warnings

    return {
        "item": type_name,
        "item_category": category_name,
        "found": True,
        "detected_roles": plan["detected_roles"],
        "phases": plan["phases"],
        "total_training_seconds": plan["total_training_seconds"],
        "total_training_formatted": plan["total_training_formatted"],
        "excluded_skills": plan["excluded_skills"],
        "warnings": all_warnings,
    }
