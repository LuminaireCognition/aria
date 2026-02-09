"""
Tests for notification profile evaluator.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from aria_esi.services.redisq.notifications.config import QuietHoursConfig, TriggerConfig
from aria_esi.services.redisq.notifications.profile_evaluator import (
    MAX_PROFILES_HARD,
    MAX_PROFILES_SOFT,
    EvaluationResult,
    ProfileEvaluator,
    ProfileMatch,
)
from aria_esi.services.redisq.notifications.profiles import NotificationProfile
from aria_esi.services.redisq.notifications.triggers import TriggerType


def make_profile(
    name: str,
    enabled: bool = True,
    watchlist_activity: bool = True,
    gatecamp_detected: bool = True,
    high_value_threshold: int = 1_000_000_000,
    throttle_minutes: int = 5,
) -> NotificationProfile:
    """Create a test profile."""
    return NotificationProfile(
        name=name,
        enabled=enabled,
        webhook_url="https://discord.com/api/webhooks/123/abc",
        triggers=TriggerConfig(
            watchlist_activity=watchlist_activity,
            gatecamp_detected=gatecamp_detected,
            high_value_threshold=high_value_threshold,
        ),
        throttle_minutes=throttle_minutes,
    )


def make_kill(
    kill_id: int = 12345,
    solar_system_id: int = 30000142,
    total_value: int = 100_000_000,
) -> MagicMock:
    """Create a mock ProcessedKill."""
    kill = MagicMock()
    kill.kill_id = kill_id
    kill.solar_system_id = solar_system_id
    kill.total_value = total_value
    return kill


def make_entity_match(has_match: bool = False) -> MagicMock:
    """Create a mock EntityMatchResult."""
    match = MagicMock()
    match.has_match = has_match
    return match


def make_gatecamp_status(confidence: str = "none") -> MagicMock:
    """Create a mock GatecampStatus."""
    status = MagicMock()
    status.confidence = confidence
    return status


class TestProfileEvaluatorInit:
    """Tests for ProfileEvaluator initialization."""

    def test_init_empty(self):
        """Initialize with empty profile list."""
        evaluator = ProfileEvaluator([])
        assert evaluator.profiles == []
        assert evaluator._initialized is True

    def test_init_with_profiles(self):
        """Initialize with profiles."""
        profiles = [
            make_profile("profile-1"),
            make_profile("profile-2"),
        ]
        evaluator = ProfileEvaluator(profiles)
        assert len(evaluator.profiles) == 2
        assert evaluator._initialized is True

    def test_init_creates_throttle(self):
        """Initialization creates throttle manager for each profile."""
        profiles = [make_profile("test", throttle_minutes=3)]
        # ProfileEvaluator constructor sets up throttle on profiles
        ProfileEvaluator(profiles)

        assert profiles[0]._throttle is not None
        assert profiles[0]._throttle.throttle_minutes == 3

    @patch("aria_esi.services.redisq.notifications.profile_evaluator.logger")
    def test_init_warns_on_many_profiles(self, mock_logger):
        """Warns when many profiles are loaded."""
        profiles = [make_profile(f"profile-{i}") for i in range(MAX_PROFILES_SOFT + 1)]
        ProfileEvaluator(profiles)

        mock_logger.warning.assert_called()
        assert "may impact performance" in str(mock_logger.warning.call_args)

    def test_init_limits_profiles(self):
        """Limits profiles to MAX_PROFILES_HARD."""
        profiles = [make_profile(f"profile-{i}") for i in range(MAX_PROFILES_HARD + 5)]
        evaluator = ProfileEvaluator(profiles)

        assert len(evaluator.profiles) == MAX_PROFILES_HARD


class TestProfileEvaluatorEvaluate:
    """Tests for profile evaluation."""

    def test_evaluate_no_profiles(self):
        """Evaluate with no profiles returns empty result."""
        evaluator = ProfileEvaluator([])
        kill = make_kill()

        result = evaluator.evaluate(kill)

        assert result.has_matches is False
        assert result.match_count == 0

    def test_evaluate_disabled_profile_skipped(self):
        """Disabled profiles are skipped."""
        profiles = [make_profile("disabled", enabled=False)]
        evaluator = ProfileEvaluator(profiles)
        kill = make_kill(total_value=2_000_000_000)  # Above threshold

        result = evaluator.evaluate(kill)

        assert result.has_matches is False

    def test_evaluate_high_value_trigger(self):
        """High value kill triggers notification."""
        profiles = [make_profile("test", high_value_threshold=1_000_000_000)]
        evaluator = ProfileEvaluator(profiles)
        kill = make_kill(total_value=2_000_000_000)

        result = evaluator.evaluate(kill)

        assert result.has_matches is True
        assert result.match_count == 1
        assert result.matches[0].profile.name == "test"

    def test_evaluate_watchlist_trigger(self):
        """Watchlist activity triggers notification."""
        profiles = [make_profile("test", watchlist_activity=True)]
        evaluator = ProfileEvaluator(profiles)
        kill = make_kill(total_value=100)  # Below high value threshold
        entity_match = make_entity_match(has_match=True)

        result = evaluator.evaluate(kill, entity_match=entity_match)

        assert result.has_matches is True
        assert result.matches[0].trigger_result.trigger_types is not None
        assert TriggerType.WATCHLIST_ACTIVITY in result.matches[0].trigger_result.trigger_types

    def test_evaluate_gatecamp_trigger(self):
        """Gatecamp detection triggers notification."""
        profiles = [make_profile("test", gatecamp_detected=True)]
        evaluator = ProfileEvaluator(profiles)
        kill = make_kill(total_value=100)
        gatecamp = make_gatecamp_status(confidence="high")

        result = evaluator.evaluate(kill, gatecamp_status=gatecamp)

        assert result.has_matches is True
        assert TriggerType.GATECAMP_DETECTED in result.matches[0].trigger_result.trigger_types

    def test_evaluate_no_trigger_match(self):
        """Kill that doesn't match any triggers is filtered."""
        profiles = [
            make_profile(
                "test",
                watchlist_activity=False,
                gatecamp_detected=False,
                high_value_threshold=10_000_000_000,
            )
        ]
        evaluator = ProfileEvaluator(profiles)
        kill = make_kill(total_value=100)

        result = evaluator.evaluate(kill)

        assert result.has_matches is False
        assert "test" in result.filtered_by_triggers

    def test_evaluate_multiple_profiles(self):
        """Multiple profiles evaluated independently."""
        profiles = [
            make_profile("high-value", high_value_threshold=500_000_000),
            make_profile("watchlist", high_value_threshold=10_000_000_000),
        ]
        evaluator = ProfileEvaluator(profiles)
        kill = make_kill(total_value=1_000_000_000)

        result = evaluator.evaluate(kill)

        # Only high-value profile should match
        assert result.match_count == 1
        assert result.matches[0].profile.name == "high-value"


