# STP-010: Analyze Tool (universe_analyze)

**Status:** Complete
**Priority:** P2 - Enhanced Feature
**Depends On:** STP-001, STP-002, STP-004
**Blocks:** None

## Objective

Implement the `universe_analyze` MCP tool for detailed security analysis of a route or system sequence. This identifies chokepoints, danger zones, and provides tactical intelligence for route planning.

## Scope

### In Scope
- `universe_analyze` tool registration
- Security profile computation
- Chokepoint detection (low-sec entry/exit points)
- Danger zone identification (consecutive low/null segments)
- Route validation (connected systems)
- Optional safest alternative suggestion

### Out of Scope
- Real-time activity data (Phase 2)
- Kill statistics overlay (Phase 2)
- Fleet composition recommendations

## File Location

```
aria_esi/mcp/tools_analyze.py
```

## Tool Specification

| Property | Value |
|----------|-------|
| Tool Name | `universe_analyze` |
| Latency Target | <2ms |
| Parameters | systems (list[str]) |

## Implementation

### Tool Registration

```python
# aria_esi/mcp/tools_analyze.py

from mcp.server import Server
from ..universe.graph import UniverseGraph
from .models import RouteAnalysis, SystemInfo, SecuritySummary, DangerZone, RouteResult
from .tools import resolve_system_name, get_universe
from .utils import build_system_info
from .errors import InvalidParameterError, RouteNotFoundError


def register_analyze_tools(server: Server, universe: UniverseGraph) -> None:
    """Register route analysis tools."""

    @server.tool()
    async def universe_analyze(systems: list[str]) -> dict:
        """
        Analyze security profile of a route or system list.

        Args:
            systems: Ordered list of system names representing a route

        Returns:
            RouteAnalysis with security breakdown, chokepoints, and dangers.

        Example:
            universe_analyze(["Jita", "Perimeter", "Urlen", "Sirppala"])
        """
        universe = get_universe()

        if len(systems) < 2:
            raise InvalidParameterError(
                "systems", systems,
                "At least 2 systems required for analysis"
            )

        # Resolve all system names
        indices = []
        for name in systems:
            idx = universe.resolve_name(name)
            if idx is None:
                raise InvalidParameterError(
                    "systems", name,
                    f"Unknown system: {name}"
                )
            indices.append(idx)

        # Validate route connectivity
        _validate_connectivity(universe, indices, systems)

        # Build analysis
        result = _analyze_route(universe, indices)

        return result.model_dump()
```

### Route Validation

```python
def _validate_connectivity(
    universe: UniverseGraph,
    indices: list[int],
    names: list[str]
) -> None:
    """
    Validate that consecutive systems are connected.

    Raises:
        RouteNotFoundError: If systems aren't connected by stargate.
    """
    g = universe.graph
    for i in range(len(indices) - 1):
        src = indices[i]
        dst = indices[i + 1]
        if dst not in g.neighbors(src):
            raise RouteNotFoundError(
                names[i], names[i + 1],
                reason="Systems not connected by stargate"
            )
```

### Analysis Implementation

```python
def _analyze_route(
    universe: UniverseGraph,
    indices: list[int]
) -> RouteAnalysis:
    """Build complete route analysis."""
    systems = [build_system_info(universe, idx) for idx in indices]
    security_summary = _compute_security_summary(universe, indices)
    chokepoints = _find_chokepoints(universe, indices)
    danger_zones = _find_danger_zones(universe, indices)

    return RouteAnalysis(
        systems=systems,
        security_summary=security_summary,
        chokepoints=chokepoints,
        danger_zones=danger_zones,
        safest_alternative=None  # Could compute on demand
    )


def _compute_security_summary(
    universe: UniverseGraph,
    indices: list[int]
) -> SecuritySummary:
    """Compute security breakdown for route."""
    highsec = 0
    lowsec = 0
    nullsec = 0
    lowest_sec = 1.0
    lowest_system = ""

    for idx in indices:
        sec = float(universe.security[idx])
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
        total_jumps=len(indices) - 1,
        highsec_jumps=highsec,
        lowsec_jumps=lowsec,
        nullsec_jumps=nullsec,
        lowest_security=lowest_sec,
        lowest_security_system=lowest_system
    )


def _find_chokepoints(
    universe: UniverseGraph,
    indices: list[int]
) -> list[SystemInfo]:
    """
    Find chokepoints: points where route transitions security class.

    A chokepoint is a system where:
    - Previous system is high-sec AND current is low/null (entry)
    - Previous system is low/null AND current is high-sec (exit)
    """
    chokepoints = []

    for i in range(1, len(indices)):
        prev_idx = indices[i - 1]
        curr_idx = indices[i]

        prev_class = universe.security_class(prev_idx)
        curr_class = universe.security_class(curr_idx)

        # Entry to dangerous space
        if prev_class == "HIGH" and curr_class in ("LOW", "NULL"):
            chokepoints.append(build_system_info(universe, curr_idx))

        # Exit from dangerous space
        elif prev_class in ("LOW", "NULL") and curr_class == "HIGH":
            chokepoints.append(build_system_info(universe, prev_idx))

    return chokepoints


def _find_danger_zones(
    universe: UniverseGraph,
    indices: list[int]
) -> list[DangerZone]:
    """
    Find danger zones: consecutive segments in low/null-sec.

    Returns list of (start_system, end_system, jump_count, min_security).
    """
    danger_zones = []
    in_danger = False
    zone_start = None
    zone_min_sec = 1.0

    for i, idx in enumerate(indices):
        sec = float(universe.security[idx])
        is_dangerous = sec < 0.45

        if is_dangerous and not in_danger:
            # Entering danger zone
            in_danger = True
            zone_start = i
            zone_min_sec = sec

        elif is_dangerous and in_danger:
            # Continuing in danger zone
            zone_min_sec = min(zone_min_sec, sec)

        elif not is_dangerous and in_danger:
            # Exiting danger zone
            in_danger = False
            if zone_start is not None:
                danger_zones.append(DangerZone(
                    start_system=universe.idx_to_name[indices[zone_start]],
                    end_system=universe.idx_to_name[indices[i - 1]],
                    jump_count=i - zone_start,
                    min_security=zone_min_sec
                ))
            zone_start = None

    # Handle case where route ends in danger zone
    if in_danger and zone_start is not None:
        danger_zones.append(DangerZone(
            start_system=universe.idx_to_name[indices[zone_start]],
            end_system=universe.idx_to_name[indices[-1]],
            jump_count=len(indices) - zone_start,
            min_security=zone_min_sec
        ))

    return danger_zones
```

