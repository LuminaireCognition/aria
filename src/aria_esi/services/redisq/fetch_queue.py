"""
Kill Fetch Queue.

Rate-limited queue for fetching full killmail data from ESI.
RedisQ only provides kill ID and hash; full data must be fetched separately.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import httpx

from ...core.logging import get_logger

if TYPE_CHECKING:
    from .models import ProcessedKill, QueuedKill

logger = get_logger(__name__)

# ESI endpoints
ESI_BASE_URL = "https://esi.evetech.net/latest"
ESI_KILLMAIL_URL = ESI_BASE_URL + "/killmails/{kill_id}/{hash}/"


@dataclass
class FetchResult:
    """Result of a killmail fetch operation."""

    kill_id: int
    success: bool
    esi_data: dict[str, Any] | None = None
    zkb_data: dict[str, Any] | None = None
    error: str | None = None


async def fetch_killmail(
    client: httpx.AsyncClient,
    kill_id: int,
    kill_hash: str,
) -> FetchResult:
    """
    Fetch a single killmail from ESI.

    Args:
        client: Async HTTP client
        kill_id: Killmail ID
        kill_hash: Killmail hash from zKillboard

    Returns:
        FetchResult with ESI data or error
    """
    url = ESI_KILLMAIL_URL.format(kill_id=kill_id, hash=kill_hash)

    try:
        response = await client.get(url, timeout=30.0)

        if response.status_code == 200:
            return FetchResult(
                kill_id=kill_id,
                success=True,
                esi_data=response.json(),
            )
        elif response.status_code == 404:
            return FetchResult(
                kill_id=kill_id,
                success=False,
                error="Killmail not found (404)",
            )
        else:
            return FetchResult(
                kill_id=kill_id,
                success=False,
                error=f"ESI error: {response.status_code}",
            )

    except httpx.TimeoutException:
        return FetchResult(
            kill_id=kill_id,
            success=False,
            error="Request timeout",
        )
    except Exception as e:
        return FetchResult(
            kill_id=kill_id,
            success=False,
            error=str(e),
        )


@dataclass
class KillFetchQueue:
    """
    Rate-limited queue for fetching killmails from ESI.

    Manages concurrent requests and respects ESI rate limits.
    """

    # Rate limiting settings
    MAX_CONCURRENT_FETCHES: int = 5
    FETCH_RATE_LIMIT: int = 20  # requests per second
    MAX_QUEUE_SIZE: int = 1000

    # Queue state
    _queue: deque[QueuedKill] = field(default_factory=deque)
    _processing: bool = False
    _client: httpx.AsyncClient | None = None
    _task: asyncio.Task | None = None

    # Rate limiting state
    _request_times: deque[float] = field(default_factory=deque)

    # Metrics
    _fetched_count: int = 0
    _error_count: int = 0

    # Callback for processed kills
    _on_kill_processed: Callable[[ProcessedKill], None] | None = None

    async def enqueue(self, kill: QueuedKill) -> bool:
        """
        Add a kill to the fetch queue.

        Args:
            kill: QueuedKill from RedisQ

        Returns:
            True if queued, False if queue is full
        """
        if len(self._queue) >= self.MAX_QUEUE_SIZE:
            logger.warning("Fetch queue full, dropping kill %d", kill.kill_id)
            return False

        self._queue.append(kill)
        return True

    async def start_processing(
        self,
        on_kill_processed: Callable[[ProcessedKill], None] | None = None,
    ) -> None:
        """
        Start processing the fetch queue.

        Args:
            on_kill_processed: Callback for each processed kill
        """
        if self._processing:
            return

        self._processing = True
        self._on_kill_processed = on_kill_processed

        # Create HTTP client with connection pooling
        self._client = httpx.AsyncClient(
            limits=httpx.Limits(
                max_keepalive_connections=10,
                max_connections=20,
            ),
            headers={
                "User-Agent": "ARIA-ESI/1.0 (EVE Online Assistant)",
                "Accept": "application/json",
            },
        )

        # Start processing task
        self._task = asyncio.create_task(self._process_loop())
        logger.info("Kill fetch queue started")

    async def stop_processing(self) -> None:
        """Stop processing and clean up."""
        self._processing = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        if self._client:
            await self._client.aclose()
            self._client = None

        logger.info(
            "Kill fetch queue stopped (fetched: %d, errors: %d)",
            self._fetched_count,
            self._error_count,
        )

    @property
    def backlog_size(self) -> int:
        """Get current queue size."""
        return len(self._queue)

    @property
    def fetched_count(self) -> int:
        """Get total fetched count."""
        return self._fetched_count

    @property
    def error_count(self) -> int:
        """Get total error count."""
        return self._error_count

    async def _process_loop(self) -> None:
        """Main processing loop."""
        from .processor import parse_esi_killmail

        assert self._client is not None, "_process_loop called without initialized client"

        while self._processing:
            if not self._queue:
                await asyncio.sleep(0.1)
                continue

            # Check rate limit
            await self._wait_for_rate_limit()

            # Get batch of kills to fetch
            batch_size = min(self.MAX_CONCURRENT_FETCHES, len(self._queue))
            batch = [self._queue.popleft() for _ in range(batch_size)]

            # Fetch in parallel
            tasks = [fetch_killmail(self._client, kill.kill_id, kill.hash) for kill in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for kill, result in zip(batch, results):
                if isinstance(result, BaseException):
                    logger.warning("Fetch exception for %d: %s", kill.kill_id, result)
                    self._error_count += 1
                    continue

                if result.success and result.esi_data:
                    try:
                        processed = parse_esi_killmail(
                            result.esi_data,
                            kill.zkb_data,
                        )
                        self._fetched_count += 1

                        if self._on_kill_processed:
                            self._on_kill_processed(processed)

                    except Exception as e:
                        logger.warning("Parse error for %d: %s", kill.kill_id, e)
                        self._error_count += 1
                else:
                    logger.debug("Fetch failed for %d: %s", kill.kill_id, result.error)
                    self._error_count += 1

            # Record request times for rate limiting
            now = time.monotonic()
            for _ in range(len(batch)):
                self._request_times.append(now)

    async def _wait_for_rate_limit(self) -> None:
        """Wait if rate limit would be exceeded."""
        now = time.monotonic()

        # Remove old request times (older than 1 second)
        while self._request_times and now - self._request_times[0] > 1.0:
            self._request_times.popleft()

        # Wait if at rate limit
        if len(self._request_times) >= self.FETCH_RATE_LIMIT:
            wait_time = 1.0 - (now - self._request_times[0])
            if wait_time > 0:
                await asyncio.sleep(wait_time)

    def get_stats(self) -> dict:
        """
        Get queue statistics.

        Returns:
            Dict with queue metrics
        """
        return {
            "queue_size": self.backlog_size,
            "fetched_count": self._fetched_count,
            "error_count": self._error_count,
            "processing": self._processing,
        }


# =============================================================================
# Module-level singleton
# =============================================================================

_fetch_queue: KillFetchQueue | None = None


def get_fetch_queue() -> KillFetchQueue:
    """Get or create the fetch queue singleton."""
    global _fetch_queue
    if _fetch_queue is None:
        _fetch_queue = KillFetchQueue()
    return _fetch_queue


def reset_fetch_queue() -> None:
    """Reset the fetch queue singleton."""
    global _fetch_queue
    _fetch_queue = None
