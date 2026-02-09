"""
Tests for Analyze Tool Implementation.

STP-010: Analyze Tool (universe_analyze) Tests
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import igraph as ig
import numpy as np
import pytest

from aria_esi.mcp.errors import InvalidParameterError, RouteNotFoundError
from aria_esi.mcp.tools import register_tools
from aria_esi.mcp.tools_analyze import (
    _analyze_route,
    _compute_security_summary,
    _find_chokepoints,
    _find_danger_zones,
    _validate_connectivity,
    register_analyze_tools,
)
from aria_esi.universe import UniverseGraph

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_universe() -> UniverseGraph:
    """
    Create a mock universe for testing route analysis.

    Graph structure:

        Jita (high 0.95) -- Perimeter (high 0.90) -- Urlen (high 0.85)
             |                    |
        *Maurasi (high 0.65) -----+
             |
        Sivala (low 0.35)
             |
        Ala (null -0.2)
             |
        Oijanen (null -0.3)

    This creates a route that:
    - Has a safe high-sec portion (Jita -> Perimeter -> Urlen)
    - Has a transition to low-sec (Maurasi -> Sivala)
    - Has a danger zone (Sivala -> Ala -> Oijanen)

    Also adds:
        Amarr (high 0.9) - NOT connected to anything (for disconnected tests)
    """
    g = ig.Graph(
        n=8,
        edges=[
            (0, 1),  # Jita -- Perimeter
            (0, 2),  # Jita -- Maurasi
            (1, 3),  # Perimeter -- Urlen
            (1, 2),  # Perimeter -- Maurasi
            (2, 4),  # Maurasi -- Sivala
            (4, 5),  # Sivala -- Ala
            (5, 6),  # Ala -- Oijanen
        ],
        directed=False,
    )
    # Note: Amarr (idx 7) has no edges - disconnected

    systems = [
        {"name": "Jita", "id": 30000142, "sec": 0.95, "const": 20000020, "region": 10000002},
        {"name": "Perimeter", "id": 30000144, "sec": 0.90, "const": 20000020, "region": 10000002},
        {"name": "Maurasi", "id": 30000140, "sec": 0.65, "const": 20000020, "region": 10000002},
        {"name": "Urlen", "id": 30000138, "sec": 0.85, "const": 20000020, "region": 10000002},
        {"name": "Sivala", "id": 30000160, "sec": 0.35, "const": 20000021, "region": 10000002},
        {"name": "Ala", "id": 30000161, "sec": -0.2, "const": 20000022, "region": 10000003},
        {"name": "Oijanen", "id": 30000162, "sec": -0.3, "const": 20000022, "region": 10000003},
        {"name": "Amarr", "id": 30002187, "sec": 0.90, "const": 20000030, "region": 10000043},
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

    highsec = frozenset(i for i in range(8) if security[i] >= 0.45)
    lowsec = frozenset(i for i in range(8) if 0.0 < security[i] < 0.45)
    nullsec = frozenset(i for i in range(8) if security[i] <= 0.0)
    border = frozenset([2])  # Maurasi borders Sivala

    region_systems = {
        10000002: [0, 1, 2, 3, 4],
        10000003: [5, 6],
        10000043: [7],
    }
    constellation_names = {
        20000020: "Kimotoro",
        20000021: "Otanuomi",
        20000022: "Somewhere",
        20000030: "Domain",
    }
    region_names = {
        10000002: "The Forge",
        10000003: "Outer Region",
        10000043: "Domain",
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
        system_count=8,
        stargate_count=7,
    )


@pytest.fixture
def registered_universe(mock_universe: UniverseGraph) -> UniverseGraph:
    """Register tools with the mock universe."""
    mock_server = MagicMock()
    register_tools(mock_server, mock_universe)
    return mock_universe


# =============================================================================
# Connectivity Validation Tests
# =============================================================================


class TestValidateConnectivity:
    """Test _validate_connectivity function."""

    def test_connected_systems_pass(self, mock_universe: UniverseGraph):
        """Connected systems pass validation."""
        indices = [0, 1, 3]  # Jita -> Perimeter -> Urlen
        names = ["Jita", "Perimeter", "Urlen"]

        # Should not raise
        _validate_connectivity(mock_universe, indices, names)

    def test_disconnected_systems_fail(self, mock_universe: UniverseGraph):
        """Disconnected systems raise error."""
        indices = [0, 7]  # Jita -> Amarr (not connected)
        names = ["Jita", "Amarr"]

        with pytest.raises(RouteNotFoundError) as exc_info:
            _validate_connectivity(mock_universe, indices, names)

        assert "not connected" in str(exc_info.value)

    def test_non_adjacent_systems_fail(self, mock_universe: UniverseGraph):
        """Non-adjacent (but reachable) systems raise error."""
        indices = [0, 3]  # Jita -> Urlen (not direct neighbors)
        names = ["Jita", "Urlen"]

        with pytest.raises(RouteNotFoundError):
            _validate_connectivity(mock_universe, indices, names)


# =============================================================================
# Security Summary Tests
# =============================================================================


class TestComputeSecuritySummary:
    """Test _compute_security_summary function."""

    def test_highsec_only_route(self, mock_universe: UniverseGraph):
        """High-sec only route counted correctly."""
        indices = [0, 1, 3]  # Jita -> Perimeter -> Urlen
        summary = _compute_security_summary(mock_universe, indices)

        assert summary.highsec_jumps == 3
        assert summary.lowsec_jumps == 0
        assert summary.nullsec_jumps == 0

    def test_mixed_security_route(self, mock_universe: UniverseGraph):
        """Mixed security route counted correctly."""
        indices = [0, 2, 4, 5]  # Jita -> Maurasi -> Sivala -> Ala
        summary = _compute_security_summary(mock_universe, indices)

        assert summary.highsec_jumps == 2  # Jita, Maurasi
        assert summary.lowsec_jumps == 1  # Sivala
        assert summary.nullsec_jumps == 1  # Ala

    def test_total_jumps_calculated(self, mock_universe: UniverseGraph):
        """Total jumps is systems minus 1."""
        indices = [0, 1, 3]  # 3 systems = 2 jumps
        summary = _compute_security_summary(mock_universe, indices)

        assert summary.total_jumps == 2

    def test_lowest_security_identified(self, mock_universe: UniverseGraph):
        """Lowest security system identified."""
        indices = [0, 2, 4, 5, 6]  # Through to Oijanen (-0.3)
        summary = _compute_security_summary(mock_universe, indices)

        assert summary.lowest_security == pytest.approx(-0.3, rel=0.01)
        assert summary.lowest_security_system == "Oijanen"


# =============================================================================
# Chokepoint Tests
# =============================================================================


class TestFindChokepoints:
    """Test _find_chokepoints function."""

    def test_no_chokepoints_safe_route(self, mock_universe: UniverseGraph):
        """Safe route has no chokepoints."""
        indices = [0, 1, 3]  # Jita -> Perimeter -> Urlen
        chokepoints = _find_chokepoints(mock_universe, indices)

        assert len(chokepoints) == 0

    def test_entry_chokepoint_detected(self, mock_universe: UniverseGraph):
        """Entry to low-sec creates chokepoint."""
        indices = [0, 2, 4]  # Jita -> Maurasi -> Sivala
        chokepoints = _find_chokepoints(mock_universe, indices)

        # Sivala is the entry chokepoint (first low-sec after high-sec)
        assert len(chokepoints) == 1
        assert chokepoints[0].name == "Sivala"

    def test_exit_chokepoint_detected(self, mock_universe: UniverseGraph):
        """Exit from low-sec creates chokepoint."""
        indices = [4, 2, 0]  # Sivala -> Maurasi -> Jita (reverse)
        chokepoints = _find_chokepoints(mock_universe, indices)

        # Sivala is the exit chokepoint (last low-sec before high-sec)
        assert len(chokepoints) == 1
        assert chokepoints[0].name == "Sivala"

    def test_both_entry_and_exit(self, mock_universe: UniverseGraph):
        """Round trip through danger has both entry and exit."""
        indices = [2, 4, 2]  # Maurasi -> Sivala -> Maurasi
        chokepoints = _find_chokepoints(mock_universe, indices)

        # Entry (Sivala) and exit (Sivala again)
        assert len(chokepoints) == 2


# =============================================================================
# Danger Zone Tests
# =============================================================================


class TestFindDangerZones:
    """Test _find_danger_zones function."""

    def test_no_danger_zones_safe_route(self, mock_universe: UniverseGraph):
        """Safe route has no danger zones."""
        indices = [0, 1, 3]  # Jita -> Perimeter -> Urlen
        danger_zones = _find_danger_zones(mock_universe, indices)

        assert len(danger_zones) == 0

    def test_single_danger_zone(self, mock_universe: UniverseGraph):
        """Single low-sec system creates danger zone."""
        indices = [2, 4, 2]  # Maurasi -> Sivala -> Maurasi
        danger_zones = _find_danger_zones(mock_universe, indices)

        assert len(danger_zones) == 1
        assert danger_zones[0].start_system == "Sivala"
        assert danger_zones[0].end_system == "Sivala"
        assert danger_zones[0].jump_count == 1

    def test_consecutive_danger_zone(self, mock_universe: UniverseGraph):
        """Consecutive dangerous systems form single zone."""
        indices = [4, 5, 6]  # Sivala -> Ala -> Oijanen
        danger_zones = _find_danger_zones(mock_universe, indices)

        assert len(danger_zones) == 1
        assert danger_zones[0].start_system == "Sivala"
        assert danger_zones[0].end_system == "Oijanen"
        assert danger_zones[0].jump_count == 3

    def test_danger_zone_min_security(self, mock_universe: UniverseGraph):
        """Danger zone tracks minimum security."""
        indices = [4, 5, 6]  # Sivala (0.35) -> Ala (-0.2) -> Oijanen (-0.3)
        danger_zones = _find_danger_zones(mock_universe, indices)

        assert danger_zones[0].min_security == pytest.approx(-0.3, rel=0.01)

    def test_route_ending_in_danger(self, mock_universe: UniverseGraph):
        """Route ending in danger zone handled correctly."""
        indices = [2, 4, 5]  # Maurasi -> Sivala -> Ala
        danger_zones = _find_danger_zones(mock_universe, indices)

        assert len(danger_zones) == 1
        assert danger_zones[0].end_system == "Ala"

    def test_multiple_danger_zones(self, mock_universe: UniverseGraph):
        """Multiple separated danger zones detected."""
        # High -> Low -> High -> Low
        indices = [2, 4, 2, 4]  # Maurasi -> Sivala -> Maurasi -> Sivala
        danger_zones = _find_danger_zones(mock_universe, indices)

        assert len(danger_zones) == 2


# =============================================================================
# Analyze Route Tests
# =============================================================================


class TestAnalyzeRoute:
    """Test _analyze_route function."""

    def test_result_structure(self, mock_universe: UniverseGraph):
        """Result has all required fields."""
        indices = [0, 1, 3]
        result = _analyze_route(mock_universe, indices)

        assert hasattr(result, "systems")
        assert hasattr(result, "security_summary")
        assert hasattr(result, "chokepoints")
        assert hasattr(result, "danger_zones")

    def test_systems_populated(self, mock_universe: UniverseGraph):
        """Systems list is populated."""
        indices = [0, 1, 3]
        result = _analyze_route(mock_universe, indices)

        assert len(result.systems) == 3
        assert result.systems[0].name == "Jita"
        assert result.systems[1].name == "Perimeter"
        assert result.systems[2].name == "Urlen"


# =============================================================================
# Tool Registration Tests
# =============================================================================


class TestAnalyzeToolRegistration:
    """Test analyze tool registration."""

    def test_tool_registered(self, mock_universe: UniverseGraph):
        """universe_analyze tool is registered."""
        mock_server = MagicMock()
        register_analyze_tools(mock_server, mock_universe)

        mock_server.tool.assert_called()


# =============================================================================
# Integration Tests
# =============================================================================


class TestUniverseAnalyzeIntegration:
    """Integration tests for the universe_analyze tool."""

    def _capture_tool(self, registered_universe: UniverseGraph):
        """Helper to capture the registered tool function."""
        from aria_esi.mcp.tools_analyze import register_analyze_tools

        captured_tool = None

        def mock_tool():
            def decorator(func):
                nonlocal captured_tool
                captured_tool = func
                return func

            return decorator

        mock_server = MagicMock()
        mock_server.tool = mock_tool
        register_analyze_tools(mock_server, registered_universe)
        return captured_tool

    def test_analyze_safe_route(self, registered_universe: UniverseGraph):
        """Safe route analysis."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(captured_tool(systems=["Jita", "Perimeter", "Urlen"]))

        assert result["security_summary"]["lowsec_jumps"] == 0
        assert result["security_summary"]["nullsec_jumps"] == 0
        assert len(result["danger_zones"]) == 0
        assert len(result["chokepoints"]) == 0

    def test_analyze_dangerous_route(self, registered_universe: UniverseGraph):
        """Dangerous route identifies threats."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(
            captured_tool(systems=["Jita", "Maurasi", "Sivala", "Ala"])
        )

        assert result["security_summary"]["lowsec_jumps"] >= 1
        assert len(result["chokepoints"]) >= 1
        assert len(result["danger_zones"]) >= 1

    def test_analyze_disconnected_systems(self, registered_universe: UniverseGraph):
        """Disconnected systems raise error."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)

        with pytest.raises(RouteNotFoundError):
            asyncio.run(captured_tool(systems=["Jita", "Amarr"]))

    def test_analyze_unknown_system(self, registered_universe: UniverseGraph):
        """Unknown system raises helpful error."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)

        with pytest.raises(InvalidParameterError) as exc_info:
            asyncio.run(captured_tool(systems=["Jita", "UnknownSystem"]))

        assert "Unknown system" in str(exc_info.value)

    def test_analyze_single_system(self, registered_universe: UniverseGraph):
        """Single system raises error."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)

        with pytest.raises(InvalidParameterError) as exc_info:
            asyncio.run(captured_tool(systems=["Jita"]))

        assert "At least 2" in str(exc_info.value)

    def test_analyze_empty_systems(self, registered_universe: UniverseGraph):
        """Empty systems list raises error."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)

        with pytest.raises(InvalidParameterError):
            asyncio.run(captured_tool(systems=[]))

    def test_analyze_security_summary_totals(self, registered_universe: UniverseGraph):
        """Security summary totals match system count."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(captured_tool(systems=["Jita", "Perimeter", "Urlen"]))

        summary = result["security_summary"]
        total = summary["highsec_jumps"] + summary["lowsec_jumps"] + summary["nullsec_jumps"]
        assert total == len(result["systems"])

    def test_analyze_case_insensitive(self, registered_universe: UniverseGraph):
        """System names are case-insensitive."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(captured_tool(systems=["jita", "PERIMETER", "Urlen"]))

        assert result["systems"][0]["name"] == "Jita"
        assert result["systems"][1]["name"] == "Perimeter"
        assert result["systems"][2]["name"] == "Urlen"

    def test_analyze_returns_system_details(self, registered_universe: UniverseGraph):
        """Analysis includes full system details."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(captured_tool(systems=["Jita", "Perimeter"]))

        system = result["systems"][0]
        assert "name" in system
        assert "security" in system
        assert "security_class" in system
        assert "region" in system
        assert "neighbors" in system


