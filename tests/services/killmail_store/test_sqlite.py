"""Tests for SQLiteKillmailStore."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from pathlib import Path

import pytest

pytestmark = pytest.mark.asyncio

from aria_esi.services.killmail_store import (
    ESIKillmail,
    KillmailRecord,
    SQLiteKillmailStore,
)


class TestSQLiteKillmailStore:
    """Tests for SQLiteKillmailStore."""

    # -------------------------------------------------------------------------
    # Initialization Tests
    # -------------------------------------------------------------------------

    async def test_initialize_creates_database(self, temp_db_path: Path) -> None:
        """Test that initialize creates the database file."""
        store = SQLiteKillmailStore(db_path=temp_db_path)
        await store.initialize()

        assert temp_db_path.exists()
        await store.close()

    async def test_initialize_runs_migrations(self, store: SQLiteKillmailStore) -> None:
        """Test that initialize runs migrations."""
        # Check that schema_migrations table exists and has at least one entry
        cursor = await store.db.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE version >= 1"
        )
        row = await cursor.fetchone()
        assert row[0] >= 1

    async def test_initialize_twice_is_idempotent(
        self, temp_db_path: Path
    ) -> None:
        """Test that initialize can be called twice safely."""
        store1 = SQLiteKillmailStore(db_path=temp_db_path)
        await store1.initialize()
        await store1.close()

        store2 = SQLiteKillmailStore(db_path=temp_db_path)
        await store2.initialize()  # Should not fail
        await store2.close()

    # -------------------------------------------------------------------------
    # Killmail CRUD Tests
    # -------------------------------------------------------------------------

    async def test_insert_kill(
        self, store: SQLiteKillmailStore, sample_kill: KillmailRecord
    ) -> None:
        """Test inserting a killmail."""
        await store.insert_kill(sample_kill)

        # Verify it was inserted
        result = await store.get_kill(sample_kill.kill_id)
        assert result is not None
        assert result.kill_id == sample_kill.kill_id
        assert result.solar_system_id == sample_kill.solar_system_id
        assert result.zkb_hash == sample_kill.zkb_hash

    async def test_insert_kill_duplicate_is_ignored(
        self, store: SQLiteKillmailStore, sample_kill: KillmailRecord
    ) -> None:
        """Test that duplicate inserts are silently ignored."""
        await store.insert_kill(sample_kill)
        await store.insert_kill(sample_kill)  # Should not raise

        # Should still be only one record
        cursor = await store.db.execute(
            "SELECT COUNT(*) FROM killmails WHERE kill_id = ?",
            (sample_kill.kill_id,),
        )
        row = await cursor.fetchone()
        assert row[0] == 1

    async def test_insert_kills_batch(
        self, store: SQLiteKillmailStore, sample_kills: list[KillmailRecord]
    ) -> None:
        """Test batch insert."""
        count = await store.insert_kills_batch(sample_kills)
        assert count == len(sample_kills)

        # Verify all were inserted
        cursor = await store.db.execute("SELECT COUNT(*) FROM killmails")
        row = await cursor.fetchone()
        assert row[0] == len(sample_kills)

    async def test_insert_kills_batch_handles_duplicates(
        self, store: SQLiteKillmailStore, sample_kills: list[KillmailRecord]
    ) -> None:
        """Test that batch insert handles duplicates gracefully."""
        await store.insert_kills_batch(sample_kills[:5])
        await store.insert_kills_batch(sample_kills)  # Includes duplicates

        cursor = await store.db.execute("SELECT COUNT(*) FROM killmails")
        row = await cursor.fetchone()
        assert row[0] == len(sample_kills)

    # -------------------------------------------------------------------------
    # Query Tests
    # -------------------------------------------------------------------------

    async def test_query_kills_all(
        self, store: SQLiteKillmailStore, sample_kills: list[KillmailRecord]
    ) -> None:
        """Test querying all kills."""
        await store.insert_kills_batch(sample_kills)

        results = await store.query_kills(limit=100)
        assert len(results) == len(sample_kills)

    async def test_query_kills_by_system(
        self, store: SQLiteKillmailStore, sample_kills: list[KillmailRecord]
    ) -> None:
        """Test querying kills by system."""
        await store.insert_kills_batch(sample_kills)

        results = await store.query_kills(systems=[30000142])
        # Half should be in system 30000142 (even indices)
        assert len(results) == 5

    async def test_query_kills_by_time_range(
        self, store: SQLiteKillmailStore, sample_kills: list[KillmailRecord]
    ) -> None:
        """Test querying kills by time range."""
        await store.insert_kills_batch(sample_kills)

        base_time = datetime(2026, 1, 26, 12, 0, 0)
        since = base_time + timedelta(minutes=2)
        until = base_time + timedelta(minutes=7)

        results = await store.query_kills(since=since, until=until)
        # Should get kills from minute 2-7 (indices 2-7, 6 kills)
        assert len(results) == 6

    async def test_query_kills_by_min_value(
        self, store: SQLiteKillmailStore, sample_kills: list[KillmailRecord]
    ) -> None:
        """Test querying kills by minimum value."""
        await store.insert_kills_batch(sample_kills)

        results = await store.query_kills(min_value=500_000_000)
        # Values: 100M, 200M, 300M, 400M, 500M, 600M, 700M, 800M, 900M, 1B
        # 500M+ = indices 4-9 = 6 kills
        assert len(results) == 6

    async def test_query_kills_with_pagination(
        self, store: SQLiteKillmailStore, sample_kills: list[KillmailRecord]
    ) -> None:
        """Test cursor-based pagination."""
        await store.insert_kills_batch(sample_kills)

        # Get first page
        page1 = await store.query_kills(limit=3)
        assert len(page1) == 3

        # Get second page using cursor
        last = page1[-1]
        cursor = (last.kill_time, last.kill_id)
        page2 = await store.query_kills(limit=3, cursor=cursor)
        assert len(page2) == 3

        # Verify no overlap
        page1_ids = {k.kill_id for k in page1}
        page2_ids = {k.kill_id for k in page2}
        assert page1_ids.isdisjoint(page2_ids)

    async def test_query_kills_ordered_by_time_desc(
        self, store: SQLiteKillmailStore, sample_kills: list[KillmailRecord]
    ) -> None:
        """Test that results are ordered by kill_time DESC."""
        await store.insert_kills_batch(sample_kills)

        results = await store.query_kills(limit=100)
        times = [k.kill_time for k in results]
        assert times == sorted(times, reverse=True)

    # -------------------------------------------------------------------------
    # ESI Details Tests
    # -------------------------------------------------------------------------

    async def test_insert_and_get_esi_details(
        self,
        store: SQLiteKillmailStore,
        sample_kill: KillmailRecord,
        sample_esi_details: ESIKillmail,
    ) -> None:
        """Test inserting and retrieving ESI details."""
        await store.insert_kill(sample_kill)
        await store.insert_esi_details(sample_kill.kill_id, sample_esi_details)

        result = await store.get_esi_details(sample_kill.kill_id)
        assert result is not None
        assert result.kill_id == sample_kill.kill_id
        assert result.fetch_status == "success"
        assert result.victim_character_id == sample_esi_details.victim_character_id

    async def test_get_esi_details_not_found(
        self, store: SQLiteKillmailStore
    ) -> None:
        """Test getting ESI details for non-existent kill."""
        result = await store.get_esi_details(999999999)
        assert result is None

    async def test_insert_esi_unfetchable(
        self, store: SQLiteKillmailStore, sample_kill: KillmailRecord
    ) -> None:
        """Test marking a kill as unfetchable."""
        await store.insert_kill(sample_kill)
        await store.insert_esi_unfetchable(sample_kill.kill_id)

        result = await store.get_esi_details(sample_kill.kill_id)
        assert result is not None
        assert result.is_unfetchable
        assert result.fetch_status == "unfetchable"
        assert result.fetched_at == 0

    # -------------------------------------------------------------------------
    # ESI Fetch Attempts Tests
    # -------------------------------------------------------------------------

    async def test_esi_fetch_attempts_lifecycle(
        self, store: SQLiteKillmailStore, sample_kill: KillmailRecord
    ) -> None:
        """Test ESI fetch attempts tracking."""
        await store.insert_kill(sample_kill)

        # Initially no attempts
        assert await store.get_esi_fetch_attempts(sample_kill.kill_id) == 0

        # First attempt
        await store.increment_esi_fetch_attempts(sample_kill.kill_id, "timeout")
        assert await store.get_esi_fetch_attempts(sample_kill.kill_id) == 1

        # Second attempt
        await store.increment_esi_fetch_attempts(sample_kill.kill_id, "500 error")
        assert await store.get_esi_fetch_attempts(sample_kill.kill_id) == 2

        # Delete on success
        await store.delete_esi_fetch_attempts(sample_kill.kill_id)
        assert await store.get_esi_fetch_attempts(sample_kill.kill_id) == 0

    # -------------------------------------------------------------------------
    # Worker State Tests
    # -------------------------------------------------------------------------

    async def test_worker_state_crud(self, store: SQLiteKillmailStore) -> None:
        """Test worker state operations."""
        worker_name = "test-worker"

        # Initially no state
        state = await store.get_worker_state(worker_name)
        assert state is None

        # Create state
        now = 1706270400
        await store.update_worker_state(
            worker_name,
            last_processed_time=now,
            last_poll_at=now,
            consecutive_failures=0,
        )

        state = await store.get_worker_state(worker_name)
        assert state is not None
        assert state.worker_name == worker_name
        assert state.last_processed_time == now
        assert state.consecutive_failures == 0

        # Update partial fields
        await store.update_worker_state(
            worker_name,
            consecutive_failures=5,
        )

        state = await store.get_worker_state(worker_name)
        assert state.consecutive_failures == 5
        assert state.last_processed_time == now  # Unchanged

    # -------------------------------------------------------------------------
    # Processed Kills Tests
    # -------------------------------------------------------------------------

    async def test_processed_kills_tracking(
        self, store: SQLiteKillmailStore, sample_kill: KillmailRecord
    ) -> None:
        """Test processed kills tracking for duplicate detection."""
        await store.insert_kill(sample_kill)
        worker_name = "test-worker"

        # Not processed yet
        assert not await store.is_kill_processed(worker_name, sample_kill.kill_id)

        # Mark as processed
        await store.mark_kill_processed(worker_name, sample_kill.kill_id)
        assert await store.is_kill_processed(worker_name, sample_kill.kill_id)

    async def test_delivery_attempts_tracking(
        self, store: SQLiteKillmailStore, sample_kill: KillmailRecord
    ) -> None:
        """Test delivery attempt tracking."""
        await store.insert_kill(sample_kill)
        worker_name = "test-worker"

        # Initially no attempts
        assert await store.get_delivery_attempts(worker_name, sample_kill.kill_id) == 0

        # First attempt
        await store.increment_delivery_attempts(worker_name, sample_kill.kill_id)
        assert await store.get_delivery_attempts(worker_name, sample_kill.kill_id) == 1

        # Second attempt
        await store.increment_delivery_attempts(worker_name, sample_kill.kill_id)
        assert await store.get_delivery_attempts(worker_name, sample_kill.kill_id) == 2

    # -------------------------------------------------------------------------
    # ESI Fetch Claims Tests
    # -------------------------------------------------------------------------

    async def test_esi_claim_lifecycle(
        self, store: SQLiteKillmailStore, sample_kill: KillmailRecord
    ) -> None:
        """Test ESI fetch claim coordination."""
        await store.insert_kill(sample_kill)

        # First worker claims
        claimed = await store.try_claim_esi_fetch(sample_kill.kill_id, "worker-1")
        assert claimed

        # Second worker cannot claim
        claimed = await store.try_claim_esi_fetch(sample_kill.kill_id, "worker-2")
        assert not claimed

        # First worker can re-claim
        claimed = await store.try_claim_esi_fetch(sample_kill.kill_id, "worker-1")
        assert claimed

        # Verify claim details
        claim = await store.get_esi_claim(sample_kill.kill_id)
        assert claim is not None
        assert claim.claimed_by == "worker-1"

        # Release claim
        await store.delete_esi_claim(sample_kill.kill_id)
        claim = await store.get_esi_claim(sample_kill.kill_id)
        assert claim is None

        # Now worker-2 can claim
        claimed = await store.try_claim_esi_fetch(sample_kill.kill_id, "worker-2")
        assert claimed

    # -------------------------------------------------------------------------
    # Maintenance Tests
    # -------------------------------------------------------------------------

    async def test_expunge_before(
        self, store: SQLiteKillmailStore, sample_kills: list[KillmailRecord]
    ) -> None:
        """Test expunging old killmails."""
        await store.insert_kills_batch(sample_kills)

        # Expunge kills older than minute 5
        base_time = datetime(2026, 1, 26, 12, 0, 0)
        cutoff = base_time + timedelta(minutes=5)

        deleted = await store.expunge_before(cutoff)
        assert deleted == 5  # Kills 0-4 (minutes 0-4)

        remaining = await store.query_kills(limit=100)
        assert len(remaining) == 5

    async def test_expunge_processed_kills(
        self, store: SQLiteKillmailStore, sample_kill: KillmailRecord
    ) -> None:
        """Test expunging old processed_kills entries."""

        await store.insert_kill(sample_kill)
        await store.mark_kill_processed("worker-1", sample_kill.kill_id)

        # Wait a tiny bit so the record is definitely in the past
        await asyncio.sleep(0.01)

        # Expunge with very short retention (should delete records older than now)
        deleted = await store.expunge_processed_kills(older_than_seconds=-1)
        assert deleted == 1

        # No longer tracked
        assert not await store.is_kill_processed("worker-1", sample_kill.kill_id)

    async def test_expunge_stale_esi_claims(
        self, store: SQLiteKillmailStore, sample_kill: KillmailRecord
    ) -> None:
        """Test expunging stale ESI claims."""
        await store.insert_kill(sample_kill)
        await store.try_claim_esi_fetch(sample_kill.kill_id, "worker-1")

        # Wait a tiny bit so the record is definitely in the past
        await asyncio.sleep(0.01)

        # Expunge with negative threshold (should delete all)
        deleted = await store.expunge_stale_esi_claims(threshold_seconds=-1)
        assert deleted == 1

        # Claim is gone
        claim = await store.get_esi_claim(sample_kill.kill_id)
        assert claim is None

    async def test_expunge_orphaned_state(
        self, store: SQLiteKillmailStore
    ) -> None:
        """Test expunging orphaned worker state."""
        # Create state for multiple workers
        await store.update_worker_state("active-worker", last_processed_time=1000)
        await store.update_worker_state("deleted-worker", last_processed_time=1000)

        # Expunge with only active-worker in profile list
        deleted = await store.expunge_orphaned_state({"active-worker"})
        assert deleted >= 1

        # Active worker state remains
        assert await store.get_worker_state("active-worker") is not None
        # Deleted worker state is gone
        assert await store.get_worker_state("deleted-worker") is None

    # -------------------------------------------------------------------------
    # Stats Tests
    # -------------------------------------------------------------------------

    async def test_get_stats(
        self,
        store: SQLiteKillmailStore,
        sample_kills: list[KillmailRecord],
        sample_esi_details: ESIKillmail,
    ) -> None:
        """Test getting store statistics."""
        await store.insert_kills_batch(sample_kills)
        await store.insert_esi_details(sample_kills[0].kill_id, sample_esi_details)
        await store.insert_esi_unfetchable(sample_kills[1].kill_id)

        stats = await store.get_stats()
        assert stats.total_killmails == len(sample_kills)
        assert stats.total_esi_details == 1
        assert stats.total_esi_unfetchable == 1
        assert stats.oldest_killmail_time is not None
        assert stats.newest_killmail_time is not None
        assert stats.database_size_bytes > 0
