"""
ESI Pagination Contract Tests.

Tests the three pagination patterns used by ESI callers:
- Pattern A ("empty response terminates"): mining ledger, order history
- Pattern B ("X-Pages header driven"): structure scope refresh
- ESIResponse.x_pages property edge cases

These tests document current behavior and guard against CCP-side changes
to ESI response format that could silently truncate data.
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aria_esi.core.client import ESIError, ESIResponse

# =============================================================================
# Helpers
# =============================================================================


def make_esi_response(
    data: list | dict | None,
    status_code: int = 200,
    last_modified: str | None = "Wed, 22 Jan 2025 10:00:00 GMT",
    expires: str | None = "Wed, 22 Jan 2025 10:15:00 GMT",
    x_pages: int | None = None,
) -> ESIResponse:
    """Create an ESI response for testing."""
    headers = {}
    if last_modified:
        headers["Last-Modified"] = last_modified
    if expires:
        headers["Expires"] = expires
    if x_pages is not None:
        headers["X-Pages"] = str(x_pages)

    return ESIResponse(data=data, headers=headers, status_code=status_code)


def make_mining_entries(page: int, count: int = 3) -> list[dict]:
    """Generate realistic mining ledger entries for a given page."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return [
        {
            "date": today,
            "type_id": 1230,  # Veldspar
            "solar_system_id": 30000142,
            "quantity": 1000 * (page * count + i),
        }
        for i in range(count)
    ]


def create_mock_public_client():
    """Create mock public ESI client with type-safe method delegations."""
    mock = MagicMock()
    mock.get_dict_safe.side_effect = lambda *a, **kw: mock.get_safe(*a, **kw) or {}
    mock.get_list_safe.side_effect = lambda *a, **kw: mock.get_safe(*a, **kw) or []
    return mock


def _make_mock_credentials():
    """Create mock credentials for testing."""
    from aria_esi.core import Credentials

    creds = MagicMock(spec=Credentials)
    creds.character_id = 12345678
    creds.access_token = "test_token"
    creds.has_scope = MagicMock(return_value=True)
    return creds


def _make_mock_client():
    """Create mock ESI client for testing."""
    from aria_esi.core import ESIClient

    client = MagicMock(spec=ESIClient)
    client.get_list.side_effect = lambda *args, **kwargs: client.get(*args, **kwargs)
    client.get_dict.side_effect = lambda *args, **kwargs: client.get(*args, **kwargs)
    client.get_list_safe.side_effect = (
        lambda *args, **kwargs: client.get(*args, **kwargs) or []
    )
    client.get_dict_safe.side_effect = (
        lambda *args, **kwargs: client.get(*args, **kwargs) or {}
    )
    return client


def _setup_mining_mocks(mock_client, mock_credentials):
    """Set up the standard mining command mock context."""
    mock_public = create_mock_public_client()

    def get_safe_side_effect(url):
        if "/types/" in url:
            return {"name": "Veldspar"}
        if "/systems/" in url:
            return {"name": "Jita", "security_status": 0.95}
        return {"name": "Unknown"}

    mock_public.get_safe.side_effect = get_safe_side_effect
    return mock_public


def _run_mining_cmd(mock_client, mock_credentials, mock_public):
    """Run cmd_mining with standard mocks, return result."""
    import argparse

    from aria_esi.commands.mining import cmd_mining

    args = argparse.Namespace()
    args.days = 30
    args.system = None
    args.ore = None

    with patch(
        "aria_esi.commands.mining.get_authenticated_client",
        return_value=(mock_client, mock_credentials),
    ):
        with patch("aria_esi.commands.mining.ESIClient") as MockPublicClient:
            MockPublicClient.return_value = mock_public
            return cmd_mining(args)


# =============================================================================
# Pattern B (Structure) Fixtures
# =============================================================================


