"""
Notification Trigger Evaluation.

Defines trigger types and logic for evaluating when kills should generate notifications.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from .config import NPCFactionKillConfig, PoliticalEntityKillConfig
from .npc_factions import NPCFactionMapper, NPCFactionTriggerResult
from .political_entities import PoliticalEntityTriggerResult

logger = logging.getLogger(__name__)

# Cache for resolved entity names (entity_type, entity_id) -> name
_entity_name_cache: dict[tuple[str, int], str] = {}

if TYPE_CHECKING:
    from ..entity_filter import EntityMatchResult
    from ..models import ProcessedKill
    from ..threat_cache import GatecampStatus
    from ..war_context import KillWarContext
    from .config import TriggerConfig


class TriggerType(Enum):
    """Types of notification triggers."""

    WATCHLIST_ACTIVITY = "watchlist_activity"
    GATECAMP_DETECTED = "gatecamp_detected"
    HIGH_VALUE = "high_value"
    WAR_ENGAGEMENT = "war_engagement"
    NPC_FACTION_KILL = "npc_faction_kill"
    POLITICAL_ENTITY = "political_entity"  # Player corp/alliance tracking
    INTEREST_V2 = "interest_v2"  # Interest Engine v2 scoring


@dataclass
class TriggerResult:
    """
    Result of trigger evaluation for a kill.

    Contains which triggers matched and relevant context.
    """

    should_notify: bool = False
    trigger_types: list[TriggerType] | None = None
    gatecamp_status: GatecampStatus | None = None
    war_context: KillWarContext | None = None
    npc_faction: NPCFactionTriggerResult | None = None
    political_entity: PoliticalEntityTriggerResult | None = None

    @property
    def primary_trigger(self) -> TriggerType | None:
        """Get the primary (first) trigger type if any."""
        if self.trigger_types:
            return self.trigger_types[0]
        return None

    @property
    def is_war_engagement(self) -> bool:
        """Check if this is a war engagement."""
        return self.war_context is not None and self.war_context.is_war_engagement

    @property
    def is_npc_faction_kill(self) -> bool:
        """Check if this is an NPC faction kill."""
        return self.npc_faction is not None and self.npc_faction.matched

    @property
    def is_political_entity_kill(self) -> bool:
        """Check if this involves a tracked political entity."""
        return self.political_entity is not None and self.political_entity.matched


def evaluate_triggers(
    kill: ProcessedKill,
    entity_match: EntityMatchResult | None,
    gatecamp_status: GatecampStatus | None,
    triggers: TriggerConfig,
    war_context: KillWarContext | None = None,
    npc_faction_mapper: NPCFactionMapper | None = None,
) -> TriggerResult:
    """
    Evaluate all triggers for a kill.

    Args:
        kill: The processed killmail
        entity_match: Entity match result from watchlist filter
        gatecamp_status: Gatecamp detection status for the system
        triggers: Trigger configuration
        war_context: Optional war context for the kill
        npc_faction_mapper: Optional NPC faction mapper for npc_faction_kill trigger

    Returns:
        TriggerResult with matched triggers
    """
    matched_triggers: list[TriggerType] = []
    skip_gatecamp = False
    npc_faction_result: NPCFactionTriggerResult | None = None
    political_entity_result: PoliticalEntityTriggerResult | None = None

    # Check war engagement trigger (evaluated first)
    if war_context and war_context.is_war_engagement:
        if triggers.war_activity:
            matched_triggers.append(TriggerType.WAR_ENGAGEMENT)
        # Optionally suppress gatecamp trigger for war kills
        if triggers.war_suppress_gatecamp:
            skip_gatecamp = True

    # Check watchlist activity trigger
    if triggers.watchlist_activity:
        if entity_match and entity_match.has_match:
            matched_triggers.append(TriggerType.WATCHLIST_ACTIVITY)

    # Check gatecamp detection trigger (unless suppressed by war context)
    if triggers.gatecamp_detected and not skip_gatecamp:
        if gatecamp_status and gatecamp_status.confidence in ("medium", "high"):
            matched_triggers.append(TriggerType.GATECAMP_DETECTED)

    # Check high value trigger
    if kill.total_value >= triggers.high_value_threshold:
        matched_triggers.append(TriggerType.HIGH_VALUE)

    # Check NPC faction kill trigger
    if triggers.npc_faction_kill.enabled and npc_faction_mapper:
        npc_faction_result = _evaluate_npc_faction_kill(
            kill=kill,
            config=triggers.npc_faction_kill,
            mapper=npc_faction_mapper,
        )
        if npc_faction_result and npc_faction_result.matched:
            matched_triggers.append(TriggerType.NPC_FACTION_KILL)

    # Check political entity kill trigger
    if triggers.political_entity.enabled and triggers.political_entity.has_entities:
        political_entity_result = _evaluate_political_entity_kill(
            kill=kill,
            config=triggers.political_entity,
        )
        if political_entity_result and political_entity_result.matched:
            matched_triggers.append(TriggerType.POLITICAL_ENTITY)

    return TriggerResult(
        should_notify=len(matched_triggers) > 0,
        trigger_types=matched_triggers if matched_triggers else None,
        gatecamp_status=gatecamp_status,
        war_context=war_context,
        npc_faction=npc_faction_result,
        political_entity=political_entity_result,
    )


def _evaluate_npc_faction_kill(
    kill: ProcessedKill,
    config: NPCFactionKillConfig,
    mapper: NPCFactionMapper,
) -> NPCFactionTriggerResult | None:
    """
    Evaluate NPC faction kill trigger.

    Args:
        kill: The processed killmail
        config: NPC faction kill configuration
        mapper: NPC faction mapper

    Returns:
        NPCFactionTriggerResult if matched, None otherwise
    """
    # Build set of watched NPC corporation IDs
    watched_corps: set[int] = set()
    for faction in config.factions:
        watched_corps.update(mapper.get_corps_for_faction(faction))

    if not watched_corps:
        return None

    # Check attackers (NPC killed someone)
    if config.as_attacker:
        for attacker_corp_id in kill.attacker_corps:
            if attacker_corp_id in watched_corps:
                attacker_faction = mapper.get_faction_for_corp(attacker_corp_id)
                corp_name = mapper.get_corp_name(attacker_corp_id) or f"Corp {attacker_corp_id}"
                if attacker_faction:
                    return NPCFactionTriggerResult(
                        matched=True,
                        faction=attacker_faction,
                        corporation_id=attacker_corp_id,
                        corporation_name=corp_name,
                        role="attacker",
                    )

    # Check victim (someone killed the NPC)
    if config.as_victim:
        if kill.victim_corporation_id and kill.victim_corporation_id in watched_corps:
            victim_faction = mapper.get_faction_for_corp(kill.victim_corporation_id)
            corp_name = (
                mapper.get_corp_name(kill.victim_corporation_id)
                or f"Corp {kill.victim_corporation_id}"
            )
            if victim_faction:
                return NPCFactionTriggerResult(
                    matched=True,
                    faction=victim_faction,
                    corporation_id=kill.victim_corporation_id,
                    corporation_name=corp_name,
                    role="victim",
                )

    return None


def _resolve_entity_name(entity_type: str, entity_id: int) -> str:
    """
    Resolve entity name from ESI with caching.

    Args:
        entity_type: "corporation" or "alliance"
        entity_id: Entity ID to resolve

    Returns:
        Entity name, or fallback like "Corp 12345" if resolution fails
    """
    import requests  # type: ignore[import-untyped]

    cache_key = (entity_type, entity_id)
    if cache_key in _entity_name_cache:
        return _entity_name_cache[cache_key]

    fallback = f"{'Corp' if entity_type == 'corporation' else 'Alliance'} {entity_id}"

    try:
        if entity_type == "corporation":
            url = f"https://esi.evetech.net/latest/corporations/{entity_id}/"
        elif entity_type == "alliance":
            url = f"https://esi.evetech.net/latest/alliances/{entity_id}/"
        else:
            return fallback

        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        name = data.get("name", fallback)
        _entity_name_cache[cache_key] = name
        return name

    except requests.RequestException as e:
        logger.debug("Failed to resolve %s %d: %s", entity_type, entity_id, e)
        _entity_name_cache[cache_key] = fallback
        return fallback


def _evaluate_political_entity_kill(
    kill: ProcessedKill,
    config: PoliticalEntityKillConfig,
) -> PoliticalEntityTriggerResult | None:
    """
    Evaluate political entity kill trigger.

    Checks if any configured corporations or alliances are involved
    in the kill as attacker or victim.

    Args:
        kill: The processed killmail
        config: Political entity kill configuration

    Returns:
        PoliticalEntityTriggerResult if matched, None otherwise
    """
    # Check minimum value threshold
    if config.min_value > 0 and kill.total_value < config.min_value:
        return None

    # Use resolved IDs if available, otherwise use raw config
    # (Resolution happens during profile loading)
    watched_corps = config._resolved_corp_ids or set(
        c for c in config.corporations if isinstance(c, int)
    )
    watched_alliances = config._resolved_alliance_ids or set(
        a for a in config.alliances if isinstance(a, int)
    )

    if not watched_corps and not watched_alliances:
        return None

    # Check victim
    if config.as_victim:
        # Check victim corporation
        if kill.victim_corporation_id and kill.victim_corporation_id in watched_corps:
            return PoliticalEntityTriggerResult(
                matched=True,
                entity_type="corporation",
                entity_id=kill.victim_corporation_id,
                entity_name=_resolve_entity_name("corporation", kill.victim_corporation_id),
                role="victim",
            )
        # Check victim alliance
        if kill.victim_alliance_id and kill.victim_alliance_id in watched_alliances:
            return PoliticalEntityTriggerResult(
                matched=True,
                entity_type="alliance",
                entity_id=kill.victim_alliance_id,
                entity_name=_resolve_entity_name("alliance", kill.victim_alliance_id),
                role="victim",
            )

    # Check attackers
    if config.as_attacker:
        # Check attacker corporations
        for attacker_corp_id in kill.attacker_corps:
            if attacker_corp_id in watched_corps:
                return PoliticalEntityTriggerResult(
                    matched=True,
                    entity_type="corporation",
                    entity_id=attacker_corp_id,
                    entity_name=_resolve_entity_name("corporation", attacker_corp_id),
                    role="attacker",
                )
        # Check attacker alliances
        for attacker_alliance_id in kill.attacker_alliances:
            if attacker_alliance_id in watched_alliances:
                return PoliticalEntityTriggerResult(
                    matched=True,
                    entity_type="alliance",
                    entity_id=attacker_alliance_id,
                    entity_name=_resolve_entity_name("alliance", attacker_alliance_id),
                    role="attacker",
                )

    return None
