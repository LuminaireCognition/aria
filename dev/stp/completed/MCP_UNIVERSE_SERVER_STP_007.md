# STP-007: Borders Tool (universe_borders)

**Status:** Draft
**Priority:** P1 - Core Feature
**Depends On:** STP-001, STP-002, STP-004
**Blocks:** STP-009 (loop planning uses border discovery)

## Objective

Implement the `universe_borders` MCP tool for finding high-sec systems that border low-sec space. This is essential for mining expedition planning and border patrol operations.

## Scope

### In Scope
- `universe_borders` tool registration
- BFS-based border system discovery
- Distance-sorted results from origin
- Adjacent lowsec system names
- Limit and max_jumps parameters

### Out of Scope
- Circular route planning (STP-009)
- Activity/danger data overlay (Phase 2)

## File Location

```
aria_esi/mcp/tools_borders.py
```

## Tool Specification

| Property | Value |
|----------|-------|
| Tool Name | `universe_borders` |
| Latency Target | <2ms |
| Parameters | origin (str), limit (int), max_jumps (int) |

## Implementation

### Tool Registration

```python
# aria_esi/mcp/tools_borders.py

from collections import deque
from mcp.server import Server
from ..universe.graph import UniverseGraph
from .models import BorderSystem
from .tools import resolve_system_name, get_universe
from .errors import InvalidParameterError


def register_borders_tools(server: Server, universe: UniverseGraph) -> None:
    """Register border discovery tools."""

    @server.tool()
    async def universe_borders(
        origin: str,
        limit: int = 10,
        max_jumps: int = 15
    ) -> dict:
        """
        Find high-sec systems that border low-sec space.

        Args:
            origin: Starting system for distance calculation
            limit: Maximum systems to return (default: 10, max: 50)
            max_jumps: Maximum search radius (default: 15, max: 30)

        Returns:
            List of BorderSystem objects sorted by distance.

        Example:
            universe_borders("Dodixie", limit=5)
        """
        # Validate parameters
        if limit < 1 or limit > 50:
            raise InvalidParameterError("limit", limit, "Must be between 1 and 50")
        if max_jumps < 1 or max_jumps > 30:
            raise InvalidParameterError("max_jumps", max_jumps, "Must be between 1 and 30")

        universe = get_universe()
        origin_idx = resolve_system_name(origin)

        # Find borders using BFS
        borders = _find_border_systems(universe, origin_idx, limit, max_jumps)

        return {
            "origin": origin,
            "borders": [b.model_dump() for b in borders],
            "total_found": len(borders),
            "search_radius": max_jumps
        }
```

### BFS Border Discovery

```python
def _find_border_systems(
    universe: UniverseGraph,
    origin_idx: int,
    limit: int,
    max_jumps: int
) -> list[BorderSystem]:
    """
    Find border systems using BFS with distance tracking.

    Algorithm:
    1. BFS from origin, tracking distance
    2. Check each visited system for border status
    3. Collect borders until limit reached or max_jumps exceeded
    4. Sort by distance and return top N

    Returns:
        List of BorderSystem objects sorted by distance.
    """
    g = universe.graph
    border_results = []

    # BFS with distance tracking
    visited = {origin_idx: 0}
    queue = deque([(origin_idx, 0)])

    # Gather extra for better sorting (may find closer ones later in BFS)
    gather_limit = limit * 3

    while queue:
        vertex, dist = queue.popleft()

        # Stop expanding beyond max_jumps
        if dist > max_jumps:
            continue

        # Check if this is a border system
        if vertex in universe.border_systems:
            border_results.append((vertex, dist))
            # Early exit if we have enough
            if len(border_results) >= gather_limit:
                break

        # Expand to neighbors
        for neighbor in g.neighbors(vertex):
            if neighbor not in visited:
                visited[neighbor] = dist + 1
                queue.append((neighbor, dist + 1))

    # Sort by distance, take top N
    border_results.sort(key=lambda x: x[1])
    border_results = border_results[:limit]

    # Build BorderSystem objects
    return [
        _build_border_system(universe, idx, dist)
        for idx, dist in border_results
    ]


def _build_border_system(
    universe: UniverseGraph,
    idx: int,
    jumps_from_origin: int
) -> BorderSystem:
    """Build BorderSystem object for a vertex."""
    # Get adjacent low-sec systems
    adjacent_lowsec = [
        universe.idx_to_name[n]
        for n in universe.graph.neighbors(idx)
        if universe.security[n] < 0.45
    ]

    return BorderSystem(
        name=universe.idx_to_name[idx],
        system_id=int(universe.system_ids[idx]),
        security=float(universe.security[idx]),
        jumps_from_origin=jumps_from_origin,
        adjacent_lowsec=adjacent_lowsec,
        region=universe.get_region_name(idx)
    )
```

### Optimization: Pre-filtered BFS

For better performance, we can prioritize high-sec systems during BFS:

