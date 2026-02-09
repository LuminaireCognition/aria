"""
Edge Case Tests for MCP Universe Server.

Tests for boundary conditions, empty inputs, and unusual scenarios.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from aria_esi.mcp.errors import (
    InsufficientBordersError,
    RouteNotFoundError,
)
from aria_esi.mcp.tools import register_tools
from aria_esi.mcp.tools_loop import register_loop_tools
from aria_esi.mcp.tools_route import register_route_tools
from aria_esi.mcp.tools_search import register_search_tools
from aria_esi.universe import UniverseGraph

from .conftest import capture_tool_function

# =============================================================================
# InsufficientBordersError Tests
# =============================================================================


class TestInsufficientBordersError:
    """Test InsufficientBordersError exception."""

    def test_error_message(self):
        """Error message includes found and required counts."""
        error = InsufficientBordersError(found=2, required=5, search_radius=10)
        assert "2" in str(error)
        assert "5" in str(error)
        assert "10" in str(error)

    def test_error_data(self):
        """Error data includes all fields."""
        error = InsufficientBordersError(found=2, required=5, search_radius=10)
        data = error._error_data()
        assert data["found"] == 2
        assert data["required"] == 5
        assert data["search_radius"] == 10
        assert "suggestion" in data

    def test_custom_suggestion(self):
        """Custom suggestion can be provided."""
        error = InsufficientBordersError(
            found=1, required=3, search_radius=5, suggestion="Try a different origin"
        )
        assert error.suggestion == "Try a different origin"

    def test_default_suggestion(self):
        """Default suggestion is provided when not specified."""
        error = InsufficientBordersError(found=1, required=3, search_radius=5)
        assert "target_jumps" in error.suggestion
        assert "min_borders" in error.suggestion


# =============================================================================
# Minimal Universe Tests
# =============================================================================


class TestMinimalUniverse:
    """Test behavior with minimal/edge case universe configurations."""

    def test_single_system_route_to_self(self, minimal_universe: UniverseGraph):
        """Route from system to itself works."""
        mock_server = MagicMock()
        register_tools(mock_server, minimal_universe)

        tool = capture_tool_function(minimal_universe, register_route_tools)
        result = asyncio.run(tool(origin="Solo", destination="Solo"))

        assert result["jumps"] == 0
        assert len(result["systems"]) == 1
        assert result["systems"][0]["name"] == "Solo"

    def test_single_system_no_neighbors(self, minimal_universe: UniverseGraph):
        """System with no neighbors has empty neighbor list."""
        mock_server = MagicMock()
        register_tools(mock_server, minimal_universe)

        from aria_esi.mcp.tools_systems import register_systems_tools

        tool = capture_tool_function(minimal_universe, register_systems_tools)
        result = asyncio.run(tool(systems=["Solo"]))

        assert result["found"] == 1
        assert result["systems"][0]["neighbors"] == []


class TestDisconnectedUniverse:
    """Test behavior with disconnected graph components."""

    def test_route_between_disconnected_systems(self, disconnected_universe: UniverseGraph):
        """Route between disconnected systems raises RouteNotFoundError."""
        mock_server = MagicMock()
        register_tools(mock_server, disconnected_universe)

        tool = capture_tool_function(disconnected_universe, register_route_tools)

        with pytest.raises(RouteNotFoundError):
            asyncio.run(tool(origin="Island1", destination="Island3"))

    def test_route_within_connected_component(self, disconnected_universe: UniverseGraph):
        """Route within same component works."""
        mock_server = MagicMock()
        register_tools(mock_server, disconnected_universe)

        tool = capture_tool_function(disconnected_universe, register_route_tools)
        result = asyncio.run(tool(origin="Island1", destination="Island2"))

        assert result["jumps"] == 1


# =============================================================================
# Boundary Condition Tests
# =============================================================================


class TestBoundaryConditions:
    """Test parameter boundary conditions."""

    def test_search_security_min_equals_max(self, standard_universe: UniverseGraph):
        """security_min == security_max returns only exact matches."""
        mock_server = MagicMock()
        register_tools(mock_server, standard_universe)

        tool = capture_tool_function(standard_universe, register_search_tools)
        # Look for systems with exactly 0.95 security
        result = asyncio.run(
            tool(security_min=0.94, security_max=0.96)
        )

        # Should find Jita (0.95)
        assert result["total_found"] >= 1

    def test_search_inverted_security_range(self, standard_universe: UniverseGraph):
        """security_min > security_max returns empty results."""
        mock_server = MagicMock()
        register_tools(mock_server, standard_universe)

        tool = capture_tool_function(standard_universe, register_search_tools)
        result = asyncio.run(
            tool(security_min=0.9, security_max=0.5)
        )

        # No systems can match impossible range
        assert result["total_found"] == 0

    def test_loop_min_equals_max_borders(self, extended_universe: UniverseGraph):
        """min_borders == max_borders constrains to exact count."""
        mock_server = MagicMock()
        register_tools(mock_server, extended_universe)

        tool = capture_tool_function(extended_universe, register_loop_tools)
        result = asyncio.run(
            tool(origin="Jita", target_jumps=20, min_borders=2, max_borders=2)
        )

        # Should have exactly 2 borders
        assert len(result["border_systems_visited"]) == 2


# =============================================================================
# Empty/Null Input Tests
# =============================================================================


class TestEmptyInputs:
    """Test handling of empty or null inputs."""

    def test_empty_avoid_systems(self, standard_universe: UniverseGraph):
        """Empty avoid_systems list is handled correctly."""
        mock_server = MagicMock()
        register_tools(mock_server, standard_universe)

        tool = capture_tool_function(standard_universe, register_route_tools)
        result = asyncio.run(
            tool(origin="Jita", destination="Urlen", avoid_systems=[])
        )

        assert result["jumps"] > 0

    def test_systems_lookup_empty_list(self, standard_universe: UniverseGraph):
        """Empty systems list returns empty results."""
        mock_server = MagicMock()
        register_tools(mock_server, standard_universe)

        from aria_esi.mcp.tools_systems import register_systems_tools

        tool = capture_tool_function(standard_universe, register_systems_tools)
        result = asyncio.run(tool(systems=[]))

        assert result["found"] == 0
        assert result["systems"] == []


# =============================================================================
# Case Sensitivity Tests
# =============================================================================


class TestCaseSensitivity:
    """Test case-insensitive system name handling."""

    def test_route_case_insensitive_origin(self, standard_universe: UniverseGraph):
        """Origin is case-insensitive."""
        mock_server = MagicMock()
        register_tools(mock_server, standard_universe)

        tool = capture_tool_function(standard_universe, register_route_tools)
        result = asyncio.run(tool(origin="jita", destination="Urlen"))

        assert result["systems"][0]["name"] == "Jita"

    def test_route_case_insensitive_destination(self, standard_universe: UniverseGraph):
        """Destination is case-insensitive."""
        mock_server = MagicMock()
        register_tools(mock_server, standard_universe)

        tool = capture_tool_function(standard_universe, register_route_tools)
        result = asyncio.run(tool(origin="Jita", destination="URLEN"))

        assert result["systems"][-1]["name"] == "Urlen"

    def test_route_mixed_case(self, standard_universe: UniverseGraph):
        """Mixed case works."""
        mock_server = MagicMock()
        register_tools(mock_server, standard_universe)

        tool = capture_tool_function(standard_universe, register_route_tools)
        result = asyncio.run(tool(origin="JiTa", destination="uRlEn"))

        assert result["jumps"] > 0