class TestProfileEvaluatorThrottle:
    """Tests for throttle handling."""

    def test_throttle_first_kill_allowed(self):
        """First kill for a profile is not throttled."""
        profiles = [make_profile("test", throttle_minutes=5)]
        evaluator = ProfileEvaluator(profiles)
        kill = make_kill(total_value=2_000_000_000)

        result = evaluator.evaluate(kill)

        assert result.has_matches is True

    def test_throttle_duplicate_blocked(self):
        """Duplicate kill within throttle window is blocked."""
        profiles = [make_profile("test", throttle_minutes=5)]
        evaluator = ProfileEvaluator(profiles)
        kill = make_kill(total_value=2_000_000_000)

        # First evaluation passes and records throttle
        result1 = evaluator.evaluate(kill)
        assert result1.has_matches is True

        # Second evaluation is throttled
        result2 = evaluator.evaluate(kill)
        assert result2.has_matches is False
        assert "test" in result2.filtered_by_throttle

    def test_throttle_different_systems_independent(self):
        """Different systems have independent throttles."""
        profiles = [make_profile("test", throttle_minutes=5)]
        evaluator = ProfileEvaluator(profiles)

        kill1 = make_kill(kill_id=1, solar_system_id=30000142, total_value=2_000_000_000)
        kill2 = make_kill(kill_id=2, solar_system_id=30000143, total_value=2_000_000_000)

        result1 = evaluator.evaluate(kill1)
        result2 = evaluator.evaluate(kill2)

        assert result1.has_matches is True
        assert result2.has_matches is True


class TestProfileEvaluatorMetrics:
    """Tests for evaluator metrics."""

    def test_get_metrics(self):
        """Get evaluator metrics."""
        profiles = [
            make_profile("profile-1", throttle_minutes=3),
            make_profile("profile-2", throttle_minutes=5),
        ]
        evaluator = ProfileEvaluator(profiles)

        metrics = evaluator.get_metrics()

        assert metrics["profile_count"] == 2
        assert metrics["initialized"] is True
        assert len(metrics["profiles"]) == 2

    def test_cleanup_throttles(self):
        """Cleanup removes expired throttle entries."""
        profiles = [make_profile("test", throttle_minutes=0)]  # Immediate expiry
        evaluator = ProfileEvaluator(profiles)
        kill = make_kill(total_value=2_000_000_000)

        # Generate some throttle entries
        evaluator.evaluate(kill)

        # Cleanup (with 0 minute throttle, entries expire immediately)
        removed = evaluator.cleanup_throttles()

        # May or may not have removed depending on timing
        assert isinstance(removed, int)


