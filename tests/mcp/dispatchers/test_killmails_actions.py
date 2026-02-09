"""
Tests for Killmails Dispatcher Action Implementations.

Tests the parameter validation and cursor encoding for killmails dispatcher.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
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
    store.initialize = AsyncMock()
    store.close = AsyncMock()

    return store


@pytest.fixture
def sample_killmails():
    """Sample killmail data for testing."""
    base_time = int(datetime.utcnow().timestamp())
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

    def test_query_store_not_initialized(self, killmails_dispatcher):
        """Query when store is not initialized."""
        with patch(
            "aria_esi.mcp.dispatchers.killmails._get_store",
            return_value=None
        ):
            result = asyncio.run(
                killmails_dispatcher(action="query")
            )

        assert "error" in result
        assert "not initialized" in result["error"].lower()


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
