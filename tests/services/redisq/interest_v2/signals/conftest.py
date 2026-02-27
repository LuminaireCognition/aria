"""
Pytest fixtures for signal provider tests.

Extends parent conftest with signal-specific fixtures.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest

from aria_esi.services.redisq.models import ProcessedKill

from ..factories import make_processed_kill

# =============================================================================
# Value Signal Fixtures
# =============================================================================


@pytest.fixture
def mock_kill_low_value() -> ProcessedKill:
    """Kill with low ISK value."""
    return make_processed_kill(
        kill_id=12345001,
        total_value=5_000_000.0,  # 5M ISK
    )


@pytest.fixture
def mock_kill_high_value() -> ProcessedKill:
    """Kill with high ISK value."""
    return make_processed_kill(
        kill_id=12345002,
        victim_ship_type_id=28606,  # Orca
        total_value=3_500_000_000.0,  # 3.5B ISK
    )


@pytest.fixture
def mock_kill_extreme_value() -> ProcessedKill:
    """Kill with extreme ISK value."""
    return make_processed_kill(
        kill_id=12345003,
        victim_ship_type_id=671,  # Titan
        total_value=150_000_000_000.0,  # 150B ISK
    )


# =============================================================================
# Ship Signal Fixtures
# =============================================================================


@pytest.fixture
def mock_kill_freighter() -> ProcessedKill:
    """Freighter kill."""
    return make_processed_kill(
        kill_id=12345010,
        victim_ship_type_id=20185,  # Obelisk
        total_value=1_200_000_000.0,  # 1.2B ISK
    )


@pytest.fixture
def mock_kill_jump_freighter() -> ProcessedKill:
    """Jump freighter kill."""
    return make_processed_kill(
        kill_id=12345011,
        victim_ship_type_id=28846,  # Rhea
        total_value=12_000_000_000.0,  # 12B ISK
    )


@pytest.fixture
def mock_kill_capital() -> ProcessedKill:
    """Capital ship kill (carrier)."""
    return make_processed_kill(
        kill_id=12345012,
        victim_ship_type_id=23757,  # Archon
        total_value=2_500_000_000.0,  # 2.5B ISK
    )


@pytest.fixture
def mock_kill_pod() -> ProcessedKill:
    """Pod kill."""
    return make_processed_kill(
        kill_id=12345013,
        victim_ship_type_id=670,  # Capsule
        is_pod_kill=True,
        total_value=50_000_000.0,  # 50M implants
    )


@pytest.fixture
def mock_kill_mining_barge() -> ProcessedKill:
    """Mining barge kill."""
    return make_processed_kill(
        kill_id=12345014,
        victim_ship_type_id=17478,  # Retriever
        total_value=35_000_000.0,  # 35M ISK
    )


@pytest.fixture
def mock_kill_rorqual() -> ProcessedKill:
    """Rorqual kill (capital miner)."""
    return make_processed_kill(
        kill_id=12345015,
        victim_ship_type_id=28352,  # Rorqual
        total_value=10_000_000_000.0,  # 10B ISK
    )


# =============================================================================
# Time Signal Fixtures
# =============================================================================


@pytest.fixture
def mock_kill_primetime() -> ProcessedKill:
    """Kill during typical primetime (19:00 UTC)."""
    return make_processed_kill(
        kill_id=12345020,
        kill_time=datetime(2024, 1, 15, 19, 30, 0, tzinfo=UTC),
    )


@pytest.fixture
def mock_kill_offhours() -> ProcessedKill:
    """Kill during off-hours (04:00 UTC)."""
    return make_processed_kill(
        kill_id=12345021,
        kill_time=datetime(2024, 1, 15, 4, 30, 0, tzinfo=UTC),
    )


@pytest.fixture
def mock_kill_midnight() -> ProcessedKill:
    """Kill at midnight UTC."""
    return make_processed_kill(
        kill_id=12345022,
        kill_time=datetime(2024, 1, 15, 0, 0, 0, tzinfo=UTC),
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
def mock_kill_corp_victim() -> ProcessedKill:
    """Kill where victim is in a tracked corporation."""
    return make_processed_kill(
        kill_id=12345030,
        victim_corporation_id=98000001,
        victim_alliance_id=99001234,
    )


@pytest.fixture
def mock_kill_corp_attacker() -> ProcessedKill:
    """Kill where attacker is in a tracked corporation."""
    return make_processed_kill(
        kill_id=12345031,
        victim_corporation_id=98000099,  # Different corp
        attacker_corps=[98000001],  # Tracked corp
        attacker_alliances=[],
    )


@pytest.fixture
def mock_kill_npc_only() -> ProcessedKill:
    """Kill with only NPC attackers."""
    return make_processed_kill(
        kill_id=12345032,
        attacker_count=5,
        attacker_corps=[1000125, 1000127],  # NPC corps (< 2M)
        attacker_alliances=[],
        total_value=10_000_000.0,
    )


@pytest.fixture
def mock_kill_solo() -> ProcessedKill:
    """Solo kill."""
    return make_processed_kill(
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
def mock_kill_war_victim() -> ProcessedKill:
    """Kill where victim is a war target."""
    return make_processed_kill(
        kill_id=12345040,
        victim_corporation_id=98000050,  # War target corp
        victim_alliance_id=99005000,  # War target alliance
    )


@pytest.fixture
def mock_kill_war_attacker() -> ProcessedKill:
    """Kill where attacker is a war target."""
    return make_processed_kill(
        kill_id=12345041,
        victim_corporation_id=98000099,
        attacker_corps=[98000050],  # War target corp
        attacker_alliances=[99005000],
    )


# =============================================================================
# Routes Signal Fixtures
# =============================================================================


@pytest.fixture
def mock_kill_on_route() -> ProcessedKill:
    """Kill on a monitored trade route."""
    return make_processed_kill(
        kill_id=12345050,
        solar_system_id=30000144,  # Perimeter (on Jita-Amarr route)
        victim_ship_type_id=20185,  # Freighter
    )


@pytest.fixture
def mock_kill_off_route() -> ProcessedKill:
    """Kill not on any monitored route."""
    return make_processed_kill(
        kill_id=12345051,
        solar_system_id=30005000,  # Random system
    )


# =============================================================================
# Assets Signal Fixtures
# =============================================================================


@pytest.fixture
def mock_kill_near_structure() -> ProcessedKill:
    """Kill in a system with corp structure."""
    return make_processed_kill(
        kill_id=12345060,
        solar_system_id=30000142,  # System with structure
    )


@pytest.fixture
def mock_kill_near_office() -> ProcessedKill:
    """Kill in a system with corp office."""
    return make_processed_kill(
        kill_id=12345061,
        solar_system_id=30002187,  # System with office
    )
