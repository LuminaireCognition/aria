"""
Tests for CLI Navigation Commands.

Tests the route command which uses local UniverseGraph for pathfinding.
Ensures CLI/MCP parity for route calculation and warnings.
"""

from __future__ import annotations

import argparse
from unittest.mock import patch

import igraph as ig
import numpy as np
import pytest

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


# =============================================================================
# Route Command Tests
# =============================================================================


class TestCmdRoute:
    """Test cmd_route function."""

    def test_basic_route_highsec(self, mock_universe: UniverseGraph):
        """Basic route between high-sec systems works."""
        from aria_esi.commands.navigation import cmd_route

        args = argparse.Namespace(
            origin="Jita",
            destination="Urlen",
            route_flag="shortest",
            avoid=None,
        )

        with patch("aria_esi.commands.navigation.load_universe_graph", return_value=mock_universe):
            result = cmd_route(args)

        assert "error" not in result
        assert result["total_jumps"] == 2
        assert result["origin"]["name"] == "Jita"
        assert result["destination"]["name"] == "Urlen"
        assert result["security_summary"]["high_sec"] == 3
        assert result["security_summary"]["low_sec"] == 0
        assert result["security_summary"]["null_sec"] == 0
        assert result["security_summary"]["threat_level"] == "MINIMAL"

    def test_route_through_lowsec(self, mock_universe: UniverseGraph):
        """Route through low-sec generates correct security summary."""
        from aria_esi.commands.navigation import cmd_route

        args = argparse.Namespace(
            origin="Jita",
            destination="Sivala",
            route_flag="shortest",
            avoid=None,
        )

        with patch("aria_esi.commands.navigation.load_universe_graph", return_value=mock_universe):
            result = cmd_route(args)

        assert "error" not in result
        assert result["security_summary"]["low_sec"] == 1
        assert result["security_summary"]["threat_level"] == "HIGH"

    def test_route_through_nullsec(self, mock_universe: UniverseGraph):
        """Route through null-sec generates correct security summary."""
        from aria_esi.commands.navigation import cmd_route

        args = argparse.Namespace(
            origin="Jita",
            destination="Ala",
            route_flag="shortest",
            avoid=None,
        )

        with patch("aria_esi.commands.navigation.load_universe_graph", return_value=mock_universe):
            result = cmd_route(args)

        assert "error" not in result
        assert result["security_summary"]["null_sec"] == 1
        assert result["security_summary"]["threat_level"] == "CRITICAL"
        assert result["security_summary"]["lowest_security"] == -0.2
        assert result["security_summary"]["lowest_security_system"] == "Ala"

    def test_route_secure_mode(self, mock_universe: UniverseGraph):
        """Secure mode works correctly."""
        from aria_esi.commands.navigation import cmd_route

        args = argparse.Namespace(
            origin="Jita",
            destination="Urlen",
            route_flag="secure",
            avoid=None,
        )

        with patch("aria_esi.commands.navigation.load_universe_graph", return_value=mock_universe):
            result = cmd_route(args)

        assert "error" not in result
        assert result["route_mode"] == "secure"
        assert result["route_mode_display"] == "Secure (high-sec priority)"

    def test_route_insecure_mode(self, mock_universe: UniverseGraph):
        """Insecure mode works correctly."""
        from aria_esi.commands.navigation import cmd_route

        args = argparse.Namespace(
            origin="Jita",
            destination="Ala",
            route_flag="insecure",
            avoid=None,
        )

        with patch("aria_esi.commands.navigation.load_universe_graph", return_value=mock_universe):
            result = cmd_route(args)

        assert "error" not in result
        assert result["route_mode"] == "insecure"
        assert result["route_mode_display"] == "Risky (low-sec/null preferred)"

    def test_route_with_avoid(self, mock_universe: UniverseGraph):
        """Route with --avoid parameter works correctly."""
        from aria_esi.commands.navigation import cmd_route

        # Avoid Perimeter, so must go through Maurasi
        args = argparse.Namespace(
            origin="Jita",
            destination="Urlen",
            route_flag="shortest",
            avoid=["Perimeter"],
        )

        with patch("aria_esi.commands.navigation.load_universe_graph", return_value=mock_universe):
            result = cmd_route(args)

        assert "error" not in result
        system_names = [s["name"] for s in result["systems"]]
        assert "Perimeter" not in system_names
        assert "Maurasi" in system_names
        assert result["avoided_systems"] == ["Perimeter"]

    def test_route_with_unresolved_avoid(self, mock_universe: UniverseGraph):
        """Route with unresolved avoid system generates warning."""
        from aria_esi.commands.navigation import cmd_route

        args = argparse.Namespace(
            origin="Jita",
            destination="Urlen",
            route_flag="shortest",
            avoid=["NonexistentSystem"],
        )

        with patch("aria_esi.commands.navigation.load_universe_graph", return_value=mock_universe):
            result = cmd_route(args)

        assert "error" not in result
        assert "warnings" in result
        assert any("Unknown systems" in w or "NonexistentSystem" in w for w in result["warnings"])

    def test_route_system_not_found(self, mock_universe: UniverseGraph):
        """Unknown origin/destination returns error."""
        from aria_esi.commands.navigation import cmd_route

        args = argparse.Namespace(
            origin="UnknownSystem",
            destination="Urlen",
            route_flag="shortest",
            avoid=None,
        )

        with patch("aria_esi.commands.navigation.load_universe_graph", return_value=mock_universe):
            result = cmd_route(args)

        assert result["error"] == "system_not_found"
        assert "UnknownSystem" in result["message"]

    def test_route_same_system(self, mock_universe: UniverseGraph):
        """Same origin and destination returns error."""
        from aria_esi.commands.navigation import cmd_route

        args = argparse.Namespace(
            origin="Jita",
            destination="Jita",
            route_flag="shortest",
            avoid=None,
        )

        with patch("aria_esi.commands.navigation.load_universe_graph", return_value=mock_universe):
            result = cmd_route(args)

        assert result["error"] == "same_system"


