"""Tests for WorkerSupervisor."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import pytest_asyncio

pytestmark = pytest.mark.asyncio

from aria_esi.services.killmail_store import SQLiteKillmailStore
from aria_esi.services.redisq.notifications.profiles import (
    NotificationProfile,
    PollingConfig,
)
from aria_esi.services.redisq.notifications.supervisor import WorkerSupervisor


def make_profile(name: str, enabled: bool = True) -> NotificationProfile:
    """Create a test profile."""
    return NotificationProfile(
        name=name,
        display_name=name.title(),
        enabled=enabled,
        webhook_url=f"https://discord.com/api/webhooks/123/{name}",
        polling=PollingConfig(
            interval_seconds=0.1,  # Fast for tests
            batch_size=10,
            overlap_window_seconds=0,
        ),
    )


class TestWorkerSupervisor:
    """Tests for WorkerSupervisor."""

    async def test_start_creates_workers(
        self, store: SQLiteKillmailStore
    ) -> None:
        """Test that start creates a worker per profile."""
        profiles = [make_profile("profile-1"), make_profile("profile-2")]
        supervisor = WorkerSupervisor(store=store, profiles=profiles)

        await supervisor.start()
        await asyncio.sleep(0.05)  # Let workers transition to RUNNING

        assert supervisor.worker_count == 2
        assert supervisor.active_worker_count == 2

        await supervisor.stop()

    async def test_disabled_profiles_skipped(
        self, store: SQLiteKillmailStore
    ) -> None:
        """Test that disabled profiles don't get workers."""
        profiles = [
            make_profile("enabled", enabled=True),
            make_profile("disabled", enabled=False),
        ]
        supervisor = WorkerSupervisor(store=store, profiles=profiles)

        await supervisor.start()

        assert supervisor.worker_count == 1
        assert "enabled" in supervisor.get_active_profile_names()
        assert "disabled" not in supervisor.get_active_profile_names()

        await supervisor.stop()

    async def test_stop_stops_all_workers(
        self, store: SQLiteKillmailStore
    ) -> None:
        """Test that stop stops all workers."""
        profiles = [make_profile("profile-1")]
        supervisor = WorkerSupervisor(store=store, profiles=profiles)

        await supervisor.start()
        await asyncio.sleep(0.05)  # Let workers transition to RUNNING
        assert supervisor.active_worker_count == 1

        await supervisor.stop()
        assert supervisor.worker_count == 0
        assert not supervisor.is_running

    async def test_get_worker_by_name(
        self, store: SQLiteKillmailStore
    ) -> None:
        """Test getting a worker by name."""
        profiles = [make_profile("my-worker")]
        supervisor = WorkerSupervisor(store=store, profiles=profiles)

        await supervisor.start()

        worker = supervisor.get_worker("my-worker")
        assert worker is not None
        assert worker.name == "my-worker"

        missing = supervisor.get_worker("nonexistent")
        assert missing is None

        await supervisor.stop()

    async def test_get_status_returns_dict(
        self, store: SQLiteKillmailStore
    ) -> None:
        """Test that get_status returns complete status."""
        profiles = [make_profile("status-test")]
        supervisor = WorkerSupervisor(store=store, profiles=profiles)

        await supervisor.start()
        await asyncio.sleep(0.05)  # Let it run briefly

        status = supervisor.get_status()

        assert status["running"] is True
        assert status["workers"]["total"] == 1
        assert status["workers"]["active"] == 1
        assert len(status["workers"]["details"]) == 1
        assert "metrics" in status
        assert "esi_coordinator" in status

        await supervisor.stop()

    async def test_metrics_tracking(
        self, store: SQLiteKillmailStore
    ) -> None:
        """Test that metrics are tracked."""
        profiles = [make_profile("metrics-test")]
        supervisor = WorkerSupervisor(store=store, profiles=profiles)

        await supervisor.start()

        metrics = supervisor.metrics
        assert metrics.workers_started == 1
        assert metrics.uptime_seconds >= 0

        await supervisor.stop()

    async def test_empty_profiles_works(
        self, store: SQLiteKillmailStore
    ) -> None:
        """Test supervisor with no profiles."""
        supervisor = WorkerSupervisor(store=store, profiles=[])

        await supervisor.start()

        assert supervisor.worker_count == 0
        assert supervisor.is_running

        await supervisor.stop()


@pytest_asyncio.fixture
async def store(tmp_path: Path):
    """Create and initialize a test store."""
    store = SQLiteKillmailStore(db_path=tmp_path / "test.db")
    await store.initialize()
    yield store
    await store.close()
