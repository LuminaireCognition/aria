"""
Tests for CLI RedisQ Commands.

Tests RedisQ real-time kill streaming service commands.
Tests focus on functions that exist and can be easily mocked.
"""

from __future__ import annotations

import argparse
from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# Module Import Tests
# =============================================================================


class TestRedisQModuleImports:
    """Test that redisq command module imports correctly."""

    def test_cmd_redisq_start_exists(self):
        """cmd_redisq_start function exists."""
        from aria_esi.commands.redisq import cmd_redisq_start
        assert callable(cmd_redisq_start)

    def test_cmd_redisq_stop_exists(self):
        """cmd_redisq_stop function exists."""
        from aria_esi.commands.redisq import cmd_redisq_stop
        assert callable(cmd_redisq_stop)

    def test_cmd_redisq_status_exists(self):
        """cmd_redisq_status function exists."""
        from aria_esi.commands.redisq import cmd_redisq_status
        assert callable(cmd_redisq_status)

    def test_cmd_redisq_backfill_exists(self):
        """cmd_redisq_backfill function exists."""
        from aria_esi.commands.redisq import cmd_redisq_backfill
        assert callable(cmd_redisq_backfill)

    def test_cmd_redisq_recent_exists(self):
        """cmd_redisq_recent function exists."""
        from aria_esi.commands.redisq import cmd_redisq_recent
        assert callable(cmd_redisq_recent)


# =============================================================================
# RedisQ Stop Command Tests
# =============================================================================


class TestCmdRedisQStop:
    """Test cmd_redisq_stop function."""

    def test_stop_returns_info(self):
        """Stop command returns informational message."""
        from aria_esi.commands.redisq import cmd_redisq_stop

        args = argparse.Namespace()
        result = cmd_redisq_stop(args)

        assert result["status"] == "info"
        assert "Ctrl+C" in result["message"]
        assert "query_timestamp" in result


# =============================================================================
# RedisQ Status Command Tests
# =============================================================================


class TestCmdRedisQStatus:
    """Test cmd_redisq_status function."""

    def test_status_returns_stats(self):
        """Status command returns database stats."""
        from aria_esi.commands.redisq import cmd_redisq_status

        args = argparse.Namespace()

        mock_stats = {
            "total_kills": 1000,
            "kills_24h": 500,
        }

        mock_db = MagicMock()
        mock_db.get_stats.return_value = mock_stats

        # Patch at the import location within the function
        with patch("aria_esi.services.redisq.database.get_realtime_database", return_value=mock_db):
            result = cmd_redisq_status(args)

        assert result["status"] == "ok"
        assert result["service"] == "redisq"
        assert result["database_stats"]["total_kills"] == 1000


# =============================================================================
# Watchlist Command Tests
# =============================================================================


class TestWatchlistCommands:
    """Test watchlist command functions."""

    def test_cmd_watchlist_list_exists(self):
        """cmd_watchlist_list function exists."""
        from aria_esi.commands.redisq import cmd_watchlist_list
        assert callable(cmd_watchlist_list)

    def test_cmd_watchlist_show_exists(self):
        """cmd_watchlist_show function exists."""
        from aria_esi.commands.redisq import cmd_watchlist_show
        assert callable(cmd_watchlist_show)

    def test_cmd_watchlist_create_exists(self):
        """cmd_watchlist_create function exists."""
        from aria_esi.commands.redisq import cmd_watchlist_create
        assert callable(cmd_watchlist_create)

    def test_watchlist_list_returns_dict(self):
        """Watchlist list command returns a dictionary."""
        from aria_esi.commands.redisq import cmd_watchlist_list

        args = argparse.Namespace(type=None)

        mock_manager = MagicMock()
        mock_manager.list_watchlists.return_value = []

        # Patch at the source module where get_entity_watchlist_manager is defined
        with patch("aria_esi.services.redisq.entity_watchlist.get_entity_watchlist_manager", return_value=mock_manager):
            result = cmd_watchlist_list(args)

        assert isinstance(result, dict)
        assert result["status"] == "ok"


# =============================================================================
# Topology Command Tests
# =============================================================================


class TestTopologyCommands:
    """Test topology command functions."""

    def test_cmd_topology_build_exists(self):
        """cmd_topology_build function exists."""
        from aria_esi.commands.redisq import cmd_topology_build
        assert callable(cmd_topology_build)

    def test_cmd_topology_show_exists(self):
        """cmd_topology_show function exists."""
        from aria_esi.commands.redisq import cmd_topology_show
        assert callable(cmd_topology_show)

    def test_cmd_topology_explain_exists(self):
        """cmd_topology_explain function exists."""
        from aria_esi.commands.redisq import cmd_topology_explain
        assert callable(cmd_topology_explain)

    def test_cmd_topology_presets_exists(self):
        """cmd_topology_presets function exists."""
        from aria_esi.commands.redisq import cmd_topology_presets
        assert callable(cmd_topology_presets)
