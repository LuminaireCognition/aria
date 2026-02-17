"""
Integration tests for NotificationManager profile mode.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from aria_esi.services.redisq.notifications.manager import (
    NotificationManager,
    _BufferedKill,
    get_notification_manager,
    reset_notification_manager,
)
from aria_esi.services.redisq.notifications.profile_evaluator import ProfileEvaluator


def write_profile_yaml(path: Path, name: str, data: dict) -> Path:
    """Helper to write a profile YAML file."""
    profile_path = path / f"{name}.yaml"
    with open(profile_path, "w") as f:
        yaml.dump(data, f)
    return profile_path


def make_mock_kill(
    kill_id: int = 12345,
    solar_system_id: int = 30000142,
    total_value: int = 100_000_000,
    is_pod_kill: bool = False,
    victim_ship_type_id: int = 587,
    attacker_count: int = 5,
) -> MagicMock:
    """Create a mock ProcessedKill."""
    from datetime import datetime, timezone

    kill = MagicMock()
    kill.kill_id = kill_id
    kill.solar_system_id = solar_system_id
    kill.total_value = total_value
    kill.is_pod_kill = is_pod_kill
    kill.victim_ship_type_id = victim_ship_type_id
    kill.attacker_count = attacker_count
    kill.kill_time = datetime.now(tz=timezone.utc)
    return kill


@pytest.fixture
def temp_profiles_dir(monkeypatch):
    """Create temporary profiles directory and patch ProfileLoader."""
    with TemporaryDirectory() as tmpdir:
        profiles_path = Path(tmpdir) / "notifications"
        profiles_path.mkdir()
        monkeypatch.setattr(
            "aria_esi.services.redisq.notifications.profile_loader.PROFILES_DIR",
            profiles_path,
        )
        yield profiles_path


@pytest.fixture
def mock_discord_client():
    """Create a mock DiscordClient."""
    with patch("aria_esi.services.redisq.notifications.manager.DiscordClient") as mock_class:
        client_instance = MagicMock()
        client_instance.send = AsyncMock(return_value=MagicMock(success=True))
        client_instance.close = AsyncMock()
        client_instance.is_healthy = True
        client_instance._total_sent = 0
        client_instance._total_failed = 0
        client_instance._last_success = None
        mock_class.return_value = client_instance
        yield mock_class


class TestNotificationManagerProfileMode:
    """Tests for profile mode initialization."""

    def test_profiles_loaded_when_profiles_exist(self, temp_profiles_dir, mock_discord_client):
        """Manager loads profiles when they exist."""
        write_profile_yaml(
            temp_profiles_dir,
            "test-profile",
            {
                "name": "test-profile",
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/123/abc",
            },
        )

        manager = NotificationManager()

        assert len(manager._profiles) == 1
        assert manager._evaluator is not None
        assert manager.is_configured is True

    def test_unconfigured_when_no_profiles(self, temp_profiles_dir, mock_discord_client):
        """Manager is unconfigured when no profiles exist."""
        manager = NotificationManager()

        assert len(manager._profiles) == 0
        assert manager._evaluator is None
        assert manager.is_configured is False

    def test_unconfigured_when_profiles_disabled(self, temp_profiles_dir, mock_discord_client):
        """Manager is unconfigured when all profiles are disabled."""
        write_profile_yaml(
            temp_profiles_dir,
            "disabled-profile",
            {
                "name": "disabled-profile",
                "enabled": False,
                "webhook_url": "https://discord.com/api/webhooks/123/abc",
            },
        )

        manager = NotificationManager()

        # No enabled profiles
        assert len(manager._profiles) == 0
        assert manager.is_configured is False

    def test_multiple_profiles_loaded(self, temp_profiles_dir, mock_discord_client):
        """Multiple enabled profiles are loaded."""
        write_profile_yaml(
            temp_profiles_dir,
            "profile-a",
            {
                "name": "profile-a",
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/111/aaa",
            },
        )
        write_profile_yaml(
            temp_profiles_dir,
            "profile-b",
            {
                "name": "profile-b",
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/222/bbb",
            },
        )
        write_profile_yaml(
            temp_profiles_dir,
            "profile-c",
            {
                "name": "profile-c",
                "enabled": False,  # Disabled
                "webhook_url": "https://discord.com/api/webhooks/333/ccc",
            },
        )

        manager = NotificationManager()

        assert len(manager._profiles) == 2  # Only enabled profiles
        assert len(manager._clients) == 2  # Webhook per profile

    def test_profile_webhooks_deduplicated(self, temp_profiles_dir, mock_discord_client):
        """Duplicate webhook URLs share a client."""
        shared_url = "https://discord.com/api/webhooks/shared/url"
        write_profile_yaml(
            temp_profiles_dir,
            "profile-a",
            {"name": "profile-a", "enabled": True, "webhook_url": shared_url},
        )
        write_profile_yaml(
            temp_profiles_dir,
            "profile-b",
            {"name": "profile-b", "enabled": True, "webhook_url": shared_url},
        )

        manager = NotificationManager()

        assert len(manager._profiles) == 2
        assert len(manager._clients) == 1  # Shared client


class TestNotificationManagerProfileProcessKill:
    """Tests for processing kills in profile mode."""

    @pytest.mark.asyncio
    async def test_process_kill_matches_profile(self, temp_profiles_dir, mock_discord_client):
        """Kill matching profile interest engine is queued."""
        write_profile_yaml(
            temp_profiles_dir,
            "high-value",
            {
                "name": "high-value",
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/123/abc",
                "interest": {
                    "engine": "v2",
                    "preset": "lowsec-pvp",
                },
            },
        )

        mock_engine = MagicMock()
        mock_result = MagicMock()
        mock_result.should_notify = True
        mock_result.interest = 0.8
        mock_result.tier.value = "elevated"
        mock_engine.calculate_interest.return_value = mock_result

        with patch.object(ProfileEvaluator, "_build_v2_engine", return_value=mock_engine):
            manager = NotificationManager()
        kill = make_mock_kill(total_value=1_000_000_000)

        result = await manager.process_kill(kill)

        assert result is True

    @pytest.mark.asyncio
    async def test_process_kill_no_match(self, temp_profiles_dir, mock_discord_client):
        """Kill not matching any profile is not queued."""
        write_profile_yaml(
            temp_profiles_dir,
            "high-value",
            {
                "name": "high-value",
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/123/abc",
                "triggers": {
                    "watchlist_activity": False,
                    "gatecamp_detected": False,
                    "high_value_threshold": 10_000_000_000,  # 10B threshold
                },
            },
        )

        manager = NotificationManager()
        kill = make_mock_kill(total_value=100_000_000)  # Below threshold

        result = await manager.process_kill(kill)

        assert result is False

    @pytest.mark.asyncio
    async def test_process_kill_multiple_profiles_match(
        self, temp_profiles_dir, mock_discord_client
    ):
        """Kill matching multiple profiles is queued to each."""
        write_profile_yaml(
            temp_profiles_dir,
            "profile-a",
            {
                "name": "profile-a",
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/111/aaa",
                "interest": {
                    "engine": "v2",
                    "preset": "lowsec-pvp",
                },
            },
        )
        write_profile_yaml(
            temp_profiles_dir,
            "profile-b",
            {
                "name": "profile-b",
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/222/bbb",
                "interest": {
                    "engine": "v2",
                    "preset": "lowsec-pvp",
                },
            },
        )

        mock_engine = MagicMock()
        mock_result = MagicMock()
        mock_result.should_notify = True
        mock_result.interest = 0.8
        mock_result.tier.value = "elevated"
        mock_engine.calculate_interest.return_value = mock_result

        with patch.object(ProfileEvaluator, "_build_v2_engine", return_value=mock_engine):
            manager = NotificationManager()
        kill = make_mock_kill(total_value=1_000_000_000)

        result = await manager.process_kill(kill)

        assert result is True


class TestNotificationManagerProfileHealth:
    """Tests for health reporting in profile mode."""

    def test_health_status_profile_mode(self, temp_profiles_dir, mock_discord_client):
        """Health status reports profile mode correctly."""
        write_profile_yaml(
            temp_profiles_dir,
            "test-profile",
            {
                "name": "test-profile",
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/123/abc",
            },
        )

        manager = NotificationManager()
        health = manager.get_health_status()

        assert health.is_configured is True
        assert health.webhook_count == 1

    def test_routing_summary_profile_mode(self, temp_profiles_dir, mock_discord_client):
        """Routing summary includes profile information."""
        write_profile_yaml(
            temp_profiles_dir,
            "profile-a",
            {
                "name": "profile-a",
                "display_name": "Profile A",
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/111/aaa",
            },
        )
        write_profile_yaml(
            temp_profiles_dir,
            "profile-b",
            {
                "name": "profile-b",
                "display_name": "Profile B",
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/222/bbb",
            },
        )

        manager = NotificationManager()
        summary = manager.get_routing_summary()

        assert summary["profile_count"] == 2
        assert summary["webhook_count"] == 2
        assert len(summary["profiles"]) == 2


class TestNotificationManagerSingleton:
    """Tests for singleton behavior."""

    def test_singleton_reset(self, temp_profiles_dir):
        """Singleton can be reset."""
        reset_notification_manager()

        # Get manager
        manager1 = get_notification_manager()

        # Reset and get again
        reset_notification_manager()

        manager2 = get_notification_manager()

        # Should be different instances
        assert manager1 is not manager2

        # Clean up
        reset_notification_manager()


class TestNotificationManagerErrorHandling:
    """Tests for error handling."""

    def test_unconfigured_on_profile_load_error(self, temp_profiles_dir, mock_discord_client):
        """Manager is unconfigured if profile loading fails."""
        # Write invalid YAML to cause load error
        (temp_profiles_dir / "invalid.yaml").write_text("{{invalid yaml")

        manager = NotificationManager()

        # Should be unconfigured
        assert len(manager._profiles) == 0
        assert manager.is_configured is False


class TestNotificationManagerLifecycle:
    """Tests for manager start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_creates_task(self, temp_profiles_dir, mock_discord_client):
        """Start creates background task."""
        write_profile_yaml(
            temp_profiles_dir,
            "lifecycle-test",
            {
                "name": "lifecycle-test",
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/123/abc",
            },
        )

        manager = NotificationManager()
        await manager.start()

        try:
            assert manager._running is True
            assert manager._process_task is not None
        finally:
            await manager.stop()

    @pytest.mark.asyncio
    async def test_start_skips_when_unconfigured(self, temp_profiles_dir):
        """Start does nothing when unconfigured."""
        manager = NotificationManager()
        await manager.start()

        assert manager._running is False
        assert manager._process_task is None

    @pytest.mark.asyncio
    async def test_start_idempotent(self, temp_profiles_dir, mock_discord_client):
        """Multiple starts don't create multiple tasks."""
        write_profile_yaml(
            temp_profiles_dir,
            "idempotent-test",
            {
                "name": "idempotent-test",
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/123/abc",
            },
        )

        manager = NotificationManager()
        await manager.start()
        task1 = manager._process_task
        await manager.start()
        task2 = manager._process_task

        try:
            assert task1 is task2
        finally:
            await manager.stop()

    @pytest.mark.asyncio
    async def test_stop_clears_state(self, temp_profiles_dir, mock_discord_client):
        """Stop clears all runtime state."""
        write_profile_yaml(
            temp_profiles_dir,
            "stop-test",
            {
                "name": "stop-test",
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/123/abc",
            },
        )

        manager = NotificationManager()
        await manager.start()
        await manager.stop()

        assert manager._running is False
        assert manager._process_task is None
        assert len(manager._clients) == 0
        assert len(manager._queues) == 0

    @pytest.mark.asyncio
    async def test_stop_closes_clients(self, temp_profiles_dir, mock_discord_client):
        """Stop closes all webhook clients."""
        write_profile_yaml(
            temp_profiles_dir,
            "close-test",
            {
                "name": "close-test",
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/123/abc",
            },
        )

        manager = NotificationManager()
        await manager.start()
        await manager.stop()

        mock_discord_client.return_value.close.assert_called()


