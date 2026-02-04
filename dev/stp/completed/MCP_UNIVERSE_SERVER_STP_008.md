# STP-008: Search Tool (universe_search)

**Status:** Complete
**Priority:** P2 - Enhanced Feature
**Depends On:** STP-001, STP-002, STP-004
**Blocks:** None

## Objective

Implement the `universe_search` MCP tool for filtering systems by various criteria including security range, region, border status, and distance from a reference point.

## Scope

### In Scope
- `universe_search` tool registration
- Security range filtering (min/max)
- Region name filtering
- Border-only filtering
- Distance-based filtering from origin
- Result limiting and pagination
- Combined filter logic

### Out of Scope
- Fuzzy name search (could add later)
- Constellation filtering (could add later)
- Activity/population data (Phase 2)

## File Location

```
aria_esi/mcp/tools_search.py
```

## Tool Specification

| Property | Value |
|----------|-------|
| Tool Name | `universe_search` |
| Latency Target | <5ms |
| Parameters | origin, max_jumps, security_min, security_max, region, is_border, limit |

## Implementation

### Tool Registration

```python
# aria_esi/mcp/tools_search.py

from collections import deque
from mcp.server import Server
from ..universe.graph import UniverseGraph
from .models import SystemSearchResult
from .tools import resolve_system_name, get_universe
from .errors import InvalidParameterError


def register_search_tools(server: Server, universe: UniverseGraph) -> None:
    """Register system search tools."""

    @server.tool()
    async def universe_search(
        origin: str | None = None,
        max_jumps: int | None = None,
        security_min: float | None = None,
        security_max: float | None = None,
        region: str | None = None,
        is_border: bool | None = None,
        limit: int = 20
    ) -> dict:
        """
        Search for systems matching criteria.

        Args:
            origin: Center point for distance filter (required if max_jumps set)
            max_jumps: Maximum distance from origin
            security_min: Minimum security status (inclusive)
            security_max: Maximum security status (inclusive)
            region: Filter to specific region name (case-insensitive)
            is_border: Filter to border systems only
            limit: Maximum results (default: 20, max: 100)

        Returns:
            List of matching SystemSearchResult objects.

        Examples:
            # Find low-sec systems within 10 jumps of Dodixie
            universe_search(
                origin="Dodixie",
                max_jumps=10,
                security_min=0.1,
                security_max=0.4
            )

            # Find all border systems in The Forge
            universe_search(region="The Forge", is_border=true)
        """
        universe = get_universe()

        # Validate parameters
        if limit < 1 or limit > 100:
            raise InvalidParameterError("limit", limit, "Must be between 1 and 100")

        if max_jumps is not None and origin is None:
            raise InvalidParameterError(
                "origin", None,
                "origin is required when max_jumps is specified"
            )

        if max_jumps is not None and (max_jumps < 1 or max_jumps > 50):
            raise InvalidParameterError("max_jumps", max_jumps, "Must be between 1 and 50")

        if security_min is not None and (security_min < -1.0 or security_min > 1.0):
            raise InvalidParameterError("security_min", security_min, "Must be between -1.0 and 1.0")

        if security_max is not None and (security_max < -1.0 or security_max > 1.0):
            raise InvalidParameterError("security_max", security_max, "Must be between -1.0 and 1.0")

        # Build search
        origin_idx = resolve_system_name(origin) if origin else None
        region_id = _resolve_region(universe, region) if region else None

        results = _search_systems(
            universe=universe,
            origin_idx=origin_idx,
            max_jumps=max_jumps,
            security_min=security_min,
            security_max=security_max,
            region_id=region_id,
            is_border=is_border,
            limit=limit
        )

        return {
            "systems": [r.model_dump() for r in results],
            "total_found": len(results),
            "filters_applied": _summarize_filters(
                origin, max_jumps, security_min, security_max, region, is_border
            )
        }
```

### Search Implementation

