"""Tests for ExpungeTask."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio

pytestmark = pytest.mark.asyncio

from aria_esi.services.killmail_store import (
    ExpungeTask,
    KillmailRecord,
    SQLiteKillmailStore,
)


def make_kill(
    kill_id: int,
    kill_time: datetime,
    ingested_at: datetime | None = None,
) -> KillmailRecord:
    """Create a killmail with specific timestamps."""
    return KillmailRecord(
        kill_id=kill_id,
        kill_time=int(kill_time.timestamp()),
        solar_system_id=30000142,
        zkb_hash=f"hash{kill_id}",
        zkb_total_value=100_000_000.0,
        zkb_points=10,
        zkb_is_npc=False,
        zkb_is_solo=False,
        zkb_is_awox=False,
        ingested_at=int((ingested_at or kill_time).timestamp()),
        victim_ship_type_id=670,
        victim_corporation_id=98000001,
        victim_alliance_id=None,
    )


class TestExpungeTask:
    """Tests for ExpungeTask."""

    async def test_run_once_cleans_old_kills(
        self, store: SQLiteKillmailStore
    ) -> None:
        """Test that run_once expunges old killmails."""
        now = datetime.now()
        old_time = now - timedelta(days=10)
        recent_time = now - timedelta(hours=1)

        # Insert old and recent kills
        old_kill = make_kill(1, old_time)
        recent_kill = make_kill(2, recent_time)

        await store.insert_kill(old_kill)
        await store.insert_kill(recent_kill)

        # Run expunge with 7 day retention
        task = ExpungeTask(store, retention_days=7)
        stats = await task.run_once()

        assert stats.killmails_deleted == 1

        # Verify only recent kill remains
        assert await store.get_kill(1) is None
        assert await store.get_kill(2) is not None

    async def test_run_once_cleans_processed_kills(
        self, store: SQLiteKillmailStore
    ) -> None:
        """Test that run_once expunges old processed_kills entries."""
        kill = make_kill(1, datetime.now())
        await store.insert_kill(kill)
        await store.mark_kill_processed("worker-1", kill.kill_id)

        # Wait a tiny bit so the record is definitely in the past
        await asyncio.sleep(0.01)

        # Run expunge with negative retention (immediate cleanup)
        task = ExpungeTask(
            store,
            retention_days=30,  # Don't clean killmails
            processed_kills_retention_seconds=-1,
        )
        stats = await task.run_once()

        assert stats.processed_kills_deleted == 1
        assert not await store.is_kill_processed("worker-1", kill.kill_id)

    async def test_run_once_cleans_stale_claims(
        self, store: SQLiteKillmailStore
    ) -> None:
        """Test that run_once expunges stale ESI claims."""
        kill = make_kill(1, datetime.now())
        await store.insert_kill(kill)
        await store.try_claim_esi_fetch(kill.kill_id, "worker-1")

        # Wait a tiny bit so the record is definitely in the past
        await asyncio.sleep(0.01)

        # Run expunge with negative threshold (immediate cleanup)
        task = ExpungeTask(
            store,
            retention_days=30,
            stale_claim_threshold_seconds=-1,
        )
        stats = await task.run_once()

        assert stats.stale_claims_deleted == 1
        assert await store.get_esi_claim(kill.kill_id) is None

    async def test_run_once_cleans_orphaned_state(
        self, store: SQLiteKillmailStore
    ) -> None:
        """Test that run_once expunges orphaned worker state."""
        # Create state for two workers
        await store.update_worker_state("active-worker", last_processed_time=1000)
        await store.update_worker_state("deleted-worker", last_processed_time=1000)

        task = ExpungeTask(store, retention_days=30)
        task.set_active_profiles({"active-worker"})
        stats = await task.run_once()

        assert stats.orphaned_state_deleted >= 1
        assert await store.get_worker_state("active-worker") is not None
        assert await store.get_worker_state("deleted-worker") is None

    async def test_run_once_optimizes_database(
        self, store: SQLiteKillmailStore
    ) -> None:
        """Test that run_once calls optimize_database."""
        task = ExpungeTask(store)
        stats = await task.run_once()

        # Just verify it doesn't error
        assert stats.duration_seconds >= 0

    async def test_start_and_stop(self, store: SQLiteKillmailStore) -> None:
        """Test starting and stopping the expunge task."""
        task = ExpungeTask(
            store,
            interval_seconds=0.1,  # Fast interval for testing
        )

        # Start the task
        asyncio_task = task.start()
        assert not asyncio_task.done()

        # Let it run briefly
        await asyncio.sleep(0.05)

        # Stop the task
        await task.stop(timeout=1.0)
        assert asyncio_task.done()

    async def test_start_twice_raises(self, store: SQLiteKillmailStore) -> None:
        """Test that starting twice raises an error."""
        task = ExpungeTask(store)
        task.start()

        with pytest.raises(RuntimeError, match="already running"):
            task.start()

        await task.stop()


@pytest_asyncio.fixture
async def store(tmp_path: Path):
    """Create and initialize a test store."""
    store = SQLiteKillmailStore(db_path=tmp_path / "test.db")
    await store.initialize()
    yield store
    await store.close()
