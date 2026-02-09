"""
UniverseGraph - Core data structure for EVE Online universe navigation.

This module provides the UniverseGraph dataclass, an in-memory representation
of New Eden's stargate network optimized for O(1) lookups and fast graph traversal.

STP-001: Core Data Model
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import igraph as ig
import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray

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

    Attributes:
        graph: Core igraph structure representing the stargate network
        name_to_idx: Maps system names to vertex indices ("Jita" -> 0)
        idx_to_name: Maps vertex indices to system names (0 -> "Jita")
        name_to_id: Maps system names to EVE system IDs ("Jita" -> 30000142)
        id_to_idx: Maps EVE system IDs to vertex indices (30000142 -> 0)
        security: Array of security status values indexed by vertex
        system_ids: Array of EVE system IDs indexed by vertex
        constellation_ids: Array of constellation IDs indexed by vertex
        region_ids: Array of region IDs indexed by vertex
        name_lookup: Case-insensitive name mapping ("jita" -> "Jita")
        constellation_names: Maps constellation IDs to names
        region_names: Maps region IDs to names
        region_name_lookup: Case-insensitive region name to ID ("the forge" -> 10000002)
        border_systems: Set of high-sec vertices bordering low-sec
        region_systems: Maps region IDs to lists of vertex indices
        highsec_systems: Set of high-sec vertices (security >= 0.45)
        lowsec_systems: Set of low-sec vertices (0.0 < security < 0.45)
        nullsec_systems: Set of null-sec vertices (security <= 0.0)
        version: Cache version for invalidation
        system_count: Total number of systems in the graph
        stargate_count: Total number of stargate connections
    """

    # Core graph structure
    graph: ig.Graph

    # Bidirectional name mapping
    name_to_idx: dict[str, int]
    idx_to_name: dict[int, str]
    name_to_id: dict[str, int]
    id_to_idx: dict[int, int]

    # Vectorized system attributes (indexed by graph vertex)
    security: NDArray[np.float32]
    system_ids: NDArray[np.int32]
    constellation_ids: NDArray[np.int32]
    region_ids: NDArray[np.int32]

    # Name resolution (case-insensitive)
    name_lookup: dict[str, str]

    # Hierarchy names
    constellation_names: dict[int, str]
    region_names: dict[int, str]

    # O(1) region name resolution (case-insensitive)
    region_name_lookup: dict[str, int]

    # Pre-computed indexes
    border_systems: frozenset[int]
    region_systems: dict[int, list[int]]
    highsec_systems: frozenset[int]
    lowsec_systems: frozenset[int]
    nullsec_systems: frozenset[int]

    # Metadata
    version: str
    system_count: int
    stargate_count: int

    def resolve_name(self, name: str) -> int | None:
        """
        Resolve system name to vertex index (case-insensitive).

        Args:
            name: System name to resolve (case-insensitive)

        Returns:
            Vertex index if found, None otherwise
        """
        canonical = self.name_lookup.get(name.lower())
        if canonical:
            return self.name_to_idx.get(canonical)
        return None

    def security_class(self, idx: int) -> SecurityClass:
        """
        Return security classification for vertex.

        Uses EVE Online's standard thresholds:
        - HIGH: security >= 0.45 (rounds to 0.5+)
        - LOW: 0.0 < security < 0.45 (rounds to 0.1-0.4)
        - NULL: security <= 0.0

        Args:
            idx: Vertex index

        Returns:
            Security classification: "HIGH", "LOW", or "NULL"
        """
        sec = self.security[idx]
        if sec >= 0.45:
            return "HIGH"
        elif sec > 0.0:
            return "LOW"
        return "NULL"

    def neighbors_with_security(self, idx: int) -> list[tuple[int, float]]:
        """
        Return neighbors with their security values.

        Args:
            idx: Vertex index

        Returns:
            List of (neighbor_idx, security_value) tuples
        """
        return [(n, float(self.security[n])) for n in self.graph.neighbors(idx)]

    def get_system_id(self, idx: int) -> int:
        """
        Get EVE system ID from vertex index.

        Args:
            idx: Vertex index

        Returns:
            EVE system ID
        """
        return int(self.system_ids[idx])

    def get_region_name(self, idx: int) -> str:
        """
        Get region name for vertex.

        Args:
            idx: Vertex index

        Returns:
            Region name, or "Unknown" if not found
        """
        region_id = int(self.region_ids[idx])
        return self.region_names.get(region_id, "Unknown")

    def get_constellation_name(self, idx: int) -> str:
        """
        Get constellation name for vertex.

        Args:
            idx: Vertex index

        Returns:
            Constellation name, or "Unknown" if not found
        """
        constellation_id = int(self.constellation_ids[idx])
        return self.constellation_names.get(constellation_id, "Unknown")

    def is_border_system(self, idx: int) -> bool:
        """
        Check if vertex is a border system.

        A border system is a high-sec system that has at least one
        neighboring low-sec or null-sec system.

        Args:
            idx: Vertex index

        Returns:
            True if the system is a border system
        """
        return idx in self.border_systems

    def get_adjacent_lowsec(self, idx: int) -> list[str]:
        """
        Get names of adjacent low-sec systems for a border system.

        Args:
            idx: Vertex index

        Returns:
            List of adjacent low-sec system names (empty if not a border system)
        """
        if idx not in self.border_systems:
            return []
        return [self.idx_to_name[n] for n in self.graph.neighbors(idx) if self.security[n] < 0.45]

    def resolve_region(self, name: str) -> int | None:
        """
        Resolve region name to region ID (case-insensitive, O(1)).

        Args:
            name: Region name to resolve (case-insensitive)

        Returns:
            Region ID if found, None otherwise
        """
        return self.region_name_lookup.get(name.lower())

    def to_dict(self) -> dict:
        """
        Convert UniverseGraph to a dictionary for safe serialization.

        The igraph instance is NOT included - it must be serialized separately
        using igraph's native format.

        Note: msgpack doesn't support int keys in dicts, so we convert them
        to strings. NumPy arrays are converted to lists with dtype metadata.

        Returns:
            Dictionary representation suitable for msgpack serialization
        """
        return {
            # Convert int-keyed dicts to string keys for msgpack compatibility
            "name_to_idx": self.name_to_idx,
            "idx_to_name": {str(k): v for k, v in self.idx_to_name.items()},
            "name_to_id": self.name_to_id,
            "id_to_idx": {str(k): v for k, v in self.id_to_idx.items()},
            # NumPy arrays with dtype preservation
            "security": {"dtype": "float32", "data": self.security.tolist()},
            "system_ids": {"dtype": "int32", "data": self.system_ids.tolist()},
            "constellation_ids": {"dtype": "int32", "data": self.constellation_ids.tolist()},
            "region_ids": {"dtype": "int32", "data": self.region_ids.tolist()},
            # String-keyed dicts (already compatible)
            "name_lookup": self.name_lookup,
            # Int-keyed dicts to string keys
            "constellation_names": {str(k): v for k, v in self.constellation_names.items()},
            "region_names": {str(k): v for k, v in self.region_names.items()},
            "region_name_lookup": self.region_name_lookup,
            # Frozensets to sorted lists (for deterministic serialization)
            "border_systems": sorted(self.border_systems),
            "highsec_systems": sorted(self.highsec_systems),
            "lowsec_systems": sorted(self.lowsec_systems),
            "nullsec_systems": sorted(self.nullsec_systems),
            # Region systems: int keys to string keys
            "region_systems": {str(k): v for k, v in self.region_systems.items()},
            # Metadata
            "version": self.version,
            "system_count": self.system_count,
            "stargate_count": self.stargate_count,
        }

    @classmethod
    def from_dict(cls, data: dict, graph: ig.Graph) -> UniverseGraph:
        """
        Reconstruct UniverseGraph from dictionary and igraph instance.

        Args:
            data: Dictionary from to_dict()
            graph: igraph.Graph instance (deserialized separately)

        Returns:
            Reconstructed UniverseGraph instance
        """
        return cls(
            graph=graph,
            # Restore int keys from string keys
            name_to_idx=data["name_to_idx"],
            idx_to_name={int(k): v for k, v in data["idx_to_name"].items()},
            name_to_id=data["name_to_id"],
            id_to_idx={int(k): v for k, v in data["id_to_idx"].items()},
            # Restore NumPy arrays with correct dtype
            security=np.array(data["security"]["data"], dtype=np.float32),
            system_ids=np.array(data["system_ids"]["data"], dtype=np.int32),
            constellation_ids=np.array(data["constellation_ids"]["data"], dtype=np.int32),
            region_ids=np.array(data["region_ids"]["data"], dtype=np.int32),
            # String-keyed dicts (no conversion needed)
            name_lookup=data["name_lookup"],
            # Restore int keys
            constellation_names={int(k): v for k, v in data["constellation_names"].items()},
            region_names={int(k): v for k, v in data["region_names"].items()},
            region_name_lookup=data["region_name_lookup"],
            # Restore frozensets from sorted lists
            border_systems=frozenset(data["border_systems"]),
            highsec_systems=frozenset(data["highsec_systems"]),
            lowsec_systems=frozenset(data["lowsec_systems"]),
            nullsec_systems=frozenset(data["nullsec_systems"]),
            # Restore int keys for region_systems
            region_systems={int(k): v for k, v in data["region_systems"].items()},
            # Metadata
            version=data["version"],
            system_count=data["system_count"],
            stargate_count=data["stargate_count"],
        )
