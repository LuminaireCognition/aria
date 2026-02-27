"""Tests for backfill service (gap recovery from zKillboard)."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from aria_esi.services.redisq.backfill import (
    ESI_KILLMAIL_URL,
    ESI_RATE_LIMIT,
    ZKB_ALL_KILLS_URL,
    ZKB_REGION_KILLS_URL,
    _fetch_esi_killmail,
    _fetch_zkb_kills,
    backfill_from_zkillboard,
    startup_recovery,
)
from aria_esi.services.redisq.models import ProcessedKill, RedisQConfig

# =============================================================================
# Async helpers (pattern from test_hull_prices.py)
# =============================================================================


async def _async_return(value):
    """Helper to return a value from an async context."""
    return value


def _make_mock_response(status_code: int = 200, json_data=None):
    """Create a mock httpx response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data if json_data is not None else {}
    return resp


def _make_async_client(get_side_effect=None, get_return_value=None):
    """Create a mock httpx.AsyncClient with async context manager support."""
    client = MagicMock(spec=httpx.AsyncClient)
    if get_side_effect is not None:
        client.get = AsyncMock(side_effect=get_side_effect)
    elif get_return_value is not None:
        client.get = AsyncMock(return_value=get_return_value)
    else:
        client.get = AsyncMock(return_value=_make_mock_response())
    return client


def _make_zkb_kill(
    kill_id: int = 100,
    kill_time: str = "2024-06-15T12:00:00Z",
    kill_hash: str = "abc123",
    total_value: float = 50_000_000.0,
) -> dict:
    """Create a sample zKillboard kill entry."""
    return {
        "killmail_id": kill_id,
        "killmail_time": kill_time,
        "zkb": {
            "hash": kill_hash,
            "totalValue": total_value,
        },
    }


# =============================================================================
# TestFetchEsiKillmail
# =============================================================================


class TestFetchEsiKillmail:
    """Tests for _fetch_esi_killmail."""

    @pytest.mark.asyncio
    async def test_success_returns_json(self) -> None:
        """Test 200 response returns parsed JSON."""
        esi_data = {"killmail_id": 42, "solar_system_id": 30000142}
        client = _make_async_client(
            get_return_value=_make_mock_response(200, esi_data)
        )

        result = await _fetch_esi_killmail(client, 42, "hash123")

        assert result == esi_data

    @pytest.mark.asyncio
    async def test_non_200_returns_none(self) -> None:
        """Test non-200 status returns None."""
        client = _make_async_client(
            get_return_value=_make_mock_response(404)
        )

        result = await _fetch_esi_killmail(client, 42, "hash123")

        assert result is None

    @pytest.mark.asyncio
    async def test_http_error_returns_none(self) -> None:
        """Test httpx.RequestError returns None."""
        client = _make_async_client(
            get_side_effect=httpx.RequestError("connection failed")
        )

        result = await _fetch_esi_killmail(client, 42, "hash123")

        assert result is None

    @pytest.mark.asyncio
    async def test_constructs_correct_url(self) -> None:
        """Test URL contains kill_id and hash."""
        client = _make_async_client(
            get_return_value=_make_mock_response(200, {})
        )

        await _fetch_esi_killmail(client, 999, "myhash")

        expected_url = ESI_KILLMAIL_URL.format(kill_id=999, hash="myhash")
        client.get.assert_called_once_with(expected_url)


# =============================================================================
# TestFetchZkbKills
# =============================================================================