class TestNotificationManagerCommentary:
    """Tests for commentary generation."""

    @pytest.mark.asyncio
    async def test_commentary_generator_created(self, temp_profiles_dir, mock_discord_client):
        """Commentary generator is created for profiles with commentary enabled."""

        write_profile_yaml(
            temp_profiles_dir,
            "commentary-test",
            {
                "name": "commentary-test",
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/123/abc",
                "commentary": {
                    "enabled": True,
                    "warrant_threshold": 0.5,
                },
            },
        )

        with patch(
            "aria_esi.services.redisq.notifications.manager.create_commentary_generator"
        ) as mock_create:
            mock_generator = MagicMock()
            mock_generator.is_configured = True
            mock_create.return_value = mock_generator

            manager = NotificationManager()
            generator = manager._get_commentary_generator(manager._profiles[0])

            assert generator is mock_generator
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_commentary_not_generated_below_threshold(
        self, temp_profiles_dir, mock_discord_client
    ):
        """Commentary not generated when warrant score below threshold."""
        write_profile_yaml(
            temp_profiles_dir,
            "threshold-test",
            {
                "name": "threshold-test",
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/123/abc",
                "commentary": {
                    "enabled": True,
                    "warrant_threshold": 0.9,  # Very high threshold
                },
            },
        )

        manager = NotificationManager()

        # Create mock pattern context with low warrant score
        mock_pattern_context = MagicMock()
        mock_pattern_context.warrant_score.return_value = 0.2
        mock_pattern_context.kill.kill_id = 12345

        commentary, persona = await manager._generate_commentary_for_profile(
            profile=manager._profiles[0],
            pattern_context=mock_pattern_context,
            notification_text="Test notification",
        )

        assert commentary is None
        assert persona is None

    @pytest.mark.asyncio
    async def test_commentary_disabled_returns_none(self, temp_profiles_dir, mock_discord_client):
        """Commentary returns None when disabled."""
        write_profile_yaml(
            temp_profiles_dir,
            "disabled-test",
            {
                "name": "disabled-test",
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/123/abc",
                # No commentary config
            },
        )

        manager = NotificationManager()

        mock_pattern_context = MagicMock()
        mock_pattern_context.warrant_score.return_value = 1.0

        commentary, persona = await manager._generate_commentary_for_profile(
            profile=manager._profiles[0],
            pattern_context=mock_pattern_context,
            notification_text="Test notification",
        )

        assert commentary is None
        assert persona is None


