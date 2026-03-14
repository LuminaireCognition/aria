"""
Tests for Killmails Dispatcher Action Implementations.

Tests the parameter validation and cursor encoding for killmails dispatcher.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# =============================================================================
# Test Fixtures
# =============================================================================


@dataclass
class MockKillmail:
    """Mock killmail for testing."""
    kill_id: int
    kill_time: int
    solar_system_id: int
    zkb_total_value: int
    victim_ship_type_id: int
    victim_corporation_id: int
    zkb_is_npc: bool
    zkb_is_solo: bool


@pytest.fixture
def killmails_dispatcher(standard_universe):
    """Create killmails dispatcher with mock server."""
    from aria_esi.mcp.dispatchers.killmails import register_killmails_dispatcher

    mock_server = MagicMock()
    captured_func = None

    def mock_tool():
        def decorator(func):
            nonlocal captured_func
            captured_func = func
            return func
        return decorator

    mock_server.tool = mock_tool
    register_killmails_dispatcher(mock_server)
    return captured_func


@pytest.fixture
def mock_killmail_store():
    """Create mock killmail store."""
    store = AsyncMock()

    # Default query returns empty
    store.query_kills = AsyncMock(return_value=[])
    store.get_esi_details_batch = AsyncMock(return_value={})
    store.initialize = AsyncMock()
    store.close = AsyncMock()

    return store


@pytest.fixture
def sample_killmails():
    """Sample killmail data for testing."""
    base_time = int(datetime.now(UTC).timestamp())
    return [
        MockKillmail(
            kill_id=1001,
            kill_time=base_time - 3600,  # 1 hour ago
            solar_system_id=30000142,  # Jita
            zkb_total_value=100000000,
            victim_ship_type_id=587,  # Rifter
            victim_corporation_id=1000125,
            zkb_is_npc=False,
            zkb_is_solo=False,
        ),
        MockKillmail(
            kill_id=1002,
            kill_time=base_time - 1800,  # 30 mins ago
            solar_system_id=30000142,
            zkb_total_value=500000000,
            victim_ship_type_id=24690,  # Hurricane
            victim_corporation_id=1000125,
            zkb_is_npc=False,
            zkb_is_solo=True,
        ),
        MockKillmail(
            kill_id=1003,
            kill_time=base_time - 900,  # 15 mins ago
            solar_system_id=30002691,  # Uedama
            zkb_total_value=50000000,
            victim_ship_type_id=17703,  # Iteron
            victim_corporation_id=98000001,
            zkb_is_npc=False,
            zkb_is_solo=False,
        ),
    ]


# =============================================================================
# Query Action Tests
# =============================================================================


class TestQueryAction:
    """Tests for killmails query action."""

    def test_query_basic(self, killmails_dispatcher, mock_killmail_store, sample_killmails):
        """Basic killmail query."""
        mock_killmail_store.query_kills = AsyncMock(return_value=sample_killmails)

        with patch(
            "aria_esi.mcp.dispatchers.killmails._get_store",
            return_value=mock_killmail_store
        ):
            result = asyncio.run(
                killmails_dispatcher(action="query")
            )

        assert "kills" in result
        assert "count" in result

    def test_query_with_hours(self, killmails_dispatcher, mock_killmail_store, sample_killmails):
        """Query with time window."""
        mock_killmail_store.query_kills = AsyncMock(return_value=sample_killmails)

        with patch(
            "aria_esi.mcp.dispatchers.killmails._get_store",
            return_value=mock_killmail_store
        ):
            result = asyncio.run(
                killmails_dispatcher(action="query", hours=24)
            )

        assert result["query"]["hours"] == 24

    def test_query_with_min_value(self, killmails_dispatcher, mock_killmail_store, sample_killmails):
        """Query with minimum value filter."""
        high_value = [k for k in sample_killmails if k.zkb_total_value >= 100000000]
        mock_killmail_store.query_kills = AsyncMock(return_value=high_value)

        with patch(
            "aria_esi.mcp.dispatchers.killmails._get_store",
            return_value=mock_killmail_store
        ):
            result = asyncio.run(
                killmails_dispatcher(action="query", min_value=100000000)
            )

        assert result["query"]["min_value"] == 100000000

    def test_query_with_limit(self, killmails_dispatcher, mock_killmail_store, sample_killmails):
        """Query with result limit."""
        mock_killmail_store.query_kills = AsyncMock(return_value=sample_killmails[:2])

        with patch(
            "aria_esi.mcp.dispatchers.killmails._get_store",
            return_value=mock_killmail_store
        ):
            result = asyncio.run(
                killmails_dispatcher(action="query", limit=2)
            )

        assert len(result["kills"]) <= 2

    def test_query_pagination(self, killmails_dispatcher, mock_killmail_store, sample_killmails):
        """Query with pagination cursor."""
        # First page returns 3 items (plus one extra to detect more)
        mock_killmail_store.query_kills = AsyncMock(return_value=sample_killmails + [sample_killmails[0]])

        with patch(
            "aria_esi.mcp.dispatchers.killmails._get_store",
            return_value=mock_killmail_store
        ):
            result = asyncio.run(
                killmails_dispatcher(action="query", limit=3)
            )

        assert "next_cursor" in result
        assert result["next_cursor"] is not None

    def test_query_store_not_initialized_attempts_fallback(self, killmails_dispatcher):
        """Query when store is not initialized attempts ESI fallback."""
        mock_auth_ctx = MagicMock()
        mock_auth_ctx.character_id = 12345
        mock_auth_ctx.creds.has_scope.return_value = False  # No scope → error

        with (
            patch(
                "aria_esi.mcp.dispatchers.killmails._get_store",
                return_value=None,
            ),
            patch(
                "aria_esi.store.esi_client.get_authenticated_async_esi_client",
                new_callable=AsyncMock,
                return_value=mock_auth_ctx,
            ),
        ):
            result = asyncio.run(
                killmails_dispatcher(action="query")
            )

        # Should get an auth error (fallback attempted but scope missing)
        assert "error" in result


# =============================================================================
# Recent Action Tests
# =============================================================================


class TestRecentAction:
    """Tests for killmails recent action."""

    def test_recent_basic(self, killmails_dispatcher, mock_killmail_store, sample_killmails):
        """Basic recent killmails query."""
        mock_killmail_store.query_kills = AsyncMock(return_value=sample_killmails)

        with patch(
            "aria_esi.mcp.dispatchers.killmails._get_store",
            return_value=mock_killmail_store
        ):
            result = asyncio.run(
                killmails_dispatcher(action="recent")
            )

        assert "kills" in result
        assert "count" in result

    def test_recent_with_limit(self, killmails_dispatcher, mock_killmail_store, sample_killmails):
        """Recent with limit parameter."""
        mock_killmail_store.query_kills = AsyncMock(return_value=sample_killmails[:1])

        with patch(
            "aria_esi.mcp.dispatchers.killmails._get_store",
            return_value=mock_killmail_store
        ):
            result = asyncio.run(
                killmails_dispatcher(action="recent", limit=1)
            )

        assert result["query"]["limit"] == 1


# =============================================================================
# Stats Action Tests
# =============================================================================


class TestStatsAction:
    """Tests for killmails stats action."""

    def test_stats_basic(self, killmails_dispatcher, mock_killmail_store, sample_killmails):
        """Basic stats query."""
        mock_killmail_store.query_kills = AsyncMock(return_value=sample_killmails)

        with patch(
            "aria_esi.mcp.dispatchers.killmails._get_store",
            return_value=mock_killmail_store
        ):
            result = asyncio.run(
                killmails_dispatcher(action="stats")
            )

        assert "total_kills" in result
        assert "total_value" in result
        assert result["total_kills"] == 3

    def test_stats_total_value(self, killmails_dispatcher, mock_killmail_store, sample_killmails):
        """Stats calculates total value correctly."""
        mock_killmail_store.query_kills = AsyncMock(return_value=sample_killmails)

        with patch(
            "aria_esi.mcp.dispatchers.killmails._get_store",
            return_value=mock_killmail_store
        ):
            result = asyncio.run(
                killmails_dispatcher(action="stats")
            )

        expected_value = sum(k.zkb_total_value for k in sample_killmails)
        assert result["total_value"] == expected_value

    def test_stats_group_by_system(self, killmails_dispatcher, mock_killmail_store, sample_killmails):
        """Stats with group_by=system."""
        mock_killmail_store.query_kills = AsyncMock(return_value=sample_killmails)

        with patch(
            "aria_esi.mcp.dispatchers.killmails._get_store",
            return_value=mock_killmail_store
        ):
            result = asyncio.run(
                killmails_dispatcher(action="stats", group_by="system")
            )

        assert "groups" in result
        assert result["groups"] is not None
        # Sample has kills in two systems
        assert len(result["groups"]) == 2

    def test_stats_group_by_corporation(self, killmails_dispatcher, mock_killmail_store, sample_killmails):
        """Stats with group_by=corporation."""
        mock_killmail_store.query_kills = AsyncMock(return_value=sample_killmails)

        with patch(
            "aria_esi.mcp.dispatchers.killmails._get_store",
            return_value=mock_killmail_store
        ):
            result = asyncio.run(
                killmails_dispatcher(action="stats", group_by="corporation")
            )

        assert "groups" in result
        assert result["groups"] is not None

    def test_stats_group_by_hour(self, killmails_dispatcher, mock_killmail_store, sample_killmails):
        """Stats with group_by=hour."""
        mock_killmail_store.query_kills = AsyncMock(return_value=sample_killmails)

        with patch(
            "aria_esi.mcp.dispatchers.killmails._get_store",
            return_value=mock_killmail_store
        ):
            result = asyncio.run(
                killmails_dispatcher(action="stats", group_by="hour")
            )

        assert "groups" in result
        assert result["groups"] is not None

    def test_stats_time_window(self, killmails_dispatcher, mock_killmail_store, sample_killmails):
        """Stats includes time window info."""
        mock_killmail_store.query_kills = AsyncMock(return_value=sample_killmails)

        with patch(
            "aria_esi.mcp.dispatchers.killmails._get_store",
            return_value=mock_killmail_store
        ):
            result = asyncio.run(
                killmails_dispatcher(action="stats", hours=24)
            )

        assert "time_window" in result
        assert result["time_window"]["hours"] == 24


# =============================================================================
# Invalid Action Tests
# =============================================================================


class TestKillmailsInvalidActions:
    """Tests for invalid action handling."""

    def test_invalid_action_returns_error(self, killmails_dispatcher, mock_killmail_store):
        """Unknown action returns error response."""
        with patch(
            "aria_esi.mcp.dispatchers.killmails._get_store",
            return_value=mock_killmail_store
        ):
            result = asyncio.run(
                killmails_dispatcher(action="nonexistent_action")
            )

        assert "error" in result
        assert "valid_actions" in result


# =============================================================================
# Cursor Encoding/Decoding Tests
# =============================================================================


class TestCursorEncoding:
    """Tests for pagination cursor encoding/decoding."""

    def test_encode_decode_round_trip(self):
        """Cursor can be encoded and decoded."""
        from aria_esi.mcp.dispatchers.killmails import _decode_cursor, _encode_cursor

        kill_time = 1700000000
        kill_id = 12345

        cursor = _encode_cursor(kill_time, kill_id)
        decoded = _decode_cursor(cursor)

        assert decoded is not None
        assert decoded[0] == kill_time
        assert decoded[1] == kill_id

    def test_decode_invalid_cursor(self):
        """Invalid cursor returns None."""
        from aria_esi.mcp.dispatchers.killmails import _decode_cursor

        result = _decode_cursor("invalid_cursor_string")
        assert result is None

    def test_decode_empty_cursor(self):
        """Empty cursor returns None."""
        from aria_esi.mcp.dispatchers.killmails import _decode_cursor

        result = _decode_cursor("")
        assert result is None


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestKillmailsErrorHandling:
    """Tests for error handling."""

    def test_store_error_returns_error(self, killmails_dispatcher, mock_killmail_store):
        """Store errors are handled gracefully."""
        mock_killmail_store.query_kills = AsyncMock(side_effect=Exception("Database error"))

        with patch(
            "aria_esi.mcp.dispatchers.killmails._get_store",
            return_value=mock_killmail_store
        ):
            result = asyncio.run(
                killmails_dispatcher(action="query")
            )

        assert "error" in result

    def test_hours_clamped_to_valid_range(self, killmails_dispatcher, mock_killmail_store):
        """Hours parameter is clamped to valid range."""
        mock_killmail_store.query_kills = AsyncMock(return_value=[])

        with patch(
            "aria_esi.mcp.dispatchers.killmails._get_store",
            return_value=mock_killmail_store
        ):
            # Try 1000 hours (should clamp to 168)
            result = asyncio.run(
                killmails_dispatcher(action="query", hours=1000)
            )

        assert result["query"]["hours"] == 168

    def test_limit_clamped_to_valid_range(self, killmails_dispatcher, mock_killmail_store):
        """Limit parameter is clamped to valid range."""
        mock_killmail_store.query_kills = AsyncMock(return_value=[])

        with patch(
            "aria_esi.mcp.dispatchers.killmails._get_store",
            return_value=mock_killmail_store
        ):
            # Try 500 limit (should clamp to 100)
            result = asyncio.run(
                killmails_dispatcher(action="query", limit=500)
            )

        assert result["query"]["limit"] == 100


# =============================================================================
# Character ID Filtering Tests
# =============================================================================


class TestCharacterIdFiltering:
    """Tests for character_id filtering passthrough."""

    def test_query_with_character_id(
        self, killmails_dispatcher, mock_killmail_store, sample_killmails
    ):
        """Verify character_id is passed through to store.query_kills."""
        mock_killmail_store.query_kills = AsyncMock(return_value=sample_killmails[:1])

        with patch(
            "aria_esi.mcp.dispatchers.killmails._get_store",
            return_value=mock_killmail_store,
        ):
            result = asyncio.run(
                killmails_dispatcher(action="query", character_id=12345)
            )

        assert "kills" in result
        # Verify character_id was passed to the store
        call_kwargs = mock_killmail_store.query_kills.call_args
        assert call_kwargs.kwargs.get("character_id") == 12345

    def test_stats_with_character_id(
        self, killmails_dispatcher, mock_killmail_store, sample_killmails
    ):
        """Verify character_id is passed through to stats query."""
        mock_killmail_store.query_kills = AsyncMock(return_value=sample_killmails)

        with patch(
            "aria_esi.mcp.dispatchers.killmails._get_store",
            return_value=mock_killmail_store,
        ):
            result = asyncio.run(
                killmails_dispatcher(action="stats", character_id=67890)
            )

        assert "total_kills" in result
        call_kwargs = mock_killmail_store.query_kills.call_args
        assert call_kwargs.kwargs.get("character_id") == 67890


# =============================================================================
# ESI Enrichment Tests
# =============================================================================


class TestESIEnrichment:
    """Tests for ESI details enrichment in query results."""

    def _make_esi_detail(self, kill_id):
        """Create a mock ESI detail object."""
        from aria_esi.services.killmail_store.protocol import ESIKillmail

        return ESIKillmail(
            kill_id=kill_id,
            fetched_at=1700000000,
            fetch_status="success",
            fetch_attempts=1,
            victim_character_id=99000001,
            victim_ship_type_id=587,
            victim_corporation_id=1000125,
            victim_alliance_id=None,
            victim_damage_taken=12450,
            attacker_count=5,
            final_blow_character_id=99000002,
            final_blow_ship_type_id=16242,
            final_blow_corporation_id=98000001,
            attackers_json=None,
            items_json=None,
            position_json=None,
        )

    def test_query_enriches_with_esi_details(
        self, killmails_dispatcher, mock_killmail_store, sample_killmails
    ):
        """ESI fields are preferred when available."""
        km = sample_killmails[:1]
        mock_killmail_store.query_kills = AsyncMock(return_value=km)
        esi_detail = self._make_esi_detail(km[0].kill_id)
        mock_killmail_store.get_esi_details_batch = AsyncMock(
            return_value={km[0].kill_id: esi_detail}
        )

        with patch(
            "aria_esi.mcp.dispatchers.killmails._get_store",
            return_value=mock_killmail_store,
        ):
            result = asyncio.run(killmails_dispatcher(action="query"))

        kill = result["kills"][0]
        assert kill["has_esi_details"] is True
        assert kill["victim_character_id"] == 99000001
        assert kill["victim_damage_taken"] == 12450
        assert kill["attacker_count"] == 5

    def test_query_without_esi_details_uses_denormalized(
        self, killmails_dispatcher, mock_killmail_store, sample_killmails
    ):
        """Fallback to denormalized fields when ESI details unavailable."""
        km = sample_killmails[:1]
        mock_killmail_store.query_kills = AsyncMock(return_value=km)
        mock_killmail_store.get_esi_details_batch = AsyncMock(return_value={})

        with patch(
            "aria_esi.mcp.dispatchers.killmails._get_store",
            return_value=mock_killmail_store,
        ):
            result = asyncio.run(killmails_dispatcher(action="query"))

        kill = result["kills"][0]
        assert kill["has_esi_details"] is False
        assert kill["victim_ship_type_id"] == km[0].victim_ship_type_id
        assert kill["victim_corporation_id"] == km[0].victim_corporation_id
        assert "victim_character_id" not in kill
        assert "victim_damage_taken" not in kill

    def test_query_esi_batch_failure_degrades_gracefully(
        self, killmails_dispatcher, mock_killmail_store, sample_killmails
    ):
        """Exception in ESI batch fetch doesn't break query."""
        mock_killmail_store.query_kills = AsyncMock(return_value=sample_killmails[:1])
        mock_killmail_store.get_esi_details_batch = AsyncMock(
            side_effect=Exception("DB error")
        )

        with patch(
            "aria_esi.mcp.dispatchers.killmails._get_store",
            return_value=mock_killmail_store,
        ):
            result = asyncio.run(killmails_dispatcher(action="query"))

        assert "kills" in result
        assert result["count"] == 1
        # Should fall back gracefully — no ESI fields
        kill = result["kills"][0]
        assert kill["has_esi_details"] is False


