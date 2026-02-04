"""
Tests for services module lazy imports.
"""

from __future__ import annotations

import pytest


class TestServicesLazyImports:
    """Tests for lazy import functionality in services/__init__.py."""

    def test_import_market_refresh_service(self):
        """Should lazily import MarketRefreshService."""
        from aria_esi.services import MarketRefreshService

        assert MarketRefreshService is not None
        assert hasattr(MarketRefreshService, "__init__")

    def test_import_arbitrage_engine(self):
        """Should lazily import ArbitrageEngine."""
        from aria_esi.services import ArbitrageEngine

        assert ArbitrageEngine is not None

    def test_import_arbitrage_calculator(self):
        """Should lazily import ArbitrageCalculator."""
        from aria_esi.services import ArbitrageCalculator

        assert ArbitrageCalculator is not None

    def test_invalid_attribute_raises(self):
        """Should raise AttributeError for unknown attributes."""
        import aria_esi.services as services

        with pytest.raises(AttributeError, match="has no attribute"):
            _ = services.NonexistentClass

    def test_all_exports_defined(self):
        """Should have __all__ with expected exports."""
        import aria_esi.services as services

        assert "MarketRefreshService" in services.__all__
        assert "ArbitrageEngine" in services.__all__
        assert "ArbitrageCalculator" in services.__all__