@pytest.fixture
def temp_db():
    """Create a temporary sync database for testing."""
    from aria_esi.store.market.database import MarketDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = MarketDatabase(db_path)

        conn = db._get_connection()
        test_types = [
            (34, "Tritanium", "tritanium", None, None, None, 0.01, 0.01),
            (35, "Pyerite", "pyerite", None, None, None, 0.01, 0.01),
        ]
        conn.executemany(
            """
            INSERT OR REPLACE INTO types (
                type_id, type_name, type_name_lower,
                group_id, category_id, market_group_id, volume, packaged_volume
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            test_types,
        )
        conn.commit()

        yield db, db_path
        db.close()


@pytest.fixture
def mock_esi_client():
    """Create a mock ESI client for structure tests."""
    return MagicMock()


def create_test_scope(sync_db, scope_name, scope_type, **kwargs):
    """Create a test scope with watchlist."""
    from aria_esi.store.market.database import MarketScope, WatchlistItem

    watchlist = sync_db.create_watchlist(f"{scope_name}_watchlist")
    items = []
    for type_id in [34, 35]:
        item = sync_db.add_watchlist_item(watchlist.watchlist_id, type_id)
        items.append(item)

    scope = sync_db.create_scope(
        scope_name=scope_name,
        scope_type=scope_type,
        watchlist_id=watchlist.watchlist_id,
        **kwargs,
    )
    return scope, items


# =============================================================================
# 1. ESIResponse X-Pages Edge Cases
# =============================================================================


class TestESIResponseXPagesEdgeCases:
    """Tests for ESIResponse.x_pages property with edge values CCP might send."""

    @pytest.mark.unit
    def test_x_pages_zero(self):
        """X-Pages: 0 should parse as 0."""
        resp = ESIResponse(data=[], headers={"X-Pages": "0"})
        assert resp.x_pages == 0

    @pytest.mark.unit
    def test_x_pages_negative(self):
        """X-Pages: -1 should parse as -1 (int() accepts negatives)."""
        resp = ESIResponse(data=[], headers={"X-Pages": "-1"})
        assert resp.x_pages == -1

    @pytest.mark.unit
    def test_x_pages_one(self):
        """X-Pages: 1 — single page response."""
        resp = ESIResponse(data=[], headers={"X-Pages": "1"})
        assert resp.x_pages == 1

    @pytest.mark.unit
    def test_x_pages_very_large(self):
        """X-Pages: 999999 — very large page count."""
        resp = ESIResponse(data=[], headers={"X-Pages": "999999"})
        assert resp.x_pages == 999999

    @pytest.mark.unit
    def test_x_pages_empty_string(self):
        """X-Pages: '' — empty string should return None (ValueError from int())."""
        resp = ESIResponse(data=[], headers={"X-Pages": ""})
        assert resp.x_pages is None

    @pytest.mark.unit
    def test_x_pages_float_string(self):
        """X-Pages: '5.0' — float string should return None (ValueError from int())."""
        resp = ESIResponse(data=[], headers={"X-Pages": "5.0"})
        assert resp.x_pages is None

    @pytest.mark.unit
    def test_x_pages_whitespace(self):
        """X-Pages: ' 5 ' — int() strips whitespace natively."""
        resp = ESIResponse(data=[], headers={"X-Pages": " 5 "})
        assert resp.x_pages == 5


# =============================================================================
# 2. Pattern A: Empty Response Terminates (mining ledger)
# =============================================================================


class TestEmptyResponseTerminationContract:
    """Tests Pattern A pagination through cmd_mining (simplest caller)."""

    @pytest.mark.integration
    def test_terminates_on_empty_list(self):
        """Pagination stops when ESI returns an empty list."""
        mock_client = _make_mock_client()
        mock_credentials = _make_mock_credentials()
        mock_public = _setup_mining_mocks(mock_client, mock_credentials)

        mock_client.get.side_effect = [
            make_mining_entries(1),
            make_mining_entries(2),
            [],
        ]

        result = _run_mining_cmd(mock_client, mock_credentials, mock_public)

        assert mock_client.get.call_count == 3
        assert result.get("summary", {}).get("total_entries") == 6

    @pytest.mark.integration
    def test_terminates_on_none_response(self):
        """Pagination stops when get() returns None (shouldn't happen but guards)."""
        mock_client = _make_mock_client()
        mock_credentials = _make_mock_credentials()
        mock_public = _setup_mining_mocks(mock_client, mock_credentials)

        mock_client.get.side_effect = [make_mining_entries(1), None]

        result = _run_mining_cmd(mock_client, mock_credentials, mock_public)

        assert mock_client.get.call_count == 2
        # Page 1 data should still be present
        assert result.get("summary", {}).get("total_entries") == 3

    @pytest.mark.integration
    def test_terminates_on_dict_response(self):
        """Pagination stops when ESI returns error dict instead of list."""
        mock_client = _make_mock_client()
        mock_credentials = _make_mock_credentials()
        mock_public = _setup_mining_mocks(mock_client, mock_credentials)

        mock_client.get.side_effect = [
            make_mining_entries(1),
            {"error": "timeout"},
        ]

        result = _run_mining_cmd(mock_client, mock_credentials, mock_public)

        assert mock_client.get.call_count == 2
        assert result.get("summary", {}).get("total_entries") == 3

    @pytest.mark.integration
    def test_first_page_empty(self):
        """Zero data on first page returns empty summary."""
        mock_client = _make_mock_client()
        mock_credentials = _make_mock_credentials()
        mock_public = _setup_mining_mocks(mock_client, mock_credentials)

        mock_client.get.side_effect = [[]]

        result = _run_mining_cmd(mock_client, mock_credentials, mock_public)

        assert result.get("summary", {}).get("total_entries") == 0
        assert result.get("summary", {}).get("total_quantity") == 0

    @pytest.mark.integration
    def test_aggregates_all_pages(self):
        """All items from all pages are accumulated via .extend()."""
        mock_client = _make_mock_client()
        mock_credentials = _make_mock_credentials()
        mock_public = _setup_mining_mocks(mock_client, mock_credentials)

        p1 = make_mining_entries(1, count=2)
        p2 = make_mining_entries(2, count=3)
        p3 = make_mining_entries(3, count=1)

        mock_client.get.side_effect = [p1, p2, p3, []]

        result = _run_mining_cmd(mock_client, mock_credentials, mock_public)

        assert mock_client.get.call_count == 4
        assert result.get("summary", {}).get("total_entries") == 6

    @pytest.mark.integration
    def test_partial_last_page(self):
        """Last page can have fewer items than earlier pages."""
        mock_client = _make_mock_client()
        mock_credentials = _make_mock_credentials()
        mock_public = _setup_mining_mocks(mock_client, mock_credentials)

        full_page = make_mining_entries(1, count=5)
        partial_page = make_mining_entries(2, count=1)

        mock_client.get.side_effect = [full_page, partial_page, []]

        result = _run_mining_cmd(mock_client, mock_credentials, mock_public)

        assert result.get("summary", {}).get("total_entries") == 6

    @pytest.mark.integration
    def test_safety_limit_20_enforced(self):
        """Safety limit breaks loop at page > 20 even if data keeps coming."""
        mock_client = _make_mock_client()
        mock_credentials = _make_mock_credentials()
        mock_public = _setup_mining_mocks(mock_client, mock_credentials)

        # Always return data — never an empty list
        mock_client.get.side_effect = [
            make_mining_entries(i, count=1) for i in range(25)
        ]

        result = _run_mining_cmd(mock_client, mock_credentials, mock_public)

        # Should stop at page 20 (safety limit: `if page > 20: break`)
        # Pages 1-20 fetched = 20 calls
        assert mock_client.get.call_count <= 21


# =============================================================================
# 3. Pattern B: X-Pages Header Driven (structure scope)
# =============================================================================


class TestXPagesDrivenPaginationContract:
    """Tests Pattern B pagination through MarketScopeFetcher._refresh_structure_scope()."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_x_pages_1_no_further_fetch(self, temp_db, mock_esi_client):
        """X-Pages=1 on page 1 means single page, no further requests."""
        from aria_esi.store.market.database_async import AsyncMarketDatabase
        from aria_esi.store.market.scope_refresh import MarketScopeFetcher

        sync_db, db_path = temp_db
        async_db = AsyncMarketDatabase(db_path)

        try:
            scope, items = create_test_scope(
                sync_db,
                "single_page_structure",
                "structure",
                structure_id=1234567890,
                parent_region_id=10000002,
            )

            call_count = 0

            def mock_get_with_headers(endpoint, auth=False, params=None, **kwargs):
                nonlocal call_count
                call_count += 1
                return make_esi_response(
                    [
                        {
                            "order_id": 1,
                            "type_id": 34,
                            "is_buy_order": True,
                            "price": 100.0,
                            "volume_remain": 1000,
                        }
                    ],
                    x_pages=1,
                )

            mock_esi_client.get_with_headers = mock_get_with_headers

            fetcher = MarketScopeFetcher(async_db, mock_esi_client)
            result = await fetcher.refresh_scope(scope, force_refresh=True)

            assert result.scan_status == "complete"
            assert result.pages_fetched == 1
            assert call_count == 1
        finally:
            await async_db.close()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_x_pages_missing_loops_to_max(self, temp_db, mock_esi_client):
        """Missing X-Pages header means total_pages=None, loops until max_pages."""
        from aria_esi.store.market.database_async import AsyncMarketDatabase
        from aria_esi.store.market.scope_refresh import MarketScopeFetcher

        sync_db, db_path = temp_db
        async_db = AsyncMarketDatabase(db_path)

        try:
            scope, items = create_test_scope(
                sync_db,
                "no_xpages_structure",
                "structure",
                structure_id=2222222222,
                parent_region_id=10000002,
            )

            def mock_get_with_headers(endpoint, auth=False, params=None, **kwargs):
                # Always return data, never set X-Pages
                page = int(params.get("page", 1)) if params else 1
                return make_esi_response(
                    [
                        {
                            "order_id": page,
                            "type_id": 34,
                            "is_buy_order": True,
                            "price": 100.0,
                            "volume_remain": 1000,
                        }
                    ],
                    x_pages=None,
                )

            mock_esi_client.get_with_headers = mock_get_with_headers

            fetcher = MarketScopeFetcher(async_db, mock_esi_client)
            result = await fetcher.refresh_scope(
                scope, force_refresh=True, max_structure_pages=3
            )

            # With no X-Pages, total_pages stays None, loop runs until max_pages
            assert result.pages_fetched == 3
        finally:
            await async_db.close()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_x_pages_changes_between_pages(self, temp_db, mock_esi_client):
        """Only page 1 X-Pages header is used; later pages' headers are ignored."""
        from aria_esi.store.market.database_async import AsyncMarketDatabase
        from aria_esi.store.market.scope_refresh import MarketScopeFetcher

        sync_db, db_path = temp_db
        async_db = AsyncMarketDatabase(db_path)

        try:
            scope, items = create_test_scope(
                sync_db,
                "changing_xpages_structure",
                "structure",
                structure_id=3333333333,
                parent_region_id=10000002,
            )

            def mock_get_with_headers(endpoint, auth=False, params=None, **kwargs):
                page = int(params.get("page", 1)) if params else 1
                # Page 1 says 3 pages; later pages say fewer
                reported_pages = 3 if page == 1 else 1
                return make_esi_response(
                    [
                        {
                            "order_id": page,
                            "type_id": 34,
                            "is_buy_order": True,
                            "price": 100.0,
                            "volume_remain": 1000,
                        }
                    ],
                    x_pages=reported_pages,
                )

            mock_esi_client.get_with_headers = mock_get_with_headers

            fetcher = MarketScopeFetcher(async_db, mock_esi_client)
            result = await fetcher.refresh_scope(scope, force_refresh=True)

            # Should fetch 3 pages based on page 1 header, ignoring page 2's "1"
            assert result.pages_fetched == 3
            assert result.scan_status == "complete"
        finally:
            await async_db.close()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_empty_data_mid_pagination(self, temp_db, mock_esi_client):
        """Empty data mid-pagination doesn't stop when X-Pages drives the loop."""
        from aria_esi.store.market.database_async import AsyncMarketDatabase
        from aria_esi.store.market.scope_refresh import MarketScopeFetcher

        sync_db, db_path = temp_db
        async_db = AsyncMarketDatabase(db_path)

        try:
            scope, items = create_test_scope(
                sync_db,
                "empty_mid_structure",
                "structure",
                structure_id=4444444444,
                parent_region_id=10000002,
            )

            def mock_get_with_headers(endpoint, auth=False, params=None, **kwargs):
                page = int(params.get("page", 1)) if params else 1
                if page == 2:
                    # Empty page in the middle
                    return make_esi_response([], x_pages=3)
                return make_esi_response(
                    [
                        {
                            "order_id": page,
                            "type_id": 34,
                            "is_buy_order": True,
                            "price": 100.0,
                            "volume_remain": 1000,
                        }
                    ],
                    x_pages=3,
                )

            mock_esi_client.get_with_headers = mock_get_with_headers

            fetcher = MarketScopeFetcher(async_db, mock_esi_client)
            result = await fetcher.refresh_scope(scope, force_refresh=True)

            # X-Pages=3 drives pagination; empty page 2 doesn't stop it
            assert result.pages_fetched == 3
            assert result.scan_status == "complete"
        finally:
            await async_db.close()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_max_pages_param_respected(self, temp_db, mock_esi_client):
        """max_pages truncates even when X-Pages says more pages exist."""
        from aria_esi.store.market.database_async import AsyncMarketDatabase
        from aria_esi.store.market.scope_refresh import MarketScopeFetcher

        sync_db, db_path = temp_db
        async_db = AsyncMarketDatabase(db_path)

        try:
            scope, items = create_test_scope(
                sync_db,
                "max_pages_structure",
                "structure",
                structure_id=5555555555,
                parent_region_id=10000002,
            )

            def mock_get_with_headers(endpoint, auth=False, params=None, **kwargs):
                page = int(params.get("page", 1)) if params else 1
                return make_esi_response(
                    [
                        {
                            "order_id": page,
                            "type_id": 34,
                            "is_buy_order": True,
                            "price": 100.0,
                            "volume_remain": 1000,
                        }
                    ],
                    x_pages=100,
                )

            mock_esi_client.get_with_headers = mock_get_with_headers

            fetcher = MarketScopeFetcher(async_db, mock_esi_client)
            result = await fetcher.refresh_scope(
                scope, force_refresh=True, max_structure_pages=3
            )

            assert result.pages_fetched == 3
            assert result.pages_truncated is True
            assert result.scan_status == "truncated"
        finally:
            await async_db.close()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_truncation_metadata_set(self, temp_db, mock_esi_client):
        """Truncation sets scan_status and pages_truncated correctly."""
        from aria_esi.store.market.database_async import AsyncMarketDatabase
        from aria_esi.store.market.scope_refresh import MarketScopeFetcher

        sync_db, db_path = temp_db
        async_db = AsyncMarketDatabase(db_path)

        try:
            scope, items = create_test_scope(
                sync_db,
                "truncation_meta_structure",
                "structure",
                structure_id=6666666666,
                parent_region_id=10000002,
            )

            def mock_get_with_headers(endpoint, auth=False, params=None, **kwargs):
                page = int(params.get("page", 1)) if params else 1
                return make_esi_response(
                    [
                        {
                            "order_id": page,
                            "type_id": 34,
                            "is_buy_order": True,
                            "price": 100.0,
                            "volume_remain": 1000,
                        }
                    ],
                    x_pages=10,
                )

            mock_esi_client.get_with_headers = mock_get_with_headers

            fetcher = MarketScopeFetcher(async_db, mock_esi_client)
            result = await fetcher.refresh_scope(
                scope, force_refresh=True, max_structure_pages=3
            )

            assert result.scan_status == "truncated"
            assert result.pages_truncated is True
            assert len(result.warnings) > 0
            assert "Truncated" in result.warnings[0]
        finally:
            await async_db.close()


# =============================================================================
# 4. Pagination Error Recovery
# =============================================================================


class TestPaginationErrorRecoveryContract:
    """Tests error recovery for both pagination patterns."""

    # --- Pattern A errors (mining) ---

    @pytest.mark.integration
    def test_pattern_a_error_page_1_returns_error(self):
        """ESIError on page 1 returns error dict (mining.py:69-75)."""
        mock_client = _make_mock_client()
        mock_credentials = _make_mock_credentials()
        mock_public = _setup_mining_mocks(mock_client, mock_credentials)

        mock_client.get.side_effect = ESIError("Server error", status_code=500)

        result = _run_mining_cmd(mock_client, mock_credentials, mock_public)

        assert result.get("error") == "esi_error"
        assert "mining ledger" in result.get("message", "").lower()

    @pytest.mark.integration
    def test_pattern_a_error_mid_pagination_keeps_partial(self):
        """ESIError on page 3 keeps pages 1-2 data (mining.py:76 — breaks)."""
        mock_client = _make_mock_client()
        mock_credentials = _make_mock_credentials()
        mock_public = _setup_mining_mocks(mock_client, mock_credentials)

        mock_client.get.side_effect = [
            make_mining_entries(1, count=2),
            make_mining_entries(2, count=3),
            ESIError("Timeout", status_code=504),
        ]

        result = _run_mining_cmd(mock_client, mock_credentials, mock_public)

        # Should have partial data from pages 1-2 (not an error dict)
        assert "error" not in result
        assert result.get("summary", {}).get("total_entries") == 5

    # --- Pattern B errors (structure scope) ---

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_pattern_b_403_sets_error_status(self, temp_db, mock_esi_client):
        """403 on structure endpoint sets scan_status='error'."""
        from aria_esi.store.market.database_async import AsyncMarketDatabase
        from aria_esi.store.market.scope_refresh import MarketScopeFetcher

        sync_db, db_path = temp_db
        async_db = AsyncMarketDatabase(db_path)

        try:
            scope, items = create_test_scope(
                sync_db,
                "forbidden_structure",
                "structure",
                structure_id=7777777777,
                parent_region_id=10000002,
            )

            def mock_get_with_headers(endpoint, auth=False, params=None, **kwargs):
                raise ESIError("Access denied", status_code=403)

            mock_esi_client.get_with_headers = mock_get_with_headers

            fetcher = MarketScopeFetcher(async_db, mock_esi_client)
            result = await fetcher.refresh_scope(scope, force_refresh=True)

            assert result.scan_status == "error"
            assert len(result.errors) > 0
            assert "Access denied" in result.errors[0] or "403" in result.errors[0]
        finally:
            await async_db.close()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_pattern_b_404_sets_error_status(self, temp_db, mock_esi_client):
        """404 on structure endpoint sets scan_status='error'."""
        from aria_esi.store.market.database_async import AsyncMarketDatabase
        from aria_esi.store.market.scope_refresh import MarketScopeFetcher

        sync_db, db_path = temp_db
        async_db = AsyncMarketDatabase(db_path)

        try:
            scope, items = create_test_scope(
                sync_db,
                "missing_structure",
                "structure",
                structure_id=8888888888,
                parent_region_id=10000002,
            )

            def mock_get_with_headers(endpoint, auth=False, params=None, **kwargs):
                raise ESIError("Not found", status_code=404)

            mock_esi_client.get_with_headers = mock_get_with_headers

            fetcher = MarketScopeFetcher(async_db, mock_esi_client)
            result = await fetcher.refresh_scope(scope, force_refresh=True)

            assert result.scan_status == "error"
            assert len(result.errors) > 0
            assert "not found" in result.errors[0].lower() or "destroyed" in result.errors[0].lower()
        finally:
            await async_db.close()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_pattern_b_error_mid_pagination_stops(self, temp_db, mock_esi_client):
        """ESIError on page 2 of 3 stops pagination and returns immediately."""
        from aria_esi.store.market.database_async import AsyncMarketDatabase
        from aria_esi.store.market.scope_refresh import MarketScopeFetcher

        sync_db, db_path = temp_db
        async_db = AsyncMarketDatabase(db_path)

        try:
            scope, items = create_test_scope(
                sync_db,
                "mid_error_structure",
                "structure",
                structure_id=9999999999,
                parent_region_id=10000002,
            )

            call_count = 0

            def mock_get_with_headers(endpoint, auth=False, params=None, **kwargs):
                nonlocal call_count
                call_count += 1
                page = int(params.get("page", 1)) if params else 1

                if page == 1:
                    return make_esi_response(
                        [
                            {
                                "order_id": 1,
                                "type_id": 34,
                                "is_buy_order": True,
                                "price": 100.0,
                                "volume_remain": 1000,
                            }
                        ],
                        x_pages=3,
                    )
                raise ESIError("Server error", status_code=500)

            mock_esi_client.get_with_headers = mock_get_with_headers

            fetcher = MarketScopeFetcher(async_db, mock_esi_client)
            result = await fetcher.refresh_scope(scope, force_refresh=True)

            assert result.scan_status == "error"
            # Should have stopped after page 2 error, not continued to page 3
            assert call_count == 2
        finally:
            await async_db.close()
