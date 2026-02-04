# MCP Universe Server Design Document

**Status:** Draft
**Date:** 2026-01-16
**Based On:** [MCP Universe Server Proposal](MCP_UNIVERSE_SERVER_PROPOSAL.md)

## Overview

This document specifies the technical design for the ARIA Universe MCP Server, a high-performance navigation and universe query service for EVE Online. The server maintains an in-memory graph representation of New Eden's stargate network, enabling sub-millisecond query response times.

## Architecture

### System Context

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Claude Code Session                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐    stdio/JSON-RPC    ┌──────────────────────────┐    │
│  │   Claude     │◄───────────────────►│   aria-universe MCP      │    │
│  │   (LLM)      │                      │   Server (persistent)    │    │
│  └──────────────┘                      └───────────┬──────────────┘    │
│         │                                          │                    │
│         │ Tool calls                               │ In-memory          │
│         ▼                                          ▼                    │
│  ┌──────────────┐                      ┌──────────────────────────┐    │
│  │  ARIA Skills │                      │     UniverseGraph        │    │
│  │  (existing)  │                      │   (igraph + indexes)     │    │
│  └──────────────┘                      └──────────────────────────┘    │
│                                                    ▲                    │
│                                                    │ Loaded once        │
│                                                    │ at startup         │
│                                        ┌──────────────────────────┐    │
│                                        │    universe.pkl          │    │
│                                        │  (pre-built graph)       │    │
│                                        └──────────────────────────┘    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Component Architecture

```
aria_esi/
├── mcp/
│   ├── __init__.py
│   ├── server.py           # MCP server entry point
│   ├── tools.py            # Tool implementations
│   └── models.py           # Pydantic response models
├── universe/
│   ├── __init__.py
│   ├── graph.py            # UniverseGraph class
│   ├── builder.py          # JSON → pickle builder
│   ├── algorithms.py       # Pathfinding algorithms
│   └── indexes.py          # Pre-computed indexes
└── data/
    ├── universe_cache.json # Source (existing)
    └── universe.pkl        # Compiled graph (generated)
```

## Data Model

### UniverseGraph

The core data structure optimized for O(1) lookups and fast graph traversal.

```python
from dataclasses import dataclass, field
from typing import FrozenSet
import igraph as ig
import numpy as np

@dataclass(frozen=False, slots=True)
class UniverseGraph:
    """
    Pre-built graph structure for EVE Online universe navigation.

    Design principles:
    - igraph for C-speed pathfinding (vs Python-native alternatives)
    - NumPy arrays for vectorized attribute access
    - Dict indexes for O(1) name resolution
    - Frozen sets for O(1) membership tests
    """

    # Core graph structure
    graph: ig.Graph

    # Bidirectional name mapping
    name_to_idx: dict[str, int]          # "Jita" → 0
    idx_to_name: dict[int, str]          # 0 → "Jita"
    name_to_id: dict[str, int]           # "Jita" → 30000142
    id_to_idx: dict[int, int]            # 30000142 → 0

    # Vectorized system attributes (indexed by graph vertex)
    security: np.ndarray                  # float32[n_systems]
    system_ids: np.ndarray                # int32[n_systems]
    constellation_ids: np.ndarray         # int32[n_systems]
    region_ids: np.ndarray                # int32[n_systems]

    # Name resolution (case-insensitive)
    name_lookup: dict[str, str]           # "jita" → "Jita"

    # Hierarchy names
    constellation_names: dict[int, str]   # 20000001 → "Kimotoro"
    region_names: dict[int, str]          # 10000002 → "The Forge"

    # Pre-computed indexes
    border_systems: FrozenSet[int]        # High-sec vertices bordering low-sec
    region_systems: dict[int, list[int]]  # region_id → [vertex_idx, ...]
    highsec_systems: FrozenSet[int]       # security >= 0.45
    lowsec_systems: FrozenSet[int]        # 0.0 < security < 0.45
    nullsec_systems: FrozenSet[int]       # security <= 0.0

    # Metadata
    version: str                          # Cache version for invalidation
    system_count: int
    stargate_count: int

    def resolve_name(self, name: str) -> int | None:
        """Resolve system name to vertex index (case-insensitive)."""
        canonical = self.name_lookup.get(name.lower())
        if canonical:
            return self.name_to_idx.get(canonical)
        return None

    def security_class(self, idx: int) -> str:
        """Return security classification for vertex."""
        sec = self.security[idx]
        if sec >= 0.45:
            return "HIGH"
        elif sec > 0.0:
            return "LOW"
        return "NULL"

    def neighbors_with_security(self, idx: int) -> list[tuple[int, float]]:
        """Return neighbors with their security values."""
        return [
            (n, self.security[n])
            for n in self.graph.neighbors(idx)
        ]
```