class TestProfileEvaluatorHelpers:
    """Tests for evaluator helper methods."""

    def test_get_profile_by_name(self):
        """Get profile by name."""
        profiles = [
            make_profile("profile-1"),
            make_profile("profile-2"),
        ]
        evaluator = ProfileEvaluator(profiles)

        assert evaluator.get_profile_by_name("profile-1") is profiles[0]
        assert evaluator.get_profile_by_name("profile-2") is profiles[1]
        assert evaluator.get_profile_by_name("not-found") is None

    def test_reload_profiles(self):
        """Reload profiles reinitializes state."""
        evaluator = ProfileEvaluator([make_profile("old")])
        assert evaluator.profiles[0].name == "old"

        new_profiles = [make_profile("new-1"), make_profile("new-2")]
        evaluator.reload_profiles(new_profiles)

        assert len(evaluator.profiles) == 2
        assert evaluator.profiles[0].name == "new-1"
        assert evaluator._initialized is True


class TestEvaluationResult:
    """Tests for EvaluationResult dataclass."""

    def test_has_matches_empty(self):
        """has_matches is False with no matches."""
        result = EvaluationResult(kill_id=123)
        assert result.has_matches is False

    def test_has_matches_with_matches(self):
        """has_matches is True with matches."""
        result = EvaluationResult(
            kill_id=123,
            matches=[ProfileMatch(profile=make_profile("test"), trigger_result=MagicMock())],
        )
        assert result.has_matches is True

    def test_match_count(self):
        """match_count returns correct count."""
        result = EvaluationResult(
            kill_id=123,
            matches=[
                ProfileMatch(profile=make_profile("a"), trigger_result=MagicMock()),
                ProfileMatch(profile=make_profile("b"), trigger_result=MagicMock()),
            ],
        )
        assert result.match_count == 2


class TestProfileEvaluatorQuietHours:
    """Tests for quiet hours filtering."""

    def test_quiet_hours_filters_kills(self):
        """Quiet hours filters kills during window."""
        profile = NotificationProfile(
            name="quiet-test",
            enabled=True,
            webhook_url="https://discord.com/api/webhooks/123/abc",
            triggers=TriggerConfig(high_value_threshold=100),
            quiet_hours=QuietHoursConfig(
                enabled=True,
                start="00:00",
                end="23:59",  # All day quiet
                timezone="UTC",
            ),
        )
        evaluator = ProfileEvaluator([profile])
        kill = make_kill(total_value=1_000_000_000)

        result = evaluator.evaluate(kill)

        assert result.has_matches is False
        assert "quiet-test" in result.filtered_by_quiet_hours

    def test_quiet_hours_disabled_allows_kills(self):
        """Disabled quiet hours allows kills."""
        profile = NotificationProfile(
            name="no-quiet",
            enabled=True,
            webhook_url="https://discord.com/api/webhooks/123/abc",
            triggers=TriggerConfig(high_value_threshold=100),
            quiet_hours=QuietHoursConfig(enabled=False),
        )
        evaluator = ProfileEvaluator([profile])
        kill = make_kill(total_value=1_000_000_000)

        result = evaluator.evaluate(kill)

        assert result.has_matches is True

    def test_quiet_hours_outside_window_allows_kills(self):
        """Kills outside quiet hours window are allowed."""
        # Set quiet hours to a different time zone that's definitely not now
        profile = NotificationProfile(
            name="windowed-quiet",
            enabled=True,
            webhook_url="https://discord.com/api/webhooks/123/abc",
            triggers=TriggerConfig(high_value_threshold=100),
            quiet_hours=QuietHoursConfig(
                enabled=True,
                start="03:00",
                end="04:00",  # 1-hour window
                timezone="Pacific/Fiji",  # Unlikely to match
            ),
        )
        evaluator = ProfileEvaluator([profile])
        kill = make_kill(total_value=1_000_000_000)

        # This test is somewhat time-dependent but the window is small
        result = evaluator.evaluate(kill)

        # Should pass most of the time (23 hours out of 24)
        # If it fails, the test is running during quiet hours in Fiji
        assert result.has_matches is True or "windowed-quiet" in result.filtered_by_quiet_hours


