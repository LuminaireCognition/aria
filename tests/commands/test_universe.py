"""
Tests for CLI Universe Commands.

Tests the borders, loop, system, and graph management commands.
"""

from __future__ import annotations

import argparse
from unittest.mock import MagicMock, patch

import numpy as np


def _make_mock_universe(
    systems=None,
    border_indices=None,
    neighbors_map=None,
):
    """Create a mock UniverseGraph with configurable data.

    Args:
        systems: List of (idx, name, security, region_id, constellation_id, system_id) tuples
        border_indices: Set of vertex indices that are border systems
        neighbors_map: Dict mapping idx -> list of neighbor indices
    """
    if systems is None:
        systems = [
            (0, "Jita", 0.9459, 10000002, 20000020, 30000142),
            (1, "Perimeter", 0.9072, 10000002, 20000020, 30000144),
            (2, "Sivala", 0.5000, 10000002, 20000020, 30000138),
            (3, "Aufay", 0.3500, 10000002, 20000021, 30000137),
        ]
    if border_indices is None:
        border_indices = frozenset({2})  # Sivala
    if neighbors_map is None:
        neighbors_map = {
            0: [1],     # Jita -> Perimeter
            1: [0, 2],  # Perimeter -> Jita, Sivala
            2: [1, 3],  # Sivala -> Perimeter, Aufay
            3: [2],     # Aufay -> Sivala
        }

    universe = MagicMock()
    universe.border_systems = border_indices

    # Build arrays
    n = len(systems)
    security = np.zeros(n, dtype=np.float32)
    system_ids = np.zeros(n, dtype=np.int32)
    region_ids = np.zeros(n, dtype=np.int32)
    constellation_ids = np.zeros(n, dtype=np.int32)
    idx_to_name = {}
    name_lookup = {}
    region_names = {}
    constellation_names = {}

    for idx, name, sec, rid, cid, sid in systems:
        security[idx] = sec
        system_ids[idx] = sid
        region_ids[idx] = rid
        constellation_ids[idx] = cid
        idx_to_name[idx] = name
        name_lookup[name.lower()] = name

    universe.security = security
    universe.system_ids = system_ids
    universe.region_ids = region_ids
    universe.constellation_ids = constellation_ids
    universe.idx_to_name = idx_to_name
    universe.name_lookup = name_lookup

    region_names = {10000002: "The Forge"}
    constellation_names = {20000020: "Kimotoro", 20000021: "Okkelen"}
    universe.region_names = region_names
    universe.constellation_names = constellation_names
    universe.region_name_lookup = {"the forge": 10000002}

    def resolve_name(name):
        canonical = name_lookup.get(name.lower())
        if canonical:
            for idx, n in idx_to_name.items():
                if n == canonical:
                    return idx
        return None

    def resolve_region(name):
        return universe.region_name_lookup.get(name.lower())

    def get_region_name(idx):
        rid = int(region_ids[idx])
        return region_names.get(rid, "Unknown")

    def get_constellation_name(idx):
        cid = int(constellation_ids[idx])
        return constellation_names.get(cid, "Unknown")

    def neighbors_with_security(idx):
        return [(n, float(security[n])) for n in neighbors_map.get(idx, [])]

    def get_adjacent_lowsec(idx):
        if idx not in border_indices:
            return []
        return [idx_to_name[n] for n in neighbors_map.get(idx, []) if security[n] < 0.45]

    # Mock graph for shortest_paths
    def shortest_paths(source, target):
        # Simple BFS distance
        from collections import deque
        dists = {}
        queue = deque([(source, 0)])
        dists[source] = 0
        while queue:
            current, d = queue.popleft()
            for nb in neighbors_map.get(current, []):
                if nb not in dists:
                    dists[nb] = d + 1
                    queue.append((nb, d + 1))
        return [[dists.get(t, float("inf")) for t in target]]

    graph_mock = MagicMock()
    graph_mock.neighbors = lambda idx: neighbors_map.get(idx, [])
    graph_mock.shortest_paths = shortest_paths
    universe.graph = graph_mock

    universe.resolve_name = resolve_name
    universe.resolve_region = resolve_region
    universe.get_region_name = get_region_name
    universe.get_constellation_name = get_constellation_name
    universe.neighbors_with_security = neighbors_with_security
    universe.get_adjacent_lowsec = get_adjacent_lowsec

    return universe


