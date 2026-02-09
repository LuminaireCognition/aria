"""
Tests for Activity Skill Planning MCP Tools.

Tests activity loading, searching, and skill plan generation.
"""

from __future__ import annotations

from aria_esi.mcp.sde.tools_activities import (
    get_activity,
    load_activities,
    resolve_parameters,
    search_activities,
)


class TestActivityLoading:
    """Tests for activity loading from YAML."""

    def test_load_activities_returns_dict(self):
        """Activities load as a dictionary."""
        activities = load_activities()
        assert isinstance(activities, dict)

    def test_activities_have_required_fields(self):
        """Activities have display_name and category."""
        activities = load_activities()
        for activity_id, data in activities.items():
            assert "display_name" in data, f"{activity_id} missing display_name"
            assert "category" in data, f"{activity_id} missing category"

    def test_gas_huffing_activity_exists(self):
        """Gas huffing activity is defined."""
        activity = get_activity("gas_huffing")
        assert activity is not None
        assert activity.get("display_name") == "Gas Cloud Harvesting"
        assert activity.get("category") == "mining"

    def test_activity_has_skill_tiers(self):
        """Activities have minimum, easy_80, and full tiers."""
        activity = get_activity("gas_huffing")
        assert activity is not None
        assert "minimum" in activity
        assert "easy_80" in activity
        assert "full" in activity

    def test_activity_skills_have_level(self):
        """Skill entries have skill name and level."""
        activity = get_activity("gas_huffing")
        assert activity is not None

        for tier in ["minimum", "easy_80", "full"]:
            skills = activity.get(tier, [])
            for skill in skills:
                assert "skill" in skill, f"Missing skill name in {tier}"
                assert "level" in skill, f"Missing level in {tier}"


class TestActivitySearch:
    """Tests for activity search functionality."""

    def test_search_by_name(self):
        """Search finds activities by name."""
        results = search_activities("gas")
        assert len(results) > 0
        activity_ids = [r["activity_id"] for r in results]
        assert "gas_huffing" in activity_ids

    def test_search_by_category(self):
        """Search finds activities by category."""
        results = search_activities("mining")
        assert len(results) > 0
        # Should find multiple mining activities
        categories = [r.get("category") for r in results]
        assert "mining" in categories

    def test_search_case_insensitive(self):
        """Search is case-insensitive."""
        results_lower = search_activities("mining")
        results_upper = search_activities("MINING")
        assert len(results_lower) == len(results_upper)

    def test_search_by_description(self):
        """Search finds activities by description keywords."""
        results = search_activities("asteroid")
        assert len(results) > 0

    def test_search_no_results(self):
        """Search returns empty list for no matches."""
        results = search_activities("xyznonexistent")
        assert results == []


class TestParameterResolution:
    """Tests for parameterized activity handling."""

    def test_resolve_simple_parameter(self):
        """Simple parameter replacement works."""
        skills = [
            {"skill": "${field}", "level": 2},
            {"skill": "Science", "level": 5},
        ]
        params = {"field": "Mechanical Engineering"}
        resolved = resolve_parameters(skills, params)

        assert resolved[0]["skill"] == "Mechanical Engineering"
        assert resolved[1]["skill"] == "Science"

    def test_missing_parameter_marked(self):
        """Missing parameters are marked as required."""
        skills = [
            {"skill": "${field}", "level": 2},
        ]
        params = {}  # No field provided
        resolved = resolve_parameters(skills, params)

        assert "parameter_required" in resolved[0]
        assert resolved[0]["parameter_required"] == "field"

    def test_non_parameterized_unchanged(self):
        """Non-parameterized skills pass through unchanged."""
        skills = [
            {"skill": "Mining", "level": 4},
            {"skill": "Astrogeology", "level": 3},
        ]
        resolved = resolve_parameters(skills, {})

        assert resolved[0]["skill"] == "Mining"
        assert resolved[1]["skill"] == "Astrogeology"


class TestActivityCategories:
    """Tests for activity categorization."""

    def test_mining_category_exists(self):
        """Mining activities exist."""
        results = search_activities("mining")
        mining_activities = [r for r in results if r.get("category") == "mining"]
        assert len(mining_activities) >= 2  # At least basic and barge

    def test_exploration_category_exists(self):
        """Exploration activities exist."""
        results = search_activities("exploration")
        assert len(results) > 0

    def test_combat_category_exists(self):
        """Combat activities exist."""
        activities = load_activities()
        combat_activities = [
            a for a in activities.values() if a.get("category") == "combat"
        ]
        assert len(combat_activities) > 0

    def test_industry_category_exists(self):
        """Industry activities exist."""
        activities = load_activities()
        industry_activities = [
            a for a in activities.values() if a.get("category") == "industry"
        ]
        assert len(industry_activities) > 0


class TestActivityContent:
    """Tests for specific activity content."""

    def test_missions_l3_has_ships(self):
        """L3 missions activity has ship recommendations."""
        activity = get_activity("missions_l3")
        assert activity is not None
        assert "ships" in activity
        ships = activity["ships"]
        assert "recommended" in ships

    def test_research_agents_has_parameters(self):
        """R&D agent activity has parameters defined."""
        activity = get_activity("research_agents")
        assert activity is not None
        assert "parameters" in activity
        params = activity["parameters"]
        assert len(params) > 0
        # Should have field parameter
        param_names = [p.get("name") for p in params]
        assert "field" in param_names

    def test_activity_notes_are_lists(self):
        """Activity notes are stored as lists."""
        activity = get_activity("gas_huffing")
        assert activity is not None
        if "notes" in activity:
            assert isinstance(activity["notes"], list)

    def test_exploration_wormhole_has_cloaking(self):
        """Wormhole exploration includes cloaking skill."""
        activity = get_activity("exploration_wormhole")
        assert activity is not None

        # Check that cloaking appears in some tier
        all_skills = []
        for tier in ["minimum", "easy_80", "full"]:
            skills = activity.get(tier, [])
            all_skills.extend([s.get("skill") for s in skills])

        assert "Cloaking" in all_skills


class TestActivityTiers:
    """Tests for activity tier progression."""

    def test_tier_skill_counts_increase(self):
        """Higher tiers generally have same or more skills."""
        activity = get_activity("mining_basic")
        assert activity is not None

        min_skills = len(activity.get("minimum", []))
        easy_skills = len(activity.get("easy_80", []))
        full_skills = len(activity.get("full", []))

        # Each tier should have at least as many skills as the previous
        assert easy_skills >= min_skills
        assert full_skills >= easy_skills

    def test_tier_levels_increase(self):
        """Higher tiers have same or higher skill levels."""
        activity = get_activity("gas_huffing")
        assert activity is not None

        # Find Gas Cloud Harvesting skill in each tier
        for prev_tier, next_tier in [("minimum", "easy_80"), ("easy_80", "full")]:
            prev_skills = {s["skill"]: s["level"] for s in activity.get(prev_tier, [])}
            next_skills = {s["skill"]: s["level"] for s in activity.get(next_tier, [])}

            for skill, level in prev_skills.items():
                if skill in next_skills:
                    assert (
                        next_skills[skill] >= level
                    ), f"{skill} level decreased from {prev_tier} to {next_tier}"