### Response Models

Pydantic models for type-safe, serializable responses.

```python
from pydantic import BaseModel, Field
from typing import Literal

class NeighborInfo(BaseModel):
    """Adjacent system summary."""
    name: str
    security: float
    security_class: Literal["HIGH", "LOW", "NULL"]

class SystemInfo(BaseModel):
    """Complete system information."""
    name: str
    system_id: int
    security: float = Field(ge=-1.0, le=1.0)
    security_class: Literal["HIGH", "LOW", "NULL"]
    constellation: str
    constellation_id: int
    region: str
    region_id: int
    neighbors: list[NeighborInfo]
    is_border: bool = Field(description="High-sec system adjacent to low-sec")
    adjacent_lowsec: list[str] = Field(default_factory=list)

class SecuritySummary(BaseModel):
    """Route security breakdown."""
    total_jumps: int
    highsec_jumps: int
    lowsec_jumps: int
    nullsec_jumps: int
    lowest_security: float
    lowest_security_system: str

class RouteResult(BaseModel):
    """Complete route with analysis."""
    origin: str
    destination: str
    mode: Literal["shortest", "safe", "unsafe"]
    jumps: int
    systems: list[SystemInfo]
    security_summary: SecuritySummary
    warnings: list[str] = Field(default_factory=list)

class BorderSystem(BaseModel):
    """Border system with distance info."""
    name: str
    system_id: int
    security: float
    jumps_from_origin: int
    adjacent_lowsec: list[str]
    region: str

class LoopResult(BaseModel):
    """Circular route through border systems."""
    systems: list[SystemInfo]
    total_jumps: int
    unique_systems: int
    border_systems_visited: list[BorderSystem]
    backtrack_jumps: int
    efficiency: float = Field(ge=0.0, le=1.0)

class RouteAnalysis(BaseModel):
    """Detailed security analysis of a route."""
    systems: list[SystemInfo]
    security_summary: SecuritySummary
    chokepoints: list[SystemInfo] = Field(description="Low-sec entry/exit points")
    danger_zones: list[tuple[str, str]] = Field(description="Consecutive low/null segments")
    safest_alternative: RouteResult | None = None
```

## MCP Tool Specifications

### Tool Registry

| Tool | Description | Latency Target |
|------|-------------|----------------|
| `universe_route` | Calculate route between systems | <2ms |
| `universe_systems` | Batch system info lookup | <1ms |
| `universe_borders` | Find nearby border systems | <2ms |
| `universe_search` | Filter systems by criteria | <5ms |
| `universe_loop` | Plan circular border route | <20ms |
| `universe_analyze` | Analyze route security | <2ms |

### Tool: `universe_route`

```python
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

    Example:
        universe_route("Jita", "Amarr", mode="safe")
    """
```

**Algorithm:**