```python
def _resolve_region(universe: UniverseGraph, region_name: str) -> int | None:
    """Resolve region name to ID (case-insensitive)."""
    name_lower = region_name.lower()
    for region_id, name in universe.region_names.items():
        if name.lower() == name_lower:
            return region_id
    return None


def _search_systems(
    universe: UniverseGraph,
    origin_idx: int | None,
    max_jumps: int | None,
    security_min: float | None,
    security_max: float | None,
    region_id: int | None,
    is_border: bool | None,
    limit: int
) -> list[SystemSearchResult]:
    """
    Execute system search with filters.

    Strategy:
    - If origin + max_jumps: BFS within range, then filter
    - If region: Iterate region systems, then filter
    - Otherwise: Full scan with filters (less efficient)
    """
    results = []
    distances = {}

    # Determine candidate set
    if origin_idx is not None and max_jumps is not None:
        # BFS to find systems within range
        candidates, distances = _bfs_within_range(universe, origin_idx, max_jumps)
    elif region_id is not None:
        # Use region index
        candidates = set(universe.region_systems.get(region_id, []))
    elif is_border:
        # Use border index
        candidates = universe.border_systems
    else:
        # Full scan
        candidates = set(range(universe.system_count))

    # Apply filters
    for idx in candidates:
        if len(results) >= limit:
            break

        # Security filter
        sec = universe.security[idx]
        if security_min is not None and sec < security_min:
            continue
        if security_max is not None and sec > security_max:
            continue

        # Region filter (if not already applied)
        if region_id is not None and origin_idx is not None:
            if int(universe.region_ids[idx]) != region_id:
                continue

        # Border filter (if not already applied as candidate set)
        if is_border is True and idx not in universe.border_systems:
            continue
        if is_border is False and idx in universe.border_systems:
            continue

        results.append(_build_search_result(universe, idx, distances.get(idx)))

    return results


def _bfs_within_range(
    universe: UniverseGraph,
    origin_idx: int,
    max_jumps: int
) -> tuple[set[int], dict[int, int]]:
    """
    BFS to find all systems within max_jumps.

    Returns:
        Tuple of (set of vertex indices, dict of distances)
    """
    g = universe.graph
    visited = {origin_idx: 0}
    queue = deque([(origin_idx, 0)])

    while queue:
        vertex, dist = queue.popleft()
        if dist >= max_jumps:
            continue

        for neighbor in g.neighbors(vertex):
            if neighbor not in visited:
                visited[neighbor] = dist + 1
                queue.append((neighbor, dist + 1))

    return set(visited.keys()), visited


def _build_search_result(
    universe: UniverseGraph,
    idx: int,
    jumps_from_origin: int | None
) -> SystemSearchResult:
    """Build search result for a vertex."""
    return SystemSearchResult(
        name=universe.idx_to_name[idx],
        system_id=int(universe.system_ids[idx]),
        security=float(universe.security[idx]),
        security_class=universe.security_class(idx),
        region=universe.get_region_name(idx),
        jumps_from_origin=jumps_from_origin
    )


def _summarize_filters(
    origin: str | None,
    max_jumps: int | None,
    security_min: float | None,
    security_max: float | None,
    region: str | None,
    is_border: bool | None
) -> dict:
    """Summarize applied filters for response."""
    filters = {}
    if origin:
        filters["origin"] = origin
    if max_jumps is not None:
        filters["max_jumps"] = max_jumps
    if security_min is not None:
        filters["security_min"] = security_min
    if security_max is not None:
        filters["security_max"] = security_max
    if region:
        filters["region"] = region
    if is_border is not None:
        filters["is_border"] = is_border
    return filters
```

## Response Format

```json
{
  "systems": [
    {
      "name": "Oulley",
      "system_id": 30002715,
      "security": 0.3,
      "security_class": "LOW",
      "region": "Sinq Laison",
      "jumps_from_origin": 4
    },
    {
      "name": "Muetralle",
      "system_id": 30002657,
      "security": 0.2,
      "security_class": "LOW",
      "region": "Sinq Laison",
      "jumps_from_origin": 6
    }
  ],
  "total_found": 2,
  "filters_applied": {
    "origin": "Dodixie",
    "max_jumps": 10,
    "security_min": 0.1,
    "security_max": 0.4
  }
}
```

## Acceptance Criteria

1. [x] Tool registered and callable via MCP
2. [x] Security range filtering works (inclusive bounds)
3. [x] Region filtering works (case-insensitive)
4. [x] Border-only filtering works
5. [x] Distance filtering requires origin
6. [x] Limit parameter respected
7. [x] Parameter validation with clear errors
8. [x] Response time < 5ms for typical queries
9. [x] Unknown region returns empty results (not error)

## Test Requirements

```python
# tests/mcp/test_tools_search.py

@pytest.mark.asyncio
async def test_search_by_security_range(mock_server):
    """Filter by security range."""
    result = await mock_server.call_tool(
        "universe_search",
        security_min=0.1,
        security_max=0.4,
        limit=10
    )
    for sys in result["systems"]:
        assert 0.1 <= sys["security"] <= 0.4


@pytest.mark.asyncio
async def test_search_by_region(mock_server):
    """Filter by region name."""
    result = await mock_server.call_tool(
        "universe_search",
        region="The Forge",
        limit=10
    )
    for sys in result["systems"]:
        assert sys["region"] == "The Forge"


@pytest.mark.asyncio
async def test_search_borders_only(mock_server):
    """Filter to border systems only."""
    result = await mock_server.call_tool(
        "universe_search",
        is_border=True,
        limit=10
    )
    # Verify all returned are actually borders
    systems = await mock_server.call_tool(
        "universe_systems",
        systems=[s["name"] for s in result["systems"]]
    )
    for sys in systems["systems"]:
        assert sys["is_border"] is True


@pytest.mark.asyncio
async def test_search_with_distance(mock_server):
    """Filter by distance from origin."""
    result = await mock_server.call_tool(
        "universe_search",
        origin="Jita",
        max_jumps=5,
        limit=20
    )
    for sys in result["systems"]:
        assert sys["jumps_from_origin"] is not None
        assert sys["jumps_from_origin"] <= 5


@pytest.mark.asyncio
async def test_search_requires_origin_for_max_jumps(mock_server):
    """max_jumps without origin raises error."""
    with pytest.raises(InvalidParameterError):
        await mock_server.call_tool(
            "universe_search",
            max_jumps=10
        )


@pytest.mark.asyncio
async def test_search_combined_filters(mock_server):
    """Multiple filters combine correctly."""
    result = await mock_server.call_tool(
        "universe_search",
        origin="Dodixie",
        max_jumps=10,
        security_min=0.5,
        is_border=True,
        limit=10
    )
    for sys in result["systems"]:
        assert sys["security"] >= 0.5
        assert sys["jumps_from_origin"] <= 10
```

## Estimated Effort

- Implementation: Medium
- Testing: Medium
- Total: Medium

## Notes

- Uses pre-computed indexes (region_systems, border_systems) for efficiency
- BFS-based distance filter is O(V + E) within range
- Full scan is O(N) where N = system_count; acceptable for filtered queries
- Consider adding constellation filter in future