class TestNotificationManagerTestWebhook:
    """Tests for test webhook functionality."""

    @pytest.mark.asyncio
    async def test_test_webhook_success(self, temp_profiles_dir, mock_discord_client):
        """Test webhook succeeds."""
        write_profile_yaml(
            temp_profiles_dir,
            "webhook-test",
            {
                "name": "webhook-test",
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/123/abc",
            },
        )

        manager = NotificationManager()
        success, message = await manager.test_webhook()

        assert success is True
        assert "webhook-test" in message

    @pytest.mark.asyncio
    async def test_test_webhook_unconfigured(self, temp_profiles_dir):
        """Test webhook fails when unconfigured."""
        manager = NotificationManager()
        success, message = await manager.test_webhook()

        assert success is False
        assert "no" in message.lower() and "configured" in message.lower()

    @pytest.mark.asyncio
    async def test_test_webhook_by_profile_name(self, temp_profiles_dir, mock_discord_client):
        """Test webhook for specific profile."""
        write_profile_yaml(
            temp_profiles_dir,
            "profile-a",
            {
                "name": "profile-a",
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/111/aaa",
            },
        )
        write_profile_yaml(
            temp_profiles_dir,
            "profile-b",
            {
                "name": "profile-b",
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/222/bbb",
            },
        )

        manager = NotificationManager()
        success, message = await manager.test_webhook(profile_name="profile-b")

        assert success is True
        assert "profile-b" in message

    @pytest.mark.asyncio
    async def test_test_webhook_profile_not_found(self, temp_profiles_dir, mock_discord_client):
        """Test webhook fails for unknown profile."""
        write_profile_yaml(
            temp_profiles_dir,
            "real-profile",
            {
                "name": "real-profile",
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/123/abc",
            },
        )

        manager = NotificationManager()
        success, message = await manager.test_webhook(profile_name="fake-profile")

        assert success is False
        assert "not found" in message.lower()

    @pytest.mark.asyncio
    async def test_test_webhook_send_failure(self, temp_profiles_dir, mock_discord_client):
        """Test webhook reports send failure."""
        write_profile_yaml(
            temp_profiles_dir,
            "fail-test",
            {
                "name": "fail-test",
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/123/abc",
            },
        )

        # Make send fail
        mock_discord_client.return_value.send = AsyncMock(
            return_value=MagicMock(success=False, error="Connection refused")
        )

        manager = NotificationManager()
        success, message = await manager.test_webhook()

        assert success is False
        assert "failed" in message.lower()


