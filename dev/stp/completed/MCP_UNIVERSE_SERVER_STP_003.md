# STP-003: Graph Builder

**Status:** Draft
**Priority:** P0 - Foundation
**Depends On:** STP-001
**Blocks:** STP-004 (runtime), STP-011 (CLI)

## Objective

Implement the build pipeline that converts `universe_cache.json` into an optimized `universe.pkl` file containing a fully-indexed `UniverseGraph`.

## Scope

### In Scope
- JSON parsing and validation
- igraph construction from stargate data
- NumPy array construction for attributes
- Index computation (name lookups, security sets, border systems)
- Pickle serialization
- Build function with optional output path

### Out of Scope
- CLI commands (STP-011)
- Universe cache generation (existing functionality)
- Graph verification (STP-011)

## File Location

```
aria_esi/universe/builder.py
```

## Implementation

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

### Main Build Function

```python
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

    # Build stable vertex ordering (sorted by system_id)
    system_list = sorted(
        systems.values(),
        key=lambda s: s["system_id"]
    )
    n = len(system_list)

    # Build name indexes
    name_to_idx = {s["name"]: i for i, s in enumerate(system_list)}
    idx_to_name = {i: s["name"] for i, s in enumerate(system_list)}
    name_to_id = {s["name"]: s["system_id"] for s in system_list}
    id_to_idx = {s["system_id"]: i for i, s in enumerate(system_list)}
    name_lookup = {s["name"].lower(): s["name"] for s in system_list}

    # Build edge list from stargates
    edges = _build_edge_list(system_list, stargates, name_to_idx, id_to_idx)

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
    border_systems = _compute_border_systems(g, security, highsec)

    # Region index
    region_systems = _build_region_index(system_list)

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

### Helper Functions

```python
def _build_edge_list(
    system_list: list[dict],
    stargates: dict,
    name_to_idx: dict[str, int],
    id_to_idx: dict[int, int]
) -> set[tuple[int, int]]:
    """Build undirected edge set from stargate data."""
    edges = set()
    for sys in system_list:
        src_idx = name_to_idx[sys["name"]]
        for gate_id in sys.get("stargates", []):
            gate = stargates.get(str(gate_id))
            if gate:
                dest_id = gate["destination_system_id"]
                if dest_id in id_to_idx:
                    dst_idx = id_to_idx[dest_id]
                    # Normalize edge direction for deduplication
                    edge = (min(src_idx, dst_idx), max(src_idx, dst_idx))
                    edges.add(edge)
    return edges


def _compute_border_systems(
    g: ig.Graph,
    security: np.ndarray,
    highsec: frozenset[int]
) -> frozenset[int]:
    """Identify high-sec systems adjacent to low/null-sec."""
    return frozenset(
        v for v in highsec
        if any(g.neighbors(v)) and any(
            security[n] < 0.45 for n in g.neighbors(v)
        )
    )


def _build_region_index(system_list: list[dict]) -> dict[int, list[int]]:
    """Build region_id → [vertex_idx, ...] mapping."""
    region_systems = {}
    for i, sys in enumerate(system_list):
        rid = sys.get("region_id", 0)
        if rid not in region_systems:
            region_systems[rid] = []
        region_systems[rid].append(i)
    return region_systems
```

### Load Function

```python
def load_universe_graph(graph_path: Path) -> UniverseGraph:
    """Load pre-built universe graph from pickle."""
    with open(graph_path, "rb") as f:
        return pickle.load(f)
```

## Data Paths

```python
# Default paths relative to package
DATA_DIR = Path(__file__).parent.parent / "data"
DEFAULT_CACHE_PATH = DATA_DIR / "universe_cache.json"
DEFAULT_GRAPH_PATH = DATA_DIR / "universe.pkl"
```

## Acceptance Criteria

1. [ ] `build_universe_graph()` produces valid UniverseGraph
2. [ ] All systems from cache are indexed
3. [ ] All stargates create bidirectional edges
4. [ ] Border systems correctly identified (high-sec adjacent to low-sec)
5. [ ] Security sets partition all systems
6. [ ] Pickle file is < 2MB (compressed)
7. [ ] Graph loads in < 50ms
8. [ ] Name resolution works after load

## Test Requirements

```python
# tests/universe/test_builder.py

@pytest.fixture
def sample_cache(tmp_path):
    """Create minimal universe cache for testing."""
    cache = {
        "systems": {
            "30000142": {"system_id": 30000142, "name": "Jita", "security_status": 0.9, ...},
            "30002187": {"system_id": 30002187, "name": "Amarr", "security_status": 1.0, ...},
        },
        "stargates": {...},
        "constellations": {...},
        "regions": {...}
    }
    path = tmp_path / "universe_cache.json"
    path.write_text(json.dumps(cache))
    return path


def test_build_creates_valid_graph(sample_cache):
    """Builder produces valid UniverseGraph."""
    universe = build_universe_graph(sample_cache)
    assert universe.system_count > 0
    assert universe.stargate_count > 0


def test_build_saves_to_pickle(sample_cache, tmp_path):
    """Builder saves pickle when output_path provided."""
    output = tmp_path / "universe.pkl"
    build_universe_graph(sample_cache, output)
    assert output.exists()


def test_pickle_roundtrip(sample_cache, tmp_path):
    """Graph survives pickle/unpickle."""
    output = tmp_path / "universe.pkl"
    original = build_universe_graph(sample_cache, output)
    loaded = load_universe_graph(output)
    assert loaded.system_count == original.system_count


def test_load_performance(real_graph_path):
    """Graph loads within latency budget."""
    import time
    start = time.perf_counter()
    load_universe_graph(real_graph_path)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.050  # 50ms budget


def test_border_systems_correct(sample_cache):
    """Border systems correctly identified."""
    universe = build_universe_graph(sample_cache)
    for idx in universe.border_systems:
        # Must be high-sec
        assert universe.security[idx] >= 0.45
        # Must have at least one low/null neighbor
        neighbors = universe.graph.neighbors(idx)
        assert any(universe.security[n] < 0.45 for n in neighbors)
```

## Estimated Effort

- Implementation: Medium
- Testing: Medium
- Total: Medium

## Notes

- Use `pickle.HIGHEST_PROTOCOL` for best performance
- Consider adding lz4 compression for larger graphs
- Edge deduplication uses min/max ordering for undirected edges
- Stable vertex ordering (sorted by system_id) ensures reproducible builds
