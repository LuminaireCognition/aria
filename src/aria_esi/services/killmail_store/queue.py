"""
Bounded Killmail Queue with Backpressure.

Provides a memory-bounded queue between the RedisQ reader and SQLite writer.
Implements drop-oldest semantics when the queue is full.

See KILLMAIL_STORE_REDESIGN_PROPOSAL.md D5: Ingest Backpressure.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass

from .protocol import KillmailRecord

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_QUEUE_SIZE = 1000  # ~15 minutes of average load
DEFAULT_BATCH_SIZE = 100  # Records per write transaction
DEFAULT_FLUSH_INTERVAL = 1.0  # Seconds between batch writes


@dataclass
class IngestMetrics:
    """Backpressure metrics for observability."""

    received_total: int = 0
    written_total: int = 0
    dropped_total: int = 0
    queue_depth: int = 0
    last_drop_time: float | None = None


class BoundedKillQueue:
    """
    Bounded queue with drop-oldest backpressure.

    When the queue is full, the oldest kill is dropped to make room for
    the new one. This prevents memory exhaustion during burst events
    while keeping the most recent kills.

    Thread-safe via asyncio.Lock.
    """

    def __init__(self, maxsize: int = DEFAULT_QUEUE_SIZE):
        """
        Initialize the bounded queue.

        Args:
            maxsize: Maximum queue size. When exceeded, oldest items are dropped.
        """
        self._queue: deque[KillmailRecord] = deque(maxlen=maxsize)
        self._maxsize = maxsize
        self.metrics = IngestMetrics()
        self._lock = asyncio.Lock()
        self._not_empty = asyncio.Event()

    async def put(self, kill: KillmailRecord) -> bool:
        """
        Add kill to queue.

        When queue is full, oldest kill is dropped (deque maxlen behavior).

        Args:
            kill: Killmail record to queue

        Returns:
            True if accepted without drop, False if a kill was dropped
        """
        async with self._lock:
            self.metrics.received_total += 1
            was_full = len(self._queue) >= self._maxsize

            if was_full:
                # deque will auto-drop oldest when we append
                dropped = self._queue[0]
                self.metrics.dropped_total += 1
                self.metrics.last_drop_time = time.time()
                logger.warning(
                    "Backpressure: dropped kill %d (age: %.1fs) - queue full",
                    dropped.kill_id,
                    time.time() - dropped.ingested_at,
                    extra={
                        "event": "backpressure_drop",
                        "kill_id": dropped.kill_id,
                        "kill_age_seconds": time.time() - dropped.ingested_at,
                        "queue_depth": self.metrics.queue_depth,
                        "drops_total": self.metrics.dropped_total,
                    },
                )

            self._queue.append(kill)
            self.metrics.queue_depth = len(self._queue)
            self._not_empty.set()
            return not was_full

    async def get_batch(self, max_batch: int = DEFAULT_BATCH_SIZE) -> list[KillmailRecord]:
        """
        Get up to max_batch kills for writing.

        Does not wait if queue is empty - returns empty list immediately.

        Args:
            max_batch: Maximum number of records to return

        Returns:
            List of killmail records (may be empty)
        """
        async with self._lock:
            batch: list[KillmailRecord] = []
            for _ in range(min(max_batch, len(self._queue))):
                batch.append(self._queue.popleft())
            self.metrics.queue_depth = len(self._queue)
            if not self._queue:
                self._not_empty.clear()
            return batch

    async def wait_for_items(self, timeout: float | None = None) -> bool:
        """
        Wait until the queue has items.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if items are available, False if timeout occurred
        """
        try:
            await asyncio.wait_for(self._not_empty.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    def get_metrics(self) -> IngestMetrics:
        """Get current metrics snapshot."""
        return IngestMetrics(
            received_total=self.metrics.received_total,
            written_total=self.metrics.written_total,
            dropped_total=self.metrics.dropped_total,
            queue_depth=self.metrics.queue_depth,
            last_drop_time=self.metrics.last_drop_time,
        )

    def mark_written(self, count: int) -> None:
        """
        Mark records as successfully written.

        Args:
            count: Number of records written
        """
        self.metrics.written_total += count

    def is_empty(self) -> bool:
        """Check if the queue is empty."""
        return len(self._queue) == 0

    def __len__(self) -> int:
        """Get current queue size."""
        return len(self._queue)