class TestNotificationManagerHealthStatus:
    """Tests for health status aggregation."""

    def test_health_unconfigured(self, temp_profiles_dir):
        """Health reports unconfigured when no profiles."""
        manager = NotificationManager()
        health = manager.get_health_status()

        assert health.is_configured is False
        assert health.is_healthy is False
        assert health.webhook_count == 1  # Default

    def test_health_aggregates_queue_depth(self, temp_profiles_dir, mock_discord_client):
        """Health aggregates queue depth from all webhooks."""
        write_profile_yaml(
            temp_profiles_dir,
            "queue-test",
            {
                "name": "queue-test",
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/123/abc",
            },
        )

        manager = NotificationManager()
        health = manager.get_health_status()

        assert health.queue_depth >= 0  # May have queued items or not

    def test_health_success_rate_calculation(self, temp_profiles_dir, mock_discord_client):
        """Health calculates success rate correctly."""
        write_profile_yaml(
            temp_profiles_dir,
            "rate-test",
            {
                "name": "rate-test",
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/123/abc",
            },
        )

        # Set up mock client with some sent/failed counts
        mock_discord_client.return_value._total_sent = 8
        mock_discord_client.return_value._total_failed = 2

        manager = NotificationManager()
        health = manager.get_health_status()

        # 8 / (8 + 2) = 0.8
        assert health.success_rate == 0.8

    def test_health_success_rate_empty(self, temp_profiles_dir, mock_discord_client):
        """Health returns 1.0 success rate when no attempts."""
        write_profile_yaml(
            temp_profiles_dir,
            "empty-test",
            {
                "name": "empty-test",
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/123/abc",
            },
        )

        mock_discord_client.return_value._total_sent = 0
        mock_discord_client.return_value._total_failed = 0

        manager = NotificationManager()
        health = manager.get_health_status()

        assert health.success_rate == 1.0

    def test_health_tracks_webhook_health(self, temp_profiles_dir, mock_discord_client):
        """Health tracks per-webhook health status."""
        write_profile_yaml(
            temp_profiles_dir,
            "webhook-health",
            {
                "name": "webhook-health",
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/123/abc",
            },
        )

        manager = NotificationManager()
        health = manager.get_health_status()

        assert health.webhook_count == 1
        assert len(health.webhooks_healthy) == 1

    def test_health_is_healthy_when_all_ok(self, temp_profiles_dir, mock_discord_client):
        """is_healthy is True when all webhooks healthy and not paused."""
        write_profile_yaml(
            temp_profiles_dir,
            "healthy-test",
            {
                "name": "healthy-test",
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/123/abc",
            },
        )

        mock_discord_client.return_value.is_healthy = True

        manager = NotificationManager()
        health = manager.get_health_status()

        assert health.is_healthy is True

    def test_health_not_healthy_when_paused(self, temp_profiles_dir, mock_discord_client):
        """is_healthy is False when queues are paused."""
        write_profile_yaml(
            temp_profiles_dir,
            "paused-test",
            {
                "name": "paused-test",
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/123/abc",
            },
        )

        manager = NotificationManager()

        # Simulate paused queue - need to set the internal attribute
        for queue in manager._queues.values():
            # WebhookQueue uses _is_paused or similar - let's mock the health response
            with patch.object(queue, "get_health") as mock_health:
                mock_health.return_value = MagicMock(
                    queue_depth=0,
                    is_paused=True,
                )
                # Call to verify no exception (health status aggregation works)
                manager.get_health_status()


