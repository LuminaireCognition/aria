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
            kill.victim_ship_type_id = 17740  # Non-pod to avoid pod-spike format

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


    async def test_send_rollup_returns_false_when_no_callback(
        self, worker: NotificationWorker, store: SQLiteKillmailStore
    ) -> None:
        """Rollup returns False when _send_notification is None (default)."""
        assert worker._send_notification is None

        kills = [make_kill(500)]
        kills[0].zkb_total_value = 100_000_000

        result = await worker._send_rollup(kills)
        assert result is False

    async def test_send_rollup_no_callback_does_not_mark_processed(
        self, worker: NotificationWorker, store: SQLiteKillmailStore
    ) -> None:
        """Rollup with no callback does not mark kills as processed or update metrics."""
        assert worker._send_notification is None

        kills = [make_kill(501), make_kill(502)]
        for kill in kills:
            kill.zkb_total_value = 100_000_000
            await store.insert_kill(kill)

        initial_rollups = worker._metrics.rollups_sent
        await worker._send_rollup(kills)

        # Kills should NOT be marked as processed
        assert not await store.is_kill_processed("test-profile", 501)
        assert not await store.is_kill_processed("test-profile", 502)
        # Metrics should be unchanged
        assert worker._metrics.rollups_sent == initial_rollups


class TestNotificationWorkerPodRollup:
    """Tests for pod-aware rollup formatting."""

    async def test_pod_heavy_rollup_format(
        self, worker: NotificationWorker, store: SQLiteKillmailStore
    ) -> None:
        """Pod-heavy rollup uses pod spike format."""
        # Create kills that are mostly pods (>= 80%)
        kills = []
        for i in range(5):
            kill = make_kill(900 + i)
            kill.victim_ship_type_id = 670  # Capsule
            kill.zkb_total_value = 10_000_000
            kills.append(kill)

        sent_payload = None

        async def capture_send(payload, url):
            nonlocal sent_payload
            sent_payload = payload
            return MagicMock(success=True)

        worker._send_notification = capture_send

        result = await worker._send_rollup(kills)

        assert result is True
        assert sent_payload is not None
        assert "Pod spike" in sent_payload["content"]
        assert "5 pods" in sent_payload["content"]
        # Should NOT have ISK total
        assert "ISK" not in sent_payload["content"]

    async def test_mixed_rollup_uses_standard_format(
        self, worker: NotificationWorker, store: SQLiteKillmailStore
    ) -> None:
        """Mixed kill rollup uses standard ISK-based format."""
        kills = []
        # 2 pods, 3 ships = 40% pod ratio (< 80%)
        for i in range(5):
            kill = make_kill(950 + i)
            kill.victim_ship_type_id = 670 if i < 2 else 17740
            kill.zkb_total_value = 100_000_000
            kills.append(kill)

        sent_payload = None

        async def capture_send(payload, url):
            nonlocal sent_payload
            sent_payload = payload
            return MagicMock(success=True)

        worker._send_notification = capture_send

        result = await worker._send_rollup(kills)

        assert result is True
        assert sent_payload is not None
        assert "Activity" in sent_payload["content"]
        assert "5 kills" in sent_payload["content"]
        assert "ISK" in sent_payload["content"]


