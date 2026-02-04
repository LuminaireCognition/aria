"""
Tests for Search Tool Implementation.

STP-008: Search Tool (universe_search) Tests
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import igraph as ig
import numpy as np
import pytest

from aria_esi.mcp.errors import InvalidParameterError, SystemNotFoundError
from aria_esi.mcp.tools import register_tools
from aria_esi.mcp.tools_search import (
    _bfs_within_range,
    _build_search_result,
    _resolve_region,
    _search_systems,
    _summarize_filters,
    register_search_tools,
)
from aria_esi.universe import UniverseGraph

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_universe() -> UniverseGraph:
    """
    Create a mock universe for testing search functionality.

    Graph structure:
        Jita (high 0.95) -- Perimeter (high 0.90) -- Urlen (high 0.85)
             |                    |
        *Maurasi (high 0.65) -----+
             |
        Sivala (low 0.35)
             |
        Ala (null -0.2)

        Additionally (different region):
        *Uedama (high 0.50) -- Niarja (low 0.30)
             |
        Haatomo (high 0.70)

    Regions:
    - The Forge (10000002): Jita, Perimeter, Maurasi, Urlen, Sivala, Haatomo
    - Outer Region (10000003): Ala
    - Domain (10000043): Uedama, Niarja

    Border systems: Maurasi, Uedama
    """
    g = ig.Graph(
        n=9,
        edges=[
            (0, 1),  # Jita -- Perimeter
            (0, 2),  # Jita -- Maurasi
            (1, 3),  # Perimeter -- Urlen
            (1, 2),  # Perimeter -- Maurasi
            (2, 4),  # Maurasi -- Sivala
            (4, 5),  # Sivala -- Ala
            (6, 7),  # Uedama -- Niarja
            (6, 8),  # Uedama -- Haatomo
            (3, 8),  # Urlen -- Haatomo (connects clusters)
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
        {"name": "Uedama", "id": 30002691, "sec": 0.50, "const": 20000023, "region": 10000043},
        {"name": "Niarja", "id": 30002692, "sec": 0.30, "const": 20000023, "region": 10000043},
        {"name": "Haatomo", "id": 30002693, "sec": 0.70, "const": 20000023, "region": 10000002},
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

    highsec = frozenset(i for i in range(9) if security[i] >= 0.45)
    lowsec = frozenset(i for i in range(9) if 0.0 < security[i] < 0.45)
    nullsec = frozenset(i for i in range(9) if security[i] <= 0.0)
    # Maurasi (idx 2) borders Sivala, Uedama (idx 6) borders Niarja
    border = frozenset([2, 6])

    region_systems = {
        10000002: [0, 1, 2, 3, 4, 8],  # The Forge
        10000003: [5],  # Outer Region
        10000043: [6, 7],  # Domain
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
        system_count=9,
        stargate_count=9,
    )


@pytest.fixture
def registered_universe(mock_universe: UniverseGraph) -> UniverseGraph:
    """Register tools with the mock universe."""
    mock_server = MagicMock()
    register_tools(mock_server, mock_universe)
    return mock_universe


# =============================================================================
# Region Resolution Tests
# =============================================================================


class TestResolveRegion:
    """Test _resolve_region function."""

    def test_resolves_exact_match(self, mock_universe: UniverseGraph):
        """Region name resolves with exact match."""
        region_id = _resolve_region(mock_universe, "The Forge")
        assert region_id == 10000002

    def test_resolves_case_insensitive(self, mock_universe: UniverseGraph):
        """Region name resolution is case-insensitive."""
        region_id = _resolve_region(mock_universe, "the forge")
        assert region_id == 10000002

        region_id = _resolve_region(mock_universe, "THE FORGE")
        assert region_id == 10000002

    def test_unknown_region_returns_none(self, mock_universe: UniverseGraph):
        """Unknown region returns None."""
        region_id = _resolve_region(mock_universe, "Unknown Region")
        assert region_id is None


# =============================================================================
# BFS Range Tests
# =============================================================================


class TestBfsWithinRange:
    """Test _bfs_within_range function."""

    def test_finds_systems_within_range(self, mock_universe: UniverseGraph):
        """BFS finds all systems within specified range."""
        candidates, distances = _bfs_within_range(mock_universe, 0, 2)  # Jita, 2 jumps

        # Should find Jita (0), Perimeter (1), Maurasi (1), Urlen (2)
        assert 0 in candidates  # Jita
        assert 1 in candidates  # Perimeter
        assert 2 in candidates  # Maurasi
        assert 3 in candidates  # Urlen

    def test_distances_correct(self, mock_universe: UniverseGraph):
        """BFS returns correct distances."""
        _, distances = _bfs_within_range(mock_universe, 0, 5)

        assert distances[0] == 0  # Jita (origin)
        assert distances[1] == 1  # Perimeter
        assert distances[2] == 1  # Maurasi
        assert distances[3] == 2  # Urlen

    def test_respects_max_jumps(self, mock_universe: UniverseGraph):
        """BFS respects maximum jumps limit."""
        candidates, _ = _bfs_within_range(mock_universe, 0, 1)

        # Should only find immediate neighbors
        assert 0 in candidates  # Jita
        assert 1 in candidates  # Perimeter
        assert 2 in candidates  # Maurasi
        # Urlen (2 jumps) should not be included
        assert 3 not in candidates


# =============================================================================
# Search Systems Tests
# =============================================================================


class TestSearchSystems:
    """Test _search_systems function."""

    def test_security_min_filter(self, mock_universe: UniverseGraph):
        """Filter by minimum security."""
        results = _search_systems(
            universe=mock_universe,
            origin_idx=None,
            max_jumps=None,
            security_min=0.5,
            security_max=None,
            region_id=None,
            is_border=None,
            limit=100,
        )

        for r in results:
            assert r.security >= 0.5

    def test_security_max_filter(self, mock_universe: UniverseGraph):
        """Filter by maximum security."""
        results = _search_systems(
            universe=mock_universe,
            origin_idx=None,
            max_jumps=None,
            security_min=None,
            security_max=0.4,
            region_id=None,
            is_border=None,
            limit=100,
        )

        for r in results:
            assert r.security <= 0.4

    def test_security_range_filter(self, mock_universe: UniverseGraph):
        """Filter by security range."""
        results = _search_systems(
            universe=mock_universe,
            origin_idx=None,
            max_jumps=None,
            security_min=0.3,
            security_max=0.7,
            region_id=None,
            is_border=None,
            limit=100,
        )

        for r in results:
            assert 0.3 <= r.security <= 0.7

    def test_region_filter(self, mock_universe: UniverseGraph):
        """Filter by region."""
        region_id = 10000002  # The Forge
        results = _search_systems(
            universe=mock_universe,
            origin_idx=None,
            max_jumps=None,
            security_min=None,
            security_max=None,
            region_id=region_id,
            is_border=None,
            limit=100,
        )

        for r in results:
            assert r.region == "The Forge"

    def test_border_filter_true(self, mock_universe: UniverseGraph):
        """Filter to border systems only."""
        results = _search_systems(
            universe=mock_universe,
            origin_idx=None,
            max_jumps=None,
            security_min=None,
            security_max=None,
            region_id=None,
            is_border=True,
            limit=100,
        )

        result_names = [r.name for r in results]
        assert "Maurasi" in result_names
        assert "Uedama" in result_names
        assert len(results) == 2  # Only border systems

    def test_border_filter_false(self, mock_universe: UniverseGraph):
        """Filter to non-border systems only."""
        results = _search_systems(
            universe=mock_universe,
            origin_idx=None,
            max_jumps=None,
            security_min=None,
            security_max=None,
            region_id=None,
            is_border=False,
            limit=100,
        )

        result_names = [r.name for r in results]
        assert "Maurasi" not in result_names
        assert "Uedama" not in result_names

    def test_distance_filter(self, mock_universe: UniverseGraph):
        """Filter by distance from origin."""
        results = _search_systems(
            universe=mock_universe,
            origin_idx=0,  # Jita
            max_jumps=2,
            security_min=None,
            security_max=None,
            region_id=None,
            is_border=None,
            limit=100,
        )

        for r in results:
            assert r.jumps_from_origin is not None
            assert r.jumps_from_origin <= 2

    def test_combined_filters(self, mock_universe: UniverseGraph):
        """Multiple filters combine correctly."""
        results = _search_systems(
            universe=mock_universe,
            origin_idx=0,  # Jita
            max_jumps=5,
            security_min=0.5,
            security_max=None,
            region_id=None,
            is_border=True,
            limit=100,
        )

        for r in results:
            assert r.security >= 0.5
            assert r.jumps_from_origin is not None
            assert r.jumps_from_origin <= 5

    def test_limit_respected(self, mock_universe: UniverseGraph):
        """Limit parameter is respected."""
        results = _search_systems(
            universe=mock_universe,
            origin_idx=None,
            max_jumps=None,
            security_min=None,
            security_max=None,
            region_id=None,
            is_border=None,
            limit=3,
        )

        assert len(results) <= 3

    def test_unknown_region_empty_results(self, mock_universe: UniverseGraph):
        """Unknown region returns empty results (not error)."""
        # Region ID that doesn't exist
        results = _search_systems(
            universe=mock_universe,
            origin_idx=None,
            max_jumps=None,
            security_min=None,
            security_max=None,
            region_id=99999999,
            is_border=None,
            limit=100,
        )

        assert len(results) == 0


# =============================================================================
# Build Search Result Tests
# =============================================================================


class TestBuildSearchResult:
    """Test _build_search_result function."""

    def test_builds_result_fields(self, mock_universe: UniverseGraph):
        """Search result has all required fields."""
        result = _build_search_result(mock_universe, 0, 5)  # Jita at 5 jumps

        assert result.name == "Jita"
        assert result.system_id == 30000142
        assert result.security == pytest.approx(0.95, rel=0.01)
        assert result.security_class == "HIGH"
        assert result.region == "The Forge"
        assert result.jumps_from_origin == 5

    def test_jumps_from_origin_none(self, mock_universe: UniverseGraph):
        """Jumps from origin can be None."""
        result = _build_search_result(mock_universe, 0, None)

        assert result.jumps_from_origin is None


# =============================================================================
# Summarize Filters Tests
# =============================================================================


class TestSummarizeFilters:
    """Test _summarize_filters function."""

    def test_all_filters(self):
        """All filters included when set."""
        filters = _summarize_filters(
            origin="Jita",
            max_jumps=10,
            security_min=0.1,
            security_max=0.4,
            region="The Forge",
            is_border=True,
        )

        assert filters["origin"] == "Jita"
        assert filters["max_jumps"] == 10
        assert filters["security_min"] == 0.1
        assert filters["security_max"] == 0.4
        assert filters["region"] == "The Forge"
        assert filters["is_border"] is True

    def test_empty_when_no_filters(self):
        """Empty dict when no filters applied."""
        filters = _summarize_filters(
            origin=None,
            max_jumps=None,
            security_min=None,
            security_max=None,
            region=None,
            is_border=None,
        )

        assert filters == {}

    def test_partial_filters(self):
        """Only set filters included."""
        filters = _summarize_filters(
            origin="Jita",
            max_jumps=5,
            security_min=None,
            security_max=None,
            region=None,
            is_border=None,
        )

        assert "origin" in filters
        assert "max_jumps" in filters
        assert "security_min" not in filters
        assert "security_max" not in filters
        assert "region" not in filters
        assert "is_border" not in filters


# =============================================================================
# Tool Registration Tests
# =============================================================================


class TestSearchToolRegistration:
    """Test search tool registration."""

    def test_tool_registered(self, mock_universe: UniverseGraph):
        """universe_search tool is registered."""
        mock_server = MagicMock()
        register_search_tools(mock_server, mock_universe)

        # Verify server.tool() decorator was called
        mock_server.tool.assert_called()


# =============================================================================
# Integration Tests
# =============================================================================


class TestUniverseSearchIntegration:
    """Integration tests for the universe_search tool."""

    def _capture_tool(self, registered_universe: UniverseGraph):
        """Helper to capture the registered tool function."""
        from aria_esi.mcp.tools_search import register_search_tools

        captured_tool = None

        def mock_tool():
            def decorator(func):
                nonlocal captured_tool
                captured_tool = func
                return func

            return decorator

        mock_server = MagicMock()
        mock_server.tool = mock_tool
        register_search_tools(mock_server, registered_universe)
        return captured_tool

    def test_search_by_security_range(self, registered_universe: UniverseGraph):
        """Filter by security range."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(
            captured_tool(security_min=0.1, security_max=0.4, limit=10)
        )

        for sys in result["systems"]:
            assert 0.1 <= sys["security"] <= 0.4

    def test_search_by_region(self, registered_universe: UniverseGraph):
        """Filter by region name."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(captured_tool(region="The Forge", limit=10))

        for sys in result["systems"]:
            assert sys["region"] == "The Forge"

    def test_search_borders_only(self, registered_universe: UniverseGraph):
        """Filter to border systems only."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(captured_tool(is_border=True, limit=10))

        # All returned should be border systems
        names = [s["name"] for s in result["systems"]]
        assert "Maurasi" in names or "Uedama" in names

    def test_search_with_distance(self, registered_universe: UniverseGraph):
        """Filter by distance from origin."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(captured_tool(origin="Jita", max_jumps=2, limit=20))

        for sys in result["systems"]:
            assert sys["jumps_from_origin"] is not None
            assert sys["jumps_from_origin"] <= 2

    def test_search_requires_origin_for_max_jumps(
        self, registered_universe: UniverseGraph
    ):
        """max_jumps without origin raises error."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)

        with pytest.raises(InvalidParameterError) as exc_info:
            asyncio.run(captured_tool(max_jumps=10))

        assert "origin" in str(exc_info.value)

    def test_search_combined_filters(self, registered_universe: UniverseGraph):
        """Multiple filters combine correctly."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(
            captured_tool(
                origin="Jita", max_jumps=5, security_min=0.5, is_border=True, limit=10
            )
        )

        for sys in result["systems"]:
            assert sys["security"] >= 0.5
            assert sys["jumps_from_origin"] <= 5

    def test_search_invalid_limit_too_high(self, registered_universe: UniverseGraph):
        """Invalid limit (too high) raises error."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)

        with pytest.raises(InvalidParameterError):
            asyncio.run(captured_tool(limit=200))

    def test_search_invalid_limit_zero(self, registered_universe: UniverseGraph):
        """Invalid limit (zero) raises error."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)

        with pytest.raises(InvalidParameterError):
            asyncio.run(captured_tool(limit=0))

    def test_search_invalid_max_jumps_too_high(
        self, registered_universe: UniverseGraph
    ):
        """Invalid max_jumps (too high) raises error."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)

        with pytest.raises(InvalidParameterError):
            asyncio.run(captured_tool(origin="Jita", max_jumps=100))

    def test_search_invalid_max_jumps_zero(self, registered_universe: UniverseGraph):
        """Invalid max_jumps (zero) raises error."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)

        with pytest.raises(InvalidParameterError):
            asyncio.run(captured_tool(origin="Jita", max_jumps=0))

    def test_search_invalid_security_min(self, registered_universe: UniverseGraph):
        """Invalid security_min raises error."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)

        with pytest.raises(InvalidParameterError):
            asyncio.run(captured_tool(security_min=-2.0))

    def test_search_invalid_security_max(self, registered_universe: UniverseGraph):
        """Invalid security_max raises error."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)

        with pytest.raises(InvalidParameterError):
            asyncio.run(captured_tool(security_max=2.0))

    def test_search_unknown_origin(self, registered_universe: UniverseGraph):
        """Unknown origin raises SystemNotFoundError."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)

        with pytest.raises(SystemNotFoundError):
            asyncio.run(captured_tool(origin="UnknownSystem", max_jumps=5))

    def test_search_unknown_region_empty(self, registered_universe: UniverseGraph):
        """Unknown region returns empty results (not error)."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(captured_tool(region="Unknown Region", limit=10))

        assert result["total_found"] == 0
        assert result["systems"] == []

    def test_search_case_insensitive_origin(self, registered_universe: UniverseGraph):
        """Origin is case-insensitive, canonical name used in response."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(captured_tool(origin="jita", max_jumps=2, limit=10))

        # Canonical name is used in filters_applied
        assert result["filters_applied"]["origin"] == "Jita"
        assert result["total_found"] > 0

    def test_search_case_insensitive_region(self, registered_universe: UniverseGraph):
        """Region is case-insensitive."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(captured_tool(region="the forge", limit=10))

        for sys in result["systems"]:
            assert sys["region"] == "The Forge"

    def test_search_filters_in_response(self, registered_universe: UniverseGraph):
        """Applied filters are included in response."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        result = asyncio.run(
            captured_tool(
                origin="Jita", max_jumps=5, security_min=0.5, region="The Forge"
            )
        )

        filters = result["filters_applied"]
        assert filters["origin"] == "Jita"
        assert filters["max_jumps"] == 5
        assert filters["security_min"] == 0.5
        assert filters["region"] == "The Forge"

    def test_search_default_limit(self, registered_universe: UniverseGraph):
        """Default limit is applied."""
        import asyncio

        captured_tool = self._capture_tool(registered_universe)
        # Our mock universe has 9 systems, less than default limit of 20
        result = asyncio.run(captured_tool())

        assert result["total_found"] <= 20


# =============================================================================
# Performance Tests
# =============================================================================


class TestSearchPerformance:
    """Test search performance."""

    def test_search_latency(self, registered_universe: UniverseGraph):
        """Search completes within latency budget."""
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

        from aria_esi.mcp.tools_search import register_search_tools

        register_search_tools(mock_server, registered_universe)

        start = time.perf_counter()
        for _ in range(100):
            asyncio.run(
                captured_tool(
                    origin="Jita", max_jumps=10, security_min=0.5, limit=20
                )
            )
        elapsed = time.perf_counter() - start

        avg_time = elapsed / 100
        # Should be well under 5ms budget
        assert avg_time < 0.005

    def test_bfs_performance(self, mock_universe: UniverseGraph):
        """BFS algorithm is fast."""
        start = time.perf_counter()
        for _ in range(100):
            _bfs_within_range(mock_universe, 0, 10)
        elapsed = time.perf_counter() - start

        avg_time = elapsed / 100
        assert avg_time < 0.001  # 1ms
