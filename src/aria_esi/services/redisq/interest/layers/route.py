"""
Route Interest Layer.

Calculates interest based on named travel routes.
Systems along defined routes receive interest, with optional
ship type filtering for logistics-specific routes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .....core.logging import get_logger
from ..models import LayerScore
from .base import BaseLayer

if TYPE_CHECKING:
    from .....universe.graph import UniverseGraph
    from ...models import ProcessedKill

logger = get_logger(__name__)


# =============================================================================
# Ship Type Categories
# =============================================================================

# Ship categories for filtering (by group ID)
# These are approximate - actual filtering uses ship_type_id
LOGISTICS_SHIP_TYPES = {
    # Freighters
    20183,  # Charon
    20185,  # Obelisk
    20187,  # Fenrir
    20189,  # Providence
    # Jump Freighters
    28844,  # Rhea
    28846,  # Anshar
    28848,  # Ark
    28850,  # Nomad
    # Deep Space Transports
    12729,  # Bustard
    12733,  # Impel
    12735,  # Occator
    12731,  # Mastodon
    # Blockade Runners
    12745,  # Crane
    12747,  # Prorator
    12753,  # Viator
    12743,  # Prowler
    # Industrials (common)
    648,  # Badger
    649,  # Tayra
    651,  # Hoarder
    652,  # Mammoth
    653,  # Wreathe
    654,  # Sigil
    655,  # Epithal
    656,  # Miasmos
    657,  # Kryos
    658,  # Nereus
    # Orcas
    28606,  # Orca
    # Bowhead
    34328,  # Bowhead
}

# Ship type name to type ID mapping for common ships
SHIP_TYPE_NAME_TO_IDS: dict[str, set[int]] = {
    "freighter": {20183, 20185, 20187, 20189},
    "jump freighter": {28844, 28846, 28848, 28850},
    "dst": {12729, 12733, 12735, 12731},  # Deep Space Transport
    "deep space transport": {12729, 12733, 12735, 12731},
    "blockade runner": {12745, 12747, 12753, 12743},
    "industrial": {648, 649, 651, 652, 653, 654, 655, 656, 657, 658},
    "transport ship": {12729, 12733, 12735, 12731, 12745, 12747, 12753, 12743},
    "orca": {28606},
    "bowhead": {34328},
}


def resolve_ship_filter(filter_names: list[str]) -> set[int]:
    """
    Resolve ship type names to type IDs.

    Args:
        filter_names: List of ship type names or categories

    Returns:
        Set of ship type IDs
    """
    result: set[int] = set()
    for name in filter_names:
        name_lower = name.lower()
        if name_lower in SHIP_TYPE_NAME_TO_IDS:
            result.update(SHIP_TYPE_NAME_TO_IDS[name_lower])
        else:
            logger.warning("Unknown ship filter category: %s", name)
    return result


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class RouteDefinition:
    """Definition of a named route."""

    name: str
    waypoints: list[str]  # System names
    interest: float = 0.95
    ship_filter: list[str] | None = None  # Ship type names
    bidirectional: bool = True

    # Resolved ship type IDs (computed on build)
    _ship_type_ids: set[int] | None = field(default=None, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RouteDefinition:
        """Create from config dict."""
        return cls(
            name=data.get("name", "unnamed"),
            waypoints=data.get("waypoints", []),
            interest=data.get("interest", 0.95),
            ship_filter=data.get("ship_filter"),
            bidirectional=data.get("bidirectional", True),
        )

    def resolve_ship_filter(self) -> set[int] | None:
        """Resolve ship filter names to type IDs."""
        if self.ship_filter is None:
            return None
        if self._ship_type_ids is None:
            self._ship_type_ids = resolve_ship_filter(self.ship_filter)
        return self._ship_type_ids

    def matches_ship(self, ship_type_id: int | None) -> bool:
        """
        Check if a ship matches this route's filter.

        Args:
            ship_type_id: Victim ship type ID

        Returns:
            True if ship matches filter (or no filter configured)
        """
        if self.ship_filter is None:
            return True  # No filter = all ships match
        if ship_type_id is None:
            return False  # Can't match without ship type

        resolved = self.resolve_ship_filter()
        return ship_type_id in resolved if resolved else True


@dataclass
class RouteConfig:
    """Configuration for the route layer."""

    routes: list[RouteDefinition] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> RouteConfig:
        """Create from config dict."""
        if not data:
            return cls()

        routes = []
        for route_data in data.get("routes", []):
            routes.append(RouteDefinition.from_dict(route_data))

        return cls(routes=routes)

    @property
    def is_configured(self) -> bool:
        """Check if any routes are configured."""
        return len(self.routes) > 0


# =============================================================================
# Route Layer
# =============================================================================


@dataclass
class RouteLayer(BaseLayer):
    """
    Route-based interest layer.

    Provides interest for systems along named travel routes.
    Useful for logistics monitoring (e.g., Jita trade route).

    Features:
    - Named routes with multiple waypoints
    - Shortest path calculation between waypoints
    - Optional ship type filtering per route
    - Bidirectional or one-way routes

    Example config:
        routes:
          - name: jita_logistics
            waypoints: [Tama, Nourvukaiken, Jita]
            interest: 0.95
            ship_filter: [Freighter, Industrial]
    """

    _name: str = "route"

    # Pre-computed route data: system_id -> [(route_name, interest, ship_type_ids)]
    _route_systems: dict[int, list[tuple[str, float, set[int] | None]]] = field(
        default_factory=dict
    )

    config: RouteConfig = field(default_factory=RouteConfig)

    @property
    def name(self) -> str:
        return self._name

    @property
    def total_systems(self) -> int:
        """Total number of systems covered by routes."""
        return len(self._route_systems)

    def score_system(self, system_id: int) -> LayerScore:
        """
        Score a system based on route membership.

        Returns highest route interest (ignoring ship filter since
        we don't have kill context).

        Args:
            system_id: Solar system ID

        Returns:
            LayerScore with highest route interest
        """
        if system_id not in self._route_systems:
            return LayerScore(layer=self.name, score=0.0, reason=None)

        routes = self._route_systems[system_id]
        if not routes:
            return LayerScore(layer=self.name, score=0.0, reason=None)

        # Return highest interest route (ship filter is ignored without kill)
        best_route, best_interest, _ = max(routes, key=lambda r: r[1])
        return LayerScore(
            layer=self.name,
            score=best_interest,
            reason=f"on route: {best_route}",
        )

    def score_kill(self, system_id: int, kill: ProcessedKill | None) -> LayerScore:
        """
        Score a kill based on route membership with ship filtering.

        Only returns interest if the victim ship matches the route's
        ship filter (or if no filter is configured).

        Args:
            system_id: Solar system ID
            kill: ProcessedKill with victim ship data

        Returns:
            LayerScore with route interest (if ship matches filter)
        """
        if kill is None:
            return self.score_system(system_id)

        if system_id not in self._route_systems:
            return LayerScore(layer=self.name, score=0.0, reason=None)

        routes = self._route_systems[system_id]
        if not routes:
            return LayerScore(layer=self.name, score=0.0, reason=None)

        # Find highest interest route where ship matches filter
        best_interest = 0.0
        best_route = None

        for route_name, interest, ship_filter in routes:
            # Check ship filter
            if ship_filter is not None:
                if kill.victim_ship_type_id not in ship_filter:
                    continue  # Ship doesn't match this route's filter

            if interest > best_interest:
                best_interest = interest
                best_route = route_name

        if best_route is None:
            return LayerScore(layer=self.name, score=0.0, reason=None)

        return LayerScore(
            layer=self.name,
            score=best_interest,
            reason=f"on route: {best_route}",
        )

    def get_routes_for_system(self, system_id: int) -> list[str]:
        """Get names of routes that include a system."""
        if system_id not in self._route_systems:
            return []
        return [route_name for route_name, _, _ in self._route_systems[system_id]]

    @classmethod
    def from_config(
        cls,
        config: RouteConfig,
        graph: UniverseGraph,
    ) -> RouteLayer:
        """
        Build route layer from configuration.

        Calculates shortest paths between all waypoints for each route.

        Args:
            config: Route configuration
            graph: Universe graph for path calculation

        Returns:
            Configured RouteLayer with pre-computed route systems
        """
        route_systems: dict[int, list[tuple[str, float, set[int] | None]]] = {}

        for route in config.routes:
            if len(route.waypoints) < 2:
                logger.warning(
                    "Route '%s' has fewer than 2 waypoints, skipping",
                    route.name,
                )
                continue

            # Resolve ship filter
            ship_filter = route.resolve_ship_filter()

            # Calculate path between consecutive waypoints
            for i in range(len(route.waypoints) - 1):
                origin = route.waypoints[i]
                dest = route.waypoints[i + 1]

                path_systems = cls._calculate_path(graph, origin, dest)
                if not path_systems:
                    logger.warning(
                        "No path found for route '%s' segment %s -> %s",
                        route.name,
                        origin,
                        dest,
                    )
                    continue

                # Add all systems to route map
                for system_id in path_systems:
                    if system_id not in route_systems:
                        route_systems[system_id] = []
                    route_systems[system_id].append((route.name, route.interest, ship_filter))

        logger.info(
            "Built route layer: %d systems across %d routes",
            len(route_systems),
            len(config.routes),
        )

        return cls(_route_systems=route_systems, config=config)

    @staticmethod
    def _calculate_path(
        graph: UniverseGraph,
        origin: str,
        destination: str,
    ) -> list[int]:
        """
        Calculate shortest path between two systems.

        Args:
            graph: Universe graph
            origin: Origin system name
            destination: Destination system name

        Returns:
            List of system IDs along the path (empty if not found)
        """
        origin_idx = graph.resolve_name(origin)
        dest_idx = graph.resolve_name(destination)

        if origin_idx is None:
            logger.warning("Unknown system in route: %s", origin)
            return []
        if dest_idx is None:
            logger.warning("Unknown system in route: %s", destination)
            return []

        try:
            path_indices = graph.graph.get_shortest_paths(origin_idx, to=dest_idx, mode="all")[0]
            return [graph.get_system_id(idx) for idx in path_indices]
        except Exception as e:
            logger.warning("Failed to calculate path %s -> %s: %s", origin, destination, e)
            return []

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "routes": [
                {
                    "name": r.name,
                    "waypoints": r.waypoints,
                    "interest": r.interest,
                    "ship_filter": r.ship_filter,
                    "bidirectional": r.bidirectional,
                }
                for r in self.config.routes
            ],
            "systems": {
                str(system_id): [
                    {"route": name, "interest": interest} for name, interest, _ in entries
                ]
                for system_id, entries in self._route_systems.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RouteLayer:
        """Deserialize from dictionary."""
        config = RouteConfig.from_dict({"routes": data.get("routes", [])})

        # Rebuild route systems from saved data
        route_systems: dict[int, list[tuple[str, float, set[int] | None]]] = {}
        for system_id_str, entries in data.get("systems", {}).items():
            system_id = int(system_id_str)
            route_systems[system_id] = [
                (e["route"], e["interest"], None)  # Ship filter not saved
                for e in entries
            ]

        return cls(_route_systems=route_systems, config=config)
