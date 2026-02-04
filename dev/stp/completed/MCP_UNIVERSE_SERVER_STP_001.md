# STP-001: Core Data Model (UniverseGraph)

**Status:** Complete
**Priority:** P0 - Foundation
**Depends On:** None
**Blocks:** STP-003, STP-004, STP-005 through STP-010

## Objective

Implement the `UniverseGraph` dataclass - the core in-memory data structure for EVE Online universe navigation. This provides O(1) lookups and fast graph traversal for all downstream tools.

## Scope

### In Scope
- `UniverseGraph` dataclass with all attributes
- Name resolution methods (case-insensitive)
- Security classification helper
- Neighbor query method
- Type hints and docstrings

### Out of Scope
- Graph construction (STP-003)
- Serialization/deserialization (STP-003)
- MCP integration (STP-004)

## File Location

```
aria_esi/universe/graph.py
aria_esi/universe/__init__.py
```

## Implementation

### UniverseGraph Dataclass

```python
from dataclasses import dataclass
from typing import FrozenSet, Literal
import igraph as ig
import numpy as np

SecurityClass = Literal["HIGH", "LOW", "NULL"]

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
```

### Methods

```python
def resolve_name(self, name: str) -> int | None:
    """Resolve system name to vertex index (case-insensitive)."""
    canonical = self.name_lookup.get(name.lower())
    if canonical:
        return self.name_to_idx.get(canonical)
    return None

def security_class(self, idx: int) -> SecurityClass:
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
        (n, float(self.security[n]))
        for n in self.graph.neighbors(idx)
    ]

def get_system_id(self, idx: int) -> int:
    """Get EVE system ID from vertex index."""
    return int(self.system_ids[idx])

def get_region_name(self, idx: int) -> str:
    """Get region name for vertex."""
    region_id = int(self.region_ids[idx])
    return self.region_names.get(region_id, "Unknown")

def get_constellation_name(self, idx: int) -> str:
    """Get constellation name for vertex."""
    constellation_id = int(self.constellation_ids[idx])
    return self.constellation_names.get(constellation_id, "Unknown")

def is_border_system(self, idx: int) -> bool:
    """Check if vertex is a border system."""
    return idx in self.border_systems

def get_adjacent_lowsec(self, idx: int) -> list[str]:
    """Get names of adjacent low-sec systems for a border system."""
    if idx not in self.border_systems:
        return []
    return [
        self.idx_to_name[n]
        for n in self.graph.neighbors(idx)
        if self.security[n] < 0.45
    ]
```

## Dependencies

```toml
# pyproject.toml additions
[project.dependencies]
igraph = ">=0.11.0"
numpy = ">=1.24.0"
```

## Acceptance Criteria

1. [x] `UniverseGraph` dataclass defined with all attributes
2. [x] All methods implemented with correct type hints
3. [x] `resolve_name()` handles case-insensitive lookups
4. [x] `security_class()` correctly classifies all security levels
5. [x] `neighbors_with_security()` returns accurate neighbor data
6. [x] Module exports `UniverseGraph` from `aria_esi.universe`

## Test Requirements

```python
# tests/universe/test_graph.py

def test_resolve_name_case_insensitive(mock_universe):
    """Name resolution ignores case."""
    assert mock_universe.resolve_name("jita") == mock_universe.resolve_name("JITA")
    assert mock_universe.resolve_name("JiTa") == mock_universe.resolve_name("jita")

def test_resolve_name_unknown_returns_none(mock_universe):
    """Unknown names return None."""
    assert mock_universe.resolve_name("NonexistentSystem") is None

def test_security_class_boundaries(mock_universe):
    """Security classification uses correct thresholds."""
    # Test at boundaries: 0.45, 0.0
    # HIGH: >= 0.45
    # LOW: > 0.0 and < 0.45
    # NULL: <= 0.0

def test_neighbors_returns_valid_data(mock_universe):
    """Neighbor query returns correct format."""
    jita_idx = mock_universe.resolve_name("Jita")
    neighbors = mock_universe.neighbors_with_security(jita_idx)
    assert all(isinstance(n, tuple) and len(n) == 2 for n in neighbors)
    assert all(isinstance(n[0], int) and isinstance(n[1], float) for n in neighbors)
```

## Estimated Effort

- Implementation: Small
- Testing: Small
- Total: Small

## Notes

- Use `slots=True` for memory efficiency with many instances (though we only have one)
- NumPy arrays use specific dtypes for memory optimization
- FrozenSet used for immutable set operations with O(1) membership test
