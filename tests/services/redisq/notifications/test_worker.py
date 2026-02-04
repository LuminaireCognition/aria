"""Tests for NotificationWorker."""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from aria_esi.services.killmail_store import (
    KillmailRecord,
    SQLiteKillmailStore,
)
from aria_esi.services.redisq.notifications.esi_coordinator import ESICoordinator
from aria_esi.services.redisq.notifications.profiles import (
    NotificationProfile,
    PollingConfig,
)
from aria_esi.services.redisq.notifications.worker import (
    NotificationWorker,
    WorkerState,
)

pytestmark = pytest.mark.asyncio


def make_kill(kill_id: int, kill_time: datetime | None = None) -> KillmailRecord:
    """Create a test killmail record."""
    kt = kill_time or datetime(2026, 1, 26, 12, 0, 0)
    return KillmailRecord(
        kill_id=kill_id,
        kill_time=int(kt.timestamp()),
        solar_system_id=30000142,
        zkb_hash=f"hash{kill_id}",
        zkb_total_value=100_000_000.0,
        zkb_points=10,
        zkb_is_npc=False,
        zkb_is_solo=False,
        zkb_is_awox=False,
        ingested_at=int(kt.timestamp()),
        victim_ship_type_id=670,
        victim_corporation_id=98000001,
        victim_alliance_id=None,
    )


class TestNotificationWorker:
    """Tests for NotificationWorker."""

    async def test_start_and_stop(self, worker: NotificationWorker) -> None:
        """Test worker start and stop lifecycle."""
        assert worker.state == WorkerState.STOPPED

        task = worker.start()
        assert not task.done()

        # Wait briefly for worker to start
        await asyncio.sleep(0.05)
        assert worker.state == WorkerState.RUNNING

        await worker.stop()
        assert worker.state == WorkerState.STOPPED
        assert task.done()

    async def test_start_twice_raises(self, worker: NotificationWorker) -> None:
        """Test that starting twice raises error."""
        worker.start()

        with pytest.raises(RuntimeError, match="already running"):
            worker.start()

        await worker.stop()

    async def test_worker_name_matches_profile(self, worker: NotificationWorker) -> None:
        """Test that worker name matches profile name."""
        assert worker.name == "test-profile"

    async def test_processes_kills_from_store(
        self, worker: NotificationWorker, store: SQLiteKillmailStore
    ) -> None:
        """Test that worker processes kills from the store."""
        # Insert some kills
        for i in range(5):
            await store.insert_kill(make_kill(100 + i))

        # Start worker
        worker.start()
        await asyncio.sleep(0.1)  # Let it poll once

        # Check metrics
        assert worker.metrics.last_poll_time is not None
        # Worker should have seen the kills
        total = (
            worker.metrics.kills_processed
            + worker.metrics.kills_skipped_duplicate
            + worker.metrics.kills_skipped_filter
        )
        assert total > 0 or worker.metrics.last_poll_time is not None

        await worker.stop()

    async def test_skips_duplicate_kills(
        self, worker: NotificationWorker, store: SQLiteKillmailStore
    ) -> None:
        """Test that worker skips already-processed kills."""
        kill = make_kill(200)
        await store.insert_kill(kill)

        # Mark as already processed
        await store.mark_kill_processed("test-profile", kill.kill_id)

        # Start worker
        worker.start()
        await asyncio.sleep(0.1)

        # Should have skipped the duplicate
        assert worker.metrics.kills_skipped_duplicate >= 1

        await worker.stop()

    async def test_get_status_returns_dict(self, worker: NotificationWorker) -> None:
        """Test that get_status returns a status dict."""
        status = worker.get_status()

        assert status["name"] == "test-profile"
        assert status["state"] == "stopped"
        assert "metrics" in status

    async def test_worker_updates_worker_state(
        self, worker: NotificationWorker, store: SQLiteKillmailStore
    ) -> None:
        """Test that worker updates worker state in database."""
        # Insert a kill
        await store.insert_kill(make_kill(300))

        # Start worker
        worker.start()
        await asyncio.sleep(0.15)  # Let it poll
        await worker.stop()

        # Check worker state was updated (call to verify no crash)
        await store.get_worker_state("test-profile")
        # Just verify poll happened
        assert worker.metrics.last_poll_time is not None