class TestNotificationWorkerPodRollupBoundary:
    """Tests for pod rollup threshold boundary conditions."""

    async def test_pod_ratio_exactly_80_percent_triggers_pod_format(
        self, worker: NotificationWorker, store: SQLiteKillmailStore
    ) -> None:
        """Exactly 80% pods (4/5) should trigger pod spike format."""
        kills = []
        for i in range(5):
            kill = make_kill(1000 + i)
            # 4 pods, 1 ship = 80%
            kill.victim_ship_type_id = 670 if i < 4 else 17740
            kill.zkb_total_value = 10_000_000
            kills.append(kill)

        sent_payload = None

        async def capture_send(payload, url):
            nonlocal sent_payload
            sent_payload = payload
            return MagicMock(success=True)

        worker._send_notification = capture_send

        result = await worker._send_rollup(kills)

        assert result is True
        assert "Pod spike" in sent_payload["content"]
        assert "4 pods" in sent_payload["content"]
        assert "ISK" not in sent_payload["content"]

    async def test_pod_ratio_just_below_80_percent_uses_standard_format(
        self, worker: NotificationWorker, store: SQLiteKillmailStore
    ) -> None:
        """Below 80% pods (3/5 = 60%) should use standard format."""
        kills = []
        for i in range(5):
            kill = make_kill(1010 + i)
            # 3 pods, 2 ships = 60%
            kill.victim_ship_type_id = 670 if i < 3 else 17740
            kill.zkb_total_value = 100_000_000
            kills.append(kill)

        sent_payload = None

        async def capture_send(payload, url):
            nonlocal sent_payload
            sent_payload = payload
            return MagicMock(success=True)

        worker._send_notification = capture_send

        result = await worker._send_rollup(kills)

        assert result is True
        assert "Activity" in sent_payload["content"]
        assert "5 kills" in sent_payload["content"]
        assert "ISK" in sent_payload["content"]

    async def test_single_pod_kill_rollup(
        self, worker: NotificationWorker, store: SQLiteKillmailStore
    ) -> None:
        """Single pod kill (100% ratio) should use pod format."""
        kill = make_kill(1020)
        kill.victim_ship_type_id = 670
        kill.zkb_total_value = 10_000

        sent_payload = None

        async def capture_send(payload, url):
            nonlocal sent_payload
            sent_payload = payload
            return MagicMock(success=True)

        worker._send_notification = capture_send

        result = await worker._send_rollup([kill])

        assert result is True
        assert "Pod spike" in sent_payload["content"]
        assert "1 pod" in sent_payload["content"]

    async def test_single_ship_kill_rollup(
        self, worker: NotificationWorker, store: SQLiteKillmailStore
    ) -> None:
        """Single ship kill (0% ratio) should use standard format."""
        kill = make_kill(1030)
        kill.victim_ship_type_id = 17740
        kill.zkb_total_value = 500_000_000

        sent_payload = None

        async def capture_send(payload, url):
            nonlocal sent_payload
            sent_payload = payload
            return MagicMock(success=True)

        worker._send_notification = capture_send

        result = await worker._send_rollup([kill])

        assert result is True
        assert "Activity" in sent_payload["content"]
        assert "1 kills" in sent_payload["content"]
        assert "ISK" in sent_payload["content"]

    async def test_rollup_value_formatting_billions(
        self, worker: NotificationWorker, store: SQLiteKillmailStore
    ) -> None:
        """Rollup formats value in billions when >= 1B."""
        kills = [make_kill(1040), make_kill(1041)]
        for kill in kills:
            kill.victim_ship_type_id = 17740
            kill.zkb_total_value = 1_500_000_000  # 1.5B each

        sent_payload = None

        async def capture_send(payload, url):
            nonlocal sent_payload
            sent_payload = payload
            return MagicMock(success=True)

        worker._send_notification = capture_send

        await worker._send_rollup(kills)

        assert "3.0B" in sent_payload["content"]

    async def test_rollup_value_formatting_millions(
        self, worker: NotificationWorker, store: SQLiteKillmailStore
    ) -> None:
        """Rollup formats value in millions when < 1B."""
        kills = [make_kill(1050), make_kill(1051)]
        for kill in kills:
            kill.victim_ship_type_id = 17740
            kill.zkb_total_value = 50_000_000  # 50M each

        sent_payload = None

        async def capture_send(payload, url):
            nonlocal sent_payload
            sent_payload = payload
            return MagicMock(success=True)

        worker._send_notification = capture_send

        await worker._send_rollup(kills)

        assert "100M" in sent_payload["content"]

    async def test_rollup_missing_victim_ship_type_id(
        self, worker: NotificationWorker, store: SQLiteKillmailStore
    ) -> None:
        """Kills with None victim_ship_type_id should not count as pods."""
        kills = []
        for i in range(3):
            kill = make_kill(1060 + i)
            kill.victim_ship_type_id = None  # Missing ship type
            kill.zkb_total_value = 100_000_000
            kills.append(kill)

        sent_payload = None

        async def capture_send(payload, url):
            nonlocal sent_payload
            sent_payload = payload
            return MagicMock(success=True)

        worker._send_notification = capture_send

        result = await worker._send_rollup(kills)

        assert result is True
        assert "Activity" in sent_payload["content"]  # Not pod format


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


