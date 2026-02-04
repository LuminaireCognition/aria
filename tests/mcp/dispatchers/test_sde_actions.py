"""
Tests for SDE Dispatcher Action Implementations.

Tests the parameter validation for SDE dispatcher actions.
Implementation tests are intentionally limited to validation logic
to avoid brittle mocking of internal functions.
"""

from __future__ import annotations

import asyncio

import pytest

from aria_esi.mcp.errors import InvalidParameterError


# =============================================================================
# Item Info Action Tests
# =============================================================================


class TestItemInfoAction:
    """Tests for SDE item_info action."""

    def test_item_info_requires_item(self, sde_dispatcher):
        """Item info action requires item parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(sde_dispatcher(action="item_info"))

        assert "item" in str(exc.value).lower()


# =============================================================================
# Blueprint Info Action Tests
# =============================================================================


class TestBlueprintInfoAction:
    """Tests for SDE blueprint_info action."""

    def test_blueprint_info_requires_item(self, sde_dispatcher):
        """Blueprint info action requires item parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(sde_dispatcher(action="blueprint_info"))

        assert "item" in str(exc.value).lower()


# =============================================================================
# Search Action Tests
# =============================================================================


class TestSearchAction:
    """Tests for SDE search action."""

    def test_search_requires_query(self, sde_dispatcher):
        """Search action requires query parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(sde_dispatcher(action="search"))

        assert "query" in str(exc.value).lower()


# =============================================================================
# Skill Requirements Action Tests
# =============================================================================


class TestSkillRequirementsAction:
    """Tests for SDE skill_requirements action."""

    def test_skill_requirements_requires_item(self, sde_dispatcher):
        """Skill requirements action requires item parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(sde_dispatcher(action="skill_requirements"))

        assert "item" in str(exc.value).lower()


# =============================================================================
# Corporation Info Action Tests
# =============================================================================


class TestCorporationInfoAction:
    """Tests for SDE corporation_info action."""

    def test_corporation_info_requires_id_or_name(self, sde_dispatcher):
        """Corporation info requires either corporation_id or corporation_name."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(sde_dispatcher(action="corporation_info"))

        error_msg = str(exc.value).lower()
        assert "corporation_id" in error_msg or "corporation_name" in error_msg


# =============================================================================
# Meta Variants Action Tests
# =============================================================================


class TestMetaVariantsAction:
    """Tests for SDE meta_variants action."""

    def test_meta_variants_requires_item(self, sde_dispatcher):
        """Meta variants action requires item parameter."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(sde_dispatcher(action="meta_variants"))

        assert "item" in str(exc.value).lower()


# =============================================================================
# Invalid Action Tests
# =============================================================================


class TestSDEInvalidActions:
    """Tests for invalid action handling."""

    def test_invalid_action_raises_error(self, sde_dispatcher):
        """Unknown action raises InvalidParameterError."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(sde_dispatcher(action="nonexistent_action"))

        assert "action" in str(exc.value)
        assert "must be one of" in str(exc.value).lower()

    def test_empty_action_raises_error(self, sde_dispatcher):
        """Empty action raises InvalidParameterError."""
        with pytest.raises(InvalidParameterError) as exc:
            asyncio.run(sde_dispatcher(action=""))

        assert "action" in str(exc.value)
