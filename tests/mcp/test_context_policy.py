"""
Tests for MCP context policy limits.
"""

from __future__ import annotations

import pytest

from aria_esi.mcp.context_policy import (
    FITTING,
    GLOBAL,
    MARKET,
    SDE,
    SKILLS,
    UNIVERSE,
    MarketLimits,
    SDELimits,
    SkillsLimits,
    UniverseLimits,
)


class TestUniverseLimits:
    """Tests for UniverseLimits dataclass."""

    def test_frozen_immutability(self):
        """Should not allow modification of frozen dataclass."""
        with pytest.raises(Exception):  # FrozenInstanceError
            UNIVERSE.SEARCH_MAX_LIMIT = 999

    def test_singleton_values(self):
        """Should have expected default values."""
        assert UNIVERSE.SEARCH_MAX_LIMIT == 100
        assert UNIVERSE.SEARCH_MAX_JUMPS == 50
        assert UNIVERSE.BORDERS_MAX_LIMIT == 50
        assert UNIVERSE.BORDERS_MAX_JUMPS == 30
        assert UNIVERSE.NEAREST_MAX_LIMIT == 50
        assert UNIVERSE.NEAREST_MAX_JUMPS == 50
        assert UNIVERSE.WAYPOINTS_MIN_COUNT == 2
        assert UNIVERSE.WAYPOINTS_MAX_COUNT == 50
        assert UNIVERSE.LOOP_MIN_TARGET_JUMPS == 10
        assert UNIVERSE.LOOP_MAX_TARGET_JUMPS == 100

    def test_output_limits(self):
        """Should have output limits for wrap_output."""
        assert UNIVERSE.OUTPUT_MAX_ROUTE == 100
        assert UNIVERSE.OUTPUT_MAX_SYSTEMS == 50
        assert UNIVERSE.OUTPUT_MAX_HOTSPOTS == 50
        assert UNIVERSE.OUTPUT_MAX_CHOKEPOINTS == 50
        assert UNIVERSE.OUTPUT_MAX_FW_SYSTEMS == 50

    def test_route_summarization_constants(self):
        """Should have route summarization thresholds."""
        assert UNIVERSE.ROUTE_SUMMARIZE_THRESHOLD == 20
        assert UNIVERSE.ROUTE_SHOW_HEAD == 5
        assert UNIVERSE.ROUTE_SHOW_TAIL == 5


class TestMarketLimits:
    """Tests for MarketLimits dataclass."""

    def test_frozen_immutability(self):
        """Should not allow modification of frozen dataclass."""
        with pytest.raises(Exception):
            MARKET.ORDERS_MAX_LIMIT = 999

    def test_singleton_values(self):
        """Should have expected default values."""
        assert MARKET.ORDERS_MAX_LIMIT == 50
        assert MARKET.ORDERS_DEFAULT_LIMIT == 10
        assert MARKET.NEARBY_MAX_JUMPS == 50
        assert MARKET.NEARBY_MAX_REGIONS == 10
        assert MARKET.ARBITRAGE_MAX_RESULTS == 50
        assert MARKET.HISTORY_MAX_DAYS == 365

    def test_output_limits(self):
        """Should have output limits for wrap_output."""
        assert MARKET.OUTPUT_MAX_ITEMS == 50
        assert MARKET.OUTPUT_MAX_ORDERS == 20
        assert MARKET.OUTPUT_MAX_HISTORY == 30
        assert MARKET.OUTPUT_MAX_SOURCES == 50
        assert MARKET.OUTPUT_MAX_ARBITRAGE == 20


class TestSDELimits:
    """Tests for SDELimits dataclass."""

    def test_frozen_immutability(self):
        """Should not allow modification of frozen dataclass."""
        with pytest.raises(Exception):
            SDE.SEARCH_MAX_LIMIT = 999

    def test_singleton_values(self):
        """Should have expected default values."""
        assert SDE.SEARCH_MAX_LIMIT == 50
        assert SDE.SEARCH_DEFAULT_LIMIT == 10
        assert SDE.AGENTS_MAX_LIMIT == 100
        assert SDE.AGENTS_DEFAULT_LIMIT == 20
        assert SDE.SKILLS_MAX_TREE_DEPTH == 30

    def test_output_limits(self):
        """Should have output limits for wrap_output."""
        assert SDE.OUTPUT_MAX_SEARCH_ITEMS == 20
        assert SDE.OUTPUT_MAX_AGENTS == 30
        assert SDE.OUTPUT_MAX_SKILL_TREE == 30


class TestSkillsLimits:
    """Tests for SkillsLimits dataclass."""

    def test_frozen_immutability(self):
        """Should not allow modification of frozen dataclass."""
        with pytest.raises(Exception):
            SKILLS.TRAINING_MAX_SKILLS = 999

    def test_singleton_values(self):
        """Should have expected default values."""
        assert SKILLS.TRAINING_MAX_SKILLS == 50
        assert SKILLS.EASY80_MAX_SKILLS == 30
        assert SKILLS.ACTIVITY_MAX_SKILLS == 50

    def test_output_limits(self):
        """Should have output limits for wrap_output."""
        assert SKILLS.OUTPUT_MAX_SKILLS == 30
        assert SKILLS.OUTPUT_MAX_ACTIVITIES == 50


class TestFittingLimits:
    """Tests for FittingLimits dataclass."""

    def test_frozen_immutability(self):
        """Should not allow modification of frozen dataclass."""
        with pytest.raises(Exception):
            FITTING.MAX_EFT_LENGTH = 999

    def test_singleton_values(self):
        """Should have expected default values."""
        assert FITTING.MAX_EFT_LENGTH == 10000
        assert FITTING.MAX_MODULES == 100
        assert FITTING.OUTPUT_MAX_WARNINGS == 10


