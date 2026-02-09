"""
Tests for Systems Tool Implementation.

STP-006: Systems Tool (universe_systems) Tests
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import igraph as ig
import numpy as np
import pytest

from aria_esi.mcp.tools import register_tools
from aria_esi.mcp.tools_systems import register_systems_tools
from aria_esi.mcp.utils import build_system_info
from aria_esi.universe import UniverseGraph

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_universe() -> UniverseGraph:
    """
    Create a mock universe for testing system lookups.

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
# Shared Utility Tests
# =============================================================================


class TestBuildSystemInfo:
    """Test build_system_info shared utility."""

    def test_system_info_fields(self, mock_universe: UniverseGraph):
        """SystemInfo has all required fields."""
        info = build_system_info(mock_universe, 0)  # Jita

        assert info.name == "Jita"
        assert info.system_id == 30000142
        assert info.security == pytest.approx(0.95, rel=0.01)
        assert info.security_class == "HIGH"
        assert info.constellation == "Kimotoro"
        assert info.constellation_id == 20000020
        assert info.region == "The Forge"
        assert info.region_id == 10000002

    def test_neighbors_included(self, mock_universe: UniverseGraph):
        """SystemInfo includes neighbor information."""
        info = build_system_info(mock_universe, 0)  # Jita

        # Jita has 2 neighbors: Perimeter and Maurasi
        assert len(info.neighbors) == 2
        neighbor_names = [n.name for n in info.neighbors]
        assert "Perimeter" in neighbor_names
        assert "Maurasi" in neighbor_names

    def test_neighbor_info_complete(self, mock_universe: UniverseGraph):
        """Neighbor info includes all fields."""
        info = build_system_info(mock_universe, 0)  # Jita

        for neighbor in info.neighbors:
            assert hasattr(neighbor, "name")
            assert hasattr(neighbor, "security")
            assert hasattr(neighbor, "security_class")
            assert neighbor.name in ["Perimeter", "Maurasi"]
            assert neighbor.security_class == "HIGH"

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

    def test_non_border_empty_adjacent(self, mock_universe: UniverseGraph):
        """Non-border systems have empty adjacent_lowsec."""
        jita = build_system_info(mock_universe, 0)
        assert jita.adjacent_lowsec == []


# =============================================================================
# Tool Registration Tests
# =============================================================================


class TestSystemsToolRegistration:
    """Test systems tool registration."""

    def test_tool_registered(self, mock_universe: UniverseGraph):
        """universe_systems tool is registered."""
        mock_server = MagicMock()
        register_systems_tools(mock_server, mock_universe)

        # Verify server.tool() decorator was called
        mock_server.tool.assert_called()


# =============================================================================
# Integration Tests
# =============================================================================


