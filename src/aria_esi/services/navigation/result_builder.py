"""
Route Result Construction.

Utilities for building structured route results with security analysis,
warnings, and metadata. Used by both MCP tools and CLI commands.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from .weights import HIGHSEC_THRESHOLD

if TYPE_CHECKING:
    from ...universe.graph import UniverseGraph


@dataclass
class SecuritySummary:
    """Security breakdown for a route."""

    total_jumps: int
    highsec_jumps: int
    lowsec_jumps: int
    nullsec_jumps: int
    lowest_security: float
    lowest_security_system: str


def compute_security_summary(
    universe: UniverseGraph,
    path: list[int],
) -> SecuritySummary:
    """
    Compute security breakdown for a route.

    Args:
        universe: UniverseGraph for security lookups
        path: List of vertex indices

    Returns:
        SecuritySummary with jump counts by security class and lowest point
    """
    highsec = 0
    lowsec = 0
    nullsec = 0
    lowest_sec = 1.0
    lowest_system = ""

    for idx in path:
        sec = universe.security[idx]
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
        total_jumps=len(path) - 1,
        highsec_jumps=highsec,
        lowsec_jumps=lowsec,
        nullsec_jumps=nullsec,
        lowest_security=float(lowest_sec),
        lowest_security_system=lowest_system,
    )


def generate_warnings(
    universe: UniverseGraph,
    path: list[int],
    mode: str,
) -> list[str]:
    """
    Generate route warnings for dangerous situations.

    Warnings are generated for:
    - Entering low/null-sec from high-sec
    - Pipe systems (single entry/exit) in dangerous space
    - Safe mode routes that still traverse dangerous space

    Args:
        universe: UniverseGraph for security lookups
        path: List of vertex indices
        mode: Routing mode used (shortest, safe, unsafe)

    Returns:
        List of warning strings
    """
    warnings = []

    # Count low/null transitions
    lowsec_entries = 0
    for i in range(len(path) - 1):
        src_class = universe.security_class(path[i])
        dst_class = universe.security_class(path[i + 1])

        if src_class == "HIGH" and dst_class in ("LOW", "NULL"):
            lowsec_entries += 1

    if lowsec_entries > 0:
        warnings.append(f"Route enters low/null-sec {lowsec_entries} time(s)")

    # Check for pipe systems (single entry/exit)
    for idx in path[1:-1]:  # Skip origin and destination
        if len(universe.graph.neighbors(idx)) == 2:
            sec = universe.security[idx]
            if sec < HIGHSEC_THRESHOLD:
                name = universe.idx_to_name[idx]
                warnings.append(f"Pipe system: {name} (potential gatecamp)")
                break  # Only warn once

    if mode == "safe" and any(universe.security[idx] < HIGHSEC_THRESHOLD for idx in path):
        warnings.append("No fully high-sec route available")

    return warnings


def get_threat_level(
    high_sec: int,
    low_sec: int,
    null_sec: int,
    lowest_sec: float,
) -> Literal["MINIMAL", "ELEVATED", "HIGH", "CRITICAL"]:
    """
    Determine threat level based on route composition.

    Args:
        high_sec: Number of high-sec systems in route
        low_sec: Number of low-sec systems in route
        null_sec: Number of null-sec systems in route
        lowest_sec: Lowest security value encountered

    Returns:
        Threat level string: MINIMAL, ELEVATED, HIGH, or CRITICAL
    """
    if null_sec > 0:
        return "CRITICAL"
    elif low_sec > 0:
        return "HIGH"
    elif lowest_sec <= 0.5:
        return "ELEVATED"
    else:
        return "MINIMAL"