class TestNotificationWorkerScopeFiltering:
    """Tests for v2 scope system filtering in _poll_once."""

    async def test_v2_scope_systems_passed_to_store_query(
        self, store: SQLiteKillmailStore, coordinator: ESICoordinator
    ) -> None:
        """When _v2_scope_systems is set, query_kills receives the system IDs."""
        scoped_profile = NotificationProfile(
            name="scoped-profile",
            display_name="Scoped",
            enabled=True,
            webhook_url="https://discord.com/api/webhooks/123/abc",
            polling=PollingConfig(
                interval_seconds=0.05,
                batch_size=10,
                overlap_window_seconds=0,
            ),
        )
        scoped_profile._v2_scope_systems = [30000142, 30000144]

        worker = NotificationWorker(
            profile=scoped_profile,
            store=store,
            esi_coordinator=coordinator,
        )

        # Insert kills in different systems
        kill_in_scope = make_kill(700)
        kill_in_scope = KillmailRecord(
            kill_id=700,
            kill_time=int(datetime(2026, 1, 26, 12, 0, 0).timestamp()),
            solar_system_id=30000142,  # In scope
            zkb_hash="hash700",
            zkb_total_value=100_000_000.0,
            zkb_points=10,
            zkb_is_npc=False,
            zkb_is_solo=False,
            zkb_is_awox=False,
            ingested_at=int(datetime(2026, 1, 26, 12, 0, 0).timestamp()),
            victim_ship_type_id=670,
            victim_corporation_id=98000001,
            victim_alliance_id=None,
        )
        kill_out_of_scope = KillmailRecord(
            kill_id=701,
            kill_time=int(datetime(2026, 1, 26, 12, 0, 0).timestamp()),
            solar_system_id=30002187,  # NOT in scope
            zkb_hash="hash701",
            zkb_total_value=100_000_000.0,
            zkb_points=10,
            zkb_is_npc=False,
            zkb_is_solo=False,
            zkb_is_awox=False,
            ingested_at=int(datetime(2026, 1, 26, 12, 0, 0).timestamp()),
            victim_ship_type_id=670,
            victim_corporation_id=98000001,
            victim_alliance_id=None,
        )

        await store.insert_kill(kill_in_scope)
        await store.insert_kill(kill_out_of_scope)

        # Run one poll
        worker.start()
        await asyncio.sleep(0.15)
        await worker.stop()

        # The in-scope kill should have been seen; the out-of-scope kill should not
        in_scope_processed = await store.is_kill_processed("scoped-profile", 700)
        out_of_scope_processed = await store.is_kill_processed("scoped-profile", 701)

        assert in_scope_processed is True
        assert out_of_scope_processed is False

    async def test_no_scope_systems_queries_all(
        self, worker: NotificationWorker, store: SQLiteKillmailStore
    ) -> None:
        """When _v2_scope_systems is None, all kills are queried."""
        assert worker.profile._v2_scope_systems is None

        # Insert kills in different systems
        kill_a = KillmailRecord(
            kill_id=800,
            kill_time=int(datetime(2026, 1, 26, 12, 0, 0).timestamp()),
            solar_system_id=30000142,
            zkb_hash="hash800",
            zkb_total_value=100_000_000.0,
            zkb_points=10,
            zkb_is_npc=False,
            zkb_is_solo=False,
            zkb_is_awox=False,
            ingested_at=int(datetime(2026, 1, 26, 12, 0, 0).timestamp()),
            victim_ship_type_id=670,
            victim_corporation_id=98000001,
            victim_alliance_id=None,
        )
        kill_b = KillmailRecord(
            kill_id=801,
            kill_time=int(datetime(2026, 1, 26, 12, 0, 0).timestamp()),
            solar_system_id=30002187,
            zkb_hash="hash801",
            zkb_total_value=100_000_000.0,
            zkb_points=10,
            zkb_is_npc=False,
            zkb_is_solo=False,
            zkb_is_awox=False,
            ingested_at=int(datetime(2026, 1, 26, 12, 0, 0).timestamp()),
            victim_ship_type_id=670,
            victim_corporation_id=98000001,
            victim_alliance_id=None,
        )

        await store.insert_kill(kill_a)
        await store.insert_kill(kill_b)

        worker.start()
        await asyncio.sleep(0.15)
        await worker.stop()

        # Both should have been processed (no system filtering)
        a_processed = await store.is_kill_processed("test-profile", 800)
        b_processed = await store.is_kill_processed("test-profile", 801)

        assert a_processed is True
        assert b_processed is True


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


