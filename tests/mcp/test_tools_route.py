"""
Tests for Route Tool Implementation.

STP-005: Route Tool (universe_route) Tests
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import igraph as ig
import numpy as np
import pytest

from aria_esi.mcp.errors import InvalidParameterError, SystemNotFoundError
from aria_esi.mcp.tools import register_tools
from aria_esi.mcp.tools_route import (
    _build_route_result,
    _calculate_route,
    _compute_safe_weights,
    _compute_security_summary,
    _compute_unsafe_weights,
    _generate_warnings,
    register_route_tools,
)
from aria_esi.mcp.utils import build_system_info
from aria_esi.universe import UniverseGraph

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_universe() -> UniverseGraph:
    """
    Create a mock universe for testing routes.

    Graph structure:
        Jita (high-sec 0.95) -- Perimeter (high-sec 0.90)
             |                        |
        Maurasi (high-sec 0.65) -- Urlen (high-sec 0.85)
             |
        Sivala (low-sec 0.35)
             |
        Ala (null-sec -0.2)
    """
    g = ig.Graph(
        n=6,
        edges=[
            (0, 1),  # Jita -- Perimeter
            (0, 2),  # Jita -- Maurasi
            (1, 3),  # Perimeter -- Urlen
            (2, 3),  # Maurasi -- Urlen
            (2, 4),  # Maurasi -- Sivala
            (4, 5),  # Sivala -- Ala
        ],
        directed=False,
    )

    systems = [
        {"name": "Jita", "id": 30000142, "sec": 0.95, "const": 20000020, "region": 10000002},
        {"name": "Perimeter", "id": 30000144, "sec": 0.90, "const": 20000020, "region": 10000002},
        {"name": "Maurasi", "id": 30000140, "sec": 0.65, "const": 20000020, "region": 10000002},
        {"name": "Urlen", "id": 30000138, "sec": 0.85, "const": 20000020, "region": 10000002},
        {"name": "Sivala", "id": 30000160, "sec": 0.35, "const": 20000021, "region": 10000002},
        {"name": "Ala", "id": 30000161, "sec": -0.2, "const": 20000022, "region": 10000003},
    ]

    name_to_idx = {s["name"]: i for i, s in enumerate(systems)}
    idx_to_name = {i: s["name"] for i, s in enumerate(systems)}
    name_to_id = {s["name"]: s["id"] for s in systems}
    id_to_idx = {s["id"]: i for i, s in enumerate(systems)}
    name_lookup = {s["name"].lower(): s["name"] for s in systems}

    security = np.array([s["sec"] for s in systems], dtype=np.float32)
    system_ids = np.array([s["id"] for s in systems], dtype=np.int32)
    constellation_ids = np.array([s["const"] for s in systems], dtype=np.int32)
    region_ids = np.array([s["region"] for s in systems], dtype=np.int32)

    highsec = frozenset(i for i in range(6) if security[i] >= 0.45)
    lowsec = frozenset(i for i in range(6) if 0.0 < security[i] < 0.45)
    nullsec = frozenset(i for i in range(6) if security[i] <= 0.0)
    border = frozenset([2])  # Maurasi borders Sivala (low-sec)

    region_systems = {
        10000002: [0, 1, 2, 3, 4],
        10000003: [5],
    }
    constellation_names = {
        20000020: "Kimotoro",
        20000021: "Otanuomi",
        20000022: "Somewhere",
    }
    region_names = {
        10000002: "The Forge",
        10000003: "Outer Region",
    }
    region_name_lookup = {name.lower(): rid for rid, name in region_names.items()}

    return UniverseGraph(
        graph=g,
        name_to_idx=name_to_idx,
        idx_to_name=idx_to_name,
        name_to_id=name_to_id,
        id_to_idx=id_to_idx,
        security=security,
        system_ids=system_ids,
        constellation_ids=constellation_ids,
        region_ids=region_ids,
        name_lookup=name_lookup,
        constellation_names=constellation_names,
        region_names=region_names,
        region_name_lookup=region_name_lookup,
        border_systems=border,
        region_systems=region_systems,
        highsec_systems=highsec,
        lowsec_systems=lowsec,
        nullsec_systems=nullsec,
        version="test-1.0",
        system_count=6,
        stargate_count=6,
    )


@pytest.fixture
def registered_universe(mock_universe: UniverseGraph) -> UniverseGraph:
    """Register tools with the mock universe."""
    mock_server = MagicMock()
    register_tools(mock_server, mock_universe)
    return mock_universe


# =============================================================================
# Route Calculation Tests
# =============================================================================


class TestCalculateRoute:
    """Test _calculate_route function."""

    def test_shortest_path_direct(self, mock_universe: UniverseGraph):
        """Direct path is found in shortest mode."""
        # Jita to Perimeter is direct
        path = _calculate_route(mock_universe, 0, 1, "shortest")
        assert path == [0, 1]

    def test_shortest_path_multi_hop(self, mock_universe: UniverseGraph):
        """Multi-hop path is found in shortest mode."""
        # Jita to Ala: Jita -> Maurasi -> Sivala -> Ala
        path = _calculate_route(mock_universe, 0, 5, "shortest")
        assert path == [0, 2, 4, 5]
        assert len(path) == 4

    def test_shortest_path_same_system(self, mock_universe: UniverseGraph):
        """Same origin and destination returns single-element path."""
        path = _calculate_route(mock_universe, 0, 0, "shortest")
        assert path == [0]

    def test_safe_path_avoids_lowsec(self, mock_universe: UniverseGraph):
        """Safe mode avoids low-sec when possible."""
        # From Jita to Urlen, there are two paths:
        # - Jita -> Perimeter -> Urlen (all high-sec)
        # - Jita -> Maurasi -> Urlen (all high-sec but goes through border)
        # Safe mode should prefer the first as Maurasi borders low-sec
        path = _calculate_route(mock_universe, 0, 3, "safe")
        # Both paths are valid as both are high-sec
        assert 0 in path
        assert 3 in path
        assert len(path) in [3, 3]  # Either path is 2 jumps

    def test_unsafe_path_prefers_lowsec(self, mock_universe: UniverseGraph):
        """Unsafe mode prefers low/null-sec when available."""
        # This is harder to test with our small graph, but we can verify
        # the route to Ala uses the low-sec path
        path = _calculate_route(mock_universe, 0, 5, "unsafe")
        # Must go through Sivala (low-sec) to reach Ala
        assert 4 in path  # Sivala
        assert 5 in path  # Ala


class TestComputeSafeWeights:
    """Test _compute_safe_weights function."""

    def test_highsec_low_weight(self, mock_universe: UniverseGraph):
        """High-sec destinations have weight 1."""
        weights = _compute_safe_weights(mock_universe)
        # Edge 0-1 is Jita-Perimeter (both high-sec)
        assert weights[0] == 1.0

    def test_lowsec_entry_high_weight(self, mock_universe: UniverseGraph):
        """Entering low-sec has high weight."""
        weights = _compute_safe_weights(mock_universe)
        # Edge 2-4 is Maurasi-Sivala (high to low)
        # Find the edge index
        g = mock_universe.graph
        edge_idx = g.get_eid(2, 4)
        assert weights[edge_idx] == 50.0

    def test_nullsec_highest_weight(self, mock_universe: UniverseGraph):
        """Null-sec has highest weight."""
        weights = _compute_safe_weights(mock_universe)
        # Edge 4-5 is Sivala-Ala (low to null)
        g = mock_universe.graph
        edge_idx = g.get_eid(4, 5)
        assert weights[edge_idx] == 100.0


class TestComputeUnsafeWeights:
    """Test _compute_unsafe_weights function."""

    def test_nullsec_low_weight(self, mock_universe: UniverseGraph):
        """Null-sec destinations have weight 1."""
        weights = _compute_unsafe_weights(mock_universe)
        g = mock_universe.graph
        edge_idx = g.get_eid(4, 5)
        assert weights[edge_idx] == 1.0

    def test_lowsec_medium_weight(self, mock_universe: UniverseGraph):
        """Low-sec destinations have weight 2."""
        weights = _compute_unsafe_weights(mock_universe)
        g = mock_universe.graph
        edge_idx = g.get_eid(2, 4)
        assert weights[edge_idx] == 2.0

    def test_highsec_high_weight(self, mock_universe: UniverseGraph):
        """High-sec destinations have weight 10."""
        weights = _compute_unsafe_weights(mock_universe)
        # Edge 0-1 is Jita-Perimeter (both high-sec)
        assert weights[0] == 10.0


# =============================================================================
# Result Construction Tests
# =============================================================================


class TestBuildSystemInfo:
    """Test build_system_info function."""

    def test_system_info_fields(self, mock_universe: UniverseGraph):
        """SystemInfo has all required fields."""
        info = build_system_info(mock_universe, 0)  # Jita

        assert info.name == "Jita"
        assert info.system_id == 30000142
        assert info.security == pytest.approx(0.95, rel=0.01)
        assert info.security_class == "HIGH"
        assert info.constellation == "Kimotoro"
        assert info.region == "The Forge"

    def test_neighbors_included(self, mock_universe: UniverseGraph):
        """SystemInfo includes neighbor information."""
        info = build_system_info(mock_universe, 0)  # Jita

        # Jita has 2 neighbors: Perimeter and Maurasi
        assert len(info.neighbors) == 2
        neighbor_names = [n.name for n in info.neighbors]
        assert "Perimeter" in neighbor_names
        assert "Maurasi" in neighbor_names

    def test_border_system_flag(self, mock_universe: UniverseGraph):
        """Border systems are correctly flagged."""
        # Maurasi (idx 2) is a border system
        maurasi = build_system_info(mock_universe, 2)
        assert maurasi.is_border is True

        # Jita (idx 0) is not a border system
        jita = build_system_info(mock_universe, 0)
        assert jita.is_border is False

    def test_adjacent_lowsec(self, mock_universe: UniverseGraph):
        """Border systems list adjacent low-sec systems."""
        maurasi = build_system_info(mock_universe, 2)
        assert "Sivala" in maurasi.adjacent_lowsec


class TestComputeSecuritySummary:
    """Test _compute_security_summary function."""

    def test_highsec_only_route(self, mock_universe: UniverseGraph):
        """Route through high-sec only."""
        path = [0, 1, 3]  # Jita -> Perimeter -> Urlen
        summary = _compute_security_summary(mock_universe, path)

        assert summary.total_jumps == 2
        assert summary.highsec_jumps == 3  # Systems, not jumps
        assert summary.lowsec_jumps == 0
        assert summary.nullsec_jumps == 0
        assert summary.lowest_security >= 0.45

    def test_mixed_security_route(self, mock_universe: UniverseGraph):
        """Route through mixed security space."""
        path = [0, 2, 4, 5]  # Jita -> Maurasi -> Sivala -> Ala
        summary = _compute_security_summary(mock_universe, path)

        assert summary.total_jumps == 3
        assert summary.highsec_jumps == 2  # Jita, Maurasi
        assert summary.lowsec_jumps == 1  # Sivala
        assert summary.nullsec_jumps == 1  # Ala
        assert summary.lowest_security == pytest.approx(-0.2, rel=0.01)
        assert summary.lowest_security_system == "Ala"


class TestGenerateWarnings:
    """Test _generate_warnings function."""

    def test_no_warnings_highsec_route(self, mock_universe: UniverseGraph):
        """High-sec only route has no warnings."""
        path = [0, 1, 3]  # Jita -> Perimeter -> Urlen
        warnings = _generate_warnings(mock_universe, path, "shortest")
        assert len(warnings) == 0

    def test_lowsec_entry_warning(self, mock_universe: UniverseGraph):
        """Warning when entering low/null-sec."""
        path = [0, 2, 4, 5]  # Jita -> Maurasi -> Sivala -> Ala
        warnings = _generate_warnings(mock_universe, path, "shortest")

        assert any("low/null-sec" in w for w in warnings)

    def test_pipe_system_warning(self, mock_universe: UniverseGraph):
        """Warning for pipe systems in low-sec."""
        # Sivala has only 2 neighbors and is low-sec
        path = [0, 2, 4, 5]  # Goes through Sivala
        warnings = _generate_warnings(mock_universe, path, "shortest")

        pipe_warnings = [w for w in warnings if "Pipe system" in w]
        assert len(pipe_warnings) == 1
        assert "Sivala" in pipe_warnings[0]

    def test_safe_mode_lowsec_warning(self, mock_universe: UniverseGraph):
        """Safe mode warns if route still goes through low-sec."""
        path = [0, 2, 4, 5]
        warnings = _generate_warnings(mock_universe, path, "safe")

        assert any("No fully high-sec route" in w for w in warnings)


class TestBuildRouteResult:
    """Test _build_route_result function."""

    def test_route_result_structure(self, mock_universe: UniverseGraph):
        """RouteResult has all required fields."""
        path = [0, 1, 3]  # Jita -> Perimeter -> Urlen
        result = _build_route_result(mock_universe, path, "Jita", "Urlen", "shortest")

        assert result.origin == "Jita"
        assert result.destination == "Urlen"
        assert result.mode == "shortest"
        assert result.jumps == 2
        assert len(result.systems) == 3
        assert result.security_summary is not None

    def test_systems_order(self, mock_universe: UniverseGraph):
        """Systems are in correct order."""
        path = [0, 2, 4, 5]
        result = _build_route_result(mock_universe, path, "Jita", "Ala", "shortest")

        system_names = [s.name for s in result.systems]
        assert system_names == ["Jita", "Maurasi", "Sivala", "Ala"]


# =============================================================================
# Tool Registration Tests
# =============================================================================


class TestRouteToolRegistration:
    """Test route tool registration."""

    def test_tool_registered(self, mock_universe: UniverseGraph):
        """universe_route tool is registered."""
        mock_server = MagicMock()
        register_route_tools(mock_server, mock_universe)

        # Verify server.tool() decorator was called
        mock_server.tool.assert_called()


# =============================================================================
# Integration Tests
# =============================================================================


class TestUniverseRouteIntegration:
    """Integration tests for the universe_route tool."""

    def _capture_tool(self, registered_universe: UniverseGraph):
        """Helper to capture the registered tool function."""
        from aria_esi.mcp.tools_route import register_route_tools

        captured_tool = None

        def mock_tool():
            def decorator(func):
                nonlocal captured_tool
                captured_tool = func
                return func

            return decorator

        mock_server = MagicMock()
        mock_server.tool = mock_tool
        register_route_tools(mock_server, registered_universe)
        return captured_tool

    def test_universe_route_basic(self, registered_universe: UniverseGraph):
        """Basic route calculation works end-to-end."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(captured_tool("Jita", "Urlen", "shortest"))

        assert result["origin"] == "Jita"
        assert result["destination"] == "Urlen"
        assert result["jumps"] == 2
        assert result["systems"][0]["name"] == "Jita"
        assert result["systems"][-1]["name"] == "Urlen"

    def test_universe_route_invalid_mode(self, registered_universe: UniverseGraph):
        """Invalid mode raises error."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)

        with pytest.raises(InvalidParameterError):
            asyncio.run(captured_tool("Jita", "Urlen", "invalid"))

    def test_universe_route_unknown_system(self, registered_universe: UniverseGraph):
        """Unknown system with multiple suggestions raises error."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)

        # "a" matches multiple systems, so no auto-correction, raises error
        # Note: Single-suggestion typos like "Jit" -> "Jita" are auto-corrected
        with pytest.raises(SystemNotFoundError) as exc:
            asyncio.run(captured_tool("a", "Urlen", "shortest"))

        assert len(exc.value.suggestions) > 0

    def test_universe_route_case_insensitive(self, registered_universe: UniverseGraph):
        """System names are case-insensitive."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(captured_tool("jita", "URLEN", "shortest"))

        assert result["jumps"] == 2

    def test_universe_route_safe_mode(self, registered_universe: UniverseGraph):
        """Safe mode works correctly."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(captured_tool("Jita", "Urlen", "safe"))

        assert result["mode"] == "safe"
        assert result["jumps"] >= 2

    def test_universe_route_unsafe_mode(self, registered_universe: UniverseGraph):
        """Unsafe mode works correctly."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(captured_tool("Jita", "Ala", "unsafe"))

        assert result["mode"] == "unsafe"
        # Route must go through low/null-sec to reach Ala
        assert any(s["security_class"] != "HIGH" for s in result["systems"])


# =============================================================================
# Performance Tests
# =============================================================================


class TestRoutePerformance:
    """Test route calculation performance."""

    def test_route_calculation_fast(self, mock_universe: UniverseGraph):
        """Route calculation is fast (< 2ms for simple routes)."""
        start = time.perf_counter()
        for _ in range(100):
            _calculate_route(mock_universe, 0, 5, "shortest")
        elapsed = time.perf_counter() - start

        avg_time = elapsed / 100
        # Should be well under 2ms even on slow systems
        assert avg_time < 0.002

    def test_weight_computation_fast(self, mock_universe: UniverseGraph):
        """Weight computation is fast."""
        start = time.perf_counter()
        for _ in range(100):
            _compute_safe_weights(mock_universe)
            _compute_unsafe_weights(mock_universe)
        elapsed = time.perf_counter() - start

        avg_time = elapsed / 100
        assert avg_time < 0.001


# =============================================================================
# Avoid Systems Tests
# =============================================================================


class TestAvoidSystems:
    """Test avoid_systems parameter functionality."""

    def test_route_avoids_single_system(self, mock_universe: UniverseGraph):
        """Route calculation avoids a single specified system when alternate exists."""
        # Normal route from Jita to Urlen can go via Maurasi or Perimeter
        # If we avoid Perimeter (target of edge 0-1), it should prefer Maurasi
        path_with_avoid = _calculate_route(
            mock_universe, 0, 3, "shortest", avoid_systems={1}  # Avoid Perimeter (idx 1)
        )

        # Path should not contain Perimeter (idx 1)
        assert 1 not in path_with_avoid
        # Path should go Jita -> Maurasi -> Urlen
        assert path_with_avoid == [0, 2, 3]

    def test_route_with_empty_avoid_set(self, mock_universe: UniverseGraph):
        """Empty avoid set behaves like no avoidance."""
        path_no_avoid = _calculate_route(mock_universe, 0, 3, "shortest")
        path_empty_avoid = _calculate_route(mock_universe, 0, 3, "shortest", avoid_systems=set())

        assert path_no_avoid == path_empty_avoid

    def test_safe_mode_with_avoid_systems(self, mock_universe: UniverseGraph):
        """Safe mode combined with avoid_systems works correctly."""
        # Avoid Perimeter, so must go through Maurasi
        path = _calculate_route(
            mock_universe, 0, 3, "safe", avoid_systems={1}  # Avoid Perimeter
        )

        assert 1 not in path
        assert 2 in path  # Must go through Maurasi

    def test_avoid_prefers_alternate_route(self, mock_universe: UniverseGraph):
        """When avoiding a system, prefer alternate routes if available."""
        # From Jita to Urlen, avoid Maurasi - should prefer Perimeter path
        path = _calculate_route(
            mock_universe, 0, 3, "shortest", avoid_systems={2}  # Avoid Maurasi
        )

        # Should take Jita -> Perimeter -> Urlen
        assert path == [0, 1, 3]
        assert 2 not in path  # Maurasi avoided


class TestAvoidSystemsIntegration:
    """Integration tests for avoid_systems via the full tool interface."""

    def _capture_tool(self, registered_universe: UniverseGraph):
        """Helper to capture the registered tool function."""
        from aria_esi.mcp.tools_route import register_route_tools

        captured_tool = None

        def mock_tool():
            def decorator(func):
                nonlocal captured_tool
                captured_tool = func
                return func

            return decorator

        mock_server = MagicMock()
        mock_server.tool = mock_tool
        register_route_tools(mock_server, registered_universe)
        return captured_tool

    def test_avoid_systems_via_tool(self, registered_universe: UniverseGraph):
        """avoid_systems parameter works through full tool interface."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(
            captured_tool("Jita", "Urlen", "shortest", avoid_systems=["Perimeter"])
        )

        # Route should not contain Perimeter
        system_names = [s["name"] for s in result["systems"]]
        assert "Perimeter" not in system_names
        assert "Maurasi" in system_names

    def test_unknown_avoid_system_warning(self, registered_universe: UniverseGraph):
        """Unknown systems in avoid_systems generate warnings."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(
            captured_tool("Jita", "Urlen", "shortest", avoid_systems=["NonexistentSystem"])
        )

        # Should still calculate route but include warning
        assert result["jumps"] >= 1
        assert any("Unknown systems" in w for w in result["warnings"])
        assert "NonexistentSystem" in str(result["warnings"])

    def test_mixed_valid_invalid_avoid_systems(self, registered_universe: UniverseGraph):
        """Mix of valid and invalid avoid_systems works correctly."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(
            captured_tool(
                "Jita", "Urlen", "shortest", avoid_systems=["Perimeter", "InvalidSystem"]
            )
        )

        # Should avoid Perimeter (valid) and warn about InvalidSystem
        system_names = [s["name"] for s in result["systems"]]
        assert "Perimeter" not in system_names
        assert any("InvalidSystem" in w for w in result["warnings"])
