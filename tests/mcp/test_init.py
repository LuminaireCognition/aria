"""
Tests for MCP Package Initialization.

Tests module exports and accessibility of MCP components.
"""

from __future__ import annotations


# =============================================================================
# Module Exports Tests
# =============================================================================


class TestModuleExports:
    """Test __all__ exports are accessible."""

    def test_all_defined(self):
        """__all__ is defined and non-empty."""
        import aria_esi.mcp as mcp

        assert hasattr(mcp, "__all__")
        assert len(mcp.__all__) > 0

    def test_all_exports_accessible(self):
        """All items in __all__ are importable."""
        import aria_esi.mcp as mcp

        for name in mcp.__all__:
            assert hasattr(mcp, name), f"Missing export: {name}"


# =============================================================================
# Server Exports Tests
# =============================================================================


class TestServerExports:
    """Test server class exports."""

    def test_universe_server_accessible(self):
        """UniverseServer can be imported."""
        from aria_esi.mcp import UniverseServer

        assert UniverseServer is not None

    def test_main_accessible(self):
        """main function can be imported."""
        from aria_esi.mcp import main

        assert callable(main)


# =============================================================================
# Error Exports Tests
# =============================================================================


class TestErrorExports:
    """Test error class exports."""

    def test_universe_error_accessible(self):
        """UniverseError can be imported."""
        from aria_esi.mcp import UniverseError

        assert UniverseError is not None
        assert issubclass(UniverseError, Exception)

    def test_system_not_found_error_accessible(self):
        """SystemNotFoundError can be imported."""
        from aria_esi.mcp import SystemNotFoundError

        assert SystemNotFoundError is not None
        assert issubclass(SystemNotFoundError, Exception)

    def test_route_not_found_error_accessible(self):
        """RouteNotFoundError can be imported."""
        from aria_esi.mcp import RouteNotFoundError

        assert RouteNotFoundError is not None
        assert issubclass(RouteNotFoundError, Exception)

    def test_invalid_parameter_error_accessible(self):
        """InvalidParameterError can be imported."""
        from aria_esi.mcp import InvalidParameterError

        assert InvalidParameterError is not None
        assert issubclass(InvalidParameterError, Exception)

    def test_insufficient_borders_error_accessible(self):
        """InsufficientBordersError can be imported."""
        from aria_esi.mcp import InsufficientBordersError

        assert InsufficientBordersError is not None
        assert issubclass(InsufficientBordersError, Exception)


# =============================================================================
# Model Exports Tests
# =============================================================================


class TestModelExports:
    """Test model class exports."""

    def test_mcp_model_accessible(self):
        """MCPModel can be imported."""
        from aria_esi.mcp import MCPModel

        assert MCPModel is not None

    def test_neighbor_info_accessible(self):
        """NeighborInfo can be imported."""
        from aria_esi.mcp import NeighborInfo

        assert NeighborInfo is not None

    def test_system_info_accessible(self):
        """SystemInfo can be imported."""
        from aria_esi.mcp import SystemInfo

        assert SystemInfo is not None

    def test_security_summary_accessible(self):
        """SecuritySummary can be imported."""
        from aria_esi.mcp import SecuritySummary

        assert SecuritySummary is not None

    def test_route_result_accessible(self):
        """RouteResult can be imported."""
        from aria_esi.mcp import RouteResult

        assert RouteResult is not None

    def test_border_system_accessible(self):
        """BorderSystem can be imported."""
        from aria_esi.mcp import BorderSystem

        assert BorderSystem is not None

    def test_loop_result_accessible(self):
        """LoopResult can be imported."""
        from aria_esi.mcp import LoopResult

        assert LoopResult is not None

    def test_danger_zone_accessible(self):
        """DangerZone can be imported."""
        from aria_esi.mcp import DangerZone

        assert DangerZone is not None

    def test_route_analysis_accessible(self):
        """RouteAnalysis can be imported."""
        from aria_esi.mcp import RouteAnalysis

        assert RouteAnalysis is not None

    def test_system_search_result_accessible(self):
        """SystemSearchResult can be imported."""
        from aria_esi.mcp import SystemSearchResult

        assert SystemSearchResult is not None

    def test_border_search_result_accessible(self):
        """BorderSearchResult can be imported."""
        from aria_esi.mcp import BorderSearchResult

        assert BorderSearchResult is not None