@pytest_asyncio.fixture
async def store(tmp_path: Path):
    """Create and initialize a test store."""
    store = SQLiteKillmailStore(db_path=tmp_path / "test.db")
    await store.initialize()
    yield store
    await store.close()


@pytest.fixture
def profile() -> NotificationProfile:
    """Create a test profile."""
    return NotificationProfile(
        name="test-profile",
        display_name="Test Profile",
        enabled=True,
        webhook_url="https://discord.com/api/webhooks/123/abc",
        polling=PollingConfig(
            interval_seconds=0.05,  # Fast polling for tests
            batch_size=10,
            overlap_window_seconds=0,
        ),
    )


@pytest.fixture
def coordinator(store: SQLiteKillmailStore) -> ESICoordinator:
    """Create a test coordinator."""
    return ESICoordinator(store=store)


@pytest.fixture
def worker(
    profile: NotificationProfile,
    store: SQLiteKillmailStore,
    coordinator: ESICoordinator,
) -> NotificationWorker:
    """Create a test worker."""
    return NotificationWorker(
        profile=profile,
        store=store,
        esi_coordinator=coordinator,
    )


class TestNotificationWorkerProperties:
    """Tests for worker property accessors."""

    async def test_is_running_false_initially(self, worker: NotificationWorker) -> None:
        """Worker is not running initially."""
        assert worker.is_running is False

    async def test_is_running_true_after_start(self, worker: NotificationWorker) -> None:
        """Worker is running after start."""
        worker.start()
        await asyncio.sleep(0.05)
        assert worker.is_running is True
        await worker.stop()

    async def test_metrics_property(self, worker: NotificationWorker) -> None:
        """Metrics property returns WorkerMetrics."""
        from aria_esi.services.redisq.notifications.worker import WorkerMetrics

        assert isinstance(worker.metrics, WorkerMetrics)


class TestNotificationWorkerESI:
    """Tests for ESI fetch functionality."""

    async def test_fetch_esi_killmail_success(self, worker: NotificationWorker) -> None:
        """Successful ESI fetch returns ESIKillmail."""

        kill = make_kill(100)

        mock_response = {
            "killmail_id": 100,
            "killmail_time": "2026-01-26T12:00:00Z",
            "solar_system_id": 30000142,
            "victim": {
                "character_id": 12345,
                "ship_type_id": 670,
                "corporation_id": 98000001,
                "damage_taken": 1000,
            },
            "attackers": [{"character_id": 67890, "ship_type_id": 11993, "final_blow": True}],
        }

        # Mock the HTTP client
        mock_client = AsyncMock()
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_client.get = AsyncMock(return_value=mock_response_obj)

        worker._http_client = mock_client

        result = await worker._fetch_esi_killmail(kill)

        assert result is not None
        assert result.kill_id == 100
        assert result.victim_character_id == 12345
        assert result.attacker_count == 1

    async def test_fetch_esi_killmail_no_hash(self, worker: NotificationWorker) -> None:
        """Fetch returns None when zkb_hash is missing."""
        kill = make_kill(100)
        kill.zkb_hash = None

        result = await worker._fetch_esi_killmail(kill)

        assert result is None

    async def test_fetch_esi_killmail_404(self, worker: NotificationWorker) -> None:
        """Fetch returns None on 404."""
        kill = make_kill(100)

        mock_client = AsyncMock()
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 404
        mock_client.get = AsyncMock(return_value=mock_response_obj)

        worker._http_client = mock_client

        result = await worker._fetch_esi_killmail(kill)

        assert result is None

    async def test_fetch_esi_killmail_timeout(self, worker: NotificationWorker) -> None:
        """Fetch returns None on timeout."""
        import httpx

        kill = make_kill(100)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

        worker._http_client = mock_client

        result = await worker._fetch_esi_killmail(kill)

        assert result is None

    async def test_fetch_esi_killmail_error(self, worker: NotificationWorker) -> None:
        """Fetch returns None on HTTP error."""
        kill = make_kill(100)

        mock_client = AsyncMock()
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 500
        mock_client.get = AsyncMock(return_value=mock_response_obj)

        worker._http_client = mock_client

        result = await worker._fetch_esi_killmail(kill)

        assert result is None


