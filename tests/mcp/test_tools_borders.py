"""
Tests for Borders Tool Implementation.

STP-007: Borders Tool (universe_borders) Tests
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import igraph as ig
import numpy as np
import pytest

from aria_esi.mcp.errors import InvalidParameterError, SystemNotFoundError
from aria_esi.mcp.tools import register_tools
from aria_esi.mcp.tools_borders import (
    _build_border_system,
    _find_border_systems,
    register_borders_tools,
)
from aria_esi.universe import UniverseGraph

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_universe() -> UniverseGraph:
    """
    Create a mock universe for testing border lookups.

    Graph structure (with border systems marked *):
        Jita (high 0.95) -- Perimeter (high 0.90) -- Urlen (high 0.85)
             |                    |
        *Maurasi (high 0.65) -----+
             |
        Sivala (low 0.35)
             |
        Ala (null -0.2)

        Additionally:
        *Uedama (high 0.50) -- Niarja (low 0.30)
             |
        Haatomo (high 0.70)

    Maurasi and Uedama are border systems (high-sec adjacent to low-sec)
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
            (6, 7),  # Uedama -- Niarja
            (6, 3),  # Uedama -- Urlen (connects the two clusters)
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
        {"name": "Uedama", "id": 30002691, "sec": 0.50, "const": 20000023, "region": 10000002},
        {"name": "Niarja", "id": 30002692, "sec": 0.30, "const": 20000023, "region": 10000002},
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
    # Maurasi (idx 2) borders Sivala, Uedama (idx 6) borders Niarja
    border = frozenset([2, 6])

    region_systems = {
        10000002: [0, 1, 2, 3, 4, 6, 7],
        10000003: [5],
    }
    constellation_names = {
        20000020: "Kimotoro",
        20000021: "Otanuomi",
        20000022: "Somewhere",
        20000023: "Uosusuokko",
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
        system_count=8,
        stargate_count=8,
    )


@pytest.fixture
def registered_universe(mock_universe: UniverseGraph) -> UniverseGraph:
    """Register tools with the mock universe."""
    mock_server = MagicMock()
    register_tools(mock_server, mock_universe)
    return mock_universe


# =============================================================================
# BFS Algorithm Tests
# =============================================================================


class TestFindBorderSystems:
    """Test _find_border_systems function."""

    def test_finds_nearby_borders(self, mock_universe: UniverseGraph):
        """BFS finds border systems near origin."""
        borders = _find_border_systems(mock_universe, 0, limit=10, max_jumps=15)

        # Should find Maurasi (1 jump) and Uedama (3 jumps via Jita->Perimeter->Urlen->Uedama)
        border_names = [b.name for b in borders]
        assert "Maurasi" in border_names
        assert "Uedama" in border_names

    def test_sorted_by_distance(self, mock_universe: UniverseGraph):
        """Results are sorted by distance."""
        borders = _find_border_systems(mock_universe, 0, limit=10, max_jumps=15)

        distances = [b.jumps_from_origin for b in borders]
        assert distances == sorted(distances)

    def test_respects_limit(self, mock_universe: UniverseGraph):
        """Limit parameter is respected."""
        borders = _find_border_systems(mock_universe, 0, limit=1, max_jumps=15)

        assert len(borders) <= 1

    def test_respects_max_jumps(self, mock_universe: UniverseGraph):
        """Max jumps parameter limits search radius."""
        # Maurasi is 1 jump from Jita
        borders = _find_border_systems(mock_universe, 0, limit=10, max_jumps=1)

        # Should find Maurasi at 1 jump
        assert len(borders) >= 1
        for b in borders:
            assert b.jumps_from_origin <= 1

    def test_origin_is_border(self, mock_universe: UniverseGraph):
        """Origin that is a border system appears at distance 0."""
        # Maurasi (idx 2) is a border system
        borders = _find_border_systems(mock_universe, 2, limit=10, max_jumps=15)

        # Maurasi should appear first at distance 0
        assert len(borders) > 0
        assert borders[0].name == "Maurasi"
        assert borders[0].jumps_from_origin == 0

    def test_stays_in_highsec(self, mock_universe: UniverseGraph):
        """BFS only traverses high-sec systems."""
        # From Jita, should not traverse through Sivala (low-sec) or Ala (null-sec)
        borders = _find_border_systems(mock_universe, 0, limit=10, max_jumps=15)

        # Should still find both border systems via high-sec paths
        border_names = [b.name for b in borders]
        assert "Maurasi" in border_names
        assert "Uedama" in border_names


class TestBuildBorderSystem:
    """Test _build_border_system function."""

    def test_border_system_fields(self, mock_universe: UniverseGraph):
        """BorderSystem has all required fields."""
        border = _build_border_system(mock_universe, 2, 1)  # Maurasi at 1 jump

        assert border.name == "Maurasi"
        assert border.system_id == 30000140
        assert border.security == pytest.approx(0.65, rel=0.01)
        assert border.jumps_from_origin == 1
        assert border.region == "The Forge"

    def test_adjacent_lowsec_populated(self, mock_universe: UniverseGraph):
        """Adjacent lowsec systems are listed."""
        border = _build_border_system(mock_universe, 2, 1)  # Maurasi

        # Maurasi is adjacent to Sivala (low-sec)
        assert "Sivala" in border.adjacent_lowsec

    def test_uedama_adjacent_lowsec(self, mock_universe: UniverseGraph):
        """Uedama's adjacent lowsec includes Niarja."""
        border = _build_border_system(mock_universe, 6, 3)  # Uedama at 3 jumps

        assert "Niarja" in border.adjacent_lowsec


