"""
ESI Fetch Coordinator.

Coordinates ESI fetch claims between multiple workers to prevent
duplicate API calls and manage retry logic.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ....core.logging import get_logger

if TYPE_CHECKING:
    from ...killmail_store import ESIKillmail, KillmailRecord, SQLiteKillmailStore

logger = get_logger(__name__)


@dataclass
class FetchResult:
    """Result of an ESI fetch attempt."""

    success: bool
    kill_id: int
    esi_data: ESIKillmail | None = None
    error: str | None = None
    claimed_by_other: bool = False


@dataclass
class ESICoordinator:
    """
    Coordinates ESI fetches across multiple workers.

    Uses the killmail store's claim table to ensure only one worker
    fetches ESI details for a given kill. Handles retries and marks
    kills as unfetchable after max attempts.

    Flow:
    1. Worker calls try_claim() to claim a kill
    2. If claimed, worker fetches from ESI
    3. Worker calls complete() with result
    4. On failure, attempts are tracked until max_attempts
    5. After max_attempts, kill is marked unfetchable
    """

    store: SQLiteKillmailStore
    max_attempts: int = 3
    claim_timeout_seconds: float = 60.0
    retry_delay_seconds: float = 5.0

    # Metrics
    _claims_attempted: int = field(default=0, repr=False)
    _claims_won: int = field(default=0, repr=False)
    _claims_lost: int = field(default=0, repr=False)
    _fetches_success: int = field(default=0, repr=False)
    _fetches_failed: int = field(default=0, repr=False)
    _marked_unfetchable: int = field(default=0, repr=False)

    async def try_claim(
        self, kill: KillmailRecord, worker_name: str
    ) -> tuple[bool, ESIKillmail | None]:
        """
        Try to claim a kill for ESI fetch.

        If another worker already fetched the ESI data, returns
        (False, existing_data). If claim is won, returns (True, None)
        and the worker should proceed with the fetch.

        Args:
            kill: The killmail record to claim
            worker_name: Unique worker identifier

        Returns:
            Tuple of (claimed, existing_esi_data)
        """
        self._claims_attempted += 1

        # Check if ESI data already exists
        existing = await self.store.get_esi_details(kill.kill_id)
        if existing is not None:
            logger.debug(
                "Kill %d already has ESI data (status=%s)",
                kill.kill_id,
                existing.fetch_status,
            )
            return False, existing

        # Check attempt count
        attempts = await self.store.get_esi_fetch_attempts(kill.kill_id)
        if attempts >= self.max_attempts:
            logger.debug(
                "Kill %d exceeded max attempts (%d), marking unfetchable",
                kill.kill_id,
                self.max_attempts,
            )
            await self.store.insert_esi_unfetchable(kill.kill_id)
            self._marked_unfetchable += 1
            return False, None

        # Try to claim
        claimed = await self.store.try_claim_esi_fetch(kill.kill_id, worker_name)
        if claimed:
            self._claims_won += 1
            logger.debug(
                "Worker '%s' claimed kill %d for ESI fetch",
                worker_name,
                kill.kill_id,
            )
            return True, None
        else:
            self._claims_lost += 1
            logger.debug(
                "Worker '%s' lost claim for kill %d (another worker claimed)",
                worker_name,
                kill.kill_id,
            )
            return False, None

    async def wait_for_claim(
        self, kill: KillmailRecord, worker_name: str, timeout: float = 30.0
    ) -> tuple[bool, ESIKillmail | None]:
        """
        Wait for ESI data or claim availability with exponential backoff.

        Use this when another worker has claimed the kill. This will wait
        for either the data to appear (other worker succeeded) or the claim
        to expire (other worker failed/timed out).

        Args:
            kill: The killmail record
            worker_name: Unique worker identifier
            timeout: Maximum time to wait in seconds

        Returns:
            Tuple of (claimed, existing_esi_data)
        """
        start = asyncio.get_event_loop().time()
        backoff = 1.0

        while True:
            elapsed = asyncio.get_event_loop().time() - start
            if elapsed >= timeout:
                logger.debug(
                    "Wait for kill %d timed out after %.1fs",
                    kill.kill_id,
                    elapsed,
                )
                return False, None

            # Check if data now exists
            existing = await self.store.get_esi_details(kill.kill_id)
            if existing is not None:
                return False, existing

            # Try to claim again
            claimed = await self.store.try_claim_esi_fetch(kill.kill_id, worker_name)
            if claimed:
                self._claims_won += 1
                return True, None

            # Wait with exponential backoff
            await asyncio.sleep(min(backoff, timeout - elapsed))
            backoff = min(backoff * 2, 10.0)

    async def complete_success(self, kill_id: int, esi_data: ESIKillmail) -> None:
        """
        Record successful ESI fetch.

        Args:
            kill_id: The killmail ID
            esi_data: The fetched ESI data
        """
        await self.store.insert_esi_details(kill_id, esi_data)
        await self.store.delete_esi_claim(kill_id)
        await self.store.delete_esi_fetch_attempts(kill_id)
        self._fetches_success += 1
        logger.debug("ESI fetch success for kill %d", kill_id)

    async def complete_failure(self, kill_id: int, error: str, worker_name: str) -> bool:
        """
        Record failed ESI fetch attempt.

        Increments attempt counter and releases claim for retry.
        Returns True if more attempts are available, False if max reached.

        Args:
            kill_id: The killmail ID
            error: Error description
            worker_name: Worker that attempted the fetch

        Returns:
            True if more attempts available, False if max reached
        """
        await self.store.increment_esi_fetch_attempts(kill_id, error)
        await self.store.delete_esi_claim(kill_id)
        self._fetches_failed += 1

        attempts = await self.store.get_esi_fetch_attempts(kill_id)
        if attempts >= self.max_attempts:
            logger.warning(
                "Kill %d ESI fetch failed permanently after %d attempts",
                kill_id,
                attempts,
            )
            await self.store.insert_esi_unfetchable(kill_id)
            self._marked_unfetchable += 1
            return False

        logger.debug(
            "Kill %d ESI fetch failed (attempt %d/%d): %s",
            kill_id,
            attempts,
            self.max_attempts,
            error,
        )
        return True

    def get_metrics(self) -> dict:
        """Get coordinator metrics."""
        return {
            "claims_attempted": self._claims_attempted,
            "claims_won": self._claims_won,
            "claims_lost": self._claims_lost,
            "fetches_success": self._fetches_success,
            "fetches_failed": self._fetches_failed,
            "marked_unfetchable": self._marked_unfetchable,
        }
