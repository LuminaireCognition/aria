"""Tests for BoundedKillQueue."""

from __future__ import annotations

import asyncio
from datetime import datetime

import pytest

pytestmark = pytest.mark.asyncio

from aria_esi.services.killmail_store import BoundedKillQueue, KillmailRecord


def make_kill(kill_id: int, ingested_at: int | None = None) -> KillmailRecord:
    """Create a minimal killmail for testing."""
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
        ingested_at=ingested_at or int(datetime(2026, 1, 26, 12, 0, 0).timestamp()),
        victim_ship_type_id=670,
        victim_corporation_id=98000001,
        victim_alliance_id=None,
    )


class TestBoundedKillQueue:
    """Tests for BoundedKillQueue."""

    async def test_put_and_get_batch(self) -> None:
        """Test basic put and get operations."""
        queue = BoundedKillQueue(maxsize=100)

        # Put some kills
        for i in range(10):
            accepted = await queue.put(make_kill(i))
            assert accepted

        assert len(queue) == 10
        assert queue.metrics.received_total == 10
        assert queue.metrics.dropped_total == 0

        # Get a batch
        batch = await queue.get_batch(max_batch=5)
        assert len(batch) == 5
        assert len(queue) == 5

        # Get remaining
        batch = await queue.get_batch(max_batch=10)
        assert len(batch) == 5
        assert queue.is_empty()

    async def test_backpressure_drops_oldest(self) -> None:
        """Test that queue drops oldest kills when full."""
        queue = BoundedKillQueue(maxsize=5)

        # Fill the queue
        for i in range(5):
            await queue.put(make_kill(i))

        assert queue.metrics.dropped_total == 0

        # Add one more - should drop oldest (kill_id=0)
        await queue.put(make_kill(99))

        assert queue.metrics.dropped_total == 1
        assert len(queue) == 5

        # Verify kill_id=0 was dropped
        batch = await queue.get_batch(max_batch=10)
        kill_ids = [k.kill_id for k in batch]
        assert 0 not in kill_ids
        assert 99 in kill_ids

    async def test_metrics_tracking(self) -> None:
        """Test that metrics are tracked correctly."""
        queue = BoundedKillQueue(maxsize=3)

        # Add 5 kills, 2 will be dropped
        for i in range(5):
            await queue.put(make_kill(i))

        metrics = queue.get_metrics()
        assert metrics.received_total == 5
        assert metrics.dropped_total == 2
        assert metrics.queue_depth == 3

        # Get batch and mark as written
        batch = await queue.get_batch(max_batch=3)
        queue.mark_written(len(batch))

        metrics = queue.get_metrics()
        assert metrics.written_total == 3
        assert metrics.queue_depth == 0

    async def test_wait_for_items(self) -> None:
        """Test waiting for items in the queue."""
        queue = BoundedKillQueue(maxsize=10)

        # Queue is empty, wait should timeout
        has_items = await queue.wait_for_items(timeout=0.01)
        assert not has_items

        # Add an item
        await queue.put(make_kill(1))

        # Now wait should return immediately
        has_items = await queue.wait_for_items(timeout=0.1)
        assert has_items

    async def test_wait_for_items_concurrent(self) -> None:
        """Test concurrent wait and put."""
        queue = BoundedKillQueue(maxsize=10)

        async def producer():
            await asyncio.sleep(0.05)
            await queue.put(make_kill(1))

        async def consumer():
            return await queue.wait_for_items(timeout=1.0)

        # Start both tasks
        producer_task = asyncio.create_task(producer())
        consumer_task = asyncio.create_task(consumer())

        has_items = await consumer_task
        await producer_task

        assert has_items
        assert len(queue) == 1

    async def test_get_batch_empty_queue(self) -> None:
        """Test getting batch from empty queue."""
        queue = BoundedKillQueue(maxsize=10)

        batch = await queue.get_batch(max_batch=10)
        assert len(batch) == 0

    async def test_get_batch_respects_max_batch(self) -> None:
        """Test that get_batch respects the max_batch parameter."""
        queue = BoundedKillQueue(maxsize=100)

        # Add 20 kills
        for i in range(20):
            await queue.put(make_kill(i))

        # Request only 5
        batch = await queue.get_batch(max_batch=5)
        assert len(batch) == 5
        assert len(queue) == 15

    async def test_fifo_order(self) -> None:
        """Test that queue maintains FIFO order."""
        queue = BoundedKillQueue(maxsize=10)

        # Add kills in order
        for i in range(5):
            await queue.put(make_kill(i))

        # Get should return in same order
        batch = await queue.get_batch(max_batch=5)
        kill_ids = [k.kill_id for k in batch]
        assert kill_ids == [0, 1, 2, 3, 4]

    async def test_drop_oldest_tracks_time(self) -> None:
        """Test that drop records last_drop_time."""
        queue = BoundedKillQueue(maxsize=2)

        await queue.put(make_kill(1))
        await queue.put(make_kill(2))

        assert queue.metrics.last_drop_time is None

        await queue.put(make_kill(3))  # Triggers drop

        assert queue.metrics.last_drop_time is not None

    async def test_concurrent_access(self) -> None:
        """Test thread safety with concurrent producers."""
        queue = BoundedKillQueue(maxsize=1000)

        async def producer(start_id: int, count: int):
            for i in range(count):
                await queue.put(make_kill(start_id + i))

        # Run 5 producers concurrently
        tasks = [
            asyncio.create_task(producer(i * 100, 50))
            for i in range(5)
        ]
        await asyncio.gather(*tasks)

        # All kills should be received
        assert queue.metrics.received_total == 250
        assert len(queue) == 250
