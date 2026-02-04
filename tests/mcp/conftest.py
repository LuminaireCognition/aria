"""
Shared Test Fixtures for MCP Universe Server Tests.

Provides reusable fixtures and factory functions to reduce test boilerplate.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import igraph as ig
import numpy as np
import pytest

from aria_esi.mcp.tools import register_tools
from aria_esi.universe import UniverseGraph

# =============================================================================
# Mock Universe Factory
# =============================================================================


def create_mock_universe(
    systems: list[dict[str, Any]],
    edges: list[tuple[int, int]],
    border_indices: list[int] | None = None,
) -> UniverseGraph:
    """
    Factory function to create a mock UniverseGraph for testing.

    Args:
        systems: List of system dicts with keys: name, id, sec, const, region
        edges: List of (source_idx, target_idx) tuples for stargates
        border_indices: Optional list of vertex indices that are border systems

    Returns:
        Configured UniverseGraph instance

    Example:
        systems = [
            {"name": "Jita", "id": 30000142, "sec": 0.95, "const": 20000020, "region": 10000002},
            {"name": "Perimeter", "id": 30000144, "sec": 0.90, "const": 20000020, "region": 10000002},
        ]
        edges = [(0, 1)]  # Jita -- Perimeter
        universe = create_mock_universe(systems, edges)
    """
    n = len(systems)
    g = ig.Graph(n=n, edges=edges, directed=False)

    name_to_idx = {s["name"]: i for i, s in enumerate(systems)}
    idx_to_name = {i: s["name"] for i, s in enumerate(systems)}
    name_to_id = {s["name"]: s["id"] for s in systems}
    id_to_idx = {s["id"]: i for i, s in enumerate(systems)}
    name_lookup = {s["name"].lower(): s["name"] for s in systems}

    security = np.array([s["sec"] for s in systems], dtype=np.float32)
    system_ids = np.array([s["id"] for s in systems], dtype=np.int32)
    constellation_ids = np.array([s["const"] for s in systems], dtype=np.int32)
    region_ids = np.array([s["region"] for s in systems], dtype=np.int32)

    highsec = frozenset(i for i in range(n) if security[i] >= 0.45)
    lowsec = frozenset(i for i in range(n) if 0.0 < security[i] < 0.45)
    nullsec = frozenset(i for i in range(n) if security[i] <= 0.0)

    if border_indices is None:
        # Auto-detect borders: high-sec systems adjacent to low-sec
        border_indices = []
        for i in range(n):
            if security[i] >= 0.45:
                for neighbor in g.neighbors(i):
                    if security[neighbor] < 0.45:
                        border_indices.append(i)
                        break
    border = frozenset(border_indices)

    # Build region_systems mapping
    region_systems: dict[int, list[int]] = {}
    for i, s in enumerate(systems):
        region_id = s["region"]
        if region_id not in region_systems:
            region_systems[region_id] = []
        region_systems[region_id].append(i)

    # Build constellation and region name lookups
    constellation_names: dict[int, str] = {}
    region_names: dict[int, str] = {}
    for s in systems:
        # Use default names if not provided
        const_id = s["const"]
        region_id = s["region"]
        if const_id not in constellation_names:
            constellation_names[const_id] = s.get("const_name", f"Constellation-{const_id}")
        if region_id not in region_names:
            region_names[region_id] = s.get("region_name", f"Region-{region_id}")

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
        system_count=n,
        stargate_count=len(edges),
    )


# =============================================================================
# Standard Test Universes
# =============================================================================

# Standard systems used across multiple tests
STANDARD_SYSTEMS = [
    {"name": "Jita", "id": 30000142, "sec": 0.95, "const": 20000020, "region": 10000002,
     "const_name": "Kimotoro", "region_name": "The Forge"},
    {"name": "Perimeter", "id": 30000144, "sec": 0.90, "const": 20000020, "region": 10000002,
     "const_name": "Kimotoro", "region_name": "The Forge"},
    {"name": "Maurasi", "id": 30000140, "sec": 0.65, "const": 20000020, "region": 10000002,
     "const_name": "Kimotoro", "region_name": "The Forge"},
    {"name": "Urlen", "id": 30000138, "sec": 0.85, "const": 20000020, "region": 10000002,
     "const_name": "Kimotoro", "region_name": "The Forge"},
    {"name": "Sivala", "id": 30000160, "sec": 0.35, "const": 20000021, "region": 10000002,
     "const_name": "Otanuomi", "region_name": "The Forge"},
    {"name": "Ala", "id": 30000161, "sec": -0.2, "const": 20000022, "region": 10000003,
     "const_name": "Somewhere", "region_name": "Outer Region"},
]

STANDARD_EDGES = [
    (0, 1),  # Jita -- Perimeter
    (0, 2),  # Jita -- Maurasi
    (1, 3),  # Perimeter -- Urlen
    (2, 3),  # Maurasi -- Urlen
    (2, 4),  # Maurasi -- Sivala
    (4, 5),  # Sivala -- Ala
]


# =============================================================================
# Shared Fixtures
# =============================================================================


@pytest.fixture
def standard_universe() -> UniverseGraph:
    """
    Standard 6-system universe for basic tests.

    Graph structure:
        Jita (high-sec 0.95) -- Perimeter (high-sec 0.90)
             |                        |
        *Maurasi (high-sec 0.65) -- Urlen (high-sec 0.85)
             |
        Sivala (low-sec 0.35)
             |
        Ala (null-sec -0.2)

    Border systems: Maurasi (adjacent to Sivala)
    """
    return create_mock_universe(STANDARD_SYSTEMS, STANDARD_EDGES)


@pytest.fixture
def extended_universe() -> UniverseGraph:
    """
    Extended 11-system universe for loop and search tests.

    Includes additional systems for diversity testing and multi-region scenarios.
    """
    systems = [
        *STANDARD_SYSTEMS,
        {"name": "Haatomo", "id": 30002693, "sec": 0.70, "const": 20000023, "region": 10000002,
         "const_name": "Uosusuokko", "region_name": "The Forge"},
        {"name": "Uedama", "id": 30002691, "sec": 0.50, "const": 20000023, "region": 10000043,
         "const_name": "Uosusuokko", "region_name": "Domain"},
        {"name": "Niarja", "id": 30002692, "sec": 0.30, "const": 20000023, "region": 10000043,
         "const_name": "Uosusuokko", "region_name": "Domain"},
        {"name": "Aufay", "id": 30002694, "sec": 0.55, "const": 20000024, "region": 10000044,
         "const_name": "Aufayland", "region_name": "Sinq Laison"},
        {"name": "Balle", "id": 30002695, "sec": 0.25, "const": 20000024, "region": 10000044,
         "const_name": "Aufayland", "region_name": "Sinq Laison"},
    ]

    edges = [
        *STANDARD_EDGES,
        (3, 6),  # Urlen -- Haatomo
        (6, 7),  # Haatomo -- Uedama
        (7, 8),  # Uedama -- Niarja
        (6, 9),  # Haatomo -- Aufay
        (9, 10), # Aufay -- Balle
        (3, 7),  # Urlen -- Uedama (shortcut)
    ]

    return create_mock_universe(systems, edges)


@pytest.fixture
def registered_standard_universe(standard_universe: UniverseGraph) -> UniverseGraph:
    """Standard universe with MCP tools registered."""
    mock_server = MagicMock()
    register_tools(mock_server, standard_universe)
    return standard_universe


@pytest.fixture
def registered_extended_universe(extended_universe: UniverseGraph) -> UniverseGraph:
    """Extended universe with MCP tools registered."""
    mock_server = MagicMock()
    register_tools(mock_server, extended_universe)
    return extended_universe


# =============================================================================
# Test Helpers
# =============================================================================


def capture_tool_function(universe: UniverseGraph, register_func: callable) -> callable:
    """
    Helper to capture the registered tool function for direct testing.

    Args:
        universe: UniverseGraph to register with
        register_func: Tool registration function (e.g., register_route_tools)

    Returns:
        The captured async tool function

    Example:
        from aria_esi.mcp.tools_route import register_route_tools
        tool = capture_tool_function(universe, register_route_tools)
        result = await tool(origin="Jita", destination="Amarr")
    """
    captured_tool = None

    def mock_tool():
        def decorator(func):
            nonlocal captured_tool
            captured_tool = func
            return func
        return decorator

    mock_server = MagicMock()
    mock_server.tool = mock_tool
    register_func(mock_server, universe)
    return captured_tool


# =============================================================================
# Edge Case Fixtures
# =============================================================================


@pytest.fixture
def minimal_universe() -> UniverseGraph:
    """Single-system universe for edge case testing."""
    systems = [
        {"name": "Solo", "id": 30000001, "sec": 0.5, "const": 20000001, "region": 10000001,
         "const_name": "Lonely", "region_name": "Empty Space"},
    ]
    return create_mock_universe(systems, [])


@pytest.fixture
def disconnected_universe() -> UniverseGraph:
    """Universe with two disconnected components."""
    systems = [
        {"name": "Island1", "id": 30000001, "sec": 0.9, "const": 20000001, "region": 10000001,
         "const_name": "North", "region_name": "North Region"},
        {"name": "Island2", "id": 30000002, "sec": 0.9, "const": 20000001, "region": 10000001,
         "const_name": "North", "region_name": "North Region"},
        {"name": "Island3", "id": 30000003, "sec": 0.9, "const": 20000002, "region": 10000002,
         "const_name": "South", "region_name": "South Region"},
        {"name": "Island4", "id": 30000004, "sec": 0.9, "const": 20000002, "region": 10000002,
         "const_name": "South", "region_name": "South Region"},
    ]
    edges = [
        (0, 1),  # North cluster
        (2, 3),  # South cluster (disconnected from North)
    ]
    return create_mock_universe(systems, edges)
