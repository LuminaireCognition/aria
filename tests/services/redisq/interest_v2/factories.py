"""
Shared test factory for ProcessedKill instances.

Replaces duplicated MockProcessedKill dataclasses across test files with a
single factory that returns real ProcessedKill objects.
"""

from __future__ import annotations

from datetime import UTC, datetime

from aria_esi.services.redisq.models import ProcessedKill


def make_processed_kill(
    kill_id: int = 12345678,
    kill_time: datetime | None = None,
    solar_system_id: int = 30000142,  # Jita
    victim_ship_type_id: int | None = 24690,  # Vexor
    victim_corporation_id: int | None = 98000001,
    victim_alliance_id: int | None = 99001234,
    is_pod_kill: bool = False,
    attacker_count: int = 3,
    attacker_corps: list[int] | None = None,
    attacker_alliances: list[int] | None = None,
    attacker_ship_types: list[int] | None = None,
    final_blow_ship_type_id: int | None = 17703,
    total_value: float = 150_000_000.0,  # 150M ISK
    hull_value: float | None = None,
) -> ProcessedKill:
    """Create a ProcessedKill with sensible test defaults.

    All fields are overridable via keyword arguments.
    """
    if kill_time is None:
        kill_time = datetime.now(UTC)
    if attacker_corps is None:
        attacker_corps = [98000002, 98000003]
    if attacker_alliances is None:
        attacker_alliances = [99005678]
    if attacker_ship_types is None:
        attacker_ship_types = [17703, 17703]  # Astero

    return ProcessedKill(
        kill_id=kill_id,
        kill_time=kill_time,
        solar_system_id=solar_system_id,
        victim_ship_type_id=victim_ship_type_id,
        victim_corporation_id=victim_corporation_id,
        victim_alliance_id=victim_alliance_id,
        is_pod_kill=is_pod_kill,
        attacker_count=attacker_count,
        attacker_corps=attacker_corps,
        attacker_alliances=attacker_alliances,
        attacker_ship_types=attacker_ship_types,
        final_blow_ship_type_id=final_blow_ship_type_id,
        total_value=total_value,
        hull_value=hull_value,
    )
