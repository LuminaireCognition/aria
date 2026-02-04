"""
Shared Utilities for MCP Universe Server Tools.

Provides common functions used across multiple tool implementations.

STP-006: Systems Tool (extracted for sharing)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .errors import InvalidParameterError
from .models import NeighborInfo, SecurityFilter, SystemInfo

if TYPE_CHECKING:
    from ..universe.graph import UniverseGraph


# =============================================================================
# Distance Matrix Optimization
# =============================================================================


@dataclass
class DistanceMatrix:
    """
    Precomputed distance matrix for efficient TSP and route optimization.

    Computes all-pairs shortest paths between a set of waypoints in a single
    operation, then provides O(1) distance lookups and path retrieval.

    Usage:
        matrix = DistanceMatrix.compute(universe, waypoint_indices)
        dist = matrix.distance(0, 3)  # Distance from waypoint 0 to 3
        path = matrix.path(0, 3)      # Full path as vertex indices
    """

    waypoints: list[int]
    _distances: list[list[float]] = field(repr=False)
    _paths: list[list[list[int]]] = field(repr=False)
    _idx_map: dict[int, int] = field(repr=False)

    @classmethod
    def compute(
        cls,
        universe: UniverseGraph,
        waypoints: list[int],
        security_filter: SecurityFilter = "highsec",
        avoid_systems: set[int] | None = None,
    ) -> DistanceMatrix:
        """
        Compute distance matrix for given waypoints.

        Args:
            universe: UniverseGraph for pathfinding
            waypoints: List of vertex indices to include
            security_filter: Security constraint for routing:
                - "highsec": Only high-sec routes (>= 0.45)
                - "lowsec": Allow low-sec, avoid null-sec
                - "any": No security restrictions
            avoid_systems: Set of vertex indices to avoid (infinite weight)

        Returns:
            DistanceMatrix with precomputed distances and paths

        Raises:
            InvalidParameterError: If waypoints contains invalid vertex indices
        """
        g = universe.graph
        vertex_count = g.vcount()

        # Validate waypoint indices are within bounds
        invalid = [v for v in waypoints if v < 0 or v >= vertex_count]
        if invalid:
            raise InvalidParameterError(
                "waypoints",
                invalid,
                f"Vertex indices must be between 0 and {vertex_count - 1}",
            )

        # Compute edge weights based on security_filter and avoid_systems
        weights = compute_filtered_weights(
            universe,
            security_filter=security_filter,
            avoid_systems=avoid_systems,
        )

        # Compute all-pairs shortest paths in one call
        # This is O(V * E * log(V)) total instead of O(n² * V * E * log(V))
        distances: list[list[float]] = []
        paths: list[list[list[int]]] = []

        for src in waypoints:
            # Single call gets distances and paths to ALL targets
            row_paths = g.get_shortest_paths(src, waypoints, weights=weights)
            row_dists = [len(p) - 1 if p else float("inf") for p in row_paths]
            distances.append(row_dists)
            paths.append(row_paths)

        # Build index map: vertex_idx -> matrix position
        idx_map = {v: i for i, v in enumerate(waypoints)}

        return cls(
            waypoints=waypoints,
            _distances=distances,
            _paths=paths,
            _idx_map=idx_map,
        )

    def distance(self, src_idx: int, dst_idx: int) -> float:
        """
        Get precomputed distance between two waypoints.

        Args:
            src_idx: Source vertex index (must be in waypoints)
            dst_idx: Destination vertex index (must be in waypoints)

        Returns:
            Number of jumps, or inf if unreachable
        """
        i = self._idx_map[src_idx]
        j = self._idx_map[dst_idx]
        return self._distances[i][j]

    def path(self, src_idx: int, dst_idx: int) -> list[int]:
        """
        Get precomputed path between two waypoints.

        Args:
            src_idx: Source vertex index (must be in waypoints)
            dst_idx: Destination vertex index (must be in waypoints)

        Returns:
            List of vertex indices forming the path
        """
        i = self._idx_map[src_idx]
        j = self._idx_map[dst_idx]
        return self._paths[i][j]

    def __len__(self) -> int:
        """Number of waypoints in matrix."""
        return len(self.waypoints)


def _compute_safe_weights(universe: UniverseGraph) -> list[float]:
    """
    Compute edge weights that penalize lowsec/nullsec travel.

    Weights:
        - Highsec destination (>= HIGHSEC_THRESHOLD): WEIGHT_NORMAL
        - Lowsec destination (LOWSEC_THRESHOLD to HIGHSEC_THRESHOLD): WEIGHT_LOWSEC_PENALTY
        - Nullsec destination (< LOWSEC_THRESHOLD): WEIGHT_NULLSEC_PENALTY

    Args:
        universe: UniverseGraph with security data

    Returns:
        List of edge weights indexed by edge ID
    """
    weights = []
    for edge in universe.graph.es:
        dst_sec = universe.security[edge.target]
        if dst_sec >= HIGHSEC_THRESHOLD:
            weights.append(WEIGHT_NORMAL)
        elif dst_sec >= LOWSEC_THRESHOLD:
            weights.append(WEIGHT_LOWSEC_PENALTY)
        else:
            weights.append(WEIGHT_NULLSEC_PENALTY)
    return weights


def compute_safe_weights(universe: UniverseGraph) -> list[float]:
    """
    Public API for computing safe edge weights.

    See _compute_safe_weights for details.
    """
    return _compute_safe_weights(universe)


# =============================================================================
# Security Constants
# =============================================================================

# Security status thresholds for classification
# EVE rounds security to one decimal, so 0.45 rounds to 0.5 (high-sec)
HIGHSEC_THRESHOLD = 0.45  # Minimum security for high-sec classification
LOWSEC_THRESHOLD = 0.0  # Boundary between low-sec and null-sec

# Weight constants for security-based routing
WEIGHT_NORMAL = 1.0
WEIGHT_LOWSEC_PENALTY = 100.0
WEIGHT_NULLSEC_PENALTY = 1000.0
WEIGHT_AVOID = float("inf")  # Effectively blocks the edge


def compute_filtered_weights(
    universe: UniverseGraph,
    security_filter: SecurityFilter = "highsec",
    avoid_systems: set[int] | None = None,
) -> list[float] | None:
    """
    Compute edge weights based on security filter and avoided systems.

    This is the unified weight computation function for all routing tools.

    Args:
        universe: UniverseGraph with security data
        security_filter: Security constraint for routing:
            - "highsec": Only high-sec routes (>= 0.45 security)
            - "lowsec": Allow low-sec, avoid null-sec
            - "any": No security restrictions (shortest path)
        avoid_systems: Set of vertex indices to avoid completely

    Returns:
        List of edge weights indexed by edge ID, or None for unweighted
        (only when security_filter="any" and no avoid_systems)
    """
    # Fast path: no constraints at all
    if security_filter == "any" and not avoid_systems:
        return None  # Unweighted shortest path

    g = universe.graph
    security = universe.security
    avoid = avoid_systems or set()
    weights: list[float] = []

    for edge in g.es:
        dst_idx = edge.target

        # Check if destination is in avoid set
        if dst_idx in avoid:
            weights.append(WEIGHT_AVOID)
            continue

        dst_sec = security[dst_idx]

        if security_filter == "highsec":
            # Only allow high-sec, heavy penalty for low/null
            if dst_sec >= HIGHSEC_THRESHOLD:
                weights.append(WEIGHT_NORMAL)
            elif dst_sec >= LOWSEC_THRESHOLD:
                weights.append(WEIGHT_LOWSEC_PENALTY)
            else:
                weights.append(WEIGHT_NULLSEC_PENALTY)

        elif security_filter == "lowsec":
            # Allow high and low-sec, penalize null-sec
            if dst_sec >= LOWSEC_THRESHOLD:
                weights.append(WEIGHT_NORMAL)
            else:
                weights.append(WEIGHT_NULLSEC_PENALTY)

        else:  # security_filter == "any"
            # No security penalty, but still handle avoid_systems
            weights.append(WEIGHT_NORMAL)

    return weights


def get_security_threshold(security_filter: SecurityFilter) -> float:
    """
    Get the minimum security threshold for a security filter.

    Args:
        security_filter: The security filter type

    Returns:
        Minimum security value for traversable systems
    """
    if security_filter == "highsec":
        return HIGHSEC_THRESHOLD
    elif security_filter == "lowsec":
        return LOWSEC_THRESHOLD
    else:  # "any"
        return -1.0  # Allow everything


def build_system_info(universe: UniverseGraph, idx: int) -> SystemInfo:
    """
    Build complete SystemInfo for a vertex.

    This function is shared across tools_route.py and tools_systems.py
    to avoid duplication.

    Args:
        universe: UniverseGraph for system lookups
        idx: Vertex index

    Returns:
        Complete SystemInfo with all fields populated
    """
    neighbors = [
        NeighborInfo(
            name=universe.idx_to_name[n],
            security=float(universe.security[n]),
            security_class=universe.security_class(n),
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
        adjacent_lowsec=universe.get_adjacent_lowsec(idx),
    )
