"""
Route Weight Computation.

Provides edge weight computation functions for different routing modes.
These weights control how the pathfinding algorithm selects routes
based on security preferences and system avoidance.

Weight Schemes:
- Shortest: All edges weight 1 (unless avoiding systems)
- Safe: Penalize low-sec entry, penalize null-sec heavily
- Unsafe: Prefer null-sec, acceptable low-sec, avoid high-sec
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...universe.graph import UniverseGraph


# =============================================================================
# Security Thresholds
# =============================================================================

# EVE rounds security to one decimal, so 0.45 rounds to 0.5 (high-sec)
HIGHSEC_THRESHOLD = 0.45  # Minimum security for high-sec classification
LOWSEC_THRESHOLD = 0.0  # Boundary between low-sec and null-sec


# =============================================================================
# Route Weight Constants
# =============================================================================

# Safe mode weights (penalize dangerous space)
WEIGHT_NORMAL = 1.0  # Normal traversal cost
WEIGHT_LOWSEC_ENTRY = 50.0  # Penalty for entering low-sec from high-sec
WEIGHT_LOWSEC_STAY = 10.0  # Penalty for staying in low-sec
WEIGHT_NULLSEC = 100.0  # Strong penalty for null-sec

# Unsafe mode weights (prefer dangerous space for hunters)
WEIGHT_UNSAFE_NULLSEC = 1.0  # Preferred: null-sec
WEIGHT_UNSAFE_LOWSEC = 2.0  # Acceptable: low-sec
WEIGHT_UNSAFE_HIGHSEC = 10.0  # Avoided: high-sec

# System avoidance
WEIGHT_AVOID = float("inf")  # Effectively blocks the edge

# Territory preference (multiplier applied to non-territory edges)
WEIGHT_TERRITORY_PENALTY = 3.0  # Non-territory systems cost 3x more


# =============================================================================
# Weight Computation Functions
# =============================================================================


def compute_avoid_weights(
    universe: UniverseGraph,
    avoid_systems: set[int],
) -> list[float]:
    """
    Compute edge weights that only block avoided systems.

    Used for "shortest" mode with avoid_systems specified.
    All non-avoided edges get weight 1.0.

    Note: The graph is undirected, so edge.source/edge.target are arbitrary.
    We check both endpoints to ensure avoidance works regardless of
    igraph's internal edge direction.

    Args:
        universe: UniverseGraph for edge iteration
        avoid_systems: Set of vertex indices to avoid

    Returns:
        List of edge weights indexed by edge ID
    """
    g = universe.graph
    weights = []

    for edge in g.es:
        if edge.source in avoid_systems or edge.target in avoid_systems:
            weights.append(WEIGHT_AVOID)
        else:
            weights.append(WEIGHT_NORMAL)

    return weights


def _safe_directed_weight(src_sec: float, dst_sec: float) -> float:
    """Compute safe-mode weight for a directed traversal from src to dst."""
    if dst_sec >= HIGHSEC_THRESHOLD:
        return WEIGHT_NORMAL
    elif dst_sec > LOWSEC_THRESHOLD:
        if src_sec >= HIGHSEC_THRESHOLD:
            return WEIGHT_LOWSEC_ENTRY
        return WEIGHT_LOWSEC_STAY
    return WEIGHT_NULLSEC


def compute_safe_weights(
    universe: UniverseGraph,
    avoid_systems: set[int] | None = None,
) -> list[float]:
    """
    Compute edge weights that prefer high-sec routes.

    Weight scheme (per directed traversal):
    - High-sec -> high-sec: WEIGHT_NORMAL (1)
    - High-sec -> low-sec: WEIGHT_LOWSEC_ENTRY (50) - strong avoidance
    - Low-sec -> low-sec: WEIGHT_LOWSEC_STAY (10) - moderate penalty
    - Any -> null-sec: WEIGHT_NULLSEC (100) - very strong penalty
    - Any -> avoided system: WEIGHT_AVOID (infinity)

    Note: The graph is undirected, so edge.source/edge.target are arbitrary.
    We compute the weight for both traversal directions and take the max
    (conservative — penalizes border crossings in both directions).

    Args:
        universe: UniverseGraph with security data
        avoid_systems: Optional set of vertex indices to avoid

    Returns:
        List of edge weights indexed by edge ID
    """
    g = universe.graph
    security = universe.security
    avoid = avoid_systems or set()
    weights = []

    for edge in g.es:
        # Check avoid list first (either endpoint)
        if edge.source in avoid or edge.target in avoid:
            weights.append(WEIGHT_AVOID)
            continue

        sec_a = security[edge.source]
        sec_b = security[edge.target]

        # Compute both directions, take max (conservative for safe routing)
        w_fwd = _safe_directed_weight(sec_a, sec_b)
        w_rev = _safe_directed_weight(sec_b, sec_a)
        weights.append(max(w_fwd, w_rev))

    return weights


def compute_unsafe_weights(
    universe: UniverseGraph,
    avoid_systems: set[int] | None = None,
) -> list[float]:
    """
    Compute edge weights that prefer dangerous space (for hunters).

    Weight scheme:
    - Null-sec edge: WEIGHT_UNSAFE_NULLSEC (1) - preferred
    - Low-sec edge: WEIGHT_UNSAFE_LOWSEC (2) - acceptable
    - High-sec edge: WEIGHT_UNSAFE_HIGHSEC (10) - avoided
    - Avoided system: WEIGHT_AVOID (infinity)

    Note: The graph is undirected, so edge.source/edge.target are arbitrary.
    We check both endpoints and use the most dangerous (lowest sec) to
    classify the edge (optimistic — prefers edges touching dangerous space).

    Args:
        universe: UniverseGraph with security data
        avoid_systems: Optional set of vertex indices to avoid

    Returns:
        List of edge weights indexed by edge ID
    """
    g = universe.graph
    security = universe.security
    avoid = avoid_systems or set()
    weights = []

    for edge in g.es:
        # Check avoid list first (either endpoint)
        if edge.source in avoid or edge.target in avoid:
            weights.append(WEIGHT_AVOID)
            continue

        # Use the most dangerous endpoint to classify this edge
        worst_sec = min(security[edge.source], security[edge.target])

        if worst_sec <= LOWSEC_THRESHOLD:
            weights.append(WEIGHT_UNSAFE_NULLSEC)  # Prefer null-sec
        elif worst_sec < HIGHSEC_THRESHOLD:
            weights.append(WEIGHT_UNSAFE_LOWSEC)  # Low-sec acceptable
        else:
            weights.append(WEIGHT_UNSAFE_HIGHSEC)  # Avoid high-sec

    return weights


def apply_territory_preference(
    weights: list[float],
    universe: UniverseGraph,
    preferred_systems: set[int],
) -> list[float]:
    """
    Apply territory preference to existing edge weights.

    Multiplies weights for edges leading to non-territory systems,
    making the pathfinder prefer routes through territory.

    Args:
        weights: Pre-computed edge weights to modify
        universe: UniverseGraph for edge iteration
        preferred_systems: Set of vertex indices to prefer

    Returns:
        New list of modified edge weights
    """
    g = universe.graph
    result = []

    for i, edge in enumerate(g.es):
        w = weights[i]
        if w == WEIGHT_AVOID:
            result.append(w)
        elif edge.source not in preferred_systems and edge.target not in preferred_systems:
            # Neither endpoint is in preferred territory — penalize
            result.append(w * WEIGHT_TERRITORY_PENALTY)
        else:
            result.append(w)

    return result