```python
def _calculate_route(self, origin_idx: int, dest_idx: int, mode: str) -> list[int]:
    g = self.universe.graph

    if mode == "shortest":
        # Unweighted BFS - O(V + E)
        path = g.get_shortest_paths(origin_idx, dest_idx)[0]

    elif mode == "safe":
        # Weight edges by destination security
        # High-sec → high-sec: weight 1
        # High-sec → low-sec: weight 50 (strong avoidance)
        # Low-sec → low-sec: weight 10
        weights = []
        for edge in g.es:
            src_sec = self.universe.security[edge.source]
            dst_sec = self.universe.security[edge.target]

            if dst_sec >= 0.45:
                weights.append(1)
            elif src_sec >= 0.45:
                weights.append(50)  # Entering low-sec penalty
            else:
                weights.append(10)  # Staying in low-sec

        path = g.get_shortest_paths(origin_idx, dest_idx, weights=weights)[0]

    elif mode == "unsafe":
        # Inverse weighting for hunters
        weights = []
        for edge in g.es:
            dst_sec = self.universe.security[edge.target]
            if dst_sec < 0.45:
                weights.append(1)   # Prefer dangerous space
            else:
                weights.append(10)  # Avoid high-sec

        path = g.get_shortest_paths(origin_idx, dest_idx, weights=weights)[0]

    return path
```

### Tool: `universe_systems`

```python
@server.tool()
async def universe_systems(
    systems: list[str]
) -> dict:
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
```

### Tool: `universe_borders`

```python
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
        limit: Maximum systems to return (default: 10)
        max_jumps: Maximum search radius (default: 15)

    Returns:
        List of BorderSystem objects sorted by distance.

    Example:
        universe_borders("Dodixie", limit=5)
    """
```

**Algorithm:**

```python
def _find_borders(self, origin_idx: int, limit: int, max_jumps: int) -> list[dict]:
    g = self.universe.graph
    borders = []

    # BFS with distance tracking
    visited = {origin_idx: 0}
    queue = deque([(origin_idx, 0)])

    while queue and len(borders) < limit * 2:  # Gather extras for sorting
        vertex, dist = queue.popleft()

        if dist > max_jumps:
            continue

        if vertex in self.universe.border_systems:
            borders.append((vertex, dist))

        for neighbor in g.neighbors(vertex):
            if neighbor not in visited:
                visited[neighbor] = dist + 1
                queue.append((neighbor, dist + 1))

    # Sort by distance, take top N
    borders.sort(key=lambda x: x[1])
    return borders[:limit]
```

### Tool: `universe_search`

```python
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
        region: Filter to specific region name
        is_border: Filter to border systems only
        limit: Maximum results (default: 20, max: 100)

    Returns:
        List of matching SystemInfo objects.

    Example:
        # Find low-sec systems within 10 jumps of Dodixie
        universe_search(
            origin="Dodixie",
            max_jumps=10,
            security_min=0.1,
            security_max=0.4
        )
    """
```

### Tool: `universe_loop`

```python
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
```

**Algorithm:**

```python
def _plan_loop(
    self,
    origin_idx: int,
    target_jumps: int,
    min_borders: int,
    max_borders: int
) -> dict:
    # Step 1: Find candidate borders
    candidates = self._find_borders(origin_idx, limit=max_borders * 3, max_jumps=target_jumps // 2)

    if len(candidates) < min_borders:
        return {"error": f"Only found {len(candidates)} border systems in range"}

    # Step 2: Select diverse subset using greedy algorithm
    # Start with closest, then iteratively add most distant from selected set
    selected = [candidates[0]]
    remaining = candidates[1:]

    while len(selected) < max_borders and remaining:
        # Find candidate maximizing minimum distance to selected set
        best_idx = max(
            range(len(remaining)),
            key=lambda i: min(
                self._jump_distance(remaining[i][0], s[0])
                for s in selected
            )
        )
        selected.append(remaining.pop(best_idx))

    # Step 3: Nearest-neighbor TSP approximation
    tour = self._nearest_neighbor_tsp(origin_idx, [s[0] for s in selected])

    # Step 4: Expand tour to full route
    full_route = []
    for i in range(len(tour)):
        src = tour[i]
        dst = tour[(i + 1) % len(tour)]
        segment = self._calculate_route(src, dst, "shortest")
        full_route.extend(segment[:-1])  # Avoid duplicating waypoints
    full_route.append(origin_idx)  # Close the loop

    return {
        "systems": [self._system_detail(v) for v in full_route],
        "border_systems_visited": [self._border_detail(s[0], s[1]) for s in selected],
        "total_jumps": len(full_route) - 1,
        "unique_systems": len(set(full_route)),
        "backtrack_jumps": len(full_route) - len(set(full_route)),
        "efficiency": len(set(full_route)) / len(full_route)
    }

def _nearest_neighbor_tsp(self, start: int, waypoints: list[int]) -> list[int]:
    """Simple nearest-neighbor TSP heuristic."""
    tour = [start]
    unvisited = set(waypoints)

    current = start
    while unvisited:
        nearest = min(unvisited, key=lambda w: self._jump_distance(current, w))
        tour.append(nearest)
        unvisited.remove(nearest)
        current = nearest

    return tour

def _jump_distance(self, src: int, dst: int) -> int:
    """Get shortest path distance between two vertices."""
    return len(self.universe.graph.get_shortest_paths(src, dst)[0]) - 1
```

