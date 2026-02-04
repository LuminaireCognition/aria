"""
Notification Worker.

A single worker that polls the killmail store and processes kills
for a specific notification profile. Workers are managed by the
WorkerSupervisor.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

import httpx

from ....core.logging import get_logger

if TYPE_CHECKING:
    from ...killmail_store import ESIKillmail, KillmailRecord, SQLiteKillmailStore
    from .esi_coordinator import ESICoordinator
    from .profiles import NotificationProfile

logger = get_logger(__name__)


class WorkerState(Enum):
    """Worker lifecycle states."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    FAILED = "failed"


@dataclass
class WorkerMetrics:
    """Metrics for a single worker."""

    kills_processed: int = 0
    kills_skipped_duplicate: int = 0
    kills_skipped_filter: int = 0
    notifications_sent: int = 0
    notifications_failed: int = 0
    rollups_sent: int = 0
    last_poll_time: datetime | None = None
    last_notification_time: datetime | None = None
    consecutive_errors: int = 0
    total_errors: int = 0


@dataclass
class NotificationWorker:
    """
    Worker that polls killmail store for a single profile.

    Each worker:
    1. Polls the store for kills since last_processed_time - overlap_window
    2. Checks processed_kills table for duplicates
    3. Evaluates triggers against each kill
    4. Coordinates ESI fetch if needed
    5. Formats and sends Discord notification
    6. Updates worker_state with new high-water mark

    Workers are resilient to restarts - they resume from persisted
    worker_state in the database.
    """

    profile: NotificationProfile
    store: SQLiteKillmailStore
    esi_coordinator: ESICoordinator

    # Callbacks for notification delivery
    _send_notification: Any = None  # Callable[[dict, str], Awaitable[bool]]
    _format_kill: Any = None  # Callable[[KillmailRecord, ...], dict]
    _evaluate_triggers: Any = None  # Callable[[KillmailRecord], TriggerResult | None]

    # Runtime state
    _state: WorkerState = field(default=WorkerState.STOPPED, repr=False)
    _task: asyncio.Task | None = field(default=None, repr=False)
    _stop_event: asyncio.Event = field(default_factory=asyncio.Event, repr=False)
    _metrics: WorkerMetrics = field(default_factory=WorkerMetrics, repr=False)

    # Rate limit tracking
    _pending_kills: list[KillmailRecord] = field(default_factory=list, repr=False)
    _rate_limited_until: float = 0.0

    # HTTP client for ESI fetches (lazy-initialized)
    _http_client: httpx.AsyncClient | None = field(default=None, repr=False)

    @property
    def name(self) -> str:
        """Get worker name (matches profile name)."""
        return self.profile.name

    @property
    def state(self) -> WorkerState:
        """Get current worker state."""
        return self._state

    @property
    def is_running(self) -> bool:
        """Check if worker is running."""
        return self._state == WorkerState.RUNNING

    @property
    def metrics(self) -> WorkerMetrics:
        """Get worker metrics."""
        return self._metrics

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client for ESI fetches."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0),
                headers={
                    "User-Agent": "ARIA-ESI/1.0 (EVE Online Assistant)",
                    "Accept": "application/json",
                },
            )
        return self._http_client

    async def _fetch_esi_killmail(self, kill: KillmailRecord) -> ESIKillmail | None:
        """
        Fetch killmail details from ESI.

        Args:
            kill: KillmailRecord with zkb_hash

        Returns:
            ESIKillmail with full details, or None on failure
        """

        if not kill.zkb_hash:
            logger.warning("Kill %d has no zkb_hash, cannot fetch ESI", kill.kill_id)
            return None

        url = f"https://esi.evetech.net/latest/killmails/{kill.kill_id}/{kill.zkb_hash}/"

        try:
            client = await self._get_http_client()
            response = await client.get(url)

            if response.status_code == 200:
                data = response.json()
                return self._parse_esi_response(kill.kill_id, data)
            elif response.status_code == 404:
                logger.debug("Kill %d not found on ESI (404)", kill.kill_id)
                return None
            else:
                logger.warning("ESI error for kill %d: %d", kill.kill_id, response.status_code)
                return None

        except httpx.TimeoutException:
            logger.warning("ESI timeout for kill %d", kill.kill_id)
            return None
        except Exception as e:
            logger.warning("ESI fetch error for kill %d: %s", kill.kill_id, e)
            return None

    def _parse_esi_response(self, kill_id: int, data: dict) -> ESIKillmail:
        """Parse ESI killmail response into ESIKillmail."""
        import json

        from ...killmail_store import ESIKillmail

        victim = data.get("victim", {})
        attackers = data.get("attackers", [])

        # Find final blow attacker
        final_blow = next((a for a in attackers if a.get("final_blow")), {})

        return ESIKillmail(
            kill_id=kill_id,
            fetched_at=int(time.time()),
            fetch_status="success",
            fetch_attempts=1,
            victim_character_id=victim.get("character_id"),
            victim_ship_type_id=victim.get("ship_type_id"),
            victim_corporation_id=victim.get("corporation_id"),
            victim_alliance_id=victim.get("alliance_id"),
            victim_damage_taken=victim.get("damage_taken"),
            attacker_count=len(attackers),
            final_blow_character_id=final_blow.get("character_id"),
            final_blow_ship_type_id=final_blow.get("ship_type_id"),
            final_blow_corporation_id=final_blow.get("corporation_id"),
            attackers_json=json.dumps(attackers) if attackers else None,
            items_json=json.dumps(data.get("items", [])) if data.get("items") else None,
            position_json=json.dumps(victim.get("position")) if victim.get("position") else None,
        )

    def start(self) -> asyncio.Task:
        """
        Start the worker.

        Returns:
            The asyncio task running the worker loop
        """
        if self._state in (WorkerState.RUNNING, WorkerState.STARTING):
            raise RuntimeError(f"Worker '{self.name}' already running")

        self._state = WorkerState.STARTING
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop())
        return self._task

    async def stop(self, timeout: float = 5.0) -> None:
        """
        Stop the worker gracefully.

        Args:
            timeout: Maximum time to wait for shutdown
        """
        if self._state == WorkerState.STOPPED:
            return

        self._state = WorkerState.STOPPING
        self._stop_event.set()

        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning("Worker '%s' stop timed out, cancelling", self.name)
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            except asyncio.CancelledError:
                pass
            self._task = None

        # Close HTTP client
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

        self._state = WorkerState.STOPPED

    async def _run_loop(self) -> None:
        """Main worker loop."""
        self._state = WorkerState.RUNNING
        logger.info("Worker '%s' started", self.name)

        try:
            while not self._stop_event.is_set():
                try:
                    await self._poll_once()
                    self._metrics.consecutive_errors = 0
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self._metrics.consecutive_errors += 1
                    self._metrics.total_errors += 1
                    logger.error(
                        "Worker '%s' poll error (consecutive=%d): %s",
                        self.name,
                        self._metrics.consecutive_errors,
                        e,
                    )

                    # Exponential backoff on errors
                    backoff = min(30, 2**self._metrics.consecutive_errors)
                    await asyncio.sleep(backoff)
                    continue

                # Check for rate limit backoff
                if time.time() < self._rate_limited_until:
                    wait_time = self._rate_limited_until - time.time()
                    logger.debug(
                        "Worker '%s' rate limited, waiting %.1fs",
                        self.name,
                        wait_time,
                    )
                    await asyncio.sleep(wait_time)
                    continue

                # Normal poll interval
                await asyncio.sleep(self.profile.polling.interval_seconds)

        except asyncio.CancelledError:
            logger.debug("Worker '%s' cancelled", self.name)
            raise
        except Exception as e:
            logger.error("Worker '%s' fatal error: %s", self.name, e)
            self._state = WorkerState.FAILED
            raise
        finally:
            if self._state != WorkerState.FAILED:
                self._state = WorkerState.STOPPED
            logger.info("Worker '%s' stopped", self.name)

    async def _poll_once(self) -> None:
        """Execute a single poll iteration."""
        self._metrics.last_poll_time = datetime.utcnow()

        # Check if we should send rollup (after rate limit clears)
        if (
            self._pending_kills
            and len(self._pending_kills) >= self.profile.rate_limit_strategy.rollup_threshold
        ):
            max_rollup = self.profile.rate_limit_strategy.max_rollup_kills
            await self._send_rollup(self._pending_kills[:max_rollup])

        # Get worker state from database
        worker_state = await self.store.get_worker_state(self.name)
        last_processed_time = worker_state.last_processed_time if worker_state else 0

        # Calculate query window with overlap for safety
        overlap = self.profile.polling.overlap_window_seconds
        since_time = last_processed_time - overlap if last_processed_time > 0 else 0

        # Extract system IDs from topology filter (if configured)
        system_ids: list[int] | None = None
        if self.profile._topology_filter is not None:
            geo_layer = self.profile._topology_filter.get_layer("geographic")
            if geo_layer is not None and hasattr(geo_layer, "_interest_map"):
                system_ids = list(geo_layer._interest_map.keys())

        # Query kills from store with system filtering
        since = datetime.fromtimestamp(since_time) if since_time > 0 else None
        kills = await self.store.query_kills(
            systems=system_ids,
            since=since,
            limit=self.profile.polling.batch_size,
        )

        if not kills:
            return

        logger.debug(
            "Worker '%s' polled %d kills (since=%s)",
            self.name,
            len(kills),
            since.isoformat() if since else "start",
        )

        # Process each kill
        new_high_water = last_processed_time
        for kill in kills:
            # Check for duplicates
            if await self.store.is_kill_processed(self.name, kill.kill_id):
                self._metrics.kills_skipped_duplicate += 1
                continue

            # Evaluate triggers (if callback set)
            trigger_result = None
            if self._evaluate_triggers:
                trigger_result = self._evaluate_triggers(kill)
                if trigger_result is None:
                    self._metrics.kills_skipped_filter += 1
                    # Still mark as processed to avoid re-evaluating
                    await self.store.mark_kill_processed(self.name, kill.kill_id)
                    continue

            # Check if we need ESI data and coordinate fetch
            esi_data = None
            if trigger_result and getattr(trigger_result, "requires_esi", False):
                claimed, existing = await self.esi_coordinator.try_claim(kill, self.name)
                if existing:
                    esi_data = existing
                elif claimed:
                    # Fetch from ESI with coordination
                    try:
                        fetched = await self._fetch_esi_killmail(kill)
                        if fetched:
                            await self.esi_coordinator.complete_success(kill.kill_id, fetched)
                            esi_data = fetched
                        else:
                            # Fetch failed - let coordinator track attempts
                            await self.esi_coordinator.complete_failure(
                                kill.kill_id, "Fetch returned None", self.name
                            )
                    except Exception as e:
                        logger.warning("ESI fetch error for kill %d: %s", kill.kill_id, e)
                        await self.esi_coordinator.complete_failure(kill.kill_id, str(e), self.name)

            # Format and send notification
            if self._format_kill and self._send_notification:
                payload = self._format_kill(kill, trigger_result, esi_data)
                result = await self._send_notification(payload, self.profile.webhook_url)

                # Handle SendResult object or bool return
                if hasattr(result, "success"):
                    success = result.success
                    # Check for rate limit
                    if hasattr(result, "is_rate_limited") and result.is_rate_limited:
                        backoff = (
                            result.retry_after or self.profile.rate_limit_strategy.backoff_seconds
                        )
                        self._rate_limited_until = time.time() + backoff
                        self._pending_kills.append(kill)
                        self._metrics.notifications_failed += 1
                        logger.warning(
                            "Worker '%s' rate limited for %.1fs, %d kills pending",
                            self.name,
                            backoff,
                            len(self._pending_kills),
                        )
                        return  # Exit poll iteration early
                else:
                    success = bool(result)

                if success:
                    self._metrics.notifications_sent += 1
                    self._metrics.last_notification_time = datetime.utcnow()
                else:
                    self._metrics.notifications_failed += 1

            # Mark as processed
            await self.store.mark_kill_processed(self.name, kill.kill_id)
            self._metrics.kills_processed += 1

            # Update high-water mark
            if kill.kill_time > new_high_water:
                new_high_water = kill.kill_time

        # Persist worker state
        if new_high_water > last_processed_time:
            await self.store.update_worker_state(
                self.name,
                last_processed_time=new_high_water,
                last_poll_at=int(time.time()),
                consecutive_failures=self._metrics.consecutive_errors,
            )

    async def _send_rollup(self, kills: list[KillmailRecord]) -> bool:
        """
        Send a rollup message for multiple kills.

        Used when rate limited with many pending kills.

        Args:
            kills: Kills to roll up

        Returns:
            True if rollup sent successfully
        """
        if not kills:
            return True

        from collections import Counter

        # Calculate aggregates
        total_value = sum(k.zkb_total_value or 0 for k in kills)

        # Get primary system (most common)
        system_counts = Counter(k.solar_system_id for k in kills)
        primary_system_id = system_counts.most_common(1)[0][0]

        # Format timestamp for zkill URL (YYYYMMDDHHMM)
        first_kill_time = datetime.fromtimestamp(kills[0].kill_time)
        timestamp = first_kill_time.strftime("%Y%m%d%H%M")

        # Format value in billions or millions
        if total_value >= 1_000_000_000:
            value_str = f"{total_value / 1_000_000_000:.1f}B"
        else:
            value_str = f"{total_value / 1_000_000:.0f}M"

        # Build message
        content = (
            f"📊 Activity ({len(kills)} kills rolled up)\n"
            f"💀 {value_str} ISK total\n"
            f"🔗 https://zkillboard.com/related/{primary_system_id}/{timestamp}/"
        )

        # Send via webhook
        if self._send_notification:
            result = await self._send_notification(
                {"content": content},
                self.profile.webhook_url,
            )

            # Handle SendResult object or bool return
            if hasattr(result, "success"):
                success = result.success
            else:
                success = bool(result)

            if success:
                self._metrics.rollups_sent += 1
                # Mark all as processed
                for kill in kills:
                    await self.store.mark_kill_processed(self.name, kill.kill_id)
                # Clear pending kills that were rolled up
                self._pending_kills = [k for k in self._pending_kills if k not in kills]
                return True
            return False
        return False

    def get_status(self) -> dict:
        """Get worker status."""
        return {
            "name": self.name,
            "state": self._state.value,
            "profile": self.profile.name,
            "metrics": {
                "kills_processed": self._metrics.kills_processed,
                "kills_skipped_duplicate": self._metrics.kills_skipped_duplicate,
                "kills_skipped_filter": self._metrics.kills_skipped_filter,
                "notifications_sent": self._metrics.notifications_sent,
                "notifications_failed": self._metrics.notifications_failed,
                "rollups_sent": self._metrics.rollups_sent,
                "consecutive_errors": self._metrics.consecutive_errors,
                "total_errors": self._metrics.total_errors,
            },
            "last_poll_time": (
                self._metrics.last_poll_time.isoformat() if self._metrics.last_poll_time else None
            ),
            "last_notification_time": (
                self._metrics.last_notification_time.isoformat()
                if self._metrics.last_notification_time
                else None
            ),
        }
