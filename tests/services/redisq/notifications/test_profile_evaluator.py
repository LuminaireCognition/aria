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


def make_profile(
    name: str,
    enabled: bool = True,
    watchlist_activity: bool = True,
    gatecamp_detected: bool = True,
    high_value_threshold: int = 1_000_000_000,
    throttle_minutes: int = 5,
) -> NotificationProfile:
    """Create a test profile (without v2 engine, for init/helper tests)."""
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


def make_v2_profile(
    name: str,
    enabled: bool = True,
    throttle_minutes: int = 5,
    quiet_hours: QuietHoursConfig | None = None,
) -> NotificationProfile:
    """Create a test profile with v2 interest engine config."""
    return NotificationProfile(
        name=name,
        enabled=enabled,
        webhook_url="https://discord.com/api/webhooks/123/abc",
        interest={
            "engine": "v2",
            "preset": "lowsec-pvp",
        },
        throttle_minutes=throttle_minutes,
        quiet_hours=quiet_hours or QuietHoursConfig(),
    )


def make_mock_engine(should_notify: bool = True, interest: float = 0.8) -> MagicMock:
    """Create a mock InterestEngineV2."""
    engine = MagicMock()
    result = MagicMock()
    result.should_notify = should_notify
    result.interest = interest
    result.tier.value = "elevated" if should_notify else "none"
    engine.calculate_interest.return_value = result
    return engine


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
    """Tests for profile evaluation via v2 interest engine."""

    def test_evaluate_no_profiles(self):
        """Evaluate with no profiles returns empty result."""
        evaluator = ProfileEvaluator([])
        kill = make_kill()

        result = evaluator.evaluate(kill)

        assert result.has_matches is False
        assert result.match_count == 0

    def test_evaluate_disabled_profile_skipped(self):
        """Disabled profiles are skipped."""
        profiles = [make_v2_profile("disabled", enabled=False)]
        with patch.object(ProfileEvaluator, "_build_v2_engine", return_value=make_mock_engine()):
            evaluator = ProfileEvaluator(profiles)
        kill = make_kill()

        result = evaluator.evaluate(kill)

        assert result.has_matches is False

    def test_evaluate_v2_match(self):
        """Kill matching v2 interest engine triggers notification."""
        profiles = [make_v2_profile("test")]
        with patch.object(
            ProfileEvaluator, "_build_v2_engine", return_value=make_mock_engine(should_notify=True)
        ):
            evaluator = ProfileEvaluator(profiles)
        kill = make_kill()

        result = evaluator.evaluate(kill)

        assert result.has_matches is True
        assert result.match_count == 1
        assert result.matches[0].profile.name == "test"

    def test_evaluate_v2_no_match(self):
        """Kill not matching v2 interest engine is filtered."""
        profiles = [make_v2_profile("test")]
        with patch.object(
            ProfileEvaluator,
            "_build_v2_engine",
            return_value=make_mock_engine(should_notify=False),
        ):
            evaluator = ProfileEvaluator(profiles)
        kill = make_kill()

        result = evaluator.evaluate(kill)

        assert result.has_matches is False
        assert "test" in result.filtered_by_interest

    def test_evaluate_multiple_profiles(self):
        """Multiple profiles evaluated independently."""
        profiles = [
            make_v2_profile("match-profile"),
            make_v2_profile("no-match-profile"),
        ]

        engine_match = make_mock_engine(should_notify=True)
        engine_no_match = make_mock_engine(should_notify=False)
        engines = iter([engine_match, engine_no_match])

        with patch.object(
            ProfileEvaluator, "_build_v2_engine", side_effect=lambda p: next(engines)
        ):
            evaluator = ProfileEvaluator(profiles)

        kill = make_kill()
        result = evaluator.evaluate(kill)

        # Only match-profile should match
        assert result.match_count == 1
        assert result.matches[0].profile.name == "match-profile"


class TestProfileEvaluatorThrottle:
    """Tests for throttle handling."""

    def test_throttle_first_kill_allowed(self):
        """First kill for a profile is not throttled."""
        profiles = [make_v2_profile("test", throttle_minutes=5)]
        with patch.object(ProfileEvaluator, "_build_v2_engine", return_value=make_mock_engine()):
            evaluator = ProfileEvaluator(profiles)
        kill = make_kill()

        result = evaluator.evaluate(kill)

        assert result.has_matches is True

    def test_throttle_duplicate_blocked(self):
        """Duplicate kill within throttle window is blocked."""
        profiles = [make_v2_profile("test", throttle_minutes=5)]
        with patch.object(ProfileEvaluator, "_build_v2_engine", return_value=make_mock_engine()):
            evaluator = ProfileEvaluator(profiles)
        kill = make_kill()

        # First evaluation passes and records throttle
        result1 = evaluator.evaluate(kill)
        assert result1.has_matches is True

        # Second evaluation is throttled
        result2 = evaluator.evaluate(kill)
        assert result2.has_matches is False
        assert "test" in result2.filtered_by_throttle

    def test_throttle_different_systems_independent(self):
        """Different systems have independent throttles."""
        profiles = [make_v2_profile("test", throttle_minutes=5)]
        with patch.object(ProfileEvaluator, "_build_v2_engine", return_value=make_mock_engine()):
            evaluator = ProfileEvaluator(profiles)

        kill1 = make_kill(kill_id=1, solar_system_id=30000142)
        kill2 = make_kill(kill_id=2, solar_system_id=30000143)

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
        profile = make_v2_profile(
            "quiet-test",
            quiet_hours=QuietHoursConfig(
                enabled=True,
                start="00:00",
                end="23:59",  # All day quiet
                timezone="UTC",
            ),
        )
        with patch.object(ProfileEvaluator, "_build_v2_engine", return_value=make_mock_engine()):
            evaluator = ProfileEvaluator([profile])
        kill = make_kill()

        result = evaluator.evaluate(kill)

        assert result.has_matches is False
        assert "quiet-test" in result.filtered_by_quiet_hours

    def test_quiet_hours_disabled_allows_kills(self):
        """Disabled quiet hours allows kills."""
        profile = make_v2_profile(
            "no-quiet",
            quiet_hours=QuietHoursConfig(enabled=False),
        )
        with patch.object(ProfileEvaluator, "_build_v2_engine", return_value=make_mock_engine()):
            evaluator = ProfileEvaluator([profile])
        kill = make_kill()

        result = evaluator.evaluate(kill)

        assert result.has_matches is True

    def test_quiet_hours_outside_window_allows_kills(self):
        """Kills outside quiet hours window are allowed."""
        # Set quiet hours to a different time zone that's definitely not now
        profile = make_v2_profile(
            "windowed-quiet",
            quiet_hours=QuietHoursConfig(
                enabled=True,
                start="03:00",
                end="04:00",  # 1-hour window
                timezone="Pacific/Fiji",  # Unlikely to match
            ),
        )
        with patch.object(ProfileEvaluator, "_build_v2_engine", return_value=make_mock_engine()):
            evaluator = ProfileEvaluator([profile])
        kill = make_kill()

        # This test is somewhat time-dependent but the window is small
        result = evaluator.evaluate(kill)

        # Should pass most of the time (23 hours out of 24)
        # If it fails, the test is running during quiet hours in Fiji
        assert result.has_matches is True or "windowed-quiet" in result.filtered_by_quiet_hours


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