### Tool: `universe_analyze`

```python
@server.tool()
async def universe_analyze(
    systems: list[str]
) -> dict:
    """
    Analyze security profile of a route or system list.

    Args:
        systems: Ordered list of system names representing a route

    Returns:
        RouteAnalysis with security breakdown, chokepoints, and dangers.

    Example:
        universe_analyze(["Jita", "Perimeter", "Urlen", "Sirppala"])
    """
```

## Graph Builder

### Build Pipeline

```
universe_cache.json ──► builder.py ──► universe.pkl
     (2-5 MB)              │            (~1 MB)
                           │
                           ├─► Parse systems and stargates
                           ├─► Build igraph with edges
                           ├─► Compute numpy attribute arrays
                           ├─► Build name indexes
                           ├─► Pre-compute border systems
                           └─► Pickle and compress
```

### Builder Implementation

```python
# aria_esi/universe/builder.py

import json
import pickle
from pathlib import Path
import igraph as ig
import numpy as np
from .graph import UniverseGraph

def build_universe_graph(
    cache_path: Path,
    output_path: Path | None = None
) -> UniverseGraph:
    """
    Convert universe_cache.json to optimized UniverseGraph.

    Args:
        cache_path: Path to universe_cache.json
        output_path: Optional path to save pickled graph

    Returns:
        UniverseGraph instance ready for queries
    """
    with open(cache_path) as f:
        data = json.load(f)

    systems = data["systems"]
    stargates = data["stargates"]
    constellations = data.get("constellations", {})
    regions = data.get("regions", {})

    # Build stable vertex ordering
    system_list = sorted(
        systems.values(),
        key=lambda s: s["system_id"]
    )
    n = len(system_list)

    # Build indexes
    name_to_idx = {s["name"]: i for i, s in enumerate(system_list)}
    idx_to_name = {i: s["name"] for i, s in enumerate(system_list)}
    name_to_id = {s["name"]: s["system_id"] for s in system_list}
    id_to_idx = {s["system_id"]: i for i, s in enumerate(system_list)}
    name_lookup = {s["name"].lower(): s["name"] for s in system_list}

    # Build edge list from stargates
    edges = set()
    for sys in system_list:
        src_idx = name_to_idx[sys["name"]]
        for gate_id in sys.get("stargates", []):
            gate = stargates.get(str(gate_id))
            if gate:
                dest_id = gate["destination_system_id"]
                if dest_id in id_to_idx:
                    dst_idx = id_to_idx[dest_id]
                    edge = (min(src_idx, dst_idx), max(src_idx, dst_idx))
                    edges.add(edge)

    # Create igraph
    g = ig.Graph(n=n, edges=list(edges), directed=False)

    # Vectorized attributes
    security = np.array(
        [s["security_status"] for s in system_list],
        dtype=np.float32
    )
    system_ids = np.array(
        [s["system_id"] for s in system_list],
        dtype=np.int32
    )
    constellation_ids = np.array(
        [s["constellation_id"] for s in system_list],
        dtype=np.int32
    )
    region_ids = np.array(
        [s.get("region_id", 0) for s in system_list],
        dtype=np.int32
    )

    # Pre-compute security sets
    highsec = frozenset(i for i in range(n) if security[i] >= 0.45)
    lowsec = frozenset(i for i in range(n) if 0.0 < security[i] < 0.45)
    nullsec = frozenset(i for i in range(n) if security[i] <= 0.0)

    # Pre-compute border systems
    border_systems = frozenset(
        v for v in highsec
        if any(g.neighbors(v)) and any(
            security[n] < 0.45 for n in g.neighbors(v)
        )
    )

    # Region index
    region_systems = {}
    for i, sys in enumerate(system_list):
        rid = sys.get("region_id", 0)
        if rid not in region_systems:
            region_systems[rid] = []
        region_systems[rid].append(i)

    # Name lookups for constellations and regions
    constellation_names = {
        int(k): v["name"]
        for k, v in constellations.items()
    }
    region_names = {
        int(k): v["name"]
        for k, v in regions.items()
    }

    universe = UniverseGraph(
        graph=g,
        name_to_idx=name_to_idx,
        idx_to_name=idx_to_name,
        name_to_id=name_to_id,
        id_to_idx=id_to_idx,
        name_lookup=name_lookup,
        security=security,
        system_ids=system_ids,
        constellation_ids=constellation_ids,
        region_ids=region_ids,
        constellation_names=constellation_names,
        region_names=region_names,
        border_systems=border_systems,
        region_systems=region_systems,
        highsec_systems=highsec,
        lowsec_systems=lowsec,
        nullsec_systems=nullsec,
        version=data.get("version", "unknown"),
        system_count=n,
        stargate_count=len(edges)
    )

    if output_path:
        with open(output_path, "wb") as f:
            pickle.dump(universe, f, protocol=pickle.HIGHEST_PROTOCOL)

    return universe
```