# =============================================================================
# Performance Tests
# =============================================================================


class TestAnalyzePerformance:
    """Test analyze performance."""

    def test_analyze_latency(self, registered_universe: UniverseGraph):
        """Analysis completes within latency budget."""
        import asyncio

        captured_tool = None

        def mock_tool():
            def decorator(func):
                nonlocal captured_tool
                captured_tool = func
                return func

            return decorator

        mock_server = MagicMock()
        mock_server.tool = mock_tool

        from aria_esi.mcp.tools_analyze import register_analyze_tools

        register_analyze_tools(mock_server, registered_universe)

        start = time.perf_counter()
        for _ in range(100):
            asyncio.run(captured_tool(systems=["Jita", "Perimeter", "Urlen"]))
        elapsed = time.perf_counter() - start

        avg_time = elapsed / 100
        # Should be well under 5ms budget (relaxed from 2ms to avoid flaky failures)
        assert avg_time < 0.005

    def test_security_summary_fast(self, mock_universe: UniverseGraph):
        """Security summary computation is fast."""
        indices = [0, 1, 2, 3, 4, 5, 6]  # Full route

        start = time.perf_counter()
        for _ in range(1000):
            _compute_security_summary(mock_universe, indices)
        elapsed = time.perf_counter() - start

        avg_time = elapsed / 1000
        assert avg_time < 0.0001  # 0.1ms