# =============================================================================
# Borders Command Tests
# =============================================================================


class TestCmdBorders:
    """Test cmd_borders function."""

    def test_borders_missing_argument(self):
        """Returns error when neither region nor system specified."""
        from aria_esi.commands.universe import cmd_borders

        args = argparse.Namespace(region=None, system=None, limit=10)
        universe = _make_mock_universe()

        with patch("aria_esi.commands.universe._load_graph", return_value=(universe, None)):
            result = cmd_borders(args)

        assert result["error"] == "missing_argument"
        assert "region" in result["message"] or "system" in result["message"]

    def test_borders_graph_not_available(self):
        """Returns error when graph is not available."""
        from aria_esi.commands.universe import cmd_borders

        args = argparse.Namespace(region="The Forge", system=None, limit=10)
        err = {"error": "graph_not_found", "message": "Universe graph not available", "hint": "Run 'aria-esi graph-build'"}

        with patch("aria_esi.commands.universe._load_graph", return_value=(None, err)):
            result = cmd_borders(args)

        assert result["error"] == "graph_not_found"
        assert "hint" in result

    def test_borders_by_region_success(self):
        """Borders by region returns border systems."""
        from aria_esi.commands.universe import cmd_borders

        args = argparse.Namespace(region="The Forge", system=None, limit=10)
        universe = _make_mock_universe()

        with patch("aria_esi.commands.universe._load_graph", return_value=(universe, None)):
            result = cmd_borders(args)

        assert "error" not in result
        assert result["search_type"] == "region"
        assert result["region"] == "The Forge"
        assert result["count"] == 1
        assert result["border_systems"][0]["name"] == "Sivala"

    def test_borders_by_region_no_results(self):
        """Returns error when no border systems found in region."""
        from aria_esi.commands.universe import cmd_borders

        args = argparse.Namespace(region="Empty Region", system=None, limit=10)
        universe = _make_mock_universe()

        with patch("aria_esi.commands.universe._load_graph", return_value=(universe, None)):
            result = cmd_borders(args)

        assert result["error"] == "no_results"

    def test_borders_by_system_success(self):
        """Borders by system proximity returns nearest borders."""
        from aria_esi.commands.universe import cmd_borders

        args = argparse.Namespace(region=None, system="Jita", limit=5)
        universe = _make_mock_universe()

        with patch("aria_esi.commands.universe._load_graph", return_value=(universe, None)):
            result = cmd_borders(args)

        assert "error" not in result
        assert result["search_type"] == "proximity"
        assert result["origin"]["name"] == "Jita"
        assert len(result["border_systems"]) == 1
        assert result["border_systems"][0]["name"] == "Sivala"
        assert result["border_systems"][0]["approx_jumps"] == 2

    def test_borders_by_system_not_found(self):
        """Returns error when system not found."""
        from aria_esi.commands.universe import cmd_borders

        args = argparse.Namespace(region=None, system="NonexistentSystem", limit=5)
        universe = _make_mock_universe()

        with patch("aria_esi.commands.universe._load_graph", return_value=(universe, None)):
            result = cmd_borders(args)

        assert result["error"] == "system_not_found"


# =============================================================================
# Loop Command Tests
# =============================================================================


