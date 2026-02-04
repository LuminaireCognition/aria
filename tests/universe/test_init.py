"""
Tests for Universe Package Initialization.

Tests module exports and accessibility of universe components.
"""

from __future__ import annotations


# =============================================================================
# Module Exports Tests
# =============================================================================


class TestModuleExports:
    """Test __all__ exports are accessible."""

    def test_all_defined(self):
        """__all__ is defined and non-empty."""
        import aria_esi.universe as universe

        assert hasattr(universe, "__all__")
        assert len(universe.__all__) > 0

    def test_all_exports_accessible(self):
        """All items in __all__ are importable."""
        import aria_esi.universe as universe

        for name in universe.__all__:
            assert hasattr(universe, name), f"Missing export: {name}"


# =============================================================================
# UniverseGraph Exports Tests
# =============================================================================


class TestUniverseGraphExports:
    """Test UniverseGraph class exports."""

    def test_universe_graph_accessible(self):
        """UniverseGraph can be imported."""
        from aria_esi.universe import UniverseGraph

        assert UniverseGraph is not None

    def test_security_class_accessible(self):
        """SecurityClass type alias can be imported."""
        from aria_esi.universe import SecurityClass

        assert SecurityClass is not None
        # SecurityClass is a Literal type alias, not an enum


# =============================================================================
# Error Exports Tests
# =============================================================================


class TestErrorExports:
    """Test error class exports."""

    def test_universe_build_error_accessible(self):
        """UniverseBuildError can be imported."""
        from aria_esi.universe import UniverseBuildError

        assert UniverseBuildError is not None
        assert issubclass(UniverseBuildError, Exception)

    def test_serialization_error_accessible(self):
        """SerializationError can be imported."""
        from aria_esi.universe import SerializationError

        assert SerializationError is not None
        assert issubclass(SerializationError, Exception)


# =============================================================================
# Function Exports Tests
# =============================================================================


class TestFunctionExports:
    """Test function exports."""

    def test_build_universe_graph_accessible(self):
        """build_universe_graph can be imported."""
        from aria_esi.universe import build_universe_graph

        assert callable(build_universe_graph)

    def test_load_universe_graph_accessible(self):
        """load_universe_graph can be imported."""
        from aria_esi.universe import load_universe_graph

        assert callable(load_universe_graph)


# =============================================================================
# Constants Exports Tests
# =============================================================================


class TestConstantsExports:
    """Test constant exports."""

    def test_default_cache_path_accessible(self):
        """DEFAULT_CACHE_PATH can be imported."""
        from aria_esi.universe import DEFAULT_CACHE_PATH

        assert DEFAULT_CACHE_PATH is not None

    def test_default_graph_path_accessible(self):
        """DEFAULT_GRAPH_PATH can be imported."""
        from aria_esi.universe import DEFAULT_GRAPH_PATH

        assert DEFAULT_GRAPH_PATH is not None

    def test_legacy_graph_path_accessible(self):
        """LEGACY_GRAPH_PATH can be imported."""
        from aria_esi.universe import LEGACY_GRAPH_PATH

        assert LEGACY_GRAPH_PATH is not None
