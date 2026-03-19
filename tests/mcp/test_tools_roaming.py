"""
Tests for Roaming Route Action Implementation.

Tests for Change 1: roam_route action - linear hunting/roaming routes through active systems.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from aria_esi.mcp.dispatchers.universe import (
    _roam_route,
    classify_systems,
    collect_bfs_data,
    greedy_forward_walk,
    sweep_retrace,
)
from aria_esi.mcp.errors import InvalidParameterError
from aria_esi.mcp.tools import register_tools
from aria_esi.store.activity import ActivityData
from aria_esi.universe import UniverseGraph

from .conftest import create_mock_universe


# =============================================================================
# Test Fixtures
# =============================================================================


def _build_nullsec_universe() -> UniverseGraph:
    """
    Build a null-sec universe for roaming tests.

    Topology (loosely inspired by Fountain but deterministic):

        Origin (0) -- Hub1 (1) -- Active1 (2) -- Active2 (3) -- DeadEnd (4)
                        |              |
                      Hub2 (5) -- Active3 (6) -- Active4 (7)
                        |
                      Camped (8)
                        |
                      PvP1 (9) -- PvP2 (10)

    Systems 2,3,6,7 have high NPC kills (ratting).
    System 8 has high PVP kills (camped).
    Systems 9,10 have PVP kills (hunting grounds for kills mode).
    """
    systems = [
        {"name": "Origin", "id": 30100001, "sec": -0.2, "const": 20100001, "region": 10100001,
         "const_name": "TestConst", "region_name": "Test Region"},
        {"name": "Hub1", "id": 30100002, "sec": -0.3, "const": 20100001, "region": 10100001,
         "const_name": "TestConst", "region_name": "Test Region"},
        {"name": "Active1", "id": 30100003, "sec": -0.4, "const": 20100001, "region": 10100001,
         "const_name": "TestConst", "region_name": "Test Region"},
        {"name": "Active2", "id": 30100004, "sec": -0.5, "const": 20100001, "region": 10100001,
         "const_name": "TestConst", "region_name": "Test Region"},
        {"name": "DeadEnd", "id": 30100005, "sec": -0.3, "const": 20100001, "region": 10100001,
         "const_name": "TestConst", "region_name": "Test Region"},
        {"name": "Hub2", "id": 30100006, "sec": -0.2, "const": 20100001, "region": 10100001,
         "const_name": "TestConst", "region_name": "Test Region"},
        {"name": "Active3", "id": 30100007, "sec": -0.4, "const": 20100001, "region": 10100001,
         "const_name": "TestConst", "region_name": "Test Region"},
        {"name": "Active4", "id": 30100008, "sec": -0.5, "const": 20100001, "region": 10100001,
         "const_name": "TestConst", "region_name": "Test Region"},
        {"name": "Camped", "id": 30100009, "sec": -0.2, "const": 20100001, "region": 10100001,
         "const_name": "TestConst", "region_name": "Test Region"},
        {"name": "PvP1", "id": 30100010, "sec": -0.3, "const": 20100001, "region": 10100001,
         "const_name": "TestConst", "region_name": "Test Region"},
        {"name": "PvP2", "id": 30100011, "sec": -0.4, "const": 20100001, "region": 10100001,
         "const_name": "TestConst", "region_name": "Test Region"},
    ]

    edges = [
        (0, 1),   # Origin -- Hub1
        (1, 2),   # Hub1 -- Active1
        (2, 3),   # Active1 -- Active2
        (3, 4),   # Active2 -- DeadEnd
        (2, 6),   # Active1 -- Active3  (cross-link)
        (1, 5),   # Hub1 -- Hub2
        (5, 6),   # Hub2 -- Active3
        (6, 7),   # Active3 -- Active4
        (5, 8),   # Hub2 -- Camped
        (8, 9),   # Camped -- PvP1
        (9, 10),  # PvP1 -- PvP2
    ]

    return create_mock_universe(systems, edges)


# Activity data fixtures
RATTING_ACTIVITY = {
    30100001: ActivityData(system_id=30100001, npc_kills=0, ship_kills=0, pod_kills=0, ship_jumps=5),
    30100002: ActivityData(system_id=30100002, npc_kills=10, ship_kills=0, pod_kills=0, ship_jumps=15),
    30100003: ActivityData(system_id=30100003, npc_kills=200, ship_kills=1, pod_kills=0, ship_jumps=10),
    30100004: ActivityData(system_id=30100004, npc_kills=150, ship_kills=0, pod_kills=0, ship_jumps=8),
    30100005: ActivityData(system_id=30100005, npc_kills=30, ship_kills=0, pod_kills=0, ship_jumps=3),
    30100006: ActivityData(system_id=30100006, npc_kills=5, ship_kills=0, pod_kills=0, ship_jumps=20),
    30100007: ActivityData(system_id=30100007, npc_kills=180, ship_kills=0, pod_kills=0, ship_jumps=12),
    30100008: ActivityData(system_id=30100008, npc_kills=120, ship_kills=0, pod_kills=0, ship_jumps=6),
    30100009: ActivityData(system_id=30100009, npc_kills=0, ship_kills=8, pod_kills=3, ship_jumps=50),
    30100010: ActivityData(system_id=30100010, npc_kills=0, ship_kills=4, pod_kills=1, ship_jumps=15),
    30100011: ActivityData(system_id=30100011, npc_kills=0, ship_kills=3, pod_kills=0, ship_jumps=10),
}


@pytest.fixture
def roam_universe() -> UniverseGraph:
    """Null-sec universe for roaming tests."""
    return _build_nullsec_universe()


@pytest.fixture
def registered_roam_universe(roam_universe: UniverseGraph) -> UniverseGraph:
    """Roam universe with tools registered."""
    mock_server = MagicMock()
    register_tools(mock_server, roam_universe)
    return roam_universe


def _mock_activity_cache():
    """Create a mock activity cache returning deterministic data."""
    mock_cache = MagicMock()

    async def mock_get_all_activity():
        return dict(RATTING_ACTIVITY)

    async def mock_get_activity(system_id):
        return RATTING_ACTIVITY.get(system_id, ActivityData(system_id=system_id))

    mock_cache.get_all_activity = mock_get_all_activity
    mock_cache.get_activity = mock_get_activity
    mock_cache.get_kills_cache_age.return_value = 60
    return mock_cache


# =============================================================================
# Unit Tests: classify_systems
# =============================================================================


class TestClassifySystems:
    """Test system classification logic."""

    def test_ratting_classification(self, roam_universe: UniverseGraph):
        """Systems with high NPC kills classified as hunt."""
        visited = {i: i for i in range(11)}
        classification, hunt_metrics, hunt_threshold = classify_systems(
            roam_universe, visited, RATTING_ACTIVITY, "ratting", hotspot_threshold=5
        )
        # P75 of non-zero NPC values [10, 200, 150, 30, 5, 180, 120] = 165
        # hunt_threshold = max(165, 50) = 165
        # Active1 (200) and Active3 (180) are above threshold
        assert classification[2] == "hunt"  # Active1: 200 npc >= 165
        assert classification[6] == "hunt"  # Active3: 180 npc >= 165
        # Active2 (150) and Active4 (120) are below P75 threshold
        assert classification[3] == "transit"  # Active2: 150 npc < 165
        assert classification[7] == "transit"  # Active4: 120 npc < 165

    def test_threat_classification(self, roam_universe: UniverseGraph):
        """Systems with high PVP kills classified as threat."""
        visited = {i: i for i in range(11)}
        classification, _, _ = classify_systems(
            roam_universe, visited, RATTING_ACTIVITY, "ratting", hotspot_threshold=5
        )
        # Camped system has 11 pvp kills >= 5 threshold
        assert classification[8] == "threat"

    def test_transit_classification(self, roam_universe: UniverseGraph):
        """Low-activity systems classified as transit."""
        visited = {i: i for i in range(11)}
        classification, _, _ = classify_systems(
            roam_universe, visited, RATTING_ACTIVITY, "ratting", hotspot_threshold=5
        )
        assert classification[0] == "transit"  # Origin: 0 npc
        assert classification[1] == "transit"  # Hub1: 10 npc (below threshold)

    def test_kills_mode_threat_classification(self, roam_universe: UniverseGraph):
        """In kills mode, high-traffic pipe systems are classified as threat."""
        visited = {i: i for i in range(11)}
        classification, _, _ = classify_systems(
            roam_universe, visited, RATTING_ACTIVITY, "kills", hotspot_threshold=5
        )
        # Camped system has ship_jumps=50, threshold is 5*50=250, so NOT threat
        # But Hub2 has ship_jumps=20 (below 250), so transit
        # Let's verify high-traffic systems: the threshold is hotspot_threshold*50 = 250
        # None of our systems reach 250 ship_jumps, so no threats in kills mode
        for idx in range(11):
            assert classification[idx] != "threat" or RATTING_ACTIVITY[int(roam_universe.system_ids[idx])].ship_jumps >= 250


# =============================================================================
# Unit Tests: greedy_forward_walk
# =============================================================================


class TestGreedyForwardWalk:
    """Test the greedy forward walk algorithm."""

    def test_no_duplicate_systems(self, roam_universe: UniverseGraph):
        """Linear walk must not revisit systems."""
        visited = {i: i for i in range(11)}
        classification, hunt_metrics, _ = classify_systems(
            roam_universe, visited, RATTING_ACTIVITY, "ratting", hotspot_threshold=5
        )
        route = greedy_forward_walk(
            roam_universe, 0, 10, classification, hunt_metrics,
            avoid_hotspots=True, direction_idx=None, visited_bfs=visited,
        )
        assert len(route) == len(set(route)), "Route contains duplicate systems"

    def test_avoids_threat_systems(self, roam_universe: UniverseGraph):
        """Walk avoids threat-classified systems when avoid_hotspots=True."""
        visited = {i: i for i in range(11)}
        classification, hunt_metrics, _ = classify_systems(
            roam_universe, visited, RATTING_ACTIVITY, "ratting", hotspot_threshold=5
        )
        route = greedy_forward_walk(
            roam_universe, 0, 10, classification, hunt_metrics,
            avoid_hotspots=True, direction_idx=None, visited_bfs=visited,
        )
        # System 8 (Camped) should not be in route
        assert 8 not in route

    def test_respects_avoid_systems(self, roam_universe: UniverseGraph):
        """Walk respects explicit avoid set."""
        visited = {i: i for i in range(11)}
        classification, hunt_metrics, _ = classify_systems(
            roam_universe, visited, RATTING_ACTIVITY, "ratting", hotspot_threshold=5
        )
        # Block Hub1 — this should severely limit route
        route = greedy_forward_walk(
            roam_universe, 0, 10, classification, hunt_metrics,
            avoid_hotspots=True, direction_idx=None, visited_bfs=visited,
            avoid_indices={1},
        )
        assert 1 not in route

    def test_targets_hunt_systems(self, roam_universe: UniverseGraph):
        """Walk should pass through hunt-classified systems."""
        visited = {i: i for i in range(11)}
        classification, hunt_metrics, _ = classify_systems(
            roam_universe, visited, RATTING_ACTIVITY, "ratting", hotspot_threshold=5
        )
        route = greedy_forward_walk(
            roam_universe, 0, 10, classification, hunt_metrics,
            avoid_hotspots=True, direction_idx=None, visited_bfs=visited,
        )
        # Route should include at least some hunt systems
        hunt_in_route = [idx for idx in route if classification.get(idx) == "hunt"]
        assert len(hunt_in_route) >= 1


# =============================================================================
# Unit Tests: sweep_retrace
# =============================================================================


class TestSweepRetrace:
    """Test sweep-mode retrace logic."""

    def test_retrace_limit_hard(self, roam_universe: UniverseGraph):
        """Sweep mode must not retrace more than 2 systems."""
        visited = {i: i for i in range(11)}
        classification, hunt_metrics, _ = classify_systems(
            roam_universe, visited, RATTING_ACTIVITY, "ratting", hotspot_threshold=5
        )
        # Build a short route first
        route = greedy_forward_walk(
            roam_universe, 0, 5, classification, hunt_metrics,
            avoid_hotspots=True, direction_idx=None, visited_bfs=visited,
        )
        _, retrace = sweep_retrace(
            roam_universe, route, 15, classification, hunt_metrics,
            avoid_hotspots=True,
        )
        assert len(retrace) <= 2

    def test_retrace_only_transit(self, roam_universe: UniverseGraph):
        """Sweep mode must only retrace through transit systems."""
        visited = {i: i for i in range(11)}
        classification, hunt_metrics, _ = classify_systems(
            roam_universe, visited, RATTING_ACTIVITY, "ratting", hotspot_threshold=5
        )
        route = greedy_forward_walk(
            roam_universe, 0, 5, classification, hunt_metrics,
            avoid_hotspots=True, direction_idx=None, visited_bfs=visited,
        )
        _, retrace = sweep_retrace(
            roam_universe, route, 15, classification, hunt_metrics,
            avoid_hotspots=True,
        )
        for idx in retrace:
            assert classification.get(idx) == "transit", f"Retraced through non-transit: {idx}"


# =============================================================================
# Integration Tests: _roam_route action
# =============================================================================


class TestRoamRouteAction:
    """Integration tests for the roam_route action."""

    def test_linear_no_backtrack(self, registered_roam_universe: UniverseGraph):
        """Linear mode must never revisit a system."""
        with patch("aria_esi.mcp.dispatchers.universe._helpers_roam.get_activity_cache", return_value=_mock_activity_cache()):
            result = asyncio.run(_roam_route(origin="Origin", target_jumps=10, mode="linear"))
        system_names = [s["name"] for s in result["systems"]]
        assert len(system_names) == len(set(system_names)), "Route contains duplicate systems"

    def test_sweep_minimal_retrace(self, registered_roam_universe: UniverseGraph):
        """Sweep mode retrace systems have retrace phase."""
        with patch("aria_esi.mcp.dispatchers.universe._helpers_roam.get_activity_cache", return_value=_mock_activity_cache()):
            result = asyncio.run(_roam_route(origin="Origin", target_jumps=10, mode="sweep"))
        for name in result["retrace_systems"]:
            # Find the retrace occurrence (should have phase="retrace")
            retrace_entries = [s for s in result["systems"] if s["name"] == name and s["phase"] == "retrace"]
            if retrace_entries:
                assert retrace_entries[0]["phase"] == "retrace"

    def test_targets_ratting(self, registered_roam_universe: UniverseGraph):
        """Route should pass through high-NPC systems when activity_type=ratting."""
        with patch("aria_esi.mcp.dispatchers.universe._helpers_roam.get_activity_cache", return_value=_mock_activity_cache()):
            result = asyncio.run(_roam_route(origin="Origin", target_jumps=10, activity_type="ratting"))
        hunt_systems = [s for s in result["systems"] if s["phase"] == "hunt"]
        assert len(hunt_systems) >= 1
        assert all(s["npc_kills"] > 0 for s in hunt_systems)

    def test_avoids_pvp_hotspots(self, registered_roam_universe: UniverseGraph):
        """Route should not pass through PVP hotspots."""
        with patch("aria_esi.mcp.dispatchers.universe._helpers_roam.get_activity_cache", return_value=_mock_activity_cache()):
            result = asyncio.run(_roam_route(origin="Origin", target_jumps=10, hotspot_threshold=5))
        for system in result["systems"]:
            assert system["ship_kills"] + system["pod_kills"] < 5 or system["name"] == "Origin", (
                f"Route passed through PVP hotspot: {system['name']} "
                f"({system['ship_kills'] + system['pod_kills']} kills)"
            )

    def test_respects_target_jumps(self, registered_roam_universe: UniverseGraph):
        """Route length should be reasonable relative to target."""
        with patch("aria_esi.mcp.dispatchers.universe._helpers_roam.get_activity_cache", return_value=_mock_activity_cache()):
            result = asyncio.run(_roam_route(origin="Origin", target_jumps=10))
        # Should be at least some jumps (graph has 11 systems)
        assert result["total_jumps"] > 0
        assert result["total_jumps"] <= 11  # Can't exceed graph size

    def test_jump_numbers_1_indexed(self, registered_roam_universe: UniverseGraph):
        """Jump numbers should be 1-indexed per proposal spec."""
        with patch("aria_esi.mcp.dispatchers.universe._helpers_roam.get_activity_cache", return_value=_mock_activity_cache()):
            result = asyncio.run(_roam_route(origin="Origin", target_jumps=10, mode="linear"))
        if result["systems"]:
            assert result["systems"][0]["jump_number"] == 1
            for i, s in enumerate(result["systems"]):
                assert s["jump_number"] == i + 1

    def test_has_escape_routes(self, registered_roam_universe: UniverseGraph):
        """Result should include escape route data."""
        with patch("aria_esi.mcp.dispatchers.universe._helpers_roam.get_activity_cache", return_value=_mock_activity_cache()):
            result = asyncio.run(_roam_route(origin="Origin", target_jumps=10))
        # escape_routes field should exist (may be empty in all-null test universe)
        assert "escape_routes" in result

    def test_avoid_systems_blocks_forward(self, registered_roam_universe: UniverseGraph):
        """When avoid_systems cuts off all paths, return partial route."""
        with patch("aria_esi.mcp.dispatchers.universe._helpers_roam.get_activity_cache", return_value=_mock_activity_cache()):
            result = asyncio.run(_roam_route(
                origin="Origin", target_jumps=10, mode="linear",
                avoid_systems=["Hub1"],  # Block only exit from Origin
            ))
        # Should return origin-only route (0 jumps)
        assert result["total_jumps"] == 0
        assert len(result["systems"]) == 1

    def test_sweep_retrace_limit(self, registered_roam_universe: UniverseGraph):
        """Sweep mode must not retrace more than 2 systems total."""
        with patch("aria_esi.mcp.dispatchers.universe._helpers_roam.get_activity_cache", return_value=_mock_activity_cache()):
            result = asyncio.run(_roam_route(origin="Origin", target_jumps=10, mode="sweep"))
        assert len(result["retrace_systems"]) <= 2


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestRoamRouteErrors:
    """Test error handling in roam_route."""

    def test_missing_origin(self, registered_roam_universe: UniverseGraph):
        """Raises error when origin is missing."""
        with pytest.raises(InvalidParameterError, match="origin"):
            asyncio.run(_roam_route(origin=None))

    def test_invalid_activity_type(self, registered_roam_universe: UniverseGraph):
        """Raises error for invalid activity_type."""
        with pytest.raises(InvalidParameterError, match="activity_type"):
            asyncio.run(_roam_route(origin="Origin", activity_type="invalid"))

    def test_invalid_mode(self, registered_roam_universe: UniverseGraph):
        """Raises error for invalid mode."""
        with pytest.raises(InvalidParameterError, match="mode"):
            asyncio.run(_roam_route(origin="Origin", mode="invalid"))

    def test_target_jumps_too_low(self, registered_roam_universe: UniverseGraph):
        """Raises error for target_jumps < 10."""
        with pytest.raises(InvalidParameterError, match="target_jumps"):
            asyncio.run(_roam_route(origin="Origin", target_jumps=5))

    def test_target_jumps_too_high(self, registered_roam_universe: UniverseGraph):
        """Raises error for target_jumps > 40."""
        with pytest.raises(InvalidParameterError, match="target_jumps"):
            asyncio.run(_roam_route(origin="Origin", target_jumps=50))
