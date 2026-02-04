"""
Tests for RedisQ poller module.
"""

from __future__ import annotations

import asyncio
import sqlite3
import sys
import time
from datetime import datetime, UTC
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import httpx
import pytest

from aria_esi.services.redisq.database import RealtimeKillsDatabase
from aria_esi.services.redisq.models import (
    IngestMetrics,
    PollerStatus,
    ProcessedKill,
    QueuedKill,
    RedisQConfig,
)
from aria_esi.services.redisq.poller import (
    RedisQPoller,
    get_poller,
    reset_poller,
    REDISQ_URL,
)


@pytest.fixture
def db(tmp_path: Path) -> RealtimeKillsDatabase:
    """Create a test database."""
    db_path = tmp_path / "test.db"

    # Initialize schema
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS realtime_kills (
            kill_id INTEGER PRIMARY KEY,
            kill_time INTEGER NOT NULL,
            solar_system_id INTEGER NOT NULL,
            victim_ship_type_id INTEGER,
            victim_corporation_id INTEGER,
            victim_alliance_id INTEGER,
            attacker_count INTEGER,
            attacker_corps TEXT,
            attacker_alliances TEXT,
            attacker_ship_types TEXT,
            final_blow_ship_type_id INTEGER,
            total_value REAL,
            is_pod_kill INTEGER DEFAULT 0,
            watched_entity_match INTEGER DEFAULT 0,
            watched_entity_ids TEXT,
            created_at INTEGER DEFAULT (strftime('%s', 'now'))
        );

        CREATE TABLE IF NOT EXISTS redisq_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at INTEGER NOT NULL
        );
    """)
    conn.commit()
    conn.close()

    db = RealtimeKillsDatabase(db_path, ensure_schema=False)
    yield db
    db.close()


@pytest.fixture
def config() -> RedisQConfig:
    """Create a test config."""
    return RedisQConfig(
        enabled=True,
        queue_id="test-queue-123",
        poll_interval_seconds=10,
        filter_regions=[],
        min_value_isk=0,
        retention_hours=24,
    )


@pytest.fixture
def mock_fetch_queue():
    """Create a mock fetch queue."""
    mock_queue = MagicMock()
    mock_queue.start_processing = AsyncMock()
    mock_queue.stop_processing = AsyncMock()
    mock_queue.enqueue = AsyncMock()
    mock_queue.backlog_size = 0
    return mock_queue


@pytest.fixture
def mock_ingest_queue():
    """Create a mock ingest queue."""
    mock_queue = MagicMock()
    mock_queue.put = AsyncMock()
    mock_queue.get_batch = AsyncMock(return_value=[])
    mock_queue.mark_written = MagicMock()
    mock_queue.wait_for_items = AsyncMock(return_value=False)
    mock_queue.get_metrics = MagicMock(return_value=MagicMock(
        received_total=10,
        written_total=8,
        dropped_total=2,
        queue_depth=0,
        last_drop_time=None,
    ))
    return mock_queue


class TestPollTimePersistence:
    """Tests for poll time persistence."""

    @pytest.mark.asyncio
    async def test_poll_time_persisted_on_stop(self, db: RealtimeKillsDatabase, config: RedisQConfig):
        """Test that last poll time is persisted when poller stops."""
        with patch("aria_esi.services.redisq.poller.get_realtime_database", return_value=db):
            with patch("aria_esi.services.redisq.poller.get_fetch_queue") as mock_fetch_queue:
                mock_queue = MagicMock()
                mock_queue.start_processing = AsyncMock()
                mock_queue.stop_processing = AsyncMock()
                mock_fetch_queue.return_value = mock_queue

                poller = RedisQPoller(config=config)

                # Simulate having polled
                poller._last_poll_time = datetime.now(UTC).replace(tzinfo=None)
                poller._running = True

                # Stop should persist the poll time
                await poller.stop()

                # Verify poll time was persisted
                persisted = db.get_last_poll_time()
                assert persisted is not None
                assert abs((persisted - poller._last_poll_time).total_seconds()) < 1

    @pytest.mark.asyncio
    async def test_poll_time_not_persisted_if_never_polled(
        self, db: RealtimeKillsDatabase, config: RedisQConfig
    ):
        """Test that no poll time is persisted if poller never polled."""
        with patch("aria_esi.services.redisq.poller.get_realtime_database", return_value=db):
            with patch("aria_esi.services.redisq.poller.get_fetch_queue") as mock_fetch_queue:
                mock_queue = MagicMock()
                mock_queue.start_processing = AsyncMock()
                mock_queue.stop_processing = AsyncMock()
                mock_fetch_queue.return_value = mock_queue

                poller = RedisQPoller(config=config)
                poller._running = True
                # _last_poll_time is None by default

                await poller.stop()

                # Should not have persisted anything
                assert db.get_last_poll_time() is None

    def test_persist_interval_configured(self, config: RedisQConfig):
        """Test that persist interval is configured."""
        poller = RedisQPoller(config=config)

        # Should persist every 60 seconds by default
        assert poller._persist_interval_seconds == 60
        assert poller._last_persisted_poll_time == 0.0


class TestPollerStartup:
    """Tests for poller startup behavior."""

    @pytest.mark.asyncio
    async def test_start_generates_queue_id_if_none(
        self, db: RealtimeKillsDatabase, mock_fetch_queue
    ):
        """Test that start generates a queue ID if none exists."""
        config = RedisQConfig(enabled=True, queue_id="")

        # Mock the dynamic imports that happen inside start()
        mock_entity_filter_module = MagicMock()
        mock_entity_filter_module.EntityAwareFilter.side_effect = Exception("Skip init")

        mock_topology_module = MagicMock()
        mock_topology_module.TopologyFilter.from_config.side_effect = Exception("Skip init")

        mock_war_context_module = MagicMock()
        mock_war_context_module.get_war_context_provider.side_effect = Exception("Skip init")

        mock_notification_module = MagicMock()
        mock_notification_module.get_notification_manager.side_effect = Exception("Skip init")

        mock_name_resolver_module = MagicMock()
        mock_name_resolver_module.get_name_resolver.side_effect = Exception("Skip init")

        mock_settings_module = MagicMock()
        mock_settings_module.get_settings.side_effect = Exception("Skip init")

        with (
            patch("aria_esi.services.redisq.poller.get_realtime_database", return_value=db),
            patch("aria_esi.services.redisq.poller.get_fetch_queue", return_value=mock_fetch_queue),
            patch("aria_esi.services.redisq.poller.create_filter_from_config"),
            patch.dict("sys.modules", {
                "aria_esi.services.redisq.entity_filter": mock_entity_filter_module,
                "aria_esi.services.redisq.topology": mock_topology_module,
                "aria_esi.services.redisq.war_context": mock_war_context_module,
                "aria_esi.services.redisq.notifications": mock_notification_module,
                "aria_esi.services.redisq.name_resolver": mock_name_resolver_module,
                "aria_esi.core.config": mock_settings_module,
            }),
        ):
            poller = RedisQPoller(config=config)
            await poller.start()

            try:
                # Queue ID should have been generated
                assert config.queue_id.startswith("aria-")
                assert len(config.queue_id) == 13  # "aria-" + 8 hex chars
            finally:
                await poller.stop()

    @pytest.mark.asyncio
    async def test_start_uses_existing_queue_id(
        self, db: RealtimeKillsDatabase, mock_fetch_queue
    ):
        """Test that start uses existing queue ID from database."""
        existing_id = "aria-existing1"
        db.set_queue_id(existing_id)

        config = RedisQConfig(enabled=True, queue_id="")

        # Mock the dynamic imports that happen inside start()
        mock_entity_filter_module = MagicMock()
        mock_entity_filter_module.EntityAwareFilter.side_effect = Exception("Skip init")

        mock_topology_module = MagicMock()
        mock_topology_module.TopologyFilter.from_config.side_effect = Exception("Skip init")

        mock_war_context_module = MagicMock()
        mock_war_context_module.get_war_context_provider.side_effect = Exception("Skip init")

        mock_notification_module = MagicMock()
        mock_notification_module.get_notification_manager.side_effect = Exception("Skip init")

        mock_name_resolver_module = MagicMock()
        mock_name_resolver_module.get_name_resolver.side_effect = Exception("Skip init")

        mock_settings_module = MagicMock()
        mock_settings_module.get_settings.side_effect = Exception("Skip init")

        with (
            patch("aria_esi.services.redisq.poller.get_realtime_database", return_value=db),
            patch("aria_esi.services.redisq.poller.get_fetch_queue", return_value=mock_fetch_queue),
            patch("aria_esi.services.redisq.poller.create_filter_from_config"),
            patch.dict("sys.modules", {
                "aria_esi.services.redisq.entity_filter": mock_entity_filter_module,
                "aria_esi.services.redisq.topology": mock_topology_module,
                "aria_esi.services.redisq.war_context": mock_war_context_module,
                "aria_esi.services.redisq.notifications": mock_notification_module,
                "aria_esi.services.redisq.name_resolver": mock_name_resolver_module,
                "aria_esi.core.config": mock_settings_module,
            }),
        ):
            poller = RedisQPoller(config=config)
            await poller.start()

            try:
                assert config.queue_id == existing_id
            finally:
                await poller.stop()

    @pytest.mark.asyncio
    async def test_start_idempotent_if_already_running(
        self, db: RealtimeKillsDatabase, config: RedisQConfig, mock_fetch_queue
    ):
        """Test that start is idempotent if already running."""
        # Mock the dynamic imports that happen inside start()
        mock_entity_filter_module = MagicMock()
        mock_entity_filter_module.EntityAwareFilter.side_effect = Exception("Skip init")

        mock_topology_module = MagicMock()
        mock_topology_module.TopologyFilter.from_config.side_effect = Exception("Skip init")

        mock_war_context_module = MagicMock()
        mock_war_context_module.get_war_context_provider.side_effect = Exception("Skip init")

        mock_notification_module = MagicMock()
        mock_notification_module.get_notification_manager.side_effect = Exception("Skip init")

        mock_name_resolver_module = MagicMock()
        mock_name_resolver_module.get_name_resolver.side_effect = Exception("Skip init")

        mock_settings_module = MagicMock()
        mock_settings_module.get_settings.side_effect = Exception("Skip init")

        with (
            patch("aria_esi.services.redisq.poller.get_realtime_database", return_value=db),
            patch("aria_esi.services.redisq.poller.get_fetch_queue", return_value=mock_fetch_queue),
            patch("aria_esi.services.redisq.poller.create_filter_from_config"),
            patch.dict("sys.modules", {
                "aria_esi.services.redisq.entity_filter": mock_entity_filter_module,
                "aria_esi.services.redisq.topology": mock_topology_module,
                "aria_esi.services.redisq.war_context": mock_war_context_module,
                "aria_esi.services.redisq.notifications": mock_notification_module,
                "aria_esi.services.redisq.name_resolver": mock_name_resolver_module,
                "aria_esi.core.config": mock_settings_module,
            }),
        ):
            poller = RedisQPoller(config=config)
            await poller.start()

            try:
                # Second start should be a no-op
                await poller.start()
                assert poller._running is True
            finally:
                await poller.stop()


class TestPollerStop:
    """Tests for poller stop behavior."""

    @pytest.mark.asyncio
    async def test_stop_idempotent_if_not_running(self, config: RedisQConfig):
        """Test that stop is idempotent if not running."""
        poller = RedisQPoller(config=config)
        # Should not raise
        await poller.stop()
        assert poller._running is False

    @pytest.mark.asyncio
    async def test_stop_cancels_all_tasks(
        self, db: RealtimeKillsDatabase, config: RedisQConfig, mock_fetch_queue
    ):
        """Test that stop cancels all background tasks."""
        # Mock the dynamic imports that happen inside start()
        mock_entity_filter_module = MagicMock()
        mock_entity_filter_module.EntityAwareFilter.side_effect = Exception("Skip init")

        mock_topology_module = MagicMock()
        mock_topology_module.TopologyFilter.from_config.side_effect = Exception("Skip init")

        mock_war_context_module = MagicMock()
        mock_war_context_module.get_war_context_provider.side_effect = Exception("Skip init")

        mock_notification_module = MagicMock()
        mock_notification_module.get_notification_manager.side_effect = Exception("Skip init")

        mock_name_resolver_module = MagicMock()
        mock_name_resolver_module.get_name_resolver.side_effect = Exception("Skip init")

        mock_settings_module = MagicMock()
        mock_settings_module.get_settings.side_effect = Exception("Skip init")

        with (
            patch("aria_esi.services.redisq.poller.get_realtime_database", return_value=db),
            patch("aria_esi.services.redisq.poller.get_fetch_queue", return_value=mock_fetch_queue),
            patch("aria_esi.services.redisq.poller.create_filter_from_config"),
            patch.dict("sys.modules", {
                "aria_esi.services.redisq.entity_filter": mock_entity_filter_module,
                "aria_esi.services.redisq.topology": mock_topology_module,
                "aria_esi.services.redisq.war_context": mock_war_context_module,
                "aria_esi.services.redisq.notifications": mock_notification_module,
                "aria_esi.services.redisq.name_resolver": mock_name_resolver_module,
                "aria_esi.core.config": mock_settings_module,
            }),
        ):
            poller = RedisQPoller(config=config)
            await poller.start()

            # Capture task references
            poll_task = poller._poll_task
            cleanup_task = poller._cleanup_task
            entity_refresh_task = poller._entity_refresh_task

            await poller.stop()

            # All tasks should be None after stop
            assert poller._poll_task is None
            assert poller._cleanup_task is None
            assert poller._entity_refresh_task is None
            assert poller._running is False

    @pytest.mark.asyncio
    async def test_stop_flushes_ingest_queue(
        self, db: RealtimeKillsDatabase, config: RedisQConfig, mock_fetch_queue, mock_ingest_queue
    ):
        """Test that stop flushes remaining items from ingest queue."""
        mock_killmail_store = AsyncMock()
        mock_killmail_store.insert_kills_batch = AsyncMock(return_value=5)
        mock_killmail_store.close = AsyncMock()

        remaining_kills = [MagicMock() for _ in range(5)]
        mock_ingest_queue.get_batch = AsyncMock(return_value=remaining_kills)

        with (
            patch("aria_esi.services.redisq.poller.get_realtime_database", return_value=db),
            patch("aria_esi.services.redisq.poller.get_fetch_queue", return_value=mock_fetch_queue),
        ):
            poller = RedisQPoller(config=config)
            poller._running = True
            poller._ingest_queue = mock_ingest_queue
            poller._killmail_store = mock_killmail_store

            await poller.stop()

            # Verify flush happened
            mock_killmail_store.insert_kills_batch.assert_called_once_with(remaining_kills)
            mock_ingest_queue.mark_written.assert_called_once_with(5)
            mock_killmail_store.close.assert_called_once()


class TestPollerHealth:
    """Tests for poller health checks."""

    def test_is_healthy_returns_false_when_not_running(self, config: RedisQConfig):
        """Test is_healthy returns False when not running."""
        poller = RedisQPoller(config=config)
        assert poller.is_healthy() is False

    def test_is_healthy_returns_false_when_poll_stale(self, config: RedisQConfig):
        """Test is_healthy returns False when poll time is stale."""
        poller = RedisQPoller(config=config)
        poller._running = True
        # Set poll time to 3 minutes ago (> 2 minute threshold)
        poller._last_poll_time = datetime.utcnow()
        # Simulate stale poll by manipulating the datetime comparison
        from datetime import timedelta
        poller._last_poll_time = datetime.utcnow() - timedelta(minutes=3)

        assert poller.is_healthy() is False

    def test_is_healthy_returns_false_with_excessive_errors(self, config: RedisQConfig):
        """Test is_healthy returns False with too many errors."""
        poller = RedisQPoller(config=config)
        poller._running = True
        poller._last_poll_time = datetime.utcnow()
        # Add 51 errors in the last hour
        now = time.time()
        poller._errors_last_hour = [now - i for i in range(51)]

        assert poller.is_healthy() is False

    def test_is_healthy_returns_true_when_healthy(self, config: RedisQConfig):
        """Test is_healthy returns True when all conditions met."""
        poller = RedisQPoller(config=config)
        poller._running = True
        poller._last_poll_time = datetime.utcnow()
        poller._errors_last_hour = []

        assert poller.is_healthy() is True


class TestPollerStatus:
    """Tests for poller status reporting."""

    def test_get_status_basic(self, config: RedisQConfig, mock_fetch_queue):
        """Test basic status reporting."""
        with patch("aria_esi.services.redisq.poller.get_fetch_queue", return_value=mock_fetch_queue):
            poller = RedisQPoller(config=config)
            poller._running = True
            poller._kills_processed = 100
            poller._kills_filtered = 50
            poller._last_poll_time = datetime.utcnow()
            poller._last_kill_time = datetime.utcnow()

            status = poller.get_status()

            assert status.is_running is True
            assert status.queue_id == "test-queue-123"
            assert status.kills_processed == 100
            assert status.kills_filtered == 50
            assert status.last_poll_time is not None
            assert status.last_kill_time is not None

    def test_get_status_with_entity_filter(self, config: RedisQConfig, mock_fetch_queue):
        """Test status includes entity filter stats."""
        mock_entity_filter = MagicMock()
        mock_entity_filter.watched_corp_count = 5
        mock_entity_filter.watched_alliance_count = 3

        with patch("aria_esi.services.redisq.poller.get_fetch_queue", return_value=mock_fetch_queue):
            poller = RedisQPoller(config=config)
            poller._running = True
            poller._entity_filter = mock_entity_filter
            poller._watched_entity_kills = 10

            status = poller.get_status()

            assert status.watched_corps_count == 5
            assert status.watched_alliances_count == 3
            assert status.watched_entity_kills == 10

    def test_get_status_with_topology_filter(self, config: RedisQConfig, mock_fetch_queue):
        """Test status includes topology filter stats."""
        mock_topology_filter = MagicMock()
        mock_topology_filter.is_active = True
        mock_topology_filter.interest_map = MagicMock()
        mock_topology_filter.interest_map.total_systems = 100
        mock_topology_filter.get_metrics.return_value = {"passed": 80, "filtered": 20}

        with patch("aria_esi.services.redisq.poller.get_fetch_queue", return_value=mock_fetch_queue):
            poller = RedisQPoller(config=config)
            poller._running = True
            poller._topology_filter = mock_topology_filter

            status = poller.get_status()

            assert status.topology_active is True
            assert status.topology_systems_tracked == 100
            assert status.topology_passed == 80
            assert status.topology_filtered == 20

    def test_get_status_with_ingest_queue(self, config: RedisQConfig, mock_fetch_queue, mock_ingest_queue):
        """Test status includes ingest queue metrics."""
        with patch("aria_esi.services.redisq.poller.get_fetch_queue", return_value=mock_fetch_queue):
            poller = RedisQPoller(config=config)
            poller._running = True
            poller._ingest_queue = mock_ingest_queue

            status = poller.get_status()

            assert status.ingest is not None
            assert status.ingest.received_total == 10
            assert status.ingest.written_total == 8
            assert status.ingest.dropped_total == 2


class TestPollOnce:
    """Tests for single poll operations."""

    @pytest.mark.asyncio
    async def test_poll_once_returns_early_without_client(self, config: RedisQConfig):
        """Test poll_once returns early if client is None."""
        poller = RedisQPoller(config=config)
        poller._client = None
        # Should not raise
        await poller._poll_once()

    @pytest.mark.asyncio
    async def test_poll_once_handles_rate_limit(self, config: RedisQConfig):
        """Test poll_once handles 429 rate limit response."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "5"}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        poller = RedisQPoller(config=config)
        poller._client = mock_client

        with patch("aria_esi.services.redisq.poller.get_realtime_database") as mock_db:
            # Should handle rate limit and sleep
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                await poller._poll_once()
                mock_sleep.assert_called_once_with(5.0)

    @pytest.mark.asyncio
    async def test_poll_once_handles_rate_limit_no_retry_after(self, config: RedisQConfig):
        """Test poll_once uses default backoff without Retry-After header."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        poller = RedisQPoller(config=config)
        poller._client = mock_client

        with patch("aria_esi.services.redisq.poller.get_realtime_database") as mock_db:
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                await poller._poll_once()
                mock_sleep.assert_called_once_with(30.0)

    @pytest.mark.asyncio
    async def test_poll_once_handles_non_200(self, config: RedisQConfig):
        """Test poll_once handles non-200 responses."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        poller = RedisQPoller(config=config)
        poller._client = mock_client

        with patch("aria_esi.services.redisq.poller.get_realtime_database"):
            # Should return without processing
            await poller._poll_once()
            assert poller._last_poll_time is not None

    @pytest.mark.asyncio
    async def test_poll_once_handles_null_package(self, config: RedisQConfig):
        """Test poll_once handles null package (quiet period)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"package": None}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        poller = RedisQPoller(config=config)
        poller._client = mock_client

        with patch("aria_esi.services.redisq.poller.get_realtime_database"):
            await poller._poll_once()
            # Should have updated poll time but no processing
            assert poller._last_poll_time is not None

    @pytest.mark.asyncio
    async def test_poll_once_handles_invalid_package(self, config: RedisQConfig, mock_fetch_queue):
        """Test poll_once handles invalid kill package."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "package": {"killID": 0, "zkb": {"hash": ""}}  # Invalid
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        poller = RedisQPoller(config=config)
        poller._client = mock_client

        with (
            patch("aria_esi.services.redisq.poller.get_realtime_database") as mock_db,
            patch("aria_esi.services.redisq.poller.get_fetch_queue", return_value=mock_fetch_queue),
        ):
            await poller._poll_once()
            # Should not have queued for fetch
            mock_fetch_queue.enqueue.assert_not_called()

    @pytest.mark.asyncio
    async def test_poll_once_skips_existing_kill(
        self, db: RealtimeKillsDatabase, config: RedisQConfig, mock_fetch_queue, mock_ingest_queue
    ):
        """Test poll_once skips kills already in database."""
        # Pre-populate database with a kill - use the public connection getter
        conn = db._get_connection()
        conn.execute(
            "INSERT INTO realtime_kills (kill_id, kill_time, solar_system_id) VALUES (?, ?, ?)",
            (12345, int(time.time()), 30000142),
        )
        conn.commit()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "package": {
                "killID": 12345,
                "zkb": {"hash": "abc123"},
                "killmail": {"solar_system_id": 30000142},
            }
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        poller = RedisQPoller(config=config)
        poller._client = mock_client
        poller._ingest_queue = mock_ingest_queue

        with (
            patch("aria_esi.services.redisq.poller.get_realtime_database", return_value=db),
            patch("aria_esi.services.redisq.poller.get_fetch_queue", return_value=mock_fetch_queue),
        ):
            await poller._poll_once()
            # Should store in ingest queue but not fetch via ESI
            mock_ingest_queue.put.assert_called_once()
            mock_fetch_queue.enqueue.assert_not_called()

    @pytest.mark.asyncio
    async def test_poll_once_queues_new_kill(
        self, db: RealtimeKillsDatabase, config: RedisQConfig, mock_fetch_queue, mock_ingest_queue
    ):
        """Test poll_once queues new kills for ESI fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "package": {
                "killID": 99999,
                "zkb": {"hash": "newhash"},
                "killmail": {"solar_system_id": 30000142},
            }
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        poller = RedisQPoller(config=config)
        poller._client = mock_client
        poller._ingest_queue = mock_ingest_queue

        with (
            patch("aria_esi.services.redisq.poller.get_realtime_database", return_value=db),
            patch("aria_esi.services.redisq.poller.get_fetch_queue", return_value=mock_fetch_queue),
        ):
            await poller._poll_once()
            # Should store in ingest queue and queue for ESI fetch
            mock_ingest_queue.put.assert_called_once()
            mock_fetch_queue.enqueue.assert_called_once()

    @pytest.mark.asyncio
    async def test_poll_once_handles_timeout(self, config: RedisQConfig):
        """Test poll_once handles HTTP timeout gracefully."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

        poller = RedisQPoller(config=config)
        poller._client = mock_client

        # Should not raise
        await poller._poll_once()

    @pytest.mark.asyncio
    async def test_poll_once_applies_topology_prefilter(
        self, db: RealtimeKillsDatabase, config: RedisQConfig, mock_fetch_queue, mock_ingest_queue
    ):
        """Test poll_once applies topology pre-filter."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "package": {
                "killID": 77777,
                "zkb": {"hash": "filteredhash"},
                "killmail": {"solar_system_id": 30000142},
            }
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        mock_topology = MagicMock()
        mock_topology.is_active = True
        mock_topology.should_fetch.return_value = False  # Filter it out

        poller = RedisQPoller(config=config)
        poller._client = mock_client
        poller._ingest_queue = mock_ingest_queue
        poller._topology_filter = mock_topology

        with (
            patch("aria_esi.services.redisq.poller.get_realtime_database", return_value=db),
            patch("aria_esi.services.redisq.poller.get_fetch_queue", return_value=mock_fetch_queue),
        ):
            await poller._poll_once()
            # Should store but not fetch
            mock_ingest_queue.put.assert_called_once()
            mock_fetch_queue.enqueue.assert_not_called()


class TestPollLoop:
    """Tests for main polling loop."""

    @pytest.mark.asyncio
    async def test_poll_loop_handles_errors_with_backoff(self, config: RedisQConfig):
        """Test poll loop handles errors with exponential backoff."""
        poller = RedisQPoller(config=config)
        poller._running = True

        call_count = 0
        max_consecutive_errors = 0

        async def mock_poll_once():
            nonlocal call_count, max_consecutive_errors
            call_count += 1
            # Track max errors seen
            max_consecutive_errors = max(max_consecutive_errors, poller._consecutive_errors)
            if call_count < 3:
                raise Exception("Test error")
            poller._running = False  # Stop after 3 calls

        poller._poll_once = mock_poll_once

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await poller._poll_loop()

            # Should have recorded errors and done backoff
            # Note: consecutive_errors is reset to 0 after success, so check errors_last_hour
            assert len(poller._errors_last_hour) == 2  # Two errors were recorded
            assert mock_sleep.call_count >= 2  # Two backoffs for two errors

    @pytest.mark.asyncio
    async def test_poll_loop_resets_errors_on_success(self, config: RedisQConfig):
        """Test poll loop resets consecutive errors on successful poll."""
        poller = RedisQPoller(config=config)
        poller._running = True
        poller._consecutive_errors = 5

        call_count = 0

        async def mock_poll_once():
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                poller._running = False

        poller._poll_once = mock_poll_once

        await poller._poll_loop()

        assert poller._consecutive_errors == 0


class TestOnKillProcessed:
    """Tests for kill processed callback."""

    def test_on_kill_processed_filters_by_topology(
        self, db: RealtimeKillsDatabase, config: RedisQConfig
    ):
        """Test _on_kill_processed filters by topology."""
        mock_topology = MagicMock()
        mock_topology.is_active = True
        mock_topology.calculator = MagicMock()
        mock_topology.calculator.should_fetch.return_value = False

        kill = ProcessedKill(
            kill_id=1,
            kill_time=datetime.utcnow(),
            solar_system_id=30000142,
            victim_ship_type_id=587,
            victim_corporation_id=123,
            victim_alliance_id=None,
            attacker_count=1,
            attacker_corps=[456],
            attacker_alliances=[],
            attacker_ship_types=[587],
            final_blow_ship_type_id=587,
            total_value=1000000.0,
            is_pod_kill=False,
        )

        with patch("aria_esi.services.redisq.poller.get_realtime_database", return_value=db):
            poller = RedisQPoller(config=config)
            poller._topology_filter = mock_topology
            poller._on_kill_processed(kill)

            assert poller._kills_filtered == 1
            assert poller._kills_processed == 0

    def test_on_kill_processed_filters_by_main_filter(
        self, db: RealtimeKillsDatabase, config: RedisQConfig
    ):
        """Test _on_kill_processed filters by main filter."""
        mock_filter = MagicMock()
        mock_filter.process_kill.return_value = (False, None)

        kill = ProcessedKill(
            kill_id=1,
            kill_time=datetime.utcnow(),
            solar_system_id=30000142,
            victim_ship_type_id=587,
            victim_corporation_id=123,
            victim_alliance_id=None,
            attacker_count=1,
            attacker_corps=[456],
            attacker_alliances=[],
            attacker_ship_types=[587],
            final_blow_ship_type_id=587,
            total_value=1000000.0,
            is_pod_kill=False,
        )

        with patch("aria_esi.services.redisq.poller.get_realtime_database", return_value=db):
            poller = RedisQPoller(config=config)
            poller._filter = mock_filter
            poller._on_kill_processed(kill)

            assert poller._kills_filtered == 1
            assert poller._kills_processed == 0

    def test_on_kill_processed_saves_accepted_kill(
        self, db: RealtimeKillsDatabase, config: RedisQConfig
    ):
        """Test _on_kill_processed saves accepted kills."""
        mock_filter = MagicMock()
        mock_filter.process_kill.return_value = (True, None)

        kill = ProcessedKill(
            kill_id=12345,
            kill_time=datetime.utcnow(),
            solar_system_id=30000142,
            victim_ship_type_id=587,
            victim_corporation_id=123,
            victim_alliance_id=None,
            attacker_count=1,
            attacker_corps=[456],
            attacker_alliances=[],
            attacker_ship_types=[587],
            final_blow_ship_type_id=587,
            total_value=1000000.0,
            is_pod_kill=False,
        )

        with patch("aria_esi.services.redisq.poller.get_realtime_database", return_value=db):
            poller = RedisQPoller(config=config)
            poller._filter = mock_filter
            poller._on_kill_processed(kill)

            assert poller._kills_processed == 1
            assert poller._last_kill_time == kill.kill_time

    def test_on_kill_processed_tracks_entity_matches(
        self, db: RealtimeKillsDatabase, config: RedisQConfig
    ):
        """Test _on_kill_processed tracks entity matches."""
        mock_entity_match = MagicMock()
        mock_entity_match.has_match = True
        mock_entity_match.match_types = ["victim_corp"]
        mock_entity_match.all_matched_ids = [123456]  # Real list for JSON serialization

        mock_filter = MagicMock()
        mock_filter.process_kill.return_value = (True, mock_entity_match)

        kill = ProcessedKill(
            kill_id=12345,
            kill_time=datetime.utcnow(),
            solar_system_id=30000142,
            victim_ship_type_id=587,
            victim_corporation_id=123,
            victim_alliance_id=None,
            attacker_count=1,
            attacker_corps=[456],
            attacker_alliances=[],
            attacker_ship_types=[587],
            final_blow_ship_type_id=587,
            total_value=1000000.0,
            is_pod_kill=False,
        )

        with patch("aria_esi.services.redisq.poller.get_realtime_database", return_value=db):
            poller = RedisQPoller(config=config)
            poller._filter = mock_filter
            poller._on_kill_processed(kill)

            assert poller._watched_entity_kills == 1


class TestBackgroundLoops:
    """Tests for background maintenance loops."""

    @pytest.mark.asyncio
    async def test_cleanup_loop_runs_cleanup(self, config: RedisQConfig):
        """Test cleanup loop runs periodic cleanup."""
        poller = RedisQPoller(config=config)
        poller._running = True

        call_count = 0

        async def controlled_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                poller._running = False

        mock_threat_cache = MagicMock()
        mock_threat_cache.cleanup_old_data.return_value = (10, 5)

        mock_threat_cache_module = MagicMock()
        mock_threat_cache_module.get_threat_cache.return_value = mock_threat_cache

        with (
            patch("asyncio.sleep", side_effect=controlled_sleep),
            patch.dict("sys.modules", {
                "aria_esi.services.redisq.threat_cache": mock_threat_cache_module,
            }),
        ):
            await poller._cleanup_loop()

    @pytest.mark.asyncio
    async def test_entity_refresh_loop_refreshes_cache(self, config: RedisQConfig):
        """Test entity refresh loop refreshes cache."""
        mock_entity_filter = MagicMock()
        mock_entity_filter.watched_corp_count = 5
        mock_entity_filter.watched_alliance_count = 3

        poller = RedisQPoller(config=config)
        poller._running = True
        poller._entity_filter = mock_entity_filter

        call_count = 0

        async def controlled_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                poller._running = False

        with patch("asyncio.sleep", side_effect=controlled_sleep):
            await poller._entity_refresh_loop()

            mock_entity_filter.refresh_cache.assert_called()

    @pytest.mark.asyncio
    async def test_writer_loop_writes_batches(self, config: RedisQConfig, mock_ingest_queue):
        """Test writer loop writes batches to store."""
        mock_killmail_store = AsyncMock()
        mock_killmail_store.insert_kills_batch = AsyncMock(return_value=5)

        mock_ingest_queue.wait_for_items = AsyncMock(return_value=True)
        mock_ingest_queue.get_batch = AsyncMock(return_value=[MagicMock() for _ in range(5)])

        poller = RedisQPoller(config=config)
        poller._running = True
        poller._ingest_queue = mock_ingest_queue
        poller._killmail_store = mock_killmail_store

        call_count = 0

        original_wait = mock_ingest_queue.wait_for_items

        async def controlled_wait(timeout):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                poller._running = False
                return False
            return True

        mock_ingest_queue.wait_for_items = controlled_wait

        await poller._writer_loop()

        mock_killmail_store.insert_kills_batch.assert_called()
        mock_ingest_queue.mark_written.assert_called()


class TestErrorTracking:
    """Tests for error tracking functionality."""

    def test_record_error_adds_timestamp(self, config: RedisQConfig):
        """Test _record_error adds error timestamp."""
        poller = RedisQPoller(config=config)
        assert len(poller._errors_last_hour) == 0

        poller._record_error()

        assert len(poller._errors_last_hour) == 1
        assert poller._errors_last_hour[0] <= time.time()

    def test_prune_old_errors_removes_old(self, config: RedisQConfig):
        """Test _prune_old_errors removes old errors."""
        poller = RedisQPoller(config=config)
        now = time.time()

        # Add some old and some recent errors
        poller._errors_last_hour = [
            now - 7200,  # 2 hours ago (should be removed)
            now - 3700,  # 1+ hours ago (should be removed)
            now - 1800,  # 30 min ago (should stay)
            now - 60,    # 1 min ago (should stay)
        ]

        poller._prune_old_errors()

        assert len(poller._errors_last_hour) == 2


class TestSingleton:
    """Tests for singleton management functions."""

    @pytest.mark.asyncio
    async def test_get_poller_creates_singleton(self, db: RealtimeKillsDatabase):
        """Test get_poller creates singleton."""
        reset_poller()

        mock_settings = MagicMock()
        mock_settings.redisq_enabled = True
        mock_settings.redisq_regions = []
        mock_settings.redisq_min_value = 0
        mock_settings.redisq_retention_hours = 24

        mock_config_module = MagicMock()
        mock_config_module.get_settings.return_value = mock_settings

        with (
            patch.dict("sys.modules", {
                "aria_esi.core.config": mock_config_module,
            }),
            patch("aria_esi.services.redisq.poller.get_realtime_database", return_value=db),
        ):
            poller1 = await get_poller()
            poller2 = await get_poller()

            assert poller1 is poller2

        reset_poller()

    @pytest.mark.asyncio
    async def test_get_poller_with_config(self, config: RedisQConfig):
        """Test get_poller with provided config."""
        reset_poller()

        poller = await get_poller(config)
        assert poller.config is config

        reset_poller()

    def test_reset_poller_clears_singleton(self, config: RedisQConfig):
        """Test reset_poller clears singleton."""
        # Import the module-level variable
        import aria_esi.services.redisq.poller as poller_module

        poller_module._poller = RedisQPoller(config=config)
        assert poller_module._poller is not None

        reset_poller()

        assert poller_module._poller is None