class TestUniverseSystemsIntegration:
    """Integration tests for the universe_systems tool."""

    def _capture_tool(self, registered_universe: UniverseGraph):
        """Helper to capture the registered tool function."""
        from aria_esi.mcp.tools_systems import register_systems_tools

        captured_tool = None

        def mock_tool():
            def decorator(func):
                nonlocal captured_tool
                captured_tool = func
                return func

            return decorator

        mock_server = MagicMock()
        mock_server.tool = mock_tool
        register_systems_tools(mock_server, registered_universe)
        return captured_tool

    def test_single_system_lookup(self, registered_universe: UniverseGraph):
        """Single system returns complete info."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(captured_tool(["Jita"]))

        assert result["found"] == 1
        assert result["not_found"] == 0
        assert len(result["systems"]) == 1
        assert result["systems"][0]["name"] == "Jita"
        assert result["systems"][0]["security_class"] == "HIGH"

    def test_batch_lookup_preserves_order(self, registered_universe: UniverseGraph):
        """Batch lookup preserves input order."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(captured_tool(["Sivala", "Jita", "Perimeter"]))

        assert result["found"] == 3
        assert result["systems"][0]["name"] == "Sivala"
        assert result["systems"][1]["name"] == "Jita"
        assert result["systems"][2]["name"] == "Perimeter"

    def test_unknown_system_returns_null(self, registered_universe: UniverseGraph):
        """Unknown systems return null in position."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(captured_tool(["Jita", "UnknownSystem", "Perimeter"]))

        assert result["found"] == 2
        assert result["not_found"] == 1
        assert result["systems"][0] is not None
        assert result["systems"][1] is None
        assert result["systems"][2] is not None

    def test_case_insensitive_lookup(self, registered_universe: UniverseGraph):
        """Lookup ignores case."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(captured_tool(["jita", "JITA", "JiTa"]))

        assert result["found"] == 3
        for sys in result["systems"]:
            assert sys["name"] == "Jita"  # Canonical form

    def test_empty_list_returns_empty(self, registered_universe: UniverseGraph):
        """Empty input returns empty results."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(captured_tool([]))

        assert result["found"] == 0
        assert result["not_found"] == 0
        assert result["systems"] == []

    def test_all_unknown_systems(self, registered_universe: UniverseGraph):
        """All unknown systems returns all nulls."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(captured_tool(["Unknown1", "Unknown2", "Unknown3"]))

        assert result["found"] == 0
        assert result["not_found"] == 3
        assert all(s is None for s in result["systems"])

    def test_neighbor_info_complete(self, registered_universe: UniverseGraph):
        """Neighbor info includes all fields."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(captured_tool(["Jita"]))

        neighbors = result["systems"][0]["neighbors"]
        assert len(neighbors) > 0
        for neighbor in neighbors:
            assert "name" in neighbor
            assert "security" in neighbor
            assert "security_class" in neighbor

    def test_lowsec_system_info(self, registered_universe: UniverseGraph):
        """Low-sec systems have correct security class."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(captured_tool(["Sivala"]))

        assert result["found"] == 1
        assert result["systems"][0]["name"] == "Sivala"
        assert result["systems"][0]["security_class"] == "LOW"
        assert result["systems"][0]["security"] == pytest.approx(0.35, rel=0.01)

    def test_nullsec_system_info(self, registered_universe: UniverseGraph):
        """Null-sec systems have correct security class."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(captured_tool(["Ala"]))

        assert result["found"] == 1
        assert result["systems"][0]["name"] == "Ala"
        assert result["systems"][0]["security_class"] == "NULL"
        assert result["systems"][0]["security"] == pytest.approx(-0.2, rel=0.01)

    def test_border_system_info(self, registered_universe: UniverseGraph):
        """Border system has is_border flag and adjacent_lowsec."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(captured_tool(["Maurasi"]))

        assert result["found"] == 1
        system = result["systems"][0]
        assert system["is_border"] is True
        assert "Sivala" in system["adjacent_lowsec"]


# =============================================================================
# Performance Tests
# =============================================================================


class TestSystemsPerformance:
    """Test system lookup performance."""

    def test_single_lookup_latency(self, registered_universe: UniverseGraph):
        """Single system lookup within latency budget."""
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

        from aria_esi.mcp.tools_systems import register_systems_tools

        register_systems_tools(mock_server, registered_universe)

        start = time.perf_counter()
        for _ in range(100):
            asyncio.run(captured_tool(["Jita"]))
        elapsed = time.perf_counter() - start

        avg_time = elapsed / 100
        # Should be fast (allow slack for CI environment variability)
        assert avg_time < 0.005

    def test_batch_lookup_latency(self, registered_universe: UniverseGraph):
        """Batch lookup within latency budget."""
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

        from aria_esi.mcp.tools_systems import register_systems_tools

        register_systems_tools(mock_server, registered_universe)

        start = time.perf_counter()
        for _ in range(100):
            asyncio.run(captured_tool(["Jita", "Perimeter", "Maurasi", "Urlen", "Sivala"]))
        elapsed = time.perf_counter() - start

        avg_time = elapsed / 100
        # 5 systems should still be fast (allow slack for parallel test execution)
        assert avg_time < 0.005  # 5ms threshold to avoid flaky failures

    def test_build_system_info_fast(self, mock_universe: UniverseGraph):
        """build_system_info is fast."""
        start = time.perf_counter()
        for _ in range(1000):
            build_system_info(mock_universe, 0)
        elapsed = time.perf_counter() - start

        avg_time = elapsed / 1000
        # Each call should be very fast
        assert avg_time < 0.0001  # 0.1ms
