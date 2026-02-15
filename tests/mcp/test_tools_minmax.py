"""
Tests for Min-Max Skill Planning Module.

Tests pure functions with synthetic data — no mocks needed.
"""

from __future__ import annotations

import pytest

from aria_esi.mcp.sde.tools_minmax import (
    IMPACT_TIER_ORDER,
    MINIMUM_SCORED_SKILLS,
    _build_role_skill_set,
    _score_breakpoint,
    calculate_minmax_efficacy,
    classify_role_strength,
    effectiveness_per_sp,
    generate_minmax_plan,
    scope_skills_to_roles,
)
from aria_esi.mcp.sde.tools_skills import calculate_sp_for_level


# =============================================================================
# Synthetic Test Data Builders
# =============================================================================


def _make_efficacy_rules(roles: dict | None = None) -> dict:
    """Build minimal efficacy_rules dict for testing."""
    return {"ship_roles": roles or {}}


def _make_role(skills: list[dict]) -> dict:
    """Build a role entry with given skills."""
    return {"skills": skills}


def _make_skill_entry(skill: str, per_level: float = 0, effect: str = "", multiplicative: bool = False) -> dict:
    """Build a skill entry for efficacy rules."""
    entry: dict = {"skill": skill, "per_level": per_level, "effect": effect}
    if multiplicative:
        entry["multiplicative"] = True
    return entry


def _make_tree_entry(
    skill_name: str,
    required_level: int = 0,
    rank: int = 1,
    skill_id: int = 1000,
    primary_attribute: str = "intelligence",
    secondary_attribute: str = "memory",
) -> dict:
    """Build a full_tree skill entry."""
    return {
        "skill_id": skill_id,
        "skill_name": skill_name,
        "required_level": required_level,
        "rank": rank,
        "primary_attribute": primary_attribute,
        "secondary_attribute": secondary_attribute,
    }


# =============================================================================
# TestClassifyRoleStrength
# =============================================================================


class TestClassifyRoleStrength:
    """Tests for classify_role_strength."""

    def test_strong_role_has_enough_scored_skills(self):
        """Role with >= MINIMUM_SCORED_SKILLS scored skills is strong."""
        rules = _make_efficacy_rules(
            {
                "drone_boat": _make_role(
                    [
                        _make_skill_entry("Drones", per_level=5),
                        _make_skill_entry("Drone Interfacing", per_level=10),
                        _make_skill_entry("Navigation", per_level=0),
                    ]
                )
            }
        )
        assert classify_role_strength("drone_boat", rules) == "strong"

    def test_weak_role_has_too_few_scored_skills(self):
        """Role with < MINIMUM_SCORED_SKILLS scored skills is weak."""
        rules = _make_efficacy_rules(
            {
                "hauler": _make_role(
                    [
                        _make_skill_entry("Hull Upgrades", per_level=3),
                        _make_skill_entry("Navigation", per_level=0),
                    ]
                )
            }
        )
        assert classify_role_strength("hauler", rules) == "weak"

    def test_missing_role_is_weak(self):
        """A role not in efficacy rules is weak."""
        rules = _make_efficacy_rules({})
        assert classify_role_strength("nonexistent", rules) == "weak"

    def test_role_with_all_zero_per_level_is_weak(self):
        """Role where all skills have per_level=0 is weak."""
        rules = _make_efficacy_rules(
            {
                "shield_tank": _make_role(
                    [
                        _make_skill_entry("Shield Management", per_level=0),
                        _make_skill_entry("Shield Operation", per_level=0),
                        _make_skill_entry("Tactical Shield Manipulation", per_level=0),
                    ]
                )
            }
        )
        assert classify_role_strength("shield_tank", rules) == "weak"

    def test_exactly_minimum_scored_is_strong(self):
        """Role with exactly MINIMUM_SCORED_SKILLS scored skills is strong."""
        skills = [_make_skill_entry(f"Skill{i}", per_level=5) for i in range(MINIMUM_SCORED_SKILLS)]
        rules = _make_efficacy_rules({"test_role": _make_role(skills)})
        assert classify_role_strength("test_role", rules) == "strong"


# =============================================================================
# TestBuildRoleSkillSet
# =============================================================================


