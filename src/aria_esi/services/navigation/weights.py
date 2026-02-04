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

    Args:
        universe: UniverseGraph for edge iteration
        avoid_systems: Set of vertex indices to avoid

    Returns:
        List of edge weights indexed by edge ID
    """
    g = universe.graph
    weights = []

    for edge in g.es:
        if edge.target in avoid_systems:
            weights.append(WEIGHT_AVOID)
        else:
            weights.append(WEIGHT_NORMAL)

    return weights


def compute_safe_weights(
    universe: UniverseGraph,
    avoid_systems: set[int] | None = None,
) -> list[float]:
    """
    Compute edge weights that prefer high-sec routes.

    Weight scheme:
    - High-sec -> high-sec: WEIGHT_NORMAL (1)
    - High-sec -> low-sec: WEIGHT_LOWSEC_ENTRY (50) - strong avoidance
    - Low-sec -> low-sec: WEIGHT_LOWSEC_STAY (10) - moderate penalty
    - Any -> null-sec: WEIGHT_NULLSEC (100) - very strong penalty
    - Any -> avoided system: WEIGHT_AVOID (infinity)

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
        dst_idx = edge.target

        # Check avoid list first
        if dst_idx in avoid:
            weights.append(WEIGHT_AVOID)
            continue

        src_sec = security[edge.source]
        dst_sec = security[dst_idx]

        if dst_sec >= HIGHSEC_THRESHOLD:
            # Destination is high-sec
            weights.append(WEIGHT_NORMAL)
        elif dst_sec > LOWSEC_THRESHOLD:
            # Destination is low-sec
            if src_sec >= HIGHSEC_THRESHOLD:
                weights.append(WEIGHT_LOWSEC_ENTRY)  # Entering low-sec penalty
            else:
                weights.append(WEIGHT_LOWSEC_STAY)  # Staying in low-sec
        else:
            # Destination is null-sec
            weights.append(WEIGHT_NULLSEC)

    return weights


def compute_unsafe_weights(
    universe: UniverseGraph,
    avoid_systems: set[int] | None = None,
) -> list[float]:
    """
    Compute edge weights that prefer dangerous space (for hunters).

    Weight scheme:
    - Any -> null-sec: WEIGHT_UNSAFE_NULLSEC (1) - preferred
    - Any -> low-sec: WEIGHT_UNSAFE_LOWSEC (2) - acceptable
    - Any -> high-sec: WEIGHT_UNSAFE_HIGHSEC (10) - avoided
    - Any -> avoided system: WEIGHT_AVOID (infinity)

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
        dst_idx = edge.target

        # Check avoid list first
        if dst_idx in avoid:
            weights.append(WEIGHT_AVOID)
            continue

        dst_sec = security[dst_idx]

        if dst_sec <= LOWSEC_THRESHOLD:
            weights.append(WEIGHT_UNSAFE_NULLSEC)  # Prefer null-sec
        elif dst_sec < HIGHSEC_THRESHOLD:
            weights.append(WEIGHT_UNSAFE_LOWSEC)  # Low-sec acceptable
        else:
            weights.append(WEIGHT_UNSAFE_HIGHSEC)  # Avoid high-sec

    return weights
