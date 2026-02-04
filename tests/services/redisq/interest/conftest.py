"""
Fixtures for interest calculation tests.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass

from aria_esi.services.redisq.interest.layers.base import BaseLayer
from aria_esi.services.redisq.interest.models import LayerScore
from aria_esi.services.redisq.models import ProcessedKill

# =============================================================================
# Mock Layers for Testing
# =============================================================================


class MockGeographicLayer(BaseLayer):
    """Mock geographic layer with configurable interest map."""

    _name = "geographic"

    def __init__(self, interest_map: dict[int, float] | None = None):
        self._interest_map = interest_map or {}

    def score_system(self, system_id: int) -> LayerScore:
        interest = self._interest_map.get(system_id, 0.0)
        reason = "in operational area" if interest > 0 else None
        return LayerScore(layer=self.name, score=interest, reason=reason)


class MockEntityLayer(BaseLayer):
    """Mock entity layer with configurable corp/alliance matching."""

    _name = "entity"

    def __init__(
        self,
        corp_id: int | None = None,
        alliance_id: int | None = None,
        watched_corps: set[int] | None = None,
        watched_alliances: set[int] | None = None,
    ):
        self.corp_id = corp_id
        self.alliance_id = alliance_id
        self.watched_corps = watched_corps or set()
        self.watched_alliances = watched_alliances or set()

    def score_system(self, system_id: int) -> LayerScore:
        # Entity layer requires kill context
        return LayerScore(layer=self.name, score=0.0, reason=None)

    def score_kill(self, system_id: int, kill: ProcessedKill | None) -> LayerScore:
        if kill is None:
            return self.score_system(system_id)

        # Corp member victim - ALWAYS max interest
        if kill.victim_corporation_id == self.corp_id:
            return LayerScore(
                layer=self.name,
                score=1.0,
                reason="corp member loss",
            )

        # Corp member attacker
        if self.corp_id and self.corp_id in kill.attacker_corps:
            return LayerScore(
                layer=self.name,
                score=0.9,
                reason="corp member kill",
            )

        # Alliance member
        if self.alliance_id and kill.victim_alliance_id == self.alliance_id:
            return LayerScore(
                layer=self.name,
                score=0.8,
                reason="alliance member loss",
            )

        # Watched entities
        if kill.victim_corporation_id in self.watched_corps:
            return LayerScore(
                layer=self.name,
                score=0.9,
                reason="watched corp victim",
            )

        for corp in kill.attacker_corps:
            if corp in self.watched_corps:
                return LayerScore(
                    layer=self.name,
                    score=0.9,
                    reason="watched corp attacker",
                )

        return LayerScore(layer=self.name, score=0.0, reason=None)


class MockPatternLayer(BaseLayer):
    """Mock pattern layer returning escalation multipliers."""

    _name = "pattern"

    def __init__(self, escalations: dict[int, tuple[float, str]] | None = None):
        # system_id -> (multiplier, reason)
        self._escalations = escalations or {}

    def score_system(self, system_id: int) -> LayerScore:
        if system_id in self._escalations:
            mult, reason = self._escalations[system_id]
            return LayerScore(layer=self.name, score=mult, reason=reason)
        return LayerScore(layer=self.name, score=1.0, reason=None)

    def score_kill(self, system_id: int, kill: ProcessedKill | None) -> LayerScore:
        return self.score_system(system_id)


# =============================================================================
# Test Kill Factory
# =============================================================================


def make_kill(
    kill_id: int = 12345,
    system_id: int = 30000142,  # Jita
    victim_corp: int | None = None,
    victim_alliance: int | None = None,
    victim_ship_type_id: int = 587,  # Rifter
    attacker_corps: list[int] | None = None,
    attacker_alliances: list[int] | None = None,
    attacker_ship_types: list[int] | None = None,
    total_value: float = 10_000_000,
    is_pod_kill: bool = False,
) -> ProcessedKill:
    """Create a ProcessedKill for testing."""
    return ProcessedKill(
        kill_id=kill_id,
        kill_time=datetime.now(timezone.utc).replace(tzinfo=None),
        solar_system_id=system_id,
        victim_ship_type_id=victim_ship_type_id,
        victim_corporation_id=victim_corp,
        victim_alliance_id=victim_alliance,
        attacker_count=len(attacker_corps or [1]) + 1,
        attacker_corps=attacker_corps or [98000001],
        attacker_alliances=attacker_alliances or [],
        attacker_ship_types=attacker_ship_types or [587],
        final_blow_ship_type_id=587,
        total_value=total_value,
        is_pod_kill=is_pod_kill,
    )


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_geographic_layer() -> MockGeographicLayer:
    """Geographic layer with some systems configured."""
    return MockGeographicLayer(
        interest_map={
            30002537: 1.0,  # Tama - operational
            30002538: 0.95,  # Kedama - 1-hop
            30002539: 0.7,  # 2-hop neighbor
        }
    )


@pytest.fixture
def mock_entity_layer() -> MockEntityLayer:
    """Entity layer with test corp/alliance."""
    return MockEntityLayer(
        corp_id=98000001,  # Test corp
        alliance_id=99000001,  # Test alliance
        watched_corps={98506879},  # Watched enemy corp
    )


@pytest.fixture
def mock_pattern_layer() -> MockPatternLayer:
    """Pattern layer with one escalated system."""
    return MockPatternLayer(
        escalations={
            30002540: (1.5, "Active gatecamp detected"),
        }
    )


@pytest.fixture
def test_kill() -> ProcessedKill:
    """Basic test kill."""
    return make_kill()


@pytest.fixture
def corp_loss_kill() -> ProcessedKill:
    """Kill where victim is from test corp."""
    return make_kill(
        victim_corp=98000001,  # Test corp
        system_id=30000142,  # Jita - not in topology
    )


@pytest.fixture
def watched_attacker_kill() -> ProcessedKill:
    """Kill with watched corp as attacker."""
    return make_kill(
        attacker_corps=[98506879],  # Watched enemy corp
    )
