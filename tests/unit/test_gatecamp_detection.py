"""
Unit tests for gatecamp detection algorithm.

Tests the core detection logic for identifying active gatecamps
from kill patterns.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from aria_esi.services.redisq.models import ProcessedKill
from aria_esi.services.redisq.threat_cache import (
    FORCE_ASYMMETRY_THRESHOLD,
    detect_gatecamp,
    detect_smartbomb_camp,
)


def make_kill(
    kill_id: int = 1,
    kill_time: datetime | None = None,
    system_id: int = 30000142,  # Jita
    victim_corp: int = 1,
    victim_alliance: int | None = None,
    attacker_count: int = 1,
    attacker_corps: list[int] | None = None,
    attacker_alliances: list[int] | None = None,
    attacker_ship_types: list[int] | None = None,
    is_pod: bool = False,
    value: float = 10_000_000,
) -> ProcessedKill:
    """Create a test kill with sensible defaults."""
    if kill_time is None:
        kill_time = datetime.utcnow()
    if attacker_corps is None:
        attacker_corps = [100]
    if attacker_alliances is None:
        attacker_alliances = []
    if attacker_ship_types is None:
        attacker_ship_types = [587]  # Rifter

    return ProcessedKill(
        kill_id=kill_id,
        kill_time=kill_time,
        solar_system_id=system_id,
        victim_ship_type_id=670 if is_pod else 587,  # Capsule vs Rifter
        victim_corporation_id=victim_corp,
        victim_alliance_id=victim_alliance,
        attacker_count=attacker_count,
        attacker_corps=attacker_corps,
        attacker_alliances=attacker_alliances,
        attacker_ship_types=attacker_ship_types,
        final_blow_ship_type_id=attacker_ship_types[0] if attacker_ship_types else None,
        total_value=value,
        is_pod_kill=is_pod,
    )


class TestGatecampDetectionBasic:
    """Basic gatecamp detection tests."""

    def test_insufficient_kills_returns_none(self):
        """Less than 3 kills should not trigger detection."""
        kills = [
            make_kill(kill_id=1, victim_corp=1, attacker_count=8),
            make_kill(kill_id=2, victim_corp=2, attacker_count=8),
        ]
        result = detect_gatecamp(system_id=123, kills=kills)
        assert result is None

    def test_basic_camp_detection_multiple_victim_corps(self):
        """3+ kills from different victim corps with high force asymmetry = camp."""
        kills = [
            make_kill(
                kill_id=1,
                victim_corp=1,
                attacker_count=8,
                attacker_corps=[100, 101],
            ),
            make_kill(
                kill_id=2,
                victim_corp=2,
                attacker_count=8,
                attacker_corps=[100, 101],
            ),
            make_kill(
                kill_id=3,
                victim_corp=3,
                attacker_count=8,
                attacker_corps=[100, 101],
            ),
        ]
        result = detect_gatecamp(system_id=123, kills=kills)

        assert result is not None
        assert result.confidence in ("medium", "high")
        assert result.kill_count == 3
        assert result.force_asymmetry >= FORCE_ASYMMETRY_THRESHOLD

    def test_fleet_fight_not_camp(self):
        """Single victim corp with similar-sized forces = fleet fight, not camp."""
        kills = [
            make_kill(
                kill_id=1,
                victim_corp=1,
                attacker_count=2,
                attacker_corps=[100],
            ),
            make_kill(
                kill_id=2,
                victim_corp=1,
                attacker_count=2,
                attacker_corps=[100],
            ),
            make_kill(
                kill_id=3,
                victim_corp=1,
                attacker_count=2,
                attacker_corps=[100],
            ),
        ]
        result = detect_gatecamp(system_id=123, kills=kills)

        # Low force asymmetry + single victim corp = not a camp
        assert result is None

    def test_single_corp_high_asymmetry_is_camp(self):
        """Single victim corp but 5:1+ force ratio = still a camp (small gang picked off)."""
        kills = [
            make_kill(
                kill_id=1,
                victim_corp=1,
                attacker_count=10,
                attacker_corps=[100, 101],
            ),
            make_kill(
                kill_id=2,
                victim_corp=1,
                attacker_count=10,
                attacker_corps=[100, 101],
            ),
            make_kill(
                kill_id=3,
                victim_corp=1,
                attacker_count=10,
                attacker_corps=[100, 101],
            ),
        ]
        result = detect_gatecamp(system_id=123, kills=kills)

        # High force asymmetry triggers detection even with single victim corp
        assert result is not None
        assert result.force_asymmetry >= FORCE_ASYMMETRY_THRESHOLD


class TestSmartbombDetection:
    """Smartbomb camp detection tests."""

    def test_smartbomb_detection_with_valid_ships_and_timing(self):
        """Kills within 60s with smartbomb ships = smartbomb camp."""
        base_time = datetime.utcnow()
        rokh_type_id = 24690  # Rokh is a known smartbomb platform

        kills = [
            make_kill(
                kill_id=1,
                kill_time=base_time,
                victim_corp=1,
                attacker_ship_types=[rokh_type_id],
            ),
            make_kill(
                kill_id=2,
                kill_time=base_time + timedelta(seconds=5),
                victim_corp=2,
                attacker_ship_types=[rokh_type_id],
            ),
            make_kill(
                kill_id=3,
                kill_time=base_time + timedelta(seconds=10),
                victim_corp=3,
                attacker_ship_types=[rokh_type_id],
            ),
        ]

        attacker_ships = {rokh_type_id}
        assert detect_smartbomb_camp(kills, attacker_ships) is True

        # Also test via full detection
        result = detect_gatecamp(system_id=123, kills=kills)
        assert result is not None
        assert result.is_smartbomb_camp is True

    def test_smartbomb_requires_ship_types(self):
        """Fast kills without smartbomb ships = not smartbomb camp."""
        base_time = datetime.utcnow()
        rifter_type_id = 587  # Rifter is not a smartbomb ship

        kills = [
            make_kill(
                kill_id=1,
                kill_time=base_time,
                victim_corp=1,
                attacker_ship_types=[rifter_type_id],
            ),
            make_kill(
                kill_id=2,
                kill_time=base_time + timedelta(seconds=5),
                victim_corp=2,
                attacker_ship_types=[rifter_type_id],
            ),
            make_kill(
                kill_id=3,
                kill_time=base_time + timedelta(seconds=10),
                victim_corp=3,
                attacker_ship_types=[rifter_type_id],
            ),
        ]

        attacker_ships = {rifter_type_id}
        assert detect_smartbomb_camp(kills, attacker_ships) is False

        # Also test via full detection
        result = detect_gatecamp(system_id=123, kills=kills)
        # Should still detect as camp (multiple victim corps), just not smartbomb
        assert result is not None
        assert result.is_smartbomb_camp is False

    def test_smartbomb_requires_timing(self):
        """Smartbomb ships but slow kills = not smartbomb camp."""
        base_time = datetime.utcnow()
        rokh_type_id = 24690

        kills = [
            make_kill(
                kill_id=1,
                kill_time=base_time,
                victim_corp=1,
                attacker_ship_types=[rokh_type_id],
            ),
            make_kill(
                kill_id=2,
                kill_time=base_time + timedelta(seconds=120),  # Too slow
                victim_corp=2,
                attacker_ship_types=[rokh_type_id],
            ),
            make_kill(
                kill_id=3,
                kill_time=base_time + timedelta(seconds=240),  # Too slow
                victim_corp=3,
                attacker_ship_types=[rokh_type_id],
            ),
        ]

        attacker_ships = {rokh_type_id}
        assert detect_smartbomb_camp(kills, attacker_ships) is False


class TestConfidenceFactors:
    """Tests for confidence level calculation."""

    def test_high_confidence_multiple_factors(self):
        """High pod ratio + consistent attackers + force asymmetry = high confidence."""
        base_time = datetime.utcnow()
        attackers = [100, 101]

        kills = [
            # Ship kills
            make_kill(
                kill_id=1,
                kill_time=base_time,
                victim_corp=1,
                attacker_count=10,
                attacker_corps=attackers,
                is_pod=False,
            ),
            make_kill(
                kill_id=2,
                kill_time=base_time + timedelta(seconds=30),
                victim_corp=1,
                attacker_count=10,
                attacker_corps=attackers,
                is_pod=True,  # Pod kill
            ),
            make_kill(
                kill_id=3,
                kill_time=base_time + timedelta(seconds=60),
                victim_corp=2,
                attacker_count=10,
                attacker_corps=attackers,
                is_pod=False,
            ),
            make_kill(
                kill_id=4,
                kill_time=base_time + timedelta(seconds=90),
                victim_corp=2,
                attacker_count=10,
                attacker_corps=attackers,
                is_pod=True,  # Pod kill
            ),
            make_kill(
                kill_id=5,
                kill_time=base_time + timedelta(seconds=120),
                victim_corp=3,
                attacker_count=10,
                attacker_corps=attackers,
                is_pod=False,
            ),
        ]

        result = detect_gatecamp(system_id=123, kills=kills)

        assert result is not None
        assert result.confidence == "high"

    def test_low_confidence_minimal_factors(self):
        """Just meeting minimum threshold = low confidence."""
        kills = [
            make_kill(
                kill_id=1,
                victim_corp=1,
                attacker_count=6,  # Just above threshold
                attacker_corps=[100],
            ),
            make_kill(
                kill_id=2,
                victim_corp=2,
                attacker_count=6,
                attacker_corps=[200],  # Different attacker
            ),
            make_kill(
                kill_id=3,
                victim_corp=3,
                attacker_count=6,
                attacker_corps=[300],  # Different attacker
            ),
        ]

        result = detect_gatecamp(system_id=123, kills=kills)

        assert result is not None
        # Inconsistent attackers + no pod kills = lower confidence
        assert result.confidence in ("low", "medium")


class TestAttackerTracking:
    """Tests for attacker corp/alliance tracking."""

    def test_attacker_corps_collected(self):
        """All attacker corps should be collected from kills."""
        kills = [
            make_kill(
                kill_id=1,
                victim_corp=1,
                attacker_count=10,
                attacker_corps=[100, 101],
            ),
            make_kill(
                kill_id=2,
                victim_corp=2,
                attacker_count=10,
                attacker_corps=[100, 102],
            ),
            make_kill(
                kill_id=3,
                victim_corp=3,
                attacker_count=10,
                attacker_corps=[100, 103],
            ),
        ]

        result = detect_gatecamp(system_id=123, kills=kills)

        assert result is not None
        # Should have all unique attacker corps
        assert set(result.attacker_corps) == {100, 101, 102, 103}

    def test_attacker_ships_collected(self):
        """All attacker ships should be collected for fleet composition."""
        kills = [
            make_kill(
                kill_id=1,
                victim_corp=1,
                attacker_count=10,
                attacker_ship_types=[587, 588],  # Rifter, Punisher
            ),
            make_kill(
                kill_id=2,
                victim_corp=2,
                attacker_count=10,
                attacker_ship_types=[587, 589],  # Rifter, Executioner
            ),
            make_kill(
                kill_id=3,
                victim_corp=3,
                attacker_count=10,
                attacker_ship_types=[587],  # Rifter
            ),
        ]

        result = detect_gatecamp(system_id=123, kills=kills)

        assert result is not None
        assert set(result.attacker_ships) == {587, 588, 589}


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_kills_returns_none(self):
        """Empty kill list should return None."""
        result = detect_gatecamp(system_id=123, kills=[])
        assert result is None

    def test_system_name_propagation(self):
        """System name should be included in result if provided."""
        kills = [
            make_kill(kill_id=i, victim_corp=i, attacker_count=10)
            for i in range(1, 4)
        ]

        result = detect_gatecamp(
            system_id=30000142,
            kills=kills,
            system_name="Jita",
        )

        assert result is not None
        assert result.system_name == "Jita"
        assert result.system_id == 30000142

    def test_last_kill_time_tracked(self):
        """Result should include the most recent kill time."""
        base_time = datetime.utcnow()
        latest_time = base_time + timedelta(minutes=5)

        kills = [
            make_kill(
                kill_id=1,
                kill_time=base_time,
                victim_corp=1,
                attacker_count=10,
            ),
            make_kill(
                kill_id=2,
                kill_time=base_time + timedelta(minutes=2),
                victim_corp=2,
                attacker_count=10,
            ),
            make_kill(
                kill_id=3,
                kill_time=latest_time,
                victim_corp=3,
                attacker_count=10,
            ),
        ]

        result = detect_gatecamp(system_id=123, kills=kills)

        assert result is not None
        assert result.last_kill_time == latest_time

    def test_force_asymmetry_calculation(self):
        """Force asymmetry should be average attackers per kill."""
        kills = [
            make_kill(kill_id=1, victim_corp=1, attacker_count=5),
            make_kill(kill_id=2, victim_corp=2, attacker_count=10),
            make_kill(kill_id=3, victim_corp=3, attacker_count=15),
        ]

        result = detect_gatecamp(system_id=123, kills=kills)

        assert result is not None
        # Average: (5 + 10 + 15) / 3 = 10.0
        assert result.force_asymmetry == 10.0


class TestWarContextIntegration:
    """Tests for war context integration with gatecamp detection."""

    def test_war_context_param_accepted(self):
        """detect_gatecamp should accept war_context parameter."""
        kills = [
            make_kill(kill_id=i, victim_corp=i, attacker_count=10)
            for i in range(1, 4)
        ]

        # Should not raise with None war_context
        result = detect_gatecamp(system_id=123, kills=kills, war_context=None)
        assert result is not None

    def test_gatecamp_status_war_fields_default(self):
        """GatecampStatus should have war fields with default values."""
        kills = [
            make_kill(kill_id=i, victim_corp=i, attacker_count=10)
            for i in range(1, 4)
        ]

        result = detect_gatecamp(system_id=123, kills=kills)

        assert result is not None
        assert result.is_war_engagement is False
        assert result.war_attacker_alliance is None
        assert result.war_defender_alliance is None
        assert result.war_kills_filtered == 0

    def test_gatecamp_status_to_dict_includes_war_fields(self):
        """GatecampStatus.to_dict() should include war fields when present."""
        from aria_esi.services.redisq.threat_cache import GatecampStatus

        status = GatecampStatus(
            system_id=123,
            kill_count=5,
            is_war_engagement=True,
            war_attacker_alliance=1000001,
            war_defender_alliance=2000001,
            war_kills_filtered=2,
        )

        result_dict = status.to_dict()

        assert result_dict["is_war_engagement"] is True
        assert result_dict["war_attacker_alliance"] == 1000001
        assert result_dict["war_defender_alliance"] == 2000001
        assert result_dict["war_kills_filtered"] == 2

    def test_gatecamp_status_to_dict_omits_war_when_not_present(self):
        """GatecampStatus.to_dict() should omit war fields when not applicable."""
        from aria_esi.services.redisq.threat_cache import GatecampStatus

        status = GatecampStatus(
            system_id=123,
            kill_count=5,
        )

        result_dict = status.to_dict()

        # War engagement fields should not be in dict when not active
        assert "is_war_engagement" not in result_dict
        assert "war_attacker_alliance" not in result_dict
        assert "war_defender_alliance" not in result_dict
        assert "war_kills_filtered" not in result_dict
