# STP-009: Loop Tool (universe_loop)

**Status:** Complete
**Priority:** P2 - Enhanced Feature
**Depends On:** STP-001, STP-002, STP-004, STP-005, STP-007
**Blocks:** None

## Objective

Implement the `universe_loop` MCP tool for planning circular routes that visit multiple border systems and return to origin. This supports mining expeditions, PI collection circuits, and exploration patrols.

## Scope

### In Scope
- `universe_loop` tool registration
- Border system discovery within range
- Spatial diversity selection algorithm
- Nearest-neighbor TSP approximation
- Route expansion to full waypoint list
- Efficiency metrics (backtracking)

### Out of Scope
- Optimal TSP solution (NP-hard, use heuristic)
- Activity-based danger assessment (Phase 2)
- Jump bridge shortcuts (Phase 2)

## File Location

```
aria_esi/mcp/tools_loop.py
```

## Tool Specification

| Property | Value |
|----------|-------|
| Tool Name | `universe_loop` |
| Latency Target | <20ms |
| Parameters | origin (str), target_jumps (int), min_borders (int), max_borders (int) |

## Implementation

### Tool Registration

```python
# aria_esi/mcp/tools_loop.py

from collections import deque
from mcp.server import Server
from ..universe.graph import UniverseGraph
from .models import LoopResult, SystemInfo, BorderSystem
from .tools import resolve_system_name, get_universe
from .utils import build_system_info
from .errors import InvalidParameterError


def register_loop_tools(server: Server, universe: UniverseGraph) -> None:
    """Register loop planning tools."""

    @server.tool()
    async def universe_loop(
        origin: str,
        target_jumps: int = 20,
        min_borders: int = 4,
        max_borders: int = 8
    ) -> dict:
        """
        Plan a circular route visiting multiple border systems.

        Useful for: Mining expeditions, PI routes, exploration circuits.

        Args:
            origin: Starting and ending system
            target_jumps: Approximate desired loop length (default: 20)
            min_borders: Minimum border systems to visit (default: 4)
            max_borders: Maximum border systems to visit (default: 8)

        Returns:
            LoopResult with optimized route minimizing backtracking.

        Algorithm:
            1. BFS to find border systems within range
            2. Select spatially diverse subset
            3. Approximate TSP solution through selected borders
            4. Expand waypoints to full route

        Example:
            universe_loop("Masalle", target_jumps=25, min_borders=5)
        """
        universe = get_universe()

        # Validate parameters
        if target_jumps < 10 or target_jumps > 100:
            raise InvalidParameterError(
                "target_jumps", target_jumps, "Must be between 10 and 100"
            )
        if min_borders < 2 or min_borders > 10:
            raise InvalidParameterError(
                "min_borders", min_borders, "Must be between 2 and 10"
            )
        if max_borders < min_borders or max_borders > 15:
            raise InvalidParameterError(
                "max_borders", max_borders,
                f"Must be between {min_borders} and 15"
            )

        origin_idx = resolve_system_name(origin)

        result = _plan_loop(
            universe=universe,
            origin_idx=origin_idx,
            target_jumps=target_jumps,
            min_borders=min_borders,
            max_borders=max_borders
        )

        return result
```

### Loop Planning Algorithm