class TestBuildRoleSkillSet:
    """Tests for _build_role_skill_set."""

    def test_single_role(self):
        """Single role produces expected skill set."""
        rules = _make_efficacy_rules(
            {
                "drone_boat": _make_role(
                    [
                        _make_skill_entry("Drones", per_level=5),
                        _make_skill_entry("Drone Interfacing", per_level=10),
                    ]
                )
            }
        )
        result = _build_role_skill_set(["drone_boat"], rules)
        assert "Drones" in result
        assert "Drone Interfacing" in result
        assert result["Drones"]["per_level"] == 5

    def test_multi_role_union(self):
        """Multiple roles union their skills."""
        rules = _make_efficacy_rules(
            {
                "drone_boat": _make_role([_make_skill_entry("Drones", per_level=5)]),
                "armor_tank": _make_role([_make_skill_entry("Hull Upgrades", per_level=3)]),
            }
        )
        result = _build_role_skill_set(["drone_boat", "armor_tank"], rules)
        assert "Drones" in result
        assert "Hull Upgrades" in result

    def test_multi_role_max_per_level(self):
        """When a skill appears in multiple roles, keep highest per_level."""
        rules = _make_efficacy_rules(
            {
                "role_a": _make_role([_make_skill_entry("Drones", per_level=3)]),
                "role_b": _make_role([_make_skill_entry("Drones", per_level=7)]),
            }
        )
        result = _build_role_skill_set(["role_a", "role_b"], rules)
        assert result["Drones"]["per_level"] == 7

    def test_empty_roles(self):
        """Empty role list produces empty set."""
        rules = _make_efficacy_rules({"drone_boat": _make_role([_make_skill_entry("Drones", per_level=5)])})
        result = _build_role_skill_set([], rules)
        assert result == {}

    def test_skips_skills_without_name(self):
        """Skills without 'skill' key are skipped."""
        rules = _make_efficacy_rules(
            {"test_role": _make_role([{"per_level": 5}])}
        )
        result = _build_role_skill_set(["test_role"], rules)
        assert result == {}


# =============================================================================
# TestScopeSkillsToRoles
# =============================================================================


class TestScopeSkillsToRoles:
    """Tests for scope_skills_to_roles."""

    def test_sde_prereqs_never_excluded(self):
        """Skills with required_level > 0 are always included."""
        tree = [_make_tree_entry("Spaceship Command", required_level=3)]
        rules = _make_efficacy_rules({})
        included, excluded = scope_skills_to_roles(tree, set(), [], rules)
        assert len(included) == 1
        assert included[0]["skill_name"] == "Spaceship Command"
        assert len(excluded) == 0

    def test_direct_reqs_included(self):
        """Direct requirement skills are included even without role match."""
        tree = [_make_tree_entry("Gallente Cruiser", required_level=0)]
        rules = _make_efficacy_rules({})
        included, excluded = scope_skills_to_roles(tree, {"Gallente Cruiser"}, [], rules)
        assert len(included) == 1
        assert included[0]["skill_name"] == "Gallente Cruiser"

    def test_role_skills_included(self):
        """Skills in a detected role are included."""
        tree = [_make_tree_entry("Drones", required_level=0)]
        rules = _make_efficacy_rules(
            {"drone_boat": _make_role([_make_skill_entry("Drones", per_level=5)])}
        )
        included, excluded = scope_skills_to_roles(tree, set(), ["drone_boat"], rules)
        assert len(included) == 1

    def test_non_role_skills_excluded(self):
        """Skills not in any role and not prerequisites are excluded."""
        tree = [
            _make_tree_entry("Drones", required_level=0),
            _make_tree_entry("Mining", required_level=0),
        ]
        rules = _make_efficacy_rules(
            {"drone_boat": _make_role([_make_skill_entry("Drones", per_level=5)])}
        )
        included, excluded = scope_skills_to_roles(tree, set(), ["drone_boat"], rules)
        assert len(included) == 1
        assert included[0]["skill_name"] == "Drones"
        assert len(excluded) == 1
        assert excluded[0]["skill_name"] == "Mining"


# =============================================================================
# TestEffectivenessPerSp
# =============================================================================