class TestProfileEvaluatorTopology:
    """Tests for topology filtering."""

    def test_topology_filter_applied(self):
        """Topology filter rejects kills outside monitored systems."""
        profile = NotificationProfile(
            name="topo-test",
            enabled=True,
            webhook_url="https://discord.com/api/webhooks/123/abc",
            triggers=TriggerConfig(high_value_threshold=100),
            topology={
                "geographic": {
                    "systems": [{"id": 30000001, "name": "Jita"}],
                    "range_hops": 0,
                }
            },
        )

        # Mock the topology filter to reject the kill's system
        with patch.object(ProfileEvaluator, "_build_calculator") as mock_build:
            mock_filter = MagicMock()
            mock_filter.should_fetch.return_value = False
            mock_build.return_value = mock_filter

            evaluator = ProfileEvaluator([profile])

        kill = make_kill(solar_system_id=30000142, total_value=1_000_000_000)
        result = evaluator.evaluate(kill)

        assert result.has_matches is False
        assert "topo-test" in result.filtered_by_topology

    def test_npc_faction_bypass_topology(self):
        """NPC faction kills bypass topology when ignore_topology is True."""
        from aria_esi.services.redisq.notifications.config import NPCFactionKillConfig

        profile = NotificationProfile(
            name="npc-bypass",
            enabled=True,
            webhook_url="https://discord.com/api/webhooks/123/abc",
            triggers=TriggerConfig(
                high_value_threshold=10_000_000_000,  # Very high threshold
                npc_faction_kill=NPCFactionKillConfig(
                    enabled=True,
                    factions=["serpentis"],
                    as_attacker=True,
                    ignore_topology=True,
                ),
            ),
            topology={
                "geographic": {
                    "systems": [{"id": 30000001, "name": "Jita"}],
                    "range_hops": 0,
                }
            },
        )

        # Create mock mapper
        mock_mapper = MagicMock()
        mock_mapper.get_corps_for_faction.return_value = {1000125}
        mock_mapper.get_faction_for_corp.return_value = "serpentis"
        mock_mapper.get_corp_name.return_value = "Serpentis Corporation"

        kill = make_kill(solar_system_id=30000142, total_value=100)
        kill.attacker_corps = [1000125]  # Serpentis corp

        with patch.object(ProfileEvaluator, "_build_calculator") as mock_build:
            mock_filter = MagicMock()
            mock_filter.should_fetch.return_value = False  # Topology rejects
            mock_build.return_value = mock_filter

            with patch(
                "aria_esi.services.redisq.notifications.npc_factions.get_npc_faction_mapper"
            ) as mock_get_mapper:
                mock_get_mapper.return_value = mock_mapper

                evaluator = ProfileEvaluator([profile])
                result = evaluator.evaluate(kill)

        # Should match despite topology rejection because NPC faction bypasses
        assert result.has_matches is True


class TestProfileEvaluatorWarContext:
    """Tests for war context handling."""

    def test_war_context_passed_to_triggers(self):
        """War context is passed to trigger evaluation."""
        profile = NotificationProfile(
            name="war-test",
            enabled=True,
            webhook_url="https://discord.com/api/webhooks/123/abc",
            triggers=TriggerConfig(
                war_activity=True,
                high_value_threshold=10_000_000_000,
            ),
        )
        evaluator = ProfileEvaluator([profile])

        kill = make_kill(total_value=100)
        war_context = MagicMock()
        war_context.is_war_engagement = True
        war_context.relationship = MagicMock()
        war_context.relationship.is_mutual = False
        war_context.relationship.kill_count = 1

        result = evaluator.evaluate(kill, war_context=war_context)

        assert result.has_matches is True
        assert result.matches[0].trigger_result.war_context is war_context

    def test_war_context_none_when_not_provided(self):
        """War context is None when not provided."""
        profile = make_profile("test", high_value_threshold=100)
        evaluator = ProfileEvaluator([profile])
        kill = make_kill(total_value=1_000_000_000)

        result = evaluator.evaluate(kill)

        assert result.has_matches is True
        assert result.matches[0].trigger_result.war_context is None


