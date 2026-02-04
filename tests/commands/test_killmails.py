"""
Tests for CLI Killmails Commands.

Tests kill and loss tracking for post-mortem analysis.
"""

from __future__ import annotations

import argparse
from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# Killmails Command Tests
# =============================================================================


class TestCmdKillmails:
    """Test cmd_killmails function."""

    def test_killmails_no_credentials(self):
        """Returns error when credentials are missing."""
        from aria_esi.commands.killmails import cmd_killmails
        from aria_esi.core import CredentialsError

        args = argparse.Namespace(
            limit=10,
            losses_only=False,
            kills_only=False,
            days=7,
        )

        mock_error = CredentialsError("No credentials found")

        with patch("aria_esi.commands.killmails.get_authenticated_client", side_effect=mock_error):
            result = cmd_killmails(args)

        assert "error" in result

    def test_killmails_empty_history(self, mock_authenticated_client):
        """Returns empty message when no killmails found."""
        from aria_esi.commands.killmails import cmd_killmails

        mock_client, mock_creds = mock_authenticated_client
        mock_client.get.return_value = []

        args = argparse.Namespace(
            limit=10,
            losses_only=False,
            kills_only=False,
            days=7,
        )

        with patch("aria_esi.commands.killmails.get_authenticated_client", return_value=(mock_client, mock_creds)), \
             patch("aria_esi.commands.killmails.ESIClient") as mock_public:
            mock_public.return_value = MagicMock()
            result = cmd_killmails(args)

        assert result.get("total_killmails", 0) == 0 or "No killmails" in result.get("message", "") or result.get("killmails") == []

    def test_killmails_esi_error(self, mock_authenticated_client):
        """Returns error when ESI fetch fails."""
        from aria_esi.commands.killmails import cmd_killmails
        from aria_esi.core import ESIError

        mock_client, mock_creds = mock_authenticated_client
        mock_client.get.side_effect = ESIError("Service unavailable", status_code=503)

        args = argparse.Namespace(
            limit=10,
            losses_only=False,
            kills_only=False,
            days=7,
        )

        with patch("aria_esi.commands.killmails.get_authenticated_client", return_value=(mock_client, mock_creds)):
            result = cmd_killmails(args)

        # May be esi_error or scope_not_authorized depending on mock setup
        assert "error" in result


# =============================================================================
# Damage Analysis Tests
# =============================================================================


class TestDamageTypeAnalysis:
    """Test damage type analysis functionality."""

    def test_analyze_damage_types_empty(self):
        """Empty attacker list returns zero damage."""
        from aria_esi.commands.killmails import _analyze_damage_types

        result = _analyze_damage_types([], {})

        assert result["total_damage"] == 0
        assert result["breakdown"] == {}

    def test_analyze_damage_types_with_weapons(self):
        """Damage types are inferred from weapon names."""
        from aria_esi.commands.killmails import _analyze_damage_types

        attackers = [
            {"damage_done": 1000, "weapon_type_id": 1},
            {"damage_done": 2000, "weapon_type_id": 2},
        ]
        type_cache = {
            1: {"name": "150mm Autocannon II"},
            2: {"name": "Heavy Pulse Laser II"},
        }

        result = _analyze_damage_types(attackers, type_cache)

        assert result["total_damage"] == 3000
        # Should have some breakdown
        assert len(result["breakdown"]) > 0

    def test_analyze_damage_types_unknown_weapon(self):
        """Unknown weapons are categorized as unknown."""
        from aria_esi.commands.killmails import _analyze_damage_types

        attackers = [
            {"damage_done": 1000, "weapon_type_id": 999},
        ]
        type_cache = {
            999: {"name": "Mystery Weapon"},
        }

        result = _analyze_damage_types(attackers, type_cache)

        assert result["total_damage"] == 1000
        assert "unknown" in result["breakdown"]


# =============================================================================
# Attacker Categorization Tests
# =============================================================================