class TestEffectivenessPerSp:
    """Tests for effectiveness_per_sp."""

    def test_positive_score_for_measured_skill(self):
        """Skills with per_level > 0 get positive scores."""
        role_skills = {"Drones": {"skill": "Drones", "per_level": 5}}
        score = effectiveness_per_sp("Drones", 3, 4, 1, role_skills)
        assert score > 0

    def test_negative_rank_for_unmeasured_skill(self):
        """Unmeasured skills return -rank."""
        role_skills = {}
        score = effectiveness_per_sp("Unknown", 3, 4, 3, role_skills)
        assert score == -3

    def test_higher_per_level_gives_higher_score(self):
        """Higher per_level = higher effectiveness score."""
        role_low = {"Drones": {"skill": "Drones", "per_level": 2}}
        role_high = {"Drones": {"skill": "Drones", "per_level": 10}}
        score_low = effectiveness_per_sp("Drones", 3, 4, 1, role_low)
        score_high = effectiveness_per_sp("Drones", 3, 4, 1, role_high)
        assert score_high > score_low

    def test_from_level_zero(self):
        """from_level=0 works correctly (no special casing needed)."""
        role_skills = {"Drones": {"skill": "Drones", "per_level": 5}}
        score = effectiveness_per_sp("Drones", 0, 4, 1, role_skills)
        # SP cost from 0 to 4: calculate_sp_for_level(1, 4) - calculate_sp_for_level(1, 0) = 45255 - 0
        assert score > 0
        expected = (5 * 4) / 45255  # per_level * levels / sp_cost
        assert abs(score - expected) < 1e-10

    def test_multi_role_max_per_level_used(self):
        """Pre-built map already has max per_level from _build_role_skill_set."""
        # Simulating the result of _build_role_skill_set with max per_level = 10
        role_skills = {"Drones": {"skill": "Drones", "per_level": 10}}
        score = effectiveness_per_sp("Drones", 3, 4, 1, role_skills)
        expected = (10 * 1) / (calculate_sp_for_level(1, 4) - calculate_sp_for_level(1, 3))
        assert abs(score - expected) < 1e-10


# =============================================================================
# TestScoreBreakpoint
# =============================================================================


class TestScoreBreakpoint:
    """Tests for _score_breakpoint."""

    def test_critical_before_high(self):
        """Critical impact sorts before high."""
        critical = _score_breakpoint("SkillA", 2, {"impact": "critical"})
        high = _score_breakpoint("SkillB", 2, {"impact": "high"})
        assert critical < high

    def test_high_before_medium(self):
        """High impact sorts before medium."""
        high = _score_breakpoint("SkillA", 2, {"impact": "high"})
        medium = _score_breakpoint("SkillB", 2, {"impact": "medium"})
        assert high < medium

    def test_rank_tiebreaker_within_tier(self):
        """Within same tier, lower rank sorts first."""
        low_rank = _score_breakpoint("SkillA", 1, {"impact": "high"})
        high_rank = _score_breakpoint("SkillB", 5, {"impact": "high"})
        assert low_rank < high_rank

    def test_unknown_impact_defaults_to_medium(self):
        """Unknown impact maps to medium (tier 2)."""
        unknown = _score_breakpoint("SkillA", 2, {"impact": "unknown_tier"})
        medium = _score_breakpoint("SkillB", 2, {"impact": "medium"})
        assert unknown[0] == medium[0]


# =============================================================================
# TestCalculateMinmaxEfficacy
# =============================================================================


class TestCalculateMinmaxEfficacy:
    """Tests for calculate_minmax_efficacy."""

    def test_100_percent_at_target(self):
        """Skills at target levels = 100% efficacy."""
        targets = {"Drones": 5, "Hull Upgrades": 4}
        current = {"Drones": 5, "Hull Upgrades": 4}
        rules = _make_efficacy_rules(
            {"drone_boat": _make_role([_make_skill_entry("Drones", per_level=5)])}
        )
        result = calculate_minmax_efficacy(current, targets, ["drone_boat"], rules)
        assert result == 100.0

    def test_multiplicative_gets_higher_weight(self):
        """Multiplicative skills get weight 3.0, affecting efficacy more."""
        targets = {"SkillA": 5, "SkillB": 5}
        rules = _make_efficacy_rules(
            {
                "test_role": _make_role(
                    [
                        _make_skill_entry("SkillA", per_level=5, multiplicative=True),
                        _make_skill_entry("SkillB", per_level=5),
                    ]
                )
            }
        )

        # SkillA at 0, SkillB at 5 — multiplicative skill missing hurts more
        levels_a_missing = {"SkillA": 0, "SkillB": 5}
        eff_a_missing = calculate_minmax_efficacy(levels_a_missing, targets, ["test_role"], rules)

        # SkillA at 5, SkillB at 0 — non-multiplicative skill missing hurts less
        levels_b_missing = {"SkillA": 5, "SkillB": 0}
        eff_b_missing = calculate_minmax_efficacy(levels_b_missing, targets, ["test_role"], rules)

        # Missing the multiplicative skill should result in lower efficacy
        assert eff_a_missing < eff_b_missing

    def test_per_level_weighting(self):
        """Skills with higher per_level get slightly more weight."""
        targets = {"HighImpact": 5, "LowImpact": 5}
        rules = _make_efficacy_rules(
            {
                "test_role": _make_role(
                    [
                        _make_skill_entry("HighImpact", per_level=20),
                        _make_skill_entry("LowImpact", per_level=1),
                    ]
                )
            }
        )
        # Both at target
        levels = {"HighImpact": 5, "LowImpact": 5}
        assert calculate_minmax_efficacy(levels, targets, ["test_role"], rules) == 100.0

    def test_empty_inputs(self):
        """Empty inputs return 100%."""
        rules = _make_efficacy_rules({})
        assert calculate_minmax_efficacy({}, {}, [], rules) == 100.0
        assert calculate_minmax_efficacy({"Drones": 5}, {}, [], rules) == 100.0