class TestCmdLoop:
    """Test cmd_loop function."""

    def test_loop_invalid_target_jumps_too_low(self):
        """Returns error when target_jumps is below minimum."""
        from aria_esi.commands.universe import cmd_loop

        args = argparse.Namespace(
            origin="Jita",
            target_jumps=5,  # Below minimum of 10
            min_borders=3,
            max_borders=6,
            security_filter="highsec",
            avoid=None,
        )

        result = cmd_loop(args)

        assert result["error"] == "invalid_parameter"
        assert "target_jumps" in result["message"]

    def test_loop_invalid_target_jumps_too_high(self):
        """Returns error when target_jumps is above maximum."""
        from aria_esi.commands.universe import cmd_loop

        args = argparse.Namespace(
            origin="Jita",
            target_jumps=200,  # Above maximum of 100
            min_borders=3,
            max_borders=6,
            security_filter="highsec",
            avoid=None,
        )

        result = cmd_loop(args)

        assert result["error"] == "invalid_parameter"
        assert "target_jumps" in result["message"]

    def test_loop_invalid_min_borders_too_low(self):
        """Returns error when min_borders is below minimum."""
        from aria_esi.commands.universe import cmd_loop

        args = argparse.Namespace(
            origin="Jita",
            target_jumps=20,
            min_borders=1,  # Below minimum of 2
            max_borders=6,
            security_filter="highsec",
            avoid=None,
        )

        result = cmd_loop(args)

        assert result["error"] == "invalid_parameter"
        assert "min_borders" in result["message"]

    def test_loop_invalid_max_borders_below_min(self):
        """Returns error when max_borders is below min_borders."""
        from aria_esi.commands.universe import cmd_loop

        args = argparse.Namespace(
            origin="Jita",
            target_jumps=20,
            min_borders=5,
            max_borders=3,  # Below min_borders
            security_filter="highsec",
            avoid=None,
        )

        result = cmd_loop(args)

        assert result["error"] == "invalid_parameter"
        assert "max_borders" in result["message"]

    def test_loop_invalid_security_filter(self):
        """Returns error when security_filter is invalid."""
        from aria_esi.commands.universe import cmd_loop

        args = argparse.Namespace(
            origin="Jita",
            target_jumps=20,
            min_borders=3,
            max_borders=6,
            security_filter="invalid_filter",
            avoid=None,
        )

        result = cmd_loop(args)

        assert result["error"] == "invalid_parameter"
        assert "security_filter" in result["message"]


# =============================================================================
# System Info Command Tests
# =============================================================================


class TestCmdSystemInfo:
    """Test cmd_system_info function."""

    def test_system_info_graph_not_available(self):
        """Returns error when graph is not available."""
        from aria_esi.commands.universe import cmd_system_info

        args = argparse.Namespace(system="Jita")
        err = {"error": "graph_not_found", "message": "Universe graph not available", "hint": "Run 'aria-esi graph-build'"}

        with patch("aria_esi.commands.universe._load_graph", return_value=(None, err)):
            result = cmd_system_info(args)

        assert result["error"] == "graph_not_found"

    def test_system_info_system_not_found(self):
        """Returns error when system not found."""
        from aria_esi.commands.universe import cmd_system_info

        args = argparse.Namespace(system="NonexistentSystem")
        universe = _make_mock_universe()

        with patch("aria_esi.commands.universe._load_graph", return_value=(universe, None)):
            result = cmd_system_info(args)

        assert result["error"] == "system_not_found"

    def test_system_info_success(self):
        """Returns system info when found."""
        from aria_esi.commands.universe import cmd_system_info

        args = argparse.Namespace(system="Jita")
        universe = _make_mock_universe()

        with patch("aria_esi.commands.universe._load_graph", return_value=(universe, None)):
            result = cmd_system_info(args)

        assert "error" not in result
        assert result["system"]["name"] == "Jita"
        assert result["system"]["region"] == "The Forge"
        assert result["system"]["constellation"] == "Kimotoro"
        assert len(result["neighbors"]) == 1
        assert result["neighbors"][0]["name"] == "Perimeter"