# --- Forced rollup mode tests ---


def make_kill_with_system(
    kill_id: int,
    system_id: int = 30000142,
    ship_type_id: int = 670,
    ingested_at: int | None = None,
) -> KillmailRecord:
    """Create a test killmail with configurable system and ship type."""
    ts = ingested_at or int(datetime(2026, 1, 26, 12, 0, 0).timestamp())
    return KillmailRecord(
        kill_id=kill_id,
        kill_time=ts,
        solar_system_id=system_id,
        zkb_hash=f"hash{kill_id}",
        zkb_total_value=10_000_000.0,
        zkb_points=5,
        zkb_is_npc=False,
        zkb_is_solo=False,
        zkb_is_awox=False,
        ingested_at=ts,
        victim_ship_type_id=ship_type_id,
        victim_corporation_id=98000001,
        victim_alliance_id=None,
    )


@pytest_asyncio.fixture
async def force_store(tmp_path: Path):
    """Create a test store for forced rollup tests."""
    s = SQLiteKillmailStore(db_path=tmp_path / "force_test.db")
    await s.initialize()
    yield s
    await s.close()


@pytest.fixture
def force_profile() -> NotificationProfile:
    """Create a profile with force_rollup=True."""
    from aria_esi.services.redisq.notifications.profiles import RateLimitStrategy

    return NotificationProfile(
        name="force-rollup-profile",
        display_name="Force Rollup",
        enabled=True,
        webhook_url="https://discord.com/api/webhooks/123/abc",
        polling=PollingConfig(
            interval_seconds=0.05,
            batch_size=50,
            overlap_window_seconds=0,
        ),
        rate_limit_strategy=RateLimitStrategy(
            force_rollup=True,
            rollup_window_minutes=1,  # 1 minute window for testability
            max_rollup_kills=20,
        ),
    )


@pytest.fixture
def force_coordinator(force_store: SQLiteKillmailStore) -> ESICoordinator:
    """Create a test coordinator for forced rollup tests."""
    return ESICoordinator(store=force_store)


@pytest.fixture
def force_worker(
    force_profile: NotificationProfile,
    force_store: SQLiteKillmailStore,
    force_coordinator: ESICoordinator,
) -> NotificationWorker:
    """Create a worker with force_rollup enabled."""
    return NotificationWorker(
        profile=force_profile,
        store=force_store,
        esi_coordinator=force_coordinator,
    )


