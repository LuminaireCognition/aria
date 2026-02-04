"""
Tests for Navigation Service Errors.

Tests domain-specific exceptions for route calculation operations.
"""

from __future__ import annotations

import pytest


# =============================================================================
# NavigationError Tests
# =============================================================================


class TestNavigationError:
    """Test NavigationError base exception."""

    def test_can_instantiate(self):
        """Can create NavigationError."""
        from aria_esi.services.navigation.errors import NavigationError

        error = NavigationError("Test error")
        assert str(error) == "Test error"

    def test_is_exception(self):
        """NavigationError is an Exception."""
        from aria_esi.services.navigation.errors import NavigationError

        assert issubclass(NavigationError, Exception)


# =============================================================================
# RouteNotFoundError Tests
# =============================================================================


class TestRouteNotFoundError:
    """Test RouteNotFoundError exception."""

    def test_basic_message(self):
        """Creates error with basic message."""
        from aria_esi.services.navigation.errors import RouteNotFoundError

        error = RouteNotFoundError("Jita", "Amarr")

        assert "Jita" in str(error)
        assert "Amarr" in str(error)
        assert error.origin == "Jita"
        assert error.destination == "Amarr"

    def test_with_reason(self):
        """Creates error with reason."""
        from aria_esi.services.navigation.errors import RouteNotFoundError

        error = RouteNotFoundError("Jita", "Amarr", reason="Systems disconnected")

        assert "Systems disconnected" in str(error)
        assert error.reason == "Systems disconnected"

    def test_is_navigation_error(self):
        """RouteNotFoundError is a NavigationError."""
        from aria_esi.services.navigation.errors import NavigationError, RouteNotFoundError

        assert issubclass(RouteNotFoundError, NavigationError)


# =============================================================================
# SystemNotFoundError Tests
# =============================================================================


class TestSystemNotFoundError:
    """Test SystemNotFoundError exception."""

    def test_basic_message(self):
        """Creates error with system name."""
        from aria_esi.services.navigation.errors import SystemNotFoundError

        error = SystemNotFoundError("NotARealSystem")

        assert "NotARealSystem" in str(error)
        assert error.name == "NotARealSystem"

    def test_is_navigation_error(self):
        """SystemNotFoundError is a NavigationError."""
        from aria_esi.services.navigation.errors import NavigationError, SystemNotFoundError

        assert issubclass(SystemNotFoundError, NavigationError)
