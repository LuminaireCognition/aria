"""
Tests for CLI Universe Commands.

Tests the borders, loop, system, and graph management commands.
"""

from __future__ import annotations

import argparse
from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# Borders Command Tests
# =============================================================================


class TestCmdBorders:
    """Test cmd_borders function."""

    def test_borders_missing_argument(self):
        """Returns error when neither region nor system specified."""
        from aria_esi.commands.universe import cmd_borders

        args = argparse.Namespace(region=None, system=None, limit=10)

        with patch("aria_esi.commands.universe.is_cache_available", return_value=True):
            result = cmd_borders(args)

        assert result["error"] == "missing_argument"
        assert "region" in result["message"] or "system" in result["message"]

    def test_borders_cache_not_available(self):
        """Returns error when cache is not available."""
        from aria_esi.commands.universe import cmd_borders

        args = argparse.Namespace(region="The Forge", system=None, limit=10)

        with patch("aria_esi.commands.universe.is_cache_available", return_value=False):
            result = cmd_borders(args)

        assert result["error"] == "cache_not_found"
        assert "hint" in result

    def test_borders_by_region_success(self):
        """Borders by region returns border systems."""
        from aria_esi.commands.universe import cmd_borders

        args = argparse.Namespace(region="The Forge", system=None, limit=10)

        mock_borders = [
            {"name": "System1", "security": 0.5, "adjacent_lowsec": ["LowSec1"]},
            {"name": "System2", "security": 0.6, "adjacent_lowsec": ["LowSec2"]},
        ]

        with patch("aria_esi.commands.universe.is_cache_available", return_value=True), \
             patch("aria_esi.commands.universe.find_border_systems_in_region", return_value=mock_borders):
            result = cmd_borders(args)

        assert "error" not in result
        assert result["search_type"] == "region"
        assert result["region"] == "The Forge"
        assert result["count"] == 2
        assert len(result["border_systems"]) == 2

    def test_borders_by_region_no_results(self):
        """Returns error when no border systems found in region."""
        from aria_esi.commands.universe import cmd_borders

        args = argparse.Namespace(region="Empty Region", system=None, limit=10)

        with patch("aria_esi.commands.universe.is_cache_available", return_value=True), \
             patch("aria_esi.commands.universe.find_border_systems_in_region", return_value=[]):
            result = cmd_borders(args)

        assert result["error"] == "no_results"

    def test_borders_by_system_success(self):
        """Borders by system proximity returns nearest borders."""
        from aria_esi.commands.universe import cmd_borders

        args = argparse.Namespace(region=None, system="Jita", limit=5)

        mock_borders = [
            {"name": "Border1", "security": 0.5, "jumps": 3},
        ]
        mock_origin = {"name": "Jita", "id": 30000142, "security": 0.95}

        with patch("aria_esi.commands.universe.is_cache_available", return_value=True), \
             patch("aria_esi.commands.universe.find_nearest_border_systems", return_value=mock_borders), \
             patch("aria_esi.commands.universe.get_system_by_name", return_value=("Jita", 30000142)), \
             patch("aria_esi.commands.universe.get_system_full_info", return_value=mock_origin):
            result = cmd_borders(args)

        assert "error" not in result
        assert result["search_type"] == "proximity"
        assert result["origin"]["name"] == "Jita"

    def test_borders_by_system_not_found(self):
        """Returns error when system not found."""
        from aria_esi.commands.universe import cmd_borders

        args = argparse.Namespace(region=None, system="NonexistentSystem", limit=5)

        with patch("aria_esi.commands.universe.is_cache_available", return_value=True), \
             patch("aria_esi.commands.universe.find_nearest_border_systems", return_value=[]), \
             patch("aria_esi.commands.universe.get_system_by_name", return_value=None):
            result = cmd_borders(args)

        assert result["error"] == "system_not_found"


# =============================================================================
# Loop Command Tests
# =============================================================================