class TestRouteWarnings:
    """Test route warning generation (MCP parity)."""

    def test_lowsec_entry_warning(self, mock_universe: UniverseGraph):
        """Warning when entering low/null-sec."""
        from aria_esi.commands.navigation import cmd_route

        args = argparse.Namespace(
            origin="Jita",
            destination="Ala",
            route_flag="shortest",
            avoid=None,
        )

        with patch("aria_esi.commands.navigation.load_universe_graph", return_value=mock_universe):
            result = cmd_route(args)

        assert "warnings" in result
        assert any("low/null-sec" in w for w in result["warnings"])

    def test_pipe_system_warning(self, mock_universe: UniverseGraph):
        """Warning for pipe systems in low-sec."""
        from aria_esi.commands.navigation import cmd_route

        # Sivala has only 2 neighbors and is low-sec
        args = argparse.Namespace(
            origin="Jita",
            destination="Ala",
            route_flag="shortest",
            avoid=None,
        )

        with patch("aria_esi.commands.navigation.load_universe_graph", return_value=mock_universe):
            result = cmd_route(args)

        assert "warnings" in result
        pipe_warnings = [w for w in result["warnings"] if "Pipe system" in w]
        assert len(pipe_warnings) == 1
        assert "Sivala" in pipe_warnings[0]

    def test_no_highsec_route_warning(self, mock_universe: UniverseGraph):
        """Warning when safe mode still routes through low-sec."""
        from aria_esi.commands.navigation import cmd_route

        # Route to Ala must go through low-sec even in safe mode
        args = argparse.Namespace(
            origin="Jita",
            destination="Ala",
            route_flag="secure",
            avoid=None,
        )

        with patch("aria_esi.commands.navigation.load_universe_graph", return_value=mock_universe):
            result = cmd_route(args)

        assert "warnings" in result
        assert any("No fully high-sec route" in w for w in result["warnings"])

    def test_no_warnings_highsec_only(self, mock_universe: UniverseGraph):
        """No warnings for high-sec only routes."""
        from aria_esi.commands.navigation import cmd_route

        args = argparse.Namespace(
            origin="Jita",
            destination="Urlen",
            route_flag="shortest",
            avoid=None,
        )

        with patch("aria_esi.commands.navigation.load_universe_graph", return_value=mock_universe):
            result = cmd_route(args)

        # No route-based warnings (might have avoid warnings if any)
        if "warnings" in result:
            # Should not have security-related warnings
            assert not any("low/null-sec" in w for w in result["warnings"])
            assert not any("Pipe system" in w for w in result["warnings"])


class TestSecurityClassification:
    """Test security classification matches MCP (null-sec threshold = 0.0)."""

    def test_nullsec_boundary(self, mock_universe: UniverseGraph):
        """Systems at 0.0 are classified as null-sec."""
        from aria_esi.commands.navigation import cmd_route

        # Ala has -0.2 security, should be null-sec
        args = argparse.Namespace(
            origin="Jita",
            destination="Ala",
            route_flag="shortest",
            avoid=None,
        )

        with patch("aria_esi.commands.navigation.load_universe_graph", return_value=mock_universe):
            result = cmd_route(args)

        # Verify null-sec is counted correctly
        assert result["security_summary"]["null_sec"] == 1
        # Sivala (0.35) is low-sec, not null-sec
        assert result["security_summary"]["low_sec"] == 1

    def test_lowsec_boundary(self, mock_universe: UniverseGraph):
        """Systems above 0.0 but below 0.45 are low-sec."""
        from aria_esi.commands.navigation import cmd_route

        # Route to Sivala (0.35) - should be low-sec
        args = argparse.Namespace(
            origin="Jita",
            destination="Sivala",
            route_flag="shortest",
            avoid=None,
        )

        with patch("aria_esi.commands.navigation.load_universe_graph", return_value=mock_universe):
            result = cmd_route(args)

        # Jita (0.95) + Maurasi (0.65) = 2 high-sec
        # Sivala (0.35) = 1 low-sec
        assert result["security_summary"]["high_sec"] == 2
        assert result["security_summary"]["low_sec"] == 1
        assert result["security_summary"]["null_sec"] == 0
