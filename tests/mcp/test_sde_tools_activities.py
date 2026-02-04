"""
Tests for SDE activity skill planning MCP tools and utility functions.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from aria_esi.mcp.sde.tools_activities import (
    get_activity,
    load_activities,
    resolve_parameters,
    search_activities,
)


@pytest.fixture(autouse=True)
def clear_activities_cache():
    """Clear the activities cache before each test."""
    import aria_esi.mcp.sde.tools_activities as activities_module

    activities_module._activities_cache = None
    yield
    activities_module._activities_cache = None


@pytest.fixture
def mock_activities():
    """Sample activities for testing."""
    return {
        "gas_huffing": {
            "display_name": "Gas Huffing",
            "category": "mining",
            "description": "Harvest gas clouds in wormholes and low-sec.",
            "minimum": [
                {"skill": "Mining", "level": 1},
            ],
            "easy_80": [
                {"skill": "Mining", "level": 4},
                {"skill": "Gas Cloud Harvesting", "level": 4},
            ],
            "full": [
                {"skill": "Mining", "level": 5},
                {"skill": "Gas Cloud Harvesting", "level": 5},
            ],
        },
        "research_agents": {
            "display_name": "Research Agents",
            "category": "research",
            "description": "Generate datacores through R&D agents.",
            "parameters": [
                {
                    "name": "field",
                    "type": "skill",
                    "options": ["Mechanical Engineering", "Electronic Engineering"],
                }
            ],
            "minimum": [
                {"skill": "${field}", "level": 1},
            ],
        },
        "l3_missions": {
            "display_name": "Level 3 Missions",
            "category": "combat",
            "description": "Run level 3 security missions.",
        },
    }


class TestLoadActivities:
    """Tests for load_activities function."""

    def test_load_returns_dict(self, mock_activities, tmp_path):
        """Should return a dictionary of activities."""
        # Create a mock YAML file
        yaml_content = """
gas_huffing:
  display_name: Gas Huffing
  category: mining
"""
        activities_file = tmp_path / "reference" / "activities" / "skill_plans.yaml"
        activities_file.parent.mkdir(parents=True)
        activities_file.write_text(yaml_content)

        with patch(
            "aria_esi.mcp.sde.tools_activities._get_project_root",
            return_value=tmp_path,
        ):
            result = load_activities()

        assert isinstance(result, dict)
        assert "gas_huffing" in result

    def test_load_caches_result(self, tmp_path):
        """Should cache loaded activities when file unchanged."""
        yaml_content = """
test_activity:
  display_name: Test
"""
        activities_file = tmp_path / "reference" / "activities" / "skill_plans.yaml"
        activities_file.parent.mkdir(parents=True)
        activities_file.write_text(yaml_content)

        with patch(
            "aria_esi.mcp.sde.tools_activities._get_project_root",
            return_value=tmp_path,
        ):
            result1 = load_activities()
            # Load again without modifying file
            result2 = load_activities()

        # Should return same cached dict (no file change)
        assert result1 is result2

    def test_load_reloads_on_file_change(self, tmp_path):
        """Should reload activities when file is modified (hot-reload)."""
        import os
        import time

        yaml_content = """
test_activity:
  display_name: Test
