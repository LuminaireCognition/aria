"""
RedisQ Poller Service.

Polls zKillboard's RedisQ endpoint for real-time kill notifications.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

import httpx

from ...core.logging import get_logger
from ..killmail_store import BoundedKillQueue, SQLiteKillmailStore
from .database import get_realtime_database
from .fetch_queue import get_fetch_queue
from .models import IngestMetrics, PollerStatus, QueuedKill, RedisQConfig
from .processor import KillFilter, create_filter_from_config

if TYPE_CHECKING:
    from .entity_filter import EntityAwareFilter
    from .models import ProcessedKill
    from .name_resolver import NameResolver
    from .notifications import NotificationManager
    from .topology import TopologyFilter
    from .war_context import WarContextProvider

logger = get_logger(__name__)

# RedisQ endpoint (moved to zkillredisq.stream in May 2025)
REDISQ_URL = "https://zkillredisq.stream/listen.php"


@dataclass
class RedisQPoller:
    """
    RedisQ polling service for real-time killmails.

    Connects to zKillboard's RedisQ service and streams kill
    notifications, fetching full killmail data from ESI.
    """

    config: RedisQConfig

    # Runtime state
    _running: bool = False
    _client: httpx.AsyncClient | None = None
    _poll_task: asyncio.Task | None = None
    _cleanup_task: asyncio.Task | None = None
    _last_poll_time: datetime | None = None
    _last_kill_time: datetime | None = None

    # Metrics
    _kills_processed: int = 0
    _kills_filtered: int = 0
    _errors_last_hour: list[float] = field(default_factory=list)
    _consecutive_errors: int = 0

    # Persistence tracking (persist poll time every 60s, not every poll)
    _last_persisted_poll_time: float = 0.0
    _persist_interval_seconds: int = 60

    # Components
    _filter: KillFilter | None = None
    _entity_filter: EntityAwareFilter | None = None
    _entity_refresh_task: asyncio.Task | None = None

    # Entity tracking stats
    _watched_entity_kills: int = 0

    # Notification manager
    _notification_manager: NotificationManager | None = None

    # Topology pre-filter
    _topology_filter: TopologyFilter | None = None

    # War context provider
    _war_context_provider: WarContextProvider | None = None

    # Name resolver for display names
    _name_resolver: NameResolver | None = None

    # Killmail store (persistent storage)
    _killmail_store: SQLiteKillmailStore | None = None
    _ingest_queue: BoundedKillQueue | None = None
    _writer_task: asyncio.Task | None = None
    _writer_interval_seconds: float = 1.0
    _writer_batch_size: int = 100

    async def start(self) -> None:
        """
        Start the poller service.

        Initializes queue ID if needed, starts fetch queue,
        and begins polling RedisQ.
        """
        if self._running:
            logger.warning("Poller already running")
            return

        # Initialize or load queue ID
        db = get_realtime_database()
        if not self.config.queue_id:
            existing_id = db.get_queue_id()
            if existing_id:
                self.config.queue_id = existing_id
            else:
                self.config.queue_id = f"aria-{uuid.uuid4().hex[:8]}"
                db.set_queue_id(self.config.queue_id)
                logger.info("Generated new queue ID: %s", self.config.queue_id)

        # Create filter
        self._filter = create_filter_from_config(self.config)

        # Initialize entity filter for watched entity tracking
        try:
            from .entity_filter import EntityAwareFilter

            self._entity_filter = EntityAwareFilter()
            self._entity_filter.refresh_cache()
            self._filter.entity_filter = self._entity_filter

            if self._entity_filter.is_active:
                logger.info(
                    "Entity tracking active: %d corps, %d alliances watched",
                    self._entity_filter.watched_corp_count,
                    self._entity_filter.watched_alliance_count,
                )
        except Exception as e:
            logger.warning("Failed to initialize entity filter: %s", e)
            self._entity_filter = None

        # Initialize topology pre-filter
        try:
            from .topology import TopologyFilter

            self._topology_filter = TopologyFilter.from_config()
            if self._topology_filter.is_active:
                logger.info(
                    "Topology pre-filter active: %d systems tracked",
                    self._topology_filter.interest_map.total_systems
                    if self._topology_filter.interest_map
                    else 0,
                )
        except Exception as e:
            logger.warning("Failed to initialize topology filter: %s", e)
            self._topology_filter = None

        # Initialize war context provider
        try:
            from .war_context import get_war_context_provider

            self._war_context_provider = get_war_context_provider()
            stats = self._war_context_provider.get_stats()
            if stats["total_relationships"] > 0:
                logger.info(
                    "War context loaded: %d relationships (%d inferred, %d ESI)",
                    stats["total_relationships"],
                    stats["inferred_wars"],
                    stats["esi_wars"],
                )
        except Exception as e:
            logger.warning("Failed to initialize war context: %s", e)
            self._war_context_provider = None

        # Initialize killmail store for persistent storage
        try:
            from ...core.config import get_settings

            store_path = get_settings().killmail_db_path
            store_path.parent.mkdir(parents=True, exist_ok=True)
            self._killmail_store = SQLiteKillmailStore(db_path=store_path)
            await self._killmail_store.initialize()
            self._ingest_queue = BoundedKillQueue(maxsize=1000)
            logger.info("Killmail store initialized: %s", store_path)
        except Exception as e:
            logger.warning("Failed to initialize killmail store: %s", e)
            self._killmail_store = None
            self._ingest_queue = None

        # Initialize notification manager
        try:
            from .notifications import get_notification_manager

            self._notification_manager = get_notification_manager()
            if self._notification_manager and self._notification_manager.is_configured:
                await self._notification_manager.start()
                logger.info("Discord notifications enabled")
        except Exception as e:
            logger.warning("Failed to initialize notification manager: %s", e)
            self._notification_manager = None

        # Initialize name resolver for notification display names
        try:
            from .name_resolver import get_name_resolver

            self._name_resolver = get_name_resolver()
            logger.debug("Name resolver initialized")
        except Exception as e:
            logger.warning("Failed to initialize name resolver: %s", e)
            self._name_resolver = None

        # Create HTTP client with long timeout for polling
        # follow_redirects required: /listen.php redirects to /object.php as of Aug 2025
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=10.0,
                read=60.0,  # Long timeout for RedisQ long-poll
                write=10.0,
                pool=10.0,
            ),
            headers={
                "User-Agent": "ARIA-ESI/1.0 (EVE Online Assistant)",
                "Accept": "application/json",
            },
            follow_redirects=True,
        )

        # Start fetch queue
        fetch_queue = get_fetch_queue()
        await fetch_queue.start_processing(
            on_kill_processed=self._on_kill_processed,
        )

        self._running = True

        # Start polling task
        self._poll_task = asyncio.create_task(self._poll_loop())

        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        # Start entity refresh task (refresh cache every 5 minutes)
        self._entity_refresh_task = asyncio.create_task(self._entity_refresh_loop())

        # Start writer task for killmail store
        if self._killmail_store and self._ingest_queue:
            self._writer_task = asyncio.create_task(self._writer_loop())

        logger.info(
            "RedisQ poller started (queue_id=%s, regions=%s)",
            self.config.queue_id,
            self.config.filter_regions or "all",
        )

    async def stop(self) -> None:
        """Stop the poller service."""
        if not self._running:
            return

        self._running = False

        # Cancel tasks
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

        if self._entity_refresh_task:
            self._entity_refresh_task.cancel()
            try:
                await self._entity_refresh_task
            except asyncio.CancelledError:
                pass
            self._entity_refresh_task = None

        if self._writer_task:
            self._writer_task.cancel()
            try:
                await self._writer_task
            except asyncio.CancelledError:
                pass
            self._writer_task = None

        # Flush remaining queue items before shutdown
        if self._ingest_queue and self._killmail_store:
            remaining = await self._ingest_queue.get_batch(max_batch=1000)
            if remaining:
                await self._killmail_store.insert_kills_batch(remaining)
                self._ingest_queue.mark_written(len(remaining))
                logger.info("Flushed %d kills on shutdown", len(remaining))

        # Close killmail store
        if self._killmail_store:
            await self._killmail_store.close()
            self._killmail_store = None
            self._ingest_queue = None

        # Stop fetch queue
        fetch_queue = get_fetch_queue()
        await fetch_queue.stop_processing()

        # Persist final poll time for gap recovery on next startup
        if self._last_poll_time:
            db = get_realtime_database()
            db.set_last_poll_time(self._last_poll_time)

        # Stop notification manager
        if self._notification_manager:
            await self._notification_manager.stop()

        # Close HTTP client
        if self._client:
            await self._client.aclose()
            self._client = None

        logger.info(
            "RedisQ poller stopped (processed=%d, filtered=%d)",
            self._kills_processed,
            self._kills_filtered,
        )

    def is_healthy(self) -> bool:
        """
        Check if the poller is healthy.

        Returns:
            True if running without excessive errors
        """
        if not self._running:
            return False

        # Check for recent activity
        if self._last_poll_time:
            since_poll = (datetime.utcnow() - self._last_poll_time).total_seconds()
            if since_poll > 120:  # No poll in 2 minutes
                return False

        # Check for excessive errors
        self._prune_old_errors()
        if len(self._errors_last_hour) > 50:
            return False

        return True

    def get_status(self) -> PollerStatus:
        """
        Get current poller status.

        Returns:
            PollerStatus snapshot
        """
        self._prune_old_errors()
        fetch_queue = get_fetch_queue()

        # Get entity tracking stats
        watched_corps = 0
        watched_alliances = 0
        if self._entity_filter is not None:
            watched_corps = self._entity_filter.watched_corp_count
            watched_alliances = self._entity_filter.watched_alliance_count

        # Get topology filter stats
        topology_active = False
        topology_systems = 0
        topology_passed = 0
        topology_filtered = 0
        if self._topology_filter is not None and self._topology_filter.is_active:
            topology_active = True
            if self._topology_filter.interest_map:
                topology_systems = self._topology_filter.interest_map.total_systems
            metrics = self._topology_filter.get_metrics()
            topology_passed = metrics["passed"]
            topology_filtered = metrics["filtered"]

        # Get ingest metrics
        ingest_metrics = None
        if self._ingest_queue:
            queue_metrics = self._ingest_queue.get_metrics()
            ingest_metrics = IngestMetrics(
                received_total=queue_metrics.received_total,
                written_total=queue_metrics.written_total,
                dropped_total=queue_metrics.dropped_total,
                queue_depth=queue_metrics.queue_depth,
                last_drop_time=(
                    datetime.fromtimestamp(queue_metrics.last_drop_time)
                    if queue_metrics.last_drop_time
                    else None
                ),
            )

        return PollerStatus(
            is_running=self._running,
            queue_id=self.config.queue_id,
            last_poll_time=self._last_poll_time,
            last_kill_time=self._last_kill_time,
            kills_processed=self._kills_processed,
            kills_filtered=self._kills_filtered,
            fetch_queue_size=fetch_queue.backlog_size,
            errors_last_hour=len(self._errors_last_hour),
            filter_regions=self.config.filter_regions,
            watched_entity_kills=self._watched_entity_kills,
            watched_corps_count=watched_corps,
            watched_alliances_count=watched_alliances,
            topology_active=topology_active,
            topology_systems_tracked=topology_systems,
            topology_passed=topology_passed,
            topology_filtered=topology_filtered,
            ingest=ingest_metrics,
        )

    async def _poll_loop(self) -> None:
        """Main polling loop."""
        while self._running:
            try:
                await self._poll_once()
                self._consecutive_errors = 0
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._record_error()
                self._consecutive_errors += 1
                logger.warning("Poll error (consecutive=%d): %s", self._consecutive_errors, e)

                # Exponential backoff on errors
                backoff = min(30, 2**self._consecutive_errors)
                await asyncio.sleep(backoff)

    async def _poll_once(self) -> None:
        """Execute a single poll to RedisQ."""
        if not self._client:
            return

        params = {
            "queueID": self.config.queue_id,
            "ttw": str(self.config.poll_interval_seconds),
        }

        try:
            response = await self._client.get(REDISQ_URL, params=params)
            self._last_poll_time = datetime.utcnow()

            # Persist poll time periodically for gap recovery
            now_ts = time.time()
            if now_ts - self._last_persisted_poll_time >= self._persist_interval_seconds:
                db = get_realtime_database()
                db.set_last_poll_time(self._last_poll_time)
                self._last_persisted_poll_time = now_ts

            if response.status_code == 429:
                # Rate limited - respect Retry-After header or use default backoff
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    try:
                        backoff = float(retry_after)
                    except ValueError:
                        backoff = 30.0
                else:
                    backoff = 30.0
                logger.warning("RedisQ rate limited (429), backing off %.1fs", backoff)
                await asyncio.sleep(backoff)
                return

            if response.status_code != 200:
                logger.warning("RedisQ returned %d", response.status_code)
                return

            data = response.json()
            package = data.get("package")

            if package is None:
                # No kill available (normal during quiet periods)
                return

            # Create queued kill from package
            now = time.time()
            queued_kill = QueuedKill.from_redisq_package(package, now)

            if queued_kill.kill_id == 0 or not queued_kill.hash:
                logger.debug("Invalid kill package received")
                return

            # Store ALL kills in the persistent store (no pre-filtering)
            if self._ingest_queue:
                record = queued_kill.to_killmail_record()
                await self._ingest_queue.put(record)
                logger.debug("Enqueued kill %d for storage", queued_kill.kill_id)

            # Check if already in legacy database (for ESI fetch decision)
            db = get_realtime_database()
            if db.kill_exists(queued_kill.kill_id):
                logger.debug(
                    "Kill %d already in legacy db, skipping ESI fetch", queued_kill.kill_id
                )
                return

            # Apply topology pre-filter for ESI fetch decision (saves API quota)
            # Storage happens unconditionally above; this only affects ESI enrichment
            if self._topology_filter and self._topology_filter.is_active:
                if not self._topology_filter.should_fetch(queued_kill):
                    # Kill stored but not worth fetching ESI details
                    return

            # Queue for ESI fetch
            fetch_queue = get_fetch_queue()
            await fetch_queue.enqueue(queued_kill)

            logger.debug("Queued kill %d for ESI fetch", queued_kill.kill_id)

        except httpx.TimeoutException:
            # Normal for long-poll, just retry
            pass

    def _on_kill_processed(self, kill: ProcessedKill) -> None:
        """
        Callback when a kill is fetched and parsed.

        Applies filters and saves to database with entity match data.
        """
        # Apply topology filter post-fetch (pre-fetch filter may not have system ID)
        # This is the authoritative filter - pre-fetch is just an optimization
        if self._topology_filter and self._topology_filter.is_active:
            if self._topology_filter.calculator is not None:
                # Context-aware mode: check interest score
                if not self._topology_filter.calculator.should_fetch(kill.solar_system_id):
                    self._kills_filtered += 1
                    logger.debug(
                        "Kill %d filtered by topology (system=%d, interest below threshold)",
                        kill.kill_id,
                        kill.solar_system_id,
                    )
                    return
            elif self._topology_filter.interest_map is not None:
                # Legacy mode: check if system is in interest map
                if not self._topology_filter.interest_map.is_interesting(kill.solar_system_id):
                    self._kills_filtered += 1
                    logger.debug(
                        "Kill %d filtered by topology (system=%d not in operational area)",
                        kill.kill_id,
                        kill.solar_system_id,
                    )
                    return

        # Apply filter and check entity matching
        if self._filter:
            should_store, entity_match = self._filter.process_kill(kill)

            if not should_store:
                self._kills_filtered += 1
                logger.debug(
                    "Kill %d filtered (system=%d, value=%.0f)",
                    kill.kill_id,
                    kill.solar_system_id,
                    kill.total_value,
                )
                return
        else:
            entity_match = None

        # Save to database with entity match data
        db = get_realtime_database()
        db.save_kill(kill, entity_match)

        self._kills_processed += 1
        self._last_kill_time = kill.kill_time

        # Trigger notifications if configured
        if self._notification_manager and self._notification_manager.is_configured:
            try:
                # Get war context for the kill
                war_context = None
                if self._war_context_provider:
                    war_context = self._war_context_provider.check_kill(kill)

                # Get gatecamp status for the system (with war context filtering)
                from .threat_cache import get_threat_cache

                threat_cache = get_threat_cache()
                gatecamp_status = threat_cache.get_gatecamp_status(
                    kill.solar_system_id,
                    war_context=self._war_context_provider,
                )

                # Resolve display names for notification
                system_name = None
                ship_name = None
                if self._name_resolver:
                    system_name = self._name_resolver.resolve_system_name(kill.solar_system_id)
                    ship_name = (
                        self._name_resolver.resolve_type_name(kill.victim_ship_type_id)
                        if kill.victim_ship_type_id
                        else None
                    )

                # Fire async notification processing
                asyncio.create_task(
                    self._notification_manager.process_kill(
                        kill=kill,
                        entity_match=entity_match,
                        gatecamp_status=gatecamp_status,
                        war_context=war_context,
                        system_name=system_name,
                        ship_name=ship_name,
                    )
                )
            except Exception as e:
                logger.debug("Notification trigger failed: %s", e)

        # Track watched entity kills
        if entity_match and entity_match.has_match:
            self._watched_entity_kills += 1
            logger.info(
                "Watched entity kill %d (system=%d, matches=%s)",
                kill.kill_id,
                kill.solar_system_id,
                entity_match.match_types,
            )
        else:
            logger.debug(
                "Saved kill %d (system=%d, value=%.0f ISK)",
                kill.kill_id,
                kill.solar_system_id,
                kill.total_value,
            )

    async def _cleanup_loop(self) -> None:
        """Periodic cleanup of old kills and detections."""
        while self._running:
            try:
                await asyncio.sleep(3600)  # Run every hour

                # Use ThreatCache for comprehensive cleanup (kills + detections)
                from .threat_cache import get_threat_cache

                threat_cache = get_threat_cache()
                kills_deleted, detections_deleted = threat_cache.cleanup_old_data(
                    kill_retention_hours=self.config.retention_hours,
                    detection_retention_days=7,  # 7 days for backtesting
                )

                if kills_deleted > 0 or detections_deleted > 0:
                    logger.info(
                        "Cleanup removed %d old kills, %d old detections",
                        kills_deleted,
                        detections_deleted,
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Cleanup error: %s", e)

    async def _entity_refresh_loop(self) -> None:
        """Periodic refresh of entity watchlist cache."""
        while self._running:
            try:
                await asyncio.sleep(300)  # Refresh every 5 minutes

                if self._entity_filter is not None:
                    self._entity_filter.refresh_cache()
                    logger.debug(
                        "Entity cache refreshed: %d corps, %d alliances",
                        self._entity_filter.watched_corp_count,
                        self._entity_filter.watched_alliance_count,
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Entity refresh error: %s", e)

    async def _writer_loop(self) -> None:
        """Background task to drain ingest queue to killmail store."""
        while self._running:
            try:
                if not self._ingest_queue or not self._killmail_store:
                    await asyncio.sleep(self._writer_interval_seconds)
                    continue

                # Wait for items with timeout
                has_items = await self._ingest_queue.wait_for_items(
                    timeout=self._writer_interval_seconds
                )

                if not has_items:
                    continue

                # Get batch from queue
                batch = await self._ingest_queue.get_batch(max_batch=self._writer_batch_size)

                if not batch:
                    continue

                # Write to store
                count = await self._killmail_store.insert_kills_batch(batch)
                self._ingest_queue.mark_written(count)

                if count > 0:
                    logger.debug("Wrote %d kills to store", count)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Writer loop error: %s", e)
                await asyncio.sleep(1.0)  # Brief backoff on error

    def _record_error(self) -> None:
        """Record an error timestamp."""
        self._errors_last_hour.append(time.time())
        self._prune_old_errors()

    def _prune_old_errors(self) -> None:
        """Remove error timestamps older than 1 hour."""
        cutoff = time.time() - 3600
        self._errors_last_hour = [t for t in self._errors_last_hour if t > cutoff]


# =============================================================================
# Module-level singleton
# =============================================================================

_poller: RedisQPoller | None = None


async def get_poller(config: RedisQConfig | None = None) -> RedisQPoller:
    """
    Get or create the RedisQ poller singleton.

    Args:
        config: Configuration for new poller (ignored if already created)

    Returns:
        RedisQPoller instance
    """
    global _poller

    if _poller is None:
        if config is None:
            from ...core.config import get_settings

            settings = get_settings()
            db = get_realtime_database()
            queue_id = db.get_queue_id() or ""
            config = RedisQConfig.from_settings(settings, queue_id)

        _poller = RedisQPoller(config=config)

    return _poller


def reset_poller() -> None:
    """Reset the poller singleton."""
    global _poller
    _poller = None