```python
def _find_border_systems_optimized(
    universe: UniverseGraph,
    origin_idx: int,
    limit: int,
    max_jumps: int
) -> list[BorderSystem]:
    """
    Optimized border search that stays in high-sec.

    This version only traverses high-sec systems, which is
    faster and more relevant for mining/PI operations.
    """
    g = universe.graph
    border_results = []
    visited = {origin_idx: 0}
    queue = deque([(origin_idx, 0)])

    while queue and len(border_results) < limit:
        vertex, dist = queue.popleft()

        if dist > max_jumps:
            continue

        # Check if border
        if vertex in universe.border_systems:
            border_results.append((vertex, dist))

        # Only expand through high-sec neighbors
        for neighbor in g.neighbors(vertex):
            if neighbor not in visited:
                # Only queue high-sec systems
                if universe.security[neighbor] >= 0.45:
                    visited[neighbor] = dist + 1
                    queue.append((neighbor, dist + 1))

    return [
        _build_border_system(universe, idx, dist)
        for idx, dist in border_results
    ]
```

## Response Format

```json
{
  "origin": "Dodixie",
  "borders": [
    {
      "name": "Aunia",
      "system_id": 30002683,
      "security": 0.5,
      "jumps_from_origin": 3,
      "adjacent_lowsec": ["Ladistier", "Oulley"],
      "region": "Sinq Laison"
    },
    {
      "name": "Covryn",
      "system_id": 30002659,
      "security": 0.6,
      "jumps_from_origin": 5,
      "adjacent_lowsec": ["Muetralle"],
      "region": "Sinq Laison"
    }
  ],
  "total_found": 2,
  "search_radius": 15
}
```

## Acceptance Criteria

1. [ ] Tool registered and callable via MCP
2. [ ] BFS correctly discovers border systems
3. [ ] Results sorted by distance from origin
4. [ ] Adjacent lowsec names populated
5. [ ] Limit parameter respected
6. [ ] max_jumps parameter limits search radius
7. [ ] Parameter validation with clear errors
8. [ ] Response time < 2ms for typical queries

## Test Requirements

```python
# tests/mcp/test_tools_borders.py

@pytest.mark.asyncio
async def test_borders_from_dodixie(mock_server):
    """Find borders near Dodixie trade hub."""
    result = await mock_server.call_tool(
        "universe_borders",
        origin="Dodixie",
        limit=5
    )
    assert result["total_found"] <= 5
    assert all(b["jumps_from_origin"] > 0 for b in result["borders"])


@pytest.mark.asyncio
async def test_borders_sorted_by_distance(mock_server):
    """Results sorted by distance."""
    result = await mock_server.call_tool(
        "universe_borders",
        origin="Jita",
        limit=10
    )
    distances = [b["jumps_from_origin"] for b in result["borders"]]
    assert distances == sorted(distances)


@pytest.mark.asyncio
async def test_borders_have_adjacent_lowsec(mock_server):
    """Border systems have adjacent lowsec populated."""
    result = await mock_server.call_tool(
        "universe_borders",
        origin="Dodixie",
        limit=5
    )
    for border in result["borders"]:
        assert len(border["adjacent_lowsec"]) > 0


@pytest.mark.asyncio
async def test_borders_respects_max_jumps(mock_server):
    """Max jumps limits search radius."""
    result = await mock_server.call_tool(
        "universe_borders",
        origin="Jita",
        max_jumps=5,
        limit=100
    )
    for border in result["borders"]:
        assert border["jumps_from_origin"] <= 5


@pytest.mark.asyncio
async def test_borders_invalid_limit(mock_server):
    """Invalid limit raises error."""
    with pytest.raises(InvalidParameterError):
        await mock_server.call_tool(
            "universe_borders",
            origin="Jita",
            limit=100  # Over max
        )


@pytest.mark.asyncio
async def test_borders_origin_is_border(mock_server):
    """Origin that is a border system appears in results."""
    # Find a known border system and use as origin
    # It should appear at distance 0
    result = await mock_server.call_tool(
        "universe_borders",
        origin="Uedama",  # Known border
        limit=5
    )
    if result["total_found"] > 0:
        # Origin might be in results at distance 0
        first = result["borders"][0]
        if first["name"] == "Uedama":
            assert first["jumps_from_origin"] == 0


def test_borders_latency(mock_server):
    """Border discovery within latency budget."""
    import time
    start = time.perf_counter()
    asyncio.run(mock_server.call_tool(
        "universe_borders",
        origin="Dodixie",
        limit=10
    ))
    elapsed = time.perf_counter() - start
    assert elapsed < 0.002  # 2ms budget
```

## Estimated Effort

- Implementation: Medium
- Testing: Small
- Total: Medium

## Notes

- Pre-computed `border_systems` set enables O(1) membership checks
- BFS guarantees shortest path distances
- Gathering extra (limit * 3) ensures best results after sorting
- Consider adding region filter parameter in future
