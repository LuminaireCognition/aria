"""
Tests for Interest Engine v2 Simulation Tool.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from aria_esi.services.redisq.interest_v2.cli.simulate import (
    SimulationKillResult,
    SimulationResult,
    SimulationSummary,
    format_simulation_report,
    simulate_profile,
)


@dataclass
class MockProcessedKill:
    """Mock kill for simulation tests."""
    kill_id: int
    solar_system_id: int
    kill_time: datetime | None = None
    victim_ship_type_id: int | None = 24690
    victim_corporation_id: int | None = 98000001
    victim_alliance_id: int | None = None
    is_pod_kill: bool = False
    attacker_count: int = 1
    attacker_corps: list[int] = field(default_factory=list)
    attacker_alliances: list[int] = field(default_factory=list)
    attacker_ship_types: list[int] = field(default_factory=list)
    final_blow_ship_type_id: int | None = None
    total_value: float = 50_000_000


class TestSimulationKillResult:
    """Tests for SimulationKillResult dataclass."""

    def test_would_notify_notify_tier(self):
        """NOTIFY tier returns would_notify=True."""
        result = SimulationKillResult(
            kill_id=123,
            system_id=456,
            timestamp=None,
            v2_tier="notify",
            v2_interest=0.65,
        )
        assert result.would_notify is True

    def test_would_notify_priority_tier(self):
        """PRIORITY tier returns would_notify=True."""
        result = SimulationKillResult(
            kill_id=123,
            system_id=456,
            timestamp=None,
            v2_tier="priority",
            v2_interest=0.90,
        )
        assert result.would_notify is True

    def test_would_notify_digest_tier(self):
        """DIGEST tier returns would_notify=False."""
        result = SimulationKillResult(
            kill_id=123,
            system_id=456,
            timestamp=None,
            v2_tier="digest",
            v2_interest=0.45,
        )
        assert result.would_notify is False

    def test_would_notify_filter_tier(self):
        """FILTER tier returns would_notify=False."""
        result = SimulationKillResult(
            kill_id=123,
            system_id=456,
            timestamp=None,
            v2_tier="filter",
            v2_interest=0.0,
        )
        assert result.would_notify is False

    def test_tier_changed_v1_vs_v2(self):
        """tier_changed detects difference from v1."""
        # v1 triggered, v2 would not notify
        result = SimulationKillResult(
            kill_id=123,
            system_id=456,
            timestamp=None,
            v2_tier="digest",  # Not notify
            v2_interest=0.45,
            v1_triggered=True,  # But v1 did trigger
        )
        assert result.tier_changed is True

        # Both agree
        result2 = SimulationKillResult(
            kill_id=124,
            system_id=456,
            timestamp=None,
            v2_tier="notify",
            v2_interest=0.65,
            v1_triggered=True,
        )
        assert result2.tier_changed is False

    def test_tier_changed_none_v1(self):
        """tier_changed returns False when no v1 data."""
        result = SimulationKillResult(
            kill_id=123,
            system_id=456,
            timestamp=None,
            v2_tier="notify",
            v2_interest=0.65,
            v1_triggered=None,  # No v1 comparison
        )
        assert result.tier_changed is False


class TestSimulationSummary:
    """Tests for SimulationSummary dataclass."""

    def test_v2_total_notify(self):
        """v2_total_notify combines notify and priority."""
        summary = SimulationSummary(
            profile_name="test",
            total_kills=100,
            v2_notify=30,
            v2_priority=10,
            v2_digest=40,
            v2_filter=20,
        )
        assert summary.v2_total_notify == 40

    def test_to_dict(self):
        """Summary converts to dictionary."""
        summary = SimulationSummary(
            profile_name="test",
            total_kills=100,
            v2_notify=30,
            v2_priority=10,
            v2_digest=40,
            v2_filter=20,
            v1_triggered=35,
            tier_changes=5,
        )

        d = summary.to_dict()

        assert d["profile"] == "test"
        assert d["total_kills"] == 100
        assert d["v2"]["notify"] == 30
        assert d["v2"]["priority"] == 10
        assert d["v1_triggered"] == 35
        assert d["tier_changes"] == 5


class TestSimulationResult:
    """Tests for SimulationResult dataclass."""

    def test_get_tier_breakdown(self):
        """Tier breakdown groups kills correctly."""
        result = SimulationResult(
            summary=SimulationSummary(
                profile_name="test",
                total_kills=3,
                v2_notify=1,
                v2_priority=1,
                v2_digest=1,
                v2_filter=0,
            ),
            kills=[
                SimulationKillResult(1, 100, None, "priority", 0.90),
                SimulationKillResult(2, 100, None, "notify", 0.65),
                SimulationKillResult(3, 100, None, "digest", 0.45),
            ],
        )

        breakdown = result.get_tier_breakdown()

        assert len(breakdown["priority"]) == 1
        assert len(breakdown["notify"]) == 1
        assert len(breakdown["digest"]) == 1
        assert len(breakdown["filter"]) == 0

    def test_get_changed_kills(self):
        """Changed kills returns only those with tier change."""
        result = SimulationResult(
            summary=SimulationSummary(
                profile_name="test",
                total_kills=3,
                v2_notify=2,
                v2_priority=0,
                v2_digest=1,
                v2_filter=0,
                tier_changes=1,
            ),
            kills=[
                SimulationKillResult(1, 100, None, "notify", 0.65, v1_triggered=True),  # Same
                SimulationKillResult(2, 100, None, "notify", 0.70, v1_triggered=False),  # Changed
                SimulationKillResult(3, 100, None, "digest", 0.45, v1_triggered=False),  # Same
            ],
        )

        changed = result.get_changed_kills()

        assert len(changed) == 1
        assert changed[0].kill_id == 2


class TestSimulateProfile:
    """Tests for simulate_profile function."""

    def test_empty_kills_list(self, reset_registry):
        """Empty kills list returns empty result."""
        from aria_esi.services.redisq.interest_v2.config import InterestConfigV2
        from aria_esi.services.redisq.interest_v2.engine import InterestEngineV2

        config = InterestConfigV2(engine="v2", preset="trade-hub")
        engine = InterestEngineV2(config)

        result = simulate_profile(engine, [], "test")

        assert result.summary.total_kills == 0
        assert result.summary.v2_notify == 0
        assert len(result.kills) == 0

    def test_single_kill_simulation(self, reset_registry):
        """Single kill is simulated correctly."""
        from aria_esi.services.redisq.interest_v2.config import InterestConfigV2
        from aria_esi.services.redisq.interest_v2.engine import InterestEngineV2

        config = InterestConfigV2(engine="v2", preset="trade-hub")
        engine = InterestEngineV2(config)

        kills = [MockProcessedKill(kill_id=123, solar_system_id=30000142)]

        result = simulate_profile(engine, kills, "test")

        assert result.summary.total_kills == 1
        assert len(result.kills) == 1
        assert result.kills[0].kill_id == 123

    def test_multiple_kills_simulation(self, reset_registry):
        """Multiple kills are simulated."""
        from aria_esi.services.redisq.interest_v2.config import InterestConfigV2
        from aria_esi.services.redisq.interest_v2.engine import InterestEngineV2

        config = InterestConfigV2(engine="v2", preset="trade-hub")
        engine = InterestEngineV2(config)

        kills = [
            MockProcessedKill(kill_id=1, solar_system_id=30000142),
            MockProcessedKill(kill_id=2, solar_system_id=30000142),
            MockProcessedKill(kill_id=3, solar_system_id=30000142),
        ]

        result = simulate_profile(engine, kills, "test")

        assert result.summary.total_kills == 3
        assert len(result.kills) == 3

    def test_v1_comparison(self, reset_registry):
        """V1 results are compared correctly."""
        from aria_esi.services.redisq.interest_v2.config import InterestConfigV2
        from aria_esi.services.redisq.interest_v2.engine import InterestEngineV2

        config = InterestConfigV2(engine="v2", preset="trade-hub")
        engine = InterestEngineV2(config)

        kills = [
            MockProcessedKill(kill_id=1, solar_system_id=30000142),
            MockProcessedKill(kill_id=2, solar_system_id=30000142),
        ]

        v1_results = {1: True, 2: False}

        result = simulate_profile(engine, kills, "test", v1_results)

        assert result.summary.v1_triggered == 1  # Kill 1 was triggered in v1

    def test_time_range_tracked(self, reset_registry):
        """Time range is tracked from kill timestamps."""
        from aria_esi.services.redisq.interest_v2.config import InterestConfigV2
        from aria_esi.services.redisq.interest_v2.engine import InterestEngineV2

        config = InterestConfigV2(engine="v2", preset="trade-hub")
        engine = InterestEngineV2(config)

        now = datetime.now()
        kills = [
            MockProcessedKill(kill_id=1, solar_system_id=30000142, kill_time=now - timedelta(hours=2)),
            MockProcessedKill(kill_id=2, solar_system_id=30000142, kill_time=now - timedelta(hours=1)),
            MockProcessedKill(kill_id=3, solar_system_id=30000142, kill_time=now),
        ]

        result = simulate_profile(engine, kills, "test")

        assert result.summary.start_time is not None
        assert result.summary.end_time is not None
        assert result.summary.start_time <= result.summary.end_time


class TestFormatSimulationReport:
    """Tests for report formatting."""

    def test_includes_profile_name(self):
        """Report includes profile name."""
        result = SimulationResult(
            summary=SimulationSummary(
                profile_name="my-profile",
                total_kills=10,
                v2_notify=5,
                v2_priority=2,
                v2_digest=3,
                v2_filter=0,
            ),
            kills=[],
        )

        report = format_simulation_report(result)

        assert "my-profile" in report

    def test_includes_tier_counts(self):
        """Report includes tier counts."""
        result = SimulationResult(
            summary=SimulationSummary(
                profile_name="test",
                total_kills=100,
                v2_notify=30,
                v2_priority=10,
                v2_digest=40,
                v2_filter=20,
            ),
            kills=[],
        )

        report = format_simulation_report(result)

        assert "PRIORITY" in report
        assert "NOTIFY" in report
        assert "DIGEST" in report
        assert "FILTER" in report
        assert "30" in report  # notify count
        assert "10" in report  # priority count

    def test_includes_percentage(self):
        """Report includes notification percentage."""
        result = SimulationResult(
            summary=SimulationSummary(
                profile_name="test",
                total_kills=100,
                v2_notify=30,
                v2_priority=10,
                v2_digest=40,
                v2_filter=20,
            ),
            kills=[],
        )

        report = format_simulation_report(result)

        assert "40" in report  # v2_total_notify
        assert "%" in report

    def test_includes_v1_comparison(self):
        """Report includes v1 comparison when available."""
        result = SimulationResult(
            summary=SimulationSummary(
                profile_name="test",
                total_kills=100,
                v2_notify=30,
                v2_priority=10,
                v2_digest=40,
                v2_filter=20,
                v1_triggered=35,
                tier_changes=5,
                new_notifications=3,
                lost_notifications=2,
            ),
            kills=[],
        )

        report = format_simulation_report(result)

        assert "v1" in report.lower()
        assert "35" in report  # v1_triggered
        assert "5" in report  # tier_changes

    def test_shows_net_change(self):
        """Report shows net change indicator."""
        result = SimulationResult(
            summary=SimulationSummary(
                profile_name="test",
                total_kills=100,
                v2_notify=30,
                v2_priority=10,
                v2_digest=40,
                v2_filter=20,
                v1_triggered=35,
                tier_changes=10,
                new_notifications=8,
                lost_notifications=2,
            ),
            kills=[],
        )

        report = format_simulation_report(result)

        # Net +6 (8 new - 2 lost)
        assert "+6" in report or "more" in report.lower()

    def test_verbose_shows_kill_details(self):
        """Verbose mode shows individual kill details."""
        result = SimulationResult(
            summary=SimulationSummary(
                profile_name="test",
                total_kills=1,
                v2_notify=1,
                v2_priority=0,
                v2_digest=0,
                v2_filter=0,
            ),
            kills=[
                SimulationKillResult(
                    kill_id=12345,
                    system_id=30000142,
                    timestamp=None,
                    v2_tier="priority",
                    v2_interest=0.95,
                    dominant_category="location",
                ),
            ],
        )

        report = format_simulation_report(result, verbose=True)

        assert "12345" in report  # kill_id
        assert "location" in report.lower()

    def test_shows_errors(self):
        """Report shows errors if any."""
        result = SimulationResult(
            summary=SimulationSummary(
                profile_name="test",
                total_kills=0,
                v2_notify=0,
                v2_priority=0,
                v2_digest=0,
                v2_filter=0,
            ),
            kills=[],
            errors=["Error processing kill 123: Something went wrong"],
        )

        report = format_simulation_report(result)

        assert "Error" in report
        assert "123" in report