# =============================================================================
# ESI Fallback Tests
# =============================================================================


def _make_mock_auth_ctx(has_scope: bool = True, char_id: int = 12345):
    """Create a mock authenticated ESI context."""
    ctx = MagicMock()
    ctx.character_id = char_id
    ctx.creds.has_scope.return_value = has_scope

    # Mock the client's get_safe to return killmail refs
    ctx.client = AsyncMock()
    return ctx


def _make_esi_killmail_response(kill_id: int, kill_hash: str = "abc123"):
    """Create a mock ESI killmail response (full killmail data)."""
    # Use current time so time-window filters don't exclude it
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "killmail_id": kill_id,
        "killmail_time": now,
        "solar_system_id": 30000142,
        "victim": {
            "ship_type_id": 587,
            "character_id": 99000001,
            "corporation_id": 1000125,
            "damage_taken": 12450,
        },
        "attackers": [
            {
                "character_id": 99000002,
                "ship_type_id": 16242,
                "corporation_id": 98000001,
                "final_blow": True,
                "damage_done": 6200,
            },
        ],
    }


class TestESIFallback:
    """Tests for ESI fallback when store is unavailable."""

    def test_query_falls_back_when_store_unavailable(self, killmails_dispatcher):
        """When store is None, query falls back to ESI."""
        mock_auth = _make_mock_auth_ctx()
        refs = [
            {"killmail_id": 1001, "killmail_hash": "hash1"},
            {"killmail_id": 1002, "killmail_hash": "hash2"},
        ]
        mock_auth.client.get_safe = AsyncMock(return_value=refs)

        mock_pub_client = AsyncMock()
        mock_pub_client.get_safe = AsyncMock(
            side_effect=[
                _make_esi_killmail_response(1001),
                _make_esi_killmail_response(1002),
            ]
        )

        with (
            patch("aria_esi.mcp.dispatchers.killmails._get_store", return_value=None),
            patch(
                "aria_esi.store.esi_client.get_authenticated_async_esi_client",
                new_callable=AsyncMock,
                return_value=mock_auth,
            ),
            patch(
                "aria_esi.store.esi_client.get_async_esi_client",
                new_callable=AsyncMock,
                return_value=mock_pub_client,
            ),
        ):
            result = asyncio.run(killmails_dispatcher(action="query", hours=24))

        assert "kills" in result
        assert result["count"] == 2
        assert result["source"] == "esi_fallback"

    def test_fallback_includes_source_field(self, killmails_dispatcher):
        """Verify source=esi_fallback is present in fallback response."""
        mock_auth = _make_mock_auth_ctx()
        mock_auth.client.get_safe = AsyncMock(return_value=[])

        with (
            patch("aria_esi.mcp.dispatchers.killmails._get_store", return_value=None),
            patch(
                "aria_esi.store.esi_client.get_authenticated_async_esi_client",
                new_callable=AsyncMock,
                return_value=mock_auth,
            ),
        ):
            result = asyncio.run(killmails_dispatcher(action="recent"))

        assert result["source"] == "esi_fallback"

    def test_fallback_scope_missing_returns_error(self, killmails_dispatcher):
        """Fallback with missing scope returns error."""
        mock_auth = _make_mock_auth_ctx(has_scope=False)

        with (
            patch("aria_esi.mcp.dispatchers.killmails._get_store", return_value=None),
            patch(
                "aria_esi.store.esi_client.get_authenticated_async_esi_client",
                new_callable=AsyncMock,
                return_value=mock_auth,
            ),
        ):
            result = asyncio.run(killmails_dispatcher(action="query"))

        assert "error" in result
        assert "scope_not_authorized" in result["error"]

    def test_stats_no_fallback_returns_error(self, killmails_dispatcher):
        """Stats still returns error when store is unavailable (no fallback)."""
        with patch("aria_esi.mcp.dispatchers.killmails._get_store", return_value=None):
            result = asyncio.run(killmails_dispatcher(action="stats"))

        assert "error" in result
        assert "not initialized" in result["error"].lower()