"""
        activities_file = tmp_path / "reference" / "activities" / "skill_plans.yaml"
        activities_file.parent.mkdir(parents=True)
        activities_file.write_text(yaml_content)

        with patch(
            "aria_esi.mcp.sde.tools_activities._get_project_root",
            return_value=tmp_path,
        ):
            result1 = load_activities()
            assert "test_activity" in result1

            # Ensure mtime changes (some filesystems have 1-second resolution)
            time.sleep(0.01)
            # Update mtime by touching the file with new content
            activities_file.write_text("updated_activity:\n  display_name: Updated\n")
            # Force mtime to be newer
            os.utime(activities_file, (time.time() + 1, time.time() + 1))

            result2 = load_activities()

        # Should have reloaded with new content
        assert "updated_activity" in result2
        assert "test_activity" not in result2

    def test_missing_file_returns_empty(self, tmp_path):
        """Should return empty dict if file not found."""
        with patch(
            "aria_esi.mcp.sde.tools_activities._get_project_root",
            return_value=tmp_path,
        ):
            result = load_activities()

        assert result == {}


class TestGetActivity:
    """Tests for get_activity function."""

    def test_get_existing_activity(self, mock_activities):
        """Should return activity by ID."""
        with patch(
            "aria_esi.mcp.sde.tools_activities.load_activities",
            return_value=mock_activities,
        ):
            result = get_activity("gas_huffing")

        assert result is not None
        assert result["display_name"] == "Gas Huffing"

    def test_get_nonexistent_activity(self, mock_activities):
        """Should return None for unknown activity."""
        with patch(
            "aria_esi.mcp.sde.tools_activities.load_activities",
            return_value=mock_activities,
        ):
            result = get_activity("nonexistent")

        assert result is None


class TestSearchActivities:
    """Tests for search_activities function."""

    def test_search_by_id(self, mock_activities):
        """Should match activity ID."""
        with patch(
            "aria_esi.mcp.sde.tools_activities.load_activities",
            return_value=mock_activities,
        ):
            results = search_activities("gas")

        assert len(results) == 1
        assert results[0]["activity_id"] == "gas_huffing"

    def test_search_by_display_name(self, mock_activities):
        """Should match display name."""
        with patch(
            "aria_esi.mcp.sde.tools_activities.load_activities",
            return_value=mock_activities,
        ):
            results = search_activities("Level 3")

        assert len(results) == 1
        assert results[0]["activity_id"] == "l3_missions"

    def test_search_by_category(self, mock_activities):
        """Should match category."""
        with patch(
            "aria_esi.mcp.sde.tools_activities.load_activities",
            return_value=mock_activities,
        ):
            results = search_activities("mining")

        assert len(results) == 1
        assert results[0]["category"] == "mining"

    def test_search_by_description(self, mock_activities):
        """Should match description."""
        with patch(
            "aria_esi.mcp.sde.tools_activities.load_activities",
            return_value=mock_activities,
        ):
            results = search_activities("datacores")

        assert len(results) == 1
        assert results[0]["activity_id"] == "research_agents"

    def test_search_case_insensitive(self, mock_activities):
        """Search should be case insensitive."""
        with patch(
            "aria_esi.mcp.sde.tools_activities.load_activities",
            return_value=mock_activities,
        ):
            results = search_activities("GAS HUFFING")

        assert len(results) == 1

    def test_search_no_matches(self, mock_activities):
        """Should return empty list when no matches."""
        with patch(
            "aria_esi.mcp.sde.tools_activities.load_activities",
            return_value=mock_activities,
        ):
            results = search_activities("nonexistent_xyz")

        assert results == []

    def test_search_multiple_matches(self, mock_activities):
        """Should return multiple matches."""
        with patch(
            "aria_esi.mcp.sde.tools_activities.load_activities",
            return_value=mock_activities,
        ):
            # "missions" appears in l3_missions description, "security missions"
            results = search_activities("missions")

        assert len(results) >= 1


class TestResolveParameters:
    """Tests for resolve_parameters function."""

    def test_resolve_simple_parameter(self):
        """Should resolve ${param} placeholders."""
        skills = [{"skill": "${field}", "level": 3}]
        params = {"field": "Mechanical Engineering"}

        result = resolve_parameters(skills, params)

        assert len(result) == 1
        assert result[0]["skill"] == "Mechanical Engineering"
        assert result[0]["level"] == 3

    def test_preserve_non_parameterized(self):
        """Should preserve skills without parameters."""
        skills = [{"skill": "Mining", "level": 4}]
        params = {}

        result = resolve_parameters(skills, params)

        assert result[0]["skill"] == "Mining"

    def test_missing_parameter_marked(self):
        """Should mark missing parameters."""
        skills = [{"skill": "${field}", "level": 3}]
        params = {}  # Missing 'field'

        result = resolve_parameters(skills, params)

        assert result[0]["skill"] == "[field - parameter required]"
        assert result[0]["parameter_required"] == "field"

    def test_multiple_skills(self):
        """Should handle multiple skills."""
        skills = [
            {"skill": "Mining", "level": 4},
            {"skill": "${field}", "level": 3},
            {"skill": "Science", "level": 3},
        ]
        params = {"field": "Electronic Engineering"}

        result = resolve_parameters(skills, params)

        assert len(result) == 3
        assert result[0]["skill"] == "Mining"
        assert result[1]["skill"] == "Electronic Engineering"
        assert result[2]["skill"] == "Science"

    def test_preserves_other_fields(self):
        """Should preserve other skill fields like notes."""
        skills = [{"skill": "Mining", "level": 4, "note": "Core skill"}]
        params = {}

        result = resolve_parameters(skills, params)

        assert result[0]["note"] == "Core skill"

    def test_does_not_modify_original(self):
        """Should not modify original skill list."""
        skills = [{"skill": "${field}", "level": 3}]
        params = {"field": "Test"}

        resolve_parameters(skills, params)

        assert skills[0]["skill"] == "${field}"  # Unchanged


# =============================================================================
# Cache Management Tests (Phase 2 Priority 3)
# =============================================================================


class TestResetActivitiesCache:
    """Tests for reset_activities_cache function."""

    def test_reset_clears_global_cache(self, tmp_path):
        """reset_activities_cache should clear the global cache."""
        import aria_esi.mcp.sde.tools_activities as activities_module
        from aria_esi.mcp.sde.tools_activities import (
            load_activities,
            reset_activities_cache,
        )

        # Create a mock YAML file
        yaml_content = """
