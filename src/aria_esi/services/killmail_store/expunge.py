"""
Expunge Task for Killmail Store.

Background task that periodically cleans up old data:
- Killmails older than retention period (default 7 days)
- Processed kills older than 1 hour
- Stale ESI fetch claims (older than 60 seconds)
- Orphaned ESI fetch attempts
- Orphaned worker state for deleted profiles

See KILLMAIL_STORE_REDESIGN_PROPOSAL.md Phase 1: Storage Foundation.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .sqlite import SQLiteKillmailStore

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_RETENTION_DAYS = 7
DEFAULT_EXPUNGE_INTERVAL_SECONDS = 3600  # 1 hour
DEFAULT_PROCESSED_KILLS_RETENTION_SECONDS = 3600  # 1 hour
DEFAULT_STALE_CLAIM_THRESHOLD_SECONDS = 60


@dataclass
class ExpungeStats:
    """Statistics from an expunge run."""

    killmails_deleted: int = 0
    processed_kills_deleted: int = 0
    stale_claims_deleted: int = 0
    orphaned_attempts_deleted: int = 0
    orphaned_state_deleted: int = 0
    duration_seconds: float = 0.0


class ExpungeTask:
    """
    Background task that periodically cleans up old data.

    Runs in a loop, sleeping between expunge cycles. Should be started
    as an asyncio task and cancelled on shutdown.
    """

    def __init__(
        self,
        store: SQLiteKillmailStore,
        retention_days: int = DEFAULT_RETENTION_DAYS,
        interval_seconds: int = DEFAULT_EXPUNGE_INTERVAL_SECONDS,
        processed_kills_retention_seconds: int = DEFAULT_PROCESSED_KILLS_RETENTION_SECONDS,
        stale_claim_threshold_seconds: int = DEFAULT_STALE_CLAIM_THRESHOLD_SECONDS,
    ):
        """
        Initialize the expunge task.

        Args:
            store: Killmail store to clean
            retention_days: How long to keep killmails
            interval_seconds: How often to run cleanup
            processed_kills_retention_seconds: How long to keep processed_kills entries
            stale_claim_threshold_seconds: When to consider ESI claims abandoned
        """
        self.store = store
        self.retention_days = retention_days
        self.interval_seconds = interval_seconds
        self.processed_kills_retention = processed_kills_retention_seconds
        self.stale_claim_threshold = stale_claim_threshold_seconds
        self._active_profiles: set[str] = set()
        self._running = False
        self._task: asyncio.Task | None = None

    def set_active_profiles(self, profiles: set[str]) -> None:
        """
        Set the list of active notification profiles.

        Used to identify orphaned worker state.

        Args:
            profiles: Set of active profile names
        """
        self._active_profiles = profiles

    async def run_once(self) -> ExpungeStats:
        """
        Run a single expunge cycle.

        Returns:
            Statistics from the expunge run
        """
        start_time = time.time()
        stats = ExpungeStats()

        # Calculate cutoff for killmail retention
        cutoff = datetime.now() - timedelta(days=self.retention_days)

        try:
            # Delete old killmails (cascades to esi_details via FK)
            stats.killmails_deleted = await self.store.expunge_before(cutoff)
            if stats.killmails_deleted > 0:
                logger.info(
                    "Expunged %d killmails older than %s",
                    stats.killmails_deleted,
                    cutoff.isoformat(),
                )

            # Delete old processed_kills entries
            stats.processed_kills_deleted = await self.store.expunge_processed_kills(
                self.processed_kills_retention
            )
            if stats.processed_kills_deleted > 0:
                logger.debug(
                    "Expunged %d processed_kills entries",
                    stats.processed_kills_deleted,
                )

            # Delete stale ESI claims
            stats.stale_claims_deleted = await self.store.expunge_stale_esi_claims(
                self.stale_claim_threshold
            )
            if stats.stale_claims_deleted > 0:
                logger.info(
                    "Expunged %d stale ESI fetch claims",
                    stats.stale_claims_deleted,
                )

            # Delete orphaned ESI fetch attempts
            stats.orphaned_attempts_deleted = await self.store.expunge_orphaned_esi_attempts()
            if stats.orphaned_attempts_deleted > 0:
                logger.debug(
                    "Expunged %d orphaned ESI fetch attempts",
                    stats.orphaned_attempts_deleted,
                )

            # Delete orphaned worker state
            if self._active_profiles:
                stats.orphaned_state_deleted = await self.store.expunge_orphaned_state(
                    self._active_profiles
                )
                if stats.orphaned_state_deleted > 0:
                    logger.info(
                        "Expunged %d orphaned worker state entries",
                        stats.orphaned_state_deleted,
                    )

            # Optimize database after cleanup
            await self.store.optimize_database()

        except Exception as e:
            logger.error("Expunge cycle failed: %s", e, exc_info=True)
            raise

        stats.duration_seconds = time.time() - start_time

        total_deleted = (
            stats.killmails_deleted
            + stats.processed_kills_deleted
            + stats.stale_claims_deleted
            + stats.orphaned_attempts_deleted
            + stats.orphaned_state_deleted
        )

        if total_deleted > 0:
            logger.info(
                "Expunge cycle complete: %d total records deleted in %.2fs",
                total_deleted,
                stats.duration_seconds,
            )
        else:
            logger.debug("Expunge cycle complete: no records to delete")

        return stats

    async def run(self) -> None:
        """
        Run the expunge loop continuously.

        Runs until cancelled. Handles errors gracefully with exponential backoff.
        """
        self._running = True
        backoff = 60.0  # Start with 1 minute on error
        max_backoff = 3600.0  # Max 1 hour between retries

        logger.info(
            "Expunge task started (retention=%d days, interval=%d seconds)",
            self.retention_days,
            self.interval_seconds,
        )

        while self._running:
            try:
                await self.run_once()
                backoff = 60.0  # Reset backoff on success
                await asyncio.sleep(self.interval_seconds)

            except asyncio.CancelledError:
                logger.info("Expunge task cancelled")
                break

            except Exception as e:
                logger.error(
                    "Expunge task error, retrying in %.0fs: %s",
                    backoff,
                    e,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)

        self._running = False
        logger.info("Expunge task stopped")

    def start(self) -> asyncio.Task:
        """
        Start the expunge task as a background task.

        Returns:
            The asyncio Task running the expunge loop
        """
        if self._task is not None and not self._task.done():
            raise RuntimeError("Expunge task already running")

        self._task = asyncio.create_task(self.run(), name="killmail-expunge")
        return self._task

    async def stop(self, timeout: float = 5.0) -> None:
        """
        Stop the expunge task gracefully.

        Args:
            timeout: How long to wait for the task to finish
        """
        self._running = False
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await asyncio.wait_for(self._task, timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning("Expunge task did not stop within timeout")
            except asyncio.CancelledError:
                pass
