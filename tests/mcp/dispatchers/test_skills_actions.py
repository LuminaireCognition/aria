"""
Tests for Skills Dispatcher Action Implementations.

Tests the parameter validation for skills dispatcher actions.
Implementation tests are intentionally limited to validation logic
to avoid brittle mocking of internal functions.
"""

from __future__ import annotations

import asyncio

import pytest

from aria_esi.mcp.errors import InvalidParameterError


# =============================================================================
# Training Time Action Tests
# =============================================================================


class TestTrainingTimeAction:
    """Tests for skills training_time action."""

    def test_training_time_requires_skill_list(self, skills_dispatcher):
        """Training time action requires skill_list parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(skills_dispatcher(action="training_time"))

        assert "skill_list" in str(exc.value).lower()

    def test_training_time_empty_list_raises_error(self, skills_dispatcher):
        """Empty skill_list raises error."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(
                skills_dispatcher(action="training_time", skill_list=[])
            )

        assert "skill_list" in str(exc.value).lower()


# =============================================================================
# Easy 80 Plan Action Tests
# =============================================================================


class TestEasy80PlanAction:
    """Tests for skills easy_80_plan action."""

    def test_easy_80_plan_requires_item(self, skills_dispatcher):
        """Easy 80 plan action requires item parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(skills_dispatcher(action="easy_80_plan"))

        assert "item" in str(exc.value).lower()


# =============================================================================
# T2 Requirements Action Tests
# =============================================================================


class TestT2RequirementsAction:
    """Tests for skills t2_requirements action."""

    def test_t2_requirements_requires_item(self, skills_dispatcher):
        """T2 requirements action requires item parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(skills_dispatcher(action="t2_requirements"))

        assert "item" in str(exc.value).lower()


# =============================================================================
# Activity Plan Action Tests
# =============================================================================


class TestActivityPlanAction:
    """Tests for skills activity_plan action."""

    def test_activity_plan_requires_activity(self, skills_dispatcher):
        """Activity plan action requires activity parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(skills_dispatcher(action="activity_plan"))

        assert "activity" in str(exc.value).lower()


# =============================================================================
# Activity Search Action Tests
# =============================================================================


class TestActivitySearchAction:
    """Tests for skills activity_search action."""

    def test_activity_search_requires_query(self, skills_dispatcher):
        """Activity search action requires query parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(skills_dispatcher(action="activity_search"))

        assert "query" in str(exc.value).lower()


# =============================================================================
# Activity Compare Action Tests
# =============================================================================


class TestActivityCompareAction:
    """Tests for skills activity_compare action."""

    def test_activity_compare_requires_activity(self, skills_dispatcher):
        """Activity compare action requires activity parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(skills_dispatcher(action="activity_compare"))

        assert "activity" in str(exc.value).lower()


# =============================================================================
# Invalid Action Tests
# =============================================================================


class TestSkillsInvalidActions:
    """Tests for invalid action handling."""

    def test_invalid_action_raises_error(self, skills_dispatcher):
        """Unknown action raises InvalidParameterError."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(skills_dispatcher(action="nonexistent_action"))

        assert "action" in str(exc.value)
        assert "must be one of" in str(exc.value).lower()

    def test_empty_action_raises_error(self, skills_dispatcher):
        """Empty action raises InvalidParameterError."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(skills_dispatcher(action=""))

        assert "action" in str(exc.value)
