"""
Pytest fixtures for signal provider tests.

Extends parent conftest with signal-specific fixtures.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pytest


@dataclass
class MockProcessedKill:
    """Mock ProcessedKill for testing signals."""

    kill_id: int = 12345678
    solar_system_id: int = 30000142  # Jita
    victim_ship_type_id: int | None = 24690  # Vexor
    victim_corporation_id: int | None = 98000001
    victim_alliance_id: int | None = 99001234
    is_pod_kill: bool = False
    attacker_count: int = 3
    attacker_corps: list[int] = field(default_factory=lambda: [98000002, 98000003])
    attacker_alliances: list[int] = field(default_factory=lambda: [99005678])
    attacker_ship_types: list[int] = field(default_factory=lambda: [17703, 17703])  # Astero
    final_blow_ship_type_id: int | None = 17703
    total_value: float = 150_000_000.0  # 150M ISK
    kill_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# Value Signal Fixtures
# =============================================================================


@pytest.fixture
def mock_kill_low_value() -> MockProcessedKill:
    """Kill with low ISK value."""
    return MockProcessedKill(
        kill_id=12345001,
        total_value=5_000_000.0,  # 5M ISK
    )


@pytest.fixture
def mock_kill_high_value() -> MockProcessedKill:
    """Kill with high ISK value."""
    return MockProcessedKill(
        kill_id=12345002,
        victim_ship_type_id=28606,  # Orca
        total_value=3_500_000_000.0,  # 3.5B ISK
    )


@pytest.fixture
def mock_kill_extreme_value() -> MockProcessedKill:
    """Kill with extreme ISK value."""
    return MockProcessedKill(
        kill_id=12345003,
        victim_ship_type_id=671,  # Titan
        total_value=150_000_000_000.0,  # 150B ISK
    )


# =============================================================================
# Ship Signal Fixtures
# =============================================================================


@pytest.fixture
def mock_kill_freighter() -> MockProcessedKill:
    """Freighter kill."""
    return MockProcessedKill(
        kill_id=12345010,
        victim_ship_type_id=20185,  # Obelisk
        total_value=1_200_000_000.0,  # 1.2B ISK
    )


@pytest.fixture
def mock_kill_jump_freighter() -> MockProcessedKill:
    """Jump freighter kill."""
    return MockProcessedKill(
        kill_id=12345011,
        victim_ship_type_id=28846,  # Rhea
        total_value=12_000_000_000.0,  # 12B ISK
    )


@pytest.fixture
def mock_kill_capital() -> MockProcessedKill:
    """Capital ship kill (carrier)."""
    return MockProcessedKill(
        kill_id=12345012,
        victim_ship_type_id=23757,  # Archon
        total_value=2_500_000_000.0,  # 2.5B ISK
    )


@pytest.fixture
def mock_kill_pod() -> MockProcessedKill:
    """Pod kill."""
    return MockProcessedKill(
        kill_id=12345013,
        victim_ship_type_id=670,  # Capsule
        is_pod_kill=True,
        total_value=50_000_000.0,  # 50M implants
    )


@pytest.fixture
def mock_kill_mining_barge() -> MockProcessedKill:
    """Mining barge kill."""
    return MockProcessedKill(
        kill_id=12345014,
        victim_ship_type_id=17478,  # Retriever
        total_value=35_000_000.0,  # 35M ISK
    )


@pytest.fixture
def mock_kill_rorqual() -> MockProcessedKill:
    """Rorqual kill (capital miner)."""
    return MockProcessedKill(
        kill_id=12345015,
        victim_ship_type_id=28352,  # Rorqual
        total_value=10_000_000_000.0,  # 10B ISK
    )


# =============================================================================
# Time Signal Fixtures
# =============================================================================


@pytest.fixture
def mock_kill_primetime() -> MockProcessedKill:
    """Kill during typical primetime (19:00 UTC)."""
    return MockProcessedKill(
        kill_id=12345020,
        kill_time=datetime(2024, 1, 15, 19, 30, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def mock_kill_offhours() -> MockProcessedKill:
    """Kill during off-hours (04:00 UTC)."""
    return MockProcessedKill(
        kill_id=12345021,
        kill_time=datetime(2024, 1, 15, 4, 30, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def mock_kill_midnight() -> MockProcessedKill:
    """Kill at midnight UTC."""
    return MockProcessedKill(
        kill_id=12345022,
        kill_time=datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc),
    )


# =============================================================================
# Location Signal Fixtures
# =============================================================================


@pytest.fixture
def mock_distance_function() -> Callable[[int, int], int | None]:
    """Mock distance function for geographic signal tests."""
    # Simple distance map for testing
    distances = {
        # Jita as origin
        (30000142, 30000142): 0,  # Jita to Jita
        (30000142, 30000144): 1,  # Jita to Perimeter
        (30000142, 30002187): 3,  # Jita to Amarr (approx)
        # Amarr as origin
        (30002187, 30002187): 0,  # Amarr to Amarr
        (30002187, 30002188): 1,  # Amarr to nearby
        (30002187, 30000142): 3,  # Amarr to Jita
        # Dodixie
        (30002659, 30002659): 0,
        (30002659, 30000142): 10,  # Far from Jita
    }

    def get_distance(from_id: int, to_id: int) -> int | None:
        return distances.get((from_id, to_id))

    return get_distance


@pytest.fixture
def mock_security_lookup() -> Callable[[int], float | None]:
    """Mock security status lookup for security signal tests."""
    securities = {
        30000142: 0.95,  # Jita - high sec
        30000144: 0.88,  # Perimeter - high sec
        30002187: 1.0,  # Amarr - high sec
        30002659: 0.87,  # Dodixie - high sec
        30002813: 0.45,  # Low sec border
        30003837: 0.35,  # Low sec
        30004759: -0.1,  # Null sec
        31000005: -1.0,  # Wormhole
    }

    def get_security(system_id: int) -> float | None:
        return securities.get(system_id)

    return get_security


# =============================================================================
# Politics Signal Fixtures
# =============================================================================


@pytest.fixture
def mock_kill_corp_victim() -> MockProcessedKill:
    """Kill where victim is in a tracked corporation."""
    return MockProcessedKill(
        kill_id=12345030,
        victim_corporation_id=98000001,
        victim_alliance_id=99001234,
    )


@pytest.fixture
def mock_kill_corp_attacker() -> MockProcessedKill:
    """Kill where attacker is in a tracked corporation."""
    return MockProcessedKill(
        kill_id=12345031,
        victim_corporation_id=98000099,  # Different corp
        attacker_corps=[98000001],  # Tracked corp
        attacker_alliances=[],
    )


@pytest.fixture
def mock_kill_npc_only() -> MockProcessedKill:
    """Kill with only NPC attackers."""
    return MockProcessedKill(
        kill_id=12345032,
        attacker_count=5,
        attacker_corps=[1000125, 1000127],  # NPC corps (< 2M)
        attacker_alliances=[],
        total_value=10_000_000.0,
    )


@pytest.fixture
def mock_kill_solo() -> MockProcessedKill:
    """Solo kill."""
    return MockProcessedKill(
        kill_id=12345033,
        attacker_count=1,
        attacker_corps=[98000002],
        attacker_alliances=[99005678],
    )


# =============================================================================
# Activity Signal Fixtures
# =============================================================================


@dataclass
class MockGatecampStatus:
    """Mock gatecamp status object."""

    confidence: str = "medium"


@pytest.fixture
def mock_gatecamp_high() -> MockGatecampStatus:
    """High confidence gatecamp."""
    return MockGatecampStatus(confidence="high")


@pytest.fixture
def mock_gatecamp_low() -> MockGatecampStatus:
    """Low confidence gatecamp."""
    return MockGatecampStatus(confidence="low")


@pytest.fixture
def mock_activity_spike() -> dict[str, Any]:
    """Activity data with spike detected."""
    return {
        "spike_detected": True,
        "sustained_kills": 2,
    }


@pytest.fixture
def mock_activity_sustained() -> dict[str, Any]:
    """Activity data with sustained activity."""
    return {
        "spike_detected": False,
        "sustained_kills": 10,
    }


@pytest.fixture
def mock_activity_quiet() -> dict[str, Any]:
    """Activity data with no notable patterns."""
    return {
        "spike_detected": False,
        "sustained_kills": 1,
    }


# =============================================================================
# War Signal Fixtures
# =============================================================================


@pytest.fixture
def mock_kill_war_victim() -> MockProcessedKill:
    """Kill where victim is a war target."""
    return MockProcessedKill(
        kill_id=12345040,
        victim_corporation_id=98000050,  # War target corp
        victim_alliance_id=99005000,  # War target alliance
    )


@pytest.fixture
def mock_kill_war_attacker() -> MockProcessedKill:
    """Kill where attacker is a war target."""
    return MockProcessedKill(
        kill_id=12345041,
        victim_corporation_id=98000099,
        attacker_corps=[98000050],  # War target corp
        attacker_alliances=[99005000],
    )


# =============================================================================
# Routes Signal Fixtures
# =============================================================================


@pytest.fixture
def mock_kill_on_route() -> MockProcessedKill:
    """Kill on a monitored trade route."""
    return MockProcessedKill(
        kill_id=12345050,
        solar_system_id=30000144,  # Perimeter (on Jita-Amarr route)
        victim_ship_type_id=20185,  # Freighter
    )


@pytest.fixture
def mock_kill_off_route() -> MockProcessedKill:
    """Kill not on any monitored route."""
    return MockProcessedKill(
        kill_id=12345051,
        solar_system_id=30005000,  # Random system
    )


# =============================================================================
# Assets Signal Fixtures
# =============================================================================


@pytest.fixture
def mock_kill_near_structure() -> MockProcessedKill:
    """Kill in a system with corp structure."""
    return MockProcessedKill(
        kill_id=12345060,
        solar_system_id=30000142,  # System with structure
    )


@pytest.fixture
def mock_kill_near_office() -> MockProcessedKill:
    """Kill in a system with corp office."""
    return MockProcessedKill(
        kill_id=12345061,
        solar_system_id=30002187,  # System with office
    )