class TestFetchZkbKills:
    """Tests for _fetch_zkb_kills."""

    @pytest.mark.asyncio
    @patch("aria_esi.services.redisq.backfill.asyncio.sleep", new_callable=AsyncMock)
    async def test_no_regions_fetches_all_kills_url(self, mock_sleep) -> None:
        """Test no regions → GET all-kills URL."""
        kills_data = [_make_zkb_kill(1), _make_zkb_kill(2)]
        client = _make_async_client(
            get_return_value=_make_mock_response(200, kills_data)
        )

        result = await _fetch_zkb_kills(client, regions=None, max_kills=100)

        client.get.assert_called_once_with(ZKB_ALL_KILLS_URL)
        assert len(result) == 2

    @pytest.mark.asyncio
    @patch("aria_esi.services.redisq.backfill.asyncio.sleep", new_callable=AsyncMock)
    async def test_regions_fetches_per_region_url(self, mock_sleep) -> None:
        """Test regions → per-region URL."""
        kills_data = [_make_zkb_kill(1)]
        client = _make_async_client(
            get_return_value=_make_mock_response(200, kills_data)
        )

        result = await _fetch_zkb_kills(client, regions=[10000002], max_kills=100)

        expected_url = ZKB_REGION_KILLS_URL.format(region_id=10000002)
        client.get.assert_called_with(expected_url)
        assert len(result) == 1

    @pytest.mark.asyncio
    @patch("aria_esi.services.redisq.backfill.asyncio.sleep", new_callable=AsyncMock)
    async def test_multiple_regions_combines_results(self, mock_sleep) -> None:
        """Test multiple regions combine kill lists."""
        kill_a = _make_zkb_kill(1)
        kill_b = _make_zkb_kill(2)
        client = _make_async_client(
            get_side_effect=[
                _make_mock_response(200, [kill_a]),
                _make_mock_response(200, [kill_b]),
            ]
        )

        result = await _fetch_zkb_kills(
            client, regions=[10000002, 10000043], max_kills=100
        )

        assert len(result) == 2
        assert client.get.call_count == 2

    @pytest.mark.asyncio
    @patch("aria_esi.services.redisq.backfill.asyncio.sleep", new_callable=AsyncMock)
    async def test_max_kills_truncates_result(self, mock_sleep) -> None:
        """Test return truncated to max_kills."""
        kills = [_make_zkb_kill(i) for i in range(10)]
        client = _make_async_client(
            get_return_value=_make_mock_response(200, kills)
        )

        result = await _fetch_zkb_kills(client, regions=None, max_kills=3)

        assert len(result) == 3

    @pytest.mark.asyncio
    @patch("aria_esi.services.redisq.backfill.asyncio.sleep", new_callable=AsyncMock)
    async def test_region_fetch_breaks_at_max(self, mock_sleep) -> None:
        """Test region loop breaks when max_kills reached."""
        big_batch = [_make_zkb_kill(i) for i in range(10)]
        client = _make_async_client(
            get_side_effect=[
                _make_mock_response(200, big_batch),
                _make_mock_response(200, [_make_zkb_kill(99)]),
            ]
        )

        result = await _fetch_zkb_kills(
            client, regions=[1, 2, 3], max_kills=5
        )

        # Should break after first region (10 >= 5), second region not fetched
        assert client.get.call_count == 1
        assert len(result) == 5

    @pytest.mark.asyncio
    @patch("aria_esi.services.redisq.backfill.asyncio.sleep", new_callable=AsyncMock)
    async def test_all_kills_http_error_returns_empty(self, mock_sleep) -> None:
        """Test HTTP error on all-kills returns empty list."""
        client = _make_async_client(
            get_side_effect=httpx.RequestError("timeout")
        )

        result = await _fetch_zkb_kills(client, regions=None, max_kills=100)

        assert result == []

    @pytest.mark.asyncio
    @patch("aria_esi.services.redisq.backfill.asyncio.sleep", new_callable=AsyncMock)
    async def test_region_error_continues_to_next(self, mock_sleep) -> None:
        """Test error on one region continues to next."""
        kill = _make_zkb_kill(1)
        client = _make_async_client(
            get_side_effect=[
                httpx.RequestError("fail"),
                _make_mock_response(200, [kill]),
            ]
        )

        result = await _fetch_zkb_kills(
            client, regions=[10000002, 10000043], max_kills=100
        )

        assert len(result) == 1

    @pytest.mark.asyncio
    @patch("aria_esi.services.redisq.backfill.asyncio.sleep", new_callable=AsyncMock)
    async def test_all_kills_non_200_returns_empty(self, mock_sleep) -> None:
        """Test non-200 on all-kills returns empty list."""
        client = _make_async_client(
            get_return_value=_make_mock_response(502)
        )

        result = await _fetch_zkb_kills(client, regions=None, max_kills=100)

        assert result == []

    @pytest.mark.asyncio
    @patch("aria_esi.services.redisq.backfill.asyncio.sleep", new_callable=AsyncMock)
    async def test_region_non_200_continues(self, mock_sleep) -> None:
        """Test non-200 on one region, next region succeeds."""
        kill = _make_zkb_kill(1)
        client = _make_async_client(
            get_side_effect=[
                _make_mock_response(503),
                _make_mock_response(200, [kill]),
            ]
        )

        result = await _fetch_zkb_kills(
            client, regions=[10000002, 10000043], max_kills=100
        )

        assert len(result) == 1