## Response Format

```json
{
  "systems": [
    {"name": "Jita", "security": 0.9, "security_class": "HIGH", ...},
    {"name": "Perimeter", "security": 0.9, "security_class": "HIGH", ...},
    {"name": "Urlen", "security": 0.8, "security_class": "HIGH", ...},
    {"name": "Sirppala", "security": 0.7, "security_class": "HIGH", ...}
  ],
  "security_summary": {
    "total_jumps": 3,
    "highsec_jumps": 4,
    "lowsec_jumps": 0,
    "nullsec_jumps": 0,
    "lowest_security": 0.7,
    "lowest_security_system": "Sirppala"
  },
  "chokepoints": [],
  "danger_zones": [],
  "safest_alternative": null
}
```

### With Danger Zones

```json
{
  "systems": [...],
  "security_summary": {
    "total_jumps": 8,
    "highsec_jumps": 5,
    "lowsec_jumps": 3,
    "nullsec_jumps": 1,
    "lowest_security": -0.2,
    "lowest_security_system": "X-7OMU"
  },
  "chokepoints": [
    {"name": "Tama", "security": 0.3, ...},
    {"name": "Nourv", "security": 0.3, ...}
  ],
  "danger_zones": [
    {
      "start_system": "Tama",
      "end_system": "Nourv",
      "jump_count": 4,
      "min_security": -0.2
    }
  ],
  "safest_alternative": null
}
```

## Acceptance Criteria

1. [x] Tool registered and callable via MCP
2. [x] Route validation catches disconnected systems
3. [x] Security summary correctly counts all classes
4. [x] Chokepoints identify all security transitions
5. [x] Danger zones correctly identify consecutive low/null
6. [x] Unknown systems raise helpful errors
7. [x] Response time < 2ms for typical queries

## Test Requirements

```python
# tests/mcp/test_tools_analyze.py

@pytest.mark.asyncio
async def test_analyze_safe_route(mock_server):
    """Safe route has no danger zones."""
    result = await mock_server.call_tool(
        "universe_analyze",
        systems=["Jita", "Perimeter", "Urlen"]
    )
    assert result["security_summary"]["lowsec_jumps"] == 0
    assert len(result["danger_zones"]) == 0
    assert len(result["chokepoints"]) == 0


@pytest.mark.asyncio
async def test_analyze_dangerous_route(mock_server):
    """Dangerous route identifies chokepoints and zones."""
    # Need test data with known dangerous route
    result = await mock_server.call_tool(
        "universe_analyze",
        systems=["HighSec", "LowSec1", "LowSec2", "HighSec"]
    )
    assert len(result["chokepoints"]) >= 2  # Entry and exit
    assert len(result["danger_zones"]) >= 1


@pytest.mark.asyncio
async def test_analyze_disconnected_systems(mock_server):
    """Disconnected systems raise error."""
    with pytest.raises(RouteNotFoundError):
        await mock_server.call_tool(
            "universe_analyze",
            systems=["Jita", "Amarr"]  # Not adjacent
        )


@pytest.mark.asyncio
async def test_analyze_unknown_system(mock_server):
    """Unknown system raises helpful error."""
    with pytest.raises(InvalidParameterError) as exc:
        await mock_server.call_tool(
            "universe_analyze",
            systems=["Jita", "UnknownSystem"]
        )
    assert "Unknown system" in str(exc.value)


@pytest.mark.asyncio
async def test_analyze_single_system(mock_server):
    """Single system raises error."""
    with pytest.raises(InvalidParameterError):
        await mock_server.call_tool(
            "universe_analyze",
            systems=["Jita"]
        )


@pytest.mark.asyncio
async def test_analyze_security_summary(mock_server):
    """Security summary counts correctly."""
    result = await mock_server.call_tool(
        "universe_analyze",
        systems=["Jita", "Perimeter", "Urlen"]
    )
    summary = result["security_summary"]
    total = summary["highsec_jumps"] + summary["lowsec_jumps"] + summary["nullsec_jumps"]
    assert total == len(result["systems"])
```

## Estimated Effort

- Implementation: Medium
- Testing: Small
- Total: Medium

## Notes

- Chokepoints are where gatecamps typically occur
- Danger zones help capsuleers plan defensive measures
- Could add safest_alternative by calling route tool with "safe" mode
- Consider adding pipe detection (systems with only 2 gates)