# =============================================================================
# ESI History Tests
# =============================================================================


class TestESIHistory:
    """Tests for esi_history action."""

    @pytest.fixture(autouse=True)
    def allow_authenticated(self):
        """Allow authenticated actions for esi_history tests."""
        with patch("aria_esi.mcp.dispatchers.killmails.check_capability"):
            yield

    def test_esi_history_basic(self, killmails_dispatcher):
        """Basic esi_history returns enriched kills."""
        mock_auth = _make_mock_auth_ctx()
        refs = [{"killmail_id": 2001, "killmail_hash": "hashA"}]
        mock_auth.client.get_safe = AsyncMock(return_value=refs)

        mock_pub_client = AsyncMock()
        mock_pub_client.get_safe = AsyncMock(
            return_value=_make_esi_killmail_response(2001)
        )

        with (
            patch(
                "aria_esi.store.esi_client.get_authenticated_async_esi_client",
                new_callable=AsyncMock,
                return_value=mock_auth,
            ),
            patch(
                "aria_esi.store.esi_client.get_async_esi_client",
                new_callable=AsyncMock,
                return_value=mock_pub_client,
            ),
        ):
            result = asyncio.run(
                killmails_dispatcher(action="esi_history", hours=168)
            )

        assert "kills" in result
        assert result["source"] == "esi_direct"
        assert result["count"] == 1
        # ESI data has no ISK value
        assert result["kills"][0]["value"] is None
        assert result["kills"][0]["has_esi_details"] is True

    def test_esi_history_hours_not_clamped(self, killmails_dispatcher):
        """esi_history does not clamp hours to 168."""
        mock_auth = _make_mock_auth_ctx()
        mock_auth.client.get_safe = AsyncMock(return_value=[])

        with patch(
            "aria_esi.store.esi_client.get_authenticated_async_esi_client",
            new_callable=AsyncMock,
            return_value=mock_auth,
        ):
            result = asyncio.run(
                killmails_dispatcher(action="esi_history", hours=2160)
            )

        assert result["query"]["hours"] == 2160

    def test_esi_history_pagination_cursor(self, killmails_dispatcher):
        """esi_history supports pagination via cursor."""
        from aria_esi.mcp.dispatchers.killmails import _encode_cursor

        mock_auth = _make_mock_auth_ctx()
        refs = [{"killmail_id": 3001, "killmail_hash": "hashB"}]
        mock_auth.client.get_safe = AsyncMock(return_value=refs)

        mock_pub_client = AsyncMock()
        mock_pub_client.get_safe = AsyncMock(
            return_value=_make_esi_killmail_response(3001)
        )

        cursor = _encode_cursor(0, 4000)  # before_kill_id=4000

        with (
            patch(
                "aria_esi.store.esi_client.get_authenticated_async_esi_client",
                new_callable=AsyncMock,
                return_value=mock_auth,
            ),
            patch(
                "aria_esi.store.esi_client.get_async_esi_client",
                new_callable=AsyncMock,
                return_value=mock_pub_client,
            ),
        ):
            result = asyncio.run(
                killmails_dispatcher(action="esi_history", cursor=cursor, hours=168)
            )

        # Verify before_kill_id was passed to ESI
        auth_call = mock_auth.client.get_safe.call_args
        assert auth_call.kwargs.get("params", {}).get("before_kill_id") == 4000 or \
            (auth_call.args[1] if len(auth_call.args) > 1 else auth_call.kwargs.get("params", {})).get("before_kill_id") == 4000

    def test_esi_history_scope_missing(self, killmails_dispatcher):
        """esi_history with missing scope returns error."""
        mock_auth = _make_mock_auth_ctx(has_scope=False)

        with patch(
            "aria_esi.store.esi_client.get_authenticated_async_esi_client",
            new_callable=AsyncMock,
            return_value=mock_auth,
        ):
            result = asyncio.run(
                killmails_dispatcher(action="esi_history", hours=168)
            )

        assert "error" in result
        assert "scope_not_authorized" in result["error"]