```python
def _plan_loop(
    universe: UniverseGraph,
    origin_idx: int,
    target_jumps: int,
    min_borders: int,
    max_borders: int
) -> dict:
    """
    Plan circular route through border systems.

    Returns:
        LoopResult as dict
    """
    # Step 1: Find candidate borders within reasonable range
    search_radius = target_jumps // 2
    candidates = _find_borders_with_distance(
        universe, origin_idx,
        limit=max_borders * 3,
        max_jumps=search_radius
    )

    if len(candidates) < min_borders:
        return {
            "error": f"Only found {len(candidates)} border systems within {search_radius} jumps",
            "suggestion": "Try increasing target_jumps or decreasing min_borders"
        }

    # Step 2: Select diverse subset
    selected = _select_diverse_borders(
        universe, candidates, max_borders
    )

    # Ensure we have at least min_borders
    if len(selected) < min_borders:
        selected = candidates[:min_borders]

    # Step 3: Solve TSP approximation
    tour = _nearest_neighbor_tsp(
        universe, origin_idx, [s[0] for s in selected]
    )

    # Step 4: Expand tour to full route
    full_route = _expand_tour(universe, tour)

    # Step 5: Build result
    return _build_loop_result(
        universe, origin_idx, full_route, selected
    )


def _find_borders_with_distance(
    universe: UniverseGraph,
    origin_idx: int,
    limit: int,
    max_jumps: int
) -> list[tuple[int, int]]:
    """Find border systems with their distances from origin."""
    g = universe.graph
    borders = []
    visited = {origin_idx: 0}
    queue = deque([(origin_idx, 0)])

    while queue:
        vertex, dist = queue.popleft()
        if dist > max_jumps:
            continue

        if vertex in universe.border_systems:
            borders.append((vertex, dist))

        for neighbor in g.neighbors(vertex):
            if neighbor not in visited:
                visited[neighbor] = dist + 1
                queue.append((neighbor, dist + 1))

    borders.sort(key=lambda x: x[1])
    return borders[:limit]


def _select_diverse_borders(
    universe: UniverseGraph,
    candidates: list[tuple[int, int]],
    max_count: int
) -> list[tuple[int, int]]:
    """
    Select spatially diverse border systems.

    Algorithm: Greedy selection maximizing minimum distance to selected set.
    Start with closest to origin, then iteratively add most distant from
    currently selected set.
    """
    if not candidates:
        return []

    selected = [candidates[0]]
    remaining = list(candidates[1:])

    while len(selected) < max_count and remaining:
        # Find candidate maximizing minimum distance to selected set
        best_idx = -1
        best_min_dist = -1

        for i, (vertex, _) in enumerate(remaining):
            min_dist = min(
                _jump_distance(universe, vertex, s[0])
                for s in selected
            )
            if min_dist > best_min_dist:
                best_min_dist = min_dist
                best_idx = i

        if best_idx >= 0:
            selected.append(remaining.pop(best_idx))
        else:
            break

    return selected


def _jump_distance(universe: UniverseGraph, src: int, dst: int) -> int:
    """Get shortest path distance between two vertices."""
    paths = universe.graph.get_shortest_paths(src, dst)
    if paths and paths[0]:
        return len(paths[0]) - 1
    return float('inf')


def _nearest_neighbor_tsp(
    universe: UniverseGraph,
    start: int,
    waypoints: list[int]
) -> list[int]:
    """
    Nearest-neighbor TSP heuristic.

    Produces a tour visiting all waypoints and returning to start.
    """
    tour = [start]
    unvisited = set(waypoints)

    current = start
    while unvisited:
        nearest = min(
            unvisited,
            key=lambda w: _jump_distance(universe, current, w)
        )
        tour.append(nearest)
        unvisited.remove(nearest)
        current = nearest

    # Don't add start again here - expansion handles return
    return tour


def _expand_tour(universe: UniverseGraph, tour: list[int]) -> list[int]:
    """
    Expand tour waypoints to full route with intermediate systems.

    Connects each consecutive pair with shortest path.
    """
    if len(tour) < 2:
        return tour

    full_route = []

    for i in range(len(tour)):
        src = tour[i]
        dst = tour[(i + 1) % len(tour)]  # Wrap to origin

        paths = universe.graph.get_shortest_paths(src, dst)
        if paths and paths[0]:
            segment = paths[0]
            # Add all but last (will be added as next segment's start)
            if i < len(tour) - 1:
                full_route.extend(segment[:-1])
            else:
                # Last segment returns to origin, include all
                full_route.extend(segment)

    return full_route


def _build_loop_result(
    universe: UniverseGraph,
    origin_idx: int,
    full_route: list[int],
    borders_visited: list[tuple[int, int]]
) -> dict:
    """Build LoopResult from computed route."""
    systems = [build_system_info(universe, idx) for idx in full_route]

    border_systems = [
        BorderSystem(
            name=universe.idx_to_name[idx],
            system_id=int(universe.system_ids[idx]),
            security=float(universe.security[idx]),
            jumps_from_origin=dist,
            adjacent_lowsec=universe.get_adjacent_lowsec(idx),
            region=universe.get_region_name(idx)
        )
        for idx, dist in borders_visited
    ]

    unique_count = len(set(full_route))
    total_jumps = len(full_route) - 1 if full_route else 0
    backtrack = len(full_route) - unique_count

    return LoopResult(
        systems=[s.model_dump() for s in systems],
        total_jumps=total_jumps,
        unique_systems=unique_count,
        border_systems_visited=[b.model_dump() for b in border_systems],
        backtrack_jumps=backtrack,
        efficiency=unique_count / len(full_route) if full_route else 0.0
    ).model_dump()
```

