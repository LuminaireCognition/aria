# STP-005: Route Tool (universe_route)

**Status:** Draft
**Priority:** P1 - Core Feature
**Depends On:** STP-001, STP-002, STP-004
**Blocks:** None

## Objective

Implement the `universe_route` MCP tool for calculating optimal routes between EVE Online systems with support for shortest, safe, and unsafe routing modes.

## Scope

### In Scope
- `universe_route` tool registration
- Three routing modes: shortest, safe, unsafe
- Edge weight calculation for weighted pathfinding
- Full RouteResult construction with security analysis
- Warning generation for dangerous routes

### Out of Scope
- Jump bridge support (Phase 2)
- Wormhole connections (Phase 2)
- Route caching (optimization)

## File Location

```
aria_esi/mcp/tools_route.py
```

## Tool Specification

| Property | Value |
|----------|-------|
| Tool Name | `universe_route` |
| Latency Target | <2ms |
| Parameters | origin (str), destination (str), mode (str) |

## Implementation

### Tool Registration

```python
# aria_esi/mcp/tools_route.py

from mcp.server import Server
from ..universe.graph import UniverseGraph
from .models import RouteResult, SystemInfo, SecuritySummary, NeighborInfo
from .errors import SystemNotFoundError, RouteNotFoundError, InvalidParameterError
from .tools import resolve_system_name, get_universe

VALID_MODES = {"shortest", "safe", "unsafe"}


def register_route_tools(server: Server, universe: UniverseGraph) -> None:
    """Register route-related MCP tools."""

    @server.tool()
    async def universe_route(
        origin: str,
        destination: str,
        mode: str = "shortest"
    ) -> dict:
        """
        Calculate optimal route between two systems.

        Args:
            origin: Starting system name (case-insensitive)
            destination: Target system name (case-insensitive)
            mode: Routing preference
                - "shortest": Minimum jumps (default)
                - "safe": Avoid low/null-sec where possible
                - "unsafe": Prefer low/null-sec (for hunting)

        Returns:
            RouteResult with full system details and security analysis
        """
        # Validate mode
        if mode not in VALID_MODES:
            raise InvalidParameterError(
                "mode", mode,
                f"Must be one of: {', '.join(VALID_MODES)}"
            )

        # Resolve system names
        origin_idx = resolve_system_name(origin)
        dest_idx = resolve_system_name(destination)

        # Calculate route
        path = _calculate_route(universe, origin_idx, dest_idx, mode)

        if not path:
            raise RouteNotFoundError(origin, destination)

        # Build result
        return _build_route_result(
            universe, path, origin, destination, mode
        ).model_dump()
```

### Routing Algorithms

```python
def _calculate_route(
    universe: UniverseGraph,
    origin_idx: int,
    dest_idx: int,
    mode: str
) -> list[int]:
    """
    Calculate route using appropriate algorithm for mode.

    Returns:
        List of vertex indices from origin to destination.
    """
    g = universe.graph

    if mode == "shortest":
        # Unweighted BFS - O(V + E)
        paths = g.get_shortest_paths(origin_idx, dest_idx)
        return paths[0] if paths and paths[0] else []

    elif mode == "safe":
        weights = _compute_safe_weights(universe)
        paths = g.get_shortest_paths(origin_idx, dest_idx, weights=weights)
        return paths[0] if paths and paths[0] else []

    elif mode == "unsafe":
        weights = _compute_unsafe_weights(universe)
        paths = g.get_shortest_paths(origin_idx, dest_idx, weights=weights)
        return paths[0] if paths and paths[0] else []

    return []


def _compute_safe_weights(universe: UniverseGraph) -> list[float]:
    """
    Compute edge weights that prefer high-sec.

    Weight scheme:
    - High-sec → high-sec: 1
    - High-sec → low-sec: 50 (strong avoidance)
    - Low-sec → low-sec: 10
    - Any → null-sec: 100
    """
    g = universe.graph
    security = universe.security
    weights = []

    for edge in g.es:
        src_sec = security[edge.source]
        dst_sec = security[edge.target]

        if dst_sec >= 0.45:
            # Destination is high-sec
            weights.append(1.0)
        elif dst_sec > 0.0:
            # Destination is low-sec
            if src_sec >= 0.45:
                weights.append(50.0)  # Entering low-sec penalty
            else:
                weights.append(10.0)  # Staying in low-sec
        else:
            # Destination is null-sec
            weights.append(100.0)

    return weights


def _compute_unsafe_weights(universe: UniverseGraph) -> list[float]:
    """
    Compute edge weights that prefer dangerous space.

    Weight scheme:
    - Any → null-sec: 1 (preferred)
    - Any → low-sec: 2
    - Any → high-sec: 10 (avoided)
    """
    g = universe.graph
    security = universe.security
    weights = []

    for edge in g.es:
        dst_sec = security[edge.target]

        if dst_sec <= 0.0:
            weights.append(1.0)   # Prefer null-sec
        elif dst_sec < 0.45:
            weights.append(2.0)   # Low-sec acceptable
        else:
            weights.append(10.0)  # Avoid high-sec

    return weights
```

### Result Construction