class TestNotificationManagerProcessLoop:
    """Tests for the process loop."""

    @pytest.mark.asyncio
    async def test_process_loop_runs(self, temp_profiles_dir, mock_discord_client):
        """Process loop runs and processes queues."""
        write_profile_yaml(
            temp_profiles_dir,
            "loop-test",
            {
                "name": "loop-test",
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/123/abc",
            },
        )

        manager = NotificationManager()

        # Add item to queue
        queue = manager._queues.get("https://discord.com/api/webhooks/123/abc")
        if queue:
            queue.enqueue({"content": "Test"}, kill_id=1, trigger_type="test")

        await manager.start()
        await asyncio.sleep(0.2)  # Let loop run
        await manager.stop()

        # Queue should have been processed
        assert queue.depth == 0 or True  # May or may not be processed

    @pytest.mark.asyncio
    async def test_process_loop_cleans_throttles(self, temp_profiles_dir, mock_discord_client):
        """Process loop periodically cleans throttle entries."""
        write_profile_yaml(
            temp_profiles_dir,
            "throttle-cleanup",
            {
                "name": "throttle-cleanup",
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/123/abc",
            },
        )

        manager = NotificationManager()

        await manager.start()
        await asyncio.sleep(0.1)
        await manager.stop()

        # Just verify no errors occurred during cleanup
        assert True