# =============================================================================
# TestBackfillFromZkillboard
# =============================================================================


class TestBackfillFromZkillboard:
    """Tests for backfill_from_zkillboard."""

    def _patch_deps(self):
        """Return a stack of common patches for backfill_from_zkillboard."""
        return {
            "db": patch(
                "aria_esi.services.redisq.backfill.get_realtime_database"
            ),
            "client_cls": patch(
                "aria_esi.services.redisq.backfill.httpx.AsyncClient"
            ),
            "fetch_zkb": patch(
                "aria_esi.services.redisq.backfill._fetch_zkb_kills",
                new_callable=AsyncMock,
            ),
            "fetch_esi": patch(
                "aria_esi.services.redisq.backfill._fetch_esi_killmail",
                new_callable=AsyncMock,
            ),
            "parse": patch(
                "aria_esi.services.redisq.backfill.parse_esi_killmail"
            ),
            "sleep": patch(
                "aria_esi.services.redisq.backfill.asyncio.sleep",
                new_callable=AsyncMock,
            ),
        }

    def _setup_mocks(self, patches):
        """Start patches and configure defaults. Returns dict of mocks."""
        mocks = {name: p.start() for name, p in patches.items()}

        # Configure async client context manager
        mock_client = MagicMock()
        mocks["client_cls"].return_value.__aenter__ = AsyncMock(
            return_value=mock_client
        )
        mocks["client_cls"].return_value.__aexit__ = AsyncMock(
            return_value=False
        )
        mocks["mock_client"] = mock_client

        # Configure db
        mock_db = MagicMock()
        mock_db.kill_exists.return_value = False
        mock_db.save_kill.return_value = None
        mocks["db"].return_value = mock_db
        mocks["mock_db"] = mock_db

        # Configure parse
        mocks["parse"].return_value = MagicMock(spec=ProcessedKill)

        return mocks

    def _stop_patches(self, patches):
        for p in patches.values():
            p.stop()

    @pytest.mark.asyncio
    async def test_happy_path_processes_kills(self) -> None:
        """Test end-to-end: fetch → filter → parse → save."""
        patches = self._patch_deps()
        mocks = self._setup_mocks(patches)
        try:
            now = datetime(2024, 6, 15, 12, 30, 0)
            since = now - timedelta(hours=1)
            kill = _make_zkb_kill(100, "2024-06-15T12:00:00Z", "hash1")
            mocks["fetch_zkb"].return_value = [kill]
            mocks["fetch_esi"].return_value = {"killmail_id": 100}

            result = await backfill_from_zkillboard(since=since)

            assert len(result) == 1
            mocks["mock_db"].save_kill.assert_called_once()
        finally:
            self._stop_patches(patches)

    @pytest.mark.asyncio
    async def test_no_zkb_kills_returns_empty(self) -> None:
        """Test empty zKB response returns []."""
        patches = self._patch_deps()
        mocks = self._setup_mocks(patches)
        try:
            mocks["fetch_zkb"].return_value = []

            result = await backfill_from_zkillboard(
                since=datetime(2024, 6, 15, 12, 0, 0)
            )

            assert result == []
        finally:
            self._stop_patches(patches)

    @pytest.mark.asyncio
    @patch("aria_esi.services.redisq.backfill.datetime")
    async def test_default_since_one_hour_ago(self, mock_dt) -> None:
        """Test since=None defaults to utcnow() - 1 hour."""
        now = datetime(2024, 6, 15, 13, 0, 0)
        mock_dt.utcnow.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        patches = self._patch_deps()
        mocks = self._setup_mocks(patches)
        try:
            kill = _make_zkb_kill(100, "2024-06-15T12:30:00Z", "hash1")
            mocks["fetch_zkb"].return_value = [kill]
            mocks["fetch_esi"].return_value = {"killmail_id": 100}

            result = await backfill_from_zkillboard()

            # Kill at 12:30 is after since (12:00), should be processed
            assert len(result) == 1
        finally:
            self._stop_patches(patches)

    @pytest.mark.asyncio
    async def test_filters_kills_without_id(self) -> None:
        """Test kills without killmail_id are skipped."""
        patches = self._patch_deps()
        mocks = self._setup_mocks(patches)
        try:
            kill = {"killmail_time": "2024-06-15T12:00:00Z", "zkb": {"hash": "h"}}
            mocks["fetch_zkb"].return_value = [kill]

            result = await backfill_from_zkillboard(
                since=datetime(2024, 6, 15, 11, 0, 0)
            )

            assert result == []
        finally:
            self._stop_patches(patches)

    @pytest.mark.asyncio
    async def test_filters_kills_with_invalid_time(self) -> None:
        """Test kills with unparseable time are skipped."""
        patches = self._patch_deps()
        mocks = self._setup_mocks(patches)
        try:
            kill = {
                "killmail_id": 100,
                "killmail_time": "not-a-date",
                "zkb": {"hash": "h"},
            }
            mocks["fetch_zkb"].return_value = [kill]

            result = await backfill_from_zkillboard(
                since=datetime(2024, 6, 15, 11, 0, 0)
            )

            assert result == []
        finally:
            self._stop_patches(patches)

    @pytest.mark.asyncio
    async def test_filters_kills_before_since(self) -> None:
        """Test kills before 'since' are filtered out."""
        patches = self._patch_deps()
        mocks = self._setup_mocks(patches)
        try:
            # Kill is at 10:00, since is at 11:00
            kill = _make_zkb_kill(100, "2024-06-15T10:00:00Z", "hash1")
            mocks["fetch_zkb"].return_value = [kill]

            result = await backfill_from_zkillboard(
                since=datetime(2024, 6, 15, 11, 0, 0)
            )

            assert result == []
        finally:
            self._stop_patches(patches)

    @pytest.mark.asyncio
    async def test_filters_duplicate_kills(self) -> None:
        """Test kills already in database are skipped."""
        patches = self._patch_deps()
        mocks = self._setup_mocks(patches)
        try:
            mocks["mock_db"].kill_exists.return_value = True
            kill = _make_zkb_kill(100, "2024-06-15T12:00:00Z", "hash1")
            mocks["fetch_zkb"].return_value = [kill]

            result = await backfill_from_zkillboard(
                since=datetime(2024, 6, 15, 11, 0, 0)
            )

            assert result == []
        finally:
            self._stop_patches(patches)

    @pytest.mark.asyncio
    async def test_all_filtered_returns_empty(self) -> None:
        """Test all kills filtered out returns []."""
        patches = self._patch_deps()
        mocks = self._setup_mocks(patches)
        try:
            # All kills too old
            old_kill = _make_zkb_kill(100, "2024-06-14T10:00:00Z", "hash1")
            mocks["fetch_zkb"].return_value = [old_kill]

            result = await backfill_from_zkillboard(
                since=datetime(2024, 6, 15, 11, 0, 0)
            )

            assert result == []
        finally:
            self._stop_patches(patches)

    @pytest.mark.asyncio
    async def test_skips_kill_without_hash(self) -> None:
        """Test kills without zkb hash are skipped in processing loop."""
        patches = self._patch_deps()
        mocks = self._setup_mocks(patches)
        try:
            kill = {
                "killmail_id": 100,
                "killmail_time": "2024-06-15T12:00:00Z",
                "zkb": {},  # No hash
            }
            mocks["fetch_zkb"].return_value = [kill]

            result = await backfill_from_zkillboard(
                since=datetime(2024, 6, 15, 11, 0, 0)
            )

            assert result == []
            mocks["fetch_esi"].assert_not_called()
        finally:
            self._stop_patches(patches)

    @pytest.mark.asyncio
    async def test_skips_kill_without_id_in_esi_loop(self) -> None:
        """Test kill missing killmail_id in processing loop is skipped."""
        patches = self._patch_deps()
        mocks = self._setup_mocks(patches)
        try:
            # First kill has id for filtering, but we craft one that passes
            # filtering but loses id in the processing loop via get()
            # This edge case: kill has killmail_id=0 (falsy)
            kill = {
                "killmail_id": 0,
                "killmail_time": "2024-06-15T12:00:00Z",
                "zkb": {"hash": "abc"},
            }
            mocks["fetch_zkb"].return_value = [kill]

            result = await backfill_from_zkillboard(
                since=datetime(2024, 6, 15, 11, 0, 0)
            )

            # kill_id=0 is falsy, so it gets filtered in the first loop
            assert result == []
        finally:
            self._stop_patches(patches)

    @pytest.mark.asyncio
    async def test_continues_on_esi_failure(self) -> None:
        """Test ESI fetch returning None skips that kill, processes next."""
        patches = self._patch_deps()
        mocks = self._setup_mocks(patches)
        try:
            kill1 = _make_zkb_kill(100, "2024-06-15T12:00:00Z", "hash1")
            kill2 = _make_zkb_kill(101, "2024-06-15T12:01:00Z", "hash2")
            mocks["fetch_zkb"].return_value = [kill1, kill2]
            mocks["fetch_esi"].side_effect = [None, {"killmail_id": 101}]

            result = await backfill_from_zkillboard(
                since=datetime(2024, 6, 15, 11, 0, 0)
            )

            assert len(result) == 1

        finally:
            self._stop_patches(patches)

    @pytest.mark.asyncio
    async def test_continues_on_parse_failure(self) -> None:
        """Test parse_esi_killmail exception logs warning and continues."""
        patches = self._patch_deps()
        mocks = self._setup_mocks(patches)
        try:
            kill1 = _make_zkb_kill(100, "2024-06-15T12:00:00Z", "hash1")
            kill2 = _make_zkb_kill(101, "2024-06-15T12:01:00Z", "hash2")
            mocks["fetch_zkb"].return_value = [kill1, kill2]
            mocks["fetch_esi"].side_effect = [
                {"killmail_id": 100},
                {"killmail_id": 101},
            ]
            # First parse raises, second succeeds
            mocks["parse"].side_effect = [
                ValueError("bad data"),
                MagicMock(spec=ProcessedKill),
            ]

            result = await backfill_from_zkillboard(
                since=datetime(2024, 6, 15, 11, 0, 0)
            )

            assert len(result) == 1
        finally:
            self._stop_patches(patches)

    @pytest.mark.asyncio
    async def test_passes_regions_to_fetch(self) -> None:
        """Test regions parameter forwarded to _fetch_zkb_kills."""
        patches = self._patch_deps()
        mocks = self._setup_mocks(patches)
        try:
            mocks["fetch_zkb"].return_value = []

            await backfill_from_zkillboard(
                regions=[10000002, 10000043],
                since=datetime(2024, 6, 15, 11, 0, 0),
            )

            call_args = mocks["fetch_zkb"].call_args
            assert call_args[0][1] == [10000002, 10000043]
        finally:
            self._stop_patches(patches)

    @pytest.mark.asyncio
    async def test_rate_limiting_sleeps(self) -> None:
        """Test asyncio.sleep called per kill for rate limiting."""
        patches = self._patch_deps()
        mocks = self._setup_mocks(patches)
        try:
            kill1 = _make_zkb_kill(100, "2024-06-15T12:00:00Z", "hash1")
            kill2 = _make_zkb_kill(101, "2024-06-15T12:01:00Z", "hash2")
            mocks["fetch_zkb"].return_value = [kill1, kill2]
            mocks["fetch_esi"].return_value = {"killmail_id": 100}

            await backfill_from_zkillboard(
                since=datetime(2024, 6, 15, 11, 0, 0)
            )

            # sleep called once per kill in the processing loop
            expected_delay = 1.0 / ESI_RATE_LIMIT
            for call in mocks["sleep"].call_args_list:
                assert call[0][0] == pytest.approx(expected_delay)
            assert mocks["sleep"].call_count == 2
        finally:
            self._stop_patches(patches)