### CLI Integration

```bash
# Build/rebuild the graph
uv run aria-esi universe build

# Verify graph integrity
uv run aria-esi universe verify

# Graph statistics
uv run aria-esi universe stats
```

## MCP Server Implementation

### Server Entry Point

```python
# aria_esi/mcp/server.py

import asyncio
import pickle
from pathlib import Path
from mcp.server import Server
from mcp.server.stdio import stdio_server
from ..universe.graph import UniverseGraph
from .tools import register_tools

DEFAULT_GRAPH_PATH = Path(__file__).parent.parent / "data" / "universe.pkl"

class UniverseServer:
    """MCP server for EVE Online universe queries."""

    def __init__(self, graph_path: Path = DEFAULT_GRAPH_PATH):
        self.graph_path = graph_path
        self.universe: UniverseGraph | None = None
        self.server = Server("aria-universe")

    def load_graph(self):
        """Load pre-built universe graph from pickle."""
        with open(self.graph_path, "rb") as f:
            self.universe = pickle.load(f)

    async def run(self):
        """Start MCP server with stdio transport."""
        self.load_graph()
        register_tools(self.server, self.universe)

        async with stdio_server() as (read, write):
            await self.server.run(
                read,
                write,
                self.server.create_initialization_options()
            )

def main():
    """Entry point for MCP server."""
    server = UniverseServer()
    asyncio.run(server.run())

if __name__ == "__main__":
    main()
```

### Error Handling

```python
class UniverseError(Exception):
    """Base exception for universe queries."""
    pass

class SystemNotFoundError(UniverseError):
    """Raised when a system name cannot be resolved."""
    def __init__(self, name: str, suggestions: list[str] = None):
        self.name = name
        self.suggestions = suggestions or []
        super().__init__(f"Unknown system: {name}")

class RouteNotFoundError(UniverseError):
    """Raised when no route exists between systems."""
    def __init__(self, origin: str, destination: str, reason: str = None):
        self.origin = origin
        self.destination = destination
        self.reason = reason
        super().__init__(f"No route from {origin} to {destination}")
```

Error responses follow MCP conventions:

```json
{
  "error": {
    "code": "SYSTEM_NOT_FOUND",
    "message": "Unknown system: Juta",
    "data": {
      "suggestions": ["Jita", "Jatate"]
    }
  }
}
```

## Configuration