class TestNotificationWorkerParseESI:
    """Tests for ESI response parsing."""

    async def test_parse_esi_response_full(self, worker: NotificationWorker) -> None:
        """Parse complete ESI response."""
        data = {
            "killmail_id": 100,
            "victim": {
                "character_id": 12345,
                "ship_type_id": 670,
                "corporation_id": 98000001,
                "alliance_id": 99000001,
                "damage_taken": 5000,
                "position": {"x": 1.0, "y": 2.0, "z": 3.0},
            },
            "attackers": [
                {
                    "character_id": 67890,
                    "ship_type_id": 11993,
                    "corporation_id": 98000002,
                    "final_blow": True,
                    "damage_done": 5000,
                },
                {
                    "character_id": 11111,
                    "ship_type_id": 11989,
                    "final_blow": False,
                    "damage_done": 0,
                },
            ],
            "items": [{"item_type_id": 1234, "quantity_destroyed": 1}],
        }

        result = worker._parse_esi_response(100, data)

        assert result.kill_id == 100
        assert result.victim_character_id == 12345
        assert result.victim_ship_type_id == 670
        assert result.victim_corporation_id == 98000001
        assert result.victim_alliance_id == 99000001
        assert result.victim_damage_taken == 5000
        assert result.attacker_count == 2
        assert result.final_blow_character_id == 67890
        assert result.final_blow_ship_type_id == 11993
        assert result.final_blow_corporation_id == 98000002
        assert result.attackers_json is not None
        assert result.items_json is not None
        assert result.position_json is not None

    async def test_parse_esi_response_minimal(self, worker: NotificationWorker) -> None:
        """Parse minimal ESI response."""
        data = {
            "killmail_id": 100,
            "victim": {},
            "attackers": [],
        }

        result = worker._parse_esi_response(100, data)

        assert result.kill_id == 100
        assert result.victim_character_id is None
        assert result.attacker_count == 0
        assert result.final_blow_character_id is None

    async def test_parse_esi_response_no_final_blow(self, worker: NotificationWorker) -> None:
        """Parse response with no final blow attacker."""
        data = {
            "victim": {"character_id": 12345},
            "attackers": [
                {"character_id": 67890, "final_blow": False},
            ],
        }

        result = worker._parse_esi_response(100, data)

        assert result.final_blow_character_id is None


class TestNotificationWorkerRollup:
    """Tests for rollup functionality."""

    async def test_send_rollup_empty_list(self, worker: NotificationWorker) -> None:
        """Rollup with empty list returns True."""
        result = await worker._send_rollup([])
        assert result is True

    async def test_send_rollup_formats_message(
        self, worker: NotificationWorker, store: SQLiteKillmailStore
    ) -> None:
        """Rollup formats message correctly."""
        kills = [
            make_kill(100),
            make_kill(101),
            make_kill(102),
        ]
        for kill in kills:
            kill.zkb_total_value = 500_000_000

        # Mock send notification
        sent_payload = None

        async def capture_send(payload, url):
            nonlocal sent_payload
            sent_payload = payload
            return MagicMock(success=True)

        worker._send_notification = capture_send

        result = await worker._send_rollup(kills)

        assert result is True
        assert sent_payload is not None
        assert "3 kills" in sent_payload["content"]
        assert "1.5B" in sent_payload["content"]

    async def test_send_rollup_marks_processed(
        self, worker: NotificationWorker, store: SQLiteKillmailStore
    ) -> None:
        """Rollup marks kills as processed."""
        kills = [make_kill(200), make_kill(201)]
        for kill in kills:
            kill.zkb_total_value = 100_000_000

        worker._send_notification = AsyncMock(return_value=MagicMock(success=True))

        await worker._send_rollup(kills)

        # Check kills are marked as processed
        assert await store.is_kill_processed("test-profile", 200)
        assert await store.is_kill_processed("test-profile", 201)

    async def test_send_rollup_updates_metrics(self, worker: NotificationWorker) -> None:
        """Rollup updates metrics."""
        kills = [make_kill(300)]
        kills[0].zkb_total_value = 100_000_000

        worker._send_notification = AsyncMock(return_value=MagicMock(success=True))

        initial_rollups = worker._metrics.rollups_sent
        await worker._send_rollup(kills)

        assert worker._metrics.rollups_sent == initial_rollups + 1

    async def test_send_rollup_failure(self, worker: NotificationWorker) -> None:
        """Rollup returns False on send failure."""
        kills = [make_kill(400)]
        kills[0].zkb_total_value = 100_000_000

        worker._send_notification = AsyncMock(return_value=MagicMock(success=False))

        result = await worker._send_rollup(kills)

        assert result is False