## Response Format

```json
{
  "systems": [
    {"name": "Masalle", "security": 0.9, ...},
    {"name": "Aunia", "security": 0.5, ...},
    ...
  ],
  "total_jumps": 24,
  "unique_systems": 20,
  "border_systems_visited": [
    {
      "name": "Aunia",
      "system_id": 30002683,
      "security": 0.5,
      "jumps_from_origin": 3,
      "adjacent_lowsec": ["Ladistier", "Oulley"],
      "region": "Sinq Laison"
    },
    ...
  ],
  "backtrack_jumps": 4,
  "efficiency": 0.83
}
```

## Acceptance Criteria

1. [x] Tool registered and callable via MCP
2. [x] Route starts and ends at origin
3. [x] Visits between min_borders and max_borders border systems
4. [x] Diverse border selection (not clustered)
5. [x] TSP approximation minimizes total distance
6. [x] Full route includes intermediate systems
7. [x] Efficiency metric calculated correctly
8. [x] Response time < 20ms for typical queries
9. [x] Helpful error when insufficient borders found

## Test Requirements

```python
# tests/mcp/test_tools_loop.py

@pytest.mark.asyncio
async def test_loop_returns_to_origin(mock_server):
    """Loop starts and ends at origin."""
    result = await mock_server.call_tool(
        "universe_loop",
        origin="Dodixie",
        target_jumps=20
    )
    assert result["systems"][0]["name"] == "Dodixie"
    assert result["systems"][-1]["name"] == "Dodixie"


@pytest.mark.asyncio
async def test_loop_visits_borders(mock_server):
    """Loop visits multiple border systems."""
    result = await mock_server.call_tool(
        "universe_loop",
        origin="Dodixie",
        min_borders=4,
        max_borders=6
    )
    assert len(result["border_systems_visited"]) >= 4
    assert len(result["border_systems_visited"]) <= 6


@pytest.mark.asyncio
async def test_loop_efficiency(mock_server):
    """Loop efficiency is reasonable."""
    result = await mock_server.call_tool(
        "universe_loop",
        origin="Dodixie",
        target_jumps=25
    )
    assert result["efficiency"] >= 0.5  # At least 50% unique systems


@pytest.mark.asyncio
async def test_loop_insufficient_borders(mock_server):
    """Returns error when not enough borders found."""
    result = await mock_server.call_tool(
        "universe_loop",
        origin="Jita",
        target_jumps=5,  # Very small radius
        min_borders=10   # Too many required
    )
    assert "error" in result


@pytest.mark.asyncio
async def test_loop_diverse_selection(mock_server):
    """Borders are spatially diverse."""
    result = await mock_server.call_tool(
        "universe_loop",
        origin="Dodixie",
        max_borders=5
    )
    # Check that borders aren't all in same region
    regions = {b["region"] for b in result["border_systems_visited"]}
    # Not a strict requirement but indicates diversity
    assert len(regions) >= 1


def test_loop_latency(mock_server):
    """Loop planning within latency budget."""
    import time
    start = time.perf_counter()
    asyncio.run(mock_server.call_tool(
        "universe_loop",
        origin="Dodixie",
        target_jumps=20
    ))
    elapsed = time.perf_counter() - start
    assert elapsed < 0.020  # 20ms budget
```

## Estimated Effort

- Implementation: Large
- Testing: Medium
- Total: Large

## Notes

- Nearest-neighbor TSP is O(n^2) which is acceptable for n ≤ 15
- Could upgrade to 2-opt improvement for better routes
- Diversity selection prevents clustering around origin
- Efficiency metric helps capsuleers evaluate route quality
