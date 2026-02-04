"""
Universe module for EVE Online navigation and graph queries.

This module provides the core data structures and algorithms for
navigating New Eden's stargate network.
"""

from aria_esi.universe.builder import (
    DEFAULT_CACHE_PATH,
    DEFAULT_GRAPH_PATH,
    LEGACY_GRAPH_PATH,
    UniverseBuildError,
    build_universe_graph,
    load_universe_graph,
)
from aria_esi.universe.graph import SecurityClass, UniverseGraph
from aria_esi.universe.serialization import SerializationError

__all__ = [
    "UniverseGraph",
    "UniverseBuildError",
    "SerializationError",
    "SecurityClass",
    "build_universe_graph",
    "load_universe_graph",
    "DEFAULT_CACHE_PATH",
    "DEFAULT_GRAPH_PATH",
    "LEGACY_GRAPH_PATH",
]