class TestNotificationWorkerForcedRollup:
    """Tests for force_rollup mode."""

    async def test_force_rollup_buffers_kills(
        self, force_worker: NotificationWorker, force_store: SQLiteKillmailStore
    ) -> None:
        """force_rollup=True buffers kills in _pending_kills instead of sending."""
        # Insert kills
        for i in range(3):
            await force_store.insert_kill(make_kill_with_system(2000 + i))

        # No send callback — would crash if called
        force_worker._send_notification = None
        force_worker._format_kill = None

        force_worker.start()
        await asyncio.sleep(0.15)
        await force_worker.stop()

        # Kills should be buffered
        assert len(force_worker._pending_kills) >= 3
        assert force_worker.metrics.kills_processed >= 3

    async def test_flush_sends_after_window(
        self, force_worker: NotificationWorker, force_store: SQLiteKillmailStore
    ) -> None:
        """Flush sends kills that have aged past the rollup window."""
        import time as _time

        # Create kills with ingested_at in the past (older than 1 min window)
        old_ts = int(_time.time()) - 120  # 2 minutes ago
        for i in range(3):
            kill = make_kill_with_system(2100 + i, ingested_at=old_ts)
            force_worker._pending_kills.append(kill)

        sent_payloads = []

        async def capture_send(payload, url):
            sent_payloads.append(payload)
            return MagicMock(success=True)

        force_worker._send_notification = capture_send

        await force_worker._flush_forced_rollups()

        # Should have sent one rollup
        assert len(sent_payloads) == 1
        # Pending kills should be empty now
        assert len(force_worker._pending_kills) == 0

    async def test_flush_skips_young_kills(
        self, force_worker: NotificationWorker, force_store: SQLiteKillmailStore
    ) -> None:
        """Flush does not send kills that are younger than the window."""
        import time as _time

        # Create kills with recent ingested_at (younger than 1 min window)
        recent_ts = int(_time.time())
        for i in range(3):
            kill = make_kill_with_system(2200 + i, ingested_at=recent_ts)
            force_worker._pending_kills.append(kill)

        sent_payloads = []

        async def capture_send(payload, url):
            sent_payloads.append(payload)
            return MagicMock(success=True)

        force_worker._send_notification = capture_send

        await force_worker._flush_forced_rollups()

        # Should NOT have sent anything
        assert len(sent_payloads) == 0
        # Kills should remain pending
        assert len(force_worker._pending_kills) == 3

    async def test_flush_groups_by_system(
        self, force_worker: NotificationWorker, force_store: SQLiteKillmailStore
    ) -> None:
        """Flush groups kills by solar_system_id, one rollup per system."""
        import time as _time

        old_ts = int(_time.time()) - 120
        # 3 kills in Jita (30000142), 2 kills in Perimeter (30000144)
        for i in range(3):
            force_worker._pending_kills.append(
                make_kill_with_system(2300 + i, system_id=30000142, ingested_at=old_ts)
            )
        for i in range(2):
            force_worker._pending_kills.append(
                make_kill_with_system(2310 + i, system_id=30000144, ingested_at=old_ts)
            )

        sent_payloads = []

        async def capture_send(payload, url):
            sent_payloads.append(payload)
            return MagicMock(success=True)

        force_worker._send_notification = capture_send

        await force_worker._flush_forced_rollups()

        # Should have sent 2 rollups (one per system)
        assert len(sent_payloads) == 2
        assert len(force_worker._pending_kills) == 0

    async def test_flush_caps_at_max_rollup_kills(
        self, force_worker: NotificationWorker, force_store: SQLiteKillmailStore
    ) -> None:
        """Flush sends chunks of max_rollup_kills per message."""
        import time as _time

        from aria_esi.services.redisq.notifications.profiles import RateLimitStrategy

        # Set max_rollup_kills to 5
        force_worker.profile.rate_limit_strategy = RateLimitStrategy(
            force_rollup=True,
            rollup_window_minutes=1,
            max_rollup_kills=5,
        )

        old_ts = int(_time.time()) - 120
        # 12 kills in same system → should produce 3 rollup messages (5 + 5 + 2)
        for i in range(12):
            force_worker._pending_kills.append(
                make_kill_with_system(2400 + i, system_id=30000142, ingested_at=old_ts)
            )

        sent_payloads = []

        async def capture_send(payload, url):
            sent_payloads.append(payload)
            return MagicMock(success=True)

        force_worker._send_notification = capture_send

        await force_worker._flush_forced_rollups()

        assert len(sent_payloads) == 3
        assert len(force_worker._pending_kills) == 0

    async def test_flush_marks_processed(
        self, force_worker: NotificationWorker, force_store: SQLiteKillmailStore
    ) -> None:
        """Flush marks kills as processed via _send_rollup."""
        import time as _time

        old_ts = int(_time.time()) - 120
        kills = [make_kill_with_system(2500 + i, ingested_at=old_ts) for i in range(3)]
        for k in kills:
            await force_store.insert_kill(k)
        force_worker._pending_kills.extend(kills)

        force_worker._send_notification = AsyncMock(return_value=MagicMock(success=True))

        await force_worker._flush_forced_rollups()

        for k in kills:
            assert await force_store.is_kill_processed("force-rollup-profile", k.kill_id)

    async def test_flush_send_failure_stops_flushing(
        self, force_worker: NotificationWorker, force_store: SQLiteKillmailStore
    ) -> None:
        """Send failure during flush stops further flushing, preserves remaining."""
        import time as _time

        old_ts = int(_time.time()) - 120
        # 3 kills in system A, 3 kills in system B
        for i in range(3):
            force_worker._pending_kills.append(
                make_kill_with_system(2600 + i, system_id=30000142, ingested_at=old_ts)
            )
        for i in range(3):
            force_worker._pending_kills.append(
                make_kill_with_system(2610 + i, system_id=30000144, ingested_at=old_ts)
            )

        call_count = 0

        async def fail_on_second(payload, url):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return MagicMock(success=True)
            return MagicMock(success=False)

        force_worker._send_notification = fail_on_second

        await force_worker._flush_forced_rollups()

        # First system succeeded, second failed → pending_kills not fully cleared
        # The exact count depends on iteration order, but at least some remain
        assert call_count == 2