class TestAttackerCategorization:
    """Test attacker categorization functionality."""

    def test_categorize_attackers_empty(self):
        """Empty attacker list returns empty categories."""
        from aria_esi.commands.killmails import _categorize_attackers

        result = _categorize_attackers([], 12345, {}, {})

        assert result["players"] == []
        assert result["npcs"] == []
        assert result["structures"] == []
        assert result["final_blow"] is None

    def test_categorize_attackers_player(self):
        """Player attackers are correctly categorized."""
        from aria_esi.commands.killmails import _categorize_attackers

        attackers = [
            {
                "character_id": 99999,
                "corporation_id": 98000001,
                "ship_type_id": 587,
                "damage_done": 5000,
                "final_blow": True,
            }
        ]
        type_cache = {587: {"name": "Rifter"}}
        char_cache = {99999: {"name": "Attacker Pilot"}}

        result = _categorize_attackers(attackers, 12345, type_cache, char_cache)

        assert len(result["players"]) == 1
        assert result["final_blow"] is not None

    def test_categorize_attackers_npc(self):
        """NPC attackers are correctly categorized."""
        from aria_esi.commands.killmails import _categorize_attackers

        attackers = [
            {
                "faction_id": 500010,  # Serpentis
                "ship_type_id": 17703,
                "damage_done": 3000,
                "final_blow": True,
            }
        ]
        type_cache = {17703: {"name": "Serpentis Chief Patroller"}}
        char_cache = {}

        result = _categorize_attackers(attackers, 12345, type_cache, char_cache)

        assert len(result["npcs"]) == 1


# =============================================================================
# NPC Damage Profile Tests
# =============================================================================


class TestNPCDamageProfiles:
    """Test NPC damage profile lookup."""

    def test_serpentis_profile(self):
        """Serpentis damage profile is correct."""
        from aria_esi.commands.killmails import NPC_DAMAGE_PROFILES

        profile = NPC_DAMAGE_PROFILES.get("Serpentis")
        assert profile is not None
        assert "kinetic" in profile["deals"]
        assert "thermal" in profile["deals"]

    def test_angel_cartel_profile(self):
        """Angel Cartel damage profile is correct."""
        from aria_esi.commands.killmails import NPC_DAMAGE_PROFILES

        profile = NPC_DAMAGE_PROFILES.get("Angel Cartel")
        assert profile is not None
        assert "explosive" in profile["deals"]
        assert "kinetic" in profile["deals"]

    def test_blood_raider_profile(self):
        """Blood Raider damage profile is correct."""
        from aria_esi.commands.killmails import NPC_DAMAGE_PROFILES

        profile = NPC_DAMAGE_PROFILES.get("Blood Raider")
        assert profile is not None
        assert "em" in profile["deals"]
        assert "thermal" in profile["deals"]


# =============================================================================
# Weapon Damage Hints Tests
# =============================================================================


class TestWeaponDamageHints:
    """Test weapon damage type hints."""

    def test_autocannon_damage_hint(self):
        """Autocannon damage hint is explosive/kinetic."""
        from aria_esi.commands.killmails import DAMAGE_TYPE_HINTS

        hint = DAMAGE_TYPE_HINTS.get("Autocannon")
        assert hint is not None
        assert "explosive" in hint
        assert "kinetic" in hint

    def test_laser_damage_hint(self):
        """Laser damage hint is EM/thermal."""
        from aria_esi.commands.killmails import DAMAGE_TYPE_HINTS

        hint = DAMAGE_TYPE_HINTS.get("Laser")
        assert hint is not None
        assert "em" in hint
        assert "thermal" in hint

    def test_blaster_damage_hint(self):
        """Blaster damage hint is kinetic/thermal."""
        from aria_esi.commands.killmails import DAMAGE_TYPE_HINTS

        hint = DAMAGE_TYPE_HINTS.get("Blaster")
        assert hint is not None
        assert "kinetic" in hint
        assert "thermal" in hint
