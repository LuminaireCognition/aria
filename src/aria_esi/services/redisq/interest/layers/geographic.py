"""
Geographic Interest Layer.

Calculates interest based on distance from operational systems.
Supports system classification (home/hunting/transit) with different
expansion radii and decay weights.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from .....core.logging import get_logger
from ..models import LayerScore
from .base import BaseLayer

if TYPE_CHECKING:
    from .....universe.graph import UniverseGraph

logger = get_logger(__name__)


# =============================================================================
# System Classification
# =============================================================================


class SystemClassification(str, Enum):
    """Classification of operational systems."""

    HOME = "home"  # Staging/HQ - full 3-hop expansion
    HUNTING = "hunting"  # Active roaming areas - 2-hop expansion
    TRANSIT = "transit"  # Passing through - 1-hop expansion


# Default hop weights per classification
DEFAULT_HOME_WEIGHTS: dict[int, float] = {
    0: 1.0,  # Home system itself
    1: 0.95,  # Immediate neighbors
    2: 0.8,  # 2-hop
    3: 0.5,  # 3-hop
}

DEFAULT_HUNTING_WEIGHTS: dict[int, float] = {
    0: 1.0,  # Hunting ground
    1: 0.85,  # Immediate neighbors
    2: 0.5,  # 2-hop
}

DEFAULT_TRANSIT_WEIGHTS: dict[int, float] = {
    0: 0.7,  # Transit point
    1: 0.3,  # Immediate neighbors only
}


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class GeographicSystem:
    """Configuration for a single operational system."""

    name: str
    classification: SystemClassification = SystemClassification.HOME

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GeographicSystem:
        """Create from config dict."""
        return cls(
            name=data["name"],
            classification=SystemClassification(data.get("classification", "home")),
        )


@dataclass
class GeographicConfig:
    """Configuration for the geographic layer."""

    systems: list[GeographicSystem] = field(default_factory=list)

    # Per-classification hop weights
    home_weights: dict[int, float] = field(default_factory=lambda: DEFAULT_HOME_WEIGHTS.copy())
    hunting_weights: dict[int, float] = field(
        default_factory=lambda: DEFAULT_HUNTING_WEIGHTS.copy()
    )
    transit_weights: dict[int, float] = field(
        default_factory=lambda: DEFAULT_TRANSIT_WEIGHTS.copy()
    )

    def get_weights(self, classification: SystemClassification) -> dict[int, float]:
        """Get hop weights for a classification."""
        if classification == SystemClassification.HOME:
            return self.home_weights
        elif classification == SystemClassification.HUNTING:
            return self.hunting_weights
        else:
            return self.transit_weights

    def get_max_hops(self, classification: SystemClassification) -> int:
        """Get maximum expansion hops for a classification."""
        weights = self.get_weights(classification)
        return max(weights.keys()) if weights else 0

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> GeographicConfig:
        """Create from config dict."""
        if not data:
            return cls()

        systems = []
        for sys_data in data.get("systems", []):
            if isinstance(sys_data, str):
                # Simple string format - defaults to home
                systems.append(GeographicSystem(name=sys_data))
            else:
                systems.append(GeographicSystem.from_dict(sys_data))

        return cls(
            systems=systems,
            home_weights=data.get("home_weights", DEFAULT_HOME_WEIGHTS.copy()),
            hunting_weights=data.get("hunting_weights", DEFAULT_HUNTING_WEIGHTS.copy()),
            transit_weights=data.get("transit_weights", DEFAULT_TRANSIT_WEIGHTS.copy()),
        )

    @classmethod
    def from_legacy_config(
        cls,
        operational_systems: list[str],
        interest_weights: dict[str, float] | None = None,
    ) -> GeographicConfig:
        """
        Create from legacy topology configuration.

        Legacy config has a flat list of systems and simple weight keys:
        {"operational": 1.0, "hop_1": 1.0, "hop_2": 0.7}

        All systems are treated as "home" classification.
        """
        systems = [
            GeographicSystem(name=name, classification=SystemClassification.HOME)
            for name in operational_systems
        ]

        # Convert legacy weights to home weights
        if interest_weights:
            home_weights = {
                0: interest_weights.get("operational", 1.0),
                1: interest_weights.get("hop_1", 1.0),
                2: interest_weights.get("hop_2", 0.7),
            }
        else:
            home_weights = DEFAULT_HOME_WEIGHTS.copy()

        return cls(systems=systems, home_weights=home_weights)


# =============================================================================
# Geographic Layer
# =============================================================================


@dataclass
class GeographicLayer(BaseLayer):
    """
    Geographic interest layer using BFS expansion from operational systems.

    Each system classification has different expansion depths:
    - home: 3 hops (full situational awareness)
    - hunting: 2 hops (active engagement areas)
    - transit: 1 hop (passing through)

    Interest scores decay with distance based on classification weights.
    """

    _name: str = "geographic"

    # Pre-computed interest map: system_id -> (interest, classification, from_system)
    _interest_map: dict[int, tuple[float, str, str | None]] = field(default_factory=dict)

    # Configuration used to build this layer
    config: GeographicConfig = field(default_factory=GeographicConfig)

    @property
    def name(self) -> str:
        return self._name

    @property
    def total_systems(self) -> int:
        """Total number of systems in the interest map."""
        return len(self._interest_map)

    def score_system(self, system_id: int) -> LayerScore:
        """
        Score a system based on geographic proximity.

        Args:
            system_id: Solar system ID

        Returns:
            LayerScore with interest and classification info
        """
        if system_id in self._interest_map:
            interest, classification, from_system = self._interest_map[system_id]
            reason = f"{classification}"
            if from_system:
                reason += f" (from {from_system})"
            return LayerScore(layer=self.name, score=interest, reason=reason)

        return LayerScore(layer=self.name, score=0.0, reason=None)

    def get_system_info(self, system_id: int) -> dict[str, Any] | None:
        """
        Get detailed info for a system in the topology.

        Returns:
            Dict with interest, classification, from_system, or None if not tracked
        """
        if system_id not in self._interest_map:
            return None

        interest, classification, from_system = self._interest_map[system_id]
        return {
            "system_id": system_id,
            "interest": interest,
            "classification": classification,
            "from_system": from_system,
        }

    def get_systems_by_classification(
        self, classification: SystemClassification | str
    ) -> list[int]:
        """Get all system IDs with a specific classification."""
        if isinstance(classification, str):
            classification = SystemClassification(classification)

        target = classification.value
        return [system_id for system_id, (_, cls, _) in self._interest_map.items() if cls == target]

    @classmethod
    def from_config(
        cls,
        config: GeographicConfig,
        graph: UniverseGraph,
    ) -> GeographicLayer:
        """
        Build geographic layer from configuration.

        Performs BFS expansion from each operational system based on
        its classification.

        Args:
            config: Geographic configuration
            graph: Universe graph for neighbor lookups

        Returns:
            Configured GeographicLayer with pre-computed interest map
        """
        interest_map: dict[int, tuple[float, str, str | None]] = {}

        for geo_sys in config.systems:
            # Resolve system name to vertex index
            idx = graph.resolve_name(geo_sys.name)
            if idx is None:
                logger.warning("Unknown system in geographic config: %s", geo_sys.name)
                continue

            weights = config.get_weights(geo_sys.classification)
            max_hops = config.get_max_hops(geo_sys.classification)

            # BFS expansion
            cls._expand_from_system(
                interest_map=interest_map,
                graph=graph,
                start_idx=idx,
                start_name=geo_sys.name,
                classification=geo_sys.classification.value,
                weights=weights,
                max_hops=max_hops,
            )

        logger.info(
            "Built geographic layer: %d systems tracked from %d operational systems",
            len(interest_map),
            len(config.systems),
        )

        return cls(_interest_map=interest_map, config=config)

    @classmethod
    def from_legacy_config(
        cls,
        operational_systems: list[str],
        interest_weights: dict[str, float] | None,
        graph: UniverseGraph,
    ) -> GeographicLayer:
        """
        Build from legacy topology configuration.

        Provides backward compatibility with existing configs.

        Args:
            operational_systems: List of system names
            interest_weights: Legacy weight dict
            graph: Universe graph

        Returns:
            Configured GeographicLayer
        """
        config = GeographicConfig.from_legacy_config(
            operational_systems=operational_systems,
            interest_weights=interest_weights,
        )
        return cls.from_config(config, graph)

    @staticmethod
    def _expand_from_system(
        interest_map: dict[int, tuple[float, str, str | None]],
        graph: UniverseGraph,
        start_idx: int,
        start_name: str,
        classification: str,
        weights: dict[int, float],
        max_hops: int,
    ) -> None:
        """
        BFS expansion from a single system.

        Updates interest_map in place. If a system already has higher
        interest from another source, it's preserved.
        """
        # BFS queue: (vertex_idx, hop_level, from_system_name)
        from collections import deque

        visited: set[int] = set()
        queue: deque[tuple[int, int, str | None]] = deque()

        # Start with the operational system itself
        queue.append((start_idx, 0, None))

        while queue:
            idx, hop_level, from_system = queue.popleft()

            if idx in visited:
                continue
            if hop_level > max_hops:
                continue
            if hop_level not in weights:
                continue

            visited.add(idx)

            system_id = graph.get_system_id(idx)
            interest = weights[hop_level]

            # Only update if this is higher interest than existing
            existing = interest_map.get(system_id)
            if existing is None or existing[0] < interest:
                # For hop 0, from_system is None (it IS the operational system)
                # For hop 1+, from_system is the previous system name
                actual_from = from_system if hop_level > 0 else None
                interest_map[system_id] = (interest, classification, actual_from)

            # Queue neighbors for next hop
            if hop_level < max_hops:
                current_name = graph.idx_to_name.get(idx, start_name)
                for neighbor_idx in graph.graph.neighbors(idx):
                    if neighbor_idx not in visited:
                        queue.append((neighbor_idx, hop_level + 1, current_name))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for caching."""
        return {
            "name": self.name,
            "systems": {
                str(system_id): {
                    "interest": interest,
                    "classification": classification,
                    "from_system": from_system,
                }
                for system_id, (interest, classification, from_system) in self._interest_map.items()
            },
            "config": {
                "systems": [
                    {"name": s.name, "classification": s.classification.value}
                    for s in self.config.systems
                ],
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GeographicLayer:
        """Deserialize from dictionary."""
        interest_map = {}
        for system_id_str, sys_data in data.get("systems", {}).items():
            system_id = int(system_id_str)
            interest_map[system_id] = (
                sys_data["interest"],
                sys_data["classification"],
                sys_data.get("from_system"),
            )

        config_data = data.get("config", {})
        config = GeographicConfig.from_dict(config_data)

        return cls(_interest_map=interest_map, config=config)
