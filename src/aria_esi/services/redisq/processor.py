"""
Kill Processing and Filtering.

Parses ESI killmail responses and filters based on configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from ...core.logging import get_logger
from .models import ProcessedKill

if TYPE_CHECKING:
    from .entity_filter import EntityAwareFilter, EntityMatchResult

logger = get_logger(__name__)

# Pod ship type IDs (Capsule and Capsule - Genolution 'Auroral' 197-variant)
POD_TYPE_IDS = {670, 33328}


def is_pod_kill(ship_type_id: int | None) -> bool:
    """
    Check if a ship type ID is a pod.

    Args:
        ship_type_id: Ship type ID to check

    Returns:
        True if this is a pod kill
    """
    return ship_type_id in POD_TYPE_IDS if ship_type_id else False


def parse_esi_killmail(esi_data: dict[str, Any], zkb_data: dict[str, Any]) -> ProcessedKill:
    """
    Parse ESI killmail response into ProcessedKill.

    Args:
        esi_data: Full killmail data from ESI /killmails/{id}/{hash}/
        zkb_data: zKillboard metadata from RedisQ package

    Returns:
        ProcessedKill with extracted data
    """
    # Parse kill time
    kill_time_str = esi_data.get("killmail_time", "")
    try:
        # ESI returns ISO format: 2024-01-15T12:34:56Z
        kill_time = datetime.fromisoformat(kill_time_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        kill_time = datetime.utcnow()

    # Extract victim data
    victim = esi_data.get("victim", {})
    victim_ship_type_id = victim.get("ship_type_id")
    victim_corporation_id = victim.get("corporation_id")
    victim_alliance_id = victim.get("alliance_id")

    # Extract attacker data
    attackers = esi_data.get("attackers", [])
    attacker_count = len(attackers)

    attacker_corps: list[int] = []
    attacker_alliances: list[int] = []
    attacker_ship_types: list[int] = []
    final_blow_ship_type_id: int | None = None

    for attacker in attackers:
        corp_id = attacker.get("corporation_id")
        alliance_id = attacker.get("alliance_id")
        ship_type_id = attacker.get("ship_type_id")

        if corp_id and corp_id not in attacker_corps:
            attacker_corps.append(corp_id)
        if alliance_id and alliance_id not in attacker_alliances:
            attacker_alliances.append(alliance_id)
        if ship_type_id and ship_type_id not in attacker_ship_types:
            attacker_ship_types.append(ship_type_id)

        # Find final blow dealer's ship
        if attacker.get("final_blow"):
            final_blow_ship_type_id = ship_type_id

    # Get total value from zKillboard (ESI doesn't provide this)
    total_value = zkb_data.get("totalValue", 0.0)

    return ProcessedKill(
        kill_id=esi_data.get("killmail_id", 0),
        kill_time=kill_time.replace(tzinfo=None),  # Store as naive UTC
        solar_system_id=esi_data.get("solar_system_id", 0),
        victim_ship_type_id=victim_ship_type_id,
        victim_corporation_id=victim_corporation_id,
        victim_alliance_id=victim_alliance_id,
        attacker_count=attacker_count,
        attacker_corps=attacker_corps,
        attacker_alliances=attacker_alliances,
        attacker_ship_types=attacker_ship_types,
        final_blow_ship_type_id=final_blow_ship_type_id,
        total_value=total_value,
        is_pod_kill=is_pod_kill(victim_ship_type_id),
    )


@dataclass
class KillFilter:
    """
    Filter for determining which kills to process.

    Filters are applied post-fetch since RedisQ doesn't support
    server-side filtering.
    """

    regions: set[int] = field(default_factory=set)
    min_value: int = 0

    # Optional entity filter for flagging watched entities
    entity_filter: EntityAwareFilter | None = None

    # System ID to region ID mapping (loaded lazily)
    _system_regions: dict[int, int] = field(default_factory=dict, repr=False)

    def should_process(self, kill: ProcessedKill) -> bool:
        """
        Check if a kill should be processed based on filters.

        Args:
            kill: ProcessedKill to evaluate

        Returns:
            True if kill passes all filters
        """
        # Value filter
        if self.min_value > 0 and kill.total_value < self.min_value:
            return False

        # Region filter (if specified)
        if self.regions:
            region_id = self._get_region_for_system(kill.solar_system_id)
            if region_id and region_id not in self.regions:
                return False

        return True

    def _get_region_for_system(self, system_id: int) -> int | None:
        """
        Get region ID for a system.

        Uses cached mapping or looks up via SDE.

        Args:
            system_id: Solar system ID

        Returns:
            Region ID or None if not found
        """
        if system_id in self._system_regions:
            return self._system_regions[system_id]

        # Try to look up from universe graph if available
        try:
            from ...mcp.universe.graph import UniverseGraph

            graph = UniverseGraph.load()
            if system_id in graph.systems:
                region_id = graph.systems[system_id].region_id
                self._system_regions[system_id] = region_id
                return region_id
        except Exception:
            pass

        return None

    def process_kill(self, kill: ProcessedKill) -> tuple[bool, EntityMatchResult | None]:
        """
        Process a kill through filters and entity checking.

        Args:
            kill: ProcessedKill to process

        Returns:
            Tuple of (should_store, entity_match_result)
            - should_store: True if kill passes filters and should be saved
            - entity_match_result: EntityMatchResult if entity filter active, else None
        """
        # Apply standard filters first
        if not self.should_process(kill):
            return False, None

        # Check entity filter if active
        entity_match = None
        if self.entity_filter is not None:
            entity_match = self.entity_filter.check_kill(kill)

        return True, entity_match

    def get_filter_summary(self) -> dict:
        """
        Get a summary of active filters.

        Returns:
            Dict describing active filters
        """
        summary: dict[str, list[int] | str | int | dict[str, bool | int]] = {
            "regions": list(self.regions) if self.regions else "all",
            "min_value_isk": self.min_value if self.min_value > 0 else "none",
        }

        if self.entity_filter is not None:
            summary["entity_tracking"] = {
                "active": self.entity_filter.is_active,
                "watched_corps": self.entity_filter.watched_corp_count,
                "watched_alliances": self.entity_filter.watched_alliance_count,
            }
        else:
            summary["entity_tracking"] = "disabled"

        return summary


def create_filter_from_config(config: Any) -> KillFilter:
    """
    Create a KillFilter from RedisQConfig.

    Args:
        config: RedisQConfig instance

    Returns:
        Configured KillFilter
    """
    return KillFilter(
        regions=set(config.filter_regions) if config.filter_regions else set(),
        min_value=config.min_value_isk,
    )