class TestGlobalLimits:
    """Tests for GlobalLimits dataclass."""

    def test_frozen_immutability(self):
        """Should not allow modification of frozen dataclass."""
        with pytest.raises(Exception):
            GLOBAL.MAX_OUTPUT_SIZE_BYTES = 999

    def test_singleton_values(self):
        """Should have expected default values."""
        assert GLOBAL.MAX_OUTPUT_SIZE_BYTES == 10240  # 10 KB
        assert GLOBAL.MAX_TOTAL_OUTPUT_BYTES == 51200  # 50 KB
        assert GLOBAL.HARD_LIMIT_BYTES == 102400  # 100 KB
        assert GLOBAL.MAX_ERROR_MESSAGE_LENGTH == 500


class TestLimitsConsistency:
    """Cross-check limit consistency."""

    def test_output_limits_within_input_limits(self):
        """Output limits should not exceed input limits."""
        assert UNIVERSE.OUTPUT_MAX_SYSTEMS <= UNIVERSE.SEARCH_MAX_LIMIT
        assert UNIVERSE.OUTPUT_MAX_SYSTEMS <= UNIVERSE.BORDERS_MAX_LIMIT
        assert UNIVERSE.OUTPUT_MAX_SYSTEMS <= UNIVERSE.NEAREST_MAX_LIMIT

        assert MARKET.OUTPUT_MAX_ORDERS <= MARKET.ORDERS_MAX_LIMIT
        assert MARKET.OUTPUT_MAX_ARBITRAGE <= MARKET.ARBITRAGE_MAX_RESULTS

        assert SDE.OUTPUT_MAX_SEARCH_ITEMS <= SDE.SEARCH_MAX_LIMIT
        assert SDE.OUTPUT_MAX_AGENTS <= SDE.AGENTS_MAX_LIMIT

    def test_default_limits_within_max_limits(self):
        """Default limits should not exceed max limits."""
        assert MARKET.ORDERS_DEFAULT_LIMIT <= MARKET.ORDERS_MAX_LIMIT
        assert MARKET.NEARBY_DEFAULT_LIMIT <= MARKET.NEARBY_MAX_LIMIT
        assert MARKET.ARBITRAGE_DEFAULT_RESULTS <= MARKET.ARBITRAGE_MAX_RESULTS
        assert MARKET.HISTORY_DEFAULT_DAYS <= MARKET.HISTORY_MAX_DAYS

        assert SDE.SEARCH_DEFAULT_LIMIT <= SDE.SEARCH_MAX_LIMIT
        assert SDE.AGENTS_DEFAULT_LIMIT <= SDE.AGENTS_MAX_LIMIT

    def test_loop_borders_range_valid(self):
        """Loop borders limits should have valid range."""
        assert UNIVERSE.LOOP_MIN_BORDERS < UNIVERSE.LOOP_MAX_BORDERS
        assert UNIVERSE.LOOP_MAX_BORDERS <= UNIVERSE.LOOP_MAX_BORDERS_CAP

    def test_waypoints_range_valid(self):
        """Waypoints limits should have valid range."""
        assert UNIVERSE.WAYPOINTS_MIN_COUNT < UNIVERSE.WAYPOINTS_MAX_COUNT

    def test_loop_jumps_range_valid(self):
        """Loop jumps limits should have valid range."""
        assert UNIVERSE.LOOP_MIN_TARGET_JUMPS < UNIVERSE.LOOP_MAX_TARGET_JUMPS

    def test_route_summarization_valid(self):
        """Route summarization limits should be valid."""
        # Head + tail should fit within threshold for summarization to make sense
        assert UNIVERSE.ROUTE_SHOW_HEAD + UNIVERSE.ROUTE_SHOW_TAIL < UNIVERSE.ROUTE_SUMMARIZE_THRESHOLD
        # Values should be positive
        assert UNIVERSE.ROUTE_SUMMARIZE_THRESHOLD > 0
        assert UNIVERSE.ROUTE_SHOW_HEAD > 0
        assert UNIVERSE.ROUTE_SHOW_TAIL > 0


class TestNewInstanceEquality:
    """Test that creating new instances gives same values."""

    def test_universe_limits_equality(self):
        """New UniverseLimits should equal singleton."""
        new_limits = UniverseLimits()
        assert new_limits.SEARCH_MAX_LIMIT == UNIVERSE.SEARCH_MAX_LIMIT
        assert new_limits.BORDERS_MAX_JUMPS == UNIVERSE.BORDERS_MAX_JUMPS

    def test_market_limits_equality(self):
        """New MarketLimits should equal singleton."""
        new_limits = MarketLimits()
        assert new_limits.ORDERS_MAX_LIMIT == MARKET.ORDERS_MAX_LIMIT
        assert new_limits.OUTPUT_MAX_ORDERS == MARKET.OUTPUT_MAX_ORDERS

    def test_sde_limits_equality(self):
        """New SDELimits should equal singleton."""
        new_limits = SDELimits()
        assert new_limits.SEARCH_MAX_LIMIT == SDE.SEARCH_MAX_LIMIT
        assert new_limits.OUTPUT_MAX_AGENTS == SDE.OUTPUT_MAX_AGENTS

    def test_skills_limits_equality(self):
        """New SkillsLimits should equal singleton."""
        new_limits = SkillsLimits()
        assert new_limits.TRAINING_MAX_SKILLS == SKILLS.TRAINING_MAX_SKILLS
        assert new_limits.OUTPUT_MAX_SKILLS == SKILLS.OUTPUT_MAX_SKILLS
