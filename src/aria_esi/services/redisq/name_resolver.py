"""
Name Resolution for Killmail Notifications.

Resolves EVE Online IDs to human-readable names for display:
- System IDs → System names (via universe graph)
- Type IDs → Type names (via SDE database)
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from ...core.logging import get_logger

if TYPE_CHECKING:
    from ...universe.graph import UniverseGraph

logger = get_logger(__name__)


class NameResolver:
    """
    Resolves EVE IDs to display names.

    Uses in-memory universe graph for systems and SDE database for types.
    Includes LRU caching for type lookups to minimize DB queries.
    """

    def __init__(self, graph: UniverseGraph | None = None):
        """
        Initialize resolver.

        Args:
            graph: Optional pre-loaded universe graph.
                   If None, will load on first system lookup.
        """
        self._graph = graph
        self._graph_loaded = graph is not None

    def _ensure_graph(self) -> UniverseGraph | None:
        """Lazy-load universe graph if not already loaded."""
        if not self._graph_loaded:
            try:
                from ...universe import load_universe_graph

                self._graph = load_universe_graph()
                self._graph_loaded = True
                logger.debug("Universe graph loaded for name resolution")
            except Exception as e:
                logger.warning("Failed to load universe graph: %s", e)
                self._graph = None
                self._graph_loaded = True  # Don't retry on failure
        return self._graph

    def resolve_system_name(self, system_id: int) -> str | None:
        """
        Resolve system ID to name.

        Args:
            system_id: EVE system ID

        Returns:
            System name if found, None otherwise
        """
        graph = self._ensure_graph()
        if graph is None:
            return None

        idx = graph.id_to_idx.get(system_id)
        if idx is not None:
            return graph.idx_to_name.get(idx)
        return None

    def resolve_type_name(self, type_id: int) -> str | None:
        """
        Resolve type ID to name.

        Args:
            type_id: EVE type ID

        Returns:
            Type name if found, None otherwise
        """
        return _resolve_type_name_cached(type_id)

    def resolve_system_with_fallback(self, system_id: int) -> str:
        """
        Resolve system ID to name with fallback.

        Args:
            system_id: EVE system ID

        Returns:
            System name or "System {id}" fallback
        """
        name = self.resolve_system_name(system_id)
        return name if name else f"System {system_id}"

    def resolve_type_with_fallback(self, type_id: int | None) -> str:
        """
        Resolve type ID to name with fallback.

        Args:
            type_id: EVE type ID or None

        Returns:
            Type name, "Unknown", or "Ship {id}" fallback
        """
        if type_id is None:
            return "Unknown"
        name = self.resolve_type_name(type_id)
        return name if name else f"Ship {type_id}"


@lru_cache(maxsize=1024)
def _resolve_type_name_cached(type_id: int) -> str | None:
    """
    Cached type ID to name resolution via SDE.

    Uses LRU cache to avoid repeated DB queries for common types.
    """
    try:
        from ...mcp.market.database import get_market_database

        db = get_market_database()
        conn = db._get_connection()
        cursor = conn.execute(
            "SELECT type_name FROM types WHERE type_id = ?",
            (type_id,),
        )
        row = cursor.fetchone()
        if row:
            return row[0]
    except Exception as e:
        logger.debug("Failed to resolve type %d: %s", type_id, e)
    return None


# Module-level singleton for shared access
_resolver: NameResolver | None = None


def get_name_resolver() -> NameResolver:
    """
    Get or create the name resolver singleton.

    Returns:
        NameResolver instance
    """
    global _resolver
    if _resolver is None:
        _resolver = NameResolver()
    return _resolver


def reset_name_resolver() -> None:
    """Reset the name resolver singleton (for testing)."""
    global _resolver
    _resolver = None
    _resolve_type_name_cached.cache_clear()