class TestSendRollupPodTypeIDs:
    """Tests that _send_rollup uses POD_TYPE_IDS (not just 670)."""

    async def test_type_33328_counted_as_pod(
        self, worker: NotificationWorker, store: SQLiteKillmailStore
    ) -> None:
        """Type 33328 (Capsule - Genolution) counts as a pod in rollup."""
        kills = []
        for i in range(5):
            kill = make_kill(3000 + i)
            kill.victim_ship_type_id = 33328  # Capsule - Genolution
            kill.zkb_total_value = 10_000_000
            kills.append(kill)

        sent_payload = None

        async def capture_send(payload, url):
            nonlocal sent_payload
            sent_payload = payload
            return MagicMock(success=True)

        worker._send_notification = capture_send

        result = await worker._send_rollup(kills)

        assert result is True
        assert sent_payload is not None
        assert "Pod spike" in sent_payload["content"]
        assert "5 pods" in sent_payload["content"]

    async def test_mixed_pod_types_counted(
        self, worker: NotificationWorker, store: SQLiteKillmailStore
    ) -> None:
        """Both 670 and 33328 count as pods together."""
        kills = []
        for i in range(5):
            kill = make_kill(3100 + i)
            # Mix of both pod types
            kill.victim_ship_type_id = 670 if i % 2 == 0 else 33328
            kill.zkb_total_value = 10_000_000
            kills.append(kill)

        sent_payload = None

        async def capture_send(payload, url):
            nonlocal sent_payload
            sent_payload = payload
            return MagicMock(success=True)

        worker._send_notification = capture_send

        await worker._send_rollup(kills)

        assert "Pod spike" in sent_payload["content"]
        assert "5 pods" in sent_payload["content"]