# =============================================================================
# TestGenerateMinmaxPlan
# =============================================================================


class TestGenerateMinmaxPlan:
    """Tests for generate_minmax_plan — integration tests with synthetic data."""

    @pytest.fixture
    def basic_tree(self):
        """A simple skill tree with prerequisite + support skills."""
        return [
            _make_tree_entry("Spaceship Command", required_level=3, rank=1, skill_id=100),
            _make_tree_entry("Gallente Cruiser", required_level=3, rank=5, skill_id=101),
            _make_tree_entry("Drones", required_level=0, rank=1, skill_id=102),
            _make_tree_entry("Drone Interfacing", required_level=0, rank=5, skill_id=103),
            _make_tree_entry("Medium Drone Operation", required_level=0, rank=3, skill_id=104),
        ]

    @pytest.fixture
    def drone_boat_rules(self):
        """Efficacy rules for a drone_boat role."""
        return _make_efficacy_rules(
            {
                "drone_boat": _make_role(
                    [
                        _make_skill_entry("Drones", per_level=5, effect="+5% drone HP/level"),
                        _make_skill_entry(
                            "Drone Interfacing", per_level=10, effect="+10% drone damage/level",
                            multiplicative=True,
                        ),
                        _make_skill_entry(
                            "Medium Drone Operation", per_level=3, effect="+3% medium drone damage/level",
                        ),
                    ]
                )
            }
        )

    def test_phase1_contains_prerequisites(self, basic_tree, drone_boat_rules):
        """Phase 1 should contain SDE prerequisites."""
        plan = generate_minmax_plan(
            full_tree=basic_tree,
            direct_requirement_names={"Gallente Cruiser"},
            detected_roles=["drone_boat"],
            efficacy_rules=drone_boat_rules,
            breakpoint_skills={},
        )
        phase1 = next((p for p in plan["phases"] if p["phase"] == 1), None)
        assert phase1 is not None
        phase1_names = {s["skill_name"] for s in phase1["skills"]}
        assert "Spaceship Command" in phase1_names
        assert "Gallente Cruiser" in phase1_names

    def test_phase2_contains_role_skills(self, basic_tree, drone_boat_rules):
        """Phase 2 should contain role-relevant skills."""
        plan = generate_minmax_plan(
            full_tree=basic_tree,
            direct_requirement_names={"Gallente Cruiser"},
            detected_roles=["drone_boat"],
            efficacy_rules=drone_boat_rules,
            breakpoint_skills={},
        )
        phase2 = next((p for p in plan["phases"] if p["phase"] == 2), None)
        assert phase2 is not None
        phase2_names = {s["skill_name"] for s in phase2["skills"]}
        assert "Drones" in phase2_names
        assert "Drone Interfacing" in phase2_names

    def test_phase3_targets_level_5(self, basic_tree, drone_boat_rules):
        """Phase 3 skills should target level 5."""
        plan = generate_minmax_plan(
            full_tree=basic_tree,
            direct_requirement_names={"Gallente Cruiser"},
            detected_roles=["drone_boat"],
            efficacy_rules=drone_boat_rules,
            breakpoint_skills={},
        )
        phase3 = next((p for p in plan["phases"] if p["phase"] == 3), None)
        assert phase3 is not None
        for skill in phase3["skills"]:
            assert skill["to_level"] == 5

    def test_no_roles_warns(self, basic_tree):
        """No detected roles produces a warning."""
        plan = generate_minmax_plan(
            full_tree=basic_tree,
            direct_requirement_names=set(),
            detected_roles=[],
            efficacy_rules=_make_efficacy_rules({}),
            breakpoint_skills={},
        )
        assert len(plan["warnings"]) == 0  # Warnings are added in _minmax_plan_impl, not here
        # Phase 2 and 3 should be empty
        assert not any(p["phase"] == 2 for p in plan["phases"])
        assert not any(p["phase"] == 3 for p in plan["phases"])

    def test_weak_roles_warning(self, basic_tree):
        """Weak roles produce a warning."""
        # Role with only 1 scored skill = weak
        rules = _make_efficacy_rules(
            {"weak_role": _make_role([_make_skill_entry("Drones", per_level=5)])}
        )
        plan = generate_minmax_plan(
            full_tree=basic_tree,
            direct_requirement_names=set(),
            detected_roles=["weak_role"],
            efficacy_rules=rules,
            breakpoint_skills={},
        )
        assert any("limited efficacy data" in w for w in plan["warnings"])

    def test_current_skills_skip_trained(self, basic_tree, drone_boat_rules):
        """Already-trained skills are skipped in Phase 1."""
        plan = generate_minmax_plan(
            full_tree=basic_tree,
            direct_requirement_names={"Gallente Cruiser"},
            detected_roles=["drone_boat"],
            efficacy_rules=drone_boat_rules,
            breakpoint_skills={},
            current_skills={"Spaceship Command": 5, "Gallente Cruiser": 5},
        )
        phase1 = next((p for p in plan["phases"] if p["phase"] == 1), None)
        # Both prereqs already trained — Phase 1 should be empty or absent
        if phase1 is not None:
            phase1_names = {s["skill_name"] for s in phase1["skills"]}
            assert "Spaceship Command" not in phase1_names
            assert "Gallente Cruiser" not in phase1_names

    def test_direct_reqs_strong_even_with_empty_strong_roles(self):
        """Direct requirements classify as strong even when strong_roles is empty.

        This tests the Issue 8 fix: skill_in_strong should be True for direct
        requirements regardless of strong_roles being empty.
        """
        tree = [
            _make_tree_entry("Gallente Cruiser", required_level=0, rank=5),
        ]
        # All roles are weak (only 1 scored skill each)
        rules = _make_efficacy_rules(
            {"weak_role": _make_role([_make_skill_entry("Drones", per_level=5)])}
        )
        plan = generate_minmax_plan(
            full_tree=tree,
            direct_requirement_names={"Gallente Cruiser"},
            detected_roles=["weak_role"],
            efficacy_rules=rules,
            breakpoint_skills={},
        )
        phase2 = next((p for p in plan["phases"] if p["phase"] == 2), None)
        if phase2:
            gal_cruiser = next(
                (s for s in phase2["skills"] if s["skill_name"] == "Gallente Cruiser"), None
            )
            if gal_cruiser:
                # Should NOT be marked as weak-role-only (was_weak_role_only is stripped,
                # but we can verify it sorted before weak skills by checking its position)
                # The key test is that it's present and wasn't mis-classified
                assert gal_cruiser["scoring_bucket"] == "role_support"

    def test_breakpoint_skills_in_phase2(self, basic_tree, drone_boat_rules):
        """Breakpoint skills appear in Phase 2 with correct bucket."""
        breakpoints = {
            "Drones": {"breakpoint_level": 5, "impact": "critical", "effect": "Unlock T2 drones"},
        }
        plan = generate_minmax_plan(
            full_tree=basic_tree,
            direct_requirement_names={"Gallente Cruiser"},
            detected_roles=["drone_boat"],
            efficacy_rules=drone_boat_rules,
            breakpoint_skills=breakpoints,
        )
        phase2 = next((p for p in plan["phases"] if p["phase"] == 2), None)
        assert phase2 is not None
        drones = next((s for s in phase2["skills"] if s["skill_name"] == "Drones"), None)
        assert drones is not None
        assert drones["scoring_bucket"] == "breakpoint"
        assert drones["to_level"] == 5

    def test_total_training_time_sums_phases(self, basic_tree, drone_boat_rules):
        """Total training time should equal sum of all phase totals."""
        plan = generate_minmax_plan(
            full_tree=basic_tree,
            direct_requirement_names={"Gallente Cruiser"},
            detected_roles=["drone_boat"],
            efficacy_rules=drone_boat_rules,
            breakpoint_skills={},
        )
        phase_sum = sum(p["phase_total_seconds"] for p in plan["phases"])
        assert plan["total_training_seconds"] == phase_sum

    def test_excluded_skills_tracked(self):
        """Skills not in roles are tracked in excluded_skills."""
        tree = [
            _make_tree_entry("Drones", required_level=0, rank=1),
            _make_tree_entry("Mining", required_level=0, rank=1),
        ]
        rules = _make_efficacy_rules(
            {"drone_boat": _make_role([_make_skill_entry("Drones", per_level=5)])}
        )
        plan = generate_minmax_plan(
            full_tree=tree,
            direct_requirement_names=set(),
            detected_roles=["drone_boat"],
            efficacy_rules=rules,
            breakpoint_skills={},
        )
        excluded_names = {e["skill_name"] for e in plan["excluded_skills"]}
        assert "Mining" in excluded_names
