"""
Worker Supervisor.

Manages the lifecycle of notification workers, one per enabled profile.
Handles startup, health monitoring, restart on failure, and graceful shutdown.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from ....core.logging import get_logger
from .esi_coordinator import ESICoordinator
from .worker import NotificationWorker, WorkerState

if TYPE_CHECKING:
    from ...killmail_store import SQLiteKillmailStore
    from .profiles import NotificationProfile

logger = get_logger(__name__)


@dataclass
class SupervisorMetrics:
    """Metrics for the worker supervisor."""

    workers_started: int = 0
    workers_restarted: int = 0
    workers_failed: int = 0
    health_checks: int = 0
    uptime_seconds: float = 0.0


@dataclass
class WorkerSupervisor:
    """
    Manages notification workers for all enabled profiles.

    Responsibilities:
    1. Create a worker for each enabled profile
    2. Start all workers on supervisor start
    3. Health check loop (every 5 seconds)
    4. Restart failed workers with exponential backoff
    5. Graceful shutdown with timeout

    Usage:
        supervisor = WorkerSupervisor(store, profiles)
        await supervisor.start()
        # ... run until shutdown
        await supervisor.stop()
    """

    store: SQLiteKillmailStore
    profiles: list[NotificationProfile]

    # Configuration
    health_check_interval: float = 5.0
    restart_backoff_base: float = 1.0
    restart_backoff_max: float = 60.0
    shutdown_timeout: float = 10.0

    # Shared ESI coordinator
    esi_coordinator: ESICoordinator | None = field(default=None, repr=False)

    # Callbacks to inject into workers
    _send_notification: Any = field(default=None, repr=False)
    _format_kill: Any = field(default=None, repr=False)
    _evaluate_triggers: Any = field(default=None, repr=False)

    # Runtime state
    _workers: dict[str, NotificationWorker] = field(default_factory=dict, repr=False)
    _restart_counts: dict[str, int] = field(default_factory=dict, repr=False)
    _running: bool = field(default=False, repr=False)
    _health_task: asyncio.Task | None = field(default=None, repr=False)
    _start_time: datetime | None = field(default=None, repr=False)
    _metrics: SupervisorMetrics = field(default_factory=SupervisorMetrics, repr=False)

    def __post_init__(self) -> None:
        """Initialize ESI coordinator if not provided."""
        if self.esi_coordinator is None:
            self.esi_coordinator = ESICoordinator(store=self.store)

    @property
    def is_running(self) -> bool:
        """Check if supervisor is running."""
        return self._running

    @property
    def worker_count(self) -> int:
        """Get number of managed workers."""
        return len(self._workers)

    @property
    def active_worker_count(self) -> int:
        """Get number of currently running workers."""
        return sum(1 for w in self._workers.values() if w.is_running)

    @property
    def metrics(self) -> SupervisorMetrics:
        """Get supervisor metrics."""
        if self._start_time:
            self._metrics.uptime_seconds = (datetime.utcnow() - self._start_time).total_seconds()
        return self._metrics

    async def start(self) -> None:
        """
        Start the supervisor and all workers.

        Creates a worker for each enabled profile and starts them.
        Also starts the health check loop.
        """
        if self._running:
            logger.warning("Supervisor already running")
            return

        self._running = True
        self._start_time = datetime.utcnow()

        logger.info(
            "Starting worker supervisor with %d profiles",
            len(self.profiles),
        )

        # Create and start workers for each profile
        for profile in self.profiles:
            if not profile.enabled:
                logger.debug("Skipping disabled profile: %s", profile.name)
                continue

            worker = self._create_worker(profile)
            self._workers[profile.name] = worker
            self._restart_counts[profile.name] = 0

            try:
                worker.start()
                self._metrics.workers_started += 1
                logger.info("Started worker for profile: %s", profile.name)
            except Exception as e:
                logger.error(
                    "Failed to start worker for profile %s: %s",
                    profile.name,
                    e,
                )

        # Start health check loop
        self._health_task = asyncio.create_task(self._health_loop())

        logger.info(
            "Supervisor started: %d/%d workers running",
            self.active_worker_count,
            self.worker_count,
        )

    async def stop(self, timeout: float | None = None) -> None:
        """
        Stop the supervisor and all workers gracefully.

        Args:
            timeout: Maximum time to wait for shutdown (uses default if None)
        """
        if not self._running:
            return

        self._running = False
        effective_timeout = timeout if timeout is not None else self.shutdown_timeout

        logger.info("Stopping supervisor (timeout=%.1fs)...", effective_timeout)

        # Stop health check loop
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
            self._health_task = None

        # Stop all workers concurrently
        stop_tasks = [
            worker.stop(timeout=effective_timeout / 2) for worker in self._workers.values()
        ]

        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)

        self._workers.clear()
        self._restart_counts.clear()

        logger.info("Supervisor stopped")

    def _create_worker(self, profile: NotificationProfile) -> NotificationWorker:
        """Create a worker for a profile."""
        # ESI coordinator is guaranteed non-None after __post_init__
        assert self.esi_coordinator is not None
        return NotificationWorker(
            profile=profile,
            store=self.store,
            esi_coordinator=self.esi_coordinator,
            _send_notification=self._send_notification,
            _format_kill=self._format_kill,
            _evaluate_triggers=self._evaluate_triggers,
        )

    async def _health_loop(self) -> None:
        """Background loop to check worker health and restart failed workers."""
        while self._running:
            try:
                await asyncio.sleep(self.health_check_interval)
                self._metrics.health_checks += 1

                for name, worker in list(self._workers.items()):
                    if worker.state == WorkerState.FAILED:
                        await self._handle_failed_worker(name, worker)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Health check error: %s", e)

    async def _handle_failed_worker(self, name: str, worker: NotificationWorker) -> None:
        """Handle a failed worker by restarting with backoff."""
        self._metrics.workers_failed += 1
        self._restart_counts[name] = self._restart_counts.get(name, 0) + 1
        restart_count = self._restart_counts[name]

        # Calculate backoff
        backoff = min(
            self.restart_backoff_base * (2 ** (restart_count - 1)),
            self.restart_backoff_max,
        )

        logger.warning(
            "Worker '%s' failed (restart %d), waiting %.1fs before restart",
            name,
            restart_count,
            backoff,
        )

        await asyncio.sleep(backoff)

        if not self._running:
            return

        # Recreate and restart worker
        profile = worker.profile
        new_worker = self._create_worker(profile)
        self._workers[name] = new_worker

        try:
            new_worker.start()
            self._metrics.workers_restarted += 1
            logger.info(
                "Worker '%s' restarted (attempt %d)",
                name,
                restart_count,
            )
        except Exception as e:
            logger.error(
                "Failed to restart worker '%s': %s",
                name,
                e,
            )

    def get_worker(self, name: str) -> NotificationWorker | None:
        """Get a worker by name."""
        return self._workers.get(name)

    def get_active_profile_names(self) -> set[str]:
        """Get names of all active profiles."""
        return set(self._workers.keys())

    def get_status(self) -> dict:
        """Get supervisor status."""
        return {
            "running": self._running,
            "uptime_seconds": (
                (datetime.utcnow() - self._start_time).total_seconds() if self._start_time else 0
            ),
            "workers": {
                "total": self.worker_count,
                "active": self.active_worker_count,
                "details": [worker.get_status() for worker in self._workers.values()],
            },
            "metrics": {
                "workers_started": self._metrics.workers_started,
                "workers_restarted": self._metrics.workers_restarted,
                "workers_failed": self._metrics.workers_failed,
                "health_checks": self._metrics.health_checks,
            },
            "esi_coordinator": (
                self.esi_coordinator.get_metrics() if self.esi_coordinator else None
            ),
        }