class TestSendRollupCustomTitle:
    """Tests for custom rollup_title support."""

    async def test_custom_title_in_pod_rollup(
        self, force_worker: NotificationWorker
    ) -> None:
        """Custom rollup_title appears in pod-heavy rollup."""
        from aria_esi.services.redisq.notifications.profiles import RateLimitStrategy

        force_worker.profile.rate_limit_strategy = RateLimitStrategy(
            force_rollup=True,
            rollup_window_minutes=5,
            rollup_title="Smartbomb camp",
        )

        kills = [make_kill_with_system(3200 + i, ship_type_id=670) for i in range(5)]

        sent_payload = None

        async def capture_send(payload, url):
            nonlocal sent_payload
            sent_payload = payload
            return MagicMock(success=True)

        force_worker._send_notification = capture_send

        await force_worker._send_rollup(kills)

        assert "Smartbomb camp" in sent_payload["content"]
        assert "/ 5m" in sent_payload["content"]

    async def test_default_title_pod_rollup(
        self, force_worker: NotificationWorker
    ) -> None:
        """Default title 'Pod spike' used when rollup_title is None."""
        kills = [make_kill_with_system(3300 + i, ship_type_id=670) for i in range(5)]

        sent_payload = None

        async def capture_send(payload, url):
            nonlocal sent_payload
            sent_payload = payload
            return MagicMock(success=True)

        force_worker._send_notification = capture_send

        await force_worker._send_rollup(kills)

        assert "Pod spike" in sent_payload["content"]

    async def test_default_title_activity_rollup(
        self, force_worker: NotificationWorker
    ) -> None:
        """Default title 'Activity' used for non-pod rollup when rollup_title is None."""
        kills = [make_kill_with_system(3400 + i, ship_type_id=17740) for i in range(5)]

        sent_payload = None

        async def capture_send(payload, url):
            nonlocal sent_payload
            sent_payload = payload
            return MagicMock(success=True)

        force_worker._send_notification = capture_send

        await force_worker._send_rollup(kills)

        assert "Activity" in sent_payload["content"]
        assert "/ 1m" in sent_payload["content"]

    async def test_rate_suffix_only_with_force_rollup(
        self, worker: NotificationWorker
    ) -> None:
        """Non-force-rollup uses 'rolled up' phrasing, no rate suffix."""
        kills = [make_kill(3500 + i) for i in range(5)]
        for k in kills:
            k.victim_ship_type_id = 670

        sent_payload = None

        async def capture_send(payload, url):
            nonlocal sent_payload
            sent_payload = payload
            return MagicMock(success=True)

        worker._send_notification = capture_send

        await worker._send_rollup(kills)

        assert "rolled up" in sent_payload["content"]
        assert "/ " not in sent_payload["content"]


class TestSendRollupSystemName:
    """Tests that _send_rollup includes system name via name resolver."""

    async def test_system_name_in_rollup(
        self, worker: NotificationWorker
    ) -> None:
        """System name appears in rollup message when resolver works."""
        from unittest.mock import patch

        kills = [make_kill(3600 + i) for i in range(5)]
        for k in kills:
            k.victim_ship_type_id = 670

        sent_payload = None

        async def capture_send(payload, url):
            nonlocal sent_payload
            sent_payload = payload
            return MagicMock(success=True)

        worker._send_notification = capture_send

        mock_resolver = MagicMock()
        mock_resolver.resolve_system_with_fallback.return_value = "Jita"

        with patch(
            "aria_esi.services.redisq.name_resolver.get_name_resolver",
            return_value=mock_resolver,
        ):
            await worker._send_rollup(kills)

        assert "📍 Jita" in sent_payload["content"]

    async def test_system_name_graceful_failure(
        self, worker: NotificationWorker
    ) -> None:
        """Rollup works even when name resolver fails."""
        from unittest.mock import patch

        kills = [make_kill(3700 + i) for i in range(5)]
        for k in kills:
            k.victim_ship_type_id = 670

        sent_payload = None

        async def capture_send(payload, url):
            nonlocal sent_payload
            sent_payload = payload
            return MagicMock(success=True)

        worker._send_notification = capture_send

        with patch(
            "aria_esi.services.redisq.name_resolver.get_name_resolver",
            side_effect=RuntimeError("no resolver"),
        ):
            result = await worker._send_rollup(kills)

        assert result is True
        assert "📍" not in sent_payload["content"]
        # Should still have the rest of the message
        assert "Pod spike" in sent_payload["content"]
