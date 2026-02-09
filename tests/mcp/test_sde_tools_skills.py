"""
Tests for SDE skill requirement MCP tools and utility functions.
"""

from __future__ import annotations

from aria_esi.mcp.sde.tools_skills import (
    DEFAULT_ATTRIBUTES,
    SP_PER_LEVEL,
    calculate_sp_for_level,
    calculate_sp_per_minute,
    format_training_time,
)


class TestCalculateSpForLevel:
    """Tests for calculate_sp_for_level function."""

    def test_level_1_rank_1(self):
        """Rank 1 skill at level 1 needs 250 SP."""
        assert calculate_sp_for_level(1, 1) == 250

    def test_level_5_rank_1(self):
        """Rank 1 skill at level 5 needs 256,000 SP."""
        assert calculate_sp_for_level(1, 5) == 256000

    def test_rank_multiplier(self):
        """Higher rank multiplies SP required."""
        # Rank 3 skill at level 4
        expected = SP_PER_LEVEL[4] * 3  # 45255 * 3
        assert calculate_sp_for_level(3, 4) == expected

    def test_level_below_1_returns_zero(self):
        """Level 0 or negative returns 0."""
        assert calculate_sp_for_level(1, 0) == 0
        assert calculate_sp_for_level(1, -1) == 0

    def test_level_above_5_returns_zero(self):
        """Level above 5 returns 0."""
        assert calculate_sp_for_level(1, 6) == 0

    def test_all_levels(self):
        """Test all valid levels for rank 1."""
        expected = {
            1: 250,
            2: 1415,
            3: 8000,
            4: 45255,
            5: 256000,
        }
        for level, sp in expected.items():
            assert calculate_sp_for_level(1, level) == sp


class TestCalculateSpPerMinute:
    """Tests for calculate_sp_per_minute function."""

    def test_default_attributes(self):
        """Default attributes should give reasonable SP/min."""
        # Formula: primary + secondary/2
        # Default: 20 + 20/2 = 30
        sp_per_min = calculate_sp_per_minute("intelligence", "memory")
        assert sp_per_min == 30.0

    def test_with_custom_attributes(self):
        """Custom attributes should affect SP/min."""
        attrs = {"intelligence": 27, "memory": 21}
        # 27 + 21/2 = 37.5
        sp_per_min = calculate_sp_per_minute("intelligence", "memory", attrs)
        assert sp_per_min == 37.5

    def test_perception_willpower(self):
        """Test perception/willpower combination."""
        attrs = {"perception": 24, "willpower": 22}
        # 24 + 22/2 = 35.0
        sp_per_min = calculate_sp_per_minute("perception", "willpower", attrs)
        assert sp_per_min == 35.0

    def test_none_attributes_uses_default(self):
        """None attribute names fall back to intelligence/memory."""
        sp_per_min = calculate_sp_per_minute(None, None)
        # Default: 20 + 20/2 = 30
        assert sp_per_min == 30.0

    def test_missing_attribute_falls_back(self):
        """Missing attribute in dict falls back to 20."""
        attrs = {"intelligence": 25}  # No memory
        # 25 + 20/2 = 35.0
        sp_per_min = calculate_sp_per_minute("intelligence", "memory", attrs)
        assert sp_per_min == 35.0

    def test_charisma_default(self):
        """Charisma defaults to 19 in default attributes."""
        assert DEFAULT_ATTRIBUTES["charisma"] == 19


class TestFormatTrainingTime:
    """Tests for format_training_time function."""

    def test_seconds_only(self):
        """Under 60 seconds shows just seconds."""
        assert format_training_time(30) == "30s"
        assert format_training_time(59) == "59s"

    def test_minutes_only(self):
        """Under 60 minutes shows just minutes."""
        assert format_training_time(60) == "1m"
        assert format_training_time(120) == "2m"
        assert format_training_time(3540) == "59m"  # 59 minutes

    def test_hours_only(self):
        """Full hours without remaining minutes."""
        assert format_training_time(3600) == "1h"
        assert format_training_time(7200) == "2h"

    def test_hours_and_minutes(self):
        """Hours with remaining minutes."""
        assert format_training_time(3660) == "1h 1m"
        assert format_training_time(7380) == "2h 3m"

    def test_days_only(self):
        """Full days without remaining hours."""
        assert format_training_time(86400) == "1d"
        assert format_training_time(172800) == "2d"

    def test_days_and_hours(self):
        """Days with remaining hours."""
        assert format_training_time(90000) == "1d 1h"  # 25 hours
        assert format_training_time(180000) == "2d 2h"  # 50 hours

    def test_zero_seconds(self):
        """Zero seconds shows 0s."""
        assert format_training_time(0) == "0s"

    def test_large_values(self):
        """Large training times (weeks)."""
        week_seconds = 7 * 24 * 60 * 60  # 604800
        result = format_training_time(week_seconds)
        assert result == "7d"

    def test_realistic_values(self):
        """Test realistic skill training times."""
        # Level 5 of a rank 1 skill (about 5.9 days at 30 SP/min)
        # 256000 SP / 30 SP/min = 8533 minutes = 142.2 hours ≈ 5d 22h
        five_days = 5 * 24 * 60 * 60 + 22 * 60 * 60  # 5d 22h in seconds
        result = format_training_time(five_days)
        assert result == "5d 22h"


class TestSpPerLevelConstants:
    """Tests for SP_PER_LEVEL constants."""

    def test_level_progression(self):
        """Each level requires more SP than the previous."""
        levels = sorted(SP_PER_LEVEL.keys())
        for i in range(len(levels) - 1):
            assert SP_PER_LEVEL[levels[i]] < SP_PER_LEVEL[levels[i + 1]]

    def test_level_5_is_highest(self):
        """Level 5 requires the most SP."""
        assert SP_PER_LEVEL[5] == max(SP_PER_LEVEL.values())

    def test_all_levels_present(self):
        """All 5 levels are defined."""
        assert set(SP_PER_LEVEL.keys()) == {1, 2, 3, 4, 5}


class TestDefaultAttributes:
    """Tests for DEFAULT_ATTRIBUTES constant."""

    def test_all_attributes_present(self):
        """All five attributes are defined."""
        expected = {"intelligence", "memory", "perception", "willpower", "charisma"}
        assert set(DEFAULT_ATTRIBUTES.keys()) == expected

    def test_balanced_remap(self):
        """Default is a balanced remap (20/20/20/20/19)."""
        assert DEFAULT_ATTRIBUTES["intelligence"] == 20
        assert DEFAULT_ATTRIBUTES["memory"] == 20
        assert DEFAULT_ATTRIBUTES["perception"] == 20
        assert DEFAULT_ATTRIBUTES["willpower"] == 20
        assert DEFAULT_ATTRIBUTES["charisma"] == 19
