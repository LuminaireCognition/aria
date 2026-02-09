"""
Webhook Queue Manager.

Bounded async queue for webhook sends with rate limiting and circuit breaker.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from ....core.logging import get_logger

if TYPE_CHECKING:
    from .discord_client import DiscordClient

logger = get_logger(__name__)


@dataclass
class QueuedMessage:
    """A message queued for sending."""

    payload: dict[str, Any]
    queued_at: float  # Unix timestamp
    kill_id: int | None = None
    trigger_type: str | None = None


@dataclass
class QueueHealth:
    """Health status of the webhook queue."""

    is_healthy: bool
    is_paused: bool
    queue_depth: int
    success_rate: float
    last_success: datetime | None
    messages_sent_1h: int
    messages_dropped_1h: int


@dataclass
class WebhookQueue:
    """
    Bounded async queue for Discord webhook sends.

    Features:
    - Max size: 100 alerts (oldest dropped if full)
    - Rate limit: 5 req/sec (Discord limit)
    - Circuit breaker: Pause after 3 consecutive failures spanning >5 minutes
    - Auto-resume on next successful send
    """

    client: DiscordClient
    max_size: int = 100
    rate_limit_per_sec: float = 5.0

    # Queue state - initialized in __post_init__ to use max_size
    _queue: deque[QueuedMessage] = field(default_factory=deque)

    def __post_init__(self) -> None:
        """Initialize queue with configured max size."""
        if not isinstance(self._queue, deque) or self._queue.maxlen != self.max_size:
            self._queue = deque(maxlen=self.max_size)

    _is_paused: bool = False
    _pause_start: float | None = None

    # Metrics for health reporting
    _sent_timestamps: list[float] = field(default_factory=list)  # Last hour
    _dropped_timestamps: list[float] = field(default_factory=list)  # Last hour
    _failure_start: float | None = None  # When failures started
    _consecutive_failures: int = 0

    # Rate limiting
    _last_send_time: float = 0.0

    def enqueue(
        self, payload: dict[str, Any], kill_id: int | None = None, trigger_type: str | None = None
    ) -> bool:
        """
        Add a message to the queue.

        Args:
            payload: Discord webhook payload
            kill_id: Optional kill ID for logging
            trigger_type: Optional trigger type for logging

        Returns:
            True if queued, False if dropped due to full queue
        """
        now = time.time()

        if len(self._queue) >= self.max_size:
            # Queue is full - oldest message will be dropped by deque
            self._dropped_timestamps.append(now)
            logger.warning(
                "Webhook queue full, dropping oldest message (depth=%d)",
                len(self._queue),
            )

        message = QueuedMessage(
            payload=payload,
            queued_at=now,
            kill_id=kill_id,
            trigger_type=trigger_type,
        )
        self._queue.append(message)

        return True

    async def process_queue(self) -> int:
        """
        Process all queued messages.

        Respects rate limits and circuit breaker state.

        Returns:
            Number of messages successfully sent
        """
        if self._is_paused:
            # Check if we should try to resume (after 5 minute pause)
            if self._pause_start and (time.time() - self._pause_start) >= 300:
                logger.info("Attempting to resume webhook queue after pause")
                self._is_paused = False
            else:
                return 0

        sent_count = 0
        min_interval = 1.0 / self.rate_limit_per_sec

        while self._queue:
            # Rate limiting
            now = time.time()
            elapsed = now - self._last_send_time
            if elapsed < min_interval:
                await asyncio.sleep(min_interval - elapsed)

            message = self._queue.popleft()

            # Skip very old messages (>5 minutes old)
            message_age = time.time() - message.queued_at
            if message_age > 300:
                logger.debug(
                    "Skipping stale message (age=%.1fs, kill_id=%s)",
                    message_age,
                    message.kill_id,
                )
                continue

            # Send the message
            result = await self.client.send(message.payload)
            self._last_send_time = time.time()

            if result.success:
                sent_count += 1
                self._sent_timestamps.append(time.time())
                self._consecutive_failures = 0
                self._failure_start = None

                logger.debug(
                    "Sent webhook for kill %s (trigger=%s)",
                    message.kill_id,
                    message.trigger_type,
                )
            else:
                self._consecutive_failures += 1
                if self._failure_start is None:
                    self._failure_start = time.time()

                logger.warning(
                    "Webhook send failed: %s (consecutive=%d)",
                    result.error,
                    self._consecutive_failures,
                )

                # Check for circuit breaker trigger
                if self._should_pause():
                    self._is_paused = True
                    self._pause_start = time.time()
                    logger.warning("Pausing webhook queue due to repeated failures")
                    # Re-queue the failed message
                    self._queue.appendleft(message)
                    break

        # Cleanup old metrics
        self._cleanup_metrics()

        return sent_count

    def _should_pause(self) -> bool:
        """Check if circuit breaker should trigger."""
        # Pause after 3 consecutive failures spanning >5 minutes
        if self._consecutive_failures < 3:
            return False

        if self._failure_start is None:
            return False

        failure_duration = time.time() - self._failure_start
        return failure_duration >= 300  # 5 minutes

    def _cleanup_metrics(self) -> None:
        """Remove metrics older than 1 hour."""
        cutoff = time.time() - 3600

        self._sent_timestamps = [ts for ts in self._sent_timestamps if ts >= cutoff]
        self._dropped_timestamps = [ts for ts in self._dropped_timestamps if ts >= cutoff]

    def get_health(self) -> QueueHealth:
        """Get current queue health status."""
        self._cleanup_metrics()

        # Calculate success rate from client
        success_rate = self.client.success_rate if self.client else 1.0

        return QueueHealth(
            is_healthy=not self._is_paused and self.client.is_healthy,
            is_paused=self._is_paused,
            queue_depth=len(self._queue),
            success_rate=success_rate,
            last_success=self.client._last_success if self.client else None,
            messages_sent_1h=len(self._sent_timestamps),
            messages_dropped_1h=len(self._dropped_timestamps),
        )

    def resume(self) -> bool:
        """
        Manually resume a paused queue.

        Returns:
            True if was paused and now resumed, False if wasn't paused
        """
        if not self._is_paused:
            return False

        self._is_paused = False
        self._pause_start = None
        self._consecutive_failures = 0
        self._failure_start = None
        logger.info("Webhook queue manually resumed")
        return True

    @property
    def depth(self) -> int:
        """Get current queue depth."""
        return len(self._queue)

    @property
    def is_paused(self) -> bool:
        """Check if queue is paused."""
        return self._is_paused
