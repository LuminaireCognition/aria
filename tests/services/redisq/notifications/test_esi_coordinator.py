"""Tests for ESICoordinator."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
import pytest_asyncio

pytestmark = pytest.mark.asyncio

from aria_esi.services.killmail_store import (
    ESIKillmail,
    KillmailRecord,
    SQLiteKillmailStore,
)
from aria_esi.services.redisq.notifications.esi_coordinator import ESICoordinator


def make_kill(kill_id: int) -> KillmailRecord:
    """Create a test killmail record."""
    return KillmailRecord(
        kill_id=kill_id,
        kill_time=int(datetime(2026, 1, 26, 12, 0, 0).timestamp()),
        solar_system_id=30000142,
        zkb_hash=f"hash{kill_id}",
        zkb_total_value=100_000_000.0,
        zkb_points=10,
        zkb_is_npc=False,
        zkb_is_solo=False,
        zkb_is_awox=False,
        ingested_at=int(datetime(2026, 1, 26, 12, 0, 0).timestamp()),
        victim_ship_type_id=670,
        victim_corporation_id=98000001,
        victim_alliance_id=None,
    )


def make_esi_data(kill_id: int) -> ESIKillmail:
    """Create test ESI killmail data."""
    return ESIKillmail(
        kill_id=kill_id,
        fetched_at=int(datetime.now().timestamp()),
        fetch_status="success",
        fetch_attempts=1,
        victim_character_id=12345678,
        victim_ship_type_id=670,
        victim_corporation_id=98000001,
        victim_alliance_id=None,
        victim_damage_taken=1000,
        attacker_count=1,
        final_blow_character_id=87654321,
        final_blow_ship_type_id=24690,
        final_blow_corporation_id=98000002,
        attackers_json="[]",
        items_json="[]",
        position_json="{}",
    )


class TestESICoordinator:
    """Tests for ESICoordinator."""

    async def test_try_claim_wins_on_fresh_kill(
        self, coordinator: ESICoordinator, store: SQLiteKillmailStore
    ) -> None:
        """Test that first claim wins."""
        kill = make_kill(1)
        await store.insert_kill(kill)

        claimed, existing = await coordinator.try_claim(kill, "worker-1")
        assert claimed is True
        assert existing is None

    async def test_try_claim_returns_existing_data(
        self, coordinator: ESICoordinator, store: SQLiteKillmailStore
    ) -> None:
        """Test that try_claim returns existing ESI data."""
        kill = make_kill(2)
        esi_data = make_esi_data(2)
        await store.insert_kill(kill)
        await store.insert_esi_details(kill.kill_id, esi_data)

        claimed, existing = await coordinator.try_claim(kill, "worker-1")
        assert claimed is False
        assert existing is not None
        assert existing.kill_id == 2

    async def test_try_claim_loses_to_other_worker(
        self, coordinator: ESICoordinator, store: SQLiteKillmailStore
    ) -> None:
        """Test that second worker loses claim."""
        kill = make_kill(3)
        await store.insert_kill(kill)

        # First worker claims
        claimed1, _ = await coordinator.try_claim(kill, "worker-1")
        assert claimed1 is True

        # Second worker tries to claim
        claimed2, _ = await coordinator.try_claim(kill, "worker-2")
        assert claimed2 is False

    async def test_complete_success_stores_data(
        self, coordinator: ESICoordinator, store: SQLiteKillmailStore
    ) -> None:
        """Test that complete_success stores ESI data."""
        kill = make_kill(4)
        esi_data = make_esi_data(4)
        await store.insert_kill(kill)

        # Claim and complete
        await coordinator.try_claim(kill, "worker-1")
        await coordinator.complete_success(kill.kill_id, esi_data)

        # Verify stored
        stored = await store.get_esi_details(kill.kill_id)
        assert stored is not None
        assert stored.kill_id == 4

        # Verify claim released
        claim = await store.get_esi_claim(kill.kill_id)
        assert claim is None

    async def test_complete_failure_increments_attempts(
        self, coordinator: ESICoordinator, store: SQLiteKillmailStore
    ) -> None:
        """Test that complete_failure tracks attempts."""
        kill = make_kill(5)
        await store.insert_kill(kill)

        # First failure
        await coordinator.try_claim(kill, "worker-1")
        more = await coordinator.complete_failure(kill.kill_id, "timeout", "worker-1")
        assert more is True

        attempts = await store.get_esi_fetch_attempts(kill.kill_id)
        assert attempts == 1

    async def test_marks_unfetchable_after_max_attempts(
        self, coordinator: ESICoordinator, store: SQLiteKillmailStore
    ) -> None:
        """Test that kill is marked unfetchable after max attempts."""
        coordinator.max_attempts = 2
        kill = make_kill(6)
        await store.insert_kill(kill)

        # First failure
        await coordinator.try_claim(kill, "worker-1")
        await coordinator.complete_failure(kill.kill_id, "error1", "worker-1")

        # Second failure - should mark unfetchable
        await coordinator.try_claim(kill, "worker-1")
        more = await coordinator.complete_failure(kill.kill_id, "error2", "worker-1")
        assert more is False

        # Verify marked unfetchable
        details = await store.get_esi_details(kill.kill_id)
        assert details is not None
        assert details.is_unfetchable

    async def test_metrics_tracking(
        self, coordinator: ESICoordinator, store: SQLiteKillmailStore
    ) -> None:
        """Test that metrics are tracked."""
        kill = make_kill(7)
        await store.insert_kill(kill)

        await coordinator.try_claim(kill, "worker-1")
        metrics = coordinator.get_metrics()

        assert metrics["claims_attempted"] == 1
        assert metrics["claims_won"] == 1


@pytest_asyncio.fixture
async def store(tmp_path: Path):
    """Create and initialize a test store."""
    store = SQLiteKillmailStore(db_path=tmp_path / "test.db")
    await store.initialize()
    yield store
    await store.close()


@pytest.fixture
def coordinator(store: SQLiteKillmailStore) -> ESICoordinator:
    """Create a test coordinator."""
    return ESICoordinator(store=store, max_attempts=3)