# =============================================================================
# TestStartupRecovery
# =============================================================================


class TestStartupRecovery:
    """Tests for startup_recovery."""

    def _make_config(self, filter_regions: list[int] | None = None) -> RedisQConfig:
        """Create a RedisQConfig for testing."""
        return RedisQConfig(
            enabled=True,
            queue_id="test-queue",
            filter_regions=filter_regions or [],
        )

    @pytest.mark.asyncio
    @patch("aria_esi.services.redisq.backfill.get_realtime_database")
    async def test_first_run_no_recovery(self, mock_get_db) -> None:
        """Test last_poll=None → first_run, no recovery."""
        mock_db = MagicMock()
        mock_db.get_last_poll_time.return_value = None
        mock_get_db.return_value = mock_db

        result = await startup_recovery(self._make_config())

        assert result["recovery_needed"] is False
        assert result["reason"] == "first_run"
        assert result["kills_recovered"] == 0

    @pytest.mark.asyncio
    @patch("aria_esi.services.redisq.backfill.datetime")
    @patch("aria_esi.services.redisq.backfill.get_realtime_database")
    async def test_small_gap_no_recovery(self, mock_get_db, mock_dt) -> None:
        """Test gap < 600s → gap_too_small."""
        now = datetime(2024, 6, 15, 12, 5, 0)
        last_poll = datetime(2024, 6, 15, 12, 0, 0)  # 5 min gap

        mock_dt.utcnow.return_value = now
        mock_db = MagicMock()
        mock_db.get_last_poll_time.return_value = last_poll
        mock_get_db.return_value = mock_db

        result = await startup_recovery(self._make_config())

        assert result["recovery_needed"] is False
        assert result["reason"] == "gap_too_small"
        assert result["gap_seconds"] == 300.0

    @pytest.mark.asyncio
    @patch("aria_esi.services.redisq.backfill.backfill_from_zkillboard", new_callable=AsyncMock)
    @patch("aria_esi.services.redisq.backfill.datetime")
    @patch("aria_esi.services.redisq.backfill.get_realtime_database")
    async def test_boundary_600s_triggers_recovery(
        self, mock_get_db, mock_dt, mock_backfill
    ) -> None:
        """Test gap == 600s → triggers recovery (not < 600)."""
        now = datetime(2024, 6, 15, 12, 10, 0)
        last_poll = datetime(2024, 6, 15, 12, 0, 0)  # Exactly 10 min

        mock_dt.utcnow.return_value = now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        mock_dt.return_value = now
        # Need timedelta to work
        mock_backfill.return_value = []

        mock_db = MagicMock()
        mock_db.get_last_poll_time.return_value = last_poll
        mock_get_db.return_value = mock_db

        result = await startup_recovery(self._make_config())

        # gap == 600s, 600 < 600 is False, so recovery triggers
        assert result["recovery_needed"] is True
        assert result["reason"] == "gap_detected"

    @pytest.mark.asyncio
    @patch("aria_esi.services.redisq.backfill.backfill_from_zkillboard", new_callable=AsyncMock)
    @patch("aria_esi.services.redisq.backfill.datetime")
    @patch("aria_esi.services.redisq.backfill.get_realtime_database")
    async def test_gap_triggers_recovery(
        self, mock_get_db, mock_dt, mock_backfill
    ) -> None:
        """Test 30min gap → recovery with kills."""
        now = datetime(2024, 6, 15, 12, 30, 0)
        last_poll = datetime(2024, 6, 15, 12, 0, 0)  # 30 min gap

        mock_dt.utcnow.return_value = now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        mock_processed = MagicMock(spec=ProcessedKill)
        mock_backfill.return_value = [mock_processed, mock_processed]

        mock_db = MagicMock()
        mock_db.get_last_poll_time.return_value = last_poll
        mock_get_db.return_value = mock_db

        result = await startup_recovery(self._make_config())

        assert result["recovery_needed"] is True
        assert result["kills_recovered"] == 2

    @pytest.mark.asyncio
    @patch("aria_esi.services.redisq.backfill.backfill_from_zkillboard", new_callable=AsyncMock)
    @patch("aria_esi.services.redisq.backfill.datetime")
    @patch("aria_esi.services.redisq.backfill.get_realtime_database")
    async def test_limits_recovery_to_2_hours(
        self, mock_get_db, mock_dt, mock_backfill
    ) -> None:
        """Test 5-hour gap → since = now - 2h (not last_poll)."""
        now = datetime(2024, 6, 15, 17, 0, 0)
        last_poll = datetime(2024, 6, 15, 12, 0, 0)  # 5 hour gap

        mock_dt.utcnow.return_value = now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        mock_backfill.return_value = []

        mock_db = MagicMock()
        mock_db.get_last_poll_time.return_value = last_poll
        mock_get_db.return_value = mock_db

        await startup_recovery(self._make_config())

        # Since should be now - 2h = 15:00, not last_poll 12:00
        call_kwargs = mock_backfill.call_args[1]
        assert call_kwargs["since"] == datetime(2024, 6, 15, 15, 0, 0)

    @pytest.mark.asyncio
    @patch("aria_esi.services.redisq.backfill.backfill_from_zkillboard", new_callable=AsyncMock)
    @patch("aria_esi.services.redisq.backfill.datetime")
    @patch("aria_esi.services.redisq.backfill.get_realtime_database")
    async def test_uses_last_poll_when_recent(
        self, mock_get_db, mock_dt, mock_backfill
    ) -> None:
        """Test 30min gap → since = last_poll."""
        now = datetime(2024, 6, 15, 12, 30, 0)
        last_poll = datetime(2024, 6, 15, 12, 0, 0)

        mock_dt.utcnow.return_value = now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        mock_backfill.return_value = []

        mock_db = MagicMock()
        mock_db.get_last_poll_time.return_value = last_poll
        mock_get_db.return_value = mock_db

        await startup_recovery(self._make_config())

        # Since should be last_poll (12:00), since it's > now - 2h (10:30)
        call_kwargs = mock_backfill.call_args[1]
        assert call_kwargs["since"] == last_poll

    @pytest.mark.asyncio
    @patch("aria_esi.services.redisq.backfill.backfill_from_zkillboard", new_callable=AsyncMock)
    @patch("aria_esi.services.redisq.backfill.datetime")
    @patch("aria_esi.services.redisq.backfill.get_realtime_database")
    async def test_passes_config_regions(
        self, mock_get_db, mock_dt, mock_backfill
    ) -> None:
        """Test filter_regions forwarded to backfill."""
        now = datetime(2024, 6, 15, 13, 0, 0)
        last_poll = datetime(2024, 6, 15, 12, 0, 0)

        mock_dt.utcnow.return_value = now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        mock_backfill.return_value = []

        mock_db = MagicMock()
        mock_db.get_last_poll_time.return_value = last_poll
        mock_get_db.return_value = mock_db

        config = self._make_config(filter_regions=[10000002, 10000043])
        await startup_recovery(config)

        call_kwargs = mock_backfill.call_args[1]
        assert call_kwargs["regions"] == [10000002, 10000043]

    @pytest.mark.asyncio
    @patch("aria_esi.services.redisq.backfill.backfill_from_zkillboard", new_callable=AsyncMock)
    @patch("aria_esi.services.redisq.backfill.datetime")
    @patch("aria_esi.services.redisq.backfill.get_realtime_database")
    async def test_empty_regions_passes_none(
        self, mock_get_db, mock_dt, mock_backfill
    ) -> None:
        """Test filter_regions=[] → regions=None."""
        now = datetime(2024, 6, 15, 13, 0, 0)
        last_poll = datetime(2024, 6, 15, 12, 0, 0)

        mock_dt.utcnow.return_value = now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        mock_backfill.return_value = []

        mock_db = MagicMock()
        mock_db.get_last_poll_time.return_value = last_poll
        mock_get_db.return_value = mock_db

        config = self._make_config(filter_regions=[])
        await startup_recovery(config)

        call_kwargs = mock_backfill.call_args[1]
        assert call_kwargs["regions"] is None

    @pytest.mark.asyncio
    @patch("aria_esi.services.redisq.backfill.backfill_from_zkillboard", new_callable=AsyncMock)
    @patch("aria_esi.services.redisq.backfill.datetime")
    @patch("aria_esi.services.redisq.backfill.get_realtime_database")
    async def test_result_has_all_fields(
        self, mock_get_db, mock_dt, mock_backfill
    ) -> None:
        """Test recovery result dict has all expected keys."""
        now = datetime(2024, 6, 15, 13, 0, 0)
        last_poll = datetime(2024, 6, 15, 12, 0, 0)

        mock_dt.utcnow.return_value = now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        mock_backfill.return_value = [MagicMock(spec=ProcessedKill)]

        mock_db = MagicMock()
        mock_db.get_last_poll_time.return_value = last_poll
        mock_get_db.return_value = mock_db

        result = await startup_recovery(self._make_config())

        assert "recovery_needed" in result
        assert "reason" in result
        assert "gap_seconds" in result
        assert "recovery_since" in result
        assert "kills_recovered" in result
        assert result["recovery_needed"] is True
        assert result["kills_recovered"] == 1
