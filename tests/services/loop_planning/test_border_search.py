"""
Tests for Border System Search.

Tests BFS-based border system discovery for loop planning.
"""

from __future__ import annotations

import pytest

from tests.mcp.conftest import create_mock_universe, STANDARD_SYSTEMS, STANDARD_EDGES


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def standard_universe():
    """Standard 6-system universe for border search tests."""
    return create_mock_universe(STANDARD_SYSTEMS, STANDARD_EDGES)


# =============================================================================
# Security Threshold Tests
# =============================================================================


class TestGetSecurityThreshold:
    """Test get_security_threshold function."""

    def test_highsec_threshold(self):
        """Highsec filter returns 0.45 threshold."""
        from aria_esi.services.loop_planning.border_search import get_security_threshold

        threshold = get_security_threshold("highsec")
        assert threshold == 0.45

    def test_lowsec_threshold(self):
        """Lowsec filter returns 0.0 threshold."""
        from aria_esi.services.loop_planning.border_search import get_security_threshold

        threshold = get_security_threshold("lowsec")
        assert threshold == 0.0

    def test_any_threshold(self):
        """Any filter returns -1.0 threshold (allow all)."""
        from aria_esi.services.loop_planning.border_search import get_security_threshold

        threshold = get_security_threshold("any")
        assert threshold == -1.0


# =============================================================================
# Border Search Tests
# =============================================================================


class TestFindBordersWithDistance:
    """Test find_borders_with_distance function."""

    def test_finds_border_system(self, standard_universe):
        """Finds border systems with correct distances."""
        from aria_esi.services.loop_planning.border_search import find_borders_with_distance

        # Maurasi (2) is a border system, connected to Jita (0)
        borders = find_borders_with_distance(
            universe=standard_universe,
            origin_idx=0,  # Jita
            limit=10,
            max_jumps=5,
            security_filter="highsec",
        )

        # Should find Maurasi
        border_indices = [idx for idx, _ in borders]
        assert 2 in border_indices  # Maurasi

    def test_returns_sorted_by_distance(self, standard_universe):
        """Results are sorted by distance."""
        from aria_esi.services.loop_planning.border_search import find_borders_with_distance

        borders = find_borders_with_distance(
            universe=standard_universe,
            origin_idx=0,
            limit=10,
            max_jumps=10,
            security_filter="highsec",
        )

        # Should be sorted by distance (ascending)
        distances = [dist for _, dist in borders]
        assert distances == sorted(distances)

    def test_respects_limit(self, standard_universe):
        """Respects the limit parameter."""
        from aria_esi.services.loop_planning.border_search import find_borders_with_distance

        borders = find_borders_with_distance(
            universe=standard_universe,
            origin_idx=0,
            limit=1,
            max_jumps=10,
            security_filter="highsec",
        )

        assert len(borders) <= 1

    def test_respects_max_jumps(self, standard_universe):
        """Respects the max_jumps parameter."""
        from aria_esi.services.loop_planning.border_search import find_borders_with_distance

        # With max_jumps=0, should only find border if origin is border
        borders = find_borders_with_distance(
            universe=standard_universe,
            origin_idx=0,  # Jita is not a border
            limit=10,
            max_jumps=0,
            security_filter="highsec",
        )

        # Jita is not a border, so should find nothing at distance 0
        assert len(borders) == 0

    def test_respects_avoid_systems(self, standard_universe):
        """Avoids systems in avoid_systems set."""
        from aria_esi.services.loop_planning.border_search import find_borders_with_distance

        # Avoid Maurasi (2) which is on the path to other border systems
        borders = find_borders_with_distance(
            universe=standard_universe,
            origin_idx=0,
            limit=10,
            max_jumps=10,
            security_filter="highsec",
            avoid_systems={2},  # Block Maurasi
        )

        # Maurasi should not be in results
        border_indices = [idx for idx, _ in borders]
        assert 2 not in border_indices

    def test_highsec_filter_constrains_search(self, standard_universe):
        """Highsec filter limits traversal to high-sec systems."""
        from aria_esi.services.loop_planning.border_search import find_borders_with_distance

        borders = find_borders_with_distance(
            universe=standard_universe,
            origin_idx=0,
            limit=10,
            max_jumps=10,
            security_filter="highsec",
        )

        # With highsec filter, we can only reach through highsec
        # All found borders should be in highsec
        for idx, _ in borders:
            assert standard_universe.security[idx] >= 0.45

    def test_any_filter_allows_all_systems(self, standard_universe):
        """Any filter allows traversal through all security levels."""
        from aria_esi.services.loop_planning.border_search import find_borders_with_distance

        borders = find_borders_with_distance(
            universe=standard_universe,
            origin_idx=0,
            limit=10,
            max_jumps=10,
            security_filter="any",
        )

        # Should be able to find borders (even through lowsec/nullsec)
        assert len(borders) > 0

    def test_empty_result_when_no_borders(self, standard_universe):
        """Returns empty list when no borders found."""
        from aria_esi.services.loop_planning.border_search import find_borders_with_distance

        # Start from Ala (nullsec) with highsec filter - can't reach anything
        borders = find_borders_with_distance(
            universe=standard_universe,
            origin_idx=5,  # Ala (nullsec)
            limit=10,
            max_jumps=10,
            security_filter="highsec",
        )

        assert len(borders) == 0


# =============================================================================
# Constants Tests
# =============================================================================


class TestConstants:
    """Test module constants."""

    def test_highsec_threshold(self):
        """HIGHSEC_THRESHOLD is correctly defined."""
        from aria_esi.services.loop_planning.border_search import HIGHSEC_THRESHOLD

        assert HIGHSEC_THRESHOLD == 0.45

    def test_lowsec_threshold(self):
        """LOWSEC_THRESHOLD is correctly defined."""
        from aria_esi.services.loop_planning.border_search import LOWSEC_THRESHOLD

        assert LOWSEC_THRESHOLD == 0.0