### Claude Code MCP Settings

Add to `.claude/settings.local.json`:

```json
{
  "mcpServers": {
    "aria-universe": {
      "command": "uv",
      "args": ["run", "python", "-m", "aria_esi.mcp.server"],
      "cwd": "/Users/jskelton/EveOnline/.claude/scripts"
    }
  }
}
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ARIA_UNIVERSE_GRAPH` | `data/universe.pkl` | Path to pickled graph |
| `ARIA_UNIVERSE_LOG_LEVEL` | `WARNING` | Logging verbosity |

## Testing Strategy

### Unit Tests

```python
# tests/test_universe_graph.py

def test_graph_loading():
    """Graph loads within latency budget."""
    import time
    start = time.perf_counter()
    universe = load_universe_graph()
    elapsed = time.perf_counter() - start
    assert elapsed < 0.050  # 50ms budget

def test_name_resolution():
    """Case-insensitive name lookup works."""
    universe = load_universe_graph()
    assert universe.resolve_name("jita") == universe.resolve_name("JITA")
    assert universe.resolve_name("nonexistent") is None

def test_border_detection():
    """Border systems correctly identified."""
    universe = load_universe_graph()
    # Uedama is a known border system
    uedama_idx = universe.resolve_name("Uedama")
    assert uedama_idx in universe.border_systems

def test_route_calculation():
    """Routes calculate correctly."""
    universe = load_universe_graph()
    jita = universe.resolve_name("Jita")
    amarr = universe.resolve_name("Amarr")

    path = universe.graph.get_shortest_paths(jita, amarr)[0]
    assert len(path) > 0
    assert path[0] == jita
    assert path[-1] == amarr
```

### Integration Tests

```python
# tests/test_mcp_tools.py

@pytest.mark.asyncio
async def test_route_tool():
    """Route tool returns valid response."""
    server = UniverseServer()
    server.load_graph()

    result = await server.tools["universe_route"](
        origin="Jita",
        destination="Amarr",
        mode="shortest"
    )

    assert result["jumps"] > 0
    assert result["systems"][0]["name"] == "Jita"
    assert result["systems"][-1]["name"] == "Amarr"

@pytest.mark.asyncio
async def test_route_latency():
    """Route queries complete within latency budget."""
    server = UniverseServer()
    server.load_graph()

    import time
    start = time.perf_counter()
    await server.tools["universe_route"](
        origin="Jita",
        destination="Amarr",
        mode="shortest"
    )
    elapsed = time.perf_counter() - start

    assert elapsed < 0.002  # 2ms budget
```

### Benchmark Suite

```bash
# Run performance benchmarks
uv run pytest tests/benchmarks/ -v --benchmark-enable
```

## Deployment Checklist

- [ ] Build universe.pkl from current cache: `uv run aria-esi universe build`
- [ ] Run verification: `uv run aria-esi universe verify`
- [ ] Run test suite: `uv run pytest tests/`
- [ ] Add MCP configuration to settings
- [ ] Test MCP connection with Claude Code
- [ ] Update ARIA skills to use MCP tools where beneficial

## Future Enhancements

### Phase 2 Candidates

1. **Jump Bridge Support**: Add alliance jump bridge network as configurable edges
2. **Wormhole Connections**: Temporary edge support for wormhole mapping
3. **Activity Data**: Overlay recent kill data for danger assessment
4. **Pre-computed Trade Routes**: Cache routes between major hubs
5. **Region Subgraphs**: Extract regional graphs for faster local queries

### Performance Optimizations

1. **Edge Caching**: Cache computed route segments for common paths
2. **Parallel BFS**: Use igraph's multi-threaded pathfinding for large queries
3. **Compressed Pickle**: Use lz4 compression for faster graph loading
4. **Memory Mapping**: mmap the pickle for shared memory across processes

## References

- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [igraph Python Documentation](https://python.igraph.org/en/stable/)
- [EVE Universe Data](https://esi.evetech.net/ui/#/Universe)
- [Proposal Document](MCP_UNIVERSE_SERVER_PROPOSAL.md)