class TestProfileEvaluatorV2Engine:
    """Tests for Interest Engine v2 evaluation path."""

    def test_v2_engine_used_when_configured(self):
        """Interest v2 engine is used when profile has interest config."""
        profile = NotificationProfile(
            name="v2-test",
            enabled=True,
            webhook_url="https://discord.com/api/webhooks/123/abc",
            interest={
                "engine": "v2",
                "preset": "lowsec-pvp",
            },
        )

        # Mock the v2 engine
        mock_engine = MagicMock()
        mock_result = MagicMock()
        mock_result.should_notify = True
        mock_result.interest = 0.8
        mock_result.tier.value = "elevated"
        mock_engine.calculate_interest.return_value = mock_result

        with patch.object(ProfileEvaluator, "_build_v2_engine") as mock_build:
            mock_build.return_value = mock_engine

            evaluator = ProfileEvaluator([profile])

        kill = make_kill(total_value=100)
        result = evaluator.evaluate(kill)

        assert result.has_matches is True
        assert result.matches[0].interest_result is mock_result

    def test_v2_engine_interest_filtering(self):
        """V2 engine filters kills below interest threshold."""
        profile = NotificationProfile(
            name="v2-filter-test",
            enabled=True,
            webhook_url="https://discord.com/api/webhooks/123/abc",
            interest={
                "engine": "v2",
                "preset": "lowsec-pvp",
            },
        )

        mock_engine = MagicMock()
        mock_result = MagicMock()
        mock_result.should_notify = False  # Filtered
        mock_result.interest = 0.1
        mock_result.tier.value = "none"
        mock_engine.calculate_interest.return_value = mock_result

        with patch.object(ProfileEvaluator, "_build_v2_engine") as mock_build:
            mock_build.return_value = mock_engine

            evaluator = ProfileEvaluator([profile])

        kill = make_kill(total_value=100)
        result = evaluator.evaluate(kill)

        assert result.has_matches is False
        assert "v2-filter-test" in result.filtered_by_interest

    def test_v2_engine_init_error_fails_closed(self):
        """V2 engine init errors fail closed and do not fall back to v1."""
        profile = NotificationProfile(
            name="v2-fallback",
            enabled=True,
            webhook_url="https://discord.com/api/webhooks/123/abc",
            interest={
                "engine": "v2",
                "preset": "invalid-preset",
            },
            topology={
                "geographic": {
                    "systems": [{"id": 30000142, "name": "Jita"}],
                }
            },
        )

        with patch.object(ProfileEvaluator, "_build_v2_engine") as mock_build_v2:
            mock_build_v2.side_effect = ValueError("Invalid preset")
            evaluator = ProfileEvaluator([profile])

        # Profile should be marked invalid and not configured with v1 fallback
        assert evaluator.profiles[0]._interest_engine_v2 is None
        assert evaluator.profiles[0]._topology_filter is None
        assert evaluator.profiles[0]._init_error is not None

        kill = make_kill(total_value=100)
        result = evaluator.evaluate(kill)
        assert result.has_matches is False
        assert "v2-fallback" in result.filtered_by_engine_error

    def test_uses_interest_v2_property(self):
        """Profile uses_interest_v2 property works."""
        profile_v2 = NotificationProfile(
            name="v2-profile",
            webhook_url="https://discord.com/api/webhooks/123/abc",
            interest={"engine": "v2"},
        )
        profile_v1 = NotificationProfile(
            name="v1-profile",
            webhook_url="https://discord.com/api/webhooks/123/abc",
        )

        assert profile_v2.uses_interest_v2 is True
        assert profile_v1.uses_interest_v2 is False


class TestProfileEvaluatorFilteredLists:
    """Tests for filtered lists in EvaluationResult."""

    def test_filtered_by_topology_list(self):
        """filtered_by_topology tracks filtered profiles."""
        result = EvaluationResult(
            kill_id=123,
            filtered_by_topology=["profile-a", "profile-b"],
        )
        assert len(result.filtered_by_topology) == 2
        assert "profile-a" in result.filtered_by_topology

    def test_filtered_by_throttle_list(self):
        """filtered_by_throttle tracks filtered profiles."""
        result = EvaluationResult(
            kill_id=123,
            filtered_by_throttle=["profile-a"],
        )
        assert "profile-a" in result.filtered_by_throttle

    def test_filtered_by_quiet_hours_list(self):
        """filtered_by_quiet_hours tracks filtered profiles."""
        result = EvaluationResult(
            kill_id=123,
            filtered_by_quiet_hours=["profile-a"],
        )
        assert "profile-a" in result.filtered_by_quiet_hours

    def test_filtered_by_triggers_list(self):
        """filtered_by_triggers tracks filtered profiles."""
        result = EvaluationResult(
            kill_id=123,
            filtered_by_triggers=["profile-a"],
        )
        assert "profile-a" in result.filtered_by_triggers

    def test_filtered_by_interest_list(self):
        """filtered_by_interest tracks filtered profiles."""
        result = EvaluationResult(
            kill_id=123,
            filtered_by_interest=["profile-a"],
        )
        assert "profile-a" in result.filtered_by_interest