test_activity:
  display_name: Test
"""
        activities_file = tmp_path / "reference" / "activities" / "skill_plans.yaml"
        activities_file.parent.mkdir(parents=True)
        activities_file.write_text(yaml_content)

        with patch(
            "aria_esi.mcp.sde.tools_activities._get_project_root",
            return_value=tmp_path,
        ):
            # Load to populate cache
            load_activities()
            assert activities_module._activities_cache is not None

            # Reset the cache
            reset_activities_cache()
            assert activities_module._activities_cache is None


class TestCacheStaleness:
    """Tests for cache staleness detection."""

    def test_is_activities_cache_stale_when_none(self):
        """Cache should be stale when None."""
        import aria_esi.mcp.sde.tools_activities as activities_module
        from aria_esi.mcp.sde.tools_activities import _is_activities_cache_stale

        activities_module._activities_cache = None
        assert _is_activities_cache_stale() is True

    def test_is_activities_cache_stale_when_file_missing(self, tmp_path):
        """Cache should be stale when file is missing."""
        import aria_esi.mcp.sde.tools_activities as activities_module
        from aria_esi.mcp.sde.tools_activities import _is_activities_cache_stale

        # Set a dummy cache
        activities_module._activities_cache = ({}, 0)

        with patch(
            "aria_esi.mcp.sde.tools_activities._get_project_root",
            return_value=tmp_path,
        ):
            assert _is_activities_cache_stale() is True

    def test_is_activities_cache_stale_when_file_newer(self, tmp_path):
        """Cache should be stale when file has newer mtime."""
        import time

        import aria_esi.mcp.sde.tools_activities as activities_module
        from aria_esi.mcp.sde.tools_activities import _is_activities_cache_stale

        # Create the file
        activities_file = tmp_path / "reference" / "activities" / "skill_plans.yaml"
        activities_file.parent.mkdir(parents=True)
        activities_file.write_text("test: true")

        # Set cache with old mtime
        activities_module._activities_cache = ({}, time.time() - 100)

        with patch(
            "aria_esi.mcp.sde.tools_activities._get_project_root",
            return_value=tmp_path,
        ):
            assert _is_activities_cache_stale() is True


# =============================================================================
# Activity Skill Plan Impl Tests (Phase 2 Priority 3)
# =============================================================================


@pytest.mark.asyncio
class TestActivitySkillPlanImpl:
    """Tests for _activity_skill_plan_impl function."""

    async def test_exact_match_by_id(self, mock_activities):
        """Should find activity by exact ID match."""
        from aria_esi.mcp.sde.tools_activities import _activity_skill_plan_impl

        with patch(
            "aria_esi.mcp.sde.tools_activities.load_activities",
            return_value=mock_activities,
        ), patch(
            "aria_esi.mcp.sde.tools_activities.calculate_activity_training_time",
            return_value={"skills": [], "total_sp": 0, "total_seconds": 0, "total_formatted": "0s", "warnings": []},
        ):
            result = await _activity_skill_plan_impl("gas_huffing")

        assert result["found"] is True
        assert result["activity_id"] == "gas_huffing"
        assert result["display_name"] == "Gas Huffing"

    async def test_match_with_underscore_to_space(self, mock_activities):
        """Should match activity with underscores replaced by spaces."""
        from aria_esi.mcp.sde.tools_activities import _activity_skill_plan_impl

        with patch(
            "aria_esi.mcp.sde.tools_activities.load_activities",
            return_value=mock_activities,
        ), patch(
            "aria_esi.mcp.sde.tools_activities.calculate_activity_training_time",
            return_value={"skills": [], "total_sp": 0, "total_seconds": 0, "total_formatted": "0s", "warnings": []},
        ):
            result = await _activity_skill_plan_impl("gas huffing")

        assert result["found"] is True
        assert result["activity_id"] == "gas_huffing"

    async def test_fuzzy_match_single_result(self, mock_activities):
        """Should return single fuzzy match directly."""
        from aria_esi.mcp.sde.tools_activities import _activity_skill_plan_impl

        with patch(
            "aria_esi.mcp.sde.tools_activities.load_activities",
            return_value=mock_activities,
        ), patch(
            "aria_esi.mcp.sde.tools_activities.calculate_activity_training_time",
            return_value={"skills": [], "total_sp": 0, "total_seconds": 0, "total_formatted": "0s", "warnings": []},
        ):
            result = await _activity_skill_plan_impl("huff")  # Should match "gas_huffing"

        assert result["found"] is True
        assert result["activity_id"] == "gas_huffing"

    async def test_multiple_matches_returns_suggestions(self):
        """Should return suggestions when multiple activities match."""
        from aria_esi.mcp.sde.tools_activities import _activity_skill_plan_impl

        activities = {
            "mining_barge": {"display_name": "Mining Barge", "category": "mining"},
            "mining_frigate": {"display_name": "Mining Frigate", "category": "mining"},
        }

        with patch(
            "aria_esi.mcp.sde.tools_activities.load_activities",
            return_value=activities,
        ):
            result = await _activity_skill_plan_impl("mining")

        assert result["found"] is False
        assert "Multiple activities" in result["error"]
        assert "suggestions" in result
        assert len(result["suggestions"]) == 2

    async def test_not_found_returns_categories(self, mock_activities):
        """Should return available categories when not found."""
        from aria_esi.mcp.sde.tools_activities import _activity_skill_plan_impl

        with patch(
            "aria_esi.mcp.sde.tools_activities.load_activities",
            return_value=mock_activities,
        ):
            result = await _activity_skill_plan_impl("nonexistent_xyz_123")

        assert result["found"] is False
        assert "not found" in result["error"]
        assert "available_categories" in result
        assert "mining" in result["available_categories"]
        assert "combat" in result["available_categories"]

    async def test_missing_required_parameter(self, mock_activities):
        """Should indicate missing required parameter."""
        from aria_esi.mcp.sde.tools_activities import _activity_skill_plan_impl

        with patch(
            "aria_esi.mcp.sde.tools_activities.load_activities",
            return_value=mock_activities,
        ):
            result = await _activity_skill_plan_impl("research_agents")

        assert result["found"] is True
        assert result["requires_parameters"] is True
        assert len(result["missing_parameters"]) == 1
        assert result["missing_parameters"][0]["name"] == "field"

    async def test_parameter_default_used(self):
        """Should use default parameter value when provided in activity."""
        from aria_esi.mcp.sde.tools_activities import _activity_skill_plan_impl

        activities = {
            "research_with_default": {
                "display_name": "Research With Default",
                "category": "research",
                "parameters": [
                    {
                        "name": "field",
                        "type": "skill",
                        "default": "Mechanical Engineering",
                    }
                ],
                "easy_80": [{"skill": "${field}", "level": 3}],
            },
        }

        with patch(
            "aria_esi.mcp.sde.tools_activities.load_activities",
            return_value=activities,
        ), patch(
            "aria_esi.mcp.sde.tools_activities.calculate_activity_training_time",
            return_value={"skills": [], "total_sp": 0, "total_seconds": 0, "total_formatted": "0s", "warnings": []},
        ):
            result = await _activity_skill_plan_impl("research_with_default")

        assert result["found"] is True
        # Should not require parameters since default is available
        assert "requires_parameters" not in result or result.get("requires_parameters") is False

    async def test_tier_all_returns_all_tiers(self, mock_activities):
        """tier='all' should return all tier data."""
        from aria_esi.mcp.sde.tools_activities import _activity_skill_plan_impl

        with patch(
            "aria_esi.mcp.sde.tools_activities.load_activities",
            return_value=mock_activities,
        ), patch(
            "aria_esi.mcp.sde.tools_activities.calculate_activity_training_time",
            return_value={"skills": [], "total_sp": 0, "total_seconds": 0, "total_formatted": "0s", "warnings": []},
        ):
            result = await _activity_skill_plan_impl("gas_huffing", tier="all")

        assert result["found"] is True
        assert "minimum" in result
        assert "easy_80" in result
        assert "full" in result


# =============================================================================
# Activity List Impl Tests (Phase 2 Priority 3)
# =============================================================================


@pytest.mark.asyncio
class TestActivityListImpl:
    """Tests for _activity_list_impl function."""

    async def test_list_all_activities(self, mock_activities):
        """Should list all activities when no filter."""
        from aria_esi.mcp.sde.tools_activities import _activity_list_impl

        with patch(
            "aria_esi.mcp.sde.tools_activities.load_activities",
            return_value=mock_activities,
        ):
            result = await _activity_list_impl()

        assert result["total"] == 3
        assert len(result["activities"]) == 3
        assert "mining" in result["categories"]
        assert "combat" in result["categories"]
        assert "research" in result["categories"]
        assert result["filter_applied"] is None

    async def test_filter_by_category(self, mock_activities):
        """Should filter activities by category."""
        from aria_esi.mcp.sde.tools_activities import _activity_list_impl

        with patch(
            "aria_esi.mcp.sde.tools_activities.load_activities",
            return_value=mock_activities,
        ):
            result = await _activity_list_impl(category="mining")

        assert result["total"] == 1
        assert result["activities"][0]["activity_id"] == "gas_huffing"
        assert result["filter_applied"] == "mining"

    async def test_has_parameters_flag_correct(self, mock_activities):
        """has_parameters flag should reflect activity configuration."""
        from aria_esi.mcp.sde.tools_activities import _activity_list_impl

        with patch(
            "aria_esi.mcp.sde.tools_activities.load_activities",
            return_value=mock_activities,
        ):
            result = await _activity_list_impl()

        # Find the activities
        gas_huffing = next(a for a in result["activities"] if a["activity_id"] == "gas_huffing")
        research_agents = next(a for a in result["activities"] if a["activity_id"] == "research_agents")

        assert gas_huffing["has_parameters"] is False
        assert research_agents["has_parameters"] is True


# =============================================================================
# Activity Search Impl Tests (Phase 2 Priority 3)
# =============================================================================


@pytest.mark.asyncio
class TestActivitySearchImpl:
    """Tests for _activity_search_impl function."""

    async def test_search_returns_formatted_matches(self, mock_activities):
        """Should return formatted search results."""
        from aria_esi.mcp.sde.tools_activities import _activity_search_impl

        with patch(
            "aria_esi.mcp.sde.tools_activities.load_activities",
            return_value=mock_activities,
        ):
            result = await _activity_search_impl("gas")

        assert result["query"] == "gas"
        assert result["total"] == 1
        assert len(result["matches"]) == 1
        match = result["matches"][0]
        assert match["activity_id"] == "gas_huffing"
        assert match["display_name"] == "Gas Huffing"
        assert match["category"] == "mining"

    async def test_search_no_results(self, mock_activities):
        """Should return empty matches for no results."""
        from aria_esi.mcp.sde.tools_activities import _activity_search_impl

        with patch(
            "aria_esi.mcp.sde.tools_activities.load_activities",
            return_value=mock_activities,
        ):
            result = await _activity_search_impl("xyz_nonexistent")

        assert result["query"] == "xyz_nonexistent"
        assert result["total"] == 0
        assert result["matches"] == []


# =============================================================================
# Activity Compare Tiers Impl Tests (Phase 2 Priority 3)
# =============================================================================


@pytest.mark.asyncio
class TestActivityCompareTiersImpl:
    """Tests for _activity_compare_tiers_impl function."""

    async def test_tier_comparison_structure(self, mock_activities):
        """Should return tier comparison with correct structure."""
        from aria_esi.mcp.sde.tools_activities import _activity_compare_tiers_impl

        with patch(
            "aria_esi.mcp.sde.tools_activities.load_activities",
            return_value=mock_activities,
        ), patch(
            "aria_esi.mcp.sde.tools_activities.calculate_activity_training_time",
            return_value={
                "skills": [],
                "total_sp": 1000,
                "total_seconds": 3600,
                "total_formatted": "1h",
                "warnings": [],
            },
        ):
            result = await _activity_compare_tiers_impl("gas_huffing")

        assert result["activity_id"] == "gas_huffing"
        assert "tiers" in result
        assert "minimum" in result["tiers"]
        assert "easy_80" in result["tiers"]
        assert "full" in result["tiers"]

    async def test_savings_calculation(self, mock_activities):
        """Should calculate savings between tiers."""
        from aria_esi.mcp.sde.tools_activities import _activity_compare_tiers_impl

        # Mock different training times for each tier
        call_count = [0]

        def mock_training_time(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:  # minimum
                return {"skills": [], "total_sp": 1000, "total_seconds": 1800, "total_formatted": "30m", "warnings": []}
            elif call_count[0] == 2:  # easy_80
                return {"skills": [], "total_sp": 3000, "total_seconds": 7200, "total_formatted": "2h", "warnings": []}
            else:  # full
                return {"skills": [], "total_sp": 5000, "total_seconds": 18000, "total_formatted": "5h", "warnings": []}

        with patch(
            "aria_esi.mcp.sde.tools_activities.load_activities",
            return_value=mock_activities,
        ), patch(
            "aria_esi.mcp.sde.tools_activities.calculate_activity_training_time",
            side_effect=mock_training_time,
        ):
            result = await _activity_compare_tiers_impl("gas_huffing")

        # Should have savings calculation
        if "minimum_saves" in result:
            assert result["minimum_saves"]["seconds"] > 0
            assert "percentage" in result["minimum_saves"]

    async def test_not_found_passthrough(self, mock_activities):
        """Should passthrough not-found result from plan impl."""
        from aria_esi.mcp.sde.tools_activities import _activity_compare_tiers_impl

        with patch(
            "aria_esi.mcp.sde.tools_activities.load_activities",
            return_value=mock_activities,
        ):
            result = await _activity_compare_tiers_impl("nonexistent_xyz_123")

        assert result["found"] is False
        assert "error" in result


# =============================================================================
# Calculate Activity Training Time Tests (Phase 2 Priority 3)
# =============================================================================


class TestCalculateActivityTrainingTime:
    """Tests for calculate_activity_training_time function."""

    def test_already_trained_skill_shows_no_training(self):
        """Skills at or above target should show no training needed."""
        from aria_esi.mcp.sde.tools_activities import calculate_activity_training_time

        skills = [{"skill": "Mining", "level": 3}]
        current_skills = {"Mining": 5}  # Already at level 5

        with patch(
            "aria_esi.mcp.market.database.get_market_database"
        ) as mock_db, patch(
            "aria_esi.mcp.sde.queries.get_sde_query_service"
        ):
            # Mock database connection
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = None  # Won't actually be called since skill is trained
            mock_conn.execute.return_value = mock_cursor
            mock_db.return_value._get_connection.return_value = mock_conn

            result = calculate_activity_training_time(skills, current_skills)

        assert len(result["skills"]) == 1
        assert result["skills"][0]["training_needed"] is False
        assert result["skills"][0]["training_formatted"] == "Already trained"

    def test_parameterized_skill_adds_warning(self):
        """Unresolved parameterized skills should add warning."""
        from aria_esi.mcp.sde.tools_activities import calculate_activity_training_time

        skills = [{"skill": "[field - parameter required]", "level": 3, "parameter_required": "field"}]

        with patch(
            "aria_esi.mcp.market.database.get_market_database"
        ) as mock_db, patch(
            "aria_esi.mcp.sde.queries.get_sde_query_service"
        ):
            mock_conn = MagicMock()
            mock_db.return_value._get_connection.return_value = mock_conn

            result = calculate_activity_training_time(skills)

        assert len(result["warnings"]) >= 1
        assert any("field" in w for w in result["warnings"])

    def test_skill_not_found_adds_warning(self):
        """Unknown skills should add warning."""
        from aria_esi.mcp.sde.tools_activities import calculate_activity_training_time

        skills = [{"skill": "Nonexistent Skill XYZ", "level": 3}]

        with patch(
            "aria_esi.mcp.market.database.get_market_database"
        ) as mock_db, patch(
            "aria_esi.mcp.sde.queries.get_sde_query_service"
        ):
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = None  # Skill not found in SDE
            mock_conn.execute.return_value = mock_cursor
            mock_db.return_value._get_connection.return_value = mock_conn

            result = calculate_activity_training_time(skills)

        assert len(result["warnings"]) >= 1
        assert any("Nonexistent Skill XYZ" in w for w in result["warnings"])

    def test_training_time_calculation_accuracy(self):
        """Training time should be calculated correctly."""
        from aria_esi.mcp.sde.tools_activities import calculate_activity_training_time

        skills = [{"skill": "Mining", "level": 3}]

        mock_skill_attrs = MagicMock()
        mock_skill_attrs.rank = 1
        mock_skill_attrs.primary_attribute = "intelligence"
        mock_skill_attrs.secondary_attribute = "memory"

        with patch(
            "aria_esi.mcp.market.database.get_market_database"
        ) as mock_db, patch(
            "aria_esi.mcp.sde.queries.get_sde_query_service"
        ) as mock_query_service:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = (3386,)  # Mining skill ID
            mock_conn.execute.return_value = mock_cursor
            mock_db.return_value._get_connection.return_value = mock_conn

            mock_query_service.return_value.get_skill_attributes.return_value = mock_skill_attrs

            result = calculate_activity_training_time(skills)

        # Should have calculated training time
        assert result["total_seconds"] > 0
        assert result["total_sp"] > 0
        assert len(result["skills"]) == 1
        assert result["skills"][0]["training_needed"] is True

    def test_multiple_skills_sum_correctly(self):
        """Multiple skills should sum training times."""
        from aria_esi.mcp.sde.tools_activities import calculate_activity_training_time

        skills = [
            {"skill": "Mining", "level": 2},
            {"skill": "Astrogeology", "level": 2},
        ]

        mock_skill_attrs = MagicMock()
        mock_skill_attrs.rank = 1
        mock_skill_attrs.primary_attribute = "intelligence"
        mock_skill_attrs.secondary_attribute = "memory"

        with patch(
            "aria_esi.mcp.market.database.get_market_database"
        ) as mock_db, patch(
            "aria_esi.mcp.sde.queries.get_sde_query_service"
        ) as mock_query_service:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            # Return different skill IDs for different skills
            mock_cursor.fetchone.side_effect = [(3386,), (3410,)]
            mock_conn.execute.return_value = mock_cursor
            mock_db.return_value._get_connection.return_value = mock_conn

            mock_query_service.return_value.get_skill_attributes.return_value = mock_skill_attrs

            result = calculate_activity_training_time(skills)

        # Should have two skills with training
        assert len(result["skills"]) == 2
        # Total should be sum of individual times
        individual_totals = sum(
            s.get("training_seconds", 0)
            for s in result["skills"]
            if s.get("training_needed")
        )
        assert result["total_seconds"] == individual_totals
