# STP-006: Systems Tool (universe_systems)

**Status:** Draft
**Priority:** P1 - Core Feature
**Depends On:** STP-001, STP-002, STP-004
**Blocks:** None

## Objective

Implement the `universe_systems` MCP tool for batch lookup of system information. This tool enables efficient retrieval of detailed information for multiple systems in a single call.

## Scope

### In Scope
- `universe_systems` tool registration
- Batch system name resolution
- Full SystemInfo construction for each system
- Null handling for unknown systems
- Preserved input order in output

### Out of Scope
- Fuzzy search (use `universe_search`)
- Route calculation (use `universe_route`)

## File Location

```
aria_esi/mcp/tools_systems.py
```

## Tool Specification

| Property | Value |
|----------|-------|
| Tool Name | `universe_systems` |
| Latency Target | <1ms |
| Parameters | systems (list[str]) |

## Implementation

### Tool Registration

```python
# aria_esi/mcp/tools_systems.py

from mcp.server import Server
from ..universe.graph import UniverseGraph
from .models import SystemInfo, NeighborInfo
from .tools import get_universe


def register_systems_tools(server: Server, universe: UniverseGraph) -> None:
    """Register system lookup tools."""

    @server.tool()
    async def universe_systems(systems: list[str]) -> dict:
        """
        Get detailed information for one or more systems.

        Args:
            systems: List of system names (case-insensitive)

        Returns:
            List of SystemInfo objects, preserving input order.
            Unknown systems return null in their position.

        Example:
            universe_systems(["Jita", "Perimeter", "Unknown"])
            # Returns: [SystemInfo, SystemInfo, null]
        """
        universe = get_universe()
        results = []

        for name in systems:
            idx = universe.resolve_name(name)
            if idx is None:
                results.append(None)
            else:
                results.append(_build_system_info(universe, idx))

        return {
            "systems": [
                s.model_dump() if s else None
                for s in results
            ],
            "found": sum(1 for s in results if s is not None),
            "not_found": sum(1 for s in results if s is None)
        }
```

### System Info Builder

```python
def _build_system_info(universe: UniverseGraph, idx: int) -> SystemInfo:
    """
    Build complete SystemInfo for a vertex.

    This is shared with tools_route.py - consider moving to shared module.
    """
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
```

### Shared Utilities

To avoid duplication with `tools_route.py`, extract to shared module:

```python
# aria_esi/mcp/utils.py

from ..universe.graph import UniverseGraph
from .models import SystemInfo, NeighborInfo


def build_system_info(universe: UniverseGraph, idx: int) -> SystemInfo:
    """Build complete SystemInfo for a vertex."""
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
```

## Response Format

```json
{
  "systems": [
    {
      "name": "Jita",
      "system_id": 30000142,
      "security": 0.9459,
      "security_class": "HIGH",
      "constellation": "Kimotoro",
      "constellation_id": 20000020,
      "region": "The Forge",
      "region_id": 10000002,
      "neighbors": [
        {"name": "Perimeter", "security": 0.9, "security_class": "HIGH"},
        {"name": "New Caldari", "security": 1.0, "security_class": "HIGH"}
      ],
      "is_border": false,
      "adjacent_lowsec": []
    },
    {
      "name": "Perimeter",
      ...
    },
    null
  ],
  "found": 2,
  "not_found": 1
}
```

## Acceptance Criteria

1. [ ] Tool registered and callable via MCP
2. [ ] Batch lookup processes multiple systems in single call
3. [ ] Input order preserved in output
4. [ ] Unknown systems return null (not error)
5. [ ] Case-insensitive name resolution
6. [ ] Full neighbor information included
7. [ ] Border status and adjacent lowsec populated
8. [ ] Response time < 1ms for typical queries (≤10 systems)

## Test Requirements

```python
# tests/mcp/test_tools_systems.py

@pytest.mark.asyncio
async def test_single_system_lookup(mock_server):
    """Single system returns complete info."""
    result = await mock_server.call_tool(
        "universe_systems",
        systems=["Jita"]
    )
    assert result["found"] == 1
    assert result["systems"][0]["name"] == "Jita"
    assert result["systems"][0]["security_class"] == "HIGH"


@pytest.mark.asyncio
async def test_batch_lookup_preserves_order(mock_server):
    """Batch lookup preserves input order."""
    result = await mock_server.call_tool(
        "universe_systems",
        systems=["Amarr", "Jita", "Dodixie"]
    )
    assert result["found"] == 3
    assert result["systems"][0]["name"] == "Amarr"
    assert result["systems"][1]["name"] == "Jita"
    assert result["systems"][2]["name"] == "Dodixie"


@pytest.mark.asyncio
async def test_unknown_system_returns_null(mock_server):
    """Unknown systems return null in position."""
    result = await mock_server.call_tool(
        "universe_systems",
        systems=["Jita", "UnknownSystem", "Amarr"]
    )
    assert result["found"] == 2
    assert result["not_found"] == 1
    assert result["systems"][0] is not None
    assert result["systems"][1] is None
    assert result["systems"][2] is not None


@pytest.mark.asyncio
async def test_case_insensitive_lookup(mock_server):
    """Lookup ignores case."""
    result = await mock_server.call_tool(
        "universe_systems",
        systems=["jita", "JITA", "JiTa"]
    )
    assert result["found"] == 3
    for sys in result["systems"]:
        assert sys["name"] == "Jita"  # Canonical form


@pytest.mark.asyncio
async def test_empty_list_returns_empty(mock_server):
    """Empty input returns empty results."""
    result = await mock_server.call_tool(
        "universe_systems",
        systems=[]
    )
    assert result["found"] == 0
    assert result["systems"] == []


@pytest.mark.asyncio
async def test_neighbor_info_complete(mock_server):
    """Neighbor info includes all fields."""
    result = await mock_server.call_tool(
        "universe_systems",
        systems=["Jita"]
    )
    neighbors = result["systems"][0]["neighbors"]
    assert len(neighbors) > 0
    for neighbor in neighbors:
        assert "name" in neighbor
        assert "security" in neighbor
        assert "security_class" in neighbor


def test_batch_lookup_latency(mock_server):
    """Batch lookup within latency budget."""
    import time
    start = time.perf_counter()
    asyncio.run(mock_server.call_tool(
        "universe_systems",
        systems=["Jita", "Amarr", "Dodixie", "Rens", "Hek"]
    ))
    elapsed = time.perf_counter() - start
    assert elapsed < 0.001  # 1ms budget
```

## Estimated Effort

- Implementation: Small
- Testing: Small
- Total: Small

## Notes

- Consider extracting `build_system_info` to shared utils module
- Null handling allows caller to detect missing systems without failing entire batch
- Response includes `found`/`not_found` counts for quick validation
