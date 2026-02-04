"""
Tests for CLI Fit Selection Commands.

Tests skill-aware fit selection from archetype library.
Tests focus on display helpers and edge cases.
"""

from __future__ import annotations

import argparse
from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# Display Helper Tests
# =============================================================================


class TestDisplayCandidate:
    """Test _display_candidate helper function."""

    def test_display_candidate_none(self, capsys):
        """Displays (none) for None candidate."""
        from aria_esi.commands.fit import _display_candidate

        _display_candidate(None)
        captured = capsys.readouterr()
        assert "(none)" in captured.out

    def test_display_candidate_no_archetype(self, capsys):
        """Displays tier for candidate without archetype."""
        from aria_esi.commands.fit import _display_candidate

        mock_candidate = MagicMock()
        mock_candidate.tier = "standard"
        mock_candidate.archetype = None

        _display_candidate(mock_candidate)
        captured = capsys.readouterr()
        assert "standard" in captured.out

    def test_display_candidate_flyable(self, capsys):
        """Displays full candidate info for flyable fit."""
        from aria_esi.commands.fit import _display_candidate

        mock_candidate = MagicMock()
        mock_candidate.tier = "standard"
        mock_candidate.can_fly = True
        mock_candidate.missing_skills = []
        mock_candidate.archetype = MagicMock()
        mock_candidate.archetype.stats.dps = 300
        mock_candidate.archetype.stats.ehp = 20000
        mock_candidate.archetype.stats.tank_sustained = None
        mock_candidate.archetype.stats.estimated_isk = 50000000  # 50M ISK

        _display_candidate(mock_candidate)
        captured = capsys.readouterr()
        assert "Tier: standard" in captured.out
        assert "Can fly: Yes" in captured.out
        assert "DPS: 300" in captured.out

    def test_display_candidate_missing_skills(self, capsys):
        """Displays missing skills count for unflyable fit."""
        from aria_esi.commands.fit import _display_candidate

        mock_candidate = MagicMock()
        mock_candidate.tier = "advanced"
        mock_candidate.can_fly = False
        mock_candidate.missing_skills = [
            {"skill_name": "Drones", "required": 5, "current": 3},
            {"skill_name": "Gallente Cruiser", "required": 4, "current": 2},
        ]
        mock_candidate.archetype = MagicMock()
        mock_candidate.archetype.stats.dps = 400
        mock_candidate.archetype.stats.ehp = 30000
        mock_candidate.archetype.stats.tank_sustained = None
        mock_candidate.archetype.stats.estimated_isk = 100000000  # 100M ISK

        _display_candidate(mock_candidate)
        captured = capsys.readouterr()
        assert "Can fly: No" in captured.out
        assert "Missing skills: 2" in captured.out


# =============================================================================
# Fit Check Command Tests
# =============================================================================


class TestCmdFitCheck:
    """Test cmd_fit_check function."""

    def test_fit_check_exists(self):
        """cmd_fit_check function exists and is callable."""
        from aria_esi.commands.fit import cmd_fit_check
        assert callable(cmd_fit_check)


# =============================================================================
# Fit Validate Command Tests
# =============================================================================


class TestCmdFitValidate:
    """Test cmd_fit_validate function."""

    def test_fit_validate_exists(self):
        """Fit validate command exists and is callable."""
        from aria_esi.commands.fit import cmd_fit_validate

        # Just verify the function exists
        assert callable(cmd_fit_validate)
