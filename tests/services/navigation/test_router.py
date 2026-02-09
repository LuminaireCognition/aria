"""
Tests for Navigation Service Router.

Tests the NavigationService class that provides unified routing algorithms.
"""

from __future__ import annotations

import pytest

from tests.mcp.conftest import create_mock_universe, STANDARD_SYSTEMS, STANDARD_EDGES


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def standard_universe():
    """
    Standard 6-system universe for routing tests.

    Graph structure:
        Jita (0.95) -- Perimeter (0.90)
             |                |
        *Maurasi (0.65) -- Urlen (0.85)
             |
        Sivala (0.35)
             |
        Ala (-0.2)

    Border systems: Maurasi (adjacent to Sivala)
    """
    return create_mock_universe(STANDARD_SYSTEMS, STANDARD_EDGES)


# =============================================================================
# NavigationService Tests
# =============================================================================


class TestNavigationService:
    """Test NavigationService class."""

    def test_calculate_route_shortest(self, standard_universe):
        """Shortest route uses minimum jumps."""
        from aria_esi.services.navigation.router import NavigationService

        service = NavigationService(standard_universe)

        # Jita (0) to Urlen (3): Jita -> Perimeter -> Urlen (2 jumps) or Jita -> Maurasi -> Urlen (2 jumps)
        path = service.calculate_route(0, 3, mode="shortest")

        assert len(path) == 3  # Origin + 2 jumps = 3 systems
        assert path[0] == 0  # Starts at Jita
        assert path[-1] == 3  # Ends at Urlen

    def test_calculate_route_shortest_same_system(self, standard_universe):
        """Route to same system returns single-element path."""
        from aria_esi.services.navigation.router import NavigationService

        service = NavigationService(standard_universe)
        path = service.calculate_route(0, 0, mode="shortest")

        assert path == [0]

    def test_calculate_route_safe_avoids_lowsec(self, standard_universe):
        """Safe mode prefers high-sec over low-sec."""
        from aria_esi.services.navigation.router import NavigationService

        service = NavigationService(standard_universe)

        # Jita to Ala: must go through Sivala (low-sec), but safe mode penalizes it
        path = service.calculate_route(0, 5, mode="safe")

        assert len(path) > 0
        assert path[0] == 0  # Starts at Jita
        assert path[-1] == 5  # Ends at Ala

    def test_calculate_route_unsafe_prefers_dangerous(self, standard_universe):
        """Unsafe mode prefers dangerous space."""
        from aria_esi.services.navigation.router import NavigationService

        service = NavigationService(standard_universe)

        path = service.calculate_route(0, 5, mode="unsafe")

        assert len(path) > 0
        assert path[0] == 0
        assert path[-1] == 5

    def test_calculate_route_with_avoidance(self, standard_universe):
        """Avoidance blocks specified systems."""
        from aria_esi.services.navigation.router import NavigationService

        service = NavigationService(standard_universe)

        # Block Maurasi (2) - must use Perimeter route
        avoid = {2}
        path = service.calculate_route(0, 3, mode="shortest", avoid_systems=avoid)

        assert len(path) > 0
        assert 2 not in path  # Maurasi not in path

    def test_calculate_route_avoidance_still_finds_path(self, standard_universe):
        """Avoidance with infinite weights still finds path if it's the only option."""
        from aria_esi.services.navigation.router import NavigationService

        service = NavigationService(standard_universe)

        # Blocking Sivala (4) doesn't prevent routing to Ala (5) since
        # infinite weight is still finite for pathfinding purposes when
        # it's the only option. This tests that the algorithm completes.
        avoid = {4}  # Block Sivala
        path = service.calculate_route(0, 5, mode="shortest", avoid_systems=avoid)

        # Path still exists because Sivala is the only route and
        # infinite weight paths are returned when no other option exists
        assert len(path) > 0
        assert path[0] == 0
        assert path[-1] == 5


class TestResolveAvoidSystems:
    """Test resolve_avoid_systems method."""

    def test_resolve_valid_names(self, standard_universe):
        """Resolves valid system names to indices."""
        from aria_esi.services.navigation.router import NavigationService

        service = NavigationService(standard_universe)

        indices, unresolved = service.resolve_avoid_systems(["Jita", "Perimeter"])

        assert 0 in indices  # Jita
        assert 1 in indices  # Perimeter
        assert len(unresolved) == 0

    def test_resolve_invalid_names(self, standard_universe):
        """Reports unresolved names."""
        from aria_esi.services.navigation.router import NavigationService

        service = NavigationService(standard_universe)

        indices, unresolved = service.resolve_avoid_systems(["Jita", "NotARealSystem"])

        assert 0 in indices  # Jita resolved
        assert "NotARealSystem" in unresolved

    def test_resolve_empty_list(self, standard_universe):
        """Empty input returns empty results."""
        from aria_esi.services.navigation.router import NavigationService

        service = NavigationService(standard_universe)

        indices, unresolved = service.resolve_avoid_systems([])

        assert len(indices) == 0
        assert len(unresolved) == 0

    def test_resolve_all_invalid(self, standard_universe):
        """All invalid names returns empty indices."""
        from aria_esi.services.navigation.router import NavigationService

        service = NavigationService(standard_universe)

        indices, unresolved = service.resolve_avoid_systems(["Fake1", "Fake2"])

        assert len(indices) == 0
        assert "Fake1" in unresolved
        assert "Fake2" in unresolved


class TestRouteMode:
    """Test route mode constants and validation."""

    def test_valid_modes(self):
        """Valid modes are defined."""
        from aria_esi.services.navigation.router import VALID_MODES

        assert "shortest" in VALID_MODES
        assert "safe" in VALID_MODES
        assert "unsafe" in VALID_MODES

    def test_invalid_mode_returns_empty(self, standard_universe):
        """Invalid mode returns empty path."""
        from aria_esi.services.navigation.router import NavigationService

        service = NavigationService(standard_universe)

        # Invalid mode should return empty
        path = service.calculate_route(0, 3, mode="invalid_mode")  # type: ignore

        assert path == []