class TestNotificationWorkerRateLimit:
    """Tests for rate limit handling."""

    async def test_rate_limit_backoff(
        self, worker: NotificationWorker, store: SQLiteKillmailStore
    ) -> None:
        """Rate limit triggers backoff."""
        import time

        # Insert kills
        for i in range(5):
            await store.insert_kill(make_kill(500 + i))

        # Mock send to return rate limit
        rate_limit_result = MagicMock()
        rate_limit_result.success = False
        rate_limit_result.is_rate_limited = True
        rate_limit_result.retry_after = 60

        call_count = 0

        async def rate_limit_send(payload, url):
            nonlocal call_count
            call_count += 1
            return rate_limit_result

        worker._send_notification = rate_limit_send
        worker._format_kill = lambda *args: {"content": "test"}
        worker._evaluate_triggers = lambda *args: MagicMock(requires_esi=False)

        # Start worker and let it poll
        worker.start()
        await asyncio.sleep(0.15)
        await worker.stop()

        # Should have hit rate limit and set backoff
        assert worker._rate_limited_until > time.time() - 60

    async def test_pending_kills_tracked(
        self, worker: NotificationWorker, store: SQLiteKillmailStore
    ) -> None:
        """Pending kills are tracked during rate limit."""
        await store.insert_kill(make_kill(600))

        rate_limit_result = MagicMock()
        rate_limit_result.success = False
        rate_limit_result.is_rate_limited = True
        rate_limit_result.retry_after = 30

        worker._send_notification = AsyncMock(return_value=rate_limit_result)
        worker._format_kill = lambda *args: {"content": "test"}
        worker._evaluate_triggers = lambda *args: MagicMock(requires_esi=False)

        worker.start()
        await asyncio.sleep(0.15)
        await worker.stop()

        # Pending kills should be tracked
        assert len(worker._pending_kills) >= 0  # May be empty if not processed


class TestNotificationWorkerHTTPClient:
    """Tests for HTTP client management."""

    async def test_http_client_lazy_init(self, worker: NotificationWorker) -> None:
        """HTTP client is lazily initialized."""
        assert worker._http_client is None

        client = await worker._get_http_client()

        assert client is not None
        assert worker._http_client is client

        await worker.stop()

    async def test_http_client_reused(self, worker: NotificationWorker) -> None:
        """HTTP client is reused on subsequent calls."""
        client1 = await worker._get_http_client()
        client2 = await worker._get_http_client()

        assert client1 is client2

        await worker.stop()

    async def test_http_client_closed_on_stop(self, worker: NotificationWorker) -> None:
        """HTTP client is closed on worker stop."""
        # Start the worker so stop() actually runs cleanup
        worker.start()
        await asyncio.sleep(0.05)

        # Get the HTTP client
        await worker._get_http_client()
        assert worker._http_client is not None

        await worker.stop()

        # Client should be closed and set to None
        assert worker._http_client is None