# =============================================================================
# Tool Registration Tests
# =============================================================================


class TestBordersToolRegistration:
    """Test borders tool registration."""

    def test_tool_registered(self, mock_universe: UniverseGraph):
        """universe_borders tool is registered."""
        mock_server = MagicMock()
        register_borders_tools(mock_server, mock_universe)

        # Verify server.tool() decorator was called
        mock_server.tool.assert_called()


# =============================================================================
# Integration Tests
# =============================================================================


class TestUniverseBordersIntegration:
    """Integration tests for the universe_borders tool."""

    def _capture_tool(self, registered_universe: UniverseGraph):
        """Helper to capture the registered tool function."""
        from aria_esi.mcp.tools_borders import register_borders_tools

        captured_tool = None

        def mock_tool():
            def decorator(func):
                nonlocal captured_tool
                captured_tool = func
                return func

            return decorator

        mock_server = MagicMock()
        mock_server.tool = mock_tool
        register_borders_tools(mock_server, registered_universe)
        return captured_tool

    def test_borders_from_jita(self, registered_universe: UniverseGraph):
        """Find borders near Jita."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(captured_tool("Jita", limit=5, max_jumps=15))

        assert result["origin"] == "Jita"
        assert result["total_found"] >= 1
        assert len(result["borders"]) <= 5

    def test_borders_sorted_by_distance(self, registered_universe: UniverseGraph):
        """Results sorted by distance."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(captured_tool("Jita", limit=10, max_jumps=15))

        distances = [b["jumps_from_origin"] for b in result["borders"]]
        assert distances == sorted(distances)

    def test_borders_have_adjacent_lowsec(self, registered_universe: UniverseGraph):
        """Border systems have adjacent lowsec populated."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(captured_tool("Jita", limit=5, max_jumps=15))

        for border in result["borders"]:
            assert len(border["adjacent_lowsec"]) > 0

    def test_borders_respects_max_jumps(self, registered_universe: UniverseGraph):
        """Max jumps limits search radius."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(captured_tool("Jita", max_jumps=1, limit=50))

        for border in result["borders"]:
            assert border["jumps_from_origin"] <= 1

    def test_borders_invalid_limit(self, registered_universe: UniverseGraph):
        """Invalid limit raises error."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)

        with pytest.raises(InvalidParameterError):
            asyncio.run(captured_tool("Jita", limit=100, max_jumps=15))  # Over max

    def test_borders_invalid_limit_zero(self, registered_universe: UniverseGraph):
        """Zero limit raises error."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)

        with pytest.raises(InvalidParameterError):
            asyncio.run(captured_tool("Jita", limit=0, max_jumps=15))

    def test_borders_invalid_max_jumps(self, registered_universe: UniverseGraph):
        """Invalid max_jumps raises error."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)

        with pytest.raises(InvalidParameterError):
            asyncio.run(captured_tool("Jita", limit=10, max_jumps=50))  # Over max

    def test_borders_invalid_max_jumps_zero(self, registered_universe: UniverseGraph):
        """Zero max_jumps raises error."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)

        with pytest.raises(InvalidParameterError):
            asyncio.run(captured_tool("Jita", limit=10, max_jumps=0))

    def test_borders_origin_is_border(self, registered_universe: UniverseGraph):
        """Origin that is a border system appears at distance 0."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(captured_tool("Maurasi", limit=5, max_jumps=15))

        # Maurasi should appear first at distance 0
        assert result["total_found"] >= 1
        first = result["borders"][0]
        assert first["name"] == "Maurasi"
        assert first["jumps_from_origin"] == 0

    def test_borders_unknown_system(self, registered_universe: UniverseGraph):
        """Unknown origin raises error."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)

        with pytest.raises(SystemNotFoundError):
            asyncio.run(captured_tool("UnknownSystem", limit=5, max_jumps=15))

    def test_borders_case_insensitive(self, registered_universe: UniverseGraph):
        """Origin is case-insensitive."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(captured_tool("jita", limit=5, max_jumps=15))

        assert result["origin"] == "Jita"  # Canonical form
        assert result["total_found"] >= 1

    def test_search_radius_in_response(self, registered_universe: UniverseGraph):
        """Search radius is included in response."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(captured_tool("Jita", limit=5, max_jumps=10))

        assert result["search_radius"] == 10


# =============================================================================
# Performance Tests
# =============================================================================


class TestBordersPerformance:
    """Test border discovery performance."""

    def test_borders_latency(self, registered_universe: UniverseGraph):
        """Border discovery within latency budget."""
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

        from aria_esi.mcp.tools_borders import register_borders_tools

        register_borders_tools(mock_server, registered_universe)

        start = time.perf_counter()
        for _ in range(100):
            asyncio.run(captured_tool("Jita", limit=10, max_jumps=15))
        elapsed = time.perf_counter() - start

        avg_time = elapsed / 100
        # Should be well under 3ms (allows for CI variability)
        assert avg_time < 0.003

    def test_bfs_performance(self, mock_universe: UniverseGraph):
        """BFS algorithm is fast."""
        start = time.perf_counter()
        for _ in range(100):
            _find_border_systems(mock_universe, 0, limit=10, max_jumps=15)
        elapsed = time.perf_counter() - start

        avg_time = elapsed / 100
        assert avg_time < 0.001  # 1ms
