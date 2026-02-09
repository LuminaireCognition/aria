"""
Shared fixtures for notification tests.

Provides factory functions and fixtures for creating test objects
used across the notification test suite.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest


def make_processed_kill(
    kill_id: int = 12345,
    solar_system_id: int = 30000142,
    total_value: int = 100_000_000,
    is_pod_kill: bool = False,
    victim_ship_type_id: int = 587,
    victim_corporation_id: int = 98000001,
    victim_alliance_id: int | None = None,
    attacker_count: int = 5,
    attacker_corps: list[int] | None = None,
    attacker_alliances: list[int] | None = None,
    kill_time: datetime | None = None,
) -> MagicMock:
    """
    Create a mock ProcessedKill for testing.

    Args:
        kill_id: Kill ID
        solar_system_id: System where kill occurred
        total_value: Total ISK value
        is_pod_kill: Whether this is a pod kill
        victim_ship_type_id: Victim ship type ID
        victim_corporation_id: Victim corporation ID
        victim_alliance_id: Victim alliance ID (optional)
        attacker_count: Number of attackers
        attacker_corps: List of attacker corporation IDs
        attacker_alliances: List of attacker alliance IDs
        kill_time: Kill timestamp

    Returns:
        Mock ProcessedKill
    """
    kill = MagicMock()
    kill.kill_id = kill_id
    kill.solar_system_id = solar_system_id
    kill.total_value = total_value
    kill.is_pod_kill = is_pod_kill
    kill.victim_ship_type_id = victim_ship_type_id
    kill.victim_corporation_id = victim_corporation_id
    kill.victim_alliance_id = victim_alliance_id
    kill.attacker_count = attacker_count
    kill.attacker_corps = attacker_corps or [98000002]
    kill.attacker_alliances = attacker_alliances or []
    kill.kill_time = kill_time or datetime.now(tz=timezone.utc)
    return kill


def make_entity_match(
    has_match: bool = False,
    match_types: list[str] | None = None,
) -> MagicMock:
    """
    Create a mock EntityMatchResult for testing.

    Args:
        has_match: Whether an entity match was found
        match_types: Types of matches found

    Returns:
        Mock EntityMatchResult
    """
    match = MagicMock()
    match.has_match = has_match
    match.match_types = match_types or []
    return match


def make_gatecamp_status(
    confidence: str = "none",
    kill_count: int = 0,
    system_id: int = 30000142,
    system_name: str = "Jita",
    is_smartbomb_camp: bool = False,
) -> MagicMock:
    """
    Create a mock GatecampStatus for testing.

    Args:
        confidence: Confidence level ("none", "low", "medium", "high")
        kill_count: Number of kills detected
        system_id: System ID
        system_name: System name
        is_smartbomb_camp: Whether smartbombs were detected

    Returns:
        Mock GatecampStatus
    """
    status = MagicMock()
    status.confidence = confidence
    status.kill_count = kill_count
    status.system_id = system_id
    status.system_name = system_name
    status.is_smartbomb_camp = is_smartbomb_camp
    return status


def make_war_context(
    is_war_engagement: bool = False,
    relationship: MagicMock | None = None,
) -> MagicMock:
    """
    Create a mock KillWarContext for testing.

    Args:
        is_war_engagement: Whether kill is a war engagement
        relationship: Optional war relationship mock

    Returns:
        Mock KillWarContext
    """
    context = MagicMock()
    context.is_war_engagement = is_war_engagement

    if relationship is None and is_war_engagement:
        relationship = MagicMock()
        relationship.is_mutual = False
        relationship.kill_count = 1

    context.relationship = relationship
    return context


def make_npc_faction_result(
    matched: bool = True,
    faction: str = "serpentis",
    corporation_id: int = 1000125,
    corporation_name: str = "Serpentis Corporation",
    role: str = "attacker",
) -> MagicMock:
    """
    Create a mock NPCFactionTriggerResult for testing.

    Args:
        matched: Whether faction matched
        faction: Faction key
        corporation_id: NPC corporation ID
        corporation_name: NPC corporation name
        role: "attacker" or "victim"

    Returns:
        Mock NPCFactionTriggerResult
    """
    result = MagicMock()
    result.matched = matched
    result.faction = faction
    result.corporation_id = corporation_id
    result.corporation_name = corporation_name
    result.role = role
    return result


def make_political_entity_result(
    matched: bool = True,
    entity_type: str = "corporation",
    entity_id: int = 98000001,
    entity_name: str = "Test Corporation",
    role: str = "attacker",
) -> MagicMock:
    """
    Create a mock PoliticalEntityTriggerResult for testing.

    Args:
        matched: Whether entity matched
        entity_type: "corporation" or "alliance"
        entity_id: Entity ID
        entity_name: Entity name
        role: "attacker" or "victim"

    Returns:
        Mock PoliticalEntityTriggerResult
    """
    result = MagicMock()
    result.matched = matched
    result.entity_type = entity_type
    result.entity_id = entity_id
    result.entity_name = entity_name
    result.role = role
    return result


def make_trigger_config(
    watchlist_activity: bool = True,
    gatecamp_detected: bool = True,
    high_value_threshold: int = 1_000_000_000,
    war_activity: bool = False,
    war_suppress_gatecamp: bool = True,
    npc_faction_kill_enabled: bool = False,
    npc_faction_kill_factions: list[str] | None = None,
    political_entity_enabled: bool = False,
    political_entity_corps: list[int] | None = None,
    political_entity_alliances: list[int] | None = None,
) -> Any:
    """
    Create a TriggerConfig for testing.

    Args:
        watchlist_activity: Enable watchlist trigger
        gatecamp_detected: Enable gatecamp trigger
        high_value_threshold: High value threshold
        war_activity: Enable war activity trigger
        war_suppress_gatecamp: Suppress gatecamp for war kills
        npc_faction_kill_enabled: Enable NPC faction trigger
        npc_faction_kill_factions: Factions to watch
        political_entity_enabled: Enable political entity trigger
        political_entity_corps: Corporations to watch
        political_entity_alliances: Alliances to watch

    Returns:
        TriggerConfig instance
    """
    from aria_esi.services.redisq.notifications.config import (
        NPCFactionKillConfig,
        PoliticalEntityKillConfig,
        TriggerConfig,
    )

    npc_faction_kill = NPCFactionKillConfig(
        enabled=npc_faction_kill_enabled,
        factions=npc_faction_kill_factions or [],
    )

    political_entity = PoliticalEntityKillConfig(
        enabled=political_entity_enabled,
        corporations=political_entity_corps or [],
        alliances=political_entity_alliances or [],
    )

    return TriggerConfig(
        watchlist_activity=watchlist_activity,
        gatecamp_detected=gatecamp_detected,
        high_value_threshold=high_value_threshold,
        war_activity=war_activity,
        war_suppress_gatecamp=war_suppress_gatecamp,
        npc_faction_kill=npc_faction_kill,
        political_entity=political_entity,
    )


def make_notification_profile(
    name: str = "test-profile",
    enabled: bool = True,
    webhook_url: str = "https://discord.com/api/webhooks/123/abc",
    triggers: Any | None = None,
    throttle_minutes: int = 5,
    topology: dict[str, Any] | None = None,
    interest: dict[str, Any] | None = None,
) -> Any:
    """
    Create a NotificationProfile for testing.

    Args:
        name: Profile name
        enabled: Whether profile is enabled
        webhook_url: Discord webhook URL
        triggers: TriggerConfig (uses defaults if None)
        throttle_minutes: Throttle window
        topology: Topology configuration
        interest: Interest v2 configuration

    Returns:
        NotificationProfile instance
    """
    from aria_esi.services.redisq.notifications.config import TriggerConfig
    from aria_esi.services.redisq.notifications.profiles import NotificationProfile

    return NotificationProfile(
        name=name,
        enabled=enabled,
        webhook_url=webhook_url,
        triggers=triggers or TriggerConfig(),
        throttle_minutes=throttle_minutes,
        topology=topology or {},
        interest=interest or {},
    )


@pytest.fixture
def mock_npc_faction_mapper():
    """Create a mock NPC faction mapper."""
    mapper = MagicMock()
    mapper.is_loaded = True
    mapper.get_corps_for_faction.return_value = {1000125, 1000126}
    mapper.get_faction_for_corp.return_value = "serpentis"
    mapper.get_corp_name.return_value = "Serpentis Corporation"
    mapper.get_all_faction_keys.return_value = [
        "serpentis",
        "angel_cartel",
        "guristas",
        "blood_raiders",
        "sansha",
    ]
    return mapper