# =============================================================================
# Scope Metadata Tests
# =============================================================================


class TestScopeMetadata:
    """Tests for scope metadata in killmail responses."""

    def test_query_global_scope(self, killmails_dispatcher, mock_killmail_store, sample_killmails):
        """Query without character_id returns scope=global with scope_note."""
        mock_killmail_store.query_kills = AsyncMock(return_value=sample_killmails)

        with patch(
            "aria_esi.mcp.dispatchers.killmails._get_store",
            return_value=mock_killmail_store,
        ):
            result = asyncio.run(
                killmails_dispatcher(action="query")
            )

        assert result["scope"] == "global"
        assert "scope_note" in result
        assert "character_id" in result["scope_note"]

    def test_query_character_scope(
        self, killmails_dispatcher, mock_killmail_store, sample_killmails
    ):
        """Query with character_id returns scope=character, no scope_note."""
        mock_killmail_store.query_kills = AsyncMock(return_value=sample_killmails[:1])

        with patch(
            "aria_esi.mcp.dispatchers.killmails._get_store",
            return_value=mock_killmail_store,
        ):
            result = asyncio.run(
                killmails_dispatcher(action="query", character_id=12345)
            )

        assert result["scope"] == "character"
        assert "scope_note" not in result

    def test_esi_fallback_scope(self, killmails_dispatcher):
        """ESI fallback always returns scope=character."""
        mock_auth = _make_mock_auth_ctx()
        mock_auth.client.get_safe = AsyncMock(return_value=[])

        with (
            patch("aria_esi.mcp.dispatchers.killmails._get_store", return_value=None),
            patch(
                "aria_esi.store.esi_client.get_authenticated_async_esi_client",
                new_callable=AsyncMock,
                return_value=mock_auth,
            ),
        ):
            result = asyncio.run(
                killmails_dispatcher(action="query")
            )

        assert result["scope"] == "character"

    def test_esi_history_scope(self, killmails_dispatcher):
        """ESI history always returns scope=character."""
        mock_auth = _make_mock_auth_ctx()
        mock_auth.client.get_safe = AsyncMock(return_value=[])

        with (
            patch("aria_esi.mcp.dispatchers.killmails.check_capability"),
            patch(
                "aria_esi.store.esi_client.get_authenticated_async_esi_client",
                new_callable=AsyncMock,
                return_value=mock_auth,
            ),
        ):
            result = asyncio.run(
                killmails_dispatcher(action="esi_history", hours=168)
            )

        assert result["scope"] == "character"

    def test_esi_fallback_no_scope_note(self, killmails_dispatcher):
        """ESI fallback without character_id has no scope_note."""
        mock_auth = _make_mock_auth_ctx()
        mock_auth.client.get_safe = AsyncMock(return_value=[])

        with (
            patch("aria_esi.mcp.dispatchers.killmails._get_store", return_value=None),
            patch(
                "aria_esi.store.esi_client.get_authenticated_async_esi_client",
                new_callable=AsyncMock,
                return_value=mock_auth,
            ),
        ):
            result = asyncio.run(
                killmails_dispatcher(action="query")
            )

        assert result["scope"] == "character"
        assert "scope_note" not in result

    def test_esi_fallback_mismatched_character_id(self, killmails_dispatcher):
        """ESI fallback with mismatched character_id includes scope_note."""
        mock_auth = _make_mock_auth_ctx(char_id=12345)
        mock_auth.client.get_safe = AsyncMock(return_value=[])

        with (
            patch("aria_esi.mcp.dispatchers.killmails._get_store", return_value=None),
            patch(
                "aria_esi.store.esi_client.get_authenticated_async_esi_client",
                new_callable=AsyncMock,
                return_value=mock_auth,
            ),
        ):
            result = asyncio.run(
                killmails_dispatcher(action="query", character_id=99999)
            )

        assert result["scope"] == "character"
        assert "scope_note" in result
        assert "99999" in result["scope_note"]