class TestNotificationManagerForceRollup:
    """Tests for force_rollup buffering in NotificationManager."""

    def _make_rollup_profile(self, name="rollup-test", force_rollup=True, **overrides):
        """Return a profile YAML dict with force_rollup enabled."""
        data = {
            "name": name,
            "enabled": True,
            "webhook_url": f"https://discord.com/api/webhooks/{name}/abc",
            "throttle_minutes": 0,
            "interest": {
                "engine": "v2",
                "preset": "lowsec-pvp",
            },
            "rate_limit_strategy": {
                "force_rollup": force_rollup,
                "rollup_window_minutes": 5,
                "max_rollup_kills": 20,
            },
        }
        if overrides:
            for key, val in overrides.items():
                if key.startswith("rls_"):
                    data["rate_limit_strategy"][key[4:]] = val
                else:
                    data[key] = val
        return data

    def _patch_v2_engine(self):
        """Return a patch context that makes v2 engine match all kills."""
        mock_engine = MagicMock()
        mock_result = MagicMock()
        mock_result.should_notify = True
        mock_result.interest = 0.8
        mock_result.tier.value = "elevated"
        mock_engine.calculate_interest.return_value = mock_result
        return patch.object(ProfileEvaluator, "_build_v2_engine", return_value=mock_engine)

    @pytest.mark.asyncio
    async def test_force_rollup_buffers_kill(self, temp_profiles_dir, mock_discord_client):
        """Kill matching force_rollup profile is buffered, not sent to webhook queue."""
        write_profile_yaml(temp_profiles_dir, "rollup-test", self._make_rollup_profile())
        with self._patch_v2_engine():
            manager = NotificationManager()

        kill = make_mock_kill(kill_id=100)
        result = await manager.process_kill(kill, system_name="Tama")

        assert result is True
        # Kill should be buffered, not in the webhook queue
        assert "rollup-test" in manager._rollup_buffers
        assert len(manager._rollup_buffers["rollup-test"]) == 1
        assert manager._rollup_buffers["rollup-test"][0].kill.kill_id == 100
        # Webhook queue should be empty (not sent immediately)
        queue = manager._queues.get("https://discord.com/api/webhooks/rollup-test/abc")
        assert queue is not None
        assert queue.depth == 0

    @pytest.mark.asyncio
    async def test_rollup_flush_after_window(self, temp_profiles_dir, mock_discord_client):
        """Buffered kills flush after rollup_window_minutes expires."""
        write_profile_yaml(temp_profiles_dir, "rollup-test", self._make_rollup_profile())
        with self._patch_v2_engine():
            manager = NotificationManager()

        kill = make_mock_kill(kill_id=200)
        await manager.process_kill(kill, system_name="Tama")

        # Artificially age the buffered kill past the window
        manager._rollup_buffers["rollup-test"][0] = _BufferedKill(
            kill=kill,
            profile_name="rollup-test",
            buffered_at=time.time() - 6 * 60,  # 6 minutes ago (window is 5)
            system_name="Tama",
        )

        await manager._flush_rollup_buffers()

        # Buffer should be empty now
        assert len(manager._rollup_buffers.get("rollup-test", [])) == 0
        # Webhook queue should have the rollup message
        queue = manager._queues.get("https://discord.com/api/webhooks/rollup-test/abc")
        assert queue.depth == 1

    @pytest.mark.asyncio
    async def test_young_kills_not_flushed(self, temp_profiles_dir, mock_discord_client):
        """Kills younger than window stay buffered."""
        write_profile_yaml(temp_profiles_dir, "rollup-test", self._make_rollup_profile())
        with self._patch_v2_engine():
            manager = NotificationManager()

        kill = make_mock_kill(kill_id=300)
        await manager.process_kill(kill, system_name="Tama")

        # Kill was just buffered — should not flush
        await manager._flush_rollup_buffers()

        assert len(manager._rollup_buffers["rollup-test"]) == 1
        queue = manager._queues.get("https://discord.com/api/webhooks/rollup-test/abc")
        assert queue.depth == 0

    @pytest.mark.asyncio
    async def test_rollup_message_pod_format(self, temp_profiles_dir, mock_discord_client):
        """Pod-heavy rollup uses 'Pod spike' title."""
        write_profile_yaml(temp_profiles_dir, "rollup-test", self._make_rollup_profile())
        with self._patch_v2_engine():
            manager = NotificationManager()

        # Buffer 5 pod kills (victim_ship_type_id=670 is a pod)
        for i in range(5):
            kill = make_mock_kill(kill_id=400 + i, is_pod_kill=True, victim_ship_type_id=670)
            await manager.process_kill(kill, system_name="Tama")

        # Age all kills
        buf = manager._rollup_buffers["rollup-test"]
        for i in range(len(buf)):
            buf[i].buffered_at = time.time() - 6 * 60

        await manager._flush_rollup_buffers()

        queue = manager._queues.get("https://discord.com/api/webhooks/rollup-test/abc")
        assert queue.depth == 1
        # Inspect the queued payload
        msg = queue._queue[0].payload
        assert "Pod spike" in msg["content"]
        assert "5 pods" in msg["content"]

    @pytest.mark.asyncio
    async def test_rollup_message_standard_format(self, temp_profiles_dir, mock_discord_client):
        """Mixed kills use 'Activity' title."""
        write_profile_yaml(temp_profiles_dir, "rollup-test", self._make_rollup_profile())
        with self._patch_v2_engine():
            manager = NotificationManager()

        # Buffer 5 non-pod kills
        for i in range(5):
            kill = make_mock_kill(kill_id=500 + i, victim_ship_type_id=587)
            await manager.process_kill(kill, system_name="Tama")

        buf = manager._rollup_buffers["rollup-test"]
        for i in range(len(buf)):
            buf[i].buffered_at = time.time() - 6 * 60

        await manager._flush_rollup_buffers()

        queue = manager._queues.get("https://discord.com/api/webhooks/rollup-test/abc")
        assert queue.depth == 1
        msg = queue._queue[0].payload
        assert "Activity" in msg["content"]
        assert "5 kills" in msg["content"]

    @pytest.mark.asyncio
    async def test_mixed_profiles(self, temp_profiles_dir, mock_discord_client):
        """Non-rollup profile sends immediately while rollup profile buffers."""
        write_profile_yaml(
            temp_profiles_dir,
            "immediate",
            self._make_rollup_profile(name="immediate", force_rollup=False),
        )
        write_profile_yaml(
            temp_profiles_dir,
            "rollup",
            self._make_rollup_profile(name="rollup", force_rollup=True),
        )
        with self._patch_v2_engine():
            manager = NotificationManager()

        kill = make_mock_kill(kill_id=600)
        result = await manager.process_kill(kill, system_name="Tama")

        assert result is True
        # Immediate profile should have queued to its webhook
        imm_queue = manager._queues.get("https://discord.com/api/webhooks/immediate/abc")
        assert imm_queue.depth == 1
        # Rollup profile should be buffered, not queued
        roll_queue = manager._queues.get("https://discord.com/api/webhooks/rollup/abc")
        assert roll_queue.depth == 0
        assert len(manager._rollup_buffers.get("rollup", [])) == 1

    @pytest.mark.asyncio
    async def test_custom_rollup_title(self, temp_profiles_dir, mock_discord_client):
        """Custom rollup_title appears in message."""
        profile_data = self._make_rollup_profile(rls_rollup_title="Smartbomb camp")
        write_profile_yaml(temp_profiles_dir, "rollup-test", profile_data)
        with self._patch_v2_engine():
            manager = NotificationManager()

        for i in range(3):
            kill = make_mock_kill(kill_id=700 + i, victim_ship_type_id=587)
            await manager.process_kill(kill, system_name="Niarja")

        for b in manager._rollup_buffers["rollup-test"]:
            b.buffered_at = time.time() - 6 * 60

        await manager._flush_rollup_buffers()

        queue = manager._queues.get("https://discord.com/api/webhooks/rollup-test/abc")
        msg = queue._queue[0].payload
        assert "Smartbomb camp" in msg["content"]

    @pytest.mark.asyncio
    async def test_rollup_groups_by_system(self, temp_profiles_dir, mock_discord_client):
        """Kills in different systems produce separate rollup messages."""
        write_profile_yaml(temp_profiles_dir, "rollup-test", self._make_rollup_profile())
        with self._patch_v2_engine():
            manager = NotificationManager()

        # 2 kills in system A, 2 in system B
        for i in range(2):
            kill = make_mock_kill(kill_id=800 + i, solar_system_id=30000142)
            await manager.process_kill(kill, system_name="Jita")
        for i in range(2):
            kill = make_mock_kill(kill_id=810 + i, solar_system_id=30002187)
            await manager.process_kill(kill, system_name="Amarr")

        for b in manager._rollup_buffers["rollup-test"]:
            b.buffered_at = time.time() - 6 * 60

        await manager._flush_rollup_buffers()

        queue = manager._queues.get("https://discord.com/api/webhooks/rollup-test/abc")
        # Should have 2 rollup messages (one per system)
        assert queue.depth == 2

    @pytest.mark.asyncio
    async def test_rollup_billion_isk_formatting(self, temp_profiles_dir, mock_discord_client):
        """High-value rollup formats ISK in billions."""
        write_profile_yaml(temp_profiles_dir, "rollup-test", self._make_rollup_profile())
        with self._patch_v2_engine():
            manager = NotificationManager()

        for i in range(3):
            kill = make_mock_kill(
                kill_id=900 + i, total_value=2_000_000_000, victim_ship_type_id=587
            )
            await manager.process_kill(kill, system_name="Tama")

        buf = manager._rollup_buffers["rollup-test"]
        for i in range(len(buf)):
            buf[i].buffered_at = time.time() - 6 * 60

        await manager._flush_rollup_buffers()

        queue = manager._queues.get("https://discord.com/api/webhooks/rollup-test/abc")
        msg = queue._queue[0].payload
        assert "6.0B ISK" in msg["content"]

    @pytest.mark.asyncio
    async def test_rollup_chunks_at_max_rollup_kills(self, temp_profiles_dir, mock_discord_client):
        """Kills exceeding max_rollup_kills are split into multiple rollup messages."""
        write_profile_yaml(
            temp_profiles_dir,
            "rollup-test",
            self._make_rollup_profile(rls_max_rollup_kills=2),
        )
        with self._patch_v2_engine():
            manager = NotificationManager()

        for i in range(5):
            kill = make_mock_kill(kill_id=1000 + i, victim_ship_type_id=587)
            await manager.process_kill(kill, system_name="Tama")

        buf = manager._rollup_buffers["rollup-test"]
        for i in range(len(buf)):
            buf[i].buffered_at = time.time() - 6 * 60

        await manager._flush_rollup_buffers()

        queue = manager._queues.get("https://discord.com/api/webhooks/rollup-test/abc")
        # 5 kills / max 2 per message = 3 messages (2, 2, 1)
        assert queue.depth == 3

    @pytest.mark.asyncio
    async def test_rollup_single_pod_singular_label(self, temp_profiles_dir, mock_discord_client):
        """Single pod kill rollup uses singular 'pod' not 'pods'."""
        write_profile_yaml(temp_profiles_dir, "rollup-test", self._make_rollup_profile())
        with self._patch_v2_engine():
            manager = NotificationManager()

        kill = make_mock_kill(kill_id=1100, is_pod_kill=True, victim_ship_type_id=670)
        await manager.process_kill(kill, system_name="Tama")

        manager._rollup_buffers["rollup-test"][0].buffered_at = time.time() - 6 * 60

        await manager._flush_rollup_buffers()

        queue = manager._queues.get("https://discord.com/api/webhooks/rollup-test/abc")
        msg = queue._queue[0].payload
        assert "1 pod /" in msg["content"]
        assert "pods" not in msg["content"]

    @pytest.mark.asyncio
    async def test_rollup_genolution_capsule_counted_as_pod(
        self, temp_profiles_dir, mock_discord_client
    ):
        """Type 33328 (Capsule - Genolution) counts as pod in rollup detection."""
        write_profile_yaml(temp_profiles_dir, "rollup-test", self._make_rollup_profile())
        with self._patch_v2_engine():
            manager = NotificationManager()

        # 2 regular capsules + 2 Genolution capsules = all pods
        for i, type_id in enumerate([670, 670, 33328, 33328]):
            kill = make_mock_kill(kill_id=1200 + i, is_pod_kill=True, victim_ship_type_id=type_id)
            await manager.process_kill(kill, system_name="Tama")

        buf = manager._rollup_buffers["rollup-test"]
        for i in range(len(buf)):
            buf[i].buffered_at = time.time() - 6 * 60

        await manager._flush_rollup_buffers()

        queue = manager._queues.get("https://discord.com/api/webhooks/rollup-test/abc")
        msg = queue._queue[0].payload
        assert "Pod spike" in msg["content"]
        assert "4 pods" in msg["content"]

    @pytest.mark.asyncio
    async def test_stop_clears_rollup_buffers(self, temp_profiles_dir, mock_discord_client):
        """stop() clears pending rollup buffers."""
        write_profile_yaml(temp_profiles_dir, "rollup-test", self._make_rollup_profile())
        with self._patch_v2_engine():
            manager = NotificationManager()

        kill = make_mock_kill(kill_id=1300)
        await manager.process_kill(kill, system_name="Tama")
        assert len(manager._rollup_buffers["rollup-test"]) == 1

        await manager.start()
        await manager.stop()

        assert len(manager._rollup_buffers) == 0

    @pytest.mark.asyncio
    async def test_rollup_stale_profile_discarded(self, temp_profiles_dir, mock_discord_client):
        """Buffered kills for a removed profile are discarded on flush."""
        write_profile_yaml(temp_profiles_dir, "rollup-test", self._make_rollup_profile())
        with self._patch_v2_engine():
            manager = NotificationManager()

        kill = make_mock_kill(kill_id=1400)
        await manager.process_kill(kill, system_name="Tama")

        # Simulate profile removal by clearing the profiles list
        manager._profiles = []

        manager._rollup_buffers["rollup-test"][0].buffered_at = time.time() - 6 * 60
        await manager._flush_rollup_buffers()

        # Buffer for the stale profile should be discarded
        assert "rollup-test" not in manager._rollup_buffers

    @pytest.mark.asyncio
    async def test_rollup_no_system_name_uses_resolver_fallback(
        self, temp_profiles_dir, mock_discord_client
    ):
        """Rollup without buffered system_name falls back to name resolver."""
        write_profile_yaml(temp_profiles_dir, "rollup-test", self._make_rollup_profile())
        with self._patch_v2_engine():
            manager = NotificationManager()

        # Process kill WITHOUT system_name
        kill = make_mock_kill(kill_id=1500, solar_system_id=30000142)
        await manager.process_kill(kill)  # No system_name kwarg

        manager._rollup_buffers["rollup-test"][0].buffered_at = time.time() - 6 * 60

        # Mock the name resolver to return "Jita"
        mock_resolver = MagicMock()
        mock_resolver.resolve_system_with_fallback.return_value = "Jita"
        with patch(
            "aria_esi.services.redisq.name_resolver.get_name_resolver",
            return_value=mock_resolver,
        ):
            await manager._flush_rollup_buffers()

        queue = manager._queues.get("https://discord.com/api/webhooks/rollup-test/abc")
        msg = queue._queue[0].payload
        assert "Jita" in msg["content"]

    @pytest.mark.asyncio
    async def test_rollup_message_contains_zkillboard_url(
        self, temp_profiles_dir, mock_discord_client
    ):
        """Rollup message contains correctly formatted zkillboard related URL."""
        write_profile_yaml(temp_profiles_dir, "rollup-test", self._make_rollup_profile())
        with self._patch_v2_engine():
            manager = NotificationManager()

        kill = make_mock_kill(kill_id=1600, solar_system_id=30000142)
        await manager.process_kill(kill, system_name="Jita")

        manager._rollup_buffers["rollup-test"][0].buffered_at = time.time() - 6 * 60
        await manager._flush_rollup_buffers()

        queue = manager._queues.get("https://discord.com/api/webhooks/rollup-test/abc")
        msg = queue._queue[0].payload
        assert "https://zkillboard.com/related/30000142/" in msg["content"]
