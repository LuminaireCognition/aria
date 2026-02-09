"""
Operational Topology for Kill Pre-Filtering.

This module provides system-level interest filtering for the RedisQ poller.

Two modes are supported:
1. Legacy mode: Simple operational_systems + hop expansion (InterestMap)
2. Context-aware mode: Multi-layer interest calculation (InterestCalculator)

Context-aware mode is preferred when configured. It provides:
- Geographic: System proximity with classifications (home/hunting/transit)
- Entity: Corp/alliance involvement (corp member loss = 1.0 always)
- Route: Named travel corridors with ship filtering
- Asset: Corp structures and offices
- Pattern: Activity escalation (gatecamps, spikes)

Kills outside the topology are filtered BEFORE ESI fetch, saving API quota.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ...core.logging import get_logger

if TYPE_CHECKING:
    from ...universe.graph import UniverseGraph
    from .interest import InterestCalculator
    from .models import QueuedKill

logger = get_logger(__name__)

# Cache file location
TOPOLOGY_CACHE_PATH = Path("cache/topology_map.json")

# Well-known special systems
GANK_PIPES = {"Uedama", "Niarja", "Sivala", "Aufay"}
TRADE_HUBS = {"Jita", "Amarr", "Dodixie", "Rens", "Hek"}


# =============================================================================
# Interest Map
# =============================================================================


@dataclass
class SystemInterest:
    """Interest data for a single system."""

    system_id: int
    system_name: str
    interest: float  # 0.0 to 1.0
    hop_level: int  # 0=operational, 1=1-hop, 2=2-hop
    from_system: str | None = None  # Which operational system this is connected to
    is_border: bool = False
    is_gank_pipe: bool = False
    is_trade_hub: bool = False


@dataclass
class InterestMap:
    """
    O(1) lookup structure for system interest scores.

    Provides fast checks for whether a system is in the operational topology
    and what its interest weight is.
    """

    # Core lookup: system_id -> SystemInterest
    systems: dict[int, SystemInterest] = field(default_factory=dict)

    # Metadata
    operational_systems: list[str] = field(default_factory=list)
    interest_weights: dict[str, float] = field(default_factory=dict)
    built_at: float = 0.0
    version: str = "1.0"

    # Route info between operational systems
    routes: dict[str, list[str]] = field(default_factory=dict)

    def get_interest(self, system_id: int) -> float:
        """
        Get interest score for a system.

        Args:
            system_id: Solar system ID

        Returns:
            Interest score (0.0 if not in topology)
        """
        if system_id in self.systems:
            return self.systems[system_id].interest
        return 0.0

    def is_interesting(self, system_id: int) -> bool:
        """
        Check if a system is in the operational topology.

        Args:
            system_id: Solar system ID

        Returns:
            True if system is in topology
        """
        return system_id in self.systems

    def get_system_info(self, system_id: int) -> SystemInterest | None:
        """
        Get full system interest data.

        Args:
            system_id: Solar system ID

        Returns:
            SystemInterest or None if not in topology
        """
        return self.systems.get(system_id)

    @property
    def total_systems(self) -> int:
        """Total number of systems in topology."""
        return len(self.systems)

    def get_systems_by_hop(self, hop_level: int) -> list[SystemInterest]:
        """Get all systems at a specific hop level."""
        return [s for s in self.systems.values() if s.hop_level == hop_level]

    def get_special_systems(self) -> dict[str, list[str]]:
        """Get categorized special systems in topology."""
        result: dict[str, list[str]] = {
            "gank_pipes": [],
            "trade_hubs": [],
            "border_systems": [],
        }
        for s in self.systems.values():
            if s.is_gank_pipe:
                result["gank_pipes"].append(s.system_name)
            if s.is_trade_hub:
                result["trade_hubs"].append(s.system_name)
            if s.is_border:
                result["border_systems"].append(s.system_name)
        return result

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return {
            "version": self.version,
            "built_at": self.built_at,
            "operational_systems": self.operational_systems,
            "interest_weights": self.interest_weights,
            "routes": self.routes,
            "systems": {
                str(system_id): {
                    "system_id": s.system_id,
                    "system_name": s.system_name,
                    "interest": s.interest,
                    "hop_level": s.hop_level,
                    "from_system": s.from_system,
                    "is_border": s.is_border,
                    "is_gank_pipe": s.is_gank_pipe,
                    "is_trade_hub": s.is_trade_hub,
                }
                for system_id, s in self.systems.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InterestMap:
        """Deserialize from dictionary."""
        systems = {}
        for system_id_str, s_data in data.get("systems", {}).items():
            system_id = int(system_id_str)
            systems[system_id] = SystemInterest(
                system_id=s_data["system_id"],
                system_name=s_data["system_name"],
                interest=s_data["interest"],
                hop_level=s_data["hop_level"],
                from_system=s_data.get("from_system"),
                is_border=s_data.get("is_border", False),
                is_gank_pipe=s_data.get("is_gank_pipe", False),
                is_trade_hub=s_data.get("is_trade_hub", False),
            )

        return cls(
            systems=systems,
            operational_systems=data.get("operational_systems", []),
            interest_weights=data.get("interest_weights", {}),
            built_at=data.get("built_at", 0.0),
            version=data.get("version", "1.0"),
            routes=data.get("routes", {}),
        )

    def save(self, path: Path | None = None) -> None:
        """Save to JSON cache file."""
        if path is None:
            path = TOPOLOGY_CACHE_PATH

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.info("Saved topology map to %s", path)

    @classmethod
    def load(cls, path: Path | None = None) -> InterestMap | None:
        """
        Load from JSON cache file.

        Returns:
            InterestMap or None if file doesn't exist
        """
        if path is None:
            path = TOPOLOGY_CACHE_PATH

        if not path.exists():
            return None

        try:
            with open(path) as f:
                data = json.load(f)
            return cls.from_dict(data)
        except (json.JSONDecodeError, OSError, KeyError) as e:
            logger.warning("Failed to load topology map from %s: %s", path, e)
            return None


# =============================================================================
# Topology Builder
# =============================================================================


class TopologyBuilder:
    """
    Builds InterestMap from operational systems using BFS expansion.

    Uses UniverseGraph for neighbor discovery and route calculation.
    """

    def __init__(self, graph: UniverseGraph):
        """
        Initialize builder with universe graph.

        Args:
            graph: UniverseGraph instance for navigation
        """
        self.graph = graph

    def build(
        self,
        operational_systems: list[str],
        interest_weights: dict[str, float] | None = None,
    ) -> InterestMap:
        """
        Build InterestMap from operational systems.

        Args:
            operational_systems: List of system names user operates in
            interest_weights: Optional custom weights (defaults to standard)

        Returns:
            InterestMap with all systems in topology
        """
        if interest_weights is None:
            interest_weights = {
                "operational": 1.0,
                "hop_1": 1.0,
                "hop_2": 0.7,
            }

        systems: dict[int, SystemInterest] = {}

        # Resolve operational systems to vertex indices
        resolved_ops: list[tuple[str, int]] = []
        for name in operational_systems:
            idx = self.graph.resolve_name(name)
            if idx is None:
                logger.warning("Unknown system in topology config: %s", name)
                continue
            resolved_ops.append((name, idx))

        if not resolved_ops:
            logger.warning("No valid operational systems found")
            return InterestMap(
                operational_systems=operational_systems,
                interest_weights=interest_weights,
                built_at=time.time(),
            )

        # Add operational systems (hop 0)
        for name, idx in resolved_ops:
            system_id = self.graph.get_system_id(idx)
            systems[system_id] = SystemInterest(
                system_id=system_id,
                system_name=name,
                interest=interest_weights.get("operational", 1.0),
                hop_level=0,
                from_system=None,
                is_border=self.graph.is_border_system(idx),
                is_gank_pipe=name in GANK_PIPES,
                is_trade_hub=name in TRADE_HUBS,
            )

        # BFS for 1-hop neighbors
        hop_1_indices = set()
        for name, idx in resolved_ops:
            for neighbor_idx in self.graph.graph.neighbors(idx):
                neighbor_id = self.graph.get_system_id(neighbor_idx)
                if neighbor_id not in systems:
                    hop_1_indices.add((neighbor_idx, name))

        for neighbor_idx, from_system in hop_1_indices:
            neighbor_id = self.graph.get_system_id(neighbor_idx)
            neighbor_name = self.graph.idx_to_name[neighbor_idx]
            if neighbor_id not in systems:
                systems[neighbor_id] = SystemInterest(
                    system_id=neighbor_id,
                    system_name=neighbor_name,
                    interest=interest_weights.get("hop_1", 1.0),
                    hop_level=1,
                    from_system=from_system,
                    is_border=self.graph.is_border_system(neighbor_idx),
                    is_gank_pipe=neighbor_name in GANK_PIPES,
                    is_trade_hub=neighbor_name in TRADE_HUBS,
                )

        # BFS for 2-hop neighbors
        hop_2_indices = set()
        for neighbor_idx, _ in hop_1_indices:
            for second_neighbor_idx in self.graph.graph.neighbors(neighbor_idx):
                second_id = self.graph.get_system_id(second_neighbor_idx)
                if second_id not in systems:
                    from_sys = self.graph.idx_to_name[neighbor_idx]
                    hop_2_indices.add((second_neighbor_idx, from_sys))

        for second_idx, from_system in hop_2_indices:
            second_id = self.graph.get_system_id(second_idx)
            second_name = self.graph.idx_to_name[second_idx]
            if second_id not in systems:
                systems[second_id] = SystemInterest(
                    system_id=second_id,
                    system_name=second_name,
                    interest=interest_weights.get("hop_2", 0.7),
                    hop_level=2,
                    from_system=from_system,
                    is_border=self.graph.is_border_system(second_idx),
                    is_gank_pipe=second_name in GANK_PIPES,
                    is_trade_hub=second_name in TRADE_HUBS,
                )

        # Calculate routes between operational systems
        routes = self._calculate_routes(resolved_ops)

        return InterestMap(
            systems=systems,
            operational_systems=operational_systems,
            interest_weights=interest_weights,
            built_at=time.time(),
            routes=routes,
        )

    def _calculate_routes(self, operational_systems: list[tuple[str, int]]) -> dict[str, list[str]]:
        """
        Calculate shortest routes between all pairs of operational systems.

        Returns dict mapping "Origin -> Destination" to list of system names.
        """
        routes = {}

        if len(operational_systems) < 2:
            return routes

        for i, (name1, idx1) in enumerate(operational_systems):
            for name2, idx2 in operational_systems[i + 1 :]:
                # Use igraph's shortest path
                try:
                    path_indices = self.graph.graph.get_shortest_paths(idx1, to=idx2, mode="all")[0]
                    if path_indices:
                        path_names = [self.graph.idx_to_name[p] for p in path_indices]
                        routes[f"{name1} -> {name2}"] = path_names
                except Exception as e:
                    logger.debug("Failed to calculate route %s -> %s: %s", name1, name2, e)

        return routes


# =============================================================================
# Topology Filter
# =============================================================================


@dataclass
class TopologyFilter:
    """
    Pre-filter for the poller that checks kills against the operational topology.

    This filter runs BEFORE ESI fetch to save API quota.

    Supports two modes:
    1. Context-aware mode (InterestCalculator): Multi-layer interest scoring
    2. Legacy mode (InterestMap): Simple hop-based expansion

    Context-aware mode takes priority when configured.
    """

    # Context-aware calculator (preferred when configured)
    calculator: InterestCalculator | None = None

    # Legacy interest map (fallback)
    interest_map: InterestMap | None = None

    # Metrics
    _passed: int = 0
    _filtered: int = 0

    @property
    def is_active(self) -> bool:
        """Check if topology filtering is active."""
        if self.calculator is not None:
            return True
        return self.interest_map is not None and self.interest_map.total_systems > 0

    @property
    def mode(self) -> str:
        """Get current filtering mode."""
        if self.calculator is not None:
            return "context_aware"
        if self.interest_map is not None:
            return "legacy"
        return "disabled"

    def should_fetch(self, queued_kill: QueuedKill) -> bool:
        """
        Check if a kill should be fetched from ESI.

        Args:
            queued_kill: QueuedKill from RedisQ

        Returns:
            True if kill should be fetched, False to filter out
        """
        # Passthrough if not active
        if not self.is_active:
            return True

        # Passthrough if system ID not available (conservative)
        if queued_kill.solar_system_id is None:
            self._passed += 1
            return True

        # Use calculator if available (context-aware mode)
        if self.calculator is not None:
            if self.calculator.should_fetch(queued_kill.solar_system_id):
                self._passed += 1
                return True
            self._filtered += 1
            logger.debug(
                "Context-aware filter: kill %d in system %d filtered (below threshold)",
                queued_kill.kill_id,
                queued_kill.solar_system_id,
            )
            return False

        # Fallback to legacy interest map
        if self.interest_map and self.interest_map.is_interesting(queued_kill.solar_system_id):
            self._passed += 1
            return True

        # Filter out
        self._filtered += 1
        logger.debug(
            "Topology filter: kill %d in system %d filtered (not in operational area)",
            queued_kill.kill_id,
            queued_kill.solar_system_id,
        )
        return False

    def get_metrics(self) -> dict[str, Any]:
        """Get filter metrics."""
        return {
            "passed": self._passed,
            "filtered": self._filtered,
            "total": self._passed + self._filtered,
            "mode": self.mode,
        }

    def reset_metrics(self) -> None:
        """Reset filter metrics."""
        self._passed = 0
        self._filtered = 0

    @classmethod
    def from_config(cls) -> TopologyFilter:
        """
        Create TopologyFilter from config.

        Tries context_topology first, falls back to legacy topology.
        """
        from .interest import ContextAwareTopologyConfig
        from .notifications.config import TopologyConfig

        # Try context-aware topology first
        context_config = ContextAwareTopologyConfig.load()

        if context_config.enabled:
            validation_errors = context_config.validate()
            if validation_errors:
                logger.warning(
                    "Context topology config has errors: %s. Falling back to legacy.",
                    validation_errors,
                )
            else:
                try:
                    calculator = context_config.build_calculator()
                    total_systems = sum(
                        layer.total_systems
                        for layer in calculator.layers
                        if hasattr(layer, "total_systems")
                    )
                    logger.info(
                        "Context-aware topology active: %d layers, ~%d systems tracked",
                        len(calculator.layers),
                        total_systems,
                    )
                    return cls(calculator=calculator)
                except Exception as e:
                    logger.warning(
                        "Failed to build context-aware calculator: %s. Falling back to legacy.",
                        e,
                    )

        # Fall back to legacy topology
        config = TopologyConfig.load()

        if not config.enabled:
            logger.debug("Topology filtering disabled")
            return cls()

        # Try to load cached topology
        interest_map = InterestMap.load()

        if interest_map is None:
            logger.warning(
                "Topology enabled but no topology map found. "
                "Run 'uv run aria-esi topology-build' to generate."
            )
            return cls()

        # Verify the cached topology matches current config
        if set(interest_map.operational_systems) != set(config.operational_systems):
            logger.warning(
                "Cached topology does not match config operational systems. "
                "Run 'uv run aria-esi topology-build' to regenerate."
            )
            # Still use the cached topology, but warn

        logger.info(
            "Legacy topology filter active: %d systems tracked (%d operational, %d hop-1, %d hop-2)",
            interest_map.total_systems,
            len(interest_map.get_systems_by_hop(0)),
            len(interest_map.get_systems_by_hop(1)),
            len(interest_map.get_systems_by_hop(2)),
        )

        return cls(interest_map=interest_map)


# =============================================================================
# Helper Functions
# =============================================================================


def build_topology(
    operational_systems: list[str],
    interest_weights: dict[str, float] | None = None,
    save_cache: bool = True,
) -> InterestMap:
    """
    Build and optionally cache operational topology.

    Args:
        operational_systems: List of system names
        interest_weights: Optional custom weights
        save_cache: Whether to save to cache file

    Returns:
        InterestMap
    """
    from ...universe import load_universe_graph

    graph = load_universe_graph()
    builder = TopologyBuilder(graph)
    interest_map = builder.build(operational_systems, interest_weights)

    if save_cache:
        interest_map.save()

    return interest_map


def get_topology_filter() -> TopologyFilter:
    """Get a topology filter from current config."""
    return TopologyFilter.from_config()
