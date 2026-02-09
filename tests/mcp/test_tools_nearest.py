"""
Tests for Nearest Tool Implementation.

STP-011: Nearest Tool (universe_nearest) Tests
"""

from __future__ import annotations

from unittest.mock import MagicMock

import igraph as ig
import numpy as np
import pytest

from aria_esi.mcp.errors import InvalidParameterError, SystemNotFoundError
from aria_esi.mcp.tools import register_tools
from aria_esi.mcp.tools_nearest import (
    _build_predicate,
    _build_result,
    _find_nearest,
    _summarize_predicates,
    register_nearest_tools,
)
from aria_esi.universe import UniverseGraph

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_universe() -> UniverseGraph:
    """
    Create a mock universe for testing nearest lookups.

    Graph structure:
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
        Haatomo (high 0.70) -- Urlen

    Border systems: Maurasi, Uedama (high-sec adjacent to low-sec)
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
# Predicate Building Tests
# =============================================================================


class TestBuildPredicate:
    """Test predicate construction."""

    def test_border_predicate_true(self, mock_universe: UniverseGraph):
        """Border predicate filters correctly."""
        predicate = _build_predicate(
            universe=mock_universe,
            is_border=True,
            min_adjacent_lowsec=None,
            security_min=None,
            security_max=None,
            region_id=None,
        )
        # Maurasi (idx 2) is a border system
        assert predicate(2) is True
        # Jita (idx 0) is not a border system
        assert predicate(0) is False

    def test_border_predicate_false(self, mock_universe: UniverseGraph):
        """Non-border predicate filters correctly."""
        predicate = _build_predicate(
            universe=mock_universe,
            is_border=False,
            min_adjacent_lowsec=None,
            security_min=None,
            security_max=None,
            region_id=None,
        )
        # Jita (idx 0) is not a border system
        assert predicate(0) is True
        # Maurasi (idx 2) is a border system
        assert predicate(2) is False

    def test_security_range_predicate(self, mock_universe: UniverseGraph):
        """Security range predicate filters correctly."""
        predicate = _build_predicate(
            universe=mock_universe,
            is_border=None,
            min_adjacent_lowsec=None,
            security_min=0.5,
            security_max=0.7,
            region_id=None,
        )
        # Maurasi (0.65) is in range
        assert predicate(2) is True
        # Uedama (0.50) is at boundary
        assert predicate(6) is True
        # Jita (0.95) is above range
        assert predicate(0) is False
        # Sivala (0.35) is below range
        assert predicate(4) is False

    def test_min_adjacent_lowsec_predicate(self, mock_universe: UniverseGraph):
        """Adjacent low-sec count predicate filters correctly."""
        predicate = _build_predicate(
            universe=mock_universe,
            is_border=None,
            min_adjacent_lowsec=1,
            security_min=None,
            security_max=None,
            region_id=None,
        )
        # Maurasi has 1 adjacent low-sec (Sivala)
        assert predicate(2) is True
        # Jita has 0 adjacent low-sec
        assert predicate(0) is False

    def test_region_predicate(self, mock_universe: UniverseGraph):
        """Region predicate filters correctly."""
        predicate = _build_predicate(
            universe=mock_universe,
            is_border=None,
            min_adjacent_lowsec=None,
            security_min=None,
            security_max=None,
            region_id=10000002,
        )
        # Jita is in The Forge
        assert predicate(0) is True
        # Ala is in Outer Region
        assert predicate(5) is False

    def test_combined_predicates(self, mock_universe: UniverseGraph):
        """Combined predicates work correctly."""
        predicate = _build_predicate(
            universe=mock_universe,
            is_border=True,
            min_adjacent_lowsec=None,
            security_min=0.6,
            security_max=0.7,
            region_id=10000002,
        )
        # Maurasi: border, 0.65 security, The Forge
        assert predicate(2) is True
        # Uedama: border, 0.50 security (below min)
        assert predicate(6) is False


# =============================================================================
# Find Nearest Tests
# =============================================================================


class TestFindNearest:
    """Test nearest system finding."""

    def test_finds_nearest_border(self, mock_universe: UniverseGraph):
        """Finds nearest border system."""
        predicate = _build_predicate(
            universe=mock_universe,
            is_border=True,
            min_adjacent_lowsec=None,
            security_min=None,
            security_max=None,
            region_id=None,
        )
        # From Jita, nearest border is Maurasi (1 jump)
        results = _find_nearest(mock_universe, 0, predicate, limit=5, max_jumps=10)
        assert len(results) >= 1
        assert results[0].name == "Maurasi"
        assert results[0].jumps_from_origin == 1

    def test_respects_limit(self, mock_universe: UniverseGraph):
        """Respects result limit."""
        predicate = _build_predicate(
            universe=mock_universe,
            is_border=True,
            min_adjacent_lowsec=None,
            security_min=None,
            security_max=None,
            region_id=None,
        )
        results = _find_nearest(mock_universe, 0, predicate, limit=1, max_jumps=10)
        assert len(results) == 1

    def test_respects_max_jumps(self, mock_universe: UniverseGraph):
        """Respects max_jumps limit."""
        predicate = _build_predicate(
            universe=mock_universe,
            is_border=True,
            min_adjacent_lowsec=None,
            security_min=None,
            security_max=None,
            region_id=None,
        )
        # Uedama is 3 jumps from Jita (Jita -> Perimeter -> Urlen -> Uedama)
        results = _find_nearest(mock_universe, 0, predicate, limit=5, max_jumps=2)
        # Should only find Maurasi, not Uedama
        names = [r.name for r in results]
        assert "Maurasi" in names
        assert "Uedama" not in names

    def test_results_distance_ordered(self, mock_universe: UniverseGraph):
        """Results are ordered by distance."""
        predicate = _build_predicate(
            universe=mock_universe,
            is_border=True,
            min_adjacent_lowsec=None,
            security_min=None,
            security_max=None,
            region_id=None,
        )
        results = _find_nearest(mock_universe, 0, predicate, limit=5, max_jumps=10)
        distances = [r.jumps_from_origin for r in results]
        assert distances == sorted(distances)


# =============================================================================
# Result Building Tests
# =============================================================================


class TestBuildResult:
    """Test result object construction."""

    def test_builds_complete_result(self, mock_universe: UniverseGraph):
        """Builds complete search result."""
        result = _build_result(mock_universe, 0, 3)
        assert result.name == "Jita"
        assert result.system_id == 30000142
        assert result.security == pytest.approx(0.95, abs=0.01)
        assert result.security_class == "HIGH"
        assert result.region == "The Forge"
        assert result.jumps_from_origin == 3


class TestSummarizePredicates:
    """Test predicate summary generation."""

    def test_empty_predicates(self):
        """Empty predicates returns empty dict."""
        result = _summarize_predicates(None, None, None, None, None)
        assert result == {}

    def test_all_predicates(self):
        """All predicates included in summary."""
        result = _summarize_predicates(
            is_border=True,
            min_adjacent_lowsec=2,
            security_min=0.5,
            security_max=0.8,
            region="The Forge",
        )
        assert result["is_border"] is True
        assert result["min_adjacent_lowsec"] == 2
        assert result["security_min"] == 0.5
        assert result["security_max"] == 0.8
        assert result["region"] == "The Forge"


# =============================================================================
# Integration Tests
# =============================================================================


# Import the capture helper from conftest
from tests.mcp.conftest import capture_tool_function


class TestUniverseNearestIntegration:
    """Integration tests for universe_nearest tool via async invocation."""

    @pytest.mark.asyncio
    async def test_finds_nearest_border_systems(self, registered_universe: UniverseGraph):
        """Tool finds nearest border systems with full response structure."""
        tool = capture_tool_function(registered_universe, register_nearest_tools)
        result = await tool(origin="Jita", is_border=True, limit=5, max_jumps=10)

        assert result["origin"] == "Jita"
        assert result["total_found"] >= 1
        assert result["search_radius"] == 10
        assert "systems" in result
        assert "predicates" in result
        assert result["predicates"]["is_border"] is True

        # Maurasi should be the nearest border (1 jump from Jita)
        if result["systems"]:
            assert result["systems"][0]["name"] == "Maurasi"
            assert result["systems"][0]["jumps_from_origin"] == 1

    @pytest.mark.asyncio
    async def test_finds_nearest_with_security_range(self, registered_universe: UniverseGraph):
        """Tool filters by security range."""
        tool = capture_tool_function(registered_universe, register_nearest_tools)
        result = await tool(
            origin="Jita",
            security_min=0.3,
            security_max=0.4,
            limit=5,
            max_jumps=10,
        )

        assert result["origin"] == "Jita"
        assert result["predicates"]["security_min"] == 0.3
        assert result["predicates"]["security_max"] == 0.4

        # Sivala (0.35) should match
        names = [s["name"] for s in result["systems"]]
        assert "Sivala" in names

    @pytest.mark.asyncio
    async def test_finds_nearest_with_min_adjacent_lowsec(self, registered_universe: UniverseGraph):
        """Tool filters by minimum adjacent low-sec systems."""
        tool = capture_tool_function(registered_universe, register_nearest_tools)
        result = await tool(
            origin="Jita",
            min_adjacent_lowsec=1,
            limit=5,
            max_jumps=10,
        )

        assert result["predicates"]["min_adjacent_lowsec"] == 1
        # Maurasi has 1 adjacent low-sec (Sivala)
        names = [s["name"] for s in result["systems"]]
        assert "Maurasi" in names

    @pytest.mark.asyncio
    async def test_finds_nearest_with_region_filter(self, registered_universe: UniverseGraph):
        """Tool filters by region."""
        tool = capture_tool_function(registered_universe, register_nearest_tools)
        result = await tool(
            origin="Jita",
            region="The Forge",
            limit=10,
            max_jumps=10,
        )

        assert result["predicates"]["region"] == "The Forge"
        # All results should be in The Forge
        for system in result["systems"]:
            assert system["region"] == "The Forge"

    @pytest.mark.asyncio
    async def test_unknown_region_returns_empty_with_warning(self, registered_universe: UniverseGraph):
        """Unknown region returns empty results with warning."""
        tool = capture_tool_function(registered_universe, register_nearest_tools)
        result = await tool(
            origin="Jita",
            region="NonexistentRegion",
            limit=5,
            max_jumps=10,
        )

        assert result["total_found"] == 0
        assert result["systems"] == []
        assert "warning" in result
        assert "NonexistentRegion" in result["warning"]

    @pytest.mark.asyncio
    async def test_respects_limit_parameter(self, registered_universe: UniverseGraph):
        """Tool respects the limit parameter."""
        tool = capture_tool_function(registered_universe, register_nearest_tools)
        result = await tool(origin="Jita", limit=1, max_jumps=10)

        assert len(result["systems"]) <= 1

    @pytest.mark.asyncio
    async def test_respects_max_jumps_parameter(self, registered_universe: UniverseGraph):
        """Tool respects the max_jumps parameter."""
        tool = capture_tool_function(registered_universe, register_nearest_tools)
        result = await tool(origin="Jita", max_jumps=1, limit=10)

        # All results should be within 1 jump
        for system in result["systems"]:
            assert system["jumps_from_origin"] <= 1

    @pytest.mark.asyncio
    async def test_invalid_limit_zero_raises(self, registered_universe: UniverseGraph):
        """Invalid limit (0) raises error."""
        tool = capture_tool_function(registered_universe, register_nearest_tools)
        with pytest.raises(InvalidParameterError) as exc_info:
            await tool(origin="Jita", limit=0)
        assert exc_info.value.param == "limit"

    @pytest.mark.asyncio
    async def test_invalid_limit_too_high_raises(self, registered_universe: UniverseGraph):
        """Invalid limit (> 50) raises error."""
        tool = capture_tool_function(registered_universe, register_nearest_tools)
        with pytest.raises(InvalidParameterError) as exc_info:
            await tool(origin="Jita", limit=100)
        assert exc_info.value.param == "limit"

    @pytest.mark.asyncio
    async def test_invalid_max_jumps_zero_raises(self, registered_universe: UniverseGraph):
        """Invalid max_jumps (0) raises error."""
        tool = capture_tool_function(registered_universe, register_nearest_tools)
        with pytest.raises(InvalidParameterError) as exc_info:
            await tool(origin="Jita", max_jumps=0)
        assert exc_info.value.param == "max_jumps"

    @pytest.mark.asyncio
    async def test_invalid_max_jumps_too_high_raises(self, registered_universe: UniverseGraph):
        """Invalid max_jumps (> 50) raises error."""
        tool = capture_tool_function(registered_universe, register_nearest_tools)
        with pytest.raises(InvalidParameterError) as exc_info:
            await tool(origin="Jita", max_jumps=100)
        assert exc_info.value.param == "max_jumps"

    @pytest.mark.asyncio
    async def test_invalid_security_min_raises(self, registered_universe: UniverseGraph):
        """Invalid security_min (< -1.0 or > 1.0) raises error."""
        tool = capture_tool_function(registered_universe, register_nearest_tools)
        with pytest.raises(InvalidParameterError) as exc_info:
            await tool(origin="Jita", security_min=2.0)
        assert exc_info.value.param == "security_min"

    @pytest.mark.asyncio
    async def test_invalid_security_max_raises(self, registered_universe: UniverseGraph):
        """Invalid security_max (< -1.0 or > 1.0) raises error."""
        tool = capture_tool_function(registered_universe, register_nearest_tools)
        with pytest.raises(InvalidParameterError) as exc_info:
            await tool(origin="Jita", security_max=-2.0)
        assert exc_info.value.param == "security_max"

    @pytest.mark.asyncio
    async def test_invalid_min_adjacent_lowsec_raises(self, registered_universe: UniverseGraph):
        """Invalid min_adjacent_lowsec (< 1) raises error."""
        tool = capture_tool_function(registered_universe, register_nearest_tools)
        with pytest.raises(InvalidParameterError) as exc_info:
            await tool(origin="Jita", min_adjacent_lowsec=0)
        assert exc_info.value.param == "min_adjacent_lowsec"

    @pytest.mark.asyncio
    async def test_unknown_origin_raises(self, registered_universe: UniverseGraph):
        """Unknown origin system raises SystemNotFoundError."""
        tool = capture_tool_function(registered_universe, register_nearest_tools)
        with pytest.raises(SystemNotFoundError):
            await tool(origin="NonexistentSystem")

    @pytest.mark.asyncio
    async def test_case_insensitive_origin(self, registered_universe: UniverseGraph):
        """Origin system name is case-insensitive."""
        tool = capture_tool_function(registered_universe, register_nearest_tools)
        result = await tool(origin="jita", limit=1, max_jumps=5)

        # Should resolve "jita" to "Jita"
        assert result["origin"] == "Jita"

    @pytest.mark.asyncio
    async def test_is_border_false_excludes_borders(self, registered_universe: UniverseGraph):
        """is_border=False excludes border systems."""
        tool = capture_tool_function(registered_universe, register_nearest_tools)
        result = await tool(origin="Jita", is_border=False, limit=10, max_jumps=10)

        # Maurasi and Uedama are border systems, should not appear
        names = [s["name"] for s in result["systems"]]
        assert "Maurasi" not in names
        assert "Uedama" not in names

    @pytest.mark.asyncio
    async def test_combined_predicates(self, registered_universe: UniverseGraph):
        """Multiple predicates combine correctly."""
        tool = capture_tool_function(registered_universe, register_nearest_tools)
        result = await tool(
            origin="Jita",
            is_border=True,
            security_min=0.6,
            security_max=0.7,
            region="The Forge",
            limit=5,
            max_jumps=10,
        )

        # Maurasi (0.65, border, The Forge) should match
        names = [s["name"] for s in result["systems"]]
        if names:
            assert "Maurasi" in names


# =============================================================================
# Performance Tests
# =============================================================================


class TestNearestPerformance:
    """Performance tests for nearest tool."""

    def test_predicate_build_fast(self, mock_universe: UniverseGraph):
        """Predicate building is fast."""
        import time

        start = time.perf_counter()
        for _ in range(1000):
            _build_predicate(
                universe=mock_universe,
                is_border=True,
                min_adjacent_lowsec=1,
                security_min=0.5,
                security_max=0.8,
                region_id=10000002,
            )
        elapsed = time.perf_counter() - start
        assert elapsed < 0.1  # 1000 builds in under 100ms

    def test_find_nearest_fast(self, mock_universe: UniverseGraph):
        """Finding nearest is fast."""
        import time

        predicate = _build_predicate(
            universe=mock_universe,
            is_border=True,
            min_adjacent_lowsec=None,
            security_min=None,
            security_max=None,
            region_id=None,
        )
        start = time.perf_counter()
        for _ in range(100):
            _find_nearest(mock_universe, 0, predicate, limit=5, max_jumps=10)
        elapsed = time.perf_counter() - start
        assert elapsed < 0.1  # 100 searches in under 100ms
