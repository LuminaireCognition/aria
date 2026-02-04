"""
Tool Registration Framework for MCP Universe Server.

Provides the infrastructure for registering and implementing MCP tools.
Individual tool implementations will be added in subsequent STPs.

STP-004: MCP Server Core
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .errors import SystemNotFoundError

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from ..universe.graph import UniverseGraph


@dataclass(frozen=True)
class ResolvedSystem:
    """
    Result of system name resolution with optional correction tracking.

    When a typo is auto-corrected, corrected_from contains the original input.
    """

    idx: int
    canonical_name: str
    corrected_from: str | None = None

    @property
    def was_corrected(self) -> bool:
        """True if the input was auto-corrected."""
        return self.corrected_from is not None


# Global reference for tool implementations
_universe: UniverseGraph | None = None


def register_tools(server: FastMCP, universe: UniverseGraph) -> None:
    """
    Register all MCP tools with server using domain dispatchers.

    This consolidates ~45 individual tools into 6 domain dispatchers
    plus 1 unified status tool to reduce LLM attention degradation.

    Dispatchers:
    - universe(): Navigation, routing, borders, activity (14 actions)
    - market(): Prices, orders, arbitrage, scopes (19 actions)
    - sde(): Item info, blueprints, corporations, agents (8 actions)
    - skills(): Training time, easy 80%, activities (9 actions)
    - fitting(): Fit statistics calculation (1 action)
    - status(): Unified status across all domains

    Args:
        server: MCP Server instance
        universe: Loaded UniverseGraph for queries
    """
    global _universe
    _universe = universe

    # Import dispatchers
    from .dispatchers import (
        register_fitting_dispatcher,
        register_market_dispatcher,
        register_sde_dispatcher,
        register_skills_dispatcher,
        register_status_tool,
        register_universe_dispatcher,
    )

    # Register domain dispatchers
    register_universe_dispatcher(server, universe)
    register_market_dispatcher(server, universe)
    register_sde_dispatcher(server, universe)
    register_skills_dispatcher(server, universe)
    register_fitting_dispatcher(server, universe)
    register_status_tool(server)


def get_universe() -> UniverseGraph:
    """
    Get the loaded universe graph for tool implementations.

    Returns:
        UniverseGraph instance

    Raises:
        RuntimeError: If graph has not been loaded
    """
    if _universe is None:
        raise RuntimeError("Universe graph not loaded")
    return _universe


def reset_universe() -> None:
    """
    Reset the universe graph singleton.

    Use for testing to ensure clean state between tests.
    """
    global _universe
    _universe = None


def resolve_system_name(name: str, *, auto_correct: bool = True) -> ResolvedSystem:
    """
    Resolve system name to vertex index with optional auto-correction.

    When auto_correct is True (default) and there's a single high-confidence
    suggestion for an unknown system name, the tool auto-corrects and proceeds
    rather than raising an error. The correction is tracked in the returned
    ResolvedSystem object.

    Args:
        name: System name to resolve (case-insensitive)
        auto_correct: If True, auto-correct typos with single high-confidence match

    Returns:
        ResolvedSystem with idx, canonical_name, and optional corrected_from

    Raises:
        SystemNotFoundError: If system cannot be resolved (and auto_correct fails)
    """
    universe = get_universe()
    idx = universe.resolve_name(name)

    if idx is not None:
        # Exact match (case-insensitive)
        canonical = universe.idx_to_name[idx]
        return ResolvedSystem(idx=idx, canonical_name=canonical)

    # No exact match - try to find suggestions
    suggestions = _find_suggestions(name, universe)

    # Auto-correct if enabled and single high-confidence suggestion
    if auto_correct and len(suggestions) == 1:
        corrected_name = suggestions[0]
        corrected_idx = universe.resolve_name(corrected_name)
        if corrected_idx is not None:
            return ResolvedSystem(
                idx=corrected_idx,
                canonical_name=corrected_name,
                corrected_from=name,
            )

    # Cannot resolve - raise error with suggestions
    raise SystemNotFoundError(name, suggestions)


def collect_corrections(*resolved: ResolvedSystem) -> dict[str, str]:
    """
    Collect corrections from multiple ResolvedSystem objects.

    Args:
        *resolved: ResolvedSystem objects to check for corrections

    Returns:
        Dict mapping original input → canonical name for corrected systems.
        Empty dict if no corrections were made.

    Example:
        >>> origin = resolve_system_name("Kisago")  # Corrects to Kisogo
        >>> dest = resolve_system_name("Jita")      # Exact match
        >>> collect_corrections(origin, dest)
        {"Kisago": "Kisogo"}
    """
    corrections: dict[str, str] = {}
    for r in resolved:
        if r.was_corrected and r.corrected_from is not None:
            corrections[r.corrected_from] = r.canonical_name
    return corrections


def _levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calculate Levenshtein edit distance between two strings.

    Uses O(min(m,n)) space dynamic programming approach.
    """
    if len(s1) < len(s2):
        s1, s2 = s2, s1

    if len(s2) == 0:
        return len(s1)

    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            # Cost is 0 if chars match, 1 otherwise
            cost = 0 if c1 == c2 else 1
            curr_row.append(
                min(
                    prev_row[j + 1] + 1,  # deletion
                    curr_row[j] + 1,  # insertion
                    prev_row[j] + cost,  # substitution
                )
            )
        prev_row = curr_row

    return prev_row[-1]


def _find_suggestions(name: str, universe: UniverseGraph, limit: int = 3) -> list[str]:
    """
    Find similar system names for error suggestions.

    Uses a two-pass approach:
    1. Fast prefix/substring matching (exact character matches)
    2. Fuzzy Levenshtein distance matching for typos (if no prefix matches)

    Args:
        name: The misspelled system name
        universe: UniverseGraph for name lookup
        limit: Maximum suggestions to return

    Returns:
        List of similar system names, sorted by relevance
    """
    name_lower = name.lower()
    prefix_matches: list[str] = []

    # Pass 1: Fast prefix/substring matching
    for canonical_lower, canonical in universe.name_lookup.items():
        if canonical_lower.startswith(name_lower) or name_lower in canonical_lower:
            prefix_matches.append(canonical)
            if len(prefix_matches) >= limit:
                return prefix_matches

    # If we found any prefix matches, return them
    if prefix_matches:
        return prefix_matches

    # Pass 2: Fuzzy matching with Levenshtein distance
    # Only consider names within reasonable edit distance based on input length
    max_distance = max(2, len(name) // 3)  # At least 2, scales with length

    candidates: list[tuple[int, str]] = []
    for canonical_lower, canonical in universe.name_lookup.items():
        # Skip names with very different lengths (optimization)
        if abs(len(canonical_lower) - len(name_lower)) > max_distance:
            continue

        distance = _levenshtein_distance(name_lower, canonical_lower)
        if distance <= max_distance:
            candidates.append((distance, canonical))

    # Sort by distance, then alphabetically for ties
    candidates.sort(key=lambda x: (x[0], x[1]))

    return [name for _, name in candidates[:limit]]