```python
def _build_route_result(
    universe: UniverseGraph,
    path: list[int],
    origin: str,
    destination: str,
    mode: str
) -> RouteResult:
    """Build complete RouteResult from path."""
    systems = [_build_system_info(universe, idx) for idx in path]
    security_summary = _compute_security_summary(universe, path)
    warnings = _generate_warnings(universe, path, mode)

    return RouteResult(
        origin=origin,
        destination=destination,
        mode=mode,
        jumps=len(path) - 1,
        systems=systems,
        security_summary=security_summary,
        warnings=warnings
    )


def _build_system_info(universe: UniverseGraph, idx: int) -> SystemInfo:
    """Build SystemInfo for a vertex."""
    neighbors = [
        NeighborInfo(
            name=universe.idx_to_name[n],
            security=float(universe.security[n]),
            security_class=universe.security_class(n)
        )
        for n in universe.graph.neighbors(idx)
    ]

    return SystemInfo(
        name=universe.idx_to_name[idx],
        system_id=int(universe.system_ids[idx]),
        security=float(universe.security[idx]),
        security_class=universe.security_class(idx),
        constellation=universe.get_constellation_name(idx),
        constellation_id=int(universe.constellation_ids[idx]),
        region=universe.get_region_name(idx),
        region_id=int(universe.region_ids[idx]),
        neighbors=neighbors,
        is_border=idx in universe.border_systems,
        adjacent_lowsec=universe.get_adjacent_lowsec(idx)
    )


def _compute_security_summary(
    universe: UniverseGraph,
    path: list[int]
) -> SecuritySummary:
    """Compute security breakdown for route."""
    highsec = 0
    lowsec = 0
    nullsec = 0
    lowest_sec = 1.0
    lowest_system = ""

    for idx in path:
        sec = universe.security[idx]
        sec_class = universe.security_class(idx)

        if sec_class == "HIGH":
            highsec += 1
        elif sec_class == "LOW":
            lowsec += 1
        else:
            nullsec += 1

        if sec < lowest_sec:
            lowest_sec = sec
            lowest_system = universe.idx_to_name[idx]

    return SecuritySummary(
        total_jumps=len(path) - 1,
        highsec_jumps=highsec,
        lowsec_jumps=lowsec,
        nullsec_jumps=nullsec,
        lowest_security=float(lowest_sec),
        lowest_security_system=lowest_system
    )


def _generate_warnings(
    universe: UniverseGraph,
    path: list[int],
    mode: str
) -> list[str]:
    """Generate route warnings for dangerous situations."""
    warnings = []

    # Count low/null transitions
    lowsec_entries = 0
    for i in range(len(path) - 1):
        src_class = universe.security_class(path[i])
        dst_class = universe.security_class(path[i + 1])

        if src_class == "HIGH" and dst_class in ("LOW", "NULL"):
            lowsec_entries += 1

    if lowsec_entries > 0:
        warnings.append(f"Route enters low/null-sec {lowsec_entries} time(s)")

    # Check for pipe systems (single entry/exit)
    for idx in path[1:-1]:  # Skip origin and destination
        if len(universe.graph.neighbors(idx)) == 2:
            sec = universe.security[idx]
            if sec < 0.45:
                name = universe.idx_to_name[idx]
                warnings.append(f"Pipe system: {name} (potential gatecamp)")
                break  # Only warn once

    if mode == "safe" and any(universe.security[idx] < 0.45 for idx in path):
        warnings.append("No fully high-sec route available")

    return warnings
```

## Acceptance Criteria

1. [ ] Tool registered and callable via MCP
2. [ ] Shortest mode uses unweighted BFS
3. [ ] Safe mode strongly avoids low/null-sec
4. [ ] Unsafe mode prefers dangerous space
5. [ ] Full SystemInfo returned for each waypoint
6. [ ] SecuritySummary accurately counts security classes
7. [ ] Warnings generated for dangerous routes
8. [ ] Response time < 2ms for typical queries
9. [ ] Handles unknown systems with suggestions

## Test Requirements

```python
# tests/mcp/test_tools_route.py

@pytest.mark.asyncio
async def test_route_shortest(mock_server):
    """Shortest route finds minimum jumps."""
    result = await mock_server.call_tool(
        "universe_route",
        origin="Jita",
        destination="Amarr",
        mode="shortest"
    )
    assert result["jumps"] > 0
    assert result["systems"][0]["name"] == "Jita"
    assert result["systems"][-1]["name"] == "Amarr"


@pytest.mark.asyncio
async def test_route_safe_avoids_lowsec(mock_server):
    """Safe route minimizes low-sec exposure."""
    safe = await mock_server.call_tool(
        "universe_route",
        origin="Jita",
        destination="Amarr",
        mode="safe"
    )
    shortest = await mock_server.call_tool(
        "universe_route",
        origin="Jita",
        destination="Amarr",
        mode="shortest"
    )
    # Safe route may be longer but with fewer low-sec
    assert safe["security_summary"]["lowsec_jumps"] <= shortest["security_summary"]["lowsec_jumps"]


@pytest.mark.asyncio
async def test_route_invalid_mode(mock_server):
    """Invalid mode raises error."""
    with pytest.raises(InvalidParameterError):
        await mock_server.call_tool(
            "universe_route",
            origin="Jita",
            destination="Amarr",
            mode="invalid"
        )


@pytest.mark.asyncio
async def test_route_unknown_system(mock_server):
    """Unknown system raises with suggestions."""
    with pytest.raises(SystemNotFoundError) as exc:
        await mock_server.call_tool(
            "universe_route",
            origin="Juta",
            destination="Amarr"
        )
    assert "Jita" in exc.value.suggestions


def test_route_latency(mock_server):
    """Route calculation within latency budget."""
    import time
    start = time.perf_counter()
    asyncio.run(mock_server.call_tool(
        "universe_route",
        origin="Jita",
        destination="Amarr",
        mode="shortest"
    ))
    elapsed = time.perf_counter() - start
    assert elapsed < 0.002  # 2ms budget
```

## Estimated Effort

- Implementation: Medium
- Testing: Medium
- Total: Medium

## Notes

- Edge weights pre-computed once per mode; could cache for repeated queries
- Warning detection includes pipe system check for gatecamp risk
- igraph's `get_shortest_paths` returns empty list for unreachable nodes