class TestCmdLoop:
    """Test cmd_loop function."""

    def test_loop_invalid_target_jumps_too_low(self):
        """Returns error when target_jumps is below minimum."""
        from aria_esi.commands.universe import cmd_loop

        args = argparse.Namespace(
            origin="Jita",
            target_jumps=5,  # Below minimum of 10
            min_borders=3,
            max_borders=6,
            security_filter="highsec",
            avoid=None,
        )

        result = cmd_loop(args)

        assert result["error"] == "invalid_parameter"
        assert "target_jumps" in result["message"]

    def test_loop_invalid_target_jumps_too_high(self):
        """Returns error when target_jumps is above maximum."""
        from aria_esi.commands.universe import cmd_loop

        args = argparse.Namespace(
            origin="Jita",
            target_jumps=200,  # Above maximum of 100
            min_borders=3,
            max_borders=6,
            security_filter="highsec",
            avoid=None,
        )

        result = cmd_loop(args)

        assert result["error"] == "invalid_parameter"
        assert "target_jumps" in result["message"]

    def test_loop_invalid_min_borders_too_low(self):
        """Returns error when min_borders is below minimum."""
        from aria_esi.commands.universe import cmd_loop

        args = argparse.Namespace(
            origin="Jita",
            target_jumps=20,
            min_borders=1,  # Below minimum of 2
            max_borders=6,
            security_filter="highsec",
            avoid=None,
        )

        result = cmd_loop(args)

        assert result["error"] == "invalid_parameter"
        assert "min_borders" in result["message"]

    def test_loop_invalid_max_borders_below_min(self):
        """Returns error when max_borders is below min_borders."""
        from aria_esi.commands.universe import cmd_loop

        args = argparse.Namespace(
            origin="Jita",
            target_jumps=20,
            min_borders=5,
            max_borders=3,  # Below min_borders
            security_filter="highsec",
            avoid=None,
        )

        result = cmd_loop(args)

        assert result["error"] == "invalid_parameter"
        assert "max_borders" in result["message"]

    def test_loop_invalid_security_filter(self):
        """Returns error when security_filter is invalid."""
        from aria_esi.commands.universe import cmd_loop

        args = argparse.Namespace(
            origin="Jita",
            target_jumps=20,
            min_borders=3,
            max_borders=6,
            security_filter="invalid_filter",
            avoid=None,
        )

        result = cmd_loop(args)

        assert result["error"] == "invalid_parameter"
        assert "security_filter" in result["message"]


# =============================================================================
# System Info Command Tests
# =============================================================================


class TestCmdSystemInfo:
    """Test cmd_system_info function."""

    def test_system_info_cache_not_available(self):
        """Returns error when cache is not available."""
        from aria_esi.commands.universe import cmd_system_info

        args = argparse.Namespace(system="Jita")

        with patch("aria_esi.commands.universe.is_cache_available", return_value=False):
            result = cmd_system_info(args)

        assert result["error"] == "cache_not_found"

    def test_system_info_system_not_found(self):
        """Returns error when system not found."""
        from aria_esi.commands.universe import cmd_system_info

        args = argparse.Namespace(system="NonexistentSystem")

        with patch("aria_esi.commands.universe.is_cache_available", return_value=True), \
             patch("aria_esi.commands.universe.get_system_by_name", return_value=None):
            result = cmd_system_info(args)

        assert result["error"] == "system_not_found"

    def test_system_info_success(self):
        """Returns system info when found."""
        from aria_esi.commands.universe import cmd_system_info

        args = argparse.Namespace(system="Jita")

        mock_info = {
            "name": "Jita",
            "id": 30000142,
            "security": 0.95,
            "region": "The Forge",
            "constellation": "Kimotoro",
        }

        with patch("aria_esi.commands.universe.is_cache_available", return_value=True), \
             patch("aria_esi.commands.universe.get_system_by_name", return_value=("Jita", 30000142)), \
             patch("aria_esi.commands.universe.get_system_full_info", return_value=mock_info):
            result = cmd_system_info(args)

        assert "error" not in result
        assert result["system"]["name"] == "Jita"


# =============================================================================
# Cache Info Command Tests
# =============================================================================


class TestCmdCacheInfo:
    """Test cmd_cache_info function."""

    def test_cache_info_returns_data(self):
        """Returns cache info from get_cache_info."""
        from aria_esi.commands.universe import cmd_cache_info

        args = argparse.Namespace()

        mock_cache_info = {
            "version": "1.0",
            "system_count": 8000,
            "border_count": 500,
        }

        with patch("aria_esi.commands.universe.get_cache_info", return_value=mock_cache_info):
            result = cmd_cache_info(args)

        assert result["version"] == "1.0"
        assert result["system_count"] == 8000
        assert "query_timestamp" in result

    def test_cache_info_empty(self):
        """Returns empty info when cache is not available."""
        from aria_esi.commands.universe import cmd_cache_info

        args = argparse.Namespace()

        with patch("aria_esi.commands.universe.get_cache_info", return_value={}):
            result = cmd_cache_info(args)

        assert "query_timestamp" in result
