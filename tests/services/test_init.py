"""
Tests for Services Package Initialization.

Tests lazy import functionality and module exports.
"""

from __future__ import annotations


# =============================================================================
# Module Exports Tests
# =============================================================================


class TestModuleExports:
    """Test __all__ exports are accessible."""

    def test_all_defined(self):
        """__all__ is defined and non-empty."""
        import aria_esi.services as services

        assert hasattr(services, "__all__")
        assert len(services.__all__) > 0

    def test_market_refresh_service_accessible(self):
        """MarketRefreshService can be imported."""
        from aria_esi.services import MarketRefreshService

        assert MarketRefreshService is not None
        assert hasattr(MarketRefreshService, "__name__")

    def test_arbitrage_engine_accessible(self):
        """ArbitrageEngine can be imported."""
        from aria_esi.services import ArbitrageEngine

        assert ArbitrageEngine is not None

    def test_arbitrage_calculator_accessible(self):
        """ArbitrageCalculator can be imported."""
        from aria_esi.services import ArbitrageCalculator

        assert ArbitrageCalculator is not None

    def test_freshness_functions_accessible(self):
        """Freshness utility functions can be imported."""
        from aria_esi.services import (
            get_combined_freshness,
            get_confidence,
            get_effective_volume,
            get_freshness,
            get_scope_freshness,
        )

        assert callable(get_freshness)
        assert callable(get_scope_freshness)
        assert callable(get_confidence)
        assert callable(get_combined_freshness)
        assert callable(get_effective_volume)

    def test_calculate_net_profit_accessible(self):
        """calculate_net_profit can be imported."""
        from aria_esi.services import calculate_net_profit

        assert callable(calculate_net_profit)

    def test_redisq_module_accessible(self):
        """redisq submodule can be imported."""
        from aria_esi.services import redisq

        assert redisq is not None
        # Check it's a module
        import types

        assert isinstance(redisq, types.ModuleType)

    def test_navigation_service_accessible(self):
        """NavigationService can be imported."""
        from aria_esi.services import NavigationService

        assert NavigationService is not None

    def test_navigation_module_accessible(self):
        """navigation submodule can be imported."""
        from aria_esi.services import navigation

        import types

        assert isinstance(navigation, types.ModuleType)

    def test_loop_planning_service_accessible(self):
        """LoopPlanningService can be imported."""
        from aria_esi.services import LoopPlanningService

        assert LoopPlanningService is not None

    def test_loop_planning_module_accessible(self):
        """loop_planning submodule can be imported."""
        from aria_esi.services import loop_planning

        import types

        assert isinstance(loop_planning, types.ModuleType)


# =============================================================================
# Lazy Import Tests
# =============================================================================


class TestLazyImport:
    """Test lazy import functionality."""

    def test_invalid_attribute_raises(self):
        """Accessing invalid attribute raises AttributeError."""
        import aria_esi.services as services
        import pytest

        with pytest.raises(AttributeError) as exc_info:
            _ = services.NonExistentAttribute

        assert "has no attribute" in str(exc_info.value)
        assert "NonExistentAttribute" in str(exc_info.value)

    def test_freshness_functions_resolve_correctly(self):
        """Freshness functions resolve to correct implementations."""
        from aria_esi.services import get_freshness

        # Test that it works
        result = get_freshness(0)  # Very old timestamp
        assert result == "stale"

    def test_lazy_imports_are_cached(self):
        """Multiple imports return same object."""
        from aria_esi.services import ArbitrageEngine
        from aria_esi.services import ArbitrageEngine as AE2

        assert ArbitrageEngine is AE2
